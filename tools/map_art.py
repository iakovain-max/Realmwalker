"""Settlements on the world map drawn in the manner of their people: Norse longhouses, Qasari domes and minarets,
Khurgan felt tents, Volsk onion domes behind log walls, white Thalassian towns, Itzan step-pyramids, Highland tower
houses, Southron towers and red roofs, halfling burrows, orc stockades. Same hand as tools/tile_art.py town_mark:
drawn large on a 32 grid and shrunk, with an ink outline. Used only by tools/build_tiles.py.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

INK = (40, 30, 22, 255)
STYLES = ("northmarch", "southron", "highland", "qasari", "khurgan", "volsk", "thalassian", "itzan", "halfling",
          "orcish")


def _c(c) -> tuple:
    return tuple(c) + (255,) if len(c) == 3 else tuple(c)


def town_mark(style: str, big: bool, size: int = 64) -> Image.Image:
    """A small place (hamlet, village) or a big one (town, city) of this people, as a drawing on the map."""
    sc = 4
    im = Image.new("RGBA", (size * sc, size * sc), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = size / 32 * sc

    def P(*pts, fill, width=1):
        d.polygon([(x * k, y * k) for x, y in pts], fill=_c(fill), outline=INK, width=max(1, int(width * sc / 2)))

    def R(x0, y0, x1, y1, fill):
        d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=_c(fill), outline=INK, width=max(1, sc // 2))

    def E(x0, y0, x1, y1, fill):
        d.ellipse([x0 * k, y0 * k, x1 * k, y1 * k], fill=_c(fill), outline=INK, width=max(1, sc // 2))

    def PIE(x0, y0, x1, y1, fill, start=180, end=360):
        d.pieslice([x0 * k, y0 * k, x1 * k, y1 * k], start, end, fill=_c(fill), outline=INK, width=max(1, sc // 2))

    def door(x, y):
        d.rectangle([x * k, y * k, (x + 2) * k, (y + 3) * k], fill=(40, 28, 20, 255))

    if style == "northmarch":  # long halls with turf roofs, a stave church, a palisade
        halls = [(3, 18, 17), (14, 13, 15)] + ([(6, 8, 13), (17, 22, 13)] if big else [])
        for x, y, w in halls:
            R(x, y + 4, x + w, y + 9, (120, 86, 56))
            P((x - 1, y + 4), (x + 2, y), (x + w - 2, y), (x + w + 1, y + 4), fill=(96, 120, 70))  # turf
            door(x + w // 2, y + 6)
        if big:
            R(24, 6, 29, 16, (110, 80, 52))
            P((23, 6), (26.5, -1), (30, 6), fill=(80, 60, 44))
            for x in range(1, 32, 3):
                R(x, 27, x + 2, 31, (130, 96, 60))
    elif style == "southron":  # red tile roofs, ochre walls, a tall bell tower
        houses = [(4, 16, 9), (13, 19, 10)] + ([(20, 12, 9), (6, 8, 8)] if big else [])
        for x, y, w in houses:
            R(x, y + 3, x + w, y + 10, (214, 184, 132))
            P((x - 1, y + 3), (x + w / 2, y - 1), (x + w + 1, y + 3), fill=(176, 80, 52))
        R(24 if big else 22, 3, 28 if big else 26, 26, (206, 176, 128))
        P((23 if big else 21, 3), (26 if big else 24, -1), (29 if big else 27, 3), fill=(166, 74, 48))
        if big:
            for x in range(2, 31, 4):
                R(x, 27, x + 3, 31, (196, 168, 120))
    elif style == "highland":  # a stone tower house over thatched cottages
        for x, y in ((3, 19), (18, 21)) + (((10, 23),) if big else ()):
            R(x, y + 3, x + 10, y + 8, (160, 150, 130))
            P((x - 1, y + 3), (x + 5, y - 1), (x + 11, y + 3), fill=(176, 150, 92))
        R(12, 4, 20, 22, (150, 144, 132))
        for x in (12, 15, 18):
            R(x, 2, x + 2, 4, (150, 144, 132))
        d.rectangle([15.5 * k, 9 * k, 16.5 * k, 12 * k], fill=(30, 24, 20, 255))
        if big:
            R(1, 13, 7, 30, (150, 144, 132))
            R(25, 13, 31, 30, (150, 144, 132))
    elif style == "qasari":  # flat roofs, white and sand cubes, a great dome, a minaret
        cubes = [(3, 18, 8, 9), (11, 21, 9, 7), (21, 19, 8, 9)] + ([(5, 11, 7, 7), (19, 10, 7, 9)] if big else [])
        for x, y, w, h in cubes:
            R(x, y, x + w, y + h, (226, 210, 170) if (x + y) % 2 else (236, 228, 210))
            d.rectangle([(x + 2) * k, (y + 2) * k, (x + 3) * k, (y + 4) * k], fill=(60, 44, 30, 255))
        PIE(9, 8, 21, 22, (90, 150, 170), 180, 360)
        R(10, 15, 20, 21, (230, 222, 200))
        R(25 if big else 26, 2, 28 if big else 29, 24, (232, 222, 196))
        P((24.5 if big else 25.5, 2), (26.5 if big else 27.5, -2), (28.5 if big else 29.5, 2), fill=(90, 150, 170))
        if big:
            for x in (2, 30):
                R(x - 1, 10, x + 1, 30, (210, 190, 150))
    elif style == "khurgan":  # round felt tents round the khan's great tent, a horse-tail standard
        tents = [(3, 20, 8), (21, 21, 8), (12, 24, 7)] + ([(1, 12, 7), (24, 12, 7)] if big else [])
        for x, y, w in tents:
            R(x, y + 3, x + w, y + 7, (226, 216, 190))
            PIE(x, y, x + w, y + 7, (210, 200, 176), 180, 360)
            d.rectangle([(x + w / 2 - 0.7) * k, (y + 4) * k, (x + w / 2 + 0.7) * k, (y + 7) * k], fill=(170, 60, 40, 255))
        if big:
            R(9, 12, 23, 20, (232, 222, 200))
            PIE(9, 5, 23, 19, (206, 190, 150), 180, 360)
            d.rectangle([15 * k, 14 * k, 17 * k, 20 * k], fill=(170, 60, 40, 255))
        d.line([(16 * k, 1 * k), (16 * k, (6 if big else 18) * k)], fill=INK, width=sc)
        for i in range(3):
            d.line([((16 - 1 + i) * k, (2 + i) * k), ((15 + i) * k, (8 + i) * k)], fill=(60, 50, 44, 255), width=sc)
    elif style == "volsk":  # log walls with towers, a church of onion domes inside
        if big:
            R(2, 16, 30, 30, (120, 84, 54))
            for x in (1, 25):
                R(x, 11, x + 6, 30, (110, 78, 50))
                P((x - 0.5, 11), (x + 3, 6), (x + 6.5, 11), fill=(90, 110, 70))
        else:
            R(4, 21, 15, 28, (140, 100, 64))
            P((3, 21), (9.5, 16), (16, 21), fill=(110, 80, 52))
        R(13, 12, 21, 26, (226, 222, 210))
        for x, y, r, col in ((17, 9, 3.5, (210, 170, 60)), (13.5, 13, 2.2, (70, 110, 170)), (20.5, 13, 2.2, (70, 110, 170))):
            E(x - r, y - r, x + r, y + r * 1.1, col)
            P((x - r * 0.5, y - r * 0.7), (x, y - r * 2), (x + r * 0.5, y - r * 0.7), fill=col)
    elif style == "thalassian":  # white cubes stepping down a slope, blue domes, a temple of columns above
        steps = [(2, 22, 8), (9, 19, 8), (16, 16, 8), (23, 13, 7)] if big else [(4, 20, 8), (12, 18, 8), (20, 16, 7)]
        for x, y, w in steps:
            R(x, y, x + w, y + 7, (240, 238, 232))
            d.rectangle([(x + 2) * k, (y + 2) * k, (x + 3) * k, (y + 4) * k], fill=(60, 90, 150, 255))
        PIE(10, 13, 16, 21, (60, 100, 180), 180, 360)
        if big:
            R(3, 8, 15, 10, (232, 226, 210))
            P((2, 8), (9, 3), (16, 8), fill=(232, 226, 210))
            for x in (4, 7, 10, 13):
                R(x, 10, x + 1, 16, (236, 232, 222))
    elif style == "itzan":  # a stepped pyramid with its temple, thatched huts round it
        if big:
            for i, (x0, x1) in enumerate(((3, 29), (6, 26), (9, 23), (12, 20))):
                R(x0, 26 - i * 5, x1, 30 - i * 5, (196, 180, 150))
            R(13, 4, 19, 10, (180, 70, 50))
            P((12, 4), (16, 0), (20, 4), fill=(110, 140, 80))
            d.rectangle([15.3 * k, 10 * k, 16.7 * k, 30 * k], fill=(160, 140, 112, 255))
        else:
            for i, (x0, x1) in enumerate(((8, 24), (11, 21), (14, 18))):
                R(x0, 25 - i * 4, x1, 29 - i * 4, (196, 180, 150))
            for x in (1, 25):
                R(x, 23, x + 6, 29, (190, 168, 120))
                P((x - 1, 23), (x + 3, 18), (x + 7, 23), fill=(176, 150, 80))
    elif style == "halfling":  # round green doors in grassy mounds, a garden fence
        mounds = [(2, 16, 15), (15, 19, 14)] + ([(8, 9, 14)] if big else [])
        for x, y, w in mounds:
            PIE(x, y, x + w, y + 14, (110, 150, 76), 180, 360)
            E(x + w / 2 - 2, y + 3, x + w / 2 + 2, y + 7, (60, 110, 60) if (x % 2) else (170, 60, 50))
            d.ellipse([(x + w / 2 - 0.3) * k, (y + 5) * k, (x + w / 2 + 0.3) * k, (y + 5.6) * k], fill=(230, 200, 80, 255))
        for x in range(1, 31, 3):
            d.line([(x * k, 27 * k), (x * k, 30 * k)], fill=(120, 90, 60, 255), width=sc)
        d.line([(1 * k, 28 * k), (30 * k, 28 * k)], fill=(120, 90, 60, 255), width=sc)
    elif style == "orcish":  # a stockade of sharpened stakes, crude huts, a skull on a pole
        for x in range(2, 31, 3):
            P((x, 30), (x, 17), (x + 1, 14), (x + 2, 17), (x + 2, 30), fill=(110, 80, 52))
        for x, y in ((5, 5), (17, 7)) + (((10, 1),) if big else ()):
            R(x, y + 5, x + 10, y + 10, (100, 84, 64))
            P((x - 1, y + 5), (x + 5, y), (x + 11, y + 5), fill=(90, 70, 50))
        d.line([(28 * k, 2 * k), (28 * k, 14 * k)], fill=INK, width=sc)
        E(26.5, 0, 29.5, 3, (226, 220, 200))
    return im.resize((size, size), Image.LANCZOS)


def all_drawn() -> dict[str, Image.Image]:
    out: dict[str, Image.Image] = {}
    for style in STYLES:
        out[f"map/town_{style}_small"] = town_mark(style, False)
        out[f"map/town_{style}_big"] = town_mark(style, True)
    return out
