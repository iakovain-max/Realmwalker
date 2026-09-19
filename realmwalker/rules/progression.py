"""Experience, levelling and resting.

Levelling here is automatic (sensible choices made for you); M7 adds the choices: subclass, ability
increases and spells. Rest recovers hit points, hit dice, spell slots and once-per-rest features;
M4 adds food, safety and interruptions.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules.character import Character, modifier
from realmwalker.rules.spells import restore_slots

SHORT_REST_FEATURES = ("second_wind", "action_surge", "channel_divinity")


def award_xp(char: Character, xp: int, tables, rng: RNG) -> list[str]:
    """Give experience; returns messages (including any level-ups)."""
    if xp <= 0 or not char.alive:
        return []
    char.xp += xp
    messages = []
    table = tables.rules["xp_for_level"]
    while char.level < min(tables.rules["max_level"], len(table)) and char.xp >= table[char.level]:
        messages += level_up(char, tables, rng)
    return messages


def level_up(char: Character, tables, rng: RNG) -> list[str]:
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
            char.subclass = next(iter(cls["subclasses"]))
            notes.append(f"Chosen path: {cls['subclasses'][char.subclass]['name']}.")
        elif feat["id"] == "asi":
            best = max(cls["primary"], key=lambda a: (char.abilities[a] < 20, -cls["primary"].index(a)))
            char.abilities[best] = min(20, char.abilities[best] + 2)
            notes.append(f"{tables.rules['abilities'][best]['name']} rises to {char.abilities[best]}.")
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
        top = len(cls["spellcasting"]["slots"][char.level - 1])
        candidates = [s for s in tables.spells.for_class("wizard", top)
                      if tables.spells[s]["level"] > 0 and s not in char.spells.get("spellbook", [])]
        candidates.sort(key=lambda s: -tables.spells[s]["level"])
        for s in candidates[:2]:
            char.spells.setdefault("spellbook", []).append(s)
            notes.append(f"Copied {tables.spells[s]['name']} into the spellbook.")
    cantrips = cls.get("spellcasting", {}).get("cantrips")
    if cantrips and char.spells:
        want = cantrips[char.level - 1]
        known = char.spells.setdefault("cantrips", [])
        for s in tables.spells.for_class(char.cls, 0):
            if len(known) >= want:
                break
            if tables.spells[s]["level"] == 0 and s not in known:
                known.append(s)
    return notes


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
    return [f"{char.name.split()[0]} wakes rested."]
