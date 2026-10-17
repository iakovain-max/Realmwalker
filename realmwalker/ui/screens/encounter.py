"""Meeting something hostile on the road: fight, ambush, slip away, or talk."""

from __future__ import annotations

from realmwalker.game.fight import (ATTITUDE_WORDS, encounter_bait, encounter_bait_food, encounter_evade,
                                    encounter_fight, encounter_pass, encounter_pay, encounter_pay_cost, encounter_talk,
                                    encounter_talk_dc)
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas


def group_summary(game, creatures) -> str:
    counts: dict[str, int] = {}
    for c in creatures:
        counts[c.def_id] = counts.get(c.def_id, 0) + 1
    parts = []
    for def_id, n in counts.items():
        d = game.tables.creatures[def_id]
        parts.append(f"{n} {d['plural'] if n > 1 else d['name']}")
    return ", ".join(parts)


class EncounterScreen(Screen):
    modal = True
    title = "Trouble"
    sound_open = "danger"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.enc = game.encounter

    def options(self) -> list[tuple[str, str, str, bool, str]]:
        """(key, label, action, enabled, why not)."""
        enc = self.enc
        stealth = min(self.game.sheet(c).skill_bonus("stealth") for c in self.game.party if c.alive)
        dc, why = encounter_talk_dc(self.game)
        out = [("l", "Let them be, and go on your way", "pass", True, "")] if enc.attitude != "hostile" else []
        mood = {"friendly": ", with the advantage of their goodwill", "hostile": ", at a disadvantage: they are hostile"}
        out += [
            ("f", "Fight", "fight", True, ""),
            ("a", "Ambush them (they are caught unawares)", "ambush", enc.spotted_first, "they have already seen you"),
            ("s", f"Slip away (Stealth {stealth:+d}" + (", with the advantage of seeing them first)" if enc.spotted_first
                                                         else ")"), "evade", True, ""),
            ("t", "Talk your way past (Persuasion" + (f", DC {dc}" if dc else "") + mood.get(enc.attitude, "") + ")",
             "talk", dc is not None, why),
        ]
        # A sure way out, at a price: the purse to robbers, food to hungry beasts. Shown only where it could work.
        cost, why = encounter_pay_cost(self.game)
        if cost is not None or why == "you have nothing to give them":
            out.append(("p", f"Hand over your purse ({money_text(cost)})" if cost else "Hand over your purse",
                        "pay", cost is not None, why))
        food, why = encounter_bait_food(self.game)
        if food is not None or why == "you have not enough food to throw them":
            out.append(("b", "Throw them food and back away", "bait", food is not None, why))
        from realmwalker.game import stonework

        waves = stonework.wave_casters(self.game)
        if waves:
            c, sid = waves[0]
            out.append(("w", f"{c.name.split()[0]} calls up a great wave ({self.game.tables.spells[sid]['name']}: "
                             "6d10, then the fight)", "wave", enc.spotted_first, "they have already seen you"))
        return out

    def act(self, action: str) -> None:
        game = self.game
        if game.encounter is None:
            self.close()
            return
        if action == "fight":
            encounter_fight(game, ambush=False)
        elif action == "ambush":
            encounter_fight(game, ambush=True)
        elif action == "evade":
            encounter_evade(game)
        elif action == "talk":
            encounter_talk(game)
        elif action == "pass":
            encounter_pass(game)
        elif action == "pay":
            encounter_pay(game)
        elif action == "bait":
            encounter_bait(game)
        elif action == "wave":
            from realmwalker.game import stonework

            for line in stonework.wave(game):
                game.say(line, "info")
            encounter_fight(game, ambush=False)  # (the drowned lie on the field: a fight already won is ended at once)
        self.close()  # the game screen opens the battle, if there is one

    def handle_key(self, ev: KeyEvent) -> bool:
        for key, _, action, enabled, why in self.options():
            if ev.key == key:
                if enabled:
                    self.act(action)
                else:
                    self.app.notify(why[:1].upper() + why[1:] + ".", "warn")
                return True
        if ev.key == "enter":
            self.act("fight")
        return True

    def render(self, canvas: Canvas) -> None:
        enc = self.enc
        width = min(72, canvas.width - 4)
        iw = width - 4
        intro = markup.wrap(markup.escape(enc.intro), iw)
        options = self.options()
        x, y, w, h = modal_box(canvas, width, len(intro) + 11 + len(options), "Trouble on the road",
                               fg=colors.named("danger"))
        row = y + 2
        for line in intro:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        row += 1
        canvas.markup(x + 2, row, f"<dim>You see:</> {markup.escape(group_summary(self.game, enc.creatures))}", max_width=iw)
        row += 1
        canvas.markup(x + 2, row, enc.threat, max_width=iw)
        row += 1
        canvas.markup(x + 2, row, ATTITUDE_WORDS.get(enc.attitude, ""), max_width=iw)
        row += 1
        seen = "<good>You saw them first.</>" if enc.spotted_first else "<warn>They have seen you.</>"
        canvas.markup(x + 2, row, seen, max_width=iw)
        row += 2
        for key, label, action, enabled, why in options:
            # A greyed-out choice says why, in place of its bracketed note: "Ambush them: they have already seen you".
            text = label if enabled else f"{label.split(' (')[0]}: {why}"
            canvas.button(x + 2, row, text, lambda a=action: self.act(a), hotkey=key.upper(), enabled=enabled,
                          max_width=iw)
            row += 1
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("l", "f", "a", "s", "t", "p", "b", "w", "enter")]
