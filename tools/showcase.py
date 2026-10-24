"""Contact sheets of the story's pictures (Expansion 6 Part B), drawn by the real renderer, for looking at.

    .venv/Scripts/python.exe tools/showcase.py [--sheet vignettes] [--out build/showcase]

Sheets: vignettes (the fourteen backdrops at day and at night, with figures). Opens the game's window for a moment,
draws the sheet, saves it as a PNG and closes. Anton looks at these to judge the pictures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHEETS = ("vignettes",)


def _sheet_screen(app, sheet: str):
    from realmwalker.ui.screens.base import Screen

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
    ap.add_argument("--sheet", default="vignettes", choices=SHEETS)
    ap.add_argument("--out", default=str(ROOT / "build" / "showcase"))
    args = ap.parse_args(argv)
    from realmwalker.app import App
    from realmwalker.ui import window

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    app = App(home=str(ROOT / "build" / "showcase_home"))
    shot = out / f"{args.sheet}.png"

    def show(app):
        app.push(_sheet_screen(app, args.sheet))

    try:
        window.run(app, script=[(10, show)], max_frames=70, screenshots_at={60: shot})
    finally:
        app.shutdown()
    print(f"Saved {shot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
