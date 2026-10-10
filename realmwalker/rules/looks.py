"""How a person looks: build, skin, eyes, hair, beard, the marks of their people (an elf's ears, a half-orc's tusks),
scars and paint, and the colours they wear. Pure data logic; the pictures are drawn from it by ui/gfx/dolls.py.

A player chooses their looks when they make a character (`Character.looks`). Everyone else's are read from the words
that describe them (`from_text`): "a heavy man with a braided red beard" is drawn heavy, with a red braided beard,
and what the words do not say is picked by a stable hash of who it is, so a person looks the same every time.
`describe` writes the words for a set of looks, so the description and the picture always agree.

What each people may have is in data/appearance.json "looks"/"races"; a people not written there (a race added to
data/races.json and nothing more) uses "_default", so it can be made and drawn at once.
"""

from __future__ import annotations

import re
import zlib

from realmwalker.core.rng import RNG

# The looks a person has, in the order they are offered at character creation. features is {name: option}.
SLOTS = ("build", "skin", "eyes", "hair", "hair_colour", "beard", "beard_colour", "mark", "paint", "paint_colour")
# slot -> the table of options in data/appearance.json looks
TABLE = {"build": "builds", "skin": "skins", "eyes": "eyes", "hair": "hair_styles", "hair_colour": "hair_colours",
         "beard": "beards", "beard_colour": "hair_colours", "mark": "marks", "paint": "paints",
         "paint_colour": "paint_colours"}
# slot -> the race list that says which of them a people may have
RACE_LIST = {"build": "builds", "skin": "skins", "eyes": "eyes", "hair": "hair_styles", "hair_colour": "hair_colours",
             "beard_colour": "hair_colours", "mark": "marks", "paint": "paints", "paint_colour": "paint_colours"}


def data(tables) -> dict:
    return tables.appearance["looks"]


def stable(key: str, n: int) -> int:
    """A number below n that is always the same for the same key (no random stream used)."""
    return zlib.crc32(key.encode("utf-8")) % n if n > 0 else 0


def race_spec(tables, race: str) -> dict:
    """What a people may look like: their own entry over the defaults."""
    races = data(tables)["races"]
    spec = dict(races["_default"])
    spec.update(races.get(race) or {})
    return spec


def _sex(sex: str) -> str:
    return "female" if sex == "female" else "male"


def options(tables, race: str, sex: str) -> dict:
    """slot -> the options a person of this people and sex may have, and "features" -> {feature: [options]}."""
    spec = race_spec(tables, race)
    d = data(tables)
    out: dict = {}
    for slot in SLOTS:
        if slot == "beard":
            pool = spec["beards"].get(_sex(sex)) or ["none"]
        else:
            pool = spec[RACE_LIST[slot]]
        table = d[TABLE[slot]]
        out[slot] = [k for k in pool if k in table]
    out["features"] = {f: [o for o in opts if o in d["features"].get(f, {}).get("options", {})]
                       for f, opts in spec.get("features", {}).items() if f in d["features"]}
    return out


def name_of(tables, slot: str, key: str) -> str:
    """The name of an option, as shown when choosing ("Braids", "Woad blue")."""
    d = data(tables)
    if slot.startswith("feature:"):
        opt = d["features"].get(slot[8:], {}).get("options", {}).get(key)
    elif slot in ("dye", "cloak"):
        return "As made" if not key else key.replace("_", " ").capitalize()
    else:
        opt = d[TABLE[slot]].get(key)
    return opt["name"] if opt else key.replace("_", " ").capitalize()


def feature_name(tables, feature: str) -> str:
    return data(tables)["features"].get(feature, {}).get("name", feature.capitalize())


# ---------------------------------------------------------------------------- making looks
def _pick(pool: list, key: str):
    return pool[stable(key, len(pool))] if pool else None


def normalise(tables, looks: dict | None, race: str, sex: str, key: str = "") -> dict:
    """Looks that this people and sex can have: anything missing or not allowed (after a change of people, or of
    sex) is chosen again, by the stable hash of `key`."""
    opts = options(tables, race, sex)
    spec = race_spec(tables, race)
    looks = dict(looks or {})
    out: dict = {}
    for slot in SLOTS:
        pool = opts[slot]
        value = looks.get(slot)
        if value not in pool:
            if slot == "beard":
                value = "none" if "none" in pool else _pick(pool, key + slot)
            elif slot == "hair":
                value = _pick(spec["likely_hair"].get(_sex(sex)) or pool, key + slot)
                value = value if value in pool else _pick(pool, key + slot)
            elif slot == "beard_colour":
                value = out.get("hair_colour") if out.get("hair_colour") in pool else _pick(pool, key + slot)
            elif slot in ("mark", "paint"):
                value = "none" if "none" in pool else _pick(pool, key + slot)
            elif slot == "build":
                value = "average" if "average" in pool else _pick(pool, key + slot)
            else:
                value = _pick(pool, key + slot)
        out[slot] = value
    feats = dict(looks.get("features") or {})
    out["features"] = {f: (feats.get(f) if feats.get(f) in pool else pool[0]) for f, pool in opts["features"].items()
                       if pool}
    dyes = data(tables)["dyes"]
    out["dye"] = looks.get("dye") if looks.get("dye") in dyes else ""
    out["cloak"] = looks.get("cloak") if looks.get("cloak") in dyes else ""
    return out


def random_looks(tables, race: str, sex: str, age: int, rng: RNG) -> dict:
    """A whole new look for someone of this people, sex and age (character creation, R for random)."""
    opts = options(tables, race, sex)
    spec = race_spec(tables, race)
    sx = _sex(sex)
    looks: dict = {}
    for slot in ("build", "skin", "eyes"):
        looks[slot] = rng.choice(opts[slot])
    aged = [c for c in spec.get("old_colours", []) if c in opts["hair_colour"]]
    young = [c for c in opts["hair_colour"] if c not in aged] or opts["hair_colour"]
    old = _old_age(tables, race)
    if aged and (age >= old and rng.chance(0.7) or age >= old * 0.75 and rng.chance(0.3)):
        looks["hair_colour"] = rng.choice(aged)
    else:
        looks["hair_colour"] = rng.choice(young)
    likely = [h for h in spec["likely_hair"].get(sx, []) if h in opts["hair"]] or opts["hair"]
    looks["hair"] = rng.choice(likely)
    beards = opts["beard"]
    if rng.chance(float(spec["beard_chance"].get(sx, 0.0))):
        pool = [b for b in spec.get("likely_beards", {}).get(sx, []) if b in beards] or [b for b in beards if b != "none"]
        looks["beard"] = rng.choice(pool) if pool else "none"
    else:
        looks["beard"] = "none" if "none" in beards else rng.choice(beards)
    looks["beard_colour"] = looks["hair_colour"]
    marks = [m for m in opts["mark"] if m != "none"]
    looks["mark"] = rng.choice(marks) if marks and rng.chance(float(spec["mark_chance"])) else "none"
    paints = [p for p in opts["paint"] if p != "none"]
    looks["paint"] = rng.choice(paints) if paints and rng.chance(float(spec["paint_chance"])) else "none"
    looks["paint_colour"] = rng.choice(opts["paint_colour"])
    looks["features"] = {f: rng.choice(pool) for f, pool in opts["features"].items() if pool}
    return normalise(tables, looks, race, sex)


# ---------------------------------------------------------------------------- reading looks from words
_CONTEXT = {
    "hair": ("hair", "head", "locks", "braid", "plait", "topknot", "top-knot", "crest", "curls", "bald", "shaven", "shaved",
             "scalp", "mohawk", "tails", "bun", "ponytail", "queue", "shorn"),
    "beard": ("beard", "moustache", "mustache", "whisker", "stubble", "unshaven", "goatee", "chops", "sideburns",
              "clean-shaven", "beardless", "bristle"),
    "eyes": ("eye",),
    "skin": ("skin", "complexion", "face", "tanned", "weather", "cheek", "sunburn", "freckle", "ruddy", "pale", "pallid"),
}


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in re.split(r"[,;.:!?]| and | with | but ", (text or "").lower()) if c.strip()]


def _found(word: str, text: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(word), text) is not None


def _match(table: dict, pool: list, text: str):
    """The first option of the pool whose words appear in the text (longest words first, so "dark green" beats
    "green")."""
    best = None
    for key in pool:
        for word in table.get(key, {}).get("words", []):
            if word and _found(word, text) and (best is None or len(word) > best[0]):
                best = (len(word), key)
    return best[1] if best else None


def from_text(tables, text: str, race: str, sex: str, age: int = 30, key: str = "") -> dict:
    """Looks read from a description ("heavy, with braided red hair and a scar down one cheek"); whatever the words
    do not say is chosen by the stable hash of `key` (an npc's id), so a person looks the same every time."""
    d = data(tables)
    opts = options(tables, race, sex)
    spec = race_spec(tables, race)
    sx = _sex(sex)
    parts = _clauses(text)
    whole = " ".join(parts)

    def context(name: str) -> str:
        return " ".join(c for c in parts if any(w in c for w in _CONTEXT[name]))

    hair_text, beard_text, eye_text, skin_text = context("hair"), context("beard"), context("eyes"), context("skin")
    hair_only = " ".join(c for c in parts if any(w in c for w in _CONTEXT["hair"]) and not any(
        w in c for w in _CONTEXT["beard"] + ("eye",)))
    looks: dict = {}
    # The build from words about the body, not "heavy tusks" or "a thick beard".
    body_text = " ".join(c for c in parts if not any(w in c for w in (
        "tusk", "horn", "ear", "beard", "hair", "eye", "brow", "scar", "paint", "tattoo", "nose", "tail", "lip")))
    looks["build"] = _match(d["builds"], opts["build"], body_text) or ("average" if "average" in opts["build"] else
                                                                      _pick(opts["build"], key + "build"))
    looks["skin"] = _match(d["skins"], opts["skin"], skin_text) or _pick(opts["skin"], key + "skin")
    looks["eyes"] = _match(d["eyes"], opts["eyes"], eye_text) or _pick(opts["eyes"], key + "eyes")
    colour = _match(d["hair_colours"], opts["hair_colour"], hair_only or hair_text)
    if colour is None:
        aged = [c for c in spec.get("old_colours", []) if c in opts["hair_colour"]]
        if age >= _old_age(tables, race) and aged:
            colour = _pick(aged, key + "hc")
        else:
            colour = _pick([c for c in opts["hair_colour"] if c not in aged] or opts["hair_colour"], key + "hc")
    looks["hair_colour"] = colour
    style = _match(d["hair_styles"], opts["hair"], hair_only or hair_text)
    if style is None:
        likely = [h for h in spec["likely_hair"].get(sx, []) if h in opts["hair"]] or opts["hair"]
        style = _pick(likely, key + "hs")
    looks["hair"] = style
    beards = opts["beard"]
    beard = _match(d["beards"], beards, beard_text) if beard_text else None
    if beard is None and _found("beard", beard_text) and not _found("beardless", beard_text):
        beard = "short" if "short" in beards else None  # "a beard", said of no particular kind
    if beard is None:
        if stable(key + "beard", 100) < float(spec["beard_chance"].get(sx, 0.0)) * 100:
            pool = [b for b in spec.get("likely_beards", {}).get(sx, []) if b in beards] or [b for b in beards if b != "none"]
            beard = _pick(pool, key + "bs") if pool else "none"
        else:
            beard = "none" if "none" in beards else _pick(beards, key + "bs")
    looks["beard"] = beard
    looks["beard_colour"] = _match(d["hair_colours"], opts["beard_colour"], beard_text) or colour
    looks["mark"] = _mark(whole, opts["mark"]) or "none"
    looks["paint"] = _match(d["paints"], [p for p in opts["paint"] if p != "none"], whole) or "none"
    paint_text = " ".join(c for c in parts if any(w in c for w in ("paint", "woad", "tattoo", "ink", "ochre", "chalk",
                                                                     "mark", "stripe", "sigil")))
    looks["paint_colour"] = (_match(d["paint_colours"], opts["paint_colour"], paint_text)
                             or _pick(opts["paint_colour"], key + "pc"))
    feats = {}
    for f, pool in opts["features"].items():
        if pool:
            feats[f] = _match(d["features"][f]["options"], pool, whole) or pool[0]
    looks["features"] = feats
    return normalise(tables, looks, race, sex, key)


def of_npc(tables, npc) -> dict:
    """How a townsperson looks, read from the words that describe them (the same every time; a companion hired from
    the town keeps the face they had there)."""
    return from_text(tables, (npc.profile or {}).get("appearance", ""), npc.race, npc.sex, npc.age, f"npc{npc.id}")


def _old_age(tables, race: str) -> int:
    races = getattr(tables, "races", {}) or {}
    return int(races[race]["age"]["old"]) if race in races else 60


def _mark(text: str, pool: list) -> str | None:
    """Scars are told many ways: which one is it?"""
    if "scar" in text:
        if "eye" in text and "brow" not in text and "scar_eye" in pool:
            return "scar_eye"
        if "brow" in text and "scar_brow" in pool:
            return "scar_brow"
        if "scar_cheek" in pool:
            return "scar_cheek"
    for mark in ("eyepatch", "broken_nose", "earring", "burn", "freckles"):
        if mark in pool and any(_found(w, text) for w in _MARK_WORDS.get(mark, ())):
            return mark
    return None


_MARK_WORDS = {"eyepatch": ("patch over", "eyepatch", "eye-patch", "lost eye", "one-eyed"),
               "broken_nose": ("broken nose", "badly healed nose", "crooked nose", "flattened nose"),
               "earring": ("earring", "ear-ring", "ring in one ear"), "burn": ("burn", "scald"),
               "freckles": ("freckle",)}


# ---------------------------------------------------------------------------- writing the words
def describe(tables, looks: dict, race: str, sex: str) -> str:
    """One sentence that says how someone looks: "Heavy and ruddy-faced, with a braided red beard, short red hair
    and grey eyes; a scar down one cheek." Written from the same looks the picture is drawn from."""
    d = data(tables)
    key = "|".join(str(looks.get(s, "")) for s in SLOTS)
    build_say = d["builds"].get(looks.get("build", ""), {}).get("say") or ["Of middling build"]
    build_word = build_say[stable(key + "b", len(build_say))] if isinstance(build_say, list) else str(build_say)
    skin = d["skins"].get(looks.get("skin", ""), {}).get("say", "")
    head = f"{build_word} and {skin}" if skin and stable(key + "s", 3) == 0 else build_word
    colour = d["hair_colours"].get(looks.get("hair_colour", ""), {}).get("say", "")
    hair = d["hair_styles"].get(looks.get("hair", ""), {}).get("say", "").replace("{c}", colour)
    beard_colour = d["hair_colours"].get(looks.get("beard_colour", ""), {}).get("say", colour)
    beard = d["beards"].get(looks.get("beard", "none"), {}).get("say", "").replace("{c}", beard_colour)
    eyes = d["eyes"].get(looks.get("eyes", ""), {}).get("say", "")
    things = [t for t in (beard, hair) if t] if beard and stable(key + "o", 2) else [t for t in (hair, beard) if t]
    if eyes:
        things.append(f"{eyes} eyes")
    sentence = head + (", with " + _join(things) if things else "")
    extras = []
    for f, option in (looks.get("features") or {}).items():
        say = d["features"].get(f, {}).get("options", {}).get(option, {}).get("say", "")
        if say:
            extras.append(say)
    mark = d["marks"].get(looks.get("mark", "none"), {}).get("say", "")
    if mark:
        extras.append(mark)
    paint = d["paints"].get(looks.get("paint", "none"), {}).get("say", "")
    if paint:
        extras.append(paint.replace("{c}", d["paint_colours"].get(looks.get("paint_colour", ""), {}).get("say", "")))
    if extras:
        sentence += "; " + _join(extras)
    return sentence[:1].upper() + sentence[1:] + "."


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]
