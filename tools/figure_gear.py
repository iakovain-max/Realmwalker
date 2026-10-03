"""What figures wear and hold, drawn to fit each body (tools/figure_art.py): clothes, armour, hair, beards, hats and
helmets, cloaks, weapons, shields, torches. Greys are coloured when drawn; metal is steel, crowns gold."""

from __future__ import annotations

import numpy as np

from figure_art import (EMPTY, FOOT, HAND, H, HEAD, LARM, LLEG, NEUTRAL, PELVIS, TORSO, UARM, ULEG, W, Body,
                        outline, paint, shades, to_image)

METAL = np.array([[26, 26, 30], [110, 112, 120], [168, 172, 180], [212, 216, 222], [250, 250, 252]], np.float32)
GOLD = np.array([[48, 32, 10], [150, 104, 34], [212, 164, 62], [240, 204, 104], [255, 240, 180]], np.float32)
WOOD = np.array([[36, 22, 12], [92, 60, 34], [128, 88, 52], [160, 116, 72], [186, 144, 96]], np.float32)
LEATHER = np.array([[30, 20, 14], [72, 48, 32], [102, 70, 46], [128, 92, 62], [150, 112, 80]], np.float32)

# ---------------------------------------------------------------------------- clothes and armour
# parts: body parts covered. skirt: rows of thigh covered, across the gap (99: to the knee). gown: down to the feet,
# across the gap, flaring. pauldrons: the shoulders grow a pixel. pattern: how the stuff is worked.
GARMENTS = {
    "shirt": dict(parts=(TORSO, UARM, PELVIS)),
    "shirt_long": dict(parts=(TORSO, UARM, LARM, PELVIS)),
    "tunic": dict(parts=(TORSO, UARM, LARM, PELVIS), skirt=2, pattern="hem"),
    "vest": dict(parts=(TORSO,), pattern="open"),
    "robe": dict(parts=(TORSO, UARM, LARM, PELVIS, ULEG, LLEG), gown=True, pattern="robe"),
    "dress": dict(parts=(TORSO, UARM, PELVIS, ULEG, LLEG), gown=True, pattern="hem"),
    "coat": dict(parts=(TORSO, UARM, LARM, PELVIS, ULEG), skirt=99, pattern="coat"),
    "rags": dict(parts=(TORSO, UARM, PELVIS), skirt=2, pattern="tatters"),
    "pants": dict(parts=(PELVIS, ULEG, LLEG)),
    "shorts": dict(parts=(PELVIS, ULEG)),
    "boots": dict(parts=(FOOT,), shin_rows=2, pattern="boots"),
    "shoes": dict(parts=(FOOT,)),
    "gloves": dict(parts=(HAND,)),
    "gauntlets": dict(parts=(HAND, LARM), pattern="bands"),
    "padded": dict(parts=(TORSO, UARM, PELVIS), skirt=1, pattern="quilt"),
    "leather": dict(parts=(TORSO, UARM, PELVIS), skirt=1, pattern="straps"),
    "studded": dict(parts=(TORSO, UARM, PELVIS), skirt=1, pattern="studs"),
    "hide": dict(parts=(TORSO, UARM, PELVIS), skirt=2, pattern="fur"),
    "chain_shirt": dict(parts=(TORSO, UARM, PELVIS), skirt=1, pattern="mail"),
    "chain_mail": dict(parts=(TORSO, UARM, LARM, PELVIS, ULEG), skirt=99, pattern="mail"),
    "ring_mail": dict(parts=(TORSO, UARM, PELVIS), skirt=2, pattern="rings"),
    "scale_mail": dict(parts=(TORSO, UARM, LARM, PELVIS), skirt=3, pattern="scales"),
    "breastplate": dict(parts=(TORSO,), pattern="plate"),
    "half_plate": dict(parts=(TORSO, UARM, PELVIS), skirt=2, pauldrons=True, pattern="plate"),
    "splint": dict(parts=(TORSO, UARM, LARM, PELVIS), skirt=2, pauldrons=True, pattern="bands"),
    "plate": dict(parts=(TORSO, UARM, LARM, PELVIS, ULEG, LLEG, FOOT), pauldrons=True, pattern="plate"),
    "greaves": dict(parts=(LLEG,), pattern="bands"),
    "tabard": dict(parts=(), tabard=True, pattern="hem"),
    "belt": dict(parts=(), belt=True),
}


def garment_mask(body: Body, spec: dict) -> np.ndarray:
    g = body.grid
    m = np.isin(g, spec.get("parts", ()))
    r = body.rows
    c = body.c
    hip = body.p["hip"]
    x0, x1 = c - hip // 2, c + hip // 2
    if spec.get("skirt"):
        n = spec["skirt"]
        bottom = min(r["uleg"] + n, r["lleg"]) if n < 99 else r["lleg"]
        m[r["uleg"]:bottom, x0:x1] = True
    if spec.get("gown"):
        rows = r["foot"] - r["uleg"]
        for i in range(rows):
            flare = 1 if i >= rows // 2 else 0
            m[r["uleg"] + i, x0 - flare:x1 + flare] = True
    if spec.get("pauldrons"):
        lo, hi = body.torso_rows[0]
        arm = body.p["arm"]
        m[r["torso"] + 1:r["torso"] + 3, lo - arm - 1:hi + arm + 1] = True
    if spec.get("shin_rows"):
        band = slice(r["foot"] - spec["shin_rows"], r["foot"])
        m[band] |= g[band] == LLEG
    if spec.get("tabard"):
        m[r["torso"] + 1:r["lleg"], c - 3:c + 3] = True
    if spec.get("belt"):
        m[r["pelvis"], x0:x1] = True
    return m


def _pattern(s: np.ndarray, m: np.ndarray, kind: str, body: Body) -> None:
    ys, xs = np.mgrid[0:H, 0:W]
    inner = m & (s >= 2)
    r = body.rows
    c = body.c
    g = body.grid
    if kind == "mail":  # rows of rings: a dark link every other pixel, every other row, staggered
        s[inner & (ys % 2 == 0) & (s == 2)] = 3
        s[inner & (ys % 2 == 1) & ((xs + ys // 2) % 2 == 0) & (s == 2)] = 1
    elif kind == "rings":
        s[inner & (xs % 2 == 0) & (ys % 2 == 0)] = 1
    elif kind == "scales":
        s[inner & ((ys % 3) == 2)] = 1
        s[inner & ((ys % 3) == 0) & ((xs + ys // 3) % 2 == 0)] = 3
    elif kind == "quilt":
        s[inner & (ys % 2 == 0)] = 1
    elif kind == "straps":
        band = (ys >= r["torso"]) & (ys < r["pelvis"])
        s[m & band & ((xs == c - 3) | (xs == c + 2))] = 1
    elif kind == "studs":
        s[inner & (xs % 3 == 1) & (ys % 3 == 1)] = 4
    elif kind == "fur":
        top = m & ~np.roll(m, 1, axis=0)
        s[top] = 4
        bottom = m & ~np.roll(m, -1, axis=0)
        s[bottom & (xs % 2 == 0)] = -1
    elif kind == "plate":
        s[inner & (xs == c - 2) & (ys >= r["torso"]) & (ys < r["pelvis"])] = 4
        s[inner & (xs > c) & (g == TORSO)] = 1
        s[inner & np.isin(g, (UARM, LARM, ULEG, LLEG)) & (ys % 3 == 0)] = 1
    elif kind == "bands":
        s[inner & (ys % 2 == 0)] = 1
    elif kind == "open":
        s[m & ((xs == c - 1) | (xs == c))] = -1
    elif kind == "coat":
        s[m & (xs == c - 1) & (ys >= r["pelvis"])] = 1
        s[m & (xs == c - 1) & (ys < r["pelvis"])] = 3
    elif kind == "robe":
        s[m & (xs == c - 1) & (ys >= r["torso"] + 1)] = 1
    elif kind == "tatters":
        bottom = m & ~np.roll(m, -1, axis=0)
        s[bottom & (xs % 2 == 1)] = -1
        s[inner & ((xs * 7 + ys * 3) % 11 == 0)] = 1
    elif kind == "hem":
        bottom = m & ~np.roll(m, -1, axis=0)
        s[bottom] = 1
    elif kind == "boots":
        top = m & ~np.roll(m, 1, axis=0)
        s[top] = 3


def garment(body: Body, name: str):
    spec = GARMENTS[name]
    m = garment_mask(body, spec)
    s = shades(m)
    if spec.get("pattern"):
        _pattern(s, m, spec["pattern"], body)
    m = s >= 1
    return to_image(paint(s, NEUTRAL, line=outline(m) & (body.grid == EMPTY)))


# ---------------------------------------------------------------------------- hair, beards, headgear
HAIR = ("short", "long", "ponytail", "bun", "curly", "braids", "topknot", "cropped")
BEARDS = ("stubble", "short", "full", "long", "braided")
HEADGEAR = ("hood", "cap", "kettle", "nasal", "greathelm", "crown", "wizard", "straw", "furhat", "circlet", "horned")


def _box(body: Body):
    hx, hy, hw, hh = body.head
    return hx, hy, hw, hh, body.c, hy + hh // 2


def hair(body: Body, style: str):
    hx, hy, hw, hh, c, ey = _box(body)
    m = np.zeros((H, W), bool)
    m[hy - 1, hx + 1:hx + hw - 1] = True
    m[hy:hy + 2, hx:hx + hw] = True
    m[hy + 2:ey - 1, hx:hx + 1] = True
    m[hy + 2:ey - 1, hx + hw - 1:hx + hw] = True
    if style == "cropped":
        m[hy - 1] = False
        m[hy + 2:ey - 1] = False
    if style in ("long", "braids"):
        bottom = body.rows["torso"] + 3
        m[hy + 2:bottom, hx - 1:hx + 1] = True
        m[hy + 2:bottom, hx + hw - 1:hx + hw + 1] = True
        m[ey - 1:bottom, hx + 1] = False
        m[ey - 1:bottom, hx + hw - 2] = False
        if style == "braids":
            m[body.rows["torso"]:bottom + 2, hx - 1] = True
            m[body.rows["torso"]:bottom + 2, hx + hw] = True
    if style == "ponytail":
        m[hy + 1:body.rows["torso"] + 2, hx + hw:hx + hw + 2] = True
    if style == "bun":
        m[hy - 3:hy - 1, c - 2:c + 2] = True
    if style == "curly":
        m[hy - 2, hx + 1:hx + hw - 1:2] = True
        m[hy + 2:ey + 1, hx - 1] = True
        m[hy + 2:ey + 1, hx + hw] = True
    if style == "topknot":
        m[:] = False
        m[hy - 3:hy, c - 1:c + 1] = True
        m[hy, c - 2:c + 2] = True
    s = shades(m)
    ys, xs = np.mgrid[0:H, 0:W]
    s[m & (s == 2) & ((xs + ys) % 3 == 0)] = 3  # strands
    return to_image(paint(s, NEUTRAL, line=outline(m) & (body.grid == EMPTY)))


def beard(body: Body, style: str):
    hx, hy, hw, hh, c, ey = _box(body)
    m = np.zeros((H, W), bool)
    jaw = hy + hh
    ys, xs = np.mgrid[0:H, 0:W]
    if style == "stubble":
        m[ey + 2:jaw] = body.grid[ey + 2:jaw] == HEAD
        s = np.where(m & ((xs + ys) % 2 == 1), 1, -1).astype(np.int8)
        return to_image(paint(s, NEUTRAL))
    m[ey + 1, c - 2:c + 2] = True  # moustache
    m[ey + 2:jaw] = body.grid[ey + 2:jaw] == HEAD
    m[ey + 2, c - 1:c + 1] = False  # the mouth shows
    if style in ("full", "long", "braided"):
        m[jaw:jaw + 2, c - 3:c + 3] = True
    if style in ("long", "braided"):
        for i in range(4):
            m[jaw + 2 + i, c - 3 + i // 2:c + 3 - i // 2] = True
    if style == "braided":
        m[jaw + 6:jaw + 8, c - 2] = True
        m[jaw + 6:jaw + 8, c + 1] = True
    s = shades(m)
    s[m & (s == 2) & ((xs + 2 * ys) % 4 == 0)] = 3
    return to_image(paint(s, NEUTRAL, line=outline(m) & (body.grid != HEAD) & ~m))


def headgear(body: Body, kind: str):
    """Cloth headgear in greys (coloured when drawn); helmets in steel; crowns and circlets in gold."""
    hx, hy, hw, hh, c, ey = _box(body)
    m = np.zeros((H, W), bool)
    ramp = NEUTRAL
    slit = None
    if kind == "hood":
        m[hy - 1, hx:hx + hw] = True
        m[hy:body.rows["torso"] + 1, hx - 1:hx + hw + 1] = True
        m[ey - 1:hy + hh, hx + 1:hx + hw - 1] = False  # the face shows
        m[body.rows["torso"]:body.rows["torso"] + 2, hx - 2:hx + hw + 2] = True
    elif kind == "cap":
        m[hy - 1:hy + 2, hx:hx + hw] = True
        m[hy - 1, hx] = m[hy - 1, hx + hw - 1] = False
    elif kind in ("kettle", "nasal", "horned"):
        ramp = METAL
        m[hy - 2:hy + 2, hx:hx + hw] = True
        m[hy - 2, hx:hx + 2] = False
        m[hy - 2, hx + hw - 2:hx + hw] = False
        if kind == "kettle":
            m[hy + 2, hx - 2:hx + hw + 2] = True
        else:
            m[hy + 2, hx:hx + hw] = True
            m[hy + 3:ey + 2, c - 1] = True
        if kind == "horned":
            for i in range(3):
                m[hy - 1 - i, hx - 1 - i // 2] = True
                m[hy - 1 - i, hx + hw + i // 2] = True
    elif kind == "greathelm":
        ramp = METAL
        m[hy - 1:hy + hh + 1, hx - 1:hx + hw + 1] = True
        m[hy - 1, hx - 1] = m[hy - 1, hx + hw] = False
        slit = ey
    elif kind == "crown":
        ramp = GOLD
        m[hy:hy + 2, hx:hx + hw] = True
        m[hy - 2:hy, hx:hx + hw:2] = True
    elif kind == "circlet":
        ramp = GOLD
        m[hy + 1, hx:hx + hw] = True
    elif kind == "wizard":
        top = max(0, hy - 5)
        for i, y in enumerate(range(top, hy + 1)):
            half = 1 + i
            m[y, c - half + 1:c + half - 1 + (1 if i else 0)] = True
        m[top, c + 1:c + 3] = True  # the tip, bent over
        m[hy + 1, hx - 2:hx + hw + 2] = True
    elif kind == "straw":
        m[hy - 2:hy, hx + 1:hx + hw - 1] = True
        m[hy, hx - 3:hx + hw + 3] = True
    elif kind == "furhat":
        m[hy - 2:hy + 2, hx - 1:hx + hw + 1] = True
        m[hy - 2, hx - 1] = m[hy - 2, hx + hw] = False
    s = shades(m)
    ys, xs = np.mgrid[0:H, 0:W]
    if kind in ("furhat", "straw"):
        s[m & (s >= 2) & ((xs + ys) % 2 == 0)] = 3
    a = paint(s, ramp, line=outline(m) & (body.grid != HEAD) & ~m)
    if slit is not None:
        a[slit, hx:hx + hw, :3] = (16, 14, 14)
    return to_image(a)


def cloak(body: Body, part: str):
    """A cloak: the back (drawn behind the body, hanging to the shins and showing past the arms and between the legs)
    or the front (a mantle over the shoulders, with a clasp)."""
    r = body.rows
    lo, hi = body.torso_rows[0]
    arm = body.p["arm"]
    m = np.zeros((H, W), bool)
    c = body.c
    ys, xs = np.mgrid[0:H, 0:W]
    if part == "back":
        bottom = r["foot"] - 1
        rows = bottom - r["torso"]
        for i, y in enumerate(range(r["torso"], bottom)):
            flare = 1 if i >= rows // 3 else 0
            x0, x1 = lo - arm - flare, hi + arm + flare
            if i == rows - 1:  # the hem curls in at its corners
                x0, x1 = x0 + 1, x1 - 1
            m[y, x0:x1] = True
        m[r["torso"], lo - arm:lo] = False  # the shoulders are round
        m[r["torso"], hi:hi + arm] = False
        s = shades(m)
        s[m & ((xs - c) % 3 == 0) & (s >= 2) & (ys > r["pelvis"])] = 1  # folds
        s[m & (ys == bottom - 1) & (xs % 2 == 0)] = 1
        return to_image(paint(s, NEUTRAL, line=outline(m) & (body.grid == EMPTY)))
    m[r["torso"] - 1, c - 3:c + 3] = True  # the collar
    m[r["torso"], lo:hi] = True
    m[r["torso"] + 1, lo - arm + 1:hi + arm - 1] = True
    m[r["torso"] + 2, lo - arm:lo + 1] = True  # it falls over the shoulders
    m[r["torso"] + 2, hi - 1:hi + arm] = True
    m[r["torso"] + 3, lo - arm:lo - arm + 1] = True
    m[r["torso"] + 3, hi + arm - 1:hi + arm] = True
    s = shades(m)
    a = paint(s, NEUTRAL, line=outline(m) & (body.grid == EMPTY))
    a[r["torso"], c - 1:c + 1, :3] = GOLD[3]
    a[r["torso"] + 1, c - 1:c + 1, :3] = GOLD[1]
    a[r["torso"], c - 1:c + 1, 3] = 255
    a[r["torso"] + 1, c - 1:c + 1, 3] = 255
    return to_image(a)


# ---------------------------------------------------------------------------- held things
# Drawn once, held at the reference body's hand; the game moves them to each body's hand.
# Templates: rows top to bottom; the hand is "h". m metal (coloured), M metal highlight, g gold, w wood, l leather,
# s string, f flame, F flame core, o glass/gem, b dark iron. Outlines are added.
WEAPONS = {
    "dagger": ["M", "m", "m", "gg g", " h"],
    "shortsword": ["M", "m", "m", "m", "m", "m", "ggg", " h", " g"],
    "longsword": ["M", "m", "m", "m", "m", "m", "m", "m", "m", "ggggg", "  h", "  l", "  g"],
    "greatsword": [" M", "Mm", "Mm", "Mm", "Mm", "Mm", "Mm", "Mm", "Mm", "Mm", "Mm", "ggggg", "  h", "  l", "  l", "  g"],
    "scimitar": ["  M", " Mm", " m", "Mm", "m", "m", "m", "gg", "h", "g"],
    "rapier": ["M", "m", "m", "m", "m", "m", "m", "m", " g ", "g g", "ghg", " g"],
    "club": [" ww", " ww", " ww", "ww", "w", "w", "h", "w"],
    "mace": ["mMm", "mmm", "mMm", " w", " w", " w", " h", " w"],
    "morningstar": [" M ", "MmM", "mmm", " m ", " w", " w", " w", " h", " w"],
    "flail": [" mM", " mm", "  b", " b", "b", "w", "w", "h", "w"],
    "warhammer": ["mmm", "mMm", " w", " w", " w", " w", " h", " w"],
    "maul": ["mmmm", "mMMm", "mmmm", " w", " w", " w", " w", " w", " h", " w"],
    "handaxe": ["mm", "Mmw", "m w", "  w", "  h", "  w"],
    "battleaxe": [" mm", "Mmmw", "Mm w", " m w", "   w", "   w", "   h", "   w"],
    "greataxe": ["  mm  ", "Mmmwmm", "Mm wmM", " m wm", "   w", "   w", "   w", "   w", "   h", "   w"],
    "spear": ["M", "m", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "h", "w", "w"],
    "pike": ["M", "m", "m", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "h", "w"],
    "glaive": [" M", "Mm", "Mm", " m", " w", " w", " w", " w", " w", " w", " w", " w", " w", " h", " w"],
    "halberd": [" M", "mMmm", "mm", " w", " w", " w", " w", " w", " w", " w", " w", " w", " h", " w"],
    "quarterstaff": ["w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "h", "w", "w", "w", "w"],
    "staff": ["o", "g", "w", "w", "w", "w", "w", "w", "w", "w", "w", "w", "h", "w", "w", "w", "w"],
    "sickle": [" mm", "m  M", "m", " m", " w", " h", " w"],
    "javelin": ["M", "w", "w", "w", "w", "w", "w", "w", "w", "h", "w", "w"],
    "shortbow": ["w", "ws", "w s", "w s", "w  s", " w s", "  ws", "  h", " w s", "w  s", "w s", "ws", "w"],
    "longbow": ["w", "ws", "w s", "w s", "w s", "w  s", " w s", "  ws", "  h", " w s", "w  s", "w s", "w s", "ws", "w"],
    "crossbow": ["  m  ", "wwwww", "m w m", "  w", "  h", "  w"],
    "hand_crossbow": [" m ", "wmw", " h", " w"],
    "sling": ["l", "l", "l", "ll", " h"],
    "knife": ["M", "m", "h", "w"],
    "torch": ["fF", "Ff", "fF", "w", "w", "h", "w"],
    "lantern": [" g ", "gog", "oFo", "gog", " h"],
    "book": ["llll", "lwwl", "lwwl", "lhll"],
    "pickaxe": ["mmmmm", "m w M", "  w", "  w", "  w", "  h", "  w"],
    "scythe": ["mmmm", "   mw", "    w", "    w", "    w", "    h", "    w", "    w"],
    "trident": ["m m m", "mmmmm", "  m", "  w", "  w", "  w", "  w", "  w", "  w", "  h", "  w"],
    "whip": ["l", " l", "  l", "  l", " l", "l", "h", "l"],
    "holy_symbol": [" g ", "ggg", " g ", " h"],
}
COLOURS = {
    "M": None, "m": None,  # metal: highlight / body (coloured when drawn)
    "g": (220, 172, 70), "w": (116, 80, 46), "l": (90, 60, 38), "s": (222, 212, 184), "f": (244, 140, 40),
    "F": (255, 224, 120), "o": (150, 210, 255), "b": (70, 70, 78), "h": (102, 70, 46),
}


def _template(rows: list[str]):
    """(pixels {(x, y): ch}, hand (x, y)) from a template."""
    px = {}
    hand = (0, 0)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == " ":
                continue
            px[(x, y)] = ch
            if ch == "h":
                hand = (x, y)
    return px, hand


def held(name: str, hand_xy: tuple[float, float], part: str = "all", mirror: bool = False):
    """A held thing as two layers: 'metal' (greys, coloured when drawn) and 'rest' (its own colours). The hand pixel
    lands on hand_xy."""
    rows = WEAPONS[name]
    px, (hx, hy) = _template(rows)
    ox = int(round(hand_xy[0])) - hx
    oy = int(round(hand_xy[1])) - hy
    metal = np.zeros((H, W, 4), np.uint8)
    rest = np.zeros((H, W, 4), np.uint8)
    shape = np.zeros((H, W), bool)
    for (x, y), ch in px.items():
        X, Y = ox + (-x if mirror else x), oy + y
        if not (0 <= X < W and 0 <= Y < H):
            continue
        shape[Y, X] = True
        if ch in ("m", "M"):
            v = NEUTRAL[4] if ch == "M" else NEUTRAL[3 if (x + y) % 3 else 2]
            metal[Y, X, :3] = v
            metal[Y, X, 3] = 255
        else:
            col = np.array(COLOURS[ch], np.float32)
            if ch in ("w", "l", "h") and (x + y) % 2:
                col = col * 0.85
            rest[Y, X, :3] = col
            rest[Y, X, 3] = 255
    line = outline(shape)
    rest[line, :3] = (24, 18, 14)
    rest[line, 3] = 255
    if part == "metal":
        return to_image(metal)
    if part == "rest":
        return to_image(rest)
    out = rest.copy()
    m = metal[..., 3] > 0
    out[m] = metal[m]
    return to_image(out)


SHIELDS = ("buckler", "round", "kite", "heater", "tower")
EMBLEMS = ("none", "cross", "saltire", "chevron", "pale", "bend", "sun", "moon", "star", "tree", "skull", "tower",
           "crown", "beast", "flame", "eye")


def _shield_mask(kind: str, cx: int, cy: int) -> np.ndarray:
    m = np.zeros((H, W), bool)
    ys, xs = np.mgrid[0:H, 0:W]
    if kind == "buckler":
        m = (xs - cx) ** 2 + (ys - cy) ** 2 <= 6
    elif kind == "round":
        m = (xs - cx) ** 2 + (ys - cy) ** 2 <= 13
    elif kind == "kite":
        for i in range(10):
            half = 3 if i < 5 else max(0, 3 - (i - 4) // 2)
            m[cy - 4 + i, cx - half:cx + half + 1] = True
    elif kind == "heater":
        for i in range(8):
            half = 3 if i < 4 else max(0, 3 - (i - 3))
            m[cy - 3 + i, cx - half:cx + half + 1] = True
    elif kind == "tower":
        m[cy - 6:cy + 6, cx - 3:cx + 4] = True
    return m


def shield(kind: str, hand_xy: tuple[float, float], layer: str):
    """A shield on the arm at hand_xy: 'field' (coloured when drawn), 'rim' (iron and wood), or an emblem."""
    cx, cy = int(round(hand_xy[0])) + 1, int(round(hand_xy[1])) - 3
    m = _shield_mask(kind, cx, cy)
    ys, xs = np.mgrid[0:H, 0:W]
    a = np.zeros((H, W, 4), np.uint8)
    edge = m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
    inner = m & ~edge
    if layer == "field":
        s = shades(inner)
        return to_image(paint(s, NEUTRAL))
    if layer == "rim":
        a[edge, :3] = METAL[2]
        a[edge & ((xs < cx) | (ys < cy)), :3] = METAL[3]
        a[edge, 3] = 255
        line = outline(m)
        a[line, :3] = (22, 18, 16)
        a[line, 3] = 255
        if kind in ("round", "buckler"):
            a[cy, cx, :3] = METAL[4]
            a[cy, cx, 3] = 255
        return to_image(a)
    em = np.zeros((H, W), bool)
    if layer == "cross":
        em = inner & ((xs == cx) | (ys == cy - 1))
    elif layer == "saltire":
        em = inner & ((xs - cx == ys - cy) | (xs - cx == cy - ys))
    elif layer == "chevron":
        em = inner & (ys - cy == -abs(xs - cx) + 1)
    elif layer == "pale":
        em = inner & (abs(xs - cx) <= 0)
    elif layer == "bend":
        em = inner & (xs - cx == ys - cy)
    elif layer in ("sun", "star"):
        em = inner & ((xs - cx) ** 2 + (ys - cy + 1) ** 2 <= 2)
        if layer == "sun":
            em |= inner & (((xs - cx) == 0) | ((ys - cy + 1) == 0)) & ((xs - cx) ** 2 + (ys - cy + 1) ** 2 <= 9)
    elif layer == "moon":
        em = inner & ((xs - cx) ** 2 + (ys - cy) ** 2 <= 4) & ~((xs - cx - 1) ** 2 + (ys - cy) ** 2 <= 3)
    elif layer == "tree":
        em = inner & (((xs == cx) & (ys >= cy - 1)) | ((abs(xs - cx) <= 1) & (ys == cy - 2)) | ((xs == cx) & (ys == cy - 3)))
    elif layer == "skull":
        em = inner & (abs(xs - cx) <= 1) & (abs(ys - cy + 1) <= 1)
        em[cy - 1, cx - 1] = em[cy - 1, cx + 1] = False
    elif layer == "tower":
        em = inner & (abs(xs - cx) <= 1) & (ys >= cy - 2) & (ys <= cy + 1)
        em[cy - 2, cx] = False
    elif layer == "crown":
        em = inner & (abs(xs - cx) <= 2) & (ys == cy)
        em |= inner & (ys == cy - 1) & ((xs - cx) % 2 == 0) & (abs(xs - cx) <= 2)
    elif layer == "beast":
        em = inner & (abs(xs - cx) <= 1) & (abs(ys - cy) <= 1)
        em |= inner & (ys == cy - 2) & ((xs == cx - 1) | (xs == cx + 1))
    elif layer == "flame":
        em = inner & (abs(xs - cx) <= (ys - (cy - 3)) // 2) & (ys <= cy + 1) & (ys >= cy - 3)
    elif layer == "eye":
        em = inner & (abs(xs - cx) <= 1) & (ys == cy)
        em[cy - 1, cx] = em[cy + 1, cx] = True
        em &= inner
    a[em, :3] = NEUTRAL[3]
    a[em, 3] = 255
    return to_image(a)
