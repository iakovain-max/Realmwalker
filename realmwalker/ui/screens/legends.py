"""The Legends book (2026-10, after Dwarf Fortress's Legends mode): every person, realm, place, war, beast,
artifact, age, god and song of the world's history, each with a page, every name on a page a link.

Left: the kinds of things along the top, a search line and the list. Right: the page. Keys: ← → the kind of thing,
↑ ↓ the list, Enter (or a click) opens, / searches, Tab moves between the list and the page, Backspace goes back
and ] forward, PgUp PgDn scroll the page, Esc closes. The pages themselves are made in world/legends.py.
"""

from __future__ import annotations

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas
from realmwalker.world import legends

LINK_COLOURS = {"H": "name", "F": "info", "S": "place", "X": "place", "W": "danger", "A": "loot", "E": "title",
                "K": "ai"}
Token = tuple[str, tuple, str | None]  # (text, colour, link)


def tokens(line: str) -> list[Token]:
    out: list[Token] = []
    for text, ref in legends.segments(line):
        if ref is None:
            out += [(t, c, None) for t, c in markup.parse(text)]
        else:
            out.append((text, colors.named(LINK_COLOURS.get(ref[:1], "info")), ref))
    return out


def layout(lines: list[str], width: int) -> list[list[Token]]:
    """Lines broken to fit: words keep their colour and their link."""
    out: list[list[Token]] = []
    width = max(8, width)
    for line in lines:
        if not line:
            out.append([])
            continue
        words: list[Token] = []
        for text, colour, ref in tokens(line):
            for i, piece in enumerate(text.split(" ")):
                if i:
                    words.append((" ", colour, ref))
                if piece:
                    words.append((piece, colour, ref))
        row: list[Token] = []
        used = 0
        for word in words:
            n = len(word[0])
            if word[0] == " " and used == 0:
                continue
            if used + n > width and used > 0:
                while row and row[-1][0] == " ":
                    row.pop()
                out.append(row)
                row, used = [], 0
                if word[0] == " ":
                    continue
                word = ("  " + word[0], word[1], word[2])  # a wrapped line is indented a little
                n += 2
            row.append(word)
            used += n
        out.append(row)
    return out


class LegendsScreen(Screen):
    title = "Legends"
    sound_open = "ui_page"
    sound_close = "ui_page"

    def __init__(self, app, world, tables=None, ref: str | None = None) -> None:
        super().__init__(app)
        self.world = world
        self.tables = tables if tables is not None else app.tables
        self.cat = 0
        self.query = ""
        self.searching = False
        self.focus = "list"
        self.sel = 0
        self.offset = 0
        self.back: list[str] = []
        self.ahead: list[str] = []
        self.ref: str | None = None
        self.page_scroll = 0
        self._entries: tuple | None = None
        self._page: tuple | None = None
        self._layout: tuple | None = None
        if ref is not None:
            self.open(ref, remember=False)
        else:
            first = self.entries()
            if first:
                self.open(first[0][0], remember=False)

    @property
    def captures_text(self) -> bool:  # type: ignore[override]
        return self.searching

    # ------------------------------------------------------------------ what is shown
    def entries(self) -> list[tuple[str, str]]:
        key = (self.cat, self.query, len(self.world.history))
        if self._entries is None or self._entries[0] != key:
            category = legends.CATEGORIES[self.cat][0]
            self._entries = (key, legends.entries(self.world, self.tables, category, self.query))
        return self._entries[1]

    def page(self) -> tuple[str, list[str]]:
        if self.ref is None:
            return "Legends", ["<dim>Nothing to read.</>"]
        key = (self.ref, len(self.world.history))
        if self._page is None or self._page[0] != key:
            self._page = (key, legends.page(self.world, self.tables, self.ref))
        return self._page[1]

    def open(self, ref: str, *, remember: bool = True) -> None:
        if remember and self.ref is not None and ref != self.ref:
            self.back.append(self.ref)
            del self.back[:-60]
            self.ahead.clear()
        self.ref = ref
        self.page_scroll = 0
        self._layout = None

    def go_back(self) -> None:
        if self.back:
            if self.ref is not None:
                self.ahead.append(self.ref)
            self.ref = self.back.pop()
            self.page_scroll = 0
            self._layout = None

    def go_ahead(self) -> None:
        if self.ahead:
            if self.ref is not None:
                self.back.append(self.ref)
            self.ref = self.ahead.pop()
            self.page_scroll = 0
            self._layout = None

    def set_category(self, i: int) -> None:
        self.cat = i % len(legends.CATEGORIES)
        self.sel = 0
        self.offset = 0
        items = self.entries()
        if items:
            self.open(items[0][0])

    def choose(self, i: int) -> None:
        items = self.entries()
        if 0 <= i < len(items):
            self.sel = i
            self.open(items[i][0])

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        items = self.entries()
        if self.searching:
            if ev.key in ("escape", "enter"):
                self.searching = False
                if ev.key == "enter" and items:
                    self.choose(0)
                return True
            if ev.key == "backspace":
                self.query = self.query[:-1]
            elif ev.is_text and len(self.query) < 30:
                self.query += ev.key
            else:
                return False
            self.sel = 0
            self.offset = 0
            return True
        if ev.key in ("escape", "n"):
            self.close()
        elif ev.key == "/":
            self.searching = True
        elif ev.key == "tab":
            self.focus = "page" if self.focus == "list" else "list"
        elif ev.key in ("left", "right"):
            self.set_category(self.cat + (1 if ev.key == "right" else -1))
        elif ev.key in ("up", "down") and self.focus == "list":
            if items:
                self.choose(max(0, min(len(items) - 1, self.sel + (1 if ev.key == "down" else -1))))
        elif ev.key in ("up", "down"):
            self.page_scroll = max(0, self.page_scroll + (1 if ev.key == "down" else -1))
        elif ev.key in ("pageup", "pagedown"):
            self.page_scroll = max(0, self.page_scroll + (12 if ev.key == "pagedown" else -12))
        elif ev.key in ("home", "end") and self.focus == "list" and items:
            self.choose(0 if ev.key == "home" else len(items) - 1)
        elif ev.key == "enter" and items:
            self.choose(self.sel)
        elif ev.key == "backspace":
            self.go_back()
        elif ev.key == "]":
            self.go_ahead()
        elif ev.key in [str(i + 1) for i in range(len(legends.CATEGORIES))]:
            self.set_category(int(ev.key) - 1)
        else:
            return False
        return True

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        name = markup.escape(self.world.meta.name)
        canvas.frame(0, 0, w, h - 1, f"Legends of {name}", double=True)
        x = 2
        for i, (_, label) in enumerate(legends.CATEGORIES):
            text = f" {label} "
            if x + len(text) > w - 2:
                break
            chosen = i == self.cat
            if chosen:
                canvas.fill(x, 1, len(text), 1, colors.HILITE_BG)
            over = canvas.hit(x, 1, len(text), 1, lambda i=i: self.set_category(i))
            canvas.text(x, 1, text, colors.SELECT_FG if chosen else colors.FG if over else colors.DIM)
            x += len(text) + 1
        list_w = min(42, max(22, w // 3))
        self.render_list(canvas, 2, 3, list_w - 2, h - 6)
        self.render_page(canvas, list_w + 2, 3, w - list_w - 4, h - 6)
        hint = ("type to search · Enter to read the first · Esc stop searching" if self.searching else
                "← → kind · ↑↓ choose · / search · Tab page · Backspace back · ] forward · PgUp PgDn · Esc close")
        canvas.text(2, h - 2, hint, colors.FAINT, max_width=w - 4)

    def render_list(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        items = self.entries()
        label = "Search: " + self.query + ("_" if self.searching else "")
        over = canvas.hit(x, y, w, 1, self.start_search, tooltip="Type to find a name (or press /)")
        canvas.text(x, y, label if (self.query or self.searching) else "/ to search",
                    colors.TITLE if self.searching else colors.FG if over else colors.FAINT, max_width=w)
        top = y + 1
        visible = max(1, h - 1)
        self.sel = max(0, min(self.sel, len(items) - 1)) if items else 0
        if self.sel < self.offset:
            self.offset = self.sel
        elif self.sel >= self.offset + visible:
            self.offset = self.sel - visible + 1
        canvas.hit(x, top, w, visible, wheel=self.scroll_list)
        for i, (ref, text) in enumerate(items[self.offset: self.offset + visible]):
            index = self.offset + i
            chosen = ref == self.ref
            row = top + i
            if chosen:
                canvas.fill(x, row, w, 1, colors.HILITE_BG)
            label, whole = legends.cap(text), None
            if len(label) > w > 1:  # too long for the list: it ends in "…", and the whole of it is the tooltip
                label, whole = label[: w - 1].rstrip() + "…", label
            hover = canvas.hit(x, row, w, 1, lambda index=index: self.choose(index), whole)
            fg = colors.SELECT_FG if chosen else colors.FG if hover or index == self.sel else colors.DIM
            canvas.text(x, row, label, fg, max_width=w)
        if not items:
            canvas.markup(x, top, "<dim>Nothing by that name.</>" if self.query else "<dim>Nothing is remembered.</>",
                          max_width=w)

    def start_search(self) -> None:
        self.searching = True

    def scroll_list(self, dy: int) -> None:
        items = self.entries()
        self.offset = max(0, min(max(0, len(items) - 1), self.offset - dy * 3))

    def scroll_page(self, dy: int) -> None:
        self.page_scroll = max(0, self.page_scroll - dy * 3)

    def render_page(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        title, lines = self.page()
        key = (self.ref, w, len(self.world.history))
        if self._layout is None or self._layout[0] != key:
            self._layout = (key, layout(lines, w - 1))
        rows = self._layout[1]
        canvas.text(x, y, legends.cap(markup.escape(title)), colors.TITLE, max_width=w)
        canvas.hline(x, y + 1, w, "─", colors.FAINT)
        body_y, body_h = y + 2, max(1, h - 2)
        most = max(0, len(rows) - body_h)
        self.page_scroll = min(self.page_scroll, most)
        canvas.hit(x, body_y, w, body_h, wheel=self.scroll_page)
        for i, row in enumerate(rows[self.page_scroll: self.page_scroll + body_h]):
            cx = x
            for text, colour, ref in row:
                if ref is not None:
                    hover = canvas.hit(cx, body_y + i, len(text), 1, lambda ref=ref: self.open(ref))
                    if hover:
                        colour = colors.lerp(colour, (255, 255, 255), 0.45)
                cx = canvas.text(cx, body_y + i, text, colour, max_width=x + w - cx)
        if len(rows) > body_h:
            canvas.text(x + w - 8, y, f"{self.page_scroll + 1}/{most + 1}", colors.FAINT)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "down", "enter", "tab", "pagedown", "tab", "right", "down", "right",
                                      "backspace", "/", "a", "enter", "escape")]
