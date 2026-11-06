"""What the world keeps of a tale (Expansion 6 G.3, docs/ADVENTURES.md §5.9, §5.19, §8.6): the rest of the consequence
ops, each through the system that already moves the world - never beside it.

Registered into `endings.OPS` (the endings' whitelist) with `@consequence`; a place argument names one of the tale's
places ("home", "town"...), "villain" names the villain's own faction (an outlaw's band). Ops that only a great tale
should do take a `min_tier` (the tale's tier must reach it, or nothing happens).

People and power:
    figure_dies(who, cause, min_tier)   "villain" or "lord:<place>": Politics.die, so a seat's succession runs
    figure_rests()                      the risen villain no longer walks (his tomb is only a tomb)
    faction_falls(who)                  Politics.fall (its towns to their liege; one it held by force goes home)
    set_owner(place, to, min_tier)      Politics.set_owner (the ledger): to the villain (an occupation, the
                                        `occupied` mark keeps who held it), to the holder of another place, "freed"
    succession(place, min_tier)         the lord of a place steps down; Politics.succeed crowns the next
    relation(a, b, n)                   factions.change_relation (places by their realm, "villain")
    law(place, key, value)              the realm that makes the laws there changes one (and says so)
    standing(place, n)                  your standing with the place's realm
Places:
    status(place, mark, how)            "add" or "lift" a mark (the one door: world/marks.py)
    rebuild(place)                      a ruin, an emptied or burned place starts rebuilding (remembering what it was)
    ruin(place, min_tier)               ruined in full: a floor of survivors, the townsfolk's fates, the map re-stamped
    lay_barrow(place), lay_scar()       `politics["laid"]`, `scar["laid"]` (as past.on_battle writes them)
    monument(place, what, words)        the memorial mark, with its form and its words (Look at it on the town map)
    rename(place, words, min_tier)      a site or settlement takes a new name; `politics["renamed"]` keeps the old
Memory and reward:
    song(form, lo, hi)                  a work by a real bard figure (`politics["works"]`), sung at inns from a day
    relic(to, words)                    the villain's token goes to you (a keepsake) or to the nearest temple
    title(place, min_tier)              reputation.grant_title by the place's realm (the honour, not its thresholds)
    land(place, min_tier)               a holding near the place: its rent is paid when you come to the town
    right(place, kind)                  "board" (free board at its inns for life) or "letter" (a letter of
                                        recommendation that opens doors where its writer holds sway)
    threat_grows()                      the threat's tier rises once (a dark ending feeds it)
    ally_fate(fate)                     the ally's fate decided by the ending ("broke": they walk away)

Afterwards, in play: `on_visit(game, s)` (from story.on_enter_town) gives a ruined or emptied town's people their
fates, newcomers to a rebuilding one (`newcomers`), and pays a holding's rent; `song_at_inn` (services' meals and
rooms); `board_free` (services.stay_price); `monument_look` (describe_local); `recommends` (people.papers_impression).
"""

from __future__ import annotations

import zlib

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story.endings import _place, consequence

DAY = 24 * 60
FATE_JOBS = ("wayfarer", "adventurer", "pilgrim")  # (passing through: never counted among a town's own)


def spec(game) -> dict:
    return game.tables.adventures.get("consequences", {}) or {}


def _h(*parts) -> int:
    return zlib.crc32("/".join(map(str, parts)).encode())


def _day(game) -> float:
    from realmwalker.world import news

    return float(news.now_days(game.world))


def _tier_ok(adv: dict, min_tier) -> bool:
    return int(adv.get("tier", 1)) >= int(min_tier or 1)


def _settlement(game, adv: dict, place: str):
    p = _place(adv, place)
    if not p:
        return None
    if "settlement" in p:
        return game.world.settlements[int(p["settlement"])]
    from realmwalker.game.story import places

    x, y = places.xy(game.world, p)
    return game.world.settlement_at(x, y)


def _near_settlement(game, adv: dict, place: str):
    """The place's settlement, or the nearest one to it (a lair's country belongs to someone)."""
    s = _settlement(game, adv, place)
    if s is not None:
        return s
    p = _place(adv, place)
    w = game.world
    if not p or not w.settlements:
        return None
    from realmwalker.game.story import places

    x, y = places.xy(w, p)
    return min(w.settlements, key=lambda t: ((t.x - x) ** 2 + (t.y - y) ** 2, t.id))


def _realm(game, adv: dict, place: str):
    from realmwalker.world import factions as fx

    if place == "villain":
        return _villain_faction(game, adv)
    s = _near_settlement(game, adv, place)
    return fx.realm_of_settlement(game.world, s) if s is not None else None


def _villain_faction(game, adv: dict):
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    if t is None:
        return None
    gang = threats.gang_of(game.world, t)
    if gang is not None:
        return gang
    fig = threats.villain_figure(game.world, t)
    return game.world.factions.get(fig.faction) if fig is not None and fig.faction >= 0 else None


def _words(game, adv: dict, key: str, rng, **more) -> str:
    """A line from the story's words (adventures.json "words"), filled with the tale's names."""
    from realmwalker.game.story import places, words as wordsmod

    tables = game.tables.adventures.get("words", {})
    lines = spec(game).get("words", {}).get(key) or tables.get(key)
    if not lines:
        return ""
    values = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
    for name in ("home", "town"):
        p = adv["places"].get(name)
        if p:
            values.setdefault(name, places.name(game.world, p))
    values.update({k: str(v) for k, v in more.items()})
    text = textgen.fill(rng.choice(list(lines)), rng, tables, values)
    return text[:1].upper() + text[1:]


def _rng(game, adv: dict, what: str):
    return game.world.rng.child(f"consequence/{adv['id']}/{what}")


def _politics(game):
    from realmwalker.game import past

    return past._politics(game)


def _restamp(game, s) -> None:
    """A mark changed on the town you are standing in: the map follows at once."""
    lm = game.local
    if s is None or lm is None or not game.in_local or lm.kind != "settlement":
        return
    if game.world.settlement_at(game.player.x, game.player.y) is not s:
        return
    from realmwalker.game import placemarks

    placemarks.stamp(game, lm, s)


def _remember(game, adv: dict, kind: str, text: str, importance: int = 2, **refs) -> None:
    from realmwalker.world.history import remember

    remember(game.world, game.moment.year, kind, text, importance=importance, player=True,
             data={"adventure": adv["id"]}, **refs)


# ---------------------------------------------------------------------------- people and power
@consequence("figure_dies")
def _figure_dies(game, adv, who: str = "villain", cause: str = "", min_tier: int = 1) -> list[str]:
    """A figure dies through Politics.die: if they held a seat (a lord, a captain), its succession runs."""
    from realmwalker.world import factions as fx, threats

    if not _tier_ok(adv, min_tier):
        return []
    w = game.world
    if who == "villain":
        t = threats.records(w).get(adv["threat"])
        fig = threats.villain_figure(w, t) if t is not None else None
    elif who.startswith("lord:"):
        s = _near_settlement(game, adv, who[5:])
        f = w.factions.get(s.owner) if s is not None else None
        fig = fx.leader_of(w, f) if f is not None else None
    else:
        return []
    if fig is None or not fig.alive:
        return []
    led = w.factions.get(fig.faction) if fig.faction >= 0 else None
    led = led if led is not None and led.leader == fig.id and led.active else None
    pol = _politics(game)
    why = _words(game, adv, cause, _rng(game, adv, "cause")) if cause else "in the days the tale ended"
    pol.die(fig, why[:1].lower() + why[1:], led=led)
    if led is not None:
        fx.touch(w)
    return [f"<warn>{esc(fig.full_name())} is dead.</>"]


@consequence("figure_rests")
def _figure_rests(game, adv, *args) -> list[str]:
    """The risen villain no longer walks: his tomb is only a tomb (villain_lives reads `politics["tombs"]`)."""
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    if t is None or "site" not in t["home"]:
        return []
    tombs = game.world.politics.get("tombs") or {}
    site = str(t["home"]["site"])
    fig = threats.villain_figure(game.world, t)
    if fig is not None and tombs.get(site) == fig.id:
        tombs.pop(site, None)
        game.world.politics.setdefault("rested", {})[str(fig.id)] = game.moment.year
    return []


@consequence("faction_falls")
def _faction_falls(game, adv, who: str = "villain") -> list[str]:
    from realmwalker.world import factions as fx

    f = _realm(game, adv, who)
    if f is None or not f.active or f.kind in ("kingdom",) and who != "villain":
        return []  # (a tale may break a band or a cult; a kingdom falls only to a war)
    pol = _politics(game)
    pol.fall(f)
    fx.touch(game.world)
    from realmwalker.world import threats

    threats.settle(game.world, _day(game))  # (the threat whose band is gone ends now)
    return []


@consequence("set_owner")
def _set_owner(game, adv, place: str, to: str, min_tier: int = 1) -> list[str]:
    """A settlement changes hands through Politics.set_owner (the ownership ledger). To "villain": an occupation (the
    villain's faction holds it by force; the `occupied` mark keeps who held it, and it goes back when they fall);
    to "freed": back to its own; to a place: the holder of that place takes it."""
    from realmwalker.world import factions as fx, marks

    if not _tier_ok(adv, min_tier):
        return []
    s = _settlement(game, adv, place)
    if s is None:
        return []
    w = game.world
    pol = _politics(game)
    if to == "freed":
        if not isinstance(s.status.get("occupied"), dict):
            return []
        pol.free(s)
        fx.touch(w)
        return [f"<good>{esc(s.name)} is free again.</>"]
    if to == "villain":
        f = _villain_faction(game, adv)
        if f is None or not f.active or s.owner == f.id or s.status.get("siege"):
            return []
        was = s.owner
        pol.set_owner(s, f.id)
        marks.add(w, s, "occupied", _day(game), game.tables, by=f.id, was=was, adv=adv["id"])
    else:
        other = _settlement(game, adv, to)
        if other is None or other.owner < 0 or other.owner == s.owner:
            return []
        pol.set_owner(s, other.owner)
    fx.touch(w)
    _restamp(game, s)
    return []


@consequence("succession")
def _succession(game, adv, place: str, min_tier: int = 1, cause: str = "") -> list[str]:
    """The lord of a place steps down (shamed, or worn out by it): the succession code crowns the next."""
    from realmwalker.world import factions as fx

    if not _tier_ok(adv, min_tier):
        return []
    w = game.world
    s = _near_settlement(game, adv, place)
    f = w.factions.get(s.owner) if s is not None else None
    old = fx.leader_of(w, f) if f is not None and f.active else None
    if old is None or f.kind in ("bandit_gang", "pirate_crew"):
        return []
    pol = _politics(game)
    why = _words(game, adv, cause, _rng(game, adv, "succession")) if cause else "stepped down"
    old.role = "member"
    pol.succeed(f, old, why[:1].lower() + why[1:])
    fx.touch(w)
    new = fx.leader_of(w, f)
    if new is None or new is old:
        return []
    return [f"<warn>{esc(f.name)} has a new head: {esc(new.full_name())}.</>"]


@consequence("relation")
def _relation(game, adv, a: str, b: str, n: float) -> list[str]:
    from realmwalker.world import factions as fx

    fa, fb = _realm(game, adv, a), _realm(game, adv, b)
    if fa is None or fb is None or fa.id == fb.id:
        return []
    fx.change_relation(game.world, fa.id, fb.id, float(n))
    return []


@consequence("law")
def _law(game, adv, place: str, key: str, value) -> list[str]:
    """The realm that makes the laws in a place changes one of them (factions.laws_of), and the land hears of it."""
    from realmwalker.world import factions as fx, news

    w = game.world
    s = _near_settlement(game, adv, place)
    if s is None:
        return []
    f = w.factions.get(s.owner)
    while f is not None and not f.laws and f.liege >= 0:
        f = w.factions.get(f.liege)
    if f is None or not f.laws or f.laws.get(key) == value:
        return []
    f.laws[key] = value
    text = _words(game, adv, f"law_{key}", _rng(game, adv, "law"), realm=f.name, value=str(value).replace("_", " "))
    if text:
        news.add(w, text, s.x, s.y, kind="law", importance=2, factions=[f.id], player=True)
    fx.touch(w)
    return [f"<info>{esc(text)}</>"] if text else []


@consequence("standing")
def _standing(game, adv, place: str, n: float) -> list[str]:
    from realmwalker.game import reputation

    f = _realm(game, adv, place)
    if f is None:
        return []
    reputation.change_standing(game, f.id, float(n))
    reputation.know(game, f.id)
    return []


# ---------------------------------------------------------------------------- places
@consequence("status")
def _status(game, adv, place: str, mark: str, how: str = "add") -> list[str]:
    """A mark added or lifted (`status` is another name for `mark`: one way to touch a place)."""
    from realmwalker.world import marks

    s = _settlement(game, adv, place)
    if s is None or mark not in marks.table(game.tables):
        return []
    if how == "lift":
        if mark not in s.status:
            return []
        marks.lift(game.world, s, mark)
    else:
        from realmwalker.game.story.endings import _villain_short

        marks.add(game.world, s, mark, _day(game), game.tables, by=_villain_short(game, adv))
    _restamp(game, s)
    return []


FALLEN_MARKS = ("ruined", "emptied", "burned", "burning", "sacked", "burned_out")


@consequence("rebuild")
def _rebuild(game, adv, place: str = "town") -> list[str]:
    """A fallen place begins again: its ruin or emptiness lifted, `rebuilding` with the town it was to fill back to."""
    from realmwalker.world import marks

    s = _settlement(game, adv, place)
    if s is None or not any(m in s.status for m in FALLEN_MARKS):
        return []
    was = int(s.population)
    for m in FALLEN_MARKS:
        v = s.status.get(m)
        if isinstance(v, dict) and v.get("was"):
            was = max(was, int(v["was"]))
        marks.lift(game.world, s, m)
    days = int(spec(game).get("rebuild_days", 240))
    marks.add(game.world, s, "rebuilding", _day(game), game.tables, until=_day(game) + days, was=was)
    _restamp(game, s)
    return [f"<good>{esc(s.name)} will be built again.</>"]


@consequence("ruin")
def _ruin(game, adv, place: str = "town", min_tier: int = 1) -> list[str]:
    """A settlement ruined in full: its people fall to a floor of survivors (the rest dead or fled: `fates`), most of
    its buildings are shells (the `ruined` mark's dressing, the map re-stamped), the land is told and the history
    keeps it. In a year or so people creep back (ruined ages into rebuilding, which remembers the town it was)."""
    from realmwalker.world import marks, news

    if not _tier_ok(adv, min_tier):
        return []
    s = _settlement(game, adv, place)
    if s is None or "ruined" in s.status:
        return []
    w = game.world
    sp = spec(game).get("ruin", {})
    was = int(s.population)
    for m in ("emptied", "rebuilding"):
        v = s.status.get(m)
        if isinstance(v, dict) and v.get("was"):
            was = max(was, int(v["was"]))
    for m in ("burning", "rebuilding", "emptied", "festival", "beset", "plague", "famine"):
        marks.lift(w, s, m)
    s.population = max(int(sp.get("least", 5)), int(was * float(sp.get("floor", 0.1))))
    from realmwalker.game.story.endings import _villain_short

    marks.add(w, s, "ruined", _day(game), game.tables, was=was, by=_villain_short(game, adv), adv=adv["id"])
    rng = _rng(game, adv, "ruin")
    text = _words(game, adv, "ruin_news", rng, place=s.name) or f"{s.name} is in ruins."
    news.add(w, text, s.x, s.y, kind="ruined", importance=3, places=[s.id], player=True)
    _remember(game, adv, "ruined", text, importance=3, places=[s.id])
    fates(game, s)
    _restamp(game, s)
    return [f"<danger>{esc(text)}</>"]


@consequence("lay_barrow")
def _lay_barrow(game, adv, place: str = "home") -> list[str]:
    """The barrow is only a grave again (`politics["laid"]`, as past.on_battle writes it)."""
    p = _place(adv, place)
    if not p or "site" not in p:
        return []
    game.world.politics.setdefault("laid", {})[str(int(p["site"]))] = game.moment.year
    return []


@consequence("lay_scar")
def _lay_scar(game, adv, *args) -> list[str]:
    """The threat's field of the restless dead is quiet (`scar["laid"]`)."""
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    scars = game.world.politics.get("scars") or []
    i = (t.get("source") or {}).get("scar") if t is not None else None
    if i is not None and 0 <= int(i) < len(scars):
        scars[int(i)]["laid"] = True
    return []


@consequence("monument")
def _monument(game, adv, place: str = "town", what: str = "statue", words: str = "") -> list[str]:
    """A monument stands in the square (the memorial mark, with its form and what is cut in it): a statue, a shrine,
    a cairn, or the villain's cage on a gibbet. Look at it on the town's map to read it."""
    from realmwalker.world import marks

    s = _settlement(game, adv, place)
    if s is None:
        return []
    rng = _rng(game, adv, "monument")
    text = _words(game, adv, words, rng, place=s.name) if words else ""
    marks.add(game.world, s, "memorial", _day(game), game.tables, what=what, words=text, adv=adv["id"],
              by=game.leader.name)
    _restamp(game, s)
    return [f"<dim>{esc(s.name)} will raise a {esc(SHAPES.get(what, what))} to remember it.</>"]


SHAPES = {"statue": "statue", "shrine": "shrine", "cairn": "cairn", "gibbet": "gibbet", "stone": "standing stone"}


@consequence("rename")
def _rename(game, adv, place: str = "home", words: str = "", min_tier: int = 1) -> list[str]:
    """A place takes a new name from what happened there ("the Wolf's Grave"). `politics["renamed"]` keeps the old
    name, so the history and the Legends book can say what it was called."""
    from realmwalker.world import news

    if not _tier_ok(adv, min_tier) or not words:
        return []
    p = _place(adv, place)
    w = game.world
    if not p:
        return []
    if "site" in p:
        thing, key = w.sites[int(p["site"])], f"X{int(p['site'])}"
    elif "settlement" in p and w.settlements[int(p["settlement"])].kind in ("hamlet", "village"):
        thing, key = w.settlements[int(p["settlement"])], f"S{int(p['settlement'])}"  # (only a small place is renamed)
    else:
        return []
    renamed = w.politics.setdefault("renamed", {})
    if key in renamed:
        return []
    new = _words(game, adv, words, _rng(game, adv, "rename"))
    if not new or new == thing.name:
        return []
    old = thing.name
    renamed[key] = {"old": old, "new": new, "year": game.moment.year, "adv": adv["id"]}
    thing.name = new
    for lm in w.local_maps.values():  # (a dungeon built under it keeps its name in its meta)
        meta = getattr(lm, "meta", None) or {}
        if meta.get("name") == old:
            meta["name"] = new
    x, y = (thing.x, thing.y)
    text = f"{old} has a new name since {adv['title']}: people call it {new} now."
    news.add(w, text, x, y, kind="renamed", importance=2, player=True)
    _remember(game, adv, "renamed", text, importance=2, **({"sites": [thing.id]} if key[0] == "X" else
                                                             {"places": [thing.id]}))
    return [f"<info>People will call {esc(old)} {esc(new)} now.</>"]


# ---------------------------------------------------------------------------- memory and reward
@consequence("song")
def _song(game, adv, form: str = "ballad", lo: int = 21, hi: int = 42) -> list[str]:
    """A song of the tale is made by a real bard (a figure of the world, in the Legends book as its author), and is
    sung at the inns round about from some weeks on (`song_at_inn`)."""
    from realmwalker.world import factions as fx

    w = game.world
    forms = game.tables.history["works"]["forms"]
    if form not in forms:
        return []
    s = _near_settlement(game, adv, "town") or _near_settlement(game, adv, "home")
    if s is None:
        return []
    rng = _rng(game, adv, "song")
    bard = fx.make_figure(w, game.tables, rng, s.culture if s.culture != "orcish" else "heartland",
                          year=game.moment.year, role="member", age=(20, 55))
    bard.home = f"S{s.id}"
    bard.fame += 2
    words = game.tables.adventures.get("words", {})
    subject = adv["title"]
    if subject.startswith("The "):
        subject = "the " + subject[4:]  # ("The Lay of the Hunt for...")
    title = textgen.fill(rng.choice(list(forms[form]["titles"])), rng, words, {"subject": subject})
    title = title[:1].upper() + title[1:]
    works = w.politics.setdefault("works", [])
    work = {"id": len(works), "title": title, "form": form, "author": bard.id, "year": game.moment.year,
            "about": {"adventure": adv["id"]}, "place": f"S{s.id}",
            "sung": {"from": _day(game) + rng.randint(int(lo), int(hi)), "x": s.x, "y": s.y,
                     "reach": int(spec(game).get("song_reach", 30))}}
    works.append(work)
    _remember(game, adv, "work_written", f"{bard.full_name()} made {forms[form]['word']}, {title}, of what "
              f"{game.leader.name} did", importance=1, figures=[bard.id], places=[s.id])
    return []


def song_at_inn(game, npc) -> list[str]:
    """At an inn's table: a song made of your deeds, if one is sung here now (once in each town)."""
    w = game.world
    s = w.settlements[npc.settlement] if 0 <= npc.settlement < len(w.settlements) else None
    if s is None:
        return []
    heard = game.renown.flags.setdefault("songs_heard", [])
    day = _day(game)
    for work in w.politics.get("works") or ():
        sung = work.get("sung") if isinstance(work, dict) else None
        if not sung or day < float(sung["from"]) or f"K{work['id']}/S{s.id}" in heard:
            continue
        if (s.x - sung["x"]) ** 2 + (s.y - sung["y"]) ** 2 > int(sung["reach"]) ** 2:
            continue
        heard.append(f"K{work['id']}/S{s.id}")
        bard = w.figures.get(work["author"])
        rng = w.rng.child(f"sung/{work['id']}/{s.id}")
        lines = spec(game).get("words", {}).get("song_at_inn") or ["{singer} sings {title}."]
        singer = "a travelling singer" if bard is None or bard.home != f"S{s.id}" else bard.full_name()
        text = textgen.fill(rng.choice(list(lines)), rng, {}, {"singer": singer, "title": work["title"],
                                                                 "hero": game.leader.name.split()[0]})
        game.renown.fame += 1 if len(heard) <= 3 else 0
        return [f"<info>{esc(text[:1].upper() + text[1:])}</>"]
    return []


@consequence("relic")
def _relic(game, adv, to: str = "hero", words: str = "") -> list[str]:
    """What the villain leaves (a tusk, a crown of grave-gold, a captain's blade) goes to you as a keepsake, or to the
    temple of the town, where it is shown (`politics["relics"]`)."""
    from realmwalker.rules.inventory import add_item

    if not words:
        return []
    rng = _rng(game, adv, "relic")
    name = _words(game, adv, words, rng)
    if not name:
        return []
    name = name[:1].lower() + name[1:]
    if to == "temple":
        s = _near_settlement(game, adv, "town")
        if s is None:
            return []
        game.world.politics.setdefault("relics", []).append({"name": name, "settlement": s.id, "adv": adv["id"],
                                                             "year": game.moment.year})
        return [f"<dim>The {esc(name)} will be kept in the temple at {esc(s.name)}.</>"]
    add_item(game.leader, game.tables.items, "trinket", 1, made_at=game.world.time, name=name,
             tags=[f"relic:{adv['id']}"])
    return [f"<loot>You keep the {esc(name)}.</>"]


def relic_line(game, s) -> str:
    """A relic kept in a town's temple (for its description and its priest)."""
    for r in game.world.politics.get("relics") or ():
        if r.get("settlement") == s.id:
            return f"The temple keeps the {esc(r['name'])}."
    return ""


@consequence("title")
def _title(game, adv, place: str = "town", min_tier: int = 2) -> list[str]:
    """A great tale's honour: the realm grants you a title (the honour itself, past its usual thresholds)."""
    from realmwalker.game import reputation

    if not _tier_ok(adv, min_tier):
        return []
    realm = _realm(game, adv, place)
    if realm is None or realm.kind not in game.tables.law["titles"]["names"] or             any(t.get("realm") == realm.id for t in game.renown.flags.get("titles", [])):
        return []
    return [reputation.grant_title(game, realm, earned=True)]


@consequence("land")
def _land(game, adv, place: str = "town", min_tier: int = 3) -> list[str]:
    """A holding granted near the place (a farm and its tenants): its rent waits for you in the town, a month's at a
    time (paid by `on_visit`)."""
    if not _tier_ok(adv, min_tier):
        return []
    s = _near_settlement(game, adv, place)
    realm = _realm(game, adv, place)
    if s is None or realm is None:
        return []
    lands = game.renown.flags.setdefault("lands", [])
    if any(x["settlement"] == s.id for x in lands):
        return []
    sp = spec(game).get("land", {})
    rent = int(sp.get("rent", [300, 600])[0] + (int(adv.get("tier", 1)) - 1) * int(sp.get("per_tier", 200)))
    name = _words(game, adv, "land_name", _rng(game, adv, "land"), place=s.name) or f"a holding near {s.name}"
    lands.append({"settlement": s.id, "realm": realm.id, "name": name, "rent": rent, "paid": _day(game)})
    return [f"<good>{esc(realm.name)} grants you {esc(name[:1].lower() + name[1:])}.</> <dim>Its rent waits for you "
            f"in {esc(s.name)}.</>"]


@consequence("right")
def _right(game, adv, place: str = "town", kind: str = "board") -> list[str]:
    """A right for life: free board at the town's inns, or a letter of recommendation from its lord that opens doors
    wherever the realm holds sway."""
    s = _near_settlement(game, adv, place)
    if s is None:
        return []
    rights = game.renown.flags.setdefault("rights", [])
    if kind == "board":
        if any(r["kind"] == "board" and r["settlement"] == s.id for r in rights):
            return []
        rights.append({"kind": "board", "settlement": s.id, "adv": adv["id"]})
        return [f"<good>The innkeepers of {esc(s.name)} will take no coin from you again.</>"]
    if kind == "letter":
        from realmwalker.game import letters
        from realmwalker.world import factions as fx

        realm = _realm(game, adv, place)
        if realm is None:
            return []
        lord = fx.leader_of(game.world, realm)
        sender = lord.full_name() if lord is not None else realm.name
        rng = _rng(game, adv, "letter")
        lines = [_words(game, adv, "letter_line", rng, realm=realm.name, place=s.name) for _ in range(2)]
        lines = [x for i, x in enumerate(lines) if x and x not in lines[:i]] or [f"Let {game.leader.name} pass."]
        lid = letters.write(game, sender=sender, lines=lines, hand="fine")
        it = letters.give(game, lid)
        if it is not None:
            it.name = f"letter of recommendation from {sender}"
            it.tags.append(f"recommends:{realm.id}")
        rights.append({"kind": "letter", "realm": realm.id, "adv": adv["id"]})
        return [f"<good>{esc(sender)} gives you a letter of recommendation.</> <dim>Where {esc(realm.name)} holds "
                f"sway, it opens doors.</>"]
    return []


def board_free(game, settlement_id: int) -> bool:
    return any(r.get("kind") == "board" and r.get("settlement") == settlement_id
               for r in game.renown.flags.get("rights") or ())


def recommends(game, npc) -> int:
    """A letter of recommendation in your pack, from the realm that holds this person's town: the high-born and the
    soldiers think better of you (people.papers_impression)."""
    from realmwalker.rules.inventory import carried
    from realmwalker.world import factions as fx

    if npc.social != "high" and npc.job not in ("guard", "lord", "headman"):
        return 0
    w = game.world
    s = w.settlements[npc.settlement] if 0 <= npc.settlement < len(w.settlements) else None
    realm = fx.realm_of_settlement(w, s) if s is not None else None
    if realm is None:
        return 0
    for it in carried(game.party):
        if f"recommends:{realm.id}" in it.tags:
            return int(spec(game).get("letter_bonus", 6))
    return 0


@consequence("threat_grows")
def _threat_grows(game, adv, *args) -> list[str]:
    """A dark ending feeds the threat: its tier rises once (as a doom would raise it)."""
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    if t is None or t["state"] == "ended" or t.get("grown"):
        return []
    top = game.tables.threats["kinds"][t["kind"]]["tiers"][1]
    if t["tier"] < top:
        t["tier"] += 1
        t["grown"] = True
    return []


@consequence("ally_fate")
def _ally_fate(game, adv, fate: str = "broke") -> list[str]:
    """The ending decides what the ally does: "broke" - they cannot stomach it and walk away (stakes.after_tale gives
    their fate and page)."""
    from realmwalker.game.story import stakes

    rec = adv.get("ally")
    if not rec or rec.get("state") not in ("joined", "riding") or fate != "broke":
        return []
    npc = stakes.npc_of(game, adv)
    if npc is None or not npc.alive:
        return []
    c = stakes.companion_of(game, adv)
    if c is not None:
        from realmwalker.game import companions

        companions.dismiss(game, c)
    rec["state"] = "broke"
    return [f"<warn>{esc(npc.first_name)} will not look at you, and does not ride with you again.</>"]


# ---------------------------------------------------------------------------- afterwards, in play
def fates(game, s) -> int:
    """The townsfolk's fates when their town is ruined or emptied: most die or flee, a floor stays (its notables, and
    those a story is about, among them). Once a mark; the people who went are kept (the dead as dead, the fled as
    gone), and their homes wait for newcomers. Returns how many went."""
    w = game.world
    town = w.towns.get(s.id)
    rec = s.status.get("ruined") or s.status.get("emptied")
    if town is None or not town.npcs or not isinstance(rec, dict):
        return 0
    key = f"{'ruined' if 'ruined' in s.status else 'emptied'}/{rec.get('since')}"
    if town.flags.get("fates") == key:
        return 0
    town.flags["fates"] = key
    sp = spec(game).get("fates", {})
    stays, dies = (float(sp.get("ruined_stay", 0.2)), float(sp.get("ruined_die", 0.45))) if "ruined" in s.status \
        else (float(sp.get("emptied_stay", 0.35)), float(sp.get("emptied_die", 0.15)))
    folk = [w.npcs[i] for i in town.npcs if i in w.npcs and w.npcs[i].alive and not w.npcs[i].flags.get("gone")
            and not w.npcs[i].flags.get("visitor") and w.npcs[i].job not in FATE_JOBS]
    town.flags.setdefault("folk_full", len(folk))
    went = 0
    where = s.name
    for npc in folk:
        if npc.notable or npc.flags.get("story") or npc.flags.get("figure") is not None or \
                npc.flags.get("companion") or npc.flags.get("with_party"):
            continue
        r = (_h(s.id, key, npc.id) % 1000) / 1000.0
        if r < stays:
            continue
        went += 1
        if r < stays + dies:
            npc.alive = False
            npc.present = False
            npc.flags["fate"] = f"died when {where} fell"
        else:
            npc.flags["gone"] = True
            npc.present = False
            npc.flags["fate"] = f"fled when {where} fell"
    return went


def newcomers(game, s) -> int:
    """A rebuilding town fills again: newcomers take the empty homes of those who died or fled, as many as its people
    have grown back (Politics.regrow), a few at a visit. Returns how many came."""
    from realmwalker.game import people

    w = game.world
    town = w.towns.get(s.id)
    r = s.status.get("rebuilding")
    if town is None or not isinstance(r, dict) or not town.flags.get("folk_full"):
        return 0
    was = max(1, int(r.get("was", s.population)))
    target = int(town.flags["folk_full"] * min(1.0, s.population / was))
    here = [w.npcs[i] for i in town.npcs if i in w.npcs and w.npcs[i].alive and not w.npcs[i].flags.get("gone")
            and not w.npcs[i].flags.get("visitor") and w.npcs[i].job not in FATE_JOBS]
    empty = [w.npcs[i] for i in town.npcs if i in w.npcs and w.npcs[i].flags.get("fate")
             and not w.npcs[i].flags.get("replaced")]
    n = min(target - len(here), len(empty), int(spec(game).get("newcomers_a_visit", 6)))
    if n <= 0:
        return 0
    rng = w.rng.child(f"newcomers/{s.id}/{int(_day(game))}")
    jobs = list(game.tables.people["commoner_jobs"])
    occ = game.tables.people["occupations"]
    for old in sorted(empty, key=lambda x: x.id)[:n]:
        job = old.job if old.job in jobs or old.job in occ and not occ[old.job].get("notable") else rng.choice(jobs)
        if job not in occ:
            job = rng.choice(jobs)
        npc = people.make_npc(game, s, job, rng.child(str(old.id)), building=old.building, post=old.post,
                              home=old.home)
        npc.flags["newcomer"] = int(_day(game))
        old.flags["replaced"] = npc.id
        people.add(w, town, npc)
    from realmwalker.game.story import lives

    lives.ensure(game, s.id)
    lm = game.local
    if lm is not None and game.in_local and lm.kind == "settlement" and w.settlement_at(game.player.x,
                                                                                           game.player.y) is s:
        people.update_positions(game, lm)
    return n


def rent(game, s) -> list[str]:
    """A holding's steward pays what has come in since your last visit (whole months)."""
    out = []
    for land in game.renown.flags.get("lands") or ():
        if land["settlement"] != s.id:
            continue
        months = int((_day(game) - float(land["paid"])) // 30)
        if months <= 0:
            continue
        land["paid"] = float(land["paid"]) + months * 30
        paid = months * int(land["rent"])
        game.leader.money += paid
        from realmwalker.rules.items import money_text

        out.append(f"<loot>Your steward finds you: {months} month{'s' if months > 1 else ''} of rent from "
                   f"{esc(land['name'][:1].lower() + land['name'][1:])}, {money_text(paid)}.</>")
    return out


def on_visit(game, s) -> None:
    """Into a town (story.on_enter_town): its people's fates if it fell, newcomers if it is rebuilding, your rent."""
    if "ruined" in s.status or "emptied" in s.status:
        fates(game, s)
    elif "rebuilding" in s.status:
        if newcomers(game, s) and game.flavour(1):
            game.say("<dim>There are new faces here: settlers come to fill the empty houses.</>", "info")
    for line in rent(game, s):
        game.say(line, "info")


def monument_look(game, lm, x: int, y: int) -> str:
    """The words on a monument, for Look on a town's map."""
    if lm is None or lm.kind != "settlement":
        return ""
    rec = ((lm.meta or {}).get("marks") or {}).get("memorial") or {}
    if [x, y] not in rec.get("props", []):
        return ""
    s = game.world.settlement_at(game.player.x, game.player.y)
    v = s.status.get("memorial") if s is not None else None
    if not isinstance(v, dict) or not v.get("words"):
        return ""
    return f"<info>{esc(v['words'])}</>"
