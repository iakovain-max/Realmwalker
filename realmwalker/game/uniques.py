"""Unique companions (after v1; Anton asked for them on 2026-09-26): seven people who are like no one else.

The game does not make them up. The same seven, with the same faces, words, gifts and gear, are in every world
(data/uniques.json); only where they are is the world's, chosen once (`place`) the first time anyone looks.

- Sir Osric Vane, the last knight of the Grey Lantern, keeps a vigil over a barrow. Put its dead king down and he
  is yours. He keeps watch every night.
- Durgin Ashbeard, last of Kharak-Dûl, drinks in the alehouse nearest the dragon that burned his hold. Drink him
  under the table and swear to kill it with him. He knows where dragons sleep, and his shield turns fire.
- Tobiah Vell, Twice-Hanged, sits in the cells of the greatest city. Buy him out, talk him out or let him out. The
  first blow that should kill him each day does not.
- Sister Wendeline, the Plague-Bell, is wherever the sickness is. Work a day beside her among the sick. She never
  catches anything, and her bell heals.
- Grusha Nine-Fingers, the Penitent, scrubs a temple's floors. Talk her into facing the village she helped to burn
  twenty years ago, and take her there; what happens then is up to you and them. Orcs and goblins know her name.
- Aelith of the Long Memory has written down five hundred years of this land. Tell her something she does not
  know. She remembers what happened in every place you walk into.
- Wren Underbough, the Night-Road, is the best smuggler on the back roads. Run her crate past a gate. With her,
  gate-wardens never search your packs.

They take no wage and carry no purse; they join a level above the leader (never below their own least level). What
the world knows of them is kept with the world (world.politics["uniques"]): where they are, whether they have been
met, what they asked of you, and, when they leave you, the whole of the character, so they come back as they left.
"""

from __future__ import annotations

from realmwalker.core import dice, textgen
from realmwalker.core.rng import RNG
from realmwalker.game import companions as comp
from realmwalker.rules.character import Character
from realmwalker.rules.items import Item, money_text

FINE = 2500  # what the gaoler takes to let Tobiah go
BLOOD_PRICE = 3000  # what a burned village asks for its dead
TOBIAH_DC, LOCK_DC, INSIGHT_DC, HISTORY_DC, WORK_DC, DRINK_DC, PLEA_DC = 17, 15, 14, 17, 12, 15, 15
RUMOUR_DAYS = 120  # how often people start talking about them again, while nobody has found them
LOYALTY = 60.0
PERK_FEATURES = {"unhangable": "relentless_endurance", "plaguebell": "plague_proof"}
BOOKS = ("history_book", "lore_book", "old_map")
TRIBE_FOES = ("orc", "goblin", "hobgoblin", "bugbear")


def table(game) -> dict:
    return game.tables.uniques


def data(game) -> dict:
    return {k: v for k, v in table(game)["uniques"].items() if not k.startswith("_")}


def records(world) -> dict:
    return world.politics.get("uniques", {})


def ensure(game) -> dict:
    """Where the seven are in this world: chosen the first time anyone looks, and then kept."""
    w = game.world
    if "uniques" not in w.politics and w.settlements:
        place(game)
    return records(w)


def rec(game, uid: str) -> dict:
    return ensure(game).get(uid, {})


def unique_of(c: Character) -> str | None:
    return c.companion.get("unique") if c.companion else None


def with_party(game, uid: str) -> Character | None:
    return next((c for c in game.party[1:] if c.alive and unique_of(c) == uid), None)


def perk(game, name: str) -> Character | None:
    """The unique companion in the party with this gift, if any."""
    for c in game.party[1:]:
        uid = unique_of(c)
        if uid and c.alive and data(game).get(uid, {}).get("perk") == name:
            return c
    return None


def npc_of(game, uid: str):
    return game.world.npcs.get(rec(game, uid).get("npc", -1))


# ---------------------------------------------------------------------------- where they are
def _dist(a, b) -> float:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _pick(settlements, used: set, key) -> object | None:
    fresh = [s for s in settlements if s.id not in used]
    pool = fresh or list(settlements)
    return min(pool, key=key) if pool else None


def place(game) -> None:
    """Find each of the seven a home in this world, spread about so that no two share a town if it can be helped."""
    from realmwalker.game import dragons
    from realmwalker.world import factions as fx
    from realmwalker.world import news

    w = game.world
    rng = w.rng.child("uniques")
    towns = [s for s in w.settlements if s.kind in ("town", "city")] or list(w.settlements)
    used: set[int] = set()
    out: dict[str, dict] = {}
    for uid, u in data(game).items():
        r: dict = {"state": "waiting", "npc": -1, "site": -1, "village": -1, "dragon": ""}
        where = u["where"]
        s = None
        if where == "barrow":
            barrows = [x for x in w.sites if x.kind == "barrow"] or list(w.sites)
            best = None
            for b in barrows:
                near = _pick(w.settlements, used, lambda t, b=b: _dist(t, b))
                if near is not None and (best is None or _dist(near, b) < _dist(best[0], best[1])):
                    best = (near, b)
            if best is not None:
                s, site = best
                r["site"] = site.id
        elif where == "dragon":
            living = dragons.living(w)
            if living:
                d = living[0]
                lair = w.sites[d["lair"]]
                holds = [t for t in w.settlements if t.kind == "hold"] or towns
                s = _pick(holds, used, lambda t: _dist(t, lair))
                r.update(site=lair.id, dragon=d["name"])
            else:
                s = _pick([t for t in w.settlements if t.kind == "hold"] or towns, used, lambda t: -t.population)
        elif where == "gaol":
            s = _pick(towns, used, lambda t: (t.kind != "city", -t.population))
        elif where == "sickness":
            sick = [t for t in w.settlements if t.status.get("plague")]
            if not sick:
                struck = [e for e in w.history if e.get("kind") == "plague" and e.get("places")]
                sick = [w.settlements[p] for e in struck[-3:] for p in e["places"] if 0 <= p < len(w.settlements)]
            s = _pick(sick or towns, used, lambda t: (t.kind not in ("town", "city"), -t.population))
        elif where == "penance":
            camps = [p for p in (news.faction_place(w, f) for f in fx.active_factions(w, "tribe")) if p is not None]

            def to_tribes(t) -> float:
                return min((abs(t.x - x) + abs(t.y - y) for x, y in camps), default=0)

            s = _pick(towns, used, to_tribes)
            if s is not None:
                villages = [v for v in w.settlements if v.kind in ("hamlet", "village") and v.id != s.id
                            and 5 <= _dist(v, s) <= 25] or [v for v in w.settlements if v.id != s.id]
                village = min(villages, key=lambda v: (to_tribes(v), _dist(v, s))) if villages else None
                r["village"] = village.id if village is not None else -1
        elif where == "memory":
            halls = [t for t in w.settlements if t.kind == "elfhall"] or [t for t in w.settlements if t.kind == "city"]
            s = _pick(halls or towns, used, lambda t: -t.population)
        elif where == "road":
            homes = [t for t in w.settlements if t.culture == "halfling" and t.kind in ("village", "town")]
            homes = homes or [t for t in towns if t.walled and w.river[t.x, t.y]] or towns
            s = _pick(homes, used, lambda t: -t.population)
        if s is None:
            s = rng.choice(w.settlements)
        r["town"] = s.id
        used.add(s.id)
        out[uid] = r
    w.politics["uniques"] = out
    for uid in out:
        rumour(game, uid)


def words(game, uid: str) -> dict:
    """The world's part of their story: the town they are in, the barrow, the dragon, the village."""
    w = game.world
    r = records(w).get(uid, {})
    town = w.settlements[r["town"]] if 0 <= r.get("town", -1) < len(w.settlements) else None
    site = w.sites[r["site"]] if 0 <= r.get("site", -1) < len(w.sites) else None
    village = w.settlements[r["village"]] if 0 <= r.get("village", -1) < len(w.settlements) else None
    return {"town": town.name if town is not None else "the city",
            "site": site.name if site is not None else "the old barrow",
            "dragon": r.get("dragon") or "the wyrm", "village": village.name if village is not None else "the village",
            "leader": game.leader.name.split()[0] if game.party else "you"}


def fill(game, uid: str, text: str, **extra) -> str:
    values = {**words(game, uid), **{k: str(v) for k, v in extra.items()}}
    return textgen.fill(text, game.world.rng.child(f"unique-words/{uid}"), {}, values)


def talk_line(game, uid: str, kind: str, rng: RNG | None = None, **extra) -> str:
    lines = data(game)[uid]["talk"].get(kind) or [""]
    rng = rng or game.world.rng.child(f"unique-talk/{uid}/{kind}/{game.world.time}")
    return fill(game, uid, rng.choice(lines), **extra)


def rumour(game, uid: str) -> None:
    """People talk about them, in the town they are in and for a long way round."""
    from realmwalker.world import news

    w = game.world
    r = records(w).get(uid)
    if r is None or not 0 <= r.get("town", -1) < len(w.settlements):
        return
    s = w.settlements[r["town"]]
    rng = w.rng.child(f"unique-rumour/{uid}/{game.moment.total_days}")
    news.add(w, fill(game, uid, rng.choice(data(game)[uid]["rumours"])), s.x, s.y, kind="unique", importance=3,
             places=[s.id])
    r["rumour"] = game.moment.total_days


# ---------------------------------------------------------------------------- meeting them
def arrive_town(game, lm, settlement) -> None:
    """Walking into a town: whoever of the seven lives here is about (made the first time); Grusha's village
    remembers her; Aelith remembers the place."""
    if lm.kind != "settlement":
        return
    ensure(game)
    made = False
    for uid, r in records(game.world).items():
        if r.get("town") == settlement.id and r.get("state") == "waiting" and uid in data(game):
            npc = npc_of(game, uid)
            if npc is None:
                made = appear(game, uid, lm, settlement) or made
    if made:
        from realmwalker.game.people import update_positions

        update_positions(game, lm)
    grusha = with_party(game, "grusha")
    if grusha is not None and rec(game, "grusha").get("village") == settlement.id and \
            grusha.companion.get("penance", "pending") == "pending":
        head = headman(game, settlement)
        game.say(f"<warn>{talk_line(game, 'grusha', 'arrive', headman=head.first_name if head else 'the headman')}</>",
                 "warn")
    remember(game, settlement)


def appear(game, uid: str, lm, settlement) -> bool:
    """Their townsperson: the same face in every world, in the building they would be in."""
    from realmwalker.game import followers
    from realmwalker.game.people import add, make_npc, town_of

    u = data(game)[uid]
    w = game.world
    where = followers.spot_in(game, lm, tuple(u["building"]))
    if where is None:
        return False
    bi, cell = where
    npc = make_npc(game, settlement, "wayfarer", w.rng.child(f"unique-npc/{uid}"), building=bi, post=cell, home=cell)
    npc.name, npc.sex, npc.age = u["name"], u["sex"], u["age"]
    npc.race, npc.culture, npc.title = u["race"], u["culture"], u["title"]
    npc.traits, npc.speech, npc.stats = list(u["traits"]), u["speech"], u["stats"]
    npc.notable, npc.purse = True, 0
    npc.profile = {k: fill(game, uid, v) for k, v in u["profile"].items()}
    npc.flags["unique"] = uid
    add(w, town_of(w, settlement.id), npc)
    records(w)[uid]["npc"] = npc.id
    return True


def greeting(game, npc, rng: RNG) -> str:
    """How they say hello: their own way, and differently once you have travelled together."""
    uid = npc.flags.get("unique")
    if uid not in data(game):
        return ""
    r = rec(game, uid)
    return talk_line(game, uid, "again" if (r.get("met") or "char" in r) else "greet", rng)


def headman(game, settlement):
    """Who speaks for a village when it has something to say."""
    from realmwalker.game.people import npcs_in

    folk = [n for n in npcs_in(game.world, settlement.id) if n.alive and n.notable]
    return next((n for n in folk if n.job in ("headman", "lord")), None) or next(
        (n for n in folk if n.job in ("priest", "innkeeper")), None) or (folk[0] if folk else None)


# ---------------------------------------------------------------------------- making them
def signature(game, uid: str) -> Item:
    """The one thing that is theirs: a magic item whose properties are written down, not rolled."""
    it = data(game)[uid]["item"]
    spec = game.tables.magic["rarities"][it["rarity"]]
    props = [dict(p) for p in it["props"]]
    for p in props:
        if p["kind"] == "charges":
            p["left"] = int(p["value"])
    base = game.tables.items.get(it["base"])
    magic = {"rarity": it["rarity"], "props": props, "identified": True, "cursed": False, "title": it["title"],
             "story": fill(game, uid, it["story"]), "source": "unique", "unique": uid,
             "value": int(base["value"] * float(spec["value_mult"]) + int(spec["value_add"]))}
    from realmwalker.game.magic_items import look_for

    magic["look"] = dict(it.get("look") or look_for(game, magic, game.world.rng.child(f"unique_look/{uid}")))
    return Item(uid=0, def_id=it["base"], qty=1, quality="fine", condition=100, made_at=game.world.time, magic=magic)


def make_character(game, uid: str) -> Character:
    """Them, as a full character: fixed scores, skills and gear, one level above the leader (or their own least)."""
    from realmwalker.rules import progression
    from realmwalker.rules.creation import CharacterBuilder
    from realmwalker.rules.inventory import add_existing, add_item, equip, equip_everything_sensible, fill_containers

    u = data(game)[uid]
    t = game.tables
    rng = game.world.rng.child(f"unique/{uid}")
    b = CharacterBuilder(t, rng)
    b.set_race(u["race"])
    b.set_culture(u["culture"])
    b.set_class(u["class"])
    b.set_background(u["background"])
    b.scores = dict(u["scores"])
    if u.get("style"):
        b.fighting_style, b.style_chosen = u["style"], True  # (a Fighting Style feat)
    if u.get("subclass") and "subclass" in t.classes[u["class"]]["choices_at_1"]:
        b.subclass = u["subclass"]
    b.sex, b.name, b.age = u["sex"], u["name"], u["age"]
    profile = {k: fill(game, uid, v) for k, v in u["profile"].items()}
    b.appearance, b.backstory, b.personality = profile["appearance"], profile["backstory"], profile["personality"]
    char = b.build(game.world.time)
    char.skills = list(dict.fromkeys(u["skills"]))
    char.expertise = list(u["expertise"])
    char.subclass = u.get("subclass") or char.subclass  # theirs from the start, whatever level it comes at
    if char.spells:
        if u.get("cantrips"):
            char.spells["cantrips"] = list(u["cantrips"])
        if u.get("spells"):
            char.spells["spellbook"] = list(u["spells"])
    table_xp = t.rules["xp_for_level"]
    level = min(int(t.rules["max_level"]), len(table_xp), max(int(u["level"]), game.leader.level + 1))
    if level > 1:
        progression.award_xp(char, table_xp[level - 1], t, rng, auto=True)
    progression.auto_resolve(char, t)  # (a level-1 choice too: a cleric's Divine Order)
    items = t.items
    char.inventory, char.equipped, char.next_uid = [], {}, 1
    for def_id, qty in items.starting_packs.get("everyone", []) + [list(p) for p in u["kit"]]:
        if def_id in items:
            add_item(char, items, def_id, int(qty), made_at=game.world.time)
    equip_everything_sensible(char, items)
    fill_containers(char, items, "clean")
    mine = add_existing(char, items, signature(game, uid))
    equip(char, items, mine.uid)
    feature = PERK_FEATURES.get(u["perk"])
    if feature and feature not in char.features:
        char.features.append(feature)
        if feature == "relentless_endurance":
            char.uses["relentless_endurance"] = 1
    char.money = 0
    char.hp = char.max_hp
    return char


def join(game, uid: str, npc, *, said: str = "") -> list[str]:
    """They come with you: as they were, if they have travelled with you before."""
    u = data(game)[uid]
    r = rec(game, uid)
    kept = r.pop("char", None)
    char = Character.from_dict(kept) if kept else make_character(game, uid)
    char.alive = True
    comp.enlist(game, npc, char, "unique", unique=uid, title=u["role"], values=list(u["values"]), want=u["want"],
                loyalty=r.pop("loyalty", LOYALTY))
    for key in ("penance", "oath"):
        if key in r:
            char.companion[key] = r[key]
    r["state"], r["met"] = "with", True
    cls = game.tables.classes[char.cls]["name"].lower()
    out = [said] if said else []
    out.append(f"<good>{comp.first(char)} joins you</>: {u['known_as']}, {u['epithet']}, a level {char.level} {cls}. "
               f"<dim>({u['perk_text']})</>")
    out.append(f"<name>{comp.first(char)}:</> {comp.line(game, 'hired', char)}")
    if u["perk"] == "dragonlore":
        out += reveal_lairs(game)
    return out


def left(game, c: Character) -> None:
    """They leave you (dismissed, recalled, run off): home again, as they were, to be found there."""
    uid = unique_of(c)
    r = rec(game, uid) if uid else None
    if r is None or r.get("state") == "dead":
        return
    k = c.companion
    r["state"] = "waiting"
    r["loyalty"] = float(k.get("loyalty", LOYALTY))
    for key in ("penance", "oath"):
        if key in k:
            r[key] = k[key]
    kept = Character.from_dict(c.to_dict())
    kept.companion = {}
    r["char"] = kept.to_dict()


def died(game, c: Character) -> None:
    """One of the seven is dead. They are gone from this world for good, and the world hears of it."""
    from realmwalker.world import news

    uid = unique_of(c)
    if not uid:
        return
    u = data(game)[uid]
    r = rec(game, uid)
    r["state"] = "dead"
    r.pop("char", None)
    p = game.player
    news.add(game.world, f"{u['known_as']}, {u['epithet']}, is dead", p.x, p.y, kind="unique", importance=3)


# ---------------------------------------------------------------------------- what they are like
def lines(game, c: Character) -> dict:
    uid = unique_of(c)
    return data(game)[uid]["lines"] if uid and uid in data(game) else {}


def feelings(game, c: Character, tags) -> float:
    """What this one likes and hates beyond their values (on top of companions.react)."""
    uid = unique_of(c)
    if not uid or uid not in data(game):
        return 0.0
    u = data(game)[uid]
    spec = comp.data(game)["reactions"]
    return (float(spec["likes"]) * sum(1 for t in tags if t in u["likes"])
            + float(spec["hates"]) * sum(1 for t in tags if t in u["hates"]))


def banter(game, rng: RNG) -> str:
    """Two of the seven, talking to each other on the road."""
    here = [unique_of(c) for c in game.party[1:] if c.alive and unique_of(c)]
    pairs = [lines_ for key, lines_ in table(game).get("banter", {}).items()
             if not key.startswith("_") and all(p in here for p in key.split("+"))]
    return rng.choice(rng.choice(pairs)) if pairs else ""


def bond_text(game, c: Character) -> str:
    uid = unique_of(c)
    u = data(game).get(uid)
    if u is None:
        return ""
    k = c.companion
    state = k.get("penance") if uid == "grusha" else k.get("oath")
    text = u["bond_text"].get(state or "default") or u["bond_text"]["default"]
    return f"{u['known_as']}, {u['epithet']}. {fill(game, uid, text)}"


def gift(game, c: Character) -> str:
    u = data(game).get(unique_of(c))
    return u["perk_text"] if u else ""


def pay_word(game, c: Character) -> str:
    u = data(game).get(unique_of(c))
    return u["bond"] if u else "their own reasons"


def personal(c: Character, tables) -> list[str]:
    uid = unique_of(c)
    return list(tables.uniques["uniques"].get(uid, {}).get("personal", [])) if uid else []


# ---------------------------------------------------------------------------- the gifts
def reveal_lairs(game) -> list[str]:
    """Durgin knows where every dragon in the land sleeps."""
    from realmwalker.game import dragons

    out = []
    for d in dragons.living(game.world):
        site = game.world.sites[d["lair"]]
        if not game.player.explored[site.x, site.y]:
            game.player.explored[site.x, site.y] = True
            out.append(f"<info>Durgin marks {site.name} on your map: {d['name']} sleeps there.</>")
    return out


def remember(game, settlement) -> None:
    """Aelith was here before, and says what happened (once for each place, and only if the world's voice is on)."""
    aelith = perk(game, "remembrance")
    if aelith is None or not game.flavour():
        return
    k = aelith.companion
    done = k.setdefault("remembered", [])
    if settlement.id in done:
        return
    events = [e for e in game.world.history if settlement.id in e.get("places", []) and e.get("text")]
    if not events:
        return
    done.append(settlement.id)
    rng = game.world.rng.child(f"remember/{settlement.id}")
    e = max(events, key=lambda e: (e.get("importance", 1), e["year"]))
    text = e["text"].strip()
    text = text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?")) else ".")
    line = textgen.fill(rng.choice(table(game)["remembrance"]), rng, {},
                        {"text": text, "year": str(e["year"]), "place": settlement.name})
    game.say(textgen.escape_markup(line), "flavor")


def talked_past(game, creatures) -> bool:
    """Orcs and goblins who know Grusha's name."""
    return perk(game, "tribes") is not None and any(c.def_id.startswith(TRIBE_FOES) for c in creatures)


def waved_through(game) -> str:
    """Wren and the gate-wardens: returns what happened, or '' if she is not with you."""
    if perk(game, "backroads") is None:
        return ""
    return talk_line(game, "wren", "gate")


# ---------------------------------------------------------------------------- in conversation
def room_problem(game) -> str | None:
    if not comp.room(game):
        return f"you already have {comp.data(game)['max_companions']} companions"
    return None


def infamous(game) -> bool:
    r = game.renown
    return r.infamy >= r.fame + 10


def unique_quest(game, uid: str) -> dict | None:
    from realmwalker.game import quests

    qid = rec(game, uid).get("quest")
    return quests.by_id(game, qid) if qid is not None else None


def talk_choices(conv) -> list:
    """What you can say to one of the seven (their own ways in), or, where Grusha's village waits, to its headman."""
    from realmwalker.game.dialogue import Choice

    game, npc = conv.game, conv.npc
    uid = npc.flags.get("unique")
    if uid is None:
        return reckoning_choices(conv)
    r = rec(game, uid)
    if r.get("state") != "waiting" or not npc.alive or uid not in data(game):
        return []

    def say(label: str, step: str, ok: bool = True, why: str = "", **extra) -> Choice:
        problem = (why or "no") if not ok else room_problem(game) if step in JOINING else None
        return Choice("recruit", label, problem is None, problem or "", {"how": "unique", "uid": uid, "step": step,
                                                                        **extra})

    if "char" in r or r.get("met"):
        if r.get("oathbroken"):
            return [say("Will you come with me again?", "again", False, "he has not forgotten your broken oath")]
        return [say("Will you come with me again?", "again")]
    return CHOICES[uid](game, r, say)


JOINING = ("again", "done", "cleared", "oath", "pay", "speak", "pick", "come", "go", "book", "history", "magic",
           "guild")


def _osric(game, r, say) -> list:
    from realmwalker.game import quests

    w = words(game, "osric")
    q = unique_quest(game, "osric")
    if r.get("site", -1) in quests.cleared(game) and (q is None or q["state"] != "return"):
        return [say("The barrow is quiet now.", "cleared")]
    if not r.get("told"):
        return [say("What keeps you here?", "ask")]
    if q is None or q["state"] in ("failed", "abandoned", "finished"):
        return [say(f"I will go down into {w['site']} for you.", "vow")]
    if q["state"] == "return":
        return [say(f"It is done: {w['site']} is still.", "done")]
    return [say(f"About {w['site']}...", "advice")]


def _durgin(game, r, say) -> list:
    if not r.get("won"):
        return [say("[Constitution] Drink with him.", "drink", r.get("drank") != game.moment.total_days,
                    "he drank you under the table once today")]
    w = words(game, "durgin")
    from realmwalker.game import dragons

    if not dragons.living(game.world) or not r.get("dragon"):
        return [say("Then fight beside me.", "oath")]
    return [say(f"I swear it: we kill {w['dragon']} together.", "oath",
                game.leader.level >= 3, "he will not take the unblooded against a dragon (level 3)")]


def _tobiah(game, r, say) -> list:
    today = game.moment.total_days
    out = [] if r.get("hello") else [say("Why are you in here?", "hello")]
    out.append(say(f"Pay the gaoler to let him go ({money_text(FINE)}).", "pay",
                   sum(c.money for c in game.party) >= FINE, "you don't have that much"))
    out.append(say("[Persuasion] Speak for him to the gaoler.", "speak", r.get("spoke") != today,
                   "the gaoler has heard you once today"))
    out.append(say("[Sleight of Hand] Slip the lock while nobody is looking.", "pick", r.get("picked") != today,
                   "you have tried the lock once today"))
    return out


def _wendeline(game, r, say) -> list:
    from realmwalker.game import quests

    if infamous(game):
        return [say("Will you walk with me, Sister?", "come", False, "she knows what they say of you")]
    cured = [q for q in game.quests if q["template"] == "cure" and q["state"] == "finished"]
    out = []
    if cured or r.get("worked_ok"):
        out.append(say("Will you walk with me, Sister?", "come",
                       cured=quests.title(game, cured[-1]) if cured and not r.get("worked_ok") else ""))
    else:
        out.append(say("[Medicine] Work beside her among the sick for a day.", "work",
                       r.get("worked") != game.moment.total_days, "you have worked a day here already"))
    return out


def _grusha(game, r, say) -> list:
    w = words(game, "grusha")
    if not r.get("told"):
        return [say("What are you atoning for?", "tell")]
    if not r.get("ready"):
        return [say("[Insight] You are not doing penance. You are hiding.", "insight",
                    r.get("pressed") != game.moment.total_days, "give her time")]
    if infamous(game):
        return [say(f"I will walk with you to {w['village']}.", "go", False, "she will not ride with your kind")]
    return [say(f"I will walk with you to {w['village']}.", "go")]


def _aelith(game, r, say) -> list:
    out = [] if r.get("asked") else [say("What do you want?", "ask")]
    book = next((it for c in game.party for it in c.inventory if it.def_id in BOOKS), None)
    strange = next((it for c in game.party for it in c.inventory if it.magic and not it.magic.get("identified")), None)
    out.append(say("Give her a book from your pack to read.", "book", book is not None, "you carry no book she might read"))
    out.append(say("[History] Tell her about somewhere you have been.", "history",
                   r.get("tried") != game.moment.total_days, "she has heard you once today"))
    out.append(say("Show her something strange you carry.", "magic", strange is not None,
                   "you carry nothing strange enough"))
    return out


def _wren(game, r, say) -> list:
    out = []
    if any(game.world.factions[f].kind == "thieves_guild" for f in game.renown.members if f in game.world.factions):
        out.append(say("I'm one of the Guild. Walk with me.", "guild"))
    q = unique_quest(game, "wren")
    if q is not None and q.get("done") and q["state"] in ("return", "finished"):
        out.append(say("Your crate is delivered, and nobody looked in it.", "done"))
    elif q is None or q["state"] in ("failed", "abandoned", "finished"):
        out.append(say("You look like somebody with a cargo to move.", "cargo"))
    else:
        out.append(say("About your crate...", "waiting"))
    return out


CHOICES = {"osric": _osric, "durgin": _durgin, "tobiah": _tobiah, "wendeline": _wendeline, "grusha": _grusha,
           "aelith": _aelith, "wren": _wren}


def talk_choose(conv, choice) -> None:
    game, npc = conv.game, conv.npc
    uid, step = choice.data.get("uid"), choice.data.get("step")
    if uid is None:
        reckoning(conv, step)
        return
    r = rec(game, uid)
    rng = conv.rng
    conv.you_say(choice.label)
    said = ""
    if step == "again":
        r["join"] = True
    elif uid == "osric":
        said = _osric_step(conv, r, step)
    elif uid == "durgin":
        said = _durgin_step(conv, r, step)
    elif uid == "tobiah":
        said = _tobiah_step(conv, r, step)
    elif uid == "wendeline":
        said = _wendeline_step(conv, r, step, choice)
    elif uid == "grusha":
        said = _grusha_step(conv, r, step)
    elif uid == "aelith":
        said = _aelith_step(conv, r, step)
    elif uid == "wren":
        said = _wren_step(conv, r, step)
    if said is None:
        return
    if r.pop("join", False):
        for text in join(game, uid, npc, said=said):
            conv.note(text)
        conv.ended = True
    elif said:
        conv.npc_says(said)


def _quest(game, uid: str, npc, template: str, target: dict, extra_words: dict, days: int) -> list[str]:
    """A piece of work they ask of you, kept in the journal like any other."""
    from realmwalker.game import quests

    rng = game.world.rng.child(f"unique-quest/{uid}/{game.moment.total_days}")
    q = quests.base_quest(game, npc, template, rng)
    q.update(reward=0, days=days, unique=uid, target=target)
    q["words"].update(extra_words)
    q["words"]["pay"] = "no money"
    notes = quests.accept(game, q)
    rec(game, uid)["quest"] = q["id"]
    return notes


def _osric_step(conv, r, step) -> str | None:
    from realmwalker.game import quests

    game, npc = conv.game, conv.npc
    w = words(game, "osric")
    if step == "ask":
        r["told"] = True
        if r.get("site", -1) < 0:
            r["join"] = True  # no barrow in this world: he has kept his vigil over nothing, and knows it
        return talk_line(game, "osric", "ask")
    if step == "vow":
        site = game.world.sites[r["site"]]
        conv.npc_says(talk_line(game, "osric", "vow"))
        for text in _quest(game, "osric", npc, "clear_lair", {"site": site.id},
                           {"site": site.name[:1].upper() + site.name[1:],
                            "where": quests.direction(game.world.settlements[npc.settlement], site)}, 120):
            conv.note(text)
        return ""
    if step == "advice":
        return talk_line(game, "osric", "advice")
    if step in ("done", "cleared"):
        q = unique_quest(game, "osric")
        if q is not None and q["state"] == "return":
            for text in quests.reward(game, q, text=f"{w['site'][:1].upper() + w['site'][1:]} is still. Osric's vigil "
                                                     f"is over."):
                conv.note(text)
        r["join"] = True
        return talk_line(game, "osric", "done" if step == "done" else "cleared")
    return ""


def _durgin_step(conv, r, step) -> str | None:
    from realmwalker.game import dragons, quests

    game, npc = conv.game, conv.npc
    leader = game.leader
    if step == "drink":
        r["drank"] = game.moment.total_days
        game.pass_time(60, "rest")
        rng = conv.rng
        bonus = game.sheet(leader).save_bonus("con") - int(leader.intoxication // 20)
        roll = dice.d20(rng).natural
        ok = roll + bonus >= DRINK_DC
        conv.note(f"<dice>Constitution: {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = {roll + bonus} vs DC "
                  f"{DRINK_DC} — {'you keep up' if ok else 'you do not'}</>")
        leader.intoxication = min(100.0, leader.intoxication + (35.0 if ok else 60.0))
        if not ok:
            conv.ended = True
            return talk_line(game, "durgin", "lose")
        r["won"] = True
        return talk_line(game, "durgin", "win")
    if step == "oath":
        living = [d for d in dragons.living(game.world) if d["name"] == r.get("dragon")]
        if not living:
            r["oath"] = "free"
            r["join"] = True
            return talk_line(game, "durgin", "no_dragon")
        site = game.world.sites[living[0]["lair"]]
        conv.npc_says(talk_line(game, "durgin", "oath"))
        for text in _quest(game, "durgin", npc, "slay_dragon", {"site": site.id, "dragon": living[0]["name"]},
                           {"dragon": living[0]["name"], "colour": living[0].get("color", "great"), "site": site.name,
                            "where": quests.direction(game.world.settlements[npc.settlement], site)}, 365):
            conv.note(text)
        r["oath"] = "default"
        r["join"] = True
        return ""
    return ""


def _tobiah_step(conv, r, step) -> str | None:
    from realmwalker.game import law, reputation
    from realmwalker.world import factions as fx

    game, npc = conv.game, conv.npc
    today = game.moment.total_days
    if step == "hello":
        r["hello"] = True
        return talk_line(game, "tobiah", "hello")
    if step == "pay":
        law.take_money(game, FINE)
        r["join"] = True
        return talk_line(game, "tobiah", "paid")
    if step == "speak":
        r["spoke"] = today
        realm = fx.realm_of_settlement(game.world, game.world.settlements[npc.settlement])
        standing = reputation.standing(game, realm.id) if realm is not None else 0
        dc = TOBIAH_DC - (3 if standing >= 15 else 0) - (3 if standing >= 50 else 0)
        ok, roll = conv.check("persuasion", dc)
        conv.note(roll)
        if not ok:
            return talk_line(game, "tobiah", "spoke_no")
        r["join"] = True
        return talk_line(game, "tobiah", "spoke")
    if step == "pick":
        r["picked"] = today
        ok, roll = conv.check("sleight_of_hand", LOCK_DC)
        conv.note(roll)
        if not ok:
            return talk_line(game, "tobiah", "picked_no")
        law.commit(game, "jailbreak", witnesses=law.witnesses_here(game, exclude=[npc]))
        r["join"] = True
        return talk_line(game, "tobiah", "picked")
    return ""


def _wendeline_step(conv, r, step, choice) -> str | None:
    from realmwalker.game import camp
    from realmwalker.rules import health

    game, npc = conv.game, conv.npc
    if step == "work":
        r["worked"] = game.moment.total_days
        town = game.world.settlements[npc.settlement]
        game.pass_time(8 * 60, "walk")
        ok, roll = camp.check(game, "medicine", WORK_DC, tag="wendeline")
        conv.note(roll)
        if town.status.get("plague") and conv.rng.chance(0.3):
            health.expose(game.leader, game.tables, "plague", conv.rng)  # you were among the sick all day
        if not ok:
            return talk_line(game, "wendeline", "worked_no")
        r["worked_ok"] = True
        return talk_line(game, "wendeline", "worked")
    if step == "come":
        r["join"] = True
        cured = choice.data.get("cured")
        if cured:
            return talk_line(game, "wendeline", "heard", cured=cured)
        return talk_line(game, "wendeline", "come")
    return ""


def _grusha_step(conv, r, step) -> str | None:
    game = conv.game
    if step == "tell":
        r["told"] = True
        return talk_line(game, "grusha", "tell")
    if step == "insight":
        r["pressed"] = game.moment.total_days
        ok, roll = conv.check("insight", INSIGHT_DC)
        conv.note(roll)
        if not ok:
            return talk_line(game, "grusha", "hiding")
        r["ready"] = True
        return talk_line(game, "grusha", "ready")
    if step == "go":
        r["penance"] = "pending"
        r["join"] = True
        return talk_line(game, "grusha", "go")
    return ""


def _aelith_step(conv, r, step) -> str | None:
    from realmwalker.game import magic_items

    game = conv.game
    if step == "ask":
        r["asked"] = True
        return talk_line(game, "aelith", "ask")
    if step == "book":
        game.pass_time(60, "rest")
        r["join"] = True
        return talk_line(game, "aelith", "book")
    if step == "history":
        r["tried"] = game.moment.total_days
        ok, roll = conv.check("history", HISTORY_DC)
        conv.note(roll)
        if not ok:
            return talk_line(game, "aelith", "told_no")
        r["join"] = True
        return talk_line(game, "aelith", "told")
    if step == "magic":
        strange = next((it for c in game.party for it in c.inventory if it.magic and not it.magic.get("identified")),
                       None)
        if strange is None:
            return ""
        for text in magic_items.identify(game, strange):
            conv.note(text)
        r["join"] = True
        return talk_line(game, "aelith", "shown", item=game.tables.items.name(strange, False))
    return ""


def _wren_step(conv, r, step) -> str | None:
    from realmwalker.game import quests

    game, npc = conv.game, conv.npc
    if step == "guild":
        r["join"] = True
        return talk_line(game, "wren", "guild")
    if step == "cargo":
        q = quests._smuggle(game, npc, game.world.rng.child(f"wren-cargo/{game.moment.total_days}"))
        if q is None:  # no walled town anywhere near: she takes you on trust
            r["join"] = True
            return talk_line(game, "wren", "done")
        q.update(unique="wren", days=max(int(q["days"]), 30))  # the one who takes the crate pays for it
        said = talk_line(game, "wren", "cargo", recipient=q["words"]["recipient"], dest=q["words"]["dest"])
        conv.npc_says(said)
        for text in quests.accept(game, q):
            conv.note(text)
        r["quest"] = q["id"]
        return ""
    if step == "waiting":
        return talk_line(game, "wren", "waiting")
    if step == "done":
        r["join"] = True
        return talk_line(game, "wren", "done")
    return ""


# ---------------------------------------------------------------------------- Grusha's village
def reckoning_choices(conv) -> list:
    """At the village she helped to burn, whoever speaks for it has something to say about Grusha."""
    from realmwalker.game.dialogue import Choice

    game, npc = conv.game, conv.npc
    grusha = with_party(game, "grusha")
    if grusha is None or grusha.companion.get("penance", "pending") != "pending":
        return []
    village = rec(game, "grusha").get("village")
    if npc.settlement != village or headman(game, game.world.settlements[village]) is not npc:
        return []
    k = grusha.companion
    pleaded = bool(k.get("pleaded"))

    def say(label, step, ok=True, why="") -> Choice:
        return Choice("recruit", label, ok, "" if ok else why, {"how": "unique", "step": step})

    return [say("[Persuasion] Speak for Grusha.", "plead", not pleaded, "they have heard you"),
            say("Let Grusha speak for herself.", "own", not pleaded, "they have heard her"),
            say(f"Pay the blood-price ({money_text(BLOOD_PRICE)}).", "price",
                sum(c.money for c in game.party) >= BLOOD_PRICE, "you don't have that much"),
            say("Hand her over to them.", "hang"),
            say("Take her away from here.", "away")]


def reckoning(conv, step: str) -> None:
    from realmwalker.game.people import change_disposition, npcs_in

    game, npc = conv.game, conv.npc
    grusha = with_party(game, "grusha")
    if grusha is None:
        return
    k = grusha.companion
    head = npc.first_name
    rng = conv.rng
    folk = [n for n in npcs_in(game.world, npc.settlement) if n.alive]

    def settle(state: str, loyalty: float, line: str) -> None:
        k["penance"] = rec(game, "grusha")["penance"] = state
        comp.change_loyalty(grusha, loyalty)
        conv.npc_says(talk_line(game, "grusha", line, rng, headman=head))

    if step == "plead":
        k["pleaded"] = True
        conv.you_say("[Persuasion] You speak for Grusha: what she did, and what she has done since.")
        ok, roll = conv.check("persuasion", PLEA_DC + {"hostile": 4, "unfriendly": 2}.get(npc.mood(), 0))
        conv.note(roll)
        if ok:
            settle("forgiven", 30, "forgiven")
            for n in folk:
                change_disposition(n, 10)
        else:
            conv.npc_says(f"\"Words.\" {head} shakes their head. \"We have had twenty years of silence. Words are cheap.\"")
    elif step == "own":
        k["pleaded"] = True
        conv.you_say("You step back, and let Grusha speak.")
        s = game.sheet(grusha)
        roll = dice.d20(rng).natural
        total = roll + s.mod("wis") + 2
        conv.note(f"<dice>Grusha: {roll} + {total - roll} = {total} vs DC {PLEA_DC}</>")
        if total >= PLEA_DC:
            settle("forgiven", 35, "forgiven")
        else:
            settle("unforgiven", 5, "unforgiven")
    elif step == "price":
        from realmwalker.game.law import take_money

        take_money(game, BLOOD_PRICE)
        conv.you_say("You count out the blood-price.")
        settle("paid", 15, "paid")
    elif step == "hang":
        conv.you_say("Take her. She is yours.")
        conv.npc_says(talk_line(game, "grusha", "hanged", rng, headman=head))
        k["penance"] = "hanged"
        grusha.alive = False
        game.party.remove(grusha)
        comp.died(game, grusha)
        comp.react(game, "execution")
        for n in folk:
            change_disposition(n, 20)
    elif step == "away":
        conv.you_say("She is coming with me.")
        settle("unforgiven", -5, "walked")
        for n in folk:
            change_disposition(n, -20)
    conv.ended = step in ("price", "hang", "away") or k.get("penance") != "pending"


# ---------------------------------------------------------------------------- the days go by
def daily(game) -> None:
    """Rumours while nobody has found them; Durgin's dragon; the ones who went home with a dead leader's party."""
    from realmwalker.game import quests

    ensure(game)
    today = game.moment.total_days
    here = {unique_of(c) for c in list(game.party[1:]) + comp.waiting(game) if unique_of(c)}
    for uid, r in records(game.world).items():
        if uid not in data(game):
            continue
        if r.get("state") == "with" and uid not in here:
            r["state"] = "waiting"  # their party broke up (the leader died): home again
        if r.get("state") == "waiting" and not r.get("met") and today - int(r.get("rumour", -10**6)) >= RUMOUR_DAYS:
            rumour(game, uid)
    durgin = with_party(game, "durgin")
    q = unique_quest(game, "durgin")
    if durgin is not None and q is not None and q["state"] == "return":
        game.say(f"<good>{talk_line(game, 'durgin', 'avenged')}</>", "good")
        for text in quests.reward(game, q, text=f"{q['words'].get('dragon', 'The wyrm')} is dead. Durgin's oath is kept."):
            game.say(text, "good")
        durgin.companion["oath"] = rec(game, "durgin")["oath"] = "avenged"
        comp.change_loyalty(durgin, 40)


def on_fail(game, q) -> None:
    """Work one of them asked of you has failed or been given up. Durgin does not forgive a broken oath."""
    if q.get("unique") != "durgin":
        return
    durgin = with_party(game, "durgin")
    rec(game, "durgin")["oathbroken"] = True
    if durgin is not None:
        text = talk_line(game, "durgin", "oathbreak")
        comp.dismiss(game, durgin)
        game.say(f"<danger>{text}</>", "danger")
