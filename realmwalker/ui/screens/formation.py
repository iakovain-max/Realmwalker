"""Battle order (f on the party screen): where each member of the party stands when a fight begins.

A block of five squares by five, the front row towards the enemy. Choose someone (click them, or 1-5, or Tab) and put
them on a square (click it, or the arrow keys): whoever stood there takes their old place. When the enemy comes from
all sides the block is turned to face the most of them, and in a narrow place it is squeezed into the room there is.
"""

from __future__ import annotations

from realmwalker.game import arena
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

N = arena.FORMATION_SIZE
MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
ROW_WORDS = ["front", "second", "middle", "fourth", "rear"]


class FormationScreen(Screen):
    title = "Battle order"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.sel = 0
        self.message = ""

    def party(self) -> list:
        return [c for c in self.game.party if c.alive]

    def cells(self) -> list[tuple[int, int]]:
        return arena.formation(self.party())

    def place(self, cell: tuple[int, int]) -> None:
        party = self.party()
        if not party:
            return
        self.sel = max(0, min(self.sel, len(party) - 1))
        arena.set_cell(party, self.sel, cell)
        who = party[self.sel].name.split()[0]
        self.message = f"{who}: {ROW_WORDS[cell[1]]} row."
        self.game.dirty = True

    def reset(self) -> None:
        for c in self.party():
            c.formation = []
        self.message = "Back to the usual order: fighters in front, priests and rogues behind them, wizards at the back."
        self.game.dirty = True

    def handle_key(self, ev: KeyEvent) -> bool:
        party = self.party()
        if ev.key in ("escape", "f"):
            self.close()
            return True
        if not party:
            return True
        if ev.key == "tab":
            self.sel = (self.sel + (-1 if ev.shift else 1)) % len(party)
        elif ev.is_text and ev.key.isdigit() and 1 <= int(ev.key) <= len(party):
            self.sel = int(ev.key) - 1
        elif ev.key in MOVES:
            c, r = self.cells()[self.sel]
            dx, dy = MOVES[ev.key]
            self.place((max(0, min(N - 1, c + dx)), max(0, min(N - 1, r + dy))))
        elif ev.key == "r":
            self.reset()
        return True

    def render(self, canvas: Canvas) -> None:
        from realmwalker.ui.gfx import dolls, scenes, theme
        from realmwalker.ui.gfx.scene import Rect

        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, "Battle order", double=True)
        party = self.party()
        cells = self.cells()
        self.sel = max(0, min(self.sel, len(party) - 1)) if party else 0
        list_w = min(34, max(22, w // 3))
        y = 2
        canvas.text(2, y, "Who", colors.TITLE)
        y += 1
        for i, c in enumerate(party):
            chosen = i == self.sel
            rows = 3
            if chosen:
                canvas.fill(2, y, list_w, rows, colors.HILITE_BG)
            canvas.hit(2, y, list_w, rows, lambda i=i: setattr(self, "sel", i))
            col, row = cells[i]
            label = f"{i + 1}. {markup.escape(c.name)}"
            sub = f"<dim>{self.game.tables.classes[c.cls]['name'].lower()}, {ROW_WORDS[row]} row</>"
            canvas.clear_cells(3, y, 6, 3)
            scenes.bust(canvas, dolls.character(c, self.game.tables, atlas=canvas.gfx.atlas),
                        tuple(int(v) for v in canvas.cell_rect(3, y, 6, 3)))
            canvas.markup(10, y, label, fg=colors.SELECT_FG if chosen else colors.FG, max_width=list_w - 9)
            canvas.markup(10, y + 1, sub, max_width=list_w - 9)
            y += 4
        # The block itself.
        gx = list_w + 6
        room_w, room_h = w - gx - 3, h - 12
        cw = max(3, min(12, room_w // N))
        ch = max(1, min(6, room_h // N))
        ch = max(2, min(ch, (cw * canvas.cell_w) // max(1, canvas.cell_h)))
        canvas.markup(gx, 2, "<title>Towards the enemy</> ↑", max_width=room_w)
        top = 3
        occupant = {cell: i for i, cell in enumerate(cells)}
        for r in range(N):
            for c in range(N):
                x0, y0 = gx + c * cw, top + r * ch
                i = occupant.get((c, r))
                chosen = i is not None and i == self.sel
                over = canvas.hit(x0, y0, cw, ch, action=lambda c=c, r=r: self.place((c, r)),
                                  tooltip=f"{ROW_WORDS[r]} row" + (f": {markup.escape(party[i].name)}" if i is not None else ""))
                bg = colors.HILITE_BG if chosen else (colors.HOVER_BG if over else (28, 26, 30) if (c + r) % 2 else (22, 20, 24))
                px, py, pw, ph = canvas.cell_rect(x0, y0, cw, ch)
                canvas.clear_cells(x0, y0, cw, ch)
                canvas.under(Rect(px + 1, py + 1, pw - 2, ph - 2, (*bg, 255)))
                canvas.under(theme.lines_box(px + 1, py + 1, pw - 2, ph - 2,
                                             (214, 176, 108, 230) if chosen else (90, 74, 52, 200)))
                if i is not None:
                    size = min(pw, ph) - 6
                    size = max(16, (size // 16) * 16)
                    cmd = dolls.draw(canvas.gfx.atlas, dolls.character(party[i], self.game.tables, atlas=canvas.gfx.atlas),
                                     px + (pw - size) / 2, py + (ph - size) / 2, size)
                    if cmd is not None:
                        canvas.under(cmd)
                    canvas.text(x0, y0, str(i + 1), colors.TITLE)
        y = top + N * ch + 1
        text = ("Choose someone (click, 1-5 or Tab), then click a square or use the arrow keys; whoever stood there takes "
                "their place. The front row faces the enemy when a fight begins. Spread out against fire and spells; "
                "keep the fragile behind a shield wall. Where there is no room, the block is squeezed into what room there "
                "is, front rank first; when they come from all sides, it turns to face the most of them.")
        canvas.wrapped(gx, y, f"<dim>{text}</>", room_w, max_lines=max(2, h - y - 5))
        if self.message:
            canvas.wrapped(2, h - 5, markup.escape(self.message), w - 4, max_lines=1)
        bx = canvas.button(2, h - 3, "Usual order", self.reset, hotkey="r")
        canvas.button(bx + 2, h - 3, "Back", self.close, hotkey="Esc")

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("tab", "up", "left", "down", "right", "1", "2", "r", "escape")]
