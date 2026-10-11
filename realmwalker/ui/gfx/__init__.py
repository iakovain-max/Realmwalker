"""Graphics on top of the text grid: tiles, pictures, smooth movement and fine text.

Every screen draws its words into a tcod console of text cells and records picture commands (scene.py) beside
them, in layers; in a window the GPU draws them (gpu.py). Headless (tests, the autoplay bot) the same commands are
recorded through `headless()` and checked instead of shown, so every screen's pictures are exercised in every run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.ui.gfx.atlas import Atlas

MOTION_LEVELS = ("full", "calm", "off")


@dataclass
class GfxContext:
    """What a screen needs to know to draw pictures this frame."""

    atlas: Atlas
    cell_w: int = 10
    cell_h: int = 20
    now: float = 0.0  # seconds, for animation
    motion: str = "full"  # animations: full, calm (no idle movement), off
    ppc: dict = field(default_factory=dict)  # remembered map scales
    # Paint big pictures (the whole world map) on a background thread. A window does; headless runs do not: the small
    # map stands in for the painted one, and no thread is left painting a world nobody will look at (it used to keep
    # every core busy through a test run).
    background: bool = True

    @property
    def animate(self) -> bool:
        return self.motion != "off"

    @property
    def ambient(self) -> bool:
        """Idle movement: water, torches, weather. Only at "full"."""
        return self.motion == "full"


def headless(cell_w: int = 10, cell_h: int = 20) -> GfxContext:
    """A picture context with no window: screens record their pictures over the real tile sheets (loaded once per
    process), exactly as in a window, and nothing is shown."""
    from realmwalker.paths import Paths
    from realmwalker.ui.gfx.atlas import load

    return GfxContext(load(str(Paths().tiles)), cell_w, cell_h, background=False)
