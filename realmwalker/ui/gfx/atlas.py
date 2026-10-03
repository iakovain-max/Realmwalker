"""The tile sheets (assets/tiles, built by tools/build_tiles.py): where each named picture is.

Pure data: loading needs Pillow and numpy but no window, so tests can ask what a thing would look like.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger("realmwalker.gfx")

Rect = tuple[int, int, int, int, int]  # sheet, x, y, w, h

_NUMBERED = re.compile(r"^(.*)_(\d+)$")


class Atlas:
    def __init__(self, folder: Path | None) -> None:
        self.folder = folder
        self.tile = 32
        self.rects: dict[str, Rect] = {}
        self.sheet_files: list[str] = []
        self._sheets: list[np.ndarray] | None = None
        self.families: dict[str, list[str]] = {}
        self.figures: dict = {}  # each figure body's hands (tools/build_tiles.py figure_tiles)
        if folder is None:
            return
        index = folder / "tiles.json"
        if not index.exists():
            log.warning("No tile sheets at %s: the maps will be drawn with letters.", folder)
            return
        try:
            meta = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.exception("Could not read %s", index)
            return
        self.tile = int(meta.get("tile", 32))
        self.sheet_files = list(meta.get("sheets", []))
        self.rects = {k: tuple(v) for k, v in meta.get("tiles", {}).items()}
        self.figures = meta.get("figures", {})
        fam: dict[str, list[tuple[int, str]]] = {}
        for name in self.rects:
            m = _NUMBERED.match(name)
            if m:
                fam.setdefault(m.group(1), []).append((int(m.group(2)), name))
        self.families = {k: [n for _, n in sorted(v)] for k, v in fam.items()}

    @property
    def ok(self) -> bool:
        return bool(self.rects)

    def has(self, name: str) -> bool:
        return name in self.rects

    def rect(self, name: str) -> Rect | None:
        return self.rects.get(name)

    def family(self, base: str) -> list[str]:
        """"floor/grass" -> ["floor/grass_0", "floor/grass_1", ...]; a single tile is a family of one."""
        if base in self.families:
            return self.families[base]
        return [base] if base in self.rects else []

    def resolve(self, *names: str) -> str | None:
        """The first of `names` that exists, as a tile or a family (the family's first tile)."""
        for n in names:
            if not n:
                continue
            if n in self.rects:
                return n
            f = self.families.get(n)
            if f:
                return f[0]
        return None

    def sheets(self) -> list[np.ndarray]:
        """The sheet images as RGBA arrays (loaded on first use)."""
        if self._sheets is None:
            from PIL import Image

            self._sheets = []
            for fn in self.sheet_files:
                with Image.open(self.folder / fn) as im:
                    self._sheets.append(np.ascontiguousarray(np.asarray(im.convert("RGBA"), dtype=np.uint8)))
        return self._sheets

    def image(self, name: str):
        """One tile as a PIL image (for building pictures out of tiles, like a paper doll)."""
        from PIL import Image

        r = self.rects.get(name)
        if r is None:
            return None
        s, x, y, w, h = r
        return Image.fromarray(self.sheets()[s][y : y + h, x : x + w])


@lru_cache(maxsize=4)
def load(folder: str) -> Atlas:
    return Atlas(Path(folder))
