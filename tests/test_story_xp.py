"""Experience from stories (Expansion 6 C.8, docs/ADVENTURES.md §8.10): a story's end is worth a share of the encounter
budget for the party's levels, more when no blood was shed; the Experience setting can make fights give none (the
DMG's milestones), and then stories give twice as much."""

import pytest

from realmwalker.game import fight, townlife
from realmwalker.game.encounters import make_encounter
from realmwalker.game.story import check, experience, situations
from realmwalker.rules.combat import FOE
from realmwalker.world.tables import Tables
from tests.test_first_hour import SEEDS, a_life
from tests.test_situations import forced, talk
from tests.test_story_hooks import _start_near_a_beast, made  # noqa: F401 (a fixture)


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture
def life(tables):
    townlife.forget()
    return a_life(tables, SEEDS[0])


def won_fight(game):
    enc = make_encounter(game, "bandits", game.world.rng.child("story_xp/fight"))
    battle = fight.start_battle(game, enc.creatures, enc.intro, title="Bandits")
    for f in battle.fighters:
        if f.side == FOE:
            f.hp, f.state = 0, "dead"
    battle.outcome = "victory"
    xp = game.leader.xp
    fight.finish_battle(game)
    return game.leader.xp - xp


def test_the_data_reads_right(tables):
    assert check.problems(tables) == []
    assert set(tables.situations["experience"]["sizes"]) >= {"small", "fair", "great", "chapter", "finale"}


def test_a_bigger_end_is_worth_more_and_blood_less(life):
    game, _ = life
    small, fair, great = (experience.amount(game, s) for s in ("small", "fair", "great"))
    assert 0 < small < fair < great
    assert experience.amount(game, "fair", no_fight=True) > fair, "a way through without a fight is worth more"
    assert experience.amount(game, "chapter") > great, "a chapter of a tale is a high budget"


def test_a_trouble_seen_through_gives_experience(life):
    game, town = life
    sit = forced(game, town, "promise_unkept")
    situations.met(game, sit)
    talk(game, situations.asker(game, sit), "sit_take")
    game.leader.money = 10000
    xp = game.leader.xp
    talk(game, situations._npc(game, sit, "creditor"), "sit_act", act="pay")
    assert sit["ending"] == "kept_paid"
    assert game.leader.xp - xp == experience.amount(game, "small", no_fight=True)


def test_stories_only_fights_give_none_and_stories_twice(life):
    game, town = life
    assert won_fight(game) > 0, "by default a fight won is worth experience"
    both = experience.amount(game, "fair")
    game.experience = "stories"
    assert abs(experience.amount(game, "fair") - 2 * both) <= 1
    game.aftermath = None  # (the first fight's aftermath screen, read and closed)
    assert game.battle is None and game.over is None
    assert won_fight(game) == 0, "stories only: no experience from fights"


def test_the_setting_is_copied_onto_the_game(life, make_app):
    from realmwalker.ui.screens.game_screen import GameScreen
    from realmwalker.ui.screens.settings_screen import SettingsScreen

    game, _ = life
    app = make_app()
    screen = SettingsScreen(app)
    opt = next(o for o in screen.options if o.label == "Experience")
    assert opt.value() == "Fights and stories"
    opt.change(1)
    assert app.settings.experience == "stories" and opt.value() == "Stories only"
    GameScreen(app, game).update()
    assert game.experience == "stories"


def test_a_chapter_behind_you_pays_once(made, tables):
    from realmwalker.game import story
    from realmwalker.game.story import forge

    game, t = _start_near_a_beast(made, tables)
    adv = forge.make(game, t)
    adv["chapter"] = len(adv["chapters"]) - 1  # (the last chapter stays the current one when it is done)
    ch = story.chapter(adv)
    ch["state"] = "open"
    for st in ch["steps"]:
        st["state"] = "done"
    want = experience.amount(game, "chapter")
    xp = game.leader.xp
    story._chapter_check(game, adv)
    story._chapter_check(game, adv)
    assert ch["state"] == "done" and game.leader.xp - xp == want
