"""Enemy casters (Expansion 3 G.1; docs/expansions/03-demigods-magics.md, G.1 How).

- Every spell a stat block names is the catalogue's, and usable in a fight (or its use is outside one).
- Every battle spell, in a test caster's hands (tools/arena.py caster_def: a war mage with a 17th-level caster's
  slots), is cast by the enemy's tactics in some arena scenario, by its worth (rules/engine/estimates), never refused,
  never leaving the battle broken; or the scene it needs is not in the arena (NOT_CAST, a reason each).
- A test caster with every battle spell of one level, and the cantrips, fights each scenario to its end within the
  turn budget (150 ms at the 95th percentile, never 400 ms, the thread's own time).
"""

import time
from collections import Counter

import pytest

from realmwalker.rules import combat
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE
from realmwalker.world.tables import Tables
from tests.test_tactics_coverage import TRIED, problems
from tools import arena


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)  # (its own: the test caster is registered in it)


def _spells() -> list[str]:
    from tools.balance import load_tables

    try:
        return arena.battle_spells(load_tables())
    except SystemExit:  # (the data is checked by its own tests)
        return []


SPELLS = _spells()
SEEDS = 2

# Spells the arena's scenes give the enemy no reason to cast (a reason each); each is weighed where its scene is, in
# the tests named.
NOT_CAST: dict[str, str] = {}


def test_every_caster_names_catalogue_spells_it_can_use(tables):
    from realmwalker.rules.engine import check

    assert not [p for p in check.problems(tables) if "casts the spell" in p]
    casters = 0
    for cid, d in tables.creatures.defs.items():
        if cid == arena.CASTER:
            continue
        for sid in d.get("spells", []):
            sp = tables.spells[sid]
            casters += 1
            assert sp.get("cast") != "reaction" or sid == "counterspell", f"{cid}: {sid}"
            sc = d["spellcasting"]
            assert sid in sc.get("at_will", []) or any(sid in v for v in sc.get("per_day", {}).values()) \
                or any(sid in p["spells"] for p in sc.get("shared", {}).values()) \
                or (sp["level"] and sc.get("slots")), f"{cid} has no way to cast {sid}"
            if spellrules.out_of_battle(sp):
                assert sid in ("thaumaturgy",) or sp.get("road_only") or sp.get("minutes"), f"{cid}: {sid}"
    assert casters >= 10


def _fight(tables, spells, scenario, seed, refused, broken, times, used):
    b = arena.caster_setup(tables, spells, scenario, seed)
    where = f"{scenario}, seed {seed}"
    r = arena.run(b, clock=time.thread_time, check=lambda bb, f: broken.extend(
        f"{where}, round {bb.round}, after {f.name}: {p}" for p in problems(bb)))
    assert b.outcome is not None, f"{where}: the fight did not end in {r['steps']} steps"
    used += r["used"]
    times += r["times"]


def _watch(monkeypatch, refused):
    for name in TRIED:
        real = getattr(combat.Battle, name)

        def tried(self, f, *a, _real=real, _name=name, **k):
            r = _real(self, f, *a, **k)
            if r is False and f.side == FOE and self.current is f:
                refused.append(f"round {self.round}: {f.name} {_name} {a}")
            return r
        monkeypatch.setattr(combat.Battle, name, tried)


@pytest.mark.slow
@pytest.mark.parametrize("sid", SPELLS)
def test_the_enemy_casts_each_battle_spell(tables, sid, monkeypatch):
    refused, broken, times = [], [], []
    used: Counter = Counter()
    _watch(monkeypatch, refused)
    for seed in range(SEEDS):
        for scenario in arena.SCENARIOS:
            _fight(tables, [sid], scenario, seed, refused, broken, times, used)
        if used.get(f"cast:{sid}"):
            break
    assert not refused, refused[:5]
    assert not broken, broken[:5]
    if sid in NOT_CAST:
        return
    assert used.get(f"cast:{sid}"), f"the enemy never cast {sid} (used {dict(used)})"


@pytest.mark.slow
@pytest.mark.parametrize("level", range(1, 10))
def test_a_caster_of_each_level_fights_without_hangs(tables, level, monkeypatch):
    spells = [s for s in SPELLS if tables.spells[s]["level"] in (0, level)]
    refused, broken, times = [], [], []
    used: Counter = Counter()
    _watch(monkeypatch, refused)
    for scenario in arena.SCENARIOS:
        _fight(tables, spells, scenario, level, refused, broken, times, used)
    assert not refused, refused[:5]
    assert not broken, broken[:5]
    cast = [k for k in used if k.startswith("cast:") and tables.spells[k[5:]]["level"] == level]
    assert cast, f"no spell of level {level} was cast ({dict(used)})"
    ms = sorted(x * 1000 for x in times)
    p95 = ms[max(0, int(len(ms) * 0.95) - 1)]
    assert p95 < 150 and ms[-1] < 400, f"level {level}: 95th percentile {p95:.0f} ms, slowest {ms[-1]:.0f} ms"


def test_every_exception_is_a_battle_spell():
    assert set(NOT_CAST) <= set(SPELLS)
