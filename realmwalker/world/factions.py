"""Factions: realms and lords, tribes, guilds, churches, cults and outlaws (M6).

Made with the world, after settlements, roads and sites, and kept in the world save. Code decides everything
here: who holds which settlement, who rules, who likes whom, and the laws.

Relations between factions run from -100 to +100 and are kept symmetric. A settlement's `owner` is the
faction that holds it directly (a noble house, the crown, a free city, a clan); its realm is the top of
the chain of lieges above that owner.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from realmwalker.core import textgen
from realmwalker.core.rng import RNG

CULTURE_RACE = {"elven": "elf", "dwarven": "dwarf", "halfling": "halfling", "orcish": "orc"}
REALM_KINDS = ("kingdom", "noble_house", "free_city", "clan", "highland_clan", "elven_realm")
TERRITORY_RADIUS = {"city": 13, "town": 9, "village": 6, "hamlet": 4, "hold": 10, "elfhall": 10}
HUMAN_SETTLEMENTS = ("hamlet", "village", "town", "city")
WATER_BIOMES = ("ocean", "lake")


@dataclass
class Figure:
    """A person who matters to history: rulers, heirs, guildmasters, legends. Becomes a townsperson when met."""

    id: int
    name: str
    sex: str
    race: str
    culture: str
    born: int  # year
    faction: int = -1
    title: str = ""  # "King", "Lady", "Guildmaster"
    role: str = ""  # ruler, heir, spouse, member, legend
    died: int | None = None
    cause: str = ""
    parent: int = -1
    spouse: int = -1
    epithet: str = ""
    traits: list[str] = field(default_factory=list)
    npc: int = -1  # the townsperson this figure is, once placed in a town
    notes: list[str] = field(default_factory=list)
    # The lived history (world/ages, 2026-10): all optional, so figures saved before it still load.
    kind: str = "person"  # person, dragon, beast, god
    mother: int = -1
    father: int = -1
    home: str = ""  # where they live(d): "S12" a settlement, "X5" a site (a lair, a tower, a barrow)
    died_at: str = ""  # where they died (the same kind of reference)
    buried: str = ""  # their grave, if anyone remembers it
    job: str = ""  # knight, priest, mage, smith, bard, chronicler, merchant, outlaw, adventurer, warchief...
    cls: str = ""  # an adventurer's calling (fighter, wizard...), with `level`
    level: int = 0
    kills: list[int] = field(default_factory=list)  # figures they slew
    slayer: int = -1  # the figure who slew them
    spheres: list[str] = field(default_factory=list)  # a god's domains
    creature: str = ""  # a beast's kind in data/creatures.json
    regnal: str = ""  # "III": the third of that name on a throne
    fame: int = 0  # how much there is to tell about them
    family: str = ""  # the family's own name as its men bear it (world/names.py); a woman's may differ in her name

    @property
    def alive(self) -> bool:
        return self.died is None

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    def age(self, year: int) -> int:
        return (self.died if self.died is not None else year) - self.born

    def full_name(self) -> str:
        epithet = f" {self.epithet}" if self.epithet else ""
        if self.title.startswith("the "):
            return f"{self.name}{epithet}, {self.title}"
        title = f"{self.title} " if self.title else ""
        if self.regnal:
            return f"{title}{self.first_name} {self.regnal}{epithet}"  # King Aldric III, not King Aldric III Draycott
        if self.epithet and self.kind == "person" and not self.epithet.startswith(("the ", "of ")) and \
                " " in self.name:
            return f"{title}{self.first_name}{epithet}"  # a by-name stands for the family: Anselm Bloodaxe
        return f"{title}{self.name}{epithet}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Figure:
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Faction:
    id: int
    name: str
    kind: str
    culture: str = ""
    leader: int = -1  # figure id
    seat: int = -1  # settlement id
    site: int = -1  # site id: a lair, a hidden shrine
    area: int = -1  # named area (a tribe's country)
    liege: int = -1  # the faction this one is sworn to
    faith: str = ""
    values: list[str] = field(default_factory=list)
    laws: dict = field(default_factory=dict)  # only for realms that make their own
    goals: list[str] = field(default_factory=list)
    relations: dict[int, int] = field(default_factory=dict)
    wealth: int = 0  # gold crowns, roughly
    military: int = 0  # fighting men, roughly
    founded: int = 0  # year
    fallen: int | None = None  # year it was destroyed or dissolved
    members: list[int] = field(default_factory=list)  # notable figures
    rulers: list[int] = field(default_factory=list)  # every leader so far, in order
    color: tuple[int, int, int] = (120, 120, 120)
    secret: bool = False
    presence: list[int] = field(default_factory=list)  # settlements with a chapter, temple or hidden cell
    flags: dict = field(default_factory=dict)

    @property
    def active(self) -> bool:
        return self.fallen is None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["relations"] = {str(k): v for k, v in self.relations.items()}
        d["color"] = list(self.color)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Faction:
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        known["relations"] = {int(k): int(v) for k, v in d.get("relations", {}).items()}
        known["color"] = tuple(d.get("color", (120, 120, 120)))
        return cls(**known)


# ---------------------------------------------------------------------------- queries
def active_factions(world, *kinds: str) -> list[Faction]:
    return [f for _, f in sorted(world.factions.items()) if f.active and (not kinds or f.kind in kinds)]


def owner_of(world, settlement) -> Faction | None:
    f = world.factions.get(getattr(settlement, "owner", -1))
    return f if f is not None and f.active else None


def top_liege(world, faction: Faction | None) -> Faction | None:
    seen = set()
    while faction is not None and faction.liege >= 0 and faction.id not in seen:
        seen.add(faction.id)
        up = world.factions.get(faction.liege)
        if up is None or not up.active:
            break
        faction = up
    return faction


def realm_of_settlement(world, settlement) -> Faction | None:
    return top_liege(world, owner_of(world, settlement))


def vassals(world, faction: Faction) -> list[Faction]:
    return [f for f in active_factions(world) if f.liege == faction.id]


def holdings(world, faction: Faction, deep: bool = False) -> list:
    """Settlements the faction holds (with deep=True, also those of its vassals, and theirs)."""
    ids = {faction.id}
    if deep:
        frontier = [faction]
        while frontier:
            f = frontier.pop()
            for v in vassals(world, f):
                if v.id not in ids:
                    ids.add(v.id)
                    frontier.append(v)
    return [s for s in world.settlements if getattr(s, "owner", -1) in ids]


def laws_of(world, faction: Faction | None) -> dict:
    """The laws that apply in a faction's lands: its own, or its liege's."""
    seen = set()
    while faction is not None and faction.id not in seen:
        seen.add(faction.id)
        if faction.laws:
            return faction.laws
        faction = world.factions.get(faction.liege)
    return {}


def laws_at(world, settlement) -> dict:
    return laws_of(world, owner_of(world, settlement))


def leader_of(world, faction: Faction | None) -> Figure | None:
    if faction is None:
        return None
    return world.figures.get(faction.leader)


def relation(world, a: int, b: int) -> int:
    if a == b:
        return 100
    fa = world.factions.get(a)
    return int(fa.relations.get(b, 0)) if fa is not None else 0


def set_relation(world, a: int, b: int, value: float) -> None:
    if a == b or a not in world.factions or b not in world.factions:
        return
    v = int(max(-100, min(100, round(value))))
    world.factions[a].relations[b] = v
    world.factions[b].relations[a] = v


def change_relation(world, a: int, b: int, amount: float) -> None:
    set_relation(world, a, b, relation(world, a, b) + amount)


def band(table: list, score: float) -> tuple[str, str]:
    """(name, colour) for a score, from a [[lowest score, name, colour], ...] table."""
    name, color = table[0][1], table[0][2]
    for low, n, c in table:
        if score >= low:
            name, color = n, c
    return name, color


def standing_name(tables, score: float) -> tuple[str, str]:
    return band(tables.factions["standings"], score)


def relation_state(world, tables, a: int, b: int) -> tuple[str, str]:
    at_war = any(w.get("active") and {w["attacker"], w["defender"]} == {a, b} for w in getattr(world, "wars", []))
    if at_war:
        return "at war", "danger"
    fa, fb = world.factions.get(a), world.factions.get(b)
    if fa is not None and fb is not None and (fa.liege == b or fb.liege == a):
        return ("vassal of" if fa.liege == b else "liege of"), "info"
    return band(tables.factions["relation_states"], relation(world, a, b))


def kind_label(tables, faction: Faction) -> str:
    label = tables.factions["kinds"].get(faction.kind, {}).get("label", faction.kind)
    people = faction.flags.get("people")
    return f"{label} of {people}" if people else label


def faction_title(world, tables, faction: Faction) -> str:
    """'House Draycott, sworn to the Kingdom of Ashmere' and the like (plain text, no markup)."""
    name = faction.name
    liege = world.factions.get(faction.liege)
    if liege is not None and liege.active:
        return f"{name}, sworn to {liege.name}"
    return name


def faith_for_culture(tables, culture: str) -> str:
    from realmwalker.world.cultures import faith_for

    return faith_for(tables, culture)


def family_of(fig) -> str:
    """A figure's family name (kept on the figure; else the last word of the name)."""
    if fig is None:
        return ""
    return fig.family or (fig.name.split()[-1] if " " in fig.name else "")


def church_of(world, faith: str) -> Faction | None:
    for f in active_factions(world, "temple"):
        if f.faith == faith:
            return f
    return None


def figure_title(tables, kind: str, sex: str, culture: str | None = None) -> str:
    """What the head of this kind of faction is called (by their people's custom: a Sultana, a Jarl, a Khagan)."""
    cultures = getattr(tables, "cultures", None)
    if cultures is not None:
        return cultures.title(kind, sex, culture)
    titles = tables.factions["kinds"][kind]["leader"]
    return titles[0] if sex == "male" else titles[1]


# ---------------------------------------------------------------------------- territory
def territory(world) -> tuple[np.ndarray, np.ndarray]:
    """(owner, realm) grids [x, y] of faction ids (-1 = nobody's), from the settlements' holders. Cached until
    ownership changes (bump world.faction_version)."""
    cache = getattr(world, "_territory", None)
    version = getattr(world, "faction_version", 0)
    if cache is not None and cache[0] == version:
        return cache[1], cache[2]
    w, h = world.width, world.height
    owner = np.full((w, h), -1, dtype=np.int16)
    realm = np.full((w, h), -1, dtype=np.int16)
    best = np.full((w, h), np.inf, dtype=np.float32)
    xs = np.arange(w, dtype=np.float32)[:, None]
    ys = np.arange(h, dtype=np.float32)[None, :]
    for s in world.settlements:
        f = owner_of(world, s)
        if f is None:
            continue
        r = TERRITORY_RADIUS.get(s.kind, 6)
        x0, x1 = max(0, s.x - r), min(w, s.x + r + 1)
        y0, y1 = max(0, s.y - r), min(h, s.y + r + 1)
        d = np.hypot(xs[x0:x1] - s.x, ys[:, y0:y1] - s.y) / r
        sub = best[x0:x1, y0:y1]
        closer = (d < 1.0) & (d < sub)
        sub[closer] = d[closer]
        owner[x0:x1, y0:y1][closer] = f.id
        top = top_liege(world, f)
        realm[x0:x1, y0:y1][closer] = top.id if top is not None else f.id
    for f in active_factions(world, "tribe"):
        if f.area >= 0:
            mask = (world.area == f.area) & (realm < 0)
            owner[mask] = f.id
            realm[mask] = f.id
    water = np.isin(world.biome, [world.biome_ids.index(b) for b in WATER_BIOMES if b in world.biome_ids])
    owner[water] = -1
    realm[water] = -1
    world._territory = (version, owner, realm)
    return owner, realm


def realm_at(world, x: int, y: int) -> Faction | None:
    _, realm = territory(world)
    f = world.factions.get(int(realm[x, y]))
    return f if f is not None and f.active else None


def lord_at(world, x: int, y: int) -> Faction | None:
    owner, _ = territory(world)
    f = world.factions.get(int(owner[x, y]))
    return f if f is not None and f.active else None


def touch(world) -> None:
    """Ownership or factions changed: maps and caches must be rebuilt."""
    world.faction_version = getattr(world, "faction_version", 0) + 1


# ---------------------------------------------------------------------------- making them
def make_figure(world, tables, rng: RNG, culture: str, *, year: int, faction: Faction | None = None,
                role: str = "member", title: str = "", family: str | None = None, sex: str | None = None,
                age: tuple[int, int] = (25, 65), race: str | None = None) -> Figure:
    """A new person of note, named as their people name people (world/names.py)."""
    from realmwalker.world.names import forge

    nf = forge(world, tables)
    sex = sex or rng.choice(["male", "female"])
    family = family or nf.family_base(culture, rng)
    noble = faction is not None and faction.kind in REALM_KINDS
    fig = Figure(
        id=world.next_figure_id, name=nf.person(culture, sex, rng, noble=noble, family=family), sex=sex,
        race=race or culture_race(tables, culture), culture=culture,
        born=year - rng.randint(*age), faction=faction.id if faction else -1, title=title, role=role,
        traits=rng.sample(sorted(tables.people["personality"]), 2), family=family,
    )
    world.next_figure_id += 1
    world.figures[fig.id] = fig
    if faction is not None:
        faction.members.append(fig.id)
    return fig


def culture_race(tables, culture: str) -> str:
    cultures = getattr(tables, "cultures", None)
    if cultures is not None and cultures.known(culture):
        return cultures.race(culture)
    return CULTURE_RACE.get(culture, "human")


def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


class FactionMaker:
    """Names, colours, values and laws for the factions the lived history makes (world/ages/sim.py)."""

    def __init__(self, world, tables, rng: RNG) -> None:
        self.w = world
        self.t = tables
        self.data = tables.factions
        self.rng = rng
        self.year = tables.calendar.start_year
        sizes = ["small", "medium", "large"]
        self.size = sizes.index(world.meta.size) if world.meta.size in sizes else 1
        self.used_names: set[str] = {s.name for s in world.settlements}
        self.colors = [tuple(c) for c in self.data["realm_colors"]]
        rng.shuffle(self.colors)
        self.color_i = 0
        from realmwalker.world.names import forge
        from realmwalker.world.naming import Namer

        self.forge = forge(world, tables)
        self.namer = Namer(tables.place_names, rng.child("names"), forge=self.forge)
        self.namer.used = set(self.used_names)

    # ------------------------------------------------------------------ helpers
    def pick_values(self, kind: str, extra: list[str] | None = None) -> list[str]:
        pairs = self.data["kinds"][kind]["values"]
        out: list[str] = list(extra or [])[:1]
        clashes = self.data["values"]
        for _ in range(8):
            if len(out) >= 2:
                break
            v = self.rng.weighted([p[0] for p in pairs], [float(p[1]) for p in pairs])
            if v in out or any(v in clashes[o]["clashes"] or o in clashes[v]["clashes"] for o in out):
                continue
            out.append(v)
        return out

    def make_name(self, kind: str, culture: str | None = None, **values: str) -> str:
        """A faction's name, in its people's manner when they have one for this kind ('the Sultanate of X')."""
        cultures = getattr(self.t, "cultures", None)
        names = cultures.realm_patterns(kind, culture) if cultures is not None and culture else \
            self.data["kinds"][kind]["names"]
        patterns = [p for p in names if all(slot in values or slot in self.data["words"] for slot in textgen.slots(p))]
        patterns = patterns or self.data["kinds"][kind]["names"][:1]
        name = ""
        for _ in range(20):
            name = textgen.fill(self.rng.choice(patterns), self.rng, self.data["words"], values)
            name = name[:1].lower() + name[1:] if name.startswith("The ") else name
            if name not in self.used_names:
                break
        self.used_names.add(name)
        return name

    def next_color(self) -> tuple[int, int, int]:
        c = self.colors[self.color_i % len(self.colors)]
        self.color_i += 1
        return c

    def new_faction(self, kind: str, culture: str, name: str = "", **kw) -> Faction:
        w = self.w
        fid = max(w.factions, default=-1) + 1
        spec = self.data["kinds"][kind]
        f = Faction(id=fid, name=name, kind=kind, culture=culture, secret=bool(spec.get("secret")),
                    founded=self.year - self.rng.randint(20, 240), **kw)
        if not f.values:
            f.values = self.pick_values(kind)
        if not f.faith:
            f.faith = faith_for_culture(self.t, culture)
        if spec["group"] == "realms":
            f.color = self.next_color()
        w.factions[fid] = f
        return f

    def seat_family(self, culture: str) -> str:
        """A family name no other ruling house has."""
        used = self.__dict__.setdefault("used_families", set())
        family = self.forge.family_base(culture, self.rng, avoid=used)
        used.add(family)
        return family

    # ------------------------------------------------------------------ names of countries
    def land_name(self, culture: str) -> str:
        """A country's name: a stem of its people and one of their land endings ('Ashmark', 'Qadiristan')."""
        name = ""
        for _ in range(30):
            name = self.forge.land(culture, self.rng)
            if name not in self.used_names:
                break
        self.used_names.add(name)
        return name

    # ------------------------------------------------------------------ laws, strength, goals
    def set_laws(self, f: Faction) -> None:
        if f.kind not in REALM_KINDS and f.kind != "tribe":
            return
        if f.kind == "noble_house" and f.liege >= 0:
            return  # their liege's laws
        laws = dict(self.data["culture_laws"].get(f.culture) or self.data["culture_laws"]["heartland"])
        for v in f.values:
            laws.update(self.data["value_laws"].get(v, {}))
        laws["faith"] = f.faith
        f.laws = laws

    def set_strength(self, f: Faction) -> None:
        spec = self.data["kinds"][f.kind]
        if spec["group"] == "realms":
            pop = sum(s.population for s in holdings(self.w, f))
            f.wealth = int(pop * self.rng.uniform(0.15, 0.3))
            factor = 1.5 if "warlike" in f.values else 0.8 if "mercantile" in f.values else 1.0
            f.military = int(pop * 0.035 * factor * self.rng.uniform(0.8, 1.2)) + 5
        else:
            f.wealth = self.rng.randint(*spec["wealth"])
            f.military = self.rng.randint(*spec["military"])

    def set_goals(self, f: Faction) -> None:
        w = self.w
        goals = []
        if f.kind in ("kingdom", "noble_house", "free_city", "clan", "highland_clan", "elven_realm"):
            enemies = sorted((o for o in active_factions(w, *REALM_KINDS) if o.id != f.id
                              and top_liege(w, o) is not top_liege(w, f)), key=lambda o: relation(w, f.id, o.id))
            if "expansionist" in f.values and enemies:
                goals.append(f"to take the lands of {enemies[0].name}")
            if "mercantile" in f.values:
                goals.append("to grow rich on trade")
            if "pious" in f.values:
                goals.append("to root out heresy")
            if f.liege >= 0 and self.rng.chance(0.3):
                goals.append(f"to be free of {w.factions[f.liege].name}")
        goals += {
            "tribe": ["to raid the soft lands", "to take back the old hunting grounds"],
            "merchant_guild": ["to control the trade of the realm"],
            "thieves_guild": ["to own the night markets", "to buy the watch"],
            "mages_circle": ["to recover lost lore"],
            "mercenary_company": ["to find a war that pays"],
            "healers_guild": ["to keep the plague from the towns"],
            "smiths_guild": ["to keep the secrets of good steel"],
            "temple": ["to bring the faithful home"],
            "knightly_order": ["to put down the servants of darkness"],
            "cult": [f"to wake {self.data['faiths'].get(f.faith, {}).get('god', 'their god')}"],
            "bandit_gang": ["to grow fat on the roads"],
            "pirate_crew": ["to take a rich ship"],
        }.get(f.kind, [])[:1]
        f.goals = goals[:3]
