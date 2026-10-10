"""War in the ages: why neighbours fight, who fights beside them, and what it costs.

Every war has a cause (a border, a claim, the true faith, old wrongs, raids, a rebellion) and a name. Each year of it
brings battles at real places, fought by named commanders and their knights; the dead are remembered, and so are
the ones who killed them. A war that goes well brings sieges: a town is taken (its lord may bend the knee or be put
out), sacked, or razed to the ground. Wars end in victory, exhaustion or a treaty, and leave grudges, veterans
looking for pay, and deserters on the roads. As in Dwarf Fortress, defenders usually hold, and a conquest matters.
"""

from __future__ import annotations

import math

from realmwalker.world import factions as fx
from realmwalker.world.ages.sim import S


LEVY = 3.0


def dead_text(n: int) -> str:
    return "a handful" if n < 5 else f"{n:,}"


class War:
    def __init__(self, sim) -> None:
        self.s = sim
        self.data = sim.data["war"]
        self.version = -1
        self._fighting: set[int] = set()
        self.peace: dict[tuple[int, int], int] = {}  # (a, b) -> no war again before this year
        self.captives: list[dict] = []
        self.past: dict[tuple[int, int], dict] = {}  # (a, b) -> the last war between them

    # ------------------------------------------------------------------ who is fighting
    def active_wars(self) -> list[dict]:
        return [w for w in self.s.w.wars if w.get("active")]

    def sides(self, war: dict) -> tuple[set[int], set[int]]:
        allies = war.get("allies", {})
        return ({war["attacker"], *allies.get("attacker", [])}, {war["defender"], *allies.get("defender", [])})

    def fighting(self) -> set[int]:
        key = (len(self.s.w.wars), sum(1 for w in self.s.w.wars if w.get("active")), self.s.version)
        if key != self.version:
            out: set[int] = set()
            for war in self.active_wars():
                a, d = self.sides(war)
                out |= a | d
            self._fighting = out
            self.version = key
        return self._fighting

    def at_war(self, fid: int) -> bool:
        if fid in self.fighting():
            return True
        f = self.s.w.factions.get(fid)
        top = self.s.top(f) if f is not None else None
        return top is not None and top.id in self._fighting

    def at_war_with(self, a, b) -> bool:
        for war in self.active_wars():
            sa, sd = self.sides(war)
            if (a.id in sa and b.id in sd) or (a.id in sd and b.id in sa):
                return True
        return False

    def wars_of(self, f) -> list[dict]:
        return [w for w in self.active_wars() if f.id in (w["attacker"], w["defender"])]

    def strength(self, f) -> float:
        total = float(f.military)
        for v in self.s.vassals(f):
            total += v.military * 0.8
        return max(1.0, total)

    def side_strength(self, war: dict, attacker: bool) -> float:
        main = self.s.w.factions[war["attacker" if attacker else "defender"]]
        total = self.strength(main)
        for fid in war.get("allies", {}).get("attacker" if attacker else "defender", []):
            ally = self.s.faction(fid)
            if ally is not None:
                total += self.strength(ally) * 0.5
        return total

    # ------------------------------------------------------------------ the year
    def year(self) -> None:
        self.declare()
        for war in self.active_wars():
            self.campaign(war)
        self.prisoners()

    def declare(self) -> None:
        s = self.s
        r = s.r
        powers = s.powers()
        anchors = {f.id: s.anchor(f) for f in powers}
        reach = float(self.data["reach"])
        for i, a in enumerate(powers):
            for b in powers[i + 1:]:
                if a.kind == "tribe" and b.kind == "tribe":
                    continue
                if a.culture == b.culture and a.culture in ("elven", "dwarven"):
                    continue  # the old peoples do not make war on their own kind
                pa, pb = anchors[a.id], anchors[b.id]
                if pa is None or pb is None or math.hypot(pa[0] - pb[0], pa[1] - pb[1]) > reach:
                    continue
                if self.peace.get((min(a.id, b.id), max(a.id, b.id)), -10**9) > s.year:
                    continue
                if len(self.wars_of(a)) >= 2 or len(self.wars_of(b)) >= 2 or self.at_war_with(a, b):
                    continue
                rel = fx.relation(s.w, a.id, b.id)
                if rel > -20:
                    continue
                p = float(self.data["base"]) + max(0.0, -rel - 30) * float(self.data["hostility"])
                if any(v in ("expansionist", "warlike") for v in a.values + b.values):
                    p *= 1.5
                if "tribe" in (a.kind, b.kind):
                    p *= 0.4
                if r.chance(p):
                    attacker, defender = (a, b) if self.eagerness(a) >= self.eagerness(b) else (b, a)
                    self.start(attacker, defender, self.reason(attacker, defender))

    def eagerness(self, f) -> float:
        return self.strength(f) * (1.5 if "expansionist" in f.values or "warlike" in f.values else 1.0) * \
            self.s.r.uniform(0.7, 1.3)

    def reason(self, a, b) -> str:
        s = self.s
        if a.kind == "tribe" or b.kind == "tribe":
            return "raids"
        if b.flags.get("crisis", -10**6) >= s.year - 20:
            return "succession"
        last = self.past.get((min(a.id, b.id), max(a.id, b.id)))
        if last is not None and last.get("end_year", -10**6) >= s.year - 80 and last.get("result") != "draw" and \
                s.r.chance(0.6):
            return "revenge"
        human = {"heartland", "northmarch", "southron", "halfling"}
        if a.culture in human and b.culture in human and a.faith != b.faith and \
                ("pious" in a.values or "pious" in b.values) and s.r.chance(0.35):
            return "religion"
        if "mercantile" in a.values and "mercantile" in b.values:
            return "trade"
        return s.r.choice(["border", "border", "conquest"])

    def start(self, attacker, defender, reason: str, *, claimant=None) -> dict:
        s = self.s
        w = s.w
        here = s.anchor(defender) or (w.width // 2, w.height // 2)
        near = s.land.nearest_standing(here[0], here[1], 30)
        place = s.place_name(near[0][1]) if near else (s.area_name(*here) or "the border")
        name = s.words.war_name(reason, attacker, defender, place)
        cal = s.t.calendar
        day = (s.year - cal.start_year) * cal.days_per_year + s.r.uniform(0, cal.days_per_year - 1)
        war = {"id": int(w.politics.get("next_war", 0)), "name": name, "attacker": attacker.id,
               "defender": defender.id, "reason": reason, "started": day, "year": s.year, "ended": None,
               "end_year": None, "active": True, "score": 0.0, "battles": 0, "siege": None, "result": "",
               "dead": 0, "allies": {"attacker": [], "defender": []},
               "claimant": claimant.id if claimant is not None else -1, "taken": []}
        w.politics["next_war"] = war["id"] + 1
        w.wars.append(war)
        self.version = -1
        self.s.realms.change_relation(attacker, defender, -20)
        if attacker.liege == defender.id:
            attacker.liege = -1  # rebels renounce their fealty; if they are crushed it is forced on them again
            s.touch()
        if reason == "rebellion":
            s.record("rebellion", {"rebel": attacker.name, "liege": defender.name, "war": name}, importance=4,
                     factions=[attacker, defender], war=war)
        else:
            words = s.t.politics["war_reasons"].get(reason, reason)
            crowns = attacker.kind in ("kingdom", "elven_realm", "clan") and defender.kind in ("kingdom", "elven_realm",
                                                                                            "clan")
            s.record("war_named", {"attacker": attacker.name, "defender": defender.name, "reason": words,
                                   "war": name}, importance=4 if crowns else 3, factions=[attacker, defender], war=war)
        self.call_allies(war, attacker, defender)
        s.stat("wars")
        return war

    def call_allies(self, war: dict, attacker, defender) -> None:
        s = self.s
        for side, friend, foe in (("attacker", attacker, defender), ("defender", defender, attacker)):
            for c in s.powers():
                if c.id in (attacker.id, defender.id) or c.kind == "tribe":
                    continue
                if fx.relation(s.w, c.id, friend.id) >= 55 and fx.relation(s.w, c.id, foe.id) <= 0 and \
                        s.r.chance(0.4) and not self.at_war_with(c, friend):
                    war["allies"][side].append(c.id)
                    s.record("joined_war", {"ally": c.name, "friend": friend.name, "war": war["name"]}, importance=3,
                             factions=[c, friend, foe], war=war)
                    self.s.realms.change_relation(c, foe, -15)

    # ------------------------------------------------------------------ campaigns
    def campaign(self, war: dict) -> None:
        s = self.s
        r = s.r
        a = s.faction(war["attacker"])
        d = s.faction(war["defender"])
        if a is None or d is None:
            self.end(war, a if a is not None else d)
            return
        battles = 1 + (r.random() < 0.55) + (r.random() < 0.2)
        for _ in range(battles):
            self.battle(war, a, d)
            if not war["active"] or not a.active or not d.active:
                break
        if war["active"] and a.active and d.active and abs(war["score"]) >= 30 and r.chance(0.65):
            self.siege(war, a, d)
        if not war["active"]:
            return
        if not a.active or not d.active:
            self.end(war, a if a.active else d if d.active else None)
            return
        age = s.year - war["year"]
        spent = a.military < 0.35 * a.flags.get("base_military", a.military + 1) and \
            d.military < 0.35 * d.flags.get("base_military", d.military + 1)
        if abs(war["score"]) >= 70 or spent or (age >= 2 and r.chance(min(0.85, 0.1 * age))):
            winner = a if war["score"] >= 35 else d if war["score"] <= -35 else None
            self.end(war, winner)

    def front(self, side, other):
        """The place of `side` nearest the enemy: where the fighting is."""
        s = self.s
        targets = s.holdings(side, deep=True)
        origin = s.anchor(other)
        if not targets or origin is None:
            return None
        st = min(targets, key=lambda t: ((t.x - origin[0]) ** 2 + (t.y - origin[1]) ** 2, t.id))
        return s.land.spots[st.id]

    def host(self, f) -> list:
        """Who leads a side into battle, and the knights of name beside them (the commander first)."""
        s = self.s
        folk = s.folk
        top = f  # the sides of a war are powers in their own right
        out = []
        ruler = s.leader(top)
        if ruler is not None and folk.is_adult(ruler) and folk.eq_age(ruler) < 55 and ruler.kind == "person" and \
                s.r.chance(0.45 if "warlike" in top.values else 0.15):
            out.append(ruler)  # most rulers send their lords and captains; the warlike ride out themselves
        lords = [s.leader(v) for v in s.vassals(top)]
        lords = [x for x in lords if x is not None and folk.is_adult(x) and folk.eq_age(x) < 60]
        knights = [s.w.figures[m] for m in top.members if m in s.w.figures]
        knights = [k for k in knights if k.alive and k.job in ("knight", "captain", "hero") and folk.is_adult(k)
                   and folk.eq_age(k) < 55 and k not in out]
        pool = sorted({x.id: x for x in lords + knights}.values(), key=lambda x: (-x.fame, x.id))
        if not out:
            if pool:
                out.append(pool.pop(0))
            else:
                job = "warchief" if top.kind == "tribe" else "captain"
                race = "half_orc" if top.kind == "tribe" and top.culture == "orcish" else None
                out.append(folk.adult_person(top.culture, age=(25, 45), faction=top, role="member", job=job,
                                             race=race, home=S(top.seat) if top.seat >= 0 else ""))
        pool = [p for p in pool if p not in out]
        s.r.shuffle(pool)
        out += pool[: s.r.randint(0, 3)]
        return out

    def battle(self, war: dict, a, d) -> None:
        s = self.s
        r = s.r
        attacking = war["score"] >= 0 if r.random() < 0.7 else war["score"] < 0
        hit, hitter = (d, a) if attacking else (a, d)
        sp = self.front(hit, hitter)
        if sp is not None:
            st = s.w.settlements[sp.sid]
            place_name = st.name
            if r.chance(0.5):
                river = s.w.river_at(st.x, st.y)
                area = s.area_name(st.x, st.y)
                place_name = river.name if river is not None and r.chance(0.5) else area or st.name
            places = [sp.sid]
            where = S(sp.sid)
        else:
            here = s.anchor(hit) or (s.w.width // 2, s.w.height // 2)
            place_name = s.area_name(*here) or "the border"
            places = []
            where = ""
        name = s.words.battle_name(place_name)
        # Hosts: the standing strength, with the levies called up for a campaign (about three to one).
        fa = self.side_strength(war, attacking) * r.uniform(0.35, 0.8) * LEVY
        fd = self.side_strength(war, not attacking) * r.uniform(0.35, 0.8) * LEVY
        host_a, host_d = self.host(hitter), self.host(hit)
        skill = (max(x.level for x in host_a) - max(x.level for x in host_d)) * 0.03 + \
            (host_a[0].fame - host_d[0].fame) * 0.004
        p_win = max(0.05, min(0.95, fa / (fa + fd * float(self.data["defender_edge"])) + skill))
        attacker_won = r.random() < p_win
        winner, loser = (hitter, hit) if attacker_won else (hit, hitter)
        win_host, lose_host = (host_a, host_d) if attacker_won else (host_d, host_a)
        win_force, lose_force = (fa, fd) if attacker_won else (fd, fa)
        lose_dead = int(lose_force * r.uniform(0.15, 0.4))
        win_dead = int(win_force * r.uniform(0.04, 0.15))
        for f, dead, force in ((loser, lose_dead, lose_force), (winner, win_dead, win_force)):
            f.military = max(1, int(f.military * (1 - 0.8 * dead / max(1.0, force + 1))))
        swing = r.uniform(8, 18)
        war["score"] = max(-100.0, min(100.0, war["score"] + (swing if winner.id == war["attacker"] else -swing)))
        war["battles"] += 1
        war["dead"] += lose_dead + win_dead
        s.stat("battles")
        s.stat("battle_dead", lose_dead + win_dead)
        big = lose_force + win_force > 3000
        win_cmd, lose_cmd = win_host[0], lose_host[0]
        e = s.record("battle_named", {"battle": name, "winner": winner.name, "loser": loser.name,
                                      "victor": win_cmd.full_name(), "vanquished": lose_cmd.full_name(),
                                      "dead": f"{lose_dead + win_dead:,}", "war": war["name"]},
                     importance=3 if big else 2, factions=[winner, loser], places=places,
                     figures=[win_cmd, lose_cmd], war=war,
                     data={"name": name, "won": winner.id, "lost": loser.id, "forces": [int(win_force),
                                                                                        int(lose_force)],
                           "dead": [win_dead, lose_dead], "commanders": [win_cmd.id, lose_cmd.id],
                           "host": [x.id for x in win_host], "foes": [x.id for x in lose_host]})
        win_cmd.fame += 3 if big else 2
        for fig in win_host[1:]:
            fig.fame += 1
        self.casualties(e, war, name, where, win_host, lose_host, chances=(0.04, 0.07))
        self.casualties(e, war, name, where, lose_host, win_host, chances=(0.12, 0.2))
        if lose_cmd.alive and r.chance(0.12) and lose_cmd.role != "ruler":
            self.captives.append({"who": lose_cmd.id, "by": s.top(winner).id, "year": s.year, "war": war["id"]})
            s.record("captured", {"captive": lose_cmd.full_name(), "captor": winner.name, "battle": name},
                     importance=2, factions=[winner, loser], figures=[lose_cmd], war=war)
        s.lore.battle(e, win_host, lose_host)

    def casualties(self, e: dict, war: dict, name: str, where: str, host: list, foes: list, *,
                   chances: tuple[float, float]) -> None:
        s = self.s
        r = s.r
        for i, fig in enumerate(host):
            if not fig.alive or not r.chance(chances[0] if i == 0 else chances[1]):
                continue
            slayer = r.choice(foes) if foes and r.chance(0.7) else None
            if slayer is not None and not slayer.alive:
                slayer = None
            cause = f"at {name}" + (f", slain by {slayer.full_name()}" if slayer is not None else "")
            e["figures"] = list(dict.fromkeys(e["figures"] + [fig.id] + ([slayer.id] if slayer else [])))
            e.setdefault("data", {}).setdefault("fell", []).append([fig.id, slayer.id if slayer else -1])
            was_ruler = fig.role == "ruler"
            title = fig.full_name()
            s.folk.die(fig, "battle", cause=cause, slayer=slayer, where=where, war=war, tell=False)
            if not was_ruler:
                s.record("fell", {"name": title, "battle": name,
                                  "slayer": slayer.full_name() if slayer is not None else "an unknown hand"},
                         importance=3 if fig.fame >= 6 or fig.role == "heir" else 2,
                         figures=[fig] + ([slayer] if slayer is not None else []), war=war,
                         places=e.get("places", []), factions=e.get("factions", []))
            if slayer is not None and was_ruler and not slayer.epithet and title.startswith(("King ", "Queen ")):
                slayer.epithet = "Kingslayer"
            if slayer is not None and slayer.fame >= 10 and not slayer.epithet and r.chance(0.3):
                slayer.epithet = r.choice(s.data["epithets"]["warrior"])

    def prisoners(self) -> None:
        s = self.s
        for c in list(self.captives):
            if s.year <= c["year"]:
                continue
            self.captives.remove(c)
            fig = s.w.figures.get(c["who"])
            captor = s.faction(c["by"])
            if fig is None or not fig.alive:
                continue
            if captor is not None and "cruel" in captor.values and s.r.chance(0.5):
                e = s.record("executed_captive", {"captive": fig.full_name(), "captor": captor.name}, importance=2,
                             factions=[captor], figures=[fig], war=c["war"])
                s.folk.die(fig, "executed", cause_event=e, tell=False)
            else:
                ransom = s.r.choice([200, 500, 1000, 2000, 5000])
                s.record("ransomed", {"captive": fig.full_name(), "captor": captor.name if captor else "their captors",
                                      "ransom": f"{ransom:,}"}, importance=1, figures=[fig],
                         factions=[captor] if captor else [], war=c["war"])

    # ------------------------------------------------------------------ sieges and conquest
    def siege(self, war: dict, a, d) -> None:
        s = self.s
        r = s.r
        attacking = war["score"] > 0
        besieger = a if attacking else d
        defender = d if attacking else a
        sp = self.front(defender, besieger)
        if sp is None:
            return
        st = s.w.settlements[sp.sid]
        top = defender
        if top.seat == sp.sid and abs(war["score"]) < 70:
            return  # a capital holds until the war is nearly lost
        walls = 1.7 if st.walled else 1.25 if s.land.kind_of(sp) in ("town", "city") else 1.0
        garrison = self.strength(top) * 0.35 * walls
        power = self.strength(besieger) * r.uniform(0.5, 1.3)
        name = s.words.battle_name(st.name, "siege")
        s.stat("sieges")
        if r.random() < power / (power + garrison):
            self.conquer(war, sp, besieger, top, name)
            war["score"] += 15 if besieger.id == war["attacker"] else -15
        else:
            war["score"] += -10 if besieger.id == war["attacker"] else 10
            s.record("relieved", {"place": st.name, "attacker": besieger.name, "defender": top.name, "siege": name},
                     importance=2, factions=[besieger, top], places=[sp.sid], war=war)

    def conquer(self, war: dict, sp, winner, loser, siege_name: str) -> None:
        s = self.s
        r = s.r
        st = s.w.settlements[sp.sid]
        cruel = "cruel" in winner.values or winner.kind == "tribe"
        sacked = r.chance(0.6 if cruel else 0.3)
        razed = False
        if winner.kind == "tribe" or (cruel and r.chance(0.35)) or r.chance(0.07):
            if not sp.fated and sp.founded is not None and s.year >= sp.founded + 10:
                razed = True
            elif sp.fated and s.year < s.present - 60 and r.chance(0.3):
                razed = True
        lost = s.land.damage(sp, r.uniform(0.25, 0.5) if sacked or razed else 0.05)
        values = {"attacker": winner.name, "defender": loser.name, "place": st.name, "siege": siege_name,
                  "dead": dead_text(lost), "what": s.land.words(sp.sid), "war": war["name"]}
        war["taken"].append(sp.sid)
        if razed:
            e = s.record("razed", values, importance=4, factions=[winner, loser], places=[sp.sid], war=war)
            self.massacre(sp, e, war, 0.35)
            s.land.ruin(sp, f"razed by {winner.name} in {war['name']}", event=e, by=winner)
            return
        elder = {"hold": "clan", "elfhall": "elven_realm"}.get(sp.destiny)
        if winner.kind == "tribe" or (elder is not None and winner.kind != elder) or                 (sp.human and winner.kind in ("clan", "elven_realm")):
            # Raiders burn and plunder and go home; and no man holds a dwarven hold or an elven hall for long.
            e = s.record("sacked", values, importance=4, factions=[winner, loser], places=[sp.sid], war=war)
            self.massacre(sp, e, war, 0.2)
            s.lore.looted(sp, winner, e)
            return
        e = s.record("sacked" if sacked else "taken", values, importance=4, factions=[winner, loser],
                     places=[sp.sid], war=war)
        if sacked:
            self.massacre(sp, e, war, 0.15)
        s.lore.looted(sp, winner, e)
        s.realms.take(sp, winner, loser, e, sacked=sacked)

    def massacre(self, sp, e: dict, war: dict, chance: float) -> None:
        """When a town is sacked, people of note die in it too."""
        s = self.s
        home = S(sp.sid)
        for hid in sorted(s.living):
            fig = s.w.figures[hid]
            if fig.kind == "person" and fig.home == home and fig.role != "ruler" and s.r.chance(chance):
                e["figures"] = list(dict.fromkeys(e["figures"] + [fig.id]))
                s.folk.die(fig, "battle", cause=f"when {s.place_name(sp.sid)} fell", where=home, war=war,
                           cause_event=e, tell=False)

    # ------------------------------------------------------------------ peace
    def end(self, war: dict, winner) -> None:
        s = self.s
        w = s.w
        cal = s.t.calendar
        war["active"] = False
        war["ended"] = (s.year - cal.start_year) * cal.days_per_year + s.r.uniform(0, cal.days_per_year - 1)
        war["end_year"] = s.year
        self.version = -1
        a = w.factions.get(war["attacker"])
        d = w.factions.get(war["defender"])
        if a is None or d is None:
            return
        war["result"] = "attacker" if winner is a else "defender" if winner is d else "draw"
        key = (min(a.id, d.id), max(a.id, d.id))
        self.past[key] = war
        self.peace[key] = s.year + s.r.randint(4, 12)
        until = war["ended"] + cal.days_per_year * s.r.uniform(3, 8)
        a.flags.setdefault("peace_until", {})[str(d.id)] = until
        d.flags.setdefault("peace_until", {})[str(a.id)] = until
        if a.active and d.active:
            fx.set_relation(w, a.id, d.id, (-35 if winner is not None else -20) + s.r.uniform(-10, 10))
        if war["reason"] == "rebellion":
            if winner is a and a.active:
                a.liege = -1
                s.touch()
                s.record("freedom", {"rebel": a.name, "liege": d.name, "war": war["name"]}, importance=4,
                         factions=[a, d], war=war)
            elif a.active:
                leader = s.leader(a)
                e = s.record("crushed", {"rebel": a.name, "liege": d.name, "war": war["name"]}, importance=3,
                             factions=[a, d], war=war)
                if leader is not None:
                    s.folk.die(leader, "executed", cause_event=e, tell=False)
                if a.active and d.active:
                    a.liege = d.id  # fealty, sworn again on their knees
                    s.touch()
                    fx.set_relation(w, a.id, d.id, 10)
        else:
            seat = d.seat if d.seat >= 0 and s.land.spots[d.seat].standing else None
            place = s.place_name(seat) if seat is not None else (s.area_name(*(s.anchor(d) or (0, 0))) or "the border")
            treaty = s.words.peace_name(place)
            terms = f", {winner.name} the victor" if winner is not None else ", with nothing settled"
            big = war["taken"] or war["dead"] >= 600
            s.record("peace_named" if war["dead"] >= 100 else "peace_small",
                     {"a": a.name, "b": d.name, "terms": terms, "treaty": treaty, "war": war["name"],
                      "dead": f"{war['dead']:,}"}, importance=4 if big else 3, factions=[a, d], war=war,
                     data={"treaty": treaty})
            if winner is not None and a.active and d.active and not war["taken"] and abs(war["score"]) >= 50:
                loser = d if winner is a else a
                sp = self.front(loser, winner)
                top_loser = s.top(loser) or loser
                if sp is not None and sp.sid != top_loser.seat and sp.human and winner.kind not in ("clan", "elven_realm"):
                    e = s.record("ceded", {"place": s.place_name(sp.sid), "loser": loser.name, "winner": winner.name,
                                           "treaty": treaty}, importance=3, factions=[winner, loser], places=[sp.sid],
                                 war=war)
                    s.realms.take(sp, winner, loser, e, sacked=False)
        for side in ("attacker", "defender"):
            for fid in war.get("allies", {}).get(side, []):
                ally = s.faction(fid)
                enemy = d if side == "attacker" else a
                if ally is not None and enemy.active:
                    s.realms.change_relation(ally, enemy, -10)
        s.orders.after_war(war, winner)
        s.lore.war_song(war, winner)
