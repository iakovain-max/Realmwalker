"""Expansion 5 Part E: the DMG 2024's crystal balls, the Enduring Spellbook, Enspelled Armor and Weapon, the two
wizard's hats, the Pearl of Power, the Ring of Spell Storing, the five robes and the Ruby of the War Mage as treasure
makers (data/treasure.json "makers"), checked against the page images (DMG pp. 249-250, 261-262, 270-271, 288, 299,
301-303, 306 of the PDF).

    .venv\\Scripts\\python.exe tools\\codex\\wizard_wonders.py    writes them into data/treasure.json

Properties the rules read (rules/magic.py and the handlers named): `charges` with `worn` (only while worn or held),
`stored` (a spell kept in a ring: cast once at its `level` with its caster's `dc`, `attack` and `mod`), `sense`
(darkvision or truesight in feet), `spell_dc`, `base_ac` (unarmoured), `focus` (a spellcasting focus `for` a class),
`hat` (a wizard's hat's Unknown Spell: rules/hats.py), `store` (the ring's room), `patches` (the Robe of Useful
Items), `war_ruby` (the Ruby of the War Mage); traits pearl_of_power, robe_of_eyes, robe_of_stars."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROBE = ["robe"]
HAT = ["pointed_hat"]
SPELL_LEVELS = ("cantrip or level 1 spell", "level 2 or 3 spell", "level 4 or 5 spell", "level 6, 7, or 8 spell")


def ball(extra: list[dict] | None = None, title: str = "Crystal Ball") -> dict:
    return {"kind": "focus", "bases": ["arcane_orb"], "title": title, "attune": True, "props": [
        {"kind": "charges", "spell": "scrying", "at_will": True, "dc": 17,
         "text": "Scrying (save DC 17) at will while you touch it: it is the mirror, and nothing else is needed."}]
        + (extra or [])}


MAKERS: dict[str, dict] = {
    # ------------------------------------------------------------------ crystal balls (DMG 2024 pp. 245-246)
    "crystal_ball": {
        "": ball(),
        "of mind reading": ball([{"kind": "flag", "flag": "scry_thoughts", "text": "Whoever you scry, you read "
                                  "their thoughts as well (Detect Thoughts, DC 17, as long as the scrying lasts)."}],
                                "Crystal Ball of Mind Reading"),
        "of telepathy": ball([{"kind": "flag", "flag": "scry_thoughts", "text": "Whoever you scry, you speak with "
                               "mind to mind and hear what they think."},
                              {"kind": "flag", "flag": "scry_suggest", "daily": True, "text": "Once a day, a "
                               "Suggestion (DC 17) through the sensor: a person you scry who fails the save thinks "
                               "well of you for eight hours, should you meet."}],
                             "Crystal Ball of Telepathy"),
        "of true seeing": ball([{"kind": "flag", "flag": "scry_true", "text": "Truesight 120 feet round the "
                                 "sensor: you see whoever you scry as they truly are, and all that stands near them."}],
                               "Crystal Ball of True Seeing")},
    # ------------------------------------------------------------------ the spellbook (DMG 2024 p. 257)
    "enduring_spellbook": {"": {"kind": "wondrous", "bases": ["spellbook"], "title": "Enduring Spellbook", "props": [
        {"kind": "flag", "flag": "enduring", "text": "Fire and water cannot harm it or anything written in it, and "
         "it does not age."}]}},
    # ------------------------------------------------------------------ enspelled arms (DMG 2024 p. 258)
    "enspelled_armor": {
        v: {"kind": "armor", "title": "Enspelled Armor", "attune": True, "enspell": ["abjuration", "illusion"],
            "props": [{"kind": "pool", "value": 6, "left": 6, "regain": "1d6", "worn": True, "text": "It holds 6 charges; 1d6 come "
                       "back each dawn. Worn, a charge casts its spell."}]}
        for v in SPELL_LEVELS},
    "enspelled_weapon": {
        v: {"kind": "weapon", "title": "Enspelled Weapon", "attune": True,
            "enspell": ["conjuration", "divination", "evocation", "necromancy", "transmutation"],
            "props": [{"kind": "pool", "value": 6, "left": 6, "regain": "1d6", "worn": True, "text": "It holds 6 charges; 1d6 come "
                       "back each dawn. In hand, a charge casts its spell."}]}
        for v in SPELL_LEVELS},
    # ------------------------------------------------------------------ hats (DMG 2024 pp. 266-267)
    "hat_of_many_spells": {"": {"kind": "clothing", "bases": HAT, "title": "Hat of Many Spells", "attune": True,
                                "attune_by": ["wizard"], "props": [
        {"kind": "focus", "for": "wizard", "text": "A spellcasting focus for your wizard spells, pulled out of the hat."},
        {"kind": "hat", "spells": "any", "text": "Unknown Spell: a wizard spell of a level you can cast that you do "
         "not know, for a slot of its level and an Intelligence (Arcana) check, DC 10 + its level. Cast, the hat "
         "rests until a short or long rest; a failure brings something else out of the hat."}]}},
    "hat_of_wizardry": {"": {"kind": "clothing", "bases": HAT, "title": "Hat of Wizardry", "attune": True,
                             "attune_by": ["wizard"], "props": [
        {"kind": "focus", "for": "wizard", "text": "A spellcasting focus for your wizard spells."},
        {"kind": "hat", "spells": "cantrip", "text": "Unknown Spell: once a long rest, a wizard cantrip you do not "
         "know (cast with an action), on an Intelligence (Arcana) check, DC 10; a failure wastes the action."}]}},
    # ------------------------------------------------------------------ the pearl (DMG 2024 p. 284)
    "pearl_of_power": {"": {"kind": "wondrous", "bases": ["pearl"], "title": "Pearl of Power", "attune": True,
                            "attune_by": "spellcaster", "props": [
        {"kind": "trait", "trait": "pearl_of_power", "daily": True, "text": "Once a day, the Magic action: one "
         "spent spell slot of level 3 or lower comes back."}]}},
    # ------------------------------------------------------------------ the ring (DMG 2024 p. 295)
    "ring_of_spell_storing": {"": {"kind": "jewellery", "bases": ["plain_ring"], "title": "Ring of Spell Storing",
                                   "attune": True, "props": [
        {"kind": "store", "most": 5, "fill": "1d6-1", "text": "It keeps up to 5 levels of spells cast into it (a "
         "spell of level 1 to 5, by the slot it was cast with). Worn, you cast a spell kept in it with its caster's "
         "slot, save DC and attack, and it is gone from the ring."}]}},
    # ------------------------------------------------------------------ robes (DMG 2024 pp. 297-298)
    "robe_of_eyes": {"": {"kind": "clothing", "bases": ROBE, "title": "Robe of Eyes", "attune": True, "props": [
        {"kind": "trait", "trait": "robe_of_eyes", "text": "All-Around Vision: Advantage on Wisdom (Perception) "
         "checks that rely on sight."},
        {"kind": "sense", "sense": "darkvision", "value": 120, "text": "Darkvision 120 feet."},
        {"kind": "sense", "sense": "truesight", "value": 120, "text": "Truesight 120 feet."},
        {"kind": "flag", "flag": "light_blinds", "text": "Drawback: Light cast on the robe, or Daylight within 5 "
         "feet of it, Blinds you for a minute (a Constitution save at the end of each of your turns: DC 11 for "
         "Light, 15 for Daylight)."}]}},
    "robe_of_scintillating_colors": {"": {"kind": "clothing", "bases": ROBE, "title": "Robe of Scintillating Colors",
                                          "attune": True, "props": [
        {"kind": "charges", "spell": "robe_colors", "value": 3, "left": 3, "regain": "1d3", "worn": True,
         "text": "3 charges, 1d3 back each dawn. The Magic action and a charge: dazzling hues until the end of your "
         "next turn."}]}},
    "robe_of_stars": {"": {"kind": "clothing", "bases": ROBE, "title": "Robe of Stars", "attune": True, "props": [
        {"kind": "save", "value": 1, "text": "+1 to every saving throw."},
        {"kind": "charges", "spell": "magic_missile", "value": 6, "left": 6, "regain": "1d6", "level": 5,
         "worn": True, "text": "Six great stars: the Magic action plucks one to cast Magic Missile at level 5. 1d6 "
         "of them come back each day."},
        {"kind": "trait", "trait": "robe_of_stars", "text": "The Magic action takes you into the Astral Plane with "
         "all you carry; another brings you back where you were."}]}},
    "robe_of_the_archmagi": {"": {"kind": "clothing", "bases": ROBE, "title": "Robe of the Archmagi", "attune": True,
                                  "attune_by": ["sorcerer", "warlock", "wizard"], "props": [
        {"kind": "base_ac", "value": 15, "text": "Armor: unarmoured, your Armor Class is 15 + your Dexterity "
         "modifier."},
        {"kind": "trait", "trait": "magic_resistance", "text": "Magic Resistance: Advantage on saving throws against "
         "spells and other magical effects."},
        {"kind": "spell_dc", "value": 2, "text": "War Mage: +2 to your spell save DC."},
        {"kind": "spell_attack", "value": 2, "text": "War Mage: +2 to your spell attack rolls."}]}},
    "robe_of_useful_items": {"": {"kind": "clothing", "bases": ROBE, "title": "Robe of Useful Items", "props": [
        {"kind": "patches", "extra": "4d4", "text": "Cloth patches: worn, the Magic action tears one off and it "
         "becomes the thing it shows. With the last one gone it is an ordinary robe."}]}},
    # ------------------------------------------------------------------ the ruby (DMG 2024 p. 302)
    "ruby_of_the_war_mage": {"": {"kind": "wondrous", "bases": ["gemstone"], "title": "Ruby of the War Mage",
                                  "attune": True, "attune_by": "spellcaster", "props": [
        {"kind": "war_ruby", "text": "Pressed for ten minutes against a simple or martial weapon, it makes that "
         "weapon a spellcasting focus for your spells, until you take it off with the Magic action."}]}},
}

# The Robe of Useful Items' patches (DMG 2024 p. 298): two each of six things, then 4d4 rolled on the table
# (d100 low, high, what it becomes). Those the world has no way to show (an iron door, an open pit, a window) are
# rolled again when the robe is made (game/wonders.py), and so is the rowboat (the game keeps no boats); the silver
# coffer is an art object of the nearest worth.
PATCHES = {"always": ["bullseye_lantern", "dagger", "mirror", "pole", "rope", "sack"],
           "table": [[1, 8, "gold_100"], [9, 15, "silver_coffer"], [16, 22, "iron_door"], [23, 30, "gems_10"],
                     [31, 44, "ladder"], [45, 51, "riding_horse"], [52, 59, "pit"], [60, 68, "potions_4"],
                     [69, 75, "rowboat"], [76, 83, "scroll_1_3"], [84, 90, "mastiffs_2"], [91, 96, "window"],
                     [97, 100, "portable_ram"]]}


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
    data = json.loads(out)
    if data.get("patches") != PATCHES:
        import re

        out = re.sub(r'\n  "patches": \{[^\n]*\},?', "", out)
        out = out.replace('\n  "makers": {', '\n  "patches": ' + json.dumps(PATCHES) + ',\n  "makers": {', 1)
    json.loads(out)
    path.write_text(out, encoding="utf-8", newline="\n")
    print(f"{len(MAKERS)} makers written")


if __name__ == "__main__":
    main()
