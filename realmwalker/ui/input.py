"""Simple input events used by all screens, and translation from tcod/SDL events.

Keys are plain strings:
  * printable characters as typed: "g", "G", "?", "+"  (layout-correct, from text input)
  * named keys: "up" "down" "left" "right" "upleft" "upright" "downleft" "downright" "wait"
    "enter" "escape" "backspace" "tab" "delete" "home" "end" "pageup" "pagedown" "f1".."f12"
  * with ctrl/alt held, the base key plus flags: KeyEvent("s", ctrl=True)
"""

from __future__ import annotations

from dataclasses import dataclass

import tcod.event
from tcod.event import KeySym

DIRECTIONS = {
    "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
    "upleft": (-1, -1), "upright": (1, -1), "downleft": (-1, 1), "downright": (1, 1),
}


@dataclass(frozen=True)
class KeyEvent:
    key: str
    ctrl: bool = False
    alt: bool = False
    shift: bool = False

    @property
    def is_text(self) -> bool:
        """A typed character (for text fields)."""
        return len(self.key) == 1 and not self.ctrl and not self.alt

    @property
    def direction(self) -> tuple[int, int] | None:
        return DIRECTIONS.get(self.key) if not self.ctrl and not self.alt else None


@dataclass(frozen=True)
class MouseEvent:
    kind: str  # "move", "click", "wheel"
    x: int = -1
    y: int = -1
    button: str = "left"  # "left", "right", "middle"
    dy: int = 0


InputEvent = KeyEvent | MouseEvent


_SPECIAL: dict[int, str] = {
    KeySym.UP: "up", KeySym.DOWN: "down", KeySym.LEFT: "left", KeySym.RIGHT: "right",
    KeySym.RETURN: "enter", KeySym.KP_ENTER: "enter", KeySym.ESCAPE: "escape",
    KeySym.BACKSPACE: "backspace", KeySym.TAB: "tab", KeySym.DELETE: "delete",
    KeySym.HOME: "home", KeySym.END: "end", KeySym.PAGEUP: "pageup", KeySym.PAGEDOWN: "pagedown",
    KeySym.F1: "f1", KeySym.F2: "f2", KeySym.F3: "f3", KeySym.F4: "f4", KeySym.F5: "f5", KeySym.F6: "f6",
    KeySym.F7: "f7", KeySym.F8: "f8", KeySym.F9: "f9", KeySym.F10: "f10", KeySym.F11: "f11", KeySym.F12: "f12",
}

# Numpad keys double as movement. Their digit is also sent as text, which we swallow.
_KEYPAD: dict[int, tuple[str, str]] = {
    KeySym.KP_8: ("up", "8"), KeySym.KP_2: ("down", "2"), KeySym.KP_4: ("left", "4"), KeySym.KP_6: ("right", "6"),
    KeySym.KP_7: ("upleft", "7"), KeySym.KP_9: ("upright", "9"), KeySym.KP_1: ("downleft", "1"),
    KeySym.KP_3: ("downright", "3"), KeySym.KP_5: ("wait", "5"),
    KeySym.KP_PLUS: ("+", "+"), KeySym.KP_MINUS: ("-", "-"), KeySym.KP_PERIOD: ("wait", "."),
}

_MOUSE_BUTTONS = {1: "left", 2: "middle", 3: "right"}


class EventTranslator:
    def __init__(self) -> None:
        self._swallow_text: str | None = None
        self.mouse = (-1, -1)

    def translate(self, event: tcod.event.Event) -> list[InputEvent]:
        if isinstance(event, tcod.event.KeyDown):
            return self._key(event)
        if isinstance(event, tcod.event.TextInput):
            text = event.text
            if self._swallow_text is not None and text == self._swallow_text:
                self._swallow_text = None
                return []
            self._swallow_text = None
            return [KeyEvent(ch) for ch in text if ch.isprintable()]
        if isinstance(event, tcod.event.MouseMotion):
            self.mouse = (int(event.position.x), int(event.position.y))
            return [MouseEvent("move", *self.mouse)]
        if isinstance(event, tcod.event.MouseButtonDown):
            pos = (int(event.position.x), int(event.position.y))
            self.mouse = pos
            return [MouseEvent("click", *pos, button=_MOUSE_BUTTONS.get(int(event.button), "left"))]
        if isinstance(event, tcod.event.MouseWheel):
            dy = -int(event.y) if event.flipped else int(event.y)
            return [MouseEvent("wheel", *self.mouse, dy=dy)]
        return []

    def _key(self, event: tcod.event.KeyDown) -> list[InputEvent]:
        mod = event.mod
        ctrl = bool(mod & tcod.event.Modifier.CTRL)
        alt = bool(mod & tcod.event.Modifier.ALT)
        shift = bool(mod & tcod.event.Modifier.SHIFT)
        sym = int(event.sym)
        self._swallow_text = None
        if sym in _KEYPAD:
            name, text = _KEYPAD[sym]
            self._swallow_text = text
            return [KeyEvent(name, ctrl, alt, shift)]
        if sym in _SPECIAL:
            return [KeyEvent(_SPECIAL[sym], ctrl, alt, shift)]
        if (ctrl or alt) and 32 <= sym < 127:
            # Text input is not sent for ctrl/alt combinations, so report the key itself.
            return [KeyEvent(chr(sym), ctrl, alt, shift)]
        return []
