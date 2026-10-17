"""Spells outside battle, part E.3 (Expansion 3): finding and seeing (Detect Magic, Detect Evil and Good, Detect Poison
and Disease, Find Traps, Locate Object, Locate Creature, Locate Animals or Plants, Clairvoyance, Arcane Eye, Scrying,
Beast Sense, Drawmij's Instant Summons), asking the powers (Augury, Divination, Commune, Commune with Nature, Contact
Other Plane, Legend Lore) and talking (Comprehend Languages, Tongues, Speak with Animals, Speak with Dead, Speak with
Plants, Message, Sending, Animal Messenger, Dream, Telepathy, Rary's Telepathic Bond, Detect Thoughts). Each is cast
where it is used: in a dungeon, on the road, in a town, after a fight, in a real fight."""

import copy

import numpy as np
import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import camp, divining, dungeon, fight, magic, quests, speech, spellwork
from realmwalker.game.encounters import LocalActor, PendingEncounter, make_encounter
from realmwalker.game.state import new_game
from realmwalker.rules import progression
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check, estimates
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

E3 = sorted(("detect_magic detect_evil_and_good detect_poison_and_disease find_traps locate_object locate_creature "
             "locate_animals_or_plants clairvoyance arcane_eye scrying beast_sense drawmijs_instant_summons augury "
             "divination commune commune_with_nature contact_other_plane legend_lore comprehend_languages tongues "
             "speak_with_animals speak_with_dead speak_with_plants message sending animal_messenger dream telepathy "
             "rarys_telepathic_bond detect_thoughts").split())
COMPONENTS = ("glass_eye", "scrying_mirror", "sapphire", "divination_tools", "seers_incense", "rare_incense",
              "ivory_strips")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    """Every caster in these tests has the spells of E.3 ready (the druid, the ranger, the bard and the warlock, whose
    spells many of these are, are not in the game yet; which ones a class learns is Part C's, tested there)."""
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + E3)) if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


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
        add_item(c, tables.items, cid, 3 if tables.items.get(cid).get("stack") else 1)
    return c


def companion(tables, seed=2):
    c = hero(tables, "fighter", 0, seed)
    c.is_player = False
    c.companion = {"loyalty": 60, "wage": 0}
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


def into_dungeon(game, site_index=0):
    site = game.world.sites[site_index]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    return game.local


def open_cells(game, lm, near: int, far: int):
    """Walkable squares between `near` and `far` squares of the player with nothing of stone between."""
    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    p = game.player
    out = []
    for x in range(max(0, p.lx - far), min(lm.width, p.lx + far + 1)):
        for y in range(max(0, p.ly - far), min(lm.height, p.ly + far + 1)):
            d = max(abs(x - p.lx), abs(y - p.ly))
            if near <= d <= far and walk[x, y] and (x, y) not in lm.features \
                    and not divining.behind_stone(game, lm, x, y):
                out.append((x, y))
    return out


def text(lines) -> str:
    return " ".join(lines)


def fight_of(tables, party, foes=("bandit",), env=None, spots=None):
    rng = RNG(1, "foes")
    b = Battle(tables, party, [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)], env or Env(), RNG(1, "b"),
               spots=spots or {})
    b.start("Test fight.")
    return b


# ---------------------------------------------------------------------------- the data
def test_the_thirty_spells_are_in_and_the_start_up_check_knows_them(tables):
    assert all(sid in tables.spells for sid in E3)
    assert not [p for p in check.problems(tables) if any(sid in p for sid in E3)]
    for sid in E3:
        if sid != "detect_thoughts":
            assert sp.out_of_battle(tables.spells[sid]), f"{sid} is never cast in a fight"
        assert sp.road_use(tables, sid) is not None, f"{sid} has a use outside a fight"
    for cid in COMPONENTS:
        assert cid in tables.items and tables.items.get(cid).get("how")


# ---------------------------------------------------------------------------- sensing
def test_detect_magic_names_the_auras_in_the_pack_and_a_chest_that_holds_magic(world, tables):
    from realmwalker.game import magic_items

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    ring = magic_items.make(game, RNG(3, "ring"), kind="ring") or magic_items.make(game, RNG(3, "r"))
    ring.magic["identified"] = False
    wiz.inventory.append(ring)
    pos = open_cells(game, lm, 2, 5)[0]
    lm.features[pos] = {"kind": "chest", "treasure": 1, "contents": {"items": [ring.to_dict() | {"uid": 0}], "money": 7}}
    said = text(cast(game, wiz, "detect_magic"))
    assert "aura of" in said and "glows with magic" in said
    assert any(m["kind"] == "magic" and (m["x"], m["y"]) == pos for m in divining.marks_here(game))
    game.player.lx, game.player.ly = pos
    dungeon.open_chest(game, lm, *pos)
    assert any(it.magic for it in lm.items[pos]), "the chest held what was sensed in it"


def test_fixed_contents_stay_what_they_were(world, tables):
    game = game_with(world, tables, hero(tables))
    lm = into_dungeon(game)
    pos = open_cells(game, lm, 1, 6)[0]
    lm.features[pos] = {"kind": "chest", "treasure": 2}
    first = dungeon.fix_contents(game, lm, pos)
    assert dungeon.fix_contents(game, lm, pos) == first


def test_detect_evil_finds_the_undead_but_not_through_stone(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    lm = into_dungeon(game)
    near = open_cells(game, lm, 2, 5)[0]
    lm.actors.append(LocalActor(900, "skeletons", near[0], near[1], [spawn(tables, "skeleton", RNG(1), 1)]))
    said = text(cast(game, cleric, "detect_evil_and_good"))
    assert "undead" in said.lower()
    assert any(m["kind"] == "evil" and m.get("actor") == 900 for m in divining.marks_here(game))
    p = game.player
    for x, y in divining._line(p.lx, p.ly, *near):  # a wall of stone between: nothing is sensed through it
        dungeon.set_terrain(lm, x, y, "wall_stone")
    assert divining.behind_stone(game, lm, *near)


def test_detect_poison_finds_a_hidden_fever_and_poisoned_darts(world, tables):
    cleric = hero(tables, "cleric")
    friend = companion(tables)
    game = game_with(world, tables, cleric, friend)
    did = next(iter(tables.diseases.defs))
    friend.diseases.append({"id": did, "phase": "incubating"})
    lm = into_dungeon(game)
    pos = open_cells(game, lm, 2, 5)[0]
    lm.features[pos] = {"kind": "trap", "trap": "darts", "dc": 30}
    said = text(cast(game, cleric, "detect_poison_and_disease"))
    assert "not yet showing" in said and lm.features[pos]["found"]


def test_find_traps_senses_traps_in_sight_and_helps_search_for_them(world, tables, monkeypatch):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    lm = into_dungeon(game)
    pos = open_cells(game, lm, 1, 2)[0]
    lm.features[pos] = {"kind": "trap", "trap": "blade", "dc": 12}
    said = text(cast(game, cleric, "find_traps"))
    assert "swinging blade" in said and lm.features[pos].get("sensed") and not lm.features[pos].get("found")
    assert "not where" in said or "do not know where" in said
    out = text(dungeon.search(game))
    assert lm.features[pos].get("found") or "nothing" in out


def test_find_traps_out_on_the_road_finds_nothing_to_look_for(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    assert magic.road_problem(game, cleric, "find_traps") == "there are no traps to find out here"


# ---------------------------------------------------------------------------- locating
def test_locate_object_points_to_the_nearest_chest(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    far = open_cells(game, lm, 6, 30)[-1]
    lm.features[far] = {"kind": "chest", "treasure": 1}
    s = subject(game, wiz, "locate_object", name="chest")
    said = text(cast(game, wiz, "locate_object", s))
    assert "feet to the" in said
    assert any(m["kind"] == "thing" for m in divining.marks_here(game))


def test_locate_creature_finds_a_captive_and_someone_met_in_town(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    spot = open_cells(game, lm, 4, 30)[-1]
    lm.features[spot] = {"kind": "captive", "name": "Aldo the miller"}
    s = subject(game, wiz, "locate_creature", name="Aldo")
    assert "feet" in text(cast(game, wiz, "locate_creature", s))
    assert any(m["kind"] == "creature" for m in divining.marks_here(game))


def test_locate_animals_or_plants_helps_the_hunt_and_the_forage(world, tables, monkeypatch):
    druid = hero(tables, "cleric")
    game = game_with(world, tables, druid)
    wild = next((x, y) for x in range(game.world.width) for y in range(game.world.height)
                if game.world.settlement_at(x, y) is None and camp.by_land(game, tables.camping["forage"])
                is not None and game.biome_key(x, y) in ("forest", "plains", "hills"))
    game.player.x, game.player.y = wild
    cast(game, druid, "locate_animals_or_plants", subject(game, druid, "locate_animals_or_plants", "herbs"))
    assert druid.effects.get("forage_tip", 0) > 0
    seen = {}
    real = camp.check

    def spy(game_, skill, dc, bonus=0, **kw):
        seen[kw.get("tag")] = bonus
        return real(game_, skill, dc, bonus, **kw)

    monkeypatch.setattr(camp, "check", spy)
    camp.forage(game)
    assert seen.get("forage") == 5
    cast(game, druid, "locate_animals_or_plants", subject(game, druid, "locate_animals_or_plants", "game"))
    assert druid.effects.get("hunting_tip", 0) > 0


# ---------------------------------------------------------------------------- seeing from afar
def test_clairvoyance_and_arcane_eye_map_the_level(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    lm.seen[:] = False
    before = int(lm.seen.sum())
    cast(game, wiz, "clairvoyance")
    after_eye = int(lm.seen.sum())
    assert after_eye > before, "the nearest unseen rooms are seen"
    said = text(cast(game, wiz, "arcane_eye"))
    assert int(lm.seen.sum()) > after_eye and "map" in said
    for a in lm.actors:
        if a.creatures and divining._flood(game, lm)[a.x, a.y]:
            assert any(m.get("actor") == a.id for m in divining.marks_here(game))


def test_clairvoyance_only_under_the_ground(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    assert "under the ground" in magic.road_problem(game, wiz, "clairvoyance")


def test_scrying_finds_a_dragon_or_is_shaken_off(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    s = subject(game, wiz, "scrying", kind="figure")
    monkeypatch.setattr(divining, "scry_bonus", lambda game_, fig: -50)
    said = text(cast(game, wiz, "scrying", s))
    assert "is in" in said or "is at" in said
    wiz.spells["slots_used"] = []  # (ignored: just keep casting)
    sp.restore_slots(wiz)
    monkeypatch.setattr(divining, "scry_bonus", lambda game_, fig: 50)
    said = text(cast(game, wiz, "scrying", s))
    assert "Not again for a day" in said
    assert all(x.ref != s.ref for x in magic.road_targets(game, wiz, "scrying"))


def test_beast_sense_lets_the_party_see_a_band_first(world, tables):
    ranger = hero(tables, "cleric")
    game = game_with(world, tables, ranger)
    assert magic.road_problem(game, ranger, "beast_sense") == "you have no animal to look through"
    ranger.animals = [{"kind": "riding_horse", "name": "Bess"}]
    cast(game, ranger, "beast_sense")
    group = next(iter(g for g in tables.creatures.encounters if tables.creatures.encounters[g].get("weight", 1)))
    assert make_encounter(game, group, RNG(5)).spotted_first


# ---------------------------------------------------------------------------- Drawmij's Instant Summons
def test_instant_summons_calls_back_what_robbers_took_but_not_what_was_sold(world, tables):
    from realmwalker.game import gear
    from realmwalker.rules.inventory import remove_item

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    add_item(wiz, tables.items, "silver_ring" if "silver_ring" in tables.items.defs else "dagger")
    s = subject(game, wiz, "drawmijs_instant_summons")
    cast(game, wiz, "drawmijs_instant_summons", s)
    gem = next(i for i in wiz.inventory if any(t.startswith("summons:") for t in i.tags))
    assert gear.use_name(game, gem) == "Crush the sapphire"
    thing = next(i for i in wiz.inventory if i.uid == s.ref)
    assert "with you already" in text(gear.use_item(game, wiz, gem))
    remove_item(wiz, thing.uid)
    divining.taken(game, [thing], "robbers")
    said = text(gear.use_item(game, wiz, gem))
    assert "hand" in said and any(i.def_id == thing.def_id for i in wiz.inventory)
    assert not any(i.uid == gem.uid for i in wiz.inventory), "the sapphire is crushed"
    # a second one, sold: it stays where it is
    s2 = subject(game, wiz, "drawmijs_instant_summons")
    cast(game, wiz, "drawmijs_instant_summons", s2)
    gem2 = next(i for i in wiz.inventory if any(t.startswith("summons:") for t in i.tags))
    remove_item(wiz, s2.ref)
    assert "will not come" in text(gear.use_item(game, wiz, gem2))


def test_robbers_on_the_road_carry_off_a_bound_thing_that_can_be_called(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    add_item(wiz, tables.items, "gold_ring" if "gold_ring" in tables.items.defs else "dagger")
    best = max((i for i in wiz.inventory if tables.items.value(i) >= 100 and not i.tags
                and float(tables.items.get(i.def_id).get("weight", 0)) <= 10 and i.def_id != "sapphire"),
               key=lambda i: tables.items.value(i))
    cast(game, wiz, "drawmijs_instant_summons", divining.Subject("x", "item", best.uid))
    fight._rob_party(game, RNG(2))
    rec = wiz.spells[divining.SUMMONS][str(best.uid)]
    if not any(i.uid == best.uid for i in wiz.inventory):
        assert rec.get("taken") == "robbers" and rec.get("item")


# ---------------------------------------------------------------------------- asking the powers
def _work(game, template="bounty", hidden="deserters"):
    for q in [q for q in game.quests]:
        game.quests.remove(q)
    site = game.world.sites[1]
    q = {"id": 999, "template": template, "state": "accepted", "giver": -1, "giver_name": "Old Hal", "giver_job": "guard",
         "town": 0, "faction": -1, "reward": 500, "days": 9, "offered_day": 0, "hidden": hidden, "revealed": False,
         "done": False, "target": {"site": site.id, "gang": -1}, "words": {"giver": "Hal", "town": "Here"},
         "journal": []}
    if template == "bounty":
        q["text_key"] = ""
    game.quests.append(q)
    return q, site


def test_augury_reads_woe_in_a_work_with_a_hidden_side_and_muddles_when_asked_too_often(world, tables, monkeypatch):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    monkeypatch.setattr(quests, "LIVE", ("accepted", "return", "active"))
    q, _ = _work(game)
    monkeypatch.setattr(quests, "title", lambda game_, q_: "the bounty")
    s = subject(game, cleric, "augury", "work")
    assert divining.omen(game, s) == "both"
    said = text(cast(game, cleric, "augury", s))
    assert "Weal and woe" in said
    for _ in range(8):
        divining.muddled(game, cleric, "augury")
    assert cleric.uses["omen:augury"] >= 9
    progression.long_rest(cleric, tables, RNG(1))
    assert "omen:augury" not in cleric.uses


def test_divination_tells_the_truth_of_a_work_and_where_its_quarry_is(world, tables, monkeypatch):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    monkeypatch.setattr(quests, "LIVE", ("accepted", "return", "active"))
    monkeypatch.setattr(quests, "title", lambda game_, q_: "the bounty")
    monkeypatch.setattr(quests, "fill", lambda game_, q_, kind, which="": "They are deserters, starving.")
    q, site = _work(game)
    game.player.explored[site.x, site.y] = False
    said = text(cast(game, cleric, "divination", subject(game, cleric, "divination", "work")))
    assert q["revealed"] and "not as you were told" in said
    assert game.player.explored[site.x, site.y]
    assert not any(i.def_id == "seers_incense" and i.qty == 3 for i in cleric.inventory), "the incense burned"


def test_commune_answers_three_questions_from_the_world(world, tables, monkeypatch):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    monkeypatch.setattr(quests, "LIVE", ("accepted", "return", "active"))
    monkeypatch.setattr(quests, "title", lambda game_, q_: "the bounty")
    monkeypatch.setattr(quests, "fill", lambda game_, q_, kind, which="": "They are deserters.")
    q, _ = _work(game)
    pool = divining.questions(game)
    assert pool and pool[0].data["ask"] == "work"
    lines = cast(game, cleric, "commune", pool[0])
    answers = [ln for ln in lines if "Yes." in ln or "No." in ln]
    assert len(answers) == min(3, len(pool))
    assert q["revealed"], "a No to an honest work writes down what it hides"


def test_contact_other_plane_can_leave_the_caster_senseless_until_a_long_rest(world, tables, monkeypatch):
    from realmwalker.core import dice

    wiz = hero(tables)
    game = game_with(world, tables, wiz)

    class Low:
        natural = 1

    monkeypatch.setattr(divining.dice, "d20", lambda *a, **k: Low())
    said = text(cast(game, wiz, "contact_other_plane"))
    assert "psychic" in said or "necrotic" in said or "reels" in said
    assert wiz.uses.get("addled")
    ok, why = sp.can_cast(wiz, tables, "magic_missile")
    assert not ok and "reeling" in why
    b = fight_of(tables, [wiz])
    assert "incapacitated" in b.side(PARTY)[0].conditions
    progression.long_rest(wiz, tables, RNG(1))
    assert not wiz.uses.get("addled")
    del dice


def test_commune_with_nature_tells_the_land_and_not_in_a_town(world, tables):
    druid = hero(tables, "cleric")
    game = game_with(world, tables, druid)
    town = game.world.settlements[0]
    game.player.x, game.player.y = town.x, town.y
    assert "town" in magic.road_problem(game, druid, "commune_with_nature")
    game.player.x, game.player.y = town.x + 2, town.y + 2
    said = text(cast(game, druid, "commune_with_nature"))
    assert "Places:" in said and "Water:" in said


def test_legend_lore_knows_a_storied_thing_and_where_a_lost_artifact_lies(world, tables):
    from realmwalker.game import magic_items

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    blade = magic_items.make(game, RNG(9, "b"), kind="weapon") or magic_items.make(game, RNG(9))
    blade.magic.update(identified=False, story="Forged for a king who drowned.", title="Kingsbane")
    wiz.inventory.append(blade)
    s = subject(game, wiz, "legend_lore", "carried")
    said = text(cast(game, wiz, "legend_lore", s))
    assert blade.magic["identified"] and "drowned" in said
    arts = game.world.politics.get("artifacts", [])
    lost = [i for i, a in enumerate(arts) if not a.get("found") and 0 <= int(a.get("site", -1)) < len(game.world.sites)]
    if lost:
        sp.restore_slots(wiz)
        site = game.world.sites[arts[lost[0]]["site"]]
        game.player.explored[site.x, site.y] = False
        cast(game, wiz, "legend_lore", divining.Subject(arts[lost[0]]["name"], "artifact", lost[0]))
        assert game.player.explored[site.x, site.y]


def test_legend_lore_needs_the_ivory_strips(world, tables):
    wiz = hero(tables)
    wiz.inventory = [i for i in wiz.inventory if i.def_id != "ivory_strips"]
    assert "ivory" in sp.component_problem(wiz, tables, "legend_lore")


# ---------------------------------------------------------------------------- talking
def _encounter(game, group_ids):
    creatures = [spawn(game.tables, d, RNG(1), i + 1) for i, d in enumerate(group_ids)]
    game.encounter = PendingEncounter("test", creatures, "They come.", True, "", attitude="indifferent")
    return game.encounter


def test_a_band_that_shares_no_tongue_and_tongues_or_comprehend_languages(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    _encounter(game, ["gnoll", "gnoll"])
    dc, why = fight.encounter_talk_dc(game)
    assert dc is None and "no tongue" in why
    cast(game, wiz, "comprehend_languages")
    harder, why = fight.encounter_talk_dc(game)
    assert harder is not None and not why
    sp.end(wiz, "comprehend_languages")
    cast(game, wiz, "tongues", wiz)
    dc, why = fight.encounter_talk_dc(game)
    assert dc is not None and dc <= harder


def test_speak_with_animals_lets_hungry_beasts_be_talked_past(world, tables):
    druid = hero(tables, "cleric")
    game = game_with(world, tables, druid)
    _encounter(game, ["wolf", "wolf"])
    assert fight.encounter_talk_dc(game)[0] is None
    cast(game, druid, "speak_with_animals")
    assert fight.encounter_talk_dc(game)[0] is not None


def test_speak_with_dead_asks_a_slain_bandit_where_its_band_keeps(world, tables):
    from realmwalker.world import factions as fx

    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    b = fight_of(tables, [cleric], ("bandit",))
    foe = b.side(FOE)[0]
    foe.creature.hp, foe.creature.alive, foe.state, foe.hp = 0, False, "dead", 0
    b._check_end()
    game.battle = b
    fight.finish_battle(game)
    game.battle = None
    s = subject(game, cleric, "speak_with_dead", "corpse")
    said = text(cast(game, cleric, "speak_with_dead", s))
    gangs = [f for f in fx.active_factions(game.world, "gang") if 0 <= f.site < len(game.world.sites)]
    if gangs:
        assert "We keep to" in said
    assert magic.road_problem(game, cleric, "speak_with_dead") is not None, "a corpse answers once"


def test_speak_with_plants_warns_of_a_band_and_shows_food(world, tables):
    druid = hero(tables, "cleric")
    game = game_with(world, tables, druid)
    town = game.world.settlements[0]
    game.player.x, game.player.y = town.x + 2, town.y + 2
    cast(game, druid, "speak_with_plants")
    assert druid.effects.get("forewarned", 0) > 0 and druid.effects.get("forage_tip", 0) > 0


def test_message_sending_animal_messenger_dream_and_telepathy_call_a_waiting_companion(world, tables):
    from realmwalker.game import companions

    wiz = hero(tables)
    friend = companion(tables)
    game = game_with(world, tables, wiz, friend)
    town = game.world.settlements[0]
    game.player.x, game.player.y = town.x, town.y
    companions.wait_here(game, friend)
    assert friend in game.waiting
    s = subject(game, wiz, "message", "companion")
    said = text(cast(game, wiz, "message", s))
    assert friend in game.party and "joins you" in said
    for sid in ("sending", "telepathy", "dream", "animal_messenger"):
        sp.restore_slots(wiz)
        game.player.x, game.player.y = town.x, town.y
        if friend in game.party:
            companions.wait_here(game, friend)
        game.player.x, game.player.y = town.x + 3, town.y
        s = subject(game, wiz, sid, "companion")
        said = text(cast(game, wiz, sid, s))
        assert friend.companion.get("coming", 0) > game.world.time, sid
        assert friend.companion["wait_at"] == [game.player.x, game.player.y]
        assert "sets out" in said
        friend.companion.pop("coming")
        companions.rejoin(game)
        assert friend in game.party


def test_animal_messenger_reaches_fifty_miles(world, tables):
    from realmwalker.game import companions

    wiz = hero(tables)
    friend = companion(tables)
    game = game_with(world, tables, wiz, friend)
    companions.wait_here(game, friend)
    game.player.x += 40  # (120 miles off)
    assert "reach" in magic.road_problem(game, wiz, "animal_messenger")


def test_dream_sends_a_nightmare_and_the_beast_meets_you_hurt(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    nightmare = next((s for s in magic.road_targets(game, wiz, "dream") if s.kind == "nightmare"), None)
    if nightmare is None:
        pytest.skip("no dragon or beast of the songs lives in this world")
    monkeypatch.setattr(divining, "scry_bonus", lambda game_, fig: -50)
    cast(game, wiz, "dream", nightmare)
    fig = game.world.figures[nightmare.ref]
    assert fig.name in game.renown.flags["nightmares"]
    beast = spawn(tables, "wolf", RNG(1), 1)
    beast.name, beast.named = fig.name, True
    before = beast.hp
    said = speech.nightmares_at_the_start(game, [beast])
    assert beast.hp < before and said


def test_rarys_telepathic_bond_keeps_the_linked_from_surprise(world, tables):
    wiz = hero(tables)
    friend = companion(tables)
    game = game_with(world, tables, wiz, friend)
    cast(game, wiz, "rarys_telepathic_bond")
    assert sp.lasting_flag(friend, tables, "linked") or sp.lasting_flag(wiz, tables, "linked")
    env = Env()
    env.surprised = PARTY
    b = fight_of(tables, [wiz, friend], ("bandit",), env=env)
    assert not any(f.surprised for f in b.side(PARTY))


def test_detect_thoughts_finds_an_invisible_foe_in_a_fight(tables):
    wiz = hero(tables)
    b = fight_of(tables, [wiz], ("bandit",), spots={0: (2, 2), 1: (4, 2)})
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    foe.conditions["invisible"] = -1
    assert not b.can_see(me, foe)
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert estimates.spell_value(b, me, "detect_thoughts", target=me).total() > 0, "the Auto sees its worth"
    assert b.do_cast(me, "detect_thoughts", me)
    assert b.can_see(me, foe)


def test_detect_thoughts_reads_a_townsman_near_you(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = game.world.settlements[0]
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    npc = next(n for n in game.world.npcs.values() if n.settlement == town.id and n.alive)
    npc.present = True
    npc.x, npc.y = game.player.lx + 1, game.player.ly
    npc.profile["secret"] = "They owe the miller forty crowns."
    monkeypatch.setattr(speech.dice, "d20", lambda *a, **k: type("R", (), {"natural": 1})())
    s = subject(game, wiz, "detect_thoughts", "person")
    said = text(cast(game, wiz, "detect_thoughts", s))
    assert "forty crowns" in said


# ---------------------------------------------------------------------------- the Spells page
def test_the_spells_page_lists_what_locate_object_seeks(make_app, world, tables):
    from realmwalker.ui.screens.spells import SpellsScreen, spell_detail

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    far = open_cells(game, lm, 6, 30)[-1]
    lm.features[far] = {"kind": "chest", "treasure": 1}
    s = subject(game, wiz, "locate_object", name="chest")
    lines = " ".join(spell_detail(game, wiz, "locate_object", s))
    assert "nearest chest" in lines and "Enter casts it" in lines
    app = make_app()
    screen = SpellsScreen(app, game)
    screen.sel = screen.spells().index("locate_object")
    assert any(t.name == "the nearest chest" for t in screen.targets())


# ---------------------------------------------------------------------------- from the fresh review
def test_a_bound_thing_won_back_is_not_called_twice(world, tables):
    from realmwalker.game import gear
    from realmwalker.rules.inventory import add_existing, remove_item
    from realmwalker.rules.items import Item

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    s = subject(game, wiz, "drawmijs_instant_summons")
    cast(game, wiz, "drawmijs_instant_summons", s)
    gem = next(i for i in wiz.inventory if any(t.startswith("summons:") for t in i.tags))
    thing = next(i for i in wiz.inventory if i.uid == s.ref)
    remove_item(wiz, thing.uid)
    divining.taken(game, [thing], "robbers")
    back = Item.from_dict(thing.to_dict())
    back.uid = 0
    add_existing(wiz, tables.items, back)  # (the robbers beaten, the thing picked up again: a new uid)
    count = sum(1 for i in wiz.inventory if i.def_id == thing.def_id and i.name == thing.name)
    assert "with you already" in text(gear.use_item(game, wiz, gem))
    assert sum(1 for i in wiz.inventory if i.def_id == thing.def_id and i.name == thing.name) == count


def test_trees_do_not_stop_divination_but_walls_do(world, tables):
    game = game_with(world, tables, hero(tables))
    lm = into_dungeon(game)
    near = open_cells(game, lm, 3, 5)[0]
    p = game.player
    line = divining._line(p.lx, p.ly, *near)
    for x, y in line:
        dungeon.set_terrain(lm, x, y, "tree_broadleaf")
    assert not divining.behind_stone(game, lm, *near)
    dungeon.set_terrain(lm, *line[0], "secret_door")
    assert divining.behind_stone(game, lm, *near)


def test_the_dead_of_the_last_fight_go_cold_after_a_day(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    b = fight_of(tables, [cleric], ("bandit",))
    foe = b.side(FOE)[0]
    foe.creature.hp, foe.creature.alive, foe.state, foe.hp = 0, False, "dead", 0
    speech.remember_the_dead(game, b, "bandits")
    assert speech._corpses(game)
    game.world.time += 2 * 24 * 60
    assert not speech._corpses(game)
    b2 = fight_of(tables, [cleric], ("bandit",))
    speech.remember_the_dead(game, b2, "bandits")  # (nobody fell this time)
    assert game.fresh_dead is None


def test_a_reeling_mind_reads_no_ritual(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    wiz.uses["addled"] = 1
    assert "reeling" in magic.road_problem(game, wiz, "comprehend_languages")
