"""Situations (Expansion 6 Part C, docs/ADVENTURES.md §5.16, §6.7-6.10, §8.10): small stories about real people,
forged from the world and met in a scene.

A situation is a record in `world.politics["situations"]` (goals.situations), world-side like an adventure:

    {"id": "Q3", "town": sid, "root": {"kind", "key", ...refs}, "predicament": pid,
     "roles": {role: {"npc", "settlement", "job"} | {"band", "faction", "site", "name", "state"} | {"site", "place"}
               | {"threat"} | {"figure"}},
     "stakes": {"what"}, "clock": {"due": day, "half": bool}, "goals": [{"id", "test", "reached"?, "way"?}],
     "obstacles": [{"id", "kind", "who", "acts", "spells", "state"}], "turn": {"id", "state"} | None,
     "meeting": {"kind", "state"}, "state", "ways": [...], "flags": [...], "used": [act ids], "quest": id | None,
     "threat": tid | None, "adventure": None, "ending": None, "tone", "made": day, "met": day, "life": hero's life,
     "words": {...}, "journal": [lines]}

States: `latent` (forged; its meeting waits for the hero in its town) -> `met` (seen: in the journal's Troubles) ->
`taken` (the hero said they would help) -> `done` / `failed`, or `lapsed` (the clock ran out without the hero, and the
world's own outcome happened).

Forging (`make`): only in towns that have their people, when the town's gap has passed (`due_here`); a root gathered
from the town (`ROOTS`: lives' seeds and secrets, threats at its door, the realm's war or plague, the bands and
temples near, the history's grudges and scars, the land, a companion from here), a predicament its root can make
(situations.json `roots`), weighted down by what this hero has met; roles bound to real people (`BINDS`; a kin who is
only a name becomes a person now); obstacles, at most one turn (`turns`), a meeting (`meetings`, played as a scene of
scenes.json), the clock, and words written once.

Play: the meeting's scene opens a conversation with the one who asks; `talk_choices` give the take and refuse, and
the obstacles' acts (a check, a price, a truth needed: `do_act`); a predicament may set work (`WORKS`: a quest made
through `quests.make` for its real target). Goals are goals.py tests; when one is reached (`goals.REACTIONS`) the first
ending whose `when` and `if` hold is played (`finish`): its people ops (`OPS`) write the outcome into the world. A
clock run out plays the predicament's `lapse` (law 7). When the hero dies (`on_death`) live situations lose their
work and go back to latent, keeping their clocks.

    make(game, sid, root=None, predicament=None)   due_here(game, s)   maybe_forge(game, s=None)
    daily(game)   on_enter_town(game, s)   on_tick(game, lm, s)   talk_choices(conv)   talk_choose(conv, choice)
    take(game, sit)   finish(game, sit, ending)   on_quest_end(game, q, ok)   on_magic(game, spell)   on_death(game)
    troubles(game)   journal_lines(game, sit)   problems(tables)
"""

from __future__ import annotations

import copy

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story import goals

LIVE = goals.LIVE
ENDED = ("done", "failed", "lapsed")
CHOICES = {"sit_ask", "sit_take", "sit_refuse", "sit_act"}
TONES = ("good", "mixed", "bitter")
CONDS = ("goal", "way", "flag", "knows", "turn", "not", "taken", "refused", "work_done", "work_failed", "holds")
WHEN = ("forge", "meet", "take", "half", "end")
WORK_WAYS = {"rescue": "fight", "retrieve": "fight", "deliver": "talk", "cure": "talk", "feud": "talk",
             "assassinate": "fight", "collect_debt": "talk", "clear_lair": "fight", "bounty": "fight"}
CHECK_SKILLS = ("persuasion", "intimidation", "deception", "insight", "investigation", "medicine", "religion",
                "arcana", "history", "performance", "nature", "survival", "animal_handling", "sleight_of_hand")


def data(game) -> dict:
    return getattr(game.tables, "situations", None) or {}


def predicaments(tables) -> dict:
    return {k: v for k, v in ((getattr(tables, "situations", None) or {}).get("predicaments") or {}).items()
            if not k.startswith("_")}


def records(world) -> dict:
    return goals.situations(world)


def spec_of(game, sit: dict) -> dict:
    return predicaments(game.tables).get(sit["predicament"], {})


def _today(game) -> int:
    return int(game.moment.total_days)


def _life(game) -> str:
    from realmwalker.game.story.forge import life_of

    return life_of(game)


def _rarity(game) -> dict:
    r = data(game).get("rarity") or {}
    return {"gap": r.get("gap", [10, 20]), "per_town": int(r.get("per_town", 1)), "per_great": int(r.get("per_great", 2)),
            "near": int(r.get("near", 3)), "first": r.get("first", [0, 3]), "turn_chance": float(r.get("turn_chance", 0.5))}


def _npc(game, sit: dict, role: str):
    rec = sit["roles"].get(role) or {}
    return game.world.npcs.get(int(rec["npc"])) if rec.get("npc") is not None else None


def _role_of(sit: dict, npc) -> str | None:
    for role, rec in sit["roles"].items():
        if rec.get("npc") is not None and int(rec["npc"]) == npc.id:
            return role
    return None


# ---------------------------------------------------------------------------- rarity
def _dist(game, s) -> int:
    return max(abs(s.x - game.player.x), abs(s.y - game.player.y))


def _reach(game) -> int:
    from realmwalker.game.story import lives

    return int((lives.data(game) or {}).get("reach", 30))


def live_in(game, sid: int) -> list[dict]:
    return [s for s in goals.live(game) if s.get("town") == sid]


def live_near(game) -> list[dict]:
    return [s for s in goals.live(game) if goals.within_reach(game, s)]


def own(sits: list[dict]) -> list[dict]:
    """The towns' own troubles: an adventure's situations are its steps, outside the rarity rules (C.10)."""
    return [x for x in sits if not x.get("adventure")]


def _limit(s) -> int:
    return 2 if getattr(s, "great", False) else 1


def due_here(game, s) -> bool:
    """Whether a situation may be forged in this town now: it has its people, has fewer live than it may hold (one, two
    in a great city), its gap has passed, and fewer than three are live within reach of the hero."""
    town = game.world.towns.get(s.id)
    if town is None or not town.npcs or _dist(game, s) > _reach(game):
        return False
    r = _rarity(game)
    if len(own(live_in(game, s.id))) >= (r["per_great"] if _limit(s) > 1 else r["per_town"]):
        return False
    if len(own(live_near(game))) >= r["near"]:
        return False
    nxt = town.flags.get("sit_next")
    return nxt is None or _today(game) >= int(nxt)


def _next_gap(game, s, rng, first: bool = False) -> None:
    town = game.world.towns.get(s.id)
    if town is not None:
        lo, hi = _rarity(game)["first" if first else "gap"]
        town.flags["sit_next"] = _today(game) + rng.randint(int(lo), int(hi))


def maybe_forge(game, s=None) -> dict | None:
    """Forge one situation in this town (on entering it) or in the nearest town near the hero that is due (daily)."""
    w = game.world
    if not predicaments(game.tables):
        return None
    towns = [s] if s is not None else sorted(
        (w.settlements[sid] for sid, t in w.towns.items() if t.npcs and 0 <= sid < len(w.settlements)),
        key=lambda x: (_dist(game, x), x.id))
    for town in towns:
        if not due_here(game, town):
            continue
        sit = make(game, town.id)
        if sit is None:
            game.world.towns[town.id].flags["sit_next"] = _today(game) + 3  # (nothing fits now: look again soon)
            continue
        return sit
    return None


# ---------------------------------------------------------------------------- roots
ROOTS: dict[str, object] = {}


def root(kind: str):
    """fn(game, s, rng) -> [root dicts with "kind", "key" and their refs] for this town"""
    def wrap(fn):
        ROOTS[kind] = fn
        return fn
    return wrap


@root("life")
def _life_roots(game, s, rng) -> list[dict]:
    """The town's life events marked as story seeds, newest first; then secrets kept in its lives."""
    from realmwalker.game.people import npcs_in
    from realmwalker.game.story import lives

    out = [{"kind": "life", "key": f"life:{ev['kind']}", "npc": nid, "event": int(ev["day"]), "weight": 3.0,
            "name": ev.get("name") if ev["kind"] == "death_of_age" else None}
           for nid, ev in lives.seeds(game, s.id)]
    for n in npcs_in(game.world, s.id):
        lf = n.flags.get("life") if n.alive else None
        for sec in (lf or {}).get("secrets", []):
            if not sec.get("known"):
                out.append({"kind": "life", "key": f"life:secret_{sec['kind']}", "npc": n.id, "weight": 1.0})
    return out


@root("threat")
def _threat_roots(game, s, rng) -> list[dict]:
    from realmwalker.world import threats

    return [{"kind": "threat", "key": "threat", "threat": t["id"], "weight": 2.0}
            for t in threats.live(game.world) if s.id in t["stakes"][:6]]


@root("politics")
def _politics_roots(game, s, rng) -> list[dict]:
    from realmwalker.world import factions as fx
    from realmwalker.world.politics import at_war

    out = []
    realm = fx.realm_of_settlement(game.world, s)
    if realm is not None and at_war(game.world, realm.id):
        out.append({"kind": "politics", "key": "politics:war", "faction": realm.id, "weight": 1.5})
    if s.status.get("plague") or s.status.get("famine"):
        out.append({"kind": "politics", "key": "politics:plague", "weight": 1.5})
    return out


@root("faction")
def _faction_roots(game, s, rng) -> list[dict]:
    from realmwalker.game.people import npcs_in
    from realmwalker.game.quests import cleared, dist
    from realmwalker.world import factions as fx

    w = game.world
    out, done = [], cleared(game)
    for f in fx.active_factions(w, "bandit_gang", "cult"):
        if 0 <= f.site < len(w.sites) and f.site not in done and dist(w.sites[f.site], s) <= 22:
            out.append({"kind": "faction", "key": f"faction:{f.kind}", "faction": f.id, "weight": 1.0})
    if any(n.alive and n.job in ("priest", "preacher", "monk") for n in npcs_in(w, s.id)):
        out.append({"kind": "faction", "key": "faction:temple", "weight": 0.7})
    return out


@root("history")
def _history_roots(game, s, rng) -> list[dict]:
    from realmwalker.game import past
    from realmwalker.game.people import npcs_in

    w = game.world
    out = []
    for n in npcs_in(w, s.id):
        fig = w.figures.get(n.flags.get("figure", -1)) if n.alive else None
        if fig is not None and past.grudge_of(w, fig.id) is not None:
            out.append({"kind": "history", "key": "history:grudge", "npc": n.id, "figure": fig.id, "weight": 1.5})
    for sc in w.politics.get("scars", ()):
        if isinstance(sc, dict) and not sc.get("laid") and max(abs(int(sc.get("x", -99)) - s.x),
                                                               abs(int(sc.get("y", -99)) - s.y)) <= 8:
            out.append({"kind": "history", "key": "history:scar", "weight": 1.0})
            break
    return out


@root("land")
def _land_roots(game, s, rng) -> list[dict]:
    from realmwalker.game.quests import dist

    near = [x for x in game.world.sites if 3 <= dist(x, s) <= 16]
    return [{"kind": "land", "key": "land", "weight": 0.6}] if near else []


@root("companion")
def _companion_roots(game, s, rng) -> list[dict]:
    w = game.world
    out = []
    for c in game.party[1:]:
        nid = (c.companion or {}).get("npc")
        n = w.npcs.get(nid) if nid is not None else None
        if n is not None and n.settlement == s.id:
            out.append({"kind": "companion", "key": "companion", "companion": c.name, "weight": 1.0})
    return out


@root("vignette")
def _vignette_roots(game, s, rng) -> list[dict]:
    """The hand-made stories whose needs hold here (story/vignettes.py): seldom, and each once a world."""
    from realmwalker.game.story import vignettes

    return vignettes.roots(game, s, rng)


def gather_roots(game, s, rng) -> list[dict]:
    out = []
    for fn in ROOTS.values():
        out.extend(fn(game, s, rng))
    return out


# ---------------------------------------------------------------------------- binding roles
BINDS: dict[str, object] = {}
ADULT_NOT = ("child", "guard", "visitor")


def bind(kind: str):
    """fn(game, s, sit, spec, rng) -> a role record or None (the predicament cannot be cast here)"""
    def wrap(fn):
        BINDS[kind] = fn
        return fn
    return wrap


def _free(game, sit: dict, n, child: bool = False) -> bool:
    """Someone a new role may take: alive, here, not another story's, not already in this one, not on a journey."""
    f = n.flags
    if not n.alive or f.get("story") or f.get("visitor") or f.get("companion") or f.get("escort") is not None:
        return False
    if f.get("gone") or f.get("moved_on") or f.get("captive") or f.get("with_party") or \
            f.get("law") in ("accused", "jailed", "hanged"):
        return False
    if n.job in ("wayfarer", "adventurer", "pilgrim") or (n.job == "child") != child:
        return False
    return not any(r.get("npc") == n.id for r in sit["roles"].values())


def _entry(n) -> dict:
    return {"npc": int(n.id), "settlement": int(n.settlement), "job": n.job}


def _folk(game, s, sit, jobs=None, child: bool = False) -> list:
    from realmwalker.game.people import npcs_in

    out = [n for n in npcs_in(game.world, s.id) if _free(game, sit, n, child)]
    if jobs:
        out = [n for n in out if n.job in jobs]
    return sorted(out, key=lambda n: n.id)


@bind("root")
def _bind_root(game, s, sit, spec, rng):
    n = game.world.npcs.get(sit["root"].get("npc", -1))
    if n is None or n.settlement != s.id or not _free(game, sit, n, n.job == "child"):
        return None
    if spec.get("root_jobs") and n.job not in spec["root_jobs"]:
        return None
    return _entry(n)


@bind("given")
def _bind_given(game, s, sit, spec, rng):
    """What a vignette's need found for this role (story/vignettes.py): a townsperson, a site, a figure."""
    entry = (sit["root"].get("roles") or {}).get(spec.get("_role", ""))
    if entry is None:
        return None
    n = game.world.npcs.get(entry["npc"]) if entry.get("npc") is not None else None
    if entry.get("npc") is not None and (n is None or not (_free(game, sit, n, n.job == "child") or _of_tale(sit, n))):
        return None
    return dict(entry)


def _of_tale(sit: dict, n) -> bool:
    """Someone of the adventure this situation is a step of (their own tale's person: C.10)."""
    adv = sit["root"].get("adv")
    return bool(adv) and n.alive and (n.flags.get("story") or {}).get("adv") == adv


@bind("job")
def _bind_job(game, s, sit, spec, rng):
    for job in spec.get("jobs") or []:
        folk = _folk(game, s, sit, [job], job == "child")
        if folk:
            return _entry(rng.choice(folk))
    if spec.get("any"):
        folk = _folk(game, s, sit)
        return _entry(rng.choice(folk)) if folk else None
    return None


ROLE_JOBS = {"notable": ("headman", "lord", "elder", "innkeeper"), "watch": ("guard",),
             "priest": ("priest", "preacher", "monk", "acolyte"), "healer": ("healer", "priest", "monk"),
             "merchant": ("moneylender", "shopkeeper", "market_trader", "innkeeper", "smith")}


def _jobs_bind(kind: str):
    def fn(game, s, sit, spec, rng):
        for job in ROLE_JOBS[kind]:
            folk = _folk(game, s, sit, [job])
            if folk:
                return _entry(folk[0] if kind in ("notable", "watch") else rng.choice(folk))
        return None
    fn.__doc__ = f"A townsperson who is a {', '.join(ROLE_JOBS[kind])}."
    bind(kind)(fn)


for _k in ROLE_JOBS:
    _jobs_bind(_k)


@bind("any")
def _bind_any(game, s, sit, spec, rng):
    folk = [n for n in _folk(game, s, sit) if n.job not in ADULT_NOT and n.age >= 16]
    return _entry(rng.choice(folk)) if folk else None


def _make_person(game, s, job: str, name: str | None, sex: str | None, age: int | None, near, rng):
    """A person of the town made now (a kin who was only a name, a stranger come in): placed at `near`'s home."""
    from realmwalker.game import people

    town = people.town_of(game.world, s.id)
    home = tuple(near.home) if near is not None else (0, 0)
    npc = people.make_npc(game, s, job, rng, post=home, home=home)
    if sex:
        npc.sex = sex
    family = (near.flags.get("family") or near.name.split()[-1]) if near is not None else npc.flags.get("family")
    if name:
        npc.name = f"{name} {family}" if family else name
        npc.flags["family"] = family
    if age:
        npc.age = int(age)
    npc.x, npc.y = home
    people.add(game.world, town, npc)
    _MADE.append(npc.id)
    return npc


_MADE: list[int] = []  # (people made while one situation is forged: taken away again if it fails)
MAKES = ("kin", "tie", "stranger")


def _life_of(n) -> dict:
    """Someone's life, begun now if they had none kept (a role needs their ties)."""
    lf = n.flags.get("life")
    if lf is None:
        lf = n.flags["life"] = {"ties": [], "want": None, "fear": None, "secrets": [], "things": [], "events": []}
    return lf


KIN_JOB = {"son": "labourer", "daughter": "labourer", "brother": "labourer", "sister": "labourer",
           "husband": "labourer", "wife": "labourer", "father": "labourer", "mother": "labourer"}
KIN_SEX = {"son": "male", "brother": "male", "husband": "male", "father": "male", "daughter": "female",
           "sister": "female", "wife": "female", "mother": "female"}


def _kin_age(kind: str, of, rng, young: bool = False) -> int:
    """How old a kin is beside the one they are kin to: a parent a generation older, a child younger."""
    if young:
        return rng.randint(6, 12)
    if kind in ("son", "daughter"):
        return max(16, of.age - rng.randint(18, 30))
    if kind in ("father", "mother"):
        return of.age + rng.randint(18, 30)
    return max(16, of.age + rng.randint(-6, 6))


@bind("kin")
def _bind_kin(game, s, sit, spec, rng):
    """A tie of another role (`of`, `kinds`): the person if they are one, else made now from their name. With `make`, a
    tie is made when there is none (a son the life never named)."""
    from realmwalker.game.story import lives

    of = _npc(game, sit, spec["of"])
    if of is None:
        return None
    lf = _life_of(of)
    if lf is None:
        return None
    kinds = spec.get("kinds") or list(KIN_SEX)
    ties = [t for t in lf["ties"] if t["kind"] in kinds and t.get("state", "alive") == "alive"
            and t.get("figure") is None and (not spec.get("young") or int(t.get("age", 99)) < 14)]
    for t in ties:
        n = game.world.npcs.get(t["npc"]) if t.get("npc") is not None else None
        if n is not None and n.settlement == s.id and _free(game, sit, n, n.job == "child"):
            return dict(_entry(n), kin=t["kind"])
    named = [t for t in ties if t.get("npc") is None]
    if not named and spec.get("make"):
        from realmwalker.world.names import forge

        kind = rng.choice(kinds)
        name = forge(game.world, game.tables).given(of.culture, KIN_SEX.get(kind, "male"), rng,
                                                     avoid={t["name"] for t in lf["ties"]})
        t = {"kind": kind, "name": name, "npc": None, "figure": None, "state": "alive",
             "age": _kin_age(kind, of, rng, bool(spec.get("young")))}
        lf["ties"].append(t)
        named = [t]
    if not named:
        return None
    t = rng.choice(named)
    if t.get("age") is None:
        t["age"] = _kin_age(t["kind"], of, rng, bool(spec.get("young")))
    age = t.get("age")
    young = age is not None and int(age) < 14
    job = "child" if young else spec.get("job") or KIN_JOB.get(t["kind"], "labourer")
    n = _make_person(game, s, job, t["name"], KIN_SEX.get(t["kind"]), age, of, rng)
    t["npc"] = n.id
    back = lives.REVERSE.get(lives.KIN_OF.get(t["kind"], ""), None)
    if back:
        word = lives.KIN_WORDS[back][of.sex == "female"]
        n.flags["life"] = {"ties": [{"kind": word, "name": of.first_name, "npc": of.id, "figure": None,
                                     "state": "alive"}], "want": None, "fear": None, "secrets": [], "things": [],
                           "events": []}
    return dict(_entry(n), kin=t["kind"])


@bind("tie")
def _bind_tie(game, s, sit, spec, rng):
    """A rival, creditor, lover, patron or enemy of another role: the person if they are one; a name is given to a
    townsperson of a fitting trade (`jobs`); with `make`, the tie is made with one."""
    from realmwalker.game.story import lives

    of = _npc(game, sit, spec["of"])
    lf = _life_of(of) if of is not None else None
    if lf is None:
        return None
    kinds = spec.get("kinds") or ["rival"]
    jobs = spec.get("jobs") or []
    for t in lf["ties"]:
        if t["kind"] not in kinds or t.get("state", "alive") != "alive":
            continue
        n = game.world.npcs.get(t["npc"]) if t.get("npc") is not None else None
        if n is not None and n.settlement == s.id and _free(game, sit, n):
            return dict(_entry(n), tie=t["kind"])
    folk = [n for n in _folk(game, s, sit, jobs or None) if n.job not in ADULT_NOT and n.id != of.id]
    if spec.get("same_job"):
        folk = [n for n in folk if n.job == of.job] or folk
    if not folk:
        return None
    named = next((t for t in lf["ties"] if t["kind"] in kinds and t.get("npc") is None and t.get("state") == "alive"),
                 None)
    if named is None and not spec.get("make"):
        return None
    n = rng.choice(folk)
    if named is None:
        lf["ties"].append({"kind": kinds[0], "name": n.first_name, "npc": n.id, "figure": None, "state": "alive"})
    else:
        named["npc"], named["name"] = n.id, n.first_name
    return dict(_entry(n), tie=kinds[0] if named is None else named["kind"])


@bind("stranger")
def _bind_stranger(game, s, sit, spec, rng):
    """Someone come in from the road (`jobs`: their trade), lodged at the inn, who stays while the story lasts."""
    from realmwalker.game.people import npcs_in

    host = next((n for n in npcs_in(game.world, s.id) if n.alive and n.job == "innkeeper"), None) or \
        next((n for n in npcs_in(game.world, s.id) if n.alive and n.notable), None)
    if host is None:
        return None
    jobs = [j for j in spec.get("jobs") or ["wayfarer"] if j in game.tables.people["occupations"]] or ["labourer"]
    n = _make_person(game, s, rng.choice(jobs), None, None, None, host, rng)
    n.post = tuple(host.post)
    n.flags["stranger"] = True
    return _entry(n)


@bind("band")
def _bind_band(game, s, sit, spec, rng):
    """A gang, cult or tribe with a camp within reach (`kinds`, `within` tiles), not yet cleared; the root's if it
    names one."""
    from realmwalker.game.quests import cleared, dist
    from realmwalker.world import factions as fx

    w = game.world
    want = sit["root"].get("faction")
    kinds = spec.get("kinds") or ["bandit_gang", "cult", "tribe"]
    done = cleared(game)
    found = [f for f in fx.active_factions(w, *kinds) if 0 <= f.site < len(w.sites) and f.site not in done
             and dist(w.sites[f.site], s) <= int(spec.get("within", 22))]
    if not found:
        return None
    f = next((f for f in found if f.id == want), None) or min(found, key=lambda f: (dist(w.sites[f.site], s), f.id))
    return {"band": int(f.id), "faction": int(f.id), "site": int(f.site), "name": f.name, "state": None}


@bind("site")
def _bind_site(game, s, sit, spec, rng):
    """A place out in the land (`within` [lo, hi] tiles; `styles` of dungeon)."""
    from realmwalker.game.quests import dist

    lo, hi = spec.get("within", [3, 16])
    styles = spec.get("styles")
    near = [x for x in game.world.sites if lo <= dist(x, s) <= hi and (not styles or getattr(x, "kind", "") in styles)]
    if not near:
        return None
    x = rng.choice(sorted(near, key=lambda x: x.id))
    return {"site": int(x.id), "place": {"site": int(x.id)}, "name": x.name}


@bind("threat")
def _bind_threat(game, s, sit, spec, rng):
    from realmwalker.world import threats

    t = threats.records(game.world).get(sit["root"].get("threat") or "")
    if t is None:
        live = [t for t in threats.live(game.world) if s.id in t["stakes"][:6]]
        t = live[0] if live else None
    return None if t is None else {"threat": t["id"], "name": threats.villain_name(game.world, t)}


@bind("figure")
def _bind_figure(game, s, sit, spec, rng):
    fid = sit["root"].get("figure")
    fig = game.world.figures.get(fid) if fid is not None else None
    return None if fig is None else {"figure": int(fig.id), "name": fig.full_name()}


@bind("far")
def _bind_far(game, s, sit, spec, rng):
    """A person of a trade (`jobs`) in another town (`within` [lo, hi]): bound now if that town has its people, else
    waiting for it (`politics["story_people"]`; story/cast.place_people binds them when it is filled)."""
    from realmwalker.game.quests import dist

    w = game.world
    lo, hi = spec.get("within", [6, 30])
    towns = sorted((x for x in w.settlements if x.id != s.id and lo <= dist(x, s) <= hi), key=lambda x: (dist(x, s), x.id))
    if spec.get("town") == "root":  # (the town the root names: a vignette's shrine)
        towns = [w.settlements[int(sit["root"]["settlement"])]] if sit["root"].get("settlement") is not None else []
    if not towns:
        return None
    dest = towns[rng.randint(0, min(2, len(towns) - 1))]
    jobs = list(spec.get("jobs") or ["headman"])
    town = w.towns.get(dest.id)
    if town is not None and town.npcs:
        folk = _folk(game, dest, sit, jobs) or [n for n in _folk(game, dest, sit) if n.notable]
        return _entry(folk[0]) if folk else None
    w.politics.setdefault("story_people", {}).setdefault(f"S{dest.id}", []).append(
        {"sit": sit["id"], "role": spec.get("_role", ""), "jobs": jobs})
    return {"job": jobs[0], "jobs": jobs, "settlement": int(dest.id)}


def place_people(game, settlement, rec: dict) -> None:
    """A town is filled: a situation's role waiting for it is bound to the person of its trade (story/cast.py)."""
    from realmwalker.game.story import cast

    sit = records(game.world).get(rec.get("sit"))
    if sit is None or sit["state"] not in LIVE:
        return
    entry = sit["roles"].get(rec["role"]) or {}
    if entry.get("npc") is not None:
        return
    npc = cast._choose(game, settlement.id, {"job": rec["jobs"][0], "jobs": rec["jobs"]}, {"id": sit["id"]})
    if npc is not None:
        sit["roles"][rec["role"]] = _entry(npc)
        npc.flags["story"] = {"sit": sit["id"], "role": rec["role"]}
        _write_words(game, sit)


# ---------------------------------------------------------------------------- forging
def _weight(game, root: dict, pid: str, sid: int) -> float:
    """A root's weight, down by how often this hero has met the predicament and the root's kind, and by the town's own
    troubles before (the variety)."""
    life = _life(game)
    allsits = list(records(game.world).values())
    met = [s for s in allsits if s.get("life") == life or s["state"] == "latent"]  # (and those still waiting)
    same = sum(1 for s in met if s["predicament"] == pid)
    kind = sum(1 for s in met if s["root"].get("kind") == root["kind"])
    here = sum(1 for s in allsits if s.get("town") == sid and s["predicament"] == pid)
    return float(root.get("weight", 1.0)) / (1 + 2 * same) / (1 + 0.3 * kind) / (1 + 3 * here)


def make(game, sid: int, root: dict | None = None, predicament: str | None = None) -> dict | None:
    """Forge a situation in a peopled town (see the module's docstring). None when nothing fits."""
    w = game.world
    s = w.settlements[sid]
    preds = predicaments(game.tables)
    town = w.towns.get(sid)
    if not preds or town is None or not town.npcs:
        return None
    if predicament in preds and preds[predicament].get("inside") and (root or {}).get("kind") != "adventure":
        return None  # (an adventure step's own: only for_step makes one)
    if predicament in preds and preds[predicament].get("vignette") and (root or {}).get("vignette") != predicament:
        from realmwalker.game.story import vignettes

        root = vignettes.find(game, s, predicament)  # (a vignette comes only from what its need finds)
        if root is None:
            return None
    n = int(w.politics.get("next_situation", 1))
    qid = f"Q{n}"
    rng = w.rng.child(f"situation/{qid}")
    roots = [root] if root is not None else gather_roots(game, s, rng)
    table = data(game).get("roots") or {}
    pool = []
    for r in roots:
        for pid in table.get(r["key"]) or ([r["vignette"]] if r.get("vignette") else []):
            if pid in preds and (predicament is None or pid == predicament):
                pool.append((r, pid, _weight(game, r, pid, sid)))
    if predicament is not None and not pool and predicament in preds:
        pool = [(root or {"kind": "town", "key": "town"}, predicament, 1.0)]
    order = []
    while pool:
        total = sum(p[2] for p in pool)
        x = rng.random() * total
        for i, p in enumerate(pool):
            x -= p[2]
            if x <= 0 or i == len(pool) - 1:
                order.append(pool.pop(i))
                break
    for r, pid, _ in order[:12]:
        sit = _cast(game, s, dict(r), pid, qid, rng.child(pid))
        if sit is not None:
            w.politics["next_situation"] = n + 1
            records(w)[qid] = sit
            if r.get("kind") == "life" and r.get("event") is not None:
                _use_seed(game, r)
            _turn(game, sit, "forge")
            _next_gap(game, s, rng)
            return sit
    return None


def _use_seed(game, r: dict) -> None:
    n = game.world.npcs.get(r.get("npc", -1))
    for ev in ((n.flags.get("life") or {}).get("events", []) if n is not None else []):
        if int(ev.get("day", -1)) == int(r["event"]) and ev.get("seed"):
            ev["used"] = True


def _unbind(game, sit: dict) -> None:
    for rec in sit["roles"].values():
        n = game.world.npcs.get(rec["npc"]) if rec.get("npc") is not None else None
        if n is not None and (n.flags.get("story") or {}).get("sit") == sit["id"]:
            n.flags.pop("story", None)


def _cast(game, s, root: dict, pid: str, qid: str, rng) -> dict | None:
    spec = predicaments(game.tables)[pid]
    today = _today(game)
    sit = {"id": qid, "town": int(s.id), "root": root, "predicament": pid, "roles": {}, "stakes": {}, "clock": {},
           "goals": _story_tag(copy.deepcopy(spec["goals"]), qid), "obstacles": [], "turn": None, "meeting": None, "state": "latent",
           "ways": [], "flags": [], "used": [], "quest": None, "threat": root.get("threat"), "adventure": root.get("adv"),
           "ending": None, "tone": None, "made": today, "met": None, "life": None, "words": {}, "journal": []}
    _MADE.clear()
    first = [r for r, rs in spec["roles"].items() if rs["bind"] not in MAKES and rs.get("or") not in MAKES]
    for role in first + [r for r in spec["roles"] if r not in first]:  # (those who make no one first)
        rs = spec["roles"][role]
        entry = None
        for how in (rs["bind"], rs.get("or")):
            fn = BINDS.get(how) if how else None
            if entry is None and fn is not None:
                entry = fn(game, s, sit, dict(rs, _role=role), rng)
        if entry is None:
            if rs.get("optional"):
                continue
            _undo(game, sit)
            return None
        sit["roles"][role] = entry
        n = game.world.npcs.get(entry["npc"]) if entry.get("npc") is not None else None
        if n is not None and not _of_tale(sit, n):  # (the tale's own people keep their part in it)
            n.flags["story"] = {"sit": qid, "role": role}
    for i, ob in enumerate(spec.get("obstacles", [])):
        if ob.get("who") and ob["who"] not in sit["roles"]:
            continue
        if ob.get("chance") is not None and not rng.chance(float(ob["chance"])):
            continue
        sit["obstacles"].append(dict(copy.deepcopy(ob), id=ob.get("id", f"o{i}"), state="standing"))
    lo, hi = spec.get("clock", [12, 24])
    sit["clock"] = {"due": today + rng.randint(int(lo), int(hi)), "half": False}
    sit["words"].update(root.get("words") or {})  # (a vignette's own things: the ruin, the dead, the blade)
    sit["meeting"] = _meeting(game, sit, spec, rng)
    if sit["meeting"] is None:
        _undo(game, sit)
        return None
    sit["roles"] = {r: sit["roles"][r] for r in spec["roles"] if r in sit["roles"]}  # (the data's order)
    sit["turn"] = _pick_turn(game, sit, spec, rng)
    _write_words(game, sit, rng, kept_only=True)  # (the heirloom's name, before it is put in a pocket)
    for op in spec.get("forge", []):  # (what is already so when it is forged: the lost one gone to the band)
        _op(game, sit, op)
    _write_words(game, sit, rng)
    _MADE.clear()
    return sit


def _undo(game, sit: dict) -> None:
    """A forging that failed leaves nothing behind: its people let go, those it made taken away, its waiting roles
    forgotten."""
    from realmwalker.game import townlife

    _unbind(game, sit)
    w = game.world
    for nid in _MADE:
        n = w.npcs.pop(nid, None)
        town = w.towns.get(n.settlement) if n is not None else None
        if town is not None and nid in town.npcs:
            town.npcs.remove(nid)
        townlife.forget_person(nid)
        for other in w.npcs.values():
            for t in (other.flags.get("life") or {}).get("ties", []):
                if t.get("npc") == nid:
                    t["npc"] = None
    _MADE.clear()
    for key, recs in list(w.politics.get("story_people", {}).items()):
        w.politics["story_people"][key] = [r for r in recs if r.get("sit") != sit["id"]]


def _story_tag(t, qid: str):
    """A goal's "$story" is this situation's own thing ("story:Q3")."""
    if isinstance(t, list):
        return [_story_tag(x, qid) for x in t]
    if isinstance(t, dict):
        return {k: _story_tag(v, qid) for k, v in t.items()}
    return f"story:{qid}" if t == "$story" else t


def _cast_of(game, spec: dict, kind: str) -> dict:
    """A meeting's scene roles and the situation's roles that play them (the predicament's `parts` say who)."""
    m = (data(game).get("meetings") or {}).get(kind) or {}
    out = dict(m.get("cast", {}))
    for k, v in (spec.get("parts") or {}).items():
        if k in out:
            out[k] = v
    return out


def _meeting(game, sit: dict, spec: dict, rng) -> dict | None:
    meets = data(game).get("meetings") or {}
    life = _life(game)
    seen = {s["meeting"]["kind"] for s in records(game.world).values() if s.get("life") == life and s.get("meeting")}
    ok = []
    for kind in spec.get("meetings", []):
        m = meets.get(kind)
        if m is None or m.get("scene") not in game.tables.scenes:
            continue
        if any(_npc(game, sit, r) is None for r in _cast_of(game, spec, kind).values()):
            continue
        ok.append(kind)
    if not ok:
        return None
    twin = {s["meeting"]["kind"] for s in records(game.world).values() if s.get("meeting") and s is not sit
            and s["predicament"] == sit["predicament"] and s["root"].get("kind") == sit["root"].get("kind")
            and (s.get("life") == life or s["state"] == "latent")}  # (never two alike in root, shape and meeting)
    fresh = [k for k in ok if k not in seen and k not in twin] or [k for k in ok if k not in twin] or         [k for k in ok if k not in seen] or ok
    return {"kind": rng.choice(fresh), "state": "waiting"}


def _pick_turn(game, sit: dict, spec: dict, rng) -> dict | None:
    turns = data(game).get("turns") or {}
    ids = {ob["id"] for ob in sit["obstacles"]}
    fits = [tid for tid, t in sorted(turns.items()) if not tid.startswith("_") and sit["predicament"] in t.get("for", [])
            and all(r in sit["roles"] for r in t.get("needs", []))
            and (not t.get("threat") or sit.get("threat")) and (t.get("obstacle") or {}).get("id") not in ids]
    if not fits or not rng.chance(_rarity(game)["turn_chance"]):
        return None
    return {"id": rng.choice(fits), "state": "hidden"}


def _turn(game, sit: dict, when: str) -> list[str]:
    """A turn whose time has come: its ops, its obstacle, its line (in the journal once the situation is met)."""
    t = sit.get("turn")
    if not t or t["state"] != "hidden":
        return []
    td = (data(game).get("turns") or {}).get(t["id"]) or {}
    if td.get("when", "take") != when:
        return []
    t["state"] = "fired"
    lines = []
    for op in td.get("ops", []):
        lines += _op(game, sit, op)
    ob = td.get("obstacle")
    if ob and (not ob.get("who") or ob["who"] in sit["roles"]):
        sit["obstacles"].append(dict(copy.deepcopy(ob), id=ob.get("id", f"t_{t['id']}"), state="standing"))
    line = _fill(game, sit, td.get("line"), f"turn/{t['id']}")
    if line:
        sit["journal"].append(line)
        if sit["state"] != "latent":
            lines.append(f"<warn>{esc(line)}</>")
    return lines


# ---------------------------------------------------------------------------- words
def _name(game, rec: dict) -> tuple[str, str, str]:
    w = game.world
    if rec.get("npc") is not None and rec["npc"] in w.npcs:
        n = w.npcs[rec["npc"]]
        return n.name, n.first_name, n.title
    if rec.get("job") is not None and rec.get("settlement") is not None:
        job = game.tables.people["occupations"].get(rec["job"], {}).get("name", rec["job"])
        place = w.settlements[int(rec["settlement"])].name
        return f"the {job} of {place}", f"the {job}", job
    name = rec.get("name") or "someone"
    return name, name, name


def _due_words(game, day: int, by: bool = False) -> str:
    """When the clock runs out, in words: "tomorrow", "in 6 days" ("by tomorrow", "within 6 days")."""
    left = day - _today(game)
    if left <= 1:
        return "by tomorrow" if by else "tomorrow"
    return f"within {left} days" if by else f"in {left} days"


def _values(game, sit: dict) -> dict:
    from realmwalker.game.people import pronouns
    from realmwalker.game.quests import when_text

    w = game.world
    s = w.settlements[sit["town"]]
    due = int(sit["clock"]["due"])
    out = {"town": s.name, "due": _due_words(game, due), "by_due": _due_words(game, due, by=True),
           "you": game.leader.name.split()[0], "dead": sit["root"].get("name") or "the dead"}
    for role, rec in sit["roles"].items():
        full, first, title = _name(game, rec)
        out[role] = first
        out[f"{role}_full"] = full
        out[f"{role}_title"] = title
        if rec.get("kin"):
            out[f"{role}_kin"] = rec["kin"]
        n = _npc(game, sit, role)
        if n is not None:
            p = pronouns(n)
            out[f"{role}_they"], out[f"{role}_them"], out[f"{role}_their"] = p["they"], p["them"], p["their"]
        if rec.get("site") is not None and 0 <= int(rec["site"]) < len(w.sites):
            out[f"{role}_site"] = w.sites[int(rec["site"])].name
    spec = spec_of(game, sit)
    for role, rec in sit["roles"].items():  # (what the other one is to a kin: "my son", from the mother's side)
        of = (spec.get("roles", {}).get(role) or {}).get("of")
        o = _npc(game, sit, of) if of else None
        if rec.get("kin") and o is not None and f"{of}_kin" not in out:
            from realmwalker.game.story import lives

            back = lives.REVERSE.get(lives.KIN_OF.get(rec["kin"], ""))
            if back:
                out[f"{of}_kin"] = lives.KIN_WORDS[back][o.sex == "female"]
    for ob in sit.get("obstacles", []):
        for a in ob.get("acts", []):
            if a.get("price"):
                from realmwalker.rules.items import money_text

                out[f"price_{a['id']}"] = money_text(int(a["price"]) * int(sit.get("price_mult", 1)))
    for k, v in sit.get("words", {}).items():
        if isinstance(v, str) and k not in out:
            out[k] = v
    return out


def _fill(game, sit: dict, lines, key: str) -> str:
    if isinstance(lines, str):
        lines = [lines]
    if not lines:
        return ""
    rng = game.world.rng.child(f"situation/{sit['id']}/words/{key}")
    return textgen.tidy(textgen.fill(rng.choice(list(lines)), rng, game.tables.adventures.get("words", {}),
                                     _values(game, sit)))


def _write_words(game, sit: dict, rng=None, kept_only: bool = False) -> None:
    """The words met once, written at forging and kept: the things named (`keep`: the heirloom, the prize), the title,
    the stakes, the plea, the journal's first line. A kept name keeps its own first letter ("the stall by the gate")."""
    spec = spec_of(game, sit)
    wd = spec.get("words", {})
    for key in wd.get("keep", []):
        if wd.get(key) and key not in sit["words"]:
            r = game.world.rng.child(f"situation/{sit['id']}/words/{key}")
            tpl = r.choice(list(wd[key]))
            text = textgen.fill(tpl, r, game.tables.adventures.get("words", {}), _values(game, sit))
            sit["words"][key] = text[:1].lower() + text[1:] if tpl[:1].islower() else text
    if kept_only:
        return
    for key in ("title", "stakes", "plea", "first"):
        if wd.get(key):
            sit["words"][key] = _fill(game, sit, wd[key], key)


def title(game, sit: dict) -> str:
    return sit["words"].get("title") or spec_of(game, sit).get("name", sit["predicament"])


# ---------------------------------------------------------------------------- meeting
def _meet_cast(game, sit: dict) -> dict:
    out = {}
    for scene_role, role in _cast_of(game, spec_of(game, sit), sit["meeting"]["kind"]).items():
        n = _npc(game, sit, role)
        if n is not None:
            out[scene_role] = n.id
    return out


def asker(game, sit: dict):
    return _npc(game, sit, spec_of(game, sit).get("asks", "asker"))


def on_enter_town(game, s) -> None:
    """Into a peopled town: a situation may be forged here (a natural moment). It is met a little later, by the town's
    clock (`on_tick`), never on the step through the gate."""
    if due_here(game, s):
        town = game.world.towns.get(s.id)
        if town is not None and town.flags.get("sit_next") is None:
            _next_gap(game, s, game.world.rng.child(f"situation/first/{s.id}"), first=True)  # (not on the first step)
        maybe_forge(game, s)


def on_tick(game, lm, s) -> None:
    """A town tick: now and then, a situation waiting here is met (its scene played)."""
    from realmwalker.game import townlife

    if game.local is not lm or game.busy:
        return
    if townlife._town(game, lm).ticks % 12:
        return
    _try_meet(game, s)


def _try_meet(game, s) -> bool:
    from realmwalker.game.story import stage

    if stage.current(game) is not None or game.busy:
        return False
    for sit in live_in(game, s.id):
        if sit["state"] != "latent" or (sit.get("meeting") or {}).get("state") != "waiting":
            continue
        m = (data(game).get("meetings") or {}).get(sit["meeting"]["kind"]) or {}
        cast = _meet_cast(game, sit)
        if len(cast) < len(m.get("cast", {})):
            continue
        from realmwalker.game import townlife

        folk = [game.world.npcs[i] for i in cast.values()]
        if any(not n.alive or not n.present or townlife.asleep(game, n) for n in folk):
            continue  # (they are about by day: the meeting waits for them)
        _write_words(game, sit)
        words = {k: v for k, v in _values(game, sit).items() if isinstance(v, str)}
        words["hook"] = words.get("plea", "")
        a = asker(game, sit)
        if a is not None and m.get("letter"):
            words["sender"], words["hand_of"] = f"{a.first_name}, {a.title}", a.job
        rec = stage.start(game, m["scene"], cast=cast, words=words)
        if rec is None:
            return False
        rec["sit"] = sit["id"]
        met(game, sit)
        return True
    return False


def met(game, sit: dict) -> None:
    """The situation is seen: it is in the hero's journal, as theirs."""
    if sit["state"] != "latent":
        return
    _write_words(game, sit)  # (said now: the days left are today's)
    sit["state"] = "met"
    sit["met"] = _today(game)
    sit["life"] = _life(game)
    sit["meeting"]["state"] = "played"
    first = sit["words"].get("first")
    if first:
        sit["journal"].append(first)
    for line in _turn(game, sit, "meet"):
        game.say(line, "story")
    game.say(f"<info>Journal: {esc(title(game, sit))}</> <dim>(a trouble in "
             f"{esc(game.world.settlements[sit['town']].name)}; j)</>", "story")


# ---------------------------------------------------------------------------- conversation
def _cond(game, sit: dict, text: str) -> bool:
    if text.startswith("not:"):
        return not _cond(game, sit, text[4:])
    kind, _, arg = text.partition(":")
    if kind == "goal":
        return any(g["id"] == arg and g.get("reached") is not None for g in sit["goals"])
    if kind == "way":
        return goals.way_used(sit, arg)
    if kind == "flag":
        return arg in sit["flags"]
    if kind == "knows":
        return f"knows_{arg}" in sit["flags"]
    if kind == "turn":
        return bool(sit.get("turn")) and sit["turn"]["id"] == arg and sit["turn"]["state"] == "fired"
    if kind == "taken":
        return sit["state"] == "taken" or "taken" in sit["flags"]
    if kind == "refused":
        return "refused" in sit["flags"]
    if kind == "work_done":
        return "work_done" in sit["flags"]
    if kind == "work_failed":
        return "work_failed" in sit["flags"]
    if kind == "holds":
        return any(f"story:{sit['id']}" in it.tags for c in game.party for it in c.inventory)
    return False


def _acts(game, sit: dict, npc) -> list[tuple[dict, dict | None]]:
    """The acts open to the hero with this person: (act, its obstacle or None)."""
    role = _role_of(sit, npc)
    out = []
    spec = spec_of(game, sit)
    for ob in sit["obstacles"]:
        if ob["state"] != "standing":
            continue
        for a in ob.get("acts", []):
            if a.get("who", ob.get("who")) == role:
                out.append((a, ob))
    for a in spec.get("acts", []):
        if a.get("who") == role:
            out.append((a, None))
    tried = sit.get("tried", {})
    today = _today(game)
    return [(a, ob) for a, ob in out if f"{(ob or {}).get('id', '')}/{a['id']}" not in sit["used"]
            and int(tried.get(f"{(ob or {}).get('id', '')}/{a['id']}", -1)) < today
            and all(_cond(game, sit, c) for c in a.get("needs", []))
            and not any(_cond(game, sit, c) for c in a.get("unless", []))]


def _price(sit: dict, a: dict) -> int:
    return int(a.get("price", 0)) * int(sit.get("price_mult", 1))


def _talk(game, key: str) -> list[str]:
    return (data(game).get("talk") or {}).get(key) or ["..."]


def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice
    from realmwalker.game.law import party_money

    game, npc = conv.game, conv.npc
    out = []
    for sit in live_in(game, npc.settlement):
        role = _role_of(sit, npc)
        if role is None:
            continue
        spec = spec_of(game, sit)
        asks = role == spec.get("asks", "asker")
        wd = spec.get("words", {})
        if sit["state"] == "latent" and asks:
            out.append(Choice("sit_ask", _fill(game, sit, wd.get("ask") or _talk(game, "ask"), "ask"),
                              data={"sit": sit["id"]}))
        elif sit["state"] == "met" and asks and "refused" not in sit["flags"]:
            out.append(Choice("sit_take", _fill(game, sit, wd.get("take") or _talk(game, "take"), "take"),
                              data={"sit": sit["id"]}))
            out.append(Choice("sit_refuse", _fill(game, sit, wd.get("refuse") or _talk(game, "refuse"), "refuse"),
                              data={"sit": sit["id"]}))
        if sit["state"] != "taken":
            continue
        money = party_money(game)
        for a, ob in _acts(game, sit, npc):
            label = _fill(game, sit, a.get("label") or a["id"], f"act/{a['id']}")
            if a.get("check"):
                label = f"[{game.tables.rules['skills'][a['check'][0]]['name']}] {label}"
            price = _price(sit, a)
            if price:
                from realmwalker.rules.items import money_text

                label = f"{label} ({money_text(price)})"
            out.append(Choice("sit_act", label, enabled=money >= price, why="you don't have that much",
                              data={"sit": sit["id"], "act": a["id"], "ob": (ob or {}).get("id")}))
    return out


def talk_choose(conv, choice) -> None:
    game = conv.game
    sit = records(game.world).get(choice.data.get("sit"))
    if sit is None or sit["state"] not in LIVE:
        return
    spec = spec_of(game, sit)
    wd = spec.get("words", {})
    conv.you_say(esc(choice.label))
    if choice.id == "sit_ask":
        conv.npc_says(esc(sit["words"].get("plea") or _fill(game, sit, wd.get("plea"), "plea")))
        met(game, sit)
    elif choice.id == "sit_take":
        conv.npc_says(esc(_fill(game, sit, wd.get("thanks") or _talk(game, "thanks"), "thanks")))
        for line in take(game, sit):
            conv.note(line)
    elif choice.id == "sit_refuse":
        sit["flags"].append("refused")
        conv.npc_says(esc(_fill(game, sit, wd.get("refused") or _talk(game, "refused"), "refused")))
        from realmwalker.game.people import change_disposition

        change_disposition(conv.npc, -5)
        sit["journal"].append(_fill(game, sit, ["You told {asker} it was not your trouble."], "refused_note"))
        goals.notify(game, "talk", "talk", npc=conv.npc)
    elif choice.id == "sit_act":
        do_act(conv, sit, choice.data["act"], choice.data.get("ob"))


def do_act(conv, sit: dict, aid: str, obid: str | None) -> None:
    """An act with a person of the story: its check rolled, its price paid if it passed; then what passing it does.
    A failed check may be tried again the next day."""
    from realmwalker.game.law import take_money

    game = conv.game
    ob = next((o for o in sit["obstacles"] if o["id"] == obid), None) if obid else None
    acts = (ob or {}).get("acts", []) if ob is not None else spec_of(game, sit).get("acts", [])
    a = next((x for x in acts if x["id"] == aid), None)
    if a is None:
        return
    key = f"{(ob or {}).get('id', '')}/{a['id']}"
    price = _price(sit, a)
    ok = True
    if a.get("check"):
        skill, dc = a["check"][0], int(a["check"][1])
        ok, text = conv.check(skill, dc)
        conv.note(text)
    if price and ok:  # (paid only when it is taken: a haggle that fails costs nothing)
        take_money(game, price)
        conv.paid = True
    if ok:
        sit["used"].append(key)
    else:
        sit.setdefault("tried", {})[key] = _today(game)  # (another day, another try)
    way = a.get("way") or ("pay" if price else "talk")
    if ok:
        said = _fill(game, sit, a.get("say"), f"say/{key}")
        if said:
            conv.npc_says(esc(said))
        if ob is not None and a.get("pass", True):
            ob["state"] = "passed"
            ob["way"] = way
        for op in a.get("then", []):
            for line in _op(game, sit, op):
                conv.note(line)
        note = _fill(game, sit, a.get("note"), f"note/{key}")
        if note:
            sit["journal"].append(note)
    else:
        said = _fill(game, sit, a.get("fail_say") or ["No. I will not."], f"fail/{key}")
        conv.npc_says(esc(said))
        for op in a.get("fail", []):
            for line in _op(game, sit, op):
                conv.note(line)
    goals.notify(game, "talk", way, npc=conv.npc)


def take(game, sit: dict) -> list[str]:
    """The hero takes it on: the work it needs (a quest for its real target), its turn on taking."""
    if sit["state"] == "latent":
        met(game, sit)
    if sit["state"] != "met":
        return []
    sit["state"] = "taken"
    sit["flags"].append("taken")
    sit["taken"] = _today(game)
    out = [f"<info>Journal: {esc(title(game, sit))}.</> <dim>(the stakes: {esc(sit['words'].get('stakes', ''))})</>"]
    out += _make_work(game, sit)
    out += _turn(game, sit, "take")
    goals.notify(game, "talk", "talk")
    return out


# ---------------------------------------------------------------------------- work
WORKS: dict[str, object] = {}


def work(kind: str):
    """fn(game, sit, spec) -> a quests.make target or None"""
    def wrap(fn):
        WORKS[kind] = fn
        return fn
    return wrap


def _role_ref(game, sit, ref):
    return sit["roles"].get(ref) or {}


@work("rescue")
def _w_rescue(game, sit, spec):
    band, held = _role_ref(game, sit, spec["band"]), _npc(game, sit, spec["who"])
    if band.get("faction") is None or held is None:
        return None
    return {"kind": "rescue", "holder": band["faction"], "captive": held.name, "npc": held.id,
            "kin": sit["roles"][spec["who"]].get("kin") or "kin", "sex": held.sex}


@work("retrieve")
def _w_retrieve(game, sit, spec):
    place = _role_ref(game, sit, spec["site"])
    if place.get("site") is None:
        return None
    return {"kind": "retrieve", "site": place["site"]}


@work("deliver")
def _w_deliver(game, sit, spec):
    from realmwalker.game.people import prepare_town

    rec = _role_ref(game, sit, spec["to"])
    if rec.get("npc") is None and rec.get("settlement") is not None:
        prepare_town(game, game.world.settlements[int(rec["settlement"])])  # (the town fills, and binds them)
        rec = _role_ref(game, sit, spec["to"])
    n = game.world.npcs.get(rec.get("npc", -1))
    return None if n is None else {"kind": "deliver", "dest": n.settlement, "npc": n.id}


@work("cure")
def _w_cure(game, sit, spec):
    return {"kind": "cure", "count": int(spec.get("count", 4))} if "healing_herbs" in game.tables.items else None


@work("feud")
def _w_feud(game, sit, spec):
    a, b = _npc(game, sit, spec["a"]), _npc(game, sit, spec["b"])
    return None if a is None or b is None else {"kind": "feud", "a": a.id, "b": b.id}


@work("assassinate")
def _w_assassinate(game, sit, spec):
    n = _npc(game, sit, spec["who"])
    return None if n is None else {"kind": "assassinate", "npc": n.id}


@work("collect_debt")
def _w_collect(game, sit, spec):
    n = _npc(game, sit, spec["who"])
    return None if n is None else {"kind": "collect_debt", "dest": n.settlement, "npc": n.id,
                                   "debt": int(spec.get("debt", 4000))}


def _make_work(game, sit: dict) -> list[str]:
    from realmwalker.game import quests

    spec = spec_of(game, sit).get("work")
    if not spec or sit.get("quest") is not None or spec["kind"] not in WORKS:
        return []
    target = WORKS[spec["kind"]](game, sit, spec)
    if target is None:
        return []
    target["town"] = sit["town"]
    giver = _npc(game, sit, spec.get("giver", "asker"))
    q = quests.make(game, giver, target, game.world.rng.child(f"situation/{sit['id']}/work"))
    if target.get("npc") is not None and spec["kind"] == "rescue":
        q["target"]["npc"] = int(target["npc"])
    if spec.get("item") and sit["words"].get(spec["item"]):  # (what the work brings back: the lost one's ring)
        q["target"]["item"] = q["words"]["item"] = sit["words"][spec["item"]]
    q["situation"] = sit["id"]
    left = int(sit["clock"]["due"]) - _today(game)
    if int(q["days"]) > left:  # (the work needs longer than the clock gave: the trouble waits for it)
        sit["clock"]["due"] = _today(game) + int(q["days"])
    q["days"] = int(sit["clock"]["due"]) - _today(game)
    out = quests.accept(game, q)
    sit["quest"] = q["id"]
    return out


def on_quest_end(game, q: dict, ok: bool) -> None:
    """A situation's work is over (quests.reward / fail): its goals hear of it."""
    sit = records(game.world).get(q.get("situation"))
    if sit is None or sit["state"] not in LIVE:
        return
    sit["flags"].append("work_done" if ok else "work_failed")
    goals.notify(game, "talk", WORK_WAYS.get(q.get("template"), "talk") if ok else "wait")


def on_magic(game, spell: str) -> list[str]:
    """A spell cast on the road in a situation's town may pass an obstacle that names it (a curse lifted)."""
    w = game.world
    s = w.settlement_at(game.player.x, game.player.y)
    if s is None:
        return []
    out = []
    for sit in live_in(game, s.id):
        if sit["state"] != "taken":
            continue
        for ob in sit["obstacles"]:
            if ob["state"] == "standing" and spell in ob.get("spells", []):
                ob["state"] = "passed"
                ob["way"] = "magic"
                for op in ob.get("by_magic", []):
                    out += _op(game, sit, op)
                note = _fill(game, sit, ob.get("magic_note"), f"magic/{ob['id']}")
                if note:
                    sit["journal"].append(note)
                    out.append(f"<good>{esc(note)}</>")
    return out


# ---------------------------------------------------------------------------- the people ops
OPS: dict[str, object] = {}
OP_ARGS: dict[str, tuple] = {}


def op(name: str, *args: str):
    """fn(game, sit, *args) -> lines said; `args`: the kinds of its arguments (role, word, int, float...)"""
    def wrap(fn):
        OPS[name] = fn
        OP_ARGS[name] = args
        return fn
    return wrap


def _op(game, sit: dict, o: list) -> list[str]:
    return OPS[o[0]](game, sit, *o[1:]) or []


@op("flag", "word")
def _o_flag(game, sit, f):
    if f not in sit["flags"]:
        sit["flags"].append(f)


@op("unflag", "word")
def _o_unflag(game, sit, f):
    sit["flags"] = [x for x in sit["flags"] if x != f]


@op("learn", "word")
def _o_learn(game, sit, truth):
    """The hero comes to know a truth of this situation (a codeword `knows_<truth>`, and the hero's own truths)."""
    _o_flag(game, sit, f"knows_{truth}")
    known = game.renown.flags.setdefault("truths", [])
    key = f"{sit['id']}:{truth}"
    if key not in known:
        known.append(key)


@op("tell", "role", "word")
def _o_tell(game, sit, role, truth):
    n = _npc(game, sit, role)
    if n is not None:
        k = n.flags.setdefault("knows", [])
        if f"{sit['id']}:{truth}" not in k:
            k.append(f"{sit['id']}:{truth}")
    _o_flag(game, sit, f"told_{truth}")


@op("law", "role", "law")
def _o_law(game, sit, role, state):
    """Someone's standing with the law: accused, jailed, pardoned, free, or hanged (dead, and buried)."""
    n = _npc(game, sit, role)
    if n is None or not n.alive:
        return []
    if state == "free":
        n.flags.pop("law", None)
        return []
    n.flags["law"] = state
    if state == "hanged":
        _die(game, sit, n, "hanged")
    return []


def _die(game, sit, n, how: str) -> None:
    """A death through the people code: alive no more, forgotten by the streets, mourned, a job that wanted them heard."""
    from realmwalker.game import townlife
    from realmwalker.game.story import lives

    n.alive = False
    n.present = False
    n.flags.pop("with_party", None)
    townlife.forget_person(n.id)
    if game.quests:
        from realmwalker.game import quests

        quests.on_npc_death(game, n)
    for t in (lives.life(n) or {}).get("ties", []):
        other = game.world.npcs.get(t["npc"]) if t.get("npc") is not None else None
        if other is not None and other.alive and lives.KIN_OF.get(t["kind"]) is not None:
            lives._mourn(game, other, 21)
            for ot in (lives.life(other) or {}).get("ties", []):
                if ot.get("npc") == n.id:
                    ot["state"] = "dead"
    n.flags["died"] = {"how": how, "day": _today(game), "situation": sit["id"]}
    _o_grave(game, sit, _role_of(sit, n))  # (every death a story brings is buried in its town)


@op("npc_fate", "role", "fate")
def _o_fate(game, sit, role, fate):
    """What becomes of someone: alive (as they were), home (back where they live), gone (away for good), ruined (the
    shop shut, the purse empty), jailed, dead."""
    n = _npc(game, sit, role)
    if n is None:
        return []
    if fate == "dead":
        if n.alive:
            _die(game, sit, n, "story")
    elif fate in ("home", "alive"):
        for k in ("captive", "with_party", "away"):
            n.flags.pop(k, None)
        if fate == "home":
            n.x, n.y = n.home
        n.present = True
    elif fate == "gone":
        for k in ("captive", "with_party"):
            n.flags.pop(k, None)
        n.flags["gone"] = True
        n.present = False
    elif fate == "ruined":
        n.purse = 0
        _o_shop(game, sit, role, "shut", 60)
    elif fate == "jailed":
        n.flags["law"] = "jailed"
        n.present = False
    return []


@op("dead_kin", "role")
def _o_dead_kin(game, sit, role):
    """The one the story mourns, when its root names nobody: a kin of `role` lately dead (a name in their life; a
    fresh grave in the town), kept as the words' {dead}."""
    from realmwalker.game.story import lives

    n = _npc(game, sit, role)
    if n is None or sit["root"].get("name"):
        return []
    lf = lives.life(n) or {}
    ties = [t for t in lf.get("ties", []) if lives.KIN_OF.get(t["kind"]) and t.get("npc") is None
            and t.get("figure") is None]
    dead = next((t for t in ties if t.get("state") == "dead"), None)
    if dead is None:
        alive = [t for t in ties if t.get("state", "alive") == "alive" and lives.KIN_OF[t["kind"]] in ("parent", "spouse")]
        if not alive:  # (a parent the life never named, named now)
            from realmwalker.world.names import forge

            r = game.world.rng.child(f"situation/{sit['id']}/dead")
            kind = r.choice(["father", "mother"])
            name = forge(game.world, game.tables).given(n.culture, KIN_SEX[kind], r,
                                                        avoid={t["name"] for t in lf.get("ties", [])})
            alive = [{"kind": kind, "name": name, "npc": None, "figure": None, "state": "alive"}]
            _life_of(n)["ties"].append(alive[0])
        dead = alive[0]
        dead["state"] = "dead"
        lives._grave(game, game.world.settlements[sit["town"]], {"name": dead["name"]})
        lives._mourn(game, n, 21)
    sit["root"]["name"] = dead["name"]
    return []


@op("away", "role")
def _o_away(game, sit, role):
    """Someone is away from the town (gone to the band, held): not in its streets until they come home."""
    n = _npc(game, sit, role)
    if n is not None:
        n.flags["captive"] = sit["id"]
        n.present = False


@op("tie", "role", "word", "role")
def _o_tie(game, sit, a, kind, b):
    """A tie made in two lives: married (husband and wife), or lovers, rivals, enemies, a patron."""
    from realmwalker.game.story import lives

    na, nb = _npc(game, sit, a), _npc(game, sit, b)
    if na is None or nb is None:
        return []
    for x, y in ((na, nb), (nb, na)):
        lf = x.flags.setdefault("life", {"ties": [], "want": None, "fear": None, "secrets": [], "things": [],
                                         "events": []})
        word = lives.KIN_WORDS["spouse"][y.sex == "female"] if kind == "married" else kind
        lf["ties"] = [t for t in lf["ties"] if t.get("npc") != y.id]
        lf["ties"].append({"kind": word, "name": y.first_name, "npc": y.id, "figure": None, "state": "alive"})
    return []


@op("grave", "role")
def _o_grave(game, sit, role):
    from realmwalker.game.story import lives

    n = _npc(game, sit, role) if role else None
    lm = goals._town_map(game, sit["town"])
    if n is not None and not any(g.get("who") == {"npc": n.id} for g in (lm.meta.get("graves", []) if lm else [])):
        lives._grave(game, game.world.settlements[sit["town"]], {"npc": n.id})


@op("mark", "word")
def _o_mark(game, sit, mark):
    from realmwalker.world import marks

    if mark in game.tables.marks:
        marks.add(game.world, game.world.settlements[sit["town"]], mark, float(_today(game)), game.tables)


def _legend(game, key: str) -> list:
    return game.renown.legend.setdefault(key, [])


@op("favour", "role", "word", "int")
def _o_favour(game, sit, role, kind, weight):
    """Someone owes the hero a favour (spent as a way through later: story/favours.py, C.7)."""
    n = _npc(game, sit, role)
    if n is not None and n.alive:
        _legend(game, "favours").append({"from": n.id, "weight": int(weight), "kind": kind, "day": _today(game),
                                         "used": False, "situation": sit["id"]})
        return [f"<good>{esc(n.first_name)} owes you a favour.</>"]
    return []


@op("contact", "role", "word")
def _o_contact(game, sit, role, kind):
    n = _npc(game, sit, role)
    if n is not None and n.alive and not any(c.get("npc") == n.id for c in _legend(game, "contacts")):
        _legend(game, "contacts").append({"npc": n.id, "kind": kind, "since": _today(game)})
        return [f"<good>{esc(n.first_name)} will be a friend to you in {esc(game.world.settlements[n.settlement].name)}.</>"]
    return []


@op("xp_story", "word")
def _o_xp(game, sit, size):
    """Experience from a story's end, by the encounter budget for the party's levels (story/experience.py, C.8): a
    quarter of a moderate fight's budget for a small end, half for a fair one, the whole for a great one; more when no
    blood was shed, twice as much under "Stories only"."""
    from realmwalker.game.story import experience

    return experience.award(game, size, f"situation/{sit['id']}", no_fight=not goals.way_used(sit, "fight"))


@op("shop", "role", "word", "int")
def _o_shop(game, sit, role, how, days):
    from realmwalker.game.story.lives import DAY

    n = _npc(game, sit, role)
    if n is None:
        return []
    if how == "shut":
        n.flags["closed_until"] = game.world.time + int(days) * DAY
    else:
        n.flags.pop("closed_until", None)
    return []


@op("move", "role")
def _o_move(game, sit, role):
    """Someone leaves for another town for good (the nearest other one): gone from here, remembered there."""
    n = _npc(game, sit, role)
    if n is None or not n.alive:
        return []
    from realmwalker.game.quests import dist

    s = game.world.settlements[sit["town"]]
    others = sorted((x for x in game.world.settlements if x.id != s.id), key=lambda x: (dist(x, s), x.id))
    n.flags["gone"] = True
    n.flags["moved_to"] = others[0].id if others else None
    n.present = False
    return []


@op("money", "int")
def _o_money(game, sit, amount):
    """The hero is paid (from the asker's purse as far as it goes, the rest from what they can scrape together)."""
    from realmwalker.rules.items import money_text

    a = asker(game, sit)
    if a is not None:
        a.purse = max(0, int(getattr(a, "purse", 0) or 0) - int(amount))
    game.leader.money += int(amount)
    return [f"<loot>You are given {money_text(int(amount))}.</>"]


@op("disposition", "role", "int")
def _o_disp(game, sit, role, n):
    from realmwalker.game.people import change_disposition

    x = _npc(game, sit, role)
    if x is not None:
        change_disposition(x, int(n))


@op("standing", "int")
def _o_standing(game, sit, n):
    """The hero's standing with whoever holds the town."""
    from realmwalker.game import reputation
    from realmwalker.world import factions as fx

    owner = fx.owner_of(game.world, game.world.settlements[sit["town"]])
    if owner is not None:
        reputation.change_standing(game, owner.id, float(n))


def _story_item(game, sit, key: str):
    from realmwalker.rules.items import Item

    name = sit["words"].get(key) or _fill(game, sit, spec_of(game, sit).get("words", {}).get(key) or [key],
                                          f"item/{key}")
    base = spec_of(game, sit).get("base", "gold_ring")
    base = base if base in game.tables.items else "gold_ring"
    return Item(uid=0, def_id=base, qty=1, made_at=game.world.time, name=name, tags=[f"story:{sit['id']}"])


@op("item", "word")
def _o_item(game, sit, key):
    """A story thing comes into the hero's hands (tagged "story:<id>"): its name from the words (`key`)."""
    from realmwalker.rules.inventory import add_existing

    it = _story_item(game, sit, key)
    add_existing(game.leader, game.tables.items, it)
    return [f"<loot>You have {esc(it.name)}.</>"]


@op("plant", "role", "word")
def _o_plant(game, sit, role, key):
    """The situation's thing is in someone's keeping (a pawned ring, a stolen deed): in their pockets."""
    n = _npc(game, sit, role)
    if n is not None:
        n.inventory.append(_story_item(game, sit, key))


@op("hand", "role")
def _o_hand(game, sit, role):
    """Someone hands the situation's thing to the hero."""
    from realmwalker.rules.inventory import add_existing

    n = _npc(game, sit, role)
    tag = f"story:{sit['id']}"
    it = next((x for x in (n.inventory if n is not None else []) if tag in x.tags), None)
    if it is None:
        return []
    n.inventory.remove(it)
    add_existing(game.leader, game.tables.items, it)
    return [f"<loot>You have {esc(it.name or 'it')}.</>"]


@op("give_back", "role")
def _o_give_back(game, sit, role):
    """The hero gives the situation's thing to someone (back where it belongs)."""
    from realmwalker.rules.inventory import remove_item, unequip

    n = _npc(game, sit, role)
    tag = f"story:{sit['id']}"
    for c in game.party:
        for it in list(c.inventory):
            if tag in it.tags and n is not None:
                if c.slot_of(it.uid) is not None:
                    unequip(c, c.slot_of(it.uid))
                remove_item(c, it.uid)
                n.inventory.append(it)
                return [f"<info>You give {esc(it.name or 'it')} to {esc(n.first_name)}.</>"]
    return []


@op("thread")
def _o_thread(game, sit):
    """A threat's hand was behind it: its tale is offered (a thread into an adventure)."""
    from realmwalker.game import story
    from realmwalker.world import threats

    t = threats.records(game.world).get(sit.get("threat") or "")
    if t is not None and t.get("adventure") is None and t["state"] in threats.LIVE and story._can_take(game, t):
        story.offer_hook(game, t, game.world.settlements[sit["town"]])
    return []


@op("clock", "float")
def _o_clock(game, sit, factor):
    left = int(sit["clock"]["due"]) - _today(game)
    sit["clock"]["due"] = _today(game) + max(1, int(left * float(factor)))


@op("lay_scar")
def _o_lay_scar(game, sit):
    """The field of the dead the vignette is about is laid (past.restless no longer sends its dead)."""
    i = sit["root"].get("scar")
    scars = game.world.politics.get("scars") or []
    if i is not None and 0 <= int(i) < len(scars) and isinstance(scars[int(i)], dict):
        scars[int(i)]["laid"] = True
    return []


@op("price", "int")
def _o_price(game, sit, mult):
    sit["price_mult"] = int(mult)


@op("news", "word")
def _o_news(game, sit, key):
    from realmwalker.world import news

    s = game.world.settlements[sit["town"]]
    text = _fill(game, sit, spec_of(game, sit).get("words", {}).get(key) or [key], f"news/{key}")
    if text:
        news.add(game.world, text, s.x, s.y, kind="situation", importance=1, places=[s.id])


@op("step")
def _o_step(game, sit):
    """The adventure's step this situation is (C.10) is done: the witness tells the tale, the one who knows tells what
    it fears."""
    from realmwalker.game import story

    aid = sit.get("adventure")
    st = story.find_step(game, aid, sit.get("step"))
    if st is None or st["state"] != "open":
        return []
    out = story.step_told(game, story.adventures(game.world)[aid], st)
    story.step_done(game, aid, st["id"])
    return out


@op("key", "word")
def _o_key(game, sit, key):
    """A key of the adventure this situation belongs to (the hunter who will stand with you)."""
    from realmwalker.game.story import beats

    if not sit.get("adventure"):
        return []
    return beats.OPS["key"](game, {"adv": sit["adventure"]}, key) or []


@op("say", "word")
def _o_say(game, sit, key):
    text = _fill(game, sit, spec_of(game, sit).get("words", {}).get(key) or [key], f"say/{key}")
    return [esc(text)] if text else []


# ---------------------------------------------------------------------------- endings
def _ending_for(game, sit: dict, gid: str) -> dict | None:
    for e in spec_of(game, sit).get("endings", []):
        if e.get("when") == gid and all(_cond(game, sit, c) for c in e.get("if", [])):
            return e
    return None


def _on_goal(game, sit: dict, gid: str, way: str) -> None:
    if sit.get("predicament") not in predicaments(game.tables) or sit["state"] not in LIVE:
        return
    for op_ in [o for g in sit["goals"] if g["id"] == gid for o in g.get("then", [])]:
        for line in _op(game, sit, op_):
            game.say(line, "story")
    e = _ending_for(game, sit, gid)
    if e is not None:
        for line in finish(game, sit, e):
            game.say(line, "story")


goals.REACTIONS.append(_on_goal)


def finish(game, sit: dict, e: dict, lapsed: bool = False) -> list[str]:
    """The situation ends: the ending's ops written into the world, its line in the journal, the work closed, the
    people let go, and the town's gap begun."""
    from realmwalker.game import quests

    if sit["state"] not in LIVE:
        return []
    out = []
    sit["ending"] = e.get("id", "lapsed" if lapsed else "end")
    sit["tone"] = e.get("tone", "bitter")
    sit["state"] = "lapsed" if lapsed else ("failed" if sit["tone"] == "bitter" else "done")
    sit["ended"] = _today(game)
    out += _turn(game, sit, "end") if not lapsed and e.get("tone") == "good" else []
    for o in e.get("ops", []):
        out += _op(game, sit, o)
    forged = {o[1] for o in spec_of(game, sit).get("forge", []) if o[0] == "law"}
    for role in sit["roles"]:
        n = _npc(game, sit, role)
        law = n.flags.get("law") if n is not None and n.alive else None
        if law == "pardoned" or (law == "accused" and role in forged):
            n.flags.pop("law", None)  # (it is over: the pardoned are simply free; the matter it began is closed)
    line = _fill(game, sit, e.get("line"), f"end/{sit['ending']}")
    if line:
        sit["journal"].append(line)
        if sit.get("life") == _life(game):
            tag = {"good": "good", "mixed": "info", "bitter": "warn"}[sit["tone"]]
            out.insert(0, f"<{tag}>{esc(title(game, sit))}: {esc(line)}</>")
    q = quests.by_id(game, sit.get("quest"))
    if q is not None and q["state"] in quests.LIVE and not q["done"]:
        q["state"] = "finished"
        q["journal"].append("It is over, one way or another.")
    _unbind(game, sit)
    if not sit.get("adventure"):  # (an adventure's step leaves the town's own gap alone)
        s = game.world.settlements[sit["town"]]
        _next_gap(game, s, game.world.rng.child(f"situation/{sit['id']}/gap"))
    return out


# ---------------------------------------------------------------------------- inside adventures (C.10)
def inside(tables, kind: str, route: str | None = None) -> list[str]:
    """The predicaments an adventure's step of this kind (and talk route's role) may become."""
    return [pid for pid, p in sorted(predicaments(tables).items())
            if (p.get("inside") or {}).get("step") == kind and (p["inside"].get("route") or None) == route]


def for_step(game, adv: dict, st: dict, npc, route: str | None = None) -> dict | None:
    """An adventure's step met in its person's town may become a situation (ADVENTURES.md §5.16): the witness who will
    not speak, the hunter who will not hunt. Decided once a step (`st["inside"]`); the situation finishes the step
    (the op "step"), and its lapse never leaves the tale stuck."""
    if "inside" in st or npc is None or not npc.alive:
        return None
    pids = inside(game.tables, st["kind"], route)
    rng = game.world.rng.child(f"inside/{adv['id']}/{st['id']}")
    pid = rng.choice(pids) if pids else None
    st["inside"] = None
    if pid is None or not rng.chance(float(predicaments(game.tables)[pid]["inside"].get("chance", 1.0))):
        return None
    root = {"kind": "adventure", "key": f"adventure:{st['kind']}", "adv": adv["id"], "step": st["id"],
            "threat": adv.get("threat"), "npc": int(npc.id),
            "roles": {"asker": {"npc": int(npc.id), "settlement": int(npc.settlement), "job": npc.job}}}
    sit = make(game, int(npc.settlement), root=root, predicament=pid)
    if sit is None:
        return None
    sit["step"] = st["id"]
    st["inside"] = sit["id"]
    return sit


def of_step(game, st: dict) -> dict | None:
    """The live situation an adventure's step became, or None."""
    sit = records(game.world).get(st.get("inside") or "")
    return sit if sit is not None and sit["state"] in LIVE else None


def _moot(game, sit: dict) -> bool:
    """An adventure's situation whose step is over, or whose tale is no longer the hero's, simply ends."""
    from realmwalker.game import story

    if not sit.get("adventure"):
        return False
    adv = story.adventures(game.world).get(sit["adventure"])
    st = story.find_step(game, sit["adventure"], sit.get("step"))
    return adv is None or adv["state"] != "active" or st is None or st["state"] != "open"


def _drop(game, sit: dict) -> None:
    sit["state"], sit["ending"], sit["tone"], sit["ended"] = "lapsed", "moot", "mixed", _today(game)
    _unbind(game, sit)


def daily(game) -> None:
    """Once a day (story.daily): clocks run out (the world's own outcome), half-clock turns fire, and a town near the
    hero whose gap has passed may be given a new situation."""
    today = _today(game)
    for sit in list(goals.live(game)):
        if sit.get("predicament") not in predicaments(game.tables):
            continue
        if _moot(game, sit):
            _drop(game, sit)
            continue
        due = int(sit["clock"]["due"])
        if today >= due:
            lapse = spec_of(game, sit).get("lapse") or {"ops": [], "tone": "bitter"}
            for line in finish(game, sit, dict(lapse, id="lapsed"), lapsed=True):
                if sit.get("life") == _life(game):
                    game.say(line, "story")
            continue
        if not sit["clock"].get("half") and today >= (int(sit["made"]) + due) // 2:
            sit["clock"]["half"] = True
            for line in _turn(game, sit, "half"):
                game.say(line, "story")
    maybe_forge(game)


def on_death(game) -> None:
    """The hero is dead: their situations lose their work and go back to latent, keeping their clocks (an adventure's
    end with its tale)."""
    for sit in goals.live(game):
        if sit.get("adventure"):
            _drop(game, sit)
            continue
        sit["quest"] = None
        sit["state"] = "latent"
        sit["flags"] = [f for f in sit["flags"] if f != "taken"]
        sit["life"] = None
        if sit.get("meeting"):
            sit["meeting"]["state"] = "waiting"
        for role in sit["roles"]:
            n = _npc(game, sit, role)
            if n is not None and n.flags.get("with_party"):
                n.flags.pop("with_party", None)
                n.present = True


# ---------------------------------------------------------------------------- the journal
def troubles(game) -> list[dict]:
    """The hero's situations (met in this life), live first, newest first."""
    life = _life(game)
    mine = [s for s in records(game.world).values() if s.get("life") == life]
    return sorted(mine, key=lambda s: (s["state"] not in LIVE, -int(s.get("met") or 0), s["id"]))


STATE_WORDS = {"met": "seen", "taken": "taken on", "done": "over", "failed": "over, badly", "lapsed": "too late"}


def journal_lines(game, sit: dict) -> str:
    """A trouble in the journal: in the hero's own notes, what is at stake and by when, what stands in the way."""
    from realmwalker.game.quests import when_text

    w = game.world
    s = w.settlements[sit["town"]]
    lines = [f"<title>{esc(title(game, sit))}</>", f"<dim>{esc(s.name)} · {STATE_WORDS.get(sit['state'], '')}</>", ""]
    for line in sit["journal"]:
        lines.append(esc(line))
    if sit["state"] in LIVE:
        lines += ["", f"<title>At stake</> {esc(sit['words'].get('stakes', ''))}",
                  f"<dim>Time: {esc(when_text(game, int(sit['clock']['due'])))}.</>"]
        standing = [ob for ob in sit["obstacles"] if ob["state"] == "standing"]
        if standing and sit["state"] == "taken":
            lines += ["", "<title>In the way</>"]
            for ob in standing:
                lines.append(f"<warn>-</> {esc(_fill(game, sit, ob.get('note') or [ob['kind']], f'ob/{ob['id']}'))}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------- the start-up check
def problems(tables) -> list[str]:
    """Every predicament reads right: its roles bind by known kinds, its tests are goals.py tests, its acts, endings,
    turns and ops are known, its meetings name scenes that exist (story/check.py)."""
    out = []
    d = getattr(tables, "situations", None) or {}
    preds = predicaments(tables)
    scenes = getattr(tables, "scenes", {}) or {}
    meets = d.get("meetings") or {}
    for key, lst in (d.get("roots") or {}).items():
        kind = key.split(":", 1)[0]
        if kind not in ROOTS and kind != "town":
            out.append(f"situations.json: the root '{key}' is of no kind the game gathers.")
        for pid in lst:
            if pid not in preds:
                out.append(f"situations.json: the root '{key}' names the predicament '{pid}', which is not written.")
    for mid, m in meets.items():
        if m.get("scene") not in scenes:
            out.append(f"situations.json: the meeting '{mid}' plays the scene '{m.get('scene')}', which is not in "
                       f"scenes.json.")
    for tid, t in (d.get("turns") or {}).items():
        if t.get("when", "take") not in WHEN:
            out.append(f"situations.json: the turn '{tid}' fires '{t.get('when')}', which is not a time the game knows.")
        for o in t.get("ops", []):
            out += _op_problem(o, None, f"turn {tid}")
    for pid, p in preds.items():
        where = f"situations.json: {pid}"
        roles = set(p.get("roles", {}))
        for role, rs in p.get("roles", {}).items():
            if rs.get("bind") not in BINDS:
                out.append(f"{where}: the role '{role}' binds by '{rs.get('bind')}', which is not a way the game binds.")
            if rs.get("of") is not None and rs["of"] not in roles:
                out.append(f"{where}: the role '{role}' is of '{rs['of']}', which is not a role.")
        if p.get("asks", "asker") not in roles:
            out.append(f"{where}: the one who asks ('{p.get('asks', 'asker')}') is not a role.")
        if p.get("inside"):
            from realmwalker.game.story.steps import STEPS

            if p["inside"].get("step") not in STEPS:
                out.append(f"{where}: it is inside a step of the kind '{p['inside'].get('step')}', which is not one.")
            if (p["roles"].get("asker") or {}).get("bind") != "given":
                out.append(f"{where}: the step's person is the one who asks (the role 'asker', bound 'given').")
            if not any(o and o[0] == "step" for e in p.get("endings", []) for o in e.get("ops", [])):
                out.append(f"{where}: no ending finishes the adventure's step (the op 'step').")
        for m in p.get("meetings", []):
            if m not in meets:
                out.append(f"{where}: the meeting '{m}' is not one of situations.json's meetings.")
            else:
                cast = dict(meets[m].get("cast", {}))
                cast.update({k: v for k, v in (p.get("parts") or {}).items() if k in cast})
                for r in cast.values():
                    if r not in roles:
                        out.append(f"{where}: the meeting '{m}' casts the role '{r}', which it does not have.")
        ids = {g.get("id") for g in p.get("goals", [])}
        for g in p.get("goals", []):
            for o in g.get("then", []):
                out += _op_problem(o, roles, f"{pid} goal {g.get('id')}")
        tones = set()
        for e in p.get("endings", []):
            if e.get("when") not in ids:
                out.append(f"{where}: the ending '{e.get('id')}' waits for the goal '{e.get('when')}', which it has not.")
            tones.add(e.get("tone"))
            for c in e.get("if", []):
                out += _cond_problem(c, ids, f"{pid} ending {e.get('id')}")
            for o in e.get("ops", []):
                out += _op_problem(o, roles, f"{pid} ending {e.get('id')}")
        if not tones & {"bitter", "mixed"} and not p.get("lapse"):
            out.append(f"{where}: every predicament has at least one bitter or mixed ending.")
        for o in (p.get("lapse") or {}).get("ops", []) + p.get("forge", []):
            out += _op_problem(o, roles, f"{pid} lapse")
        acts = [(a, ob) for ob in p.get("obstacles", []) for a in ob.get("acts", [])] + \
            [(a, None) for a in p.get("acts", [])]
        for a, ob in acts:
            who = a.get("who", (ob or {}).get("who"))
            if who not in roles:
                out.append(f"{where}: the act '{a.get('id')}' is done with '{who}', who is not a role.")
            if a.get("check") and a["check"][0] not in CHECK_SKILLS:
                out.append(f"{where}: the act '{a.get('id')}' checks '{a['check'][0]}', which is not a skill it may.")
            if a.get("way") and a["way"] not in goals.WAYS:
                out.append(f"{where}: the act '{a.get('id')}' is the way '{a['way']}', which is not a way.")
            for c in a.get("needs", []) + a.get("unless", []):
                out += _cond_problem(c, ids, f"{pid} act {a.get('id')}")
            for o in a.get("then", []) + a.get("fail", []):
                out += _op_problem(o, roles, f"{pid} act {a.get('id')}")
        w = p.get("work")
        if w and w.get("kind") not in WORKS:
            out.append(f"{where}: the work '{w.get('kind')}' is not work a situation can set.")
    return out


def _cond_problem(c: str, goal_ids: set, where: str) -> list[str]:
    raw = c[4:] if c.startswith("not:") else c
    kind, _, arg = raw.partition(":")
    if kind not in CONDS:
        return [f"situations.json: {where}: the condition '{c}' is not one the game knows."]
    if kind == "goal" and arg not in goal_ids:
        return [f"situations.json: {where}: the condition '{c}' names a goal it has not."]
    return []


def _op_problem(o, roles, where: str) -> list[str]:
    if not isinstance(o, list) or not o or o[0] not in OPS:
        return [f"situations.json: {where}: {o!r} is not an op the game knows."]
    args = OP_ARGS[o[0]]
    if len(o) - 1 != len(args):
        return [f"situations.json: {where}: '{o[0]}' takes {len(args)} argument(s)."]
    out = []
    for kind, a in zip(args, o[1:]):
        if kind == "role" and roles is not None and a not in roles:
            out.append(f"situations.json: {where}: '{o[0]}' names the role '{a}', which is not one of it.")
        if kind == "fate" and a not in ("alive", "home", "gone", "ruined", "jailed", "dead"):
            out.append(f"situations.json: {where}: '{a}' is not a fate.")
        if kind == "law" and a not in goals.LAW_STATES:
            out.append(f"situations.json: {where}: '{a}' is not a state of the law.")
    return out
