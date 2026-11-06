"""The Reading (Expansion 6 F.4, docs/ADVENTURES.md §5.7): a seer lays the Wayfarer's Deck for you, and the tale's
hidden truths come up as cards and riddles.

The game's own deck (data/packs/06_adventures_events/reading.json): twenty great cards, each with its tags, the
signs by which it shows itself in a place and the marks by which it shows on a person; four suits of minor cards for
colour (one crosses each great card). A reading lays five places, each answering one hidden truth of the tale:
- the key: where what you need lies (a fetch step's place, else where its truth is learned, else a search);
- the hand: who will stand with you (the tale's ally, else the patron who is not its traitor, else its witness): the
  npc id is `adv["reading"]["named"]`, never the traitor (story/traitors.py) and, once the villain knows of the
  reading, the first it strikes at (story/villain.py `_helper`);
- the shadow: what the villain fears (its weakness, else the blueprint's: the Risen's name, the Outlaw's back way);
- the door: where the last stand will be (the finale step's place);
- the turn: what is coming (a hidden traitor's reason, which counts as one of their tells; else the threat's next
  stage).
The truth comes first: each place's truth carries tags, the card is the one whose tags fit best (`_card`), and the
riddle is written from the real place's own past (its history's events with its name kept out, a tomb's dead, a
ruin's fall, a battlefield's name and year), its look (the land, a river, a road) or a person's trade.

A card may come up silent (reading.json `silent`, and always when there is no truth to read yet); a reading may be
asked again once the tale's chapter has moved on (`readable`: "again"), which lays the silent places and the turn
anew. Once in a tale the villain's own card may turn up (`villain_card`): it speaks through the seer, its attention
rises, and it knows whom the Hand named.

Seers: a townsperson of the job "seer" (people.json) keeps a fire at a crossroads town (`crossroads`) or in a city
(people.populate_town); a hermit lives at some wonders (`hermit_at`, offered from `on_arrive`). Talk (`talk_choices`,
"story_reading") or the hermit offers the beat "reading_offer"; its op `reading pay|favour` lays the cards and
sets `politics["director"]["reading"]` {adv}, which opens the reading's screen (ui/screens/reading.py).

Afterwards the cards' imagery is planted in the world and pointed out when met: arriving at the key's or the door's
place (`on_arrive`), greeting the one the Hand named (`on_meet`, from dialogue), gaining the key the shadow foretold
(`on_key`, from the beats' key op). The journal keeps the reading.

The record `adv["reading"]` (None until read): {seer, day, chapter, times, named, cards {pos: {card, minor [suit,
rank], riddle, silent, truth {what, tags, ...}}}, villain {card, voice} or absent, villain_knows, pointed [pos]}.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story.beats import condition, op

POSITIONS = ("key", "hand", "shadow", "door", "turn")
BEAT = "reading_offer"
TALK_CHOICES = {"story_reading"}
SHADOW_KEYS = ("weakness", "name", "backway", "anchor")  # (the finale keys a shadow foretells, in this order)


def spec(game) -> dict:
    return getattr(game.tables, "reading", None) or {}


def _story():
    from realmwalker.game import story

    return story


def _today(game) -> int:
    return int(game.moment.total_days)


def record(adv: dict | None) -> dict | None:
    return (adv or {}).get("reading")


def named(game, adv: dict) -> int | None:
    """The npc id the Hand named (bound late if the role's town had no people yet when it was read), or None."""
    rec = record(adv)
    if not rec:
        return None
    if rec.get("named") is None:
        truth = ((rec.get("cards") or {}).get("hand") or {}).get("truth") or {}
        entry = adv["cast"].get(truth.get("role") or "") if truth.get("role") else None
        if entry and "npc" in entry:
            rec["named"] = int(entry["npc"])
    return None if rec.get("named") is None else int(rec["named"])


# ---------------------------------------------------------------------------- seers
def crossroads(world, s, need: int = 3) -> bool:
    """Roads leave this town in `need` directions or more (a town where the roads meet keeps a seer's fire)."""
    n = 0
    for dx, dy in ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)):
        x, y = s.x + dx, s.y + dy
        if world.in_bounds(x, y) and bool(world.road[x, y]):
            n += 1
    return n >= need


def keeps_seer(game, s) -> bool:
    """Whether a seer keeps a fire here: in a city, or where the roads meet."""
    if not spec(game) or "seer" not in game.tables.people["occupations"]:
        return False
    return s.kind == "city" or getattr(s, "great", False) or \
        crossroads(game.world, s, int(spec(game)["seers"]["crossroads"]))


def hermit_at(game, x: int, y: int):
    """The wonder on this square, if a hermit who reads the cards lives there (the same answer every time)."""
    import zlib

    sp = spec(game)
    if not sp:
        return None
    for wd in game.world.wonders:
        cells = {tuple(c) for c in (wd.cells or [])} | {(wd.x, wd.y)}
        if (x, y) in cells:
            roll = zlib.crc32(f"hermit/{game.world.meta.id}/{wd.id}".encode()) % 1000 / 1000.0
            return wd if roll < float(sp["seers"]["hermit_chance"]) else None
    return None


def seer_words(game, npc) -> dict:
    p = _pronouns(getattr(npc, "sex", ""))
    return {"seer": npc.name, **p}


def _pronouns(sex: str) -> dict:
    p = textgen.pronoun_values(sex)
    s = p["s"] == "s"
    p.update({"es": "es" if s else "", "ies": "ies" if s else "y",
              "theirs": {"she": "hers", "he": "his"}.get(p["they"], "theirs")})
    return p


# ---------------------------------------------------------------------------- may it be read?
def readable(game, adv: dict) -> str | None:
    """"first" (never read), "again" (the chapter moved on since: the silent places and the turn), or None."""
    if adv.get("state") != "active":
        return None
    rec = record(adv)
    if not rec:
        return "first"
    if int(adv.get("chapter", 0)) > int(rec.get("chapter", 0)):
        return "again"
    return None


def tale_to_read(game) -> tuple[dict | None, bool]:
    """The hero's oldest tale that may be read now, and whether any tale is live at all."""
    tales = _story().active(game)
    for adv in tales:
        if readable(game, adv):
            return adv, True
    return None, bool(tales)


# ---------------------------------------------------------------------------- the truths
def _fill(game, text: str, rng, words: dict) -> str:
    return textgen.fill(text, rng, {}, words)


def _phrase(game, text: str, rng, words: dict) -> str:
    """A piece of a riddle, written to sit inside a sentence (not capitalised, no full stop)."""
    out = _fill(game, text, rng, words).rstrip(".")
    return out[:1].lower() + out[1:] if out[:2] != "I " else out


def _place_tags(game, place: dict) -> list[str]:
    w = game.world
    sp = spec(game)["places"]
    tags: list[str] = []
    x, y = _xy(game, place)
    if "settlement" in place:
        s = w.settlements[int(place["settlement"])]
        tags += sp["kinds"].get(s.kind, {}).get("tags", [])
        if s.walled:
            tags.append("castle")
        for e in _events(game, place)[:6]:
            tags += spec(game)["event_tags"].get(e["kind"], [])
    if "site" in place:
        site = w.sites[int(place["site"])]
        tags += sp["kinds"].get(site.kind, {}).get("tags", [])
        if str(site.id) in w.politics.get("tombs", {}):
            tags += ["king_dead", "tomb"]
        for e in _events(game, place)[:6]:
            tags += spec(game)["event_tags"].get(e["kind"], [])
    if w.in_bounds(x, y):
        if int(w.river[x, y]) > 0:
            tags += ["river", "water", "crossing"]
        if bool(w.road[x, y]):
            tags.append("road")
        biome = w.biome_ids[int(w.biome[x, y])]
        if "forest" in biome or biome == "jungle":
            tags += ["forest", "old"]
        from realmwalker.game import past

        if past.scar_at(w, x, y) is not None:
            tags += ["battlefield", "war", "defeat"]
    return tags


def _xy(game, place: dict) -> tuple[int, int]:
    from realmwalker.game.story import places

    return places.xy(game.world, place)


def _events(game, place: dict) -> list[dict]:
    """The history's events at a place, the most important and newest first."""
    w = game.world
    if "settlement" in place:
        sid = int(place["settlement"])
        found = [e for e in w.history if sid in e.get("places", ()) and e.get("text")]
    elif "site" in place:
        sid = int(place["site"])
        found = [e for e in w.history if sid in (e.get("sites") or ()) and e.get("text")]
    else:
        return []
    return sorted(found, key=lambda e: (-int(e.get("importance", 1)), -int(e.get("year", 0))))


def _masked(game, place: dict, text: str) -> str:
    """An event's words with the place's own name kept out of them (a riddle does not say the answer)."""
    from realmwalker.game.story import places

    name = places.name(game.world, place)
    stand = "the place"
    if "site" in place:
        stand = {"cave": "the cave", "barrow": "the barrow", "tower": "the tower", "ruin": "the ruins"}.get(
            game.world.sites[int(place["site"])].kind, "the place")
    if "settlement" in place:
        stand = {"hamlet": "the hamlet", "village": "the village", "city": "the city", "hold": "the hold"}.get(
            game.world.settlements[int(place["settlement"])].kind, "the town")
    text = text.replace(name, stand)
    if name.lower().startswith("the "):
        text = text.replace(name[4:], stand)  # (the history's own form of it, without its article)
    text = text.strip().rstrip(".")
    for article in ("The ", "A ", "An "):
        if text.startswith(article):
            return article.lower() + text[len(article):]
    return text


def _where(game, place: dict, rng) -> tuple[str, str]:
    """A place's riddle phrases: where (its past, else what it is) and its look (the land, the water, the road)."""
    from realmwalker.game import past

    w = game.world
    sp = spec(game)
    pl = sp["places"]
    x, y = _xy(game, place)
    looks: list[str] = []
    if w.in_bounds(x, y):
        if int(w.river[x, y]) > 0:
            looks += pl["looks"].get("river", [])
        if bool(w.road[x, y]) and "settlement" not in place:
            looks += pl["looks"].get("road", [])
        looks += pl["looks"].get(w.biome_ids[int(w.biome[x, y])], [])
    look = rng.choice(looks) if looks else "where the cards cannot see the sky"
    pasts: list[str] = []
    if "site" in place:
        site = w.sites[int(place["site"])]
        tomb = w.politics.get("tombs", {}).get(str(site.id))
        fig = w.figures.get(tomb) if tomb is not None else None
        if fig is not None:
            epithet = (getattr(fig, "epithet", "") or "").strip() or f"the {getattr(fig, 'title', '') or 'lord'}"
            died = f"in {past.year_text(fig.died)}" if fig.died is not None else "long ago"
            pasts.append(_phrase(game, rng.choice(pl["tomb"]), rng, {"epithet": epithet, "died": died}))
        ruin = w.politics.get("ruins", {}).get(str(site.id))
        if ruin:
            pasts.append(_phrase(game, rng.choice(pl["ruin"]), rng, {"was": ruin.get("was", "a town"),
                                                                   "cause": ruin.get("cause", "it fell")}))
    if "tile" in place:
        scar = past.scar_at(w, x, y)
        if scar is not None:
            pasts.append(_phrase(game, rng.choice(pl["scar"]), rng, {"name": scar["name"], "year": scar["year"]}))
    for e in _events(game, place)[:3]:
        lines = sp["pasts"].get(e["kind"]) or sp["pasts"]["any"]
        pasts.append(_phrase(game, rng.choice(lines), rng, {"year": past.year_text(e.get("year")),
                                                          "what": _masked(game, place, e["text"])}))
    if not pasts:
        kinds = pl["kinds"]
        kind = w.settlements[int(place["settlement"])].kind if "settlement" in place else \
            w.sites[int(place["site"])].kind if "site" in place else ""
        if kind in kinds:
            pasts.append(f"in {rng.choice(kinds[kind]['words'])}")
        from realmwalker.game.story import places as pls

        name = pls.name(w, place)
        if "settlement" in place or "site" in place:
            pasts.append(_phrase(game, rng.choice(pl["initial"]), rng, {"initial": name.removeprefix("the ").strip()[:1]
                                                                      .upper() or "a letter"}))
    where = pasts[0] if pasts and rng.chance(0.8) else (rng.choice(pasts) if pasts else look)
    if where == look:  # (nothing but the land to go on: one phrase, not the same one twice)
        look = ""
    return where, look


def _place_truth(game, place: dict | None, extra: list[str], rng) -> dict | None:
    from realmwalker.game.story import places

    if not place or not places.exists(game.world, place):
        return None
    where, look = _where(game, place, rng)
    return {"what": "place", "place": dict(place), "tags": _place_tags(game, place) + list(extra),
            "where": where, "look": look}


def _steps(adv: dict, kinds: tuple[str, ...]):
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            if st["kind"] in kinds and st["state"] not in ("done", "failed"):
                yield st


def _key_truth(game, adv: dict, rng) -> dict | None:
    for st in _steps(adv, ("fetch",)):
        if st["target"].get("place"):
            return _place_truth(game, st["target"]["place"], ["relic", "anchor", "treasure"], rng)
    for st in _steps(adv, ("learn",)):
        for r in st["target"].get("routes", []):
            if r.get("at"):
                return _place_truth(game, r["at"], ["lore", "knowledge"], rng)
            who = r.get("who") or {}
            if who.get("settlement") is not None:
                return _place_truth(game, {"settlement": int(who["settlement"])}, ["lore", "knowledge"], rng)
    for st in _steps(adv, ("search", "infiltrate")):
        if st["target"].get("place"):
            return _place_truth(game, st["target"]["place"], ["search", "secret"], rng)
    return None


def _door_truth(game, adv: dict, rng) -> dict | None:
    for st in _steps(adv, ("finale",)):
        if st["target"].get("place"):
            return _place_truth(game, st["target"]["place"], ["battle", "doom"], rng)
    return _place_truth(game, adv["places"].get("home"), ["battle", "doom"], rng)


def _bind(game, adv: dict, role: str) -> dict | None:
    """The role's person, bound now if their town has its people already."""
    from realmwalker.game.story import cast

    entry = adv["cast"].get(role)
    if cast.pending(entry):
        town = game.world.towns.get(int(entry["settlement"]))
        if town is not None and town.npcs:
            npc = cast._choose(game, int(entry["settlement"]), entry, adv)
            if npc is not None:
                adv["cast"][role] = cast._take(npc, adv, role, entry)
                cast._rebind_steps(adv, role, adv["cast"][role])
                entry = adv["cast"][role]
    return entry


def _hand_truth(game, adv: dict, rng) -> dict | None:
    from realmwalker.game.story import cast, patrons, stakes

    w = game.world
    tr = adv.get("traitor") or {}
    false = {int(tr["npc"])} if tr.get("npc") is not None and tr.get("state") not in ("never", "faltered") else set()
    ally = stakes.npc_of(game, adv)
    role = None
    if ally is not None and ally.alive and int(ally.id) not in false:
        role, entry = "ally", {"npc": int(ally.id), "settlement": ally.settlement, "job": ally.job}
    else:
        entry = None
        for r in ("ally", "patron", "witness"):
            e = adv["cast"].get(r)
            if not e or not ("npc" in e or "job" in e):
                continue
            if r == "patron" and ((patrons.record(adv) or {}).get("motive") == "traitor"
                                  or tr.get("role") == "patron"):
                continue
            entry = _bind(game, adv, r)
            p = cast.person(w, entry)
            if "npc" in entry and (p is None or not getattr(p, "alive", False) or int(entry["npc"]) in false):
                entry = None
                continue
            role = r
            break
    if entry is None or role is None:
        return None
    sid = entry.get("settlement")
    town = w.settlements[int(sid)].name if sid is not None and 0 <= int(sid) < len(w.settlements) else "the town"
    job = entry.get("job") or ""
    trades = spec(game)["trades"]
    trade = trades.get(job) or trades["default"]
    who = _phrase(game, rng.choice(trade["words"]), rng, {"town": town})
    return {"what": "person", "role": role, "npc": entry.get("npc"), "job": job,
            "settlement": None if sid is None else int(sid), "tags": list(trade["tags"]), "who": who}


def _shadow_truth(game, adv: dict, rng) -> dict | None:
    shadows = spec(game)["shadows"]
    weak = (adv.get("hidden") or {}).get("weakness")
    entry, key = None, None
    if weak:
        w = next((x for lst in game.tables.villains.get("weaknesses", {}).values() for x in lst
                  if x["id"] == weak.get("weakness")), None)
        if w is not None:
            entry, key = shadows.get(w["name"]), "weakness"
    if entry is None:
        entry = shadows.get(adv["blueprint"]) or shadows["default"]
    if key is None:
        key = next((k for k in SHADOW_KEYS if k in adv.get("finale", {}).get("keys", {})), None)
    return {"what": "shadow", "key": key, "fear": rng.choice(entry["words"]), "tags": list(entry["tags"])}


def _turn_truth(game, adv: dict, rng) -> dict | None:
    from realmwalker.game.story import traitors
    from realmwalker.world import threats

    rec = traitors.hidden(adv)
    if rec is not None:
        entry = spec(game)["traitor"].get(rec["reason"]) or next(iter(spec(game)["traitor"].values()))
        return {"what": "traitor", "reason": rec["reason"], "tell": rng.choice(entry["words"]),
                "tags": list(entry["tags"])}
    t = threats.records(game.world).get(adv["threat"])
    if t is None or t.get("state") == "ended":
        return None
    sch = t.get("scheme") or {}
    stages = list(sch.get("stages", []))
    nxt = stages[min(int(sch.get("stage", -1)) + 1, len(stages) - 1)] if stages else ""
    entry = spec(game)["turns"].get(nxt) or spec(game)["turns"]["default"]
    return {"what": "scheme", "stage": nxt, "next": rng.choice(entry["words"]), "tags": list(entry["tags"])}


TRUTHS = {"key": _key_truth, "hand": _hand_truth, "shadow": _shadow_truth, "door": _door_truth, "turn": _turn_truth}


# ---------------------------------------------------------------------------- the cards
def _card(game, tags: list[str], used: set[str], rng) -> str:
    """The great card whose tags fit the truth best (a little chance among equals), not yet on the cloth."""
    deck = spec(game)["great"]
    want = set(tags)
    best, score = None, -1.0
    for cid in sorted(deck):
        if cid in used:
            continue
        s = len(want & set(deck[cid]["tags"])) * 10 + rng.random()
        if s > score:
            best, score = cid, s
    return best or rng.choice(sorted(deck))


def _deal(game, wants: dict[str, list[str]], used: set[str], rng) -> dict[str, str]:
    """Cards for several truths at once: the truth with the fewest cards that fit it chooses first, each taking the
    card that fits it best (so one place does not take the only card that fits another's truth)."""
    deck = spec(game)["great"]
    jitter = {(p, c): rng.random() for p in sorted(wants) for c in sorted(deck)}

    def fit(pos: str, cid: str) -> int:
        return len(set(wants[pos]) & set(deck[cid]["tags"]))

    out: dict[str, str] = {}
    taken = set(used)
    for pos in sorted(wants, key=lambda p: (sum(1 for c in deck if c not in taken and fit(p, c)), p)):
        free = [c for c in sorted(deck) if c not in taken]
        if not free:
            break
        cid = max(free, key=lambda c: fit(pos, c) * 10 + jitter[(pos, c)])
        out[pos] = cid
        taken.add(cid)
    return out


def _minor(game, rng) -> list:
    return [rng.choice(sorted(spec(game)["suits"])), rng.randint(1, 10)]


def card_name(game, cid: str) -> str:
    return spec(game)["great"][cid]["name"]


def minor_name(game, minor: list) -> str:
    sp = spec(game)
    return f"{sp['ranks'][int(minor[1]) - 1]} of {sp['suits'][minor[0]]['name']}"


def minor_means(game, minor: list) -> str:
    suit = spec(game)["suits"][minor[0]]
    return suit["low"] if int(minor[1]) <= 5 else suit["high"]


def _riddle(game, pos: str, truth: dict, rng) -> str:
    r = spec(game)["riddles"]
    if pos in ("key", "door"):
        text = rng.choice([t for t in r[pos] if truth.get("look") or "{look}" not in t] or r[pos])
        return _fill(game, text, rng, {"where": truth["where"], "look": truth["look"]})
    if pos == "hand":
        return _fill(game, rng.choice(r["hand"]), rng, {"who": truth["who"]})
    if pos == "shadow":
        return _fill(game, rng.choice(r["shadow"]), rng, {"fear": truth["fear"]})
    if truth["what"] == "traitor":
        tell = truth["tell"]
        return _fill(game, rng.choice(r["turn_traitor"]), rng, {"tell": tell, "Tell": tell[:1].upper() + tell[1:]})
    return _fill(game, rng.choice(r["turn_scheme"]), rng, {"next": truth["next"]})


def lay(game, adv: dict, seer: str) -> list[str]:
    """Read the cards for a tale: the five places (or, again, the silent ones and the turn), maybe the villain's own
    card. Writes the record and the journal, and opens the reading's screen."""
    from realmwalker.game.story import traitors, villain

    sp = spec(game)
    first = record(adv) is None
    rec = adv["reading"] if not first else {"seer": seer, "day": _today(game), "chapter": int(adv["chapter"]),
                                            "times": 0, "named": None, "cards": {}, "pointed": []}
    rec["times"] = int(rec.get("times", 0)) + 1
    rng = game.world.rng.child(f"reading/{adv['id']}/{rec['times']}")
    todo = list(POSITIONS) if first else [p for p in POSITIONS if rec["cards"].get(p, {}).get("silent")
                                         or p == "turn"]
    used = {c["card"] for p, c in rec["cards"].items() if p not in todo and not c.get("silent")}
    silent_left = int(sp["silent"]["most"])
    truths: dict[str, dict | None] = {}
    silent: dict[str, bool] = {}
    for pos in [p for p in POSITIONS if p in todo]:
        truths[pos] = TRUTHS[pos](game, adv, rng.child(pos))
        silent[pos] = truths[pos] is None or (first and silent_left > 0 and rng.child(f"{pos}/silent").chance(
            float(sp["silent"]["chance"])))
        if silent[pos]:
            silent_left -= 1
    chosen = _deal(game, {p: (t or {}).get("tags", []) for p, t in truths.items() if not silent[p]}, used,
                   rng.child("deal"))
    used |= set(chosen.values())
    for pos, truth in truths.items():
        cid = chosen.get(pos) or _card(game, [], used, rng.child(f"{pos}/card"))
        used.add(cid)
        card = {"card": cid, "minor": _minor(game, rng.child(f"{pos}/minor")), "silent": bool(silent[pos]),
                "truth": truth or {}, "riddle": ""}
        if silent[pos]:
            card["riddle"] = _fill(game, rng.child(f"{pos}/s").choice(sp["silent_words"]), rng, {"seer": seer})
        else:
            card["riddle"] = _riddle(game, pos, truth, rng.child(f"{pos}/r"))
        rec["cards"][pos] = card
        if pos == "hand" and not silent[pos] and truth.get("npc") is not None:
            rec["named"] = int(truth["npc"])
        if pos == "turn" and not silent[pos] and truth.get("what") == "traitor":
            tr = traitors.hidden(adv)
            if tr is not None and not rec.get("traitor_told"):
                tr["seen"] = int(tr.get("seen", 0)) + 1  # (the cards warn of them: one of their tells, once)
                rec["traitor_told"] = True
    rec["seer"] = seer
    rec["chapter"] = int(adv["chapter"])
    adv["reading"] = rec
    named(game, adv)
    out = []
    vc = sp["villain_card"]
    chance = float(vc["chance"]) + float(vc["per_attention"]) * int(adv.get("attention", 0))
    if "villain" not in rec and rng.child("villain").chance(min(1.0, chance)):
        from realmwalker.world import threats

        t = threats.records(game.world).get(adv["threat"]) or {}
        cards = sp["villain"]["cards"].get(t.get("kind", ""), sp["villain"]["cards"]["default"])
        free = [c for c in cards if c not in used] or list(cards)
        cid = rng.child("villain/card").choice(free)
        words = {"seer": seer, "villain": _story()._villain_name(game, adv)}
        voices = sp["villain"]["voice"].get(t.get("kind", ""), sp["villain"]["voice"]["default"])
        voice = _fill(game, rng.child("villain/voice").choice(voices), rng, words)
        rec["villain"] = {"card": cid, "voice": voice}
        rec["villain_knows"] = True
        villain.notice(game, adv, int(vc["notice"]))
        out.append(f"<danger>{esc(voice)}</>")
    _journal(game, adv, rec, todo)
    from realmwalker.game.story import beats

    beats.director(game.world)["reading"] = {"adv": adv["id"]}
    game.dirty = True
    return out


def _journal(game, adv: dict, rec: dict, laid: list[str]) -> None:
    sp = spec(game)
    story = _story()
    day = _today(game)
    story.journal(adv, esc(f"{rec['seer']} read the cards for you."), day)
    for pos in laid:
        c = rec["cards"][pos]
        head = f"{sp['positions'][pos]['name']}: {card_name(game, c['card'])}"
        story.journal(adv, esc(f"{head}. {c['riddle']}" if not c["silent"] else f"{head}, silent."), day)
    if rec.get("villain") and "villain" not in rec.get("told", []):
        rec.setdefault("told", []).append("villain")
        story.journal(adv, esc(f"Its own card turned up: {card_name(game, rec['villain']['card'])}. It knows."), day)


# ---------------------------------------------------------------------------- the beat and its op
def offer(game, adv: dict, seer: str, place: str, kind: str = "seer", where: str = "town", npc=None) -> dict:
    from realmwalker.game.economy import money_text
    from realmwalker.game.story import beats

    sp = spec(game)
    rng = game.world.rng.child(f"reading-offer/{adv['id']}/{_today(game)}")
    words = {"seer": seer, "place": place, **(_pronouns(getattr(npc, "sex", "")) if npc is not None else
                                               _pronouns(""))}
    intro = _fill(game, rng.choice(sp["intros"].get(kind) or sp["intros"]["seer"]), rng, words)
    ask = _fill(game, rng.choice(sp["asks"]), rng, words)
    return beats.offer(game, BEAT, adv=adv["id"], where=where,
                       words={"seer": seer, "seer_intro": intro, "seer_ask": ask, "price": money_text(int(sp["price"]))})


@condition("reading_price")
def _can_pay(game, ctx, value) -> bool:
    return sum(c.money for c in game.party) >= int(spec(game).get("price", 0))


@op("reading")
def _reading_op(game, ctx, how: str = "pay"):
    from realmwalker.game.story import beats

    adv = beats.adventure(game, ctx)
    if adv is None or not readable(game, adv):
        return []
    sp = spec(game)
    seer = (ctx.get("words") or {}).get("seer", "the seer")
    out: list[str] = []
    if how == "pay":
        out += beats.OPS["money"](game, ctx, -int(sp["price"])) or []
    elif how == "favour":
        out += beats.OPS["time"](game, ctx, int(sp["favour_minutes"])) or []
    return out + lay(game, adv, seer)


# ---------------------------------------------------------------------------- talk
def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    if conv.npc.job != "seer" or not spec(conv.game):
        return []
    rng = conv.game.world.rng.child(f"seer-ask/{conv.npc.id}")
    return [Choice("story_reading", rng.choice(spec(conv.game)["talk"]["ask"]), data={})]


def talk_choose(conv, choice) -> None:
    game, npc = conv.game, conv.npc
    sp = spec(game)
    rng = game.world.rng.child(f"seer-talk/{npc.id}/{_today(game)}")
    words = seer_words(game, npc)
    adv, any_tale = tale_to_read(game)
    if adv is None:
        key = "done" if any_tale else "none"
        conv.npc_says(esc(_fill(game, rng.choice(sp["talk"][key]), rng, words)))
        return
    conv.npc_says(esc(_fill(game, rng.choice(sp["talk"]["yes"]), rng, words)))
    place = game.world.settlements[npc.settlement].name if npc.settlement is not None else "the town"
    offer(game, adv, npc.name, place, "seer", "town", npc)
    conv.ended = True


# ---------------------------------------------------------------------------- pointed out
def _said(game, adv: dict, key: str, rng, words: dict) -> str:
    return _fill(game, rng.choice(spec(game)[key]), rng, words)


def on_arrive(game) -> None:
    """The party stands on a world tile: a card's place met is pointed out (said once)."""
    from realmwalker.game.story import places

    if not spec(game):
        return
    for adv in _story().active(game):
        rec = record(adv)
        if not rec:
            continue
        for pos in ("key", "door"):
            c = rec["cards"].get(pos)
            if not c or c["silent"] or pos in rec["pointed"] or not c["truth"].get("place"):
                continue
            if places.here(game, c["truth"]["place"]):
                rec["pointed"].append(pos)
                rng = game.world.rng.child(f"pointed/{adv['id']}/{pos}")
                deck = spec(game)["great"][c["card"]]
                line = _said(game, adv, "pointed", rng, {"sign": rng.choice(deck["signs"]),
                                                         "card": _cap(card_name(game, c["card"])),
                                                         "seer": rec["seer"]})
                game.say(f"<story>{esc(line)}</>", "story")
                _story().journal(adv, esc(f"{spec(game)['positions'][pos]['name']} was "
                                          f"{places.name(game.world, c['truth']['place'])}."), _today(game))


def hermit(game) -> bool:
    """At a wonder where a hermit reads the cards, with a tale to read: the offer (once a week). True if it waits."""
    from realmwalker.game.story import beats

    if not spec(game) or beats.pending(game) is not None:
        return False
    p = game.player
    wd = hermit_at(game, p.x, p.y)
    if wd is None:
        return False
    adv, _ = tale_to_read(game)
    if adv is None:
        return False
    d = beats.director(game.world).setdefault("hermits", {})
    if _today(game) - int(d.get(str(wd.id), -999)) < int(spec(game)["seers"]["hermit_every"]):
        return False
    d[str(wd.id)] = _today(game)
    rng = game.world.rng.child(f"hermit/{wd.id}")
    seer = _cap(_fill(game, rng.choice(spec(game)["hermits"]), rng, {"wonder": wd.name}))
    offer(game, adv, seer, wd.name, "hermit", "wild")
    return True


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def on_meet(game, npc) -> list[str]:
    """Greeting someone: the one the Hand named, the card's mark on them pointed out (once)."""
    out = []
    if not spec(game):
        return out
    for adv in _story().active(game):
        rec = record(adv)
        if not rec or "hand" in rec["pointed"]:
            continue
        c = rec["cards"].get("hand") or {}
        if c.get("silent") or named(game, adv) != int(npc.id):
            continue
        rec["pointed"].append("hand")
        rng = game.world.rng.child(f"met/{adv['id']}")
        deck = spec(game)["great"][c["card"]]
        mark = _fill(game, rng.choice(deck["marks"]), rng, _pronouns(getattr(npc, "sex", "")))
        line = _said(game, adv, "met", rng, {"mark": _cap(mark), "card": _cap(card_name(game, c["card"])),
                                             "seer": rec["seer"]})
        out.append(f"<story>{esc(line)}</>")
    return out


def on_key(game, adv: dict, k: str) -> list[str]:
    """A key of the tale gained: the one the Shadow foretold, pointed out (once)."""
    rec = record(adv)
    if not rec or "shadow" in rec["pointed"] or not spec(game):
        return []
    c = rec["cards"].get("shadow") or {}
    if c.get("silent") or (c.get("truth") or {}).get("key") != k:
        return []
    rec["pointed"].append("shadow")
    rng = game.world.rng.child(f"shadow-seen/{adv['id']}")
    line = _said(game, adv, "shadow_seen", rng, {"card": _cap(card_name(game, c["card"])), "seer": rec["seer"],
                                                 "fear": c["truth"].get("fear", "")})
    return [f"<story>{esc(line)}</>"]


def daily(game) -> None:
    """A Hand that named a role whose town had no people yet learns their name once it has."""
    for adv in _story().active(game):
        if record(adv):
            named(game, adv)


def journal_lines(game, adv: dict) -> list[str]:
    """The reading as the journal keeps it: each place, its card and its riddle (marked up)."""
    rec = record(adv)
    if not rec:
        return []
    sp = spec(game)
    out = [f"<dim>{esc(rec['seer'])} read the cards for you.</>"]
    for p in POSITIONS:
        c = rec["cards"].get(p)
        if not c:
            continue
        head = f"{sp['positions'][p]['name']} - {_cap(card_name(game, c['card']))}"
        out.append(f"  {esc(head)}: " + ("<faint>silent; ask again when the tale moves on</>" if c["silent"]
                                         else esc(c["riddle"])))
    if rec.get("villain"):
        out.append(f"  <danger>{esc(_cap(card_name(game, rec['villain']['card'])))}, reversed: it knows.</>")
    return out
