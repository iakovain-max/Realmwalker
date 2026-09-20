"""Dragons and paper (M8 part 4): dragons that wake, burn, take tribute and can be killed for good; and the
books, maps and letters that tell you true things about this world."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import books, dragons, dungeon, quests, treasure
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.rules.creatures import spawn
from realmwalker.rules.inventory import add_existing
from realmwalker.world import dungeon as gen
from realmwalker.world import politics
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Wyrmland", 5, "small"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def a_dragon(game):
    alive = dragons.living(game.world)
    if not alive:
        pytest.skip("no sleeping dragon in this world")
    return alive[0]


def result(outcome="victory", dead=(), captives=()):
    return SimpleNamespace(outcome=outcome, dead=list(dead), captives=list(captives), fled=[], xp=0)


def item(game, def_id):
    return add_existing(game.leader, game.tables.items, treasure.new_item(game, def_id, RNG(1, "book")))


# ---------------------------------------------------------------------------- dragons
def test_every_world_has_dragons_with_lairs(world):
    records = world.politics["dragons"]
    assert records
    for d in records:
        assert d["name"] and d["color"]
        if d["alive"] and d["lair"] >= 0:
            site = world.sites[d["lair"]]
            assert gen.style_for(world, site) == "lair" and gen.depth_for(world, site) == 1


def test_the_land_around_a_lair_warns_you(game):
    d = a_dragon(game)
    lair = game.world.sites[d["lair"]]
    game.player.x, game.player.y = lair.x, lair.y
    assert dragons.near(game) is d
    dragons.arrive(game)
    said = [m.text for m in game.log.messages]
    assert any(d["name"] in text or "bones" in text or "burned" in text for text in said), said
    before = len(game.log.messages)
    dragons.arrive(game)  # the same stretch of country says it once
    assert len(game.log.messages) == before
    game.enter_local()
    dungeon.descend(game, 1)
    assert any(d["name"] in m.text for m in game.log.messages[-4:])
    assert any(a.group == "dragon" for a in game.local.actors)


def test_a_dragon_wakes_and_the_country_pays(game):
    d = a_dragon(game)
    p = politics.Politics(game.world, game.tables, RNG(3, "dragon"), year=politics.year_of(game.world, game.tables))
    burned = tribute = 0
    for i in range(40):
        d["alive"] = True
        before = len(game.world.news)
        p.dragon_wakes(d)
        for s in game.world.settlements:
            if s.status.get("burned") is not None:
                burned += 1
                s.status.pop("burned")
            if s.status.get("tribute"):
                tribute += 1
                s.status.pop("tribute")
        assert len(game.world.news) >= before
    assert burned and tribute
    assert any("dragon" in n["kind"] for n in game.world.news)


def test_killing_a_dragon_is_remembered(game):
    d = a_dragon(game)
    lair = game.world.sites[d["lair"]]
    game.player.x, game.player.y = lair.x, lair.y
    for s in dragons.tribute_towns(game.world, d):
        s.status["tribute"] = d["name"]
    beast = spawn(game.tables, "young_dragon", RNG(1), 1)
    beast.name = d["name"]
    fame = game.renown.fame
    dragons.on_battle(game, result(dead=[beast]))
    assert not d["alive"] and d["slain_by"] == game.leader.name
    assert game.renown.fame > fame
    assert any(e.get("kind") == "dragon_slain" and game.leader.name in e["text"] for e in game.world.history)
    assert not any(s.status.get("tribute") for s in dragons.tribute_towns(game.world, d))
    assert dragons.at_site(game.world, lair) is None


def test_a_lord_pays_for_a_dragons_head(game):
    d = a_dragon(game)
    lair = game.world.sites[d["lair"]]
    for c in game.party:
        c.level = 6
    near = [s for s in game.world.settlements if quests.dist(s, lair) <= 20]
    if not near:
        pytest.skip("nobody lives near this lair")
    for s in near:
        folk = npcs_in(game.world, s.id) or (prepare_town(game, s) and npcs_in(game.world, s.id))
        givers = [n for n in folk if n.job in ("lord", "headman", "priest")]
        for npc in givers:
            q = quests.make_offer(game, npc, game.world.rng.child(f"dq/{npc.id}"), "slay_dragon")
            if q is not None:
                break
        else:
            continue
        break
    else:
        pytest.skip("no one near the lair will pay for it")
    assert q["target"]["dragon"] == d["name"] and q["reward"] >= 30000
    quests.accept(game, q)
    game.player.x, game.player.y = lair.x, lair.y
    game.enter_local()
    lm = dungeon.descend(game, 1) or game.local
    boss = next(a for a in lm.actors if a.group == "dragon")
    lm.actors.remove(boss)
    quests.on_battle(game, result(dead=boss.creatures), boss)
    assert q["done"]
    money = game.leader.money
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert game.leader.money == money + q["reward"]


# ---------------------------------------------------------------------------- books, maps and letters
def test_a_map_puts_places_on_your_map(game):
    it = item(game, "old_map")
    known = int(game.player.explored.sum()) + len(game.player.known_settlements)
    lines = books.read(game, game.leader, it)
    assert lines and "read" in it.tags
    assert int(game.player.explored.sum()) + len(game.player.known_settlements) > known


def test_a_history_book_teaches_you_who_holds_the_land(game):
    it = item(game, "history_book")
    known = set(game.renown.known)
    xp = game.leader.xp
    lines = books.read(game, game.leader, it)
    assert lines
    assert set(game.renown.known) > known or any("year" in line for line in lines)
    assert game.leader.xp > xp
    again = books.read(game, game.leader, it)
    assert again == lines and game.leader.xp == xp + books.XP_FOR_LEARNING  # the same words, and no second lesson


def test_old_lore_names_where_a_treasure_lies(game):
    it = item(game, "lore_book")
    lines = books.read(game, game.leader, it)
    assert lines
    artifacts = [a for a in game.world.politics["artifacts"] if a.get("site", -1) >= 0]
    if artifacts:
        assert any(a["name"] in lines[0] for a in artifacts) or "dragon" in lines[0]
        site = next(game.world.sites[a["site"]] for a in artifacts if a["name"] in lines[0]) if \
            any(a["name"] in lines[0] for a in artifacts) else None
        if site is not None:
            assert game.player.explored[site.x, site.y]


def test_a_dead_strangers_letter(game):
    it = item(game, "found_letter")
    lines = books.read(game, game.leader, it)
    assert lines and ("map now" in lines[0] or "dead" in lines[0])


def test_paper_turns_up_in_treasure(game):
    found = 0
    for i in range(120):
        items, _ = treasure.roll(game, 3, RNG(i, "paper"))
        found += sum(1 for it in items if books.kind_of(game, it))
    assert found > 3


def test_the_dark_says_something_now_and_then(game):
    """Walking a dungeon is not silent: water, draughts, a bone underfoot — but only with a light."""
    from realmwalker.game import dungeon

    site = game.world.sites[0]
    game.player.local_key = None
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    moments = set()
    for key in ("any", lm.meta.get("style", "")):
        moments.update(game.tables.sites["dungeon_moments"].get(key, []))
    assert moments, "a dungeon has things it can say"
    game.lit = None
    said = len(game.log.messages)
    for step in range(60):
        game.player.steps += 1
        game._underground(lm)
    assert len(game.log.messages) == said, "in the dark you see nothing at all"
    game.lit = {"item": "torch", "left": 600.0}
    heard = set()
    for step in range(400):
        game.player.steps += 1
        before = len(game.log.messages)
        game._underground(lm)
        heard.update(m.text for m in game.log.messages[before:])
    assert heard <= moments, f"and what it says comes from the data: {heard - moments}"
    assert len(heard) >= 4, f"in more than one way: {heard}"
