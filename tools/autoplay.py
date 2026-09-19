"""Headless autoplay bot: plays the game with random but sensible input and checks invariants.

    python tools/autoplay.py                 # both runs: AI off, then mocked AI
    python tools/autoplay.py --ai mock --turns 10000 --seed 7

Every screen lists sensible keys for the bot (Screen.autoplay_keys); the bot mixes those with
random keys, mouse moves and clicks on real buttons. It fails if the game reports any error,
if an invariant breaks, or if anything is written to errors.log. As milestones add systems,
the invariant checks grow with them.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import string
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tcod.console  # noqa: E402

from realmwalker.app import App  # noqa: E402
from realmwalker.config import AUTOSAVE_CHOICES, FONT_SIZES, VERBOSITY_LEVELS, Settings  # noqa: E402
from realmwalker.core.logs import count_error_lines  # noqa: E402
from realmwalker.ui.input import KeyEvent, MouseEvent  # noqa: E402
from tools.mock_player2 import MockPlayer2  # noqa: E402

CONSOLE_SIZES = [(80, 30), (100, 34), (120, 45), (192, 54)]
SPECIAL_KEYS = ["up", "down", "left", "right", "enter", "escape", "tab", "backspace", "pageup", "pagedown",
                "home", "end", "f1", "upleft", "downright", "wait"]
UNREACHABLE_AI = "http://127.0.0.1:9/v1"  # nothing listens here: behaves like Player2 being closed


@dataclass
class AutoplayReport:
    ai_mode: str
    turns: int = 0
    restarts: int = 0
    errors: list[str] = field(default_factory=list)
    screens: Counter = field(default_factory=Counter)
    ai_stats: dict = field(default_factory=dict)
    mock_calls: int = 0
    save_checks: int = 0
    game_turns: int = 0
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = [
            f"Autoplay ({self.ai_mode} AI): {self.turns} turns, {self.restarts} restarts, {self.elapsed:.1f} s",
            f"  screens visited: {dict(self.screens.most_common())}",
            f"  AI requests: {self.ai_stats}  mock chat calls: {self.mock_calls}",
            f"  turns inside a game: {self.game_turns}  save/load round trips checked: {self.save_checks}",
            "  RESULT: " + ("OK" if self.ok else f"FAILED ({len(self.errors)} problems)"),
        ]
        lines += [f"    - {e}" for e in self.errors[:20]]
        return "\n".join(lines)


def _pick_event(app: App, rng: random.Random, console: tcod.console.Console):
    roll = rng.random()
    top = app.top
    if roll < 0.60 and top is not None:
        keys = top.autoplay_keys() or [KeyEvent("escape")]
        return rng.choice(keys)
    if roll < 0.72:
        return KeyEvent(rng.choice(string.ascii_letters + string.digits + " ?.,<>`"))
    if roll < 0.82:
        return KeyEvent(rng.choice(SPECIAL_KEYS))
    if roll < 0.84:
        return KeyEvent(rng.choice(["=", "-"]), ctrl=True)
    if roll < 0.92 and app.regions:
        region = rng.choice(app.regions)
        x = region.x + rng.randrange(max(1, region.w))
        y = region.y + rng.randrange(max(1, region.h))
        kind = rng.choice(["click", "click", "move", "wheel"])
        return MouseEvent(kind, x, y, button=rng.choice(["left", "left", "right"]), dy=rng.choice([-1, 1]))
    return MouseEvent("move", rng.randrange(console.width), rng.randrange(console.height))


def _check_invariants(app: App, report: AutoplayReport, turn: int) -> None:
    def fail(msg: str) -> None:
        if len(report.errors) < 50:
            report.errors.append(f"turn {turn}: {msg}")

    if app.error_count:
        fail(f"the game reported {app.error_count} recovered error(s); see errors.log")
        app.error_count = 0
    if not app.screens:
        fail("screen stack is empty")
    s = app.settings
    if s.font_size not in FONT_SIZES or s.verbosity not in VERBOSITY_LEVELS or s.autosave_minutes not in AUTOSAVE_CHOICES:
        fail(f"settings out of range: {s}")
    for key, value in app.ai.stats.items():
        if not isinstance(value, int) or value < 0:
            fail(f"AI stat {key} has invalid value {value!r}")
    game = app.game
    if game is not None:
        w, p = game.world, game.player
        if not w.in_bounds(p.x, p.y):
            fail(f"player off the world at {(p.x, p.y)}")
        elif not app.tables.biomes.passable[game._biome_remap[w.biome[p.x, p.y]]]:
            fail(f"player standing in impassable {game.biome_key(p.x, p.y)} at {(p.x, p.y)}")
        if game.in_local:
            lm = game.local
            if lm is None or not lm.in_bounds(p.lx, p.ly):
                fail("player outside the local map")
            else:
                t = int(game.remap_for(lm)[lm.terrain[p.lx, p.ly]])
                if not app.tables.terrain.walk[t]:
                    fail(f"player inside solid {app.tables.terrain.ids[t]} on a local map")
        key = w.meta.id
        last = _LAST_TIME.get(key)
        if last is not None and w.time < last:
            fail(f"time ran backwards: {last} -> {w.time}")
        _LAST_TIME[key] = w.time
        if p.explored.shape != (w.width, w.height):
            fail("explored map has the wrong shape")


_LAST_TIME: dict[str, int] = {}


def _check_save_round_trip(app: App, report: AutoplayReport, turn: int) -> None:
    """Saving and loading must give back exactly the same game."""
    from realmwalker.game import save

    game = app.game
    if game is None:
        return
    folder = save.save_game(game, app.paths.saves)
    loaded = save.load_game(folder, app.tables)
    a, b = save.world_entries(game.world), save.world_entries(loaded.world)
    c, d = save.character_entries(game), save.character_entries(loaded)
    diffs = [k for k in a if k != "manifest.json" and a[k] != b.get(k)]
    diffs += [k for k in c if k != "manifest.json" and c[k] != d.get(k)]
    if diffs:
        report.errors.append(f"turn {turn}: save/load round trip differs in {diffs[:5]}")
    report.save_checks += 1


def run_autoplay(*, turns: int = 3000, seed: int = 1, ai: str = "off", home: Path | None = None) -> AutoplayReport:
    report = AutoplayReport(ai_mode=ai)
    own_home = home is None
    home = Path(tempfile.mkdtemp(prefix="realmwalker_autoplay_")) if home is None else home
    mock = MockPlayer2("chaos", seed=seed).start() if ai == "mock" else None
    config = {"player2_base_url": mock.base_url if mock else UNREACHABLE_AI, "debug_console": True}
    settings = {"ai_enabled": ai == "mock"}
    rng = random.Random(seed)
    ai_totals: Counter = Counter()
    start = time.monotonic()

    def new_app() -> App:
        app = App(home=home, headless=True, config_overrides=config, settings_overrides=settings)
        app.ai.retry_interval = 0.5
        return app

    app = new_app()
    console = tcod.console.Console(*CONSOLE_SIZES[0], order="F")
    try:
        for turn in range(turns):
            if turn % 200 == 0:
                console = tcod.console.Console(*rng.choice(CONSOLE_SIZES), order="F")
            ev = _pick_event(app, rng, console)
            app.handle_event(ev)
            if mock is not None and rng.random() < 0.03:
                app.ai.wait_idle(5.0)
            app.update()
            app.render(console)
            app.window_requests.clear()
            if app.top is not None:
                report.screens[type(app.top).__name__] += 1
            _check_invariants(app, report, turn)
            if app.game is not None:
                report.game_turns += 1
                if report.game_turns % 400 == 0:
                    _check_save_round_trip(app, report, turn)
            report.turns = turn + 1
            if not app.running:
                ai_totals.update(app.ai.stats)
                app.shutdown()
                report.restarts += 1
                app = new_app()
        app.ai.wait_idle(10.0)
        app.update()
        _check_invariants(app, report, report.turns)
        ai_totals.update(app.ai.stats)
        report.ai_stats = dict(ai_totals)
    finally:
        app.shutdown()
        if mock is not None:
            report.mock_calls = mock.chat_calls
            mock.stop()

    # Settings written to disk must load back identically.
    loaded = Settings.load(app.paths.settings_file)
    if loaded != app.settings:
        report.errors.append(f"settings did not round-trip: saved {app.settings}, loaded {loaded}")
    logged = count_error_lines(app.paths.logs)
    if logged:
        tail = (app.paths.logs / "errors.log").read_text(encoding="utf-8", errors="replace")[-1500:]
        report.errors.append(f"{logged} error line(s) in errors.log:\n{tail}")
    report.elapsed = time.monotonic() - start
    if own_home and report.ok:
        shutil.rmtree(home, ignore_errors=True)
    elif not report.ok:
        report.errors.append(f"logs kept in {home}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Realmwalker headless autoplay bot")
    parser.add_argument("--turns", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--ai", choices=["off", "mock", "both"], default="both")
    parser.add_argument("--json", action="store_true", help="print a machine-readable result line")
    args = parser.parse_args()
    modes = ["off", "mock"] if args.ai == "both" else [args.ai]
    ok = True
    for mode in modes:
        report = run_autoplay(turns=args.turns, seed=args.seed, ai=mode)
        print(report.summary())
        if args.json:
            print(json.dumps({"mode": mode, "ok": report.ok, "turns": report.turns, "errors": len(report.errors)}))
        ok = ok and report.ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
