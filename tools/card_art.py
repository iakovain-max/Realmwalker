"""The Wayfarer's Deck (Expansion 6 F.4): the faces of the twenty great cards, the four suits and the back, drawn as
small pixel patterns ('.' is transparent) on a 24x36 card. The reading's screen draws them at whole multiples.

Run this file to write a contact sheet to build/cards.png so the cards can be looked at.
"""
from __future__ import annotations

from PIL import Image

W, H = 24, 36
EMBLEM = 16

PALETTE: dict[str, tuple[int, int, int, int]] = {
    "k": (22, 16, 14, 255),      # outline
    "x": (52, 46, 52, 255),      # black cloth
    "m": (112, 106, 112, 255),   # grey
    "M": (164, 160, 160, 255),   # light grey
    "r": (128, 30, 30, 255),     # dark red
    "R": (184, 54, 44, 255),     # red
    "o": (214, 118, 40, 255),    # ember
    "l": (250, 222, 120, 255),   # flame light
    "y": (220, 178, 64, 255),    # gold
    "Y": (148, 110, 38, 255),    # dark gold
    "b": (226, 210, 172, 255),   # parchment
    "B": (176, 156, 118, 255),   # shadowed parchment
    "s": (150, 156, 164, 255),   # steel
    "S": (86, 90, 100, 255),     # dark steel
    "c": (120, 170, 206, 255),   # water
    "C": (54, 94, 150, 255),     # deep water
    "g": (104, 146, 60, 255),    # leaf
    "G": (52, 84, 40, 255),      # dark leaf
    "n": (128, 86, 52, 255),     # brown
    "d": (76, 50, 32, 255),      # dark brown
    "f": (210, 156, 124, 255),   # skin
    "w": (244, 240, 230, 255),   # white
    "v": (120, 80, 150, 255),    # violet
}

# Each card's band colour at the foot of its face.
BAND = {"lantern": "y", "hound": "n", "widow": "x", "ford": "C", "crown": "y", "bell": "Y", "mask": "v",
        "key": "S", "ash_tree": "G", "bride": "w", "smith": "R", "pilgrim": "n", "sleeper": "m",
        "broken_shield": "S", "crow": "x", "mother": "R", "grave": "m", "wheel": "d", "candle": "o", "wolf": "m"}

GREAT: dict[str, list[str]] = {
    "lantern": [
        "................",
        ".......kk.......",
        "......k..k......",
        ".....kkkkkk.....",
        "....kYYYYYYk....",
        "....kYkkkkYk....",
        "....kYkllkYk....",
        "....kYlyylYk....",
        "....kYlyolYk....",
        "....kYlooyYk....",
        "....kYkllkYk....",
        "....kYkkkkYk....",
        "....kYYYYYYk....",
        ".....kkkkkk.....",
        "................",
        "................",
    ],
    "hound": [
        "................",
        "..kk............",
        ".knnk...........",
        "knnwnk..........",
        "kknnnnk.........",
        "..knnnk.........",
        "..knnnnkkkkk....",
        "...knnnnnnnnk...",
        "...knnnnnnnnnk..",
        "...knnkknnnnnk.k",
        "...knk.knnnnkknk",
        "...knk.knkknk.kk",
        "..knnk.knkknk...",
        "..kkk..kkkkkk...",
        "................",
        "................",
    ],
    "widow": [
        "......kkkk......",
        ".....kxxxxk.....",
        "....kxxxxxxk....",
        "....kxkffkxk....",
        "...kxkfffffkx...",
        "...kxkfkfkfkxk..",
        "...kxkfffffkxk..",
        "...kxxkfffkxxk..",
        "..kxxxxkkkxxxxk.",
        "..kxxxxxxxxxxxk.",
        ".kxxxwxxxxxxxxxk",
        ".kxxxxwxxxxxxxxk",
        ".kxxxxxxxxxxxxxk",
        ".kkkkkkkkkkkkkkk",
        "................",
        "................",
    ],
    "ford": [
        "................",
        "................",
        "cccccccccccccccc",
        "cCccccCcccccCccc",
        "ccccccccccccccc.",
        "..kkk....kkk....",
        ".kMMMk..kMMMk...",
        ".kMmmk..kMmmk...",
        "cckkkccccckkkccc",
        "CcccCcccCcccCccc",
        "cccccc.kkk.ccccc",
        "......kMMMk.....",
        "ccccc.kmmmk.cccc",
        "cCcccCckkkcccCcc",
        "cccccccccccccccc",
        "................",
    ],
    "crown": [
        "................",
        "................",
        "................",
        "..k....k....k...",
        ".kyk..kyk..kyk..",
        ".kyk.kyRyk.kyk..",
        ".kyykyyyyykyyk..",
        ".kyyyyyyyyyyyk..",
        ".kyRyyyCyyyRyk..",
        ".kyyyyyyyyyyyk..",
        ".kYYYYYYYYYYYk..",
        ".kkkkkkkkkkkkk..",
        "................",
        "................",
        "................",
        "................",
    ],
    "bell": [
        ".......kk.......",
        "......kYYk......",
        ".......kk.......",
        "......kyyk......",
        ".....kyyyyk.....",
        ".....kyyyYk.....",
        "....kyyyyyYk....",
        "....kyyyyyYk....",
        "....kyyyyyYk....",
        "...kyyyyyyyYk...",
        "...kyyyyyyyYk...",
        "..kyyyyyyyyyYk..",
        "..kYYYYYYYYYYk..",
        "..kkkkkkkkkkkk..",
        ".......kk.......",
        ".......kk.......",
    ],
    "mask": [
        "................",
        "................",
        "...kkkkkkkkkk...",
        "..kwwwwwwwwwwk..",
        ".kwwwwwwwwwwwwk.",
        ".kwwkkkwwkkkwwk.",
        ".kwkxxkwwkxxkwk.",
        ".kwwkkkwwkkkwwk.",
        ".kwwwwwwwwwwwwk.",
        "..kwwwwkkwwwwk..",
        "..kwwkwwwwkwwk..",
        "...kwwkkkkwwk...",
        "....kwwwwwwk....",
        ".....kkkkkk.....",
        "...vv......vv...",
        "..v..........v..",
    ],
    "key": [
        "................",
        "....kkkk........",
        "...kyyyyk.......",
        "..kyykkyyk......",
        "..kykbbkyk......",
        "..kykbbkyk......",
        "..kyykkyyk......",
        "...kyyyyk.......",
        "....kyyk........",
        "....kyyk........",
        "....kyykk.......",
        "....kyyyyk......",
        "....kyykk.......",
        "....kyyyyk......",
        "....kyykk.......",
        ".....kk.........",
    ],
    "ash_tree": [
        "....kkkkkkk.....",
        "..kkgggGgggkk...",
        ".kggGggggGgggk..",
        "kgggggGgggggGgk.",
        "kgGgggggggGgggk.",
        "kggggGggGggggGk.",
        ".kggggggggggggk.",
        "..kkGkkdkkGkkk..",
        "....kkkdkkk.....",
        "......kdk.......",
        "......kdk.......",
        "......kdk.......",
        ".....kdddk......",
        "...kkdkkkdkk....",
        "..kd.k...k.dk...",
        "GGGGGGGGGGGGGGGG",
    ],
    "bride": [
        "................",
        "......kkk.......",
        ".....kwwwk......",
        "....kwfffwk.....",
        "....kwfkfwk.....",
        "....kwfffwk.....",
        "...kwwkfkwwk....",
        "...kwwwkwwwk....",
        "..kwwwRgRwwwk...",
        "..kwwwgRgwwwk...",
        "..kwwwwwwwwwk...",
        ".kwwwwwwwwwwwk..",
        ".kwwwwwwwwwwwk..",
        ".kwwwwwwwwwwwk..",
        ".kkkkkkkkkkkkk..",
        "................",
    ],
    "smith": [
        "................",
        ".........kkkk...",
        "........ksssSk..",
        "........ksssSk..",
        "........kkdkkk..",
        "..........kdk...",
        ".........kdk....",
        "........kdk.....",
        ".......kdk..o...",
        "......kk...olo..",
        "..kkkkkkkkkkkk..",
        ".kssssssssssSSk.",
        "..kkkksssSkkkk..",
        ".....ksssSk.....",
        "....kSSSSSSk....",
        "....kkkkkkkk....",
    ],
    "pilgrim": [
        "..kk............",
        ".kddk...........",
        ".kddk....kkkk...",
        "..kdk...kbbbbk..",
        "..kdk..kbkbkbbk.",
        "..kdk..kbbkbkbk.",
        "..kdk..kbkbkbbk.",
        "..kdk..kbbkbkbk.",
        "..kdk...kbbbbk..",
        "..kdk....kbbk...",
        "..kdk.....kk....",
        "..kdk...........",
        "..kdk...........",
        "..kdk...........",
        "..kdk...........",
        "..kkk...........",
    ],
    "sleeper": [
        "................",
        "................",
        "................",
        "................",
        "....kkk.........",
        "...kfffkkkkkkk..",
        "..kfkfkkmmmmmmk.",
        "..kfffkmmffmmmmk",
        "...kkkkmmffmmmmk",
        "..kMMMMkkmmmmmmk",
        ".kMMMMMMMkkkkkk.",
        ".kmmmmmmmmmmmmk.",
        ".kkkkkkkkkkkkkk.",
        "................",
        "................",
        "................",
    ],
    "broken_shield": [
        "................",
        ".kkkkkkk.kkkkkk.",
        ".ksssssk.ksssssk",
        ".ksRRRRk.kRRRRsk",
        ".ksRyRRRk.kRRRsk",
        ".ksRyyRRk.kRRRsk",
        ".ksRRRRk.kRRRRsk",
        "..ksRRRk.kRRRsk.",
        "..ksRRRRk.kRRsk.",
        "...ksRRRk.kRsk..",
        "....ksRRk.ksk...",
        ".....ksRk..k....",
        "......ksk.......",
        ".......k...kSk..",
        "..........kSsSk.",
        "...........kkk..",
    ],
    "crow": [
        "................",
        "................",
        "..........kkk...",
        ".........kxxxk..",
        "........kxwxxyy.",
        "........kxxxxk..",
        "......kkxxxxk...",
        "....kkxxxxxxk...",
        "..kkxxxxxxxxk...",
        ".kxxxxmxxxxk....",
        "kxxxmxxxxxk.....",
        "...kkkxxxk......",
        ".....k.k.k......",
        ".....k.k........",
        "....dddddddddd..",
        "................",
    ],
    "mother": [
        ".....kkkk.......",
        "....kffffk......",
        "....kfkfkk......",
        "....kffffk......",
        "...kkRffRkk.....",
        "..kRRRkkRRRk....",
        "..kRRkffkRRk....",
        "..kRkfkkfkRk....",
        "..kRkfffkkRk....",
        "..kRRkbbbkRk....",
        "..kRRkbbbkRRk...",
        "..kRRRkkkRRRk...",
        ".kRRRRRRRRRRRk..",
        ".kRRRRRRRRRRRk..",
        ".kkkkkkkkkkkkk..",
        "................",
    ],
    "grave": [
        "................",
        "......kkkk......",
        ".....kMMMMk.....",
        "....kMMkkMMk....",
        "....kMkMMkMk....",
        "....kMMkkMMk....",
        "....kMMkkMMk....",
        "....kMMMMMMk....",
        "....kMMMMMmk....",
        "....kMmMMMmk....",
        "....kMMMMMMk....",
        "..kkkkkkkkkkkk..",
        ".kdndddnddddndk.",
        "kdddndddddnddddk",
        "kkkkkkkkkkkkkkkk",
        "................",
    ],
    "wheel": [
        "................",
        ".....kkkkkk.....",
        "...kkdddddkk....",
        "..kddkkdkkddk...",
        ".kddk.kdk.kddk..",
        ".kdkk.kdk.kkdk..",
        "kddkdkkdkkdkddk.",
        "kdk..kkYkk..kdk.",
        "kdddddkYkdddddk.",
        "kdk..kkYkk..kdk.",
        "kddkdkkdkkdkddk.",
        ".kdkk.kdk.kkdk..",
        ".kddk.kdk.kddk..",
        "..kddkkdkkddk...",
        "...kkdddddkk....",
        ".....kkkkkk.....",
    ],
    "candle": [
        ".......k........",
        "......kok.......",
        ".....kolok......",
        ".....kollk......",
        "......kok.......",
        ".......k........",
        "......kkkk......",
        ".....kwwwBk.....",
        ".....kwwwBk.....",
        ".....kwwwBk.....",
        ".....kwwwBk.....",
        ".....kwwwBk.....",
        "...kkkkkkkkkk...",
        "..kYyyyyyyyyYk..",
        "...kkkkkkkkkk...",
        "................",
    ],
    "wolf": [
        "................",
        "..kk......kk....",
        "..kmk....kmk....",
        "..kmmkkkkmmk....",
        "..kmmmmmmmmk....",
        ".kmmmmmmmmmmk...",
        ".kmmykmmmykmk...",
        ".kmmmmmmmmmmk...",
        "..kmmmmmmmmk....",
        "...kmmMMmmk.....",
        "...kmMkkMmk.....",
        "....kMwwMk......",
        "....kMMMMk......",
        ".....kkkk.......",
        "................",
        "................",
    ],
}

SUITS: dict[str, list[str]] = {
    "blades": [
        ".......kk.......",
        "......kssk......",
        "......kssk......",
        "......kssk......",
        "......kssk......",
        "......kssk......",
        "......kssk......",
        "......kssk......",
        "....kkkkkkkk....",
        "....kYyyyyYk....",
        "....kkkddkkk....",
        "......kddk......",
        "......kddk......",
        "......kyyk......",
        ".......kk.......",
        "................",
    ],
    "coins": [
        "................",
        "................",
        ".....kkkkkk.....",
        "....kyyyyyyk....",
        "...kyyYYYYyyk...",
        "..kyyYyyyyYyyk..",
        "..kyYyykkyyYyk..",
        "..kyYykyykyYyk..",
        "..kyYykyykyYyk..",
        "..kyYyykkyyYyk..",
        "..kyyYyyyyYyyk..",
        "...kyyYYYYyyk...",
        "....kyyyyyyk....",
        ".....kkkkkk.....",
        "................",
        "................",
    ],
    "cups": [
        "................",
        "...kkkkkkkkkk...",
        "...kyyyyyyyyk...",
        "...kRRRRRRRRk...",
        "...kyyyyyyyYk...",
        "....kyyyyyYk....",
        "....kyyyyyYk....",
        ".....kyyyYk.....",
        "......kyyk......",
        "......kyYk......",
        "......kyYk......",
        ".....kyyyYk.....",
        "....kyyyyyYk....",
        "....kkkkkkkk....",
        "................",
        "................",
    ],
    "stones": [
        "................",
        "................",
        "......kkkk......",
        ".....kMMMmk.....",
        ".....kMmmmk.....",
        "......kkkk......",
        "....kkkkkkk.....",
        "...kMMMMmmmk....",
        "...kMmmmmmmk....",
        "....kkkkkkk.....",
        "..kkkkkkkkkkk...",
        ".kMMMMMmmmmmmk..",
        ".kMmmmmmmmmmmk..",
        ".kmmmmmmmmmmmk..",
        "..kkkkkkkkkkk...",
        "................",
    ],
}

BACK_STAR = [
    "................",
    ".......kk.......",
    ".......yy.......",
    "......kyyk......",
    "......kyyk......",
    "..k...kyyk...k..",
    "...yykyyyykyy...",
    ".kyyyyyRRyyyyyk.",
    ".kyyyyyRRyyyyyk.",
    "...yykyyyykyy...",
    "..k...kyyk...k..",
    "......kyyk......",
    "......kyyk......",
    ".......yy.......",
    ".......kk.......",
    "................",
]


def _pattern(rows: list[str]) -> list[str]:
    return [(r + "." * EMBLEM)[:EMBLEM] for r in (rows + ["." * EMBLEM] * EMBLEM)[:EMBLEM]]


def _frame(face: str, band: str | None) -> Image.Image:
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = im.load()
    for y in range(H):
        for x in range(W):
            corner = (x in (0, W - 1)) and (y in (0, H - 1))
            if corner:
                continue
            edge = x in (0, W - 1) or y in (0, H - 1)
            rim = x in (1, W - 2) or y in (1, H - 2)
            inner = x in (3, W - 4) and 3 <= y <= H - 4 or y in (3, H - 4) and 3 <= x <= W - 4
            if edge:
                px[x, y] = PALETTE["k"]
            elif rim:
                px[x, y] = PALETTE["Y"]
            elif inner:
                px[x, y] = PALETTE["B"]
            else:
                px[x, y] = PALETTE[face]
                if face == "b" and (x * 7 + y * 13) % 29 == 0:
                    px[x, y] = PALETTE["B"]  # (a little grain in the parchment)
    if band:
        for y in range(H - 10, H - 4):
            for x in range(4, W - 4):
                px[x, y] = PALETTE[band]
        for x in range(5, W - 5, 3):  # (a row of pips along the band)
            px[x, H - 7] = PALETTE["y"] if band not in ("y", "w") else PALETTE["k"]
        for x in range(4, W - 4):
            px[x, H - 11] = PALETTE["B"]
    return im


def _stamp(im: Image.Image, rows: list[str], ox: int, oy: int) -> None:
    px = im.load()
    for y, row in enumerate(_pattern(rows)):
        for x, ch in enumerate(row):
            if ch != ".":
                px[ox + x, oy + y] = PALETTE[ch]


def great(cid: str) -> Image.Image:
    im = _frame("b", BAND[cid])
    _stamp(im, GREAT[cid], (W - EMBLEM) // 2, 5)
    return im


def suit(name: str) -> Image.Image:
    im = _frame("b", None)
    _stamp(im, SUITS[name], (W - EMBLEM) // 2, (H - EMBLEM) // 2)
    return im


def back() -> Image.Image:
    im = _frame("r", None)
    px = im.load()
    for y in range(4, H - 4):
        for x in range(4, W - 4):
            if (x + y) % 4 == 0 or (x - y) % 4 == 0:
                px[x, y] = PALETTE["R"]
    _stamp(im, BACK_STAR, (W - EMBLEM) // 2, (H - EMBLEM) // 2)
    return im


def all_drawn() -> dict[str, Image.Image]:
    out = {f"card/{cid}": great(cid) for cid in GREAT}
    out.update({f"card/suit_{s}": suit(s) for s in SUITS})
    out["card/back"] = back()
    return out


if __name__ == "__main__":
    from pathlib import Path

    tiles = all_drawn()
    scale = 4
    cols = 8
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * (W * scale + 8), rows * (H * scale + 8)), (40, 34, 30, 255))
    for i, (name, im) in enumerate(sorted(tiles.items())):
        big = im.resize((W * scale, H * scale), Image.NEAREST)
        sheet.paste(big, ((i % cols) * (W * scale + 8) + 4, (i // cols) * (H * scale + 8) + 4), big)
    out = Path(__file__).resolve().parent.parent / "build" / "cards.png"
    sheet.save(out)
    print(out)
