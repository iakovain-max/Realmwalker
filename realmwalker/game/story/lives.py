"""Lives of townsfolk (Expansion 6 C.4, docs/ADVENTURES.md §5.16, §8.10; data lives.json).

A life is kept on the person, `npc.flags["life"]` (saved with the NPC, JSON-native):
    {"ties": [{"kind": "son", "name": "Ivo", "npc": 813 | None, "figure": id | None, "state": "alive"}],
     "want": id, "fear": id, "secrets": [{"kind": "debt", "to": "Odo", "known": False}],
     "things": [{"kind": "heirloom", "words": "..."}], "events": [{"day", "kind", ...}]}
Kin are names first (`npc` None) and become people only when a story needs them; those who share a house are tied by
their ids, and a figure of the history brings the family the history gave them. The person's words (`npc.profile`
want, fear, secret) are written from the life, so there is one source.

    ensure(game, sid)         the notables and up to `others` more get a life (from people.populate_town and
                              story.on_enter_town); returns how many were made
    daily(game)               from story.daily: shows that are over are put away; every `every` days, `week`
    week(game)                life events in the peopled towns within `reach` of the hero (at most `per_town` a town)
    seeds(game, sid)          the events marked as a story's seed (for situations, C.6)
The events show by themselves: mourning dress (`flags["dress"]`, dolls), a shop shut with a sign (`closed_until`:
`sign`, read by services and the game's walking in), staying at home (`home_until`, townlife.activity), what they say
in passing (`bark`), a new grave (remains), and a crowd at the grave or the temple (`gather`, from townlife's tick).
`note` is what they tell you of it when you ask about them.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

MAX_EVENTS = 8
REST_DAYS = 42  # the same kind of event does not come to the same person again for six weeks
DAY = 1440
KIN_WORDS = {"spouse": ("husband", "wife"), "child": ("son", "daughter"), "parent": ("father", "mother"),
             "sibling": ("brother", "sister")}
KIN_OF = {"husband": "spouse", "wife": "spouse", "son": "child", "daughter": "child", "father": "parent",
          "mother": "parent", "brother": "sibling", "sister": "sibling"}
REVERSE = {"spouse": "spouse", "child": "parent", "parent": "child", "sibling": "sibling"}


def data(game) -> dict:
    return getattr(game.tables, "lives", None) or {}


def life(npc) -> dict | None:
    return npc.flags.get("life")


def _days(game) -> int:
    return int(game.world.time) // DAY


# ---------------------------------------------------------------------------- making lives
def ensure(game, sid: int) -> int:
    """Give the notables of a peopled town, and up to `others` more, their lives (once)."""
    d = data(game)
    w = game.world
    town = w.towns.get(sid)
    if not d or town is None or not town.npcs:
        return 0
    folk = [w.npcs[i] for i in town.npcs if i in w.npcs and w.npcs[i].alive and not w.npcs[i].flags.get("visitor")
            and w.npcs[i].job not in ("wayfarer", "adventurer", "pilgrim")]
    if all("life" in n.flags for n in folk if n.notable) and sum("life" in n.flags for n in folk) >= \
            min(len(folk), int(d["others"]) + sum(n.notable for n in folk)):
        return 0
    rng = w.rng.child(f"lives/{sid}")
    others = sorted((n for n in folk if not n.notable and n.job != "child"), key=lambda n: n.id)
    rng.shuffle(others)
    chosen = [n for n in folk if n.notable] + others[:int(d["others"])]
    houses: dict[tuple, list] = {}
    for n in folk:
        houses.setdefault(tuple(n.home), []).append(n)
    made = 0
    for npc in chosen:
        if "life" in npc.flags:
            continue
        npc.flags["life"] = make(game, npc, houses.get(tuple(npc.home), []), folk, rng.child(str(npc.id)))
        write_profile(game, npc, rng.child(f"words/{npc.id}"))
        made += 1
    return made


def _kin(npc, other) -> str | None:
    """How someone under the same roof is kin to this person (a word: wife, son, father, sister), or None."""
    if other is npc or other.job in ("serving_hand",) or npc.job == "serving_hand":
        return None
    gap = other.age - npc.age
    she = other.sex == "female"
    if gap <= -16:
        return KIN_WORDS["child"][she]
    if gap >= 16:
        return KIN_WORDS["parent"][she]
    if other.sex != npc.sex and npc.age >= 18 and other.age >= 18 and abs(gap) <= 12:
        return KIN_WORDS["spouse"][she]
    return KIN_WORDS["sibling"][she]


def make(game, npc, house: list, folk: list, rng) -> dict:
    """A life for this person: ties (their household, their family in the history, kin by name), a want, a fear,
    secrets and things of note, by their trade, age, nature and wealth (data lives.json)."""
    d = data(game)
    ties: list[dict] = []
    have = set()
    spouse_taken = False
    for other in sorted(house, key=lambda n: n.id):
        kind = _kin(npc, other)
        if kind is None or (KIN_OF[kind] == "spouse" and spouse_taken):
            continue
        spouse_taken = spouse_taken or KIN_OF[kind] == "spouse"
        ties.append(_tie(kind, other.first_name, npc=other.id, state="alive" if other.alive else "dead"))
    fig = game.world.figures.get(npc.flags.get("figure", -1))
    if fig is not None:
        ties += _figure_kin(game, fig, {t["npc"] for t in ties})
    have = {KIN_OF.get(t["kind"], t["kind"]) for t in ties}
    from realmwalker.world.names import forge

    nf = forge(game.world, game.tables)
    taken = {t["name"] for t in ties} | {n.first_name for n in folk}  # (kin by name are not the neighbours)

    def name(sex: str) -> str:
        n = nf.given(npc.culture, sex, rng, avoid=taken)
        taken.add(n)
        return n

    kin = d["kin"]
    if "spouse" not in have and npc.age >= 18 and npc.job not in ("monk", "acolyte", "beggar") \
            and rng.chance(float(kin["spouse"]) * (0.6 if npc.age < 24 else 1.0)):
        sex = "male" if npc.sex == "female" else "female"
        state = "dead" if npc.age >= 55 and rng.chance(0.35) else "alive"
        ties.append(_tie(KIN_WORDS["spouse"][sex == "female"], name(sex), state=state))
        have.add("spouse")
    gap = min(40, npc.age - 16)  # (the oldest a child of theirs can be is their age less sixteen)
    if "child" not in have and gap >= 1 and npc.job not in ("monk", "acolyte"):
        lo, hi = kin["children"]
        most = min(int(hi), 1 + (npc.age - 17) // 4)
        for _ in range(rng.randint(min(int(lo), most), most) if "spouse" in have or rng.chance(0.3) else 0):
            sex = rng.choice(["male", "female"])
            ties.append(_tie(KIN_WORDS["child"][sex == "female"], name(sex), state="dead" if rng.chance(0.08) else "alive",
                             age=npc.age - 16 - rng.randint(0, gap - 1)))
    if "parent" not in have:
        for sex in ("male", "female"):
            alive = rng.chance(float(kin["parent"]) * max(0.0, (60 - npc.age) / 40))
            if alive or rng.chance(0.25):
                ties.append(_tie(KIN_WORDS["parent"][sex == "female"], name(sex), state="alive" if alive else "dead"))
    if "sibling" not in have and rng.chance(float(kin["sibling"])):
        sex = rng.choice(["male", "female"])
        ties.append(_tie(KIN_WORDS["sibling"][sex == "female"], name(sex), state="alive"))
    ties += _others(game, npc, folk, d, rng, name)
    lf = {"ties": ties, "want": None, "fear": None, "secrets": [], "things": [], "events": []}
    lf["want"] = _pick(d["wants"], npc, lf, rng)
    lf["fear"] = _pick(d["fears"], npc, lf, rng)
    lf["secrets"] = _secrets(game, npc, lf, d, rng)
    for kind, spec in d["things"].items():
        if npc.social in spec.get("social", ["low", "middle", "high"]) and \
                rng.chance({"high": 0.35, "middle": 0.22, "low": 0.1}[npc.social]):
            lf["things"].append({"kind": kind, "words": rng.choice(spec["words"]), "state": "kept"})
    return lf


def _tie(kind: str, name: str, *, npc: int | None = None, figure: int | None = None, state: str = "alive",
         age: int | None = None) -> dict:
    t = {"kind": kind, "name": name, "npc": npc, "figure": figure, "state": state}
    if age is not None:
        t["age"] = int(age)
    return t


def _figure_kin(game, fig, known: set) -> list[dict]:
    """A figure of the history brings the family the history gave them (spouse, parents, children)."""
    figs = game.world.figures
    out = []

    def add(kind_key: str, f) -> None:
        if f is None or f.kind != "person" or (f.npc in known and f.npc != -1):
            return
        word = KIN_WORDS[kind_key][f.sex == "female"]
        out.append(_tie(word, f.name.split()[0], npc=f.npc if f.npc != -1 else None, figure=f.id,
                        state="alive" if f.alive else "dead"))

    add("spouse", figs.get(fig.spouse))
    add("parent", figs.get(fig.father))
    add("parent", figs.get(fig.mother))
    kids = [f for f in figs.values() if fig.id in (f.parent, f.mother, f.father) and f.id != fig.id]
    for f in sorted(kids, key=lambda f: f.born)[:4]:
        add("child", f)
    return out


def _others(game, npc, folk: list, d: dict, rng, name) -> list[dict]:
    """A lover, a rival, a creditor, a patron, an enemy: people of the town where one fits, else a name."""
    out = []
    pool = [n for n in folk if n is not npc and n.job != "child"]
    for kind, p in d["ties"].items():
        if not rng.chance(float(p)) or (kind == "lover" and npc.age < 16):
            continue
        if kind == "creditor":
            fits = [n for n in pool if n.job in ("moneylender", "lord", "innkeeper", "shopkeeper") or n.social == "high"]
        elif kind == "patron":
            fits = [n for n in pool if n.notable and n.social != "low"]
        elif kind == "rival":
            fits = [n for n in pool if n.job == npc.job or n.social == npc.social]
        elif kind == "lover":
            fits = [n for n in pool if n.sex != npc.sex and n.age >= 16 and abs(n.age - npc.age) <= 15]
        else:
            fits = pool
        other = rng.choice(fits) if fits else None
        if other is not None:
            out.append(_tie(kind, other.first_name, npc=other.id))
        elif kind != "patron":
            out.append(_tie(kind, name(rng.choice(["male", "female"]))))
    return out


def _has(lf: dict, need: str) -> bool:
    for t in lf["ties"]:
        if t["state"] != "alive":
            continue
        if t["kind"] == need or KIN_OF.get(t["kind"]) == need or (need == "kin" and t["kind"] in KIN_OF):
            return True
    return False


def _fits(spec: dict, npc, lf: dict) -> bool:
    if spec.get("needs") and not _has(lf, spec["needs"]):
        return False
    if spec.get("not") and _has(lf, spec["not"]):
        return False
    if spec.get("social") and npc.social not in spec["social"]:
        return False
    return not spec.get("forced")


def _pick(table: dict, npc, lf: dict, rng) -> str | None:
    """A want or a fear: those of their trade, nature and ties weigh more than those anyone might have."""
    ids, weights = [], []
    for k, spec in sorted(table.items()):
        if not _fits(spec, npc, lf):
            continue
        weight = 1.0
        if spec.get("jobs"):
            if npc.job not in spec["jobs"]:
                continue
            weight += 2.0
        if spec.get("traits"):
            if not set(spec["traits"]) & set(npc.traits):
                continue
            weight += 2.0
        if spec.get("needs"):
            weight += 2.5
        ids.append(k)
        weights.append(weight)
    return rng.weighted(ids, weights) if ids else None


def _secrets(game, npc, lf: dict, d: dict, rng) -> list[dict]:
    """Secrets: the faith or the guild they hide (people.secret_members), then perhaps one more by their nature."""
    out = []
    hidden = game.world.factions.get(npc.flags.get("secret", -1)) if npc.flags.get("secret") is not None else None
    if hidden is not None:
        out.append({"kind": "faith" if hidden.kind == "cult" else "guild", "faction": hidden.id, "known": False})
    if rng.chance(float(d["secret_chance"])):
        fits = {k: s for k, s in d["secrets"].items() if _fits(s, npc, lf)
                and (not s.get("traits") or set(s["traits"]) & set(npc.traits))}
        if fits:
            kind = rng.weighted(sorted(fits), [3.0 if fits[k].get("needs") else 1.0 for k in sorted(fits)])
            rec = {"kind": kind, "known": False}
            need = d["secrets"][kind].get("needs")
            if need:
                rec["to"] = _tie_of(lf, need)["name"]
            out.append(rec)
    return out


def _tie_of(lf: dict, need: str) -> dict | None:
    for t in lf["ties"]:
        if t["state"] == "alive" and (t["kind"] == need or KIN_OF.get(t["kind"]) == need):
            return t
    return None


# ---------------------------------------------------------------------------- words
def values(game, npc, lf: dict | None = None) -> dict:
    """The words a life's templates fill: pronouns, and each tie's name by its kind (the first living one)."""
    from realmwalker.game.people import pronouns

    lf = lf or life(npc) or {"ties": []}
    v = dict(pronouns(npc))
    v.update({"Their": v["their"].capitalize(), "Them": v["them"].capitalize(), "were": "was"})
    s = game.world.settlements[npc.settlement] if 0 <= npc.settlement < len(game.world.settlements) else None
    v["town"] = s.name if s is not None else "this place"
    for t in lf["ties"]:
        if t["state"] not in ("alive", "levied"):
            continue
        for key in (t["kind"], KIN_OF.get(t["kind"])):
            if key and key not in v:
                v[key] = t["name"]
    return v


def fill(text: str, vals: dict) -> str:
    for k, val in vals.items():
        text = text.replace("{" + k + "}", str(val))
    return text


def write_profile(game, npc, rng) -> None:
    """The person's words (want, fear, secret) written from their life: one source."""
    d = data(game)
    lf = life(npc)
    if not lf:
        return
    vals = values(game, npc, lf)
    if lf.get("want") and not npc.flags.get("grudge"):  # (a blood feud of the history keeps its own words)
        npc.profile["want"] = fill(rng.choice(d["wants"][lf["want"]]["words"]), vals)
    if lf.get("fear"):
        npc.profile["fear"] = fill(rng.choice(d["fears"][lf["fear"]]["words"]), vals)
    if lf["secrets"]:
        sec = lf["secrets"][0]
        v = dict(vals)
        if sec.get("to"):
            v.update({"creditor": sec["to"], "lover": sec["to"]})
        npc.profile["secret"] = fill(rng.choice(d["secrets"][sec["kind"]]["words"]), v)
    else:
        npc.profile.pop("secret", None)


def family_line(game, npc) -> str | None:
    """Who they have, in a sentence ('She has a husband, Odo, and two children, Ivo and Mette.')."""
    lf = life(npc)
    if not lf:
        return None
    from realmwalker.game.people import pronouns

    p = pronouns(npc)
    living = [t for t in lf["ties"] if t["kind"] in KIN_OF and t["state"] == "alive"]
    spouse = [t for t in living if KIN_OF[t["kind"]] == "spouse"]
    kids = [t for t in living if KIN_OF[t["kind"]] == "child"]
    parts = [f"a {spouse[0]['kind']}, {esc(spouse[0]['name'])}" + ("," if kids else "")] if spouse else []
    if len(kids) == 1:
        parts.append(f"a {kids[0]['kind']}, {esc(kids[0]['name'])}")
    elif kids:
        names = [esc(t["name"]) for t in kids]
        count = ("two", "three", "four", "five", "six")[min(len(kids), 6) - 2]
        parts.append(f"{count} children, {', '.join(names[:-1])} and {names[-1]}")
    dead = [t for t in lf["ties"] if KIN_OF.get(t["kind"]) == "spouse" and t["state"] == "dead"]
    if not parts:
        return f"{p['They']} {p['are']} a widow{'er' if npc.sex == 'male' else ''}." if dead else None
    return f"{p['They']} {p['have']} {' and '.join(parts)}."


def _ago(game, day: int) -> str:
    n = _days(game) - int(day)
    if n <= 0:
        return "today"
    if n == 1:
        return "yesterday"
    if n < 7:
        return f"{n} days ago"
    return "last week" if n < 14 else f"{n // 7} weeks ago"


def _event_vals(game, npc, ev: dict) -> dict:
    vals = values(game, npc)
    vals.update({"kin": ev.get("kin", ""), "name": esc(ev.get("name", "")), "ago": _ago(game, ev["day"]),
                 "thing": ev.get("thing", "something"), "rival": esc(ev.get("rival", vals.get("rival", "a neighbour"))),
                 "lover": esc(ev.get("lover", vals.get("lover", "someone"))),
                 "creditor": esc(ev.get("creditor", vals.get("creditor", "the moneylender")))})
    return vals


def _show(npc, game) -> dict | None:
    sh = npc.flags.get("life_show")
    if sh and int(sh["until"]) > int(game.world.time):
        return sh
    return None


def note(game, npc) -> str | None:
    """What they tell you of their latest life event while it still shows (asked about themselves)."""
    lf = life(npc)
    sh = _show(npc, game)
    if not lf or sh is None or not lf["events"] or not npc.alive:
        return None
    ev = lf["events"][-1]
    spec = data(game)["events"].get(ev["kind"])
    if spec is None:
        return None
    text = spec["note"][(npc.id + int(ev["day"])) % len(spec["note"])]
    return fill(text, _event_vals(game, npc, ev))


def bark(game, npc, roll: int) -> str | None:
    """What they say in passing while their life event shows (six times in ten), else None."""
    sh = _show(npc, game)
    if sh is None or roll % 10 >= 6:
        return None
    lf = life(npc)
    ev = lf["events"][-1] if lf and lf["events"] else None
    spec = data(game)["events"].get(sh["kind"]) if ev is not None else None
    if spec is None:
        return None
    lines = spec["bark"]
    return fill(lines[(roll // 10) % len(lines)], _event_vals(game, npc, ev))


def sign(game, npc) -> str | None:
    """The sign on a shut shop's door, or None when it is open."""
    if int(npc.flags.get("closed_until", 0)) <= int(game.world.time):
        return None
    lf = life(npc)
    ev = lf["events"][-1] if lf and lf["events"] else {"kind": "sickness", "day": _days(game)}
    spec = data(game)["events"].get(ev["kind"], {})
    lines = spec.get("sign") or data(game)["events"]["sickness"]["sign"]
    return fill(lines[npc.id % len(lines)], _event_vals(game, npc, ev))


def walk_in(game, lm, building) -> str | None:
    """Walking into a building whose keeper has shut it: the sign on the door (a line for the log)."""
    from realmwalker.game.people import settlement_of

    s = settlement_of(game, lm)
    if s is None or building not in lm.buildings:
        return None
    bi = lm.buildings.index(building)
    w = game.world
    for i in w.towns[s.id].npcs if s.id in w.towns else []:
        n = w.npcs.get(i)
        if n is not None and n.alive and n.building == bi:
            words = sign(game, n)
            if words:
                return f"The place is shut. A sign on the door: <story>\"{words}\"</>"
    return None


# ---------------------------------------------------------------------------- the weeks
def daily(game) -> None:
    """Once a day (story.daily): put away what no longer shows; every `every` days, a week of lives."""
    d = data(game)
    if not d:
        return
    now = int(game.world.time)
    for town in game.world.towns.values():
        flags = town.flags
        if flags.get("life_gathering") and int(flags["life_gathering"]["until"]) <= now:
            flags.pop("life_gathering", None)
            if (flags.get("gathering") or {}).get("life"):
                flags.pop("gathering", None)
    for npc in game.world.npcs.values():
        f = npc.flags
        if f.get("dress") == "mourning" and int(f.get("mourning_until", 0)) <= now:
            f.pop("dress", None)
            f.pop("mourning_until", None)
        for key in ("closed_until", "home_until"):
            if key in f and int(f[key]) <= now:
                del f[key]
        if "life_show" in f and int(f["life_show"]["until"]) <= now:
            del f["life_show"]
    rec = game.world.politics.setdefault("lives", {"day": -999})
    today = _days(game)
    if today - int(rec.get("day", -999)) >= int(d["every"]):
        rec["day"] = today
        week(game)


def week(game) -> list[tuple[int, int, str]]:
    """A week of lives in the peopled towns within reach of the hero: (settlement, npc, event kind) for each."""
    d = data(game)
    w = game.world
    px, py = game.player.x, game.player.y
    reach = int(d["reach"])
    out = []
    for sid in sorted(w.towns):
        town = w.towns[sid]
        if not town.npcs or not 0 <= sid < len(w.settlements):
            continue
        s = w.settlements[sid]
        if max(abs(s.x - px), abs(s.y - py)) > reach:
            continue
        ensure(game, sid)
        rng = w.rng.child(f"lives/week/{sid}/{_days(game)}")
        people = [w.npcs[i] for i in town.npcs if i in w.npcs and w.npcs[i].alive and "life" in w.npcs[i].flags]
        rng.shuffle(people)
        n = 0
        for npc in people:
            if n >= int(d["per_town"]):
                break
            if _show(npc, game) is not None:
                continue
            kinds = sorted(EVENTS)
            rng.shuffle(kinds)
            lately = {e["kind"] for e in npc.flags["life"]["events"] if _days(game) - int(e["day"]) < REST_DAYS}
            for kind in kinds:
                spec = d["events"].get(kind)
                if spec is None or kind in lately:
                    continue
                can, do = EVENTS[kind]
                odds = can(game, s, npc, npc.flags["life"])
                if odds and rng.chance(min(0.9, float(spec["chance"]) * odds)):
                    if happen(game, s, npc, kind, rng.child(f"{kind}/{npc.id}")):
                        out.append((sid, npc.id, kind))
                        n += 1
                    break
    return out


def happen(game, s, npc, kind: str, rng) -> dict | None:
    """One life event, now: its effects, its record on the life (and a seed for a story, by chance), its show."""
    spec = data(game)["events"][kind]
    ev = EVENTS[kind][1](game, s, npc, npc.flags["life"], rng)
    if ev is None:
        return None
    ev.update({"day": _days(game), "kind": kind})
    if ev.get("self"):  # (their own death: the family's lives carry it, and their record keeps the day)
        npc.flags["life"]["events"].append(ev)
        return ev
    if rng.chance(float(spec["seed"])):
        ev["seed"] = True
    record(game, npc, ev, rng.randint(*spec["days"]))
    return ev


def record(game, npc, ev: dict, days: int) -> None:
    lf = npc.flags["life"]
    lf["events"] = (lf["events"] + [ev])[-MAX_EVENTS:]
    npc.flags["life_show"] = {"kind": ev["kind"], "until": int(game.world.time) + int(days) * DAY}


def seeds(game, sid: int) -> list[tuple[int, dict]]:
    """The life events of a town marked as the seed of a story (npc id, event), newest first (situations, C.6)."""
    w = game.world
    town = w.towns.get(sid)
    out = []
    for i in town.npcs if town is not None else []:
        n = w.npcs.get(i)
        for ev in (life(n) or {}).get("events", []) if n is not None else []:
            if ev.get("seed") and not ev.get("used"):
                out.append((i, ev))
    return sorted(out, key=lambda p: -int(p[1]["day"]))


# ---------------------------------------------------------------------------- the events
# Each: can(game, s, npc, life) -> a factor on the data's chance (0: cannot), do(...) -> the event's record or None.
EVENTS: dict = {}


def event(kind: str):
    def reg(pair):
        EVENTS[kind] = pair
        return pair
    return reg


def _marks(s) -> list[str]:
    from realmwalker.world import marks

    return marks.marks_of(s)


def _lm(game, s):
    from realmwalker.world.local import local_key

    lm = game.world.local_maps.get(local_key(s.x, s.y))
    return lm if lm is not None and lm.kind == "settlement" else None


def _shut(game, npc, days: float, home: bool) -> None:
    """A trade shut for a while (with a sign on the door); `home`: they keep to the house."""
    until = int(game.world.time + days * DAY)
    from realmwalker.game import economy

    if npc.building >= 0 or economy.shop_spec(game, npc) is not None:
        npc.flags["closed_until"] = max(until, int(npc.flags.get("closed_until", 0)))
    if home:
        npc.flags["home_until"] = max(until, int(npc.flags.get("home_until", 0)))


def _mourn(game, npc, days: int) -> None:
    npc.flags["dress"] = "mourning"
    npc.flags["mourning_until"] = max(int(game.world.time) + days * DAY, int(npc.flags.get("mourning_until", 0)))


def _grave(game, s, who: dict) -> tuple[int, int] | None:
    """A fresh grave in the town's graveyard (remains.py's own: listed in lm.meta["graves"])."""
    lm = _lm(game, s)
    if lm is None:
        return None
    from realmwalker.game import remains
    from realmwalker.game.dungeon import set_terrain

    spot = remains._grave_spot(game, lm)
    if spot is None:
        return None
    set_terrain(lm, spot[0], spot[1], "grave_fresh")
    lm.meta.setdefault("graves", []).append({"x": spot[0], "y": spot[1], "who": who, "day": game.world.time / DAY})
    return spot


def _gathering(game, s, kind: str, spot, ids: list[int], start_day: int, hours: tuple[int, int], rng,
               name: str = "") -> None:
    """A crowd for a day's hours (a funeral at the grave, a wedding or a christening at the temple): townlife makes it
    when its time comes (`gather`)."""
    from realmwalker.game.people import town_of

    if spot is None:
        return
    town = town_of(game.world, s.id)
    w = game.world
    neighbours = [i for i in town.npcs if i in w.npcs and w.npcs[i].alive and i not in ids
                  and w.npcs[i].job not in ("guard", "soldier") and not w.npcs[i].flags.get("stays")]
    ids = list(ids) + rng.sample(sorted(neighbours), min(len(neighbours), rng.randint(5, 9)))
    lines = [fill(m, {"name": esc(name)}) for m in data(game)["events"][kind].get("murmur") or []]
    town.flags["life_gathering"] = {"kind": kind, "spot": [int(spot[0]), int(spot[1])], "ids": ids, "radius": 2,
                                    "from": (start_day * 24 + hours[0]) * 60, "until": (start_day * 24 + hours[1]) * 60,
                                    "murmur": lines}


def _temple_door(game, s):
    lm = _lm(game, s)
    if lm is None:
        return None
    b = next((b for b in lm.buildings if b.kind == "temple"), None)
    return tuple(b.door) if b is not None else None


def gather(game, flags: dict) -> None:
    """From townlife's tick: a life's crowd forms when its hours come, and goes when they are over (never over a
    story's own gathering)."""
    g = flags.get("life_gathering")
    if not g:
        return
    now = int(game.world.time)
    cur = flags.get("gathering")
    if int(g["from"]) <= now < int(g["until"]):
        if cur is None:
            flags["gathering"] = {"spot": list(g["spot"]), "ids": list(g["ids"]), "radius": g["radius"],
                                  "until": g["until"], "life": g["kind"], "murmur": list(g["murmur"])}
    elif now >= int(g["until"]):
        flags.pop("life_gathering", None)
        if cur is not None and cur.get("life"):
            flags.pop("gathering", None)


def _can_die(game, s, npc, lf) -> float:
    old = max(0.0, (npc.age - 58) / 8.0)
    parent = any(KIN_OF.get(t["kind"]) == "parent" and t["state"] == "alive" and t["npc"] is None
                 and t.get("figure") is None for t in lf["ties"])
    plague = 3.0 if "plague" in _marks(s) else 1.0
    return (old + (0.6 if parent else 0.0)) * plague if npc.job not in ("lord",) else 0.0


def _die(game, s, npc, lf, rng) -> dict | None:
    """A death of age: the old one themself (through the people code), or a parent who was only a name. The family
    mourn in black, the shop is shut, a fresh grave is dug and a crowd stands round it the next morning."""
    old = npc.age >= 60 and rng.chance(min(0.8, (npc.age - 58) / 12.0)) and not npc.flags.get("figure")
    if old:
        return _die_self(game, s, npc, lf, rng)
    parents = [t for t in lf["ties"] if KIN_OF.get(t["kind"]) == "parent" and t["state"] == "alive"
               and t["npc"] is None and t.get("figure") is None]
    if not parents:
        return None
    t = rng.choice(parents)
    t["state"] = "dead"
    _mourn(game, npc, rng.randint(14, 30))
    _shut(game, npc, rng.randint(1, 3), home=True)
    spot = _grave(game, s, {"name": t["name"]})
    _gathering(game, s, "death_of_age", spot, [npc.id], _days(game) + 1, (9, 11), rng, name=t["name"])
    return {"kin": t["kind"], "name": t["name"]}


def _die_self(game, s, npc, lf, rng) -> dict | None:
    w = game.world
    npc.alive = False
    npc.present = False
    from realmwalker.game import townlife

    townlife.forget_person(npc.id)
    if game.quests:
        from realmwalker.game import quests

        quests.on_npc_death(game, npc)
    spot = _grave(game, s, {"npc": npc.id})
    mourners = []
    for t in lf["ties"]:
        other = w.npcs.get(t["npc"]) if t["npc"] is not None else None
        if other is None or not other.alive or KIN_OF.get(t["kind"]) is None:
            continue
        olf = other.flags.get("life")
        word = KIN_WORDS[REVERSE[KIN_OF[t["kind"]]]][npc.sex == "female"]
        if olf is not None:
            for ot in olf["ties"]:
                if ot["npc"] == npc.id:
                    ot["state"] = "dead"
            ev = {"day": _days(game), "kind": "death_of_age", "kin": word, "name": npc.first_name, "who": npc.id}
            if rng.chance(float(data(game)["events"]["death_of_age"]["seed"])):
                ev["seed"] = True
            record(game, other, ev, rng.randint(*data(game)["events"]["death_of_age"]["days"]))
        _mourn(game, other, rng.randint(14, 30))
        _shut(game, other, rng.randint(1, 3), home=True)
        mourners.append(other.id)
    _gathering(game, s, "death_of_age", spot, mourners, _days(game) + 1, (9, 11), rng, name=npc.first_name)
    return {"kin": "", "name": npc.first_name, "who": npc.id, "self": True}


event("death_of_age")((_can_die, _die))


def _can_sicken(game, s, npc, lf) -> float:
    if int(npc.flags.get("home_until", 0)) > int(game.world.time):
        return 0.0
    m = _marks(s)
    return (4.0 if "plague" in m else 1.0) * (1.5 if "famine" in m else 1.0) * (1.5 if npc.age >= 55 else 1.0)


def _sicken(game, s, npc, lf, rng) -> dict:
    days = rng.randint(3, 8)
    _shut(game, npc, days, home=True)
    return {"name": npc.first_name}


event("sickness")((_can_sicken, _sicken))


def _can_owe(game, s, npc, lf) -> float:
    debt = any(sec["kind"] == "debt" for sec in lf["secrets"])
    return 2.0 if debt else (1.0 if _has(lf, "creditor") else 0.0)


def _owe(game, s, npc, lf, rng) -> dict | None:
    t = _tie_of(lf, "creditor")
    if t is None:
        return None
    npc.purse = max(0, int(npc.purse * 0.4))
    for sec in lf["secrets"]:
        if sec["kind"] == "debt":
            sec["due"] = _days(game) + rng.randint(7, 21)
    return {"creditor": t["name"], "name": t["name"], "to": t["npc"]}


event("debt_due")((_can_owe, _owe))


def _young_kin(lf) -> list[dict]:
    return [t for t in lf["ties"] if t["kind"] in ("son", "brother", "husband") and t["state"] == "alive"
            and t["npc"] is None and t.get("figure") is None and 16 <= int(t.get("age", 25)) <= 40]


def _can_levy(game, s, npc, lf) -> float:
    from realmwalker.world import factions as fx
    from realmwalker.world.politics import at_war

    realm = fx.realm_of_settlement(game.world, s)
    if realm is None or not at_war(game.world, realm.id) or not _young_kin(lf):
        return 0.0
    return 1.0


def _levy(game, s, npc, lf, rng) -> dict:
    t = rng.choice(_young_kin(lf))
    t["state"] = "levied"
    return {"kin": t["kind"], "name": t["name"]}


event("levy")((_can_levy, _levy))


def _can_wed(game, s, npc, lf) -> float:
    if _has(lf, "spouse") or not 18 <= npc.age <= 50 or npc.job in ("monk", "acolyte", "priest"):
        return 0.0
    return 3.0 if _has(lf, "lover") else 1.0


def _wed(game, s, npc, lf, rng) -> dict:
    lover = _tie_of(lf, "lover")
    sex = "male" if npc.sex == "female" else "female"
    word = KIN_WORDS["spouse"][sex == "female"]
    if lover is not None:
        lover["kind"] = word  # (the lover is the one they marry)
        lf["secrets"] = [x for x in lf["secrets"] if x["kind"] != "lover"]
        name, other = lover["name"], lover["npc"]
    else:
        from realmwalker.world.names import forge

        name = forge(game.world, game.tables).given(npc.culture, sex, rng, avoid={t["name"] for t in lf["ties"]})
        lf["ties"].append(_tie(word, name))
        other = None
    o = game.world.npcs.get(other) if other is not None else None
    if o is not None and o.flags.get("life"):
        for ot in o.flags["life"]["ties"]:
            if ot["npc"] == npc.id:
                ot["kind"] = KIN_WORDS["spouse"][npc.sex == "female"]
    if lf.get("want") == "spouse":
        lf["want"] = None
    _gathering(game, s, "marriage", _temple_door(game, s), [npc.id] + ([other] if o is not None else []),
               _days(game) + 1, (11, 13), rng)
    return {"kin": word, "name": name}


event("marriage")((_can_wed, _wed))


def _can_bear(game, s, npc, lf) -> float:
    if not _has(lf, "spouse"):
        return 0.0
    sp = _tie_of(lf, "spouse")
    mother_age = npc.age if npc.sex == "female" else int(sp.get("age", npc.age - 2))
    return 1.0 if 18 <= mother_age <= 42 else 0.0


def _bear(game, s, npc, lf, rng) -> dict:
    from realmwalker.world.names import forge

    sex = rng.choice(["male", "female"])
    name = forge(game.world, game.tables).given(npc.culture, sex, rng, avoid={t["name"] for t in lf["ties"]})
    word = KIN_WORDS["child"][sex == "female"]
    lf["ties"].append(_tie(word, name, age=0))
    sp = _tie_of(lf, "spouse")
    o = game.world.npcs.get(sp["npc"]) if sp and sp["npc"] is not None else None
    if o is not None and o.flags.get("life"):
        o.flags["life"]["ties"].append(_tie(word, name, age=0))
    _gathering(game, s, "birth", _temple_door(game, s), [npc.id] + ([o.id] if o is not None else []),
               _days(game) + 2, (10, 12), rng)
    return {"kin": word, "name": name}


event("birth")((_can_bear, _bear))


def _can_lose(game, s, npc, lf) -> float:
    kept = [t for t in lf["things"] if t.get("state", "kept") == "kept"]
    gangs = 2.0 if any(m in _marks(s) for m in ("gang", "lawless")) else 1.0
    return gangs if kept else 0.0


def _lose(game, s, npc, lf, rng) -> dict | None:
    kept = [t for t in lf["things"] if t.get("state", "kept") == "kept"]
    if not kept:
        return None
    t = rng.choice(kept)
    t["state"] = "stolen"
    short = data(game)["things"].get(t["kind"], {}).get("short", "something")
    return {"thing": short, "what": t["kind"]}


event("theft")((_can_lose, _lose))


def _can_quarrel(game, s, npc, lf) -> float:
    return (1.5 if set(npc.traits) & {"gruff", "proud", "bitter", "cruel"} else 1.0) if _has(lf, "rival") else 0.0


def _quarrel(game, s, npc, lf, rng) -> dict | None:
    t = _tie_of(lf, "rival")
    if t is None:
        return None
    return {"rival": t["name"], "name": t["name"], "to": t["npc"]}


event("quarrel")((_can_quarrel, _quarrel))


def _can_be_found(game, s, npc, lf) -> float:
    return 1.0 if any(x["kind"] == "lover" and not x.get("known") for x in lf["secrets"]) else 0.0


def _found(game, s, npc, lf, rng) -> dict | None:
    sec = next((x for x in lf["secrets"] if x["kind"] == "lover" and not x.get("known")), None)
    if sec is None:
        return None
    sec["known"] = True  # (the town talks; what it does about it is a story's)
    return {"lover": sec.get("to", "someone"), "name": sec.get("to", "someone")}


event("love_found_out")((_can_be_found, _found))


# ---------------------------------------------------------------------------- the start-up check
def problems(tables) -> list[str]:
    """Every event the data names has its rule here, and every rule its words; the tie kinds the words need exist."""
    d = getattr(tables, "lives", None) or {}
    out = []
    if not d:
        return out
    for kind in d.get("events", {}):
        if kind not in EVENTS:
            out.append(f"lives.json: events.{kind} is not a life event the game knows.")
    for kind in EVENTS:
        if kind not in d.get("events", {}):
            out.append(f"lives.json: the life event '{kind}' has no words.")
    known = set(KIN_OF) | set(KIN_WORDS) | set(d.get("ties", {})) | {"kin"}
    for table in ("wants", "fears", "secrets", "things"):
        for k, spec in d.get(table, {}).items():
            for key in ("needs", "not"):
                if spec.get(key) and spec[key] not in known:
                    out.append(f"lives.json: {table}.{k} needs '{spec[key]}', which is not a tie.")
            jobs = tables.people["occupations"] if hasattr(tables, "people") else {}
            for j in spec.get("jobs", []):
                if jobs and j not in jobs:
                    out.append(f"lives.json: {table}.{k} names unknown occupation '{j}'.")
            traits = tables.people.get("personality", {}) if hasattr(tables, "people") else {}
            for tr in spec.get("traits", []):
                if traits and tr not in traits:
                    out.append(f"lives.json: {table}.{k} names unknown trait '{tr}'.")
    return out
