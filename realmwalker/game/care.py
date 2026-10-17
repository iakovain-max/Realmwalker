"""Caring for the body at the level of the game: who does the treating, how long it takes, and
healing magic used outside battle. The rules themselves are in rules/health.py."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import health
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.engine import traits
from realmwalker.rules.inventory import remove_item

HEALING_SPELLS = ("cure_wounds", "healing_word", "lesser_restoration", "mass_cure_wounds", "mass_healing_word")
WOODED = {"forest", "pine_forest", "marsh", "hills"}


def healer_for(game, patient: Character) -> Character:
    """The party member best at Medicine who is fit to work (the patient, if alone)."""
    able = [c for c in game.party if c.alive and c.hp > 0]
    return max(able, key=lambda c: Sheet(c, game.tables).skill_bonus("medicine"), default=patient)


def fire_here(game) -> bool:
    camp = getattr(game, "camp", None)
    return bool(camp and camp.fire)


def wooded_here(game) -> bool:
    p = game.player
    return game.biome_key(p.x, p.y) in WOODED


def options(game, patient: Character, wound) -> list[tuple[str, str, bool, str]]:
    healer = healer_for(game, patient)
    return health.treatment_options(healer, patient, wound, game.tables, fire=fire_here(game), wooded=wooded_here(game))


def treat(game, patient: Character, wound, action: str) -> list[str]:
    """Carry out a treatment; time passes. Returns messages for the log."""
    healer = healer_for(game, patient)
    rng = game.world.rng.child(f"treat/{game.world.time}/{patient.name}/{action}")
    ok, msgs, minutes = health.treat(healer, patient, wound, action, game.tables, rng, fire=fire_here(game),
                                     wooded=wooded_here(game), now=game.world.time)
    if healer is not patient and minutes:
        msgs.insert(0, f"{healer.name.split()[0]} sees to {patient.name.split()[0]}.")
    if minutes:
        game.pass_time(minutes, "rest")
    game.dirty = True
    return msgs


def painkiller(game, patient: Character) -> list[str]:
    it = next((i for i in patient.inventory if i.def_id == "poppy_milk"), None)
    if it is None:
        return ["There is no poppy milk in the pack."]
    remove_item(patient, it.uid, 1)
    game.dirty = True
    return [health.take_poppy(patient)]


def drink_potion(game, patient: Character, item) -> list[str]:
    """A potion of healing drunk outside a fight (DMG 2024): its hit points, the worst wound first."""
    d = game.tables.items.get(item.def_id)
    heal = (d.get("use") or {}).get("heal")
    if not heal:
        return ["That is not a healing draught."]
    if patient.hp >= patient.max_hp and not patient.wounds:
        return [f"{patient.name.split()[0]} has no hurt for it to mend; better kept for when there is."]
    owner = next((c for c in game.party if c.item(item.uid) is not None), patient)
    remove_item(owner, item.uid, 1)
    rng = game.world.rng.child(f"potion/{game.world.time}/{patient.name}")
    amount = dice.roll(heal, rng).total
    wound = max(patient.wounds, key=lambda w: (w.severity, w.bleed), default=None)
    game.dirty = True
    game.cue("heal")
    return [f"{patient.name.split()[0]} drinks the {d['name']}: warmth runs through the limbs."] + \
        health.magic_heal(patient, wound, amount)


def healing_magic(game, caster: Character) -> list[tuple[str, str, bool, str]]:
    """(spell id, label, possible, why not) for the healing spells this character knows."""
    out = []
    known = spellrules.known_spells(caster, game.tables)
    for sid in HEALING_SPELLS:
        if sid not in known:
            continue
        ok, why = spellrules.can_cast(caster, game.tables, sid)
        out.append((sid, game.tables.spells[sid]["name"], ok, why))
    return out


def cast(game, caster: Character, patient: Character, wound, spell_id: str, slot_level: int | None = None,
         free: bool = False) -> list[str]:
    """Cast a healing spell outside battle: it uses a slot like any other casting (`slot_level`: a higher one heals
    more); `free`: read from a scroll (no slot, no materials, at the spell's own level)."""
    t = game.tables
    spell = t.spells[spell_id]
    level = spell["level"]
    slot = None
    if not free:
        ok, why = spellrules.can_cast(caster, t, spell_id)
        if not ok:
            return [f"{spell['name']}: {why}."]
        slot = spellrules.lowest_free_slot(caster, t, level) if level else None
        if level and slot_level in spellrules.slot_choices(caster, t, spell_id):
            slot = slot_level
        if level and slot is None:
            return ["No spell slot left for that. A long rest restores them."]
        if slot:
            spellrules.spend_slot(caster, slot)
        spellrules.spend_material(caster, t, spell_id)
    s = Sheet(caster, t)
    rng = game.world.rng.child(f"cast/{game.world.time}/{spell_id}")
    msgs = [] if free else [f"{caster.name.split()[0]} casts <magic>{spell['name']}</>."]
    use = spellrules.road_use(t, spell_id)
    if use == "heal":
        h = spellrules.heal_op(spell)
        targets = [c for c in game.party if c.alive] if spellrules.heals_many(spell) else [patient]
        for c in targets:
            amount = dice.roll(spellrules.scaled(h["dice"], h.get("up", ""), (slot or level) - level), rng).total \
                + (s.mod(spellrules.casting_ability(caster, t)) if h.get("add_mod") else 0)
            if "disciple_of_life" in traits.of_char(caster, t) and not free:  # (2024: with a spell slot)
                amount += 2 + max(1, slot or level)  # (2024: 2 + the slot's level)
            target_wound = wound if c is patient else max(c.wounds, key=lambda w: (w.severity, w.bleed), default=None)
            msgs += health.magic_heal(c, target_wound if h.get("mends_wound", True) else None, amount)
    elif use == "cure":
        msgs += health.magic_restore(patient, t)
    game.pass_time(1, "rest")
    game.dirty = True
    if game.world.factions:
        from realmwalker.game import law

        law.magic_check(game, caster)
    return msgs
