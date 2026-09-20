"""Townsfolk: who lives where, days and nights, first impressions, memory, and conversations."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import save
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import first_impression, is_day, npc_at, npcs_in, update_positions
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Peopleland", 8, "medium"), tables).generate()


def hero(tables, seed=1, background="soldier", race="human"):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class("fighter")
    b.set_background(background)
    return b.build()


@pytest.fixture
def game(tables, world):
    return new_game(copy.deepcopy(world), tables, hero(tables))


def visit(game, kind: str):
    s = next((s for s in game.world.settlements if s.kind == kind), None)
    if s is None:
        pytest.skip(f"no {kind} in this world")
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return s


def at_noon(game):
    m = game.moment
    game.world.time += ((12 - m.hour) % 24) * 60 - m.minute


@pytest.mark.parametrize("kind", ["hamlet", "village", "town", "city", "hold", "elfhall"])
def test_every_settlement_has_its_people(game, kind):
    at_noon(game)
    s = visit(game, kind)
    people = npcs_in(game.world, s.id)
    assert people
    jobs = {n.job for n in people}
    assert "headman" in jobs or kind in ("town", "city") and "innkeeper" in jobs or kind == "hold"
    if kind in ("town", "city"):
        assert {"innkeeper", "priest", "smith", "shopkeeper", "guard"} <= jobs
    walk = game.tables.terrain.walk[game.remap_for(game.local)[game.local.terrain]]
    for n in people:
        assert n.profile.get("appearance") and n.profile_source == "fallback"
        if n.present:
            assert walk[n.x, n.y], f"{n.title} stands in a wall"
    positions = [(n.x, n.y) for n in people if n.present]
    assert len(positions) == len(set(positions)), "two people in one place"


def test_people_are_made_once(game):
    s = visit(game, "town")
    before = [n.id for n in npcs_in(game.world, s.id)]
    game.leave_local()
    game.enter_local()
    assert [n.id for n in npcs_in(game.world, s.id)] == before


def test_shops_close_and_people_go_home_at_night(game):
    s = visit(game, "town")
    lm = game.local
    at_noon(game)
    update_positions(game, lm)
    assert is_day(game)
    day = {n.id for n in npcs_in(game.world, s.id) if n.present}
    game.world.time += 12 * 60
    assert not is_day(game)
    update_positions(game, lm)
    night = {n.id for n in npcs_in(game.world, s.id) if n.present}
    assert night < day
    jobs_at_night = {game.world.npcs[i].job for i in night}
    assert jobs_at_night <= {"innkeeper", "serving_hand", "guard", "priest", "lord", "acolyte"}


def test_first_impressions(game, tables):
    s = visit(game, "town")
    npc = next(n for n in npcs_in(game.world, s.id) if n.job == "shopkeeper")
    npc.traits = ["honest", "cheerful"]
    clean = first_impression(game, npc)
    game.leader.dirt = 90
    assert first_impression(game, npc) < clean
    game.leader.dirt = 0
    npc.traits = ["suspicious", "gruff"]
    assert first_impression(game, npc) < clean


def test_walking_into_someone_starts_a_conversation(game):
    at_noon(game)
    s = visit(game, "village")
    lm = game.local
    npc = next(n for n in npcs_in(game.world, s.id) if n.present)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        x, y = npc.x + dx, npc.y + dy
        if lm.in_bounds(x, y) and game.tables.terrain.walk[game.remap_for(lm)[lm.terrain[x, y]]] \
                and npc_at(game, x, y) is None:
            game.player.lx, game.player.ly = x, y
            t = game.world.time
            game.move(-dx, -dy)
            assert game.talk_to == npc.id and (game.player.lx, game.player.ly) == (x, y)
            return
    pytest.skip("nowhere to stand beside them")


def test_a_conversation_menu_and_its_answers(game):
    at_noon(game)
    s = visit(game, "town")
    npc = next(n for n in npcs_in(game.world, s.id) if n.job == "innkeeper")
    conv = Conversation(game, npc)
    assert npc.met and conv.lines and any(who == "npc" for who, _ in conv.lines)
    labels = {c.id for c in conv.menu()}
    assert {"who", "place", "rumours", "ask_person", "threaten", "offer_bribe", "goodbye"} <= labels
    for cid in ("who", "place", "rumours", "who"):
        choice = next(c for c in conv.menu() if c.id == cid)
        conv.choose(choice)
    assert npc.known
    conv.choose(next(c for c in conv.menu() if c.id == "ask_person"))
    person = next(c for c in conv.menu() if c.id == "person")
    conv.choose(person)
    assert game.world.npcs[person.data["other"]].known
    # Rumours once a day.
    lines = len(conv.lines)
    conv.choose(next(c for c in conv.menu() if c.id == "rumours"))
    assert any("\"" in t for _, t in conv.lines[lines:])
    conv.choose(next(c for c in conv.menu() if c.id == "goodbye"))
    assert conv.ended


def test_special_options_resolve_to_whitelisted_outcomes(game):
    at_noon(game)
    s = visit(game, "town")
    for npc in npcs_in(game.world, s.id):
        if npc.job == "guard":
            continue
        conv = Conversation(game, npc)
        specials = [c for c in conv.menu() if c.id == "special"]
        for c in specials:
            conv.choose(c)
        assert all(opt["used"] for opt in conv.special)
        if game.busy:
            break


def test_threats_are_remembered(game):
    at_noon(game)
    s = visit(game, "town")
    npc = next(n for n in npcs_in(game.world, s.id) if n.job == "weaver" or n.job == "farmer" or n.job == "labourer")
    conv = Conversation(game, npc)
    before = npc.disposition
    conv.choose(next(c for c in conv.menu() if c.id == "threaten"))
    assert npc.disposition < before and any("threatened" in m for m in npc.memory)


def test_bribes(game):
    at_noon(game)
    s = visit(game, "town")
    npc = next(n for n in npcs_in(game.world, s.id) if n.job in ("farmer", "labourer", "weaver", "carter", "beggar",
                                                                   "washerwoman", "fisher"))
    npc.traits = ["greedy", "weary"]
    game.leader.money = 5000
    conv = Conversation(game, npc)
    before = npc.disposition
    conv.choose(next(c for c in conv.menu() if c.id == "offer_bribe"))
    conv.choose(next(c for c in conv.menu() if c.id == "bribe" and c.data["amount"] == 1000))
    assert npc.disposition > before and game.leader.money == 4000


def test_fighting_townsfolk_has_consequences(game):
    from realmwalker.game.fight import finish_battle

    at_noon(game)
    s = visit(game, "town")
    npc = next(n for n in npcs_in(game.world, s.id) if n.job == "labourer" or n.job == "farmer")
    conv = Conversation(game, npc)
    conv.start_fight()
    assert game.battle is not None and game.battle_npcs
    for f in game.battle.side("foe"):
        f.state = "dead"
        f.creature.alive = False
    game.battle._check_end()
    finish_battle(game)
    assert not npc.alive and any(npc.name in d for d in game.leader.deeds)


def test_people_survive_saving(game, tmp_path):
    at_noon(game)
    s = visit(game, "city")
    npc = next(n for n in npcs_in(game.world, s.id) if n.notable)
    npc.disposition = 42
    npc.remember("was bought a drink by the traveller")
    npc.known = True
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    again = loaded.world.npcs[npc.id]
    assert again.to_dict() == npc.to_dict()
    assert loaded.world.towns[s.id].npcs == game.world.towns[s.id].npcs


def test_a_name_goes_before_you(game):
    """Fame and infamy change how a stranger takes you: notables hear more, and sooner."""
    from realmwalker.game.people import fame_impression, first_impression, npcs_in

    s = next(x for x in game.world.settlements if x.kind in ("town", "city"))
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    npc = next(n for n in npcs_in(game.world, s.id) if n.notable)
    plain = first_impression(game, npc)
    game.renown.fame = 30
    famous = first_impression(game, npc)
    assert famous > plain
    game.renown.fame = 0
    game.renown.infamy = 30
    hated = first_impression(game, npc)
    assert hated < plain
    ordinary = next(n for n in npcs_in(game.world, s.id) if not n.notable)
    assert abs(fame_impression(game, ordinary)) <= abs(fame_impression(game, npc))


def test_a_town_has_street_life(game):
    """Walking a town's streets shows small things: idle life by day and night, and what it is going through."""
    from realmwalker.game.people import town_moment

    s = next(x for x in game.world.settlements if x.kind in ("town", "city"))
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    seen = set()
    for i in range(40):
        game.player.steps += 1
        game.world.time += 7
        line = town_moment(game, s)
        assert line and "{" not in line
        seen.add(line)
    assert len(seen) > 3, seen
    s.status["plague"] = {"until": 10**9}
    plague = {town_moment(game, s) for _ in range(40) if (setattr(game.player, "steps", game.player.steps + 1)
                                                         or True)}
    assert any("chalk" in line or "dead-cart" in line or "herbs" in line for line in plague), plague


def test_someone_who_hates_you_will_not_gossip(game):
    """A hostile person answers questions about the town and its people with a closed door."""
    s = visit(game, "town")
    npc = next(n for n in npcs_in(game.world, s.id) if n.alive and n.job != "guard")
    other = next(n for n in npcs_in(game.world, s.id) if n.alive and n is not npc)
    conv = Conversation(game, npc)  # meeting someone sets their first impression, so sour it afterwards
    npc.disposition = -90
    assert npc.mood() == "hostile"
    conv.rumours()
    said = " ".join(t for _, t in conv.lines)
    assert any(line.strip('"').split(".")[0] in said for line in game.tables.dialogue["refuse_talk"])
    before = len(conv.lines)
    conv.about_person(other)
    assert len(conv.lines) == before + 2, "one question, one refusal"


def test_a_shop_door_after_dark_says_it_is_shut(game):
    """Push a trade's door open at night and a voice answers through it."""
    s = visit(game, "town")
    lm = game.local
    trade = next((b for b in lm.buildings if b.kind in ("store", "smithy", "inn")), None)
    if trade is None:
        pytest.skip("no trades in this town")
    game.world.time += (23 - game.moment.hour) * 60  # on towards eleven at night
    before = len(game.log.messages)
    game._shut_for_the_night(lm, trade.x + trade.w // 2, trade.y + trade.h // 2)
    said = " ".join(m.text for m in game.log.messages[before:])
    assert "shut" in said.lower() or "closed" in said.lower()
    game.world.time += 12 * 60  # and on to eleven in the morning
    before = len(game.log.messages)
    game._shut_for_the_night(lm, trade.x + trade.w // 2, trade.y + trade.h // 2)
    assert len(game.log.messages) == before, "by day the door just opens"


def test_people_greet_you_out_of_their_trade_and_not_all_alike(game):
    """A smith does not open with the same words as a beggar, and a town is not four sentences."""
    s = visit(game, "town")
    folk = [n for n in npcs_in(game.world, s.id) if n.alive]
    said = set()
    for npc in folk:
        for _ in range(4):
            npc.flags.pop("greeted", None)
            conv = Conversation(game, npc)
            said.update(t for kind, t in conv.lines if kind == "npc")
    assert len(said) >= 20, f"a town should not run out of words this fast: {len(said)}"
    trades = game.tables.dialogue["greeting_job"]
    jobs = {n.job for n in folk} & set(trades)
    assert jobs, "somebody in a town has a trade"
    assert any(line in said for job in jobs for line in trades[job]), "and it shows in how they say hello"


def test_walking_into_an_inn_says_what_the_room_is_like(game):
    """The tavern writing has been in the data since the first week; walking in now shows it, once."""
    s = visit(game, "town")
    lm = game.local
    inns = [(i, b) for i, b in enumerate(lm.buildings) if b.kind == "inn"]
    if not inns:
        pytest.skip("no inn in this town")
    bi, inn = inns[0]
    before = len(game.log.messages)
    game.player.lx, game.player.ly = inn.x + inn.w // 2, inn.y + inn.h // 2
    game._walk_in(lm, inn)
    said = [m.text for m in game.log.messages[before:]]
    assert said, "the common room is worth a look"
    assert len(said[0]) > 80, f"and more than a line of it: {said[0]}"
    assert "{" not in said[0], f"every slot is filled: {said[0]}"
    again = len(game.log.messages)
    game._walk_in(lm, inn)
    assert len(game.log.messages) == again, "but only the first time you push the door open"
    town = game.world.towns[s.id]
    kept = town.flags["taprooms"][str(bi)]
    assert kept in said[0], "and what it said is kept in the save"
