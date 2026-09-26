"""The party (p): who travels with you, how they feel about it, their pay and their orders."""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.game import companions as comp
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas, ScrollText


class PartyScreen(Screen):
    title = "Party"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.sel = 0
        self.detail = ScrollText("")
        self.message = ""

    def members(self) -> list:
        return list(self.game.party) + comp.waiting(self.game)

    def current(self):
        m = self.members()
        if not m:
            return None
        self.sel = max(0, min(self.sel, len(m) - 1))
        return m[self.sel]

    def index_in_party(self) -> int | None:
        c = self.current()
        return self.game.party.index(c) if c in self.game.party else None

    # ------------------------------------------------------------------ actions
    def talk(self) -> None:
        c = self.current()
        if c is None or not c.companion:
            return
        self.message = f"{c.name.split()[0]}: {comp.mood_line(self.game, c)}"

    def their_business(self) -> None:
        """A devoted companion's own job: hear it, take it, or tell them it is done."""
        from realmwalker.game import quests

        c = self.current()
        if c is None or not c.companion:
            return
        q = quests.personal_offer(self.game, c)
        if q is None:
            self.message = f"{c.name.split()[0]} keeps their own business to themselves."
            return
        if q.get("state") == "offered":
            def yes(c=c, q=q) -> None:
                for text in quests.accept_personal(self.game, c, q):
                    self.game.say(text, "info")
                self.message = f"{c.name.split()[0]}: \"Thank you. I won't forget it.\""

            def no(c=c) -> None:
                self.message = quests.refuse_personal(self.game, c)

            self.app.push(ConfirmBox(self.app, quests.personal_pitch(self.game, c, q) +
                                     f"\n\n<dim>({quests.terms(q)})</>", yes, no,
                                     title=f"{c.name.split()[0]} asks something of you"))
            return
        if q.get("done"):
            for text in quests.finish_personal(self.game, c, q):
                self.game.say(text, "good")
            self.message = f"{c.name.split()[0]}: it is settled."
            return
        self.message = f"{c.name.split()[0]} is waiting on you: {quests.title(self.game, q)}."

    def order(self) -> None:
        c = self.current()
        if c is None or not c.companion or c not in self.game.party:
            return
        cycle = ["follow", "watch", "forage", "wait"]
        now = c.companion.get("order", "follow")
        nxt = cycle[(cycle.index(now) + 1) % len(cycle)] if now in cycle else "follow"
        self.message = comp.set_order(self.game, c, nxt)
        self.game.dirty = True

    def raise_pay(self) -> None:
        c = self.current()
        if c is None or not c.companion:
            return
        self.message = comp.raise_wage(self.game, c)
        self.game.dirty = True

    def dismiss(self) -> None:
        c = self.current()
        if c is None or not c.companion:
            return

        def yes() -> None:
            for text in comp.dismiss(self.game, c):
                self.game.say(text, "info")
            self.message = f"{c.name.split()[0]} has gone."

        self.app.push(ConfirmBox(self.app, f"Send {c.name} away? They will go home.", yes, title="Dismiss"))

    def sheet(self, key: str) -> None:
        i = self.index_in_party()
        if i is None:
            self.message = "They are waiting elsewhere."
            return
        from realmwalker.ui.screens.health import HealthScreen
        from realmwalker.ui.screens.sheets import CharacterScreen, EquipmentScreen, InventoryScreen

        cls = {"c": CharacterScreen, "i": InventoryScreen, "e": EquipmentScreen, "h": HealthScreen}[key]
        self.app.push(cls(self.app, self.game, i))

    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.members())
        if ev.key in ("escape", "p"):
            self.close()
        elif ev.key == "up":
            self.sel = max(0, self.sel - 1)
        elif ev.key == "down":
            self.sel = min(max(0, n - 1), self.sel + 1)
        elif ev.key == "t":
            self.talk()
        elif ev.key == "o":
            self.order()
        elif ev.key == "b":
            self.their_business()
        elif ev.key == "w":
            self.raise_pay()
        elif ev.key == "d":
            self.dismiss()
        elif ev.key in ("c", "i", "e", "h"):
            self.sheet(ev.key)
        elif ev.key in ("pageup", "pagedown"):
            self.detail.handle_key(ev)
        return True

    # ------------------------------------------------------------------ drawing
    def details(self, c) -> str:
        g = self.game
        t = g.tables
        lines = [f"<title>{markup.escape(c.name)}</>",
                 f"<dim>{t.races[c.race]['name']} {t.classes[c.cls]['name'].lower()}, level {c.level}"
                 + (f" ({t.classes[c.cls]['subclasses'][c.subclass]['name']})" if c.subclass else "") + "</>",
                 f"Hit points {c.hp}/{c.max_hp}." + ("" if c.companion else f" Money {money_text(c.money)}.")]
        if c.pending:
            lines.append("<info>Has level-up choices waiting (c, then l).</>")
        if c.companion:
            k = c.companion
            spec = comp.data(g)
            arch = spec["archetypes"].get(k.get("archetype"), {})
            word, color = comp.loyalty_word(k.get("loyalty", 50))
            values = [spec["values"][v]["label"] for v in k.get("values", []) if v in spec["values"]]
            days = max(0, (g.world.time - int(k.get("hired", g.world.time))) // 1440)
            who = arch.get("name") or comp.who_they_are(g, c)
            lines += [
                "",
                f"{textgen.a_or_an(who).capitalize()}, with you for {days} day{'s' if days != 1 else ''}.",
                f"Loyalty: <{color}>{word}</> <dim>({int(k.get('loyalty', 50))})</>",
                f"They are {' and '.join(values)}. They want {k.get('want', 'pay')}.",
                markup.escape(comp.bond_text(g, c)) + (f" <warn>Unpaid for {k['unpaid']} days.</>" if k.get("unpaid")
                                                       else "")
                + (f" <dim>(paid {money_text(k['paid'])} so far)</>" if k.get("paid") else ""),
            ]
            if k.get("unique"):
                from realmwalker.game import uniques

                lines.append(f"<info>Gift:</> {markup.escape(uniques.gift(g, c))}")
            lines += [
                f"Orders: {comp.ORDERS.get(k.get('order', 'follow'), 'follow')}."
                + (" <dim>(waiting)</>" if c not in g.party else ""),
            ]
        if c.backstory:
            lines += ["", markup.escape(c.backstory)]
        return "\n".join(lines)

    def render(self, canvas: Canvas) -> None:
        g = self.game
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, "The party", double=True)
        members = self.members()
        cur = self.current()
        list_w = min(40, max(24, w // 3))
        y = 2
        for i, c in enumerate(members):
            chosen = c is cur
            if chosen:
                canvas.fill(2, y, list_w, 1, colors.HILITE_BG)
            canvas.hit(2, y, list_w, 1, lambda i=i: setattr(self, "sel", i))
            tag = ""
            if c.companion:
                word, color = comp.loyalty_word(c.companion.get("loyalty", 50))
                tag = f" <{color}>{word}</>" if c in g.party else " <dim>waiting</>"
            elif c is g.leader:
                tag = " <dim>you</>"
            canvas.markup(3, y, f"{markup.escape(c.name)}{tag}", max_width=list_w - 2)
            y += 1
        n = len(comp.companions(g)) + len(comp.waiting(g))
        canvas.wrapped(2, y + 1, f"<dim>{n} of {comp.data(g)['max_companions']} companions. Find more at inns.</>",
                       list_w, max_lines=2)
        if cur is not None:
            self.detail.set_text(self.details(cur))
            self.detail.render(canvas, list_w + 5, 2, w - list_w - 8, h - 9)
        if self.message:
            canvas.wrapped(2, h - 6, self.message if "<" in self.message else markup.escape(self.message), w - 4,
                           max_lines=2)
        bx = 2
        if cur is not None and cur.companion:
            bx = canvas.button(bx, h - 3, "Talk", self.talk, hotkey="t")
            from realmwalker.game import quests

            offer = quests.personal_offer(self.game, cur)
            if offer is not None:
                label = ("Their own business" if offer.get("state") == "offered" else
                         "It is done" if offer.get("done") else "Their job")
                bx = canvas.button(bx + 2, h - 3, label, self.their_business, hotkey="b")
            bx = canvas.button(bx + 2, h - 3, "Orders", self.order, hotkey="o")
            if cur.companion.get("wage"):  # the others do not come for pay
                bx = canvas.button(bx + 2, h - 3, "Raise pay", self.raise_pay, hotkey="w")
            bx = canvas.button(bx + 2, h - 3, "Dismiss", self.dismiss, hotkey="d")
            bx += 2
        bx = canvas.button(bx, h - 3, "Sheet", lambda: self.sheet("c"), hotkey="c")
        bx = canvas.button(bx + 2, h - 3, "Pack", lambda: self.sheet("i"), hotkey="i")
        canvas.button(bx + 2, h - 3, "Back", self.close, hotkey="Esc")

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "t", "b", "o", "up", "down", "escape")]
