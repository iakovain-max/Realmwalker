"""Lore of the ages: artifacts that pass from hand to hand, and the songs and chronicles written about it all.

An artifact is made by a named smith for a ruler, a hero or a church. From then on it is always somewhere: in
someone's hands, in a town (a treasury, a temple), or lying in a site (a ruin, a barrow, a lair). It is inherited,
taken from the dead by whoever killed them, looted when a town falls, carried off by a dragon, buried with its
owner, stolen, found again by a hero. Each move is written into its story.

Works are what bards, chroniclers and scholars made of the great events: a ballad of the hero who slew the troll, a
lament for the burned town, a chronicle of a kingdom's kings.
"""

from __future__ import annotations

from realmwalker.world.ages.sim import S, X

WEAPONS = ("sword", "spear", "axe", "bow", "hammer")


class Lore:
    def __init__(self, sim) -> None:
        self.s = sim
        self.items: list[dict] = []
        self.works: list[dict] = []
        self.pending: list[tuple[int, int]] = []  # (artifact index, faction id): to go to whoever rules next

    # ------------------------------------------------------------------ making
    def setup(self) -> None:
        s = self.s
        for _ in range(s.per_size("old_artifacts")):
            sites = [x for x in s.w.sites if x.kind in ("ruin", "barrow", "cave", "tower")]
            if not sites:
                return
            site = s.r.choice(sites)
            year = s.year0 - s.r.randint(50, 800)
            a = self.make(None, year=year, quiet=True)
            a["place"] = X(site.id)
            a["fate"] = s.r.choice(s.data["artifacts"]["old_fates"]).replace("{site}", site.name)
            s.record("artifact_lost_old", {"artifact": a["name"], "site": site.name, "fate": a["fate"]},
                     importance=3, year=year + s.r.randint(10, 200), sites=[site.id], data={"artifact": a["id"]})

    def make(self, owner, *, kind: str | None = None, maker=None, year: int | None = None, quiet: bool = False,
             why: str = "") -> dict:
        s = self.s
        r = s.r
        spec = s.data["artifacts"]
        kinds = sorted(spec["kinds"])
        if kind is None:
            kind = r.weighted(kinds, [float(spec["kinds"][k]["weight"]) for k in kinds])
        culture = owner.culture if owner is not None and owner.culture else "heartland"
        if maker is None and owner is not None:
            dwarf = r.chance(0.35)
            maker_culture = "dwarven" if dwarf else culture if culture not in ("orcish",) else "heartland"
            home = owner.home if owner.home.startswith("S") else ""
            maker = s.folk.adult_person(maker_culture, age=(35, 65), role="member", job="smith", home=home)
            maker.fame += 3
        material = r.choice(spec["kinds"][kind]["materials"])
        name = s.words.artifact_name(kind, culture)
        a = {"id": len(self.items), "name": name, "kind": kind, "material": material,
             "maker": maker.id if maker is not None else -1, "made": int(s.year if year is None else year),
             "holder": owner.id if owner is not None else -1, "place": "", "bearer": owner.id if owner else -1,
             "story": [], "fate": "", "found": False}
        self.items.append(a)
        if owner is not None:
            owner.fame += 2
        if not quiet and owner is not None:
            e = s.record("artifact_made", {"artifact": name, "maker": maker.full_name() if maker else "a master",
                                           "owner": owner.full_name(), "material": material,
                                           "why": why or "at their command"},
                         importance=3, figures=[owner] + ([maker] if maker is not None else []),
                         data={"artifact": a["id"]})
            a["story"].append(e["id"])
        return a

    def held_by(self, fig) -> list[dict]:
        return [a for a in self.items if a["holder"] == fig.id]

    def lying_at(self, ref: str) -> list[dict]:
        return [a for a in self.items if a["holder"] < 0 and a["place"] == ref]

    def move(self, a: dict, *, holder=None, place: str = "", event: dict | None = None, fate: str = "") -> None:
        a["holder"] = holder.id if holder is not None else -1
        a["place"] = "" if holder is not None else place
        if fate:
            a["fate"] = fate
        if event is not None:
            a["story"].append(event["id"])
            event.setdefault("data", {}).setdefault("artifacts", []).append(a["id"])

    def might(self, fig) -> float:
        return 2.0 * sum(1 for a in self.held_by(fig) if a["kind"] in WEAPONS + ("shield", "armour"))

    # ------------------------------------------------------------------ the year
    def year(self) -> None:
        s = self.s
        for idx, fid in list(self.pending):
            f = s.faction(fid)
            a = self.items[idx]
            if f is None:
                self.pending.remove((idx, fid))
                continue
            heir = s.leader(f)
            if heir is not None:
                self.pending.remove((idx, fid))
                self.move(a, holder=heir, fate=f"passed to {heir.full_name()}")
        for f in s.active("kingdom", "clan", "elven_realm", "temple", "noble_house"):
            ruler = s.leader(f)
            if ruler is None or not s.chance("artifact", 2.0 if f.kind == "kingdom" else 1.0):
                continue
            kind = "relic" if f.kind == "temple" else None
            self.make(ruler, kind=kind, why=s.r.choice(s.data["artifacts"]["why"]))
        if s.chance("theft"):
            self.theft()
        for k in s.active("kingdom"):
            if s.chance("chronicle"):
                self.chronicle(k)

    def theft(self) -> None:
        s = self.s
        r = s.r
        held = [a for a in self.items if a["holder"] >= 0 and s.w.figures[a["holder"]].alive
                and s.w.figures[a["holder"]].home.startswith("S")]
        if not held:
            return
        a = r.choice(held)
        owner = s.w.figures[a["holder"]]
        home = int(owner.home[1:])
        thieves = s.active("thieves_guild")
        guild = r.choice(thieves) if thieves and r.chance(0.6) else None
        thief = s.folk.adult_person(s.w.settlements[home].culture, age=(18, 40), role="member", job="thief",
                                    faction=guild, home=S(home))
        caught = r.chance(0.35)
        e = s.record("artifact_stolen", {"artifact": a["name"], "owner": owner.full_name(), "thief": thief.full_name(),
                                         "place": s.place_name(home)}, importance=2 if not caught else 1,
                     figures=[owner, thief], places=[home], factions=[guild] if guild else [])
        if caught:
            s.folk.die(thief, "executed", cause_event=e, tell=False)
            e["text"] += " " + s.words.text("thief_caught", {"thief": thief.name})
            return
        self.move(a, holder=thief, event=e, fate=f"was stolen by {thief.full_name()}")
        hideouts = [x for x in s.w.sites if x.kind in ("cave", "ruin") and abs(x.x - s.w.settlements[home].x) +
                    abs(x.y - s.w.settlements[home].y) < 30 and x.id not in s.wild.tombs]
        if hideouts and r.chance(0.5):
            site = r.choice(hideouts)
            self.move(a, place=X(site.id), fate=f"was hidden by a thief in {site.name}, who never came back for it")

    # ------------------------------------------------------------------ deaths, battles, sacks, dragons
    def on_death(self, fig, slayer) -> None:
        s = self.s
        r = s.r
        for a in self.held_by(fig):
            if slayer is not None and slayer.kind == "person" and slayer.alive and r.chance(0.6):
                self.move(a, holder=slayer, fate=f"was taken from {fig.full_name()} by {slayer.full_name()}")
            elif slayer is not None and slayer.kind in ("beast", "dragon"):
                self.move(a, place=slayer.home, fate=f"lies where {fig.full_name()} fell, in the lair of {slayer.name}")
            elif slayer is not None:
                where = fig.died_at or fig.home
                self.move(a, place=where, fate=f"was lost when {fig.full_name()} fell")
            else:
                f = s.faction(fig.faction)
                if fig.role == "ruler" and f is not None and fig.id == f.leader:
                    a["holder"] = -1
                    a["place"] = fig.home
                    self.pending.append((a["id"], f.id))
                    continue
                kids = [k for k in s.folk.children(fig) if k.kind == "person"]
                if kids:
                    heir = min(kids, key=lambda k: k.born)
                    self.move(a, holder=heir, fate=f"passed to {heir.full_name()}")
                else:
                    self.move(a, place=fig.home, fate=f"was left in {s.place_name(int(fig.home[1:]))} when "
                              f"{fig.full_name()} died" if fig.home.startswith("S") else "was lost")

    def battle(self, e: dict, win_host: list, lose_host: list) -> None:
        pass  # what the fallen carried goes where on_death sends it

    def looted(self, sp, winner, e: dict) -> None:
        s = self.s
        leader = s.leader(winner)
        for a in self.lying_at(S(sp.sid)):
            if leader is not None:
                self.move(a, holder=leader, event=e, fate=f"was carried off when {winner.name} took "
                                                         f"{s.place_name(sp.sid)}")

    def place_lost(self, sp, e: dict) -> None:
        for a in self.lying_at(S(sp.sid)):
            self.move(a, place=S(sp.sid), event=e, fate=f"was lost in the fall of {self.s.place_name(sp.sid)}")

    def hoard(self, dragon, b: dict, sp, e: dict, *, tribute: bool = False) -> None:
        s = self.s
        lair = s.w.sites[b["lair"]]
        for a in self.lying_at(S(sp.sid)):
            if s.r.chance(0.5):
                how = "was given up as tribute to" if tribute else "was carried off by"
                self.move(a, place=X(lair.id), event=e, fate=f"{how} the dragon {dragon.name}, and lies in its hoard "
                                                            f"in {lair.name}")

    def recover(self, hero, lair, e: dict) -> None:
        here = self.lying_at(X(lair.id))
        if here:
            a = self.s.r.choice(here)
            self.move(a, holder=hero, event=e, fate=f"was brought out of {lair.name} by {hero.full_name()}")

    def explore(self, hero=None) -> None:
        """A hero goes into a ruin or a barrow and comes out with something old (or does not come out)."""
        s = self.s
        options = [a for a in self.items if a["holder"] < 0 and a["place"].startswith("X")]
        options = [a for a in options if s.wild.lair_holder(int(a["place"][1:])) is None]
        if hero is not None and hero.home.startswith("S"):
            sp = s.land.spots[int(hero.home[1:])]
            options = [a for a in options if abs(s.w.sites[int(a["place"][1:])].x - sp.x) +
                       abs(s.w.sites[int(a["place"][1:])].y - sp.y) <= 50]
        if not options:
            return
        a = s.r.choice(options)
        site = s.w.sites[int(a["place"][1:])]
        hero = hero or s.wild.find_hero((site.x, site.y))
        if hero is None:
            return
        if s.r.random() < 0.4 - hero.level * 0.03:
            e = s.record("hero_lost", {"hero": hero.full_name(), "site": site.name}, importance=2, sites=[site.id],
                         figures=[hero])
            s.folk.die(hero, "accident", cause=f"in {site.name}, and was never found", where=X(site.id),
                       cause_event=e, tell=False)
            return
        e = s.record("artifact_found", {"hero": hero.full_name(), "artifact": a["name"], "site": site.name},
                     importance=3, sites=[site.id], figures=[hero], data={"artifact": a["id"]})
        hero.fame += 3
        hero.level = min(20, hero.level + 1)
        hero.notes.append(f"found {a['name']} in {site.name}")
        self.move(a, holder=hero, event=e, fate=f"was found in {site.name} by {hero.full_name()}")

    def grave_goods(self, fig, site, year: int | None = None) -> None:
        """Laid in a barrow with what was theirs (or with something made for the grave)."""
        s = self.s
        mine = self.held_by(fig) + [a for a in self.items if a["holder"] < 0 and a["place"] == fig.home
                                   and a.get("bearer") == fig.id]
        if not mine and s.r.chance(0.5):
            mine = [self.make(fig, year=year, quiet=True)]
        for a in mine:
            self.move(a, place=X(site.id), fate=f"was buried with {fig.full_name()} in {site.name}")
            self.pending = [(i, f) for i, f in self.pending if i != a["id"]]

    # ------------------------------------------------------------------ works
    def author(self, job: str, near_sid: int | None):
        s = self.s
        culture = s.w.settlements[near_sid].culture if near_sid is not None else "heartland"
        if culture in ("orcish",):
            culture = "heartland"
        fig = s.folk.adult_person(culture, age=(22, 60), role="member", job=job,
                                  home=S(near_sid) if near_sid is not None else "")
        fig.fame += 2
        return fig

    def compose(self, form: str, about: dict, *, place: int | None, **values) -> dict | None:
        s = self.s
        spec = s.data["works"]["forms"][form]
        author = self.author(spec["author"], place)
        title = s.words.work_title(form, **values)
        work = {"id": len(self.works), "title": title, "form": form, "author": author.id, "year": s.year,
                "about": about, "place": S(place) if place is not None else ""}
        self.works.append(work)
        s.record("work_written", {"author": author.full_name(), "title": title, "form": spec["word"]}, importance=1,
                 figures=[author], places=[place] if place is not None else [], data={"work": work["id"]})
        return work

    def war_song(self, war: dict, winner) -> None:
        s = self.s
        if war["battles"] < 2 or not s.r.chance(0.45):
            return
        side = winner if winner is not None else s.faction(war["defender"])
        place = side.seat if side is not None and side.seat >= 0 and s.land.spots[side.seat].standing else None
        self.compose(s.r.choice(["ballad", "epic"]), {"war": war["id"]}, place=place, war=war["name"],
                     subject=war["name"])

    def song_of(self, event: dict, hero=None, place: int | None = None, form: str = "ballad") -> None:
        s = self.s
        if hero is not None:
            self.compose(form, {"event": event["id"], "figure": hero.id}, place=place, subject=hero.full_name(),
                         hero=hero.first_name)
        else:
            self.compose(form, {"event": event["id"]}, place=place, subject=s.place_name(place) if place is not None
                         else "the old days")

    def chronicle(self, realm) -> None:
        s = self.s
        place = realm.seat if realm.seat >= 0 and s.land.spots[realm.seat].standing else None
        self.compose("chronicle", {"faction": realm.id}, place=place, subject=realm.name, realm=realm.name)
