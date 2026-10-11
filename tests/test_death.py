"""Death and legacy (M9): the obituary, what the world keeps of a dead character, companions set free, and the
weeks that pass before the next life begins."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import companions, death, interlude, save
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.world import politics
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Graveland", 23, "small"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def a_town(game):
    return next(s for s in game.world.settlements if s.kind in ("town", "city"))


def kill_the_leader(game, cause="killed by wolves"):
    game.leader.alive = False
    game.leader.hp = 0
    game.over = {"cause": cause, "place": "the open road"}


# ---------------------------------------------------------------------------- the record
def test_a_death_is_written_into_the_world(game):
    game.leader.deeds.append("burned a bandit camp")
    game.leader.kills["wolf"] = 3
    game.renown.fame = 20
    kill_the_leader(game)
    record = death.die(game)
    assert record in death.fallen(game.world)
    assert record["name"] == game.leader.name and record["cause"] == "killed by wolves"
    assert record["kills"]["wolf"] == 3 and "burned a bandit camp" in record["deeds"]
    assert any(e.get("player") and game.leader.name in e["text"] for e in game.world.history)
    assert any(n.get("player") and game.leader.name in n["text"] for n in game.world.news)
    assert death.die(game) is record  # writing it twice changes nothing


def test_an_unknown_death_goes_unremarked(game):
    game.renown.fame = 0
    game.renown.infamy = 0
    game.leader.level = 1
    news_before = len(game.world.news)
    kill_the_leader(game, "of fever")
    death.die(game)
    assert len(game.world.news) == news_before


def test_companions_go_home_and_can_be_hired_again(game):
    s = a_town(game)
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    folk = [n for n in npcs_in(game.world, s.id) if n.flags.get("recruit")]
    if not folk:
        pytest.skip("nobody for hire in this town")
    npc = folk[0]
    npc.met, npc.disposition = True, 20
    game.leader.money = 100000
    companions.hire(game, npc)
    assert len(game.party) == 2 and npc.flags.get("companion")
    kill_the_leader(game)
    death.die(game)
    assert len(game.party) == 1 and not game.waiting
    assert npc.alive and npc.present and npc.flags.get("recruit") and not npc.flags.get("companion")
    assert any(game.leader.name in m for m in npc.memory)


def test_the_obituary_says_what_they_were(game):
    game.leader.deeds.append("hanged the captain of the Grey Dogs")
    game.leader.kills["bandit"] = 4
    game.renown.standing[next(iter(game.world.factions))] = 40
    kill_the_leader(game, "of a wound that festered")
    record = death.die(game)
    lines = death.fallback_obituary(game, record)
    text = "\n".join(lines)
    assert game.leader.name in text and "festered" in text and "4 bandits" in text
    assert "hanged the captain" in text
    first = game.leader.name.split()[0]
    assert first in record["obituary"] and "{" not in record["obituary"]
    assert record["obituary"] in text  # the built-in words are on the death screen


def test_obituaries_vary(game):
    """Many deaths, many different words: the opening and closing are not always the same."""
    seen = set()
    for i in range(12):
        record = {"id": f"x/{i}", "day": i, "name": f"Wat {i}", "race": game.leader.race, "cls": game.leader.cls,
                  "age": 20 + i, "days_lived": i * 40, "place": "Ashfell", "year": 1200, "kills": {"wolf": i},
                  "deeds": ["burned a barn"] if i % 2 else [], "fame": i * 2, "infamy": 0}
        seen.add(death.write_obituary(game, record).split(".")[0])
    assert len(seen) >= 6


def test_the_dead_are_saved_with_the_world(game, tmp_path):
    kill_the_leader(game)
    death.die(game)
    save.save_game(game, tmp_path)
    loaded_world = save.load_world(tmp_path / game.world.meta.id)
    assert death.fallen(loaded_world)[-1]["name"] == game.leader.name


# ---------------------------------------------------------------------------- the years between
def test_a_world_that_has_been_lived_in_moves_on(game):
    politics.tick(game.world, game.tables)  # a world that has been played has a last tick
    assert interlude.should_pass(game.world)
    before_time = game.world.time
    summary = interlude.pass_the_years(game.world, game.tables, RNG(4, "gap"), days=120)
    assert game.world.time == before_time + 120 * 1440
    assert summary["days"] == 120
    assert isinstance(summary["lines"], list) and len(summary["lines"]) <= interlude.MAX_LINES
    text = "\n".join(interlude.summary_text(game.world, game.tables, summary))
    assert "months" in text or "days" in text
    assert "{" not in text


def test_the_summary_names_what_changed(game):
    w = game.world
    before = interlude.snapshot(w)
    s = next(s for s in w.settlements if s.owner >= 0)
    others = [f for f in w.factions.values() if f.id != s.owner and f.active]
    if not others:
        pytest.skip("only one power in this world")
    s.owner = others[0].id
    s.status["plague"] = {"until": 10**6}
    after = interlude.snapshot(w)
    lines = interlude.changes(w, game.tables, before, after)
    assert any(s.name in line and others[0].name in line for line in lines)
    assert any("Plague" in line and s.name in line for line in lines)


def test_a_new_character_is_told_about_the_world(game):
    kill_the_leader(game)
    record = death.die(game)
    politics.tick(game.world, game.tables)
    summary = interlude.pass_the_years(game.world, game.tables, RNG(9, "gap"), days=60)
    text = "\n".join(interlude.summary_text(game.world, game.tables, summary))
    assert record["name"] in text  # the one who came before is remembered


def test_those_who_came_before_are_in_the_chronicle(game, tmp_path):
    """The next character can read about the one before, in the same book as the old legends."""
    from realmwalker.ui.screens.chronicle import ChronicleScreen

    game.leader.kills["wolf"] = 2
    kill_the_leader(game, "of a wound that festered")
    record = death.die(game)

    class FakeApp:
        def __init__(self):
            self.error_count = 0

    screen = ChronicleScreen(FakeApp(), game, tab=2)
    screen.build(2)
    text = screen.views[2].text if hasattr(screen.views[2], "text") else ""
    assert record["name"] in text and "festered" in text and record["obituary"][:30] in text


def test_your_past_lives_are_in_the_legends_book(game):
    """As Dwarf Fortress keeps its adventurers among the figures of its Legends: a dead character of yours has a page,
    first among the People, with what the world kept of them."""
    from realmwalker.world import legends

    game.leader.deeds.append("burned a bandit camp")
    game.leader.kills["wolf"] = 3
    game.leader.kills["goblin boss"] = 2
    game.renown.fame = 20
    kill_the_leader(game)
    record = death.die(game)
    w, t = game.world, game.tables
    ref, label = legends.entries(w, t, "people")[0]
    assert ref == "P0" and game.leader.name in label and "your life" in label
    title, lines = legends.page(w, t, ref)
    text = "\n".join(legends.plain(line) for line in lines)
    assert title == game.leader.name
    assert "One of your lives" in text and "killed by wolves" in text
    assert "3 wolves" in text and "2 goblin bosses" in text and "burned a bandit camp" in text
    assert record["obituary"][:40] in text
    assert "What the world remembers" in text  # their death went into the history (fame 20)
    assert legends.entries(w, t, "people", game.leader.name.lower())[0][0] == "P0"
