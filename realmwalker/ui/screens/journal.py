"""The Journal: work you have taken on, what is left to do, and how it ended."""

from __future__ import annotations

from realmwalker.game import quests
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas, ScrollText

GROUPS = (("In hand", quests.LIVE), ("Finished", ("finished",)), ("Failed or given up", ("failed", "abandoned")))


def status_markup(game, q) -> str:
    state = q["state"]
    if state == "return":
        who = q["giver_name"] if q["giver"] >= 0 else f"the watch of {game.world.settlements[q['town']].name}"
        return f"<good>Done: go back to {markup.escape(who)}.</>"
    if state == "active":
        left = quests.days_left(game, q)
        if left is None:
            return "<info>Under way.</>"
        color = "danger" if left <= 2 else "warn" if left <= 5 else "info"
        return f"<{color}>{max(0, left)} day{'s' if left != 1 else ''} left.</>"
    return {"finished": "<dim>Finished.</>", "failed": "<danger>Failed.</>",
            "abandoned": "<dim>Given up.</>"}.get(state, state)


def details(game, q) -> str:
    esc = markup.escape
    w = game.world
    town = w.settlements[q["town"]]
    lines = [f"<title>{esc(quests.title(game, q))}</>", status_markup(game, q), ""]
    lines.append(f"<dim>For</> {esc(q['giver_name'])} <dim>of</> {esc(town.name)}")
    reward = q["reward"]
    if q["template"] == "collect_debt":
        lines.append(f"<dim>Pay</> a quarter of what you collect (the debt is {esc(q['words'].get('debt', '?'))})")
    else:
        lines.append(f"<dim>Pay</> {money_text(reward)}")
    t = q["target"]
    if "site" in t and 0 <= t["site"] < len(w.sites):
        s = w.sites[t["site"]]
        lines.append(f"<dim>Where</> {esc(quests.cap(s.name))} <dim>({esc(quests.direction(town, s))})</>")
    if "dest" in t and 0 <= t["dest"] < len(w.settlements):
        lines.append(f"<dim>Where</> {esc(w.settlements[t['dest']].name)} "
                     f"<dim>({esc(quests.direction(town, w.settlements[t['dest']]))})</>")
    if q["template"] == "hunt_beast":
        lines.append(f"<dim>Where</> {esc(q['words'].get('where', ''))} <dim>(marked on your map)</>")
    if q.get("revealed"):
        lines.append("<warn>There is more to this than you were told.</>")
    lines.append("")
    for entry in q["journal"]:
        lines.append(esc(entry))
        lines.append("")
    return "\n".join(lines)


class JournalScreen(Screen):
    title = "Journal"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.sel = 0
        self.offset = 0
        self.detail = ScrollText("")
        self._shown = None

    def rows(self) -> list[tuple[str, object]]:
        out: list[tuple[str, object]] = []
        for label, states in GROUPS:
            members = [q for q in self.game.quests if q["state"] in states]
            if not members:
                continue
            members.sort(key=lambda q: (q["state"] != "return", q.get("deadline") or 0) if q["state"] in quests.LIVE
                         else -(q.get("finished") or q.get("taken") or 0))
            out.append(("group", label))
            out += [("quest", q) for q in members]
        return out

    def entries(self) -> list[dict]:
        return [q for kind, q in self.rows() if kind == "quest"]

    def selected(self) -> dict | None:
        items = self.entries()
        if not items:
            return None
        self.sel = max(0, min(self.sel, len(items) - 1))
        return items[self.sel]

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.entries())
        if ev.key in ("escape", "j"):
            self.close()
        elif ev.key == "up":
            self.sel = max(0, self.sel - 1)
        elif ev.key == "down":
            self.sel = min(max(0, n - 1), self.sel + 1)
        elif ev.key in ("pageup", "pagedown"):
            self.detail.handle_key(ev)
        elif ev.key == "a":
            self.ask_abandon()
        return True

    def pick(self, i: int) -> None:
        self.sel = i

    def ask_abandon(self) -> None:
        q = self.selected()
        if q is None or q["state"] not in quests.LIVE:
            return

        def yes(q=q) -> None:
            quests.abandon(self.game, q)
            self._shown = None

        self.app.push(ConfirmBox(self.app, f"Give up {markup.escape(quests.title(self.game, q))}? "
                                           f"{markup.escape(q['giver_name'])} will not forget it.", yes,
                                 title="Give it up?", danger=True))

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        game = self.game
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, "Journal: the work you have taken on", double=True)
        list_w = min(46, max(26, w // 3))
        rows = self.rows()
        sel = self.selected()
        top, bottom = 2, h - 3
        visible = max(1, bottom - top)
        index_of_sel = next((i for i, (k, q) in enumerate(rows) if k == "quest" and q is sel), 0)
        if index_of_sel < self.offset + 1:
            self.offset = max(0, index_of_sel - 1)
        elif index_of_sel >= self.offset + visible:
            self.offset = index_of_sel - visible + 1
        qi = sum(1 for kind, _ in rows[: self.offset] if kind == "quest") - 1
        y = top
        for kind, item in rows[self.offset: self.offset + visible]:
            if kind == "group":
                canvas.section(2, y, list_w - 2, str(item))
            else:
                qi += 1
                q = item
                chosen = q is sel
                if chosen:
                    canvas.fill(2, y, list_w - 2, 1, colors.HILITE_BG)
                canvas.hit(2, y, list_w - 2, 1, lambda i=qi: self.pick(i))
                mark = "!" if q["state"] == "return" else "·"
                color = colors.named("good") if q["state"] == "return" else (
                    colors.SELECT_FG if chosen else colors.FG if q["state"] in quests.LIVE else colors.DIM)
                canvas.text(3, y, f"{mark} {quests.title(game, q)}"[: list_w - 4], color)
            y += 1
        if not rows:
            canvas.markup(3, top, "<dim>You have taken on no work. Ask people in towns: \"Is there any work?\" "
                                  "The notice board may have bounties.</>", max_width=w - 6)
        dx = list_w + 2
        if sel is not None:
            key = (sel["id"], sel["state"], len(sel["journal"]), game.world.time)
            if self._shown != key:
                self.detail.set_text(details(game, sel))
                self._shown = key
            self.detail.render(canvas, dx, top, w - dx - 2, bottom - top)
        hint = "↑↓ choose · PgUp PgDn scroll · a give it up · Esc close"
        canvas.text(2, h - 2, hint, colors.FAINT, max_width=w - 4)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "up", "pagedown", "escape")]
