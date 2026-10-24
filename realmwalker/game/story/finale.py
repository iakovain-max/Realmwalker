"""The finale (docs/ADVENTURES.md §5.8): a fair, epic fight.

Keys (one list for data and code): what each key found on the way does to the battle, registered with `@key("name")`
and applied by `prepare` when the finale's battle starts; LEGENDARY is the menu a boss template's legendary actions
are taken from, and PHASES the kinds of second phase. story/check.py reports names that are not here.
"""

from __future__ import annotations

KEYS: dict[str, object] = {}
LEGENDARY: dict[str, object] = {}
PHASES: dict[str, object] = {}


def key(name: str):
    """fn(battle, game, adv, *args)"""
    def wrap(fn):
        KEYS[name] = fn
        return fn
    return wrap


def legendary(name: str):
    def wrap(fn):
        LEGENDARY[name] = fn
        return fn
    return wrap


def phase(name: str):
    def wrap(fn):
        PHASES[name] = fn
        return fn
    return wrap


def split_key(text: str) -> tuple[str, list[str]]:
    """'vulnerable(fire)' -> ('vulnerable', ['fire']); 'surprise' -> ('surprise', [])."""
    text = text.strip()
    if text.endswith(")") and "(" in text:
        name, rest = text.split("(", 1)
        args = [a.strip() for a in rest[:-1].split(",") if a.strip()]
        return name.strip(), args
    return text, []
