"""Spells outside battle, part E.4 (Expansion 3): minds and the law (Friends, Enthrall, Zone of Truth, Geas, Modify
Memory, Glibness, Antipathy/Sympathy, Awaken), disguise and illusion (Disguise Self, Seeming, Minor Illusion, Silent
Image, Major Image, Programmed Illusion, Project Image, Mislead, Hallucinatory Terrain, Mirage Arcane, Illusory
Script, Magic Mouth, Nystul's Magic Aura, Nondetection, Sequester) and the small arts (Druidcraft, Elementalism,
Prestidigitation, Thaumaturgy). Each is cast where it is used: in a town among its people, at a camp, on the road,
in a real fight."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import camp, dialogue, encounters, fight, glamour, law, magic, revival, spellwork
from realmwalker.game.encounters import PendingEncounter
from realmwalker.game.state import new_game
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

E4 = sorted(("friends enthrall zone_of_truth geas modify_memory glibness antipathy_sympathy awaken disguise_self "
             "seeming minor_illusion silent_image major_image programmed_illusion project_image mislead "
             "hallucinatory_terrain mirage_arcane illusory_script magic_mouth nystuls_magic_aura nondetection sequester "
             "druidcraft elementalism prestidigitation thaumaturgy").split())
LASTING = ("glibness", "disguise_self", "seeming", "mislead", "nondetection")  # (cast in a fight too, or lasting)
COMPONENTS = ("jade_dust", "lead_ink", "diamond_dust_pinch", "gem_1000", "gem_5000")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    """Every caster in these tests has the spells of E.4 ready (the bard, the druid and the warlock, whose spells many
    of these are, are not in the game yet)."""
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + E4)) if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


class _D20:
    def __init__(self, n):
        self.natural = n


def fixed_d20(monkeypatch, n):
    monkeypatch.setattr(glamour.dice, "d20", lambda *a, **k: _D20(n))


def hero(tables, cls="wizard", xp=355000, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    add_item(c, tables.items, "component_pouch")
    for cid in COMPONENTS:
        add_item(c, tables.items, cid, 3)
    return c


def game_with(world, tables, *party):
    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        game.party.append(c)
    game.survival = False
    from realmwalker.game import pack

    pack.sync(game)
    return game


def cast(game, c, sid, target=None, slot=None):
    why = magic.road_problem(game, c, sid, target)
    assert why is None, f"{sid}: {why}"
    return magic.cast_on_road(game, c, sid, target, slot)


def subject(game, c, sid, kind=None, name=None):
    subs = magic.road_targets(game, c, sid)
    for s in subs:
        if (kind is None or s.kind == kind) and (name is None or name in s.name):
            return s
    raise AssertionError(f"{sid}: no subject {kind} {name} in {[s.name for s in subs]}")


def text(lines) -> str:
    return " ".join(lines)


def in_town(game):
    town = game.world.settlements[0]
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    return town


def someone_near(game, town, job=None, dx=1):
    npc = next(n for n in game.world.npcs.values() if n.settlement == town.id and n.alive
               and (job is None or n.job == job))
    npc.present = True
    npc.x, npc.y = game.player.lx + dx, game.player.ly
    return npc


def in_the_wild(game):
    game.leave_local() if game.local is not None else None
    for x in range(game.world.width):
        for y in range(game.world.height):
            if game.world.settlement_at(x, y) is None and game.world.danger[x, y] >= 1 \
                    and game.tables.biomes.family(game.land_key(x, y)) in ("forest", "plains", "hills"):
                game.player.x, game.player.y = x, y
                return
    raise AssertionError("no wild land")


# ---------------------------------------------------------------------------- the data
IN_FIGHTS_TOO = ("minor_illusion", "silent_image", "major_image")  # (images on the battle mat: Expansion 5 Part A)


def test_the_twenty_seven_spells_are_in_and_the_start_up_check_knows_them(tables):
    assert all(sid in tables.spells for sid in E4)
    assert not [p for p in check.problems(tables) if any(sid in p for sid in E4)]
    for sid in E4:
        if sid not in LASTING and sid not in IN_FIGHTS_TOO:
            assert sp.out_of_battle(tables.spells[sid]), f"{sid} is never cast in a fight"
        assert sp.road_use(tables, sid) is not None, f"{sid} has a use outside a fight"
    for cid in COMPONENTS:
        assert cid in tables.items and tables.items.get(cid).get("how") or cid.startswith("gem_")


# ---------------------------------------------------------------------------- minds and the law
def test_friends_warms_someone_for_the_talk_and_they_know_it_after(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    npc = someone_near(game, town)
    npc.disposition = -30
    fixed_d20(monkeypatch, 1)
    said = text(cast(game, wiz, "friends", subject(game, wiz, "friends", "person")))
    assert "Friendly" in said
    talk = dialogue.Conversation(game, npc)
    assert talk.attitude() == "friendly"
    before = npc.disposition
    game.world.time += glamour.TALK_MINUTES + 5
    assert talk.attitude() != "friendly"
    assert npc.disposition == before + glamour.FRIENDS_SOUR, "when it ends they know what was done"
    assert magic.road_problem(game, wiz, "friends", subject(game, wiz, "friends", "person")) is None
    assert "will not again" in text(cast(game, wiz, "friends", subject(game, wiz, "friends", "person")))


def test_enthrall_leaves_no_witnesses_to_a_theft(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    npc = someone_near(game, town, dx=2)
    monkeypatch.setattr(law, "_unseen", lambda game_, n: False)
    monkeypatch.setattr("realmwalker.game.vision.can_see", lambda *a, **k: True)
    assert npc in law.witnesses_here(game)
    fixed_d20(monkeypatch, 1)
    said = text(cast(game, wiz, "enthrall"))
    assert "hang on every word" in said
    assert npc not in law.witnesses_here(game)
    assert glamour.watcher_minus(game, npc) == 10


def test_zone_of_truth_shows_a_work_for_what_it_is(world, tables, monkeypatch):
    from realmwalker.game import quests

    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    town = in_town(game)
    npc = someone_near(game, town)
    monkeypatch.setattr(quests, "LIVE", ("accepted", "return", "active"))
    game.quests[:] = [{"id": 999, "template": "bounty", "state": "accepted", "giver": npc.id, "town": town.id,
                       "faction": -1, "reward": 500, "days": 9, "offered_day": 0, "hidden": "deserters",
                       "revealed": False, "done": False, "target": {"site": 1, "gang": -1}, "words": {}, "journal": [],
                       "text_key": ""}]
    monkeypatch.setattr(quests, "reveal", lambda game_, q: q.__setitem__("revealed", True))
    fixed_d20(monkeypatch, 1)
    said = text(cast(game, cleric, "zone_of_truth", subject(game, cleric, "zone_of_truth", "person")))
    assert game.quests[0]["revealed"] and "not what they told" in said


def test_geas_binds_a_guard_who_saw_a_crime(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    guard = someone_near(game, town, job="guard")
    game.renown.crimes.append({"id": 77, "crime": "theft", "witnesses": [guard.id], "reported": False,
                               "report_at": game.world.time + 60, "time": game.world.time})
    fixed_d20(monkeypatch, 1)
    said = text(cast(game, wiz, "geas", subject(game, wiz, "geas", "person")))
    assert "do as you say, for 30 days" in said and "say nothing" in said
    assert 77 in guard.flags["silenced"] and glamour.obeys(game, guard)
    assert int(guard.flags["bribed_until"]) > game.world.time, "the watch's guard never lays hands on you"
    talk = dialogue.Conversation(game, guard)
    assert talk.attitude() == "friendly"
    monkeypatch.setattr(law, "_unseen", lambda game_, n: False)
    monkeypatch.setattr("realmwalker.game.vision.can_see", lambda *a, **k: True)
    assert guard not in law.witnesses_here(game), "a geased guard sees none of your new crimes"
    before = guard.disposition
    game.world.time += 31 * glamour.DAY
    glamour.tick(game)
    assert not glamour.obeys(game, guard) and guard.disposition == max(-100, before + glamour.GEAS_SOUR)


def test_a_ninth_level_geas_holds_until_ended(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    npc = someone_near(game, town)
    fixed_d20(monkeypatch, 1)
    cast(game, wiz, "geas", subject(game, wiz, "geas", "person"), 9)
    assert npc.flags["geas_until"] == glamour.FOREVER


def test_modify_memory_wipes_a_witness_and_their_grudge(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    npc = someone_near(game, town)
    severity = int(law.crime_def(game, "theft")["severity"])
    npc.disposition = -5 - 10 * severity  # (an old -5, and the grudge the theft left)
    npc.remember("saw the traveller commit " + law.crime_def(game, "theft")["name"])
    game.renown.crimes.append({"id": 5, "crime": "theft", "witnesses": [npc.id], "reported": False,
                               "report_at": game.world.time + 60, "time": game.world.time})
    fixed_d20(monkeypatch, 1)
    said = text(cast(game, wiz, "modify_memory", subject(game, wiz, "modify_memory", "person")))
    assert "no longer remember" in said
    assert 5 in npc.flags["silenced"] and npc.disposition == -5, "the day's grudge goes; the older one stays"
    assert not any("traveller commit" in m for m in npc.memory)


def test_glibness_makes_every_charisma_roll_at_least_fifteen(world, tables, monkeypatch):
    bard = hero(tables)
    game = game_with(world, tables, bard)
    town = in_town(game)
    npc = someone_near(game, town)
    cast(game, bard, "glibness")
    assert glamour.glib(game)
    assert glamour.cha_roll(game, bard, "persuasion", 2) == 15 and glamour.cha_roll(game, bard, "athletics", 2) == 2
    monkeypatch.setattr(dialogue.dice, "d20", lambda *a, **k: _D20(1))
    ok, words = dialogue.Conversation(game, npc).check("persuasion", 10)
    assert "glib: 15" in words and ok


def test_antipathy_sends_a_band_of_that_kind_running(world, tables, monkeypatch):
    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    kinds = glamour.kinds_here(game)
    assert kinds
    kind = kinds[0][0]
    s = next(x for x in magic.road_targets(game, druid, "antipathy_sympathy")
             if x.ref == kind and x.data["how"] == "antipathy")
    cast(game, druid, "antipathy_sympathy", s)
    rng = RNG(3, "band")
    band = [spawn(tables, kind, rng, i + 1) for i in range(3)]
    enc = PendingEncounter("test", band, "They come.", False, "")
    fixed_d20(monkeypatch, 1)
    assert glamour.on_meeting(game, enc) is None, "most failed: the band runs"
    s2 = next(x for x in magic.road_targets(game, druid, "antipathy_sympathy")
              if x.ref == kind and x.data["how"] == "sympathy")
    cast(game, druid, "antipathy_sympathy", s2)
    enc = PendingEncounter("test", band, "They come.", False, "")
    enc = glamour.on_meeting(game, enc)
    assert enc is not None and enc.spotted_first, "drawn to you entranced: you see them first"


def test_awaken_wakes_an_animal_that_keeps_watch(world, tables):
    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    game.leader.animals.append({"kind": "mastiff", "name": "Brindle", "unfed": 0, "bought": 0})
    said = text(cast(game, druid, "awaken", subject(game, druid, "awaken", "animal")))
    assert "Brindle is awake" in said
    assert not any(i.def_id == "gem_1000" and i.qty == 3 for i in druid.inventory), "the agate was used up"
    rng = RNG(4, "night")
    enc = PendingEncounter("test", [spawn(tables, "wolf", rng, 1)], "Wolves.", False, "", asleep=True)
    enc, notes = spellwork.night_visitors(game, enc)
    assert not enc.asleep and "Brindle" in text(notes)


# ---------------------------------------------------------------------------- disguise and illusion
def test_disguise_self_and_seeming_are_as_good_as_the_spell_dc(world, tables):
    wiz = hero(tables)
    friend = hero(tables, "fighter", 0, 2)
    friend.is_player = False
    friend.companion = {"loyalty": 60, "wage": 0}
    game = game_with(world, tables, wiz, friend)
    dc = sp.save_dc(game.sheet(wiz), tables)
    said = text(cast(game, wiz, "disguise_self"))
    assert law.disguised(game) and int(game.renown.flags["disguise_dc"]) == dc and f"DC {dc}" in said
    game.leader.effects["disguised"] = 0
    said = text(cast(game, wiz, "seeming"))
    assert "Every face in the party" in said and law.disguised(game)
    assert game.leader.effects["disguised"] >= 8


def test_an_illusion_draws_the_town_eyes_away(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    npc = someone_near(game, town)
    assert glamour.distraction(game) == 0
    cast(game, wiz, "minor_illusion")
    assert glamour.distraction(game) == 5 and glamour.watcher_minus(game, npc) == 5
    cast(game, wiz, "major_image", slot=4)
    assert glamour.distraction(game) == 10
    game.world.time += 600
    assert glamour.distraction(game) == 10, "from a 4th-level slot it stays while you are in the town"
    game.leave_local()
    glamour.tick(game)
    in_town(game)
    assert glamour.distraction(game) == 0, "out of the town, the image is gone for good"


def test_minor_illusion_is_only_for_a_town(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    assert "only in a town" in magic.road_problem(game, wiz, "minor_illusion")


def test_mislead_turns_the_caster_invisible_in_a_fight(tables):
    wiz = hero(tables)
    b = Battle(tables, [wiz], [spawn(tables, "bandit", RNG(1), 1)], Env(), RNG(1, "b"), spots={0: (2, 2), 1: (6, 2)})
    b.start("Test fight.")
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert b.do_cast(me, "mislead", me)
    assert "invisible" in me.conditions and not b.can_see(foe, me)


def test_mislead_in_a_town_leaves_no_witnesses(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    npc = someone_near(game, town, dx=2)
    monkeypatch.setattr(law, "_unseen", lambda game_, n: False)
    monkeypatch.setattr("realmwalker.game.vision.can_see", lambda *a, **k: True)
    assert law.witnesses_here(game)
    cast(game, wiz, "mislead")
    assert glamour.unseen(game) and law.witnesses_here(game) == []
    assert npc is not None


def test_the_camp_wards_of_illusion(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    camp.make_camp(game)
    rng = RNG(5, "night")
    cast(game, wiz, "magic_mouth")
    enc = PendingEncounter("test", [spawn(tables, "wolf", rng, 1)], "Wolves.", False, "", asleep=True)
    enc, notes = spellwork.night_visitors(game, enc)
    assert not enc.asleep and "cries out" in text(notes)
    cast(game, wiz, "programmed_illusion")
    enc = PendingEncounter("test", [spawn(tables, "wolf", rng, 1)], "Wolves.", False, "", asleep=True)
    enc, notes = spellwork.night_visitors(game, enc)
    assert enc.spotted_first and not enc.asleep and "illusion" in text(notes)
    cast(game, wiz, "hallucinatory_terrain")
    assert spellwork.hidden(game, "long"), "hunters pass the veiled camp by"
    monkeypatch.setattr(spellwork.dice, "d20", lambda *a, **k: _D20(1))
    enc = PendingEncounter("test", [spawn(tables, "wolf", rng, 1)], "Wolves.", False, "", asleep=True)
    assert spellwork.night_visitors(game, enc)[0] is None
    cast(game, wiz, "mirage_arcane")
    rec = spellwork.wards_here(game)["veil"]
    assert rec["until"] - game.world.time > 9 * glamour.DAY


def test_project_image_hears_a_far_town(world, tables):
    from realmwalker.game import news

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    home = game.world.settlements[0]
    game.player.x, game.player.y = home.x, home.y
    far = next(s for s in game.world.settlements if 0 < max(abs(s.x - home.x), abs(s.y - home.y)) * 3 <= 500)
    game.player.known_settlements.add(far.id)
    news.add(game.world, "the miller's daughter married a stranger", far.x, far.y, kind="local", importance=3)
    s = subject(game, wiz, "project_image", "town", far.name)
    said = text(cast(game, wiz, "project_image", s))
    assert far.name in said


def test_illusory_script_waves_you_through_the_gate_and_speaks_for_you(world, tables, monkeypatch):
    from realmwalker.game import people

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    npc = someone_near(game, town)
    before = people.papers_impression(game, npc)
    cast(game, wiz, "illusory_script")
    assert glamour.scripted(game)
    assert people.papers_impression(game, npc) == before + glamour.SCRIPT_IMPRESS
    walled = next((s for s in game.world.settlements if s.walled), None)
    if walled is not None:
        monkeypatch.setattr(law, "rng_for", lambda game_, what: type("R", (), {"chance": lambda self, p: True})())
        monkeypatch.setattr("realmwalker.game.uniques.waved_through", lambda game_: "")
        said = text(law.gate_search(game, walled))
        assert not said or "without a look" in said


def test_nystuls_aura_and_sequester_hide_things_from_robbers_and_the_watch(world, tables):
    from realmwalker.game import magic_items

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    ring = magic_items.make(game, RNG(3, "ring"), kind="ring") or magic_items.make(game, RNG(3, "r"))
    wiz.inventory.append(ring)
    add_item(wiz, tables.items, "gem_500", 1)
    gem = next(i for i in wiz.inventory if i.def_id == "gem_500")
    cast(game, wiz, "nystuls_magic_aura", subject(game, wiz, "nystuls_magic_aura", "thing"))
    assert glamour.masked(game, ring) and glamour.hidden_thing(game, ring, robbers=True)
    cast(game, wiz, "sequester", next(s for s in magic.road_targets(game, wiz, "sequester") if s.ref is gem))
    assert glamour.sequestered(gem)
    fight._rob_party(game, RNG(1, "rob"))
    assert ring in wiz.inventory and gem in wiz.inventory, "robbers passed over the masked and the sequestered"
    law.confiscate(game, 0)
    assert gem in wiz.inventory, "the watch never saw the sequestered thing"


def test_sequester_holds_a_body_out_of_time(world, tables):
    wiz = hero(tables, "cleric")  # (a priest who could raise the fallen: the body is carried, not buried at once)
    friend = hero(tables, "fighter", 0, 2)
    friend.is_player = False
    friend.companion = {"loyalty": 60, "wage": 0}
    game = game_with(world, tables, wiz, friend)
    friend.alive = False
    friend.hp = 0
    game.party.remove(friend)
    game.fallen.append({"char": friend, "died": float(game.world.time), "since": float(game.world.time),
                        "counted": 0.0, "repose": 0.0, "cause": "a test"})
    s = next(x for x in magic.road_targets(game, wiz, "sequester") if x.kind == "body")
    said = text(cast(game, wiz, "sequester", s))
    assert "out of time" in said
    body = revival.body_of(game, friend)
    game.world.time += 50 * glamour.DAY
    assert revival.dead_for(game, body) < glamour.DAY


def test_nondetection_hides_a_mind_from_detect_thoughts(tables):
    wiz = hero(tables)
    b = Battle(tables, [wiz], [spawn(tables, "bandit", RNG(1), 1)], Env(), RNG(1, "b"), spots={0: (2, 2), 1: (4, 2)})
    b.start("Test fight.")
    me = b.side(PARTY)[0]
    assert b.thinks(me)
    me.buffs.append({"nondetection": True})
    assert not b.thinks(me)


# ---------------------------------------------------------------------------- the small arts
def test_druidcraft_tells_the_weather_and_lights_the_fire(world, tables):
    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    c = camp.make_camp(game)
    c.fire = False
    said = text(cast(game, druid, "druidcraft"))
    assert "The weather here now:" in said and c.fire


def test_elementalism_and_prestidigitation_at_the_camp(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    c = camp.make_camp(game)
    c.fire = False
    assert "embers" in text(cast(game, wiz, "elementalism")) and c.fire
    wiz.wet = 60.0
    assert "drier" in text(cast(game, wiz, "elementalism")) and wiz.wet < 60
    wiz.dirt = 50.0
    cast(game, wiz, "prestidigitation")
    assert wiz.dirt < 50 and game.renown.flags.get("warm_meal")


def test_thaumaturgy_gives_advantage_on_intimidation(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    town = in_town(game)
    npc = someone_near(game, town)
    npc.disposition = 0
    talk = dialogue.Conversation(game, npc)
    assert talk._mode("intimidation") != "advantage"
    cast(game, cleric, "thaumaturgy")
    assert talk._mode("intimidation") == "advantage"
    assert "booming" in talk.check("intimidation", 10)[1]


def test_an_encounter_on_the_road_goes_through_antipathy(world, tables, monkeypatch):
    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    seen = []
    monkeypatch.setattr(glamour, "on_meeting", lambda game_, enc: seen.append(enc) or enc)
    monkeypatch.setattr(encounters, "encounter_chance", lambda *a: 1.0)
    encounters.roll_encounter(game, 60)
    assert seen


def test_the_wards_wake_the_camp_in_a_real_rest(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    camp.make_camp(game)
    cast(game, wiz, "programmed_illusion")
    band = [spawn(tables, "wolf", RNG(6, "night"), 1)]
    monkeypatch.setattr(encounters, "roll_encounter",
                        lambda game_, minutes: PendingEncounter("test", list(band), "Wolves.", False, ""))
    said = text(fight.rest(game, "long"))
    assert game.encounter is not None and not game.encounter.asleep and game.encounter.spotted_first, said
    game.encounter = None
    game.camp.wards.clear()
    game.leader.animals.append({"kind": "mastiff", "name": "Brindle", "unfed": 0, "bought": 0, "awake": True})
    said = text(fight.rest(game, "long"))
    assert game.encounter is not None and not game.encounter.asleep and "Brindle" in said


def test_mislead_ends_when_you_strike_someone_in_a_town(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    someone_near(game, town)
    cast(game, wiz, "mislead")
    assert glamour.unseen(game)
    law.commit(game, "assault")
    assert not glamour.unseen(game)


def test_prestidigitation_warms_the_whole_party_meal(world, tables):
    wiz = hero(tables)
    friend = hero(tables, "fighter", 0, 2)
    friend.is_player = False
    friend.companion = {"loyalty": 60, "wage": 0}
    game = game_with(world, tables, wiz, friend)
    in_the_wild(game)
    camp.make_camp(game).fire = False
    cast(game, wiz, "prestidigitation")
    for c in game.party:
        add_item(c, tables.items, "bread", 2)
        c.hunger, c.body_heat = 60.0, -40.0
    for c in game.party:
        camp.eat_meal(game, c)
    assert all(c.body_heat > -40.0 for c in game.party), "everyone's food was warm"


def test_glibness_reaches_haggling(world, tables, monkeypatch):
    from realmwalker.game import economy

    bard = hero(tables)
    game = game_with(world, tables, bard)
    cast(game, bard, "glibness")
    seen = []
    real = glamour.cha_roll
    monkeypatch.setattr(glamour, "cha_roll", lambda *a: seen.append(a[2]) or real(*a))
    town = in_town(game)
    npc = next((n for n in game.world.npcs.values() if n.settlement == town.id and n.alive
                and n.job in ("shopkeeper", "market_trader")), None)
    if npc is None:
        pytest.skip("no merchant in this town")
    economy.haggle(game, npc)
    assert seen and seen[0] in glamour.CHA_SKILLS
