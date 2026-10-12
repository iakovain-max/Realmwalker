# Expansion 1 — Dice & Destiny (XL, five parts)

*Icon*: a twenty-sided die showing a small star, under a thin arc of light. *Tagline*: "The rules of the realm, made
whole." Branch `dlc/01-dice-destiny`; each part goes to `main` when it meets §5.2 of `docs/EXPANSIONS.md`.

## What Anton will see

Fights, checks and conditions follow the 2024 Player's Handbook; the creatures already in the game are re-made from
the 2025 Monster Manual; enemies think harder; reactions ask first; loot follows the Dungeon Master's Guide; small
icons show every state, and pointing at anything in a fight tells what it is and what it can do; borrowed monster
pictures are reworked to match the game's own art; the main menu gets its shelf of expansions, with this one first.

## Decisions

- **Packs** live in `data/packs/NN_id/`; the registry merges each pack's fragment files over the base files by key
  (dicts merge, a key defined twice is an error unless the later one says `"_replace": true`); provenance is kept
  per (file, top-level section, key). New kinds of file (conditions.json...) are registered in `schemas.DATA_FILES`.
- **The codex** (`docs/expansions/codex/`, shape in its README) is built for all three books at the start, from the
  books' own lists, with every entry assigned to an expansion by §6 and Appendices A, B and E of the plan. It is the
  checklist: an expansion is not released while one of its entries is `todo`.
- **The kernel** is built beside the old combat code and takes it over piece by piece (§4.3.9); `battle.events` keep
  their meaning (pictures and sounds read them). Balance must not drift: `tools/balance.py` before and after.
- **2024 rules**: conditions, exhaustion (−2 per level to d20 tests, −5 ft speed per level, death at 6), surprise
  (disadvantage on initiative), grapple and shove (saving throws), the Study/Influence/Search/Utilize/Magic actions,
  Heroic Inspiration, Bloodied. The game's own wounds, survival and death stay on top (adapted in the codex).

## Parts and tasks

### Part A — Foundations
- [x] A.1 Content packs: `data/packs/`, registry merge + `_replace`, provenance (`registry.origin`), schemas for
  `pack.json`; tests (merge, duplicate key error, `_replace`, provenance, pack record validity, unique ids/orders).
- [x] A.2 `realmwalker/expansions.py`: released expansions in order, names, taglines, icons, accents, adds, live counts.
- [x] A.3 The shelf on the title screen (icons on the right, tooltips, glint until seen, kept in Settings) and the
  Expansions screen (E); autoplay and smoke tour visit them; tests at three window sizes.
- [x] A.4 The codex for all three books (classes, species, backgrounds, feats, equipment, spells, rules, monsters,
  magic items, world), every entry assigned to an expansion; `tools/codex/coverage.py`; `tests/test_codex.py`.
- [x] A.5 Part A to `main`.

### Part B — The kernel
- [x] B.1 `rules/engine/`: events, effects (ops), query (derived numbers), conditions (data), durations, resources.
- [x] B.2 Conditions and the query numbers routed through the kernel; old and new compared in tests.
- [x] B.3 The 41 spells as definitions (2024 versions); the old reader retired.
- [x] B.4 Class features, monster traits and item properties on the kernel; old branches in `combat.py` deleted.
- [x] B.5 2024 rules glossary: d20 tests, actions, unarmed strikes, surprise, Heroic Inspiration, concentration,
  temporary hit points, damage order, falling, suffocation, burning, areas incl. Emanation, cover, obscurement,
  objects; exhaustion and hunger/thirst in 2024 form on the body system; "careful player" measured again.
- [ ] B.6 Stat blocks (2025): the 35 creatures re-made (Appendix A), with ids renamed; legendary actions and
  resistance, recharge, uses per day, 2025 spellcasting and multiattack proven on test creatures.
- [ ] B.7 Balance in band; Part B to `main`.

### Part C — Reactions and Tactics 2.0
- [ ] C.1 Resumable resolution and reaction prompts; the *Reactions* setting.
- [ ] C.2 Elevation, flying, jumping, climbing; senses; telepathy; changing sides; antimagic; the missing actions.
- [ ] C.3 One list of possible actions (`engine.actions.options`) used by the screen, Auto and the enemy.
- [ ] C.4 Tactics 2.0 over today's creatures and spells; roles and preferred range replace `rank`.
- [ ] C.5 `tools/arena.py`, `tests/test_tactics_coverage.py`, timing budgets; Part C to `main`.

### Part D — Treasure and encounters
- [ ] D.1 Magic item framework (attunement, charges, activation, curses, identification, artifacts, sentient items).
- [ ] D.2 DMG treasure: individual and hoards by CR, the four themes and rarity tables, monster treasure themes.
- [ ] D.3 Encounter builder and the DMG XP budget; travel pace; starting attitudes and Influence.
- [ ] D.4 Part D to `main`.

### Part E — Tooltips, icons and pictures
- [ ] E.1 Cards (`rules/describe.py`) and `ui/tooltips.py`; status icons; creature cards; the battle log's rolls.
- [ ] E.2 The picture adaptation pass for borrowed monster tiles (before/after contact sheet).
- [ ] E.3 Spell effect styles (`fx`); fliers drawn with their height.
- [ ] E.4 The icon on the shelf; release v1.1.0 (pack status, notes, tag, `PROGRESS.md`, `STATUS.md`).

## Left in the battle code on purpose (B.4)

- The four 2014 fighting styles a fighter picks today (archery, defence, duelling, great weapon, protection, two
  weapons) stay as small checks in `combat.py` and the sheet: they become the 2024 Fighting Style feats in Expansion 2
  (Blades & Backgrounds), where feats arrive.
- `Fighter.prefers_range` (wizards and creatures marked "back" keep their distance) and the Auto's use of Second Wind,
  Action Surge and Cunning Action in `tactics.py`: Tactics 2.0 (Part C) plans from the one list of actions instead.
- The creatures' old attack extras (trip, paralysis, poison) stay readable until every creature fights with its 2025
  stat block (B.6); then they go.

## Codex entries delivered

Everything with `"dlc": 1` in `docs/expansions/codex/` (the rules glossary, the DMG systems of Appendix E row 1, the
35 re-made creatures, the 41 spells in 2024 form, and the stat block rules).
