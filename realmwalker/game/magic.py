"""Spell scrolls outside battle (M7): a wizard can copy one into their spellbook. It takes an Arcana check, costly
inks (50 gold crowns a spell level) and two hours a level, and the scroll is used up either way. Reading scrolls
in battle is in rules/combat.py."""

from __future__ import annotations

from realmwalker.core import dice
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
