"""Every creature's tactics, proven in the arena (tools/arena.py; docs/EXPANSIONS.md §4.7, Part C.5).

For each creature, seeded fights in every arena scenario, in which
- every option it has (its attacks, breath, webs and spells) is chosen at least once,
- the tactics never try anything the rules refuse, and never leave the battle in a state the rules forbid
  (an action spent twice, two bodies in one square, a spell slot below nothing),
- every fight comes to an end,
- an enemy turn is decided in under 150 ms at the 95th percentile and never takes 400 ms (plan §3).
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from realmwalker.rules import combat
from realmwalker.rules.combat import FOE
from realmwalker.world.tables import Tables
from tools import arena

pytestmark = pytest.mark.slow  # some three hundred fights

ROOT = Path(__file__).resolve().parents[1]
CREATURES = sorted(json.loads((ROOT / "data" / "creatures.json").read_text(encoding="utf-8"))["creatures"])
SEEDS = 2

# "creature/option": why the arena's scenarios do not bring it out. Empty: everything is used.
NOT_CHOSEN: dict[str, str] = {}

# What the tactics do through these must never be refused (a False back means they tried what the rules forbid).
TRIED = ("do_attack", "do_offhand", "do_move", "do_fly", "do_leave", "attack_object", "creature_cast")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def problems(b) -> list[str]:
    """What is wrong with the battle as it stands, by the rules."""
    out = []
    taken: dict = {}
    for x in b.fighters:
        if min(x.action, x.bonus, x.reaction, x.move_left) < 0:
            out.append(f"{x.name}: action {x.action}, bonus {x.bonus}, reaction {x.reaction}, move {x.move_left}")
        if not 0 <= x.hp <= x.max_hp or x.temp_hp < 0:
            out.append(f"{x.name}: {x.hp} of {x.max_hp} hit points (+{x.temp_hp})")
        if any(n < 0 for n in x.slots) or (x.creature is not None and any(n < 0 for n in x.creature.uses.values())):
            out.append(f"{x.name}: slots {x.slots}, uses {x.creature.uses if x.creature else {}}")
    for x in b.on_field():
        for c in x.cells:
            if not (0 <= c[0] < b.field.width and 0 <= c[1] < b.field.height):
                out.append(f"{x.name} off the field at {c}")
            other = taken.get(c)
            if other is not None and other is not x and not x.z and not other.z and \
                    "prone" not in x.conditions and "prone" not in other.conditions:
                out.append(f"{x.name} and {other.name} both standing in {c}")  # (stopped on the way through: Prone)
            taken.setdefault(c, x)
    return out


@pytest.mark.parametrize("creature", CREATURES)
def test_the_tactics_use_everything_a_creature_has_and_only_what_is_allowed(tables, creature, monkeypatch):
    refused: list[str] = []
    for name in TRIED:
        real = getattr(combat.Battle, name)

        def tried(self, f, *a, _real=real, _name=name, **k):
            r = _real(self, f, *a, **k)
            if r is False and f.side == FOE and self.current is f:
                refused.append(f"round {self.round}: {f.name} {_name} {a}")
            return r
        monkeypatch.setattr(combat.Battle, name, tried)
    used: Counter = Counter()
    times: list[float] = []
    broken: list[str] = []
    for scenario in arena.SCENARIOS:
        for seed in range(SEEDS):
            where = f"{scenario}, seed {seed}"
            b = arena.setup(tables, creature, scenario, seed)
            r = arena.run(b, check=lambda bb, f, where=where: broken.extend(
                f"{where}, round {bb.round}, after {f.name}: {p}" for p in problems(bb)))
            assert b.outcome is not None, f"{where}: the fight did not end in {r['steps']} steps"
            used += r["used"]
            times += r["times"]
    assert not refused, refused[:5]
    assert not broken, broken[:5]
    unused = [o for o in arena.options_of(tables, creature) if not used.get(o) and f"{creature}/{o}" not in NOT_CHOSEN]
    assert not unused, f"{creature} never chose {unused} (used {dict(used)})"
    ms = sorted(x * 1000 for x in times)
    assert ms, f"{creature} never took a turn"
    p95 = ms[max(0, int(len(ms) * 0.95) - 1)]
    assert p95 < 150 and ms[-1] < 400, f"{creature}: 95th percentile {p95:.0f} ms, slowest {ms[-1]:.0f} ms"


def test_every_creature_is_in_the_arena_and_every_exception_is_a_real_option(tables):
    assert CREATURES == sorted(tables.creatures.defs)
    for key in NOT_CHOSEN:
        creature, option = key.split("/", 1)
        assert option in arena.options_of(tables, creature), key
