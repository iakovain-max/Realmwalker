"""The Journal: the tales you are part of (Expansion 6), work you have taken on, what is left to do and how it
ended, and the people you have met."""

from __future__ import annotations

from realmwalker.game import quests
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas, ScrollText

GROUPS = (("In hand", quests.LIVE), ("Finished", ("finished",)), ("Failed or given up", ("failed", "abandoned")))
TABS = ("Adventures", "Work", "People")
ADVENTURES, WORK, PEOPLE = 0, 1, 2
TALE_GROUPS = (("Under way", ("active",)), ("Ended", ("won", "lost", "abandoned", "orphaned")))


def met_people(game) -> list:
    """Everyone you have spoken to, the ones you know by name first, then by town."""
    folk = [n for n in game.world.npcs.values() if n.met]
    folk.sort(key=lambda n: (game.world.settlements[n.settlement].name if 0 <= n.settlement <
                             len(game.world.settlements) else "", not n.notable, n.name))
    return folk


STEP_WORDS = {"go": "Go to {place}.", "search": "Search {place} for what it left.",
              "witness": "Find {who}, who saw it, and hear it from them.", "read": "Read {what}.",
              "learn": "Learn what {villain} fears: {routes}.", "prepare": "Get the means: {means}.",
              "choose": "Decide how to bring it to you.", "slay": "Face {villain}.",
              "finale": "Finish it at {place}.",
              "rescue": "Bring {who} out of {place}.", "fetch": "Bring {what} out of {place}.",
              "defeat": "Overcome {who}, at {place}.", "capture": "Take {who} alive, at {place}.",
              "recruit": "Win {who} to your side.", "rally": "Raise the people of {place} to stand.",
              "hold": "Hold {place} on the night of {night}.", "rite": "Perform the rite at {place}.",
              "escort": "Walk {who} safely to {to}.", "confront": "Confront {who} with what you know."}
ROUTE_WORDS = {"talk": "ask someone who knows", "check": "study its kill", "divine": "magic",
               "tail": "follow someone by night"}
CHECK_WORDS = {"nature": "study its kill", "history": "read the place's past", "religion": "read the signs of the dead",
               "insight": "watch the people", "investigation": "search the place"}


def _thing(game, adv, st) -> str:
    """The thing a read or fetch step is about, in words (a fetch's name filled from the tale's words)."""
    tg = st["target"]
    if st["kind"] != "fetch":
        return tg.get("item", "it")
    q = quests.by_id(game, st.get("quest"))
    return q["target"]["item"] if q is not None else "what the tale needs"


def trouble_lines(game, sit) -> str:
    """A trouble (a situation) in the journal, in the hero's own notes (game/story/situations.py)."""
    from realmwalker.game.story import situations

    return situations.journal_lines(game, sit)


def tale_lines(game, adv) -> str:
    """A tale in the journal: its chapters (done, now, to come), what is to be done now and where, the people of it,
    what you have found, and what you have written of it."""
    from realmwalker.game import story
    from realmwalker.game.story import cast, places
    from realmwalker.game.story import words as wordsmod
    from realmwalker.world import threats

    esc = markup.escape
    w = game.world
    words = wordsmod.for_adventure(game, adv)
    lines = [f"<title>{esc(adv['title'])}</>", "", esc(adv["words"]["premise"]), ""]
    for i, ch in enumerate(adv["chapters"]):
        now = i == adv["chapter"] and adv["state"] == "active"
        mark = "<good>[x]</>" if ch["state"] == "done" else "<warn>[>]</>" if now else "<faint>[ ]</>"
        lines.append(f"{mark} {esc(ch['title'])}" if ch["state"] != "locked" else f"{mark} <faint>to come</>")
    ch = story.chapter(adv)
    if adv["state"] == "active" and ch is not None:
        lines += ["", f"<title>Now</> {esc(ch['goal'])}"]
        for st in ch["steps"]:
            tg = st["target"]
            routes = ", ".join(CHECK_WORDS.get(r.get("skill", ""), ROUTE_WORDS["check"]) if r.get("how") == "check"
                               else ROUTE_WORDS.get(r.get("how", ""), r.get("how", "")) for r in tg.get("routes", []))
            means = ", ".join(game.tables.items.get(m)["name"] for m in tg.get("means", []) if game.tables.items.get(m))
            text = st["note"] + (f" ({routes})" if routes else "") if st.get("note") else \
                STEP_WORDS.get(st["kind"], st["kind"]).format(
                place=places.name(w, tg["place"]) if tg.get("place") else "the place",
                who=cast.describe(game, adv, tg["role"]) if tg.get("role") else "them",
                villain=words.get("villain", "it"), routes=routes, means=means or "something",
                what=_thing(game, adv, st), to=places.name(w, tg["to"]) if tg.get("to") else "the place",
                night=quests.when_text(game, int(tg["night"])) if tg.get("night") is not None else "a night to come")
            mark = "<good>[x]</>" if st["state"] == "done" else "<warn>[lost]</>" if st["state"] == "failed" else                 "<faint>(if you like)</>" if st["optional"] else "-"
            lines.append(f"  {mark} {esc(text)}")
    known = [r for r in ("patron", "ally", "witness") if r in adv["cast"]]
    if known:
        lines += ["", "<title>People</> " + "; ".join(f"{esc(cast.describe(game, adv, r))} ({r})" for r in known)]
    if adv["keys"]:
        lines += ["", "<title>Found</> " + "; ".join(esc(wordsmod.key_text(game, adv, k)) for k in adv["keys"])]
    th = threats.records(w).get(adv["threat"])
    if th is not None and th["state"] in threats.LIVE:
        n = len(th["scheme"]["stages"])
        clock = "".join("#" if i <= th["scheme"]["stage"] else "." for i in range(n))
        lines += ["", f"<title>Its time</> <danger>{clock}</> <dim>(when the last mark is filled, it has won)</>"]
    if adv["state"] == "active" and not adv.get("boss_dead"):  # (how much the villain cares about you: E.1)
        from realmwalker.game.story import villain

        top = int(villain.spec(game)["max"])
        att = max(0, min(top, int(adv.get("attention", 0))))
        eye = "#" * att + "." * (top - att)
        lines.append(f"<title>Its eye</> <warn>{eye}</> {esc(words.get('villain_short', 'it'))}: "
                     f"{esc(villain.level(game, adv))}")
        if (adv.get("token") or {}).get("used"):  # (once it has shown you what its spy took)
            lines.append(f"<dim>It holds {esc(adv['token']['what'])}, {esc(adv['token']['of'])}'s.</>")
    if adv.get("journal"):
        lines += ["", "<title>Your notes</>"] + [f"<dim>{esc(j['text'])}</>" for j in adv["journal"][-6:]]
    if adv.get("ending"):
        lines += ["", f"<title>How it ended</> {esc(adv['ending'].replace('_', ' '))}"]
        lines += [f"<dim>{esc(pg['text'])}</>" for pg in adv.get("epilogue", [])]
    return "\n".join(lines)


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
    from realmwalker.game.story import favours

    lines += favours.person_lines(game, npc)  # (a favour owed, a contact: C.7)
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
    elif q["giver_name"].endswith(town.name):  # ("the watch of Bradwich", not "... of Bradwich of Bradwich")
        lines.append(f"<dim>For</> {esc(q['giver_name'])}")
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
    if q.get("contract") is not None:
        from realmwalker.game.story import work

        lines.append(work.terms_note(game, q))  # (paid work shows its terms)
    if q["state"] in quests.LIVE and not q.get("done"):
        danger = quests.danger_note(game, q)  # how the beast or the raiders measure up against the party now
        if danger:
            lines.append(danger)
    if q.get("revealed"):
        lines.append("<warn>There is more to this than you were told.</>")
    lines.append("")
    for entry in q["journal"]:
        lines.append(esc(entry))
        lines.append("")
    return "\n".join(lines)


class JournalScreen(Screen):
    title = "Journal"
    sound_open = "ui_page"

    def __init__(self, app, game, tab: int | None = None) -> None:
        super().__init__(app)
        self.game = game
        if tab is None:  # (the tales first, when there are any; else the work in hand)
            from realmwalker.game.story import forge

            from realmwalker.game.story import situations

            life = forge.life_of(game)
            tales = any(a["hero"]["life"] == life for a in game.world.politics.get("adventures", {}).values()) or \
                bool(situations.troubles(game))
            tab = ADVENTURES if tales else WORK
        self.tab = tab
        self.sel = 0
        self.offset = 0
        self.detail = ScrollText("")
        self._shown = None

    def rows(self) -> list[tuple[str, object]]:
        if self.tab == ADVENTURES:
            from realmwalker.game.story import forge

            life = forge.life_of(self.game)
            mine = [a for a in self.game.world.politics.get("adventures", {}).values() if a["hero"]["life"] == life]
            out: list[tuple[str, object]] = []
            for label, states in TALE_GROUPS:
                members = sorted((a for a in mine if a["state"] in states), key=lambda a: -int(a["id"][1:]))
                if members:
                    out.append(("group", label))
                    out += [("quest", a) for a in members]
            from realmwalker.game.story import situations

            troubles = situations.troubles(self.game)  # (the people's troubles you have met: C.6)
            if troubles:
                out.append(("group", "Troubles"))
                out += [("quest", s) for s in troubles]
            return out
        if self.tab == PEOPLE:
            from realmwalker.game.story import favours

            out: list[tuple[str, object]] = []
            friends = favours.people_rows(self.game)  # (favours owed and contacts first: C.7)
            friend_ids = {n.id for n in friends}
            if friends:
                out.append(("group", "Favours and contacts"))
                out += [("quest", n) for n in friends]
            town = None
            for npc in met_people(self.game):
                if npc.id in friend_ids:
                    continue
                where = self.game.world.settlements[npc.settlement].name if 0 <= npc.settlement < \
                    len(self.game.world.settlements) else "elsewhere"
                if where != town:
                    town = where
                    out.append(("group", where))
                out.append(("quest", npc))
            return out
        out: list[tuple[str, object]] = []
        for label, states in GROUPS:
            members = [q for q in self.game.quests if q["state"] in states and not q.get("adventure")]
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
        if self.tab != WORK or q is None or q["state"] not in quests.LIVE:
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
        title = {ADVENTURES: "Journal: the tales you are part of", WORK: "Journal: the work you have taken on",
                 PEOPLE: "Journal: the people you have met"}[self.tab]
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
                if self.tab == ADVENTURES and "predicament" in q:
                    from realmwalker.game.story import situations

                    live = q["state"] in situations.LIVE
                    mark = "!" if q["state"] == "met" else "·" if live else ("*" if q["state"] == "done" else "-")
                    color = colors.SELECT_FG if chosen else (colors.FG if live else colors.DIM)
                    canvas.text(3, y, f"{mark} {situations.title(game, q)}"[: list_w - 4], color)
                elif self.tab == ADVENTURES:
                    mark = "·" if q["state"] == "active" else ("*" if q["state"] == "won" else "-")
                    color = colors.SELECT_FG if chosen else (colors.FG if q["state"] == "active" else colors.DIM)
                    canvas.text(3, y, f"{mark} {q['title']}"[: list_w - 4], color)
                elif self.tab == PEOPLE:
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
            empty = ("<dim>You have taken on no work. Read the notice boards for bounties and for who is hiring, "
                     "and listen to people: someone with a real need will ask you. A faction you join sends word of "
                     "its own work.</>"
                     if self.tab == WORK else
                     "<dim>You are part of no tale yet. Listen in towns for what troubles them, and read the notice "
                     "boards: someone always needs a hero.</>" if self.tab == ADVENTURES else
                     "<dim>You have spoken to nobody yet. Walk into a town and walk into people.</>")
            canvas.markup(3, top, empty, max_width=w - 6)
        dx = list_w + 2
        if sel is not None:
            key = (self.tab, id(sel), game.world.time)
            if self._shown != key:
                self.detail.set_text(person_lines(game, sel) if self.tab == PEOPLE else
                                     trouble_lines(game, sel) if self.tab == ADVENTURES and "predicament" in sel else
                                     tale_lines(game, sel) if self.tab == ADVENTURES else details(game, sel))
                self._shown = key
            self.detail.render(canvas, dx, top, w - dx - 2, bottom - top)
        bx = canvas.button(2, h - 2, "Close", self.close, hotkey="Esc")
        bx = canvas.button(bx + 2, h - 2, TABS[(self.tab + 1) % len(TABS)],
                           lambda: self.handle_key(KeyEvent("tab")), hotkey="Tab")
        if self.tab == WORK and sel is not None and sel["state"] in quests.LIVE:
            bx = canvas.button(bx + 2, h - 2, "Give it up", self.ask_abandon, hotkey="a")
        canvas.text(bx + 2, h - 2, "↑↓ choose · PgUp PgDn scroll", colors.FAINT, max_width=max(0, w - bx - 4))

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "tab", "down", "up", "pagedown", "tab", "escape")]
