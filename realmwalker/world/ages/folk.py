"""The folk of the ages: people of note, born, married and buried.

Only the people a chronicler would know are figures: the families of rulers and lords, knights and captains, priests,
mages, smiths and bards, heroes and villains, and the beasts they fight. Common folk are numbers in a settlement.

Ruling families are real families: the ruler and the heir marry (often into another house, which binds the two
houses together) and have children; children grow up to be knights, priests and scholars, marry out, and are there
to claim a throne when the line falters. Names run in families, and a throne counts its kings (Aldric III).
"""

from __future__ import annotations

from realmwalker.world import factions as fx
from realmwalker.world.ages.sim import DYNASTIC, S

LINE_ROLES = ("ruler", "heir")


class Folk:
    def __init__(self, sim) -> None:
        self.s = sim
        self.cultures = sim.t.names["cultures"]
        pol = sim.t.politics
        self.lifespan = pol["lifespan"]
        m = pol["mortality"]
        self.base, self.from_age, self.doubling = float(m["base"]), float(m["from_age"]), float(m["doubling_years"])
        self.f = sim.data["folk"]
        self.traits = sorted(sim.t.people["personality"])
        self.kids: dict[int, list[int]] = {}  # parent id -> children ids, oldest first
        self.regnal: dict[tuple[int, str], int] = {}  # (realm id, first name) -> how many have reigned by it

    # ------------------------------------------------------------------ ages
    def span(self, race: str) -> float:
        return float(self.lifespan.get(race, 1.0))

    def adult_age(self, race: str) -> int:
        return int(self.f["adult"] * self.span(race))

    def is_adult(self, fig) -> bool:
        return fig.age(self.s.year) >= self.adult_age(fig.race)

    def eq_age(self, fig) -> float:
        """Age as a human would count it (a dwarf of 140 is like a man of 40)."""
        return fig.age(self.s.year) / self.span(fig.race)

    def death_rate(self, fig) -> float:
        eq = self.eq_age(fig)
        if eq < 12:
            return float(self.f["child_death"])
        return min(0.9, self.base * 2 ** ((eq - self.from_age) / self.doubling))

    # ------------------------------------------------------------------ making people
    def first_name(self, culture: str, sex: str, avoid=()) -> str:
        names = (self.cultures.get(culture) or self.cultures["heartland"])[sex]
        first = self.s.r.choice(names)
        for _ in range(6):
            if first not in avoid:
                break
            first = self.s.r.choice(names)
        return first

    def family_name(self, culture: str) -> str:
        """A family name for someone new: not one of the ruling houses' (a commoner called Grimstad would be taken
        for a prince)."""
        names = (self.cultures.get(culture) or self.cultures["heartland"])["family"]
        houses = self.s.fm.__dict__.get("used_families", set())
        options = [n for n in names if n not in houses] or names
        return self.s.r.choice(options)

    def person(self, culture: str, *, born: int, sex: str | None = None, family: str | None = None,
               race: str | None = None, faction=None, role: str = "member", job: str = "", home: str = "",
               mother: int = -1, father: int = -1, first: str | None = None, title: str = "") -> fx.Figure:
        s = self.s
        w = s.w
        r = s.r
        sex = sex or r.choice(["male", "female"])
        first = first or self.first_name(culture, sex)
        family = family if family is not None else self.family_name(culture)
        traits = r.sample(self.traits, 2)
        fig = fx.Figure(id=w.next_figure_id, name=f"{first} {family}".strip(), sex=sex,
                        race=race or fx.CULTURE_RACE.get(culture, "human"), culture=culture, born=int(born),
                        faction=faction.id if faction is not None else -1, title=title, role=role, traits=traits,
                        mother=mother, father=father, home=home, job=job)
        w.next_figure_id += 1
        w.figures[fig.id] = fig
        if faction is not None:
            faction.members.append(fig.id)
        s.living.add(fig.id)
        for p in (mother, father):
            if p >= 0:
                self.kids.setdefault(p, []).append(fig.id)
        return fig

    def adult_person(self, culture: str, *, age: tuple[int, int] = (20, 45), **kw) -> fx.Figure:
        race = kw.get("race") or fx.CULTURE_RACE.get(culture, "human")
        span = self.span(race)
        born = self.s.year - int(self.s.r.randint(*age) * span)
        return self.person(culture, born=born, **kw)

    def move(self, fig, faction) -> None:
        old = self.s.w.factions.get(fig.faction)
        if old is not None and fig.id in old.members:
            old.members.remove(fig.id)
        fig.faction = faction.id if faction is not None else -1
        if faction is not None and fig.id not in faction.members:
            faction.members.append(fig.id)
        if faction is not None and faction.seat >= 0:
            fig.home = S(faction.seat)

    # ------------------------------------------------------------------ kin
    def children(self, fig, *, living: bool = True) -> list:
        figs = self.s.w.figures
        out = [figs[k] for k in self.kids.get(fig.id, ())]
        return [k for k in out if k.alive] if living else out

    def siblings(self, fig, *, living: bool = True) -> list:
        figs = self.s.w.figures
        seen = set()
        out = []
        for p in (fig.father, fig.mother):
            for k in self.kids.get(p, ()):
                if k != fig.id and k not in seen:
                    seen.add(k)
                    out.append(figs[k])
        out.sort(key=lambda k: k.born)
        return [k for k in out if k.alive] if living else out

    def close_kin(self, a, b) -> bool:
        if a.id in (b.father, b.mother) or b.id in (a.father, a.mother):
            return True
        parents_a = {p for p in (a.father, a.mother) if p >= 0}
        parents_b = {p for p in (b.father, b.mother) if p >= 0}
        return bool(parents_a & parents_b)

    def is_line(self, fig) -> bool:
        """The ruler or heir of a house: their marriages and children are the house's future."""
        if fig.role not in LINE_ROLES:
            return False
        f = self.s.faction(fig.faction)
        return f is not None and f.kind in DYNASTIC

    # ------------------------------------------------------------------ the year
    def year(self) -> None:
        s = self.s
        r = s.r
        figs = s.w.figures
        dying = []
        for hid in sorted(s.living):
            fig = figs[hid]
            if fig.kind == "person" and r.random() < self.death_rate(fig):
                dying.append(fig)
        for fig in dying:
            if fig.alive:
                self.die(fig, self.natural_cause(fig))
        self.marriages()
        self.births()
        self.coming_of_age()

    def natural_cause(self, fig) -> str:
        r = self.s.r
        eq = self.eq_age(fig)
        if eq < 12:
            return "child"
        if eq >= 62:
            return r.weighted(["old", "illness", "accident"], [6, 3, 1])
        options, weights = ["illness", "accident", "murder"], [5, 3, 0.6]
        if fig.sex == "female" and 17 <= eq <= 42 and self.kids.get(fig.id):
            options.append("childbed")
            weights.append(1.5)
        return r.weighted(options, weights)

    def cause(self, kind: str) -> str:
        causes = self.s.data["causes"].get(kind) or self.s.t.politics["causes"].get(kind) or ["of a fever"]
        return self.s.r.choice(causes)

    # ------------------------------------------------------------------ marriages
    def marriages(self) -> None:
        s = self.s
        r = s.r
        figs = s.w.figures
        singles: dict[tuple[str, str], list] = {}
        seekers = []
        for hid in sorted(s.living):
            fig = figs[hid]
            if fig.kind != "person" or fig.job in ("priest", "mage") or not self.in_family(fig):
                continue
            if fig.spouse >= 0 and figs[fig.spouse].alive:
                continue
            eq = self.eq_age(fig)
            if not 16 <= eq <= 48:
                continue
            singles.setdefault((fig.race, fig.sex), []).append(fig)
            want = float(self.f["marry"]) * (1.6 if self.is_line(fig) else 1.0)
            if eq <= 40 and r.chance(want):
                seekers.append(fig)
        wed: set[int] = set()
        for fig in seekers:
            if fig.id in wed:
                continue
            other_sex = "female" if fig.sex == "male" else "male"
            partner = None
            if r.chance(float(self.f["alliance_marriage"])):
                pool = [p for p in singles.get((fig.race, other_sex), ())
                        if p.id not in wed and p.faction != fig.faction and not self.close_kin(fig, p)
                        and not (self.is_line(p) and self.is_line(fig))
                        and abs(self.eq_age(p) - self.eq_age(fig)) <= 15]
                if pool:
                    weights = [3.0 if p.culture == fig.culture else 1.0 for p in pool]
                    partner = r.weighted(pool, weights)
            if partner is None:
                f = s.faction(fig.faction)
                span = self.span(fig.race)
                age = max(self.f["adult"], self.eq_age(fig) + r.randint(-6, 4))
                partner = self.person(fig.culture, born=s.year - int(age * span), sex=other_sex, race=fig.race,
                                      faction=f, role="spouse", home=fig.home)
            self.marry(fig, partner)
            wed.update((fig.id, partner.id))

    def in_family(self, fig) -> bool:
        """A member of a ruling family: the line, and its children and siblings who live with the house."""
        f = self.s.faction(fig.faction)
        if f is None or f.kind not in DYNASTIC:
            return False
        family = self.s.realms.family_of(f)
        return bool(family) and fig.name.endswith(" " + family) or fig.role in LINE_ROLES

    def marry(self, a, b) -> None:
        s = self.s
        a.spouse, b.spouse = b.id, a.id
        fa, fb = s.faction(a.faction), s.faction(b.faction)
        line_a, line_b = self.is_line(a), self.is_line(b)
        if line_a and not line_b:
            mover, stayer = b, a
        elif line_b and not line_a:
            mover, stayer = a, b
        else:
            mover, stayer = (a, b) if a.sex == "female" else (b, a)
        moved_from = s.faction(mover.faction)
        if mover.faction != stayer.faction:
            self.move(mover, s.faction(stayer.faction))
        if b.role == "spouse" or a.role == "spouse":
            pass
        elif mover.role == "member":
            mover.role = "spouse"
        important = line_a or line_b
        if fa is not None and fb is not None and fa is not fb:
            s.realms.change_relation(fa, fb, float(self.f["marriage_bond"]))
        if important:
            home = s.faction(stayer.faction)
            kingly = home is not None and home.kind in ("kingdom", "elven_realm", "clan")
            s.record("wedding", {"a": stayer.full_name(), "b": mover.full_name(),
                                 "from": moved_from.name if moved_from is not None and moved_from is not home
                                 else "a good family"},
                     importance=2 if kingly else 1, figures=[stayer, mover],
                     factions=[f for f in (home, moved_from) if f is not None],
                     places=[int(stayer.home[1:])] if stayer.home.startswith("S") else [])

    # ------------------------------------------------------------------ births
    def births(self) -> None:
        s = self.s
        r = s.r
        figs = s.w.figures
        for f in s.active(*DYNASTIC):
            for line in (s.leader(f), s.realms.heir_of(f)):
                if line is None or not line.alive or line.spouse < 0:
                    continue
                spouse = figs.get(line.spouse)
                if spouse is None or not spouse.alive:
                    continue
                mother, father = (line, spouse) if line.sex == "female" else (spouse, line)
                lo, hi = self.f["fertile"]
                if not lo <= self.eq_age(mother) <= hi:
                    continue
                n = len(self.kids.get(mother.id, ()))
                if n >= int(self.f["max_children"]) or not r.chance(float(self.f["birth"]) * float(self.f["birth_decay"]) ** n):
                    continue
                self.child(f, line, mother, father)

    def child(self, f, line, mother, father) -> fx.Figure:
        s = self.s
        r = s.r
        sex = r.choice(["male", "female"])
        family = line.name.split()[-1] if " " in line.name else s.realms.family_of(f)
        siblings = {k.first_name for k in self.children(mother)}
        first = None
        if r.chance(float(self.f["named_after"])):
            figs = s.w.figures
            options = [p for p in (figs.get(line.father), figs.get(line.mother), figs.get(father.id),
                                   figs.get(mother.id)) if p is not None and p.sex == sex]
            options += [figs[x] for x in f.rulers if x in figs and figs[x].sex == sex]
            options = [p for p in options if p.first_name not in siblings]
            if options:
                first = r.choice(options).first_name
        first = first or self.first_name(line.culture, sex, avoid=siblings)
        kid = self.person(line.culture, born=s.year, sex=sex, family=family, race=line.race, faction=f,
                          role="member", home=line.home or (S(f.seat) if f.seat >= 0 else ""), mother=mother.id,
                          father=father.id, first=first)
        kid.parent = line.id
        return kid

    def coming_of_age(self) -> None:
        """Children of the great take up a life: a knight's spurs, a novice's robe, a scholar's books."""
        s = self.s
        r = s.r
        figs = s.w.figures
        jobs = self.f["callings"]
        for hid in sorted(s.living):
            fig = figs[hid]
            if fig.kind != "person" or fig.job or fig.age(s.year) != self.adult_age(fig.race):
                continue
            f = s.faction(fig.faction)
            if f is None or f.kind not in DYNASTIC:
                continue
            table = jobs["male" if fig.sex == "male" else "female"]
            job = r.weighted([j for j, _ in table], [float(w) for _, w in table])
            if job != "none" and not (fig.role in LINE_ROLES and job in ("priest", "mage")):
                fig.job = job
                if job in ("knight", "captain"):
                    fig.cls, fig.level = "fighter", r.randint(2, 5) + r.randint(0, 3)
                elif job == "mage":
                    fig.cls, fig.level = "wizard", r.randint(1, 6)
                elif job == "priest":
                    fig.cls, fig.level = "cleric", r.randint(1, 5)

    # ------------------------------------------------------------------ death
    def die(self, fig, kind: str = "illness", *, cause: str | None = None, slayer=None, where: str = "",
            war=None, cause_event: dict | None = None, tell: bool = True, importance: int | None = None):
        """Someone dies. A ruler is succeeded (and the succession is the story); others of note get a line."""
        s = self.s
        if not fig.alive:
            return None
        fig.died = s.year
        fig.cause = cause or self.cause(kind)
        fig.died_at = where or fig.home
        if slayer is not None:
            fig.slayer = slayer.id
            slayer.kills.append(fig.id)
            slayer.fame += 1 + fig.fame // 3 + (4 if fig.role == "ruler" else 0)
        s.living.discard(fig.id)
        s.stat("deaths")
        if kind in ("old", "illness", "accident", "childbed"):
            s.wild.bury(fig)  # the great are laid in a barrow, with what was theirs
        elif kind in ("beast", "battle", "murder", "executed") and fig.job == "priest":
            s.faith.died_for_faith(fig)
        s.lore.on_death(fig, slayer)
        f = s.w.factions.get(fig.faction)
        event = None
        if f is not None and f.active and f.leader == fig.id:
            event = s.realms.succeed(f, fig, cause_event=cause_event, war=war)
        elif tell and cause_event is None and self.notable(fig):
            values = {"name": fig.full_name(), "cause": fig.cause,
                      "slayer": slayer.full_name() if slayer is not None else ""}
            place = int(fig.died_at[1:]) if fig.died_at.startswith("S") else None
            event = s.record("slain" if slayer is not None else "died", values,
                             importance=importance or (3 if fig.fame >= 8 else 2 if fig.fame >= 3 or
                                                       fig.role == "heir" else 1),
                             figures=[fig] + ([slayer] if slayer is not None else []),
                             factions=[f] if f is not None and f.active else [],
                             places=[place] if place is not None else [], war=war)
        if fig.role == "heir" and f is not None and f.active:
            s.realms.heir_of(f)  # the next in line is the heir now
        s.realms.regent_died(fig)
        return event

    def notable(self, fig) -> bool:
        return fig.fame >= 3 or fig.role == "heir" or fig.job in ("hero", "adventurer", "archmage", "prophet") or \
            (fig.role == "spouse" and self.s.leader(self.s.faction(fig.faction)) is not None and
             self.s.leader(self.s.faction(fig.faction)).spouse == fig.id)
