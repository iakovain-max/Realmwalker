# Expansion programme – status

Current: 02 Blades & Backgrounds · part C (feats) · branch dlc/02-blades-backgrounds · step 4 of §5.1
On GitHub (main): World Variety · Clearing the decks (§0.4) · 01 Dice & Destiny (v1.1.0, 2026-10-13: the rules kernel,
  the 2024 rules, the 2025 creatures, reactions that ask, Tactics 2.0, magic items and treasure, encounters by the
  budget, cards and status icons, adapted monster pictures, spell looks, the shelf) · 02 part A (arms and
  armour: the 2024 weapons and armour, the eight weapon masteries, the Armaments basics) · 02 part B (origins:
  species, the sixteen backgrounds, origin feats, creation in the 2024 order; saves format 15)
Codex coverage: 2,951 entries from the three books, every one assigned to an expansion; Expansion 1: all 327 settled
  (237 done, 65 adapted, 25 omitted; `tools/codex/coverage.py --dlc`)
Assumptions waiting for Anton:
- The Player2 AI writer is removed (tagged `before-ai-removal`); its text is replaced everywhere by the game's own
  words, strengthened where they were thin.
- Letters mode is gone; a PC that cannot draw the pictures is told so plainly.
- Saves from before 2026-10-12 no longer load (start a new world).
- Codex judgement calls: trick weapons and similar items placed by their world (notes in magic_items.json); the eight
  creatures printed in both the PHB and the MM kept with Expansion 1; the Airship with Ships & Sea Monsters (22);
  elf lineage spells marked to work from Expansion 3.
- Part D: money follows the DMG (more of it than before); the DMG hoard row CR 11-16 uses its printed average
  (x 1,000); quest coin stays the giver's, great works add a magic gift; bands keep the old thinning for a lone
  traveller (Fair Chances); in mountains and marsh the travel pace only forbids Fast.
- Part E: the chance on an attack or spell card while choosing is against the nearest foe; a party member's
  melee blow that would kill a beaten humanoid asks to knock them out (the Auto and the enemy kill, as before);
  rituals cast outside a fight spend no slot; small beasts' heights on their squares were chosen by eye.
- Expansion 2 part A: the lance is always two-handed until mounted combat (Expansion 9); magic ammunition is spent
  once loosed, hit or miss; only a bow or crossbow is swung as an improvised weapon (throwing a blade without the
  Thrown property is left out); the silvered weapon's extra die waits for shapechangers; push and topple are the
  battle's judgement (asked only under the Reactions setting "all"); a Nick weapon in either hand frees the off-hand
  blow; the watch's guards and deserters, as trained soldiers, use the spear's Sap; firearms are rare gnomish work
  (the 2025 bandit captain's pistol stays in its stat block).
- Expansion 2 part B: gear the game lacks is paid in coin until part D; lineage spells work as they arrive
  (Expansion 3); Magic Initiate's spells are cast in a fight only; Lucky is for one's own rolls; no Initiative Swap;
  the realm's tongues are standard languages; two wolves at level 1: 85% won, 15% down (band widened).
- A window smoke test from part B's first run hung (the creation tour lacked a step; fixed) and its process may
  still be open on this PC (main.py --smoke-test ... --home build/smoke_home): it can be closed from Task Manager.
Ideas for later:
- (none yet)
Next session starts at: Expansion 2 Part C, task C.1 in docs/expansions/02-blades-backgrounds.md (branch
  `dlc/02-blades-backgrounds`; parts A and B are merged into main; rules/feats.py and data/feats.json hold the
  origin feats already)

## Done

| When | What | Branch |
|---|---|---|
| 2026-10-12 | World Variety merged into `main` and pushed | `world-variety` |
| 2026-10-12 | §0.4 Clearing the decks: A friends' build, B the AI writer, C faster tools, D letters mode, E old saves, F leftovers | `prep/clear-the-decks` |
| 2026-10-12 | Dice & Destiny part A: content packs and provenance, the expansion shelf and screen, the codex of all three books | `dlc/01-dice-destiny` |
| 2026-10-12 | Dice & Destiny B.2 and most of B.1: the rules kernel (conditions as data, the numbers in one place, traits and hooks) | `dlc/01-dice-destiny` |
| 2026-10-12 | Dice & Destiny part B: spells and abilities as definitions (2024), the 2024 rules glossary, the 35 creatures from their 2025 stat blocks; C.1 reactions that ask | `dlc/01-dice-destiny` |
| 2026-10-12 | Dice & Destiny part C: changing sides, senses, Study/Search/Ready, fliers and falling, antimagic, breakable things, climbing, swimming and leaping; one list of actions; Tactics 2.0; the arena and its proof | `dlc/01-dice-destiny` |
| 2026-10-12 | Dice & Destiny part D: magic item framework (attunement, charges at dawn, identifying, artifacts, sentient items), DMG treasure and hoards, encounters by the XP budget, travel pace, attitudes | `dlc/01-dice-destiny` |
| 2026-10-13 | Dice & Destiny part E: cards and tooltips, 47 status icons, the battle log's rolls, Creature details; the adaptation pass for borrowed monster tiles; spell looks; the last glossary rules; the codex settled; the shelf icon; **released as 1.1.0** and merged into `main` | `dlc/01-dice-destiny` |
| 2026-10-13 | Blades & Backgrounds begun: the branch, the design note and its four parts (arms and armour, origins, feats, gear and mounts) | `dlc/02-blades-backgrounds` |
| 2026-10-13 | Blades & Backgrounds part A: the 2024 weapons and armour, the eight weapon masteries (rules, picks, tactics, pictures), armour training, the Armaments basics; merged into `main` | `dlc/02-blades-backgrounds` |
| 2026-10-13 | Blades & Backgrounds part B: species (orcs for half-orcs), sixteen backgrounds, origin feats, languages, creation in the 2024 order with array and rolling; merged into `main` | `dlc/02-blades-backgrounds` |

## Notes for the next session

- Part C cut off by a usage limit at 13:19 (2026-10-13) just before merging: all of C.1-C.3 is built and committed; autoplay OK, smoke OK, the full suite was green apart from four arena-coverage failures that are fixed in 016e10e (rerun the full suite). Still to do: the fresh review (§5.2), then PROGRESS/STATUS/CLAUDE.md (a drafted script was in the old session's scratchpad: write the entry anew), merge into main and push.
- The three books' text is extracted to `build/codex/<phb|dmg|mm>/p###.txt` (`tools/codex/extract.py`); render page
  images with `tools/codex/extract.py --render mm 120 121` (to `build/codex/pages/`) to check numbers.
- `docs/expansions/codex/README.md` fixes the codex's shape (one entry per line, `<kind>:<slug>` ids, PDF pages).
- Edit scripts on this PC: heredocs into the Windows Python halve backslashes, and Python's text mode writes CRLF;
  write scripts to files and keep line endings (see the memory note on Windows editing).
- `tools/arena.py` (every creature, four scenarios) shows what the tactics use and how long a turn takes; after
  adding creatures or spells, run it and keep `tests/test_tactics_coverage.py` green (every option chosen, nothing
  refused, the time budget; a reasoned exception goes in its NOT_CHOSEN).
