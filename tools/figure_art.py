"""People drawn as pixel art, in layers: a body for each race and sex, then clothes, armour, hair, beards, hats and
helmets, cloaks, and what they hold. Used by tools/build_tiles.py; the game stacks the layers (ui/gfx/dolls.py).

Every body is built from proportions (head, shoulders, waist, arms, legs) into a map of body parts. Clothes and armour
are those parts repainted in a material, so one coat fits a dwarf and an elf alike. Shading is worked out from the
shapes, with the light from the top left, and every figure gets a dark outline: sharp pixels, no smoothing.

Cloth, hair, leather and metal are drawn in greys and coloured when drawn (multiplied by a colour), so a red tunic and
a green one are one picture. Weapons and shields are drawn once, held at a hand, and moved to each body's hand.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

W = H = 32
GROUND = 31  # the row under the feet (its outline is the last row)
(EMPTY, HEAD, NECK, TORSO, UARM, LARM, HAND, PELVIS, ULEG, LLEG, FOOT, EAR) = range(12)
NAMES = {HEAD: "head", NECK: "neck", TORSO: "torso", UARM: "upper arm", LARM: "forearm", HAND: "hand",
         PELVIS: "hips", ULEG: "thigh", LLEG: "shin", FOOT: "foot", EAR: "ear"}

ROOT = Path(__file__).resolve().parent.parent
SEXES = ("male", "female")


@lru_cache(maxsize=1)
def _data() -> tuple[dict, dict]:
    """The figures' data (data/sprites.json) and what each people may look like (data/appearance.json)."""
    sprites = json.loads((ROOT / "data" / "sprites.json").read_text(encoding="utf-8"))["figures"]
    looks = json.loads((ROOT / "data" / "appearance.json").read_text(encoding="utf-8"))["looks"]
    return sprites, looks


def proportions(race: str, sex: str, build: str = "average") -> dict:
    """A body's proportions in pixels (data/sprites.json figures.bodies), changed by its build."""
    sprites, _ = _data()
    bodies = sprites["bodies"]
    p = dict((bodies.get(race) or bodies["human"])[sex])
    for k, v in sprites["builds"].get(build, {}).items():
        p[k] = p.get(k, 0) + v
    p["arm"] = max(2, min(4, p["arm"]))
    p["leg"] = max(2, p["leg"])
    p["waist"] = max(4, min(p["waist"], p["sh"] + 2))
    p["hip"] = max(p["hip"], 2 * p["leg"] + p["gap"])
    return p


# Grey ramps (outline, shadow, base, light, highlight): coloured when drawn.
NEUTRAL = np.array([[30, 28, 28], [96, 92, 90], [156, 152, 148], [204, 200, 196], [240, 238, 234]], np.float32)
# Skin is drawn in light greys and coloured when drawn with the real skin colour (data/sprites.json figures.skins), so
# any people's skin, however strange, is one colour in the data.
SKIN = np.array([[60, 44, 42], [176, 152, 148], [228, 222, 218], [246, 242, 238], [254, 252, 250]], np.float32)
EYE = (34, 26, 24)


class Body:
    """A body's map of parts, and where its head, hands and feet are."""

    def __init__(self, race: str, sex: str, build: str = "average") -> None:
        p = proportions(race, sex, build)
        self.race, self.sex, self.build, self.p = race, sex, build, p
        g = np.zeros((H, W), np.int8)
        c = 16
        y = GROUND
        foot_top = y - p["foot"]
        lleg_top = foot_top - p["lleg"]
        uleg_top = lleg_top - p["uleg"]
        pelvis_top = uleg_top - p["pelvis"]
        torso_top = pelvis_top - p["torso"]
        neck_top = torso_top - p["neck"]
        head_top = neck_top - p["head_h"]
        self.rows = dict(foot=foot_top, lleg=lleg_top, uleg=uleg_top, pelvis=pelvis_top, torso=torso_top,
                         neck=neck_top, head=head_top)
        # Legs and feet.
        half_gap = p["gap"] // 2
        self.legs = []
        for side in (-1, 1):
            if side < 0:
                x0, x1 = c - half_gap - p["leg"], c - half_gap
            else:
                x0, x1 = c + half_gap, c + half_gap + p["leg"]
            self.legs.append((x0, x1))
            g[uleg_top:lleg_top, x0:x1] = ULEG
            g[lleg_top:foot_top, x0:x1] = LLEG
            fx0, fx1 = (x0 - 1, x1) if side < 0 else (x0, x1 + 1)
            g[foot_top:y, fx0:fx1] = FOOT
        # Hips.
        hw = p["hip"]
        g[pelvis_top:uleg_top, c - hw // 2:c + hw // 2] = PELVIS
        # Torso, narrowing from the shoulders to the waist.
        n = p["torso"]
        self.torso_rows = []
        for i in range(n):
            t = i / max(1, n - 1)
            w = int(round((p["sh"] - (p["sh"] - p["waist"]) * min(1.0, t * 1.4)) / 2)) * 2
            g[torso_top + i, c - w // 2:c + w // 2] = TORSO
            self.torso_rows.append((c - w // 2, c + w // 2))
        # Arms hang from the shoulders, a little apart from the waist.
        sh_l, sh_r = c - p["sh"] // 2, c + p["sh"] // 2
        arm = p["arm"]
        arm_top = torso_top + 1
        arm_len = n + p["pelvis"] - 1
        upper = arm_len // 2
        self.hands = []
        for side in (-1, 1):
            x0, x1 = (sh_l - arm, sh_l) if side < 0 else (sh_r, sh_r + arm)
            g[arm_top:arm_top + upper, x0:x1] = UARM
            g[arm_top + upper:arm_top + arm_len, x0:x1] = LARM
            g[arm_top + arm_len:arm_top + arm_len + 2, x0:x1] = HAND
            self.hands.append(((x0 + x1 - 1) / 2, arm_top + arm_len + 0.5))
        # Round the shoulders: the arm's top outer corner goes.
        g[arm_top, sh_l - arm] = EMPTY if arm > 2 else g[arm_top, sh_l - arm]
        g[arm_top, sh_r + arm - 1] = EMPTY if arm > 2 else g[arm_top, sh_r + arm - 1]
        g[torso_top, sh_l:sh_l + 1] = EMPTY
        g[torso_top, sh_r - 1:sh_r] = EMPTY
        # Neck and head.
        if p["neck"]:
            g[neck_top:torso_top, c - 2:c + 2] = NECK
        hw2 = p["head_w"] // 2
        hh = p["head_h"]
        for i in range(hh):
            inset = 1 if i == 0 else (1 if i >= hh - 2 else 0)
            if i == hh - 1:
                inset = 2
            g[head_top + i, c - hw2 + inset:c + hw2 - inset] = HEAD
        self.head = (c - hw2, head_top, p["head_w"], hh)
        self.grid = g
        self.c = c

    def mask(self, *parts) -> np.ndarray:
        return np.isin(self.grid, parts)


# ---------------------------------------------------------------------------- shading and drawing
def shades(mask: np.ndarray, flat: bool = False) -> np.ndarray:
    """Shade index per pixel (1 shadow .. 4 highlight) for a shape lit from the top left; -1 outside."""
    s = np.full(mask.shape, -1, np.int8)
    if not mask.any():
        return s
    s[mask] = 2
    if flat:
        return s
    up = np.zeros_like(mask)
    up[1:] = mask[:-1]
    left = np.zeros_like(mask)
    left[:, 1:] = mask[:, :-1]
    down = np.zeros_like(mask)
    down[:-1] = mask[1:]
    right = np.zeros_like(mask)
    right[:, :-1] = mask[:, 1:]
    lit = mask & (~up | ~left)
    dark = mask & (~down | ~right)
    s[dark] = 1
    s[lit & ~dark] = 3
    corner = mask & ~up & ~left
    s[corner] = 4
    return s


def outline(mask: np.ndarray) -> np.ndarray:
    m = np.zeros_like(mask)
    m[1:] |= mask[:-1]
    m[:-1] |= mask[1:]
    m[:, 1:] |= mask[:, :-1]
    m[:, :-1] |= mask[:, 1:]
    return m & ~mask


def paint(shade: np.ndarray, ramp: np.ndarray, out: np.ndarray | None = None, line: np.ndarray | None = None) -> np.ndarray:
    """Pixels coloured from a ramp by shade index; outline pixels in the ramp's darkest colour."""
    img = np.zeros((H, W, 4), np.uint8) if out is None else out
    for k in range(1, 5):
        m = shade == k
        img[m, :3] = ramp[k]
        img[m, 3] = 255
    if line is not None:
        img[line, :3] = ramp[0]
        img[line, 3] = 255
    return img


def to_image(a: np.ndarray) -> Image.Image:
    return Image.fromarray(a, "RGBA")


# ---------------------------------------------------------------------------- bodies
def base(body: Body) -> Image.Image:
    """The bare figure in skin (tinted per person), with eyes, brows and a mouth."""
    g = body.grid
    m = g != EMPTY
    s = shades(m)
    # Where an arm lies against the body, a darker seam so the arm reads.
    torso = np.isin(g, (TORSO, PELVIS))
    for part in (UARM, LARM, HAND):
        pm = g == part
        s[pm & np.roll(torso, -1, axis=1)] = 1  # the left arm's inner edge
        s[pm & np.roll(torso, 1, axis=1)] = 1  # the right arm's inner edge
    legs = np.isin(g, (ULEG, LLEG, FOOT))
    s[legs & np.roll(legs, -2, axis=1) & ~np.roll(legs, -1, axis=1)] = 1
    a = paint(s, SKIN, line=outline(m))
    hx, hy, hw, hh = body.head
    c = body.c
    ey = hy + hh // 2
    a[ey, c - 2, :3] = EYE
    a[ey, c + 1, :3] = EYE
    a[ey - 1, c - 3:c - 1, :3] = SKIN[1]  # brows
    a[ey - 1, c + 1:c + 3, :3] = SKIN[1]
    a[ey + 1, c - 1, :3] = SKIN[1]  # nose
    if hh >= 8:
        a[ey + 2, c - 1:c + 1, :3] = (128, 120, 120)  # mouth
    return to_image(a)


def body_key(race: str, sex: str, build: str = "average") -> str:
    """The name of a body in the tile sheets: "dwarf_male", "elf_female_slight"."""
    return f"{race}_{sex}" + ("" if build == "average" else f"_{build}")


def bodies() -> dict[str, Body]:
    """Every body to draw: each people with a body in data/sprites.json, each sex, and each build that people may
    have (data/appearance.json looks), the average one always."""
    sprites, looks = _data()
    races = looks["races"]
    out = {}
    for race in sprites["bodies"]:
        if race.startswith("_"):
            continue
        spec = dict(races["_default"])
        spec.update(races.get(race) or {})
        builds = ["average"] + [b for b in spec["builds"] if b != "average"]
        for sex in SEXES:
            for build in builds:
                out[body_key(race, sex, build)] = Body(race, sex, build)
    return out
