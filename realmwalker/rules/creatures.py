"""Creatures and encounter groups from data/creatures.json."""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules.items import Item
from realmwalker.rules.wounds import Wound


@dataclass
class Creature:
    uid: int
    def_id: str
    name: str  # what the game calls this one: "wolf", "Wat" (named humanoids)
    hp: int
    max_hp: int
    money: int = 0
    inventory: list[Item] = field(default_factory=list)
    wounds: list[Wound] = field(default_factory=list)
    conditions: dict[str, int] = field(default_factory=dict)
    uses: dict[str, int] = field(default_factory=dict)
    alive: bool = True
    named: bool = False
    sex: str = ""  # for named people: the sex their name goes with (so their picture matches)
    culture: str = ""  # the people they come from, for their dress (a mage in a turban); "" for no one in particular

    def to_dict(self) -> dict:
        return {"uid": self.uid, "def_id": self.def_id, "name": self.name, "hp": self.hp, "max_hp": self.max_hp,
                "money": self.money, "inventory": [i.to_dict() for i in self.inventory],
                "wounds": [w.to_dict() for w in self.wounds], "conditions": dict(self.conditions),
                "uses": dict(self.uses), "alive": self.alive, "named": self.named, "sex": self.sex,
                **({"culture": self.culture} if self.culture else {})}

    @classmethod
    def from_dict(cls, d: dict) -> Creature:
        return cls(uid=d["uid"], def_id=d["def_id"], name=d["name"], hp=d["hp"], max_hp=d["max_hp"],
                   money=d.get("money", 0), inventory=[Item.from_dict(i) for i in d.get("inventory", [])],
                   wounds=[Wound.from_dict(w) for w in d.get("wounds", [])], conditions=dict(d.get("conditions", {})),
                   uses=dict(d.get("uses", {})), alive=d.get("alive", True), named=d.get("named", False),
                   sex=d.get("sex", ""), culture=d.get("culture", ""))


class CreatureTable:
    def __init__(self, data: dict, statblocks: dict | None = None) -> None:
        """Creatures from data/creatures.json; one that names a 2025 stat block (data/statblocks.json) fights with it
        (rules/engine/statblocks.py puts the two together)."""
        from realmwalker.rules.engine import statblocks as sb

        blocks = (statblocks or {}).get("statblocks", {})
        self.blocks: dict[str, dict] = blocks
        self.defs: dict[str, dict] = {k: (sb.resolve(k, v, blocks) if "statblock" in v else v)
                                      for k, v in data["creatures"].items() if not k.startswith("_")}
        self.encounters: dict[str, dict] = {k: v for k, v in data["encounters"].items() if not k.startswith("_")}
        self.site_inhabitants: dict[str, list[str]] = data.get("site_inhabitants", {})

    def __getitem__(self, def_id: str) -> dict:
        return self.defs[def_id]

    def __contains__(self, def_id: object) -> bool:
        # Without this, "x in tables.creatures" walks the table as if it were a list, from index 0: KeyError: 0.
        return def_id in self.defs


def spawn(tables, def_id: str, rng: RNG, uid: int, *, now: int = 0) -> Creature:
    d = tables.creatures[def_id]
    hp = max(1, dice.roll(d["hp"], rng).total)
    name = d["name"]
    named = False
    sex = ""
    culture = d.get("names")
    if culture and culture in tables.names["cultures"] and rng.chance(0.7):
        c = tables.names["cultures"][culture]
        sex = rng.choice(["male", "male", "female"])
        name = rng.choice(c[sex])
        named = True
    money = individual_treasure(tables, float(d.get("cr", 0)), rng) if "individual" in keeps(d) else 0
    creature = Creature(uid=uid, def_id=def_id, name=name, hp=hp, max_hp=hp, money=money, named=named, sex=sex)
    next_uid = 1
    for item_id, qty in d.get("gear", []) + d.get("loot", []):
        if item_id in tables.items:
            condition = rng.randint(35, 95)
            creature.inventory.append(Item(next_uid, item_id, int(qty), condition=condition, made_at=now))
            next_uid += 1
    pocket = rng.child(f"trinket/{uid}")  # (its own stream: the fight's dice are as they were)
    if "individual" in keeps(d) and "trinket" in tables.items and \
            pocket.chance(float(tables.trinket_chance["pocket"])):
        from realmwalker.rules.items import make_trinket

        creature.inventory.append(make_trinket(tables, pocket, next_uid, now))
    if "relentless" in d.get("traits", []):
        creature.uses["relentless"] = 1
    return creature


# ---------------------------------------------------------------------------- what they carry (DMG 2024)
def keeps(cdef: dict) -> list[str]:
    """The creature's Monster Manual treasure, in lower case ("individual", a theme, "any", "none")."""
    return [t.lower() for t in cdef.get("treasure", ["none"])]


def individual_treasure(tables, cr: float, rng: RNG) -> int:
    """Random Individual Treasure (DMG 2024, data/treasure.json): copper for one creature of this Challenge Rating."""
    rows = tables.treasure["individual"]
    cr = max(0.0, float(cr))
    row = next((r for r in rows if cr <= r[1]), rows[-1])
    _lo, _hi, expr, times, coin = row
    return dice.roll(expr, rng).total * int(times) * int(tables.treasure["coins"][coin])


def band_purse(tables, creatures: list[Creature], rng: RNG) -> None:
    """A band of a kind that keeps a hoard at home (its block names a theme or Any, not Individual) carries one
    purse on the road: its leader's. Beasts and the dead carry nothing (their blocks say None)."""
    if any(c.money for c in creatures):
        return
    keepers = [c for c in creatures if keeps(tables.creatures[c.def_id]) and "none" not in keeps(tables.creatures[c.def_id])]
    if keepers:
        lead = max(keepers, key=lambda c: float(tables.creatures[c.def_id].get("cr", 0)))
        lead.money = individual_treasure(tables, float(tables.creatures[lead.def_id].get("cr", 0)), rng)


def spawn_group(tables, group_id: str, rng: RNG, first_uid: int = 1, *, now: int = 0, party_size: int = 3,
                budget: int | None = None) -> list[Creature]:
    """Spawn an encounter group. With an XP `budget` (DMG 2024, rules/encounter.py) the rank and file are trimmed or
    grown to fit it, never the last of a kind; without one, a lone traveller meets fewer of the rank and file."""
    from realmwalker.rules import encounter

    group = tables.creatures.encounters[group_id]
    out: list[Creature] = []
    uid = first_uid
    counts = encounter.counts_for(tables, group["members"], rng, budget, party_size)
    for (def_id, _count), n in zip(group["members"], counts):
        for _ in range(n):
            out.append(spawn(tables, def_id, rng, uid, now=now))
            uid += 1
    # Tell apart unnamed creatures of the same kind: "wolf", "second wolf"...
    seen: dict[str, int] = {}
    ordinals = ["", "second ", "third ", "fourth ", "fifth ", "sixth "]
    names = {c.name for c in out if c.named}
    for c in out:
        if c.named:
            # Two bandits called Isolde would be one too many: the next free name from the same list.
            others = [o for o in out if o is not c and o.named and o.name == c.name]
            culture = tables.creatures[c.def_id].get("names")
            pool = tables.names["cultures"].get(culture, {}).get(c.sex or "male", []) if others else []
            if others and c.name in pool and others[0].uid < c.uid:
                i = pool.index(c.name)
                c.name = next((n for n in pool[i + 1:] + pool[:i] if n not in names), c.name)
                names.add(c.name)
            continue
        seen[c.name] = seen.get(c.name, 0) + 1
        if seen[c.name] > 1:
            c.name = f"{ordinals[min(seen[c.name] - 1, len(ordinals) - 1)]}{c.name}"
    band_purse(tables, out, rng)
    return out


def typical_group(tables, group_id: str, party_size: int = 3) -> list[str]:
    """The members of a group as it usually turns up (the average roll, scaled for the party as spawn_group does):
    for judging how dangerous a kind of band is before anyone has met it."""
    group = tables.creatures.encounters[group_id]
    scale = min(1.3, 0.45 + 0.2 * max(1, party_size))
    out: list[str] = []
    for def_id, count in group["members"]:
        n, sides, flat = dice.parse(str(count))
        mean = max(1, int(round(n * (sides + 1) / 2 + flat)))
        if mean > 1:
            mean = max(1, int(round(mean * scale)))
        out += [def_id] * mean
    return out


def choose_encounter(tables, biome: str, danger: int, night: bool, on_road: bool, rng: RNG) -> str | None:
    """Pick a hostile group suited to the place, the danger level and the time of day."""
    options, weights = [], []
    for gid, g in tables.creatures.encounters.items():
        lo, hi = g["danger"]
        if not lo <= danger <= hi:
            continue
        if "any" not in g["biomes"] and biome not in g["biomes"] and tables.biomes.family(biome) not in g["biomes"]:
            continue
        if g["time"] == "night" and not night or g["time"] == "day" and night:
            continue
        weight = float(g.get("weight", 1))
        if g.get("road") and on_road:
            weight *= 2
        options.append(gid)
        weights.append(weight)
    if not options:
        return None
    return rng.weighted(options, weights)


def group_xp(tables, creatures: list[Creature]) -> int:
    return sum(int(tables.creatures[c.def_id]["xp"]) for c in creatures)
