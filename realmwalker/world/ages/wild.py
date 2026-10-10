"""The wild in the ages: tribes and their raids, beasts and dragons in their lairs, and the heroes who hunt them.

- Tribes of orcs, goblins and nomads live in the rough country. They raid villages, burn hamlets and carry people
  off; a child taken from a lord's hall may grow up to lead the tribe that took them.
- Beasts with names (dragons, trolls, ogres, giant spiders, dire wolves, great bears) take lairs in caves and
  ruins and come out to kill. The more they kill, the more likely someone goes to kill them: a wandering hero, a
  lord's knight. Heroes who win become famous (and sometimes lords); heroes who lose leave their gear in the lair.
- The old sites have pasts: barrows hold the chieftains and kings of before the records (and some of after),
  towers were raised by mages, ruins older than the records belonged to peoples nobody names any more.
- Doomed places (land.py) meet their end here when their year comes, by whatever is near: war, a horde, a beast,
  or plague, flood and blight and the slow going away of the last families.
"""

from __future__ import annotations

import math

from realmwalker.world import factions as fx
from realmwalker.world.ages.sim import S, X
from realmwalker.world.ages.war import dead_text

TRIBE_HOMES = {"hills": "orcs", "mountains": "orcs", "tundra": "orcs", "pine_forest": "goblins", "marsh": "goblins",
               "forest": "goblins", "desert": "nomads"}


class Wild:
    def __init__(self, sim) -> None:
        self.s = sim
        self.beasts: dict[int, dict] = {}  # figure id -> {"type", "lair", "infamy", "sleep_until", "awake_until"}
        self.tombs: dict[int, int] = {}  # site id -> figure buried there
        self.towers: dict[int, int] = {}  # site id -> the figure who raised it
        self.elder: dict[int, dict] = {}  # site id -> an elder ruin's past

    # ------------------------------------------------------------------ the sites of the wild
    def site_free(self, site) -> bool:
        return site.faction < 0 and not any(b["lair"] == site.id for b in self.beasts.values()
                                            if self.s.w.figures[self._hid(b)].alive)

    def _hid(self, b: dict) -> int:
        return b["id"]

    def lair_for(self, kinds: tuple[str, ...], *, biomes=None, near=None, within: float = 10**6):
        s = self.s
        w = s.w
        options = []
        for site in w.sites:
            if site.kind not in kinds or site.id in self.tombs or not self.site_free(site):
                continue
            if biomes and w.biome_ids[int(w.biome[site.x, site.y])] not in biomes:
                continue
            if near is not None and math.hypot(site.x - near[0], site.y - near[1]) > within:
                continue
            options.append(site)
        return s.r.choice(options) if options else None

    def lair_holder(self, site_id: int):
        for hid, b in self.beasts.items():
            fig = self.s.w.figures[hid]
            if fig.alive and b["lair"] == site_id:
                return fig
        return None

    # ------------------------------------------------------------------ setting out the wild
    def setup(self) -> None:
        self.tribes_setup()
        self.barrows()
        self.towers_setup()
        self.elder_ruins()
        for _ in range(self.s.per_size("dragons")):
            self.new_beast("dragon", born=self.s.year0 - self.s.r.randint(150, 900), quiet=True)
        for _ in range(self.s.per_size("beasts")):
            btype = self.s.r.weighted(*self.beast_weights())
            self.new_beast(btype, born=self.s.year0 - self.s.r.randint(10, 80), quiet=True)

    def tribe_areas(self) -> list:
        s = self.s
        w = s.w
        settled = {w.settlements[sp.sid].area for sp in s.land.spots}
        out = []
        for a in w.areas:
            if a.kind not in TRIBE_HOMES or a.id in settled or a.size < 20:
                continue
            if any(f.area == a.id for f in s.active("tribe")):
                continue
            mask = w.area == a.id
            danger = float(w.danger[mask].mean()) if mask.any() else 0.0
            if danger >= 2.0:
                out.append((a.size * danger, a))
        out.sort(key=lambda t: (-t[0], t[1].id))
        return [a for _, a in out]

    def tribes_setup(self) -> None:
        for a in self.tribe_areas()[: self.s.per_size("tribes")]:
            self.new_tribe(a, founded=self.s.year0 - self.s.r.randint(20, 300), quiet=True)

    def new_tribe(self, a, *, founded: int | None = None, quiet: bool = False):
        s = self.s
        people = TRIBE_HOMES[a.kind]
        culture = "southron" if people == "nomads" else "orcish"
        name = s.fm.make_name("tribe", land=a.name)
        t = s.realms.new("tribe", culture, name, area=a.id, founded=founded,
                         faith="old_ways" if people == "nomads" else "red_jaw")
        t.flags["people"] = people
        t.military = s.r.randint(*s.t.factions["kinds"]["tribe"]["military"])
        t.flags["base_military"] = t.military
        race = {"orcs": "half_orc", "goblins": "half_orc", "nomads": "human"}[people]
        chief = s.folk.adult_person(culture, age=(22, 45), faction=t, role="member", job="warchief", race=race)
        s.realms.crown(t, chief)
        if s.r.chance(0.6):
            chief.epithet = s.r.choice(s.t.factions["words"]["epithet"])
        lair = self.lair_for(("cave", "ruin"), near=(a.x, a.y), within=max(12.0, math.sqrt(a.size)))
        if lair is not None:
            lair.faction = t.id
            t.site = lair.id
            chief.home = X(lair.id)
        if not quiet:
            s.record("tribe_rose", {"tribe": name, "place": a.name, "chief": chief.full_name()}, importance=3,
                     factions=[t], figures=[chief])
        return t

    def barrows(self) -> None:
        """Every barrow holds someone: a chieftain or king of before the records, with what was buried with them."""
        s = self.s
        w = s.w
        for site in w.sites:
            if site.kind != "barrow":
                continue
            if s.r.chance(0.3):
                continue  # an empty barrow: someone of the ages may be laid in it yet
            near = s.land.nearest_standing(site.x, site.y, 10**6) or []
            culture = "heartland"
            for _, sid in near[:1]:
                culture = s.land.spots[sid].prior
            if culture in ("halfling", "elven", "dwarven"):
                culture = "northmarch"
            died = s.year0 - s.r.randint(40, 700)
            king = s.folk.person(culture, born=died - s.r.randint(35, 75), sex="male" if s.r.chance(0.75) else "female",
                                 role="legend", job="chieftain", home=X(site.id))
            s.living.discard(king.id)
            king.died = died
            king.cause = s.folk.cause(s.r.weighted(["old", "battle", "illness"], [4, 4, 2]))
            king.title = s.r.choice(s.data["barrows"]["titles"])[0 if king.sex == "male" else 1]
            king.epithet = s.r.choice(s.data["barrows"]["epithets"]) if s.r.chance(0.7) else ""
            king.buried = X(site.id)
            king.died_at = X(site.id)
            king.fame = s.r.randint(4, 12)
            self.tombs[site.id] = king.id
            s.record("barrow_raised", {"name": king.full_name(), "site": site.name}, importance=2, year=died,
                     sites=[site.id], figures=[king])
            if s.r.chance(0.55):
                s.lore.grave_goods(king, site, year=died)

    def towers_setup(self) -> None:
        """Every lonely tower was raised by a mage: some before the records, some in the years to come."""
        s = self.s
        self.tower_plans: list[tuple[int, int]] = []
        for site in s.w.sites:
            if site.kind != "tower":
                continue
            built = s.r.randint(s.year0 - 400, s.year0 + max(1, s.years // 2))
            if built >= s.year0:
                self.tower_plans.append((built, site.id))
                continue
            mage = self.tower_mage(site, built)
            mage.died = built + s.r.randint(5, 60)
            mage.cause = s.r.choice(s.data["causes"]["vanished"])
            mage.died_at = X(site.id)
            s.living.discard(mage.id)
            s.record("tower_raised", {"mage": mage.name, "site": site.name}, importance=2, year=built,
                     sites=[site.id], figures=[mage])
        self.tower_plans.sort()

    def tower_mage(self, site, built: int):
        s = self.s
        culture = "heartland"
        near = s.land.nearest_standing(site.x, site.y, 10**6)
        if near:
            culture = s.land.spots[near[0][1]].prior
        if culture in ("halfling", "dwarven", "elven"):
            culture = "heartland"
        mage = s.folk.person(culture, born=built - s.r.randint(40, 70), job="mage", role="member",
                             home=X(site.id))
        mage.cls, mage.level = "wizard", s.r.randint(7, 15)
        mage.fame = s.r.randint(3, 9)
        self.towers[site.id] = mage.id
        return mage

    def towers_year(self) -> None:
        s = self.s
        while self.tower_plans and self.tower_plans[0][0] <= s.year:
            _, site_id = self.tower_plans.pop(0)
            site = s.w.sites[site_id]
            if not self.site_free(site):
                continue
            mage = self.tower_mage(site, s.year)
            s.record("tower_raised", {"mage": mage.name, "site": site.name}, importance=2, sites=[site.id],
                     figures=[mage])
            s.orders.mage_rose(mage, site)

    def elder_ruins(self) -> None:
        """The ruins that were already ruins when the records began."""
        s = self.s
        data = s.data["elder_ruins"]
        for site in s.w.sites:
            if site.kind != "ruin":
                continue
            fell = s.year0 - s.r.randint(60, 1500)
            was = s.r.choice(data["was"])
            people = s.r.choice(data["peoples"])
            cause = s.r.choice(data["causes"])
            self.elder[site.id] = {"year": fell, "cause": cause, "was": was, "people": people, "elder": True}
            if s.r.chance(0.35):
                s.record("elder_fall", {"site": site.name, "was": was, "people": people, "cause": cause},
                         importance=3, year=fell, sites=[site.id])

    # ------------------------------------------------------------------ beasts
    def beast_weights(self) -> tuple[list[str], list[float]]:
        types = [t for t, spec in sorted(self.s.data["beasts"].items()) if t != "dragon" and spec.get("weight", 0) > 0]
        return types, [float(self.s.data["beasts"][t]["weight"]) for t in types]

    def new_beast(self, btype: str, *, born: int | None = None, quiet: bool = False, lair=None):
        s = self.s
        spec = s.data["beasts"][btype]
        if lair is None:
            # A beast makes its home within reach of people and their cattle (but not on their doorstep).
            reach = float(spec["range"])
            near_people = {site.id for site in s.w.sites
                           if any(4 <= d <= reach for d, _ in s.land.nearest_standing(site.x, site.y, reach))}
            for biomes in (spec.get("biomes"), None):
                options = [site for site in s.w.sites if site.id in near_people and site.kind in spec["lairs"]
                           and site.id not in self.tombs and self.site_free(site)
                           and (not biomes or s.w.biome_ids[int(s.w.biome[site.x, site.y])] in biomes)]
                if options:
                    lair = s.r.choice(options)
                    break
        if lair is None:
            lair = self.lair_for(tuple(spec["lairs"]), biomes=spec.get("biomes"))
            if lair is None:
                lair = self.lair_for(tuple(spec["lairs"]))
        if lair is None:
            return None
        name, epithet = s.words.beast_name(btype)
        dragon = btype == "dragon"
        fig = fx.Figure(id=s.w.next_figure_id, name=name, sex=s.r.choice(["male", "female"]), race=btype,
                        culture="", born=int(born if born is not None else s.year - s.r.randint(5, 40)),
                        role="beast", kind="dragon" if dragon else "beast", creature=spec["creature"],
                        home=X(lair.id), epithet=epithet, fame=s.r.randint(2, 6))
        s.w.next_figure_id += 1
        s.w.figures[fig.id] = fig
        s.living.add(fig.id)
        b = {"id": fig.id, "type": btype, "lair": lair.id, "infamy": 0, "asleep": False,
             "awake_until": s.year + s.r.randint(3, 20), "sleep_until": -1,
             "life": fig.born + s.r.randint(*spec["life"])}
        if dragon:
            b["color"] = s.r.choice(s.t.politics["dragons"]["colors"])
            if s.r.chance(0.5):
                b["asleep"] = True
                b["sleep_until"] = s.year + s.r.randint(5, 60)
        self.beasts[fig.id] = b
        s.record("dragon_came" if dragon else "beast_came",
                 {"beast": self.beast_title(fig), "site": lair.name, "kind": spec["word"]},
                 importance=4 if dragon else 3, sites=[lair.id], figures=[fig],
                 year=s.year if born is None or born >= s.year0 else max(born + 1, s.year0 - s.r.randint(1, 40)))
        return fig

    def beast_title(self, fig) -> str:
        return f"{fig.name} {fig.epithet}".strip()

    def year(self) -> None:
        s = self.s
        self.raids()
        if len([f for f in s.active("tribe")]) < s.per_size("tribes") and s.chance("tribe_rises"):
            areas = self.tribe_areas()
            if areas:
                self.new_tribe(s.r.choice(areas[:4]))
        alive = [hid for hid in sorted(self.beasts) if s.w.figures[hid].alive]
        if len([h for h in alive if self.beasts[h]["type"] != "dragon"]) < s.per_size("beasts") + 2 and \
                s.chance("beast_arrives"):
            self.new_beast(s.r.weighted(*self.beast_weights()))
        if len([h for h in alive if self.beasts[h]["type"] == "dragon"]) < s.per_size("dragons") and \
                s.chance("dragon_arrives"):
            self.new_beast("dragon")
        for hid in alive:
            self.beast_year(s.w.figures[hid], self.beasts[hid])
        self.heroes()
        self.towers_year()

    def beast_year(self, fig, b: dict) -> None:
        s = self.s
        r = s.r
        spec = s.data["beasts"][b["type"]]
        if s.year >= b["life"]:
            e = s.record("beast_died", {"beast": self.beast_title(fig), "site": s.w.sites[b["lair"]].name},
                         importance=2, sites=[b["lair"]], figures=[fig])
            s.folk.die(fig, "old", cause="of great age, alone in its lair", where=X(b["lair"]), cause_event=e,
                       tell=False)
            return
        if b["type"] == "dragon":
            # A dragon wakes for a few years of burning, then sleeps for decades on what it took.
            if b["asleep"]:
                if s.year < b["sleep_until"]:
                    return
                b["asleep"] = False
                b["awake_until"] = s.year + r.randint(2, 12)
                s.record("dragon_wakes", {"dragon": self.beast_title(fig), "site": s.w.sites[b["lair"]].name},
                         importance=4, sites=[b["lair"]], figures=[fig])
            elif s.year > b["awake_until"]:
                b["asleep"] = True
                b["sleep_until"] = s.year + r.randint(15, 90)
                s.record("dragon_sleeps", {"dragon": self.beast_title(fig)}, importance=3, sites=[b["lair"]],
                         figures=[fig])
                return
        if not r.chance(float(spec["attack"])):
            return
        lair = s.w.sites[b["lair"]]
        near = s.land.nearest_standing(lair.x, lair.y, float(spec["range"]))
        if not near:
            return
        d, sid = near[0] if r.chance(0.5) else r.choice(near)
        self.attack(fig, b, s.land.spots[sid])

    def attack(self, fig, b: dict, sp) -> None:
        s = self.s
        r = s.r
        st = s.w.settlements[sp.sid]
        dragon = b["type"] == "dragon"
        values = {"beast": self.beast_title(fig), "dragon": self.beast_title(fig), "place": st.name,
                  "what": s.land.words(sp.sid)}
        s.stat("dragon_attacks" if dragon else "beast_attacks")
        b["infamy"] += 1
        fig.fame += 1
        if dragon and r.chance(0.35) and st.owner >= 0:
            e = s.record("dragon_tribute", values, importance=3, places=[sp.sid], figures=[fig],
                         factions=[s.faction(st.owner)] if s.faction(st.owner) else [])
            s.lore.hoard(fig, b, sp, e, tribute=True)
            return
        lost = s.land.damage(sp, r.uniform(0.2, 0.45) if dragon else r.uniform(0.01, 0.06))
        values["dead"] = dead_text(lost)
        kind = "dragon" if dragon else "beast_attack"
        e = s.record(kind, values, importance=4 if dragon else 2, places=[sp.sid], figures=[fig],
                     factions=[s.faction(st.owner)] if s.faction(st.owner) else [], data={"dead": lost})
        victims = [s.w.figures[h] for h in sorted(s.living) if s.w.figures[h].kind == "person"
                   and s.w.figures[h].home == S(sp.sid) and s.w.figures[h].role != "ruler"]
        if victims and r.chance(0.3 if dragon else 0.18):
            victim = r.choice(victims)
            e["figures"] = list(dict.fromkeys(e["figures"] + [victim.id]))
            b["infamy"] += 2
            cause = r.choice(s.data["causes"]["dragon" if dragon else "beast"]).replace("{beast}", fig.name)
            s.folk.die(victim, "beast", cause=cause, slayer=fig, where=S(sp.sid), cause_event=e, tell=False)
        if dragon:
            s.lore.hoard(fig, b, sp, e)
            if not sp.fated and sp.pop < 120 and r.chance(0.4) and sp.founded is not None and \
                    s.year >= sp.founded + 10:
                s.land.ruin(sp, f"burned by the dragon {fig.name}", kind="burned_down", by=None,
                            values={"by": fig.name}, importance=4)

    # ------------------------------------------------------------------ heroes
    def heroes(self) -> None:
        s = self.s
        r = s.r
        for hid in sorted(self.beasts):
            fig = s.w.figures[hid]
            b = self.beasts[hid]
            if not fig.alive or b["infamy"] < int(s.data["heroes"]["infamy"]):
                continue
            if b["type"] == "dragon" and b["asleep"] and not r.chance(0.3):
                continue
            if not s.chance("hero_goes", 1.0 + b["infamy"] * 0.05):
                continue
            self.hunt(fig, b)
        if s.chance("hero_explores"):
            s.lore.explore()
        self.adventurers()

    def adventurers(self) -> None:
        """Young people set out from the towns to make a name: they go into ruins, hunt down outlaws, grow famous,
        and (the lucky ones) grow old and tell of it in the inns."""
        s = self.s
        r = s.r
        living = [s.w.figures[h] for h in sorted(s.living)]
        heroes = [f for f in living if f.kind == "person" and f.job == "adventurer"]
        if len(heroes) < s.per_size("adventurers") and s.chance("hero_rises"):
            towns = [sp for sp in s.land.standing() if sp.human and sp.kind_now in ("village", "town", "city")]
            if towns:
                sp = r.weighted(towns, [sp.pop for sp in towns])
                hero = s.folk.adult_person(s.w.settlements[sp.sid].culture, age=(17, 26), role="hero",
                                           job="adventurer", home=S(sp.sid))
                classes = s.data["heroes"]["classes"]
                hero.cls = r.weighted([c for c, _ in classes], [float(w) for _, w in classes])
                hero.level = r.randint(1, 3)
        for hero in heroes:
            if not hero.alive or s.folk.eq_age(hero) > 48 or not r.chance(0.12):
                continue
            gangs = [g for g in s.active("bandit_gang") if 0 <= g.site < len(s.w.sites)]
            if gangs and r.chance(0.5):
                gang = r.choice(gangs)
                site = s.w.sites[gang.site]
                if hero.level + r.gauss(0, 3) > 5:
                    hero.level = min(20, hero.level + 1)
                    hero.fame += 2
                    e = s.record("outlaws_hunted", {"hero": hero.full_name(), "gang": gang.name, "site": site.name},
                                 importance=2, figures=[hero], factions=[gang], sites=[site.id])
                    leader = s.leader(gang)
                    if leader is not None and r.chance(0.5):
                        s.folk.die(leader, "battle", cause=f"at the hands of {hero.full_name()}", slayer=hero,
                                   where=X(site.id), cause_event=e, tell=False)
                else:
                    e = s.record("hero_fell_outlaws", {"hero": hero.full_name(), "gang": gang.name,
                                                       "site": site.name}, importance=1, figures=[hero],
                                 factions=[gang], sites=[site.id])
                    s.folk.die(hero, "battle", cause=f"at the hands of {gang.name}", where=X(site.id),
                               cause_event=e, tell=False)
            else:
                s.lore.explore(hero)

    def find_hero(self, near_xy, *, local_lord=None):
        """A hero to answer the call: a wandering adventurer nearby, a lord's knight, or someone new."""
        s = self.s
        folk = s.folk
        best = None
        for hid in sorted(s.living):
            fig = s.w.figures[hid]
            if fig.kind != "person" or fig.job not in ("hero", "adventurer", "knight") or not folk.is_adult(fig) \
                    or folk.eq_age(fig) > 52:
                continue
            if fig.job == "knight" and (local_lord is None or fig.faction != local_lord.id):
                continue
            if fig.home.startswith("S"):
                sp = s.land.spots[int(fig.home[1:])]
                d = math.hypot(sp.x - near_xy[0], sp.y - near_xy[1])
            else:
                d = 60.0
            if d <= 45 and (best is None or (fig.level, fig.fame, -fig.id) > best[0]):
                best = ((fig.level, fig.fame, -fig.id), fig)
        if best is not None and s.r.chance(0.7):
            return best[1]
        near = s.land.nearest_standing(near_xy[0], near_xy[1], 40, test=lambda sp: sp.human)
        if not near:
            return None
        sid = s.r.weighted([sid for _, sid in near], [s.land.spots[sid].pop for _, sid in near])  # towns breed them
        culture = s.w.settlements[sid].culture
        hero = folk.adult_person(culture, age=(18, 32), role="hero", job="adventurer", home=S(sid))
        classes = s.data["heroes"]["classes"]
        hero.cls = s.r.weighted([c for c, _ in classes], [float(w) for _, w in classes])
        hero.level = s.r.randint(3, 6) + s.r.randint(0, 3)
        hero.fame = 1
        return hero

    def hunt(self, beast, b: dict) -> None:
        s = self.s
        r = s.r
        spec = s.data["beasts"][b["type"]]
        lair = s.w.sites[b["lair"]]
        lords = s.land.nearest_standing(lair.x, lair.y, 40)
        lord = None
        if lords:
            owner = s.faction(s.w.settlements[lords[0][1]].owner)
            lord = s.top(owner) if owner is not None else None
        hero = self.find_hero((lair.x, lair.y), local_lord=lord)
        if hero is None:
            return
        if b["type"] == "dragon" and hero.level < 8 and not r.chance(0.15):
            return  # nobody sane goes after a dragon without a great name behind them
        band = r.chance(0.45)
        power = hero.level + (4.0 if band else 0) + s.lore.might(hero) + r.gauss(0, 3.0)
        foe = float(spec["power"]) + min(3.0, b["infamy"] * 0.1) + r.gauss(0, 2.0)
        values = {"hero": hero.full_name(), "beast": self.beast_title(beast), "site": lair.name,
                  "kind": spec["word"], "band": " and a band of companions" if band else ""}
        if power > foe:
            e = s.record("dragon_slain" if b["type"] == "dragon" else "beast_slain",
                         {**values, "legend": hero.full_name(), "dragon": self.beast_title(beast)},
                         importance=5 if b["type"] == "dragon" else 3, sites=[lair.id], figures=[hero, beast])
            s.folk.die(beast, "beast", cause=f"slain by {hero.full_name()}", slayer=hero, where=X(lair.id),
                       cause_event=e, tell=False)
            hero.level = min(20, hero.level + r.randint(1, 3))
            hero.fame += 6 if b["type"] == "dragon" else 3
            hero.fame += b["infamy"] // 2
            if not hero.epithet and spec.get("slayer"):
                hero.epithet = r.choice(spec["slayer"])
            hero.notes.append(f"slew {self.beast_title(beast)}")
            s.lore.recover(hero, lair, e)
            s.stat("heroes")
            if lord is not None and lord.kind == "kingdom" and hero.job == "adventurer" and r.chance(0.35):
                hero.job = "knight"
                s.folk.move(hero, lord)
                s.record("knighted", {"hero": hero.full_name(), "realm": lord.name}, importance=2,
                         factions=[lord], figures=[hero])
        else:
            e = s.record("hero_fell", values, importance=3 if hero.fame >= 5 else 2, sites=[lair.id],
                         figures=[hero, beast])
            b["infamy"] += 2
            beast.fame += 2
            s.folk.die(hero, "beast", cause=f"in {lair.name}, at the claws of {beast.name}", slayer=beast,
                       where=X(lair.id), cause_event=e, tell=False)

    # ------------------------------------------------------------------ the dead and their barrows
    def bury(self, fig) -> None:
        """A great one dies at home: if a barrow nearby is empty, they are laid in it with honour."""
        s = self.s
        if fig.kind != "person" or not fig.home.startswith("S") or fig.fame < 8:
            return
        sp = s.land.spots[int(fig.home[1:])]
        options = [site for site in s.w.sites if site.kind == "barrow" and site.id not in self.tombs
                   and math.hypot(site.x - sp.x, site.y - sp.y) <= 30 and self.site_free(site)]
        if not options or not s.r.chance(0.6):
            return
        site = min(options, key=lambda x: (math.hypot(x.x - sp.x, x.y - sp.y), x.id))
        self.tombs[site.id] = fig.id
        fig.buried = X(site.id)
        s.record("laid_to_rest", {"name": fig.full_name(), "site": site.name}, importance=2, sites=[site.id],
                 figures=[fig])
        s.lore.grave_goods(fig, site)

    # ------------------------------------------------------------------ raids
    def raids(self) -> None:
        s = self.s
        r = s.r
        for t in s.active("tribe"):
            if not s.chance("tribe_raid"):
                continue
            home = s.anchor(t)
            if home is None:
                continue
            targets = [s.land.spots[sid] for _, sid in s.land.nearest_standing(
                home[0], home[1], 30, test=lambda sp: sp.human and sp.kind_now in ("hamlet", "village"))]
            if not targets:
                continue
            sp = r.choice(targets)
            st = s.w.settlements[sp.sid]
            realm = s.top(s.faction(st.owner)) if st.owner >= 0 else None
            burned = sp.kind_now == "hamlet" and r.chance(0.25)
            lost = s.land.damage(sp, 0.5 if burned else r.uniform(0.05, 0.15))
            values = {"tribe": t.name, "place": st.name, "dead": dead_text(lost)}
            if burned and not sp.fated and sp.founded is not None and s.year >= sp.founded + 8:
                e = s.record("burned", values, importance=3, places=[sp.sid], factions=[t] + ([realm] if realm else []))
                s.land.ruin(sp, f"burned by {t.name}", event=e, by=t)
            else:
                e = s.record("burned" if burned else "raid", values,
                             importance=3 if burned else 2 if lost >= 30 else 1, places=[sp.sid],
                             factions=[t] + ([realm] if realm else []))
                self.abduct(t, sp, e)
            if realm is not None:
                s.realms.change_relation(t, realm, -8)
            t.military += r.randint(1, 4)
            s.stat("raids")

    def abduct(self, tribe, sp, e: dict) -> None:
        s = self.s
        r = s.r
        if not r.chance(0.12):
            return
        young = [s.w.figures[h] for h in sorted(s.living) if s.w.figures[h].kind == "person"
                 and s.w.figures[h].home == S(sp.sid) and s.folk.eq_age(s.w.figures[h]) < 14]
        if not young:
            return
        child = r.choice(young)
        family = s.faction(child.faction)
        s.folk.move(child, tribe)
        child.job = "captive"
        child.role = "member"
        child.home = X(tribe.site) if tribe.site >= 0 else ""
        e["figures"] = list(dict.fromkeys(e["figures"] + [child.id]))
        s.record("abducted", {"child": child.full_name(), "tribe": tribe.name,
                              "family": family.name if family is not None else "their family"},
                 importance=2, figures=[child], factions=[tribe] + ([family] if family else []), places=[sp.sid])
        if family is not None and family.active:
            s.realms.heir_of(family)  # a child carried off is no longer anyone's heir

    # ------------------------------------------------------------------ doom
    def doom(self, sp) -> None:
        """A doomed place's year has come: it ends by whatever is near."""
        s = self.s
        r = s.r
        st = s.w.settlements[sp.sid]
        owner = s.faction(st.owner)
        top = s.top(owner) if owner is not None else None
        if top is not None:
            for war in s.war.active_wars():
                sides = s.war.sides(war)
                if top.id in sides[0] or top.id in sides[1]:
                    enemy_id = war["defender"] if top.id in sides[0] else war["attacker"]
                    enemy = s.faction(enemy_id)
                    there = s.anchor(enemy) if enemy is not None else None
                    if enemy is not None and there is not None and math.hypot(there[0] - sp.x, there[1] - sp.y) < 55:
                        name = s.words.battle_name(st.name, "siege")
                        values = {"attacker": enemy.name, "defender": top.name, "place": st.name, "siege": name,
                                  "dead": dead_text(int(sp.pop * 0.4)), "what": s.land.words(sp.sid),
                                  "war": war["name"]}
                        e = s.record("razed", values, importance=4, factions=[enemy, top], places=[sp.sid], war=war)
                        s.war.massacre(sp, e, war, 0.35)
                        s.land.ruin(sp, f"razed by {enemy.name} in {war['name']}", event=e, by=enemy)
                        return
        for t in s.active("tribe"):
            there = s.anchor(t)
            if there is not None and math.hypot(there[0] - sp.x, there[1] - sp.y) < 38:
                e = s.record("burned", {"tribe": t.name, "place": st.name, "dead": dead_text(int(sp.pop * 0.3))},
                             importance=3, places=[sp.sid], factions=[t] + ([top] if top else []))
                s.war.massacre(sp, e, None, 0.25)
                s.land.ruin(sp, f"burned by {t.name}", event=e, by=t)
                return
        for hid in sorted(self.beasts):
            fig = s.w.figures[hid]
            b = self.beasts[hid]
            lair = s.w.sites[b["lair"]]
            if fig.alive and math.hypot(lair.x - sp.x, lair.y - sp.y) < 26:
                values = {"beast": self.beast_title(fig), "place": st.name, "what": s.land.words(sp.sid)}
                e = s.record("beast_destroyed", values, importance=4 if b["type"] == "dragon" else 3,
                             places=[sp.sid], figures=[fig])
                b["infamy"] += 3
                s.war.massacre(sp, e, None, 0.3)
                s.land.ruin(sp, f"destroyed by {fig.name}", event=e, kind="beast_destroyed")
                return
        causes = s.data["abandoned"]["hold" if sp.destiny == "hold" else "town"]
        cause = r.choice(causes)
        e = s.record("abandoned", {"place": st.name, "cause": cause, "what": s.land.words(sp.sid)}, importance=3,
                     places=[sp.sid], factions=[top] if top else [])
        s.land.ruin(sp, cause, event=e, kind="abandoned")
