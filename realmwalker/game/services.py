"""What townsfolk can do for you besides talk: trade, and services such as rooms, meals, baths,
healing, repairs and animals. Filled in by the economy (M5 parts 3 and 4)."""

from __future__ import annotations


def choices(conv) -> list:
    """Extra menu entries for this person's trade and services."""
    return []


def choose(conv, choice) -> str | None:
    return None
