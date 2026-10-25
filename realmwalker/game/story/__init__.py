"""The story engine, the player's side (Expansion 6, docs/ADVENTURES.md): adventures forged from the world's threats,
their steps and beats, villains who act, finales and endings.

This package is the one door the rest of the game calls (§8.4); the world's side of a story, the threats, is
world/threats.py and runs without a game. The hooks:
- `daily` (pass_time's day change; its own catch-up stamp): quiet lowers the villain's attention, steps repair
  themselves, carried means finish a prepare step, scheduled beats come due, an adventure whose threat ended in the
  world ends too; the factions you serve send their commissions (story/work.py);
- `on_travel` (before a travel event; True when a story beat takes its place), `on_arrive` (a tile of the world map),
  `on_enter_town`, `on_night` (camp and inn), `on_descend` (a dungeon level), `on_battle` (after past.on_battle,
  whether or not there are jobs), `on_quest_end`, `on_read`;
- `talk_choices`/`talk_choose` (STORY_CHOICES): witnesses, the ones who know, patrons, hooks;
- `boss_for` (dungeon.populate, with precedence over the rest), `map_marks`, `notices`, `begin` (a new life),
  `on_death`.
Records: `politics["adventures"]` (story/forge.py), `politics["director"]` (the pending beat, scheduled beats,
counters), `politics["story_sites"]`, `politics["story_people"]`.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

# The modules whose handlers fill the registries story/check.py reads (step kinds, selectors, ops, keys).
HANDLER_MODULES = ("realmwalker.world.threats", "realmwalker.game.story.selectors", "realmwalker.game.story.cast",
                   "realmwalker.game.story.steps", "realmwalker.game.story.beats", "realmwalker.game.story.endings",
                   "realmwalker.game.story.finale", "realmwalker.game.story.stage", "realmwalker.game.story.goals",
                   "realmwalker.game.story.situations", "realmwalker.game.story.opening")
STORY_CHOICES = {"story_witness", "story_learn", "story_patron", "story_hook", "sit_ask", "sit_take", "sit_refuse",
                 "sit_act", "fav_call", "fav_hide", "contact_ask",  # (situations, C.6; favours and contacts, C.7)
                 "story_recruit", "story_rally", "story_confront", "story_escort"}  # (Part D's steps: story/deeds.py)


def load_all() -> None:
    import importlib

    for name in HANDLER_MODULES:
        importlib.import_module(name)


# ---------------------------------------------------------------------------- records
def adventures(world) -> dict:
    return world.politics.setdefault("adventures", {})


def active(game) -> list[dict]:
    """The hero's live adventures, oldest first."""
    from realmwalker.game.story.forge import life_of

    life = life_of(game)
    return [a for a in sorted(adventures(game.world).values(), key=lambda a: int(a["id"][1:]))
            if a["state"] == "active" and a["hero"]["life"] == life]


def chapter(adv: dict) -> dict | None:
    i = int(adv["chapter"])
    return adv["chapters"][i] if 0 <= i < len(adv["chapters"]) else None


def open_steps(adv: dict) -> list[dict]:
    ch = chapter(adv)
    return [st for st in ch["steps"] if st["state"] == "open"] if ch else []


def find_step(game, aid: str, sid: str | None) -> dict | None:
    adv = adventures(game.world).get(aid)
    if adv is None or sid is None:
        return None
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            if st["id"] == sid:
                return st
    return None


def threat_of(game, adv: dict) -> dict | None:
    from realmwalker.world import threats

    return threats.records(game.world).get(adv["threat"])


def journal(adv: dict, line: str, day: int) -> None:
    adv.setdefault("journal", []).append({"day": int(day), "text": line})


# ---------------------------------------------------------------------------- steps and chapters
def step_done(game, aid: str, sid: str | None) -> list[str]:
    """A step is done: what it gives (clues, keys, codewords), the villain's notice, and the chapter, if that was
    enough, ends with its reveal and opens the next (its title card waits for the beat screen)."""
    from realmwalker.game.story import beats, villain

    adv = adventures(game.world).get(aid)
    st = find_step(game, aid, sid)
    if adv is None or st is None or st["state"] != "open" or adv["state"] != "active":
        return []
    st["state"] = "done"
    for g in st.get("gives", []):
        kind, _, what = g.partition(":")
        rec = {"adv": aid}
        if kind == "clue":
            beats.OPS["clue"](game, rec, what)
        elif kind == "key":
            beats.OPS["key"](game, rec, what)
        elif kind == "flag" and "|" not in what:
            beats.OPS["flag"](game, rec, what)
        elif kind == "lead":
            adv.setdefault("leads", []).append(what)
    villain.on_step(game, adv, st)
    _chapter_check(game, adv)
    game.dirty = True
    return []


def _chapter_check(game, adv: dict) -> None:
    from realmwalker.game.story import beats

    ch = chapter(adv)
    if ch is None or ch["state"] == "done":
        return  # (a last chapter stays the current one: it is done, and paid, once)
    required = [s for s in ch["steps"] if not s["optional"]]
    done = [s for s in required if s["state"] in ("done", "failed")]  # (a failed step moves the tale on: law 6)
    need = len(required) if ch["need"] == "all" else min(int(ch["need"]), len(required))
    if len(done) < need:
        return
    ch["state"] = "done"
    day = int(game.moment.total_days)
    journal(adv, ch["reveal"], day)
    game.say(f"<title>{esc(ch['title'])}</> <dim>is behind you.</> {esc(ch['reveal'])}", "story")
    game.cue("reveal")
    from realmwalker.game.story import experience

    for line in experience.award(game, "chapter", f"chapter/{adv['id']}/{adv['chapter']}"):  # (a high budget: C.8)
        game.say(line, "good")
    beats.OPS["clock"](game, {"adv": adv["id"]}, -10)  # (a chapter done holds the villain's scheme a while)
    if int(adv["chapter"]) + 1 < len(adv["chapters"]):
        adv["chapter"] = int(adv["chapter"]) + 1
        nxt = chapter(adv)
        nxt["state"] = "open"
        journal(adv, nxt["opening"], day)
        beats.director(game.world)["card"] = {"adv": adv["id"], "chapter": int(adv["chapter"])}
        from realmwalker.game.story import deeds

        deeds.setup(game, adv)  # (its rescues, fetches, bands and nights take their places: D.2)


def begin_card(game, adv: dict) -> None:
    from realmwalker.game.story import beats

    journal(adv, adv["words"]["hook"], int(game.moment.total_days))
    journal(adv, adv["chapters"][0]["opening"], int(game.moment.total_days))
    beats.director(game.world)["card"] = {"adv": adv["id"], "chapter": 0}


# ---------------------------------------------------------------------------- the story's foes
def villain_group(game, adv: dict) -> tuple[str | None, str]:
    from realmwalker.game import past
    from realmwalker.world import threats

    t = threat_of(game, adv)
    fig = threats.villain_figure(game.world, t) if t else None
    if fig is None:
        return None, ""
    group = past.group_of(game, fig) if fig.kind == "beast" else \
        game.tables.threats["kinds"].get(t["kind"], {}).get("band")  # (the barrow's lord, the outlaws' captain: D.3)
    return group, threats.villain_name(game.world, t)


def asking(game, adv: dict, key: str, default: str) -> str:
    """What the hero says of a tale's villain (threats.json kind `ask` / `learn_ask`), with its name."""
    t = threat_of(game, adv) if adv is not None else None
    text = game.tables.threats["kinds"].get((t or {}).get("kind", ""), {}).get(key) or default
    if adv is None:
        return text.replace("{villain}", "it")
    from realmwalker.core import textgen
    from realmwalker.game.story import words as wordsmod

    words = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
    return textgen.fill(text, game.world.rng, {}, dict(words, villain=_villain_name(game, adv)))


def tag_band(creatures: list, adv_id: str, name: str | None, role: str = "villain", step: str | None = None) -> None:
    """The first of a band is the villain (or the role it stands for, named when it is a person), the rest its
    minions: all carry the story tag (with the step a Part D band belongs to)."""
    for i, c in enumerate(creatures):
        c.story = {"adv": adv_id, "role": role if i == 0 else "minion"}
        if step is not None:
            c.story["step"] = step
    if creatures and name:
        creatures[0].name = name
        creatures[0].named = True


def named_encounter(game, adv: dict | None, role: str = "villain") -> list[str]:
    """The story's own foe, met here and now (the beast at the bait, or on the hunters' trail)."""
    from realmwalker.game.encounters import make_encounter

    if adv is None:
        return []
    group, name = villain_group(game, adv)
    if group is None or group not in game.tables.creatures.encounters:
        return []
    rng = game.world.rng.child(f"story-fight/{adv['id']}/{game.world.time}")
    enc = make_encounter(game, group, rng)
    if not enc.creatures:
        return []
    tag_band(enc.creatures, adv["id"], name)
    enc.intro = f"{name}. " + enc.intro
    game.encounter = enc
    game.travel = None
    return []


def boss_for(game, lm) -> dict | None:
    """A story's band bound to this dungeon level (politics["story_sites"]), for dungeon.populate: it takes the
    place of whatever would have been the master here."""
    for rec in game.world.politics.get("story_sites", {}).get(lm.key, []):
        adv = adventures(game.world).get(rec["adv"])
        if adv is None or adv["state"] != "active" or rec.get("what") != "band":
            continue
        if rec.get("role"):  # (a step's own band - the waker, the right hand - while its step is open: D.2)
            st = find_step(game, adv["id"], rec.get("step"))
            if st is not None and st["state"] == "open" and rec.get("group") in game.tables.creatures.encounters:
                return {"group": rec["group"], "name": rec.get("name"), "adv": adv["id"], "role": rec["role"],
                        "step": rec.get("step")}
            continue
        group, name = villain_group(game, adv)
        if group is not None and group in game.tables.creatures.encounters:
            return {"group": group, "name": name, "adv": adv["id"]}
    return None


# ---------------------------------------------------------------------------- the hooks of the game
def daily(game) -> None:
    """Once a game day (from pass_time): see the module's docstring."""
    from realmwalker.game.story import beats, endings, villain
    from realmwalker.game.story.steps import STEPS

    d = beats.director(game.world)
    today = int(game.moment.total_days)
    if int(d.get("day", -1)) == today:
        return
    d["day"] = today
    d["at"] = [int(game.player.x), int(game.player.y)]
    for adv in active(game):  # (a villain taken alive whom no aftermath judged: the lord's justice, D.3)
        if adv.get("boss_taken") and int(adv.get("taken_day", today)) < today:
            for line in endings.finish(game, adv):
                game.say(line, "story")
    from realmwalker.game.story import work

    work.daily(game)  # (commissions from the factions you serve: C.2)
    from realmwalker.game.story import lives

    lives.daily(game)  # (the week's life events in the towns near you: C.4)
    from realmwalker.game.story import goals

    goals.notify(game, "day")  # (clocks, lives and the world's own turns: a situation's goals, C.5)
    from realmwalker.game.story import situations

    situations.daily(game)  # (clocks run out, turns at half time, a new trouble in a town near you: C.6)
    from realmwalker.game.story import favours

    favours.daily(game)  # (letters from your contacts, and their warnings: C.7)
    for adv in active(game):
        villain.quiet(game, adv)
        villain.lapse(game, adv)  # (an invitation never taken up: E.2)
        t = threat_of(game, adv)
        if t is not None and t["state"] == "ended":
            if t.get("outcome") == "slain":
                adv["boss_dead"] = adv.get("boss_dead") or not _villain_alive(game, adv)
            for line in endings.finish(game, adv):
                game.say(line, "story")
            continue
        for st in open_steps(adv):
            STEPS[st["kind"]].repair(game, adv, st)
            if st["kind"] == "prepare" and st["state"] == "open" and _carries(game, st["target"]["means"]):
                step_done(game, adv["id"], st["id"])
                game.say(f"<good>You have what you need against {esc(_villain_name(game, adv))}.</>", "story")
    from realmwalker.game.story import deeds

    deeds.daily(game)  # (chapters set up, a hold's night missed: D.2)
    from realmwalker.game.story import opening

    opening.daily(game)  # (the first day gone by and the opening never came: D.4)
    for item in list(d.get("scheduled", [])):
        if int(item["day"]) <= today and beats.pending(game) is None:
            d["scheduled"].remove(item)
            _play_scheduled(game, item)


def _play_scheduled(game, item: dict) -> None:
    from realmwalker.game.story import beats

    if item.get("hook"):
        from realmwalker.world import threats

        t = threats.records(game.world).get(item["hook"])
        if t is not None and t["state"] in threats.LIVE and t.get("adventure") is None:
            town = item.get("town")
            offer_hook(game, t, game.world.settlements[int(town)] if town is not None else None)
        return
    if item.get("beat") in game.tables.beats:
        beats.offer(game, item["beat"], adv=item.get("adv"), where=_where(game))


def _villain_alive(game, adv: dict) -> bool:
    from realmwalker.world import threats

    t = threat_of(game, adv)
    fig = threats.villain_figure(game.world, t) if t else None
    return fig is not None and fig.alive


def _villain_name(game, adv: dict) -> str:
    from realmwalker.world import threats

    t = threat_of(game, adv)
    return threats.villain_name(game.world, t) if t else "it"


def _carries(game, means: list[str]) -> bool:
    return any(it.def_id in means for c in game.party for it in c.inventory)


def _where(game) -> str:
    if game.local is not None and game.local.kind == "dungeon":
        return "dungeon"
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return "town"
    return "road" if game.world.road[game.player.x, game.player.y] else "wild"


def on_travel(game, minutes: float) -> bool:
    """The Storyteller's travel opportunity (from the overworld walk, before a travel event): a villain's move; True
    when a beat waits now (the random event is skipped). One story beat a day of travel at most."""
    from realmwalker.game.story import beats, villain

    if beats.pending(game) is not None or game.busy:
        return False
    d = beats.director(game.world)
    today = int(game.moment.total_days)
    if _offer_choice(game):
        return True
    from realmwalker.game.story import opening

    if opening.on_travel(game):  # (walking away from the start without going in: D.4)
        return True
    if int(d.get("travel_beat_day", -10)) >= today:
        return False
    from realmwalker.game.story import deeds

    if deeds.on_travel(game):  # (an escort's ambush: D.2)
        return True
    where = _where(game)
    for adv in active(game):
        beat = villain.due_move(game, adv, where)
        if beat is not None:
            beats.offer(game, beat, adv=adv["id"], where=where)
            d["travel_beat_day"] = today
            return True
    return False


def _offer_choice(game) -> bool:
    """A choose step's beat is offered once every step before it in its chapter is done (the Beast's bait or tracks,
    once its weakness is known and the means carried): on the road, at camp, or arriving anywhere. True when it
    waits now."""
    from realmwalker.game.story import beats

    if beats.pending(game) is not None:
        return False
    for adv in active(game):
        ch = chapter(adv)
        if ch is None:
            continue
        for i, st in enumerate(ch["steps"]):
            if st["kind"] != "choose" or st["state"] != "open" or not st.get("beat"):
                continue
            if all(o["state"] != "open" or o["optional"] for o in ch["steps"][:i]) and \
                    beats.eligible(game, st["beat"], {"adv": adv["id"], "where": _where(game)}):
                beats.offer(game, st["beat"], adv=adv["id"], step=st["id"], where=_where(game))
                return True
    return False


def _due_slay(game) -> bool:
    """A named foe still to be fought whose meeting has passed (the hunt lost, the beast not driven off): it comes for
    the hero in the night (law 6: a lost fight moves the story on, it does not stop it). True when it is here."""
    if game.encounter is not None or game.battle is not None:
        return False
    for adv in active(game):
        ch = chapter(adv)
        if ch is None:
            continue
        for i, st in enumerate(ch["steps"]):
            if st["kind"] == "slay" and st["state"] == "open" and \
                    all(o["state"] != "open" or o["optional"] for o in ch["steps"][:i]):
                named_encounter(game, adv, st["target"].get("role", "villain"))
                if game.encounter is not None:
                    game.say(f"<danger>{esc(_villain_name(game, adv))} has come for you in the dark.</>", "story")
                    return True
    return False


def on_arrive(game) -> bool:
    """The party stands on a tile of the world map: a step that is here (go, search, a learning route's check) plays
    its beat, or is done. True when a beat waits."""
    from realmwalker.game.story import beats, places

    if beats.pending(game) is not None:
        return False
    for adv in active(game):
        rec = adv.get("invited")
        if rec and rec.get("state") == "going" and places.here(game, adv["places"]["home"]):
            beats.offer(game, rec.get("beat", "villain_dinner"), adv=adv["id"], where=_where(game))
            return True  # (its invitation taken up: the dinner at its hall, E.2)
    for adv in active(game):
        for st in open_steps(adv):
            t = st["target"]
            if st["kind"] in ("go", "search") and "place" in t and places.here(game, t["place"]):
                if st["kind"] == "search" and any(o["kind"] == "go" and o["state"] == "open" and
                                                  o["target"].get("place") == t["place"] for o in open_steps(adv)):
                    continue  # (first the arrival, then the search)
                if st.get("beat"):
                    beats.offer(game, st["beat"], adv=adv["id"], step=st["id"], where=_where(game))
                    return True
                step_done(game, adv["id"], st["id"])
            if st["kind"] == "learn" and st.get("beat"):
                for r in t["routes"]:
                    if r.get("how") == "check" and places.here(game, r["at"]):
                        beats.offer(game, st["beat"], adv=adv["id"], step=st["id"], where=_where(game))
                        return True
    from realmwalker.game.story import deeds

    if deeds.on_arrive(game):  # (a band waiting here, a hold's night, a rite: D.2)
        return True
    return _offer_choice(game)


def after_beat(game) -> None:
    """A beat was played: whatever else is here may play now (the search after the arrival)."""
    if game.encounter is None and game.battle is None:
        on_arrive(game)


def on_enter_town(game, settlement) -> None:
    """Into a town: a threat at its door that nobody has taken on may be offered by its people (once a week)."""
    from realmwalker.game.story import beats, lives
    from realmwalker.world import threats

    lives.ensure(game, settlement.id)  # (a town peopled before lives were kept)
    from realmwalker.game.story import goals

    goals.notify(game, "town")  # (into its streets: a situation's goals, C.5)
    from realmwalker.game.story import favours

    favours.on_enter_town(game, settlement)  # (a contact's runner at the gate: C.7)
    from realmwalker.game.story import situations

    if beats.pending(game) is not None:
        return
    from realmwalker.game.story import opening

    if opening.on_enter_town(game, settlement):  # (the crisis at the gate, the runner with the summons: D.4)
        return
    if _show_tale(game, settlement):
        return
    from realmwalker.game.story import villain

    if villain.seen_in_town(game, settlement):  # (one who helped you, made an example of: E.2)
        return
    for t in threats.live(game.world):
        if settlement.id in t["stakes"][:6] and t.get("adventure") is None and _can_take(game, t):
            offer = t.get("offer") or {}
            if int(game.moment.total_days) - int(offer.get("since", -99)) >= 7:
                offer_hook(game, t, settlement)
                return
    situations.on_enter_town(game, settlement)  # (a trouble forged here, or met in a scene: C.6)


def _show_tale(game, town) -> bool:
    """Show, don't tell (B.9): the one who saw it tells it again in their street, a crowd round them, and comes to
    you (the witness step's conversation); once the den chapter begins, the hunter who stands with you sends a boy
    running with a note in the hunter's own hand. Each once a tale. True when a scene began."""
    from realmwalker.game.people import npcs_in
    from realmwalker.game.story import cast, stage
    from realmwalker.game.story import words as wordsmod

    if not _on_its_map(game, town):
        return False
    for adv in active(game):
        words = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
        for st in open_steps(adv):
            if st["kind"] == "learn" and "ally" not in adv["keys"]:
                _hunter_situation(game, adv, st, town)
            if st["kind"] != "witness" or st.get("shown"):
                continue
            npc = next((n for n in npcs_in(game.world, town.id) if n.alive and _is(game, st["target"].get("who"), n)),
                       None)
            if npc is not None and "inside" not in st:
                from realmwalker.game.story import situations

                _bind_if_waiting(game, adv, st, npc)
                if situations.for_step(game, adv, st, npc) is not None:
                    st["shown"] = True  # (met in its own scene, by the town's clock)
                    continue
            if npc is not None and stage.start(game, "survivor", cast={"survivor": npc.id}, words=words) is not None:
                st["shown"] = True
                return True
        ch = chapter(adv)
        if ch is None or ch["id"] != "den" or "ally" not in adv["keys"] or adv.get("ally_note") is not None:
            continue
        ally = cast.person(game.world, adv["cast"].get("ally"))
        if ally is None or not getattr(ally, "alive", True) or getattr(ally, "settlement", None) == town.id:
            continue  # (in the hunter's own town, the hunter would simply come)
        words.update(sender=f"{ally.first_name}, {ally.title}", hand_of=getattr(ally, "job", "plain"))
        if stage.start(game, "ally_note", words=words) is not None:
            adv["ally_note"] = int(game.moment.total_days)
            return True
    return False


def on_town_tick(game, lm, town) -> None:
    """A tick of a town's own time while you are on its map (townlife.tick): at midnight, someone a tale would have
    you follow (a learn step's `tail` route: the gang's man in town) slips out, and the scene of following them
    begins - once a night (D.3)."""
    hour = game.moment.hour
    if not (hour >= 23 or hour < 3) or game.busy or not game.in_local:
        return
    from realmwalker.game.people import npcs_in
    from realmwalker.game.story import stage
    from realmwalker.game.story import words as wordsmod

    today = int(game.moment.total_days) + (1 if hour >= 23 else 0)  # (one night is one try, either side of midnight)
    for adv in active(game):
        for st in open_steps(adv):
            if st["kind"] != "learn" or int(st.get("tailed", -1)) == today:
                continue
            route = next((r for r in st["target"]["routes"] if r.get("how") == "tail"), None)
            if route is None:
                continue
            npc = next((n for n in npcs_in(game.world, town.id) if n.alive and _is(game, route.get("who"), n)), None)
            if npc is None:
                continue
            if route.get("role"):
                _bind_role(game, adv, route["role"], npc)
            words = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
            then = {"adv": adv["id"], "step": st["id"], "finishes": "inside_followed"}
            if stage.start(game, "midnight_tail", cast={"suspect": npc.id}, words=words, then=then,
                           force=True) is not None:
                st["tailed"] = today
                return


def learned_by_following(game, adv: dict, sid: str) -> list[str]:
    """Followed to the end: what was seen is the learn step's truth, and the step is done."""
    st = find_step(game, adv["id"], sid)
    if st is None or st["state"] != "open":
        return []
    told = truth_told(game, adv, st)
    journal(adv, told, int(game.moment.total_days))
    step_done(game, adv["id"], sid)
    return [f"<good>{esc(told)}</>"]


def _hunter_situation(game, adv: dict, st: dict, town) -> None:
    """The hunter who knows what it fears is in this town: their part may become a situation (C.10)."""
    from realmwalker.game.people import npcs_in
    from realmwalker.game.story import situations

    if "inside" in st:
        return
    route = next((r for r in st["target"].get("routes", []) if r.get("how") == "talk" and r.get("role") == "ally"),
                 None)
    if route is None:
        return
    npc = next((n for n in npcs_in(game.world, town.id) if n.alive and _is(game, route.get("who"), n)), None)
    if npc is None:
        return
    _bind_role(game, adv, "ally", npc)
    situations.for_step(game, adv, st, npc, route="ally")


def on_night(game, where: str) -> bool:
    """A night at camp or at the inn: the villain may answer you (a carcass at the camp's edge, a test by night), or a
    choice that is due is put to you."""
    from realmwalker.game.story import beats, villain

    if beats.pending(game) is not None:
        return False
    if _offer_choice(game) or (where == "camp" and _due_slay(game)):
        return True
    from realmwalker.game.story import deeds

    if deeds.on_night(game, where):  # (the night a place must be held: D.2)
        return True
    for adv in active(game):
        beat = villain.due_move(game, adv, where)
        if beat is not None:
            spec = game.tables.beats.get(beat, {})
            if where == "inn" and spec.get("stage") and _stage_at_inn(game, adv, beat, spec["stage"]):
                return True  # (played on the town's map: the figure comes to your room, E.2)
            beats.offer(game, beat, adv=adv["id"], where=where)
            left = spec.get("leaves")
            if left and where == "camp":  # (and there it lies in the camp's picture until you move on)
                p = game.player
                beats.director(game.world)["left"] = {"what": left, "x": p.x, "y": p.y, "adv": adv["id"],
                                                      "day": int(game.moment.total_days)}
                if left == "dead":
                    game.cue("dead")  # (D.5)
            return True
    return False


def _stage_at_inn(game, adv: dict, beat: str, scene: str) -> bool:
    """The villain's visit to your room at the inn, staged on the town's map (E.2): the lamps gutter, a figure is
    there by your bed, it speaks (the beat), and it is gone. False when no scene can play here."""
    from realmwalker.game.story import stage, words as wordsmod

    from realmwalker.world import threats

    words = {k: str(v) for k, v in wordsmod.for_adventure(game, adv).items() if k in ("villain", "villain_short",
                                                                                      "hero", "home")}
    t = threats.records(game.world).get(adv["threat"])
    if t is not None:
        words["villain_creature"] = t["villain"]["creature"]
    return stage.start(game, scene, words=words, then={"beat": beat, "adv": adv["id"]}, force=True) is not None


LEFT = ("carcass", "dead", "visitor")  # what a beat may leave at your camp (beats.json `leaves`; drawn by
#   ui/gfx/scenes.camp: the beast's carcass, the Risen's dead standing at the edge of the light, the villain itself
#   beyond a fire burned low: E.2)


def left_at_camp(game) -> str | None:
    """What the villain left at the camp you are in (a carcass), for the camp's picture; None once you move on."""
    rec = left_record(game)
    return rec["what"] if rec else None


def left_record(game) -> dict | None:
    """The record of what was left at this camp ({what, adv, x, y, day}); a visitor only while its beat waits."""
    from realmwalker.game.story import beats

    rec = beats.director(game.world).get("left") if getattr(game, "camp", None) is not None else None
    if not rec or (rec["x"], rec["y"]) != (game.player.x, game.player.y):
        return None
    if rec["what"] == "visitor" and (beats.pending(game) or {}).get("adv") != rec.get("adv"):
        return None  # (gone when the fire flares again)
    return rec if int(game.moment.total_days) - int(rec["day"]) <= 1 else None


def on_descend(game, lm) -> None:
    """Down into a level: a band bound here already in place is tagged (a level filled before the tale began), and
    the finale's level warns before it (law 5: never a surprise)."""
    from realmwalker.game.story import deeds

    deeds.on_descend(game, lm)  # (a step's band on a level filled before: D.2)
    for adv in active(game):
        for st in [s for ch in adv["chapters"] for s in ch["steps"] if s["state"] == "open"]:  # (early too)
            if st["kind"] != "finale" or st["target"].get("level") != lm.key:
                continue
            group, name = villain_group(game, adv)
            tagged = any(getattr(c, "story", None) and c.story.get("adv") == adv["id"]
                         for a in lm.actors for c in a.creatures)
            if not tagged:
                for a in lm.actors:
                    if a.creatures and a.creatures[0].named and a.creatures[0].name == name:
                        tag_band(a.creatures, adv["id"], name)
            words = game.tables.adventures["blueprints"][adv["blueprint"]]["finale"].get("words", {})
            if words.get("warning"):
                rng = game.world.rng.child(f"warning/{adv['id']}")
                game.say(f"<warn>{esc(rng.choice(words['warning']))}</>", "story")


def finish_off(game, result) -> list[str]:
    """A story's villain that is not a person (a beast) taken helpless - asleep, held, senseless - is killed where it
    lies: no hunter leaves it to wake, and nobody pays for a captive beast. It becomes one of the dead (before the
    aftermath asks what to do with captives, and before the listeners hear of the fight)."""
    out = []
    for c in list(result.captives):
        tag = getattr(c, "story", None)
        adv = adventures(game.world).get((tag or {}).get("adv"))
        if not tag or tag.get("role") != "villain" or adv is None or adv["state"] != "active":
            continue
        from realmwalker.world import threats

        t = threat_of(game, adv)
        fig = threats.villain_figure(game.world, t) if t is not None else None
        if fig is None or fig.kind != "beast":
            continue  # (a person taken is the aftermath's to judge)
        result.captives.remove(c)
        c.hp = 0
        c.alive = False
        result.dead.append(c)
        out.append(f"<warn>{esc(c.name)} does not wake. You make sure of it.</>")
    return out


def on_battle(game, result, actor=None) -> None:
    """After a fight: a story's foe dead, taken or fled (by its story tag, never by its name)."""
    from realmwalker.game.story import deeds, endings, villain

    deeds.on_battle(game, result)  # (a step's band, a hold's wave: D.2)
    seen, harm = [], {}
    for c, how in [(c, "dead") for c in result.dead] + [(c, "taken") for c in getattr(result, "captives", [])] + \
            [(c, "fled") for c in getattr(result, "fled", [])]:
        tag = getattr(c, "story", None)
        if not tag:
            continue
        adv = adventures(game.world).get(tag.get("adv"))
        if adv is None or adv["state"] != "active":
            continue
        if tag.get("role") == "villain":
            seen.append((adv, how))
        elif how == "dead":  # (its servants killed, once a fight; each lieutenant slain, and its wrath: E.1)
            h = harm.setdefault(adv["id"], {"servants": 0, "lieutenants": 0})
            h["servants" if tag.get("role") == "minion" else "lieutenants"] += 1
    for aid, h in harm.items():
        villain.on_fight(game, adventures(game.world)[aid], servants=min(1, h["servants"]),
                         lieutenants=h["lieutenants"])
    battle = getattr(game, "battle", None)
    if battle is not None and int(getattr(battle, "great_magic", 0) or 0):
        villain.on_magic(game, int(battle.great_magic))  # (great magic cast in its reach)
    for adv, how in seen:
        if how == "dead" or (how == "taken" and _villain_is_person(game, adv)):
            adv["boss_dead" if how == "dead" else "boss_taken"] = True  # (a lord of outlaws taken alive: D.3)
            for st in open_steps(adv):
                if st["kind"] in ("slay", "finale"):
                    st["state"] = "done"
            if how == "taken":
                adv["taken_day"] = int(game.moment.total_days)
                continue  # (the aftermath judges the captain first: on_fate ends the tale with the fate chosen)
            for line in endings.finish(game, adv):
                game.say(line, "story")
        else:
            adv["boss_fled"] = how == "fled"
            for st in open_steps(adv):
                if st["kind"] == "slay" and (st["target"].get("fled_ok") or how == "taken"):
                    step_done(game, adv["id"], st["id"])


def _villain_is_person(game, adv: dict) -> bool:
    from realmwalker.world import threats

    fig = threats.villain_figure(game.world, threat_of(game, adv))
    return fig is not None and fig.kind == "person" and fig.alive


def on_fate(game, creature, fate: str) -> str | None:
    """A story foe taken alive is judged in the aftermath (fight.decide_captive): what they tell, or None. A tale's
    villain taken alive ends the tale by the fate chosen: spared or robbed and let go (the codeword villain_spared),
    else given to the lord's justice or put to death (D.3)."""
    from realmwalker.game.story import beats, deeds, endings

    tag = getattr(creature, "story", None) or {}
    adv = adventures(game.world).get(tag.get("adv"))
    if tag.get("role") == "villain" and adv is not None and adv["state"] == "active" and adv.get("boss_taken"):
        adv["villain_fate"] = fate
        if fate == "execute":  # (put to death where they knelt: the gang broken, as if they fell fighting)
            adv["boss_taken"], adv["boss_dead"] = False, True
        if fate in ("spare", "rob"):
            beats.OPS["flag"](game, {"adv": adv["id"]}, "villain_spared")
        for line in endings.finish(game, adv):
            game.say(line, "story")
        return None
    return deeds.on_fate(game, creature, fate)


def on_quest_end(game, q: dict, ok: bool) -> None:
    """A step's quest reports back (rescue, escort and deliver steps come with Part D)."""
    aid, sid = q.get("adventure"), q.get("step")
    if not aid:
        return
    st = find_step(game, aid, sid)
    if st is not None and st["state"] == "open":
        if ok:
            step_done(game, aid, sid)
        else:
            st["state"] = "failed"
            if st.get("kidnap"):  # (too late: the one it took dies in its hall, E.2)
                from realmwalker.game.story import villain

                villain.lost(game, adventures(game.world)[aid], st)


def on_job_taken(game, q: dict) -> None:
    """A hunting job on a beast that is a threat's villain opens that threat's tale (its hook beat now, or as soon as
    no other beat waits): until Part C retires the job offers, the board's beasts lead into their stories."""
    from realmwalker.game.story import beats
    from realmwalker.world import threats

    if q.get("template") not in ("hunt_beast", "clear_lair") or q.get("adventure"):
        return
    fig = q.get("target", {}).get("beast")
    if fig is None:
        return
    for t in threats.records(game.world).values():
        if t["state"] in threats.LIVE and t.get("adventure") is None and t["villain"].get("figure") == fig:
            if beats.pending(game) is None:
                offer_hook(game, t, game.world.settlements[int(q["town"])])
            else:
                beats.director(game.world).setdefault("scheduled", []).append(
                    {"day": int(game.moment.total_days), "hook": t["id"], "town": int(q["town"])})
            return


def divine_questions(game) -> list[dict]:
    """What the powers can be asked of a tale (a learn step with a divination route, in the open chapter):
    [{"adv", "step", "ask"}] for divining.questions and the Divination spell."""
    from realmwalker.game.story import words as wordsmod

    out = []
    for adv in active(game):
        for st in open_steps(adv):
            if st["kind"] == "learn" and any(r.get("how") == "divine" for r in st["target"].get("routes", [])):
                name = wordsmod.for_adventure(game, adv).get("villain_short", "it")
                ask = f"What will kill {name}?" if st["target"].get("answer") is None else \
                    asking(game, adv, "learn_ask", "What is {villain}?")
                out.append({"adv": adv["id"], "step": st["id"], "ask": ask})
    return out


def divined(game, aid: str, sid: str) -> list[str]:
    """The powers answered a tale's question: its truth in words (what it fears), a clue, and the step is done."""
    from realmwalker.game.story import beats

    adv = adventures(game.world).get(aid)
    st = find_step(game, aid, sid)
    if adv is None or st is None or st["state"] != "open":
        return []
    told = truth_told(game, adv, st)
    beats.OPS["clue"](game, {"adv": aid}, st["target"].get("truth", "villain"))
    journal(adv, f"The powers answered me: {told}", int(game.moment.total_days))
    step_done(game, aid, sid)
    return [told]


def truth_told(game, adv: dict, st: dict | None) -> str:
    """What a learn step's truth is, told (by someone who knows, the powers, a check at the place): its `answer`
    (a words table of adventures.json, D.3: who the risen was, who sells the caravans' days), else what it fears."""
    from realmwalker.core import textgen
    from realmwalker.game.story import words as wordsmod

    words = wordsmod.for_adventure(game, adv)
    key = (st or {}).get("target", {}).get("answer")
    tables = game.tables.adventures.get("words", {})
    if key and tables.get(key):
        rng = game.world.rng.child(f"truth/{adv['id']}/{(st or {}).get('id', '')}")
        return textgen.fill(rng.choice(tables[key]), rng, tables, words)
    return words.get("weakness_lore", "Nobody knows for sure.")


def on_read(game, item) -> None:
    """A document read: a read step whose tag it carries is done."""
    tags = set(getattr(item, "tags", []) or [])
    for adv in active(game):
        for st in open_steps(adv):
            if st["kind"] == "read" and st["target"].get("tag") in tags:
                step_done(game, adv["id"], st["id"])


# ---------------------------------------------------------------------------- hooks: offering a tale
def _can_take(game, t: dict) -> bool:
    from realmwalker.game.story import forge

    cap = int(game.tables.adventures.get("max_active", 3))
    if float(t.get("bargained", -1)) > float(game.moment.total_days):
        return False  # (you took its offer, and it keeps its side of it for now: E.2)
    return len(active(game)) < cap and bool(forge.fitting(game, t))


def hook_words(game, t: dict, town=None) -> dict:
    from realmwalker.game.quests import direction
    from realmwalker.world import threats

    w = game.world
    town = town or (w.settlements[t["stakes"][0]] if t["stakes"] else None)
    where = direction(town, w.sites[t["home"]["site"]]) if town is not None and "site" in t["home"] else "not far"
    return {"villain": threats.villain_name(w, t), "home": threats.home_name(w, t),
            "town": town.name if town is not None else "the villages", "where": where}


def hook_line(game, t: dict, town=None) -> str:
    from realmwalker.core import textgen

    kind = game.tables.threats["kinds"][t["kind"]]
    rng = game.world.rng.child(f"hook/{t['id']}/{int(game.moment.total_days) // 7}")
    return textgen.fill(rng.choice(kind["hooks"]), rng, {}, hook_words(game, t, town))


def offer_hook(game, t: dict, town=None) -> None:
    """A threat's people ask the hero to take it on (the hook beat: take it, or not now)."""
    from realmwalker.game.story import beats

    if not _can_take(game, t):
        return
    t["offer"] = {"by": town.id if town is not None else (t["stakes"][0] if t["stakes"] else -1),
                  "where": _where(game), "since": int(game.moment.total_days)}
    words = hook_words(game, t, town)
    words["hook"] = hook_line(game, t, town)
    words["threat"] = t["id"]
    then = {"beat": "story_hook", "where": _where(game), "words": words}
    if town is not None and _on_its_map(game, town):  # (show, don't tell: someone of the town comes to you with it)
        from realmwalker.game.story import stage

        scene = ("runner", "plea")[int(game.moment.total_days + town.id) % 2]
        if stage.start(game, scene, words={"town": words.get("town", town.name)}, then=then) is not None:
            return
    beats.offer(game, "story_hook", where=then["where"], words=words)


def _on_its_map(game, town) -> bool:
    lm = game.local
    return bool(game.in_local and lm is not None and lm.kind == "settlement"
                and game.world.settlement_at(game.player.x, game.player.y) is town)


def take_hook(game, tid: str) -> list[str]:
    """The hero takes the tale on: the adventure is forged now, and begins."""
    from realmwalker.game.story import forge
    from realmwalker.world import threats

    t = threats.records(game.world).get(tid)
    if t is None or t["state"] not in threats.LIVE or t.get("adventure") is not None or not _can_take(game, t):
        return ["<dim>It is too late for that now.</>"]
    adv = forge.make(game, t)
    if adv is None:
        return ["<dim>Nobody can tell you where to begin. Perhaps another time.</>"]
    from realmwalker.game.story import beats, deeds

    first = beats.director(game.world).get("opening") or {}
    if first.get("threat") == tid and first.get("state") == "played":
        adv["opening"] = first["kind"]  # (the tale a life began with: D.4)
    begin_card(game, adv)

    deeds.setup(game, adv)  # (the first chapter's rescues, fetches, bands and nights: D.2)
    return [f"<title>{esc(adv['title'])}</> <dim>(the journal, j: Adventures)</>"]


# ---------------------------------------------------------------------------- talk
def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice
    from realmwalker.world import threats

    game, npc = conv.game, conv.npc
    out = []
    for adv in active(game):
        name = _villain_name(game, adv)
        for st in open_steps(adv):
            t = st["target"]
            sit_made = st.get("inside") is not None  # (the step became a situation: its own talk, C.10)
            if st["kind"] == "witness" and not sit_made and _is(game, t.get("who"), npc):
                out.append(Choice("story_witness", f"They say you saw {name}. Tell me.",
                                  data={"adv": adv["id"], "step": st["id"]}))
            if st["kind"] == "learn" and any(r.get("how") == "talk" and _is(game, r.get("who"), npc)
                                             and not (sit_made and r.get("role") == "ally") for r in t["routes"]):
                out.append(Choice("story_learn", asking(game, adv, "learn_ask", "What does {villain} fear? What will "
                                                        "kill it?"), data={"adv": adv["id"], "step": st["id"]}))
        if _is(game, adv["cast"].get("patron"), npc):
            out.append(Choice("story_patron", f"About {name}...", data={"adv": adv["id"]}))
    from realmwalker.game.story import deeds, situations

    out += deeds.talk_choices(conv)  # (recruit, rally, confront, an escort's setting out: D.2)
    out += situations.talk_choices(conv)
    from realmwalker.game.story import favours

    out += favours.call_choices(conv)  # (a favour called in, a contact's news: C.7)
    for t in threats.live(game.world):
        if t.get("adventure") is None and npc.notable and npc.settlement in t["stakes"][:6] and _can_take(game, t):
            ask = game.tables.threats["kinds"].get(t["kind"], {}).get("ask", "I hear something is killing your people.")
            out.append(Choice("story_hook", ask, data={"threat": t["id"]}))
            break
    return out


def _is(game, entry, npc) -> bool:
    """Whether a role or route's person is this townsperson (one still waiting for their town, if they fit)."""
    from realmwalker.game.story import cast

    if not entry:
        return False
    if "npc" in entry:
        return int(entry["npc"]) == npc.id
    if "job" in entry and int(entry.get("settlement", -1)) == npc.settlement:
        return npc.job in entry.get("jobs", [entry["job"]]) and not cast._taken(game.world, npc)
    return False


def talk_choose(conv, choice) -> None:
    from realmwalker.core import textgen
    from realmwalker.game.story import words as wordsmod

    game = conv.game
    cid, data = choice.id, choice.data
    if cid.startswith("sit_"):
        from realmwalker.game.story import situations

        situations.talk_choose(conv, choice)
        return
    if cid in ("fav_call", "fav_hide", "contact_ask"):
        from realmwalker.game.story import favours

        favours.choose(conv, choice)
        return
    from realmwalker.game.story import deeds

    if cid in deeds.TALK_CHOICES:
        deeds.talk_choose(conv, choice)
        return
    if cid == "story_hook":
        from realmwalker.world import threats

        t = threats.records(game.world).get(data["threat"])
        if t is not None:
            conv.note(esc(hook_line(game, t)))
            offer_hook(game, t, game.world.settlements[conv.npc.settlement])
            conv.ended = True
        return
    adv = adventures(game.world).get(data.get("adv"))
    if adv is None:
        return
    words = wordsmod.for_adventure(game, adv)
    tables = game.tables.adventures.get("words", {})
    rng = game.world.rng.child(f"talk/{adv['id']}/{data.get('step', '')}/{conv.npc.id}")
    if cid == "story_witness":
        st = find_step(game, adv["id"], data["step"])
        for line in step_told(game, adv, st, conv.npc.id) if st is not None else []:
            conv.note(line)
        _bind_if_waiting(game, adv, st, conv.npc)
        step_done(game, adv["id"], data["step"])
    elif cid == "story_learn":
        st = find_step(game, adv["id"], data["step"])
        conv.note(esc(truth_told(game, adv, st)))
        route = next((r for r in (st or {}).get("target", {}).get("routes", []) if r.get("how") == "talk"
                      and _is(game, r.get("who"), conv.npc)), None)
        if route is not None and route.get("role"):
            _bind_role(game, adv, route["role"], conv.npc)
            if route["role"] == "ally":
                from realmwalker.game.story import beats

                conv.note(esc(f"\"And I'll come with you,\" {conv.npc.first_name} says. \"When you go up there.\""))
                for line in beats.OPS["key"](game, {"adv": adv["id"]}, "ally"):
                    conv.note(line)
        step_done(game, adv["id"], data["step"])
    elif cid == "story_patron":
        ch = chapter(adv)
        lines = tables.get("patron_brief", ["{goal}"])
        conv.note(esc(textgen.fill(rng.choice(lines), rng, tables, dict(words, goal=ch["goal"] if ch else ""))))


def step_told(game, adv: dict, st: dict, who: int | None = None) -> list[str]:
    """What the person of a witness or learn step tells when they tell it (in talk, or as their situation ends)."""
    from realmwalker.core import textgen
    from realmwalker.game.story import words as wordsmod

    words = wordsmod.for_adventure(game, adv)
    if st["kind"] == "learn":
        return [esc(truth_told(game, adv, st))]
    tables = game.tables.adventures.get("words", {})
    rng = game.world.rng.child(f"talk/{adv['id']}/{st['id']}/{who if who is not None else 'sit'}")
    lines = tables.get(st.get("words") or "witness_tale") or ["It was dark. I ran."]
    return [esc(textgen.fill(rng.choice(lines), rng, tables, words))]


def _bind_role(game, adv: dict, role: str, npc) -> None:
    """A role still waiting for its town is this townsperson (met in their own town before it was ever filled)."""
    from realmwalker.game.story import cast

    entry = adv["cast"].get(role)
    if entry and cast.pending(entry):
        adv["cast"][role] = cast._take(npc, adv, role, entry)
        cast._rebind_steps(adv, role, adv["cast"][role])


def _bind_if_waiting(game, adv, st, npc) -> None:
    from realmwalker.game.story import cast

    if st is None:
        return
    role = st["target"].get("role")
    entry = adv["cast"].get(role) if role else None
    if entry and cast.pending(entry):
        adv["cast"][role] = cast._take(npc, adv, role, entry)
        st["target"]["who"] = dict(adv["cast"][role])


# ---------------------------------------------------------------------------- the map and the board
def map_marks(game) -> list[tuple[int, int]]:
    """Where the hero's tales want them now: the places of the open steps."""
    from realmwalker.game.story import places

    out = []
    for adv in active(game):
        for st in open_steps(adv):
            for p in (st["target"].get("place"), st["target"].get("to")):  # (an escort's end too: D.2)
                if p and places.exists(game.world, p):
                    out.append(places.xy(game.world, p))
            for r in st["target"].get("routes", []):
                if r.get("at"):
                    out.append(places.xy(game.world, r["at"]))
    now = game.world.time / 1440.0
    for t in game.world.politics.get("director", {}).get("tracks", []):  # (tracks followed off a map: B.6)
        if now - float(t["day"]) <= 1.0:
            out.append((int(t["x"]), int(t["y"])))
    return out


def map_signs(game) -> list[tuple[int, int, str]]:
    """The story's pictures on the world map: a seal ("story") where a tale wants the hero, and claw marks ("sign")
    at the den of a threat whose signs they have heard and whose tale they have not taken."""
    from realmwalker.world import threats

    out = [(x, y, "story") for x, y in dict.fromkeys(map_marks(game))]
    heard = game.renown.heard
    for t in threats.live(game.world):
        if t.get("adventure") is None and any(n in heard for n in t.get("signs", [])):
            x, y = threats.home_xy(game.world, t)
            if game.player.explored[x, y]:  # (the signs do not give away a den you have never seen)
                out.append((x, y, "sign"))
    return out


def notices(game, settlement) -> list[str]:
    """A notice board's hooks: every stirring threat within a week's walk that nobody has taken on."""
    from realmwalker.world import threats

    reach = int(game.tables.threats.get("start", {}).get("tiles", 56))
    return [hook_line(game, t, settlement) for t in threats.live(game.world) if t.get("adventure") is None
            and threats.distance(game.world, t, settlement.x, settlement.y) <= reach and _can_take(game, t)]


# ---------------------------------------------------------------------------- lives
def begin(game) -> None:
    """A new life: the director starts afresh, and a fitting tale is offered near where the hero sets out."""
    from realmwalker.game.story import beats
    from realmwalker.world import news, threats

    d = beats.director(game.world)
    d["pending"] = None
    d["card"] = None
    d["scheduled"] = []
    d["day"] = -1
    d["opening"] = None
    w = game.world
    x, y = game.player.x, game.player.y
    d["at"] = [int(x), int(y)]
    reach = int(game.tables.threats.get("start", {}).get("tiles", 56))
    near = [t for t in threats.records(w).values() if t["state"] != "ended" and t.get("adventure") is None
            and threats.distance(w, t, x, y) <= reach * 2 and _can_take(game, t)]
    if not near:
        return
    if any(threats.distance(w, t, x, y) <= reach for t in near):  # (twice as far only when nothing is near: D.4)
        near = [t for t in near if threats.distance(w, t, x, y) <= reach]
    near.sort(key=lambda t: (t["state"] not in threats.LIVE, t["tier"], threats.distance(w, t, x, y), t["id"]))
    t = near[0]
    if t["state"] == "dormant":
        threats.stir(w, game.tables, t, w.rng.child(f"begin/{t['id']}"), day=news.now_days(w))
    from realmwalker.game.story import opening

    opening.begin(game, t)  # (the first hour: a crisis, a summons or the gang's captive, D.4)


def on_death(game) -> None:
    """The hero is dead: their tales are orphaned (the threats go on, and remember), and no beat waits."""
    from realmwalker.game.story import beats

    for adv in active(game):
        adv["state"] = "orphaned"
        t = threat_of(game, adv)
        if t is not None and t.get("adventure") == adv["id"]:
            t["adventure"] = None
    d = beats.director(game.world)
    d["pending"] = None
    d["card"] = None
    d["scheduled"] = []
    d["opening"] = None
    from realmwalker.game.story import situations

    situations.on_death(game)  # (live troubles lose their work and wait for the next hero: C.6)


# ---------------------------------------------------------------------------- the finale's card
def finale_band(game, actor) -> dict | None:
    """The adventure whose finale this band on a close-up map is (its villain, with the finale step open), or None."""
    tag = getattr(actor.creatures[0], "story", None) if actor is not None and actor.creatures else None
    if not tag or tag.get("role") != "villain":
        return None
    adv = adventures(game.world).get(tag.get("adv"))
    if adv is None or adv["state"] != "active":
        return None
    if any(st["kind"] == "finale" for st in open_steps(adv)):
        return adv
    lm = game.local
    return adv if lm is not None and at_its_den(adv, lm.key) else None


def at_its_den(adv: dict, key: str | None) -> bool:
    """This close-up map is the level the tale's finale is bound to (met there early, it is the finale still)."""
    return key is not None and any(st["kind"] == "finale" and st["state"] == "open" and
                                   st["target"].get("level") == key for ch in adv["chapters"] for st in ch["steps"])


def hold_for_finale(game, actor) -> bool:
    """Walking into the boss's band (or it reaching you) shows its card first: Fight, or Not yet (law 5)."""
    adv = finale_band(game, actor)
    if adv is None:
        return False
    game.finale = {"adv": adv["id"], "actor": int(actor.id)}
    return True


def fight_finale(game) -> None:
    """The card said Fight: the battle with the boss's band begins."""
    from realmwalker.game.fight import start_battle
    from realmwalker.rules.combat import FOE

    rec, game.finale = game.finale, None
    lm = game.local
    actor = next((a for a in (lm.actors if lm is not None else []) if a.id == (rec or {}).get("actor")), None)
    if actor is None:
        return
    name = actor.creatures[0].name if actor.creatures else "it"
    start_battle(game, actor.creatures, f"{name}!", surprised=None if actor.alert else FOE, actor=actor,
                 title=name)


def finale_card(game) -> dict:
    """What the boss's card shows: its name, its first words, and what you know (keys found, unknowns)."""
    from realmwalker.game.story import words as wordsmod

    rec = game.finale or {}
    adv = adventures(game.world).get(rec.get("adv"))
    if adv is None:
        return {}
    bp = game.tables.adventures["blueprints"][adv["blueprint"]]
    temper = game.tables.villains.get("tempers", {}).get((threat_of(game, adv) or {}).get("villain", {})
                                                          .get("temper") or "", {})
    rng = game.world.rng.child(f"first/{adv['id']}")
    first = rng.choice(temper.get("first_words") or bp["finale"].get("words", {}).get("first", ["..."]))
    from realmwalker.core import textgen

    first = textgen.fill(first, rng, game.tables.adventures.get("words", {}),
                         {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)})
    known = []
    for k in bp["finale"].get("keys", {}):
        known.append((wordsmod.key_text(game, adv, k) if k in adv["keys"] else "?", k in adv["keys"]))
    level = int(adv["target_level"])
    return {"name": _villain_name(game, adv), "title": adv["title"], "first": first, "known": known,
            "warning": level > game.leader.level, "level": level}
