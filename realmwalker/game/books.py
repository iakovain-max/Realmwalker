"""Books, maps and letters (M8): paper is treasure in a world where few can read.

What you find in a chest may be worth more than the silver beside it: a map that puts places on your own map, a
book of histories that tells you who really held this country, old lore that names where a lost treasure came to
rest, a letter from someone who found something and did not live to use it.

Everything a book tells you is true of *this* world: it is drawn from the world's own history, factions, sites and
lost artifacts. Reading marks the places on your map; reading the same thing twice says the same words (the words
come from the item's own seeded stream), so nothing is lost and nothing is invented twice.
"""

from __future__ import annotations

import math

from realmwalker.core.textgen import escape_markup as esc
from realmwalker.world import factions as fx

KINDS = ("map", "history", "lore", "letter")
XP_FOR_LEARNING = 25


def kind_of(game, item) -> str | None:
    return game.tables.items.get(item.def_id).get("use", {}).get("read")


def rng_for(game, item):
    return game.world.rng.child(f"book/{item.def_id}/{item.uid}")


def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def remembered(game, item) -> list[str] | None:
    """What this very book said the first time (kept with the world, so it always says the same)."""
    return game.world.politics.get("books", {}).get(f"{item.def_id}/{item.uid}")


def read(game, char, item) -> list[str]:
    """Read it (an hour of squinting). Returns what it tells you, marked up."""
    kind = kind_of(game, item)
    if kind not in KINDS:
        return ["There is nothing to read there."]
    first = "read" not in item.tags
    if first:
        from realmwalker.game import magic_items

        magic_items.notice(game, "reading")
    rng = rng_for(game, item)
    game.pass_time(60, "rest")
    if game.over is not None:
        return []
    if not first:
        kept = remembered(game, item)
        if kept is not None:
            return list(kept)
    out = {"map": _map, "history": _history, "lore": _lore, "letter": _letter}[kind](game, rng, first)
    if first:
        game.world.politics.setdefault("books", {})[f"{item.def_id}/{item.uid}"] = list(out)
        item.tags = list(item.tags) + ["read"]
        if item.name.startswith(("sealed", "unread")):
            item.name = ""
        from realmwalker.rules.progression import award_xp

        if kind in ("history", "lore"):
            out += award_xp(char, XP_FOR_LEARNING, game.tables, rng, auto=True)
        game.dirty = True
    return out


# ---------------------------------------------------------------------------- what each kind tells you
def _map(game, rng, first: bool) -> list[str]:
    """An old map: places you did not know, marked on yours."""
    w = game.world
    p = game.player
    spots = [("site", s) for s in w.sites] + [("town", s) for s in w.settlements]
    spots = [(kind, s) for kind, s in spots if dist(s, p) <= 30]
    rng.shuffle(spots)
    named = []
    for kind, s in spots:
        if len(named) >= 5:
            break
        if kind == "town" and s.id in p.known_settlements:
            continue
        if kind == "site" and p.explored[s.x, s.y]:
            continue
        p.explored[s.x, s.y] = True
        if kind == "town":
            p.known_settlements.add(s.id)
        named.append(s.name)
    if not named:
        return ["<dim>An old map of country you already know. Someone drew the hills wrong.</>"]
    where = ", ".join(esc(n) for n in named[:-1])
    last = esc(named[-1])
    return [f"<info>The map is old, and the ink has run, but the hand was careful. It marks "
            f"{where}{' and ' if where else ''}{last}.</> <dim>(They are on your map now.)</>"]


def _history(game, rng, first: bool) -> list[str]:
    """A book of histories: who held this country, and what became of them."""
    w = game.world
    lines = []
    works = [k for k in w.politics.get("works", []) if k.get("form") in ("chronicle", "epic", "ballad", "lament")]
    if works and rng.chance(0.6):
        # A copy of something that was really written: the world's own chronicles and songs (world/ages).
        work = rng.choice(works)
        author = w.figures.get(work.get("author", -1))
        form = game.tables.history["works"]["forms"].get(work["form"], {}).get("word", "a work")
        by = f" by {author.full_name()}" if author is not None else ""
        lines.append(f"<info>It is a copy of {esc(work['title'])}, {esc(form)}{esc(by)}, written in "
                     f"{work.get('year')}.</>")
        about = work.get("about", {})
        told = [e for e in w.history if e.get("text") and e.get("importance", 2) >= 3 and (
            e.get("id") == about.get("event") or ("war" in about and e.get("war") == about["war"]) or
            ("faction" in about and about["faction"] in e.get("factions", ())) or
            ("figure" in about and about["figure"] in e.get("figures", ())))]
        if told:
            e = rng.choice(told)
            from realmwalker.game.past import lower_first

            lines.append(f"<info>It tells how, in {e['year']}, {esc(lower_first(e['text']))}</>")
    events = [e for e in w.history if e.get("importance", 2) >= 3]
    if events and len(lines) < 2:
        e = rng.choice(events)
        lines.append(f"<info>In the year {e['year']}: {esc(e['text'].rstrip('.'))}.</>")
    facs = [f for f in fx.active_factions(w) if not f.secret and f.id not in game.renown.known]
    if facs:
        f = min(facs, key=lambda f: abs(f.founded - w.meta.seed % 400))
        from realmwalker.game.reputation import know

        know(game, f.id)
        seat = w.settlements[f.seat].name if 0 <= f.seat < len(w.settlements) else "no seat anyone remembers"
        lines.append(f"<info>It gives an account of {esc(f.name)}, founded in {f.founded}, seated at "
                     f"{esc(seat)}.</> <dim>(They are in your list of factions now.)</>")
    figures = [fig for fig in w.figures.values() if fig.role == "legend" and fig.notes]
    if figures:
        fig = rng.choice(figures)
        lines.append(f"<dim>There is a page on {esc(fig.full_name())}, who {esc(fig.notes[0])}.</>")
    return lines or ["<dim>Dry pages about tithes and boundary stones. You learn nothing you can use.</>"]


def _lore(game, rng, first: bool) -> list[str]:
    """Old lore: where a lost treasure came to rest, or where a dragon sleeps."""
    w = game.world
    p = game.player
    artifacts = [a for a in w.politics.get("artifacts", []) if not a.get("found")
                 and 0 <= a.get("site", -1) < len(w.sites)]
    if artifacts:
        a = rng.choice(artifacts)
        site = w.sites[a["site"]]
        p.explored[site.x, site.y] = True
        return [f"<magic>{esc(a['name'])}</>: the book says it {esc(a.get('fate', 'was lost'))}. It names the place: "
                f"<place>{esc(site.name)}</>. <dim>(It is on your map now.)</>"]
    from realmwalker.game import dragons

    sleeping = dragons.living(w)
    if sleeping:
        d = rng.choice(sleeping)
        lair = w.sites[d["lair"]]
        p.explored[lair.x, lair.y] = True
        return [f"<danger>The book is about {esc(d['name'])}, a {d['color']} dragon, and where it went to sleep: "
                f"{esc(lair.name)}.</> <dim>(It is on your map now.)</> It says nothing useful about killing one."]
    return ["<dim>Old lore about older things, all of it already picked over.</>"]


def _letter(game, rng, first: bool) -> list[str]:
    """A dead stranger's letter: what they found, and what found them."""
    w = game.world
    p = game.player
    unknown = [s for s in w.sites if not p.explored[s.x, s.y]]
    cults = [f for f in fx.active_factions(w, "cult") if 0 <= f.site < len(w.sites) and f.id not in game.renown.known]
    if cults and rng.chance(0.4):
        f = rng.choice(cults)
        site = w.sites[f.site]
        p.explored[site.x, site.y] = True
        from realmwalker.game.reputation import know

        know(game, f.id)
        return [f"<warn>The hand is educated and shaking. It writes of lights at {esc(site.name)}, of people who go "
                f"there and do not come back, and of a name: {esc(f.name)}. It stops in the middle of a word.</> "
                f"<dim>(The place is on your map now.)</>"]
    if unknown:
        site = min(unknown, key=lambda s: dist(s, p))
        p.explored[site.x, site.y] = True
        return [f"<info>Someone wrote home about {esc(site.name)}: what they meant to find there, and how much of "
                f"the money was already spent. There is no second letter.</> <dim>(It is on your map now.)</>"]
    return ["<dim>A letter about a debt, between two people who are both long dead.</>"]
