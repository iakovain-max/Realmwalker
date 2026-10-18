"""Expansion 5 Part D: the DMG 2024's eleven wands, seven staffs and four rods as treasure makers (data/treasure.json
"makers"), checked against the page images (DMG pp. 262, 299-305, 306-315, 318-322 of the PDF).

    .venv\\Scripts\\python.exe tools\\codex\\wands_staffs_rods.py    writes them into data/treasure.json

Each wand, staff or rod keeps one store of charges (`pool`: value, regain dice, what a d20 of 1 does to it when the
last charge goes, what a 20 gives back) and its spells draw from it (`charges` with a `cost`, maybe a `level`, `more`
charges for higher levels, the item's own `dc`). rules/magic.py reads them."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAND = ["arcane_wand"]
STAFF = ["arcane_staff"]
QSTAFF = ["quarterstaff"]
ROD = ["arcane_rod"]
CASTERS = "spellcaster"


def pool(n: int, regain: str, last: str | None = "crumble", lucky: str | None = None, text: str = "") -> dict:
    p = {"kind": "pool", "value": n, "left": n, "regain": regain}
    if last:
        p["last"] = last
    if lucky:
        p["lucky"] = lucky
    p["text"] = text or (f"{n} charges; {regain} come back each dawn" + (
        ". When the last is spent, a d20: on a 1 it " + {"crumble": "crumbles into ashes",
                                                          "vanish": "is gone for ever",
                                                          "display": "goes up in a last display",
                                                          "mundane": "loses its magic",
                                                          "weaken": "keeps only its edge as a weapon"}[last]
        if last else "") + (f"; on a 20, {lucky} come back" if lucky else "") + ".")
    return p


def spell(sid: str, cost: int, text: str, **kw) -> dict:
    return {"kind": "charges", "spell": sid, "cost": cost, **kw, "text": text}


MAKERS: dict[str, dict] = {
    # ------------------------------------------------------------------ wands (DMG 2024 pp. 318-322)
    "wand_of_binding": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Binding", "attune": True, "props": [
        pool(7, "1d6+1"),
        spell("hold_monster", 5, "Hold Monster (DC 17) for 5 charges.", dc=17),
        spell("hold_person", 2, "Hold Person (DC 17) for 2 charges.", dc=17)]}},
    "wand_of_enemy_detection": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Enemy Detection", "attune": True,
                                     "props": [
        pool(7, "1d6+1"),
        spell("wand_enemy_detection", 1, "A charge and the Magic action: for a minute you know where every foe within "
              "60 feet is, the invisible and the hidden too.")]}},
    "wand_of_fear": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Fear", "attune": True, "props": [
        pool(7, "1d6+1"),
        spell("command", 1, "Command (DC 15), 'Grovel!', for 1 charge.", dc=15),
        spell("wand_fear", 3, "Fear in a 60-foot cone (DC 15) for 3 charges.", dc=15)]}},
    "wand_of_fireballs": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Fireballs", "attune": True,
                               "attune_by": CASTERS, "props": [
        pool(7, "1d6+1"),
        spell("fireball", 1, "Fireball (DC 15) at level 3 for 1 charge, a level higher for each charge more (3 at "
              "most).", level=3, more=2, dc=15)]}},
    "wand_of_lightning_bolts": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Lightning Bolts", "attune": True,
                                     "attune_by": CASTERS, "props": [
        pool(7, "1d6+1"),
        spell("lightning_bolt", 1, "Lightning Bolt (DC 15) at level 3 for 1 charge, a level higher for each charge more "
              "(3 at most).", level=3, more=2, dc=15)]}},
    "wand_of_magic_detection": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Magic Detection", "props": [
        pool(3, "1d3", last=None),
        spell("detect_magic", 1, "Detect Magic for 1 charge.")]}},
    "wand_of_magic_missiles": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Magic Missiles", "props": [
        pool(7, "1d6+1"),
        spell("magic_missile", 1, "Magic Missile at level 1 for 1 charge, a level higher for each charge more (3 at "
              "most).", level=1, more=2)]}},
    "wand_of_paralysis": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Paralysis", "attune": True,
                               "attune_by": CASTERS, "props": [
        pool(7, "1d6+1"),
        spell("wand_paralysis", 1, "A thin blue ray at a creature within 60 feet for 1 charge: a Constitution save "
              "(DC 15) or Paralyzed for a minute, a save at the end of each of its turns.")]}},
    "wand_of_polymorph": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Polymorph", "attune": True,
                               "attune_by": CASTERS, "props": [
        pool(7, "1d6+1"),
        spell("polymorph", 1, "Polymorph (DC 15) for 1 charge.", dc=15)]}},
    "wand_of_pyrotechnics": {"": {"kind": "focus", "bases": WAND, "title": "Wand of Pyrotechnics", "props": [
        pool(7, "1d6+1", last="display", text="7 charges; 1d6+1 come back each dawn. When the last is spent, a d20: on a 1 it goes up "
             "in a last harmless display and is gone."),
        {"kind": "flag", "flag": "fireworks", "text": "A charge throws a harmless burst of coloured fire into the night "
         "with a crackle heard far off: an evening's show by the camp fire (the camp's evening, e), and the "
         "company's spirits rise."}]}},
    "wand_of_the_war_mage": {
        f"+{n}": {"kind": "focus", "bases": WAND, "title": f"Wand of the War Mage +{n}", "attune": True,
                  "attune_by": CASTERS, "props": [
            {"kind": "spell_attack", "value": n, "text": f"+{n} to spell attack rolls while held."},
            {"kind": "flag", "flag": "spell_cover", "text": "Your spell attacks ignore half cover."}]}
        for n in (1, 2, 3)},
    # ------------------------------------------------------------------ staffs (DMG 2024 pp. 306-311, 258)
    "staff_of_adornment": {"": {"kind": "focus", "bases": STAFF, "title": "Staff of Adornment", "props": [
        {"kind": "flag", "flag": "adornment", "text": "Up to three tiny things float an inch above its tip, turning "
         "slowly at your wish; it serves as an arcane focus."}]}},
    "staff_of_charming": {"": {"kind": "focus", "bases": STAFF, "title": "Staff of Charming", "attune": True,
                               "attune_by": ["bard", "cleric", "druid", "sorcerer", "warlock", "wizard"], "props": [
        pool(10, "1d8+2"),
        spell("charm_person", 1, "Charm Person for 1 charge, with your own save DC."),
        spell("command", 1, "Command for 1 charge, with your own save DC."),
        spell("comprehend_languages", 1, "Comprehend Languages for 1 charge."),
        {"kind": "trait", "trait": "staff_of_charming", "text": "Reflect Enchantment: a save made against an "
         "enchantment aimed at you alone turns it back on its caster (a reaction and a charge). Resist Enchantment: "
         "once a day such a save failed becomes a success."},
        {"kind": "trait", "trait": "resist_enchantment", "daily": True}]}},
    "staff_of_healing": {"": {"kind": "focus", "bases": STAFF, "title": "Staff of Healing", "attune": True,
                              "attune_by": ["bard", "cleric", "druid"], "props": [
        pool(10, "1d6+4", last="vanish"),
        spell("cure_wounds", 1, "Cure Wounds, a charge for each level of the spell (4 at most).", level=1, more=3),
        spell("lesser_restoration", 2, "Lesser Restoration for 2 charges."),
        spell("mass_cure_wounds", 5, "Mass Cure Wounds for 5 charges.")]}},
    "staff_of_power": {"": {"kind": "weapon", "bases": QSTAFF, "title": "Staff of Power", "attune": True,
                            "attune_by": ["sorcerer", "warlock", "wizard"], "props": [
        {"kind": "bonus", "value": 2},
        {"kind": "ac", "value": 2, "text": "+2 to Armor Class while held."},
        {"kind": "save", "value": 2, "text": "+2 to every saving throw while held."},
        {"kind": "spell_attack", "value": 2, "text": "+2 to spell attack rolls while held."},
        pool(20, "2d8+4", last="weaken", lucky="1d8+2"),
        spell("cone_of_cold", 5, "Cone of Cold for 5 charges."),
        spell("fireball", 5, "Fireball at level 5 for 5 charges.", level=5),
        spell("globe_of_invulnerability", 6, "Globe of Invulnerability for 6 charges."),
        spell("hold_monster", 5, "Hold Monster for 5 charges."),
        spell("levitate", 2, "Levitate for 2 charges."),
        spell("lightning_bolt", 5, "Lightning Bolt at level 5 for 5 charges.", level=5),
        spell("magic_missile", 1, "Magic Missile for 1 charge."),
        spell("ray_of_enfeeblement", 1, "Ray of Enfeeblement for 1 charge."),
        spell("wall_of_force", 5, "Wall of Force for 5 charges."),
        {"kind": "trait", "trait": "retributive_strike", "times": 4, "text": "Retributive Strike: broken over the "
         "knee, it explodes 30 feet round (16 force for each charge to you unless you are flung clear, half the time; "
         "4 for each to everyone else, a Dexterity save (DC 17) for half)."}]}},
    "staff_of_striking": {"": {"kind": "weapon", "bases": QSTAFF, "title": "Staff of Striking", "attune": True,
                               "props": [
        {"kind": "bonus", "value": 3},
        pool(10, "1d6+4", last="mundane"),
        {"kind": "trait", "trait": "staff_of_striking", "text": "A melee hit with it may spend up to 3 charges: 1d6 "
         "force more for each."}]}},
    "staff_of_the_magi": {"": {"kind": "weapon", "bases": QSTAFF, "title": "Staff of the Magi", "attune": True,
                               "attune_by": ["sorcerer", "warlock", "wizard"], "props": [
        {"kind": "bonus", "value": 2},
        {"kind": "spell_attack", "value": 2, "text": "+2 to spell attack rolls while held."},
        pool(50, "4d6+2", last=None, lucky="1d12+1"),
        {"kind": "trait", "trait": "staff_of_the_magi", "text": "Spell Absorption: Advantage on saves against spells; "
         "a spell aimed at you alone may be drunk by the staff (a reaction), its level added to the charges (past 50 "
         "the staff explodes)."},
        {"kind": "trait", "trait": "retributive_strike", "times": 6, "text": "Retributive Strike: broken over the "
         "knee, it explodes 30 feet round (16 force for each charge to you unless you are flung clear, half the time; "
         "6 for each to everyone else, a Dexterity save (DC 17) for half)."},
        spell("arcane_lock", 0, "Arcane Lock, at will."),
        spell("detect_magic", 0, "Detect Magic, at will."),
        spell("enlarge_reduce", 0, "Enlarge/Reduce, at will."),
        spell("light", 0, "Light, at will."),
        spell("mage_hand", 0, "Mage Hand, at will."),
        spell("protection_from_evil_and_good", 0, "Protection from Evil and Good, at will."),
        spell("conjure_elemental", 7, "Conjure Elemental for 7 charges."),
        spell("dispel_magic", 3, "Dispel Magic for 3 charges."),
        spell("fireball", 7, "Fireball at level 7 for 7 charges.", level=7),
        spell("flaming_sphere", 2, "Flaming Sphere for 2 charges."),
        spell("ice_storm", 4, "Ice Storm for 4 charges."),
        spell("invisibility", 2, "Invisibility for 2 charges."),
        spell("knock", 2, "Knock for 2 charges."),
        spell("lightning_bolt", 7, "Lightning Bolt at level 7 for 7 charges.", level=7),
        spell("passwall", 5, "Passwall for 5 charges."),
        spell("plane_shift", 7, "Plane Shift for 7 charges."),
        spell("telekinesis", 5, "Telekinesis for 5 charges."),
        spell("wall_of_fire", 4, "Wall of Fire for 4 charges."),
        spell("web", 2, "Web for 2 charges.")]}},
    "enspelled_staff": {
        variant: {"kind": "weapon", "bases": QSTAFF, "title": "Enspelled Staff", "attune": True, "attune_by": CASTERS,
                  "enspell": True, "props": [pool(6, "1d6", last="mundane")]}
        for variant in ("cantrip or level 1 spell", "level 2 or 3 spell", "level 4 or 5 spell",
                        "level 6, 7, or 8 spell")},
    # ------------------------------------------------------------------ rods (DMG 2024 pp. 299-301)
    "rod_of_absorption": {"": {"kind": "focus", "bases": ROD, "title": "Rod of Absorption", "attune": True, "props": [
        {"kind": "absorb", "dice": "1d10", "most": 50, "text": "A reaction drinks a spell aimed at you alone that "
         "fills no area: its levels are stored (50 in all its life). A caster holding it spends the stored levels as "
         "spell slots up to level 5."},
        {"kind": "trait", "trait": "rod_of_absorption"}]}},
    "rod_of_alertness": {"": {"kind": "focus", "bases": ROD, "title": "Rod of Alertness", "attune": True, "props": [
        {"kind": "trait", "trait": "rod_of_alertness", "text": "Advantage on Wisdom (Perception) checks and on "
         "Initiative while held."},
        {"kind": "charges", "spell": "detect_evil_and_good", "at_will": True, "text": "Detect Evil and Good, at will."},
        {"kind": "charges", "spell": "detect_magic", "at_will": True, "text": "Detect Magic, at will."},
        {"kind": "charges", "spell": "detect_poison_and_disease", "at_will": True,
         "text": "Detect Poison and Disease, at will."},
        {"kind": "charges", "spell": "see_invisibility", "at_will": True, "text": "See Invisibility, at will."},
        {"kind": "charges", "spell": "rod_aura", "value": 1, "left": 1, "text": "Protective Aura, once a day: planted, "
         "it sheds bright light 60 feet round for ten minutes; you and your friends in it have +1 to Armor Class and "
         "saves and see the invisible."}]}},
    "rod_of_resurrection": {"": {"kind": "focus", "bases": ROD, "title": "Rod of Resurrection", "attune": True,
                                 "attune_by": ["cleric", "druid", "paladin"], "props": [
        pool(5, "1", last="vanish", text="5 charges; 1 comes back each dawn. When the last is spent, a d20: on a 1 it "
             "is gone in a harmless burst of radiance."),
        spell("heal", 1, "Heal for 1 charge."),
        spell("resurrection", 5, "Resurrection for 5 charges.")]}},
    "rod_of_rulership": {"": {"kind": "focus", "bases": ROD, "title": "Rod of Rulership", "attune": True, "props": [
        {"kind": "charges", "spell": "rod_rulership", "value": 1, "left": 1, "text": "Once a day, the Magic action: "
         "every foe within 120 feet makes a Wisdom save (DC 15) or is Charmed for eight hours, taking you for its "
         "trusted leader until you or your friends harm it."}]}},
}

# The Enspelled Staff's numbers by the level of its spell (DMG 2024 p. 258): [save DC, attack bonus].
ENSPELL = {"0": [13, 5], "1": [13, 5], "2": [13, 5], "3": [15, 7], "4": [15, 7], "5": [17, 9], "6": [17, 9],
           "7": [18, 10], "8": [18, 10]}


def main() -> None:
    path = ROOT / "data" / "treasure.json"
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith('"makers": {'))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("  }"))
    keep = [ln for ln in lines[start + 1:end] if not any(ln.strip().startswith(f'"{k}"') for k in MAKERS)]
    if keep and not keep[-1].rstrip().endswith(","):
        keep[-1] = keep[-1].rstrip() + ","
    new = [f'    "{k}": {json.dumps(v, ensure_ascii=False)},' for k, v in MAKERS.items()]
    new[-1] = new[-1].rstrip(",")
    lines[start + 1:end] = keep + new
    out = "\n".join(lines)
    out = re.sub(r'\n  "enspell": \{[^\n]*\},?', "", out)  # (the Enspelled Staff's table, written afresh)
    out = out.replace('\n  "makers": {', '\n  "enspell": ' + json.dumps(ENSPELL) + ',\n  "makers": {', 1)
    json.loads(out)
    path.write_text(out, encoding="utf-8", newline="\n")
    print(f"{len(MAKERS)} makers written")


if __name__ == "__main__":
    main()
