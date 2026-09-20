"""Map legend: every glyph used on the maps and what it means, drawn in its real colours."""

from __future__ import annotations

from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.map_render import ROAD_FG, RIVER_FG
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText


def _hex(rgb) -> str:
    r, g, b = (int(c) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _glyph(ch: str, rgb) -> str:
    return f"<{_hex(rgb)}>{ch}</>"


def legend_text(tables) -> str:
    out = ["<title>The overworld</>", ""]
    for bid, b in zip(tables.biomes.ids, tables.biomes.defs):
        unique = list(dict.fromkeys(b["glyphs"]))
        glyphs = " ".join(_glyph(g, b["fg"]) for g in unique) + " " * (6 - 2 * len(unique))
        out.append(f"  {glyphs}  {b['name'].capitalize()}" + ("" if b["passable"] else " <dim>(no crossing on foot)</>"))
    out += [
        f"  {_glyph('~', RIVER_FG[1])}      Stream",
        f"  {_glyph('≈', RIVER_FG[3])}      River",
        f"  {_glyph('═', tuple(ROAD_FG))} {_glyph('║', tuple(ROAD_FG))}    Road",
        f"  {_glyph('@', (255, 244, 200))}      You",
        "", "<title>Places</>", "",
    ]
    for kind, spec in tables.sites["settlement_types"].items():
        out.append(f"  {_glyph(spec['glyph'], spec['fg'])}      {spec['name'].capitalize()}")
    for kind, spec in tables.sites["site_types"].items():
        out.append(f"  {_glyph(spec['glyph'], spec['fg'])}      {spec['name'].capitalize()} <dim>— {spec['desc']}</>")
    out += ["", "<dim>A tile lit like lamplight is somewhere the work in your journal (j) wants you.</>",
            "", "<title>On foot (local maps)</>", ""]
    for tid, t in zip(tables.terrain.ids, tables.terrain.defs):
        unique = list(dict.fromkeys(t["glyphs"]))
        glyphs = " ".join(_glyph(g, t["fg"]) for g in unique) + " " * (6 - 2 * len(unique))
        blocked = "" if t["walk"] else " <dim>(blocks the way)</>"
        out.append(f"  {glyphs}  {t['name'].capitalize()}{blocked}")
    return "\n".join(out)


class LegendScreen(Screen):
    title = "Map legend"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.view = ScrollText(legend_text(app.tables))

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(90, w - 2)
        x0 = (w - width) // 2
        canvas.frame(x0, 0, width, h - 1, self.title, double=True)
        self.view.render(canvas, x0 + 2, 2, width - 4, h - 5)
        canvas.button(x0 + 2, h - 3, "Back", self.close, hotkey="Esc")
        canvas.text(x0 + 12, h - 3, "↑↓ PgUp PgDn scroll", colors.FAINT)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "/"):
            self.close()
            return True
        return self.view.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("pagedown"), KeyEvent("escape")]
