"""Meeting something hostile on the road: fight, ambush, slip away, or talk."""

from __future__ import annotations

from realmwalker.game.fight import encounter_evade, encounter_fight, encounter_talk, encounter_talk_dc
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

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.enc = game.encounter

    def options(self) -> list[tuple[str, str, str, bool, str]]:
        """(key, label, action, enabled, why not)."""
        enc = self.enc
        stealth = min(self.game.sheet(c).skill_bonus("stealth") for c in self.game.party if c.alive)
        dc, why = encounter_talk_dc(self.game)
        return [
            ("f", "Fight", "fight", True, ""),
            ("a", "Ambush them (they are caught unawares)", "ambush", enc.spotted_first, "they have already seen you"),
            ("s", f"Slip away (Stealth {stealth:+d})", "evade", True, ""),
            ("t", "Talk your way past (Persuasion" + (f", DC {dc})" if dc else ")"), "talk", dc is not None, why),
        ]

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
        x, y, w, h = modal_box(canvas, width, len(intro) + 14, "Trouble on the road", fg=colors.named("danger"))
        row = y + 2
        for line in intro:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        row += 1
        canvas.markup(x + 2, row, f"<dim>You see:</> {markup.escape(group_summary(self.game, enc.creatures))}", max_width=iw)
        row += 1
        canvas.markup(x + 2, row, enc.threat, max_width=iw)
        row += 1
        seen = "<good>You saw them first.</>" if enc.spotted_first else "<warn>They have seen you.</>"
        canvas.markup(x + 2, row, seen, max_width=iw)
        row += 2
        for key, label, action, enabled, why in self.options():
            canvas.button(x + 2, row, label if enabled else f"{label}: {why}", lambda a=action: self.act(a),
                          hotkey=key.upper(), enabled=enabled)
            row += 1
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("f", "a", "s", "t", "enter")]
