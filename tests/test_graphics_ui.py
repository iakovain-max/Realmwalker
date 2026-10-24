"""The graphics update and the new interface, headless: every game thing has a picture, screens draw with pictures
without a window, the map painter paints, worlds can be deleted safely, and everything can be done without Shift
or with the mouse alone."""

import copy

import numpy as np
import pytest
import tcod.console

from realmwalker.paths import Paths
from realmwalker.ui.gfx import GfxContext, dolls
from realmwalker.ui.gfx.atlas import Atlas
from realmwalker.ui.gfx.scene import Batch, Image
from realmwalker.ui.input import KeyEvent, MouseEvent
from tests.worlds import cached_world  # noqa: E402

SIZE = (160, 50)


@pytest.fixture(scope="module")
def atlas():
    a = Atlas(Paths().tiles)
    assert a.ok, "the tile sheets (assets/tiles) are missing"
    return a


@pytest.fixture
def world(make_app):
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    return cached_world(WorldOptions("Pictureland", 11, "small"), app.tables)


@pytest.fixture
def pictured(make_app, world, atlas):
    """An app drawing with pictures (as in a window), with a game started."""
    from realmwalker.game.state import new_game

    app = make_app()
    app.gfx = GfxContext(atlas, 10, 20, background=False)
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    return app, game


def render(app, size=SIZE):
    con = tcod.console.Console(*size, order="F")
    app.render(con)
    app.update()
    return app.last_canvas


def commands(canvas, kind=None):
    out = []
    for layer in canvas.layers:
        out += [c for c in layer.under + layer.over if kind is None or isinstance(c, kind)]
    return out


# ---------------------------------------------------------------------------- every thing has a picture
def test_every_terrain_creature_item_and_outfit_has_a_picture(make_app, atlas):
    app = make_app()
    t = app.tables
    sp = t.sprites
    missing = []
    for tid, spec in sp["terrain"].items():
        assert tid in t.terrain.index, f"sprites.json names a terrain that does not exist: {tid}"
        for key in ("ground", "object", "wall", "cold", "object_vertical"):
            name = spec.get(key)
            if name and not atlas.family(name) and not (spec.get("autotile") and atlas.family(f"{name}_0")):
                missing.append(f"terrain {tid} {key}: {name}")
        over = spec.get("over")
        for name in ([over] if isinstance(over, str) else over or []):
            if not atlas.family(name):
                missing.append(f"terrain {tid} over: {name}")
    for tid in t.terrain.ids:
        assert tid in sp["terrain"], f"local terrain {tid} has no picture in data/sprites.json"
    for cid in t.creatures.defs:
        for name, *_ in dolls.creature(cid, t, "test", atlas):
            if not atlas.has(name):
                missing.append(f"creature {cid}: {name}")
    from realmwalker.ui.gfx.localview import item_sprite
    from realmwalker.rules.items import Item

    for iid in t.items.defs:
        name = item_sprite(atlas, t, Item(0, iid))
        if not atlas.has(name):
            missing.append(f"item {iid}: {name}")
    missing += dolls.problems(t, atlas)
    for kind, name in list(sp["world"]["settlements"].items()) + list(sp["world"]["sites"].items()):
        if not atlas.has(name):
            missing.append(f"map mark {kind}: {name}")
    assert not missing, missing


def test_townsfolk_and_the_player_are_dressed(pictured, atlas):
    from realmwalker.game.people import npcs_in, prepare_town

    app, game = pictured
    town = game.world.settlements[0]
    prepare_town(game, town)
    people = npcs_in(game.world, town.id)
    assert people
    looks = set()
    for npc in people:
        parts = dolls.npc(npc, game.tables, atlas)
        assert parts and all(atlas.has(p[0]) for p in parts), parts
        assert any(p[0].startswith("fig/body/") for p in parts)
        looks.add(tuple(parts))
    assert len(looks) > len(people) // 2, "townsfolk should not all look alike"
    me = dolls.character(game.leader, game.tables, atlas=atlas)
    assert all(atlas.has(p[0]) for p in me) and any(p[0].startswith("fig/body/") for p in me)
    picture = dolls.compose(atlas, me)
    assert picture.shape == (32, 32, 4) and (picture[..., 3] > 0).sum() > 150


def test_figures_read_their_looks_from_words_and_wear_what_they_wear(pictured, atlas):
    from realmwalker.rules.items import Item

    app, game = pictured
    t = game.tables
    from realmwalker.rules import looks

    f = dolls.Figure(t, "human", "male", "x", looks.from_text(t, "Heavy, with straw-coloured hair, in sober dark clothes",
                                                             "human", "male", 30, "x"))
    assert f.hair == tuple(t.sprites["figures"]["hair_colours"]["blond"]), "'coloured' is not 'red'"
    assert f.look["build"] == "heavy"
    f = dolls.Figure(t, "human", "female", "y", looks.from_text(t, "A pale face and a shaven head", "human", "female",
                                                               30, "y"))
    assert f.look["hair"] == "bald" and f.skin == tuple(t.sprites["figures"]["skins"]["human"]["fair"])
    me = game.leader
    blade = Item(990001, "longsword")
    blade.magic = {"rarity": "rare", "look": {"metal": "red_steel", "glow": "red"}}
    me.inventory.append(blade)
    me.equipped["main_hand"] = blade.uid
    parts = dolls.character(me, t, atlas=atlas)
    held = {p[0]: p[1] for p in parts if p[0].startswith("fig/held/longsword/")}
    assert held["fig/held/longsword/metal"][:3] == tuple(t.sprites["figures"]["metals"]["red_steel"])
    assert "fig/held/longsword/glow" in held


# ---------------------------------------------------------------------------- screens draw with pictures
def test_the_main_view_draws_the_map_with_pictures(pictured):
    app, game = pictured
    canvas = render(app)
    assert app.error_count == 0
    chunks = [c for c in commands(canvas, Image) if isinstance(c.key, tuple) and c.key[0] in ("chunk", "map overview")]
    assert chunks, "the overworld is painted (the small map stands in until its chunks are done)"
    gs = app.top
    assert gs.tiles_drawn
    # On foot in a town: tiles, roofs and people.
    app.handle_event(KeyEvent("enter"))
    assert game.in_local
    canvas = render(app)
    assert app.error_count == 0
    assert sum(len(b) for b in commands(canvas, Batch)) > 200
    # Underground.
    from realmwalker.game import dungeon

    game.player.local_key = None
    site = min(game.world.sites, key=lambda s: abs(s.x - game.player.x) + abs(s.y - game.player.y))
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    for a in game.local.actors:
        a.alert = False
    render(app)
    assert app.error_count == 0


def test_every_screen_draws_with_pictures(pictured):
    from realmwalker.ui.screens.camp import CampScreen
    from realmwalker.ui.screens.game_menu import GameMenu, WorldsScreen
    from realmwalker.ui.screens.health import HealthScreen
    from realmwalker.ui.screens.journal import JournalScreen
    from realmwalker.ui.screens.party import PartyScreen
    from realmwalker.ui.screens.settings_screen import SettingsScreen
    from realmwalker.ui.screens.sheets import CharacterScreen, EquipmentScreen, InventoryScreen
    from realmwalker.ui.screens.title import TitleScreen
    from realmwalker.ui.screens.world_map import WorldMapScreen

    app, game = pictured
    gs = app.top
    screens = [CharacterScreen(app, game), InventoryScreen(app, game), EquipmentScreen(app, game),
               HealthScreen(app, game), CampScreen(app, game), JournalScreen(app, game), PartyScreen(app, game),
               SettingsScreen(app), GameMenu(app), WorldsScreen(app), TitleScreen(app), WorldMapScreen(app, gs)]
    for size in ((80, 30), SIZE, (240, 67)):
        for screen in screens:
            app.push(screen)
            render(app, size)
            app.pop()
    assert app.error_count == 0


def test_a_conversation_shows_who_you_are_talking_to(pictured):
    from realmwalker.game.people import npcs_in

    app, game = pictured
    app.handle_event(KeyEvent("enter"))
    s = game.world.settlement_at(game.player.x, game.player.y)
    npc = next(n for n in npcs_in(game.world, s.id) if n.notable)
    game.talk_to = npc.id
    render(app)
    canvas = render(app)
    assert type(app.top).__name__ == "DialogueScreen"
    assert any(isinstance(c.key, tuple) and c.key[0] == "fig" for c in commands(canvas, Image)), "the portrait is drawn"
    assert app.error_count == 0


def test_a_fight_is_a_stage_and_its_blows_are_shown(pictured):
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter
    from realmwalker.ui.screens.battle import BattleScreen

    app, game = pictured
    enc = make_encounter(game, "bandits", game.world.rng.child("stage"))
    fight.start_battle(game, enc.creatures, enc.intro, title="Bandits")
    render(app)
    screen = app.top
    assert isinstance(screen, BattleScreen)
    for _ in range(200):
        if game.battle is None or screen.battle.outcome is not None:
            break
        if screen.actor() is not None:
            app.handle_event(KeyEvent("z"))  # let the game play the turn
        app.update()
        render(app)
    kinds = {e["kind"] for e in screen.battle.events}
    assert "attack" in kinds and "move" in kinds
    assert screen.board.cells, "everyone has a place on the field"
    assert app.error_count == 0


def test_the_battlefield_is_drawn_as_a_grid_with_highlights(pictured):
    """Whose turn it is gets the squares they can walk to, a path to the square under the mouse, and the odds against
    an enemy under it; a spell aimed at a square shows the squares it would fill."""
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter
    from realmwalker.ui.input import MouseEvent
    from realmwalker.ui.screens.battle import BattleScreen

    app, game = pictured
    enc = make_encounter(game, "wolf_pack", game.world.rng.child("grid"))
    fight.start_battle(game, enc.creatures, enc.intro, title="Wolves")
    render(app)
    screen = app.top
    assert isinstance(screen, BattleScreen)
    for _ in range(100):
        if screen.actor() is not None or screen.battle.outcome is not None:
            break
        app.update()
        render(app)
    f = screen.actor()
    if f is None:
        return
    ov = screen.overlay()
    assert ov["reach"], "where they can walk is shown"
    target = sorted(ov["reach"])[0]
    screen.hover = target
    ov = screen.overlay()
    assert ov["path"][0] == (f.x, f.y) and ov["path"][-1] == target and ov["cost"] >= 5
    canvas = render(app)
    assert screen.board.T >= 16 and screen.board.art is not None
    # Walk there with a click.
    gx, gy = screen.board.sq_px(target[0] + 0.5, target[1] + 0.5)
    app.handle_event(MouseEvent("click", int(gx // app.gfx.cell_w), int(gy // app.gfx.cell_h), px=gx, py=gy))
    assert (f.x, f.y) == target
    assert app.error_count == 0


def test_the_domains_on_the_battle_mat(pictured):
    """A Trickery cleric's double (its maker's pale likeness), a Light cleric's corona, a warding flare and a god's
    answer are drawn without trouble (Expansion 5 Part B)."""
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter
    from realmwalker.rules.combat import Token
    from realmwalker.rules.engine.handlers import domains

    app, game = pictured
    enc = make_encounter(game, "wolf_pack", game.world.rng.child("domains"))
    battle = fight.start_battle(game, enc.creatures, enc.intro, title="Wolves")
    render(app)
    me = battle.side("party")[0]
    foe = battle.side("foe")[0]
    tok = Token(battle._zone_id(), domains.DOUBLE, foe.x - 1, foe.y, me.id, rounds=10)
    battle.tokens.append(tok)
    battle._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=me.id)
    me.buffs.append({"corona": True, "light": 12, "rounds": 10, "source": "corona_of_light"})
    battle._event("flare", by=me.id, at=foe.id, to=me.id)
    battle._event("miracle", who=me.id, domain="light")
    battle._event("double_cast", id=tok.id, by=me.id)
    for _ in range(6):
        app.update()
        render(app)
    assert app.error_count == 0


# ---------------------------------------------------------------------------- the painter
def test_the_map_painter_paints_pieces_that_meet(make_app, world):
    from realmwalker.ui.gfx.paint import CANON, ChunkCache, WorldPainter

    app = make_app()
    painter = WorldPainter(world, app.tables)
    a = painter.paint(0, 0, 16, 16, 12)
    assert a.size == (192, 192)
    cache = ChunkCache(painter)
    im = cache.paint_now((0, 0))
    assert cache.get((0, 0)) is im
    assert im.size[0] == min(cache.n, world.width) * CANON
    cache.close()
    whole = painter.overview(3)
    assert whole.size == (world.width * 3, world.height * 3)


# ---------------------------------------------------------------------------- saved worlds
def test_deleting_a_world_touches_nothing_else(tmp_path, monkeypatch):
    from realmwalker.game import save
    from realmwalker.game.save import SaveError, delete_world

    monkeypatch.setattr(save, "_to_recycle_bin", lambda path: False)
    saves = tmp_path / "saves"
    good = saves / "dunmark-1"
    good.mkdir(parents=True)
    (good / save.WORLD_FILE).write_bytes(b"x")
    (good / save.CHARACTER_FILE).write_bytes(b"x")
    stranger = tmp_path / "elsewhere"
    stranger.mkdir()
    (stranger / save.WORLD_FILE).write_bytes(b"x")
    not_a_save = saves / "notes"
    not_a_save.mkdir()
    with pytest.raises(SaveError):
        delete_world(stranger, saves)
    with pytest.raises(SaveError):
        delete_world(not_a_save, saves)
    assert delete_world(good, saves) == "deleted"
    assert not good.exists() and stranger.exists() and not_a_save.exists()


def test_the_saved_worlds_screen_deletes_after_asking(pictured, monkeypatch):
    from realmwalker.game import save
    from realmwalker.ui.screens.base import ConfirmBox
    from realmwalker.ui.screens.game_menu import WorldsScreen

    monkeypatch.setattr(save, "_to_recycle_bin", lambda path: False)
    app, game = pictured
    app.save_game()
    folder = app.paths.saves / game.world.meta.id
    app.end_game()
    screen = WorldsScreen(app)
    app.push(screen)
    render(app)
    assert any(s.folder == folder for s in screen.saves)
    screen.selected = next(i for i, s in enumerate(screen.saves) if s.folder == folder)
    app.handle_event(KeyEvent("delete"))
    assert isinstance(app.top, ConfirmBox)
    app.handle_event(KeyEvent("n"))
    assert folder.exists()
    app.handle_event(KeyEvent("delete"))
    app.handle_event(KeyEvent("y"))
    assert not folder.exists()
    assert all(s.folder != folder for s in screen.saves)
    assert app.error_count == 0


# ---------------------------------------------------------------------------- no Shift, and the mouse alone
def test_keys_without_shift(make_app, world):
    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.legend import LegendScreen
    from realmwalker.ui.screens.log_screen import LogScreen
    from realmwalker.ui.screens.spells import SpellsScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    gs = app.top
    for key, kind in (("o", LogScreen), ("k", LegendScreen)):
        app.handle_event(KeyEvent(key))
        assert isinstance(app.top, kind), key
        app.handle_event(KeyEvent("escape"))
    from realmwalker.rules import spells as sp

    c = game.leader
    c.cls = "wizard"
    sp.init_spells(c, game.tables)
    app.handle_event(KeyEvent("a"))
    assert isinstance(app.top, SpellsScreen)
    app.handle_event(KeyEvent("escape"))
    washed = []
    monkey = __import__("realmwalker.game.survival", fromlist=["wash"])
    original = monkey.wash
    monkey.wash = lambda g: washed.append(1) or []
    try:
        app.handle_event(KeyEvent("b"))
    finally:
        monkey.wash = original
    assert washed
    app.handle_event(KeyEvent("enter"))
    assert game.in_local
    app.handle_event(KeyEvent("x"))
    assert not game.in_local
    assert app.top is gs and app.error_count == 0


def test_every_button_on_the_action_bar_works(pictured):
    from realmwalker.ui import hud

    app, game = pictured
    gs = app.top
    for local in (False, True):
        if local:
            app.handle_event(KeyEvent("enter"))
            assert game.in_local
        render(app)
        for action in hud.actions(gs):
            if action.id in ("menu", "leave", "enter"):
                continue
            action.run()
            render(app)
            while app.top is not gs:
                app.pop()
            gs.look = None
            game.travel = None
    assert app.error_count == 0


def test_a_right_click_on_the_map_offers_what_can_be_done(make_app, world):
    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.popup import ContextMenu

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    gs = app.top
    render(app)
    p = game.player
    px, py = gs.world_view.cell_px(p.x + 3.5, p.y + 0.5)
    app.handle_event(MouseEvent("click", int(px // 10), int(py // 20), button="right", px=px, py=py))
    menu = app.top
    assert isinstance(menu, ContextMenu)
    labels = [e[0] for e in menu.entries]
    assert any("Travel" in label for label in labels) and any("Look" in label for label in labels)
    look = next(i for i, e in enumerate(menu.entries) if e[0].startswith("Look"))
    menu.choose(look)
    assert gs.look is not None and app.top is gs


def test_the_pack_uses_a_thing_on_a_double_click(make_app, world):
    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.sheets import InventoryScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    c = game.leader
    c.hunger = 60
    inv = InventoryScreen(app, game)
    app.push(inv)
    render(app)
    idx = next(i for i, it in enumerate(inv.visible_items()) if it.def_id == "rations")
    inv._click(idx)
    assert c.hunger == 60, "one click only chooses"
    inv._click(idx)
    assert c.hunger < 60, "a second click straight after uses it"
    inv._menu(idx)
    assert type(app.top).__name__ == "ContextMenu"
    assert app.error_count == 0


def test_markup_is_closed_with_a_bare_tag():
    """Colour markup closes with </>; a "</title>" shows on screen as it is (it did, on the help screen)."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    bad = []
    for path in list((root / "realmwalker").rglob("*.py")) + list((root / "data").glob("*.json")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"</[a-z_]+>", line):
                bad.append(f"{path.relative_to(root)}:{n}")
    assert not bad, bad


def test_the_pack_shows_magic_things_with_their_glow(pictured):
    """A rare thing in the pack is drawn on its card with a faint light behind it (this once broke the pack: the
    light was borrowed from the battle screen under a name that had changed)."""
    from realmwalker.core.rng import RNG
    from realmwalker.game import magic_items
    from realmwalker.rules.inventory import add_existing
    from realmwalker.ui.screens.sheets import InventoryScreen

    app, game = pictured
    made = 0
    for i in range(80):
        it = magic_items.make(game, RNG(i, "pack-glow"), rarity="rare")
        if it is None:
            continue
        it.magic["identified"] = True
        it.magic.setdefault("look", {})["glow"] = "gold"
        add_existing(game.leader, game.tables.items, it)
        made += 1
        if made >= 6:
            break
    assert made
    inv = InventoryScreen(app, game)
    app.push(inv)
    for i, it in enumerate(inv.visible_items()):
        inv.selected = i
        canvas = render(app)
        if it.magic:
            assert any(getattr(c, "key", None) == "item_glow" for c in commands(canvas, Image)), it.def_id
    assert app.error_count == 0


def test_the_map_legend_shows_the_maps_own_pictures(make_app, atlas):
    """Pictures are the only look: the legend shows, beside each name, the picture the maps draw for it."""
    from realmwalker.ui.screens.legend import LegendScreen, legend_rows

    app = make_app()
    rows = legend_rows(app.tables, atlas)
    missing = [label for kind, pic, label in rows if kind == "tile" and not atlas.resolve(str(pic))]
    assert not missing, missing
    assert sum(1 for kind, _, _ in rows if kind == "swatch") >= len(app.tables.biomes.ids)
    app.push(LegendScreen(app))
    canvas = render(app)
    assert "Map key" in canvas.words() and commands(canvas, Batch)
    assert app.error_count == 0


@pytest.mark.story
def test_the_story_s_screens_draw_and_answer_keys(pictured):
    """Expansion 6: the beat screen (pages, choices), a chapter's title card, the boss's card and the epilogue open
    from the game screen when they wait, draw, and close on their keys."""
    from realmwalker.game import story
    from realmwalker.game.story import beats, forge
    from realmwalker.ui.input import KeyEvent
    from realmwalker.world import threats

    app, game = pictured
    t = next((t for t in threats.records(game.world).values() if t["kind"] == "beast" and t["state"] != "ended"
              and forge.fitting(game, t)), None)
    if t is None:
        pytest.skip("no beast tale in this world")
    if t["state"] == "dormant":
        threats.stir(game.world, app.tables, t, game.world.rng, day=0)
    beats.director(game.world)["pending"] = None
    story.offer_hook(game, t)
    render(app)  # (the game screen opens what waits)
    canvas = render(app)
    assert type(app.screens[-1]).__name__ == "BeatScreen"
    assert threats.villain_name(game.world, t) in canvas.words()
    app.handle_event(KeyEvent("1"))  # (I will hunt it)
    app.handle_event(KeyEvent("enter"))
    render(app)
    adv = story.active(game)[0]
    assert type(app.screens[-1]).__name__ == "TitleCardScreen"
    render(app)  # (the game screen opens what waits)
    canvas = render(app)
    assert "Chapter I" in canvas.words()
    app.handle_event(KeyEvent("enter"))
    render(app)
    assert not (game.world.politics["director"].get("card") or game.world.politics["director"].get("pending"))
    game.finale = {"adv": adv["id"], "actor": -1}
    render(app)  # (the game screen opens what waits)
    canvas = render(app)
    assert type(app.screens[-1]).__name__ == "FinaleScreen" and "What you know" in canvas.words()
    app.handle_event(KeyEvent("escape"))
    render(app)
    assert game.finale is None
    adv["epilogue"] = [{"about": "place", "text": "It was over."}, {"about": "hero", "text": "You went on."}]
    game.renown.legend["offered"] = ["the Hunter"]
    game.epilogue = {"adv": adv["id"]}
    render(app)  # (the game screen opens what waits)
    canvas = render(app)
    assert type(app.screens[-1]).__name__ == "EpilogueScreen" and "It was over." in canvas.words()
    app.handle_event(KeyEvent("enter"))
    render(app)
    app.handle_event(KeyEvent("1"))
    render(app)
    assert game.epilogue is None and game.renown.legend["epithet"] == "the Hunter"
    assert app.error_count == 0


def test_the_story_s_pictures_draw(pictured):
    """Expansion 6 A.10: a beat's picture (the camp at night) above its words, the chapter card's seal and band, and
    on the world map a seal where a tale wants you and claw marks at a den whose signs you have heard."""
    from realmwalker.game import story
    from realmwalker.game.story import beats, forge
    from realmwalker.ui.gfx.scene import Sprite
    from realmwalker.world import threats

    app, game = pictured
    t = next((t for t in threats.records(game.world).values() if t["kind"] == "beast" and t["state"] != "ended"
              and forge.fitting(game, t)), None)
    if t is None:
        pytest.skip("no beast tale in this world")
    if t["state"] == "dormant":
        threats.stir(game.world, app.tables, t, game.world.rng, day=0)
    other = next((o for o in threats.live(game.world) if o is not t), None)
    adv = forge.make(game, t)
    beats.director(game.world)["pending"] = None
    beats.director(game.world)["card"] = {"adv": adv["id"], "chapter": 0}
    render(app)
    canvas = render(app)
    names = {c.name for c in commands(canvas, Sprite)}
    assert type(app.screens[-1]).__name__ == "TitleCardScreen" and "map/story" in names
    assert "Chapter I" in canvas.words()
    app.handle_event(KeyEvent("enter"))
    render(app)
    beats.offer(game, "beast_carcass", adv=adv["id"], where="camp")
    render(app)
    canvas = render(app)
    names = {c.name for c in commands(canvas, Sprite)}
    assert type(app.screens[-1]).__name__ == "BeatScreen"
    assert any(n.startswith("feature/campfire") for n in names), "the camp at night above the beat's words"
    app.handle_event(KeyEvent("1"))
    app.handle_event(KeyEvent("enter"))
    render(app)
    if other is not None and other.get("signs"):
        game.renown.heard.add(other["signs"][0])
    marks = story.map_signs(game)
    assert any(k == "story" for _, _, k in marks)
    if other is not None and other.get("signs"):
        assert any(k == "sign" for _, _, k in marks)
    assert all(app.gfx.atlas.has(f"map/{k}") for k in ("story", "sign"))
    assert app.error_count == 0
