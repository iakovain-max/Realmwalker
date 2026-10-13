"""Character creation in the 2024 order: calling, background, people, the choices they leave (lineage, feats,
spells, the background's increases, the calling's style and kit, languages, equipment), abilities, every skill and
tool pick on one checklist, identity, looks, starting place, begin.

Every step starts with a sensible choice already made, so pressing Enter through all of them
gives a playable character. Tab / Shift+Tab (or clicking a step) moves between steps.
"""

from __future__ import annotations

from realmwalker.core.textgen import a_or_an
from realmwalker.game.describe import cap, settlement_line
from realmwalker.game.state import new_game
from realmwalker.rules import looks
from realmwalker.rules.character import ABILITIES, modifier, signed
from realmwalker.rules.creation import SEXES, CharacterBuilder, make_ties, starting_places
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas, TextField

STEPS = ["Calling", "Background", "People", "Choices", "Abilities", "Skills & tools", "Who you are", "Looks",
         "Where you start", "Begin"]
CALLING, BACKGROUND, PEOPLE, ORIGIN, ABILITIES_STEP, TRAINING, IDENTITY, LOOKS, START, BEGIN = range(10)
LISTS = (CALLING, BACKGROUND, PEOPLE)
METHODS = {"point_buy": "Point buy (27 points)", "array": "Standard array (15 14 13 12 10 8)",
           "roll": "Roll 4d6, keep three (R: roll again)"}
COLOUR_SLOTS = ("skin", "eyes", "hair_colour", "beard_colour", "paint_colour", "dye", "cloak")
LEFT_W = 26


class CreationScreen(Screen):
    title = "Create your character"
    animating = True

    def __init__(self, app, world) -> None:
        super().__init__(app)
        self.world = world
        self.t = app.tables
        self.tables = app.tables  # describe helpers look for .tables
        self.b = CharacterBuilder(self.t, app.ui_rng.child("creation"), world=world)
        self.step = 0
        self.cursor = [0] * len(STEPS)  # selected row within each step
        self.name_field = TextField(self.b.name, max_len=32)
        self.places: list[int] = []
        self._places_for: tuple | None = None
        self._refresh_places()

    # ------------------------------------------------------------------ helpers
    @property
    def captures_text(self) -> bool:  # type: ignore[override]
        return self.step == IDENTITY and self.cursor[IDENTITY] == 0

    def _lists(self) -> list[str]:
        if self.step == PEOPLE:
            return list(self.t.races)
        if self.step == CALLING:
            return list(self.t.classes)
        if self.step == BACKGROUND:
            return list(self.t.backgrounds)
        return []

    def _refresh_places(self) -> None:
        key = (self.b.background, self.b.race, self.b.culture)
        if self._places_for != key:
            self.places = starting_places(self.world, self.t, self.b.background, self.b.race,
                                          self.app.ui_rng.child(f"places{key}"), culture=self.b.culture)
            self._places_for = key
            self.cursor[START] = 0
        if self.places:
            self.b.start_settlement = self.places[min(self.cursor[START], len(self.places) - 1)]

    def home_name(self) -> str:
        if self.b.start_settlement is not None:
            return self.world.settlements[self.b.start_settlement].name
        return "a small place nobody has heard of"

    def _row_count(self) -> int:
        if self.step in LISTS:
            return len(self._lists())
        if self.step == ORIGIN:
            return max(1, len(self._choice_rows()))
        if self.step == ABILITIES_STEP:
            return 7
        if self.step == TRAINING:
            return max(1, len(self._skill_rows()))
        if self.step == IDENTITY:
            return 4
        if self.step == LOOKS:
            return len(self._look_rows())
        if self.step == START:
            return max(1, len(self.places))
        return 1

    def _look_rows(self) -> list[tuple[str, str, list[str]]]:
        """Rows on the Looks step: (slot, label, options). Only what this people and sex can change is shown."""
        b = self.b
        opts = looks.options(self.t, b.race, b.sex)
        rows = [(slot, label, opts[slot]) for slot, label in (
            ("build", "Build"), ("skin", "Skin"), ("eyes", "Eyes"), ("hair", "Hair"), ("hair_colour", "Hair colour"),
            ("beard", "Beard")) if len(opts[slot]) > 1]
        if b.looks.get("beard", "none") != "none":
            rows.append(("beard_colour", "Beard colour", opts["beard_colour"]))
        for feat, pool in opts["features"].items():
            if len(pool) > 1:
                rows.append((f"feature:{feat}", looks.feature_name(self.t, feat), pool))
        rows.append(("mark", "Mark or scar", opts["mark"]))
        rows.append(("paint", "Paint or tattoo", opts["paint"]))
        if b.looks.get("paint", "none") != "none":
            rows.append(("paint_colour", "Paint colour", opts["paint_colour"]))
        dyes = [""] + list(looks.data(self.t)["dyes"])
        rows.append(("dye", "Clothes colour", dyes))
        rows.append(("cloak", "Cloak colour", dyes))
        return rows

    def _look_value(self, slot: str) -> str:
        if slot.startswith("feature:"):
            return (self.b.looks.get("features") or {}).get(slot[8:], "")
        return self.b.looks.get(slot, "")

    def change_look(self, row: int, delta: int) -> None:
        rows = self._look_rows()
        if not rows:
            return
        slot, _, pool = rows[max(0, min(row, len(rows) - 1))]
        current = self._look_value(slot)
        i = pool.index(current) if current in pool else -1
        self.b.set_look(slot, pool[(i + delta) % len(pool)])
        self.cursor[LOOKS] = min(self.cursor[LOOKS], len(self._look_rows()) - 1)

    # ------------------------------------------------------------------ actions
    def go(self, step: int) -> None:
        self.step = max(0, min(len(STEPS) - 1, step))
        if self.step == START:
            self._refresh_places()
        self.cursor[self.step] = min(self.cursor[self.step], max(0, self._row_count() - 1))

    def choose(self) -> None:
        """Enter on the current row."""
        row = self.cursor[self.step]
        if self.step in LISTS:
            key = self._lists()[row]
            {PEOPLE: self.b.set_race, CALLING: self.b.set_class, BACKGROUND: self.b.set_background}[self.step](key)
            self.name_field.value = self.b.name
            self.go(self.step + 1)
        elif self.step == START:
            self._refresh_places()
            self.go(BEGIN)
        elif self.step == BEGIN:
            self.begin()
        else:
            self.go(self.step + 1)

    def adjust(self, delta: int) -> None:
        """Left/right on the current row."""
        row = self.cursor[self.step]
        if self.step == PEOPLE:
            race = self.t.races[self.b.race]
            cultures = race["cultures"]
            if self._lists()[row] == self.b.race and len(cultures) > 1:
                i = (cultures.index(self.b.culture) + delta) % len(cultures)
                self.b.set_culture(cultures[i])
                self.name_field.value = self.b.name
        elif self.step == ORIGIN:
            self.cycle_choice(row, delta)
        elif self.step == ABILITIES_STEP:
            if row == 0:
                methods = list(METHODS)
                self.b.set_method(methods[(methods.index(self.b.score_method) + delta) % len(methods)])
                return
            ab = ABILITIES[row - 1]
            if self.b.score_method != "point_buy":
                other = ABILITIES[(row - 1 + delta) % len(ABILITIES)]
                self.b.swap_scores(ab, other)  # (array and rolled scores are moved about, not bought)
                self.cursor[ABILITIES_STEP] = ABILITIES.index(other) + 1
            elif not self.b.change(ab, delta):
                self.app.notify("Scores run from 8 to 15, and you have 27 points to spend.", "warn")
        elif self.step == TRAINING:
            self.cursor[TRAINING] = self._skill_column_jump(row, delta)
        elif self.step == IDENTITY:
            if row == 1:
                self.b.sex = SEXES[(SEXES.index(self.b.sex) + 1) % 2]
                self.b.name = self.b.random_name()
                self.name_field.value = self.b.name
                self.b.fit_looks()  # a beard may go, a likely hair style come
            elif row == 2:
                age = self.t.races[self.b.race]["age"]
                self.b.age = max(age["adult"], min(age["old"], self.b.age + delta))
            elif row == 3:
                self.write_backstory()
        elif self.step == LOOKS:
            self.change_look(row, delta)

    def reroll_name(self) -> None:
        self.b.name = self.b.random_name()
        self.name_field.value = self.b.name

    def write_backstory(self) -> None:
        """A new backstory from the built-in words (each press writes another)."""
        self._refresh_places()
        self.b.apply_backstory(self.b.fallback_backstory(self.home_name()))

    def begin(self) -> None:
        self.b.name = self.name_field.value.strip() or self.b.random_name()
        problems = self.b.problems()
        if problems:
            self.app.notify(problems[0], "warn", 5)
            return
        if not self.b.backstory:
            self.b.apply_backstory(self.b.fallback_backstory(self.home_name()))
        self._refresh_places()
        start = self.b.start_settlement
        # A world that has been lived in before does not wait: weeks or months pass before the new life begins.
        from realmwalker.game import interlude

        summary = None
        if interlude.should_pass(self.world):
            summary = interlude.pass_the_years(self.world, self.t)
        char = self.b.build(self.world.time)
        if start is not None:
            char.ties = make_ties(self.world, self.t, char, start, self.world.rng.child(f"ties/{char.name}"))
        game = new_game(self.world, self.t, char, start)
        for tie in char.ties:
            game.say(f"<dim>{markup.escape(tie['text'])}</>", "flavor")
        self.app.start_game(game)
        if summary is not None:
            from realmwalker.ui.screens.interlude import InterludeScreen

            self.app.push(InterludeScreen(self.app, game, summary))

    def leave(self) -> None:
        def go_back() -> None:
            from realmwalker.ui.screens.title import TitleScreen

            self.app.replace(TitleScreen(self.app))

        self.app.push(ConfirmBox(self.app, "Stop creating this character? The world is kept; you can use "
                                           "<loot>New Character</> on the title screen later.", go_back))

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "tab":
            self.go(self.step + (-1 if ev.shift else 1))
            return True
        if ev.key == "escape":
            if self.step == 0:
                self.leave()
            else:
                self.go(self.step - 1)
            return True
        if self.captures_text and ev.key not in ("up", "down", "enter"):
            if self.name_field.handle_key(ev):
                self.b.name = self.name_field.value
                return True
        rows = self._row_count()
        if ev.key == "up":
            self.cursor[self.step] = (self.cursor[self.step] - 1) % rows
            self._after_move()
        elif ev.key == "down":
            self.cursor[self.step] = (self.cursor[self.step] + 1) % rows
            self._after_move()
        elif ev.key in ("left", "right"):
            self.adjust(-1 if ev.key == "left" else 1)
        elif ev.key == "enter":
            self.choose()
        elif ev.key == " " and self.step == TRAINING:
            self.tick(self.cursor[TRAINING])
        elif ev.key in ("e", "E") and self.step == TRAINING and self.b.needs_expertise():
            self.tick_expertise(self.cursor[TRAINING])
        elif ev.key in ("s", "S") and self.step == ABILITIES_STEP:
            self.b.set_method(self.b.score_method if self.b.score_method != "roll" else "array")
            if self.b.score_method == "point_buy":
                self.b.scores = dict(self.t.classes[self.b.cls]["suggested"])
        elif ev.key in ("r", "R") and self.step == ABILITIES_STEP and self.b.score_method == "roll":
            self.b.reroll()
        elif ev.key in ("r", "R") and self.step == IDENTITY:
            self.b.randomize_identity()
            self.name_field.value = self.b.name
        elif ev.key in ("r", "R") and self.step == LOOKS:
            self.b.randomize_looks()
        elif ev.key in ("w", "W") and self.step == IDENTITY:
            self.write_backstory()
        else:
            return False
        return True

    def _after_move(self) -> None:
        # Moving through the lists previews the choice straight away.
        row = self.cursor[self.step]
        if self.step == PEOPLE:
            self.b.set_race(self._lists()[row])
            self.name_field.value = self.b.name
        elif self.step == CALLING:
            self.b.set_class(self._lists()[row])
        elif self.step == BACKGROUND:
            self.b.set_background(self._lists()[row])
        elif self.step == START:
            self._refresh_places()

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, self.title, double=True)
        self._render_steps(canvas, 2, 2, LEFT_W - 2, h - 4)
        canvas.text(LEFT_W, 1, "│", colors.BORDER)
        for y in range(2, h - 2):
            canvas.text(LEFT_W, y, "│", colors.FAINT)
        x, width = LEFT_W + 2, w - LEFT_W - 4
        canvas.text(x, 2, f"{self.step + 1}. {STEPS[self.step]}", colors.TITLE)
        body_y, body_h = 4, h - 8
        if self.step in LISTS and width >= 110:
            # The character, large, on the right while choosing a people, a calling and a past.
            show_w = min(40, width // 3)
            width -= show_w + 2
            self._showcase(canvas, x + width + 2, body_y, show_w, body_h)
        [self._r_class, self._r_background, self._r_race, self._r_origin, self._r_abilities, self._r_training,
         self._r_identity, self._r_looks, self._r_start, self._r_begin][self.step](canvas, x, body_y, width, body_h)
        hint = "↑↓ choose · ←→ change · Enter: accept & next · Tab/Shift+Tab: steps · Esc: back"
        canvas.text(x, h - 3, hint, colors.FAINT, max_width=width)

    def _render_steps(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        for i, name in enumerate(STEPS):
            selected = i == self.step
            over = canvas.hit(x, y + i, w, 1, action=lambda i=i: self.go(i))
            fg = colors.SELECT_FG if selected else (colors.FG if over else colors.DIM)
            canvas.text(x, y + i, ("► " if selected else "  ") + f"{i + 1} {name}", fg, colors.HILITE_BG if selected else None,
                        max_width=w)
        sy = y + len(STEPS) + 2
        b = self.b
        if self.step == LOOKS:
            # On the Looks step this panel shows the face, as large as it will go, and who it belongs to.
            preview = self._preview_character()
            room = (y + h) - sy - 4
            cw, ch = canvas.cell_w, canvas.cell_h
            k = min(10, int((w * cw - 8) // 16), int((room * ch - 8) // 16)) if preview is not None else 0
            if k >= 2:
                from realmwalker.ui.gfx import dolls, scenes

                side = 16 * k + 8
                rows = -(-side // ch)
                canvas.clear_cells(x, sy, w, rows)
                parts = dolls.character(preview, self.t, atlas=canvas.gfx.atlas, bare_head=True)
                scenes.bust(canvas, parts, (int(x * cw), int(sy * ch), side, side), side=16)
                sy += rows + 1
            race = self.t.races[b.race]["name"]
            cls = self.t.classes[b.cls]["name"]
            for i, line in enumerate((f"<name>{markup.escape(self.name_field.value or '?')}</>", f"{race} {cls}")):
                if sy + i < y + h:
                    canvas.markup(x, sy + i, line, max_width=w)
            return
        if h - (sy - y) > 20:
            preview = self._preview_character()
            if preview is not None:
                from realmwalker.ui.gfx import scenes

                rows = 6
                canvas.clear_cells(x, sy, w, rows)
                scenes.figure(canvas, preview, self.t, tuple(int(v) for v in canvas.cell_rect(x, sy, min(w, 14), rows)))
                sy += rows + 1
        race = self.t.races[b.race]["name"]
        cls = self.t.classes[b.cls]["name"]
        lines = [
            f"<name>{markup.escape(self.name_field.value or '?')}</>",
            f"{race} {cls}",
            f"<dim>{self.t.backgrounds[b.background]['name']}</>",
            "",
            f"HP <good>{b.max_hp()}</>",
        ]
        final = b.final_scores()
        for a in ABILITIES:
            lines.append(f"<dim>{self.t.rules['abilities'][a]['short']}</> {final[a]:>2} <dim>({signed(modifier(final[a]))})</>")
        for i, line in enumerate(lines):
            if sy + i < y + h:
                canvas.markup(x, sy + i, line, max_width=w)

    def _preview_character(self):
        """The character as they would be now (dressed in the chosen kit), for the figure; kept until a choice changes."""
        b = self.b
        key = (b.race, b.sex, b.cls, b.kit, b.background, b.appearance, b.subclass, repr(sorted(b.looks.items())),
               b.take_gold, b.lineage)
        if getattr(self, "_preview_key", None) != key:
            self._preview_key = key
            try:
                saved_name = b.name
                b.name = b.name or "?"
                self._preview = b.build()
                b.name = saved_name
            except Exception:
                self._preview = None
        return self._preview

    def _list(self, canvas: Canvas, x: int, y: int, keys: list[str], names: list[str], width: int) -> None:
        row = self.cursor[self.step]
        for i, (key, name) in enumerate(zip(keys, names)):
            selected = i == row
            over = canvas.hit(x, y + i, width, 1, action=lambda i=i: self._click_row(i))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            canvas.text(x, y + i, ("► " if selected else "  ") + name, colors.SELECT_FG if selected else colors.FG, bg,
                        max_width=width)

    def _click_row(self, i: int) -> None:
        if self.cursor[self.step] == i:
            self.choose()
        else:
            self.cursor[self.step] = i
            self._after_move()

    def _detail(self, canvas: Canvas, x: int, y: int, w: int, h: int, text: str) -> None:
        canvas.wrapped(x, y, text, w, max_lines=h)

    def _r_race(self, canvas, x, y, w, h) -> None:
        keys = list(self.t.races)
        self._list(canvas, x, y, keys, [self.t.races[k]["name"] for k in keys], 18)
        r = self.t.races[self.b.race]
        traits = "\n".join(f"<loot>{t['name']}</>: {t['text']}" for t in r["traits"])
        lineages = r.get("lineages") or {}
        if lineages:
            traits += "\n\n" + "\n".join(f"<title>{v['name']}</>: {v['text']}" for v in lineages.values())
        culture = self.b.culture_label()
        like = self.t.cultures.get(self.b.culture)["like"]
        cult = (f"<title>Culture:</> ◄ {culture} ►" if len(r["cultures"]) > 1 else f"<title>Culture:</> {culture}") + \
            f" <dim>(like the {like})</>"
        text = (f"<name>{r['name']}</>\n{r['description']}\n\n{cult}\n"
                f"<dim>Speed:</> {r['speed']} ft · <dim>Size:</> {r['size']}"
                + (f" · <dim>Darkvision:</> {r['darkvision']} ft" if r["darkvision"] else "") + f"\n\n{traits}")
        self._detail(canvas, x + 22, y, w - 22, h, text)

    def _r_class(self, canvas, x, y, w, h) -> None:
        keys = list(self.t.classes)
        self._list(canvas, x, y, keys, [self.t.classes[k]["name"] for k in keys], 18)
        c = self.t.classes[self.b.cls]
        abil = self.t.rules["abilities"]
        feats = "\n".join(f"<loot>{f['name']}</> <dim>(level {f['level']})</>: {f['text']}" for f in c["features"] if f["level"] <= 5)
        text = (f"<name>{c['name']}</>\n{c['description']}\n\n"
                f"<dim>Hit die:</> d{c['hit_die']} · <dim>Saves:</> {', '.join(abil[a]['name'] for a in c['saves'])}\n"
                f"<dim>Armour:</> {', '.join(c['armor']) or 'none'} · "
                f"<dim>Weapons:</> {self.t.items.proficiency_words(c['weapons'])}\n"
                f"<dim>Skills:</> choose {c['skill_count']}\n\n{feats}")
        self._detail(canvas, x + 22, y, w - 22, h, text)

    def _r_background(self, canvas, x, y, w, h) -> None:
        keys = list(self.t.backgrounds)
        self._list(canvas, x, y, keys, [self.t.backgrounds[k]["name"] for k in keys], 18)
        bg = self.t.backgrounds[self.b.background]
        skills = ", ".join(self.t.rules["skills"][s]["name"] for s in bg["skills"])
        tools = ", ".join(self.t.rules["tools"][t] for t in bg["tools"]) or "none"
        items = ", ".join(self.t.items.get(i)["name"] + (f" ×{q}" if q > 1 else "") for i, q in bg["items"])
        tie = {"lord_served": "the lord you served", "temple": "the temple that raised you",
               "criminal": "a fence who knows you, and a bounty on your head", "home_village": "a village that loves you",
               "noble_house": "a real noble house", "scholar": "an old master and a library",
               "clan": "a clan of the wild country", "guild": "a guild and its master"}.get(bg["tie"]["kind"], "")
        from realmwalker.rules import feats

        abil = ", ".join(self.t.rules["abilities"][a]["name"] for a in bg["abilities"])
        feat = feats.defs(self.t)[bg["feat"]["id"]]
        feat_name = feats.name(self.t, {"id": bg["feat"]["id"], "choices": bg["feat"].get("choices") or {}})
        text = (f"<name>{bg['name']}</>\n{bg['description']}\n\n<dim>Raises:</> {abil} <dim>(+2 and +1, or +1 each)</>\n"
                f"<dim>Feat:</> <loot>{feat_name}</>: {feat['text']}\n"
                f"<dim>Skills:</> {skills}\n<dim>Tools:</> {tools}\n"
                f"<dim>Gear:</> {items}, <loot>{money_text(bg['money'])}</> <dim>(or {money_text(bg['gold'])} instead)</>\n\n"
                f"<loot>{bg['feature']['name']}</>: {bg['feature']['text']}\n\n<dim>Ties:</> {tie}.")
        self._detail(canvas, x + 22, y, w - 22, h, text)

    def _r_abilities(self, canvas, x, y, w, h) -> None:
        b = self.b
        race_bonus = b.bonus()
        msel = self.cursor[ABILITIES_STEP] == 0
        canvas.hit(x, y, 60, 1, action=lambda: self.adjust(1) if self.cursor[ABILITIES_STEP] == 0 else
                   self.cursor.__setitem__(ABILITIES_STEP, 0))
        canvas.markup(x, y, ("►" if msel else " ") + f"<title>Method:</> ◄ {METHODS[b.score_method]} ►", max_width=w,
                      bg=colors.HILITE_BG if msel else None)
        if b.score_method == "point_buy":
            canvas.markup(x, y + 1, f" Points left: <{'good' if b.points_left() == 0 else 'warn'}>{b.points_left()}</> of "
                                    f"{b.point_buy['budget']}   <dim>(S: suggested for a {self.t.classes[b.cls]['name']})</>",
                          max_width=w)
        else:
            canvas.markup(x, y + 1, " <dim>←→ on a score swaps it with its neighbour.</>", max_width=w)
        canvas.text(x, y + 2, "Ability          Score  Bkgd  Final  Mod", colors.DIM)
        final = b.final_scores()
        primary = self.t.classes[b.cls]["primary"]
        for i, a in enumerate(ABILITIES):
            row = y + 3 + i
            selected = i + 1 == self.cursor[ABILITIES_STEP]
            over = canvas.hit(x, row, 44, 1, action=lambda i=i: self.cursor.__setitem__(ABILITIES_STEP, i + 1),
                              right_action=lambda a=a: b.change(a, -1))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, row, 44, 1, bg)
            name = self.t.rules["abilities"][a]["name"] + (" *" if a in primary else "")
            bonus = int(race_bonus.get(a, 0))
            canvas.text(x, row, ("►" if selected else " ") + name, colors.SELECT_FG if selected else colors.FG, bg)
            canvas.text(x + 17, row, f"◄{b.scores[a]:>2}►" if selected else f" {b.scores[a]:>2} ", colors.TITLE, bg)
            canvas.text(x + 24, row, f"{signed(bonus) if bonus else '':>3}", colors.named("good"), bg)
            canvas.text(x + 30, row, f"{final[a]:>2}", colors.FG, bg)
            canvas.text(x + 36, row, signed(modifier(final[a])), colors.DIM, bg)
        help_text = ("Point buy: scores start at 8 and cost more the higher they go (15 costs 9 points). * marks what a "
                     f"{self.t.classes[b.cls]['name']} most relies on. Your background adds its increases on top "
                     "(chosen in the Choices step).\n\n"
                     f"Hit points at first level: <good>{b.max_hp()}</>.")
        canvas.wrapped(x, y + 11, help_text, min(w, 70), max_lines=h - 11)

    # ------------------------------------------------------------------ step 4: the choices, each with its list
    def _choice_rows(self) -> list[dict]:
        """Rows of the Choices step, under their headings: {group, label, value, options [(key, name, words)],
        taken {key: why it cannot be had here}, set(key)}. Skill and tool picks are on the Skills & tools step."""
        from realmwalker.rules import feats

        b, t = self.b, self.t
        abil = t.rules["abilities"]
        rows: list[dict] = []

        def row(group, label, value, options, put, taken=None):
            rows.append({"group": group, "label": label, "value": value, "options": options, "set": put,
                         "taken": taken or {}})

        def feat_words(fid):
            d = feats.defs(t)[fid]
            picks = [c["kind"] for c in d.get("choices", {}).values()]
            more = " <dim>(Its picks are made in step 6, Skills & tools.)</>" if any(
                k in b.SKILL_KINDS for k in picks) else ""
            return d["text"] + more

        def spell_words(sid):
            sp = t.spells[sid] if sid in t.spells else None
            if not sp:
                return ""
            level = "Cantrip" if sp["level"] == 0 else f"Level {sp['level']} spell"
            return f"<dim>{level}, {sp.get('school', '')}.</> {sp.get('text', '')}"

        def feat_rows(group, source, fid):
            slots = [x for x in b.feat_slots() if x[0] == source]
            spec = feats.defs(t)[fid].get("choices", {})
            for _, _, key, index, opts in slots:
                kind = spec[key]["kind"]
                if kind in b.SKILL_KINDS:
                    continue
                have = b.feat_choices.get(source, {}).get(key)
                if index >= 0:
                    have = list(have or [])
                    value = have[index] if index < len(have) else ""
                    taken = {v: f"{kind} {j + 1}" for j, v in enumerate(have) if j != index and v}
                    label = f"{'Cantrip' if kind == 'cantrip' else 'Spell'} {index + 1}"
                    if kind == "spell" and int(spec[key].get("count", 1)) == 1:
                        label = "Level 1 spell"
                else:
                    value, taken = have, {}
                    label = {"spell_list": "Spell list", "ability": "Casting ability"}.get(kind, key.title())
                if kind in ("cantrip", "spell"):
                    options = [(o, t.spells[o]["name"], spell_words(o)) for o in opts]
                elif kind == "ability":
                    options = [(o, abil[o]["name"], "The ability its spells are cast with.") for o in opts]
                else:
                    options = [(o, feats.choice_word(t, o), "Whose spells you learn: the cleric's, the druid's or "
                                                           "the wizard's.") for o in opts]
                row(group, label, value, options,
                    lambda v, source=source, key=key, index=index: b.set_feat_slot(source, key, index, v), taken)

        # your people
        race = t.races[b.race]
        people = f"Your people: {race['name']}"
        for key, spec in b.species_choices().items():
            if spec.get("kind") == "lineage":
                lins = race.get("lineages") or {}
                row(people, "Lineage", b.lineage, [(k, v["name"], v["text"]) for k, v in lins.items()],
                    lambda v: b.set_choice("lineage", v))
            elif spec.get("kind") == "origin_feat":
                row(people, "Versatile: a feat", b.versatile,
                    [(f, feats.defs(t)[f]["name"], feat_words(f)) for f in b.choice_options("versatile")],
                    lambda v: b.set_choice("versatile", v))
                feat_rows(people, "versatile", b.versatile)
        # your background
        bg = t.backgrounds[b.background]
        past = f"Your background: {bg['name']}"
        bg_feat = bg["feat"]["id"]
        row(past, "Its feat", bg_feat, [(bg_feat, feats.name(t, {"id": bg_feat, "choices": bg["feat"].get("choices") or {}}),
                                         feat_words(bg_feat))], lambda v: None)
        feat_rows(past, "background", bg_feat)
        names = [abil[a]["name"] for a in b.bg_abilities()]
        row(past, "Ability increases", b.bonus_mode,
            [("2/1", "+2 to one, +1 to another", f"Of {', '.join(names)}: one rises by 2 and another by 1."),
             ("1/1/1", "+1 to each of three", f"{', '.join(names)} each rise by 1.")], lambda v: b.set_bonus(v))
        if b.bonus_mode == "2/1":
            final = b.final_scores()
            for i, plus in ((0, 2), (1, 1)):
                other = b.bonus_pick[1 - i] if len(b.bonus_pick) > 1 else ""

                def put(v, i=i):
                    pick = list(b.bonus_pick)
                    pick[i] = v
                    b.set_bonus("2/1", pick)

                row(past, f"+{plus} to", b.bonus_pick[i] if len(b.bonus_pick) > i else "",
                    [(a, abil[a]["name"], f"{abil[a]['name']} rises by {plus}: now {final[a]} "
                                          f"({signed(modifier(final[a]))}).") for a in b.bg_abilities()],
                    put, {other: f"+{3 - plus}"} if other else {})
        items = ", ".join(t.items.get(i)["name"] + (f" ×{q}" if q > 1 else "") for i, q in bg["items"])
        row(past, "Its gear", "gold" if b.take_gold else "gear",
            [("gear", "the background's gear", f"{items}, and {money_text(bg['money'])}."),
             ("gold", f"{money_text(bg['gold'])} instead", "Set out with coin and buy your own.")],
            lambda v: setattr(b, "take_gold", v == "gold"))
        # your calling
        cls = t.classes[b.cls]
        calling = f"Your calling: {cls['name']}"
        if "fighting_style" in cls["choices_at_1"]:
            def style(v):
                b.fighting_style = v
                b.style_chosen = True

            row(calling, "Fighting style", b.fighting_style,
                [(k, t.feats["feats"][k]["name"], t.feats["feats"][k]["text"]) for k in b.styles()], style)
        if "subclass" in cls["choices_at_1"]:
            row(calling, "Divine domain" if b.cls == "cleric" else "Path", b.subclass,
                [(k, v["name"], v["text"]) for k, v in cls["subclasses"].items()],
                lambda v: setattr(b, "subclass", v))
        kits = []
        for i, kit in enumerate(cls["kits"]):
            things = ", ".join(t.items.get(d)["name"] + (f" ×{q}" if q > 1 else "") for d, q in kit["items"])
            kits.append((i, kit["name"], things + "."))
        row(calling, "Kit", b.kit, kits, lambda v: b.set_kit(int(v)))
        # languages
        lists = t.rules["language_lists"]
        liked = set(lists["by_species"].get(b.race, []) + lists["by_culture"].get(b.culture, []))
        for i in range(2):
            other = b.languages[1 - i] if len(b.languages) > 1 - i else ""
            row("Languages (everyone speaks Common)", f"Language {i + 1}", b.languages[i] if i < len(b.languages) else "",
                [(x, x, "Often spoken by your people." if x in liked else "") for x in b.language_options()],
                lambda v, i=i: b.set_language(i, v), {other: f"language {2 - i}"} if other else {})
        return rows

    def cycle_choice(self, i: int, delta: int) -> None:
        """←→ on a row: the next option that is free (one already taken by the row beside it is passed over)."""
        rows = self._choice_rows()
        if not rows:
            return
        r = rows[max(0, min(i, len(rows) - 1))]
        keys = [k for k, _, _ in r["options"] if k not in r["taken"] or k == r["value"]]
        if len(keys) < 2:
            return
        at = keys.index(r["value"]) if r["value"] in keys else -1
        r["set"](keys[(at + delta) % len(keys)])
        self.cursor[ORIGIN] = min(self.cursor[ORIGIN], len(self._choice_rows()) - 1)

    def set_choice_value(self, i: int, key) -> None:
        rows = self._choice_rows()
        r = rows[max(0, min(i, len(rows) - 1))]
        if key in r["taken"] and key != r["value"]:
            self.app.notify(f"Already chosen as {r['taken'][key]}.", "warn")
            return
        r["set"](key)
        self.cursor[ORIGIN] = min(i, len(self._choice_rows()) - 1)

    def _r_origin(self, canvas, x, y, w, h) -> None:
        """The choices on the left under their headings; on the right, every option of the selected one, the chosen
        one marked, with what it does."""
        rows = self._choice_rows()
        sel = min(self.cursor[ORIGIN], len(rows) - 1)
        wide = w >= 84
        lw = min(54, w // 2 + 4) if wide else w
        label_w = 22
        # where each row goes (headings between groups); scrolled so the selected row shows
        lines: list[tuple[str, int]] = []  # ("head", row index of its first) or ("row", index)
        group = None
        for i, r in enumerate(rows):
            if r["group"] != group:
                group = r["group"]
                lines.append(("head", i))
            lines.append(("row", i))
        room = h - (1 if wide else 6)
        at = next(j for j, ln in enumerate(lines) if ln == ("row", sel))
        top = max(0, min(at - room // 2, len(lines) - room)) if len(lines) > room else 0
        for j, (kind, i) in enumerate(lines[top:top + room]):
            ry = y + j
            r = rows[i]
            if kind == "head":
                canvas.text(x, ry, r["group"], colors.TITLE, max_width=lw)
                continue
            selected = i == sel
            over = canvas.hit(x, ry, lw, 1, action=lambda i=i: self.cursor.__setitem__(ORIGIN, i),
                              right_action=lambda i=i: self.cycle_choice(i, -1),
                              wheel=lambda d, i=i: self.cycle_choice(i, d))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, ry, lw, 1, bg)
            canvas.text(x, ry, ("► " if selected else "  ") + r["label"], colors.SELECT_FG if selected else colors.FG,
                        bg, max_width=label_w)
            name = next((n for k, n, _ in r["options"] if k == r["value"]), "—")
            many = len(r["options"]) > 1
            canvas.markup(x + label_w, ry, (f"◄ {name} ►" if many and selected else name), fg=colors.FG, bg=bg,
                          max_width=lw - label_w)
        r = rows[sel]
        words = next((d for k, _, d in r["options"] if k == r["value"]), "")
        if not wide:
            canvas.wrapped(x, y + room + 1, words or "", w, max_lines=h - room - 2)
            return
        # the options of the selected choice
        px, pw = x + lw + 3, w - lw - 3
        for yy in range(y, y + h):
            canvas.text(px - 2, yy, "│", colors.FAINT)
        opts = r["options"]
        canvas.markup(px, y, f"<title>{markup.escape(r['label'])}</>" +
                      (f" <dim>— {len(opts)} to choose from</>" if len(opts) > 1 else ""), max_width=pw)
        about_lines = markup.wrap(words, pw)[:8] if words else []
        list_room = max(3, h - 3 - len(about_lines))
        cur = next((j for j, (k, _, _) in enumerate(opts) if k == r["value"]), 0)
        top = max(0, min(cur - list_room // 2, len(opts) - list_room)) if len(opts) > list_room else 0
        for j, (k, name, d) in enumerate(opts[top:top + list_room]):
            ry = y + 2 + j
            chosen = k == r["value"]
            taken = r["taken"].get(k) if not chosen else None
            over = canvas.hit(px, ry, pw, 1, action=lambda i=sel, k=k: self.set_choice_value(i, k),
                              tooltip=d or None)
            bg = colors.HILITE_BG if chosen else (colors.HOVER_BG if over and not taken else None)
            if bg:
                canvas.fill(px, ry, pw, 1, bg)
            if taken:
                canvas.text(px, ry, f"  {name}  (chosen as {taken})", colors.FAINT, bg, max_width=pw)
            else:
                canvas.text(px, ry, ("● " if chosen else "  ") + name, colors.SELECT_FG if chosen else colors.FG, bg,
                            max_width=pw)
        if top > 0:
            canvas.text(px + pw - 2, y + 2, "▲", colors.DIM)
        if top + list_room < len(opts):
            canvas.text(px + pw - 2, y + 1 + list_room, "▼", colors.DIM)
        canvas.wrapped(px, y + 3 + min(list_room, len(opts)), words, pw, max_lines=8)

    # ------------------------------------------------------------------ step 6: every skill and tool on one checklist
    def _skill_rows(self) -> list[str]:
        """Every skill, then the tools any pick may take (or that come with the origin)."""
        b = self.b
        skills = list(self.t.rules["skills"])
        pools = b.skill_pools()
        tools = [x for p in pools for x in p["allowed"] if x not in self.t.rules["skills"]]
        tools += [x for x in b.known_tools() if x not in tools]
        return skills + list(dict.fromkeys(tools))

    def _skill_column_jump(self, row: int, delta: int) -> int:
        """←→ hop between the skills and the tools."""
        n_skills = len(self.t.rules["skills"])
        rows = self._skill_rows()
        if len(rows) == n_skills:
            return row
        if row < n_skills and delta > 0:
            return min(len(rows) - 1, n_skills + row)
        if row >= n_skills and delta < 0:
            return min(n_skills - 1, row - n_skills)
        return row

    def tick(self, i: int) -> None:
        rows = self._skill_rows()
        x = rows[max(0, min(i, len(rows) - 1))]
        self.cursor[TRAINING] = rows.index(x)
        b = self.b
        mine = any(x in p["picked"] for p in b.skill_pools())
        why = b.unpick(x) if mine or x in b.granted() else b.pick(x)
        if why:
            self.app.notify(why, "warn", 5)

    def tick_expertise(self, i: int) -> None:
        rows = self._skill_rows()
        x = rows[max(0, min(i, len(rows) - 1))]
        b = self.b
        if x not in self.t.rules["skills"]:
            return
        if x not in b.known_skills():
            self.app.notify("Expertise doubles a skill you have: tick the skill first.", "warn")
        elif not b.toggle_expertise(x):
            self.app.notify(f"You can only choose {b.needs_expertise()} for Expertise. Take one off first.", "warn")

    def _skill_state(self, x: str) -> tuple[str, str, str]:
        """(box, where from (short), where from (in words)) for a skill or tool."""
        b = self.b
        for p in b.skill_pools():
            if x in p["picked"]:
                return "x", p["name"], f"Chosen for <title>{markup.escape(p['name'])}</> ({p['from']})."
        where = b.granted().get(x)
        if where:
            return "■", where.split(" (")[0].replace("your ", ""), f"You have it from {where}."
        if x in b.known_skills() or x in b.known_tools():
            return "■", "", "You have it already."
        return " ", "", ""

    def _skill_words(self, x: str) -> str:
        b, t = self.b, self.t
        _, _, have = self._skill_state(x)
        takes = [p["name"] for p in b.skill_pools() if x in p["allowed"]]
        if not have:
            have = (f"Can be chosen for: {', '.join(takes)}." if takes else
                    "<dim>None of your picks can take it (other callings and feats can).</>")
        if x in t.rules["skills"]:
            sk = t.rules["skills"][x]
            ab = t.rules["abilities"][sk["ability"]]["name"]
            return f"<name>{sk['name']}</> <dim>({ab})</>: {sk.get('text', '')}\n{have}"
        name = t.rules["tools"].get(x, x)
        about = ""
        try:
            it = t.items.get(x)
        except (KeyError, TypeError):
            it = None
        if it:
            use = it.get("utilize") or {}
            uses = "; ".join(f"{u['text']} (DC {u['dc']})" for u in use.get("uses", []))
            about = it.get("how") or (f"Used to: {uses}." if uses else "")
            if use.get("crafts"):
                about += f" Makes: {', '.join(str(c).replace('_', ' ') for c in use['crafts'][:6])}."
        return f"<name>{cap(name)}</>: {about}\n{have}"

    def _r_training(self, canvas, x, y, w, h) -> None:
        """Every skill and tool as a tick box: what you have and from where, how good you are at it, and the picks
        still to make."""
        b, t = self.b, self.t
        pools = b.skill_pools()
        parts = []
        for p in pools:
            n, k = len(p["picked"]), p["count"]
            what = {"skill": "", "tool": " tools", "skill_or_tool": " skills or tools"}[p["kind"]]
            parts.append(f"<{'good' if n >= k else 'warn'}>{markup.escape(p['name'])} {n}/{k}</>{'' if n >= k else what}")
        if b.needs_expertise():
            n = len(b.expertise)
            parts.append(f"<{'good' if n >= b.needs_expertise() else 'warn'}>Expertise ♦ {n}/{b.needs_expertise()}</>")
        head = "<dim>Picks:</> " + " · ".join(parts)
        used = canvas.wrapped(x, y, head, w, max_lines=3)
        rows = self._skill_rows()
        n_skills = len(t.rules["skills"])
        sel = min(self.cursor[TRAINING], len(rows) - 1)
        words_h = 4
        top_y = y + used + 1
        room = h - used - 1 - words_h - 1
        two = len(rows) > n_skills and w >= 100
        final = b.final_scores()
        prof = t.rules["proficiency_bonus"][0]

        def draw(i, rx, ry, cw):
            x_ = rows[i]
            box, src, _ = self._skill_state(x_)
            choosable = box != " " or any(x_ in p["allowed"] for p in pools)
            selected = i == sel
            over = canvas.hit(rx, ry, cw, 1, action=lambda i=i: self.tick(i),
                              right_action=(lambda i=i: self.tick_expertise(i)) if b.needs_expertise() else None)
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(rx, ry, cw, 1, bg)
            fg = colors.SELECT_FG if selected else (colors.FG if choosable else colors.FAINT)
            exp = "♦" if x_ in b.expertise else " "
            if x_ in t.rules["skills"]:
                sk = t.rules["skills"][x_]
                bonus = modifier(final[sk["ability"]]) + (prof if box != " " else 0) * (2 if x_ in b.expertise else 1)
                canvas.text(rx, ry, f"{'►' if selected else ' '}[{box}]{exp}{sk['name']}", fg, bg, max_width=21)
                canvas.text(rx + 21, ry, t.rules["abilities"][sk["ability"]]["short"], colors.DIM, bg)
                canvas.text(rx + 25, ry, f"{signed(bonus):>3}", colors.named("good") if box != " " else colors.DIM, bg)
                canvas.text(rx + 30, ry, src, colors.DIM, bg, max_width=max(0, cw - 30))
            else:
                canvas.text(rx, ry, f"{'►' if selected else ' '}[{box}] {cap(t.rules['tools'].get(x_, x_))}", fg, bg,
                            max_width=min(cw, 30))
                if cw > 32:
                    canvas.text(rx + 31, ry, src, colors.DIM, bg, max_width=cw - 31)

        def column(idx, cx, cw, title):
            canvas.text(cx, top_y, title, colors.TITLE, max_width=cw)
            r = room - 1
            at = idx.index(sel) if sel in idx else 0
            top = max(0, min(at - r // 2, len(idx) - r)) if len(idx) > r else 0
            for j, i in enumerate(idx[top:top + r]):
                draw(i, cx, top_y + 1 + j, cw)
            if top > 0:
                canvas.text(cx + cw - 1, top_y + 1, "▲", colors.DIM)
            if top + r < len(idx):
                canvas.text(cx + cw - 1, top_y + r, "▼", colors.DIM)

        if two:
            cw = min(48, (w - 3) // 2 + 4)
            column(list(range(n_skills)), x, cw, "Skills")
            column(list(range(n_skills, len(rows))), x + cw + 3, w - cw - 3, "Tools")
        else:
            column(list(range(len(rows))), x, w, "Skills" + (" and tools" if len(rows) > n_skills else ""))
        hint = ("Space or click: tick or untick" + (" · E or right-click: Expertise ♦" if b.needs_expertise() else "")
                + " · ■ comes with your origin")
        canvas.wrapped(x, y + h - words_h - 1, self._skill_words(rows[sel]), w, max_lines=words_h - 1)
        canvas.text(x, y + h - 1, hint, colors.FAINT, max_width=w)

    def _r_identity(self, canvas, x, y, w, h) -> None:
        b = self.b
        age = self.t.races[b.race]["age"]
        rows = [
            ("Name", None),
            ("Sex", f"◄ {b.sex} ►"),
            ("Age", f"◄ {b.age} ► <dim>(adult at {age['adult']}, old at {age['old']})</>"),
            ("Backstory", "<dim>◄ ► write one (again for another) · or press W</>"),
        ]
        for i, (label, value) in enumerate(rows):
            selected = i == self.cursor[IDENTITY]
            ry = y + i * 2
            canvas.hit(x, ry, w, 1, action=lambda i=i: self.cursor.__setitem__(IDENTITY, i))
            canvas.text(x, ry, ("► " if selected else "  ") + label, colors.TITLE if selected else colors.FG)
            if label == "Name":
                self.name_field.render(canvas, x + 12, ry, 34, selected)
                hint = "(R: new random character)" if canvas.width - (x + 48) > 27 else "(R: random)"
                canvas.text(x + 48, ry, hint, colors.FAINT, max_width=canvas.width - (x + 48) - 2)
            else:
                canvas.markup(x + 12, ry, value, max_width=w - 12)
        canvas.markup(x, y + 8, f"<dim>Looks:</> {markup.escape(b.appearance)} <dim>(the next step changes them)</>",
                      max_width=w)
        ty = y + 10
        if b.backstory:
            used = canvas.wrapped(x, ty, markup.escape(b.backstory), min(w, 90), max_lines=6)
            extras = [("Personality", b.personality), ("Ideal", b.ideal), ("Bond", b.bond), ("Flaw", b.flaw)]
            for j, (label, value) in enumerate(extras):
                canvas.markup(x, ty + used + 1 + j, f"<dim>{label}:</> {markup.escape(value)}", max_width=w)
        else:
            canvas.wrapped(x, ty, "<dim>No backstory yet. One will be written when you begin, or press W to write "
                                  "one now.</>", min(w, 90))

    def _r_looks(self, canvas, x, y, w, h) -> None:
        """Every look as a row (◄ choice ►, a swatch for colours), and the character large beside them: the head and
        shoulders bare, and the whole figure in the gear they set out with."""
        b = self.b
        rows = self._look_rows()
        label_w, value_w = 18, 24
        list_w = label_w + value_w + 5
        sel = min(self.cursor[LOOKS], len(rows) - 1)
        for i, (slot, label, pool) in enumerate(rows):
            ry = y + i
            if ry >= y + h - 4:
                break
            selected = i == sel
            over = canvas.hit(x, ry, list_w, 1, action=lambda i=i: self.cursor.__setitem__(LOOKS, i),
                              right_action=lambda i=i: self.change_look(i, -1),
                              wheel=lambda d, i=i: self.change_look(i, d))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, ry, list_w, 1, bg)
            canvas.text(x, ry, ("► " if selected else "  ") + label, colors.SELECT_FG if selected else colors.FG, bg,
                        max_width=label_w)
            value = self._look_value(slot)
            name = looks.name_of(self.t, slot, value)
            vx = x + label_w
            canvas.hit(vx, ry, 2, 1, action=lambda i=i: self.change_look(i, -1))
            canvas.text(vx, ry, "◄", colors.TITLE if selected else colors.DIM, bg)
            canvas.text(vx + 2, ry, name, colors.FG, bg, max_width=value_w - 6)
            canvas.hit(vx + value_w - 3, ry, 2, 1, action=lambda i=i: self.change_look(i, 1))
            canvas.text(vx + value_w - 3, ry, "►", colors.TITLE if selected else colors.DIM, bg)
            rgb = self._swatch(slot, value) if slot in COLOUR_SLOTS else None
            if rgb is not None:
                canvas.text(vx + value_w, ry, "██", rgb, bg)
        words = (f"<dim>How others see you:</> {markup.escape(b.appearance)}\n\n"
                 "<dim>↑↓ choose · ←→ or click ◄ ► to change · mouse wheel over a row · R: a new random look</>")
        used = len(rows) + 1 + canvas.wrapped(x, y + len(rows) + 1, words, min(list_w + 4, w),
                                               max_lines=max(2, h - len(rows) - 1))
        self._looks_pictures(canvas, x, y, w, h, list_w, used)

    def _looks_pictures(self, canvas, x, y, w, h, list_w, used) -> None:
        """The whole figure as they set out (the face, bare-headed, is in the panel on the left): beside the choices,
        or under them when the window is narrow, wherever it can be larger. Every pixel a whole number of screen
        pixels."""
        preview = self._preview_character()
        if preview is None:
            return
        from realmwalker.ui.gfx import scenes
        from realmwalker.ui.gfx.scene import Text

        cw, ch = canvas.cell_w, canvas.cell_h

        def scale(room_w: float, room_h: float) -> int:
            return min(12, int((room_h - 50) // 32), int((room_w - 50) // 32))

        beside = scale((w - list_w - 4) * cw, h * ch)
        below = scale(w * cw, (h - used - 1) * ch)
        k = max(beside, below)
        if k < 2:
            return
        if beside >= below:
            px, py, pw, ph = x + list_w + 4, y, w - list_w - 4, h
        else:
            px, py, pw, ph = x, y + used + 1, w, h - used - 1
        canvas.clear_cells(px, py, pw, ph)
        fig_side = 32 * k
        fx, fy = int(px * cw), int(py * ch) + 22
        scenes.figure(canvas, preview, self.t, (fx, fy, fig_side + 40, fig_side + 20), most=fig_side)
        canvas.over(Text(fx + (fig_side + 40) / 2, fy - 4, "As you set out", "heading_light", 15, (200, 180, 140, 255),
                         anchor="mb", shadow=False, outline=True))

    def _showcase(self, canvas, x: int, y: int, w: int, h: int) -> None:
        """The character as they stand now, as large as fits, with a word on what changes them."""
        preview = self._preview_character()
        if preview is None:
            return
        from realmwalker.ui.gfx import scenes
        from realmwalker.ui.gfx.scene import Text

        cw, ch = canvas.cell_w, canvas.cell_h
        k = min(10, int((w * cw - 40) // 32), int((h * ch - 60) // 32))
        if k < 2:
            return
        canvas.clear_cells(x, y, w, h)
        side = 32 * k
        fx, fy = int(x * cw + (w * cw - side - 40) / 2), int(y * ch) + 22
        scenes.figure(canvas, preview, self.t, (fx, fy, side + 40, side + 20), most=side)
        caption = {PEOPLE: self.t.races[self.b.race]["name"], CALLING: self.t.classes[self.b.cls]["name"],
                   BACKGROUND: self.t.backgrounds[self.b.background]["name"]}.get(self.step, "")
        canvas.over(Text(fx + (side + 40) / 2, fy - 4, caption, "heading_light", 15, (200, 180, 140, 255), anchor="mb",
                         shadow=False, outline=True))
        canvas.wrapped(x, y + (side + 50) // ch + 1, f"<dim>Looks are chosen in step {LOOKS + 1} (R there for a new face).</>",
                       w, max_lines=3)

    def _swatch(self, slot: str, value: str):
        """The colour of a choice, for the little square beside it."""
        if not value:
            return None
        f = self.t.sprites["figures"]
        if slot == "skin":
            from realmwalker.ui.gfx.dolls import skin_colour

            return skin_colour(self.t, self.b.race, value)
        table = {"eyes": "eye_colours", "hair_colour": "hair_colours", "beard_colour": "hair_colours",
                 "paint_colour": "paint_colours", "dye": "colours", "cloak": "colours"}[slot]
        rgb = f[table].get(value)
        return tuple(rgb) if rgb else None

    def _r_start(self, canvas, x, y, w, h) -> None:
        self._refresh_places()
        bg = self.t.backgrounds[self.b.background]
        canvas.wrapped(x, y, f"Places that suit {a_or_an(bg['name'].lower())}:", w)
        for i, sid in enumerate(self.places):
            s = self.world.settlements[sid]
            selected = i == self.cursor[START]
            ry = y + 2 + i * 3
            over = canvas.hit(x, ry, w, 2, action=lambda i=i: self._click_row(i))
            bgc = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bgc:
                canvas.fill(x, ry, w, 2, bgc)
            canvas.markup(x, ry, ("► " if selected else "  ") + settlement_line(self, s), bg=bgc, max_width=w)
            area = self.world.area_at(s.x, s.y)
            biome = self.t.biomes.defs[self.t.biomes.index.get(self.world.biome_id(s.x, s.y), 0)]["name"]
            where = f"{cap(biome)}" + (f", in <place>{area.name}</>" if area else "")
            canvas.markup(x + 4, ry + 1, f"<dim>{where}.</>", bg=bgc, max_width=w - 4)

    def _r_begin(self, canvas, x, y, w, h) -> None:
        b = self.b
        t = self.t
        problems = b.problems()
        home = self.home_name()
        lines = [
            f"<name>{markup.escape(self.name_field.value)}</>, {b.sex}, {b.age}: {t.races[b.race]['name']} "
            f"{t.classes[b.cls]['name']}, formerly {a_or_an(t.backgrounds[b.background]['name'].lower())}.",
            f"<dim>Starts in</> <place>{home}</>.",
            "",
            f"<dim>Skills:</> {', '.join(t.rules['skills'][s]['name'] + (' ♦' if s in b.expertise else '') for s in b.known_skills())}",
            f"<dim>Tools:</> {', '.join(t.rules['tools'].get(x, x) for x in b.known_tools()) or 'none'}",
            f"<dim>Hit points:</> {b.max_hp()} · <dim>Money:</> "
            f"{money_text(t.backgrounds[b.background]['gold' if b.take_gold else 'money'])}",
            "",
        ]
        if problems:
            lines += [f"<danger>•</> {p}" for p in problems]
        else:
            lines.append("<good>Ready.</> Press <loot>Enter</> to begin. The world does not wait, and death is permanent.")
        canvas.wrapped(x, y, "\n".join(lines), min(w, 100), max_lines=h)
        canvas.button(x, y + h - 2, "Begin", self.begin, hotkey="Enter")

    def autoplay_keys(self) -> list[KeyEvent]:
        keys = [KeyEvent(k) for k in ("enter", "enter", "enter", "down", "up", "left", "right", "tab", " ")]
        if self.step == IDENTITY:
            keys += [KeyEvent("w"), KeyEvent("r")]
        if self.step == ABILITIES_STEP:
            keys += [KeyEvent("up"), KeyEvent("right"), KeyEvent("r")]
        if self.step == LOOKS:
            keys += [KeyEvent("r"), KeyEvent("right"), KeyEvent("down"), KeyEvent("right")]
        return keys

