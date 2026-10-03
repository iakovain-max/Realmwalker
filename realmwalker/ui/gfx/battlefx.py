"""The battle drawn as a stage: both sides as figures on the ground where the fight is, and what happens shown as it
happens: a lunge, an arrow in flight, a spell, a hit that flashes and shakes, the damage rising off the wounded, a
miss, a healing glow, the fallen going down.

The rules (rules/combat.Battle) write a list of events; this reads the new ones each frame and turns them into
short effects. Nothing here changes the fight. With animations off, figures simply stand and fall.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.ui.gfx import dolls, theme
from realmwalker.ui.gfx.scene import Image, Rect, Sprite, Text, tile_batch

LUNGE = 0.26
FLIGHT = 0.24
FLOAT = 1.1
FALL = 0.4
STAGGER = 0.32  # one blow after another in the same moment
MAGIC_FX = {"fire": "fx/fire", "cold": "fx/cold", "poison": "fx/poison", "necrotic": "fx/drain", "radiant": "fx/glow",
            "force": "fx/magic", "lightning": "fx/storm", "thunder": "fx/storm", "acid": "fx/poison", "psychic": "fx/drain"}


class BattleStage:
    def __init__(self) -> None:
        self.seen = 0
        self.fx: list[dict] = []
        self.prev: dict[int, tuple[str, int]] = {}
        self.fell: dict[int, float] = {}  # fighter -> when they went down (for the fall)
        self.pos: dict[int, tuple[float, float, float]] = {}  # fighter -> (centre x, feet y, size)
        self.cells: dict[int, tuple[int, int, int, int]] = {}  # fighter -> cell rect (for clicks)
        self.busy_until = 0.0

    # ------------------------------------------------------------------ what happened
    def feed(self, battle, now: float, animate: bool) -> None:
        events = battle.events[self.seen:]
        self.seen = len(battle.events)
        t = max(now, self.busy_until - STAGGER if self.busy_until > now else now)
        for ev in events if animate else []:
            k = ev["kind"]
            if k == "attack":
                a, b = ev["by"], ev["to"]
                if ev.get("melee"):
                    self.fx.append({"kind": "lunge", "who": a, "at": b, "t0": t, "dur": LUNGE})
                    impact = t + LUNGE * 0.5
                else:
                    self.fx.append({"kind": "shot", "from": a, "to": b, "t0": t, "dur": FLIGHT,
                                    "sprite": _missile(ev.get("weapon", ""), ev.get("how", ""), ev.get("dtype", ""))})
                    impact = t + FLIGHT
                if not ev.get("hit"):
                    self.fx.append({"kind": "float", "who": b, "text": "miss", "color": (190, 186, 176), "t0": impact,
                                    "dur": FLOAT, "size": 17})
                    self.fx.append({"kind": "dodge", "who": b, "t0": impact, "dur": 0.25})
                self._impact = impact
                t += STAGGER
            elif k == "damage":
                at = getattr(self, "_impact", t)
                if at < now - 0.05:
                    at = t
                crit = ev.get("crit")
                try:
                    hurt_party = battle.fighter(ev["to"]).side == "party"
                except StopIteration:
                    hurt_party = False
                text = f"{ev['amount']}"
                color = (255, 220, 120) if crit else ((255, 120, 96) if hurt_party else (255, 236, 220))
                self.fx.append({"kind": "hit", "who": ev["to"], "t0": at, "dur": 0.28, "crit": crit})
                self.fx.append({"kind": "float", "who": ev["to"], "text": ("crit! " if crit else "") + text,
                                "color": color, "t0": at, "dur": FLOAT, "size": 24 if crit else 20})
                spark = MAGIC_FX.get(ev.get("dtype", ""))
                if spark:
                    self.fx.append({"kind": "burst", "who": ev["to"], "sprite": spark, "t0": at, "dur": 0.45})
                elif ev.get("dtype") in ("slashing", "piercing", "bludgeoning"):
                    self.fx.append({"kind": "burst", "who": ev["to"], "sprite": "fx/blood", "t0": at, "dur": 0.4,
                                    "small": True})
                self._impact = at
            elif k == "immune":
                self.fx.append({"kind": "float", "who": ev["to"], "text": "unharmed", "color": (170, 170, 190),
                                "t0": getattr(self, "_impact", t), "dur": FLOAT, "size": 16})
            elif k == "heal":
                self.fx.append({"kind": "burst", "who": ev["to"], "sprite": "fx/sparkle", "t0": t, "dur": 0.6})
                self.fx.append({"kind": "float", "who": ev["to"], "text": f"+{ev['amount']}", "color": (140, 230, 120),
                                "t0": t, "dur": FLOAT, "size": 20})
            elif k == "cast":
                self.fx.append({"kind": "glow", "who": ev["by"], "t0": t, "dur": 0.45})
                t += 0.15
        end = max([f["t0"] + f["dur"] * (0.55 if f["kind"] == "float" else 1.0) for f in self.fx] + [now])
        self.busy_until = end
        # Who went down, died or ran since last time.
        for f in battle.fighters:
            state = f.state
            old = self.prev.get(f.id)
            if old is not None and old[0] != state and state in ("down", "dead"):
                self.fell[f.id] = max(now, getattr(self, "_impact", now)) if animate else now - FALL
            if state == "fighting" and f.id in self.fell:
                del self.fell[f.id]
            self.prev[f.id] = (state, f.hp)
        self.fx = [e for e in self.fx if e["t0"] + e["dur"] > now - 0.05]

    def busy(self, now: float) -> bool:
        return now < self.busy_until

    # ------------------------------------------------------------------ where everyone stands
    def layout(self, battle, rect, size: float) -> None:
        from realmwalker.rules.combat import BACK, FOE, FRONT, PARTY

        x, y, w, h = rect
        ground = y + h * 0.80
        columns = {(PARTY, BACK): 0.12, (PARTY, FRONT): 0.32, (FOE, FRONT): 0.68, (FOE, BACK): 0.88}
        self.pos = {}
        for (side, rank), fx_ in columns.items():
            members = [f for f in battle.side(side) if f.rank == rank and f.state != "fled"]
            members.sort(key=lambda f: f.id)  # everyone keeps their spot, standing or fallen
            n = len(members)
            if not n:
                continue
            depth = min(size * 0.55, (h * 0.62) / max(1, n))
            for i, f in enumerate(members):
                row = i  # nearer ones lower on the screen, further ones higher and a little smaller
                far = 1.0 - 0.06 * min(row, 5)
                cx = x + w * fx_ + (size * 0.28 * (1 if (row % 2) else -1) if n > 1 else 0) * (1 if side == PARTY else -1)
                fy = ground - row * depth
                self.pos[f.id] = (cx, fy, size * far)

    def place(self, fid: int, now: float) -> tuple[float, float, float]:
        """Where a fighter is drawn now: their spot, moved by any lunge, shake or dodge."""
        cx, fy, size = self.pos.get(fid, (0, 0, 0))
        for e in self.fx:
            if now < e["t0"] or now > e["t0"] + e["dur"]:
                continue
            p = (now - e["t0"]) / e["dur"]
            if e["kind"] == "lunge" and e["who"] == fid and e["at"] in self.pos:
                tx, ty, _ = self.pos[e["at"]]
                k = math.sin(math.pi * p) * 0.42
                cx += (tx - cx) * k
                fy += (ty - fy) * k
            elif e["kind"] == "hit" and e["who"] == fid:
                amp = (6 if e.get("crit") else 3.5) * (1 - p)
                cx += math.sin(p * 40) * amp
            elif e["kind"] == "dodge" and e["who"] == fid:
                cx += math.sin(math.pi * p) * size * 0.12
        return cx, fy, size

    # ------------------------------------------------------------------ drawing
    def draw(self, canvas, game, battle, rect, now: float, *, current=None, targets=(), target=None,
             hover=None) -> None:
        gfx = canvas.gfx
        atlas = gfx.atlas
        x, y, w, h = rect
        size = float(32 * max(2, min(4, int(h * 0.30) // 32)))  # whole multiples of the 32-pixel figures stay sharp
        self.layout(battle, rect, size)
        self._backdrop(canvas, game, rect)
        order = sorted(self.pos.items(), key=lambda kv: kv[1][1])
        for fid, _ in order:
            f = battle.fighter(fid)
            cx, fy, s = self.place(fid, now)
            names = _figure(f, game)
            tint = (255, 255, 255)
            alpha = 255
            flash = next((e for e in self.fx if e["kind"] == "hit" and e["who"] == fid and e["t0"] <= now <= e["t0"] + e["dur"]),
                         None)
            if flash is not None:
                p = (now - flash["t0"]) / flash["dur"]
                tint = (255, int(120 + 135 * p), int(110 + 145 * p))
            if f.state == "surrendered":
                tint = (170, 170, 170)
            angle = 0.0
            if fid in self.fell:
                p = min(1.0, max(0.0, (now - self.fell[fid]) / FALL)) if gfx.animate else 1.0
                angle = -90.0 * (p * p) if f.side != "party" else 90.0 * (p * p)
                if f.state == "dead":
                    alpha = int(255 - 120 * p)
                    tint = tuple(int(c * (1 - 0.35 * p)) for c in tint)
            # Ground glow: whose turn it is, who can be chosen, who is chosen.
            ring = None
            if target is not None and fid == target.id:
                pulse = 0.5 + 0.5 * math.sin(now * 7) if gfx.ambient else 1.0
                ring = (255, 90, 60, int(150 + 100 * pulse))
            elif fid in targets:
                ring = (230, 120, 80, 120)
            elif current is not None and fid == current.id and battle.outcome is None:
                ring = (255, 214, 110, 220)
            elif hover == fid:
                ring = (255, 255, 255, 90)
            bob = math.sin(now * 3.0) * 2 if (current is not None and fid == current.id and gfx.ambient and angle == 0) else 0
            canvas.under(Image("bshadow", _shadow, (cx - s * 0.36, fy - s * 0.12, s * 0.72, s * 0.24), rgba=(255, 255, 255, 170)))
            if ring:
                canvas.under(Image("bring", _ring, (cx - s * 0.5, fy - s * 0.2, s, s * 0.4), rgba=ring))
            if f.state == "dead" and fid in self.fell:
                canvas.under(Image("blood", _blood, (cx - s * 0.4, fy - s * 0.1, s * 0.8, s * 0.22),
                                   rgba=(140, 20, 16, 170)))
            top = fy - s * 0.85 if angle else fy - s + bob
            cmd = dolls.draw(atlas, names, cx - s / 2, top, s, tuple(c / 255 for c in tint), alpha / 255, angle)
            if cmd is not None:
                canvas.under(cmd)
            self._label(canvas, battle, f, cx, fy, s)
            # The cells it covers, for clicks.
            cw, ch = canvas.cell_w, canvas.cell_h
            self.cells[fid] = (int((cx - s / 2) // cw), int((fy - s) // ch), max(1, int(s // cw)), max(1, int((s + 34) // ch)))
        self._effects(canvas, now)

    def _label(self, canvas, battle, f, cx, fy, s) -> None:
        from realmwalker.ui import colors

        known = f.side == "party" or (f.creature is not None and f.creature.def_id in battle.known)
        color = (150, 220, 130) if f.side == "party" else (236, 120, 100)
        if not f.active and f.state != "down":
            color = (130, 126, 120)
        canvas.over(Text(cx, fy + 4, f.name, "prose_bold", 15, (*color, 255), anchor="mt", outline=True, shadow=False))
        bw = s * 0.9
        ratio = f.hp / max(1, f.max_hp)
        bar_color = colors.named("good" if ratio > 0.6 else ("warn" if ratio > 0.3 else "danger"))
        if f.state in ("dead", "fled"):
            return
        canvas.over(*theme.bar(cx - bw / 2, fy + 22, bw, 7, ratio, bar_color))
        if known:
            canvas.over(Text(cx, fy + 31, f"{f.hp}/{f.max_hp}", "mono", 11, (210, 204, 190, 230), anchor="mt",
                             outline=True, shadow=False))
        if f.state == "down":
            canvas.over(Text(cx, fy - s - 4, "down" if not f.stable else "down · stable", "prose_bold", 14,
                             (255, 110, 90, 255), anchor="mb", outline=True, shadow=False))

    def _effects(self, canvas, now: float) -> None:
        atlas = canvas.gfx.atlas
        for e in self.fx:
            if now < e["t0"]:
                continue
            p = (now - e["t0"]) / e["dur"]
            if p > 1:
                continue
            if e["kind"] == "shot" and e["from"] in self.pos and e["to"] in self.pos:
                ax, ay, as_ = self.place(e["from"], now)
                bx, by, bs = self.place(e["to"], now)
                ay -= as_ * 0.55
                by -= bs * 0.55
                px_, py_ = ax + (bx - ax) * p, ay + (by - ay) * p - math.sin(math.pi * p) * 18
                ang = math.degrees(math.atan2(by - ay, bx - ax))
                sz = 30
                name = e["sprite"]
                base = name.rsplit("_", 1)[0]
                if len(atlas.family(base)) == 8:  # pictures for eight directions: 0 points north, 2 east...
                    name = f"{base}_{int(round((ang + 90) / 45.0)) % 8}"
                if atlas.has(name):
                    canvas.over(Sprite(name, px_ - sz / 2, py_ - sz / 2, sz, sz))
                else:
                    canvas.over(Image("spark", _spark, (px_ - 8, py_ - 8, 16, 16), rgba=(255, 230, 160, 255)))
            elif e["kind"] == "float" and e["who"] in self.pos:
                cx, fy, s = self.place(e["who"], now)
                rise = 40 * (1 - (1 - p) ** 2)
                a = int(255 * (1 - max(0.0, (p - 0.55) / 0.45)))
                canvas.over(Text(cx + 8, fy - s - 6 - rise, e["text"], "heading", e.get("size", 20), (*e["color"], a),
                                 anchor="mb", outline=True, shadow=False))
            elif e["kind"] == "burst" and e["who"] in self.pos:
                cx, fy, s = self.place(e["who"], now)
                frames = atlas.family(e["sprite"]) or ([e["sprite"]] if atlas.has(e["sprite"]) else [])
                if not frames:
                    continue
                name = frames[min(len(frames) - 1, int(p * len(frames)))]
                k = (0.5 if e.get("small") else 0.9) * s * (0.8 + 0.4 * p)
                a = int(255 * (1 - p) ** 0.7)
                canvas.over(Sprite(name, cx - k / 2, fy - s * 0.55 - k / 2, k, k, (255, 255, 255, a)))
            elif e["kind"] == "glow" and e["who"] in self.pos:
                cx, fy, s = self.place(e["who"], now)
                a = int(220 * math.sin(math.pi * p))
                canvas.under(Image("glow", _glow, (cx - s * 0.7, fy - s * 1.1, s * 1.4, s * 1.4), rgba=(190, 150, 255, a)))

    def _backdrop(self, canvas, game, rect) -> None:
        """Where the fight is: the sky and the ground you stand on (or a vault of stone underground)."""
        x, y, w, h = rect
        lm = game.local
        under = lm is not None and lm.kind == "dungeon"
        light = 0.0 if under else float(game.light)
        if under:
            canvas.under(Rect(x, y, w, h, (16, 14, 18, 255), bottom=(30, 26, 26, 255)))
            wall = "wall/cave" if lm.meta.get("style") in ("cave", "lair", "warren", "hideout") else "wall/stone"
            floor = "floor/rough" if "cave" in wall else "floor/flagstone"
            self._tiles(canvas, wall, x, y + h * 0.08, w, h * 0.30, 0.42)
            self._tiles(canvas, floor, x, y + h * 0.38, w, h * 0.62, 0.55)
        else:
            day = (96, 118, 140)
            night = (16, 20, 38)
            k = max(0.0, min(1.0, (light - 0.2) / 0.7))
            sky = tuple(int(n + (d - n) * k) for n, d in zip(night, day))
            canvas.under(Rect(x, y, w, h * 0.45, (*tuple(int(c * 0.7) for c in sky), 255), bottom=(*sky, 255)))
            canvas.under(Image(("hills", int(w), int(h)), lambda: _hills(int(w), int(h * 0.2)),
                               (x, y + h * 0.27, w, h * 0.2), rgba=(*tuple(int(60 + 120 * k) for _ in range(3)), 255)))
            ground = "floor/grass"
            if lm is not None:
                t = game.tables.terrain.ids[int(game.remap_for(lm)[lm.terrain[game.player.lx, game.player.ly]])]
                ground = game.tables.sprites["terrain"].get(t, {}).get("ground") or ground
            elif game.world.road[game.player.x, game.player.y]:
                ground = "floor/dirt"
            else:
                key = game.biome_key(game.player.x, game.player.y)
                ground = {"desert": "floor/sand", "coast": "floor/sand", "tundra": "floor/snow", "high_mountains": "floor/snow",
                          "mountains": "floor/rock", "marsh": "floor/swamp", "pine_forest": "floor/dirt",
                          "hills": "floor/heath"}.get(key, "floor/grass")
            self._tiles(canvas, ground, x, y + h * 0.42, w, h * 0.58, 0.45 + 0.55 * k)
            # Distance: the ground fades into haze towards the hills.
            canvas.under(Rect(x, y + h * 0.42, w, h * 0.22, (*tuple(int(c * 0.8) for c in sky), 150),
                              bottom=(*tuple(int(c * 0.8) for c in sky), 0)))
        canvas.under(Image("vignette", _vignette, (x, y, w, h), rgba=(255, 255, 255, 255)))

    def _tiles(self, canvas, family: str, x, y, w, h, light: float) -> None:
        atlas = canvas.gfx.atlas
        names = atlas.family(family)
        if not names:
            return
        t = 40
        cols, rows = int(w // t) + 1, int(h // t) + 1
        dst, picks = [], []
        for j in range(rows):
            for i in range(cols):
                picks.append(names[(i * 7 + j * 13) % len(names)])
                dst.append((x + i * t, y + j * t, t, t))
        from realmwalker.ui.gfx.scene import Clip

        c = np.full((len(dst), 4), light, np.float32)
        c[:, 3] = 1.0
        canvas.under(Clip((int(x), int(y), int(w), int(h))))
        canvas.under(*tile_batch(atlas, picks, np.array(dst, np.float32), c))
        canvas.under(Clip(None))


def _figure(f, game) -> list:
    if f.char is not None:
        return dolls.character(f.char, game.tables)
    return dolls.creature(f.creature.def_id, game.tables, f"foe{f.id}", sex=getattr(f.creature, "sex", ""))


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
    if "dart" in w or "knife" in w or "dagger" in w or "axe" in w:
        return "fx/dart_2"
    return "fx/arrow_2"


# ---------------------------------------------------------------------------- small pictures
def _shadow():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 6, 88, 26], fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(4))


def _ring():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 52), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 6, 120, 46], outline=(255, 255, 255, 255), width=5)
    return im.filter(ImageFilter.GaussianBlur(2))


def _blood():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([10, 6, 70, 24], fill=(255, 255, 255, 220))
    d.ellipse([50, 10, 90, 22], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(1.5))


def _spark():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 8, 24, 24], fill=(255, 255, 255, 255))
    return im.filter(ImageFilter.GaussianBlur(3))


def _glow():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([16, 16, 112, 112], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(14))


def _hills(w: int, h: int):
    from PIL import Image as PImage, ImageDraw

    im = PImage.new("RGBA", (max(8, w), max(8, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(0, h)]
    for i in range(0, w + 40, 40):
        pts.append((i, h * (0.35 + 0.25 * math.sin(i / 97.0) + 0.15 * math.sin(i / 31.0 + 1.3))))
    pts.append((w, h))
    d.polygon(pts, fill=(54, 62, 58, 255))
    return im


def _vignette():
    a = np.zeros((128, 256, 4), np.uint8)
    yy, xx = np.mgrid[0:128, 0:256]
    d = np.sqrt(((xx - 128) / 128.0) ** 2 + ((yy - 64) / 64.0) ** 2)
    a[..., 3] = (np.clip(d - 0.55, 0, 1) * 230).astype(np.uint8)
    return a
