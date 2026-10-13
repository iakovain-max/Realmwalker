"""Reading the codex (docs/expansions/codex/*.json): the checklist of everything in the three books.

    entries()          every entry, from every file and fragment (classes.json, monsters.devils.json...)
    problems(data)     what is wrong with it (missing fields, duplicate ids, notes missing, game ids that do not exist,
                       released expansions with work still to do)
    coverage()         counts by book and by file, for tools/codex/coverage.py and the release notes
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODEX = ROOT / "docs" / "expansions" / "codex"
COMMON = ("id", "name", "book", "page", "dlc", "status", "game", "note")
STATUSES = ("todo", "done", "adapted", "omitted")
BOOKS = {"phb": "Player's Handbook", "dmg": "Dungeon Master's Guide", "mm": "Monster Manual"}
EXTRA = {
    "spells": ("level", "school", "classes", "ritual", "concentration"),
    "monsters": ("type", "size", "cr", "habitat", "treasure", "group"),
    "magic_items": ("kind", "category", "rarity", "attunement", "theme"),
    "classes": ("kind", "class", "subclass", "level"),
    "species": ("kind", "species"),
    "backgrounds": ("abilities", "feat"),
    "feats": ("category", "prerequisite"),
    "equipment": ("kind", "category"),
    "rules": ("kind",),
    "world": ("kind",),
}
# Where a done or adapted entry's `game` ids live in the game's data: codex file -> (data file, section). An id may
# also be written "<data file>/<section>/<key>" to point anywhere else.
GAME_HOME = {
    "spells": ("spells.json", "spells"),
    "monsters": ("creatures.json", "creatures"),
    "classes": ("classes.json", "classes"),
    "species": ("races.json", "races"),
    "backgrounds": ("backgrounds.json", "backgrounds"),
    "items": ("items.json", "items"),
    "equipment": ("items.json", "items"),
}


def files(folder: Path = CODEX) -> list[Path]:
    return sorted(p for p in folder.glob("*.json"))


def kind_of(path: Path) -> str:
    """The codex file a path belongs to: monsters.devils.json -> monsters."""
    return path.name.split(".", 1)[0]


def entries(folder: Path = CODEX) -> list[tuple[str, dict]]:
    """(codex file, entry) for every entry."""
    out = []
    for path in files(folder):
        data = json.loads(path.read_text(encoding="utf-8"))
        for e in data.get("entries", []):
            out.append((kind_of(path), e))
    return out


def _game_has(data, kind: str, gid: str) -> bool:
    if "/" in gid:
        filename, section, key = gid.split("/", 2)
    elif kind in GAME_HOME:
        (filename, section), key = GAME_HOME[kind], gid
    else:
        return True  # nowhere to look it up yet: the expansion that delivers it says where (see GAME_HOME)
    body = data.get(filename) or {}
    return key in (body.get(section) or {})


def problems(data=None, released: set[int] | None = None, folder: Path = CODEX) -> list[str]:
    """Everything wrong with the codex. data: the loaded game data (to check `game` ids); released: the numbers of the
    expansions that are out (none of their entries may still be `todo`)."""
    out = []
    seen: dict[str, str] = {}
    for kind, e in entries(folder):
        eid = e.get("id", "?")
        where = f"codex {kind}: {eid}"
        for f in COMMON + EXTRA.get(kind, ()):
            if f not in e:
                out.append(f"{where}: missing '{f}'")
        if eid in seen:
            out.append(f"{where}: the id is also in {seen[eid]}")
        seen[eid] = kind
        if e.get("book") not in BOOKS:
            out.append(f"{where}: book must be one of {', '.join(BOOKS)}")
        if not isinstance(e.get("dlc"), int) or not 1 <= e["dlc"] <= 26:
            out.append(f"{where}: dlc must be an expansion number, 1 to 26")
        status = e.get("status")
        if status not in STATUSES:
            out.append(f"{where}: status must be one of {', '.join(STATUSES)}")
        if status in ("adapted", "omitted") and not str(e.get("note", "")).strip():
            out.append(f"{where}: an {status} entry must say why in its note")
        up = e.get("upgrade_in")
        if up is not None and (not isinstance(up, int) or not isinstance(e.get("dlc"), int) or up <= e["dlc"]):
            out.append(f"{where}: upgrade_in must be a later expansion than its dlc")
        if status in ("done", "adapted"):
            if not e.get("game"):
                out.append(f"{where}: a {status} entry must name what implements it in 'game'")
            elif data is not None:
                for gid in e["game"]:
                    if not _game_has(data, kind, str(gid)):
                        out.append(f"{where}: the game has no '{gid}'")
        if released and status == "todo" and e.get("dlc") in released:
            out.append(f"{where}: still to do, but expansion {e['dlc']} is released")
    return out


def coverage() -> dict:
    """{"books": {book: Counter(status)}, "files": {file: Counter(status)}, "dlc": {n: Counter(status)}}."""
    books: dict[str, Counter] = defaultdict(Counter)
    kinds: dict[str, Counter] = defaultdict(Counter)
    dlcs: dict[int, Counter] = defaultdict(Counter)
    for kind, e in entries():
        books[e.get("book", "?")][e.get("status", "?")] += 1
        kinds[kind][e.get("status", "?")] += 1
        dlcs[e.get("dlc", 0)][e.get("status", "?")] += 1
        for extra in e.get("also", []):  # a creature printed in two books counts for both
            books[extra.get("book", "?")][e.get("status", "?")] += 1
    return {"books": dict(books), "files": dict(kinds), "dlc": dict(dlcs)}


def line(name: str, c: Counter) -> str:
    total = sum(c.values())
    done = c.get("done", 0)
    parts = [f"{name}: {done} of {total} done"]
    for s in ("adapted", "omitted"):
        if c.get(s):
            parts.append(f"{c[s]} {s}")
    pct = round(100 * (done + c.get("adapted", 0) + c.get("omitted", 0)) / total) if total else 0
    return ", ".join(parts) + f" ({pct}%)"
