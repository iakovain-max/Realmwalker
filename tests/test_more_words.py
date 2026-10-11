"""More words where they are read most (after v1): after a fight, in every wound, entering a land, meeting a
tradesman, looking at a stranger, and hearing a traveller's story. Floors, not targets."""

import pytest
from tests.worlds import cached_world  # noqa: E402


def test_the_end_of_a_fight_is_told_many_ways(data):
    after = data["combat_text.json"]["aftermath"]
    assert len(after["victory"]) >= 10
    for kind in ("fled", "parley", "robbed"):
        assert len(after[kind]) >= 4, kind


def test_every_wound_has_five_ways_to_look(data):
    for kind, by_severity in data["combat_text.json"]["wound"].items():
        for sev, lines in by_severity.items():
            assert len(set(lines)) >= 5, f"a {kind} wound of severity {sev}"


def test_every_land_has_several_faces(data):
    for biome, spec in data["biomes.json"]["biomes"].items():
        assert len(spec["descriptions"]) >= 5, biome


def test_every_trade_greets_you_three_ways_or_more(data):
    for job, lines in data["dialogue.json"]["greeting_job"].items():
        assert len(lines) >= 3, job


def test_strangers_are_described_in_more_than_two_shapes(data):
    assert len(data["people.json"]["text"]["appearance"]) >= 5
    for arch, spec in data["companions.json"]["archetypes"].items():
        assert len(spec["story"]) >= 3, arch


@pytest.mark.slow
@pytest.mark.parametrize("dead", [1, 3])
def test_the_dead_take_the_right_verb(data, dead):
    """"The wolf lies still", "Three wolves lie still" (it used to be "The wolf lie still")."""
    import copy

    from realmwalker.core.rng import RNG
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter
    from realmwalker.game.state import new_game
    from realmwalker.rules.combat import FOE
    from realmwalker.world.generator import WorldOptions
    from realmwalker.world.tables import Tables

    tables = Tables(data)
    world = cached_world(WorldOptions("Verbland", 6, "small"), tables)
    seen = set()
    for seed in range(40):
        game = new_game(copy.deepcopy(world), tables)
        game.survival = False
        game.world.time += seed * 97  # a different fight each time
        game.encounter = make_encounter(game, "wolf_pack", RNG(seed, "v"))
        game.encounter.creatures = game.encounter.creatures[:dead] * (1 if len(game.encounter.creatures) >= dead else 3)
        game.encounter.creatures = game.encounter.creatures[:dead]
        b = fight.encounter_fight(game, False)
        game.encounter = None
        for f in b.side(FOE):
            f.hp = 0
            f.state = "dead"
        b.outcome = "victory"
        after = fight.finish_battle(game)
        seen.add(after.text)
        words = after.text.split()
        for bad in (("lie", "still"), ("are", "down"), ("are", "finished")):
            if dead == 1:
                assert " ".join(bad) not in after.text, after.text
        if "lies" in words:
            assert dead == 1, after.text
        assert "on the pine forest" not in after.text and "on the forest" not in after.text
    assert len(seen) >= 5
