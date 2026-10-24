"""Endings (docs/ADVENTURES.md §5.9, §8.6): which ending an adventure reaches, and what the world keeps of it.

An ending is chosen from the blueprint's ordered list: the first whose `if` holds wins, and the last has none. Its
`ops` are consequence operations, applied through the world's own systems (past.beast_slain, quests.site_cleared,
history.remember, the news...), never beside them. Both are whitelists: ending conditions in `CONDITIONS` (a name)
or `PREFIXES` ("key:", "flag:"...), ops in `OPS`, filled with `@ending_if` and `@consequence`; story/check.py
reports anything else.

`finish(game, adv)` ends a tale: the ending, its ops, the epilogue's pages (written once and kept), the epithet
offered (`Renown.legend["offered"]`), and the epilogue screen waiting (`game.epilogue`).
"""

from __future__ import annotations

from realmwalker.core import textgen

CONDITIONS: dict[str, object] = {}
PREFIXES: dict[str, object] = {}
OPS: dict[str, object] = {}
WON = ("slain", "laid_to_rest", "destroyed", "broken", "pardoned", "redeemed")  # (endings the hero won)


def ending_if(name: str):
    """fn(game, adv, arg) -> bool; a name ending in ':' is a prefix ("key:anchor")."""
    def wrap(fn):
        (PREFIXES if name.endswith(":") else CONDITIONS)[name] = fn
        return fn
    return wrap


def consequence(name: str):
    """fn(game, adv, *args) -> list of lines said"""
    def wrap(fn):
        OPS[name] = fn
        return fn
    return wrap


def known_condition(text: str) -> bool:
    if text in CONDITIONS:
        return True
    return any(text.startswith(p) and len(text) > len(p) for p in PREFIXES)


def holds(game, adv: dict, text: str) -> bool:
    if text in CONDITIONS:
        return bool(CONDITIONS[text](game, adv, None))
    for p, fn in PREFIXES.items():
        if text.startswith(p):
            return bool(fn(game, adv, text[len(p):]))
    return False


def choose(game, adv: dict) -> dict:
    from realmwalker.game.story.check import BUILT_PARTS

    bp = game.tables.adventures["blueprints"][adv["blueprint"]]
    for e in bp["endings"]:
        if e.get("from_part", "A") not in BUILT_PARTS:
            continue
        if all(holds(game, adv, c) for c in e.get("if", [])):
            return e
    return bp["endings"][-1]


def finish(game, adv: dict) -> list[str]:
    """The tale ends: the ending's consequences, the epilogue written and waiting, the epithet offered."""
    from realmwalker.game.story import words as wordsmod
    from realmwalker.world import news, threats

    if adv["state"] != "active":
        return []
    e = choose(game, adv)
    adv["ending"] = e["id"]
    lines: list[str] = []
    for op in e["ops"]:
        lines += OPS[op[0]](game, adv, *op[1:]) or []
    adv["state"] = "won" if e["id"] in WON else "abandoned" if e["id"] == "abandoned" else "lost"
    adv["ended"] = float(news.now_days(game.world))
    rng = game.world.rng.child(f"epilogue/{adv['id']}")
    words = wordsmod.for_adventure(game, adv)
    tables = game.tables.adventures.get("words", {})
    adv["epilogue"] = [{"about": about, "text": textgen.fill(rng.choice(lst), rng, tables, words)}
                       for about, lst in e.get("pages", {}).items() if about == "hero" or about == "place"
                       or adv["cast"].get(about)]
    t = threats.records(game.world).get(adv["threat"])
    if t is not None and t.get("adventure") == adv["id"]:
        t["adventure"] = None  # (the threat goes on in the world if it was not ended)
    bp = game.tables.adventures["blueprints"][adv["blueprint"]]
    if adv["state"] == "won" and bp.get("epithets"):
        offered = []
        for tag in bp["epithets"]:
            for ep in game.tables.adventures.get("epithets", {}).get(tag, []):
                text = textgen.fill(ep, rng, tables, words)
                if text not in offered:
                    offered.append(text)
        rng.shuffle(offered)
        game.renown.legend["offered"] = offered[:3]
    game.epilogue = {"adv": adv["id"]}
    return lines


# ---------------------------------------------------------------------------- conditions
@ending_if("boss_dead")
def _boss_dead(game, adv, arg) -> bool:
    return bool(adv.get("boss_dead"))


@ending_if("boss_fled")
def _boss_fled(game, adv, arg) -> bool:
    return bool(adv.get("boss_fled"))


@ending_if("scheme_done")
def _scheme_done(game, adv, arg) -> bool:
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    return t is not None and t.get("outcome") == "doom"


@ending_if("hero_dead")
def _hero_dead(game, adv, arg) -> bool:
    return adv.get("state") == "orphaned"


@ending_if("abandoned")
def _abandoned(game, adv, arg) -> bool:
    return bool(adv.get("abandoned"))


@ending_if("key:")
def _key(game, adv, k) -> bool:
    return k in adv["keys"]


@ending_if("no_key:")
def _no_key(game, adv, k) -> bool:
    return k not in adv["keys"]


@ending_if("flag:")
def _flag(game, adv, f) -> bool:
    return f in adv["flags"]


@ending_if("step_done:")
def _step(game, adv, sid) -> bool:
    return any(st["id"] == sid and st["state"] == "done" for ch in adv["chapters"] for st in ch["steps"])


# ---------------------------------------------------------------------------- consequences
def _place(adv: dict, name: str) -> dict | None:
    return adv["places"].get(name)


@consequence("beast_slain")
def _beast_slain(game, adv, *args) -> list[str]:
    """The beast of the history is dead: the history, the region's thanks and the news, through past.beast_slain."""
    from realmwalker.game import past
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    fig = threats.villain_figure(game.world, t) if t else None
    if fig is None or not fig.alive:
        return []
    site = t["home"].get("site")
    if site is None:
        past.figure_slain(game, fig.id)
        return []
    past.beast_slain(game, fig, int(site))
    return []


@consequence("clear_site")
def _clear_site(game, adv, place: str = "home") -> list[str]:
    from realmwalker.game import quests

    p = _place(adv, place)
    if p and "site" in p:
        quests.site_cleared(game, int(p["site"]))
    return []


@consequence("danger")
def _danger(game, adv, place: str, n: int) -> list[str]:
    """The country round a place grows safer (or worse): its danger, 1 to 10 (never the sea's 0)."""
    from realmwalker.game.story import places

    w = game.world
    p = _place(adv, place)
    if not p:
        return []
    x0, y0 = places.xy(w, p)
    r = 6
    xs, xe = max(0, x0 - r), min(w.width, x0 + r + 1)
    ys, ye = max(0, y0 - r), min(w.height, y0 + r + 1)
    land = w.danger[xs:xe, ys:ye] > 0
    w.danger[xs:xe, ys:ye][land] = (w.danger[xs:xe, ys:ye][land].astype(int) + int(n)).clip(1, 10)
    return ["<good>The country round about is safer for it.</>"] if int(n) < 0 else []


@consequence("fame")
def _fame(game, adv, n: int) -> list[str]:
    game.renown.fame = max(0, game.renown.fame + int(n))
    return []


@consequence("infamy")
def _infamy(game, adv, n: int) -> list[str]:
    game.renown.infamy = max(0, game.renown.infamy + int(n))
    return []


@consequence("history")
def _history(game, adv, kind: str, importance: int = 3) -> list[str]:
    """The tale goes into the world's history as a chapter of its own (the Legends book)."""
    from realmwalker.game.story import places
    from realmwalker.world.history import remember
    from realmwalker.world import threats

    w = game.world
    t = threats.records(w).get(adv["threat"])
    home = adv["places"].get("home", {})
    year = game.tables.calendar.at(int(w.time)).year
    text = f"{adv['title']}: {game.leader.name} ended it at {places.name(w, home)}" if home else adv["title"]
    figs = [t["villain"]["figure"]] if t and t["villain"].get("figure") is not None else []
    remember(w, year, kind, text, importance=int(importance), sites=[home["site"]] if "site" in home else [],
             figures=figs, player=True, data={"adventure": adv["id"]})
    return []


@consequence("news")
def _news(game, adv, *words) -> list[str]:
    from realmwalker.game.story import places
    from realmwalker.world import news

    home = adv["places"].get("home") or adv["places"].get("town")
    x, y = places.xy(game.world, home) if home else (game.player.x, game.player.y)
    text = " ".join(str(w) for w in words) or f"{adv['title']}: it is over."
    news.add(game.world, text, x, y, kind="story", importance=3, player=True)
    return []


@consequence("emptied")
def _emptied(game, adv, place: str = "town") -> list[str]:
    from realmwalker.world import news, threats
    from realmwalker.world.politics import Politics

    p = _place(adv, place)
    t = threats.records(game.world).get(adv["threat"])
    if not p or "settlement" not in p or t is None:
        return []
    s = game.world.settlements[int(p["settlement"])]
    if s.status.get("emptied"):
        return []  # (the doom of the scheme already did it)
    pol = Politics(game.world, game.tables, game.world.rng.child(f"ending/{adv['id']}"),
                   day=news.now_days(game.world))
    t = dict(t, stakes=[s.id])
    threats.STAGE_OPS["emptied"](pol, t)
    return []


@consequence("sequel")
def _sequel(game, adv, kind: str = "returns", lo: int = 28, hi: int = 56) -> list[str]:
    """The villain will be back (it fled): its threat goes on in the world, dormant, and stirs again in a while."""
    from realmwalker.world import news, threats

    t = threats.records(game.world).get(adv["threat"])
    if t is None or t["state"] == "ended":
        return []
    rng = game.world.rng.child(f"sequel/{adv['id']}")
    t["state"] = "dormant"
    t["adventure"] = None
    t["sequel"] = kind
    t["scheme"]["held_until"] = float(news.now_days(game.world)) + rng.randint(int(lo), int(hi))
    return []


@consequence("threat_free")
def _threat_free(game, adv, *args) -> list[str]:
    """The threat goes on without an adventure (given up, or the hero gone)."""
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    if t is not None:
        t["adventure"] = None
    return []
