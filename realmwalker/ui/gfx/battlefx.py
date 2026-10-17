"""The battle drawn as a battle mat: the field (cut from the place the fight is in, so it is drawn with the same tiles
as the close-up maps, in the same light), a faint grid of five-foot squares, everyone as a figure on their squares,
and what happens shown as it happens: people walking their paths, a lunge, an arrow in flight, a ray, a fireball's
bead and its burst over every square it fills, a cone of flame, a stroke of lightning, a thunderclap, webs, burning
grass, spirits wheeling about a priest, hits that flash and shake, the damage rising off the wounded, the fallen.

The rules (rules/combat.Battle) write a list of events; this reads the new ones each frame and turns them into
short effects on a timeline, so that a whole enemy turn plays out in order. Nothing here changes the fight. With
animations off, everything simply stands where it is.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.audio.cues import battle_sounds, timeline
from realmwalker.ui.gfx import dolls, theme
from realmwalker.ui.gfx.scene import Image, Lines, Rect, Sprite, Text, tile_batch

STEP = 0.11  # seconds to walk a square
PUSH_STEP = 0.06
LUNGE = 0.26
FLIGHT = 0.26
FLOAT = 1.1
# A steed of another world, in its kind's colours (Find Steed: celestial pale gold, fey green-silver, fiend ember).
STEED_TINT = {"celestial": (255, 238, 190, 255), "fey": (196, 255, 222, 255), "fiend": (225, 140, 120, 255)}
FALL = 0.4
STAGGER = 0.30
TILE_SIZES = (96, 64, 48, 32, 24, 16)  # whole and half multiples of the 32-pixel tiles, so they stay sharp
DAY = np.array([1.0, 1.0, 1.0], np.float32)
NIGHT = np.array([0.30, 0.32, 0.48], np.float32)
DARK = np.array([0.26, 0.25, 0.33], np.float32)  # unlit ground underground: dim, but the shape of the place still shows
TORCH = np.array([1.0, 0.80, 0.52], np.float32)
MAGIC_FX = {"fire": "fx/fire", "cold": "fx/cold", "poison": "fx/poison", "necrotic": "fx/drain", "radiant": "fx/glow",
            "force": "fx/magic", "lightning": "fx/sparkle", "thunder": "", "acid": "fx/poison", "psychic": "fx/drain"}
COLOURS = {"fire": (255, 140, 46), "cold": (150, 205, 255), "lightning": (210, 210, 255), "thunder": (230, 224, 200),
           "necrotic": (150, 80, 170), "radiant": (255, 232, 150), "force": (190, 150, 255), "poison": (130, 210, 90),
           "acid": (170, 225, 70), "psychic": (235, 130, 210), "": (200, 180, 255)}
SPELL_COLOURS = {"sleep": (190, 150, 255), "web": (220, 220, 210), "bless": (255, 220, 120), "healing_word": (140, 230, 120),
                 "cure_wounds": (140, 230, 120), "mass_healing_word": (140, 230, 120), "mass_cure_wounds": (140, 230, 120),
                 "spirit_guardians": (255, 220, 130), "guardian_of_faith": (255, 220, 130), "misty_step": (200, 220, 255)}
# A weapon mastery as it lands (rules/engine/handlers/mastery.py): its word and colour. Topple shows as the fall.
MASTERY_MARKS = {"push": ("driven back", (236, 214, 170)), "sap": ("sapped", (214, 190, 120)),
                 "slow": ("slowed", (150, 190, 230)), "vex": ("an opening", (240, 150, 120)),
                 "cleave": ("cleave", (255, 200, 120)), "graze": ("grazed", (230, 170, 150)), "topple": ("", (0, 0, 0)),
                 "reeling": ("reeling", (240, 170, 110)), "unsteady": ("unsteady", (214, 190, 120))}
CONDITION_WORDS = {"prone": "down", "restrained": "held fast", "paralyzed": "paralysed", "stunned": "stunned",
                   "asleep": "asleep", "poisoned": "poisoned", "grappled": "grappled", "frightened": "afraid",
                   "blinded": "blind"}
# The looks a spell can have (data/spells.json "fx"), and the look of a cast that names only what it does.
LOOKS = ("bolt", "ray", "darts", "touch", "cone", "burst", "shock", "line", "rain", "strike", "zone", "aura", "summon",
         "teleport", "heal", "buff", "curse", "sleep", "thrown")
LOOKS_BY_EFFECT = {"save": "burst", "breath": "cone", "heal": "heal", "buff": "buff", "sleep": "sleep",
                   "condition": "curse", "attack": "bolt", "darts": "darts", "zone": "zone", "aura": "aura",
                   "summon": "summon", "teleport": "teleport"}
SHAPE_LOOKS = {"line": "line", "cone": "cone", "cube": "shock", "sphere": "burst", "cylinder": "burst"}  # a breath, a blast
STATUS_ROW = 4  # status icons shown over a figure before "+N"
TAGS = {"paralyzed": "held", "stunned": "stunned", "restrained": "webbed", "grappled": "held", "unconscious": "asleep",
        "frightened": "afraid"}  # the one word under a figure (the full words float up when it happens)


def colour_for(dtype: str, spell: str = "") -> tuple[int, int, int]:
    return SPELL_COLOURS.get(spell) or COLOURS.get(dtype, COLOURS[""])


class BattleBoard:
    def __init__(self) -> None:
        self.seen = 0
        self.fx: list[dict] = []
        self.looks: dict[int, str] = {}  # caster -> the look of the spell just cast
        self.tracks: dict[int, list] = {}  # fighter -> [(start time, path, seconds a square)]
        self.tok_tracks: dict[int, list] = {}
        self.fell: dict[int, float] = {}
        self.lifts: dict[int, tuple[float, float, float, float]] = {}  # fighter -> (start, from z, to z, seconds)
        self.prev: dict[int, str] = {}
        self.busy_until = 0.0
        self.art = None
        self.art_key = None
        self.T = 32
        self.origin = (0.0, 0.0)
        self.rect = (0, 0, 0, 0)
        self.cells: dict[int, tuple[int, int, int, int]] = {}  # fighter -> cell rect (for clicks)
        self.figures: dict[int, list] = {}
        self._impact = 0.0
        self.shake_until = 0.0
        self.cam: tuple[float, float] | None = None
        self.cam_t = 0.0
        self.sounds: list[tuple[float, str]] = []  # (when, sound) for the screen to play, on the moments drawn

    # ------------------------------------------------------------------ the camera
    def layout(self, field, rect, zoom: int | None = None, focus: tuple[float, float] | None = None,
               now: float = 0.0) -> None:
        """Fit the field into the rectangle with square tiles of a whole size (or the size chosen by zooming), big
        enough that people can be told apart: a field too big for the room follows `focus` (the one whose turn it
        is), gliding there."""
        x, y, w, h = rect
        self.rect = rect
        T = zoom
        if T is None:
            T = next((t for t in TILE_SIZES if t * min(field.width, 22) <= w and t * min(field.height, 14) <= h),
                     TILE_SIZES[-1])
        self.T = T
        if focus is not None:
            dt = max(0.0, min(0.2, now - self.cam_t))
            self.cam_t = now
            if self.cam is None or abs(self.cam[0] - focus[0]) > 30 or dt <= 0:
                self.cam = focus
            else:
                k = min(1.0, dt * 6.0)
                self.cam = (self.cam[0] + (focus[0] - self.cam[0]) * k, self.cam[1] + (focus[1] - self.cam[1]) * k)
            focus = self.cam
        fw, fh = field.width * T, field.height * T
        if fw <= w:
            ox = x + (w - fw) / 2
        else:
            cx = (focus[0] if focus else field.width / 2) * T
            ox = x + w / 2 - cx
            ox = min(x, max(x + w - fw, ox))
        if fh <= h:
            oy = y + (h - fh) / 2
        else:
            cy = (focus[1] if focus else field.height / 2) * T
            oy = y + h / 2 - cy
            oy = min(y, max(y + h - fh, oy))
        self.origin = (round(ox), round(oy))

    def to_square(self, px: float, py: float, field) -> tuple[int, int] | None:
        x0, y0, w, h = self.rect
        if not (x0 <= px < x0 + w and y0 <= py < y0 + h):
            return None
        sx = int(math.floor((px - self.origin[0]) / self.T))
        sy = int(math.floor((py - self.origin[1]) / self.T))
        return (sx, sy) if field.in_bounds(sx, sy) else None

    def sq_px(self, x: float, y: float) -> tuple[float, float]:
        return self.origin[0] + x * self.T, self.origin[1] + y * self.T

    # ------------------------------------------------------------------ what happened
    def feed(self, battle, now: float, animate: bool) -> None:
        events = battle.events[self.seen:]
        self.seen = len(battle.events)
        if not events:
            self._states(battle, now, animate)
            return
        t = max(now, self.busy_until - 0.05)
        for ev in events if animate else []:
            t0 = t
            t = self._schedule(battle, ev, t)
            impact = self._impact if self._impact >= t0 - 0.6 else t0
            self.sounds += [(t0 if moment == "start" else max(t0, impact), sid) for moment, sid in battle_sounds(ev)]
        if not animate:
            self.sounds += timeline(events, now)
            for ev in events:
                if ev["kind"] in ("fly", "fall"):
                    self.lifts.pop(ev["who"], None)  # (drawn at its height as it is)
        end = max([e["t0"] + e["dur"] * (0.55 if e["kind"] == "float" else 1.0) for e in self.fx] + [t, now])
        for tracks in list(self.tracks.values()) + list(self.tok_tracks.values()):
            for t0, path, step in tracks:
                end = max(end, t0 + step * (len(path) - 1))
        self.busy_until = end
        self._states(battle, now, animate)
        self.fx = [e for e in self.fx if e["t0"] + e["dur"] > now - 0.05]

    def _states(self, battle, now: float, animate: bool) -> None:
        """Who went down, died or got away since last time (they fall when the blow lands)."""
        for f in battle.fighters:
            state = f.state
            old = self.prev.get(f.id)
            if old is not None and old != state and state in ("down", "dead"):
                self.fell[f.id] = max(now, self._impact) if animate else now - FALL
            if state in ("fighting", "fleeing") and f.id in self.fell:
                del self.fell[f.id]
            self.prev[f.id] = state

    def _schedule(self, battle, ev: dict, t: float) -> float:
        k = ev["kind"]
        if k in ("move", "push", "teleport"):
            path = [tuple(p) for p in ev["path"]]
            who = ev["who"]
            if k == "teleport":
                self.fx.append({"kind": "puff", "at": path[0], "t0": t, "dur": 0.4, "color": (200, 220, 255)})
                self.tracks.setdefault(who, []).append((t + 0.25, [path[-1], path[-1]], 0.01))
                self.fx.append({"kind": "puff", "at": path[-1], "t0": t + 0.25, "dur": 0.4, "color": (200, 220, 255)})
                return t + 0.45
            step = STEP if k == "move" else PUSH_STEP
            self.tracks.setdefault(who, []).append((t, path, step))
            return t + step * (len(path) - 1)
        if k in ("fly", "fall"):  # rising or coming down, or falling out of the sky
            who = ev["who"]
            start = self.height(battle.fighter(who), t) if who in self.lifts else float(ev.get("before", ev.get("feet", 0)))
            end = float(ev.get("z", 0)) if k == "fly" else 0.0
            dur = 0.3 if k == "fly" else 0.22
            self.lifts[who] = (t, start, end, dur)
            return t + dur
        if k == "leave":
            self.fx.append({"kind": "float", "who": ev["who"], "text": "gone", "color": (210, 200, 180), "t0": t,
                            "dur": FLOAT, "size": 16})
            return t + 0.2
        if k in ("shape", "unshape"):  # (Polymorph: drawn anew in its new body, or its own again)
            self.figures.pop(ev["who"], None)
            f = battle.fighter(ev["who"])
            if f is not None:
                self.fx.append({"kind": "puff", "at": (f.x, f.y), "t0": t, "dur": 0.4, "color": (190, 160, 240)})
            return t + 0.3
        if k == "burst":  # a spell bursting around a creature (Ice Knife, Hail of Thorns)
            col = COLOURS.get(ev.get("dtype", ""), (230, 230, 240))
            for c in ev.get("cells", ())[::2]:
                self.fx.append({"kind": "puff", "at": tuple(c), "t0": t, "dur": 0.35, "color": col})
            return t + 0.3
        if k == "image":  # Mirror Image: a duplicate takes the blow and is gone
            self.fx.append({"kind": "float", "who": ev["who"], "text": "an image", "color": (200, 210, 255), "t0": t,
                            "dur": FLOAT, "size": 14})
            return t + 0.15
        if k == "attack":
            a, b = ev["by"], ev["to"]
            if ev.get("melee"):
                self.fx.append({"kind": "lunge", "who": a, "at": b, "t0": t, "dur": LUNGE})
                impact = t + LUNGE * 0.5
            else:
                how = ev.get("how", "")
                if how.startswith("spell") and self.looks.get(a) == "ray":
                    self.fx.append({"kind": "beam", "from": a, "to": b, "t0": t, "dur": 0.32, "color": colour_for(ev.get("dtype", ""))})
                    impact = t + 0.12
                else:
                    self.fx.append({"kind": "shot", "from": a, "to": b, "t0": t, "dur": FLIGHT,
                                    "sprite": _missile(ev.get("weapon", ""), how, ev.get("dtype", ""))})
                    impact = t + FLIGHT
            if not ev.get("hit"):
                self.fx.append({"kind": "float", "who": b, "text": "miss", "color": (190, 186, 176), "t0": impact,
                                "dur": FLOAT, "size": 16})
                self.fx.append({"kind": "dodge", "who": b, "t0": impact, "dur": 0.25})
            self._impact = impact
            return t + STAGGER
        if k == "opportunity":
            self.fx.append({"kind": "float", "who": ev["by"], "text": "opportunity!", "color": (255, 210, 110), "t0": t,
                            "dur": FLOAT * 0.8, "size": 14})
            return t
        if k == "dart":
            self.fx.append({"kind": "shot", "from": ev["by"], "to": ev["to"], "t0": t, "dur": 0.3, "sprite": "fx/magic_dart",
                            "curve": 30})
            self._impact = t + 0.3
            return t + 0.12
        if k == "damage":
            at = self._impact if self._impact >= t - 0.6 else t
            crit = ev.get("crit")
            try:
                hurt_party = battle.fighter(ev["to"]).side == "party"
            except StopIteration:
                hurt_party = False
            color = (255, 220, 120) if crit else ((255, 120, 96) if hurt_party else (255, 236, 220))
            self.fx.append({"kind": "hit", "who": ev["to"], "t0": at, "dur": 0.28, "crit": crit})
            self.fx.append({"kind": "float", "who": ev["to"], "text": ("crit! " if crit else "") + str(ev["amount"]),
                            "color": color, "t0": at, "dur": FLOAT, "size": 24 if crit else 20})
            spark = MAGIC_FX.get(ev.get("dtype", ""))
            if spark:
                self.fx.append({"kind": "burst", "who": ev["to"], "sprite": spark, "t0": at, "dur": 0.45})
            elif ev.get("dtype") in ("slashing", "piercing"):
                self.fx.append({"kind": "burst", "who": ev["to"], "sprite": "fx/blood", "t0": at, "dur": 0.4, "small": True})
            if crit:
                self.shake_until = max(self.shake_until, at + 0.25)
            return t
        if k == "immune":
            self.fx.append({"kind": "float", "who": ev["to"], "text": "unharmed", "color": (170, 170, 190),
                            "t0": max(t, self._impact), "dur": FLOAT, "size": 16})
            return t
        if k == "heal":
            self.fx.append({"kind": "burst", "who": ev["to"], "sprite": "fx/sparkle", "t0": t, "dur": 0.6})
            self.fx.append({"kind": "float", "who": ev["to"], "text": f"+{ev['amount']}", "color": (140, 230, 120),
                            "t0": t, "dur": FLOAT, "size": 20})
            return t + 0.1
        if k == "save":
            if ev.get("ok"):
                self.fx.append({"kind": "float", "who": ev["who"], "text": "saved", "color": (200, 200, 210),
                                "t0": max(t, self._impact) + 0.05, "dur": FLOAT * 0.8, "size": 13, "low": True})
            return t
        if k == "cast":
            return self._cast(battle, ev, t)
        if k == "buff":
            self.fx.append({"kind": "ring", "who": ev["who"], "t0": t, "dur": 0.7, "color": colour_for("", ev.get("spell", "")) if
                            ev.get("spell") in SPELL_COLOURS else (255, 220, 130)})
            return t
        if k in ("condition", "prone", "yield", "hide", "stand"):
            word = {"prone": "knocked down", "yield": "yields", "hide": "hidden", "stand": ""}.get(k) or \
                CONDITION_WORDS.get(ev.get("cond", ""), ev.get("cond", ""))
            if word:
                self.fx.append({"kind": "float", "who": ev["who"], "text": word, "color": (230, 200, 150),
                                "t0": max(t, self._impact) + 0.1, "dur": FLOAT, "size": 15, "low": True})
            return t
        if k == "mastery":  # a weapon's trick: a word and a mark over the one it caught
            word, color = MASTERY_MARKS.get(ev.get("trick", ""), ("", (230, 200, 150)))
            at = max(t, self._impact) + 0.12
            if word:
                self.fx.append({"kind": "float", "who": ev["who"], "text": word, "color": color, "t0": at, "dur": FLOAT,
                                "size": 15, "low": True})
            if ev.get("trick") in ("sap", "slow", "vex"):
                self.fx.append({"kind": "ring", "who": ev["who"], "t0": at, "dur": 0.5, "color": color})
            if ev.get("trick") == "push":
                self.shake_until = max(self.shake_until, at + 0.12)
            return t
        if k == "portent":  # (a diviner's foretold die over the one whose roll it takes: a gold die face)
            at = max(t, self._impact) + 0.05
            to = ev.get("to", ev["who"])
            self.fx.append({"kind": "float", "who": to, "text": f"foretold {ev.get('value', '')}",
                            "color": (240, 214, 130), "t0": at, "dur": FLOAT, "size": 15, "low": False})
            self.fx.append({"kind": "ring", "who": ev["who"], "t0": at, "dur": 0.5, "color": (240, 214, 130)})
            return t
        if k == "flare":  # (Warding Flare: light flares from the cleric into the attacker's eyes)
            at = max(t, self._impact)
            self.fx.append({"kind": "ring", "who": ev["by"], "t0": at, "dur": 0.4, "color": (255, 236, 160)})
            self.fx.append({"kind": "burst", "who": ev["at"], "sprite": "fx/sparkle", "t0": at + 0.05, "dur": 0.45})
            self.fx.append({"kind": "float", "who": ev["at"], "text": "dazzled", "color": (255, 236, 160),
                            "t0": at + 0.05, "dur": FLOAT * 0.8, "size": 14, "low": False})
            return t + 0.15
        if k == "miracle":  # (a god answers the dying: a column of the god's light and a word over them)
            at = max(t, self._impact) + 0.1
            color = {"life": (190, 240, 170), "light": (255, 240, 170), "trickery": (200, 180, 255),
                     "war": (255, 170, 120)}.get(ev.get("domain", ""), (255, 240, 170))
            self.fx.append({"kind": "ring", "who": ev["who"], "t0": at, "dur": 1.0, "color": color})
            self.fx.append({"kind": "burst", "who": ev["who"], "sprite": "fx/sparkle", "t0": at, "dur": 0.9})
            self.fx.append({"kind": "float", "who": ev["who"], "text": "the god answers", "color": color,
                            "t0": at + 0.1, "dur": FLOAT * 1.4, "size": 18, "low": False})
            return t + 0.6
        if k == "double_cast":  # (Invoke Duplicity: the spell leaves from the double's square)
            self.fx.append({"kind": "tok_glow", "id": ev["id"], "t0": t, "dur": 0.5})
            return t + 0.1
        if k == "illusion" and ev.get("what") == "double":  # (Illusory Self: the struck figure bursts into mist)
            at = max(t, self._impact)
            self.fx.append({"kind": "ring", "who": ev["who"], "t0": at, "dur": 0.45, "color": (190, 170, 255)})
            self.fx.append({"kind": "float", "who": ev["who"], "text": "a double", "color": (190, 170, 255),
                            "t0": at + 0.05, "dur": FLOAT, "size": 14, "low": False})
            return t
        if k == "illusion_seen":  # (seen through: a pale flicker over the one who saw)
            self.fx.append({"kind": "float", "who": ev["who"], "text": "an illusion!", "color": (190, 170, 255),
                            "t0": t, "dur": FLOAT, "size": 14, "low": True})
            return t
        if k == "maneuver":  # a Battle Master's maneuver: its name over the fighter, a steel-blue ring
            at = max(t, self._impact) + 0.05
            self.fx.append({"kind": "float", "who": ev["who"], "text": str(ev.get("what", "")).lower(),
                            "color": (170, 200, 236), "t0": at, "dur": FLOAT, "size": 14, "low": False})
            self.fx.append({"kind": "ring", "who": ev["who"], "t0": at, "dur": 0.45, "color": (170, 200, 236)})
            return t
        if k == "disarm":
            self.fx.append({"kind": "float", "who": ev["who"], "text": "disarmed", "color": (236, 214, 170),
                            "t0": max(t, self._impact) + 0.12, "dur": FLOAT, "size": 15, "low": True})
            return t
        if k == "poison":  # (the poison on the blade goes into the wound: rules/poisons.on_hit)
            self.fx.append({"kind": "float", "who": ev["who"], "text": "envenomed", "color": (150, 214, 110),
                            "t0": max(t, self._impact) + 0.1, "dur": FLOAT, "size": 14, "low": True})
            return t
        if k == "rearm":  # (War Bond: a bonded weapon flies back to the hand)
            self.fx.append({"kind": "float", "who": ev["who"], "text": "to hand", "color": (170, 200, 236),
                            "t0": max(t, self._impact) + 0.05, "dur": FLOAT, "size": 14, "low": False})
            self.fx.append({"kind": "ring", "who": ev["who"], "t0": t, "dur": 0.35, "color": (170, 200, 236)})
            return t
        if k == "arms_form":  # (the Rod of Lordly Might's buttons, the Veteran's Cane's twist: what it is now)
            self.fx.append({"kind": "float", "who": ev["who"], "text": str(ev.get("what", "")), "color": (236, 200, 120),
                            "t0": max(t, self._impact) + 0.05, "dur": FLOAT, "size": 14, "low": False})
            return t
        if k == "behead":  # (a Vorpal Sword's stroke)
            self.fx.append({"kind": "float", "who": ev["who"], "text": "beheaded", "color": (236, 90, 80),
                            "t0": max(t, self._impact) + 0.15, "dur": FLOAT, "size": 16, "low": False})
            self.shake_until = max(self.shake_until, max(t, self._impact) + 0.2)
            return t
        if k == "concentration_end":
            self.fx.append({"kind": "float", "who": ev["who"], "text": "concentration broken", "color": (200, 170, 255),
                            "t0": max(t, self._impact) + 0.15, "dur": FLOAT, "size": 13, "low": True})
            return t
        if k == "token_move":
            self.tok_tracks.setdefault(ev["id"], []).append((t, [tuple(p) for p in ev["path"]], 0.08))
            return t + 0.08
        if k == "token_strike":
            self.fx.append({"kind": "tok_lunge", "id": ev["id"], "at": ev["to"], "t0": t, "dur": LUNGE})
            return t
        if k == "zone":
            self.fx.append({"kind": "zone_in", "cells": [tuple(c) for c in ev.get("cells", [])], "t0": t, "dur": 0.5,
                            "zone": ev.get("zone", "")})
            return t
        return t

    def _cast(self, battle, ev: dict, t: float) -> float:
        """A spell drawn by its look (data/spells.json "fx": the event's `look`), coloured by its damage type."""
        spell = ev.get("spell", "")
        dtype = ev.get("dtype", "")
        look = ev.get("look") or SHAPE_LOOKS.get(ev.get("shape", "")) or LOOKS_BY_EFFECT.get(ev.get("effect", ""), "")
        color = colour_for(dtype, spell)
        if look in ("curse",):
            color = (150, 90, 200) if not dtype else color
        self.fx.append({"kind": "glow", "who": ev["by"], "t0": t, "dur": 0.5, "color": color})
        self.looks[ev["by"]] = look  # the spell attack that follows is drawn as this look (a ray is a beam)
        area = [tuple(c) for c in ev.get("area") or []]
        point = tuple(ev["point"]) if ev.get("point") else None
        start = t + 0.25
        try:
            caster = battle.fighter(ev["by"])
            ox, oy = caster.x + caster.sq / 2, caster.y + caster.sq / 2
        except StopIteration:
            ox, oy = (area[0][0] + 0.5, area[0][1] + 0.5) if area else (0.0, 0.0)
        target = ev.get("to")
        if not area:
            if look == "curse" and target is not None:
                self.fx.append({"kind": "ring", "who": target, "t0": start, "dur": 0.7, "color": color})
            elif look == "touch" and target is not None:
                self.fx.append({"kind": "burst", "who": target, "sprite": MAGIC_FX.get(dtype, "fx/magic"), "t0": start,
                                "dur": 0.4})
            elif look == "strike" and target is not None:
                try:
                    f = battle.fighter(target)
                    self.fx.append({"kind": "column", "at": (f.x + f.sq / 2, f.y + f.sq / 2), "t0": start, "dur": 0.5,
                                    "color": color})
                except StopIteration:
                    pass
                self._impact = start + 0.2
                return start + 0.3
            elif look in ("summon",) and point is not None:
                self.fx.append({"kind": "puff", "at": point, "t0": start, "dur": 0.5, "color": color})
            elif look == "aura":
                self.fx.append({"kind": "ring", "who": ev["by"], "t0": start, "dur": 0.9, "color": color, "wide": True})
            return t + 0.2
        cx, cy = ox, oy  # where the spell spreads from: the caster (cone, line, aura) or the point (burst, rain)
        if look in ("burst", "thrown", "sleep", "rain", "strike", "zone", "heal") and point is not None:
            cx, cy = point[0] + 0.5, point[1] + 0.5
        if look in ("burst", "thrown") and point is not None:  # a bead (or a flask) flies to the spot, and bursts
            self.fx.append({"kind": "bead", "from": (ox, oy), "to": (cx, cy), "t0": start, "dur": 0.32, "color": color,
                            "sprite": MAGIC_FX.get(dtype, "fx/magic")})
            start += 0.32
        radius = max((max(abs(c[0] + 0.5 - cx), abs(c[1] + 0.5 - cy)) for c in area), default=1.5) + 0.5
        if look == "line" and point is not None:
            far = max(area, key=lambda c: (c[0] + 0.5 - ox) ** 2 + (c[1] + 0.5 - oy) ** 2)
            self.fx.append({"kind": "bolt", "from": (ox, oy), "to": (far[0] + 0.5, far[1] + 0.5), "t0": start, "dur": 0.45,
                            "color": color, "seed": len(self.fx)})
        elif look in ("burst", "thrown"):
            self.fx.append({"kind": "flash", "at": (cx, cy), "t0": start, "dur": 0.55, "color": color, "radius": radius})
            self.shake_until = max(self.shake_until, start + 0.3)
        elif look == "shock":
            self.fx.append({"kind": "shock", "at": (cx, cy), "t0": start, "dur": 0.45, "color": color,
                            "radius": max(1.5, math.sqrt(len(area)) * 0.8)})
        elif look == "strike":
            self.fx.append({"kind": "column", "at": (cx, cy), "t0": start, "dur": 0.55, "color": color,
                            "radius": radius})
        elif look == "aura":
            self.fx.append({"kind": "shock", "at": (cx, cy), "t0": start, "dur": 0.8, "color": color, "radius": radius})
        sprite = "fx/sparkle" if look in ("sleep", "heal", "buff", "aura") else MAGIC_FX.get(dtype, "fx/magic")
        if look in ("line", "shock") or spell == "web":
            sprite = ""  # the bolt or the shockwave is the picture; the squares only flash
        delay = 0.035 if look != "rain" else 0.0
        for i, c in enumerate(area):
            d = math.hypot(c[0] + 0.5 - cx, c[1] + 0.5 - cy)
            wait = d * delay if look != "rain" else ((c[0] * 7 + c[1] * 13 + i) % 9) * 0.05  # rain falls unevenly
            self.fx.append({"kind": "cell", "at": c, "t0": start + wait, "dur": 0.5, "sprite": sprite, "color": color})
        reach = max((math.hypot(c[0] + 0.5 - cx, c[1] + 0.5 - cy) for c in area), default=0)
        self._impact = start + (reach * delay if look != "rain" else 0.4) + 0.1
        return self._impact + 0.15

    def busy(self, now: float) -> bool:
        return now < self.busy_until

    # ------------------------------------------------------------------ where everyone is drawn
    def pos(self, f, now: float) -> tuple[float, float]:
        """Where a fighter is drawn now (in squares): along the path they are walking, else where they stand."""
        tracks = self.tracks.get(f.id)
        if tracks:
            keep = []
            out = None
            for t0, path, step in tracks:
                t1 = t0 + step * (len(path) - 1)
                if now >= t1:
                    continue
                keep.append((t0, path, step))
                if out is None:
                    if now < t0:
                        out = path[0]
                    else:
                        k = (now - t0) / step
                        i = min(len(path) - 2, int(k))
                        p = k - i
                        a, b = path[i], path[i + 1]
                        out = (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)
            self.tracks[f.id] = keep
            if out is not None:
                return float(out[0]), float(out[1])
        return float(f.x), float(f.y)

    def tok_pos(self, tok, now: float) -> tuple[float, float]:
        tracks = self.tok_tracks.get(tok.id)
        if tracks:
            for t0, path, step in tracks:
                t1 = t0 + step * (len(path) - 1)
                if now < t1:
                    if now < t0:
                        return path[0]
                    p = (now - t0) / max(1e-6, t1 - t0)
                    return (path[0][0] + (path[-1][0] - path[0][0]) * p, path[0][1] + (path[-1][1] - path[0][1]) * p)
            self.tok_tracks[tok.id] = []
        return float(tok.x), float(tok.y)

    def height(self, f, now: float) -> float:
        """A fighter's height above the ground in feet as drawn now (rising and falling are animated)."""
        lift = self.lifts.get(f.id)
        if lift is None:
            return float(f.z)
        t0, a, b, dur = lift
        if now <= t0:
            return a
        return b if now >= t0 + dur else a + (b - a) * (now - t0) / dur

    def lift_px(self, f, now: float) -> float:
        """How far above its shadow a flier is drawn: a little for every five feet, so that height reads at a glance
        without hiding the squares above it."""
        return min(self.height(f, now), 60.0) / 5.0 * self.T * 0.13

    def place(self, f, now: float) -> tuple[float, float, float]:
        """Pixel centre-bottom (feet) and size of a fighter now, moved by any lunge, shake or dodge."""
        x, y = self.pos(f, now)
        T = self.T
        size = T * f.sq
        px, py = self.sq_px(x, y)
        cx, fy = px + size / 2, py + size
        for e in self.fx:
            if now < e["t0"] or now > e["t0"] + e["dur"]:
                continue
            p = (now - e["t0"]) / e["dur"]
            if e["kind"] == "lunge" and e["who"] == f.id:
                tx, ty = self._target_px(e["at"], now)
                if tx is not None:
                    k = math.sin(math.pi * p) * 0.38
                    cx += (tx - cx) * k
                    fy += (ty - fy) * k
            elif e["kind"] == "hit" and e["who"] == f.id:
                amp = (6 if e.get("crit") else 3.5) * (1 - p)
                cx += math.sin(p * 40) * amp
            elif e["kind"] == "dodge" and e["who"] == f.id:
                cx += math.sin(math.pi * p) * T * 0.15
        return cx, fy, size

    def _target_px(self, fid, now):
        f = self._fighters.get(fid) if hasattr(self, "_fighters") else None
        if f is None:
            return None, None
        x, y = self.pos(f, now)
        px, py = self.sq_px(x, y)
        s = self.T * f.sq
        return px + s / 2, py + s

    # ------------------------------------------------------------------ drawing
    def draw(self, canvas, game, battle, rect, now: float, *, overlay: dict | None = None, zoom: int | None = None) -> None:
        overlay = overlay or {}
        gfx = canvas.gfx
        atlas = gfx.atlas
        fld = battle.field
        self._fighters = {f.id: f for f in battle.fighters}
        cur = battle.current if (battle.order and battle.outcome is None) else None
        focus = None
        if cur is not None:
            fx_, fy_ = self.pos(cur, now)
            focus = (fx_ + cur.sq / 2, fy_ + cur.sq / 2)
        self.layout(fld, rect, zoom, focus, now)
        if now < self.shake_until and gfx.animate:
            a = (self.shake_until - now) * 10
            self.origin = (self.origin[0] + math.sin(now * 61) * a, self.origin[1] + math.cos(now * 53) * a)
        x, y, w, h = rect
        canvas.under(*theme.panel(x, y, w, h, "inset"))
        T = self.T
        fx, fy = self.origin
        canvas.under(Rect(fx - 6, fy - 6, fld.width * T + 12, fld.height * T + 12, (6, 5, 7, 255)))
        canvas.under(Rect(fx - 4, fy - 4, fld.width * T + 8, fld.height * T + 8, (*theme.BRONZE, 255), line=2))
        self._ground(canvas, game, battle, now)
        self._zones(canvas, battle, now)
        self._grid(canvas, fld)
        self._overlay_under(canvas, battle, overlay, now)
        self._tokens(canvas, battle, now)
        self._people(canvas, game, battle, now, overlay, cur)
        self._overlay_over(canvas, battle, overlay, now)
        self._effects(canvas, now)

    def _ground(self, canvas, game, battle, now: float) -> None:
        from realmwalker.ui.gfx.localview import LocalArt, _batches, _corners
        from realmwalker.world.local import LocalMap

        fld = battle.field
        key = (fld.key, fld.version)
        if self.art_key != key:
            lm = LocalMap(key=f"{fld.key}", kind=fld.kind, width=fld.width, height=fld.height,
                          terrain_ids=list(game.tables.terrain.ids), terrain=fld.terrain.copy(),
                          variant=np.zeros((fld.width, fld.height), np.uint8), meta={"style": fld.style})
            getattr(game, "_remaps", {}).pop(lm.key, None)
            self.art = LocalArt(game, lm, canvas.gfx.atlas)
            self.art_key = key
        art = self.art
        T = self.T
        W, H = fld.width, fld.height
        L = battle.light()
        base = float(np.clip(fld.base_light, 0, 1))
        if fld.underground:
            B = DARK
        elif base >= 0.95:
            B = DAY
        else:
            B = NIGHT + (DAY - NIGHT) * base
        extra = np.clip(L - base, 0, 1)[..., None]
        light = np.clip(B[None, None, :] + extra * TORCH[None, None, :] * 1.05, 0, 1.0).astype(np.float32)
        self.light = light
        corners = _corners(light, art.WALL >= 0)
        ox, oy = self.origin
        gx = (ox + np.arange(W) * T)[:, None].repeat(H, 1).astype(np.float32)
        gy = (oy + np.arange(H) * T)[None, :].repeat(W, 0).astype(np.float32)
        hsh = art.hash
        ambient = canvas.gfx.ambient
        frame = int(now * 5) if ambient else 0
        quads = []
        everywhere = np.ones((W, H), bool)

        def layer(F, anim=None):
            m = everywhere & (F >= 0)
            if not m.any():
                return
            f = F[m]
            count = art.fam_count[f]
            pick = np.where(anim[m] > 1, (hsh[m] + frame) % count, hsh[m] % count) if anim is not None else hsh[m] % count
            rows = art.fam_rects[art.fam_start[f] + pick]
            dst = np.stack([gx[m], gy[m], np.full(len(f), T, np.float32), np.full(len(f), T, np.float32)], axis=1)
            col = corners[:-1, :-1][m], corners[1:, :-1][m], corners[1:, 1:][m], corners[:-1, 1:][m]
            rgba = np.ones((len(f), 4, 4), np.float32)
            rgba[:, 0, :3], rgba[:, 1, :3], rgba[:, 2, :3], rgba[:, 3, :3] = col
            quads.append((dst, rows, rgba))

        layer(art.G)
        layer(art.WALL)
        layer(art.V)
        layer(art.O, art.ANIM)
        canvas.under(*_batches(quads))

    def _grid(self, canvas, fld) -> None:
        """Faint lines between the squares, so distances can be counted."""
        T = self.T
        if T < 20:
            return
        ox, oy = self.origin
        W, H = fld.width, fld.height
        col = (0, 0, 0, 46)
        cmds = []
        for i in range(1, W):
            cmds.append(Lines([(ox + i * T, oy), (ox + i * T, oy + H * T)], 1, col))
        for j in range(1, H):
            cmds.append(Lines([(ox, oy + j * T), (ox + W * T, oy + j * T)], 1, col))
        canvas.under(*cmds)

    def _zones(self, canvas, battle, now: float) -> None:
        T = self.T
        atlas = canvas.gfx.atlas
        ambient = canvas.gfx.ambient
        for z in battle.zones:
            if z.kind == "web":
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Image("bweb", _web_image, (px, py, T, T), rgba=(235, 235, 225, 210), smooth=False))
            elif z.kind in ("plants", "grease", "spikes", "daggers", "overgrowth"):
                make = {"plants": _vines_image, "overgrowth": _vines_image, "grease": _grease_image, "spikes": _thorns_image,
                        "daggers": _blades_image}[z.kind]
                for i, (x, y) in enumerate(sorted(z.cells)):
                    px, py = self.sq_px(x, y)
                    wob = (int(now * 10) + i) % 2 if ambient and z.kind == "daggers" else 0
                    canvas.under(Image(f"b{z.kind}{wob}", (lambda m=make, w=wob: m(w)), (px, py, T, T),
                                       rgba=(255, 255, 255, 230), smooth=False))
            elif z.kind == "lights":  # (Dancing Lights: four bobbing torch-sized glows over a patch of the field)
                xs = sorted({c[0] for c in z.cells})
                ys = sorted({c[1] for c in z.cells})
                cx, cy = (xs[len(xs) // 2], ys[len(ys) // 2]) if xs else (0, 0)
                for i, (dx, dy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
                    bob = int(2 * math.sin(now * 3.0 + i * 1.7)) if ambient else 0
                    px, py = self.sq_px(cx + dx, cy + dy)
                    canvas.over(Rect(px + T // 2 - 3, py + T // 2 - 3 + bob, 6, 6, (255, 236, 170, 200)))
                    canvas.over(Rect(px + T // 2 - 1, py + T // 2 - 1 + bob, 2, 2, (255, 255, 235, 255)))
            elif z.kind in ("moonbeam", "silence"):
                pulse = 0.5 + 0.5 * math.sin(now * 2.2) if ambient else 0.6
                col = (225, 235, 255) if z.kind == "moonbeam" else (150, 170, 210)
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Rect(px, py, T, T, (*col, int((60 if z.kind == "moonbeam" else 30) + 30 * pulse))))
                xs = [c[0] for c in z.cells]
                ys = [c[1] for c in z.cells]
                if xs:
                    bx, by = self.sq_px(min(xs), min(ys))
                    canvas.under(theme.lines_box(bx, by, (max(xs) - min(xs) + 1) * T, (max(ys) - min(ys) + 1) * T,
                                                 (*col, int(110 + 70 * pulse))))
            elif z.kind in ("fire", "sphere"):
                frames = atlas.family("fx/fire") or atlas.family("fx/flame")
                for i, (x, y) in enumerate(sorted(z.cells)):
                    px, py = self.sq_px(x, y)
                    canvas.under(Rect(px, py, T, T, (255, 110, 30, 50)))
                    if frames:
                        name = frames[(int(now * 8) + i) % len(frames)] if ambient else frames[i % len(frames)]
                        canvas.under(Sprite(name, px, py, T, T, (255, 255, 255, 220)))
            elif z.kind in ("fog", "darkness"):
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Image("bfog", _fog_image, (px - T * 0.25, py - T * 0.25, T * 1.5, T * 1.5),
                                       rgba=(180, 184, 190, 170) if z.kind == "fog" else (10, 8, 14, 230)))
            elif z.kind == "illusion" and not z.real:  # (an image: Expansion 5 Part A)
                self._image(canvas, battle, z, now)
            elif z.kind in GROUND_LOOKS:  # the second wave's ground (Expansion 3 D.2)
                self._spell_ground(canvas, z, now)
            elif z.kind == "ice":
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Image("bice", _ice_image, (px, py, T, T), rgba=(220, 240, 255, 200), smooth=False))
            elif z.kind in ("caltrops", "bearings"):
                make = _caltrops_image if z.kind == "caltrops" else _bearings_image
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Image(f"b{z.kind}", make, (px, py, T, T), rgba=(255, 255, 255, 230), smooth=False))
            elif z.kind in ("guardians", "guardian"):
                pulse = 0.5 + 0.5 * math.sin(now * 3) if ambient else 0.6
                for (x, y) in z.cells:
                    px, py = self.sq_px(x, y)
                    canvas.under(Rect(px, py, T, T, (255, 220, 120, int(26 + 22 * pulse))))
                xs = [c[0] for c in z.cells]
                ys = [c[1] for c in z.cells]
                if xs:
                    bx, by = self.sq_px(min(xs), min(ys))
                    canvas.under(theme.lines_box(bx, by, (max(xs) - min(xs) + 1) * T, (max(ys) - min(ys) + 1) * T,
                                                 (255, 220, 130, int(90 + 80 * pulse))))
                if z.kind == "guardians" and ambient:
                    owner = self._fighters.get(z.owner)
                    if owner is not None:
                        ox_, oy_ = self.pos(owner, now)
                        ccx, ccy = self.sq_px(ox_ + owner.sq / 2, oy_ + owner.sq / 2)
                        for k in range(6):
                            ang = now * 1.6 + k * math.pi / 3
                            r = T * (z.radius + 0.3) * (0.55 + 0.25 * math.sin(now * 2 + k))
                            sx, sy = ccx + math.cos(ang) * r, ccy + math.sin(ang) * r * 0.8
                            canvas.under(Image("bspirit", _glow_image, (sx - T * 0.3, sy - T * 0.3, T * 0.6, T * 0.6),
                                               rgba=(255, 236, 170, 200)))

    IMAGE_LOOKS = ("feature/crates_0", "feature/boulder", "feature/barrels_0", "feature/crates_1", "feature/barrels_1")

    def _image(self, canvas, battle, z, now: float) -> None:
        """An illusion: the thing it shows (crates, a boulder, barrels). The player's side knows it for what it is, so
        it shimmers, half there; a foe's image the party has not seen through looks as solid as the real thing."""
        T = self.T
        atlas = canvas.gfx.atlas
        known = any(battle.knows_illusion(f, z) for f in battle.side("party"))
        pulse = 0.5 + 0.5 * math.sin(now * 3.1 + z.id) if canvas.gfx.ambient else 0.6
        alpha = int(120 + 50 * pulse) if known else 255
        for i, (x, y) in enumerate(sorted(z.cells)):
            px, py = self.sq_px(x, y)
            name = self.IMAGE_LOOKS[(z.id + i) % len(self.IMAGE_LOOKS)]
            if atlas.has(name):
                canvas.under(Sprite(name, px, py, T, T, (255, 255, 255, alpha)))
            if known:
                canvas.under(Rect(px, py, T, T, (170, 150, 255, int(22 + 26 * pulse))))
        if known:
            xs = [c[0] for c in z.cells]
            ys = [c[1] for c in z.cells]
            if xs:
                bx, by = self.sq_px(min(xs), min(ys))
                canvas.under(theme.lines_box(bx, by, (max(xs) - min(xs) + 1) * T, (max(ys) - min(ys) + 1) * T,
                                             (190, 170, 255, int(90 + 80 * pulse))))

    def _spell_ground(self, canvas, z, now: float) -> None:
        """Tentacles, poison clouds, swarms, sleet, storms of light, conjured spirits, walls of wind and force."""
        T = self.T
        ambient = canvas.gfx.ambient
        look = GROUND_LOOKS[z.kind]
        col = look["colour"]
        pulse = 0.5 + 0.5 * math.sin(now * 2.4) if ambient else 0.6
        make = look.get("image")
        for i, (x, y) in enumerate(sorted(z.cells)):
            px, py = self.sq_px(x, y)
            if look.get("fog"):
                canvas.under(Image("bfog", _fog_image, (px - T * 0.25, py - T * 0.25, T * 1.5, T * 1.5),
                                   rgba=(*col, look.get("alpha", 180))))
            else:
                canvas.under(Rect(px, py, T, T, (*col, int(look.get("alpha", 50) + 30 * pulse))))
            if make is not None:
                frame = (int(now * 6) + i) % 2 if ambient and look.get("frames") else 0
                canvas.under(Image(f"b{z.kind}{frame}", (lambda m=make, fr=frame: m(fr)), (px, py, T, T),
                                   rgba=(255, 255, 255, 230), smooth=False))
        if look.get("edge"):
            xs = [c[0] for c in z.cells]
            ys = [c[1] for c in z.cells]
            if xs:
                bx, by = self.sq_px(min(xs), min(ys))
                canvas.under(theme.lines_box(bx, by, (max(xs) - min(xs) + 1) * T, (max(ys) - min(ys) + 1) * T,
                                             (*col, int(110 + 70 * pulse))))

    def _overlay_under(self, canvas, battle, ov: dict, now: float) -> None:
        T = self.T
        for (x, y) in ov.get("exits", ()):
            px, py = self.sq_px(x, y)
            canvas.under(Rect(px + 2, py + 2, T - 4, T - 4, (240, 220, 140, 60)))
        reach = ov.get("reach") or set()
        if reach:
            # Where they can walk this turn: a faint wash, and a clear line round its edge.
            for (x, y) in reach:
                px, py = self.sq_px(x, y)
                canvas.under(Rect(px, py, T, T, (150, 200, 255, 22)))
            edge = []
            for (x, y) in reach:
                px, py = self.sq_px(x, y)
                if (x - 1, y) not in reach:
                    edge.append(Lines([(px, py), (px, py + T)], 2, (170, 210, 255, 170)))
                if (x + 1, y) not in reach:
                    edge.append(Lines([(px + T, py), (px + T, py + T)], 2, (170, 210, 255, 170)))
                if (x, y - 1) not in reach:
                    edge.append(Lines([(px, py), (px + T, py)], 2, (170, 210, 255, 170)))
                if (x, y + 1) not in reach:
                    edge.append(Lines([(px, py + T), (px + T, py + T)], 2, (170, 210, 255, 170)))
            canvas.under(*edge)
        for (x, y) in ov.get("dash", ()):
            px, py = self.sq_px(x, y)
            canvas.under(Rect(px, py, T, T, (255, 220, 110, 30)))
        for (x, y) in ov.get("threat", ()):
            px, py = self.sq_px(x, y)
            canvas.under(Rect(px, py, T, T, (255, 70, 50, 46)))
        for (x, y) in ov.get("flank", ()):
            # Where you could stand to flank the enemy pointed at: a gold diamond in the square.
            cx, cy = self.sq_px(x + 0.5, y + 0.5)
            r = T * 0.3
            canvas.under(Lines([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy), (cx, cy - r)], max(2, T // 16),
                               (255, 214, 110, 220)))
        area = ov.get("area")
        if area:
            r, g, b = ov.get("area_color", (255, 160, 60))
            pulse = 0.5 + 0.5 * math.sin(now * 5) if canvas.gfx.ambient else 0.6
            for (x, y) in area:
                px, py = self.sq_px(x, y)
                canvas.under(Rect(px, py, T, T, (r, g, b, int(70 + 50 * pulse))))
                canvas.under(Rect(px, py, T, T, (r, g, b, 150), line=1))
        cur = ov.get("current")
        if cur is not None:
            f = self._fighters.get(cur)
            if f is not None:
                x, y = self.pos(f, now)
                px, py = self.sq_px(x, y)
                s = T * f.sq
                pulse = 0.5 + 0.5 * math.sin(now * 4) if canvas.gfx.ambient else 1.0
                canvas.under(Image("bring", _ring_image, (px - s * 0.06, py + s * 0.55, s * 1.12, s * 0.5),
                                   rgba=(255, 214, 110, int(150 + 90 * pulse))))
        for fid in ov.get("targets", ()):
            f = self._fighters.get(fid)
            if f is None:
                continue
            px, py = self.sq_px(*self.pos(f, now))
            s = T * f.sq
            col = (255, 90, 60, 230) if fid == ov.get("target") else (230, 130, 90, 140)
            canvas.under(Image("bring", _ring_image, (px - s * 0.06, py + s * 0.55, s * 1.12, s * 0.5), rgba=col))

    def _overlay_over(self, canvas, battle, ov: dict, now: float) -> None:
        T = self.T
        path = ov.get("path")
        if path:
            pts = [self.sq_px(x + 0.5, y + 0.5) for x, y in path]
            warn = ov.get("warn", set())
            canvas.over(Lines(pts, max(2, T // 12), (255, 236, 170, 200), dash=(T * 0.18, T * 0.12)))
            for i, (x, y) in enumerate(path[1:], 1):
                cx, cy = self.sq_px(x + 0.5, y + 0.5)
                r = T * 0.1
                col = (255, 90, 60, 240) if (x, y) in warn else (255, 236, 170, 220)
                canvas.over(Rect(cx - r, cy - r, 2 * r, 2 * r, col))
            ex, ey = path[-1]
            px, py = self.sq_px(ex, ey)
            canvas.over(Rect(px + 1, py + 1, T - 2, T - 2, (255, 236, 170, 230), line=2))
            if ov.get("cost") is not None:
                canvas.over(Text(px + T / 2, py - 2, f"{ov['cost']} ft", "prose_bold", max(12, min(18, T // 3)),
                                 (255, 240, 200, 255), anchor="mb", outline=True, shadow=False))
            if warn:
                wx, wy = self.sq_px(*sorted(warn)[0])
                canvas.over(Text(wx + T / 2, wy + T / 2, "!", "heading", max(14, T // 2), (255, 90, 60, 255),
                                 anchor="mm", outline=True, shadow=False))
        hov = ov.get("hover")
        if hov is not None:
            px, py = self.sq_px(*hov)
            canvas.over(Rect(px, py, T, T, (255, 255, 255, 110), line=1))
        aim = ov.get("aim")
        if aim is not None:
            px, py = self.sq_px(*aim)
            canvas.over(Rect(px - 1, py - 1, T + 2, T + 2, (255, 220, 120, 240), line=2))

    def _tokens(self, canvas, battle, now: float) -> None:
        T = self.T
        atlas = canvas.gfx.atlas
        for tok in battle.tokens:
            x, y = self.tok_pos(tok, now)
            px, py = self.sq_px(x, y)
            bob = math.sin(now * 3 + tok.id) * T * 0.06 if canvas.gfx.ambient else 0.0
            for e in self.fx:
                if e["kind"] == "tok_lunge" and e["id"] == tok.id and e["t0"] <= now <= e["t0"] + e["dur"]:
                    tx, ty = self._target_px(e["at"], now)
                    if tx is not None:
                        k = math.sin(math.pi * (now - e["t0"]) / e["dur"]) * 0.45
                        px += (tx - T / 2 - px) * k
                        py += (ty - T - py) * k
            if tok.kind == "duplicity":  # (a Trickery cleric's double: its maker's likeness, pale and shimmering)
                parts = self.figures.get(tok.owner)
                glow = any(e["kind"] == "tok_glow" and e["id"] == tok.id and e["t0"] <= now <= e["t0"] + e["dur"]
                           for e in self.fx)
                canvas.under(Image("bshadow", _shadow_image, (px + T * 0.14, py + T * 0.86, T * 0.72, T * 0.22),
                                   rgba=(255, 255, 255, 80)))
                if glow:
                    canvas.under(Image("bglow", _glow_image, (px - T * 0.2, py - T * 0.2, T * 1.4, T * 1.4),
                                       rgba=(200, 180, 255, 150)))
                if parts:
                    flick = 0.08 * math.sin(now * 3.1 + tok.id) if canvas.gfx.ambient else 0.0
                    cmd = dolls.draw(atlas, parts, px, py, T, (0.82, 0.8, 1.0), 0.58 + flick, 0.0)
                    if cmd is not None:
                        canvas.under(cmd)
                continue
            if tok.kind == "mage_hand":  # (an Arcane Trickster's unseen hand: only its own side sees it, faintly)
                owner = next((f for f in battle.fighters if f.id == tok.owner), None)
                if owner is None or owner.side != "party":
                    continue
                name = "fx/unseen_hand_glow" if atlas.has("fx/unseen_hand_glow") else "fx/magic_0"
                canvas.under(Sprite(name, px + T * 0.1, py + bob + T * 0.1, T * 0.8, T * 0.8, (255, 255, 255, 170)))
                continue
            if tok.kind == "dancing_sword":  # (a Dancing Sword: the blade itself in the air, steel-bright)
                owner = next((f for f in battle.fighters if f.id == tok.owner), None)
                it = owner.char.item(tok.item_uid) if owner is not None and owner.char is not None else None
                name = f"item/{it.def_id}" if it is not None and atlas.has(f"item/{it.def_id}") else "item/longsword"
                canvas.under(Image("bglow", _glow_image, (px - T * 0.15, py - T * 0.15 + bob, T * 1.3, T * 1.3),
                                   rgba=(200, 220, 255, 110)))
                canvas.under(Sprite(name if atlas.has(name) else "fx/magic_0", px + T * 0.02, py + bob, T * 0.96, T * 0.96,
                                    (240, 245, 255, 255), angle=-45.0 + math.sin(now * 2 + tok.id) * 20.0))
                continue
            if tok.kind == "guardian":
                canvas.under(Image("bglow", _glow_image, (px - T * 0.3, py - T * 0.3, T * 1.6, T * 1.6), rgba=(255, 230, 150, 120)))
                name = "feature/statue_hero" if atlas.has("feature/statue_hero") else "feature/statue"
                canvas.under(Sprite(name, px, py, T, T, (255, 240, 200, 255)))
            else:
                canvas.under(Image("bglow", _glow_image, (px - T * 0.15, py - T * 0.15 + bob, T * 1.3, T * 1.3),
                                   rgba=(170, 150, 255, 110)))
                name = "item/mace" if atlas.has("item/mace") else "fx/magic_0"
                canvas.under(Sprite(name, px + T * 0.02, py + bob, T * 0.96, T * 0.96, (235, 225, 255, 255), angle=-30.0))

    def _people(self, canvas, game, battle, now: float, ov: dict, cur) -> None:
        gfx = canvas.gfx
        atlas = gfx.atlas
        T = self.T
        light = getattr(self, "light", None)
        seen_by_party = ov.get("seen", None)
        order = []
        for f in battle.fighters:
            if f.state == "fled" or f.state == "away" and not (f.away or {}).get("stays") \
                    or f.state == "dead" and getattr(f, "bond", None) is not None:
                continue  # (gone, or banished or blinked away for now; a familiar or a steed vanishes at 0)
            x, y = self.pos(f, now)
            order.append((y + f.sq, f, x, y))
        order.sort(key=lambda t: t[0])
        self.cells = {}
        self.status_px = {}
        cw, ch = canvas.cell_w, canvas.cell_h
        for _, f, x, y in order:
            cx, fy, s = self.place(f, now)
            parts = self.figures.get(f.id)
            if parts is None:
                parts = _figure(f, game, atlas)
                self.figures[f.id] = parts
            tint = (1.0, 1.0, 1.0)
            if light is not None:
                lx, ly = int(min(battle.field.width - 1, max(0, round(x)))), int(min(battle.field.height - 1, max(0, round(y))))
                tint = tuple(float(v) for v in light[lx, ly])
            alpha = 1.0
            if f.state == "away":  # (sealed in a sphere: seen through its shimmer)
                alpha = 0.7
                bx, by = self.sq_px(x, y)
                pulse = 0.5 + 0.5 * math.sin(now * 3) if gfx.ambient else 0.6
                pts = [(bx + T * f.sq / 2 + math.cos(a / 12 * math.pi) * T * f.sq * 0.55,
                        by + T * f.sq / 2 + math.sin(a / 12 * math.pi) * T * f.sq * 0.55) for a in range(25)]
                canvas.over(Lines(pts, max(2, T // 14), (190, 220, 255, int(140 + 80 * pulse))))
            flash = next((e for e in self.fx if e["kind"] == "hit" and e["who"] == f.id and e["t0"] <= now <= e["t0"] + e["dur"]),
                         None)
            if flash is not None:
                p = (now - flash["t0"]) / flash["dur"]
                tint = (1.0, 0.45 + 0.55 * p, 0.42 + 0.58 * p)
            if f.state == "surrendered":
                tint = tuple(v * 0.6 for v in tint)
            if f.hidden:
                alpha = 0.55
            if (getattr(f, "bond", None) or {}).get("spectral"):  # (an illusionist's phantom: pale and see-through)
                alpha = min(alpha, 0.62 + (0.08 * math.sin(now * 2.7 + f.id) if gfx.ambient else 0.0))
                tint = (tint[0] * 0.8, tint[1] * 0.82, min(1.0, tint[2] * 1.1))
            unseen = seen_by_party is not None and f.side != "party" and f.id not in seen_by_party and f.state != "dead"
            if unseen:  # somewhere in the dark: a shape, no more
                tint = (0.10, 0.10, 0.16)
                alpha = min(alpha, 0.75)
            angle = 0.0
            if f.id in self.fell:
                p = min(1.0, max(0.0, (now - self.fell[f.id]) / FALL)) if gfx.animate else 1.0
                angle = (90.0 if f.side == "party" else -90.0) * (p * p)
                if f.state == "dead":
                    alpha *= 1 - 0.45 * p
                    tint = tuple(v * (1 - 0.35 * p) for v in tint)
            elif "prone" in f.conditions and f.state == "fighting":
                angle = 70.0 if f.side == "party" else -70.0
            up = self.lift_px(f, now) if f.state in ("fighting", "fleeing") else 0.0
            canvas.under(Image("bshadow", _shadow_image, (cx - s * 0.36, fy - s * 0.14, s * 0.72, s * 0.22),
                               rgba=(255, 255, 255, 150 if not up else 95)))
            if up:  # aloft: the shadow stays on the ground, the figure above it, and how high beside it
                canvas.over(Text(cx + s * 0.42, fy - 1, f"{int(round(self.height(f, now) / 5.0)) * 5} ft", "prose_bold",
                                 max(10, min(13, T // 4)), (190, 220, 255, 255), anchor="mb", outline=True, shadow=False))
                fy -= up
            if f.state == "dead" and f.id in self.fell:
                canvas.under(Image("bblood", _blood_image, (cx - s * 0.4, fy - s * 0.16, s * 0.8, s * 0.24),
                                   rgba=(140, 20, 16, 170)))
            bob = math.sin(now * 3.0) * 1.5 if (cur is not None and f is cur and gfx.ambient and not angle) else 0
            top = fy - s * 0.9 if angle else fy - s + bob
            cmd = dolls.draw(atlas, parts, cx - s / 2, top, s, tint, alpha, angle)
            if cmd is not None:
                canvas.under(cmd)
            if f.concentration is not None and gfx.ambient:
                canvas.under(Image("bglow", _glow_image, (cx - s * 0.5, fy - s * 1.1, s, s), rgba=(190, 150, 255, 46)))
            if f.buffs and any(bf.get("corona") for bf in f.buffs):  # (Corona of Light: a sun about them)
                pulse = 0.5 + 0.5 * math.sin(now * 2.2) if gfx.ambient else 0.6
                canvas.under(Image("bglow", _glow_image, (cx - s * 0.95, fy - s * 1.55, s * 1.9, s * 1.9),
                                   rgba=(255, 226, 140, int(70 + 50 * pulse))))
            if not unseen:
                self._label(canvas, battle, f, cx, fy, s, ov)
            px, py = self.sq_px(x, y)
            self.cells[f.id] = (int(px // cw), int(py // ch), max(1, int(s // cw)), max(1, int(s // ch)))

    def _label(self, canvas, battle, f, cx, fy, s, ov) -> None:
        from realmwalker.ui import colors

        if f.state in ("dead", "fled") or f.state == "away" and not (f.away or {}).get("stays"):
            return
        T = self.T
        ratio = f.hp / max(1, f.max_hp)
        bar_color = colors.named("good" if ratio > 0.6 else ("warn" if ratio > 0.3 else "danger"))
        bw = s * 0.8
        canvas.over(*theme.bar(cx - bw / 2, fy - s - 5, bw, max(3, T // 10), ratio, bar_color))
        if T >= 24:
            self._statuses(canvas, battle, f, cx, fy - s - 7)
        show_name = f.id in (ov.get("named") or ()) or f.id == ov.get("current") or f.id == ov.get("target")
        if show_name and T >= 24:
            color = (150, 220, 130) if f.side == "party" else (236, 120, 100)
            canvas.over(Text(cx, fy - s - 7, f.name, "prose_bold", max(12, min(16, T // 3)), (*color, 255), anchor="mb",
                             outline=True, shadow=False))
        tag = None
        if f.state == "down":
            tag = ("stable" if f.stable else f"dying {f.death_saves[1]}/3", (255, 110, 90))
        elif f.state == "surrendered":
            tag = ("yields", (200, 200, 190))
        elif f.state == "fleeing":
            tag = ("flees", (230, 200, 120))
        else:
            c = next((c for c in TAGS if c in f.conditions), None)
            if c is not None:
                tag = (TAGS[c], (230, 200, 150))
        if tag is not None and T >= 24:  # one short word, small enough to sit under its own square
            canvas.over(Text(cx, fy - 1, tag[0], "prose_bold", max(10, min(13, T // 4)), (*tag[1], 255), anchor="mb",
                             outline=True, shadow=False))

    def _statuses(self, canvas, battle, f, cx: float, bottom: float) -> None:
        """A row of status icons above the health bar: up to four, then "+N" (rules/describe.statuses)."""
        from realmwalker.rules import describe

        sts = describe.statuses(f, battle)
        if not sts:
            return
        k = 2 if self.T >= 40 else 1  # whole multiples of the 10-pixel pictograms
        size = 10 * k
        shown = sts[:STATUS_ROW]
        extra = len(sts) - len(shown)
        width = len(shown) * (size + 1) + (size if extra else 0)
        x0 = cx - width / 2
        top = bottom - size
        rects = []
        for i, st in enumerate(shown):
            px = round(x0 + i * (size + 1))
            canvas.over(Sprite(st.icon, px, round(top), size, size))
            rects.append(((px, top, size, size), st))
        if extra:
            canvas.over(Text(x0 + len(shown) * (size + 1) + 1, bottom, f"+{extra}", "prose_bold", max(10, size - 2),
                             (230, 220, 200, 255), anchor="lb", outline=True, shadow=False))
        self.status_px[f.id] = rects

    def _effects(self, canvas, now: float) -> None:
        atlas = canvas.gfx.atlas
        T = self.T
        for e in self.fx:
            if now < e["t0"]:
                continue
            p = (now - e["t0"]) / e["dur"]
            if p > 1:
                continue
            k = e["kind"]
            if k == "shot":
                a, b = self._centre(e["from"], now), self._centre(e["to"], now)
                if a is None or b is None:
                    continue
                (ax, ay), (bx, by) = a, b
                lift = e.get("curve", 14)
                px_, py_ = ax + (bx - ax) * p, ay + (by - ay) * p - math.sin(math.pi * p) * lift
                ang = math.degrees(math.atan2(by - ay, bx - ax))
                sz = max(20, T * 0.8)
                name = e["sprite"]
                base = name.rsplit("_", 1)[0]
                if len(atlas.family(base)) == 8:  # pictures for eight directions: 0 points north, 2 east...
                    name = f"{base}_{int(round((ang + 90) / 45.0)) % 8}"
                elif atlas.family(base) and not atlas.has(name):
                    fam = atlas.family(base)
                    name = fam[int(now * 10) % len(fam)]
                if atlas.has(name):
                    canvas.over(Sprite(name, px_ - sz / 2, py_ - sz / 2, sz, sz))
                else:
                    canvas.over(Image("bspark", _glow_image, (px_ - 10, py_ - 10, 20, 20), rgba=(255, 230, 160, 255)))
            elif k == "beam":
                a, b = self._centre(e["from"], now), self._centre(e["to"], now)
                if a is None or b is None:
                    continue
                r, g, bl = e["color"]
                fade = int(255 * (1 - p) ** 0.6)
                canvas.over(Lines([a, b], max(6, T * 0.3), (r, g, bl, fade // 3)))
                canvas.over(Lines([a, b], max(2, T * 0.1), (min(255, r + 60), min(255, g + 60), min(255, bl + 60), fade)))
            elif k == "bead":
                (ax, ay), (bx, by) = self.sq_px(*e["from"]), self.sq_px(*e["to"])
                px_, py_ = ax + (bx - ax) * p, ay + (by - ay) * p - math.sin(math.pi * p) * T
                r, g, bl = e["color"]
                canvas.over(Image("bglow", _glow_image, (px_ - T * 0.5, py_ - T * 0.5, T, T), rgba=(r, g, bl, 220)))
                fam = atlas.family(e["sprite"])
                if fam:
                    canvas.over(Sprite(fam[int(now * 12) % len(fam)], px_ - T * 0.35, py_ - T * 0.35, T * 0.7, T * 0.7))
            elif k == "bolt":
                (ax, ay), (bx, by) = self.sq_px(*e["from"]), self.sq_px(*e["to"])
                r, g, bl = e["color"]
                fade = int(255 * (1 - p))
                pts = [(ax, ay)]
                n = 9
                seed = e["seed"] + int(now * 20)
                for i in range(1, n):
                    t = i / n
                    jitter = math.sin(seed * 12.9898 + i * 78.233) * T * 0.35
                    nx, ny = -(by - ay), bx - ax
                    ln = math.hypot(nx, ny) or 1.0
                    pts.append((ax + (bx - ax) * t + nx / ln * jitter, ay + (by - ay) * t + ny / ln * jitter))
                pts.append((bx, by))
                canvas.over(Lines(pts, max(8, T * 0.4), (r, g, bl, fade // 3)))
                canvas.over(Lines(pts, max(2, T * 0.1), (255, 255, 255, fade)))
            elif k == "column":  # light or fire falling from above onto the spot
                cx, cy = self.sq_px(*e["at"])
                r, g, bl = e["color"]
                fade = int(255 * (1 - p) ** 0.7)
                width = max(8, T * 0.5) * e.get("radius", 1.0) ** 0.5
                top = cy - T * 6 * (1 - min(1.0, p * 3))
                canvas.over(Lines([(cx, top - T * 4), (cx, cy)], width, (r, g, bl, fade // 3)))
                canvas.over(Lines([(cx, top - T * 4), (cx, cy)], max(2, width * 0.3), (255, 250, 230, fade)))
            elif k == "flash":
                cx, cy = self.sq_px(*e["at"])
                rad = e["radius"] * T * (0.4 + 0.8 * min(1.0, p * 2))
                r, g, bl = e["color"]
                canvas.over(Image("bburst", _burst_image, (cx - rad, cy - rad, rad * 2, rad * 2),
                                  rgba=(r, g, bl, int(230 * (1 - p) ** 0.8))))
            elif k == "shock":
                cx, cy = self.sq_px(*e["at"])
                rad = e["radius"] * T * (0.3 + 1.0 * p)
                r, g, bl = e["color"]
                canvas.over(Image("bring2", _ring_image, (cx - rad, cy - rad, rad * 2, rad * 2),
                                  rgba=(r, g, bl, int(230 * (1 - p)))))
            elif k == "cell":
                x, y = e["at"]
                px, py = self.sq_px(x, y)
                fam = atlas.family(e["sprite"]) or ([e["sprite"]] if atlas.has(e["sprite"]) else [])
                r, g, bl = e["color"]
                canvas.over(Rect(px, py, T, T, (r, g, bl, int(110 * (1 - p)))))
                if fam:
                    name = fam[min(len(fam) - 1, int(p * len(fam)))]
                    s = T * (0.8 + 0.4 * p)
                    canvas.over(Sprite(name, px + (T - s) / 2, py + (T - s) / 2, s, s, (255, 255, 255, int(255 * (1 - p) ** 0.7))))
            elif k == "puff":
                x, y = e["at"]
                px, py = self.sq_px(x, y)
                s = T * (0.6 + 0.8 * p)
                r, g, bl = e["color"]
                canvas.over(Image("bglow", _glow_image, (px + (T - s) / 2, py + (T - s) / 2, s, s), rgba=(r, g, bl, int(220 * (1 - p)))))
            elif k == "zone_in":
                for (x, y) in e["cells"]:
                    px, py = self.sq_px(x, y)
                    canvas.over(Rect(px, py, T, T, (255, 255, 255, int(80 * (1 - p)))))
            elif k == "float" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                rise = 36 * (1 - (1 - p) ** 2)
                a = int(255 * (1 - max(0.0, (p - 0.55) / 0.45)))
                y0 = fy - s * (0.45 if e.get("low") else 1.0) - 8 - rise
                canvas.over(Text(cx + 6, y0, e["text"], "heading", e.get("size", 20), (*e["color"], a), anchor="mb",
                                 outline=True, shadow=False))
            elif k == "burst" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                frames = atlas.family(e["sprite"]) or ([e["sprite"]] if atlas.has(e["sprite"]) else [])
                if not frames:
                    continue
                name = frames[min(len(frames) - 1, int(p * len(frames)))]
                kk = (0.5 if e.get("small") else 0.9) * s * (0.8 + 0.4 * p)
                a = int(255 * (1 - p) ** 0.7)
                canvas.over(Sprite(name, cx - kk / 2, fy - s * 0.55 - kk / 2, kk, kk, (255, 255, 255, a)))
            elif k == "glow" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                a = int(220 * math.sin(math.pi * p))
                r, g, bl = e.get("color", (190, 150, 255))
                canvas.under(Image("bglow", _glow_image, (cx - s * 0.7, fy - s * 1.15, s * 1.4, s * 1.4), rgba=(r, g, bl, a)))
            elif k == "ring" and e["who"] in self._fighters:
                f = self._fighters[e["who"]]
                cx, fy, s = self.place(f, now)
                rad = s * (0.4 + 0.5 * p)
                r, g, bl = e["color"]
                canvas.over(Image("bring2", _ring_image, (cx - rad, fy - s * 0.5 - rad * 0.5, rad * 2, rad),
                                  rgba=(r, g, bl, int(220 * (1 - p)))))

    def _centre(self, fid, now):
        f = self._fighters.get(fid)
        if f is None:
            return None
        cx, fy, s = self.place(f, now)
        return cx, fy - s * 0.55


def _figure(f, game, atlas) -> list:
    from realmwalker.rules import simulacrum

    if simulacrum.snow(f):  # (a Simulacrum: the likeness in snow)
        return dolls.frost(_likeness(f, game, atlas))
    return _likeness(f, game, atlas)


def _likeness(f, game, atlas) -> list:
    if f.char is not None:
        return dolls.character(f.char, game.tables, atlas=atlas)
    bond = getattr(f, "bond", None) or {}
    if bond.get("picture"):  # (a steed: the animal it looks like, in its kind's colours; a spirit: its form's)
        tint = STEED_TINT.get(bond.get("type", ""), dolls.WHITE) if bond.get("kind") == "steed" else dolls.WHITE
        return [(f"creature/{bond['picture']}", tint, 0, 0)]
    return dolls.creature(f.creature.def_id, game.tables, f"foe{f.id}", atlas, sex=getattr(f.creature, "sex", ""))


def _missile(weapon: str, kind: str, dtype: str) -> str:
    w = weapon.lower()
    if kind.startswith("spell"):
        return MAGIC_FX.get(dtype, "fx/magic") + "_0"
    if "crossbow" in w or "bolt" in w:
        return "fx/bolt_2"
    if "javelin" in w or "spear" in w:
        return "fx/javelin_2"
    if "sling" in w:
        return "fx/shot_2"
    if "dart" in w or "knife" in w or "dagger" in w or "axe" in w or "hammer" in w:
        return "fx/dart_2"
    return "fx/arrow_2"


# ---------------------------------------------------------------------------- small pictures made by code
def _shadow_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 6, 88, 26], fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(4))


def _ring_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 64), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 6, 120, 58], outline=(255, 255, 255, 255), width=5)
    return im.filter(ImageFilter.GaussianBlur(1.5))


def _blood_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([10, 6, 70, 24], fill=(255, 255, 255, 220))
    d.ellipse([50, 10, 90, 22], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(1.5))


def _glow_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([16, 16, 112, 112], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(14))


def _burst_image():
    """A blast seen from above: white-hot at the heart, ragged at the rim."""
    s = 128
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2) / (s / 2)
    ang = np.arctan2(yy - s / 2, xx - s / 2)
    rim = 0.82 + 0.1 * np.sin(ang * 7) + 0.06 * np.sin(ang * 13 + 1.0)
    a = np.clip((rim - d) / 0.35, 0, 1)
    core = np.clip(1 - d / 0.5, 0, 1)
    out = np.zeros((s, s, 4), np.uint8)
    out[..., 0] = 255
    out[..., 1] = (200 + 55 * core).astype(np.uint8)
    out[..., 2] = (160 + 95 * core).astype(np.uint8)
    out[..., 3] = (255 * a).astype(np.uint8)
    return out


def _tentacles_image(frame: int = 0):
    """Evard's Black Tentacles: dark rubbery arms curling up out of the ground (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(41)
    for _ in range(4):
        x, y = (int(v) for v in rng.integers(4, s - 4, 2))
        pts = [(x, y + 6)]
        for k in range(5):
            x = int(np.clip(x + (1 if (k + frame) % 2 else -1) * int(rng.integers(1, 3)), 1, s - 2))
            y = int(np.clip(y - 2, 1, s - 2))
            pts.append((x, y))
        d.line(pts, fill=(34, 20, 44, 245), width=2)
        d.point(pts[-1], fill=(120, 90, 140, 255))
    return im


def _insects_image(frame: int = 0):
    """Insect Plague: a swarm of biting locusts, dark specks in the air (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(53 + frame)
    for _ in range(22):
        x, y = (int(v) for v in rng.integers(1, s - 2, 2))
        d.point((x, y), fill=(40, 34, 20, 255))
        d.point((x + 1, y), fill=(90, 80, 40, 200))
    return im


def _wind_image(frame: int = 0):
    """Wind Wall: streaks of a strong wind blowing straight up (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(61 + frame)
    for _ in range(6):
        x, y = (int(v) for v in rng.integers(2, s - 2, 2))
        d.line([(x, y), (x + 1, y - 6)], fill=(235, 240, 245, 200), width=1)
    return im


def _sleet_image(frame: int = 0):
    """Sleet Storm: driving sleet over a skin of ice (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(67 + frame)
    for _ in range(9):
        x, y = (int(v) for v in rng.integers(2, s - 3, 2))
        d.line([(x, y), (x - 2, y + 4)], fill=(230, 240, 255, 230), width=1)
    return im


def _blades_image(frame: int = 0):
    """Blade Barrier: whirling blades of force, bright slivers turning in the air (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(71)
    for _ in range(5):
        x, y = (int(v) for v in rng.integers(4, s - 4, 2))
        dx, dy = ((3, -2), (2, 3))[(frame + x) % 2]
        d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=(225, 210, 255, 240), width=1)
        d.point((x + dx, y + dy), fill=(255, 255, 255, 255))
    return im


def _thorns_image(frame: int = 0):
    """Wall of Thorns: a tangle of dark brambles bristling with pale thorns."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(79)
    for _ in range(6):
        x0, y0, x1, y1 = (int(v) for v in rng.integers(1, s - 1, 4))
        d.line([(x0, y0), (x1, y1)], fill=(46, 64, 30, 250), width=2)
        mx, my = (x0 + x1) // 2, (y0 + y1) // 2
        d.point([(mx, my - 1), (mx + 1, my)], fill=(210, 200, 150, 255))
    return im


def _quake_image(frame: int = 0):
    """Earthquake: the ground split by dark cracks, a little dust thrown up along them (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(97)
    for _ in range(3):
        x, y = (int(v) for v in rng.integers(2, s - 2, 2))
        pts = [(x, y)]
        for _ in range(4):
            x = int(min(s - 1, max(0, x + rng.integers(-6, 7))))
            y = int(min(s - 1, max(0, y + rng.integers(-6, 7))))
            pts.append((x, y))
        d.line(pts, fill=(28, 20, 14, 235), width=1)
        for px_, py_ in pts[1:]:
            d.point((px_ + frame, py_ - 1 - frame), fill=(190, 170, 130, 200))
    return im


def _embers_image(frame: int = 0):
    """Incendiary Cloud: glowing embers drifting in the smoke (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(101)
    for _ in range(7):
        x, y = (int(v) for v in rng.integers(2, s - 2, 2))
        y = (y - 3 * frame) % s
        d.point((x, y), fill=(255, 190, 70, 255))
        d.point((x, (y + 1) % s), fill=(220, 90, 30, 230))
    return im


def _prismatic_image(frame: int = 0):
    """Prismatic Wall: seven bands of colour, shimmering (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bands = [(230, 50, 50), (240, 140, 40), (240, 220, 60), (70, 190, 80), (70, 120, 230), (90, 60, 170),
             (170, 80, 210)]
    h = s / len(bands)
    for i, col in enumerate(bands[frame:] + bands[:frame]):
        d.rectangle([0, int(i * h), s - 1, int((i + 1) * h)], fill=(*col, 215))
    for x in range(0, s, 6):
        d.point((x + frame * 3 % 6, (x * 7) % s), fill=(255, 255, 255, 255))
    return im


GROUND_LOOKS = {  # how the second wave's ground looks on the battle mat (BattleBoard._spell_ground)
    "tentacles": {"colour": (40, 26, 52), "alpha": 70, "image": _tentacles_image, "frames": True},
    "cloud": {"colour": (176, 200, 84), "fog": True, "alpha": 190},
    "stench": {"colour": (190, 186, 90), "fog": True, "alpha": 175},
    "hunger": {"colour": (8, 6, 12), "fog": True, "alpha": 235},
    "insects": {"colour": (120, 104, 60), "alpha": 40, "image": _insects_image, "frames": True},
    "sleet": {"colour": (200, 214, 236), "fog": True, "alpha": 160, "image": _sleet_image, "frames": True},
    "radiance": {"colour": (255, 240, 190), "alpha": 70, "edge": True},
    "spirits": {"colour": (170, 230, 190), "alpha": 40, "edge": True},
    "elemental": {"colour": (255, 150, 70), "alpha": 50, "edge": True},
    "wind": {"colour": (220, 230, 240), "alpha": 20, "image": _wind_image, "frames": True},
    "force": {"colour": (150, 190, 255), "alpha": 150},
    "stone": {"colour": (120, 116, 108), "alpha": 0},
    # the third wave's (D.3)
    "blades": {"colour": (150, 120, 220), "alpha": 35, "image": _blades_image, "frames": True},
    "thorns": {"colour": (40, 58, 26), "alpha": 140, "image": _thorns_image},
    "celestial": {"colour": (255, 246, 205), "alpha": 70, "edge": True},
    "icewall": {"colour": (200, 232, 255), "alpha": 120},
    # the fourth wave's (D.4)
    "antimagic": {"colour": (120, 120, 130), "alpha": 45, "edge": True},
    "quake": {"colour": (120, 96, 66), "alpha": 50, "image": _quake_image, "frames": True},
    "embers": {"colour": (120, 70, 50), "fog": True, "alpha": 200, "image": _embers_image, "frames": True},
    "prismatic": {"colour": (230, 230, 255), "alpha": 60, "image": _prismatic_image, "frames": True},
    "glare": {"colour": (255, 250, 230), "alpha": 40, "edge": True},
    "storm": {"colour": (70, 76, 92), "fog": True, "alpha": 150, "image": _sleet_image, "frames": True},
}


def _fog_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for (x, y, r) in ((22, 26, 16), (40, 30, 15), (30, 40, 14), (34, 22, 12)):
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 150))
    return im.filter(ImageFilter.GaussianBlur(6))


def _web_image():
    """A web across a square, in sharp single pixels: spokes from the middle and three rings of thread."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s / 2
    spokes = 8
    pts = []
    for k in range(spokes):
        ang = k * 2 * math.pi / spokes + 0.2
        pts.append((c + math.cos(ang) * c, c + math.sin(ang) * c))
        d.line([(c, c), pts[-1]], fill=(255, 255, 255, 200), width=1)
    for ring in (0.3, 0.55, 0.85):
        ring_pts = [(c + (p[0] - c) * ring, c + (p[1] - c) * ring) for p in pts]
        d.line(ring_pts + [ring_pts[0]], fill=(255, 255, 255, 170), width=1)
    return im


def _vines_image(_frame: int = 0):
    """Entangle: grasping weeds and vines over the square, in sharp pixels."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(23)
    d.rectangle([0, 0, s, s], fill=(60, 110, 40, 50))
    for _ in range(7):
        x, y = (int(v) for v in rng.integers(0, s, 2))
        pts = [(x, y)]
        for _k in range(4):
            x = int(np.clip(x + rng.integers(-6, 7), 0, s - 1))
            y = int(np.clip(y + rng.integers(-6, 7), 0, s - 1))
            pts.append((x, y))
        d.line(pts, fill=(70, 150, 50, 235), width=1)
        for px, py in pts[1:]:
            d.point((px, py), fill=(140, 210, 90, 255))
    return im


def _grease_image(_frame: int = 0):
    """Grease: a dark slick with a few bright glints."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(29)
    d.rectangle([0, 0, s, s], fill=(52, 44, 30, 120))
    for _ in range(6):
        x, y = (int(v) for v in rng.integers(1, s - 6, 2))
        d.ellipse([x, y, x + 5, y + 3], fill=(84, 72, 46, 170))
        d.point((x + 1, y + 1), fill=(230, 220, 170, 255))
    return im


def _thorns_image(_frame: int = 0):
    """Spike Growth: hard thorns and spikes hidden in the ground."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(31)
    for _ in range(11):
        x, y = (int(v) for v in rng.integers(2, s - 3, 2))
        d.line([(x, y + 2), (x + 1, y - 2)], fill=(110, 84, 50, 235), width=1)
        d.point((x + 1, y - 2), fill=(200, 180, 140, 255))
    return im


def _blades_image(frame: int = 0):
    """Cloud of Daggers: spinning blades glinting in the air (two frames)."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(37 + frame)
    for _ in range(8):
        x, y = (int(v) for v in rng.integers(3, s - 4, 2))
        dx, dy = ((3, -3), (3, 3))[int(rng.integers(0, 2))]
        d.line([(x, y), (x + dx, y + dy)], fill=(210, 216, 228, 245), width=1)
        d.point((x, y), fill=(255, 255, 255, 255))
    return im


def _caltrops_image():
    """Iron caltrops strewn on the ground: little dark four-pointed stars."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(11)
    for _ in range(7):
        x, y = (int(v) for v in rng.integers(3, s - 4, 2))
        d.line([(x - 2, y), (x + 2, y)], fill=(58, 56, 54, 255), width=1)
        d.line([(x, y - 2), (x, y + 2)], fill=(58, 56, 54, 255), width=1)
        d.point((x, y - 2), fill=(150, 146, 138, 255))
    return im


def _bearings_image():
    """Ball bearings spilled over the floor: small bright beads with a dark side."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(17)
    for _ in range(14):
        x, y = (int(v) for v in rng.integers(1, s - 3, 2))
        d.rectangle([x, y, x + 1, y + 1], fill=(120, 118, 112, 255))
        d.point((x, y), fill=(230, 226, 214, 255))
    return im


def _ice_image():
    """Hailstones and a skin of ice on the ground, in sharp pixels."""
    from PIL import Image as PImage, ImageDraw

    s = 32
    im = PImage.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(5)
    d.rectangle([0, 0, s, s], fill=(200, 230, 255, 60))
    for _ in range(9):
        x, y = rng.integers(2, s - 4, 2)
        d.polygon([(x, y), (x + 3, y + 1), (x + 1, y + 3)], fill=(240, 250, 255, 230))
    for _ in range(4):
        x, y = rng.integers(0, s - 8, 2)
        d.line([(x, y), (x + 7, y + 3)], fill=(255, 255, 255, 160), width=1)
    return im
