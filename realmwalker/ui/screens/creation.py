"""Character creation in the 2024 order: calling, background, people, the origin's choices (lineage, feats,
languages, the background's increases, equipment), abilities, skills, identity, looks, starting place, begin.

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

STEPS = ["Calling", "Background", "People", "Origin", "Abilities", "Skills & training", "Who you are", "Looks",
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

    def _origin_rows(self) -> list[tuple]:
        """Rows on the Origin step: the lineage, the species' choices, the origin feats' picks, the background's
        increases, the two languages, and the equipment or the coin."""
        b = self.b
        rows: list[tuple] = []
        for key, spec in b.species_choices().items():
            rows.append(("choice", key))
        for slot in b.feat_slots():
            rows.append(("feat",) + slot[:4])
        rows.append(("bonus_mode",))
        if b.bonus_mode == "2/1":
            rows += [("bonus", 0), ("bonus", 1)]
        rows += [("language", 0), ("language", 1)]
        rows.append(("gear",))
        return rows

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

    def _training_rows(self) -> list[tuple[str, str]]:
        """Rows on the Skills & training step: (kind, value)."""
        rows = [("skill", s) for s in self.b.skill_options()]
        if self.b.needs_expertise():
            rows += [("expertise", s) for s in self.b.all_skills()]
        cls = self.t.classes[self.b.cls]
        if "fighting_style" in cls["choices_at_1"]:
            rows.append(("style", ""))
        if "subclass" in cls["choices_at_1"]:
            rows.append(("subclass", ""))
        rows.append(("kit", ""))
        return rows

    def _row_count(self) -> int:
        if self.step in LISTS:
            return len(self._lists())
        if self.step == ORIGIN:
            return len(self._origin_rows())
        if self.step == ABILITIES_STEP:
            return 7
        if self.step == TRAINING:
            return len(self._training_rows())
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

    def _toggle(self, kind: str, skill: str) -> None:
        ok = self.b.toggle_skill(skill) if kind == "skill" else self.b.toggle_expertise(skill)
        if not ok:
            limit = self.b.skill_count() if kind == "skill" else self.b.needs_expertise()
            self.app.notify(f"You can only choose {limit}. Untick one first.", "warn")

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
            self.adjust_origin(row, delta)
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
            kind, _ = self._training_rows()[row]
            cls = self.t.classes[self.b.cls]
            if kind == "style":
                styles = self.b.styles()
                self.b.fighting_style = styles[(styles.index(self.b.fighting_style) + delta) % len(styles)]
                self.b.style_chosen = True
            elif kind == "subclass":
                subs = list(cls["subclasses"])
                self.b.subclass = subs[(subs.index(self.b.subclass) + delta) % len(subs)]
            elif kind == "kit":
                self.b.set_kit((self.b.kit + delta) % len(cls["kits"]))
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

    def adjust_origin(self, row: int, delta: int) -> None:
        b = self.b
        rows = self._origin_rows()
        if not rows:
            return
        r = rows[max(0, min(row, len(rows) - 1))]

        def cycle(opts, current):
            if not opts:
                return current
            i = opts.index(current) if current in opts else -1
            return opts[(i + delta) % len(opts)]

        if r[0] == "choice":
            key = r[1]
            current = b.lineage if key == "lineage" else b.versatile if key == "versatile" else b.choices.get(key)
            b.set_choice(key, cycle(b.choice_options(key), current))
        elif r[0] == "feat":
            _, source, fid, key, index = r
            slot = next(x for x in b.feat_slots() if x[0] == source and x[2] == key and x[3] == index)
            have = b.feat_choices[source].get(key)
            current = have[index] if index >= 0 and isinstance(have, list) and index < len(have) else have
            b.set_feat_slot(source, key, index, cycle(slot[4], current))
        elif r[0] == "bonus_mode":
            b.set_bonus("1/1/1" if b.bonus_mode == "2/1" else "2/1")
        elif r[0] == "bonus":
            pick = list(b.bonus_pick)
            pick[r[1]] = cycle(b.bg_abilities(), pick[r[1]])
            if pick[0] == pick[1]:
                pick[1 - r[1]] = next(a for a in b.bg_abilities() if a != pick[r[1]])
            b.set_bonus("2/1", pick)
        elif r[0] == "language":
            opts = [x for x in b.language_options() if x not in b.languages or b.languages.index(x) == r[1]]
            b.set_language(r[1], cycle(opts, b.languages[r[1]] if r[1] < len(b.languages) else ""))
        elif r[0] == "gear":
            b.take_gold = not b.take_gold
        self.cursor[ORIGIN] = min(self.cursor[ORIGIN], len(self._origin_rows()) - 1)

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
            kind, value = self._training_rows()[self.cursor[TRAINING]]
            if kind in ("skill", "expertise"):
                self._toggle(kind, value)
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

    def _r_origin(self, canvas, x, y, w, h) -> None:
        """The origin's choices, one a row: ◄ value ►, with what the chosen one does."""
        from realmwalker.rules import feats

        b = self.b
        t = self.t
        rows = self._origin_rows()
        sel = min(self.cursor[ORIGIN], len(rows) - 1)
        label_w = 26
        detail = ""
        for i, r in enumerate(rows):
            ry = y + i
            if ry >= y + h - 4:
                break
            label, value, about = self._origin_row(r)
            selected = i == sel
            if selected:
                detail = about
            over = canvas.hit(x, ry, w, 1, action=lambda i=i: self._click_origin(i),
                              right_action=lambda i=i: self.adjust_origin(i, -1),
                              wheel=lambda d, i=i: self.adjust_origin(i, d))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, ry, w, 1, bg)
            canvas.text(x, ry, ("► " if selected else "  ") + label, colors.SELECT_FG if selected else colors.FG, bg,
                        max_width=label_w)
            canvas.markup(x + label_w, ry, f"◄ {value} ►", bg=bg, max_width=w - label_w)
        names = ", ".join(feats.name(t, {"id": fid, "choices": fixed}) for _, fid, fixed in b.origin_feats())
        info = (f"<dim>Your origin gives:</> <loot>{names}</>\n\n{detail}\n\n"
                "<dim>↑↓ choose · ←→ or click to change · Enter: next step</>")
        canvas.wrapped(x, y + len(rows) + 1, info, min(w, 90), max_lines=max(2, h - len(rows) - 1))

    def _click_origin(self, i: int) -> None:
        if self.cursor[ORIGIN] == i:
            self.adjust_origin(i, 1)
        self.cursor[ORIGIN] = i

    def _origin_row(self, r: tuple) -> tuple[str, str, str]:
        """(label, value, words on it) for a row of the Origin step."""
        from realmwalker.rules import feats

        b, t = self.b, self.t
        abil = t.rules["abilities"]
        if r[0] == "choice":
            key = r[1]
            if key == "lineage":
                lin = (t.races[b.race].get("lineages") or {}).get(b.lineage or "", {})
                return "Lineage", lin.get("name", "—"), lin.get("text", "")
            if key == "versatile":
                d = feats.defs(t)[b.versatile]
                return "Versatile: origin feat", d["name"], d["text"]
            v = b.choices.get(key, "")
            trait = next((x for x in t.races[b.race]["traits"] if x["id"] == key), {})
            return f"{trait.get('name', key)}: skill", t.rules["skills"].get(v, {}).get("name", v), trait.get("text", "")
        if r[0] == "feat":
            _, source, fid, key, index = r
            ch = b.feat_choices.get(source, {})
            v = ch.get(key)
            v = v[index] if index >= 0 and isinstance(v, list) and index < len(v) else v
            fname = feats.defs(t)[fid]["name"]
            kind = feats.defs(t)[fid]["choices"][key]["kind"]
            if kind in ("cantrip", "spell"):
                sp = t.spells[v] if v in t.spells else {}
                return f"{fname}: {'cantrip' if kind == 'cantrip' else 'spell'}", sp.get("name", "—"), sp.get("text", "")
            if kind == "spell_list":
                return f"{fname}: list", str(v).title(), "Whose spells: the cleric's, the druid's or the wizard's."
            if kind == "ability":
                return f"{fname}: casting with", abil.get(v, {}).get("name", str(v)), "The ability its spells are cast with."
            name = t.rules["skills"][v]["name"] if v in t.rules["skills"] else feats.tool_name(t, str(v))
            return f"{fname}: {'skill or tool' if kind == 'skill_or_tool' else 'tool' if kind == 'tool' else 'skill'}", \
                name, feats.defs(t)[fid]["text"]
        if r[0] == "bonus_mode":
            return "Background increases", "+2 and +1" if b.bonus_mode == "2/1" else "+1 to each of three", \
                "Your background raises " + ", ".join(abil[a]["name"] for a in b.bg_abilities()) + "."
        if r[0] == "bonus":
            a = b.bonus_pick[r[1]] if len(b.bonus_pick) > r[1] else ""
            return ("+2 to" if r[1] == 0 else "+1 to"), abil.get(a, {}).get("name", a), ""
        if r[0] == "language":
            v = b.languages[r[1]] if r[1] < len(b.languages) else "—"
            return f"Language {r[1] + 1}", v, "Everyone speaks Common, and two more tongues."
        bg = t.backgrounds[b.background]
        if b.take_gold:
            return "Equipment", f"{money_text(bg['gold'])} instead", "Set out with coin and buy your own."
        return "Equipment", "the background's gear", f"Its gear and {money_text(bg['money'])}."

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
                     "(chosen in the Origin step).\n\n"
                     f"Hit points at first level: <good>{b.max_hp()}</>.")
        canvas.wrapped(x, y + 11, help_text, min(w, 70), max_lines=h - 11)

    def _r_training(self, canvas, x, y, w, h) -> None:
        b = self.b
        rules = self.t.rules
        fixed = ", ".join(rules["skills"][s]["name"] for s in b.fixed_skills()) or "none"
        canvas.markup(x, y, f"<dim>Already known (people and background):</> {fixed}", max_width=w)
        canvas.markup(x, y + 1, f"Choose <title>{b.skill_count()}</> class skills (Space or click ticks; Enter moves on)"
                                + (f", then <title>{b.needs_expertise()}</> for Expertise" if b.needs_expertise() else "") + ":",
                      max_width=w)
        rows = self._training_rows()
        cls = self.t.classes[b.cls]
        ry = y + 3
        for i, (kind, value) in enumerate(rows):
            if kind == "expertise" and i == len(b.skill_options()):
                ry += 1  # a gap before the Expertise picks
            selected = i == self.cursor[TRAINING]
            over = canvas.hit(x, ry, w, 1, action=lambda i=i: self._click_training(i))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            mark = "► " if selected else "  "
            if kind == "skill":
                on = value in b.class_skills
                text = f"{mark}[{'x' if on else ' '}] {rules['skills'][value]['name']} <dim>({rules['skills'][value]['ability'].upper()})</>"
            elif kind == "expertise":
                on = value in b.expertise
                text = f"{mark}[{'♦' if on else ' '}] Expertise: {rules['skills'][value]['name']}"
            elif kind == "style":
                st = self.t.feats["feats"][b.fighting_style]
                text = f"{mark}<title>Fighting style:</> ◄ {st['name']} ► <dim>{st['text']}</>"
            elif kind == "subclass":
                sub = cls["subclasses"][b.subclass]
                text = f"{mark}<title>{'Divine domain' if b.cls == 'cleric' else 'Path'}:</> ◄ {sub['name']} ► <dim>{sub['text']}</>"
            else:
                kit = cls["kits"][b.kit]
                items = ", ".join(self.t.items.get(i)["name"] + (f" ×{q}" if q > 1 else "") for i, q in kit["items"])
                text = f"{mark}<title>Equipment:</> ◄ {kit['name']} ► <dim>{items}</>"
            if bg:
                canvas.fill(x, ry, w, 1, bg)
            canvas.markup(x, ry, text, bg=bg, max_width=w)
            ry += 1

    def _click_training(self, i: int) -> None:
        self.cursor[TRAINING] = i
        kind, value = self._training_rows()[i]
        if kind in ("skill", "expertise"):
            self._toggle(kind, value)
        else:
            self.adjust(1)

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
            f"<dim>Skills:</> {', '.join(t.rules['skills'][s]['name'] + (' ♦' if s in b.expertise else '') for s in b.all_skills())}",
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

