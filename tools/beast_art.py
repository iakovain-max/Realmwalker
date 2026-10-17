"""Riding and draught animals, saddles and vehicles, drawn by hand (Blades & Backgrounds part D).

32x32, facing right like the Crawl animals, a dark outline, a few muted colours each, no smoothing.
Animals are built from one equine frame (`_equine`) with the parts that differ (legs, neck, mane, tail, gear)
set by each picture; the saddles and vehicles are side views."""
from __future__ import annotations

from PIL import Image, ImageDraw

from tile_art import blank, outline, shadow

K = (18, 14, 10, 255)


def c(r, g, b):
    return (r, g, b, 255)


def _px(d, pts, col):
    for x, y in pts:
        d.point((x, y), fill=col)


def _equine(body, hi, low, dark, *, top=10, bot=19, gy=28, rump=7, chest=22, neck=4, mane=None, tail=None,
            tail_len=9, head=1.0, ears=1, feather=None, leg_w=2, thick=0):
    """A horse side view facing right. top/bot: the barrel; gy: the ground; neck: how far the poll is above the withers."""
    im = blank()
    d = ImageDraw.Draw(im)
    mane = mane or dark
    tail = tail or dark
    # tail first (behind the body)
    tx = rump
    d.polygon([(tx, top + 1), (tx - 2, top + 4), (tx - 4, top + 3 + tail_len // 2), (tx - 3, top + 2 + tail_len),
               (tx - 1, top + 3 + tail_len // 2), (tx + 1, top + 5)], fill=tail)
    # far legs (a shade darker), then the body, then the near legs
    fl = chest - 1
    hl = rump + 3
    for x in (fl - 3, hl + 2):
        d.rectangle([x, bot - 2, x + leg_w - 1, gy], fill=low)
        d.rectangle([x, gy - 3, x + leg_w - 1, gy], fill=dark)
    # barrel and rump
    d.polygon([(rump, top + 2), (rump + 2, top), (chest - 4, top), (chest - 1, top + 1), (chest + 1, top + 4),
               (chest + 1, bot - 3), (chest - 2, bot), (rump + 3, bot), (rump, bot - 3)], fill=body)
    d.line([(rump + 2, top + 1), (chest - 5, top + 1)], fill=hi)           # the lit back
    d.line([(rump + 1, bot - 2), (chest - 2, bot - 1)], fill=low)          # the shaded belly
    # hind leg: thigh, hock, cannon
    d.polygon([(rump - 1, top + 4), (rump + 4, top + 3), (rump + 5, bot), (rump + 3, bot + 3), (rump + 3, gy - 4),
               (rump + 1, gy - 4), (rump + 1, bot + 2), (rump - 1, bot - 1)], fill=body)
    d.rectangle([rump + 1, bot + 3, rump + 1 + leg_w - 1, gy], fill=body)
    d.rectangle([rump + 1, gy - 3, rump + leg_w, gy], fill=dark)
    # near front leg
    d.rectangle([chest - 2, bot - 3, chest - 3 + leg_w, gy], fill=body)
    d.rectangle([chest - 2, gy - 3, chest - 3 + leg_w, gy], fill=dark)
    # neck and head
    wy = top + 1                                       # withers height
    nx = chest - 3
    d.polygon([(nx - 3, wy), (nx + 1, wy - neck), (nx + 3, wy - neck - 1), (nx + 6, wy - neck + 3), (nx + 6, wy + 4),
               (chest + 1, top + 7), (chest - 3, top + 5)], fill=body)
    hx, hy = nx + 3, wy - neck - 1                      # the poll
    hl_ = int(round(6 * head))
    d.polygon([(hx, hy), (hx + 2, hy - 1), (hx + 2 + hl_, hy + hl_ - 1), (hx + 2 + hl_, hy + hl_ + 1),
               (hx + 1 + hl_, hy + hl_ + 2), (hx + 2, hy + 5), (hx, hy + 4)], fill=body)
    d.line([(hx + 1, hy), (hx + hl_ + 1, hy + hl_ - 1)], fill=hi)
    d.rectangle([hx + hl_, hy + hl_, hx + hl_ + 2, hy + hl_ + 2], fill=low)            # the muzzle
    d.point((hx + 3, hy + 2), fill=K)                                                  # the eye
    # ears
    for i in range(ears):
        d.line([(hx + i, hy - 1), (hx + i, hy - 3)], fill=body)
        d.point((hx + i, hy - 3), fill=dark)
    # mane down the crest
    d.line([(nx - 3, wy), (nx + 1, wy - neck), (hx - 1, hy)], fill=mane, width=2)
    d.point((hx + 1, hy - 1), fill=mane)
    if feather:
        for x in (fl - 3, hl + 2, rump + 1, chest - 2):
            d.rectangle([x - 1, gy - 3, x + leg_w, gy - 1], fill=feather)
    return im, d


def _finish(im):
    return shadow(outline(im))


def riding_horse() -> Image.Image:
    im, d = _equine(c(122, 70, 40), c(156, 96, 56), c(88, 48, 28), c(34, 24, 20), top=8, bot=17, gy=29, rump=5, chest=22, neck=6,
                    head=1.2, tail_len=11)
    return _finish(im)


def pony() -> Image.Image:
    im, d = _equine(c(150, 132, 98), c(180, 164, 124), c(112, 96, 70), c(66, 54, 42), top=13, bot=21, gy=28,
                    rump=8, chest=22, neck=3, mane=c(70, 58, 44), tail=c(70, 58, 44), tail_len=7, head=0.85, leg_w=2)
    d = ImageDraw.Draw(im)
    d.rectangle([20, 8, 26, 10], fill=c(70, 58, 44))   # a thick forelock and mane
    d.line([(8, 13), (19, 13)], fill=c(120, 104, 76))
    return _finish(im)


def draft_horse() -> Image.Image:
    im, d = _equine(c(138, 78, 42), c(170, 102, 58), c(98, 54, 30), c(52, 34, 24), top=9, bot=20, gy=28, rump=6,
                    chest=23, neck=4, mane=c(222, 214, 196), tail=c(222, 214, 196), head=1.0, feather=c(224, 218, 200),
                    leg_w=3)
    # the collar about the neck, and a strap across the back
    d.polygon([(20, 10), (24, 7), (27, 9), (27, 14), (24, 16), (21, 14)], outline=c(60, 38, 22), fill=None)
    d.line([(21, 9), (21, 14)], fill=c(90, 58, 34), width=2)
    d.line([(14, 10), (14, 17)], fill=c(60, 38, 22))
    d.point((14, 10), fill=c(190, 160, 70))
    return _finish(im)


def mule() -> Image.Image:
    im, d = _equine(c(120, 108, 94), c(148, 136, 118), c(90, 80, 68), c(54, 48, 42), neck=4, tail_len=6, ears=1,
                    mane=c(60, 54, 48), head=1.0)
    d = ImageDraw.Draw(im)
    # long ears
    d.line([(24, 4), (23, 0)], fill=c(120, 108, 94), width=2)
    d.line([(26, 5), (28, 1)], fill=c(120, 108, 94), width=2)
    d.point((23, 0), fill=c(54, 48, 42))
    d.point((28, 1), fill=c(54, 48, 42))
    # the thin tail with a tuft
    d.line([(6, 12), (4, 19)], fill=c(54, 48, 42))
    d.rectangle([3, 19, 4, 22], fill=c(54, 48, 42))
    # pack saddle with two bundles
    d.rectangle([9, 9, 17, 10], fill=c(110, 74, 42))
    d.rectangle([8, 11, 12, 17], fill=c(168, 140, 84))
    d.rectangle([14, 11, 18, 17], fill=c(150, 78, 60))
    d.line([(8, 11), (12, 11)], fill=c(200, 176, 118))
    d.line([(14, 11), (18, 11)], fill=c(184, 108, 84))
    d.line([(8, 14), (18, 14)], fill=c(70, 46, 28))
    return _finish(im)


def warhorse() -> Image.Image:
    im, d = _equine(c(70, 60, 56), c(98, 86, 78), c(48, 40, 38), c(26, 20, 18), top=9, bot=19, gy=28, rump=6,
                    chest=23, neck=4, leg_w=3)
    d = ImageDraw.Draw(im)
    cloth, cloth_hi, trim = c(122, 36, 38), c(156, 56, 54), c(196, 164, 84)
    # caparison hanging over the body
    d.polygon([(6, 11), (10, 9), (19, 9), (23, 11), (23, 22), (20, 24), (9, 24), (6, 22)], fill=cloth)
    d.line([(10, 10), (19, 10)], fill=cloth_hi)
    d.line([(6, 23), (9, 25), (20, 25), (23, 23)], fill=trim)
    d.line([(6, 11), (6, 22)], fill=trim)
    d.line([(23, 11), (23, 22)], fill=trim)
    d.point((14, 16), fill=trim)
    d.point((13, 17), fill=trim)
    d.point((15, 17), fill=trim)
    d.point((14, 18), fill=trim)
    # a metal chanfron on the face
    steel, steel_hi = c(150, 156, 164), c(200, 206, 212)
    d.polygon([(27, 4), (29, 5), (32 - 1, 11), (29, 12), (28, 10), (27, 7)], fill=steel)
    d.line([(28, 5), (30, 10)], fill=steel_hi)
    d.point((28, 4), fill=c(196, 164, 84))
    return _finish(im)


def camel() -> Image.Image:
    body, hi, low, dark = c(176, 144, 90), c(206, 176, 118), c(134, 106, 64), c(84, 62, 38)
    im = blank()
    d = ImageDraw.Draw(im)
    # far legs
    for x in (8, 20):
        d.line([(x, 17), (x, 28)], fill=low, width=2)
    # tail
    d.line([(5, 12), (4, 19)], fill=dark)
    # body with the hump
    d.polygon([(5, 14), (8, 11), (10, 6), (13, 5), (15, 7), (16, 11), (21, 11), (23, 13), (23, 18), (20, 20), (8, 20),
               (5, 18)], fill=body)
    d.line([(10, 7), (13, 6)], fill=hi)
    d.line([(7, 12), (22, 12)], fill=hi)
    d.line([(7, 19), (21, 19)], fill=low)
    # near legs: long, knobbly, with a bend at the knee
    for x, k in ((6, 0), (19, 1)):
        d.polygon([(x, 17), (x + 3, 17), (x + 3, 23), (x + 2, 28), (x, 28), (x, 23)], fill=body)
        d.rectangle([x, 23, x + 3, 24], fill=low)       # the knee
        d.rectangle([x - 1, 28, x + 2, 29], fill=dark)  # the broad foot
    # curved neck up to a small head, facing right
    d.polygon([(20, 11), (22, 7), (23, 3), (25, 2), (27, 3), (26, 6), (25, 9), (24, 14), (22, 15)], fill=body)
    d.line([(22, 10), (24, 3)], fill=hi)
    d.polygon([(25, 2), (29, 2), (31, 4), (31, 6), (28, 7), (25, 6)], fill=body)
    d.rectangle([29, 5, 31, 6], fill=low)
    d.point((27, 3), fill=K)
    d.point((25, 1), fill=dark)
    d.line([(21, 9), (23, 5)], fill=dark)               # a few hairs on the neck
    return _finish(im)


# ---- small beasts: the familiar's forms the Crawl pack lacks (Expansion 3 F.1) -----------------------------------
def cat() -> Image.Image:
    """A grey tabby sitting half-turned, tail curled round its feet: small on its square, as a cat is."""
    body, hi, low, dark = c(128, 120, 112), c(168, 160, 150), c(92, 86, 80), c(52, 48, 46)
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(9, 27), (6, 26), (5, 23), (6, 20)], fill=dark, width=2)           # the tail, curled up the side
    d.ellipse([8, 17, 21, 29], fill=body)                                        # haunch and body
    d.polygon([(15, 18), (20, 14), (23, 18), (22, 28), (17, 28)], fill=body)     # chest, sitting up
    d.line([(10, 20), (13, 18)], fill=low)                                       # tabby stripes
    d.line([(10, 23), (14, 21)], fill=low)
    d.line([(11, 26), (15, 24)], fill=low)
    d.rectangle([18, 25, 19, 28], fill=hi)                                       # the forepaws
    d.rectangle([21, 25, 22, 28], fill=hi)
    d.ellipse([18, 9, 27, 17], fill=body)                                        # the head
    d.polygon([(19, 11), (19, 6), (22, 9)], fill=body)                           # ears
    d.polygon([(24, 9), (27, 6), (27, 11)], fill=body)
    d.point((20, 8), fill=c(196, 150, 140))
    d.point((26, 8), fill=c(196, 150, 140))
    d.point((22, 12), fill=c(150, 196, 96))                                      # green eyes
    d.point((25, 12), fill=c(150, 196, 96))
    d.point((24, 14), fill=c(196, 150, 140))                                     # the nose
    d.line([(20, 15), (26, 15)], fill=hi)                                        # a pale muzzle
    d.line([(18, 10), (21, 9)], fill=low)
    return _finish(im)


def owl() -> Image.Image:
    """A tawny owl perched upright on the ground, round-faced, wings folded."""
    body, hi, low, dark = c(140, 104, 64), c(184, 150, 104), c(102, 74, 44), c(58, 40, 24)
    face = c(206, 184, 146)
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse([10, 13, 23, 29], fill=body)                                       # the body
    d.polygon([(10, 18), (8, 26), (12, 29), (14, 20)], fill=low)                 # the folded wing
    for y in (19, 22, 25):                                                       # breast markings
        d.point((17, y), fill=dark)
        d.point((20, y + 1), fill=dark)
    d.ellipse([11, 6, 24, 18], fill=body)                                        # the head
    d.polygon([(11, 8), (12, 4), (14, 7)], fill=body)                            # ear tufts
    d.polygon([(21, 7), (23, 4), (24, 8)], fill=body)
    d.ellipse([12, 8, 23, 17], fill=face)                                        # the facial disc
    d.line([(17, 8), (17, 16)], fill=low)
    d.rectangle([13, 10, 15, 12], fill=c(232, 176, 40))                          # great yellow eyes
    d.rectangle([19, 10, 21, 12], fill=c(232, 176, 40))
    d.point((14, 11), fill=K)
    d.point((20, 11), fill=K)
    d.polygon([(17, 13), (16, 14), (17, 16), (18, 14)], fill=dark)               # the beak
    d.line([(14, 29), (15, 30)], fill=c(160, 150, 120))                          # talons
    d.line([(19, 29), (20, 30)], fill=c(160, 150, 120))
    d.line([(13, 6), (22, 6)], fill=hi)
    return _finish(im)


def weasel(body=c(150, 92, 48), hi=c(186, 124, 70), low=c(110, 64, 32), dark=c(62, 36, 20),
           belly=c(222, 206, 176)) -> Image.Image:
    """A weasel stretched low and long, head up and alert, a pale belly under a russet back."""
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(3, 23), (6, 24), (9, 24)], fill=dark, width=2)                      # the tail, black at the tip
    d.line([(6, 24), (9, 24)], fill=body, width=2)
    d.ellipse([7, 20, 24, 27], fill=body)                                        # the long body
    d.line([(10, 26), (22, 26)], fill=belly)
    d.line([(9, 21), (21, 21)], fill=hi)
    for x in (9, 12, 19, 22):                                                    # short legs
        d.rectangle([x, 26, x + 1, 29], fill=low)
    d.polygon([(21, 21), (24, 16), (27, 16), (27, 22), (24, 24)], fill=body)     # the neck, raised
    d.line([(25, 18), (25, 23)], fill=belly)
    d.ellipse([23, 12, 30, 18], fill=body)                                       # the head
    d.rectangle([28, 15, 31, 17], fill=belly)                                    # the muzzle
    d.point((31, 15), fill=K)
    d.point((26, 14), fill=K)                                                    # the eye
    d.point((24, 12), fill=dark)                                                 # a round ear
    return _finish(im)


# ---- saddles ---------------------------------------------------------------------------------------------------

def _saddle(leather, hi, dark, *, high=False, iron=None, pad=None):
    im = blank()
    d = ImageDraw.Draw(im)
    # skirt (the flap) and seat
    d.polygon([(6, 13), (26, 13), (27, 22), (22, 24), (10, 24), (5, 22)], fill=leather)
    d.line([(7, 14), (25, 14)], fill=hi)
    d.line([(7, 22), (26, 22)], fill=dark)
    if high:
        d.polygon([(4, 8), (9, 7), (10, 14), (5, 14)], fill=leather)      # the cantle
        d.polygon([(23, 6), (27, 6), (28, 14), (22, 14)], fill=leather)   # the pommel
        d.line([(5, 8), (8, 8)], fill=hi)
        d.line([(23, 6), (27, 6)], fill=hi)
    else:
        d.polygon([(6, 10), (11, 10), (12, 14), (6, 14)], fill=leather)
        d.polygon([(21, 9), (25, 10), (26, 14), (21, 14)], fill=leather)
        d.line([(6, 10), (10, 10)], fill=hi)
        d.line([(21, 9), (24, 10)], fill=hi)
    d.rectangle([11, 11, 21, 13], fill=hi if pad is None else pad)       # the seat
    # girth strap and stirrup
    d.line([(15, 24), (15, 27)], fill=dark)
    d.polygon([(13, 27), (18, 27), (18, 30), (13, 30)], outline=iron or c(150, 150, 152), fill=None)
    d.point((15, 28), fill=(0, 0, 0, 0))
    if iron:
        for p in ((5, 8), (8, 8), (24, 6), (26, 6), (6, 21), (25, 21)):
            d.point(p, fill=iron)
    return outline(im)


def riding_saddle() -> Image.Image:
    return shadow(_saddle(c(130, 82, 46), c(168, 112, 66), c(84, 52, 30)))


def military_saddle() -> Image.Image:
    return shadow(_saddle(c(96, 62, 38), c(130, 88, 56), c(58, 38, 24), high=True, iron=c(170, 174, 182)))


def exotic_saddle() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    cloth, cloth_hi, gold, leather = c(126, 40, 44), c(164, 64, 62), c(200, 168, 84), c(110, 72, 42)
    d.polygon([(4, 14), (7, 6), (25, 6), (28, 14), (28, 24), (22, 26), (10, 26), (4, 24)], fill=cloth)   # the seat
    d.rectangle([8, 8, 24, 12], fill=cloth_hi)                                                          # padded cushion
    for x in (11, 15, 19):
        d.line([(x, 8), (x, 12)], fill=cloth)
    d.line([(8, 7), (24, 7)], fill=gold)
    d.line([(5, 14), (27, 14)], fill=gold)
    d.line([(5, 24), (27, 24)], fill=gold)
    d.rectangle([5, 6, 7, 14], fill=leather)    # a high back rail
    d.rectangle([25, 6, 27, 14], fill=leather)
    d.line([(10, 15), (10, 25)], fill=leather)  # straps
    d.line([(21, 15), (21, 25)], fill=leather)
    d.rectangle([9, 18, 11, 19], fill=gold)
    d.rectangle([20, 18, 22, 19], fill=gold)
    d.line([(15, 26), (15, 29)], fill=leather)
    d.polygon([(13, 29), (18, 29), (18, 31), (13, 31)], outline=gold, fill=None)
    return shadow(outline(im))


# ---- vehicles --------------------------------------------------------------------------------------------------

def _wheel(d, cx, cy, r, rim, spoke, hub):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rim, fill=None)
    if r > 4:
        d.ellipse([cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1], outline=rim, fill=None)
    for dx, dy in ((r - 1, 0), (-(r - 1), 0), (0, r - 1), (0, -(r - 1)), (r * 2 // 3, r * 2 // 3),
                   (-(r * 2 // 3), r * 2 // 3), (r * 2 // 3, -(r * 2 // 3)), (-(r * 2 // 3), -(r * 2 // 3))):
        d.line([(cx, cy), (cx + dx, cy + dy)], fill=spoke)
    d.rectangle([cx - 1, cy - 1, cx + 1, cy + 1], fill=hub)


WOOD, WOOD_HI, WOOD_LO = c(128, 88, 52), c(164, 118, 72), c(88, 58, 34)
IRON = c(120, 122, 128)


def cart() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(15, 19), (31, 17)], fill=WOOD_LO, width=2)              # the shafts, forward to the right
    d.line([(15, 20), (31, 18)], fill=WOOD, width=1)
    d.polygon([(4, 11), (24, 11), (22, 20), (6, 20)], fill=WOOD)     # the open box
    d.line([(4, 11), (24, 11)], fill=WOOD_HI)
    for x in (9, 14, 19):
        d.line([(x, 12), (x, 19)], fill=WOOD_LO)
    d.line([(6, 19), (22, 19)], fill=WOOD_LO)
    d.polygon([(7, 11), (10, 8), (14, 9), (13, 11)], fill=c(176, 150, 92))   # a heap of sacks in it
    d.polygon([(14, 11), (17, 8), (21, 10), (21, 11)], fill=c(150, 120, 74))
    _wheel(d, 14, 22, 6, WOOD_LO, WOOD, IRON)
    return shadow(outline(im))


def wagon() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(24, 22), (31, 20)], fill=WOOD_LO, width=2)               # the tongue
    d.polygon([(2, 14), (25, 14), (24, 22), (3, 22)], fill=WOOD)       # the bed
    d.line([(2, 14), (25, 14)], fill=WOOD_HI)
    for x in (7, 12, 17, 22):
        d.line([(x, 15), (x, 21)], fill=WOOD_LO)
    d.line([(3, 21), (24, 21)], fill=WOOD_LO)
    canvas, canvas_hi, canvas_lo = c(204, 192, 160), c(228, 218, 186), c(158, 146, 116)
    d.polygon([(3, 14), (4, 8), (8, 4), (17, 3), (22, 6), (25, 9), (25, 14)], fill=canvas)   # the canvas cover
    d.line([(6, 7), (10, 4)], fill=canvas_hi)
    d.line([(10, 4), (17, 4)], fill=canvas_hi)
    for x in (8, 14, 20):
        d.line([(x, 5), (x, 13)], fill=canvas_lo)
    d.line([(3, 13), (25, 13)], fill=canvas_lo)
    _wheel(d, 7, 24, 5, WOOD_LO, WOOD, IRON)
    _wheel(d, 20, 24, 5, WOOD_LO, WOOD, IRON)
    d.rectangle([5, 22, 22, 23], fill=WOOD_LO)    # the axle beam showing between wheels
    return shadow(outline(im))


def carriage() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    lac, lac_hi, lac_lo, brass = c(52, 36, 56), c(84, 62, 88), c(34, 24, 38), c(206, 170, 80)
    d.line([(25, 22), (31, 20)], fill=WOOD_LO, width=2)                # the pole
    d.polygon([(8, 4), (22, 4), (24, 7), (24, 9), (6, 9), (6, 7)], fill=lac_lo)               # the roof
    d.line([(8, 4), (22, 4)], fill=brass)
    d.polygon([(5, 9), (25, 9), (25, 21), (5, 21)], fill=lac)                                  # the cabin
    d.line([(6, 10), (24, 10)], fill=lac_hi)
    d.rectangle([9, 11, 13, 16], fill=c(120, 148, 160))     # a small window
    d.rectangle([9, 11, 13, 11], fill=brass)
    d.line([(11, 12), (11, 16)], fill=c(88, 112, 124))
    d.rectangle([16, 11, 22, 19], outline=brass, fill=None)  # the door
    d.point((21, 15), fill=brass)
    d.line([(5, 20), (25, 20)], fill=brass)
    d.rectangle([2, 21, 6, 23], fill=lac_lo)                 # the rear step
    _wheel(d, 9, 24, 5, lac_lo, brass, brass)
    _wheel(d, 21, 24, 5, lac_lo, brass, brass)
    d.rectangle([4, 3, 5, 4], fill=brass)                    # a lamp
    return shadow(outline(im))


def chariot() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(14, 20), (31, 13)], fill=WOOD_LO, width=2)                  # the pole, rising to the yoke
    d.line([(14, 21), (31, 14)], fill=WOOD, width=1)
    d.polygon([(6, 8), (16, 8), (20, 10), (22, 14), (20, 18), (6, 18)], fill=WOOD)   # a low curved front
    d.line([(6, 8), (16, 8)], fill=WOOD_HI)
    d.line([(16, 8), (20, 10), (22, 14)], fill=c(196, 164, 84))              # brass rim
    d.polygon([(6, 8), (6, 18), (9, 18), (9, 10)], fill=WOOD_LO)
    d.line([(10, 18), (20, 18)], fill=WOOD_LO)
    d.rectangle([12, 11, 16, 14], fill=c(122, 36, 38))     # a painted shield panel
    _wheel(d, 12, 23, 7, WOOD_LO, WOOD, IRON)
    return shadow(outline(im))


def sled() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(4, 25), (26, 25)], fill=c(70, 52, 38), width=2)               # runners
    d.line([(26, 25), (29, 21)], fill=c(70, 52, 38), width=2)               # curled front
    d.line([(4, 26), (24, 26)], fill=c(150, 150, 156))                      # iron shoe
    d.line([(8, 23), (8, 25)], fill=WOOD_LO)
    d.line([(14, 23), (14, 25)], fill=WOOD_LO)
    d.line([(21, 23), (21, 25)], fill=WOOD_LO)
    d.rectangle([5, 20, 25, 22], fill=WOOD)                                  # the low bed
    d.line([(5, 20), (25, 20)], fill=WOOD_HI)
    d.polygon([(7, 20), (9, 14), (17, 12), (22, 15), (23, 20)], fill=c(170, 140, 90))   # a bundle
    d.line([(9, 15), (16, 13)], fill=c(204, 178, 124))
    d.line([(8, 17), (22, 17)], fill=c(72, 50, 32))                           # the lashing
    d.line([(15, 13), (15, 20)], fill=c(72, 50, 32))
    return shadow(outline(im))



# ---------------------------------------------------------------------------- Animate Objects (Expansion 3 F.3)
# Things that have sprouted legs: a chest, a table and a statue under a roof; a stone, a log and a boulder outside.
# Side views facing right, the legs thin and jointed like a crab's, so a thing on the field reads as alive.
LEG, LEG_HI = c(58, 46, 36), c(96, 80, 62)


def _legs(d, feet: list[tuple[int, int]], top: int, gy: int = 28) -> None:
    """Jointed legs from the underside (`top`) to the ground, each bent outwards at the knee."""
    for x, lean in feet:
        knee = (x + lean * 2, top + (gy - top) // 2)
        d.line([(x, top), knee], fill=LEG)
        d.line([knee, (x + lean, gy)], fill=LEG)
        d.point(knee, fill=LEG_HI)


def animated_chest() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    _legs(d, [(8, -1), (12, 1), (19, -1), (23, 1)], 21)
    d.rectangle([5, 12, 26, 21], fill=WOOD)                          # the box
    d.polygon([(5, 12), (7, 8), (24, 8), (26, 12)], fill=WOOD_HI)    # the lid, ajar like a mouth
    d.line([(6, 12), (25, 12)], fill=c(30, 18, 12))                  # the dark gap under the lid
    for x in (9, 22):
        d.line([(x, 8), (x, 21)], fill=IRON)                          # iron bands
    d.rectangle([14, 13, 17, 16], fill=c(190, 160, 70))              # the lock
    d.point((15, 15), fill=K)
    d.line([(5, 21), (26, 21)], fill=WOOD_LO)
    return shadow(outline(im))


def animated_table() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    _legs(d, [(5, -1), (10, 1), (21, -1), (26, 1)], 15)
    for x in (6, 25):                                                 # its own carved legs, lifted like arms
        d.line([(x, 14), (x + (-3 if x < 15 else 3), 6)], fill=WOOD_LO, width=2)
    d.rectangle([2, 12, 29, 15], fill=WOOD)                           # the top
    d.line([(2, 12), (29, 12)], fill=WOOD_HI)
    d.line([(3, 15), (28, 15)], fill=WOOD_LO)
    d.rectangle([8, 16, 23, 17], fill=WOOD_LO)                        # the apron
    return shadow(outline(im))


def animated_statue() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone, hi, lo = c(150, 148, 140), c(190, 188, 178), c(104, 102, 98)
    _legs(d, [(10, -1), (21, 1)], 25)
    d.rectangle([8, 22, 23, 25], fill=lo)                             # the plinth, walking
    d.polygon([(12, 22), (11, 13), (13, 9), (18, 9), (20, 13), (19, 22)], fill=stone)   # the robed body
    d.line([(13, 10), (13, 21)], fill=hi)
    d.line([(18, 12), (18, 21)], fill=lo)
    d.ellipse([12, 3, 18, 9], fill=stone)                             # the head
    d.point((16, 6), fill=c(120, 220, 230))                          # an eye lit from within
    d.line([(19, 12), (25, 7)], fill=stone, width=2)                  # a raised arm
    d.line([(12, 12), (8, 17)], fill=stone, width=2)
    return shadow(outline(im))


def animated_stone() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone, hi, lo = c(132, 124, 112), c(170, 162, 148), c(92, 86, 78)
    _legs(d, [(10, -1), (14, 1), (18, -1), (22, 1)], 21)
    d.polygon([(7, 21), (8, 15), (12, 11), (19, 10), (24, 13), (26, 19), (24, 22), (9, 22)], fill=stone)
    d.line([(11, 13), (18, 11)], fill=hi)
    d.line([(9, 21), (24, 21)], fill=lo)
    d.line([(15, 13), (17, 17), (21, 18)], fill=lo)                    # a crack
    return shadow(outline(im))


def animated_log() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    bark, hi, lo = c(98, 70, 44), c(132, 98, 62), c(66, 46, 30)
    _legs(d, [(5, -1), (10, 1), (16, -1), (21, 1), (26, 1)], 19)
    d.rectangle([3, 12, 27, 19], fill=bark)                           # the trunk
    d.line([(4, 12), (26, 12)], fill=hi)
    d.line([(4, 19), (26, 19)], fill=lo)
    for x in (9, 15, 21):
        d.line([(x, 14), (x + 2, 17)], fill=lo)                       # the bark's furrows
    d.ellipse([25, 11, 30, 20], fill=c(176, 140, 92))                 # the cut end, ringed
    d.ellipse([26, 13, 29, 18], outline=c(140, 106, 66))
    d.line([(8, 12), (6, 7)], fill=bark, width=2)                     # a broken branch
    return shadow(outline(im))


def animated_boulder() -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone, hi, lo = c(118, 112, 104), c(160, 154, 142), c(80, 76, 70)
    _legs(d, [(6, -1), (11, 1), (20, -1), (25, 1)], 22)
    d.ellipse([3, 4, 28, 24], fill=stone)                             # the boulder
    d.arc([5, 5, 26, 22], 200, 300, fill=hi)
    d.line([(6, 20), (25, 21)], fill=lo)
    d.line([(10, 9), (14, 14), (12, 19)], fill=lo)                    # cracks
    d.line([(19, 7), (21, 12)], fill=lo)
    d.ellipse([16, 9, 18, 11], fill=c(96, 132, 70))                   # moss
    d.point((22, 13), fill=c(220, 120, 60))                           # a glint where its eye should be
    return shadow(outline(im))


# BEGIN F7
# ---- Expansion 3 F.7: the rest of Appendix B's beasts (big cats, elk, goats, badgers, ape, weasel, sea things, sprite)
def _chain(d, pts, fill):
    """A thick, tapering rope of discs: pts are (x, y, radius); the discs between neighbours are filled in."""
    for (x0, y0, r0), (x1, y1, r1) in zip(pts, pts[1:]):
        n = max(2, int(max(abs(x1 - x0), abs(y1 - y0)) * 2))
        for i in range(n + 1):
            t = i / n
            x, y, r = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t
            d.ellipse([round(x - r), round(y - r), round(x + r), round(y + r)], fill=fill)


def _big_cat(body, hi, low, dark, *, belly=None, mane=None, mane_hi=None, eye=None, nose=None, stripes=None,
             tail_tip=None, muzzle=None, rings=None):
    """A big cat side view facing right: low-slung, heavy shoulders, a long tail curving up at its end."""
    belly = belly or low
    tail_tip = tail_tip or dark
    muzzle = muzzle or belly
    eye = eye or c(226, 190, 60)
    nose = nose or c(150, 90, 90)
    im = blank()
    d = ImageDraw.Draw(im)
    tail = [(6, 12), (3, 11), (1, 14), (1, 18), (2, 21), (4, 21)]
    d.line(tail, fill=body, width=2, joint="curve")
    d.line(tail[-3:], fill=tail_tip, width=2, joint="curve")
    if rings:
        for p in ((2, 12), (1, 15), (1, 18)):
            d.point(p, fill=rings)
    # the far legs: one reaching forward, one back, a shade darker
    d.polygon([(22, 15), (26, 15), (25, 21), (25, 27), (27, 28), (22, 28), (23, 26), (23, 21)], fill=low)
    d.line([(22, 28), (27, 28)], fill=dark)
    d.polygon([(12, 15), (15, 15), (14, 21), (14, 27), (15, 28), (11, 28), (12, 26), (12, 21)], fill=low)
    d.line([(11, 28), (15, 28)], fill=dark)
    # body: rump, flank, shoulders higher than the loins, the deep chest
    d.polygon([(6, 12), (9, 10), (15, 10), (19, 8), (23, 8), (25, 11), (25, 16), (22, 19), (16, 18), (10, 17),
               (6, 16)], fill=body)
    d.line([(9, 10), (15, 10), (19, 8), (23, 8)], fill=hi)                         # the lit back
    d.line([(10, 16), (21, 17)], fill=belly)                                        # the paler belly
    d.line([(11, 17), (21, 18)], fill=low)
    # near hind leg: big thigh, the hock, a long paw
    d.polygon([(5, 12), (11, 11), (12, 17), (10, 21), (9, 27), (10, 28), (5, 28), (6, 26), (7, 21), (5, 17)], fill=body)
    d.line([(7, 12), (10, 12)], fill=hi)
    d.line([(6, 27), (9, 27)], fill=low)
    d.line([(5, 28), (10, 28)], fill=dark)
    # the mane, behind the head
    if mane:
        d.polygon([(18, 4), (22, 2), (27, 2), (29, 5), (30, 11), (29, 17), (26, 21), (21, 21), (17, 17), (16, 10)],
                  fill=mane)
        d.polygon([(18, 4), (22, 2), (26, 2), (23, 5), (19, 7)], fill=mane_hi or mane)
        d.line([(18, 11), (18, 17)], fill=dark)
        d.line([(21, 17), (22, 20)], fill=dark)
        d.line([(25, 18), (25, 20)], fill=dark)
    # near foreleg: thick, ending in a broad paw
    d.polygon([(16, 14), (21, 14), (21, 19), (20, 27), (21, 28), (15, 28), (17, 26), (17, 19)], fill=body)
    d.line([(18, 15), (18, 19)], fill=hi)
    d.line([(17, 27), (20, 27)], fill=low)
    d.line([(15, 28), (21, 28)], fill=dark)
    # the head, carried low and forward
    d.polygon([(22, 10), (24, 7), (28, 7), (31, 10), (31, 15), (28, 17), (24, 16), (22, 14)], fill=body)
    d.line([(24, 7), (28, 7)], fill=hi)
    d.rectangle([28, 12, 31, 16], fill=muzzle)                                    # the muzzle
    d.point((31, 11), fill=nose)
    d.point((31, 12), fill=nose)
    d.line([(29, 16), (31, 16)], fill=dark)                                       # the mouth
    d.point((27, 10), fill=eye)
    d.point((28, 10), fill=eye)
    d.line([(26, 11), (26, 13)], fill=dark)                                       # the tear line under the eye
    d.rectangle([24, 5, 26, 6], fill=body)                                        # the ear
    d.point((25, 5), fill=dark)
    d.point((25, 6), fill=c(150, 100, 100))
    if stripes:
        for x, y0, y1 in ((7, 12, 15), (9, 11, 16), (11, 10, 16), (13, 10, 16), (15, 10, 16), (17, 9, 15),
                          (19, 8, 14), (21, 8, 13), (23, 8, 11)):
            d.line([(x, y0), (x - 1, y1)], fill=stripes)
        for y in (14, 17):
            d.line([(6, y), (8, y)], fill=stripes)                                # the thigh
        d.line([(26, 8), (27, 10)], fill=stripes)                                 # the face
        d.line([(24, 12), (26, 15)], fill=stripes)
        d.line([(23, 9), (24, 11)], fill=stripes)
        for y in (22, 25):
            d.line([(17, y), (20, y)], fill=stripes)
            d.line([(7, y), (9, y)], fill=stripes)
            d.line([(23, y), (25, y)], fill=stripes)
    return im, d


def lion() -> Image.Image:
    im, d = _big_cat(c(184, 140, 78), c(222, 180, 108), c(138, 98, 52), c(72, 44, 24), belly=c(214, 178, 118),
                     mane=c(92, 56, 28), mane_hi=c(124, 80, 40), tail_tip=c(52, 32, 18), muzzle=c(220, 188, 130),
                     eye=c(236, 196, 60))
    d.line([(24, 8), (28, 8)], fill=c(230, 196, 130))
    d.line([(22, 12), (22, 14)], fill=c(230, 196, 130))
    for p in ((20, 4), (23, 3), (19, 12), (20, 16), (28, 4), (29, 9)):
        d.point(p, fill=c(150, 100, 52))
    return _finish(im)


def tiger() -> Image.Image:
    im, d = _big_cat(c(206, 120, 40), c(238, 160, 70), c(150, 82, 28), c(40, 24, 16), belly=c(236, 220, 188),
                     stripes=c(34, 22, 18), muzzle=c(236, 224, 196), tail_tip=c(34, 22, 18), rings=c(34, 22, 18),
                     eye=c(236, 210, 70))
    return _finish(im)


def panther() -> Image.Image:
    im, d = _big_cat(c(40, 40, 50), c(86, 94, 112), c(58, 60, 76), c(14, 14, 20), belly=c(34, 34, 46),
                     muzzle=c(52, 52, 62), eye=c(244, 214, 60), nose=c(90, 70, 76), tail_tip=c(20, 20, 28))
    d.line([(12, 12), (18, 10)], fill=c(112, 122, 142))
    d.line([(7, 14), (9, 13)], fill=c(70, 78, 96))
    d.line([(18, 17), (20, 16)], fill=c(70, 78, 96))
    return _finish(im)


def elk() -> Image.Image:
    body, hi, low, dark = c(132, 92, 58), c(168, 124, 82), c(98, 66, 40), c(40, 28, 20)
    neck = c(82, 56, 36)
    im, d = _equine(body, hi, low, dark, top=14, bot=22, gy=30, rump=5, chest=21, neck=5, mane=c(60, 40, 26),
                    tail=body, tail_len=3, head=1.15, ears=1, leg_w=2)
    d.polygon([(5, 14), (7, 13), (9, 14), (8, 16), (6, 16)], fill=c(210, 196, 160))        # the pale rump patch
    d.line([(8, 22), (20, 22)], fill=c(204, 188, 150))                                       # a pale belly
    # the heavy neck, darker than the body, with a shaggy throat
    wy, nx = 15, 18
    d.polygon([(nx - 2, wy), (nx + 1, wy - 4), (nx + 4, wy - 2), (nx + 5, wy + 4), (nx + 4, wy + 9), (nx, wy + 7),
               (nx - 3, wy + 4)], fill=neck)
    d.line([(nx + 5, wy + 2), (nx + 4, wy + 8)], fill=c(50, 34, 22))
    # the great rack: a broad notched palm sweeping back from the brow, and a brow tine forward
    ant, ant_hi, ant_lo = c(214, 198, 160), c(246, 234, 202), c(156, 138, 102)
    d.polygon([(22, 8), (20, 6), (17, 5), (13, 4), (10, 3), (11, 1), (13, 3), (14, 0), (16, 3), (18, 0), (19, 3),
               (22, 1), (22, 4), (23, 6)], fill=ant)
    d.line([(22, 8), (20, 6), (17, 5), (13, 4)], fill=ant_lo)
    d.line([(14, 3), (14, 1)], fill=ant_hi)
    d.line([(18, 2), (18, 1)], fill=ant_hi)
    d.line([(22, 4), (22, 2)], fill=ant_hi)
    d.line([(23, 7), (26, 5), (27, 6)], fill=ant)                                          # the brow tine
    d.point((26, 5), fill=ant_hi)
    return _finish(im)


def _goat(big: bool, body, hi, low, dark, horn, beard) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    if not big:
        d.line([(8, 16), (6, 13)], fill=body, width=2)                           # the short upturned tail
        for x in (11, 21):                                                       # far legs
            d.rectangle([x, 22, x + 1, 29], fill=low)
        d.polygon([(8, 18), (11, 16), (20, 15), (24, 17), (24, 22), (21, 24), (10, 24), (8, 22)], fill=body)
        d.line([(10, 17), (21, 16)], fill=hi)
        d.line([(10, 23), (21, 23)], fill=low)
        for x in (8, 22):                                                        # near legs
            d.rectangle([x, 22, x + 2, 29], fill=body)
            d.rectangle([x, 28, x + 2, 29], fill=dark)
        d.polygon([(21, 16), (23, 12), (26, 10), (28, 13), (26, 19), (24, 21)], fill=body)          # the neck
        d.polygon([(24, 10), (28, 9), (31, 13), (31, 15), (28, 16), (25, 15)], fill=body)            # the head
        d.line([(25, 10), (28, 10)], fill=hi)
        d.rectangle([29, 13, 31, 15], fill=hi)
        d.point((31, 13), fill=K)
        d.point((27, 11), fill=K)
        d.line([(24, 9), (23, 6), (21, 5)], fill=horn)                                                # short curved horns
        d.line([(25, 9), (24, 6), (22, 5)], fill=horn)
        d.point((21, 5), fill=dark)
        d.line([(23, 11), (21, 12)], fill=low, width=1)                                               # an ear
        d.line([(28, 16), (28, 19)], fill=beard)                                                     # the beard
        d.point((28, 20), fill=beard)
    else:
        d.polygon([(3, 12), (1, 15), (3, 17), (5, 15)], fill=dark)               # the shaggy tail
        for x in (9, 20):
            d.rectangle([x, 22, x + 2, 30], fill=low)
        # shaggy body: the coat hangs in rags along the belly and chest
        d.polygon([(3, 15), (7, 9), (13, 8), (18, 7), (23, 9), (25, 13), (25, 20), (24, 24), (22, 22), (20, 26), (18, 23),
                   (15, 25), (13, 22), (10, 26), (8, 22), (5, 24), (4, 20)], fill=body)
        d.line([(7, 10), (13, 9), (18, 8), (22, 10)], fill=dark, width=1)                              # the dark ridge
        d.line([(6, 13), (11, 12)], fill=hi)
        d.line([(12, 14), (17, 12)], fill=hi)
        d.line([(8, 18), (14, 17)], fill=low)
        d.line([(15, 19), (21, 18)], fill=low)
        for x in (7, 22):                                                        # near legs
            d.rectangle([x, 22, x + 3, 30], fill=body)
            d.rectangle([x, 29, x + 3, 30], fill=dark)
            d.line([(x + 1, 22), (x + 1, 27)], fill=hi)
        d.polygon([(20, 11), (22, 6), (25, 5), (28, 8), (27, 16), (25, 19), (22, 18)], fill=body)    # neck and shoulders
        d.polygon([(25, 4), (29, 4), (31, 8), (31, 12), (28, 13), (25, 11)], fill=body)               # the head
        d.line([(26, 5), (29, 5)], fill=hi)
        d.rectangle([28, 9, 31, 12], fill=c(176, 160, 134))
        d.point((31, 9), fill=K)
        d.point((27, 7), fill=c(226, 180, 60))
        d.point((28, 7), fill=K)
        # great horns sweeping up and back clear of the shoulders, ridged, a shade darker than ivory
        _chain(d, [(26, 4, 1.9), (25, 1.4, 1.7), (22, 0.4, 1.4), (19.5, 1.2, 1.1), (18, 3.2, 0.6)], horn)
        for x, y in ((25, 3), (23, 1), (20, 1)):                                            # rings on the horn
            d.point((x, y), fill=low)
        d.point((18, 3), fill=dark)
        d.line([(24, 0), (21, 0)], fill=c(236, 224, 186))
        d.line([(28, 13), (28, 18)], fill=beard, width=2)                                            # the long beard
        d.point((28, 19), fill=beard)
        d.line([(25, 8), (23, 10)], fill=dark, width=2)
    return im


def goat() -> Image.Image:
    return _finish(_goat(False, c(206, 202, 192), c(236, 232, 222), c(150, 146, 138), c(60, 52, 48), c(214, 196, 150),
                         c(240, 236, 228)))


def giant_goat() -> Image.Image:
    return _finish(_goat(True, c(110, 98, 84), c(148, 134, 116), c(74, 66, 58), c(36, 30, 26), c(176, 158, 120),
                         c(70, 62, 54)))


def _badger(k: float, ox: int, body, hi, low, dark) -> Image.Image:
    """A badger side view facing right, drawn on a grid scaled by k so a giant one has the same build."""
    im = blank()
    d = ImageDraw.Draw(im)

    def P(x, y):
        return (round(ox + x * k), round(30 - (28 - y) * k))

    def R(x0, y0, x1, y1):
        a, b = P(x0, y0), P(x1, y1)
        return [a[0], a[1], max(b[0], a[0]), max(b[1], a[1])]

    white, stripe = c(228, 224, 212), c(26, 22, 22)
    d.polygon([P(5, 17), P(2, 18), P(3, 21), P(6, 20)], fill=low)                        # the short tail
    for x in (8, 18):
        d.rectangle(R(x, 23, x + 2, 28), fill=dark)                                       # far legs
    d.ellipse(R(4, 14, 22, 25), fill=body)                                                # the low round body
    d.line([P(7, 15), P(12, 14), P(19, 15)], fill=hi, width=max(1, round(k)))              # grizzled back
    d.line([P(8, 17), P(11, 16)], fill=low)
    d.line([P(13, 18), P(17, 17)], fill=low)
    d.line([P(6, 22), P(20, 23)], fill=dark)
    for x in (6, 16):                                                                     # near legs, stubby
        d.rectangle(R(x, 23, x + 3, 28), fill=dark)
        d.line([P(x + 1, 28), P(x + 3, 28)], fill=c(210, 200, 180))                       # the claws
    d.polygon([P(19, 15), P(23, 13), P(30, 18), P(30, 21), P(26, 23), P(20, 22)], fill=white)   # the head
    d.polygon([P(21, 14), P(24, 12), P(25, 14)], fill=stripe)                              # ear
    d.polygon([P(23, 14), P(30, 19), P(30, 20), P(26, 20), P(22, 16)], fill=stripe)        # the black eye stripe
    d.line([P(22, 21), P(28, 22)], fill=stripe)                                           # lower jaw stripe
    d.point(P(30, 19), fill=K)
    d.point(P(26, 17), fill=c(230, 226, 214))                                             # the eye in the stripe
    d.line([P(24, 14), P(29, 17)], fill=white)                                            # the white crown line
    return im


def badger() -> Image.Image:
    return _finish(_badger(0.8, 3, c(116, 114, 112), c(162, 160, 154), c(86, 84, 84), c(38, 36, 36)))


def giant_badger() -> Image.Image:
    return _finish(_badger(1.0, 0, c(82, 80, 80), c(122, 120, 116), c(58, 56, 58), c(28, 26, 28)))


def ape() -> Image.Image:
    fur, hi, low, dark = c(60, 58, 64), c(100, 98, 106), c(38, 36, 42), c(20, 18, 22)
    face, chest = c(132, 120, 110), c(92, 88, 90)
    im = blank()
    d = ImageDraw.Draw(im)
    # far arm and far leg, in the shade
    d.polygon([(19, 11), (23, 12), (24, 21), (26, 28), (21, 28), (20, 21)], fill=low)
    d.polygon([(8, 22), (14, 22), (14, 28), (16, 29), (8, 29)], fill=low)
    # the hunched trunk: shoulders highest, the back sloping down to the haunches
    d.polygon([(3, 22), (6, 15), (11, 8), (16, 4), (21, 4), (25, 8), (26, 14), (24, 21), (20, 24), (11, 25), (5, 25)],
              fill=fur)
    d.line([(7, 15), (11, 9), (16, 5), (21, 5)], fill=hi)
    d.line([(9, 17), (13, 12)], fill=hi)
    d.line([(7, 21), (12, 18)], fill=low)
    d.polygon([(19, 14), (25, 13), (24, 20), (20, 22)], fill=chest)                        # the paler chest
    d.line([(20, 15), (24, 14)], fill=hi)
    d.line([(22, 16), (22, 20)], fill=low)
    # the near leg: short, bowed, with a broad foot
    d.polygon([(6, 20), (14, 19), (16, 25), (15, 29), (5, 29), (8, 25)], fill=fur)
    d.line([(8, 21), (12, 21)], fill=hi)
    d.rectangle([5, 28, 16, 29], fill=low)
    d.line([(7, 27), (14, 27)], fill=dark)
    # the near arm, long and heavy, down to the knuckles on the ground
    d.polygon([(15, 8), (22, 8), (26, 15), (27, 23), (29, 29), (22, 29), (22, 24), (19, 17)], fill=fur)
    d.line([(16, 9), (21, 9), (25, 15), (26, 22)], fill=hi)
    d.line([(15, 9), (18, 16), (21, 24), (22, 28)], fill=dark)                              # the arm's back edge
    d.rectangle([22, 27, 29, 29], fill=low)
    d.line([(23, 27), (28, 27)], fill=dark)
    # the head, low between the shoulders: a crest, a heavy brow, a paler face
    d.polygon([(22, 6), (25, 4), (29, 5), (31, 8), (31, 13), (28, 15), (24, 14), (21, 10)], fill=fur)
    d.polygon([(22, 6), (25, 4), (28, 4), (25, 7)], fill=hi)                                # the crest
    d.polygon([(26, 9), (31, 9), (31, 13), (28, 15), (26, 13)], fill=face)
    d.line([(25, 8), (31, 8)], fill=dark)                                                   # the heavy brow
    d.point((28, 10), fill=c(214, 170, 80))
    d.point((29, 10), fill=c(214, 170, 80))
    d.point((31, 11), fill=dark)
    d.line([(28, 13), (31, 13)], fill=dark)
    return _finish(im)


def giant_weasel() -> Image.Image:
    """A giant weasel: the weasel's lithe build in a polecat's coat, dark brown with a cream mask and belly."""
    return weasel(c(92, 66, 46), c(128, 96, 68), c(64, 44, 30), c(34, 24, 18), c(214, 196, 160))

def giant_seahorse() -> Image.Image:
    body, hi, low, dark = c(66, 134, 110), c(110, 186, 156), c(40, 94, 82), c(22, 56, 56)
    belly = c(176, 214, 180)
    fin = c(170, 218, 214)
    im = blank()
    d = ImageDraw.Draw(im)
    d.polygon([(9, 12), (6, 14), (5, 18), (7, 21), (10, 20)], fill=fin)                      # the dorsal fin
    for x0, y0, x1, y1 in ((9, 13, 6, 15), (9, 15, 6, 18), (9, 18, 7, 20)):
        d.line([(x0, y0), (x1, y1)], fill=c(110, 170, 170))
    # the tail curling forward at the bottom, the trunk, the neck and the head
    _chain(d, [(15, 22, 4.2), (14, 26, 3), (17, 29, 2.4), (21, 29, 1.8), (23, 26, 1.3), (21, 24, 0.9)], body)
    _chain(d, [(20, 5, 3.2), (17, 9, 3.4), (15, 14, 5.2), (16, 19, 5.0), (15, 23, 3.8)], body)
    # the paler belly on the front of the trunk
    _chain(d, [(19, 13, 2.2), (20, 17, 2.4), (19, 21, 1.8)], belly)
    for y in (12, 15, 18, 21, 24):                                                           # the body's rings
        d.line([(12 if y < 20 else 13, y), (19 if y < 20 else 17, y)], fill=low)
    d.line([(12, 11), (14, 8), (17, 6)], fill=hi)
    d.line([(11, 14), (11, 20)], fill=hi)
    d.line([(13, 27), (14, 25)], fill=low)
    d.polygon([(20, 8), (24, 6), (30, 7), (30, 9), (24, 10), (21, 12)], fill=body)           # the snout
    d.line([(24, 7), (29, 8)], fill=hi)
    d.polygon([(15, 3), (16, 0), (18, 2), (20, 0), (21, 3), (22, 1), (22, 4)], fill=dark)    # the crown
    d.point((19, 4), fill=c(244, 220, 90))                                                   # the eye
    d.point((20, 4), fill=K)
    d.line([(23, 9), (28, 9)], fill=low)
    return _finish(im)


def octopus() -> Image.Image:
    body, hi, low, dark = c(150, 72, 54), c(196, 112, 84), c(104, 46, 40), c(60, 24, 28)
    sucker = c(226, 170, 140)
    im = blank()
    d = ImageDraw.Draw(im)
    arms = [  # from the body out along the ground, each curling its tip
        [(12, 21), (8, 24), (4, 25), (2, 23)],
        [(13, 23), (10, 27), (6, 28), (3, 28), (2, 26)],
        [(14, 23), (13, 28), (9, 30)],
        [(18, 23), (19, 28), (23, 30)],
        [(20, 22), (24, 27), (28, 28), (30, 26)],
        [(21, 20), (25, 23), (29, 22), (30, 19)],
    ]
    for pts in arms:
        _chain(d, [(x, y, 1.9 - 0.4 * i) for i, (x, y) in enumerate(pts)], body)
    for pts in arms:
        for x, y in pts[1:-1]:
            d.point((x, y + 1), fill=sucker)
    d.ellipse([8, 7, 24, 24], fill=body)                                                     # the round mantle
    d.polygon([(10, 12), (12, 7), (17, 5), (22, 8), (24, 13), (18, 10)], fill=body)           # the domed top
    d.ellipse([8, 5, 23, 20], fill=body)
    d.arc([10, 6, 21, 17], 200, 290, fill=hi)
    d.line([(12, 9), (15, 7)], fill=hi)
    for p in ((14, 11), (19, 12), (11, 14), (21, 16), (16, 9)):                                # mottling
        d.point(p, fill=low)
    d.ellipse([13, 17, 24, 24], fill=body)                                                   # the head under the mantle
    eyeball = c(232, 206, 110)
    for x0 in (13, 19):                                                                       # eyes, wide awake
        d.rectangle([x0, 15, x0 + 2, 17], fill=eyeball)
        d.rectangle([x0 + 1, 16, x0 + 2, 16], fill=K)                                         # a bar of a pupil
    d.point((18, 21), fill=low)                                                               # the siphon
    return _finish(im)


def sprite() -> Image.Image:
    """A sprite: a foot tall, a slim green-brown archer with a dragonfly's wings."""
    skin, hi, tunic, dark = c(150, 156, 90), c(190, 194, 120), c(62, 100, 56), c(34, 52, 32)
    wing, wing_hi, vein, far = c(206, 232, 244), c(242, 250, 255), c(132, 176, 200), c(170, 202, 222)
    im = blank()
    d = ImageDraw.Draw(im)
    # the far wings, then the near pair: long ovals swept up and back, a smaller pair below
    d.polygon([(15, 22), (11, 16), (9, 11), (10, 8), (12, 8), (15, 13), (16, 20)], fill=far)
    d.polygon([(15, 24), (9, 22), (7, 25), (10, 26), (14, 26)], fill=far)
    d.polygon([(16, 22), (14, 16), (13, 10), (14, 6), (16, 5), (18, 8), (19, 14), (18, 20)], fill=wing)
    d.polygon([(16, 24), (10, 21), (8, 23), (9, 26), (14, 27)], fill=wing)
    d.line([(16, 21), (14, 8)], fill=vein)
    d.line([(16, 21), (16, 11)], fill=vein)
    d.line([(15, 14), (17, 14)], fill=vein)
    d.line([(16, 24), (9, 24)], fill=vein)
    d.line([(14, 7), (16, 6)], fill=wing_hi)
    d.line([(18, 10), (18, 15)], fill=wing_hi)
    d.line([(10, 22), (13, 23)], fill=wing_hi)
    # legs, tunic, arms, head
    d.line([(17, 27), (16, 30)], fill=dark)
    d.line([(19, 27), (20, 30)], fill=dark)
    d.rectangle([15, 30, 16, 30], fill=dark)
    d.rectangle([20, 30, 21, 30], fill=dark)
    d.polygon([(16, 21), (20, 21), (21, 27), (16, 27)], fill=tunic)                         # the tunic
    d.line([(17, 22), (19, 22)], fill=c(96, 140, 76))
    d.line([(16, 25), (20, 25)], fill=dark)                                                 # a belt
    d.rectangle([16, 16, 20, 20], fill=skin)                                                # the head
    d.line([(16, 15), (20, 15)], fill=c(70, 52, 34))                                         # brown hair
    d.rectangle([16, 16, 16, 18], fill=c(70, 52, 34))
    d.polygon([(16, 15), (18, 13), (21, 15)], fill=tunic)                                   # a leaf cap
    d.point((19, 17), fill=K)
    d.point((20, 19), fill=hi)
    d.line([(19, 22), (23, 21)], fill=skin)                                                 # the bow arm, out front
    d.line([(17, 23), (19, 23)], fill=skin)
    # the tiny bow, held upright, with its string and an arrow
    d.arc([21, 17, 27, 29], 270, 90, fill=c(134, 92, 52))
    d.line([(24, 17), (24, 29)], fill=c(216, 210, 190))
    d.line([(20, 23), (24, 23)], fill=c(196, 176, 130))
    d.point((23, 21), fill=skin)
    return _finish(im)
# END F7


def hard_edges(im: Image.Image) -> Image.Image:
    """A creature on the field has no soft pixels (tests/test_adapted_art.py): the drop shadow goes, the rest is
    solid."""
    r, g, b, a = im.split()
    im = Image.merge("RGBA", (r, g, b, a.point(lambda v: 255 if v >= 200 else 0)))
    box = im.getbbox()
    if box is not None and box[3] < 32:  # stand on the tile's last row, as the dolls do (adapt_art.FOOT)
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.paste(im, (0, 32 - box[3]))
        im = out
    return im


def all_drawn() -> dict[str, Image.Image]:
    horse = riding_horse()
    flip = Image.FLIP_LEFT_RIGHT   # the Crawl animals face left
    return {k: (hard_edges(v.transpose(flip)) if k.startswith("creature/") else v) for k, v in {
        "creature/riding_horse": horse,
        "creature/horse": horse.copy(),
        "creature/otherworldly_steed": horse.copy(),  # (Find Steed: drawn as the look chosen, in its kind's colours)
        "creature/pony": pony(),
        "creature/mule": mule(),
        "creature/draft_horse": draft_horse(),
        "creature/warhorse": warhorse(),
        "creature/camel": camel(),
        "creature/cat": cat(),
        "creature/owl": owl(),
        "creature/weasel": weasel(),
        "creature/lion": lion(),
        "creature/tiger": tiger(),
        "creature/panther": panther(),
        "creature/elk": elk(),
        "creature/goat": goat(),
        "creature/giant_goat": giant_goat(),
        "creature/badger": badger(),
        "creature/giant_badger": giant_badger(),
        "creature/ape": ape(),
        "creature/giant_weasel": giant_weasel(),
        "creature/giant_seahorse": giant_seahorse(),
        "creature/octopus": octopus(),
        "creature/sprite": sprite(),
        "creature/animated_object": animated_chest(),  # (Animate Objects: the card's picture)
        "creature/animated_chest": animated_chest(),
        "creature/animated_table": animated_table(),
        "creature/animated_statue": animated_statue(),
        "creature/animated_stone": animated_stone(),
        "creature/animated_log": animated_log(),
        "creature/animated_boulder": animated_boulder(),
        "item/riding_saddle": riding_saddle(),
        "item/military_saddle": military_saddle(),
        "item/exotic_saddle": exotic_saddle(),
        "item/cart": cart(),
        "item/wagon": wagon(),
        "item/carriage": carriage(),
        "item/chariot": chariot(),
        "item/sled": sled(),
    }.items()}
