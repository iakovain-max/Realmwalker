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
  friends (the stress: 1d10 necrotic a spell level for every spell until a long rest, Strength 5 for 2d4 days, a
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
- [x] E.4 Minds and the law, disguise and illusion, the small arts (27 spells). The old E.4 was split in two at its
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
    Wisdom save): they forget the last day: the crimes of yours they saw and not yet reported (silenced; a report
    already made stands), the casting itself, and any grudge from it (their mood back to indifferent at worst).
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
- [x] E.5 Locks and stone, weather and land (14 spells). The old E.5 was split in two at its start (2026-10-17): 28
  spells and Wish's other uses, each a system of its own, were too many for one part; lasting protections and great
  magic became E.6. Locks and stone: knock, arcane lock, mending, mage hand, fabricate, stone shape, passwall, move
  earth, creation, Leomund's secret chest. Weather and land: control water, control weather, plant growth, tsunami.
  How (the design, at the start of E.5; numbers from the 2024 PHB):
  - The new module is `game/stonework.py`: road ops `does` "lock" (`how`: knock, arcane), "mend", "hand", "make"
    (`how`: fabricate, creation), "stone" (`how`: shape, passwall), "chest", "weather", "plants" and "part" (in
    `spells.E5_KINDS` / ROAD_USES, checked at start-up), through game/spellwork's door; Move Earth is a camp ward
    ("earthworks"); Tsunami is a road op "wave" cast from the encounter screen.
  - Locks: Knock (in a dungeon) opens a locked door or chest within 60 feet (Subjects), with a knock that wakes the
    level; in the cells, a sure way out of the lock (the escape's check +10: the jailer still may hear the run).
    Arcane Lock (25 GP gold dust, consumed): in a dungeon a closed door next to you is locked for good to everyone but
    the party (its DC +10 for anyone forcing it; the level's dwellers cannot pass it); in a town your room at the inn
    is locked while you stay in that town (no inn thief).
  - Mending (a minute) mends the most worn thing the party carries by 25, up to three-quarters (a break or a tear;
    the last of the wear needs tools). Mage Hand (in a town, for the talk that follows): the next theft from a stall
    is done by the hand from 30 feet (Advantage on Sleight of Hand; caught, nobody grabs your wrist: the merchant
    cries witchcraft, the theft fails and the magic was seen).
  - Making: Fabricate (10 minutes) makes any camp craft whose raw materials the party carries, without the tools,
    the fire or the check, three batches at most; a craft that needs an artisan's tools needs someone trained with
    them (the book's high craftsmanship). Creation (a minute) makes a thing of wood, cloth, leather or rope (vegetable
    matter: 24 hours) or of stone (12 hours) from the gear list; the book's metals last an hour or less and are left
    out (no iron crowbar for an hour), as are gems and coin: it vanishes at its time, and no merchant buys it.
  - Stone: Stone Shape opens one 5-foot section of a dungeon's stone or cave wall next to you into the floor beyond
    (Subjects: each way where one square of wall stands between you and floor), for good; Passwall opens up to 20
    feet of wall for an hour (the passage closes behind you when it ends; a hidden room beyond is found).
  - Move Earth (concentration up to two hours, cast in the wild): a ditch and a bank round the camp, a ward
    "earthworks" (the night's visitors are seen climbing it: the camp is awake and sees them first).
  - Leomund's Secret Chest (a 5,000 GP chest and its 50 GP replica): the party's coin, treasure or spare gear goes into
    the chest on the Ethereal Plane (Subjects: the coin, the treasure, everything not worn): it weighs nothing and no
    robber, thief or watchman can take it, and it cannot be used until the replica calls the chest back (the
    replica's use). After 60 days each day has a growing 5% chance that the chest is lost with all in it.
  - Weather and land: Control Water parts a river (a lasting spell of ten minutes: the next river crossed costs no
    ford time and nobody gets wet). Control Weather (cast in ten minutes, outdoors, 8 hours, about two map tiles round
    the caster): clear the sky, bring rain or snow, still the wind, warm or cool the air by 10 degrees
    (`renown.flags["weather"]`, read through survival.weather). Plant Growth: in a fight its Overgrowth is ground
    that costs four times the movement for the caster's foes (100 feet, the caster's friends' squares left out, as
    the book lets); outside one its Enrichment (8 hours) doubles what is foraged on this map tile for a year
    (`renown.flags["enriched"]`), and cast in a village it is a deed for its folk. Tsunami (a minute): when a band
    on the road is seen first, a great wave strikes it before the fight (6d10 bludgeoning, Strength save for half)
    and the fight begins with the band reeling (the wave rolls on; its later blows are left out).
- [x] E.6 Lasting protections and the caster's keeping (9 spells). The old E.6 was split in two at its start
  (2026-10-17): 13 spells and Wish's six other uses, four of them systems as big as a part (a soul in a jar, a body
  grown in a vessel, a spell waiting for its moment, a prison for good), were too many for one part; great magic and
  Wish became E.7. Lasting protections: glyph of warding, symbol, guards and wards, forbiddance, hallow, magic circle,
  Mordenkainen's private sanctum. The caster's keeping: demiplane, Tasha's bubbling cauldron.
  How (the design, at the start of E.6; numbers from the 2024 PHB):
  - The new module is `game/warding.py`: road ops `does` "protect" (`how`: glyph, symbol, guards, forbiddance, circle,
    sanctum), "hallow", "demiplane" and "cauldron" (in `spells.E6_KINDS` / ROAD_USES, checked at start-up), through
    game/spellwork's door. A protection on a camp is a camp ward (`Camp.wards`, as E.1's), so it stands where the
    party rests, in the wild or underground, and is left behind when the party moves on; a hallowed place is kept by
    the world (`politics["hallowed"]`), for good.
  - Where they act: the night's visitors (`spellwork.night_visitors` asks `warding.night` first), a rest underground
    while hunters search the level (`spellwork.hidden` asks `warding.keeps_out`), and a fight at the camp or on
    hallowed ground (`warding.at_the_start`, from `fight.start_battle`). A creature's saved `conditions` now come into
    the fight with it (Battle: a sleep brought in breaks on damage; "discord" is Symbol's mark), so what a glyph did
    in the dark is still on the band when the fight begins.
  - Glyph of Warding (an hour; 200 GP of diamond dust, consumed): inscribed on the way into the camp, it waits until
    something comes in the night (as long as you camp here). Subjects: an explosive rune of acid, cold, fire,
    lightning or thunder (5d8, +1d8 a slot above 3; Dexterity save for half, on every one of the band), or a spell
    glyph holding a prepared spell of level 5 or lower that is cast with an action at a foe or a point and asks no
    concentration (its own slot spent as the glyph is made): as the fight begins it takes effect at the first of them
    (an area centred on it), with no action. Either way the camp is woken. In a town, the glyph guards your room at
    the inn while you stay there: the night's thief sets it off, is burnt and runs with nothing.
  - Symbol (a minute; 1,000 GP of diamond dust, consumed): the same, with one of six effects (Subjects): Death
    (10d10 necrotic, Constitution save for half), Discord (Wisdom: a minute of Disadvantage on attacks), Fear (Wisdom:
    Frightened, they run: those who fail are gone from the band), Pain (Constitution: Incapacitated a minute), Sleep
    (Wisdom: Unconscious ten minutes, woken by damage), Stunning (Wisdom: Stunned a minute). The fight begins with
    the band as the symbol left it; a band that all fled or died is no fight at all.
  - Magic Circle (a minute; 100 GP of salt and powdered silver, consumed; an hour, one more a slot above 3):
    celestials, elementals, fey, fiends and undead cannot come into the camp: those of the night's band stay out
    (a band all of them goes away); a fight at the camp gives the party the Protection from Evil mark against them;
    underground the party may rest while only such creatures hunt the level.
  - Forbiddance (ten minutes or a ritual; 1,000 GP of ruby dust, kept; a day): the same six kinds as the book
    (aberrations, celestials, elementals, fey, fiends, undead) take 5d10 radiant or necrotic (Subjects) as they come
    into the camp, and again at the end of each of their turns in a fight there. (Its ward against teleporting in
    has nothing to stop yet: no foe teleports to a camp.)
  - Guards and Wards (an hour; a silver rod, kept; 24 hours): fog, locked ways and webs round the camp: the night's
    band loses its way half the time and goes elsewhere; when it finds the camp, the magic mouth has woken you.
    Underground, hunters lose their way in the fog and the locked doors: the party may rest while it stands.
  - Mordenkainen's Private Sanctum (ten minutes; 24 hours): the camp is dark fog and silence from outside: the
    night is half as likely to bring anything as a cold camp's, fire or no fire (the fire still warms), and nobody
    finds the animals. (Divination against the party, sensors and teleporting are nobody's to use yet.)
  - Hallow (24 hours; 1,000 GP of incense, consumed; for good): aberrations, elementals, fey, fiends and undead cannot
    come onto the ground (a camp there, in the wild on that map tile or underground within 60 feet), and one more
    effect (Subjects): Courage (the party cannot be Frightened in a fight there), Fear (every foe there that is not
    a humanoid is Frightened), Resistance (the party resists necrotic damage there), Vulnerability (foes of the
    warded kinds are vulnerable to radiant damage there) or Peaceful Rest (the dead buried there never rise: a
    haunted battlefield is laid to rest for good, and in a town or village the folk remember it as a deed).
    Detect Evil and Good tells a hallowed place. Daylight, Darkness, Silence, Tongues and Extradimensional
    Interference are left out (nothing in the game uses them yet).
  - Demiplane (an action; an hour): a shadowy door to a stone room out of the world: put the coin and treasure, the
    spare arms, or all of it inside, or take back everything (Subjects; kept as item records with the coin, as the
    secret chest's things are, but never lost); for the hour it is also a room to rest in (a short rest whatever
    hunts outside, like Rope Trick).
  - Tasha's Bubbling Cauldron (an action; a 500 GP gilded ladle, kept): potions of one common or uncommon kind
    (Subjects: today the potions of healing and greater healing; the rest come with their expansion), as many as
    the caster's spellcasting modifier (at least one). They are real potions until the spell is cast again, when the
    last ones vanish; no merchant buys them. Cast before a fight, not in one (drawing a potion is a bonus action,
    as drinking one is).
  - Companions: one who knows Forbiddance casts it as a ritual before a long rest in the wild (radiant).
- [x] E.7 Great magic and Wish's other uses; Part E to `main`: contingency, magic jar, clone, imprisonment, and
  Wish's other uses outside a fight (Object Creation, Resistance, Spell Immunity, Sudden Learning, Roll Redo,
  Reshape Reality).
  How (the design, at the start of E.7; numbers from the 2024 PHB):
  - The new module is `game/greatmagic.py`: road ops `does` "contingency", "jar", "clone", "imprison" and "wish" (in
    `spells.E7_KINDS` / ROAD_USES, checked at start-up), through game/spellwork's door (subjects, problem, cast). What
    the fight needs is in rules/combat (the contingent spell's trigger, the jar's actions, Roll Redo) and the kernel
    (`query.resists` reads a wished resistance, `effects.warded` a wished immunity to one spell).
  - Contingency (ten minutes; a 1,500 GP statuette of the caster, kept and carried; ten days): Subjects pair a spell
    of level 5 or lower that the caster could cast now, cast with an action, that can be aimed at the caster (target
    self or ally) and works in a fight, with one of three triggers: "as a fight begins", "when I am brought below half
    my hit points", "when I fall". Both slots are spent as it is cast (the contingent spell's lowest that will do).
    Kept as `char.spells["contingency"]` {spell, slot, trigger, until}; in a fight `Battle._contingency(f, trigger)`
    casts it on the caster alone at once, with no action, and Contingency ends. Casting it again ends the old one; it
    ends if the statuette is not in the party's packs when it would act.
  - Magic Jar (a minute; a 500 GP gem, kept until the spell ends, then shattered): the caster's soul goes into the gem
    until they return (`char.spells["jar"]`); meanwhile they cast nothing and their body is carried along (outside a
    fight nothing else changes). In a fight the body is Incapacitated where it stands, and its turns have two actions:
    Possess, at a humanoid foe within 100 feet that it can see (Charisma save; a success makes it immune for a day,
    kept in the fight), and Return (back to the body: the spell ends). A possessed foe fights for the party, under the
    player (the caster's mind: its own hit points, attacks and speed; the caster's spells are left out), with a third
    action, Leave (back into the gem; the foe's soul returns to it). If the host dies, a Charisma save against the
    caster's own DC brings the soul back to the gem; a failure is death. If the body dies while the soul is away, the
    soul dies when the spell ends. At the end of a fight the soul goes back to the gem, and a host left standing runs
    (it is no longer a foe). The Auto on Magic Jar possesses the strongest humanoid foe in reach.
  - Clone (an hour; a 1,000 GP diamond, consumed, and a 2,000 GP vessel, which stays with the clone): cast in a town
    or city on someone of the party (Subjects); the vessel is sealed in its temple's crypt (`renown.flags["clones"]`
    {who, settlement, ready}), and the clone is grown in 120 days. When that someone dies after it is grown, their
    soul goes to the clone: the leader wakes there whole, with nothing of what they carried (their companions take it
    up and come to that town, 24 miles a day, as when sent for); a companion wakes there and waits there. The clone is
    then spent. The age chosen is left out (it changes nothing in the game).
  - Imprisonment (a minute; a 5,000 GP statuette, consumed): cast from the meeting screen (i) when a band is seen
    first, as Tsunami is: the strongest of it makes a Wisdom save (a Legendary Resistance is spent on it); a failure
    binds it for good, in the form its kind suits (a dragon is buried, the undead chained, fiends, celestials and fey
    hedged in a prison of their own, humanoids shut in a gem, anything else asleep): it is gone from the band, its XP
    is the party's, and a named beast or dragon of the world is bound in the world's record (its lair empty, its
    tribute lifted, a deed of the land as slaying it is). A success makes it immune for a day. The minute passes; then
    the fight begins with whoever is left knowing you. The ending trigger is left out (nothing is likely to end it).
  - Wish outside a fight (`road_too: "wish"`; the battle's Wish is as D.4 made it): Subjects in groups (Shift ←→ jumps
    to the next group on the Spells page): Object Creation (any thing that is not magic, worth 100 to 25,000 GP, into
    the pack), Instant Health (the party whole, the Greater Restoration effects ended),
    Resistance (the party, for good, to one damage type: `char.spells["wished_resist"]`), Spell Immunity (the party
    for 8 hours to one spell a foe of this world casts: `char.effects["immune_spell:<id>"]`), Sudden Learning (give
    up a feat that nothing else needs; a new one they are eligible for is chosen as a waiting choice, on the sheet),
    Reshape Reality (four wishes the game understands: a lost artifact, which carries the party to the place where it
    lies; that a named beast or a dragon were dead, which comes true by the beast's might (a beast half the time, a
    dragon a quarter), and otherwise it learns your name and comes for you; that the realm forget your crimes, which
    clears your bounties and crimes in the realm you stand in; and that a fallen friend the party carries were alive,
    who rises whole at the death toll). Every one of them brings the stress (spells.wish_stress). Copying a spell
    outside a fight is left out (the copies are the battle's).
  - Roll Redo is in the fight's Wish list: one of the foes' hits on a friend since the caster's last turn is rolled
    again with Disadvantage; a miss gives back all its damage (a friend down stands again), and a hit that was a
    critical and is not one now gives back half. Redoing a save is left out (what a failed save brought cannot be
    taken back cleanly). It brings the stress; the Auto never uses it.

### Part F — Appendix B: familiars, steeds and summons
Split at its start (2026-10-17, as E.2 and E.4-E.6 were): the part as planned was 36 stat blocks with pictures and
some twenty creature-making spells on a battle that had no way yet for a creature to fight on the party's side. Each
stat block now comes with the spell that brings it into play (never a block that nothing calls); each piece goes to
`main` when done.
- [x] F.1 Allies on the field, Find Familiar and Find Steed: a creature fighting for the party (the foundation every
  later piece uses); the familiar's forms of Appendix B (bat, cat, crab, frog, hawk, lizard, octopus, owl, rat, raven,
  scorpion, spider, weasel) with pictures; the Otherworldly Steed; the familiar and the steed as followers outside a
  fight.
- [x] F.2 Summoned spirits, levels 2-4 (split at its start, 2026-10-17): a creature whose numbers grow with the
  slot, held by concentration; Summon Beast, Summon Fey, Summon Undead, Summon Aberration, Summon Construct, Summon
  Elemental and Giant Insect, with their stat blocks, pictures and the costly components.
- [x] F.3 Summoned spirits, levels 5-6: Summon Celestial, Summon Dragon (Shared Resistances, Breath Weapon), Summon
  Fiend (Death Throes) and Animate Objects (several creatures at once, commanded with the caster's Bonus Action).
- [x] F.4 The dead (split at its start, 2026-10-17: the bound go to F.5): servants that outlast a fight - Animate
  Dead (skeletons and zombies), Create Undead (ghouls, ghasts, wights, mummies) and Finger of Death's zombie; the
  ghast and the mummy with their stat blocks and pictures; commanded with the Bonus Action, held again each day or
  they go free.
- [x] F.5 The bound: Planar Ally (a spirit of the cleric's god for a price by the hour or day), Planar Binding (a
  captive celestial, elemental, fey or fiend, or a Planar Ally's spirit, bound for a day to a year) and Magic Circle
  turned inward (a spirit that will not stay to be bound is held in it), on F.4's servants.
- [x] F.6 Shapes in a fight (split at its start, 2026-10-17: the old F.6 was four spells and 24 stat blocks with
  pictures): Polymorph and True Polymorph, a fighter's numbers swapped for a creature's for the fight, the forms
  taken from the creatures the game has.
- [x] F.7 The rest of Appendix B: ape, badger, constrictor snake, crocodile, elephant, elk, giant badger, giant crab,
  giant goat, giant seahorse, giant weasel, goat, lion, octopus, panther, reef shark, tiger, venomous snake; imp,
  quasit, pseudodragon, sprite, sphinx of wonder, slaad tadpole, with pictures; each as Polymorph's or True
  Polymorph's form and met in the land where it lives (the beasts in their biomes' bands, the fiends and fey where
  such things are met), and the cult fanatic's imp or quasit.
- [x] F.8 Animal Shapes and Shapechange (on F.6's swap), outside a fight too; Part F complete.

#### F.8 — How
- **The spells** (2024 PHB pages 243 and 318, read off the page images). **Animal Shapes** (level 8, druid; an
  action, 30 feet, V S, 24 hours, no concentration): any number of willing creatures within range each become a
  Large or smaller Beast of Challenge Rating 4 or lower; a target keeps its hit points, Intelligence, Wisdom and
  Charisma, cannot cast spells and cannot use its gear (it melds into the form), and gains Temporary Hit Points equal
  to the form's hit points. It ends for a target when those are gone, when it leaves the form as a Bonus Action, or
  after 24 hours; on later turns the caster may change the targets again with a Magic action. **Shapechange** (level
  9, druid and wizard; an action, self, V S M: a jade circlet worth 1,500 GP, not consumed; concentration up to an
  hour): the caster becomes a creature of Challenge Rating no higher than its level, never a Construct or an
  Undead, keeping its Intelligence, Wisdom and Charisma, its proficiencies and its Spellcasting, with Temporary Hit
  Points equal to the form's hit points; it ends when those are gone, and a Magic action shifts it into another form.
- **On F.6's swap**: the effects op "shape" learns `cr` (a fixed cap: Animal Shapes' 4), `size` (the largest form:
  "large"), `not` (kinds never taken: construct, undead), `keeps` ("mind": the three mental scores and their saves;
  "spells": the Spellcasting), `leave` (a Bonus Action to leave the form), `shift` ("self": the shaped one shifts
  with a Magic action; "caster": the caster changes its targets) and `hours` (it outlasts the fight). A spell aimed at
  `all_allies` takes the willing within range: every friend that casts no spells (it would lose them for a day),
  never the caster. `Fighter.shape` keeps these (`conc`: only a concentration shape ends with its caster's
  concentration, so a druid's other spell no longer undoes Animal Shapes). A shape that keeps its Spellcasting casts
  through the creature's door (`creature_cast`): the form's block gets the character's battle spells (no
  concentration spell: it would end the shape), its spell attack and DC, and its slots, which are written back to the
  character when the shape ends. The game chooses the form as F.6 does (the strongest a friend may take, never one
  that breathes only water); a shift takes the strongest other form (Shapechange) or the strongest again (Animal
  Shapes), with fresh Temporary Hit Points.
- **Outside a fight**: a shape that outlasts the fight is a record on the character, `char.spells["shape"]` {form,
  spell, until, temp, caster, conc}, written when it is taken (in a fight or on the road) and kept at the fight's end
  with the Temporary Hit Points left; a shape that ended in the fight takes its record with it. When a fight starts
  the shaped come into it in their forms (`Battle.bring_shapes`, from `fight.start_battle`), the Shapechanger
  concentrating on it. On the Spells page (game/shapeshift.py through spellwork's door, road op `does: "shape"`) both
  spells list their forms as Subjects (the fliers first, then the swiftest, then the strongest); Animal Shapes takes
  the whole party (the caster too: it can leave whenever it likes) and, while it holds, its forms and "everyone back to
  their own shape" are chosen with no slot (the Magic action). Shapechange lasts an hour on the road. While shaped:
  the party's pace is the form's (a party of elk outpaces walkers; F.6's travel rule for those borne by magic), a
  party that all flies crosses water and mountains as on the wind (`magic_crossing` "fly"), one that all swims crosses
  rivers and lakes; no spells (Animal Shapes) and no gear used (tools, potions); drawn as the form everywhere
  (`dolls.character`). It ends at its hour (`shapeshift.tick` from spellwork's tick). Harm outside a fight falls on
  the body itself (the borrowed hit points are the fight's: adapted). "You must have seen the sort of creature" is the
  game's creatures (adapted); the equipment's falling to the ground is left out (it always melds in).
- **The Auto** casts Animal Shapes by the worth of the willing (a friend weaker than the beast gains, one stronger
  loses by the difference: F.6's worth with that loss added) and Shapechange by its form's worth (it keeps its spells,
  so a caster now gains), shifts again when the borrowed hit points run low, and never leaves a form on its own. The
  enemy's casters get them when G.1 gives them spells.
- **Tests** (tests/test_shapes_lasting.py): Animal Shapes on the willing (never a spellcaster, never the caster),
  Large or smaller and CR 4 at most; the Bonus Action to leave; the caster's Magic action changes them again; the shape
  outlasts the fight with the hit points left and comes into the next one, and ends at its hour; Shapechange keeps the
  mind and casts a spell in the form (its slot spent on the character), shifts, ends with the concentration; the road:
  the Subjects, the pace, flying over water, no casting, drawn as the form; the Auto casts both; the catalogue test
  casts both.

#### F.7 — How
- **The stat blocks** are the 2025 Monster Manual's (the PHB's Appendix B prints the same creatures; the MM is the
  newer text): the animals of its Appendix A (pages 351-375), the imp (180), the pseudodragon (252), the quasit (255),
  the slaad tadpole (287), the sphinx of wonder (294) and the sprite (301), numbers read off the page images. They
  come as fragments of the expansion's pack: `statblocks.beasts.json` (the blocks) and `creatures.beasts.json` (their
  flavour: names, bodies, morale, roles, what they butcher into, two descriptions or more, and their encounters).
- **Forms**: every one of them is a form for Polymorph (the beasts) or True Polymorph (all), as F.6's `shapes.forms`
  reads every creature. A creature that breathes only water (the octopus, the giant seahorse, the reef shark: trait
  `water_breathing`) is never a friend's form (it would flounder on dry ground), but may be a foe's.
- **Met in the land** (data in `creatures.beasts.json` "encounters", by biome, danger and time of day, three intros
  each): apes in the jungle; badgers and giant badgers in forests and hills; the constrictor snake in jungle and marsh;
  crocodiles in marsh, by coasts and in jungle rivers; elephants on the savanna; elk in forests, pine forests, plains,
  hills and tundra; the giant crab on coasts; goats and giant goats in hills and mountains; the giant weasel in
  forests, hills and plains; lions on the savanna, steppe and desert edges; panthers and tigers in jungle and forest;
  venomous snakes in marsh, jungle, desert, savanna and badlands; the pseudodragon alone in hills, mountains, forests
  and coasts; sprites in forests and the fey forest; the sphinx of wonder alone in deserts and dunes. The cult
  fanatic's imp or quasit: a cult circle may come with its devil or its demon (two more cult circles, each with one).
  Slaad tadpoles hatch in the wizards' towers (the tower's inhabitants). The three water creatures are met when fights
  go under water (Expansion 22), with the octopus's Ink Cloud and the seahorse's Bubble Dash (both "while
  underwater") and the octopus as a familiar's form; until then they are shapes only (adapted).
- **What the kernel learns**: a creature's bonus action that is a save against one creature (the elephant's
  Trample: only on a Prone creature within 5 feet, `requires: "target_prone"`), made after its Attack action; a
  stat block action's `advantage_if` (`query.ADVANTAGE_IF`: the bugbear warrior's Light Hammer on the creature it
  holds, written in its block since Expansion 1 and read by nothing until now; the reef shark has only Pack Tactics,
  the Advantage on the hurt is the giant shark's); a hold that restrains while it lasts (the crocodile's Bite: a
  condition op's `with`, ended by `durations.remove` with the grapple); a save that fails by 5 or more bringing more
  (`fail_by` {by, on_fail}: the
  pseudodragon's Sting, Unconscious until it takes damage); Running Leap (the lion's 25 feet with a run, `Fighter.jump`
  from the trait's `feet`); the sphinx of wonder's Burst of Ingenuity (its Reaction, twice a day: +2 to a failed save
  of its own or a friend's within 30 feet that the 2 would turn); Invisibility cast at will on itself (the imp, the
  quasit, the sprite: their stat block's `spellcasting` at will, cast on the caster only). Left out, with notes in the
  codex: Shape-Shift (the imp's and quasit's other bodies), Heart Sight (no fight use), Hold Breath and Compression
  (no water or cracks in the fights yet); the pseudodragon's sleeper is woken by damage only (shaking it awake is left
  out).
- **The Auto and the enemy** use what they have by the existing worth (attacks, saves, Roar in place of a Rend, the
  imp's Invisibility before it strikes); the quasit opens with its Scare and the pseudodragon with its Sting (their
  `ai` `opens_with`, which now also reads what a failed save brings), and a hold the target saves its way out of is
  worth its expected rounds; the arena's coverage test fights all 24.
- **Pictures**: from the Crawl pack where it has the animal (the crocodile, elephant, reef shark, constrictor snake,
  venomous snake, imp, quasit, sphinx of wonder in a sphinx's colours, giant crab and pseudodragon recoloured, the
  slaad tadpole a recoloured newt), the rest drawn in tools/beast_art.py: the big cats (lion, tiger, panther) on one
  frame, the elk and the goats on the equine frame, the badgers, the ape, the giant weasel, the giant seahorse, the
  octopus and the sprite.
- **Tests** (tests/test_beasts.py): every new block resolves and has a picture; Trample only on the Prone, as a
  bonus action; the crocodile's hold restrains; Advantage on the one held; the pseudodragon's sleep by 5; the sphinx's Burst turns a failed save;
  the lion's leap; the imp turns invisible and strikes; the water-breathers never a friend's form; each beast is met in
  its biome; a cult circle with its imp; the tower's tadpoles. The codex marks the 24 (done or adapted).

#### F.6 — How
- **A shape** is a fighter's numbers swapped for a creature's for the rest of the fight (the 2024 text: "the
  target's game statistics are replaced by the stat block of the chosen Beast"). `Battle.shape(f, cid, by=caster,
  spell=)` keeps what it was in `Fighter.shape` {char, creature, cdef, sq, slots,
  recharge, by, spell, temp} and gives the fighter a
  new `Creature` of the form (named for who it is: "Aldric, as a brown bear"), with the hit points it had (hit points
  are kept) and Temporary Hit Points equal to the form's own hit points (the higher of those and any it had). A party
  member keeps playing as itself (control follows the side, as for allies): the form's attacks, speeds, senses, size
  and traits; no spells (its character is set aside: `f.char` is None while shaped), no class features, no gear.
- **It ends** (`Battle.unshape`) when its Temporary Hit Points are gone (`_apply_hp_loss`: what is left of the blow
  falls on its own hit points), when the caster's concentration ends (`_end_concentration`), or when the fight ends
  (at the outcome, with Magic Jar's release: the spell outlasts no fight; adapted). Conditions stay with the fighter.
  On ending, its hit points go back to the character or creature it was. A shapechanger, a creature at 0 hit points
  and one already shaped are not affected.
- **Polymorph** (level 4, concentration up to an hour, 60 feet, a caterpillar cocoon: the component pouch serves): a
  creature makes a Wisdom save or becomes a Beast whose Challenge Rating is no more than its own (a character: its
  level). The party's own are willing: no save. The form is the game's choice (as Chromatic Orb picks its damage):
  for a friend the strongest beast it may become (by hit points and blows, `shapes.best`), for a foe the weakest
  (`shapes.worst`: a frog, a rat). **True Polymorph** (level 9, concentration up to an hour, 30 feet, a drop of
  mercury, a dollop of gum arabic and a wisp of smoke: the pouch) does the same with any creature that is not unique
  or a shapechanger, by the same Challenge Rating rule; the hour that makes it lasting and the object forms are left
  out (no fight lasts an hour; objects wait). The spells' effects op is {"op": "shape", "forms": ["beast"] | "any"}.
- **The Auto** casts it by its worth (`estimates`: a foe's threat taken away times the chance it fails the save; a
  friend's blows and the temporary hit points gained). The enemy's casters get it when G.1 gives them the spells.
- **Pictures**: a shaped fighter is drawn as its form (battlefx draws a fighter without a character by its creature).
- **Tests** (tests/test_shapes.py): a foe polymorphed into the weakest beast (the save, its blows and AC now the
  beast's, back as it was when the temporary hit points go with the rest of the blow on its own hit points), a
  friend into the strongest it may be (no save, played by the player, cannot cast, back at the end of the
  concentration with its own hit points), True Polymorph into a non-beast; the fight's end undoes it; the Auto casts
  it; the catalogue test casts both.

#### F.5 — How
- **The bound** are F.4's servants (`char.spells["servants"]`, rules/servants.py) with what the dead did not need: a
  record may carry `form` and `level` (a spirit's numbers for its slot, made in each fight by `allies.summon_def`
  with its master's spell attack and DC), `picture`, `heals` (whole again at a long rest: `servants.rest` from
  `progression.long_rest`; the dead never heal) and `bound` (held by Planar Binding). Neither kind waits for a word
  (`word` False): a spirit or a bound creature acts on its own in a fight, played by the player or the Auto (z), right
  after its master. When its time is up it goes (no fight): a spirit reports and returns home, a bound captive runs
  off into the wild; a master's death sends them all away. They wait outside a settlement's close-up map, as the dead
  do, and are drawn behind the party by their own picture.
- **Planar Ally** (level 6, cleric, ten minutes, outside a fight: road op "bind", how "ally"): the cleric's god
  (the faith of their people, `faction.faith_for_culture`) sends a spirit of its kind: data/factions.json faiths
  `ally` {creature, form} - a celestial for the gods of light and law, an elemental for the old gods of land, sky and
  sea, a fiend for the dark gods and cults - as F.3's (or F.2's) spirit at the slot's level, named for the god ("a
  defending celestial spirit of Solun"). The bargain is the book's price (100 GP a minute is never cheaper than an
  hour here, so the terms are by the hour or day): an hour 1,000 GP, a day 10,000, three days 30,000, ten days 100,000
  (each a Subject on the Spells page), paid at once from the party's purse; half when the party's leader belongs to
  that god's church (the book's "aligned with the creature's ethos"). No money, no casting. The work asked is always
  the same (to fight beside you and keep you safe on the road): tasks of another kind, choosing a creature by name and
  the spirit's refusal of a suicidal task are left out.
- **Planar Binding** (level 5, an hour, 60 feet, a jewel of 1,000 GP consumed: the rare stone, a sapphire, a jacinth
  or a flawless diamond; road op "bind", how "binding"): the target is a celestial, elemental, fey or fiend the party
  holds - a captive taken after a fight (`renown.flags["captives"]`: the 2025 goblins are fey), a Planar Ally spirit
  serving one of the party, or a creature this spell already binds (to bind it again for longer) - each a Subject. It
  makes a Charisma save against the caster's DC (Magic Resistance: Advantage); on a failure it serves for 24 hours,
  10, 30, 180 or 366 days by the slot (5 to 9). A captive bound leaves the captives (no bounty for it then) and fights
  for its master; a spirit's term grows to match (the book: "that spell's duration is extended"). On a success the
  jewel is spent and nothing changes. A Hostile creature twisting its orders is left out (orders are only to fight).
- **Magic Circle turned inward** (the E.6 spell, a Subject now: "outward: keep them out of the camp" or "inward: hold
  what stands inside it"): an inward circle (`renown.flags["inward_circle"]` {until, x, y, map}) holds a spirit
  inside it for its hour (one more a slot above 3). A Planar Ally's spirit will not stay an hour to be bound unless
  held so: Planar Binding on one needs an inward circle here that lasts the hour of the casting. A captive is tied
  already and needs none.
- **Tests** (tests/test_bound.py): Planar Ally's price by term and the church's half, the god's kind, the spirit in a
  real fight (its numbers at the slot, acting on its own, played by the Auto), healed at a long rest, gone home when
  its time ends and when its master dies, waiting outside a town; Planar Binding on a captive goblin (the save, the
  jewel, its term by slot, fighting for the party, running off when it ends) and on a spirit (refused without the
  inward circle, its term extended with one); the circle's two directions. The autoplay bot's servant checks cover
  the new records.

#### F.4 — How
- **A servant** is a creature that serves a party member beyond one fight. Its record lives on its master, in
  `char.spells["servants"]` (saved with the character): a list of {id, cid (its creature), name, hp, max_hp, spell,
  word (it acts only when commanded), reach (feet the command carries: 60, or 120 for Create Undead's), until (the
  world minute its control ends; none: for ever), made, uses}. `rules/servants.py` (pure rules) adds and finds them,
  brings them into a fight beside their master (`bring_in`, from fight.start_battle with the familiar and the steed;
  bond kind "servant"), writes back what became of them (`after`: hit points kept, the destroyed struck off) and
  holds at most twelve to a master (the wight's own number; the book has no cap, the battle needs one). They earn no
  XP, their kills are their master's, they never run, and they do not keep a lost fight going (F.1's rules for
  allies). The undead do not eat, sleep or heal: what a fight takes from them stays taken.
- **Commanding**: F.3's Bonus Action becomes "Command your servants" (`Battle.command_objects`, ability id
  "command_objects"; called "Command the dead" when only undead answer, as before for the objects alone): every
  animated object and every servant with `word` within its reach of its master acts on its next turn; the others take
  the Dodge action as their turn begins (`Battle._waits_for_word`). The Auto commands whenever a foe stands.
- **Animate Dead** (level 3, a minute, outside a fight: road op "raise", how "dead"): a corpse becomes a zombie and a
  pile of bones a skeleton. Corpses are the Medium or Small humanoids among the fresh dead of the last fight, where it
  was fought (`game.fresh_dead`, kept for Speak with Dead; each body is used once); bones are the skeletons destroyed
  in that fight, or the old bones of a crypt's level underground (six piles on each such level, `lm.meta["bones"]`).
  One creature, two more for each slot above 3 (as many as there are bodies); or the same casting holds again up to
  four of the caster's Animate Dead servants (two more a slot above 3) for another 24 hours. Each choice is a Subject
  on the Spells page ("raise the dead here: three zombies", "hold your dead for another day: four"). A command
  carries 60 feet.
- **Create Undead** (level 6, a minute, only at night: how "ghouls"): up to three corpses become ghouls (four at slot
  7; five ghouls, or two ghasts or wights, at 8; six ghouls, three ghasts or wights, or two mummies at 9), each corpse
  needing a black onyx stone of 150 GP (kept, not used up; a new item sold in cities). Or the casting holds again as
  many of the caster's Create Undead servants for another 24 hours. A command carries 120 feet.
- **Going free**: when a servant's 24 hours pass unheld (`game/servants.tick`, from pass_time), it stops obeying.
  Out in the land, with nothing else under way, the freed dead turn on their maker: a fight begins with them (an
  encounter "the dead you raised", hostile, seen coming). Anywhere else (a town, a fight, an encounter already
  waiting) they shamble off into the dark and are gone. The game warns two hours before ("The dead grow restless:
  their hold on them ends in two hours").
- **Finger of Death** (in the catalogue since D.3): a humanoid killed by it rises at the start of its caster's next
  turn as a zombie on the caster's side (`Battle._rise_as_zombies`, from the turn's start; the effects op "rise"
  {"as": "zombie", "types": ["humanoid"]} marks the body). It follows its maker's spoken orders: no Bonus Action is
  needed (bond `word` False; the player plays it, z: the Auto). After the fight a party caster keeps it as a servant
  for ever (until none); a foe's zombie goes with the fight.
- **The dead and other people**: servants follow the party in the wild and underground (drawn behind it, as the
  familiar is: localview), but never come into a settlement's close-up map: they wait outside its walls, are in none
  of its fights, and fall in behind again when the party leaves (`servants.here`). Raising the dead is "desecration"
  to companions (the devout hate it: `companions.react`); casting where people see falls under the realm's magic law
  as every spell does.
- **The ghast** (MM 2025 p. 130: AC 13, 36 hit points, Stench DC 10, Bite 1d8 + 3 and 2d8 necrotic, Claw 2d6 + 3
  with a DC 10 Constitution save or Paralyzed) and **the mummy** (p. 219: AC 11, 58 hit points, Speed 20, vulnerable to
  fire, Multiattack two Rotting Fists (1d10 + 3 and 3d6 necrotic, cursed) and the Dreadful Glare (DC 11 Wisdom or
  Frightened)): stat blocks in the pack (`statblocks.allies.json`), traits "stench" (a turn-start emanation, a
  creature that saves is spared it for the fight) and "mummy_rot" (Rotting Fist's curse: in a fight the target cannot
  regain hit points, and a creature brought to 0 by the fist dies and turns to dust; on a party member afterwards the
  curse stays, `char.effects["kept:mummy_rot"]`: no healing and the hit point maximum 3d6 lower each day until Remove
  Curse lifts it; read by `game/servants._rot_day` as time passes). The Glare's 24-hour
  immunity is kept for the fight. Pictures: the Crawl pack's necrophage (the ghast) and its mummy.
- **Tests** (tests/test_servants.py): Animate Dead on the fresh dead and on a crypt's bones, the numbers by slot,
  holding again, going free (the fight, and gone in a town); Create Undead at night only, by slot, the onyx stones;
  servants brought into a fight, waiting without a word, commanded by the player and the Auto, the reach; Finger of
  Death's zombie rising, fighting, kept afterwards; the ghast's Stench and Claw, the mummy's Glare and curse (the dust,
  the lasting curse lifted by Remove Curse); the dead waiting outside a town. The arena fights the ghast and the
  mummy; the autoplay bot checks every servant record (a living creature id, hit points within the maximum, at most
  twelve).

#### F.3 — How
- **The three spirits** are F.2's summoning ({"op": "ally", "kind": "summon"}, `allies.summon_spirit`, numbers by
  the slot from the creature's `summon` record), with what F.2 did not need:
  - **Summon Celestial** (level 5, a reliquary of 500 GP): the celestial spirit, Large, AC 11 + the level (+2 as the
    Defender), 40 hit points + 10 a level above 5, flies 40; Radiant Bow (the Avenger: 600 feet, 2d6 + 2 + the level)
    or Radiant Mace (the Defender: 1d10 + 3 + the level, and itself or a friend it sees within 10 feet of the target
    gains 1d10 temporary hit points: the kernel op `special` "defender_ward", to the friend who needs it most);
    Healing Touch once a summoning (its own spell with `per_day`, an action, 2d8 + the level to another creature it
    touches: the heal op's `plus_level` reads the spirit's slot level from its bond). Resists radiant; never charmed or
    frightened. The game picks the Avenger when the foes stand far off or fly, the Defender beside friends in a brawl.
  - **Summon Dragon** (level 5, an object engraved with a dragon, 500 GP): the draconic spirit, Large, AC 14 + the
    level, 50 hit points + 10 a level above 5, flies 60 and swims 30, blindsight 30; Rend (reach 10 feet, 1d6 + 4 +
    the level) half the level times, and its Breath Weapon in the same Multiattack (a 30-foot cone, a Dexterity save
    against the caster's DC, 2d6 of the chosen type, half on a save). The chosen resistance is its form (acid, cold,
    fire, lightning, poison: the one the foes resist least, as Chromatic Orb picks); Shared Resistances gives the
    caster that resistance for as long as they hold the spell (a buff with `conc`). An attack's `with_multiattack`
    makes it part of the Attack action: once a turn, while the action is unspent or spent on this turn's attacks, it
    costs nothing more (`Battle.area_attack`; the tactics breathe first when it catches a foe and no friend, then
    Rend); a creature's attacks a turn are its Multiattack when the player commands it too (`query.attacks_per_action`).
  - **Summon Fiend** (level 6, a bloody vial of 600 GP): the fiendish spirit, Large, AC 12 + the level, 50 (Demon),
    40 (Devil) or 60 (Yugoloth) hit points + 15 a level above 6, Magic Resistance (Advantage on saves against
    spells), resists fire, immune to poison. Demon: climbs 40, Bite (1d12 + 3 + the level necrotic) and Death Throes
    (when it drops to 0 or the spell ends: everyone within 10 feet makes a Dexterity save, 2d10 + the level fire, half
    on a save; the "dismissed" event is new, emitted by `Battle.dismiss`). Devil: flies 60, Fiery Strike (melee or 150
    feet, 2d6 + 3 + the level fire) and Devil's Sight (magical darkness does not stop its darkvision:
    `Battle.can_see`). Yugoloth: Claws (1d8 + 3 + the level slashing) and after each a teleport of up to 30 feet (the
    game's choice: beside a new foe when its own fell, or out of a crowd when it is bloodied). The form: the Demon
    among many foes, the Devil when they fly or stand far off, the Yugoloth otherwise.
- **Animate Objects** (level 5, V S, 120 feet, concentration up to a minute) wakes things lying about: as many as
  the caster's spellcasting modifier, a Large one counting two and a Huge one three (the game's choice: a Huge one
  against a single great foe, Large ones in pairs, a Medium one for what is left). The animated object (AC 15, 10,
  20 or 40 hit points, Speed 30, blindsight 30, immune to poison and psychic and to charm, exhaustion, fear,
  paralysis and poison) slams with force for 1d4 + 3 (Medium), 2d6 + 3 + the modifier (Large) or 2d12 + 3 + the
  modifier (Huge), one more 1d4/1d6/1d12 a slot above 5 (the creature's `summon` record has `sizes` in place of
  `forms`; `allies.animate_objects`). What they are follows the place: a chest, a table or a statue under a roof, a
  stone, a log or a boulder outside (built-in words, three pictures for each). They act right after the caster, and
  only when commanded: "Command the animated objects" is the caster's Bonus Action (`Battle.class_abilities`,
  "command_objects"; the Auto gives it whenever a foe stands); otherwise each takes the Dodge action as its turn
  begins. A creature that casts it commands them as part of its turn. At 0 they fall back into things (gone, as a
  spirit); all of them go when the concentration ends.
- **The Auto** values each summoning as F.2's (`estimates._summon_worth`: the blows of the form it would pick, the
  breath for a cone, the Healing Touch), and Animate Objects by the objects it would make; it commands the objects
  with its Bonus Action. The spirits are played like any ally (z).
- **Costly components** (kept, not used up): a reliquary (500 GP), a dragon-engraved token (500 GP), a bloody vial
  (600 GP), sold in cities.
- **Pictures**: the Crawl pack's angels for the Avenger and the Defender, its dragons in the five colours (the red
  one recoloured), a balrug, a red devil and a neqoxec for the fiends; the animated objects drawn by hand
  (`tools/beast_art.py`); the three components.
- **Tests**: tests/test_summons.py (each spell in a real fight: numbers at two slots, every trait and blow, the
  Shared Resistance gone with the spell, the breath with the Rends, Death Throes at 0 and when the spell ends,
  Devil's Sight, the yugoloth's step; the objects by the modifier, waiting without a command, commanded by the player
  and the Auto, their slams by size and slot, gone with the concentration); the arena's coverage test fights each
  new creature in its forms; the catalogue test casts each.

#### F.2 — How
- **A summoned spirit** is an ally (F.1) with `bond` kind "summon" and `conc` True: the spell's effects op
  {"op": "ally", "kind": "summon", "creature": id} calls `allies.summon_spirit`, which makes its numbers for the slot
  (`allies.summon_def`) and puts it at the chosen point (the spell's target is a point in range: the nearest free
  squares to it). It takes its turn right after its caster's (the 2024 text: it shares the caster's count). When the
  caster's concentration ends (`Battle._end_concentration`: let go, broken by damage, a new concentration spell, the
  caster down) it disappears, as at 0 hit points; it never outlasts the fight. On the enemy's side the same op gives
  the caster's side a spirit (add_ally takes the owner's side).
- **Numbers by the slot** come from the creature's `summon` record in creatures.allies.json: the spell's own `level`,
  `ac` (+ the slot level; a form may add), `hp` and `hp_up` (for each level above the spell's), and `forms`
  {form: {hp, speeds, traits, attacks, damage_type, resist, immune, picture, spells}}; the stat block (statblocks.
  allies.json, numbers as printed at level 0 of "the spell's level") has every action of every form, each attack
  with `plus_level` adding the slot level to its damage and the caster's spell attack as its bonus; the Multiattack
  is half the slot level (round down) of the form's attacks. The creature's own DC is the caster's spell save DC.
- **The form** (Air/Land/Water, a mood, Ghostly/Putrid/Skeletal...) is chosen by the game for this fight, as
  Chromatic Orb picks its best damage type (`allies.best_form`): a form that flies when foes are aloft, the
  element whose blow hurts the foes most, a ranged form when they stand far off, and the strongest otherwise. The
  form is named in the log ("a skeletal spirit").
- **Traits** (data/packs/03_demigods_magics/traits.json, handlers in engine/handlers/summons.py): Regeneration (the
  slaad's 5, `spirit_regeneration`), Whispering Aura (2d6 psychic, Wisdom save, at the start of its turns, to every
  creature but its caster within 5 feet), Festering Aura (Constitution save or Poisoned, whoever starts a turn beside
  it but its caster), Heated Body (1d10 fire to whoever hits it in melee), Stony Lethargy (a foe starting its turn
  within 10 feet: Wisdom save or no Opportunity Attacks and half Speed), Berserk Lashing (its reaction: a Slam at
  whoever hurt it). Pack Tactics, Flyby and Spider Climb are the game's own. Water Breathing, Amorphous Form and
  Incorporeal Passage wait for fights under water and through walls (codex: adapted).
- **Blows that do more** (stat block `on_hit` with kernel ops, `statblocks.ops` "kernel"): the slaad's Claw (no
  healing until the start of its next turn), Deathly Touch (Frightened until the end of the target's next turn),
  Rotting Claw (a Poisoned target is Paralyzed until the end of its next turn: the op `if_condition`), Web Bolt
  (Speed 0 until the start of the insect's next turn), Poison Jab's extra 1d4 poison.
- **Its own magic** (spells of classes ["creature"], at will, Bonus Action): Fey Step (30 feet, then the mood's
  effect: Fuming, Advantage on its next attack this turn; Mirthful, a foe within 10 feet saves or is Charmed until
  it takes damage; Tricksy, magical Darkness on a 10-foot cube beside it until the end of its next turn) and the
  centipede's Venomous Spew (Constitution save or Poisoned until the start of its next turn).
- **The Auto** values a summoning by the spirit's blows over three rounds and its hit points (`estimates`), less
  when the caster already concentrates on something worth more; the spirit itself is played like any ally (z).
- **Costly components** (kept, not used up): a gilded acorn (200 GP), a gilded flower (300 GP), a gilded skull
  (300 GP), a platinum-inlaid vial (400 GP), a lockbox (400 GP) and a gold-inlaid vial (400 GP), sold in cities.
- **Pictures**: the forms from the Crawl pack (hawk, wolf, shark; a faun for the fey; ghost, ghoul, skeleton; an
  eye, a red slaad and a tentacled horror; clay, iron and stone golems; the four elementals; wasp, spider,
  centipede).
- **Tests**: tests/test_summons.py (each spell in a real fight: numbers at two slots, placed at the point, its turn
  after its caster's, gone when concentration ends and at 0, each trait and blow, the Auto casts one); the arena's
  coverage test; the catalogue test's NO_USE has none of them.

#### F.1 — How
- **An ally on the field** is a `Fighter` on the party's side made from a `Creature` (no `char`), with
  `Fighter.bond` {owner (fighter id), kind ("familiar", "steed", later "summon"), spell, level}. `Battle.add_ally(
  creature, owner, kind, ...)` puts it beside its owner (the nearest free squares) at any time; at a fight's start
  `fight.start_battle` brings in every follower of the party (below) through it. Turns: a familiar rolls its own
  Initiative and is put into the order by it; a steed acts right after its owner (the 2024 text: it shares the
  owner's count). Who plays it: the player, as a party member (the battle screen's options for a creature are the
  ones a possessed host already uses), or the Auto with `z` (tactics treat it as any fighter on its team). A
  familiar cannot attack (`actions.options` leaves out every attack, a spell and a blow for it); it can Help, Dodge,
  Dash, Disengage, Hide and move, and the Auto has it Help the friend about to strike the most hurt foe (or Dodge
  out of reach). The steed fights with Otherworldly Slam and its kind's bonus action (Fell Glare, Fey Step, Healing
  Touch, once a long rest each) and Life Bond (it gains what its owner gains from a spell of level 1 or more within
  5 feet). Mounted combat waits for Expansion 9: until then the steed fights beside its rider, not under them.
- **Who has won**: the fight is lost when no character of the party stands (an ally alone does not keep it going: it
  goes with the fallen, as the book's steed disappears when its owner dies), and won when no foe stands, as ever.
  Allies earn no XP and are not the party's dead; what they kill counts for the party (the kills ledger).
- **At 0 hit points** a familiar or a steed disappears (the book): its record is marked gone until the spell is cast
  again; a new casting while one lives changes its form (familiar) or replaces it (steed).
- **Followers outside a fight** are kept on their owner: `char.spells["familiar"]` {form, type, name, hp, gone,
  away} and `char.spells["steed"]` {look, type, level, name, hp, gone} (saved with the character, no format change:
  `spells` is a free dict). Their hit points come back at a long rest. Find Familiar is a ritual (the hour, no slot,
  the 10 GP incense spent); its type (celestial, fey, fiend) and form are chosen on the Spells page (Subjects, as
  E.3), with a name from the game's words. Dismissing it to its pocket and calling it back are road uses of the
  same spell (no slot): one kept away does not come into a fight. Find Steed is a paladin spell (no paladin yet):
  cast from a scroll, a wand or by a companion who knows it, at its slot's level (`level` in the stat block's
  numbers). Its look (horse, camel, dire wolf, elk) and type are chosen as it is cast.
- **On the road**: the steed is a mount in the herd (`leader.animals`, an entry with `summoned` {owner, ...}) that
  its owner rides first (`mounts.assign`); it eats nothing, is never sold, stabled, rustled, robbed or awakened, and
  vanishes when its owner dies. Its pace is a warhorse's (the 2024 travel pace does not grow with speed). The
  familiar keeps watch at night as an awakened animal does (the camp is not caught asleep, `spellwork._awake_watch`)
  and walks behind the party on close-up maps (drawn as followers are, small). Delivering touch spells and seeing
  through its eyes are left out (no touch spell reaches further in a fight than the caster's reach yet; the eyes
  wait for a scouting system).
- **Pictures**: the thirteen forms from the Crawl pack where it has them (bat, rat, raven, spider, scorpion, frog,
  crab, lizard, octopus, hawk recoloured), the cat, owl and weasel drawn by hand (`tools/beast_art.py`), the steed as
  the riding horse in its kind's colours (celestial pale gold, fey green-silver, fiend black and ember). The forms'
  stat blocks are the 2025 MM's (Appendix B's numbers checked on the page images); a type other than beast is
  carried on the creature (`Creature.kind_as`), read where a kind matters (Protection from Evil and Good, Magic
  Circle, Hallow).
- **Tests**: tests/test_allies.py (a familiar and a steed in a real fight: placed, turns in order, the familiar's
  options without attacks and its Help, the steed's slam and bonus action, Life Bond, disappearing at 0, the fight
  lost with only an ally standing, followers kept and healed, the steed ridden on the road, the night watch);
  the arena's coverage test with the new creatures; the autoplay bot checks every follower's record.

### Part G — Enemy casters, services, release
- [x] G.1 Every caster stat block on the catalogue; arena: every battle spell cast by the AI in a scenario; a test
  caster of each spell level 1–9 casts without hangs.
- [x] G.2 Spellcasting services and scrolls in temples, mages' guilds and shops; the law of magic.
- [ ] G.3 Every Expansion 3 codex entry settled; balance; the icon; release v1.3.0.

#### G.1 — How
- **The casters there are.** Today's stat blocks that cast (the acolyte, the cult fanatic; the imp, quasit and sprite's
  Invisibility; the summoned spirits' and the steed's gifts) name only catalogue spells, and the 2025 Monster Manual
  gives the sphinx of wonder none. The book's great casters (the Mage, Priest, Archmage, Lich, Druid...) are assigned
  by the codex to the expansions of their classes and peoples (5, 11, 18...): they come there, on this. A start-up
  check (`engine/check.problems`) refuses a stat block naming a spell that no spell file defines.
- **The test caster** (`tools/arena.py`: `caster_def`, `caster_setup`, `battle_spells`): a war mage (CR 9; a 17th-level
  caster's slots, DC 17, +9 to hit, Intelligence 18) that knows only the spells it is given, cantrips at will, put in
  the arena's four scenarios against a party of fitting level. `arena.py --spells` (`--spell x`, `--shard k/n`) gives
  it each battle spell in turn (every spell cast on one's own turn in a fight: not a reaction, not one used outside a
  fight, not a creature's gift, an item's or a follow-up) and reports how often the tactics cast it and what broke.
- **The rule**: every battle spell is cast by the enemy in some scenario, through the same `estimates` the Auto uses
  (no spell is chosen by name), or has a reason in the test's NOT_CAST (as the catalogue test's NO_USE: the field is
  lit, nobody here is invisible). Where a spell's rules were written for a party caster only, they become anyone's.
- **Levels 1-9**: a test caster with every battle spell of one level (and the cantrips) fights each scenario to its
  end: no hang, nothing the rules refuse, nothing broken, the turn budget (150 ms at the 95th percentile, never 400
  ms, in the thread's own time).
- **Tests** (tests/test_enemy_casters.py, slow): every stat block's spells are the catalogue's and usable in a fight
  (or their use is outside one); each battle spell cast by the enemy; the nine levels without hangs.

#### G.2 — How
- **Who casts for pay** (PHB 2024 p. 232, Spellcasting; the table's prices checked on the page image): a temple's
  priest casts from the cleric's list, a new townsperson, the **mage**, from the wizard's. Each has a highest spell
  level they can cast for you: the table's availability by place (cantrips to level 2 in a village or hamlet, to 5 in
  a town, hold or elf-hall, to 9 in a city), and within it each one's own reach, settled once by their name (a
  village priest 1-2, a town's 3-5, a city's 5-9: "the higher the level, the harder to find"); a figure of the world
  (a temple's high priest, the circle's archmage) reaches the place's limit. The price is the table's (30 GP a
  cantrip, 50, 200, 300, 2,000 for levels 4-5, 20,000 for 6-8, 100,000 for 9), moved by their mood as every fee is,
  plus the value of a costly component (the book: add its cost).
- **What they cast** (`game/spellhire.py`): every spell of their list and reach that does something for the party
  outside a fight, through the same code the party's own casting uses (`magic.cast_on_road(hired=True)`: no slot, no
  material, no strain; the caster is the townsperson made a character of their class and level, kept for the
  session only): healing and restoring (on whoever needs it most), returning the dead the party carries (Revivify,
  Raise Dead, Resurrection, True Resurrection), lasting spells of an hour or more on one of the party or all of them
  (Aid, Death Ward, Darkvision, Water Breathing, Mind Blank...), Remove Curse, Regenerate, Gentle Repose, food,
  water, purifying, the Heroes' Feast, asking the powers (Augury, Divination, Commune, Legend Lore), Locate Object
  and Locate Creature, Sending, Mending, Identify. Only what would do something now is offered, each with its
  target ("Lesser Restoration, for Mira"). Spells that need the caster to stay with you (familiars, summons, shapes,
  wards on a camp, travel, the great magic) are not for hire.
- **The mage**: one in a town where a mages' circle keeps a house, two in a city, three in a great one (in the
  library, or working at home); at the circle's seat its archmage is one of them (`people.FIGURE_JOBS`). Their wares
  (economy.json shop "mage"): spellbooks, foci, ink, parchment, the costly components, scrolls of the wizard's list
  and the common and uncommon magic items of a city. Scrolls by rarity (DMG 2024: common and uncommon are bought;
  rare ones seldom, in cities; very rare and legendary never): the mage's scrolls to level 3 in a town and 5 in a
  city; the temple's of the cleric's list to level 1 in a village, 3 in a town or city; the apothecary's and general
  store's few as before.
- **The law of magic** (`game/law.py`, realm laws legal / licensed / forbidden): casting by the party in a town is
  seen and judged as before (`law.magic_check`), now for whoever in the party casts (a feat, a scroll, a companion),
  and never for the townsperson you paid (they have their licence). A licence is bought from a lord, a headman or a
  mage of a licensed realm by any party with a caster. Where magic is forbidden: no scrolls or magic things on open
  sale (the temple's own prayers excepted), and a mage casts for you only where nobody else sees, at half as much
  again for the risk.
- **The screen**: the services list scrolls (arrows, Enter, the wheel), and a spell's line shows its card.
- **Tests** (tests/test_spellhire.py): the price table and the reach by place; every spell a priest and a mage of
  level 9 offer is cast for pay in a real town without error and does its work (a body raised, a wound healed, a
  thing identified, a buff kept); nothing offered that would do nothing; a mage in a forbidden realm refuses with
  witnesses near; the hired caster breaks no law; scrolls and the mage's wares by place and law.

#### G.3 — How
- **Simulacrum** (PHB 2024 p. 320: level 7 illusion, wizard, 12 hours, powdered ruby worth 1,500+ GP consumed: the
  city markets' vial of ruby dust): a road op `does: "simulacrum"` in `game/greatmagic.py`. Its subjects are those
  within ten feet for the twelve hours: anyone of the party (the caster too), a beast of the herd that has a stat
  block (the mule, the horses, the camel, the elephant, the mastiff), and a prisoner who is a beast or a humanoid.
  Casting it again destroys the simulacrum made before.
- **A copy of a party member** is a character made from the original at the time of casting (`rules/simulacrum.py`:
  the original's record copied, its hit point maximum halved and the hit points full; what they wear and hold
  copied in snow, nothing in the pack, no money; no familiar, steed, servants, shape, Contingency or Simulacrum of
  its own; it never levels, rests or eats). It is kept on its maker, `char.spells["simulacrum"]` {of, char (the copy's
  record), made}, and walks behind the party (drawn as the original, pale as frost). In a fight it is a party-side
  fighter with the character's classes, spells and the slots it had (they never come back), bond kind "simulacrum"
  and type construct, placed beside its maker and acting right after them (played as a party member: z for Auto);
  healing does nothing to it, at 0 hit points it melts (no death saves), and it earns nothing, is never counted
  among the party's dead and does not keep a lost fight going. After the fight its record is written back.
- **A copy of a creature** is a servant record (`rules/servants.py`, spell "simulacrum", type construct, half the
  stat block's hit points, never healing by itself); it follows into towns too (the raised dead do not).
- **Repair**: at a long rest with its maker, the maker spends 100 GP per hit point restored, up to what is missing,
  but never more than half of the coin they carry (the game's choice: a rest never empties the purse); the log says
  what was spent.
- **Balance**: `tools/balance.py --runs 60` across the expansion's numbers; the bands stay as they are or the change
  is explained in the notes.
- **The icon** (`tools/tile_art.dlc_icons`, "dlc/demigods_magics"): a crowned silhouette rising out of an open book
  that spills light; pack.json released, version 1.3.0; README, CLAUDE.md, PROGRESS (release notes §5.3), tag and
  the GitHub release.
- **Tests** (tests/test_simulacrum.py): the copy is made with half the maximum and only what is worn; a second
  casting destroys the first; it fights in a real battle beside its maker (party side, construct, no healing, melts
  at 0, not among the dead, no XP); its slots stay spent across fights; the repair at a long rest and its cap; a
  beast's and a prisoner's copy as servants; the save keeps it.
