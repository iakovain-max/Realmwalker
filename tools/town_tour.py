"""A tour of towns, for looking at them: makes a world, then visits a settlement of each people (and a dwarven hold
and an elven hall) on foot, by day and by night, saving a screenshot of each. AI off; nothing is saved.

    .venv\\Scripts\\python.exe tools\\town_tour.py [--seed 21] [--size large] [--out build\\shots\\towns]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--size", default="large")
    ap.add_argument("--out", default=str(ROOT / "build" / "shots" / "towns"))
    ap.add_argument("--night", action="store_true", help="also a shot of each by night")
    args = ap.parse_args(argv)
    os.environ.setdefault("SDL_AUDIO_DRIVER", "dummy")
    from realmwalker.app import App
    from realmwalker.game import encounters, events
    from realmwalker.game.state import new_game
    from realmwalker.ui import window
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    app = App(home=tempfile.mkdtemp(prefix="realmwalker-tour-"), settings_overrides={"ai_enabled": False})
    encounters.encounter_chance = lambda *a, **k: 0.0
    events.event_chance = lambda *a, **k: 0.0
    world = WorldGenerator(WorldOptions("Tour", args.seed, args.size, history=100), app.tables).generate()
    game = new_game(world, app.tables)
    game.survival = False
    app.start_game(game)
    picks = []
    seen = set()
    for s in sorted(world.settlements, key=lambda s: -s.population):
        style = app.tables.cultures.town_style(s.culture) if s.culture in app.tables.cultures.ids else s.culture
        key = (style, s.kind in ("town", "city", "hold", "elfhall"))
        if key not in seen:
            seen.add(key)
            picks.append((s, style))
    steps, shots = [], {}
    frame = 20
    for s, style in picks:
        def go(app, s=s, night=False):
            g = app.game
            if g.in_local:
                g.player.local_key = None
            g.player.x, g.player.y = s.x, s.y
            day = g.world.time // 1440
            g.world.time = day * 1440 + (23 * 60 if night else 11 * 60)
            g.enter_local()

        def deep_in(app, s=s, night=False, go=go):
            """Into the heart of the place (a hold's halls, a city's middle), away from where you came in."""
            import numpy as np

            go(app, s, night)
            g = app.game
            lm = g.local
            walk = g.tables.terrain.walk[g.remap_for(lm)[lm.terrain]]
            pts = [(int(x), int(y)) for x, y in np.argwhere(walk) if lm.building_at(int(x), int(y)) is None
                   and lm.under_rock(int(x), int(y)) == bool(lm.meta.get("underground"))]
            cx, cy = lm.width // 2, lm.height // 2
            g.player.lx, g.player.ly = min(pts, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)

        name = f"{style}_{s.kind}_{s.name.replace(' ', '_')}"
        steps.append((frame, go))
        shots[frame + 12] = out / f"{name}.png"
        frame += 20
        if args.night:
            steps.append((frame, lambda app, s=s, go=go: go(app, s, True)))
            shots[frame + 12] = out / f"{name}_night.png"
            frame += 20
        if s.kind in ("hold", "city"):
            steps.append((frame, deep_in))
            shots[frame + 12] = out / f"{name}_inside.png"
            frame += 20
            if args.night:
                steps.append((frame, lambda app, s=s, deep_in=deep_in: deep_in(app, s, True)))
                shots[frame + 12] = out / f"{name}_inside_night.png"
                frame += 20
    try:
        window.run(app, script=steps, max_frames=frame + 10, screenshot_to=out / "last.png", screenshots_at=shots)
    finally:
        app.shutdown()
    print("\n".join(str(p) for p in shots.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
