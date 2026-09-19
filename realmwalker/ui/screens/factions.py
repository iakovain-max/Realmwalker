"""The Factions screen: the powers of the land as far as you know them, and where you stand with each."""

from __future__ import annotations

from realmwalker.game import reputation
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText
from realmwalker.world import factions as fx

GROUP_ORDER = ("realms", "wild", "faiths", "guilds", "outlaws")


class FactionsScreen(Screen):
    title = "Factions"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.sel = 0
        self.offset = 0
        self.detail = ScrollText("")
        self._shown = None

    def rows(self) -> list[tuple[str, object]]:
        """('group', label) headers and ('faction', faction) rows, in display order."""
        t = self.game.tables.factions
        known = reputation.known_factions(self.game)
        out: list[tuple[str, object]] = []
        for group in GROUP_ORDER:
            members = [f for f in known if t["kinds"][f.kind]["group"] == group]
            if not members:
                continue
            members.sort(key=lambda f: (f.liege >= 0, f.name.lower().removeprefix("the ")))
            out.append(("group", t["groups"][group]))
            out += [("faction", f) for f in members]
        return out

    def factions(self) -> list:
        return [f for kind, f in self.rows() if kind == "faction"]

    def selected(self):
        facs = self.factions()
        if not facs:
            return None
        self.sel = max(0, min(self.sel, len(facs) - 1))
        return facs[self.sel]

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.factions())
        if ev.key in ("escape", "f"):
            self.close()
        elif ev.key == "up":
            self.sel = max(0, self.sel - 1)
        elif ev.key == "down":
            self.sel = min(max(0, n - 1), self.sel + 1)
        elif ev.key == "home":
            self.sel = 0
        elif ev.key == "end":
            self.sel = max(0, n - 1)
        elif ev.key in ("pageup", "pagedown"):
            self.detail.handle_key(ev)
        return True

    def pick(self, i: int) -> None:
        self.sel = i

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        game = self.game
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, "Factions: the powers of the land, as far as you know them", double=True)
        r = game.renown
        head = f"<dim>Fame</> {r.fame}   <dim>Infamy</> {r.infamy}"
        bounties = [(game.world.factions[fid], amount) for fid, amount in r.bounties.items()
                    if amount > 0 and fid in game.world.factions]
        if bounties:
            head += "   <danger>Wanted in " + ", ".join(
                f"{markup.escape(f.name)} ({money_text(a)})" for f, a in bounties[:3]) + "</>"
        canvas.markup(2, 1, head, max_width=w - 4)
        list_w = min(46, max(24, w // 3))
        rows = self.rows()
        sel = self.selected()
        top, bottom = 3, h - 3
        visible = max(1, bottom - top)
        index_of_sel = next((i for i, (k, f) in enumerate(rows) if k == "faction" and f is sel), 0)
        if index_of_sel < self.offset + 1:
            self.offset = max(0, index_of_sel - 1)
        elif index_of_sel >= self.offset + visible:
            self.offset = index_of_sel - visible + 1
        fi = sum(1 for kind, _ in rows[: self.offset] if kind == "faction") - 1
        y = top
        for kind, item in rows[self.offset: self.offset + visible]:
            if kind == "group":
                canvas.section(2, y, list_w - 2, str(item))
            else:
                fi += 1
                f = item
                name = f.name[:1].upper() + f.name[1:]
                score = reputation.standing(game, f.id)
                _, color = fx.standing_name(game.tables, score)
                chosen = f is sel
                if chosen:
                    canvas.fill(2, y, list_w - 2, 1, colors.HILITE_BG)
                canvas.hit(2, y, list_w - 2, 1, lambda i=fi: self.pick(i))
                indent = "  " if f.liege >= 0 else ""
                canvas.text(3, y, (indent + name)[: list_w - 9], colors.SELECT_FG if chosen else colors.FG)
                canvas.text(list_w - 5, y, f"{score:+d}".rjust(4), colors.named(color))
            y += 1
        if not rows:
            canvas.markup(3, top, "<dim>You know of no one yet.</>")
        # The details of the chosen one.
        dx = list_w + 2
        if sel is not None:
            if self._shown != (sel.id, game.world.time):
                self.detail.set_text(reputation.faction_details(game, sel))
                self._shown = (sel.id, game.world.time)
            self.detail.render(canvas, dx, top, w - dx - 2, bottom - top)
        canvas.text(2, h - 2, "↑↓ choose · PgUp PgDn scroll the details · Esc close", colors.FAINT, max_width=w - 4)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "down", "up", "end", "pagedown", "home", "escape")]
