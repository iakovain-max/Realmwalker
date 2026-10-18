"""The wizard's hats of the DMG 2024 (Expansion 5 Part E): the Hat of Wizardry and the Hat of Many Spells.

Both are a spellcasting focus for wizard spells (rules/magic.item_focus) and have an Unknown Spell: a wizard spell
the wearer does not know, cast through the hat after an Intelligence (Arcana) check.
- The Hat of Wizardry (`spells` "cantrip"): a wizard cantrip cast with an action, DC 10; success or not, the hat
  rests until a long rest.
- The Hat of Many Spells (`spells` "any"): a level 1+ wizard spell of a level the wearer can cast (no material dearer
  than 1,000 GP), for a slot of its level, DC 10 + its level; cast, the hat rests until a short or long rest; failed,
  the slot is spent and something else comes out of the hat (`mishap`, the book's d100 table).

In a fight a hat's spell is "hat:<item uid>:<spell id>" (`Battle.hat_options`, `Battle._cast_from_hat`); outside one
the Spells page lists it the same way (`game/magic.cast_from_hat`). The hat's state is its property's `spent`
("short" or "long": until which rest it waits), cleared by `rest` from progression.short_rest / long_rest."""

from __future__ import annotations

from realmwalker.rules import magic
from realmwalker.rules import spells as spellrules

PREFIX = "hat:"
MOST_GP = 1000  # a material component dearer than this cannot be pulled out of the Hat of Many Spells
MISHAP_SPELLS = ["enlarge_reduce", "enlarge_reduce", "faerie_fire", "fireball", "gust_of_wind", "invisibility",
                 "lightning_bolt", "phantasmal_force", "polymorph", "stinking_cloud"]  # the d10 of 01-50


def prop(item) -> dict | None:
    return next((p for p in magic.props(item) if p.get("kind") == "hat"), None) if item is not None else None


def worn(char) -> list[tuple[object, dict]]:
    """(hat, its property) for each working hat the character wears."""
    if char is None or not char.equipped:
        return []
    on = set(char.equipped.values())
    return [(it, prop(it)) for it in char.inventory if it.uid in on and prop(it) is not None and magic.working(char, it)]


def ready(item) -> bool:
    p = prop(item)
    return p is not None and not p.get("spent")


def many(item) -> bool:
    """The Hat of Many Spells (any level), not the Hat of Wizardry (cantrips)."""
    p = prop(item)
    return p is not None and p.get("spells") == "any"


def dc(tables, sid: str, item) -> int:
    return 10 + (int(tables.spells[sid]["level"]) if many(item) else 0)


def _known(char, tables) -> set[str]:
    return set(spellrules.known_spells(char, tables)) | set(spellrules.preparable(char, tables)) \
        | set((char.spells or {}).get("spellbook", ()))


def _material_gp(tables, spell: dict) -> float:
    """The worth of a spell's costly component in gold (the cheapest thing that serves), 0 if none."""
    m = spell.get("material") or {}
    values = [int(tables.items.get(i)["value"]) for i in m.get("items", ()) if i in tables.items]
    return (min(values) if values else 0) / 100


def spells(char, tables, item, *, battle: bool | None = None, level: int | None = None) -> list[str]:
    """The wizard spells this hat could bring out for this wearer: unknown to them, of the hat's levels (`level`:
    only that one), fit for a fight (`battle` True) or for the road (False), or either (None)."""
    if char is None or prop(item) is None:
        return []
    known = _known(char, tables)
    total = spellrules.slots_total(char, tables)
    top = max((i + 1 for i, n in enumerate(total) if n), default=0)
    out = []
    for sid, sp in tables.spells.defs.items():
        if "wizard" not in sp.get("classes", ()) or sid in known or sp.get("again_of") or sp.get("stress"):
            continue
        lvl = int(sp.get("level", 0))
        if many(item):
            if not 1 <= lvl <= top or _material_gp(tables, sp) > MOST_GP:
                continue
        elif lvl != 0 or sp.get("cast", "action") != "action":
            continue
        if level is not None and lvl != level:
            continue
        in_fight = not spellrules.out_of_battle(sp) and not spellrules.has_op(sp, "identify", "revive") \
            and sp.get("cast") != "reaction"
        if battle is True and not in_fight:
            continue
        if battle is False and not spellrules.on_the_road(tables, sid)[0]:
            continue
        out.append(sid)
    return sorted(out, key=lambda s: (tables.spells[s]["level"], tables.spells[s]["name"]))


def problem(char, tables, item, sid: str, *, listed: bool = False) -> str | None:
    """Why this spell cannot be pulled from the hat now (None: it can be tried). `listed`: the spell came from
    `spells` a moment ago (not worked out again: the lists are long)."""
    p = prop(item)
    if p is None or not magic.working(char, item):
        return "the hat answers only a wizard attuned to it"
    if item.uid not in set(char.equipped.values()):
        return "the hat must be worn"
    if p.get("spent"):
        return "the hat rests until a " + ("short or long rest" if p["spent"] == "short" else "long rest")
    if sid not in tables.spells or (not listed and sid not in spells(char, tables, item)):
        return "not a spell the hat can bring out for you"
    lvl = int(tables.spells[sid]["level"])
    if lvl > 0 and not spellrules.slots_left(char, tables)[lvl - 1]:
        return f"no level {lvl} spell slot left"
    lacking = spellrules.component_problem(char, tables, sid)
    if lacking:
        return lacking  # (a costly component must still be at hand)
    return None


def odds(sheet, tables, sid: str, item) -> float:
    """The chance of the Arcana check (for the Auto's weighing)."""
    bonus = sheet.skill_bonus("arcana") if hasattr(sheet, "skill_bonus") else sheet.mod("int")
    need = dc(tables, sid, item) - bonus
    return max(0.05, min(0.95, (21 - need) / 20))


def spend(item, success: bool) -> None:
    """After a try: Many Spells rests until a short rest once a spell is cast; Wizardry until a long rest either way."""
    p = prop(item)
    if p is None:
        return
    if many(item):
        if success:
            p["spent"] = "short"
    else:
        p["spent"] = "long"


def rest(char, long: bool) -> None:
    """A rest: the hats wake (a short rest wakes the Hat of Many Spells)."""
    for it in char.inventory:
        p = prop(it)
        if p is not None and p.get("spent") and (long or p["spent"] == "short"):
            p.pop("spent", None)


def mishap_roll(rng) -> int:
    return rng.randint(1, 100)


def mishap(b, f, rng) -> None:
    """The Hat of Many Spells' failure (DMG 2024's table, d100), in a fight. The random spell is cast with the
    wearer's own numbers at a target of its choosing; the creatures that come out leave the field at once (they are
    nobody's), the bats bite and scatter, and a magic item is a potion of healing of its rarity."""
    from realmwalker.rules.inventory import add_item

    roll = mishap_roll(rng)
    who = f.the_name
    c = f.char
    if roll <= 50:
        sid = MISHAP_SPELLS[rng.randint(1, 10) - 1]
        if sid not in b.t.spells:
            b.say("Something sputters out of the hat and fizzles.", "magic")
            return
        sp = b.t.spells[sid]
        target, point = _random_aim(b, f, sid, rng)
        b.say(f"<magic>Out of the hat comes the wrong spell: {sp['name']}!</>", "magic")
        s = f.sheet
        b.cast(f, sid, sp, target, point, up=0, mod=s.mod(spellrules.casting_ability(c, b.t)),
               dc=spellrules.save_dc(s, b.t), bonus=spellrules.attack_bonus(s, b.t), mult=1, level=int(sp["level"]),
               slotted=False)
    elif roll <= 55:
        from realmwalker.rules.engine import durations

        durations.give(b, f, "stunned", ends=durations.until(b, f, "turn_end"))
        b.say(f"{who} stands dazed, Stunned, sure something wonderful just happened.", "warn")
    elif roll <= 60:
        b.say("A harmless cloud of butterflies bursts from the hat and flutters away over the field.", "magic")
    elif roll <= 65:
        thing = ["acid", "alchemists_fire", "crowbar", "torch"][rng.randint(1, 4) - 1]
        add_item(c, b.t.items, thing, 1)
        b.say(f"{who} pulls {b.t.items.get(thing)['name']} out of the hat.", "magic")
    elif roll <= 70:
        from realmwalker.rules.engine import durations

        durations.give(b, f, "poisoned", rounds=600)
        b.say(f"Magic sickness: {who} is Poisoned for an hour.", "warn")
    elif roll <= 75:
        from realmwalker.rules.engine import durations

        durations.give(b, f, "petrified", ends=durations.until(b, f, "turn_end"))
        b.say(f"{who} turns to stone, until the end of their next turn.", "danger")
    elif roll <= 80:
        thing = ["dagger", "grappling_hook", "caltrops", "gem_50"][rng.randint(1, 4) - 1]
        add_item(c, b.t.items, thing, 1)
        b.say(f"{who} pulls {b.t.items.get(thing)['name']} out of the hat.", "magic")
    elif roll <= 85:
        beast = ["a camel", "a constrictor snake", "an elephant", "a mule"][rng.randint(1, 4) - 1]
        b.say(f"{beast[:1].upper() + beast[1:]} tumbles out of the hat, looks about in alarm, and makes off from the "
              "field.", "magic")
    elif roll <= 90:
        from realmwalker.core import dice

        n = dice.roll("2d4", rng).total
        b.say(f"A swarm of bats bursts from the hat and tears at {who} before it scatters.", "danger")
        b._hit(None, f, n, "piercing", crit=False, weapon="a swarm of bats")
    elif roll <= 95:
        b.say("A shimmering doorway to somewhere else opens beside the hat, and closes again.", "magic")
    else:
        rarity = rng.randint(1, 6)
        potion = "potion_healing" if rarity <= 3 else "potion_healing_greater" if rarity <= 5 else \
            "potion_healing_superior"
        add_item(c, b.t.items, potion, 1)
        b.say(f"{who} pulls a {b.t.items.get(potion)['name']} out of the hat.", "magic")


def _random_aim(b, f, sid: str, rng):
    """Where the hat's wrong spell goes: somewhere it can go, chosen by chance."""
    sp = b.t.spells[sid]
    mode = sp["target"]
    if mode in ("enemy", "ally", "creature"):
        who = b.spell_targets(f, sid)
        return (rng.choice(who) if who else f), None
    if mode in ("point", "direction"):
        points = sorted(b.spell_points(f, sid))
        return None, (rng.choice(points) if points else (f.x, f.y))
    return None, None


def road_mishap(game, char, rng) -> list[str]:
    """The Hat of Many Spells' failure outside a fight: the same table, in a quieter world."""
    from realmwalker.core.textgen import escape_markup as esc
    from realmwalker.rules.inventory import add_item

    t = game.tables
    who = esc(char.name.split()[0])
    roll = mishap_roll(rng)
    if roll <= 50:
        sid = MISHAP_SPELLS[rng.randint(1, 10) - 1]
        name = t.spells[sid]["name"] if sid in t.spells else "a spell"
        return [f"<magic>Out of the hat comes the wrong spell: {name}</>, and it spends itself on the empty air."]
    if roll <= 55:
        return [f"{who} stands dazed a moment, sure something wonderful just happened."]
    if roll <= 60:
        return ["A harmless cloud of butterflies bursts from the hat and flutters away."]
    if roll in range(61, 66) or roll in range(76, 81):
        pool = ["acid", "alchemists_fire", "crowbar", "torch"] if roll <= 65 else \
            ["dagger", "grappling_hook", "caltrops", "gem_50"]
        thing = pool[rng.randint(1, 4) - 1]
        add_item(char, t.items, thing, 1, made_at=game.world.time)
        return [f"{who} pulls {t.items.get(thing)['name']} out of the hat."]
    if roll <= 70:
        return [f"<warn>Magic sickness: {who} feels green for an hour.</>"]
    if roll <= 75:
        return [f"<warn>{who} turns to stone for a moment, and back.</>"]
    if roll <= 85:
        beast = ["a camel", "a constrictor snake", "an elephant", "a mule"][rng.randint(1, 4) - 1]
        return [f"{beast[:1].upper() + beast[1:]} tumbles out of the hat, looks about in alarm, and is gone within the "
                "hour."]
    if roll <= 90:
        n = min(char.hp - 1, max(0, rng.randint(1, 4) + rng.randint(1, 4)))
        char.hp -= max(0, n)
        return [f"<danger>A swarm of bats bursts from the hat and bites {who} ({n} piercing) before it scatters.</>"]
    if roll <= 95:
        return ["A shimmering doorway to somewhere else opens beside the hat, and closes again."]
    rarity = rng.randint(1, 6)
    potion = "potion_healing" if rarity <= 3 else "potion_healing_greater" if rarity <= 5 else "potion_healing_superior"
    add_item(char, t.items, potion, 1, made_at=game.world.time)
    return [f"{who} pulls a {t.items.get(potion)['name']} out of the hat."]
