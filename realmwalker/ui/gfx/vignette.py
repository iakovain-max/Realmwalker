"""Pictures for stories (Expansion 6 B.2, docs/ADVENTURES.md §8.12): a small scene painted from a spec, above a beat's
words, an event on the road, a chapter's title card or an epilogue page. Show, don't tell.

    compose(canvas, rect, spec, now, game=None)   paint it in a pixel rect
    for_place(game, place)                         the backdrop for a story's place ({"site"|"settlement"|"tile"})
    BACKDROPS                                      the sixteen kinds

A spec is {"backdrop": kind, "time": "day"|"dusk"|"night"|"dawn" (else the hour's light), "props": [sprite names],
"figures": [doll parts lists], "fire": bool, "atmosphere": "mist"|"embers"|"ash"|"haze", "pan": bool}, or simply a
backdrop's name. The far ground (roofs, hills, tents, ruined walls) is painted once for its kind, size and seed and
kept (the titleart way); the near ground is the game's own tiles; props, figures, fire and the air are drawn every
frame, so they move.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from realmwalker.ui.gfx import dolls, theme
from realmwalker.ui.gfx.scene import Clip, Image, Rect, Sprite, tile_batch

# kind: what lies far off, the ground, a near wall (indoors) or a row of house fronts, its own props and trees, its fire
# and its air. "sky": False for rooms.
BACKDROPS = {
    "street": {"far": "roofs", "ground": "floor/cobble", "fronts": "wall/plaster", "props": ["feature/lamp_post",
               "feature/barrels"], "sky": True},
    "square": {"far": "roofs", "ground": "floor/flags", "props": ["feature/well", "feature/notice_board",
               "feature/stall"], "sky": True},
    "inn": {"ground": "floor/planks", "wall": "wall/wood", "props": ["feature/table", "feature/barrels",
            "feature/hearth"], "fire": True, "sky": False},
    "hall": {"ground": "floor/flagstone", "wall": "wall/stone", "props": ["feature/throne", "feature/tapestry",
             "feature/column"], "sky": False},
    "camp": {"far": "hills", "ground": "floor/grass", "props": ["feature/bedroll"], "fire": True, "sky": True,
             "trees": "tree/pine", "time": "night"},
    "road": {"far": "hills", "ground": "floor/dirt", "props": ["feature/cart"], "trees": "tree/oak", "sky": True},
    "ford": {"far": "hills", "ground": "floor/mud", "water": True, "props": ["feature/rock"], "trees": "tree/birch",
             "sky": True},
    "barrow": {"far": "hills", "near": "mound", "ground": "floor/heath", "props": ["feature/standing_stone", "feature/bones"],
               "trees": "tree/dead", "sky": True, "atmosphere": "mist"},
    "ruin": {"far": "ruins", "ground": "floor/rough", "props": ["feature/column", "feature/rock"],
             "trees": "tree/dead", "sky": True},
    "battlefield": {"far": "hills", "ground": "floor/mud", "props": ["feature/standard", "feature/bones",
                    "feature/weapon_rack"], "trees": "tree/dead", "sky": True, "atmosphere": "haze"},
    "burned_street": {"far": "burnt", "ground": "floor/ash", "fronts": "wall/brick_dark", "props": ["feature/cart"],
                      "sky": True, "atmosphere": "embers", "smoke": True},
    "rift": {"far": "rift", "ground": "floor/volcanic", "props": ["feature/skull_post", "feature/bones"],
             "sky": True, "atmosphere": "ash", "time": "dusk"},
    "crusader_camp": {"far": "tents", "ground": "floor/drygrass", "props": ["feature/standard", "feature/banner",
                      "feature/weapon_rack"], "fire": True, "sky": True},
    "sickroom": {"ground": "floor/planks_dark", "wall": "wall/white", "props": ["feature/bed", "feature/candles",
                 "feature/stool"], "sky": False},
    # Expansion 6 D.5: the outlaws' hideout (their camp under the trees) and the halls under a barrow.
    "hideout": {"far": "hills", "ground": "floor/dirt", "props": ["feature/bedroll", "feature/barrels",
                "feature/weapon_rack", "feature/horse_post", "feature/crates"], "fire": True, "sky": True,
                "trees": "tree/pine", "time": "dusk"},
    "barrow_hall": {"ground": "floor/flagstone", "wall": "wall/stone_gray", "props": ["feature/sarcophagus",
                    "feature/bones", "feature/candles", "feature/skull_post"], "sky": False, "atmosphere": "mist"},
}
SKIES = {"day": ((96, 130, 170), (176, 196, 210)), "dawn": ((70, 74, 110), (220, 160, 120)),
         "dusk": ((40, 36, 70), (190, 104, 70)), "night": ((8, 10, 24), (30, 34, 60))}
HORIZON = 0.55  # the ground begins this far down


def _time(game, spec: dict, kind: dict) -> str:
    if spec.get("time"):
        return spec["time"]
    if kind.get("time"):
        return kind["time"]
    light = float(getattr(game, "light", 1.0)) if game is not None else 1.0
    if light >= 0.8:
        return "day"
    if light >= 0.45:
        return "dusk"
    return "night"


def _lightness(t: str) -> float:
    return {"day": 1.0, "dawn": 0.8, "dusk": 0.7, "night": 0.45}.get(t, 1.0)


# ---------------------------------------------------------------------------- the far ground (painted once)
@lru_cache(maxsize=24)
def _far(what: str, w: int, h: int, seed: int):
    """A silhouette band for the far ground: rooftops and chimneys, hills, a barrow's mound, broken walls, burnt
    rafters, a host's tents, the rift's red crack. White on clear, tinted when drawn."""
    from PIL import Image as PImage, ImageDraw

    rng = np.random.default_rng(seed)
    im = PImage.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    W = (255, 255, 255, 255)
    if what in ("roofs", "burnt"):
        x = -rng.integers(0, 20)
        while x < w:
            bw = int(rng.integers(max(8, w // 14), max(12, w // 6)))
            top = int(h * rng.uniform(0.25, 0.6))
            peak = top - int(bw * rng.uniform(0.25, 0.5))
            if what == "burnt" and rng.random() < 0.6:  # (a roof gone: the rafters stand black against the sky)
                d.rectangle([x, top, x + bw, h], fill=W)
                for i in range(1, 4):
                    rx = x + bw * i // 4
                    d.line([(rx, top), (x + bw // 2, peak)], fill=W, width=max(1, w // 160))
            else:
                d.polygon([(x, top), (x + bw // 2, peak), (x + bw, top), (x + bw, h), (x, h)], fill=W)
                if rng.random() < 0.5:
                    cx = x + int(bw * rng.uniform(0.2, 0.7))
                    d.rectangle([cx, peak + (top - peak) // 3 - h // 10, cx + max(2, w // 90), top], fill=W)
            x += bw + int(rng.integers(0, max(2, w // 40)))
    elif what == "hills":
        xs = np.arange(w)
        base = h * 0.55
        y = base - h * 0.25 * np.abs(np.sin(xs / max(1, w) * math.pi * rng.uniform(1.2, 2.2) + rng.uniform(0, 3)))
        y -= h * 0.08 * np.sin(xs / max(1, w) * math.pi * 7 + rng.uniform(0, 3))
        d.polygon([(0, h)] + [(int(i), int(v)) for i, v in zip(xs[::4], y[::4])] + [(w, int(y[-1])), (w, h)], fill=W)
    elif what == "mound":  # a long barrow: a low green hump with a stone-lined mouth, nearer than the hills
        xs = np.arange(w)
        y = h - h * 0.92 * np.clip(1 - ((xs - w * 0.58) / (w * 0.3)) ** 2, 0, 1) ** 0.6
        d.polygon([(0, h)] + [(int(i), int(v)) for i, v in zip(xs[::2], y[::2])] + [(w, h)], fill=W)
        mx, my = int(w * 0.5), int(h * 0.62)
        mw, mh = max(4, w // 22), max(6, int(h * 0.38))
        d.rectangle([mx - mw - 3, my - 3, mx + mw + 3, h], fill=(150, 150, 150, 255))  # (the stones of its door)
        d.rectangle([mx - mw, my, mx + mw, h], fill=(0, 0, 0, 255))
    elif what == "ruins":
        x = int(rng.integers(0, 20))
        while x < w:
            bw = int(rng.integers(max(6, w // 18), max(10, w // 8)))
            top = int(h * rng.uniform(0.2, 0.7))
            pts = [(x, h), (x, top)]
            for i in range(1, 4):
                pts.append((x + bw * i // 4, top + int(rng.integers(-h // 8, h // 6))))
            pts += [(x + bw, int(h * rng.uniform(0.5, 0.8))), (x + bw, h)]
            d.polygon(pts, fill=W)
            x += bw + int(rng.integers(w // 30, w // 10))
    elif what == "tents":
        x = int(rng.integers(0, 10))
        while x < w:
            tw = int(rng.integers(max(10, w // 16), max(14, w // 9)))
            top = int(h * rng.uniform(0.35, 0.6))
            d.polygon([(x, h), (x + tw // 2, top), (x + tw, h)], fill=W)
            d.line([(x + tw // 2, top), (x + tw // 2, top - h // 8)], fill=W, width=max(1, w // 200))
            x += tw + int(rng.integers(0, w // 30))
        d.rectangle([0, int(h * 0.8), w, h], fill=W)
    elif what == "rift":
        xs = np.arange(w)
        y = h * 0.6 - h * 0.1 * np.abs(np.sin(xs / max(1, w) * math.pi * 3))
        d.polygon([(0, h)] + [(int(i), int(v)) for i, v in zip(xs[::4], y[::4])] + [(w, h)], fill=W)
    return im


def _crack(w: int, h: int):
    """The rift's wound in the sky: a jagged red line, glowing."""
    from PIL import Image as PImage, ImageDraw, ImageFilter

    rng = np.random.default_rng(66)
    im = PImage.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts, x, y = [], w * 0.2, 0.0
    while y < h:
        pts.append((x, y))
        x += rng.uniform(-w * 0.05, w * 0.06)
        y += rng.uniform(h * 0.06, h * 0.14)
    d.line(pts, fill=(255, 255, 255, 255), width=max(2, w // 120))
    return im.filter(ImageFilter.GaussianBlur(1.5))


def _glow():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([16, 16, 112, 112], fill=(255, 255, 255, 210))
    return im.filter(ImageFilter.GaussianBlur(16))


def _speck():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([5, 5, 11, 11], fill=(255, 255, 255, 255))
    return im.filter(ImageFilter.GaussianBlur(1.0))


# ---------------------------------------------------------------------------- composing
def compose(canvas, rect, spec, now: float, game=None) -> bool:
    """Paint the picture in a pixel rect (x, y, w, h). False if the backdrop is not one of BACKDROPS."""
    if isinstance(spec, str):
        spec = {"backdrop": spec}
    kind = BACKDROPS.get(spec.get("backdrop", ""))
    if kind is None:
        return False
    x, y, w, h = (float(v) for v in rect)
    atlas = canvas.gfx.atlas
    animate = canvas.gfx.animate
    ambient = canvas.gfx.ambient
    t = _time(game, spec, kind)
    k = _lightness(t)
    pan = (math.sin(now * 0.12) * w * 0.02) if spec.get("pan") and animate else 0.0
    seed = sum(ord(c) for c in spec.get("backdrop", "")) + int(spec.get("seed", 0))
    canvas.under(Clip((int(x), int(y), int(w), int(h))))
    horizon = y + h * HORIZON
    if kind.get("sky"):
        top, low = SKIES[t]
        canvas.under(Rect(x, y, w, h * HORIZON + 2, (*top, 255), bottom=(*low, 255)))
        if spec.get("backdrop") == "rift":
            canvas.under(Image("vig_crack", lambda: _crack(256, 256), (x + w * 0.45 + pan * 0.3, y, w * 0.3, h * 0.6),
                               rgba=(255, 80, 50, 230)))
        far = kind.get("far")
        if far:
            fw, fh = int(w * 1.1), int(h * 0.35)
            shade = tuple(int(c * 0.45 * k + 6) for c in low)
            if far == "burnt":
                shade = (20, 16, 14)
            canvas.under(Image(("vig_far", far, fw, fh, seed), lambda a=far, b=fw, c=fh, d=seed: _far(a, b, c, d),
                               (x - w * 0.05 + pan * 0.4, horizon - fh + 2, fw, fh), rgba=(*shade, 255)))
        near = kind.get("near")
        if near:
            nw, nh = int(w * 0.9), int(h * 0.3)
            canvas.under(Image(("vig_near", near, nw, nh, seed), lambda a=near, b=nw, c=nh, d=seed: _far(a, b, c, d),
                               (x + w * 0.05 + pan * 0.6, horizon - nh + 4, nw, nh),
                               rgba=(int(52 * k + 8), int(70 * k + 10), int(44 * k + 8), 255)))
    else:  # a room: its back wall fills the top
        wall = atlas.family(kind["wall"]) or [kind["wall"]]
        _tiles(canvas, atlas, wall, x + pan * 0.5, y, w, h * HORIZON + 4, max(24.0, h * 0.18), k * 0.85, seed)
    if kind.get("fronts"):  # a row of house fronts across the middle, doors and dark windows
        fronts = atlas.family(kind["fronts"]) or [kind["fronts"]]
        front_h = h * 0.26
        ft = front_h / 2
        _tiles(canvas, atlas, fronts, x + pan * 0.6, horizon - front_h, w, front_h, ft, k * 0.8, seed)
        house = ft * 3.2
        burned = spec.get("backdrop") == "burned_street"
        for i in range(int(w // house) + 2):
            hx = x + pan * 0.6 + i * house
            canvas.under(Rect(hx, horizon - front_h, ft * 0.12, front_h, (20, 14, 10, 200)))  # (where one ends)
            lit = t in ("night", "dusk") and (i * 7 + seed) % 3 == 0 and not burned
            glass = (236, 180, 90, 235) if lit else (16, 12, 10, 235)
            canvas.under(Rect(hx + house * 0.2, horizon - front_h * 0.8, ft * 0.5, ft * 0.55, glass))
            canvas.under(Rect(hx + house * 0.62, horizon - front_h * 0.62, ft * 0.6, front_h * 0.62,
                              (12, 8, 6, 240) if burned else (58, 38, 24, 245)))
    ground = atlas.family(kind["ground"]) or [kind["ground"]]
    tile = max(24.0, h * 0.16)
    _tiles(canvas, atlas, ground, x, horizon, w, h - h * HORIZON, tile, k, seed + 1)
    if kind.get("water"):  # a ford: the river across the near ground, shining
        names = atlas.family("water/shallow") or atlas.family("water/river") or []
        if names:
            _tiles(canvas, atlas, names, x, horizon + h * 0.14, w, tile, tile, k, seed + 2)
    trees = kind.get("trees")
    if trees and atlas.family(trees):
        tn = atlas.family(trees)
        ts = h * 0.32
        for i, fx in enumerate((0.06, 0.88, 0.95)):
            canvas.under(Sprite(tn[(i + seed) % len(tn)], x + w * fx - ts / 2 + pan * 0.7, horizon - ts * 0.85,
                                ts, ts, _rgba(k * 0.75)))
    props = list(spec.get("props") or kind.get("props", []))
    ps = h * 0.24
    for i, name in enumerate(props):
        fam = atlas.family(name)
        sprite = fam[(i + seed) % len(fam)] if fam else name
        if not atlas.has(sprite):
            continue
        fx = (0.14 + 0.72 * ((i * 0.37 + 0.1) % 1.0))
        py = horizon + h * (0.06 + 0.1 * (i % 2))
        canvas.under(Sprite(sprite, x + w * fx - ps / 2 + pan * 0.8, py - ps * 0.6, ps, ps, _rgba(k)))
    fire = spec.get("fire", kind.get("fire"))
    fx, fy = x + w * 0.5 + pan, y + h * 0.82
    if fire:
        flick = 0.85 + 0.15 * math.sin(now * 11) * math.sin(now * 7.3 + 1) if ambient else 1.0
        g = h * 0.9 * flick
        canvas.under(Image("vig_glow", _glow, (fx - g / 2, fy - g * 0.6, g, g), rgba=(255, 150, 70, int(140 * flick))))
        size = h * 0.22
        frame = int(now * 8) % 3 if ambient else 0
        if kind.get("sky"):
            canvas.under(Sprite(f"feature/campfire_{frame}", fx - size / 2, fy - size * 0.8, size, size))
    figures = list(spec.get("figures") or [])
    if figures:
        fs = int(max(32, min(h * 0.42, 96)) // 16 * 16)
        lit = k + (0.3 if fire else 0.0)
        tint = tuple(min(1.0, v * lit) for v in (1.0, 0.95, 0.9))
        n = len(figures)
        for i, parts in enumerate(figures):
            px = x + w * (float(spec.get("figures_x", 0.5)) + (i - (n - 1) / 2) * 0.16) + pan
            if fire:
                px += (w * 0.12) if i >= n / 2 else -(w * 0.12)
            cmd = dolls.draw(atlas, parts, px - fs / 2, y + h * 0.92 - fs, fs, tint)
            if cmd is not None:
                canvas.under(cmd)
    if kind.get("smoke") or spec.get("smoke"):
        for i in range(4):
            sx = x + w * (0.15 + 0.23 * i) + pan
            for j in range(5):
                tt = ((now * 0.18 + j * 0.2 + i * 0.13) % 1.0) if ambient else j * 0.2
                s = h * (0.12 + 0.2 * tt)
                canvas.under(Sprite("fx/smoke", sx - s / 2 + tt * w * 0.05, horizon - h * 0.1 - tt * h * 0.5, s, s,
                                    (60, 56, 54, int(150 * (1 - tt)))))
    _air(canvas, spec.get("atmosphere", kind.get("atmosphere")), x, y, w, h, now, ambient)
    canvas.under(Clip(None))
    canvas.under(*theme.panel(x, y, w, h, "inset", ornaments=False, border=True)[2:])
    return True


def _rgba(k: float) -> tuple[int, int, int, int]:
    v = int(255 * max(0.2, min(1.0, k)))
    return v, v, v, 255


def _tiles(canvas, atlas, names, x, y, w, h, t, k, seed) -> None:
    if not names or w <= 0 or h <= 0:
        return
    cols, rows = int(w // t) + 2, int(h // t) + 2
    dst, picks = [], []
    for j in range(rows):
        for i in range(cols):
            picks.append(names[(i * 5 + j * 3 + seed) % len(names)])
            dst.append((x + i * t - t * 0.5, y + j * t, t, t))
    c = np.full((len(dst), 4), max(0.15, min(1.0, k)), np.float32)
    c[:, 3] = 1
    canvas.under(*tile_batch(atlas, picks, np.array(dst, np.float32), c))


def _air(canvas, kind, x, y, w, h, now, ambient) -> None:
    """The air: mist in bands, embers rising, ash falling, a haze over everything."""
    if not kind:
        return
    if kind == "mist":
        from realmwalker.ui.gfx import titleart

        mw, mh = int(w), int(h * 0.5)
        drift = (now * 6) % max(1, mw) if ambient else 0
        for dx in (-drift, mw - drift):
            canvas.under(Image(("vig_mist", mw, mh), lambda: titleart.mist(mw, mh), (x + dx, y + h * 0.45, mw, mh),
                               rgba=(255, 255, 255, 150)))
    elif kind == "haze":
        canvas.under(Rect(x, y, w, h, (150, 130, 110, 50)))
    elif kind in ("embers", "ash"):
        colour = (255, 150, 60) if kind == "embers" else (190, 186, 180)
        rng = np.random.default_rng(13 if kind == "embers" else 14)
        for i in range(28):
            px, ph, sp = rng.random(), rng.random(), 0.05 + 0.08 * rng.random()
            tt = ((now * sp + ph) % 1.0) if ambient else ph
            yy = (1 - tt) if kind == "embers" else tt
            s = 3 + 3 * rng.random()
            sway = math.sin(now * 1.3 + i) * 6 if ambient else 0
            canvas.under(Image("vig_speck", _speck, (x + px * w + sway, y + yy * h, s, s),
                               rgba=(*colour, int(200 * (1 - abs(0.5 - tt) * 1.2)))))


# ---------------------------------------------------------------------------- choosing
SCARRED = ("burning", "burned", "sacked", "emptied")  # (a place that has been through these is a burned street)


def _scarred(s) -> bool:
    return s is not None and any(m in s.status for m in SCARRED)


def for_place(game, place: dict | None) -> str:
    """The backdrop for a story's place: a town's square, a barrow or a ruin, a ford, the road."""
    if not place or game is None:
        return "road"
    w = game.world
    if "settlement" in place:
        part = place.get("part")
        if part not in ("inn", "hall", "temple") and _scarred(w.settlements[int(place["settlement"])]):
            return "burned_street"
        return {"inn": "inn", "hall": "hall", "temple": "hall"}.get(part, "square")
    if "site" in place:
        site = w.sites[int(place["site"])]
        if is_hideout(w, site.id):
            return "hideout"
        kind = getattr(site, "kind", "")
        if kind in ("barrow", "tomb", "crypt", "cave", "lair"):
            return "barrow"
        return "ruin"
    try:
        x, y = int(place["tile"][0]), int(place["tile"][1])
    except (KeyError, TypeError, ValueError):
        return "road"
    s = w.settlement_at(x, y)
    if s is not None:
        return "burned_street" if _scarred(s) else "street"
    if w.river[x, y] and not w.road[x, y]:
        return "ford"
    return "road"


def is_hideout(world, site_id: int) -> bool:
    """A living gang keeps its hideout at this site (the outlaws' camp, not the place's old stones)."""
    from realmwalker.world import factions as fx

    return any(g.site == site_id for g in fx.active_factions(world, "bandit_gang"))


def party_figures(game, most: int = 3) -> list:
    """The party as figures for a picture (the hero first)."""
    if game is None:
        return []
    return [dolls.character(c, game.tables) for c in game.party if c.alive][:most]


PERSON_BACKDROP = {"patron": "hall", "ally": "camp", "witness": "street"}


def for_epilogue(game, adv: dict, about: str) -> dict:
    """An epilogue page's picture (B.9): the place as it now is - burned, rebuilding, a statue in its square, decked
    for a feast - the one the page tells of in their own place (a fresh grave if they are dead), and last, you on
    the road."""
    from realmwalker.game.story import cast

    w = game.world
    spec: dict = {"seed": int(str(adv.get("id", "A0"))[1:] or 0) * 7 + len(about), "time": "day"}
    if about in ("place", "innocent"):
        entry = adv["cast"].get("innocent") if about == "innocent" else None
        sid = (entry or {}).get("settlement", (adv["places"].get("town") or {}).get("settlement"))
        s = w.settlements[int(sid)] if sid is not None and 0 <= int(sid) < len(w.settlements) else None
        st = s.status if s is not None else {}
        scarred = _scarred(s)
        spec["backdrop"] = "burned_street" if scarred else "square"
        props = []
        if "memorial" in st:
            props += ["feature/statue", "feature/grave_0"]
        if "rebuilding" in st:
            props.append("feature/scaffold_0")
        if "festival" in st:
            props += ["feature/banner_0", "feature/lantern_post"]
        if props:
            spec["props"] = props
        if scarred:
            spec["time"] = "dusk"
        return spec
    if about in PERSON_BACKDROP:
        spec["backdrop"] = PERSON_BACKDROP[about]
        if about == "ally":
            spec["time"] = "dusk"
        person = cast.person(w, adv["cast"].get(about))
        if person is not None and hasattr(person, "job"):
            if getattr(person, "alive", True):
                spec["figures"] = [dolls.npc(person, game.tables)]
            else:
                spec["props"] = ["feature/grave_fresh_0"]
        return spec
    spec.update(backdrop="road", time="dusk", figures=party_figures(game, 3))
    return spec
