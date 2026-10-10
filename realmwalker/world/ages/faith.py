"""Faith in the ages: the gods, the churches, the temples raised as towns grow, the saints, and the heresies.

Every faith has its god and lesser powers with their spheres (data/history.json "pantheon"). The churches are older
than the records: each has a prophet who founded it and a line of high priests. As towns grow, temples are raised in
them. Priests who die for the faith are remembered as saints. Now and then a priest hears another voice, and a cult
is born in secret; churches hunt cults, and the hunt has its martyrs on both sides.
"""

from __future__ import annotations

from realmwalker.world import factions as fx
from realmwalker.world.ages.sim import S

GODS_BORN = -10000


class Faith:
    def __init__(self, sim) -> None:
        self.s = sim
        self.gods: dict[str, list[int]] = {}  # faith id -> god figure ids (the god first)
        self.martyrs: list[tuple[int, int]] = []  # (figure id, year died) waiting to be made saints

    # ------------------------------------------------------------------ the gods
    def setup_gods(self) -> None:
        s = self.s
        pantheon = s.data["pantheon"]
        for fid, faith in sorted(s.t.factions["faiths"].items()):
            spec = pantheon.get(fid, {})
            ids = []
            for name, spheres in [[faith["god"], spec.get("spheres", [])]] + spec.get("lesser", []):
                god = fx.Figure(id=s.w.next_figure_id, name=name, sex=spec.get("sex", "male"), race="god",
                                culture="", born=GODS_BORN, role="god", kind="god", spheres=list(spheres),
                                fame=20 if not ids else 8)
                s.w.next_figure_id += 1
                s.w.figures[god.id] = god
                ids.append(god.id)
            self.gods[fid] = ids

    def god_of(self, faith: str):
        ids = self.gods.get(faith)
        return self.s.w.figures[ids[0]] if ids else None

    # ------------------------------------------------------------------ churches
    def setup(self) -> None:
        s = self.s
        land = s.land
        standing = land.standing()
        for fid, faith in sorted(s.t.factions["faiths"].items()):
            if faith.get("cult") or not faith.get("church"):
                continue
            followers = [sp for sp in standing if s.w.settlements[sp.sid].culture in faith["cultures"]]
            if not followers:
                continue
            seat = max(followers, key=lambda sp: (sp.destiny in ("city", "town", "hold", "elfhall"), sp.cap))
            st = s.w.settlements[seat.sid]
            f = s.realms.new("temple", st.culture, faith["name"], faith=fid, seat=seat.sid,
                             founded=s.year0 - s.r.randint(*s.data["realms"]["church_age"]),
                             values=s.fm.pick_values("temple", list(faith["values"])))
            f.presence = [sp.sid for sp in followers if land.kind_of(sp) != "hamlet"]
            race = fx.CULTURE_RACE.get(st.culture, "human")
            prophet = s.folk.person(st.culture, born=f.founded - s.r.randint(30, 60), role="past", job="prophet",
                                    home=S(seat.sid), race=race, faction=f)
            s.living.discard(prophet.id)
            prophet.died = f.founded + s.r.randint(2, 30)
            prophet.cause = s.folk.cause("old")
            prophet.title = "the Prophet"
            prophet.fame = 15
            prophet.notes.append(f"founded {faith['name']}")
            f.rulers.append(prophet.id)
            last = s.realms.prehistory(f, until=s.year0, race=race)
            new = s.folk.adult_person(st.culture, age=(40, 70), faction=f, role="member", job="priest",
                                      home=S(seat.sid), race=race)
            s.realms.crown(f, new)
            god = self.god_of(fid)
            s.record("church_founded", {"prophet": prophet.name, "faction": f.name,
                                        "god": god.name if god is not None else faith["god"],
                                        "place": st.name}, importance=4, year=f.founded, factions=[f],
                     figures=[prophet] + ([god] if god is not None else []), places=[seat.sid])
            del last

    def church_for(self, culture: str):
        faith = fx.faith_for_culture(self.s.t, culture)
        for f in self.s.active("temple"):
            if f.faith == faith:
                return f
        return None

    def temple_for(self, sp) -> None:
        """A place grew into a town: its people raise a temple to their god."""
        s = self.s
        st = s.w.settlements[sp.sid]
        church = self.church_for(st.culture)
        if church is None or sp.sid in church.presence:
            return
        church.presence.append(sp.sid)
        god = self.god_of(church.faith)
        s.record("temple_raised", {"place": st.name, "god": god.name if god is not None else "the gods",
                                   "faction": church.name}, importance=1, places=[sp.sid], factions=[church])

    # ------------------------------------------------------------------ the year
    def year(self) -> None:
        s = self.s
        for church in s.active("temple"):
            if len(s.active("cult")) < s.per_size("cult", "counts") + 1 and s.chance("heresy"):
                self.heresy(church)
        for cult in s.active("cult"):
            self.cult_year(cult)
        self.canonize()

    def heresy(self, church) -> None:
        s = self.s
        taken = {f.faith for f in s.active("cult")}
        gods = [fid for fid, f in sorted(s.t.factions["faiths"].items()) if f.get("cult") and fid not in taken]
        if not gods:
            return
        faith = s.r.choice(gods)
        spec = s.t.factions["faiths"][faith]
        towns = [sp for sp in s.land.standing() if sp.human and sp.kind_now in ("village", "town", "city")]
        if not towns:
            return
        where = s.r.choice(towns)
        st = s.w.settlements[where.sid]
        priests = [s.w.figures[m] for m in church.members if m in s.w.figures]
        priests = [p for p in priests if p.alive and p.kind == "person" and p.role == "member" and p.job == "priest"
                   and p.id != church.leader]
        founder = s.r.choice(priests) if priests and s.r.chance(0.5) else \
            s.folk.adult_person(st.culture, age=(28, 55), role="member", job="priest", home=S(where.sid))
        cult = s.realms.new("cult", st.culture, s.fm.make_name("cult", god=spec["god"]), faith=faith,
                            values=s.fm.pick_values("cult", list(spec["values"])))
        cult.secret = True
        cult.presence = [where.sid]
        cult.military = s.r.randint(4, 15)
        cult.flags["base_military"] = cult.military
        site = next((x for x in sorted(s.w.sites, key=lambda x: (abs(x.x - where.x) + abs(x.y - where.y), x.id))
                     if x.kind in ("ruin", "barrow", "tower") and s.wild.site_free(x) and x.id not in s.wild.tombs),
                    None)
        if site is not None:
            site.faction = cult.id
            cult.site = site.id
        god = self.god_of(faith)
        s.record("heresy", {"founder": founder.full_name(), "god": spec["god"], "place": st.name,
                            "church": church.name, "faction": cult.name}, importance=3, places=[where.sid],
                 factions=[church], figures=[founder] + ([god] if god is not None else []))
        founder.job = "cult leader"
        s.realms.crown(cult, founder)
        fx.set_relation(s.w, cult.id, church.id, -80)
        for realm in s.active("kingdom", "noble_house", "free_city"):
            fx.set_relation(s.w, cult.id, realm.id, -60 + s.r.uniform(-10, 10))

    def cult_year(self, cult) -> None:
        s = self.s
        r = s.r
        towns = [s.land.spots[i] for i in cult.presence if s.land.spots[i].standing]
        cult.presence = [sp.sid for sp in towns]
        if towns and s.chance("cult_spread"):
            near = [sp for sp in s.land.standing() if sp.human and sp.sid not in cult.presence and
                    min(abs(sp.x - t.x) + abs(sp.y - t.y) for t in towns) < 30]
            if near:
                cult.presence.append(r.choice(near).sid)
                cult.military += r.randint(2, 6)
        if towns and s.chance("cult_purge"):
            sp = r.choice(towns)
            st = s.w.settlements[sp.sid]
            church = self.church_for(st.culture)
            if church is None:
                return
            cult.presence = [i for i in cult.presence if i != sp.sid]
            cult.military = max(1, int(cult.military * 0.7))
            leader = s.leader(cult)
            burned = s.folk.adult_person(st.culture, age=(20, 60), faction=cult, role="member", job="cultist",
                                         home=S(sp.sid))
            e = s.record("persecution", {"church": church.name, "cult": cult.name, "place": st.name,
                                         "victim": burned.full_name()}, importance=2, places=[sp.sid],
                         factions=[church, cult], figures=[burned])
            s.folk.die(burned, "executed", cause=r.choice(s.data["causes"]["heretic"]), cause_event=e, tell=False)
            if leader is not None and r.chance(0.2):
                e["figures"].append(leader.id)
                s.folk.die(leader, "executed", cause=r.choice(s.data["causes"]["heretic"]), cause_event=e, tell=False)
            if not cult.presence and cult.military < 8 and cult.active:
                s.realms.fall(cult, kind="cult_destroyed")
        elif towns and s.chance("cult_crime"):
            sp = r.choice(towns)
            victims = [s.w.figures[h] for h in sorted(s.living) if s.w.figures[h].kind == "person"
                       and s.w.figures[h].home == S(sp.sid) and s.w.figures[h].job == "priest"]
            if victims:
                victim = r.choice(victims)
                e = s.record("martyred", {"victim": victim.full_name(), "cult": cult.name,
                                          "place": s.place_name(sp.sid)}, importance=2, places=[sp.sid],
                             figures=[victim])
                s.folk.die(victim, "murder", cause=f"at the hands of {cult.name}", cause_event=e, tell=False)
                self.martyrs.append((victim.id, s.year))

    def died_for_faith(self, fig) -> None:
        if fig.job == "priest":
            self.martyrs.append((fig.id, self.s.year))

    def canonize(self) -> None:
        s = self.s
        for hid, died in list(self.martyrs):
            if s.year - died < 20:
                continue
            self.martyrs.remove((hid, died))
            if not s.r.chance(0.35):
                continue
            fig = s.w.figures[hid]
            church = self.church_for(fig.culture)
            if church is None:
                continue
            fig.title = "Saint"
            fig.fame += 6
            s.record("sainted", {"saint": fig.name, "faction": church.name, "cause": fig.cause}, importance=2,
                     factions=[church], figures=[fig])
