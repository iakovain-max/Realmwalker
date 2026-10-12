"""The arena: seeded fights for every creature, to see what the tactics do with it (docs/EXPANSIONS.md §4.7, Proof).

    .venv\\Scripts\\python.exe tools\\arena.py                 every creature, three scenarios, 4 seeds each
    .venv\\Scripts\\python.exe tools\\arena.py --creature wolf --runs 10
    .venv\\Scripts\\python.exe tools\\arena.py --groups        the encounter groups against parties of fitting level

For each creature it reports how often each of its options was used (attacks, breath, spells), how fights ended, and
how long an enemy turn took to decide (the budget: 150 ms at the 95th percentile, never 400 ms). Scenarios:
    close    the party right in front of it
    far      the party across the field
    bunched  the party standing together a little way off (for breath and area spells), one of its friends hurt
    surrounded  the party on every side of it, so that stepping back to shoot is not worth it
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realmwalker.core.rng import RNG  # noqa: E402
from realmwalker.rules import tactics  # noqa: E402
from realmwalker.rules.combat import FOE, PARTY, Battle, Env  # noqa: E402
from realmwalker.rules.creatures import spawn  # noqa: E402
from tools.balance import PARTY_CLASSES, load_tables, make_hero  # noqa: E402

SCENARIOS = ("close", "far", "bunched", "surrounded")


def party_level(cr: float) -> int:
    """A party of four of about this level makes a fair fight of one creature of this challenge."""
    return max(1, min(10, int(round(cr * 1.3)) or 1))


def setup(tables, creature: str, scenario: str, seed: int) -> Battle:
    d = tables.creatures[creature]
    level = party_level(float(d["cr"]))
    party = [make_hero(tables, PARTY_CLASSES[i % len(PARTY_CLASSES)], level, seed * 10 + i) for i in range(4)]
    rng = RNG(seed, f"arena/{creature}/{scenario}")
    foes = [spawn(tables, creature, rng, 1), spawn(tables, creature, rng, 2)]
    size = foes[0] and (3 if d["size"] in ("huge", "gargantuan") else (2 if d["size"] == "large" else 1))
    fx = 14 - size
    if scenario == "close":
        spots = {0: (fx - 1, 4), 1: (fx - 1, 6), 2: (fx - 2, 5), 3: (fx - 2, 3), 4: (fx, 4), 5: (fx, 7)}
    elif scenario == "far":
        spots = {0: (1, 4), 1: (1, 6), 2: (2, 5), 3: (1, 2), 4: (fx, 4), 5: (fx, 7)}
    elif scenario == "surrounded":
        cx, cy = 7, 4
        spots = {0: (cx - 1, cy), 1: (cx + size, cy), 2: (cx, cy - 1), 3: (cx, cy + size), 4: (cx, cy), 5: (fx, 8)}
    else:
        spots = {0: (5, 4), 1: (5, 5), 2: (6, 4), 3: (6, 5), 4: (fx, 4), 5: (fx, 7)}
    b = Battle(tables, party, foes, Env(), rng, spots=spots)
    for f in b.side(PARTY):
        f.auto = True
    b.start()
    if scenario == "bunched":
        hurt = b.side(FOE)[1]
        hurt.hp = max(1, hurt.max_hp // 3)  # a friend in trouble (for the healers)
    return b


def run(b: Battle, *, max_steps: int = 3000, check=None, clock=time.perf_counter) -> dict:
    """Play the fight out; what each foe used, and how long its turns took to decide (by `clock`: the tests time the
    thinking itself, time.thread_time, so that a busy PC does not count). `check(battle, fighter)` is called after
    every enemy turn (tests/test_tactics_coverage.py looks at the battle there)."""
    used: Counter = Counter()
    times: list[float] = []
    real = tactics.take_turn

    def timed(bb, f):
        start = clock()
        real(bb, f)
        if f.side == FOE:
            times.append(clock() - start)
            if check is not None:
                check(bb, f)
    tactics.take_turn = timed
    try:
        steps = 0
        while b.outcome is None and steps < max_steps:
            b.step()
            steps += 1
    finally:
        tactics.take_turn = real
    foes = {f.id: f for f in b.side(FOE)}
    for e in b.events:
        who = foes.get(e.get("by"))
        if who is None:
            continue
        if e["kind"] == "attack":
            used[f"attack:{e.get('weapon')}"] += 1
        elif e["kind"] == "cast":
            sp = e.get("spell")
            if sp in b.t.spells and sp in who.cdef.get("spells", []):
                used[f"cast:{sp}"] += 1
            else:  # a breath or a web: one of its own actions, cast like a spell
                a = next((a for a in who.cdef.get("attacks", []) if sp in (a.get("id"), a["name"])), None)
                used[f"attack:{a['name'] if a else sp}"] += 1
    return {"used": used, "times": times, "outcome": b.outcome, "steps": steps, "rounds": b.round}


def options_of(tables, creature: str) -> list[str]:
    """Every option the creature has that the tactics may choose (passive traits are not options)."""
    d = tables.creatures[creature]
    out = [f"attack:{a['name']}" for a in d.get("attacks", [])]
    for sid in d.get("spells", []):
        if sid in tables.spells and tables.spells[sid].get("cast") != "reaction":
            out.append(f"cast:{sid}")
    return list(dict.fromkeys(out))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--creature", action="append")
    ap.add_argument("--runs", type=int, default=4)
    args = ap.parse_args(argv)
    t = load_tables()
    creatures = args.creature or sorted(t.creatures.defs)
    all_times: list[float] = []
    for cid in creatures:
        used: Counter = Counter()
        outcomes: Counter = Counter()
        for scenario in SCENARIOS:
            for seed in range(args.runs):
                r = run(setup(t, cid, scenario, seed))
                used += r["used"]
                outcomes[r["outcome"]] += 1
                all_times += r["times"]
        unused = [o for o in options_of(t, cid) if not used.get(o)]
        print(f"{cid}: {dict(outcomes)}; used {dict(used)}" + (f"; never used {unused}" if unused else ""))
    if all_times:
        ms = sorted(x * 1000 for x in all_times)
        p95 = ms[int(len(ms) * 0.95) - 1]
        print(f"enemy turns: {len(ms)}, median {statistics.median(ms):.1f} ms, 95th percentile {p95:.1f} ms, "
              f"slowest {ms[-1]:.1f} ms (budget: 150 ms, never 400 ms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
