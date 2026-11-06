"""A threat's signs in play (Expansion 6 G.1, docs/ADVENTURES.md §5.1, §5.19): every stage of a threat's scheme shows
itself the ways threats.json says, besides the news its signs make (world/threats._sign) and the marks its effects
leave (threats.STAGE_OPS, drawn on the world map by ui/gfx/mapsigns.py and stamped on the town's map by
game/placemarks.py):

- the land: a stage's `flavour`, a line now and then as you walk the country in its reach (only with the world's
  voice on: `GameState.flavour`), from `on_the_land` after each step on the overworld;
- the streets: its `barks`, said in passing by the people of the towns it threatens (`bark`, from
  townlife._words_for);
- the road: its `overlay`, a line after the words of an ordinary meeting with people who mean no harm in its reach
  once its effects have come (`overlay`, from encounters.roll_encounter; `story.overlay` is this);
- the town: its `scene` (scenes.signs.json: the dead carried in, the priest at the doors, a robbed carter at the gate,
  refugees), played once a stage when you walk into a town it threatens (`on_enter_town`, from story.on_enter_town;
  kept in the threat's `staged` list);
- the prices: the marks it leaves say their own (marks.json `prices`, economy.troubles_factor; the trade screen says
  why: economy.dear_because).

World-side records only are read here; nothing is kept but the threat's `staged` list and the step of the last
line on the land (`renown.flags["land_sign"]`).
"""

from __future__ import annotations

from realmwalker.core import textgen

LAND_GAP = 30  # steps between two lines on the land (20 with the most Text detail)
LAND_CHANCE = 0.35
BARK_SHARE = 3  # one bark in this many, in a town a threat has in its stakes, is the threat's


def _stage(tables, t: dict) -> dict | None:
    from realmwalker.world import threats

    kinds = tables.threats.get("kinds", {})
    if t["kind"] not in kinds:
        return None
    st = threats.stages(tables, t)
    i = int(t["scheme"].get("stage", -1))
    return st[i] if 0 <= i < len(st) else None


def here(world, tables, x: int, y: int) -> list[tuple[dict, dict]]:
    """The live threats whose reach covers this square, nearest first, with their stage now."""
    from realmwalker.world import threats

    out = []
    for t in threats.live(world):
        st = _stage(tables, t)
        if st is None:
            continue
        d = threats.distance(world, t, x, y)
        if d <= int(t["reach"]["r"]):
            out.append((d, int(t["id"][1:]), t, st))
    out.sort(key=lambda e: (e[0], e[1]))
    return [(t, st) for _, _, t, st in out]


def words(world, t: dict, rng) -> dict:
    from realmwalker.world import threats

    return threats._words(world, t, rng)


def _fill(world, t: dict, lines, rng) -> str:
    text = textgen.fill(rng.choice(list(lines)), rng, {}, words(world, t, rng))
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------- the land
def land_line(game, rng) -> str | None:
    """A line of the nearest threat's stage on the land here (None: no threat here, or its stage has none)."""
    p = game.player
    for t, st in here(game.world, game.tables, p.x, p.y):
        if st.get("flavour"):
            return _fill(game.world, t, st["flavour"], rng)
    return None


def on_the_land(game) -> None:
    """After a step on the overworld: now and then, a line of what the threat here has done to the country."""
    if game.busy or game.in_local or not game.flavour(1):
        return
    flags = game.renown.flags
    steps = int(game.player.steps)
    gap = LAND_GAP * 2 // 3 if game.flavour(2) else LAND_GAP
    if steps - int(flags.get("land_sign", -10 ** 6)) < gap:
        return
    rng = game.world.rng.child(f"land-sign/{steps}")
    if not rng.chance(LAND_CHANCE):
        return
    line = land_line(game, rng)
    if line:
        flags["land_sign"] = steps
        game.say(f"<dim>{line}</>", "place")


# ---------------------------------------------------------------------------- the streets
def bark(game, npc, roll: int) -> str | None:
    """What one of a threatened town's people says in passing about it (one bark in BARK_SHARE)."""
    from realmwalker.world import threats

    if roll % BARK_SHARE:
        return None
    for t in threats.live(game.world):
        if npc.settlement not in t["stakes"][:6]:
            continue
        st = _stage(game.tables, t)
        if st is None or not st.get("barks"):
            continue
        rng = game.world.rng.child(f"threat-bark/{t['id']}/{roll}")
        return _fill(game.world, t, st["barks"], rng)
    return None


# ---------------------------------------------------------------------------- the road
def _people(game, enc) -> bool:
    cr = game.tables.creatures
    return bool(enc.creatures) and all(cr[c.def_id].get("kind") == "humanoid" for c in enc.creatures)


def overlay(game, enc, rng):
    """An ordinary meeting in a threat's reach, once its stage's effects have come, carries its shadow: a line after
    the meeting's words (only with people who mean no harm: travellers, pedlars, folk on the move). Returns enc."""
    if enc is None or enc.attitude == "hostile" or not _people(game, enc):
        return enc
    p = game.player
    for t, st in here(game.world, game.tables, p.x, p.y):
        if t["scheme"].get("applied") and st.get("overlay"):
            enc.intro = f"{enc.intro} {_fill(game.world, t, st['overlay'], rng)}".strip()
            break
    return enc


# ---------------------------------------------------------------------------- the town
def on_enter_town(game, settlement) -> bool:
    """Into a town a threat has in its stakes: its stage's scene, once a stage. True when one began."""
    from realmwalker.game.story import stage
    from realmwalker.world import threats

    for t in threats.live(game.world):
        if settlement.id not in t["stakes"][:6]:
            continue
        st = _stage(game.tables, t)
        if st is None or not st.get("scene") or st["id"] in t.get("staged", []):
            continue
        rng = game.world.rng.child(f"threat-scene/{t['id']}/{st['id']}")
        w = {k: v for k, v in words(game.world, t, rng).items() if isinstance(v, str)}
        if stage.start(game, st["scene"], words=w) is not None:
            t.setdefault("staged", []).append(st["id"])
            return True
    return False
