"""Character creation: people, calling, background, abilities, skills, identity, starting place, begin.

Every step starts with a sensible choice already made, so pressing Enter through all of them
gives a playable character. Tab / Shift+Tab (or clicking a step) moves between steps.
"""

from __future__ import annotations

from realmwalker.ai.service import AIResult, Priority, Ticket
from realmwalker.ai.tasks import BACKSTORY, backstory_variables
from realmwalker.core.textgen import a_or_an
from realmwalker.game.describe import cap, settlement_line
from realmwalker.game.state import new_game
from realmwalker.rules.character import ABILITIES, modifier, signed
from realmwalker.rules.creation import SEXES, CharacterBuilder, make_ties, starting_places
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas, TextField

STEPS = ["People", "Calling", "Background", "Abilities", "Skills & training", "Who you are", "Where you start", "Begin"]
LEFT_W = 26
SPINNER = "|/-\\"


class CreationScreen(Screen):
    title = "Create your character"
    animating = True

    def __init__(self, app, world) -> None:
        super().__init__(app)
        self.world = world
        self.t = app.tables
        self.tables = app.tables  # describe helpers look for .tables
        self.b = CharacterBuilder(self.t, app.ui_rng.child("creation"))
        self.step = 0
        self.cursor = [0] * len(STEPS)  # selected row within each step
        self.name_field = TextField(self.b.name, max_len=32)
        self.places: list[int] = []
        self._places_for: tuple | None = None
        self.ticket: Ticket | None = None
        self.frame = 0
        self._refresh_places()

    # ------------------------------------------------------------------ helpers
    @property
    def captures_text(self) -> bool:  # type: ignore[override]
        return self.step == 5 and self.cursor[5] == 0

    def _lists(self) -> list[str]:
        if self.step == 0:
            return list(self.t.races)
        if self.step == 1:
            return list(self.t.classes)
        if self.step == 2:
            return list(self.t.backgrounds)
        return []

    def _refresh_places(self) -> None:
        key = (self.b.background, self.b.race)
        if self._places_for != key:
            self.places = starting_places(self.world, self.t, self.b.background, self.b.race,
                                          self.app.ui_rng.child(f"places{key}"))
            self._places_for = key
            self.cursor[6] = 0
        if self.places:
            self.b.start_settlement = self.places[min(self.cursor[6], len(self.places) - 1)]

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
        if self.step in (0, 1, 2):
            return len(self._lists())
        if self.step == 3:
            return 6
        if self.step == 4:
            return len(self._training_rows())
        if self.step == 5:
            return 5
        if self.step == 6:
            return max(1, len(self.places))
        return 1

    # ------------------------------------------------------------------ actions
    def go(self, step: int) -> None:
        self.step = max(0, min(len(STEPS) - 1, step))
        if self.step == 6:
            self._refresh_places()
        self.cursor[self.step] = min(self.cursor[self.step], max(0, self._row_count() - 1))

    def choose(self) -> None:
        """Enter on the current row."""
        row = self.cursor[self.step]
        if self.step in (0, 1, 2):
            key = self._lists()[row]
            [self.b.set_race, self.b.set_class, self.b.set_background][self.step](key)
            self.name_field.value = self.b.name
            self.go(self.step + 1)
        elif self.step == 6:
            self._refresh_places()
            self.go(7)
        elif self.step == 7:
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
        if self.step == 0:
            race = self.t.races[self.b.race]
            cultures = race["cultures"]
            if self._lists()[row] == self.b.race and len(cultures) > 1:
                i = (cultures.index(self.b.culture) + delta) % len(cultures)
                self.b.set_culture(cultures[i])
                self.name_field.value = self.b.name
        elif self.step == 3:
            ab = ABILITIES[row]
            if not self.b.change(ab, delta):
                self.app.notify("Scores run from 8 to 15, and you have 27 points to spend.", "warn")
        elif self.step == 4:
            kind, _ = self._training_rows()[row]
            cls = self.t.classes[self.b.cls]
            if kind == "style":
                styles = list(cls["fighting_styles"])
                self.b.fighting_style = styles[(styles.index(self.b.fighting_style) + delta) % len(styles)]
                self.b.style_chosen = True
            elif kind == "subclass":
                subs = list(cls["subclasses"])
                self.b.subclass = subs[(subs.index(self.b.subclass) + delta) % len(subs)]
            elif kind == "kit":
                self.b.set_kit((self.b.kit + delta) % len(cls["kits"]))
        elif self.step == 5:
            if row == 1:
                self.b.sex = SEXES[(SEXES.index(self.b.sex) + 1) % 2]
                self.b.name = self.b.random_name()
                self.name_field.value = self.b.name
            elif row == 2:
                age = self.t.races[self.b.race]["age"]
                self.b.age = max(age["adult"], min(age["old"], self.b.age + delta))
            elif row == 3:
                self.b.appearance = self.b.random_appearance()
            elif row == 4:
                self.write_backstory(ai=delta > 0)

    def reroll_name(self) -> None:
        self.b.name = self.b.random_name()
        self.name_field.value = self.b.name

    def write_backstory(self, ai: bool = True) -> None:
        self._refresh_places()
        tie = make_ties(self.world, self.t, self.b.build(self.world.time), self.b.start_settlement or 0,
                        self.app.ui_rng.child("tiepreview"))[0]["text"] if self.world.settlements else ""
        self._pending_tie = tie
        if ai and self.app.ai.usable():
            if self.ticket is not None:
                return
            variables = backstory_variables(self.b, self.t, self.home_name(), tie)
            self.ticket = self.app.ai.submit(BACKSTORY, variables, priority=Priority.URGENT, callback=self._backstory_done)
            self._ticket_started = self.app.clock()
        else:
            if ai:
                self.app.notify("The AI is not available; using built-in text.", "warn")
            self.b.apply_backstory(self.b.fallback_backstory(self.home_name()), "built-in")

    def _backstory_done(self, result: AIResult) -> None:
        self.ticket = None
        if result.ok and result.data:
            self.b.apply_backstory(result.data, "ai")
            self.app.notify("The AI wrote your backstory.", "good")
        else:
            self.b.apply_backstory(self.b.fallback_backstory(self.home_name()), "built-in")
            self.app.notify(f"AI backstory failed ({result.error}); used built-in text.", "warn")

    def begin(self) -> None:
        self.b.name = self.name_field.value.strip() or self.b.random_name()
        problems = self.b.problems()
        if problems:
            self.app.notify(problems[0], "warn", 5)
            return
        if self.ticket is not None:
            self.ticket.cancel()
            self.ticket = None
        if not self.b.backstory:
            self.b.apply_backstory(self.b.fallback_backstory(self.home_name()), "built-in")
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
        elif ev.key == " " and self.step == 4:
            kind, value = self._training_rows()[self.cursor[4]]
            if kind in ("skill", "expertise"):
                self._toggle(kind, value)
        elif ev.key in ("s", "S") and self.step == 3:
            self.b.scores = dict(self.t.classes[self.b.cls]["suggested"])
        elif ev.key in ("r", "R") and self.step == 5:
            self.b.randomize_identity()
            self.name_field.value = self.b.name
        elif ev.key in ("w", "W") and self.step == 5:
            self.write_backstory(ai=True)
        else:
            return False
        return True

    def _after_move(self) -> None:
        # Moving through the lists previews the choice straight away.
        row = self.cursor[self.step]
        if self.step == 0:
            self.b.set_race(self._lists()[row])
            self.name_field.value = self.b.name
        elif self.step == 1:
            self.b.set_class(self._lists()[row])
        elif self.step == 2:
            self.b.set_background(self._lists()[row])
        elif self.step == 6:
            self._refresh_places()

    def update(self) -> None:
        self.frame += 1

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
        [self._r_race, self._r_class, self._r_background, self._r_abilities, self._r_training, self._r_identity,
         self._r_start, self._r_begin][self.step](canvas, x, body_y, width, body_h)
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
        bonus = ", ".join(f"{self.t.rules['abilities'][a]['short']} {signed(v)}" for a, v in r["ability_bonus"].items())
        traits = "\n".join(f"<loot>{t['name']}</>: {t['text']}" for t in r["traits"])
        culture = self.t.names["cultures"].get(self.b.culture, {}).get("label", self.b.culture)
        cult = f"<title>Culture:</> ◄ {culture} ►" if len(r["cultures"]) > 1 else f"<title>Culture:</> {culture}"
        text = (f"<name>{r['name']}</>\n{r['description']}\n\n{cult}\n<dim>Abilities:</> {bonus}\n"
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
        text = (f"<name>{bg['name']}</>\n{bg['description']}\n\n<dim>Skills:</> {skills}\n<dim>Tools:</> {tools}\n"
                f"<dim>Gear:</> {items}\n<dim>Money:</> <loot>{money_text(bg['money'])}</>\n\n"
                f"<loot>{bg['feature']['name']}</>: {bg['feature']['text']}\n\n<dim>Ties:</> {tie}.")
        self._detail(canvas, x + 22, y, w - 22, h, text)

    def _r_abilities(self, canvas, x, y, w, h) -> None:
        b = self.b
        race_bonus = self.t.races[b.race]["ability_bonus"]
        canvas.markup(x, y, f"Points left: <{'good' if b.points_left() == 0 else 'warn'}>{b.points_left()}</> of "
                            f"{b.point_buy['budget']}   <dim>(S: suggested for a {self.t.classes[b.cls]['name']})</>")
        canvas.text(x, y + 2, "Ability          Score  Race  Final  Mod", colors.DIM)
        final = b.final_scores()
        primary = self.t.classes[b.cls]["primary"]
        for i, a in enumerate(ABILITIES):
            row = y + 3 + i
            selected = i == self.cursor[3]
            over = canvas.hit(x, row, 44, 1, action=lambda i=i: self.cursor.__setitem__(3, i),
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
        help_text = ("Scores start at 8 and cost more the higher they go (15 costs 9 points). * marks what a "
                     f"{self.t.classes[b.cls]['name']} most relies on. Your people add their bonuses on top.\n\n"
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
            selected = i == self.cursor[4]
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
                st = cls["fighting_styles"][b.fighting_style]
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
        self.cursor[4] = i
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
            ("Looks", markup.escape(b.appearance) + " <dim>(← → new)</>"),
            ("Backstory", "<dim>→ ask the AI to write it · ← built-in text · or press W</>"),
        ]
        for i, (label, value) in enumerate(rows):
            selected = i == self.cursor[5]
            ry = y + i * 2
            canvas.hit(x, ry, w, 1, action=lambda i=i: self.cursor.__setitem__(5, i))
            canvas.text(x, ry, ("► " if selected else "  ") + label, colors.TITLE if selected else colors.FG)
            if label == "Name":
                self.name_field.render(canvas, x + 12, ry, 34, selected)
                canvas.text(x + 48, ry, "(R: new random character)", colors.FAINT)
            else:
                canvas.markup(x + 12, ry, value, max_width=w - 12)
        ty = y + 11
        if self.ticket is not None:
            spin = SPINNER[self.frame // 3 % 4]
            canvas.markup(x, ty, f"<ai>{spin} The AI is writing your backstory…</>")
            return
        if b.backstory:
            source = "<ai>written by the AI</>" if b.backstory_source == "ai" else "<dim>built-in text</>"
            used = canvas.wrapped(x, ty, f"{markup.escape(b.backstory)}  ({source})", min(w, 90), max_lines=6)
            extras = [("Personality", b.personality), ("Ideal", b.ideal), ("Bond", b.bond), ("Flaw", b.flaw)]
            for j, (label, value) in enumerate(extras):
                canvas.markup(x, ty + used + 1 + j, f"<dim>{label}:</> {markup.escape(value)}", max_width=w)
        else:
            canvas.wrapped(x, ty, "<dim>No backstory yet. One will be written from built-in text when you begin, "
                                  "unless you ask the AI (a little Player2 energy).</>", min(w, 90))

    def _r_start(self, canvas, x, y, w, h) -> None:
        self._refresh_places()
        bg = self.t.backgrounds[self.b.background]
        canvas.wrapped(x, y, f"Places that suit {a_or_an(bg['name'].lower())}:", w)
        for i, sid in enumerate(self.places):
            s = self.world.settlements[sid]
            selected = i == self.cursor[6]
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
            f"<dim>Hit points:</> {b.max_hp()} · <dim>Money:</> {money_text(t.backgrounds[b.background]['money'])}",
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
        if self.step == 5:
            keys += [KeyEvent("w"), KeyEvent("r")]
        return keys

