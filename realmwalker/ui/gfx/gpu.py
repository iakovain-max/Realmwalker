"""Draws a frame's layers with SDL: text consoles, tiles, pictures, lines and typefaces. Only the window uses this.

Everything is drawn into one frame texture the size of the text grid, which is then put in the window
(centred, scaled down only when the window is smaller than the smallest grid). Screenshots read that texture.
"""

from __future__ import annotations

import logging

import numpy as np
import tcod.render
import tcod.sdl.render
from tcod.sdl.render import BlendMode, RendererFlip, ScaleMode

from realmwalker.ui.gfx import typefaces
from realmwalker.ui.gfx.atlas import Atlas
from realmwalker.ui.gfx.scene import Batch, Clip, Image, Layer, Lines, Rect, Sprite, Text

log = logging.getLogger("realmwalker.gfx")

KEEP_FRAMES = 900  # a picture not drawn for this many frames is let go


class Gpu:
    def __init__(self, renderer: tcod.sdl.render.Renderer, atlas: Atlas) -> None:
        self.r = renderer
        self.atlas = atlas
        self.frame = 0
        self._sheets: dict[tuple[int, bool], tcod.sdl.render.Texture] = {}
        self._sheet_size: list[tuple[int, int]] = []
        self._images: dict = {}  # key -> [texture, last frame]
        self._texts: dict = {}  # key -> [texture, ox, oy, w, h, last frame]
        self._consoles: list[tcod.render.SDLConsoleRender] = []
        self._tileset_atlas: tcod.render.SDLTilesetAtlas | None = None
        self._frame_tex: tcod.sdl.render.Texture | None = None
        self._indices: np.ndarray = np.zeros(0, np.uint32)
        self.last_size = (0, 0)
        self.failed: set[str] = set()

    # ------------------------------------------------------------------ resources
    def set_tileset(self, tileset) -> None:
        self._tileset_atlas = tcod.render.SDLTilesetAtlas(self.r, tileset)
        self._consoles = []

    def _sheet(self, index: int, smooth: bool) -> tcod.sdl.render.Texture | None:
        key = (index, smooth)
        tex = self._sheets.get(key)
        if tex is None:
            sheets = self.atlas.sheets()
            if index >= len(sheets):
                return None
            tex = self.r.upload_texture(sheets[index])
            tex.blend_mode = BlendMode.BLEND
            tex.scale_mode = ScaleMode.LINEAR if smooth else ScaleMode.NEAREST
            self._sheets[key] = tex
        return tex

    def _sheet_dims(self, index: int) -> tuple[int, int]:
        s = self.atlas.sheets()[index]
        return s.shape[1], s.shape[0]

    def _quad_indices(self, n: int) -> np.ndarray:
        if len(self._indices) < n * 6:
            base = np.arange(max(n, 1024), dtype=np.uint32) * 4
            idx = np.stack([base, base + 1, base + 2, base, base + 2, base + 3], axis=1)
            self._indices = np.ascontiguousarray(idx.reshape(-1))
        return self._indices[: n * 6]

    def _image(self, cmd: Image) -> tcod.sdl.render.Texture | None:
        entry = self._images.get(cmd.key)
        if entry is None:
            try:
                pic = cmd.make()
            except Exception:
                if repr(cmd.key) not in self.failed:
                    self.failed.add(repr(cmd.key))
                    log.exception("Could not make the picture %r", cmd.key)
                return None
            if pic is None:
                return None
            arr = np.asarray(pic.convert("RGBA") if hasattr(pic, "convert") else pic, dtype=np.uint8)
            tex = self.r.upload_texture(np.ascontiguousarray(arr))
            tex.blend_mode = BlendMode.BLEND
            tex.scale_mode = ScaleMode.LINEAR if cmd.smooth else ScaleMode.NEAREST
            entry = self._images[cmd.key] = [tex, self.frame]
        entry[1] = self.frame
        return entry[0]

    def drop_image(self, key) -> None:
        self._images.pop(key, None)

    def _text(self, cmd: Text):
        key = (cmd.text, cmd.font, cmd.size, tuple(cmd.rgba), cmd.shadow, cmd.outline)
        entry = self._texts.get(key)
        if entry is None:
            arr, ox, oy = typefaces.render(cmd.text, cmd.font, cmd.size, cmd.rgba, cmd.shadow, cmd.outline)
            tex = self.r.upload_texture(np.ascontiguousarray(arr))
            tex.blend_mode = BlendMode.BLEND
            tex.scale_mode = ScaleMode.LINEAR
            w, h = typefaces.measure(cmd.text, cmd.font, cmd.size)
            entry = self._texts[key] = [tex, ox, oy, w, h, self.frame, arr.shape[1], arr.shape[0]]
        entry[5] = self.frame
        return entry

    def _evict(self) -> None:
        if self.frame % 120:
            return
        old = self.frame - KEEP_FRAMES
        for k in [k for k, v in self._images.items() if v[1] < old]:
            del self._images[k]
        for k in [k for k, v in self._texts.items() if v[5] < old]:
            del self._texts[k]

    # ------------------------------------------------------------------ the frame
    def draw(self, layers: list[Layer], width: int, height: int, bg) -> tcod.sdl.render.Texture:
        """Draw every layer into the frame texture and return it."""
        self.frame += 1
        if self._frame_tex is None or (self._frame_tex.width, self._frame_tex.height) != (width, height):
            self._frame_tex = self.r.new_texture(width, height, format=int(tcod.lib.SDL_PIXELFORMAT_RGBA32),
                                                 access=int(tcod.sdl.render.TextureAccess.TARGET))
            self._frame_tex.blend_mode = BlendMode.NONE
            self._consoles = []
        self.last_size = (width, height)
        with self.r.set_render_target(self._frame_tex):
            self.r.clip_rect = None
            self.r.draw_blend_mode = BlendMode.NONE
            self.r.draw_color = (*bg, 255)
            self.r.clear()
            self.r.draw_blend_mode = BlendMode.BLEND
            for i, layer in enumerate(layers):
                self._run(layer.under)
                self.r.clip_rect = None
                self._console(i, layer.console, width, height)
                self._run(layer.over)
                self.r.clip_rect = None
        self._evict()
        return self._frame_tex

    def present(self, frame_tex, ox: float, oy: float, scale: float, bg) -> None:
        self.r.draw_blend_mode = BlendMode.NONE
        self.r.draw_color = (*bg, 255)
        self.r.clip_rect = None
        self.r.clear()
        frame_tex.scale_mode = ScaleMode.NEAREST if scale >= 1 else ScaleMode.LINEAR
        self.r.copy(frame_tex, dest=(ox, oy, frame_tex.width * scale, frame_tex.height * scale))
        self.r.present()

    def read_frame(self) -> np.ndarray | None:
        if self._frame_tex is None:
            return None
        with self.r.set_render_target(self._frame_tex):
            return self.r.read_pixels(format="RGBA")

    def _console(self, index: int, console, width: int, height: int) -> None:
        if self._tileset_atlas is None:
            return
        while len(self._consoles) <= index:
            self._consoles.append(tcod.render.SDLConsoleRender(self._tileset_atlas))
        tex = self._consoles[index].render(console)
        tex.blend_mode = BlendMode.BLEND
        self.r.copy(tex, dest=(0, 0, tex.width, tex.height))
        self.r.draw_blend_mode = BlendMode.BLEND  # libtcod leaves the renderer copying, not blending

    # ------------------------------------------------------------------ commands
    def _run(self, cmds) -> None:
        for cmd in cmds:
            try:
                if isinstance(cmd, Batch):
                    self._batch(cmd)
                elif isinstance(cmd, Rect):
                    self._rect(cmd)
                elif isinstance(cmd, Text):
                    self._draw_text(cmd)
                elif isinstance(cmd, Image):
                    self._draw_image(cmd)
                elif isinstance(cmd, Sprite):
                    self._sprite(cmd)
                elif isinstance(cmd, Lines):
                    self._lines(cmd)
                elif isinstance(cmd, Clip):
                    self.r.clip_rect = None if cmd.rect is None else tuple(int(v) for v in cmd.rect)
            except Exception:
                kind = type(cmd).__name__
                if kind not in self.failed:  # say it once, then carry on drawing the rest
                    self.failed.add(kind)
                    log.exception("Could not draw a %s", kind)

    def _batch(self, b: Batch) -> None:
        n = len(b.dst)
        if n == 0:
            return
        dst = b.dst
        src = b.src
        smooth = not (np.allclose(dst[:, 2] % src[:, 2], 0) and np.allclose(dst[:, 3] % src[:, 3], 0))
        tex = self._sheet(b.sheet, smooth)
        if tex is None:
            return
        sw, sh = self._sheet_dims(b.sheet)
        x, y, w, h = dst[:, 0], dst[:, 1], dst[:, 2], dst[:, 3]
        xy = np.empty((n, 4, 2), np.float32)
        xy[:, 0, 0] = x
        xy[:, 0, 1] = y
        xy[:, 1, 0] = x + w
        xy[:, 1, 1] = y
        xy[:, 2, 0] = x + w
        xy[:, 2, 1] = y + h
        xy[:, 3, 0] = x
        xy[:, 3, 1] = y + h
        inset = 0.5 if smooth else 0.0
        u0 = (src[:, 0] + inset) / sw
        v0 = (src[:, 1] + inset) / sh
        u1 = (src[:, 0] + src[:, 2] - inset) / sw
        v1 = (src[:, 1] + src[:, 3] - inset) / sh
        uv = np.empty((n, 4, 2), np.float32)
        uv[:, 0, 0] = u0
        uv[:, 0, 1] = v0
        uv[:, 1, 0] = u1
        uv[:, 1, 1] = v0
        uv[:, 2, 0] = u1
        uv[:, 2, 1] = v1
        uv[:, 3, 0] = u0
        uv[:, 3, 1] = v1
        c = b.rgba
        if c.ndim == 2:
            c = np.repeat(c[:, None, :], 4, axis=1)
        self.r.geometry(tex, xy.reshape(-1, 2), np.clip(c, 0, 1).reshape(-1, 4).astype(np.float32),
                        uv.reshape(-1, 2), self._quad_indices(n))

    def _rect(self, c: Rect) -> None:
        self.r.draw_blend_mode = BlendMode.BLEND
        if c.line:
            t = c.line
            self.r.draw_color = tuple(int(v) for v in c.rgba)
            self.r.fill_rects(np.array([[c.x, c.y, c.w, t], [c.x, c.y + c.h - t, c.w, t],
                                        [c.x, c.y + t, t, c.h - 2 * t], [c.x + c.w - t, c.y + t, t, c.h - 2 * t]],
                                       np.float32))
            return
        if c.bottom is None:
            self.r.draw_color = tuple(int(v) for v in c.rgba)
            self.r.fill_rect((c.x, c.y, c.w, c.h))
            return
        top = np.array(c.rgba, np.float32) / 255
        bot = np.array(c.bottom, np.float32) / 255
        xy = np.array([[c.x, c.y], [c.x + c.w, c.y], [c.x + c.w, c.y + c.h], [c.x, c.y + c.h]], np.float32)
        col = np.array([top, top, bot, bot], np.float32)
        uv = np.zeros((4, 2), np.float32)
        self.r.geometry(None, xy, col, uv, self._quad_indices(1))

    def _draw_text(self, cmd: Text) -> None:
        if not cmd.text:
            return
        tex, ox, oy, w, h, _, tw, th = self._text(cmd)
        ax, ay = cmd.anchor[0], cmd.anchor[1] if len(cmd.anchor) > 1 else "t"
        x = cmd.x - (w / 2 if ax == "m" else (w if ax == "r" else 0))
        y = cmd.y - (h / 2 if ay == "m" else (h if ay in ("b", "s") else 0))
        self.r.copy(tex, dest=(round(x + ox), round(y + oy), tw, th))

    def _draw_image(self, cmd: Image) -> None:
        tex = self._image(cmd)
        if tex is None:
            return
        tint = tuple(int(v) for v in cmd.rgba[:3])
        alpha = int(cmd.rgba[3])
        tex.color_mod = tint
        tex.alpha_mod = alpha
        self.r.copy(tex, source=cmd.src, dest=cmd.dst)
        if tint != (255, 255, 255):
            tex.color_mod = (255, 255, 255)
        if alpha != 255:
            tex.alpha_mod = 255

    def _sprite(self, s: Sprite) -> None:
        r = self.atlas.rect(s.name)
        if r is None:
            return
        sheet, x, y, w, h = r
        smooth = (s.w % w) != 0 or (s.h % h) != 0 or (s.angle % 90) != 0
        tex = self._sheet(sheet, smooth)
        if tex is None:
            return
        tex.color_mod = tuple(int(v) for v in s.rgba[:3])
        tex.alpha_mod = int(s.rgba[3])
        self.r.copy(tex, source=(x, y, w, h), dest=(s.x, s.y, s.w, s.h), angle=s.angle,
                    flip=RendererFlip.HORIZONTAL if s.flip else RendererFlip.NONE)
        tex.color_mod = (255, 255, 255)
        tex.alpha_mod = 255

    def _lines(self, c: Lines) -> None:
        pts = c.points
        if len(pts) < 2:
            return
        segs = []
        if c.dash:
            on, off = c.dash
            for a, b in zip(pts[:-1], pts[1:]):
                d = b - a
                length = float(np.hypot(*d))
                if length <= 0:
                    continue
                u = d / length
                t = 0.0
                while t < length:
                    e = min(length, t + on)
                    segs.append((a + u * t, a + u * e))
                    t = e + off
        else:
            segs = list(zip(pts[:-1], pts[1:]))
        if not segs:
            return
        a = np.array([s[0] for s in segs], np.float32)
        b = np.array([s[1] for s in segs], np.float32)
        d = b - a
        length = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-6)[:, None]
        nrm = np.stack([-d[:, 1], d[:, 0]], axis=1) / length * (c.width / 2)
        xy = np.stack([a + nrm, b + nrm, b - nrm, a - nrm], axis=1).astype(np.float32)
        col = np.tile(np.array(c.rgba, np.float32) / 255, (len(segs) * 4, 1))
        uv = np.zeros((len(segs) * 4, 2), np.float32)
        self.r.geometry(None, xy.reshape(-1, 2), col, uv, self._quad_indices(len(segs)))
