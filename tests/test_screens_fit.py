"""Screens that fit (after v1): no text runs over the side of a box or off the edge of the window, at any size the
game supports; a big fight shows everyone on the board when there is room; nothing is said twice on one line."""

import copy
import re

import pytest
import tcod.console

from realmwalker.core.rng import RNG
from realmwalker.ui import widgets
from tests.worlds import cached_world  # noqa: E402

SIZES = [(80, 30), (100, 34), (120, 45), (160, 45), (192, 54)]
SIDES = {ord("│"), ord("║")}


class Watch:
    """Records the boxes a screen draws and every line of text, then checks what ran over a side or the edge."""

    def __init__(self, monkeypatch):
        self.frames, self.texts, self.problems = [], [], []
        frame, text = widgets.Canvas.frame, widgets.Canvas.text
        watch = self

        def rec_frame(canvas, x, y, w, h, title="", **kw):
            frame(canvas, x, y, w, h, title, **kw)
            if w >= 2 and h >= 2:
                watch.frames.append((x, y, w, h, len(watch.texts)))

        def rec_text(canvas, x, y, s, fg=None, bg=None, max_width=None):
            shown = s[: max(0, max_width)] if max_width is not None else s
            if s and 0 <= y < canvas.height and x < canvas.width < x + len(shown.rstrip()):
                watch.problems.append(f"off the edge: {shown.strip()!r}")
            watch.texts.append((x, y, shown))
            return text(canvas, x, y, s, **({} if fg is None else {"fg": fg}), bg=bg, max_width=max_width)

        monkeypatch.setattr(widgets.Canvas, "frame", rec_frame)
        monkeypatch.setattr(widgets.Canvas, "text", rec_text)

    def render(self, screen, size):
        self.frames, self.texts = [], []
        con = tcod.console.Console(*size, order="F")
        canvas = widgets.Canvas(con)
        screen.render(canvas)
        for x, y, w, h, first in self.frames:
            for side in (x, x + w - 1):
                for yy in range(max(0, y + 1), min(con.height, y + h - 1)):
                    if 0 <= side < con.width and int(con.rgb["ch"][side, yy]) not in SIDES:
                        over = next((s for tx, ty, s in reversed(self.texts[first:])
                                     if ty == yy and tx <= side < tx + len(s) and s.strip()), None)
                        if over:
                            self.problems.append(f"over a border at {size}: {over.strip()!r}")
        return "\n".join("".join(chr(c) for c in con.rgb["ch"][:, y]) for y in range(con.height))


@pytest.fixture
def world(make_app):
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    return app, cached_world(WorldOptions("Fitland", 3, "small"), app.tables)


@pytest.fixture
def game(world):
    from realmwalker.game.state import new_game

    app, w = world
    g = new_game(copy.deepcopy(w), app.tables)
    g.survival = False
    app.start_game(g)
    return app, g


def hire(app, g, n=1):
    from realmwalker.game import companions
    from realmwalker.game.people import npcs_in

    for s in g.world.settlements:
        g.player.local_key = None
        g.player.x, g.player.y = s.x, s.y
        g.enter_local()
        for npc in npcs_in(g.world, s.id):
            if npc.flags.get("recruit") and not npc.flags.get("companion") and len(g.party) <= n:
                npc.disposition, npc.met = 30, True
                g.leader.money = 10 ** 5
                companions.hire(g, npc)
        if len(g.party) > n:
            break
    g.leave_local()
    return len(g.party) > n


def test_trouble_on_the_road_fits_its_box(game, monkeypatch):
    from realmwalker.game.encounters import make_encounter
    from realmwalker.ui.screens.encounter import EncounterScreen

    app, g = game
    g.encounter = make_encounter(g, "bandits", RNG(2, "fit"))
    g.encounter.spotted_first = False  # "Ambush them" is greyed out, and says why
    watch = Watch(monkeypatch)
    for size in SIZES:
        shown = watch.render(EncounterScreen(app, g), size)
        assert "they have already seen you" in shown
    assert not watch.problems, watch.problems


def test_trouble_with_a_purse_or_food_to_give_still_fits(game, monkeypatch):
    """The sure ways out (2026-10): half the purse to robbers, food thrown to hungry beasts."""
    from realmwalker.game.encounters import make_encounter
    from realmwalker.rules.inventory import add_item
    from realmwalker.ui.screens.encounter import EncounterScreen

    app, g = game
    g.leader.money = 123456
    add_item(g.leader, g.tables.items, "raw_meat", 6)
    watch = Watch(monkeypatch)
    for group, words in (("bandits", "Hand over your purse"), ("wolf_pack", "Throw them food")):
        g.encounter = make_encounter(g, group, RNG(2, "fit"))
        g.encounter.spotted_first = True  # the long "Slip away (..., with the advantage of seeing them first)"
        for size in SIZES:
            shown = watch.render(EncounterScreen(app, g), size)
            assert words in shown, (group, size)
    assert not watch.problems, watch.problems


def test_the_camp_at_night_fits_and_offers_sleep_until_morning(game, monkeypatch):
    from realmwalker.ui.screens.camp import CampScreen

    app, g = game
    for s in g.world.settlements:  # out of town, so the shelter is offered
        g.player.x, g.player.y = s.x + 2, s.y
        if g.world.settlement_at(g.player.x, g.player.y) is None and \
                g.step_minutes(g.player.x, g.player.y, g.player.x, g.player.y) is not None:
            break
    m = g.moment
    g.world.time = (m.total_days + 1) * 1440 + 21 * 60
    watch = Watch(monkeypatch)
    for size in SIZES:
        shown = watch.render(CampScreen(app, g), size)
        if size[1] >= 34:
            assert "Sleep until morning" in shown, size
    assert not watch.problems, watch.problems


def test_every_road_event_fits_and_names_its_skill_once(game, monkeypatch):
    from realmwalker.game import events
    from realmwalker.ui.screens.event import EventScreen

    app, g = game
    watch = Watch(monkeypatch)
    for eid in g.tables.travel_events:
        g.event = events.make_event(g, eid)
        for label, _, _ in events.options(g, g.event):
            if label.startswith("["):
                skill = label[1:label.index("]")]
                assert label.count(skill) == 1, label
        for size in ((80, 30), (160, 45)):
            watch.render(EventScreen(app, g), size)
    g.event = None
    assert not watch.problems, watch.problems


def test_an_inn_names_each_price_once(game, monkeypatch):
    from realmwalker.game.people import npcs_in
    from realmwalker.game import services
    from realmwalker.ui.screens.services import ServicesScreen

    app, g = game
    town = next(s for s in g.world.settlements if s.kind in ("town", "city", "village"))
    g.player.x, g.player.y = town.x, town.y
    g.enter_local()
    keeper = next((n for n in npcs_in(g.world, town.id) if n.job == "innkeeper"), None)
    if keeper is None:
        pytest.skip("no inn")
    watch = Watch(monkeypatch)
    screen = ServicesScreen(app, g, keeper)
    screen.sub = next(s for s in services.services_for(g, keeper) if s.id == "room")  # the beds, by grade
    shown = watch.render(screen, (160, 45))
    beds = [line for line in shown.splitlines() if "Poor:" in line or "Modest:" in line]
    assert beds
    for bed in beds:
        assert len(re.findall(r"\d+ (?:gp|sp|cp)(?: \d+ (?:sp|cp))*", bed)) == 1, bed
    assert not watch.problems, watch.problems


def test_the_sheets_fit_a_small_window(game, monkeypatch):
    from realmwalker.ui.screens.sheets import CharacterScreen, InventoryScreen
    from realmwalker.ui.screens.title import TitleScreen

    app, g = game
    hire(app, g)
    watch = Watch(monkeypatch)
    for size in SIZES:
        sheet = CharacterScreen(app, g)
        watch.render(sheet, size)
        if sheet.narrow(size[0]):
            sheet.toggle_skills()  # the notes, where the skills were
            assert "Tie:" in watch.render(sheet, size) or "Looks:" in watch.render(sheet, size)
        watch.render(InventoryScreen(app, g), size)
        watch.render(TitleScreen(app), size)
    assert not watch.problems, watch.problems


def test_a_big_fight_shows_everyone_when_there_is_room(game, monkeypatch):
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter
    from realmwalker.rules.combat import FOE
    from realmwalker.ui.screens.battle import BattleScreen

    app, g = game
    hire(app, g, 3)
    for group in ("bandit_gang", "goblin_warband", "orc_warband", "bandits", "goblins"):
        g.encounter = make_encounter(g, group, RNG(9, "crowd"))
        if len(g.encounter.creatures) >= 4:
            break
    b = fight.encounter_fight(g, False)
    g.encounter = None
    if len(b.side(FOE)) < 4:
        pytest.skip("not a big enough band")
    watch = Watch(monkeypatch)
    screen = BattleScreen(app, g)
    shown = watch.render(screen, (160, 45))
    assert all(f.name[:10] in shown for f in b.side(FOE)), "everyone is in the order of battle"
    for f in b.fighters:  # and on the field, where they stand
        if f.state != "fled":
            assert f.id in screen.board.cells, f"{f.name} is not on the board"
    assert not watch.problems, watch.problems


def test_every_step_of_creation_fits_and_every_origin_choice_turns(world, monkeypatch):
    """The 2024 order (calling, background, people, origin...) at every size; every row of the Origin step changes
    both ways without trouble, for a human (Versatile, Skillful) acolyte (Magic Initiate) and an elf (a lineage)."""
    from realmwalker.ui.screens import creation as cr

    app, w = world
    watch = Watch(monkeypatch)
    screen = cr.CreationScreen(app, w)
    for race, bg in (("human", "acolyte"), ("elf", "sage"), ("dwarf", "entertainer")):
        screen.b.set_background(bg)
        screen.b.set_race(race)
        rows = screen._origin_rows()
        for i in range(len(rows)):
            screen.adjust_origin(i, 1)
            screen.adjust_origin(min(i, len(screen._origin_rows()) - 1), -1)
        assert screen.b.problems() == []
        assert screen.b.build().feats
    for method in ("array", "roll", "point_buy"):
        screen.b.set_method(method)
    for size in SIZES:
        for step in range(len(cr.STEPS)):
            screen.go(step)
            text = watch.render(screen, size)
            if step == cr.ORIGIN:
                assert "Language" in text or "Equipment" in text
    assert not watch.problems, watch.problems[:5]
