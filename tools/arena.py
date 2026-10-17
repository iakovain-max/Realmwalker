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
from realmwalker.rules import combat  # noqa: E402
from realmwalker.rules.combat import FOE, PARTY, Battle, Env  # noqa: E402
from realmwalker.rules.creatures import spawn  # noqa: E402
from tools.balance import PARTY_CLASSES, load_tables, make_hero  # noqa: E402

SCENARIOS = ("close", "far", "bunched", "surrounded")
# The other actions, counted when an enemy takes them on its own turn ("action:fly", "action:shove"...).
OTHER_ACTIONS = ("do_fly", "attack_object", "do_search", "do_hide", "do_shove", "do_grapple", "do_help", "do_dodge",
                 "do_ready", "do_dash", "do_disengage", "do_escape", "do_extinguish")


def party_level(cr: float) -> int:
    """A party of four of about this level makes a fair fight of one creature of this challenge."""
    return max(1, min(10, int(round(cr * 1.3)) or 1))


def setup(tables, creature: str, scenario: str, seed: int, *, second: str | None = None) -> Battle:
    """`second`: the other foe is this creature instead (an enemy caster's escort: Expansion 3 G.1)."""
    d = tables.creatures[creature]
    level = party_level(float(d["cr"]))
    party = [make_hero(tables, PARTY_CLASSES[i % len(PARTY_CLASSES)], level, seed * 10 + i) for i in range(4)]
    rng = RNG(seed, f"arena/{creature}/{scenario}")
    foes = [spawn(tables, creature, rng, 1), spawn(tables, second or creature, rng, 2)]
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
    if d.get("summon"):  # (a summoned spirit fights in its summoned shapes: each run and each foe another form)
        for i, f in enumerate(b.side(FOE)):
            _as_summoned(tables, f, creature, SCENARIOS.index(scenario) if scenario in SCENARIOS else 0, seed, i)
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
    originals = {name: getattr(combat.Battle, name) for name in OTHER_ACTIONS}

    def counted(name):
        def call(self, f, *a, **k):
            if f.side == FOE and self.current is f:
                used[f"action:{name[3:] if name.startswith('do_') else name}"] += 1
            return originals[name](self, f, *a, **k)
        return call
    for name in OTHER_ACTIONS:
        setattr(combat.Battle, name, counted(name))
    try:
        steps = 0
        while b.outcome is None and steps < max_steps:
            if b.pending_party() is not None:  # (a creature the party called in mid-fight plays on Auto too)
                for x in b.side(PARTY):
                    x.auto = True
            b.step()
            steps += 1
    finally:
        tactics.take_turn = real
        for name, fn in originals.items():
            setattr(combat.Battle, name, fn)
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


SUMMON_ATTACK, SUMMON_DC = 7, 15  # (a summoned spirit's caster: a 9th level wizard's numbers)


def summon_forms(tables, creature: str) -> list[str]:
    s = tables.creatures[creature]["summon"]
    return list(s.get("forms") or {"medium": None})  # (an animated object: a Medium one; its Slam is the same at
    # every size)


def _summoned_def(tables, creature: str, form: str) -> dict:
    from realmwalker.rules import allies

    s = tables.creatures[creature]["summon"]
    if "sizes" in s:
        return allies.object_def(tables, form, int(s["level"]), SUMMON_ATTACK, 4, False)
    return allies.summon_def(tables, creature, int(s["level"]), form, SUMMON_ATTACK, SUMMON_DC)


def _as_summoned(tables, f, creature: str, scenario_i: int, seed: int, i: int) -> None:
    """A summoned creature's numbers at its spell's level, in one of its forms (rules/allies.summon_def)."""
    from realmwalker.rules import allies

    forms = summon_forms(tables, creature)
    form = forms[(seed + scenario_i * 2 + i) % len(forms)]
    f.cdef = _summoned_def(tables, creature, form)
    f.slots = []
    f.creature.name = f.cdef["name"]
    f.creature.hp = f.creature.max_hp = int(f.cdef["hp"])


def options_of(tables, creature: str) -> list[str]:
    """Every option the creature has that the tactics may choose (passive traits are not options); a summoned
    creature's, in all its forms."""
    d = tables.creatures[creature]
    if d.get("summon"):
        from realmwalker.rules import allies

        out = []
        for form in summon_forms(tables, creature):
            sd = _summoned_def(tables, creature, form)
            out += [f"attack:{a['name']}" for a in sd["attacks"]] + [f"cast:{sid}" for sid in sd.get("spells", [])]
        return list(dict.fromkeys(out))
    out = [f"attack:{a['name']}" for a in d.get("attacks", [])]
    for sid in d.get("spells", []):
        from realmwalker.rules import spells as spellrules

        if sid in tables.spells and tables.spells[sid].get("cast") != "reaction" \
                and not spellrules.out_of_battle(tables.spells[sid]):  # (Thaumaturgy's use is outside a fight)
            out.append(f"cast:{sid}")
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- enemy casters (Expansion 3 G.1)
CASTER = "arena_caster"
CASTER_SLOTS = [4, 3, 3, 3, 2, 1, 1, 1, 1]  # (a 17th-level caster's slots, PHB)


def battle_spells(tables) -> list[str]:
    """Every spell an enemy caster could cast on its own turn in a fight: not a reaction, not one whose use is outside
    a fight, not a creature's own gift, an item's, a follow-up or Wish's copies."""
    from realmwalker.rules import spells as spellrules

    out = []
    for sid, sp in tables.spells.defs.items():
        if (sid.startswith("_") or sp.get("cast") == "reaction" or spellrules.out_of_battle(sp)
                or spellrules.has_op(sp, "identify")):
            continue  # (Identify is offered to nobody in a fight)
        if set(sp.get("classes", [])) & {"creature", "item", "again"} or sp.get("again_of"):
            continue
        out.append(sid)
    return sorted(out)


def caster_def(tables, spells: list[str], *, level: int = 17) -> dict:
    """A test caster: a war mage's numbers (a 17th-level caster's slots, DC 17, +9 to hit) knowing only these spells
    (cantrips at will). Registered under CASTER for spawn()."""
    import copy

    d = copy.deepcopy(tables.creatures.defs["cult_fanatic"])
    cantrips = [s for s in spells if tables.spells[s]["level"] == 0]
    d.update(name="war mage", plural="war mages", cr=9.0, xp=5000, hp="15d8+45", ac=12,
             abilities={"str": 10, "dex": 14, "con": 16, "int": 18, "wis": 18, "cha": 18}, morale="fanatic",
             ai={"role": "controller", "range": 30}, traits=[], gear=[], spells=list(spells),
             attacks=[{"id": "dagger", "name": "dagger", "item": "dagger", "bonus": 6, "damage": "1d4+2", "damage_type": "piercing",
                       "kind": "melee", "reach": False}])  # (a plain blade: its magic is its weapon)
    for k in ("multiattack", "multiattack_plan"):
        d.pop(k, None)
    d["spellcasting"] = {"ability": "int", "dc": 17, "attack": 9, "at_will": cantrips, "per_day": {},
                         "slots": CASTER_SLOTS[:max(1, (level + 1) // 2)], "self_only": False}
    tables.creatures.defs[CASTER] = d
    return d


def caster_setup(tables, spells: list[str], scenario: str, seed: int, *, second: str | None = None) -> Battle:
    caster_def(tables, spells)
    return setup(tables, CASTER, scenario, seed, second=second)


def spells_report(tables, spells: list[str], runs: int) -> int:
    """Each battle spell in a test caster's hands, in every scenario: how often the tactics cast it, and anything that
    broke."""
    import traceback

    never, broke = [], []
    all_times: list[float] = []
    for sid in spells:
        n = 0
        outcomes: Counter = Counter()
        for scenario in SCENARIOS:
            for seed in range(runs):
                try:
                    r = run(caster_setup(tables, [sid], scenario, seed))
                except Exception:  # (the report goes on; the trouble is listed)
                    broke.append((sid, scenario, seed, traceback.format_exc(limit=-3)))
                    continue
                n += r["used"].get(f"cast:{sid}", 0)
                outcomes[r["outcome"]] += 1
                all_times += r["times"]
        print(f"{sid} (level {tables.spells[sid]['level']}): cast {n}; {dict(outcomes)}")
        if not n:
            never.append(sid)
    print(f"\nnever cast ({len(never)}): {never}")
    for sid, scenario, seed, tb in broke:
        print(f"\nBROKE {sid} {scenario} seed {seed}:\n{tb}")
    if all_times:
        ms = sorted(x * 1000 for x in all_times)
        print(f"enemy turns: {len(ms)}, 95th percentile {ms[int(len(ms) * 0.95) - 1]:.1f} ms, slowest {ms[-1]:.1f} ms")
    return 1 if broke else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--creature", action="append")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--spells", action="store_true", help="every battle spell in a test caster's hands")
    ap.add_argument("--spell", action="append", help="these spells only (with --spells)")
    ap.add_argument("--shard", help="k/n: every n-th spell from the k-th (to run several side by side)")
    args = ap.parse_args(argv)
    t = load_tables()
    if args.spells or args.spell:
        spells = args.spell or battle_spells(t)
        if args.shard:
            k, n = (int(x) for x in args.shard.split("/"))
            spells = spells[k::n]
        return spells_report(t, spells, args.runs)
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
