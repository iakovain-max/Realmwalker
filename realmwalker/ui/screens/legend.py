"""Map legend: what each thing on the maps is, with the picture the map draws for it."""

from __future__ import annotations

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

# (kind, picture or colour, label): kind is "head" (a section), "tile" (a tile from the atlas), "swatch" (a colour of
# the painted map) or "note" (a line of words).
Row = tuple[str, object, str]


def legend_rows(tables, atlas=None) -> list[Row]:
    """Every row of the legend; with an atlas, only pictures it has (a people whose towns have no mark of their own
    is left out)."""
    sp = tables.sprites
    world = sp["world"]
    rows: list[Row] = [("head", None, "The world map")]
    for bid, b in zip(tables.biomes.ids, tables.biomes.defs):
        colour = world["biomes"].get(bid, {}).get("color")
        if colour is None:
            continue
        rows.append(("swatch", tuple(colour), b["name"].capitalize()
                     + ("" if b["passable"] else " <dim>(no crossing on foot)</>")))
    rows.append(("swatch", tuple(world["road"]), "Road"))
    rows.append(("swatch", tuple(world["river"]), "River or stream"))
    rows.append(("head", None, "Places"))
    for kind, spec in tables.sites["settlement_types"].items():
        rows.append(("tile", world["settlements"].get(kind, "map/village"), spec["name"].capitalize()))
    styles: dict[str, str] = {}
    for cid in tables.cultures.ids:
        styles.setdefault(tables.cultures.get(cid).get("town", ""), tables.cultures.get(cid)["folk"][0][0])
    for style, folk in styles.items():
        name = f"map/town_{style}_small"
        if atlas is None or atlas.resolve(name):
            rows.append(("tile", name, f"A town of the {folk} <dim>(each people marks its own)</>"))
    for kind, spec in tables.sites["site_types"].items():
        rows.append(("tile", world["sites"].get(kind, "map/ruin"), f"{spec['name'].capitalize()} <dim>— {spec['desc']}</>"))
    rows.append(("note", None, "<dim>A place lit like lamplight is somewhere the work in your journal (j) wants you.</>"))
    rows.append(("head", None, "On foot (close-up maps)"))
    for tid, t in zip(tables.terrain.ids, tables.terrain.defs):
        spec = sp["terrain"].get(tid, {})
        over = spec.get("over")
        names = [spec.get("object"), spec.get("wall"), over if isinstance(over, str) else (over or [None])[0],
                 spec.get("ground")]
        names = [n for name in names if name for n in (name, f"{name}_0")]
        tile = next((n for n in names if atlas is None or atlas.resolve(n)), names[0] if names else None)
        blocked = "" if t["walk"] else " <dim>(blocks the way)</>"
        rows.append(("tile", tile, f"{t['name'].capitalize()}{blocked}"))
    return rows


class LegendScreen(Screen):
    title = "Map legend"
    sound_open = "ui_page"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.rows = legend_rows(app.tables, app.gfx.atlas)
        self.offset = 0
        self._page = 10

    def scroll(self, dy: int) -> None:
        self.offset = max(0, min(max(0, len(self.rows) - self._page), self.offset + dy))

    def render(self, canvas: Canvas) -> None:
        from realmwalker.ui.gfx.scene import Rect

        w, h = canvas.width, canvas.height
        width = min(96, w - 2)
        x0 = (w - width) // 2
        canvas.frame(x0, 0, width, h - 1, self.title, double=True)
        top, bottom = 2, h - 4
        self._page = max(1, bottom - top)
        self.scroll(0)
        canvas.hit(x0, top, width, self._page, wheel=lambda dy: self.scroll(-dy * 3))
        y = top
        cw, ch = canvas.cell_w, canvas.cell_h
        for kind, pic, label in self.rows[self.offset:]:
            if y >= bottom:
                break
            x = x0 + 2
            if kind == "head":
                canvas.section(x, y, width - 4, label)
            elif kind == "note":
                canvas.markup(x, y, label, max_width=width - 4)
            else:
                if kind == "swatch":
                    canvas.clear_cells(x, y, 2, 1)
                    canvas.under(Rect(x * cw + 2, y * ch + 3, 2 * cw - 4, ch - 6, (*pic, 255)),
                                 Rect(x * cw + 2, y * ch + 3, 2 * cw - 4, ch - 6, (20, 16, 12, 255), line=1))
                else:
                    canvas.icon(x, y, str(pic), "·")
                canvas.markup(x + 4, y, label, max_width=width - 8)
            y += 1
        canvas.button(x0 + 2, h - 3, "Back", self.close, hotkey="Esc")
        canvas.text(x0 + 12, h - 3, "↑↓ PgUp PgDn scroll", colors.FAINT)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "/"):
            self.close()
            return True
        step = {"up": -1, "down": 1, "pageup": -self._page, "pagedown": self._page, "home": -10**6, "end": 10**6}
        if ev.key in step:
            self.scroll(step[ev.key])
            return True
        return False

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("pagedown"), KeyEvent("escape")]


def legend_text(tables) -> str:
    """The legend as plain words (for searching and tests)."""
    return "\n".join(markup.plain(label) for _, _, label in legend_rows(tables))
