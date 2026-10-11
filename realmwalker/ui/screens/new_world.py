"""New World: choose a name, seed, size, the lie of the land, the climate and danger/magic levels, then watch the
world form."""

from __future__ import annotations

import logging
import threading
import traceback

import numpy as np

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import MessageBox, Screen
from realmwalker.ui.widgets import Canvas, TextField
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.model import WORLD_SIZES
from realmwalker.world.naming import Namer

log = logging.getLogger("realmwalker.ui.newworld")

SIZES = [("small", "Small"), ("medium", "Medium"), ("large", "Large")]
DANGER = [(1, "Low"), (2, "Normal"), (3, "High"), (4, "Brutal")]
MAGIC = [(1, "Scarce"), (2, "Rare"), (3, "Uncommon")]
HISTORY = [(100, "Short"), (250, "Normal"), (500, "Long"), (1000, "Epic")]
LAND = [("random", "Any"), ("continent", "Continent"), ("islands", "Islands"), ("twin", "Two lands"),
        ("inland_sea", "Inland sea")]
CLIMATE = [("random", "Any"), ("frozen", "Frozen"), ("cold", "Cold"), ("temperate", "Mild"), ("warm", "Warm"),
           ("scorched", "Hot"), ("varied", "Extreme")]
HELP = {
    "name": "What this world is called. Several worlds can exist side by side.",
    "seed": "The same seed and settings always make the same world. Share a seed to share a world.",
    "size": "Small worlds are quick to cross; large ones take weeks of travel and hold more of everything.",
    "land": "The lie of the land: one great continent, a scatter of islands, two lands with a sea between them, or a "
            "continent round an inland sea. Any: the world decides.",
    "climate": "Frozen worlds are ice and tundra with a cold green south; hot ones are deserts, sand seas and jungles. "
               "Mild worlds have a little of everything, Extreme ones the most of both ends. Any: the world decides.",
    "danger": "How wild and hostile the land is: more ruins and lairs, more dangerous roads.",
    "magic": "How rare magic is. Even at its most common, magic is rare, costly and feared.",
    "history": "How many years the world lives before you arrive (100, 250, 500 or 1000): its kingdoms, wars, "
               "dynasties, dragons and ruins. A longer history takes longer to make.",
    "generate": "Make the world. It takes a few seconds.",
}


class NewWorldScreen(Screen):
    title = "New World"

    def __init__(self, app) -> None:
        super().__init__(app)
        rng = app.ui_rng.child("newworld")
        namer = Namer(app.tables.place_names, rng)
        name = namer.region("world")
        self.name = TextField(name[:1].upper() + name[1:], max_len=28)
        self.seed = TextField(str(rng.randint(1000, 999999)), max_len=9, allowed="0123456789")
        self.size = 1
        self.danger = 1
        self.magic = 1
        self.history = 1
        self.land = 0
        self.climate = 0
        self.rows = ["name", "seed", "size", "land", "climate", "danger", "magic", "history", "generate", "back"]
        self.focus = 0

    @property
    def captures_text(self) -> bool:  # type: ignore[override]
        return self.rows[self.focus] in ("name", "seed")

    def options(self) -> WorldOptions:
        seed = int(self.seed.value) if self.seed.value.isdigit() else 1
        name = self.name.value.strip() or "Nameless"
        return WorldOptions(name=name, seed=seed, size=SIZES[self.size][0], danger=DANGER[self.danger][0],
                            magic=MAGIC[self.magic][0], history=HISTORY[self.history][0], land=LAND[self.land][0],
                            climate=CLIMATE[self.climate][0])

    def generate(self) -> None:
        self.app.replace(WorldGenScreen(self.app, self.options()))

    def _change(self, row: str, d: int) -> None:
        if row == "size":
            self.size = (self.size + d) % len(SIZES)
        elif row == "danger":
            self.danger = (self.danger + d) % len(DANGER)
        elif row == "magic":
            self.magic = (self.magic + d) % len(MAGIC)
        elif row == "history":
            self.history = (self.history + d) % len(HISTORY)
        elif row == "land":
            self.land = (self.land + d) % len(LAND)
        elif row == "climate":
            self.climate = (self.climate + d) % len(CLIMATE)
        elif row == "seed" and d:
            self.seed.value = str(self.app.ui_rng.randint(1000, 999999))

    # ------------------------------------------------------------------
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width, height = min(76, w - 2), min(28, h - 1)
        x0, y0 = (w - width) // 2, max(0, (h - height) // 2)
        canvas.frame(x0, y0, width, height, self.title, double=True)
        x = x0 + 3
        y = y0 + 2
        labels = {"name": "World name", "seed": "Seed", "size": "Size", "danger": "Danger", "magic": "Magic",
                  "history": "History", "land": "Land", "climate": "Climate"}
        choices = {"size": SIZES, "danger": DANGER, "magic": MAGIC, "history": HISTORY, "land": LAND, "climate": CLIMATE}
        settings = [r for r in self.rows if r not in ("generate", "back")]
        for i, row in enumerate(settings):
            ry = y + i * 2
            focused = i == self.focus
            canvas.hit(x, ry, width - 6, 1, action=lambda i=i: self._focus(i), tooltip=HELP[row],
                       right_action=lambda row=row: self._change(row, -1))
            canvas.text(x, ry, ("► " if focused else "  ") + labels[row], colors.TITLE if focused else colors.FG)
            fx = x + 16
            if row == "name":
                self.name.render(canvas, fx, ry, 32, focused)
            elif row == "seed":
                self.seed.render(canvas, fx, ry, 12, focused)
                canvas.text(fx + 14, ry, "← → new random seed" if focused else "", colors.FAINT)
            else:
                values = choices[row]
                index = getattr(self, row)
                cx = fx
                for j, (_, label) in enumerate(values):
                    chosen = j == index
                    text = f"[{label}]" if chosen else f" {label} "
                    over = canvas.hit(cx, ry, len(text), 1, action=lambda row=row, j=j: self._set(row, j))
                    fg = colors.SELECT_FG if chosen else (colors.FG if over else colors.DIM)
                    cx = canvas.text(cx, ry, text, fg, colors.HILITE_BG if chosen and focused else None) + 1
                if row == "size":
                    ww, wh = WORLD_SIZES[SIZES[self.size][0]]
                    canvas.text(cx + 1, ry, f"{ww * 3}×{wh * 3} miles", colors.FAINT)
                elif row == "history":
                    canvas.text(cx + 1, ry, f"{HISTORY[self.history][0]} years", colors.FAINT)
        by = y + len(settings) * 2 + 1
        gen_focus = self.rows[self.focus] == "generate"
        back_focus = self.rows[self.focus] == "back"
        bx = canvas.button(x, by, ("► " if gen_focus else "") + "Generate world", self.generate, hotkey="Enter")
        canvas.button(bx + 4, by, ("► " if back_focus else "") + "Back", self.close, hotkey="Esc")
        canvas.hline(x, by + 2, width - 6, "─", colors.FAINT)
        canvas.wrapped(x, by + 3, f"<dim>{HELP[self.rows[self.focus]] if self.rows[self.focus] in HELP else 'Return to the title screen.'}</>",
                       width - 6, max_lines=3)

    def _focus(self, i: int) -> None:
        self.focus = i

    def _set(self, row: str, j: int) -> None:
        self.focus = self.rows.index(row)
        setattr(self, row, j)

    def handle_key(self, ev: KeyEvent) -> bool:
        row = self.rows[self.focus]
        if ev.key == "escape":
            self.close()
        elif ev.key == "enter":
            if row == "back":
                self.close()
            else:
                self.generate()
        elif ev.key in ("down", "tab"):
            self.focus = (self.focus + 1) % len(self.rows)
        elif ev.key == "up":
            self.focus = (self.focus - 1) % len(self.rows)
        elif ev.key in ("left", "right"):
            self._change(row, -1 if ev.key == "left" else 1)
        elif row == "name":
            return self.name.handle_key(ev)
        elif row == "seed":
            return self.seed.handle_key(ev)
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("up"), KeyEvent("left"), KeyEvent("right"), KeyEvent("enter"),
                KeyEvent("enter"), KeyEvent("enter"), KeyEvent("escape")]


class WorldGenScreen(Screen):
    """Runs world generation in the background, showing the land take shape."""

    title = "Creating the world"
    animating = True

    def __init__(self, app, options: WorldOptions) -> None:
        super().__init__(app)
        self.options = options
        self.gen = WorldGenerator(options, app.tables)
        self.world = None
        self.error: str | None = None
        self.finished = False
        self.headlines: list[str] = []  # the great events of the ages, as they happen
        self.thread = threading.Thread(target=self._run, name="worldgen", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            self.world = self.gen.generate()
        except Exception:
            self.error = traceback.format_exc()
            log.error("World generation failed:\n%s", self.error)

    def update(self) -> None:
        ages = self.gen.ages
        if ages is not None and ages[3] and (not self.headlines or self.headlines[-1] != ages[3]):
            self.headlines.append(ages[3])
            del self.headlines[:-6]
        if self.finished:
            return
        if self.error is not None:
            self.finished = True
            self.app.replace(MessageBox(self.app, "The world could not be made",
                                        "Something went wrong while generating the world. Details are in the log. "
                                        "Try another seed.", color=colors.named("danger")))
        elif self.world is not None:
            self.finished = True
            from realmwalker.game.save import save_world, world_folder
            from realmwalker.ui.screens.creation import CreationScreen

            try:
                save_world(self.world, world_folder(self.app.paths.saves, self.world))
            except Exception:
                self.app.report_error("saving the new world")
            self.app.replace(CreationScreen(self.app, self.world))

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"{self.title}: {markup.escape(self.options.name)}", double=True)
        canvas.text(2, 2, self.gen.stage + "…", colors.TITLE)
        bar_w = min(60, w - 6)
        canvas.bar(2, 3, bar_w, self.gen.fraction, colors.named("gold"))
        canvas.text(2 + bar_w + 2, 3, f"{int(self.gen.fraction * 100)}%", colors.DIM)
        top = 5
        ages = self.gen.ages
        if ages is not None:
            year, figures, events, _ = ages
            canvas.text(2, 4, f"The year {year}  ·  {figures:,} people of note  ·  {events:,} things remembered",
                        colors.DIM, max_width=w - 4)
            lines = self.headlines[-min(4, max(0, (h - 14) // 4)):] if h > 20 else []
            for i, line in enumerate(lines):
                fg = colors.FG if i == len(lines) - 1 else colors.FAINT
                canvas.text(2, 5 + i, markup.escape(line), fg, max_width=w - 4)
            top = 6 + len(lines)
        self._preview(canvas, 2, top, w - 4, h - top - 3)

    def _preview(self, canvas: Canvas, x: int, y: int, aw: int, ah: int) -> None:
        pv = self.gen.preview
        if "elevation" not in pv or aw <= 0 or ah <= 0:
            return
        W, H = pv["elevation"].shape
        scale = max(W / aw, H / ah, 1e-9)
        ow, oh = int(W / scale), int(H / scale)
        xs = np.minimum((np.arange(ow) * scale).astype(int), W - 1)
        ys = np.minimum((np.arange(oh) * scale).astype(int), H - 1)
        if "biome" in pv:
            t = self.app.tables
            painted = t.sprites["world"]["biomes"]
            pal = np.array([painted.get(bid, painted["plains"])["color"] for bid in t.biomes.ids], np.float32)
            colours = pal[pv["biome"][np.ix_(xs, ys)]]
        else:
            e = pv["elevation"][np.ix_(xs, ys)]
            land = np.clip(e / 3000.0, 0, 1)[..., None]
            low, high = np.array([60, 110, 50]), np.array([200, 190, 170])
            colours = low * (1 - land) + high * land
            colours[e < 0] = (20, 40, 90)
        if "river" in pv:
            r = pv["river"][np.ix_(xs, ys)] > 0
            colours[r] = (60, 110, 200)
        if "road" in pv:
            colours[pv["road"][np.ix_(xs, ys)]] = (170, 130, 80)
        marks = {"hamlet": (190, 150, 100), "village": (220, 180, 120), "town": (235, 230, 215), "city": (255, 235, 150),
                 "hold": (190, 200, 225), "elfhall": (130, 230, 200), "ruin": (120, 40, 35)}
        for px, py, kind in self.gen.places:
            cx, cy = int(px / scale), int(py / scale)
            if 0 <= cx < ow and 0 <= cy < oh:
                colours[cx, cy] = marks.get(kind, (220, 180, 120))
        ox = x + (aw - ow) // 2
        oy = y + (ah - oh) // 2
        dst = (slice(ox, ox + ow), slice(oy, oy + oh))
        canvas.con.rgb["ch"][dst] = ord(" ")
        canvas.con.rgb["bg"][dst] = colours.astype(np.uint8)
        canvas.con.rgba["bg"][ox:ox + ow, oy:oy + oh, 3] = 255  # opaque, over the parchment

    def handle_key(self, ev: KeyEvent) -> bool:
        return True  # nothing to do but wait a moment

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("space")]
