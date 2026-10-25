"""Check hand-made vignettes (Expansion 6 C.9): the data reads right, each can be forged from what its need finds in
two test worlds, and every line it can say fills with no "{" left.

    .venv/Scripts/python.exe tools/vignette_check.py              every vignette
    .venv/Scripts/python.exe tools/vignette_check.py v_drowned_bell v_bridge_toll
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from realmwalker.data.registry import DataRegistry  # noqa: E402
from realmwalker.paths import Paths  # noqa: E402
from realmwalker.world.tables import Tables  # noqa: E402

SEEDS = (3, 42)
TOWNS = 16  # the towns nearest the hero that are peopled and looked in


def lines_of(spec: dict, data: dict) -> list[tuple[str, list]]:
    out = [(f"words.{k}", v) for k, v in spec.get("words", {}).items() if isinstance(v, list) and k != "keep"]
    for ob in spec.get("obstacles", []):
        out.append((f"obstacle {ob['id']} note", ob.get("note", [])))
        out.append((f"obstacle {ob['id']} magic_note", ob.get("magic_note", [])))
        for a in ob.get("acts", []):
            for k in ("label", "say", "fail_say", "note"):
                out.append((f"act {a['id']} {k}", a.get(k, [])))
        fav = ob.get("favour") or {}
        for k in ("say", "note"):
            out.append((f"obstacle {ob['id']} favour {k}", fav.get(k, [])))
    for a in spec.get("acts", []):
        for k in ("label", "say", "fail_say", "note"):
            out.append((f"act {a['id']} {k}", a.get(k, [])))
    for e in spec.get("endings", []):
        out.append((f"ending {e['id']}", e.get("line", [])))
    out.append(("lapse", (spec.get("lapse") or {}).get("line", [])))
    for m in spec.get("meetings", []):
        scene = data["scenes"].get((data["meetings"].get(m) or {}).get("scene"), {})
        for k, v in (scene.get("words") or {}).items():
            out.append((f"scene {m} {k}", v))
    return [(k, v) for k, v in out if v]


def main(ids: list[str]) -> int:
    from realmwalker.core import textgen
    from realmwalker.game import townlife
    from realmwalker.game.people import prepare_town
    from realmwalker.game.story import check, situations, vignettes
    from tests.test_first_hour import a_life

    reg, errors = DataRegistry.load(Paths().data)
    if errors:
        print("DATA ERRORS:", *errors, sep="\n  ")
        return 1
    tables = Tables(reg)
    probs = [p for p in check.problems(tables) if "situations" in p or "vig" in p or "scene" in p]
    for p in probs:
        print("PROBLEM:", p)
    vs = vignettes.vignettes(tables)
    ids = ids or sorted(vs)
    bad = len(probs)
    forged: dict[str, list] = {v: [] for v in ids}
    for seed in SEEDS:
        townlife.forget()
        game, town = a_life(tables, seed)
        w = game.world
        towns = sorted(w.settlements, key=lambda s: (abs(s.x - town.x) + abs(s.y - town.y), s.id))[:TOWNS]
        for s in towns:
            prepare_town(game, s)
        for vid in ids:
            if vid not in vs:
                print(f"{vid}: NOT A VIGNETTE (no 'vignette' block, or not written)")
                bad += 1
                continue
            for s in towns:
                sit = situations.make(game, s.id, predicament=vid)
                if sit is None:
                    continue
                forged[vid].append(f"{s.name} ({s.kind}, seed {seed})")
                data = {"meetings": tables.situations.get("meetings", {}), "scenes": tables.scenes}
                values = situations._values(game, sit)
                for where, lines in lines_of(vs[vid], data):
                    for line in lines:
                        rng = w.rng.child("check")
                        text = textgen.fill(line, rng, tables.adventures.get("words", {}), values)
                        if "{" in text or "}" in text:
                            print(f"{vid} {where}: unfilled: {text}")
                            bad += 1
                if len(forged[vid]) == 1:
                    print(f"\n=== {vid} in {s.name}: {sit['words'].get('title')}")
                    print("  plea:", sit["words"].get("plea"))
                    print("  first:", sit["words"].get("first"))
                    print("  roles:", {r: situations._name(game, e)[0] for r, e in sit["roles"].items()})
                situations._unbind(game, sit)
                situations._undo(game, sit)
                del situations.records(w)[sit["id"]]
                break
    print()
    for vid in ids:
        print(f"{vid}: forged in {len(forged[vid])} of 2 worlds: {forged[vid]}")
        if not forged[vid]:
            bad += 1
    print("OK" if not bad else f"{bad} PROBLEM(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
