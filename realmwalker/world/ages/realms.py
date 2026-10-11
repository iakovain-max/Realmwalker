"""Realms and lords of the ages: how they begin, grow, pass from parent to child, and break apart.

- The elder peoples are older than the records: every dwarven hold has its clan, the elven halls their realms.
- Men begin with a few old kingdoms and lordships in their homelands, each with a line of rulers reaching back to
  its founder. They spread by founding villages and towns; a kingdom grants each new town to a lord, raising new
  noble houses from its knights and younger sons.
- A ruler is followed by an heir chosen by the custom of their people (the eldest son, the eldest child, the most
  able kinsman, the eldest of the clan, the choice of the elders). A child on the throne needs a regent, and a
  regent may want more. A line that dies out means a crisis: a great lord takes the crown, or the seat passes to
  a new house.
- Vassals who hate their lords rise; rich cities buy their freedom; strong lordships crown themselves; weak ones
  swear fealty to a strong neighbour.
"""

from __future__ import annotations

import math

from realmwalker.world import factions as fx
from realmwalker.world.ages.sim import DYNASTIC, S, gap
from realmwalker.world.ages.words import roman
from realmwalker.world.politics import SEAT_WORDS

HUMAN_REALMS = ("kingdom", "noble_house", "free_city", "highland_clan")
RELATION_WORDS = {"child": ("son", "daughter"), "sibling": ("brother", "sister"), "grandchild": ("grandson",
                  "granddaughter"), "nibling": ("nephew", "niece"), "spouse": ("widower", "widow"),
                  "kin": ("kinsman", "kinswoman")}


class Realms:
    def __init__(self, sim) -> None:
        self.s = sim
        self.data = sim.data["realms"]
        self.regents: dict[int, dict] = {}  # faction id -> {"regent": figure id, "heir": figure id}
        self.heirs: dict[int, int] = {}  # faction id -> the heir's figure id

    # ------------------------------------------------------------------ making factions and their rulers
    def new(self, kind: str, culture: str, name: str = "", *, seat: int = -1, liege: int = -1,
            founded: int | None = None, **kw):
        f = self.s.fm.new_faction(kind, culture, name, seat=seat, liege=liege, **kw)
        f.founded = int(self.s.year if founded is None else founded)
        self.s.touch()
        return f

    def family_of(self, f) -> str:
        return f.flags.get("dynasty") or f.flags.get("family") or ""

    def title(self, f, fig) -> str:
        return fx.figure_title(self.s.t, f.kind, fig.sex, f.culture)

    def house_name(self, culture: str, family: str, place: str | None = None) -> str:
        """A noble house as its people name one ('House Elwood', 'the House of al-Qasimi', 'the Qarluq Clan'),
        with its seat after it when the name alone is taken."""
        s = self.s
        patterns = s.t.cultures.realm_patterns("noble_house", culture)
        base = s.r.choice(patterns).replace("{family}", family)
        return f"{base} of {place}" if place else base

    def reign_length(self, race: str) -> int:
        lo, hi = self.s.t.politics["reign"].get(race, self.s.t.politics["reign"]["human"])
        return max(2, int(lo + (hi - lo) * self.s.r.random() ** 1.6))

    def found_dynasty(self, f, *, family: str | None = None, age: tuple[int, int] = (25, 55), founder=None,
                      father=None, race: str | None = None, year: int | None = None):
        """A ruler for a dynastic faction: the founder (given) or a new one, with a spouse and children."""
        s = self.s
        folk = s.folk
        year = s.year if year is None else year
        born = child = None
        if founder is None:
            span = folk.span(race or fx.culture_race(s.t, f.culture))
            born, child = self.birth_after(father, year, s.r.randint(*age), span)
            if child and not family and father.family:
                family = father.family  # the old ruler's child carries the old ruler's name
        elif not family and founder.family:
            family = founder.family  # a new line goes by its founder's name
        family = family or self.family_of(f) or s.fm.seat_family(f.culture)
        if f.kind == "kingdom":
            f.flags["dynasty"] = family
        else:
            f.flags["family"] = family
        if founder is None:
            founder = folk.person(f.culture, born=born, family=family, race=race,
                                  faction=f, role="ruler", home=S(f.seat) if f.seat >= 0 else "",
                                  father=father.id if child and father.sex == "male" else -1,
                                  mother=father.id if child and father.sex == "female" else -1,
                                  sex="male" if s.r.chance(0.62) else "female")
            if child:
                founder.parent = father.id
        self.crown(f, founder, quiet=True)
        if s.r.chance(0.7) and founder.spouse < 0:
            other = "female" if founder.sex == "male" else "male"
            span = folk.span(founder.race)
            spouse = folk.person(f.culture, born=founder.born + int(s.r.randint(-5, 8) * span), sex=other,
                                 race=founder.race, faction=f, role="spouse", home=founder.home)
            founder.spouse, spouse.spouse = spouse.id, founder.id
            youngest_parent = max(founder.born, spouse.born)
            for i in range(s.r.randint(0, 3)):
                first = youngest_parent + int(17 * span)
                if first > year:
                    break
                child_born = s.r.randint(first, min(year, youngest_parent + int(42 * span)))
                mother, father_ = (founder, spouse) if founder.sex == "female" else (spouse, founder)
                kid = folk.person(f.culture, born=child_born, family=family, race=founder.race, faction=f,
                                  home=founder.home, mother=mother.id, father=father_.id)
                kid.parent = founder.id
        self.heir_of(f)
        return founder

    def crown(self, f, fig, *, quiet: bool = False) -> None:
        """Someone takes a seat: they lead the faction now (and any seat they held before passes to their heir)."""
        s = self.s
        left = [g for g in s.active() if g is not f and g.leader == fig.id]
        old = s.w.figures.get(f.leader)
        if old is not None and old.alive and old is not fig and old.role == "ruler":
            old.role = "member"
            old.title = ""  # the style goes with the seat
        if fig.faction != f.id:
            s.folk.move(fig, f)
        fig.role = "ruler"
        fig.title = self.title(f, fig)
        f.leader = fig.id
        if fig.id not in f.rulers:
            f.rulers.append(fig.id)
        if f.seat >= 0:
            fig.home = S(f.seat)
        if f.kind == "kingdom":
            key = (f.id, fig.first_name)
            n = s.folk.regnal.get(key, 0) + 1
            s.folk.regnal[key] = n
            if n >= 2:
                fig.regnal = roman(n)
                if n == 2:
                    for rid in f.rulers:
                        first = s.w.figures.get(rid)
                        if first is not None and first is not fig and first.first_name == fig.first_name and \
                                not first.regnal:
                            first.regnal = "I"
        if f.id in self.regents and self.regents[f.id].get("heir") != fig.id:
            self.regents.pop(f.id, None)  # someone else sits there now: the regency is over
        self.heir_of(f)
        for g in left:
            self.pass_on(g, fig)

    def pass_on(self, g, old) -> None:
        """`old` has taken another seat: the one they held goes to their heir, or to a new line."""
        s = self.s
        heir = self.next_in_line(g, old) if g.kind in DYNASTIC else None
        if heir is not None and heir is not old:
            self.crown(g, heir, quiet=True)
        elif g.kind in DYNASTIC:
            self.found_dynasty(g, family=self.family_of(g) or None)
        else:
            new = s.folk.adult_person(g.culture, age=(30, 60), faction=g, role="member",
                                      home=S(g.seat) if g.seat >= 0 else "")
            self.crown(g, new, quiet=True)

    # ------------------------------------------------------------------ the old world (before the records)
    def setup(self) -> None:
        self.elder_peoples()
        self.old_realms()
        self.early_settlements()

    def prehistory(self, f, *, until: int, race: str):
        """The rulers between a realm's founding and the start of the records (all dead now). Returns the last."""
        s = self.s
        folk = s.folk
        family = self.family_of(f)
        dynastic = f.kind in DYNASTIC
        year = f.founded
        prev = None
        span = folk.span(race)
        while True:
            reign = self.reign_length(race) if dynastic else s.r.randint(5, 25)
            if year + reign >= until:
                break
            born, child = self.birth_after(prev if dynastic else None, year, s.r.randint(20, 50), span)
            fig = folk.person(f.culture, born=born, family=family if dynastic else None,
                              race=race, faction=f, role="past", home=S(f.seat) if f.seat >= 0 else "",
                              father=prev.id if child and prev.sex == "male" else -1,
                              mother=prev.id if child and prev.sex == "female" else -1,
                              sex="male" if s.r.chance(0.66) else "female")
            s.living.discard(fig.id)
            fig.title = self.title(f, fig)
            fig.died = year + reign
            fig.cause = folk.cause(s.r.weighted(["old", "illness", "battle", "murder", "accident"], [5, 4, 2, 1, 1]))
            fig.died_at = fig.home
            if f.kind == "kingdom":
                key = (f.id, fig.first_name)
                n = folk.regnal.get(key, 0) + 1
                folk.regnal[key] = n
                if n >= 2:
                    fig.regnal = roman(n)
            if s.r.chance(0.22):
                fig.epithet = s.r.choice(s.t.factions["words"]["epithet"])
            f.rulers.append(fig.id)
            if child:
                fig.parent = prev.id
            prev = fig
            year += reign
        return prev

    def birth_after(self, parent, year: int, age: int, span: float) -> tuple[int, bool]:
        """When someone who takes a seat in `year` at about `age` was born, and whether they can be the child of
        `parent` (born at least 17 years after them, grown by the time they rule). A successor who cannot be is a
        brother or a cousin instead."""
        born = year - int(age * span)
        if parent is None:
            return born, False
        earliest = parent.born + int(17 * span)
        latest = year - int(16 * span)
        if earliest > latest or (parent.died is not None and earliest > parent.died):
            return born, False
        born = min(max(born, earliest), latest)
        if parent.died is not None:
            born = min(born, parent.died)
        return born, True

    def elder_peoples(self) -> None:
        s = self.s
        land = s.land
        w = s.w
        for sp in land.spots:
            if sp.destiny != "hold":
                continue
            family = s.fm.seat_family("dwarven")
            founded = s.year0 - s.r.randint(*self.data["elder"]["dwarven"])
            c = self.new("clan", "dwarven", s.fm.make_name("clan", family=family), seat=sp.sid, founded=founded)
            c.flags["family"] = family
            land.settle(sp, by=c, year=founded, quiet=True)
            last = self.prehistory(c, until=s.year0, race="dwarf")
            ruler = self.found_dynasty(c, family=family, age=(20, 55), father=last, race="dwarf")
            s.record("chapter", {"people": "dwarves", "faction": c.name, "place": w.settlements[sp.sid].name},
                     importance=3, year=founded, factions=[c], places=[sp.sid], figures=[ruler])
        halls = [sp for sp in land.spots if sp.destiny == "elfhall"]
        while halls:
            seat = max(halls, key=lambda sp: sp.cap)
            group = [sp for sp in halls if math.hypot(sp.x - seat.x, sp.y - seat.y) <= 45]
            area = w.area_at(seat.x, seat.y)
            land_name = area.name if area is not None else s.namer.settlement("elven")
            if any(land_name in f.name for f in s.active("elven_realm")):
                land_name = s.namer.settlement("elven")
            founded = s.year0 - s.r.randint(*self.data["elder"]["elven"])
            r = self.new("elven_realm", "elven", s.fm.make_name("elven_realm", land=land_name), seat=seat.sid,
                         founded=founded)
            for sp in group:
                land.settle(sp, by=r, year=founded + (0 if sp is seat else s.r.randint(0, 300)), quiet=True)
                halls.remove(sp)
            last = self.prehistory(r, until=s.year0, race="elf")
            ruler = self.found_dynasty(r, age=(25, 70), father=last, race="elf")
            s.record("chapter", {"people": "elves", "faction": r.name, "place": w.settlements[seat.sid].name},
                     importance=3, year=founded, factions=[r], places=[seat.sid], figures=[ruler])

    def old_realms(self) -> None:
        s = self.s
        w = s.w
        land = s.land
        human = [sp for sp in land.spots if sp.human and sp.fated and s.t.cultures.is_human(sp.prior)]
        big = sorted([sp for sp in human if sp.destiny == "city"], key=lambda sp: -sp.cap) + \
            sorted([sp for sp in human if sp.destiny == "town"], key=lambda sp: -sp.cap)
        want = s.per_size("realms")
        spread = max(w.width, w.height) * float(self.data["spread"])
        capitals: list = []
        peoples = [c for c in s.t.cultures.human if any(sp.prior == c for sp in big)]
        s.r.shuffle(peoples)
        for culture in peoples:  # every people with a city or a town of its own has an old realm first
            options = [sp for sp in big if sp.prior == culture]
            if options and len(capitals) < want:
                capitals.append(options[0])
        for sp in big:
            if len(capitals) >= want:
                break
            if sp not in capitals and all(math.hypot(sp.x - c.x, sp.y - c.y) >= spread for c in capitals):
                capitals.append(sp)
        for sp in big:  # a small world may have to put two capitals closer than it likes
            if len(capitals) >= min(want, 2):
                break
            if sp not in capitals:
                capitals.append(sp)
        for cap in capitals:
            culture = cap.prior
            founded = s.year0 - s.r.randint(*self.data["old_realm_age"])
            land_name = s.fm.land_name(culture)
            k = self.new("kingdom", culture, s.fm.make_name("kingdom", culture, land=land_name), seat=cap.sid,
                         founded=founded)
            k.flags["land"] = land_name
            k.flags["dynasty"] = s.fm.seat_family(culture)
            land.settle(cap, by=k, year=founded, quiet=True)
            last = self.prehistory(k, until=s.year0, race="human")
            founder = s.w.figures[k.rulers[0]] if k.rulers else None
            ruler = self.found_dynasty(k, father=last, race="human")
            s.record("chapter", {"people": "lords", "faction": k.name, "place": w.settlements[cap.sid].name},
                     importance=4, year=founded, factions=[k], places=[cap.sid],
                     figures=[founder or ruler])
        towns = [sp for sp in human if sp.destiny == "town" and sp not in capitals]
        towns.sort(key=lambda sp: -min((math.hypot(sp.x - c.x, sp.y - c.y) for c in capitals), default=0))
        for sp in towns[: s.per_size("lordships")]:
            if capitals and min(math.hypot(sp.x - c.x, sp.y - c.y) for c in capitals) < spread * 0.5:
                continue
            founded = s.year0 - s.r.randint(*self.data["lordship_age"])
            family = s.fm.seat_family(sp.prior)
            name = self.house_name(sp.prior, family)
            s.fm.used_names.add(name)
            h = self.new("noble_house", sp.prior, name, seat=sp.sid, founded=founded)
            h.flags["family"] = family
            land.settle(sp, by=h, year=founded, quiet=True)
            last = self.prehistory(h, until=s.year0, race="human")
            self.found_dynasty(h, family=family, father=last, race="human")
            s.record("founded_lordship", {"founder": f"the first of {name}", "place": s.place_name(sp.sid),
                                          "faction": h.name}, importance=2, year=founded, factions=[h],
                     places=[sp.sid])

    def early_settlements(self) -> None:
        """Places founded before the records begin, oldest first."""
        s = self.s
        early = sorted((sp for sp in s.land.spots if sp.human and sp.plan is not None and sp.plan < s.year0
                        and sp.founded is None), key=lambda sp: (sp.plan, sp.sid))
        for sp in early:
            s.year = sp.plan
            s.land.settle(sp, year=sp.plan, quiet=sp.destiny in ("hamlet", "village"))
        s.year = s.year0

    # ------------------------------------------------------------------ founding places
    def can_found(self, realm, sp) -> bool:
        if sp.destiny == "hold":
            return realm.kind == "clan"
        if sp.destiny == "elfhall":
            return realm.kind == "elven_realm"
        if realm.kind not in HUMAN_REALMS:
            return False
        if realm.kind in ("highland_clan", "free_city") and sp.destiny in ("town", "city"):
            return False
        return realm.founded <= self.s.year

    def nearest_lord(self, realm, sp):
        """Who in a realm holds the land nearest a new village: the crown or one of its lords."""
        s = self.s
        best = None
        for st in s.holdings(realm, deep=True):
            owner = s.faction(st.owner)
            if owner is None or owner.seat != st.id:
                continue
            d = math.hypot(st.x - sp.x, st.y - sp.y)
            if best is None or d < best[0]:
                best = (d, owner)
        return best[1] if best is not None else realm

    def found_settlement(self, sp, realm, *, rebuild: bool, old_name: str, year: int | None, quiet: bool) -> None:
        """Who holds a new place, and how it is told."""
        s = self.s
        land = s.land
        st = s.w.settlements[sp.sid]
        when = s.year if year is None else year
        values = {"place": st.name, "old": old_name or "the old place", "what": land.words(sp.sid),
                  "settlers": s.r.choice(s.data["words"]["settlers"])}
        if realm is not None and realm.seat == sp.sid:
            e = s.record("founded_seat" if not rebuild else "rebuilt",
                         {**values, "faction": realm.name}, importance=1, year=when, places=[sp.sid],
                         factions=[realm]) if not quiet else None
            land.set_owner(sp.sid, realm.id, e if e is not None else self._quiet(sp, realm, when))
            return
        if realm is None:
            if sp.destiny in ("town", "city"):
                h = self.raise_house(sp, None, year=when)
                e = s.record("rebuilt" if rebuild else "founded_lordship",
                             {**values, "founder": s.w.figures[h.leader].full_name(), "faction": h.name},
                             importance=2, year=when, places=[sp.sid], factions=[h], figures=[h.leader])
                land.set_owner(sp.sid, h.id, e)
            else:
                e = s.record("rebuilt" if rebuild else "settled", {**values, "realm": "no lord"}, importance=1,
                             year=when, places=[sp.sid])
                land.set_owner(sp.sid, -1, e)
            return
        if realm.kind == "kingdom" and sp.destiny in ("town", "city"):
            h = self.raise_house(sp, realm, year=when)
            ruler = s.leader(realm)
            e = s.record("rebuilt" if rebuild else "founded_town",
                         {**values, "founder": s.w.figures[h.leader].full_name(), "faction": h.name,
                          "ruler": ruler.full_name() if ruler else realm.name, "realm": realm.name},
                         importance=2, year=when, places=[sp.sid], factions=[realm, h],
                         figures=[h.leader] + ([ruler] if ruler else []))
            land.set_owner(sp.sid, h.id, e)
            return
        lord = self.nearest_lord(realm, sp) if realm.kind == "kingdom" else realm
        e = s.record("rebuilt" if rebuild else "settled", {**values, "realm": realm.name}, importance=1,
                     year=when, places=[sp.sid], factions=[realm]) if not quiet or rebuild else None
        land.set_owner(sp.sid, lord.id, e if e is not None else self._quiet(sp, lord, when))

    def _quiet(self, sp, holder, when: int) -> dict:
        """A small place founded long ago: one plain line, so the ledger of who held what stays whole."""
        return self.s.record("settled", {"place": self.s.place_name(sp.sid), "realm": holder.name,
                                         "settlers": self.s.r.choice(self.s.data["words"]["settlers"]),
                                         "what": self.s.land.words(sp.sid)},
                             importance=1, year=when, places=[sp.sid], factions=[holder])

    def raise_house(self, sp, realm, *, year: int | None = None, founder=None, why: str = ""):
        """A new noble house holds a town: a knight, a war hero or a younger son of the royal house."""
        s = self.s
        folk = s.folk
        culture = realm.culture if realm is not None else sp.prior
        culture = s.t.cultures.human_or_default(culture)
        if founder is None and realm is not None:
            cadets = [k for k in folk.children(s.leader(realm)) if folk.is_adult(k) and k.role == "member"
                      and k.sex == "male"] if s.leader(realm) is not None else []
            if cadets and s.r.chance(0.3):
                founder = cadets[-1]
        family = s.fm.seat_family(culture)
        if founder is not None and founder.faction == (realm.id if realm is not None else -2):
            family = fx.family_of(founder) or family
            name = self.house_name(culture, family, s.place_name(sp.sid))
        else:
            name = self.house_name(culture, family)
        if name in s.fm.used_names:
            name = self.house_name(culture, family, s.place_name(sp.sid))
        s.fm.used_names.add(name)
        h = self.new("noble_house", culture, name, seat=sp.sid, liege=realm.id if realm is not None else -1,
                     founded=year)
        h.flags["family"] = family
        if founder is not None:
            if fx.family_of(founder) != family:
                founder.family = family
                founder.name = s.folk.forge.person(culture, founder.sex, s.r, noble=True, first=founder.first_name,
                                                   family=family)
            self.found_dynasty(h, family=family, founder=founder, year=year)
        else:
            self.found_dynasty(h, family=family, age=(24, 50), year=year)
            leader = s.w.figures[h.leader]
            if not leader.job:
                leader.job = "knight"
        if realm is not None:
            fx.set_relation(s.w, h.id, realm.id, 45 + s.r.uniform(-10, 15))
        return h

    # ------------------------------------------------------------------ heirs and successions
    def kin_of(self, fig) -> list[tuple[str, object]]:
        """Blood relatives, nearest first: children, grandchildren, siblings, their children."""
        folk = self.s.folk
        out: list[tuple[str, object]] = []
        kids = folk.children(fig, living=False)
        for k in kids:
            if k.alive:
                out.append(("child", k))
        for k in kids:
            for g in folk.children(k):
                out.append(("grandchild", g))
        sibs = folk.siblings(fig, living=False)
        for b in sibs:
            if b.alive:
                out.append(("sibling", b))
        for b in sibs:
            for n in folk.children(b):
                out.append(("nibling", n))
        return out

    def eligible(self, f, fig) -> bool:
        if not fig.alive or fig.kind != "person" or fig.job in ("priest",):
            return False
        other = self.s.w.factions.get(fig.faction)
        return not (other is not None and other.active and other.id != f.id and other.leader == fig.id)

    def next_in_line(self, f, ruler):
        """The heir by the custom of the ruler's people."""
        s = self.s
        folk = s.folk
        custom = (s.data["peoples"].get(f.culture) or s.data["peoples"]["heartland"])["succession"]
        kin = [(rel, k) for rel, k in self.kin_of(ruler) if self.eligible(f, k)]
        if custom in ("male_primogeniture", "primogeniture"):
            for rel in ("child", "grandchild", "sibling", "nibling"):
                group = [k for r, k in kin if r == rel]
                if group:
                    if custom == "male_primogeniture":
                        group.sort(key=lambda k: (k.sex != "male", k.born))
                    else:
                        group.sort(key=lambda k: k.born)
                    return group[0]
        elif custom == "tanistry":
            adults = [k for _, k in kin if folk.is_adult(k)]
            if adults:
                return max(adults, key=lambda k: (k.fame, k.sex == "male", -k.born))
            if kin:
                return min((k for _, k in kin), key=lambda k: k.born)
        elif custom in ("seniority", "elective"):
            family = self.family_of(f)
            members = [s.w.figures[m] for m in f.members if m in s.w.figures]
            pool = [m for m in members if m.id != ruler.id and self.eligible(f, m) and folk.is_adult(m)
                    and (not family or fx.family_of(m) == family)]
            pool += [k for _, k in kin if folk.is_adult(k) and k not in pool]
            if pool:
                if custom == "seniority":
                    return min(pool, key=lambda k: k.born)
                return max(pool, key=lambda k: (k.fame, -k.born))
            if kin:
                return min((k for _, k in kin), key=lambda k: k.born)
        return None

    def heir_of(self, f):
        """Who would take the seat if the ruler died today (marked with the role "heir")."""
        s = self.s
        if f.kind not in DYNASTIC:
            return None
        ruler = s.leader(f)
        heir = self.next_in_line(f, ruler) if ruler is not None else None
        old = self.heirs.get(f.id)
        new = heir.id if heir is not None else -1
        if old != new:
            prev = s.w.figures.get(old) if old is not None else None
            if prev is not None and prev.role == "heir":
                prev.role = "member"
            if heir is not None:
                heir.role = "heir"
            self.heirs[f.id] = new
        return heir

    def relation_word(self, old, new) -> str:
        for rel, k in self.kin_of(old):
            if k is new:
                male, female = RELATION_WORDS[rel]
                return f"their {male if new.sex == 'male' else female}"
        if old.spouse == new.id:
            return "their widow" if new.sex == "female" else "their widower"
        return "a kinsman" if new.sex == "male" else "a kinswoman"

    def succeed(self, f, old, *, cause_event: dict | None = None, war=None) -> dict | None:
        """A leader is dead. Who follows them, by custom, by force or by choice."""
        s = self.s
        folk = s.folk
        if f.kind in DYNASTIC:
            heir = self.next_in_line(f, old)
            if heir is None and old.spouse >= 0:
                spouse = s.w.figures.get(old.spouse)
                if spouse is not None and spouse.alive and spouse.faction == f.id and folk.is_adult(spouse) and \
                        s.r.chance(0.35):
                    heir = spouse
            if heir is not None:
                relation = self.relation_word(old, heir)
                self.crown(f, heir)
                values = {"old": old.full_name(), "cause": old.cause, "new": heir.full_name(),
                          "relation": relation, "seat": SEAT_WORDS.get(f.kind, "seat"), "faction": f.name}
                importance = 4 if f.kind == "kingdom" else 3 if f.kind in ("clan", "elven_realm") else 2
                if not folk.is_adult(heir):
                    regent = self.choose_regent(f, heir, old)
                    values["regent"] = regent.full_name() if regent is not None else "the council"
                    e = s.record("succession_minor", values, importance=importance, factions=[f],
                                 figures=[old, heir] + ([regent] if regent is not None else []), war=war,
                                 places=[f.seat] if f.seat >= 0 else [])
                else:
                    e = s.record("succession", values, importance=importance, factions=[f], figures=[old, heir],
                                 war=war, places=[f.seat] if f.seat >= 0 else [])
                return e
            return self.crisis(f, old, war=war)
        return self.elect(f, old, war=war)

    def choose_regent(self, f, heir, old):
        s = self.s
        folk = s.folk
        options = []
        mother = s.w.figures.get(heir.mother)
        father = s.w.figures.get(heir.father)
        for p in (mother, father):
            if p is not None and p.alive and folk.is_adult(p):
                options.append(p)
        options += [k for rel, k in self.kin_of(old) if rel == "sibling" and folk.is_adult(k)]
        regent = options[0] if options else None
        if regent is None:
            regent = folk.adult_person(f.culture, age=(35, 60), faction=f, role="member", job="steward",
                                       home=S(f.seat) if f.seat >= 0 else "")
        self.regents[f.id] = {"regent": regent.id, "heir": heir.id}
        regent.fame += 2
        return regent

    def regent_died(self, fig) -> None:
        for fid, reg in list(self.regents.items()):
            if reg["regent"] == fig.id:
                f = self.s.faction(fid)
                heir = self.s.w.figures.get(reg["heir"])
                if f is None or heir is None or not heir.alive or f.leader != heir.id:
                    self.regents.pop(fid, None)
                    continue
                self.choose_regent(f, heir, fig)

    def regencies(self) -> None:
        """Child rulers grow up, and a regent who has tasted power may not wish to let it go."""
        s = self.s
        folk = s.folk
        for fid, reg in sorted(self.regents.items()):
            f = s.faction(fid)
            heir = s.w.figures.get(reg["heir"])
            regent = s.w.figures.get(reg["regent"])
            if f is None or heir is None or not heir.alive or f.leader != heir.id or regent is None:
                self.regents.pop(fid, None)
                continue
            if folk.is_adult(heir):
                self.regents.pop(fid, None)
                s.record("came_of_age", {"ruler": heir.full_name(), "regent": regent.full_name(), "faction": f.name},
                         importance=2, factions=[f], figures=[heir, regent])
            elif regent.alive and s.chance("usurping_regent", 2.0 if "proud" in regent.traits else 1.0):
                self.regents.pop(fid, None)
                e = s.record("regent_usurps", {"regent": regent.full_name(), "ruler": heir.full_name(),
                                               "faction": f.name}, importance=4 if f.kind == "kingdom" else 3,
                             factions=[f], figures=[regent, heir])
                # The regent takes the seat first, so the child's death is no longer anyone's succession.
                self.crown(f, regent)
                if f.kind == "kingdom":
                    f.flags["dynasty"] = fx.family_of(regent) or f.flags["dynasty"]
                folk.die(heir, "murder", cause=s.r.choice(s.data["causes"]["vanished"]), cause_event=e, tell=False)

    def crisis(self, f, old, *, war=None) -> dict | None:
        """A line has ended. A kingdom finds a new king among its lords; a vassal's seat goes back to its liege;
        others find a new chief."""
        s = self.s
        folk = s.folk
        seat = f.seat if f.seat >= 0 else None
        if f.kind == "kingdom":
            houses = [v for v in s.vassals(f) if v.kind == "noble_house" and s.leader(v) is not None]
            if houses:
                strongest = max(houses, key=lambda h: (h.military, h.id))
                usurper = s.leader(strongest)
                e = s.record("crisis", {"old": old.full_name(), "cause": old.cause, "new": usurper.full_name(),
                                        "house": strongest.name, "seat": "throne", "faction": f.name},
                             importance=4, factions=[f, strongest], figures=[old, usurper], war=war,
                             places=[seat] if seat is not None else [])
                self.crown(f, usurper)
                f.flags["dynasty"] = self.family_of(strongest) or fx.family_of(usurper)
                f.flags["crisis"] = s.year  # (crowning the usurper handed their house to its own heir)
                for v in houses:
                    if v is not strongest:
                        self.change_relation(v, f, -s.r.uniform(10, 35))
                if len(houses) >= 2 and s.chance("succession_war"):
                    rival = max((h for h in houses if h is not strongest), key=lambda h: (h.military, h.id))
                    s.war.start(rival, f, "succession", claimant=s.leader(rival))
                return e
            steward = folk.adult_person(f.culture, age=(30, 55), faction=f, role="member", job="steward",
                                        home=S(seat) if seat is not None else "")
            family = fx.family_of(steward)
            e = s.record("crisis", {"old": old.full_name(), "cause": old.cause, "new": steward.full_name(),
                                    "house": self.house_name(f.culture, family), "seat": "throne",
                                    "faction": f.name},
                         importance=4, factions=[f], figures=[old, steward], war=war,
                         places=[seat] if seat is not None else [])
            f.flags["dynasty"] = family
            f.flags["crisis"] = s.year
            self.found_dynasty(f, family=family, founder=steward)
            return e
        if f.kind == "noble_house" and f.liege >= 0 and s.faction(f.liege) is not None:
            return self.escheat(f, old, war=war)
        # A new line: the strongest of the kin by marriage, a captain, an elder.
        new = folk.adult_person(f.culture, age=(28, 60), faction=f,
                                role="member", home=S(seat) if seat is not None else "",
                                race=old.race if old.kind == "person" else None)
        family = fx.family_of(new)
        e = s.record("crisis", {"old": old.full_name(), "cause": old.cause, "new": new.full_name(),
                                "house": "another line", "seat": SEAT_WORDS.get(f.kind, "seat"), "faction": f.name},
                     importance=3 if f.kind in ("clan", "elven_realm") else 2, factions=[f], figures=[old, new],
                     war=war, places=[seat] if seat is not None else [])
        if f.kind == "noble_house":
            f.flags["family"] = family
            place = s.place_name(seat) if seat is not None else "the March"
            name = self.house_name(f.culture, family)
            f.name = name if name not in s.fm.used_names else self.house_name(f.culture, family, place)
            s.fm.used_names.add(f.name)
        self.found_dynasty(f, family=family if f.kind == "noble_house" else None, founder=new)
        return e

    def escheat(self, f, old, *, war=None) -> dict:
        """A vassal house dies out: its lands go back to its liege, who gives the seat to someone new."""
        s = self.s
        liege = s.faction(f.liege)
        seat = f.seat
        e = s.record("house_ended", {"old": old.full_name(), "cause": old.cause, "house": f.name,
                                     "liege": liege.name}, importance=2, factions=[f, liege], figures=[old], war=war,
                     places=[seat] if seat >= 0 else [])
        held = s.land.held_by(f.id)
        self.fall(f, event=e, quiet=True)
        top = s.top(liege) or liege
        if seat >= 0 and s.land.spots[seat].standing and s.land.spots[seat].human and \
                s.land.kind_of(s.land.spots[seat]) in ("town", "city"):
            hero = self.deserving(top)
            h = self.raise_house(s.land.spots[seat], top, founder=hero)
            g = s.record("granted", {"place": s.place_name(seat), "lord": s.w.figures[h.leader].full_name(),
                                     "liege": top.name, "faction": h.name}, importance=2, factions=[top, h],
                         figures=[h.leader], places=[seat])
            for sid in held:
                s.land.set_owner(sid, h.id, g)
        return e

    def deserving(self, realm):
        """Someone the crown owes a town: a knight with a name, or nobody (a new man will be found)."""
        s = self.s
        options = [s.w.figures[m] for m in realm.members if m in s.w.figures]
        options = [m for m in options if m.alive and m.kind == "person" and m.role == "member"
                   and m.job in ("knight", "captain", "hero") and s.folk.is_adult(m)]
        if not options:
            return None
        best = max(options, key=lambda m: (m.fame, -m.born))
        return best if best.fame >= 3 else None

    def elect(self, f, old, *, war=None) -> dict | None:
        """Councils, chapters and crews choose the next one."""
        s = self.s
        folk = s.folk
        members = [s.w.figures[m] for m in f.members if m in s.w.figures]
        pool = [m for m in members if m.alive and m.kind == "person" and m.id != old.id and folk.is_adult(m)
                and m.role != "ruler"]
        if f.kind in ("bandit_gang", "pirate_crew") and s.r.chance(0.4):
            e = s.record("gang_ended", {"old": old.full_name(), "cause": old.cause, "faction": f.name},
                         importance=2, factions=[f], figures=[old], war=war)
            self.fall(f, event=e, quiet=True)
            return e
        if pool and s.r.chance(0.6):
            new = max(pool, key=lambda m: (m.fame, s.r.random()))
        else:
            ages = {"temple": (40, 70), "mages_circle": (45, 85), "tribe": (22, 45), "bandit_gang": (20, 45),
                    "pirate_crew": (22, 50)}.get(f.kind, (35, 65))
            race = old.race if old.kind == "person" else None
            job = {"temple": "priest", "mages_circle": "mage", "tribe": "warchief", "thieves_guild": "thief"}.get(
                f.kind, "")
            new = folk.adult_person(f.culture, age=ages, faction=f, role="member", race=race, job=job,
                                    home=S(f.seat) if f.seat >= 0 else old.home)
        self.crown(f, new)
        if f.kind in ("tribe", "bandit_gang", "pirate_crew") and not new.epithet and s.r.chance(0.6):
            new.epithet = s.r.choice(s.t.factions["words"]["epithet"])
        importance = 1 if f.secret else 3 if f.kind in ("temple", "free_city") else \
            2 if f.kind in ("tribe", "knightly_order", "mages_circle") else 1
        return s.record("elected", {"old": old.full_name(), "cause": old.cause, "new": new.full_name(),
                                    "faction": f.name}, importance=importance, factions=[] if f.secret else [f],
                        figures=[old, new], war=war)

    # ------------------------------------------------------------------ the end of factions
    def fall(self, f, *, event: dict | None = None, conqueror=None, quiet: bool = False,
             kind: str = "faction_fell") -> dict:
        """A faction is no more. Its lands go to its liege or its conqueror (or to nobody); its vassals are free."""
        s = self.s
        if not f.active:
            return event or {}
        if event is None:
            event = s.record(kind, {"faction": f.name, "conqueror": conqueror.name if conqueror else "its enemies"},
                             importance=4 if f.kind == "kingdom" else 3 if f.kind in ("clan", "elven_realm",
                                                                                      "free_city") else 2,
                             factions=[f] + ([conqueror] if conqueror else []))
        f.fallen = s.year
        heir = s.w.figures.get(self.heirs.pop(f.id, -1))
        if heir is not None and heir.role == "heir":
            heir.role = "member"
        self.regents.pop(f.id, None)
        liege = s.faction(f.liege)
        to = conqueror if conqueror is not None else liege
        for sid in s.land.held_by(f.id):
            s.land.set_owner(sid, to.id if to is not None else -1, event)
        for v in s.vassals(f):
            v.liege = conqueror.id if conqueror is not None and conqueror.kind in HUMAN_REALMS else -1
        for site in s.w.sites:
            if site.faction == f.id:
                site.faction = -1
        s.touch()
        return event

    def place_lost(self, sp, holder: int, event: dict) -> None:
        """A seat is razed or taken: whoever sat there moves to another of their places, or falls."""
        s = self.s
        for f in s.active():
            if f.seat != sp.sid:
                continue
            left = s.land.held_by(f.id)
            if f.kind in fx.REALM_KINDS:
                if left:
                    f.seat = max(left, key=lambda sid: s.land.spots[sid].pop)
                    leader = s.leader(f)
                    if leader is not None:
                        leader.home = S(f.seat)
                else:
                    self.fall(f, event=event)
            else:
                options = [st for st in s.land.standing() if st.sid != sp.sid and st.human
                           and s.w.settlements[st.sid].culture == f.culture] or \
                    [st for st in s.land.standing() if st.sid != sp.sid and st.human]
                if options:
                    f.seat = max(options, key=lambda st: st.pop).sid
                f.presence = [i for i in f.presence if i != sp.sid]

    def take(self, sp, winner, loser, event: dict, *, sacked: bool) -> None:
        """A place changes hands in war. A lord whose seat it is may bend the knee, or be put out."""
        s = self.s
        st = s.w.settlements[sp.sid]
        owner = s.faction(st.owner)
        top_winner = s.top(winner) or winner
        if owner is not None and owner.seat == sp.sid and owner.kind == "noble_house" and owner is not loser \
                and s.r.chance(0.55):
            owner.liege = top_winner.id
            s.touch()
            fx.set_relation(s.w, owner.id, top_winner.id, 10)
            event.setdefault("data", {})["fealty"] = owner.id
            return
        if owner is not None and owner.seat == sp.sid:
            left = [sid for sid in s.land.held_by(owner.id) if sid != sp.sid]
            if left:
                owner.seat = max(left, key=lambda sid: s.land.spots[sid].pop)
            else:
                s.land.set_owner(sp.sid, -1, event)
                self.fall(owner, event=event, conqueror=None)
        if sp.human and s.land.kind_of(sp) in ("town", "city") and top_winner.kind == "kingdom":
            hero = self.deserving(top_winner)
            h = self.raise_house(sp, top_winner, founder=hero)
            s.land.set_owner(sp.sid, h.id, event)
            event.setdefault("figures", []).append(h.leader)
        else:
            s.land.set_owner(sp.sid, top_winner.id if top_winner.kind != "tribe" else -1, event)

    # ------------------------------------------------------------------ the year
    def year(self) -> None:
        self.drift()
        self.regencies()
        self.grants()
        self.claims()
        self.fealty()
        self.rebellions()
        self.charters()
        self.proclamations()
        self.intrigue()
        self.military()

    def grants(self) -> None:
        """A crown that holds a town itself sooner or later gives it to a lord: a knight who earned it, a younger
        son, a new man. The villages round about go with it."""
        s = self.s
        for k in s.active("kingdom"):
            for sid in s.land.held_by(k.id):
                sp = s.land.spots[sid]
                if sid == k.seat or not sp.human or sp.kind_now not in ("town", "city") or not s.chance("grant"):
                    continue
                h = self.raise_house(sp, k, founder=self.deserving(k))
                lord = s.w.figures[h.leader]
                e = s.record("granted", {"place": s.place_name(sid), "lord": lord.full_name(), "liege": k.name,
                                         "faction": h.name}, importance=2, factions=[k, h], figures=[lord],
                             places=[sid])
                s.land.set_owner(sid, h.id, e)
                for other in s.land.held_by(k.id):
                    near = s.land.spots[other]
                    if other != k.seat and near.kind_now in ("hamlet", "village") and \
                            math.hypot(near.x - sp.x, near.y - sp.y) <= 12:
                        s.land.set_owner(other, h.id, e)
                break

    def change_relation(self, a, b, amount: float) -> None:
        if a is None or b is None or a.id == b.id:
            return
        fx.change_relation(self.s.w, a.id, b.id, amount)

    def drift(self) -> None:
        s = self.s
        r = s.r
        sigma = float(self.data["drift"])
        powers = s.powers()
        anchors = {f.id: s.anchor(f) for f in powers}
        lands = {f.id: s.lands(f) for f in powers}
        border = float(s.data["war"].get("border_reach", 0))
        for i, a in enumerate(powers):
            pa = anchors[a.id]
            for b in powers[i + 1:]:
                pb = anchors[b.id]
                rel = fx.relation(s.w, a.id, b.id)
                change = r.gauss(0, sigma) - rel * 0.03
                if pa is not None and pb is not None and (math.hypot(pa[0] - pb[0], pa[1] - pb[1]) < 40 or
                                                          gap(lands[a.id], lands[b.id]) <= border):
                    change -= float(self.data["border_friction"])  # neighbours rub
                if a.culture == b.culture:
                    change += 0.6
                if a.faith != b.faith and ("pious" in a.values or "pious" in b.values):
                    change -= 0.8
                fx.set_relation(s.w, a.id, b.id, rel + change)
        for v in s.active("noble_house", "highland_clan"):
            liege = s.faction(v.liege)
            if liege is None:
                continue
            rel = fx.relation(s.w, v.id, liege.id)
            change = r.gauss(0, 6) - (rel - 20) * 0.04
            if "cruel" in liege.values:
                change -= 1.5
            if "honor-bound" in liege.values:
                change += 0.8
            if s.war.at_war(liege.id):
                change -= 1.2  # levies, taxes and sons sent to die
            fx.set_relation(s.w, v.id, liege.id, rel + change)

    def claims(self) -> None:
        """Free villages near a realm come under its rule."""
        s = self.s
        for sp in s.land.spots:
            if not sp.standing or not sp.human or s.w.settlements[sp.sid].owner >= 0:
                continue
            if not s.r.chance(0.12):
                continue
            for d, sid in sp.near:
                if d > s.land.reach:
                    break
                other = s.land.spots[sid]
                owner = s.faction(s.w.settlements[sid].owner) if other.standing else None
                top = s.top(owner) if owner is not None else None
                if top is not None and top.kind in HUMAN_REALMS:
                    lord = self.nearest_lord(top, sp) if top.kind == "kingdom" else top
                    s.land.set_owner(sp.sid, lord.id, None)
                    break

    def fealty(self) -> None:
        s = self.s
        for f in s.active("noble_house", "highland_clan"):
            if f.liege >= 0 or s.war.at_war(f.id) or len(s.land.held_by(f.id)) > 3:
                continue
            if not s.chance("fealty"):
                continue
            here = s.anchor(f)
            if here is None:
                continue
            best = None
            for k in s.active("kingdom"):
                there = s.anchor(k)
                if there is None or k.liege >= 0:
                    continue
                d = math.hypot(here[0] - there[0], here[1] - there[1])
                if d < 45 and fx.relation(s.w, f.id, k.id) > 10 and k.military > 2.5 * max(1, f.military):
                    if best is None or d < best[0]:
                        best = (d, k)
            if best is None:
                continue
            k = best[1]
            f.liege = k.id
            s.touch()
            fx.set_relation(s.w, f.id, k.id, 40)
            leader = s.leader(f)
            s.record("fealty", {"lord": leader.full_name() if leader else f.name, "faction": f.name,
                                "liege": k.name}, importance=2, factions=[f, k], figures=[leader] if leader else [])

    def rebellions(self) -> None:
        s = self.s
        for v in s.active("noble_house", "highland_clan", "clan"):
            liege = s.faction(v.liege)
            if liege is None or s.war.at_war_with(v, liege) or s.leader(v) is None:
                continue
            rel = fx.relation(s.w, v.id, liege.id)
            if rel > -20:
                continue
            troubled = s.war.at_war(liege.id) or liege.id in self.regents or \
                liege.flags.get("crisis", -10**6) >= s.year - 5
            if s.chance("rebellion", 3.0 if troubled else 1.0):
                s.war.start(v, liege, "rebellion")

    def charters(self) -> None:
        s = self.s
        want = s.per_size("free_city", "counts")
        if len(s.active("free_city")) >= want + 1:
            return
        for k in s.active("kingdom"):
            for sid in s.land.held_by(k.id):
                sp = s.land.spots[sid]
                if sid == k.seat or not sp.human or s.land.kind_of(sp) != "city":
                    continue
                if not s.chance("charter", 2.0 if "mercantile" in k.values or s.war.at_war(k.id) else 1.0):
                    continue
                st = s.w.settlements[sid]
                fc = self.new("free_city", st.culture, s.fm.make_name("free_city", st.culture, seat=st.name),
                              seat=sid)
                e = s.record("charter", {"place": st.name, "faction": fc.name, "liege": k.name}, importance=3,
                             factions=[fc, k], places=[sid])
                s.land.set_owner(sid, fc.id, e)
                new = s.folk.adult_person(st.culture, age=(40, 65), faction=fc, role="member", job="merchant",
                                          home=S(sid))
                self.crown(fc, new)
                fx.set_relation(s.w, fc.id, k.id, -10 + s.r.uniform(-15, 15))
                return

    def proclamations(self) -> None:
        s = self.s
        for f in s.active("noble_house", "highland_clan"):
            if f.liege >= 0 or s.leader(f) is None:
                continue
            held = [s.land.spots[sid] for sid in s.land.held_by(f.id)]
            deep = [s.land.spots[st.id] for st in s.holdings(f, deep=True)]
            if len(deep) < 6 or not any(s.land.kind_of(sp) in ("town", "city") for sp in held):
                continue
            if not s.chance("proclamation"):
                continue
            ruler = s.leader(f)
            old_name = f.name
            culture = s.t.cultures.human_or_default(f.culture)
            land_name = s.fm.land_name(culture)
            f.kind = "kingdom"
            f.name = s.fm.make_name("kingdom", culture, land=land_name)
            f.flags["land"] = land_name
            f.flags["dynasty"] = self.family_of(f) or fx.family_of(ruler)
            f.color = s.fm.next_color()
            s.touch()
            self.crown(f, ruler)
            s.record("proclaimed", {"ruler": ruler.full_name(), "old": old_name, "faction": f.name}, importance=4,
                     factions=[f], figures=[ruler], places=[f.seat] if f.seat >= 0 else [])

    def intrigue(self) -> None:
        """Brothers who would be kings, wives who would be widows: now and then a ruler is murdered."""
        s = self.s
        folk = s.folk
        for f in s.active("kingdom", "noble_house", "highland_clan", "clan", "elven_realm"):
            ruler = s.leader(f)
            if ruler is None or not s.chance("assassination"):
                continue
            plotters = [k for rel, k in self.kin_of(ruler) if rel == "sibling" and folk.is_adult(k)
                        and k.faction == f.id] + [m for m in s.vassals(f) if s.leader(m) is not None]
            plotter = None
            if plotters and s.r.chance(0.6):
                p = s.r.choice(plotters)
                plotter = p if hasattr(p, "born") else s.leader(p)
            found = plotter is not None and s.r.chance(0.45)
            e = s.record("assassination" if found else "assassination_unknown",
                         {"victim": ruler.full_name(), "faction": f.name,
                          "plotter": plotter.full_name() if plotter and found else ""},
                         importance=4 if f.kind == "kingdom" else 3, factions=[f],
                         figures=[ruler] + ([plotter] if plotter and found else []),
                         places=[f.seat] if f.seat >= 0 else [])
            folk.die(ruler, "murder", slayer=plotter if found else None, cause_event=e, tell=False)
            if found and plotter.alive and s.r.chance(0.5) and f.leader != plotter.id:
                folk.die(plotter, "executed", cause_event=e, tell=False)

    def military(self) -> None:
        s = self.s
        for f in s.active():
            spec = s.t.factions["kinds"][f.kind]
            if spec["group"] == "realms":
                pop = sum(s.land.spots[sid].pop for sid in s.land.held_by(f.id))
                factor = 1.5 if "warlike" in f.values else 0.8 if "mercantile" in f.values else 1.0
                base = int(pop * 0.035 * factor) + 5
            else:
                base = int(f.flags.get("base_military", f.military or 10))
            f.flags["base_military"] = base
            if f.military < base:
                f.military = min(base, int(f.military + base * 0.18 + 1))
            elif f.military > base * 1.2:
                f.military = int(f.military * 0.95)
