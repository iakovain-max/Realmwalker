"""The past in play (2026-10): what the lived history (world/ages) gives the game.

Ruins say what they were; barrows whose they are; towns when they were founded and what befell them; townsfolk tell
of it; heroes of the history sit in the inns; named beasts wait in their lairs and are remembered when they die; the
dead king in a barrow has his own name; towns pay to be rid of the beast that killed their people; history books
quote the world's own chronicles; the AI is told the truth.
"""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import dungeon, past, quests
from realmwalker.game.describe import describe_overworld
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.rules.creatures import spawn
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Pastland", 33, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def result(dead=()):
    return SimpleNamespace(outcome="victory", dead=list(dead), captives=[], fled=[], xp=0)


def stand_on(game, thing):
    game.player.x, game.player.y = thing.x, thing.y
    game.player.explored[thing.x, thing.y] = True


# ---------------------------------------------------------------------------- places say what they were
def test_ruins_and_barrows_tell_their_past(game):
    w = game.world
    ruins = [s for s in w.sites if s.kind == "ruin" and not w.politics["ruins"][str(s.id)].get("elder")]
    assert ruins
    site = ruins[0]
    stand_on(game, site)
    text = describe_overworld(game, site.x, site.y)
    past_of = w.politics["ruins"][str(site.id)]
    assert "Once" in text and str(past_of["fell"]) in text
    barrows = [s for s in w.sites if str(s.id) in w.politics.get("tombs", {})]
    if barrows:
        stand_on(game, barrows[0])
        fig = w.figures[w.politics["tombs"][str(barrows[0].id)]]
        assert fig.full_name() in describe_overworld(game, barrows[0].x, barrows[0].y)


def test_towns_remember_their_founding_and_their_troubles(game):
    w = game.world
    town = max(w.settlements, key=lambda s: len(past.great_events(game, s, 6)))
    stand_on(game, town)
    text = describe_overworld(game, town.x, town.y)
    assert "Founded in" in text
    assert past.great_events(game, town)
    game.enter_local()
    folk = [n for n in npcs_in(w, town.id) if n.alive and n.job not in ("guard",)]
    said = []
    for npc in folk[:6]:
        npc.disposition = 40
        conv = Conversation(game, npc)
        conv.choose(next(c for c in conv.menu() if c.id == "place"))
        said += [text for _, text in conv.lines]
    assert any(e["text"][:12].lower() in line.lower() for line in said for e in past.great_events(game, town, 6)), \
        said


# ---------------------------------------------------------------------------- the masters of the old places
def a_lair(game):
    for site_id, hid in game.world.politics.get("lairs", {}).items():
        fig = game.world.figures[hid]
        if fig.kind == "beast":
            return game.world.sites[int(site_id)], fig
    pytest.skip("no named beast in this world")


def test_a_named_beast_waits_in_its_lair_and_its_death_is_remembered(game):
    site, beast = a_lair(game)
    stand_on(game, site)
    assert beast.name in past.site_past(game, site)
    game.enter_local()
    dungeon.descend(game, 1)
    deepest = int(game.local.meta.get("depth", 1))
    while int(game.local.meta.get("level", 1)) < deepest:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)
    named = [c for a in game.local.actors for c in a.creatures if getattr(c, "named", False)]
    assert named and named[0].name == past.beast_title(beast), [a.group for a in game.local.actors]
    fame = game.renown.fame
    past.on_battle(game, result(dead=named[:1]))
    assert not beast.alive and str(site.id) not in game.world.politics["lairs"]
    assert game.renown.fame > fame
    assert any(e.get("player") and e["kind"] == "beast_slain" and beast.name in e["text"]
               for e in game.world.history)


def test_the_dead_king_in_the_barrow_has_a_name(game):
    w = game.world
    barrows = [s for s in w.sites if s.kind == "barrow" and str(s.id) in w.politics.get("tombs", {})
               and dungeon.gen.style_for(w, s) == "crypt"]
    if not barrows:
        pytest.skip("no tomb in this world")
    site = barrows[0]
    fig = w.figures[w.politics["tombs"][str(site.id)]]
    group, name = past.boss_for(game, site, "barrow_wight")
    assert group == "barrow_wight" and name == fig.full_name()
    stand_on(game, site)
    wight = spawn(game.tables, "wight", RNG(2), 1)
    wight.name, wight.named = name, True
    past.on_battle(game, result(dead=[wight]))
    assert any(e.get("player") and e["kind"] == "laid_to_rest" for e in w.history)


def test_a_town_pays_to_be_rid_of_the_beast_that_killed_its_people(game):
    w = game.world
    lairs = [(w.sites[int(k)], w.figures[h]) for k, h in w.politics.get("lairs", {}).items()
             if w.figures[h].kind == "beast"]
    near = [s for s in w.settlements if any(3 <= quests.dist(s, site) <= 16 for site, _ in lairs)]
    if not near:
        pytest.skip("nobody lives near a lair")
    for s in near[:6]:
        prepare_town(game, s)
        for npc in npcs_in(w, s.id)[:8]:
            for i in range(8):
                q = quests._clear_lair(game, npc, RNG(i, "lair"))
                if q and q.get("text_key") == "clear_lair_beast":
                    beast = w.figures[q["target"]["beast"]]
                    assert q["words"]["beast"] == past.beast_title(beast)
                    text = quests.pitch(game, q)
                    assert q["words"]["beast"] in text and "{" not in text
                    return
    pytest.skip("no offer came up")


# ---------------------------------------------------------------------------- people of the history
def test_heroes_of_the_history_drink_in_their_home_inns(game):
    w = game.world
    heroes = [f for f in w.figures.values() if f.alive and f.kind == "person" and f.job in ("adventurer", "hero")
              and f.home.startswith("S")]
    if not heroes:
        pytest.skip("no living hero in this world")
    for hero in heroes:
        town = w.settlements[int(hero.home[1:])]
        stand_on(game, town)
        game.enter_local()
        met = [n for n in npcs_in(w, town.id) if n.flags.get("figure") is not None
               and w.figures[n.flags["figure"]].job in ("adventurer", "hero")]
        if met:
            npc = met[0]
            assert npc.flags.get("recruit") and npc.title and npc.profile["backstory"]
            return
        game.leave_local() if hasattr(game, "leave_local") else None
    pytest.skip("no hero lives where there is an inn")


def test_the_ai_is_told_the_truth_about_a_town(game):
    from realmwalker.game.people_ai import dialogue_variables, settlement_variables

    w = game.world
    town = max(w.settlements, key=lambda s: len(past.great_events(game, s, 6)))
    town_people = prepare_town(game, town)
    facts = settlement_variables(game, town, town_people)
    assert "Founded in" in facts["history"]
    npc = next(n for n in npcs_in(w, town.id) if n.notable)
    assert "past (true)" in dialogue_variables(game, npc)["place"]


def test_history_books_quote_the_world_s_own_chronicles(game):
    from realmwalker.game import books

    w = game.world
    assert w.politics.get("works")
    said = []
    for i in range(12):
        said += books._history(game, RNG(i, "book"), True)
    assert any("It is a copy of" in line for line in said)
    assert not any(".." in line for line in said)
