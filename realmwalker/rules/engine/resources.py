"""Pools of uses and their recovery (docs/EXPANSIONS.md §4.3.1): Second Wind, Action Surge, Channel Divinity...

A trait or feature with a `resource` in data/traits.json has a pool: `{"id", "max", "recover"}`. The uses left are kept
on the character as before (`Character.uses[id]`). `max` is a number or a name: "wis_mod" (the Wisdom modifier, at
least 1). `recover` is "short" (a short or a long rest brings it back), "long" (a long rest), or "dawn".
"""

from __future__ import annotations

from realmwalker.rules.character import modifier
from realmwalker.rules.engine import traits as tr


def pools(char, tables) -> dict[str, dict]:
    """The character's pools: resource id -> its definition."""
    defs = tr.table(tables)
    out = {}
    for t in sorted(tr.of_char(char, tables)):
        r = (defs.get(t) or {}).get("resource")
        if r:
            out[r["id"]] = r
    return out


def maximum(char, r: dict) -> int:
    m = r["max"]
    if m == "wis_mod":
        return max(1, modifier(char.abilities["wis"]))
    return int(m)


def left(char, rid: str) -> int:
    return int(char.uses.get(rid, 0))


def spend(char, rid: str, n: int = 1) -> None:
    char.uses[rid] = max(0, left(char, rid) - n)


def fill(char, tables, *, only: set[str] | None = None) -> None:
    """Every pool (or only these) full."""
    for rid, r in pools(char, tables).items():
        if only is None or rid in only:
            char.uses[rid] = maximum(char, r)


def recover(char, tables, rest: str) -> None:
    """A rest ("short" or "long") or the dawn brings back what it brings back. A long rest brings back everything a
    short one does."""
    brings = {"short": ("short",), "long": ("short", "long", "dawn"), "dawn": ("dawn",)}[rest]
    for rid, r in pools(char, tables).items():
        if r["recover"] in brings:
            char.uses[rid] = maximum(char, r)


def granted(char, tables, before: frozenset[str]) -> None:
    """Pools that came with features just gained start full (a fighter's new Action Surge)."""
    defs = tr.table(tables)
    for t in sorted(tr.of_char(char, tables) - before):
        r = (defs.get(t) or {}).get("resource")
        if r:
            char.uses[r["id"]] = maximum(char, r)
