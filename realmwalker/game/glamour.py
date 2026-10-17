"""Minds, illusions and the small arts (Expansion 3 E.4): the spells of townsfolk and the law outside a fight.

A spell's {"op": "road", "does": "mind" | "illusion" | "art", "how": ...} is done here (game/spellwork's door sends it
here). Minds: Friends, Enthrall, Zone of Truth, Geas, Modify Memory (a person near you), Antipathy/Sympathy (a kind of
creature, for ten days) and Awaken (one of the party's animals). Illusions: the town's eyes drawn away (Minor
Illusion, Silent Image, Major Image), the image walking into a far town (Project Image), the letter that shows each
reader the seal they honour (Illusory Script), a magic thing masked (Nystul's Magic Aura) and a thing or a body taken
out of the world (Sequester). The small arts: Druidcraft, Elementalism, Prestidigitation, Thaumaturgy.

A conversation takes no time in this game, so a spell of a minute lasts for the talk that follows: its record is a
time (world minutes) on the person (`npc.flags`) or in `game.renown.flags`, both saved. The rest of E.4 is elsewhere:
the camp's wards (Magic Mouth, Programmed Illusion, Hallucinatory Terrain, Mirage Arcane) in game/spellwork.py, the
disguises (Disguise Self, Seeming) in game/waymagic.after_lasting, and the lasting buffs "glib" (Glibness), "unnoticed"
(Mislead, Invisibility in a town) and "nondetection" read through the helpers below.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject
from realmwalker.rules.character import Character

TALK_MINUTES = 10  # a spell of a minute holds for the talk that follows (ten minutes of the world)
DAY = 24 * 60
FRIENDS_SOUR = -20  # Friends: when it ends they know (PHB 2024), and like you less
GEAS_SOUR = -40
GEAS_HARM = "5d10"  # (the book's psychic harm for acting against it: never, here, as they obey)
GLIB_FLOOR = 15  # Glibness: a Charisma check's die counts as 15 at least
CHA_SKILLS = ("persuasion", "deception", "intimidation", "performance")
FOREVER = 10 ** 9
SEQUESTER_DAYS = 365 * 100  # a body held out of time: until the spell is ended (a century of the world here)


def _road(spell: dict) -> dict:
    return next((o for o in spell.get("effects", ()) if o.get("op") == "road"), {})


def _first(c) -> str:
    return esc(c.name.split()[0])


def _now(game) -> int:
    return int(game.world.time)


def _flags(game) -> dict:
    return game.renown.flags


def _here_id(game) -> int | None:
    lm = game.local
    if lm is None or lm.kind != "settlement":
        return None
    s = game.world.settlement_at(game.player.x, game.player.y)
    return s.id if s is not None else None


# ---------------------------------------------------------------------------- read by the rest of the game
def charmed(game, npc) -> bool:
    """Whether someone is under Friends or a Geas of yours right now. When a Friends spell has run out, they know
    what was done (their mood sours once)."""
    now = _now(game)
    if int(npc.flags.get("geas_until", -1)) >= now:
        return True
    until = npc.flags.get("charmed_until")
    if until is None:
        return False
    if now <= int(until):
        return True
    _sour(npc, "charmed_until", FRIENDS_SOUR, "was charmed by the traveller's magic")
    return False


def _sour(npc, key: str, amount: int, memory: str) -> None:
    from realmwalker.game.people import change_disposition

    npc.flags.pop(key, None)
    change_disposition(npc, amount)
    npc.remember(memory)


def tick(game) -> None:
    """A Geas run out: they know, and hate you for it (from pass_time, through spellwork.tick)."""
    now = _now(game)
    bound = _flags(game).get("geased")
    if bound and isinstance(game.world.npcs, dict):
        for nid in list(bound):
            npc = game.world.npcs.get(nid)
            until = npc.flags.get("geas_until") if npc is not None else None
            if until is None:
                bound.remove(nid)
            elif int(until) < now:
                _sour(npc, "geas_until", GEAS_SOUR, "was bound by the traveller's geas")
                npc.flags.pop("bribed_until", None)
                bound.remove(nid)
    for key in ("distraction", "booming"):
        rec = _flags(game).get(key)
        if rec is not None and int(rec.get("until", 0)) < now:
            del _flags(game)[key]
    anti = _flags(game).get("antipathy")
    if anti is not None and int(anti.get("until", 0)) < now:
        del _flags(game)["antipathy"]
    for key in ("script_until",):
        if int(_flags(game).get(key, FOREVER)) < now:
            del _flags(game)[key]


def obeys(game, npc) -> bool:
    """Under a Geas of yours: a guard never lays hands on you."""
    return int(npc.flags.get("geas_until", -1)) >= _now(game)


def enthralled(game, npc) -> bool:
    """Under Enthrall (their eyes on the speaker), or made to forget this very minute (Modify Memory)."""
    return int(npc.flags.get("enthralled_until", -1)) >= _now(game)


def distraction(game) -> int:
    """How much the town's eyes are drawn away from you right now (an illusion's penalty to their Perception)."""
    rec = _flags(game).get("distraction")
    if not rec or int(rec.get("until", 0)) < _now(game) or rec.get("settlement") != _here_id(game):
        return 0
    return int(rec.get("minus", 0))


def watcher_minus(game, npc) -> int:
    """What this person's eyes are worth less right now: Enthrall's -10, an illusion's distraction."""
    return (10 if enthralled(game, npc) else 0) + distraction(game)


def unseen(game) -> bool:
    """Mislead (or Invisibility) on the leader: in a town nobody sees what they do."""
    from realmwalker.rules import spells as spellrules

    return spellrules.lasting_flag(game.leader, game.tables, "unnoticed")


def glib(game, char: Character | None = None) -> bool:
    from realmwalker.rules import spells as spellrules

    return spellrules.lasting_flag(char or game.leader, game.tables, "glib")


def cha_roll(game, char: Character | None, skill: str, roll: int) -> int:
    """A Charisma check's die under Glibness: never below 15."""
    if skill in CHA_SKILLS and glib(game, char):
        return max(int(roll), GLIB_FLOOR)
    return int(roll)


def booming(game) -> bool:
    """Thaumaturgy's booming voice: Advantage on Intimidation in the talk that follows."""
    rec = _flags(game).get("booming")
    return bool(rec) and int(rec.get("until", 0)) >= _now(game)


def scripted(game) -> bool:
    """Illusory Script's letter in the pack: each reader sees the seal they would honour."""
    return int(_flags(game).get("script_until", -1)) >= _now(game)


SCRIPT_IMPRESS = 5  # (as a lord's signet: data/items.json signet_ring)


def masked(game, item) -> bool:
    """Nystul's Magic Aura on a carried thing: it looks like nothing much."""
    return _tag_until(item, "masked") >= _now(game)


def sequestered(item) -> bool:
    return "sequestered" in (item.tags or [])


def _tag_until(item, name: str) -> float:
    for t in item.tags or []:
        if t.startswith(name + ":"):
            return float(t.split(":", 1)[1])
    return 0.0


def hidden_thing(game, item, *, robbers: bool = False) -> bool:
    """A thing that is not taken: sequestered (from robbers, thieves and the watch), or masked (robbers, who pick the
    best-looking things, pass it over)."""
    return sequestered(item) or (robbers and masked(game, item))


# ---------------------------------------------------------------------------- the road: Antipathy/Sympathy
def kinds_here(game) -> list[tuple[str, str]]:
    """The kinds of creature that could be met here: (creature id, plural name), from the land's encounter table."""
    t = game.tables
    p = game.player
    biome = game.land_key(p.x, p.y)
    danger = int(game.world.danger[p.x, p.y])
    seen: dict[str, str] = {}
    for g in t.creatures.encounters.values():
        if float(g.get("weight", 1)) == 0:
            continue
        lo, hi = g["danger"]
        if not lo <= danger <= hi:
            continue
        if "any" not in g["biomes"] and biome not in g["biomes"] and t.biomes.family(biome) not in g["biomes"]:
            continue
        for cid, _n in g["members"]:
            if cid in t.creatures and cid not in seen:
                seen[cid] = t.creatures[cid].get("plural") or t.creatures[cid]["name"]
    return sorted(seen.items(), key=lambda kv: kv[1])


def on_meeting(game, enc):
    """A band met on the road while Antipathy/Sympathy holds: those of the named kind make Wisdom saves. Antipathy:
    if most of the band fail, it flees (None: nothing is met). Sympathy: those failing come entranced, and the party
    sees them first. Returns the encounter (or None) and says what happened."""
    rec = _flags(game).get("antipathy")
    if enc is None or not rec or int(rec.get("until", 0)) < _now(game):
        return enc
    kind = rec["kind"]
    ours = [c for c in enc.creatures if c.def_id == kind and c.hp > 0]
    if not ours:
        return enc
    rng = game.world.rng.child(f"antipathy/{_now(game)}")
    failed = []
    for c in ours:
        wis = int((game.tables.creatures[c.def_id].get("abilities") or {}).get("wis", 10))
        if dice.d20(rng).natural + (wis - 10) // 2 < int(rec["dc"]):
            failed.append(c)
    name = game.tables.creatures[kind].get("plural") or game.tables.creatures[kind]["name"]
    if rec["how"] == "antipathy":
        if len(failed) * 2 > len(enc.creatures):
            game.say(f"<good>{esc(name[:1].upper() + name[1:])} come out of the land, stop as if struck, and run from "
                     f"you as far as they can.</> <dim>(Antipathy: {len(failed)} of {len(ours)} failed)</>", "good")
            return None
        if failed:
            game.say(f"<dim>Some of the {esc(name)} shy away from you (Antipathy); the rest come on.</>", "dim")
            enc.creatures = [c for c in enc.creatures if c not in failed] or enc.creatures
        return enc
    if failed:
        enc.spotted_first = True
        enc.asleep = False
        game.say(f"<good>{esc(name[:1].upper() + name[1:])} come to you as if called, eyes fixed on you, heedless of "
                 f"anything else.</> <dim>(Sympathy: {len(failed)} of {len(ours)} entranced; they are caught "
                 f"unaware)</>", "good")
    return enc


# ---------------------------------------------------------------------------- Awaken: the animals
def awake_animal(game) -> dict | None:
    return next((a for a in game.leader.animals if a.get("awake")), None)


def _asleep_animals(game) -> list[dict]:
    return [a for a in game.leader.animals if not a.get("awake")]


# ---------------------------------------------------------------------------- the people near you
def _people_near(game, squares: int) -> list[Subject]:
    lm = game.local
    if lm is None or lm.kind != "settlement" or not isinstance(game.world.npcs, dict):
        return []
    p = game.player
    here = _here_id(game)
    out = []
    for npc in game.world.npcs.values():
        if here is None or npc.settlement != here or not npc.alive or not npc.present:
            continue
        if max(abs(npc.x - p.lx), abs(npc.y - p.ly)) <= squares:
            out.append(Subject(npc.name if npc.known else npc.label(), "person", npc.id, npc.x, npc.y))
    out.sort(key=lambda s: max(abs(s.x - p.lx), abs(s.y - p.ly)))
    return out


def _squares(spell: dict) -> int:
    r = spell.get("range")
    return max(2, int(r) // 5) if isinstance(r, int) else 2


def _save(game, caster, npc, ability: str, tag: str) -> tuple[bool, str]:
    """A person's save against the caster's spell: d20 (+2 for the notable, whose wits are sharper) against the DC."""
    from realmwalker.rules.spells import save_dc

    dc = save_dc(game.sheet(caster), game.tables)
    roll = dice.d20(game.world.rng.child(f"glamour/{tag}/{npc.id}/{_now(game)}")).natural
    bonus = 2 if npc.notable else 0
    said = f"<dim>({ability.capitalize()} save {roll} {bonus:+d} = {roll + bonus} vs DC {dc})</>"
    return roll + bonus >= dc, said


ABILITY_WORD = {"wis": "Wisdom", "cha": "Charisma"}


# ---------------------------------------------------------------------------- the minds
def _friends(game, caster, spell, npc) -> list[str]:
    name = esc(npc.first_name)
    if int(npc.flags.get("friends_at", -DAY - 1)) > _now(game) - DAY:
        return [f"{name} has felt that magic once today, and will not again: the words slide off."]
    npc.flags["friends_at"] = _now(game)
    ok, said = _save(game, caster, npc, "Wisdom", "friends")
    if ok:
        return [f"{_first(caster)} smiles and makes a small sign; {name} only looks puzzled. {said}"]
    npc.flags["charmed_until"] = _now(game) + int(spell.get("minutes", 1)) + TALK_MINUTES
    return [f"<good>{name} warms to {_first(caster)} at once, as to an old friend.</> For the talk that follows "
            f"they are Friendly. <dim>When it wears off they will know what was done.</> {said}"]


def _enthrall(game, caster, spell, o) -> list[str]:
    here = _people_near(game, _squares(spell))
    held = 0
    until = _now(game) + int(spell.get("minutes", 1)) + 1
    for s in here:
        npc = game.world.npcs[s.ref]
        ok, _said = _save(game, caster, npc, "Wisdom", "enthrall")
        if not ok:
            npc.flags["enthralled_until"] = until
            held += 1
    out = [f"{_first(caster)} begins to speak, and the words wind and wind."]
    if held:
        out.append(f"<good>{held} of the {len(here)} near hang on every word</>, blind to anything else for a minute: "
                   f"no witness to what your hands do, and easy to slip past.")
    else:
        out.append("<dim>Nobody near is held by it.</>")
    return out


def _truth(game, caster, spell, npc) -> list[str]:
    from realmwalker.game import quests

    name = esc(npc.first_name)
    ok, said = _save(game, caster, npc, "Charisma", "truth")
    out = [f"{_first(caster)} draws a circle of quiet round {name}."]
    if ok:
        return out + [f"{name} shakes it off and says nothing they did not mean to. {said}"]
    npc.flags["truthful_until"] = _now(game) + int(spell.get("rounds", 100)) // 10
    works = [q for q in quests.active(game) + [q for q in game.quests if q["state"] == "offered"]
             if q.get("giver") == npc.id]
    for q in works:
        if q.get("hidden") and not q.get("revealed"):
            quests.reveal(game, q)
            return out + [f"<warn>{name} cannot hold to the story: the work they gave you is not what they told "
                          f"you.</> <dim>(The journal has it.)</> {said}"]
    if works:
        return out + [f"<good>{name} answers everything plainly: the work they gave you is just what they said.</> "
                      f"{said}"]
    want = npc.profile.get("want")
    return out + [f"<good>{name} speaks only the truth for ten minutes</>"
                  + (f": what they want is {esc(want)}." if want else ".") + f" {said}"]


def _geas(game, caster, spell, npc, level: int) -> list[str]:
    from realmwalker.game import law

    name = esc(npc.first_name)
    ok, said = _save(game, caster, npc, "Wisdom", "geas")
    out = [f"{_first(caster)} speaks the binding words to {name}."]
    if ok:
        return out + [f"{name} stiffens, and the words break on them. {said}"]
    o = _road(spell)
    days = int(o.get("days", 30))
    for lv, d in sorted((o.get("days_by_level") or {}).items(), key=lambda kv: int(kv[0])):
        if level >= int(lv):
            days = int(d)
    until = FOREVER if days < 0 else _now(game) + days * DAY
    npc.flags["geas_until"] = until
    npc.flags["bribed_until"] = until  # (a guard under it never lays hands on you: law.watch)
    if npc.id not in _flags(game).setdefault("geased", []):
        _flags(game)["geased"].append(npc.id)
    seen = law.unreported_seen_by(game, npc)
    law.silence(npc, seen)
    lasts = "until the spell is ended" if days < 0 else ("a year" if days >= 365 else f"{days} days")
    out.append(f"<good>{name} bows their head: they will do as you say, for {lasts}.</> {said}")
    if seen:
        out.append(f"<good>They will say nothing of what they saw you do.</>")
    want, secret = npc.profile.get("want"), npc.profile.get("secret")
    if want:
        out.append(f"<good>What {name} wants:</> {esc(want)}")
    if secret:
        out.append(f"<good>What {name} hides:</> {esc(secret)}")
    if npc.job == "guard":
        out.append("<dim>A guard of the watch: they will not lay a hand on you.</>")
    return out


def _memory(game, caster, spell, npc) -> list[str]:
    from realmwalker.game import law

    name = esc(npc.first_name)
    ok, said = _save(game, caster, npc, "Wisdom", "memory")
    out = [f"{_first(caster)} holds {name}'s eyes and speaks softly of yesterday."]
    if ok:
        return out + [f"{name} blinks and steps back, uneasy: their memory holds. {said}"]
    since = _now(game) - DAY
    npc.flags["enthralled_until"] = _now(game) + int(spell.get("minutes", 1)) + 1  # (the casting is forgotten too)
    seen = [r for r in law.unreported_seen_by(game, npc) if int(r.get("time", 0)) >= since]
    law.silence(npc, seen)
    npc.memory = [m for m in npc.memory if "traveller" not in m]
    if npc.disposition < 0:
        npc.disposition = 0
    out.append(f"<good>The last day goes soft and grey in {name}'s mind: whatever passed between you is gone.</> "
               f"{said}")
    if seen:
        out.append("<good>They no longer remember what they saw you do.</>")
    return out


def _antipathy(game, caster, spell, target, level: int) -> list[str]:
    from realmwalker.rules.spells import save_dc

    how, kind = target.data["how"], target.ref
    days = int(_road(spell).get("days", 10))
    _flags(game)["antipathy"] = {"how": how, "kind": kind, "until": _now(game) + int(spell.get("minutes", 60))
                                 + days * DAY, "dc": int(save_dc(game.sheet(caster), game.tables))}
    name = esc(target.name.split(": ", 1)[-1])
    if how == "antipathy":
        return [f"{_first(caster)} works vinegar into the air round you for an hour. <good>For {days} days {name} "
                f"will want nothing so much as to be far from you.</> <dim>(A band of them makes Wisdom saves: if most "
                f"fail, it runs.)</>"]
    return [f"{_first(caster)} works honey into the air round you for an hour. <good>For {days} days {name} will be "
            f"drawn to you, heedless.</> <dim>(Those failing a Wisdom save come entranced: you see them first.)</>"]


def _awaken(game, caster, spell, target) -> list[str]:
    a = next((x for x in game.leader.animals if x is target.ref or x.get("name") == target.name), None)
    if a is None:
        return ["The animal is not with you."]
    a["awake"] = True
    first = esc(a["name"])
    return [f"For eight hours {_first(caster)} sits with {first}, a hand on its head. At the end of it {first} looks "
            f"up, and says, carefully, <good>\"I know you.\"</>",
            f"<good>{first} is awake: it speaks, thinks, and keeps watch.</> While it is with you, the camp is never "
            f"caught asleep."]


# ---------------------------------------------------------------------------- the illusions
def _distract(game, caster, spell, o, level: int) -> list[str]:
    here = _here_id(game)
    minutes = int(o.get("minutes", 1))
    stays = o.get("stays_from") is not None and level >= int(o["stays_from"])
    until = FOREVER if stays else _now(game) + int(spell.get("minutes", 1)) + minutes
    minus = int(o.get("minus", 5))
    old = _flags(game).get("distraction")
    if old and old.get("settlement") == here and int(old.get("until", 0)) >= _now(game) \
            and int(old.get("minus", 0)) > minus:
        minus, until = int(old["minus"]), max(until, int(old["until"]))
    _flags(game)["distraction"] = {"settlement": here, "until": until, "minus": minus}
    sight = {"minor_illusion": "a crash of pots from the next street, a cry, a dog that is not there",
             "silent_image": "a runaway cart that rolls down the street without a sound",
             "major_image": "smoke and the crackle of fire from a roof across the way, and the smell of it"}
    what = sight.get(spell.get("id", ""), "something that is not there")
    lasts = "until you leave the town" if stays else ("a minute" if minutes <= 1 else f"{minutes} minutes")
    return [f"{_first(caster)} makes a small movement, and every head turns: {what}.",
            f"<good>For {lasts} the town looks the other way</> <dim>(-{minus} to every watcher's Perception: "
            f"a quick hand, a slipped watch, a creep past the guards)</>."]


def towns_within(game, miles: int) -> list[Subject]:
    """Known towns within reach (Project Image)."""
    from realmwalker.game.state import MILES_PER_TILE

    p = game.player
    tile = MILES_PER_TILE
    out = []
    for sid in sorted(game.player.known_settlements):
        s = game.world.settlements[sid]
        d = max(abs(s.x - p.x), abs(s.y - p.y)) * tile
        if 0 < d <= miles:
            out.append(Subject(s.name, "town", sid, s.x, s.y, data={"miles": d}))
    out.sort(key=lambda s: s.data["miles"])
    return out[:30]


def _project(game, caster, spell, target) -> list[str]:
    from realmwalker.game import news, notices

    s = game.world.settlements[target.ref]
    out = [f"{_first(caster)} sits very still. Far away, in {esc(s.name)}, a figure just like them walks in through "
           f"the gate and looks about."]
    heard = news.hear(game, count=3, x=s.x, y=s.y)
    out += heard or ["<dim>There is no news there that you have not heard.</>"]
    board = [n for n in notices.read(game, s) if n.get("kind") != "wanted"]
    if board:
        out.append("On the board by the gate:")
        out += [f"<info>{esc(n['title'])}</>: {esc(n['text'])}" for n in board[:4]]
    return out


def _script(game, caster, spell, o) -> list[str]:
    days = int(o.get("days", 10))
    _flags(game)["script_until"] = _now(game) + int(spell.get("minutes", 1)) + days * DAY
    return [f"{_first(caster)} writes a short letter in grey ink and folds it. Read by anyone else, it shows the seal "
            f"and the hand they would most honour.",
            f"<good>For {days} days the watch waves you through the gates unsearched, and your papers speak for you "
            f"as a lord's.</>"]


def _mask(game, caster, spell, o, target) -> list[str]:
    item = target.ref
    hours = int(o.get("hours", 24))
    item.tags = [t for t in (item.tags or []) if not t.startswith("masked:")] + \
        [f"masked:{_now(game) + int(spell.get('minutes', 1)) + hours * 60}"]
    name = game.tables.items.name(item, False)
    return [f"{_first(caster)} draws a silk cloth over the {esc(name)}: <good>for a day its magic shows no aura, and "
            f"it looks like nothing much.</> <dim>(Robbers pass it over.)</>"]


def _sequester(game, caster, spell, target) -> list[str]:
    if target.kind == "body":
        from realmwalker.game import revival

        body = revival.body_of(game, target.ref)
        if body is None:
            return ["The body is not with you."]
        revival.repose(game, body, SEQUESTER_DAYS)
        return [f"{_first(caster)} sprinkles gem dust over {esc(target.ref.name.split()[0])}'s body: <good>it is held "
                f"out of time.</> No day passes for it until it is raised."]
    item = target.ref
    if "sequestered" not in (item.tags or []):
        item.tags = list(item.tags or []) + ["sequestered"]
    name = game.tables.items.name(item, False)
    return [f"{_first(caster)} sprinkles gem dust over the {esc(name)}: <good>it fades from every eye and every "
            f"divination but yours.</> No robber, thief or watchman will find it."]


# ---------------------------------------------------------------------------- the small arts
def forecast(game) -> str:
    """The weather here over the next day, in plain words (the world's own weather: it comes true)."""
    from realmwalker.world.weather import describe, weather_at

    p = game.player
    now = _now(game)
    seen = []
    for h in (0, 6, 12, 18, 24):
        w = weather_at(game.world, game.tables, p.x, p.y, now + h * 60)
        words = describe(w)
        if not seen or seen[-1][1] != words:
            seen.append((h, words))
    parts = [("now" if h == 0 else f"in {h} hours") + ": " + words for h, words in seen]
    return "; ".join(parts)


def _art(game, caster, spell, how: str) -> list[str]:
    from realmwalker.game import camp as campmod

    first = _first(caster)
    if how == "druidcraft":
        out = [f"{first} whispers to the wind and the grass. <good>The weather here {forecast(game)}.</>"]
        c = campmod.camp_here(game)
        if c is not None and not c.fire and game.world.settlement_at(game.player.x, game.player.y) is None:
            c.fire = True
            out.append("At a word, the camp's kindling catches.")
        return out
    if how == "elementalism":
        c = campmod.camp_here(game)
        if c is not None and not c.fire and game.world.settlement_at(game.player.x, game.player.y) is None:
            c.fire = True
            return [f"{first} beckons fire: a little cloud of embers drifts into the kindling, and it catches."]
        wet = [x for x in game.party if x.alive and getattr(x, "wet", 0) > 0]
        if wet:
            for x in wet:
                x.wet = max(0.0, float(x.wet) - 25.0)
            return [f"{first} beckons the air: a warm, steady breeze plucks at clothes and hair. "
                    f"<good>The party is a little drier.</>"]
        from realmwalker.game import spellwork

        spellwork._drink_all(game, 0.5 * len([x for x in game.party if x.alive]))
        return [f"{first} beckons water: <good>a cup of clean, cold water fills in each hand.</>"]
    if how == "prestidigitation":
        for x in game.party:
            if x.alive and getattr(x, "dirt", 0) > 0:
                x.dirt = max(0.0, float(x.dirt) - 30.0)
        _flags(game)["warm_meal"] = True
        return [f"{first} snaps their fingers over everyone in turn: <good>the grime of days lifts from skin and "
                f"clothes,</> and the next meal will be warm and tasty."]
    if how == "thaumaturgy":
        _flags(game)["booming"] = {"until": _now(game) + TALK_MINUTES}
        return [f"{first}'s voice booms, the ground trembles underfoot and the flames lean away. <good>For the talk "
                f"that follows, Advantage on Intimidation.</>"]
    return []


# ---------------------------------------------------------------------------- the door (game/spellwork)
def subjects(game, caster, sid: str, level: int | None = None) -> list[Subject]:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does, how = o.get("does"), o.get("how")
    if does == "mind" and how in ("friends", "truth", "geas", "memory"):
        return _people_near(game, _squares(spell))
    if does == "mind" and how == "antipathy":
        out = []
        for cid, plural in kinds_here(game):
            out.append(Subject(f"Antipathy: {plural}", "kind", cid, data={"how": "antipathy"}))
            out.append(Subject(f"Sympathy: {plural}", "kind", cid, data={"how": "sympathy"}))
        return out
    if does == "mind" and how == "awaken":
        return [Subject(a["name"], "animal", a) for a in _asleep_animals(game)]
    if does == "illusion" and how == "project":
        return towns_within(game, int(o.get("miles", 500)))
    if does == "illusion" and how in ("mask", "sequester"):
        from realmwalker.rules import magic
        from realmwalker.rules.inventory import carried

        out = []
        for it in carried(game.party):
            if how == "mask" and (not getattr(it, "magic", None) or masked(game, it)):
                continue
            if how == "sequester" and (sequestered(it) or game.tables.items.value(it) < 100):
                continue
            out.append(Subject(game.tables.items.name(it, False), "thing", it))
        if how == "sequester":
            from realmwalker.game import revival

            out += [Subject(f"the body of {b['char'].name}", "body", b["char"]) for b in revival.bodies(game)]
        return out[:40]
    return []


def problem(game, caster, sid: str, target) -> str | None:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does, how = o.get("does"), o.get("how")
    aimed = target is not None and not isinstance(target, Character)
    if does == "mind":
        if how in ("friends", "truth", "geas", "memory", "enthrall") and not _people_near(game, _squares(spell)):
            return "nobody is near enough" if game.local is not None and game.local.kind == "settlement" \
                else "only among townsfolk"
        if how == "antipathy" and not kinds_here(game):
            return "no creature roams this land to name"
        if how == "awaken" and not _asleep_animals(game):
            return "you have no animal to wake" if not game.leader.animals else "your animals are all awake"
        if how != "enthrall" and not aimed:
            return "choose who (←→)" if how != "antipathy" else "choose the kind, and which way (←→)"
    if does == "illusion":
        if how == "distract" and _here_id(game) is None:
            return "only in a town, where eyes can be drawn away"
        if how in ("project", "mask", "sequester") and not subjects(game, caster, sid):
            return {"project": "you know no town within 500 miles",
                    "mask": "you carry no magic thing to mask",
                    "sequester": "nothing you carry is worth hiding, and no body is with you"}[how]
        if how in ("project", "mask", "sequester") and not aimed:
            return "choose which (←→)"
    if does == "art" and how == "thaumaturgy" and _here_id(game) is None and game.local is None:
        return None
    return None


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    spell = dict(game.tables.spells[sid], id=sid)
    o = _road(spell)
    does, how = o.get("does"), o.get("how")
    if isinstance(target, Character):
        target = None
    if does == "mind":
        if how == "enthrall":
            return _enthrall(game, caster, spell, o)
        if how == "antipathy":
            return _antipathy(game, caster, spell, target, level)
        if how == "awaken":
            return _awaken(game, caster, spell, target)
        npc = game.world.npcs[target.ref]
        if how == "friends":
            return _friends(game, caster, spell, npc)
        if how == "truth":
            return _truth(game, caster, spell, npc)
        if how == "geas":
            return _geas(game, caster, spell, npc, level)
        return _memory(game, caster, spell, npc)
    if does == "illusion":
        if how == "distract":
            return _distract(game, caster, spell, o, level)
        if how == "project":
            return _project(game, caster, spell, target)
        if how == "script":
            return _script(game, caster, spell, o)
        if how == "mask":
            return _mask(game, caster, spell, o, target)
        return _sequester(game, caster, spell, target)
    return _art(game, caster, spell, how)
