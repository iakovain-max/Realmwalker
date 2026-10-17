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
                    Searing Smite, Ensnaring Strike, Phantasmal Force)
    repeat          an ability: a save at the end of each of its turns ends the mark (against the mark's `dc`)
    heroism         temporary hit points at the start of each of its turns (Heroism)
    immune          [conditions] that cannot take hold of it (Heroism: frightened)
    save_bonus      added to its saving throws (Warding Bond)
    weak            Disadvantage on Strength-based attacks and saves (Ray of Enfeeblement)
    damage_die      "-1d8": added to the damage it deals (Ray of Enfeeblement)
    duel            the caster's id: Disadvantage on attacks against anyone else (Compelled Duel)
    maddened        the caster's id: its turn goes on a blow at one of its own friends (Crown of Madness)
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
})
ZONES = frozenset({"web", "fire", "fog", "ice", "caltrops", "bearings", "darkness", "antimagic", "plants", "grease",
                   "spikes", "daggers", "moonbeam", "sphere", "silence"})


def _weapon(opt) -> bool:
    return opt.kind in ("melee", "ranged") or opt.kind == "unarmed"


def attack_mods(b, att, target, opt, r) -> None:
    """Advantage and Disadvantage from marks (query.attack_roll)."""
    for bf in target.buffs:
        if bf.get("outlined"):
            r.add("advantage", "outlined")
            break
    if any(bf.get("blurred") for bf in target.buffs) and not att.has_trait("blindsight") \
            and not att.has_trait("truesight"):
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
    if bf is None or att.has_trait("blindsight") or att.has_trait("truesight"):
        return False
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


def after_hit(b, att, target, opt) -> None:
    """Armor of Agathys: a melee blow on the warded one, while its temporary hit points hold, is answered in cold."""
    if not opt.is_melee or not att.active:
        return
    for bf in target.buffs:
        if bf.get("retaliate") and target.temp_hp > 0:
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
    """Warding Bond: the caster takes the same damage as the warded one."""
    for bf in list(target.buffs):
        if bf.get("bond") is None or amount <= 0:
            continue
        caster = next((x for x in b.fighters if x.id == bf["bond"]), None)
        if caster is None or caster is target or caster.state not in ("fighting",):
            continue
        if caster.hp <= amount:
            target.buffs.remove(bf)  # (the bond ends when the caster drops)
        b.say(f"The bond carries the hurt to {caster.the_name}.", "magic")
        b._hit(None, caster, amount, "force", crit=False, weapon="warding bond", raw=True)


def turn_start(b, f) -> None:
    """Heroism's courage; harm that comes at the start of a turn."""
    for v in f.buff_value("heroism"):
        if int(v) > f.temp_hp:
            f.temp_hp = int(v)
    _dots(b, f, "start")


def turn_end(b, f) -> None:
    """Harm that comes at the end of a turn; and marks shaken off with a save."""
    _dots(b, f, "end")
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
