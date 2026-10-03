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
    kind: str  # "move", "click", "wheel", "release"
    x: int = -1  # the text cell
    y: int = -1
    button: str = "left"  # "left", "right", "middle"
    dy: int = 0
    px: float = -1.0  # the pixel in the frame (-1: not known; tests and the bot work in cells)
    py: float = -1.0
    clicks: int = 1  # 2 for a double click


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
    """Turns SDL events into game events. `to_frame` maps a window pixel to (frame pixel x, y, cell x, y); without
    it, event positions are taken to be cells already (tcod's convert_event)."""

    def __init__(self, to_frame=None) -> None:
        self._swallow_text: str | None = None
        self.mouse = (-1, -1)
        self.mouse_px = (-1.0, -1.0)
        self.to_frame = to_frame

    def _where(self, event) -> tuple[int, int, float, float]:
        x, y = float(event.position.x), float(event.position.y)
        if self.to_frame is None:
            return int(x), int(y), -1.0, -1.0
        return self.to_frame(x, y)

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
            cx, cy, px, py = self._where(event)
            self.mouse, self.mouse_px = (cx, cy), (px, py)
            return [MouseEvent("move", cx, cy, px=px, py=py)]
        if isinstance(event, tcod.event.MouseButtonDown):
            cx, cy, px, py = self._where(event)
            self.mouse, self.mouse_px = (cx, cy), (px, py)
            try:
                clicks = int(event.sdl_event.button.clicks)
            except Exception:
                clicks = 1
            return [MouseEvent("click", cx, cy, button=_MOUSE_BUTTONS.get(int(event.button), "left"), px=px, py=py,
                               clicks=clicks)]
        if isinstance(event, tcod.event.MouseButtonUp):
            cx, cy, px, py = self._where(event)
            return [MouseEvent("release", cx, cy, button=_MOUSE_BUTTONS.get(int(event.button), "left"), px=px, py=py)]
        if isinstance(event, tcod.event.MouseWheel):
            dy = -int(event.y) if event.flipped else int(event.y)
            return [MouseEvent("wheel", *self.mouse, dy=dy, px=self.mouse_px[0], py=self.mouse_px[1])]
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
