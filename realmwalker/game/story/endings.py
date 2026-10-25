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
WON = ("slain", "laid_to_rest", "destroyed", "destroyed_for_now", "broken", "taken", "spared", "pardoned",
       "redeemed")  # (endings the hero won)


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
    if adv["state"] == "won":
        from realmwalker.game import law

        lines += law.clear_framed(game, adv["id"])  # (its frames come to light: E.2)
        from realmwalker.game.story import experience

        lines += experience.award(game, "finale", f"finale/{adv['id']}")  # (on top of the finale fight's own: C.8)
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


@consequence("mark")
def _mark(game, adv, place: str, mark: str) -> list[str]:
    """A mark on the tale's settlement (marks.json): haunted, paying outlaws, remembering..."""
    from realmwalker.world import marks, news

    p = _place(adv, place)
    if not p or "settlement" not in p or mark not in marks.table(game.tables):
        return []
    s = game.world.settlements[int(p["settlement"])]
    marks.add(game.world, s, mark, float(news.now_days(game.world)), game.tables, by=_villain_short(game, adv))
    return []


def _villain_short(game, adv) -> str:
    from realmwalker.game.story import words as wordsmod

    return str(wordsmod.for_adventure(game, adv).get("villain_short", "it"))


@consequence("bargained")
def _bargained(game, adv, lo: int = 60, hi: int = 120) -> list[str]:
    """You took its offer (E.2: a bargain, or a wedge driven home): it keeps its word for a while - its scheme waits
    lo-hi days, and then goes on as before, with nobody against it."""
    from realmwalker.world import news, threats

    t = threats.records(game.world).get(adv["threat"])
    if t is None or t["state"] == "ended":
        return []
    rng = game.world.rng.child(f"bargained/{adv['id']}")
    t["adventure"] = None
    until = float(news.now_days(game.world)) + rng.randint(int(lo), int(hi))
    t["scheme"]["held_until"] = until
    t["bargained"] = until  # (no one offers you its tale again while its word holds: story._can_take)
    return []


# ---------------------------------------------------------------------------- the Risen and the Outlaw Lord (D.3)
@ending_if("boss_taken")
def _boss_taken(game, adv, arg) -> bool:
    return bool(adv.get("boss_taken"))


def _threat_and_figure(game, adv):
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    return t, (threats.villain_figure(game.world, t) if t is not None else None)


def _settle(game) -> None:
    from realmwalker.world import news, threats

    threats.settle(game.world, news.now_days(game.world))  # (the threat whose villain is gone ends now)


def _lay(game, adv, kind: str, said: str) -> list[str]:
    """The barrow is only a grave again (`politics["laid"]`, as past.on_battle writes it), his field of the dead
    with it (`scar["laid"]`), and the world remembers who did it."""
    from realmwalker.core.textgen import escape_markup as esc
    from realmwalker.world.history import remember

    w = game.world
    t, fig = _threat_and_figure(game, adv)
    if t is None or "site" not in t["home"]:
        return []
    site = w.sites[int(t["home"]["site"])]
    w.politics.setdefault("laid", {})[str(site.id)] = game.moment.year
    scars = w.politics.get("scars") or []
    i = (t.get("source") or {}).get("scar")
    if i is not None and 0 <= int(i) < len(scars):
        scars[int(i)]["laid"] = True
    name = fig.full_name() if fig is not None else adv["title"]
    text = f"{game.leader.name} {kind} {name}, who had walked in {site.name} since they died"
    remember(w, game.moment.year, "laid_to_rest", text, importance=3, sites=[site.id],
             figures=[fig.id] if fig is not None else [], player=True, data={"adventure": adv["id"]})
    _settle(game)
    from realmwalker.game.story import words as wordsmod

    said = textgen.fill(said, w.rng, {}, {k: v for k, v in wordsmod.for_adventure(game, adv).items()
                                          if isinstance(v, str)})
    return [f"<good>{esc(name)} {said}</>"]


@consequence("risen_laid")
def _risen_laid(game, adv, *args) -> list[str]:
    """Laid to rest by the rite: he goes back into the dark of his own will, and does not come out again."""
    return _lay(game, adv, "laid to rest", "is at rest. The barrow is only a grave now.")


@consequence("risen_destroyed")
def _risen_destroyed(game, adv, *args) -> list[str]:
    """Destroyed with what bound him broken: he is gone for good."""
    return _lay(game, adv, "destroyed", "is gone, and what bound {him} to the world is broken with {him}.")


def _gang(game, adv):
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    return threats.gang_of(game.world, t) if t is not None else None


@consequence("outlaw_broken")
def _outlaw_broken(game, adv, *args) -> list[str]:
    """The band is broken in its hideout: its captain dead (or taken to the gallows), the gang finished
    (past.den_falls), the roads quieter."""
    from realmwalker.game import past

    t, fig = _threat_and_figure(game, adv)
    gang = _gang(game, adv)
    if t is None or gang is None or not gang.active:
        return []
    site = game.world.sites[int(t["home"]["site"])] if "site" in t["home"] else None
    fate = adv.get("villain_fate")
    if fig is not None and fig.alive and site is not None and fate not in ("spare", "rob"):  # (let go: they live)
        if adv.get("boss_taken") and fate != "execute":
            pol = past._politics(game)
            pol.die(fig, f"hanged, taken alive by {game.leader.name}")
            fig.died_at = f"X{site.id}"
            gang.flags["leader_slain"] = game.moment.total_days
        else:
            past.den_leader_slain(game, gang, fig, site)
    if site is not None:
        past.den_falls(game, gang, site)
    _settle(game)
    return []


@consequence("outlaw_pardoned")
def _outlaw_pardoned(game, adv, *args) -> list[str]:
    """A parley that ends it without blood: the band disbands and its men are pardoned through the lord of the
    town (a law outcome): the gang is no more, its captain lives, the lord owes the hero a little."""
    from realmwalker.core.textgen import escape_markup as esc
    from realmwalker.game import past, reputation
    from realmwalker.game.story import places
    from realmwalker.world import factions as fx
    from realmwalker.world.history import remember

    w = game.world
    t, fig = _threat_and_figure(game, adv)
    gang = _gang(game, adv)
    if t is None or gang is None or not gang.active:
        return []
    pol = past._politics(game)
    pol.fall(gang)
    town = adv["places"].get("town")
    s = w.settlements[int(town["settlement"])] if town and "settlement" in town else None
    realm = fx.realm_of_settlement(w, s) if s is not None else None
    lord = realm.name if realm is not None else "the lord"
    text = f"{gang.name} laid down their arms at {game.leader.name}'s word, and were pardoned by {lord}"
    remember(w, pol.year, "pardoned", text, importance=2, factions=[gang.id] + ([realm.id] if realm else []),
             figures=[fig.id] if fig is not None else [], player=True, data={"adventure": adv["id"]})
    x, y = places.xy(w, town) if town else (game.player.x, game.player.y)
    reputation.deed(game, f"ended {gang.name} without blood", {realm.id: 6.0} if realm is not None else {}, x=x, y=y,
                    fame=2, importance=2, news_text=text)
    _settle(game)
    return [f"<good>{esc(gang.name[:1].upper() + gang.name[1:])} are no more.</> <dim>Their men go home, or into "
            f"{esc(lord)}'s service, with their lives.</>"]
