"""The beat language (docs/ADVENTURES.md §8.6): a beat's conditions and the ops of its choices.

Both are whitelists, filled by `@condition("name")` and `@op("name")`; story/check.py reports anything a beat names
that is not here. Each part adds the conditions and ops its own content uses.
"""

from __future__ import annotations

CONDITIONS: dict[str, object] = {}
OPS: dict[str, object] = {}


def condition(name: str):
    """fn(game, ctx, value) -> bool"""
    def wrap(fn):
        CONDITIONS[name] = fn
        return fn
    return wrap


def op(name: str):
    """fn(game, ctx, *args) -> list of lines said"""
    def wrap(fn):
        OPS[name] = fn
        return fn
    return wrap
