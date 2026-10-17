# Expansion 4 — Steel & Shadows (M, four parts)

*Icon*: a steel gauntlet gripping a dagger whose blade fades into shadow. *Tagline*: "Masters of the blade, and of the
knife in the dark." Branch `dlc/04-steel-shadows`; each part goes to `main` when it meets §5.2 of `docs/EXPANSIONS.md`;
the icon and version 1.4.0 come with Part D. Books: PHB 96–101 (Battle Master, Eldritch Knight), 135–136 (Arcane
Trickster); DMG 94–95 (Poison) and the Appendix B items; MM 25 (Assassin), 298 (Spy, Spy Master). Codex: 66 entries
(`tools/codex/coverage.py --dlc`).

## What Anton will see

At level 3 a fighter may now become a **Battle Master**: four (later six) superiority dice that come back on a short
rest, and maneuvers chosen from the book's twenty – trip a foe so friends strike at an advantage, turn a near miss
into a hit, parry a blow, riposte when a foe misses, rally a friend, push, disarm, goad, frighten, sweep into a second
foe – used by you, by your companions on Auto, and offered when you choose an attack. An **Eldritch Knight** casts
wizard spells between sword blows and calls a bonded weapon back to hand; an **Arcane Trickster** works a hidden,
spectral hand that picks pockets and trips foes, and at the top steals spells from the minds of casters. **Poisons**
are the DMG's: bought in black markets where the law allows it (and a crime where it does not), harvested from slain
creatures with a poisoner's kit, brewed, and coated on blades. **Assassins and spies** walk the world: guilds of
thieves and assassins offer work and poisons, cities hide black markets, realms keep spies (and catch them at court),
and knights of some peoples settle insults by duels of honour. The fighter's and rogue's magic items of the DMG come
last: the Vorpal Sword, the Luck Blade, the Defender, the Dancing Sword...

## Decisions

- **Maneuvers are kernel hooks** (`rules/engine/handlers/battle_master.py`, trait ids in data/traits.json) fed by a
  pool `superiority` (d8; d10 from 10, d12 from 18; 4/5/6 dice; short rest). Known maneuvers are
  `char.choices["maneuvers"]` (no save format change), chosen as a pending kind "maneuvers" (3 at level 3, +2 at 7,
  10 and 15, one swapped each time) with Suggest; the Auto's companions learn by their fighting style.
- **One maneuver per attack.** A blow's maneuver is asked as Cunning Strike is (`reactions.ask` with the battle's
  judgement as the default, `tactics.maneuver`); the save DC is 8 + the better of Strength and Dexterity + proficiency.
- **Checks outside a fight** (Ambush's Stealth, Commanding Presence, Tactical Assessment) work like Tactical Mind: a
  failed check that the die could turn spends it; Ambush adds its die to Initiative when the fighter would be behind.
- **Relentless**: once a turn, the first maneuver rolls a free d8 instead of spending a die.
- **Know Your Enemy** is the Study action with a bonus action at 30 feet (the creature's card shows its immunities,
  resistances and vulnerabilities), once a long rest or for a superiority die.
- **Student of War**: a tool (artisan's tools) and a fighter skill, chosen as pending choices.
- **The Eldritch Knight and Arcane Trickster** are third casters on the 2024 table (wizard spells; the trickster's
  from any school since 2024), slots and known spells through the Expansion 3 spellcasting (prepared lists).
  The Trickster's Mage Hand is invisible and steered with Cunning Action's bonus action.
- **Poisons** (DMG): items with `poison` {kind: contact, ingested, inhaled, injury; dc; effect}; coating a blade is
  the existing `coat_poison` item spell grown to every injury poison; buying is legal only where data/law.json says
  so (else a crime witnessed as theft is); harvesting is a Nature check with a poisoner's kit on a fresh body of a
  creature whose stat block deals poison (`gear` after a fight). The Poisoner feat loses its `upgrade_in`.
- **Assassin, Spy, Spy Master** are the 2025 stat blocks; they hide and strike first (tactics roles).
- **No new class.** Monsters do not get maneuvers (the 2025 MM gives none); named fighters built as characters do.

## Parts and tasks

### Part A — The Battle Master
- [ ] A.1 Data: the subclass and its features in classes.json; traits and the superiority pool; the twenty maneuvers
  (data/traits.json "maneuvers" with cost, when, save); the "maneuvers" pending choice (creation, level-up, Suggest,
  the Auto); Student of War's tool and skill.
- [ ] A.2 On a blow: Disarming, Distracting, Goading, Menacing, Pushing, Sweeping, Trip, Maneuvering, Precision (on a
  miss); reactions Parry and Riposte; Commander's Strike (one attack given to a friend's reaction); bonus actions
  Evasive Footwork, Feinting, Lunging, Rally; Bait and Switch; Ambush at Initiative; Relentless; Know Your Enemy.
- [ ] A.3 Checks: Ambush (Stealth), Commanding Presence, Tactical Assessment through `camp.check` / `Battle.check`.
- [ ] A.4 Tactics: Trip for friends' advantage, Precision on a near miss, Riposte and Parry, Menacing on a caster,
  Goading off a weak friend, Rally a hurt one; the Auto and the battle screen; arena green; a test in a real fight
  each.
- [ ] A.5 Cards, status icons (goaded, distracted), log lines, sounds; the codex's 28 Battle Master entries; Part A to
  `main`.

### Part B — The Eldritch Knight and the Arcane Trickster
- [ ] B.1 Third-caster slots and known spells (both); the wizard list; companions casting them.
- [ ] B.2 Eldritch Knight: War Bond (bonded weapons: never disarmed, called to hand), War Magic and Improved War Magic
  (a cantrip or a level 1-2 spell in place of attacks), Eldritch Strike, Arcane Charge.
- [ ] B.3 Arcane Trickster: Mage Hand Legerdemain (the spectral hand in a fight and in towns: theft, locks),
  Magical Ambush, Versatile Trickster (the hand trips), Spell Thief (a reaction; the stolen spell for 8 hours).
- [ ] B.4 Tactics, the hand's picture, cards and icons; 13 codex entries; Part B to `main`.

### Part C — Poisons and the people of the shadows
- [ ] C.1 The DMG poisons as items (buy, harvest, brew, apply; Potion of Poison, Dagger of Venom); the Poisoner feat
  in full; antitoxin and Periapt-like wards read through `query`.
- [ ] C.2 Assassin, Spy and Spy Master stat blocks with pictures, encounters and tactics (hide, strike first).
- [ ] C.3 The world: thieves' and assassins' guilds (work, poisons), black markets in cities, spies in realms'
  service (politics: a spy discovered at court; news), duels of honour where a people's culture has them.
- [ ] C.4 Cards, words, sounds; 4 codex entries (+ the two poison items); Part C to `main`.

### Part D — Arms of steel and shadow; release
- [ ] D.1 The fighter's and rogue's magic items of Appendix B (Vorpal Sword, Luck Blade, Defender, Dancing Sword,
  Sword of Sharpness, Wounding, Answering, Vengeance, Scimitar of Speed, Executioner's Axe, Mace of Terror, Vicious
  Weapon, Weapon of Warning, Rod of Lordly Might, Veteran's Cane, Gloves of Thievery, Boots of False Tracks, the
  Amulet and Periapt of Proof) with pictures and treasure placement.
- [ ] D.2 Every Expansion 4 codex entry settled; balance; the icon; release v1.4.0.
