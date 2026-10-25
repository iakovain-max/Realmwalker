"""The retreat and defeat as content (docs/ADVENTURES.md §5.8, fairness rules 3 and 6; Expansion 6 E.5).

**The retreat.** The party can always get away from a finale (the battle's own flight: no place seals yet). It costs,
and the tale goes on (`on_retreat`, from story.on_battle when the fight against a made boss ends in flight): the boss
is whole again when you come back (its hit points, its Legendary Resistances); its scheme comes on a stage (the
threat's next stage is due now); the villain's attention grows; and an ally who came with you may lose heart (the key
"ally" lost, by adventures.json "retreat" `ally_lost`). `adv["retreats"]` counts them.

**Defeat as content.** Beaten in its finale by a villain who keeps prisoners (adventures.json "defeat" `tempers`, and
never a beast), the fallen are not killed: they wake in its cells (`on_defeat`, from fight.finish_battle's defeat
branch, before robbers and death are asked). Everyone still breathing comes round at 1 hit point after hours senseless;
their weapons, armour and money are taken and put in a locked chest in another room of the same level; the boss keeps
the wounds you gave it (only a retreat lets it mend) and its band is no longer watchful; and the tale gains a step, "escape" (optional, so the tale never waits on
it): get out of the place, done when the party leaves the site's map (`on_leave`, from GameState.leave_local).
Nothing else is lost: the finale step stays open, so you can go back for the end. A villain takes you alive once in a
tale (`adv["taken_alive"]`): the second time it does not trust its locks.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

TAKE = ("weapon", "armor", "shield")  # the item categories taken from a prisoner (data/items.json)


def spec(game) -> dict:
    return game.tables.adventures.get("defeat") or {}


def retreat_spec(game) -> dict:
    return game.tables.adventures.get("retreat") or {}


def _story():
    from realmwalker.game import story

    return story


def _say(game, adv, key: str, **more) -> str:
    from realmwalker.game.story import deeds

    return deeds.say(game, adv, key, **more)


def finale_of(game, battle) -> dict | None:
    """The tale whose made boss stood in this fight (finale.prepare marks it)."""
    aid = getattr(battle, "__dict__", {}).get("finale_of") if battle is not None else None
    adv = _story().adventures(game.world).get(aid) if aid else None
    return adv if adv is not None and adv["state"] == "active" else None


def _boss(battle, adv):
    for fid, aid in (battle.__dict__.get("story_bosses") or {}).items():
        if aid == adv["id"]:
            f = next((x for x in battle.fighters if x.id == fid), None)
            if f is not None:
                return f
    return None


def _heal(f) -> None:
    c = f.creature if f is not None else None
    if c is None or not c.alive:
        return
    c.hp = c.max_hp
    c.uses.pop("legendary_resistance", None)
    c.uses.pop("legendary_actions", None)


# ---------------------------------------------------------------------------- the retreat
def on_retreat(game, battle) -> list[str]:
    adv = finale_of(game, battle)
    if adv is None or adv.get("boss_dead"):
        return []
    rs = retreat_spec(game)
    adv["retreats"] = int(adv.get("retreats", 0)) + 1
    _heal(_boss(battle, adv))
    out = [f"<warn>{esc(_say(game, adv, 'retreat'))}</>"]
    from realmwalker.world import news, threats

    t = threats.records(game.world).get(adv["threat"])
    if t is not None and t["state"] in threats.LIVE:
        t["scheme"]["next"] = min(float(t["scheme"]["next"]), news.now_days(game.world))  # (its next stage, now)
        t["scheme"].pop("held_until", None)
    from realmwalker.game.story import villain

    villain.notice(game, adv, int(rs.get("attention", 1)))
    rng = game.world.rng.child(f"retreat/{adv['id']}/{adv['retreats']}")
    if "ally" in adv["keys"] and rng.chance(float(rs.get("ally_lost", 0.0))):
        adv["keys"].remove("ally")
        out.append(f"<danger>{esc(_say(game, adv, 'retreat_ally'))}</>")
    _story().journal(adv, esc(_say(game, adv, "journal_retreat")), int(game.moment.total_days))
    return out


# ---------------------------------------------------------------------------- taken alive
def keeps_prisoners(game, adv: dict) -> bool:
    from realmwalker.world import threats

    t = _story().threat_of(game, adv)
    fig = threats.villain_figure(game.world, t) if t is not None else None
    if fig is None or fig.kind == "beast" or adv.get("taken_alive"):
        return False
    return (t.get("villain") or {}).get("temper") in spec(game).get("tempers", ())


def on_defeat(game, battle, result, after) -> bool:
    """Beaten at its finale by a villain that keeps prisoners: you wake in its cells (see the module's words). True if
    it took you; the aftermath then says so."""
    adv = finale_of(game, battle)
    lm = game.local
    if adv is None or lm is None or lm.kind != "dungeon" or not keeps_prisoners(game, adv):
        return False
    boss = _boss(battle, adv)
    if boss is None or not boss.active or not any(c.alive for c in game.party):
        return False
    adv["taken_alive"] = {"day": int(game.moment.total_days)}
    # (it keeps the wounds you gave it: only a retreat gives it time to mend)
    actor = game.battle_actor
    if actor is not None:
        actor.alert = False  # (it has you in chains: it is not watching the door)
    for c in game.party:
        if c.alive:
            c.hp = max(1, c.hp)
    chest = _take_gear(game, lm, adv, actor)
    _to_the_cells(game, lm, actor, chest)
    from realmwalker.game.fight import lie_senseless

    after.outcome = "taken"
    after.text = esc(_say(game, adv, "taken_wake"))
    after.notes.append(lie_senseless(game, 2 + game.world.rng.child(f"taken/{adv['id']}").randint(0, 3)))
    if chest is not None:
        after.notes.append(esc(_say(game, adv, "taken_gear")))
    _escape_step(game, adv, lm, chest)
    from realmwalker.game.story import villain

    villain.notice(game, adv, 1)
    _story().journal(adv, esc(_say(game, adv, "journal_taken")), int(game.moment.total_days))
    return True


def _take_gear(game, lm, adv, actor) -> tuple[int, int] | None:
    """Weapons, armour and money go into a locked chest in another room of the level. Its place, or None."""
    from realmwalker.game import glamour
    from realmwalker.rules.inventory import remove_item

    items = game.tables.items
    leader = game.party[0]
    taken, money = [], 0
    for c in game.party:
        money += c.money
        c.money = 0
    for it in list(leader.inventory):
        if items.category(it) in TAKE and not glamour.hidden_thing(game, it, robbers=True):
            got = remove_item(leader, it.uid)
            if got is not None:
                taken.append(got)
    if not taken and not money:
        return None
    spot = _room_spot(game, lm, far_from=(actor.x, actor.y) if actor is not None else None, nearest=True)
    if spot is None:
        return None
    from realmwalker.game.dungeon import set_terrain

    set_terrain(lm, spot[0], spot[1], "chest")
    lm.features[spot] = {"kind": "chest", "locked": int(spec(game).get("lock", 12)), "story": adv["id"],
                         "contents": {"items": [it.to_dict() for it in taken], "money": int(money)}}
    return spot


def _room_spot(game, lm, far_from=None, nearest: bool = False, avoid: tuple | None = None):
    """A free walkable square in a room of the level: the room nearest the boss's (`nearest`) or the one farthest from
    it, never the one it stands in, nor the room of `avoid`."""
    rooms = lm.meta.get("rooms") or []
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken = {(a.x, a.y) for a in lm.actors}

    def inside(r, xy):
        return xy is not None and r[0] <= xy[0] < r[0] + r[2] and r[1] <= xy[1] < r[1] + r[3]

    def free(r):
        return [(x, y) for y in range(r[1], r[1] + r[3]) for x in range(r[0], r[0] + r[2])
                if lm.in_bounds(x, y) and walk[x, y] and (x, y) not in taken and (x, y) not in lm.features
                and (x, y) != tuple(lm.entry)]

    cands = [r for r in rooms if not inside(r, far_from) and not inside(r, avoid) and free(r)]
    if not cands:
        cands = [r for r in rooms if free(r)]
    if not cands:
        return None
    if far_from is not None:
        def dist(r):
            return (r[0] + r[2] / 2 - far_from[0]) ** 2 + (r[1] + r[3] / 2 - far_from[1]) ** 2
        cands.sort(key=dist, reverse=not nearest)
    cells = free(cands[0])
    return cells[len(cells) // 2]


def _to_the_cells(game, lm, actor, chest) -> None:
    """The party is put in a room as far from the boss as the level goes (its cells), in chains."""
    spot = _room_spot(game, lm, far_from=(actor.x, actor.y) if actor is not None else None, avoid=chest)
    if spot is None:
        return
    p = game.player
    p.lx, p.ly = spot
    if "chains" in game.tables.terrain.index and spot not in lm.features:
        from realmwalker.game.dungeon import set_terrain

        set_terrain(lm, spot[0], spot[1], "chains")
    game.dirty = True


def _escape_step(game, adv, lm, chest) -> None:
    ch = _story().chapter(adv)
    if ch is None:
        return
    n = 1 + sum(1 for c in adv["chapters"] for st in c["steps"] if st["kind"] == "escape")
    place = dict(adv["places"]["home"])
    ch["steps"].append({"id": f"{ch['id']}.escape{n}", "kind": "escape", "state": "open", "optional": True,
                        "gives": [], "target": {"place": place, "level": lm.key,
                                                "chest": list(chest) if chest is not None else None}})


def on_leave(game) -> None:
    """Out of a site's map onto the road: an escape from that site is done."""
    from realmwalker.game.story import places

    for adv in _story().active(game):
        for st in _story().open_steps(adv):
            if st["kind"] == "escape" and places.here(game, st["target"]["place"]):
                game.say(f"<good>{esc(_say(game, adv, 'escaped'))}</>", "story")
                _story().step_done(game, adv["id"], st["id"])
