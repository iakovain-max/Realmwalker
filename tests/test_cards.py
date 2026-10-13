"""Cards, status icons and the battle log's rolls (docs/EXPANSIONS.md §4.15, Expansion 1 part E.1): every state a fight
can produce has an icon and card words; every creature and every option produces a card; cards stay inside the window
and off what they describe; pointing at a line of the log shows its roll; the battle board draws the icons."""

import copy

import pytest
import tcod.console

from realmwalker.core.rng import RNG
from realmwalker.rules import describe, tactics
from realmwalker.rules.engine import durations
from realmwalker.ui import tooltips, widgets
from realmwalker.ui.gfx import headless
from realmwalker.world.tables import Tables
from tests.test_combat import battle, foes, hero, hero_at, turn_of
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def test_every_status_and_item_mark_has_an_icon(tables):
    atlas = headless().atlas
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from status_art import STATUS_NAMES

    for sid in describe.STATES + describe.ITEM_MARKS:
        assert sid in STATUS_NAMES, sid
        assert atlas.has(f"status/{sid}"), f"no picture for {sid}: rebuild the tiles"
    assert set(describe.CONDITIONS) == set(tables.conditions["conditions"])


def test_every_condition_has_a_card_with_its_ending(tables):
    b = battle(tables, [hero(tables)], foes(tables, "goblin"))
    me, gob = b.fighters
    for cid in describe.CONDITIONS:
        durations.give(b, me, cid, ends=durations.until(b, gob, "turn_end"), source=gob)
        card = next(s.card for s in describe.statuses(me, b) if s.id == cid)
        assert card.title and card.lines[0], cid
        assert "goblin" in card.text().lower() and "next turn" in card.footer, cid
        durations.remove(me, cid)


def test_the_states_of_a_fight_all_show(tables):
    b = battle(tables, [hero_at(tables, "fighter", 3), hero(tables, "cleric", seed=2)], foes(tables, "goblin", "stirge"))
    me, priest, gob, stirge = b.fighters
    me.z, me.dodging, me.readied, me.temp_hp, me.hidden = 10, True, "reach", 4, 14
    me.marked = True
    me.buffs.append({"attack_die": "1d4", "save_die": "1d4", "rounds": 10, "source": "bless", "conc": priest.id})
    me.buffs.append({"slow": 10, "source": "slow:ray_of_frost"})
    me.buffs.append({"burning": True, "source": "burning"})
    me.char.uses["heroic_inspiration"] = 1
    priest.concentration = {"spell": "bless", "rounds": 9}
    stirge.attached_to = me.id
    gob.grappled_by = priest.id
    me.hp = max(1, me.max_hp // 3)
    ids = [s.id for s in describe.statuses(me, b)]
    for sid in ("flying", "dodging", "readied", "temp_hp", "hidden", "marked", "blessed", "slowed", "burning",
                "heroic", "bloodied"):
        assert sid in ids, sid
    assert ids.index("burning") < ids.index("blessed")  # the worst first
    assert "concentrating" in [s.id for s in describe.statuses(priest, b)]
    assert "grappling" in [s.id for s in describe.statuses(priest, b)]
    assert "attached" in [s.id for s in describe.statuses(stirge, b)]
    blessed = next(s.card for s in describe.statuses(me, b) if s.id == "blessed")
    assert "Bless" in blessed.title and "1d4" in blessed.lines[0] and "concentration" in blessed.text()
    me.hp, me.state, me.death_saves = 0, "down", [1, 2]
    dying = next(s.card for s in describe.statuses(me, b) if s.id == "dying")
    assert "failed 2" in dying.text()


def test_every_creature_and_every_option_has_a_card(tables):
    for cid in sorted(tables.creatures.defs):
        b = battle(tables, [hero_at(tables, "wizard", 3)], foes(tables, cid))
        me, it = b.fighters[0], b.fighters[-1]
        card = describe.creature(b, it, full=True)
        assert card.title and any("AC" in x for x in card.lines), cid
        assert len(card.lines) <= describe.MAX_LINES
        short = describe.creature(b, it, full=False)
        assert not any("AC " in x for x in short.lines) and "Study" in short.footer, cid
        assert describe.creature(b, me).lines
    b = battle(tables, [hero_at(tables, "wizard", 3)], foes(tables, "goblin"))
    me, gob = b.fighters
    for o in b.attack_options(me):
        card = describe.attack(b, me, o, gob)
        assert "to hit" in card.text(), o.name
    from realmwalker.rules import spells as sprules

    for sid in sprules.known_spells(me.char, tables):
        card = describe.choice(b, me, "cast", sid, sid, True, "", gob)
        assert card.title and "range" in card.text(), sid
    for aid, name, ok, why in b.class_abilities(me):
        assert describe.choice(b, me, "ability", aid, name, ok, why).title


def test_cards_fit_inside_the_window_and_beside_what_they_describe(tables):
    b = battle(tables, [hero_at(tables, "fighter", 3)], foes(tables, "young_dragon"))
    card = describe.creature(b, b.fighters[1], full=True)
    for size in ((80, 30), (120, 45), (192, 54)):
        for rect in ((0, 0, 3, 2), (size[0] - 3, size[1] - 2, 3, 2), (size[0] // 2, size[1] // 2, 4, 2)):
            con = tcod.console.Console(*size, order="F")
            canvas = widgets.Canvas(con, mouse=(rect[0], rect[1]))
            x, y, w, h = tooltips.draw_card(canvas, card, rect)
            assert 0 <= x and x + w <= size[0] and 0 <= y and y + h <= size[1], (size, rect)
            rx, ry, rw, rh = rect
            overlaps = x < rx + rw and rx < x + w and y < ry + rh and ry < y + h
            assert not overlaps, (size, rect, (x, y, w, h))


def test_pointing_at_a_line_of_the_log_shows_its_roll(tables):
    b = battle(tables, [hero_at(tables, "fighter", 3)], foes(tables, "goblin", "goblin"), spots={0: (4, 4), 1: (5, 4), 2: (5, 5)})
    b.show_dice = False
    me = b.fighters[0]
    me.auto = True
    for _ in range(6):
        turn_of(b, me)
        tactics.take_turn(b, me)
        if any(e["kind"] == "attack" and e.get("hit") for e in b.events):
            break
    lines = [i for i in b.rolls if b.log[i][1] != "dice"]
    assert lines, "the attack's lines carry their rolls"
    card = describe.log_line(b, lines[-1])
    assert card is not None and any("vs AC" in x or "damage" in x for x in card.lines)


def test_damage_rolls_say_what_changed_them(tables):
    b = battle(tables, [hero_at(tables, "fighter", 3)], foes(tables, "skeleton"))
    me, bones = b.fighters
    b._hit(me, bones, 10, "bludgeoning", crit=False, weapon="mace")
    n = max(b.rolls)
    assert any("vulnerable: doubled = 20" in r for r in b.rolls[n])


@pytest.fixture
def game(make_app):
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    w = cached_world(WorldOptions("Cardland", 3, "small"), app.tables)
    g = new_game(copy.deepcopy(w), app.tables)
    g.survival = False
    app.start_game(g)
    return app, g


def test_the_battle_board_draws_status_icons_with_their_cards(game):
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter
    from realmwalker.ui.screens.battle import BattleScreen

    app, g = game
    g.encounter = make_encounter(g, "goblins", RNG(3, "cards"))
    b = fight.encounter_fight(g, False)
    g.encounter = None
    me = b.fighters[0]
    me.dodging, me.temp_hp = True, 3
    screen = BattleScreen(app, g)
    con = tcod.console.Console(160, 45, order="F")
    canvas = widgets.Canvas(con)
    screen.render(canvas)
    assert me.id in screen.board.status_px
    names = [st.id for _, st in screen.board.status_px[me.id]]
    assert "dodging" in names and "temp_hp" in names
    (px, py, s, _), st = screen.board.status_px[me.id][0]
    cx, cy = int(px // canvas.cell_w), int(py // canvas.cell_h)
    canvas2 = widgets.Canvas(tcod.console.Console(160, 45, order="F"), mouse=(cx, cy))
    screen.render(canvas2)
    assert canvas2.tip_is_card
    canvas2.draw_tooltip()
    assert any(st.card.title in w for w in canvas2.words().splitlines()) or st.card.title in canvas2.words()


def test_creature_details_setting_hides_what_is_not_known(game):
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter
    from realmwalker.rules.combat import FOE
    from realmwalker.ui.screens.battle import BattleScreen

    app, g = game
    g.encounter = make_encounter(g, "goblins", RNG(3, "cards"))
    b = fight.encounter_fight(g, False)
    g.encounter = None
    screen = BattleScreen(app, g)
    gob = b.side(FOE)[0]
    assert screen.full_details(gob)
    app.settings.creature_details = "known"
    b.known.discard(gob.creature.def_id)
    assert not screen.full_details(gob)
    b.known.add(gob.creature.def_id)
    assert screen.full_details(gob)


def test_a_bound_thing_and_a_sentient_demand_carry_their_marks(game):
    from realmwalker.game import magic_items
    from realmwalker.ui.hud import body_card

    app, g = game
    it = g.leader.inventory[0]
    kind = next(iter(magic_items.data(g)["sentient"]["demands"]))
    it.magic = {"attune": True, "identified": True, "props": [], "sentient": {"demand": {"kind": kind}}}
    g.leader.attuned = [it.uid]
    assert describe.item_marks(g, it) == ["bound", "demand"]
    assert "Bound to" in describe.item_mark_card(g, it, "bound").text()
    assert describe.item_mark_card(g, it, "demand").lines[0]
    g.leader.thirst = 90
    card = body_card(g.leader, g.tables)
    assert any("Drink" in x for x in card.lines)
