"""Why people follow you (after v1, asked for by Anton): only your purse is spent, and not everyone who walks with
you does it for a wage. Knights lent by a realm that honours you, farm lads and drunkards told about your work,
people talked into leaving home, the homeless, and those who have heard your name."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import companions as comp
from realmwalker.game import save
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Fellowland", 21, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    g.leader.money = 100000
    return g


def to_town(game, kind="town"):
    s = next(s for s in game.world.settlements if s.kind == kind)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return s


def hire_one(game, kind="city"):
    s = to_town(game, kind)
    t = [n for n in npcs_in(game.world, s.id) if n.flags.get("recruit") and n.alive and not n.flags.get("companion")]
    if not t:
        pytest.skip("no traveller at this inn")
    npc = t[0]
    npc.disposition, npc.met = 20, True
    assert "joins you" in comp.hire(game, npc)[0]
    return game.party[-1], npc, s


# ---------------------------------------------------------------------------- one purse
def test_companions_carry_no_purse(game):
    c, npc, s = hire_one(game)
    assert c.money == 0, "a new companion brings no coin of their own for you to spend"
    before = game.leader.money
    comp.daily(game)
    assert c.money == 0 and game.leader.money == before - c.companion["wage"]
    assert comp.pay_word(game, c).endswith("a day")


def test_an_older_saves_companion_coin_is_yours(game, tmp_path):
    c, npc, s = hire_one(game)
    c.money = 750  # as a companion from before carried it
    before = game.leader.money
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    assert loaded.leader.money == before + 750
    assert all(m.money == 0 for m in loaded.party[1:])


def test_the_party_screen_shows_no_companion_purse(make_app, world):
    import tcod.console

    from realmwalker.ui.screens.party import PartyScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    game.leader.money = 100000
    app.start_game(game)
    c, npc, s = hire_one(game)
    screen = PartyScreen(app, game)
    screen.sel = 1
    app.push(screen)
    con = tcod.console.Console(120, 40, order="F")
    app.render(con)
    text = "\n".join("".join(chr(ch) for ch in con.rgb["ch"][:, y]) for y in range(con.height))
    assert "Money" not in text.split(c.name.split()[0], 1)[1], "a companion has no money line"
    assert app.error_count == 0


def member(tables, cls, seed):
    b = CharacterBuilder(tables, RNG(seed, "member"))
    b.set_class(cls)
    return b.build()
