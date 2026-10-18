"""Schools & Domains Part E on the screens: the Spells page's hat spells and the ring, the battle screen's hat
menu, and the pack's list of a robe's patches."""

import copy

from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from tests.test_gear import person, tables, world  # noqa: F401 (fixtures)
from tests.test_wizard_wonders import give, make


def _app(make_app, world, cls="wizard"):
    from realmwalker.game.state import new_game

    app = make_app()
    c = person(app.tables, cls, bg="sage")
    game = new_game(copy.deepcopy(world), app.tables, c)
    app.start_game(game)
    game.survival = False
    return app, game, c


def test_the_spells_page_reaches_into_a_hat_and_casts_into_a_ring(make_app, world):
    import tcod.console

    from realmwalker.rules import hats
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.spells import SpellsScreen

    app, game, c = _app(make_app, world)
    hat = give(c, make(game, "hat_of_wizardry"))
    ring = give(c, make(game, "ring_of_spell_storing"))
    ring.magic["props"] = [p for p in ring.magic["props"] if not p.get("stored")]
    screen = SpellsScreen(app, game)
    app.push(screen)
    order = screen.spells()
    hat_values = [v for v in order if v.startswith(f"hat:{hat.uid}:")]
    assert hat_values
    screen.sel = order.index(hat_values[0])
    app.render(tcod.console.Console(120, 40, order="F"))
    shown = app.last_canvas.words()
    assert "Out of the hat" in shown and "(Arcana) DC 10" in shown and "Reach into the hat" in shown
    app.handle_event(KeyEvent("enter"))
    assert hats.prop(hat)["spent"] == "long"
    screen.sel = screen.spells().index("magic_missile")
    app.render(tcod.console.Console(120, 40, order="F"))
    assert "Into the ring" in app.last_canvas.words()
    left = spellrules.slots_left(c, app.tables)[0]
    app.handle_event(KeyEvent("r"))
    assert spellrules.slots_left(c, app.tables)[0] == left - 1
    assert [p["spell"] for p in ring.magic["props"] if p.get("stored")] == ["magic_missile"]
    for size in ((80, 30), (160, 45)):
        app.render(tcod.console.Console(*size, order="F"))
    assert app.error_count == 0


def test_the_battle_screen_lists_a_hats_spells(make_app, world):
    import tcod

    from realmwalker.game import fight
    from realmwalker.game.encounters import PendingEncounter
    from realmwalker.rules.creatures import spawn
    from realmwalker.ui import widgets
    from realmwalker.ui.screens.battle import BattleScreen

    app, game, c = _app(make_app, world)
    give(c, make(game, "hat_of_many_spells"))
    rng = RNG(5, "band")
    game.encounter = PendingEncounter("test", [spawn(app.tables, "bandit", rng, i + 1) for i in range(2)],
                                      "They come.", False, "")
    b = fight.encounter_fight(game, False)
    game.encounter = None
    from realmwalker.rules.combat import PARTY

    me = b.side(PARTY)[0]
    screen = BattleScreen(app, game)
    app.push(screen)
    b.order = [me.id] + [i for i in b.order if i != me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    screen.pick_action("cast")
    labels = [r[0] for r in screen.choices]
    i = next(i for i, r in enumerate(screen.choices) if str(r[1]).startswith("hatmenu:"))
    assert "Hat of Many Spells" in labels[i] and screen.choices[i][2]
    screen._click_choice(i)
    assert screen.choice_kind == "hat" and all(str(r[1]).startswith("hat:") for r in screen.choices)
    for size in ((80, 30), (160, 45)):
        screen.render(widgets.Canvas(tcod.console.Console(*size, order="F")))
    assert app.error_count == 0


def test_the_pack_lists_a_robes_patches(make_app, world):
    import tcod

    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.sheets import InventoryScreen

    app, game, c = _app(make_app, world, "fighter")
    robe = give(c, make(game, "robe_of_useful_items"))
    screen = InventoryScreen(app, game)
    app.push(screen)
    items = [screen.current()]
    for _ in range(80):
        if screen.current() is robe:
            break
        app.handle_event(KeyEvent("down"))
    assert screen.current() is robe
    assert screen.action_name(robe) == "Tear off a patch"
    app.handle_event(KeyEvent("enter"))
    menu = app.screens[-1]
    assert type(menu).__name__ == "ContextMenu" and len(menu.entries) >= 6
    before = len(c.inventory)
    menu.choose(0)
    assert len(c.inventory) >= before or c.money > 0
    app.render(tcod.console.Console(120, 40, order="F"))
    assert app.error_count == 0 and items
