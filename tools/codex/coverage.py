"""How much of the three books is in the game, by the codex (docs/expansions/codex).

    .venv\\Scripts\\python.exe tools\\codex\\coverage.py            by book and by list
    .venv\\Scripts\\python.exe tools\\codex\\coverage.py --dlc      also by expansion
    .venv\\Scripts\\python.exe tools\\codex\\coverage.py --markdown  a table for the release notes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.codex.codex import BOOKS, coverage, line  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dlc", action="store_true", help="also show each expansion")
    ap.add_argument("--markdown", action="store_true", help="a table for the release notes")
    args = ap.parse_args(argv)
    cov = coverage()
    if args.markdown:
        print("| Book | Done | Adapted | Omitted | To do | Total |")
        print("|---|---|---|---|---|---|")
        for key, name in BOOKS.items():
            c = cov["books"].get(key, {})
            print(f"| {name} | {c.get('done', 0)} | {c.get('adapted', 0)} | {c.get('omitted', 0)} | "
                  f"{c.get('todo', 0)} | {sum(c.values())} |")
        return 0
    for key, name in BOOKS.items():
        print(line(name, cov["books"].get(key, {})))
    print()
    for kind, c in sorted(cov["files"].items()):
        print("  " + line(kind, c))
    if args.dlc:
        print()
        for n, c in sorted(cov["dlc"].items()):
            print("  " + line(f"Expansion {n}", c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
