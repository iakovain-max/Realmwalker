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
- [x] D.1 Cantrips to 2nd level (134 spells): new ops first, then batches; fx for each; arena coverage green.
  Decided while building: each wave brings the spells that work in a fight; a spell whose use is outside a
  fight comes with the system it plugs into in Part E (its entry, scroll and codex mark together), and the
  summoning spells with Part F. From this wave, waiting for E: dancing lights, druidcraft, elementalism,
  friends, light, mage hand, mending, message, minor illusion, prestidigitation, thaumaturgy; alarm,
  comprehend languages, create or destroy water, detect evil and good, detect magic, detect poison and
  disease, disguise self, feather fall, goodberry, illusory script, jump, longstrider, purify food and drink,
  silent image, speak with animals, Tenser's floating disk, unseen servant; aid (a raised maximum that
  outlives the fight), alter self, animal messenger, arcane lock, augury, beast sense, continual flame,
  darkvision, detect thoughts, enhance ability, enthrall, find traps, gentle repose, knock, levitate, locate
  animals or plants, locate object, magic mouth, Nystul's magic aura, pass without trace, rope trick, see
  invisibility, spider climb, zone of truth. Waiting for F: find familiar, find steed, summon beast.
- [x] D.2 3rd to 5th level (128; Counterspell is in already, B.4). Dispel Magic with the Abjurer's Spell Breaker: a
  bonus action for them, their proficiency added to its check, the slot kept when it ends nothing.
  Built: 66 battle spells (23 of level 3, 22 of level 4, 21 of level 5) on new kernel pieces (sent away and back,
  dispelling, auras shared with friends, Confusion, Haste, Slow, Blink, ground that holds or sickens, walls). The
  2024 Conjure spells are not creatures: they are ground or auras and came now. Waiting for E: clairvoyance,
  create food and water, daylight, feign death, gaseous form, glyph of warding, Leomund's tiny hut, magic circle,
  major image, meld into stone, nondetection, phantom steed, plant growth, remove curse, sending, speak with dead,
  speak with plants, tongues, water breathing, water walk; arcane eye, control water, divination, fabricate,
  hallucinatory terrain, Leomund's secret chest, locate creature, Mordenkainen's faithful hound, Mordenkainen's
  private sanctum, stone shape; awaken, commune, commune with nature, contact other plane, creation, dream, geas,
  hallow, legend lore, mislead, modify memory, passwall, Rary's telepathic bond, raise dead, reincarnate, scrying,
  seeming, teleportation circle, tree stride. Waiting for F: animate dead, summon fey, summon undead; giant
  insect, polymorph (the beasts it turns into come with F's stat blocks), summon aberration, summon construct,
  summon elemental; animate objects, planar binding, summon celestial, summon dragon.
- [x] D.3 6th and 7th level (55). Battle spells (27): blade barrier, chain lightning, circle of death, conjure fey
  (2024: a spirit that strikes, a token), disintegrate, eyebite, flesh to stone, globe of invulnerability, harm,
  heal, mass suggestion, Otiluke's freezing sphere, Otto's irresistible dance, sunbeam, true seeing, wall of ice,
  wall of thorns; conjure celestial (2024: a pillar of light, ground that heals friends and sears foes), delayed
  blast fireball, divine word, finger of death, fire storm, forcecage (the solid box), Mordenkainen's sword, power
  word fortify, prismatic spray, reverse gravity. New kernel pieces: a bolt that
  leaps (`leap`), dust, a lowered maximum, the three saves of stone, a spell ward, dancing, true sight, ground of
  blades, thorns, celestial light and ice, the forcecage, banished for good, effects by hit points left, slaying,
  falling upward, a random ray, shared temporary hit points, a conjured thing's hit that frightens. Waiting for E:
  arcane gate, contingency, Drawmij's instant summons, find the path, forbiddance, guards and wards, heroes' feast,
  magic jar, move earth, programmed illusion, Tasha's bubbling cauldron, transport via plants, wind walk, word of
  recall; etherealness, mirage arcane, Mordenkainen's magnificent mansion, plane shift (the 2024 spell only
  carries willing travellers; its old banishing touch is gone), project image, regenerate (cast in a minute), resurrection, sequester, symbol, teleport. Waiting for F: create undead, planar ally, summon fiend,
  simulacrum.
- [ ] D.4 8th and 9th level (34), Wish (its safe uses and its stress) and Meteor Swarm; Part D to `main`.
  Battle spells (20): antimagic field (an emanation that moves with its caster), befuddlement (no spells for a
  day), dominate monster, earthquake (ground that throws down and breaks concentration), holy aura, incendiary
  cloud, maze (away until a DC 20 Intelligence check), mind blank, power word stun, sunburst; foresight, mass heal (700 hit points shared), meteor swarm (four spheres, each creature once), power word
  heal, power word kill, prismatic wall (a wall foes cannot pass, blinding glare beside it), storm of vengeance (a
  storm by its turns), time stop (turns in a row until you touch another), weird, and Wish: in a fight it copies
  any battle spell of level 8 or lower without its components (safe), or gives Instant Health to up to twenty
  friends (the stress: 1d10 necrotic a spell level for every spell until a long rest, Strength 3 for 2d4 days, a
  third of the time never Wish again). Waiting for E: antipathy/sympathy, clone, control weather, demiplane,
  glibness, telepathy, tsunami (cast in a minute); astral projection, gate, imprisonment (cast in a minute), true
  resurrection, and Wish's other uses outside a fight. Waiting for F: animal shapes, shapechange, true polymorph.

### Part E — Spells outside battle
The spells that waited for Part E, sorted (2026-10-17, at the start of E.1). Spells of one system go together, so a
system is built once and every spell that uses it comes with it.
- [x] E.1 Healing, return from death, food and the body, shelter and watch (19 spells, and Revivify on the road).
  Healing: aid (a raised maximum that outlives the fight; in a fight too), regenerate, remove curse. Return from
  death: revivify, gentle repose, raise dead, reincarnate, resurrection, true resurrection (a fallen companion's body
  is carried while someone in the party could raise it; companions raise a fallen leader at once if they can). Food
  and the body: goodberry, create or destroy water, purify food and drink, create food and water, heroes' feast.
  Shelter and watch (wards on the camp): alarm, Leomund's tiny hut, rope trick, Mordenkainen's faithful hound,
  Mordenkainen's magnificent mansion.
- [x] E.2 Light, the body on the move, travel (34 spells). E.2 was split in two at its start (2026-10-17): 64
  spells in six groups were too many for one part; finding and seeing, asking the powers and talking became E.3.
  Light: light, dancing lights, continual flame, daylight. The body on the move: darkvision, see invisibility, jump,
  longstrider, feather fall, spider climb, levitate, water breathing, water walk, gaseous form, meld into stone,
  feign death, alter self, enhance ability, pass without trace. Travel: phantom steed, Tenser's floating disk, unseen
  servant, wind walk, transport via plants, tree stride, teleport, teleportation circle, word of recall, arcane gate,
  find the path, plane shift, etherealness, astral projection, gate.
  How (the design, at the start of E.2):
  - Most of the body's spells are lasting buffs (a spell of ten minutes or more is kept on the character, carried into
    any fight: rules/spells.lasting), read by new keys outside a fight and by the battle inside one: `light` (squares
    of light: Light, Daylight; the dungeon's light, the close view at night, a fighter's glow), `darkvision` (feet),
    `see_invisible`, `speed` (Longstrider: the sheet's speed, so the road is quicker too), `climb` (Spider Climb: a
    Climb Speed equal to the Speed), `swim` (Alter Self's gills), `skills` ({skill: bonus}: Pass without Trace's +10
    Stealth, for creeping, slipping away and hiding), `check_adv` (Enhance Ability: Advantage on checks with the
    target's best ability; outside a fight +5 to its skills, the passive rule), `carry` (Tenser's Floating Disk: 500
    pounds more before the caster is laden), `steed` (Phantom Steed: its rider travels 13 miles an hour), `servant`
    (Unseen Servant: the camp's chores take half the time), `water_walk` and `water_breathing` (fords cost nothing and
    nobody gets wet; lakes and the sea can be walked over with Water Walk, lakes walked under with Water Breathing,
    at half pace), `wind` (Wind Walk: the party flies, ten times a walker's pace, over anything, and nothing on the
    ground meets it), `ethereal` (Etherealness: nobody on the road meets the party, and in a dungeon walls and doors
    do not stop it and traps do not spring; chests cannot be touched), `pathfinding` (Find the Path: nobody loses the
    way, and in a dungeon the way to the stairs is shown).
  - In a fight: Dancing Lights lights a 20-foot patch of the field (a zone "lights"); Daylight also ends magical
    Darkness of level 3 or lower (op `undark`); Jump lets a leap of 30 feet (`leap`); Feather Fall is cast as a reaction
    by whoever has it ready when a friend falls (and in a dungeon's pit); Levitate lifts a foe 20 feet that fails a
    Constitution save (the `lift` op with `gentle`: no ceiling, a soft landing); Gaseous Form makes a friend a slow
    mist that cannot be hurt much, attack or cast (`mist`: for running); Feign Death takes a willing friend out of
    the fight, lying as if dead (sent away, "feign"), back on their feet when it ends; Tree Stride steps from tree to
    tree, again each turn (`near: "tree"` on the teleport op, and its `again`).
  - Travel by magic is `game/waymagic.py` (road op `does` "travel" with `how`): Teleport (the book's table by
    familiarity: a permanent circle known, the town the character comes from or a town stayed in, a town visited, a
    town only heard of; mishaps do 3d10 force and roll again, a similar place is the nearest town of the same kind, off
    target lands 2d12 miles away), Teleportation Circle (to a city's circle: its sigils are learned by visiting it),
    Word of Recall (cast once in a temple town to make it the sanctuary; then back to it from anywhere, with five
    more), Transport via Plants (from woodland to a visited place with woodland beside it), Plane Shift, Astral
    Projection and Gate (until the planes come in Expansion 26: Plane Shift goes by way of another plane to a city's
    circle, or near another known place; Astral Projection and Gate to any known place, on target), Arcane Gate (in a
    dungeon, a gate to the stairs up or down within 500 feet). Etherealness and Wind Walk are lasting buffs (above);
    Meld into Stone is a ward on the camp ("meld": a lone caster rests hidden from hunters).
- [x] E.3 Finding and seeing, asking the powers (answered from the world's history), talking (30 spells).
  Finding and seeing: detect magic, detect evil and good, detect poison and disease, find traps, locate object, locate
  creature, locate animals or plants, clairvoyance, arcane eye, scrying, beast sense, Drawmij's instant summons.
  Asking the powers: augury, divination, commune, commune with nature, contact other plane, legend lore. Talking:
  comprehend languages, tongues, speak with animals, speak with dead, speak with plants, message, sending, animal
  messenger, dream, telepathy, Rary's telepathic bond, detect thoughts.
  How (the design, at the start of E.3; numbers from the 2024 PHB, build/e3_facts.json while building):
  - Finding and seeing and asking the powers are `game/divining.py`, talking `game/speech.py`; road ops `does`
    "sense" (`what`: magic, evil, poison, traps), "locate" (object, creature, nature), "scout" (room, level, scry,
    beast), "summons", "ask" (`how`: augury, divination, commune, nature, other_plane, lore), "speak" (dead, plants),
    "send" (message, sending, animal, dream, telepathy). A spell aimed at something chosen has target "subject": the
    Spells page lists Subjects (a question, a person, a thing to seek, a corpse, a companion far away) as it lists
    places. What is sensed on a close-up map is marked there for the spell's time (`game.sensed`, not saved).
  - Sensing: Detect Magic names the unknown magic in the packs by its aura and marks the chests within 30 feet that
    hold magic; Detect Evil and Good the aberrations, celestials, elementals, fey, fiends and undead within 30 feet not
    behind stone (and says when the ground is a haunted battlefield or a tomb); Detect Poison and Disease the sickness
    still hidden in the party, the foul food and water carried, poison traps and venomous bands within 30 feet; Find
    Traps every trap within 120 feet in sight, by its nature (the book: not where): the party finds them with
    Advantage on a search and saves against them with Advantage.
  - Locating (on a close-up map, 1,000 feet): Locate Object a chest, the hoard or the work's lost thing on the level;
    Locate Creature the work's person, captive or quarry, or anyone met in this town; Locate Animals or Plants the
    nearest game or herbs within 5 miles (the next hunt or forage +5) and a hunted beast's patch.
  - Seeing from afar: Clairvoyance the nearest rooms not yet seen and who is in them; Arcane Eye the whole level but
    behind secret doors, and its bands; Scrying a figure of the world (the book's save: Wisdom against the DC, +5 for
    one only heard of, +0 met, -5 known well; a possession -4, a body part -10): where they are now, added to the map;
    Beast Sense a party animal ranging ahead for an hour (the band met is seen first).
  - Drawmij's Instant Summons binds a carried thing to its sapphire; what robbers, a thief at an inn or the watch take
    comes back when the sapphire is crushed (they keep it in a sack or a strongbox, not in hand: adapted); what was
    sold or given away does not.
  - Asking: Augury reads weal or woe from what truly waits (the level below, the road ahead, a work in hand and its
    hidden side); Divination answers one question about a work truly (its hidden side, where its thing or person is);
    Commune asks three yes-or-no questions made from the world (does someone live, does an artifact lie somewhere, does
    a dragon sleep, is a work as told); Contact Other Plane five, after a DC 15 Intelligence save (6d6 psychic and
    senseless until a long rest on a failure), sometimes "unclear"; Commune with Nature tells the land within 3 miles
    (one map tile: sites, water, lairs, game and herbs) or 300 feet under the ground (the level's map and its folk);
    Legend Lore the legend of a person, place or thing: a carried storied thing is known through and through, a lost
    artifact's resting place, a named beast's lair and what harms it, a site's depth and its master. Repeated before a
    long rest, each casting after the first has a growing 25% chance of a muddled answer (augury, divination,
    commune, contact).
  - Talking: a language rule for words on the road: a band whose tongues nobody in the party speaks cannot be talked
    past (only gnolls and trolls today), unless someone has Tongues; Comprehend Languages makes it harder (+5) rather
    than impossible. Speak with Animals lets beasts be talked past (lasting, ten minutes). Speak with Dead asks a foe
    slain in the last fight where their band keeps its lair and who sent them (the lair goes on the map; a work's
    hidden truth may come out). Speak with Plants tells what passed in the last day (the next band is seen first) and
    where food grows. Message calls a companion waiting in the same town; Sending, Telepathy and Animal Messenger (25
    miles a day, 50 for a bird; its reach by its duration) send a waiting companion on their way to you; Dream does
    the same at night, or sends a nightmare to a named beast or dragon of a work (3d6 psychic, no rest: it starts the
    next fight hurt). Rary's Telepathic Bond: while it lasts no one in the party is surprised unless all are. Detect
    Thoughts in a fight senses thinking creatures within 30 feet (the invisible and the hidden found); outside one it
    reads a person near you (Wisdom save): what they feel about you, and a work's hidden side if they gave it.
- [ ] E.4 Minds and the law, disguise and illusion, the small arts (27 spells). The old E.4 was split in two at its
  start (2026-10-17): 54 spells and Wish in seven groups were too many for one part; the spells of townsfolk and the
  law (minds, disguise and illusion, the small arts) are E.4, locks and stone, weather and land, lasting protections
  and great magic became E.5. Minds and the law: friends, enthrall, zone of truth, geas, modify memory, glibness,
  antipathy/sympathy, awaken. Disguise and illusion: disguise self, seeming, minor illusion, silent image, major
  image, programmed illusion, project image, mislead, hallucinatory terrain, mirage arcane, illusory script, magic
  mouth, Nystul's magic aura, nondetection, sequester. The small arts: druidcraft, elementalism, prestidigitation,
  thaumaturgy.
  How (the design, at the start of E.4; numbers from the 2024 PHB):
  - The new module is `game/glamour.py`: road ops `does` "mind" (`how`: friends, enthrall, truth, geas, memory,
    antipathy, awaken), "illusion" (`how`: distract, decoy, veil, project, script, mask, sequester) and "art" (`how`:
    druidcraft, elementalism, prestidigitation, thaumaturgy), listed in `spells.E4_KINDS` and checked at start-up.
    Spells aimed at someone or something list Subjects, as E.3's do (a person near you, a party animal, a kind of
    creature, a carried thing, a town far away). A conversation takes no time in this game, so a spell of a minute
    lasts for the conversation that follows (ten minutes of the world): its record is a time on the person
    (`npc.flags`) or in `renown.flags`, both saved.
  - Minds: Friends (a person within 10 feet, Wisdom save; not twice in a day) makes them Friendly for the talk
    (Advantage on Influence); when it ends they know, and like you less (-20). Enthrall: everyone of your choice within
    60 feet who fails a Wisdom save has -10 to Perception for a minute: they are no witnesses to a theft or a crime,
    a merchant watches your hands at -10, and creeping past them is easier. Zone of Truth (a person, Charisma save):
    they cannot lie for ten minutes: a work they gave you that hides something is shown for what it is, and an
    honest one is known honest. Geas (a person, Wisdom save; 30 days, a year from level 7, until ended at 9): they
    obey: they keep silent about every crime of yours they saw, tell what they want and what they hide, and stay
    Friendly; a guard under it never lays hands on you; when it ends they know (-40). Modify Memory (a person,
    Wisdom save): they forget the last day: the crimes of yours they saw (unreported ones are silenced; their word
    is withdrawn from a report not yet acted on) and any grudge from it (their mood back to indifferent at worst).
    Glibness (an hour): every Charisma check's die is at least 15 (conversations, bribes, disguise, haggling).
    Antipathy/Sympathy (an hour to cast, 10 days, on the caster): a kind of creature (an encounter group) is chosen;
    a band of that kind met on the road makes Wisdom saves: Antipathy sends it fleeing if most fail, Sympathy brings
    it to you entranced (it is caught unaware). Awaken (8 hours, a 1,000 GP agate) wakes a party animal: it speaks,
    it is named, and it keeps watch: the camp is never caught asleep while it is with you (awakened plants wait for
    Part F's followers).
  - Disguise: Disguise Self (an hour) and Seeming (8 hours, the whole party) are disguises whose quality is the
    caster's spell save DC (a watchman's check against it sees through, as against a disguise kit's roll); Alter
    Self's stays unseen-through. Illusions in a town distract (`renown.flags["distraction"]`: a penalty to the
    Perception of everyone watching, for a time, in that town): Minor Illusion -5 for a minute, Silent Image -5 for
    ten minutes, Major Image -10 for ten minutes, and from a 4th-level slot until you leave the town (it lasts until
    dispelled). Mislead: in a fight the caster turns Invisible (until it attacks, deals damage or casts) and a double
    stays; outside one, for the hour, nobody in town sees the caster (no witnesses). Wards on the camp: Magic Mouth
    and Programmed Illusion ("mouth": it wakes the camp, as Alarm; "decoy": the night's visitors fall on an illusory
    camp: the real one is awake and catches them unaware), Hallucinatory Terrain (24 hours) and Mirage Arcane (10 days):
    "veil", hunters and night visitors pass the hidden camp by (an Investigation check against the DC sees it, which
    only a clever band makes). Project Image: your image walks into a known town within 500 miles: you hear its news
    and see its work board as if there. Illusory Script (10 days): a letter that shows each reader the seal they would
    honour: the gate's guards wave you through without a search, and your papers impress as a noble's. Nystul's Magic
    Aura (24 hours): a carried magic thing shows no aura: robbers take it for junk. Sequester (until dispelled): a
    carried thing hidden from robbers, thieves, the watch and every divination; a fallen friend's body held out of
    time (its days stop for good). Nondetection (8 hours): no Detect Thoughts or other divination of a foe finds the
    one warded (in a fight: no enemy's `sense_thoughts`).
  - The small arts: Druidcraft tells the next day's weather here (the weather is the world's own, so it is true) and
    lights or snuffs the camp's fire; Elementalism lights the fire, gives everyone a cup of clean water, or dries the
    party a little; Prestidigitation cleans the party (the grime of a few days) and warms the next meal; Thaumaturgy
    gives Advantage on Intimidation in the talk that follows.
  - The law: every one of them is magic seen (law.magic_check) where it is cast before witnesses; a spell on a
    person is noticed when it ends (the charmed know, the enthralled do not).
- [ ] E.5 Locks and stone, weather and land, lasting protections, great magic; Part E to `main`. Locks and stone:
  knock, arcane lock, mending, mage hand, fabricate, stone shape, passwall, move earth, creation, Leomund's secret
  chest. Weather and land: control water, control weather, plant growth, tsunami (cast in a minute). Lasting
  protections: glyph of warding, symbol, guards and wards, forbiddance, hallow, magic circle, Mordenkainen's private
  sanctum. Great magic: contingency, magic jar, Tasha's bubbling cauldron, clone, demiplane, imprisonment, and Wish's
  other uses outside a fight.

### Part F — Appendix B: familiars, steeds and summons
- [ ] F.1 The 36 stat blocks (beasts, imp, quasit, pseudodragon, sprite, sphinx of wonder, slaad tadpole) with
  pictures; Find Familiar, Find Steed, the Summon spells' spirits, Animate Dead; followers outside battle; Part F
  to `main`.

### Part G — Enemy casters, services, release
- [ ] G.1 Every caster stat block on the catalogue; arena: every battle spell cast by the AI in a scenario; a test
  caster of each spell level 1–9 casts without hangs.
- [ ] G.2 Spellcasting services and scrolls in temples, mages' guilds and shops; the law of magic.
- [ ] G.3 Every Expansion 3 codex entry settled; balance; the icon; release v1.3.0.
