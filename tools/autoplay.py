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
    fights: int = 0
    events: int = 0
    talks: int = 0
    battle_turns: int = 0
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
            f"  fights started by the bot: {self.fights}  travel events: {self.events}  talks: {self.talks}  "
            f"turns spent in battle: {self.battle_turns}",
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
        for member in game.party:
            if not 0 <= member.hp <= member.max_hp:
                fail(f"{member.name} has {member.hp}/{member.max_hp} hit points")
            if member.money < 0:
                fail(f"{member.name} has negative money")
            uids = [it.uid for it in member.inventory]
            if len(uids) != len(set(uids)):
                fail(f"{member.name} has two items with the same id")
            if any(it.qty <= 0 for it in member.inventory):
                fail(f"{member.name} carries an item stack of zero or fewer")
            for need in ("hunger", "thirst", "fatigue", "dirt", "wet", "intoxication"):
                value = getattr(member, need)
                if not 0 <= value <= 100:
                    fail(f"{member.name} has {need} {value}")
            if not -100 <= member.body_heat <= 100 or not 0 <= member.blood <= 100:
                fail(f"{member.name} has body heat {member.body_heat} and blood {member.blood}")
            if not 0 <= member.exhaustion <= 6:
                fail(f"{member.name} has exhaustion {member.exhaustion}")
            for w in member.wounds:
                if not 1 <= w.severity <= 3 or not 0 <= w.bleed <= 3 or not 0 <= w.infection <= 100:
                    fail(f"{member.name} has an impossible wound {w}")
            for d in member.diseases:
                if d.get("phase") not in ("incubating", "sick", "dormant", "immune") or d.get("id") not in app.tables.diseases:
                    fail(f"{member.name} has an impossible disease {d}")
            if any(v < -1e-6 for k, v in member.effects.items() if not k.endswith("_clean")):
                fail(f"{member.name} has an expired timed effect {member.effects}")
            from realmwalker.rules.inventory import container_capacity

            for it in member.inventory:
                if it.fill < 0 or it.fill > container_capacity(app.tables.items, it) + 1e-6:
                    fail(f"{member.name}'s {it.def_id} holds {it.fill} pints")
            equipped = list(member.equipped.values())
            if len(equipped) != len(set(equipped)):
                fail(f"{member.name} wears one item in two places")
            if any(member.item(uid) is None for uid in equipped):
                fail(f"{member.name} has something equipped that is not in the pack")
        lm = game.local
        if lm is not None:
            for pile in lm.items.values():
                if any(it.qty <= 0 for it in pile):
                    fail("an item on the ground has zero quantity")
            walk = app.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
            for a in lm.actors:
                if not lm.in_bounds(a.x, a.y) or not walk[a.x, a.y]:
                    fail(f"creatures of {a.group} stand in a wall at {(a.x, a.y)}")
                if not a.creatures:
                    fail(f"an empty band of {a.group} is on the map")
                if any(not 0 < c.hp <= c.max_hp for c in a.creatures):
                    fail(f"a creature of {a.group} has impossible hit points")
            if lm.kind == "settlement":
                from realmwalker.game.people import npcs_in, settlement_here

                here = settlement_here(game)
                spots = set()
                town = game.world.towns.get(here.id) if here is not None else None
                for shop in (town.shops.values() if town is not None else []):
                    if shop["coin"] < 0 or any(q < 0 for q in shop["stock"].values()):
                        fail(f"a shop in {here.name} has negative coin or stock")
                for npc in npcs_in(game.world, here.id) if here is not None else []:
                    if not -100 <= npc.disposition <= 100:
                        fail(f"{npc.name} has disposition {npc.disposition}")
                    if npc.alive and npc.present:
                        if not lm.in_bounds(npc.x, npc.y) or not walk[npc.x, npc.y]:
                            fail(f"{npc.name} the {npc.title} stands in a wall at {(npc.x, npc.y)}")
                        if (npc.x, npc.y) in spots:
                            fail(f"two townsfolk stand at {(npc.x, npc.y)}")
                        spots.add((npc.x, npc.y))
        b = game.battle
        if b is not None:
            if b.outcome is None and not b.order:
                fail("a battle is running without a turn order")
            for f in b.fighters:
                if not 0 <= f.hp <= f.max_hp:
                    fail(f"{f.name} has {f.hp}/{f.max_hp} hit points in battle")
                if f.state not in ("fighting", "fleeing", "down", "dead", "fled", "surrendered"):
                    fail(f"{f.name} is in an unknown state {f.state!r}")
        if not game.leader.alive and game.over is None and b is None and game.aftermath is None:
            fail("the leader is dead but the game goes on")
        if game.over is None and any(not c.alive for c in game.party) and b is None and game.aftermath is None:
            fail("a dead companion is still in the party")


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


def _start_a_fight(app: App, rng: random.Random, report: AutoplayReport) -> None:
    """Random walking rarely meets trouble, so now and then trouble is sent to find the bot."""
    from realmwalker.game.encounters import make_encounter
    from realmwalker.ui.screens.game_screen import GameScreen

    game = app.game
    if game is None or game.busy or not isinstance(app.top, GameScreen):
        return
    roll = rng.random()
    if roll < 0.3:
        from realmwalker.game.people import npcs_in

        here = game.world.settlement_at(game.player.x, game.player.y)
        if here is None:
            here = rng.choice(game.world.settlements)
            game.player.local_key = None
            game.player.x, game.player.y = here.x, here.y
        if not game.in_local:
            game.enter_local()
        people = [n for n in npcs_in(game.world, here.id) if n.alive and n.present]
        if people:
            game.talk_to = rng.choice(people).id
            report.talks += 1
        return
    if roll < 0.55:
        from realmwalker.game.events import make_event

        game.event = make_event(game, rng.choice(sorted(app.tables.travel_events)))
        report.events += 1
        return
    group = rng.choice(sorted(app.tables.creatures.encounters))
    game.encounter = make_encounter(game, group, game.world.rng.child(f"autoplay/{game.world.time}/{group}"))
    report.fights += 1


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
                if report.game_turns % 150 == 0:
                    _start_a_fight(app, rng, report)
                if app.game is not None and app.game.battle is not None:
                    report.battle_turns += 1
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
