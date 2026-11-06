"""The epilogue in full and the tale's chapter of history (Expansion 6 G.4, docs/ADVENTURES.md §5.9, §5.13).

*What became of them*: endings.finish writes the ending's own pages (the place, the patron, the ally...), then every
cast module adds its own (lieutenants, the ally's fate, the rival, the patron's secret and the innocent, the traitor);
`compose(game, adv, before)` is the last word: it adds
- the places as they now are: the tale's town gets a closing sentence for its most telling mark (ruined, occupied,
  rebuilding, a memorial...: VIGNETTE_MARKS), and each other place of the tale whose state is worth a page (a town by
  its marks; a site renamed, laid to rest, cleared, or still held) gets a vignette page "place:<key>" (VIGNETTES at
  most), its picture from ui/gfx/vignette.for_epilogue;
- the realm: how its lord took the ending (won, lost, abandoned);
- what is left to come back (story/sequels.py: the heir, the gang in the gap, the dead who will walk again);
- you, last: your standing with that realm now, the title the tale gave you, your name on the roads;
then orders the pages by ORDER and keeps MOST at most (dropping by DROP: a second vignette or lieutenant first, the
hero's never).
Every line comes from adventures consequences `words` (vignette_<mark>, epilogue_realm_<how>, epilogue_sequel_<kind>,
hero_standing, hero_title, hero_fame, hero_infamy), filled with the tale's names.

`chronicle(game, adv)` writes the tale into the world's history as a named chapter, once (`world.politics["tales"]`
[{adv, title, year, began, hero, life, kind, ending, state, villain, villain_name, places, chapters, pages,
sequel_of}]); the Legends book's Tales are its pages (world/legends.tale_page). An orphaned tale (its hero died:
story.on_death) is written as far as it went.
"""

from __future__ import annotations

VIGNETTE_MARKS = ("ruined", "occupied", "cursed", "emptied", "burned", "rebuilding", "haunted", "memorial",
                  "festival")
VIGNETTES = 2  # vignette pages of other places, at most
MOST = 8  # pages in all (ADVENTURES.md §5.9: 4-8)
ORDER = ("place", "place:", "patron", "traitor", "ally", "witness", "carter", "suspect", "taken", "rival",
         "lieutenant:", "innocent", "realm", "sequel", "hero")
# (what goes first when there are too many: (kind, how many of it to keep while anything else can go))
DROP = (("place:", 1), ("lieutenant:", 1), ("witness", 0), ("suspect", 0), ("carter", 0), ("taken", 0),
        ("lieutenant:", 0), ("place:", 0), ("traitor", 0), ("rival", 0), ("realm", 0), ("innocent", 0))
SPOKEN = 10  # standing with the realm (either way) from which your page says what it thinks of you
FAMED = 20  # fame (or infamy) from which your name goes before you, and the hero's page says so
REALMS = "realms"  # (the faction group whose lord takes notice)


def snapshot(game) -> dict:
    """What the hero has before the ending's ops (endings.finish): the epilogue tells what changed."""
    return {"titles": len(game.renown.flags.get("titles", [])), "fame": int(game.renown.fame),
            "infamy": int(game.renown.infamy)}


def _words(game, adv: dict, key: str, what: str, **more) -> str:
    from realmwalker.game.story import consequences

    return consequences._words(game, adv, key, game.world.rng.child(f"epilogue/{adv['id']}/{what}"), **more)


def _kind(about: str) -> str:
    return about.split(":", 1)[0] + ":" if ":" in about else about


def _rank(about: str) -> int:
    k = _kind(about)
    return ORDER.index(k) if k in ORDER else ORDER.index("realm") - 1


# ---------------------------------------------------------------------------- the places as they now are
def town_mark(s) -> str | None:
    """The most telling mark on a settlement now (VIGNETTE_MARKS' order), or None."""
    if s is None:
        return None
    return next((m for m in VIGNETTE_MARKS if m in s.status), None)


def _town(game, adv: dict):
    p = adv["places"].get("town") or {}
    sid = p.get("settlement")
    w = game.world
    return w.settlements[int(sid)] if sid is not None and 0 <= int(sid) < len(w.settlements) else None


def site_state(game, adv: dict, site_id: int) -> tuple[str, dict]:
    """How a site of the tale is now: renamed, laid, cleared or held (its villain still there), or "" (nothing to
    tell), with the words' extras."""
    from realmwalker.world import threats

    w = game.world
    pol = w.politics
    rn = (pol.get("renamed") or {}).get(f"X{site_id}")
    if rn and rn.get("adv") == adv["id"]:
        return "renamed", {"old": rn.get("old", "the old place")}
    if str(site_id) in (pol.get("laid") or {}):
        return "laid", {}
    if site_id in (pol.get("cleared") or []):
        return "cleared", {}
    t = threats.records(w).get(adv["threat"])
    if t is not None and t["state"] != "ended" and t["home"].get("site") == site_id:
        return "held", {}
    return "", {}


def vignette_pages(game, adv: dict) -> list[dict]:
    """A page for each other place of the tale worth one: a town by its marks, a site by what became of it."""
    w = game.world
    town = _town(game, adv)
    seen = {("S", town.id)} if town is not None else set()
    out = []
    for key in sorted(adv["places"]):
        p = adv["places"][key] or {}
        if "settlement" in p:
            s = w.settlements[int(p["settlement"])]
            if ("S", s.id) in seen:
                continue
            seen.add(("S", s.id))
            mark = town_mark(s)
            text = _words(game, adv, f"vignette_{mark}", f"v/{key}", place=s.name) if mark else ""
        elif "site" in p:
            sid = int(p["site"])
            if ("X", sid) in seen or not 0 <= sid < len(w.sites):
                continue
            seen.add(("X", sid))
            state, more = site_state(game, adv, sid)
            text = _words(game, adv, f"vignette_{state}", f"v/{key}", place=w.sites[sid].name, **more) \
                if state else ""
        else:
            continue
        if text:
            out.append({"about": f"place:{key}", "text": text})
        if len(out) >= VIGNETTES:
            break
    return out


# ---------------------------------------------------------------------------- the realm, the sequel, you
def realm_of(game, adv: dict):
    """The realm the tale's town belongs to (its top liege of the group realms), or None."""
    from realmwalker.world import factions as fx

    s = _town(game, adv)
    if s is None:
        return None
    realm = fx.realm_of_settlement(game.world, s)
    if realm is None or game.tables.factions["kinds"].get(realm.kind, {}).get("group") != REALMS:
        return None
    return realm


def realm_page(game, adv: dict) -> dict | None:
    from realmwalker.world import factions as fx

    realm = realm_of(game, adv)
    if realm is None:
        return None
    how = {"won": "won", "abandoned": "abandoned"}.get(adv.get("state"), "lost")
    lead = fx.leader_of(game.world, realm)
    ruler = lead.full_name() if lead is not None and lead.alive else f"the lords of {realm.name}"
    town = _town(game, adv)
    text = _words(game, adv, f"epilogue_realm_{how}", "realm", realm=realm.name, ruler=ruler,
                  town=town.name if town is not None else "the town")
    return {"about": "realm", "text": text} if text else None


def sequel_page(game, adv: dict) -> dict | None:
    from realmwalker.game.story import sequels

    found = sequels.of_tale(game, adv)
    if found is None:
        return None
    kind, t = found
    text = _words(game, adv, f"epilogue_sequel_{kind}", "sequel", **sequels.words(game, adv, t))
    return {"about": "sequel", "text": text} if text else None


def hero_lines(game, adv: dict, before: dict) -> list[str]:
    """Your standing with the realm now, the title the tale gave you, your name on the roads."""
    from realmwalker.game import reputation
    from realmwalker.world import factions as fx

    out = []
    realm = realm_of(game, adv)
    if realm is not None and abs(reputation.standing(game, realm.id)) >= SPOKEN:
        name = fx.standing_name(game.tables, reputation.standing(game, realm.id))[0].lower()
        out.append(_words(game, adv, "hero_standing", "standing", realm=realm.name, standing=name))
    titles = game.renown.flags.get("titles", [])
    if len(titles) > int(before.get("titles", len(titles))):
        out.append(_words(game, adv, "hero_title", "title", title=f"{titles[-1]['title']} {game.leader.name}"))
    fame, infamy = int(game.renown.fame), int(game.renown.infamy)
    if infamy >= FAMED and infamy > int(before.get("infamy", infamy)) and infamy >= fame:
        out.append(_words(game, adv, "hero_infamy", "infamy"))
    elif fame >= FAMED and fame > int(before.get("fame", fame)):
        out.append(_words(game, adv, "hero_fame", "fame"))
    return [x for x in out if x]


# ---------------------------------------------------------------------------- the whole
def compose(game, adv: dict, before: dict | None = None) -> list[dict]:
    """The epilogue's last word (endings.finish): the places as they are, the realm, the sequel, you; in order."""
    before = before or {}
    pages = [dict(p) for p in adv.get("epilogue", [])]
    town = _town(game, adv)
    mark = town_mark(town)
    for p in pages:
        if p["about"] == "place" and mark:
            more = _words(game, adv, f"vignette_{mark}", "v/town", place=town.name)
            if more:
                p["text"] = f"{p['text']} {more}"
    pages += vignette_pages(game, adv)
    for extra in (realm_page(game, adv), sequel_page(game, adv)):
        if extra is not None:
            pages.append(extra)
    hero = next((p for p in pages if p["about"] == "hero"), None)
    lines = hero_lines(game, adv, before)
    if lines:
        if hero is None:
            hero = {"about": "hero", "text": ""}
            pages.append(hero)
        hero["text"] = " ".join(x for x in [hero["text"]] + lines if x)
    pages = [p for _, p in sorted(enumerate(pages), key=lambda ip: (_rank(ip[1]["about"]), ip[0]))]
    while len(pages) > MOST:
        cut = next((i for kind, keep in DROP for i in range(len(pages) - 1, -1, -1)
                    if _kind(pages[i]["about"]) == kind
                    and sum(_kind(p["about"]) == kind for p in pages) > keep), None)
        if cut is None:
            break
        pages.pop(cut)
    adv["epilogue"] = pages
    return pages


# ---------------------------------------------------------------------------- the chapter of history
def tales(world) -> list:
    return world.politics.setdefault("tales", [])


def tale_of(world, adv_id: str) -> int | None:
    return next((i for i, r in enumerate(tales(world)) if r.get("adv") == adv_id), None)


def _place_refs(game, adv: dict) -> list[str]:
    out = []
    for key in sorted(adv["places"]):
        p = adv["places"][key] or {}
        ref = f"S{int(p['settlement'])}" if "settlement" in p else f"X{int(p['site'])}" if "site" in p else None
        if ref and ref not in out:
            out.append(ref)
    return out


def chronicle(game, adv: dict) -> dict:
    """The tale as a named chapter of the world's history (once): kept in `politics["tales"]` for the Legends book."""
    from realmwalker.game.story import endings
    from realmwalker.world import threats

    w = game.world
    i = tale_of(w, adv["id"])
    if i is not None:
        return tales(w)[i]
    t = threats.records(w).get(adv["threat"]) or {}
    fig = threats.villain_figure(w, t) if t else None
    cal = game.tables.calendar
    began = cal.at(int(float(adv.get("began", 0)) * 1440)).year
    reached = [ch["title"] for ch in adv["chapters"] if ch["state"] in ("done", "open")]
    state = adv.get("state", "active")
    rec = {"adv": adv["id"], "title": adv["title"], "year": int(game.moment.year), "began": int(began),
           "hero": adv["hero"]["name"], "life": adv["hero"]["life"], "kind": t.get("kind", ""),
           "ending": adv.get("ending") or state, "state": state, "won": adv.get("ending") in endings.WON,
           "villain": fig.id if fig is not None else None,
           "villain_name": threats.villain_name(w, t) if t else "something",
           "places": _place_refs(game, adv), "chapters": reached,
           "pages": [dict(p) for p in adv.get("epilogue", [])],
           "sequel_of": adv.get("sequel_of") or (adv.get("returning") or {}).get("from")}
    tales(w).append(rec)
    return rec
