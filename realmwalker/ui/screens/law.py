"""The law's windows: the watch has hold of you (ArrestScreen), and the sentence being carried out (SentenceScreen)."""

from __future__ import annotations

from realmwalker.game import law
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas

ARREST_KEYS = {"pay": "p", "quiet": "q", "bribe": "b", "run": "r", "fight": "f"}


class ArrestScreen(Screen):
    modal = True
    title = "The watch"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.message = ""

    def intro(self) -> str:
        game = self.game
        a = game.arrest
        w = game.world
        realm = w.factions[a["realm"]]
        guard = w.npcs.get(a.get("guard", -1))
        who = guard.label() if guard is not None else "The watch"
        crimes = law.open_crimes(game, realm.id)
        if crimes:
            names = sorted({law.crime_def(game, r["crime"])["name"] for r in crimes if r["crime"] in game.tables.law["crimes"]})
            what = ", ".join(names) or "old crimes"
        else:
            what = "your record"
        bounty = game.renown.bounties.get(realm.id, 0)
        text = (f"{who[:1].upper() + who[1:]} takes hold of your arm. \"In the name of {realm.name}. You're wanted "
                f"for {what}.\"")
        if bounty:
            text += f" The price on your head here is {money_text(bounty)}."
        return text

    def act(self, action: str) -> None:
        game = self.game
        if game.arrest is None:
            self.close()
            return
        if action == "pay":
            text = law.pay_bounty(game, game.arrest["realm"])
            game.say(text, "info")
            if "clean" in text:
                game.arrest = None
                self.close()
            else:
                self.message = text
        elif action == "quiet":
            law.go_quietly(game)
            self.close()
        elif action == "bribe":
            ok, text = law.bribe_guard(game)
            game.say(text, "info" if ok else "warn")
            if ok:
                self.close()
            else:
                self.message = text
        elif action == "run":
            ok, text = law.run_for_it(game)
            game.say(text, "info" if ok else "warn")
            if ok:
                self.close()
            else:
                self.message = text
        elif action == "fight":
            law.fight_the_watch(game)
            self.close()

    def handle_key(self, ev: KeyEvent) -> bool:
        if self.game.arrest is None:
            self.close()
            return True
        for action, label, enabled, why in law.arrest_options(self.game):
            if ev.key == ARREST_KEYS[action]:
                if enabled:
                    self.act(action)
                else:
                    self.app.notify(why[:1].upper() + why[1:] + ".", "warn")
                return True
        return True

    def render(self, canvas: Canvas) -> None:
        game = self.game
        if game.arrest is None:
            return
        width = min(80, canvas.width - 4)
        iw = width - 4
        intro = markup.wrap(markup.escape(self.intro()), iw)
        msg = markup.wrap(self.message, iw) if self.message else []
        opts = law.arrest_options(game)
        x, y, w, h = modal_box(canvas, width, len(intro) + len(msg) + len(opts) + 8, "The watch",
                               fg=colors.named("danger"))
        row = y + 2
        for line in intro:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        row += 1
        for line in msg:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        if msg:
            row += 1
        for action, label, enabled, why in opts:
            text = label if enabled else f"{label}: {why}"
            canvas.button(x + 2, row, text[: iw - 4], lambda a=action: self.act(a), hotkey=ARREST_KEYS[action].upper(),
                          enabled=enabled)
            row += 1
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("p", "b", "r", "q", "f")]


class SentenceScreen(Screen):
    modal = True
    title = "Sentence"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        s = game.sentence
        realm = game.world.factions.get(s["realm"]) if s else None
        self.header = (f"The law of {realm.name}: {law.sentence_text(s['steps'])}." if realm is not None and s["steps"]
                       else "")

    def options(self) -> list[tuple[str, str, str]]:
        """(key, label, action)."""
        s = self.game.sentence
        if s is None or s.get("finished") or self.game.over is not None:
            return [("enter", "Go on", "close")]
        if s.get("gallows"):
            from realmwalker.game import stonework

            how = "Knock +10" if stonework.knock_in_cell(self.game) is not None else "Sleight of Hand / Athletics"
            return [("e", f"[{how}] Try to get out of the cell tonight (very hard)", "escape_gallows"),
                    ("a", "Wait for the morning", "hang")]
        step = law.next_step(self.game)
        if step is None:
            return [("enter", "Go on", "close")]
        kind, _, n = step.partition(":")
        label = {"fine": "Pay the fine", "flogging": "Take the lash", "branding": "Take the brand",
                 "death": "Hear the sentence", "jail": f"Serve {n} days in the cells",
                 "labour": f"Serve {n} days of hard labour"}.get(kind, "Go on")
        out = [("enter", label, "step")]
        if kind in ("jail", "labour"):
            from realmwalker.game import stonework

            how = "Knock +10" if stonework.knock_in_cell(self.game) is not None else "Sleight of Hand / Athletics"
            out.append(("e", f"[{how}] Try to escape instead", "escape"))
        return out

    def act(self, action: str) -> None:
        game = self.game
        s = game.sentence
        if action == "close" or s is None:
            game.sentence = None
            self.close()
            return
        if action == "step":
            law.carry_out(game)
        elif action == "escape":
            ok, text = law.attempt_escape(game, int(game.tables.law["escape_dc"]))
            s["notes"].append(text)
            if not ok:
                step = law.next_step(game)
                if step is not None and ":" in step:
                    kind, _, n = step.partition(":")
                    i = s["steps"].index(step)
                    s["steps"][i] = f"{kind}:{int(n) + 7}"
                    s["notes"].append("They add a week to your time, and a beating to go with it.")
        elif action == "escape_gallows":
            s["notes"] += law.gallows_choice(game, escape=True)
        elif action == "hang":
            s["notes"] += law.gallows_choice(game, escape=False)
        game.dirty = True

    def handle_key(self, ev: KeyEvent) -> bool:
        for key, label, action in self.options():
            if ev.key == key:
                self.act(action)
                return True
        if ev.key == "escape" and (self.game.sentence is None or self.game.sentence.get("finished")):
            self.act("close")
        return True

    def render(self, canvas: Canvas) -> None:
        game = self.game
        s = game.sentence
        width = min(84, canvas.width - 4)
        iw = width - 4
        lines = []
        if self.header:
            lines += markup.wrap(f"<title>{markup.escape(self.header)}</>", iw) + [[]]
        for note in (s["notes"] if s else [])[-8:]:
            lines += markup.wrap(note, iw) + [[]]
        opts = self.options()
        height = min(canvas.height - 2, len(lines) + len(opts) + 5)
        x, y, w, h = modal_box(canvas, width, height, "Justice", fg=colors.named("danger"))
        row = y + 2
        room = h - len(opts) - 4
        for line in lines[-room:] if room > 0 else []:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        row = y + h - len(opts) - 2
        for key, label, action in opts:
            canvas.button(x + 2, row, label[: iw - 6], lambda a=action: self.act(a),
                          hotkey="Enter" if key == "enter" else key.upper())
            row += 1
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("enter", "enter", "e", "a", "escape")]
