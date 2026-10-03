"""Paper dolls: people drawn as a stack of tiles (body, clothes, hair, what they hold).

The player and companions wear what they really wear; townsfolk dress for their trade (data/sprites.json
"outfits"), and a few humanoid creatures (bandits, guards, cultists) are dressed the same way. Choices that are
not given by the game are picked by a stable hash of who it is, so a person looks the same every time.
"""

from __future__ import annotations

import zlib

LAYERS = ("cloak", "base", "boots", "legs", "body", "gloves", "hair", "beard", "head", "hand_right", "hand_left")
HIDES_HAIR = ("hood", "full", "iron", "fhelm", "chain", "helm", "dwarf_helm")  # headgear that covers the hair


def stable(key: str, n: int) -> int:
    return zlib.crc32(key.encode("utf-8")) % max(1, n) if n > 0 else 0


def choose(options, key: str):
    if not options:
        return ""
    if isinstance(options, str):
        return options
    return options[stable(key, len(options))]


def hair_word(text: str, table: dict) -> str | None:
    t = (text or "").lower()
    for word in table:
        if word != "_" and word in t:
            return word
    return None


def _base(sprites: dict, race: str, sex: str) -> str:
    r = sprites["races"].get(race) or sprites["races"]["human"]
    return r["female"] if sex == "female" else r["male"]


def _hair(sprites: dict, race: str, sex: str, looks: str, key: str, age: int = 30) -> tuple[str, str]:
    """(hair tile, beard tile) from the words used to describe them."""
    table = sprites["hair"]
    pool = table["elf"] if race == "elf" else table["female" if sex == "female" else "male"]
    word = hair_word(looks, pool)
    if word is None and age >= 55:
        word = "grey" if "grey" in pool else None
    hair = choose(pool.get(word) if word else pool["_"], key + "hair")
    beard = ""
    if sex != "female" and race != "elf":
        chance = sprites["races"].get(race, {}).get("beard", 0.4)
        if stable(key + "beard", 100) < chance * 100:
            bt = table["beard"]
            beard = bt.get(word or "_") or bt["_"]
    return (f"doll/hair/{hair}" if hair else "", f"doll/beard/{beard}" if beard else "")


def assemble(parts: dict[str, str]) -> list[str]:
    """Tile names, back to front, for the parts that exist."""
    out = []
    for layer in LAYERS:
        name = parts.get(layer)
        if name:
            out.append(name if "/" in name else f"doll/{layer}/{name}")
    return out


def npc(npc, tables) -> list[str]:
    """A townsperson dressed for their trade."""
    sp = tables.sprites
    key = f"npc{npc.id}"
    outfit = sp["outfits"].get(npc.job) or sp["outfits"]["_"]
    parts = {layer: choose(opts, key + layer) for layer, opts in outfit.items()}
    parts["base"] = _base(sp, npc.race, npc.sex)
    looks = (npc.profile or {}).get("appearance", "")
    hair, beard = _hair(sp, npc.race, npc.sex, looks, key, npc.age)
    if not parts.get("head", "").startswith(HIDES_HAIR):
        parts["hair"] = hair
    parts["beard"] = beard
    return assemble(parts)


def creature(def_id: str, tables, key: str) -> list[str]:
    """A creature: its own picture, or a dressed doll for people (bandits, guards...)."""
    spec = tables.sprites["creatures"].get(def_id)
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, dict) and "doll" in spec:
        doll = spec["doll"]
        parts = {layer: choose(opts, key + layer) for layer, opts in doll.items()}
        sex = "female" if stable(key + "sex", 5) == 0 else "male"
        parts["base"] = _base(tables.sprites, spec.get("race", "human"), sex)
        hair, beard = _hair(tables.sprites, "human", sex, "", key)
        if not parts.get("head"):
            parts["hair"] = hair
        parts["beard"] = beard
        return assemble(parts)
    if isinstance(spec, dict) and "tile" in spec:
        return [spec["tile"]]
    return [f"creature/{def_id}"]


def character(char, tables, *, lit: bool = False) -> list[str]:
    """The player or a companion, in what they wear and hold."""
    sp = tables.sprites
    worn = sp["worn"]
    key = f"pc{char.name}"
    parts: dict[str, str] = {"base": _base(sp, char.race, char.sex)}

    def wear(slot: str) -> dict:
        it = char.equipped_item(slot)
        return worn.get(it.def_id, {}) if it is not None else {}

    for slot in ("under", "main", "armor"):  # later slots cover earlier ones
        for layer, name in wear(slot).items():
            parts[layer] = name
    for slot in ("outer", "head", "helmet", "hands", "feet", "main_hand", "off_hand"):
        for layer, name in wear(slot).items():
            parts[layer] = name
    if "body" not in parts:
        fallback = sp["classes"].get(char.cls, {}).get("body") or ["plain"]
        parts["body"] = choose(fallback, key)
    if "legs" not in parts:
        parts["legs"] = "pants_brown"
    hair, beard = _hair(sp, char.race, char.sex, getattr(char, "appearance", ""), key, getattr(char, "age", 30))
    if not parts.get("head", "").startswith(HIDES_HAIR):
        parts["hair"] = hair
    parts["beard"] = beard
    if lit and not parts.get("hand_left"):
        parts["hand_left"] = "held_torch"
    return assemble(parts)
