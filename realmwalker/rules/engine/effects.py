"""Effect operations: what spells (and, in time, abilities and magic items) do, as data (docs/EXPANSIONS.md §4.3.2).

A spell's `effects` is a list of ops, run in order when it is cast (`cast`). A top-level op picks its own targets from
the spell's aim (`target`: enemy, ally, self, all_allies, downed_ally, dead_ally, point, direction; `area`; `affects`);
an op inside another (`on_hit`, `on_fail`, `then`) works on the creature the outer op was dealing with.

    attack     a spell attack: attack (ranged|melee), damage + type, up (dice per slot level above), scaling
               ("cantrip"), rays + rays_up (one attack each, re-aimed as targets fall), on_hit [ops]
    darts      sure hits: count + count_up, damage + type, each at the weakest when the first falls (Magic Missile)
    save       a saving throw: ability, damage (one or a list of {dice, type, up}), half (true: half on a save), cover
               (false: cover does not help), kinds / not_kinds (who it works on), sure_save (traits that always
               succeed), on_fail [ops]
    condition  condition, and how it ends: ends ("own_turn_end", "caster_turn_start"...), rounds (the old way),
               immune_as (a condition that, if it is immune to it, keeps this off too: Suggestion's charm),
               repeat_save (shaken off with the same save at the end of each of its turns), on_damage, then
               {save, on_fail}; while the spell needs concentration, the condition ends with it
    heal       dice, add_mod, up, mends_wound; count / count_up for several
    modifier   buff {...} for `rounds` (a lasting spell outlives the fight: rules/spells.py); needs (a condition
               the creature must have for it to take: Otto's dance rides on its charm)
    zone       zone (web, ice, fire, fog, caltrops, bearings), rounds, dc (a fixed DC); a web catches (Dexterity save,
               Restrained); caltrops and ball bearings catch whoever walks in (Battle._zone_underfoot)
    aura       an emanation that moves with the caster and hurts enemies in it (Spirit Guardians)
    guardian   a token at a point that hurts enemies who come near, until its strength is spent
    summon     a spiritual weapon at a point: it strikes now and on later turns with a bonus action
    teleport   the caster to the point (Misty Step)
    push       feet, straight away from the caster or the point
    ignite     dry ground in the area catches; burn {rounds, damage}: the area keeps burning
    slow       feet off its speed, until the start of the caster's next turn
    no_opportunity, no_heal, mark   (until a turn ends or starts: see each)
    lose_turn  it spends its next turn grovelling on the ground (Command)
    ally       kind ("steed"): a creature that fights for the caster appears beside them (Find Steed;
               rules/allies.summon, Battle.add_ally); kind "summon" with creature (an id with a `summon` record):
               a spirit at the point, its numbers for the slot, gone when the concentration ends (Summon Beast...:
               rules/allies.summon_spirit); kind "objects": things lying about, as many as the caster's spellcasting
               modifier, acting only when commanded (Animate Objects: rules/allies.animate_objects)
    if_condition  condition, ops [ops]: those ops only if the creature has the condition now (Rotting Claw)
    burning    it catches fire (1d4 fire at the start of each of its turns, until put out with an action)
    damage     damage that has already landed (a stat block's extra harm): damage + type
    stabilize, restore (conditions, one, disease), revive (consumes, within_rounds), identify (outside a fight)
    gain_action (one more action this turn), say (a line: {name}, {their}), special (Python by id: SPECIAL)

The second wave (D.2):
    attack     drain: the caster heals that share of the damage dealt (Vampiric Touch: 0.5); spread: each ray at
               a different creature (Steel Wind Strike)
    condition  control: the one it holds fights for the caster's side (Dominate); damage_save: each time it takes
               damage it saves again, and a success ends it
    zone       fail (a condition a failed save brings: "restrained" holds, "prone", "retching"), rough (difficult
               terrain), dark (heavily obscured), held ("4d8|2d8": the damage and its `up` for one already
               held, on a failed save each turn), frees (that save frees it); "stone" and "force" raise a wall on the area's free squares (the
               ground comes back when the spell ends); "wind" turns ordinary missiles aside
    banish     how ("banished" | "sphere"), max_size, home (false: it comes back even from its own plane), below_hp (only if it has no more hit points left: Banishing Smite): off
               the field while the caster concentrates (Battle.send_away)
    dispel     ends every spell on the creature at the point and on the ground there: of the slot's level or lower
               at once, higher ones on a check (10 + the spell's level); Spell Breaker adds proficiency and keeps
               the slot when nothing ends; never a spell marked `no_dispel` (Forcecage)

The third wave (D.3):
    spell      `leap` (feet): a one-target spell's extra targets (`targets`, `targets_up`) must be that close to the
               first target, nearest it first (Chain Lightning: targets 4, targets_up 1, leap 30)
    attack     with no damage: a touch that only carries its on_hit (Plane Shift)
    save       dust (a creature it brings to 0 hit points is dust: dead, and nothing brings it back: Disintegrate);
               max_hp_loss (a failed save lowers its hit point maximum by the damage taken, for the fight: Harm)
    condition  petrify (with save): it saves at the end of each of its turns; three successes free it, three
               failures turn it to stone (Petrified while the spell lasts; for good from an instant spell)
    heal       per_up: hit points more for each slot level above (Heal: dice "70", per_up 10)
    temp_hp    share (spell target all_allies, count): the amount divided evenly among up to `count` friends in
               range (Power Word Fortify)
    zone       "blades" and "thorns" (a save on entering or starting a turn there; rough, dark as said), "celestial"
               (with heal + heal_up + add_mod: the caster's friends in it are healed once a turn, foes save against
               its damage; friends_safe), "icewall" (a wall like stone; with damage and catch, those standing in
               its area as it rises save against it)
    banish     how "cage" (Forcecage's box: everyone in the area is sealed off, as by the sphere); `forever` (sent
               from this plane for good, no concentration needed, and beaten: Plane Shift, Divine Word); kinds
    by_hp      tiers [[most, [ops]], ...]: the first tier whose number is at least its hit points now (Divine Word)
    slay       it dies outright; max_hp: only if it has that many hit points or fewer (Power Word Kill)
    lift       feet: it falls upward and hangs there while the caster concentrates, then falls (Reverse Gravity;
               under a roof it strikes the ceiling twenty feet up); gentle (Levitate): it rises, roof or not, unhurt,
               and floats down unhurt when the spell ends
    one_of     choices [[ops], ...] and a die: one of them for each creature; a face past the choices brings two
               (Prismatic Spray's rays)
    summon     on_hit [ops]: what the conjured thing's hit brings besides its damage (Conjure Fey's fear)

The fourth wave (D.4):
    spell      `spheres` (with an area): that many spheres, the others laid by the battle where they catch the most
               foes and the fewest friends, each creature caught once (Meteor Swarm: Battle._more_spheres)
    heal       full (every hit point it lacks: Power Word Heal); pool (hit points shared among the friends in
               range, the most hurt first: Mass Heal, 700); restore [conditions] ended on each one healed
    zone       follow (it moves with the caster, the area's size round them: Antimagic Field); breaks (a failed
               save also breaks concentration: Earthquake, "quake"); "embers" (Incendiary Cloud); "prismatic" (a
               wall like stone) with near (feet: a ring of "glare" beside it, foes only: near_save, near_fail and
               lasts, the rounds the failure's condition lasts); "storm" with stages [{ops, count, say, rough,
               dark}, ...]: at the start of each of the caster's later turns the next stage (the last again and
               again) runs its ops on each creature under it, `count` of them at most (Storm of Vengeance:
               Battle._storm_turn)
    banish     escape {skill, dc}: each of its turns goes on a check, and a success brings it back and ends the
               spell (Maze: Battle._maze_turn)
    time_stop  dice ("1d4+1"): the caster takes that many more turns in a row; it ends when an action or an
               effect of theirs reaches another creature (Battle._more_time, combat.TOUCHES)

Servants (F.4):
    rise       as (a creature id), types (creature kinds): a creature of those kinds the spell has killed rises at
               the start of its caster's next turn as `as`, on the caster's side (Finger of Death's zombie:
               Battle.mark_rising, _rise_as_zombies; kept after the fight by rules/servants.after)

Shapes (F.6):
    shape      forms (creature kinds, or "any"): while the caster concentrates, the target is another creature
               (Battle.shape: the form's numbers, its own hit points kept, temporary hit points the form's; ends with
               them, the concentration or the fight); a friend is willing and takes the strongest form, a foe saves
               (Wisdom) or takes the weakest (rules/shapes.py)
               F.8: cr (a fixed cap), size (the largest form), not (kinds never taken), keeps ("mind",
               "proficiencies", "spells"), leave (a Bonus Action out), shift ("self", "caster": a Magic action to
               another form), hours (it outlasts the fight: rules/shapes.record); the spell's target all_allies takes
               the willing within range (`willing`: every friend that casts no spells, never the caster)

Outside a fight (Part E):
    max_up     amount (dice), per_up, count: the hit point maximum and hit points go up while the spell lasts (Aid;
               rules/spells.raise_max); in a fight too, on up to `count` friends in range
    revive     within_days (instead of within_rounds), hp ("all" for every hit point), toll (the penalty to d20
               tests that a long rest takes down by one), closes (mortal wounds, poison), regrow (lost parts),
               cures (diseases and curses), species ("new": Reincarnate) - for the fallen (game/revival.py)
    road       does: one of rules/spells.ROAD_USES (food, water, wards on the camp...: game/spellwork.py); never
               cast in a fight (the spell has "road_only" or "minutes")

Unknown ops are data errors at start-up (rules/engine/check.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from realmwalker.core import dice
from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import conditions, durations, events, statblocks

OPS: dict[str, Callable] = {}
WALLS = ("stone", "force", "icewall", "prismatic")  # zones that rise as walls on the free squares of their area
GROUND = ("tentacles", "cloud", "stench", "hunger", "insects", "sleet", "radiance", "spirits", "elemental", "blades",
          "thorns", "celestial", "quake", "embers", "glare")  # zones whose harm is Battle._ground's: a save, and
# what a failure brings
ENERGY = ("acid", "cold", "fire", "lightning", "thunder")  # (Protection from Energy's choice)
SPECIAL: dict[str, Callable] = {}  # what an op {"op": "special", "handler": id} calls (rules/engine/handlers/)


def op(name: str):
    def register(fn: Callable) -> Callable:
        OPS[name] = fn
        return fn
    return register


def special(name: str):
    """Register Python for an effect the ops cannot say ({"op": "special", "handler": name})."""
    def register(fn: Callable) -> Callable:
        SPECIAL[name] = fn
        return fn
    return register


@dataclass
class Cast:
    """One casting: who, what, at whom or where, and the numbers it was cast with."""
    b: Any
    caster: Any
    sid: str
    spell: dict
    target: Any
    point: tuple | None
    area: list = field(default_factory=list)
    up: int = 0  # slot levels above the spell's own
    mod: int = 0  # the caster's spellcasting modifier
    dc: int = 10
    bonus: int = 0  # spell attack bonus
    mult: int = 1  # cantrip dice multiplier
    level: int = 0  # the level it was cast at
    empowered: int = 0  # damage added to one damage roll (Empowered Evocation, Potent Spellcasting)
    maximize: bool = False  # every damage die at its highest (an evoker's Overchannel)
    slotted: bool = True  # cast with a spell slot (not a scroll, a free cast, an item's or a creature's own magic)
    crit: bool = False  # riding on a critical hit (a smite): its damage dice doubled
    pushed: list = field(default_factory=list)  # (fighter, feet) to throw back once everyone has saved


MECHANICS = (("attack", "attack"), ("darts", "darts"), ("save", "save"), ("heal", "heal"), ("stabilize", "heal"),
             ("restore", "heal"), ("revive", "heal"), ("modifier", "buff"), ("teleport", "teleport"), ("zone", "zone"),
             ("summon", "summon"), ("guardian", "summon"), ("aura", "aura"), ("ally", "summon"))


def mechanic(spell: dict) -> str:
    """What a cast does, in one word, for the board and the sounds (its look is `fx`): attack, save, heal..."""
    if spell.get("fx") == "sleep":
        return "sleep"
    ops = {o["op"] for o in spell.get("effects", ())}
    return next((word for op, word in MECHANICS if op in ops), "")


def cast(b, f, sid: str, spell: dict, target, point, *, up: int, mod: int, dc: int, bonus: int, mult: int,
         level: int, slotted: bool = True) -> None:
    """A spell's effects, once it has been paid for (by a party caster, or a monster's own magic)."""
    area = b.spell_area(f, sid, point, target) if spell.get("area") else []
    shut = [x for x in b.fighters if (x.buffs or x.char is not None) and warded(b, f, x, level, sid)]
    stolen = []
    if not spell.get("thrown") and not spell.get("again_of"):
        from realmwalker.rules.engine.handlers import arcane

        stolen = arcane.spell_thief(b, f, spell, sid, level, target, area)  # (an Arcane Trickster's reaction)
        shut += stolen
    if shut and area:  # (Globe of Invulnerability: its barrier is left out of the spell's area)
        area = [sq for sq in area if not any(sq in x.cells for x in shut)]
    if spell.get("thrown"):
        b.say(f"{f.the_name} throws a flask: <danger>{spell['name'].lower()}</>!", "info")
    elif spell.get("again_of"):
        b.say(f"{f.the_name}: <magic>{spell['name']}</>.", "magic")
    else:
        b.say(f"{f.the_name} casts <magic>{spell['name']}</>.", "magic")
    if not spell.get("ability"):
        from realmwalker.rules.engine import marks

        marks.acted(b, f)  # (Invisibility ends with a casting)
    if spellrules.harms(spell) or spell.get("smite_with"):
        from realmwalker.rules.engine import marks

        marks.end_sanctuary(f)  # (Sanctuary ends when the warded one turns on an enemy)
    b._event("cast", by=f.id, to=target.id if target is not None else None, spell=sid, effect=mechanic(spell),
             look=spell.get("fx", ""), dtype=spellrules.main_type(spell), area=list(area), point=point,
             shape=(spell.get("area") or {}).get("shape", ""))
    if spell.get("concentration"):
        b._start_concentration(f, sid, spell)
        f.concentration.update(target=target.id if target is not None else None, up=up)  # (for its follow-up)
    events.emit(b, "spell_cast", actor=f, spell=spell, sid=sid, level=level, slotted=slotted)  # an Arcane Ward...
    c = Cast(b, f, sid, spell, target, point, list(area), up, mod, dc, bonus, mult, level, slotted=slotted)
    if f.char is not None and spell.get("school") == "evocation" and f.char.cls == "wizard" \
            and f.has_trait("empowered_evocation"):
        c.empowered = mod
    if f.char is not None and spell.get("level") == 0 and "cleric" in spell.get("classes", ()) \
            and f.has_trait("blessed_potent_spellcasting"):
        c.empowered = max(c.empowered, f.mod("wis"))  # (a cleric's Potent Spellcasting)
    if slotted and 1 <= level <= 5 and f.char is not None and "wizard" in spell.get("classes", ()) \
            and f.has_trait("overchannel") and any(spellrules.damage_parts(o) for o in spellrules.ops(spell)):
        from realmwalker.rules.engine.handlers import wizard

        c.maximize = wizard.overchannel(b, f, spell, level)
    if target is not None and target in stolen:
        return  # (Spell Thief: the spell passes them by; its words were said)
    if target is not None and target in shut:
        if target.char is not None and target.char.effects.get(f"immune_spell:{sid}", 0) > 0:
            b.say(f"{spell['name']} does not touch {target.the_name}: a wish keeps it off.", "magic")
        else:
            b.say(f"The spell breaks against the shimmering barrier around {target.the_name}.", "magic")
        return
    before = b.__dict__.get("_casting")
    b._casting = f if not spell.get("ability") and "item" not in spell.get("classes", ()) else None
    try:
        if target is not None and target.team != f.team and spellrules.harms(spell) and not spell.get("area") \
                and not spellrules.has_op(spell, "attack"):  # (an attack roll meets Sanctuary in Battle._attack)
            from realmwalker.rules.engine import marks

            if marks.sanctuary_stops(b, f, target):
                return  # (the spell is lost: Sanctuary)
        run(c, spell.get("effects", ()))
        if c.maximize:
            from realmwalker.rules.engine.handlers import wizard

            wizard.overchannel_price(b, f)
    finally:
        from realmwalker.rules.engine.handlers import arcane

        arcane.spend_struck(b, f)  # (Eldritch Strike: spent on the save it weakened)
        b._casting = before


def run(c: Cast, ops, victim=None) -> None:
    for o in ops:
        OPS[o["op"]](c, o, victim)


def expr(c: Cast, base: str, up: str = "", *, scaling: bool = False, empower: bool = False) -> str:
    """A dice expression with the cantrip multiplier, the slot levels above and an evoker's bonus worked in."""
    n, sides, flat = dice.parse(base)
    if scaling:
        n *= c.mult
    if up and c.up:
        un, us, _ = dice.parse(up)
        if us == sides:
            n += un * c.up
    if empower:
        flat += c.empowered
    if c.maximize:
        return str(n * sides + flat)  # (Overchannel: the greatest the dice can do)
    if not n:
        return str(flat)
    return f"{n}d{sides}{'+' + str(flat) if flat > 0 else (str(flat) if flat < 0 else '')}"


def potent(c: Cast) -> bool:
    """An evoker's Potent Cantrip: a cantrip that misses, or that is saved against, still does half its damage."""
    return c.spell.get("level") == 0 and c.caster.char is not None and c.caster.has_trait("potent_cantrip") \
        and not c.spell.get("ability") and "item" not in c.spell.get("classes", ())


def _allowed(o: dict, x) -> bool:
    if o.get("kinds") and x.kind not in o["kinds"]:
        return False
    if o.get("not_kinds") and x.kind in o["not_kinds"]:
        return False
    return True


def _targets(c: Cast) -> list:
    """The creature(s) a spell aimed at one target works on: the target, and with a higher slot more of the same kind
    (Hold Person, Command), nearest first."""
    return many(c.b, c.caster, c.sid, c.spell, c.target, c.up, level=c.level)


def many(b, f, sid: str, spell: dict, target, up: int, *, level: int | None = None) -> list:
    """The creatures a one-target spell works on: the target, and `targets` - 1 (+ `targets_up` a slot level above)
    more of the same kind, nearest the caster first; with `leap` (feet), only those that close to the first target,
    nearest it first (Chain Lightning's bolts)."""
    if target is None:
        return []
    out = [target]
    extra = int(spell.get("targets", 1)) - 1 + int(spell.get("targets_up", 0)) * up
    if extra:
        mine = spell["target"] == "ally"  # (a blessing may be on the caster too: Aid)
        others = [x for x in b.spell_targets(f, sid) if x is not target and (mine or x is not f)
                  and (level is None or not warded(b, f, x, level))]
        if spell.get("leap"):
            n = int(spell["leap"]) // grid.SQUARE_FT
            others = [x for x in others if b.gap(target, x) <= n]
            others.sort(key=lambda x: (b.gap(target, x), b.gap(f, x)))
        else:
            others.sort(key=lambda x: b.gap(f, x))
        out += others[:extra]
    return out


# ---------------------------------------------------------------------------- attacks and damage
@op("attack")
def _attack(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import AttackOption

    b, f, spell = c.b, c.caster, c.spell
    target = victim or c.target
    rays = int(o.get("rays", 1)) * (c.mult if o.get("rays_scaling") else 1) + int(o.get("rays_up", 0)) * c.up
    reach = b.spell_range(spell)
    o = typed(c, o, [target])
    struck = []
    for _ in range(rays):
        if o.get("spread") and target is not None and target in struck:
            fresh = [x for x in b.spell_targets(f, c.sid) if x not in struck and x.team != f.team]
            if not fresh:
                break  # (Steel Wind Strike: one blow for each creature, no more)
            target = min(fresh, key=lambda x: b.gap(f, x))
        if target is None or not target.active:
            options = [x for x in b.spell_targets(f, c.sid) if not o.get("spread") or x not in struck]
            if not options:
                break
            target = b.rng.choice(options)
        struck.append(target)
        for dice_, dtype, up in spellrules.damage_parts(o)[:1] or [("0", "force", "")]:
            opt = AttackOption("spell", spell["name"].lower(), "spell_melee" if o["attack"] == "melee" else "spell_ranged",
                               c.bonus, expr(c, dice_, up, scaling=o.get("scaling") == "cantrip", empower=True)
                               + (f"{c.mod:+d}" if o.get("add_mod") and c.mod else ""), dtype,  # (Flame Blade)
                               range=(reach, reach),
                               extra={} if spellrules.damage_parts(o) else {"no_damage": True})  # (Plane Shift's touch)
            c.empowered = 0  # (one damage roll of the spell: the first ray)
            before = target.hp
            if b._attack(f, opt, target):
                if o.get("drain") and f.active and before > target.hp:
                    gain = int((before - max(0, target.hp)) * float(o["drain"]))
                    if gain > 0:
                        b._heal(f, gain)  # (Vampiric Touch)
                if target.active:
                    run(c, o.get("on_hit", ()), target)
            elif o.get("miss_half") and (target.active or target.state == "down"):
                half = _roll(c, opt.damage, dtype) // 2  # (Melf's Acid Arrow: splashed, if not struck)
                if half > 0:
                    b._hit(f, target, half, dtype, crit=False, weapon=spell["name"].lower())
            elif potent(c) and (target.active or target.state == "down"):
                half = _roll(c, opt.damage, dtype) // 2
                if half > 0:
                    b.say(f"<magic>The cantrip still bites.</> (Potent Cantrip)", "magic")
                    b._hit(f, target, half, dtype, crit=False, weapon=spell["name"].lower())
        if o.get("after") and target is not None:
            run(c, o["after"], target)  # hit or miss (Ice Knife's burst)


def typed(c: Cast, o: dict, victims: list) -> dict:
    """An op whose damage type the caster chooses (`types`: Chromatic Orb, Dragon's Breath): the one that hurts these
    creatures most, the first listed when it makes no difference."""
    if not o.get("types"):
        return o
    from realmwalker.rules.engine import estimates

    xs = [x for x in victims if x is not None and x.team != c.caster.team] or [x for x in victims if x is not None]
    best = max(o["types"], key=lambda t: (sum(estimates.damage_factor(x, t) for x in xs), -o["types"].index(t)))
    return {**o, "type": best}


@op("darts")
def _darts(c: Cast, o: dict, victim) -> None:
    b, f = c.b, c.caster
    target = victim or c.target
    count = int(o.get("count", 1)) + int(o.get("count_up", 0)) * c.up
    for _ in range(count):
        if target is None or not target.active:
            options = b.spell_targets(f, c.sid)
            if not options:
                break
            target = min(options, key=lambda x: x.hp)
        dice_, dtype, _ = spellrules.damage_parts(o)[0]
        amount = dice.roll(expr(c, dice_, empower=True), b.rng).total
        c.empowered = 0  # (Empowered Evocation: the first dart)
        b._event("dart", by=f.id, to=target.id, dtype=dtype)
        b._hit(f, target, amount, dtype, crit=False, weapon="dart of force")


@op("save")
def _save(c: Cast, o: dict, victim) -> None:
    b, f, spell = c.b, c.caster, c.spell
    area = c.area
    if o.get("around"):  # everyone within so many feet of the creature (Ice Knife, Hail of Thorns)
        centre = victim or c.target
        n = int(o["around"]) // grid.SQUARE_FT
        area = [] if centre is None else [(x, y) for x in range(centre.x - n, centre.x + centre.sq + n)
                                          for y in range(centre.y - n, centre.y + centre.sq + n)
                                          if b.field.in_bounds(x, y) and grid.gap(centre.space, (x, y, 1)) <= n]
        victims = b.in_area(area, o.get("affects", "all"), f)
        if area:
            b._event("burst", by=f.id, cells=sorted(area), dtype=spellrules.damage_parts(o)[0][1]
                     if spellrules.damage_parts(o) else "")
    elif victim is not None:
        victims = [victim]
    elif c.area:
        victims = b.in_area(c.area, spell.get("affects", "all"), f)
    else:
        victims = _targets(c)
    o = typed(c, o, victims)
    parts = [(expr(c, d, up, scaling=o.get("scaling") == "cantrip", empower=i == 0), t)
             for i, (d, t, up) in enumerate(spellrules.damage_parts(o))]
    c.empowered = 0 if parts else c.empowered  # (one damage roll of the spell)
    rolled = {i: _roll(c, e, t) for i, (e, t) in enumerate(parts)} if area else {}
    origin = c.point if spell["target"] == "point" and c.point is not None else (f.x, f.y)
    spared = b.sculpted(f, c.sid, victims, c.level) if c.area and not o.get("around") else set()
    on_save = "half" if o.get("half") or (parts and potent(c)) else "none"
    ability = o["ability"]
    dc = int(o.get("dc", c.dc))
    for x in victims:
        if not _allowed(o, x):
            if x is c.target:
                b.say(f"The spell finds no grip on {x.the_name}.", "system")
            continue
        if x.id in spared:
            b.say(f"<magic>The fire parts around {x.the_name}.</> (Sculpt Spells)" if spellrules.main_type(spell) == "fire"
                  else f"<magic>The spell passes {x.the_name} by.</> (Sculpt Spells)", "magic")
            continue
        cover = 0
        if ability == "dex" and o.get("cover", True):
            cover = min(grid.THREE_QUARTERS, b.field.cover((origin[0], origin[1], 1), x.space))
            cover = 0 if cover == grid.TOTAL else cover
        if any(x.has_trait(t) for t in o.get("sure_save", ())) or x.kind in o.get("sure_kinds", ()):
            saved = True
            b.dice_say(f"{x.name} {ability.upper()} save: not affected")
        else:
            saved = b._save(x, ability, dc, bonus=grid.COVER_AC[cover] if ability == "dex" else 0,
                            against=_conditions_in(o.get("on_fail", ())),
                            advantage="advantage" if o.get("advantage") else "")  # (Charm Person in a fight)
        b._event("save", who=x.id, ok=saved)
        before = x.hp
        for i, (e, dtype) in enumerate(parts):
            if i == 0 and o.get("hurt_damage") and x.hp < x.max_hp:  # (Toll the Dead: a bigger die for the hurt)
                e = expr(c, o["hurt_damage"], scaling=o.get("scaling") == "cantrip")
            full = rolled[i] if i in rolled and not (i == 0 and o.get("hurt_damage")) else _roll(c, e, dtype)
            b._save_hit(f, x, ability, saved, full, dtype, on_save)
        if o.get("max_hp_loss") and not saved and x.state != "dead" and before > max(0, x.hp):
            cut(b, x, before - max(0, x.hp))  # (Harm: the maximum falls by the necrotic damage taken)
        if o.get("dust") and not saved and x.hp <= 0 and before > 0 and x.state in ("down", "dead", "fighting"):
            dust(b, x, f)  # (Disintegrate)
            continue
        if not saved and x.active:
            run(c, o.get("on_fail", ()), x)
        elif saved and x.active:
            run(c, o.get("on_save", ()), x)  # (Ray of Enfeeblement: even a save leaves its mark)
    # Hurled away, the farthest first so that nobody is stopped by a friend who is about to be thrown too.
    src = f if spell["target"] != "point" else (origin[0], origin[1])
    for x, feet in sorted(c.pushed, key=lambda p: -grid.gap((origin[0], origin[1], 1), p[0].space)):
        if x.active:
            b._push(src, x, int(feet) // 5)
    c.pushed.clear()


def cut(b, x, amount: int) -> None:
    """Its hit point maximum falls for the rest of the fight (Harm), never below 1."""
    x.max_cut += int(amount)
    if x.hp > x.max_hp:
        x.hp = x.max_hp
    b.say(f"{x.the_name}'s life is withered: {x.possessive} greatest strength falls to {x.max_hp}.",
          "danger" if x.side == "party" else "good")


def dust(b, x, by) -> None:
    """Brought to nothing by a disintegrating ray: dead at once, and no spell in the game brings it back."""
    if x.state != "dead":
        b._kill(x, "turned to dust", by)
    x.__dict__["dust"] = True
    b._event("dust", who=x.id)
    b.say(f"{x.the_name} crumbles into fine grey dust.", "danger" if x.side == "party" else "good")


@op("push")
def _push(c: Cast, o: dict, victim) -> None:
    if o.get("max_size") and victim is not None and not statblocks.size_at_most(victim.size, o["max_size"]):
        return
    if victim is not None and victim is not c.caster and victim.hp > 0:
        if o.get("now"):
            c.b._push(c.caster, victim, int(o["feet"]) // 5)
        else:
            c.pushed.append((victim, int(o["feet"])))


def _roll(c: Cast, e: str, dtype: str) -> int:
    """A spell's damage roll (Elemental Adept: a 1 on a die of the chosen element counts as a 2)."""
    rolled = dice.roll(e, c.b.rng, double_dice=c.crit)
    if c.caster.char is not None and c.b.__dict__.get("_casting") is c.caster:
        from realmwalker.rules import feats

        return rolled.total + feats.adept_ones(c.caster.char, dtype, rolled.rolls)
    return rolled.total


@op("damage")
def _damage(c: Cast, o: dict, victim) -> None:
    """Damage without a roll to hit or a save (it has already landed)."""
    victim = victim or c.target  # (at the top of a spell: its target; Witch Bolt's later bolts)
    if o.get("max_size") and victim is not None and not statblocks.size_at_most(victim.size, o["max_size"]):
        return
    if victim is not None and not _allowed(o, victim):
        return  # (Divine Smite's more against fiends and undead)
    if o.get("charge_feet") and c.caster.moved_feet < int(o["charge_feet"]):
        return  # only after a charge (a boar's Gore)
    if victim is not None and (victim.active or victim.state == "down"):
        for dice_, dtype, up in spellrules.damage_parts(o):
            c.b._hit(c.caster, victim, _roll(c, expr(c, dice_, up), dtype), dtype, crit=False,
                     weapon=c.spell.get("name", dtype))


@op("ignite")
def _ignite(c: Cast, o: dict, victim) -> None:
    c.b._ignite(c.caster, c.area)


@op("burn")
def _burn(c: Cast, o: dict, victim) -> None:
    """Oil or alchemist's fire keeps burning where it fell."""
    from realmwalker.rules.combat import Zone

    b = c.b
    b._add_zone(Zone(b._zone_id(), "fire", set(c.area), owner=c.caster.id, rounds=int(o.get("rounds", 1)), save="dex",
                     dc=10, damage=str(o.get("damage", "1d4")), damage_type="fire", on_save="none"))


# ---------------------------------------------------------------------------- what a hit or a failed save brings
def _ends(c: Cast, x, how: str | None) -> dict | None:
    if not how:
        return None
    whose, at = how.rsplit("_turn_", 1)
    return durations.until(c.b, c.caster if whose == "caster" else x, f"turn_{at}")


@op("condition")
def _condition(c: Cast, o: dict, victim) -> None:
    b, f, spell = c.b, c.caster, c.spell
    victims = [victim] if victim is not None else _targets(c)
    cid = o["condition"]
    for x in victims:
        if x is None or not x.active:
            continue
        if o.get("max_size") and not statblocks.size_at_most(x.size, o["max_size"]):
            continue
        if x.kind in o.get("not_kinds", ()) or x.char is not None and x.char.race in o.get("not_species", ()):
            continue  # (a ghoul's touch: not the dead, not elves)
        if o.get("charge_feet") and f.moved_feet < int(o["charge_feet"]):
            continue
        if o.get("immune_as"):
            from realmwalker.rules.engine import query

            if query.condition_immune(x, o["immune_as"]):
                b.say(f"{x.the_name} shrugs it off.", "system")
                continue  # (Suggestion is a charm: those who cannot be charmed are not stood down)
        extra = {}
        if o.get("escape"):
            extra["escape"] = int(o["escape"])
        if spell.get("concentration"):
            extra["conc"] = f.id
        if o.get("on_damage"):
            extra["on_damage"] = True
        if o.get("with"):
            if o["with"] not in x.conditions:
                continue  # (no hold took: nothing to be restrained by)
            extra["with"] = o["with"]  # (it ends when that condition does: Restrained while Grappled)
        if o.get("control"):
            extra["control"] = f.team  # (Dominate: it fights for the caster's side while it lasts)
        if o.get("damage_save"):
            extra["damage_save"] = {"save": o.get("save", spell_save(spell)), "dc": int(o.get("save_dc") or c.dc)}
        if o.get("then"):
            t = o["then"]
            extra["then"] = {"save": t["save"], "dc": c.dc, "caster": f.id, "spell": c.sid,
                             "on_fail": t.get("on_fail", []), "conc": f.id if spell.get("concentration") else None}
        ends = _ends(c, x, o.get("ends"))
        rounds = None if spell.get("concentration") or ends is not None else \
            (-1 if cid == "prone" else int(o.get("rounds", spell.get("rounds", 1))))
        if not durations.give(b, x, cid, ends=ends, rounds=rounds, source=f, **extra):
            b.say(f"{x.the_name} shrugs it off.", "system")
            continue
        if cid == "grappled":
            x.grappled_by = f.id
        if o.get("repeat_save") or o.get("petrify"):
            x.save_ends.append({"cond": cid, "save": o.get("save", spell_save(spell)), "dc": int(o.get("save_dc") or c.dc),
                                "conc": f.id if spell.get("concentration") else None,
                                **({"tally": [0, 0]} if o.get("petrify") else {})})  # (successes, failures)
        b._event("condition", who=x.id, cond=cid)
        b.say(f"{x.the_name} is {conditions.name(b.t, cid).lower()}.", "good" if x.side != f.side else "danger")


def _conditions_in(ops_: list) -> tuple:
    """The conditions a failed save would bring (Brave and Fey Ancestry read them)."""
    return tuple(o.get("condition") for o in ops_ if o.get("op") == "condition" and o.get("condition"))


def spell_save(spell: dict) -> str:
    s = spellrules.op(spell, "save")
    return s["ability"] if s else "con"


def then_save(b, x, then: dict) -> None:
    """The second saving throw of a spell that tightens its grip (Sleep): a failure brings what `on_fail` says."""
    caster = next((f for f in b.fighters if f.id == then.get("caster")), None)
    if then.get("conc") is not None and (caster is None or caster.concentration is None):
        return  # the spell is over
    if b._save(x, then["save"], int(then["dc"]), against=_conditions_in(then.get("on_fail", ()))):
        return
    spell = b.t.spells[then["spell"]] if then.get("spell") in b.t.spells else {}
    c = Cast(b, caster or x, then.get("spell", ""), spell, x, None, dc=int(then["dc"]))
    run(c, then.get("on_fail", ()), x)


@op("slow")
def _slow(c: Cast, o: dict, victim) -> None:
    if victim is not None:
        durations.buff(victim, {"slow": int(o["feet"]), "source": f"slow:{c.sid}"},
                       durations.until(c.b, c.caster, "turn_start"))


@op("no_opportunity")
def _no_opportunity(c: Cast, o: dict, victim) -> None:
    if victim is not None:
        durations.buff(victim, {"no_opportunity": True, "source": f"jolt:{c.sid}"},
                       durations.until(c.b, victim, "turn_start"))


@op("no_heal")
def _no_heal(c: Cast, o: dict, victim) -> None:
    if victim is not None:  # (until the end of the caster's next turn; `until` "turn_start": its start, a slaad's Claw)
        durations.buff(victim, {"no_heal": True, "source": f"chill:{c.sid}"},
                       durations.until(c.b, c.caster, o.get("until", "turn_end")))


@op("if_condition")
def _if_condition(c: Cast, o: dict, victim) -> None:
    if victim is not None and o["condition"] in victim.conditions:
        run(c, o["ops"], victim)


@op("mark")
def _mark(c: Cast, o: dict, victim) -> None:
    """The next attack roll against it has advantage, until the end of the caster's next turn (Guiding Bolt)."""
    if victim is not None:
        durations.buff(victim, {"marked": c.caster.id, "source": f"mark:{c.sid}"},
                       durations.until(c.b, c.caster, "turn_end"))


@op("burning")
def _burning(c: Cast, o: dict, victim) -> None:
    """It catches fire: 1d4 fire at the start of each of its turns until put out (rules/engine/hazards.py)."""
    if victim is not None and victim.active:
        durations.buff(victim, {"burning": True, "source": "burning"})
        c.b.say(f"{victim.the_name} is on fire!", "danger" if victim.side == c.caster.side else "good")


@op("attach")
def _attach(c: Cast, o: dict, victim) -> None:
    """A stirge fastens on: it drinks at the start of each of its turns (statblock damage `when` start of turn)."""
    if victim is not None and victim.active:
        c.caster.attached_to = victim.id
        c.b.say(f"{c.caster.the_name} fastens onto {victim.the_name}.", "danger" if victim.side == "party" else "info")


@op("lose_turn")
def _lose_turn(c: Cast, o: dict, victim) -> None:
    """Command's Grovel: on its next turn it throws itself down, and does nothing else."""
    if victim is not None:
        victim.grovel = True


# ---------------------------------------------------------------------------- help
@op("heal")
def _heal(c: Cast, o: dict, victim) -> None:
    b, f, spell = c.b, c.caster, c.spell
    if victim is not None:
        targets = [victim]
    elif spell["target"] == "self":
        targets = [f]
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell)
        near = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach]
        targets = sorted(near, key=lambda x: x.hp / max(1, x.max_hp))[: int(o.get("count", 6)) + int(o.get("count_up", 0)) * c.up]
    elif c.area:
        near = [x for x in b.in_area(c.area, "allies", f)]
        targets = sorted(near, key=lambda x: x.hp / max(1, x.max_hp))[: int(o.get("count", 6))]
    else:
        targets = [c.target]
    pool = int(o["pool"]) if o.get("pool") else None
    if pool is not None and spell["target"] == "all_allies":  # (Mass Heal: everyone in range may share it)
        reach = b.spell_range(spell)
        targets = sorted([x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach],
                         key=lambda x: (x.state != "down", x.hp / max(1, x.max_hp)))
    for x in targets:
        if x is None:
            continue
        if x.no_heal:
            b.say(f"The magic finds no hold in {x.the_name}.", "warn")
            continue
        if o.get("full") or pool is not None:  # (Power Word Heal: all it lacks; Mass Heal: from the pool)
            need = max(0, x.max_hp - x.hp)
            amount = need if pool is None else min(need, pool)
            if pool is not None:
                if amount <= 0 and not any(cid in x.conditions for cid in o.get("restore", ())):
                    continue
                pool -= amount
            if amount > 0:
                b._heal(x, amount)
            _restored(c, x, o.get("restore", ()))
            if pool is not None and pool <= 0:
                break
            continue
        rolled = dice.roll(expr(c, o["dice"], o.get("up", "")), b.rng)
        if x.buff_value("heal_max"):  # (Beacon of Hope: the most the dice can give)
            n_, s_, flat_ = dice.parse(expr(c, o["dice"], o.get("up", "")))
            rolled = dice.roll(str(n_ * s_ + flat_), b.rng)
        amount = rolled.total + (c.mod if o.get("add_mod") else 0) + int(o.get("per_up", 0)) * c.up  # (Heal: +10)
        if f.has_trait("feat_healer") and not spell.get("ability"):  # Healer: healing dice of 1 rolled again
            amount += sum(b.rng.randint(1, max(1, dice.parse(o["dice"])[1])) - 1 for r in rolled.rolls if r == 1)
        if o.get("add") == "level" and f.char is not None:
            amount += f.char.level  # Second Wind
        elif o.get("add") == "level" and f.bond is not None:
            amount += int(f.bond.get("level", 0))  # (a celestial steed's Healing Touch: the spell's level)
        if not spell.get("ability"):
            n_, s_, flat_ = dice.parse(expr(c, o["dice"], o.get("up", "")))
            amount = events.emit(b, "heal_spell", actor=f, target=x, amount=amount, level=c.level,
                                 rolled=rolled.total, most=n_ * s_ + flat_).amount
        b._heal(x, amount)
        if c.level >= 1 and not spell.get("ability"):  # (Life Bond: a steed beside its rider heals as much)
            for s_ in b.fighters:
                if s_.bond is not None and s_.bond.get("owner") == x.id and s_.active and s_.has_trait("life_bond") \
                        and b.gap(s_, x) <= 1 and s_.hp < s_.max_hp:
                    b._heal(s_, amount)
        _restored(c, x, o.get("restore", ()))
        if o.get("mends_wound") and x.wounds:
            w = max(x.wounds, key=lambda w: (w.severity, w.bleed))
            w.severity -= 1
            w.bleed = max(0, w.bleed - 1)
            if w.severity <= 0:
                x.wounds.remove(w)
            b.say(f"The worst of {x.the_name}'s wounds closes a little.", "magic")


def _restored(c: Cast, x, conds) -> None:
    """The conditions a healing spell also ends (Mass Heal, Power Word Heal; prone: it gets up)."""
    gone = [cid for cid in conds if cid in x.conditions]
    for cid in gone:
        durations.remove(x, cid)
        x.save_ends = [se for se in x.save_ends if se["cond"] != cid]
    if gone:
        c.b.say(f"{x.the_name} is free of {', '.join(gone)}.", "good" if x.side == "party" else "info")


@op("time_stop")
def _time_stop(c: Cast, o: dict, victim) -> None:
    """Time Stop: the caster takes 1d4 + 1 turns in a row (Battle._more_time); it ends when anything they do reaches
    another creature."""
    b, f = c.b, c.caster
    n = dice.roll(str(o.get("dice", "1d4+1")), b.rng).total
    b.dice_say(f"Time Stop: {n} turns")
    f.buffs = [bf for bf in f.buffs if bf.get("time_stop") is None]
    f.buffs.append({"time_stop": n, "source": c.sid})
    b._time_stop = f.id
    b.__dict__.pop("_time_broken", None)
    b._event("time", who=f.id, stopped=True)
    b.say(f"The world holds its breath. Nothing moves but {f.the_name}.", "magic")


@op("modifier")
def _modifier(c: Cast, o: dict, victim) -> None:
    b, f, spell, sid = c.b, c.caster, c.spell, c.sid
    if victim is not None:
        targets = [victim]
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell)
        near = [x for x in b.team(f.team) if x.active and b.feet(f, x) <= reach]
        near.sort(key=lambda x: (x is not f, b.feet(f, x)))
        targets = near[: int(o.get("count", 3)) + int(o.get("count_up", 0)) * c.up]
    elif spell["target"] == "self":
        targets = [f]
    else:
        targets = _targets(c)
    for x in targets:
        if x is None:
            continue
        if o.get("needs") and o["needs"] not in x.conditions:
            continue  # (Otto's dance rides on the charm: no charm, no dance)
        if x.char is not None and spellrules.lasts(b.t, sid) and victim is None:
            # It outlives the fight: kept on them (the sheet counts its armour), the rest carried here.
            spellrules.keep(x.char, b.t, sid, c.level)
            x.buffs = [bf for bf in x.buffs if bf.get("lasting") != sid]
            part = spellrules.battle_part(b.t, sid, x.char)
            if part:
                x.buffs.append(part)
            if spell.get("concentration") and f.concentration is not None:
                f.concentration.setdefault("on", []).append(x.id)  # (lost with the caster's concentration)
        else:
            x.buffs = [bf for bf in x.buffs if bf.get("source") != sid]
            bf = {**filled(c, spellrules.buff_at(o, c.level, spell)), "source": sid}
            if spell.get("concentration") and not o.get("not_conc"):
                bf["conc"] = f.id
            if o.get("ends"):
                durations.buff(x, bf, _ends(c, x, o["ends"]))  # (until a turn of the caster's or its own)
            else:
                x.buffs.append({**bf, "rounds": int(o.get("rounds", spell.get("rounds", 10)))})
        b._event("buff", who=x.id, spell=sid)
    if o.get("buff", {}).get("aura"):
        b._follow_auras()  # (an aura's friends have its gift at once)
    if victim is None:
        b.say(spell["text"], "magic")


def filled(c: Cast, buff: dict) -> dict:
    """A buff with the casting's numbers put in: "$caster" (the caster's id), "$dc", "$mod" (the spellcasting
    modifier, at least 1)."""
    out = {}
    for k, v in buff.items():
        if isinstance(v, dict):
            v = filled(c, v)  # (an aura's grant: Globe of Invulnerability's ward by the slot's level)
        if v == "$caster":
            v = c.caster.id
        elif v == "$dc":
            v = c.dc
        elif v == "$mod":
            v = max(1, c.mod)
        elif v == "$spell":
            v = c.sid
        elif v == "$mult":
            v = c.mult
        elif v == "$foe_type":  # (Resistance: the kind of harm the foes here deal most)
            from collections import Counter

            seen = Counter(o.damage_type for e in c.b.enemies_of(c.caster) for o in c.b.attack_options(e)
                           if o.damage_type)
            v = seen.most_common(1)[0][0] if seen else "slashing"
        elif v == "$foe_energy":  # (Protection from Energy: the energy the foes here deal most)
            from collections import Counter

            seen = Counter(o.damage_type for e in c.b.enemies_of(c.caster) for o in c.b.attack_options(e)
                           if o.damage_type in ENERGY)
            for e in c.b.enemies_of(c.caster):
                for sid_ in (e.cdef or {}).get("spells", ()) if e.creature is not None else ():
                    t_ = spellrules.main_type(c.b.t.spells[sid_]) if sid_ in c.b.t.spells else ""
                    if t_ in ENERGY:
                        seen[t_] += 2
            v = [seen.most_common(1)[0][0] if seen else "fire"]
        elif v == "$up":
            v = c.up
        elif v == "$level":
            v = c.level or c.spell.get("level", 0)
        out[k] = v
    return out


@op("temp_hp")
def _temp_hp(c: Cast, o: dict, victim) -> None:
    """Temporary hit points (False Life, Armor of Agathys): the larger of the old and the new, never added. With
    `share` (and the spell's target all_allies), the amount is divided among up to `count` friends within range
    (Power Word Fortify)."""
    amount = dice.roll(expr(c, str(o["amount"]), str(o.get("up", ""))), c.b.rng).total \
        + (max(0, c.mod) if o.get("add_mod") else 0)
    if o.get("per_up"):
        amount += int(o["per_up"]) * c.up
    if o.get("share") and victim is None:
        for x, each in shares(c.b, c.caster, c.spell, amount, int(o.get("count", 6)), level=c.level):
            _give_temp(c, x, each)
        return
    x = victim or (c.caster if c.spell["target"] == "self" else c.target)
    if x is None or not x.active:
        return
    _give_temp(c, x, amount)


def shares(b, f, spell: dict, amount: int, count: int, *, level: int | None = None) -> list:
    """How shared temporary hit points are divided: evenly among the friends in range who would gain from them,
    those nearest a foe first; a friend who already has as many keeps them and the rest share more (Power Word
    Fortify)."""
    reach = b.spell_range(spell, f)
    near = [x for x in b.team(f.team) if x.active and b.feet(f, x) <= reach
            and (level is None or not warded(b, f, x, level))]
    near.sort(key=lambda x: (min((b.gap(x, e) for e in b.enemies_of(f)), default=99), x.temp_hp, x.id))
    picked = near[:max(1, count)]
    while picked:
        each = amount // len(picked)
        keep = [x for x in picked if x.temp_hp < each]
        if len(keep) == len(picked) or not keep:
            break
        picked = keep
    return [(x, amount // len(picked)) for x in picked]


def _give_temp(c: Cast, x, amount: int) -> None:
    if amount > x.temp_hp:
        x.temp_hp = amount
        c.b._event("buff", who=x.id, spell=c.sid)
        c.b.say(f"{x.the_name} has {amount} temporary hit points.", "magic")


@op("weapon_attack")
def _weapon_attack(c: Cast, o: dict, victim) -> None:
    """True Strike (2024): one attack with a weapon in reach, with the spellcasting ability in place of Strength or
    Dexterity; radiant if that hurts more; and `extra` radiant dice from level 5 (one fewer than the cantrip's
    tier)."""
    import dataclasses

    from realmwalker.rules.engine import estimates

    b, f = c.b, c.caster
    target = victim or c.target
    if target is None or not target.active:
        return
    opts = estimates.weapon_blows(b, f, target)  # (a creature's blade too: Expansion 3 G.1)
    if not opts:
        b.say(f"{f.the_name} has no weapon that reaches {target.the_name}.", "warn")
        return
    opt = opts[0]
    am = estimates.blow_mod(b, f, opt)
    n, sides, flat = dice.parse(opt.damage)
    flat += c.mod - am
    dmg = f"{n}d{sides}{'+' + str(flat) if flat > 0 else (str(flat) if flat < 0 else '')}" if n else str(max(1, flat))
    dtype = opt.damage_type
    if estimates.damage_factor(target, "radiant") > estimates.damage_factor(target, dtype):
        dtype = "radiant"
    extra = dict(opt.extra)
    more = c.mult - 1
    if more > 0 and o.get("extra"):
        extra["extra"] = list(extra.get("extra", ())) + [{"damage": f"{more}{o['extra'][1:]}",
                                                          "type": o.get("extra_type", "radiant")}]
    struck = dataclasses.replace(opt, bonus=opt.bonus - am + c.mod, damage=dmg, damage_type=dtype, extra=extra)
    b._attack(f, struck, target)


@op("pull")
def _pull(c: Cast, o: dict, victim) -> None:
    """Pulled straight towards the caster (Thorn Whip)."""
    if victim is None or not victim.active or victim is c.caster:
        return
    if o.get("max_size") and not statblocks.size_at_most(victim.size, o["max_size"]):
        return
    c.b._pull(c.caster, victim, int(o["feet"]) // grid.SQUARE_FT)


@op("no_reaction")
def _no_reaction(c: Cast, o: dict, victim) -> None:
    """No reactions until the start of its next turn (Arms of Hadar)."""
    if victim is not None and victim.active:
        victim.reaction = False


@op("flee")
def _flee(c: Cast, o: dict, victim) -> None:
    """It spends its reaction running from the caster as far as its speed allows (Dissonant Whispers)."""
    if victim is None or not victim.active or not victim.reaction or victim.speed <= 0:
        return
    victim.reaction = False
    c.b.say(f"{victim.the_name} flees in terror.", "good" if victim.side != c.caster.side else "danger")
    c.b._push(c.caster, victim, victim.speed // grid.SQUARE_FT)


@op("move_zone")
def _move_zone(c: Cast, o: dict, victim) -> None:
    """The caster moves what its spell left on the field to a new point (Moonbeam, Flaming Sphere, Cloud of
    Daggers): the same shape, laid out again there."""
    b, f = c.b, c.caster
    base = c.spell.get("again_of", c.sid)
    z = next((z for z in b.zones if z.owner == f.id and z.spell == base), None)
    if z is None or c.point is None:
        return
    area = b.t.spells[base].get("area") or {}
    cells = set(b.field.area(area.get("shape", "sphere"), int(area.get("size", 5)), origin=f.space, toward=c.point))
    if not cells:
        return
    z.cells = cells
    z.centre = c.point
    z.struck.clear()
    b._sync_zones()
    b._event("zone_move", id=z.id, cells=sorted(cells))
    for x in b.in_area(sorted(cells), "all", f):
        b._zones_on(x, start=False)


@op("stabilize")
def _stabilize(c: Cast, o: dict, victim) -> None:
    x = victim or c.target
    if x is not None:
        x.stable = True
        c.b.say(f"{x.the_name} stops bleeding out.", "good")


@op("restore")
def _restore(c: Cast, o: dict, victim) -> None:
    """Lesser Restoration: one condition ends (the worst first); here it also eases a disease taking hold."""
    x = victim or c.target
    if x is None:
        return
    for cid in o.get("conditions", ()):
        if cid in x.conditions:
            durations.remove(x, cid)
            x.save_ends = [se for se in x.save_ends if se["cond"] != cid]
            if o.get("one"):
                break
    if o.get("disease") and x.char:
        x.char.conditions = [k for k in x.char.conditions if not k.startswith("exposed:")]
    c.b.say(f"{x.the_name} looks clearer.", "good")


@op("revive")
def _revive(c: Cast, o: dict, victim) -> None:
    b, f = c.b, c.caster
    x = victim or c.target
    if x is None or x.state != "dead" or x.char is None and (x.creature is None or x.bond is not None) \
            or (x.bond or {}).get("kind") == "simulacrum":
        return  # (a summoned thing that vanished has no body to call back; nor has melted snow: G.3)
    if x.__dict__.get("dust"):
        b.say(f"Nothing of {x.the_name} is left to call back.", "warn")
        return
    x.state = "fighting"  # (the diamond is the spell's costly component: spent as it is cast, rules/spells.py)
    if x.char is not None:
        x.char.alive = True
        x.char.death_cause = None  # (or the body would be found dead of it again as time passed)
    else:
        x.creature.alive = True  # (an enemy caster's fallen friend: Expansion 3 G.1)
    taken = {cell for y in b.on_field() if y is not x for cell in y.cells}
    if any(cell in taken for cell in x.cells):  # (someone stands where it fell: the nearest free ground)
        x.x, x.y = b._free_near((x.x, x.y), x.sq, taken)
    x.hp = int(o.get("hp", 1))
    x.conditions = {"prone": -1}
    x.cond_ends = {}
    x.death_saves = [0, 0]
    b._event("heal", to=x.id, amount=x.hp)
    b.say(f"{x.the_name} draws a ragged breath.", "magic")


@op("identify")
def _identify(c: Cast, o: dict, victim) -> None:
    pass  # outside a fight only (game/magic.py)


@op("road")
def _road(c: Cast, o: dict, victim) -> None:
    pass  # outside a fight only (game/spellwork.py): such a spell is never offered in one


@op("max_up")
def _max_up(c: Cast, o: dict, victim) -> None:
    """Aid: up to `count` friends in range (the caster first, then the worst hurt), their maximum and hit points
    raised while the spell lasts; it outlives the fight, kept on the character (rules/spells.raise_max)."""
    b, f, spell, sid = c.b, c.caster, c.spell, c.sid
    if victim is not None:
        targets = [victim]
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell)
        near = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach]
        near.sort(key=lambda x: (x is not f, x.hp / max(1, x.max_hp)))
        targets = near[: int(o.get("count", 3)) + int(o.get("count_up", 0)) * c.up]
    elif spell["target"] == "self":
        targets = [f]
    else:
        targets = [c.target]
    amount = spellrules.max_up_amount(spell, c.level or int(spell["level"]), b.rng)
    for x in targets:
        if x is None or x.state == "dead":
            continue
        if x.char is None:  # (a creature: its maximum raised on its own record, never twice by one spell: G.1)
            if x.creature is None:
                continue
            key = spellrules.MAX_UP + sid
            gained = max(0, amount - int(x.creature.uses.get(key, 0)))
            if gained:
                x.creature.uses[key] = amount
                x.creature.max_hp += gained
                b.say(f"{x.the_name}'s strength grows: {gained} more hit points while {spell['name']} lasts.", "good")
                b._heal(x, gained)
            continue
        gained = spellrules.raise_max(x.char, sid, amount)
        if spellrules.lasts(b.t, sid):
            spellrules.keep(x.char, b.t, sid, c.level)
        if gained:
            b.say(f"{x.the_name}'s strength grows: {gained} more hit points while {spell['name']} lasts.", "good")
            x.char.hp -= gained  # (the hit points come through the battle's healing, which stands up the fallen)
            b._heal(x, gained)


@op("special")
def _special(c: Cast, o: dict, victim) -> None:
    SPECIAL[o["handler"]](c, o, victim)


@op("gain_action")
def _gain_action(c: Cast, o: dict, victim) -> None:
    """One more action this turn (Action Surge)."""
    c.caster.action += int(o.get("count", 1))


@op("say")
def _say(c: Cast, o: dict, victim) -> None:
    f = victim or c.caster
    c.b.say(o["text"].replace("{name}", f.the_name).replace("{their}", f.possessive), o.get("style", "info"))


# ---------------------------------------------------------------------------- things left on the field
@op("zone")
def _zone(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Zone

    b, f, spell = c.b, c.caster, c.spell
    rounds = -1 if spell.get("concentration") else int(o.get("rounds", spell.get("rounds", 10)))
    dmg = spellrules.damage_parts(o)
    z = Zone(b._zone_id(), o["zone"], set(c.area), owner=f.id, spell=c.sid, rounds=rounds,
             save=o.get("save", "dex") if o.get("save", "dex") != "none" else "",
             dc=int(o.get("dc", c.dc)),  # (caltrops and ball bearings have the book's own DC)
             damage=expr(c, dmg[0][0], dmg[0][2]) if dmg else "", damage_type=dmg[0][1] if dmg else "",
             on_save="half" if o.get("half") else "none", centre=c.point,
             fail=o.get("fail", ""), rough=bool(o.get("rough")), dark=bool(o.get("dark")),
             held=expr(c, *o["held"].split("|")) if o.get("held") else "", frees=bool(o.get("frees")),
             friends_safe=bool(o.get("friends_safe")),
             heal=(expr(c, o["heal"], o.get("heal_up", "")) + (f"+{c.mod}" if o.get("add_mod") and c.mod > 0 else ""))
             if o.get("heal") else "",
             breaks=bool(o.get("breaks")), lasts=int(o.get("lasts", 0)), stages=list(o.get("stages", ())),
             cast={"dc": c.dc, "mod": c.mod, "level": c.level, "up": c.up})
    if o.get("spare"):  # (Plant Growth: the caster leaves out the ground round its friends, as the book lets)
        r = int(o["spare"])
        for x in b.on_field():
            if x.team == f.team:
                z.cells -= {(cx + dx, cy + dy) for (cx, cy) in x.cells for dx in range(-r, r + 1)
                            for dy in range(-r, r + 1)}
    if o.get("follow"):  # (Antimagic Field: it goes where the caster goes)
        z.follows = True
        z.radius = max(1, int((spell.get("area") or {}).get("size", 10)) // grid.SQUARE_FT)
        z.cells = set()
        b._add_zone(z)
        b._follow_auras()
        return
    if z.kind in WALLS:  # a wall: it rises on the free squares of the area
        taken = {sq for x in b.on_field() for sq in x.cells}
        name = {"stone": "wall_stone", "force": "wall_force", "prismatic": "wall_prismatic"}.get(z.kind, "ice_wall")
        for sq in sorted(z.cells):
            if sq in taken or not b.field.passable(*sq):
                continue
            z.was[sq] = b.field.name(*sq)
            b.field.terrain[sq] = b.t.terrain.index[name]
        z.cells = set(z.was)
        b.field._derive()
        if not z.cells:
            return
        b._add_zone(z)
        if o.get("near"):  # (Prismatic Wall: the glare beside it blinds foes who come near or start a turn there)
            r = int(o["near"]) // grid.SQUARE_FT
            ring = {(x, y) for (wx, wy) in z.cells for x in range(wx - r, wx + r + 1) for y in range(wy - r, wy + r + 1)
                    if b.field.in_bounds(x, y) and (x, y) not in z.cells}
            g = Zone(b._zone_id(), "glare", ring, owner=f.id, spell=c.sid, rounds=z.rounds,
                     save=o.get("near_save", "con"), dc=z.dc, fail=o.get("near_fail", "blinded"),
                     lasts=int(o.get("lasts", 10)), friends_safe=True)
            b._add_zone(g)
            for x in b.in_area(sorted(ring), "enemies", f):
                b._ground(x, g, start=False)
        if o.get("catch") and z.damage:  # (Wall of Ice: those it rises beside are thrown aside, frozen)
            for x in b.in_area(c.area, spell.get("affects", "all"), f):
                b.say(f"The ice bursts up around {x.the_name}.", "danger" if x.side == "party" else "info")
                b._save_damage(f, x, z.save or "dex", z.dc, z.damage, z.damage_type, z.on_save)
        return
    b._add_zone(z)
    if o.get("catch"):  # (whoever stands there as it appears: caught, or hurt)
        for x in b.in_area(c.area, spell.get("affects", "all"), f):
            if z.heal and x.team == f.team:
                b._zones_on(x, start=False)  # (Conjure Celestial's healing light)
            elif z.fail or z.kind in GROUND:
                b._ground(x, z, start=False)
            elif z.holds or z.kind == "grease":
                b._zone_catch(x, z)
            elif x is not f or not z.damage:
                b._zones_on(x, start=False)


@op("banish")
def _banish(c: Cast, o: dict, victim) -> None:
    """Banishment, Otiluke's Resilient Sphere, Banishing Smite, Forcecage: off the field while the caster
    concentrates; everyone in the spell's area for an area spell (the forcecage's box). `forever`: sent from this
    plane for good, no concentration needed (Plane Shift, Divine Word's banishing): beaten."""
    b, f = c.b, c.caster
    if victim is not None:
        victims = [victim]
    elif c.area:
        victims = b.in_area(c.area, c.spell.get("affects", "all"), f)
    else:
        victims = _targets(c)
    for x in victims:
        if x is None or not x.active or x is f:
            continue
        if not _allowed(o, x):
            continue
        if o.get("below_hp") and x.hp > int(o["below_hp"]):
            continue
        if o.get("max_size") and not statblocks.size_at_most(x.size, o["max_size"]):
            continue  # (the sphere holds a Large creature at most)
        if o.get("forever"):
            b.send_off(x, by=f)
            continue
        if f.concentration is None:
            continue  # (a spell that holds nothing cannot keep anyone away)
        b.send_away(x, o.get("how", "banished"), by=f, spell=c.sid)
        if x.away is not None and o.get("escape"):
            x.away["escape"] = dict(o["escape"])  # (Maze: a check each turn finds the way out)
        if x.away is not None and o.get("home") is False:
            x.away["home"] = False  # (Banishing Smite: back when it ends, wherever it comes from)


@op("dispel")
def _dispel(c: Cast, o: dict, victim) -> None:
    """Dispel Magic (2024): every spell on the creature at the point, and on the ground there, of the slot's level or
    lower ends; a higher one ends on a check with the spellcasting ability against 10 + its level (an abjurer's
    Spell Breaker adds proficiency, and keeps the slot when nothing ends)."""
    b, f = c.b, c.caster
    target = victim or c.target or (b.at(*c.point) if c.point is not None else None)
    breaker = f.has_trait("spell_breaker")
    ended = 0

    def beats(level: int, name: str) -> bool:
        if level <= c.level:
            return True
        bonus = c.mod + (query_prof(f) if breaker else 0)
        roll = b.rng.randint(1, 20)
        b.dice_say(f"{f.name}'s check against {name}: {roll}{bonus:+d} vs {10 + level}")
        return roll + bonus >= 10 + level

    if target is not None and target.state in ("fighting", "fleeing", "down", "away"):
        for (level, name, end, _by) in held_spells(b, target):
            if beats(level, name):
                end()
                ended += 1
                b.say(f"{name} on {target.the_name} unravels.", "magic")
    if c.point is not None:
        for z in [z for z in b.zones if c.point in z.cells and z.spell in b.t.spells and z.kind != "force"]:
            sp = b.t.spells[z.spell]
            if beats(sp["level"], sp["name"]):
                owner = next((x for x in b.fighters if x.id == z.owner), None)
                if owner is not None and owner.concentration is not None and owner.concentration["spell"] == z.spell:
                    b._end_concentration(owner, quiet=False, why="is dispelled")
                else:
                    b._remove_zone(z)
                ended += 1
    if not ended:
        b.say("The spell finds nothing to undo.", "system")
        if breaker and c.slotted and c.level > 0 and f.char is not None:
            spellrules.unspend_slot(f.char, c.level)
            b.say("<magic>The slot is not lost.</> (Spell Breaker)", "magic")


def query_prof(f) -> int:
    from realmwalker.rules.engine import query

    return query.proficiency(f)


def held_spells(b, x) -> list:
    """The spells working on a creature now, as (level, name, end it, the caster's id or None): its marks and
    blessings, the conditions a caster's concentration holds on it, and being sent away."""
    out = []
    seen = set()
    for bf in list(x.buffs):
        sid = bf.get("source") if bf.get("source") in b.t.spells else bf.get("lasting")
        if sid not in b.t.spells or bf.get("aura_of") is not None or (sid, bf.get("conc")) in seen:
            continue
        seen.add((sid, bf.get("conc")))
        sp = b.t.spells[sid]

        def end(x=x, sid=sid):
            if any(g.get("haste") for g in x.buffs if g.get("source") == sid) and x.active:
                b.lethargy(x)
            x.buffs = [g for g in x.buffs if g.get("source") != sid and g.get("lasting") != sid]
            if x.char is not None:
                spellrules.end(x.char, sid)
        by = bf.get("conc") if bf.get("conc") is not None else bf.get("by")
        out.append((max(int(sp["level"]), int(bf.get("level") or 0)), sp["name"], end, by))
    for caster in b.fighters:
        conc = caster.concentration
        if conc is None or conc["spell"] not in b.t.spells:
            continue
        held = [cid for cid, e in x.cond_ends.items() if e.get("conc") == caster.id] + \
            [se["cond"] for se in x.save_ends if se.get("conc") == caster.id]
        away = x.state == "away" and x.away and x.away.get("by") == caster.id
        shaped = x.shape is not None and x.shape.get("by") == caster.id and x.shape.get("conc", True)  # (F.6)
        if not held and not away and not shaped:
            continue
        sp = b.t.spells[conc["spell"]]
        if sp.get("no_dispel"):
            continue  # (Forcecage: Dispel Magic cannot end it)

        def end(x=x, caster=caster, held=tuple(held), away=away, shaped=shaped):
            for cid in held:
                durations.remove(x, cid)
                x.save_ends = [se for se in x.save_ends if se.get("cond") != cid]
            if away:
                b.bring_back(x)
            if shaped:
                b.unshape(x)
        out.append((int(sp["level"]) + int(conc.get("up", 0)), sp["name"], end, caster.id))
    return out


@op("aura")
def _aura(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Zone

    b, f, spell = c.b, c.caster, c.spell
    dice_, dtype, up = spellrules.damage_parts(o)[0]
    z = Zone(b._zone_id(), "guardians", set(), owner=f.id, spell=c.sid,
             rounds=-1 if spell.get("concentration") else int(spell.get("rounds", 10)), radius=int(o["radius"]) // 5,
             save=o["ability"], dc=c.dc, damage=expr(c, dice_, up), damage_type=dtype,
             on_save="half" if o.get("half") else "none", friends_safe=True)
    b._add_zone(z)
    b._follow_auras()


@op("by_hp")
def _by_hp(c: Cast, o: dict, victim) -> None:
    """What it does depends on the hit points it has left (Divine Word): `tiers` [[most, [ops]], ...], the first
    whose number is at least its hit points now; nothing past the last."""
    x = victim or c.target
    if x is None or not x.active:
        return
    for most, ops_ in o["tiers"]:
        if x.hp <= int(most):
            run(c, ops_, x)
            return


@op("slay")
def _slay(c: Cast, o: dict, victim) -> None:
    """It dies outright (Divine Word at 20 hit points or fewer; with `max_hp`, only if it has that many or fewer)."""
    x = victim or c.target
    if x is None or x.state not in ("fighting", "fleeing", "down"):
        return
    if o.get("max_hp") is not None and x.hp > int(o["max_hp"]):
        return
    c.b.say(f"{x.the_name} falls dead at the word.", "danger" if x.side == "party" else "good")
    c.b._kill(x, "slain by a word of power", c.caster)


@op("lift")
def _lift(c: Cast, o: dict, victim) -> None:
    """Reverse Gravity: it falls upward, to `feet` above the ground in the open (under a roof or below ground it
    strikes the ceiling twenty feet up and takes the fall), and hangs there while the caster concentrates; when the
    spell ends it falls (Battle._end_concentration). A flier may fly as it likes."""
    b = c.b
    x = victim
    if x is None or not x.active or x.hovers or x.fly_speed > 0:
        return  # (a flier flies as it likes)
    gentle = bool(o.get("gentle"))  # (Levitate: it rises, hangs, and floats down gently when the spell ends)
    roof = b.env.place in ("underground", "indoors") and not gentle
    top = 20 if roof else int(o.get("feet", 100))
    if x.z >= top:
        return
    rise = top - x.z
    start = x.z
    x.z = top
    b._event("fly", who=x.id, z=x.z, before=start)
    if gentle:
        x.__dict__["soft_landing"] = True
        b.say(f"{x.the_name} rises {rise} feet into the air and hangs there, out of reach.",
              "danger" if x.side == "party" else "good")
    else:
        b.say(f"{x.the_name} falls upward" + (" and slams into the ceiling." if roof else " into the sky."),
              "danger" if x.side == "party" else "good")
    durations.buff(x, {"aloft": c.caster.id, "conc": c.caster.id, "source": f"aloft:{c.sid}"})
    if roof:
        from realmwalker.rules.engine import hazards

        hurt = hazards.falling(b.t, rise)
        if hurt:
            b._hit(None, x, dice.roll(hurt, b.rng).total, "bludgeoning", crit=False, weapon="fall")


@op("one_of")
def _one_of(c: Cast, o: dict, victim) -> None:
    """One of several effects for each creature, by a die (Prismatic Spray's rays): `choices` [[ops], ...]; a face of
    the `die` past the choices brings two of them, rolled again."""
    b = c.b
    if victim is not None:
        victims = [victim]
    elif c.area:
        victims = b.in_area(c.area, c.spell.get("affects", "all"), c.caster)
    else:
        victims = _targets(c)
    choices = o["choices"]
    die = int(o.get("die", len(choices)))
    for x in victims:
        if x is None or not x.active:
            continue
        face = b.rng.randint(1, die)
        picks = [face - 1] if face <= len(choices) else [b.rng.randint(0, len(choices) - 1) for _ in range(2)]
        b.dice_say(f"{x.name}: d{die} = {face}")
        for i in picks:
            if x.active:
                run(c, choices[i], x)


def after_strike(b, f, tok, target) -> None:
    """What a conjured thing's hit brings besides its damage (Conjure Fey's fear): its summon op's `on_hit`."""
    spell = b.t.spells[tok.spell] if tok.spell in b.t.spells else None
    if spell is None or not target.active:
        return
    o = spellrules.op(spell, "summon") or {}
    if o.get("on_hit"):
        c = Cast(b, f, tok.spell, spell, target, None, dc=tok.bonus + 8)
        run(c, o["on_hit"], target)


def warded(b, f, x, level: int, sid: str | None = None) -> bool:
    """A Globe of Invulnerability keeps this spell off `x`: a ward above the spell's level, and the caster outside
    the same barrier. A Wish's Spell Immunity keeps that one spell off (`sid`)."""
    if sid is not None and f is not x and x.char is not None and x.char.effects.get(f"immune_spell:{sid}", 0) > 0:
        return True
    wards = [bf for bf in x.buffs if bf.get("spell_ward") is not None and int(bf["spell_ward"]) > int(level)]
    if not wards or f is x:
        return False
    for bf in wards:
        bearer = next((y for y in b.fighters if y.id == bf.get("aura_of")), None)
        if bearer is None:
            return True
        r = next((int(a["aura"].get("radius", 10)) for a in bearer.buffs
                  if a.get("aura") and "spell_ward" in (a["aura"].get("grant") or {})), 10) // grid.SQUARE_FT
        if grid.gap(bearer.space, f.space) > r:
            return True  # (cast from outside that barrier)
    return False


@op("guardian")
def _guardian(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Token, Zone

    b, f, spell, point = c.b, c.caster, c.spell, c.point
    if point is None:
        return
    tok = Token(b._zone_id(), "guardian", point[0], point[1], f.id, rounds=int(spell.get("rounds", 10)), spell=c.sid)
    b.tokens.append(tok)
    b._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=f.id)
    r = int(o["radius"]) // 5
    cells = {(x, y) for x in range(point[0] - r, point[0] + r + 1) for y in range(point[1] - r, point[1] + r + 1)
             if b.field.in_bounds(x, y)}
    dice_, dtype, up = spellrules.damage_parts(o)[0]
    z = Zone(b._zone_id(), "guardian", cells, owner=f.id, spell=c.sid, rounds=int(spell.get("rounds", 10)), radius=r,
             centre=point, save=o["ability"], dc=c.dc, damage=expr(c, dice_, up), damage_type=dtype,
             on_save="half" if o.get("half") else "none", friends_safe=True, budget=int(o.get("budget", 60)))
    z.token = tok.id  # type: ignore[attr-defined]
    b._add_zone(z)


@op("ally")
def _ally(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules import allies

    level = c.level or int(c.spell.get("level", 1))
    if o.get("kind") == "summon":
        allies.summon_spirit(c.b, c.caster, o["creature"], level, c.point, sid=c.sid)
        return
    if o.get("kind") == "objects":  # (Animate Objects: Expansion 3 F.3)
        allies.animate_objects(c.b, c.caster, level, c.point, sid=c.sid)
        return
    allies.summon(c.b, c.caster, o.get("kind", "steed"), level)


@op("shape")
def _shape(c: Cast, o: dict, victim) -> None:
    """Polymorph, True Polymorph (Expansion 3 F.6): the creature becomes another for as long as the caster
    concentrates (`forms`: the creature types it may become, or "any"). A friend is willing (no save) and takes the
    strongest form it may; a foe makes a Wisdom save or takes the weakest (rules/shapes.py chooses). Animal Shapes and
    Shapechange (F.8): the op's limits and what the shape keeps; Animal Shapes takes every willing friend in range."""
    from realmwalker.rules import shapes

    b, f = c.b, c.caster
    if c.spell.get("concentration") and f.concentration is None:
        return
    if victim is None and c.spell["target"] == "all_allies":
        targets = willing(b, f, c.spell)
        if not targets:
            b.say("Nobody near is willing to take a beast's shape.", "system")
    else:
        x = victim if victim is not None else (f if c.spell["target"] == "self" else c.target)
        targets = [x] if x is not None else []
    kinds = o.get("forms", ["beast"])
    for x in targets:
        if not shapes.shapeable(x):
            b.say(f"The spell finds no grip on {x.the_name}.", "system")
            continue
        friend = x.team == f.team
        if not friend and b._save(x, "wis", c.dc):
            continue
        cid = shapes.best(b.t, x, kinds, o) if friend else shapes.worst(b.t, x, kinds, o)
        if cid is None:
            b.say(f"There is no shape {x.the_name} could take.", "system")
            continue
        was = x.the_name
        if b.shape(x, cid, by=f, spell=c.sid, how=o):
            b.say(f"<magic>{was[:1].upper() + was[1:]} twists and shrinks and swells into "
                  f"{a_or_an(b.t.creatures[cid]['name'])}.</>", "magic")


def willing(b, f, spell: dict) -> list:
    """Who takes Animal Shapes in a fight (Expansion 3 F.8): every friend within range that casts no spells (it would
    lose them for a day) and is not already shaped, never the caster; the game's choice for "any number of willing
    creatures"."""
    from realmwalker.rules import shapes

    reach = b.spell_range(spell)
    out = []
    for x in b.team(f.team):
        if x is f or not x.active or not shapes.shapeable(x) or b.feet(f, x) > reach:
            continue
        if x.char is not None and spellrules.is_caster(x.char, b.t) or x.char is None and (x.cdef or {}).get("spells"):
            continue  # (a caster would lose its spells; a creature's shape lasts the fight: Expansion 3 G.1)
        out.append(x)
    return out


def a_or_an(words: str) -> str:
    return ("an " if words[:1].lower() in "aeiou" else "a ") + words


@op("rise")
def _rise(c: Cast, o: dict, victim) -> None:
    """Finger of Death: the creature it was aimed at, if it lies dead and is of the kinds named, rises at the start
    of the caster's next turn (Expansion 3 F.4)."""
    x = victim if victim is not None else c.target
    if x is None or not hasattr(x, "state") or x.state != "dead" or x.bond is not None:
        return
    if o.get("types") and x.kind not in o["types"]:
        return
    c.b.mark_rising(c.caster, x, o.get("as", "zombie"))


@op("summon")
def _summon(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Token, signed_mod

    b, f, spell, point = c.b, c.caster, c.spell, c.point
    if point is None:
        return
    dice_, dtype, up = spellrules.damage_parts(o)[0]
    tok = Token(b._zone_id(), o.get("token", "spiritual_weapon"), point[0], point[1], f.id,
                rounds=-1 if spell.get("concentration") else int(spell.get("rounds", 10)),
                damage=expr(c, dice_, up) + (signed_mod(c.mod) if o.get("add_mod") else ""), bonus=c.bonus,
                damage_type=dtype, spell=c.sid)
    b.tokens = [t for t in b.tokens if not (t.owner == f.id and t.kind == tok.kind)]
    b.tokens.append(tok)
    b._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=f.id)
    near = [e for e in b.enemies_of(f) if grid.gap((tok.x, tok.y, 1), e.space) <= 1]
    if near:
        b._spirit_strike(f, tok, min(near, key=lambda e: e.hp))


@op("teleport")
def _teleport(c: Cast, o: dict, victim) -> None:
    b, f, point = c.b, c.caster, c.point
    if point is not None:
        start = (f.x, f.y)
        f.x, f.y = point
        b._event("teleport", who=f.id, path=[start, point])
        b._sync_grapples(f)
        if o.get("near") == "tree":
            b.say(f"{f.the_name} steps into a tree and out of another.", "magic")
        else:
            b.say(f"{f.the_name} steps through the mist and is somewhere else.", "magic")


@op("undark")
def _undark(c: Cast, o: dict, victim) -> None:
    """Sunlight ends magical Darkness of `level` or lower that its area overlaps (Daylight): the area is the light
    the caster now carries, `light` squares round them."""
    b, f = c.b, c.caster
    reach = int(o.get("light", 12))
    for z in [z for z in b.zones if z.kind == "darkness"]:
        level = int(b.t.spells[z.spell]["level"]) if getattr(z, "spell", "") in b.t.spells else 2
        if level <= int(o.get("level", 3)) and any(grid.gap(f.space, (x, y, 1)) <= reach for x, y in z.cells):
            b._remove_zone(z)
            b.say("The magical darkness burns away in the sunlight.", "magic")
