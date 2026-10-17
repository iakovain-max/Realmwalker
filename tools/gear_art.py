"""Hand-drawn 32x32 icons for the 2024 gear (Blades & Backgrounds part D): tool kits, games, instruments, adventuring
gear and the seven packs. Same style as tile_art.firearm(): a few flat colours per object, a lit edge, a dark outline,
a drop shadow. Pictures that the Crawl pack shows well (potions, staffs, wands, the mirror, the horn...) are mapped in
build_tiles.py ITEMS instead; everything here is drawn by code. `all_drawn()` gives {"item/<id>": image}."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from tile_art import blank, outline, shadow


def C(r, g, b):
    return (r, g, b, 255)


WOOD, WOOD_D, WOOD_L = C(122, 78, 44), C(84, 52, 30), C(168, 118, 70)
LEATHER, LEATHER_D, LEATHER_L = C(110, 74, 46), C(70, 46, 30), C(150, 108, 70)
IRON, IRON_D, IRON_L = C(84, 88, 98), C(52, 54, 62), C(150, 156, 168)
BRASS, BRASS_D, BRASS_L = C(190, 150, 66), C(120, 90, 40), C(232, 202, 122)
PAPER, PAPER_D = C(212, 198, 160), C(160, 144, 108)
ROPE, ROPE_D = C(176, 148, 96), C(120, 94, 56)
CLOTH, CLOTH_D = C(176, 168, 150), C(122, 116, 104)
RED, RED_D = C(150, 40, 40), C(96, 24, 28)
GLASS, GLASS_D = C(150, 190, 196), C(96, 130, 140)
INK = C(30, 28, 36)


def _new():
    im = blank()
    return im, ImageDraw.Draw(im)


def _fin(im):
    return shadow(outline(im))


def _line(d, pts, col, w=1):
    d.line(pts, fill=col, width=w)


def _px(d, pts, col):
    for p in pts:
        d.point(p, fill=col)


# --------------------------------------------------------------------------- tool glyphs (about 12 tall, in a case)

def _hammer(d, cx, y0, head=IRON, hi=IRON_L, haft=WOOD):
    _line(d, [(cx, y0 + 3), (cx, y0 + 12)], haft, 2)
    d.rectangle([cx - 3, y0, cx + 2, y0 + 3], fill=head)
    _line(d, [(cx - 3, y0), (cx + 2, y0)], hi)


def _chisel(d, cx, y0):
    _line(d, [(cx, y0 + 7), (cx, y0 + 12)], WOOD, 2)
    d.rectangle([cx - 1, y0, cx, y0 + 7], fill=IRON_L)
    _line(d, [(cx - 1, y0 + 7), (cx, y0 + 7)], BRASS)


def _brush(d, cx, y0, col):
    _line(d, [(cx, y0 + 5), (cx, y0 + 12)], WOOD_L, 1)
    d.rectangle([cx - 1, y0 + 4, cx + 1, y0 + 6], fill=BRASS)
    d.polygon([(cx - 2, y0 + 4), (cx + 2, y0 + 4), (cx + 1, y0), (cx - 1, y0)], fill=col)


def _quill(d, cx, y0):
    d.polygon([(cx - 3, y0 + 8), (cx + 2, y0), (cx + 4, y0 + 1), (cx + 1, y0 + 7)], fill=PAPER)
    _line(d, [(cx - 3, y0 + 8), (cx + 3, y0 + 1)], PAPER_D)
    _line(d, [(cx - 3, y0 + 8), (cx - 1, y0 + 12)], INK, 1)


def _bottle(d, cx, y0, col, cork=WOOD_L):
    d.rectangle([cx - 1, y0 + 1, cx, y0 + 4], fill=GLASS)
    d.rectangle([cx - 1, y0, cx, y0 + 1], fill=cork)
    d.rectangle([cx - 3, y0 + 5, cx + 2, y0 + 12], fill=col)
    _px(d, [(cx - 3, y0 + 5), (cx - 3, y0 + 6)], GLASS)


def _tongs(d, cx, y0):
    _line(d, [(cx - 1, y0), (cx + 1, y0 + 12)], IRON_L, 1)
    _line(d, [(cx + 2, y0), (cx, y0 + 12)], IRON, 1)
    _px(d, [(cx, y0 + 6)], BRASS)


def _knife(d, cx, y0):
    d.polygon([(cx - 1, y0), (cx + 1, y0 + 2), (cx + 1, y0 + 7), (cx - 1, y0 + 7)], fill=IRON_L)
    _line(d, [(cx, y0 + 8), (cx, y0 + 12)], WOOD, 2)
    _line(d, [(cx - 1, y0 + 8), (cx + 1, y0 + 8)], BRASS)


def _awl(d, cx, y0):
    _line(d, [(cx, y0), (cx, y0 + 6)], IRON_L)
    d.ellipse([cx - 2, y0 + 6, cx + 1, y0 + 12], fill=WOOD)


def _gem(d, cx, y0, col, hi):
    d.polygon([(cx, y0 + 2), (cx + 3, y0 + 5), (cx, y0 + 11), (cx - 3, y0 + 5)], fill=col)
    d.polygon([(cx, y0 + 2), (cx + 3, y0 + 5), (cx - 3, y0 + 5)], fill=hi)


def _spool(d, cx, y0, col):
    d.rectangle([cx - 3, y0 + 1, cx + 2, y0 + 11], fill=col)
    d.rectangle([cx - 4, y0, cx + 3, y0 + 1], fill=WOOD_L)
    d.rectangle([cx - 4, y0 + 11, cx + 3, y0 + 12], fill=WOOD_L)
    _line(d, [(cx - 3, y0 + 4), (cx + 2, y0 + 3)], WOOD_L)


def _shears(d, cx, y0):
    _line(d, [(cx - 3, y0 + 10), (cx + 2, y0)], IRON_L, 1)
    _line(d, [(cx + 3, y0 + 10), (cx - 2, y0)], IRON_L, 1)
    d.ellipse([cx - 5, y0 + 9, cx - 2, y0 + 12], outline=IRON)
    d.ellipse([cx + 2, y0 + 9, cx + 5, y0 + 12], outline=IRON)


def _dividers(d, cx, y0):
    _line(d, [(cx - 1, y0 + 12), (cx, y0 + 1)], IRON_L)
    _line(d, [(cx + 3, y0 + 12), (cx + 1, y0 + 1)], IRON_L)
    d.rectangle([cx - 1, y0, cx + 1, y0 + 2], fill=BRASS)


def _ruler(d, cx, y0):
    d.rectangle([cx - 1, y0, cx + 1, y0 + 12], fill=WOOD_L)
    for k in range(1, 12, 3):
        _px(d, [(cx - 1, y0 + k)], WOOD_D)


def _file(d, cx, y0):
    d.rectangle([cx - 1, y0, cx, y0 + 8], fill=IRON)
    for k in range(0, 8, 2):
        _px(d, [(cx - 1, y0 + k)], IRON_L)
    _line(d, [(cx, y0 + 9), (cx, y0 + 12)], WOOD, 2)


def _pipe(d, cx, y0):  # a glassblower's blowpipe with a glowing gather
    _line(d, [(cx, y0 + 3), (cx, y0 + 12)], IRON_L, 1)
    d.ellipse([cx - 2, y0, cx + 2, y0 + 4], fill=C(230, 130, 50))
    _px(d, [(cx - 1, y0 + 1)], C(255, 210, 120))


def _trowel(d, cx, y0):
    d.polygon([(cx, y0), (cx + 3, y0 + 7), (cx - 3, y0 + 7)], fill=IRON_L)
    _line(d, [(cx, y0 + 7), (cx, y0 + 12)], WOOD, 2)


def _palette(d, cx, y0):
    d.ellipse([cx - 4, y0 + 1, cx + 4, y0 + 11], fill=WOOD_L)
    d.ellipse([cx - 3, y0 + 7, cx - 1, y0 + 9], fill=(0, 0, 0, 0))
    _px(d, [(cx - 2, y0 + 3), (cx, y0 + 2), (cx + 2, y0 + 3)], C(180, 50, 50))
    _px(d, [(cx + 3, y0 + 5), (cx + 3, y0 + 8)], C(60, 90, 160))
    _px(d, [(cx + 1, y0 + 9)], C(220, 190, 70))


def _clay(d, cx, y0):
    d.ellipse([cx - 4, y0 + 4, cx + 4, y0 + 12], fill=C(160, 100, 64))
    d.ellipse([cx - 3, y0 + 4, cx + 3, y0 + 8], fill=C(186, 124, 80))


def _mortar(d, cx, y0):
    d.polygon([(cx - 4, y0 + 4), (cx + 4, y0 + 4), (cx + 3, y0 + 11), (cx - 3, y0 + 11)], fill=IRON)
    _line(d, [(cx - 4, y0 + 4), (cx + 4, y0 + 4)], IRON_L)
    _line(d, [(cx + 1, y0 + 4), (cx + 4, y0)], WOOD_L, 2)


def _seal(d, cx, y0):
    _line(d, [(cx, y0), (cx, y0 + 6)], WOOD, 2)
    d.ellipse([cx - 3, y0 + 7, cx + 3, y0 + 12], fill=RED)
    _px(d, [(cx - 1, y0 + 9)], C(210, 90, 80))


def _spoon(d, cx, y0):
    _line(d, [(cx, y0 + 4), (cx, y0 + 12)], WOOD_L, 1)
    d.ellipse([cx - 2, y0, cx + 2, y0 + 5], fill=WOOD)


def _funnel(d, cx, y0):
    d.polygon([(cx - 4, y0 + 1), (cx + 4, y0 + 1), (cx + 1, y0 + 8), (cx - 1, y0 + 8)], fill=BRASS)
    d.rectangle([cx - 1, y0 + 8, cx, y0 + 12], fill=BRASS_D)


def kit(name):
    """An open case lined with cloth, three tools standing in it."""
    im, d = _new()
    slots = {
        "alchemists": (lambda d, x, y: _bottle(d, x, y, C(70, 160, 80)), lambda d, x, y: _mortar(d, x, y),
                       lambda d, x, y: _bottle(d, x, y, C(170, 50, 60))),
        "brewers": (lambda d, x, y: _bottle(d, x, y, C(196, 136, 48)), lambda d, x, y: _funnel(d, x, y),
                    lambda d, x, y: _spoon(d, x, y)),
        "calligraphers": (lambda d, x, y: _quill(d, x, y), lambda d, x, y: _bottle(d, x, y, INK),
                          lambda d, x, y: _brush(d, x, y, INK)),
        "cartographers": (lambda d, x, y: _dividers(d, x, y), lambda d, x, y: _quill(d, x, y),
                          lambda d, x, y: _ruler(d, x, y)),
        "cobblers": (lambda d, x, y: _awl(d, x, y), lambda d, x, y: _knife(d, x, y), lambda d, x, y: _hammer(d, x, y)),
        "glassblowers": (lambda d, x, y: _pipe(d, x, y), lambda d, x, y: _tongs(d, x, y),
                         lambda d, x, y: _bottle(d, x, y, C(80, 130, 190))),
        "jewelers": (lambda d, x, y: _gem(d, x, y, C(170, 40, 60), C(230, 110, 120)), lambda d, x, y: _tongs(d, x, y),
                     lambda d, x, y: _gem(d, x, y, C(50, 90, 190), C(130, 170, 240))),
        "masons": (lambda d, x, y: _hammer(d, x, y), lambda d, x, y: _chisel(d, x, y), lambda d, x, y: _trowel(d, x, y)),
        "painters": (lambda d, x, y: _brush(d, x, y, C(180, 50, 50)), lambda d, x, y: _palette(d, x, y),
                     lambda d, x, y: _brush(d, x, y, C(60, 90, 170))),
        "potters": (lambda d, x, y: _clay(d, x, y), lambda d, x, y: _awl(d, x, y), lambda d, x, y: _spoon(d, x, y)),
        "tinkers": (lambda d, x, y: _hammer(d, x, y), lambda d, x, y: _tongs(d, x, y), lambda d, x, y: _file(d, x, y)),
        "weavers": (lambda d, x, y: _spool(d, x, y, C(170, 50, 50)), lambda d, x, y: _shears(d, x, y),
                    lambda d, x, y: _spool(d, x, y, C(60, 90, 170))),
        "woodcarvers": (lambda d, x, y: _knife(d, x, y), lambda d, x, y: _chisel(d, x, y),
                        lambda d, x, y: _hammer(d, x, y, head=WOOD_D, hi=WOOD_L)),
        "forgery": (lambda d, x, y: _quill(d, x, y), lambda d, x, y: _seal(d, x, y),
                    lambda d, x, y: _bottle(d, x, y, INK)),
        "poisoners": (lambda d, x, y: _bottle(d, x, y, C(100, 170, 50)), lambda d, x, y: _knife(d, x, y),
                      lambda d, x, y: _bottle(d, x, y, C(130, 60, 160))),
    }[name]
    case = {"alchemists": LEATHER_D, "poisoners": C(54, 46, 58), "forgery": C(60, 56, 50)}.get(name, LEATHER)
    lining = {"alchemists": C(70, 60, 90), "poisoners": C(60, 40, 70), "weavers": C(140, 110, 70)}.get(name, C(120, 52, 48))
    d.rectangle([2, 9, 29, 28], fill=case)
    d.rectangle([4, 11, 27, 26], fill=lining)
    _line(d, [(2, 9), (29, 9)], LEATHER_L)
    for k, fn in enumerate(slots):
        fn(d, 8 + 8 * k, 12)
    d.rectangle([2, 25, 29, 28], fill=case)  # the front lip hides the feet of the tools
    _line(d, [(2, 25), (29, 25)], LEATHER_L)
    d.rectangle([14, 24, 17, 28], fill=BRASS)  # clasp
    _px(d, [(15, 26)], BRASS_D)
    return _fin(im)


# --------------------------------------------------------------------------- games

def dragonchess():
    im, d = _new()
    d.polygon([(2, 20), (16, 12), (30, 20), (16, 28)], fill=WOOD_D)
    d.polygon([(4, 20), (16, 13), (28, 20), (16, 27)], fill=C(200, 180, 140))
    for i in range(4):
        for j in range(4):
            if (i + j) % 2 == 0:
                cx = 16 + (i - j) * 3
                cy = 14 + (i + j) * 2 + 2
                d.polygon([(cx, cy - 2), (cx + 3, cy), (cx, cy + 2), (cx - 3, cy)], fill=WOOD)
    d.polygon([(2, 20), (16, 28), (16, 30), (2, 22)], fill=WOOD_D)
    d.polygon([(30, 20), (16, 28), (16, 30), (30, 22)], fill=WOOD)
    # a dragon piece: base, neck, head with a crest
    d.rectangle([13, 16, 18, 18], fill=RED_D)
    d.rectangle([14, 11, 17, 16], fill=RED)
    d.polygon([(14, 11), (12, 8), (16, 5), (20, 7), (17, 11)], fill=RED)
    _px(d, [(13, 5), (14, 4), (18, 5)], RED_D)
    _px(d, [(17, 7)], C(240, 200, 80))
    return _fin(im)


def three_dragon_ante():
    im, d = _new()

    def card(cx, cy, ang, col):
        a = math.radians(ang)
        pts = []
        for x, y in ((-6, -9), (6, -9), (6, 9), (-6, 9)):
            pts.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
        d.polygon(pts, fill=col, outline=INK)
        inner = []
        for x, y in ((-4, -7), (4, -7), (4, 7), (-4, 7)):
            inner.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
        d.polygon(inner, outline=C(160, 140, 90))
        d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=RED)

    card(10, 18, -28, C(226, 214, 180))
    card(22, 18, 28, C(226, 214, 180))
    card(16, 15, 0, C(240, 228, 192))
    return _fin(im)


# --------------------------------------------------------------------------- instruments

def bagpipes():
    im, d = _new()
    bag, bag_d = C(150, 52, 44), C(100, 32, 30)
    d.ellipse([6, 12, 24, 27], fill=bag)
    d.ellipse([8, 14, 15, 19], fill=C(190, 84, 70))
    d.arc([6, 12, 24, 27], 20, 160, fill=bag_d, width=2)
    for x, y2 in ((13, 3), (17, 2), (21, 4)):  # three drones
        _line(d, [(x - 1, 14), (x, y2)], WOOD, 2)
        _px(d, [(x, y2)], BRASS)
    _line(d, [(10, 24), (4, 30)], WOOD_D, 3)  # the chanter, with holes
    _px(d, [(8, 26), (7, 27), (6, 28)], INK)
    _line(d, [(24, 20), (30, 17)], WOOD, 2)  # the blowpipe
    d.ellipse([26, 15, 30, 18], fill=BRASS)
    return _fin(im)


def drum():
    im, d = _new()
    d.rectangle([6, 12, 25, 25], fill=C(140, 60, 44))
    d.ellipse([6, 22, 25, 28], fill=C(140, 60, 44))
    d.ellipse([6, 8, 25, 16], fill=C(222, 206, 170))
    d.ellipse([8, 9, 23, 15], outline=C(180, 160, 120))
    for x in range(7, 25, 4):  # lacing
        _line(d, [(x, 14), (x + 2, 25)], ROPE, 1)
        _line(d, [(x + 2, 14), (x + 4, 25)], ROPE_D, 1)
    d.arc([6, 9, 25, 17], 0, 180, fill=IRON_L)
    d.arc([6, 22, 25, 28], 0, 180, fill=IRON)
    _line(d, [(4, 3), (16, 11)], WOOD_L, 2)  # sticks
    _line(d, [(28, 3), (18, 11)], WOOD_L, 2)
    _px(d, [(3, 2), (4, 2), (28, 2), (29, 2)], WOOD_D)
    return _fin(im)


def dulcimer():
    im, d = _new()
    d.polygon([(10, 5), (22, 5), (29, 26), (3, 26)], fill=WOOD)
    d.polygon([(11, 7), (21, 7), (27, 24), (5, 24)], fill=C(158, 106, 62))
    for k in range(5):  # strings
        x0 = 12 + k * 2
        x1 = 8 + k * 4
        _line(d, [(x0, 7), (x1, 24)], C(226, 220, 200))
    _px(d, [(11, 4), (13, 4), (15, 4), (17, 4), (19, 4), (21, 4)], BRASS)
    d.ellipse([14, 19, 18, 22], fill=WOOD_D)
    _line(d, [(2, 29), (12, 21)], WOOD_L, 1)  # a hammer
    d.ellipse([12, 20, 14, 22], fill=WOOD_D)
    return _fin(im)


def lyre():
    im, d = _new()
    d.ellipse([9, 20, 23, 30], fill=WOOD)
    d.ellipse([11, 22, 21, 28], fill=C(160, 108, 62))
    d.ellipse([14, 24, 18, 27], fill=WOOD_D)
    d.arc([3, 2, 17, 26], 90, 180, fill=WOOD, width=2)
    d.arc([15, 2, 29, 26], 0, 90, fill=WOOD, width=2)
    _line(d, [(3, 8), (3, 4)], WOOD, 2)
    _line(d, [(28, 8), (28, 4)], WOOD, 2)
    d.rectangle([3, 4, 28, 6], fill=BRASS_D)
    _line(d, [(3, 4), (28, 4)], BRASS_L)
    for x in (9, 12, 15, 18, 21, 24):
        _line(d, [(x, 7), (x, 22)], C(226, 220, 200))
    return _fin(im)


def pan_flute():
    im, d = _new()
    tube, tube_d = C(190, 156, 98), C(132, 100, 56)
    for k in range(6):
        x = 3 + k * 4
        top = 6 + k * 3
        d.rectangle([x, top, x + 3, 26], fill=tube)
        _line(d, [(x, top), (x, 26)], C(222, 192, 134))
        _line(d, [(x + 3, top), (x + 3, 26)], tube_d)
        d.rectangle([x + 1, top, x + 2, top + 1], fill=INK)
    d.rectangle([2, 15, 28, 16], fill=RED)
    d.rectangle([2, 21, 28, 22], fill=RED)
    return _fin(im)


def shawm():
    im, d = _new()
    d.rectangle([24, 2, 28, 5], fill=BRASS_L)  # the reed
    _line(d, [(24, 5), (20, 9)], BRASS, 2)
    _line(d, [(21, 8), (12, 17)], WOOD_D, 4)
    _line(d, [(20, 8), (11, 17)], WOOD, 1)
    d.polygon([(10, 15), (15, 20), (13, 30), (3, 30), (2, 22)], fill=WOOD_D)  # the wide flared bell
    d.polygon([(10, 15), (12, 17), (6, 30), (3, 30), (2, 22)], fill=WOOD)
    d.polygon([(2, 22), (3, 30), (13, 30), (15, 20), (15, 22), (13, 28), (4, 28), (4, 22)], fill=BRASS)
    d.ellipse([3, 25, 12, 30], fill=INK)
    _px(d, [(19, 10), (17, 12), (15, 14)], INK)
    return _fin(im)


def viol():
    im, d = _new()
    wood, wood_h = C(150, 92, 48), C(196, 130, 72)
    d.ellipse([9, 18, 21, 30], fill=wood)
    d.ellipse([11, 12, 21, 22], fill=wood)
    d.ellipse([10, 21, 15, 26], fill=wood_h)
    _line(d, [(17, 16), (28, 5)], WOOD_D, 3)
    d.ellipse([27, 2, 31, 6], fill=WOOD_D)
    _line(d, [(15, 25), (28, 6)], C(226, 220, 200))  # strings
    d.rectangle([13, 23, 16, 24], fill=INK)
    _line(d, [(2, 17), (13, 5)], WOOD_L, 2)  # the bow, apart
    _line(d, [(4, 18), (14, 7)], C(236, 232, 214))
    d.rectangle([1, 16, 4, 19], fill=WOOD_D)
    return _fin(im)


# --------------------------------------------------------------------------- adventuring gear

def ball_bearings():
    im, d = _new()
    balls = [(16, 8), (11, 15), (21, 15), (7, 22), (16, 22), (25, 22)]
    for x, y in balls:
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=IRON)
        d.ellipse([x - 3, y - 3, x, y], fill=IRON_L)
        _px(d, [(x - 2, y - 2)], C(220, 224, 232))
    return _fin(im)


def pearl():
    """A pearl on a scrap of dark velvet (a costly spell component: Identify)."""
    im, d = _new()
    d.rounded_rectangle([5, 16, 27, 26], radius=3, fill=C(48, 34, 72))
    d.rounded_rectangle([6, 17, 26, 21], radius=2, fill=C(66, 48, 98))
    d.ellipse([11, 9, 21, 19], fill=C(196, 188, 182))
    d.ellipse([11, 9, 20, 17], fill=C(226, 220, 212))
    d.ellipse([12, 10, 18, 15], fill=C(242, 236, 230))
    _px(d, [(14, 11), (15, 11), (14, 12)], C(255, 255, 255))
    _px(d, [(19, 16), (18, 17)], C(222, 196, 204))  # (a blush of pink on the shadowed side)
    return _fin(im)


def caltrops():
    im, d = _new()
    for cx, cy in ((10, 21), (22, 22), (16, 10)):
        for dx, dy in ((-6, 4), (6, 4), (0, -6)):
            _line(d, [(cx, cy), (cx + dx, cy + dy)], IRON, 2)
        _line(d, [(cx, cy), (cx, cy - 6)], IRON_L, 1)
        _px(d, [(cx - 6, cy + 4), (cx + 6, cy + 4), (cx, cy - 6)], IRON_L)
        d.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=IRON_L)
    return _fin(im)


def net():
    im, d = _new()
    cord = C(176, 150, 98)
    mask = Image.new("L", (32, 32), 0)
    ImageDraw.Draw(mask).ellipse([3, 3, 28, 28], fill=255)
    lay = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for k in range(-32, 64, 6):
        ld.line([(k, 0), (k + 32, 32)], fill=cord, width=1)
        ld.line([(k, 32), (k + 32, 0)], fill=cord, width=1)
    im.paste(lay, (0, 0), mask)
    d.arc([3, 3, 28, 28], 0, 360, fill=ROPE_D, width=2)
    for k in (9, 15, 21):
        _px(d, [(k, 9), (k, 21), (9, k), (21, k)], ROPE_D)
    return _fin(im)


def bucket():
    im, d = _new()
    d.arc([6, 1, 25, 18], 190, 350, fill=IRON_L, width=1)
    d.polygon([(6, 10), (25, 10), (22, 28), (9, 28)], fill=WOOD)
    for x in range(9, 25, 4):
        _line(d, [(x - (x - 16) // 5, 11), (x - (x - 16) // 4, 27)], WOOD_D)
    d.ellipse([6, 8, 25, 13], fill=WOOD_L)
    d.ellipse([8, 9, 23, 12], fill=C(70, 50, 36))
    d.rectangle([6, 14, 25, 15], fill=IRON)
    d.rectangle([8, 23, 23, 24], fill=IRON)
    return _fin(im)


def barrel():
    """A cooper's barrel on its side-less stand: bellied staves, three iron hoops, a bung."""
    im, d = _new()
    d.polygon([(9, 3), (22, 3), (26, 10), (26, 21), (22, 28), (9, 28), (5, 21), (5, 10)], fill=WOOD)
    for x in (9, 13, 17, 21):
        _line(d, [(x, 4), (x + (1 if x > 15 else -1), 15), (x, 27)], WOOD_D)
    for y in (6, 15, 25):
        d.rectangle([5 if y == 15 else 7, y, 26 if y == 15 else 24, y + 1], fill=IRON)
    d.ellipse([9, 2, 22, 5], fill=WOOD_L)
    d.rectangle([15, 18, 16, 19], fill=C(60, 40, 28))
    return _fin(im)


def basket():
    im, d = _new()
    d.arc([6, 2, 25, 22], 180, 360, fill=WOOD_D, width=2)
    d.polygon([(3, 12), (28, 12), (24, 27), (7, 27)], fill=C(176, 138, 76))
    for y in range(14, 27, 3):
        _line(d, [(5, y), (26, y)], C(130, 96, 50))
    for x in range(8, 26, 4):
        _line(d, [(x, 13), (x - 1, 26)], C(214, 178, 108))
    d.ellipse([3, 10, 28, 15], fill=C(214, 178, 108))
    d.ellipse([6, 11, 25, 14], fill=C(70, 50, 36))
    return _fin(im)


def jug():
    im, d = _new()
    clay, clay_h, clay_d = C(168, 112, 70), C(210, 154, 100), C(112, 70, 44)
    d.ellipse([6, 10, 24, 29], fill=clay)
    d.rectangle([12, 4, 18, 12], fill=clay)
    d.ellipse([11, 3, 19, 6], fill=clay_h)
    d.rectangle([13, 1, 17, 4], fill=WOOD_L)
    d.arc([18, 8, 29, 20], 270, 90, fill=clay_d, width=3)
    d.ellipse([9, 14, 13, 20], fill=clay_h)
    _line(d, [(8, 18), (22, 18)], clay_d)
    return _fin(im)


def pouch():
    im, d = _new()
    d.polygon([(8, 12), (23, 12), (28, 24), (24, 29), (7, 29), (3, 24)], fill=LEATHER)
    d.polygon([(9, 14), (13, 14), (8, 26), (6, 24)], fill=LEATHER_L)
    d.polygon([(10, 12), (21, 12), (22, 6), (9, 6)], fill=LEATHER_D)  # the gathered neck
    d.rectangle([9, 11, 22, 13], fill=ROPE)
    _line(d, [(22, 12), (27, 17)], ROPE, 1)
    _px(d, [(27, 18), (26, 19)], ROPE_D)
    _line(d, [(10, 6), (9, 3), (12, 5), (15, 3), (17, 5), (20, 3), (22, 6)], LEATHER_L)
    return _fin(im)


def quiver():
    im, d = _new()
    _line(d, [(14, 15), (24, 5)], C(226, 220, 200), 1)  # shafts and fletchings
    _line(d, [(17, 16), (28, 8)], C(226, 220, 200), 1)
    _line(d, [(11, 14), (21, 3)], C(226, 220, 200), 1)
    for p in ((21, 3), (24, 5), (28, 8)):
        _px(d, [(p[0] - 1, p[1] - 1), (p[0] + 1, p[1] + 1), (p[0], p[1])], C(180, 40, 40))
    d.polygon([(2, 24), (11, 13), (19, 21), (10, 31)], fill=LEATHER)
    d.polygon([(2, 24), (11, 13), (13, 15), (4, 26)], fill=LEATHER_L)
    d.polygon([(11, 13), (19, 21), (17, 23), (9, 15)], fill=LEATHER_D)
    _line(d, [(6, 28), (16, 18)], LEATHER_D)
    _line(d, [(7, 18), (13, 24)], BRASS, 2)
    return _fin(im)


def bolt_case():
    im, d = _new()
    for x in (8, 12, 16, 20):
        _line(d, [(x, 12), (x, 6)], IRON_L)
        _px(d, [(x, 5)], IRON_L)
        _px(d, [(x - 1, 7), (x + 1, 7)], IRON)
        d.rectangle([x, 12, x, 13], fill=WOOD_L)
    d.rectangle([4, 12, 24, 28], fill=LEATHER)
    d.rectangle([4, 12, 24, 15], fill=LEATHER_D)
    _line(d, [(4, 12), (24, 12)], LEATHER_L)
    d.rectangle([4, 20, 24, 21], fill=LEATHER_D)
    d.rectangle([12, 17, 16, 23], fill=BRASS)
    _px(d, [(14, 19)], BRASS_D)
    _line(d, [(25, 13), (28, 24)], LEATHER_D, 2)
    return _fin(im)


def scroll_case():
    im, d = _new()
    d.polygon([(5, 22), (10, 27), (27, 10), (22, 5)], fill=LEATHER)
    _line(d, [(7, 21), (21, 7)], LEATHER_L)
    d.polygon([(2, 20), (8, 26), (11, 23), (5, 17)], fill=BRASS)
    d.polygon([(21, 9), (24, 5), (29, 10), (25, 13)], fill=BRASS)
    _line(d, [(4, 19), (9, 24)], BRASS_L)
    _line(d, [(14, 20), (18, 24)], LEATHER_D, 2)  # a strap
    _line(d, [(14, 20), (18, 24)], BRASS_D, 1)
    return _fin(im)


def bell():
    im, d = _new()
    d.ellipse([13, 2, 19, 7], outline=BRASS_D)
    d.polygon([(11, 6), (21, 6), (23, 18), (28, 24), (4, 24), (9, 18)], fill=BRASS)
    d.polygon([(11, 6), (14, 6), (13, 18), (8, 24), (4, 24), (9, 18)], fill=BRASS_L)
    _line(d, [(4, 24), (28, 24)], BRASS_D, 2)
    d.rectangle([5, 22, 27, 22], fill=BRASS_L)
    d.ellipse([14, 25, 18, 29], fill=IRON)
    return _fin(im)


def chain():
    im, d = _new()
    k = 0
    for t in range(0, 6):
        x, y = 4 + t * 4.4, 27 - t * 4.4
        d.ellipse([x - 3, y - 2, x + 3, y + 2] if t % 2 else [x - 2, y - 3, x + 2, y + 3], outline=IRON_L, width=2)
    for t in range(0, 6):
        x, y = 4 + t * 4.4, 27 - t * 4.4
        d.point((int(x), int(y)), fill=IRON_D)
    return _fin(im)


def pole():
    im, d = _new()
    _line(d, [(3, 29), (28, 4)], WOOD, 3)
    _line(d, [(4, 27), (27, 4)], WOOD_L, 1)
    for k in (9, 15, 21):  # foot marks
        _px(d, [(k, 33 - k - 1), (k + 1, 33 - k - 1)], BRASS)
        _line(d, [(k - 1, 33 - k + 1), (k + 2, 33 - k - 2)], WOOD_D)
    d.polygon([(2, 30), (2, 26), (6, 30)], fill=IRON)
    return _fin(im)


def magnifying_glass():
    im, d = _new()
    d.ellipse([3, 3, 21, 21], fill=BRASS)
    d.ellipse([5, 5, 19, 19], fill=C(150, 196, 214))
    d.ellipse([7, 7, 12, 11], fill=C(210, 236, 244))
    _line(d, [(19, 19), (28, 28)], WOOD, 4)
    _line(d, [(18, 18), (21, 21)], BRASS_D, 3)
    return _fin(im)


def portable_ram():
    im, d = _new()
    d.polygon([(2, 26), (7, 29), (23, 13), (18, 8)], fill=WOOD)
    _line(d, [(5, 25), (19, 11)], WOOD_L)
    _line(d, [(10, 27), (22, 15)], WOOD_D)
    d.ellipse([1, 25, 6, 30], fill=WOOD_D)
    d.polygon([(19, 6), (25, 2), (30, 7), (28, 15), (21, 15), (17, 11)], fill=IRON)
    d.polygon([(19, 6), (25, 2), (24, 8)], fill=IRON_L)
    d.rectangle([17, 9, 19, 13], fill=IRON_D)
    _line(d, [(8, 21), (6, 29)], ROPE, 2)  # two rope handles hanging below
    _line(d, [(14, 15), (12, 23)], ROPE, 2)
    return _fin(im)


def ladder():
    im, d = _new()
    _line(d, [(4, 28), (14, 3)], WOOD, 3)
    _line(d, [(14, 29), (26, 4)], WOOD, 3)
    _line(d, [(5, 26), (14, 4)], WOOD_L, 1)
    for t in range(5):
        y = 25 - t * 5
        xl = 4 + (28 - y) * 0.4
        xr = 14 + (29 - y) * 0.48
        _line(d, [(int(xl), y), (int(xr), y - 1)], WOOD_D, 2)
    return _fin(im)


def block_and_tackle():
    im, d = _new()
    _line(d, [(16, 1), (16, 4)], IRON, 2)
    d.ellipse([14, 0, 18, 3], outline=IRON_L)
    d.rectangle([9, 4, 23, 12], fill=WOOD)
    d.rectangle([9, 4, 23, 5], fill=WOOD_L)
    d.ellipse([12, 6, 20, 14], fill=IRON)
    d.ellipse([14, 8, 18, 12], fill=IRON_D)
    d.rectangle([9, 18, 23, 26], fill=WOOD)
    d.rectangle([9, 18, 23, 19], fill=WOOD_L)
    d.ellipse([12, 17, 20, 25], fill=IRON)
    d.ellipse([14, 19, 18, 23], fill=IRON_D)
    _line(d, [(12, 12), (12, 20)], ROPE, 1)
    _line(d, [(20, 12), (20, 20)], ROPE, 1)
    _line(d, [(11, 12), (11, 21)], ROPE_D, 1)
    _line(d, [(21, 21), (21, 30)], ROPE, 1)
    d.arc([12, 25, 20, 31], 0, 180, fill=IRON_L)
    return _fin(im)


def iron_spikes():
    im, d = _new()
    for x0, ang in ((7, -14), (16, 0), (25, 14)):
        a = math.radians(ang)
        def P(x, y):
            return (x0 + x * math.cos(a) - y * math.sin(a), 16 + x * math.sin(a) + y * math.cos(a))
        d.polygon([P(-4, -14), P(4, -14), P(4, -11), P(-4, -11)], fill=IRON_L)  # the flat head
        d.polygon([P(-2, -11), P(2, -11), P(1, 11), P(0, 14), P(-1, 11)], fill=IRON)
        d.line([P(-1, -10), P(-1, 10)], fill=IRON_L)
    return _fin(im)


def lock():
    im, d = _new()
    d.arc([8, 2, 23, 20], 180, 360, fill=IRON_L, width=3)
    _line(d, [(9, 11), (9, 14)], IRON_L, 3)
    _line(d, [(22, 11), (22, 14)], IRON_L, 3)
    d.rectangle([5, 14, 26, 28], fill=BRASS)
    d.rectangle([5, 14, 26, 16], fill=BRASS_L)
    d.rectangle([5, 26, 26, 28], fill=BRASS_D)
    d.ellipse([14, 18, 18, 22], fill=INK)
    d.polygon([(15, 21), (17, 21), (18, 25), (14, 25)], fill=INK)
    return _fin(im)


def signal_whistle():
    im, d = _new()
    d.rectangle([4, 12, 22, 20], fill=BRASS)
    d.rectangle([4, 12, 22, 14], fill=BRASS_L)
    d.rectangle([20, 10, 26, 17], fill=BRASS_D)
    d.rectangle([2, 14, 5, 19], fill=BRASS_L)
    d.rectangle([11, 9, 15, 12], fill=BRASS_D)
    d.ellipse([22, 20, 30, 28], outline=ROPE, width=1)
    _line(d, [(22, 19), (25, 20)], ROPE)
    return _fin(im)


def string():
    im, d = _new()
    mask = Image.new("L", (32, 32), 0)
    ImageDraw.Draw(mask).ellipse([5, 6, 25, 26], fill=255)
    lay = Image.new("RGBA", (32, 32), C(210, 196, 160))
    ld = ImageDraw.Draw(lay)
    for k in range(-30, 40, 4):
        ld.line([(k + 6, 6), (k + 26, 26)], fill=C(170, 152, 112))
    for k in range(0, 50, 5):
        ld.line([(k - 8, 26), (k + 12, 6)], fill=C(236, 226, 196))
    im.paste(lay, (0, 0), mask)
    d.ellipse([5, 6, 25, 26], outline=C(150, 130, 92))
    _line(d, [(22, 24), (27, 27), (30, 24), (27, 21)], C(190, 172, 130))
    return _fin(im)


def climbers_kit():
    im, d = _new()
    d.ellipse([9, 18, 27, 29], outline=ROPE, width=2)  # a rope coil
    d.ellipse([12, 21, 24, 26], outline=ROPE_D, width=1)
    _line(d, [(5, 4), (5, 20)], IRON_L, 3)  # a grapnel
    d.arc([0, 14, 10, 24], 20, 160, fill=IRON_L, width=2)
    d.arc([0, 12, 10, 22], 20, 160, fill=IRON_L, width=2)
    d.ellipse([3, 1, 8, 5], outline=IRON, width=1)
    _line(d, [(5, 19), (2, 17)], IRON_L, 2)
    _line(d, [(5, 19), (8, 17)], IRON_L, 2)
    # a piton and a carabiner
    _line(d, [(15, 3), (23, 10)], IRON, 2)
    d.ellipse([12, 1, 16, 5], outline=IRON_L)
    d.rounded_rectangle([24, 3, 30, 14], radius=3, outline=BRASS_L, width=2)
    return _fin(im)


# --------------------------------------------------------------------------- packs

def _backpack(d, body, body_d, body_l):
    d.rectangle([9, 9, 24, 29], fill=body)
    d.ellipse([9, 5, 24, 15], fill=body_d)  # the flap
    d.rectangle([9, 9, 24, 13], fill=body_d)
    d.rectangle([9, 13, 24, 14], fill=body_l)
    d.rectangle([11, 21, 22, 28], fill=body_d)  # front pocket
    _line(d, [(11, 21), (22, 21)], body_l)
    d.rectangle([15, 12, 18, 16], fill=BRASS)
    _px(d, [(16, 14)], BRASS_D)
    _line(d, [(11, 8), (10, 27)], LEATHER_D, 1)
    _line(d, [(22, 8), (23, 27)], LEATHER_D, 1)


def pack(name):
    im, d = _new()
    if name == "burglars":
        _backpack(d, C(70, 70, 80), C(46, 46, 56), C(104, 104, 116))
        _line(d, [(26, 9), (26, 28)], IRON_L, 3)  # a crowbar strapped on the side, hooked at the head
        _line(d, [(26, 9), (22, 5)], IRON_L, 3)
        _px(d, [(21, 4), (21, 5)], IRON_D)
        _line(d, [(24, 14), (28, 14)], LEATHER_D)
        _line(d, [(24, 22), (28, 22)], LEATHER_D)
    elif name == "diplomats":
        _backpack(d, C(130, 40, 56), C(90, 26, 40), C(168, 74, 86))
        d.rectangle([2, 12, 8, 26], fill=PAPER)  # a rolled scroll on the side with a seal
        d.ellipse([1, 10, 9, 14], fill=C(236, 224, 190))
        d.ellipse([1, 24, 9, 28], fill=PAPER_D)
        d.rectangle([2, 18, 8, 20], fill=C(190, 150, 70))
        d.ellipse([3, 17, 6, 21], fill=C(200, 40, 40))
    elif name == "dungeoneers":
        _backpack(d, C(100, 78, 54), C(70, 52, 36), C(140, 112, 80))
        d.ellipse([20, 16, 31, 29], outline=ROPE, width=2)  # a rope coil
        d.ellipse([23, 20, 28, 25], outline=ROPE_D, width=1)
        _line(d, [(5, 14), (5, 4)], WOOD, 2)  # a torch
        d.polygon([(3, 5), (5, 0), (8, 5)], fill=C(240, 150, 40))
        _px(d, [(5, 3)], C(255, 230, 120))
        _line(d, [(5, 14), (8, 12)], LEATHER_D)
    elif name == "entertainers":
        _backpack(d, C(48, 90, 70), C(30, 62, 50), C(80, 128, 104))
        _line(d, [(28, 6), (30, 3)], WOOD_D, 3)  # a lute's neck and pegs
        _line(d, [(28, 6), (24, 18)], WOOD, 3)
        d.ellipse([20, 17, 29, 26], fill=WOOD)
        d.ellipse([22, 19, 27, 24], fill=WOOD_D)
        _px(d, [(27, 4), (29, 6), (26, 8)], BRASS_L)
        _line(d, [(5, 4), (5, 18)], C(200, 60, 80), 2)  # a feathered cap's plume
        d.polygon([(2, 20), (8, 20), (7, 14), (3, 14)], fill=C(200, 60, 80))
    elif name == "explorers":
        _backpack(d, C(150, 124, 80), C(110, 88, 56), C(190, 164, 112))
        d.rectangle([7, 2, 26, 7], fill=C(120, 60, 50))  # a bedroll over the top
        d.ellipse([5, 2, 9, 7], fill=C(80, 40, 36))
        _line(d, [(12, 2), (12, 7)], LEATHER_D)
        _line(d, [(21, 2), (21, 7)], LEATHER_D)
        d.ellipse([20, 17, 31, 30], outline=ROPE, width=2)
        d.ellipse([23, 21, 28, 26], outline=ROPE_D, width=1)
    elif name == "priests":
        _backpack(d, C(190, 184, 170), C(140, 134, 120), C(226, 220, 204))
        d.ellipse([12, 21, 21, 29], fill=BRASS)
        d.ellipse([14, 23, 19, 27], fill=BRASS_L)
        for a in range(0, 360, 45):
            x = 16.5 + 6 * math.cos(math.radians(a))
            y = 25 + 6 * math.sin(math.radians(a))
            _line(d, [(16, 25), (int(x), int(y))], BRASS, 1)
        _line(d, [(5, 6), (5, 24)], BRASS, 2)  # a censer chain / candle
        d.rectangle([3, 22, 7, 28], fill=C(236, 226, 190))
        _px(d, [(5, 20), (5, 21)], C(250, 190, 70))
    elif name == "scholars":
        _backpack(d, C(48, 64, 112), C(32, 44, 84), C(80, 100, 156))
        d.polygon([(21, 4), (28, 7), (14, 14), (10, 11)], fill=PAPER)  # a scroll out of the top
        _line(d, [(10, 11), (21, 4)], C(236, 226, 196))
        d.ellipse([8, 9, 12, 13], fill=PAPER_D)
        d.rectangle([4, 17, 9, 28], fill=C(130, 40, 40))  # a book on the side
        d.rectangle([4, 17, 5, 28], fill=C(80, 24, 28))
        _line(d, [(6, 20), (8, 20)], BRASS)
        d.rectangle([23, 22, 28, 28], fill=INK)  # an ink bottle
        d.rectangle([24, 20, 27, 22], fill=GLASS)
    return _fin(im)


def mistletoe():
    im, d = _new()
    stem, leaf, leaf_d, berry = C(110, 112, 52), C(120, 160, 70), C(76, 112, 48), C(236, 232, 214)
    for tip in ((5, 6), (16, 3), (27, 7), (3, 17), (28, 18)):
        _line(d, [(16, 28), (16, 20), tip], stem, 1)
    for x, y, a in ((5, 6, 0), (16, 3, 1), (27, 7, 2), (3, 17, 0), (28, 18, 2), (10, 14, 0), (22, 14, 2), (16, 12, 1)):
        d.ellipse([x - 4, y - 2, x + 3, y + 2] if a != 1 else [x - 2, y - 1, x + 2, y + 5], fill=leaf)
        _px(d, [(x - 1, y)], leaf_d)
    for x, y in ((12, 8), (20, 8), (16, 17), (9, 21), (23, 21)):
        d.ellipse([x - 2, y - 2, x + 1, y + 1], fill=berry)
        _px(d, [(x + 1, y + 1)], C(170, 168, 150))
    return _fin(im)


def reliquary():
    im, d = _new()
    d.polygon([(3, 12), (16, 3), (29, 12), (29, 14), (3, 14)], fill=BRASS)
    d.polygon([(3, 12), (16, 3), (16, 14), (3, 14)], fill=BRASS_L)
    d.rectangle([4, 14, 27, 27], fill=BRASS)
    d.rectangle([4, 14, 7, 27], fill=BRASS_L)
    d.rectangle([4, 25, 27, 27], fill=BRASS_D)
    d.rectangle([10, 17, 21, 24], fill=C(46, 34, 50))  # glass window with a bone inside
    _line(d, [(12, 22), (19, 19)], C(226, 220, 200), 2)
    d.ellipse([14, 6, 18, 10], fill=RED)
    _px(d, [(15, 7)], C(240, 140, 130))
    _px(d, [(6, 12), (26, 12), (16, 14)], BRASS_D)
    d.rectangle([3, 27, 28, 29], fill=BRASS_D)
    return _fin(im)


# --------------------------------------------------------------------------- the lot

def all_drawn() -> dict[str, Image.Image]:
    out = {
        "alchemists_supplies": kit("alchemists"), "brewers_supplies": kit("brewers"),
        "calligraphers_supplies": kit("calligraphers"), "cartographers_tools": kit("cartographers"),
        "cobblers_tools": kit("cobblers"), "glassblowers_tools": kit("glassblowers"),
        "jewelers_tools": kit("jewelers"), "masons_tools": kit("masons"), "painters_supplies": kit("painters"),
        "potters_tools": kit("potters"), "tinkers_tools": kit("tinkers"), "weavers_tools": kit("weavers"),
        "woodcarvers_tools": kit("woodcarvers"), "forgery_kit": kit("forgery"), "poisoners_kit": kit("poisoners"),
        "dragonchess_set": dragonchess(), "three_dragon_ante_set": three_dragon_ante(),
        "bagpipes": bagpipes(), "drum": drum(), "dulcimer": dulcimer(), "lyre": lyre(), "pan_flute": pan_flute(),
        "shawm": shawm(), "viol": viol(),
        "ball_bearings": ball_bearings(), "caltrops": caltrops(), "net": net(), "bucket": bucket(), "barrel": barrel(),
        "basket": basket(), "jug": jug(), "pouch": pouch(), "quiver": quiver(), "bolt_case": bolt_case(),
        "scroll_case": scroll_case(), "bell": bell(), "chain": chain(), "pole": pole(),
        "magnifying_glass": magnifying_glass(), "portable_ram": portable_ram(), "ladder": ladder(),
        "block_and_tackle": block_and_tackle(), "iron_spikes": iron_spikes(), "lock": lock(),
        "signal_whistle": signal_whistle(), "string": string(), "climbers_kit": climbers_kit(),
        "burglars_pack": pack("burglars"), "diplomats_pack": pack("diplomats"), "dungeoneers_pack": pack("dungeoneers"),
        "entertainers_pack": pack("entertainers"), "explorers_pack": pack("explorers"),
        "priests_pack": pack("priests"), "scholars_pack": pack("scholars"),
        "mistletoe_sprig": mistletoe(), "reliquary": reliquary(), "pearl": pearl(),
    }
    return {f"item/{k}": v for k, v in out.items()}
