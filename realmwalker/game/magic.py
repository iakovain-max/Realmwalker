"""Magic outside battle.

Spell scrolls (DMG 2024): a wizard can copy one into their spellbook. It takes an Arcana check, costly inks (50
gold crowns a spell level) and two hours a level, and the scroll is used up either way. Whoever has the spell on their
list can read it aloud once (rules/spells.scroll_reader): in a fight from the spell menu (rules/combat.py), outside one
from the pack when the spell has a use there (`read_scroll`, through `cast_on_road`).

Casting on the road (after v1): from the Spells screen, a spell that lasts (Mage Armour before the day's walk,
Stoneskin before the dungeon door) or one that heals. It takes a minute and a slot, and the law of the place may
have something to say about it. Spells that only make sense in a fight say so.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup
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
    if spell["level"] == 0:
        return "cantrips are learned, not kept in a spellbook"
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


def scroll_readers(game, item) -> list[tuple]:
    """(character, how) for each of the party who can read this scroll, the surest first."""
    sid = scroll_spell(game.tables, item)
    if sid not in game.tables.spells:
        return []
    order = {"sure": 0, "device": 1, "check": 2, "device_check": 3}
    out = [(c, spellrules.scroll_reader(c, game.tables, sid)) for c in game.party if c.alive]
    return sorted([(c, how) for c, how in out if how], key=lambda p: order[p[1]])


def scroll_lines(game, item) -> list[str]:
    """What a spell scroll's card says: the spell, the scroll's numbers, and who in the party can read it."""
    t = game.tables
    sid = scroll_spell(t, item)
    if sid not in t.spells:
        return []
    spell = t.spells[sid]
    dc, attack = spellrules.scroll_numbers(t, spell["level"])
    rarity = (t.items.get(item.def_id).get("rarity") or "common").replace("_", " ")
    lines = [f"<magic>{spell['name']}</>: {spell['text']}",
             f"<dim>A {rarity} scroll. Read aloud it casts with save DC {dc} and attack +{attack}, needs no materials "
             f"and no spell slot, and crumbles once the spell is cast.</>"]
    readers = scroll_readers(game, item)
    if not readers:
        lines.append("<warn>No one in the party can read it: the spell is on none of your lists.</>")
        return lines
    words = []
    for c, how in readers:
        check = spellrules.scroll_check(game.sheet(c), t, sid, how)
        who = escape_markup(c.name.split()[0])
        if check is None:
            words.append(who + (" (Use Magic Device)" if how == "device" else ""))
        else:
            words.append(f"{who} (beyond them: an {check[2]} check first, DC {check[1]} at {check[0]:+d}, or the "
                         f"scroll is lost)")
    lines.append("Can read it: " + ", ".join(words) + ".")
    if spellrules.on_the_road(t, sid)[0]:
        lines.append("<dim>Read it here (Enter), or in a fight from the spell menu.</>")
    else:
        lines.append("<dim>Read it in a fight, from the spell menu (Cast a spell).</>")
    return lines


def read_scroll(game, item, target=None) -> list[str]:
    """Read a scroll aloud outside a fight: the surest reader in the party, when its spell has a use here."""
    t = game.tables
    sid = scroll_spell(t, item)
    if sid not in t.spells:
        return ["That is not a spell scroll."]
    readers = scroll_readers(game, item)
    if not readers:
        return ["The writing means nothing to any of you: the spell is on none of your lists."]
    able = [c for c, _ in readers if not spellrules.scroll_problem(c, t, sid)]
    reader = able[0] if able else readers[0][0]
    return cast_on_road(game, reader, sid, target or scroll_target(game, sid, reader), scroll=item)


def scroll_target(game, spell_id: str, reader):
    """Who a scroll read outside a fight is for: the most hurt of the party for a healing spell (the worst wound,
    then the fewest hit points), the sick or infected for a cure, else the reader."""
    t = game.tables
    use = spellrules.road_use(t, spell_id)
    spell = t.spells[spell_id]
    if use not in ("heal", "cure") or spell["target"] == "self":
        return reader
    hurt = [c for c in game.party if c.alive and _needs(game, spell, c)]
    if not hurt:
        return reader
    return max(hurt, key=lambda c: (max((w.severity for w in c.wounds), default=0), c.max_hp - c.hp))


def _owner(game, item):
    return next((c for c in game.party if c.item(item.uid) is not None), None)


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


def road_problem(game, caster, spell_id: str, target=None, scroll=None) -> str | None:
    """Why this spell can't be cast here and now (None when it can); `scroll`: read from that scroll instead."""
    t = game.tables
    spell = t.spells[spell_id]
    ok, why = spellrules.on_the_road(t, spell_id)
    if not ok:
        return why
    if game.battle is not None:
        return "you are in a fight"
    if scroll is not None:
        why = spellrules.scroll_problem(caster, t, spell_id)
        ok = not why
    elif spell_id not in spellrules.known_spells(caster, t):
        from realmwalker.rules import feats

        if not spell.get("ritual") or spell_id not in spellrules.ritual_spells(caster, t) + feats.ritual_spells(caster, t):
            return "not prepared (p prepares it)"
    if scroll is not None:
        pass  # (no slot and no materials: the scroll's own magic)
    elif spell.get("ritual"):  # a ritual needs no slot, but armour without training still stops it, and it needs
        why = spellrules.armour_problem(caster, t) or spellrules.component_problem(caster, t, spell_id)  # its materials
        ok = not why
    else:
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


def strain_on_road(game, caster, amount: int) -> list[str]:
    """An earlier Wish's stress tears at a caster outside a fight: necrotic damage nothing reduces; at 0 hit points
    they go down and lie senseless a while (down, not dead, as after a trap)."""
    if amount <= 0:
        return []
    first = escape_markup(caster.name.split()[0])
    caster.hp -= amount
    out = [f"<danger>Casting tears at {first}: {amount} necrotic, the strain of the wish.</>"]
    if caster.hp <= 0:
        from realmwalker.game.fight import lie_senseless

        caster.hp = 1
        out.append(f"<danger>{first} goes down and lies still.</> " + lie_senseless(game, 1))
    return out


def cast_on_road(game, caster, spell_id: str, target=None, slot_level: int | None = None, scroll=None) -> list[str]:
    """Cast a spell outside battle. Healing goes through game/care.py (the worst wound first); a lasting spell is
    kept on whoever it was cast on. `slot_level`: a higher slot, for a spell that does more with one; `scroll`: read
    from that scroll (no slot, no materials; a check first when it is above the reader). Returns what to say."""
    from realmwalker.game import care

    t = game.tables
    spell = t.spells[spell_id]
    target = target or caster
    why = road_problem(game, caster, spell_id, target, scroll=scroll)
    if why:
        return [f"{spell['name']}: {why}."]
    pre = []
    if scroll is not None:
        owner = _owner(game, scroll) or caster
        how = spellrules.scroll_reader(caster, t, spell_id)
        check = spellrules.scroll_check(game.sheet(caster), t, spell_id, how)
        remove_item(owner, scroll.uid, 1)  # (spent either way: cast, or faded on a failed check)
        game.dirty = True
        first = escape_markup(caster.name.split()[0])
        if check is not None:
            bonus, dc, words = check
            roll = dice.d20(game.world.rng.child(f"scroll/{spell_id}/{game.world.time}")).natural
            said = f"<dim>({words} {roll} {bonus:+d} = {roll + bonus} vs DC {dc})</>"
            if roll + bonus < dc:
                game.pass_time(1, "rest")
                return [f"<warn>{first} stumbles over the words of the scroll</>: they fade from the "
                        f"page, and it crumbles to dust. {said}"]
            pre.append(f"{first} masters the words of a scroll beyond them and reads "
                       f"<magic>{spell['name']}</> aloud; it crumbles as the last word is spoken. {said}")
        else:
            pre.append(f"{first} reads <magic>{spell['name']}</> aloud from a scroll; it crumbles as "
                       f"the last word is spoken.")
    use = spellrules.road_use(t, spell_id)
    if use in ("heal", "cure"):
        wound = max(target.wounds, key=lambda w: (w.severity, w.bleed), default=None)
        return pre + care.cast(game, caster, target, wound, spell_id, slot_level, free=scroll is not None)
    level = spell["level"] if scroll is None else 0  # (a scroll's own magic: no slot)
    ritual = bool(spell.get("ritual")) and scroll is None  # a Ritual (2024): ten minutes longer, and no slot spent
    free = spellrules.free_cast(caster, t, spell_id) if level and not ritual else None  # (Spell Mastery...)
    slot = spellrules.lowest_free_slot(caster, t, level) if level and not ritual and not free else None
    if slot and slot_level in spellrules.slot_choices(caster, t, spell_id) and spellrules.upcasts(spell):
        slot = slot_level
    if level and not ritual and not free and slot is None:
        return ["No spell slot left for that. A long rest restores them."]
    if free:
        spellrules.spend_free(caster, spell_id, free)
    if slot:
        spellrules.spend_slot(caster, slot)
        strained = spellrules.strain(caster, slot, game.world.rng.child(f"strain/{game.world.time}"))
        pre += strain_on_road(game, caster, strained)
    used = spellrules.spend_material(caster, t, spell_id) if scroll is None else None
    if ritual:
        game.pass_time(10, "rest")
    if use == "identify":
        from realmwalker.game import magic_items

        item = strange_things(game, caster)[0]
        name = game.tables.items.name(item, False)
        game.pass_time(1, "rest")  # (its casting time: a minute; a ritual's ten more are passed above)
        msgs = pre + [f"{escape_markup(caster.name.split()[0])} casts <magic>{spell['name']}</> over the {name}"
                      + (" as a ritual: ten minutes more, and no spell slot." if ritual else ".")]
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
    first = escape_markup(caster.name.split()[0])
    on = "" if who == [caster] else (" on the party" if len(who) > 1 else f" on {who[0].name.split()[0]}")
    msgs = pre + [f"{first} casts <magic>{spell['name']}</>{on}. <dim>It will last {lasting_text(hours)}.</>"]
    if used:
        msgs.append(f"<dim>The {used} is used up.</>")
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
