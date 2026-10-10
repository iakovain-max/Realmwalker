"""Reading the past back: the pages of the Legends book (logic only; the screen is ui/screens/legends.py).

Like Dwarf Fortress's Legends mode, every person, realm, place, war, beast, artifact, age, god and song of a world
has a page built from the structured history: who they were, how they are tied to everything else, and every event
they appear in, in order. Links are written [[REF|words]] where REF is "H12" a figure, "F3" a faction, "S5" a
settlement, "X7" a site, "W2" a war, "A4" an artifact, "E1" an age and "K3" a work; the screen draws them in their own
colour and follows them. Everything else in a line is ordinary markup (ui/markup).

Worlds made before the ages were lived have less to tell, and their pages say what there is.
"""

from __future__ import annotations

import re
from collections import defaultdict

from realmwalker.world import factions as fx

CATEGORIES = [("ages", "Ages"), ("realms", "Realms and powers"), ("people", "People"), ("places", "Places"),
              ("wars", "Wars"), ("beasts", "Beasts"), ("artifacts", "Artifacts"), ("gods", "Gods"),
              ("works", "Songs and books")]
LINK_RE = re.compile(r"\[\[([A-Z]\d+)\|([^\]]*)\]\]")
SITE_WORDS = {"ruin": "a ruin", "cave": "a cave", "barrow": "a barrow", "tower": "a lonely tower"}
KIND_WORDS = {"hamlet": "a hamlet", "village": "a village", "town": "a town", "city": "a city",
              "hold": "a dwarven hold", "elfhall": "an elven hall"}
MAX_EVENTS = 120


def link(ref: str, text: str) -> str:
    return f"[[{ref}|{clean(text)}]]"


def clean(text: str) -> str:
    """Text from the world, safe to put in a line: no markup, no link brackets."""
    return str(text).replace("<", "(").replace(">", ")").replace("[[", "(").replace("]]", ")").replace("|", "/")


def cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


# ---------------------------------------------------------------------------- the index
class Index:
    """Which events each thing appears in (made once for a history, and again when it grows)."""

    def __init__(self, world) -> None:
        self.events = world.history
        self.fig = defaultdict(list)
        self.fac = defaultdict(list)
        self.place = defaultdict(list)
        self.site = defaultdict(list)
        self.war = defaultdict(list)
        self.art = defaultdict(list)
        for i, e in enumerate(world.history):
            for h in e.get("figures", ()):
                self.fig[h].append(i)
            for f in e.get("factions", ()):
                self.fac[f].append(i)
            for p in e.get("places", ()):
                self.place[p].append(i)
            for x in e.get("sites", ()):
                self.site[x].append(i)
            if "war" in e:
                self.war[e["war"]].append(i)
            data = e.get("data") or {}
            for a in data.get("artifacts", ()):
                self.art[a].append(i)
            if "artifact" in data:
                self.art[data["artifact"]].append(i)
        self.ledger = defaultdict(list)  # settlement id -> [(year, holder faction id)]
        for e in world.history:
            for sid, fid in (e.get("data") or {}).get("owners", ()):
                self.ledger[sid].append((e["year"], fid))


_CACHE: dict[int, tuple[int, Index]] = {}


def index(world) -> Index:
    key = id(world)
    cached = _CACHE.get(key)
    if cached is None or cached[0] != len(world.history) or cached[1].events is not world.history:
        _CACHE.clear()
        cached = (len(world.history), Index(world))
        _CACHE[key] = cached
    return cached[1]


# ---------------------------------------------------------------------------- names of things, as links
def fig_link(world, hid: int) -> str:
    fig = world.figures.get(hid)
    if fig is None:
        return "someone forgotten"
    return link(f"H{hid}", fig.full_name() if fig.kind == "person" else f"{fig.name} {fig.epithet}".strip())


def fac_link(world, fid: int) -> str:
    f = world.factions.get(fid)
    return link(f"F{fid}", f.name) if f is not None else "a power long gone"


def place_ref_link(world, ref: str) -> str:
    if ref.startswith("S") and ref[1:].isdigit() and int(ref[1:]) < len(world.settlements):
        return link(ref, world.settlements[int(ref[1:])].name)
    if ref.startswith("X") and ref[1:].isdigit() and int(ref[1:]) < len(world.sites):
        return link(ref, world.sites[int(ref[1:])].name)
    return ""


def year_text(year: int | None) -> str:
    """The years count from the Reckoning; anything older is so many years Before the Reckoning."""
    if year is None:
        return "?"
    return str(year) if year > 0 else f"{1 - year} B.R."


def chips(world, e: dict, own: str) -> str:
    """The other things an event names, as links (the page's own subject left out)."""
    out = []
    for h in e.get("figures", ())[:4]:
        if f"H{h}" != own and h in world.figures:
            out.append(fig_link(world, h))
    for f in e.get("factions", ())[:2]:
        if f"F{f}" != own and f in world.factions:
            out.append(fac_link(world, f))
    for p in e.get("places", ())[:2]:
        if f"S{p}" != own and 0 <= p < len(world.settlements):
            out.append(link(f"S{p}", world.settlements[p].name))
    for x in e.get("sites", ())[:2]:
        if f"X{x}" != own and 0 <= x < len(world.sites):
            out.append(link(f"X{x}", world.sites[x].name))
    if "war" in e and f"W{e['war']}" != own:
        war = war_by_id(world, e["war"])
        if war is not None:
            out.append(link(f"W{war['id']}", war.get("name") or "a war"))
    return ("  <faint>·</> " + " <faint>·</> ".join(out[:5])) if out else ""


def names_in(world, e: dict) -> list[tuple[str, str]]:
    """Every way the things an event names may be written in its text, with their pages."""
    out: list[tuple[str, str]] = []
    for h in e.get("figures", ()):
        fig = world.figures.get(h)
        if fig is None:
            continue
        ways = {fig.full_name(), fig.name, f"{fig.name} {fig.epithet}".strip()}
        if fig.regnal:
            ways.add(f"{fig.first_name} {fig.regnal}")
        if fig.title and not fig.title.startswith("the "):
            ways.add(f"{fig.title} {fig.name}")
        out += [(way, f"H{h}") for way in ways]
    for f in e.get("factions", ()):
        if f in world.factions:
            name = world.factions[f].name
            out += [(name, f"F{f}"), (cap(name), f"F{f}")]
    for p in e.get("places", ()):
        if 0 <= p < len(world.settlements):
            out.append((world.settlements[p].name, f"S{p}"))
    for x in e.get("sites", ()):
        if 0 <= x < len(world.sites):
            out += [(world.sites[x].name, f"X{x}"), (cap(world.sites[x].name), f"X{x}")]
    if "war" in e:
        war = war_by_id(world, e["war"])
        if war is not None and war.get("name"):
            out += [(war["name"], f"W{war['id']}"), (cap(war["name"]), f"W{war['id']}")]
    return [(clean(way), ref) for way, ref in out if len(way) >= 3]


def linked(world, e: dict, own: str) -> str:
    """An event's words with the names in them made links (the page's own subject left plain), and links after it
    to whatever it names that its words do not."""
    text = clean(e["text"])
    taken: list[tuple[int, int, str]] = []
    found: set[str] = set()
    for way, ref in sorted(names_in(world, e), key=lambda t: -len(t[0])):
        start = text.find(way)
        while start >= 0:
            end = start + len(way)
            if all(end <= a or start >= b for a, b, _ in taken):
                taken.append((start, end, ref))
                found.add(ref)
                break
            start = text.find(way, start + 1)
    out, pos = [], 0
    for start, end, ref in sorted(taken):
        out.append(text[pos:start])
        out.append(text[start:end] if ref == own else f"[[{ref}|{text[start:end]}]]")
        pos = end
    out.append(text[pos:])
    rest = {"figures": [h for h in e.get("figures", ()) if f"H{h}" not in found],
            "factions": [f for f in e.get("factions", ()) if f"F{f}" not in found],
            "places": [p for p in e.get("places", ()) if f"S{p}" not in found],
            "sites": [x for x in e.get("sites", ()) if f"X{x}" not in found]}
    if "war" in e and f"W{e['war']}" not in found:
        rest["war"] = e["war"]
    return "".join(out) + chips(world, rest, own)


def timeline(world, ids: list[int], own: str, *, least: int = 1, most: int = MAX_EVENTS) -> list[str]:
    events = [world.history[i] for i in ids if i < len(world.history)]
    events = [e for e in events if e.get("importance", 2) >= least and e.get("text")]
    if len(events) > most:
        events = sorted(events, key=lambda e: (-e.get("importance", 2), e["year"]))[:most]
    events.sort(key=lambda e: (e["year"], e.get("id", 0)))
    return [f"<dim>{year_text(e['year'])}</>  {linked(world, e, own)}" for e in events]


def war_by_id(world, wid: int) -> dict | None:
    for war in world.wars:
        if war.get("id") == wid:
            return war
    return None


# ---------------------------------------------------------------------------- the lists
def entries(world, tables, category: str, query: str = "") -> list[tuple[str, str]]:
    """(ref, label) for every page in a category, best known first; filtered by `query` (any part of the label)."""
    out = _entries(world, tables, category)
    q = query.strip().lower()
    if q:
        out = [(r, label) for r, label in out if q in label.lower()]
    return out


def _entries(world, tables, category: str) -> list[tuple[str, str]]:
    w = world
    if category == "ages":
        eras = w.politics.get("eras", [])
        out = []
        for i, era in enumerate(eras):
            if era.get("start") is None:
                when = f"before {year_text(era['end'])}"
            else:
                when = f"{year_text(era['start'])}–{year_text(era['end'] - 1)}"
            out.append((f"E{i}", f"{cap(era['name'])} ({when})"))
        return out
    if category == "realms":
        active = sorted(fx.active_factions(w), key=lambda f: (tables.factions["kinds"][f.kind]["group"] != "realms",
                                                               f.liege >= 0, f.name.lower().removeprefix("the ")))
        fallen = sorted((f for f in w.factions.values() if not f.active), key=lambda f: -(f.fallen or 0))
        return [(f"F{f.id}", cap(f.name)) for f in active] + \
            [(f"F{f.id}", f"{cap(f.name)} (fell {f.fallen})") for f in fallen]
    if category == "people":
        people = [f for f in w.figures.values() if f.kind == "person"]
        people.sort(key=lambda f: (-(f.fame + 5 * (f.role in ("ruler", "legend")) + 3 * f.alive), f.id))
        return [(f"H{f.id}", f.full_name() + ("" if f.alive else f" (d. {year_text(f.died)})")) for f in people]
    if category == "places":
        out = [(f"S{s.id}", f"{s.name} ({KIND_WORDS.get(s.kind, s.kind)[2:].removeprefix('n ')})")
               for s in sorted(w.settlements, key=lambda s: (-s.population, s.id))]
        out += [(f"X{s.id}", f"{cap(s.name)} ({s.kind})") for s in sorted(w.sites, key=lambda s: (s.kind, s.id))]
        return out
    if category == "wars":
        wars = sorted(w.wars, key=lambda war: (-(war.get("year") or 0), war.get("id", 0)))
        return [(f"W{war['id']}", f"{cap(war.get('name') or 'a war')} ({war.get('year')}"
                                  f"{'–' + str(war['end_year']) if war.get('end_year') else ', still fought'})")
                for war in wars if "id" in war]
    if category == "beasts":
        beasts = [f for f in w.figures.values() if f.kind in ("beast", "dragon")]
        beasts.sort(key=lambda f: (not f.alive, -f.fame, f.id))
        return [(f"H{f.id}", f"{f.name} {f.epithet}".strip() + ("" if f.alive else f" (slain {f.died})"
                                                                  if f.slayer >= 0 else f" (d. {f.died})"))
                for f in beasts]
    if category == "artifacts":
        arts = w.politics.get("artifacts", [])
        return [(f"A{i}", cap(a["name"])) for i, a in enumerate(arts)]
    if category == "gods":
        gods = [f for f in w.figures.values() if f.kind == "god"]
        return [(f"H{f.id}", f.name) for f in sorted(gods, key=lambda f: (-f.fame, f.id))]
    if category == "works":
        works = w.politics.get("works", [])
        return [(f"K{i}", f"{work['title']} ({work['year']})") for i, work in enumerate(works)]
    return []


# ---------------------------------------------------------------------------- pages
def page(world, tables, ref: str) -> tuple[str, list[str]]:
    """(title, lines) for one page; an unknown reference gets a page that says so."""
    kind, num = ref[:1], ref[1:]
    if not num.isdigit():
        return "Nothing", ["<dim>There is no such page.</>"]
    n = int(num)
    try:
        if kind == "H" and n in world.figures:
            return figure_page(world, tables, n)
        if kind == "F" and n in world.factions:
            return faction_page(world, tables, n)
        if kind == "S" and n < len(world.settlements):
            return settlement_page(world, tables, n)
        if kind == "X" and n < len(world.sites):
            return site_page(world, tables, n)
        if kind == "W" and war_by_id(world, n) is not None:
            return war_page(world, tables, n)
        if kind == "A" and n < len(world.politics.get("artifacts", [])):
            return artifact_page(world, tables, n)
        if kind == "E" and n < len(world.politics.get("eras", [])):
            return era_page(world, tables, n)
        if kind == "K" and n < len(world.politics.get("works", [])):
            return work_page(world, tables, n)
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return "Nothing", ["<dim>Nothing is remembered of that.</>"]


def section(title: str) -> str:
    return f"<title>{title}</>"


def figure_page(world, tables, hid: int) -> tuple[str, list[str]]:
    w = world
    fig = w.figures[hid]
    own = f"H{hid}"
    ix = index(w)
    year = tables.calendar.at(w.time).year
    lines: list[str] = []
    if fig.kind == "god":
        faith = next((fid for fid, f in tables.factions["faiths"].items()
                      if f["god"] == fig.name or fig.name in f.get("god", "")), None)
        church = next((f for f in w.factions.values() if f.kind in ("temple", "cult") and f.faith == faith), None)
        lines.append(f"A power worshipped {('by ' + fac_link(w, church.id)) if church else 'in the old days'}.")
        if fig.spheres:
            lines.append(f"<dim>Spheres:</> {', '.join(clean(s) for s in fig.spheres)}.")
        lines += [""] + timeline(w, ix.fig.get(hid, []), own)
        return fig.name, lines
    if fig.kind in ("beast", "dragon"):
        beast = tables.creatures[fig.creature].get("name", fig.creature) if fig.creature in tables.creatures else \
            fig.creature
        lair = place_ref_link(w, fig.home)
        lines.append(f"A {clean(beast)}" + (f", whose lair is {lair}" if lair and fig.alive else
                                             f", that laired in {lair}" if lair else "") + ".")
        lines.append(f"First known in {year_text(fig.born)}." if fig.alive else
                     f"Died in {fig.died}, {clean(fig.cause)}.")
    else:
        race = tables.races.get(fig.race, {}).get("name", fig.race).lower()
        people = tables.names["cultures"].get(fig.culture, {}).get("label", "")
        who = {"male": "man", "female": "woman"}.get(fig.sex, "person")
        lines.append(f"A {clean(race)} {who}" + (f" of the {clean(people)} people" if people else "") +
                     f", born in {year_text(fig.born)}.")
        if fig.alive:
            lines.append(f"Living, {fig.age(year)} years old" + (f", in {place_ref_link(w, fig.home)}"
                                                                 if place_ref_link(w, fig.home) else "") + ".")
        else:
            where = place_ref_link(w, fig.died_at)
            lines.append(f"Died in {year_text(fig.died)}, {clean(fig.cause)}" + (f" ({where})" if where else "") +
                         f", aged {max(0, fig.age(year))}.")
        what = []
        if fig.job:
            what.append(clean(fig.job))
        if fig.cls and fig.level:
            what.append(f"{clean(fig.cls)} of the {ordinal(fig.level)} rank")
        if what:
            lines.append(cap(", ".join(what)) + ".")
    f = w.factions.get(fig.faction)
    if f is not None:
        if f.leader == hid and fig.alive and f.active:
            lines.append(f"{clean(fig.title or 'Head')} of {fac_link(w, f.id)}.")
        else:
            lines.append(f"Of {fac_link(w, f.id)}.")
    led = [g for g in w.factions.values() if hid in g.rulers and g.id != fig.faction]
    if led:
        lines.append("Ruled " + ", ".join(fac_link(w, g.id) for g in led) + ".")
    family = []
    for label, pid in (("Father", fig.father), ("Mother", fig.mother), ("Married to", fig.spouse)):
        if pid >= 0 and pid in w.figures:
            family.append(f"<dim>{label}:</> {fig_link(w, pid)}")
    kids = [k for k in w.figures.values() if hid in (k.mother, k.father)]
    if kids:
        kids.sort(key=lambda k: k.born)
        family.append("<dim>Children:</> " + ", ".join(fig_link(w, k.id) for k in kids[:12]))
    sibs = [k for k in w.figures.values() if k.id != hid and k.kind == "person" and
            ((fig.father >= 0 and k.father == fig.father) or (fig.mother >= 0 and k.mother == fig.mother))]
    if sibs:
        sibs.sort(key=lambda k: k.born)
        family.append("<dim>Brothers and sisters:</> " + ", ".join(fig_link(w, k.id) for k in sibs[:10]))
    if family:
        lines += [""] + family
    deeds = []
    if fig.kills:
        deeds.append("<dim>Slew:</> " + ", ".join(fig_link(w, k) for k in fig.kills[:14]) +
                     (f" and {len(fig.kills) - 14} more" if len(fig.kills) > 14 else ""))
    if fig.slayer >= 0:
        deeds.append(f"<dim>Slain by:</> {fig_link(w, fig.slayer)}")
    if fig.buried:
        deeds.append(f"<dim>Buried in:</> {place_ref_link(w, fig.buried)}")
    arts = w.politics.get("artifacts", [])
    held = [i for i, a in enumerate(arts) if a.get("holder") == hid]
    made = [i for i, a in enumerate(arts) if a.get("maker") == hid]
    if held:
        deeds.append("<dim>Carries:</> " + ", ".join(link(f"A{i}", arts[i]["name"]) for i in held))
    if made:
        deeds.append("<dim>Made:</> " + ", ".join(link(f"A{i}", arts[i]["name"]) for i in made))
    works = [i for i, k in enumerate(w.politics.get("works", [])) if k.get("author") == hid]
    if works:
        deeds.append("<dim>Wrote:</> " + ", ".join(link(f"K{i}", w.politics["works"][i]["title"]) for i in works))
    if fig.notes:
        deeds.append("<dim>Remembered for:</> " + "; ".join(clean(n) for n in fig.notes) + ".")
    if deeds:
        lines += [""] + deeds
    life = timeline(w, ix.fig.get(hid, []), own)
    if life:
        lines += ["", section("Life")] + life
    return fig.full_name() if fig.kind == "person" else f"{fig.name} {fig.epithet}".strip(), lines


def ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third"}.get(n, f"{n}th")


def faction_page(world, tables, fid: int) -> tuple[str, list[str]]:
    w = world
    f = w.factions[fid]
    own = f"F{fid}"
    ix = index(w)
    label = fx.kind_label(tables, f)
    lines = [f"{cap(label)}, founded in {year_text(f.founded)}" +
             (f"; it fell in {f.fallen}." if not f.active else ".")]
    if 0 <= f.seat < len(w.settlements):
        lines.append(f"<dim>Seat:</> {link(f'S{f.seat}', w.settlements[f.seat].name)}")
    elif f.flags.get("old_seat"):
        lines.append(f"<dim>Seat, once:</> {place_ref_link(w, f.flags['old_seat'])}")
    if 0 <= f.site < len(w.sites):
        lines.append(f"<dim>Lair:</> {link(f'X{f.site}', w.sites[f.site].name)}")
    if f.liege >= 0:
        lines.append(f"<dim>Sworn to:</> {fac_link(w, f.liege)}")
    vassals = [v for v in w.factions.values() if v.liege == fid and v.active]
    if vassals:
        lines.append("<dim>Sworn to them:</> " + ", ".join(fac_link(w, v.id) for v in vassals))
    if f.active and f.leader in w.figures:
        lines.append(f"<dim>Led by:</> {fig_link(w, f.leader)}")
    if f.values:
        lines.append(f"<dim>They hold to:</> {', '.join(clean(v) for v in f.values)}.")
    if f.goals and f.active:
        lines.append(f"<dim>They want:</> {'; '.join(clean(g) for g in f.goals)}.")
    held = [s for s in w.settlements if s.owner == fid]
    if held:
        lines.append("<dim>Holds:</> " + ", ".join(link(f"S{s.id}", s.name) for s in held))
    if f.rulers:
        lines += ["", section("Those who led them")]
        for rid in f.rulers:
            r = w.figures.get(rid)
            if r is None:
                continue
            end = "today" if r.alive and f.leader == rid else (f"died {r.died}" if r.died is not None else "")
            lines.append(f"{fig_link(w, rid)} <dim>({end})</>" if end else fig_link(w, rid))
    wars = [war for war in w.wars if fid in (war.get("attacker"), war.get("defender")) or
            fid in war.get("allies", {}).get("attacker", []) or fid in war.get("allies", {}).get("defender", [])]
    if wars:
        lines += ["", section("Wars")]
        for war in sorted(wars, key=lambda war: war.get("year") or 0):
            result = {"attacker": "won by the attackers", "defender": "won by the defenders", "draw": "a draw"}.get(
                war.get("result", ""), "still fought" if war.get("active") else "")
            lines.append(f"{link(f'W{war['id']}', war.get('name') or 'a war')} <dim>({war.get('year')}"
                         f"{'–' + str(war['end_year']) if war.get('end_year') else ''}{', ' + result if result else ''})"
                         f"</>")
    life = timeline(w, ix.fac.get(fid, []), own, least=2)
    if life:
        lines += ["", section("Their history")] + life
    return cap(f.name), lines


def settlement_page(world, tables, sid: int) -> tuple[str, list[str]]:
    w = world
    s = w.settlements[sid]
    own = f"S{sid}"
    ix = index(w)
    people = tables.names["cultures"].get(s.culture, {}).get("label", s.culture)
    lines = [f"{cap(KIND_WORDS.get(s.kind, s.kind))} of the {clean(people)} people, of about {s.population:,} souls."]
    place = w.politics.get("places", {}).get(str(sid))
    if place:
        lines.append(f"Founded in {year_text(place.get('founded'))}." if place.get("founded") is not None else "")
        names = place.get("names", [])
        if len(names) > 1:
            lines.append("<dim>Once called:</> " + ", ".join(f"{clean(n)} ({y})" for n, y in names[:-1]))
        if place.get("times", 1) > 1:
            lines.append(f"<dim>It has been built {place['times']} times.</>")
    elif str(sid) in w.politics.get("founded", {}):
        lines.append(f"Founded in {w.politics['founded'][str(sid)]}.")
    owner = w.factions.get(s.owner)
    if owner is not None:
        top = fx.top_liege(w, owner)
        lines.append(f"<dim>Held by:</> {fac_link(w, owner.id)}" +
                     (f", sworn to {fac_link(w, top.id)}" if top is not None and top is not owner else ""))
    holders = ix.ledger.get(sid, [])
    if len(holders) > 1:
        lines += ["", section("Who held it")]
        for y, fid in holders:
            lines.append(f"<dim>{year_text(y)}</>  {fac_link(w, fid) if fid >= 0 else 'nobody'}")
    here = [f for f in w.figures.values() if f.alive and f.kind == "person" and f.home == own]
    if here:
        here.sort(key=lambda f: (-f.fame, f.id))
        lines += ["", "<dim>People of note who live here:</> " + ", ".join(fig_link(w, f.id) for f in here[:16])]
    arts = [i for i, a in enumerate(w.politics.get("artifacts", [])) if a.get("place") == own and a.get("holder", -1) < 0]
    if arts:
        lines.append("<dim>Kept here:</> " + ", ".join(link(f"A{i}", w.politics["artifacts"][i]["name"]) for i in arts))
    life = timeline(w, ix.place.get(sid, []), own)
    if life:
        lines += ["", section("What happened here")] + life
    return s.name, [ln for ln in lines if ln is not None]


def site_page(world, tables, site_id: int) -> tuple[str, list[str]]:
    w = world
    site = w.sites[site_id]
    own = f"X{site_id}"
    ix = index(w)
    pol = w.politics
    lines = [f"{cap(SITE_WORDS.get(site.kind, site.kind))}."]
    past = pol.get("ruins", {}).get(str(site_id))
    if past:
        if past.get("elder"):
            lines.append(f"It was {clean(past.get('was', 'something'))} of {clean(past.get('people', 'an old people'))}"
                         f", until {clean(past.get('cause', 'it fell'))} ({year_text(past.get('year'))}).")
        else:
            names = past.get("names") or [[past.get("name", "?"), past.get("founded")]]
            lines.append(f"Once {clean(past.get('was', 'a town'))}, founded in {year_text(names[0][1])}" +
                         (f", with {past['peak']:,} souls at its height" if past.get("peak") else "") + ".")
            fell = past.get("fell", past.get("year"))
            lines.append(f"It ended in {year_text(fell)}: {clean(past.get('cause', 'abandoned'))}.")
            for y, fid in past.get("holders", []):
                if fid >= 0:
                    lines.append(f"<dim>{year_text(y)}</>  held by {fac_link(w, fid)}")
    beast = pol.get("lairs", {}).get(str(site_id))
    if beast is not None:
        lines.append(f"<danger>Lair of</> {fig_link(w, beast)}.")
    tomb = pol.get("tombs", {}).get(str(site_id))
    if tomb is not None:
        lines.append(f"The tomb of {fig_link(w, tomb)}.")
    tower = pol.get("towers", {}).get(str(site_id))
    if tower is not None:
        lines.append(f"Raised by {fig_link(w, tower)}.")
    if site.faction >= 0 and site.faction in w.factions and w.factions[site.faction].active and \
            not w.factions[site.faction].secret:
        lines.append(f"<dim>Held by:</> {fac_link(w, site.faction)}")
    arts = [i for i, a in enumerate(pol.get("artifacts", [])) if a.get("site") == site_id]
    if arts:
        lines.append("<dim>Said to lie here:</> " + ", ".join(link(f"A{i}", pol["artifacts"][i]["name"]) for i in arts))
    life = timeline(w, ix.site.get(site_id, []), own)
    if life:
        lines += ["", section("What happened here")] + life
    return cap(site.name), lines


def war_page(world, tables, wid: int) -> tuple[str, list[str]]:
    w = world
    war = war_by_id(w, wid)
    own = f"W{wid}"
    ix = index(w)
    reason = tables.politics["war_reasons"].get(war.get("reason", ""), war.get("reason", ""))
    lines = [f"{fac_link(w, war['attacker'])} against {fac_link(w, war['defender'])}, over {clean(reason)}."]
    allies = war.get("allies", {})
    for side, label in (("attacker", "With the attackers"), ("defender", "With the defenders")):
        if allies.get(side):
            lines.append(f"<dim>{label}:</> " + ", ".join(fac_link(w, f) for f in allies[side]))
    end = war.get("end_year")
    lines.append(f"From {war.get('year')} to {end}." if end else f"Begun in {war.get('year')}, and still fought.")
    result = {"attacker": f"{fac_link(w, war['attacker'])} won", "defender": f"{fac_link(w, war['defender'])} won",
              "draw": "Nothing was settled"}.get(war.get("result", ""))
    if result:
        lines.append(result + ".")
    if war.get("battles"):
        lines.append(f"{war['battles']} battles; {war.get('dead', 0):,} dead.")
    taken = [place_ref_link(w, r) for r in war.get("taken", []) if isinstance(r, str)]
    taken = [t for t in taken if t]
    if taken:
        lines.append("<dim>Places taken or destroyed:</> " + ", ".join(dict.fromkeys(taken)))
    if war.get("claimant", -1) >= 0:
        lines.append(f"<dim>Fought for the claim of:</> {fig_link(w, war['claimant'])}")
    life = timeline(w, ix.war.get(wid, []), own)
    if life:
        lines += ["", section("The war")] + life
    return cap(war.get("name") or "A war"), lines


def artifact_page(world, tables, aid: int) -> tuple[str, list[str]]:
    w = world
    a = w.politics["artifacts"][aid]
    own = f"A{aid}"
    ix = index(w)
    lines = []
    what = f"{cap(a.get('kind', 'thing'))}" + (f" of {clean(a['material'])}" if a.get("material") else "")
    made = a.get("made")
    maker = a.get("maker", -1)
    lines.append(what + (f", made in {year_text(made)}" if made is not None else "") +
                 (f" by {fig_link(w, maker)}" if maker >= 0 else "") + ".")
    if a.get("bearer", -1) >= 0:
        lines.append(f"<dim>First borne by:</> {fig_link(w, a['bearer'])}")
    if a.get("holder", -1) >= 0:
        lines.append(f"<good>Held now by</> {fig_link(w, a['holder'])}.")
    elif a.get("site", -1) >= 0:
        lines.append(f"<loot>It lies in</> {link('X' + str(a['site']), w.sites[a['site']].name)}" +
                     (" <dim>(found)</>" if a.get("found") else "") + ".")
    elif a.get("place"):
        lines.append(f"It is kept in {place_ref_link(w, a['place'])}.")
    if a.get("fate"):
        lines.append(f"<dim>It {clean(a['fate'])}.</>")
    story = sorted(set(a.get("story", [])) | set(ix.art.get(aid, [])))
    by_id = {e.get("id"): i for i, e in enumerate(w.history) if "id" in e}
    ids = [by_id[s] for s in a.get("story", []) if s in by_id] + ix.art.get(aid, [])
    life = timeline(w, sorted(set(ids)), own)
    if life:
        lines += ["", section("Its story")] + life
    del story
    return cap(a["name"]), lines


def era_page(world, tables, i: int) -> tuple[str, list[str]]:
    w = world
    era = w.politics["eras"][i]
    lines = [f"<dim>{('Before ' + str(era['end'])) if era.get('start') is None else str(era['start']) + ' to ' + str(era['end'] - 1)}</>",
             clean(era.get("summary", ""))]
    start = era.get("start")
    end = era["end"]
    ids = [k for k, e in enumerate(w.history) if (start is None or e["year"] >= start) and e["year"] < end]
    life = timeline(w, ids, f"E{i}", least=3 if start is not None else 2, most=60)
    if life:
        lines += ["", section("What was remembered")] + life
    return cap(era["name"]), lines


def work_page(world, tables, i: int) -> tuple[str, list[str]]:
    w = world
    work = w.politics["works"][i]
    form = tables.history["works"]["forms"].get(work.get("form", ""), {}).get("word", "a work")
    lines = [f"{cap(form)} by {fig_link(w, work['author'])}, {work.get('year')}."]
    about = work.get("about", {})
    if "figure" in about:
        lines.append(f"<dim>Of:</> {fig_link(w, about['figure'])}")
    if "war" in about:
        war = war_by_id(w, about["war"])
        if war is not None:
            lines.append(f"<dim>Of:</> {link('W' + str(war['id']), war.get('name') or 'a war')}")
    if "faction" in about:
        lines.append(f"<dim>Of:</> {fac_link(w, about['faction'])}")
    if "event" in about:
        e = next((e for e in w.history if e.get("id") == about["event"]), None)
        if e is not None:
            lines.append(f"<dim>It tells how:</> {clean(e['text'])}")
    if work.get("place"):
        lines.append(f"<dim>Written in:</> {place_ref_link(w, work['place'])}")
    return work["title"], lines


# ---------------------------------------------------------------------------- reading a line
def segments(line: str) -> list[tuple[str, str | None]]:
    """A line split into (markup text, link ref or None) pieces."""
    out: list[tuple[str, str | None]] = []
    pos = 0
    for m in LINK_RE.finditer(line):
        if m.start() > pos:
            out.append((line[pos:m.start()], None))
        out.append((m.group(2), m.group(1)))
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], None))
    return out


def plain(line: str) -> str:
    """A line without its links (for tests and for anything that only wants the words)."""
    return LINK_RE.sub(lambda m: m.group(2), line)
