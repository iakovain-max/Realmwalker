"""Balance harness (M9): measure the design's balance targets instead of guessing at them.

    .venv\\Scripts\\python.exe tools\\balance.py            # every check, 200 runs each
    .venv\\Scripts\\python.exe tools\\balance.py --runs 50  # quicker
    .venv\\Scripts\\python.exe tools\\balance.py --only fights

The design (docs/DESIGN.md, section 16) asks for:
  - at level 1, two wolves or three bandits are a real threat;
  - a winter night without shelter or fire is dangerous;
  - an untreated serious wound is genuinely risky;
  - a careful player can still survive and prosper.

Everything here is headless and seeded, so the numbers are repeatable. `tests/test_balance.py` asserts that
they stay inside sensible bands; this script prints them, for tuning.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

if __package__ is None:  # running as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realmwalker.core.rng import RNG
from realmwalker.data.registry import DataRegistry
from realmwalker.paths import Paths
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.combat import PARTY, Battle, Env
from realmwalker.rules.creatures import spawn_group
from realmwalker.world.tables import Tables

PARTY_CLASSES = ("fighter", "rogue", "cleric", "wizard")
FIGHT_CASES = [("wolf_pack", 2), ("bandits", 3), ("goblins", 3), ("wolf_pack", 1), ("bandits", 1)]
# Heroes (Demigods & Magics part A): a party of three at level 11 and 17 against what the worst lands send, built for
# the land's danger by the XP budget (rules/encounter.py), a High band.
TIER_CASES = [(11, "troll", 9), (11, "berserkers", 9), (17, "troll", 10), (17, "ogre", 10)]


def load_tables() -> Tables:
    data, errors = DataRegistry.load(Paths().data)
    if errors:
        raise SystemExit("\n".join(errors))
    return Tables(data)


def make_hero(tables, cls: str, level: int, seed: int):
    b = CharacterBuilder(tables, RNG(seed, f"balance/{cls}"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("soldier" if cls in ("fighter", "rogue") else "acolyte")
    c = b.build()
    if level > 1:
        from realmwalker.rules.progression import level_up

        for _ in range(level - 1):
            level_up(c, tables, RNG(seed, "up"), auto=True)
    return c


def fight_once(tables, group: str, size: int, level: int, party_size: int, seed: int, danger: int | None = None) -> dict:
    """One fight on an open field, the party played by the game's own tactics (Auto): close in, strike what is
    worth striking, heal the fallen, throw spells where they catch only foes. With a `danger`, the band is built by the
    budget of a land that dangerous (High)."""
    from realmwalker.rules import encounter

    party = [make_hero(tables, PARTY_CLASSES[i % len(PARTY_CLASSES)], level, seed * 10 + i) for i in range(party_size)]
    rng = RNG(seed, "balance-fight")
    worth = encounter.land_budget(tables, danger, party_size, "high") if danger is not None else None
    foes = spawn_group(tables, group, rng, party_size=party_size, budget=worth)
    foes = foes[:size] if size else foes
    b = Battle(tables, party, foes, Env(), rng)
    for f in b.side(PARTY):
        f.auto = True
    b.start("A balance check.")
    for _ in range(6000):
        if b.outcome is not None:
            break
        b.step()
    result = b.result()
    ours = b.side(PARTY)
    hurt = [f for f in ours if f.hp <= f.max_hp // 3]
    return {
        "foes": len(foes),
        "outcome": result.outcome,
        "party_dead": len(result.party_dead),
        "wipe": all(not c.alive for c in party),
        "down": sum(1 for f in ours if f.state in ("down", "dead")),
        "hurt": len(hurt),
        "hp_left": sum(max(0, f.hp) for f in ours) / max(1, sum(f.max_hp for f in ours)),
    }


def fights(tables, runs: int) -> list[str]:
    out = []
    for group, size in FIGHT_CASES:
        for party_size in (1, 3):
            for level in (1, 3):
                rows = [fight_once(tables, group, size, level, party_size, seed) for seed in range(runs)]
                won = sum(1 for r in rows if r["outcome"] in ("victory", "parley"))
                died = sum(1 for r in rows if r["party_dead"] or r["wipe"])
                downed = sum(1 for r in rows if r["down"])
                hp = sum(r["hp_left"] for r in rows) / len(rows)
                out.append(f"  {group} x{size or '?'} vs {party_size} at level {level}: "
                           f"won {100 * won // len(rows)}%, someone down {100 * downed // len(rows)}%, "
                           f"someone dead {100 * died // len(rows)}%, hit points left {hp:.0%}")
    return out


def tier_fights(tables, runs: int) -> list[str]:
    out = []
    for level, group, danger in TIER_CASES:
        rows = [fight_once(tables, group, 0, level, 3, seed, danger=danger) for seed in range(runs)]
        won = sum(1 for r in rows if r["outcome"] in ("victory", "parley"))
        died = sum(1 for r in rows if r["party_dead"] or r["wipe"])
        downed = sum(1 for r in rows if r["down"])
        hp = sum(r["hp_left"] for r in rows) / len(rows)
        foes = sum(r["foes"] for r in rows) / len(rows)
        out.append(f"  {group} (danger {danger}, {foes:.1f} of them) vs 3 at level {level}: won {100 * won // len(rows)}%, "
                   f"someone down {100 * downed // len(rows)}%, someone dead {100 * died // len(rows)}%, "
                   f"hit points left {hp:.0%}")
    return out


# ---------------------------------------------------------------------------- the body
def wild_spot(world, tables, target: float = -5.0):
    """A tile out in the wilds at about this temperature: no roof, no town, no help."""
    import numpy as np

    temp = world.temperature.astype(float)
    score = np.abs(temp - target)
    for s in world.settlements:
        score[max(0, s.x - 2): s.x + 3, max(0, s.y - 2): s.y + 3] = 10**6
    passable = tables.biomes.passable[world.biome]
    score[~passable] = 10**6
    score[world.biome_ids.index("high_mountains") == world.biome] = 10**6
    x, y = np.unravel_index(int(np.argmin(score)), score.shape)
    return int(x), int(y)


def winter_night(tables, runs: int, *, fire: bool, tent: bool, clothes: str = "warm") -> dict:
    """A night outdoors in deep winter, asleep, far from any roof. How many wake up?"""
    from realmwalker.game.state import new_game
    from realmwalker.rules.inventory import add_item, equip, remove_item
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    world = WorldGenerator(WorldOptions("Coldland", 7, "small"), tables).generate()
    spot = wild_spot(world, tables)
    winter = next((i for i, day in enumerate(range(0, tables.calendar.days_per_year))
                   if tables.calendar.at(day * 1440).season == "winter"), 0)
    dead = hurt = cold = 0
    for seed in range(runs):
        game = new_game(copy.deepcopy(world), tables)
        c = game.leader
        game.player.x, game.player.y = spot
        if clothes == "poor":
            for it in list(c.inventory):
                if tables.items.get(it.def_id)["category"] == "clothing":
                    remove_item(c, it.uid)
        else:
            for item in ("wool_cloak", "wool_tunic", "wool_trousers", "boots", "wool_gloves"):
                if item in tables.items:
                    it = add_item(c, tables.items, item)
                    if it is not None:
                        equip(c, tables.items, it.uid)
        # Deep winter, late evening. The minute differs per run: the body and health streams are keyed on the
        # world clock, so without this every run would roll exactly the same dice.
        game.world.time = (winter + 20) * 1440 + 21 * 60 + seed
        if fire or tent:
            from realmwalker.game.camp import Camp

            p = game.player
            game.camp = Camp(p.x, p.y, p.local_key, p.lx, p.ly, since=game.world.time, fire=fire, tent=tent)
        game.survival = True
        game.pass_time(8 * 60, "sleep")
        if not c.alive or game.over is not None:
            dead += 1
        elif c.exhaustion >= 2:
            hurt += 1
        elif c.body_heat <= -40:
            cold += 1
    return {"dead": dead, "hurt": hurt, "cold": cold, "runs": runs}


def untreated_wound(tables, runs: int, *, treat: bool) -> dict:
    """A serious, dirty wound, left alone (or bound and cleaned), for a week of resting indoors with food
    and water (so that what is measured is the wound, and nothing else)."""
    from realmwalker.game.state import new_game
    from realmwalker.rules.wounds import make_wound
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    world = WorldGenerator(WorldOptions("Woundland", 3, "small"), tables).generate()
    dead = sick = fine = 0
    for seed in range(runs):
        game = new_game(copy.deepcopy(world), tables)
        game.survival = True
        game.world.time += seed  # each run rolls its own dice (the health stream is keyed on the clock)
        c = game.leader
        rng = RNG(seed, "wound")
        wound = make_wound("torso", "slashing", 2, rng, now=game.world.time)
        if treat:
            wound.bandaged = True
            wound.cleaned = True
        c.wounds.append(wound)
        c.hp = max(1, c.max_hp // 2)
        for _ in range(7):  # a week of resting days and sleeping nights, fed and watered
            for minutes, doing in ((16 * 60, "rest"), (8 * 60, "sleep")):
                c.hunger = min(c.hunger, 20.0)
                c.thirst = min(c.thirst, 20.0)
                c.body_heat = max(c.body_heat, 0.0)
                game.pass_time(minutes, doing)
                if not c.alive or game.over is not None:
                    break
            if not c.alive or game.over is not None:
                break
        if not c.alive or game.over is not None:
            dead += 1
        elif any(w.infection > 0 for w in c.wounds) or c.diseases:
            sick += 1
        else:
            fine += 1
    return {"dead": dead, "sick": sick, "fine": fine, "runs": runs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Balance checks for Realmwalker")
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--only", choices=["fights", "cold", "wounds"], default=None)
    args = ap.parse_args(argv)
    tables = load_tables()
    if args.only in (None, "fights"):
        print("Fights (on an open field, the party on Auto)")
        for line in fights(tables, args.runs):
            print(line)
        print("Heroes against the worst lands (a High band for the land's danger, the party on Auto)")
        for line in tier_fights(tables, max(10, args.runs // 4)):
            print(line)
    if args.only in (None, "cold"):
        print("A winter night in the open, asleep, 8 hours")
        for label, kw in (("no fire, no tent", {"fire": False, "tent": False}),
                          ("a fire", {"fire": True, "tent": False}),
                          ("fire and tent", {"fire": True, "tent": True}),
                          ("poor clothes, no fire", {"fire": False, "tent": False, "clothes": "poor"})):
            r = winter_night(tables, max(10, args.runs // 10), **kw)
            print(f"  {label}: died {100 * r['dead'] // r['runs']}%, exhausted {100 * r['hurt'] // r['runs']}%, "
                  f"badly chilled {100 * r['cold'] // r['runs']}%")
    if args.only in (None, "wounds"):
        print("A serious, dirty wound for a week")
        for label, treat in (("untreated", False), ("bandaged and cleaned", True)):
            r = untreated_wound(tables, max(10, args.runs // 10), treat=treat)
            print(f"  {label}: died {100 * r['dead'] // r['runs']}%, still sick {100 * r['sick'] // r['runs']}%, "
                  f"well {100 * r['fine'] // r['runs']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
