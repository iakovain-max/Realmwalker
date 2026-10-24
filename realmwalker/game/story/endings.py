"""Endings (docs/ADVENTURES.md §5.9, §8.6): which ending an adventure reaches, and what the world keeps of it.

An ending is chosen from the blueprint's ordered list: the first whose `if` holds wins, and the last has none. Its
`ops` are consequence operations, applied through the world's own systems. Both are whitelists: ending conditions
in `CONDITIONS` (a name, or a prefix such as "key:" in `PREFIXES`) and ops in `OPS`, filled with `@ending_if` and
`@consequence`; story/check.py reports anything else.
"""

from __future__ import annotations

CONDITIONS: dict[str, object] = {}
PREFIXES: dict[str, object] = {}
OPS: dict[str, object] = {}


def ending_if(name: str):
    """fn(game, adv, arg) -> bool; a name ending in ':' is a prefix ("key:anchor")."""
    def wrap(fn):
        (PREFIXES if name.endswith(":") else CONDITIONS)[name] = fn
        return fn
    return wrap


def consequence(name: str):
    """fn(game, adv, *args) -> list of lines said"""
    def wrap(fn):
        OPS[name] = fn
        return fn
    return wrap


def known_condition(text: str) -> bool:
    if text in CONDITIONS:
        return True
    return any(text.startswith(p) and len(text) > len(p) for p in PREFIXES)
