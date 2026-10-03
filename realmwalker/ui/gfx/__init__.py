"""Graphics on top of the text grid: tiles, pictures, smooth movement and fine text.

The game still draws every screen into a tcod console of text cells, as it always has. When it runs in a real
window it can also record picture commands (scene.py) beside the text, in layers, and the window draws them
with the GPU (gpu.py). Headless (tests, the autoplay bot) nothing here needs a window: commands are recorded
and ignored, and every screen still writes its words into the cells.
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
    tiles: bool = True  # draw the maps with pictures (Settings "Graphics")
    motion: str = "full"  # animations: full, calm (no idle movement), off
    ppc: dict = field(default_factory=dict)  # remembered map scales

    @property
    def animate(self) -> bool:
        return self.motion != "off"

    @property
    def ambient(self) -> bool:
        """Idle movement: water, torches, weather. Only at "full"."""
        return self.motion == "full"
