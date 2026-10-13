# Expansion 2 — Blades & Backgrounds (L, four parts)

*Icon*: a sword laid across a rolled scroll tied with a cord. *Tagline*: "Where you come from. What you carry."
Branch `dlc/02-blades-backgrounds`; each part goes to `main` when it meets §5.2 of `docs/EXPANSIONS.md`; the icon and
version 1.2.0 come with Part D. Books: PHB 35–50 (creation, backgrounds, trinkets), 180–200 (species), 202–214
(feats), 216–236 (equipment), 349–362 (mounts); DMG Armaments (330–338). Codex: 385 entries (`coverage.py --dlc`).

## What Anton will see

Every weapon has its own trick: a mace knocks a man down, a rapier leaves an opening, a greataxe cleaves into the
next foe, and fighters and rogues choose which tricks they have mastered. Armour, gear and tools are the 2024 book's,
and each of them does something. A new character is made in the 2024 order: class, then one of sixteen backgrounds
(which gives the ability increases, an origin feat, skills, a tool and the starting kit), then the people – humans,
elves (drow, high or wood), dwarves, halflings and orcs in their 2024 form – then languages, abilities (point buy,
the standard array, or rolling 4d6) and looks. At levels 4 and 8 a feat may be taken instead of raising abilities.
Horses look like horses; mounts, carts and wagons can be bought; inns, meals and lifestyle follow the book's prices.

## Decisions

- **Masteries are kernel hooks** (`rules/engine/handlers/mastery.py`, ids in data/traits.json): each weapon's
  `mastery` in items.json; a fighter or rogue knows as many as the 2024 table gives (`Character.masteries`, chosen at
  creation and on level-up, swapped after a long rest); monsters with a weapon attack named after a mastery weapon
  use its mastery only when the stat block says so (2025 MM does not give masteries to monsters: none by default;
  trained soldiers and named NPC fighters built as characters do).
- **Character fields** (§4.4): `species`, `lineage`, `feats` [{id, choices}], `choices`, `masteries`, and `classes`
  as a list with one entry; `race` goes. Saves break: FORMAT_VERSION bumped in Part B; a new character is needed.
- **Backgrounds**: the eight map as Appendix D says (Folk Hero → Farmer, Outlander → Guide, Guild Artisan →
  Artisan); their Realmwalker ties and starting places are kept and written for the eight new ones. Ability bonuses
  move from species to backgrounds (+2/+1 or +1/+1/+1 among the three it names).
- **Half-Orc becomes the Orc**: in the world the half-orc folk and their culture become orcs (names, looks, towns
  stay); the orcs' own full culture comes in Expansion 8.
- **Feats** read their choices from the data (spells by list and level, so Magic Initiate grows with Expansion 3).
  Poisoner, Mounted Combatant and Crafter work in a basic form now and carry `upgrade_in` (4, 9, 23). The four 2014
  fighting styles a fighter picks today become the 2024 Fighting Style feats.
- **Level cap stays 10** until Expansion 3 (the 2024 classes to level 20); the feat-or-increase choice is at the
  levels the classes already give it.
- **Firearms** (musket, pistol) exist only as rare gnomish work (§1.3): never in ordinary shops or starting kits.
- **Tools** have their checks and uses now; making things with them stays camp crafting until Expansion 23.
- **Mounts** carry and draw (speed and load on the road, a cart's or wagon's load); fighting from horseback is a basic
  Mounted Combatant now, mounted combat in full in Expansion 9.

## Parts and tasks

### Part A — Arms and armour
- [x] A.1 Weapon table and armour to 2024 (items.json: properties, `mastery`, Lance, Trident, Whip, Blowgun, Musket,
  Pistol; armour and Shield numbers; improvised weapons); codex `weapon:*`, `armor:*`, the property sections.
- [x] A.2 The eight masteries as kernel handlers; `Character.masteries`, picks for fighter and rogue (creation,
  level-up, long rest); `actions.options` shows the mastery; battle log and cards say it; tests in a real fight each.
- [x] A.3 Tactics: topple then strike the prone, push into hazards or out of reach, sap the biggest hitter, slow to
  kite, vex to chain, cleave into clusters, nick for the extra blow; Auto and enemy; arena coverage green.
- [x] A.4 Armaments basics: +1/+2/+3 weapons, armour, shields, ammunition; adamantine, mithral, silvered (treasure
  and the DMG tables); townsfolk, soldiers and watch carry mastery weapons.
- [x] A.5 Pictures (new weapons in `figure_gear.py` and items sheet; mastery marks: knock-down, push, slowed,
  sapped, vexed), sounds; status icons and cards; Part A to `main`.

### Part B — Origins
- [x] B.1 Character fields (`species`, `lineage`, `feats`, `choices`, `classes` list); FORMAT_VERSION bump.
- [x] B.2 Species 2024: Human, Elf (Drow, High Elf, Wood Elf; lineage spells), Dwarf, Halfling, Orc; traits as kernel
  definitions; the half-orcs of the world become orcs; looks and bodies still drawn (`tests/test_looks.py`).
- [x] B.3 The 16 backgrounds: increases, origin feat, skills, tool, equipment or gold, ties and starting places.
- [x] B.4 Languages (standard and rare) merged with the world's tongues; creation in the 2024 order with point buy,
  standard array and 4d6; screens fit at three sizes; companions and townsfolk made the same way.
- [ ] B.5 Part B to `main` (the origin feats work from here: Alert, Crafter, Healer, Lucky, Magic Initiate,
  Musician, Savage Attacker, Skilled, Tavern Brawler, Tough).

### Part C — Feats
- [ ] C.1 Feat framework: prerequisites, choices, repeatable feats; ASI-or-feat on level-up with Suggest; Auto picks
  by archetype; the Feats tab on the character sheet.
- [ ] C.2 The general and fighting style feats (helpers in batches: data + handlers + one test each); the old four
  fighting styles retired.
- [ ] C.3 Combat feats in Auto's and NPCs' hands (Great Weapon Master, Sharpshooter, Polearm Master, Sentinel, Shield
  Master, Charger, Crusher, Piercer, Slasher, Mage Slayer, Defensive Duelist, Dual Wielder, Grappler...); arena green.
  Done-when test: a level 4 fighter takes Great Weapon Master and it works in battle, in the enemy's and Auto's hands.
- [ ] C.4 Part C to `main`.

### Part D — Gear, tools, mounts and the world; release
- [ ] D.1 Adventuring gear 2024 (Utilize uses; Potion of Healing and Spell Scroll left to Expansion 3), the packs;
  tools with checks and uses (camp crafts); trinkets in pockets, chests and starting kits.
- [ ] D.2 Services and lifestyle (inns, meals, tolls, coaches, ship's passage, hirelings, messengers) in
  `game/services.py` and prices in economy.json; shops stock the new gear by settlement size and people.
- [ ] D.3 Mounts and vehicles (riding/draft horse, warhorse, pony, mule, camel, elephant, mastiff; saddles, barding,
  feed, stabling; cart, wagon, carriage, chariot, sled) with their 2025 stat blocks; travel speed and load; a real
  horse picture and the other mounts.
- [ ] D.4 Every Expansion 2 codex entry settled; balance and the careful player measured; the icon; release v1.2.0.
