"""AgeSim: the state of a history being lived, the yearly loop, and how what happens is written down.

Each year every part of the world takes its turn (land, folk, realms, war, the wild, faith, lore, orders, troubles),
always in the same order and from the same seeded streams, so the same seed lives the same history. What is worth
remembering becomes an event in `world.history`; whatever is left standing at the end is today (present.py).

References between things use short strings where a field may point at more than one kind of thing:
"S12" a settlement, "X5" a site, "F3" a faction, "H44" a figure, "A2" an artifact, "W7" a war, "E99" an event.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Callable

from realmwalker.core.rng import RNG
from realmwalker.world import factions as fx

log = logging.getLogger("realmwalker.ages")

DYNASTIC = ("kingdom", "noble_house", "clan", "highland_clan", "elven_realm")
POWER_KINDS = ("kingdom", "free_city", "clan", "highland_clan", "elven_realm", "noble_house", "tribe")
HUMAN_KINDS = ("hamlet", "village", "town", "city")


def S(sid: int) -> str:
    return f"S{sid}"


def X(site: int) -> str:
    return f"X{site}"


def ident(thing) -> int:
    return int(thing.id) if hasattr(thing, "id") else int(thing)


class AgeSim:
    def __init__(self, world, tables, rng: RNG, *, years: int, spots: list[dict], namer,
                 progress: Callable[[int, int, int, str], None] | None = None) -> None:
        self.w = world
        self.t = tables
        self.data = tables.history
        self.rng = rng
        self.r = rng.child("setup")  # the stream of the year being lived (or of the setting up)
        self.present = tables.calendar.start_year
        self.years = max(10, int(years))
        self.year0 = self.present - self.years
        self.year = self.year0
        sizes = ["small", "medium", "large"]
        self.size = sizes.index(world.meta.size) if world.meta.size in sizes else 1
        self.spot_plan = spots
        self.namer = namer
        self.progress = progress
        self.living: set[int] = set()  # figures alive: people and beasts (gods are not counted)
        self.next_event = 0
        self.version = 0  # bumped whenever factions appear, fall or change liege or kind (see touch())
        self._active: tuple[int, list] = (-1, [])
        self._vassals: tuple[int, dict] = (-1, {})
        self.ruins_info: dict[int, dict] = {}  # spot id -> how a place ended (for the ruins of today)
        self.ruins_by_site: dict[str, dict] = {}  # ruin site id -> its past (made at the end)
        self.peak: dict[int, float] = {}  # spot id -> the most people it ever had
        self.top_realm: dict[int, str] = {}  # year -> the greatest realm then (for naming eras)
        self.stats: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.headline = ""
        self.started = time.monotonic()
        self.fm = fx.FactionMaker(world, tables, rng.child("dress"))  # names, laws and colours; never run()
        self.fm.namer = namer
        from realmwalker.world.ages.faith import Faith
        from realmwalker.world.ages.folk import Folk
        from realmwalker.world.ages.land import Land
        from realmwalker.world.ages.lore import Lore
        from realmwalker.world.ages.orders import Orders
        from realmwalker.world.ages.realms import Realms
        from realmwalker.world.ages.war import War
        from realmwalker.world.ages.wild import Wild
        from realmwalker.world.ages.words import Words

        self.words = Words(self)
        self.land = Land(self)
        self.folk = Folk(self)
        self.realms = Realms(self)
        self.war = War(self)
        self.wild = Wild(self)
        self.faith = Faith(self)
        self.lore = Lore(self)
        self.orders = Orders(self)

    # ------------------------------------------------------------------ numbers from data/history.json
    def per_size(self, key: str, section: str = "start") -> int:
        """A number by world size: from data/history.json, or (section "counts") data/factions.json "counts"."""
        values = self.t.factions["counts"][key] if section == "counts" else self.data[section][key]
        return int(values[min(self.size, len(values) - 1)])

    def rate(self, key: str) -> float:
        return float(self.data["rates"][key])

    def chance(self, key: str, scale: float = 1.0) -> bool:
        return self.r.chance(self.rate(key) * scale)

    def stat(self, name: str, amount: float = 1.0) -> None:
        self.stats[self.year][name] += amount

    # ------------------------------------------------------------------ the whole of it
    def run(self) -> None:
        w = self.w
        w.history.clear()
        w.wars.clear()
        w.factions.clear()
        w.figures.clear()
        w.next_figure_id = 0
        w.politics["next_war"] = 0
        self.land.setup()
        self.faith.setup_gods()
        self.realms.setup()
        self.faith.setup()
        self.wild.setup()
        self.lore.setup()
        self.orders.setup()
        for year in range(self.year0, self.present):
            self.year = year
            self.r = self.rng.child(f"year/{year}")
            self.land.year()
            self.folk.year()
            self.realms.year()
            self.war.year()
            self.wild.year()
            self.faith.year()
            self.lore.year()
            self.orders.year()
            self.land.troubles()
            self.report()
        self.year = self.present - 1
        self.r = self.rng.child("present")
        from realmwalker.world.ages.present import Present

        Present(self).finish()
        log.info("Lived %d years in %.1f s: %d figures, %d events, %d wars", self.years,
                 time.monotonic() - self.started, len(w.figures), len(w.history), len(w.wars))

    def report(self) -> None:
        if (self.year - self.year0) % 5 == 0:
            realms = [f for f in self.active("kingdom", "free_city", "clan", "elven_realm", "noble_house",
                                             "highland_clan") if f.liege < 0]
            if realms:
                best = max(realms, key=lambda f: (len(self.holdings(f, deep=True)), -f.id))
                for y in range(self.year, self.year + 5):
                    self.top_realm[y] = best.name
        if self.progress is not None:
            self.progress(self.year, len(self.w.figures), len(self.w.history), self.headline)

    # ------------------------------------------------------------------ writing it down
    def record(self, kind: str, values: dict | None = None, *, importance: int = 2, factions=(), places=(),
               sites=(), figures=(), war=None, data: dict | None = None, year: int | None = None,
               text: str | None = None) -> dict:
        """Something worth remembering happened. Returns the event (a dict in world.history)."""
        if text is None:
            text = self.words.text(kind, values or {})
        e = {"id": self.next_event, "year": int(self.year if year is None else year), "kind": kind, "text": text,
             "importance": int(max(1, min(5, importance))),
             "factions": [ident(f) for f in factions if f is not None],
             "places": [ident(p) for p in places if p is not None],
             "figures": [ident(f) for f in figures if f is not None]}
        if sites:
            e["sites"] = [ident(s) for s in sites if s is not None]
        if war is not None:
            e["war"] = int(war["id"]) if isinstance(war, dict) else int(war)
        if data:
            e["data"] = data
        self.next_event += 1
        self.w.history.append(e)
        if importance >= 4:
            self.headline = text
        return e

    # ------------------------------------------------------------------ small helpers used everywhere
    def faction(self, fid: int):
        f = self.w.factions.get(fid)
        return f if f is not None and f.active else None

    def figure(self, hid: int):
        return self.w.figures.get(hid)

    def leader(self, f):
        if f is None:
            return None
        fig = self.w.figures.get(f.leader)
        return fig if fig is not None and fig.alive else None

    def settlement(self, sid: int):
        return self.w.settlements[sid]

    def place_name(self, sid: int) -> str:
        return self.w.settlements[sid].name or "a nameless place"

    def area_name(self, x: int, y: int) -> str | None:
        a = self.w.area_at(x, y)
        return a.name if a is not None else None

    def top(self, f):
        return fx.top_liege(self.w, f)

    def touch(self) -> None:
        """Factions appeared, fell, or changed liege or kind: the cached lists must be made again."""
        self.version += 1

    def holdings(self, f, deep: bool = False) -> list:
        """Standing settlements a faction holds (deep: with its vassals', and theirs)."""
        ids = [f.id]
        if deep:
            seen = {f.id}
            frontier = [f]
            while frontier:
                g = frontier.pop()
                for v in self.vassals(g):
                    if v.id not in seen:
                        seen.add(v.id)
                        ids.append(v.id)
                        frontier.append(v)
        sids: set[int] = set()
        for fid in ids:
            sids.update(self.land.held_by(fid))
        return [self.w.settlements[sid] for sid in sorted(sids)]

    def vassals(self, f) -> list:
        if self._vassals[0] != self.version:
            table: dict[int, list] = {}
            for g in self.active():
                if g.liege >= 0:
                    table.setdefault(g.liege, []).append(g)
            self._vassals = (self.version, table)
        return list(self._vassals[1].get(f.id, []))

    def active(self, *kinds: str) -> list:
        if self._active[0] != self.version:
            self._active = (self.version, [f for _, f in sorted(self.w.factions.items()) if f.active])
        everyone = self._active[1]
        return [f for f in everyone if f.active and (not kinds or f.kind in kinds)] if kinds else \
            [f for f in everyone if f.active]

    def powers(self) -> list:
        """Those who make war and peace for themselves."""
        return [f for f in self.active(*POWER_KINDS) if f.liege < 0 and self.leader(f) is not None]

    def anchor(self, f) -> tuple[int, int] | None:
        """Where a faction is: its seat, its lair, or its country."""
        w = self.w
        if 0 <= f.seat < len(w.settlements) and self.land.spots[f.seat].standing:
            s = w.settlements[f.seat]
            return s.x, s.y
        if 0 <= f.site < len(w.sites):
            site = w.sites[f.site]
            return site.x, site.y
        if 0 <= f.area < len(w.areas):
            a = w.areas[f.area]
            return a.x, a.y
        held = self.holdings(f)
        if held:
            return held[0].x, held[0].y
        return None


def live_the_ages(world, tables, rng: RNG, *, years: int, spots: list[dict], namer,
                  progress: Callable[[int, int, int, str], None] | None = None) -> AgeSim:
    sim = AgeSim(world, tables, rng, years=years, spots=spots, namer=namer, progress=progress)
    sim.run()
    return sim
