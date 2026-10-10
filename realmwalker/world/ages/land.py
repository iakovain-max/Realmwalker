"""The places of the ages: where people settle, how they grow, who holds them, and how they end.

Every place a settlement could stand is a spot. Today's settlements (placed by the generator exactly as before) are
*fated*: they will stand at the end, though they may be sacked, burned or even razed and rebuilt on the way. The
generator also leaves *doomed* spots on good land: they are founded, live for a while and meet a real end (war, a
horde, a dragon, plague or simple abandonment), and become the ruins of today.

While the ages run, doomed spots are ordinary settlements appended to `world.settlements` (so every helper that
knows settlements works); present.py takes them out again and turns them into ruin sites.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from realmwalker.world.ages.sim import HUMAN_KINDS, S
from realmwalker.world.model import Settlement

LADDER = ("hamlet", "village", "town", "city")


@dataclass
class Spot:
    sid: int
    x: int
    y: int
    destiny: str  # what it is meant to become: hamlet, village, town, city, hold, elfhall
    fated: bool  # it stands today
    prior: str  # whose land this is before anyone comes (a culture)
    lo: int
    hi: int
    cap: float
    plan: int | None = None  # the year it is to be founded (None: an elder place, founded with its people)
    doom: int = 10**9  # a doomed place is gone by this year
    founded: int | None = None
    ruined: int | None = None
    rebuild: int | None = None  # a fated place that was razed is rebuilt this year
    pop: float = 0.0
    kind_now: str = "hamlet"
    founder: int = -1
    times: int = 0  # how many times a town has stood here
    near: list = field(default_factory=list)  # (distance, sid) of the other spots within reach, nearest first
    names: list = field(default_factory=list)  # [name, year founded under it]

    @property
    def standing(self) -> bool:
        return self.founded is not None and self.ruined is None

    @property
    def human(self) -> bool:
        return self.destiny in HUMAN_KINDS


class Land:
    def __init__(self, sim) -> None:
        self.s = sim
        self.spots: list[Spot] = []
        self.by_owner: dict[int, set[int]] = defaultdict(set)
        self.reach = float(sim.data["spots"]["reach"])
        types = sim.t.sites["settlement_types"]
        self.ranges = {k: tuple(v["population"]) for k, v in types.items()}
        self.thresholds = sim.data["spots"]["thresholds"]

    # ------------------------------------------------------------------ setting out the spots
    def setup(self) -> None:
        s = self.s
        w = s.w
        r = s.r
        for st in w.settlements:
            self.spots.append(self._spot(st.id, st.x, st.y, st.kind, True, st.culture))
            st.owner = -1
            st.population = 0
        for d in s.spot_plan:
            sid = len(w.settlements)
            w.settlements.append(Settlement(id=sid, name="", kind=d["kind"], x=d["x"], y=d["y"], culture=d["prior"],
                                            population=0, walled=False, area=d.get("area", -1)))
            self.spots.append(self._spot(sid, d["x"], d["y"], d["kind"], False, d["prior"]))
        w.rebuild_index()
        for a in self.spots:
            a.near = sorted((math.hypot(a.x - b.x, a.y - b.y), b.sid) for b in self.spots
                            if b is not a and math.hypot(a.x - b.x, a.y - b.y) <= self.reach * 1.6)
        plans = s.data["spots"]["plans"]
        y0, now, length = s.year0, s.present, s.years
        for sp in self.spots:
            if not sp.human:
                if not sp.fated:
                    sp.doom = r.randint(y0 + 15, max(y0 + 16, now - 5))  # an elder hall that falls in the ages
                continue
            key = sp.destiny if sp.fated else "doomed"
            lo, hi = plans[key]
            start = y0 + lo
            end = y0 + int(hi * length) if 0 <= hi <= 1 else now + int(hi)
            end = min(end, now - 4)
            start = min(start, end - 1)
            sp.plan = r.randint(start, end)
            if not sp.fated:
                after = max(sp.plan, y0) + int(s.data["spots"]["doom_after"])
                sp.doom = r.randint(min(after, now - 3), now - 3)
                sp.plan = min(sp.plan, sp.doom - 12)

    def _spot(self, sid: int, x: int, y: int, kind: str, fated: bool, prior: str) -> Spot:
        lo, hi = self.ranges.get(kind, (20, 80))
        cap = self.s.r.uniform(lo + (hi - lo) * 0.45, hi * 1.05)
        return Spot(sid=sid, x=x, y=y, destiny=kind, fated=fated, prior=prior, lo=lo, hi=hi, cap=cap)

    # ------------------------------------------------------------------ looking things up
    def standing(self) -> list[Spot]:
        return [sp for sp in self.spots if sp.standing]

    def held_by(self, fid: int) -> list[int]:
        return sorted(sid for sid in self.by_owner.get(fid, ()) if self.spots[sid].standing)

    def kind_of(self, sp: Spot) -> str:
        if not sp.human:
            return sp.destiny
        rank = 0
        for i, kind in enumerate(LADDER):
            if kind == "hamlet" or sp.pop >= self.thresholds[kind]:
                rank = i
        return LADDER[min(rank, LADDER.index(sp.destiny))]

    def words(self, sid: int) -> str:
        """'the village of Ashford' (as it is now)."""
        sp = self.spots[sid]
        kind = sp.kind_now if sp.human else {"hold": "dwarven hold", "elfhall": "elven hall"}.get(sp.destiny, "place")
        return f"the {kind} of {self.s.place_name(sid)}"

    def nearest_standing(self, x: int, y: int, within: float, test=None) -> list[tuple[float, int]]:
        out = []
        for sp in self.spots:
            if not sp.standing:
                continue
            d = math.hypot(sp.x - x, sp.y - y)
            if d <= within and (test is None or test(sp)):
                out.append((d, sp.sid))
        out.sort()
        return out

    # ------------------------------------------------------------------ ownership (every change is in an event)
    def set_owner(self, sid: int, fid: int, event: dict | None) -> None:
        st = self.s.w.settlements[sid]
        old = st.owner
        if old >= 0:
            self.by_owner[old].discard(sid)
        st.owner = int(fid)
        if fid >= 0:
            self.by_owner[fid].add(sid)
        if event is None and old != fid:
            # Every change of hands is on record: the history is the ledger of who held what.
            new = self.s.w.factions.get(fid)
            event = self.s.record("came_under", {"place": st.name or "the place",
                                                 "holder": new.name if new is not None else "no lord"},
                                  importance=1, places=[sid], factions=[new] if new is not None else [])
        if event is not None:
            event.setdefault("data", {}).setdefault("owners", []).append([int(sid), int(fid)])

    # ------------------------------------------------------------------ the year
    def year(self) -> None:
        s = self.s
        y = s.year
        for sp in self.spots:
            if sp.standing:
                self.grow(sp)
                if not sp.fated and y >= sp.doom:
                    s.wild.doom(sp)
            elif sp.human and sp.ruined is None and sp.founded is None and sp.plan is not None and sp.plan <= y:
                self.settle(sp)
            elif sp.rebuild is not None and sp.rebuild <= y:
                self.settle(sp, rebuild=True)

    def grow(self, sp: Spot) -> None:
        s = self.s
        st = s.w.settlements[sp.sid]
        people = s.data["peoples"].get(st.culture) or s.data["peoples"]["heartland"]
        rate = float(people["growth"])
        if st.owner >= 0 and s.war.at_war(st.owner):
            rate *= 0.4
        sp.pop = max(5.0, sp.pop + rate * sp.pop * (1.0 - sp.pop / sp.cap))
        before = sp.kind_now
        sp.kind_now = self.kind_of(sp)
        if sp.human and LADDER.index(sp.kind_now) > LADDER.index(before) and sp.kind_now in ("town", "city"):
            owner = s.faction(st.owner)
            top = s.top(owner) if owner is not None else None
            ruler = s.leader(top) if top is not None else None
            kind = "became_city" if sp.kind_now == "city" else "became_town"
            s.record(kind, {"place": st.name, "ruler": ruler.full_name() if ruler else "its own burghers",
                            "realm": top.name if top is not None else "no realm"},
                     importance=3 if kind == "became_city" else 2, places=[sp.sid],
                     factions=[top] if top is not None else [], figures=[ruler] if ruler else [])
            s.faith.temple_for(sp)
            s.orders.town_grew(sp)

    # ------------------------------------------------------------------ founding
    def settle(self, sp: Spot, *, rebuild: bool = False, by=None, year: int | None = None, quiet: bool = False) -> None:
        """People come to a spot (again) and build. Who comes depends on whose lands are near."""
        s = self.s
        w = s.w
        st = w.settlements[sp.sid]
        founder_realm = by if by is not None else self.founding_realm(sp)
        culture = sp.prior
        if founder_realm is not None and founder_realm.kind != "tribe":
            culture = founder_realm.culture
            if sp.prior == "halfling" and culture == "heartland" and sp.destiny in ("hamlet", "village"):
                culture = "halfling"  # the little folk settle under a heartland lord's protection
        if culture in ("dwarven", "elven", "orcish") and sp.human:
            culture = sp.prior if sp.prior not in ("dwarven", "elven", "orcish") else "heartland"
        old_name = st.name
        st.culture = culture
        st.name = self.s.namer.settlement(culture) if (not old_name or not rebuild or s.r.chance(0.65)) else old_name
        sp.names.append([st.name, s.year if year is None else year])
        sp.founded = s.year if year is None else year
        sp.ruined = None
        sp.rebuild = None
        sp.times += 1
        lo, hi = (120, 400) if sp.destiny in ("town", "city") else (25, 90)
        sp.pop = float(s.r.randint(lo, hi)) if sp.human else sp.cap * s.r.uniform(0.55, 0.8)
        sp.kind_now = self.kind_of(sp)
        st.population = int(sp.pop)
        if year is None or year >= s.year0:
            s.stat("founded")
        s.realms.found_settlement(sp, founder_realm, rebuild=rebuild, old_name=old_name, year=year, quiet=quiet)

    def founding_realm(self, sp: Spot):
        """The realm whose holdings are nearest (weighted by how near), or nobody: free settlers."""
        s = self.s
        options: dict[int, float] = {}
        for d, sid in sp.near:
            if d > self.reach:
                break
            other = self.spots[sid]
            if not other.standing:
                continue
            owner = s.faction(s.w.settlements[sid].owner)
            if owner is None:
                continue
            top = s.top(owner)
            if top is None or top.kind in ("tribe",) or not s.realms.can_found(top, sp):
                continue
            options[top.id] = options.get(top.id, 0.0) + 1.0 / (d + 6.0)
        if not options:
            return None
        ids = sorted(options)
        return s.w.factions[s.r.weighted(ids, [options[i] for i in ids])]

    # ------------------------------------------------------------------ endings
    def ruin(self, sp: Spot, cause: str, *, event: dict | None = None, kind: str = "razed", by=None,
             values: dict | None = None, importance: int = 3) -> dict:
        """A place is gone: razed, burned, abandoned. A fated place will be rebuilt; a doomed one becomes a ruin."""
        s = self.s
        st = s.w.settlements[sp.sid]
        if event is None:
            words = {"place": st.name, "cause": cause, "by": by.name if by is not None else "no one",
                     "what": self.words(sp.sid)}
            words.update(values or {})
            event = s.record(kind, words, importance=importance, places=[sp.sid], factions=[by] if by else [])
        event.setdefault("data", {})["ruined"] = int(sp.sid)
        sp.ruined = s.year
        sp.pop = 0.0
        st.population = 0
        holder = st.owner
        self.set_owner(sp.sid, -1, event)
        s.realms.place_lost(sp, holder, event)
        s.lore.place_lost(sp, event)
        s.ruins_info[sp.sid] = {"year": s.year, "cause": cause, "kind": kind, "event": event["id"],
                                "name": st.name, "was": self.words(sp.sid), "culture": st.culture,
                                "founded": sp.founded, "by": by.id if by is not None else -1,
                                "peak": max(int(s.peak.get(sp.sid, 0)), int(sp.pop))}
        if sp.fated:
            latest = s.present - 4
            if s.year + 4 <= latest:
                sp.rebuild = s.r.randint(s.year + 4, min(latest, s.year + 30))
            else:
                sp.rebuild = latest
        s.stat("ruined")
        return event

    def damage(self, sp: Spot, share: float) -> int:
        """People lost to a raid, a sack, a fire or a sickness. Returns how many."""
        lost = int(sp.pop * max(0.0, min(0.95, share)))
        sp.pop = max(10.0, sp.pop - lost)
        self.s.w.settlements[sp.sid].population = int(sp.pop)
        return lost

    # ------------------------------------------------------------------ plague and famine
    def troubles(self) -> None:
        s = self.s
        for sp in self.spots:
            if sp.standing and sp.pop > s.peak.get(sp.sid, 0):
                s.peak[sp.sid] = sp.pop
        if s.chance("great_plague"):
            self.pestilence(None)
        for realm in s.powers():
            if realm.kind == "tribe":
                continue
            if s.chance("plague"):
                self.pestilence(realm)
            if s.chance("famine"):
                self.famine(realm)

    def pestilence(self, realm) -> None:
        s = self.s
        great = realm is None
        if great:
            struck = self.standing()
        else:
            places = [self.spots[st.id] for st in s.holdings(realm, deep=True)]
            if not places:
                return
            start = s.r.weighted(places, [max(1.0, p.pop) for p in places])
            struck = [p for p in places if p is start or (math.hypot(p.x - start.x, p.y - start.y) < 16
                                                           and s.r.chance(0.6))]
        if not struck:
            return
        share = (0.15, 0.4) if great else (0.04, 0.2)
        deaths = sum(self.damage(p, s.r.uniform(*share)) for p in struck)
        homes = {S(p.sid) for p in struck}
        dead = []
        for hid in sorted(s.living):
            fig = s.w.figures[hid]
            if fig.kind == "person" and fig.home in homes and s.r.chance(0.12 if great else 0.06):
                dead.append(fig)
        first = max(struck, key=lambda p: p.pop)
        name = s.words.unique(s.data["names"]["plague"], place=s.place_name(first.sid), year=s.year) if great or \
            deaths > 1500 else ""
        e = s.record("great_plague" if great else "plague",
                     {"place": s.place_name(first.sid), "deaths": f"{round(deaths, -1 if deaths < 1000 else -2):,}",
                      "name": name or "the plague", "faction": realm.name if realm else ""},
                     importance=5 if great else 4 if name else 3, places=[p.sid for p in struck[:12]],
                     factions=[realm] if realm else [], data={"deaths": deaths, "name": name} if name else
                     {"deaths": deaths})
        s.stat("plague", deaths)
        for fig in dead:
            s.folk.die(fig, "plague", where=fig.home, cause_event=e)
        if great or name:
            s.orders.after_plague(e, first)

    def famine(self, realm) -> None:
        s = self.s
        places = [self.spots[st.id] for st in s.holdings(realm, deep=True)]
        if not places:
            return
        lost = sum(self.damage(p, s.r.uniform(0.02, 0.07)) for p in places)
        s.record("famine", {"faction": realm.name}, importance=3, factions=[realm], data={"deaths": lost})
        s.stat("famine", lost)
        for v in s.vassals(realm):
            s.realms.change_relation(v, realm, -s.r.uniform(2, 8))
