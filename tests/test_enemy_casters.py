"""Enemy casters (Expansion 3 G.1; docs/expansions/03-demigods-magics.md, G.1 How).

- Every spell a stat block names is the catalogue's, and usable in a fight (or its use is outside one).
- Every battle spell, in a test caster's hands (tools/arena.py caster_def: a war mage with a 17th-level caster's
  slots), is cast by the enemy's tactics in some arena scenario, by its worth (rules/engine/estimates), never refused,
  never leaving the battle broken; or the scene it needs is not in the arena (NOT_CAST, a reason each).
- A test caster with every battle spell of one level, and the cantrips (35 to 72 spells: three times the longest list
  a stat block prints), fights each scenario to its end, nothing refused or broken, an enemy turn never 400 ms; a
  caster with a stat block's list (16 or 24 spells drawn from them all) keeps the plan's budget (150 ms at the 95th
  percentile, never 400 ms). All in the thread's own time.
"""

import time
from collections import Counter

import pytest

from realmwalker.rules import combat, tactics
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.engine import durations
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

# Spells the arena's scenes give the enemy no reason to cast (a reason each). Those marked "a scene" are cast in a
# scene of their own below (SCENES); the rest are weighed where their scene is, in the tests named.
NOT_CAST: dict[str, str] = {
    # the scene below
    "animal_shapes": "a scene: two war mages cast spells, and a caster is never willing (the escort takes it)",
    "revivify": "a scene: nobody on the war mages' side has died yet when the fight turns",
    "lesser_restoration": "a scene: nobody on the war mages' side is poisoned, paralysed, blinded or deafened",
    "greater_restoration": "a scene: nobody on the war mages' side is charmed or petrified",
    "divine_word": "a scene: a party of level 10 stands above 50 hit points until the fight is all but over",
    # the field (as tests/test_catalogue.py's NO_USE and tests/test_spells_outside.py, test_spells_road2-4.py)
    "light": "every arena field is lit",
    "dancing_lights": "every arena field is lit",
    "daylight": "every arena field is lit, and nobody lays magical darkness",
    "darkvision": "every arena field is lit",
    "see_invisibility": "nobody in the party is invisible",
    "true_seeing": "nobody in the party is invisible, hidden or in magical darkness",
    "detect_thoughts": "nobody in the party is invisible or hidden",
    "nondetection": "nobody in the party senses thoughts",
    "jump": "nothing on the field to leap over",
    "spider_climb": "nothing on the field to climb",
    "water_walk": "no deep water on the field",
    "alter_self": "no deep water on the field (on the road it is a disguise)",
    "tree_stride": "no trees on the field",
    "pass_without_trace": "nobody on the war mages' side is hiding",
    "longstrider": "everyone is within a walk of the fight",
    "enhance_ability": "nobody on the war mages' side grapples or shoves",
    "guidance": "nobody on the war mages' side makes an ability check in these fights",
    "mind_blank": "nobody in the party charms or reads minds",
    # the party
    "protection_from_evil_and_good": "the party are humanoids: no aberration, celestial, elemental, fey, fiend or undead",
    "dispel_evil_and_good": "the party are humanoids: no celestial, elemental, fey, fiend or undead",
    "animal_friendship": "no beast fights for the party here",
    "dominate_beast": "no beast fights for the party here",
    # creatures
    "spare_the_dying": "a creature at 0 hit points dies: nobody on the war mages' side lies dying",
    "shillelagh": "a creature's blows are its stat block's: Shillelagh needs a character's club or staff",
}


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
    assert ms[-1] < 400, f"level {level}: the slowest turn took {ms[-1]:.0f} ms"


@pytest.mark.slow
@pytest.mark.parametrize("size,k", [(16, 0), (16, 1), (24, 0), (24, 1)])
def test_a_caster_with_a_stat_blocks_spells_keeps_the_turn_budget(tables, size, k, monkeypatch):
    from realmwalker.core.rng import RNG

    pick = RNG(7, "sizes").child(f"{size}/{k}")
    spells = sorted({SPELLS[pick.randint(0, len(SPELLS) - 1)] for _ in range(size)})
    refused, broken, times = [], [], []
    used: Counter = Counter()
    _watch(monkeypatch, refused)
    for scenario in arena.SCENARIOS:
        _fight(tables, spells, scenario, 1, refused, broken, times, used)
    assert not refused, refused[:5]
    assert not broken, broken[:5]
    ms = sorted(x * 1000 for x in times)
    p95 = ms[max(0, int(len(ms) * 0.95) - 1)]
    assert p95 < 150 and ms[-1] < 400, f"{spells}: 95th percentile {p95:.0f} ms, slowest {ms[-1]:.0f} ms"


def test_every_exception_is_a_battle_spell():
    assert set(NOT_CAST) <= set(SPELLS)
    assert {s for s, why in NOT_CAST.items() if why.startswith("a scene")} == set(SCENES)


# ------------------------------------------------------------------ scenes of their own
def _escort_poisoned(b, mage, escort):
    durations.give(b, escort, "poisoned", rounds=10)


def _escort_charmed(b, mage, escort):
    durations.give(b, escort, "charmed", rounds=10, source=b.side(PARTY)[0])


def _escort_dead(b, mage, escort):
    b._kill(escort, "the test")


def _party_hurt(b, mage, escort):
    for x in b.side(PARTY):
        x.hp = 25


def _nothing(b, mage, escort):
    pass


# spell: (the arena's scenario, what is done to the field first); the war mage stands with an orc, its escort, who
# casts nothing
SCENES = {
    "animal_shapes": ("bunched", _nothing),
    "revivify": ("bunched", _escort_dead),
    "lesser_restoration": ("bunched", _escort_poisoned),
    "greater_restoration": ("bunched", _escort_charmed),
    "divine_word": ("close", _party_hurt),  # (its 30 feet round the caster)
}


@pytest.mark.parametrize("sid", sorted(SCENES))
def test_the_enemy_casts_a_spell_where_its_scene_is(tables, sid):
    scenario, scene = SCENES[sid]
    b = arena.caster_setup(tables, [sid], scenario, 0, second="orc")
    mage, escort = b.side(FOE)
    escort.hp = escort.max_hp  # (the arena's hurt friend: here only what the scene does)
    scene(b, mage, escort)
    b.order = [mage.id] + [x for x in b.order if x != mage.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(mage)
    tactics.take_turn(b, mage)
    cast = [e for e in b.events if e["kind"] == "cast" and e.get("by") == mage.id and e.get("spell") == sid]
    assert cast, f"the war mage did not cast {sid}"
    assert not problems(b), problems(b)
    if sid == "animal_shapes":
        assert escort.shape is not None and b.t.creatures[escort.creature.def_id]["kind"] == "beast"
    elif sid == "revivify":
        assert escort.state == "fighting" and escort.hp == 1 and escort.creature.alive
    elif sid == "lesser_restoration":
        assert "poisoned" not in escort.conditions
    elif sid == "greater_restoration":
        assert "charmed" not in escort.conditions
