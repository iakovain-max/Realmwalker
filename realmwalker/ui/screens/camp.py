"""The camp: fire, tent, food, water, foraging, hunting, fishing, wounds and rest."""

from __future__ import annotations

from realmwalker.game import camp as camplogic
from realmwalker.game.fight import rest
from realmwalker.game.survival import fill_skins, water_here
from realmwalker.rules import body
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas


class CraftScreen(Screen):
    """What can be made here, out of what you are carrying."""

    modal = True
    title = "Make something"

    def __init__(self, app, game, camp_screen) -> None:
        super().__init__(app)
        self.game = game
        self.camp = camp_screen
        self.selected = 0

    def options(self) -> list:
        return camplogic.crafts(self.game)

    def choose(self, i: int) -> None:
        opts = self.options()
        if not 0 <= i < len(opts):
            return
        cid, label, ok, why = opts[i]
        if not ok:
            self.app.notify(f"{markup.plain(label)}: {why}.", "warn")
            return
        self.close()
        self.camp.run(lambda: camplogic.make(self.game, cid))

    def handle_key(self, ev: KeyEvent) -> bool:
        opts = self.options()
        if ev.key in ("escape", "m"):
            self.close()
        elif ev.key == "up":
            self.selected = max(0, self.selected - 1)
        elif ev.key == "down":
            self.selected = min(len(opts) - 1, self.selected + 1)
        elif ev.key == "enter":
            self.choose(self.selected)
        elif len(ev.key) == 1 and ev.key.isdigit() and ev.key != "0":
            self.choose(int(ev.key) - 1)
        return True

    def render(self, canvas: Canvas) -> None:
        from realmwalker.ui.screens.base import modal_box

        opts = self.options()
        self.selected = max(0, min(self.selected, max(0, len(opts) - 1)))
        x, y, w, h = modal_box(canvas, min(76, canvas.width - 4), len(opts) + 6, "Make something")
        for i, (cid, label, ok, why) in enumerate(opts):
            row = y + 2 + i
            if i == self.selected:
                canvas.fill(x + 1, row, w - 2, 1, colors.HILITE_BG)
            canvas.hit(x + 1, row, w - 2, 1, lambda i=i: self.choose(i))
            text = f"<loot>[{i + 1}]</> {label}" if ok else f"<faint>[{i + 1}] {markup.plain(label)}: {why}</>"
            canvas.markup(x + 2, row, text, max_width=w - 4)
        bx = canvas.button(x + 2, y + h - 2, "Back", self.close, hotkey="Esc")
        canvas.text(bx + 2, y + h - 2, "↑↓ choose · Enter or the number to make it", colors.FAINT,
                    max_width=max(0, x + w - bx - 4))

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "1", "enter", "escape")]


class CampScreen(Screen):
    title = "Camp"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.messages: list[str] = []

    # ------------------------------------------------------------------ actions
    def actions(self) -> list[tuple[str, str, object, bool, str]]:
        """(key, label, function, possible, why not)."""
        g = self.game
        c = camplogic.camp_here(g)
        fire = bool(c and c.fire)
        in_town = g.world.settlement_at(g.player.x, g.player.y) is not None
        pot = camplogic.has(g, camplogic.POTS)[1] is not None
        tent = camplogic.has(g, ("tent",))[1] is not None
        water = water_here(g)
        wild = not in_town
        return [
            ("f", "Put out the fire" if fire else "Light a fire", self._fire, True, ""),
            ("t", "Pitch the tent", lambda: camplogic.pitch_tent(g), not (c and c.tent), "already up") if tent else
            ("t", "Build a rough shelter (1 hour)", lambda: camplogic.build_shelter(g), wild and not (c and c.shelter),
             "already built" if wild else "there are roofs here"),
            ("e", "Eat a meal", self._eat, True, ""),
            ("c", "Cook raw food", lambda: camplogic.cook(g), fire, "needs a fire"),
            ("b", "Boil water", lambda: camplogic.boil_water(g), fire and pot, "needs a fire and a pot"),
            ("w", "Fill waterskins", lambda: fill_skins(g), water is not None, "no water here"),
            ("g", "Forage (1 hour)", lambda: camplogic.forage(g), wild, "not in a town"),
            ("u", "Hunt (2 hours)", lambda: camplogic.hunt(g), wild, "not in a town"),
            ("i", "Fish (2 hours)", lambda: camplogic.fish(g), water is not None and water[0] != "clean",
             "no river, lake or marsh here"),
            ("m", "Make something", self._make, True, ""),
            ("h", "See to wounds", self._health, True, ""),
            ("s", "Short rest (1 hour)", lambda: self._rest("short"), True, ""),
            ("l", self._sleep_label(), lambda: self._rest("night"), True, ""),
        ]

    def run(self, fn) -> None:
        g = self.game
        camplogic.make_camp(g)
        msgs = fn() or []
        for m in msgs:
            g.say(m, "info")
        self.messages = (self.messages + msgs)[-8:]
        self.app.save_game()
        if g.busy:
            self.close()  # something found us: the game screen takes over

    def _fire(self) -> list[str]:
        c = camplogic.camp_here(self.game)
        return camplogic.put_out_fire(self.game) if c and c.fire else camplogic.light_fire(self.game)

    def _eat(self) -> list[str]:
        out = []
        for c in self.game.party:
            if c.alive:
                out += camplogic.eat_meal(self.game, c)
        return out

    def _make(self) -> list[str]:
        """Torches, bandages, splints, salted meat, dried fish, a herbal remedy."""
        self.app.push(CraftScreen(self.app, self.game, self))
        return []

    def _health(self) -> list[str]:
        from realmwalker.ui.screens.health import HealthScreen

        self.app.push(HealthScreen(self.app, self.game))
        return []

    def _sleep_label(self) -> str:
        """By day a sleep is eight hours; begun after dark it lasts until first light, so nobody wakes at three in the
        morning and walks on into the cold."""
        g = self.game
        if g.light >= 0.5:
            return "Sleep (8 hours)"
        hours = max(8, min(14, round(g.minutes_to_dawn() / 60)))
        return f"Sleep until morning ({hours} hours)"

    def _rest(self, kind: str) -> list[str]:
        g = self.game
        g.say("You settle down to rest for an hour." if kind == "short" else "You bed down for the night.", "system")
        return rest(g, kind)

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "r"):
            self.close()
            return True
        for key, label, fn, ok, why in self.actions():
            if ev.key == key:
                if ok:
                    self.run(fn)
                else:
                    self.app.notify(f"{label}: {why}.", "warn")
                return True
        return True

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        g = self.game
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, "Camp", double=True)
        x, y = 2, 2
        col = min(56, w // 2 - 2) if w >= 100 else w - 4
        from realmwalker.world.weather import describe

        p = g.player
        place = g.world.settlement_at(p.x, p.y)
        where = place.name if place else g.biome_def(p.x, p.y)["name"].capitalize()
        m = g.moment
        canvas.markup(x, y, f"<place>{markup.escape(where)}</> <dim>· {m.time_text()} · {m.part_of_day(g.latitude)}</>",
                      max_width=col)
        y += 1
        y += canvas.wrapped(x, y, f"<info>{describe(g.weather)}</>", col, max_lines=2)
        for line in camplogic.camp_summary(g):
            y += canvas.wrapped(x, y, line, col, max_lines=2)
        y += 1
        from realmwalker.ui.screens.health import status_words

        for c in g.party:
            words = status_words(c, g.tables) or ["<good>well</>"]
            y += canvas.wrapped(x, y, f"<name>{markup.escape(c.name.split()[0])}</> {c.hp}/{c.max_hp} hp · "
                                      + " · ".join(words), col, max_lines=3)
        from realmwalker.rules.inventory import carried

        food = sum(it.qty for it in carried(g.party) if g.tables.items.get(it.def_id).get("food"))
        water = sum(it.fill for it in carried(g.party))
        canvas.markup(x, y, f"<dim>Food in the packs:</> {food} · <dim>water:</> {water:g} pint{'' if water == 1 else 's'}",
                      max_width=col)
        y += 2
        for key, label, fn, ok, why in self.actions():
            if y >= h - 3:
                break
            if ok:
                canvas.button(x, y, label, lambda fn=fn: self.run(fn), hotkey=key)
            else:
                canvas.markup(x, y, f"<faint>[{key}] {label}: {why}</>", max_width=col)
            y += 1
        # Right: what happened.
        if w >= 100:
            x2, y2, w2 = col + 5, 2, w - col - 8
            canvas.section(x2, y2, w2, "What happened")
            y2 += 1
            for msg in self.messages:
                if y2 >= h - 4:
                    break
                y2 += canvas.wrapped(x2, y2, msg, w2, max_lines=4)
            y2 += 1
            tips = ("<dim>A fire keeps you warm, dries you out, cooks and boils water, and keeps most beasts at a "
                    "distance, but people can see it from far away. Sleeping without food and water does not "
                    "restore you properly. Sleeping in the open in winter without a fire can kill.</>")
            if y2 < h - 6:
                canvas.wrapped(x2, y2, tips, w2, max_lines=h - 6 - y2)
        canvas.button(2, h - 3, "Leave the camp screen", self.close, hotkey="Esc")

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("f", "e", "c", "b", "w", "g", "u", "i", "s", "l", "t", "escape")]


# Old name, kept for anything that still refers to it.
RestScreen = CampScreen
