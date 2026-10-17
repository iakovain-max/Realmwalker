"""Locks and stone, weather and land (Expansion 3 E.5): the spells that work on things and on the land outside a fight.

A spell's {"op": "road", "does": ...} is done here (game/spellwork's door sends it here):
- "lock": Knock opens a locked door or chest within 60 feet of you underground, with a knock the whole level hears
  (and in the cells it is the escape's best friend: `knock_in_cell`); Arcane Lock seals a door beside you to everyone
  but the party, or your room at the inn of the town you stand in.
- "mend": Mending closes a break or a tear in the most worn thing the party carries.
- "hand": Mage Hand does your next theft from a stall from 30 feet away (`hand_ready`, read by game/law).
- "make": Fabricate makes a camp craft from the raw materials carried, without tools, fire or a check; Creation makes
  a thing of plant stuff or stone that vanishes at its time (tag "conjured:<minute>": `tick`, and no merchant buys it).
- "stone": Stone Shape and Passwall open a way through a dungeon's wall (Passwall's closes again after its hour:
  `on_step`, from game/dungeon.on_step).
- "chest": Leomund's Secret Chest sends the party's coin and treasure or spare arms to the Ethereal Plane (item tag
  "ethereal": it weighs nothing, nobody can take it, nothing in it can be used); the replica calls it back
  (`recall_chest`, the replica's use in game/gear). After 60 days it may be lost.
- "weather": Control Weather holds the weather round the caster (`held_weather`, read through game/survival.weather).
- "plants": Plant Growth's Enrichment (8 hours) doubles what is foraged on this tile for a year (`enriched`).
- "wave": Tsunami is not cast on the road: it is offered on the encounter screen when a band is seen first
  (`wave_casters`, `wave`).
Move Earth is a camp ward ("earthworks", game/spellwork); Control Water is a lasting spell ("part_water": the next
river is crossed dry, GameState.magic_crossing); Plant Growth's Overgrowth is ground in a fight (zone "overgrowth").
Every record is in `game.renown.flags` (saved with the character) or on the dungeon level (`lm.features`, `lm.meta`).
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character
from realmwalker.rules.inventory import add_item, carried, remove_item
from realmwalker.rules.items import money_text

DAY = 24 * 60
TALK_MINUTES = 10  # (Mage Hand: a spell of a minute holds for what you do next, as in game/glamour)
KNOCK_HEARD = 60  # squares: 300 feet, the whole level near enough
KNOCK_ESCAPE = 10  # the cell's lock opens for you: the rest is getting away
MEND_STEP, MEND_CAP = 25, 75  # a break or a tear, not the wear of years: the last of it needs tools
FABRICATE_BATCHES = 3  # a Large thing or eight 5-foot cubes of raw stuff: three of the camp's batches at most
VEGETABLE = ("wood", "leather", "rope", "wool", "cloth", "linen", "fur", "paper", "hemp", "straw", "bone", "wax")
STONE = ("stone", "clay")
CREATION_HOURS = {"vegetable": 24, "stone": 12}  # (PHB 2024: precious metals an hour, gems ten minutes: left out)
CREATION_CATEGORIES = ("gear", "tool", "weapon", "ammo", "clothing", "armor", "shield")
CHEST_DAYS = 60  # Leomund's Secret Chest: after 60 days a growing 5% a day that it is lost
CHEST_LOSS = 0.05
WEATHER_TILES = 2  # five miles round the caster: the tile and the next ones (a tile is three miles)
WEATHER_HOW = {"clear": "Clear the sky", "rain": "Bring rain (snow in the cold)", "calm": "Still the wind",
               "warm": "Warm the air", "cold": "Cool the air"}
ENRICH_DAYS = 365
WAVE = "6d10"


def _road(spell: dict) -> dict:
    return next((o for o in spell.get("effects", ()) if o.get("op") == "road"), {})


def _first(c) -> str:
    return esc(c.name.split()[0])


def _now(game) -> int:
    return int(game.world.time)


def _flags(game) -> dict:
    return game.renown.flags


def _here_id(game) -> int | None:
    lm = game.local
    if lm is None or lm.kind != "settlement":
        return None
    s = game.world.settlement_at(game.player.x, game.player.y)
    return s.id if s is not None else None


def _dungeon(game):
    lm = game.local
    return lm if lm is not None and lm.kind == "dungeon" else None


def _tid(lm, x: int, y: int) -> str:
    return lm.terrain_ids[int(lm.terrain[x, y])]


def _tdef(game, tid: str) -> dict:
    T = game.tables.terrain
    return T[T.index[tid]]


def _set(lm, x: int, y: int, name: str) -> None:
    if name not in lm.terrain_ids:
        lm.terrain_ids.append(name)
    lm.terrain[x, y] = lm.terrain_ids.index(name)


def _near(game, lm, squares: int):
    p = game.player
    for x in range(max(0, p.lx - squares), min(lm.width, p.lx + squares + 1)):
        for y in range(max(0, p.ly - squares), min(lm.height, p.ly + squares + 1)):
            yield x, y


def _way(dx: int, dy: int) -> str:
    return {(0, -1): "north", (0, 1): "south", (1, 0): "east", (-1, 0): "west"}[(dx, dy)]


# ---------------------------------------------------------------------------- read by the rest of the game
def hand_ready(game) -> bool:
    """Mage Hand is out in this town: the next theft from a stall is done by it (game/law.steal_from_shop)."""
    rec = _flags(game).get("mage_hand")
    return bool(rec) and int(rec.get("until", 0)) >= _now(game) and rec.get("settlement") == _here_id(game)


def spend_hand(game) -> None:
    _flags(game).pop("mage_hand", None)


def room_locked(game) -> bool:
    """Arcane Lock on your room at the inn of this town: no thief gets in (game/services)."""
    here = _here_id(game)
    if here is None:
        s = game.world.settlement_at(game.player.x, game.player.y)
        here = s.id if s is not None else None
    return here is not None and here in (_flags(game).get("arcane_rooms") or [])


def in_chest(item) -> bool:
    """A thing in Leomund's Secret Chest, on the Ethereal Plane: weightless, untouchable, unusable."""
    return "ethereal" in (getattr(item, "tags", None) or [])


def conjured(item) -> bool:
    """A thing made by Creation: it will vanish, and no merchant buys it."""
    return any(t.startswith("conjured:") for t in (getattr(item, "tags", None) or []))


def enriched(game) -> bool:
    """Plant Growth's Enrichment on this map tile: what is foraged here is doubled (game/camp)."""
    p = game.player
    now = _now(game)
    return any(int(r["x"]) == p.x and int(r["y"]) == p.y and int(r["until"]) >= now
               for r in _flags(game).get("enriched") or [])


def held_weather(game, w):
    """Control Weather holding the weather here (the caster's choice) for its eight hours (game/survival.weather)."""
    import dataclasses

    rec = _flags(game).get("weather")
    if not rec or int(rec.get("until", 0)) < _now(game):
        return w
    p = game.player
    if max(abs(p.x - int(rec["x"])), abs(p.y - int(rec["y"]))) > WEATHER_TILES:
        return w
    how = rec.get("how")
    if how == "clear":
        return dataclasses.replace(w, kind="heat" if w.temp >= 32 else "clear", precip=0.0, cloud=0.1,
                                   visibility=1.0)
    if how == "rain":
        return dataclasses.replace(w, kind="snow" if w.temp <= 0 else "rain", precip=max(w.precip, 0.6),
                                   cloud=max(w.cloud, 0.9), visibility=min(w.visibility, 0.6))
    if how == "calm":
        kind = {"storm": "rain", "blizzard": "snow"}.get(w.kind, w.kind)
        return dataclasses.replace(w, kind=kind, wind=min(w.wind, 5.0))
    if how in ("warm", "cold"):
        temp = round(w.temp + (10.0 if how == "warm" else -10.0), 1)
        kind = w.kind
        if temp > 1 and kind in ("flurries", "snow", "blizzard"):
            kind = {"flurries": "drizzle", "snow": "rain", "blizzard": "storm"}[kind]
        elif temp <= 0 and kind in ("drizzle", "rain", "storm"):
            kind = {"drizzle": "flurries", "rain": "snow", "storm": "blizzard"}[kind]
        if kind == "heat" and temp < 30:
            kind = "clear"
        return dataclasses.replace(w, kind=kind, temp=temp)
    return w


def tick(game) -> None:
    """As time passes: Creation's things vanish at their time; the weather held runs out; the secret chest left too
    long on the Ethereal Plane may be lost (from pass_time, through spellwork.tick)."""
    now = _now(game)
    for c in game.party:
        for it in list(c.inventory):
            for tag in it.tags or []:
                if tag.startswith("conjured:") and int(tag.split(":")[1]) < now:
                    for slot, uid in list(c.equipped.items()):
                        if uid == it.uid:
                            c.equipped[slot] = None
                    remove_item(c, it.uid)
                    game.say(f"The {game.tables.items.name(it, False)} made by magic fades away to nothing.", "dim")
                    break
    rec = _flags(game).get("weather")
    if rec is not None and int(rec.get("until", 0)) < now:
        del _flags(game)["weather"]
    rooms = _flags(game).get("enriched")
    if rooms:
        _flags(game)["enriched"] = [r for r in rooms if int(r["until"]) >= now]
    chest = _flags(game).get("secret_chest")
    if chest is not None:
        day = (now - int(chest["since"])) // DAY
        last = int(chest.get("checked", CHEST_DAYS))
        while day > last:
            last += 1
            if last > CHEST_DAYS and game.world.rng.child(f"chest/{chest['since']}/{last}").chance(
                    min(1.0, CHEST_LOSS * (last - CHEST_DAYS))):
                _lose_chest(game)
                return
        chest["checked"] = last


def _lose_chest(game) -> None:
    gone = 0
    for c in game.party:
        for it in list(c.inventory):
            if in_chest(it):
                remove_item(c, it.uid)
                gone += 1
    rec = _flags(game).pop("secret_chest", {})
    game.say("<warn>A thread of magic snaps somewhere far away: the secret chest is lost on the Ethereal Plane, with "
             f"everything in it</> <dim>({gone} things{', ' + money_text(int(rec.get('money', 0))) if rec.get('money') else ''})</>.",
             "warn")


def recall_chest(game) -> list[str]:
    """The replica touched: the chest comes back from the Ethereal Plane with all in it (the replica's use)."""
    rec = _flags(game).pop("secret_chest", None)
    things = [it for c in game.party for it in c.inventory if in_chest(it)]
    if rec is None and not things:
        return ["You turn the little replica over in your hand. Nothing answers: the chest is not on the other side."]
    for it in things:
        it.tags = [t for t in it.tags if t != "ethereal"]
    money = int((rec or {}).get("money", 0))
    game.leader.money += money
    game.cue("chest")
    game.dirty = True
    what = f"{len(things)} thing{'s' if len(things) != 1 else ''}" + (f" and {money_text(money)}" if money else "")
    return [f"<magic>You touch the replica and the chest is there before you, out of the grey: {what}, all as you "
            "left it.</>"]


def knock_in_cell(game) -> Character | None:
    """Who in the cells could open the lock with Knock (prepared, a slot left): the leader, alone in there."""
    c = game.leader
    t = game.tables
    if c.hp <= 0 or "knock" not in spellrules.known_spells(c, t) or not spellrules.can_cast(c, t, "knock")[0]:
        return None
    return c if spellrules.lowest_free_slot(c, t, 2) is not None else None


def knock_out(game) -> str | None:
    """Knock spent on the cell's lock: the slot is gone, and the words say how it opened (game/law.attempt_escape)."""
    c = knock_in_cell(game)
    if c is None:
        return None
    spellrules.spend_slot(c, spellrules.lowest_free_slot(c, game.tables, 2))
    return "speak the word of opening: the lock springs back with a knock like a hammer, and you run"


def wave_casters(game) -> list[tuple[Character, str]]:
    """Who could call up a wave before a fight (Tsunami ready and a slot for it), with the spell."""
    t = game.tables
    out = []
    for c in game.party:
        if not c.alive or c.hp <= 0 or not c.spells:
            continue
        for sid in spellrules.known_spells(c, t):
            if _road(t.spells[sid]).get("does") != "wave":
                continue
            ok, _ = spellrules.can_cast(c, t, sid)
            if ok and spellrules.lowest_free_slot(c, t, int(t.spells[sid]["level"])) is not None:
                out.append((c, sid))
    return out


def wave(game) -> list[str]:
    """Tsunami before a fight: the band seen first is struck by a wall of water (Strength save for half). The minute
    of casting passes; whoever is left fights, reeling. Returns what to say."""
    enc = game.encounter
    casters = wave_casters(game)
    if enc is None or not casters:
        return []
    c, sid = casters[0]
    t = game.tables
    spell = t.spells[sid]
    o = _road(spell)
    slot = spellrules.lowest_free_slot(c, t, int(spell["level"]))
    spellrules.spend_slot(c, slot)
    spellrules.spend_material(c, t, sid)
    dc = spellrules.save_dc(game.sheet(c), t)
    rng = game.world.rng.child(f"wave/{game.world.time}")
    hurt, gone = 0, 0
    for cr in enc.creatures:
        if cr.hp <= 0:
            continue
        cdef = t.creatures[cr.def_id]
        bonus = int((cdef.get("saves") or {}).get(o.get("save", "str"),
                                                  (int((cdef.get("abilities") or {}).get(o.get("save", "str"), 10)) - 10) // 2))
        dmg = dice.roll(o.get("dice", WAVE), rng).total
        if dice.d20(rng).natural + bonus >= dc:
            dmg //= 2
        cr.hp -= dmg
        hurt += dmg
        if cr.hp <= 0:
            cr.hp = 0
            cr.alive = False
            gone += 1
    game.pass_time(int(spell.get("minutes", 1)), "rest")
    enc.spotted_first = False  # (they know you now)
    game.cue("spell")
    out = [f"<magic>{_first(c)} raises both hands for a long minute, and a wall of water rises out of nothing and "
           f"falls on {esc(enc.group if hasattr(enc, 'group') else 'them')}.</> <dim>({o.get('dice', WAVE)} "
           f"bludgeoning, Strength save DC {dc} for half)</>"]
    left = [cr for cr in enc.creatures if cr.hp > 0]
    if not left:
        out.append("<good>When the water runs away, nothing of them is left standing.</>")
    else:
        out.append(f"{'The wave rolls on; ' if gone else ''}{len(left)} of them come on, battered and soaked.")
    return out


def on_step(game) -> None:
    """Passwall's hour is over: the passage closes (anyone in it is put out where it began). From dungeon.on_step and
    when a level is entered."""
    lm = _dungeon(game)
    if lm is None or not lm.meta.get("passwall"):
        return
    now = _now(game)
    keep = []
    p = game.player
    for rec in lm.meta["passwall"]:
        if int(rec["until"]) >= now:
            keep.append(rec)
            continue
        cells = [(int(x), int(y), str(tid)) for x, y, tid in rec["cells"]]
        if any((p.lx, p.ly) == (x, y) for x, y, _ in cells):
            p.lx, p.ly = int(rec["from"][0]), int(rec["from"][1])
            game.say("The stone closes in round you and you are pushed out, gently, where the passage began.", "warn")
        for x, y, tid in cells:
            _set(lm, x, y, tid)
        game.say("Somewhere near, the passage through the wall closes as if it had never been.", "dim")
    lm.meta["passwall"] = keep


# ---------------------------------------------------------------------------- what can be aimed at
def _locks(game, squares: int) -> list[Subject]:
    lm = _dungeon(game)
    if lm is None:
        return []
    out = []
    for x, y in _near(game, lm, squares):
        tid = _tid(lm, x, y)
        f = lm.features.get((x, y)) or {}
        if tid == "door_locked" and not f.get("arcane"):
            out.append(Subject("a locked door", "door", (x, y), x, y))
        elif tid in ("chest", "sarcophagus") and f.get("locked") and not f.get("opened"):
            out.append(Subject("a locked chest" if tid == "chest" else "a sealed coffin", "chest", (x, y), x, y))
    p = game.player
    out.sort(key=lambda s: max(abs(s.x - p.lx), abs(s.y - p.ly)))
    from realmwalker.game.divining import way_words

    for s in out:
        s.name = f"{s.name}, {way_words(s.x - p.lx, s.y - p.ly)}"
    return out


def _doors_beside(game) -> list[Subject]:
    lm = _dungeon(game)
    if lm is None:
        return []
    p = game.player
    out = []
    for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
        x, y = p.lx + dx, p.ly + dy
        if lm.in_bounds(x, y) and _tid(lm, x, y) in ("door_open", "door_closed"):
            out.append(Subject(f"the door to the {_way(dx, dy)}", "door", (x, y), x, y))
    return out


def _worn_things(game) -> list:
    items = game.tables.items
    return sorted((it for it in carried(game.party)
                   if items.category(it) in ("weapon", "armor", "shield", "helmet", "clothing")
                   and it.condition < MEND_CAP and not in_chest(it)), key=lambda it: it.condition)


def fabricable(game) -> list[tuple[str, str, int]]:
    """(craft id, its words, batches) for each camp craft the party carries the raw stuff for (its tools trained)."""
    from realmwalker.game import camp

    items = game.tables.items
    out = []
    for cid, spec in game.tables.camping.get("crafts", {}).items():
        if spec.get("tool"):
            prof = items.get(spec["tool"]).get("tool", spec["tool"])
            if not any(c.alive and prof in c.tools for c in game.party):
                continue  # (the book: things of high craftsmanship need the artisan's training)
        n = FABRICATE_BATCHES
        while n and not all(camp.party_has(game, item, int(qty) * n) for item, qty in spec["needs"]):
            n -= 1
        if n:
            out.append((cid, spec["name"], n))
    return out


def creatable(game) -> list[tuple[str, str]]:
    """(item id, its kind of stuff) for each plain thing Creation can make."""
    out = []
    for iid, d in game.tables.items.defs.items():
        if not isinstance(d, dict) or d.get("category") not in CREATION_CATEGORIES:
            continue
        if d.get("rare") or d.get("pack") or d.get("magic") or not d.get("value"):
            continue
        mat = d.get("material", "")
        stuff = "vegetable" if mat in VEGETABLE else "stone" if mat in STONE else None
        if stuff is None or float(d.get("weight", 0)) > 120:
            continue  # (no bigger than a 5-foot cube; metal, glass and gems are out)
        out.append((iid, stuff))
    return sorted(out, key=lambda p: game.tables.items.get(p[0])["name"])


def _wall_ways(game, depth: int) -> list[Subject]:
    """Each way (north, east, south, west) where no more than `depth` squares of wall stand between you and floor."""
    lm = _dungeon(game)
    if lm is None:
        return []
    p = game.player
    out = []
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        cells = []
        x, y = p.lx + dx, p.ly + dy
        while lm.in_bounds(x, y) and "wall" in _tdef(game, _tid(lm, x, y)).get("tags", []) and len(cells) < depth:
            cells.append((x, y))
            x, y = x + dx, y + dy
        if not cells or not lm.in_bounds(x, y) or not _tdef(game, _tid(lm, x, y)).get("walk") \
                or x in (0, lm.width - 1) or y in (0, lm.height - 1):
            continue
        feet = len(cells) * 5
        out.append(Subject(f"through the wall to the {_way(dx, dy)} ({feet} feet of it)", "wall", cells, x, y,
                           data={"from": (p.lx, p.ly)}))
    return out


def _chest_loads(game) -> list[Subject]:
    items = game.tables.items
    worn = {uid for c in game.party for uid in c.equipped.values() if uid is not None}
    treasure = [it for it in carried(game.party) if items.category(it) == "trade" and not in_chest(it)
                and not items.get(it.def_id).get("use") and not it.magic]
    arms = [it for it in carried(game.party) if items.category(it) in ("weapon", "armor", "shield", "helmet")
            and it.uid not in worn and not in_chest(it) and not it.magic]
    money = sum(c.money for c in game.party)
    out = []
    if treasure or money:
        out.append(Subject(f"the coin and the treasure ({money_text(money)}, {len(treasure)} things)", "load",
                           "treasure"))
    if arms:
        out.append(Subject(f"the spare arms and armour ({len(arms)} things)", "load", "arms"))
    if arms and (treasure or money):
        out.append(Subject("all of it", "load", "all"))
    return out


def subjects(game, caster, sid: str) -> list[Subject]:
    spell = game.tables.spells[sid]
    o = _road(spell) or {"does": spell.get("road_too")}
    does, how = o.get("does"), o.get("how")
    if does == "lock" and how == "knock":
        return _locks(game, max(1, int(spell.get("range", 60)) // 5))
    if does == "lock" and how == "arcane":
        return _doors_beside(game)
    if does == "make" and how == "fabricate":
        return [Subject(f"{name} ({n} batch{'es' if n > 1 else ''})", "craft", cid, data={"batches": n})
                for cid, name, n in fabricable(game)]
    if does == "make" and how == "creation":
        items = game.tables.items
        return [Subject(f"{items.get(iid)['name']} ({CREATION_HOURS[stuff]} hours)", "thing", iid,
                        data={"hours": CREATION_HOURS[stuff]}) for iid, stuff in creatable(game)]
    if does == "stone":
        return _wall_ways(game, int(o.get("squares", 1)))
    if does == "chest":
        return _chest_loads(game)
    if does == "weather":
        return [Subject(words, "weather", key) for key, words in WEATHER_HOW.items()]
    return []


def problem(game, caster, sid: str, target) -> str | None:
    spell = game.tables.spells[sid]
    o = _road(spell) or {"does": spell.get("road_too")}
    does, how = o.get("does"), o.get("how")
    aimed = target is not None and not isinstance(target, Character)
    if does == "lock":
        if how == "knock":
            if _dungeon(game) is None:
                return "only underground, where doors and chests are locked against you"
            if not _locks(game, max(1, int(spell.get("range", 60)) // 5)):
                return "no locked door or chest within 60 feet"
        else:
            if _here_id(game) is not None:
                if room_locked(game):
                    return "your room here is locked already"
                return None
            if _dungeon(game) is None:
                return "only on a door: underground, or your room at an inn in town"
            if not _doors_beside(game):
                return "no door beside you"
        if not aimed and not (how == "arcane" and _here_id(game) is not None):
            return "choose which (←→)"
    if does == "mend" and not _worn_things(game):
        return "nothing you carry has a break or a tear the spell could close"
    if does == "hand" and _here_id(game) is None:
        return "only in a town, where there are stalls to reach into"
    if does == "make":
        if not subjects(game, caster, sid):
            return "you carry no raw stuff the spell could work" if how == "fabricate" else "nothing to make"
        if not aimed:
            return "choose what (←→)"
    if does == "stone":
        if _dungeon(game) is None:
            return "only underground, through a wall"
        if not _wall_ways(game, int(o.get("squares", 1))):
            return "no wall beside you thin enough, with a way on beyond it"
        if not aimed:
            return "choose which way (←→)"
    if does == "chest":
        if _flags(game).get("secret_chest") is not None:
            return "the chest is on the Ethereal Plane already (touch the replica to call it back)"
        if not _chest_loads(game):
            return "nothing to put in it"
        if not aimed:
            return "choose what goes in (←→)"
    if does == "weather":
        lm = game.local
        if lm is not None and (lm.under_rock(game.player.lx, game.player.ly)
                               or lm.building_at(game.player.lx, game.player.ly) is not None):
            return "only under the open sky"
        if not aimed:
            return "choose how (←→)"
    if does == "plants":
        if game.local is not None and game.local.under_rock(game.player.lx, game.player.ly):
            return "nothing grows down here"
        if enriched(game):
            return "the land here is rich already"
    if does == "wave":
        return "it is cast when a band on the road is seen first, before the fight (the meeting's own choice)"
    return None


# ---------------------------------------------------------------------------- the castings
def _knock(game, caster, target) -> list[str]:
    from realmwalker.game import dungeon

    lm = _dungeon(game)
    x, y = target.ref
    tid = _tid(lm, x, y)
    if tid == "door_locked":
        _set(lm, x, y, "door_open")
        lm.features.pop((x, y), None)
        what = "the door swings open"
    else:
        lm.features[(x, y)]["locked"] = 0
        what = "the lid lifts a finger's breadth, unlocked"
    dungeon.alert_nearby(game, lm, x, y, KNOCK_HEARD)
    game.cue("unlock")
    return [f"<magic>{_first(caster)} speaks the word of opening:</> a knock like a hammer on an anvil rings out, and "
            f"{what}. <warn>Everything on this level heard it.</>"]


def _arcane_lock(game, caster, target) -> list[str]:
    here = _here_id(game)
    if here is not None:
        rooms = _flags(game).setdefault("arcane_rooms", [])
        if here not in rooms:
            rooms.append(here)
        return [f"<magic>{_first(caster)} draws a line of gold dust across the door of your room at the inn:</> it "
                "locks, and will open for nobody but you while it stands. <good>No thief will get in.</>"]
    lm = _dungeon(game)
    x, y = target.ref
    _set(lm, x, y, "door_locked")
    lm.features[(x, y)] = {"kind": "lock", "dc": 99, "arcane": True}
    return [f"<magic>{_first(caster)} touches the door with gold dust: it shuts, and locks.</> Nothing that lives "
            "here will open it; it opens for the party alone."]


def through_own_lock(game, lm, x: int, y: int) -> bool:
    """The party walks through its own Arcane Lock: it opens for them and shuts behind (from dungeon.bump)."""
    p = game.player
    bx, by = 2 * x - p.lx, 2 * y - p.ly
    if not lm.in_bounds(bx, by) or not _tdef(game, _tid(lm, bx, by)).get("walk") \
            or any(a.x == bx and a.y == by for a in lm.actors):
        game.say("Your own lock opens at your touch, but something stands in the way beyond.", "warn")
        return True
    p.lx, p.ly = bx, by
    game.pass_seconds(6)
    game.say("Your own lock opens at your touch; you pass, and it shuts and locks behind you.", "flavor")
    return True


def _mend(game, caster) -> list[str]:
    it = _worn_things(game)[0]
    it.condition = min(MEND_CAP, it.condition + MEND_STEP)
    items = game.tables.items
    return [f"{_first(caster)} passes two lodestones over the {items.name(it, False)}: <good>a split closes, a torn "
            f"strap knits</> <dim>({items.condition_word(it)})</>."]


def _hand(game, caster, spell) -> list[str]:
    _flags(game)["mage_hand"] = {"until": _now(game) + TALK_MINUTES, "settlement": _here_id(game)}
    return [f"<magic>A spectral hand floats at {_first(caster)}'s shoulder.</> Your next theft from a stall is done "
            "from 30 feet away, by the hand (Advantage on Sleight of Hand; caught, nobody can grab your wrist)."]


def _fabricate(game, caster, target) -> list[str]:
    from realmwalker.game import camp

    spec = game.tables.camping["crafts"][target.ref]
    n = int(target.data.get("batches", 1))
    for item, qty in spec["needs"]:
        camp.take_from_party(game, item, int(qty) * n)
    made = []
    for item, qty in spec["gives"]:
        q = int(qty) * n
        if add_item(game.leader, game.tables.items, item, q, made_at=game.world.time) is not None:
            made.append(f"{game.tables.items.get(item)['name']}" + (f" ×{q}" if q > 1 else ""))
    return [f"<magic>{_first(caster)} looks long at the raw stuff, and it shifts and settles into new shapes.</> "
            f"<loot>You have {', '.join(made)}.</>"]


def _creation(game, caster, target) -> list[str]:
    hours = int(target.data.get("hours", 24))
    it = add_item(game.leader, game.tables.items, target.ref, 1, made_at=game.world.time,
                  tags=[f"conjured:{_now(game) + hours * 60}"])
    name = game.tables.items.get(target.ref)["name"]
    if it is None:
        return ["The thing takes shape, wavers, and is gone: there is no room to hold it."]
    return [f"<magic>{_first(caster)} draws wisps of shadow out of the air and they set into {name}.</> "
            f"<dim>It will last {hours} hours, and then be gone.</>"]


def _stone(game, caster, spell, o, target) -> list[str]:
    lm = _dungeon(game)
    floor = {"cave_wall": "rock_floor", "wall_stone": "floor_stone", "wall_wood": "floor_stone"}
    cells = [tuple(c) for c in target.ref]
    was = [(x, y, _tid(lm, x, y)) for x, y in cells]
    for x, y, tid in was:
        _set(lm, x, y, floor.get(tid, "rock_floor"))
    if o.get("how") == "passwall":
        lm.meta.setdefault("passwall", []).append({"cells": [list(w) for w in was], "until": _now(game) + 60,
                                                   "from": list(target.data.get("from", (game.player.lx, game.player.ly)))})
        return [f"<magic>{_first(caster)} scatters a pinch of seeds on the wall, and an opening appears in it,</> "
                f"{len(cells) * 5} feet deep, with the dark beyond. <dim>It lasts an hour.</>"]
    return [f"<magic>{_first(caster)} works the stone like soft clay,</> and a low way opens through the wall."]


def _chest(game, caster, target) -> list[str]:
    load = target.ref
    items = game.tables.items
    worn = {uid for c in game.party for uid in c.equipped.values() if uid is not None}
    sent = 0
    for c in game.party:
        for it in c.inventory:
            if in_chest(it) or it.magic:
                continue
            cat = items.category(it)
            if load in ("treasure", "all") and cat == "trade" and not items.get(it.def_id).get("use") \
                    or load in ("arms", "all") and cat in ("weapon", "armor", "shield", "helmet") and it.uid not in worn \
                    or it.def_id == "leomunds_chest":
                it.tags = list(it.tags or []) + ["ethereal"]
                sent += 1
    money = 0
    if load in ("treasure", "all"):
        for c in game.party:
            money += c.money
            c.money = 0
    _flags(game)["secret_chest"] = {"since": _now(game), "money": money, "checked": 0}
    return [f"<magic>{_first(caster)} touches the chest and its tiny replica, and the chest is gone into the grey,</> "
            f"with {sent} thing{'s' if sent != 1 else ''}" + (f" and {money_text(money)}" if money else "") +
            ". No robber can take it there, and it weighs nothing; touch the replica to call it back. "
            "<dim>After 60 days it may be lost.</>"]


def _weather(game, caster, target) -> list[str]:
    p = game.player
    _flags(game)["weather"] = {"x": p.x, "y": p.y, "until": _now(game) + 8 * 60, "how": target.ref}
    game._weather_cache = None
    words = {"clear": "the clouds thin and part, and the sky clears", "rain": "clouds gather and thicken, and it begins "
             "to fall", "calm": "the wind drops away to nothing", "warm": "the air grows warmer, as if the season "
             "had turned", "cold": "the air turns cold, as if the season had turned"}[target.ref]
    return [f"<magic>{_first(caster)} burns incense and calls to the sky for ten minutes,</> and {words}. "
            "<dim>It holds for eight hours, five miles round.</>"]


def _plants(game, caster) -> list[str]:
    p = game.player
    _flags(game).setdefault("enriched", []).append({"x": p.x, "y": p.y, "until": _now(game) + ENRICH_DAYS * DAY})
    out = [f"<magic>{_first(caster)} walks the land and sings to what grows for eight hours.</> <good>For a year, "
           "the plants for a mile round bear twice over: what is foraged here is doubled.</>"]
    s = game.world.settlement_at(p.x, p.y)
    if s is not None and s.kind in ("hamlet", "village", "town") and getattr(s, "owner", None) is not None:
        from realmwalker.game import reputation

        reputation.deed(game, f"made the fields of {s.name} bear twice over", {s.owner: 3.0}, fame=1,
                        news_text=f"A traveller sang over the fields of {s.name}; the folk say this year's harvest "
                                  "will be the best in memory.")
        out.append(f"<good>The folk of {esc(s.name)} will remember it.</>")
    return out


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    spell = game.tables.spells[sid]
    o = _road(spell) or {"does": spell.get("road_too")}
    does, how = o.get("does"), o.get("how")
    if isinstance(target, Character):
        target = None
    if does == "lock":
        return _knock(game, caster, target) if how == "knock" else _arcane_lock(game, caster, target)
    if does == "mend":
        return _mend(game, caster)
    if does == "hand":
        return _hand(game, caster, spell)
    if does == "make":
        return _fabricate(game, caster, target) if how == "fabricate" else _creation(game, caster, target)
    if does == "stone":
        return _stone(game, caster, spell, o, target)
    if does == "chest":
        return _chest(game, caster, target)
    if does == "weather":
        return _weather(game, caster, target)
    if does == "plants":
        return _plants(game, caster)
    return []
