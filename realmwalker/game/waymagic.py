"""Magic for the road (Expansion 3 E.2): travel by magic, and what the body's lasting spells do in the world.

Travel (a spell's op {"op": "road", "does": "travel", "how": ...}; rules/spells.TRAVELS): the Spells page lists the
places it can reach (`places`), and `travel` takes the party there.
- teleport (Teleport): any town known. How well it is known decides the arrival, by the 2024 table (`TABLE`): a city
  visited is a permanent circle whose sigils are known (always on target), the town the character comes from is very
  familiar, a town visited was seen casually, a town only heard of was viewed once or described. A mishap does 3d10
  force to each and rolls again; a similar place is the nearest town of the same kind; off target lands 2d12 miles
  away in one of eight directions.
- circle (Teleportation Circle): to a city visited (its circle's sigils learned there), always on target.
- recall (Word of Recall): cast standing in a temple, it makes that town the sanctuary (`SANCTUARY` in the caster's
  effects); cast anywhere after, it takes the caster and five more back to it.
- plants (Transport via Plants): from woodland to a town visited that has woodland beside it.
- shift, astral, gate_far (Plane Shift, Astral Projection, Gate): until the planes come (Expansion 26), the way out of
  the world and back in: Plane Shift arrives at a city's circle known, or somewhere near any other known town (off
  target); Astral Projection and Gate arrive where they were aimed, at any known town. Astral Projection spends a
  jacinth and a silver bar of 100 GP (four bars of 25) for each traveller.
- gate (Arcane Gate): under the ground, a gate to the stairs up or down within 500 feet.

The body's lasting spells (rules/spells.lasting; keys in rules/engine/marks.py) read here and in game/state.py,
game/vision.py, game/dungeon.py and game/encounters.py: `everyone` and `anyone` ask the party.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup
from realmwalker.rules import spells as spellrules

SANCTUARY = "recall_sanctuary"  # in the caster's effects: the settlement id + 1 of Word of Recall's sanctuary
CARRIES = {"teleport": 9, "recall": 6, "shift": 9, "astral": 9}  # the caster and up to eight (five) more
GATE_REACH = 100  # squares: Arcane Gate's 500 feet
# The 2024 Teleportation Outcome table: the highest d100 roll of each outcome, by familiarity (PHB p. 334).
TABLE = {"circle": [("on", 100)],
         "very": [("mishap", 5), ("similar", 13), ("off", 24), ("on", 100)],
         "casual": [("mishap", 33), ("similar", 43), ("off", 53), ("on", 100)],
         "once": [("mishap", 43), ("similar", 53), ("off", 73), ("on", 100)]}
FAMILIARITY = {"circle": "a permanent circle whose sigils you know", "very": "very familiar",
               "casual": "seen casually", "once": "viewed once or described"}


@dataclass
class Place:
    """Somewhere a travel spell can go: a town (with how well it is known), or the stairs of a dungeon level."""
    name: str
    kind: str  # "town" or "stairs"
    sid: int = -1  # the settlement
    known: str = "casual"  # familiarity (TABLE)
    x: int = 0
    y: int = 0
    alive: bool = True  # (read by the Spells page as it would be for a person)


def _first(c) -> str:
    return escape_markup(c.name.split()[0])


def _how(spell: dict) -> str:
    return (spellrules.op(spell, "road") or {}).get("how", "")


# ---------------------------------------------------------------------------- the party's lasting spells
def everyone(game, key: str) -> bool:
    """Every living member of the party has a lasting spell giving `key` (Water Walk, Wind Walk, Etherealness)."""
    alive = [c for c in game.party if c.alive]
    return bool(alive) and all(spellrules.lasting_flag(c, game.tables, key) for c in alive)


def anyone(game, key: str) -> bool:
    return any(c.alive and spellrules.lasting_flag(c, game.tables, key) for c in game.party)


def spell_light(game) -> int:
    """Squares of light the party's lasting spells shed (Light, Daylight), or carried everburning flames: the
    radius seen by it, bright and dim together (a torch's 20 and 20 feet are six squares)."""
    bright = max([0] + [spellrules.lasting_number(c, game.tables, "light") for c in game.party if c.alive])
    out = (bright * 3 + 1) // 2 if bright else 0
    items = game.tables.items
    for c in game.party:
        if c.alive:
            for it in c.inventory:
                light = items.get(it.def_id).get("light") or {}
                if light.get("everburning"):
                    out = max(out, int(light.get("radius", 6)))
    return out


# ---------------------------------------------------------------------------- where it can go
def _knowledge(game, s) -> str | None:
    """How well the party knows a settlement, for Teleport: None when it does not know it at all."""
    p = game.player
    visited = s.id in p.visited_settlements
    if visited and (s.kind == "city" or s.great):
        return "circle"  # (a city's temple keeps a permanent circle; its sigils were learned there)
    if s.id == getattr(p, "home", None):
        return "very"
    if visited:
        return "casual"
    if s.id in p.known_settlements:
        return "once"
    return None


def _towns(game, keep) -> list[Place]:
    here = game.world.settlement_at(game.player.x, game.player.y)
    out = []
    for s in game.world.settlements:
        if here is not None and s.id == here.id:
            continue
        known = _knowledge(game, s)
        if known is None or not keep(s, known):
            continue
        out.append(Place(s.name, "town", s.id, known, s.x, s.y))
    px, py = game.player.x, game.player.y
    return sorted(out, key=lambda pl: math.hypot(pl.x - px, pl.y - py))[:40]


def woodland(game, x: int, y: int) -> bool:
    """A great tree to step into: woodland here or on a tile beside."""
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if game.world.in_bounds(x + dx, y + dy):
                key = game.biome_key(x + dx, y + dy)
                if "forest" in key or "wood" in key or "jungle" in key or "taiga" in key:
                    return True
    return False


def _stairs(game) -> list[Place]:
    lm = game.local
    if lm is None or lm.kind != "dungeon":
        return []
    p = game.player
    out = []
    for name, tid in (("the stairs up", "stairs_up"), ("the stairs down", "stairs_down")):
        if tid not in lm.terrain_ids:
            continue
        idx = lm.terrain_ids.index(tid)
        import numpy as np

        xs, ys = np.nonzero(lm.terrain == idx)
        for x, y in zip(xs.tolist(), ys.tolist()):
            if max(abs(x - p.lx), abs(y - p.ly)) <= GATE_REACH and (x, y) != (p.lx, p.ly):
                out.append(Place(name, "stairs", -1, "on", x, y))
                break
    return out


def places(game, caster, sid: str) -> list[Place]:
    """Where a travel spell could take the party from here."""
    how = _how(game.tables.spells[sid])
    if how == "gate":
        return _stairs(game)
    if how == "circle":
        return _towns(game, lambda s, known: known == "circle")
    if how == "plants":
        return _towns(game, lambda s, known: s.id in game.player.visited_settlements and woodland(game, s.x, s.y))
    if how in ("teleport", "shift", "astral", "gate_far"):
        return _towns(game, lambda s, known: True)
    return []  # (recall: no choice, the sanctuary)


def sanctuary(game, caster):
    v = caster.effects.get(SANCTUARY)
    if not v:
        return None
    sid = int(v) - 1
    return game.world.settlements[sid] if 0 <= sid < len(game.world.settlements) else None


def in_a_temple(game) -> bool:
    from realmwalker.game.law import _in_a_temple

    return _in_a_temple(game)


# ---------------------------------------------------------------------------- can it be cast here?
def problem(game, caster, sid: str, target) -> str | None:
    spell = game.tables.spells[sid]
    how = _how(spell)
    if game.battle is not None:
        return "you are in a fight"
    travellers = [c for c in game.party if c.alive]
    if how in CARRIES and len(travellers) > CARRIES[how]:
        return f"it carries {CARRIES[how]} at most, and you are {len(travellers)}"
    if how == "recall":
        if in_a_temple(game):
            return None  # (it makes this temple the sanctuary)
        home = sanctuary(game, caster)
        if home is None:
            return "no sanctuary yet: cast it once standing in a temple to make it yours"
        here = game.world.settlement_at(game.player.x, game.player.y)
        return "you are at your sanctuary already" if here is not None and here.id == home.id else None
    if how == "gate":
        if game.local is None or game.local.kind != "dungeon":
            return "only under the ground, to stairs within 500 feet"
        return None if _stairs(game) else "no stairs within 500 feet"
    if how == "plants" and not woodland(game, game.player.x, game.player.y):
        return "there is no great tree here to step into"
    if how == "astral":
        need = len(travellers)
        jac = _count(game, "jacinth")
        silver = _count(game, "silver_bar")
        if jac < need or silver < 4 * need:
            return (f"it needs a jacinth and a silver bar of 100 GP (four bars) for each of you: {need} jacinth and "
                    f"{4 * need} bars")
    if not places(game, caster, sid):
        return {"circle": "you know no city's circle yet: visit a city to learn its sigils",
                "plants": "you have seen no tree near a town you have been to"}.get(how, "you know nowhere to go")
    if target is not None and not isinstance(target, Place):
        return None  # (the Spells page aims at the first place until one is chosen)
    return None


def _count(game, def_id: str) -> int:
    return sum(it.qty for c in game.party for it in c.inventory if it.def_id == def_id)


def _spend(game, def_id: str, n: int) -> None:
    from realmwalker.rules.inventory import remove_item

    for c in game.party:
        for it in list(c.inventory):
            if n <= 0:
                return
            if it.def_id == def_id:
                take = min(n, it.qty)
                remove_item(c, it.uid, take)
                n -= take


# ---------------------------------------------------------------------------- going
def _roll(game, known: str, rng) -> str:
    r = rng.randint(1, 100)
    for outcome, top in TABLE[known]:
        if r <= top:
            return outcome
    return "on"


def _similar(game, sid: int):
    """The nearest other town of the same kind as the one aimed at."""
    w = game.world
    aim = w.settlements[sid]
    alike = [s for s in w.settlements if s.kind == aim.kind and s.id != aim.id]
    return min(alike, key=lambda s: math.hypot(s.x - aim.x, s.y - aim.y)) if alike else aim


def _off(game, x: int, y: int, rng) -> tuple[int, int, int]:
    """2d12 miles from (x, y) in one of eight directions (1 east ... 8 northeast), on land that can be walked."""
    from realmwalker.game.state import MILES_PER_TILE

    miles = dice.roll("2d12", rng).total
    dx, dy = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)][rng.randint(0, 7)]
    n = max(1, round(miles / MILES_PER_TILE))
    w = game.world
    for step in range(n, -1, -1):  # (the nearest dry land on the way back, if it would be water)
        tx, ty = x + dx * step, y + dy * step
        if w.in_bounds(tx, ty) and game.biome_def(tx, ty)["passable"]:
            return tx, ty, miles
    return x, y, 0


def _hurt(game, rng) -> list[str]:
    """A mishap: 3d10 force to each traveller (down, not dead, at 0: as after a trap)."""
    out = []
    for c in game.party:
        if not c.alive:
            continue
        dmg = dice.roll("3d10", rng).total
        c.hp -= dmg
        out.append(f"<danger>{_first(c)} is wrenched by the spell: {dmg} force.</>")
        if c.hp <= 0:
            if -c.hp >= c.max_hp:
                c.hp = 0
                c.death_cause = "torn apart by a teleport gone wrong"
                from realmwalker.game import survival

                survival.check_death(game, c)
            else:
                c.hp = 1
                from realmwalker.game.fight import lie_senseless

                out.append(lie_senseless(game, 1))
    return out


def _arrive(game, x: int, y: int) -> None:
    """Set the party down at (x, y) on the big map, as the coaches do (out of a dungeon too: magic needs no stairs)."""
    if game.in_local:
        if game.local is not None and game.local.kind == "dungeon":
            game.player.local_key = None  # (leave_local would send you to the stairs first)
            game.sneaking = False
            game.dirty = True
        else:
            game.leave_local()
    p = game.player
    prev = game.world.area_at(p.x, p.y)
    p.x, p.y = x, y
    game.travel = None
    game.camp = None
    game.reveal()
    game._arrive(prev)


def travel(game, caster, sid: str, target, level: int) -> list[str]:
    """Go (the slot and materials already spent; the casting time is passed by the caller)."""
    spell = game.tables.spells[sid]
    how = _how(spell)
    rng = game.world.rng.child(f"waymagic/{sid}/{game.world.time}")
    first = _first(caster)
    if how == "recall" and in_a_temple(game):
        here = game.world.settlement_at(game.player.x, game.player.y)
        caster.effects[SANCTUARY] = float(here.id + 1)
        return [f"{first} kneels before the altar and speaks the word: this temple of {escape_markup(here.name)} is "
                f"now {first}'s sanctuary. <dim>Cast again anywhere, Word of Recall brings you back here.</>"]
    if how == "recall":
        home = sanctuary(game, caster)
        _arrive(game, home.x, home.y)
        return [f"{first} speaks a single word, and the world folds: you stand in the temple of "
                f"{escape_markup(home.name)}, the sanctuary."]
    if how == "gate":
        place = target if isinstance(target, Place) else _stairs(game)[0]
        p = game.player
        p.lx, p.ly = place.x, place.y
        game.local.seen[max(0, p.lx - 3):p.lx + 4, max(0, p.ly - 3):p.ly + 4] = True
        return [f"Two rings of light open, one beside {first} and one at {place.name}; the party steps through the "
                f"mist between them. <dim>Step onto the stairs to take them.</>"]
    choices = places(game, caster, sid)
    place = target if isinstance(target, Place) and any(c.sid == target.sid for c in choices) else choices[0]
    aim = game.world.settlements[place.sid]
    if how == "astral":
        n = len([c for c in game.party if c.alive])
        _spend(game, "jacinth", n)
        _spend(game, "silver_bar", 4 * n)
    words = {"teleport": f"{first} speaks one word, and the world goes white.",
             "circle": f"{first} draws a circle of shimmering sigils on the ground; a portal opens in it, and you step "
                       f"through into the permanent circle of {escape_markup(aim.name)}.",
             "plants": f"{first} lays a hand on a great tree and it opens like a door; you step into green dark and "
                       f"out of a tree in the woods by {escape_markup(aim.name)}.",
             "shift": "Hand in hand in a ring, you step out of the world into a roaring sky of colour, and back in.",
             "astral": "Your spirits rise out of your sleeping bodies on silver cords, cross the silver sea of the "
                       "Astral, and come down where you willed: your bodies are drawn after you.",
             "gate_far": f"A ring of fire opens in the air; through it you see {escape_markup(aim.name)}. You step "
                         f"through, and it closes behind you."}
    out = [words.get(how, words["teleport"])]
    if how == "teleport":
        known = place.known
        out.append(f"<dim>{escape_markup(aim.name)}: {FAMILIARITY[known]}.</>")
        for _ in range(6):
            result = _roll(game, known, rng)
            if result != "mishap":
                break
            out.append("<danger>Something goes wrong in the between.</>")
            out += _hurt(game, rng)
            if game.over is not None or not game.leader.alive:
                return out
        else:
            result = "off"
        if result == "similar":
            aim = _similar(game, aim.id)
            out.append(f"<warn>You come out in {escape_markup(aim.name)}: like the place you meant, but not it.</>")
            _arrive(game, aim.x, aim.y)
            return out
        if result == "off":
            x, y, miles = _off(game, aim.x, aim.y, rng)
            _arrive(game, x, y)
            out.append(f"<warn>You come out in open country, {miles} miles from {escape_markup(aim.name)}.</>")
            return out
        _arrive(game, aim.x, aim.y)
        out.append(f"<good>You stand at {escape_markup(aim.name)}.</>")
        return out
    if how == "shift" and place.known != "circle":
        x, y, miles = _off(game, aim.x, aim.y, rng)
        _arrive(game, x, y)
        out.append(f"<warn>You come down in open country, {miles} miles from {escape_markup(aim.name)}: without a "
                   f"circle's sigils the way back in is never sure.</>")
        return out
    _arrive(game, aim.x, aim.y)
    if how != "circle":
        out.append(f"<good>You stand at {escape_markup(aim.name)}.</>")
    return out


# ---------------------------------------------------------------------------- lasting spells as they are cast
def after_lasting(game, caster, sid: str, who: list) -> list[str]:
    """What a lasting spell does in the world as it is cast outside a fight (its "outside"): Alter Self changes the
    caster's face (a disguise no watchman sees through), Find the Path shows the way to a dungeon level's stairs."""
    spell = game.tables.spells[sid]
    what = spell.get("outside")
    if what == "disguise" and caster is game.leader:
        game.renown.flags["disguise_dc"] = max(int(game.renown.flags.get("disguise_dc", 0)), 30)
        caster.effects["disguised"] = max(float(caster.effects.get("disguised", 0)),
                                          int(spell.get("rounds", 600)) / spellrules.ROUNDS_PER_HOUR)
        return ["<good>Your own face changes under your hands: nobody who knows it would know you now.</>"]
    if what == "path":
        return show_the_way(game)
    return []


def show_the_way(game) -> list[str]:
    """Find the Path under the ground: the way from here to the stairs down (up, from the deepest level) is shown."""
    lm = game.local
    if lm is None or lm.kind != "dungeon":
        return ["<dim>Wherever you go today, you will know the most direct way there.</>"]
    import numpy as np
    import tcod

    want = "stairs_down" if "stairs_down" in lm.terrain_ids and (lm.terrain == lm.terrain_ids.index("stairs_down")).any() \
        else "stairs_up"
    idx = lm.terrain_ids.index(want)
    xs, ys = np.nonzero(lm.terrain == idx)
    if not len(xs):
        return []
    T = game.tables.terrain
    ids = game.remap_for(lm)[lm.terrain]
    doors = np.array([tid.startswith("door") for tid in T.ids], dtype=bool)
    walk = (T.walk[ids] | doors[ids]).astype(np.int8)
    graph = tcod.path.SimpleGraph(cost=walk, cardinal=2, diagonal=3)
    pf = tcod.path.Pathfinder(graph)
    pf.add_root((game.player.lx, game.player.ly))
    route = pf.path_to((int(xs[0]), int(ys[0]))).tolist()
    for x, y in route:
        lm.seen[max(0, x - 1):x + 2, max(0, y - 1):y + 2] = True
    where = "down" if want == "stairs_down" else "up"
    return [f"<good>The way to the stairs {where} is clear in your mind: {len(route)} steps.</> <dim>It is marked "
            f"on the map.</>"]


def ashore(game) -> str:
    """The spell that kept the party on (or under) the water, or in the air over it, has ended out there: everyone
    swims for the nearest shore, an hour of it, soaked and spent. Returns what to say ("" when on dry land)."""
    p = game.player
    if game.in_local or game.biome_def(p.x, p.y)["passable"] or game.magic_crossing(p.x, p.y) is not None:
        return ""
    w = game.world
    best = None
    for r in range(1, 12):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                x, y = p.x + dx, p.y + dy
                if max(abs(dx), abs(dy)) == r and w.in_bounds(x, y) and game.biome_def(x, y)["passable"]:
                    best = (x, y)
                    break
            if best:
                break
        if best:
            break
    if best is None:
        return ""
    p.x, p.y = best
    game._wading = True
    for c in game.party:
        if c.alive:
            c.fatigue = min(100.0, c.fatigue + 25.0)
    game.pass_time(60, "walk")
    game.reveal()
    return ("<danger>The spell gives out beneath you, and you are in the water.</> You swim for the nearest shore and "
            "drag yourselves out, soaked and spent.")


def ethereal_here(game) -> bool:
    """The whole party walks the Border Ethereal (Etherealness): walls and doors do not stop it, traps do not
    spring, and nothing on this side can be touched."""
    return bool(game.party) and everyone(game, "ethereal")


def shunted(game) -> str:
    """Back from the Border Ethereal inside something solid: shunted to the nearest open space, with force damage
    of twice the feet moved (2024)."""
    lm = game.local
    if lm is None:
        return ""
    T = game.tables.terrain
    remap = game.remap_for(lm)
    p = game.player
    if T.walk[int(remap[lm.terrain[p.lx, p.ly]])] or ethereal_here(game):
        return ""
    for r in range(1, 30):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                x, y = p.lx + dx, p.ly + dy
                if max(abs(dx), abs(dy)) == r and lm.in_bounds(x, y) and T.walk[int(remap[lm.terrain[x, y]])]:
                    p.lx, p.ly = x, y
                    feet = 5 * r
                    for c in game.party:
                        if c.alive:
                            c.hp = max(1, c.hp - 2 * feet)
                    return (f"<danger>The grey fades and you are inside the stone: it spits you out {feet} feet "
                            f"away.</> Everyone takes {2 * feet} force.")
    return ""
