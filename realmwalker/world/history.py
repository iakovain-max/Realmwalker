"""History: the world's past, and the chronicle that tells it.

New worlds (2026-10) *live* their history year by year as they are made (world/ages, after Dwarf Fortress): today
is what the ages left. This module keeps the chronicle (told age by age when the ages are named) and, for worlds
made before that, the older way below, which tells a history that agrees with a map made first:

1. Every faction gets its line of past rulers, ending with today's (reigns by race, causes of death, the odd
   usurper who changed a kingdom's dynasty).
2. Towns and cities get founding years; the ruins in the wild get a past (what they were, and what ended them).
3. The politics engine (world/politics.py) runs a year at a time over the last few centuries: wars, plagues,
   famines, raids, cults. Its wars leave today's grudges; a war still being fought when history ends is
   today's war.
4. The deep past: dragons that burned towns (some slain by heroes, some only sleeping), legendary figures, and
   artifacts that were lost (M8 lets you look for them).

Everything goes into world.history (a list of dated events, oldest first), from which the chronicle is written
(AI when it is there, built-in words otherwise). The last year or two also become news people still talk about.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.world import factions as fx
from realmwalker.world import news
from realmwalker.world.politics import DYNASTIC, SEAT_WORDS, Politics

RECENT_YEARS = 2  # history this recent is still news


def day_of_year(tables, year: int, rng: RNG) -> float:
    """A day number (world days since the start of the present's first year) somewhere in `year`."""
    cal = tables.calendar
    return (year - cal.start_year) * cal.days_per_year + rng.uniform(0, cal.days_per_year - 1)


class HistoryMaker:
    def __init__(self, world, tables, rng: RNG) -> None:
        self.w = world
        self.t = tables
        self.data = tables.politics
        self.rng = rng
        self.present = tables.calendar.start_year
        self.year0 = self.present - int(self.data["history_years"])

    def event(self, year: int, kind: str, values: dict, *, importance: int = 2, factions=(), places=(),
              figures=()) -> None:
        text = textgen.fill(self.rng.choice(self.data["text"][kind]), self.rng, {}, {k: str(v) for k, v in values.items()})
        self.w.history.append({"year": int(year), "kind": kind, "text": text,
                               "factions": [f.id if hasattr(f, "id") else int(f) for f in factions],
                               "places": [p.id if hasattr(p, "id") else int(p) for p in places],
                               "figures": list(figures), "importance": importance})

    # ------------------------------------------------------------------ all of it
    def run(self) -> None:
        w = self.w
        w.history.clear()
        self.foundations()
        self.dynasties()
        self.ruins()
        self.deep_past()
        self.cults_and_outlaws()
        self.simulate()
        w.history.sort(key=lambda e: (e["year"], e["kind"] != "founded"))
        self.recent_news()
        w.politics["history_done"] = True
        w.politics["history_from"] = self.year0

    # ------------------------------------------------------------------ foundations
    def foundations(self) -> None:
        w = self.w
        founded = w.politics.setdefault("founded", {})
        for s in w.settlements:
            age = {"city": (300, 900), "town": (120, 500), "village": (60, 400), "hamlet": (20, 200),
                   "hold": (400, 2000), "elfhall": (800, 4000)}.get(s.kind, (50, 300))
            year = self.present - self.rng.randint(*age)
            founded[str(s.id)] = year
            if year >= self.year0 and s.kind in ("town", "city", "hold"):
                self.event(year, "founded", {"place": s.name}, importance=2, places=[s])
        for f in fx.active_factions(w):
            if f.founded >= self.year0 and f.kind in ("kingdom", "free_city", "knightly_order", "mages_circle",
                                                      "merchant_guild", "mercenary_company", "healers_guild",
                                                      "smiths_guild"):
                seat = w.settlements[f.seat] if f.seat >= 0 else None
                people = {"knightly_order": "knights", "mages_circle": "mages", "mercenary_company": "sell-swords"}.get(
                    f.kind, "members")
                if f.kind in ("kingdom", "free_city"):
                    self.event(f.founded, "chapter", {"people": "lords", "faction": f.name,
                                                      "place": seat.name if seat else "the old lands"},
                               importance=4, factions=[f], places=[seat] if seat else [])
                else:
                    self.event(f.founded, "chapter", {"people": people, "faction": f.name,
                                                      "place": seat.name if seat else "a back room"},
                               importance=2, factions=[f], places=[seat] if seat else [])

    # ------------------------------------------------------------------ rulers of the past
    def reign(self, race: str) -> int:
        lo, hi = self.data["reign"].get(race, self.data["reign"]["human"])
        return max(1, int(lo + (hi - lo) * self.rng.random() ** 1.6))  # most reigns are short

    def dynasties(self) -> None:
        w = self.w
        for f in fx.active_factions(w):
            leader = fx.leader_of(w, f)
            if leader is None or f.flags.get("minor"):
                continue
            if f.kind in ("bandit_gang", "pirate_crew", "cult"):
                continue  # short-lived; their founders are today's leaders
            dynastic = f.kind in DYNASTIC
            span = float(self.data["lifespan"].get(leader.race, 1.0))
            # When today's ruler came to power.
            took = self.present - min(self.reign(leader.race), max(1, leader.age(self.present) - int(16 * span)))
            start = max(self.year0, f.founded)
            chain = []
            successor = leader
            year = took
            family = leader.name.split()[-1]
            while year > start and len(chain) < 40:
                reign = self.reign(leader.race) if dynastic else self.rng.randint(5, 25)
                began = max(start, year - reign)
                death_age = int(self.rng.randint(38, 78) * span)
                cause_kind = self.rng.weighted(["old", "illness", "battle", "murder", "accident"],
                                               [4 if death_age > 60 * span else 1, 4, 2 if dynastic else 0, 1, 1])
                usurped = dynastic and f.kind == "kingdom" and self.rng.chance(0.08)
                if usurped:
                    family = self.rng.choice((self.t.names["cultures"].get(f.culture)
                                              or self.t.names["cultures"]["heartland"])["family"])
                pred = fx.make_figure(w, self.t, self.rng, f.culture, year=year, faction=f, role="past",
                                      family=family if dynastic else None, age=(death_age, death_age),
                                      race=leader.race)
                pred.title = fx.figure_title(self.t, f.kind, pred.sex, f.culture)
                pred.died = year
                pred.cause = self.rng.choice(self.data["causes"][cause_kind])
                if self.rng.chance(0.25):
                    pred.epithet = self.rng.choice(self.t.factions["words"]["epithet"])
                if dynastic and not usurped:
                    successor.parent = pred.id if successor.parent < 0 else successor.parent
                chain.append((pred, year, successor, usurped))
                successor = pred
                year = began
            chain.reverse()
            f.rulers = [pred.id for pred, *_ in chain] + [r for r in f.rulers if r not in {p.id for p, *_ in chain}]
            for pred, died, heir, usurped in chain:
                important = 4 if f.kind == "kingdom" else 3 if dynastic else 2
                if not dynastic:
                    if f.kind in ("temple", "free_city", "kingdom", "clan", "elven_realm") or self.rng.chance(0.25):
                        self.event(died, "elected", {"old": pred.full_name(), "cause": pred.cause,
                                                     "new": heir.full_name(), "faction": f.name},
                                   importance=2, factions=[f], figures=[pred.id, heir.id])
                    continue
                if usurped:
                    self.event(died, "crisis", {"old": pred.full_name(), "cause": pred.cause, "new": heir.full_name(),
                                                "house": "another line",
                                                "seat": SEAT_WORDS.get(f.kind, "seat")},
                               importance=important, factions=[f], figures=[pred.id, heir.id])
                else:
                    relation = "their son" if heir.sex == "male" else "their daughter"
                    self.event(died, "succession", {"old": pred.full_name(), "cause": pred.cause,
                                                    "new": heir.full_name(), "relation": relation,
                                                    "seat": SEAT_WORDS.get(f.kind, "seat")},
                               importance=important, factions=[f], figures=[pred.id, heir.id])

    # ------------------------------------------------------------------ ruins
    def ruins(self) -> None:
        w = self.w
        past = w.politics.setdefault("ruins", {})
        for site in w.sites:
            if site.kind != "ruin":
                continue
            year = self.present - self.rng.randint(15, 600)
            cause = self.rng.choice(self.data["ruin_causes"])
            was = self.rng.choice(["a village", "a hill fort", "a manor", "a small town", "a monastery", "a watchtower"])
            past[str(site.id)] = {"year": year, "cause": cause, "was": was}
            if year >= self.year0:
                name = site.name[:1].upper() + site.name[1:]
                self.event(year, "ruin", {"place": name, "cause": cause}, importance=2)

    # ------------------------------------------------------------------ dragons, legends, artifacts
    def deep_past(self) -> None:
        w = self.w
        size = {"small": 0, "medium": 1, "large": 2}.get(w.meta.size, 1)
        towns = [s for s in w.settlements if s.kind in ("village", "town", "city")]
        mountain_sites = [s for s in w.sites if s.kind in ("cave", "ruin") and
                          w.biome_ids[int(w.biome[s.x, s.y])] in ("mountains", "high_mountains", "hills")]
        legends = []
        n_legends = 3 + size + self.rng.randint(0, 2)
        for _ in range(n_legends):
            culture = self.rng.choice([s.culture for s in towns]) if towns else "heartland"
            year = self.rng.randint(self.year0 - 400, self.present - 20)
            hero = fx.make_figure(w, self.t, self.rng, culture, year=year, role="legend", age=(25, 60))
            hero.died = year
            hero.epithet = self.rng.choice(self.data["legends"]["epithets"])
            hero.cause = self.rng.choice(self.data["causes"]["battle"])
            legends.append((hero, year))
        dragons = []
        for i in range(1 + (size >= 1) + self.rng.randint(0, size)):
            name = f"{self.rng.choice(self.data['dragons']['names'])} {self.rng.choice(self.data['dragons']['epithets'])}"
            if any(d["name"] == name for d in dragons):
                continue
            color = self.rng.choice(self.data["dragons"]["colors"])
            year = self.rng.randint(self.year0 - 200, self.present - 15)
            victims = self.rng.sample(towns, min(len(towns), self.rng.randint(1, 3))) if towns else []
            for k, s in enumerate(victims):
                self.event(year + k * self.rng.randint(1, 12), "dragon", {"dragon": name, "place": s.name},
                           importance=4, places=[s])
            slain = legends and self.rng.chance(0.4)
            record = {"name": name, "color": color, "alive": not slain, "lair": -1,
                      "last_seen": year + 3 * len(victims)}
            if slain:
                hero, hyear = self.rng.choice(legends)
                hero.notes.append(f"slew the dragon {name}")
                self.event(max(hyear, record["last_seen"]), "dragon_slain",
                           {"legend": hero.full_name(), "dragon": name}, importance=4, figures=[hero.id])
            else:
                if mountain_sites:
                    lair = self.rng.choice(mountain_sites)
                    record["lair"] = lair.id
                self.event(record["last_seen"], "dragon_sleeps", {"dragon": name}, importance=3)
            dragons.append(record)
        # Every world keeps one wyrm asleep somewhere: a world with no dragon left in it is a poorer world.
        if mountain_sites and not any(d["alive"] and d["lair"] >= 0 for d in dragons):
            last = dragons[-1] if dragons else None
            if last is not None:
                last["alive"] = True
                last["lair"] = self.rng.choice(mountain_sites).id
                self.event(last["last_seen"], "dragon_sleeps", {"dragon": last["name"]}, importance=3)
        w.politics["dragons"] = dragons
        facs = fx.active_factions(w)
        sites = [s for s in w.sites if s.kind in ("ruin", "barrow", "tower", "cave")]
        for hero, year in legends:
            deed = self.rng.choice(self.data["legends"]["deeds"])
            values = {"place": self.rng.choice(towns).name if towns else "the old town",
                      "site": self.rng.choice(sites).name if sites else "the dark",
                      "faction": self.rng.choice(facs).name if facs else "the old order"}
            deed = textgen.fill(deed, self.rng, {}, values)
            deed = deed[:1].lower() + deed[1:]
            hero.notes.append(deed)
            self.event(year, "legend", {"legend": hero.full_name(), "deed": deed}, importance=3, figures=[hero.id])
        artifacts = []
        used = set()
        for _ in range(3 + size + self.rng.randint(0, 2)):
            kind, word = self.rng.choice(self.data["artifacts"]["kinds"])
            of = self.rng.choice(self.data["artifacts"]["of"])
            name = f"{word} of {of}"
            if name in used:
                continue
            used.add(name)
            site = self.rng.choice(sites) if sites else None
            fate = textgen.fill(self.rng.choice(self.data["artifacts"]["fates"]), self.rng, {},
                                {"site": site.name if site else "the dark"})
            fate = fate[:1].lower() + fate[1:]
            bearer, year = self.rng.choice(legends) if legends else (None, self.year0)
            artifacts.append({"name": name, "kind": kind, "site": site.id if site is not None and "stolen" not in fate
                              else -1, "bearer": bearer.id if bearer else -1, "found": False, "fate": fate})
            self.event(year, "artifact", {"artifact": name, "fate": fate}, importance=3,
                       figures=[bearer.id] if bearer else [])
        w.politics["artifacts"] = artifacts

    def cults_and_outlaws(self) -> None:
        w = self.w
        for c in fx.active_factions(w, "cult"):
            god = self.t.factions["faiths"].get(c.faith, {}).get("god", "a nameless god")
            towns = [w.settlements[i] for i in c.presence] if c.presence else []
            place = towns[0].name if towns else "the wild country"
            self.event(max(self.year0, c.founded), "cult", {"god": god, "place": place}, importance=2)
        for g in fx.active_factions(w, "bandit_gang"):
            area = w.areas[g.area] if g.area >= 0 else None
            self.event(max(self.year0, g.founded), "gang_new",
                       {"gang": g.name, "place": area.name if area else "the roads"}, importance=1, factions=[g])

    # ------------------------------------------------------------------ the engine, over the centuries
    def simulate(self) -> None:
        w = self.w
        saved = {f.id: f.military for f in fx.active_factions(w)}
        for f in fx.active_factions(w):
            f.flags["base_military"] = f.military
        for year in range(self.year0, self.present):
            rng = self.rng.child(f"year/{year}")
            day = day_of_year(self.t, year, rng)
            engine = Politics(w, self.t, rng, history=True, year=year, day=day)
            engine.advance(365)
            # Armies recover between the years.
            for f in fx.active_factions(w):
                base = saved.get(f.id, f.military)
                f.military = min(base, int(f.military + base * 0.25))
        for f in fx.active_factions(w):
            if f.id in saved and not any(war["active"] and f.id in (war["attacker"], war["defender"])
                                         for war in w.wars):
                f.military = saved[f.id]
        w.politics.pop("told_conquests", None)

    def recent_news(self) -> None:
        """What happened in the last year or two is still talked about."""
        w = self.w
        for e in w.history:
            if e["year"] < self.present - RECENT_YEARS or e.get("importance", 2) < 2:
                continue
            place = None
            for pid in e.get("places", []):
                if 0 <= pid < len(w.settlements):
                    s = w.settlements[pid]
                    place = (s.x, s.y)
                    break
            if place is None:
                for fid in e.get("factions", []):
                    f = w.factions.get(fid)
                    place = news.faction_place(w, f) if f is not None else None
                    if place is not None:
                        break
            if place is None:
                continue
            ago = self.present - e["year"]
            day = -self.rng.uniform(3, 150) if ago <= 1 else -self.rng.uniform(150, 330)
            news.add(w, e["text"], place[0], place[1], kind=e["kind"], importance=e.get("importance", 2),
                     factions=e.get("factions", []), places=e.get("places", []), day=day)


def remember(world, year: int, kind: str, text: str, *, importance: int = 2, factions=(), places=(), sites=(),
             figures=(), player: bool = False, data: dict | None = None) -> dict:
    """Write something into the world's history while the game is played (it keeps its order: today is last)."""
    e = {"id": int(world.politics.get("next_event", len(world.history))), "year": int(year), "kind": kind,
         "text": text, "importance": int(max(1, min(5, importance))), "factions": [int(f) for f in factions],
         "places": [int(p) for p in places], "figures": [int(h) for h in figures]}
    if sites:
        e["sites"] = [int(s) for s in sites]
    if player:
        e["player"] = True
    if data:
        e["data"] = data
    world.politics["next_event"] = e["id"] + 1
    world.history.append(e)
    return e


def generate_history(world, tables, rng: RNG) -> None:
    HistoryMaker(world, tables, rng).run()


def ensure_history(world, tables) -> bool:
    """Worlds made before the history existed get one when first loaded. True if made now."""
    if world.politics.get("history_done"):
        return False
    generate_history(world, tables, world.rng.child("history-late"))
    return True


# ---------------------------------------------------------------------------- the chronicle
ERA_YEARS = 50
WAR_GROUP = "war"
WAR_KINDS_TOLD = ("war", "peace", "battle", "taken", "sacked", "siege", "relieved", "rebellion", "freedom", "crushed")


def present_lines(world, tables) -> list[str]:
    """Who rules the great realms today, and who is at war."""
    year = tables.calendar.at(world.time).year
    out = []
    for f in fx.active_factions(world, "kingdom", "free_city", "elven_realm", "clan"):
        if f.liege >= 0:
            continue
        leader = fx.leader_of(world, f)
        if leader is not None and leader.alive:
            out.append(f"{f.name[:1].upper() + f.name[1:]} is ruled by {leader.full_name()}, "
                       f"{leader.age(year)} years old.")
    for war in world.wars:
        if war.get("active"):
            a, d = world.factions.get(war["attacker"]), world.factions.get(war["defender"])
            if a is not None and d is not None:
                out.append(f"{a.name[:1].upper() + a.name[1:]} is at war with {d.name}.")
    return out


def pick_events(events: list[dict], most: int = 6) -> list[dict]:
    """The events a chronicler would choose from a stretch of years: the greatest first, few of one kind."""
    best, per_group = [], {}
    for e in sorted(events, key=lambda e: (-e.get("importance", 2), e["year"], e.get("id", 0))):
        group = WAR_GROUP if e["kind"] in WAR_KINDS_TOLD else e["kind"]
        if per_group.get(group, 0) >= (3 if group == WAR_GROUP else 1):
            continue
        per_group[group] = per_group.get(group, 0) + 1
        best.append(e)
        if len(best) >= most:
            break
    best.sort(key=lambda e: (e["year"], e.get("id", 0)))
    return best


def lower_first(text: str) -> str:
    """'The dragon...' -> 'the dragon...' after 'In 812,' (names and people keep their capitals)."""
    for article in ("The ", "A ", "An "):
        if text.startswith(article):
            return article.lower() + text[len(article):]
    return text


def chronicle_by_ages(world, tables) -> dict:
    """The chronicle of a world that lived its history (world/ages): told age by age."""
    eras = world.politics["eras"]
    now = tables.calendar.at(world.time).year
    events = [e for e in world.history if e.get("importance", 2) >= 3 and e.get("text")]
    paras = []
    myth = eras[0]
    old = pick_events([e for e in events if e["year"] < myth["end"]], 5)
    first = f"Of {myth['name']} little is certain. {myth.get('summary', '')}".strip()
    if old:
        first += " " + " ".join(e["text"] for e in old)
    paras.append(first)
    for era in eras[1:]:
        span = [e for e in events if era["start"] <= e["year"] < era["end"]]
        great = [e for e in span if e.get("importance", 2) >= 4] or span
        chosen = pick_events(great)
        name = era["name"][:1].upper() + era["name"][1:]
        text = f"{name}, from {era['start']} to {era['end'] - 1}. {era.get('summary', '')}".strip()
        if chosen:
            text += " " + " ".join(f"In {e['year']}, {lower_first(e['text'])}" for e in chosen)
        paras.append(text)
    today = present_lines(world, tables)
    if today:
        paras.append(f"And now, in the year {now}: " + " ".join(today))
    return {"title": f"A Chronicle of {world.meta.name}", "text": "\n\n".join(paras), "source": "fallback"}


def chronicle_fallback(world, tables) -> dict:
    """A chronicle in built-in words: the deep past, then the centuries by era, then today."""
    if world.politics.get("eras"):
        return chronicle_by_ages(world, tables)
    start = int(world.politics.get("history_from", tables.calendar.start_year - 250))
    events = [e for e in world.history if e.get("importance", 2) >= 3]
    paras = []
    old = [e for e in events if e["year"] < start]
    if old:
        paras.append("Of the old days little is certain. " + " ".join(e["text"] for e in old[:6]))
    year = start
    now = tables.calendar.at(world.time).year
    while year < now:
        era = [e for e in events if year <= e["year"] < year + ERA_YEARS]
        if era:
            best, per_group = [], {}
            for e in sorted(era, key=lambda e: (-e.get("importance", 2), e["year"])):
                group = WAR_GROUP if e["kind"] in WAR_KINDS_TOLD else e["kind"]
                if per_group.get(group, 0) >= (3 if group == WAR_GROUP else 1):
                    continue
                per_group[group] = per_group.get(group, 0) + 1
                best.append(e)
                if len(best) >= 6:
                    break
            best.sort(key=lambda e: e["year"])
            paras.append(f"{year} to {min(now, year + ERA_YEARS - 1)}. " +
                         " ".join(f"In {e['year']}: {e['text']}" for e in best))
        year += ERA_YEARS
    today = present_lines(world, tables)
    if today:
        paras.append(f"And now, in the year {now}: " + " ".join(today))
    return {"title": f"A Chronicle of {world.meta.name}", "text": "\n\n".join(paras)}
