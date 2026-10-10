"""The politics engine (M6): the world moves on without you.

Rulers age, sicken and die, and are succeeded by their children, or by whoever can take the seat. Realms drift
closer or further apart; when neighbours hate each other enough they go to war over something, fight battles,
besiege and take each other's towns, and make peace when one side wins or both are spent. Vassals rebel. Plague
and famine come and go, tribes raid the borders, cults spread in secret and are sometimes rooted out, outlaw
gangs rise and are hanged.

The same engine runs in two modes:
- history (world creation, a year at a step): it tells what happened, and shapes today's grudges, but the map of
  today is already made, so conquests are only told where they agree with it;
- live (while you play, a week at a step): everything has consequences (towns change hands, prices rise, rulers
  die in their halls) and everything becomes news that travels (world/news.py).

Pure logic: no UI, no player. Everything random comes from the world's RNG.
"""

from __future__ import annotations

import math

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.world import factions as fx
from realmwalker.world import news

WAR_KINDS = ("kingdom", "free_city", "clan", "highland_clan", "elven_realm", "noble_house", "tribe")
DYNASTIC = ("kingdom", "noble_house", "clan", "highland_clan", "elven_realm")
SEAT_WORDS = {"kingdom": "throne", "noble_house": "lordship", "clan": "high seat", "highland_clan": "chiefship",
              "elven_realm": "throne", "free_city": "mayoralty"}
WEEK = 7.0
BEAST_REACH = 22  # how far (in tiles, walking) a beast of the old songs ranges from its lair to the farms


def year_of(world, tables) -> int:
    return tables.calendar.at(world.time).year


class Politics:
    def __init__(self, world, tables, rng: RNG, *, history: bool = False, year: int | None = None,
                 day: float | None = None) -> None:
        self.w = world
        self.t = tables
        self.data = tables.politics
        self.rng = rng
        self.history = history
        self.year = year if year is not None else year_of(world, tables)
        self.day = day if day is not None else news.now_days(world)
        self.changed = False  # holdings changed (territory must be redrawn)

    # ------------------------------------------------------------------ telling
    def say(self, kind: str, values: dict, *, where=None, importance: int = 2, factions=(), places=(),
            figures=()) -> str:
        words = {k: str(v) for k, v in values.items()}
        text = textgen.fill(self.rng.choice(self.data["text"][kind]), self.rng, {}, words)
        if not self.history and any(n["text"] == text and self.day - n["day"] < 90 for n in self.w.news[-60:]):
            return text
        x, y = where if where is not None else (self.w.width // 2, self.w.height // 2)
        facs = [f.id if hasattr(f, "id") else int(f) for f in factions]
        spots = [s.id if hasattr(s, "id") else int(s) for s in places]
        if self.history or importance >= 3:
            e = {"year": self.year, "kind": kind, "text": text, "factions": facs, "places": spots,
                 "figures": list(figures), "importance": importance}
            if not self.history and self.w.politics.get("deep_history"):
                e["id"] = int(self.w.politics.get("next_event", len(self.w.history)))  # the Legends book links it
                self.w.politics["next_event"] = e["id"] + 1
            self.w.history.append(e)
        if not self.history:
            news.add(self.w, text, x, y, kind=kind, importance=importance, factions=facs, places=spots, day=self.day)
        return text

    def place_of(self, f) -> tuple[int, int] | None:
        return news.faction_place(self.w, f)

    # ------------------------------------------------------------------ the step
    def advance(self, days: float) -> None:
        share = days / 365.0
        if not self.history:
            self.mortality(share)
            self.births(share)
            self.regrow(share)
        self.drift(share)
        self.declare_wars(share)
        self.fight_wars(days)
        self.pressures(share)
        if self.changed:
            fx.touch(self.w)

    # ------------------------------------------------------------------ rulers and heirs
    def annual_death_rate(self, fig) -> float:
        m = self.data["mortality"]
        span = float(self.data["lifespan"].get(fig.race, 1.0))
        eq = fig.age(self.year) / span
        rate = float(m["base"]) * 2 ** ((eq - float(m["from_age"])) / float(m["doubling_years"]))
        return min(0.9, rate)

    def mortality(self, share: float) -> None:
        w = self.w
        leaders = {f.leader: f for f in fx.active_factions(w)}
        for fig in list(w.figures.values()):
            # the heroes, exiles and others of note of a lived history (world/ages) grow old too
            if not fig.alive or fig.role not in ("ruler", "heir", "spouse", "member", "hero", "exile", "folk"):
                continue
            npc = w.npcs.get(fig.npc) if fig.npc >= 0 else None
            if npc is not None and npc.flags.get("companion"):
                continue  # walking with the player: their life is the party's now
            rate = self.annual_death_rate(fig)
            f = w.factions.get(fig.faction)
            if f is not None and f.seat >= 0 and w.settlements[f.seat].status.get("plague"):
                rate *= 3
            if fig.id in leaders and self.rng.chance(float(self.data["rates"]["assassination"]) * share):
                self.die(fig, self.cause("murder"), leaders.get(fig.id))
                continue
            if self.rng.chance(rate * share):
                self.die(fig, self.cause_for(fig), leaders.get(fig.id))

    def cause_for(self, fig) -> str:
        span = float(self.data["lifespan"].get(fig.race, 1.0))
        eq = fig.age(self.year) / span
        f = self.w.factions.get(fig.faction)
        if f is not None and f.seat >= 0 and self.w.settlements[f.seat].status.get("plague") and self.rng.chance(0.6):
            return self.cause("plague")
        if eq >= 62:
            return self.cause(self.rng.weighted(["old", "illness", "accident"], [6, 3, 1]))
        return self.cause(self.rng.weighted(["illness", "accident", "murder"], [5, 3, 1]))

    def cause(self, kind: str) -> str:
        return self.rng.choice(self.data["causes"][kind])

    def die(self, fig, cause: str, led=None) -> None:
        fig.died = self.year
        fig.cause = cause
        npc = self.w.npcs.get(fig.npc) if fig.npc >= 0 else None
        if npc is not None:
            npc.alive = False
            npc.present = False
        if led is not None and led.active:
            self.succeed(led, fig, cause)
        elif fig.role == "hero" and (fig.fame >= 3 or fig.kills):
            self.hero_died(fig, cause)

    def hero_died(self, fig, cause: str) -> None:
        """A hero of the lived history (world/ages) who had done something people sing of: their death is news."""
        home = fig.home
        if self.history or "hero_died" not in self.data["text"] or not home.startswith("S") or \
                not home[1:].isdigit() or int(home[1:]) >= len(self.w.settlements):
            return
        place = self.w.settlements[int(home[1:])]
        fig.died_at = home
        self.say("hero_died", {"hero": fig.full_name(), "cause": cause, "place": place.name},
                 where=(place.x, place.y), importance=3, places=[place], figures=[fig.id])

    def children(self, fig) -> list:
        kids = [f for f in self.w.figures.values() if f.parent == fig.id and f.alive]
        kids.sort(key=lambda k: (k.role != "heir", k.born))
        return kids

    def new_leader(self, f, *, family: str | None = None, age=(30, 62), role: str = "ruler"):
        fig = fx.make_figure(self.w, self.t, self.rng, f.culture, year=self.year, faction=f, role=role,
                             family=family, age=age)
        fig.title = fx.figure_title(self.t, f.kind, fig.sex)
        return fig

    def crown(self, f, fig) -> None:
        old = self.w.figures.get(f.leader)
        if old is not None and old.alive and old is not fig:
            old.role = "member"
        fig.role = "ruler"
        fig.faction = f.id
        fig.title = fx.figure_title(self.t, f.kind, fig.sex)
        f.leader = fig.id
        f.rulers.append(fig.id)
        if fig.id not in f.members:
            f.members.append(fig.id)

    def succeed(self, f, old, cause: str) -> None:
        w = self.w
        where = self.place_of(f)
        name = f.name
        if f.kind in DYNASTIC:
            kids = self.children(old)
            spouse = w.figures.get(old.spouse)
            if kids:
                heir = kids[0]
                relation = "their son" if heir.sex == "male" else "their daughter"
                self.crown(f, heir)
                for k in kids[1:2]:
                    k.role = "heir"
                self.say("succession", {"old": old.full_name(), "cause": cause, "new": heir.full_name(),
                                        "relation": relation, "seat": SEAT_WORDS.get(f.kind, "seat")},
                         where=where, importance=4 if f.kind == "kingdom" else 3, factions=[f])
                return
            if spouse is not None and spouse.alive and self.rng.chance(0.5):
                self.crown(f, spouse)
                self.say("succession", {"old": old.full_name(), "cause": cause, "new": spouse.full_name(),
                                        "relation": "their widow" if spouse.sex == "female" else "their widower",
                                        "seat": SEAT_WORDS.get(f.kind, "seat")},
                         where=where, importance=3, factions=[f])
                return
            if f.kind == "kingdom":
                houses = [v for v in fx.vassals(w, f) if v.kind == "noble_house" and fx.leader_of(w, v)]
                if houses:
                    strongest = max(houses, key=lambda h: h.military)
                    usurper = fx.leader_of(w, strongest)
                    self.crown(f, usurper)
                    f.flags["dynasty"] = strongest.flags.get("family", usurper.name.split()[-1])
                    f.flags["crisis"] = self.day
                    successor = self.children(usurper)
                    if successor:
                        strongest.leader = successor[0].id
                        successor[0].role = "ruler"
                        successor[0].title = fx.figure_title(self.t, "noble_house", successor[0].sex)
                        strongest.rulers.append(successor[0].id)
                    else:
                        self.crown(strongest, self.new_leader(strongest, family=strongest.flags.get("family")))
                        f.leader = usurper.id
                        usurper.faction = f.id
                    for v in houses:
                        if v is not strongest:
                            fx.change_relation(w, v.id, f.id, -self.rng.uniform(10, 35))
                    self.say("crisis", {"old": old.full_name(), "cause": cause, "new": usurper.full_name(),
                                        "house": strongest.name, "seat": "throne"},
                             where=where, importance=4, factions=[f, strongest])
                    return
            cousin = self.new_leader(f, family=old.name.split()[-1])
            self.crown(f, cousin)
            self.say("succession", {"old": old.full_name(), "cause": cause, "new": cousin.full_name(),
                                    "relation": "a cousin", "seat": SEAT_WORDS.get(f.kind, "seat")},
                     where=where, importance=3 if f.kind == "kingdom" else 2, factions=[f])
            return
        if f.kind in ("bandit_gang", "pirate_crew") and self.rng.chance(0.4):
            self.fall(f)
            self.say("gang_ended", {"old": old.full_name(), "cause": cause, "faction": name}, where=where,
                     importance=2, factions=[f])
            return
        new = self.new_leader(f)
        self.crown(f, new)
        self.say("elected", {"old": old.full_name(), "cause": cause, "new": new.full_name(), "faction": name},
                 where=where, importance=2 if not f.secret else 1, factions=[] if f.secret else [f])

    def births(self, share: float) -> None:
        w = self.w
        rate = float(self.data["birth_rate"])
        for f in fx.active_factions(w, *DYNASTIC):
            ruler = fx.leader_of(w, f)
            if ruler is None or not ruler.alive:
                continue
            spouse = w.figures.get(ruler.spouse)
            if spouse is None or not spouse.alive:
                continue
            span = float(self.data["lifespan"].get(ruler.race, 1.0))
            mother = ruler if ruler.sex == "female" else spouse
            if not 18 <= mother.age(self.year) / span <= 42:
                continue
            if self.rng.chance(rate * share):
                heirs = [k for k in self.children(ruler) if k.role == "heir"]
                child = fx.make_figure(w, self.t, self.rng, f.culture, year=self.year, faction=f,
                                       role="member" if heirs else "heir", family=ruler.name.split()[-1], age=(0, 0))
                child.parent = ruler.id
                child.race = ruler.race

    def regrow(self, share: float) -> None:
        rate = float(self.data["rates"]["military_regrowth"])
        for f in fx.active_factions(self.w):
            base = int(f.flags.setdefault("base_military", f.military))
            if f.military < base:
                f.military = min(base, int(round(f.military + base * rate * share + 0.5)))

    # ------------------------------------------------------------------ relations
    def powers(self) -> list:
        """Those who make war and peace for themselves."""
        return [f for f in fx.active_factions(self.w, *WAR_KINDS) if f.liege < 0 and f.leader in self.w.figures]

    def distance(self, a, b) -> float:
        pa, pb = self.place_of(a), self.place_of(b)
        if pa is None or pb is None:
            return 10**6
        return math.hypot(pa[0] - pb[0], pa[1] - pb[1])

    def drift(self, share: float) -> None:
        sigma = float(self.data["rates"]["relation_drift"]) * math.sqrt(max(share, 1e-6))
        powers = self.powers()
        for i, a in enumerate(powers):
            for b in powers[i + 1:]:
                r = fx.relation(self.w, a.id, b.id)
                pull = -r * 0.02 * share  # old feelings fade, slowly
                fx.set_relation(self.w, a.id, b.id, r + self.rng.gauss(0, sigma) + pull)
        # Marriages and treaties bind friendly realms closer.
        for i, a in enumerate(powers):
            for b in powers[i + 1:]:
                r = fx.relation(self.w, a.id, b.id)
                if a.kind in DYNASTIC and b.kind in DYNASTIC and r >= 20 and \
                        self.rng.chance(float(self.data["rates"]["marriage"]) * share):
                    fx.change_relation(self.w, a.id, b.id, 15)
                    self.say("marriage", {"a": a.name, "b": b.name}, where=self.place_of(a), importance=2,
                             factions=[a, b])
                elif r >= 50 and self.rng.chance(float(self.data["rates"]["treaty"]) * share):
                    fx.change_relation(self.w, a.id, b.id, 10)
                    self.say("treaty", {"a": a.name, "b": b.name}, where=self.place_of(a), importance=2,
                             factions=[a, b])

    # ------------------------------------------------------------------ war
    def at_war(self, a, b) -> bool:
        return any(w_["active"] and {w_["attacker"], w_["defender"]} == {a.id, b.id} for w_ in self.w.wars)

    def wars_of(self, f) -> list:
        return [w_ for w_ in self.w.wars if w_["active"] and f.id in (w_["attacker"], w_["defender"])]

    def strength(self, f) -> float:
        total = float(f.military)
        for v in fx.vassals(self.w, f):
            total += v.military * 0.8
        return max(1.0, total)

    def declare_wars(self, share: float) -> None:
        rates = self.data["rates"]
        powers = self.powers()
        for i, a in enumerate(powers):
            for b in powers[i + 1:]:
                if a.kind == "tribe" and b.kind == "tribe":
                    continue
                if a.culture == b.culture and a.culture in ("elven", "dwarven"):
                    continue  # the old peoples do not make war on their own kind
                if self.at_war(a, b) or self.distance(a, b) > 75:
                    continue
                until = a.flags.get("peace_until", {}).get(str(b.id))
                if until is not None and until > self.day:
                    continue
                r = fx.relation(self.w, a.id, b.id)
                if r > -25:
                    continue
                p = float(rates["war_base"]) * (0.5 if r > -40 else 1.0) + max(0, -r - 40) * float(rates["war_hostility"])
                if any(v in ("expansionist", "warlike") for v in a.values + b.values):
                    p *= 1.5
                if "tribe" in (a.kind, b.kind):
                    p *= 0.3  # the tribes mostly raid; open war with them is rarer
                if self.rng.chance(p * share):
                    attacker, defender = (a, b) if self.eagerness(a) >= self.eagerness(b) else (b, a)
                    self.start_war(attacker, defender, self.reason(attacker, defender))
        # Vassals who hate their lords rise against them.
        for v in fx.active_factions(self.w, "noble_house", "highland_clan", "clan"):
            if v.liege < 0 or v.flags.get("minor"):
                continue
            liege = self.w.factions.get(v.liege)
            if liege is None or not liege.active or self.at_war(v, liege):
                continue
            if fx.relation(self.w, v.id, liege.id) <= -30 and \
                    self.rng.chance(float(rates["rebellion"]) * share * 3):
                self.start_war(v, liege, "rebellion")

    def eagerness(self, f) -> float:
        return self.strength(f) * (1.5 if "expansionist" in f.values or "warlike" in f.values else 1.0)

    def reason(self, a, b) -> str:
        if a.kind == "tribe" or b.kind == "tribe":
            return "raids"
        if a.faith != b.faith and ("pious" in a.values or "pious" in b.values):
            return "religion"
        if b.flags.get("crisis", -10**9) > self.day - (365 if not self.history else 20 * 365):
            return "succession"
        if "mercantile" in a.values and "mercantile" in b.values:
            return "trade"
        if any(w_["attacker"] in (a.id, b.id) and w_["defender"] in (a.id, b.id) for w_ in self.w.wars):
            return "revenge"
        return self.rng.choice(["border", "border", "conquest"])

    def start_war(self, attacker, defender, reason: str) -> dict:
        war = {"id": int(self.w.politics.get("next_war", 0)), "attacker": attacker.id, "defender": defender.id,
               "reason": reason, "started": self.day, "year": self.year, "ended": None, "active": True, "score": 0.0,
               "battles": 0, "siege": None, "result": ""}
        self.w.politics["next_war"] = war["id"] + 1
        self.w.wars.append(war)
        fx.change_relation(self.w, attacker.id, defender.id, -20)
        where = self.place_of(defender)
        if reason == "rebellion":
            self.say("rebellion", {"rebel": attacker.name, "liege": defender.name}, where=where, importance=4,
                     factions=[attacker, defender])
        else:
            words = self.data["war_reasons"].get(reason, reason)
            big = "kingdom" in (attacker.kind, defender.kind) and "tribe" not in (attacker.kind, defender.kind)
            self.say("war", {"attacker": attacker.name, "defender": defender.name, "reason": words}, where=where,
                     importance=5 if big else 3 if "tribe" in (attacker.kind, defender.kind) else 4,
                     factions=[attacker, defender])
        return war

    def front(self, war: dict, attacking) -> object | None:
        """The loser's settlement nearest the winner: where the fighting is."""
        w = self.w
        a = w.factions[war["attacker"]]
        d = w.factions[war["defender"]]
        side, other = (d, a) if attacking else (a, d)
        targets = fx.holdings(w, side, deep=True)
        if not targets:
            return None
        origin = self.place_of(other)
        if origin is None:
            return targets[0]
        return min(targets, key=lambda s: (s.x - origin[0]) ** 2 + (s.y - origin[1]) ** 2)

    def fight_wars(self, days: float) -> None:
        rates = self.data["rates"]
        for war in [w_ for w_ in self.w.wars if w_["active"]]:
            a = self.w.factions.get(war["attacker"])
            d = self.w.factions.get(war["defender"])
            if a is None or d is None or not a.active or not d.active:
                self.end_war(war, None)
                continue
            expected = float(rates["war_battles_per_month"]) * days / 30.0
            n = int(expected) + (1 if self.rng.random() < expected - int(expected) else 0)
            for _ in range(n):
                self.battle(war, a, d)
                if not war["active"]:
                    break
            if war["active"]:
                self.sieges(war, a, d, days)
            if war["active"]:
                age = (self.day - war["started"]) / 365.0
                spent = a.military < 0.35 * a.flags.get("base_military", a.military + 1) and \
                    d.military < 0.35 * d.flags.get("base_military", d.military + 1)
                if abs(war["score"]) >= 60 or spent or (age >= float(rates["peace_after_years"]) and
                                                          self.rng.chance(min(1.0, 0.5 * days / 365.0 + 0.02))):
                    winner = a if war["score"] >= 40 else d if war["score"] <= -40 else None
                    self.end_war(war, winner)

    def battle(self, war: dict, a, d) -> None:
        sa = self.strength(a) * self.rng.uniform(0.6, 1.4)
        sd = self.strength(d) * self.rng.uniform(0.6, 1.4) * 1.1
        attacker_wins = self.rng.random() < sa / (sa + sd)
        winner, loser = (a, d) if attacker_wins else (d, a)
        loser.military = max(1, int(loser.military * self.rng.uniform(0.82, 0.94)))
        winner.military = max(1, int(winner.military * self.rng.uniform(0.94, 0.99)))
        swing = self.rng.uniform(8, 18)
        war["score"] = max(-100.0, min(100.0, war["score"] + (swing if attacker_wins else -swing)))
        war["battles"] += 1
        place = self.front(war, attacking=attacker_wins)
        if place is None:
            return
        if self.history and self.rng.chance(0.7):
            return  # not every skirmish makes the chronicle
        big = self.rng.chance(0.3)
        self.say("battle", {"winner": winner.name, "loser": loser.name, "place": place.name},
                 where=(place.x, place.y), importance=3 if big else 2, factions=[winner, loser], places=[place])

    def sieges(self, war: dict, a, d, days: float) -> None:
        w = self.w
        siege = war.get("siege")
        if siege is None:
            if abs(war["score"]) < 30:
                return
            attacking = war["score"] > 0
            besieger = a if attacking else d
            target = self.front(war, attacking=attacking)
            if target is None:
                return
            owner_top = fx.realm_of_settlement(w, target)
            if owner_top is not None and owner_top.seat == target.id and abs(war["score"]) < 70:
                return  # the capital holds until the war is nearly lost
            if self.history:
                self.tell_conquest(war, besieger, a if besieger is d else d)
                war["score"] *= 0.7
                return
            war["siege"] = {"settlement": target.id, "by": besieger.id, "since": self.day,
                            "until": self.day + self.rng.uniform(14, 60)}
            target.status["siege"] = {"war": war["id"], "by": besieger.id, "since": self.day}
            self.say("siege", {"attacker": besieger.name, "place": target.name}, where=(target.x, target.y),
                     importance=3, factions=[besieger], places=[target])
            return
        if self.day < siege["until"]:
            return
        target = w.settlements[siege["settlement"]]
        besieger = w.factions.get(siege["by"])
        target.status.pop("siege", None)
        war["siege"] = None
        if besieger is None or not besieger.active:
            return
        defender = fx.realm_of_settlement(w, target)
        local = (defender.military if defender is not None else 10) * 0.35 * (1.6 if target.walled else 1.0)
        power = self.strength(besieger) * self.rng.uniform(0.5, 1.3)
        if self.rng.random() < power / (power + local):
            self.take(target, besieger, defender, war)
        else:
            if besieger.id == war["attacker"]:
                war["score"] -= 10
            else:
                war["score"] += 10
            self.say("relieved", {"place": target.name, "attacker": besieger.name,
                                  "defender": defender.name if defender else "the townsfolk"},
                     where=(target.x, target.y), importance=3, factions=[besieger], places=[target])

    def take(self, target, winner, loser, war: dict) -> None:
        """A settlement changes hands. Its lord's house swears to the conqueror, or the crown takes it."""
        w = self.w
        old_owner = fx.owner_of(w, target)
        sacked = self.rng.chance(0.35)
        if old_owner is not None and old_owner.seat == target.id and old_owner.kind == "noble_house":
            old_owner.liege = winner.id
            fx.set_relation(w, old_owner.id, winner.id, 10)
        elif old_owner is not None and old_owner.seat == target.id and old_owner is loser:
            # A realm's own seat falls: the seat moves, or the realm is no more.
            rest = [s for s in fx.holdings(w, loser) if s.id != target.id]
            self.set_owner(target, winner.id)
            if rest:
                loser.seat = max(rest, key=lambda s: s.population).id
            else:
                self.fall(loser)
                for v in fx.vassals(w, loser):
                    v.liege = winner.id
        else:
            self.set_owner(target, winner.id)
        if sacked:
            target.population = max(10, int(target.population * self.rng.uniform(0.55, 0.8)))
            target.status["sacked"] = self.day
        war["score"] += 15 if winner.id == war["attacker"] else -15
        self.changed = True
        kind = "sacked" if sacked else "taken"
        self.say(kind, {"attacker": winner.name, "defender": loser.name if loser else "its lord", "place": target.name},
                 where=(target.x, target.y), importance=4, factions=[winner] + ([loser] if loser else []),
                 places=[target])

    def tell_conquest(self, war: dict, winner, loser) -> None:
        """History: a town the winner holds today was taken from the loser in this war."""
        w = self.w
        origin = self.place_of(loser)
        mine = [s for s in fx.holdings(w, winner, deep=True) if s.id != winner.seat]
        if not mine or origin is None:
            return
        target = min(mine, key=lambda s: (s.x - origin[0]) ** 2 + (s.y - origin[1]) ** 2)
        if target.id in w.politics.setdefault("told_conquests", []):
            return
        w.politics["told_conquests"].append(target.id)
        self.say("taken", {"attacker": winner.name, "defender": loser.name, "place": target.name},
                 where=(target.x, target.y), importance=4, factions=[winner, loser], places=[target])

    def end_war(self, war: dict, winner) -> None:
        w = self.w
        war["active"] = False
        war["ended"] = self.day
        war["end_year"] = self.year
        if war.get("siege"):
            s = w.settlements[war["siege"]["settlement"]]
            s.status.pop("siege", None)
            war["siege"] = None
        a = w.factions.get(war["attacker"])
        d = w.factions.get(war["defender"])
        if a is None or d is None:
            return
        war["result"] = "attacker" if winner is a else "defender" if winner is d else "draw"
        grudge = -35 if winner is not None else -20
        fx.set_relation(w, a.id, d.id, grudge + self.rng.uniform(-10, 10))
        until = self.day + 365 * self.rng.uniform(3, 8)
        a.flags.setdefault("peace_until", {})[str(d.id)] = until
        d.flags.setdefault("peace_until", {})[str(a.id)] = until
        where = self.place_of(d)
        if war["reason"] == "rebellion":
            if winner is a and not self.history:
                a.liege = -1
                self.changed = True
                self.say("freedom", {"rebel": a.name, "liege": d.name}, where=where, importance=4, factions=[a, d])
            else:
                leader = fx.leader_of(w, a)
                if leader is not None and leader.alive and not self.history:
                    self.die(leader, "on the headsman's block", a)
                fx.set_relation(w, a.id, d.id, 10)
                self.say("crushed", {"rebel": a.name, "liege": d.name}, where=where, importance=3, factions=[a, d])
            return
        terms = f", {winner.name} the victor" if winner is not None else ", with nothing settled"
        self.say("peace", {"a": a.name, "b": d.name, "terms": terms}, where=where, importance=4, factions=[a, d])
        # Beaten soldiers without pay take to the roads.
        if not self.history and self.rng.chance(0.5):
            self.new_gang(near=where)

    def set_owner(self, settlement, fid: int) -> None:
        """A place changes hands: in the history's ledger of who held what too (worlds that lived their ages)."""
        if settlement.owner == fid:
            return
        settlement.owner = fid
        if self.history or not self.w.politics.get("deep_history"):
            return
        from realmwalker.world.history import remember

        holder = self.w.factions.get(fid)
        text = textgen.fill(self.rng.choice(self.t.history["text"]["came_under"]), self.rng, {},
                            {"place": settlement.name, "holder": holder.name if holder is not None else "no lord"})
        remember(self.w, self.year, "came_under", text, importance=1, places=[settlement.id],
                 factions=[fid] if holder is not None else [], data={"owners": [[settlement.id, int(fid)]]})

    def fall(self, f) -> None:
        f.fallen = self.year
        for s in self.w.settlements:
            if s.owner == f.id:
                self.set_owner(s, f.liege if f.liege >= 0 else -1)
        for site in self.w.sites:
            if site.faction == f.id:
                site.faction = -1
        self.changed = True

    # ------------------------------------------------------------------ plague, famine, raids, cults, outlaws
    def pressures(self, share: float) -> None:
        rates = self.data["rates"]
        w = self.w
        for realm in self.powers():
            if realm.kind == "tribe":
                continue
            if self.rng.chance(float(rates["plague"]) * share):
                self.plague(realm)
            if self.rng.chance(float(rates["famine"]) * share):
                self.famine(realm)
        for tribe in fx.active_factions(w, "tribe"):
            if self.rng.chance(float(rates["tribe_raid"]) * share):
                self.raid(tribe)
        for cult in fx.active_factions(w, "cult"):
            self.cult_year(cult, share)
        if not self.history:
            for d in w.politics.get("dragons", []):
                if d.get("alive") and self.rng.chance(float(rates["dragon"]) * share * 12):
                    self.dragon_wakes(d)
            for key, hid in list(w.politics.get("lairs", {}).items()):
                fig = w.figures.get(hid)
                if fig is not None and fig.alive and fig.kind == "beast" and \
                        self.rng.chance(float(rates.get("beast_attack", 0.0)) * share):
                    self.beast_comes(fig, int(key))
        if not self.history:
            for gang in fx.active_factions(w, "bandit_gang"):
                if self.rng.chance(float(rates["gang_destroyed"]) * share):
                    self.hang_gang(gang)
            if self.rng.chance(float(rates["gang_new"]) * share):
                self.new_gang()
        if not self.history:
            self.expire_status()

    def beast_comes(self, fig, site_id: int) -> None:
        """A beast of the old songs (world/ages) comes down from its lair on the farms nearest it."""
        w = self.w
        if not 0 <= site_id < len(w.sites):
            return
        lair = w.sites[site_id]
        near = [s for s in w.settlements if abs(s.x - lair.x) + abs(s.y - lair.y) <= BEAST_REACH
                and s.kind in ("hamlet", "village", "town")]
        if not near:
            return
        s = self.rng.choice(near)
        lost = max(1, int(s.population * self.rng.uniform(0.005, 0.03)))
        s.population = max(10, s.population - lost)
        s.status["beast"] = {"until": self.day + 30, "since": self.day, "by": fig.name}
        fig.fame += 1
        realm = fx.realm_of_settlement(w, s)
        dead = "one person" if lost == 1 else f"{lost} people"
        self.say("beast_attack", {"beast": f"{fig.name} {fig.epithet}".strip(), "place": s.name, "dead": dead},
                 where=(s.x, s.y), importance=3, factions=[realm] if realm else [], places=[s], figures=[fig.id])

    def dragon_wakes(self, d: dict) -> None:
        """A dragon comes down from its lair: a village burns, or buys its life with cattle and silver."""
        w = self.w
        if not 0 <= d.get("lair", -1) < len(w.sites):
            return
        lair = w.sites[d["lair"]]
        near = [s for s in w.settlements if abs(s.x - lair.x) + abs(s.y - lair.y) <= 14]
        if not near:
            return
        s = self.rng.choice(near)
        d["last_seen"] = self.year
        realm = fx.realm_of_settlement(w, s)
        if self.rng.chance(0.45):
            s.status["burned"] = self.day
            s.population = max(10, int(s.population * self.rng.uniform(0.5, 0.8)))
            self.say("dragon", {"dragon": d["name"], "place": s.name}, where=(s.x, s.y), importance=4,
                     factions=[realm] if realm else [], places=[s])
        else:
            s.status["tribute"] = d["name"]
            self.say("dragon_tribute", {"dragon": d["name"], "place": s.name}, where=(s.x, s.y), importance=3,
                     factions=[realm] if realm else [], places=[s])
        self.changed = True

    def expire_status(self) -> None:
        for s in self.w.settlements:
            for key in ("plague", "famine", "raided", "beast"):
                v = s.status.get(key)
                if isinstance(v, dict) and v.get("until", 0) < self.day:
                    del s.status[key]
            if s.status.get("sacked", self.day) < self.day - 120:
                del s.status["sacked"]
            if s.status.get("burned", self.day) < self.day - 365:
                del s.status["burned"]

    def plague(self, realm) -> None:
        w = self.w
        towns = fx.holdings(w, realm, deep=True)
        if not towns:
            return
        start = self.rng.weighted(towns, [max(1, s.population) for s in towns])
        struck = [start] + [s for s in towns if s is not start and math.hypot(s.x - start.x, s.y - start.y) < 15
                            and self.rng.chance(0.5)]
        deaths = 0
        for s in struck:
            lost = int(s.population * self.rng.uniform(0.04, 0.18))
            deaths += lost
            if not self.history:
                s.population = max(10, s.population - lost)
                s.status["plague"] = {"until": self.day + self.rng.uniform(45, 120), "since": self.day}
        self.say("plague", {"place": start.name, "deaths": f"{round(deaths, -1 if deaths < 1000 else -2):,}"},
                 where=(start.x, start.y), importance=4, factions=[realm], places=struck)

    def famine(self, realm) -> None:
        if self.history and self.rng.chance(0.6):
            return
        if not self.history:
            for s in fx.holdings(self.w, realm, deep=True):
                s.status["famine"] = {"until": self.day + self.rng.uniform(90, 200), "since": self.day}
        self.say("famine", {"faction": realm.name}, where=self.place_of(realm), importance=3, factions=[realm])

    def raid(self, tribe) -> None:
        w = self.w
        home = self.place_of(tribe)
        if home is None:
            return
        targets = [s for s in w.settlements if s.kind in ("hamlet", "village") and
                   math.hypot(s.x - home[0], s.y - home[1]) < 28 and fx.owner_of(w, s) is not None]
        if not targets:
            return
        s = self.rng.choice(targets)
        burned = s.kind == "hamlet" and self.rng.chance(0.3)
        if not self.history:
            s.population = max(10, int(s.population * (0.5 if burned else self.rng.uniform(0.85, 0.95))))
            s.status["raided"] = {"until": self.day + 30, "since": self.day, "by": tribe.id}
            if burned:
                s.status["burned"] = self.day
        realm = fx.realm_of_settlement(w, s)
        if realm is not None:
            fx.change_relation(w, tribe.id, realm.id, -8)
        if self.history and self.rng.chance(0.85):
            return
        self.say("burned" if burned else "raid", {"tribe": tribe.name, "place": s.name}, where=(s.x, s.y),
                 importance=3 if burned else 2, factions=[tribe] + ([realm] if realm else []), places=[s])

    def cult_year(self, cult, share: float) -> None:
        w = self.w
        rates = self.data["rates"]
        god = self.t.factions["faiths"].get(cult.faith, {}).get("god", "a nameless god")
        towns = [w.settlements[i] for i in cult.presence if 0 <= i < len(w.settlements)]
        if self.history:
            return
        if self.rng.chance(float(rates["cult_spread"]) * share) and towns:
            near = [s for s in w.settlements if s.id not in cult.presence and s.kind in ("village", "town", "city")
                    and min(math.hypot(s.x - t.x, s.y - t.y) for t in towns) < 30]
            if near:
                cult.presence.append(self.rng.choice(near).id)
                cult.military += self.rng.randint(2, 8)
        if towns and self.rng.chance(float(rates["cult_incident"]) * share):
            s = self.rng.choice(towns)
            self.say("cult_incident", {"place": s.name}, where=(s.x, s.y), importance=1, places=[s])
        if towns and self.rng.chance(float(rates["cult_purge"]) * share):
            s = self.rng.choice(towns)
            church = fx.church_of(w, fx.faith_for_culture(self.t, s.culture))
            if church is None:
                return
            cult.presence = [i for i in cult.presence if i != s.id]
            cult.military = max(1, int(cult.military * 0.7))
            self.say("cult_purged", {"church": church.name, "cult": cult.name, "place": s.name}, where=(s.x, s.y),
                     importance=2, factions=[church, cult], places=[s])
            if not cult.presence and cult.military < 8:
                self.fall(cult)

    def hang_gang(self, gang) -> None:
        w = self.w
        where = self.place_of(gang)
        lord = fx.lord_at(w, *where) if where is not None else None
        if lord is None or lord.kind == "tribe":
            return
        self.fall(gang)
        leader = fx.leader_of(w, gang)
        if leader is not None and leader.alive:
            leader.died = self.year
            leader.cause = "on the gallows"
        self.say("gang_destroyed", {"lord": fx.top_liege(w, lord).name, "gang": gang.name}, where=where, importance=2,
                 factions=[gang, lord])

    def new_gang(self, near=None) -> None:
        """Outlaws take to the roads: often deserters after a war."""
        w = self.w
        lairs = [s for s in w.sites if s.faction < 0 and s.kind in ("ruin", "cave", "tower")]
        if near is not None:
            lairs = [s for s in lairs if math.hypot(s.x - near[0], s.y - near[1]) < 40] or lairs
        lairs = [s for s in lairs if w.road[max(0, s.x - 8):s.x + 9, max(0, s.y - 8):s.y + 9].any()]
        if not lairs:
            return
        site = self.rng.choice(lairs)
        human = [s for s in w.settlements if s.kind in fx.HUMAN_SETTLEMENTS]
        home = min(human, key=lambda s: (s.x - site.x) ** 2 + (s.y - site.y) ** 2) if human else None
        culture = home.culture if home is not None and home.culture != "halfling" else "heartland"
        fid = max(w.factions, default=-1) + 1
        area = w.area_at(site.x, site.y)
        gang = fx.Faction(id=fid, name="", kind="bandit_gang", culture=culture, site=site.id,
                          area=area.id if area else -1, faith=fx.faith_for_culture(self.t, culture),
                          values=["cruel", "mercantile"], founded=self.year, wealth=self.rng.randint(10, 80),
                          military=self.rng.randint(8, 25), secret=False)
        gang.flags["range"] = 16
        w.factions[fid] = gang
        leader = self.new_leader(gang, age=(20, 45))
        leader.epithet = self.rng.choice(self.t.factions["words"]["epithet"])
        self.crown(gang, leader)
        land = area.name if area is not None else site.name
        used = {f.name for f in w.factions.values()}
        for _ in range(10):
            gang.name = textgen.fill(self.rng.choice(self.t.factions["kinds"]["bandit_gang"]["names"]), self.rng,
                                     self.t.factions["words"], {"leader": leader.first_name, "land": land})
            gang.name = gang.name[:1].lower() + gang.name[1:] if gang.name.startswith("The ") else gang.name
            if gang.name not in used:
                break
        site.faction = fid
        for other in fx.active_factions(w):
            if other.id == fid:
                continue
            group = self.t.factions["kinds"][other.kind]["group"]
            v = -55 if group == "realms" else -25 if group == "guilds" and other.kind != "thieves_guild" else \
                20 if other.kind == "thieves_guild" else 0
            if v:
                fx.set_relation(w, fid, other.id, v + self.rng.gauss(0, 8))
        self.say("gang_new", {"gang": gang.name, "place": land}, where=(site.x, site.y), importance=2,
                 factions=[gang])


# ---------------------------------------------------------------------------- the live world
def tick(world, tables, *, force: bool = False) -> bool:
    """Called as time passes: a week of politics for every week gone by. True if anything ran."""
    today = news.now_days(world)
    last = world.politics.get("last_tick")
    if last is None:
        world.politics["last_tick"] = today
        return False
    ran = False
    steps = 0
    while today - last >= WEEK or force:
        force = False
        last += WEEK
        rng = world.rng.child(f"politics/{int(last)}")
        Politics(world, tables, rng, day=last, year=tables.calendar.at(int(last * 1440)).year).advance(WEEK)
        ran = True
        steps += 1
        if steps > 520:  # ten years at most in one go (a very long jail term, say)
            last = today
            break
    world.politics["last_tick"] = last
    return ran


def at_war(world, fid: int) -> bool:
    f = world.factions.get(fid)
    top = fx.top_liege(world, f) if f is not None else None
    ids = {fid} | ({top.id} if top is not None else set())
    return any(w_["active"] and (w_["attacker"] in ids or w_["defender"] in ids) for w_ in world.wars)


def war_near(world, x: int, y: int, radius: float = 25.0) -> bool:
    """Is there a war in the lands around here (for refugees, deserters and prices)?"""
    if not world.wars:
        return False
    for s in world.settlements:
        if abs(s.x - x) > radius or abs(s.y - y) > radius:
            continue
        realm = fx.realm_of_settlement(world, s)
        if realm is not None and at_war(world, realm.id):
            return True
    return False
