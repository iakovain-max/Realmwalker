"""Finding and seeing, and asking the powers (Expansion 3 E.3): the divination spells outside a fight.

A spell's {"op": "road", "does": "sense" | "locate" | "scout" | "summons" | "ask", ...} is done here (game/spellwork's
door sends it here). What a spell is aimed at is a Subject (a thing to seek, a person, a question, a work in hand),
listed on the Spells page as the places of travel are. What is sensed on a close-up map is marked there for the
spell's time (`game.sensed`, not kept in a save: a spell's glow, like a campfire). The answers come from the world as
it truly is: the levels below, the works and their hidden sides, the history's beasts, dragons and lost treasures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from realmwalker.core import dice
from realmwalker.core.textgen import a_or_an
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.rules.character import Character

SENSE_SQUARES = 6  # 30 feet
TRAP_SQUARES = 24  # 120 feet (Find Traps)
LOCATE_SQUARES = 200  # 1,000 feet
NATURE_TILES = 2  # 5 miles, at three miles a tile
EVIL_KINDS = ("aberration", "celestial", "elemental", "fey", "fiend", "undead")
TIP_HOURS = 12  # a hunt or forage helped by Locate Animals or Plants, Speak with Plants, Commune with Nature
REPEAT_CHANCE = 0.25  # each casting after the first before a long rest (augury, divination, commune, contact)
OTHER_PLANE_DC = 15
# The school of magic an item's aura shows (Detect Magic), by its first power.
SCHOOLS = {"bonus": "evocation", "ac": "abjuration", "save": "abjuration", "skill": "divination",
           "resist": "abjuration", "light": "evocation", "warmth": "transmutation", "ability": "transmutation",
           "charges": "evocation"}


@dataclass
class Subject:
    """Something a spell can be aimed at outside a fight: a thing to seek, a creature, a question, a work in hand,
    a figure of the world, a thing carried, a companion far away, a corpse."""
    name: str
    kind: str
    ref: object = None
    x: int = 0
    y: int = 0
    alive: bool = True  # (read by the Spells page as it would be for a person)
    data: dict = field(default_factory=dict)


def _road(spell: dict) -> dict:
    return next((o for o in spell.get("effects", ()) if o.get("op") == "road"), {})


def _first(c) -> str:
    return esc(c.name.split()[0])


def _feet(dx: float, dy: float) -> int:
    return int(round(math.hypot(dx, dy))) * 5


def way_words(dx: int, dy: int, unit: str = "feet") -> str:
    from realmwalker.game.events import compass

    if dx == 0 and dy == 0:
        return "right here"
    if unit == "miles":
        from realmwalker.game.state import MILES_PER_TILE

        miles = max(1, int(round(math.hypot(dx, dy) * MILES_PER_TILE)))
        return f"about {miles} mile{'s' if miles != 1 else ''} to the {compass(dx, dy)}"
    return f"{_feet(dx, dy)} feet to the {compass(dx, dy)}"


# ---------------------------------------------------------------------------- what is sensed, on the map
def mark(game, x: int, y: int, kind: str, minutes: float, **follow) -> None:
    """Show something sensed on the close-up map for a while (kinds: tools/tile_art.SENSED; `npc=` or `actor=` makes
    the mark follow that one)."""
    lm = game.local
    if lm is None:
        return
    marks = getattr(game, "sensed", None)
    if marks is None:
        marks = game.sensed = []
    marks[:] = [m for m in marks if not (m["map"] == lm.key and (m["x"], m["y"]) == (x, y) and m["kind"] == kind)]
    marks.append({"map": lm.key, "x": int(x), "y": int(y), "kind": kind, "until": game.world.time + minutes,
                  **follow})


def marks_here(game) -> list[dict]:
    """What is still sensed on this map, where it is now."""
    lm = game.local
    marks = getattr(game, "sensed", None)
    if lm is None or not marks:
        return []
    now = game.world.time
    marks[:] = [m for m in marks if m["until"] > now]
    out = []
    for m in marks:
        if m["map"] != lm.key:
            continue
        if "actor" in m:
            a = next((a for a in lm.actors if a.id == m["actor"] and a.creatures), None)
            if a is None:
                continue
            m["x"], m["y"] = a.x, a.y
        if "npc" in m:
            npc = game.world.npcs.get(m["npc"]) if isinstance(game.world.npcs, dict) else None
            if npc is None or not npc.alive or not npc.present:
                continue
            m["x"], m["y"] = npc.x, npc.y
        out.append(m)
    return out


def _minutes(spell: dict) -> float:
    return max(1.0, int(spell.get("rounds", 0)) / 10)  # (a round is six seconds)


def _line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    n = max(abs(x1 - x0), abs(y1 - y0))
    return [(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)) for i in range(1, n)] if n else []


def behind_stone(game, lm, x: int, y: int) -> bool:
    """Whether a foot of stone (a wall, not a door) lies between the player and a square: divination stops there."""
    T = game.tables.terrain
    terrain = game.remap_for(lm)[lm.terrain]
    p = game.player
    for cx, cy in _line(p.lx, p.ly, x, y):
        if not lm.in_bounds(cx, cy):
            return True
        if T.has_tag(int(terrain[cx, cy]), "wall"):  # (a wall, a cliff, a secret door; not a tree, a hedge, a door)
            return True
    return False


def _near(game, lm, x: int, y: int, squares: int) -> bool:
    p = game.player
    return max(abs(x - p.lx), abs(y - p.ly)) <= squares


def _terrain_id(game, lm, x: int, y: int) -> str:
    return game.tables.terrain.ids[int(game.remap_for(lm)[lm.terrain][x, y])]


# ---------------------------------------------------------------------------- sensing (Detect Magic, Evil and Good,
# Poison and Disease; Find Traps)
def aura_of(item) -> str:
    if item.magic.get("artifact"):
        return "every school at once"
    props = item.magic.get("props") or []
    return SCHOOLS.get(props[0].get("kind", ""), "abjuration") if props else "abjuration"


def chest_magic(game, lm, pos) -> bool:
    """Whether a closed chest holds something magic (its contents are fixed from now on: game/dungeon)."""
    from realmwalker.game import dungeon

    f = lm.features.get(pos) or {}
    if f.get("artifact") is not None:
        return True
    items, _money = dungeon.fix_contents(game, lm, pos)
    return any(it.get("magic") for it in items)


def _sense_magic(game, caster, spell) -> list[str]:
    from realmwalker.rules.inventory import carried

    out = [f"{_first(caster)} casts <magic>{spell['name']}</>: the air takes on a faint shimmer."]
    found = 0
    for it in carried(game.party):
        if it.magic and not it.magic.get("identified"):
            out.append(f"The {esc(game.tables.items.name(it, False))} glows with the aura of {aura_of(it)}.")
            it.magic["aura"] = aura_of(it)
            found += 1
    lm = game.local
    if lm is not None:
        minutes = _minutes(spell)
        for pos, f in list(lm.features.items()):
            if f.get("kind") != "chest" or f.get("opened") or not _near(game, lm, *pos, SENSE_SQUARES):
                continue
            if behind_stone(game, lm, *pos) or not chest_magic(game, lm, pos):
                continue
            mark(game, pos[0], pos[1], "magic", minutes)
            p = game.player
            out.append(f"<magic>Something in a chest {way_words(pos[0] - p.lx, pos[1] - p.ly)} glows with magic.</>")
            found += 1
        for (ix, iy), pile in lm.items.items():
            if pile and any(it.magic for it in pile) and _near(game, lm, ix, iy, SENSE_SQUARES) \
                    and (ix, iy) != (game.player.lx, game.player.ly) and not behind_stone(game, lm, ix, iy):
                mark(game, ix, iy, "magic", minutes)
                found += 1
                out.append("<magic>Something lying close by glows with magic.</>")
    if not found:
        out.append("<dim>Nothing stirs within thirty feet but the magic you already know.</>")
    return out


def _creature_def(game, c) -> dict:
    return game.tables.creatures[c.def_id]


def _venomous(game, c) -> bool:
    d = _creature_def(game, c)
    text = str(d.get("attack_extras", "")) + " ".join(d.get("traits", ()))
    return "poison" in text or "venom" in text or d.get("kind") in ("ooze",)


def _bands_near(game, lm, squares: int, test) -> list:
    p = game.player
    out = []
    for a in lm.actors:
        if not a.creatures or not _near(game, lm, a.x, a.y, squares) or behind_stone(game, lm, a.x, a.y):
            continue
        hits = [c for c in a.creatures if test(c)]
        if hits:
            out.append((a, hits, way_words(a.x - p.lx, a.y - p.ly)))
    return out


def _sense_evil(game, caster, spell) -> list[str]:
    from realmwalker.game import past

    out = [f"{_first(caster)} casts <magic>{spell['name']}</> and listens with the soul."]
    found = 0
    lm = game.local
    if lm is not None:
        for a, hits, where in _bands_near(game, lm, SENSE_SQUARES,
                                          lambda c: _creature_def(game, c).get("kind") in EVIL_KINDS):
            kind = _creature_def(game, hits[0]).get("kind")
            mark(game, a.x, a.y, "evil", _minutes(spell), actor=a.id)
            out.append(f"<warn>{a_or_an(kind).capitalize()} is there, {where}.</>")
            found += 1
    p = game.player
    scar = past.scar_at(game.world, p.x, p.y)
    if scar is not None and not scar.get("laid"):
        out.append(f"<warn>The ground is haunted: {esc(scar.get('name', 'an old battle'))} left its dead here.</>")
        found += 1
    from realmwalker.game import warding

    holy = warding.hallowed_at(game)  # (Hallow: the spell tells whether it is active here, and where)
    if holy is not None:
        out.append("<good>The ground here is hallowed: no aberration, elemental, fey, fiend or undead can come onto "
                   "it.</>" + (" Where the dead of the old battle lie, they lie quiet." if scar is not None and
                               scar.get("laid") else ""))
        found += 1
    site = game.world.site_at(p.x, p.y)
    if site is not None and site.kind == "barrow":
        out.append("<warn>The dead lie uneasy here.</>")
        found += 1
    if not found:
        out.append("<dim>Nothing of the other worlds and nothing undead is within thirty feet.</>")
    return out


def _sense_poison(game, caster, spell) -> list[str]:
    from realmwalker.game.spellwork import spoiled_things
    from realmwalker.world import dungeon as gen

    out = [f"{_first(caster)} casts <magic>{spell['name']}</> over the party and the ground round about."]
    found = 0
    for c in game.party:
        if not c.alive:
            continue
        for d in c.diseases:
            if d.get("id") in game.tables.diseases and d.get("phase") in ("incubating", "sick"):
                name = game.tables.diseases[d["id"]].get("name", d["id"])
                hidden = d.get("phase") == "incubating"
                d["sensed"] = True
                out.append(f"<warn>{_first(c)} carries {esc(name)}</>" + (", not yet showing." if hidden else "."))
                found += 1
    from realmwalker.rules import poisons

    for c in game.party:
        for it in c.inventory:
            if c.alive and poisons.masked(it):
                was = game.tables.items.name(it, False)
                out.append(f"<warn>The {esc(was)} in {_first(c)}'s pack is {esc(poisons.unmask(game.tables, it))}."
                           f"</>")
                found += 1
    food, water = spoiled_things(game)
    for it in food:
        out.append(f"<warn>The {esc(game.tables.items.name(it, False))} has gone bad.</>")
        found += 1
    for it in water:
        out.append(f"<warn>The water in the {esc(game.tables.items.name(it, False))} is foul.</>")
        found += 1
    lm = game.local
    if lm is not None:
        p = game.player
        for (x, y), f in lm.features.items():
            if f.get("kind") == "trap" and f.get("trap") == "darts" and not f.get("spent") \
                    and _near(game, lm, x, y, SENSE_SQUARES) and not behind_stone(game, lm, x, y):
                f["found"] = True  # (the poison's place is sensed: the darts' plate is found)
                out.append(f"<warn>Poison: {gen.TRAPS['darts'][0]}, {way_words(x - p.lx, y - p.ly)}.</>")
                found += 1
        for a, hits, where in _bands_near(game, lm, SENSE_SQUARES, lambda c: _venomous(game, c)):
            mark(game, a.x, a.y, "poison", _minutes(spell), actor=a.id)
            out.append(f"<warn>Something venomous waits {where}.</>")
            found += 1
    if not found:
        out.append("<dim>No poison and no sickness within thirty feet.</>")
    return out


def _sense_traps(game, caster, spell) -> list[str]:
    import tcod.map

    from realmwalker.game import vision
    from realmwalker.world import dungeon as gen

    out = [f"{_first(caster)} casts <magic>{spell['name']}</> and feels for the hidden harm in the place."]
    lm = game.local
    kinds: dict[str, int] = {}
    if lm is not None:
        p = game.player
        see = vision.sight_blockers(game, lm)
        fov = tcod.map.compute_fov(see, (p.lx, p.ly), radius=TRAP_SQUARES, light_walls=True)
        for (x, y), f in lm.features.items():
            if f.get("kind") == "trap" and not f.get("spent") and not f.get("found") and fov[x, y]:
                f["sensed"] = True
                name = {**gen.TRAPS, **gen.WARDS}.get(f.get("trap", "pit"), gen.TRAPS["pit"])[0]
                kinds[name] = kinds.get(name, 0) + 1
    if not kinds:
        return out + ["<dim>No trap you could see the way to lies within 120 feet.</>"]
    words = [f"{n} of {name}" if n > 1 else name for name, n in kinds.items()]
    out.append(f"<warn>Within 120 feet: {', '.join(words)}.</> <dim>You do not know where, but you will look for "
               f"them with Advantage, and be ready if one springs.</>")
    return out


# ---------------------------------------------------------------------------- locating (Locate Object, Creature,
# Animals or Plants)
def _object_subjects(game) -> list[Subject]:
    lm = game.local
    if lm is None:
        return []
    from realmwalker.game import quests

    out = []
    p = game.player
    closed = [(pos, f) for pos, f in lm.features.items() if f.get("kind") == "chest" and not f.get("opened")]
    for pos, f in closed:
        if f.get("artifact") is not None:
            arts = game.world.politics.get("artifacts", [])
            name = arts[f["artifact"]]["name"] if 0 <= f["artifact"] < len(arts) else "a lost treasure"
            out.append(Subject(name, "thing", pos, *pos))
        elif f.get("quest") is not None:
            q = quests.by_id(game, f["quest"])
            if q is not None and q["state"] in quests.LIVE:
                out.append(Subject(q["target"].get("item", "the thing you were sent for"), "thing", pos, *pos))
    for x, y in zip(*np.nonzero(_hoard_cells(game, lm))):
        out.append(Subject("the hoard", "thing", (int(x), int(y)), int(x), int(y)))
        break
    plain = [pos for pos, f in closed if f.get("artifact") is None and f.get("quest") is None]
    if plain:
        pos = min(plain, key=lambda q: math.hypot(q[0] - p.lx, q[1] - p.ly))
        out.append(Subject("the nearest chest", "thing", pos, *pos))
    return [s for s in out if _near(game, lm, s.x, s.y, LOCATE_SQUARES)]


def _hoard_cells(game, lm) -> np.ndarray:
    T = game.tables.terrain
    terrain = game.remap_for(lm)[lm.terrain]
    if "hoard" not in T.ids:
        return np.zeros(terrain.shape, dtype=bool)
    return terrain == T.ids.index("hoard")


def _creature_subjects(game) -> list[Subject]:
    lm = game.local
    if lm is None:
        return []
    from realmwalker.game import quests

    out = []
    if lm.kind == "dungeon":
        for (x, y), f in lm.features.items():
            if f.get("kind") == "captive" and not f.get("freed"):
                out.append(Subject(f.get("name") or "a captive", "creature", None, x, y))
        boss = lm.meta.get("boss")
        for a in lm.actors:
            if not a.creatures:
                continue
            named = next((c for c in a.creatures if getattr(c, "named", False)), None)
            if named is not None or (boss and a.group == boss and int(lm.meta.get("level", 1)) ==
                                     int(lm.meta.get("depth", 1))):
                who = named.name if named is not None else f"the master of this place"
                out.append(Subject(who, "creature", ("actor", a.id), a.x, a.y))
    here = game.world.settlement_at(game.player.x, game.player.y)
    if lm.kind == "settlement" and here is not None and isinstance(game.world.npcs, dict):
        wanted = {q["target"].get("npc") for q in quests.active(game) if q["target"].get("dest") == here.id}
        for npc in game.world.npcs.values():
            if npc.settlement != here.id or not npc.alive or not npc.present:
                continue
            if npc.id in wanted or npc.met:
                tag = " (your work)" if npc.id in wanted else ""
                out.append(Subject(f"{npc.name}{tag}", "creature", ("npc", npc.id), npc.x, npc.y))
    out.sort(key=lambda s: (not s.name.endswith("(your work)"), s.kind))
    return [s for s in out if _near(game, lm, s.x, s.y, LOCATE_SQUARES)][:30]


def _nature_subjects(game) -> list[Subject]:
    from realmwalker.game import quests

    p = game.player
    out = [Subject("game to hunt", "game"), Subject("herbs and things to eat", "herbs")]
    for q in quests.active(game):
        t = q["target"]
        if q["template"] == "hunt_beast" and not q["done"] and "x" in t:
            if math.hypot(int(t["x"]) - p.x, int(t["y"]) - p.y) <= NATURE_TILES:
                name = game.tables.creatures.encounters.get(t.get("group", ""), {}).get("name") or "the beast you hunt"
                out.append(Subject(name, "quarry", q["id"], int(t["x"]), int(t["y"])))
    return out


def _locate(game, caster, spell, target, what: str) -> list[str]:
    first = _first(caster)
    out = [f"{first} casts <magic>{spell['name']}</>."]
    p = game.player
    if what == "nature":
        if target.kind == "game":
            for c in game.party:
                c.effects["hunting_tip"] = max(float(c.effects.get("hunting_tip", 0)), TIP_HOURS)
            return out + [f"<good>{first} knows where the game is feeding</>: for half a day, hunting has +5."]
        if target.kind == "herbs":
            for c in game.party:
                c.effects["forage_tip"] = max(float(c.effects.get("forage_tip", 0)), TIP_HOURS)
            return out + [f"<good>{first} knows where good things grow</>: for half a day, foraging has +5."]
        game.player.explored[max(0, target.x - 1): target.x + 2, max(0, target.y - 1): target.y + 2] = True
        return out + [f"<good>{esc(target.name[:1].upper() + target.name[1:])} is "
                      f"{way_words(target.x - p.x, target.y - p.y, 'miles')}.</> <dim>(The place is on your map.)</>"]
    minutes = _minutes(spell)
    kind = "thing" if what == "object" else "creature"
    follow = {}
    if isinstance(target.ref, tuple) and target.ref[0] in ("actor", "npc"):
        follow = {target.ref[0]: target.ref[1]}
    mark(game, target.x, target.y, kind, minutes, **follow)
    out.append(f"<good>{esc(target.name[:1].upper() + target.name[1:])}: {way_words(target.x - p.lx, target.y - p.ly)}."
               f"</> <dim>(Marked on the map while the spell lasts.)</>")
    return out


# ---------------------------------------------------------------------------- seeing from afar (Clairvoyance, Arcane
# Eye, Scrying, Beast Sense)
def _rooms(lm) -> list[tuple[int, list[int]]]:
    hidden = set(lm.meta.get("hidden", []))
    return [(i, r) for i, r in enumerate(lm.meta.get("rooms", [])) if i not in hidden]


def _room_cells(lm, r) -> tuple[slice, slice]:
    rx, ry, rw, rh = (int(v) for v in r)
    return slice(max(0, rx - 1), min(lm.width, rx + rw + 1)), slice(max(0, ry - 1), min(lm.height, ry + rh + 1))


def _unseen_rooms(game, lm) -> list:
    p = game.player
    out = []
    for i, r in _rooms(lm):
        xs, ys = _room_cells(lm, r)
        if not lm.seen[xs, ys].any():
            cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
            out.append((math.hypot(cx - p.lx, cy - p.ly), i, r))
    return sorted(out)


def _bands_in(lm, cells: np.ndarray) -> list:
    return [a for a in lm.actors if a.creatures and 0 <= a.x < lm.width and 0 <= a.y < lm.height and cells[a.x, a.y]]


def _band_words(game, a) -> str:
    n = len(a.creatures)
    d = game.tables.creatures[a.creatures[0].def_id]
    named = next((c for c in a.creatures if getattr(c, "named", False)), None)
    if named is not None:
        return esc(named.name)
    return f"{n} {d['plural']}" if n > 1 else a_or_an(d["name"])


def _scout_rooms(game, caster, spell) -> list[str]:
    lm = game.local
    out = [f"{_first(caster)} looks into the glass eye and sends the sight away."]
    rooms = _unseen_rooms(game, lm)[:2]
    if not rooms:
        return out + ["<dim>Everything near has been seen already.</>"]
    cells = np.zeros(lm.seen.shape, dtype=bool)
    p = game.player
    for _d, _i, r in rooms:
        xs, ys = _room_cells(lm, r)
        room = np.zeros(lm.seen.shape, dtype=bool)
        room[xs, ys] = True
        cells |= room
        where = way_words(int(r[0] + r[2] / 2) - p.lx, int(r[1] + r[3] / 2) - p.ly)
        who = ", ".join(_band_words(game, a) for a in _bands_in(lm, room))
        out.append(f"A room {where}: " + (f"<warn>{who}</>." if who else "empty, as far as the eye can tell."))
    lm.seen |= cells
    for a in _bands_in(lm, cells):
        mark(game, a.x, a.y, "creature", _minutes(spell), actor=a.id)
    return out


def _flood(game, lm) -> np.ndarray:
    """Every square the arcane eye can float to from here: open ground and doors, never through a secret door or
    rock."""
    T = game.tables.terrain
    terrain = game.remap_for(lm)[lm.terrain]
    open_ = T.walk[terrain] | np.isin(terrain, [i for i, t in enumerate(T.ids) if "door" in t])
    for pos, f in lm.features.items():
        if f.get("kind") == "secret":
            open_[pos] = False
    seen = np.zeros(open_.shape, dtype=bool)
    start = (game.player.lx, game.player.ly)
    stack = [start]
    seen[start] = True
    w, h = open_.shape
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and open_[nx, ny] and not seen[nx, ny]:
                seen[nx, ny] = True
                stack.append((nx, ny))
    grown = seen.copy()  # (and the walls round what it saw)
    grown[1:, :] |= seen[:-1, :]
    grown[:-1, :] |= seen[1:, :]
    grown[:, 1:] |= seen[:, :-1]
    grown[:, :-1] |= seen[:, 1:]
    return grown


def _scout_level(game, caster, spell) -> list[str]:
    lm = game.local
    reach = _flood(game, lm)
    new = int((reach & ~lm.seen).sum())
    lm.seen |= reach
    bands = _bands_in(lm, reach)
    for a in bands:
        mark(game, a.x, a.y, "creature", _minutes(spell), actor=a.id)
    out = [f"{_first(caster)} casts <magic>{spell['name']}</>: an unseen eye drifts off down the passages."]
    if not new:
        out.append("<dim>It finds nothing you have not seen already.</>")
    else:
        out.append("<good>The whole of the level the eye can reach is on your map.</>")
    if bands:
        out.append("<warn>It sees " + ", ".join(_band_words(game, a) for a in bands[:6])
                   + (", and more" if len(bands) > 6 else "") + ".</>")
    return out


def _figure_where(game, fig) -> tuple[str, int, int] | None:
    """Where a figure of the world is now: (words, x, y) on the overworld."""
    w = game.world
    if fig.npc >= 0 and isinstance(w.npcs, dict) and fig.npc in w.npcs:
        npc = w.npcs[fig.npc]
        if 0 <= npc.settlement < len(w.settlements):
            s = w.settlements[npc.settlement]
            return f"in {esc(s.name)}", s.x, s.y
    home = fig.home or ""
    if home[:1] == "S" and home[1:].isdigit() and int(home[1:]) < len(w.settlements):
        s = w.settlements[int(home[1:])]
        return f"in {esc(s.name)}", s.x, s.y
    if home[:1] == "X" and home[1:].isdigit() and int(home[1:]) < len(w.sites):
        s = w.sites[int(home[1:])]
        return f"at {esc(s.name)}", s.x, s.y
    return None


def _figure_subjects(game) -> list[Subject]:
    """The figures of the world a caster could name: those met, the rulers of the realm here, the beasts and dragons
    of the works in hand and of the songs."""
    from realmwalker.game import quests
    from realmwalker.world import factions as fx

    w = game.world
    out: dict[int, Subject] = {}
    met = {npc.id for npc in w.npcs.values() if npc.met} if isinstance(w.npcs, dict) else set()

    def add(hid: int, how: str) -> None:
        fig = w.figures.get(hid)
        if fig is None or fig.died is not None or hid in out or _figure_where(game, fig) is None:
            return
        out[hid] = Subject(fig.full_name() if hasattr(fig, "full_name") else fig.name, "figure", hid,
                           data={"knowledge": how})

    for q in quests.active(game):
        if q["target"].get("beast") is not None:
            add(int(q["target"]["beast"]), "heard")
        if q["template"] == "slay_dragon":
            d = next((d for d in w.politics.get("dragons", []) if d.get("name") == q["target"].get("dragon")), None)
            if d is not None and d.get("figure") is not None:
                add(int(d["figure"]), "heard")
    for hid, fig in w.figures.items():
        if fig.npc in met:
            add(hid, "met")
    p = game.player
    here = w.settlement_at(p.x, p.y)
    if here is not None and here.owner in w.factions:
        own = w.factions[here.owner]
        for f in (own, fx.top_liege(w, own)):
            if f is not None and f.leader >= 0:
                add(int(f.leader), "heard")
    for d in w.politics.get("dragons", []):
        if d.get("alive") and d.get("figure") is not None:
            add(int(d["figure"]), "heard")
    return list(out.values())[:24]


def scry_bonus(game, fig) -> int:
    """A figure's Wisdom save (they have no sheet of their own): the beasts and dragons of the songs are strong-willed,
    an adventurer by their level, anyone else as a commoner."""
    if fig.kind == "dragon":
        return 6
    if fig.kind in ("beast", "god"):
        return 2
    if fig.cls and fig.level:
        return 2 + (fig.level - 1) // 4
    return 2 if fig.role == "ruler" else 0


def _scry(game, caster, spell, target, level: int) -> list[str]:
    from realmwalker.rules.spells import save_dc

    w = game.world
    fig = w.figures[target.ref]
    first = _first(caster)
    name = esc(target.name)
    out = [f"{first} gazes into the {'crystal ball' if game.__dict__.get('item_dc') else 'mirror'} and calls up "
           f"{name}."]
    knowledge = {"heard": 5, "met": 0, "well": -5}[target.data.get("knowledge", "heard")]
    rng = w.rng.child(f"scry/{target.ref}/{w.time}")
    dc = game.__dict__.get("item_dc") or save_dc(game.sheet(caster), game.tables)  # (a crystal ball's DC 17)
    roll = dice.d20(rng).natural
    total = roll + scry_bonus(game, fig) + knowledge
    said = f"<dim>(Wisdom save {roll} {scry_bonus(game, fig) + knowledge:+d} = {total} vs DC {dc})</>"
    if total >= dc:
        caster.effects[f"scry_block:{target.ref}"] = 24.0
        return out + [f"<warn>The mirror clouds: {name} feels a chill and shakes it off.</> {said} "
                      f"<dim>Not again for a day.</>"]
    where = _figure_where(game, fig)
    words, x, y = where
    game.player.explored[max(0, x - 1): x + 2, max(0, y - 1): y + 2] = True
    s = w.settlement_at(x, y)
    if s is not None:
        game.player.known_settlements.add(s.id)
    p = game.player
    away = way_words(x - p.x, y - p.y, "miles") if (x, y) != (p.x, p.y) else "here, close by"
    doing = _doing(game, fig, rng)
    from realmwalker.game import wonders

    return out + [f"<good>{name} is {words}</>, {away}: {doing} {said}", "<dim>(The place is on your map.)</>"] \
        + wonders.scry_extras(game, caster, fig, rng.child("ball"))  # (a crystal ball's thoughts, word, truesight)


def _doing(game, fig, rng) -> str:
    hour = game.moment.hour
    if fig.kind == "dragon":
        return rng.choice(["coiled on a bed of coin, one eye half open.", "stretching great wings in the dark.",
                           "gnawing at the bones of something large."])
    if fig.kind == "beast":
        return rng.choice(["pacing its den.", "asleep among bones.", "tearing at a fresh kill."])
    if hour < 6 or hour >= 22:
        return rng.choice(["asleep, and dreaming of something that makes them frown.", "awake in the dark, thinking."])
    return rng.choice(["at table with others, talking low.", "walking alone, deep in thought.",
                       "at their work, unaware of you.", "arguing with someone you cannot see."])


def _scout_beast(game, caster, spell) -> list[str]:
    beast = _a_beast(game)
    for c in game.party:
        c.effects["forewarned"] = max(float(c.effects.get("forewarned", 0)), 1.0)
    return [f"{_first(caster)} touches {esc(beast)} and looks out through its eyes as it ranges ahead. "
            f"<good>For an hour, a band on the road is seen before it sees you.</>"]


def _a_beast(game) -> str | None:
    for c in game.party:
        for a in getattr(c, "animals", None) or []:
            return a.get("name") or "the animal"
    return None


# ---------------------------------------------------------------------------- Drawmij's Instant Summons
SUMMONS = "summons"  # Character.spells key: {item uid: {"name", "taken": who, "item": the thing as it was taken}}
SUMMONS_TAG = "summons:"  # on the sapphire: the uid of the thing it calls


def _summons_subjects(game, caster) -> list[Subject]:
    bound = set((caster.spells or {}).get(SUMMONS, {}))
    out = []
    for it in caster.inventory:
        d = game.tables.items.get(it.def_id)
        if it.def_id == "sapphire" or float(d.get("weight", 0)) > 10 or str(it.uid) in bound \
                or any(t.startswith(SUMMONS_TAG) for t in it.tags):
            continue
        out.append(Subject(game.tables.items.name(it, False), "item", it.uid))
    out.sort(key=lambda s: -game.tables.items.value(next(i for i in caster.inventory if i.uid == s.ref)))
    return out[:20]


def _bind(game, caster, spell, target) -> list[str]:
    from realmwalker.rules.inventory import add_existing, remove_item
    from realmwalker.rules.items import Item

    it = next((i for i in caster.inventory if i.uid == target.ref), None)
    gem = next((i for i in caster.inventory if i.def_id == "sapphire" and not i.tags), None)
    if it is None or gem is None:
        return ["The spell finds nothing to bind."]
    remove_item(caster, gem.uid, 1)
    name = game.tables.items.name(it, False)
    bound = Item(uid=0, def_id="sapphire", qty=1, made_at=game.world.time, name=f"sapphire bound to the {name}",
                 tags=[f"{SUMMONS_TAG}{it.uid}"])
    add_existing(caster, game.tables.items, bound)
    caster.spells.setdefault(SUMMONS, {})[str(it.uid)] = {"name": name}
    return [f"{_first(caster)} touches the {esc(name)} and the sapphire together: an unseen mark settles on the "
            f"one, and its name glimmers deep in the other. <dim>Crush the sapphire (Enter on it in the pack) to "
            f"call it to your hand.</>"]


def taken(game, items, by: str) -> None:
    """Things bound by Drawmij's Instant Summons have been carried off (robbers, a thief, the watch): remember them
    as they were, so a crushed sapphire can call them back."""
    for c in list(game.party) + list(getattr(game, "waiting", [])):
        rec = (c.spells or {}).get(SUMMONS)
        if not rec:
            continue
        for it in items:
            entry = rec.get(str(it.uid))
            if entry is not None:
                entry["taken"] = by
                entry["item"] = it.to_dict()


def _same(it, d: dict | None) -> bool:
    """Whether a carried thing is the one taken (the party took it back: a new uid, the same thing)."""
    return bool(d) and it.def_id == d.get("def_id") and it.name == d.get("name", "") \
        and int(it.made_at) == int(d.get("made_at", 0)) and it.quality == d.get("quality", "common") \
        and it.magic == (d.get("magic") or {})


def crush(game, char, gem) -> list[str]:
    """Crush a bound sapphire: the thing comes to the hand of whoever bound it."""
    from realmwalker.rules.inventory import add_existing, carried, remove_item
    from realmwalker.rules.items import Item

    uid = next((t[len(SUMMONS_TAG):] for t in gem.tags if t.startswith(SUMMONS_TAG)), None)
    binder = next((c for c in game.party if c.alive and uid in (c.spells or {}).get(SUMMONS, {})), None)
    if uid is None or binder is None:
        return ["Only the one who bound it can call the thing; they are not with you."]
    entry = binder.spells[SUMMONS][uid]
    back = next((it for it in carried(game.party) if str(it.uid) == uid or _same(it, entry.get("item"))), None)
    if back is not None:
        if str(back.uid) != uid:  # (won back from the robbers or the watch: the bond follows it)
            binder.spells[SUMMONS][str(back.uid)] = {"name": entry["name"]}
            del binder.spells[SUMMONS][uid]
            gem.tags = [t for t in gem.tags if not t.startswith(SUMMONS_TAG)] + [f"{SUMMONS_TAG}{back.uid}"]
        return [f"The {esc(entry['name'])} is with you already. The sapphire stays whole."]
    if not entry.get("item"):
        return [f"The {esc(entry['name'])} is in other hands now, given or sold: it will not come. "
                f"The sapphire stays whole."]
    owner = next((c for c in game.party if any(i.uid == gem.uid for i in c.inventory)), char)
    remove_item(owner, gem.uid, 1)
    thing = Item.from_dict(entry["item"])
    thing.uid = 0
    add_existing(binder, game.tables.items, thing)
    del binder.spells[SUMMONS][uid]
    game.cue("spell")
    game.dirty = True
    return [f"{_first(binder)} speaks its name and crushes the sapphire to blue dust: <good>the {esc(entry['name'])} "
            f"is in {_first(binder)}'s hand</>, from wherever the {esc(entry['taken'])} had put it."]


# ---------------------------------------------------------------------------- asking the powers
def muddled(game, caster, sid: str) -> bool:
    """A divination asked again before a long rest: a growing chance of no answer (each casting after the first,
    25% more)."""
    key = f"omen:{sid}"
    n = int(caster.uses.get(key, 0))
    caster.uses[key] = n + 1
    rng = game.world.rng.child(f"omen/{sid}/{game.world.time}")
    return n > 0 and rng.random() < REPEAT_CHANCE * n


def _work_subjects(game) -> list[Subject]:
    from realmwalker.game import quests

    return [Subject(f"the work: {quests.title(game, q)}", "work", q["id"]) for q in quests.active(game)
            if not q["done"]]


def _augury_subjects(game) -> list[Subject]:
    out = []
    lm = game.local
    site = game.world.site_at(game.player.x, game.player.y)
    if lm is not None and lm.kind == "dungeon" and int(lm.meta.get("level", 1)) < int(lm.meta.get("depth", 1)):
        out.append(Subject("going further down", "down"))
    elif lm is None and site is not None:
        out.append(Subject(f"going down into {site.name}", "down"))
    if lm is None:
        out.append(Subject("going on along the road", "road"))
    return out + _work_subjects(game)


def _party_level(game) -> float:
    alive = [c for c in game.party if c.alive]
    return sum(c.level for c in alive) / max(1, len(alive))


def omen(game, subject: Subject) -> str:
    """What waits, truly: "weal", "woe", "both" or "neither"."""
    from realmwalker.game import quests
    from realmwalker.rules import encounter
    from realmwalker.world import dungeon as gen

    w = game.world
    p = game.player
    level = _party_level(game)
    if subject.kind == "down":
        site = w.site_at(p.x, p.y)
        lm = game.local
        if site is None:
            return "neither"
        depth = gen.depth_for(w, site)
        below = int(lm.meta.get("level", 1)) + 1 if lm is not None and lm.kind == "dungeon" else 1
        strength = encounter.land_level(game.tables, int(w.danger[p.x, p.y]), below - 1)
        bottom = below >= depth
        bad = strength > level + 1 or (bottom and strength >= level)
        good = bottom or bool(gen.dragon_at(w, site)) or any(a.get("site") == site.id and not a.get("found")
                                                             for a in w.politics.get("artifacts", []))
        return "both" if bad and good else "woe" if bad else "weal" if good else "neither"
    if subject.kind == "road":
        strength = encounter.danger_level(game.tables, int(w.danger[p.x, p.y]))
        if strength > level + 2:
            return "woe"
        near = any(math.hypot(s.x - p.x, s.y - p.y) <= 3 for s in w.settlements if s.id in p.known_settlements)
        return "weal" if near and strength <= level else "neither"
    q = quests.by_id(game, subject.ref)
    if q is None:
        return "neither"
    harm = bool(q.get("hidden")) and not q.get("revealed")
    good = int(q.get("reward", 0)) > 0
    return "both" if harm and good else "woe" if harm else "weal" if good else "neither"


OMEN_WORDS = {"weal": "<good>Weal.</> The tokens fall bright side up: it will go well.",
              "woe": "<danger>Woe.</> The tokens fall dark: it will go badly.",
              "both": "<warn>Weal and woe.</> The tokens fall half bright, half dark: good will come of it, and harm.",
              "neither": "<dim>Indifference.</> The tokens fall every way: it will be neither good nor ill."}


def _augury(game, caster, spell, target) -> list[str]:
    out = [f"{_first(caster)} casts the tokens and asks of {esc(target.name)}."]
    if muddled(game, caster, "augury"):
        return out + ["<dim>The tokens fall in a heap and mean nothing. Asked too often; rest first.</>"]
    return out + [OMEN_WORDS[omen(game, target)]]


def _work_truth(game, q) -> list[str]:
    """What the powers say of a work: its hidden side, and where its thing or person truly is (it goes on the map)."""
    from realmwalker.game import quests

    w = game.world
    out = []
    if q.get("hidden") and not q.get("revealed"):
        quests.reveal(game, q)
        out.append("<warn>It is not as you were told.</> <dim>(The journal has it.)</>")
    else:
        out.append("<good>It is as you were told.</>")
    t = q["target"]
    p = game.player
    if "site" in t and 0 <= int(t["site"]) < len(w.sites):
        s = w.sites[int(t["site"])]
        if q["template"] == "investigate" and not t.get("clue"):
            t["clue"] = True
            q["journal"].append(f"The trail leads to {s.name}.")
        p.explored[s.x, s.y] = True
        out.append(f"What you seek is at {esc(s.name)}, {way_words(s.x - p.x, s.y - p.y, 'miles')}.")
    elif "dest" in t and 0 <= int(t["dest"]) < len(w.settlements):
        s = w.settlements[int(t["dest"])]
        p.known_settlements.add(s.id)
        out.append(f"The one it concerns is in {esc(s.name)}, {way_words(s.x - p.x, s.y - p.y, 'miles')}.")
    elif q["template"] == "hunt_beast" and "x" in t:
        x, y = int(t["x"]), int(t["y"])
        p.explored[max(0, x - 1): x + 2, max(0, y - 1): y + 2] = True
        out.append(f"The beast keeps to the country {way_words(x - p.x, y - p.y, 'miles')}.")
    return out


def _divination(game, caster, spell, target) -> list[str]:
    from realmwalker.game import quests

    out = [f"{_first(caster)} burns the incense and asks the gods of {esc(target.name)}."]
    if muddled(game, caster, "divination"):
        return out + ["<dim>The smoke curls and says nothing. Asked too often; rest first.</>"]
    q = quests.by_id(game, target.ref)
    if q is None:
        return out + ["<dim>No answer comes.</>"]
    return out + ["<magic>A voice like a far bell answers:</>"] + _work_truth(game, q)


def questions(game) -> list[Subject]:
    """Yes-or-no questions the world can truly answer, the weightiest first (Commune, Contact Other Plane): works in
    hand and their hidden sides, lost treasures, the beasts of the songs, dragons, the living and the dead."""
    from realmwalker.game import quests

    w = game.world
    out = []
    for q in quests.active(game):
        if q["done"]:
            continue
        out.append(Subject(f"Is the work as I was told? ({quests.title(game, q)})", "question", q["id"],
                           data={"ask": "work", "yes": not (q.get("hidden") and not q.get("revealed"))}))
    p = game.player
    arts = [(i, a) for i, a in enumerate(w.politics.get("artifacts", [])) if not a.get("found")
            and 0 <= int(a.get("site", -1)) < len(w.sites)]
    arts.sort(key=lambda ia: math.hypot(w.sites[ia[1]["site"]].x - p.x, w.sites[ia[1]["site"]].y - p.y))
    for i, a in arts[:3]:
        s = w.sites[int(a["site"])]
        out.append(Subject(f"Does {a['name']} lie in {s.name}?", "question", i,
                           data={"ask": "artifact", "yes": True, "site": s.id}))
    for d in w.politics.get("dragons", [])[:3]:
        out.append(Subject(f"Does {d['name']} still live?", "question", d.get("figure"),
                           data={"ask": "dragon", "yes": bool(d.get("alive")), "site": d.get("lair")}))
    for site_id, hid in list(w.politics.get("lairs", {}).items())[:3]:
        fig = w.figures.get(int(hid))
        if fig is not None and 0 <= int(site_id) < len(w.sites):
            out.append(Subject(f"Does {fig.name} still haunt {w.sites[int(site_id)].name}?", "question", int(hid),
                               data={"ask": "lair", "yes": fig.died is None, "site": int(site_id)}))
    for c in getattr(game, "waiting", []):
        out.append(Subject(f"Is {c.name.split()[0]} well?", "question", c.name,
                           data={"ask": "companion", "yes": c.alive and c.hp > c.max_hp // 2}))
    return out


def _answer(game, s: Subject, words: tuple[str, str]) -> str:
    """Say a question's answer and do what knowing it does (a place goes on the map, a hidden side is written down)."""
    from realmwalker.game import quests

    w = game.world
    yes = bool(s.data.get("yes"))
    if s.data.get("ask") == "work" and not yes:
        q = quests.by_id(game, s.ref)
        if q is not None:
            quests.reveal(game, q)
    site = s.data.get("site")
    if yes and site is not None and 0 <= int(site) < len(w.sites):
        x, y = w.sites[int(site)].x, w.sites[int(site)].y
        game.player.explored[x, y] = True
    return f"{esc(s.name)} <magic>{words[0] if yes else words[1]}</>"


def _commune(game, caster, spell, target, how: str) -> list[str]:
    rng = game.world.rng.child(f"commune/{how}/{game.world.time}")
    n = int(_road(spell).get("questions", 3))
    first = _first(caster)
    out = [f"{first} kneels and calls on the god." if how == "commune" else
           f"{first} lets the mind slip loose of the world and calls to something beyond it."]
    sid = "commune" if how == "commune" else "contact_other_plane"
    if how == "other_plane":
        from realmwalker.game.magic import strain_on_road

        sheet = game.sheet(caster)
        roll = dice.d20(rng).natural
        bonus = sheet.save_bonus("int")
        said = f"<dim>(Intelligence save {roll} {bonus:+d} = {roll + bonus} vs DC {OTHER_PLANE_DC})</>"
        if roll + bonus < OTHER_PLANE_DC:
            hurt = dice.roll("6d6", rng).total
            caster.uses["addled"] = 1
            return out + [f"<danger>What answers is too vast: {first} reels from it.</> {said}"] + \
                strain_on_road(game, caster, hurt, f"<danger>It burns through {first}'s mind: {hurt} psychic.</>") \
                + [f"<warn>{first} sits senseless, staring, and will be no use until a long rest.</>"]
        out.append(f"Something answers. {said}")
    if muddled(game, caster, sid):
        return out + ["<dim>No answer comes. Asked too often; rest first.</>"]
    pool = questions(game)
    if not pool:
        return out + ["<dim>You have nothing to ask that the powers would answer.</>"]
    chosen = [target] if target is not None and target.kind == "question" else []
    chosen += [q for q in pool if q.name not in {c.name for c in chosen}][: n - len(chosen)]
    for s in chosen:
        if how == "other_plane" and rng.random() < 1 / 6:
            out.append(f"{esc(s.name)} <dim>Unclear.</>")
        else:
            out.append(_answer(game, s, ("Yes.", "No.")))
    return out


def _nature(game, caster, spell) -> list[str]:
    from realmwalker.game import camp

    w = game.world
    p = game.player
    first = _first(caster)
    lm = game.local
    if lm is not None and lm.kind == "dungeon":
        reach = _flood(game, lm)
        near = np.zeros(reach.shape, dtype=bool)
        x0, x1 = max(0, p.lx - 60), min(lm.width, p.lx + 61)
        y0, y1 = max(0, p.ly - 60), min(lm.height, p.ly + 61)
        near[x0:x1, y0:y1] = True
        lm.seen |= reach & near
        bands = _bands_in(lm, reach & near)
        out = [f"{first} lays both hands on the rock and listens: the cave tells of itself for 300 feet round."]
        if bands:
            worst = max(bands, key=lambda a: max(float(game.tables.creatures[c.def_id].get("cr", 0))
                                                  for c in a.creatures))
            out.append(f"<warn>The worst thing in it: {_band_words(game, worst)}, "
                       f"{way_words(worst.x - p.lx, worst.y - p.ly)}.</>")
        return out + ["<good>The passages near are on your map.</>"]
    out = [f"{first} sits on the bare ground and lets the spirits of the land speak."]
    found = []
    for s in w.settlements:
        if math.hypot(s.x - p.x, s.y - p.y) <= 1.5 and (s.x, s.y) != (p.x, p.y):
            p.known_settlements.add(s.id)
            p.explored[s.x, s.y] = True
            found.append(f"{esc(s.name)} {way_words(s.x - p.x, s.y - p.y, 'miles')}")
    for site in w.sites:
        if math.hypot(site.x - p.x, site.y - p.y) <= 1.5:
            p.explored[site.x, site.y] = True
            found.append(f"{esc(site.name)} {way_words(site.x - p.x, site.y - p.y, 'miles')}")
    out.append("Places: " + ("; ".join(found) + "." if found else "none within three miles but this one."))
    water = _water_near(game)
    out.append(f"Water: {water}." if water else "Water: none above the ground within three miles.")
    hunt = camp.by_land(game, game.tables.camping["hunt"])
    forage = camp.by_land(game, game.tables.camping["forage"])
    if hunt or forage:
        bits = []
        if hunt:
            bits.append(f"the game is mostly {hunt['game'][0][0]}")
        if forage:
            bits.append(f"{game.tables.items.get(forage['find'][0][0])['name']} grows thick")
        out.append(f"<good>{'; '.join(bits).capitalize()}.</> <dim>(+5 to hunt and forage here for a while.)</>")
        for c in game.party:
            c.effects["hunting_tip"] = max(float(c.effects.get("hunting_tip", 0)), TIP_HOURS)
            c.effects["forage_tip"] = max(float(c.effects.get("forage_tip", 0)), TIP_HOURS)
    strong = _strong_near(game)
    if strong:
        out.append(f"<warn>{strong}</>")
    return out


def _water_near(game) -> str:
    w = game.world
    p = game.player
    names = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = p.x + dx, p.y + dy
            if not (0 <= x < w.width and 0 <= y < w.height):
                continue
            area = w.area_at(x, y)
            wet = bool(w.river[x, y]) or game.biome_key(x, y) in ("lake", "ocean", "sea", "marsh", "deep_ocean")
            if wet:
                name = area.name if area is not None and area.kind in ("river", "lake", "ocean", "marsh") else "water"
                if name not in names:
                    names.append(name)
    return ", ".join(esc(n) for n in names[:3])


def _strong_near(game) -> str:
    """The most powerful creature near (Commune with Nature: a celestial, elemental, fey, fiend or undead of CR 10 or
    more; the beasts and dragons of the songs are the land's great ones here)."""
    w = game.world
    p = game.player
    for d in w.politics.get("dragons", []):
        lair = d.get("lair")
        if d.get("alive") and lair is not None and 0 <= int(lair) < len(w.sites):
            s = w.sites[int(lair)]
            if math.hypot(s.x - p.x, s.y - p.y) <= 1.5:
                p.explored[s.x, s.y] = True
                return f"A dragon, {esc(d['name'])}, lairs at {esc(s.name)}."
    for site_id, hid in w.politics.get("lairs", {}).items():
        fig = w.figures.get(int(hid))
        if fig is None or fig.died is not None or not 0 <= int(site_id) < len(w.sites):
            continue
        s = w.sites[int(site_id)]
        if math.hypot(s.x - p.x, s.y - p.y) <= 1.5:
            p.explored[s.x, s.y] = True
            return f"{esc(fig.name)} lairs at {esc(s.name)}."
    return ""


def _lore_subjects(game, caster) -> list[Subject]:
    from realmwalker.rules.inventory import carried

    w = game.world
    p = game.player
    out = []
    for it in carried(game.party):
        if it.magic and (it.magic.get("story") or it.magic.get("title") or it.magic.get("artifact")):
            out.append(Subject(game.tables.items.name(it, False), "carried", it.uid))
    arts = [(i, a) for i, a in enumerate(w.politics.get("artifacts", [])) if not a.get("found")]
    for i, a in arts[:8]:
        out.append(Subject(a["name"], "artifact", i))
    for site_id, hid in list(w.politics.get("lairs", {}).items())[:6]:
        fig = w.figures.get(int(hid))
        if fig is not None and fig.died is None:
            out.append(Subject(fig.name, "beast", int(hid), data={"site": int(site_id)}))
    site = w.site_at(p.x, p.y)
    if site is not None:
        out.append(Subject(site.name, "site", site.id))
    return out


def _lore(game, caster, spell, target) -> list[str]:
    from realmwalker.game import magic_items, past
    from realmwalker.rules.inventory import carried
    from realmwalker.world import dungeon as gen

    w = game.world
    p = game.player
    out = [f"{_first(caster)} burns the incense over the ivory strips and speaks the name: {esc(target.name)}."]
    if target.kind == "carried":
        it = next((i for i in carried(game.party) if i.uid == target.ref), None)
        if it is None:
            return out + ["<dim>Nothing comes.</>"]
        out += magic_items.identify(game, it)
        if it.magic.get("cursed"):
            out.append(f"<danger>A curse is bound into it.</> {esc(it.magic.get('curse', {}).get('text', ''))}".strip())
        if it.magic.get("story"):
            out.append(f"<dim>{esc(it.magic['story'])}</>")
        return out
    if target.kind == "artifact":
        a = w.politics["artifacts"][target.ref]
        out.append(f"<magic>{esc(a['name'][:1].upper() + a['name'][1:])}</> {esc(a.get('fate', 'was lost long ago'))}.")
        site = int(a.get("site", -1))
        if 0 <= site < len(w.sites):
            s = w.sites[site]
            p.explored[s.x, s.y] = True
            out.append(f"<good>It lies at the bottom of {esc(s.name)}, {way_words(s.x - p.x, s.y - p.y, 'miles')}, "
                       f"in a chest that has not been opened since.</> <dim>(The place is on your map.)</>")
        elif str(a.get("place", ""))[:1] == "S" and str(a["place"])[1:].isdigit():
            s = w.settlements[int(a["place"][1:])]
            p.known_settlements.add(s.id)
            out.append(f"Its trail ends in {esc(s.name)}, {way_words(s.x - p.x, s.y - p.y, 'miles')}.")
        return out
    if target.kind == "beast":
        fig = w.figures[target.ref]
        s = w.sites[int(target.data["site"])]
        p.explored[s.x, s.y] = True
        out.append(f"<magic>{esc(fig.name)}</> lairs at {esc(s.name)}, {way_words(s.x - p.x, s.y - p.y, 'miles')}"
                   + (f", and has killed {len(fig.kills)} whose names are remembered." if fig.kills else "."))
        group, _ = past.boss_for(game, s, None)
        harm = _what_harms(game, group)
        if harm:
            out.append(f"<good>{harm}</>")
        return out
    site = w.sites[target.ref]
    depth = gen.depth_for(w, site)
    group, name = past.boss_for(game, site, None)
    master = esc(name) if name else (esc(game.tables.creatures.encounters.get(group or "", {}).get("name", ""))
                                     or "nothing that has a name")
    out.append(f"<magic>{esc(site.name)}</> goes down {depth} level{'s' if depth != 1 else ''}; at the bottom waits "
               f"{master}.")
    lying = past.artifacts_lying_at(game, site)
    if lying:
        n = esc(w.politics["artifacts"][lying[0]]["name"])
        out.append(f"<good>{n[:1].upper() + n[1:]} lies there still.</>")
    return out


def _what_harms(game, group: str | None) -> str:
    """A beast's weakness, from its stat block: what it is vulnerable to, or what it does not resist."""
    if not group or group not in game.tables.creatures.encounters:
        return ""
    members = game.tables.creatures.encounters[group].get("members") or []
    cid = members[0][0] if members and isinstance(members[0], (list, tuple)) else (members[0] if members else None)
    if not cid or cid not in game.tables.creatures:
        return ""
    d = game.tables.creatures[cid]
    vuln = d.get("vulnerable") or d.get("vulnerabilities") or []
    if vuln:
        return f"It fears {', '.join(vuln)} above all."
    resist = set(d.get("resist") or d.get("resistances") or []) | set(d.get("immune") or [])
    if resist:
        return f"Do not trust to {', '.join(sorted(resist))}: it shrugs that off."
    return ""


# ---------------------------------------------------------------------------- the door
def subjects(game, caster, sid: str) -> list[Subject]:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does = o.get("does")
    if does == "locate":
        return {"object": _object_subjects, "creature": _creature_subjects,
                "nature": _nature_subjects}[o["what"]](game)
    if does == "scout" and o.get("how") == "scry":
        return [s for s in _figure_subjects(game) if caster.effects.get(f"scry_block:{s.ref}", 0) <= 0]
    if does == "summons":
        return _summons_subjects(game, caster)
    if does == "ask":
        how = o.get("how")
        if how == "augury":
            return _augury_subjects(game)
        if how == "divination":
            return _work_subjects(game)
        if how in ("commune", "other_plane"):
            return questions(game)
        if how == "lore":
            return _lore_subjects(game, caster)
    return []


def problem(game, caster, sid: str, target) -> str | None:
    """Why this spell would do nothing here and now (None when it would)."""
    spell = game.tables.spells[sid]
    o = _road(spell)
    does, lm = o.get("does"), game.local
    if caster.uses.get("addled"):
        return "the mind is still reeling from what it touched (a long rest)"
    aimed = not isinstance(target, Character)
    if does == "sense" and o.get("what") == "traps" and (lm is None or lm.kind != "dungeon"):
        return "there are no traps to find out here"
    if does == "locate":
        if o["what"] == "nature" and game.world.settlement_at(game.player.x, game.player.y) is not None:
            return "nothing wild grows or runs in a town"
        if o["what"] == "nature" and lm is not None and lm.kind == "dungeon":
            return "not under the ground"
        if not subjects(game, caster, sid):
            return "there is nothing you know of within 1,000 feet to seek" if o["what"] != "nature" else "nothing"
        if not aimed:
            return "choose what to seek (←→)"
    if does == "scout":
        how = o.get("how")
        if how in ("room", "level") and (lm is None or lm.kind != "dungeon"):
            return "only under the ground, where doors and corners hide the way"
        if how == "scry" and not subjects(game, caster, sid):
            return "you know of nobody in the world to look for"
        if how == "scry" and not aimed:
            return "choose who to look for (←→)"
        if how == "beast" and _a_beast(game) is None:
            return "you have no animal to look through"
        if how == "beast" and lm is not None:
            return "only on the road"
    if does == "summons":
        if not any(i.def_id == "sapphire" and not i.tags for i in caster.inventory):
            return "needs an unbound sapphire worth 1,000+ GP"
        if not subjects(game, caster, sid):
            return "nothing you carry is small enough to bind"
        if not aimed:
            return "choose the thing to bind (←→)"
    if does == "ask":
        how = o.get("how")
        if how == "augury" and not subjects(game, caster, sid):
            return "you have nothing in mind to ask about"
        if how == "divination" and not subjects(game, caster, sid):
            return "you have no work in hand to ask about"
        if how == "lore" and not subjects(game, caster, sid):
            return "nothing famous comes to mind to ask about"
        if how in ("augury", "divination", "lore") and not aimed:
            return "choose what to ask about (←→)"
        if how == "nature":
            if lm is not None and lm.kind == "settlement" or \
                    game.world.settlement_at(game.player.x, game.player.y) is not None:
                return "not among buildings: nature has been walled out of a town"
            if lm is not None and lm.kind == "dungeon" and lm.meta.get("style") != "cave":
                return "these halls were built: nature has been walled out of them"
    return None


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    """Do what the spell does (its slot and materials spent; the caller passes its casting time)."""
    spell = game.tables.spells[sid]
    o = _road(spell)
    does = o["does"]
    if isinstance(target, Character):
        target = None
    if does == "sense":
        return {"magic": _sense_magic, "evil": _sense_evil, "poison": _sense_poison,
                "traps": _sense_traps}[o["what"]](game, caster, spell)
    if does == "locate":
        return _locate(game, caster, spell, target, o["what"])
    if does == "scout":
        how = o["how"]
        if how == "room":
            return _scout_rooms(game, caster, spell)
        if how == "level":
            return _scout_level(game, caster, spell)
        if how == "scry":
            return _scry(game, caster, spell, target, level)
        return _scout_beast(game, caster, spell)
    if does == "summons":
        return _bind(game, caster, spell, target)
    how = o["how"]
    if how == "augury":
        return _augury(game, caster, spell, target)
    if how == "divination":
        return _divination(game, caster, spell, target)
    if how in ("commune", "other_plane"):
        return _commune(game, caster, spell, target, how)
    if how == "nature":
        return _nature(game, caster, spell)
    return _lore(game, caster, spell, target)
