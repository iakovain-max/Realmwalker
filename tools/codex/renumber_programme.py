"""One-off (Expansion 6 A.0, 2026-10-24): Adventures & Events becomes Expansion 6, so the old 6-26 become 7-27.

Run once:  .venv/Scripts/python.exe tools/codex/renumber_programme.py docs|codex
  docs   renumbers docs/EXPANSIONS.md (section headings, the table, cross references, appendices)
  codex  moves `dlc` and `upgrade_in` 6-26 to 7-27 in build/codex and tools/codex data, and gives the DMG's renown,
         marks of prestige and settlement calamities to 6
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def up(n: int) -> int:
    return n + 1 if 6 <= n <= 26 else n


def _num(m: re.Match) -> str:
    return str(up(int(m.group(0))))


def _nums(text: str) -> str:
    """Every bare number 6-26 in a piece of text (not after § or a dot, not part of a longer number)."""
    return re.sub(r"(?<![§.\d])\b\d+\b(?![.\d])", _num, text)


def _expansion_refs(line: str) -> str:
    # "Expansion 6", "Expansions 10 and 19", "Expansions 6–26", "Expansion 26 (...)"
    def fix(m: re.Match) -> str:
        return m.group(1) + _nums(m.group(2))
    line = re.sub(r"(Expansions? )(\d+(?:(?:[–-]| and | or |, )\d+)*)", fix, line)
    # §6.N cross references
    line = re.sub(r"§6\.(\d+)", lambda m: f"§6.{up(int(m.group(1)))}", line)
    return line


def _cells(line: str, which: list[int]) -> str:
    parts = line.split("|")
    for i in which:
        if 0 <= i < len(parts):
            parts[i] = _nums(parts[i])
    return "|".join(parts)


def docs() -> None:
    path = ROOT / "docs" / "EXPANSIONS.md"
    lines = path.read_text(encoding="utf-8").split("\n")
    section = ""
    out = []
    for line in lines:
        if line.startswith("## "):
            section = line
        heading = re.match(r"### 6\.(\d+) (.*)$", line)
        if heading:
            n = int(heading.group(1))
            line = f"### 6.{up(n)} " + _expansion_refs(heading.group(2))
            out.append(line)
            continue
        if section.startswith("## 6.") and re.match(r"\| \d+ \|", line):
            # the programme's table: the number and the Needs column
            line = _cells(line, [1, 4])
        elif section.startswith("## Appendix B") and "→" in line:
            line = re.sub(r"→ (\d+)", lambda m: f"→ {up(int(m.group(1)))}", line)
        elif section.startswith("## Appendix C") and line.startswith("| "):
            line = re.sub(r"\((\d+)\)", lambda m: f"({up(int(m.group(1)))})", line)
        elif section.startswith(("## Appendix D", "## Appendix E")) and line.startswith("| "):
            n_cells = line.count("|") - 1
            line = _cells(line, [n_cells])
        line = _expansion_refs(line)
        # the pack.json example and the STATUS template name Tieflings & Warlocks
        line = (line.replace("06_tieflings_warlocks", "07_tieflings_warlocks")
                .replace("dlc/06-tieflings-warlocks", "dlc/07-tieflings-warlocks")
                .replace("06-tieflings-warlocks.md", "07-tieflings-warlocks.md")
                .replace('"order": 6', '"order": 7')
                .replace('"version": "1.6.0"', '"version": "1.7.0"')
                .replace("Current: 06 Tieflings", "Current: 07 Tieflings")
                .replace("... · 06 part A", "... · 07 part A"))
        out.append(line)
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------------------------- the codex

# The DMG's renown (96), marks of prestige (84-85) and settlement calamities (98) go to Adventures & Events.
TO_SIX = ("rule:dmg_marks_of_prestige", "rule:dmg_renown", "calamity:")
SIX_NOTE = {"rule:dmg_marks_of_prestige": "Adventures & Events: titles, rights and land as Legend's rewards.",
            "rule:dmg_renown": "Adventures & Events: Legend.",
            "calamity:": "Adventures & Events: a seed of a threat to a settlement."}


def codex() -> None:
    """Line by line, so the files keep their one-entry-a-line shape."""
    changed = 0
    for path in sorted((ROOT / "docs" / "expansions" / "codex").glob("*.json")):
        lines = path.read_text(encoding="utf-8").split("\n")
        out = [_codex_line(line) for line in lines]
        n = sum(a != b for a, b in zip(lines, out))
        if n:
            path.write_text("\n".join(out), encoding="utf-8", newline="\n")
            print(f"{path.name}: {n} lines changed")
            changed += n
    print(f"{changed} lines changed")


def _codex_line(line: str) -> str:
    if '"id": ' not in line:
        return line
    line = re.sub(r'("dlc": )(\d+)', lambda m: m.group(1) + str(up(int(m.group(2)))), line)
    line = re.sub(r'("upgrade_in": )(\[[^\]]*\]|\d+)', lambda m: m.group(1) + _nums(m.group(2)), line)
    line = _expansion_refs(line)
    ident = re.search(r'"id": "([^"]+)"', line).group(1)
    for key in TO_SIX:
        if ident == key or (key.endswith(":") and ident.startswith(key)):
            line = re.sub(r'"dlc": \d+', '"dlc": 6', line)
            line = re.sub(r'"note": "([^"]*)"', lambda m: '"note": "' + (SIX_NOTE[key] + " " + m.group(1)).strip() + '"', line)
    return line


if __name__ == "__main__":
    {"docs": docs, "codex": codex}[sys.argv[1]]()
