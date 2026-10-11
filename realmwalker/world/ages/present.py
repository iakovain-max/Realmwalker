"""The present: what the ages leave behind is the world the player walks into.

At the last year, doomed places that still stand meet their end; whatever the present needs and the ages did not
happen to leave (two crowns at least, a church, a guild of merchants, the gangs on the roads) is founded in the last
years, so it has a history too; every town, city, hold and hall is held by a realm and every faction has a living
leader. Then the doomed places become ruin sites that keep their whole past (every reference to them is turned into
a reference to the ruin), today's factions are dressed (laws, strength, goals, relations), and the records the rest
of the game reads (dragons, artifacts, ruins, places, lairs, tombs, works, eras) are written into world.politics.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.world import factions as fx
from realmwalker.world import news
from realmwalker.world.ages.eras import name_eras
from realmwalker.world.ages.sim import DYNASTIC, S, X
from realmwalker.world.model import NO_CULTURE, Site

RECENT_YEARS = 2


class Present:
    def __init__(self, sim) -> None:
        self.s = sim
        self.w = sim.w
        self.site_of: dict[int, int] = {}  # doomed spot id -> its ruin's site id

    def finish(self) -> None:
        s = self.s
        late = s.present - 1
        s.year = late
        self.fate_of_the_doomed()
        self.unfounded()
        self.needs()
        self.every_town_held()
        self.leaders()
        s.year = late
        self.ruins()
        self.settlements()
        self.peoples_map()
        self.dress()
        self.figures()
        self.records()
        self.history_order()

    def peoples_map(self) -> None:
        """The map of peoples where the history left them: round every place, the people who live in it now
        (colonies, conquests and towns that changed their speech show as islands of their people)."""
        w = self.w
        ids = w.culture_ids
        for st in sorted(w.settlements, key=lambda st: st.population):
            if st.culture not in ids:
                ids.append(st.culture)
            ci = ids.index(st.culture)
            here = int(w.culture[st.x, st.y])
            if here == ci or here == NO_CULTURE:
                continue
            r = int(round(fx.TERRITORY_RADIUS.get(st.kind, 6) * 0.7))
            x0, x1 = max(0, st.x - r), min(w.width, st.x + r + 1)
            y0, y1 = max(0, st.y - r), min(w.height, st.y + r + 1)
            xs = np.arange(x0, x1)[:, None]
            ys = np.arange(y0, y1)[None, :]
            sub = w.culture[x0:x1, y0:y1]
            sub[((xs - st.x) ** 2 + (ys - st.y) ** 2 <= r * r) & (sub == here)] = ci
        # A bigger neighbour's lands may have been drawn over a small place: every place keeps its own square.
        for st in w.settlements:
            w.culture[st.x, st.y] = ids.index(st.culture)

    def late_year(self, back: int = 12) -> int:
        return self.s.present - self.s.r.randint(1, back)

    # ------------------------------------------------------------------ the last of the doomed, the fated all standing
    def fate_of_the_doomed(self) -> None:
        s = self.s
        for sp in s.land.spots:
            if not sp.fated and sp.standing:
                s.wild.doom(sp)

    def unfounded(self) -> None:
        s = self.s
        for sp in s.land.spots:
            if sp.fated and not sp.standing:
                s.year = self.late_year(4)
                s.land.settle(sp, rebuild=sp.founded is not None)
        s.year = s.present - 1

    # ------------------------------------------------------------------ what today needs
    def needs(self) -> None:
        s = self.s
        orders = s.orders
        while len(s.active("kingdom")) < max(2, s.per_size("kingdom", "counts") - 1):
            s.year = self.late_year()
            if not self.crown_someone():
                break
        if not s.active("noble_house"):
            for k in s.active("kingdom"):
                towns = [sid for sid in s.land.held_by(k.id) if sid != k.seat and
                         s.land.kind_of(s.land.spots[sid]) in ("town", "city")]
                if towns:
                    s.year = self.late_year()
                    h = s.realms.raise_house(s.land.spots[towns[0]], k)
                    e = s.record("granted", {"place": s.place_name(towns[0]), "lord": s.w.figures[h.leader].full_name(),
                                             "liege": k.name, "faction": h.name}, importance=2, factions=[k, h],
                                 figures=[h.leader], places=[towns[0]])
                    s.land.set_owner(towns[0], h.id, e)
                    break
        if not s.active("temple"):
            s.faith.setup()
        church = next(iter(s.active("temple")), None)
        tries = 0
        while church is not None and len(s.active("cult")) < s.per_size("cult", "counts") and tries < 8:
            s.year = self.late_year(30)
            s.faith.heresy(church)
            tries += 1
        while len(s.active("bandit_gang")) < s.per_size("bandit_gang", "counts") and tries < 30:
            s.year = self.late_year(15)
            if orders.gang() is None:
                break
            tries += 1
        while len(s.active("tribe")) < s.per_size("tribe", "counts") and tries < 40:
            areas = s.wild.tribe_areas()
            if not areas:
                break
            s.year = self.late_year(40)
            s.wild.new_tribe(areas[0])
            tries += 1
        while len(s.active("pirate_crew")) < s.per_size("pirate_crew", "counts") and tries < 50:
            s.year = self.late_year(15)
            before = len(s.active("pirate_crew"))
            orders.pirates()
            tries += 1
            if len(s.active("pirate_crew")) == before:
                break
        if not s.active("merchant_guild"):
            s.year = self.late_year(40)
            orders.merchants(force_sid=max(s.active("kingdom"), key=lambda k: k.military).seat)
        while len(s.active("thieves_guild")) < s.per_size("thieves_guild", "counts") and tries < 60:
            s.year = self.late_year(40)
            before = len(s.active("thieves_guild"))
            orders.thieves(force=True)
            tries += 1
            if len(s.active("thieves_guild")) == before:
                break
        while len(s.active("mercenary_company")) < s.per_size("mercenary_company", "counts") and tries < 70:
            sp = orders.biggest(lambda x: x.kind_now in ("town", "city") and
                                x.sid not in {f.seat for f in s.active("mercenary_company")})
            if sp is None:
                break
            s.year = self.late_year(30)
            orders.found("mercenary_company", sp.sid, job="captain", event_kind="company_founded",
                         extra={"war": "the last war"})
            tries += 1
        self.living_beasts()
        s.year = self.late_year(40)
        if not s.active("healers_guild"):
            orders.healers(None, None)
        if not s.active("mages_circle"):
            orders.mages()
        if not s.active("smiths_guild"):
            orders.smiths()
        if not s.active("knightly_order"):
            orders.knights()
        s.year = s.present - 1

    def living_beasts(self) -> None:
        """A world needs its monsters: if the heroes of the ages killed them all, new ones came in the last years,
        and have done harm already."""
        s = self.s
        wild = s.wild
        alive = [h for h, b in wild.beasts.items() if b["type"] != "dragon" and s.w.figures[h].alive]
        tries = 0
        while len(alive) < s.per_size("beasts") and tries < 6:
            tries += 1
            came = self.late_year(30)
            s.year = came
            fig = wild.new_beast(s.r.weighted(*wild.beast_weights()), born=came - s.r.randint(5, 40))
            if fig is None:
                break
            alive.append(fig.id)
            b = wild.beasts[fig.id]
            lair = s.w.sites[b["lair"]]
            spec = s.data["beasts"][b["type"]]
            for _ in range(s.r.randint(1, 3)):
                s.year = min(s.present - 1, s.year + s.r.randint(1, 6))
                near = s.land.nearest_standing(lair.x, lair.y, float(spec["range"]))
                if near:
                    wild.attack(fig, b, s.land.spots[s.r.choice(near)[1]])
        s.year = s.present - 1

    def crown_someone(self) -> bool:
        """Too few crowns in the world: the greatest of the free lords, or a great vassal, is crowned."""
        s = self.s
        options = [f for f in s.active("noble_house", "highland_clan") if s.leader(f) is not None
                   and s.land.held_by(f.id)]
        options.sort(key=lambda f: (f.liege >= 0, -len(s.holdings(f, deep=True)), f.id))
        if not options:
            return False
        f = options[0]
        if f.liege >= 0:
            old = s.faction(f.liege)
            f.liege = -1
            s.touch()
            s.record("freedom", {"rebel": f.name, "liege": old.name if old else "its liege", "war": "a short war"},
                     importance=4, factions=[f] + ([old] if old else []))
        ruler = s.leader(f)
        old_name = f.name
        culture = s.t.cultures.human_or_default(f.culture)
        land_name = s.fm.land_name(culture)
        f.kind = "kingdom"
        f.name = s.fm.make_name("kingdom", culture, land=land_name)
        f.flags["land"] = land_name
        f.flags["dynasty"] = s.realms.family_of(f) or fx.family_of(ruler)
        f.color = s.fm.next_color()
        s.touch()
        s.realms.crown(f, ruler)
        s.record("proclaimed", {"ruler": ruler.full_name(), "old": old_name, "faction": f.name}, importance=4,
                 factions=[f], figures=[ruler], places=[f.seat] if f.seat >= 0 else [])
        return True

    def every_town_held(self) -> None:
        s = self.s
        for sp in s.land.spots:
            if not sp.fated or sp.destiny not in ("town", "city", "hold", "elfhall"):
                continue
            st = s.w.settlements[sp.sid]
            owner = s.faction(st.owner)
            if owner is not None and owner.kind in fx.REALM_KINDS:
                continue
            s.year = self.late_year(8)
            if sp.destiny == "hold":
                family = s.fm.seat_family("dwarven")
                c = s.realms.new("clan", "dwarven", s.fm.make_name("clan", family=family), seat=sp.sid)
                c.flags["family"] = family
                s.realms.found_dynasty(c, family=family, age=(20, 55), race="dwarf")
                e = s.record("chapter", {"people": "dwarves", "faction": c.name, "place": st.name}, importance=3,
                             factions=[c], places=[sp.sid])
                s.land.set_owner(sp.sid, c.id, e)
                continue
            if sp.destiny == "elfhall":
                r = s.realms.new("elven_realm", "elven", s.fm.make_name("elven_realm", land=st.name), seat=sp.sid)
                s.realms.found_dynasty(r, age=(25, 70), race="elf")
                e = s.record("chapter", {"people": "elves", "faction": r.name, "place": st.name}, importance=3,
                             factions=[r], places=[sp.sid])
                s.land.set_owner(sp.sid, r.id, e)
                continue
            realm = s.land.founding_realm(sp)
            if realm is not None and realm.kind != "kingdom":
                realm = None
            h = s.realms.raise_house(sp, realm)
            e = s.record("founded_lordship" if realm is None else "granted",
                         {"founder": s.w.figures[h.leader].full_name(), "lord": s.w.figures[h.leader].full_name(),
                          "place": st.name, "faction": h.name, "liege": realm.name if realm else ""},
                         importance=2, factions=[h] + ([realm] if realm else []), figures=[h.leader], places=[sp.sid])
            s.land.set_owner(sp.sid, h.id, e)
        s.year = s.present - 1

    def leaders(self) -> None:
        s = self.s
        for f in s.active():
            leader = s.w.figures.get(f.leader)
            if leader is not None and leader.alive and leader.faction == f.id:
                continue
            if leader is not None and leader.alive and leader.faction != f.id:
                s.folk.move(leader, f)
                continue
            if f.kind in DYNASTIC:
                s.realms.found_dynasty(f)
            else:
                new = s.folk.adult_person(f.culture if f.culture else "heartland", age=(30, 60), faction=f,
                                          role="member", home=S(f.seat) if f.seat >= 0 else "")
                s.realms.crown(f, new)

    # ------------------------------------------------------------------ the doomed become ruins
    def ruin_name(self, sp, info: dict) -> str:
        s = self.s
        name = info.get("name") or "a nameless place"
        patterns = s.data["ruin_names"]["hold" if sp.destiny == "hold" else "elfhall" if sp.destiny == "elfhall"
                                          else "town"]
        for _ in range(12):
            candidate = s.words.fill(s.r.choice(patterns), name=name)
            if candidate not in s.namer.used:
                s.namer.used.add(candidate)
                return candidate
        return f"the ruins of {name}"

    def ruins(self) -> None:
        s = self.s
        w = s.w
        fated = sum(1 for sp in s.land.spots if sp.fated)
        for sp in s.land.spots:
            if sp.fated:
                continue
            info = dict(s.ruins_info.get(sp.sid) or {"year": s.present - 1, "cause": "abandoned", "kind": "abandoned",
                                                    "name": w.settlements[sp.sid].name, "was": "a village",
                                                    "culture": w.settlements[sp.sid].culture,
                                                    "founded": sp.founded})
            if w.site_at(sp.x, sp.y) is not None:
                continue
            site = Site(id=len(w.sites), kind="ruin", x=sp.x, y=sp.y, name=self.ruin_name(sp, info),
                        danger=min(10, int(w.danger[sp.x, sp.y]) + 1))
            w.sites.append(site)
            self.site_of[sp.sid] = site.id
            info["names"] = [list(n) for n in sp.names]
            info["destiny"] = sp.destiny
            info["peak"] = int(max(info.get("peak", 0), s.peak.get(sp.sid, 0)))
            info["holders"] = []
            info["fell"] = info.pop("year")
            s.ruins_info[sp.sid] = info
        self.remap(fated)
        del w.settlements[fated:]
        s.land.spots = s.land.spots[:fated]
        w.rebuild_index()

    def remap(self, fated: int) -> None:
        """Every reference to a doomed place now points at its ruin."""
        s = self.s
        w = s.w
        site_of = self.site_of

        def ref(r: str) -> str:
            if r.startswith("S") and r[1:].isdigit() and int(r[1:]) >= fated:
                site = site_of.get(int(r[1:]))
                return X(site) if site is not None else ""
            return r

        for e in w.history:
            places = e.get("places", [])
            if any(p >= fated for p in places):
                e["places"] = [p for p in places if p < fated]
                e["sites"] = list(dict.fromkeys(e.get("sites", []) + [site_of[p] for p in places
                                                                         if p >= fated and p in site_of]))
            data = e.get("data")
            if data:
                owners = data.get("owners")
                if owners:
                    for sid, fid in owners:
                        if sid >= fated and sid in site_of:
                            s.ruins_info[sid]["holders"].append([e["year"], fid])
                    data["owners"] = [[sid, fid] for sid, fid in owners if sid < fated]
                    if not data["owners"]:
                        del data["owners"]
                if "ruined" in data:
                    sid = data.pop("ruined")
                    if sid >= fated and sid in site_of:
                        data["ruin"] = site_of[sid]
                if not data:
                    del e["data"]
        for fig in w.figures.values():
            fig.home = ref(fig.home)
            fig.died_at = ref(fig.died_at)
            fig.buried = ref(fig.buried)
        for f in w.factions.values():
            if f.seat >= fated:
                f.flags["old_seat"] = ref(S(f.seat))
                f.seat = -1
            f.presence = [p for p in f.presence if p < fated]
        for a in s.lore.items:
            a["place"] = ref(a["place"])
        for work in s.lore.works:
            work["place"] = ref(work["place"])
        for war in w.wars:
            war["taken"] = [ref(S(sid)) for sid in war.get("taken", [])]
        info = {}
        for sid, data in s.ruins_info.items():
            if sid >= fated and sid in site_of:
                info[str(site_of[sid])] = data
            elif sid < fated:
                data.setdefault("rebuilt", True)
        s.ruins_by_site = info

    # ------------------------------------------------------------------ today's places and powers
    def settlements(self) -> None:
        s = self.s
        for sp in s.land.spots:
            st = s.w.settlements[sp.sid]
            st.population = max(sp.lo, min(sp.hi, int(sp.pop)))
            st.status = {}

    def dress(self) -> None:
        s = self.s
        w = s.w
        fm = s.fm
        cal = s.t.calendar
        for f in s.active():
            if f.kind == "noble_house" and f.liege >= 0:
                f.laws = {}
            else:
                fm.set_laws(f)
            military = f.military
            fm.set_strength(f)
            spec = s.t.factions["kinds"][f.kind]
            if spec["group"] == "realms":
                f.flags["base_military"] = f.military
                f.military = max(5, min(f.military, military)) if military > 0 else f.military
            else:
                f.military = max(1, military) if military > 0 else f.military
                f.flags["base_military"] = max(f.military, int(f.flags.get("base_military", f.military)))
            if "crisis" in f.flags:
                f.flags["crisis"] = (int(f.flags["crisis"]) - cal.start_year) * cal.days_per_year
        self.presence()
        self.relations()
        for f in s.active():
            fm.set_goals(f)
            goal = self.history_goal(f)
            if goal:
                f.goals = ([goal] + f.goals)[:3]
        fx.touch(w)

    def presence(self) -> None:
        s = self.s
        w = s.w
        towns = [st for st in w.settlements if st.kind in ("town", "city")]
        cities = [st for st in w.settlements if st.kind == "city"] or towns
        holds = [st for st in w.settlements if st.kind == "hold"]
        for f in s.active():
            seat = w.settlements[f.seat] if 0 <= f.seat < len(w.settlements) else None
            if f.kind == "merchant_guild":
                realm = s.faction(f.flags.get("realm", -1))
                f.presence = [st.id for st in (s.holdings(realm, deep=True) if realm else [])
                              if st.kind in ("town", "city")] or ([seat.id] if seat else [])
            elif f.kind == "thieves_guild" and seat is not None:
                f.presence = [st.id for st in towns if math.hypot(st.x - seat.x, st.y - seat.y) <= 35]
            elif f.kind == "mages_circle":
                f.presence = [st.id for st in cities]
            elif f.kind == "healers_guild":
                f.presence = [st.id for st in towns]
            elif f.kind == "smiths_guild":
                f.presence = [st.id for st in towns + holds]
            elif f.kind == "temple":
                faith = s.t.factions["faiths"].get(f.faith, {})
                f.presence = sorted({p for p in f.presence if p < len(w.settlements)} |
                                    {st.id for st in w.settlements if st.culture in faith.get("cultures", [])
                                     and st.kind != "hamlet"})
            elif f.kind in ("knightly_order", "mercenary_company", "free_city"):
                f.presence = [seat.id] if seat else []
            elif f.kind == "cult":
                f.presence = [p for p in f.presence if p < len(w.settlements)]
                if not f.presence:
                    options = [st for st in w.settlements if st.kind in ("village", "town", "city")]
                    if options:
                        f.presence = [s.r.choice(options).id]
            if seat is None and f.kind not in ("tribe", "bandit_gang", "pirate_crew", "cult") and f.presence:
                f.seat = f.presence[0]

    def relations(self) -> None:
        """Realms keep what the ages made of their feelings; everyone else starts from the usual baseline."""
        s = self.s
        w = s.w
        data = s.t.factions
        facs = s.active()
        faiths = data["faiths"]
        for i, a in enumerate(facs):
            for b in facs[i + 1:]:
                if b.id in a.relations:
                    continue
                v = s.r.gauss(0, 10)
                ra, rb = s.top(a), s.top(b)
                ga, gb = data["kinds"][a.kind]["group"], data["kinds"][b.kind]["group"]
                if a.liege == b.id or b.liege == a.id:
                    v += 45
                elif ra is rb and ga == gb == "realms":
                    v += s.r.uniform(-35, 55)
                elif ga == gb == "realms":
                    v += s.r.uniform(-45, 25)
                for x, y in ((a, b), (b, a)):
                    gy = data["kinds"][y.kind]["group"]
                    if x.kind == "cult":
                        v -= 60 if gy in ("realms", "faiths") else 10
                    if x.kind in ("bandit_gang", "pirate_crew") and gy in ("realms", "guilds") and \
                            y.kind != "thieves_guild":
                        v -= 55 if gy == "realms" else 25
                    if x.kind == "thieves_guild":
                        v += 20 if y.kind in ("bandit_gang", "pirate_crew") else -30 if gy == "realms" else 0
                    if x.kind == "tribe" and gy == "realms":
                        v -= 40
                    if x.kind == "temple" and gy == "realms":
                        v += 40 if x.faith == y.faith else -20 if "pious" in y.values else 0
                    if x.kind == "merchant_guild" and gy == "realms":
                        v += 30 if x.flags.get("realm") in (y.id, ra.id if ra else -1) else 8
                    if x.kind == "knightly_order" and gy == "realms" and x.faith == y.faith:
                        v += 25
                    if x.kind == "mercenary_company" and gy == "realms":
                        v += 10
                shared = len(set(a.values) & set(b.values))
                clash = sum(1 for va in a.values for vb in b.values if vb in data["values"][va]["clashes"])
                v += shared * 8 - clash * 10
                if a.faith != b.faith and (faiths.get(a.faith, {}).get("cult") or faiths.get(b.faith, {}).get("cult")):
                    v -= 15
                fx.set_relation(w, a.id, b.id, v)
        # Cults are hated by every realm and church, whatever else happened.
        for c in s.active("cult"):
            for other in facs:
                group = data["kinds"][other.kind]["group"]
                if other.id != c.id and group in ("realms", "faiths") and fx.relation(w, c.id, other.id) > -30:
                    fx.set_relation(w, c.id, other.id, -40 - s.r.uniform(0, 30))
        # Fallen factions keep no feelings (nobody is left to have them).
        for f in w.factions.values():
            if not f.active:
                for other in list(f.relations):
                    w.factions[other].relations.pop(f.id, None)
                f.relations = {}

    def history_goal(self, f) -> str:
        s = self.s
        w = s.w
        for war in reversed(w.wars):
            if war.get("active") or war.get("result") not in ("attacker", "defender"):
                continue
            loser = war["defender"] if war["result"] == "attacker" else war["attacker"]
            winner = war["attacker"] if loser == war["defender"] else war["defender"]
            if loser != f.id or s.faction(winner) is None:
                continue
            taken = [r for r in war.get("taken", []) if r.startswith("S")]
            for ref in taken:
                st = w.settlements[int(ref[1:])]
                holder = s.top(s.faction(st.owner)) if st.owner >= 0 else None
                if holder is not None and holder.id == winner:
                    return f"to take back {st.name}"
            return f"to avenge {war['name']}"
        return ""

    # ------------------------------------------------------------------ the people of today
    def figures(self) -> None:
        s = self.s
        w = s.w
        rulers = {r for f in w.factions.values() for r in f.rulers}
        leaders = {f.leader: f for f in s.active()}
        for f in s.active(*DYNASTIC):
            s.realms.heir_of(f)
        heirs = {hid for hid in s.realms.heirs.values() if hid >= 0}
        for fig in w.figures.values():
            if fig.kind == "god":
                fig.role = "god"
                continue
            if fig.kind in ("beast", "dragon"):
                fig.role = "beast"
                continue
            if fig.alive:
                f = w.factions.get(fig.faction)
                if fig.id in leaders:
                    fig.role = "ruler"
                    fig.title = fx.figure_title(s.t, leaders[fig.id].kind, fig.sex, leaders[fig.id].culture)
                elif fig.id in heirs and f is not None and f.active:
                    fig.role = "heir"
                elif f is not None and f.active:
                    leader = s.leader(f)
                    fig.role = "spouse" if leader is not None and leader.spouse == fig.id else "member"
                elif fig.job in ("adventurer", "hero"):
                    fig.role = "hero"
                elif f is not None:
                    fig.role = "exile"
                else:
                    fig.role = "folk"
            else:
                fig.role = "past" if fig.id in rulers else "dead"
        w.politics["grudges"] = self.grudges()
        legends = sorted((fig for fig in w.figures.values() if fig.kind == "person" and not fig.alive
                          and fig.id not in rulers and (fig.fame >= 6 or fig.kills or fig.notes)),
                         key=lambda fig: (-fig.fame, fig.id))
        for fig in legends[: 12 + 6 * s.size]:
            fig.role = "legend"
            self.deeds(fig)
        for fig in w.figures.values():
            if fig.role == "legend" and not fig.notes:
                self.deeds(fig)

    def grudges(self) -> list[dict]:
        """Blood feuds: the living whose father, mother, husband, wife, brother, sister, son or daughter was slain by
        someone still alive. They have not forgotten (game/people.py gives them the want; quests the work)."""
        s = self.s
        w = s.w
        folk = s.folk
        out = []
        for fig in w.figures.values():
            if not fig.alive or fig.kind != "person":
                continue
            kin = [(rel, w.figures.get(k)) for rel, k in (("father", fig.father), ("mother", fig.mother),
                                                           ("spouse", fig.spouse))]
            kin += [("child", k) for k in folk.children(fig, living=False)]
            kin += [("sibling", k) for k in folk.siblings(fig, living=False)]
            for rel, k in kin:
                if k is None or k.alive or k.slayer < 0:
                    continue
                slayer = w.figures.get(k.slayer)
                if slayer is None or not slayer.alive or slayer.kind != "person" or slayer.id == fig.id:
                    continue
                word = {"spouse": "husband" if k.sex == "male" else "wife",
                        "child": "son" if k.sex == "male" else "daughter",
                        "sibling": "brother" if k.sex == "male" else "sister"}.get(rel, rel)
                out.append({"by": fig.id, "against": slayer.id, "kin": k.id, "relation": word, "year": k.died,
                            "cause": k.cause})
                break
        return out

    def deeds(self, fig) -> None:
        w = self.w
        for victim_id in fig.kills[:2]:
            victim = w.figures.get(victim_id)
            if victim is not None and len(fig.notes) < 3:
                where = victim.cause.split(",")[0] if victim.cause.startswith("at ") else ""
                fig.notes.append(f"slew {victim.full_name()}" + (f" {where}" if where else ""))
        if not fig.notes and fig.cause:
            fig.notes.append(f"died {fig.cause}")

    # ------------------------------------------------------------------ the records the rest of the game reads
    def records(self) -> None:
        s = self.s
        w = s.w
        pol = w.politics
        self.dragons()
        pol["artifacts"] = [self.artifact_record(a) for a in s.lore.items]
        pol["ruins"] = {k: v for k, v in s.ruins_by_site.items()}
        for site_id, past in s.wild.elder.items():
            pol["ruins"].setdefault(str(site_id), past)
        pol["founded"] = {str(sp.sid): sp.founded for sp in s.land.spots if sp.founded is not None}
        pol["places"] = {str(sp.sid): {"founded": sp.founded, "names": [list(n) for n in sp.names],
                                       "times": sp.times, "peak": int(s.peak.get(sp.sid, sp.pop))}
                         for sp in s.land.spots}
        lairs = {}
        for hid, b in s.wild.beasts.items():
            fig = w.figures[hid]
            if fig.alive:
                lairs[str(b["lair"])] = hid
        pol["lairs"] = lairs
        pol["tombs"] = {str(k): v for k, v in s.wild.tombs.items()}
        pol["towers"] = {str(k): v for k, v in s.wild.towers.items()}
        pol["works"] = s.lore.works
        pol["eras"] = name_eras(s)
        pol["scars"] = self.scars()
        pol["history_from"] = s.year0
        pol["history_years"] = s.years
        pol["next_event"] = s.next_event
        pol["next_war"] = max([war["id"] for war in w.wars], default=-1) + 1

    def scars(self) -> list[dict]:
        """Where the history left its dead: the fields of the great battles, and the towns put to the sword. The
        dead of such places do not rest easily (game/past.py)."""
        s = self.s
        w = s.w
        biomes = s.t.biomes
        out: list[dict] = []
        taken: set[tuple[int, int]] = set()
        battles = [e for e in w.history if e["kind"] == "battle_named" and e.get("places")
                   and sum(e.get("data", {}).get("dead", [0])) >= 60]  # the deadliest fields (below)
        battles.sort(key=lambda e: (-sum(e["data"]["dead"]), e["id"]))
        for e in battles[: 10 + 5 * s.size]:
            st = w.settlements[e["places"][0]]
            options = [(x, y) for x in range(st.x - 2, st.x + 3) for y in range(st.y - 2, st.y + 3)
                       if w.in_bounds(x, y) and (x, y) not in taken and w.settlement_at(x, y) is None
                       and w.site_at(x, y) is None and biomes.passable[int(w.biome[x, y])]]
            if not options:
                continue
            x, y = s.r.choice(options)
            taken.add((x, y))
            out.append({"x": x, "y": y, "kind": "battle", "name": e["data"]["name"], "year": e["year"],
                        "dead": int(sum(e["data"]["dead"])), "event": e["id"]})
        for e in w.history:
            ruin = (e.get("data") or {}).get("ruin")
            if e["kind"] in ("razed", "beast_destroyed", "burned") and ruin is not None and 0 <= ruin < len(w.sites):
                site = w.sites[ruin]
                if (site.x, site.y) not in taken:
                    taken.add((site.x, site.y))
                    out.append({"x": site.x, "y": site.y, "kind": "massacre", "name": site.name, "year": e["year"],
                                "dead": 0, "event": e["id"]})
        return out

    def dragons(self) -> None:
        s = self.s
        w = s.w
        out = []
        for hid, b in sorted(s.wild.beasts.items()):
            if b["type"] != "dragon":
                continue
            fig = w.figures[hid]
            record = {"name": s.wild.beast_title(fig), "color": b.get("color", "red"), "alive": fig.alive,
                      "lair": b["lair"] if fig.alive else -1, "last_seen": self.last_seen(fig), "figure": hid}
            if not fig.alive:
                slayer = w.figures.get(fig.slayer)
                record["lair"] = -1
                if slayer is not None:
                    record["slain_by"] = slayer.full_name()
                    record["slain_year"] = fig.died
            out.append(record)
        if not any(d["alive"] and d["lair"] >= 0 for d in out):
            mountains = {"mountains", "high_mountains", "hills"}
            lair = s.wild.lair_for(("cave", "ruin"), biomes=mountains) or s.wild.lair_for(("cave", "ruin", "tower"))
            if lair is not None:
                s.year = self.late_year(60)
                fig = s.wild.new_beast("dragon", lair=lair)
                if fig is not None:
                    b = s.wild.beasts[fig.id]
                    b["asleep"] = True
                    fig.role = "beast"
                    s.record("dragon_sleeps", {"dragon": s.wild.beast_title(fig)}, importance=3, sites=[lair.id],
                             figures=[fig])
                    out.append({"name": s.wild.beast_title(fig), "color": b["color"], "alive": True,
                                "lair": lair.id, "last_seen": s.year, "figure": fig.id})
                    w.politics.setdefault("lairs", {})[str(lair.id)] = fig.id
                s.year = s.present - 1
        w.politics["dragons"] = out

    def last_seen(self, fig) -> int:
        seen = fig.born
        for e in self.w.history:
            if fig.id in e.get("figures", ()):
                seen = max(seen, e["year"])
        return seen

    def artifact_record(self, a: dict) -> dict:
        place = a["place"]
        site = int(place[1:]) if place.startswith("X") else -1
        record = {"name": a["name"], "kind": a["kind"], "site": site, "bearer": a.get("bearer", -1),
                  "found": False, "fate": a.get("fate") or "is kept by its owner", "holder": a["holder"],
                  "place": place, "maker": a["maker"], "made": a["made"], "material": a["material"],
                  "story": list(a["story"])}
        if a["holder"] >= 0:
            holder = self.w.figures.get(a["holder"])
            if holder is not None:
                record["fate"] = f"is held by {holder.full_name()}"
        return record

    # ------------------------------------------------------------------ the record in order, and the news of it
    def history_order(self) -> None:
        s = self.s
        w = s.w
        w.history.sort(key=lambda e: (e["year"], e.get("id", 0)))
        cal = s.t.calendar
        for e in w.history:
            if e["year"] < s.present - RECENT_YEARS or e.get("importance", 2) < 2 or not e.get("text"):
                continue
            place = None
            for pid in e.get("places", []):
                if 0 <= pid < len(w.settlements):
                    st = w.settlements[pid]
                    place = (st.x, st.y)
                    break
            if place is None:
                for site_id in e.get("sites", []):
                    if 0 <= site_id < len(w.sites):
                        place = (w.sites[site_id].x, w.sites[site_id].y)
                        break
            if place is None:
                for fid in e.get("factions", []):
                    f = w.factions.get(fid)
                    place = news.faction_place(w, f) if f is not None and f.active else None
                    if place is not None:
                        break
            if place is None:
                continue
            day = (e["year"] - cal.start_year) * cal.days_per_year + s.r.uniform(0, cal.days_per_year - 1)
            day = min(day, -s.r.uniform(3, 60))
            news.add(w, e["text"], place[0], place[1], kind=e["kind"], importance=e.get("importance", 2),
                     factions=[f for f in e.get("factions", []) if f in w.factions and w.factions[f].active],
                     places=e.get("places", []), day=day)
