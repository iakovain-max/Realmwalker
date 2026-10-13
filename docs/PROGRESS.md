# Realmwalker — progress log

Newest session first. Each milestone lists what's new, how to try it, decisions made, and known issues.

## Status at a glance

| Milestone | State |
|---|---|
| M0 — Setup | ✅ Done (2026-09-19) |
| M1 — World and movement | ✅ Done (2026-09-19) |
| M2 — Character | ✅ Done (2026-09-19) |
| M3 — Combat | ✅ Done (2026-09-19) |
| M4 — Body and survival | ✅ Done (2026-09-19) |
| M5 — Settlements and people | ✅ Done (2026-09-19) |
| M6 — Factions and politics | ✅ Done (2026-09-19) |
| M7 — Companions and progression | ✅ Done (2026-09-19) |
| M8 — Adventure content | ✅ Done (2026-09-20) |
| M9 — Death, legacy and release | ✅ Done (2026-09-20) |
| After v1 (rough edges, fair chances, riding...) | ✅ Done |
| **1.0 — Pictures and a new interface** | ✅ Done (2026-10-03), branch `graphics-ui` |
| **1.0 — Combat on a grid (a D&D battle mat)** | ✅ Done (2026-10-06), branch `grid-combat` |
| **Every item does something** | ✅ Done (2026-10-09), branch `useful-items` |
| **Choose how you look** | ✅ Done (2026-10-10), branch `looks` |
| **Sound and music** | ✅ Done (2026-10-10), branch `sound` |
| **A world that has lived (history after Dwarf Fortress)** | ✅ Done (2026-10-10), branch `world-history` |
| **Peoples, a land of extremes and wonders, a new world map** | ✅ Done (2026-10-11), branch `world-variety` |
| **Varied, bigger, living towns** | ✅ Done (2026-10-11), branch `world-variety` |
| **Clearing the decks for the expansions** | ✅ Done (2026-10-12), branch `prep/clear-the-decks` |
| **Expansion 1, *Dice & Destiny*** (version 1.1.0) | ✅ Released (2026-10-13), branch `dlc/01-dice-destiny` |
| **Expansion 2, *Blades & Backgrounds*** (version 1.2.0) | ✅ Released (2026-10-13), branch `dlc/02-blades-backgrounds` |
| **The expansion programme** (`docs/EXPANSIONS.md`, `docs/expansions/STATUS.md`) | ✅ Expansion 2, *Blades & Backgrounds* released (version 1.2.0, 2026-10-13); Expansion 3 next |

---

## After v1 — continuing work (2026-09-20), up to version 1.0 (2026-10-03) and since

The nine milestones are done; this is what has been added since, newest first. Version 1.0 is the pictures and the
new interface; then combat moved onto a grid, then every item was given a use, then looks became a choice, then the
game got sound and music, then worlds began to live their history, then the world got its peoples, its extremes and
wonders and a new map, then its towns were rebuilt by each people and came alive, then the decks were cleared for
the expansion programme (the first entries below).

### Session, 2026-10-13: Blades & Backgrounds part D — gear, inns, mounts; **released as 1.2.0** — branch `dlc/02-blades-backgrounds`

The last part of Expansion 2. **Expansion 2, *Blades & Backgrounds*, is released as version 1.2.0**: its icon (a
sword across a rolled scroll) is on the main menu's shelf. Saves from part C (format 16) still load; saves from
before part C do not (start a new world).

**What is different when you play**
- **The 2024 tools**: 25 new ones (every artisan's tool, the forgery and poisoner's kits, ten instruments,
  dragonchess and Three-Dragon Ante). Each has its Utilize uses on its card. Trained with a tool you add your
  proficiency to checks made with it, and trained in the skill as well you have advantage (camp crafts, picking a
  lock with thieves' tools). 22 new things to make at camp (m) with them: antitoxin and poison, arrows and bolts,
  ladders and poles, chains and spikes, a map, perfume, glass bottles...
- **The 2024 adventuring gear**, every piece of it doing something:
  - in a fight (the Item menu, u): **acid** dashed at someone, a **net** that restrains, **caltrops** and
    **ball bearings** strewn on the ground (whoever walks in is hurt and stopped, or falls), **basic poison** smeared
    on a blade with a bonus action (the next cut deals 1d4 poison more);
  - **antitoxin**: drink it for advantage against being poisoned for an hour;
  - **the seven packs** (explorer's, dungeoneer's, burglar's, priest's, scholar's, entertainer's, diplomat's): open
    one in the pack (Enter) and it becomes its contents;
  - **underground**: a pole finds traps, a magnifying glass searches with advantage, a portable ram forces doors;
  - **on the road**: ladders, climber's kits, iron spikes, block and tackle, chains, a signal whistle, string and a
    bell are choices in 18 of the road's events (over the walls of a shut town, a stuck cart, a fallen climber...);
  - bottles, jugs, flasks, buckets and barrels hold water; baskets, pouches, quivers, cases and chests carry; a lock
    holds a prisoner; a costume helps a disguise; a lamp and a bullseye lantern give light; a mirror, perfume and fine
    wine please the gentry; the arcane, druidic and holy foci.
- **A trinket in every pocket**: a hundred keepsakes written for the game, one in every new character's kit, and
  sometimes one in the pocket of someone who carried coin, or in a chest. Each has its own small story on its card.
- **Shops** stock all of it, the rarer things only in towns or cities, and each people's general stores have their
  own wares (dwarven lamps and mason's tools, elven lyres and yew wands, halfling cookware, Highland bagpipes...).
- **Inns by the book** (PHB 2024): a bed and a meal of each grade the town has, from a squalid loft (cheap, and your
  purse may be lighter in the morning, and the food may disagree with you) to an aristocratic suite (the town's high
  folk think better of you for three days), priced for each of you. **Stay a while**: three or seven days living at a
  chosen lifestyle, fed and rested.
- **Travel by the book**: a **toll** of 1 cp a head at a walled town's gate; **coaches** from towns to towns along
  the roads (3 cp a mile each; the days pass on the way); **ships** between harbours (1 sp a mile); a **messenger**
  (2 cp a mile) to fetch a companion who waits in another town.
- **Mounts**: **horses that look like horses** (and ponies, mules, draft horses, warhorses, camels, elephants and
  mastiffs). A camel keeps its pace in the desert; an elephant needs an exotic saddle; a mastiff carries only the
  small folk, eats meat, and guards the animals at night as well as a watch. **A rider needs a saddle**: bareback, you tire as if you walked. In towns the stable feeds
  your animals for 5 sp a head a day.
- **Vehicles**: carts, wagons, carriages, chariots and sleds at the stable. The animals nobody rides pull it, and
  pull five times what they could carry; off the roads it is slow going (a sled on snow is not); a carriage seats
  four, who ride instead of walking.

**How to see it**: start a new world (or keep a world made after part C). The shops, inns and stables of any town;
the Item menu (u) in a fight; your pack (i) for the trinket and to open a pack; the shelf on the main menu.

**What could not be checked**: the new pictures (55 gear icons, the horses, camel, saddles and carts, the icon) were
looked at on contact sheets and in the window smoke test, not in play by eye.

**Anything assumed**: coaches run up to 160 miles, four miles an hour for ten hours a day; ships sail two miles an
hour day and night, up to 600 miles; a messenger rides 30 miles a day there and back; hired companions keep their
own wages (below the book's 2 gp a day: they share the loot too); the horses' stat blocks wait for mounted combat
(Expansion 9), and so does barding; the military saddle is a plain saddle until then; a carried basket, pouch,
quiver or chest adds to what you can carry (each kind once); the inn charges each of the party; a mirror and perfume
please the gentry a little (+2, +3); the druidic foci work when the druid comes (Expansion 3); Mounted Combatant is
written but not offered until mounted combat comes.

**Codex** (`tools/codex/coverage.py`): Expansion 2: all 384 entries settled (310 done, 74 adapted). Player's
Handbook 34% · Dungeon Master's Guide 11% · Monster Manual 8%.

### Session, 2026-10-13: Blades & Backgrounds part C — feats — branch `dlc/02-blades-backgrounds`

The third part of Expansion 2. **A new world is needed**: saves from before this part are refused kindly ("Could
not load ... The files are still there, untouched."), because fighting styles are now feats.

**What is different when you play**
- **At levels 4, 8, 12...** the ability increase now offers a **feat** instead: the 42 general feats of the 2024
  book (Great Weapon Master, Sharpshooter, Sentinel, Polearm Master, Shield Master, War Caster, Resilient, Tough,
  Elemental Adept, Crusher, Piercer, Slasher, Charger, Mage Slayer, Inspiring Leader, Chef, Ritual Caster, Actor...),
  and the origin feats you do not have yet. **Suggest** picks one that suits how the character fights. A feat's own
  choices (which ability it raises, which element, which skills) are asked one at a time.
- **The fighter's fighting style is one of ten Fighting Style feats** (Archery, Defense, Dueling, Great Weapon
  Fighting, Two-Weapon Fighting, Protection, Interception, Blind Fighting, Thrown Weapon Fighting, Unarmed
  Fighting); a Champion learns another at level 7.
- **Feats work in a fight**: the heavy blow and Hew of Great Weapon Master, the shield's bash, the polearm's butt
  end, Sentinel stopping a foe in its tracks, Crusher's shove, Piercer's re-rolled die, Slasher's hamstring,
  Mage Slayer breaking a caster's spell, a Dual Wielder's off-hand longsword, and more. **Your companions on Auto
  and the enemy use them too**: berserkers swing with Great Weapon Master, town guards hold the line with Sentinel,
  an orc warchief crushes.
- **Away from fights**: an Inspiring Leader's words and the Chef's meal give hit points after a rest; a Ritual
  Caster has rituals; an Actor can pass for someone else.
- The character sheet has a **Feats** tab; the battle shows the new marks (reeling, unsteady, slowed) with cards.

**How to see it**: start a new world, make a fighter, and play to level 4 (or, with the debug console switched on, type `xp 3000`);
the level-up screen lists the feats, and Suggest picks one.

**Anything assumed**: Mounted Combatant is written but not offered until mounted combat comes (Expansion 9); a
duellist keeps a versatile blade in one hand (d8 + 2 is better than d10); Spell Sniper's longer reach is for spells
with an attack roll only, as the 2024 book says; Sentinel answers a hit on anyone but the sentinel; Skulker hides
with advantage (the book's Fog of War). The part was finished by a second session after the first was cut off by a
usage limit; a fresh review found nine things, all fixed (Dual Wielder could not hold a longsword in the off hand,
Crusher and the shield asked again after their trick was spent, raw words like "dex" on the sheet).

### Session, 2026-10-13: Blades & Backgrounds part B — origins — branch `dlc/02-blades-backgrounds`

The second part of Expansion 2. **A new world is needed**: saves from before this part are refused kindly ("Could
not load ... The files are still there, untouched."), because a character now carries a species, a lineage, feats
and their choices.

**What is different when you play**
- **A character is made in the 2024 order**: calling first, then one of **sixteen backgrounds**, then the people,
  then a new **Origin** page, then abilities, skills, who you are, looks and where you start.
- **The background shapes you most.** It raises three abilities (+2 and +1, or +1 to each), gives an **origin
  feat**, two skills, a tool, and its gear (or 50 gold pieces instead, to buy your own). Folk heroes, outlanders and
  guild artisans are now farmers, guides and artisans; new are the charlatan, entertainer, guard, hermit, merchant,
  sailor, scribe and wayfarer, each with their own ties to real people and places and their own way of telling
  your past.
- **Ten origin feats work in play**: Alert (quicker to act), Crafter (three trades, a fifth off plain goods),
  Healer (with a healer's kit, patch a friend up mid-fight), Lucky (luck points: roll a missed blow or a failed save
  again), Magic Initiate (two cantrips and a spell from the cleric's, druid's or wizard's lists, cast without being a
  caster), Musician (after a rest your playing heartens the others), Savage Attacker, Skilled, Tavern Brawler (fists
  that hurt, and a shove), Tough.
- **The peoples in their 2024 form**: humans (an extra skill and a second origin feat), elves (choose drow, high or
  wood elf: darkvision to 120 feet for a drow, speed 35 for a wood elf; hard to charm, never put to sleep), dwarves
  (darkvision 120 feet, tough, resist poison, and on stone they can feel every footstep within 60 feet), halflings
  (brave, lucky on attacks and saves, slip past bigger folk, hide behind them) and **orcs**, who replace the
  half-orcs everywhere in the world (an Adrenaline Rush to close the distance, and very hard to kill). Everyone
  walks 30 feet now (the wood elf 35).
- **Ability scores**: point buy as before, the standard array (15, 14, 13, 12, 10, 8), or **rolling 4d6** (R rolls
  again); array and rolled scores are swapped into place with the arrow keys.
- **Languages**: everyone speaks Common and chooses two more (the realm's own tongues among them).
- **Your companions and the people you meet** are made the same way; on Auto they cast their feat's spells, run in
  with Adrenaline Rush when nothing is in reach, and feel through the stone for a foe they cannot see.
- The character sheet now opens with your ties and looks, then your traits, features and feats.

**How to see it**: start a new world (title screen, New World), and make a character: the Origin page is step 4.

**What could not be checked**: how the Origin page reads to a player, and the new orc bodies, were seen only in
the window smoke test and tests at five window sizes.

**Anything assumed**: gear the game does not have yet (pouches, costumes, a mirror, perfume, a quiver, a forgery
kit, a cartographer's tools, a tent for the guide) is paid in coin at its price until part D; the lineages' spells
work as their spells arrive (Expansion 3; a high elf's Misty Step at level 5 works now); Magic Initiate's spells are
cast in a fight, not yet on the road; Lucky works on your own rolls, not yet on a blow aimed at you; Alert has no
Initiative Swap; the realm's own tongues count as standard languages. Balance: a level 1 hero now beats two wolves
85 times in 100 (it was at most 80) and is knocked down 15 times in 100 (it was at least 20); the band was widened
and the change is the 2024 origins at work.

### Session, 2026-10-13: Blades & Backgrounds part A — arms and armour — branch `dlc/02-blades-backgrounds`

The first part of Expansion 2, *Blades & Backgrounds*. Its icon and version 1.2.0 come with the last part (D). No
new world is needed; a character made before this part simply has no weapon masteries until the next long rest
(then the character sheet offers them, m).

**What is different when you play**
- **Every weapon has its own trick (weapon mastery, 2024).** Fighters master three kinds of weapon (four from level
  4, five from level 10), rogues two. The kit's weapons are chosen for you; on the character sheet (c, then m) you
  can choose again before your first long rest and once after every long rest after that. The battle's action list
  names the trick next to the weapon ("maul (Topple)"), and the log and the battle board show it as it lands:
  - *Topple* (maul, quarterstaff, battleaxe, lance, trident): a Constitution save or the foe falls prone, and the
    friends beside it strike it with advantage.
  - *Push* (warhammer, greatclub, pike, heavy crossbow): the foe is driven ten feet straight back, into the fire if
    there is fire behind it.
  - *Sap* (mace, spear, longsword, flail, morningstar, war pick): the foe's next attack is at a disadvantage.
  - *Slow* (club, javelin, sling, light crossbow, longbow, whip, musket): ten feet off its speed (never more).
  - *Vex* (rapier, shortsword, handaxe, shortbow, dart, hand crossbow, blowgun, pistol): your next attack on it has
    advantage.
  - *Graze* (greatsword, glaive): even a miss cuts, for your Strength bonus.
  - *Cleave* (greataxe, halberd): a hit carries on into a second foe beside the first, once a turn.
  - *Nick* (dagger, light hammer, sickle, scimitar): the second weapon's blow is part of the Attack and keeps your
    bonus action free.
- **Your companions on Auto and your enemies use the tricks on purpose**: topple where friends will strike the
  fallen, sap the hardest hitter, slow the one to be kept away, push into a burning patch, cleave into a crowd.
  Ordinary monsters have no masteries (as in the 2025 Monster Manual); the watch's guards and deserters, trained
  soldiers, do (the spear's Sap).
- **The weapon and armour tables are the 2024 book's**: new weapons (lance, trident, whip, blowgun with needles),
  and the musket and pistol as rare gnomish work that no ordinary shop sells; the warhammer weighs 5 lb and the war
  pick can be swung two-handed. A heavy weapon wants Strength 15 (or Dexterity 13 for a heavy bow or crossbow);
  a crossbow fires once a turn even for a fighter who strikes twice; after a won fight you find half the arrows and
  bolts you loosed; a bow swung at close quarters is a club (1d4).
- **Armour needs training**: worn without it, every Strength and Dexterity roll is at a disadvantage and no spell
  can be cast (rituals neither); a shield without training gives nothing. Putting armour on outside a fight takes a
  minute (light), five (medium) or ten (heavy).
- **Treasure has the book's armaments**: +1/+2/+3 weapons, armour and shields of any kind, +1/+2/+3 arrows and bolts
  (a choice of their own on the action bar; the plain shot never wastes them), adamantine armour (no critical hit
  gets through), adamantine weapons (break things), mithral armour (no Strength needed, no clatter when sneaking),
  silvered weapons.
- **Pictures and sounds**: the new weapons in the pack and in hand; two new state icons (Sapped, Vexing) with their
  cards; a fall thuds, a push shoves.

**How to see it**: start a fighter or a rogue (New Character), open the character sheet (c) to see the weapons
mastered (m to choose again), and fight: the attack menu names each trick.

**What could not be checked**: the look of the new weapons and of the trick words on the battle board was checked on
the tile sheet and in the window smoke test, not in a long game; the balance of masteries for the enemy is measured
only by the arena and balance runs.

**Anything assumed** (written in STATUS.md too): the lance is always two-handed until mounted combat (Expansion 9);
magic ammunition is spent once loosed, hit or miss; a bow is the only thing swung as an improvised weapon (throwing a
blade without the Thrown property is left out: the Auto would throw away its only weapon); a silvered weapon's extra
die waits for shapechangers (none in the world yet); push and topple are the battle's judgement for the Auto and the
enemy, and for you unless the Reactions setting is "all".

### Session, 2026-10-13: Dice & Destiny part E — cards, icons and pictures; **version 1.1.0 released** — branch `dlc/01-dice-destiny`

**Expansion 1, *Dice & Destiny*, is finished and out (version 1.1.0).** Its icon, a gold twenty-sided die, is now on
the title screen's shelf. No new world is needed for this part (part D's note still stands: saves from before
2026-10-12 do not load).

**What is different when you play**
- **Point at anything in a fight and a card tells you what it is.** Rest the mouse on someone for a moment: their
  name and what they are, how hurt they look, the states they are in, and for a creature a short stat block (armour,
  speeds, senses, what it resists or shrugs off, each of its traits and attacks, its breath ready or recharging,
  Legendary Resistance left, its Challenge). The same card is on the turn-order bar and on the target's name in the
  side panel.
- **Small icons for every state**, in a row over each figure's health bar (up to four, then "+3"): the fifteen
  conditions of the 2024 rules (prone, grappled, frightened, poisoned, asleep...), exhaustion, Bloodied, dying (with
  the death saves made and failed) and stable, and everything a spell or a feature leaves on someone: concentrating,
  hidden, flying, dodging, a blow readied, marked by Guiding Bolt, temporary hit points, Heroic Inspiration, slowed,
  on fire, holding someone, a stirge feeding, blessed, shielded, warded, resisting, guided, unable to heal, unable to
  strike out, surprised; and your own body's troubles (bleeding, a festering wound, pain, drink, wounds). Point at
  an icon for its card: what it does, who caused it, how long it lasts and how it ends. The one whose turn it is,
  and the one you are aiming at, have the same row of icons in the side panel, for those who play with the keys.
- **The battle log shows its dice.** Point at a line ("The goblin's blade opens your arm") and its roll appears:
  "d20 15 + 4 = 19 vs AC 16 — hit [flanking]", the damage, and whether it was a critical, resisted or doubled. This
  works whether or not the dice lines are shown in the log.
- **The action list explains itself.** Point at an attack, a spell or an ability in the list: what it costs, its
  range and area, its damage and save, concentration, how long it lasts, and the chance against the nearest foe.
- **Spells look like what they are**: Fire Bolt flies, Ray of Frost and Scorching Ray are beams, Lightning Bolt is a
  crackling line, Fireball is a bead that bursts, Burning Hands and Cone of Cold sweep out from the hands,
  Thunderwave is a shockwave, Ice Storm falls unevenly, Sacred Flame and Flame Strike come down from above as a
  column of light or fire, Hold Person and Command leave a dark ring, Spirit Guardians spreads around the priest.
  Bolts, rays and lines have the sharper bolt sound.
- **The beasts and monsters look more like the game's own figures**: a wolf, a dog, a rat or a snake now stands
  lower than a man instead of filling his square; every borrowed picture has the same dark outline and light from
  the top left, and no soft glows round it. The ghost and the wraith keep their faint, dotted look.
- **Magic things in the pack carry marks**: a gold ring for a thing bound to someone, a speech mark for a thing
  that is awake and wants something; point at them for what they mean.
- **Out of a fight**, pointing at the troubles under a party member's name in the side panel (hungry, cold,
  bleeding...) shows one card with each trouble and what to do about it.
- **A new setting, Creature details** (Settings): Full (as above), or What my character knows: until someone has
  studied a kind of creature (the Study action) or killed one before, its card shows only how hurt it looks and
  what states it is in.

**How to see it**: start or load a game and get into a fight (or use the debug console, `fight goblins`); rest the
mouse on a figure, an icon over a head, a line of the log, a choice in the list. The shelf icon is on the title
screen; pointing at it shows everything the expansion adds. **Settings → Creature details** changes the cards.

**What could not be checked**: how the cards and icons look at Anton's window size, and whether the half-second wait
before a card feels right; the adapted monster pictures were judged on a contact sheet (`build/adapt_sheet.png`
after `tools/build_tiles.py --adapt-sheet build/adapt_sheet.png`), not in his game.

**Anything assumed**
- The chance on an attack or spell card while choosing from the list is against the nearest foe.
- Icons for raging, Hunter's Mark, Hex and the weapon masteries come with the expansions that bring those features.
- Squares and the path keep their words in the side panel (what is under the mouse) rather than a floating card.
- Small beasts' heights (a wolf about three quarters of a man, a rat half) were chosen by eye.

**Codex coverage**:

| Book | Done | Adapted | Left out | Of |
|---|---|---|---|---|
| Player's Handbook | 194 | 36 | 7 | 1,797 |
| Dungeon Master's Guide | 24 | 22 | 20 | 651 |
| Monster Manual | 26 | 8 | 0 | 503 |

Expansion 1's own entries: all 327 settled (237 done, 65 adapted, 25 left out with a reason). Six glossary words
whose subject comes later were handed to the expansions that bring it: illusions (5), shape-shifting (11),
possession (18), burrowing (19), suffocation (22), improvised weapons (2).

**Also in this part (rules)**: a party member whose melee blow would kill a beaten person may knock them out instead
(the game asks; they are taken alive, a prisoner after the fight); Identify, and any ritual, cast outside a fight
spends no spell slot and ten minutes more; a creature with a damage threshold shrugs off smaller blows; a creature
with tremorsense feels anyone standing on the same ground.

### Session, 2026-10-12 (late night): Dice & Destiny part D — treasure, magic items, encounters — branch `dlc/01-dice-destiny`

**Start a new world**: saves from before this part no longer load (the game says so kindly; the files stay).

**What is different when you play**
- **Magic things must be bound to someone.** Anything of real power (rare or better, or that raises an ability, a
  save, casts spells, wards off fire...) works only for the one *attuned* to it: in the pack, **a** spends an hour
  binding the member whose page it is (and an hour to end it). Nobody can hold more than three such bonds. A plain
  +1 sword or shield needs none. A cursed thing shows itself when you bind to it (or put it on), and will not let go
  until a temple lifts the curse. A focus that casts spells binds only to someone who casts spells of their own.
- **Finding out what a thing is**: **k** in the pack spends an hour handling it and tells you what it does, every
  time, no roll; but never whether it is cursed (a priest and Identify do not tell you that either).
- **Charges come back at dawn**, some of them (a wand rolls its dice), no longer all of them with a long rest.
- **Artifacts.** The lost treasures of a world's history (the chests on the deepest level of the right ruin) are
  now true artifacts: a legendary thing's powers, plus one or two lesser gifts and a great one rolled for this world
  (a skill, warding against poison or fear, a resistance, a spell it casts, +1 armour, +2 to an ability, wounds
  closing every turn, a jolt of force on every hit, ten feet more speed, warding of the senses), and one or two
  flaws (weak arms or will, double harm from poison or from everything, blind or deaf whenever someone else wears
  it, a stink that ruins creeping, torches that go out under the ground, companions who cannot rest near you,
  beasts that cannot be calmed, a kind of creature that will never talk to you, potions going flat, scrolls going
  blank, no healing at all...); some bite when you bind to them (an ability lost for good, 8d10 of pain, a chance
  of death). Each says the one way this world remembers it can be destroyed.
- **Some things are awake.** A very rare thing may have a mind (more often a legendary one, half of all
  artifacts): Intelligence, Wisdom, Charisma, a nature, a way of making itself felt (feelings, speech, a voice in the
  head) and a purpose: a hatred of one kind of creature, a love of blood or of fame, a hunger for lore or for its
  maker, a cause, a people to protect, a god to serve. It is pleased by what serves that purpose and says so; go
  against it (run from a fight, buy your way past robbers, harm those it protects, desecrate graves...) and its
  bearer must hold firm (Charisma) or it makes a demand: keep it on you, get rid of something it hates, hand it to
  someone else, or serve its purpose within a week. Ignore it and it withholds its power; ignore it longer and it
  takes hold of its bearer for hours, and in any fight then they fight as it wills (on Auto).
- **Treasure by the Dungeon Master's Guide.** Creatures carry what their kind carries (a bandit a few gold
  pieces, a wolf nothing; a gang that keeps a hoard at home has one purse on the road, its captain's). The best
  chest on the deepest level of a ruin or cave is now the hoard of whoever rules it, sized by how strong they are
  and in the form their kind likes: gems for the arcane, coin and silver bars for warriors, trade goods for
  goblin-kind, old art for cultists and the like. There are 52 kinds of gemstone and 50 art objects to find. The
  magic in a hoard is rolled on the book's own tables by theme and rarity; things the game does not have yet are
  rolled again and then made as one of Realmwalker's own, so treasure grows richer as the expansions come. The
  world's Magic setting scales how much magic there is. Ordinary chests hold smaller stashes; coffins hold art.
- **Money is the book's now**, so there is more of it than before (prices were always the book's).
- **Cities where mages keep a house sell a minor magic thing or two** (where the lord's law allows magic).
- **Great works are rewarded better**: after a bounty, a rescue, a lost treasure brought back and the like, a
  lord, priest or headman may add a magic thing from their strongroom to the coin they promised.
- **Bands are sized by the book's experience budget** for the country they live in (they do not grow with you:
  some fights should still be avoided). Measured against before, parties of three meet the same bands, a lone
  traveller sometimes fewer in quiet country, never more. The "how dangerous they look" line now uses the book's
  difficulty against your real party.
- **Travel pace (v on the map)**: Fast covers ground in three quarters of the time but you notice less, lose your
  way more easily and cannot slip away quietly; Slow takes half as long again but you notice more, keep your
  bearings and slip away quietly. Mountains and marsh are slow going and allow no Fast pace; a road allows one step
  faster. The action bar shows the pace.
- **Moods.** Not every band on the road wants a fight: some are wary but not hostile, and you can **let them be (l)**
  and go on; now and then one is friendly. Talking your way past is harder with a hostile band and easier with a
  friendly one (the 2024 rule: DC 15 or their wits, with advantage or disadvantage by their mood), and in a fight
  the enemy listens more once most of them are bloodied. In towns, a person's mood does the same for every check in
  a conversation (instead of making it harder or easier by a number).

**How to test**: start a new world; find a ruin with a lost treasure in it (books of lore name them) to see an
artifact; in the pack try **k** and **a**; on the map press **v** a few times; travel in dangerous country and meet a
band that is only wary.

**What could not be checked**: how the new amounts of money feel over a long game; the sentient things' lines and
how often they speak are by reasoning, not by play. Tell me if they talk too much or too little.

**Anything assumed (choices made)**: the book's hoard row for CR 11-16 prints a multiplier ten times too big for
its own average; the average was kept. Artifact properties needing a person to set a quest or a creature not in the
game yet are rolled again. A village cannot pay a dragon's hoard for a delivered letter, so quest coin stays as
the terms say and only the great works add a magic gift. Bands keep the old thinning for a lone traveller (a first
version sized purely by the book was much deadlier).

**Balance**: `tools/balance.py` bands hold; the encounter sizes were measured old against new over 400 bands per
party and danger.

### Local session, 2026-10-12 (night): Dice & Destiny part C — enemies that think, and more ways to move — branch `dlc/01-dice-destiny`

**What is different when you play**
- **Enemies fight with everything they have, and choose.** Every creature now knows all its attacks and spells and
  weighs each by the same numbers you see (the chance to hit or to fail the save, the damage after resistances, a
  knock-down or a paralysis that would take): a ghoul opens with its paralysing claw, a giant spider throws its web
  first, a cult fanatic holds a fighter with Hold Person, bandits draw their scimitars when cornered. Beasts go for
  the nearest and weakest; clever foes gang up on one of you; the cleverest go for your casters and healers.
  Creatures say how they fight (brute, skirmisher, archer, controller, leader, support, lurker, solo): archers and
  casters start at the back and keep their distance, brutes charge in, leaders hang back and strike where their band
  is already at work. And they use more than blows: they **search** when you hide, a lurker **hides** and waits for
  you, they **knock someone down** when friends beside the victim will pile on, **grab** a spellcaster who would
  step away, **help** a stronger friend by distracting you, stand **on guard** to keep a spell going, **ready** a
  shot rather than run in, and **break down a door** between them and you.
- **Your companions on Auto use their whole class**: a cleric turns undead that come close, or shares out Preserve
  Life; a war cleric strikes again with the bonus action; a fighter catches a Second Wind when hurt and surges when
  it is hard going; a rogue slips away with Cunning Action. They also choose any spell they know by what it would do.
- **New moves on the battle map** (2024 rules): climb onto a table, a fence, barrels or a low wall, or swim deep
  water (each costs double, unless the creature climbs or swims by nature, like the giant spider); leap a stream, a
  chasm, a campfire or a fence (as far as your Strength score in feet after a 10-foot run, half standing; landing on
  rough ground can knock you down, and catching a fence stops you short); a river's current can be too strong. New
  actions: **Study** (k) to recall what a creature is and what it can do (instead of the free roll at the start),
  **Search** (o) for hidden foes, **Ready** (q) a blow or a shot for the first enemy to come near.
- **Fliers fly**: the stirge and the young dragon go over water and low things; a dragon breathes, then rises just
  out of reach of your swords (rising away from you gives you a free swing at it) and comes down to bite. The map
  shows a flier above its shadow with its height in feet. Knocked down or senseless, a flier falls. Your companions
  on Auto wait under it with a blow ready for when it comes down. Anyone who can fly does it with **Fly (v)**.
- **Break (x)**: strike a door, barrel, table, cart or crate instead of a creature (one of your attacks).
- A charmed creature fights for whoever charmed it, and comes back to its side when the charm ends. No spell works
  in an antimagic area, nor do spiritual weapons or guardians there.
- Someone knocked senseless in the middle of a move, in a friend's square, ends up lying there (as the rules say).

**How to test**: fight in a town or a farm (tables, fences, barrels) and watch the enemy and your companions climb
and leap; set your companions to Auto against skeletons with a cleric in the party; hide in brush and see the
enemy search for you.

**Proof, not hope**: a new tool, `tools/arena.py`, fights every creature in four set-ups and reports what it used
and how long each enemy turn took to think; a test now fails if any creature never uses one of its attacks or
spells, if the tactics ever try something the rules forbid, or if a turn takes too long (an enemy turn takes about
a fiftieth of a second; the slowest about a tenth).

**Balance**: the bands of `tools/balance.py` hold.

### Local session, 2026-10-12 (evening): Dice & Destiny part B — the 2024 rules and the 2025 creatures — branch `dlc/01-dice-destiny`

**What is different when you play**
- **Every creature you already meet is its 2025 self**, number for number from the Monster Manual (checked on its
  pages). Wolves and bears knock you down when they hit; a bugbear grabs you from ten feet away and drags you; a
  stirge fastens on and drinks every turn; a hobgoblin's longsword hits like a hammer (2d10); goblins and bugbears are
  fey now, gnolls fiends; a troll heals 15 a turn and charges; zombies get back up unless the blow was holy or a
  critical; nobles and the bandit captain parry. The bandit archer is a Scout and shoots twice, so the small bandit
  bands on the roads are plain bandits again (2025 bandits carry crossbows) and the Scouts stay with the captain's
  gangs. The captain throws daggers rather than a pistol, until firearms come (Gnomes & Golems).
- **Spells are their 2024 selves**: Sleep takes a foe in two steps and a blow or a shake wakes it; Cure Wounds heals
  2d8, Healing Word 2d4; Inflict Wounds is a Constitution save; Command makes a foe grovel its turn away; Hold Person
  holds one more with a higher slot; Spiritual Weapon needs concentration; and so on (the full list is in git).
- **The 2024 rules**: surprise costs initiative, not a turn; exhaustion takes 2 off every roll and 5 feet of speed per
  level (no more halved hit points); grappling and shoving are saving throws and one of your attacks; you can drag
  someone you hold; Help distracts an enemy for a friend's next blow; Hide needs a 15; humans wake from every long
  rest with Heroic Inspiration (one failed roll tried again); a pit is a fall (1d6 for every 10 feet); Alchemist's Fire
  sets people burning until they roll it out.
- **Reactions ask you first.** When the rules give you a choice out of turn and it costs something (Shield, a use of
  Indomitable, Guided Strike, Heroic Inspiration...), the fight stops with a small "Reaction" box: Enter takes the
  suggestion, or y / n, or click. A new setting, **Reactions** (after "Companions in a fight"): Ask me (the default),
  Ask for everything, Decide for me.

**How to test**: start a fight with a wizard in the party who knows Shield (or a fighter at level 9 with
Indomitable): when a blow would land, the Reaction box asks. Try Settings, Reactions, to change it.

**Balance**: measured before and after every step with `tools/balance.py` and the careful-player tests; every band
holds (two wolves are a little easier than before, three bandits about the same).

**For later sessions**: the battle code's numbers and features now come from data (data/conditions.json,
data/traits.json, data/spells.json effects, data/statblocks.json); CLAUDE.md describes the kernel. What is still
written by hand in the battle code, and why, is listed in docs/expansions/01-dice-destiny.md.

### Local session, 2026-10-12 (later): Dice & Destiny begins — part A done, the rules kernel started — branch `dlc/01-dice-destiny`

**Why the computer was working so hard, and what changed.** Since the world got its long history, a test run made
about eighty worlds (each lives centuries of history), and from the moment letters mode went, every map drawn in a
test started the overworld painter on a thread of its own: a few hundred painters at once, on all sixteen cores.
Now: tests draw maps without painting the parchment behind them; the worlds tests need are made once and kept in
`build/test_worlds` while the code that makes them is unchanged (a test in a fresh process checks that list); and
tests run on 6 workers, not 16. The whole suite takes about a minute and a half, with about a third of the work.
Changing the battle code no longer throws the kept worlds away.

**What is different when you play**
- **The main menu has a shelf** on the right: one icon per expansion that is out (none yet: Dice & Destiny shows
  when its last part is done), each with a tooltip, glinting until you have looked at it. E opens the Expansions
  screen: what each one added, and which version.
- **Fights follow the 2024 conditions.** The conditions (Blinded, Charmed, Frightened, Grappled, Incapacitated,
  Invisible, Paralysed, Petrified, Poisoned, Prone, Restrained, Stunned, Unconscious, and Exhaustion) are now written
  down as game data, from the Player's Handbook glossary, and every fight reads them there. What that changes: a
  blinded enemy is easy to hit; someone held fast strikes badly at anyone but the one holding them; fear spoils your
  aim only while you can see what you fear; dodging does not help while you are held; a hit from right beside a
  paralysed or senseless body is a critical whatever the weapon. Everything else about fights is as before (a test
  asks four hundred random moments of a fight both the old way and the new way).

**For the next sessions (the books, as a checklist).** `docs/expansions/codex/` now lists all 2,951 things in the
three books (spells, monsters, magic items, classes and features, species, backgrounds, feats, gear, rules, bastions,
planes...), each given to one of the 26 expansions; `tools/codex/coverage.py` counts what is done. An expansion is not
released while one of its entries is still to do. Under the hood, fights now go through a small "rules kernel"
(`realmwalker/rules/engine/`): every number (advantage, saving throws, armour, speed, damage) is worked out in one
place, and traits like Pack Tactics, Sneak Attack or a troll's Regeneration are definitions in data/traits.json
instead of special cases in the battle code. That is what lets 390 spells and 500 monsters come in later.

**Decisions made without you (say if you disagree)**: a few items and creatures could belong to two expansions; each
went where its part of the world comes in (notes in the codex). The Airship goes with Ships & Sea Monsters.

**How to test**: nothing to do differently; play a fight or two. The shelf is empty until Dice & Destiny is released.

### Local session, 2026-10-12: clearing the decks for the expansions (Anton's plan) — branch `prep/clear-the-decks`

Anton's expansion plan (`docs/EXPANSIONS.md`, saved word for word) asked for a clear-out before the expansions
begin: no friends' build, no Player2 AI writer, no letters mode, no code kept alive for old saves, and faster tools.
World Variety, which was finished, went to `main` first.

**What is different when you play**
- **Every word is the game's own.** The Player2 AI writer is gone: no AI settings, no "AI online" in the corner, no
  Player2 test on the title screen, no energy spent. Everything it used to write now comes from the game's own words,
  and where those were thin they were filled out after reading hundreds of samples: backstories (more beginnings, a
  turning point in a life, more endings, three different lines for each background), each kind of dungeon level
  (eight descriptions instead of three), the histories of magic things (23 instead of 5) and their names, and every
  kind of work you are offered (titles, and four to six ways of asking for each). The death screen now has a real
  obituary of its own, a few sentences about who you were and how it ended (it used to come only from the AI), and
  it is kept in the Legends book.
- **Pictures are the only look.** The Graphics setting (Pictures / Letters) is gone. If a computer cannot start the
  picture renderer, the game now says so plainly (update the graphics driver) instead of falling back to letters.
  The map legend (k) now shows the maps' own pictures beside each name.
- **Small fixes**: a woman to be killed was called "a man" by the one asking; raiders came "down out of about 54
  miles"; looking at a townsperson told you to walk into them to talk (it is t now, since walking only squeezes past).
- **Start a new world**: saves from before today are refused with the usual friendly message (the files are left
  alone). From now on any update may do this; Anton said he does not mind.
- **Friends get the game from GitHub**: the page's front is now `README.md` (what the game is, Code → Download ZIP,
  double-click `Play.bat`, how to update, the keys, the credits). `Build_For_Friends.bat` and the `.exe` are gone.

**Removed** (so nothing old holds the expansions back): `Build_For_Friends.bat`, `tools/build_friends.py`,
`realmwalker.spec`, PyInstaller, the icon only the `.exe` used, the packaged-exe branches in `paths.py`, and (on
this PC, to the Recycle Bin) `dist/`, `Realmwalker.zip` and PyInstaller's `build/realmwalker/`; the Player2 writer
(`realmwalker/ai/`, `ai/prompts/`, the mock server, the Player2 test screen, the AI settings and debug log, the
corner status, the debug console's AI commands, the AI-only tests, autoplay's pretend-AI mode, httpx, `ai_style` in
`cultures.json`), tagged `before-ai-removal` on GitHub so it can come back one day; letters mode (the Graphics
setting, `ui/map_render.py`, the letters battle field, the block-letter title, every "no pictures" branch, and the
glyphs and colours on lands, ground, places and creatures that only letters used); the save migration chain and the
code for old saves and worlds (the "told" history and the factions made for worlds from before the lived ages, the
politics engine's history mode they used, packs put on characters from before packs were worn, companions' coin from
older saves). The progress log's entries from before version 1.0 moved to `docs/PROGRESS_ARCHIVE.md`.

**For working on the game**: `requirements-dev.txt` (pytest-xdist, pypdf, pypdfium2); the tests run in parallel
(`pytest -n auto`, about 2.5 minutes) and `pytest -n auto -m "not slow"` is a quick check (under 2 minutes);
headless tests draw every screen's pictures through a recording picture context; `tools/codex/extract.py` dumps the
three books' text to `build/codex/` for searching (never committed).

**Checked**: full test suite green (1,105 tests), autoplay OK, the window smoke test OK, and a fresh copy of the
repository set up and started the way a friend would.

**Decisions**: the creatures' front/back `rank` stays until Expansion 1 replaces it with roles (as the plan says);
the "Ideas parking lot" below is now mostly the expansion programme's job.

### Local session, 2026-10-11 (continued): varied, bigger, living towns (Anton's request) — branch `world-variety`

The second half of Anton's request of 2026-10-11: "make town generator way more varied ... Dwarven cities now look
like human cities inside a mountain (which is, for some reason, lighted during the day and dark during the night) made
of stone. Elven cities are human cities made of wood with green woods ... add way, way more variety to shapes, sizes,
and especially looks ... make towns generally bigger, more realistic ... way, way more citizens ... bumping into one no
longer starts the dialogue automatically ... make the time move independently of the player's moves, and make the NPC
move on their own."

**What is different when you play**
- **Every people builds its own way.** A town is laid out by its people (data/towns.json): Heartland and Highland
  towns grow along roads from a market square; Southron and Thalassian cities are planned blocks round a piazza; a
  Qasari city is a bazaar street from the gate to a great domed temple with a minaret, winding alleys and houses round
  courtyards with a fountain or a palm; a Khurgan horde camps in clan circles of felt tents round their own fires,
  joined by beaten tracks, with the khan's great white tent among its horse-tail standards in the middle and horse
  corrals beyond; a Volsk town has a log fort on a rise with an onion-domed church (gold and blue domes over a
  shingled roof), log houses and boardwalk streets outside; an Itzan city a stepped pyramid on a great plaza with round
  thatched huts; Northmen long turf-roofed halls (carved beasts' heads on the gables) round a mead hall inside an earth
  bank; halflings green grassy burrows with round doors and round windows; orcs huts in a stockade.
- **A dwarven hold is cut into the mountain.** Great doors in the rock face between two stone kings; a gatehouse with
  its racks of arms; the high road lined with carved ancestors up to the pillared great hall and its throne; galleries
  on three levels, joined by cross-ways; a market hall of pillars and stalls round a fountain; the forges along a
  channel of lava; a dark lake in a cave of its own with glowing mushrooms and mushroom farms; the mine beyond a chasm
  crossed by bridges, with its carts and rubble; homes down side passages. No sun reaches it: inside it is lit by its
  braziers, forges and lava, the same at noon as at midnight, and no rain falls there.
- **An elven hall is homes in giant trees** round a glowing moonwell, the hall the greatest tree of all; some trees
  are golden, lanterns hang in their branches.
- **Bigger towns, and great cities.** A hamlet's map is 96x64, a village 112x72, a town 144x96, a city 192x128; each
  world's biggest city (two in a large world) is a **great city**, three to five times the size of any other, on a map
  of 240x160, marked large on the world map with its name in big letters.
- **Things in towns.** Houses have rooms (hall, bedroom, kitchen; an inn's common room, guest rooms and cellar; a
  temple's nave; a smith's forge...) furnished for what they are for: beds, tables and stools, chairs, benches,
  shelves, bookcases, wardrobes, trunks, rugs, ovens, hearths, pews, altars, candles, thrones, banners, tapestries,
  weapon racks, armour stands, lecterns, cauldrons, baths. In the streets: lamp posts, torches, lanterns and braziers
  that light the night, fountains, statues, stalls and carpet stalls, standing stones, runestones, horse posts, carts,
  sledges, beehives, peat stacks... Nothing ever shuts anyone in: every door can be reached, every room walked into.
- **Many more people.** A hamlet has 8-14 people, a village 20-35, a town 50-110, a city 120-260, a great city 250-450,
  a hold 60-150, an elven hall 40-90. Twenty-one new trades: bakers, butchers, brewers, tailors, cobblers, potters,
  tanners, scribes, monks, soldiers, sailors, porters, children, elders, minstrels, preachers, pilgrims, town criers,
  bath-keepers, moneylenders and herders, each with their own greeting and their own past. Everyone sleeps in a real
  bed in a real house.
- **They live their day.** Everyone keeps the day of their trade: asleep at night, the baker up at four, at work by
  day, a meal at noon, the inn or the square of an evening, home to bed; guards walk their rounds (with lanterns at
  night), children play near home, elders sit in the square, the crier goes about the streets. They walk there along the
  streets, go in and out through doors, step round each other and round you, and two meeting in a doorway get past
  each other.
- **Time flows in towns.** On a town's map the clock runs by itself (six seconds of the world every half second) and
  people walk while you stand and watch. It stops whenever another screen is open; in the wild and underground time
  still waits for you. Settings, *Time in towns*: Flows, or Waits for you (the old way).
- **Walking into someone no longer talks to them**: you squeeze past (you swap places), unless they will not budge (a
  warden at a gate; someone asleep). To talk: stand beside them and press **t** or **Enter** (a short list if several
  are beside you), or click them. Walking to someone (a click) still talks when you reach them; walking elsewhere
  squeezes through a crowd.
- **More happening.** People say things as you pass, a few words over their heads: "Fresh bread!", "Hear ye, hear ye!"
  (the crier cries real news), "Can't catch me!", "Repent, the end is near!", "♪ Oh, the wind and the rain ♪". (Only
  with Text detail Normal or Rich.)
- **Each people dresses as they do.** Qasari in robes and turbans (the women veiled), their guards in lamellar with
  spired helms and curved swords; Khurgan in coats closed at the side with fur hats, their guards with bows; Volsk in
  kaftans and tall hats (the women in headscarves), their guards in scale with pointed helms and axes; Northmen in
  tunics, their guards in mail with nasal helms and round shields; Thalassians in draped tunics, their guards with
  crested bronze helms, breastplates and round shields; Itzan in white cotton, their guards in quilted armour with
  plumes and clubs; Highlanders in kilts and plaids with bonnets; Southrons in dark doublets, their guards with
  breastplates, morions and halberds. Children are drawn smaller.
- **Coming into a place** is told in its people's own words ("The road climbs to the gate of Uldum, cut into the cliff
  between two stone kings. Galleries run away into the dark, a brazier burning at every turning...").

**How to try it**: start a new world (the towns are made as you first walk into them, so an older world made this
session will do too). Walk into a big city and stand still a while: watch the streets. Press t beside someone. Find a
dwarven hold (on the map, a gate in a mountain) and go in at night. Settings has *Time in towns*.

**Decisions made**
- Towns are made by `realmwalker/world/towns/` (plan.py: streets, plots, buildings, rooms, furniture, every door
  reached; layouts.py: one plan per people); the old builder stays as a fallback. A town that cannot reach one of its
  buildings lays a path to it (a footbridge over a stream if need be), or does not build it.
- Townsfolk keep their full built-in description from the start (making one takes a tenth of a millisecond, so the
  "described only when first looked at" idea of the plan was not needed); the AI still writes only the people of note.
- Townsfolk positions are saved; their paths are not (they are found again). Save format unchanged since this
  morning (11).

**Checked**: full test suite green (1174 tests; new: tests/test_towns.py for every people's towns at every size, doors reached, nobody shut in, holds lit the same at noon and midnight, lamps lit at night; tests/test_townlife.py for days, walking, doorways, squeezing past, t to talk, the town clock, street calls, market days, a great city of 300 stepping in 7 ms), smoke test clean (new pictures: a city, a hold, an elven hall, the peoples view), autoplay OK in both AI modes.

**Later the same evening**
- **Every people has its towns.** Towns used to go to the best farmland first, so peoples of hard country (the Qasari of the deserts, the Khurgan of the steppe) were left with two or three; now each people gets a share for its lands (how much, and how good), and the rest go wherever is best. And when a realm founds a town in another people's country, it is mostly settled by the people of that country under a foreign lord (data/history.json peoples_change colonists: 0.3); before, every new town took its founder's people, and a century of history could turn most of the world Volsk.
- **Things happen in the streets**: on the holy day (Sunsday) the priests, acolytes and monks go in procession round the square in the morning, chanting; of an evening two drinkers may come to blows in the street until the watch comes running and pulls them apart.
- Flat roofs (Qasari, Itzan) have more on them: jars, rugs airing, water tanks, striped awnings, a warm mud-brick tone.
- Fixed: people jammed in a crowded house when someone slept across the way to the door (now you only swap with someone coming the other way or standing still, and homes are not put across passages); wardens at the gates of walled towns now hold their posts; a town made ahead of your arrival (for a job) is peopled on its own map.

- **L-shaped houses** in Heartland, Highland, Southron and Volsk towns: the house along the street and a wing behind it, a corner left open, a doorway between them, the roof turning the corner.

**Not done yet** (from the design): cross-shaped buildings.

### Local session, 2026-10-11: peoples, a land of extremes and wonders, a new world map (Anton's request) — branch `world-variety`

Anton asked for worlds of extremes (huge cities, burning deserts, glacial plains, epic ranges) with wonders of the
world; real-world-flavoured peoples with their own names, towns, dress, arms and laws, and far more names; bigger,
more varied, livelier towns where people move on their own and walking into someone no longer starts a talk; names
for the land's features in the language of the people nearby; clearer realm and culture views; and a world map that
is vivid, quick and comfortable to zoom and scroll. The design is `docs/WORLD_VARIETY.md`, the plan
`docs/superpowers/plans/2026-10-11-world-variety.md`. This session did the first three parts (peoples, the land and its
wonders, the world map); the towns and their people come next.

**What is different when you play**
- **Peoples.** Nine human peoples, each like a people of our world: Heartlanders (English), Northmen (Norse),
  Southrons (Italian, Iberian), Highlanders (Gaelic), Qasari (Arab, Persian), Khurgan (Mongol, Turkic), Volsk (Slavic),
  Thalassians (Greek, Byzantine) and Itzan (Maya, Aztec), beside elves, dwarves, halflings and orcs. Each lives where its
  kind of country is (deserts, steppe, fjords, jungle...), and each world calls them by its own name for them ("the
  Mirellans"). Their rulers have their own titles (Sultan, Khagan, Jarl, Knyaz, Basileus, Holy Lord), their realms
  their own names ("the Sultanate of...", "the Khaganate of...", "the Grand Principality of...", "the Basileia of...",
  "the Sun Throne of..."), their faiths their own gods. Over centuries a town ruled by another people may come to
  speak as they do, and the map of peoples is left where the history left it.
- **Names.** Hundreds of names for each people, and every world grows new ones from each people's own sounds, so two
  worlds do not share their people. Names follow their people's custom: Bjorn Haraldsson, Rashid ibn Tariq, Ivan
  Petrovich, Lady Agafya Chelinskaya of the Boyar House of Chelinsky, Fergus mac Aodh. Guilds, orders and companies
  ("the Pochteca of...", "the Crimson Gallowglass", "the Silk-Road Company", "the Eagle Knights of...") and relics
  ("the Obsidian Mirror", "the Hammer of the Eternal Sky") are named in their makers' manner.
- **The land.** Making a world has two new choices: *Land* (one continent, islands, two lands, a continent round an
  inland sea) and *Climate* (frozen, cold, mild, warm, hot, extreme), both "Any" by default. Every world now runs from
  a frozen north to a burning south: glaciers, tundra and taiga; farmland and forest; steppe, deserts and great sand
  seas, salt pans where lakes dried up, savanna, and jungle. One to four great ranges cross the land, their peaks up to
  8,850 m; tablelands end in cliffs; rivers cut red gorges through the dry uplands and fall where they meet a scarp;
  volcanoes stand on the ranges and on islands, and the land round them is ash and black rock. Every new land has its
  own ground, plants and pictures on foot (palms, acacias, jungle giants, cacti, termite hills, steam vents, salt
  crust, crevasses...), its own camping, hunting and foraging, and behaves like its nearest old land everywhere else.
- **Wonders of the world.** Every world has a dozen or more: the highest peak, volcanoes (one awake, with a lava lake),
  great falls, the long gorge, great cliffs, a salt pan, a lake that shines at night, oases, hot springs, the enchanted
  wood, a tree as big as a castle, stone arches, a sinkhole, a forest of stone, a wall of glacier ice and the drifting
  stones. Each is named by the people living nearest it ("Jabal Madat", "Haabreen", "Altan Rashaan", "the Mirror of the
  Sky"), drawn large on the map, has a close-up map of its own (the crater with its lava lake, the falls over the
  cliff, the oasis pool among palms, the hollow inside the great tree...), and is worth finding: experience and fame
  the first time. Some help a traveller: drink at an oasis, falls or hot springs; rest at the springs to heal faster
  and keep warm; camp sheltered under the great tree; and beware the enchanted wood, where it is easy to lose your
  way. The history remembers them: volcanoes erupt and bury towns, a hero first stands on the highest peak, pilgrims
  come to holy waters. The Legends book has a new page, *Wonders* (key 5).
- **The world map** is painted once, in the background, and then shown at any zoom: no more lag. It is brighter, with
  the climate in its colours (green wet country, gold steppe, red badlands, white salt and ice), the sea from turquoise
  shallows to deep blue, gorges, cliffs, palms, acacias, jungle, mesas and cinder cones drawn on it, the wonders drawn
  large, towns drawn in their people's manner (Norse longhouses, Qasari domes and minarets, Khurgan yurts, Volsk onion
  domes, white Thalassian towns, Itzan pyramids...), and the names of seas, ranges, deserts and forests written across
  them. On the map screen (m): the mouse wheel zooms where the pointer is, dragging moves the map, a click chooses a place
  and the side panel tells about it, Enter or a double click travels there (a single click no longer sets off).
  Views: **l** Land, **p** Realms (each realm in its colour with its name across it, vassals striped in their own
  colours, and a key listing the realms you know: who rules and how they feel about you), **c** Peoples (each people
  in its colour and name, the key telling who they are), **w** Weather. Click a realm or people in the key to pick it out.

**How to try it**: start a *New world* and choose *Land* and *Climate* (try Islands and Hot, or Extreme). Open the map
(m), zoom with the wheel, drag, press p and c. Find a wonder: the Legends book (n, then b) lists them under *Wonders*.

**Decisions made**
- Save format 11: worlds made before this are refused with the usual friendly message (Anton said old saves need not load).
- New lands each name the old land they behave like (biomes.json "family"); systems that ask "is this a desert?" ask
  the family, and tables kept per land use the land's own entry first.
- The overworld zoom steps are now 6, 12, 24, 36, 48 pixels a square (whole multiples of the painted map's grain, so
  pixels stay even).

**Checked**: full test suite green (new tests: tests/test_peoples.py, test_lands.py, test_world_map.py), smoke test
clean (screenshots of the new map), autoplay OK in both AI modes.

**Next**: the towns (sizes and great cities, each people's way of building, furniture and things in the streets,
dwarven holds lit by braziers and lava, elven tree homes), then their people (many more of them, walking about on
their own as time runs, bump to pass and t to talk).

### Local session, 2026-10-10: a world that has lived (Anton's request) — branch `world-history`

Anton asked: look through the code of Realmwalker and of Dwarf Fortress, work out how DF builds its worlds, and give
Realmwalker "the same kind of living world with long history and unique characters", as detailed and expansive as
DF's, better suited to the game if possible, without breaking anything.

**What Dwarf Fortress does (what was learned).** DF's program code is closed, but its folder holds two Legends
exports, complete histories of real worlds. A script read one of them (252 years): 54,301 people, 5,669 groups,
1,899 places, 10,704 artifacts and 532,414 events of 108 kinds. The heart of it: DF *lives* its history year by year
and the world you play is whatever is left; every person has a family and a life; wars hold named battles with named
dead; artifacts pass from hand to hand; monsters have lairs, kill people and are hunted by heroes; the years are
divided into named ages. What DF does badly for a game like ours: most of it is noise (100,000 "settled at a site"
lines), nothing guarantees a playable world, and little of it reaches you outside Legends mode. The full notes and the
design are in `docs/WORLD_HISTORY.md`.

**What is different when you play**
- **Making a world**: a new choice, *History*: Short (100 years), Normal (250), Long (500) or Epic (1000). While the
  world is made you watch the years go by ("The year 873 · 2,312 people of note · 4,880 things remembered") with the
  latest great event under it, and the towns appear on the map as they are founded (ruins show dark red). A medium
  world with 250 years takes a second or two; a large one with 1000 years about seven.
- **The years are really lived.** The old peoples (dwarven clans, elven realms) are older than the records. Men begin
  with a few old kingdoms. They found villages and towns that grow; a king gives each new town to a lord, raising new
  noble houses from knights and younger sons. Rulers marry (often into other houses, which binds them together), have
  children, die, and are followed by the custom of their people: the eldest son in the Heartland, the eldest child in
  the South, the most able kinsman in the North, the eldest of the clan among dwarves, the choice of the elders among
  elves. A child on a throne needs a regent, and some regents keep the throne. When a line dies out a great lord takes
  the crown, or the seat goes back to the king. Kings are counted (Aldric III). Vassals rebel; rich cities buy their
  freedom; lordships crown themselves; neighbours who hate each other go to war for a reason (land, a claim, the true
  faith, old wrongs) and every war has a name ("the War of the Broken Crown"). Battles are fought at real places by
  named commanders; the dead are remembered, and so is who killed them ("Lord X fell at the Battle of Greyford, slain
  by Sir Y"). Towns are besieged, taken, sacked, razed and rebuilt. Tribes raid and carry children off. Named beasts
  (dragons, trolls, ogres, giant spiders, dire wolves, great bears) take lairs and come down on the farms; heroes go
  after them and come back famous, or do not come back. Young adventurers set out from the towns, go into ruins, hunt
  outlaws and grow old. Churches have prophets and saints; heretics start cults that are hunted down. Smiths make named
  weapons and crowns that are inherited, taken from the dead, stolen, carried off by dragons and buried in barrows.
  Bards and chroniclers write songs and chronicles about it all. The ages are named ("the Age of Dragons", "the Golden
  Age of Ashmere"). A medium world ends with about 1,800 people of note and 2,000 remembered events.
- **Today is what was left.** Every ruin was once a real town, with a name, a founding, a peak, a holder and an end
  ("razed by the Red Jaw tribe in the War of the Ravens"). Every lord has real ancestors. Every barrow holds someone.
  The troll in the cave has killed people you can read about. The guilds, the knightly order, the mages' circle and the
  healers' guild were founded by real people for a reason (the healers after a real plague). The number of towns,
  villages, holds and halls is the same as before, so the game's balance is unchanged.
- **The Legends book**, like DF's Legends mode: press **n** (News and history) and then **b**, or on the title screen
  choose *Saved Worlds*, pick a world and press *Legends* (you can read a world's history without playing it). Every
  person, realm, place, war, beast, artifact, age, god and song has a page: who they were, their family, their deeds,
  and every event of their life in order. Every name on a page is a link (click it); Backspace goes back and ] forward;
  / searches; ← → choose what kind of thing to list.
- **The past in play**:
  - *Look* at a ruin, a barrow or a lonely tower: it says what it was and how it ended, whose tomb it is, who raised
    it. Close to a lair you see whose lair it is. *Look* at a town: when it was founded (and what stood there before)
    and the worst or greatest things that happened to it.
  - Ask townsfolk *"What should I know about this place?"*: they tell what they lived through ("I was there, twelve
    years ago: the dragon burned the lower town") or what everyone tells.
  - Rulers, lords and heroes you meet have their real histories as their backstory.
  - A hero of the history who calls a town home may be drinking at its inn, and can be hired like any traveller.
  - A named beast is the boss of its lair, by name. Kill it and the world remembers you did ("Anton slew Grubnak the
    Bone-Gnawer, the troll of the Black Cave"), with fame and thanks from the lands it troubled. The dead king in a
    barrow is that king, by name.
  - Towns near a named beast's lair offer work to kill it, by name, and tell you who it killed.
  - Old history books are copies of the world's real chronicles and songs.
  - The built-in chronicle is told age by age; with the AI on, the AI's chronicle, town descriptions and conversations
    are given the true history to draw on.
  - When towns change hands while you play, the history's record of who held what keeps up.
  - **The beasts go on**: while you play, a named beast still comes down on the farms near its lair now and then
    (you hear the news; the town is "beset by a beast" for a while).
  - **The land remembers**: the fields of the deadliest battles and the towns put to the sword are marked. *Look* at
    a battlefield and it says what was fought there and how many died; camp or walk there at night and the dead of
    that battle may come for you (with their own words).
  - **Blood feuds**: someone whose father, wife, brother or child was killed by a person still alive wants that
    person dead; their townsperson says so, and the assassination work they offer can be that vendetta, by name.
  - **Your background is rooted in the history**: a soldier marched in a real war under a real lord; a folk hero
    drove off a real beast or raiders that troubled their village; a noble's family holds its lands from a real
    lord; an acolyte was raised by a real priest.
  - **Lost treasures can be found**: an artifact the Legends book says lies in a ruin, a barrow or a lair is really
    there, in a locked chest on the deepest level. Open it and it is yours (a very rare magic item with its name and
    its story), and the world hears that you found it.
  - In the Legends book, people's pages also show their grandparents and who they fought beside and against.
  - Heroes and other people of note grow old and die while you play, as rulers already did (not the ones walking
    with you); when a hero people sing of dies, you hear of it.
  - **Your own past lives are in the Legends book**, first among the People ("Anton (your life, d. 1049)"), as DF
    keeps its adventurers: what they were, how and where they died, their titles, what the powers thought of them,
    what they killed, who walked with them, their deeds, what was said of them, and what the world remembers.
- **More names**: every people has two to three times as many names as before (so a thousand people of note are not
  all called Aldric).
- **Found by reading the Legends book, and fixed**:
  - An age called "the Long Peace" held five wars and two burning dragons. The ages are now named for what set them
    apart from the rest of *that* world's history: a burst of battles is an age of war, a time quieter than usual a
    peace, and the ordinary run of crowns and quarrels "the Age of Kings" or "the Age of" the realm that led it.
  - In 1000-year worlds the wars stopped for good after about year 700: the land had grown into a few great
    kingdoms whose capitals lay too far apart to "reach" each other. Realms whose borders touch can now go to war
    (wars per century stay steady to the end; ordinary 250-year worlds have as many wars as before).
  - The news of a beast's attack could say "1 were killed", and was told only three ways (the game's rule is at
    least four); now five ways, and "one person".
  - Long names in the Legends book's lists end in "…" (the whole name shows when you point at it).
  - The death screen said "Killed: 3 wolfs" and "2 goblin boss"; now "3 wolves", "2 goblin bosses".
  - Causes of death read wrongly after "died": "King Guy I died drowned crossing a river in flood", "died devoured
    by the troll", "died burned as a heretic". They now read right both ways ("died in the jaws of the troll";
    "Died in 907, in a river in flood").

**How to see it**: double-click `Play.bat`, *New World*, set *History* (try Long), press Enter and watch the years go
by. In the game press **n**, then **b** for the Legends book. Walk to a ruin and press **l** (look). Ask an innkeeper
what you should know about the town.

**Decisions** (and why):
1. **Today's towns are "fated"; extra "doomed" places become the ruins.** The game's balance, quests and tests rely on
   today's world having a known shape (DF itself throws away worlds that come out wrong, which a game cannot do). The
   simulation still decides who founds every place, who holds it, what happens to it and how the doomed ones end;
   every line of history really happened in it.
2. **Only what a chronicler would remember is written down** (about 8 events a year in a medium world, not DF's
   2,000), and only people of note are people; commoners are numbers, as in DF.
3. **Dwarves and elves keep to their own**: no human king holds a dwarven hold for long, and the elder peoples do not
   take human towns (they burn and loot and go home).
4. **Monsters use creatures that already have pictures and stat blocks**; every world keeps a few named beasts alive
   (and one dragon asleep).
5. **Old worlds keep their old history** (they still load and play); a new world gets the lived one. No save format
   change was needed: every new field is optional.
6. Years before year 1 are written "B.R." (Before the Reckoning).
7. **Ages are named against the world's own usual**, not fixed numbers (`data/history.json` "eras": `stand_out`,
   `quiet`, `least`), because every world has its own background level of war.

**Known issues / not yet**
- Worlds made before this version keep their shorter told history; their Legends book works but has little in it.
- The Legends book is words only: no map of where things happened yet.

**Friends' readme**: describes the lived history and the Legends book, and no longer says combat is in ranks.

**Checked** (on the final version): all 1108 tests pass (1 skipped, as before); the window smoke test visits every
screen, the Legends book included, and closes with "0 recovered errors"; the autoplay bot played about 3000 turns
with the AI off and 3000 with the pretend AI (it made worlds, lived and died several times and opened the Legends book
about 350 times) with no errors, and the history checks held: everything the history names exists, every lair has a
living beast, and replaying who held what gives today's map. Making a world takes under a second (small, 100 years),
one to two seconds (medium, 250) and about eight (large, 1000).

### Local session, 2026-10-10: sound and music (Anton's request) — branch `sound`

Anton asked for "basic and satisfying sounds for button pressing, some combat sounds, sounds for menus", music or a
very simple way to add music (combat, travel in different lands and cities, rest, boss fights...), all of it pleasant,
even in level and never irritating, and sound settings.

**What is different when you play**
- **Music.** The game comes with eight medieval tunes by RandomMind (public domain): one for the title screen, one
  for the road, two for towns, one for inns, one for fights, a short one when you win a fight and one when you lose.
  The music follows you: the road's tune fades into the town's as you walk in, an inn has its own, a fight cuts in
  quickly and the road's tune picks up where it left off afterwards. On the road and in towns there are quiet
  stretches between tunes, so it never drones on. Under the ground and at camp it is quiet (until you add music).
- **Your own music, by dropping files in folders.** The first time the game starts it makes a folder called `music`
  in the game's folder (for you: `D:\Project Dawn\music`), with a folder for each moment: `title`, `travel`, `town`,
  `tavern`, `dungeon`, `rest`, `combat`, `boss`, `victory`, `defeat`, `death`, and folders inside some of them for
  something more particular: `travel\forest`, `travel\desert` (every kind of land), `town\city`, `town\village`
  (every size), `dungeon\crypt`, `dungeon\cave` (every kind of place below), `combat\undead`, `combat\beasts`,
  `combat\people`, `combat\monsters`, `boss\dragon`. Put .ogg, .mp3, .flac or .wav files in a folder and they play
  there; an empty folder borrows from the one above it (forest from travel), and a boss fight with no boss music
  plays the fight music. Your music for a moment replaces the game's own. Every tune is measured the first time it
  plays and evened out to the same loudness, so a loud MP3 and a quiet one sound alike. A README.txt in the folder
  explains it all.
- **Settings has sound.** Esc, Settings: *Volume* (everything), *Music*, *Sound effects*, *Interface sounds* (each 0 to
  100%, with a bar, and you hear the new level as you change it), *Sound in the background* (keep playing while
  another window is in front), and *Your music*: a page listing every moment, how many tunes it has (yours or the
  game's), what plays now, **Listen** to hear any moment's music, **Open the folder** (opens it in Explorer), and
  **Look for new music** after adding files. **Ctrl M** anywhere turns all sound off and on.
- **Interface sounds**, soft and short: a quiet wooden tick as the choice moves down a list, a click for buttons, a
  book opening and closing for screens, pages turning for the journal, chronicle, help and spells, leather for the
  pack, paper unfolding for the map and notice boards, a dull thud for "that cannot be done". Only one sound answers
  each key or click (a click that opens a screen sounds like the screen opening, not both), and walking never clicks.
- **The world**: coins whenever money changes hands (buying, selling, pay, rewards), cloth and armour when gear goes on
  or off, a harp when someone goes up a level, two plucked notes when work is written in your journal and a little
  run when it is paid, footsteps on the stairs going down or up, a chest's lid, a lock giving, a trap snapping, a fire
  catching at camp, a low drum when trouble meets you on the road, and a gong when you die.
- **Fights**: blades drawn as a fight opens (beasts growl, the dead moan), a swing for every blow, a bow's twang, a
  thrown knife's whistle, bites, spells, and the blow landing *when the picture shows it landing*: cuts, stabs, thuds,
  a heavier thud on a critical, armour ringing when it turns a blow, fire, frost, thunder, acid, webs, a dull thud
  for dark or holy magic, a chime when wounds close, and the fall of whoever goes down.
- **Even and gentle**: every effect was trimmed so it starts the instant you press, softened where it was harsh (coins,
  blades, paper), and brought to the same loudness (a sharp peak is limited, not clipped); each sound plays slightly
  higher or lower each time, so nothing heard often sounds the same twice; the music is all at one quiet, even level.

**How to see it**: just play; the title music starts with the game. Esc, Settings for the volumes and *Your music*.
To add music: Settings, Your music, *Open the folder*, drop files into (say) `combat`, press *Look for new music*,
choose Combat and *Listen*.

**Sources** (all public domain, CC0): Kenney's RPG Audio, Interface Sounds and Impact Sounds; artisticdude's RPG
Sound Pack and rubberduck's 80 and 100 CC0 sound effects (OpenGameArt); RandomMind's medieval music. The bow, the
harp, the journal's notes, the chimes and the drum were made for the game. `tools/build_sounds.py` downloads,
shapes and evens them all; credits are in `assets/sounds/CREDITS.txt` and `assets/music/CREDITS.txt` and the
friends' readme.

**Decisions**: the music folder sits next to the game, where it is easy to find (inside the friends' build: next to
Realmwalker.exe), not in %APPDATA%. Interface sounds have their own volume, as some players dislike clicks. The
dungeon, camp and boss moods ship without music: quiet underground felt right for a grim game, and they are the first
places to put your own. Sound never stops the game: no sound card, or a broken file, and it plays on in silence
(a bad tune is skipped and written to the log).

**For later**: more moods are one entry in `data/music.json` and one line where a screen says which mood it wants
(night on the road, a siege, a wedding...). Footsteps on the map were left out on purpose (heard thousands of times).

**Checked**: the whole test suite (new: `tests/test_audio.py`: every file there, readable and at one loudness, every
sound the code asks for exists, the loudness measure against the broadcast standard's own test tone, moods falling
back, your tunes replacing the game's, crossfades, picking up where it left off, once-only tunes, pauses, broken
files skipped, the Settings and Music pages, a whole fight's sounds); autoplay in both AI modes (it now also fails on
any unknown sound or mood); the smoke test in a window, which now plays all its sound to SDL's silent "dummy" device
and fails if the device, an effect or the title music does not work. I cannot hear, so the sounds were chosen by
their makers' descriptions and by measuring them (length, brightness, loudness, spectrum pictures), and a whole
smoke-test session was recorded to a file through SDL and measured: no clipping, no clicks, music about 5-8 dB under
the blows of a fight, the music changing at the right moments. **Your ears are the real test**: if anything grates,
tell me which (the Settings page names each kind), and its volume is one number in `data/sounds.json`.

### Local session, 2026-10-10: choose how you look (Anton's request) — branch `looks`

Anton asked for character creation to be upgraded visually, with separate choices for hair colour, hair style, beard
and the rest, for every people, and for it to keep working when more races are added.

**What is different when you play**
- **A new step in character creation, "Looks"** (step 7, after "Who you are"). Every choice is a row: arrow keys,
  or click the ◄ ► arrows, or the mouse wheel over a row; colours have a swatch beside them; **R** gives a whole new
  random look. As you choose, the panel on the left shows your face large and bare-headed, and the right shows the
  whole figure in the gear you set out with. Underneath, "How others see you" is written from what you chose.
- **The choices**: build (slight, average, heavy: the figure really is narrower or broader), skin, eyes (eleven
  colours), fourteen hair styles (cropped, short, receding, curly, shaggy, long, tied back, braids, one long plait,
  pinned up, topknot, a crest, two tails, shaven) in eleven colours, nine kinds of beard (stubble, moustache, goatee,
  side-whiskers, short, full, long, forked, braided) with their own colour, the marks of your people (an elf's ears:
  long, swept back or short; a half-orc's tusks: small, heavy or filed down), a mark or scar (freckles, a scar down
  the cheek, through an eye or through the brow, an eyepatch, a broken nose, a gold earring, an old burn), paint or
  tattoos (a band across the eyes, tattooed cheeks, chin stripes, a mark on the brow) in six colours, and the colour
  of your clothes and of your cloak and hood.
- **Each people has its own range**: elves are slight or average, with silver and violet eyes possible and no beards;
  dwarves average or heavy, nearly all the men bearded and the women allowed one; half-orcs with green and grey skins,
  red or amber eyes, tusks, more often scarred and painted.
- **The first three steps show you large too**: the whole figure on the right changes as you browse peoples, callings
  and pasts.
- **Everyone else uses the same looks**: townsfolk, bandits, guards and companions are read from the words that
  describe them ("a heavy man with a braided red beard and a scar through one eye" is drawn exactly so), so towns are
  full of different builds, beards, scars and paint. A companion keeps the face they had in town.

**How to see it**: start a new character (New World or New Character on the title screen) and go to step 7. Townsfolk
look different in any town.

**For peoples to come** (Anton: "there will be more races added in the future"): a people added to data/races.json
and nothing else can be made and drawn at once (human looks, drawn on a human body). To give it its own:
1. data/appearance.json looks/races: what it may have (any list left out comes from `_default`), and its features.
2. data/sprites.json figures: `skins` (real colours: any colour works now, red or blue included), and `bodies` with
   its proportions; then rebuild the tiles (`tools/build_tiles.py`).
3. Horns (curled, straight, small) and a tail are already drawn, waiting for a people with them (a tiefling would need
   only data). A new kind of feature needs a few lines in tools/figure_gear.py `feature()`.
tests/test_looks.py checks every look of every people has its picture and colour, and makes and draws a made-up
people that exists only in races.json.

**Saves**: format 10. Old characters load and are drawn from their words as before (a little more varied now).

**Checked**: the whole test suite (new: `tests/test_looks.py`), the smoke test in a window (its tour now presses Enter
once more for the new step), the autoplay bot in both AI modes, screenshots of the Looks step for every people at
1920x1000 and 1024x640.

### Local session, 2026-10-09: every item does something (Anton's request) — branch `useful-items`

Anton noticed that many things from the rulebooks (spell foci, backpacks, blankets...) did nothing, and asked for every
item to have a logical, balanced use, a backpack to be worn for more carrying, and some more small items with uses of
their own. A survey of all the items found about thirty that did nothing at all (backpack, sack, crowbar, rope,
grappling hook, shovel, hunting trap, whetstone, soap, smith's and carpenter's tools, the instruments, cards and dice,
the spell foci, the prayer book, incense, ink and quill, parchment, the signet ring, the insignia, the trophy, the
letters and papers, manacles, plain rings and amulets), and that the design's "condition wears with use and can be
repaired at a smithy or with tools" had never been built. Blankets and bedrolls already kept you warm in your sleep,
torches and lanterns already lit the dark, and the healing things already worked; those were left as they were.

**What each thing does now** (each item's card in the pack says it, and Enter uses it where that makes sense):
- **Carrying.** A new **Pack** slot on the back. A backpack worn there carries 15 lb more before you count as laden (a
  sack 5). Everyone starts with theirs on, companions too, and a character from an older save puts theirs on when
  loaded. In the shared pack, every member's backpack counts.
- **Wear and mending.** Every blow a weapon lands, and every blow armour, a shield or a helmet takes, may cost it a
  point of condition (masterwork wears slowest, crude fastest; magic not at all). Below 30 ("battered") a weapon hits
  1 worse and armour gives 1 less AC (as before). Measured: a front-line fighter's chain mail gets battered after about
  100 fights, the sword after about 200. A smith mends anything for a fee (as before). Now **tools mend** too, in an
  hour, the three most worn things at a time: smith's tools metal, carpenter's tools wood and bone, leatherworker's
  tools (new) leather and cloth, a needle and thread clothes. Untrained hands get things to "worn" at best; someone
  trained with the tool makes them as good as new. Mending looted gear also raises what it sells for.
- **A whetstone** sharpens every blade the party carries in 20 minutes: +1 damage with swords, axes and spears until the
  end of the next fight, and edges ground back to "worn" if they were worse.
- **Spell foci.** A holy symbol worn at the neck (or held) by a priest, a crystal focus held by a wizard, or a component
  pouch carried by a wizard: +1 to spell attacks and to the DC of their spells. Priests start with the symbol at the
  neck and hedge mages with the crystal in hand.
- **The prayer book.** Pray from it for an hour, once a day: it steadies whoever prays (+1 to Wisdom saves for 12
  hours), and gives a priest back spent prayers as a wizard's Arcane Recovery does. With incense burning, the whole
  party is steadied. Devout companions approve.
- **Ink, quill and parchment.** A caster can write one of their spells out as a scroll (Spells screen, w): two hours a
  spell level, a sheet of parchment, costly inks (25 gold crowns for a first-level spell, 100 for a second, 225 for a
  third) and one of the day's spell slots; an Arcana check (Religion for a priest). Anyone can read the scroll once in
  a fight. It always costs more than the scroll sells for.
- **Things that impress.** A signet ring (now worn on the ring finger) and a scroll of pedigree: lords and the high-born
  think better of you. A holy symbol worn: priests do. A guild letter: shopkeepers, smiths and traders do. An old
  soldier's insignia: guards do, and a patrol of soldiers or deserters on the road is easier to talk past. A trophy at
  the neck: +1 Intimidation. A plain ring, an amulet or a signet ring worn makes you look a little better off. The best
  of each kind counts, not all of them.
- **At camp.** Snares (new) or a hunting trap set before you sleep may hold something in the morning (a Survival check;
  snares take only small game, the trap anything; hunting laws apply). An evening of music, cards or dice (v) lifts
  every companion's loyalty, once a day (music played well more than a game), as far as content (70) but never to
  devoted: devotion is still earned by deeds. A string of bells (new) round the camp
  means nobody is caught asleep. A shovel digs a shelter in half the time, with less to go wrong, and makes a snow-hole
  in the snow. Cook's utensils make food go further at a fire (a stew: 15% more, 30% with a trained cook) and warm you.
  Soap: washing with it takes all the dirt off and washes open wounds clean (one bar a wash).
- **Locks.** A crowbar forces locked doors and chests with advantage, and the crack is heard only close by.
- **Prisoners.** Prisoners you lead to the watch now really can slip away in the night, as the game always said: one
  in five each night if their hands are tied with a belt, one in twenty-five with rope, never in manacles (one pair
  each).
- **On the road.** Navigator's tools (new) help you keep your bearings off the road in fog, storm and dark (+4, more if
  trained). A spyglass (new, dear) sees further across open land by day and spots trouble on the road sooner. New road
  events and new ways through old ones: rope across a flooded ford, a crowbar under a stuck cart, a shovel under a
  burnt farm's hearth, a grappling hook over a shut town wall at night (quieter than climbing), and three new
  meetings: someone fallen into a ravine (lower a rope), a rockfall across a mountain path (dig through, lever it
  aside, climb, or go round) and an old well with something at the bottom (climb down on a rope, or fish with a hook).
- **At the inn.** Playing for coin with an instrument is better, much better if you were taught it. Dice of your own,
  if you are trained with dice, throw 1 better; with playing cards you can play cards for money, where Insight counts
  more than luck.
- **Thrown in a fight** (Item menu, then aim at a square): a flask of oil (fire, 2d4, and it burns there a round), holy
  water (new: 2d6 radiant, only to the walking dead) and alchemist's fire (new: fire, 2d6, burning two rounds). A
  Dexterity save halves it; the DC is the thrower's (8 + proficiency + Dexterity).
- **Smaller fixes.** Rings and amulets (magic ones too) can now be sold: no shop would buy them before. They show under
  the Gear tab. The Item menu in a fight no longer lists things that cannot be used there (books, poppy milk, herbs).
  A tallow candle burns four hours instead of one (small light, long-lasting). Things with no use from the pack say
  where they are used (the tent: pitch it at camp; the tinderbox: lights the fire...).
- **Shops.** Acolytes in town and city temples keep a stall: holy symbols, prayer books, incense, candles, holy water.
  General stores now stock snares, bells, needles, cook's utensils, dice, cards, ink and parchment, navigator's tools, a
  spyglass, leatherworker's and carpenter's tools and instruments; smiths sell smith's tools, crowbars, manacles,
  grappling hooks and shovels; apothecaries alchemist's fire.

**How to see it**: start a new character (or load one: the backpack goes on by itself) and open the pack (i): every
card says what the thing does. Camp (r): m now sharpens and mends as well as makes, p sets snares, v passes the evening.
Spells screen (S): w writes a scroll. In a fight, Item lists flasks to throw.

**Saves**: nothing new is stored that an older save lacks, so old saves load as they are.

**How it was checked**: the whole test suite, with a new file of tests for every use above (`tests/test_gear.py`); the
autoplay bot in both AI modes; the balance numbers; a scripted run of 200 fights measuring how fast gear wears.

**Assumptions made without asking**: the numbers (a backpack +15 lb, a sack +5, +1 from a focus, a whetstone's +1 until
the next fight, how fast gear wears, how often prisoners slip away) are my choice of "balanced": easy to change in
`data/items.json` ("upkeep") if they feel wrong. Spell foci give a bonus rather than being required (in the rulebook a
caster without one cannot cast spells with material parts; that would only ever have taken spells away). The new items
borrow existing pictures (snares look like the hunting trap, the spyglass like a wand, holy water like a potion).

### Local session, 2026-10-06: combat on a grid, as in D&D (Anton's request) — branch `grid-combat`

Anton asked for a complete revamp of combat for 1.0, closer to real D&D, because the two ranks would stop making
sense once more spells are added: a grid both sides move on, things on it that block sight, a separate battle view
with a figure for everyone on a battlefield that looks like the place the fight started (a dungeon floor in a
dungeon, a forest in a forest, the inside of a house in a town, a keep inside a keep), effects for attacks, spells,
explosions and areas, enemies placed where they would really be (across the field usually, all around you when you
are caught unawares), and the party's starting places set on the party screen. Grid size, the rules on it, areas,
terrain, range and opportunity attacks were left to us. This replaces the design's two ranks (section 6).

**How fights work now** (the Player's Handbook's rules, as far as they go):
- **The grid.** Five-foot squares. Everyone moves up to their speed in a turn (30 feet is six squares), before,
  after or between the other things they do. Diagonals count as five feet, as in the book. Mud, brush, shallow
  water, deep snow, rubble and webs cost double. Large creatures (ogres, trolls, bears, dragons) take two squares by
  two and cannot squeeze through a one-square gap. Closed doors open as you walk through.
- **A turn**: movement, one action, one bonus action (if something gives you one), one reaction a round. Actions:
  Attack (with Extra Attack, two swings with walking between them), Cast a Spell, Dash, Disengage, Dodge, Help,
  Hide, Shove (knock down or push five feet), Grapple, use an item, Parley, Surrender. You leave the fight by walking
  off the edge of the field. Bonus actions: Second Wind, Cunning Action (Dash, Disengage or Hide), an off-hand strike
  with two light weapons, Healing Word, Misty Step, Spiritual Weapon, Shield of Faith, a thief's Fast Hands.
- **Reach and range.** A sword reaches the squares around you, a glaive or a pike two away. Bows, crossbows,
  slings and thrown weapons have their ranges (shooting past the near range, or with an enemy beside you, is at
  disadvantage). Spells have their real ranges.
- **Flanking** (the Dungeon Master's Guide's rule, added 2026-10-06 at Anton's asking): two on opposite sides of an
  enemy (a line between the centres of their squares runs through opposite sides or corners of its space), both
  beside it, both able to see it and neither helpless, have advantage on melee attacks against it. It works for the
  enemy too, and the enemy walks round you to get it. Pointing at an enemy marks the squares you could flank it from
  with gold diamonds.
- **Advantage and disadvantage** as in the book: helped, hidden or unseen attackers, targets that are prone (close
  in: advantage; further off: disadvantage), restrained, stunned, paralysed or asleep, dodging, marked by Guiding
  Bolt, pack tactics, flanking; the attacker prone, frightened, poisoned, blinded, restrained, badly exhausted, in
  armour they are not trained for, shooting at long range or with an enemy beside them, in the dark, in the rain with
  a bow, small with a heavy weapon, a monster that hates the sun out in daylight, a knight holding the line, a friend's
  shield (Protection). Saves: Dodge helps against fire and other Dexterity saves; being restrained hurts them;
  heavy exhaustion hurts all saves.
- **Opportunity attacks**: walking out of an enemy's reach gives it a free blow, unless you Disengage. The path you
  point at shows a red mark where that would happen.
- **Sight and cover** by the Dungeon Master's Guide rule (lines from the corners of your square to the corners of
  theirs): walls, tree trunks and closed doors block sight; low walls, fences, tables, boulders, carts and other
  people give half cover (+2 to AC and Dexterity saves); peering round a corner gives three-quarters (+5).
- **Light**: daylight, dusk, night, torchlight (the one carrying the party's torch lights the squares round them),
  hearths and campfires, burning ground. Striking what you cannot see is at disadvantage, and being unseen gives
  advantage; darkvision sees in the dark. You can Hide in brush, behind cover or in darkness.
- **Spells with real areas**: Fireball's 20-foot sphere, Burning Hands' and Cone of Cold's cones, Lightning Bolt's
  line, Thunderwave's cube (it throws people ten feet), Sleep, Web (a sticky zone that holds and slows), Ice Storm
  (ice underfoot afterwards), Flame Strike's column, Spirit Guardians (a burning ring round the priest), Spiritual
  Weapon (a floating mace that strikes each turn), Guardian of Faith (a guardian on the field). **Areas catch friend
  and foe alike** (an evoker's Sculpt Spells spares friends). Fire sets dry grass, brush and straw burning.
  **Concentration**: Bless, Web, Hold Person, Hold Monster, Shield of Faith and Spirit Guardians end if the caster
  is hurt and fails a Constitution save, or casts another such spell. Shield is a reaction, cast by itself when it
  would turn a blow. Every spell's range, area and casting time is written in `data/spells.json`, so more spells can
  be added without changing the rules.
- **Down and dying**: at 0 hit points a party member falls and makes death saving throws each turn (three
  successes and they are stable, three failures and they die; a natural 20 brings them round). Blows on someone
  down count as failures; a blow taking a whole life's worth below nothing kills outright. Help, a healer's kit or a
  healing spell saves them.
- **Every path's powers**, several of them never played before: Protection (a shield raised for a friend), the
  knight's Hold the Line and Rallying Cry, the cutthroat's Assassinate, the thief's Fast Hands, Sculpt Spells and
  Empowered Evocation, the abjurer's Arcane Ward (and Projected Ward), Guided Strike, Indomitable, Divine
  Intervention. Monsters: pack tactics, Nimble Escape (goblins hit and slip away), Aggressive (orcs and gnolls close
  in fast), the dragon's fire breath as a 30-foot cone, regeneration, paralysing claws, trips, poison. **Enemy
  casters cast** from the same spell list as the party, with their own save DC and slots (`data/creatures.json`:
  `spells`, `spellcasting`): cult fanatics raise a spiritual weapon, hold the strongest of you, command and wither;
  acolytes bless their band and heal it.
- **The enemy thinks on the grid**: it weighs every square it can reach and every way of hitting from there (the
  chance to hit, the damage, finishing someone, the free blows it would take, cover for archers), so archers keep
  their distance and shoot from cover, wolves close in together, the beaten run for the edge, and a dragon breathes
  where it catches the most of you. A fight neither side can get at (a gulf, a locked door) breaks off after three
  quiet rounds.

**Where it happens.** On a close-up map the battlefield is cut out of that very map around you and the ones you
fight: the dungeon's walls, doors and pillars, the street with its carts and barrels, the inside of the inn with
its tables, beds and hearth (no roof, so you can see in), a keep's halls. Everyone stands where they really stood.
On the road the field is laid out from the land: its ground, its trees, brush and stones (thick in a forest, few on
the plains), the road itself if you are on it, a stream or a river with a ford, the campfire and bedrolls if they
fell on your camp. **Where the enemy starts**: across the field in a line when both sides see each other (archers
and casters behind, at a distance that depends on the land and the light), spread wide to flank you if they are a
pack, in front and behind on the road if they are robbers, bunched up and taken by surprise if you ambushed them,
and all round you if they caught you unawares or asleep.

**The battle order** (party screen, p, then f): a block of five squares by five, the front row towards the enemy.
Click someone and then a square (or 1-5, Tab and the arrow keys); whoever stood there takes their place. By default
fighters are in front, priests and rogues behind them, wizards at the back. On a cut-out map the block is set with
you where you stood, turned to face the enemy, and squeezed into whatever room there is. (Anton suggested nine by
nine "for example"; five by five holds five people in any line, column, wedge or spread-out shape, and still fits in
a dungeon room.)

**The battle screen.** The field is drawn with the same tiles and light as the close-up maps, with a faint grid of
squares. Everyone is a figure on their squares (two by two for the large), with a health bar; the one whose turn it
is stands in a gold ring. **Click a square** to walk there: where you can walk this turn is outlined, and pointing at
a square shows the path and what it costs in feet. **Click an enemy** to walk up and strike with the best weapon
that reaches; pointing at it shows your chance to hit and why (cover, long range, advantage), and the squares it
can strike. The right column shows the one acting (health, action, bonus action, reaction, feet of movement left,
what spell they are holding) and the battle log; the action bar is along the bottom. Aiming an area spell lights up
the squares it would fill, says whom it would catch, and asks first if it would catch friends. Effects: people walk
their paths, lunge, arrows, bolts and javelins fly, rays and beams, magic missiles, a fireball's bead and its blast
over every square, cones and lines of fire, frost and lightning, a thunderclap's ring, webs, flames on the ground,
ice, the spirits wheeling round a priest, hits that flash and shake, the damage rising off the wounded, saves, the
fallen. Enemies nobody can see are dark shapes. Mouse wheel or + and - zoom; a big field follows whoever is acting.
**z** lets the game play the current character's turn; **e** or Space ends it. In letters mode the field is drawn in
letters (two to a square) and everything works with the keys.

**Settings** (at the end of the list): **Companions in a fight**: you command them (as before), or they fight by
themselves and you play only your own character.

**How it was checked**: the whole test suite, with new tests for the grid's geometry (distances, cover, sight,
areas, paths), the turn and its actions, every spell's aiming, concentration, death saves, the new powers, the
enemy's tactics, the battlefields (a dungeon fight fought in the dungeon you stood in, a fight in a house in the
house, a road fight on the road, a forest fight among trees, an ambushed camp surrounded), the battle order, the
screen's keys and mouse; the balance numbers (fights are about as dangerous as before: two wolves against a lone
level-1 fighter now lose 25% of the time where they lost 35%, mostly because Second Wind is correctly a bonus action);
a scripted run of 150 fights on real battlefields (no errors, no fight left hanging, turns under a third of a
second); the autoplay bot in both AI modes; the smoke test and screenshots of fights in a dungeon, a forest and a
town, every kind of spell effect, the battle order screen and the letters look, in a real window.

**Saves**: old saves load (the battle order starts as the usual one for each class). Nothing else in the save
changed.

**Fixed afterwards (same day)**: the pack failed to draw the card of a magic thing that glows (it borrowed a picture
from the battle screen under a name that had changed with the new battle screen); a test now draws the pack with
glowing things in it. Then a general check: the whole test suite, the autoplay bot on eight different worlds (six
with the AI off, two with the stand-in AI), a sweep that draws every screen with a party of five, magic things of
every kind, wounds and spells, at three window sizes, with every item and tab chosen, and 200 scripted fights.
Nothing else was broken. Flanking was added (above), with Dodge helping Dexterity saves, heavy exhaustion hurting
saves, and an attack from right beside someone lying down having advantage.

**Known issues / ideas for later**: figures face you and do not turn; there is no height (cliffs, stairs as high
ground) and no flying; Ready an action is not there; a fight in a dungeon is cut from the part of the map around you
(a band further off comes on from the field's edge); opportunity attacks and Shield are taken automatically; only
the cult fanatic and the acolyte have spells so far (more casters are a matter of data).

### Local session, 2026-10-03: version 1.0 — pictures and a new interface (Anton's request) — branch `graphics-ui`

Anton asked for the last two big updates before 1.0: graphics ("more detailed, informative, beautiful", simple
animations that are not irritating, a better-looking world, characters and townsfolk) and a full interface overhaul
(the inventory, fights without animation, too many walls of text), plus a button to delete a world, no Shift keys,
and play with the mouse alone. After a first look he added four wishes: figures less goofy ("pixel-arty, like the
new Steam Dwarf Fortress, sharp but pixelated"), a world map that is more stylised and sharper ("paper-style? more
pixel-style?"), towns that are less samey with doors you can find, and rare things whose look is designed (by the AI,
if it is not too hard). Then: finish, polish, playtest, and bring the handoff files to the state of 1.0.

**The game now draws pictures.** Every screen still works in letters (Settings → Graphics → Letters, and the tests
and the autoplay bot can run that way), but by default:
- **A picture engine beside the text grid** (`ui/gfx`): each frame is layers of text cells and pictures drawn by the
  GPU (tcod's SDL renderer). Tiles from the public-domain Dungeon Crawl set (CC0), toned darker, plus everything drawn
  in code (`tools/build_tiles.py` builds `assets/tiles`; `tools/tile_art.py`, `tools/figure_art.py`,
  `tools/figure_gear.py`). Fonts: Cinzel, EB Garamond, Grenze Gotisch (OFL). `data/sprites.json` says what shows what.
- **People are pixel-art figures** (32x32, sharp pixels at any size): a body for each race and sex, dressed layer by
  layer: shirts, tunics, robes, dresses, coats; padded, leather, studded, hide, chain, scale, splint and plate; hats,
  hoods, helmets, crowns; cloaks; hair and beards in eight and five styles; 30-odd weapons, torches, lanterns, books;
  shields in five shapes with sixteen devices. The player and companions wear what they really wear, in the colours
  of those very things; townsfolk dress for their trade; bandits, guards and cultists for theirs. Skin, hair and beard
  come from the words that describe a person ("straw-coloured hair", "a pale face"). Conversations show a head-and-
  shoulders portrait.
- **Rare things have their own look**: a magic item gets a metal, a cloth colour, a device and maybe a faint glow,
  from the words in its name and story and from its powers (a fire-warding blade glows red, a raven's cloak is
  black). When the AI names the item (task MAGIC_ITEM) it may choose the look again, only from fixed lists; a word
  not on them is dropped, never an error. Figures wear and hold rare things in those colours, and the inventory card
  shows a rare weapon or shield as it was made.
- **The overworld and world map are a pixel map on parchment**: painted in "map pixels" and enlarged by whole
  numbers, colours printed flat on the paper, hills shaded in dithered steps, an ink line along every coast with
  ripple lines out to sea, blue rivers, dashed roads, pixel mountains, hills and trees with ink outlines, towns with
  names, fog over what you have not seen, realms hatched in their colours with dashed borders, the route dotted.
- **Close-up maps in tiles with light** (day, dusk, night, torches, hearths), soft edges of sight, water that
  shimmers, people who glide from square to square, mouse-wheel zoom. Local maps are laid out for square tiles.
- **Towns**: every building is drawn from what it is and where: thatch, shingle, tile, slate, turf or stone roofs in
  several forms (along the house, gable end to the street, hipped, an inn's cross gable, a temple's tower and spire,
  a keep's battlements and turrets), chimneys with smoke, dormers; plaster and timber, brick, stone or log front
  walls with windows and shutters. A door in the front wall is drawn as a door (a striped awning over a shop's, barn
  doors on a stable, an arch on a temple); a door on another side shows as a gap in the eaves. Windows glow at
  night. New towns put doors in front when they can, and barrels, crates, woodpiles, haystacks, carts, troughs and
  flower boxes against the walls (never by a door or across a way through).
- **Weather you can see**: rain slanting with the wind, snow, fog, lightning in storms (only with animations on,
  never underground or indoors, and only over ground you have seen).
- **Companions** walk a step behind you on close-up maps and beside you on the road.

**The interface.** Textured panels, title plates, buttons with key badges, soft highlights, bars and gauges as
pictures. The main view has a side panel with portraits, health bars and status icons, a message log, and an action
bar along the bottom with every action as a button (click, or its key), right-click menus on the map ("what can I do
there"), click to walk, click a person to talk. The pack is rebuilt: the figure in its worn slots, things by kind
with pictures and tabs, an item card with buttons and a comparison with what you wear, double-click to use. Fights
happen on a stage with animation (lunges, arrows and spells in flight, hits, rising numbers, falls) and the order of
battle shown as figures. The character sheet shows the figure; the party list has faces and health bars; the Health
screen shows the body with each wound marked where it is (click one to choose it); the trade lists have pictures and
a card for the chosen thing; the Equipment screen shows the figure instead of the letter drawing. The title screen is
a painted night scene; **Saved Worlds** (W on the title screen) has **Delete** (to the Recycle
Bin on Windows). Settings: Graphics (pictures or letters), Animations (full, calm, off), map scales. Help covers the
mouse and the new keys.

**Keys without Shift**: Enter does the obvious thing where you stand, x leaves, a spells, b wash, o log, k legend,
+/- zoom; in the pack d drop, g give, u take off. Everything is also a button.

**Smaller fixes on the way**: walking somewhere goes round townsfolk (or up to them) instead of giving up; a bandit's
picture matches the name they go by, and no two in a band share one; prices in the pack fit their column; the help
screen showed stray "</title>" tags.

**How it was checked**: the whole test suite (new: `tests/test_graphics_ui.py` covers pictures for every terrain,
creature, item and outfit, the figures' data, every screen drawing with pictures, the painter's seams, a
conversation portrait, a fight on the stage, deleting a world; plus item looks in `tests/test_magic_items.py`);
the autoplay bot in both AI modes (it draws with pictures by default: `--letters` for the old way) on several seeds;
the smoke test in a real window; screenshots of every screen at 1920x1000 and 1024x640, looked at one by one.

**Saves**: old saves load. Towns already visited keep their old layout (their buildings are drawn the new way;
the new yards and front doors come with towns you have not been to yet). Nothing in the save format changed.

**Known issues / ideas for later**: the figures face you and do not turn; animals and monsters are still the
Dungeon Crawl pictures (only people are the new figures); buildings are rectangles (no L-shaped houses yet); the
picture engine needs a GPU that SDL can use (if it cannot, the game falls back to letters).

*Older entries (the cloud sessions after v1 and the milestones M0–M9) are in `docs/PROGRESS_ARCHIVE.md`.*


---

## Ideas parking lot (after v1 — do not build yet)
- more races and classes
- sailing
- owning property
- joining sieges and battles personally
- full crafting and smithing
- NPC voices via Player2 text-to-speech
- romance and relationships
- a player-led warband
- a main story with a growing world threat
