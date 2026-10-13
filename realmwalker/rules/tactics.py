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

from realmwalker.rules import feats, grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY, AttackOption, Battle, Fighter, _avg
from realmwalker.rules.engine import actions, estimates, query
from realmwalker.rules.engine.handlers import mastery

CAUTION = {"beast": 2.0, "mindless": 0.5, "fanatic": 1.0, "warrior": 3.0, "bandit": 6.0, "soldier": 6.0,
           "coward": 14.0, "party": 10.0}
# A creature's role (creatures.json "ai"): how much more (or less) than its nerve says it minds being struck on the way.
ROLE_CAUTION = {"brute": 0.6, "skirmisher": 1.0, "artillery": 1.4, "controller": 1.3, "leader": 1.5, "support": 1.5,
                "lurker": 1.2, "solo": 0.8}


def caution(f: Fighter) -> float:
    """How many feet of the way a blow on the way is worth avoiding: its nerve, and its role."""
    if f.char is not None:
        return CAUTION["party"]
    return CAUTION.get(f.morale_type, 4.0) * ROLE_CAUTION.get(role(f), 1.0)


def preferred_range(f: Fighter) -> int:
    """The distance in feet it likes to keep (creatures.json "ai" range; 0: in their faces)."""
    if f.char is not None:
        return 30 if f.char.cls == "wizard" else 0
    return int((f.cdef.get("ai") or {}).get("range", 0))


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
    if role(f) == "leader" and any(b.gap(a, t) <= 1 for a in b.allies_of(f) if a is not f and a.standing):
        w *= 1.2  # a leader strikes where its band is already at work
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
        _epic_moves(b, f)
    else:
        _monster_turn(b, f)


# ---------------------------------------------------------------------------- monsters
def _monster_turn(b: Battle, f: Fighter) -> None:
    opts = [o for o in b.attack_options(f) if o.available]
    breath = [o for o in opts if o.extra.get("area")]
    if breath and _try_area_attack(b, f, breath[0]):
        _rise(b, f)  # a dragon breathes, then takes to the air out of reach
        return
    if not _targets(b, f) and f.action > 0 and any(e.hidden for e in b.enemies_of(f) if e.standing):
        b.do_search(f)  # nobody in sight, but someone is hiding here
        if b.current is not f or b.outcome is not None:
            return
    plain = [o for o in opts if not o.extra.get("area")]
    _come_down(b, f, plain)
    if f.cdef.get("spells"):
        _creature_magic(b, f)
        if b.current is not f or b.outcome is not None or not f.active:
            return
        if f.action <= 0 and f.attacks_left <= 0:
            _keep_distance(b, f)
            return
        if f.concentration is not None and f.action > 0 and smarts(f) >= 1 and \
                any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing) and _best_attack_worth(b, f) < 4.0:
            _keep_distance(b, f)  # hold the spell: out of their reach, or else on guard
            if b.current is f and any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
                b.do_dodge(f)
                return
    if not plain:
        return
    if (f.has_trait("aggressive") or f.has_trait("charge")) and f.bonus > 0 and f.speed > 0 and \
            not any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
        f.bonus -= 1  # Aggressive (a bonus action to close in), or a troll's Charge (half its speed)
        f.move_left += f.speed if f.has_trait("aggressive") else f.speed // 2
    _fight(b, f, plain, attacks=max(1, int(f.cdef.get("multiattack", 1))))
    _hew(b, f)
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
    if b.outcome is None and b.current is f and f.active:
        _rise(b, f)


def _come_down(b: Battle, f: Fighter, opts: list[AttackOption]) -> None:
    """A flier aloft comes down to strike, unless it can strike from where it is."""
    if f.z <= 0 or f.fly_speed <= 0:
        return
    targets = _targets(b, f)
    if any(b.in_reach(f, o, t)[0] for o in opts if not o.is_melee for t in targets):
        return
    drop = min(f.z, f.move_left // grid.SQUARE_FT * grid.SQUARE_FT)
    if drop:
        b.do_fly(f, -drop)


def _rise(b: Battle, f: Fighter) -> None:
    """After its blows, a flier with the wits for it rises just out of the longest reach on the ground: where it can
    still hurt them next turn (a breath, a shot, a spell) or when it is bloodied. Not while it holds someone, and not
    if more than one of them would strike at it on the way up."""
    if f.fly_speed <= 0 or f.move_left < 10 or smarts(f) < 1 or b.held_by(f) or f.grappled_by is not None:
        return
    enemies = [e for e in b.enemies_of(f) if e.standing]
    if not enemies:
        return
    from_above = any(not o.is_melee or o.extra.get("area") for o in b.attack_options(f)) or bool(f.cdef.get("spells"))
    if not (from_above or f.hp <= f.max_hp // 2):
        return
    near = [e for e in enemies if b.gap(e, f) <= b.reach_of(e) and e.can_opportunity and e.reaction]
    if len(near) > 1 and not f.disengaged:
        return
    need = (max(b.reach_of(e) for e in enemies) + 1) * grid.SQUARE_FT
    up = min(need - f.z, f.move_left // grid.SQUARE_FT * grid.SQUARE_FT)
    if up >= grid.SQUARE_FT:
        b.do_fly(f, up)


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
    first = _instead_of_a_blow(b, f, opts, opt, target) if kind_melee else None
    if first == "help":
        return True
    start = 1 if first else 0
    if first and f.creature is not None:
        f.attacks_left = 0  # (the action is spent; a creature's other attacks are counted here)
    for i in range(start, attacks):
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
            struck = True
            continue
        else:
            if not b.do_attack(f, choice, target):
                break
        struck = True
    return struck


def best_plan(b: Battle, f: Fighter, opts: list[AttackOption]):
    """(score, path, option, target) for the best square to strike from this turn, or None."""
    tree = b.move_tree(f, risk=caution(f))
    occ = b.occupied_by_others(f)
    here = (f.x, f.y)
    stops = {sq: st for sq, st in tree.items() if sq == here or grid.can_stop(sq, f.sq, occ)}
    keep = preferred_range(f)
    targets = _targets(b, f)
    if not targets:
        return None
    best = None
    squares = near_at = None
    for opt in opts:
        if opt.is_melee:
            for t in targets:
                if abs(f.z - t.z) // grid.SQUARE_FT > opt.reach_sq:
                    continue  # up out of reach (or it is, from up here)
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
                    g = b.gap_from(f, sq, t)
                    if g * grid.SQUARE_FT > long:
                        continue
                    st = stops[sq]
                    less = st.cost * 0.02 + st.risk * 0.1 + near_at[sq] * (0.6 if f.prefers_range else 0.25)
                    if keep > 5 and g * grid.SQUARE_FT < keep:
                        less += (keep - g * grid.SQUARE_FT) / 10 * 0.3  # closer than it likes to be
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
        ev = p * dmg + p * _hit_effects_worth(b, f, opt, t) + (1 - p) * _miss_worth(f, opt)
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

    w = _mastery_worth(b, f, opt, t)
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


# ---------------------------------------------------------------------------- weapon masteries used on purpose
def _mastery_worth(b: Battle, f: Fighter, opt: AttackOption, t: Fighter) -> float:
    """What the weapon's trick adds to a hit (rules/engine/handlers/mastery.py): topple where friends will strike the
    prone, sap the biggest hitter, slow the one to be kept away, vex to chain hits, cleave into a crowd, push into a
    hazard or out of reach."""
    kind = mastery.of(f, opt)
    if kind is None:
        return 0.0
    threat = estimates.threat(t)
    if kind == "topple":
        if "prone" in t.conditions or not t.standing or query.condition_immune(t, "prone"):
            return 0.0
        dc = 8 + mastery.ability_mod(f, opt) + query.proficiency(f)
        melee_friends = sum(1 for a in b.allies_of(f) if a.standing and b.gap(a, t) <= 1)
        return estimates.fail_chance(b, t, "con", dc) * CONTROL["prone"] * threat * (1 + 0.5 * melee_friends)
    if kind == "sap":
        return 0.25 * threat  # the bigger its blows, the more an off blow is worth
    if kind == "slow":
        return (0.2 if f.prefers_range or preferred_range(f) > 5 else 0.05) * threat
    if kind == "vex":
        return ADVANTAGE_GAIN * 0.5 * _avg(opt.damage)  # the next blow at it comes with advantage
    if kind == "cleave" and opt.is_melee:
        near = [x for x in b.enemies_of(f) if x is not t and x.active and b.gap(x, t) <= 1 and b.in_reach(f, opt, x)[0]]
        if near:
            return 0.5 * max(0.0, _avg(opt.damage) - max(0, mastery.ability_mod(f, opt)))
    if kind == "push" and _push_lands_in_harm(b, f, t):
        return 0.6 * threat
    return 0.0


def _miss_worth(f: Fighter, opt: AttackOption) -> float:
    """Graze: a miss still deals the attack's ability bonus."""
    return float(max(0, mastery.ability_mod(f, opt))) if mastery.of(f, opt) == "graze" else 0.0


def _push_lands_in_harm(b: Battle, f: Fighter, t: Fighter) -> bool:
    """Ten feet straight back from `f` would put `t` in a burning, freezing or otherwise harmful zone."""
    sx, sy = grid.centre(*f.space)
    tx, ty = grid.centre(*t.space)
    dx = 0 if abs(tx - sx) < 0.5 else (1 if tx > sx else -1)
    dy = 0 if abs(ty - sy) < 0.5 else (1 if ty > sy else -1)
    if dx == 0 and dy == 0:
        return False
    cells = {(t.x + dx * k, t.y + dy * k) for k in (1, 2)}
    return any((z.kind == "web" or z.damage) and cells & set(z.cells) for z in b.zones)


def mastery_choice(b: Battle, f: Fighter, kind: str, t: Fighter) -> bool:
    """The battle's judgement on a free mastery choice (the enemy, the Auto, and the default for the player)."""
    if kind == "topple":  # prone helps those beside it and hinders those shooting at it
        if "prone" in t.conditions:
            return False
        melee = sum(1 for a in b.allies_of(f) if a.standing and b.gap(a, t) <= 1)
        shooters = sum(1 for a in b.allies_of(f) if a is not f and a.active and a.prefers_range)
        return melee >= shooters
    if kind == "push":
        if _push_lands_in_harm(b, f, t):
            return True
        if f.attacks_left > 0 and not f.prefers_range:
            return False  # out of reach of the next blow
        return not t.prefers_range  # it must spend its feet to come back; an archer would only thank you
    return True


def cleave_target(b: Battle, f: Fighter, near: list[Fighter]) -> Fighter | None:
    """Whom to carry the blow into: the one it could finish, else the one most worth hurting."""
    return max(near, key=lambda x: (x.hp <= 6, target_weight(b, f, x), -x.hp))


def _opening(b: Battle, f: Fighter, opt: AttackOption, t: Fighter) -> float:
    """A creature's opening move (creatures' "ai" opens_with): worth more while the target lacks what it brings."""
    if f.creature is None or (f.cdef.get("ai") or {}).get("opens_with") != opt.extra.get("id"):
        return 1.0
    brings = [e.get("condition") for e in opt.extra.get("on_hit", ()) if e.get("op") == "condition"]
    return 1.0 if any(c in t.conditions for c in brings) else 3.0


ADVANTAGE_GAIN = 0.45  # how much more a blow is worth with advantage (a 55% hit becomes an 80% one)


def _instead_of_a_blow(b: Battle, f: Fighter, opts: list[AttackOption], opt: AttackOption, t: Fighter) -> str | None:
    """Something better than the first blow, right beside the target (2024: a shove or a grab takes one attack; Help
    takes the action): knock it down when friends beside it will strike it next; grab a caster who would step away;
    distract it when one's own blow is feeble and a friend's is not. None: strike as planned."""
    if smarts(f) < 1 or b.gap(f, t) > 1 or not t.standing or not b.can_grapple(f, t)[0]:
        return None
    friends = [a for a in b.allies_of(f) if a is not f and a.standing and a.can_act() and b.gap(a, t) <= 1]
    mine = _value(b, f, opt, t, (f.x, f.y))
    pf = estimates.fail_chance(b, t, max(("str", "dex"), key=lambda ab: t.save_bonus(ab)), query.unarmed_dc(f))
    if "prone" not in t.conditions and friends:
        # Advantage makes a blow worth about half again as much: the friends' blows, and its own that are left.
        gain = ADVANTAGE_GAIN * (sum(_best_attack_worth(b, a) for a in friends) + mine * (_plan_attacks(f, opt) - 1))
        if pf * gain > mine:
            b.do_shove(f, t, "prone")
            return "shove"
    if smarts(f) >= 2 and t.prefers_range and "grappled" not in t.conditions and _plan_attacks(f, opt) > 1 and pf > 0.4:
        b.do_grapple(f, t)
        return "grapple"
    if f.creature is not None and friends and f.action > 0 and _plan_attacks(f, opt) == 1:
        best_friend = max(_best_attack_worth(b, a) for a in friends)
        if best_friend * ADVANTAGE_GAIN > mine * 1.5:
            b.do_help(f, t)
            return "help"
    return None


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
    tree = b.move_tree(f, budget=600, risk=caution(f))
    occ = b.occupied_by_others(f)
    if all(abs(t.z - f.z) // grid.SQUARE_FT > reach for t in targets) and f.fly_speed <= 0:
        _wait_below(b, f, targets, reach, tree, occ)  # they are up out of reach: wait for them to come down
        return
    best = None
    for t in targets:
        for sq in _ring(t, reach, f.sq):
            st = tree.get(sq)
            if st is None or not grid.can_stop(sq, f.sq, occ):
                continue
            if best is None or st.cost + st.risk < best[0]:
                best = (st.cost + st.risk, sq)
    if best is None and _break_through(b, f, targets, reach):
        return
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
    cost = tree[best[1]].cost * (2 if b.dragging(f) else 1)
    if ranged and f.action > 0 and preferred_range(f) > 5 and cost > f.move_left:
        _walk_budget(b, f, path, tree)  # an archer does not run in: it closes a little and waits for a shot
        if b.current is f and f.action > 0 and b.outcome is None:
            b.do_ready(f, "sight")
        return
    if f.action > 0 and not ranged and cost > f.move_left:
        if role(f) == "lurker" and b.hide_problem(f) is None:
            b.do_hide(f)  # a lurker waits in hiding for them to come
            return
        b.do_dash(f)
    _walk_budget(b, f, path, tree)


def _wait_below(b: Battle, f: Fighter, targets: list[Fighter], reach: int, tree: dict, occ: set) -> None:
    """Every enemy is in the air out of reach: stand under the nearest (not crowding it) with a blow readied for when
    it comes down to strike (the Ready action)."""
    t = min(targets, key=lambda t: b.gap(f, t))
    spots = [sq for sq in _ring(t, reach, f.sq) if sq in tree and grid.can_stop(sq, f.sq, occ)]
    if spots and (f.x, f.y) not in spots:
        _walk_budget(b, f, grid.route(tree, min(spots, key=lambda s: tree[s].cost + tree[s].risk)), tree)
    if b.current is f and b.outcome is None and f.action > 0:
        b.do_ready(f, "reach")


def _walk_budget(b: Battle, f: Fighter, path: list[tuple[int, int]], tree: dict) -> None:
    """Walk as far along a path as this turn's movement goes, stopping only where there is room to stand. The way's
    own costs say how far that is (climbing, swimming, leaping and dragging included)."""
    occ = b.occupied_by_others(f)
    heavy = 2 if b.dragging(f) else 1
    cut = 0
    for i, sq in enumerate(path):
        if tree[sq].cost * heavy > f.move_left:
            break
        if grid.can_stop(sq, f.sq, occ):
            cut = i + 1
    if cut:
        b.walk(f, path[:cut])


def _break_through(b: Battle, f: Fighter, targets: list[Fighter], reach: int) -> bool:
    """Walled off by a door, a barricade or a cart: those with the wits (or the brawn) for it break it down. True if
    it struck at something (or walked up to it)."""
    if f.char is not None or (smarts(f) < 1 and role(f) != "brute") or not b.has_action(f):
        return False
    spec = b.t.rules.get("objects", {}).get("terrain", {})
    through = {(x, y) for x in range(b.field.width) for y in range(b.field.height) if b.field.name(x, y) in spec}
    if not through:
        return False
    tree = b.move_tree(f, budget=600, risk=caution(f), through=through)
    occ = b.occupied_by_others(f)
    goal = None
    for t in targets:
        for sq in _ring(t, reach, f.sq):
            st = tree.get(sq)
            if st is not None and grid.can_stop(sq, f.sq, occ) and (goal is None or st.cost < goal[0]):
                goal = (st.cost, sq)
    if goal is None:
        return False
    path = grid.route(tree, goal[1])
    first = next((i for i, sq in enumerate(path) if any(c in through for c in grid.cells(sq[0], sq[1], f.sq))), None)
    if first is None:
        return False
    cell = next(c for c in grid.cells(path[first][0], path[first][1], f.sq) if c in through)
    before = path[:first]
    if before:
        real = b.move_tree(f, risk=caution(f))
        if before[-1] in real:
            _walk_budget(b, f, grid.route(real, before[-1]), real)
    opt = b.breakables(f).get(cell)
    if opt is not None and b.outcome is None and b.current is f:
        return b.attack_object(f, opt, cell) or True
    return bool(before)


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
    if f.action > 0 and tree[goal].cost > f.move_left:
        b.do_dash(f)
    _walk_budget(b, f, path, tree)
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
    _divine_help(b, f)
    if b.current is not f or b.outcome is not None:
        return
    if f.action > 0 and _use_power(b, f):
        if b.current is f and b.outcome is None:
            _bonus_strike(b, f)
        if b.current is f and b.outcome is None and f.move_left >= 5:
            _keep_safe(b, f)
        return
    if (spellrules.is_caster(c, b.t) or feats.innate_spells(c, b.t)) and f.action > 0:
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
    if f.bonus > 0 and any(e.standing and not b.can_see(f, e) for e in b.enemies_of(f)):
        for opt, _ in _abilities(b, f, "sense"):  # a foe it cannot see: feel for it through the stone
            b.do_ability(f, opt.value)
            break
    if opts and b.has_action(f) and f.bonus > 0 and best_plan(b, f, opts) is None:
        # Nothing in reach this turn: run with the bonus action (Adrenaline Rush, Cunning Action) to close the gap.
        dash = next((opt for opt, a in _abilities(b, f, "move") if a.get("via") == "dash"), None)
        if dash is not None:
            b.do_ability(f, dash.value)
    if opts and b.has_action(f) and f.bonus > 0 and f.moved_feet == 0:
        _steady_aim(b, f, opts)
    if opts and b.has_action(f):  # (first aid for a fallen friend may have taken the action)
        struck = _fight(b, f, opts, attacks)
        if struck and b.current is f and b.outcome is None:
            _bonus_strike(b, f)
    if b.current is f and b.outcome is None and f.bonus > 0:
        _mind_shove(b, f)
    if b.current is f and b.outcome is None and f.bonus > 0:
        _quick_sense(b, f)
    elif b.current is f and b.outcome is None and f.move_left >= 5:
        _keep_safe(b, f)
    if b.current is f and b.outcome is None and f.bonus > 0:  # Cunning Action: away when hurt, else out of sight
        moves = {a["via"]: opt for opt, a in _abilities(b, f, "move")}
        if "disengage" in moves and f.hp < f.max_hp // 2 and \
                any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
            b.do_ability(f, moves["disengage"].value)
            _step_back(b, f)
        elif "hide" in moves and not b.hide_problem(f):
            b.do_ability(f, moves["hide"].value)


def cunning_strike(b: Battle, f: Fighter, target: Fighter, opts: list[str], dice_left: int) -> str | None:
    """A rogue's Cunning Strike, by what the fight needs: away when hurt and pressed; a strong foe knocked out,
    dazed or blinded; a foe tripped where friends can fall on it; poison where it takes; the dice kept otherwise."""
    pressed = sum(1 for e in b.enemies_of(f) if e.standing and b.gap(f, e) <= 1)
    if "withdraw" in opts and pressed and (f.hp < f.max_hp // 2 or f.prefers_range):
        return "withdraw"
    if "stealth" in opts:
        return "stealth"
    strong = target.hp > 15 + 4 * dice_left
    if strong and "knock_out" in opts and dice_left >= 8:
        return "knock_out"
    if strong and "daze" in opts:
        return "daze"
    if "trip" in opts and target.standing and \
            any(x is not f and x.active and b.gap(x, target) <= 1 for x in b.allies_of(f)):
        return "trip"
    if "poison" in opts and "poisoned" not in target.conditions and not query.condition_immune(target, "poisoned"):
        return "poison"
    if strong and "obscure" in opts:
        return "obscure"
    return None


def tactical_mastery(b: Battle, f: Fighter, kind: str, target: Fighter) -> str:
    """Tactical Master: drive a foe into harm, sap the blow of a dangerous one still standing, or keep the weapon's
    own trick when it is the better (topple, vex, cleave...)."""
    from realmwalker.rules.engine.handlers.mastery import PUSHABLE

    if target.size in PUSHABLE and target.active and _push_lands_in_harm(b, f, target):
        return "push"
    if kind in ("graze", "nick", "slow", "push") and target.active:
        return "sap"
    return kind


def _divine_help(b: Battle, f: Fighter) -> None:
    """A cleric's Channel Divinity for friends: Divine Spark on a friend in a bad way, and War God's Blessing (Shield
    of Faith on the hard-pressed, a Spiritual Weapon when foes are near) for the bonus action."""
    for opt, a in _abilities(b, f, "heal_other"):
        low = [x for x in opt.targets if x.state == "down" or x.hp < x.max_hp // 3]
        if low and f.action > 0:
            b.do_ability(f, opt.value, min(low, key=lambda x: (x.state != "down", x.hp, x.id)))
            break
    if b.current is not f or b.outcome is not None or f.bonus <= 0:
        return
    for opt, a in _abilities(b, f, "bless"):
        if opt.value == "blessing_weapon" and not any(t.owner == f.id for t in b.tokens):
            b.do_ability(f, opt.value)
            return
        if opt.value == "blessing_shield" and f.hp < f.max_hp // 2 and f.concentration is None:
            b.do_ability(f, opt.value)
            return


def _steady_aim(b: Battle, f: Fighter, opts: list) -> None:
    """A rogue who can strike from where they stand, with a bow or a thrown blade, aims first (Steady Aim)."""
    for opt, _ in _abilities(b, f, "aim"):
        ranged = [o for o in opts if o.kind == "ranged"]
        if any(b.in_reach(f, o, e)[0] for o in ranged for e in b.enemies_of(f) if e.standing):
            b.do_ability(f, opt.value)
        return


def _epic_moves(b: Battle, f: Fighter) -> None:
    """The epic boons' moves at the end of a turn: Blink Steps away from the foes around a hurt or far-reaching
    fighter, then Merge with Shadows with the bonus action left (unseen until they next act)."""
    if b.current is not f or b.outcome is not None:
        return
    for opt, _ in _abilities(b, f, "escape"):
        beside = any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing)
        if beside and (f.prefers_range or f.hp < f.max_hp // 2):
            b.do_ability(f, opt.value)
        break
    if b.current is f and b.outcome is None and f.bonus > 0:
        for opt, _ in _abilities(b, f, "hide"):
            b.do_ability(f, opt.value)
            break


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
        return "attack" if opt.value in ("offhand", "spirit_strike", "hew", "pole_strike") else "other"
    if a.get("does"):
        return a["does"]  # (said in the data: Stonecunning "sense")
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


def _hew(b: Battle, f: Fighter) -> None:
    """Great Weapon Master's Hew in a creature's hands: the bonus-action blow after a critical hit or a kill."""
    from realmwalker.rules.engine.handlers import general_feats

    if b.outcome is not None or b.current is not f or not f.active or f.bonus <= 0 or not general_feats.hew_ready(b, f):
        return
    opt = b.feat_blow_option(f, "hew")
    near = [e for e in b.enemies_of(f) if e.active and opt is not None and b.in_reach(f, opt, e)[0]]
    if near:
        b.do_feat_blow(f, "hew", min(near, key=lambda e: (e.hp, e.id)))


def _mind_shove(b: Battle, f: Fighter) -> None:
    """Telekinetic: shove a foe into harm, or off a friend who is hurt or casting."""
    for opt, a in _abilities(b, f, "shove"):
        def worth(t):
            if _push_lands_in_harm(b, f, t):
                return 3.0
            pressed = [x for x in b.allies_of(f) if x is not f and x.active and b.gap(x, t) <= 1
                       and (x.hp < x.max_hp // 2 or x.prefers_range or x.concentration is not None)]
            own_blow = b.gap(f, t) <= 1 and not f.prefers_range
            return 1.0 if pressed and not own_blow else 0.0
        best = max(opt.targets, key=lambda t: (worth(t), -t.id), default=None)
        if best is not None and worth(best) > 0:
            b.do_ability(f, opt.value, best)
        return


def _quick_sense(b: Battle, f: Fighter) -> None:
    """Keen Mind's and Observant's bonus actions: Study a foe not yet known, Search for one hiding."""
    if f.bonus <= 0:
        return
    moves = {a["via"]: (opt, a) for opt, a in _abilities(b, f, "move")}
    if "search" in moves and any(e.hidden and e.standing for e in b.enemies_of(f)):
        b.do_ability(f, moves["search"][0].value)
    elif "study" in moves and moves["study"][0].targets:
        b.do_ability(f, moves["study"][0].value, max(moves["study"][0].targets, key=lambda t: (estimates.threat(t), -t.id)))


def _bonus_strike(b: Battle, f: Fighter) -> None:
    """A blow with the bonus action (the off-hand, the spiritual weapon, War Priest), at the weakest in reach; with a
    Nick weapon the off-hand blow is part of the Attack and costs no bonus action."""
    if f.bonus <= 0 and not mastery.nick_ready(b, f):
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
