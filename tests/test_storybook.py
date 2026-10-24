"""The storybook (Expansion 6 A.5, docs/ADVENTURES.md §7, §9): every tale forged on three test worlds prints as a
synopsis and passes `--check` - every role bound, every place real, every word filled, three routes to every truth,
the content rule and the six rules of a quest that matters."""

import pytest

from realmwalker.world.tables import Tables
from tools import storybook

WORLDS = [("Forgeland", 77, "medium"), ("Threatland", 61, "medium"), ("Lawland", 12, "medium")]


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.mark.slow
@pytest.mark.parametrize("name,seed,size", WORLDS)
def test_storybook_check_passes(tables, name, seed, size):
    made, trouble = storybook.run(seed, size, 4, None, True, quiet=True, tables=tables, name=name)
    if not made and trouble and "no threat here" in trouble[0]:
        pytest.skip(trouble[0])
    assert made, trouble
    assert not trouble, "\n".join(trouble)


def test_a_synopsis_reads_like_the_design(tables):
    game = storybook.make_game(77, "medium", tables, "Forgeland")
    found = storybook.candidates(game)
    if not found:
        pytest.skip("no threat with a tale")
    adv = storybook.forge_once(game, found[0], 0)
    text = storybook.synopsis(game, adv)
    for label in ("Premise", "Hook", "Patron", "Hidden", "Scheme", "Keys", "Endings", "Target", "FINALE"):
        assert label in text, label
    assert "{" not in text
    # (forging for the storybook leaves the world as it was)
    assert not game.world.politics.get("adventures")
    assert found[0].get("adventure") is None
