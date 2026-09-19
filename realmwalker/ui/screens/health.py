"""The Health screen: needs, body heat, wetness, exhaustion, wounds, sickness and lasting injuries."""

from __future__ import annotations

from realmwalker.rules import body
from realmwalker.rules.character import Sheet
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

NEEDS = [("hunger", "Food", "fed"), ("thirst", "Water", "quenched"), ("fatigue", "Rest", "rested"),
         ("dirt", "Cleanliness", "clean")]


def need_bar(canvas: Canvas, x: int, y: int, label: str, value: float, word: str, color: str, width: int) -> None:
    """A bar that empties as the need grows: full = fine."""
    canvas.text(x, y, f"{label:<12}", colors.DIM)
    bar_w = max(6, width - 30)
    filled = int(round(bar_w * (100 - value) / 100))
    canvas.text(x + 12, y, "█" * filled, colors.named(color if color != "dim" else "good"))
    canvas.text(x + 12 + filled, y, "░" * (bar_w - filled), colors.FAINT)
    canvas.markup(x + 13 + bar_w, y, f"<{color}>{word}</>", max_width=width - bar_w - 13)


def heat_bar(canvas: Canvas, x: int, y: int, value: float, width: int) -> None:
    """A thermometer from freezing (left) to heatstroke (right), with comfort in the middle."""
    canvas.text(x, y, f"{'Warmth':<12}", colors.DIM)
    bar_w = max(9, width - 30) | 1
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


def status_words(char) -> list[str]:
    """Short coloured words for everything that is not fine, worst first (for panels)."""
    out = []
    if char.exhaustion:
        out.append(f"<danger>exhaustion {char.exhaustion}</>")
    st = body.heat_stage(char.body_heat)
    if st:
        out.append(f"<{st[1]}>{st[0]}</>")
    for key in ("thirst", "hunger", "fatigue"):
        st = body.stage(key, getattr(char, key))
        if st:
            out.append(f"<{st[1]}>{st[0]}</>")
    bleeding = any(w.bleed and not w.bandaged for w in char.wounds)
    if bleeding:
        out.append("<danger>bleeding</>")
    elif char.wounds:
        out.append(f"<warn>{len(char.wounds)} wound{'s' if len(char.wounds) > 1 else ''}</>")
    for d in char.diseases:
        if d.get("stage", 0) > 0:
            out.append("<danger>sick</>")
            break
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

    @property
    def char(self):
        return self.game.party[min(self.index, len(self.game.party) - 1)]

    def render(self, canvas: Canvas) -> None:
        game = self.game
        c = self.char
        s = Sheet(c, game.tables)
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"Health — {markup.escape(c.name)}", double=True)
        col_w = min(62, w // 2 - 3) if w >= 100 else w - 4
        x = 2
        y = 2
        ratio = c.hp / max(1, c.max_hp)
        hcol = "good" if ratio > 0.6 else ("warn" if ratio > 0.3 else "danger")
        cap = body.hp_cap(c)
        cap_text = f" <danger>(at most {cap} while this exhausted)</>" if cap < c.max_hp else ""
        canvas.markup(x, y, f"<dim>Hit points</>  <{hcol}>{c.hp}</> / {c.max_hp}{cap_text}", max_width=col_w)
        y += 2
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
        else:
            canvas.markup(x, y, "<good>Not exhausted.</>", max_width=col_w)
            y += 1
        pen = body.condition_penalty(c)
        if pen:
            y += canvas.wrapped(x, y, f"<warn>{pen} to checks, attacks and saves</> from hunger, thirst, tiredness, "
                                      f"cold or heat.", col_w, max_lines=2)
        y += 1
        w_now = game.weather
        from realmwalker.world.weather import describe as describe_weather

        canvas.markup(x, y, f"<dim>Weather:</> {describe_weather(w_now)}", max_width=col_w)
        y += 1
        canvas.markup(x, y, f"<dim>Clothing warmth</> {s.warmth():g} <dim>· wind</> {int(s.wind_protection() * 100)}% "
                            f"<dim>· rain</> {int(s.water_protection() * 100)}%", max_width=col_w)
        y += 1
        water = sum(it.fill for it in c.inventory if it.fill)
        canvas.markup(x, y, f"<dim>Water carried:</> {water:g} pints", max_width=col_w)

        # Right column (or below on narrow screens): wounds, sickness, lasting injuries.
        if w >= 100:
            x2, y2, w2 = col_w + 5, 2, w - col_w - 8
        else:
            x2, y2, w2 = 2, y + 2, w - 4
        canvas.section(x2, y2, w2, "Wounds")
        y2 += 1
        if not c.wounds:
            canvas.text(x2, y2, "None. Hit points are only bruises and breath.", colors.DIM, max_width=w2)
            y2 += 1
        for wd in c.wounds:
            bits = []
            if wd.bleed and not wd.bandaged:
                bits.append("<danger>bleeding</>")
            if wd.bandaged:
                bits.append("<good>bandaged</>")
            if getattr(wd, "splinted", False):
                bits.append("<good>splinted</>")
            if wd.infected:
                bits.append("<danger>infected</>")
            line = f"• {markup.escape(wd.label)}" + (f" <dim>—</> {', '.join(bits)}" if bits else "")
            y2 += canvas.wrapped(x2, y2, line, w2, max_lines=2)
            if y2 > h - 6:
                break
        y2 += 1
        if c.diseases:
            canvas.section(x2, y2, w2, "Sickness")
            y2 += 1
            for d in c.diseases:
                y2 += canvas.wrapped(x2, y2, f"• {d['id'].replace('_', ' ')}", w2, max_lines=2)
            y2 += 1
        if c.injuries:
            canvas.section(x2, y2, w2, "Lasting injuries")
            y2 += 1
            for inj in c.injuries:
                y2 += canvas.wrapped(x2, y2, f"• {inj.replace('_', ' ')}", w2, max_lines=2)
        canvas.button(2, h - 3, "Back", self.close, hotkey="Esc")
        if len(game.party) > 1:
            canvas.button(12, h - 3, "Next person", self._next, hotkey="Tab")

    def _next(self) -> None:
        self.index = (self.index + 1) % len(self.game.party)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "h"):
            self.close()
        elif ev.key == "tab":
            self._next()
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("tab", "escape")]
