"""The Health screen: needs, body heat, wetness, exhaustion, blood, pain, wounds and their treatment,
sickness and lasting injuries."""

from __future__ import annotations

from realmwalker.game import care
from realmwalker.rules import body, health
from realmwalker.rules.character import Sheet
from realmwalker.rules.health import TREATMENTS
from realmwalker.rules.wounds import PART_LABEL
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

NEEDS = [("hunger", "Food", "fed"), ("thirst", "Water", "quenched"), ("fatigue", "Rest", "rested"),
         ("dirt", "Cleanliness", "clean")]
TREAT_KEYS = {"bandage": "b", "clean": "c", "stitch": "s", "splint": "p", "cauterize": "f", "poultice": "o"}


def need_bar(canvas: Canvas, x: int, y: int, label: str, value: float, word: str, color: str, width: int) -> None:
    """A bar that empties as the need grows: full = fine."""
    canvas.text(x, y, f"{label:<12}", colors.DIM)
    bar_w = max(6, min(24, width - 30))
    filled = int(round(bar_w * (100 - value) / 100))
    canvas.text(x + 12, y, "█" * filled, colors.named(color if color != "dim" else "good"))
    canvas.text(x + 12 + filled, y, "░" * (bar_w - filled), colors.FAINT)
    canvas.markup(x + 13 + bar_w, y, f"<{color}>{word}</>", max_width=width - bar_w - 13)


def heat_bar(canvas: Canvas, x: int, y: int, value: float, width: int) -> None:
    """A thermometer from freezing (left) to heatstroke (right), with comfort in the middle."""
    canvas.text(x, y, f"{'Warmth':<12}", colors.DIM)
    bar_w = max(9, min(25, width - 30)) | 1
    mid = bar_w // 2
    pos = int(round(mid + value / 100 * mid))
    for i in range(bar_w):
        if i < mid * 0.3:
            c = (70, 110, 200)
        elif i < mid * 0.8:
            c = (110, 150, 200)
        elif i <= bar_w - mid * 0.8:
            c = (110, 170, 90)
        elif i <= bar_w - mid * 0.3:
            c = (220, 150, 60)
        else:
            c = (220, 70, 50)
        canvas.text(x + 12 + i, y, "█" if i == pos else "─", colors.SELECT_FG if i == pos else c)
    st = body.heat_stage(value)
    word, color = st if st else ("comfortable", "good")
    canvas.markup(x + 13 + bar_w, y, f"<{color}>{word}</>", max_width=width - bar_w - 13)


def status_words(char, tables=None) -> list[str]:
    """Short coloured words for everything that is not fine, worst first (for panels)."""
    out = []
    if char.exhaustion:
        out.append(f"<danger>exhaustion {char.exhaustion}</>")
    st = health.blood_stage(char)
    if st and char.blood < 60:
        out.append(f"<{st[1]}>{st[0]}</>")
    bleeding = any((w.bleed and not w.bandaged) or w.internal for w in char.wounds)
    if bleeding:
        out.append("<danger>bleeding</>")
    if any(w.infection > 0 for w in char.wounds):
        out.append("<danger>festering</>")
    if any(d.get("phase") == "sick" for d in char.diseases):
        out.append("<danger>sick</>")
    st = body.heat_stage(char.body_heat)
    if st:
        out.append(f"<{st[1]}>{st[0]}</>")
    for key in ("thirst", "hunger", "fatigue"):
        st = body.stage(key, getattr(char, key))
        if st:
            out.append(f"<{st[1]}>{st[0]}</>")
    st = health.pain_stage(char, tables)
    if st and st[0] != "hurting":
        out.append(f"<{st[1]}>{st[0]}</>")
    elif char.wounds and not bleeding:
        out.append(f"<warn>{len(char.wounds)} wound{'s' if len(char.wounds) > 1 else ''}</>")
    st = health.intox_stage(char)
    if st:
        out.append(f"<{st[1]}>{st[0]}</>")
    st = body.stage("wet", char.wet)
    if st and char.wet >= 35:
        out.append(f"<{st[1]}>{st[0]}</>")
    st = body.stage("dirt", char.dirt)
    if st and char.dirt >= 60:
        out.append(f"<{st[1]}>{st[0]}</>")
    return out


class HealthScreen(Screen):
    title = "Health"

    def __init__(self, app, game, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.selected = 0
        self.mode = "wounds"  # wounds, magic
        self.messages: list[str] = []

    @property
    def char(self):
        return self.game.party[min(self.index, len(self.game.party) - 1)]

    def wound(self):
        c = self.char
        if not c.wounds:
            return None
        self.selected = max(0, min(self.selected, len(c.wounds) - 1))
        return c.wounds[self.selected]

    # ------------------------------------------------------------------ actions
    def say(self, msgs: list[str]) -> None:
        for m in msgs:
            self.game.say(m, "info")
        self.messages = (self.messages + msgs)[-6:]

    def do_treat(self, action: str) -> None:
        w = self.wound()
        if w is None:
            self.app.notify("No wounds to treat.", "dim")
            return
        opts = {a: (ok, why) for a, _, ok, why in care.options(self.game, self.char, w)}
        ok, why = opts.get(action, (False, ""))
        if not ok:
            self.app.notify(f"{TREATMENTS[action][0]}: {why}.", "warn")
            return
        self.say(care.treat(self.game, self.char, w, action))
        self._check_over()

    def do_poppy(self) -> None:
        self.say(care.painkiller(self.game, self.char))

    def open_magic(self) -> None:
        caster = self._caster()
        if caster is None:
            self.app.notify("No one here can cast healing spells.", "dim")
            return
        self.mode = "magic"

    def _caster(self):
        for c in self.game.party:
            if c.alive and care.healing_magic(self.game, c):
                return c
        return None

    def do_cast(self, i: int) -> None:
        caster = self._caster()
        if caster is None:
            self.mode = "wounds"
            return
        spells = care.healing_magic(self.game, caster)
        if not 0 <= i < len(spells):
            return
        sid, name, ok, why = spells[i]
        self.mode = "wounds"
        if not ok:
            self.app.notify(f"{name}: {why}.", "warn")
            return
        self.say(care.cast(self.game, caster, self.char, self.wound(), sid))

    def _check_over(self) -> None:
        if self.game.over is not None:
            self.close()

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        if self.mode == "magic":
            if ev.key == "escape":
                self.mode = "wounds"
            elif ev.is_text and ev.key.isdigit():
                self.do_cast(int(ev.key) - 1)
            return True
        if ev.key in ("escape", "h"):
            self.close()
        elif ev.key == "tab":
            self.index = (self.index + 1) % len(self.game.party)
            self.selected = 0
        elif ev.key == "up":
            self.selected = max(0, self.selected - 1)
        elif ev.key == "down":
            self.selected = min(max(0, len(self.char.wounds) - 1), self.selected + 1)
        elif ev.key == "k":
            self.do_poppy()
        elif ev.key == "m":
            self.open_magic()
        else:
            for action, key in TREAT_KEYS.items():
                if ev.key == key:
                    self.do_treat(action)
                    return True
            return False
        return True

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        game = self.game
        c = self.char
        t = game.tables
        s = Sheet(c, t)
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"Health — {markup.escape(c.name)}", double=True)
        wide = w >= 100
        col_w = min(58, w // 2 - 3) if wide else w - 4
        x, y = 2, 2
        ratio = c.hp / max(1, c.max_hp)
        hcol = "good" if ratio > 0.6 else ("warn" if ratio > 0.3 else "danger")
        cap = body.hp_cap(c)
        cap_text = f" <danger>(at most {cap} while this exhausted)</>" if cap < c.max_hp else ""
        canvas.markup(x, y, f"<dim>Hit points</>  <{hcol}>{c.hp}</> / {c.max_hp}{cap_text}", max_width=col_w)
        y += 1
        bst = health.blood_stage(c)
        bword, bcol = bst if bst else ("", "good")
        canvas.markup(x, y, f"<dim>Blood</>       <{bcol}>{int(c.blood)}%</> {bword}", max_width=col_w)
        y += 1
        p = health.pain(c, t)
        pst = health.pain_stage(c, t)
        pword, pcol = pst if pst else ("none to speak of", "good")
        relief = " <dim>(poppy)</>" if c.effects.get("poppy", 0) > 0 else ""
        canvas.markup(x, y, f"<dim>Pain</>        <{pcol}>{pword}</> <dim>({p})</>{relief}", max_width=col_w)
        y += 1
        ist = health.intox_stage(c)
        if ist:
            canvas.markup(x, y, f"<dim>Drink</>       <{ist[1]}>{ist[0]}</>", max_width=col_w)
            y += 1
        if c.addictions.get("poppy", 0) >= 20:
            craving = " <danger>(withdrawal)</>" if c.effects.get("withdrawal", 0) > 0 else ""
            canvas.markup(x, y, f"<dim>Poppy habit</> <warn>{int(c.addictions['poppy'])}%</>{craving}", max_width=col_w)
            y += 1
        y += 1
        canvas.section(x, y, col_w, "Needs")
        y += 1
        for key, label, fine in NEEDS:
            st = body.stage(key, getattr(c, key))
            word, color = st if st else (fine, "good")
            need_bar(canvas, x, y, label, getattr(c, key), word, color, col_w)
            y += 1
        heat_bar(canvas, x, y, c.body_heat, col_w)
        y += 1
        st = body.stage("wet", c.wet)
        word, color = st if st else ("dry", "good")
        need_bar(canvas, x, y, "Dryness", c.wet, word, color, col_w)
        y += 2
        if c.exhaustion:
            effects = "; ".join(body.EXHAUSTION_EFFECTS[1:c.exhaustion + 1])
            y += canvas.wrapped(x, y, f"<danger>Exhaustion {c.exhaustion} of 6:</> {effects}. A night's sleep with "
                                      f"food and water removes one level.", col_w, max_lines=4)
        pen = health.penalty(c, t)
        if pen:
            y += canvas.wrapped(x, y, f"<warn>{pen} to checks, attacks and saves</> from the body's state.", col_w,
                                max_lines=2)
        from realmwalker.world.weather import describe as describe_weather

        y += canvas.wrapped(x, y, f"<dim>Weather:</> {describe_weather(game.weather)}", col_w, max_lines=2)
        canvas.markup(x, y, f"<dim>Clothing warmth</> {s.warmth():g} <dim>· wind</> {int(s.wind_protection() * 100)}% "
                            f"<dim>· rain</> {int(s.water_protection() * 100)}%", max_width=col_w)
        y += 1
        water = sum(it.fill for it in c.inventory if it.fill)
        canvas.markup(x, y, f"<dim>Water carried:</> {water:g} pints", max_width=col_w)
        y += 1

        if wide:
            x2, y2, w2 = col_w + 5, 2, w - col_w - 8
        else:
            x2, y2, w2 = 2, y + 1, w - 4
        y2 = self._render_wounds(canvas, x2, y2, w2, h - 5)
        self._render_other(canvas, x2, y2, w2, h - 5)
        # Footer.
        bx = canvas.button(2, h - 3, "Back", self.close, hotkey="Esc")
        if len(game.party) > 1:
            bx = canvas.button(bx + 3, h - 3, "Next person", lambda: self.handle_key(KeyEvent("tab")), hotkey="Tab")
        if any(i.def_id == "poppy_milk" for i in c.inventory):
            bx = canvas.button(bx + 3, h - 3, "Poppy milk", self.do_poppy, hotkey="k")
        if self._caster() is not None:
            canvas.button(bx + 3, h - 3, "Healing magic", self.open_magic, hotkey="m")
        if self.mode == "magic":
            self._render_magic(canvas)

    def _render_wounds(self, canvas: Canvas, x: int, y: int, w: int, bottom: int) -> int:
        c = self.char
        canvas.section(x, y, w, "Wounds")
        y += 1
        if not c.wounds:
            canvas.text(x, y, "None. Hit points are only bruises and breath.", colors.DIM, max_width=w)
            return y + 2
        canvas.text(x, y, "↑↓ choose a wound, then treat it with the keys below.", colors.FAINT, max_width=w)
        y += 1
        for i, wd in enumerate(c.wounds):
            if y >= bottom - 10:
                canvas.text(x, y, f"... and {len(c.wounds) - i} more", colors.DIM)
                y += 1
                break
            selected = i == self.selected
            over = canvas.hit(x, y, w, 1, action=lambda i=i: setattr(self, "selected", i))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, y, w, 1, bg)
            label = wd.label[:1].upper() + wd.label[1:]
            canvas.markup(x, y, f"{'►' if selected else ' '} {markup.escape(label)}", fg=colors.SELECT_FG if selected else colors.FG,
                          bg=bg, max_width=w)
            y += 1
            detail = health.describe_wound(wd)
            if detail:
                y += canvas.wrapped(x + 4, y, detail, w - 4, max_lines=2)
        y += 1
        wd = self.wound()
        if wd is None:
            return y
        canvas.markup(x, y, f"<title>Treat the {PART_LABEL.get(wd.part, wd.part)} wound:</>", max_width=w)
        y += 1
        for action, label, ok, why in care.options(self.game, c, wd):
            key = TREAT_KEYS[action]
            if ok:
                canvas.button(x, y, label, lambda a=action: self.do_treat(a), hotkey=key, tooltip=TREATMENTS[action][2])
            else:
                canvas.markup(x, y, f"<faint>[{key}] {label}: {why}</>", max_width=w)
            y += 1
        return y + 1

    def _render_other(self, canvas: Canvas, x: int, y: int, w: int, bottom: int) -> None:
        c = self.char
        t = self.game.tables
        shown = [d for d in c.diseases if d.get("phase") in ("sick", "dormant", "immune")]
        if shown and y < bottom - 2:
            canvas.section(x, y, w, "Sickness")
            y += 1
            for d in shown:
                dd = t.diseases[d["id"]] if d["id"] in t.diseases else {"name": d["id"], "stages": [{"name": ""}]}
                if d["phase"] == "sick":
                    stage = dd["stages"][min(d.get("stage", 0), len(dd["stages"]) - 1)]["name"]
                    line = f"<danger>{dd['name'].capitalize()}</>: {stage}"
                elif d["phase"] == "dormant":
                    line = f"<warn>{dd['name'].capitalize()}</> <dim>(sleeping in the blood; it may come back)</>"
                else:
                    line = f"<dim>{dd['name'].capitalize()} (had it; cannot catch it again)</>"
                y += canvas.wrapped(x, y, line, w, max_lines=2)
            y += 1
        if c.injuries and y < bottom - 2:
            canvas.section(x, y, w, "Lasting injuries")
            y += 1
            for inj in c.injuries:
                d = t.health["injuries"].get(inj, {"name": inj, "text": ""})
                y += canvas.wrapped(x, y, f"<warn>{d['name'].capitalize()}</>: <dim>{d['text']}</>", w, max_lines=2)
            y += 1
        for msg in self.messages[-4:]:
            if y >= bottom:
                break
            y += canvas.wrapped(x, y, msg, w, fg=colors.DIM, max_lines=2)

    def _render_magic(self, canvas: Canvas) -> None:
        from realmwalker.ui.screens.base import modal_box

        caster = self._caster()
        if caster is None:
            return
        spells = care.healing_magic(self.game, caster)
        x, y, w, h = modal_box(canvas, 60, len(spells) + 6, f"{markup.escape(caster.name.split()[0])}'s healing magic")
        for i, (sid, name, ok, why) in enumerate(spells):
            if ok:
                canvas.button(x + 2, y + 2 + i, name, lambda i=i: self.do_cast(i), hotkey=str(i + 1))
            else:
                canvas.markup(x + 2, y + 2 + i, f"<faint>[{i + 1}] {name}: {why}</>", max_width=w - 4)
        canvas.text(x + 2, y + h - 2, "Esc: cancel", colors.FAINT)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "up", "b", "c", "s", "p", "o", "k", "m", "1", "tab", "escape")]
