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
- [x] B.6 Stat blocks (2025): the 35 creatures re-made (Appendix A), with ids renamed; legendary actions and
  resistance, recharge, uses per day, 2025 spellcasting and multiattack proven on test creatures.
- [x] B.7 Balance in band; Part B to `main`.

### Part C — Reactions and Tactics 2.0
- [x] C.1 Resumable resolution and reaction prompts; the *Reactions* setting.
- [x] C.2 Elevation, flying, jumping, climbing; senses; telepathy; changing sides; antimagic; the missing actions.
  (Fliers and falling; climbing onto low things and swimming at a foot extra per foot unless one has the speed;
  long jumps over water, chasms, fires and fences, with the Athletics and Acrobatics checks; ending a turn in
  another's space leaves you Prone; blindsight and truesight; Study, Search, Ready; changing sides by team;
  antimagic; breakable objects.)
- [x] C.3 One list of possible actions (`engine.actions.options`) used by the screen, Auto and the enemy.
- [x] C.4 Tactics 2.0 over today's creatures and spells; roles and preferred range replace `rank`. The companions'
  Auto takes its class abilities from the same list and judges each by what it does (a heal, one more action, a
  move with the bonus action, a bonus blow, a power such as Turn Undead), not by name.
- [x] C.5 `tools/arena.py`, `tests/test_tactics_coverage.py`, timing budgets; Part C to `main`. Every creature
  uses every option it has in the arena's four scenarios; nothing the tactics try is refused; an enemy turn takes
  about 20 ms (95th percentile under 60 ms, the slowest about 100 ms; budget 150 and 400).

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
- (Done in Part C: `Fighter.prefers_range` reads the creature's role and range; the Auto's class abilities come from
  the one list of actions; the creatures' old attack extras are gone, every creature fighting from its 2025 block.)

## Adapted in Part C (the battle mat is flat squares with heights for fliers)

- Climbing is onto and over low things (fences, tables, barrels, low walls); walls and cliffs have no ledge to stand
  on in a fight, so they stay walls. A slippery surface's DC 15 is not asked.
- The high jump is not used: it would only reach a flier, and reach already counts a flier's height.
- Telepathy is kept on every stat block; no creature of this expansion has it, and Influence in a fight does not ask
  for a shared language yet.
- A river is rough water (Athletics DC 15 to make headway); someone who drops senseless in deep water does not
  drown in the fight's minute.
- A long jump is the whole way moved (clearing one square is a 10-foot leap). Squeezing through a narrow space is
  not in yet, so a Large creature cannot pass a one-square doorway.
- Study's DC is 10 + half the Challenge Rating, at most 25 (data/rules.json "study"); the book leaves it to the DM.
- The enemy's estimate of a shot counts the cover of walls and things, not of creatures in the way (the battle
  screen's hit chance counts both): looking at creatures for every square it weighs would cost too much time.

## The fresh review of Part C (2026-10-12) and what was done about it

It found fliers, falling and breakable things built as rules that nothing in play used; the one list of actions
used by the enemy only for spells; roles that changed little; height left out of some distances; a long jump one
square too generous; a taken-over creature that could stay with the enemy; Influence offered to the enemy; antimagic
missing from the lists. All fixed and tested (tests/test_tactics_choices.py). The lesson is in CLAUDE.md, "How to
work": a rule is done only when it is usable in play.

## Codex entries delivered

Everything with `"dlc": 1` in `docs/expansions/codex/` (the rules glossary, the DMG systems of Appendix E row 1, the
35 re-made creatures, the 41 spells in 2024 form, and the stat block rules).
