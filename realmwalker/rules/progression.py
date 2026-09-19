"""Experience, levelling and resting.

A level-up adds hit points and class features at once. The choices (a subclass, ability increases, new spells
and cantrips) wait in `char.pending` until the player makes them on the level-up screen, or asks for sensible
choices to be made (`auto_resolve`). Rest recovers hit points, hit dice, spell slots and once-per-rest features.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules.character import Character, modifier
from realmwalker.rules.spells import restore_slots

SHORT_REST_FEATURES = ("second_wind", "action_surge", "channel_divinity")


def award_xp(char: Character, xp: int, tables, rng: RNG, *, auto: bool = False) -> list[str]:
    """Give experience; returns messages (including any level-ups)."""
    if xp <= 0 or not char.alive:
        return []
    char.xp += xp
    messages = []
    table = tables.rules["xp_for_level"]
    while char.level < min(tables.rules["max_level"], len(table)) and char.xp >= table[char.level]:
        messages += level_up(char, tables, rng, auto=auto)
    return messages


def level_up(char: Character, tables, rng: RNG, *, auto: bool = False) -> list[str]:
    """Up a level: hit points and features now; choices wait in char.pending (made now if auto)."""
    notes = _level_up(char, tables, rng)
    if char.companion and rng.chance(0.5) and tables.companions:
        from realmwalker.core import textgen

        text = rng.choice(tables.companions["lines"]["level_up"])
        notes.append(textgen.fill(text, rng, {}, {"name": char.name.split()[0], "leader": "you"}))
    if char.pending:
        notes.append(f"<info>{char.name.split()[0]} has choices to make</> (the character sheet, c, then l).")
    if auto:
        notes += auto_resolve(char, tables)
    return notes


def _level_up(char: Character, tables, rng: RNG) -> list[str]:
    cls = tables.classes[char.cls]
    char.level += 1
    con = modifier(char.abilities["con"])
    gain = max(1, cls["hit_die"] // 2 + 1 + con + int(tables.races[char.race].get("hp_per_level", 0)))
    char.max_hp += gain
    char.hp += gain
    char.hit_dice += 1
    notes = [f"<good>{char.name.split()[0]} reaches level {char.level}</> (+{gain} hit points)."]
    for feat in cls["features"]:
        if feat["level"] != char.level:
            continue
        if feat["id"] == "subclass" and not char.subclass:
            add_pending(char, {"kind": "subclass", "level": char.level})
        elif feat["id"] == "asi":
            add_pending(char, {"kind": "asi", "level": char.level})
        elif feat["id"] not in char.features:
            char.features.append(feat["id"])
            notes.append(f"New: {feat['name']}.")
        if feat["id"] in ("action_surge", "channel_divinity"):
            char.uses[feat["id"]] = 1
    if char.subclass:
        for feat in cls["subclasses"][char.subclass]["features"]:
            if feat["level"] == char.level and feat["id"] not in char.features:
                char.features.append(feat["id"])
                notes.append(f"New: {feat['name']}.")
    if char.cls == "wizard" and char.spells:
        add_pending(char, {"kind": "spells", "count": 2, "level": char.level})
    cantrips = cls.get("spellcasting", {}).get("cantrips")
    if cantrips and char.spells:
        missing = cantrips[char.level - 1] - len(char.spells.get("cantrips", []))
        if missing > 0:
            add_pending(char, {"kind": "cantrips", "count": missing, "level": char.level})
    return notes


# ---------------------------------------------------------------------------- level-up choices
def add_pending(char: Character, choice: dict) -> None:
    choice = dict(choice, new=True)
    char.pending.append(choice)


def spell_top_level(char: Character, tables) -> int:
    sc = tables.classes[char.cls].get("spellcasting")
    if not sc:
        return 0
    return len(sc["slots"][min(char.level, len(sc["slots"])) - 1])


def options(char: Character, tables, choice: dict) -> list[tuple[str, str, str]]:
    """(id, label, details) for one pending choice."""
    cls = tables.classes[char.cls]
    kind = choice["kind"]
    names = {a: tables.rules["abilities"][a]["name"] for a in tables.rules["abilities"]}
    if kind == "subclass":
        return [(sid, s["name"], s.get("text", "") + " " + "; ".join(
            f"level {f['level']}: {f['name']}" for f in s.get("features", [])))
            for sid, s in cls["subclasses"].items()]
    if kind == "asi":
        out = []
        for a in tables.rules["abilities"]:
            if char.abilities[a] <= 18:
                out.append((f"{a}+2", f"+2 {names[a]}", f"{names[a]} {char.abilities[a]} → {char.abilities[a] + 2}"))
        abil = list(tables.rules["abilities"])
        for i, a in enumerate(abil):
            for b in abil[i + 1:]:
                if char.abilities[a] <= 19 and char.abilities[b] <= 19:
                    out.append((f"{a}+1,{b}+1", f"+1 {names[a]}, +1 {names[b]}",
                                f"{names[a]} {char.abilities[a]} → {char.abilities[a] + 1}, "
                                f"{names[b]} {char.abilities[b]} → {char.abilities[b] + 1}"))
        primary = cls["primary"]
        out.sort(key=lambda o: (not any(p in o[0] for p in primary), 0 if "+2" in o[0] else 1))
        return out
    if kind == "spells":
        top = spell_top_level(char, tables)
        book = char.spells.get("spellbook", [])
        spells = [s for s in tables.spells.for_class(char.cls, top) if tables.spells[s]["level"] > 0 and s not in book]
        spells.sort(key=lambda s: (-tables.spells[s]["level"], tables.spells[s]["name"]))
        return [(s, f"{tables.spells[s]['name']} (level {tables.spells[s]['level']})",
                 tables.spells[s].get("text", tables.spells[s].get("description", ""))) for s in spells]
    if kind == "cantrips":
        known = char.spells.get("cantrips", [])
        return [(s, tables.spells[s]["name"], tables.spells[s].get("text", tables.spells[s].get("description", "")))
                for s in tables.spells.for_class(char.cls, 0) if tables.spells[s]["level"] == 0 and s not in known]
    return []


def choice_title(char: Character, tables, choice: dict) -> str:
    kind = choice["kind"]
    if kind == "subclass":
        return f"Choose a path for {char.name.split()[0]}"
    if kind == "asi":
        return "Improve your abilities: +2 to one, or +1 to two"
    if kind == "spells":
        n = choice.get("count", 1)
        return f"Copy {n} new spell{'s' if n > 1 else ''} into your spellbook"
    if kind == "cantrips":
        n = choice.get("count", 1)
        return f"Learn {n} new cantrip{'s' if n > 1 else ''}"
    return "Choose"


def resolve(char: Character, tables, choice: dict, option_id: str) -> list[str]:
    """Make one pending choice. Returns what changed."""
    cls = tables.classes[char.cls]
    kind = choice["kind"]
    notes = []
    if kind == "subclass":
        char.subclass = option_id
        sub = cls["subclasses"][option_id]
        notes.append(f"{char.name.split()[0]} follows the {sub['name']}.")
        for feat in sub.get("features", []):
            if feat["level"] <= char.level and feat["id"] not in char.features:
                char.features.append(feat["id"])
                notes.append(f"New: {feat['name']}.")
        char.pending.remove(choice)
    elif kind == "asi":
        for part in option_id.split(","):
            ability, amount = part.split("+")
            before = modifier(char.abilities[ability])
            char.abilities[ability] = min(20, char.abilities[ability] + int(amount))
            notes.append(f"{tables.rules['abilities'][ability]['name']} rises to {char.abilities[ability]}.")
            if ability == "con":
                gain = (modifier(char.abilities[ability]) - before) * char.level  # hardier at every level
                char.max_hp += gain
                char.hp += gain
        char.pending.remove(choice)
    elif kind in ("spells", "cantrips"):
        key = "spellbook" if kind == "spells" else "cantrips"
        char.spells.setdefault(key, []).append(option_id)
        notes.append(f"{'Copied' if kind == 'spells' else 'Learned'} {tables.spells[option_id]['name']}.")
        choice["count"] = choice.get("count", 1) - 1
        if choice["count"] <= 0 or not options(char, tables, choice):
            char.pending.remove(choice)
    return notes


def auto_resolve(char: Character, tables) -> list[str]:
    """Sensible choices for everything waiting: the first path, the main ability, the strongest spells."""
    notes = []
    cls = tables.classes[char.cls]
    for _ in range(40):
        if not char.pending:
            break
        choice = char.pending[0]
        opts = options(char, tables, choice)
        if not opts:
            char.pending.remove(choice)
            continue
        if choice["kind"] == "asi":
            best = max(cls["primary"], key=lambda a: (char.abilities[a] <= 18, -cls["primary"].index(a)))
            pick = f"{best}+2" if char.abilities[best] <= 18 else opts[0][0]
            if pick not in {o[0] for o in opts}:
                pick = opts[0][0]
        else:
            pick = opts[0][0]
        notes += resolve(char, tables, choice, pick)
    return notes


def has_new_choices(char: Character) -> bool:
    return any(c.get("new") for c in char.pending)


def seen_choices(char: Character) -> None:
    for c in char.pending:
        c["new"] = False


def short_rest(char: Character, tables, rng: RNG) -> list[str]:
    """An hour's rest: spend hit dice to heal, recover short-rest features."""
    notes = []
    die = tables.classes[char.cls]["hit_die"]
    con = modifier(char.abilities["con"])
    healed = 0
    while char.hp < char.max_hp and char.hit_dice > 0:
        char.hit_dice -= 1
        amount = max(1, dice.roll(f"1d{die}", rng).total + con)
        char.hp = min(char.max_hp, char.hp + amount)
        healed += amount
    if healed:
        notes.append(f"{char.name.split()[0]} recovers {healed} hit points.")
    for f in SHORT_REST_FEATURES:
        if f in char.features or (f == "channel_divinity" and f in char.uses):
            char.uses[f] = 1
    if char.subclass == "war":
        char.uses["war_priest"] = max(1, modifier(char.abilities["wis"]))
    if "arcane_recovery" in char.features and char.uses.get("arcane_recovery", 1) and char.spells:
        used = char.spells.setdefault("slots_used", [0] * 9)
        budget = max(1, (char.level + 1) // 2)
        for i in range(min(5, len(used))):
            while used[i] and budget >= i + 1:
                used[i] -= 1
                budget -= i + 1
        char.uses["arcane_recovery"] = 0
        notes.append("Arcane Recovery restores some spell slots.")
    return notes


def long_rest(char: Character, tables, rng: RNG) -> list[str]:
    """A full night: hit points, spell slots and features restored; half the hit dice back."""
    if not char.alive:
        return []
    char.hp = char.max_hp
    char.hit_dice = min(char.level, char.hit_dice + max(1, char.level // 2))
    restore_slots(char)
    for f in SHORT_REST_FEATURES:
        if f in char.features or (f == "channel_divinity" and f in char.uses):
            char.uses[f] = 1
    if "relentless_endurance" in [t.get("rule") for t in tables.races[char.race]["traits"]]:
        char.uses["relentless_endurance"] = 1
    if char.subclass == "war":
        char.uses["war_priest"] = max(1, modifier(char.abilities["wis"]))
    char.uses["arcane_recovery"] = 1
    from realmwalker.rules import magic

    magic.recharge(char)
    return [f"{char.name.split()[0]} wakes rested."]
