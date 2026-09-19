"""Trade and service windows opened from a conversation (M5 parts 3 and 4)."""

from __future__ import annotations


def open_request(screen, request: str, choice) -> None:
    """Open the window a conversation asked for."""
