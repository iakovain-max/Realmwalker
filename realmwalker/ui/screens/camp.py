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
            ("t", "Pitch the tent", lambda: camplogic.pitch_tent(g), tent and not (c and c.tent),
             "no tent" if not tent else "already up"),
            ("e", "Eat a meal", self._eat, True, ""),
            ("c", "Cook raw food", lambda: camplogic.cook(g), fire, "needs a fire"),
            ("b", "Boil water", lambda: camplogic.boil_water(g), fire and pot, "needs a fire and a pot"),
            ("w", "Fill waterskins", lambda: fill_skins(g), water is not None, "no water here"),
            ("g", "Forage (1 hour)", lambda: camplogic.forage(g), wild, "not in a town"),
            ("u", "Hunt (2 hours)", lambda: camplogic.hunt(g), wild, "not in a town"),
            ("i", "Fish (2 hours)", lambda: camplogic.fish(g), water is not None and water[0] != "clean",
             "no river, lake or marsh here"),
            ("h", "See to wounds", self._health, True, ""),
            ("s", "Short rest (1 hour)", lambda: self._rest("short"), True, ""),
            ("l", "Sleep (8 hours)", lambda: self._rest("long"), True, ""),
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

    def _health(self) -> list[str]:
        from realmwalker.ui.screens.health import HealthScreen

        self.app.push(HealthScreen(self.app, self.game))
        return []

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
        food = sum(it.qty for c in g.party for it in c.inventory if g.tables.items.get(it.def_id).get("food"))
        water = sum(it.fill for c in g.party for it in c.inventory)
        canvas.markup(x, y, f"<dim>Food in the packs:</> {food} · <dim>water:</> {water:g} pints", max_width=col)
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
