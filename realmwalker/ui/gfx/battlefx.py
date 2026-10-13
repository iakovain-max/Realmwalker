"""The battle drawn as a battle mat: the field (cut from the place the fight is in, so it is drawn with the same tiles
as the close-up maps, in the same light), a faint grid of five-foot squares, everyone as a figure on their squares,
and what happens shown as it happens: people walking their paths, a lunge, an arrow in flight, a ray, a fireball's
bead and its burst over every square it fills, a cone of flame, a stroke of lightning, a thunderclap, webs, burning
grass, spirits wheeling about a priest, hits that flash and shake, the damage rising off the wounded, the fallen.

The rules (rules/combat.Battle) write a list of events; this reads the new ones each frame and turns them into
short effects on a timeline, so that a whole enemy turn plays out in order. Nothing here changes the fight. With
animations off, everything simply stands where it is.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.audio.cues import battle_sounds, timeline
from realmwalker.ui.gfx import dolls, theme
from realmwalker.ui.gfx.scene import Image, Lines, Rect, Sprite, Text, tile_batch

STEP = 0.11  # seconds to walk a square
PUSH_STEP = 0.06
LUNGE = 0.26
FLIGHT = 0.26
FLOAT = 1.1
FALL = 0.4
STAGGER = 0.30
TILE_SIZES = (96, 64, 48, 32, 24, 16)  # whole and half multiples of the 32-pixel tiles, so they stay sharp
DAY = np.array([1.0, 1.0, 1.0], np.float32)
NIGHT = np.array([0.30, 0.32, 0.48], np.float32)
DARK = np.array([0.26, 0.25, 0.33], np.float32)  # unlit ground underground: dim, but the shape of the place still shows
TORCH = np.array([1.0, 0.80, 0.52], np.float32)
MAGIC_FX = {"fire": "fx/fire", "cold": "fx/cold", "poison": "fx/poison", "necrotic": "fx/drain", "radiant": "fx/glow",
            "force": "fx/magic", "lightning": "fx/sparkle", "thunder": "", "acid": "fx/poison", "psychic": "fx/drain"}
COLOURS = {"fire": (255, 140, 46), "cold": (150, 205, 255), "lightning": (210, 210, 255), "thunder": (230, 224, 200),
           "necrotic": (150, 80, 170), "radiant": (255, 232, 150), "force": (190, 150, 255), "poison": (130, 210, 90),
           "acid": (170, 225, 70), "psychic": (235, 130, 210), "": (200, 180, 255)}
SPELL_COLOURS = {"sleep": (190, 150, 255), "web": (220, 220, 210), "bless": (255, 220, 120), "healing_word": (140, 230, 120),
                 "cure_wounds": (140, 230, 120), "mass_healing_word": (140, 230, 120), "mass_cure_wounds": (140, 230, 120),
                 "spirit_guardians": (255, 220, 130), "guardian_of_faith": (255, 220, 130), "misty_step": (200, 220, 255)}
CONDITION_WORDS = {"prone": "down", "restrained": "held fast", "paralyzed": "paralysed", "stunned": "stunned",
                   "asleep": "asleep", "poisoned": "poisoned", "grappled": "grappled", "frightened": "afraid",
                   "blinded": "blind"}
STATUS_ROW = 4  # status icons shown over a figure before "+N"
TAGS = {"paralyzed": "held", "stunned": "stunned", "restrained": "webbed", "grappled": "held", "unconscious": "asleep",
        "frightened": "afraid"}  # the one word under a figure (the full words float up when it happens)


def colour_for(dtype: str, spell: str = "") -> tuple[int, int, int]:
    return SPELL_COLOURS.get(spell) or COLOURS.get(dtype, COLOURS[""])


class BattleBoard:
    def __init__(self) -> None:
        self.seen = 0
        self.fx: list[dict] = []
        self.tracks: dict[int, list] = {}  # fighter -> [(start time, path, seconds a square)]
        self.tok_tracks: dict[int, list] = {}
        self.fell: dict[int, float] = {}
        self.lifts: dict[int, tuple[float, float, float, float]] = {}  # fighter -> (start, from z, to z, seconds)
        self.prev: dict[int, str] = {}
        self.busy_until = 0.0
        self.art = None
        self.art_key = None
        self.T = 32
        self.origin = (0.0, 0.0)
        self.rect = (0, 0, 0, 0)
        self.cells: dict[int, tuple[int, int, int, int]] = {}  # fighter -> cell rect (for clicks)
        self.figures: dict[int, list] = {}
        self._impact = 0.0
        self.shake_until = 0.0
        self.cam: tuple[float, float] | None = None
        self.cam_t = 0.0
        self.sounds: list[tuple[float, str]] = []  # (when, sound) for the screen to play, on the moments drawn

    # ------------------------------------------------------------------ the camera
    def layout(self, field, rect, zoom: int | None = None, focus: tuple[float, float] | None = None,
               now: float = 0.0) -> None:
        """Fit the field into the rectangle with square tiles of a whole size (or the size chosen by zooming), big
        enough that people can be told apart: a field too big for the room follows `focus` (the one whose turn it
        is), gliding there."""
        x, y, w, h = rect
        self.rect = rect
        T = zoom
        if T is None:
            T = next((t for t in TILE_SIZES if t * min(field.width, 22) <= w and t * min(field.height, 14) <= h),
                     TILE_SIZES[-1])
        self.T = T
        if focus is not None:
            dt = max(0.0, min(0.2, now - self.cam_t))
            self.cam_t = now
            if self.cam is None or abs(self.cam[0] - focus[0]) > 30 or dt <= 0:
                self.cam = focus
            else:
                k = min(1.0, dt * 6.0)
                self.cam = (self.cam[0] + (focus[0] - self.cam[0]) * k, self.cam[1] + (focus[1] - self.cam[1]) * k)
            focus = self.cam
        fw, fh = field.width * T, field.height * T
        if fw <= w:
            ox = x + (w - fw) / 2
        else:
            cx = (focus[0] if focus else field.width / 2) * T
            ox = x + w / 2 - cx
            ox = min(x, max(x + w - fw, ox))
        if fh <= h:
            oy = y + (h - fh) / 2
        else:
            cy = (focus[1] if focus else field.height / 2) * T
            oy = y + h / 2 - cy
            oy = min(y, max(y + h - fh, oy))
        self.origin = (round(ox), round(oy))

    def to_square(self, px: float, py: float, field) -> tuple[int, int] | None:
        x0, y0, w, h = self.rect
        if not (x0 <= px < x0 + w and y0 <= py < y0 + h):
            return None
        sx = int(math.floor((px - self.origin[0]) / self.T))
        sy = int(math.floor((py - self.origin[1]) / self.T))
        return (sx, sy) if field.in_bounds(sx, sy) else None

    def sq_px(self, x: float, y: float) -> tuple[float, float]:
        return self.origin[0] + x * self.T, self.origin[1] + y * self.T

    # ------------------------------------------------------------------ what happened
    def feed(self, battle, now: float, animate: bool) -> None:
        events = battle.events[self.seen:]
        self.seen = len(battle.events)
        if not events:
            self._states(battle, now, animate)
            return
        t = max(now, self.busy_until - 0.05)
        for ev in events if animate else []:
            t0 = t
            t = self._schedule(battle, ev, t)
            impact = self._impact if self._impact >= t0 - 0.6 else t0
            self.sounds += [(t0 if moment == "start" else max(t0, impact), sid) for moment, sid in battle_sounds(ev)]
        if not animate:
            self.sounds += timeline(events, now)
            for ev in events:
                if ev["kind"] in ("fly", "fall"):
                    self.lifts.pop(ev["who"], None)  # (drawn at its height as it is)
        end = max([e["t0"] + e["dur"] * (0.55 if e["kind"] == "float" else 1.0) for e in self.fx] + [t, now])
        for tracks in list(self.tracks.values()) + list(self.tok_tracks.values()):
            for t0, path, step in tracks:
                end = max(end, t0 + step * (len(path) - 1))
        self.busy_until = end
        self._states(battle, now, animate)
        self.fx = [e for e in self.fx if e["t0"] + e["dur"] > now - 0.05]

    def _states(self, battle, now: float, animate: bool) -> None:
        """Who went down, died or got away since last time (they fall when the blow lands)."""
        for f in battle.fighters:
            state = f.state
            old = self.prev.get(f.id)
            if old is not None and old != state and state in ("down", "dead"):
                self.fell[f.id] = max(now, self._impact) if animate else now - FALL
            if state in ("fighting", "fleeing") and f.id in self.fell:
                del self.fell[f.id]
            self.prev[f.id] = state

    def _schedule(self, battle, ev: dict, t: float) -> float:
        k = ev["kind"]
        if k in ("move", "push", "teleport"):
            path = [tuple(p) for p in ev["path"]]
            who = ev["who"]
            if k == "teleport":
                self.fx.append({"kind": "puff", "at": path[0], "t0": t, "dur": 0.4, "color": (200, 220, 255)})
                self.tracks.setdefault(who, []).append((t + 0.25, [path[-1], path[-1]], 0.01))
                self.fx.append({"kind": "puff", "at": path[-1], "t0": t + 0.25, "dur": 0.4, "color": (200, 220, 255)})
                return t + 0.45
            step = STEP if k == "move" else PUSH_STEP
            self.tracks.setdefault(who, []).append((t, path, step))
            return t + step * (len(path) - 1)
        if k in ("fly", "fall"):  # rising or coming down, or falling out of the sky
            who = ev["who"]
            start = self.height(battle.fighter(who), t) if who in self.lifts else float(ev.get("before", ev.get("feet", 0)))
            end = float(ev.get("z", 0)) if k == "fly" else 0.0
            dur = 0.3 if k == "fly" else 0.22
            self.lifts[who] = (t, start, end, dur)
            return t + dur
        if k == "leave":
            self.fx.append({"kind": "float", "who": ev["who"], "text": "gone", "color": (210, 200, 180), "t0": t,
                            "dur": FLOAT, "size": 16})
            return t + 0.2
        if k == "attack":
            a, b = ev["by"], ev["to"]
            if ev.get("melee"):
                self.fx.append({"kind": "lunge", "who": a, "at": b, "t0": t, "dur": LUNGE})
                impact = t + LUNGE * 0.5
            else:
                how = ev.get("how", "")
                if how.startswith("spell") and ev.get("dtype") in ("cold", "fire", "necrotic", "radiant") and \
                        any(w in ev.get("weapon", "") for w in ("ray", "touch", "bolt")) and "fire bolt" not in ev.get("weapon", ""):
                    self.fx.append({"kind": "beam", "from": a, "to": b, "t0": t, "dur": 0.32, "color": colour_for(ev.get("dtype", ""))})
                    impact = t + 0.12
                else:
                    self.fx.append({"kind": "shot", "from": a, "to": b, "t0": t, "dur": FLIGHT,
                                    "sprite": _missile(ev.get("weapon", ""), how, ev.get("dtype", ""))})
                    impact = t + FLIGHT
            if not ev.get("hit"):
                self.fx.append({"kind": "float", "who": b, "text": "miss", "color": (190, 186, 176), "t0": impact,
                                "dur": FLOAT, "size": 16})
                self.fx.append({"kind": "dodge", "who": b, "t0": impact, "dur": 0.25})
            self._impact = impact
            return t + STAGGER
        if k == "opportunity":
            self.fx.append({"kind": "float", "who": ev["by"], "text": "opportunity!", "color": (255, 210, 110), "t0": t,
                            "dur": FLOAT * 0.8, "size": 14})
            return t
        if k == "dart":
            self.fx.append({"kind": "shot", "from": ev["by"], "to": ev["to"], "t0": t, "dur": 0.3, "sprite": "fx/magic_dart",
                            "curve": 30})
            self._impact = t + 0.3
            return t + 0.12
        if k == "damage":
            at = self._impact if self._impact >= t - 0.6 else t
            crit = ev.get("crit")
            try:
                hurt_party = battle.fighter(ev["to"]).side == "party"
            except StopIteration:
                hurt_party = False
            color = (255, 220, 120) if crit else ((255, 120, 96) if hurt_party else (255, 236, 220))
            self.fx.append({"kind": "hit", "who": ev["to"], "t0": at, "dur": 0.28, "crit": crit})
            self.fx.append({"kind": "float", "who": ev["to"], "text": ("crit! " if crit else "") + str(ev["amount"]),
                            "color": color, "t0": at, "dur": FLOAT, "size": 24 if crit else 20})
            spark = MAGIC_FX.get(ev.get("dtype", ""))
            if spark:
                self.fx.append({"kind": "burst", "who": ev["to"], "sprite": spark, "t0": at, "dur": 0.45})
            elif ev.get("dtype") in ("slashing", "piercing"):
                self.fx.append({"kind": "burst", "who": ev["to"], "sprite": "fx/blood", "t0": at, "dur": 0.4, "small": True})
            if crit:
                self.shake_until = max(self.shake_until, at + 0.25)
            return t
        if k == "immune":
            self.fx.append({"kind": "float", "who": ev["to"], "text": "unharmed", "color": (170, 170, 190),
                            "t0": max(t, self._impact), "dur": FLOAT, "size": 16})
            return t
        if k == "heal":
            self.fx.append({"kind": "burst", "who": ev["to"], "sprite": "fx/sparkle", "t0": t, "dur": 0.6})
            self.fx.append({"kind": "float", "who": ev["to"], "text": f"+{ev['amount']}", "color": (140, 230, 120),
                            "t0": t, "dur": FLOAT, "size": 20})
            return t + 0.1
        if k == "save":
            if ev.get("ok"):
                self.fx.append({"kind": "float", "who": ev["who"], "text": "saved", "color": (200, 200, 210),
                                "t0": max(t, self._impact) + 0.05, "dur": FLOAT * 0.8, "size": 13, "low": True})
            return t
        if k == "cast":
            return self._cast(battle, ev, t)
        if k == "buff":
            self.fx.append({"kind": "ring", "who": ev["who"], "t0": t, "dur": 0.7, "color": colour_for("", ev.get("spell", "")) if
                            ev.get("spell") in SPELL_COLOURS else (255, 220, 130)})
            return t
        if k in ("condition", "prone", "yield", "hide", "stand"):
            word = {"prone": "knocked down", "yield": "yields", "hide": "hidden", "stand": ""}.get(k) or \
                CONDITION_WORDS.get(ev.get("cond", ""), ev.get("cond", ""))
            if word:
                self.fx.append({"kind": "float", "who": ev["who"], "text": word, "color": (230, 200, 150),
                                "t0": max(t, self._impact) + 0.1, "dur": FLOAT, "size": 15, "low": True})
            return t
        if k == "concentration_end":
            self.fx.append({"kind": "float", "who": ev["who"], "text": "concentration broken", "color": (200, 170, 255),
                            "t0": max(t, self._impact) + 0.15, "dur": FLOAT, "size": 13, "low": True})
            return t
        if k == "token_move":
            self.tok_tracks.setdefault(ev["id"], []).append((t, [tuple(p) for p in ev["path"]], 0.08))
            return t + 0.08
        if k == "token_strike":
            self.fx.append({"kind": "tok_lunge", "id": ev["id"], "at": ev["to"], "t0": t, "dur": LUNGE})
            return t
        if k == "zone":
            self.fx.append({"kind": "zone_in", "cells": [tuple(c) for c in ev.get("cells", [])], "t0": t, "dur": 0.5,
                            "zone": ev.get("zone", "")})
            return t
        return t

    def _cast(self, battle, ev: dict, t: float) -> float:
        spell = ev.get("spell", "")
        dtype = ev.get("dtype", "")
        color = colour_for(dtype, spell)
        self.fx.append({"kind": "glow", "who": ev["by"], "t0": t, "dur": 0.5, "color": color})
        area = [tuple(c) for c in ev.get("area") or []]
        if not area:
            return t + 0.2
        shape = ev.get("shape", "")
        point = tuple(ev["point"]) if ev.get("point") else None
        start = t + 0.25
        try:
            caster = battle.fighter(ev["by"])
            ox, oy = caster.x + caster.sq / 2, caster.y + caster.sq / 2
        except StopIteration:
            ox, oy = area[0][0] + 0.5, area[0][1] + 0.5
        if shape in ("sphere", "cylinder") and point is not None and ev.get("effect") in ("save",) and spell != "sleep":
            # A bead flies to the spot, and bursts.
            self.fx.append({"kind": "bead", "from": (ox, oy), "to": (point[0] + 0.5, point[1] + 0.5), "t0": start,
                            "dur": 0.32, "color": color, "sprite": MAGIC_FX.get(dtype, "fx/magic")})
            start += 0.32
            cx, cy = point[0] + 0.5, point[1] + 0.5
        elif point is not None and shape in ("sphere", "cylinder", "cube") and ev.get("effect") not in ("breath",):
            cx, cy = point[0] + 0.5, point[1] + 0.5
        else:
            cx, cy = ox, oy
        if shape == "line" and point is not None:
            far = max(area, key=lambda c: (c[0] + 0.5 - ox) ** 2 + (c[1] + 0.5 - oy) ** 2)
            self.fx.append({"kind": "bolt", "from": (ox, oy), "to": (far[0] + 0.5, far[1] + 0.5), "t0": start, "dur": 0.45,
                            "color": color, "seed": len(self.fx)})
        if shape == "cube" and ev.get("effect") == "save":
            self.fx.append({"kind": "shock", "at": (cx, cy), "t0": start, "dur": 0.45, "color": color,
                            "radius": max(1.5, math.sqrt(len(area)) * 0.8)})
        if shape in ("sphere", "cylinder") and ev.get("effect") == "save":
            radius = max(abs(c[0] + 0.5 - cx) for c in area) + 0.5 if area else 2
            self.fx.append({"kind": "flash", "at": (cx, cy), "t0": start, "dur": 0.55, "color": color, "radius": radius})
            self.shake_until = max(self.shake_until, start + 0.3)
        sprite = "fx/sparkle" if ev.get("effect") in ("sleep", "heal", "buff") else MAGIC_FX.get(dtype, "fx/magic")
        if spell == "web" or dtype in ("thunder", "lightning"):
            sprite = ""  # the bolt or the shockwave is the picture; the squares only flash
        for c in area:
            d = math.hypot(c[0] + 0.5 - cx, c[1] + 0.5 - cy)
            if sprite:
                self.fx.append({"kind": "cell", "at": c, "t0": start + d * 0.035, "dur": 0.5, "sprite": sprite, "color": color})
        reach = max((math.hypot(c[0] + 0.5 - cx, c[1] + 0.5 - cy) for c in area), default=0)
        self._impact = start + reach * 0.035 + 0.1
        return self._impact + 0.15

    def busy(self, now: float) -> bool:
        return now < self.busy_until

    # ------------------------------------------------------------------ where everyone is drawn
    def pos(self, f, now: float) -> tuple[float, float]:
        """Where a fighter is drawn now (in squares): along the path they are walking, else where they stand."""
        tracks = self.tracks.get(f.id)
        if tracks:
            keep = []
            out = None
            for t0, path, step in tracks:
                t1 = t0 + step * (len(path) - 1)
                if now >= t1:
                    continue
                keep.append((t0, path, step))
                if out is None:
                    if now < t0:
                        out = path[0]
                    else:
                        k = (now - t0) / step
                        i = min(len(path) - 2, int(k))
                        p = k - i
                        a, b = path[i], path[i + 1]
                        out = (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)
            self.tracks[f.id] = keep
            if out is not None:
                return float(out[0]), float(out[1])
        return float(f.x), float(f.y)

    def tok_pos(self, tok, now: float) -> tuple[float, float]:
        tracks = self.tok_tracks.get(tok.id)
        if tracks:
            for t0, path, step in tracks:
                t1 = t0 + step * (len(path) - 1)
                if now < t1:
                    if now < t0:
                        return path[0]
                    p = (now - t0) / max(1e-6, t1 - t0)
                    return (path[0][0] + (path[-1][0] - path[0][0]) * p, path[0][1] + (path[-1][1] - path[0][1]) * p)
            self.tok_tracks[tok.id] = []
        return float(tok.x), float(tok.y)

    def height(self, f, now: float) -> float:
        """A fighter's height above the ground in feet as drawn now (rising and falling are animated)."""
        lift = self.lifts.get(f.id)
        if lift is None:
            return float(f.z)
        t0, a, b, dur = lift
        if now <= t0:
            return a
        return b if now >= t0 + dur else a + (b - a) * (now - t0) / dur

    def lift_px(self, f, now: float) -> float:
        """How far above its shadow a flier is drawn: a little for every five feet, so that height reads at a glance
        without hiding the squares above it."""
        return min(self.height(f, now), 60.0) / 5.0 * self.T * 0.13

    def place(self, f, now: float) -> tuple[float, float, float]:
        """Pixel centre-bottom (feet) and size of a fighter now, moved by any lunge, shake or dodge."""
        x, y = self.pos(f, now)
        T = self.T
        size = T * f.sq
        px, py = self.sq_px(x, y)
        cx, fy = px + size / 2, py + size
        for e in self.fx:
            if now < e["t0"] or now > e["t0"] + e["dur"]:
                continue
            p = (now - e["t0"]) / e["dur"]
            if e["kind"] == "lunge" and e["who"] == f.id:
                tx, ty = self._target_px(e["at"], now)
                if tx is not None:
                    k = math.sin(math.pi * p) * 0.38
                    cx += (tx - cx) * k
                    fy += (ty - fy) * k
            elif e["kind"] == "hit" and e["who"] == f.id:
                amp = (6 if e.get("crit") else 3.5) * (1 - p)
                cx += math.sin(p * 40) * amp
            elif e["kind"] == "dodge" and e["who"] == f.id:
                cx += math.sin(math.pi * p) * T * 0.15
        return cx, fy, size

    def _target_px(self, fid, now):
        f = self._fighters.get(fid) if hasattr(self, "_fighters") else None
        if f is None:
            return None, None
        x, y = self.pos(f, now)
        px, py = self.sq_px(x, y)
        s = self.T * f.sq
        return px + s / 2, py + s

    # ------------------------------------------------------------------ drawing
    def draw(self, canvas, game, battle, rect, now: float, *, overlay: dict | None = None, zoom: int | None = None) -> None:
        overlay = overlay or {}
        gfx = canvas.gfx
        atlas = gfx.atlas
        fld = battle.field
        self._fighters = {f.id: f for f in battle.fighters}
        cur = battle.current if (battle.order and battle.outcome is None) else None
        focus = None
        if cur is not None:
            fx_, fy_ = self.pos(cur, now)
            focus = (fx_ + cur.sq / 2, fy_ + cur.sq / 2)
        self.layout(fld, rect, zoom, focus, now)
        if now < self.shake_until and gfx.animate:
            a = (self.shake_until - now) * 10
            self.origin = (self.origin[0] + math.sin(now * 61) * a, self.origin[1] + math.cos(now * 53) * a)
        x, y, w, h = rect
        canvas.under(*theme.panel(x, y, w, h, "inset"))
        T = self.T
        fx, fy = self.origin
        canvas.under(Rect(fx - 6, fy - 6, fld.width * T + 12, fld.height * T + 12, (6, 5, 7, 255)))
        canvas.under(Rect(fx - 4, fy - 4, fld.width * T + 8, fld.height * T + 8, (*theme.BRONZE, 255), line=2))
        self._ground(canvas, game, battle, now)
        self._zones(canvas, battle, now)
        self._grid(canvas, fld)
        self._overlay_under(canvas, battle, overlay, now)
        self._tokens(canvas, battle, now)
        self._people(canvas, game, battle, now, overlay, cur)
        self._overlay_over(canvas, battle, overlay, now)
        self._effects(canvas, now)

    def _ground(self, canvas, game, battle, now: float) -> None:
        from realmwalker.ui.gfx.localview import LocalArt, _batches, _corners
        from realmwalker.world.local import LocalMap

        fld = battle.field
        key = (fld.key, fld.version)
        if self.art_key != key:
            lm = LocalMap(key=f"{fld.key}", kind=fld.kind, width=fld.width, height=fld.height,
                          terrain_ids=list(game.tables.terrain.ids), terrain=fld.terrain.copy(),
                          variant=np.zeros((fld.width, fld.height), np.uint8), meta={"style": fld.style})
            getattr(game, "_remaps", {}).pop(lm.key, None)
            self.art = LocalArt(game, lm, canvas.gfx.atlas)
            self.art_key = key
        art = self.art
        T = self.T
        W, H = fld.width, fld.height
        L = battle.light()
        base = float(np.clip(fld.base_light, 0, 1))
        if fld.underground:
            B = DARK
        elif base >= 0.95:
            B = DAY
        else:
            B = NIGHT + (DAY - NIGHT) * base
        extra = np.clip(L - base, 0, 1)[..., None]
        light = np.clip(B[None, None, :] + extra * TORCH[None, None, :] * 1.05, 0, 1.0).astype(np.float32)
        self.light = light
        corners = _corners(light, art.WALL >= 0)
        ox, oy = self.origin
        gx = (ox + np.arange(W) * T)[:, None].repeat(H, 1).astype(np.float32)
        gy = (oy + np.arange(H) * T)[None, :].repeat(W, 0).astype(np.float32)
        hsh = art.hash
        ambient = canvas.gfx.ambient
        frame = int(now * 5) if ambient else 0
        quads = []
        everywhere = np.ones((W, H), bool)

        def layer(F, anim=None):
            m = everywhere & (F >= 0)
            if not m.any():
                return
            f = F[m]
            count = art.fam_count[f]
            pick = np.where(anim[m] > 1, (hsh[m] + frame) % count, hsh[m] % count) if anim is not None else hsh[m] % count
            rows = art.fam_rects[art.fam_start[f] + pick]
            dst = np.stack([gx[m], gy[m], np.full(len(f), T, np.float32), np.full(len(f), T, np.float32)], axis=1)
            col = corners[:-1, :-1][m], corners[1:, :-1][m], corners[1:, 1:][m], corners[:-1, 1:][m]
            rgba = np.ones((len(f), 4, 4), np.float32)
            rgba[:, 0, :3], rgba[:, 1, :3], rgba[:, 2, :3], rgba[:, 3, :3] = col
            quads.append((dst, rows, rgba))

        layer(art.G)
        layer(art.WALL)
        layer(art.V)
        layer(art.O, art.ANIM)
        canvas.under(*_batches(quads))

    def _grid(self, canvas, fld) -> None:
        """Faint lines between the squares, so distances can be counted."""
        T = self.T
        if T < 20:
            return
        ox, oy = self.origin
        W, H = fld.width, fld.height
        col = (0, 0, 0, 46)
        cmds = []
        for i in range(1, W):
            cmds.append(Lines([(ox + i * T, oy), (ox + i * T, oy + H * T)], 1, col))
        for j in range(1, H):
            cmds.append(Lines([(ox, oy + j * T), (ox + W * T, oy + j * T)], 1, col))
        canvas.under(*cmds)

    def _zones(self, canvas, battle, now: float) -> None:
        T = self.T
        atlas = canvas.gfx.atlas
        ambient = canvas.gfx.ambient
        for z in battle.zones:
            if z.kind == "web":
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Image("bweb", _web_image, (px, py, T, T), rgba=(235, 235, 225, 210), smooth=False))
            elif z.kind == "fire":
                frames = atlas.family("fx/fire") or atlas.family("fx/flame")
                for i, (x, y) in enumerate(sorted(z.cells)):
                    px, py = self.sq_px(x, y)
                    canvas.under(Rect(px, py, T, T, (255, 110, 30, 50)))
                    if frames:
                        name = frames[(int(now * 8) + i) % len(frames)] if ambient else frames[i % len(frames)]
                        canvas.under(Sprite(name, px, py, T, T, (255, 255, 255, 220)))
            elif z.kind in ("fog", "darkness"):
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Image("bfog", _fog_image, (px - T * 0.25, py - T * 0.25, T * 1.5, T * 1.5),
                                       rgba=(180, 184, 190, 170) if z.kind == "fog" else (10, 8, 14, 230)))
            elif z.kind == "ice":
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Image("bice", _ice_image, (px, py, T, T), rgba=(220, 240, 255, 200), smooth=False))
            elif z.kind in ("guardians", "guardian"):
                pulse = 0.5 + 0.5 * math.sin(now * 3) if ambient else 0.6
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Rect(px, py, T, T, (255, 220, 120, int(26 + 22 * pulse))))
                xs = [c[0] for c in z.cells]
                ys = [c[1] for c in z.cells]
                if xs:
                    bx, by = self.sq_px(min(xs), min(ys))
                    canvas.under(theme.lines_box(bx, by, (max(xs) - min(xs) + 1) * T, (max(ys) - min(ys) + 1) * T,
                                                 (255, 220, 130, int(90 + 80 * pulse))))
                if z.kind == "guardians" and ambient:
                    owner = self._fighters.get(z.owner)
                    if owner is not None:
                        ox_, oy_ = self.pos(owner, now)
                        ccx, ccy = self.sq_px(ox_ + owner.sq / 2, oy_ + owner.sq / 2)
                        for k in range(6):
                            ang = now * 1.6 + k * math.pi / 3
                            r = T * (z.radius + 0.3) * (0.55 + 0.25 * math.sin(now * 2 + k))
                            sx, sy = ccx + math.cos(ang) * r, ccy + math.sin(ang) * r * 0.8
                            canvas.under(Image("bspirit", _glow_image, (sx - T * 0.3, sy - T * 0.3, T * 0.6, T * 0.6),
                                               rgba=(255, 236, 170, 200)))

    def _overlay_under(self, canvas, battle, ov: dict, now: float) -> None:
        T = self.T
        for (x, y) in ov.get("exits", ()):
            px, py = self.sq_px(x, y)
            canvas.under(Rect(px + 2, py + 2, T - 4, T - 4, (240, 220, 140, 60)))
        reach = ov.get("reach") or set()
        if reach:
            # Where they can walk this turn: a faint wash, and a clear line round its edge.
            for (x, y) in reach:
                px, py = self.sq_px(x, y)
                canvas.under(Rect(px, py, T, T, (150, 200, 255, 22)))
            edge = []
            for (x, y) in reach:
                px, py = self.sq_px(x, y)
                if (x - 1, y) not in reach:
                    edge.append(Lines([(px, py), (px, py + T)], 2, (170, 210, 255, 170)))
                if (x + 1, y) not in reach:
                    edge.append(Lines([(px + T, py), (px + T, py + T)], 2, (170, 210, 255, 170)))
                if (x, y - 1) not in reach:
                    edge.append(Lines([(px, py), (px + T, py)], 2, (170, 210, 255, 170)))
                if (x, y + 1) not in reach:
                    edge.append(Lines([(px, py + T), (px + T, py + T)], 2, (170, 210, 255, 170)))
            canvas.under(*edge)
        for (x, y) in ov.get("dash", ()):
            px, py = self.sq_px(x, y)
            canvas.under(Rect(px, py, T, T, (255, 220, 110, 30)))
        for (x, y) in ov.get("threat", ()):
            px, py = self.sq_px(x, y)
            canvas.under(Rect(px, py, T, T, (255, 70, 50, 46)))
        for (x, y) in ov.get("flank", ()):
            # Where you could stand to flank the enemy pointed at: a gold diamond in the square.
            cx, cy = self.sq_px(x + 0.5, y + 0.5)
            r = T * 0.3
            canvas.under(Lines([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy), (cx, cy - r)], max(2, T // 16),
                               (255, 214, 110, 220)))
        area = ov.get("area")
        if area:
            r, g, b = ov.get("area_color", (255, 160, 60))
            pulse = 0.5 + 0.5 * math.sin(now * 5) if canvas.gfx.ambient else 0.6
            for (x, y) in area:
                px, py = self.sq_px(x, y)
                canvas.under(Rect(px, py, T, T, (r, g, b, int(70 + 50 * pulse))))
                canvas.under(Rect(px, py, T, T, (r, g, b, 150), line=1))
        cur = ov.get("current")
        if cur is not None:
            f = self._fighters.get(cur)
            if f is not None:
                x, y = self.pos(f, now)
                px, py = self.sq_px(x, y)
                s = T * f.sq
                pulse = 0.5 + 0.5 * math.sin(now * 4) if canvas.gfx.ambient else 1.0
                canvas.under(Image("bring", _ring_image, (px - s * 0.06, py + s * 0.55, s * 1.12, s * 0.5),
                                   rgba=(255, 214, 110, int(150 + 90 * pulse))))
        for fid in ov.get("targets", ()):
            f = self._fighters.get(fid)
            if f is None:
                continue
            px, py = self.sq_px(*self.pos(f, now))
            s = T * f.sq
            col = (255, 90, 60, 230) if fid == ov.get("target") else (230, 130, 90, 140)
            canvas.under(Image("bring", _ring_image, (px - s * 0.06, py + s * 0.55, s * 1.12, s * 0.5), rgba=col))

    def _overlay_over(self, canvas, battle, ov: dict, now: float) -> None:
        T = self.T
        path = ov.get("path")
        if path:
            pts = [self.sq_px(x + 0.5, y + 0.5) for x, y in path]
            warn = ov.get("warn", set())
            canvas.over(Lines(pts, max(2, T // 12), (255, 236, 170, 200), dash=(T * 0.18, T * 0.12)))
            for i, (x, y) in enumerate(path[1:], 1):
                cx, cy = self.sq_px(x + 0.5, y + 0.5)
                r = T * 0.1
                col = (255, 90, 60, 240) if (x, y) in warn else (255, 236, 170, 220)
                canvas.over(Rect(cx - r, cy - r, 2 * r, 2 * r, col))
            ex, ey = path[-1]
            px, py = self.sq_px(ex, ey)
            canvas.over(Rect(px + 1, py + 1, T - 2, T - 2, (255, 236, 170, 230), line=2))
            if ov.get("cost") is not None:
                canvas.over(Text(px + T / 2, py - 2, f"{ov['cost']} ft", "prose_bold", max(12, min(18, T // 3)),
                                 (255, 240, 200, 255), anchor="mb", outline=True, shadow=False))
            if warn:
                wx, wy = self.sq_px(*sorted(warn)[0])
                canvas.over(Text(wx + T / 2, wy + T / 2, "!", "heading", max(14, T // 2), (255, 90, 60, 255),
                                 anchor="mm", outline=True, shadow=False))
        hov = ov.get("hover")
        if hov is not None:
            px, py = self.sq_px(*hov)
            canvas.over(Rect(px, py, T, T, (255, 255, 255, 110), line=1))
        aim = ov.get("aim")
        if aim is not None:
            px, py = self.sq_px(*aim)
            canvas.over(Rect(px - 1, py - 1, T + 2, T + 2, (255, 220, 120, 240), line=2))

    def _tokens(self, canvas, battle, now: float) -> None:
        T = self.T
        atlas = canvas.gfx.atlas
        for tok in battle.tokens:
            x, y = self.tok_pos(tok, now)
            px, py = self.sq_px(x, y)
            bob = math.sin(now * 3 + tok.id) * T * 0.06 if canvas.gfx.ambient else 0.0
            for e in self.fx:
                if e["kind"] == "tok_lunge" and e["id"] == tok.id and e["t0"] <= now <= e["t0"] + e["dur"]:
                    tx, ty = self._target_px(e["at"], now)
                    if tx is not None:
                        k = math.sin(math.pi * (now - e["t0"]) / e["dur"]) * 0.45
                        px += (tx - T / 2 - px) * k
                        py += (ty - T - py) * k
            if tok.kind == "guardian":
                canvas.under(Image("bglow", _glow_image, (px - T * 0.3, py - T * 0.3, T * 1.6, T * 1.6), rgba=(255, 230, 150, 120)))
                name = "feature/statue_hero" if atlas.has("feature/statue_hero") else "feature/statue"
                canvas.under(Sprite(name, px, py, T, T, (255, 240, 200, 255)))
            else:
                canvas.under(Image("bglow", _glow_image, (px - T * 0.15, py - T * 0.15 + bob, T * 1.3, T * 1.3),
                                   rgba=(170, 150, 255, 110)))
                name = "item/mace" if atlas.has("item/mace") else "fx/magic_0"
                canvas.under(Sprite(name, px + T * 0.02, py + bob, T * 0.96, T * 0.96, (235, 225, 255, 255), angle=-30.0))

    def _people(self, canvas, game, battle, now: float, ov: dict, cur) -> None:
        gfx = canvas.gfx
        atlas = gfx.atlas
        T = self.T
        light = getattr(self, "light", None)
        seen_by_party = ov.get("seen", None)
        order = []
        for f in battle.fighters:
            if f.state == "fled":
                continue
            x, y = self.pos(f, now)
            order.append((y + f.sq, f, x, y))
        order.sort(key=lambda t: t[0])
        self.cells = {}
        self.status_px = {}
        cw, ch = canvas.cell_w, canvas.cell_h
        for _, f, x, y in order:
            cx, fy, s = self.place(f, now)
            parts = self.figures.get(f.id)
            if parts is None:
                parts = _figure(f, game, atlas)
                self.figures[f.id] = parts
            tint = (1.0, 1.0, 1.0)
            if light is not None:
                lx, ly = int(min(battle.field.width - 1, max(0, round(x)))), int(min(battle.field.height - 1, max(0, round(y))))
                tint = tuple(float(v) for v in light[lx, ly])
            alpha = 1.0
            flash = next((e for e in self.fx if e["kind"] == "hit" and e["who"] == f.id and e["t0"] <= now <= e["t0"] + e["dur"]),
                         None)
            if flash is not None:
                p = (now - flash["t0"]) / flash["dur"]
                tint = (1.0, 0.45 + 0.55 * p, 0.42 + 0.58 * p)
            if f.state == "surrendered":
                tint = tuple(v * 0.6 for v in tint)
            if f.hidden:
                alpha = 0.55
            unseen = seen_by_party is not None and f.side != "party" and f.id not in seen_by_party and f.state != "dead"
            if unseen:  # somewhere in the dark: a shape, no more
                tint = (0.10, 0.10, 0.16)
                alpha = min(alpha, 0.75)
            angle = 0.0
            if f.id in self.fell:
                p = min(1.0, max(0.0, (now - self.fell[f.id]) / FALL)) if gfx.animate else 1.0
                angle = (90.0 if f.side == "party" else -90.0) * (p * p)
                if f.state == "dead":
                    alpha *= 1 - 0.45 * p
                    tint = tuple(v * (1 - 0.35 * p) for v in tint)
            elif "prone" in f.conditions and f.state == "fighting":
                angle = 70.0 if f.side == "party" else -70.0
            up = self.lift_px(f, now) if f.state in ("fighting", "fleeing") else 0.0
            canvas.under(Image("bshadow", _shadow_image, (cx - s * 0.36, fy - s * 0.14, s * 0.72, s * 0.22),
                               rgba=(255, 255, 255, 150 if not up else 95)))
            if up:  # aloft: the shadow stays on the ground, the figure above it, and how high beside it
                canvas.over(Text(cx + s * 0.42, fy - 1, f"{int(round(self.height(f, now) / 5.0)) * 5} ft", "prose_bold",
                                 max(10, min(13, T // 4)), (190, 220, 255, 255), anchor="mb", outline=True, shadow=False))
                fy -= up
            if f.state == "dead" and f.id in self.fell:
                canvas.under(Image("bblood", _blood_image, (cx - s * 0.4, fy - s * 0.16, s * 0.8, s * 0.24),
                                   rgba=(140, 20, 16, 170)))
            bob = math.sin(now * 3.0) * 1.5 if (cur is not None and f is cur and gfx.ambient and not angle) else 0
            top = fy - s * 0.9 if angle else fy - s + bob
            cmd = dolls.draw(atlas, parts, cx - s / 2, top, s, tint, alpha, angle)
            if cmd is not None:
                canvas.under(cmd)
            if f.concentration is not None and gfx.ambient:
                canvas.under(Image("bglow", _glow_image, (cx - s * 0.5, fy - s * 1.1, s, s), rgba=(190, 150, 255, 46)))
            if not unseen:
                self._label(canvas, battle, f, cx, fy, s, ov)
            px, py = self.sq_px(x, y)
            self.cells[f.id] = (int(px // cw), int(py // ch), max(1, int(s // cw)), max(1, int(s // ch)))

    def _label(self, canvas, battle, f, cx, fy, s, ov) -> None:
        from realmwalker.ui import colors

        if f.state in ("dead", "fled"):
            return
        T = self.T
        ratio = f.hp / max(1, f.max_hp)
        bar_color = colors.named("good" if ratio > 0.6 else ("warn" if ratio > 0.3 else "danger"))
        bw = s * 0.8
        canvas.over(*theme.bar(cx - bw / 2, fy - s - 5, bw, max(3, T // 10), ratio, bar_color))
        if T >= 24:
            self._statuses(canvas, battle, f, cx, fy - s - 7)
        show_name = f.id in (ov.get("named") or ()) or f.id == ov.get("current") or f.id == ov.get("target")
        if show_name and T >= 24:
            color = (150, 220, 130) if f.side == "party" else (236, 120, 100)
            canvas.over(Text(cx, fy - s - 7, f.name, "prose_bold", max(12, min(16, T // 3)), (*color, 255), anchor="mb",
                             outline=True, shadow=False))
        tag = None
        if f.state == "down":
            tag = ("stable" if f.stable else f"dying {f.death_saves[1]}/3", (255, 110, 90))
        elif f.state == "surrendered":
            tag = ("yields", (200, 200, 190))
        elif f.state == "fleeing":
            tag = ("flees", (230, 200, 120))
        else:
            c = next((c for c in TAGS if c in f.conditions), None)
            if c is not None:
                tag = (TAGS[c], (230, 200, 150))
        if tag is not None and T >= 24:  # one short word, small enough to sit under its own square
            canvas.over(Text(cx, fy - 1, tag[0], "prose_bold", max(10, min(13, T // 4)), (*tag[1], 255), anchor="mb",
                             outline=True, shadow=False))

    def _statuses(self, canvas, battle, f, cx: float, bottom: float) -> None:
        """A row of status icons above the health bar: up to four, then "+N" (rules/describe.statuses)."""
        from realmwalker.rules import describe

        sts = describe.statuses(f, battle)
        if not sts:
            return
        k = 2 if self.T >= 40 else 1  # whole multiples of the 10-pixel pictograms
        size = 10 * k
        shown = sts[:STATUS_ROW]
        extra = len(sts) - len(shown)
        width = len(shown) * (size + 1) + (size if extra else 0)
        x0 = cx - width / 2
        top = bottom - size
        rects = []
        for i, st in enumerate(shown):
            px = round(x0 + i * (size + 1))
            canvas.over(Sprite(st.icon, px, round(top), size, size))
            rects.append(((px, top, size, size), st))
        if extra:
            canvas.over(Text(x0 + len(shown) * (size + 1) + 1, bottom, f"+{extra}", "prose_bold", max(10, size - 2),
                             (230, 220, 200, 255), anchor="lb", outline=True, shadow=False))
        self.status_px[f.id] = rects

    def _effects(self, canvas, now: float) -> None:
        atlas = canvas.gfx.atlas
        T = self.T
        for e in self.fx:
            if now < e["t0"]:
                continue
            p = (now - e["t0"]) / e["dur"]
            if p > 1:
                continue
            k = e["kind"]
            if k == "shot":
                a, b = self._centre(e["from"], now), self._centre(e["to"], now)
                if a is None or b is None:
                    continue
                (ax, ay), (bx, by) = a, b
                lift = e.get("curve", 14)
                px_, py_ = ax + (bx - ax) * p, ay + (by - ay) * p - math.sin(math.pi * p) * lift
                ang = math.degrees(math.atan2(by - ay, bx - ax))
                sz = max(20, T * 0.8)
                name = e["sprite"]
                base = name.rsplit("_", 1)[0]
                if len(atlas.family(base)) == 8:  # pictures for eight directions: 0 points north, 2 east...
                    name = f"{base}_{int(round((ang + 90) / 45.0)) % 8}"
                elif atlas.family(base) and not atlas.has(name):
                    fam = atlas.family(base)
                    name = fam[int(now * 10) % len(fam)]
                if atlas.has(name):
                    canvas.over(Sprite(name, px_ - sz / 2, py_ - sz / 2, sz, sz))
                else:
                    canvas.over(Image("bspark", _glow_image, (px_ - 10, py_ - 10, 20, 20), rgba=(255, 230, 160, 255)))
            elif k == "beam":
                a, b = self._centre(e["from"], now), self._centre(e["to"], now)
                if a is None or b is None:
                    continue
                r, g, bl = e["color"]
                fade = int(255 * (1 - p) ** 0.6)
                canvas.over(Lines([a, b], max(6, T * 0.3), (r, g, bl, fade // 3)))
                canvas.over(Lines([a, b], max(2, T * 0.1), (min(255, r + 60), min(255, g + 60), min(255, bl + 60), fade)))
            elif k == "bead":
                (ax, ay), (bx, by) = self.sq_px(*e["from"]), self.sq_px(*e["to"])
                px_, py_ = ax + (bx - ax) * p, ay + (by - ay) * p - math.sin(math.pi * p) * T
                r, g, bl = e["color"]
                canvas.over(Image("bglow", _glow_image, (px_ - T * 0.5, py_ - T * 0.5, T, T), rgba=(r, g, bl, 220)))
                fam = atlas.family(e["sprite"])
                if fam:
                    canvas.over(Sprite(fam[int(now * 12) % len(fam)], px_ - T * 0.35, py_ - T * 0.35, T * 0.7, T * 0.7))
            elif k == "bolt":
                (ax, ay), (bx, by) = self.sq_px(*e["from"]), self.sq_px(*e["to"])
                r, g, bl = e["color"]
                fade = int(255 * (1 - p))
                pts = [(ax, ay)]
                n = 9
                seed = e["seed"] + int(now * 20)
                for i in range(1, n):
                    t = i / n
                    jitter = math.sin(seed * 12.9898 + i * 78.233) * T * 0.35
                    nx, ny = -(by - ay), bx - ax
                    ln = math.hypot(nx, ny) or 1.0
                    pts.append((ax + (bx - ax) * t + nx / ln * jitter, ay + (by - ay) * t + ny / ln * jitter))
                pts.append((bx, by))
                canvas.over(Lines(pts, max(8, T * 0.4), (r, g, bl, fade // 3)))
                canvas.over(Lines(pts, max(2, T * 0.1), (255, 255, 255, fade)))
            elif k == "flash":
                cx, cy = self.sq_px(*e["at"])
                rad = e["radius"] * T * (0.4 + 0.8 * min(1.0, p * 2))
                r, g, bl = e["color"]
                canvas.over(Image("bburst", _burst_image, (cx - rad, cy - rad, rad * 2, rad * 2),
                                  rgba=(r, g, bl, int(230 * (1 - p) ** 0.8))))
            elif k == "shock":
                cx, cy = self.sq_px(*e["at"])
                rad = e["radius"] * T * (0.3 + 1.0 * p)
                r, g, bl = e["color"]
                canvas.over(Image("bring2", _ring_image, (cx - rad, cy - rad, rad * 2, rad * 2),
                                  rgba=(r, g, bl, int(230 * (1 - p)))))
            elif k == "cell":
                x, y = e["at"]
                px, py = self.sq_px(x, y)
                fam = atlas.family(e["sprite"]) or ([e["sprite"]] if atlas.has(e["sprite"]) else [])
                r, g, bl = e["color"]
                canvas.over(Rect(px, py, T, T, (r, g, bl, int(110 * (1 - p)))))
                if fam:
                    name = fam[min(len(fam) - 1, int(p * len(fam)))]
                    s = T * (0.8 + 0.4 * p)
                    canvas.over(Sprite(name, px + (T - s) / 2, py + (T - s) / 2, s, s, (255, 255, 255, int(255 * (1 - p) ** 0.7))))
            elif k == "puff":
                x, y = e["at"]
                px, py = self.sq_px(x, y)
                s = T * (0.6 + 0.8 * p)
                r, g, bl = e["color"]
                canvas.over(Image("bglow", _glow_image, (px + (T - s) / 2, py + (T - s) / 2, s, s), rgba=(r, g, bl, int(220 * (1 - p)))))
            elif k == "zone_in":
                for (x, y) in e["cells"]:
                    px, py = self.sq_px(x, y)
                    canvas.over(Rect(px, py, T, T, (255, 255, 255, int(80 * (1 - p)))))
            elif k == "float" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                rise = 36 * (1 - (1 - p) ** 2)
                a = int(255 * (1 - max(0.0, (p - 0.55) / 0.45)))
                y0 = fy - s * (0.45 if e.get("low") else 1.0) - 8 - rise
                canvas.over(Text(cx + 6, y0, e["text"], "heading", e.get("size", 20), (*e["color"], a), anchor="mb",
                                 outline=True, shadow=False))
            elif k == "burst" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                frames = atlas.family(e["sprite"]) or ([e["sprite"]] if atlas.has(e["sprite"]) else [])
                if not frames:
                    continue
                name = frames[min(len(frames) - 1, int(p * len(frames)))]
                kk = (0.5 if e.get("small") else 0.9) * s * (0.8 + 0.4 * p)
                a = int(255 * (1 - p) ** 0.7)
                canvas.over(Sprite(name, cx - kk / 2, fy - s * 0.55 - kk / 2, kk, kk, (255, 255, 255, a)))
            elif k == "glow" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                a = int(220 * math.sin(math.pi * p))
                r, g, bl = e.get("color", (190, 150, 255))
                canvas.under(Image("bglow", _glow_image, (cx - s * 0.7, fy - s * 1.15, s * 1.4, s * 1.4), rgba=(r, g, bl, a)))
            elif k == "ring" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                rad = s * (0.4 + 0.5 * p)
                r, g, bl = e["color"]
                canvas.over(Image("bring2", _ring_image, (cx - rad, fy - s * 0.5 - rad * 0.5, rad * 2, rad),
                                  rgba=(r, g, bl, int(220 * (1 - p)))))

    def _centre(self, fid, now):
        f = self._fighters.get(fid)
        if f is None:
            return None
        cx, fy, s = self.place(f, now)
        return cx, fy - s * 0.55


def _figure(f, game, atlas) -> list:
    if f.char is not None:
        return dolls.character(f.char, game.tables, atlas=atlas)
    return dolls.creature(f.creature.def_id, game.tables, f"foe{f.id}", atlas, sex=getattr(f.creature, "sex", ""))


def _missile(weapon: str, kind: str, dtype: str) -> str:
    w = weapon.lower()
    if kind.startswith("spell"):
        return MAGIC_FX.get(dtype, "fx/magic") + "_0"
    if "crossbow" in w or "bolt" in w:
        return "fx/bolt_2"
    if "javelin" in w or "spear" in w:
        return "fx/javelin_2"
    if "sling" in w:
        return "fx/shot_2"
    if "dart" in w or "knife" in w or "dagger" in w or "axe" in w or "hammer" in w:
        return "fx/dart_2"
    return "fx/arrow_2"


# ---------------------------------------------------------------------------- small pictures made by code
def _shadow_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 6, 88, 26], fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(4))


def _ring_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 64), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 6, 120, 58], outline=(255, 255, 255, 255), width=5)
    return im.filter(ImageFilter.GaussianBlur(1.5))


def _blood_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([10, 6, 70, 24], fill=(255, 255, 255, 220))
    d.ellipse([50, 10, 90, 22], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(1.5))


def _glow_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([16, 16, 112, 112], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(14))


def _burst_image():
    """A blast seen from above: white-hot at the heart, ragged at the rim."""
    s = 128
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2) / (s / 2)
    ang = np.arctan2(yy - s / 2, xx - s / 2)
    rim = 0.82 + 0.1 * np.sin(ang * 7) + 0.06 * np.sin(ang * 13 + 1.0)
    a = np.clip((rim - d) / 0.35, 0, 1)
    core = np.clip(1 - d / 0.5, 0, 1)
    out = np.zeros((s, s, 4), np.uint8)
    out[..., 0] = 255
    out[..., 1] = (200 + 55 * core).astype(np.uint8)
    out[..., 2] = (160 + 95 * core).astype(np.uint8)
    out[..., 3] = (255 * a).astype(np.uint8)
    return out


def _fog_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for (x, y, r) in ((22, 26, 16), (40, 30, 15), (30, 40, 14), (34, 22, 12)):
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 150))
    return im.filter(ImageFilter.GaussianBlur(6))


def _web_image():
    """A web across a square, in sharp single pixels: spokes from the middle and three rings of thread."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s / 2
    spokes = 8
    pts = []
    for k in range(spokes):
        ang = k * 2 * math.pi / spokes + 0.2
        pts.append((c + math.cos(ang) * c, c + math.sin(ang) * c))
        d.line([(c, c), pts[-1]], fill=(255, 255, 255, 200), width=1)
    for ring in (0.3, 0.55, 0.85):
        ring_pts = [(c + (p[0] - c) * ring, c + (p[1] - c) * ring) for p in pts]
        d.line(ring_pts + [ring_pts[0]], fill=(255, 255, 255, 170), width=1)
    return im


def _ice_image():
    """Hailstones and a skin of ice on the ground, in sharp pixels."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(5)
    d.rectangle([0, 0, s, s], fill=(200, 230, 255, 60))
    for _ in range(9):
        x, y = rng.integers(2, s - 4, 2)
        d.polygon([(x, y), (x + 3, y + 1), (x + 1, y + 3)], fill=(240, 250, 255, 230))
    for _ in range(4):
        x, y = rng.integers(0, s - 8, 2)
        d.line([(x, y), (x + 7, y + 3)], fill=(255, 255, 255, 160), width=1)
    return im
