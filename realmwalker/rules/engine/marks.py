"""What the marks spells leave on creatures do in a fight (Expansion 3 part D): the buff keys of the spell catalogue's
modifier ops, read where attacks, damage, saves and turns are worked out (rules/combat.py, rules/engine/query.py).

On the one marked (the buff is on the creature):
    outlined        attacks against it have Advantage (Faerie Fire, Shining Smite)
    blurred         attacks against it have Disadvantage (Blur)
    warded_kinds    [kinds]: attacks by those kinds have Disadvantage (Protection from Evil and Good)
    ward_die        "1d4": taken off every attack roll against it (Blade Ward)
    sanctuary       DC: an enemy attacking it makes a Wisdom save first or loses the attack (Sanctuary); ends when the
                    warded one attacks or casts at an enemy
    images          duplicates left: a hit lands on one of them on a d6 of 3 or more (Mirror Image)
    until_act       a condition ("invisible") that ends, with the mark, when it attacks or casts (Invisibility)
    soak            dice (with soak_type): taken off damage of that type, once a turn (Resistance)
    ac_floor        its Armor Class is at least this (Barkskin)
    retaliate       damage (with retaliate_type) to whoever hits it in melee while it has temporary hit points
                    (Armor of Agathys)
    bond            the caster's id: the caster takes the same damage it takes (Warding Bond)
    quarry          dice (with quarry_type, by): extra damage when `by` hits it with an attack (Hex, Hunter's Mark)
    dot             dice (with dot_type, by, dot_at "start" | "end", dot_once): damage at its turn (Melf's Acid Arrow,
                    Searing Smite, Ensnaring Strike, Phantasmal Force); with dot_save and save_first, the save comes
                    first and only a failure hurts (Phantasmal Killer)
    repeat          an ability: a save at the end of each of its turns ends the mark (against the mark's `dc`)
    heroism         temporary hit points at the start of each of its turns (Heroism)
    immune          [conditions] that cannot take hold of it (Heroism: frightened)
    save_bonus      added to its saving throws (Warding Bond)
    weak            Disadvantage on Strength-based attacks and saves (Ray of Enfeeblement)
    damage_die      "-1d8": added to the damage it deals (Ray of Enfeeblement)
    duel            the caster's id: Disadvantage on attacks against anyone else (Compelled Duel)
    maddened        the caster's id: its turn goes on a blow at one of its own friends (Crown of Madness)
    confused        a d10 at the start of each of its turns says what it does (Confusion: `confused_turn`)
    sluggish        half speed, -2 AC and Dexterity saves, no bonus action, one attack an action (Slow)
    haste           double speed, one more attack an action, Advantage on Dexterity saves (with ac 2); when the
                    spell ends, a turn of lethargy (Battle._end_concentration)
    blink           at the end of each of its turns, on a d20 of 11 or more it vanishes until its next (Blink)
    thorns          dice (with thorns_type): damage to whoever hits it with a melee attack (Fire Shield)
    save_adv        [abilities] ("death" for death saves): Advantage on those saves (Beacon of Hope, Haste)
    save_adv_against [conditions]: Advantage on saves against them (Aura of Purity)
    save_adv_spells Advantage on saves against spells (Circle of Power), with evade_spells: no damage on a save
    heal_max        healing it receives is the most the dice can give (Beacon of Hope)
    rise            at the start of its turn at 0 hit points it regains 1 (Aura of Life)
    aura            {"radius": feet, "grant": {buff}}: friends within the radius (and the bearer) have the grant
                    while they stay there (Crusader's Mantle, Aura of Life, Aura of Purity, Circle of Power); the
                    grant's "$level" and the like are filled in as the spell is cast
    dancing         (with dc, by: "$caster") speed 0, Disadvantage on its attacks and Dexterity saves, Advantage on
                    attacks against it; at the start of each of its turns it spends its action on a Wisdom save, and
                    a success ends the dance and the caster's charm (Otto's Irresistible Dance)
    aloft           the caster's id: it hangs in the air (speed 0) and falls when the spell ends (Reverse Gravity,
                    given by the `lift` op)
    spell_ward      a level: spells below it cast from outside the same barrier do nothing to its bearer and leave
                    its squares out of their areas (Globe of Invulnerability, as an aura's grant: "$level")
    truesight       feet of truesight: it sees the invisible and through any darkness (True Seeing)
    befuddled       it cannot cast spells (Befuddlement)
    foresight       Advantage on its attack rolls, saves and checks, Disadvantage on attacks against it (Foresight)
    holy            DC: attacks against it have Disadvantage, and a fiend or undead that hits it in melee makes a
                    Constitution save or is blinded until the end of its next turn (Holy Aura, as an aura's grant:
                    "$dc"; with save_adv for every ability)
    immune_damage   [damage types] it takes none of (Mind Blank: psychic)
    time_stop       turns left in a row (Time Stop: given by the `time_stop` op)
On the one who gains (the caster, or a friend):
    hit_extra       dice (with hit_type, hit_with "weapon" | "melee" | "any"): extra damage on its hits (Divine Favor)
    weapon_plus     added to its weapon attack and damage rolls (Magic Weapon)
    smite           a spell id (with up, dc, mod, smite_with "melee" | "ranged" | "weapon"): its next such hit runs that
                    spell's `on_hit` ops on the one struck, and the mark is spent (the smites, Hail of Thorns)
    once            a save_die mark spent on the next saving throw (Mind Sliver)
"""

from __future__ import annotations

from realmwalker.core import dice

# Every key a buff may carry (the start-up check reports any other in data/spells.json).
BUFF_KEYS = frozenset({
    # the kernel's own
    "ac", "mage_armor", "attack_die", "save_die", "check_die", "resist", "death_ward", "fly", "tremorsense", "slow",
    "no_heal", "no_opportunity", "marked", "burning", "poisoned_blade", "sapped", "distracted", "aimed", "protected",
    "parry_ac", "reeling", "unsteady", "vex", "dazed",
    # this module's
    "outlined", "blurred", "warded_kinds", "ward_die", "sanctuary", "images", "ac_floor", "retaliate",
    "retaliate_type", "bond", "quarry", "quarry_type", "by", "dot", "dot_type", "dot_at", "dot_once", "dot_save",
    "dot_name", "dc", "repeat", "heroism", "immune", "save_bonus", "weak", "damage_die", "duel", "maddened",
    "hit_extra", "hit_type", "hit_with", "weapon_plus", "smite", "smite_with", "up", "mod", "level", "once", "traits",
    "shillelagh", "tier", "until_act", "soak", "soak_type", "soak_turn",
    # the second wave's (D.2)
    "confused", "sluggish", "haste", "blink", "thorns", "thorns_type", "save_adv", "save_adv_against",
    "save_adv_spells", "evade_spells", "heal_max", "rise", "aura", "grant", "radius", "aura_of", "save_first",
    # the third wave's (D.3)
    "dancing", "truesight", "aloft", "spell_ward",
    # the fourth wave's (D.4)
    "befuddled", "foresight", "holy", "immune_damage", "time_stop",
})
ZONES = frozenset({"web", "fire", "fog", "ice", "caltrops", "bearings", "darkness", "antimagic", "plants", "grease",
                   "spikes", "daggers", "moonbeam", "sphere", "silence",
                   # the second wave's (D.2): ground with a save and what a failure brings (Battle._ground)
                   "tentacles", "cloud", "stench", "hunger", "insects", "sleet", "radiance", "spirits", "elemental",
                   "wind", "stone", "force",
                   # the third wave's (D.3): walls of blades and thorns, a pillar of light, a wall of ice
                   "blades", "thorns", "celestial", "icewall",
                   # the fourth wave's (D.4): an earthquake, a burning cloud, the prismatic wall and its glare, a storm
                   "quake", "embers", "prismatic", "glare", "storm"})


def _weapon(opt) -> bool:
    return opt.kind in ("melee", "ranged") or opt.kind == "unarmed"


def attack_mods(b, att, target, opt, r) -> None:
    """Advantage and Disadvantage from marks (query.attack_roll)."""
    for bf in target.buffs:
        if bf.get("outlined"):
            r.add("advantage", "outlined")
            break
    if any(bf.get("blurred") for bf in target.buffs) and not att.has_trait("blindsight") \
            and not att.has_trait("truesight") and not att.buff_value("truesight"):
        r.add("disadvantage", "blurred")
    for bf in target.buffs:
        if att.kind in (bf.get("warded_kinds") or ()):
            r.add("disadvantage", "warded")
            break
    for bf in att.buffs:
        if bf.get("duel") is not None and bf["duel"] != target.id \
                and any(x.id == bf["duel"] and x.active for x in b.fighters):
            r.add("disadvantage", "compelled to duel")
            break
    if opt.is_melee and "finesse" not in opt.properties and any(bf.get("weak") for bf in att.buffs):
        r.add("disadvantage", "enfeebled")
    if any(bf.get("dancing") for bf in att.buffs):
        r.add("disadvantage", "dancing")  # (Otto's Irresistible Dance)
    if any(bf.get("dancing") for bf in target.buffs):
        r.add("advantage", "dancing")
    if att.buff_value("foresight"):
        r.add("advantage", "foresight")
    if target.buff_value("foresight"):
        r.add("disadvantage", "foresight")
    if target.buff_value("holy") and att.team != target.team:
        r.add("disadvantage", "holy aura")


def roll_adjust(b, att, target, opt) -> int:
    """What marks add to an attack roll: a magic weapon's bonus; a ward's die taken off."""
    out = 0
    if _weapon(opt) and opt.item_uid is not None:
        out += sum(int(v) for v in att.buff_value("weapon_plus"))
    for d in target.buff_value("ward_die"):
        out -= dice.roll(str(d).lstrip("-"), b.rng).total
    return out


def sanctuary_stops(b, att, target) -> bool:
    """Sanctuary: an enemy who would strike the warded one makes a Wisdom save, or the attack is lost. True when it
    is. The warded one's own attack ends it."""
    att.buffs = [bf for bf in att.buffs if not bf.get("sanctuary")]
    ward = next((bf for bf in target.buffs if bf.get("sanctuary")), None)
    if ward is None or att.team == target.team:
        return False
    if b._save(att, "wis", int(ward["sanctuary"])):
        return False
    b.say(f"{att.the_name} cannot bring themselves to strike {target.the_name}. (Sanctuary)", "magic")
    return True


def end_sanctuary(f) -> None:
    f.buffs = [bf for bf in f.buffs if not bf.get("sanctuary")]


def acted(b, f) -> None:
    """Invisibility (2024): it ends on the one it hides when they attack, deal damage or cast a spell."""
    gone = [bf for bf in f.buffs if bf.get("until_act")]
    if not gone:
        return
    f.buffs = [bf for bf in f.buffs if not bf.get("until_act")]
    for bf in gone:
        if bf["until_act"] in f.conditions:
            f.conditions.pop(bf["until_act"], None)
            b.say(f"{f.the_name} flickers back into sight.", "system")


def image_takes_it(b, att, target) -> bool:
    """Mirror Image: a hit may land on a duplicate instead (a d6 for each left, 3 or more), which is destroyed."""
    bf = next((bf for bf in target.buffs if bf.get("images")), None)
    if bf is None or att.has_trait("blindsight") or att.has_trait("truesight") or "blinded" in att.conditions:
        return False  # (an attacker who does not rely on sight is not fooled)
    n = int(bf["images"])
    if not any(b.rng.randint(1, 6) >= 3 for _ in range(n)):
        return False
    bf["images"] = n - 1
    if bf["images"] <= 0:
        target.buffs.remove(bf)
    b.say(f"The blow passes through one of {target.the_name}'s images, and it vanishes.", "magic")
    b._event("image", who=target.id)
    return True


def hit_damage(b, att, target, opt, amount: int, crit: bool) -> int:
    """The marks that change a hit's own damage: a magic weapon's bonus, an enfeebled striker's die."""
    if _weapon(opt) and opt.item_uid is not None:
        amount += sum(int(v) for v in att.buff_value("weapon_plus"))
    for d in att.buff_value("damage_die"):
        sign = -1 if str(d).startswith("-") else 1
        amount += sign * dice.roll(str(d).lstrip("-"), b.rng).total
    return amount


def extra_hits(b, att, target, opt, crit: bool) -> list[tuple[int, str]]:
    """Damage of other kinds a hit brings from marks: Divine Favor, Hex and Hunter's Mark."""
    out = []
    for bf in att.buffs:
        if bf.get("hit_extra"):
            how = bf.get("hit_with", "weapon")
            if how == "any" or how == "weapon" and _weapon(opt) or how == "melee" and opt.is_melee:
                out.append((dice.roll(bf["hit_extra"], b.rng, double_dice=crit).total, bf.get("hit_type", "radiant")))
    for bf in target.buffs:
        if bf.get("quarry") and bf.get("by") == att.id:
            out.append((dice.roll(bf["quarry"], b.rng, double_dice=crit).total, bf.get("quarry_type", "force")))
    return out


def smite(b, att, target, opt, crit: bool) -> None:
    """A smite readied on the weapon: its next fitting hit runs the spell's `on_hit` ops on the one struck."""
    from realmwalker.rules.engine import effects

    for bf in list(att.buffs):
        sid = bf.get("smite")
        if not sid or sid not in b.t.spells:
            continue
        how = bf.get("smite_with", "melee")
        if how == "melee" and not opt.is_melee or how == "ranged" and opt.is_melee or not _weapon(opt):
            continue
        att.buffs.remove(bf)
        spell = b.t.spells[sid]
        b.say(f"<magic>{spell['name']}!</>", "magic")
        b._event("cast", by=att.id, to=target.id, spell=sid, effect=effects.mechanic(spell), look=spell.get("fx", ""),
                 dtype=_main(spell), area=list(target.cells), point=None, shape="")
        c = effects.Cast(b, att, sid, spell, target, None, up=int(bf.get("up", 0)), mod=int(bf.get("mod", 0)),
                         dc=int(bf.get("dc", 10)), level=int(bf.get("level", spell["level"])),
                         crit=crit)
        before = b.__dict__.get("_casting")
        b._casting = att
        try:
            effects.run(c, spell.get("on_hit", ()), target)
        finally:
            b._casting = before
        return


def _main(spell: dict) -> str:
    from realmwalker.rules import spells as spellrules

    for o in spell.get("on_hit", ()):
        parts = spellrules.damage_parts(o)
        if parts:
            return parts[0][1]
    return spellrules.main_type(spell)


def after_hit(b, att, target, opt, guarded: bool = True) -> None:
    """Armor of Agathys: a melee blow on the warded one, while its temporary hit points held (`guarded`: before the
    blow), is answered in cold; the spell ends with the last of them. Fire Shield answers every melee hit."""
    if not opt.is_melee or not att.active:
        return
    holy = target.buff_value("holy")
    if holy and att.kind in ("fiend", "undead") and att.team != target.team and "blinded" not in att.conditions:
        from realmwalker.rules.engine import durations

        if not b._save(att, "con", int(holy[0])):  # (Holy Aura: the light sears the eyes of fiends and the dead)
            if durations.give(b, att, "blinded", ends=durations.until(b, att, "turn_end")):
                b._event("condition", who=att.id, cond="blinded")
                b.say(f"Holy light blinds {att.the_name}.", "good" if att.side == "foe" else "danger")
    for bf in list(target.buffs):
        if bf.get("thorns") and att.team != target.team:
            dtype = bf.get("thorns_type", "fire")
            b.say(f"{'Flames' if dtype == 'fire' else 'Bitter cold'} lash back at {att.the_name}.", "magic")
            b._hit(target, att, dice.roll(str(bf["thorns"]), b.rng).total, dtype, crit=False, weapon="the shield")
            if not att.active:
                return
    for bf in list(target.buffs):
        if bf.get("retaliate") and guarded:
            if target.temp_hp <= 0:
                target.buffs.remove(bf)
            b.say(f"Frost bites back at {att.the_name}.", "magic")
            b._hit(target, att, int(bf["retaliate"]), bf.get("retaliate_type", "cold"), crit=False,
                   weapon="armour of frost")
            return


def soaked(b, target, amount: int, dtype: str) -> int:
    """Resistance (2024): damage of the chosen type is cut by a die, once a turn."""
    for bf in target.buffs:
        if bf.get("soak") and bf.get("soak_type") == dtype and bf.get("soak_turn") != (b.round, b.turn) and amount > 0:
            bf["soak_turn"] = (b.round, b.turn)
            cut = dice.roll(str(bf["soak"]), b.rng).total
            b.note_roll(f"Resistance: {cut} off")
            return max(0, amount - cut)
    return amount


def shared(b, target, amount: int) -> None:
    """Warding Bond: the caster takes the same damage as the warded one (once: a hurt passed on is not passed back)."""
    if b.__dict__.get("_bonded"):
        return
    for bf in list(target.buffs):
        if bf.get("bond") is None or amount <= 0:
            continue
        caster = next((x for x in b.fighters if x.id == bf["bond"]), None)
        if caster is None or caster is target or caster.state not in ("fighting",):
            continue
        if caster.hp <= amount:
            target.buffs.remove(bf)  # (the bond ends when the caster drops)
        b.say(f"The bond carries the hurt to {caster.the_name}.", "magic")
        b._bonded = True
        try:
            b._hit(None, caster, amount, "force", crit=False, weapon="warding bond", raw=True)
        finally:
            b._bonded = False


def turn_start(b, f) -> None:
    """Heroism's courage; harm that comes at the start of a turn; Aura of Life lifting the fallen."""
    for v in f.buff_value("heroism"):
        if int(v) > f.temp_hp:
            f.temp_hp = int(v)
    if f.state == "down" and f.hp <= 0 and f.buff_value("rise"):
        b.say(f"The aura of life stirs {f.the_name}.", "magic")
        b._heal(f, 1)
    _dots(b, f, "start")


def after_turn_start(b, f) -> None:
    """What a mark takes from a turn as it begins (Slow: no bonus action)."""
    if f.buff_value("sluggish"):
        f.bonus = 0


def share_auras(b) -> None:
    """Auras that help friends (an `aura` buff on its bearer): those within the radius have its grant, held by the
    bearer's concentration. Run whenever anyone moves and at the start of every turn."""
    for x in b.fighters:
        if any(bf.get("aura_of") is not None for bf in x.buffs):
            x.buffs = [bf for bf in x.buffs if bf.get("aura_of") is None]
    from realmwalker.rules import grid

    for bearer in b.fighters:
        if bearer.state not in ("fighting", "fleeing"):
            continue
        for bf in bearer.buffs:
            aura = bf.get("aura")
            if not aura:
                continue
            r = int(aura.get("radius", 30)) // grid.SQUARE_FT
            for x in b.fighters:
                if x.team != bearer.team or not (x.active or x.state == "down"):
                    continue
                if x is not bearer and grid.gap(bearer.space, x.space) > r:
                    continue
                grant = {**aura.get("grant", {}), "aura_of": bearer.id, "source": bf.get("source", "aura")}
                if bf.get("conc") is not None:
                    grant["conc"] = bf["conc"]
                x.buffs.append(grant)


def dancing_turn(b, f) -> bool:
    """Otto's Irresistible Dance: at the start of its turn the dancer spends its turn collecting itself, a Wisdom
    save against the mark's DC; a success ends the dance and the caster's charm with it. True when the turn went on
    it."""
    bf = next((bf for bf in f.buffs if bf.get("dancing")), None)
    if bf is None or f.action <= 0 or f.incapacitated:
        return False
    f.action -= 1
    if b._save(f, "wis", int(bf.get("dc", 10))):
        src = bf.get("source")
        f.buffs = [x for x in f.buffs if x.get("source") != src or not src]
        if "charmed" in f.conditions and f.sources.get("charmed") == bf.get("by"):
            from realmwalker.rules.engine import durations

            durations.remove(f, "charmed")
        b.say(f"{f.the_name} stumbles out of the dance.", "system")
    else:
        b.say(f"{f.the_name} dances on, helplessly.", "good" if f.side == "foe" else "danger")
    return True


def confused_turn(b, f) -> bool:
    """Confusion (2024): at the start of its turn a d10 says what it does. 1: it wanders off in a random direction
    and does nothing else; 2-6: it does nothing at all; 7-8: it strikes at a random creature within reach (or does
    nothing); 9-10: it acts as it chooses. True when the turn was taken from it."""
    if not f.buff_value("confused") or not f.can_act():
        return False
    roll = b.rng.randint(1, 6 + 4)
    b.dice_say(f"{f.name}, confused: d10 = {roll}")
    if roll >= 9:
        return False
    if roll == 1:
        steps = []
        x, y = f.x, f.y
        dx, dy = b.rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)])
        for _ in range(max(0, f.move_left // 5)):
            if not b.field.fits(x + dx, y + dy, f.sq) or (x + dx, y + dy) in b.occupied_by_others(f):
                break
            x, y = x + dx, y + dy
            steps.append((x, y))
        b.say(f"{f.the_name} stumbles off, lost in a daze.", "system")
        if steps:
            b.do_move(f, steps[-1])
    elif roll <= 6:
        b.say(f"{f.the_name} stands bewildered and does nothing.", "system")
    else:
        near = [x for x in b.fighters if x is not f and x.active and b.gap(f, x) <= 1]
        opts = [o for o in b.attack_options(f) if o.available and o.is_melee]
        if near and opts:
            victim = b.rng.choice(near)
            b.say(f"{f.the_name} lashes out wildly at {victim.the_name}.", "system")
            b._attack(f, max(opts, key=lambda o: o.bonus), victim)
            b._check_end()
        else:
            b.say(f"{f.the_name} swings at nothing.", "system")
    return True


def turn_end(b, f) -> None:
    """Harm that comes at the end of a turn; and marks shaken off with a save; Blink's roll."""
    _dots(b, f, "end")
    if f.active and f.buff_value("blink") and b.rng.randint(1, 20) >= 11:
        b.send_away(f, "blink", by=f)
    for bf in list(f.buffs):
        if bf.get("repeat") and bf in f.buffs and f.active:
            if b._save(f, bf["repeat"], int(bf.get("dc", 10))):
                f.buffs.remove(bf)
                b.say(f"{f.the_name} shakes off the spell.", "system")


def _dots(b, f, at: str) -> None:
    for bf in list(f.buffs):
        if not bf.get("dot") or bf.get("dot_at", "start") != at or not (f.active or f.state == "down"):
            continue
        by = next((x for x in b.fighters if x.id == bf.get("by")), None)
        if bf.get("save_first") and bf.get("dot_save"):  # (Phantasmal Killer: the save comes first)
            if b._save(f, bf["dot_save"], int(bf.get("dc", 10))):
                f.buffs.remove(bf)
                b.say(f"{f.the_name} is free of it.", "system")
                continue
            b._hit(by, f, dice.roll(str(bf["dot"]), b.rng).total, bf.get("dot_type", "fire"), crit=False,
                   weapon=bf.get("dot_name", "the spell"))
            continue
        amount = dice.roll(str(bf["dot"]), b.rng).total
        b._hit(by, f, amount, bf.get("dot_type", "fire"), crit=False, weapon=bf.get("dot_name", "the spell"))
        if bf.get("dot_once") and bf in f.buffs:
            f.buffs.remove(bf)
        elif bf.get("dot_save") and bf in f.buffs and f.active:
            if b._save(f, bf["dot_save"], int(bf.get("dc", 10))):
                f.buffs.remove(bf)
                b.say(f"{f.the_name} is free of it.", "system")


def spend_saves(f) -> None:
    """A die taken off the next saving throw only (Mind Sliver) is spent on it."""
    f.buffs = [bf for bf in f.buffs if not (bf.get("once") and "save_die" in bf)]


def maddened_by(f) -> int | None:
    return next((bf["maddened"] for bf in f.buffs if bf.get("maddened") is not None), None)
