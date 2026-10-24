"""People as pixel-art figures: a body for their people, sex and build, coloured skin, eyes, hair and beard, the marks
of their people (ears, tusks, horns), scars and paint, then what they wear and hold, each a layer in the tile sheets
(tools/figure_art.py, tools/figure_gear.py) coloured when drawn.

How someone looks is a set of choices (rules/looks.py): the player's are made at character creation and kept with
the character; everyone else's are read from the words that describe them. The player and companions wear what they
really wear, in the colours of those very things (a dyed cloak, a blackened blade, a rare item's own look, or the
colours chosen at creation); townsfolk dress for their trade and bandits, guards and cultists for theirs
(data/sprites.json "figures"). A figure is stacked once into a single picture and kept (compose()).

A people with no body of its own in the tile sheets is drawn on the human one, and a skin with no colour of its own
in the data takes the first human one, so a new race can be played before anyone draws it.
"""

from __future__ import annotations

import zlib
from collections import OrderedDict

import numpy as np

from realmwalker.rules import looks as looks_rules

Part = tuple[str, tuple[int, int, int, int], int, int]  # tile, colour multiplied in (r, g, b, alpha), offset x, y
WHITE = (255, 255, 255, 255)
LAYERS = ("body", "legs", "feet", "over", "tabard", "belt", "hands")
HIDES_HAIR = ("hood", "greathelm", "kettle", "nasal", "horned", "furhat", "wizard", "turban", "veil", "headscarf",
              "tall_hat", "spired", "crested")
BACK_FEATURES = ("tail",)


def stable(key: str, n: int) -> int:
    return zlib.crc32(key.encode("utf-8")) % max(1, n) if n > 0 else 0


def choose(options, key: str):
    if not options:
        return ""
    if isinstance(options, str):
        return options
    return options[stable(key, len(options))]


def body_key(race: str, sex: str, build: str = "average") -> str:
    """The name of a body in the tile sheets (tools/figure_art.py body_key)."""
    return f"{race}_{'female' if sex == 'female' else 'male'}" + ("" if build in ("", "average") else f"_{build}")


def resolve_body(atlas, race: str, sex: str, build: str = "average") -> str:
    """The body this person is drawn on: their own if it is in the sheets, else the nearest there is (their people's
    average body, a human body of their build, a human one)."""
    sex = "female" if sex == "female" else "male"
    for key in (body_key(race, sex, build), body_key(race, sex), body_key("human", sex, build), body_key("human", sex),
                "human_male"):
        if atlas is None or atlas.has(f"fig/body/{key}"):
            return key
    return "human_male"


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


def skin_colour(tables, race: str, skin: str) -> tuple[int, int, int]:
    skins = _fig(tables)["skins"]
    palette = {k: v for k, v in (skins.get(race) or skins["human"]).items() if not k.startswith("_")}
    if skin not in palette:  # a skin named for this people but not coloured: look in every palette
        for other in skins.values():
            if isinstance(other, dict) and skin in other and not skin.startswith("_"):
                return tuple(other[skin])
        return tuple(next(iter(palette.values())))
    return tuple(palette[skin])


class Figure:
    """Builds the list of layers for one person."""

    def __init__(self, tables, race: str, sex: str, key: str, looks: dict | None = None) -> None:
        self.t = tables
        self.f = _fig(tables)
        self.race = race
        self.sex = sex
        self.key = key
        self.look = looks_rules.normalise(tables, looks, race, sex, key)
        f = self.f
        self.skin = skin_colour(tables, race, self.look["skin"])
        self.hair = tuple(f["hair_colours"].get(self.look["hair_colour"], f["hair_colours"]["brown"]))
        self.beard_rgb = tuple(f["hair_colours"].get(self.look["beard_colour"], self.hair))
        self.eye_rgb = tuple(f["eye_colours"].get(self.look["eyes"], f["eye_colours"]["brown"]))
        self.paint_rgb = tuple(f["paint_colours"].get(self.look["paint_colour"], f["paint_colours"]["woad"]))
        self.slots: dict[str, tuple[str, tuple]] = {}  # slot -> (thing, colour)
        self.cloak: tuple | None = None
        self.head: tuple[str, tuple] | None = None
        self.held: tuple[str, tuple, tuple | None] | None = None  # weapon, metal colour, glow
        self.left: tuple[str, tuple] | None = None  # something small in the other hand (a torch)
        self.shield: tuple | None = None  # shape, field colour, emblem, emblem colour
        self.bare_head = False  # leave off the hat or helmet (a portrait at character creation)

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
            small = thing in ("torch", "lantern", "book", "holy_symbol", "letter")
            if hand == "left" or (small and self.held is not None):
                self.left = (thing, metal)
            else:
                if self.held is not None and self.held[0] in ("torch", "lantern", "book", "holy_symbol", "letter"):
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
        b = resolve_body(atlas, self.race, self.sex, self.look["build"])
        look = self.look
        out: list[Part] = []

        def add(name: str, rgb=(255, 255, 255), dx: int = 0, dy: int = 0, alpha: int = 255) -> None:
            if atlas.has(name):
                out.append((name, (int(rgb[0]), int(rgb[1]), int(rgb[2]), alpha), dx, dy))

        tints = self.f.get("feature_tints", {})

        def feature(name: str, option: str) -> None:
            tint = tints.get(name, "")
            add(f"fig/feature/{b}/{name}_{option}", self.skin if tint == "skin" else (
                self.hair if tint == "hair" else (255, 255, 255)))

        feats = look.get("features") or {}
        if self.cloak:
            add(f"fig/cloak/{b}/back", self.cloak)
        for name in BACK_FEATURES:
            if feats.get(name):
                feature(name, feats[name])
        add(f"fig/body/{b}", self.skin)
        if look.get("paint") not in (None, "", "none"):
            add(f"fig/paint/{b}/{look['paint']}", self.paint_rgb)
        add(f"fig/eyes/{b}", self.eye_rgb)
        if look.get("mark") not in (None, "", "none"):
            add(f"fig/mark/{b}/{look['mark']}")
        for slot in LAYERS:
            if slot in self.slots:
                thing, rgb = self.slots[slot]
                add(f"fig/wear/{b}/{thing}", rgb)
        if self.cloak:
            add(f"fig/cloak/{b}/front", self.cloak)
        if look.get("beard") not in (None, "", "none"):
            add(f"fig/beard/{b}/{look['beard']}", self.beard_rgb)
        head = None if self.bare_head else self.head
        hidden = head is not None and head[0] in HIDES_HAIR
        if look.get("hair") not in (None, "", "bald") and not hidden:
            add(f"fig/hair/{b}/{look['hair']}", self.hair)
        for name, option in feats.items():
            if name not in BACK_FEATURES and option:
                feature(name, option)
        if head:
            thing, rgb = head
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
                "gauntlets", "greaves", "kettle", "nasal", "greathelm", "horned", "crown", "circlet", "lamellar", "spired",
                "crested"}


# ---------------------------------------------------------------------------- who
def npc(npc, tables, atlas=None) -> list[Part]:
    """A townsperson dressed for their trade, in the manner of their people."""
    fig = Figure(tables, npc.race, npc.sex, f"npc{npc.id}", looks_rules.of_npc(tables, npc))
    fig.outfit(outfit_for(tables, npc.job, npc.culture, npc.sex))
    if npc.flags.get("holding"):  # (something they carry in a scene: a letter for you)
        fig.wear("held", npc.flags["holding"])
    return fig.parts(atlas or _atlas())


def outfit_for(tables, job: str, culture: str, sex: str) -> dict:
    """What a townsperson wears (data/sprites.json figures): their trade's outfit, then their people's dress over it
    ("cultures": the people's everyday wear "_", by sex "_male"/"_female", and by trade), slot by slot."""
    f = _fig(tables)
    outfits = f["outfits"]
    spec = dict(outfits.get(job) or outfits["_"])
    dress = f.get("cultures", {}).get(culture_style(tables, culture), {})
    like = {"soldier": "guard"}.get(job, job)  # soldiers dress as their people's guards do
    for key in ("_", f"_{sex}", like, job, f"{job}_{sex}"):
        spec.update(dress.get(key, {}))
    return spec


def culture_style(tables, culture: str) -> str:
    """The people whose dress a culture wears (its town style: the same peoples)."""
    cultures = getattr(tables, "cultures", None)
    if cultures is not None and culture in getattr(cultures, "ids", ()):
        try:
            return cultures.town_style(culture)
        except Exception:  # (an old culture id)
            return culture
    return culture


def creature(def_id: str, tables, key: str, atlas=None, sex: str = "", culture: str = "") -> list[Part]:
    """A creature: its own picture, or a dressed figure for people (bandits, guards...); `sex` when their name says.
    One whose figure says `dress` (a trade: mages, priests) wears what that trade wears among its `culture`."""
    spec = _fig(tables)["creatures"].get(def_id)
    if spec is None:
        return [(f"creature/{def_id}", WHITE, 0, 0)]
    sex = sex or ("female" if stable(key + "sex", 5) == 0 else "male")
    race = spec.get("race", ["human"])[0] if isinstance(spec.get("race"), list) else "human"
    fig = Figure(tables, race, sex, key, looks_rules.from_text(tables, "", race, sex, 30, key))
    wear = {k: v for k, v in spec.items() if k not in ("race", "dress")}
    if spec.get("dress") and culture:  # (["mage"]: a list, as every figure slot is)
        wear.update(_fig(tables).get("cultures", {}).get(culture_style(tables, culture), {}).get(spec["dress"][0], {}))
    fig.outfit(wear)
    return fig.parts(atlas or _atlas())


def character_looks(char, tables) -> dict:
    """How the player or a companion looks: chosen at creation, or (one taken from the townsfolk) read from their words."""
    if getattr(char, "looks", None):
        return looks_rules.normalise(tables, char.looks, char.race, char.sex, f"pc{char.name}")
    return looks_rules.from_text(tables, getattr(char, "appearance", ""), char.race, char.sex,
                                 getattr(char, "age", 30), f"pc{char.name}")


def character(char, tables, *, lit: bool = False, atlas=None, bare_head: bool = False) -> list[Part]:
    """The player or a companion, in what they wear and hold, in the colours of those very things; in a beast's or
    another creature's shape (Animal Shapes, Shapechange: Expansion 3 F.8), that creature."""
    shape = (getattr(char, "spells", None) or {}).get("shape")
    if isinstance(shape, dict) and shape.get("form") in tables.creatures:
        return creature(shape["form"], tables, f"pc{char.name}", atlas, getattr(char, "sex", ""))
    f = _fig(tables)
    worn = f["worn"]
    look = character_looks(char, tables)
    fig = Figure(tables, char.race, char.sex, f"pc{char.name}", look)
    fig.bare_head = bare_head
    dressed = set()
    for slot in ("under", "main", "armor", "outer", "head", "helmet", "hands", "feet", "main_hand", "off_hand"):
        it = char.equipped_item(slot)
        if it is None:
            continue
        spec = worn.get(it.def_id)
        if not spec:
            continue
        item = item_look(it, tables)
        dyes = spec.get("dyes")
        chosen = look.get("cloak") if ("cloak" in spec or spec.get("head", "").startswith("hood")) else look.get("dye")
        dye = item.get("cloth") or (chosen if dyes and chosen else None) or (
            dyes[stable(f"item{it.uid}", len(dyes))] if dyes else None)
        for key in ("body", "legs", "over", "feet", "hands", "head", "cloak", "held", "shield", "tabard", "belt"):
            if key in spec:
                fig.wear(key, spec[key], dye, item, hand="left" if slot == "off_hand" else "right")
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

    for people, dress in f.get("cultures", {}).items():
        if not isinstance(dress, dict):  # (the "_comment")
            continue
        for who, spec in dress.items():
            if who.startswith("_") and who not in ("_", "_male", "_female"):
                continue
            for slot, options in spec.items():
                for o in ([options] if isinstance(options, str) else options):
                    check(f"cultures {people} {who}", slot, o)
    for group in ("outfits", "classes", "creatures"):
        for who, spec in f[group].items():
            for slot, options in spec.items():
                if slot == "race":
                    continue
                if slot == "dress":  # (a trade whose dress among each people it borrows)
                    out.extend(f"{group} {who}: dress {o} is no trade's outfit" for o in options if o not in f["outfits"])
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
    out += looks_problems(tables, atlas)
    return sorted(set(out))


def looks_problems(tables, atlas) -> list[str]:
    """Every look a people may have (data/appearance.json looks) must be drawable: a colour for each skin, hair, eye
    and paint, and a picture for each hair style, beard, mark, paint and feature on each of that people's bodies."""
    f = _fig(tables)
    d = looks_rules.data(tables)
    out: list[str] = []
    races = [r for r in d["races"] if not r.startswith("_")] + ["_default"]
    for race in races:
        for sex in ("male", "female"):
            opts = looks_rules.options(tables, race, sex)
            real = race if race in tables.races else "human"
            for build in opts["build"]:
                body = resolve_body(atlas, real, sex, build)
                for style in opts["hair"]:
                    if style != "bald" and not atlas.has(f"fig/hair/{body}/{style}"):
                        out.append(f"{race} {sex}: no hair {style} on {body}")
                for beard in opts["beard"]:
                    if beard != "none" and not atlas.has(f"fig/beard/{body}/{beard}"):
                        out.append(f"{race} {sex}: no beard {beard} on {body}")
                for mark in opts["mark"]:
                    if mark != "none" and not atlas.has(f"fig/mark/{body}/{mark}"):
                        out.append(f"{race} {sex}: no mark {mark} on {body}")
                for paint in opts["paint"]:
                    if paint != "none" and not atlas.has(f"fig/paint/{body}/{paint}"):
                        out.append(f"{race} {sex}: no paint {paint} on {body}")
                for feat, pool in opts["features"].items():
                    for option in pool:
                        if option != "none" and not atlas.has(f"fig/feature/{body}/{feat}_{option}"):
                            out.append(f"{race} {sex}: no {feat} {option} on {body}")
                if not atlas.has(f"fig/eyes/{body}"):
                    out.append(f"{race} {sex}: no eyes on {body}")
            skins = f["skins"].get(real) or f["skins"]["human"]
            out.extend(f"{race}: no colour for skin {k}" for k in opts["skin"] if k not in skins)
            out.extend(f"{race}: no colour for hair {k}" for k in opts["hair_colour"] if k not in f["hair_colours"])
            out.extend(f"{race}: no colour for eyes {k}" for k in opts["eyes"] if k not in f["eye_colours"])
            out.extend(f"{race}: no colour for paint {k}" for k in opts["paint_colour"] if k not in f["paint_colours"])
    out.extend(f"dye {c}: no such colour" for c in d["dyes"] if c not in f["colours"])
    return out


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


def bust(atlas, parts: list[Part], side: int = 20) -> tuple[int, int, int, int]:
    """The head and shoulders of a figure, in its own pixels (x, y, w, h): for a portrait. A smaller side is closer to
    the face (16: the face and a little of the shoulders)."""
    body = next((p[0][len("fig/body/"):] for p in parts if p[0].startswith("fig/body/")), None)
    head = atlas.figures.get("heads", {}).get(body)
    if head is None:
        return 0, 0, atlas.tile, atlas.tile
    hx, hy, hw, hh = head
    top = max(0, min(atlas.tile - side, hy - 3 - (20 - side) // 4))
    return 16 - side // 2, top, side, side


FROST = (206, 226, 255)  # (a Simulacrum: snow in a likeness, Expansion 3 G.3)


def frost(parts: list[Part], share: float = 0.6) -> list[Part]:
    """A figure made of snow: every layer's colour drawn most of the way to a cold white, a little see-through."""
    out = []
    for tile, (r, g, b, a), dx, dy in parts:
        out.append((tile, (int(r + (FROST[0] - r) * share), int(g + (FROST[1] - g) * share),
                           int(b + (FROST[2] - b) * share), int(a * 0.9)), dx, dy))
    return out


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
