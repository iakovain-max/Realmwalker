"""Talking (Expansion 3 E.3): the spells of speech outside a fight, and the tongues of those met on the road.

A spell's {"op": "road", "does": "speak" | "send" | "read", ...} is done here (game/spellwork's door sends it here):
Speak with Dead asks a foe slain in the last fight, Speak with Plants asks the land, Message, Sending, Animal Messenger,
Dream and Telepathy reach a companion who waits far away (or send a named beast a nightmare), and Detect Thoughts
reads a person near you. The lasting ones are buffs read here: Comprehend Languages ("comprehend"), Tongues
("tongues") and Speak with Animals ("beast_speech") open words with a band on the road (`talk_problem`).
"""

from __future__ import annotations

import math

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject, mark, way_words
from realmwalker.rules.character import Character

WALK_MILES_A_DAY = 24  # PHB 2024 travel pace, normal
BIRD_MILES_A_DAY = 50  # Animal Messenger: a beast that flies
ANIMAL_REACH = 50  # miles at level 2 (24 hours); each slot level above adds two days, 100 miles more
NIGHTMARE_DICE = "3d6"
LANGUAGE_DC = 5  # Comprehend Languages: they are understood, and half understand your signs
UNSPOKEN = ("one other language", "two other languages")  # (a stat block's words for "some tongue": not counted)
THINKING_SQUARES = 6  # Detect Thoughts: 30 feet
FRESH_MINUTES = 24 * 60  # Speak with Dead: the bodies of the last fight lie where it was for a day


def _road(spell: dict) -> dict:
    return next((o for o in spell.get("effects", ()) if o.get("op") == "road"), {})


def _first(c) -> str:
    return esc(c.name.split()[0])


def _alive(game) -> list[Character]:
    return [c for c in game.party if c.alive]


# ---------------------------------------------------------------------------- tongues on the road
def tongues_of(game, creatures) -> list[str]:
    """The languages a band speaks (from their stat blocks)."""
    out: list[str] = []
    for c in creatures:
        for lang in game.tables.creatures[c.def_id].get("languages", ()) or ():
            if lang not in UNSPOKEN and lang not in out:
                out.append(lang)
    return out


def party_tongues(game) -> set[str]:
    out = {"Common"}
    for c in _alive(game):
        out |= set(c.languages or ())
    return out


def anyone(game, key: str) -> bool:
    from realmwalker.rules import spells as spellrules

    return any(spellrules.lasting_flag(c, game.tables, key) for c in _alive(game))


def talk_problem(game, creatures) -> tuple[int, str]:
    """Words with a band: (extra DC, why it cannot be done or ""). Beasts listen only to Speak with Animals; a band
    that shares no tongue with the party cannot be talked past, unless someone has Tongues (or harder, with
    Comprehend Languages)."""
    kinds = {game.tables.creatures[c.def_id].get("kind") for c in creatures}
    if "beast" in kinds:
        return (0, "") if anyone(game, "beast_speech") else (0, "animals do not bargain")
    theirs = tongues_of(game, creatures)
    if not theirs or set(theirs) & party_tongues(game) or anyone(game, "tongues"):
        return 0, ""
    if anyone(game, "comprehend"):
        return LANGUAGE_DC, ""
    return 0, f"you share no tongue with them (they speak {', '.join(theirs)})"


# ---------------------------------------------------------------------------- the dead of the last fight
def remember_the_dead(game, battle, group: str | None) -> None:
    """After a fight: who fell on the other side, where (Speak with Dead asks them while you are still there)."""
    from realmwalker.rules.combat import FOE

    dead = []
    for f in battle.side(FOE):
        c = f.creature
        if c is None or c.alive and c.hp > 0:
            continue
        d = game.tables.creatures[c.def_id]
        dead.append({"name": c.name, "def_id": c.def_id, "kind": d.get("kind", ""), "named": bool(c.named)})
    if not dead:
        game.fresh_dead = None  # (the last fight left no one to ask)
        return
    p = game.player
    game.fresh_dead = {"map": game.local.key if game.local is not None else None, "x": p.x, "y": p.y,
                       "time": game.world.time, "group": group, "dead": dead}


def _corpses(game) -> list[Subject]:
    rec = getattr(game, "fresh_dead", None)
    if not rec:
        return []
    p = game.player
    here = game.local.key if game.local is not None else None
    if (rec["x"], rec["y"]) != (p.x, p.y) or rec["map"] != here or game.world.time - rec["time"] > FRESH_MINUTES:
        return []
    out = []
    for i, d in enumerate(rec["dead"]):
        if d["kind"] == "undead" or d.get("asked"):
            continue
        what = game.tables.creatures[d["def_id"]]["name"]
        name = d["name"] if d["named"] else f"the dead {what}"
        out.append(Subject(name, "corpse", i, data=d))
    return out


GANGS = {"gang": ("bandit", "tough", "scout", "bandit_captain", "tough_boss"), "cult": ("cultist", "cultist_fanatic"),
         "tribe": ("goblin", "hobgoblin", "bugbear", "orc", "gnoll", "ogre")}


def _band_of(game, def_id: str):
    """The faction a fallen foe belonged to: the nearest gang, cult or tribe of its kind with a place of its own."""
    from realmwalker.world import factions as fx

    w = game.world
    p = game.player
    for kind, ids in GANGS.items():
        if not any(def_id.startswith(i) for i in ids):
            continue
        found = [f for f in fx.active_factions(w, kind) if 0 <= f.site < len(w.sites)]
        if found:
            return min(found, key=lambda f: math.hypot(w.sites[f.site].x - p.x, w.sites[f.site].y - p.y))
    return None


def _speak_dead(game, caster, spell, target) -> list[str]:
    from realmwalker.game import quests

    w = game.world
    d = target.data
    d["asked"] = True  # (not again: the book's ten days, and the band's dead are gone by then)
    first = _first(caster)
    out = [f"{first} burns the incense over {esc(target.name)}. The jaw moves; the voice is dry as leaves."]
    kind = d["kind"]
    if kind == "beast":
        return out + ["<dim>It knew hunger, the scent of the trail and the dark of its den, and nothing more.</>"]
    band = _band_of(game, d["def_id"])
    if band is None:
        return out + ["\"We came for what you carried. Nobody sent us.\" <dim>It knows nothing more worth the "
                      "asking.</>"]
    site = w.sites[band.site]
    p = game.player
    p.explored[site.x, site.y] = True
    leader = w.figures.get(band.leader)
    out.append(f"<good>\"{esc(band.name)}. We keep to {esc(site.name)}\"</> ({way_words(site.x - p.x, site.y - p.y, 'miles')}). "
               f"<dim>(The place is on your map.)</>")
    if leader is not None and leader.died is None:
        out.append(f"\"{esc(leader.name)} sent us.\"")
    for q in quests.active(game):
        t = q["target"]
        if t.get("gang") == band.id or t.get("cult") == band.id:
            if q["template"] == "investigate" and not t.get("clue"):
                t["clue"] = True
                q["journal"].append(f"The trail leads to {site.name}.")
            if q.get("hidden") and not q.get("revealed"):
                quests.reveal(game, q)
    return out


# ---------------------------------------------------------------------------- the plants
def _outdoors(game) -> bool:
    lm = game.local
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return False
    return lm is None or (lm.kind not in ("dungeon", "settlement") and not lm.under_rock(game.player.lx,
                                                                                         game.player.ly))


def _speak_plants(game, caster, spell) -> list[str]:
    from realmwalker.rules.creatures import choose_encounter

    w = game.world
    p = game.player
    rng = w.rng.child(f"plants/{w.time}")
    group = choose_encounter(game.tables, game.land_key(p.x, p.y), int(w.danger[p.x, p.y]), True,
                             bool(w.road[p.x, p.y]), rng)
    out = [f"{_first(caster)} speaks to the grass and the trees, and they rustle back."]
    if group is not None:
        name = game.tables.creatures.encounters[group].get("name", group)
        out.append(f"<warn>{esc(name[:1].upper() + name[1:])} passed by in the night, and roam near still.</>")
    else:
        out.append("Nothing bigger than a fox passed in the last day.")
    for c in game.party:
        c.effects["forewarned"] = max(float(c.effects.get("forewarned", 0)), 4.0)
        c.effects["forage_tip"] = max(float(c.effects.get("forage_tip", 0)), 12.0)
    out.append("<good>For a few hours a band is seen before it sees you, and the plants show where food grows</> "
               "<dim>(+5 to forage).</>")
    return out


# ---------------------------------------------------------------------------- messages to companions far away
def _waiting(game) -> list[Character]:
    return [c for c in getattr(game, "waiting", []) if c.alive and c.companion]


def _miles_to(game, c) -> int:
    from realmwalker.game.state import MILES_PER_TILE

    at = c.companion.get("wait_at") or [game.player.x, game.player.y]
    return int(round(math.hypot(at[0] - game.player.x, at[1] - game.player.y) * MILES_PER_TILE))


def _here(game, c) -> bool:
    return c.companion.get("wait_at") == [game.player.x, game.player.y]


def _send_subjects(game, caster, how: str, level: int) -> list[Subject]:
    out = []
    for c in _waiting(game):
        if how == "message" and not _here(game, c):
            continue
        if how != "message" and _here(game, c):
            continue
        if how == "animal" and _miles_to(game, c) > animal_reach(level):
            continue
        out.append(Subject(f"{c.name.split()[0]} ({_miles_to(game, c)} miles off)" if how != "message"
                           else c.name.split()[0], "companion", c))
    if how == "dream":
        from realmwalker.game.divining import _figure_subjects

        for s in _figure_subjects(game):
            fig = game.world.figures[s.ref]
            if fig.kind in ("beast", "dragon"):
                out.append(Subject(f"a nightmare for {s.name}", "nightmare", s.ref))
    return out


def animal_reach(level: int) -> int:
    return ANIMAL_REACH + 100 * max(0, level - 2)


def _call(game, c, days: float) -> str:
    """A waiting companion sets out to meet the party where it stands (game/companions.rejoin)."""
    p = game.player
    c.companion["wait_at"] = [p.x, p.y]
    c.companion["coming"] = int(game.world.time + days * 24 * 60)
    here = game.world.settlement_at(p.x, p.y)
    span = "a few hours" if days < 0.5 else "a day" if days < 1.5 else f"{round(days)} days"
    return (f"{esc(c.name.split()[0])} sets out to meet you {'in ' + esc(here.name) if here else 'here'}: "
            f"about {span} on the road. <dim>Wait for them here.</>")


def _send(game, caster, spell, target, level: int) -> list[str]:
    from realmwalker.game import companions

    how = _road(spell)["how"]
    first = _first(caster)
    if target.kind == "nightmare":
        return _nightmare(game, caster, spell, target)
    c = target.ref
    who = esc(c.name.split()[0])
    if how == "message":
        out = [f"{first} points the copper wire towards where {who} waits and whispers. A whisper comes back."]
        c.companion.pop("coming", None)
        return out + companions.rejoin(game)
    miles = _miles_to(game, c)
    walk = miles / WALK_MILES_A_DAY
    if how == "animal":
        out = [f"{first} coaxes a bird down with a morsel and whispers the words to it; it flies off at once."]
        return out + [_call(game, c, miles / BIRD_MILES_A_DAY + walk)]
    if how == "dream":
        out = [f"{first} sinks into a trance and walks into {who}'s sleep, {miles} miles away, to tell them to come."]
    elif how == "telepathy":
        out = [f"{first} turns the silver ring and {who}'s thoughts are suddenly there, {miles} miles off, as if "
               f"they stood beside you."]
    else:
        out = [f"{first} speaks twenty-five words into the copper wire, and {who} hears them, {miles} miles away."]
    return out + [_call(game, c, walk)]


def _nightmare(game, caster, spell, target) -> list[str]:
    from realmwalker.game.divining import scry_bonus
    from realmwalker.rules.spells import save_dc

    w = game.world
    fig = w.figures[target.ref]
    rng = w.rng.child(f"dream/{target.ref}/{w.time}")
    dc = save_dc(game.sheet(caster), game.tables)
    roll = dice.d20(rng).natural
    bonus = scry_bonus(game, fig)
    said = f"<dim>(Wisdom save {roll} {bonus:+d} = {roll + bonus} vs DC {dc})</>"
    out = [f"{_first(caster)} sinks into a trance and walks into the sleep of {esc(fig.name)} as a thing of terror."]
    if roll + bonus >= dc:
        return out + [f"<warn>It wakes snarling and shakes the dream off.</> {said}"]
    hurt = dice.roll(NIGHTMARE_DICE, rng).total
    game.renown.flags.setdefault("nightmares", {})[fig.name] = {"damage": hurt, "until": w.time + 24 * 60}
    return out + [f"<good>It thrashes in its sleep and wakes worn and hurt</> ({hurt} psychic, and no rest from the "
                  f"night): if you meet it within a day, it meets you weaker. {said}"]


def nightmares_at_the_start(game, creatures) -> list[str]:
    """A named beast or dragon sent a nightmare by Dream meets the party hurt (and unrested)."""
    held = game.renown.flags.get("nightmares") if getattr(game, "renown", None) is not None else None
    if not held:
        return []
    out = []
    for c in creatures:
        rec = held.get(c.name) if c.named else None
        if rec is None:
            continue
        del held[c.name]
        if rec["until"] < game.world.time:
            continue
        c.hp = max(1, c.hp - int(rec["damage"]))
        out.append(f"<good>{esc(c.name)} is haggard from a night of terrors</> ({int(rec['damage'])} hurt).")
    for name in [n for n, r in held.items() if r["until"] < game.world.time]:
        del held[name]
    return out


# ---------------------------------------------------------------------------- reading a mind (Detect Thoughts)
def _people_near(game) -> list[Subject]:
    lm = game.local
    if lm is None or lm.kind != "settlement" or not isinstance(game.world.npcs, dict):
        return []
    p = game.player
    here = game.world.settlement_at(p.x, p.y)
    out = []
    for npc in game.world.npcs.values():
        if here is None or npc.settlement != here.id or not npc.alive or not npc.present:
            continue
        if max(abs(npc.x - p.lx), abs(npc.y - p.ly)) <= THINKING_SQUARES:
            out.append(Subject(npc.name if npc.known else npc.label(), "person", npc.id, npc.x, npc.y))
    return out


def _read(game, caster, spell, target) -> list[str]:
    from realmwalker.game import quests
    from realmwalker.rules.spells import save_dc

    w = game.world
    first = _first(caster)
    if target is None:  # (no one near: the thinking minds round about, through the walls)
        return _sense_minds(game, caster, spell)
    npc = w.npcs[target.ref]
    rng = w.rng.child(f"thoughts/{npc.id}/{w.time}")
    dc = save_dc(game.sheet(caster), game.tables)
    roll = dice.d20(rng).natural
    bonus = 2 if npc.notable else 0
    said = f"<dim>(Wisdom save {roll} {bonus:+d} = {roll + bonus} vs DC {dc})</>"
    name = esc(npc.first_name)
    feel = ("warm towards you" if npc.disposition >= 20 else "wary of you" if npc.disposition < 0
            else "indifferent to you")
    out = [f"{first} touches the copper coin and listens: {name} is thinking of {_foremost(npc, rng)}, "
           f"and feels {feel}."]
    if roll + bonus >= dc:
        npc.disposition -= 5
        return out + [f"<warn>{name} feels you probing and shuts you out, frowning at you.</> {said}"]
    want = npc.profile.get("want")
    secret = npc.profile.get("secret")
    if want:
        out.append(f"<good>What {name} wants:</> {esc(want)}")
    if secret:
        out.append(f"<good>What {name} hides:</> {esc(secret)}")
    for q in quests.active(game) + [q for q in game.quests if q["state"] == "offered"]:
        if q.get("giver") == npc.id and q.get("hidden") and not q.get("revealed"):
            quests.reveal(game, q)
            out.append("<warn>And the work they gave you is not what they told you.</> <dim>(The journal has it.)</>")
            break
    return out + [said]


def _foremost(npc, rng) -> str:
    return rng.choice(["the day's work and what it will pay", "supper", "someone they love", "an old quarrel",
                       "the price of bread", "a debt", "you, and what you might want"])


def _sense_minds(game, caster, spell) -> list[str]:
    from realmwalker.game.divining import _bands_near

    lm = game.local
    out = [f"{_first(caster)} listens for thoughts within thirty feet."]
    found = 0
    if lm is not None:
        for a, hits, where in _bands_near(game, lm, THINKING_SQUARES,
                                          lambda c: bool(tongues_of(game, [c]))):
            mark(game, a.x, a.y, "creature", 1, actor=a.id)
            out.append(f"<warn>Minds, {where}.</>")
            found += 1
    return out + ([] if found else ["<dim>No thinking mind is near.</>"])


# ---------------------------------------------------------------------------- the door
def subjects(game, caster, sid: str, level: int | None = None) -> list[Subject]:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does = o.get("does") or spell.get("road_too")
    if does == "speak" and o.get("with") == "dead":
        return _corpses(game)
    if does == "send":
        return _send_subjects(game, caster, o["how"], level or int(spell["level"]))
    if does == "read":
        return _people_near(game)
    return []


def problem(game, caster, sid: str, target) -> str | None:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does = o.get("does") or spell.get("road_too")
    aimed = target is not None and not isinstance(target, Character)
    if caster.uses.get("addled"):
        return "the mind is still reeling from what it touched (a long rest)"
    if does == "speak":
        if o.get("with") == "dead":
            if not _corpses(game):
                return "no corpse from your last fight lies here to ask"
            if not aimed:
                return "choose the corpse to ask (←→)"
        elif not _outdoors(game):
            return "only where plants grow wild"
    if does == "send":
        if not subjects(game, caster, sid):
            if o["how"] == "message":
                return "nobody you know waits near enough to hear a whisper"
            if o["how"] == "animal":
                return "no companion waits within the bird's reach"
            return "no companion of yours waits far away"
        if not aimed:
            return "choose who to reach (←→)"
        if o["how"] == "animal" and not _outdoors(game) and game.local is not None and game.local.kind == "dungeon":
            return "no bird comes under the ground"
    if does == "read" and not _people_near(game) and (game.local is None or game.local.kind != "dungeon"):
        return "nobody is near enough to read"
    return None


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does = o.get("does") or spell.get("road_too")
    if isinstance(target, Character):
        target = None
    if does == "speak":
        if o.get("with") == "dead":
            return _speak_dead(game, caster, spell, target)
        return _speak_plants(game, caster, spell)
    if does == "send":
        return _send(game, caster, spell, target, level)
    return _read(game, caster, spell, target)
