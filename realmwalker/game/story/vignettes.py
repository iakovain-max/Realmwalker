"""Vignettes (Expansion 6 C.9, docs/ADVENTURES.md §5.16, §6.11): small stories written by hand, each needing particular
things in the world, so that they turn up seldom and feel made.

A vignette is a predicament (situations.json `predicaments`, the fragment `situations.vignettes.json`) with a
`vignette` block {needs, weight?}. It is never forged from the ordinary roots: its need (`NEEDS`, by name) looks in
the world around a town for what the story is about (a ruin by the water, a young man buried here, a tower whose
master is dead, a dragon near) and gives a root of kind "vignette" that names it:

    {"kind": "vignette", "key": "vignette:<id>", "vignette": id, "weight", "roles": {role: entry}, "words": {key: text},
     ...refs (scar)}

The predicament's roles take what the root found with `"bind": "given"` (an entry: a townsperson, a site, a figure)
and bind the rest as any predicament does; the root's `words` are kept on the situation (`sit["words"]`), so every
line may name the ruin, the dead, the blade. Each vignette is met once a world (`used`), at most one is live near the
hero, and only a share of forgings look for them at all (situations.json `vignettes` {share, near}). Its meetings are
its own scenes (scenes.vignettes.json), played like any meeting.

    roots(game, s, rng) -> [root]       find(game, s, vid) -> root | None (the root its need finds here, for tests)
    is_vignette(spec)   vignettes(tables)   problems(tables)
"""

from __future__ import annotations

NEEDS: dict[str, object] = {}
WEAPONS = ("sword", "axe", "spear", "hammer", "mace", "dagger", "bow", "blade", "glaive", "falchion")


def need(name: str):
    """fn(game, s, rng) -> (roles, words, refs) or None: what this vignette is about, found around the town."""
    def wrap(fn):
        NEEDS[name] = fn
        return fn
    return wrap


def is_vignette(spec: dict) -> bool:
    return bool(spec.get("vignette"))


def vignettes(tables) -> dict:
    from realmwalker.game.story.situations import predicaments

    return {k: v for k, v in predicaments(tables).items() if is_vignette(v)}


def _rules(game) -> dict:
    from realmwalker.game.story.situations import data

    r = data(game).get("vignettes") or {}
    return {"share": float(r.get("share", 0.35)), "near": int(r.get("near", 1))}


def used(game, vid: str) -> bool:
    """A vignette is met once a world (any life's)."""
    from realmwalker.game.story.situations import records

    return any(s.get("predicament") == vid for s in records(game.world).values())


def _live_near(game) -> int:
    from realmwalker.game.story import goals
    from realmwalker.game.story.situations import predicaments

    preds = predicaments(game.tables)
    return sum(1 for s in goals.live(game) if is_vignette(preds.get(s.get("predicament"), {}))
               and goals.within_reach(game, s))


def roots(game, s, rng) -> list[dict]:
    """The vignettes whose needs hold around this town, as roots (none on most forgings: they are rare)."""
    vs = vignettes(game.tables)
    r = _rules(game)
    if not vs or _live_near(game) >= r["near"] or not rng.chance(r["share"]):
        return []
    out = []
    for vid in sorted(vs):
        root = find(game, s, vid)
        if root is not None:
            out.append(root)
    return out


def find(game, s, vid: str) -> dict | None:
    """The root this vignette's need finds around the town, or None (not here, or met already in this world)."""
    spec = vignettes(game.tables).get(vid)
    fn = NEEDS.get((spec or {}).get("vignette", {}).get("needs", ""))
    if fn is None or used(game, vid):
        return None
    got = fn(game, s, game.world.rng.child(f"vignette/{vid}/{s.id}"))
    if got is None:
        return None
    roles, words, refs = got
    return dict(refs, kind="vignette", key=f"vignette:{vid}", vignette=vid,
                weight=float(spec["vignette"].get("weight", 2.0)), roles=roles, words=words)


# ---------------------------------------------------------------------------- what the needs look at
def _year(game) -> int:
    return int(game.moment.year)


def _years(n: int) -> str:
    n = max(1, int(n))
    return "a year" if n == 1 else f"{n} years"


def _free(game, n, child: bool = False) -> bool:
    from realmwalker.game.story.situations import _free as free

    return free(game, {"roles": {}}, n, child)


def _entry(n) -> dict:
    return {"npc": int(n.id), "settlement": int(n.settlement), "job": n.job}


def _site_entry(x) -> dict:
    return {"site": int(x.id), "place": {"site": int(x.id)}, "name": x.name}


def _folk(game, s, jobs=None, child: bool = False, sex: str | None = None, age=(16, 200)) -> list:
    from realmwalker.game.people import npcs_in

    out = [n for n in npcs_in(game.world, s.id) if _free(game, n, child) and age[0] <= n.age <= age[1]
           and (jobs is None or n.job in jobs) and (sex is None or n.sex == sex)
           and (child or n.job not in ("guard", "visitor"))]
    return sorted(out, key=lambda n: n.id)


def _oldest(game, s, at_least: int = 0):
    folk = [n for n in _folk(game, s) if n.age >= at_least]
    return max(folk, key=lambda n: (n.age, -n.id)) if folk else None


def _sites(game, s, lo: int, hi: int, kinds=None) -> list:
    from realmwalker.game.quests import dist

    return sorted((x for x in game.world.sites if lo <= dist(x, s) <= hi and (kinds is None or x.kind in kinds)),
                  key=lambda x: (dist(x, s), x.id))


def _events_here(game, s, kinds) -> list[dict]:
    return [e for e in game.world.history if e.get("kind") in kinds and s.id in (e.get("places") or [])]


def _dead_figures(game, s, here_only: bool = True) -> list:
    ref = f"S{s.id}"
    return sorted((f for f in game.world.figures.values() if f.kind == "person" and not f.alive
                   and (ref in (f.home, f.died_at, f.buried) or not here_only)), key=lambda f: f.id)


def _water(game, s, r: int = 2):
    """The river or lake by the town: its name ("the river" if it has none), or None."""
    w = game.world
    lake = w.biome_ids.index("lake") if "lake" in w.biome_ids else -1
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            x, y = s.x + dx, s.y + dy
            if not (0 <= x < w.width and 0 <= y < w.height):
                continue
            if int(w.river[x, y]) >= 2:
                a = w.river_at(x, y)
                return a.name if a is not None and a.name else "the river"
            if int(w.biome[x, y]) == lake:
                return "the lake"
    return None


def _ruins(game, s, lo: int, hi: int) -> list[tuple]:
    """Ruins of the history near the town: (site, its record)."""
    rec = game.world.politics.get("ruins") or {}
    return [(x, rec[str(x.id)]) for x in _sites(game, s, lo, hi) if str(x.id) in rec and rec[str(x.id)].get("fell")]


FELL_BY = ("burned", "razed", "destroyed", "sacked", "taken", "emptied", "abandoned", "drowned", "buried", "swallowed")


def _ruin_words(game, x, r: dict) -> dict:
    """{ruin} (its name now), {ruin_was} (the hamlet of...), {ruin_cause} (as the history says it), {ruin_fall} (a
    clause: "it was burned by the Split Claw tribe", "the Long Winter came"), {ruin_years}."""
    cause = r.get("cause") or "the years"
    fall = f"it was {cause}" if cause.split()[0] in FELL_BY else f"{cause} came"
    return {"ruin": x.name, "ruin_was": r.get("was") or x.name, "ruin_cause": cause, "ruin_fall": fall,
            "ruin_years": _years(_year(game) - int(r["fell"]))}


# ---------------------------------------------------------------------------- the needs
@need("ruin_by_water")
def _ruin_by_water(game, s, rng):
    """A town by a river or a lake, a ruin of the history within a day or two, and an old one who remembers."""
    water = _water(game, s)
    ruins = _ruins(game, s, 2, 14)
    keeper = _oldest(game, s, 45)
    if water is None or not ruins or keeper is None:
        return None
    x, r = ruins[0]
    return ({"keeper": _entry(keeper), "ruin": _site_entry(x)}, dict(_ruin_words(game, x, r), water=water), {})


@need("young_dead_here")
def _young_dead_here(game, s, rng):
    """A young man of the history who lived, died or lies buried here, and a girl of the town of an age to marry."""
    yr = _year(game)
    dead = [f for f in _dead_figures(game, s) if f.sex == "male" and f.died - f.born <= 32 and yr - f.died <= 200]
    brides = _folk(game, s, sex="female", age=(16, 24))
    if not dead or not brides:
        return None
    f, b = dead[-1], rng.choice(brides)
    return ({"bride": _entry(b), "dead": {"figure": int(f.id), "name": f.full_name()}},
            {"dead_name": f.name, "dead_first": f.first_name, "dead_years": _years(yr - f.died),
             "dead_cause": f.cause or "young"}, {})


@need("bridge")
def _bridge(game, s, rng):
    """A road over a river by the town, and the town's founding in the history (the riddles' answers)."""
    w = game.world
    river = None
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            x, y = s.x + dx, s.y + dy
            if 0 <= x < w.width and 0 <= y < w.height and bool(w.road[x, y]) and int(w.river[x, y]) >= 1:
                a = w.river_at(x, y)
                river = a.name if a is not None and a.name else "the river"
                break
        if river:
            break
    founded = _events_here(game, s, ("settled", "founded_town"))
    asker = _folk(game, s, jobs=("carter", "market_trader", "shopkeeper", "farmer", "herder", "porter"))
    if river is None or not founded or not asker:
        return None
    e = founded[0]
    return ({"asker": _entry(rng.choice(asker))},
            {"river": river, "founded_years": _years(_year(game) - int(e["year"])), "founding": e["text"]}, {})


@need("smith_and_blade")
def _smith_and_blade(game, s, rng):
    """A smith of the town, a blade of the history (lost, or held far away), and a place out in the land for the
    star-iron."""
    w = game.world
    smiths = _folk(game, s, jobs=("smith",))
    arts = [a for a in (w.politics.get("artifacts") or []) if isinstance(a, dict) and a.get("kind") in WEAPONS]
    lode = _sites(game, s, 3, 16, kinds=("cave", "ruin"))
    if not smiths or not arts or not lode:
        return None
    smith = smiths[0]
    same = [a for a in arts if (w.figures.get(a.get("maker", -1)) or smith).culture == smith.culture] or arts
    a = same[0]
    maker = w.figures.get(a.get("maker", -1))
    return ({"smith": _entry(smith), "lode": _site_entry(lode[0])},
            {"blade": a["name"], "blade_maker": maker.name if maker is not None else "a smith of old",
             "blade_years": _years(_year(game) - int(a.get("made", _year(game) - 300))),
             "blade_material": a.get("material") or "old iron", "blade_fate": a.get("fate") or "is lost"}, {})


@need("hunger_here")
def _hunger_here(game, s, rng):
    """A village that has known famine (in its history, or now) and keeps a barn of grain; its reeve and its poor."""
    from realmwalker.world import factions as fx

    if s.kind not in ("hamlet", "village", "town"):
        return None
    realm = fx.realm_of_settlement(game.world, s)
    lords = {s.owner} | ({realm.id} if realm is not None else set())
    hunger = [e for e in game.world.history if e.get("kind") == "famine" and
              (s.id in (e.get("places") or []) or lords & set(e.get("factions") or []))]
    if not hunger and not s.status.get("famine"):
        return None
    reeve = next(iter(_folk(game, s, jobs=("headman", "elder", "lord"))), None)
    poor = _folk(game, s, jobs=("labourer", "farmer", "beggar", "herder", "woodcutter", "carter"))
    if reeve is None or not poor:
        return None
    year = int(hunger[-1]["year"]) if hunger else _year(game)
    return ({"reeve": _entry(reeve), "culprit": _entry(rng.choice(poor))},
            {"famine_years": _years(_year(game) - year)}, {})


@need("temple_saint")
def _temple_saint(game, s, rng):
    """A priest of the town, and a holy one of the history who lived or lies here (or of the town's own people)."""
    priests = _folk(game, s, jobs=("priest", "preacher", "monk"))
    if not priests:
        return None
    holy = [f for f in _dead_figures(game, s) if f.job in ("priest", "preacher", "monk") or f.cls == "cleric"]
    if not holy:
        holy = [f for f in _dead_figures(game, s, here_only=False) if (f.job in ("priest", "preacher", "monk")
                or f.cls == "cleric") and f.culture == s.culture and f.fame > 0]
    if not holy:
        return None
    f = max(holy, key=lambda f: (f.fame, -f.id))
    return ({"priest": _entry(priests[0]), "saint": {"figure": int(f.id), "name": f.full_name()}},
            {"saint": f.name, "saint_years": _years(_year(game) - int(f.died))}, {})


@need("gallows_scar")
def _gallows_scar(game, s, rng):
    """A field of the history's dead near the town (a massacre, a battle) not yet laid, and an old one who goes there."""
    scars = [(i, sc) for i, sc in enumerate(game.world.politics.get("scars") or ()) if isinstance(sc, dict)
             and not sc.get("laid") and max(abs(int(sc.get("x", -99)) - s.x), abs(int(sc.get("y", -99)) - s.y)) <= 8]
    asker = _oldest(game, s, 40)
    if not scars or asker is None:
        return None
    scars.sort(key=lambda p: (p[1].get("kind") != "massacre", p[0]))
    i, sc = scars[0]
    return ({"asker": _entry(asker)},
            {"scar": sc.get("name") or "the old field", "scar_years": _years(_year(game) - int(sc.get("year", 0))),
             "scar_dead": str(int(sc.get("dead", 40)))}, {"scar": i})


@need("fallen_hero")
def _fallen_hero(game, s, rng):
    """A hero of this world fell out in the land near here (one of the player's own past lives first); a child of the
    town has a map they drew."""
    from realmwalker.game.quests import dist

    w = game.world
    place, hero, years = None, None, None
    for rec in reversed(w.politics.get("fallen") or []):
        fx, fy = int(rec.get("x", -99)), int(rec.get("y", -99))
        near = sorted((x for x in w.sites if max(abs(x.x - fx), abs(x.y - fy)) <= 3), key=lambda x: x.id)
        if near and dist(near[0], s) <= 20:
            place, hero, years = near[0], rec.get("name"), _years(_year(game) - int(rec.get("year", _year(game))))
            break
    if place is None:
        for f in _dead_figures(game, s, here_only=False):
            if f.role not in ("hero", "legend") or not str(f.died_at).startswith("X"):
                continue
            x = w.sites[int(f.died_at[1:])] if int(f.died_at[1:]) < len(w.sites) else None
            if x is not None and dist(x, s) <= 20:
                place, hero, years = x, f.full_name(), _years(_year(game) - int(f.died))
                break
    children = _folk(game, s, child=True, age=(6, 14))
    keeper = next(iter(_folk(game, s, jobs=("priest", "monk", "headman", "elder", "innkeeper"))), None)
    if place is None or not children or keeper is None:
        return None
    return ({"child": _entry(rng.choice(children)), "keeper": _entry(keeper), "place": _site_entry(place)},
            {"hero": hero or "a wanderer", "hero_years": years or "some years"}, {})


@need("lord_and_heir")
def _lord_and_heir(game, s, rng):
    """A lord of a town who is a figure of the history, with a house's old wrong behind him (a grudge if the history
    keeps one)."""
    w = game.world
    if s.kind not in ("town", "city", "hold"):
        return None
    lords = [n for n in _folk(game, s, jobs=("lord", "headman")) if n.flags.get("figure") is not None]
    if not lords:
        return None
    lord = lords[0]
    fig = w.figures.get(lord.flags["figure"])
    g = next((g for g in w.politics.get("grudges") or () if fig is not None and g.get("against") == fig.id), None)
    wrong = g.get("cause") if g else "an old wrong between two houses"
    return ({"lord": _entry(lord)}, {"wrong": wrong, "house": (fig.family if fig is not None and fig.family else
                                                                lord.name.split()[-1])}, {})


@need("plague_past")
def _plague_past(game, s, rng):
    """A small place that lost many to a plague in its history; a child, and the one who leads it."""
    if s.kind not in ("hamlet", "village"):
        return None
    plague = _events_here(game, s, ("plague",))
    children = _folk(game, s, child=True, age=(6, 13))
    elder = next(iter(_folk(game, s, jobs=("headman", "elder", "priest"))), None)
    if not plague or not children or elder is None:
        return None
    e = max(plague, key=lambda e: int((e.get("data") or {}).get("deaths", 0)))
    return ({"child": _entry(rng.choice(children)), "elder": _entry(elder)},
            {"plague_years": _years(_year(game) - int(e["year"])),
             "plague_dead": str(int((e.get("data") or {}).get("deaths", 30)))}, {})


@need("masterless_tower")
def _masterless_tower(game, s, rng):
    """A wizard's tower out in the land whose master the history saw die."""
    w = game.world
    towers = w.politics.get("towers") or {}
    for x in _sites(game, s, 3, 20, kinds=("tower",)):
        f = w.figures.get(towers.get(str(x.id), -1))
        if f is not None and not f.alive:
            return ({"tower": _site_entry(x)}, {"master": f.full_name(), "master_first": f.first_name,
                                                "master_years": _years(_year(game) - int(f.died))}, {})
    return None


@need("dragon_near")
def _dragon_near(game, s, rng):
    """A living dragon whose lair is within a few days of the town; someone young of the town, and its headman."""
    from realmwalker.game.quests import dist

    w = game.world
    for d in w.politics.get("dragons") or ():
        lair = d.get("lair")
        if not d.get("alive") or lair is None or not 0 <= int(lair) < len(w.sites) or \
                dist(w.sites[int(lair)], s) > 30:
            continue
        young = _folk(game, s, age=(15, 21))
        head = next(iter(_folk(game, s, jobs=("headman", "elder", "lord"))), None)
        if not young or head is None:
            return None
        return ({"chosen": _entry(rng.choice(young)), "headman": _entry(head), "lair": _site_entry(w.sites[int(lair)])},
                {"dragon": d.get("name") or "the dragon", "dragon_colour": d.get("color") or "old"}, {})
    return None


@need("beast_lair")
def _beast_lair(game, s, rng):
    """A named beast of the history alive in its lair near the town; someone it made a widow or a widower."""
    w = game.world
    lairs = w.politics.get("lairs") or {}
    for x in _sites(game, s, 3, 20):
        f = w.figures.get(lairs.get(str(x.id), -1))
        if f is None or not f.alive:
            continue
        left = _folk(game, s, age=(22, 70))
        if not left:
            return None
        return ({"widow": _entry(rng.choice(left)), "lair": _site_entry(x), "beast": {"figure": int(f.id),
                                                                                       "name": f.full_name()}},
                {"beast": f.full_name()}, {})
    return None


@need("barrow_near")
def _barrow_near(game, s, rng):
    """A barrow of the history near the fields (its king in the tomb records), and someone who found a ring there."""
    w = game.world
    tombs = w.politics.get("tombs") or {}
    for x in _sites(game, s, 2, 12):
        f = w.figures.get(tombs.get(str(x.id), -1))
        if f is None:
            continue
        finder = _folk(game, s, jobs=("farmer", "labourer", "herder", "woodcutter", "carter"))
        if not finder:
            return None
        return ({"finder": _entry(rng.choice(finder)), "barrow": _site_entry(x)},
                {"barrow_king": f.full_name(), "king_years": _years(_year(game) - int(f.died or _year(game) - 300))},
                {})
    return None


@need("ruin_survivor")
def _ruin_survivor(game, s, rng):
    """A place the history ruined within a lifetime, and someone old enough to have lived there as a child."""
    yr = _year(game)
    for x, r in _ruins(game, s, 2, 20):
        ago = yr - int(r["fell"])
        if ago > 75:
            continue
        old = [n for n in _folk(game, s) if n.age >= ago + 8]
        if not old:
            continue
        return ({"survivor": _entry(max(old, key=lambda n: (n.age, -n.id))), "ruin": _site_entry(x)},
                _ruin_words(game, x, r), {})
    return None


@need("founder")
def _founder(game, s, rng):
    """The town's founding in the history, and a poor soul who says the founder's blood is theirs."""
    founded = _events_here(game, s, ("settled", "founded_town", "founded_lordship"))
    poor = _folk(game, s, jobs=("beggar", "labourer", "washerwoman", "porter", "serving_hand"))
    head = next(iter(_folk(game, s, jobs=("headman", "lord", "elder"))), None)
    if not founded or not poor or head is None:
        return None
    e = founded[0]
    return ({"claimant": _entry(rng.choice(poor)), "notable": _entry(head)},
            {"founding": e["text"], "founded_years": _years(_year(game) - int(e["year"]))}, {})


@need("book_about_here")
def _book_about_here(game, s, rng):
    """A book of the history written about this town or its people (a chronicle, a history), and a family it wrongs."""
    w = game.world
    works = [x for x in w.politics.get("works") or () if isinstance(x, dict) and
             (x.get("place") == f"S{s.id}" or (x.get("about") or {}).get("settlement") == s.id)]
    if not works:
        return None
    keeper = next(iter(_folk(game, s, jobs=("scribe", "priest", "monk", "headman", "elder", "lord"))), None)
    wronged = [n for n in _folk(game, s, age=(30, 90)) if keeper is None or n.id != keeper.id]
    if keeper is None or not wronged:
        return None
    b = works[0]
    author = w.figures.get(b.get("author", -1))
    return ({"wronged": _entry(rng.choice(wronged)), "keeper": _entry(keeper)},
            {"book": b.get("title") or "the chronicle", "author": author.name if author is not None else "a scribe",
             "book_years": _years(_year(game) - int(b.get("year", _year(game))))}, {})


@need("holy_road")
def _holy_road(game, s, rng):
    """A holy place of the history a few days off (a temple raised, a church founded, pilgrims' road), and a sick
    pilgrim lodged here on the way."""
    from realmwalker.game.quests import dist

    w = game.world
    kinds = ("temple_raised", "church_founded", "pilgrimage")
    holy = sorted({p for e in w.history if e.get("kind") in kinds for p in (e.get("places") or [])
                   if p != s.id and 0 <= p < len(w.settlements) and 5 <= dist(w.settlements[p], s) <= 30})
    if not holy or not any(n.job == "innkeeper" for n in _folk(game, s)):
        return None
    dest = min((w.settlements[p] for p in holy), key=lambda x: (dist(x, s), x.id))
    return ({}, {"shrine": dest.name}, {"settlement": int(dest.id)})


@need("death_at_the_inn")
def _death_at_the_inn(game, s, rng):
    """An inn, and someone of the history who died in this town by another's hand (or nobody ever knew whose)."""
    inn = _folk(game, s, jobs=("innkeeper",))
    if not inn:
        return None
    yr = _year(game)
    killed = [f for f in _dead_figures(game, s) if f.died_at == f"S{s.id}" and yr - f.died <= 250 and
              any(w in (f.cause or "") for w in ("murder", "slain", "poison", "knife", "killed", "stabbed", "strangl"))]
    if not killed:
        unknown = _events_here(game, s, ("assassination_unknown",))
        figs = [game.world.figures.get(i) for e in unknown for i in e.get("figures") or []]
        killed = [f for f in figs if f is not None and not f.alive]
    if not killed:
        return None
    f = killed[-1]
    return ({"innkeeper": _entry(inn[0]), "dead": {"figure": int(f.id), "name": f.full_name()}},
            {"dead_name": f.name, "dead_years": _years(yr - int(f.died)), "dead_cause": f.cause or "by a hand unknown"},
            {})


@need("persecution")
def _persecution(game, s, rng):
    """A faith persecuted here in the history; a house that still keeps its book, and a priest of the faith now kept."""
    old = _events_here(game, s, ("persecution", "heresy"))
    priests = _folk(game, s, jobs=("priest", "preacher", "monk"))
    keepers = [n for n in _folk(game, s, age=(25, 90)) if n.job not in ("priest", "preacher", "monk", "lord")]
    if not old or not priests or not keepers:
        return None
    e = old[-1]
    return ({"keeper": _entry(rng.choice(keepers)), "priest": _entry(priests[0])},
            {"old_wrong": e["text"], "wrong_years": _years(_year(game) - int(e["year"]))}, {})


# ---------------------------------------------------------------------------- the start-up check
def problems(tables) -> list[str]:
    out = []
    for vid, spec in vignettes(tables).items():
        v = spec["vignette"]
        if v.get("needs") not in NEEDS:
            out.append(f"situations: vignette {vid} needs '{v.get('needs')}', which is not a need "
                       f"({', '.join(sorted(NEEDS))})")
        for m in spec.get("meetings", []):
            if not m.startswith("v_"):
                out.append(f"situations: vignette {vid} meets as '{m}': a vignette's meetings are its own (v_...)")
        if not any(rs.get("bind") == "given" for rs in spec.get("roles", {}).values()) and v.get("needs") != "holy_road":
            out.append(f"situations: vignette {vid} binds no role to what its need finds (\"bind\": \"given\")")
    return out
