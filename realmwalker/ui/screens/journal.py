"""The Journal: work you have taken on, what is left to do and how it ended, and the people you have met."""

from __future__ import annotations

from realmwalker.game import quests
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas, ScrollText

GROUPS = (("In hand", quests.LIVE), ("Finished", ("finished",)), ("Failed or given up", ("failed", "abandoned")))
TABS = ("Work", "People")


def met_people(game) -> list:
    """Everyone you have spoken to, the ones you know by name first, then by town."""
    folk = [n for n in game.world.npcs.values() if n.met]
    folk.sort(key=lambda n: (game.world.settlements[n.settlement].name if 0 <= n.settlement <
                             len(game.world.settlements) else "", not n.notable, n.name))
    return folk


def person_lines(game, npc) -> str:
    esc = markup.escape
    w = game.world
    town = w.settlements[npc.settlement].name if 0 <= npc.settlement < len(w.settlements) else "somewhere"
    mood_colour = {"hostile": "danger", "unfriendly": "warn", "neutral": "dim", "friendly": "good", "warm": "good"}
    lines = [f"<title>{esc(npc.name)}</>", f"<dim>{esc(npc.title)} of</> <place>{esc(town)}</>", ""]
    lines.append(f"They are <{mood_colour.get(npc.mood(), 'dim')}>{npc.mood()}</> towards you.")
    if not npc.alive:
        lines.append("<danger>Dead.</>")
    elif npc.flags.get("companion"):
        lines.append("<good>Travels with you.</>")
    elif npc.flags.get("recruit"):
        lines.append("<info>Looking for work: they would travel with you.</>")
    from realmwalker.game import quests as q

    work = [x for x in game.quests if x.get("giver") == npc.id]
    if work:
        lines.append("")
        for x in work[-4:]:
            lines.append(f"<dim>·</> {esc(q.title(game, x))} <dim>({x['state']})</>")
    if npc.profile.get("appearance"):
        lines += ["", esc(npc.profile["appearance"])]
    if npc.profile.get("personality"):
        lines.append(esc(npc.profile["personality"]))
    if npc.memory:
        lines += ["", "<title>They remember</>"]
        lines += [f"<dim>·</> {esc(m)}" for m in npc.memory[-5:]]
    return "\n".join(lines)


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
    if q.get("personal") is not None:
        lines.append(f"<dim>For</> {esc(q['giver_name'])} <dim>(who travels with you)</>")
    else:
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

    def __init__(self, app, game, tab: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.tab = tab
        self.sel = 0
        self.offset = 0
        self.detail = ScrollText("")
        self._shown = None

    def rows(self) -> list[tuple[str, object]]:
        if self.tab == 1:
            out: list[tuple[str, object]] = []
            town = None
            for npc in met_people(self.game):
                where = self.game.world.settlements[npc.settlement].name if 0 <= npc.settlement < \
                    len(self.game.world.settlements) else "elsewhere"
                if where != town:
                    town = where
                    out.append(("group", where))
                out.append(("quest", npc))
            return out
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
        elif ev.key in ("tab", "left", "right"):
            self.tab = (self.tab + 1) % len(TABS)
            self.sel = self.offset = 0
            self._shown = None
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
        if self.tab != 0 or q is None or q["state"] not in quests.LIVE:
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
        title = "Journal: the work you have taken on" if self.tab == 0 else "Journal: the people you have met"
        canvas.frame(0, 0, w, h - 1, title, double=True)
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
                if self.tab == 1:
                    mark = "†" if not q.alive else ("·" if not q.notable else "*")
                    color = colors.SELECT_FG if chosen else (colors.DIM if not q.alive else colors.FG)
                    canvas.text(3, y, f"{mark} {q.name}, {q.title}"[: list_w - 4], color)
                else:
                    mark = "!" if q["state"] == "return" else "·"
                    color = colors.named("good") if q["state"] == "return" else (
                        colors.SELECT_FG if chosen else colors.FG if q["state"] in quests.LIVE else colors.DIM)
                    canvas.text(3, y, f"{mark} {quests.title(game, q)}"[: list_w - 4], color)
            y += 1
        if not rows:
            empty = ("<dim>You have taken on no work. Ask people in towns: \"Is there any work?\" "
                     "The notice board may have bounties.</>" if self.tab == 0 else
                     "<dim>You have spoken to nobody yet. Walk into a town and walk into people.</>")
            canvas.markup(3, top, empty, max_width=w - 6)
        dx = list_w + 2
        if sel is not None:
            key = (self.tab, id(sel), game.world.time)
            if self._shown != key:
                self.detail.set_text(person_lines(game, sel) if self.tab == 1 else details(game, sel))
                self._shown = key
            self.detail.render(canvas, dx, top, w - dx - 2, bottom - top)
        bx = canvas.button(2, h - 2, "Close", self.close, hotkey="Esc")
        bx = canvas.button(bx + 2, h - 2, TABS[(self.tab + 1) % len(TABS)],
                           lambda: self.handle_key(KeyEvent("tab")), hotkey="Tab")
        if self.tab == 0 and sel is not None and sel["state"] in quests.LIVE:
            bx = canvas.button(bx + 2, h - 2, "Give it up", self.ask_abandon, hotkey="a")
        canvas.text(bx + 2, h - 2, "↑↓ choose · PgUp PgDn scroll", colors.FAINT, max_width=max(0, w - bx - 4))

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "tab", "down", "up", "pagedown", "tab", "escape")]
