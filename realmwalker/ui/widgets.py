"""Drawing helpers and small widgets (menus, scrolling text), with mouse hit regions.

Screens draw every frame onto a Canvas. Anything clickable or hoverable registers a region;
the app routes the next mouse click or hover to it. Only the top screen is interactive.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import tcod.console

from realmwalker.ui import colors, markup
from realmwalker.ui.colors import Color
from realmwalker.ui.input import KeyEvent

WASHES = {colors.HILITE_BG, colors.HOVER_BG}  # highlight colours drawn as soft washes

WASH_MARK = (1, 2, 3)  # cells already washed by a highlight picture (see Canvas._wash)


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int
    action: Callable[[], None] | None = None
    tooltip: object = None  # words, a Card, or a function making one (built only when shown)
    wheel: Callable[[int], None] | None = None
    right_action: Callable[[], None] | None = None

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


class Canvas:
    def __init__(self, console: tcod.console.Console, mouse: tuple[int, int] = (-1, -1), interactive: bool = True,
                 gfx=None, mouse_px: tuple[float, float] | None = None) -> None:
        from realmwalker.ui.gfx.scene import Layer

        self.con = console
        self.width = console.width
        self.height = console.height
        self.mouse = mouse
        self.interactive = interactive
        self.regions: list[Region] = []
        self.tooltip: object = None  # words, a rules/describe.Card, or a function returning either
        self.tip_rect: tuple[int, int, int, int] | None = None  # what the tooltip is about (a card never covers it)
        self.tip_ready = True  # a card waits for a short hover (the App sets this; headless it shows at once)
        if gfx is None:
            from realmwalker.ui.gfx import headless

            gfx = headless()
        self.gfx = gfx  # the GfxContext: a window's, or (headless) one that records the pictures without showing them
        self.layers = [Layer(console)]
        if mouse_px is None:
            mouse_px = (mouse[0] * self.cell_w + self.cell_w / 2, mouse[1] * self.cell_h + self.cell_h / 2) \
                if mouse[0] >= 0 else (-1.0, -1.0)
        self.mouse_px = mouse_px

    # ------------------------------------------------------------------ pictures and layers
    @property
    def cell_w(self) -> int:
        return self.gfx.cell_w

    @property
    def cell_h(self) -> int:
        return self.gfx.cell_h

    @property
    def now(self) -> float:
        return self.gfx.now

    def words(self) -> str:
        """Everything this frame says: the text in every layer's cells, row by row, and the words drawn as pictures
        (box titles, headings, labels). For tests and tools that read what is on the screen."""
        from realmwalker.ui.gfx.scene import Text

        rows = []
        for layer in self.layers:
            con = layer.console
            rows += ["".join(chr(c) for c in con.rgb["ch"][:, y]) for y in range(con.height)]
            rows += [c.text for c in layer.under + layer.over if isinstance(c, Text)]
        return "\n".join(rows)

    def px(self, x: float, y: float) -> tuple[float, float]:
        """The pixel position of the top left of cell (x, y)."""
        return x * self.cell_w, y * self.cell_h

    def cell_rect(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return x * self.cell_w, y * self.cell_h, w * self.cell_w, h * self.cell_h

    def push_layer(self) -> None:
        """Start a new layer above everything drawn so far (a dialog over the map)."""
        from realmwalker.ui.gfx.scene import Layer

        con = tcod.console.Console(self.width, self.height, order="F")
        con.rgba["bg"] = (0, 0, 0, 0)
        con.rgba["fg"] = (*colors.FG, 255)
        self.con = con
        self.layers.append(Layer(con))

    def under(self, *cmds) -> None:
        """Pictures beneath this layer's text (a map, a panel)."""
        self.layers[-1].under.extend(cmds)

    def over(self, *cmds) -> None:
        """Pictures above this layer's text (a cursor, a floating number)."""
        self.layers[-1].over.extend(cmds)

    def clear_cells(self, x: int, y: int, w: int, h: int) -> None:
        """Make cells see-through, so the pictures under them show."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 > x0 and y1 > y0:
            self.con.rgba["bg"][x0:x1, y0:y1] = (0, 0, 0, 0)
            self.con.rgba["ch"][x0:x1, y0:y1] = 32

    def dim(self) -> None:
        """Darken everything drawn so far (under a dialog)."""
        from realmwalker.ui.gfx.scene import Rect

        self.over(Rect(0, 0, self.width * self.cell_w, self.height * self.cell_h, (4, 3, 6, 150)))

    def sprite(self, name: str, x: float, y: float, w: float, h: float, rgba=(255, 255, 255, 255), *,
               over: bool = True) -> bool:
        """A tile at pixel rect (x, y, w, h). False when the atlas has no picture of that name."""
        from realmwalker.ui.gfx.scene import tile_batch

        import numpy as np

        name = self.gfx.atlas.resolve(name)
        if name is None:
            return False
        c = np.array([[v / 255 for v in rgba]], np.float32)
        cmds = tile_batch(self.gfx.atlas, [name], np.array([[x, y, w, h]], np.float32), c)
        (self.over if over else self.under)(*cmds)
        return bool(cmds)

    def bar(self, x: int, y: int, w: int, ratio: float, color: Color, *, empty: Color = colors.FAINT,
            lag: float | None = None) -> None:
        """A bar w cells long, filled to ratio, drawn lit."""
        from realmwalker.ui.gfx import theme

        ratio = max(0.0, min(1.0, ratio))
        self.clear_cells(x, y, w, 1)
        cw, ch = self.cell_w, self.cell_h
        self.under(*theme.bar(x * cw, y * ch + 4, w * cw, ch - 8, ratio, color, lag=lag))

    def gauge(self, x: int, y: int, w: int, pos: float, stops: list[tuple[float, Color]]) -> None:
        """A scale from cold to hot (or any other), coloured along its length, with a marker at pos (0..1)."""
        from realmwalker.ui.gfx.scene import Rect

        pos = max(0.0, min(1.0, pos))
        self.clear_cells(x, y, w, 1)
        cw, ch = self.cell_w, self.cell_h
        px, py, pw, ph = x * cw, y * ch + 6, w * cw, ch - 12
        self.under(Rect(px - 1, py - 1, pw + 2, ph + 2, (6, 5, 7, 255)))
        n = len(stops)
        for i, (at, color) in enumerate(stops):
            nxt = stops[i + 1][0] if i + 1 < n else 1.0
            self.under(Rect(px + pw * at, py, pw * (nxt - at) + 1, ph, (*color, 255)))
        mx = px + pw * pos
        self.over(Rect(mx - 3, py - 4, 6, ph + 8, (255, 236, 190, 255)), Rect(mx - 3, py - 4, 6, ph + 8, (20, 16, 12, 255),
                                                                                line=1))

    def icon(self, x: int, y: int, name: str, glyph: str = "", fg: Color = colors.FG, *, cells: int = 2,
             rgba=(255, 255, 255, 255)) -> int:
        """A square picture `cells` wide and cells/2 tall at cell (x, y) (a letter in its place if the atlas has no such
        picture). Returns the x after it."""
        cw, ch = self.cell_w, self.cell_h
        size = min(cells * cw, max(1, cells // 2) * ch)
        px = x * cw + (cells * cw - size) / 2
        py = y * ch + (max(1, cells // 2) * ch - size) / 2
        if self.sprite(name, px, py, size, size, rgba):
            self.clear_cells(x, y, cells, max(1, cells // 2))
        elif glyph:
            self.text(x + (cells - len(glyph)) // 2, y, glyph, fg)
        return x + cells

    # ------------------------------------------------------------------ mouse
    def hovered(self, x: int, y: int, w: int, h: int) -> bool:
        mx, my = self.mouse
        return self.interactive and x <= mx < x + w and y <= my < y + h

    def hit(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        action: Callable[[], None] | None = None,
        tooltip: object = None,
        *,
        wheel: Callable[[int], None] | None = None,
        right_action: Callable[[], None] | None = None,
    ) -> bool:
        """Register a clickable/hoverable area. Returns True while the mouse is over it."""
        if not self.interactive:
            return False
        if action or tooltip or wheel or right_action:
            self.regions.append(Region(x, y, w, h, action, tooltip, wheel, right_action))
        over = self.hovered(x, y, w, h)
        if over and tooltip:
            self.tooltip = tooltip
            self.tip_rect = (x, y, w, h)
        return over

    # ------------------------------------------------------------------ drawing
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def text(self, x: int, y: int, s: str, fg: Color = colors.FG, bg: Color | None = None, max_width: int | None = None) -> int:
        """Print plain text on one line (clipped). Returns the x after the text."""
        if y < 0 or y >= self.height or not s:
            return x
        if max_width is not None:
            s = s[: max(0, max_width)]
        if x < 0:
            s = s[-x:]
            x = 0
        s = s[: max(0, self.width - x)]
        if s:
            if bg is not None and tuple(bg[:3]) in WASHES:
                self._wash(x, y, len(s), 1, tuple(bg[:3]), only_new=True)
                bg = None
            if bg is not None and len(bg) > 3:
                alpha, bg = bg[3], tuple(bg[:3])
            else:
                alpha = 255
            self.con.print(x, y, s, fg=fg, bg=bg)
            if bg is not None:
                self.con.rgba["bg"][x : x + len(s), y, 3] = alpha
        return x + len(s)

    def _wash(self, x: int, y: int, w: int, h: int, bg: Color, only_new: bool = False) -> None:
        """A highlight drawn as a soft picture under see-through cells (cells already washed are left alone)."""
        from realmwalker.ui.gfx import theme

        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        cells = self.con.rgba["bg"][x0:x1, y0:y1]
        if only_new and (cells[..., :3] == WASH_MARK).all(axis=-1).all():
            return
        cells[...] = (*WASH_MARK, 0)
        kind = "select" if bg == colors.HILITE_BG else "hover"
        cw, ch = self.cell_w, self.cell_h
        self.under(theme.row_highlight(x0 * cw, y0 * ch, (x1 - x0) * cw, (y1 - y0) * ch, kind))

    def spans(self, x: int, y: int, spans: list[markup.Span], bg: Color | None = None, max_width: int | None = None) -> int:
        limit = x + max_width if max_width is not None else self.width
        for text, color in spans:
            if x >= limit:
                break
            x = self.text(x, y, text[: limit - x], color, bg)
        return x

    def markup(self, x: int, y: int, text: str, fg: Color = colors.FG, bg: Color | None = None, max_width: int | None = None) -> int:
        return self.spans(x, y, markup.parse(text, fg), bg, max_width)

    def wrapped(self, x: int, y: int, text: str, width: int, fg: Color = colors.FG, max_lines: int | None = None,
                bg: Color | None = None) -> int:
        """Word-wrapped marked-up text. Returns the number of lines drawn."""
        lines = markup.wrap(text, width, fg)
        if max_lines is not None:
            lines = lines[:max_lines]
        for i, line in enumerate(lines):
            self.spans(x, y + i, line, bg, width)
        return len(lines)

    def centered(self, y: int, text: str, fg: Color = colors.FG, x: int = 0, width: int | None = None) -> None:
        width = self.width if width is None else width
        n = markup.length(text)
        self.markup(x + max(0, (width - n) // 2), y, text, fg)

    def fill(self, x: int, y: int, w: int, h: int, bg: Color, ch: str = " ", fg: Color | None = None) -> None:
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        self.con.rgb["ch"][x0:x1, y0:y1] = ord(ch)
        if tuple(bg[:3]) in WASHES:
            self._wash(x0, y0, x1 - x0, y1 - y0, tuple(bg[:3]))
            if fg is not None:
                self.con.rgb["fg"][x0:x1, y0:y1] = fg
            return
        if len(bg) > 3:
            self.con.rgb["bg"][x0:x1, y0:y1] = bg[:3]
            self.con.rgba["bg"][x0:x1, y0:y1, 3] = bg[3]
        else:
            self.con.rgb["bg"][x0:x1, y0:y1] = bg
            self.con.rgba["bg"][x0:x1, y0:y1, 3] = 255
        if fg is not None:
            self.con.rgb["fg"][x0:x1, y0:y1] = fg

    def frame(self, x: int, y: int, w: int, h: int, title: str = "", *, fg: Color = colors.BORDER,
              bg: Color | None = colors.PANEL_BG, double: bool = False, title_fg: Color = colors.TITLE,
              style: str | None = None) -> None:
        """A box: a textured panel with a bronze edge, its title on a plate (double and title_fg are kept for the
        callers that still pass them; the style follows fg and bg)."""
        if w < 2 or h < 2:
            return
        self._panel(x, y, w, h, title, fg, bg, style)

    def _panel(self, x: int, y: int, w: int, h: int, title: str, fg: Color, bg: Color | None, style: str | None) -> None:
        """A frame as a picture: a textured panel with a bronze edge, its title on a plate."""
        from realmwalker.ui.gfx import theme

        if style is None:
            if tuple(fg) == colors.named("danger") or tuple(fg) == colors.named("red"):
                style = "danger"
            elif tuple(fg) == colors.named("magic"):
                style = "magic"
            elif bg is None or tuple(fg) == colors.FAINT:
                style = "inset"
            elif tuple(fg) == colors.DIM:
                style = "glass"
            else:
                style = "panel"
        self.clear_cells(x, y, w, h)
        cw, ch = self.cell_w, self.cell_h
        size = 18 if w * cw > 500 else 15
        if y == 0:
            size = max(11, min(size, ch - 7))  # along the top of the screen: the title must fit its row
        self.under(*theme.panel(x * cw, y * ch, w * cw, h * ch, style, title=markup.plain(title) if title else "",
                                title_size=size, ornaments=style in ("panel", "danger", "magic"), row_h=ch))

    def hline(self, x: int, y: int, w: int, ch: str = "─", fg: Color = colors.BORDER) -> None:
        if ch in "─═" and w > 0:
            from realmwalker.ui.gfx import theme

            self.clear_cells(x, y, w, 1)
            cw, chh = self.cell_w, self.cell_h
            self.under(*theme.rule(x * cw, y * chh + chh / 2, w * cw))
            return
        self.text(x, y, ch * max(0, w), fg)

    def section(self, x: int, y: int, w: int, title: str, fg: Color = colors.BORDER) -> None:
        """A divider line with a heading: ── Title ─────"""
        from realmwalker.ui.gfx import theme

        self.clear_cells(x, y, w, 1)
        cw, ch = self.cell_w, self.cell_h
        self.over(*theme.heading(x * cw, y * ch + ch / 2, w * cw, markup.plain(title), max(12, int(ch * 0.78))))

    def button(self, x: int, y: int, label: str, action: Callable[[], None], *, hotkey: str | None = None,
               tooltip: str | None = None, enabled: bool = True, max_width: int | None = None) -> int:
        """[G] Generate  - clickable, highlighted on hover. Returns the x after it. With max_width, a label too long
        to fit ends in "…" (and the whole of it is the tooltip)."""
        room = None if max_width is None else max_width - (len(hotkey) + 3 if hotkey else 4)
        if room is not None and len(label) > room > 1:
            tooltip = tooltip or label
            label = label[: room - 1].rstrip() + "…"
        text = f"[{hotkey}] {label}" if hotkey else f"[ {label} ]"
        over = self.hit(x, y, len(text), 1, action if enabled else None, tooltip)
        return self._button(x, y, text, label, hotkey, over, enabled)

    def _button(self, x: int, y: int, text: str, label: str, hotkey: str | None, over: bool, enabled: bool) -> int:
        """A button as a picture: the same cells as "[k] Label", drawn as a raised plate with the key on a badge."""
        from realmwalker.ui.gfx import theme

        n = len(text)
        self.clear_cells(x, y, n, 1)
        cw, ch = self.cell_w, self.cell_h
        state = "off" if not enabled else ("hover" if over else "normal")
        self.under(theme.button(x * cw - 3, y * ch + 1, n * cw + 6, ch - 2, state))
        fg = colors.FAINT if not enabled else (colors.SELECT_FG if over else colors.FG)
        if hotkey:
            k = len(hotkey)
            self.under(theme.badge(x * cw + 1, y * ch + 3, (k + 2) * cw - 4, ch - 6, over))
            self.text(x + 1, y, hotkey, colors.TITLE if enabled else colors.FAINT)
            return self.text(x + 3 + k, y, label, fg)
        return self.text(x + 2, y, label, fg) + 2

    def button_row(self, x: int, y: int, right: int, buttons: list[tuple[str, Callable[[], None], str]]) -> int:
        """A row of [key] buttons three apart, as many as fit before `right`; the last (Back, usually) always does.
        The keys of those left out still work: this only decides what is drawn."""
        width = lambda b: len(b[0]) + len(b[2]) + 3  # noqa: E731
        keep = list(buttons)
        while len(keep) > 1 and x + sum(width(b) for b in keep) + 3 * (len(keep) - 1) > right:
            keep.pop(-2)
        for label, action, key in keep:
            x = self.button(x, y, label, action, hotkey=key) + 3
        return x

    @property
    def tip_is_card(self) -> bool:
        return self.tooltip is not None and not isinstance(self.tooltip, str)

    def draw_tooltip(self) -> None:
        if not self.tooltip or self.mouse[0] < 0:
            return
        tip = self.tooltip
        if not isinstance(tip, str):
            if not self.tip_ready:
                return
            tip = tip() if callable(tip) else tip
            if not tip:
                return
            if not isinstance(tip, str):
                from realmwalker.ui import tooltips

                tooltips.draw_card(self, tip, self.tip_rect)
                return
            self.tooltip = tip
        width = min(48, max(12, markup.length(self.tooltip) + 2))
        lines = markup.wrap(self.tooltip, width - 2)
        h = len(lines) + 2
        mx, my = self.mouse
        x = mx + 2 if mx + 2 + width <= self.width else max(0, mx - width - 1)
        y = my + 1 if my + 1 + h <= self.height else max(0, my - h)
        self.frame(x, y, width, h, fg=colors.DIM, bg=(24, 22, 20), style="glass")
        for i, line in enumerate(lines):
            self.spans(x + 1, y + 1 + i, line)


# ---------------------------------------------------------------------------- menus
@dataclass
class MenuItem:
    label: str
    action: Callable[[], None] | None = None
    hotkey: str | None = None
    enabled: bool = True
    note: str = ""


@dataclass
class Menu:
    items: list[MenuItem]
    selected: int = 0
    on_disabled: Callable[[MenuItem], None] | None = None
    _last_mouse: tuple[int, int] = field(default=(-1, -1), repr=False)

    def move(self, delta: int) -> None:
        if self.items:
            self.selected = (self.selected + delta) % len(self.items)

    def activate(self, index: int) -> None:
        if not 0 <= index < len(self.items):
            return
        self.selected = index
        item = self.items[index]
        if item.enabled and item.action:
            item.action()
        elif not item.enabled and self.on_disabled:
            self.on_disabled(item)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "up" and not ev.ctrl:
            self.move(-1)
        elif ev.key == "down" and not ev.ctrl:
            self.move(1)
        elif ev.key == "home":
            self.selected = 0
        elif ev.key == "end":
            self.selected = len(self.items) - 1
        elif ev.key == "enter":
            self.activate(self.selected)
        else:
            for i, item in enumerate(self.items):
                if item.hotkey and ev.is_text and ev.key.lower() == item.hotkey.lower():
                    self.activate(i)
                    return True
            return False
        return True

    def hotkeys(self) -> list[str]:
        return [i.hotkey for i in self.items if i.hotkey]

    def render(self, canvas: Canvas, x: int, y: int, width: int) -> None:
        # Hovering selects, but only when the mouse actually moved (keyboard keeps control otherwise).
        mouse_moved = canvas.mouse != self._last_mouse
        self._last_mouse = canvas.mouse
        for i, item in enumerate(self.items):
            row = y + i
            index = i
            over = canvas.hit(x, row, width, 1, action=lambda index=index: self.activate(index),
                              tooltip=item.note or None)
            if over and mouse_moved:
                self.selected = i
            selected = i == self.selected
            bg = colors.HILITE_BG if selected else None
            if bg:
                canvas.fill(x, row, width, 1, bg)
            if item.enabled:
                fg = colors.SELECT_FG if selected else colors.FG
            else:
                fg = colors.DIM if selected else colors.FAINT
            cx = x
            cx = canvas.text(cx, row, "► " if selected else "  ", colors.TITLE, bg)
            if item.hotkey:
                key_fg = colors.TITLE if item.enabled else fg
                cx = canvas.text(cx, row, item.hotkey.upper() if len(item.hotkey) == 1 else item.hotkey, key_fg, bg)
                cx = canvas.text(cx, row, "  ", fg, bg)
            canvas.text(cx, row, item.label, fg, bg, max_width=x + width - cx)


class TextField:
    """A one-line text input. `allowed` limits which characters can be typed."""

    def __init__(self, value: str = "", max_len: int = 30, allowed: str | None = None) -> None:
        self.value = value
        self.max_len = max_len
        self.allowed = allowed

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "backspace":
            self.value = self.value[:-1]
            return True
        if ev.key == "delete" or (ev.ctrl and ev.key in ("u", "U")):
            self.value = ""
            return True
        if ev.is_text:
            if self.allowed is not None and ev.key not in self.allowed:
                return True
            if len(self.value) < self.max_len:
                self.value += ev.key
            return True
        return False

    def render(self, canvas: Canvas, x: int, y: int, width: int, focused: bool) -> None:
        bg = (34, 30, 22) if focused else (20, 19, 18)
        canvas.fill(x, y, width, 1, bg)
        shown = self.value[-(width - 2):]
        canvas.text(x + 1, y, shown, colors.SELECT_FG if focused else colors.FG, bg)
        if focused:
            canvas.text(x + 1 + len(shown), y, "_", colors.TITLE, bg)


class ScrollText:
    """A scrollable block of marked-up text (help pages, long descriptions, logs)."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.offset = 0
        self._lines: list[list[markup.Span]] = []
        self._width = -1
        self._height = 1

    def set_text(self, text: str) -> None:
        self.text = text
        self._width = -1

    def scroll(self, delta: int) -> None:
        max_offset = max(0, len(self._lines) - self._height)
        self.offset = max(0, min(max_offset, self.offset + delta))

    def handle_key(self, ev: KeyEvent) -> bool:
        step = {"up": -1, "down": 1, "pageup": -max(1, self._height - 1), "pagedown": max(1, self._height - 1)}
        if ev.key in step:
            self.scroll(step[ev.key])
            return True
        if ev.key == "home":
            self.offset = 0
            return True
        if ev.key == "end":
            self.scroll(10**6)
            return True
        return False

    def render(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        if w != self._width:
            self._lines = markup.wrap(self.text, max(1, w - 1))
            self._width = w
        self._height = h
        self.scroll(0)
        canvas.hit(x, y, w, h, wheel=lambda dy: self.scroll(-dy * 3))
        for i, line in enumerate(self._lines[self.offset : self.offset + h]):
            canvas.spans(x, y + i, line, max_width=w - 1)
        if len(self._lines) > h:
            # A simple scroll bar on the right edge.
            bar_h = max(1, h * h // len(self._lines))
            max_offset = max(1, len(self._lines) - h)
            bar_y = y + (h - bar_h) * self.offset // max_offset
            from realmwalker.ui.gfx.scene import Rect

            cw, ch = canvas.cell_w, canvas.cell_h
            bx = (x + w - 1) * cw + cw / 2 - 2
            canvas.clear_cells(x + w - 1, y, 1, h)
            canvas.under(Rect(bx, y * ch + 2, 4, h * ch - 4, (8, 7, 9, 200)),
                         Rect(bx, bar_y * ch + 2, 4, bar_h * ch - 4, (150, 120, 76, 230)))
