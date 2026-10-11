"""Townsfolk: who lives in each settlement, where they are through the day, what they think of you,
and what they remember. Code decides everything mechanical (job, class, purse, stats, personality);
words (appearance, backstory, secret, what they want) come from the AI when it is there, otherwise
from data/people.json. A settlement's people are made the first time the player walks into it and
are then kept in the world save.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.rules.items import Item

from realmwalker.world.factions import CULTURE_RACE  # noqa: E402  (kept importable from here)
DAY_START, DAY_END = 7, 19
STAYS_AT_POST = {"innkeeper", "serving_hand", "guard", "priest", "lord", "wayfarer"}
WANDERS = {"guard", "farmer", "labourer", "weaver", "carter", "washerwoman", "beggar", "fisher", "woodcutter", "miner"}
MARKET_DAYS = ("Freyasday", "Saturnsday")  # when the square fills up

MOODS = [(-50, "hostile"), (-15, "unfriendly"), (15, "neutral"), (50, "friendly")]
CLASHING_TRAITS = {frozenset(p) for p in (("kind", "cruel"), ("trusting", "suspicious"), ("greedy", "generous"),
                                           ("cheerful", "bitter"), ("brave", "nervous"), ("honest", "sly"),
                                           ("gossipy", "taciturn"), ("proud", "weary"))}


@dataclass
class NPC:
    id: int
    name: str
    sex: str
    age: int
    race: str
    culture: str
    job: str
    title: str
    settlement: int
    notable: bool = False
    social: str = "low"
    purse: int = 0
    stats: str = "commoner"
    traits: list[str] = field(default_factory=list)
    speech: str = ""
    disposition: int = 0
    met: bool = False  # the player has spoken to them (so their disposition has been set)
    known: bool = False  # the player knows their name
    memory: list[str] = field(default_factory=list)
    profile: dict = field(default_factory=dict)  # appearance, personality, backstory, secret, want
    profile_source: str = ""  # "fallback" or "ai"
    profile_seen: bool = False
    alive: bool = True
    building: int = -1  # index of their workplace in the local map's buildings, or -1
    post: tuple[int, int] = (0, 0)  # where they work by day
    home: tuple[int, int] = (0, 0)  # where they sleep
    x: int = 0
    y: int = 0
    present: bool = True  # visible on the map right now (not shut away at home)
    flags: dict = field(default_factory=dict)
    inventory: list[Item] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["inventory"] = [i.to_dict() for i in self.inventory]
        d["post"] = [int(v) for v in self.post]
        d["home"] = [int(v) for v in self.home]
        d["x"], d["y"] = int(self.x), int(self.y)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> NPC:
        d = dict(d)
        d["inventory"] = [Item.from_dict(i) for i in d.get("inventory", [])]
        d["post"] = tuple(d.get("post", (0, 0)))
        d["home"] = tuple(d.get("home", (0, 0)))
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    def label(self) -> str:
        """How the player refers to them: 'Aldith, the innkeeper' or 'the innkeeper'."""
        return f"{self.first_name}, the {self.title}" if self.known else f"the {self.title}"

    def mood(self) -> str:
        for limit, word in MOODS:
            if self.disposition < limit:
                return word
        return "warm"

    def remember(self, fact: str) -> None:
        self.memory.append(fact)
        self.memory = self.memory[-8:]


@dataclass
class Town:
    settlement: int
    npcs: list[int] = field(default_factory=list)
    description: str = ""
    description_source: str = ""
    names: dict = field(default_factory=dict)  # building index -> sign name (inns, shops)
    shops: dict = field(default_factory=dict)  # merchant npc id -> shop state (economy)
    visited: int = -1  # world minute of the first visit
    seen: bool = False  # the description has been shown (so it is never replaced)
    names_seen: list[int] = field(default_factory=list)  # buildings whose sign the player has read
    flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"settlement": self.settlement, "npcs": list(self.npcs), "description": self.description,
                "description_source": self.description_source, "names": {str(k): v for k, v in self.names.items()},
                "shops": {str(k): v for k, v in self.shops.items()}, "visited": self.visited, "seen": self.seen,
                "names_seen": list(self.names_seen), "flags": self.flags}

    @classmethod
    def from_dict(cls, d: dict) -> Town:
        return cls(d["settlement"], list(d.get("npcs", [])), d.get("description", ""), d.get("description_source", ""),
                   {int(k): v for k, v in d.get("names", {}).items()}, {int(k): v for k, v in d.get("shops", {}).items()},
                   d.get("visited", -1), bool(d.get("seen", False)), list(d.get("names_seen", [])),
                   dict(d.get("flags", {})))


# ---------------------------------------------------------------------------- the world's registry
def town_of(world, sid: int) -> Town:
    town = world.towns.get(sid)
    if town is None:
        town = world.towns[sid] = Town(sid)
    return town


def npcs_in(world, sid: int) -> list[NPC]:
    town = world.towns.get(sid)
    if town is None:
        return []
    return [world.npcs[i] for i in town.npcs if i in world.npcs]


def npc_at(game, x: int, y: int) -> NPC | None:
    """A living, present townsperson standing at a local-map cell."""
    s = settlement_here(game)
    if s is None:
        return None
    for npc in npcs_in(game.world, s.id):
        if npc.alive and npc.present and npc.x == x and npc.y == y:
            return npc
    return None


def settlement_here(game):
    p = game.player
    if game.local is None or game.local.kind != "settlement":
        return None
    return game.world.settlement_at(p.x, p.y)


# ---------------------------------------------------------------------------- making people
def new_id(world) -> int:
    world.next_npc_id += 1
    return world.next_npc_id


def race_for(culture: str, rng: RNG, world=None, tables=None) -> tuple[str, str]:
    """(race, culture) for a townsperson: mostly the settlement's people, sometimes an outsider from this world."""
    from realmwalker.world.factions import culture_race

    if rng.chance(0.1):
        known = [c for c in (getattr(world, "culture_ids", None) or []) if c != "orcish"]
        outsider = rng.choice(known or ["heartland", "northmarch", "southron", "dwarven", "halfling", "elven"])
        return (culture_race(tables, outsider) if tables is not None else CULTURE_RACE.get(outsider, "human")), outsider
    return (culture_race(tables, culture) if tables is not None else CULTURE_RACE.get(culture, "human")), culture


def family_of(npc) -> str:
    """A townsperson's family name (kept when they were made; for older ones, the last word of their name)."""
    return npc.flags.get("family") or npc.name.split()[-1]


def make_npc(game, settlement, job: str, rng: RNG, *, building: int = -1, post=(0, 0), home=(0, 0)) -> NPC:
    t = game.tables
    people = t.people
    occ = people["occupations"][job]
    from realmwalker.world.names import forge

    nf = forge(game.world, t)
    race, culture = race_for(settlement.culture, rng, game.world, t)
    sex = occ.get("sex") or rng.choice(["male", "female"])
    taken = {n.first_name for n in npcs_in(game.world, settlement.id)}
    first = nf.given(culture, sex, rng, avoid=taken)  # two Gydas in one village is confusing
    family = nf.family_base(culture, rng)
    age_lo, age_hi = {"lord": (22, 66), "headman": (35, 70), "beggar": (18, 75), "serving_hand": (14, 30),
                      "acolyte": (16, 30), "guard": (18, 50)}.get(job, (18, 68))
    title = occ.get("titles", {}).get(settlement.kind, occ["name"])
    lo, hi = occ.get("purse", [0, 100])
    traits = rng.sample(sorted(people["personality"]), 2)
    while frozenset(traits) in CLASHING_TRAITS:
        traits = rng.sample(sorted(people["personality"]), 2)
    npc = NPC(
        id=new_id(game.world), name=nf.person(culture, sex, rng, first=first, family=family), sex=sex,
        age=rng.randint(age_lo, age_hi), race=race,
        culture=culture, job=job, title=title, settlement=settlement.id, notable=bool(occ.get("notable")),
        social=occ.get("social", "low"), purse=rng.randint(int(lo), int(hi)), stats=occ.get("stats", "commoner"),
        traits=traits, speech=rng.choice(people["speech"]), building=building, post=tuple(post), home=tuple(home),
        x=post[0], y=post[1],
    )
    npc.flags["family"] = family
    npc.profile = fallback_profile(game, npc, rng)
    npc.profile_source = "fallback"
    return npc


def fallback_profile(game, npc: NPC, rng: RNG) -> dict:
    t = game.tables.people["text"]
    old = npc.age >= 50
    pron = pronouns(npc)
    feature = rng.choice(t["feature"])
    values = {
        "build": rng.choice(t["build"]), "hair": rng.choice(t["hair_old" if old else "hair_young"]),
        "feature": feature, "feature_sentence": f"{pron['They']} {pron['have']} {feature}.",
        "clothes": rng.choice(t[f"clothes_{npc.social}"]),
        "person": {"male": "man", "female": "woman"}[npc.sex] if npc.age >= 18 else ("boy" if npc.sex == "male" else "girl"),
    }
    appearance = textgen.tidy(textgen.fill(rng.choice(t["appearance"]), rng, t, values))
    # A trade's own stories, mixed (for ordinary folk) with the ones anybody might have.
    own = t.get(f"backstory_{npc.job}")
    backstory = rng.choice(own if own and (npc.social != "low" or rng.chance(0.6)) else t["backstory_common"])
    secret = rng.choice(t["secret"])
    want = rng.choice(t["want"])
    words = [game.tables.people["personality"][tr]["words"] for tr in npc.traits]
    words.sort(key=lambda w: w.startswith(("a ", "an ")))  # "generous and a gossip", not "a gossip and generous"
    personality = f"{pron['They']} {pron['are']} {words[0]} and {words[1]}; {pron['their']} speech is {npc.speech}."
    return {"appearance": appearance, "personality": fill_pronouns(personality, pron),
            "backstory": fill_pronouns(backstory, pron), "secret": fill_pronouns(secret, pron),
            "want": fill_pronouns(want, pron)}


def pronouns(npc: NPC) -> dict:
    if npc.sex == "female":
        return {"they": "she", "They": "She", "them": "her", "their": "her", "themselves": "herself", "are": "is",
                "have": "has", "s": "s"}
    return {"they": "he", "They": "He", "them": "him", "their": "his", "themselves": "himself", "are": "is",
            "have": "has", "s": "s"}


def fill_pronouns(text: str, pron: dict) -> str:
    for k, v in pron.items():
        text = text.replace("{" + k + "}", v)
    return text


# ---------------------------------------------------------------------------- filling a town
def populate_town(game, lm, settlement) -> Town:
    """Put people into a settlement's close-up map the first time anyone arrives."""
    world = game.world
    town = town_of(world, settlement.id)
    if town.npcs:
        return town
    town.visited = world.time
    rng = world.rng.child(f"people/{settlement.id}")
    from realmwalker.game.people_ai import fallback_description, fallback_inn_name

    if not town.description:
        town.description = fallback_description(game, settlement, rng.child("description"))
        town.description_source = "fallback"
    for bi, b in enumerate(lm.buildings):
        if b.kind == "inn" and bi not in town.names:
            town.names[bi] = fallback_inn_name(game, rng.child(f"inn/{bi}"))
    people = game.tables.people
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken: set[tuple[int, int]] = set()

    def inside(b) -> tuple[int, int]:
        cells = [(int(x), int(y)) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1)
                 if walk[x, y] and (x, y) not in taken and (x, y) != tuple(b.door)]
        spot = rng.choice(cells) if cells else (int(b.x + b.w // 2), int(b.y + b.h // 2))
        taken.add(spot)
        return spot

    houses = [i for i, b in enumerate(lm.buildings) if b.kind == "house"]

    def a_home() -> tuple[int, int]:
        if not houses:
            return lm.entry
        return inside(lm.buildings[rng.choice(houses)])

    street_cells = outdoor_cells(game, lm, walk)

    def street() -> tuple[int, int]:
        free = [c for c in street_cells if c not in taken]
        spot = rng.choice(free) if free else lm.entry
        taken.add(spot)
        return spot

    role_for = {"inn": ["innkeeper", "serving_hand"], "temple": ["priest"], "smithy": ["smith"], "store": ["shopkeeper"],
                "healer": ["healer"], "stable": ["stablemaster"], "hall": ["headman"], "keep": ["lord"]}
    seen_roles: set[str] = set()
    for bi, b in enumerate(lm.buildings):
        for job in role_for.get(b.kind, []):
            if job == "serving_hand" and (settlement.kind in ("hamlet", "village") or rng.chance(0.4)):
                continue
            if job in ("innkeeper", "priest", "smith", "shopkeeper") or job not in seen_roles or settlement.kind == "city":
                spot = inside(b)
                npc = make_npc(game, settlement, job, rng.child(f"{bi}/{job}"), building=bi, post=spot,
                               home=spot if job in STAYS_AT_POST else a_home())
                add(world, town, npc)
                seen_roles.add(job)
        if b.kind == "temple" and settlement.kind in ("town", "city"):
            spot = inside(b)
            add(world, town, make_npc(game, settlement, "acolyte", rng.child(f"{bi}/acolyte"), building=bi, post=spot, home=spot))
    spec = people["settlement_people"].get(settlement.kind, people["settlement_people"]["village"])
    for job in spec["notables"]:
        if job not in seen_roles:
            home = a_home()
            add(world, town, make_npc(game, settlement, job, rng.child(f"notable/{job}"), post=home, home=home))
    # Market traders at the stalls.
    stalls = [(int(x), int(y)) for x, y in zip(*np.nonzero(game.remap_for(lm)[lm.terrain] == game.tables.terrain.index.get("stall", -1)))]
    for i, (sx, sy) in enumerate(stalls[:4]):
        spot = next(((sx + dx, sy + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                     if lm.in_bounds(sx + dx, sy + dy) and walk[sx + dx, sy + dy] and (sx + dx, sy + dy) not in taken), None)
        if spot is None:
            continue
        taken.add(spot)
        add(world, town, make_npc(game, settlement, "market_trader", rng.child(f"stall/{i}"), post=spot, home=a_home()))
    lo, hi = spec["guards"]
    for i in range(rng.randint(lo, hi)):
        spot = street()
        add(world, town, make_npc(game, settlement, "guard", rng.child(f"guard/{i}"), post=spot, home=spot))
    lo, hi = spec["commoners"]
    jobs = people["commoner_jobs"]
    sx, sy = settlement.x, settlement.y  # (the town may be made ahead of arrival, or for a quest far away)
    around = {game.biome_key(nx, ny) for _, nx, ny in world.neighbours(sx, sy)}
    for i in range(rng.randint(lo, hi)):
        job = rng.choice(jobs)
        near = people["occupations"][job].get("near")
        if near == "water" and not (world.river[sx, sy] or "lake" in around or "ocean" in around or "coast" in around):
            job = "labourer"
        if near == "forest" and not around & {"forest", "pine_forest"}:
            job = "farmer"
        if near == "hills" and not around & {"hills", "mountains"}:
            job = "labourer"
        add(world, town, make_npc(game, settlement, job, rng.child(f"common/{i}"), post=street(), home=a_home()))
    link_figures(game, town, settlement, lm, inside, rng)
    secret_members(game, town, settlement, rng)
    update_positions(game, lm)
    return town


# ---------------------------------------------------------------------------- townsfolk and factions (M6)
FIGURE_JOBS = {"kingdom": "lord", "noble_house": "lord", "free_city": "lord", "highland_clan": "headman",
               "clan": "headman", "elven_realm": "headman", "temple": "priest", "merchant_guild": "shopkeeper",
               "smiths_guild": "smith", "healers_guild": "healer"}


def link_figures(game, town: Town, settlement, lm, inside, rng: RNG) -> None:
    """The rulers and masters who live here are the people of history: the king in the keep, the lady in the
    hall, the high priest in the temple."""
    from realmwalker.world import factions as fx

    w = game.world
    for f in fx.active_factions(w):
        if f.seat != settlement.id or f.kind not in FIGURE_JOBS or f.flags.get("minor"):
            continue
        fig = fx.leader_of(w, f)
        if fig is None or not fig.alive or (fig.npc >= 0 and fig.npc in w.npcs):
            continue
        job = FIGURE_JOBS[f.kind]
        npc = next((n for n in npcs_in(w, settlement.id) if n.job == job and "figure" not in n.flags), None)
        if npc is None and job == "lord":
            hall = next((i for i, b in enumerate(lm.buildings) if b.kind in ("keep", "hall")), None)
            if hall is None:
                continue
            spot = inside(lm.buildings[hall])
            npc = make_npc(game, settlement, "lord", rng.child(f"lord/{f.id}"), building=hall, post=spot, home=spot)
            add(w, town, npc)
        if npc is not None:
            become_figure(game, npc, fig, rng.child(f"figure/{fig.id}"))


TRAVELLERS = {"hamlet": (0, 0), "village": (0, 1), "town": (1, 2), "city": (2, 3), "hold": (0, 1), "elfhall": (0, 1)}
TRAVELLER_DAYS = 30


def refresh_travellers(game, lm, settlement) -> None:
    """Travellers looking for work come and go at the inns, a new lot every month or so. In a mercenary
    company's home town some of its sell-swords are free to hire."""
    from realmwalker.world import factions as fx

    world = game.world
    town = world.towns.get(settlement.id)
    if town is None or not town.npcs or lm.kind != "settlement" or not getattr(game.tables, "companions", None):
        return
    day = game.moment.total_days
    if day - int(town.flags.get("travellers_day", -10**6)) < TRAVELLER_DAYS:
        return
    town.flags["travellers_day"] = day
    for n in npcs_in(world, settlement.id):
        if n.job == "adventurer" and not n.flags.get("companion") and not n.flags.get("grateful") and n.alive:
            n.alive = False  # moved on (they are not dead; they are simply gone from here)
            n.present = False
            n.flags["moved_on"] = True
    inns = [i for i, b in enumerate(lm.buildings) if b.kind == "inn"]
    if not inns:
        return
    rng = world.rng.child(f"travellers/{settlement.id}/{day}")
    arch = game.tables.companions["archetypes"]
    at_inn = [a for a, spec in arch.items() if "inn" in spec["where"]]
    lo, hi = TRAVELLERS.get(settlement.kind, (0, 1))
    count = rng.randint(lo, hi)
    home = f"S{settlement.id}"
    if count == 0 and any(f.alive and f.home == home and f.job in ("adventurer", "hero") and f.kind == "person"
                          for f in world.figures.values()):
        count = 1  # a hero of the old songs drinks here when they are at home
    company = next((f for f in fx.active_factions(world, "mercenary_company") if f.seat == settlement.id), None)
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken = {(n.x, n.y) for n in npcs_in(world, settlement.id)}
    for i in range(count + (2 if company is not None else 0)):
        from_company = company is not None and i >= count
        pool = [a for a, spec in arch.items() if "company" in spec["where"]] if from_company else at_inn
        a = rng.weighted(pool, [float(arch[x]["weight"]) for x in pool])
        bi = rng.choice(inns)
        b = lm.buildings[bi]
        cells = [(int(x), int(y)) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1)
                 if walk[x, y] and (x, y) not in taken]
        if not cells:
            continue
        spot = rng.choice(cells)
        taken.add(spot)
        npc = make_npc(game, settlement, "adventurer", rng.child(f"traveller/{i}"), building=bi, post=spot, home=spot)
        npc.title = arch[a]["name"]
        npc.flags["recruit"] = a
        if from_company:
            npc.flags["company"] = company.id
            npc.title = f"sell-sword of {company.name}"
        npc.profile["backstory"] = rng.choice(arch[a]["story"])
        add(world, town, npc)
    heroes_at_the_inn(game, settlement, rng)
    update_positions(game, lm)


def heroes_at_the_inn(game, settlement, rng: RNG) -> None:
    """A hero of the lived history who calls this town home sits among the travellers at the inn: someone who
    slew a beast or found a lost treasure, with that story to tell (and a sword for hire)."""
    w = game.world
    home = f"S{settlement.id}"
    heroes = [f for f in w.figures.values() if f.alive and f.kind == "person" and f.home == home
              and f.job in ("adventurer", "hero") and (f.npc < 0 or f.npc not in w.npcs or not w.npcs[f.npc].alive)]
    if not heroes:
        return
    fig = max(heroes, key=lambda f: (f.fame, -f.id))
    free = [n for n in npcs_in(w, settlement.id) if n.job == "adventurer" and n.alive and "figure" not in n.flags
            and not n.flags.get("company") and not n.flags.get("companion")]
    if not free:
        return
    npc = free[0]
    title = npc.title
    become_figure(game, npc, fig, rng.child(f"hero/{fig.id}"))
    npc.title = title  # still what the inn calls them: a sell-sword, a wandering knight
    npc.flags["hero"] = True


def refresh_figures(game, lm, settlement) -> None:
    """A new ruler (the old one died while you were away) now sits in the hall."""
    world = game.world
    town = world.towns.get(settlement.id)
    if town is None or not town.npcs or lm.kind != "settlement":
        return
    rng = world.rng.child(f"refresh/{settlement.id}/{world.time}")
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken = {(n.x, n.y) for n in npcs_in(world, settlement.id)}

    def inside(b) -> tuple[int, int]:
        cells = [(int(x), int(y)) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1)
                 if walk[x, y] and (x, y) not in taken and (x, y) != tuple(b.door)]
        spot = rng.choice(cells) if cells else (int(b.x + b.w // 2), int(b.y + b.h // 2))
        taken.add(spot)
        return spot

    before = set(town.npcs)
    for npc in npcs_in(world, settlement.id):
        fig = world.figures.get(npc.flags.get("figure", -1))
        if fig is not None and not fig.alive:
            npc.flags.pop("figure", None)  # the dead lord's chair is empty; their heir will take it
    link_figures(game, town, settlement, lm, inside, rng)
    if set(town.npcs) != before:
        update_positions(game, lm)


def become_figure(game, npc: NPC, fig, rng: RNG) -> None:
    """A townsperson takes on the name, age and nature of a figure of history (and their story, if the world lived
    its history: world/ages)."""
    npc.name, npc.sex, npc.race, npc.culture = fig.name, fig.sex, fig.race, fig.culture
    npc.age = max(14, fig.age(game.moment.year))
    if fig.title and not fig.title.startswith("the "):
        npc.title = fig.title.lower()
    if fig.traits:
        npc.traits = list(fig.traits)
    npc.notable = True
    if fig.role == "ruler" and npc.job in ("lord", "headman"):
        npc.social = "high" if npc.job == "lord" else npc.social
    npc.flags["figure"] = fig.id
    fig.npc = npc.id
    npc.profile = fallback_profile(game, npc, rng)
    npc.profile_source = "fallback"
    from realmwalker.game import past

    story = past.figure_story(game, fig, rng)
    if story:
        npc.profile["backstory"] = story
    grudge = past.grudge_of(game.world, fig.id)
    if grudge is not None:
        npc.profile["want"] = past.grudge_want(game, grudge)  # a blood feud the history left them
        npc.flags["grudge"] = grudge["against"]


def secret_members(game, town: Town, settlement, rng: RNG) -> None:
    """Thieves and cultists hide among ordinary folk."""
    from realmwalker.world import factions as fx

    w = game.world
    folk = [n for n in npcs_in(w, settlement.id) if not n.notable and n.job not in ("guard", "acolyte")]
    for f in fx.active_factions(w, "thieves_guild", "cult"):
        if settlement.id not in f.presence and f.seat != settlement.id:
            continue
        free = [n for n in folk if "secret" not in n.flags]
        for n in rng.sample(free, min(len(free), 2 if f.kind == "thieves_guild" else 1)):
            n.flags["secret"] = f.id


def npc_factions(game, npc: NPC) -> list:
    """The factions a townsperson answers to, most important first (secret ones are not included)."""
    from realmwalker.world import factions as fx

    w = game.world
    out = []
    fig = w.figures.get(npc.flags.get("figure", -1))
    if fig is not None and fig.faction in w.factions and w.factions[fig.faction].active:
        out.append(w.factions[fig.faction])
    settlement = w.settlements[npc.settlement]
    guild_for = {"priest": ("temple",), "acolyte": ("temple",), "smith": ("smiths_guild",),
                 "shopkeeper": ("merchant_guild",), "market_trader": ("merchant_guild",), "healer": ("healers_guild",)}
    kinds = guild_for.get(npc.job)
    for f in fx.active_factions(w, *kinds) if kinds else []:
        if f not in out and (settlement.id in f.presence or f.seat == settlement.id):
            if f.kind != "temple" or f.faith == fx.faith_for_culture(game.tables, settlement.culture):
                out.append(f)
                break
    owner = fx.owner_of(w, settlement)
    if owner is not None and owner not in out:
        out.append(owner)
    return out


def prepare_town(game, settlement) -> Town:
    """Make a settlement's close-up map and people ahead of arrival (so the AI can dress them in time)."""
    from realmwalker.world.local import get_local_map

    lm = get_local_map(game.world, game.tables, settlement.x, settlement.y)
    if lm.kind != "settlement":
        return town_of(game.world, settlement.id)
    return populate_town(game, lm, settlement)


def add(world, town: Town, npc: NPC) -> None:
    world.npcs[npc.id] = npc
    town.npcs.append(npc.id)


def outdoor_cells(game, lm, walk=None) -> list[tuple[int, int]]:
    """Streets and open ground inside the settlement, where people walk about."""
    if walk is None:
        walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    ids = game.tables.terrain.index
    street = {ids.get(n, -1) for n in ("road", "cobbles", "dirt")}
    terrain = game.remap_for(lm)[lm.terrain]
    mask = np.isin(terrain, list(street)) & walk
    cells = [(int(x), int(y)) for x, y in zip(*np.nonzero(mask))]
    cx, cy = lm.width // 2, lm.height // 2
    return [c for c in cells if abs(c[0] - cx) < 36 and abs(c[1] - cy) < 22 and lm.building_at(*c) is None]


# ---------------------------------------------------------------------------- days and nights
def is_day(game) -> bool:
    h = game.moment.hour
    return DAY_START <= h < DAY_END


def update_positions(game, lm) -> None:
    """Morning and evening: people go to work, or home. During the day some wander."""
    s = settlement_here(game)
    if s is None:
        return
    day = is_day(game)
    occupied = {(game.player.lx, game.player.ly)} | {(a.x, a.y) for a in lm.actors}
    for npc in npcs_in(game.world, s.id):
        if not npc.alive or npc.flags.get("companion") or npc.flags.get("escort") is not None:
            npc.present = False  # (those travelling with you are with you, not here as well)
            continue
        if npc.job in STAYS_AT_POST:
            target, present = npc.post, True
        elif day:
            target, present = npc.post, True
        else:
            target, present = npc.home, False  # at home behind a shut door
        if npc.flags.get("fled_until", -1) > game.world.time:
            present = False
        was_day = npc.flags.get("day")
        if was_day != day or not present:
            if target not in occupied:
                npc.x, npc.y = target
        npc.flags["day"] = day
        npc.present = present
        if present:
            occupied.add((npc.x, npc.y))


def wander(game, lm) -> None:
    """Some people drift about the streets as you walk."""
    s = settlement_here(game)
    if s is None:
        return
    rng = game.world.rng.child(f"wander/{game.world.time}/{game.player.steps}")
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    people = npcs_in(game.world, s.id)
    occupied = {(n.x, n.y) for n in people if n.alive and n.present}
    occupied.add((game.player.lx, game.player.ly))
    for npc in people:
        if not (npc.alive and npc.present and npc.job in WANDERS) or rng.random() > 0.35:
            continue
        dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        nx, ny = npc.x + dx, npc.y + dy
        if not lm.in_bounds(nx, ny) or not walk[nx, ny] or (nx, ny) in occupied or lm.building_at(nx, ny) is not None:
            continue
        if abs(nx - npc.post[0]) > 7 or abs(ny - npc.post[1]) > 5:
            continue
        occupied.discard((npc.x, npc.y))
        npc.x, npc.y = nx, ny
        occupied.add((nx, ny))


# ---------------------------------------------------------------------------- first impressions
def first_impression(game, npc: NPC) -> int:
    """How they feel about you the first time you speak."""
    from realmwalker.rules.character import Sheet

    t = game.tables
    c = game.leader
    s = Sheet(c, t)
    score = sum(int(t.people["personality"][tr]["disposition"]) for tr in npc.traits)
    expected = {"low": 0, "middle": 1, "high": 2}[npc.social]
    score += max(-15, min(10, (s.social() - expected) * 5))
    if c.dirt >= 85:
        score -= 20
    elif c.dirt >= 60:
        score -= 10
    if any(w.bleed and not w.bandaged for w in c.wounds):
        score += 5 if "kind" in npc.traits else -5
    if c.race != npc.race:
        if c.race == "half_orc":
            score -= 5 if "kind" in npc.traits else 12
        else:
            score -= 3
    if c.background == "noble" and npc.social == "high":
        score += 8
    if c.background == "acolyte" and npc.job in ("priest", "acolyte"):
        score += 10
    if c.race == npc.race and c.culture == npc.culture:
        score += 3
    score += papers_impression(game, npc)
    score += faction_impression(game, npc)
    score += fame_impression(game, npc)
    return max(-80, min(80, score))


IMPRESSED = {  # who each kind of paper, ring or insignia speaks to (data/items.json "impress")
    "high": lambda npc: npc.social == "high",
    "priests": lambda npc: npc.job in ("priest", "acolyte"),
    "soldiers": lambda npc: npc.job in ("guard", "lord"),
    "traders": lambda npc: npc.job in ("shopkeeper", "smith", "market_trader", "innkeeper", "stablemaster", "healer"),
}


def papers_impression(game, npc: NPC) -> int:
    """A signet ring on your hand, a holy symbol at your neck, a guild's letter or an old soldier's insignia in your pack:
    the people they speak to think better of you. The best one of each kind counts."""
    from realmwalker.rules.inventory import carried

    c = game.leader
    worn = set(c.equipped.values())
    best: dict[str, int] = {}
    for it in carried(game.party):
        imp = game.tables.items.get(it.def_id).get("impress")
        if not imp or (imp.get("worn") and it.uid not in worn):
            continue
        if IMPRESSED.get(imp["people"], lambda n: False)(npc):
            best[imp["people"]] = max(best.get(imp["people"], 0), int(imp["bonus"]))
    return sum(best.values())


def fame_impression(game, npc: NPC) -> int:
    """People have heard of you, or heard something about you. Notables hear more, and sooner."""
    r = game.renown
    weight = 1.0 if npc.notable else 0.6
    good = min(15, int(r.fame / 3 * weight))
    bad = min(25, int(r.infamy / 2 * weight))
    if "greedy" in npc.traits or "proud" in npc.traits:
        good = int(good * 1.5)  # fame impresses some people more than it should
    if "kind" in npc.traits or "nervous" in npc.traits:
        bad = int(bad * 1.5)  # and a bad name frightens others more
    return good - bad


def faction_impression(game, npc: NPC) -> int:
    """What your name is worth with their people, and whether there is a price on your head here."""
    from realmwalker.game.reputation import standing
    from realmwalker.world import factions as fx

    if not game.world.factions:
        return 0
    score = 0
    facs = npc_factions(game, npc)
    if facs:
        score += int(max(-25, min(20, standing(game, facs[0].id) / 3)))
        if any(f.id in game.renown.members for f in facs):
            score += 10
    secret = npc.flags.get("secret")
    if secret is not None and secret in game.renown.members:
        score += 15
    realm = fx.realm_of_settlement(game.world, game.world.settlements[npc.settlement])
    if realm is not None and game.renown.bounties.get(realm.id, 0) > 0 and not game.leader.effects.get("disguised"):
        score -= 25 if npc.job == "guard" else 8
    if realm is not None and "xenophobic" in realm.values and game.leader.race != npc.race:
        score -= 5
    thief = secret is not None and game.world.factions.get(secret) is not None and \
        game.world.factions[secret].kind in ("thieves_guild", "cult")
    r = game.renown
    score += min(8, r.fame // 5)
    score -= 0 if thief else min(12, r.infamy // 3)
    if "branded" in r.marks and not thief:
        score -= 10
    if r.flags.get("titles") and npc.social == "high":
        score += 6
    return score


def meet(game, npc: NPC) -> None:
    if not npc.met:
        npc.met = True
        npc.disposition = first_impression(game, npc)
        npc.remember(f"first met the traveller on {game.moment.date_text()}")


def change_disposition(npc: NPC, amount: int) -> None:
    npc.disposition = max(-100, min(100, npc.disposition + amount))


def town_moment(game, settlement) -> str:
    """One small thing seen in the street: idle life, or what the town is going through."""
    text = game.tables.people["text"]
    pools = ["moments"]
    pools.append("moments_day" if is_day(game) else "moments_night")
    for state in ("plague", "famine", "raided", "siege"):
        if settlement.status.get(state):
            pools.append(f"moments_{state}")
    if is_day(game) and settlement.kind in ("town", "city") and game.moment.weekday in MARKET_DAYS:
        pools.append("moments_market")
    lines = [line for pool in pools for line in text.get(pool, [])]
    if not lines:
        return ""
    rng = game.world.rng.child(f"moment/{settlement.id}/{game.world.time}/{game.player.steps}")
    return rng.choice(lines)


def describe_npc(game, npc: NPC) -> str:
    """For looking at someone."""
    who = f"<name>{npc.first_name}</>, the {npc.title}" if npc.known else f"The {npc.title}"
    mood = "" if not npc.met else f" <dim>({npc.mood()})</>"
    return f"{who}{mood}. {npc.profile.get('appearance', '')}"
