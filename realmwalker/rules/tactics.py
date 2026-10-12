"""How creatures fight on the grid, and how party members fight when left to themselves (Auto).

A turn is planned the way a sensible player would: find everyone worth hitting, every square you could reach this
turn, and every way of hitting them from there; weigh the chance to hit, the damage, whether it would finish them,
the opportunity attacks it would cost to get there and how exposed the square is; then walk there and strike.
Archers and casters keep their distance and look for cover; pack hunters close in together; the frightened and the
beaten run for the edge of the field. If nothing can be reached this turn, they close in (running, if that is all
there is to do). Party members on Auto also heal the fallen, bless, throw area spells where they catch only
enemies, and use their class's tricks.

Tactics 2.0 (docs/EXPANSIONS.md §4.7): every choice is weighed by the numbers the player sees (rules/engine/estimates.py:
the chance to hit or to fail the save, damage after resistances, a kill, control, healing); spells are chosen from
the one list of options (rules/engine/actions.py) by what they are worth less what they cost, and what they cost
falls as the fight matters more (a trivial fight is won with cantrips; a losing side spends everything); a spell held
by concentration is only given up for a better one; a creature's wits (its Intelligence) set how it picks targets
- beasts the nearest and weakest, the clever all on one, the cleverest on casters and healers first; its role
(data: creatures' "ai") sets where it wants to stand.

Pure logic: it only calls the Battle's own actions, so everything it does is something a player could do.
"""

from __future__ import annotations

from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY, AttackOption, Battle, Fighter, _avg
from realmwalker.rules.engine import actions, estimates, query

CAUTION = {"beast": 2.0, "mindless": 0.5, "fanatic": 1.0, "warrior": 3.0, "bandit": 6.0, "soldier": 6.0,
           "coward": 14.0, "party": 10.0}


# ---------------------------------------------------------------------------- wits, the fight, targets
def smarts(f: Fighter) -> int:
    """0: a beast or a mindless thing; 1: ordinary sense; 2: focuses its attacks (Intelligence 12+); 3: goes for the
    casters and healers first (16+). Characters plan as players do (2)."""
    if f.char is not None:
        return 2
    score = int(f.cdef.get("abilities", {}).get("int", 10))
    return 0 if score <= 5 else (1 if score < 12 else (2 if score < 16 else 3))


def importance(b: Battle, f: Fighter) -> float:
    """How much this fight matters to `f`'s side (0..1): the threat it faces against the hit points it has left."""
    foes = sum(estimates.threat(e) for e in b.enemies_of(f) if e.standing)
    ours = sum(max(0, x.hp) for x in b.allies_of(f)) + 1
    return max(0.0, min(1.0, foes * 2.5 / ours))


def focus(b: Battle, f: Fighter) -> Fighter | None:
    """The enemy `f`'s side is ganging up on this round (the most dangerous for its hit points, in sight)."""
    key = (f.team, b.round)
    cache = b.__dict__.setdefault("_focus", {})
    if key not in cache:
        seen = [e for e in b.enemies_of(f) if e.standing and e.state != "surrendered"]
        cache.clear() if len(cache) > 50 else None
        cache[key] = max(seen, key=lambda e: (estimates.threat(e) / max(1, e.hp), -e.id)).id if seen else None
    fid = cache[key]
    return next((x for x in b.fighters if x.id == fid), None)


def target_weight(b: Battle, f: Fighter, t: Fighter) -> float:
    """How much more a target is worth to `f` than its hit points alone say."""
    w = 1.0
    s = smarts(f)
    if t.concentration is not None and s >= 1:
        w *= 1.3  # break the spell
    if s >= 3 and t.char is not None and spellrules.is_caster(t.char, b.t):
        w *= 1.25
    elif t.char is not None and t.char.cls == "wizard":
        w *= 1.1
    if s >= 2:
        fo = focus(b, f)
        if fo is t:
            w *= 1.4
    return w


def role(f: Fighter) -> str:
    """brute, skirmisher, artillery, controller, leader, support, lurker or solo (creatures' "ai" role, else a guess)."""
    if f.char is not None:
        return "artillery" if f.char.cls == "wizard" else "brute"
    return (f.cdef.get("ai") or {}).get("role", "brute")


def take_turn(b: Battle, f: Fighter) -> None:
    """Play out `f`'s whole turn."""
    if b.burning(f) and f.action > 0 and (f.hp <= 8 or not any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing)):
        b.do_extinguish(f)  # on fire: roll it out, unless there is a fight right here worth the burns
        if b.current is not f or b.outcome is not None:
            return
    if f.state == "fleeing":
        flee(b, f)
        return
    if f.char is not None:
        _party_turn(b, f)
    else:
        _monster_turn(b, f)


# ---------------------------------------------------------------------------- monsters
def _monster_turn(b: Battle, f: Fighter) -> None:
    opts = [o for o in b.attack_options(f) if o.available]
    breath = [o for o in opts if o.extra.get("area")]
    if breath and _try_area_attack(b, f, breath[0]):
        return
    plain = [o for o in opts if not o.extra.get("area")]
    if f.cdef.get("spells"):
        _creature_magic(b, f)
        if b.current is not f or b.outcome is not None or not f.active:
            return
        if f.action <= 0 and f.attacks_left <= 0:
            _keep_distance(b, f)
            return
    if not plain:
        return
    if (f.has_trait("aggressive") or f.has_trait("charge")) and f.bonus > 0 and f.speed > 0 and \
            not any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
        f.bonus -= 1  # Aggressive (a bonus action to close in), or a troll's Charge (half its speed)
        f.move_left += f.speed if f.has_trait("aggressive") else f.speed // 2
    _fight(b, f, plain, attacks=max(1, int(f.cdef.get("multiattack", 1))))
    if f.has_trait("rampage") and f.bonus > 0 and b.outcome is None and b.current is f and f.active \
            and f.creature.uses.get("rampage", 1) > 0:
        hurt = [e for e in b.enemies_of(f) if e.standing and e.hp <= e.max_hp // 2 and b.gap(f, e) <= 1]
        rend = next((o for o in plain if o.is_melee and o.available), None)
        if hurt and rend is not None:  # Rampage: once a day, another blow at a bloodied foe
            f.bonus -= 1
            f.creature.uses["rampage"] = 0
            b._attack(f, rend, min(hurt, key=lambda e: e.hp))
            b._check_end()
    if f.has_trait("nimble_escape") and f.bonus > 0 and b.outcome is None and b.current is f and f.active:
        _slip_away(b, f)


def _fight(b: Battle, f: Fighter, opts: list[AttackOption], attacks: int) -> bool:
    """Move and strike with the best plan there is; close in if nothing can be reached. True if anything struck."""
    plan = best_plan(b, f, opts)
    if plan is None:
        approach(b, f, opts)
        return False
    score, path, opt, target = plan
    if path:
        b.walk(f, path)
        b._check_end()
    if b.outcome is not None or not f.active or not f.can_act():
        return False
    struck = False
    multi = f.creature is not None and f.cdef.get("multiattack")
    plan = f.cdef.get("multiattack_plan") if f.creature is not None else None
    if plan and not any(opt.extra.get("id") in slot for slot in plan):
        plan, multi, attacks = None, False, 1  # a single action instead of the Multiattack (a ghoul's paralysing claw)
    kind_melee = opt.is_melee
    for i in range(attacks):
        if b.outcome is not None or not f.can_act():
            break
        usable = [o for o in opts if o.is_melee == kind_melee and o.available]
        if not usable:
            break
        if plan:  # "a Bite and two Claws": each attack as the stat block names it (the best of a slot's choices)
            slot = plan[i] if i < len(plan) else plan[-1]
            fits = [o for o in usable if o.extra.get("id") in slot] or usable
            here = (f.x, f.y)
            choice = max(fits, key=lambda o: _value(b, f, o, target, here) if b.in_reach(f, o, target)[0] else -1.0)
        else:
            choice = usable[i % len(usable)] if multi else opt
        if not target.active or not b.in_reach(f, choice, target)[0]:
            others = [t for t in b.targets_for(f, choice) if t.team != f.team and t.active]
            if not others:
                break
            target = min(others, key=lambda t: t.hp)
        if f.creature is not None:
            if i == 0:
                f.action -= 1
            b._attack(f, choice, target)
            b._check_end()
        else:
            if not b.do_attack(f, choice, target):
                break
        struck = True
    return struck


def best_plan(b: Battle, f: Fighter, opts: list[AttackOption]):
    """(score, path, option, target) for the best square to strike from this turn, or None."""
    caution = CAUTION.get("party" if f.char else f.morale_type, 4.0)
    tree = b.move_tree(f, risk=caution)
    occ = b.occupied_by_others(f)
    here = (f.x, f.y)
    stops = {sq: st for sq, st in tree.items() if sq == here or grid.can_stop(sq, f.sq, occ)}
    targets = _targets(b, f)
    if not targets:
        return None
    best = None
    squares = near_at = None
    for opt in opts:
        if opt.is_melee:
            for t in targets:
                for sq in _ring(t, opt.reach_sq, f.sq):
                    st = stops.get(sq)
                    if st is None:
                        continue
                    score = _value(b, f, opt, t, sq) * _plan_attacks(f, opt) - st.cost * 0.02 - st.risk * 0.1
                    if best is None or score > best[0]:
                        best = (score, sq, opt, t)
        else:
            long = (opt.range or (80, 320))[1]
            if squares is None:
                squares = sorted(stops, key=lambda s: stops[s].cost)[:70]
                foes = [(e.space, b.reach_of(e)) for e in b.enemies_of(f) if e.standing]
                near_at = {sq: sum(1 for sp, r in foes if grid.gap((sq[0], sq[1], f.sq), sp) <= r) for sq in squares}
            many = _plan_attacks(f, opt)
            for t in targets:
                for sq in squares:
                    space = (sq[0], sq[1], f.sq)
                    if grid.gap(space, t.space) * grid.SQUARE_FT > long:
                        continue
                    st = stops[sq]
                    less = st.cost * 0.02 + st.risk * 0.1 + near_at[sq] * (0.6 if f.prefers_range else 0.25)
                    score = _value(b, f, opt, t, sq, cover=0) * many - less
                    if best is not None and score <= best[0]:
                        continue  # cover could only make it worse: no need to look for it
                    cover = b.field.cover(space, t.space)
                    if cover == grid.TOTAL:
                        continue
                    if cover:
                        score = _value(b, f, opt, t, sq, cover=cover) * many - less
                    if best is None or score > best[0]:
                        best = (score, sq, opt, t)
    if best is None or best[0] <= 0:
        return None
    score, sq, opt, t = best
    return score, grid.route(tree, sq) if sq != here else [], opt, t


def _targets(b: Battle, f: Fighter) -> list[Fighter]:
    standing = [e for e in b.enemies_of(f) if e.standing and e.state != "surrendered"
                and not ("charmed" in f.conditions and f.sources.get("charmed") == e.id)]
    seen = [e for e in standing if b.can_see(f, e) or b.gap(f, e) <= 1]
    targets = seen or [e for e in standing if not e.hidden]
    if not targets and f.creature is not None and f.morale_type in ("mindless", "fanatic"):
        targets = [e for e in b.fighters if e.team != f.team and e.state == "down"]
    return targets


def _ring(t: Fighter, reach: int, size: int) -> list[tuple[int, int]]:
    """Squares from which a creature of `size` has `t` within `reach` squares."""
    out = []
    for x in range(t.x - reach - size + 1, t.x + t.sq + reach):
        for y in range(t.y - reach - size + 1, t.y + t.sq + reach):
            if grid.gap((x, y, size), t.space) == 0:
                continue
            if grid.gap((x, y, size), t.space) <= reach:
                out.append((x, y))
    return out


def _value(b: Battle, f: Fighter, opt: AttackOption, t: Fighter, sq, *, cover: int | None = None) -> float:
    """How good one attack on `t` from square `sq` is: expected damage (by the same rules the attack will be rolled
    with), more if it could finish them, weighted by who they are."""
    space = (sq[0], sq[1], f.sq)
    if cover is None:
        cover = b.field.cover(space, t.space)
        cover = 0 if cover == grid.TOTAL else cover
    dmg = _avg(opt.damage) * estimates.damage_factor(t, opt.damage_type)
    if opt.extra.get("single_save"):  # a web, a touch that drains: no attack roll, a saving throw
        pf = estimates.fail_chance(b, t, opt.extra["save"], int(opt.extra["dc"]))
        ev = dmg * (pf + ((1 - pf) * 0.5 if opt.extra.get("half") else 0.0))
        if opt.extra.get("on_fail"):
            ev += pf * estimates.threat(t) * 0.6
    else:
        r = query.attack_roll(b, f, t, opt, space=space)
        p = estimates._p(t.ac() + grid.COVER_AC[cover] - opt.bonus, r.mode)
        dmg += sum(_avg(e["damage"]) * estimates.damage_factor(t, e["type"]) for e in opt.extra.get("extra", ())
                   if e.get("if") != "advantage" or r.mode == "advantage")
        ev = p * dmg + p * _hit_effects_worth(b, f, opt, t)
    value = ev * _opening(b, f, opt, t)
    if t.hp <= dmg:
        value *= 1.6  # it could finish them
    if t.state == "down":
        value *= 0.3
    return value * target_weight(b, f, t) + 0.5


CONTROL = {"paralyzed": 2.5, "stunned": 2.5, "restrained": 0.7, "grappled": 0.5, "prone": 0.35, "poisoned": 0.3,
           "frightened": 0.4, "blinded": 0.6}


def _hit_effects_worth(b: Battle, f: Fighter, opt: AttackOption, t: Fighter) -> float:
    """What a hit's effects are worth on top of its damage (a knock-down, a grab, a paralysis), if they would take."""
    from realmwalker.rules.engine import statblocks

    w = 0.0
    for e in opt.extra.get("on_hit", ()):
        cid = e.get("condition")
        if e.get("op") != "condition" or cid in t.conditions or query.condition_immune(t, cid):
            continue
        if e.get("max_size") and not statblocks.size_at_most(t.size, e["max_size"]):
            continue
        if t.kind in e.get("not_types", ()):
            continue
        chance = estimates.fail_chance(b, t, e["save_to_avoid"], int(e["dc"])) if e.get("save_to_avoid") else 1.0
        w += chance * CONTROL.get(cid, 0.2) * estimates.threat(t)
    return w


def _opening(b: Battle, f: Fighter, opt: AttackOption, t: Fighter) -> float:
    """A creature's opening move (creatures' "ai" opens_with): worth more while the target lacks what it brings."""
    if f.creature is None or (f.cdef.get("ai") or {}).get("opens_with") != opt.extra.get("id"):
        return 1.0
    brings = [e.get("condition") for e in opt.extra.get("on_hit", ()) if e.get("op") == "condition"]
    return 1.0 if any(c in t.conditions for c in brings) else 3.0


def _plan_attacks(f: Fighter, opt: AttackOption) -> int:
    """How many attacks a turn with this option makes: the whole Multiattack if it is part of it, else one."""
    plan = f.cdef.get("multiattack_plan") if f.creature is not None else None
    if plan and not any(opt.extra.get("id") in slot for slot in plan):
        return 1
    return max(1, int(f.cdef.get("multiattack", 1))) if f.creature is not None else 1


def approach(b: Battle, f: Fighter, opts: list[AttackOption]) -> None:
    """Nothing to hit from anywhere this turn: close in on the nearest worth fighting (running, if need be)."""
    targets = _targets(b, f)
    if not targets or f.speed <= 0:
        if f.action > 0 and f.char is None:
            b.do_dodge(f)
        return
    reach = max((o.reach_sq for o in opts if o.is_melee), default=1)
    caution = CAUTION.get("party" if f.char else f.morale_type, 4.0)
    tree = b.move_tree(f, budget=600, risk=caution)
    occ = b.occupied_by_others(f)
    best = None
    for t in targets:
        for sq in _ring(t, reach, f.sq):
            st = tree.get(sq)
            if st is None or not grid.can_stop(sq, f.sq, occ):
                continue
            if best is None or st.cost + st.risk < best[0]:
                best = (st.cost + st.risk, sq)
    if best is None:
        # Walled off: just get closer as the crow flies.
        t = min(targets, key=lambda t: b.gap(f, t))
        stops = [sq for sq in tree if tree[sq].cost <= f.move_left and grid.can_stop(sq, f.sq, occ)]
        if not stops:
            return
        sq = min(stops, key=lambda s: (grid.gap((s[0], s[1], f.sq), t.space), tree[s].cost))
        if grid.gap((sq[0], sq[1], f.sq), t.space) < b.gap(f, t):
            b.walk(f, grid.route(tree, sq))
        return
    path = grid.route(tree, best[1])
    ranged = any(not o.is_melee for o in opts)
    if f.action > 0 and not ranged and len(path) * 5 > f.move_left:
        b.do_dash(f)
    _walk_budget(b, f, path)


def _walk_budget(b: Battle, f: Fighter, path: list[tuple[int, int]]) -> None:
    """Walk as far along a path as this turn's movement goes, stopping only where there is room to stand."""
    occ = b.occupied_by_others(f)
    spent = 0
    cut = 0
    for i, sq in enumerate(path):
        step = 10 if "prone" in f.conditions or any(b.field.difficult(*c) for c in grid.cells(sq[0], sq[1], f.sq)) else 5
        if spent + step > f.move_left:
            break
        spent += step
        if grid.can_stop(sq, f.sq, occ):
            cut = i + 1
    if cut:
        b.walk(f, path[:cut])


def flee(b: Battle, f: Fighter) -> None:
    """Run for the nearest edge of the field and get away."""
    if "grappled" in f.conditions or "restrained" in f.conditions:
        if f.action > 0:
            b.do_escape(f)
        return
    if b.can_leave(f):
        b.do_leave(f)
        return
    if f.has_trait("nimble_escape") and f.bonus > 0:
        b.do_disengage(f, bonus=True)
    tree = b.move_tree(f, budget=600, risk=2.0)
    occ = b.occupied_by_others(f)
    exits = [sq for sq in tree if grid.can_stop(sq, f.sq, occ) and any(b.field.exits[c] for c in grid.cells(sq[0], sq[1], f.sq))]
    if not exits:
        approach(b, f, [o for o in b.attack_options(f) if o.available])
        return
    goal = min(exits, key=lambda s: tree[s].cost + tree[s].risk)
    path = grid.route(tree, goal)
    if f.action > 0 and len(path) * 5 > f.move_left:
        b.do_dash(f)
    _walk_budget(b, f, path)
    if b.current is f and f.active and b.can_leave(f):
        b.do_leave(f)


def _creature_magic(b: Battle, f: Fighter) -> None:
    """An enemy caster: the best of its bonus-action spells, then the best of its action spells if it is worth more than
    its weapons; its spiritual weapon strikes on later turns."""
    if not any(e.standing for e in b.enemies_of(f)):
        return
    tok = next((t for t in b.tokens if t.owner == f.id and t.kind == "spiritual_weapon"), None)
    if tok is not None and f.bonus > 0:
        near = b.spirit_targets(f)
        if near:
            f.bonus -= 1
            b._spirit_strike(f, tok, min(near, key=lambda e: e.hp))
    if f.bonus > 0:
        quick = _pick_cast(b, f, "bonus")
        slow = _pick_cast(b, f, "action", beat=_best_attack_worth(b, f)) if f.action > 0 else None
        if quick is not None and not (slow is not None and quick[4].get("concentration") and slow[4].get("concentration")
                                      and slow[0] > quick[0]):
            _do_cast(b, f, quick)  # (unless the action's spell, held the same way, is worth more)
    if f.action > 0 and b.outcome is None and b.current is f:
        _cast_best(b, f, "action", beat=_best_attack_worth(b, f))


def _best_attack_worth(b: Battle, f: Fighter) -> float:
    """What a turn of plain attacks from here would be worth (the bar a spell must clear)."""
    opts = [o for o in b.attack_options(f) if o.available and not o.extra.get("area")]
    best = 0.0
    for o in opts:
        for t in b.targets_for(f, o):
            best = max(best, _value(b, f, o, t, (f.x, f.y)))
    attacks = max(1, int(f.cdef.get("multiattack", 1))) if f.creature is not None else query.attacks_per_action(f)
    reach = 0.6 if not any(b.targets_for(f, o) for o in opts) else 1.0  # (it would have to walk first)
    return best * attacks * reach


def _aims(b: Battle, f: Fighter, opt) -> list[tuple]:
    """Where a spell could be aimed: (target, point) pairs worth weighing."""
    if opt.aim == "creature":
        return [(t, None) for t in opt.targets]
    if opt.aim == "point" and opt.points:
        enemies = [e for e in b.enemies_of(f) if e.standing]
        friends = [x for x in b.team(f.team) if x.active or x.state == "down"]
        near = {(e.x + dx, e.y + dy) for e in enemies + friends for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        return [(None, p) for p in sorted(near & opt.points)][:60]
    return [(None, None)]


def spell_cost(b: Battle, f: Fighter, level: int) -> float:
    """What spending a spell of this level is worth giving up, by how much the fight matters (cantrips are free)."""
    if level <= 0:
        return 0.0
    keep = 3.0 if f.char is not None else 1.5  # the party has the rest of the day to think of
    return keep * level * (1.0 - 0.85 * importance(b, f))


def _cast_best(b: Battle, f: Fighter, cost: str, *, beat: float = 0.0, care: float | None = None) -> bool:
    """Cast the spell (of this casting time) worth most here, if it is worth more than `beat`. True if one was cast."""
    best = _pick_cast(b, f, cost, beat=beat, care=care)
    return _do_cast(b, f, best) if best is not None else False


def _do_cast(b: Battle, f: Fighter, best) -> bool:
    _, value, target, point, _ = best
    if f.char is not None:
        return bool(b.do_cast(f, value, target, point=point))
    return bool(b.creature_cast(f, value, target, point=point))


def _pick_cast(b: Battle, f: Fighter, cost: str, *, beat: float = 0.0, care: float | None = None):
    """(score, value, target, point, spell) of the spell of this casting time worth most here, or None."""
    from realmwalker.rules.combat import spell_id

    if care is None:
        care = 4.0 if f.char is not None else (0.3 if smarts(f) == 0 else 1.0)  # friends caught in an area
    best = None
    for opt in actions.options(b, f, only=("cast",)):
        if opt.kind != "cast" or not opt.available or opt.cost != cost:
            continue
        sp = b.t.spells[spell_id(opt.value)]
        if sp.get("concentration") and f.concentration is not None:
            continue  # (keep what it holds)
        if sp.get("concentration") and sp["level"] > 0 and importance(b, f) < 0.15:
            continue
        price = spell_cost(b, f, sp["level"] if not str(opt.value).startswith(("scroll:", "charge:")) else 0)
        for target, point in _aims(b, f, opt):
            w = estimates.spell_value(b, f, opt.value, target=target, point=point)
            if w.total(care=care) <= 0.5:
                continue
            score = w.total(care=care) - price
            if f.char is not None and w.friendly > 0:
                continue  # companions never catch friends
            if best is None or score > best[0]:
                best = (score, opt.value, target, point, sp)
    if best is None or best[0] <= beat:
        return None
    return best


def _keep_distance(b: Battle, f: Fighter) -> None:
    """Its spell cast, a caster steps back from blades if it can do so without being cut."""
    if f.move_left < 5 or not any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
        return
    tree = b.move_tree(f, risk=30.0)
    occ = b.occupied_by_others(f)
    enemies = [e for e in b.enemies_of(f) if e.standing]
    best = None
    for sq, st in tree.items():
        if st.provokes or not grid.can_stop(sq, f.sq, occ):
            continue
        d = min(grid.gap((sq[0], sq[1], f.sq), e.space) for e in enemies)
        key = (-min(d, 4), st.cost)
        if best is None or key < best[0]:
            best = (key, sq)
    if best is not None and best[1] != (f.x, f.y):
        b.walk(f, grid.route(tree, best[1]))


def _slip_away(b: Battle, f: Fighter) -> None:
    """Goblins: strike and then step back out of reach without being cut down (Nimble Escape)."""
    if not any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
        return
    if not any(not o.is_melee for o in b.attack_options(f)):
        return
    b.do_disengage(f, bonus=True)
    _step_back(b, f)


def _step_back(b: Battle, f: Fighter) -> None:
    tree = b.move_tree(f)
    occ = b.occupied_by_others(f)
    enemies = [e for e in b.enemies_of(f) if e.standing]
    best = None
    for sq, st in tree.items():
        if not grid.can_stop(sq, f.sq, occ):
            continue
        d = min((grid.gap((sq[0], sq[1], f.sq), e.space) for e in enemies), default=0)
        if d <= 1:
            continue
        key = (-min(d, 4), st.cost + st.risk)
        if best is None or key < best[0]:
            best = (key, sq)
    if best is not None:
        b.walk(f, grid.route(tree, best[1]))


def _try_area_attack(b: Battle, f: Fighter, opt: AttackOption) -> bool:
    """A breath weapon: worth it if it catches two (or the only one there is), from where it stands."""
    a = opt.extra
    best = None
    for t in b.enemies_of(f):
        cells = b.field.area(a["area"]["shape"], int(a["area"]["size"]), origin=f.space, toward=(t.x, t.y), from_self=True)
        hit = b.in_area(cells, "all", f)
        enemies = sum(1 for x in hit if x.team != f.team)
        friends = sum(1 for x in hit if x.team == f.team and x is not f)
        score = enemies - 2 * friends
        if enemies and (best is None or score > best[0]):
            best = (score, (t.x, t.y))
    if best is None or best[0] < min(2, len(b.enemies_of(f))):
        return False
    b.area_attack(f, opt, best[1])
    return True


# ---------------------------------------------------------------------------- party members on Auto
def _party_turn(b: Battle, f: Fighter) -> None:
    c = f.char
    if "grappled" in f.conditions or "restrained" in f.conditions:
        enemies_near = [e for e in b.enemies_of(f) if b.gap(f, e) <= 1]
        if not enemies_near:
            b.do_escape(f)
            return
    _tend_the_fallen(b, f)
    if b.current is not f or b.outcome is not None:
        return
    if f.hp < f.max_hp // 2:  # a breath caught with the bonus action, when it is needed (Second Wind)
        for opt, a in _abilities(b, f, "heal"):
            if estimates.ability_value(b, f, a).total() > 0:
                b.do_ability(f, opt.value)
                break
    if b.current is not f or b.outcome is not None:
        return
    if f.action > 0 and _use_power(b, f):
        if b.current is f and b.outcome is None:
            _bonus_strike(b, f)
        if b.current is f and b.outcome is None and f.move_left >= 5:
            _keep_safe(b, f)
        return
    if spellrules.is_caster(c, b.t) and f.action > 0:
        if _cast_something(b, f):
            if b.current is f and b.outcome is None:
                _bonus_strike(b, f)  # (the spiritual weapon, War Priest)
            if b.current is f and b.outcome is None and f.move_left >= 5:
                _keep_safe(b, f)
            return
    if b.current is not f or b.outcome is not None:
        return
    opts = [o for o in b.attack_options(f) if o.available]
    attacks = 2 if c.level >= 5 and "extra_attack" in c.features else 1
    if opts and f.hp < f.max_hp * 0.6 and len(b.enemies_of(f)) >= 2:  # one more action when it is hard going
        for opt, _ in _abilities(b, f, "action"):
            b.do_ability(f, opt.value)
            attacks *= 2 if f.action > 1 else 1
            break
    if opts:
        struck = _fight(b, f, opts, attacks)
        if struck and b.current is f and b.outcome is None:
            _bonus_strike(b, f)
    if b.current is f and b.outcome is None and f.bonus > 0:  # Cunning Action: away when hurt, else out of sight
        moves = {a["via"]: opt for opt, a in _abilities(b, f, "move")}
        if "disengage" in moves and f.hp < f.max_hp // 2 and \
                any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
            b.do_ability(f, moves["disengage"].value)
            _step_back(b, f)
        elif "hide" in moves and not b.hide_problem(f):
            b.do_ability(f, moves["hide"].value)


def _abilities(b: Battle, f: Fighter, does: str) -> list[tuple]:
    """(option, definition) of each ability in the one list of actions (rules/engine/actions.options) that can be
    used now and does this (`_does`)."""
    out = []
    for opt in actions.options(b, f, only=("ability",)):
        if opt.kind == "ability" and opt.available:
            a = actions.find(f, opt.value)
            if _does(opt, a) == does:
                out.append((opt, a))
    return out


def _does(opt, a: dict | None) -> str:
    """What an ability is for, read from what it is: a "heal" with the bonus action, one more "action", a "move" done
    with the bonus action (Cunning Action), a bonus "attack" (an off-hand blow, a spirit's strike, War Priest), or a
    "power" used with the action (Channel Divinity)."""
    if a is None:
        return "attack" if opt.value in ("offhand", "spirit_strike") else "other"
    if a.get("via"):
        return "move"
    ops = [o["op"] for o in a.get("effects", ())]
    if "gain_action" in ops:
        return "action"
    if a["cost"] == "bonus":
        return "heal" if "heal" in ops else "attack"
    return "power" if a["cost"] == "action" else "other"


def _use_power(b: Battle, f: Fighter) -> bool:
    """A power used with the action (Turn Undead, Preserve Life), if it is worth more than the best spell or blow."""
    best = None
    for opt, a in _abilities(b, f, "power"):
        w = estimates.ability_value(b, f, a).total() - (spell_cost(b, f, 1) if a.get("uses") else 0.0)
        if w > 0.5 and (best is None or w > best[0]):
            best = (w, opt)
    if best is None:
        return False
    rival = _best_attack_worth(b, f)
    if spellrules.is_caster(f.char, b.t):
        spell = _pick_cast(b, f, "action")
        rival = max(rival, spell[0] if spell is not None else 0.0)
    if best[0] <= rival:
        return False
    b.do_ability(f, best[1].value)
    return f.action <= 0


def _bonus_strike(b: Battle, f: Fighter) -> None:
    """A blow with the bonus action (the off-hand, the spiritual weapon, War Priest), at the weakest in reach."""
    if f.bonus <= 0:
        return
    for opt, a in _abilities(b, f, "attack"):
        targets = opt.targets
        if not targets and a is not None:  # (War Priest strikes with the weapon in hand)
            weapons = [x for x in b.attack_options(f) if x.available and x.item_uid is not None]
            targets = b.targets_for(f, weapons[0]) if weapons else []
        if targets:
            b.do_ability(f, opt.value, min(targets, key=lambda t: t.hp))
            return


def _tend_the_fallen(b: Battle, f: Fighter) -> None:
    """A friend bleeding out comes first: a healing word from afar, a touch spell or first aid from beside them."""
    fallen = [x for x in b.team(f.team) if x.state == "down" and not x.stable]
    if not fallen:
        return
    options = {sid: ok for sid, ok, _ in b.spell_options(f)}
    for x in fallen:
        for sid in ("healing_word", "cure_wounds", "spare_the_dying"):
            if options.get(sid) and x in b.spell_targets(f, sid):
                b.do_cast(f, sid, x)
                return
    x = min(fallen, key=lambda x: b.gap(f, x))
    if b.gap(f, x) > 1 and f.move_left >= 5:
        tree = b.move_tree(f)
        occ = b.occupied_by_others(f)
        spots = [sq for sq in _ring(x, 1, f.sq) if sq in tree and grid.can_stop(sq, f.sq, occ)]
        if spots:
            b.walk(f, grid.route(tree, min(spots, key=lambda s: tree[s].cost + tree[s].risk)))
    if b.gap(f, x) <= 1 and f.action > 0 and x.state == "down" and not x.stable:
        for sid in ("cure_wounds", "spare_the_dying"):
            if options.get(sid) and x in b.spell_targets(f, sid):
                b.do_cast(f, sid, x)
                return
        b.do_help(f, x)


def _cast_something(b: Battle, f: Fighter) -> bool:
    """A caster's choice for the action: the spell worth most here - a heal where it keeps a friend standing, an area
    that catches only foes, a blessing when the fight matters, a sure hit, a cantrip - if it beats the weapon."""
    if not any(e.standing for e in b.enemies_of(f)):
        return False
    if f.bonus > 0:
        _cast_best(b, f, "bonus")
        if b.current is not f or b.outcome is not None:
            return True
    melee = any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing)
    beat = _best_attack_worth(b, f) if (f.char.cls != "wizard" or melee) else 0.0
    return _cast_best(b, f, "action", beat=beat)


def _keep_safe(b: Battle, f: Fighter) -> None:
    """A caster who has done their work steps away from blades if they can do it without being cut."""
    if not f.prefers_range:
        return
    if not any(b.gap(f, e) <= 2 for e in b.enemies_of(f) if e.standing):
        return
    tree = b.move_tree(f, risk=20.0)
    occ = b.occupied_by_others(f)
    enemies = [e for e in b.enemies_of(f) if e.standing]
    best = None
    for sq, st in tree.items():
        if st.provokes or not grid.can_stop(sq, f.sq, occ):
            continue
        d = min(grid.gap((sq[0], sq[1], f.sq), e.space) for e in enemies)
        key = (-min(d, 5), st.cost)
        if best is None or key < best[0]:
            best = (key, sq)
    if best is not None and best[1] != (f.x, f.y):
        b.walk(f, grid.route(tree, best[1]))
