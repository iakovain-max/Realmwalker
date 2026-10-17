# Expansion 3 — Demigods & Magics (XL, seven parts)

*Icon*: a crowned silhouette rising out of an open book that spills light. *Tagline*: "Twenty levels of power. Every
spell under the sky." Anton's name. Branch `dlc/03-demigods-magics`; each part goes to `main` when it meets §5.2 of
`docs/EXPANSIONS.md`; the icon and version 1.3.0 come with Part G. Books: PHB 44–46 (levels, tiers), 71–80 (cleric),
93–102 (fighter), 131–140 (rogue), 167–178 (wizard), 213–214 (epic boons), 231 and 235 (potion, scrolls,
spellcasting services), 238–346 (spellcasting and every spell), 349–378 (Appendix B stat blocks); DMG 53 (training
to gain levels). Codex: 558 entries (`coverage.py --dlc`): 351 spells, 4 classes, 7 subclasses, 88 features, 17
option lists and options, 12 epic boons, 36 stat blocks, 31 rules, 12 gear, services and items.

## What Anton will see

Characters and companions climb past level 10 to 20, through the book's four tiers. At 19 an epic boon (Combat
Prowess, Fate, Truesight, the Night Spirit...) is chosen in place of a feat. The world has room for them: the most
dangerous regions, the deepest dungeon levels and the named beasts' lairs build their bands for high-level parties.
Fighters, rogues, clerics and wizards are the 2024 book's from level 1 to 20, with every feature: the fighter's
Second Wind and Tactical Mind, three and four attacks; the rogue's Cunning Strike (poison, trip, withdraw, daze,
knock out, obscure); the cleric's Divine Order and Blessed Strikes; the wizard's Scholar and Spell Mastery. The
Cutthroat becomes the Assassin; the Knight stays, extended to level 18. Every spell in the Player's Handbook is in
the game — for the party, companions, enemies, scrolls and wands — and many work outside a fight: Goodberry feeds,
Tiny Hut makes a safe night, Revivify brings back the fallen, Teleport crosses the map, Augury answers from the
world's real history. Familiars, a summoned steed and the summoned spirits fight beside you. Temples and mages sell
spellcasting and scrolls at the book's prices.

## Decisions

- **Levels 11–20** (Part A): the PHB XP and proficiency tables to 20 (data/rules.json); hit points as now; the class
  tables (slots, cantrips, prepared spells) to 20 in data/classes.json. A level's features come from the class data;
  until Part B lands, levels 11–20 give hit points, proficiency, slots and the ability increases (12, 16) and the
  boon (19) every 2024 class has; the class features above 10 come with B.
- **Epic boons are feats** (data/feats.json, category `epic_boon`, prerequisite level 19, kernel trait each), chosen
  through the same "asi" choice at 19; Suggest and the Auto pick by archetype. A boon whose world arrives later
  (Dimensional Travel's teleport works in battle now) is `adapted` with its note.
- **Danger tiers**: region danger 0–10 maps to party levels up to 20 (`encounters.danger_level`); dungeon depth grows
  with danger to five levels for the worst sites; named beasts and barrow kings scale their stat blocks to the
  party's tier where the lived history made them. Low regions stay low: a level 15 party can still walk through
  farmland in peace.
- **The 2024 classes** replace the old ones in data/classes.json; subclass ids become the book's (`champion`,
  `thief`, `assassin`, `life_domain`, `war_domain`, `evoker`, `abjurer`); the Knight is ours (`original` in the
  codex), given features at 3, 7, 10, 15 and 18 in its own spirit. Saves break (FORMAT_VERSION bump in Part B: a new
  character and a new world are needed).
- **Spellcasting by the 2024 rules** (Part C): every caster prepares spells (the class table's count); wizards
  prepare from the spellbook and copy into it (as `game/magic.py` does now); rituals cast without a slot outside a
  fight and at ten minutes' cost; components: a focus or a pouch stands in for free materials, costly ones are items
  bought and spent (consumed ones go); upcasting by each spell's `higher` op; one slotted spell per turn; casting in
  armour you are not trained in is refused (already); scrolls of every level, with the Arcana check above your level.
- **The catalogue** (Part D) comes in four waves by spell level, built by helper agents in fragment files
  (`data/packs/03_demigods_magics/spells.*.json`) over the kernel's ops; a spell that needs an op the kernel lacks
  gets the op (main session) first. Spells of classes not yet in the game are castable from scrolls, wands, feats
  and by enemies. The existing 49 spells are re-checked against the 2024 text.
- **Outside battle** (Part E): Appendix C's groups plug into the existing systems; a spell whose system arrives
  later (ships, planes, bastions) works in battle and in a simpler way now, `adapted` with `upgrade_in`.
- **Appendix B stat blocks** (Part F): the 36 creatures printed there join data/creatures.json from their PHB/MM
  2025 blocks; beasts carry `upgrade_in` 11 (placed in the world by Druids & Beasts); the imp, quasit,
  pseudodragon, sprite, sphinx of wonder and slaad tadpole come as familiars and summons now.
- **Enemy casters** (Part G): every caster stat block names its spells from the catalogue; the tactics weigh them
  by `estimates` (no spell is chosen by name). Temples and mages' guilds sell spellcasting (PHB p. 235) and scrolls
  by rarity; the local law of magic (`game/law.py`) applies to casting in towns.

## Parts and tasks

### Part A — Twenty levels
- [x] A.1 XP, proficiency and the class tables to 20 (rules.json, classes.json slots/cantrips to 20); `max_level`
  20; level-up screens and the character sheet fit levels 11–20; companions level with the party.
- [x] A.2 Epic boons (12) as feats with kernel traits and handlers; the 19th-level choice; Suggest and Auto picks;
  one test each in a real fight or check.
- [x] A.3 Danger tiers: `danger_level` to 20; deeper dungeons for the worst sites; lairs and named beasts scaled;
  `tools/balance.py` measures a level 11 and a level 17 fight; the bands set.
- [x] A.4 Codex: rules level_advancement, gaining_a_level, tiers_of_play, dmg_variant_training_to_gain_levels; the
  12 boons; Part A to `main`.

### Part B — The four classes, 1–20
- [x] B.1 Fighter and Champion 2024; the Knight to 18 (original).
- [x] B.2 Rogue, Thief and the Assassin (the Cutthroat's characters become assassins); Cunning Strike and its effects
  as options in `actions.options`, in the Auto's and enemy's hands.
- [x] B.3 Cleric (Divine Order, Channel Divinity effects, Blessed Strikes, Divine Intervention), Life and War
  Domains.
- [x] B.4 Wizard (Ritual Adept, Scholar, Memorize Spell, Spell Mastery, Signature Spells), Evoker and Abjurer;
  FORMAT_VERSION bump; companion archetypes to 20; Part B to `main`.

### Part C — Spellcasting complete
- [x] C.1 Preparing spells (counts by table; the Spells screen prepares; Auto prepares by archetype); always-prepared
  spells; rituals; one slotted spell per turn; the wizard's Memorize Spell (one prepared spell swapped after a short
  rest) and Ritual Adept (rituals from the book, prepared or not).
- [x] C.2 Components: focus and pouch, costly components as items (shops), consumed ones spent; upcasting for every
  spell with a `higher` op; the spell's card shows the level chosen.
- [x] C.3 Spell scrolls 2024 (any level; Arcana check above your level; copying into a spellbook); potions of
  healing; the 31 spellcasting rules in the codex; Part C to `main`.

### Part D — The spell catalogue (four waves, helpers on the sonnet model)
- [ ] D.1 Cantrips to 2nd level (134 spells): new ops first, then batches; fx for each; arena coverage green.
- [ ] D.2 3rd to 5th level (128; Counterspell is in already, B.4). Dispel Magic with the Abjurer's Spell Breaker: a
  bonus action for them, their proficiency added to its check, the slot kept when it ends nothing.
- [ ] D.3 6th and 7th level (55).
- [ ] D.4 8th and 9th level (34), Wish (its safe uses and its stress) and Meteor Swarm; Part D to `main`.

### Part E — Spells outside battle
- [ ] E.1 Healing, return from death, food and the body, shelter and watch.
- [ ] E.2 Travel, finding and seeing, asking the powers (answered from the world's history), talking.
- [ ] E.3 Moving minds and the law, disguise, locks and stone, weather and land, lasting protections, great magic;
  Part E to `main`.

### Part F — Appendix B: familiars, steeds and summons
- [ ] F.1 The 36 stat blocks (beasts, imp, quasit, pseudodragon, sprite, sphinx of wonder, slaad tadpole) with
  pictures; Find Familiar, Find Steed, the Summon spells' spirits, Animate Dead; followers outside battle; Part F
  to `main`.

### Part G — Enemy casters, services, release
- [ ] G.1 Every caster stat block on the catalogue; arena: every battle spell cast by the AI in a scenario; a test
  caster of each spell level 1–9 casts without hangs.
- [ ] G.2 Spellcasting services and scrolls in temples, mages' guilds and shops; the law of magic.
- [ ] G.3 Every Expansion 3 codex entry settled; balance; the icon; release v1.3.0.
