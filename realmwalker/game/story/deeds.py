"""Part D's steps in play (Expansion 6 D.2, docs/ADVENTURES.md §6.2, §8.5): rescue, fetch, defeat, capture, recruit,
rally, hold, rite, escort and confront - how each is set up when its chapter opens, and what in the game finishes it.
Their binding (what a blueprint's step becomes) is story/steps.py; story/__init__.py calls in here from its hooks.

- `setup(game, adv)` once a chapter opens (and as a catch-up each day): a rescue or fetch becomes a step quest of the
  rescue or retrieve kind (the captive in chains, the chest with the story's thing, placed on the step's own level
  when the party comes down to it: quests.on_arrive_dungeon); a defeat or capture under a site binds its band to
  that level (`politics["story_sites"]`, or added on the way down to a level filled before); a hold sets its night.
- `on_arrive(game)`: a defeat or capture waiting on the land meets you there; a hold's night comes while you stand at
  its place (its waves, battle after battle with no rest); a rite is done where it must be, with what it needs.
- `on_descend(game, lm)`, `on_battle(game, result)`, `on_fate(game, creature, fate)` (from fight.decide_captive: a
  story foe taken alive and judged), `on_travel(game)` (an escort's ambush), `on_night(game, where)`, `daily(game)`
  (a hold's night missed fails it), `on_goal(game)` (a step's goal-language test, from goals.notify: the step is done
  however the hero made it true).
- endure (E.4): its day set when its chapter opens; its beat waits for the road or a night at camp (`_endure_due`),
  its op `endure` starts the battle (`endure`), and coming out of it alive does it (on_battle); a week unmet, it
  passes by itself.
- `talk_choices(conv)` / `talk_choose(conv, choice)`: recruit, rally, confront and setting out on an escort; the first
  three may become a situation (situations.for_step), which then finishes the step.

A step's record keeps its own progress: "set" (set up), "quest" (its step quest), "night" (in the target, a hold's
day), "wave", "met" (the day its band was last met), "asked" (the day a recruit or rally was refused), "taken".
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

KINDS = ("rescue", "fetch", "defeat", "capture", "recruit", "rally", "hold", "rite", "escort", "confront", "endure")
LOOSE = ("wave", "ambush", "endure")  # (a band with no named head: every one of it carries the role)
ENDURE_WAIT = 7  # days an endure's set piece waits for the road or a camp before it passes by itself
BAND_KINDS = ("defeat", "capture")
TALK_CHOICES = {"story_recruit", "story_rally", "story_confront", "story_escort"}

# Words used when adventures.json "words" has none of its own (a blueprint's words come with Part D's tales).
DEFAULT_WORDS = {
    "recruit_ask": ["Will you stand with us against {villain}?"],
    "recruit_yes": ["\"Yes. Yes, I will. Somebody has to.\""],
    "recruit_no": ["\"Not yet. Ask me again when I have slept on it.\""],
    "rally_ask": ["Call your people together. {villain} will not be stopped by one blade."],
    "rally_yes": ["\"Every man who can hold a spear will be at the gate. You have my word.\""],
    "rally_no": ["\"They are frightened. Give me a day, and ask me again.\""],
    "confront_ask": ["I know what you have done, {who}."],
    "confront_yield": ["\"...All right. All right. I'll tell you everything. Just keep them off me.\""],
    "confront_fight": ["\"You should have kept your mouth shut.\" There are men behind you now."],
    "escort_ask": ["We set out now, for {to}. Are you ready?"],
    "escort_set_out": ["\"I'm ready. Let's not stop until we're there.\""],
    "hold_set": ["They will come to {place} on the night of {night}. Be there."],
    "hold_wave": ["They come again, out of the dark, before you have caught your breath."],
    "hold_won": ["The last of them falls back into the dark, and the night is quiet. {place} still stands."],
    "hold_lost": ["{place} could not be held."],
    "hold_missed": ["You were not at {place} on the night they came."],
    "rite_done": ["It is done. The air itself seems to lighten."],
    "rite_fail": ["The words will not come right. You will have to try again tomorrow."],
    "rite_needs": ["You do not have what the rite needs."],
    "captive_talks": ["{who} talks, as the taken often do, and it is worth hearing."],
    "ambush": ["They were waiting for you on the road, as if they knew you would come this way."],
    "band_here": ["{who} is here, waiting for you."],
    "endure_here": ["They come for you as they were told to."],
    "endure_won": ["You came through it."],
    "endure_lost": ["You live, and that is all."],
    "endure_passed": ["Whatever was meant to find you never did."],
}


def _story():
    from realmwalker.game import story

    return story


def _today(game) -> int:
    return int(game.moment.total_days)


def say(game, adv: dict, key: str, rng=None, **more) -> str:
    """A line of the deeds' words (adventures.json "words", else DEFAULT_WORDS), filled with the tale's names."""
    from realmwalker.core import textgen
    from realmwalker.game.story import words as wordsmod

    tables = game.tables.adventures.get("words", {})
    lines = tables.get(key) or DEFAULT_WORDS[key]
    rng = rng or game.world.rng.child(f"deeds/{adv['id']}/{key}/{game.world.time}")
    words = dict(wordsmod.for_adventure(game, adv))
    words.update({k: str(v) for k, v in more.items()})
    return textgen.fill(rng.choice(lines), rng, tables, words)


def _open(game, kinds) -> list[tuple[dict, dict]]:
    """(adventure, step) for every open step of these kinds in the hero's live tales' current chapters."""
    story = _story()
    return [(adv, st) for adv in story.active(game) for st in story.open_steps(adv) if st["kind"] in kinds]


def role_name(game, adv: dict, role: str) -> str | None:
    """The name of the person a role is bound to (None: a band, a village, or someone not yet placed)."""
    from realmwalker.game.story import cast

    entry = adv["cast"].get(role) or {}
    if "lt" in entry:  # (a band's lieutenant names it while they are still the villain's: E.3)
        from realmwalker.game.story import lieutenants

        rec = lieutenants.of(game, adv, role)
        return lieutenants.full(rec) if rec is not None and rec["fate"] in lieutenants.FREE else None
    return cast.describe(game, adv, role) if cast.person(game.world, entry) is not None else None


def _place_words(game, place: dict) -> str:
    from realmwalker.game.story import places

    return places.name(game.world, place)


def _needs_met(game, adv: dict, needs: list[str]) -> bool:
    for n in needs:
        kind, _, what = n.partition(":")
        if kind == "key" and what not in adv["keys"]:
            return False
        if kind == "flag" and what not in adv["flags"]:
            return False
        if kind == "clue" and what not in adv.get("clues", {}):
            return False
        if kind == "item" and not any(what == it.def_id or what in (it.tags or []) for c in game.party
                                      for it in c.inventory):
            return False
    return True


def step_failed(game, adv: dict, st: dict, line: str | None = None) -> None:
    """A step that can no longer be done: it fails, leaves its codeword, and its chapter moves on (law 6)."""
    story = _story()
    if st["state"] != "open":
        return
    st["state"] = "failed"
    if line:
        story.journal(adv, line, _today(game))
        game.say(f"<warn>{esc(line)}</>", "story")
    if st.get("fails_to"):
        from realmwalker.game.story import beats

        beats.OPS["flag"](game, {"adv": adv["id"]}, st["fails_to"])
    story._chapter_check(game, adv)
    game.dirty = True


# ---------------------------------------------------------------------------- setting up (a chapter opens)
def setup(game, adv: dict) -> None:
    """The open chapter's Part D steps take their places in the world, once each."""
    story = _story()
    ch = story.chapter(adv)
    if ch is None or ch["state"] != "open" or adv["state"] != "active":
        return
    for st in ch["steps"]:
        if st["state"] == "open" and st["kind"] in SETUP and not st.get("set"):
            st["set"] = True
            SETUP[st["kind"]](game, adv, st)


def _giver(game, adv: dict):
    """Who stands behind a step quest: the patron if they are a townsperson, else nobody (the town's watch)."""
    from realmwalker.game.story import cast

    p = cast.person(game.world, adv["cast"].get("patron"))
    return p if p is not None and hasattr(p, "settlement") and getattr(p, "alive", False) else None


def _quest(game, adv: dict, st: dict, template: str, target: dict, words: dict) -> dict:
    """A step quest (ADVENTURES.md §8.5): an ordinary quest dict with `adventure` and `step`, the patron as giver, a
    long deadline and no pay of its own; it reports back through story.on_quest_end."""
    from realmwalker.game import quests
    from realmwalker.game.story import places

    w = game.world
    giver = _giver(game, adv)
    if giver is not None:
        town = w.settlements[giver.settlement]
    else:
        at = places.xy(w, adv["places"].get("town") or adv["places"]["home"])
        town = min(w.settlements, key=lambda s: (abs(s.x - at[0]) + abs(s.y - at[1]), s.id))
    q = quests.base_quest(game, giver, template, w.rng.child(f"stepquest/{adv['id']}/{st['id']}"), town=town)
    q.update({"adventure": adv["id"], "step": st["id"], "reward": 0, "state": "active", "text_key": f"story_{template}",
              "taken": game.moment.total_days, "days": 60})
    q["deadline"] = game.moment.total_days + q["days"]
    q["target"] = target
    q["words"].update({k: str(v) for k, v in words.items()})
    q["journal"].append(quests.fill(game, q, "journal"))
    game.quests.append(q)
    st["quest"] = q["id"]
    return q


def _where(game, adv: dict, site_id: int) -> str:
    from realmwalker.game.quests import direction

    w = game.world
    giver = _giver(game, adv)
    frm = w.settlements[giver.settlement] if giver is not None else None
    return direction(frm, w.sites[site_id]) if frm is not None else "not far"


def _setup_rescue(game, adv: dict, st: dict) -> None:
    from realmwalker.game.story import cast

    t = st["target"]
    site = t["place"]["site"]
    who = cast.person(game.world, t.get("who"))
    name = role_name(game, adv, t["role"]) or cap(cast.describe(game, adv, t["role"]))
    target = {"site": site, "captive": name, "level": int(t["n"]), "story": True}
    if who is not None and hasattr(who, "settlement"):
        target["npc"] = int(who.id)
        who.flags["captive"] = True
    _quest(game, adv, st, "rescue", target, {"captive": name, "site": game.world.sites[site].name,
                                             "where": _where(game, adv, site), "kin": "people"})


def _setup_fetch(game, adv: dict, st: dict) -> None:
    from realmwalker.core import textgen
    from realmwalker.game.story import words as wordsmod

    t = st["target"]
    site = t["place"]["site"]
    rng = game.world.rng.child(f"fetch/{adv['id']}/{st['id']}")
    tables = game.tables.adventures.get("words", {})
    name = textgen.fill(t["what"], rng, tables, wordsmod.for_adventure(game, adv))
    target = {"site": site, "item": name, "base": t["base"], "level": int(t["n"]), "tag": t["tag"], "story": True}
    _quest(game, adv, st, "retrieve", target, {"item": name, "site": game.world.sites[site].name,
                                               "where": _where(game, adv, site)})


def _setup_band(game, adv: dict, st: dict) -> None:
    t = st["target"]
    key = t.get("level")
    if key is None:
        return
    recs = game.world.politics.setdefault("story_sites", {}).setdefault(key, [])
    recs.append({"adv": adv["id"], "what": "band", "role": t["role"], "step": st["id"], "group": t["group"],
                 "name": role_name(game, adv, t["role"])})


def _setup_hold(game, adv: dict, st: dict) -> None:
    from realmwalker.game.quests import when_text

    t = st["target"]
    lo, hi = t["days"]
    rng = game.world.rng.child(f"hold/{adv['id']}/{st['id']}")
    t["night"] = _today(game) + rng.randint(int(lo), int(hi))
    line = say(game, adv, "hold_set", rng, place=_place_words(game, t["place"]), night=when_text(game, t["night"]))
    _story().journal(adv, line, _today(game))
    game.say(f"<warn>{esc(line)}</>", "story")


def _setup_endure(game, adv: dict, st: dict) -> None:
    lo, hi = st["target"].get("after", [0, 1])
    rng = game.world.rng.child(f"endure/{adv['id']}/{st['id']}")
    st["target"]["due"] = _today(game) + rng.randint(int(lo), int(hi))


SETUP = {"rescue": _setup_rescue, "fetch": _setup_fetch, "defeat": _setup_band, "capture": _setup_band,
         "hold": _setup_hold, "endure": _setup_endure}


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------- the story's bands
def band(game, adv: dict, st: dict, role: str, group: str, rng, said: list | None = None) -> list:
    """A band of the story spawned now (a step's foe, a wave): tagged with the tale, its first named for the role's
    person when there is one, or made the lieutenant at its head (what one who got away says goes in `said`)."""
    from realmwalker.game.encounters import land_budget
    from realmwalker.rules.creatures import spawn_group

    creatures = spawn_group(game.tables, group, rng, now=game.world.time, party_size=len(game.party),
                            budget=land_budget(game, rng.child("budget"), difficulty="high"))
    name = role_name(game, adv, role) if role not in LOOSE else None
    for i, c in enumerate(creatures):
        c.story = {"adv": adv["id"], "role": role if i == 0 or role in LOOSE else "minion",
                   "step": st["id"]}
        if i == 0 and st["kind"] == "capture":
            c.story["alive"] = True  # (wanted alive: a beaten blow knocks them out, on Auto too)
    if creatures and name:
        creatures[0].name, creatures[0].named = name, True
    from realmwalker.game.story import lieutenants

    back = lieutenants.on_spawn(game, adv, role, creatures, rng) if role not in LOOSE else ""
    if back and said is not None:
        said.append(back)
    return creatures


def _encounter(game, adv: dict, st: dict, role: str, group: str, intro: str):
    from realmwalker.game.encounters import make_encounter

    rng = game.world.rng.child(f"deed-fight/{adv['id']}/{st['id']}/{game.world.time}")
    enc = make_encounter(game, group, rng)
    said: list[str] = []
    enc.creatures = band(game, adv, st, role, group, rng.child("band"), said) or enc.creatures
    enc.intro = " ".join(said + [intro])
    enc.attitude = "hostile"
    game.encounter = enc
    game.travel = None
    return enc


# ---------------------------------------------------------------------------- listeners
def on_arrive(game) -> bool:
    """The party stands on a tile of the world map. True when something of a tale began here."""
    from realmwalker.game.story import places

    if game.encounter is not None or game.battle is not None:
        return False
    today = _today(game)
    for adv, st in _open(game, KINDS):
        t = st["target"]
        here = "place" in t and places.here(game, t["place"])
        if st["kind"] in BAND_KINDS and here and "level" not in t and int(st.get("met", -1)) != today:
            st["met"] = today
            who = role_name(game, adv, t["role"]) or "They"
            _encounter(game, adv, st, t["role"], t["group"], say(game, adv, "band_here", who=who))
            return True
        if st["kind"] == "hold" and here and _hold_due(game, st):
            return _wave(game, adv, st)
        if st["kind"] == "rite" and here and int(st.get("tried", -1)) != today:
            return _rite(game, adv, st)
    return False


def _hold_due(game, st: dict) -> bool:
    night = st["target"].get("night")
    if night is None or int(st.get("wave", 0)) > 0:
        return False
    today = _today(game)
    return today > int(night) or (today == int(night) and game.light < 0.5)


def _wave(game, adv: dict, st: dict) -> bool:
    t = st["target"]
    n = int(st.get("wave", 0))
    intro = say(game, adv, "hold_wave") if n else say(game, adv, "band_here", who=_villain_words(game, adv))
    st["wave"] = n + 1
    game.cue("horn")  # (out of the dark: D.5)
    enc = _encounter(game, adv, st, "wave", t["group"], intro)
    enc.field = t.get("field", "")  # (the ford with its carts burning: D.3)
    return True


def _villain_words(game, adv: dict) -> str:
    return f"The dead of {_story()._villain_name(game, adv)}" if (_story().threat_of(game, adv) or {}).get(
        "kind") == "risen" else "The enemy"


def _rite(game, adv: dict, st: dict) -> bool:
    from realmwalker.game import camp
    from realmwalker.game.story import beats

    t = st["target"]
    st["tried"] = _today(game)
    if not _needs_met(game, adv, t.get("needs", [])):
        game.say(f"<warn>{esc(say(game, adv, 'rite_needs'))}</>", "story")
        return False
    if st.get("beat") and beats.pending(game) is None:
        beats.offer(game, st["beat"], adv=adv["id"], step=st["id"], where=_story()._where(game))
        return True
    ok, roll = camp.check(game, t["skill"], int(t["dc"]))
    if ok:
        game.say(f"<good>{esc(say(game, adv, 'rite_done'))}</> {roll}", "story")
        _story().step_done(game, adv["id"], st["id"])
    else:
        game.say(f"<warn>{esc(say(game, adv, 'rite_fail'))}</> {roll}", "story")
    return False


def _endure_due(game) -> bool:
    """An endure's set piece whose day has come: its beat waits now (from the road and from a night at camp)."""
    from realmwalker.game.story import beats

    if beats.pending(game) is not None:
        return False
    for adv, st in _open(game, ("endure",)):
        due = st["target"].get("due")
        if due is None or st.get("offered") or _today(game) < int(due):
            continue
        st["offered"] = _today(game)
        beats.offer(game, st["target"]["beat"], adv=adv["id"], step=st["id"], where=_story()._where(game))
        return True
    return False


def endure(game, adv: dict, st: dict | None) -> list[str]:
    """The set piece's battle (the beat's op `endure`): a band of its group, every one of them tagged with the step."""
    if st is None or st["state"] != "open" or st["kind"] != "endure":
        return []
    st["fighting"] = _today(game)
    _encounter(game, adv, st, "endure", st["target"]["group"], say(game, adv, "endure_here"))
    return []


def on_night(game, where: str) -> bool:
    """A night at camp or at the inn where a hold is to be fought: its first wave comes. At camp, a set piece whose
    day has come."""
    from realmwalker.game.story import places

    if where == "camp" and _endure_due(game):
        return True
    for adv, st in _open(game, ("hold",)):
        if places.here(game, st["target"]["place"]) and st["target"].get("night") is not None and \
                _today(game) >= int(st["target"]["night"]) and int(st.get("wave", 0)) == 0:
            return _wave(game, adv, st)
    return False


def on_descend(game, lm) -> None:
    """Down into a level a step's band is bound to, filled before the tale began: the band is added to it now."""
    for adv, st in _open(game, BAND_KINDS):
        t = st["target"]
        if t.get("level") != lm.key:
            continue
        if any(getattr(c, "story", None) and c.story.get("adv") == adv["id"] and c.story.get("role") == t["role"]
               for a in lm.actors for c in a.creatures):
            continue
        spot = _far_spot(game, lm)
        if spot is None:
            continue
        rng = game.world.rng.child(f"deed-band/{adv['id']}/{st['id']}")
        creatures = band(game, adv, st, t["role"], t["group"], rng)
        if creatures:
            from realmwalker.game.encounters import LocalActor as Actor

            lm.actors.append(Actor(len(lm.actors) + 1, t["group"], spot[0], spot[1], creatures))


def _far_spot(game, lm) -> tuple[int, int] | None:
    """A free walkable square in the last open room of a level (where its master would stand)."""
    rooms = lm.meta.get("rooms", [])
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken = {(a.x, a.y) for a in lm.actors}
    hidden = set(lm.meta.get("hidden", []))
    for i in reversed([i for i in range(len(rooms)) if i not in hidden] or list(range(len(rooms)))):
        rx, ry, rw, rh = rooms[i]
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                if lm.in_bounds(x, y) and walk[x, y] and (x, y) not in taken and (x, y) not in lm.features \
                        and (x, y) != tuple(lm.entry):
                    return x, y
    return None


def on_battle(game, result) -> None:
    """After a fight: a step's band dead, taken or fled; a hold's wave beaten (the next comes at once) or the place
    lost."""
    from realmwalker.game.story import beats

    story = _story()
    how = {id(c): "dead" for c in result.dead}
    how.update({id(c): "taken" for c in getattr(result, "captives", [])})
    how.update({id(c): "fled" for c in getattr(result, "fled", [])})
    seen: dict[tuple, list[str]] = {}
    for c in list(result.dead) + list(getattr(result, "captives", [])) + list(getattr(result, "fled", [])):
        tag = getattr(c, "story", None) or {}
        if tag.get("adv") and tag.get("step"):
            seen.setdefault((tag["adv"], tag["step"], tag.get("role")), []).append(how[id(c)])
    waves = {(a, s) for (a, s, r) in seen if r == "wave"}
    for adv, st in _open(game, ("hold",)):
        if (adv["id"], st["id"]) not in waves and not (int(st.get("wave", 0)) > 0 and result.outcome != "victory"):
            continue
        if result.outcome != "victory":
            step_failed(game, adv, st, say(game, adv, "hold_lost", place=_place_words(game, st["target"]["place"])))
        elif int(st.get("wave", 0)) >= int(st["target"]["waves"]):
            line = say(game, adv, "hold_won", place=_place_words(game, st["target"]["place"]))
            story.journal(adv, line, _today(game))
            game.say(f"<good>{esc(line)}</>", "story")
            story.step_done(game, adv["id"], st["id"])
        else:
            _wave(game, adv, st)
    battle = getattr(game, "battle", None)
    fought = {((f.creature.story or {}).get("adv"), (f.creature.story or {}).get("step"))
              for f in getattr(battle, "fighters", [])
              if getattr(f, "creature", None) is not None and getattr(f.creature, "story", None)}
    for adv, st in _open(game, ("endure",)):
        if st.get("fighting") in (None, False) or not ((adv["id"], st["id"]) in fought or
                                                       (adv["id"], st["id"], "endure") in seen):
            continue
        st["fighting"] = False
        if result.outcome in ("defeat", "surrendered"):
            step_failed(game, adv, st, say(game, adv, "endure_lost"))
        else:
            line = say(game, adv, "endure_won")
            story.journal(adv, line, _today(game))
            game.say(f"<good>{esc(line)}</>", "story")
            story.step_done(game, adv["id"], st["id"])
    for adv, st in _open(game, BAND_KINDS):
        states = seen.get((adv["id"], st["id"], st["target"]["role"]))
        if not states:
            continue
        cls_slain_ok = st["kind"] == "defeat"
        if "dead" in states:
            if cls_slain_ok:
                beats.OPS["flag"](game, {"adv": adv["id"]}, f"{st['target']['role']}_slain")
                story.step_done(game, adv["id"], st["id"])
            else:
                step_failed(game, adv, st)
        elif "taken" in states:
            st["taken"] = True
            if st["kind"] == "defeat":
                beats.OPS["flag"](game, {"adv": adv["id"]}, f"{st['target']['role']}_taken")
                story.step_done(game, adv["id"], st["id"])
        elif "fled" in states and st["target"].get("fled_ok"):
            story.step_done(game, adv["id"], st["id"])


def on_fate(game, creature, fate: str) -> str | None:
    """A story foe taken alive is judged in the aftermath: a capture step is done (questioned, they give its lead and
    clues). Returns what they tell, or None."""
    from realmwalker.game.story import beats

    story = _story()
    tag = getattr(creature, "story", None) or {}
    adv = story.adventures(game.world).get(tag.get("adv"))
    st = story.find_step(game, tag.get("adv"), tag.get("step")) if adv is not None else None
    if adv is None or st is None or st["kind"] not in BAND_KINDS or tag.get("role") != st["target"]["role"]:
        return None
    beats.OPS["flag"](game, {"adv": adv["id"]}, f"{st['target']['role']}_{fate}")
    line = None
    if fate == "interrogate":
        line = say(game, adv, "captive_talks", who=creature.name if creature.named else f"The {creature.name}")
        story.journal(adv, line, _today(game))
    if st["state"] == "open":
        story.step_done(game, adv["id"], st["id"])
    return line


def on_travel(game) -> bool:
    """On the road with someone you escort: the step's ambush falls on you once, a few tiles out. A set piece whose
    day has come (endure) meets you on the road."""
    from realmwalker.game import quests

    if game.world.settlement_at(game.player.x, game.player.y) is None and _endure_due(game):
        return True
    p = game.player
    for adv, st in _open(game, ("escort",)):
        q = quests.by_id(game, st.get("quest"))
        if q is None or q["state"] not in quests.LIVE or not st["target"].get("ambush") or st.get("ambushed"):
            continue
        start = game.world.settlements[int(q["town"])]
        if max(abs(start.x - p.x), abs(start.y - p.y)) < 3 or game.world.settlement_at(p.x, p.y) is not None:
            continue
        st["ambushed"] = True
        _encounter(game, adv, st, "ambush", st["target"]["ambush"], say(game, adv, "ambush"))
        return True
    return False


def daily(game) -> None:
    """Once a day: the open chapters set up (a catch-up), and a hold whose night has passed without you fails."""
    story = _story()
    for adv in story.active(game):
        setup(game, adv)
    for adv, st in _open(game, ("hold",)):
        night = st["target"].get("night")
        if night is not None and _today(game) > int(night) + 1:  # (missed, or its waves left unfought)
            key = "hold_missed" if int(st.get("wave", 0)) == 0 else "hold_lost"
            step_failed(game, adv, st, say(game, adv, key, place=_place_words(game, st["target"]["place"])))
    for adv, st in _open(game, ("endure",)):  # (its band got past without a fight - slipped, talked, paid - is lived
        fought = st.get("fighting")           # through; never on the road nor at camp all that while: it passed you by)
        if fought not in (None, False) and _today(game) > int(fought) and game.encounter is None and \
                game.battle is None:
            st["fighting"] = False
            line = say(game, adv, "endure_won")
            story.journal(adv, line, _today(game))
            story.step_done(game, adv["id"], st["id"])
            continue
        due = st["target"].get("due")
        if due is not None and _today(game) > int(due) + ENDURE_WAIT and not st.get("fighting"):
            line = say(game, adv, "endure_passed")
            story.journal(adv, line, _today(game))
            game.say(f"<dim>{esc(line)}</>", "story")
            story.step_done(game, adv["id"], st["id"])


def on_goal(game) -> None:
    """Something happened that may make a step's goal true (goals.notify): any open step whose test now holds is done,
    however the hero made it so."""
    from realmwalker.game.story import goals
    from realmwalker.game.story.steps import STEPS

    story = _story()
    for adv in story.active(game):
        for st in story.open_steps(adv):
            test = STEPS[st["kind"]].goal(st)
            if test is None:
                continue
            sit = {"roles": dict(adv["cast"]), "flags": list(adv["flags"]), "adventure": adv["id"]}
            try:
                ok = goals.test(game, sit, test)
            except (KeyError, TypeError, ValueError):
                ok = False
            if ok:
                story.step_done(game, adv["id"], st["id"])


# ---------------------------------------------------------------------------- talk
def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice
    from realmwalker.game.story import situations

    game, npc = conv.game, conv.npc
    story = _story()
    out = []
    today = _today(game)
    for adv, st in _open(game, ("recruit", "rally", "confront", "escort")):
        t = st["target"]
        data = {"adv": adv["id"], "step": st["id"]}
        if st.get("inside") is not None and situations.of_step(game, st) is not None:
            continue  # (the step became a situation: its own talk, C.10)
        mine = story._is(game, t.get("who"), npc)
        if st["kind"] in ("recruit", "confront") and mine:
            if situations.for_step(game, adv, st, npc) is not None:
                continue
            if st["kind"] == "recruit" and int(st.get("asked", -1)) == today:
                continue
            key = "recruit_ask" if st["kind"] == "recruit" else "confront_ask"
            out.append(Choice(f"story_{st['kind']}", say(game, adv, key, who=npc.first_name), data=data))
        elif st["kind"] == "rally" and npc.settlement == t["place"]["settlement"] and int(st.get("asked", -1)) != today \
                and (mine if "who" in t else npc.notable or npc.job in ("headman", "elder", "lord", "guard")):
            if situations.for_step(game, adv, st, npc) is not None:
                continue
            out.append(Choice("story_rally", say(game, adv, "rally_ask"), data=data))
        elif st["kind"] == "escort" and mine and st.get("quest") is None:
            out.append(Choice("story_escort", say(game, adv, "escort_ask", to=_place_words(game, t["to"])),
                              data=data))
    return out


def talk_choose(conv, choice) -> None:
    from realmwalker.game.story import beats

    game, npc = conv.game, conv.npc
    story = _story()
    adv = story.adventures(game.world).get(choice.data.get("adv"))
    st = story.find_step(game, choice.data.get("adv"), choice.data.get("step"))
    if adv is None or st is None or st["state"] != "open":
        return
    t = st["target"]
    rec = {"adv": adv["id"]}
    story._bind_if_waiting(game, adv, st, npc)
    if choice.id == "story_recruit":
        paid = t.get("price", 0) > 0 and game.leader.money >= int(t["price"])
        ok, roll = (True, "") if paid else conv.check(t["skill"], int(t["dc"]))
        if paid:
            game.leader.money -= int(t["price"])
        if ok:
            conv.note(esc(say(game, adv, "recruit_yes", who=npc.first_name)) + (f" {roll}" if roll else ""))
            for line in beats.OPS["key"](game, rec, t["role"]):
                conv.note(line)
            story.step_done(game, adv["id"], st["id"])
        else:
            st["asked"] = _today(game)
            conv.note(esc(say(game, adv, "recruit_no", who=npc.first_name)) + f" {roll}")
    elif choice.id == "story_rally":
        ok, roll = conv.check(t["skill"], int(t["dc"]))
        if ok:
            conv.note(esc(say(game, adv, "rally_yes")) + f" {roll}")
            for line in beats.OPS["key"](game, rec, "militia"):
                conv.note(line)
            story.step_done(game, adv["id"], st["id"])
        else:
            st["asked"] = _today(game)
            conv.note(esc(say(game, adv, "rally_no")) + f" {roll}")
    elif choice.id == "story_confront":
        knows = t.get("clue") and t["clue"] in adv.get("clues", {})
        ok, roll = (True, "") if knows else conv.check(t["skill"], int(t["dc"]))
        if ok:
            conv.note(esc(say(game, adv, "confront_yield", who=npc.first_name)) + (f" {roll}" if roll else ""))
            beats.OPS["flag"](game, rec, f"{t['role']}_yielded")
            story.step_done(game, adv["id"], st["id"])
        else:
            conv.note(esc(say(game, adv, "confront_fight", who=npc.first_name)) + f" {roll}")
            _encounter(game, adv, st, t["role"], t["group"], say(game, adv, "confront_fight", who=npc.first_name))
            conv.ended = True
    elif choice.id == "story_escort":
        from realmwalker.game import quests

        q = _quest(game, adv, st, "escort", {"dest": int(t["to"]["settlement"]), "npc": int(npc.id), "story": True},
                   {"traveller": npc.name, "dest": _place_words(game, t["to"]),
                    "where": quests.direction(game.world.settlements[npc.settlement],
                                              game.world.settlements[int(t["to"]["settlement"])])})
        npc.flags["escort"] = q["id"]
        npc.present = False
        conv.note(esc(say(game, adv, "escort_set_out", who=npc.first_name)))
        conv.ended = True
    game.dirty = True
