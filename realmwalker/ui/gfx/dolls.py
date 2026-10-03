"""People as pixel-art figures: a body for their race and sex, coloured skin, hair and beard, then what they wear and
hold, each a layer in the tile sheets (tools/figure_art.py, tools/figure_gear.py) coloured when drawn.

The player and companions wear what they really wear, in the colours of those very things (a dyed cloak, a blackened
blade, a rare item's own look); townsfolk dress for their trade and bandits, guards and cultists for theirs
(data/sprites.json "figures"). Whatever the game does not say is picked by a stable hash of who it is, so a person
looks the same every time. A figure is stacked once into a single picture and kept (compose()).
"""

from __future__ import annotations

import re
import zlib
from collections import OrderedDict

import numpy as np

Part = tuple[str, tuple[int, int, int, int], int, int]  # tile, colour multiplied in (r, g, b, alpha), offset x, y
WHITE = (255, 255, 255, 255)
LAYERS = ("body", "legs", "feet", "over", "tabard", "belt", "hands")
HIDES_HAIR = ("hood", "greathelm", "kettle", "nasal", "horned", "furhat", "wizard")


def stable(key: str, n: int) -> int:
    return zlib.crc32(key.encode("utf-8")) % max(1, n) if n > 0 else 0


def choose(options, key: str):
    if not options:
        return ""
    if isinstance(options, str):
        return options
    return options[stable(key, len(options))]


def body_key(race: str, sex: str) -> str:
    race = race if race in ("human", "elf", "dwarf", "halfling", "half_orc") else "human"
    return f"{race}_{'female' if sex == 'female' else 'male'}"


def _fig(tables) -> dict:
    return tables.sprites["figures"]


def colour(tables, name: str | None, default=(200, 200, 200)) -> tuple[int, int, int]:
    """A named dye, leather, metal or glow."""
    if not name:
        return default
    f = _fig(tables)
    for table in ("colours", "metals", "glows"):
        if name in f[table]:
            return tuple(f[table][name])
    return default


class Figure:
    """Builds the list of layers for one person."""

    def __init__(self, tables, race: str, sex: str, key: str) -> None:
        self.t = tables
        self.f = _fig(tables)
        self.race = race if race in self.f["skins"] else "human"
        self.sex = sex
        self.body = body_key(self.race, sex)
        self.key = key
        self.slots: dict[str, tuple[str, tuple]] = {}  # slot -> (thing, colour)
        self.cloak: tuple | None = None
        self.head: tuple[str, tuple] | None = None
        self.held: tuple[str, tuple, tuple | None] | None = None  # weapon, metal colour, glow
        self.left: tuple[str, tuple] | None = None  # something small in the other hand (a torch)
        self.shield: tuple | None = None  # shape, field colour, emblem, emblem colour
        skins = self.f["skins"][self.race]
        self.skin = tuple(skins[choose(sorted(skins), key + "skin")])
        self.hair_style = ""
        self.hair = (0, 0, 0)
        self.beard = ""

    # ---- the person
    def looks(self, text: str, age: int = 30) -> None:
        """Skin, hair colour and style (and a beard) from the words used to describe them."""
        f = self.f
        # Only the words about their hair count ("straw-coloured hair", not "a red coat" or "colouRED").
        parts = re.split(r"[,;.:!?]| and | with ", (text or "").lower())
        skin_text = " ".join(c for c in parts if any(w in c for w in ("skin", "complexion", "face", "tanned", "weather")))
        text = " ".join(c for c in parts if any(w in c for w in ("hair", "bald", "shaven", "braid", "locks", "head")))

        def said(word: str, within: str | None = None) -> bool:
            return re.search(r"\b" + re.escape(word), text if within is None else within) is not None

        skins = f["skins"][self.race]
        skin = next((k for word, k in f.get("skin_words", []) if k in skins and said(word, skin_text)), None)
        if skin is not None:
            self.skin = tuple(skins[skin])

        colour_name = next((c for word, c in f["hair_words"] if said(word)), None)
        if colour_name is None:
            colour_name = "grey" if age >= 55 else choose(["black", "dark_brown", "brown", "auburn", "blond"], self.key + "hc")
        self.hair = tuple(f["hair_colours"].get(colour_name, f["hair_colours"]["brown"]))
        style = next((s for word, s in f["hair_style_words"] if said(word)), None)
        if style is None:
            pool = f["hair_styles"].get(self.body) or f["hair_styles"][self.sex if self.sex in ("male", "female") else "male"]
            style = choose(pool, self.key + "hs")
        self.hair_style = style
        chance = f["beards"].get(self.race, 0.3)
        if self.sex != "female" and stable(self.key + "beard", 100) < chance * 100:
            self.beard = choose(f["beard_styles"].get(self.race, ["short"]), self.key + "bs")

    # ---- what they wear
    def wear(self, slot: str, spec: str, dye: str | None = None, look: dict | None = None, hand: str = "right") -> None:
        """slot: body/legs/feet/over/tabard/belt/hands/head/cloak/held/shield; spec 'thing@colour' (see sprites.json)."""
        if spec is None:
            return
        thing, _, rest = spec.partition("@")
        look = look or {}
        if slot == "cloak":
            name = look.get("cloth") or thing or rest or dye or "brown"
            self.cloak = colour(self.t, name)
            return
        if slot == "tabard":
            if thing:
                self.slots["tabard"] = ("tabard", colour(self.t, look.get("cloth") or thing))
            return
        if not thing:
            return
        if slot == "held":
            metal = colour(self.t, look.get("metal") or rest or "steel")
            glow = colour(self.t, look["glow"]) if look.get("glow") else None
            small = thing in ("torch", "lantern", "book", "holy_symbol")
            if hand == "left" or (small and self.held is not None):
                self.left = (thing, metal)
            else:
                if self.held is not None and self.held[0] in ("torch", "lantern", "book", "holy_symbol"):
                    self.left = (self.held[0], self.held[1])
                self.held = (thing, metal, glow)
            return
        if slot == "shield":
            bits = (spec.split("@") + ["", "", ""])[:4]
            field = colour(self.t, look.get("cloth") or bits[1] or dye or choose(["red", "navy", "forest", "brown"], self.key + "sh"))
            emblem = look.get("emblem") or bits[2] or ""
            ecol = colour(self.t, look.get("trim") or look.get("metal") or bits[3] or "white")
            self.shield = (bits[0] or "heater", field, emblem if emblem != "none" else "", ecol)
            return
        name = look.get("metal") if rest in self.f["metals"] or thing in METAL_THINGS else None
        name = name or look.get("cloth") or rest or dye
        rgb = colour(self.t, name, (180, 170, 150))
        if slot == "head":
            self.head = (thing, rgb)
        else:
            self.slots[slot] = (thing, rgb)

    def outfit(self, spec: dict) -> None:
        """Dress from an outfit: a list of choices per slot."""
        for slot, options in spec.items():
            self.wear(slot, choose(options, self.key + slot))

    # ---- the layers
    def parts(self, atlas) -> list[Part]:
        b = self.body
        out: list[Part] = []

        def add(name: str, rgb=(255, 255, 255), dx: int = 0, dy: int = 0, alpha: int = 255) -> None:
            if atlas.has(name):
                out.append((name, (int(rgb[0]), int(rgb[1]), int(rgb[2]), alpha), dx, dy))

        if self.cloak:
            add(f"fig/cloak/{b}/back", self.cloak)
        add(f"fig/body/{b}", self.skin)
        for slot in LAYERS:
            if slot in self.slots:
                thing, rgb = self.slots[slot]
                add(f"fig/wear/{b}/{thing}", rgb)
        if self.cloak:
            add(f"fig/cloak/{b}/front", self.cloak)
        if self.beard:
            add(f"fig/beard/{b}/{self.beard}", self.hair)
        hidden = self.head is not None and self.head[0] in HIDES_HAIR
        if self.hair_style and not hidden:
            add(f"fig/hair/{b}/{self.hair_style}", self.hair)
        if self.head:
            thing, rgb = self.head
            add(f"fig/head/{b}/{thing}", (255, 255, 255) if thing in ("crown", "circlet") else rgb)
        hands = atlas.figures.get("hands", {})
        ref = hands.get(atlas.figures.get("ref", "human_male"))
        mine = hands.get(b, ref)

        def offset(i: int) -> tuple[int, int]:
            if not ref or not mine:
                return 0, 0
            return int(round(mine[i][0] - ref[i][0])), int(round(mine[i][1] - ref[i][1]))

        if self.shield:
            shape, field, emblem, ecol = self.shield
            dx, dy = offset(1)
            add(f"fig/shield/{shape}/field", field, dx, dy)
            if emblem:
                add(f"fig/shield/{shape}/{emblem}", ecol, dx, dy)
            add(f"fig/shield/{shape}/rim", (255, 255, 255), dx, dy)
        elif self.left:
            thing, metal = self.left
            dx, dy = offset(1)
            add(f"fig/held/{thing}/left_rest", (255, 255, 255), dx, dy)
            add(f"fig/held/{thing}/left_metal", metal, dx, dy)
        if self.held:
            thing, metal, glow = self.held
            dx, dy = offset(0)
            if glow:
                add(f"fig/held/{thing}/glow", glow, dx, dy, 170)
            add(f"fig/held/{thing}/rest", (255, 255, 255), dx, dy)
            add(f"fig/held/{thing}/metal", metal, dx, dy)
        return out


METAL_THINGS = {"chain_shirt", "chain_mail", "ring_mail", "scale_mail", "breastplate", "half_plate", "splint", "plate",
                "gauntlets", "greaves", "kettle", "nasal", "greathelm", "horned", "crown", "circlet"}


# ---------------------------------------------------------------------------- who
def npc(npc, tables, atlas=None) -> list[Part]:
    """A townsperson dressed for their trade."""
    fig = Figure(tables, npc.race, npc.sex, f"npc{npc.id}")
    fig.looks((npc.profile or {}).get("appearance", ""), npc.age)
    outfits = _fig(tables)["outfits"]
    fig.outfit(outfits.get(npc.job) or outfits["_"])
    return fig.parts(atlas or _atlas())


def creature(def_id: str, tables, key: str, atlas=None) -> list[Part]:
    """A creature: its own picture, or a dressed figure for people (bandits, guards...)."""
    spec = _fig(tables)["creatures"].get(def_id)
    if spec is None:
        return [(f"creature/{def_id}", WHITE, 0, 0)]
    sex = "female" if stable(key + "sex", 5) == 0 else "male"
    fig = Figure(tables, spec.get("race", ["human"])[0] if isinstance(spec.get("race"), list) else "human", sex, key)
    fig.looks("")
    fig.outfit({k: v for k, v in spec.items() if k != "race"})
    return fig.parts(atlas or _atlas())


def character(char, tables, *, lit: bool = False, atlas=None) -> list[Part]:
    """The player or a companion, in what they wear and hold, in the colours of those very things."""
    f = _fig(tables)
    worn = f["worn"]
    fig = Figure(tables, char.race, char.sex, f"pc{char.name}")
    fig.looks(getattr(char, "appearance", ""), getattr(char, "age", 30))
    dressed = set()
    for slot in ("under", "main", "armor", "outer", "head", "helmet", "hands", "feet", "main_hand", "off_hand"):
        it = char.equipped_item(slot)
        if it is None:
            continue
        spec = worn.get(it.def_id)
        if not spec:
            continue
        look = item_look(it, tables)
        dyes = spec.get("dyes")
        dye = look.get("cloth") or (dyes[stable(f"item{it.uid}", len(dyes))] if dyes else None)
        for key in ("body", "legs", "over", "feet", "hands", "head", "cloak", "held", "shield", "tabard", "belt"):
            if key in spec:
                fig.wear(key, spec[key], dye, look, hand="left" if slot == "off_hand" else "right")
                dressed.add(key)
    if "body" not in dressed and "over" not in dressed:
        fig.outfit({k: v for k, v in (f["classes"].get(char.cls) or f["classes"]["_"]).items() if k in ("body", "legs")})
    elif "body" not in dressed:
        fig.wear("body", "shirt_long@undyed")
    if "legs" not in dressed and fig.slots.get("body", ("",))[0] not in ("robe", "dress"):
        fig.wear("legs", "pants@brown")
    if "head" not in dressed:
        extra = f["classes"].get(char.cls, {}).get("head")
        if extra:
            fig.wear("head", choose(extra, fig.key + "head"))
    if lit:
        fig.wear("held", "torch")
    return fig.parts(atlas or _atlas())


def problems(tables, atlas) -> list[str]:
    """What in data/sprites.json "figures" names a picture or a colour that does not exist (for the tests)."""
    f = _fig(tables)
    named = set(f["colours"]) | set(f["metals"]) | set(f["glows"])
    out: list[str] = []

    def check(where: str, slot: str, spec: str) -> None:
        if not spec:
            return
        bits = spec.split("@")
        thing = bits[0]
        if slot in ("cloak", "tabard"):
            for c in bits:
                if c and c not in named:
                    out.append(f"{where} {slot}: no colour {c}")
            return
        if slot == "shield":
            shape = thing or "heater"
            if not atlas.has(f"fig/shield/{shape}/field"):
                out.append(f"{where} shield: no shape {shape}")
            if len(bits) > 2 and bits[2] and bits[2] != "none" and not atlas.has(f"fig/shield/{shape}/{bits[2]}"):
                out.append(f"{where} shield: no emblem {bits[2]}")
            for c in (bits[1:2] + bits[3:4]):
                if c and c not in named:
                    out.append(f"{where} shield: no colour {c}")
            return
        if slot == "held":
            tile = f"fig/held/{thing}/rest"
        elif slot == "head":
            tile = f"fig/head/human_male/{thing}"
        else:
            tile = f"fig/wear/human_male/{thing}"
        if not atlas.has(tile):
            out.append(f"{where} {slot}: no picture {tile}")
        for c in bits[1:]:
            if c and c not in named:
                out.append(f"{where} {slot}: no colour {c}")

    for group in ("outfits", "classes", "creatures"):
        for who, spec in f[group].items():
            for slot, options in spec.items():
                if slot == "race":
                    continue
                for o in ([options] if isinstance(options, str) else options):
                    check(f"{group} {who}", slot, o)
    for iid, spec in f["worn"].items():
        if iid not in tables.items.defs:
            out.append(f"worn: no item {iid}")
        for slot, o in spec.items():
            if slot == "dyes":
                out.extend(f"worn {iid}: no colour {c}" for c in o if c not in named)
            else:
                check(f"worn {iid}", slot, o)
    for body in ("human_male", "dwarf_female"):
        out.extend(f"hair {s}" for pool in f["hair_styles"].values() for s in pool if not atlas.has(f"fig/hair/{body}/{s}"))
        out.extend(f"beard {s}" for pool in f["beard_styles"].values() for s in pool
                   if not atlas.has(f"fig/beard/{body}/{s}"))
    out.extend(f"skin word {w}: no skin {k}" for w, k in f.get("skin_words", [])
               if not any(k in s for s in f["skins"].values()))
    out.extend(f"hair word {w}: no colour {k}" for w, k in f["hair_words"] if k not in f["hair_colours"])
    return sorted(set(out))


def item_parts(item, tables, atlas) -> list[Part] | None:
    """A weapon or shield on its own, in its own colours (a rare blade's metal and glow, a shield's field and device),
    for the inventory card; None for things not drawn this way."""
    spec = _fig(tables)["worn"].get(item.def_id) or {}
    if "held" not in spec and "shield" not in spec:
        return None
    look = item_look(item, tables)
    fig = Figure(tables, "human", "male", f"item{item.uid}")
    dyes = spec.get("dyes")
    dye = look.get("cloth") or (dyes[stable(f"item{item.uid}", len(dyes))] if dyes else None)
    for key in ("held", "shield"):
        if key in spec:
            fig.wear(key, spec[key], dye, look)
    parts = [p for p in fig.parts(atlas) if not p[0].startswith(("fig/body/", "fig/wear/", "fig/hair/", "fig/beard/"))]
    return parts or None


def bounds(atlas, parts: list[Part], pad: int = 1) -> tuple[int, int, int, int]:
    """The smallest square around what is drawn (x, y, side), in the figure's own pixels."""
    a = compose(atlas, parts)[..., 3] > 0
    if not a.any():
        return 0, 0, atlas.tile, atlas.tile
    ys, xs = np.nonzero(a)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    side = min(atlas.tile, max(x1 - x0, y1 - y0) + 2 * pad)
    x = max(0, min(atlas.tile - side, (x0 + x1) // 2 - side // 2))
    y = max(0, min(atlas.tile - side, (y0 + y1) // 2 - side // 2))
    return x, y, side, side


def item_look(item, tables) -> dict:
    """How a thing looks: a rare item's own look (chosen by the AI, or from its name), else nothing special."""
    m = getattr(item, "magic", None) or {}
    look = m.get("look")
    return dict(look) if isinstance(look, dict) else {}


# ---------------------------------------------------------------------------- one picture per figure
_ATLAS = None
_CACHE: OrderedDict = OrderedDict()


def _atlas():
    global _ATLAS
    if _ATLAS is None:
        from realmwalker.paths import Paths
        from realmwalker.ui.gfx.atlas import load

        _ATLAS = load(str(Paths().tiles))
    return _ATLAS


def compose(atlas, parts: list[Part]) -> np.ndarray:
    """The layers stacked into one 32x32 picture (kept, so a figure is only stacked once)."""
    key = (id(atlas), tuple(parts))
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return hit
    size = atlas.tile
    acc = np.zeros((size, size, 4), np.float32)
    sheets = atlas.sheets()
    for name, (r, g, b, a), dx, dy in parts:
        rect = atlas.rect(name)
        if rect is None:
            continue
        s, x, y, w, h = rect
        tile = sheets[s][y:y + h, x:x + w].astype(np.float32)
        if w != size or h != size:
            tile = tile[:size, :size]
        layer = np.zeros((size, size, 4), np.float32)
        x0, y0 = max(0, dx), max(0, dy)
        x1, y1 = min(size, size + dx), min(size, size + dy)
        if x1 <= x0 or y1 <= y0:
            continue
        layer[y0:y1, x0:x1] = tile[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
        layer[..., 0] *= r / 255.0
        layer[..., 1] *= g / 255.0
        layer[..., 2] *= b / 255.0
        la = layer[..., 3:4] / 255.0 * (a / 255.0)
        acc[..., :3] = layer[..., :3] * la + acc[..., :3] * (1 - la)
        acc[..., 3:4] = la * 255.0 + acc[..., 3:4] * (1 - la)
    out = np.clip(acc, 0, 255).astype(np.uint8)
    _CACHE[key] = out
    while len(_CACHE) > 600:
        _CACHE.popitem(last=False)
    return out


def figure_key(parts: list[Part]) -> int:
    return hash(tuple(parts))


def bust(atlas, parts: list[Part]) -> tuple[int, int, int, int]:
    """The head and shoulders of a figure, in its own pixels (x, y, w, h): for a portrait."""
    body = next((p[0][len("fig/body/"):] for p in parts if p[0].startswith("fig/body/")), None)
    head = atlas.figures.get("heads", {}).get(body)
    if head is None:
        return 0, 0, atlas.tile, atlas.tile
    hx, hy, hw, hh = head
    side = 20
    top = max(0, min(atlas.tile - side, hy - 3))
    return 16 - side // 2, top, side, side


def draw(atlas, parts: list[Part], x: float, y: float, size: float, light=(1.0, 1.0, 1.0), alpha: float = 1.0,
         angle: float = 0.0, crop: tuple[int, int, int, int] | None = None):
    """A picture command for a figure (or the `crop` of it, in its own pixels, filling the square). At whole multiples
    of its size every pixel is drawn as a sharp square; between them the figure is first blown up to the next whole
    multiple and then smoothed down, so its pixels stay even and only their edges soften."""
    from realmwalker.ui.gfx.scene import Image

    if not parts:
        return None
    rgba = (int(255 * min(1.0, light[0])), int(255 * min(1.0, light[1])), int(255 * min(1.0, light[2])),
            int(255 * max(0.0, min(1.0, alpha))))
    tile = atlas.tile or 32
    cx, cy, cw, ch = crop or (0, 0, tile, tile)
    ratio = size / cw
    w, h = size, ch * ratio
    if abs(ratio - round(ratio)) < 0.02 and round(ratio) >= 1:
        return Image(("fig", figure_key(parts)), lambda: compose(atlas, parts), (x, y, w, h), src=(cx, cy, cw, ch),
                     rgba=rgba, smooth=False, angle=angle)
    k = max(1, int(np.ceil(ratio)))

    def make():
        im = compose(atlas, parts)
        return np.ascontiguousarray(np.repeat(np.repeat(im, k, axis=0), k, axis=1)) if k > 1 else im

    return Image(("fig", figure_key(parts), k), make, (x, y, w, h), src=(cx * k, cy * k, cw * k, ch * k), rgba=rgba,
                 smooth=True, angle=angle)
