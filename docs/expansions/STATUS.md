# Expansion programme – status

Current: 01 Dice & Destiny · part C (reactions and Tactics 2.0) · branch dlc/01-dice-destiny · step 4 (build) of §5.1
On GitHub (main): World Variety · Clearing the decks (§0.4) · Dice & Destiny parts A and B (the rules kernel, the 2024
  rules, the 2025 creatures) and C.1 (reactions that ask)
Codex coverage: 2,951 entries from the three books, every one assigned to an expansion; 62 done, 20 adapted,
  16 omitted (`tools/codex/coverage.py --dlc`); Expansion 1's 242 rules entries are marked at the end of Part E
Assumptions waiting for Anton:
- The Player2 AI writer is removed (tagged `before-ai-removal`); its text is replaced everywhere by the game's own
  words, strengthened where they were thin.
- Letters mode is gone; a PC that cannot draw the pictures is told so plainly.
- Saves from before 2026-10-12 no longer load (start a new world).
- Codex judgement calls: trick weapons and similar items placed by their world (notes in magic_items.json); the eight
  creatures printed in both the PHB and the MM kept with Expansion 1; the Airship with Ships & Sea Monsters (22);
  elf lineage spells marked to work from Expansion 3.
Ideas for later:
- (none yet)
Next session starts at: Expansion 1, part C, task C.2 (elevation, flying, senses, changing sides, antimagic, the
  missing actions) in docs/expansions/01-dice-destiny.md

## Done

| When | What | Branch |
|---|---|---|
| 2026-10-12 | World Variety merged into `main` and pushed | `world-variety` |
| 2026-10-12 | §0.4 Clearing the decks: A friends' build, B the AI writer, C faster tools, D letters mode, E old saves, F leftovers | `prep/clear-the-decks` |
| 2026-10-12 | Dice & Destiny part A: content packs and provenance, the expansion shelf and screen, the codex of all three books | `dlc/01-dice-destiny` |
| 2026-10-12 | Dice & Destiny B.2 and most of B.1: the rules kernel (conditions as data, the numbers in one place, traits and hooks) | `dlc/01-dice-destiny` |
| 2026-10-12 | Dice & Destiny part B: spells and abilities as definitions (2024), the 2024 rules glossary, the 35 creatures from their 2025 stat blocks; C.1 reactions that ask | `dlc/01-dice-destiny` |

## Notes for the next session

- The three books' text is extracted to `build/codex/<phb|dmg|mm>/p###.txt` (`tools/codex/extract.py`); render page
  images with `tools/codex/extract.py --render mm 120 121` (to `build/codex/pages/`) to check numbers.
- `docs/expansions/codex/README.md` fixes the codex's shape (one entry per line, `<kind>:<slug>` ids, PDF pages).
- Edit scripts on this PC: heredocs into the Windows Python halve backslashes, and Python's text mode writes CRLF;
  write scripts to files and keep line endings (see the memory note on Windows editing).
