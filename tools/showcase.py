"""Contact sheets of the story's pictures (Expansion 6 Part B), drawn by the real renderer, for looking at.

    .venv/Scripts/python.exe tools/showcase.py [--sheet vignettes] [--out build/showcase]

Sheets: vignettes (the fourteen backdrops at day and at night, with figures); letter (a letter's page, in each of the
three hands); mark (a town's close-up map dressed for a mark: --mark burned, festival, siege...); signs (the world map
with a town under each sign, B.8); titlecard (the Beast's first chapter opening); epilogue (its first page, with its
picture); camp (the camp at dawn with the carcass the beast left); all (every sheet, and the mark sheet for each mark
that dresses a town). Opens the game's window for a moment, draws the sheet, saves it as a PNG and closes. Anton
looks at these to judge the pictures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHEETS = ("vignettes", "letter", "mark", "signs", "titlecard", "epilogue", "camp")
MARKS = ("burning", "burned", "sacked", "siege", "plague", "festival", "memorial", "rebuilding", "emptied")


def _letter_screen(app, hand: str):
    from types import SimpleNamespace

    from realmwalker.ui.screens.letter import LetterScreen

    lines = ["To whoever carries a sword through Starograd,",
             "Ysscara the Weaver has killed again. Anyone with the stomach for a hunt, ask for the headman of "
             "Starograd. Its lair is the ruins of Haukhall, about fifteen miles to the north.",
             "We are not fighters. We have tried, and we have buried those who tried.",
             "What we can pay is yours. Only come."]
    world = SimpleNamespace(politics={"letters": {"L1": {"from": "Gyda, headman of Starograd", "hand": hand,
                                                         "seal": [150, 40, 32] if hand != "dark" else [30, 26, 30],
                                                         "lines": lines, "key": 1, "read": True, "day": 0}}})
    return LetterScreen(app, SimpleNamespace(world=world), "L1")


def _mark_town(app, mark: str, world_name: str = "Townland:21") -> None:
    """A game in a test world, standing in its biggest town with the mark on it (the game screen as you would see
    it)."""
    import copy

    from realmwalker.game.state import new_game
    from realmwalker.world import marks
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    name, seed = world_name.split(":")
    world = copy.deepcopy(cached_world(WorldOptions(name, int(seed), "small", history=40), app.tables))
    game = new_game(world, app.tables)
    game.survival = False
    s = max((t for t in world.settlements if t.kind in ("town", "city")), key=lambda t: t.population)
    s.status.clear()
    marks.add(world, s, mark, 1.0, app.tables, until=999.0)
    world.local_maps.pop(f"{s.x},{s.y}", None)
    app.start_game(game)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.world.time = (game.world.time // 1440 + 1) * 1440 + 11 * 60
    game.enter_local()
    rec = (game.local.meta.get("marks") or {}).get(mark) or {}
    cells = rec.get("cells") or []
    burning = sorted(game.local.meta.get("fire") or {})
    if burning:  # (a burning town: stand a few steps from its fire, B.7)
        x, y = (int(v) for v in burning[len(burning) // 2].split(","))
        cells = [(x, y + 2, None)]
    if cells:  # stand where the mark is
        x, y, _ = cells[len(cells) // 2]
        walk = app.tables.terrain.walk[game.remap_for(game.local)[game.local.terrain]]
        for r in range(0, 6):
            spot = next(((x + dx, y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
                         if game.local.in_bounds(x + dx, y + dy) and walk[x + dx, y + dy]
                         and (not burning or game.local.building_at(x + dx, y + dy) is None)), None)
            if spot:
                game.player.lx, game.player.ly = spot
                break


def _signs(app) -> None:
    """The world map, with the towns about the start each under a sign (the console's showcase)."""
    import copy

    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.debug_console import DebugConsole
    from realmwalker.ui.screens.world_map import WorldMapScreen
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    world = copy.deepcopy(cached_world(WorldOptions("Signland", 21, "small", history=60), app.tables))
    game = new_game(world, app.tables)
    game.survival = False
    app.start_game(game)
    game.world.time = (game.world.time // 1440 + 1) * 1440 + 15 * 60
    DebugConsole(app).run("showcase")
    app.push(WorldMapScreen(app, app.top))


def _zoom_in(app) -> None:
    """Closer, once the map has opened (it opens fitted to the land)."""
    app.top.target = app.top.ppc = 32.0


def _tale(app, what: str) -> None:
    """A game near a beast with its tale begun: its title card, its epilogue, or the camp it left a carcass at."""
    import copy

    from realmwalker.game import camp, story
    from realmwalker.game.state import new_game
    from realmwalker.game.story import beats, endings, forge
    from realmwalker.world import threats
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    world = copy.deepcopy(cached_world(WorldOptions("Forgeland", 77, "medium"), app.tables))
    t = next(t for t in threats.records(world).values() if t["kind"] == "beast" and t["state"] != "ended")
    town = min((s for s in world.settlements if s.kind in ("town", "village")),
               key=lambda s: threats.distance(world, t, s.x, s.y))
    game = new_game(world, app.tables, start_settlement=town.id)
    game.survival = False
    app.start_game(game)
    adv = forge.make(game, threats.records(game.world)[t["id"]])
    d = beats.director(game.world)
    d["scheduled"] = []
    if what == "titlecard":
        d["card"] = {"adv": adv["id"], "chapter": 0}
        return
    d["card"] = None
    if what == "epilogue":
        endings.finish(game, adv)
        return
    game.world.time = (game.world.time // 1440 + 1) * 1440 + 6 * 60  # (dawn)
    camp.make_camp(game)
    camp.light_fire(game)
    story.on_night(game, "camp")  # (whatever the beast does; the carcass is set below so the sheet shows it)
    beats.director(game.world)["left"] = {"what": "carcass", "x": game.player.x, "y": game.player.y,
                                          "day": int(game.moment.total_days)}
    beats.director(game.world)["pending"] = None
    from realmwalker.ui.screens.camp import CampScreen

    app.push(CampScreen(app, game))


def _sheet_screen(app, sheet: str):
    from realmwalker.ui.screens.base import Screen

    if sheet == "letter":
        return _letter_screen(app, app.showcase_hand)

    class Sheet(Screen):
        title = "Showcase"

        def render(self, canvas) -> None:
            if sheet == "vignettes":
                _vignettes(canvas, app)

        def handle_key(self, ev) -> bool:
            return True

    return Sheet(app)


def _vignettes(canvas, app) -> None:
    from realmwalker.ui.gfx import dolls, vignette
    from realmwalker.ui.gfx.scene import Rect, Text

    W, H = canvas.width * canvas.cell_w, canvas.height * canvas.cell_h
    canvas.clear_cells(0, 0, canvas.width, canvas.height)
    canvas.under(Rect(0, 0, W, H, (18, 16, 14, 255)))
    kinds = list(vignette.BACKDROPS)
    cols = 4
    rows = (len(kinds) * 2 + cols - 1) // cols
    cw, ch = W / cols, H / rows
    t = app.tables
    who = [dolls.creature(c, t, f"show{c}", canvas.gfx.atlas) for c in ("bandit", "guard", "cultist")
           if c in t.creatures.defs]
    for i, (kind, time) in enumerate((k, tt) for k in kinds for tt in ("day", "night")):
        cx, cy = (i % cols) * cw, (i // cols) * ch
        spec = {"backdrop": kind, "time": time, "figures": who[:1 + i % 3]}
        vignette.compose(canvas, (cx + 6, cy + 6, cw - 12, ch - 26), spec, 1.0)
        canvas.under(Text(cx + cw / 2, cy + ch - 12, f"{kind} ({time})", "heading", 14, (230, 210, 170, 255),
                          anchor="mm"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="vignettes", choices=SHEETS + ("all",))
    ap.add_argument("--out", default=str(ROOT / "build" / "showcase"))
    ap.add_argument("--hand", default="plain", choices=("plain", "fine", "dark"))
    ap.add_argument("--mark", default="burned")
    ap.add_argument("--world", default="Townland:21", help="the test world, name:seed (Lifeland:33 has timber towns)")
    args = ap.parse_args(argv)
    if args.sheet == "all":
        rest = ["--out", args.out, "--world", args.world]
        for sheet in SHEETS:
            if sheet == "mark":
                for mark in MARKS:
                    main(["--sheet", "mark", "--mark", mark] + rest)
            elif sheet == "letter":
                for hand in ("plain", "fine", "dark"):
                    main(["--sheet", "letter", "--hand", hand] + rest)
            else:
                main(["--sheet", sheet] + rest)
        return 0
    from realmwalker.app import App
    from realmwalker.ui import window

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    app = App(home=str(ROOT / "build" / "showcase_home"))
    shot = out / {"letter": f"letter_{args.hand}.png", "mark": f"mark_{args.mark}.png"}.get(args.sheet, f"{args.sheet}.png")
    app.showcase_hand = args.hand

    def show(app):
        if args.sheet == "mark":
            _mark_town(app, args.mark, args.world)
            return
        if args.sheet == "signs":
            _signs(app)
            return
        if args.sheet in ("titlecard", "epilogue", "camp"):
            _tale(app, args.sheet)
            return
        app.push(_sheet_screen(app, args.sheet))

    try:
        script = [(10, show)] + ([(30, _zoom_in)] if args.sheet == "signs" else [])
        window.run(app, script=script, max_frames=70, screenshots_at={60: shot})
    finally:
        app.shutdown()
    print(f"Saved {shot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
