"""Orders of the ages: guilds, companies, orders and outlaws, each founded when the history gives it a reason.

Merchants band together when a capital grows rich; thieves when a city is big enough to hide them; a great mage
founds a circle; healers organise after a plague has shown what disorder costs; a paladin founds an order to fight
the dark; veterans of a war sell their swords; deserters take to the roads, and lords hang them.
"""

from __future__ import annotations

import math

from realmwalker.world import factions as fx
from realmwalker.world.ages.sim import S


class Orders:
    def __init__(self, sim) -> None:
        self.s = sim

    def setup(self) -> None:
        pass  # every order is founded in the years themselves

    # ------------------------------------------------------------------ founding
    def found(self, kind: str, sid: int, *, founder=None, job: str = "", name: str = "", values=None,
              event_kind: str = "guild_founded", importance: int = 2, extra: dict | None = None, quiet=False, **kw):
        s = self.s
        st = s.w.settlements[sid]
        culture = st.culture if st.culture not in ("orcish",) else "heartland"
        name = name or s.fm.make_name(kind, culture, seat=st.name, **(extra or {}))
        f = s.realms.new(kind, culture, name, seat=sid, **kw)
        if values:
            f.values = values
        f.presence = [sid]
        spec = s.t.factions["kinds"][kind]
        f.military = s.r.randint(*spec["military"])
        f.wealth = s.r.randint(*spec["wealth"])
        f.flags["base_military"] = f.military
        if founder is not None and (any(g.leader == founder.id for g in s.active() if g is not f)
                                    or founder.id in s.realms.heirs.values()):
            founder = None  # a lord or an heir does not leave their house to head an order: a follower does
        if founder is None:
            founder = s.folk.adult_person(culture, age=(30, 60), role="member", job=job, home=S(sid))
        s.realms.crown(f, founder)
        founder.fame += 3
        if not quiet:
            s.record(event_kind, {"founder": founder.full_name(), "faction": f.name, "place": st.name,
                                  **{k: str(v) for k, v in (extra or {}).items()}},
                     importance=importance if not f.secret else 1, factions=[] if f.secret else [f],
                     figures=[founder], places=[sid])
        return f

    def biggest(self, test=None):
        s = self.s
        options = [sp for sp in s.land.standing() if sp.human and (test is None or test(sp))]
        return max(options, key=lambda sp: (sp.pop, -sp.sid)) if options else None

    # ------------------------------------------------------------------ the year
    def year(self) -> None:
        s = self.s
        self.merchants()
        self.thieves()
        if not s.active("mages_circle") and s.year >= s.year0 + s.years // 5 and s.chance("mages_circle"):
            self.mages()
        if not s.active("smiths_guild") and s.chance("smiths_guild"):
            self.smiths()
        if not s.active("knightly_order") and s.chance("knightly_order"):
            self.knights()
        if not s.active("healers_guild") and s.year >= s.present - 25 and s.chance("healers_guild", 3.0):
            self.healers(None, None)
        for c in s.active("mercenary_company"):
            if s.chance("company_ends"):
                s.realms.fall(c, kind="company_disbanded")
        for g in s.active("bandit_gang"):
            if s.chance("gang_destroyed"):
                self.hang(g)
        if len(s.active("bandit_gang")) < s.per_size("bandit_gang", "counts") + 2 and s.chance("gang_new"):
            self.gang()
        if len(s.active("pirate_crew")) < s.per_size("pirate_crew", "counts") + 1 and s.chance("pirates_new"):
            self.pirates()
        for p in s.active("pirate_crew"):
            if s.chance("pirates_end"):
                s.realms.fall(p, kind="pirates_ended")

    def town_grew(self, sp) -> None:
        if sp.kind_now == "city":
            self.merchants(force_sid=sp.sid)

    def merchants(self, force_sid: int | None = None) -> None:
        s = self.s
        have = {f.flags.get("realm") for f in s.active("merchant_guild")}
        for k in s.active("kingdom", "free_city"):
            if k.id in have or k.seat < 0 or not s.land.spots[k.seat].standing:
                continue
            sp = s.land.spots[k.seat]
            if sp.kind_now not in ("town", "city"):
                continue
            if force_sid != k.seat and not s.chance("merchant_guild"):
                continue
            g = self.found("merchant_guild", k.seat, job="merchant")
            g.flags["realm"] = k.id
            fx.set_relation(s.w, g.id, k.id, 35)

    def thieves(self, force: bool = False) -> None:
        s = self.s
        if len(s.active("thieves_guild")) >= s.per_size("thieves_guild", "counts"):
            return
        if not force and not s.chance("thieves_guild"):
            return
        taken = {f.seat for f in s.active("thieves_guild")}
        sp = self.biggest(lambda sp: sp.kind_now == "city" and sp.sid not in taken) or \
            self.biggest(lambda sp: sp.kind_now == "town" and sp.sid not in taken)
        if sp is None:
            return
        g = self.found("thieves_guild", sp.sid, job="thief", event_kind="guild_secret")
        g.secret = True

    def mages(self, mage=None, tower=None) -> None:
        s = self.s
        sp = self.biggest(lambda sp: sp.kind_now == "city") or self.biggest(lambda sp: sp.kind_now == "town")
        if sp is None:
            return
        if mage is None:
            mage = s.folk.adult_person(s.w.settlements[sp.sid].culture, age=(45, 80), role="member", job="mage",
                                       home=S(sp.sid))
            mage.cls, mage.level = "wizard", s.r.randint(9, 16)
        mage.job = "archmage"
        g = self.found("mages_circle", sp.sid, founder=mage, event_kind="circle_founded", importance=3)
        if tower is None:
            tower = next((x for x in s.w.sites if x.kind == "tower" and s.wild.site_free(x)
                          and s.wild.towers.get(x.id) in (None, mage.id)), None)
        if tower is not None and s.wild.site_free(tower):
            tower.faction = g.id
            g.site = tower.id

    def mage_rose(self, mage, tower) -> None:
        if not self.s.active("mages_circle") and self.s.r.chance(0.5):
            self.mages(mage, tower)

    def smiths(self) -> None:
        s = self.s
        holds = [sp for sp in s.land.standing() if sp.destiny == "hold"]
        sp = max(holds, key=lambda sp: (sp.pop, -sp.sid)) if holds else self.biggest(lambda sp: sp.kind_now == "city")
        if sp is None:
            return
        self.found("smiths_guild", sp.sid, job="smith")

    def knights(self) -> None:
        s = self.s
        church = next((f for f in s.active("temple") if f.faith == "radiant"), None) or \
            next(iter(s.active("temple")), None)
        if church is None:
            return
        towns = [s.land.spots[i] for i in church.presence if s.land.spots[i].standing and
                 s.land.spots[i].kind_now in ("town", "city")]
        if not towns:
            return
        sp = s.r.choice(towns)
        heroes = [s.w.figures[h] for h in sorted(s.living) if s.w.figures[h].kind == "person"
                  and s.w.figures[h].job in ("knight", "hero") and s.w.figures[h].fame >= 6
                  and s.folk.is_adult(s.w.figures[h])]
        founder = max(heroes, key=lambda h: (h.fame, -h.id)) if heroes and s.r.chance(0.7) else None
        if founder is not None:
            founder.job = "paladin"
        god = s.t.factions["faiths"][church.faith]["short"]
        g = self.found("knightly_order", sp.sid, founder=founder, job="paladin", faith=church.faith,
                       event_kind="order_founded", importance=3, extra={"god": god})
        fx.set_relation(s.w, g.id, church.id, 60)

    def healers(self, plague_event: dict | None, sp) -> None:
        sp = sp if sp is not None and sp.standing and sp.human else self.biggest(lambda x: x.kind_now == "city") or \
            self.biggest()
        if sp is None:
            return
        name = (plague_event or {}).get("data", {}).get("name") or "the plague"
        self.found("healers_guild", sp.sid, job="healer", event_kind="healers_founded", importance=3,
                   extra={"plague": name})

    def after_plague(self, e: dict, sp) -> None:
        if not self.s.active("healers_guild"):
            self.healers(e, sp)

    # ------------------------------------------------------------------ after wars: veterans and deserters
    def after_war(self, war: dict, winner) -> None:
        s = self.s
        if war["battles"] < 2:
            return
        if len(s.active("mercenary_company")) < s.per_size("mercenary_company", "counts") + 1 and s.r.chance(0.3):
            side = winner or s.faction(war["defender"]) or s.faction(war["attacker"])
            if side is not None:
                towns = [st for st in s.holdings(side, deep=True) if s.land.spots[st.id].kind_now in ("town", "city")]
                if towns:
                    st = s.r.choice(towns)
                    veterans = [s.w.figures[h] for h in sorted(s.living) if s.w.figures[h].kind == "person"
                                and s.w.figures[h].faction == side.id and s.w.figures[h].job in ("knight", "captain")
                                and s.w.figures[h].role == "member" and s.folk.is_adult(s.w.figures[h])]
                    founder = max(veterans, key=lambda v: (v.fame, -v.id)) if veterans else None
                    if founder is not None:
                        founder.job = "captain"
                    self.found("mercenary_company", st.id, founder=founder, job="captain",
                               event_kind="company_founded", extra={"war": war["name"]})
        if len(s.active("bandit_gang")) < s.per_size("bandit_gang", "counts") + 2 and s.r.chance(0.25):
            self.gang(war=war)

    def gang(self, war: dict | None = None):
        s = self.s
        w = s.w
        lairs = [x for x in w.sites if x.kind in ("ruin", "cave", "tower") and s.wild.site_free(x)
                 and x.id not in s.wild.tombs and w.road[max(0, x.x - 8):x.x + 9, max(0, x.y - 8):x.y + 9].any()]
        if not lairs:
            return None
        site = s.r.choice(lairs)
        near = s.land.nearest_standing(site.x, site.y, 10**6, test=lambda sp: sp.human)
        culture = w.settlements[near[0][1]].culture if near else "heartland"
        if culture in ("halfling", "orcish", "elven", "dwarven"):
            culture = "heartland"
        captain = s.folk.adult_person(culture, age=(20, 45), role="member", job="outlaw",
                                      home=f"X{site.id}")
        captain.epithet = s.r.choice(s.t.factions["words"]["epithet"])
        area = w.area_at(site.x, site.y)
        land = area.name if area is not None else site.name
        name = s.fm.make_name("bandit_gang", leader=captain.first_name, land=land)
        g = s.realms.new("bandit_gang", culture, name, site=site.id, area=area.id if area else -1,
                         values=["cruel", "mercantile"])
        g.flags["range"] = 16
        g.military = s.r.randint(8, 25)
        g.wealth = s.r.randint(10, 80)
        g.flags["base_military"] = g.military
        s.realms.crown(g, captain)
        site.faction = g.id
        for other in s.active():
            group = s.t.factions["kinds"][other.kind]["group"]
            v = -55 if group == "realms" else -25 if group == "guilds" and other.kind != "thieves_guild" else \
                20 if other.kind == "thieves_guild" else 0
            if v and other.id != g.id:
                fx.set_relation(w, g.id, other.id, v + s.r.gauss(0, 8))
        s.record("gang_new", {"gang": name, "place": land}, importance=1, factions=[g], figures=[captain],
                 sites=[site.id], war=war)
        return g

    def hang(self, g) -> None:
        s = self.s
        where = s.anchor(g)
        if where is None:
            return
        near = s.land.nearest_standing(where[0], where[1], 30)
        lord = None
        for _, sid in near:
            owner = s.faction(s.w.settlements[sid].owner)
            if owner is not None:
                lord = s.top(owner) or owner
                break
        if lord is None or lord.kind == "tribe":
            return
        leader = s.leader(g)
        e = s.record("gang_destroyed", {"lord": lord.name, "gang": g.name}, importance=1, factions=[g, lord],
                     figures=[leader] if leader else [])
        if leader is not None:
            s.folk.die(leader, "executed", cause="on the gallows", cause_event=e, tell=False)
        if g.active:
            s.realms.fall(g, event=e)

    def pirates(self) -> None:
        s = self.s
        w = s.w
        if "ocean" not in w.biome_ids:
            return
        ocean = w.biome_ids.index("ocean")
        coast = [sp for sp in s.land.standing() if sp.human and (w.biome[max(0, sp.x - 2):sp.x + 3,
                                                                          max(0, sp.y - 2):sp.y + 3] == ocean).any()]
        if not coast:
            return
        home = s.r.choice(coast)
        st = w.settlements[home.sid]
        culture = st.culture if s.t.cultures.is_human(st.culture) else "southron"
        captain = s.folk.adult_person(culture, age=(25, 50), role="member", job="pirate", home=S(home.sid))
        captain.epithet = s.r.choice(s.t.factions["words"]["epithet"])
        p = s.realms.new("pirate_crew", culture, s.fm.make_name("pirate_crew"), faith="drowned")
        p.flags["coast"] = [home.x, home.y]
        p.flags["range"] = 30
        p.military = s.r.randint(*s.t.factions["kinds"]["pirate_crew"]["military"])
        p.flags["base_military"] = p.military
        s.realms.crown(p, captain)
        s.record("pirates_new", {"crew": p.name, "captain": captain.full_name(), "place": st.name}, importance=1,
                 factions=[p], figures=[captain], places=[home.sid])

    def nearest_town(self, x: int, y: int):
        s = self.s
        options = [sp for sp in s.land.standing() if sp.human and sp.kind_now in ("town", "city")]
        return min(options, key=lambda sp: (math.hypot(sp.x - x, sp.y - y), sp.sid)) if options else None
