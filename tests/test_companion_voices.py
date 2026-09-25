"""Companions with more to say (after v1): the right pronouns, a voice that fits what they care about, and words
for the cold and the heat."""

import copy
import re

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import companions as comp
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Voiceland", 41, "small"), tables).generate()


@pytest.fixture
def party(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    game.leader.money = 10 ** 5
    for s in game.world.settlements:
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        for npc in npcs_in(game.world, s.id):
            if npc.flags.get("recruit") and not npc.flags.get("companion") and len(game.party) < 3:
                npc.disposition, npc.met = 30, True
                comp.hire(game, npc)
        if len(game.party) >= 3:
            break
    if len(game.party) < 2:
        pytest.skip("nobody to hire")
    return game


def test_every_line_fills_for_a_man_and_a_woman(tables, party):
    c = party.party[1]
    for sex in ("male", "female"):
        c.sex = sex
        for kind, lines in tables.companions["lines"].items():
            for i, text in enumerate(lines):
                from realmwalker.core import textgen

                out = textgen.fill(text, RNG(i, kind), {}, {"name": "Wat", "leader": "Ann", **textgen.pronoun_values(sex)})
                assert "{" not in out, out
                if sex == "female":
                    assert not re.search(r"\b(his|him|himself)\b", out) or "his word" in out, out


def test_a_companion_is_he_or_she_not_they(party):
    c = party.party[1]
    said = {comp.line(party, "desert", c, RNG(i, "d")) for i in range(40)}
    pronoun = "She" if c.sex == "female" else "He"
    assert any(f"{pronoun} " in t for t in said), said
    assert not any("They did not go" in t for t in said)


def test_what_they_care_about_colours_what_they_say(party):
    c = party.party[1]
    value = c.companion["values"][0]
    own = set(party.tables.companions["lines"][f"road_{value}"])
    said = [comp.line(party, "road", c, RNG(i, "r")) for i in range(80)]
    from realmwalker.core import textgen

    filled = {textgen.fill(t, RNG(0), {}, {"name": c.name.split()[0], "leader": party.leader.name.split()[0],
                                           **textgen.pronoun_values(c.sex)}) for t in own}
    assert 10 <= sum(1 for t in said if t in filled) <= 60, "about four in ten road lines are in their own voice"


def test_they_judge_you_by_what_they_care_about(party):
    c = party.party[1]
    value = c.companion["values"][0]
    hated = party.tables.companions["values"][value]["hates"]
    if not hated:
        pytest.skip("this companion hates nothing")
    own = party.tables.companions["lines"][f"disapprove_{value}"]
    hits = 0
    for i in range(30):
        party.world.time += 7
        msgs = comp.react(party, hated[0])
        if msgs and any(o.split("{")[0][:12] in msgs[0] or o[-12:] in msgs[0] for o in own):
            hits += 1
    assert hits >= 10, hits


def test_the_cold_and_the_heat_get_their_own_words(party, monkeypatch):
    from realmwalker.world.weather import Weather

    party.leave_local()
    for temp, kind, lines in ((-8.0, "clear", "road_cold"), (33.0, "heat", "road_hot")):
        monkeypatch.setattr(type(party), "weather", property(lambda self, t=temp, k=kind: Weather(k, t, 5.0, 0.0, 0.0, 1.0)))
        monkeypatch.setattr(type(party), "light", property(lambda self: 1.0))
        heard = set()
        for c in party.party[1:]:
            c.fatigue = 0.0
            c.exhaustion = 0
            c.body_heat = 0.0
        for step in range(400):
            party.player.steps += 30
            before = len(party.log.messages)
            comp.road_talk(party)
            heard |= {m.text for m in party.log.messages[before:]}
        pool = set()
        from realmwalker.core import textgen

        for c in party.party[1:]:
            for t in party.tables.companions["lines"][lines]:
                pool.add(textgen.fill(t, RNG(0), {}, {"name": c.name.split()[0], "leader": party.leader.name.split()[0],
                                                      **textgen.pronoun_values(c.sex)}))
        assert heard & pool, f"nobody remarks on the {lines[5:]}"
