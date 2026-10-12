"""Magic outside battle.

Spell scrolls (M7): a wizard can copy one into their spellbook. It takes an Arcana check, costly inks (50 gold
crowns a spell level) and two hours a level, and the scroll is used up either way. Reading scrolls in battle is in
rules/combat.py.

Casting on the road (after v1): from the Spells screen, a spell that lasts (Mage Armour before the day's walk,
Stoneskin before the dungeon door) or one that heals. It takes a minute and a slot, and the law of the place may
have something to say about it. Spells that only make sense in a fight say so.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import spells as spellrules
from realmwalker.rules.inventory import remove_item
from realmwalker.rules.items import money_text

COPY_COST_PER_LEVEL = 5000  # copper
COPY_HOURS_PER_LEVEL = 2


def scroll_spell(tables, item) -> str | None:
    return tables.items.get(item.def_id).get("use", {}).get("scroll")


def copy_problem(game, char, item) -> str | None:
    """Why this character can't copy this scroll (None if they can try)."""
    sid = scroll_spell(game.tables, item)
    if sid is None or sid not in game.tables.spells:
        return "that is not a spell scroll"
    if char.cls != "wizard":
        return "only a wizard keeps a spellbook"
    spell = game.tables.spells[sid]
    if "wizard" not in spell["classes"]:
        return "that is a priest's prayer, not a wizard's spell"
    if sid in char.spells.get("spellbook", []):
        return "it is already in your spellbook"
    from realmwalker.rules.progression import spell_top_level

    if spell["level"] > spell_top_level(char, game.tables):
        return "it is beyond your skill for now"
    cost = COPY_COST_PER_LEVEL * spell["level"]
    if sum(c.money for c in game.party) < cost:
        return f"the inks cost {money_text(cost)}"
    return None


def copy_scroll(game, char, item) -> list[str]:
    problem = copy_problem(game, char, item)
    if problem:
        return [f"You can't copy it: {problem}."]
    from realmwalker.game.law import take_money

    t = game.tables
    sid = scroll_spell(t, item)
    spell = t.spells[sid]
    level = spell["level"]
    take_money(game, COPY_COST_PER_LEVEL * level)
    remove_item(char, item.uid, 1)
    game.pass_time(COPY_HOURS_PER_LEVEL * level * 60, "rest")
    sheet = game.sheet(char)
    rng = game.world.rng.child(f"copy/{sid}/{game.world.time}")
    roll = dice.d20(rng).natural
    bonus = sheet.skill_bonus("arcana")
    dc = 10 + level
    check = f"<dim>(Arcana {roll} {bonus:+d} = {roll + bonus} vs DC {dc})</>"
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "scroll", quiet=True)
    if roll + bonus >= dc:
        char.spells.setdefault("spellbook", []).append(sid)
        game.dirty = True
        return [f"<good>{char.name.split()[0]} copies {spell['name']} into the spellbook</> over "
                f"{COPY_HOURS_PER_LEVEL * level} hours of careful work. The scroll crumbles as the last word is taken "
                f"from it. {check}"]
    game.dirty = True
    return [f"<warn>The copy goes wrong</>: a slip of the pen, a word misread, and the scroll's magic unravels. "
            f"{check}"]


def scroll_stock(game, settlement, rng) -> dict[str, int]:
    """A few scrolls for sale where there are mages about."""
    from realmwalker.world import factions as fx

    t = game.tables
    mages = any(settlement.id in f.presence or f.seat == settlement.id
                for f in fx.active_factions(game.world, "mages_circle")) if game.world.factions else False
    if not mages and settlement.kind != "city":
        return {}
    top = 3 if settlement.kind == "city" else 2
    scrolls = [d for d, spec in t.items.defs.items() if spec.get("use", {}).get("scroll")
               and t.spells[spec["use"]["scroll"]]["level"] <= top]
    out = {}
    for _ in range(rng.randint(1, 3)):
        if scrolls:
            pick = rng.choice(scrolls)
            out[pick] = out.get(pick, 0) + 1
    return out


# ---------------------------------------------------------------------------- casting on the road
def road_targets(game, caster, spell_id: str) -> list:
    """Who a spell cast outside battle can be aimed at (empty when it takes everyone, or only the caster)."""
    target = game.tables.spells[spell_id]["target"]
    if target in ("ally", "downed_ally"):
        return [c for c in game.party if c.alive]
    return []


def lasting_text(hours: float) -> str:
    minutes = round(hours * 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    h = round(hours)
    return {1: "an hour", 8: "eight hours"}.get(h, f"{h} hours")


def strange_things(game, caster) -> list:
    """Magic things in the party's packs whose nature is still hidden, the caster's own first."""
    order = [caster] + [c for c in game.party if c is not caster]
    return [it for c in order if c.alive for it in c.inventory if it.magic and not it.magic.get("identified")]


def _needs(game, spell, target) -> bool:
    if spellrules.has_op(spell, "restore"):
        return bool([d for d in target.diseases if d.get("phase") in ("sick", "incubating") and d["id"] != "wound_fever"]
                    or [w for w in target.wounds if w.infection > 0])
    who = [c for c in game.party if c.alive] if spellrules.heals_many(spell) else [target]
    return any(c.hp < c.max_hp or c.wounds for c in who)


def road_problem(game, caster, spell_id: str, target=None) -> str | None:
    """Why this spell can't be cast here and now (None when it can)."""
    t = game.tables
    spell = t.spells[spell_id]
    ok, why = spellrules.on_the_road(t, spell_id)
    if not ok:
        return why
    if game.battle is not None:
        return "you are in a fight"
    ok, why = spellrules.can_cast(caster, t, spell_id)
    if not ok:
        return why
    target = target or caster
    use = spellrules.road_use(t, spell_id)
    if use == "identify" and not strange_things(game, caster):
        return "nothing you carry is strange to you"
    if use in ("heal", "cure") and not _needs(game, spell, target):
        return "there is nothing for it to mend" if use == "cure" else "nobody needs healing"
    on = caster if spell["target"] == "self" else target
    left = spellrules.lasting(on, t).get(spell_id, 0.0)
    if spell["target"] != "all_allies" and left > int(spell.get("rounds", 0)) / spellrules.ROUNDS_PER_HOUR / 2:
        return f"it is still working ({lasting_text(left)} left)"
    return None


def cast_on_road(game, caster, spell_id: str, target=None) -> list[str]:
    """Cast a spell outside battle. Healing goes through game/care.py (the worst wound first); a lasting spell is
    kept on whoever it was cast on. Returns what to say."""
    from realmwalker.game import care

    t = game.tables
    spell = t.spells[spell_id]
    target = target or caster
    why = road_problem(game, caster, spell_id, target)
    if why:
        return [f"{spell['name']}: {why}."]
    use = spellrules.road_use(t, spell_id)
    if use in ("heal", "cure"):
        wound = max(target.wounds, key=lambda w: (w.severity, w.bleed), default=None)
        return care.cast(game, caster, target, wound, spell_id)
    level = spell["level"]
    slot = spellrules.lowest_free_slot(caster, t, level) if level else None
    if level and slot is None:
        return ["No spell slot left for that. A long rest restores them."]
    if slot:
        spellrules.spend_slot(caster, slot)
    if use == "identify":
        from realmwalker.game import magic_items

        item = strange_things(game, caster)[0]
        name = game.tables.items.name(item, False)
        game.pass_time(10, "rest")
        msgs = [f"{caster.name.split()[0]} casts <magic>{spell['name']}</> over the {name}."]
        msgs += magic_items.identify(game, item)
        if game.world.factions:
            from realmwalker.game import law

            law.magic_check(game, caster)
        return msgs
    who = [c for c in game.party if c.alive] if spell["target"] == "all_allies" else \
        [caster if spell["target"] == "self" else target]
    hours = 0.0
    for c in who:
        hours = spellrules.keep(c, t, spell_id)
    first = caster.name.split()[0]
    on = "" if who == [caster] else (" on the party" if len(who) > 1 else f" on {who[0].name.split()[0]}")
    msgs = [f"{first} casts <magic>{spell['name']}</>{on}. <dim>It will last {lasting_text(hours)}.</>"]
    game.pass_time(1, "rest")
    game.dirty = True
    if game.world.factions:
        from realmwalker.game import law

        law.magic_check(game, caster)
    return msgs


# ---------------------------------------------------------------------------- writing a scroll
SCRIBE_COST_PER_LEVEL_SQUARED = 2500  # copper: costly inks, 25 gp for a first-level spell, 100 for a second...
SCRIBE_HOURS_PER_LEVEL = 2


def scribe_cost(level: int) -> int:
    return SCRIBE_COST_PER_LEVEL_SQUARED * level * level


def scribe_problem(game, char, sid: str) -> str | None:
    """Why this caster can't write this spell out as a scroll now (None if they can try). It takes ink and quill, a
    sheet of parchment, costly inks and one of the day's spell slots: the magic goes into the page."""
    from realmwalker.rules.inventory import carried

    t = game.tables
    spell = t.spells[sid] if sid in t.spells else None
    if spell is None or spell["level"] <= 0 or f"scroll_{sid}" not in t.items:
        return "only a spell of the first level or higher can be written out"
    things = carried(game.party)
    if not any((t.items.get(it.def_id).get("use") or {}).get("scribe") for it in things):
        return "you need ink and a quill"
    if not any(it.def_id == "parchment" for it in things):
        return "you need a sheet of parchment"
    ok, why = spellrules.can_cast(char, t, sid)
    if not ok:
        return why
    if game.busy:
        return "not now"
    cost = scribe_cost(spell["level"])
    if sum(c.money for c in game.party) < cost:
        return f"the inks cost {money_text(cost)}"
    return None


def scribe(game, char, sid: str) -> list[str]:
    """Write a spell out as a scroll: two hours a level, the inks, a sheet of parchment and a spell slot, and an Arcana
    check (Religion for a priest) against 10 + the spell's level. The scroll can be read once in a fight by anyone (by
    someone of another calling, with an Arcana check)."""
    problem = scribe_problem(game, char, sid)
    if problem:
        return [f"You can't write it: {problem}."]
    from realmwalker.game.law import take_money
    from realmwalker.rules.inventory import add_item

    t = game.tables
    spell = t.spells[sid]
    level = spell["level"]
    take_money(game, scribe_cost(level))
    owner = next(c for c in game.party if any(it.def_id == "parchment" for it in c.inventory))
    sheet_ = next(it for it in owner.inventory if it.def_id == "parchment")
    remove_item(owner, sheet_.uid, 1)
    slot = spellrules.lowest_free_slot(char, t, level)
    if slot is not None:
        spellrules.spend_slot(char, slot)
    game.pass_time(SCRIBE_HOURS_PER_LEVEL * level * 60, "rest")
    skill = "religion" if char.cls == "cleric" else "arcana"
    rng = game.world.rng.child(f"scribe/{sid}/{game.world.time}")
    roll = dice.d20(rng).natural
    bonus = game.sheet(char).skill_bonus(skill)
    dc = 10 + level
    check = f"<dim>({t.rules['skills'][skill]['name']} {roll} {bonus:+d} = {roll + bonus} vs DC {dc})</>"
    game.dirty = True
    if roll + bonus >= dc:
        add_item(char, t.items, f"scroll_{sid}", 1, made_at=game.world.time)
        return [f"<good>{char.name.split()[0]} writes {spell['name']} out as a scroll</> over "
                f"{SCRIBE_HOURS_PER_LEVEL * level} hours, and feels the spell go into the page. {check}"]
    return [f"<warn>The writing goes wrong</>: a blot, a word misplaced, and the spell drains out of the page and is "
            f"lost. {check}"]
