"""Mark codex entries settled: `python tools/codex/mark.py <file.json> <marks.json>`.

marks.json: {"<id>": {"status": "done" | "adapted" | "omitted", "game": [...], "note": "..."}}. Each entry stays on its
own line (docs/expansions/codex/README.md); only the named entries change.
"""
from __future__ import annotations

import json
import re
import sys

LINE = re.compile(r'^(\s*)(\{"id": "([^"]+)".*\})(,?)\s*$')


def mark(path: str, marks: dict) -> list[str]:
    with open(path, encoding="utf-8", newline="") as fh:
        lines = fh.read().split("\n")
    done = []
    for i, ln in enumerate(lines):
        m = LINE.match(ln)
        if not m or m.group(3) not in marks:
            continue
        entry = json.loads(m.group(2))
        entry.update(marks[m.group(3)])
        lines[i] = f"{m.group(1)}{json.dumps(entry, ensure_ascii=False)}{m.group(4)}"
        done.append(m.group(3))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines))
    json.loads(open(path, encoding="utf-8").read())
    return done


if __name__ == "__main__":
    marks = json.load(open(sys.argv[2], encoding="utf-8"))
    got = mark(sys.argv[1], marks)
    missing = sorted(set(marks) - set(got))
    print(f"marked {len(got)}; not found: {missing}")
