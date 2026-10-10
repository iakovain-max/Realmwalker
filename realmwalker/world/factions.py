"""Factions: realms and lords, tribes, guilds, churches, cults and outlaws (M6).

Made with the world, after settlements, roads and sites, and kept in the world save. Code decides everything
here: who holds which settlement, who rules, who likes whom, and the laws. Words about them (chronicles,
legends) come later from the AI, with built-in text when it is not there.

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

CULTURE_RACE = {"elven": "elf", "dwarven": "dwarf", "halfling": "halfling", "orcish": "half_orc"}
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
    for fid, faith in tables.factions["faiths"].items():
        if culture in faith.get("cultures", []):
            return fid
    return "radiant"


def church_of(world, faith: str) -> Faction | None:
    for f in active_factions(world, "temple"):
        if f.faith == faith:
            return f
    return None


def figure_title(tables, kind: str, sex: str) -> str:
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
    """A new person of note, of a people's names."""
    cultures = tables.names["cultures"]
    names = cultures.get(culture) or cultures["heartland"]
    sex = sex or rng.choice(["male", "female"])
    family = family or rng.choice(names["family"])
    fig = Figure(
        id=world.next_figure_id, name=f"{rng.choice(names[sex])} {family}", sex=sex,
        race=race or CULTURE_RACE.get(culture, "human"), culture=culture,
        born=year - rng.randint(*age), faction=faction.id if faction else -1, title=title, role=role,
        traits=rng.sample(sorted(tables.people["personality"]), 2),
    )
    world.next_figure_id += 1
    world.figures[fig.id] = fig
    if faction is not None:
        faction.members.append(fig.id)
    return fig


def generate_factions(world, tables, rng: RNG) -> None:
    FactionMaker(world, tables, rng).run()


def ensure_factions(world, tables) -> bool:
    """Worlds made before M6 get their factions (and the rest of M6) when first loaded. True if made now."""
    if world.factions:
        return False
    generate_factions(world, tables, world.rng.child("factions-late"))
    return True


def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


class FactionMaker:
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
        from realmwalker.world.naming import Namer

        self.namer = Namer(tables.place_names, rng.child("names"))
        self.namer.used = set(self.used_names)

    def count(self, kind: str) -> int:
        return int(self.data["counts"].get(kind, [1, 1, 1])[self.size])

    # ------------------------------------------------------------------ helpers
    def run(self) -> None:
        w = self.w
        w.factions.clear()
        w.figures.clear()
        w.next_figure_id = 0
        for s in w.settlements:
            s.owner = -1
        for site in w.sites:
            site.faction = -1
        self.churches()
        self.realms()
        self.tribes()
        self.guilds()
        self.cults()
        self.outlaws()
        for f in active_factions(w):
            self.set_laws(f)
            self.set_strength(f)
        self.relations()
        for f in active_factions(w):
            self.set_goals(f)
        touch(w)

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

    def make_name(self, kind: str, **values: str) -> str:
        patterns = [p for p in self.data["kinds"][kind]["names"]
                    if all(slot in values or slot in self.data["words"] for slot in textgen.slots(p))]
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

    def names_for(self, culture: str) -> dict:
        cultures = self.t.names["cultures"]
        return cultures.get(culture) or cultures["heartland"]

    def new_figure(self, culture: str, *, faction: Faction | None = None, role: str = "member", title: str = "",
                   family: str | None = None, sex: str | None = None, age: tuple[int, int] = (25, 65),
                   race: str | None = None) -> Figure:
        return make_figure(self.w, self.t, self.rng, culture, year=self.year, faction=faction, role=role, title=title,
                           family=family, sex=sex, age=age, race=race)

    def give_leader(self, f: Faction, *, family: str | None = None, dynasty: bool = False,
                    age: tuple[int, int] = (28, 68)) -> Figure:
        sex = "male" if self.rng.chance(0.62) else "female"
        leader = self.new_figure(f.culture, faction=f, role="ruler", family=family, sex=sex, age=age)
        leader.title = figure_title(self.t, f.kind, sex)
        if self.rng.chance(0.2):
            leader.epithet = self.rng.choice(self.data["words"]["epithet"])
        f.leader = leader.id
        f.rulers.append(leader.id)
        if dynasty:
            family_name = leader.name.split()[-1]
            if self.rng.chance(0.7):
                other = "female" if sex == "male" else "male"
                spouse = self.new_figure(f.culture, faction=f, role="spouse", sex=other, age=(20, 60))
                spouse.spouse, leader.spouse = leader.id, spouse.id
            children = self.rng.randint(0, 3) if leader.age(self.year) > 24 else 0
            for i in range(children):
                hi = max(1, leader.age(self.year) - 17)
                child = self.new_figure(f.culture, faction=f, role="heir" if i == 0 else "member", family=family_name,
                                        age=(max(1, hi - 25), hi))
                child.parent = leader.id
        return leader

    def seat_family(self, culture: str) -> str:
        """A family name no other ruling house has."""
        used = self.__dict__.setdefault("used_families", set())
        options = [n for n in self.names_for(culture)["family"] if n not in used]
        family = self.rng.choice(options or self.names_for(culture)["family"])
        used.add(family)
        return family

    # ------------------------------------------------------------------ churches and orders
    def churches(self) -> None:
        cultures_here: dict[str, list] = {}
        for s in self.w.settlements:
            cultures_here.setdefault(s.culture, []).append(s)
        for fid, faith in self.data["faiths"].items():
            if faith.get("cult") or not faith.get("church"):
                continue
            followers = [s for c in faith["cultures"] for s in cultures_here.get(c, [])]
            if not followers:
                continue
            seat = max(followers, key=lambda s: s.population)
            f = self.new_faction("temple", seat.culture, faith["name"], faith=fid, seat=seat.id,
                                 values=self.pick_values("temple", list(faith["values"])))
            f.founded = self.year - self.rng.randint(300, 900)
            f.presence = [s.id for s in followers if s.kind != "hamlet"]
            self.give_leader(f, age=(40, 75))
        radiant = church_of(self.w, "radiant") or next(iter(active_factions(self.w, "temple")), None)
        if radiant is not None:
            towns = [s for s in self.w.settlements if s.id in radiant.presence and s.kind in ("town", "city")]
            seat = self.rng.choice(towns) if towns else self.w.settlements[radiant.seat]
            god = self.data["faiths"][radiant.faith]["short"]
            order = self.new_faction("knightly_order", seat.culture, self.make_name("knightly_order", god=god),
                                     faith=radiant.faith, seat=seat.id, liege=-1)
            order.presence = [seat.id]
            self.give_leader(order, age=(35, 65))

    # ------------------------------------------------------------------ realms
    def realms(self) -> None:
        w = self.w
        rng = self.rng
        human = [s for s in w.settlements if s.kind in HUMAN_SETTLEMENTS]
        big = sorted([s for s in human if s.kind == "city"], key=lambda s: -s.population)
        big += sorted([s for s in human if s.kind == "town"], key=lambda s: -s.population)
        capitals: list = []
        want = min(self.count("kingdom"), max(1, len(big)))
        spread = max(w.width, w.height) * 0.22
        for s in big:
            if len(capitals) >= want:
                break
            if not capitals or min(dist(s, c) for c in capitals) >= spread:
                capitals.append(s)
        if not capitals and big:
            capitals.append(big[0])
        reach = max(w.width, w.height) * 0.42
        # Free cities: big places far from any capital.
        free: list = []
        leftovers = [s for s in big if s not in capitals]
        leftovers.sort(key=lambda s: -(min((dist(s, c) for c in capitals), default=0) + (40 if s.kind == "city" else 0)))
        for s in leftovers[: self.count("free_city")]:
            if min((dist(s, c) for c in capitals), default=99) > spread * 0.6:
                free.append(s)
        # Kingdoms and their crown lands.
        kingdom_of: dict[int, Faction] = {}
        for cap in capitals:
            culture = cap.culture if cap.culture != "halfling" else "heartland"
            land = self.land_name(culture)
            k = self.new_faction("kingdom", culture, self.make_name("kingdom", land=land), seat=cap.id)
            k.flags["land"] = land
            k.founded = self.year - rng.randint(120, 400)
            family = self.seat_family(culture)
            self.give_leader(k, family=family, dynasty=True)
            k.flags["dynasty"] = family
            cap.owner = k.id
            kingdom_of[cap.id] = k
        for s in free:
            f = self.new_faction("free_city", s.culture, self.make_name("free_city", seat=s.name), seat=s.id)
            self.give_leader(f, age=(40, 70))
            s.owner = f.id
        # Who is within reach of which crown.
        realm_for: dict[int, Faction | None] = {}
        for s in human:
            if s.owner >= 0:
                realm_for[s.id] = w.factions[s.owner] if s.owner in [k.id for k in kingdom_of.values()] else None
                continue
            near = min(capitals, key=lambda c: dist(s, c)) if capitals else None
            realm_for[s.id] = kingdom_of[near.id] if near is not None and dist(s, near) <= reach else None
        # Noble houses at every other town and city of a kingdom; independent lordships beyond reach.
        seats: list = [c for c in capitals] + free
        for s in human:
            if s.owner >= 0 or s.kind not in ("town", "city"):
                continue
            k = realm_for.get(s.id)
            family = self.seat_family(s.culture if s.culture != "halfling" else "heartland")
            h = self.new_faction("noble_house", s.culture, f"House {family}", seat=s.id, liege=k.id if k else -1)
            if h.name in self.used_names:
                h.name = f"House {family} of {s.name}"
            self.used_names.add(h.name)
            h.flags["family"] = family
            self.give_leader(h, family=family, dynasty=True)
            s.owner = h.id
            seats.append(s)
        # Highland clans: northern villages in rough country far from any lord.
        rough = {"hills", "mountains", "pine_forest", "tundra"}
        for s in human:
            if s.owner >= 0 or s.kind != "village" or s.culture != "northmarch":
                continue
            near = min(seats, key=lambda o: dist(s, o)) if seats else None
            if (near is None or dist(s, near) > 14) and self.biome_at(s.x, s.y) in rough:
                family = self.seat_family("northmarch")
                c = self.new_faction("highland_clan", "northmarch", self.make_name("highland_clan", family=family),
                                     seat=s.id)
                c.flags["family"] = family
                self.give_leader(c, family=family, dynasty=True)
                s.owner = c.id
                seats.append(s)
        # Villages and hamlets go to the nearest lord of their own realm (or the nearest lord at all, if close).
        for s in human:
            if s.owner >= 0:
                continue
            k = realm_for.get(s.id)
            options = [o for o in seats if top_liege(w, w.factions[o.owner]) is k] if k is not None else seats
            options = options or seats
            if not options:
                continue
            near = min(options, key=lambda o: dist(s, o))
            if k is not None or dist(s, near) <= 16:
                s.owner = near.owner
        # Dwarven holds: a clan each.
        for s in w.settlements:
            if s.kind != "hold":
                continue
            family = self.seat_family("dwarven")
            c = self.new_faction("clan", "dwarven", self.make_name("clan", family=family), seat=s.id)
            c.founded = self.year - rng.randint(300, 1200)
            c.flags["family"] = family
            self.give_leader(c, family=family, dynasty=True, age=(60, 250))
            s.owner = c.id
        # Elven halls: one realm for each group of halls.
        halls = [s for s in w.settlements if s.kind == "elfhall"]
        while halls:
            seat = max(halls, key=lambda s: s.population)
            group = [s for s in halls if dist(s, seat) <= 45]
            area = w.area_at(seat.x, seat.y)
            land = area.name if area is not None else self.namer.settlement("elven")
            if any(land in f.name for f in active_factions(w, "elven_realm")):
                land = self.namer.settlement("elven")
            r = self.new_faction("elven_realm", "elven", self.make_name("elven_realm", land=land), seat=seat.id)
            r.founded = self.year - rng.randint(800, 3000)
            self.give_leader(r, dynasty=True, age=(150, 700))
            for s in group:
                s.owner = r.id
                halls.remove(s)

    def land_name(self, culture: str) -> str:
        """A country's name: a place-name root and a land ending ('Ashmark', 'Salvenza')."""
        places = self.t.place_names["settlements"]
        tables = places.get(culture) or places["heartland"]
        words = self.data["words"]
        suffixes = words.get(f"land_suffix_{culture}") or words["land_suffix_heartland"]
        name = ""
        for _ in range(30):
            prefix = self.rng.choice(tables["prefix"])
            suffix = self.rng.choice(suffixes)
            if prefix[-1:].lower() == suffix[:1].lower():
                suffix = suffix[1:]
            name = (prefix + suffix)[:1].upper() + (prefix + suffix)[1:].lower()
            if name not in self.used_names:
                break
        self.used_names.add(name)
        return name

    def biome_at(self, x: int, y: int) -> str:
        return self.w.biome_ids[int(self.w.biome[x, y])]

    # ------------------------------------------------------------------ the wild
    def tribes(self) -> None:
        w = self.w
        settled = {s.area for s in w.settlements}
        homes = {"hills": "orcs", "mountains": "orcs", "tundra": "orcs", "pine_forest": "goblins",
                 "marsh": "goblins", "forest": "goblins", "desert": "nomads"}
        candidates = []
        for a in w.areas:
            if a.kind not in homes or a.id in settled or a.size < 20:
                continue
            mask = w.area == a.id
            danger = float(w.danger[mask].mean()) if mask.any() else 0.0
            if danger >= 2.5:
                candidates.append((a.size * danger, a))
        candidates.sort(key=lambda t: -t[0])
        for _, a in candidates[: self.count("tribe")]:
            people = homes[a.kind]
            culture = "southron" if people == "nomads" else "orcish"
            name = self.make_name("tribe", land=a.name)
            t = self.new_faction("tribe", culture, name, area=a.id,
                                 faith="old_ways" if people == "nomads" else "red_jaw")
            t.flags["people"] = people
            race = {"orcs": "half_orc", "goblins": "half_orc", "nomads": "human"}[people]
            t.founded = self.year - self.rng.randint(30, 300)
            leader = self.give_leader(t, age=(22, 50))
            leader.race = race
            lair = self.site_in_area(a.id, ("cave", "ruin"))
            if lair is not None:
                lair.faction = t.id
                t.site = lair.id

    def site_in_area(self, area_id: int, kinds: tuple[str, ...]):
        options = [s for s in self.w.sites if s.faction < 0 and s.kind in kinds and int(self.w.area[s.x, s.y]) == area_id]
        return self.rng.choice(options) if options else None

    # ------------------------------------------------------------------ guilds
    def guilds(self) -> None:
        w = self.w
        towns = [s for s in w.settlements if s.kind in ("town", "city")]
        cities = sorted([s for s in w.settlements if s.kind == "city"], key=lambda s: -s.population) or \
            sorted(towns, key=lambda s: -s.population)
        if not towns:
            return
        for k in active_factions(w, "kingdom", "free_city"):
            seat = w.settlements[k.seat]
            name = self.make_name("merchant_guild", seat=seat.name)
            g = self.new_faction("merchant_guild", seat.culture, name, seat=seat.id)
            g.flags["realm"] = k.id
            g.presence = [s.id for s in holdings(w, k, deep=True) if s.kind in ("town", "city")] or [seat.id]
            self.give_leader(g, age=(35, 70))
        for seat in cities[: self.count("thieves_guild")]:
            g = self.new_faction("thieves_guild", seat.culture, self.make_name("thieves_guild"), seat=seat.id)
            g.presence = [s.id for s in towns if dist(s, seat) <= 35]
            self.give_leader(g, age=(25, 60))
        seat = self.rng.choice(cities[:3])
        g = self.new_faction("mages_circle", seat.culture, self.make_name("mages_circle", seat=seat.name), seat=seat.id)
        g.presence = [s.id for s in cities]
        tower = next((s for s in w.sites if s.kind == "tower" and s.faction < 0), None)
        if tower is not None and self.rng.chance(0.5):
            tower.faction = g.id
            g.site = tower.id
        self.give_leader(g, age=(45, 90))
        for _ in range(self.count("mercenary_company")):
            seat = self.rng.choice(towns)
            g = self.new_faction("mercenary_company", seat.culture, self.make_name("mercenary_company", seat=seat.name),
                                 seat=seat.id)
            g.presence = [seat.id]
            self.give_leader(g, age=(28, 55))
        seat = cities[0]
        g = self.new_faction("healers_guild", seat.culture, self.make_name("healers_guild"), seat=seat.id)
        g.presence = [s.id for s in towns]
        self.give_leader(g, age=(40, 70))
        holds = [s for s in w.settlements if s.kind == "hold"]
        seat = max(holds, key=lambda s: s.population) if holds else cities[0]
        g = self.new_faction("smiths_guild", seat.culture, self.make_name("smiths_guild"), seat=seat.id)
        g.presence = [s.id for s in towns + holds]
        self.give_leader(g, age=(40, 70))

    # ------------------------------------------------------------------ cults
    def cults(self) -> None:
        w = self.w
        gods = [fid for fid, f in self.data["faiths"].items() if f.get("cult")]
        self.rng.shuffle(gods)
        towns = [s for s in w.settlements if s.kind in ("town", "city", "village")]
        for faith in gods[: self.count("cult")]:
            god = self.data["faiths"][faith]["god"]
            site = next((s for s in self.shuffled(w.sites) if s.faction < 0 and s.kind in ("ruin", "barrow", "tower")), None)
            culture = self.rng.choice(towns).culture if towns else "heartland"
            c = self.new_faction("cult", culture, self.make_name("cult", god=god), faith=faith,
                                 values=self.pick_values("cult", list(self.data["faiths"][faith]["values"])))
            c.founded = self.year - self.rng.randint(5, 120)
            if site is not None:
                site.faction = c.id
                c.site = site.id
            if towns:
                c.presence = [s.id for s in self.rng.sample(towns, min(len(towns), self.rng.randint(1, 3)))]
            self.give_leader(c, age=(30, 70))

    def shuffled(self, items: list) -> list:
        out = list(items)
        self.rng.shuffle(out)
        return out

    # ------------------------------------------------------------------ outlaws
    def outlaws(self) -> None:
        w = self.w
        roads = w.road
        lairs = []
        for s in w.sites:
            if s.faction >= 0 or s.kind not in ("ruin", "cave", "tower"):
                continue
            x0, x1, y0, y1 = max(0, s.x - 8), s.x + 9, max(0, s.y - 8), s.y + 9
            if roads[x0:x1, y0:y1].any() and w.danger[s.x, s.y] >= 2:
                lairs.append(s)
        self.rng.shuffle(lairs)
        chosen: list = []
        for s in lairs:
            if len(chosen) >= self.count("bandit_gang"):
                break
            if all(dist(s, o) > 20 for o in chosen):
                chosen.append(s)
        for site in chosen:
            area = w.area_at(site.x, site.y)
            culture = self.nearest_culture(site.x, site.y)
            names = self.names_for(culture)
            captain_first = self.rng.choice(names["male"])
            land = area.name if area is not None else site.name
            g = self.new_faction("bandit_gang", culture, "", site=site.id, area=area.id if area else -1)
            leader = self.give_leader(g, age=(22, 50))
            leader.name = f"{captain_first} {leader.name.split()[-1]}"
            if not leader.epithet:
                leader.epithet = self.rng.choice(self.data["words"]["epithet"])
            g.name = self.make_name("bandit_gang", leader=leader.first_name, land=land)
            g.founded = self.year - self.rng.randint(1, 15)
            g.flags["range"] = 16
            site.faction = g.id
        coast = [s for s in w.settlements if s.kind in HUMAN_SETTLEMENTS and self.near_sea(s.x, s.y)]
        if coast:
            for _ in range(self.count("pirate_crew")):
                home = self.rng.choice(coast)
                culture = "southron" if home.culture == "southron" else home.culture
                p = self.new_faction("pirate_crew", culture, self.make_name("pirate_crew"), faith="drowned")
                p.flags["coast"] = [home.x, home.y]
                p.flags["range"] = 30
                p.founded = self.year - self.rng.randint(1, 20)
                self.give_leader(p, age=(25, 55))

    def near_sea(self, x: int, y: int) -> bool:
        w = self.w
        if "ocean" not in w.biome_ids:
            return False
        ocean = w.biome_ids.index("ocean")
        x0, x1, y0, y1 = max(0, x - 2), x + 3, max(0, y - 2), y + 3
        return bool((w.biome[x0:x1, y0:y1] == ocean).any())

    def nearest_culture(self, x: int, y: int) -> str:
        human = [s for s in self.w.settlements if s.kind in HUMAN_SETTLEMENTS]
        if not human:
            return "heartland"
        s = min(human, key=lambda s: (s.x - x) ** 2 + (s.y - y) ** 2)
        return s.culture if s.culture != "halfling" else "heartland"

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

    # ------------------------------------------------------------------ relations
    def relations(self) -> None:
        w = self.w
        rng = self.rng
        data = self.data
        facs = active_factions(w)
        faiths = data["faiths"]
        for i, a in enumerate(facs):
            for b in facs[i + 1:]:
                v = rng.gauss(0, 10)
                ra, rb = top_liege(w, a), top_liege(w, b)
                ga, gb = data["kinds"][a.kind]["group"], data["kinds"][b.kind]["group"]
                if a.liege == b.id or b.liege == a.id:
                    v += 45
                elif ra is rb and ga == gb == "realms":
                    v += rng.uniform(-35, 55)
                elif ga == gb == "realms":
                    v += rng.uniform(-45, 25)
                    if a.culture != b.culture and ("xenophobic" in a.values or "xenophobic" in b.values):
                        v -= 20
                    if a.culture in ("dwarven",) and b.culture in ("dwarven",):
                        v += 45
                for x, y in ((a, b), (b, a)):
                    gx, gy = data["kinds"][x.kind]["group"], data["kinds"][y.kind]["group"]
                    if x.kind == "cult":
                        v -= 60 if gy in ("realms", "faiths") else 10
                    if x.kind in ("bandit_gang", "pirate_crew") and gy in ("realms", "guilds") and y.kind != "thieves_guild":
                        v -= 55 if gy == "realms" else 25
                    if x.kind == "thieves_guild":
                        v += 20 if y.kind in ("bandit_gang", "pirate_crew") else -30 if gy == "realms" else 0
                    if x.kind == "tribe" and gy == "realms":
                        close = y.seat >= 0 and self.tribe_near(x, w.settlements[y.seat])
                        v -= 55 if close else 20
                    if x.kind == "temple" and gy == "realms":
                        v += 40 if x.faith == y.faith else -20 if "pious" in y.values else 0
                    if x.kind == "merchant_guild" and gy == "realms":
                        v += 30 if x.flags.get("realm") in (y.id, ra.id if ra else -1) else 8
                    if x.kind == "knightly_order" and gy == "realms" and x.faith == y.faith:
                        v += 25
                    if x.kind == "mercenary_company" and gy == "realms":
                        v += 10
                shared = len(set(a.values) & set(b.values))
                clash = sum(1 for va in a.values for vb in b.values if vb in data["values"][va]["clashes"])
                v += shared * 8 - clash * 10
                if a.faith != b.faith and (faiths.get(a.faith, {}).get("cult") or faiths.get(b.faith, {}).get("cult")):
                    v -= 15
                set_relation(w, a.id, b.id, v)

    def tribe_near(self, tribe: Faction, settlement) -> bool:
        if tribe.area < 0:
            return False
        a = self.w.areas[tribe.area]
        return math.hypot(a.x - settlement.x, a.y - settlement.y) < 35
