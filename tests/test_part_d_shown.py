"""Part D, shown (Expansion 6 D.5): the Risen's dead stand at the edge of the camp's light; the outlaws' hideout and the
halls under a barrow have pictures of their own (a beat met there, the captive's opening); a foe a tale wants alive is
knocked out on Auto; a tale's master who beats you is still at home when you come back."""

import tcod.console

import pytest

from realmwalker.game import camp, fight, story
from realmwalker.game.story import beats, deeds, places, villain
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.ui.gfx import headless, scenes, vignette
from realmwalker.ui.gfx.scene import Sprite
from realmwalker.ui.screens.beat import backdrop_for
from realmwalker.ui.widgets import Canvas
from tests.test_risen_outlaw import _open_chapter, _step, _tale, _to_level, made, tables  # noqa: F401

pytestmark = pytest.mark.story


def _camp_sprites(game) -> set[str]:
    canvas = Canvas(tcod.console.Console(80, 30, order="F"), gfx=headless())
    scenes.camp(canvas, game, (0, 0, 640, 300), 1.0)
    return {c.name for layer in canvas.layers for c in layer.under if isinstance(c, Sprite)}


def test_the_dead_stand_at_the_edge_of_the_camps_light(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    camp.make_camp(game)
    assert "creature/wight" not in _camp_sprites(game)
    monkeypatch.setattr(villain, "due_move", lambda game, adv, where: "risen_at_camp")
    assert story.on_night(game, "camp") and beats.pending(game)["beat"] == "risen_at_camp"
    assert story.left_at_camp(game) == "dead"
    drawn = _camp_sprites(game)
    assert {"creature/wight", "creature/zombie", "creature/skeleton"} <= drawn, "a ring of the dead round the fire"
    camp.break_camp(game)
    assert story.left_at_camp(game) is None


def test_the_hideout_and_the_barrow_hall_have_their_pictures(made, tables):
    for kind in ("hideout", "barrow_hall"):
        canvas = Canvas(tcod.console.Console(80, 30, order="F"), gfx=headless())
        assert vignette.compose(canvas, (0, 0, 600, 200), {"backdrop": kind, "time": "night"}, 1.0, None)
    game, adv, t = _tale(made, tables, "outlaw")
    home = adv["places"]["home"]
    assert vignette.is_hideout(game.world, home["site"])
    assert vignette.for_place(game, home) == "hideout", "the gang's camp, not the old stones it sits in"
    assert backdrop_for(game, game.tables.beats["opening_captive"]["picture"]) == "hideout"
    _to_level(game, home, 1)
    assert backdrop_for(game, "here") == "hideout"
    game, adv, t = _tale(made, tables, "risen")
    _to_level(game, adv["places"]["home"], 1)
    assert backdrop_for(game, "here") == "barrow_hall", "under the mound: its halls, not the heath above"
    assert vignette.for_place(game, adv["places"]["home"]) == "barrow"


def test_the_one_wanted_alive_is_knocked_out_on_auto(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    st = _step(adv, "capture")
    creatures = deeds.band(game, adv, st, st["target"]["role"], st["target"]["group"], game.world.rng.child("t"))
    assert creatures[0].story["alive"] and not any(c.story.get("alive") for c in creatures[1:])
    fight.start_battle(game, creatures, "They are here.")
    b = game.battle
    hero = next(f for f in b.side(PARTY))
    hero.auto = True
    wanted = next(f for f in b.side(FOE) if f.creature is creatures[0])
    other = next((f for f in b.side(FOE) if f.creature is not creatures[0] and f.kind == "humanoid"), None)
    b._melee_blow = True
    assert b._knock_out(hero, wanted) and wanted.state == "surrendered", "taken alive, a prisoner"
    if other is not None:
        assert not b._knock_out(hero, other), "the rest the Auto kills, as before"


def test_the_master_who_beats_you_is_still_at_home(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    _open_chapter(game, adv, len(adv["chapters"]) - 1)
    _to_level(game, adv["places"]["home"])
    band = next(a for a in game.local.actors if a.creatures and getattr(a.creatures[0], "story", None)
                and a.creatures[0].story.get("role") == "villain")
    assert fight._at_home(game, band)
    other = next((a for a in game.local.actors if a is not band and a.creatures), None)
    if other is not None:
        assert not fight._at_home(game, other)
    assert places.here(game, adv["places"]["home"])


def test_the_autoplay_bot_takes_part_d_steps_and_checks_them(made, tables):
    """The bot's Part D move (tools/autoplay._part_d_move) and invariants (_check_part_d) on a live tale: each kind of
    step it meets is gone to or talked through, and nothing it does breaks the records."""
    import random

    from tools import autoplay

    for kind in ("risen", "outlaw"):
        game, adv, t = _tale(made, tables, kind)
        rng = random.Random(1)
        faults, moved = [], 0
        for n in range(len(adv["chapters"])):
            _open_chapter(game, adv, n)
            for _ in range(6):
                if game.busy:
                    game.encounter = game.battle = None
                    beats.director(game.world)["pending"] = None
                moved += bool(autoplay._part_d_move(game, rng))
                autoplay._check_part_d(game, faults.append)
        assert not faults, faults
        assert moved >= 4, f"the bot found its {kind} steps ({moved} moves)"
