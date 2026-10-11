# The codex: the three books as a checklist

Machine-readable lists of everything in Anton's three D&D books (*Player's Handbook* 2024, *Dungeon Master's Guide*
2024, *Monster Manual* 2025) that the expansion programme brings into Realmwalker (`docs/EXPANSIONS.md` §4.2).
**Names, page numbers and a few classifying numbers only — never book prose.** Text extracted from the PDFs lives in
`build/codex/` (git-ignored) and never enters a committed file.

`tests/test_codex.py` checks these files; `tools/codex/coverage.py` prints coverage by book and category.

## Files

| File | One entry per |
|---|---|
| `classes.json` | class; subclass; every class and subclass feature by level; every option list and option (maneuvers, invocations, metamagic, Brutal Strike effects, Hunter's options...) |
| `species.json` | species; lineage, legacy or ancestry; trait |
| `backgrounds.json` | background |
| `feats.json` | feat |
| `equipment.json` | weapon; mastery property; armour; adventuring gear; tool; mount; vehicle; service; trinket table |
| `spells.json` | spell |
| `rules.json` | Rules Glossary entry; each PHB rules section; each DMG Toolbox system |
| `monsters.json` | stat block (MM and PHB Appendix B; a creature printed in both is one entry with both sources) |
| `magic_items.json` | magic item; artifact; the rules for sentient and cursed items |
| `world.json` | bastion facilities, orders and events; planes and planar effects; settlement traits and calamities; supernatural gifts |

A file may be split into fragments (`monsters.fiends.json`); the test reads every `<name>*.json`.

## Shape

Each file is a JSON object with a `_comment` and an `entries` list, **one entry per line**:

```json
{
  "_comment": "Spells of the Player's Handbook (2024), PDF pages 242-346.",
  "entries": [
    {"id": "spell:acid_splash", "name": "Acid Splash", "book": "phb", "page": 242, "level": 0, "school": "evocation", "classes": ["sorcerer", "wizard"], "dlc": 3, "status": "todo", "game": [], "note": ""},
    {"id": "spell:fireball", "name": "Fireball", "book": "phb", "page": 274, "level": 3, "school": "evocation", "classes": ["sorcerer", "wizard"], "dlc": 1, "status": "todo", "game": ["fireball"], "note": "", "upgrade_in": 3}
  ]
}
```

Fields every entry has:

- `id` — `<kind>:<slug>`, unique across the whole codex (`spell:fireball`, `monster:young_red_dragon`,
  `item:bag_of_holding`, `class:wizard`, `feature:wizard/arcane_recovery`, `option:invocation/agonizing_blast`).
  The slug is the name in lower case with spaces and punctuation turned into `_`.
- `name` — the name as printed, with the OCR's mistakes corrected (checked on the page image).
- `book` — `phb`, `dmg` or `mm`; `page` — the **PDF** page where the entry begins (printed page + 3 in the PHB and
  MM, + 4 in the DMG). A creature printed in both the MM and the PHB adds `"also": [{"book": "phb", "page": 352}]`.
- `dlc` — the number of the expansion that delivers it (1–26, `docs/EXPANSIONS.md` §6 and Appendices A, B and E).
- `status` — `todo`, `done`, `adapted` or `omitted`.
- `game` — the ids in the game's data that implement it (empty while `todo`).
- `note` — required for `adapted` (what changed and why) and `omitted` (a §1.3 reason).
- `upgrade_in` (optional) — a later expansion that completes an entry delivered in a simpler form.

Fields by kind (add only these):

| File | Extra fields |
|---|---|
| spells | `level` (0 = cantrip), `school`, `classes` (lower-case class ids), `ritual` (true when it can be a ritual), `concentration` (true when its duration says Concentration) |
| monsters | `type` (Beast, Fiend...), `size` (Tiny...Gargantuan; "Medium or Small" as printed), `cr` ("0", "1/8", "1/4", "1/2", "1"...), `habitat` (list as printed: Arctic, Coastal, Desert, Forest, Grassland, Hill, Mountain, Planar, Swamp, Underdark, Underwater, Urban, Any), `treasure` (list: Arcana, Armaments, Implements, Individual, Relics, Any, None), `group` (the MM family it is printed with, e.g. "Devils", "Dragons, Red"; "" if none) |
| magic_items | `kind` (`item`, `artifact`, `rule`), `category` (Armor, Potion, Ring, Rod, Scroll, Staff, Wand, Weapon, Wondrous Item), `rarity` (common, uncommon, rare, very rare, legendary, artifact, varies), `attunement` (false, true, or the requirement as a short string: "by a wizard"), `theme` (Arcana, Armaments, Implements, Relics, or "" if on no random table) |
| classes | `kind` (`class`, `subclass`, `feature`, `option_list`, `option`), `class`, `subclass` ("" for class features), `level` (the level it is gained; 0 for option lists and options) |
| species | `kind` (`species`, `lineage`, `trait`), `species` |
| backgrounds | `abilities` (the three ability names), `feat` (the origin feat's name) |
| feats | `category` (`origin`, `general`, `fighting_style`, `epic_boon`), `prerequisite` (short text as printed, "" if none) |
| equipment | `kind` (`weapon`, `mastery`, `armor`, `gear`, `tool`, `mount`, `vehicle`, `service`, `trinket_table`), `category` (Simple Melee, Martial Ranged, Light Armor, Artisan's Tools...) |
| rules | `kind` (`glossary`, `section`, `toolbox`) |
| world | `kind` (`facility`, `order`, `event`, `plane`, `planar_effect`, `settlement_trait`, `calamity`, `gift`) |

## How an expansion uses it

An expansion is not finished while any entry with its `dlc` is still `todo` (§4.2). When it delivers an entry it sets
`status` and `game`; an `adapted` entry says in `note` what Realmwalker changed (for instance, the book's long rest
on top of the game's own wounds and hunger).
