"""Pictures for fire and what it leaves (Expansion 6 B.7, docs/ADVENTURES.md §8.14, §8.17): flames on a burning
square (three frames), embers, scorched ground, charred floors and walls, fallen beams, a broken door, and the things a
troubled town puts up (barricades, a gallows, a pyre, scaffolds, a fresh grave, a ritual circle, a cage). Drawn in
code, 32x32, in the Crawl tiles' manner (tile_art's helpers); tools/build_tiles.py adds them to the sheets."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from tile_art import S, blank, img, noise_shade, outline, planks, rng, shade, shadow, wood_wall

CHAR = (34, 28, 24)
EMBER = (236, 112, 40)
EMBER_HOT = (255, 196, 92)


def _ground(seed: int, base, spread: float = 0.16) -> np.ndarray:
    r = rng(seed)
    a = np.zeros((S, S, 4), np.float32)
    a[..., 3] = 255
    a[..., :3] = np.array(base, np.float32)
    a[..., :3] *= r.uniform(1 - spread, 1 + spread, (S, S))[..., None]
    return a


def scorched(seed: int) -> Image.Image:
    """Earth burned black, ash in drifts, a few cinders."""
    r = rng(seed)
    a = _ground(seed, (52, 46, 40), 0.22)
    for _ in range(5):  # pale drifts of ash
        cx, cy, rad = r.uniform(0, S), r.uniform(0, S), r.uniform(3, 7)
        ys, xs = np.mgrid[0:S, 0:S]
        m = (xs - cx) ** 2 + (ys - cy) ** 2 < rad * rad
        a[m, :3] = a[m, :3] * 0.5 + np.array([120, 114, 106], np.float32) * 0.5
    for _ in range(9):  # black cinders
        x, y = int(r.integers(0, S - 1)), int(r.integers(0, S - 1))
        a[y:y + 2, x:x + 2, :3] = (20, 18, 16)
    return img(a)


def embers(frame: int, seed: int = 0) -> Image.Image:
    """Ash with coals still glowing in it; the frames breathe."""
    r = rng(900 + seed)
    a = _ground(901 + seed, (44, 36, 32), 0.2)
    for k in range(14):
        x, y = int(r.integers(1, S - 2)), int(r.integers(1, S - 2))
        heat = 0.55 + 0.45 * math.sin(frame * 2.1 + k * 1.7)
        c = np.array(EMBER, np.float32) * (0.5 + 0.5 * heat)
        a[y:y + 2, x:x + 2, :3] = c
        if heat > 0.8:
            a[y, x, :3] = EMBER_HOT
    return img(a)


def charred_floor(seed: int) -> Image.Image:
    """Floorboards burned black, split along the grain, holes to the earth below."""
    r = rng(seed)
    a = np.asarray(planks(seed, (46, 36, 28)).convert("RGBA"), np.float32).copy()
    for _ in range(3):  # holes burned through
        x, y = int(r.integers(2, 26)), int(r.integers(2, 26))
        a[y:y + 4, x:x + 5, :3] = (18, 14, 12)
    for _ in range(12):  # alligatored char, catching the light
        x, y = int(r.integers(0, S - 3)), int(r.integers(0, S))
        a[y, x:x + 3, :3] = (78, 70, 62)
    return img(a)


def charred_wall(seed: int) -> Image.Image:
    """A timber wall burned black, its boards split and glowing at the cracks no longer."""
    a = np.asarray(wood_wall(seed).convert("RGBA"), np.float32).copy()
    a[..., :3] = a[..., :3] * 0.38 + np.array(CHAR, np.float32) * 0.4
    r = rng(seed + 7)
    for _ in range(10):
        x, y = int(r.integers(0, S)), int(r.integers(0, S - 4))
        a[y:y + 4, x, :3] = (88, 80, 72)
    a[0:3, :, :3] *= 0.5
    return img(a)


def fallen_beam(seed: int) -> Image.Image:
    """A roof beam come down across the square, burned black, ash round it."""
    im = blank()
    d = ImageDraw.Draw(im)
    r = rng(seed)
    flip = seed % 2
    x0, x1 = (3, 29) if not flip else (29, 3)
    beam = (40, 32, 26, 255)
    d.line([(x0, 8 + int(r.integers(0, 4))), (x1, 24 + int(r.integers(0, 4)))], fill=beam, width=6)
    d.line([(x0, 7), (x1, 23)], fill=(70, 60, 52, 255), width=1)
    for _ in range(4):  # char scales along it
        t = r.uniform(0.1, 0.9)
        x, y = x0 + (x1 - x0) * t, 9 + 16 * t
        d.rectangle([x - 1, y, x + 1, y + 1], fill=(96, 86, 76, 255))
    d.line([(6 if not flip else 26, 26), (12 if not flip else 20, 21)], fill=beam, width=3)  # a broken joist
    return shadow(outline(noise_shade(im, seed, 0.1)))


def door_broken(seed: int) -> Image.Image:
    """A door kicked in: hanging by one hinge, splinters on the floor."""
    im = blank()
    d = ImageDraw.Draw(im)
    wood = (96, 66, 40, 255)
    d.polygon([(5, 4), (15, 6), (13, 29), (4, 27)], fill=wood)  # what is left of the door, swung in
    d.line([(6, 10), (14, 11)], fill=(62, 62, 66, 255), width=1)
    d.line([(5, 21), (13, 22)], fill=(62, 62, 66, 255), width=1)
    d.line([(9, 6), (9, 28)], fill=shade(wood, 0.7))
    r = rng(seed)
    for _ in range(6):  # splinters
        x, y = int(r.integers(14, 28)), int(r.integers(18, 29))
        d.line([(x, y), (x + int(r.integers(2, 5)), y + int(r.integers(-1, 2)))], fill=shade(wood, 1.2), width=1)
    return shadow(outline(im))


def barricade(seed: int) -> Image.Image:
    """Planks, a cart wheel and sacks heaped across a street."""
    im = blank()
    d = ImageDraw.Draw(im)
    r = rng(seed)
    d.ellipse([16, 14, 29, 27], outline=(84, 58, 36, 255), width=2)  # a cart wheel
    d.line([(22, 14), (22, 27)], fill=(84, 58, 36, 255))
    d.line([(16, 20), (29, 20)], fill=(84, 58, 36, 255))
    for i in range(3):  # sacks
        x = 3 + i * 6
        d.ellipse([x, 18, x + 8, 28], fill=shade((170, 150, 110, 255), float(r.uniform(0.85, 1.05))))
    for k in range(3):  # planks across
        y = 8 + k * 5
        d.line([(2, y + int(r.integers(-2, 3))), (29, y + int(r.integers(-2, 3)))], fill=(120, 84, 50, 255), width=3)
    return shadow(outline(noise_shade(im, seed, 0.08)))


def gallows(seed: int) -> Image.Image:
    """A gallows: two posts, a crossbeam, a rope with its noose."""
    im = blank()
    d = ImageDraw.Draw(im)
    wood = (88, 62, 40, 255)
    d.rectangle([4, 4, 7, 30], fill=wood)
    d.rectangle([4, 3, 27, 6], fill=wood)
    d.line([(7, 12), (13, 6)], fill=wood, width=2)  # the brace
    d.line([(22, 6), (22, 17)], fill=(170, 150, 110, 255), width=1)
    d.ellipse([19, 17, 25, 23], outline=(170, 150, 110, 255))
    d.rectangle([12, 26, 30, 30], fill=shade(wood, 0.8))  # the platform's edge
    return shadow(outline(noise_shade(im, seed, 0.08)))


def pyre(seed: int) -> Image.Image:
    """Logs stacked crosswise to waist height, a shrouded shape laid on top."""
    im = blank()
    d = ImageDraw.Draw(im)
    r = rng(seed)
    for row in range(4):
        y = 26 - row * 4
        for col in range(3):
            x = 5 + col * 8 + (row % 2) * 3
            c = shade((122, 86, 52, 255), float(r.uniform(0.8, 1.1)))
            d.rectangle([x, y, x + 6, y + 3], fill=c)
            d.ellipse([x, y, x + 3, y + 3], fill=(176, 140, 96, 255))
    d.rounded_rectangle([7, 7, 26, 12], 3, fill=(214, 206, 188, 255))  # the shroud
    d.ellipse([22, 6, 27, 12], fill=(222, 214, 196, 255))
    return shadow(outline(im))


def scaffold(seed: int) -> Image.Image:
    """Poles lashed together with a plank walk, against a wall going up."""
    im = blank()
    d = ImageDraw.Draw(im)
    pole = (150, 118, 76, 255)
    for x in (5, 16, 27):
        d.line([(x, 2), (x, 30)], fill=pole, width=2)
    for y in (10, 21):
        d.rectangle([3, y, 29, y + 2], fill=(176, 140, 92, 255))
    d.line([(5, 21), (16, 10)], fill=pole)
    d.line([(16, 21), (27, 10)], fill=pole)
    if seed % 2:  # a bucket on a rope
        d.line([(22, 12), (22, 18)], fill=(170, 150, 110, 255))
        d.rectangle([20, 18, 24, 21], fill=(100, 80, 60, 255))
    return shadow(outline(im))


def grave_fresh(seed: int) -> Image.Image:
    """A new grave: raw earth heaped long, a plain wooden marker, flowers left."""
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse([5, 13, 27, 30], fill=(92, 64, 42, 255))
    d.ellipse([8, 15, 22, 23], fill=(116, 82, 54, 255))
    wood = (150, 116, 72, 255)
    d.rectangle([14, 3, 17, 18], fill=wood)
    if seed % 2:
        d.rectangle([10, 7, 21, 9], fill=wood)
    r = rng(seed)
    for _ in range(3):
        x, y = int(r.integers(8, 24)), int(r.integers(22, 28))
        d.point((x, y), fill=[(210, 70, 60, 255), (230, 210, 90, 255), (240, 240, 230, 255)][int(r.integers(0, 3))])
    return shadow(outline(noise_shade(im, seed, 0.08)))


def ritual_circle(seed: int) -> Image.Image:
    """A circle drawn on the ground in chalk and something darker, signs at its points."""
    im = blank()
    d = ImageDraw.Draw(im)
    chalk = (226, 222, 210, 220)
    d.ellipse([2, 2, 29, 29], outline=chalk, width=1)
    d.ellipse([6, 6, 25, 25], outline=(150, 40, 40, 200), width=1)
    pts = [(16 + 13 * math.cos(k * math.tau / 5 - math.pi / 2), 16 + 13 * math.sin(k * math.tau / 5 - math.pi / 2))
           for k in range(5)]
    for k in range(5):  # the star
        d.line([pts[k], pts[(k + 2) % 5]], fill=chalk, width=1)
    for x, y in pts:
        d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=(150, 40, 40, 230))
    return im


def cage(seed: int) -> Image.Image:
    """An iron cage, man-high, its door chained shut."""
    im = blank()
    d = ImageDraw.Draw(im)
    iron = (92, 92, 98, 255)
    d.rectangle([4, 4, 27, 6], fill=iron)
    d.rectangle([4, 27, 27, 29], fill=iron)
    for x in range(5, 28, 4):
        d.line([(x, 6), (x, 27)], fill=iron, width=1)
    d.line([(16, 15), (21, 18)], fill=(150, 150, 156, 255), width=1)  # the chain on its door
    d.rectangle([17, 17, 19, 19], fill=(120, 110, 70, 255))  # the lock
    return shadow(outline(im))


def blaze(frame: int) -> Image.Image:
    """Fire standing on a square: tongues of flame over a red heart, three frames."""
    im = blank()
    d = ImageDraw.Draw(im)
    r = rng(950 + frame)
    d.ellipse([3, 20, 29, 31], fill=(150, 40, 20, 200))
    for k in range(5):
        x = 4 + k * 6 + int(r.integers(-1, 2))
        top = 4 + int(r.integers(0, 9)) + ((k + frame) % 3) * 2
        d.polygon([(x - 3, 28), (x, top), (x + 3, 28)], fill=(232, 102, 34, 235))
        d.polygon([(x - 1, 28), (x, top + 7), (x + 1, 28)], fill=(255, 200, 90, 240))
    return outline(im, (90, 24, 10, 160))


def all_drawn() -> dict[str, Image.Image]:
    out: dict[str, Image.Image] = {}
    for i in range(3):
        out[f"floor/scorched_{i}"] = scorched(1000 + i)
        out[f"floor/charred_{i}"] = charred_floor(1010 + i)
        out[f"floor/embers_{i}"] = embers(i)
        out[f"fx/blaze_{i}"] = blaze(i)
    for i in range(2):
        out[f"wall/charred_{i}"] = charred_wall(1020 + i)
        out[f"feature/fallen_beam_{i}"] = fallen_beam(1030 + i)
        out[f"feature/barricade_{i}"] = barricade(1040 + i)
        out[f"feature/scaffold_{i}"] = scaffold(1050 + i)
        out[f"feature/grave_fresh_{i}"] = grave_fresh(1060 + i)
        out[f"feature/pyre_{i}"] = pyre(1070 + i)
    out["feature/door_broken"] = door_broken(1080)
    out["feature/gallows"] = gallows(1081)
    out["feature/ritual_circle"] = ritual_circle(1082)
    out["feature/cage"] = cage(1083)
    return out
