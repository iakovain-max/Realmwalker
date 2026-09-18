"""The colour palette. Named colours are used in text markup, e.g. "<danger>bleeding</>"."""

from __future__ import annotations

Color = tuple[int, int, int]

BG: Color = (10, 10, 14)
PANEL_BG: Color = (16, 15, 20)
FG: Color = (204, 200, 186)
DIM: Color = (112, 108, 100)
FAINT: Color = (58, 56, 54)
BORDER: Color = (104, 88, 62)
TITLE: Color = (232, 196, 120)
HILITE_BG: Color = (58, 46, 26)
HOVER_BG: Color = (34, 30, 24)
SELECT_FG: Color = (255, 232, 170)
BLACK: Color = (0, 0, 0)

NAMED: dict[str, Color] = {
    "fg": FG,
    "dim": DIM,
    "faint": FAINT,
    "title": TITLE,
    "danger": (224, 72, 58),  # blood, harm, death, hostility
    "warn": (230, 156, 60),  # warnings, needs, caution
    "good": (116, 196, 96),  # healing, success, safety
    "loot": (240, 212, 84),  # money and items
    "info": (122, 170, 222),  # neutral information, rules text
    "magic": (184, 128, 234),  # spells and the uncanny
    "name": (226, 222, 164),  # people
    "place": (150, 204, 200),  # places
    "ai": (148, 196, 164),  # AI-written text marker
    "white": (240, 240, 232),
    "grey": (150, 150, 150),
    "red": (200, 50, 40),
    "blue": (70, 110, 200),
    "green": (70, 150, 60),
    "brown": (140, 100, 60),
    "gold": (220, 180, 60),
}


def named(name: str, default: Color = FG) -> Color:
    return NAMED.get(name, default)


def lerp(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t), round(a[2] + (b[2] - a[2]) * t))


def scale(c: Color, f: float) -> Color:
    return (min(255, round(c[0] * f)), min(255, round(c[1] * f)), min(255, round(c[2] * f)))
