"""Sequel threats (Expansion 6 G.4, docs/ADVENTURES.md §5.1, §5.4, §5.9): what a tale's ending leaves behind to come
back.

Three kinds, each a real threat in `world.politics["threats"]`, asleep for some weeks and then stirring for sure
(world/threats.advance wakes a dormant threat with `sequel` once its `held_until` is past):
- "returns" (E.4, endings' `sequel` op): the villain itself, put down without its anchor;
- "heir" (the op `sequel_threat` "heir"): a slain beast's get, a new beast figure (`parent` the old one, its names
  from adventures consequences `sequels.heir`) in a free lair near the old one, with its own threat;
- "vacuum" (`sequel_threat` "vacuum"): a broken band leaves a gap on the roads, and a new gang fills it
  (`Politics.new_gang(quiet=True)`, its outlaw threat made here, asleep).
A sequel made here keeps `t["sequel_of"]` {adv, life, kind, told}; the tale forged on it later keeps `adv["sequel_of"]`
(the Legends book links the two chapters). The hero who ended the first tale hears when it stirs (`daily`, from
story.daily: a line in the log, once). The fled lieutenant's sequel is E.3's nemesis (lieutenants.after_tale).

`of_tale(game, adv)` is (kind, threat) for the sequel a tale left (the epilogue's page about it), or None.
"""

from __future__ import annotations

import math

from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story.endings import consequence

KINDS = ("heir", "vacuum", "returns")


def spec(game) -> dict:
    return (game.tables.adventures.get("consequences", {}) or {}).get("sequels", {}) or {}


def _rng(game, adv: dict, what: str):
    return game.world.rng.child(f"sequel/{adv['id']}/{what}")


def _day(game) -> float:
    from realmwalker.world import news

    return float(news.now_days(game.world))


def _asleep(game, adv: dict, t: dict, kind: str, days) -> None:
    """The new threat sleeps its weeks, then stirs for sure; it remembers the tale it came out of."""
    from realmwalker.game.story import forge

    lo, hi = (list(days) + [60, 120])[:2] if days else (60, 120)
    t["state"] = "dormant"
    t["sequel"] = kind
    t["sequel_of"] = {"adv": adv["id"], "life": forge.life_of(game), "kind": kind}
    t["scheme"]["held_until"] = _day(game) + _rng(game, adv, "days").randint(int(lo), int(hi))
    adv["sequel"] = {"kind": kind, "threat": t["id"]}


@consequence("sequel_threat")
def _sequel_threat(game, adv, kind: str = "heir", chance: float = 1.0) -> list[str]:
    """Something the tale's ending leaves to come back: the beast's heir, or the gang that fills the gap."""
    if adv.get("sequel") or not _rng(game, adv, "chance").chance(float(chance)):
        return []
    t = heir(game, adv) if kind == "heir" else vacuum(game, adv) if kind == "vacuum" else None
    if t is not None:
        _asleep(game, adv, t, kind, spec(game).get(kind, {}).get("days"))
    return []


def _old_threat(game, adv: dict) -> dict | None:
    from realmwalker.world import threats

    return threats.records(game.world).get(adv["threat"])


def _free_lair(game, t: dict, kinds, rng):
    """A lair for the heir: a cave or ruin nobody holds, no beast's nor barrow king's, not yet walked, near the old."""
    w = game.world
    pol = w.politics
    hx, hy = t["reach"]["x"], t["reach"]["y"]
    reach = 2.0 * float(t["reach"].get("r", 12))
    taken = set(pol.get("lairs", {})) | set(pol.get("tombs", {}))
    near = sorted((math.hypot(s.x - hx, s.y - hy), s.id) for s in w.sites
                  if s.kind in kinds and s.faction < 0 and str(s.id) not in taken
                  and s.id != t["home"].get("site") and f"{s.x},{s.y}/1" not in w.local_maps
                  and math.hypot(s.x - hx, s.y - hy) <= reach)
    if not near:
        return None
    return w.sites[rng.choice(near[:3])[1]]


def heir(game, adv: dict) -> dict | None:
    """A slain beast's get: a new beast of its kind in a free lair near the old one, and its threat, asleep."""
    from realmwalker.core import textgen
    from realmwalker.world import factions as fx, threats

    t = _old_threat(game, adv)
    if t is None or t["kind"] != "beast":
        return None
    old = threats.villain_figure(game.world, t)
    sp = spec(game).get("heir") or {}
    if old is None or old.kind != "beast" or not sp.get("names"):
        return None
    rng = _rng(game, adv, "heir")
    btype = game.tables.history.get("beasts", {}).get(old.race, {})
    site = _free_lair(game, t, tuple(sorted(set(btype.get("lairs") or ()) | {"cave", "ruin"})), rng)  # (a den, or a ruin)
    if site is None:
        return None
    w = game.world
    year = int(game.moment.year)
    she = rng.choice(["male", "female"])
    fig = fx.Figure(id=w.next_figure_id, name=textgen.fill(rng.choice(sp["names"]), rng, {}, {"beast": old.name}),
                    sex=she, race=old.race, culture="", born=year, role="beast", kind="beast",
                    creature=old.creature, home=f"X{site.id}", epithet=rng.choice(sp.get("epithets") or [""]),
                    fame=1, parent=old.id)
    if old.sex == "female":
        fig.mother = old.id
    else:
        fig.father = old.id
    w.next_figure_id += 1
    w.figures[fig.id] = fig
    w.politics.setdefault("lairs", {})[str(site.id)] = fig.id
    return threats.make(w, game.tables, rng.child("threat"), "beast",
                        source={"kind": "lairs", "site": site.id, "figure": fig.id, "heir_of": old.id},
                        home={"site": site.id}, figure=fig, day=_day(game))


def vacuum(game, adv: dict) -> dict | None:
    """A band broken leaves a gap on the roads: a new gang fills it, and its threat sleeps a while."""
    from realmwalker.game import past
    from realmwalker.world import factions as fx, threats

    t = _old_threat(game, adv)
    if t is None or t["kind"] != "outlaw":
        return None
    pol = past._politics(game)
    gang = pol.new_gang(near=(t["reach"]["x"], t["reach"]["y"]), quiet=True)
    if gang is None:
        return None
    leader = fx.leader_of(game.world, gang)
    if leader is None:
        return None
    return threats.make(game.world, game.tables, _rng(game, adv, "vacuum"), "outlaw",
                        source={"kind": "gangs", "faction": gang.id, "site": gang.site, "figure": leader.id,
                                "gap_of": t["source"].get("faction")},
                        home={"site": gang.site}, figure=leader, day=_day(game))



def of_tale(game, adv: dict) -> tuple[str, dict] | None:
    """(kind, threat) for what a tale left behind to come back, or None."""
    from realmwalker.world import threats

    recs = threats.records(game.world)
    rec = adv.get("sequel") or {}
    t = recs.get(rec.get("threat", ""))
    if t is not None and t["state"] != "ended":
        return rec["kind"], t
    t = recs.get(adv["threat"])
    if t is not None and t.get("sequel") == "returns" and (t.get("returns") or {}).get("adv") == adv["id"] \
            and t["state"] != "ended":
        return "returns", t
    return None


def words(game, adv: dict, t: dict) -> dict:
    """The sequel threat's names for the words: its place, its heir, its gang."""
    from realmwalker.world import threats

    w = game.world
    out = {"place": threats.home_name(w, t), "heir": threats.villain_name(w, t)}
    gang = threats.gang_of(w, t)
    out["gang"] = gang.name if gang is not None else "a new band"
    return out


def daily(game) -> None:
    """A sequel of this hero's own tale stirs: they hear of it, once (a line in the log)."""
    from realmwalker.game import story
    from realmwalker.game.story import consequences, forge
    from realmwalker.world import threats

    life = forge.life_of(game)
    for t in sorted(threats.records(game.world).values(), key=lambda t: int(t["id"][1:])):
        rec = t.get("sequel_of")
        if not rec or rec.get("told") or rec.get("life") != life or t["state"] not in threats.LIVE:
            continue
        rec["told"] = int(game.moment.total_days)
        adv = story.adventures(game.world).get(rec.get("adv"))
        if adv is None:
            continue
        line = consequences._words(game, adv, f"sequel_told_{rec['kind']}", _rng(game, adv, "told"),
                                   **words(game, adv, t))
        if line:
            game.say(f"<warn>{esc(line)}</>", "story")
