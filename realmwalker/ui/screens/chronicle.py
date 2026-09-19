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
    """The chronicle: the AI's if it has been written, else built-in words (made now, and then kept)."""
    w = game.world
    chron = w.politics.get("chronicle")
    if chron is None:
        chron = history.chronicle_fallback(w, game.tables)
        w.politics["chronicle"] = chron
        game.dirty = True
    return chron


def request_chronicle(app, game) -> None:
    """Ask the AI to write the chronicle, in the background, once per world (before anyone reads it)."""
    w = game.world
    if w.politics.get("chronicle") is not None or w.politics.get("chronicle_asked") or not app.ai.usable():
        return
    if not w.history:
        return
    from realmwalker.ai.service import Priority
    from realmwalker.ai.tasks import CHRONICLE

    w.politics["chronicle_asked"] = True

    def done(result) -> None:
        if w.politics.get("chronicle") is not None:
            return  # the built-in one has been read already; it stays
        if result.ok and result.data and result.data.get("chronicle"):
            w.politics["chronicle"] = {"title": result.data.get("title") or f"A Chronicle of {w.meta.name}",
                                       "text": result.data["chronicle"], "source": "ai"}
            game.dirty = True

    app.ai.submit(CHRONICLE, history.chronicle_facts(w, game.tables), priority=Priority.BACKGROUND, callback=done)


class ChronicleScreen(Screen):
    title = "News and history"

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
            if chron.get("source") == "ai":
                body = "\n\n".join(f"<ai>{p}</>" for p in body.split("\n\n"))
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
                else:
                    lines.append(f"<dim>{markup.escape(d['name'])}, a {d['color']} dragon: slain long ago.</>")
            lines += ["", "<title>Lost treasures</>"]
            for a in w.politics.get("artifacts", []):
                lines.append(f"<loot>{markup.escape(a['name'])}</>: it {markup.escape(a['fate'])}.")
            lines += ["", "<title>Legends</>"]
            for fig in w.figures.values():
                if fig.role == "legend":
                    deeds = "; ".join(fig.notes) or "is remembered"
                    lines.append(f"<name>{markup.escape(fig.full_name())}</> ({fig.died}): {markup.escape(deeds)}.")
            self.views[2].set_text("\n".join(lines))
        self._built.add(i)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "n"):
            self.close()
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
        canvas.text(2, h - 2, "Tab / 1-3 switch · ↑↓ PgUp PgDn scroll · Esc close", colors.FAINT, max_width=w - 4)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("tab", "pagedown", "tab", "down", "2", "escape")]
