# Expansion programme – status

Current: 03 Demigods & Magics · Part C (spellcasting complete) · branch dlc/03-demigods-magics
On GitHub (main): World Variety · Clearing the decks (§0.4) · 01 Dice & Destiny (v1.1.0, 2026-10-13: the rules kernel,
  the 2024 rules, the 2025 creatures, reactions that ask, Tactics 2.0, magic items and treasure, encounters by the
  budget, cards and status icons, adapted monster pictures, spell looks, the shelf) · 02 Blades & Backgrounds
  (v1.2.0, 2026-10-13: the 2024 weapons, armour and masteries; species, sixteen backgrounds and origin feats; the
  general and fighting style feats; the 2024 tools and gear, trinkets, inns and lifestyles, coaches, ships and
  messengers, mounts, saddles, stabling and vehicles; saves format 16) · 03 Demigods & Magics parts A and B (twenty
  levels and the epic boons; the fighter, rogue, cleric and wizard of 2024 to level 20 with the Champion, Knight,
  Thief, Assassin, Life and War Domains, Evoker and Abjurer; Counterspell; saves format 17)
Codex coverage: 2,951 entries from the three books, every one assigned to an expansion; Expansion 1: all 327 settled
  (237 done, 65 adapted, 25 omitted; `tools/codex/coverage.py --dlc`); Expansion 2: all 384 settled (310 done, 74
  adapted); Expansion 3: 98 done, 34 adapted, 1 omitted of 558 (parts A and B settled). PHB 41% · DMG 12% · MM 8%
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
- Expansion 2 part C: Mounted Combatant is written but not offered until mounted combat (Expansion 9); a duellist
  keeps a versatile blade in one hand; Spell Sniper's reach is for attack-roll spells only; Sentinel answers a hit
  on anyone but the sentinel.
- Expansion 2 part D: coaches run up to 160 miles at 4 mph for 10 hours a day; ships 2 mph day and night up to 600
  miles; a messenger rides 30 miles a day there and back; hired companions keep their own wages (below the book's
  2 gp a day, as they share the loot); the inn charges each of the party; a mirror and perfume please the gentry a
  little (+2, +3); a carried basket, pouch, quiver or chest adds to what you can carry; a thrown net is shaken off
  with a Strength save at the end of each turn (the book: an action and a DC 10 Strength check), and catches a Huge
  thing too; barding and the horses' stat blocks wait for mounted combat (Expansion 9: there is nothing for a mount
  to be armoured against before then), and so does Mounted Combatant (written, not offered; the plan's §6.2 wanted a
  basic form now); the cart's load counts the fastest animals as ridden (a mastiff may be counted wrongly).
- Expansion 3 part A: Blink Steps picks the place itself; Energy Redirection turns on whoever struck, else the
  weakest foe in range; Improve Fate works on saves and a friend's near miss, not on ability checks; Recover Vitality
  spends the dice the hurt needs; training to gain levels is omitted; danger 8-10 stand for levels 6, 11 and 20 (0-7
  unchanged) and bands grow to hosts where the budget is for heroes; named beasts grow with the party's tier (hit
  points x2.5/4 from level 11). High-tier fights are easy until the bestiary expansions bring creatures for them.
- Expansion 3 B.1: Tactical Shift and Remarkable Athlete's step add half the speed to the turn and the turn's steps
  draw no opportunity attacks; the Knight (ours) gains Unyielding at 15 (once a day, standing at hit points equal to
  the level) and Warden of the Line at 18 (Hold the Line reaches ten feet); Commanding Presence stays words only.
- Expansion 3 B.2: a dazed creature keeps its action and loses its move and bonus action; Withdraw adds half the
  speed to the turn; Thief's Reflexes folds the second turn into the first (a second action, bonus action and move);
  Stroke of Luck works on attack rolls and saves; Use Magic Device's scrolls wait for Part C; the player is asked
  which Cunning Strike to use only under the Reactions setting "all" (otherwise the battle's judgement).
- Expansion 3 B.3: the domains keep their ids `life` and `war` (the design note said `life_domain`, `war_domain`:
  only a name, and other code knows them); Divine Order is chosen at level 1 on the sheet (c, then l), the Auto takes
  Protector for a fighting priest and Thaumaturge for a praying one, and Blessed Strikes the same way; Divine
  Intervention's spell is the battle's judgement; War God's Blessing's spell still asks for concentration; Divine
  Strike is radiant; the domain spells come with Part C.
- Expansion 3 B.4: the wizard's schools keep their ids `evocation` and `abjuration` (shown as the Evoker and the
  Abjurer), as the cleric kept `life` and `war`; Counterspell came early (Part D's catalogue skips it) so that Spell
  Breaker works now, Dispel Magic waits for D.2; the Auto and the enemy counter any spell of level 1 or more, never a
  cantrip; Memorize Spell waits for preparing (C.1), every spellbook spell is ready until then; Spell Mastery's spells
  are chosen at 18 and kept (changing them after a long rest is left out); Overchannel is the battle's judgement when
  it is free and asked of the player under the Reactions setting; Arcane Recovery brings back the highest slots
  first; the ward is mended with a level 1 slot, or a level 2 one when it is far gone; Spell Resistance halves the
  damage of a spell as it is cast (burning ground or an aura left by a spell later is not counted).
  No creature knows Counterspell yet: enemies use it when their stat blocks name it (Part G puts the catalogue in
  the casters' hands). From the fresh review: the 2024 Assassinate has no critical hit on the surprised (the 2014
  rule is gone).
- Expansion 3 C.1: the prepared list may change from a long rest (or a new level) until the next fight begins, one
  spell after a short rest (Memorize Spell); an empty place may be filled at any time; a new level fills new places
  with the Auto's choice (the player changes them on the Spells page); domain spells not yet in the catalogue are
  listed in data/classes.json and prepared as they arrive (Part D).
Ideas for later:
- (none yet)
Next session starts at: task C.2 in docs/expansions/03-demigods-magics.md (Part C: components - a focus or a pouch
for free materials, costly components as items sold in shops and spent when consumed; upcasting for every spell with
a `higher` op; the spell's card shows the level chosen). C.1 (preparing) is on the branch; Part C goes to `main` with
C.3.

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
| 2026-10-13 | Blades & Backgrounds part D: the 2024 tools and gear, trinkets, shops by size and people, inns by grade, lifestyles, tolls, coaches, ships, messengers, mounts, saddles, stabling, vehicles; **released as 1.2.0** and merged into `main` | `dlc/02-blades-backgrounds` |
| 2026-10-13 | Blades & Backgrounds part C: feats (the framework, Suggest, the Feats tab; 42 general and 10 fighting style feats in play, on Auto and in the enemy's hands); finished by a second session after a usage limit; merged into `main` | `dlc/02-blades-backgrounds` |
| 2026-10-13 | Demigods & Magics begun: the branch, the design note and its seven parts (twenty levels, the four classes, spellcasting, the catalogue, spells outside battle, familiars and summons, enemy casters) | `dlc/03-demigods-magics` |
| 2026-10-13 | Demigods & Magics part A: twenty levels, the twelve epic boons (in play, on Auto), danger tiers for the worst lands, legends that grow, five-level dungeons; finished after a usage limit; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics part B: the 2024 fighter, rogue, cleric and wizard to 20 (Champion, Knight, Thief, Assassin, Life, War, Evoker, Abjurer), Counterspell, companions to 20; saves format 17; the first part built by the relay; merged into `main` | `dlc/03-demigods-magics` |

## Notes for the next session

- A window smoke test hung in part B still holds `build/smoke_home` open on this PC; part C's smoke test used
  `build/smoke_home_c`. Use a fresh folder if the old one cannot be removed.
- The three books' text is extracted to `build/codex/<phb|dmg|mm>/p###.txt` (`tools/codex/extract.py`); render page
  images with `tools/codex/extract.py --render mm 120 121` (to `build/codex/pages/`) to check numbers.
- `docs/expansions/codex/README.md` fixes the codex's shape (one entry per line, `<kind>:<slug>` ids, PDF pages).
- Edit scripts on this PC: heredocs into the Windows Python halve backslashes, and Python's text mode writes CRLF;
  write scripts to files and keep line endings (see the memory note on Windows editing).
- `tools/arena.py` (every creature, four scenarios) shows what the tactics use and how long a turn takes; after
  adding creatures or spells, run it and keep `tests/test_tactics_coverage.py` green (every option chosen, nothing
  refused, the time budget; a reasoned exception goes in its NOT_CHOSEN).
