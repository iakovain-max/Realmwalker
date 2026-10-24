"""The step kinds of adventures (docs/ADVENTURES.md §5.2, §8.5): a registry of small handlers by id.

A step kind is a class registered with `@step("go")`. Its `fields` are the keys a blueprint's step may carry besides
`kind` (story/check.py reports any other); the forge calls `bind` once, and the game's listeners (story/__init__.py)
pass on what happened. `repair` keeps an adventure from ever being stuck (law 6): when a step's target is gone, the
step binds a new one or turns into its failure branch.
"""

from __future__ import annotations

STEPS: dict[str, type] = {}
COMMON = {"kind", "id", "optional", "gives", "fails_to", "tier_min", "words"}


def step(kind: str):
    def wrap(cls):
        cls.kind = kind
        STEPS[kind] = cls
        return cls
    return wrap


class Step:
    """The default behaviour of every kind: nothing to bind, never done by itself, nothing to repair."""
    kind = ""
    fields: frozenset = frozenset()

    @classmethod
    def allowed(cls) -> set:
        return COMMON | set(cls.fields)
