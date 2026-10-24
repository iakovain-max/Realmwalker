"""Threats: the darkness in the world (Expansion 6, docs/ADVENTURES.md §5.1, §8.3).

A threat is a danger with a will behind it (a named beast, a dead king, a gang's captain...), made from what the
history left, living in `world.politics["threats"]` whether or not the player cares. World layer: no GameState, so it
moves in the interlude between lives too.

STAGE_OPS are what a scheme's stage may do to the world when it begins (data/packs/06_adventures_events/threats.json
`effects`); story/check.py reports any other.
"""

from __future__ import annotations

STAGE_OPS: dict[str, object] = {}


def stage_op(name: str):
    """fn(politics, threat, *args)"""
    def wrap(fn):
        STAGE_OPS[name] = fn
        return fn
    return wrap
