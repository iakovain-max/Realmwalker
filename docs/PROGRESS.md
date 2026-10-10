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

---

## After v1 — continuing work (2026-09-20), up to version 1.0 (2026-10-03) and since

The nine milestones are done; this is what has been added since, newest first. Version 1.0 is the pictures and the
new interface; then combat moved onto a grid, then every item was given a use, then looks became a choice, then the
game got sound and music (the first entries below).

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

### Cloud session, 2026-10-03: fair chances, and a final bug hunt (Anton's request)

Anton asked for a final pass through the code to fix every bug found, several simulated games, and a slightly
easier game: "it is too easy to randomly die right now". (Pull request "Fair chances, and a final bug hunt".)

**How it was measured.** A script played ninety lives as a careful new player would: walk from town to town, buy
food, take work, fight what looks fair and avoid what looks dangerous, camp at night, bind wounds. Before: half of
them were dead within a week, and the middle one lived five or six days. After: five in ninety died in the first
week, and the middle one lives three to four weeks. Most deaths were things a careful player could not see coming
or could do nothing about, and each of those is now fixed or fair:

- **Bugs that killed people.** When a fight ended with someone knocked down, the fight's minutes passed before they
  came round, and a body still at 0 hit points was found dead of its hurts: bandits who rob you and leave you
  killed you after all, and companions downed in a fight you *won* died afterwards. Lying senseless after a beating,
  your wounds bled the whole time with no chance to bind them. A trap that took the last hit point killed outright
  (in a fight, 0 is down, not dead): now it knocks you senseless. Underground, the rain fell and the wind blew, and
  it was noon down there whenever it was noon outside: now it is dry, still and dark. A fur cloak gave heatstroke to
  someone sitting in an inn at 16 °C, and resting beside a campfire in mild weather cooked you: clothes and fires now
  warm you up to comfortable and no further (a real heat wave still counts what you wear against you).
- **Losing a fight to animals** no longer always kills: beasts lose interest in what has stopped moving and drag off
  half the food instead. Each of the fallen makes a Constitution save to wake (most do), hours later and hurt.
  Robbers still rob; the dead, the mad and the monstrous still finish you.
- **Work fits the worker.** Nobody sends a level-1 traveller after a troll or an ogre: beast hunts now fit the party
  (an old boar, an orchard bear, a widow's wolf, a pack of wild dogs at first; trolls and ogres once you have made a
  name), and the offer and the journal say how the beast, or a raid you are asked to stand against, measures up.
- **Sure ways out on the road**, at a price: hand over half your purse to robbers (**P**), or throw hungry beasts your
  food and back away (**B**). Slipping away is much easier when you saw them first. Trouble finds you a third less
  often, and a night's camp is found less often.
- **Weather you can live through.** A rough shelter (**t** at camp when you have no tent: an hour, a Survival check)
  keeps off the wind and most of the rain, and a fire will burn in its lee even in a storm. A journey stops when a
  storm breaks, and at nightfall it stops before the dark (or the storm) can lose you. Sleep begun after dark lasts
  until first light, at camp or at an inn, so you do not wake at three in the morning and walk on into the cold. The
  cold takes heat 20% more slowly.
- **Water.** Rain fills a waterskin (**w**), and snow does by a fire. Your skins are topped up as you pass a town's
  well, and from streams and rain when they run dry. A journey stop names water up to 24 miles off. Worn to
  exhaustion 5 you can still stagger (slowly) to the water that would save you.
- **Smaller mercies.** Robbers leave the spellbook, the holy symbol, the pack and anything a piece of work gave you
  to carry. A five-point scratch on a level-1 wizard is no longer a gushing, critical wound (wounds are sized against
  a body of at least 14 hit points). A festering wound that is cleaned and bound no longer drifts towards the grave
  (left alone it still can kill). A death in battle names who did it ("killed by the bandit").

What has not changed: fights are still a real threat at level 1 (the balance numbers are the same), a winter night
without a fire and a tent is still dangerous, and an untreated serious wound still kills one in ten.

**The bug hunt** also took the game through forty dungeon dives, two hundred conversations (trade, services,
bribes, threats, pickpocketing), six hundred battles using every action there is, a month of travel with hired
companions, and the autoplay bot for over a hundred thousand turns on eleven seeds. The fixes are the ones above,
plus creeping (z) being dropped on the big map whatever way you leave the close view.

Checked by `tests/test_fair_chances.py`, new cases in `tests/test_combat.py`, `tests/test_screens_fit.py` and
`tests/test_small_fixes.py`. Old saves still load (nothing in the save changed).

**Riding** (Anton: "you can buy a horse and lead it, but it doesn't in any way speed you up"; "everyone moves as fast
as the slowest member, so everyone needs a horse to go at horse speed"). A horse did shorten a journey a little, but
nothing showed it: the travel plan, the map's estimate and the journey's forecast all still counted the walk, and in a
party one horse gave nothing at all, without a word as to why. Now (`game/mounts.py`):
- Each member rides one of the party's animals, the fastest first; whoever is left over walks, and then the whole
  party walks with them. When everyone rides, the slowest mount ridden sets the pace (before, a spare slow horse
  could hold back a lone rider on a fast one).
- A riding horse covers about half as much ground again as a walker on roads and open country, half that gain in
  woods, and nothing in marsh or mountains, where you lead it; a pony or a draft horse less; a mule only carries.
  How much each land allows is in data/economy.json ("ride_lands").
- The plan says "of riding" or "in the saddle" and counts it; the forecast before a journey says who rides and,
  when the party walks, why ("Muriel walks, with nothing to ride: the party goes at a walk").
- The side panel shows who rides what ("Osric on Bess, the riding horse · Muriel on foot (at a walk)"), and buying at
  the stable says how the party now travels. Two animals bought are no longer both called Bess.
- In the saddle you tire, hunger and thirst less than on foot, even at the walkers' pace, and a lame leg does not
  slow a rider.
Checked by `tests/test_mounts.py`. Old saves load; animals already bought are ridden at once.

### Cloud session, 2026-09-25: words that sound right

(Pull request "Words that sound right". Found by holding a few thousand conversations and reading every piece of
work, notice, history line and day's write-up the game makes without the AI.)
- **People tell their own stories.** "Tell me about yourself" used to put a note about them in their own mouth, in
  quotes ("Took over the inn when his father drank himself into the churchyard."). Now they say a line of their
  own and the story is told as what you learn: *Yrsa's story, as she tells it: took over the inn when her father
  drank himself into the churchyard.* Rulers and guild heads give their style ("Guildmistress Agnes Tanner. Most who
  come before me know that already.") instead of "They call me Edric. I'm the king."
- **Nobody names the cutpurse.** Asked about the town, people used to list the hireable travellers at the inn by
  trade, cutpurse and runaway serf included. They are "travellers at the inn" now, until you talk to them. The
  town is described once a day, not by everyone you ask, and titles take proper plurals (the ladies, the headmen).
- **Rumours and work within reach.** Townsfolk no longer tell of ruins 400 miles away; the missing of a town are
  no longer taken to a hideout up to 491 miles off (every other kind of work was already within about 120 miles).
- **Capitals where they belong.** One offer in twenty to hunt a beast began in lowercase, and heirloom offers
  said "You've heard of The Fernsby ring?". Fixed, along with "sits low in the coast", "born in a autumn", "is not
  who she say she is" and "a gossip and generous".
- **More to say.** Who someone is (3 ways to 11), remembering a threat or a kindness (1 to 6 each), bribes and
  threats (2 to 6 each), dangerous roads (2 to 6). Twelve common trades have life stories of their own; across a
  world, 1,286 townsfolk shared 40 stories, 13 secrets and 12 wants, and now share 92, 28 and 32.
- **The day's walk remembers its weather.** The written-up day of travel had three openings, four middles and three
  endings and did not know what the sky had done ("Under rain, the hours went by"). Every kind of weather has lines
  of its own now, and the day is remembered by the weather that held most of it.
- **The same fight rolls the same dice.** In a fight, sizing up the enemy (the knowledge check) happened in an
  order that changed every time the game started, so a fight rolled different dice after a reload. Fixed, and the
  roll now comes before what it told you.

Checked by `tests/test_words.py` and new floors in `tests/test_text_variety.py`; autoplay clean in both modes.
Old saves load; people already met keep the stories they had.

**More kinds of work** (design section 13). Besides bounties, lairs, beasts, letters, heirlooms, captives, debts,
disappearances and dragons, people now offer (sixteen kinds in all):
- **escort**: walk someone to another town. They travel with you and pay at the gate. Lose a fight on the road and
  they do not survive it. Some of them are running from something, and only say so on the second night.
- **assassinate**: a name, a town, and money for a quiet death. Face to face the story sometimes falls apart —
  then you can still do it, or tell them who paid and take their gratitude (and their purse) instead.
- **cure**: bring healing herbs to a town the sickness is in, and it lifts.
- **feud**: two notables who have not spoken in years. Talk each of them round, or pay them off.
- **steal**: lift a named thing from a named pocket, with the law where the law always is.
- **defend**: a village knows the raiders are coming, and roughly when. Be there on the day and they come out of
  the fields at dusk; be somewhere else and the place is sacked, sometimes burned, and the news travels.
- **smuggle**: a sealed crate that must reach another walled town without the gate wardens seeing it (they search
  travellers already; now they look for this too, and taking it is smuggling, whoever asked you to carry it).
Work of the quiet kind — killing, lifting, smuggling — brings no news and no fame, only infamy and the standing
of whoever paid.

### Cloud session, 2026-09-26: one pack for the whole party (Anton's request)

(Pull request "One pack for the whole party".) To end the micromanagement, the party now carries from one pack,
with or without companions. The inventory (**i**) is everyone's; what someone wears or wields is marked with their
name, **Tab** chooses who eats, drinks or puts things on, and **G** has the next one take a weapon up or put a thing
on. The weight is carried together — everyone's strength and the animals against everything in the pack ("Party
load") — so everyone is burdened alike and nothing needs shifting. Companions find what they need in it (the
archer's arrows, the healer's bandages, the bread at supper). Joining pours someone's things in (like supplies join
one stack); waiting, dismissal or desertion takes only what they wear and wield; the dead leave everything to the
rest. Older saves with separate packs are poured into one when loaded. Also fixed: a companion dying after the
leader had died could leave the party with nobody in it. Checked by `tests/test_shared_pack.py`, bot checks, and a
soak of twelve busy party lives (travel, fights, camps, waits, dismissals, deaths, saves and reloads).
Anton's decision the same day: **Guidance outside fights is postponed** (it would touch every check in the game).

**Companions ask for things.** A companion who becomes devoted finally asks you for one job of their own, chosen by
what they want: revenge on a real gang, a book they have wanted all their life, a cult they want ended, a pocket
worth picking, a debt nobody else will collect (press **b** on the party screen). It pays half, out of their own
purse. Seeing it through binds them to you; refusing or failing it loses them.

### Cloud session, 2026-09-25: finding your way in town

(Pull request "Finding your way in town".) Every building looks the same from the street and a city is a hundred key
presses across; the help promised "click further to travel", but on a close-up map a click only said "Leave this
place first". Now a click on a close-up map walks you there, a step at a time, stopping for any key and for anything
worth stopping for (a warning, a band that has seen you, a fight); a click on a person walks you up to them (following
if they wander) and opens the conversation; and in look mode (**l**) **Tab** jumps between the places you have seen,
nearest first (inn, shop, smithy, healer, temple, stable, hall, notice board, the people worth knowing; underground
the stairs, chests and coffins), and **Enter** walks you there. `game/wayfinding.py`; checked by
`tests/test_wayfinding.py`.

**Finding the work.** Every place your journal wants you is lit like lamplight on the map and the world map, and
the side panel shows how much work is in hand and when the next piece is due (click it, or press **j**).

**More on the road.** Eight new travel events: a flooded ford, a burnt farm, toll men whose arrangement may be
their own, a carter axle-deep in the ruts, a ring of standing stones, charcoal burners, a sick child at a cottage,
and a body in the reeds. Twenty in all, each with real choices.

### Cloud session, 2026-09-26: the first minutes read right

(Pull request "The first minutes read right".) Found by recording every line the game draws during long runs of the
bot in nine worlds and searching it for slips. Built-in text now says "an" before a vowel ("born in an autumn",
"Places that suit an acolyte", "formerly an outlander"). Weapon training is listed by name ("hand crossbow", not
"hand_crossbow"). Food in the pack says "keeps 60 days" (it read like sixty days of food). A fighter's fighting style
starts as the one that suits the chosen kit — Defence with mail and a shield, Archery with the longbow, Great Weapon
Fighting with the greataxe — instead of always Archery, until you pick one yourself. A death reads right wherever it
is told ("who froze to death", "was killed by the wolf"; it said "who died died of thirst"). "About a day and a half"
instead of "about 1 days"; no more "hour(s)". "Born to the Ironvein Clan", not "the the"; "Your old
teacher, Master Dario" instead of "Your old master Master Dario". A conversation choice you can't take yet reads
"I want to join the Guild of the Star — they need to think better of you first". Checked by
`tests/test_first_minutes.py`.

**More things that live out there.** Gnolls, hobgoblins, bugbears, berserkers and stirges, each in bands of
their own and in country that suits them (measured with the balance harness: a gnoll pack or a hobgoblin patrol
is a real fight at level 1; berserkers are a decision, not a fight, until about level 3).

### Cloud session, 2026-09-26: experience for discovery

(Pull request "Experience for discovery".) The design says experience comes from fights, work, discovery (new
regions, ruins, lore) and deeds, and the help said so too, but only books gave any for discovery. A measuring script
that wandered and explored for thirty days without taking work never reached level 2. Now the first time a character
enters a region they gain 10 experience times their level; the first time they reach a site (a ruin, a lair, a
barrow, a tower) 25 times their level; and each new level under the ground 25 times their level. The line that tells
of it says "(+25 experience)", everyone in the party gains it, the region you begin in does not count, and a piece of
work still pays about ten times as much. Measured again: an active explorer now reaches level 2 in two to three
weeks without taking work, and a very active one level 3 in a month. The numbers are in `data/rules.json`
("discovery_xp"). Save format 9; older saves still load. Checked by `tests/test_discovery.py`.

**Every level under the ground says what it is like** — cut stone and old grain in a cellar, burial niches three
deep in a crypt, scorched rock and opened armour in a lair — once, when you first come down. With Player2 running
the AI writes it instead, from the real facts of that level, and only while the built-in words are unread. Dark
places also look lived in now: fallen stone, old bones, tables and beds, pillars in the crypts and temples, water
in the low places of caves.

### Cloud session, 2026-09-26: the body

(Pull request "The body".) Two things the design asked for. **Needs with their trend**: the Health screen now says
where each need is heading — "fed · peckish in 2 hours", "tired · weary in 2 hours", "easing" while you sleep,
"wet · drying" by a fire, "cold · getting colder" or "warming" — and the side panel adds "(warming)" or "(getting
colder)" to someone cold or hot, so you can see whether the fire is enough. **Amputation** as a last resort: a limb
wound that cannot be saved (festering towards the blood, or a critical fracture, crush, burn or frostbite) can be
taken off from the Health screen (**a**, after a confirmation). It needs a blade; fire or a torch seals the stump; a
Medicine check (much harder on yourself) decides whether the stump is clean or ragged and bleeding. The infection
goes with the limb and the wound fever breaks, but what is left is for good: a lost arm means one hand for
everything (no shield, nothing two-handed), a lost leg makes every mile longer. The smallest window's Health screen
also no longer runs its treatments over the Back button. Checked by `tests/test_body.py`.

**Your own story.** The character sheet lists what you are known for (your last deeds, with fame and infamy), and
the chronicle's Legends tab has "Those who came before": the characters who lived and died in this world, with
their obituaries, beside the old heroes and the dragons.

### Cloud session, 2026-09-26: after dark

(Pull request "After dark".) Three things the design asked for. **Creeping** (**z** on a close-up map): slower
steps, one Stealth roll for the party (the worst of you, harder in clanking armour), and a band notices you only if
its Perception beats it — the dark helps, standing close does not. Fall on a band that has not seen you and you
strike first; townsfolk witness a crime only if they beat your roll too. **Gates that shut at night**: a walled town
or city is shut from nightfall until dawn, and **>** at its gate brings the warden — pay two silver at the postern,
talk your way in, climb the wall (a fall hurts), or sleep under the walls until morning. Villages stay open.
**Thieves in the camp**: a night in the wild with a mule or a horse can end with it gone, unless a companion keeps
watch. Checked by `tests/test_after_dark.py`.

**A dungeon belongs to whoever holds it.** The bottom of a bandit cellar used to hold bandits, goblins, rats and
the restless dead at once; now a place takes its character from its master, with vermin in the corners.

### Cloud session, 2026-09-25: small fixes

(Pull request "Small fixes".) Loose ends found while measuring: "Footpads has seen you!" (the verb follows the
band's name now); a death on a trap underground was written up as "died of their hurts" (it is "killed by poisoned
darts"); a chest of coins left a stray space; and a few rescues and beast hunts were offered that nobody could reach
in time, because deadlines were set from a straight line on the map. Every offer now measures the real walk, there
and back, at eight hours' walking a day, with three days to spare. Checked by `tests/test_small_fixes.py`.

**The world feels lived in.** Towns have street life (a rug beaten against a wall, a loose pig and three
people chasing it, the watch going by with a lantern and a long look) that changes with the hour, with market
days, and with what the town is going through — chalk on a door in plague, children stripping bark in a famine,
new shutters after a raid. The sky says when it turns: rain starting and stopping, fog coming up out of the
ground, the first flakes, the heat settling on you. And every named region can describe itself, in the AI's words
when Player2 is running, from the real facts of the place.

### Cloud session, 2026-09-25: companions with more to say

(Pull request "Companions with more to say".) A companion walks beside you for weeks, and had ten things to say on
the road, four at camp, four ways to approve or disapprove of you and two for most moods: over a month of travel
they said nine road lines chosen from ten. Now there are 259 lines where there were about 60:
- more of every kind (22 on the road, 14 at camp, 10 each to approve, disapprove and shout in battle, 8 each for
  rain, dark and weariness), and words for the **cold** and the **heat** on the road;
- **their own voice:** four lines in ten on the road and at camp come from what they care about (a devout
  companion stops at every shrine, a mercenary works out what the day was worth, a rebel spits at a lord's
  boundary stone), and when they judge something you did, they say it in the voice of the value it touched;
- **the right pronouns:** "He did not go empty-handed", not "They did not go".

Checked by `tests/test_companion_voices.py` and floors in `tests/test_text_variety.py`. Old saves load.

**Your name goes before you.** Fame and infamy now change how a stranger takes you the first time you speak:
notables have heard more and sooner than a farmhand, fame impresses the proud and the greedy, and a bad name
frightens the kind and the nervous worst of all.

### Cloud session, 2026-09-25: more words where they are read most

(Pull request "More words where they are read most". A census of every list of words in the data, looking for thin
ones the player meets often.) A won fight was written up one of three ways (twelve now), fleeing, a parley and being
robbed one way each (five now); every kind of wound at every severity five ways instead of three; each kind of land
two ways, so named regions shared descriptions (six now); fifteen trades two greetings each (four now); everyone you
meet was described in one of two sentence shapes (five now); and travellers for hire have four life stories each.
Two slips fixed on the way: "The wolf lie still" (the verb follows the number) and dying "on the pine forest" (the
ground underfoot now: the pine needles, the sand, the road). Checked by `tests/test_more_words.py`.

**Things the design asked for that the game did not have yet.**
- A **Spells screen** (**S**): every spell a caster knows, grouped by level, what it does, whether it can be cast
  now, the spell attack bonus and save DC, slots left today, and the size of a wizard's book. Until now you could
  only see your spells in the middle of a fight.
- **Simple crafting** at camp (**m**): torches and splints from firewood, bandages from linen, salted meat and
  smoked fish that keep, and a herbal remedy from healing herbs with a kit and a fire, each on a Survival or
  Medicine check.
- **Caravans** on the road: trade with them, walk with them for safety and a little pay, lean on the factor for a
  toll, or take what they have and meet their dozen hired swords.
- **A confirmation before drawing steel** on somebody in conversation, as the design asks for dangerous acts.
- **Landmarks on the skyline**: a ruin, a cave or an old tower coming into view is remarked on and goes on your map.

### Cloud session, 2026-09-26: what rank buys you

(Pull request "What rank buys you".) The design says rising in rank unlocks quests, discounts, training, safehouses
and titles; the game had the quests, discounts and titles. **Lessons**: from the second rank of a guild, order or
church, its people will teach you one of its skills for each rank you rise — merchants Persuasion and Insight,
healers Medicine and Nature, mages Arcana and History, thieves Stealth, Sleight of Hand and Deception, and so on —
for a long day and 50 gold crowns (25 more for each lesson after). **A safehouse**: a fence of the thieves' guild
can hide a wanted member for three days for 15 gold crowns, and the price on their head in that realm is halved
(once a week). Both are conversation choices; the numbers are in `data/law.json`. Checked by
`tests/test_rank_perks.py`.

**Factions make you earn each promotion** (the design's "faction rank-up tasks"). You join at the bottom
whatever your standing; standing opens the door to the next rank, and a piece of that faction's work walks you
through it — an offer from one of their people says whose eyes are on it, pays a little more, and promotes you
when it is done. If your standing runs two ranks ahead of what they have given you, they give in and promote you
anyway, so nobody is ever stuck.

### Cloud session, 2026-09-26: grateful companions

(Pull request "Grateful companions".) The design says companions come from taverns, guilds, freed prisoners and
grateful people; they only ever came from inns and mercenary companies. Now someone you break out of a dungeon's
chains on a rescue, once the work is handed in, waits at the inn of that town: "If you ever want someone at your
back, I'm yours. No coin. Just keep me fed." They ask no wage and nothing up front (Anton, the same day: those who
follow you for their own reasons take no pay), start out more loyal than a hired sword, and do not drift away with the travellers who come and go each month. Checked by `tests/test_grateful.py`.

**The journal remembers people** (Tab): everyone you have spoken to, by town, with what they are, how they feel
about you, what work of theirs you carry, and what they remember about you.

**How it runs** (measured on a large world of 106 settlements and 65 sites): the world is made in about a second;
a frame takes 2 ms on the overworld, in a city of 15,000 and underground alike; a save is 87 ms and about half a
megabyte, and loads in 48 ms. Twenty years of politics with nobody watching takes under a second.

### Cloud session, 2026-09-25: screens that fit

(Pull request "Screens that fit". Found by watching the side of every box and the edge of the window while the
autoplay bot played, and while every screen was drawn with a full party, ten jobs, five wounds, a level-10 wizard's
spells, all twenty road events and forty kinds of trouble, at six window sizes.)
- **The road-trouble box** let a greyed-out choice run past its border at every size ("Ambush them (they are caught
  unawares): they have already seen you"); now "Ambush them: they have already seen you", and anything too long
  ends in "…" with the whole of it in the tooltip.
- **Said twice:** "[Persuasion] Argue that you are exempt (Persuasion, DC 13)" is "(DC 13)"; an inn's prices were
  shown at the end of each line and again in the price column, and are shown once.
- **A big fight shows everyone.** The battle board held three cards a rank whatever the window, so four bandits in
  the front rank were two and "+2 more" above an empty third of the screen. It grows now when there is room.
- **Small windows:** the character sheet's notes column ran off an 80-column window (it now takes the skills'
  place there, **s** switches); the pack's buttons ran over the border with a companion along (those that do not
  fit are left out, their keys still work); the title screen said "M7 - Companions and progression" and ran off the
  edge; the creation hint ran off the edge; the side panel left "d)" alone on a line ("next due in 11 days" now).

Checked by `tests/test_screens_fit.py` (it watches the borders and the edge at five sizes). At the two smallest
window sizes a few lines still lose their last few characters (the market's top line, a hint on the health
screen); nothing important is hidden.

**Help and energy.** The help opens with "Your first hour": seven steps from the title screen to a first piece of
finished work, and what to buy before leaving town. Settings gains **AI extras**, which keeps Player2's limited
energy for people, places and conversation if you would rather not spend it on regions, dungeons, items, the
wording of work and obituaries.

### Cloud session, 2026-09-26: magic on the road

(Pull request "Magic on the road".) Mage Armour said "for eight hours" but only ever lasted the one fight, and a
wizard could not put it on before setting out, so its first turn in every fight went on armour. Now the spells that
last ten minutes or more (Mage Armour eight hours, Stoneskin and Death Ward an hour, Shield of Faith ten minutes) can
be cast on the road from the Spells screen, stay on through every fight in that time, and are still on after a fight
they were cast in. The side panel and the sheet count their armour, the sheet lists them with the time left, and the
log says when one fades. The same spell renews rather than stacks, and the fight's spell menu says "already working
on you" instead of spending a second slot. The Spells screen (**S**) is now a list you can pick from, with the chosen
spell described on the right, a green dot on what can be cast here, and **Enter** to cast (**left**/**right** choose
who it is for); healing spells can be cast from there too, on the worst wound. Spells that only make sense in a fight
say so. A new first-level wizard spell, **Identify**, is cast the same way: ten minutes over the first strange thing in the packs tells you what it is, what it does and whether it is cursed (the design names it as one of the three ways to know a magic item). Kept as a timed effect on the character (`Character.effects["spell:<id>"]`, saved already, so old characters
still load). `rules/spells.py` (`lasting`, `keep`), `game/magic.py` (`cast_on_road`); checked by
`tests/test_road_magic.py`.

**Prisoners are worth more to their own people.** Bind a beaten bandit and you could only ever hand them to the
watch. If you are sworn to the thieves' guild, their fence will take your prisoners out by the back door and come
back with three times the head price. Nothing of it is ever spoken about (no news, no fame, only infamy), the
outlaw's friends think better of you, the local realm thinks worse, and companions who like the law say so.

**Writing the game had and never used.** Sixteen pieces of work all ended with the same sentence about being paid;
the six pay lines that were sitting in the data are used now (and there are more of them). A trade's door pushed
open after dark answers "We're shut. Come back in the morning." Somebody who hates you will no longer gossip with
you about the town or the people in it.

**The game says things more ways.** Walking in fog used to be nothing but losing and finding the way again —
a dice roll and two lines at every step; now you lose the way once and stay lost until you strike a road, the
weather lifts or the light comes back, which is what the game already told you to do. Wading a river is
described differently every time, and says the cold when the water is near freezing. A town has three times as
many greetings, and people greet you out of their trade: the smith says mind the sparks, the guard asks your
business in the town, the beggar asks for a coin before you have said anything. Fights — the most-read writing
in the game — had four ways to miss and one way to describe each wound; both are three times as many now, along
with more ways for every kind of blow to land, for a fight to end, and for a beaten man to beg.

Three more places where the game used to say one thing forever: every kind of trouble on the road (thirty-six
of them, from the watch to a dragon) now has three ways of arriving instead of one; every land has six things it
can do at a night's camp instead of two; and a town in plague, famine, siege or market day has three times as
much going on in its streets. The tests now keep a floor under all of these lists, so they cannot quietly thin
out again.

A walk of four thousand steps now reads a hundred and thirteen different lines where it used to read a hundred
and three of a thinner sort: the sky turns five ways for each kind of weather instead of two, a border shows you
how you know it (a boundary stone grown over, a gibbet with the chain rusted through, two riders on the rise),
and coming back to a town you know says it six ways.

**The chronicle does not repeat itself.** Two hundred and fifty years of history, and every siege, succession,
plague and dragon was written up in one of two sentences. Four each now — and the same lines carry the news you
hear in taverns while you play, so the world sounds less like a form being filled in.

**Inns have a common room again.** The tavern writing — the building, the light, the smell, who is drinking,
one telling detail, a line somebody says about local trouble — has been sitting in the data since the first week
of the project and only ever appeared on the Player2 test screen. Walk into an inn now and the game tells you
what the room is like, once per inn, kept in the save so it is the same place when you come back. There is a
good deal more of that writing now too: nine ways for the building to look, ten smells, ten sounds, thirteen
details, twelve things to overhear.

**The dark has something to say.** Four thousand steps underground used to be ninety lines, nearly all of them
stairs. Now the passage breathes, water keeps time with nothing, a draught comes from somewhere that should not
have a somewhere, and a bone is underfoot before you see it — lines for any dark place and lines of its own for
cellars, crypts, towers, hideouts, temples, caves, warrens and lairs. Only when you can see (a light, or a
dwarf's or elf's eyes), only at normal text detail and above, and never oftener than once every dozen steps.
Going down and coming up have several ways of saying it, and a deeper level is "the third level of the barrows"
rather than "level 3".

### Cloud session, 2026-09-26: why they follow you, and seven who are like no one else (Anton's request)

Anton asked: companions' own money should be hidden or not exist, with only the player's money usable; more companions
who follow out of respect or because they have nowhere left to go (a realm's knight for someone it reveres, a drunk
or a foolish farm lad talked into it with a lucrative job, others won with a good skill check); and a new group of
**unique companions**, stronger and more interesting, usually unpaid but hard to get (a quest, or being found who
knows where), and not made up by the game: the same in every world. "Like, seven."

- **One purse.** Companions carry no coin. Wages and loot shares are paid to them and gone (the party screen says how
  much they have had of you); only your money is ever spent or shown. An older save's companion coin is handed to the
  leader when it loads.
- **Why they follow you.** Every companion now has a reason, shown on the party screen and the side panel: hired,
  grateful, sworn, for a share, to see the world, homeless, for your name, or their own. Only the hired take a wage,
  and "Raise pay" only shows for them.
- **Sworn swords.** A kingdom, noble house, free city, clan or elven realm that honours you (standing 50 or more)
  lends you one of its own if you ask its ruler: a knight of the household, a sergeant of the city guard, a
  hearth-guard. The realm pays them. Below 15, or with a price on your head there, they are called home. One at a
  time from each realm; if theirs dies with you, they think less of you and lend no other for a season.
- **Dreamers.** Tell a young farm hand, fisher, serving girl, beggar or drunk about paying work you have taken
  (Persuasion 12) and they come for a fifth of every reward. Tell them it will make them rich (Deception 10) and they
  remember it when the money comes, unless it really was riches. A week with no paying work in hand and they start to
  wonder. Level 1, poor kit, and a little weaker than a soldier.
- **The restless.** A hard word (Persuasion 16, once a week) can talk a young guard, acolyte, woodcutter or miner
  who is brave, proud or bitter, or who wants to leave, into coming with you.
- **The homeless.** Survivors of places burned in the last year, sacked in the last four months, or raided, wait at
  the inns within a few days' walk, and come for their keep.
- **Admirers.** Once your fame is 10 or more (and more than your infamy), someone who has heard of you may be waiting
  at an inn. They cool as your infamy outgrows your fame.
- **Seven who are like no one else** (`data/uniques.json`, `game/uniques.py`). The same seven, with the same faces,
  words and gear, in every world; only where they are is the world's. They take no wage, join a level above you (or
  their own least level), have their own voices, likes and dislikes, talk to each other on the road, and are rumoured
  about in the news. If you part, they go home and come back as they left; if they die, they are gone for good.
  - **Sir Osric Vane**, last knight of the Grey Lantern, keeps a vigil over a barrow near where he lodges. Clear it and
    he is yours. He keeps watch every night, whatever his orders.
  - **Durgin Ashbeard**, last of Kharak-Dûl, drinks in the alehouse nearest the sleeping dragon. Out-drink him
    (Constitution), then swear to kill it with him (level 3). He marks every dragon's lair; his shield turns fire.
    He does not forgive a broken oath.
  - **Tobiah Vell, Twice-Hanged**, is in the cells of the greatest city. Pay the gaoler 25 gp, speak for him
    (Persuasion 17, easier where they think well of you), or pick the lock (a jailbreak if anyone sees). The first
    blow that should kill him each day does not.
  - **Sister Wendeline**, the Plague-Bell, is where the sickness is (or was). Work a day beside her (Medicine 12), or
    have brought the cure to a sick town. She never catches anything, and her bell heals. The infamous she turns away.
  - **Grusha Nine-Fingers**, the Penitent, scrubs a temple floor near orc country. Ask what she atones for, see that
    she is hiding (Insight 14), and take her to the village she helped to burn. There its headman hears you: speak
    for her, let her speak, pay the blood-price, hand her over, or take her away. Orcs and goblins know her name.
  - **Aelith of the Long Memory** keeps the memory-books in an elven hall. Give her a book to read, tell her
    something she does not know (History 17), or show her something strange. She remembers what happened in every
    town you walk into, and knows magic things at a glance.
  - **Wren Underbough**, the Night-Road, is the best smuggler on the back roads. Run her crate past a gate (or be
    one of the thieves' guild). With her, gate-wardens never search your packs.
- **Fixed on the way.** Companions who outlived a dead character were marked for hire without saying as what, so the
  next character could not talk to them; now sell-swords can be hired again and the rest go back to who they were.
  And a companion's death on the road no longer drops a dead leader out of the party (the same fix as the shared
  pack's).

Checked by `tests/test_followers.py` and `tests/test_uniques.py`, and by a soak that recruited all seven about
twenty times each across twelve worlds, with sworn swords, dreamers and the restless, then travelled, fought,
rested, saved and loaded, died and started again, checking the party after every step: no problems.

**Ready to be worked on from the cloud.** `docs/CLOUD_HANDOFF.md` is a briefing for a Claude Code session
running on GitHub instead of your PC: what it can check there (all the tests, the autoplay bot, the balance
numbers), what it cannot (the window itself, the friend build — both need Windows), that it must never touch
your real Player2 energy, and how its work comes back to you as a pull request. `Update_And_Play.bat` fetches
the newest version and starts the game, so getting a change is one double-click.

His decisions on 2026-09-26: **old saves do not need to keep working** for now (a save whose shape has changed
is refused with a friendly message and he starts a new character), and cloud work should come in **large finished
batches** rather than small tweaks he would have to try one at a time — he is at work while it runs, and will
check how things look on his own PC afterwards.

**A test for the first evening.** A new character in a new world is now checked, in two different worlds, for
the things a new player needs: people in the first town, money in the purse, somebody who sells food, work on
offer, work that goes into the journal and lights the map, and a road that takes them closer to it.

**Fixes.** "Text detail" in Settings did nothing at all until now (it governs street life, companions on the
road, the weather turning, the sounds of the night and whether the AI is asked to describe regions). The dead no
longer linger in the party or among those waiting (cleared as time passes, on rejoining,
and never written into a save); `first()` no longer calls a character named "The Wanderer" "The"; the autoplay
bot's invariants no longer complain about a companion or a band of enemies holding their dead while the battle is
still being fought. A battle's dice used to come from a stream keyed on how many messages were in the log, so
saying one more thing before a fight changed the fight; each battle now has its own numbered stream. The balance
harness was measuring one run twelve times (the body and health dice are keyed on the world clock, and every run
started at the same minute), which is now fixed and the numbers are real. The debug console gained
`quest <kind>` for trying a piece of work on the spot.

### Cloud sessions (from 2026-09-25)

Work done in a Claude Code cloud session comes as one pull request per theme. **Your list of rough edges:** asked
for on 2026-09-25; no answer yet, so the first themes are rough edges found by measuring the game (scripts that
walk the world for weeks, hold hundreds of conversations and survey every offer of work). Your list goes here when
it comes, and is worked through first.

**Journeys that look after you** (pull request "Journeys that look after you"). Measured before the change: of
forty new characters using **t** to travel from town to town, sixteen died on the road within a week — eight froze,
two died of thirst, two bled out, one of heatstroke, three to animals while worn out — because a journey walked on
through the night, through "exhausted", "no water", "hypothermic" and even "cannot walk", until the traveller
dropped. Now:
- A journey **stops by itself** when night comes on, and when someone becomes weary, worn down, hungry with nothing
  to eat, parched, cold, overheated, bleeding, faint, sick or festering, or when the last of the water is gone. It
  says why, once; being weary again tomorrow stops you again. It stops at dusk before the dark can lose you.
- The stop says **where the nearest roof is** (a town within about six miles) and, when you are dry, **the nearest
  water you have seen**.
- **t** then **Enter** takes the journey up again: the world map opens on where you were going.
- **Before setting out**, the plan says how many nights it means in the open, whether the food and water will last
  (in red when they will not), and whether the nights there are cold enough to kill.
- **Sleep is broken** when the cold, thirst, hunger or a bleeding wound turns dangerous ("The cold wakes you"),
  instead of being slept through to the end. A traveller measured before this froze to death beside a lit fire,
  asleep, and then "woke rested".
- **A fire dries you even in the rain** (all but a downpour); before, rain kept you soaked beside it all night.
- **Nobody starts slowed by their pack.** Half of all new characters (78 of 160 combinations) started encumbered.
  The clothes you are dressed in no longer count against your strength (armour still counts half); the outlander's
  25 lb hunting trap (which did nothing) is fishing tackle now, the folk hero's shovel is gone and the iron pot is a
  mess kit, the criminal's crowbar is gone, and the suggested rogue has strength 10.
- **Acolytes and sages set out in boots and a cloak** instead of sandals (warmth 3, the rest had 8 to 13).
- "Too exhausted to walk" no longer says you are carrying too much; a death in battle reads "killed by the wolf".

How it was checked: tests for each of these (`tests/test_journey.py`, and every race, class and background in
`tests/test_character.py`); the balance numbers are unchanged (the harness's winter nights are dry and do not go
through sleep); autoplay clean in both modes. Old saves still load.

---

## M9 — Death, legacy and release (done)

**What you can do now**
- **Die properly.** Death is still permanent, but now it means something. The death screen gives you an
  obituary: what you were, how and where you died, what you killed, the work you finished, who you travelled
  with, what you did that anyone will remember, and what the powers of the land thought of you. With Player2
  running, the AI writes it in its own words; the words are kept with the world.
- **The world keeps your story.** A death is written into the world itself: famous ones go into the chronicle
  (**n**) and travel as news; unknown ones pass without remark, as they should. Everything you carried is gone —
  no body, no grave, no gear to recover, exactly as the design asks.
- **Companions outlive you.** Those still standing go home, remember who they travelled with and how it ended,
  and can be hired again by whoever comes next.
- **A new life in an old world.** **New Character** on the title screen makes a character in a world you have
  already played, starting wherever you choose. The world does not wait: three weeks to five months of politics
  run first, and you are told what changed before your first step — towns taken, new rulers, wars begun and
  ended, plague, famine, gangs, a dragon awake — along with what people are saying and who walked this land
  before you.
- **Help for everything.** The help screen (**F1**) now covers every system and every key, including the
  underground, magic items, work and the journal, dragons, books and paper, death and new lives, and where the
  game keeps your saves and its error log.
- **A build to send to friends.** `Build_For_Friends.bat` runs the tests, builds `Realmwalker.exe`, checks that
  the packaged game starts, and zips it (about 35 MB) with a readme that says what the game is and how to run it.

**How to try it**
1. Double-click `Play.bat` and **Continue**.
2. Get yourself killed (it is not hard). Read the obituary.
3. On the title screen choose **New Character**, pick the same world, and make someone new. Read what happened
   while nobody was watching, then walk into it.
4. To send the game to someone: double-click `Build_For_Friends.bat` and wait a few minutes; it leaves
   `Realmwalker.zip` in the project folder.

**What to look for:** Does the obituary feel like a proper ending? Is the world noticeably different when you
come back to it as someone new? Is anything in the help missing or wrong?

**How it was verified**
- 550 automated tests pass at the close of M9 (645 now, with the work since), including new ones for the death record, unremarkable deaths, companions going
  home, the obituary (built-in and AI), saving the dead with the world, the years between lives, and the death
  and interlude windows at every size.
- **A balance pass, measured** (`tools/balance.py`, locked in by `tests/test_balance.py`):
  - at level 1 alone, two wolves are won 48% of the time and put you on your back in half the fights; three
    bandits are won 38% of the time; a lone wolf or a single bandit is a fight, not a death sentence (80-95%);
  - a party of three at level 1 usually wins those fights but pays for them (someone down in 40%, someone dead
    in 3-8%); at level 3 the same fights are comfortable;
  - a winter night in the open without fire or shelter leaves you at 1-6 hit points and exhausted; a fire stops
    the damage; a fire and a tent leave you merely cold;
  - an untreated critical wound bleeds you to death within a day (17 runs in 20), and binding it saves you
    (0 in 20); a serious, dirty wound left alone for a week festers in about a fifth of cases and kills in
    about one in twelve, and binding and cleaning it roughly halves that.
  Nothing needed retuning: the numbers already sit where the design asks.
- The smoke test tours every screen; autoplay ran clean in both AI modes; the packaged build was made and its
  exe smoke-tested.

**Decisions (and why)**
1. **The obituary is kept in the world, not the character**, so the next character can be told who came before
   them — the only thing that carries over is the story.
2. **Reputation does not carry over.** Standing, money and gear die with the character; the world's memory of
   the deeds does not.
3. **The interlude runs the real politics engine**, not a summary generator, so what you are told about is what
   actually happened while you were away.
4. **Balance is measured, not asserted.** The harness prints the numbers so they can be tuned later with
   evidence, and the tests fail if the game drifts much softer or much deadlier.

**Known issues**
- The interlude does not age or replace ordinary townsfolk (only the great ones, who are simulated).
- A world with no living character keeps its local maps and townsfolk as they were, so a town you emptied stays
  empty for the next character.
- (Companion personal quests, escorts, smuggling, assassinations and faction rank-up trials were on this list
  and have since been built — see "After v1" at the top.)

---

## M8 — Adventure content (done)

**What you can do now**
- **Dungeons under every ruin, cave, barrow and tower.** Walk onto the steps down (`>`) in the close view and go
  under: cellars, crypts, hideouts, warrens, hidden temples, mage towers, caves and dragon lairs, one to three
  levels deep, each built from real rooms and corridors (or gnawed cave tunnels), with doors, locked doors, secret
  doors, hidden rooms, chests, coffins and traps. The master of the place waits at the bottom.
  - It is dark: light a torch or lantern (they burn down, so carry spares), or see only what is under your nose;
    dwarves and elves see a little in the dark.
  - **s** searches where you stand for traps, secret doors and hidden rooms. Walking into a locked door or a chest
    tries to open it (thieves' tools help). Opening a coffin may wake what is in it.
- **Magic items**, rare and mostly old. What you find looks like "a strange sword" until you know it: **Enter** on
  it in your pack studies it for an hour (Arcana, once a day per item), or a priest will tell you for a donation.
  Known items list exactly what they do (to hit and damage, armour class, saves, a skill, resistance, light,
  warmth, an ability, or a spell a few times a day) and carry a name and a history drawn from the world's own past
  — the AI writes those when Player2 is running. Some are cursed: they will not come off and they work against you
  until a temple lifts it.
- **Work, and a journal (j).** Ask people in towns "Is there any work?". A bounty on a real gang's captain in
  their real hideout; a lair to clear; a named beast to hunt (it is really out there, where they said); a sealed
  letter to carry to a real person in another town; an heirloom — or one of the world's lost treasures from the
  chronicle — to bring back from a real barrow; a son or daughter taken by outlaws, chained in the deepest room;
  a debt to collect; people going missing, and the cult that takes them. Wanted posters on the notice board can be
  taken down and taken on (press the number).
  - Each job has a reward and a deadline, and the place goes on your map. Finish it and go back to whoever set it.
    Fail it or give it up (**a** in the journal) and they, and their people, remember.
  - **Not everything is as you were told.** The outlaws may be starving deserters you can talk into leaving
    instead of killing (half pay, and your kinder companions approve). The debtor may have nothing but children
    and an empty house: take it anyway, or forgive it. A sealed letter may be worth reading — and once read, it
    can still be delivered (for half), taken to the lord (for more, and the sender is disgraced), or held over the
    sender's head for everything in their purse.
- **Dragons.** Every world keeps one asleep in a lair in the high country. While you play it wakes now and then to
  burn a village or take tribute in cattle and silver, and the news travels. The country around a lair shows it:
  burned trees, bones in the grass, no birds. It is a killing fight; its hoard is real gold, and taking any of it
  wakes the owner. Kill it and the tribute stops, the realms nearby remember it, and the chronicle (**n**) records
  who did it, beside the old heroes. Lords near a lair will pay for the head — but only offer it to a party that
  looks like it might live.
- **Paper is treasure.** Old maps, books of histories, books of old lore and dead strangers' letters turn up in
  chests and graves. **Enter** reads one (an hour): real places go on your map, a faction that really holds this
  land joins your list, one of the world's lost artifacts is named along with where it came to rest, or a cult's
  hidden temple is pointed out. They say the same thing every time you read them.

**How to try it**
1. Double-click `Play.bat` and **Continue** (old saves are upgraded).
2. In a town, talk to the innkeeper, the headman, a priest, a smith, a guard: **"Is there any work?"**. Take
   something on, then press **j** for the journal. Read the notice board in the square (**¶**) and press **1**.
3. Walk to the place on your map, press **>** to go into the close view, find the steps down (**>**) and go under.
   Light a torch first (**i**, Enter on it). Press **s** now and then.
4. Kill what is at the bottom, take what it was sitting on, and go back to whoever set you the work.
5. Try the other side of a job: break the seal on a letter you are carrying (**i**, Enter), and see what it says.

**What to look for:** Is the work worth doing (pay, distance, deadlines)? Is the journal clear about what is left
to do? Are the dungeons interesting to walk through, or a maze? Is a magic item exciting when you find one?

**How it was verified**
- 532 automated tests pass. New ones cover: dungeon layouts (every room reachable, stairs, secret rooms, coffins
  that do not block doorways), light and darkness, traps, searching, locks and chests; magic items (budgets,
  effects, identifying, curses, charges, treasure, the AI's names, saving); quests (offers tied to real gangs,
  sites, beasts, people and artifacts; taking work in conversation and from the board; clearing a lair; a bounty
  paid by the watch; deserters talked away; hunting a named beast; retrieving a thing from the deepest level;
  freeing a captive or finding them dead; a letter delivered, opened, or used against its sender; collecting a
  debt from someone who can pay and someone who cannot; investigating the missing; deadlines and dead givers;
  saving; the AI wording an offer through the mock server); dragons (lairs, the warning signs, waking to burn or
  take tribute, killing one for good, and a lord's reward); books, maps and letters; and the journal window at
  every size.
- The smoke test tours the new journal window; autoplay ran clean in both AI modes (12,000 turns each), now also
  taking on work, with invariant checks on the journal.

**Decisions (and why)**
1. **Quests are made from what the world already has.** No quest invents a gang, a village or a treasure: it
   points at a faction, a site, a person or an artifact that exists, so finishing one changes the world (a gang
   loses its captain, a site is cleared, a cult is found, a dragon dies) and the news spreads like any other deed.
2. **Code owns the terms; the AI only speaks.** The reward, the deadline, the target and the outcome are the
   game's; the AI may write the giver's words, and the game always shows the pay and the days itself.
3. **Hidden sides instead of moral labels.** A job can turn out to be something else when you get there; the game
   never says which choice is right, but your companions have opinions.
4. **One job at a time from each person, a new one about once a week**, kept with the town (so a town you visit
   often keeps changing) and thought of before you ask, so the AI has time to word it.
5. **The dragon is guaranteed.** A world where the last dragon was killed in the chronicle felt smaller, so world
   generation always leaves one asleep somewhere.

**Known issues**
- ~~Companions have no personal quests of their own yet~~ — built after v1: a devoted companion asks for one
  job of their own (party screen, **b**).
- A job's giver dying (plague, war, your own sword) closes the job with a note rather than passing it to their
  heir.
- Dungeon levels are built when you first go down and kept in the save, so a level you have seen does not change
  if the data files change.

---

## M7 — Companions and progression (done)

**What you can do now**
- **Level-up choices.** Levels still bring hit points and features at once, but the choices are yours now: a
  path (Champion or Knight, Thief or Cutthroat, Life or War, Evocation or Abjuration), ability increases at levels
  4 and 8 (+2 to one or +1 to two; Constitution adds hit points at every level), and a wizard's new spells and
  cantrips. The level-up screen opens by itself after a level-up; **Choose for me** makes sensible choices; you can
  also come back later (character sheet **c**, then **l**).
- **Spell scrolls.** Scrolls of every spell are sold where mages gather (cities, and towns with a circle of mages).
  A wizard can copy one into the spellbook (Enter on it in the pack): an Arcana check, 50 gold crowns and two hours
  per spell level, and the scroll is used up either way. Anyone can read a scroll aloud once in a fight from the
  spell menu (with a check if it isn't their kind of magic).
- **Companions**, up to four. Travellers looking for work wait at the inns of villages, towns and cities (a new lot
  every month or so), and sell-swords are for hire in a mercenary company's town. They are sell-swords, old
  soldiers, hedge wizards, wandering priests, zealots, cutpurses, outlaw hunters and runaway serfs. Ask
  "Would you travel with me?" and they name their price: a daily wage, some of it up front, and for cutpurses a
  share of the loot.
  - They are full characters of their class and about your level, with their own gear, needs, wounds and
    sicknesses. They level up with you, and you make their choices. In a fight you command each one. They can
    die, for good.
  - **Loyalty** moves with what you do, by their values (devout, in it for the money, kind, honourable,
    law-abiding, no friend of lords, greedy, cruel, brave, learned, cautious) and what they want (revenge on
    outlaws, knowledge, a cause, loot, pay). They say what they think. Unpaid wages sour them fast. Unhappy
    companions grumble, and mutinous ones slip away in the night with some of your coin. Devoted ones say so.
  - **Orders** on the party screen (**p**): follow, keep watch when you camp (you are woken before an attack), forage
    while the others sleep, or wait at this spot until you return. You can also talk to them, raise their pay or
    dismiss them.
  - The party shares its food and water. **G** in the pack hands something to the next member; **Tab** switches
    between members on the sheets.

**How to try it**
1. Double-click `Play.bat`, **Continue** (or a new world). Go to a town, walk into the inn, and talk to a traveller.
2. Hire them, then press **p** to see the party, and **c**/**i**/**e** for their sheet, pack and gear.
3. Fight something together; after a level-up, make your choices.
4. Do something your companion hates (or loves) and watch the log.

**What to look for:** Are companions worth their pay? Is loyalty too touchy, or not touchy enough? Are the
level-up choices clear?

**How it was verified**
- 479 automated tests pass. New ones cover: the fighter's path at level 3; ability increases (and hit points from
  Constitution); wizard spell choices; choices made for you; a scroll for every spell; copying (success, failure,
  who may); reading a scroll in a fight; scrolls for sale; travellers at the inns and their coming and going;
  hiring (and who won't come); hiring in conversation; loyalty following values and crimes; wages, unpaid days and
  desertion; loot shares; waiting and rejoining; keeping watch and foraging at camp; shared food; a companion's
  death; saving the party and those waiting; companions under your command in battle; and the level-up and party
  windows at every size.
- Autoplay: thousands of turns in both AI modes, now also hiring companions, with checks on party size, loyalty,
  waiting companions and level-up choices. No errors.

**Decisions (and why)**
1. **Companions are townsfolk turned into full characters** at hiring (their name, looks and story carry over), so
   everything that works for you (needs, wounds, levels, battle) works for them.
2. **Loyalty reactions come from tags** that the game already knows (mercy, execution, theft, prayer, loot...), so
   any new deed can be given a tag and every companion reacts to it by their values.
3. **Dismissed or deserting companions go home** as townsfolk (a deserter does not like you any more).
4. **Personal quests for devoted companions** come with the quest system (M8).

**Known issues**
- Freed prisoners and grateful townsfolk joining you come with quests (M8).
- Devotion has no effect in battle yet beyond their word; mutiny never turns to outright betrayal yet.
- Towns you visited before M7 get their travellers on your next visit.

---

## M6 — Factions and politics (done)

**What you can do now**
- **The powers of the land.** Every world now has kingdoms and the noble houses sworn to them, free cities,
  dwarven clans, highland clans and elven realms, and tribes of orcs, goblins or nomads in the wild. It also has
  churches (one per faith) and a knightly order, guilds (merchants, mages, healers, smiths), mercenary
  companies, a hidden thieves' guild, secret cults, bandit gangs and pirate crews. Each has a leader, values
  (pious, mercantile, warlike...), friends and enemies, and realms have their own laws. Every town is held by
  someone; the king lives in the keep of his capital, the lady in her hall, the high priest in the great temple.
  Press **f** for the Factions screen, and **p** on the world map to colour the land by realm. Crossing a border
  is announced.
- **Your standing** with each faction (Hated, Distrusted, Neutral, Respected, Honoured), plus fame and infamy.
  People who answer to a faction treat you by it, and prices follow it. Your background ties are now real: the
  soldier served an actual lord (and a deserter is remembered), the acolyte belongs to a real church, the noble
  has a family house, and the criminal has a real price on their head.
- **Deeds ripple.** Helping a faction pleases its friends and angers its enemies, but only once the news reaches
  them. Beating bandits angers their gang and pleases the lord of the land; the same goes for cultists and
  raiders. Take prisoners after a fight and hand them to any watch for a reward.
- **Law and crime.** Theft (steal in a market with **s**), pickpocketing, trespass (in a house at night),
  assault and murder are crimes, and so are poaching, smuggling, magic without a licence, witchcraft and
  heresy, each by the local law. A crime needs a witness: a guard arrests you on the spot; anyone else goes to
  the watch within hours unless you persuade, pay or frighten them into silence. When the watch takes you, you
  can pay, go quietly, bribe, run or fight. Sentences range from a fine or jail (your belongings are held until
  you are released) to the lash, the brand, hard labour or the rope, and you can try to escape. A disguise kit
  hides your face.
- **Joining.** Ask a guild's, church's or order's people to swear you in (they need your good opinion, and
  sometimes a skill, a trade, a faith or a fee). Ranks rise with standing and bring better prices. The right
  question may find the thieves' guild or a cult. A ruler who honours you may grant you a title.
- **History.** Each world has 250 years of history: dynasties with their usurpers, wars and conquests, plagues
  and famines, ruins with a past, dragons (some slain, some only sleeping), legendary heroes and lost
  artifacts. Press **n** for News and history: the news you have heard, the chronicle of the land, and its
  legends. With the Player2 AI running, one background request per world writes the chronicle as a monk would.
- **The world moves on.** While you play, rulers age, sicken and die, and their heirs or usurpers follow.
  Neighbours go to war, fight battles, besiege and take towns (borders really change), and make peace. Vassals
  rebel, plague and famine come and go, tribes raid, cults spread and are rooted out, gangs rise and are
  hanged. All of it becomes news that travels about 24 miles a day: you hear it at inns, from travellers, and on
  the notice board (¶) in a town square, which also has wanted posters (perhaps your own) and the lord's
  orders. War makes food and arms dear and fills the roads with refugees and deserters. A besieged town is
  hungry. Plague can follow you out of a town.

**How to try it**
1. Double-click `Play.bat`, start a **New World** (older worlds get their factions and history when loaded).
2. Press **f** to see who rules, **n** for the news and the chronicle, **m** then **p** for the realm map.
3. In a town, walk into the ¶ board in the square. At the inn, ask for news.
4. Try your luck with **s** in a market, or pick a pocket, and see what the watch does.

**What to look for:** Does the world feel like it has a past and a present? Do the factions and their quarrels
make sense? Is the law too harsh or too soft? Is the news interesting, or too much?

**How it was verified**
- 449 automated tests pass. New ones cover: every size of world has its powers; the structure of realms; the
  realm map; saving; older worlds; starting knowledge; background ties; rulers in their seats; first
  impressions; borders; witnesses and reports; unseen crimes; no law in the wild; fines; sentences (jail, lash,
  brand, rope, escape); bribes and running; fighting the watch; recognition; disguise; deeds rippling;
  gangs angered; prisoners; settling debts; silencing witnesses; joining and ranks; titles; theft; pickpockets;
  contraband; history (rulers, conquests that agree with the map); the world moving on for years; succession;
  a war with a siege; plague coming and going; prices in hard times; news travelling at the right pace; news at
  the inn; notice boards; the chronicle, built-in and by the (mock) AI; and every new window at every size.
- Autoplay: thousands of turns with AI off and with the fake AI on several seeds. It now commits crimes in front
  of the watch (arrests, sentences, escapes) and checks the factions, the law's records, wars, sieges and news.
  No errors. A separate stress run of 30 years of live politics on three worlds found no broken state.
- The window smoke test now shows the factions, the realm map and the chronicle. Its tour is now free of random
  road encounters, which could hijack it.

**Decisions (and why)**
1. **Code decides all politics**; the AI only writes the chronicle (one request per world, in the background).
2. **History is told, not replayed onto the map.** The map of today is made first; history then runs the same
   politics engine over 250 years for grudges, wars and plagues, but only tells of conquests that agree with
   today's borders. Wars still being fought at the end of history are today's wars.
3. **The live simulation runs a week at a time** and is cheap (30 years in about a second).
4. **Deeds reach factions at the speed of news**, from where they happened to each faction's seat.
5. **Crimes are judged by the realm at the top of the chain of lords**; a bounty in one kingdom means nothing in
   the next.
6. **Towns you visited before this update** keep their old maps (no notice board); new towns have one.

**Known issues**
- Quests, work for guilds, and hunting dragons and lost artifacts come with M8. Membership gives prices and ranks
  for now.
- Companions: M7. Joining sieges and battles yourself is on the ideas list for after v1.
- The built-in chronicle is plain and list-like; the AI version reads much better.

---

## M5 — Settlements and people (done)

**What you can do now**
- **Towns are full of people.** Walking into a settlement (`>`) you find its innkeepers, priests, smiths,
  shopkeepers, healers (barber-surgeons in towns), stablemasters, headman or reeve or mayor or alderman
  (a thane in dwarven holds, an elder among elves), a lord in the keep of a city, market traders at their stalls,
  the watch, and ordinary folk: farmers, weavers, carters, washerwomen, beggars, fishers, woodcutters, miners.
  Each has a name from their people, an age, a personality (two traits), a purse, a home and a place of work.
  They keep to day and night: shops shut at dusk and most folk go home; the inn, the temple and the watch stay.
  Some wander the streets. New buildings: general stores, healers' houses and stables, and market stalls in
  towns. (Dwarven holds now have buildings too; they had none before.)
- **Talking** (walk into someone): who they are, what to know about the place (they name the other notable
  people), news and rumours (dangerous roads, and places you did not know, which go on your map), other people
  in town, threats (Intimidation), bribes, and one to three skill-check options. Outcomes come from a fixed list
  (information, liking you more or less, prices, a small gift, a fight, calling the watch, running off, a new
  topic), so nobody can promise what the game cannot deliver. **First impressions** depend on your clothes,
  cleanliness, bleeding wounds, race and background; people **remember** what you did (threats, bribes, help)
  and greet you accordingly. Hostile people won't talk. Fight townsfolk and the dead stay dead; the rest hate you.
- **With the Player2 AI running**: when you set out for a town or stand at its gate, one background request
  writes its description, its inn signs and full profiles of its notable people (looks, personality, speech,
  backstory, a secret, what they want). When you talk to a notable (at most once a day each), one request writes
  their opening line and proposes options that fit the person and the moment, e.g. "[Insight] She is hiding
  something about the bell". A short "…" appears; if the AI is slow, the built-in lines take over. AI words only
  ever replace text you have not seen.
- **Markets**: every merchant has stock and coin, restocks weekly, only buys their own trade, and won't touch
  stolen goods. Prices follow the land (salt cheap on the coast, iron in the hills, furs in the cold north, grain
  on the plains), trade goods are dear where nobody makes them, cities pay more for food, holds less for steel,
  winter food is dear, and the merchant's feelings and a daily haggle move them. **Trading pays**: in a test
  world salt bought on the coast sold inland for 2.8 times as much, furs 2.3 times, iron 1.8 times.
- **Services** ("What can you do for me?"): a bed in the common room or a private room (a safe night's sleep),
  hot meals, baths, performing for coin (Performance) and dice at the inn; healers treat all your wounds at once,
  operate on internal bleeding and sell herbal cures; priests pray for healing or to lift a sickness (for a
  donation); smiths mend weapons and armour; a day's paid work at the smithy, the stable or on a farm.
- **Animals**: mules (carry 200 lb for you), ponies, draft horses and riding horses from the stable. Riding makes
  open ground and roads quicker if everyone has a mount. They need a bag of fodder a day, or grazing outside
  winter; unfed they starve after a few days. Robbers take them. They show in the side panel.

**How to try it**
1. Double-click `Play.bat`, **Continue**. Press `>` in a town. Walk into people (the `☺` symbols).
2. Talk to the innkeeper: ask for news, then "What can you do for me?" for a meal or a bed.
3. Visit the smith or shopkeeper: "Let me see your goods", buy and sell with Enter, haggle with `h`.
4. Buy a mule at a stable (towns and cities) and see your carrying limit rise (`i`).

**What to look for:** Do towns feel alive? Are conversations readable? Are prices sensible, and is trading
worth it? If Player2 is running, do the AI lines fit the people?

**How it was verified**
- 382 automated tests pass. New: every kind of settlement has its people, none in walls or on top of each
  other; people are made once; shops close and folk go home at night; first impressions; walking into someone
  starts a talk; the menu and its answers; special options; threats remembered; bribes; fighting townsfolk; people
  survive saving; the AI requests list the right facts; AI words only replace unseen text; AI options are kept to
  what that person can deliver; a conversation with the (mock) AI; a slow AI falls back and late replies are
  ignored; heading for a town asks for its words; every kind of merchant has stock and coin; cities stock more;
  trade goods are cheap where made; winter food is dear; mood and haggling move prices; buying and selling;
  merchants only buy their trade and run out of coin; restocking; trading in conversation; shops survive saving;
  inns, healers, temples, smiths, labour; animals (carrying, riding, selling, starving, saving); hostile people
  offer nothing; every new window renders at every size.
- Autoplay: 10,000 turns with AI off and 10,000 with the fake AI on several seeds, now walking into towns and
  talking, trading and using services, checking townsfolk never stand in walls or on each other and shops never
  go below zero. No errors.
- The window smoke test now talks to a townsperson, and **always runs with the AI off** (it had been using the
  real Player2 app when it was running; that is fixed so tests never spend your AI energy).

**Decisions (and why)**
1. **Code names people** (from their culture's name lists) and decides everything mechanical; the AI writes only
   words, in one rich request per town and one per conversation, to spend Player2 energy sparingly. Towns merely
   passed on a journey are not asked about; ordinary folk use built-in text only.
2. **Conversation outcomes come from a whitelist** that is narrowed per person (no prices from a priest, no gifts
   from someone with nothing, no watch where there are no guards).
3. **Prices** are driven by production near each town rather than a full simulated supply chain; that gives real
   trade routes now. Caravans, war and famine moving prices arrive with the world simulation (M6).
4. **Animals add carrying capacity to the leader** rather than having their own packs, to keep the inventory
   simple.

**Known issues**
- Law, crime, bounties and reputation with factions come with M6 (for now, attacking townsfolk is only
  remembered by them and recorded in your deeds).
- Quests and work beyond day labour: M8. Recruiting companions: M7.
- Settlements visited before this update have no general store, healer or stable (their maps were already made);
  their people appear on your next visit.

---

## M4 — Body and survival (done)

**What you can do now**
- **Weather.** Rain, drizzle, storms, snow, blizzards, fog and heat waves roll across the map as moving fronts,
  on top of each place's climate (latitude, height, season, day and night). The side panel shows the weather
  where you are; the world map shows it for the whole land (`m`, then `w`). Weather slows travel, shortens how
  far you can see (fog!), soaks you, and follows you into fights (rain spoils bowshots, fog hides the enemy).
- **Your body over time.** Hunger, thirst, tiredness and dirt grow as you go (faster when walking, in the heat,
  or when shivering). **Body heat** comes from the air, wind, rain, what you wear (warmth, wind and rain
  protection of each layer), whether you are wet, what you are doing, shelter, bedding and fire. Clear stages
  with warnings: peckish → hungry → starving; thirsty → parched → dehydrated; chilled → cold → hypothermic →
  freezing; hot → overheated → heat exhaustion → heatstroke. **5e exhaustion** (levels 1–6) builds up from the
  worst of these, with its real effects (disadvantage, half speed, half hit points...), and level 6 is death.
  A night's sleep with food and water takes one level away.
- **Food and water.** Eating and drinking happen by themselves from your pack when needed (a setting you can
  turn off; then use Enter on food or a waterskin in the inventory). Waterskins hold 4 pints and weigh what the
  water weighs. Wells in towns are safe; rivers, lakes and marshes may give you dysentery or marsh fever unless
  you boil the water. Food spoils (fresh bread in days, rations in months); spoiled or raw food may poison you.
  `w` fills your waterskins, `W` washes.
- **Health (h).** Wounds from battle now live on: bleeding wounds lose blood until bandaged (small cuts clot by
  themselves; gushing ones kill in hours), dirty open wounds may **fester** and poison the blood, **broken
  bones** heal straight only if splinted, **critical** wounds and unset bones may leave **lasting injuries**
  (a scar, a scarred face, a lost eye, lost fingers, a weak arm, a limp, bad lungs). Healing takes days
  (minor), one to three weeks (serious, critical) or about a month (bones). **Pain** and **blood loss** make
  everything harder. Treat wounds on the Health screen: bandage, clean, stitch, splint, cauterize, poultice;
  poppy milk dulls pain (and can hook you); drink helps too (and leaves a hangover). Clerics can cast Cure
  Wounds, Healing Word and Lesser Restoration outside battle.
- **Ten diseases** (all in `data/diseases.json`): dysentery, food poisoning, wound fever, lung fever, marsh fever,
  camp fever, plague, filth fever, the frothing sickness (from animal bites: always fatal once it shows, unless
  magic cures it first) and grave rot (from the dead). Each has its own way of spreading, time before it
  shows, stages, treatments, chance of death and after-effects. Rest, warmth, clean water and herbs help you
  throw them off.
- **Effects that matter in a fight:** exhaustion gives disadvantage, a broken arm can't hold a weapon (and
  two-handed weapons need both arms), head wounds can make you black out, great pain can put you in shock.
- **Camp (r).** Light a fire (easy in woods, hard in the open, impossible in a storm without a tent; you need a
  tinderbox, and firewood where there is none), pitch a tent, eat, cook raw meat and fish, boil water, forage
  (1 hour), hunt (2 hours), fish (2 hours, at water), see to wounds, rest or sleep. A fire warms, dries, cooks
  and keeps most beasts off, but people see it from afar. Something may find you while you hunt or sleep; if
  it comes while you sleep, you are caught unawares.
- **After a fight with beasts** you can butcher the carcasses for meat, hides and furs.
- **The road.** Travel takes longer in bad weather, and when you are hurt, sick, starving or exhausted.
  **Off the road in fog, storms or darkness you can lose your way** (Survival); a road or clear weather brings
  you back. **Twelve kinds of travel event** (all in `data/travel_events.json`): a pedlar (buy food, water,
  bandages...), pilgrims, a patrol, refugees, a wounded traveller, an abandoned camp, hunters (buy meat and
  hides; learn where the game is), a fresh carcass, a wayside shrine, a patch of healing herbs, hungry
  deserters, a gibbet. Choices use your skills, cost or gain things, add to your deeds, and some turn into
  fights. **Each day of travel is written up in the log**: by the Player2 AI when it is running (one small
  request per day, in the background), otherwise from built-in text.
- Everyone now starts with two bandages. New items: spirits, poppy milk, healing herbs, roast meat, fish, porridge,
  wild food, firewood.

**How to try it**
1. Double-click `Play.bat`, **Continue**. Press `h` to see your Health screen and `r` for the camp.
2. Walk out of town into the wilds and keep going for a few days: watch the weather, the side panel, and the
   log at each new day. Try the world map's weather view (`m`, `w`).
3. Get into a fight (or use the debug console: `` ` `` then `fight wolf_pack`), then look at your wounds with `h`
   and treat them. Rest in camp with `r` → `l`.
4. Try a winter night in the open without a fire (it is dangerous), then with one.

**What to look for:** Is survival interesting or just busywork? Are the warnings clear before things get
deadly? Is the Health screen understandable? Are travel events fun? Do the daily passages read well?

**How it was verified**
- 329 automated tests pass. New: weather is deterministic, varied and plausible; seasons are smooth; fronts move;
  needs grow and sleep restores; a winter night outside is dangerous and a fire or shelter prevents it; rain
  soaks and fire dries; heat waves; starvation and thirst build exhaustion and kill; long rests need food;
  eating, drinking, wells, river sickness, spoiled food; death ends the game; the new body fields and waterskin
  contents survive saving; wounds bleed, clot, fester (dirty more than clean), heal over days and bones over
  weeks; unset bones leave limps; wound fever; diseases incubate, strike or pass, can be recovered from, and
  the frothing sickness kills unless magic cures it early; treatments use supplies and skill; cautery; splints;
  poultices; healing magic outside battle; poppy and withdrawal; drink and hangovers; penalties in skills,
  saves and attacks; broken arms; exhaustion in battle; health state survives saving; fire, cooking, boiling,
  camps breaking when you move; foraging, hunting, fishing; butchering; every travel event and option can be
  played; requirements; news; events on roads; getting lost in fog and found by a road; travel days written up
  with and without the AI (mock); every new screen renders at every window size.
- Balance simulations (200 characters each): a bandaged minor cut heals in under 2 days; an untreated serious
  cut kills about 1 in 11 (by festering), 1 in 100 if cleaned and bandaged; a gushing critical wound left alone
  is usually fatal, almost never if treated; broken legs take 3–4 weeks; plague kills about 1 in 6 hardy
  fighters. A soldier sleeping at -8°C with a blanket and no fire wakes hypothermic; with a fire, fine.
- Autoplay: 10,000 turns with AI off and 10,000 with the fake AI on each of two seeds, meeting fights and travel
  events, checking body values, wounds, diseases and waterskins stay within bounds. No errors.
- The window smoke test now visits the Health screen and the weather map.

**Decisions (and why)**
1. **Weather is computed, not stored**: a smooth function of the world seed, place and time. Fronts really
   move and saves need nothing extra; the same moment always has the same weather.
2. **Eating and drinking are automatic by default** (the pack is used when you are hungry or thirsty). Survival
   stays meaningful (supplies run out, water can be bad, food spoils) without tedious micromanagement. It can be
   turned off in Settings.
3. **Exhaustion** uses the 5e track as the design asks; for checks and saves outside true rolls it counts as -5
   (the 5e passive-check equivalent of disadvantage); in battle it is real disadvantage.
4. **Hit points stay stamina**: blood loss, pain, festering and sickness are the body's real state, and they are
   what kill you slowly. Hit points only drop at the extremes (freezing, heatstroke, sepsis, the worst diseases).
5. **Travel-day passages use the AI sparingly**: one small background request per day of travel, skipped when
   energy is low (the built-in text is used instead).
6. **Animals (mules and horses)** are left for M5, where they can be bought; the travel rules are ready for them.

**Known issues**
- A camp is not saved: if you quit while camped, the fire is out when you come back.
- Getting lost is not saved either (you know where you are after loading).
- Inns, baths, healers and surgeons arrive with towns (M5); plague outbreaks in towns with the world simulation.
- Companions (who can keep watch and treat each other) arrive in M7.

---

## M3 — Combat (done)

**What you can do now**
- **The wilds are dangerous.** While you walk, travel or wait outside a town, something may find you. The
  wilder the region (the "Wilds" line in the side panel), the more likely; night is worse and roads are a
  little safer. What you meet depends on the land: wolves and boars in the woods, bandits and deserters on
  the roads, the restless dead near ruins, orcs and ogres in the hills, a troll if you are unlucky.
- **Trouble on the road** gives you a choice before any blood is spilled: **Fight**, **Ambush** them (only
  if you saw them first), **Slip away** (a Stealth roll), or **Talk your way past** (Persuasion; animals and
  fanatics won't listen). It also tells you how dangerous they look, from "You could take them" to "This
  will very likely kill you".
- **Ruins, caves, barrows and towers are inhabited.** On their close-up maps the inhabitants show as
  letters; once they notice you they turn red and come for you. Walk into them to attack (catching them
  unawares if they hadn't seen you); if they reach you first and you hadn't seen them, *you* are surprised.
- **The battle screen**: your side and theirs, each in a front and a back rank, with health bars, the order
  of battle along the top and the battle log. On your turn: Attack, Cast a spell, Use an item, Class
  ability, Dodge, Help / first aid, Shove or grapple, Change rank, Parley, Surrender, Flee. Pick a weapon or
  spell, then a target (number keys, arrows, or click). Clicking an enemy attacks it straight away.
- **5e rules**: initiative, attack rolls against armour class, advantage and disadvantage (prone, helped,
  dodging, darkness, shooting while in melee, pack tactics...), critical hits, saving throws, sneak attack,
  second wind, action surge, fighting styles, racial traits (halfling luck, half-orc endurance, dwarven
  poison resilience). With "Show dice rolls" on (Settings), every roll is shown in the log.
- **Ranks**: melee reaches only the enemy front rank unless it is empty or you have a reach weapon; from the
  back you need a bow, a thrown weapon or a spell. Archers fall back to shoot; brutes push forward.
- **Where blows land**: every hit strikes a body part, described in plain grim words ("Aldith slashes
  Jocelyn across the left hand"). Hard hits leave **wounds**: cuts that bleed each round until bandaged,
  broken bones, bites. Armour on that part makes a wound less likely. Wounds stay after the fight (healing
  them over time comes with M4).
- **Falling**: at 0 hit points you go down and start **bleeding out**: a few rounds, fewer if hit again. A
  friend can stop it (Help, a healer's kit, or Spare the Dying). Monsters simply die.
- **Morale**: badly hurt enemies, and bands that lose half their number or their leader, may break. Beasts
  run; bandits and soldiers may throw down their weapons; fanatics and the dead never do.
- **Surrender and robbery**: bandits, thugs and deserters take prisoners. If they beat you (or you
  surrender), they take your money and your best valuables and leave you alive. Wolves, the dead and
  cultists do not take prisoners.
- **Spells**: wizards and clerics cast from spell slots (cantrips are free): Fire Bolt, Magic Missile, Sleep,
  Burning Hands, Thunderwave, Shield, Mage Armor; Sacred Flame, Cure Wounds, Healing Word, Bless, Guiding
  Bolt, Command and more; higher levels up to Fireball, Spirit Guardians and Cone of Cold (35 spells). Turn
  Undead for clerics from level 2.
- **After the fight**: what the field looks like, experience (shared out; **levels go up automatically**
  with more hit points and new features), the fate of **prisoners** (let go, rob, question, kill; taking them
  for a bounty needs M6) and the **spoils** (take all, mark and take some, or leave the rest; on a close-up
  map what you leave stays on the ground).
- **Rest** (`r`): a short rest (an hour, spend hit dice to heal) or a long rest (eight hours: full hit
  points, spell slots and features back). A long rest in the wilds can be interrupted.
- **Death is permanent.** A death screen tells how, where and when, what you killed and what you did. The
  world stays; start a new character in it from the title screen. (The AI-written obituary is M9.)
- 22 kinds of creature in 23 encounter groups, all from data (`data/creatures.json`), with original
  descriptions; rules numbers follow the SRD 5.1.

**How to try it**
1. Double-click `Play.bat`, **Continue** (or make a new world). Walk out of town into country marked
   "dangerous" or worse, and wait (`.`) or travel at night. Or find a ruin or cave on the world map (`m`),
   go there and press `>`.
2. In battle, try `a` then Enter then `1`; try `c` as a wizard or cleric; try `p` against bandits.
3. Afterwards press `r` to rest.
4. (Testing shortcut: the debug console, the backquote key left of 1, has `fight bandits`, `fight list`,
   `heal`, `gold 50` and `xp 300`.)

**What to look for:** Are fights readable? Is the pace of enemy turns right (about half a second each; any
key hurries them)? Are level-1 fights too hard or too easy? Is anything in the battle screen confusing?

**How it was verified**
- 261 automated tests pass. New: battles against seven kinds of foes over many seeds always finish with sane
  numbers; every class can fight; initiative order; the same seed gives the same fight; ranks limit melee;
  going down, bleeding out and first aid; wounds from heavy hits; bandits surrendering and fleeing; fanatics
  and undead never breaking; parley and surrender rules; fleeing sometimes working; wizard slots, cantrips,
  Sleep; cleric healing and Turn Undead; Second Wind; potions; XP and level-up; short and long rests; a whole
  encounter to victory with loot and XP; defeat by bandits meaning robbery and by wolves meaning death;
  prisoner fates; slipping away and talking; encounter odds; inhabited sites surviving a save; fights played
  through the screens at every window size and against every encounter group; the death screen; broken
  creature data being reported on the data-error screen.
- Balance check (200 simulated fights each, a level-1 fighter alone): one wolf 83% won, two bandits 80%, three
  bandits about 40%, two wolves 28%. The design's target is that two wolves or three bandits are "a real
  threat" at level 1; a lone character also has evading, talking, fleeing and surrender. Groups are scaled
  down for a party of one until companions arrive (M7).
- Autoplay: 20,000 turns with AI off and 20,000 with the fake AI (plus 4,000 each on another seed), now
  starting about one fight every 150 turns and checking during battles: hit points in range, valid states,
  creatures never standing in walls, the dead never walking on. No errors.
- The window smoke test now meets bandits on the road and screenshots the encounter, the battle screen, the
  attack menu and target choice.

**Decisions (and why)**
1. **One action per turn**, no reactions, bonus actions, opportunity attacks or concentration (the design's
   v1 simplification). Fleeing is a group roll instead of movement. Ranged attacks from the front rank while
   engaged have disadvantage instead of provoking.
2. **Hit locations and wounds** use the design's list (head, torso, arms, legs); armour lowers the chance a
   hit becomes a wound rather than the damage. Severity scales with the share of hit points lost.
3. **Robbers keep you alive** (bandits, thugs, deserters); beasts, the dead and cultists kill. This makes
   defeat a setback rather than the end in many fights, as the design's "surrender" option intends.
4. **Enemy groups are scaled to party size** (a lone character meets smaller bands). Once companions exist
   (M7) full bands appear.
5. **Levels go up automatically** with sensible choices (average hit points, the class's features); choices
   such as subclass and spells can be revisited when M7 adds the full levelling screen.
6. **Knowledge checks**: at the start of a fight the party's best Nature/History/Religion roll decides whether
   you know an enemy's exact numbers; otherwise you only see "wounded", "badly hurt" and so on.

**Known issues**
- Quitting in the middle of a fight doesn't save the fight: you continue from just before it (inhabitants
  of a close-up map keep any hurts you gave them; a band met on the road is gone).
- ~~Wounds don't heal, fester or bleed outside battle yet~~: done in M4.
- ~~Only hostile encounters for now~~: travel events added in M4.
- Prisoners can't be taken to a town for bounty or ransom yet (M6).
- One character only; companions (and fighting side by side) arrive in M7.

---

## M2 — Character (done)

**What you can do now**
- After **New World** (or **New Character** on the title screen, for a world without a living character),
  you create your character in eight steps. Each step starts with a sensible choice, so you can press
  **Enter** through anything you don't care about:
  1. **People:** Human (Heartland, Northmarch or Southron culture), Elf, Dwarf, Halfling, Half-Orc, with their
     traits (darkvision, dwarven resilience against poison, halfling luck, half-orc endurance...).
  2. **Calling:** Fighter, Rogue, Cleric, Wizard, with hit dice, saves, proficiencies and features.
  3. **Background:** Soldier, Acolyte, Criminal, Folk Hero, Noble, Sage, Outlander, Guild Artisan: skills,
     tools, gear, money, a background feature, and **social ties**.
  4. **Abilities:** 5e point buy (27 points, 8–15), racial bonuses on top, "S" for a suggested spread.
  5. **Skills & training:** class skills, Rogue expertise, Fighter fighting style, Cleric domain (Life/War),
     and a choice of equipment kits.
  6. **Who you are:** name (type or random), sex, age, looks, and a backstory with personality, ideal, bond
     and flaw. Press **W** to have the Player2 AI write it (one request, about 2 energy), or use built-in text.
  7. **Where you start:** three or four real places in the world that suit your background.
  8. **Begin.**
- **Social ties are real places and people:** a soldier served a named lord whose seat is a real town; a
  criminal has a fence in one town and a bounty in another; a noble belongs to a house seated nearby; and so
  on. (The people and houses become full characters and factions in M5/M6.)
- **Character sheet** (`c`): abilities, saves, all 18 skills (● trained, ♦ expert), HP, AC, speed,
  initiative, passive perception, proficiencies, traits and features, ties, looks, backstory.
- **Inventory** (`i`): everything you carry with weight, value, condition and how long food keeps; filter by
  type, sort, wear/wield/remove, drop. Items lie where you drop them (on the close-up maps) and stay there;
  `g` picks them up.
- **Equipment** (`e`): a paper doll of slots (hands, armour, helmet, cloak, clothes, underclothes, hat,
  gloves, footwear), a body diagram showing which parts your armour protects, total warmth, wind and rain
  protection, and how respectable you look.
- **Weight matters:** 5e carrying limits. Worn armour and clothes count half. Over your limit you walk slower
  (journeys take longer); far over it you can't move. Dwarves and halflings walk a little slower too.
- The side panel shows your HP bar, AC, money and whether you are laden.
- Over 100 base items from data: all 5e weapons and armour, helmets, clothing layers with warmth, gear,
  tools, food (with spoilage) and trade goods.

**How to try it**
1. Double-click `Play.bat`, **New World**, Enter. Walk through the character steps (try the arrow keys
   on each one, and **W** on step 6 if you want an AI backstory).
2. In the game press `c`, `i` and `e`. In the pack, select an item and press Enter to take it off/put it on.
3. Press `>` to enter the land, then in the pack press `d` to drop something, walk away and come back, `g` to
   pick it up.

**What to look for:** Is creation clear? Are the defaults sensible? Is anything on the sheets confusing?

**How it was verified**
- 176 automated tests pass (added: every race × class builds with its defaults, spends all points, starts
  dressed, armed and not overloaded; point-buy limits; racial bonuses and traits; skills and expertise; armour
  class rules; two-handed weapons and shields; stacking; carrying limits slowing and stopping you; clothing
  warmth and status; character save round trip; every background's ties point at real places; dropping and
  picking up; items on the ground surviving a save; an M1-era save still loading).
- Autoplay: 5000 turns with AI off and 5000 with the fake AI, now also creating characters (including AI
  backstories from the fake server), using the character sheet, inventory and equipment screens, and checking
  after every action: HP in range, no negative money, no zero-sized stacks, nothing worn twice, nothing worn
  that isn't carried. Save/load round trips identical. No errors.
- The window smoke test now goes through character creation, the character sheet, inventory, equipment and a
  local map.

**Decisions (and why)**
1. **Worn armour and clothes count half toward carrying limits**, and everyone starts with a blanket (not a
   7 lb bedroll) and two days' rations. With the 5e variant limits, most characters otherwise started
   over-burdened. Weak characters are still close to their limit, which is realistic.
2. **Subclasses:** Fighter Champion/Knight and Rogue Thief/Cutthroat unlock at level 3; Cleric Life/War domains
   at level 1; Wizard Evocation/Abjuration at level 2. The Knight and Cutthroat are simplified originals in
   the spirit of the design's examples. Spells arrive with combat (M3) and levelling (M7).
3. **Backgrounds, features and descriptions are original text**; the 5e rules (point buy, skills, weapon and
   armour stats) follow the free SRD 5.1 (Creative Commons licence; credit added in `docs/CREDITS.md`).
4. **Saves moved to format 2** (characters). M1 saves still load and get a ready-made wanderer.
5. Sex is male/female as the design lists; pronouns in built-in text follow it.

**Known issues**
- ~~Spells can't be cast yet~~: done in M3.
- Items in the overworld can't be dropped (enter the land first); by design for now.

---

## M1 — World and movement (done)

**What you can do now**
- **New World** on the title screen: pick a name, a seed (same seed = same world), a size (Small / Medium /
  Large), danger and magic levels. The land forms on screen in a few seconds.
- Worlds have a coastline, mountain ranges, hills, forests and pine woods, marshes, a frozen north, lakes,
  and rivers that really run downhill to the sea. Every region, lake and major river has a name.
- Cities, towns, villages, hamlets, dwarven holds and elven halls, placed where people would actually settle
  (rivers, coasts, good farmland), each with a culture (Heartland, Northmarch, Southron, Elven, Dwarven,
  Halfling). Roads join them. Old ruins, caves, barrows and towers lie in the wilds.
- You start as **The Wanderer** (a placeholder until character creation in M2) in a town or village,
  knowing your home district and the roads out of it.
- **Walk the overworld** (arrows / number pad / Home PgUp End PgDn). Each step takes game time:
  about 45 minutes on a road, an hour or more across country, four hours or more in mountains, extra
  to wade a river. Lakes and the sea block you.
- **Enter the land** (`>`) to see any tile up close: town streets, walls and gates, houses with beds,
  hearths and tables, inns, temples, smithies, fields, graveyards, rivers with bridges or fords,
  lakeshores, ruins. Doors open when you walk into them. Walk off the edge or press `<` to leave.
- **Look** (`l`, or hover the mouse) at anything for a description: land type, region, rivers, roads,
  height, how cold it usually is this month, and how dangerous the wilds are.
- **World map** (`m`, `z` to zoom out) and **Travel** (`t`): pick a destination, see the distance and
  walking time, and set out; the journey plays out step by step and any key stops it.
- **Day and night:** a calendar with named months and weekdays; the map darkens and cools at dusk, and on
  foot you see much less at night. In woods you see only about ten steps around you.
- **Message log** at the bottom (`L` for the full history), **map legend** (`/`), **menu** (`Esc`).
- **Saving:** automatic (every few minutes, on entering or leaving places, when you quit). **Continue** on
  the title screen picks up where you left off. Several worlds can exist side by side.

**How to try it**
1. Double-click `Play.bat`, choose **New World**, press Enter.
2. Walk around; press `>` in a town to walk its streets; press `m` then `z` to see the world.
3. Press `t`, move the cursor to a far town, press Enter, then `Y` to travel.
4. Press `Esc`, choose *Save and return to the title screen*, then **Continue**.

**What to look for / tell me about:** does the world look believable? Are travel times and sight ranges
fun? Is anything hard to read (colours, symbols)? Which parts feel dull or confusing?

**How it was verified**
- 135 automated tests pass (added: same seed gives the same world; rivers always reach water; settlements on
  land; roads connect at least 80% of towns; a sensible mix of land types over several seeds; local maps
  repeatable and enterable; calendar; moving, doors, travel; save then load gives back exactly the same
  game; broken or newer saves are refused politely).
- Autoplay: 4000 turns with AI off and 4000 with the fake AI, creating worlds, walking, travelling and
  entering towns, checking after every action that you stand on walkable ground and that time never runs
  backwards; 14 save/reload round trips, all identical. No errors.
- The real window was opened by the smoke test (title, new world, walk, look, local map).

**Decisions (and why)**
1. **Map cells are taller than wide** (it is a text font). Noise on local maps is squashed vertically so
   patches look round on screen. The overworld reveal area looks slightly oval for the same reason.
2. **Overworld tile = 3 miles**; walking speeds follow 5e travel pace (roughly 24 miles in 8 hours on roads).
3. **Local maps are 96×60 cells**, generated on the first visit and stored in the save (doors you open stay open).
4. **Place names, region names and descriptions use built-in text in M1.** With the Player2 energy budget,
   AI writing is best spent on people and conversations; AI place descriptions will be batched (several
   places per request) when towns come alive in M5.
5. **Sight:** single trees and boulders do not block your view (only walls, doors and thickets do); in forests
   and marshes you simply see a short distance all around.
6. **Roads are drawn straight (north-south and east-west) with box lines**, as in Dwarf Fortress.
7. Weather, needs, encounters and daily travel narration arrive with M4 (survival), as the design orders.
8. Saves are zip files (JSON plus plain number arrays), versioned, with a place for future upgrades.

**Known issues**
- The overworld's unexplored areas are plain black; fine for now.
- Coastlines on local maps can look a little blocky.

---

## M0 — Setup (done)

**What you can do now**
- Double-click `Play.bat`. A window opens (maximized) with the title screen and menu.
- **Player2 Connection Test** (press `P`): shows whether Player2 is running, the health ping,
  your remaining AI energy, and request counts. Press `G` to have the AI write a sample tavern
  (name, sign, description, keeper, a line of overheard talk). Press `O` to pretend Player2 is
  closed and see the built-in text instead, or actually close Player2 and press `G`.
- **Settings** (`S`): text size, fullscreen, dice display, AI on/off, text detail, autosave, AI debug log.
- Anywhere: `Ctrl +` / `Ctrl -` text size, `F11` fullscreen, `F12` screenshot, `F1` help.
- `Build_For_Friends.bat` makes `Realmwalker.zip` (about 34 MB). Friends unzip and double-click `Realmwalker.exe`.

**How it was verified**
- 107 automated tests pass (dice, RNG, data validation, AI parsing and fallback, AI service against a fake
  Player2 server in every failure mode, all screens at four window sizes, error recovery, settings).
- Autoplay bot: 3000 turns with AI off and 3000 with a deliberately unreliable fake AI — no errors.
- Real window opened and toured by the smoke test; `Play.bat` launched it; the packaged `.exe` started too.
- One real Player2 generation succeeded: *"The Wet Whetstone"*, keeper Ragnvald Ormsson, a carter
  "found under the switchbacks, throat cut and boots gone" (784 tokens, ~8 s, ~2 energy).

**Decisions (and why)**
1. **Player2 via the local app API, no client ID.** The local API works without one; the header is supported
   if a client ID is ever put in `config.json`. Simplest for you and for friends.
2. **No `response_format` JSON mode** — with it, the current Player2 model returned empty replies. We ask for
   JSON in the prompt and parse it defensively instead.
3. **Generous token allowance (3000) for AI requests.** The model "thinks" silently before answering; with a
   900 cap it thought until the cap and returned nothing, *twice, costing 4 energy*. Empty replies are no
   longer retried automatically (a retry costs the same again).
4. **AI energy is very limited** (see "Needs your attention"). Background pre-generation pauses when energy is
   below 6; text the player is waiting for still uses it. Later milestones will spend AI only on what matters
   most (notable people, conversations, big moments) and use built-in text for the bulk.
5. **Font:** DejaVu Sans Mono (free licence) rendered into a CP437 tileset at runtime, with hand-drawn
   box lines and shading, so any text size works. Letters are taller than wide (like Brogue / Caves of Qud).
6. **Python 3.12** installed alongside your existing Pythons (3.10/3.11/3.13 untouched), in its own `.venv`.
7. Player settings live in `%APPDATA%\Realmwalker\settings.json`; logs in the project's `logs\` folder when
   run from source, and in `%APPDATA%\Realmwalker\logs` for the packaged game.
8. Debug console on the <code>`</code> key (commands: `help`, `ai on|off`, `offline on|off`, `ping`, `status`,
   `font N`, `test-error`). Switched off in friend builds.

**Needs your attention (when you have a moment)**
- **Player2 energy:** your account showed 10 energy at first, and testing used 7. After the daily refill it showed
  **91**, so there is far more room than first feared (a rich AI request costs about 2). Nothing to do.

**Known issues**
- None open.

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
