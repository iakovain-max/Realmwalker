"""The story engine, the player's side (Expansion 6, docs/ADVENTURES.md): adventures forged from the world's threats,
their steps and beats, villains who act, finales and endings.

This package is the one door the rest of the game calls (§8.4); the world's side of a story, the threats, is
world/threats.py and runs without a game.
"""

from __future__ import annotations

# The modules whose handlers fill the registries story/check.py reads (step kinds, selectors, ops, keys).
HANDLER_MODULES = ("realmwalker.world.threats",)


def load_all() -> None:
    import importlib

    for name in HANDLER_MODULES:
        importlib.import_module(name)
