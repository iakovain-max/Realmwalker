"""The Reading's picture (Expansion 6 F.4): the seer's fire at night, a red cloth, and the Wayfarer's Deck laid on it in
a cross (the Shadow above, the Key and the Hand to either side, the Turn in the middle, the Door below), each great
card crossed by a minor one; the villain's own card, when it turned up, lies upside down across the corner. Before the
cards are read they lie face down. Card faces are tiles `card/<id>`, `card/suit_<suit>`, `card/back`
(tools/card_art.py), drawn at whole multiples so their pixels stay even."""

from __future__ import annotations

import math

from realmwalker.ui.gfx.scene import Lines, Rect, Sprite

CARD_W, CARD_H = 24, 36
LAYOUT = {"shadow": (1, 0), "key": (0, 1), "turn": (1, 1), "hand": (2, 1), "door": (1, 2)}


def table(canvas, game, rect, rec: dict | None, now: float, chosen: str | None = None) -> dict:
    """Draw the cloth and the cards in rect (pixels). Returns {pos: (x, y, w, h)} of each card, and "villain"."""
    x, y, w, h = rect
    canvas.under(Rect(x, y, w, h, (10, 8, 14, 255), bottom=(34, 20, 14, 255)))
    ambient = canvas.gfx.ambient
    flick = 0.88 + 0.12 * math.sin(now * 9) * math.sin(now * 6.1 + 1) if ambient else 1.0
    # the fire, to the left, and its light across the cloth
    size = min(h * 0.28, 64)
    fx, fy = x + w * 0.1, y + h * 0.9
    g = size * 4 * flick
    canvas.under(Rect(fx - g / 2, fy - g * 0.6, g, g * 0.6, (0, 0, 0, 0), bottom=(120, 60, 20, int(90 * flick))))
    frame = int(now * 8) % 3 if ambient else 0
    canvas.under(Sprite(f"feature/campfire_{frame}", fx - size / 2, fy - size * 0.85, size, size))
    # the cloth
    scale = max(1, int(min((h * 0.92) / (CARD_H * 3 + 12), (w * 0.62) / (CARD_W * 3 + 12))))
    cw, ch = CARD_W * scale, CARD_H * scale
    gap = 4 * scale
    tw, th = cw * 3 + gap * 2, ch * 3 + gap * 2
    tx, ty = x + (w - tw) / 2 + w * 0.06, y + (h - th) / 2
    pad = 3 * scale
    canvas.under(Rect(tx - pad, ty - pad, tw + pad * 2, th + pad * 2, (92, 26, 24, 255), bottom=(64, 18, 18, 255)))
    canvas.under(Lines([(tx - pad, ty - pad), (tx + tw + pad, ty - pad), (tx + tw + pad, ty + th + pad),
                        (tx - pad, ty + th + pad), (tx - pad, ty - pad)], max(1, scale // 2), (176, 132, 60, 200)))
    out: dict = {}
    cards = (rec or {}).get("cards") or {}
    light = int(205 + 50 * flick)
    tint = (light, int(light * 0.94), int(light * 0.86), 255)
    for pos, (cx, cy) in LAYOUT.items():
        px, py = tx + cx * (cw + gap), ty + cy * (ch + gap)
        c = cards.get(pos)
        if c is None or c.get("silent"):
            canvas.under(Sprite("card/back", px, py, cw, ch, tint))
        else:
            canvas.under(Sprite(f"card/{c['card']}", px, py, cw, ch, tint))
            suit = (c.get("minor") or ["blades"])[0]
            mw, mh = cw * 0.55, ch * 0.55
            canvas.under(Sprite(f"card/suit_{suit}", px + cw - mw * 0.55, py + ch - mh * 0.75, mw, mh, tint,
                                angle=90.0))
        out[pos] = (px, py, cw, ch)
        if chosen == pos:
            m = max(2, scale)
            canvas.under(Lines([(px - m, py - m), (px + cw + m, py - m), (px + cw + m, py + ch + m),
                                (px - m, py + ch + m), (px - m, py - m)], max(2, scale), (240, 206, 110, 255)))
    vil = (rec or {}).get("villain")
    if vil:
        px, py = tx + 2 * (cw + gap), ty
        canvas.under(Sprite(f"card/{vil['card']}", px, py, cw, ch, (255, 150, 140, 255), angle=180.0))
        out["villain"] = (px, py, cw, ch)
        if chosen == "villain":
            m = max(2, scale)
            canvas.under(Lines([(px - m, py - m), (px + cw + m, py - m), (px + cw + m, py + ch + m),
                                (px - m, py + ch + m), (px - m, py - m)], max(2, scale), (220, 60, 50, 255)))
    return out
