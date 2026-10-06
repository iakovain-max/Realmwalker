"""How creatures fight on the grid, and how party members fight when left to themselves (Auto).

A turn is planned the way a sensible player would: find everyone worth hitting, every square you could reach this
turn, and every way of hitting them from there; weigh the chance to hit, the damage, whether it would finish them,
the opportunity attacks it would cost to get there and how exposed the square is; then walk there and strike.
Archers and casters keep their distance and look for cover; pack hunters close in together; the frightened and the
beaten run for the edge of the field. If nothing can be reached this turn, they close in (running, if that is all
there is to do). Party members on Auto also heal the fallen, bless, throw area spells where they catch only
enemies, and use their class's tricks.

Pure logic: it only calls the Battle's own actions, so everything it does is something a player could do.
"""

from __future__ import annotations

from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY, AttackOption, Battle, Fighter, _avg

CAUTION = {"beast": 2.0, "mindless": 0.5, "fanatic": 1.0, "warrior": 3.0, "bandit": 6.0, "soldier": 6.0,
           "coward": 14.0, "party": 10.0}


def take_turn(b: Battle, f: Fighter) -> None:
    """Play out `f`'s whole turn."""
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
    if f.has_trait("aggressive") and f.bonus > 0 and f.speed > 0 and \
            not any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
        f.bonus -= 1  # Aggressive: a bonus action to close in
        f.move_left += f.speed
    _fight(b, f, plain, attacks=max(1, int(f.cdef.get("multiattack", 1))))
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
    kind_melee = opt.is_melee
    for i in range(attacks):
        if b.outcome is not None or not f.can_act():
            break
        usable = [o for o in opts if o.is_melee == kind_melee and o.available]
        if not usable:
            break
        choice = usable[i % len(usable)] if multi else opt
        if not target.active or not b.in_reach(f, choice, target)[0]:
            others = [t for t in b.targets_for(f, choice) if t.side != f.side and t.active]
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
    for opt in opts:
        if opt.is_melee:
            for t in targets:
                for sq in _ring(t, opt.reach_sq, f.sq):
                    st = stops.get(sq)
                    if st is None:
                        continue
                    score = _value(b, f, opt, t, sq) - st.cost * 0.02 - st.risk * 0.1
                    if best is None or score > best[0]:
                        best = (score, sq, opt, t)
        else:
            normal, long = opt.range or (80, 320)
            squares = sorted(stops, key=lambda s: stops[s].cost)[:70]
            for t in targets:
                for sq in squares:
                    space = (sq[0], sq[1], f.sq)
                    g = grid.gap(space, t.space)
                    if g * grid.SQUARE_FT > long:
                        continue
                    cover = b.field.cover(space, t.space)
                    if cover == grid.TOTAL:
                        continue
                    st = stops[sq]
                    near = sum(1 for e in b.enemies_of(f) if e.standing and grid.gap(space, e.space) <= b.reach_of(e))
                    score = _value(b, f, opt, t, sq, cover=cover, near=near, far=g * grid.SQUARE_FT > normal)
                    score -= st.cost * 0.02 + st.risk * 0.1 + near * (0.6 if f.prefers_range else 0.25)
                    if best is None or score > best[0]:
                        best = (score, sq, opt, t)
    if best is None or best[0] <= 0:
        return None
    score, sq, opt, t = best
    return score, grid.route(tree, sq) if sq != here else [], opt, t


def _targets(b: Battle, f: Fighter) -> list[Fighter]:
    standing = [e for e in b.enemies_of(f) if e.standing and e.state != "surrendered"]
    seen = [e for e in standing if b.can_see(f, e) or b.gap(f, e) <= 1]
    targets = seen or [e for e in standing if not e.hidden]
    if not targets and f.creature is not None and f.morale_type in ("mindless", "fanatic"):
        targets = [e for e in b.side(PARTY if f.side == FOE else FOE) if e.state == "down"]
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


def _value(b: Battle, f: Fighter, opt: AttackOption, t: Fighter, sq, *, cover: int | None = None, near: int = 0,
           far: bool = False) -> float:
    """How good one attack on `t` from square `sq` is: expected damage, more if it could finish them."""
    if cover is None:
        cover = b.field.cover((sq[0], sq[1], f.sq), t.space)
        cover = 0 if cover == grid.TOTAL else cover
    ac = t.ac() + grid.COVER_AC[cover]
    need = max(2, min(20, ac - opt.bonus))
    p = (21 - need) / 20.0
    dis = near > 0 and not opt.is_melee or far or (t.dodging and opt.is_melee)
    adv = ("prone" in t.conditions and opt.is_melee) or any(c in t.conditions for c in ("restrained", "paralyzed", "stunned"))
    if f.has_trait("pack_tactics") and opt.is_melee and any(a is not f and a.standing and b.gap(a, t) <= 1 for a in b.allies_of(f)):
        adv = True
    if opt.is_melee and any(a is not f and a.standing and not a.incapacitated and grid.flanks((sq[0], sq[1], f.sq), a.space, t.space)
                            for a in b.allies_of(f)):
        adv = True  # a friend on the far side: worth walking round for
    if adv and not dis:
        p = 1 - (1 - p) ** 2
    elif dis and not adv:
        p = p * p
    dmg = _avg(opt.damage)
    value = p * dmg
    if t.hp <= dmg:
        value *= 1.6  # it could finish them
    if t.state == "down":
        value *= 0.3
    if t.concentration is not None:
        value *= 1.3
    if t.char is not None and t.char.cls == "wizard":
        value *= 1.1
    return value + 0.5


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
    """An enemy caster: its bonus-action spells first (a spiritual weapon, a shield of faith, the weapon's blow),
    then the action: heal a friend in trouble, bless the band, hold the most dangerous foe, command one to grovel,
    a withering touch on whoever is beside it, or holy fire from afar."""
    spells = b.creature_spells(f)
    enemies = [e for e in b.enemies_of(f) if e.standing]
    if not enemies:
        return
    tok = next((t for t in b.tokens if t.owner == f.id and t.kind == "spiritual_weapon"), None)
    if tok is not None and f.bonus > 0:
        near = b.spirit_targets(f)
        if near:
            f.bonus -= 1
            b._spirit_strike(f, tok, min(near, key=lambda e: e.hp))
    elif "spiritual_weapon" in spells:
        pts = b.spell_points(f, "spiritual_weapon")
        spots = [sq for e in enemies for sq in _ring(e, 1, 1) if sq in pts]
        if spots:
            b.creature_cast(f, "spiritual_weapon", point=spots[0])
    spells = b.creature_spells(f)
    if "shield_of_faith" in spells and f.concentration is None and any(b.gap(f, e) <= 2 for e in enemies):
        b.creature_cast(f, "shield_of_faith", f)
    if f.action <= 0 or b.outcome is not None:
        return
    spells = b.creature_spells(f)
    friends = [x for x in b.allies_of(f) if x.standing]
    if "cure_wounds" in spells:
        hurt = [x for x in b.spell_targets(f, "cure_wounds") if x.hp < x.max_hp * 0.4]
        if hurt:
            b.creature_cast(f, "cure_wounds", min(hurt, key=lambda x: x.hp))
            return
    if "bless" in spells and f.concentration is None and len(friends) >= 2:
        b.creature_cast(f, "bless")
        return
    if "hold_person" in spells and f.concentration is None:
        held = [e for e in b.spell_targets(f, "hold_person") if e.kind == "humanoid" and "paralyzed" not in e.conditions]
        if held:
            b.creature_cast(f, "hold_person", max(held, key=lambda e: (e.ac(), e.hp)))
            return
    beside = [e for e in enemies if b.gap(f, e) <= 1]
    if "inflict_wounds" in spells and beside:
        b.creature_cast(f, "inflict_wounds", min(beside, key=lambda e: e.hp))
        return
    if "command" in spells and beside and b.rng.chance(0.4):
        b.creature_cast(f, "command", beside[0])
        return
    if "sacred_flame" in spells and not beside:
        targets = b.spell_targets(f, "sacred_flame")
        if targets:
            b.creature_cast(f, "sacred_flame", min(targets, key=lambda e: e.hp))


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
        enemies = sum(1 for x in hit if x.side != f.side)
        friends = sum(1 for x in hit if x.side == f.side and x is not f)
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
    if "second_wind" in c.features and c.uses.get("second_wind", 0) > 0 and f.bonus > 0 and f.hp < f.max_hp // 2:
        b.do_ability(f, "second_wind")
    if b.current is not f or b.outcome is not None:
        return
    if spellrules.is_caster(c, b.t) and f.action > 0:
        if _cast_something(b, f):
            if b.current is f and b.outcome is None and f.move_left >= 5:
                _keep_safe(b, f)
            return
    if b.current is not f or b.outcome is not None:
        return
    opts = [o for o in b.attack_options(f) if o.available]
    attacks = 2 if c.level >= 5 and "extra_attack" in c.features else 1
    if "action_surge" in c.features and c.uses.get("action_surge", 0) > 0 and f.hp < f.max_hp * 0.6 \
            and len(b.enemies_of(f)) >= 2:
        b.do_ability(f, "action_surge")
        attacks *= 2 if f.action > 1 else 1
    if opts:
        struck = _fight(b, f, opts, attacks)
        if struck and b.current is f and b.outcome is None:
            _bonus_strike(b, f)
    if b.current is f and b.outcome is None and "cunning_action" in c.features and f.bonus > 0:
        if f.hp < f.max_hp // 2 and any(b.gap(f, e) <= 1 for e in b.enemies_of(f) if e.standing):
            b.do_disengage(f, bonus=True)
            _step_back(b, f)
        elif not b.hide_problem(f):
            b.do_hide(f, bonus=True)


def _bonus_strike(b: Battle, f: Fighter) -> None:
    if f.bonus <= 0:
        return
    for aid, _, ok, _ in b.class_abilities(f):
        if not ok:
            continue
        if aid == "offhand":
            opt = b.offhand_option(f)
            targets = [t for t in b.enemies_of(f) if opt is not None and b.in_reach(f, opt, t)[0]]
            if targets:
                b.do_ability(f, "offhand", min(targets, key=lambda t: t.hp))
                return
        if aid == "spirit_strike":
            targets = b.spirit_targets(f)
            if targets:
                b.do_ability(f, "spirit_strike", min(targets, key=lambda t: t.hp))
                return


def _tend_the_fallen(b: Battle, f: Fighter) -> None:
    """A friend bleeding out comes first: a healing word from afar, a touch spell or first aid from beside them."""
    fallen = [x for x in b.side(f.side) if x.state == "down" and not x.stable]
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
    """A caster's choice for the action: an area that catches only foes, a heal, a blessing, a sure hit, a cantrip."""
    options = {sid: ok for sid, ok, _ in b.spell_options(f)}
    t = b.t
    enemies = [e for e in b.enemies_of(f) if e.standing]
    if not enemies:
        return False
    # Badly hurt friends.
    for sid in ("cure_wounds", "healing_word"):
        if options.get(sid):
            hurt = [x for x in b.spell_targets(f, sid) if x.active and x.hp < x.max_hp * 0.35]
            if hurt:
                return b.do_cast(f, sid, min(hurt, key=lambda x: x.hp / max(1, x.max_hp)))
    # Bless the party at the start, if there are friends to bless.
    if options.get("bless") and f.concentration is None and b.round <= 2 and len(b.allies_of(f)) >= 2:
        return b.do_cast(f, "bless")
    if options.get("spiritual_weapon") and f.bonus > 0 and not any(tk.owner == f.id for tk in b.tokens):
        pts = b.spell_points(f, "spiritual_weapon")
        near = [sq for e in enemies for sq in _ring(e, 1, 1) if sq in pts]
        if near:
            b.do_cast(f, "spiritual_weapon", point=near[0])
    # An area spell, aimed where it catches the most foes and none of us.
    best = None
    for sid, ok in options.items():
        if not ok or sid not in t.spells:
            continue
        sp = t.spells[sid]
        if not sp.get("area") or sp["kind"] not in ("save", "sleep", "condition") or sp["level"] == 0:
            continue
        aims = b.spell_points(f, sid)
        candidates = {(e.x, e.y) for e in enemies} | {(e.x + dx, e.y + dy) for e in enemies for dx, dy in grid.DIRS8}
        for pt in candidates:
            if pt not in aims:
                continue
            cells = b.spell_area(f, sid, pt)
            hit = b.in_area(cells, sp.get("affects", "all"), f)
            spared = b.sculpted(f, sid, hit)
            foes = [x for x in hit if x.side != f.side and x.standing]
            friends = [x for x in hit if x.side == f.side and x.id not in spared]
            if friends or len(foes) < 2:
                continue
            score = sum(min(x.hp, 20) for x in foes) - sp["level"] * 3
            if best is None or score > best[0]:
                best = (score, sid, pt)
    if best is not None:
        return b.do_cast(f, best[1], point=best[2])
    # A sure strike at something nearly dead, or a cantrip.
    if options.get("magic_missile"):
        weak = [e for e in b.spell_targets(f, "magic_missile") if e.hp <= 8]
        if weak and len(enemies) >= 2:
            return b.do_cast(f, "magic_missile", min(weak, key=lambda e: e.hp))
    for sid in ("fire_bolt", "sacred_flame", "ray_of_frost", "chill_touch"):
        if options.get(sid):
            targets = b.spell_targets(f, sid)
            if f.char.cls == "cleric" and any(b.gap(f, e) <= 1 for e in enemies):
                break  # a cleric beside the enemy uses the mace
            if targets and not any(b.gap(f, e) <= 1 for e in enemies if e.standing) or (targets and sid == "sacred_flame"):
                return b.do_cast(f, sid, min(targets, key=lambda e: (e.hp, b.gap(f, e))))
    return False


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
