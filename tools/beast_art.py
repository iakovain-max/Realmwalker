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
        "creature/pony": pony(),
        "creature/mule": mule(),
        "creature/draft_horse": draft_horse(),
        "creature/warhorse": warhorse(),
        "creature/camel": camel(),
        "item/riding_saddle": riding_saddle(),
        "item/military_saddle": military_saddle(),
        "item/exotic_saddle": exotic_saddle(),
        "item/cart": cart(),
        "item/wagon": wagon(),
        "item/carriage": carriage(),
        "item/chariot": chariot(),
        "item/sled": sled(),
    }.items()}
