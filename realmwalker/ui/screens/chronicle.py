"""News and history (n): what you have heard, the chronicle of the land, and its legends."""

from __future__ import annotations

from realmwalker.game import news
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText
from realmwalker.world import history

TABS = ("News", "Chronicle", "Legends")


def ensure_chronicle(app, game) -> dict:
    """The chronicle, in built-in words (made the first time it is read, and then kept)."""
    w = game.world
    chron = w.politics.get("chronicle")
    if chron is None:
        chron = history.chronicle_fallback(w, game.tables)
        w.politics["chronicle"] = chron
        game.dirty = True
    return chron


class ChronicleScreen(Screen):
    title = "News and history"
    sound_open = "ui_page"

    def __init__(self, app, game, tab: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.tab = tab
        self.views = [ScrollText(""), ScrollText(""), ScrollText("")]
        self._built: set[int] = set()

    def build(self, i: int) -> None:
        game = self.game
        w = game.world
        t = game.tables
        if i == 0:
            items = news.heard_items(game)
            lines = ["<dim>News reaches you in inns and markets, from travellers, and on notice boards. It travels "
                     "about 24 miles a day along the roads.</>", ""]
            today = news.now_days(w)
            for n in items[:80]:
                text = markup.escape(n["text"][:1].upper() + n["text"][1:])
                lines.append(f"<info>·</> {text} <dim>({news.age_text(today - n['day'])})</>")
            if not items:
                lines.append("<dim>You have heard nothing of the wider world yet. Ask at an inn.</>")
            self.views[0].set_text("\n".join(lines))
        elif i == 1:
            chron = ensure_chronicle(self.app, game)
            body = markup.escape(chron["text"])
            lines = [f"<title>{markup.escape(chron['title'])}</>", "", body, "", "<title>Timeline</>"]
            for e in w.history:
                if e.get("importance", 2) >= 4:
                    lines.append(f"<dim>{e['year']}</>  {markup.escape(e['text'])}")
            self.views[1].set_text("\n".join(lines))
        else:
            lines = ["<title>Dragons</>"]
            for d in w.politics.get("dragons", []):
                if d.get("alive"):
                    lair = w.sites[d["lair"]] if 0 <= d.get("lair", -1) < len(w.sites) else None
                    where = f" Some say its lair is {lair.name}." if lair is not None else ""
                    lines.append(f"<danger>{markup.escape(d['name'])}</>, a {d['color']} dragon: last seen in "
                                 f"{d['last_seen']}.{markup.escape(where)} It may only be sleeping.")
                elif d.get("slain_by"):
                    lines.append(f"<good>{markup.escape(d['name'])}, a {d['color']} dragon: slain by "
                                 f"{markup.escape(d['slain_by'])} in {d.get('slain_year', '')}.</>")
                else:
                    lines.append(f"<dim>{markup.escape(d['name'])}, a {d['color']} dragon: slain long ago.</>")
            lines += ["", "<title>Lost treasures</>"]
            for a in w.politics.get("artifacts", []):
                lines.append(f"<loot>{markup.escape(a['name'])}</>: it {markup.escape(a['fate'])}.")
            fallen = w.politics.get("fallen", [])
            if fallen:
                lines += ["", "<title>Those who came before</>"]
                for r in reversed(fallen[-8:]):
                    kills = sum(r.get("kills", {}).values())
                    lines.append(f"<name>{markup.escape(r['name'])}</> ({r['year']}): "
                                 f"{markup.escape(r['cause'])}, at {markup.escape(r['place'])}."
                                 + (f" {kills} things killed." if kills else ""))
                    if r.get("obituary"):
                        lines.append(f"  <dim>{markup.escape(r['obituary'])}</>")
            lines += ["", "<title>Legends</>"]
            for fig in w.figures.values():
                if fig.role == "legend":
                    deeds = "; ".join(fig.notes) or "is remembered"
                    lines.append(f"<name>{markup.escape(fig.full_name())}</> ({fig.died}): {markup.escape(deeds)}.")
            self.views[2].set_text("\n".join(lines))
        self._built.add(i)

    def open_legends(self) -> None:
        from realmwalker.ui.screens.legends import LegendsScreen

        self.app.push(LegendsScreen(self.app, self.game.world, self.game.tables))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "n"):
            self.close()
        elif ev.key in ("b", "B"):
            self.open_legends()
        elif ev.key in ("tab", "right"):
            self.tab = (self.tab + 1) % len(TABS)
        elif ev.key == "left":
            self.tab = (self.tab - 1) % len(TABS)
        elif ev.key in ("1", "2", "3"):
            self.tab = int(ev.key) - 1
        else:
            return self.views[self.tab].handle_key(ev)
        return True

    def pick(self, i: int) -> None:
        self.tab = i

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, "News and history", double=True)
        x = 2
        for i, name in enumerate(TABS):
            label = f" {i + 1} {name} "
            if i == self.tab:
                canvas.fill(x, 1, len(label), 1, colors.HILITE_BG)
            canvas.hit(x, 1, len(label), 1, lambda i=i: self.pick(i))
            canvas.text(x, 1, label, colors.SELECT_FG if i == self.tab else colors.DIM)
            x += len(label) + 1
        if self.tab not in self._built:
            self.build(self.tab)
        width = min(110, w - 4)
        self.views[self.tab].render(canvas, 2, 3, width, h - 6)
        label = " The Legends book (b) "
        bx = max(x + 2, w - len(label) - 3)
        over = canvas.hit(bx, 1, len(label), 1, self.open_legends,
                          tooltip="Every person, realm, place, war and treasure of the history, with a page each")
        canvas.text(bx, 1, label, colors.SELECT_FG if over else colors.named("title"))
        canvas.text(2, h - 2, "Tab / 1-3 switch · ↑↓ PgUp PgDn scroll · b the Legends book · Esc close", colors.FAINT,
                    max_width=w - 4)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("tab", "pagedown", "tab", "down", "2", "b", "escape")]
