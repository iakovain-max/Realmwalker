"""Threats: the darkness in the world (Expansion 6, docs/ADVENTURES.md §5.1, §8.3).

A threat is a danger with a will behind it (a named beast, a dead king, a gang's captain...), made from what the
history left, living in `world.politics["threats"]` whether or not the player cares. World layer: no GameState, so it
moves in the interlude between lives too (at most `interlude_stages` stages there).

- `seed(world, tables, rng)` at world creation, after the ages: a dormant threat for every source the history left
  (Part A: the named beasts in `politics["lairs"]`), and a few of them stirring, within the world's budget.
- `advance(politics, days)` from `Politics.advance`: dormant threats may stir; a stirring or active threat's scheme
  moves stage by stage on its clock (signs through `world/news.add` first, the stage's effects a week later); the
  last stage is its doom, bounded and recoverable (an emptied village keeps a floor of its people and comes back);
  the history's beast-hunters keep hunting; a threat whose villain is gone ends.
- `seed_from(politics, kind, **refs)` while you play: a beast that comes down wakes (or makes) its threat.

STAGE_OPS are what a stage may do to the world when its effects come (threats.json `effects`); story/check.py reports
any other.
"""

from __future__ import annotations

import math

from realmwalker.core import textgen

STAGE_OPS: dict[str, object] = {}
STATES = ("dormant", "stirring", "active", "ended")
LIVE = ("stirring", "active")


def stage_op(name: str):
    """fn(politics, threat, *args)"""
    def wrap(fn):
        STAGE_OPS[name] = fn
        return fn
    return wrap


# ---------------------------------------------------------------------------- the records
def records(world) -> dict:
    return world.politics.setdefault("threats", {})


def live(world) -> list[dict]:
    return [t for t in sorted(records(world).values(), key=lambda t: int(t["id"][1:])) if t["state"] in LIVE]


def home_xy(world, t: dict) -> tuple[int, int]:
    home = t["home"]
    if "site" in home:
        s = world.sites[home["site"]]
    else:
        s = world.settlements[home["settlement"]]
    return s.x, s.y


def home_name(world, t: dict) -> str:
    home = t["home"]
    return world.sites[home["site"]].name if "site" in home else world.settlements[home["settlement"]].name


def distance(world, t: dict, x: int, y: int) -> float:
    hx, hy = home_xy(world, t)
    return math.hypot(hx - x, hy - y)


def tier_for(tables, kind: dict, danger: int) -> int:
    tier = 1
    for least, t in tables.threats.get("tier_by_danger", [[0, 1]]):
        if danger >= least:
            tier = t
    lo, hi = kind["tiers"]
    return max(lo, min(hi, tier))


def villain_figure(world, t: dict):
    fid = t["villain"].get("figure")
    return world.figures.get(fid) if fid is not None else None


def villain_name(world, t: dict) -> str:
    fig = villain_figure(world, t)
    if fig is None:
        return t["villain"].get("name", "something")
    return f"{fig.name} {fig.epithet}".strip() if fig.kind == "beast" else fig.full_name()


def _new_id(world) -> str:
    n = int(world.politics.get("next_threat", 0))
    world.politics["next_threat"] = n + 1
    return f"T{n}"


def make(world, tables, rng, kind_id: str, *, source: dict, home: dict, figure=None, day: float = 0.0) -> dict:
    kind = tables.threats["kinds"][kind_id]
    t = {"id": _new_id(world), "kind": kind_id, "tier": 1, "state": "dormant", "source": source, "home": home,
         "villain": {"figure": figure.id if figure is not None else None,
                     "creature": getattr(figure, "creature", "") if figure is not None else "",
                     "temper": rng.choice(kind["tempers"]) if kind["tempers"] else None},
         "stakes": [], "scheme": {"stages": [s["id"] for s in kind["stages"]], "stage": -1, "since": None,
                                  "next": None, "effects_on": None, "applied": False, "held_until": None},
         "lieutenants": [], "signs": [], "offer": None, "adventure": None, "born": float(day), "ended": None,
         "outcome": None}
    hx, hy = home_xy(world, t)
    t["tier"] = tier_for(tables, kind, int(world.danger[hx, hy]))
    t["villain"]["name"] = villain_name(world, t)
    t["reach"] = {"x": hx, "y": hy, "r": int(kind["reach"])}
    near = sorted((math.hypot(s.x - hx, s.y - hy), s.id) for s in world.settlements
                  if math.hypot(s.x - hx, s.y - hy) <= kind["reach"])
    t["stakes"] = [sid for _, sid in near]
    records(world)[t["id"]] = t
    return t


# ---------------------------------------------------------------------------- at world creation
def seed(world, tables, rng) -> None:
    """Dormant threats from what the history left, and a few stirring within the budget."""
    kinds = tables.threats.get("kinds", {})
    if "beast" in kinds:
        for key, hid in sorted(world.politics.get("lairs", {}).items(), key=lambda kv: int(kv[0])):
            fig = world.figures.get(hid)
            if fig is None or not fig.alive or fig.kind != "beast" or not 0 <= int(key) < len(world.sites):
                continue
            make(world, tables, rng.child(f"beast/{key}"), "beast", source={"kind": "lairs", "site": int(key),
                                                                            "figure": fig.id},
                 home={"site": int(key)}, figure=fig, day=0.0)
    lo, hi = budget(world, tables)
    dormant = [t for t in sorted(records(world).values(), key=lambda t: int(t["id"][1:])) if t["state"] == "dormant"]
    rng.shuffle(dormant)
    want = rng.randint(lo, hi) if hi >= lo else 0
    for t in dormant[:want]:
        stir(world, tables, t, rng, day=0.0)


def budget(world, tables) -> tuple[int, int]:
    b = tables.threats.get("budget", {}).get(world.meta.size, [3, 5])
    return int(b[0]), int(b[1])


# ---------------------------------------------------------------------------- the clock
def stage_length(tables, t: dict, stage: dict, rng) -> float:
    lo, hi = stage["days"]
    days = tables.threats.get("stage_days", {})
    base, mine = days.get("1", [lo, hi]), days.get(str(t["tier"]), [lo, hi])
    stretch = (mine[0] + mine[1]) / max(1.0, base[0] + base[1])
    return float(rng.uniform(lo, hi) * stretch)


def stages(tables, t: dict) -> list[dict]:
    return tables.threats["kinds"][t["kind"]]["stages"]


def stir(world, tables, t: dict, rng, *, day: float) -> None:
    """Dormant to stirring: the scheme's first stage begins (its signs now, its effects a week on)."""
    t["state"] = "stirring"
    _begin_stage(world, tables, t, 0, rng, day)


def _begin_stage(world, tables, t: dict, i: int, rng, day: float) -> None:
    st = stages(tables, t)[i]
    sch = t["scheme"]
    sch["stage"] = i
    sch["since"] = float(day)
    sch["next"] = float(day) + stage_length(tables, t, st, rng)
    sch["effects_on"] = float(day) + float(tables.threats.get("sign_lead_days", 7))
    sch["applied"] = False
    if i > 0:
        t["state"] = "active"
    _sign(world, tables, t, st, rng, day)


def _words(world, t: dict, rng) -> dict:
    hx, hy = home_xy(world, t)
    area = world.area_at(hx, hy)
    place = next((world.settlements[s].name for s in t["stakes"]), home_name(world, t))
    return {"villain": villain_name(world, t), "home": home_name(world, t), "place": place,
            "area": area.name if area is not None else "the wild country"}


def _sign(world, tables, t: dict, st: dict, rng, day: float) -> None:
    from realmwalker.world import news

    text = textgen.fill(rng.choice(st["signs"]), rng, {}, _words(world, t, rng))
    text = text[:1].upper() + text[1:]
    hx, hy = home_xy(world, t)
    item = news.add(world, text, hx, hy, kind="threat_sign", importance=2, places=t["stakes"][:1], day=day)
    t["signs"].append(int(item["id"]))


def advance(pol, days: float) -> None:
    """A week of the world's threats (from Politics.advance)."""
    w, tables = pol.w, pol.t
    if not tables.threats.get("kinds"):
        return
    day = pol.day
    interlude = bool(w.politics.get("interlude"))
    limit = int(tables.threats.get("interlude_stages", 1))
    for t in sorted(records(w).values(), key=lambda t: int(t["id"][1:])):
        if t["state"] == "ended":
            continue
        if not _villain_lives(w, t):
            end(w, t, "slain" if villain_figure(w, t) is not None else "gone", day)
            continue
        if t["state"] == "dormant":
            if pol.rng.chance(float(tables.threats.get("wake", 0.0)) * days / 7.0) and room_for(w, tables, t):
                stir(w, tables, t, pol.rng, day=day)
            continue
        sch = t["scheme"]
        held = sch.get("held_until") is not None and day < float(sch["held_until"])
        if not sch["applied"] and day >= float(sch["effects_on"]) and not held:
            apply_stage(pol, t)
            if t["state"] == "ended":
                continue
        if day >= float(sch["next"]) and sch["applied"] and not held:
            if interlude and int(t.get("interlude_moved", 0)) >= limit:
                continue
            nxt = sch["stage"] + 1
            if nxt < len(stages(tables, t)):
                _begin_stage(w, tables, t, nxt, pol.rng, day)
                if interlude:
                    t["interlude_moved"] = int(t.get("interlude_moved", 0)) + 1
        _hunted(pol, t)
    _recover(pol)


def apply_stage(pol, t: dict) -> None:
    st = stages(pol.t, t)[t["scheme"]["stage"]]
    t["scheme"]["applied"] = True
    for op in st.get("effects", []):
        STAGE_OPS[op[0]](pol, t, *op[1:])
    if st.get("doom"):
        if not t.get("grown") and t["tier"] < pol.t.threats["kinds"][t["kind"]]["tiers"][1]:
            t["tier"] += 1  # (a doom raises its threat's tier once, at most)
            t["grown"] = True
        end(pol.w, t, "doom", pol.day)


def end(world, t: dict, outcome: str, day: float) -> None:
    t["state"] = "ended"
    t["outcome"] = outcome
    t["ended"] = float(day)
    t["offer"] = None


def _villain_lives(world, t: dict) -> bool:
    fig = villain_figure(world, t)
    if fig is None:
        return t["villain"].get("figure") is None
    if not fig.alive:
        return False
    if t["kind"] == "beast":
        return str(t["home"].get("site")) in world.politics.get("lairs", {}) and \
            world.politics["lairs"][str(t["home"]["site"])] == fig.id
    return True


def room_for(world, tables, t: dict) -> bool:
    """Whether another threat may stir: the world's budget, and at most a few untaken near the hero."""
    lo, hi = budget(world, tables)
    if len(live(world)) >= hi:
        return False
    at = world.politics.get("director", {}).get("at")
    near = tables.threats.get("near_hero", {"tiles": 30, "untaken": 2})
    if at is not None and distance(world, t, at[0], at[1]) <= near["tiles"]:
        untaken = [o for o in live(world) if o.get("adventure") is None
                   and distance(world, o, at[0], at[1]) <= near["tiles"]]
        if len(untaken) >= near["untaken"]:
            return False
    return True


# ---------------------------------------------------------------------------- the world fights back
def _hunted(pol, t: dict) -> None:
    """The history's beast-hunters go on hunting while you play: now and then one of them brings a beast down."""
    if t["kind"] != "beast" or t.get("adventure") is not None or t["state"] not in LIVE:
        return
    w = pol.w
    spec = pol.t.threats.get("hunters")
    if not spec:
        return
    hx, hy = home_xy(w, t)
    hunters = []
    for fig in w.figures.values():
        if not fig.alive or fig.role != "hero" or fig.kind != "person" or not str(fig.home).startswith("S"):
            continue
        sid = int(fig.home[1:]) if fig.home[1:].isdigit() else -1
        if 0 <= sid < len(w.settlements) and math.hypot(w.settlements[sid].x - hx, w.settlements[sid].y - hy) <= 40:
            hunters.append(fig)
    if not hunters:
        return
    hero = max(hunters, key=lambda f: (f.fame, -f.id))
    beast = villain_figure(w, t)
    chance = float(spec["chance"]) + float(spec["per_fame"]) * max(0, hero.fame - (beast.fame if beast else 0))
    if not pol.rng.chance(chance):
        return
    site = t["home"]["site"]
    beast.died = pol.year
    beast.cause = f"slain by {hero.full_name()}"
    beast.died_at = f"X{site}"
    w.politics.get("lairs", {}).pop(str(site), None)
    hero.kills.append(beast.id)
    hero.fame += 2
    words = {"hero": hero.full_name(), "beast": villain_name(w, t), "home": home_name(w, t)}
    pol.say("threat_hunted", words, where=(hx, hy), importance=3, figures=[hero.id, beast.id])
    end(w, t, "hunted", pol.day)


def _recover(pol) -> None:
    """Dooms are bounded: an emptied place fills again (rebuilding), and in time is itself again."""
    w = pol.w
    spec = pol.t.threats.get("emptied", {"floor": 0.2, "rebuild_days": 90})
    for s in w.settlements:
        e = s.status.get("emptied")
        if isinstance(e, dict) and pol.day >= float(e.get("until", 0)):
            del s.status["emptied"]
            was = int(e.get("was", s.population))
            s.population = max(s.population, int(was * 0.5))
            s.status["rebuilding"] = {"since": pol.day, "until": pol.day + float(spec["rebuild_days"]), "was": was}
            pol.say("threat_rebuilding", {"place": s.name}, where=(s.x, s.y), importance=2, places=[s])
        r = s.status.get("rebuilding")
        if isinstance(r, dict) and pol.day >= float(r.get("until", 0)):
            del s.status["rebuilding"]
            s.population = max(s.population, int(int(r.get("was", s.population)) * 0.8))


# ---------------------------------------------------------------------------- while you play
def seed_from(pol, kind: str, *, figure=None, site: int | None = None) -> dict | None:
    """Something politics did may wake a threat (a beast came down): its own if it has one, else a new one."""
    w, tables = pol.w, pol.t
    if kind not in tables.threats.get("kinds", {}):
        return None
    for t in records(w).values():
        if t["state"] != "ended" and figure is not None and t["villain"].get("figure") == figure.id:
            if t["state"] == "dormant" and room_for(w, tables, t):
                stir(w, tables, t, pol.rng, day=pol.day)
            return t
    if kind == "beast" and figure is not None and site is not None:
        t = make(w, tables, pol.rng.child(f"beast/{site}/{int(pol.day)}"), "beast",
                 source={"kind": "lairs", "site": int(site), "figure": figure.id}, home={"site": int(site)},
                 figure=figure, day=pol.day)
        if room_for(w, tables, t):
            stir(w, tables, t, pol.rng, day=pol.day)
        return t
    return None


# ---------------------------------------------------------------------------- what a stage does
def _in_reach(world, t: dict, kinds=("hamlet", "village", "town")) -> list:
    return [world.settlements[s] for s in t["stakes"] if world.settlements[s].kind in kinds]


@stage_op("status")
def _status(pol, t: dict, key: str, how: str = "nearest") -> None:
    """A status on the settlements it threatens (the nearest, or every one in reach) for as long as the stage."""
    towns = _in_reach(pol.w, t)
    if how == "nearest":
        towns = towns[:1]
    until = float(t["scheme"]["next"]) + 7.0
    for s in towns:
        s.status[key] = {"until": until, "since": pol.day, "by": villain_name(pol.w, t), "threat": t["id"]}


@stage_op("danger")
def _danger(pol, t: dict, n: int) -> None:
    """The country round its home grows more dangerous (the region's danger, for encounters and the tier)."""
    w = pol.w
    hx, hy = home_xy(w, t)
    r = max(2, int(t["reach"]["r"]) // 2)
    x0, x1 = max(0, hx - r), min(w.width, hx + r + 1)
    y0, y1 = max(0, hy - r), min(w.height, hy + r + 1)
    land = w.danger[x0:x1, y0:y1] > 0
    w.danger[x0:x1, y0:y1][land] = (w.danger[x0:x1, y0:y1][land].astype(int) + int(n)).clip(1, 10)
    t.setdefault("danger_added", []).append([hx, hy, r, int(n)])


@stage_op("emptied")
def _emptied(pol, t: dict, which: str = "nearest") -> None:
    """The doom: the nearest small place it threatens empties, keeping a floor of its people, until it fills again."""
    from realmwalker.world.history import remember

    w = pol.w
    towns = _in_reach(w, t, ("hamlet", "village")) or _in_reach(w, t)
    if not towns:
        return
    s = towns[0]
    spec = pol.t.threats.get("emptied", {"floor": 0.2, "rebuild_days": 90})
    was = s.population
    s.population = max(10, int(s.population * float(spec["floor"])))
    s.status["emptied"] = {"since": pol.day, "until": pol.day + float(spec["rebuild_days"]), "was": was,
                           "by": villain_name(w, t), "threat": t["id"]}
    text = pol.say("threat_emptied", {"villain": villain_name(w, t), "place": s.name}, where=(s.x, s.y),
                   importance=2, places=[s])
    remember(w, pol.year, "emptied", text, importance=3, places=[s.id],
             figures=[t["villain"]["figure"]] if t["villain"].get("figure") is not None else [])
