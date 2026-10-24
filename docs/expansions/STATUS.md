# Expansion programme – status

Current: 06 Adventures & Events · Part B (show, don't tell: the stage, pictures, places that change) · branch dlc/06-adventures-events
On GitHub (main): World Variety · Clearing the decks (§0.4) · 01 Dice & Destiny (v1.1.0, 2026-10-13: the rules kernel,
  the 2024 rules, the 2025 creatures, reactions that ask, Tactics 2.0, magic items and treasure, encounters by the
  budget, cards and status icons, adapted monster pictures, spell looks, the shelf) · 02 Blades & Backgrounds
  (v1.2.0, 2026-10-13: the 2024 weapons, armour and masteries; species, sixteen backgrounds and origin feats; the
  general and fighting style feats; the 2024 tools and gear, trinkets, inns and lifestyles, coaches, ships and
  messengers, mounts, saddles, stabling and vehicles; saves format 16) · 03 Demigods & Magics (v1.3.0, 2026-10-17:
  twenty levels and the epic boons; the fighter, rogue, cleric and wizard of 2024 to level 20 with eight subclasses;
  spellcasting by the 2024 rules; the catalogue of 191 battle spells and Wish; spells outside battle in every system;
  familiars, steeds, summoned spirits, the raised dead, the bound, Polymorph and Shapechange, the 24 creatures of
  Appendix B; enemy casters; spells for pay and the law of magic; Simulacrum; saves format 18) · 04 Steel & Shadows
  (v1.4.0, 2026-10-17: the Battle Master and its twenty maneuvers; the Eldritch Knight and the Arcane Trickster; the
  DMG poisons, the Assassin, Spy and Spy Master, the black market, poisoned cups, duels, spies at court; the fighter's
  and rogue's magic items of the DMG; saves format 18) · 05 Schools & Domains Part A (2026-10-18: the Diviner and
  the Illusionist; images on the battle mat) · Part B (2026-10-18: the Light and Trickery Domains; the faiths'
  domains and the gods' answer to the dying devout) · Part C (2026-10-18: the Mage Apprentice, Mage, Archmage, Priest
  and Archpriest in the world; wizards' towers lived in; apprenticeships) · Part D (2026-10-18: the eleven wands, seven
  staffs and four rods of the DMG; one store of charges a thing, cast in fights and from the Spells page) · Part E (2026-10-18: crystal balls, the wizard's
  hats, the Pearl of Power, the Ring of Spell Storing, the five robes, Enspelled Armor and Weapon, the Ruby of the War Mage;
  **released as v1.5.0**) · 06 Adventures & Events Part A (2026-10-24: threats, the story engine and the Beast of
  {place} from its hook to its epilogue; saves format 19)
Codex coverage: 2,951 entries from the three books, every one assigned to an expansion; Expansion 1: all 327 settled
  (237 done, 65 adapted, 25 omitted; `tools/codex/coverage.py --dlc`); Expansion 2: all 384 settled (310 done, 74
  adapted); Expansion 3: all 560 settled (223 done, 336 adapted, 1 omitted); Expansion 4: all 66 settled (36 done,
  30 adapted); Expansion 5: all 72 settled (39 done, 32 adapted, 1 omitted). PHB 69% · DMG 21% · MM 17%
Known, not yet chased: one autoplay run of nine during Expansion 5 Part A's checks (2026-10-18) saw two townsfolk on
  one square of a town for seven turns (town life, untouched by the part; the other eight runs, on main and on the
  branch, were clean). The timing tests (an enemy turn under 150/400 ms) now and then miss while the suite runs
  beside autoplay and the smoke test, and pass alone; this was already so in Expansions 3 and 4.
Assumptions waiting for Anton:
- Expansion 5 Part E (robes, hats and the rest): a Hat of Many Spells is worn, not held, and its wrong spell goes at a
  target chosen by chance; its creatures run off the field (nobody's), its bats bite once (2d4) and scatter, its
  portal closes at once, its magic item is a potion of healing of the rolled rarity and stays; spells go into a
  Ring of Spell Storing only outside a fight (the Spells page, r), and a found ring holds wizard and cleric battle
  spells at the numbers of a caster of their level; the game's Light lights its caster, so it blinds a Robe of Eyes'
  wearer who casts it (Daylight within 5 feet as printed); the Scintillating Colors spare the wearer's friends; the
  Robe of Stars' stars come back at dawn, and its Astral Plane is a round off the field (back at the start of the
  wearer's next turn, the Magic action spent); the Robe of Useful Items' door, pit, window and rowboat are rolled
  again and its silver coffer is a 750 GP art object; the ruby is set from the pack (ten minutes) and the weapon must
  be in hand; patches are torn off and the ruby taken off outside a fight only (the pack); a ring takes spells only
  on an attuned finger; the crystal balls' gifts work through Scrying on the road (Telepathy's Suggestion: a person who fails
  thinks well of you for eight hours); the Enduring Spellbook's gift is on its card only (nothing harms paper yet);
  the Auto breathes on the Pearl of Power only when every slot is gone and no foe is at hand, and steps into the
  Astral at a quarter of its hit points with two foes beside it.
- Expansion 5 Part D (wands, staffs and rods): a wand's, staff's or rod's spells are cast from the pack, as Expansion
  4's charged things already were (the book: "while holding"); the War Mage's +N, the Staff of Power's +2s, spell
  absorption (the Staff of the Magi, the Rod of Absorption and its slots) and the Staff of Charming need the thing in
  hand; a countered spell from a wand still spends its charges (the 2024 Counterspell gives back only a slot); the Wand of Enemy Detection shows where every foe within 60
  feet stands for a minute (not only the nearest one's direction); the Wand of Fear's Command is "Grovel!" (the game's
  Command has no "Flee"); Retributive Strike's "travel to a random plane" is being thrown clear, unharmed, half the
  time (no planes until Expansion 27), and the Auto never breaks a staff; the Rod of Absorption's stored levels give
  back a spent slot, with no action, in a fight (the Auto draws one when its best slots are spent); the Rod of
  Alertness's planted aura goes with its bearer and lets friends in it see the invisible anywhere in it; the Rod of
  Rulership's charmed foes stand still awaiting your word (Incapacitated) until harmed, and with the Staff of
  Charming it works in fights only; a reflected enchantment is cast at its caster once its own casting is done;
  the Staff of Striking spends as many charges as fell the foe (all three on a strong one); the Staff of the Magi
  drinks a spell only when it would not burst (unless the player says so); the Wand of Pyrotechnics is an evening's
  show at camp (the spirits rise as with music); the Staff of Adornment's trinkets are words on its card; the
  Enspelled Staff binds a spell the game can cast of the variant's levels; a book item's look now comes from its book
  name; the book's Mage carries a plain wand (its focus); the debug console's `book <item>` gives one.
- Expansion 5 Part C (mages and priests of the world): the book's "Gear: Wand" is the crystal focus until Part D's
  wands; a priest's unprinted DC is 8 + PB + Wis (13); a tower master's ward makes a lock 5 harder (the book's Arcane
  Lock says 10: a party without Knock would find a lived-in tower shut for good); a tower's guardians are the master's
  familiars and apprentices until the constructs (Expansion 18); a tower master is an Archmage at level 13+ or fame
  8+, else a Mage, and so are the history's circle heads (temple heads are Archpriests); a great city's first temple
  and first mage are an Archpriest and an Archmage; the apprenticeship's lesson is a wizard spell up to third level
  (or a scroll of first or second level with no wizard in the party); killing a tower master costs 6 standing with
  every mages' circle.
- Expansion 5 Part B (the Light and Trickery Domains, the gods): Warding Flare shields only the cleric's own side, laid
  by the battle's judgement (asked under the Reactions setting "all"): a blow likely to land at a friend in a bad
  way, a heavy one, or any while uses are to spare; the Corona's "any spell that deals Fire or Radiant damage" is the
  cleric's own; the corona and the double are not dismissed early; the double is made or moved beside the foe it is
  aimed at, never elsewhere (the battle picks the square, flanking first), and spells aimed at a creature or a point with a range of 10 feet or more that do not move
  their caster go out from its square when the target is beyond the cleric's own reach (still seen with the cleric's
  own eyes; cones and lines go out from the cleric; a foe sees the double unless Blinded); the Blessing of the Trickster is laid on the party's worst sneak at each long rest (a Magic action moves
  it in a fight) and read by hiding in a fight, creeping in towns and slipping past a band; each faith names its
  domains by the feel of its god (data/factions.json), a cleric takes the first by default (War for a fighting
  priest where the god has it); the gods answer only the dying devout in fights (2% and up to 12%, a year's quiet
  after), with a gift by domain - the DMG's blessings, emissaries and omens wait.
- Expansion 5 Part A (the Diviner and the Illusionist): Portent is laid by the battle's judgement (asked only under the
  Reactions setting "all"), outside fights on the party's camp and conversation checks only; the Third Eye's reading
  of every language is left out (every writing of the world is already readable); the Search action also studies the
  images in sight (Investigation against the caster's DC; the Study action is aimed at creatures); the caster's whole
  side knows an image for what it is; an image is never laid over a creature; the phantom summon is taken whenever
  Summon Beast or Fey is cast at its own level with the free use ready (a higher slot gives the full creature; the
  costly material is still needed; the battle screen offers the phantom beside the slots, the Auto takes the
  phantom); Illusory Self comes before Shield and spends a slot only when Shield could not turn the blow; what
  Illusory Reality makes real is a wall of stones (a bridge over water or a chasm), ending with the spell even inside
  its minute; Portent is not laid on Initiative, nor on the dungeon's own checks (search, locks, traps). Casting options now take the caster's casting time (an abjurer's
  bonus-action Dispel Magic is listed as one); a Thaumaturge's extra cantrip is no longer swallowed at the next level.
- Expansion 4 Part D (the fighter's and rogue's magic items): the Defender's guard is chosen as each turn begins by the
  battle's judgement (all three to Armor Class when hurt and pressed, two against two foes, one against one, none
  with nobody near); the Rod of Lordly Might's Drain Life and Paralyze fire on a hit against a foe still strong
  (asked of the player only under the Reactions setting "all"), its light and its ladder are left out, its ram is +10
  to forcing doors and its needle +5 to keeping bearings; the Luck Blade's luck rerolls saves and blows in a fight
  only, and its Wish is cast in a fight (Instant Health, with Wish's stress), as no item casts on the road; the
  Veteran's Cane strikes as a club while it is a cane (the Auto draws the sword at once); a Dancing Sword more than 30
  feet away as its bearer's turn begins flies straight back to the hand; the Vorpal Sword finds no head on oozes,
  elementals, plants, constructs, swarms, amorphous or many-headed creatures or anything Gargantuan (30 slashing
  instead); the Sword of Wounding's unclosing wound lasts the fight (the book: an hour); the
  Sword of Vengeance's spirit binds blows only (spells may go elsewhere), and the curse lifts in the usual ways
  (Banishment cannot be aimed at a thing), leaving a +1 sword; the Executioner's Axe's temporary hit points are the
  extra damage as rolled; the Sword of Sharpness's exhaustion on a creature lasts the fight; the Boots of False Tracks
  give +5 to seeing a band of people first (there is no tracking); the Amulet of Proof against Detection keeps foes'
  divination spells and Detect Thoughts off its bearer (nobody scries the party yet); the Weapon of Warning works from
  the pack once bound and wakes a sleeping camp. From the fresh review: the unclosing wound now stops every healing
  (potions, Second Wind, a troll's regeneration); the terrified make no opportunity attacks; the Gloves of Thievery
  hide only while worn; a Luck Blade reroll of 20 is a critical; companions on Auto use charged things (a Mace of
  Terror against a crowd).
- Expansion 4 Part C (poisons and the people of the shadows): the assassins' trade is the thieves' guilds' (no
  separate assassins' faction: the world's history is unchanged); inhaled poisons are thrown up to 20 feet like a
  flask (the book: blown beside you); contact poisons on a weapon work on any hit, nothing else is smeared and
  nothing is washed off; a poison's companion condition (asleep, paralyzed, blinded) ends with the fight, the
  Poisoned condition lasts the poison's hours; a lethal cup kills an ordinary person before morning (no days of
  sickness for townsfolk); venom only from the dead; truth serum works in the conversation it was given in; the
  black market (towns and cities, members only, x1.5); poison allowed among the orcs, Khurgan, Itzan and
  Thalassians, duels among the southerners, highlanders, northmarchers and Volsk (by the feel of each culture); a
  duel is to the first fall and a death in it is no murder; Identify names only magic things, so it does not reveal
  a Potion of Poison (Detect Poison and Disease does).
- Expansion 4 Part B (Eldritch Knight, Arcane Trickster): a new level opens the whole prepared list (the book: one
  spell a level), no cantrip swap on a level; a component pouch comes with the path; War Bond's ritual is done at a
  rest over the weapon in hand and one of another reach (no third bond), robbers cannot keep a bonded weapon;
  Arcane Charge lands beside the weakest foe out of reach (the battle's judgement); the unseen hand robs stalls and
  picks pockets unseen (no locks; no trap disarming exists); Spell Thief is the battle's judgement on a harmful spell
  of level 1+, kept until the next long rest; hidden counts as Invisible for Magical Ambush; fighters and rogues on
  Auto with Intelligence 14+ (not great weapon or shield) take the arcane path; mid-Attack-action casting now needs
  War Magic (it used to be free), a vial thrown mid-action takes an attack. Spell Thief takes the reaction by
  itself (it cannot be kept for Shield) and guards the trickster only when aimed at or caught in the area;
  a knight is never disarmed even when Incapacitated (nothing disarms then anyway); the unseen hand has no card.
- Expansion 4 Part A (Battle Master): one maneuver an attack, chosen by the battle unless the Reactions setting is
  "all" (Precision, Parry and Riposte are asked as Stroke of Luck is); Ambush at Initiative is the battle's choice on
  a poor roll; the check maneuvers spend a die only when it can turn a failure; no swapping a known maneuver; a friend
  moved by Maneuvering Attack draws no blows at all; Lunging counts any 5 feet moved this turn; a disarmed weapon is
  back in hand at its holder's next turn; Relentless always takes the turn's first maneuver free; fighters on Auto
  take the Battle Master unless they fight with a great weapon (Champion) or a shield (Knight); Know Your Enemy makes
  the creature's kind known (its card shows AC and hit points too); Bait and Switch only with a one-square friend.
- Expansion 3 G.3 (Simulacrum): the copy's gear is snow in the likeness of what was worn and held, without its
  magic; no spell heals it; a long rest's repair spends at most half of the maker's coin; a beast's or a prisoner's
  copy follows the party into towns (the raised dead do not); commands are the battle's (played as a party member);
  no snow on the ground is needed; it acts right after its maker; its once-a-rest uses are those of the casting and
  never come back; the repair is paid from the maker's own coin.
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
- Expansion 2 part A: the lance is always two-handed until mounted combat (Expansion 10); magic ammunition is spent
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
- Expansion 2 part C: Mounted Combatant is written but not offered until mounted combat (Expansion 10); a duellist
  keeps a versatile blade in one hand; Spell Sniper's reach is for attack-roll spells only; Sentinel answers a hit
  on anyone but the sentinel.
- Expansion 2 part D: coaches run up to 160 miles at 4 mph for 10 hours a day; ships 2 mph day and night up to 600
  miles; a messenger rides 30 miles a day there and back; hired companions keep their own wages (below the book's
  2 gp a day, as they share the loot); the inn charges each of the party; a mirror and perfume please the gentry a
  little (+2, +3); a carried basket, pouch, quiver or chest adds to what you can carry; a thrown net is shaken off
  with a Strength save at the end of each turn (the book: an action and a DC 10 Strength check), and catches a Huge
  thing too; barding and the horses' stat blocks wait for mounted combat (Expansion 10: there is nothing for a mount
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
- Expansion 3 C.2: a focus anywhere in the shared pack serves; Verbal and Somatic components are taken as given (no
  silence or bound hands yet); a consumed component is kept when a Counterspell stops the spell; the Auto and the
  enemy spend a higher slot only when it is spare (no spell of that level ready); diamonds are sold at temples,
  pearls and diamond dust at town markets, at book price.
- Expansion 3 C.3: the check to read a scroll above your level uses the spellcasting ability (the 2024 DMG; the
  design note said Arcana, which is the thief's Use Magic Device check); a scroll stopped by a Counterspell is kept;
  a domain's always-prepared spells count as on the cleric's list for scrolls; a scroll casts with its own DC and
  attack (no focus bonus); a potion is a bonus action for everyone (Fast Hands is for the action's things); the
  Auto weighs a scroll as half a slot of its level; out of a fight the surest reader in the party reads a scroll from
  the pack; Identify takes a minute (eleven as a ritual). Codex: a repeated spell replaces the old casting rather
  than keeping the stronger (adapted), and an ongoing spell needs no Study check to name: it shows on its card.
  Spellcasting services (PHB p. 235) wait for G.2, as planned.
- Expansion 3 D.1: each wave of the catalogue brings the spells that work in a fight; a spell whose use is outside a
  fight comes with its system in Part E, the summoning spells with Part F (the lists are in the design note; Aid
  waits for E because its raised maximum must outlive the fight). The 2024 smites and Hail of Thorns are readied on
  the weapon with the bonus action before the blow (the next fitting hit within a minute). A chosen damage type
  (Chromatic Orb, Dragon's Breath, Sorcerous Burst) is the one the target is weakest to; Resistance's type is the one
  the foes deal most. Moonbeam, Flaming Sphere and Cloud of Daggers move anywhere within 60 feet of the caster.
  Reduce is in (Enlarge waits); Dragon's Breath and Magic Weapon work on the caster only; Calm Emotions and
  Suggestion make a foe stand down until hurt; Crown of Madness's blow is at the foe's own friend hurt worst;
  Arcane Vigor heals 2d6 + the modifier (no Hit Point Dice spent); Warding Bond lasts the fight. Every left-out
  rider is in the codex notes. The older spells now carry their full 2024 class lists. Fixed on the way: party
  cantrips never grew at levels 5, 11 and 17; a die taken off a roll (-1d4) could not be rolled.
- Expansion 3 D.2: the 2024 Conjure spells (Animals, Barrage, Minor Elementals, Woodland Beings, Elemental, Volley)
  are ground or auras, not creatures, so they came now; a moved pack of spirits or a later heal of Aura of Vitality
  costs a bonus action (the book gives them free). Banishment's foe is out of the fight while the caster holds the
  spell (a banished foe still counts for the fight's end); one from another plane kept away for the whole minute never
  returns; Banishing Smite's always does. Blink rolls at the end of each turn (11+ away until the next). Dispel Magic
  is aimed at a square (the creature there and the ground). Walls are laid at a point (a line always starts at the
  caster); Wall of Force also hides what is behind it; Wall of Stone is never made permanent and cannot be broken.
  Haste's extra action is one more attack in the Attack action; Slow takes the bonus action and all but one attack;
  Slow and Hypnotic Pattern catch every foe in the area (no cap of six). Confusion's wanderer walks a random way.
  Dominate turns a foe to the caster's side; each hurt lets it save again. Protection from Energy picks the energy the
  foes deal most; Elemental Weapon and Conjure Elemental are fire. Steel Wind Strike strikes each foe in reach once.
  Bigby's Hand is the Clenched Fist only (and takes the place of a Spiritual Weapon); Antilife Shell wards friends
  against every kind but undead and constructs rather than barring the way. Polymorph waits for Part F (the beasts).
- Expansion 3 D.3: walls of blades and thorns are lines from the caster's side (no rings, no cover from the blades);
  the Wall of Ice is a 20-foot block that cannot be broken; Fire Storm is one 30-foot block that spares friends;
  Delayed Blast Fireball bursts at once (no growing bead); Eyebite always puts to sleep; Otto's dancer spends its
  whole turn on each save to stop; Mass Suggestion stands foes down until hurt, as Suggestion does; Harm's lost
  maximum comes back after the fight; the Globe of Invulnerability moves with its caster; Conjure Celestial's
  pillar heals friends and sears foes and is moved with a bonus action; Divine Word's 24-hour exile is for good;
  Plane Shift waits for Part E (the 2024 spell only carries willing travellers; the old banishing touch is not
  in the book, so it was left out); the Forcecage is the solid box only, and a
  caster whose only foes left are sealed in its own sphere or cage lets them go at the start of its turn (so a won
  fight ends); Reverse Gravity lifts those in it as it is cast (100 feet, or into the ceiling 20 feet up under a
  roof or below ground), not those who walk in later; Regenerate takes a minute to cast and so waits for Part E;
  Prismatic Spray's violet ray sends its victim away for good. The new costly components are sold at markets:
  mushroom powder in towns; a black pearl, ruby dust, a miniature platinum sword and a forked metal rod in cities.
- Expansion 3 D.4: Earthquake and Storm of Vengeance spare the caster's side, as if cast from afar (on our fields
  their 100- and 300-foot reach would take in everyone); the Earthquake's save comes as foes enter or start a turn
  in it (the book: when cast and at the end of the caster's turns); the Incendiary Cloud does not drift; the
  Prismatic Wall is a 30-foot block that stops friends too (its seven layers are never crossed), and its glare
  blinds foes within 20 feet for a minute; Meteor Swarm's other three spheres are laid by the battle where they
  catch the most foes and the fewest friends; Befuddlement lasts a day (the book: until a save every 30 days);
  Weird's fear and its nightmare are shaken off by separate saves; Power Word Heal's prone creature stands without
  its reaction; Mass Heal heals the worst hurt first; Time Stop's turns end as soon as anything the caster does
  reaches another creature (an event touching it), and foes cannot take reactions in a stopped time only because
  none come (the caster moving away could still draw one: left as it is); Tsunami waits for Part E (cast in a
  minute, as Regenerate and Imprisonment). Wish in a fight: copies of any battle spell of level 8 or lower (its
  action and level 9 slot; no components; no stress) or Instant Health (with the stress); the Strength lost to the
  stress comes back after its days whatever you do (resting does not shorten it); the Auto weighs only copies of
  levels 7 and 8 (the player sees them all). Wish's other uses (Object Creation, Resistance, Spell Immunity, Sudden
  Learning, Roll Redo, Reshape Reality) wait for Part E. No druid yet: Storm of Vengeance is a druid spell, so no
  one can learn it until the druid comes (a scroll can be read by... nobody yet).
- Expansion 3 E.1: a fallen companion's body is carried while someone in the party could raise them (a spell of
  return ready, or one they could prepare whose reach is a day or more, or a scroll someone can read), and is buried
  after ten days dead (Gentle Repose stops the count) whatever Resurrection could do, or at once when nobody could
  raise them; a companion still standing calls a fallen leader back at once if a spell is ready (cheapest first), and
  after a fight casts Revivify on a friend in its last minute; the player decides the slower raisings (Spells page,
  aimed at a body). Revived bodies are held together a while (blood, hunger, thirst, cold eased so the cause does not
  kill again at once); Revivify's caster binds bleeding wounds. The death toll (-4) goes down by one a long rest, not
  by the hours. The wards belong to the camp and are not kept in a save (as a campfire is not); the Hut and the
  Mansion turn the night's visitors away, Alarm and the Hound wake the camp (the Hound bites the first, 4d8 force on a
  failed Dexterity save), Rope Trick lets a short rest happen with enemies hunting, the Mansion any rest; no ward in
  the middle of a town but the Mansion. Aid on the road picks the caster and the two worst hurt; Heroes' Feast also
  feeds and waters; Create Food and Water's food is fifteen days' rations that spoil in a day, its water fills the
  skins after the thirsty drink; Regenerate's hour of healing happens at once; Reincarnate's new body is whole (the
  book does not say) and its people are rolled on the book's table, again among this world's peoples if needed;
  Remove Curse loosens every cursed thing on a person (the curse returns when it is put on or bound again). Companions
  conjure food or water by themselves when there is none, and cast a ritual ward before a long rest in the wild.
  Spells used only outside a fight carry `road_only` (or `minutes`) and are never offered in one; the Auto prepares
  them last (the player chooses them for a need).
- Expansion 3 E.2: E.2 was split at its start (64 spells in six groups): light, the body on the move and travel are
  E.2; finding and seeing, asking the powers and talking became E.3; the old E.3 is E.4. Teleport's familiarity: a city
  visited is a permanent circle whose sigils are known (always on target: its temple keeps one), the character's home
  town is very familiar, a town visited was seen casually, a town only heard of was viewed once; a similar area is the
  nearest town of the same kind; teleporting an object alone and false destinations are left out. Teleportation
  Circle's sigils are learned by visiting a city (not two given at the start). Word of Recall's sanctuary is made by
  casting it standing in any temple (gods are not told apart yet). Travel by magic (Teleport, the circle, Recall, the
  plants, Plane Shift, Etherealness...) is never cast in a fight. Only a party carried wholly by magic (Phantom Steeds
  for everyone, Wind Walk) travels faster than a walker: the 2024 travel pace does not grow with speed, so Longstrider
  only makes up for a load or a lame leg on the road. Light and Daylight shine round their caster (not on a thing set
  down); Dancing Lights light one patch and are not moved. Enhance Ability works on the target's best ability, its
  Advantage counted as +5 (the passive rule) everywhere. Gaseous Form and Feign Death are fight spells only, and the Auto
  uses them only on a friend about to fall; a lost fight with a feigner: the foes take all for dead and go, the fallen
  beside the feigner make the Constitution save of those left for dead. Water Breathing walks a lake's bottom (not the
  sea's: Expansion 23) at half pace, soaked; Water Walk walks lakes and the sea's face; a spell ending out on the water
  means an hour's swim for the shore. Etherealness under the ground lets the party walk through walls and doors, traps
  do not spring, chests cannot be touched; on the road nothing meets it; back inside stone it is pushed out (2 force a
  foot). Until the planes (Expansion 27) Plane Shift lands at a city's circle or 2d12 miles from another known town;
  Astral Projection and Gate land on target at any known town (Astral Projection takes a jacinth and four 25 GP silver
  bars a traveller, the book's 100 GP bar). Meld into Stone is a ward for a lone caster. The Unseen Servant halves the
  camp's chores. Feather Fall is cast by itself (the battle's judgement, and over a dungeon's pit).
- Expansion 3 E.3: the powers answer from what is truly in the world, in plain words: Augury reads weal or woe from
  the level below (its strength against the party, the hoard at the bottom), the road (the land's danger) or a work
  (its hidden side, its reward); Divination answers only about a work in hand (the truth of it and where its place,
  person or beast is); Commune asks the question chosen and the two weightiest of those the world can answer (a work
  as told, an artifact where it lies, a dragon alive, a beast in its lair, a companion well), Contact Other Plane five,
  one in six "unclear"; the four of them share the book's growing 25% of no answer when asked again before a long
  rest, each counted by itself. Contact Other Plane's failure leaves the caster unable to cast and incapacitated in a
  fight until a long rest (Greater Restoration ending it waits for that spell on the road). Commune with Nature counts
  a map tile (three miles) round you; its CR 10 creature is a dragon or a beast of the songs (portals wait for the
  planes). Legend Lore on a thing carried identifies it with its curse (the DMG's other ways never show a curse).
  Scrying's connections (a likeness, a possession, a body part) are left out; the figures one can scry are those met,
  the rulers of the realm you stand in, dragons and the beasts of works in hand. Detect Magic and Detect Poison are cast
  outside a fight only (nothing in a fight is magic but spells already shown on the cards); a chest's contents are
  settled when Detect Magic looks into it (and kept in the save until opened). Find Traps (the book: not where):
  searching for a sensed trap and saving against it have Advantage. Locate Object and Creature work on close-up maps
  only (a mile is a third of a map tile). Arcane Eye's hour is the whole level it can reach at once, never past a
  secret door. Beast Sense needs an animal of the party's. Drawmij's Instant Summons: robbers and the watch keep what
  they take in a sack or a strongbox, so it comes back; sold or given away, it does not (and who has it is not told);
  inn thieves take only coin, so nothing there. A language rule on the road: a band whose stat blocks share no tongue
  with the party (Common for everyone, and each one's languages) cannot be talked past; today only gnolls and trolls
  (the troll's fearlessness stops it anyway); Tongues opens it, Comprehend Languages at +5. Speak with Animals lets
  beasts be talked past (the Influence check by their Intelligence, as for anyone). Speak with Dead asks only a foe of
  the last fight, where you fought, within a day (not kept in a save): its band is the nearest gang, cult or tribe of its kind with
  a place of its own. Speak with Plants warns for four hours (a band is seen first) and gives +5 to forage. Message
  calls a companion waiting in the same town; Sending, Telepathy and Dream send a waiting companion on their way (24
  miles a day); Animal Messenger reaches 50 miles and is always a ritual on the road (a higher slot adds nothing).
  Dream's nightmare is for a dragon or a named beast (its save by kind); it meets you within a day 3d6 the worse.
  Rary's Telepathic Bond: none of the linked is surprised while two or more are linked (our surprise is a side's).
  Detect Thoughts senses a thinking mind (a person, or a creature with a language) within 30 feet as if it were seen;
  outside a fight it reads a townsman within 30 feet (Wisdom save, +2 for the notable; a success leaves them colder).
- Expansion 3 E.4: E.4 was split at its start (54 spells and Wish in seven groups): minds and the law, disguise and
  illusion and the small arts are E.4; locks and stone, weather and land, lasting protections and great magic are E.5.
  A conversation takes no time here, so a spell of a minute (Friends, Thaumaturgy) lasts for the talk that follows
  (ten minutes of the world). Friends' Friendly is Advantage on the Influence checks; when it ends they like you 20
  less. Enthrall's -10 makes the held no witnesses at all (their eyes on the speaker), and it is offered only in a
  town. Zone of Truth answers about a work they gave you (or tells what they want). Geas's command is the game's:
  silence about your crimes, what they want and hide, Friendly, and a guard never arrests you (they obey, so its 5d10
  never comes); when it ends -40. Modify Memory forgets the last day's unreported crimes (and the casting itself), and
  the grudge each left (by its severity) and a Friends of that day; a report already made stands; older grudges stay. Glibness covers the Influence
  checks, bribing the watch and a disguise kit. Antipathy/Sympathy is cast on the caster, names a kind of creature
  that roams the land here (from the land's encounters), and acts when a band of that kind is met on the road
  (Antipathy: most of it fails, it runs; Sympathy: the failed come entranced, the party sees them first). Awaken works
  on the party's animals (a 1,000 GP rare stone for the agate); the awakened one keeps watch at night and calls out
  rustlers; plants wait for Part F. Disguise Self and Seeming are disguises as good as the spell save DC; Alter Self
  stays one nobody sees through. Minor Illusion, Silent Image and Major Image are cast only in a town and are a
  penalty to every watcher's Perception there (thefts, creeping, the watch's look at a wanted face); a Major Image from
  a 4th-level slot stays until you leave the town. Mislead and Invisibility on the leader leave no witnesses in a town
  for their hour, until an assault or a murder ends them; a geased person is no witness either. Programmed Illusion and Magic Mouth stand while you camp (camps are not kept when you move on);
  Hallucinatory Terrain and Mirage Arcane hide the camp (an Investigation check by the cleverest of a band against
  the DC sees through, rolled hourly for hunters on a close-up map) and then let any rest be taken with enemies near.
  Stacked illusions and Enthrall leave a merchant's watch at DC 5 at least; an illusion also lowers the chance that a
  guard knows an undisguised wanted face (by a twentieth for each point). Project Image hears a known town's news within 500
  miles and reads its board. Illusory Script's letter waves you through gate searches and impresses everyone (+5, as
  a lord's signet). Nystul's Magic Aura masks a magic thing from robbers for a day; Sequester hides a thing from
  robbers, thieves and the watch for good (nothing ends it yet), or holds a body out of time (a century, here). Nondetection hides a
  mind from a foe's Detect Thoughts (no foe divines yet). Druidcraft's forecast is the world's own weather, so it comes
  true; Elementalism lights the fire, else dries the party (-25 wetness), else gives a cup of water; Prestidigitation
  takes 30 of the grime off and warms what is eaten in the next hour; Thaumaturgy is Advantage on Intimidation in the next talk.
  Glibness, Disguise Self and Seeming are never cast in a fight (no use there). New components: jade dust (25 GP: one
  pinch serves Magic Mouth's 10 GP), lead ink, a pinch of diamond dust (Nondetection's 25 GP); rare stones of 1,000
  and 5,000 GP now sold in cities (for Awaken and Sequester).
- Expansion 3 E.5: E.5 was split at its start (28 spells and Wish's other uses): locks and stone, weather and land are
  E.5; lasting protections, great magic and Wish's other uses are E.6. Knock works underground (a locked door or
  chest within 60 feet; the whole level is alerted) and in the cells (+10 on the escape check; the slot is spent);
  suppressing an Arcane Lock is left out. Arcane Lock locks a dungeon door beside you (open or closed) to everything
  but the party, who step through it to the square beyond; in a town it locks your room at that town's inn while you
  stay in the town (no inn thief). Mending mends the most worn thing by 25, up to 75 (a break, not the wear of years). Mage Hand is a
  thief's tool in a town: the next theft from a stall with Advantage; caught, the merchant cries witchcraft (-20,
  the magic seen) and no theft is done. Fabricate makes up to three batches of a camp craft at once, without tools,
  fire or a check (an artisan's craft needs someone trained in its tools). Creation makes gear of plant stuff (24
  hours) or stone (12 hours) only: metal, gems and coin are left out; it vanishes at its time, no merchant buys it.
  Stone Shape opens one square of wall for good; Passwall up to four for an hour, closing when a step on that level
  comes after the hour (whoever is inside is put out where it began). Move Earth is a camp ward: the night's visitors
  are seen climbing the bank (awake, and seeing them first). Leomund's Secret Chest takes the coin and the treasure
  (gems, art, ingots: trade goods with no use), the spare arms and armour, or both; never what is worn, food, drink,
  tools or anything magic; the exquisite chest goes too; things in it weigh nothing, cannot be worn, sold or used, and
  no robber, thief or watchman takes them; the replica calls it back (no slot); after 60 days each day has a 5%
  growing chance (5%, 10%...) that it is lost. Control Water is a lasting spell of ten minutes that parts the next river
  on the road (no flood, whirlpool or redirected flow; never cast in a fight). Control Weather: five choices (clear,
  rain or snow, calm, warm +10, cool -10) for 8 hours within two map tiles, at once (the book: a stage at a time).
  Plant Growth's Overgrowth costs 4 feet a foot (a new kind of ground) in a 100-foot sphere but within two squares of
  the caster's friends as it is cast; its Enrichment doubles the forage of that map tile for a year and is a deed
  (+3 with the owner, fame) in a hamlet, village or town. Tsunami is cast from the meeting screen only when the band
  was seen first: 6d10 bludgeoning to each (Strength save for half), a minute passes, then the fight begins with them
  knowing you; its later rounds are left out; a band drowned to the last is a fight won (XP and loot as ever).
- Expansion 3 E.6: E.6 was split at its start (13 spells and Wish's six other uses, four of them systems as big as a
  part): lasting protections, the Demiplane and Tasha's cauldron are E.6; Contingency, Magic Jar, Clone, Imprisonment
  and Wish's other uses are E.7. A protection is a camp ward (where the party rests, left behind when it moves on);
  Glyph of Warding and Symbol are drawn on the way into a camp in the open (not underground: nothing comes to a
  dungeon camp in the night) or on your room's door at an inn (the night's thief sets it off); they are always set
  off by the party's foes (chosen triggers, creature-type refinements and passwords are left out). A glyph's stored
  spell is a prepared spell of level 1 to 5, cast with an action at a foe or a point, without concentration; its own
  slot is spent as the glyph is drawn, and it takes effect at the first of the band as the fight begins (an area
  centred on it), with the numbers it had when stored. A symbol strikes the band once, before the fight (the ten
  minutes of the sphere are left out: the fight is beyond the glyph); Fear sends those who fail away for good;
  Discord is Disadvantage on attacks (on checks left out). Magic Circle and Forbiddance always take every kind they
  can (five and six); the reversed circle waits for binding spells (Part F). Guards and Wards: half the night's bands
  lose their way, the rest wake you; its doors, webs and other effects are not laid on any map. Private Sanctum: the
  night's chance is half a cold camp's, fire or no fire. Hallow keeps out aberrations, elementals, fey, fiends and
  undead (celestials welcome), on the whole map tile in the open, 60 feet underground; its blessings are Courage,
  Fear (every non-humanoid foe), Resistance (necrotic), Vulnerability (radiant) and Peaceful Rest (a haunted field's
  dead laid for good, a town's graves hallowed: each a deed); Daylight, Darkness, Silence, Tongues and
  Extradimensional Interference are left out. Demiplane: one room, the party's, never lost; a short rest there for
  the hour. Tasha's cauldron is cast outside a fight only and brews the common and uncommon potions the game has
  (healing, greater healing).
  A creature's saved `conditions` now come into a fight with it (a sleep brought in breaks on damage), the first
  use of that record.
- Expansion 3 E.7: Contingency's trigger is one of three moments, all in a fight (as it begins, below half the hit
  points, falling); the contingent spell is one the caster could cast now, cast with an action at themselves or a
  friend, and it takes effect on the caster alone; triggers outside a fight (being engulfed, a fall) are left out.
  Magic Jar works in a fight: the body lies still (Incapacitated, no movement), the soul sees from its gem, possesses
  a humanoid foe within 100 feet (a foe that saves is safe from it for the rest of that fight, not a day) and the
  player plays the host with its own hit points, attacks and speed (the caster's spells from a borrowed body are left
  out); at a fight's end the soul goes back to the gem and a host left standing runs; possession outside a fight is
  left out; outside one the caster casts nothing else until the soul goes home (Magic Jar again, no slot); the gem is
  taken as the spell is cast. Clone is cast in a town or city (the temple keeps the vessel), on someone of the party;
  the age is not chosen; the leader's clone wakes with nothing and the companions bring the gear at 24 miles a day; a
  clone of someone outside the party is left out. Imprisonment is cast from the meeting screen only, when a band is
  seen first, at its strongest; the form of the prison is the game's choice by the creature's kind; a success's day
  of immunity lasts only for that meeting; the ending trigger is left out. Wish outside a fight: Object Creation lists
  every non-magic thing of 100 to 25,000 GP in the game; Resistance and Spell Immunity are for the whole party (up to
  ten); Spell Immunity lists the spells this world's foes cast at you; Sudden Learning takes back the old feat's
  ability increases, skills, tools, training and hit points (what the class or background also gives stays) and a
  style is swapped only for a style; Reshape Reality is four wishes (an artifact: carried to where it lies; a beast of
  the songs or a dragon dead: half or a quarter of the time, else a beast comes down on the farms or the dragon wakes;
  the realm forgets your crimes; a fallen friend the party carries lives, at the death toll); copying a spell outside
  a fight is left out. Roll Redo undoes a foe's hit on a friend since the last round (rerolled with Disadvantage; a
  miss gives back its damage, a lost critical half); redoing a save is left out; the Auto never wishes but to copy. From the fresh review: Wish's stress makes Strength 5, as the book says
  (D.4 had 3); a body under Protection from Evil and Good cannot be taken; leaving a body needs the gem within 100 feet.
- Expansion 3 F.1: Part F was split in four at its start (F.1 allies, the familiar and the steed; F.2 the Summon
  spells' spirits, Giant Insect, Animate Objects; F.3 Animate Dead, Create Undead, Finger of Death's zombie, Planar
  Ally and Binding; F.4 shapes with the rest of Appendix B and the cult fanatic's imp or quasit). Each stat block
  comes with the spell that brings it into play. An ally is played by the player like a party member (z: the
  Auto); it never runs, earns no XP, its kills count for its owner, and it does not keep a lost fight going. The
  octopus waits for fights under water (Expansion 23: it breathes only water); a familiar's hit points are its
  form's average; seeing through its eyes and delivering touch spells are left out; a familiar sent away stays
  out of fights (calling it back is a road use, not an action in a fight). Find Steed's looks are horse, camel and
  dire wolf (the elk waits for its picture, F.4); it fights beside its rider until mounted combat (Expansion 10);
  its gift (once a long rest) and its hit points come back at a long rest; on the road it is its rider's mount at
  a warhorse's pace and eats nothing; with no paladin yet it comes from scrolls. Flyby and Agile are one rule: no
  opportunity attacks for the whole turn (Flyby only while it can fly).
Ideas for later:
- (none yet)
- Expansion 3 F.2: the Summon spells were split at the start (F.2 levels 2-4 with the summoning itself, F.3 levels
  5-6 and Animate Objects; the dead and the bound F.4, shapes F.5). The form (Air/Land/Water, mood, Ghostly...) is
  chosen by the game for the fight (`allies.best_form`, as Chromatic Orb picks its type), not by the player; a spirit
  never outlasts the fight; it uses the caster's real spell attack and DC (not a scroll's); Water Breathing,
  Amorphous Form and Incorporeal Passage are "not yet" traits; Berserk Lashing only strikes (no move toward); Tricksy
  darkness lasts until the spirit's next turn; the mind flayer's whispers hurt the caster's friends too (the book).
- Expansion 3 F.3: the Avenger or Defender, the dragon's resistance (and breath) and the Demon, Devil or Yugoloth are
  chosen by the game for the fight, as F.2's forms are (the dragon's: the type the foes resist least); the Defender's
  temporary hit points go to whoever near the target needs them most; Healing Touch is once each time the spirit is
  summoned; the yugoloth's teleport after its Claws is the game's choice (beside the next foe when its target fell,
  out of a crowd when bloodied), for the player's spirit too; Devil's Sight sees through magical darkness within its
  darkvision (fog and walls still hide). Animate Objects: the game picks the sizes (a Huge one against a single great
  foe, Large ones in pairs, a Medium one for the rest) and what they are follows the place (a chest, a table, a statue
  under a roof; a stone, a log, a boulder outside); they act only on their caster's Bonus Action command (else they
  Dodge), and a creature that casts it commands them as part of its own turn; damage carried over to the object at 0
  is not kept. A creature the player commands now makes its Multiattack's attacks (it made one before), and a breath
  it is given is aimed at the target. The 500 GP reliquary is a new "silver reliquary" (the 1,000 GP gilded one, Holy
  Aura's, serves too).
- Expansion 3 F.4: Part F was split again at its start (F.4 the dead; F.5 the bound: Planar Ally, Planar Binding,
  Magic Circle turned inward; F.6 shapes). The bodies Animate Dead and Create Undead raise are the fresh dead of the
  last fight where it was fought (six hours, as for Speak with Dead), the skeletons it destroyed and a crypt level's
  six piles of old bones; the party's own fallen are not raised (they are kept for a spell of return). A command is
  the battle's Bonus Action only (a general order such as guarding a place is left out). Twelve servants at most to a
  master. Unheld, the dead turn on the party out in the land (an encounter, seen coming) and wander off anywhere
  else; a dead master's go free at once. The dead never enter a settlement's close-up map (they wait outside) and do
  not heal. Create Undead's choice of ghouls, ghasts, wights or mummies is the player's (a choice above the slot
  falls back to ghouls, said in the log); the onyx stones are kept. The ghast's Stench and the mummy's Glare spare one
  who saves for the fight (the book: 24 hours). The mummy's rot outside a fight: hit points kept no higher than they
  were (checked as time passes), the maximum 3d6 lower each day, at 0 dust; Remove Curse lifts it (Greater
  Restoration does not yet). Dust: only True Resurrection (its "cures") reaches the body.
- Expansion 3 F.5: Planar Ally's god is the faith of the cleric's people (data/factions.json faiths `ally`: celestial
  for the gods of light and law, elemental for the old gods of land, sky and sea, fiend for the dark gods and cults;
  which form each sends was chosen by its god's nature); the terms are an hour, a day, three days or ten days at the
  book's 1,000 GP an hour and 10,000 a day (the 100 GP minute is never cheaper here), paid at once; "aligned with the
  creature's ethos" is the leader's membership of that god's church (half); the work is always to fight beside the
  party and keep it on the road (errands, naming a creature, refusals left out). Planar Binding reaches the party's
  captives of the four kinds (today only goblins, fey in 2025) and its Planar Ally spirits (in a Magic Circle turned
  inward, or one already bound); its orders are only to fight (a Hostile creature's twisting of them left out); a
  bound captive is no longer a captive (no bounty) and runs off when the binding ends. Spirits and the bound heal at
  a long rest (the dead still do not), wait outside towns as the dead do, and never turn on the party.
- Expansion 3 F.6: Part F split again at its start (F.6 Polymorph and True Polymorph; F.7 the rest of Appendix B's
  creatures; F.8 Animal Shapes and Shapechange). The game picks the form (the strongest for a friend, the weakest for
  a foe); the party's own are always willing; a shape ends with the fight (the book: an hour); True Polymorph's
  lasting form and its objects are left out; a shaped character can still use the Influence actions (anatomy is not
  checked for speech); while shaped, what the game keeps on a character alone (exhaustion's penalties, Heroic
  Inspiration, drink and pain) is set aside with it until the shape ends.
- Expansion 3 F.8: in a fight the game picks the strongest form (as F.6), on the road the player picks (the fliers
  first, then the swiftest, then the strongest); in a fight Animal Shapes takes every friend within 30 feet who casts
  no spells, never the caster (the game's "any number of willing creatures"), on the road the whole party (a caster
  can leave at once, no slot); harm outside a fight falls on the body itself, not the borrowed hit points; "a creature
  you have seen" is any creature of the game; the gear always melds in (none drops); Dispel Magic does not end Animal
  Shapes; a Shapechanger is offered no concentration spell in its form (it would end the shape); a shift takes the
  strongest other form, the druid's change the strongest again. The druid is not a class yet: Animal Shapes comes from
  a scroll or Wish until then.
  Only a thing used from the pack is refused in a shape: the party's tools in a dungeon (a pole, a ram) and at camp
  still serve a shaped party, someone being taken to hold them (adapted). A lame leg does not slow a beast.
- Expansion 3 F.7: the stat blocks are the 2025 Monster Manual's (the PHB's Appendix B prints the same creatures).
  The octopus, giant seahorse and reef shark breathe only water: a foe's Polymorph shape but never a friend's, and
  not met until fights go under water (Expansion 23); the crocodile's Hold Breath waits with them. Where they are
  met was chosen by their habitats and the world's biomes (lions and elephants on the savanna, tigers and apes in
  the jungle, sprites in the fey forest, the sphinx of wonder in the desert...); the cult fanatic's imp or quasit is
  a cult circle with one of them; slaad tadpoles hatch in the wizards' towers until the planes come (Expansion 27).
  Shape-Shift (imp, quasit), Heart Sight (sprite) and shaking a sleeper awake (the pseudodragon's Sting) are left
  out; Burst of Ingenuity is the battle's judgement (spent when the 2 turns a failed save or a check made in a
  fight). A stat block's condition with no ending in its text lasts as the book means: a grapple until it is broken
  (the bugbear's grab too, which before ended at the victim's next turn), Restrained with it, a sleep until damage,
  a fear until saved, the pseudodragon's poison the whole fight (`rounds` in the op). Melee-only Nimble Escape
  (panther, tiger) is used when hurt or crowded. The quasit opens with its
  Scare and the pseudodragon with its Sting. The goat's Strength save is +2 as printed. Pictures: the Crawl pack's
  where it has the animal (some recoloured), the rest drawn.
- Expansion 3 G.1: a creature's Shapechange takes forms up to its Challenge Rating (the book: "your level"); Aid on a
  creature raises its own record's maximum (kept in `creature.uses["spell_hp:aid"]`, never twice by one spell); Mage
  Armor works on a creature whose stat block's gear has no armour; True Strike and smites use a creature's blows with
  a weapon its stat block names (`attack["item"]`), never claws; Revivify brings back a creature friend (not a
  summoned one, which vanished). The arena's test caster is a war mage (CR 9, DC 17, +9, Intelligence 18, AC 12, a
  dagger, a 17th-level caster's slots). The plan's turn budget (150 ms at the 95th percentile) is held for casters
  with a stat block's list (16-24 spells); a caster holding every spell of a level (35-72 spells) is held to "never
  400 ms" (its 95th percentile is about 100-200 ms).
- Expansion 3 G.2: a hamlet's priest is a village's (the book lists village, town or city); level 9 is in every city (the
  book: "City only"), and each caster's own reach is a roll within the place's range (village 1-2, town 3-5, city 5-9;
  a figure reaches the limit); the component's value is added whether or not the spell consumes it (the book: "add the
  cost of those components"); a lasting spell is for hire if it lasts an hour or more and is cast on someone else;
  spells needing the caster to stay (familiars, summons, shapes, camp wards, travel, great magic) and the "sense",
  "scout", "speak", "mind", "illusion", "art", "lock", "make", "stone" uses are not for hire; Contact Other Plane and
  Dream are (the mage bears the risk). The priest's "Ask what a strange thing is" and "Have a curse lifted" stay
  (Identify is left off the priest's list for hire, to avoid two lines for one thing) at the book's price for Identify
  (with its 100 GP pearl: 150 GP) and Remove Curse (300 GP). A companion's body is now carried (up to ten days, as
  before) while a priest of this world's places could raise it (any revive spell of a day's reach or more of a level
  some place reaches): in a world with a town or city that is always. The mage's fighting numbers are the acolyte's
  until the book's Mage comes with its expansion. Magic items for sale moved from a city's apothecary and general store
  to its mages. Where magic is forbidden: no open sale of scrolls or magic things but the temple's (cleric) scrolls; a
  mage casts for pay only with no other witness in sight, at x1.5. Towns visited before G.2 keep their people (no
  mages there); no save format change.
Next session starts at: Expansion 6, **Adventures & Events**, Part B, task B.6 (*eavesdropping, tailing and
tracks*), on branch `dlc/06-adventures-events` (B.1-B.5 done there, not yet merged; Part B goes to main with B.9).
Read docs/expansions/06-adventures-events.md Part B (B.6-B.9) and ADVENTURES.md §5.18 (its last paragraph), §8.11
(eavesdropping), §8.14 (fire), §8.16, §8.17-8.18 first.
Part B's first half (2026-10-24, realmwalker-a): B.1 the stage `game/story/stage.py` + scenes.json (one scene at a
time in politics["director"]["scene"]; cues are a registry `@cue`, checked at start-up by story/check.scene_problems;
townlife.tick calls stage.tick first, townlife.settle plays it out; errands in npc.flags["errand"] read first by
townlife.goal, runners two steps a tick; gatherings Town.flags["gathering"]; townlife.speak; GameState.held, animations,
stage_fx, camera, letter (none saved); Conversation.greet's opener; stage.on_load from save.load_game, stage.check_here
from the game screen; story.offer_hook plays "runner" or "plea" when you stand on the town's map). B.2 pictures
`ui/gfx/vignette.py` (BACKDROPS, compose, for_place), beat.picture/backdrop_for ("place", "here", a backdrop),
travel_events.json `picture`, ui/screens/titlecard.py, letters `game/letters.py` + ui/screens/letter.py (typefaces
hand/hand_fine/hand_dark; item tag letter:<id>; the pack's "Read the page"), stage cues give `letter` and read, npc
flags "holding" (fig/held/letter), the battle events "boss"/"phase" with name and line (battlefx banner, the villain
sound). B.3 `world/marks.py` + marks.json (add/lift/age/since/label/words; Politics.expire_status is marks.age; OWNED
marks: siege, emptied, rebuilding). B.4 `game/placemarks.py` (stamp from enter_local, prepare_town and the day's
politics; lm.meta["marks"]; economy.burnt_out shuts shops and services; roofs/houses "charred"). B.5
`game/remains.py` (Field.cut_from set by arena._local; Battle.__dict__["blood"] filled in Battle._hit; after_field
from fight.finish_battle; tick from enter_local and the day change; lm.meta bodies/decals/graves; LocalView _decals and
_fallen; DCSS blood picked as decal/blood and decal/pool). tools/showcase.py sheets vignettes, letter, mark.
Still to do in B: B.6 (overhear/follow scenes, track decals to the map's edge and the world map), B.7 fire, B.8 map
signs, B.9 (the Beast shown: its scenes incl. the camp screen's, title cards, its doom as a mark, vignettes on
epilogue pages; showcase first form exists; debug console showcase/mark/scene; frame timing test; FORMAT_VERSION +1 for
Part B's new saved records; smoke tour shows a burned town, a title card and a letter; merge).
Part A's second half (2026-10-24, realmwalker-b): `tools/storybook.py` (synopses; `--check`: roles, places, every
word of every line a tale can show, three routes, the content rule, the six rules as they apply to a tale;
tests/test_storybook.py on three test worlds) and the story's floors in tests/test_text_variety.py; the powers
answer a tale (`story.divine_questions`/`divined` through Divination, Commune, Contact Other Plane); a hunting job on
a threat's beast opens its hook (`story.on_job_taken`); a choose step's beat is offered when what comes before it is
done (`story._offer_choice`: road, camp, arrival) and a named foe whose fight was lost comes at night
(`story._due_slay`); the arena fights every weakness creature as the Beast's boss (tests/test_tactics_coverage.py);
map marks `map/story` and `map/sign` (`story.map_signs`, worldview), the beat's `camp_night` picture, the title
card's band and seal, sounds chapter/reveal/sign; `tools/storyplay.py` (20 of 20 Beasts finished; tests/
test_storyplay.py, slow) and the first-hour hook test. Storyplay found: the beast fought its finale's template at
the bait (now villains.json boss `before`: it fights as itself and bolts at half, phase `breaks_off`; at the den
`morale` fanatic); threats are tiered by their beast's challenge too (`threats.tier_for_villain`); a beast left
helpless at a fight's end is killed where it lies (`story.finish_off` from fight.finish_battle). Story XP is Part C's
(storyplay's party gains no levels from the tale itself). `story.on_legends_page` was left for a later part.
The way of Part A: the story is `realmwalker/game/story/` (its `__init__` is the one door: every hook the game calls)
and `world/threats.py`. Records: politics["threats"|"adventures"|"director"|"story_sites"|"story_people"]; Renown.legend;
Creature.story {adv, role} (past.on_battle skips story creatures; dungeon.populate puts a tale's band first through
story.boss_for). A beat waits in politics["director"]["pending"], a chapter card in ["card"]; game.finale and
game.epilogue are the other two story screens; GameState.busy includes them (story_waiting). Tests outside those marked
`@pytest.mark.story` never get a hook offered (tests/conftest.py _quiet_tales), because older tests walk through towns.
Step kinds finish by their beat when `beat_finishes` (go, search, choose), else by the beat's own ["step_done"] op
(learn's check route). Bosses: villains.json templates applied by story/finale.make_boss in finale.prepare (from
fight.start_battle); the frenzy phase is rules/engine/handlers/bosses.py (from Battle._hit).
The way of Part E (robes, hats and the rest): book makers written by `tools/codex/wizard_wonders.py` into
data/treasure.json (and its "patches" table); a maker's `enspell` may be a list of schools (Enspelled Armor and
Weapon). Properties: `charges` with `worn` (and a `pool` with `worn`: only while worn or held, `magic.charges`),
`stored` (a ring's spell: its `level`, `dc`, `attack`, `mod`; gone once cast, `magic.unstore`), `sense` (darkvision,
truesight: `magic.sense`, read by Sheet.darkvision and Fighter.senses), `base_ac` (Sheet.armor_class unarmoured),
`spell_dc` (spells.save_dc), `focus` {for} and the ruby's `war_ruby` + `item.magic["set_on"]` (`magic.item_focus`, read
by spells.has_focus and focus_bonus), `hat` (rules/hats.py), `store`, `patches`. The hats: cast ids
"hat:<uid>:<spell>" (`Battle.hat_options`/`_hat_problem`/`_cast_from_hat`, the Auto's short list in
actions.options, `hats.odds` in tactics; the battle screen's "hatmenu:<uid>" row and `_open_hat`; on the road
`game/magic.cast_from_hat` and the Spells page's "Out of the hat"); `hats.rest` from progression's rests. The
pack's things outside a fight are game/wonders.py (`use_name`/`use`, `choices`/`choose` behind the pack's
ContextMenu; the ring's `store`, the Spells page's r). Battle powers in rules/engine/handlers/wonders.py (the pearl,
the Astral step `send_away("astral")` back at the turn's start, the Robe of Eyes' `after_light` from Battle.cast);
the item spell robe_colors; `tactics._wondrous`. Scrying through a ball: `game.__dict__["item_dc"]` while an item's
spell is cast on the road, `wonders.scry_extras`. tests/test_wizard_wonders*.py.
The way of Part D (wands, staffs and rods): book makers written by `tools/codex/wands_staffs_rods.py` into
data/treasure.json (`attune_by`, `enspell` with the top-level "enspell" table [DC, attack] by level). One store of
charges a thing: prop `pool` {value, left, regain, last crumble|vanish|display|mundane|weaken, lucky}; its spells are
`charges` props with a `cost` (0: at will), `level`, `more`, `dc`, `attack` (`rules/magic.pool`, `pooled`,
`charge_cost`, `charge_levels`, `spend_charge(prop, rng, item, level)`, `charges_left(prop, item)`, `drained`); in a
fight "charge:<uid>:<spell>" with `slot_level` as the level the charges buy (`Battle._do_cast`; the battle screen's
`_ask_charges`, `charge_words`; `tactics.charge_of`/`charge_price` and `_slot_levels`; `estimates.spell_value` reads
the item's DC); outside one `game/magic.cast_on_road(charge=(item, prop))` -> `_cast_from_item` and `item_spells`
(the Spells page lists them after a "Wands, staffs, rods" heading; `care.cast(free=True, slot_level=)` heals at the
level bought). Powers: `rules/engine/handlers/staves.py` (staff_of_striking, staff_of_charming + resist_enchantment and
`after_cast`, `absorbed` from `Battle.cast`, `rod_draw` and `tactics._rod_slots`, `retributive_strike`/`retribution`);
item spells wand_enemy_detection (mark `sense_foes`, `Battle.can_see`), wand_fear, wand_paralysis, rod_aura,
rod_rulership; props `spell_attack` (`spells.attack_bonus`) and flag `spell_cover` (`Battle.target_ac`); flag
`fireworks` (`gear.fireworks`, the camp evening). `effects.cast` keeps `b._casting_sid`. tests/test_wands_staffs_rods.py.
The way of Part C (mages and priests): the five 2025 blocks in data/statblocks.json with creatures in
data/creatures.json. Stat block keys added: spellcasting `levels` {spell: level} ("Fireball (level 4 version)", read
in `Battle.creature_cast`), `before` (spells already in the block: Mage Armor, Mind Blank; left out of `spells`); a
reaction that casts with `uses` is a shared pool like Divine Aid (Protective Magic: Counterspell or Shield); a bonus
action that casts puts its spells in spellcasting `bonus` (`combat.cast_kind(f, spell, sid)` makes them bonus
actions); an area save action's `enemies` (Holy Word); a recharge number other than 5 (`Battle._recharge_on`). Shield
for creatures in `Battle._shield`. `Creature.culture` (saved only when set) dresses a creature whose figure says
`dress` (["mage"], ["priest"]) as that trade among its people (`dolls.creature(culture=)`; cultures' `mage`/`priest`
dress in data/sprites.json); `encounters._folk_here` gives road bands the land's people; a townsperson in a fight is
drawn by `dolls.npc` (battlefx `_townsperson`). Towers: `world/dungeon.tower_master` (the history's living wizard or a
mages' circle), `DungeonBuilder.lived_in`/`library` (glyph traps `WARDS`, `MASTER_DC`, warded locks, bookcases with a
feature "library"), `lm.meta["master"]`; `game/dungeon.MASTERS`, `search_library` (bump on the bookcase), groups
tower_mage/tower_archmage/tower_apprentices/tower_familiars; `past.tower_master_slain`. People: priest stats "priest",
mage stats "mage", `people.figure_stats` for the history's heads; a great city's first temple and mage. Quests:
template "apprenticeship" (`quests._apprenticeship`, `lesson`, `FETCHED`). Tactics: `estimates._escape_unseen`
(Invisibility for the hurt), `_out_of_reach` (Fly above melee-only foes), `tactics._read_minds` (sense_thoughts
instead of a blind search), no grapple by a ranged fighter. tests/test_mages_priests.py.
The way of Part B (the domains and the gods): `rules/engine/handlers/domains.py` (Warding Flare from `Battle._attack`
after the Protection style; Radiance of the Dawn a "power" ability valued by `estimates._radiance_of_the_dawn`; the
corona a buff `corona` read by `query.save_roll` through `domains.corona_against`, with `Battle._dawn` during the
Dawn and `Battle._casting_spell` set by `effects.cast`; the blessing the mark `kept:trickster_blessing`, read by
`Battle.do_hide`, `GameState` sneaking and `fight.encounter_evade`, laid by `domains.bless_after_rest` from
`fight.rest`; the double a Token kind "duplicity": `Battle.spell_targets`/`spell_points` add what it reaches,
`do_cast` wraps `_do_cast` in `domains.standing_in` when `cast_from_double` says so, `query.attack_roll` asks
`domains.distracted`, `double_ends`/`check_doubles` from the turn start). Aims "double_new", "double_move",
"trickster_blessable" in `actions.aim_targets`; tactics `_domain_bonus`, `_corona`. The gods: data/factions.json
faiths `domains`, `progression.faith_domain` (the default domain), `game/gods.py` (`chance`, `prayers` set on
`Battle.prayers` by `fight.start_battle`, `after_battle` from `finish_battle`: history kind "miracle",
`renown.flags["god_answered"]`), `rules/miracles.answer` from `Battle._kill`. Events flare, miracle, double_cast
(board and sounds). tests/test_domains.py.
The way of Part A (the two schools): `rules/engine/handlers/schools.py` (Portent through the kernel's "d20_before"
event, `Battle.foretold`; `party_foretell` outside fights; Expert Divination's `slot_back`; the Third Eye in
`char.spells["third_eye"]`; Illusory Self in `Battle._attack` before Shield; Phantasmal Creatures as
`spells.free_cast` "phantasm" with `bond["spectral"]`; Illusory Reality's `realisable`/`unreal`). Images are Zone kind
"illusion" (`seen`, `real`, `slotted`): `Battle.view(f)` gives each viewer a field without the images it knows
(`grid.Field.without`), `Battle.do_search` studies them, `_zones_on` sees through on entering; the Auto's worth is
`estimates.image_worth` (lines worked out once a turn). tests/test_schools.py.
The way of Part D (the magic arms): book makers in data/treasure.json with kernel traits in
`rules/engine/handlers/arms.py` (CLAUDE.md "The magic arms"); tests/test_magic_arms.py.
The way of Part C (poisons and the people of the shadows): a poison is an item with a `poison` record (schema POISON:
kind, dc, damage/half/sure, hours/hours_dice/ends, with/wakes/fail_by, repeat, fumes, slow, midnight, daily, truth,
from); `rules/poisons.py` (`record`, `of_item` with tags "dc:<n>" and "venom:<creature>", `battle_ops` the kernel's
ops, `coat` after "coat_poison", `blade`/`on_hit` from `Battle._attack` (buff `poisoned_blade` = item id, `poison_dc`,
`venom`; BLADES: the Dagger of Venom's own), `turn_start` (buff `fumes`, the effects op "fumes"), `suffer` outside a
fight, masked potions: tag "secretly:<id>" (`mask`/`masked`/`unmask`, care.drink_potion, Battle.do_item,
divining._sense_poison, treasure maker `secretly`); the save op's `against` and `fail_by`; trait modifier `immune`
(damage immunity: query.defences). Inhaled vials are spells "poison_<id>" in spells.json (= battle_ops of the record,
tested). `game/poisoning.py` harvests venom (Aftermath.venomous, V). `game/shadows.py`: poison law (law.json
`shadows`, `law.contraband_for`, `shop_sells` in economy.restock), the black market (shop kind "black_market" via
npc.flags), `guild_work` (quests.make_offer), cups (`slip`, `tell_truth`, `die_of_poison`), duels (`challenge` from a
failed threat, `accept`/`refuse`, `duel_settled` from fight._settle_townsfolk, renown.flags["duel"]); politics
`spy_caught` (rates/text in politics.json). Creature Cunning Action: `tactics._cunning_first` and `_slip_away`; a
creature's area action with `range` and a sphere bursts at a point (`Battle.area_cells`). Camp crafts may say `feat`,
`coin`, `by_proficiency` (the Poisoner's brew; `camp.maker`, `brew_dc`).
The way of Part B (the Eldritch Knight, the Arcane Trickster): a subclass may carry its own `spellcasting` (schema
SPELLCASTING: `list` "wizard", `focus`, `changes` "level", `given` cantrips); `spells.casting(char)` is the one door
(also `spell_list`, `focus_kind`); `progression.start_casting` (when the path is chosen) and `cantrips_due`. War
Magic is `Battle.war_magic` + `_spend_attacks` (the casting-time test refuses other casting mid-Attack-action;
`tactics._pick_cast_now` lowers the bar to the attacks it replaces). `rules/war_bond.py` (bonds in
`char.spells["war_bond"]`, `at_rest`, `holds`, `away`, `call`, `taken` from the robbery). `engine/handlers/arcane.py`:
eldritch_strike (buff `eldritch_struck`, read in `query.save_roll` with `b._casting`, spent by `effects.cast`),
`ambush_ready` (`ambush_turn` noted in `do_cast`), arcane_charge (on `ability_used`), the unseen hand (Token kind
"mage_hand", ability `unseen_hand`, `trip_beside_hand` from rogue.py), `spell_thief` (from `effects.cast`, joins
`shut`; `char.spells["stolen"]` in `known_spells` until `long_rest`; the caster's `stolen` set in `creature_spells`).
`game/legerdemain.py` (`trickster`) is read by `law.steal_from_shop` and `law_talk.pickpocket`. Tactics:
`_arcane_bonus`. Picture `fx/unseen_hand_glow` (tile_art.spectral_hand); event "rearm" (board words, sound).
The way of Part A (the Battle Master): `rules/engine/handlers/battle_master.py` (superiority pool `uses["superiority"]`,
`sides`, `roll_die` with Relentless, `dc_of`, `ready`; `maneuver_blow`/`maneuver_after` on a hit, `precision_attack`,
`bm_parry`, `riposte`, the buff `maneuver_die` in events.BUFF_HOOKS; specials for the abilities; `ambush_initiative`
from `Battle.start`, `check_die` from `camp.check`, `Battle.check`, `dialogue.check`). The maneuvers are fighter
`options` in classes.json kept as features ("maneuver_<slug>", each a kernel trait); a feature's `choose_count`
adds that many "option" choices and `gives.feat` takes a feat (Student of War, offered: false);
`progression.option_feature` finds a subclass feature's list; `MANEUVER_ORDER`/`SUBCLASS_FOR` for Suggest. Aims
"friend" and "unknown" with a range in `actions.aim_targets`; buffs goaded, exposed, disarmed (attack options),
maneuver_die; tactics `maneuver`, `_maneuvers_first`, `_maneuvers_after`. Cards reuse icons (sapped, marked, guided,
shielded) with their own titles.
The way of G.3 (Simulacrum): `rules/simulacrum.py` (the person's copy: `make`, `keep`, `destroy`, `repair` from
`progression.long_rest`, `bring_in` from `fight.start_battle` after the shapes, `after` from `finish_battle`, `snow(f)`,
`likeness` for the map); a creature's copy is a servant record with spell "simulacrum" and `type` "construct"
(`servants.bring_in(only=)` lets it into settlement fights, `servants.following` onto settlement maps).
`Battle.add_ally(char=)` makes a character fighter with a bond (party side, `kind` from the bond's type); `_heal`
refuses snow, `_apply_hp_loss` melts it at 0 (no death saves), `_kill` has its words, `result().party_dead` leaves out
bonded fighters; fight.py's party loops skip `f.bond is not None`. Road op `does: "simulacrum"` in
`game/greatmagic.py` (`simulacrum_subjects`, `_simulacrum`). Pictures: `dolls.frost(parts)` (battlefx `_figure`,
localview followers).
The way of Part G (G.2): `game/spellhire.py` (TRADITION priest->cleric, mage->wizard; `reach` by economy.json
services "spellcasting" `reach`/`own`, figures at the cap; `caster` builds the townsperson with `companions.build` at
`caster_level`, cached per session; `price` = table + `component_value`, x`secret_markup` where forbidden; `offers` /
`targets` / `options` / `cast`; FOR_HIRE uses; `could_raise` for revival.could_raise). `magic.road_problem/cast_on_road(
hired=True)` (no slot, material, strain or ritual time; identify takes the Item as target); `law.magic_check` ignores a
caster outside the party; `law.party_casts`; mages placed by `people.populate_town` (`magic.mages_here`), FIGURE_JOBS
"mages_circle"; shop "mage" (economy.json); `magic.scroll_stock(tradition=, top=, lo=, hi=)` by rarity
(SCROLL_WEIGHT), `magic.magic_forbidden`; services screen cursor/scroll (`ServicesScreen.cur/top/shown/tip`).
The way of Part G (G.1): `tools/arena.py` `battle_spells` (every spell cast on one's own turn in a fight), `caster_def`
/ `caster_setup(..., second=)` (the war mage, an escort beside it), `--spells`, `--spell x`, `--shard k/n`; the arena
plays a creature the party called in mid-fight on Auto. tests/test_enemy_casters.py: NOT_CAST (a reason each; "a
scene" ones are cast in SCENES), the per-level casters and the stat-block-sized ones. Kernel: `estimates.casts_spells`
(a party caster counts), `weapon_blows`/`blow_mod` (True Strike, smites), `RESTORED` (the restore op's worth), the
revive op's worth; `estimates.thinking()` (a memo of save chances, damage factors, summons and spell areas while one
choice is weighed: `tactics._pick_cast`); `tactics._touch_heal` walks to heal, restore or revive; `_creature_magic`
reuses the action's spell when no bonus spell was cast; `Battle._form_spells_of` (a creature's Shapechange keeps its
spells; `unshape` writes the slots back); `shapes.mind_kept(block=)`; `query.wears_armour`; `engine/check` refuses a
stat block naming an unknown spell.
Parts E and F and G.1 are in `main`.
The way of Part F (F.8): Animal Shapes and Shapechange are the effects op "shape" with `cr`, `size`, `not`, `keeps`
("mind", "proficiencies", "spells"), `leave`, `shift` ("self"/"caster") and `hours`; `rules/shapes.forms(..., size=,
never=)`, `best(tables, f, kinds, o, other=)`, `cap`, `limits`, `mind_kept`; `challenge` reads what a shaped fighter is
underneath. `Battle.shape(f, cid, by=, spell=, how=, temp=, until=)` stores `conc` (only a concentration shape ends
with `_end_concentration`), `leave`, `shift`, `hours`, `how`; a shape keeping "spells" gets `_form_spells` (the
character's battle spells without concentration ones, its DC, attack and cantrip multiplier in the form's
`spellcasting`, its slots as `f.slots`; `unshape` spends what was used on the character). `shape_abilities`
(leave_shape: bonus; shift_shape, reshape: action) come before `class_abilities`' character check; `shift` re-shapes
keeping the concentration and the record's hour. A lasting shape is `char.spells["shape"]` {form, spell, until,
temp, caster, conc} (`shapes.record/on_road/keep/drop`): written by `Battle.shape`, kept by `unshape_all` (the fight's
end) with the temporary hit points left, dropped by any other `unshape`; `Battle.bring_shapes` (from
`fight.start_battle`, after the servants) shapes the party at a fight's start. The willing for Animal Shapes in a fight
is `effects.willing` (friends that cast no spells, never the caster). On the road: game/shapeshift.py through
spellwork's door SHAPES (`subjects`, `problem`, `cast`, `free_use` from `magic.cast_on_road`; `road_problem` lets the
free Subjects past the slot and the preparing), `tick` from spellwork.tick, `form_of`/`party_forms`/`all_shaped`
(`GameState.pace` uses the form's speed; `magic_crossing` "fly" over everything, "swim" over rivers and lakes),
`no_hands` (gear.use_item), `words` (the sheet, the Spells page); `spells.can_cast` refuses while in a shape that
does not keep the spells; `dolls.character` draws a shaped character as its creature. Tactics: `_shift_shapes` at the
start of `take_turn`. The jade circlet is items.json `jade_circlet` (city shops). Tests: tests/test_shapes_lasting.py.
The way of Part F (F.7): the 24 creatures are pack fragments, `statblocks.beasts.json` and `creatures.beasts.json`
(flavour, encounters and the towers' inhabitants: a pack may now `{"_append": [...]}` to a list entry of a
section). The kernel learned: a stat block's bonus action that is a blow or a save (`bonus_action` attacks from
`statblocks.resolve`; `Battle.attack_problem`/`do_attack` spend the bonus action; the action list's cost "bonus";
`tactics._bonus_blow` after the Attack), `requires` and an action's `max_size` (`Battle.unfit_target`, also in
`targets_for`), `advantage_if` (`query.ADVANTAGE_IF`), a condition `with` another (Restrained while Grappled: ended
by `durations.remove` of the grapple, every grapple release now goes through it), `ends: "damage"` (on_damage),
`fail_by` (`Battle._save` keeps `failed_by`), Running Leap (`Fighter.jump`), Burst of Ingenuity
(handlers/monsters.py on d20_after), `spellcasting.self_only` (`Battle.spell_targets`), `shapes.breathes_only_water`
(never a friend's form). Tactics: `_opening` reads a failed save's conditions; a repeat-save hold is worth its
expected rounds. Pictures: tools/beast_art.py (`_big_cat`, `_goat`, `_badger`...), build_tiles' `recolor` has a
saturation `floor`. Tests: tests/test_beasts.py.
The way of Part F (F.6): a shape is `Battle.shape(f, cid, by=, spell=)`: `Fighter.shape` keeps {char, creature,
cdef, sq, slots, recharge, by, spell, temp} and the fighter becomes a `Creature` of the form (uid 94000 + id, named
"X, as a rat") with its own hit points and the form's as temporary ones; `f.char` is None while shaped, so every
`if f.char` branch reads the form. `Battle.unshape` (from `_apply_hp_loss` when the temporary hit points are gone,
`_end_concentration` for the caster's shapes, `_kill`, the outcome in `_check_end` and `result()`) writes the hit
points back. rules/shapes.py: `forms` (any creature but NOT_FORMS, summoned or unique ones), `best`/`worst` by
`strength`, `challenge` (a character's level). The effects op "shape" {"forms": [...] | "any"}; the spell target
kind "creature" (friend or foe: `Battle.spell_targets`); `estimates._shape_worth`; battlefx's "shape"/"unshape"
events redraw the figure. Tests: tests/test_shapes.py.
The way of Part F (F.5): the bound are F.4's servant records with `form`, `level`, `picture`, `heals` (whole at a
long rest: `rules/servants.rest` from progression.long_rest) and `bound`; `rules/servants.spirit_def` gives a spirit
its numbers in each fight (`allies.summon_def` with its master's spell attack and DC) and `is_undead` tells the dead
from the rest (warnings, `game/servants._leave`: the dead go free, the others `_go_home`). game/servants.py's road op
"bind" (how "ally"/"binding", spellwork.SERVANTS): `ally_kind` (the faith's `ally`), `ally_price` (`church_member`),
`TERMS`, `binding_subjects` (captives by `bindable_captives`, spirits by `bound_rows`), `BINDING_DAYS`, `_cha_save`
(Magic Resistance). Magic Circle's Subjects outward/inward (game/warding.py; `inward_circle` reads
`renown.flags["inward_circle"]` {until, by, x, y, map}). Tests: tests/test_bound.py.
The way of Part F (F.4): a servant is a record in `char.spells["servants"]` {id, cid, name, hp, max_hp, spell, word,
reach, until, made, warned} (rules/servants.py: add, hold, due, soon, bring_in from fight.start_battle when
game/servants.here, after from finish_battle); in a fight bond kind "servant" with `word` (waits for
`Battle.command_objects`, now also "Command the dead" and "Command your servants": `commanded_of`, `within_word`,
`_needs_word`, `_waits_for_word`), `reach`, `rid`, and `keep` for a zombie risen in the fight (the effects op "rise":
`Battle.mark_rising`, `_rise_as_zombies` at its caster's turn start). game/servants.py: the road op "raise" (how
"dead"/"ghouls", `spells.F4_KINDS`; spellwork.SERVANTS), the bodies (`corpses`, `bones`), `tick` from pass_time
(warning, `_go_free`: the encounter "raised_dead"), `died`, `following` (localview draws them), the mummy's rot
(`_rot_day`, `lift_rot`). Marks kept until lifted are "kept:" effects (rules/health leaves them alone):
`servants.ROT`, `ROT_HP`, `ROT_LOST`, `ROT_DAYS`, `DUST` (revival.problem). Kernel: handler "stench", special
"mummy_rot", an attack's `spares` (Battle._save_action) and `dust` (`Battle._turn_to_dust`). Tests: tests/test_servants.py.
The way of Part F (F.3): a summoned creature's form may say `attack_types` {attack: type} (a draconic spirit's
breath), `shared` (a resistance its caster gets while the spell holds: a buff with `conc`), `ac` (+2 for the Defender)
and its record `per_day` (a creature spell once a summoning: Healing Touch); an attack with `with_multiattack` is part
of the Attack action (`Battle.area_attack`, `struck_this_turn`; tactics `_breath_with_blows`); kernel `special`
"defender_ward", traits magic_resistance, death_throes (the new "dismissed" event from `Battle.dismiss`),
devils_sight (`Battle._devils_sight`), yugoloth_step. Animate Objects: the creature's `summon` has `sizes` in place of
`forms` (`allies.object_sizes`, `object_def`, `animate_objects`; the "ally" op's kind "objects"); bond kind
"objects" waits for `Battle.command_objects` (the caster's "command_objects" ability, a Bonus Action; the Auto's
`tactics._command_objects`). Tests: tests/test_summons_high.py.
The way of Part F (F.2): a summoned creature has a `summon` record in creatures.allies.json (the spell's `level`, `ac`
and `hp` at it, `hp_up` a level, `forms` {form: name, picture, hp, ac, speeds, traits, attacks, damage_type, resist,
immune, spells, likes, weight}); its stat block's attacks marked `plus_level` add the slot level; `allies.summon_def`
makes its numbers for the slot and the caster (the caster's spell attack and DC; Multiattack = half the level),
`allies.summon_spirit` puts it on the field (the "ally" op, kind "summon"; `bond` kind "summon", `conc` True, form,
picture), `Battle._end_concentration` dismisses it (`Battle.dismiss`). Its traits are hooks in
engine/handlers/summons.py; a stat block's `on_hit` may carry kernel ops ({"op": "kernel", "ops": [...]}); the
`if_condition` op. The Auto's worth: `estimates._summon_worth`. Tests: tests/test_summons.py.
The way of Part F (F.1): a creature fighting for the party is a Fighter on the party's side with `bond` {owner,
kind, spell, level, type, picture} made by `Battle.add_ally` (beside its owner; a familiar by its own Initiative,
anything else right after its owner); rules/allies.py keeps the records on the owner (`char.spells["familiar"]`,
`["steed"]`), brings them into a fight (`bring_in`, from fight.start_battle), writes them back (`after`) and heals
them at a long rest; the "ally" effects op summons in a fight (`allies.summon`); a creature's numbers for its slot
are a copy of its definition set on `Fighter.cdef` (`allies.steed_def`); a creature-only gift is a spell with
classes ["creature"] in its `spellcasting.per_day` (no scroll, no Wish copy). `Fighter.blows` False: no attacks
(a familiar); the Auto's `tactics._familiar_turn` Helps. Outside a fight game/allies.py goes through spellwork's
door (ALLIES); the steed is a herd animal with `summoned` (economy.json animals `summoned`: never sold, fed,
stabled, stolen or awakened; `allies.put_in_herd` keeps the herd in step from pass_time). Tests: tests/test_allies.py.
The way of Part E: a spell outside a fight has `road_only` (or `minutes`) and an op {"op": "road", "does": ...}
(rules/spells.ROAD_USES and the kinds in E3_KINDS to E6_KINDS, checked at start-up), done in a module of its own
through game/spellwork.py's door (subjects, problem, cast); game/magic.cast_on_road spends the slot and passes the
casting time. A spell aimed at something chosen lists Subjects (game/divining.Subject). The arena's coverage test
(tests/test_tactics_coverage.py) must stay green with the new creatures.

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
| 2026-10-17 | Demigods & Magics part C: preparing spells, rituals, one slot a turn, higher slots, components (focus, pouch, costly ones), spell scrolls of every level (2024), the four potions of healing; the spellcasting rules settled in the codex; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics D.1: the catalogue's first wave, 79 battle spells (cantrips to level 2) with new ground, marks and cards; outside-a-fight spells to Part E, summons to F; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics D.2: the second wave, 66 battle spells of levels 3 to 5 (creatures sent away, Dispel Magic and Spell Breaker, auras for friends, Haste, Slow, Confusion, Dominate, new ground and walls); merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics D.4: the fourth wave, 19 battle spells of levels 8 and 9 and Wish (copies, Instant Health and its stress), Meteor Swarm, Time Stop, Storm of Vengeance, the Prismatic Wall, Earthquake, Maze, the words of power; Part D merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics E.1: spells outside battle - return from death (bodies carried, Raise Dead to True Resurrection, Gentle Repose, a fallen leader called back), Aid, Regenerate, Remove Curse, food and water, wards on the camp; companions cast them on their own; saves format 18; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics D.3: the third wave, 27 battle spells of levels 6 and 7 (Chain Lightning, Disintegrate, Heal, Harm, Flesh to Stone, the Globe, Otto's dance, walls of ice, thorns and blades, Divine Word, Prismatic Spray, Reverse Gravity, the Forcecage...); merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics E.2: light, the body on the move and travel by magic (34 spells: Teleport by its table, Teleportation Circle, Word of Recall, Wind Walk, Water Walk, Etherealness, Feather Fall, Feign Death...); E.2 split, E.3 next; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics E.3: finding and seeing (Detect Magic, Find Traps, Locate Object and Creature, Clairvoyance, Arcane Eye, Scrying, Drawmij's Instant Summons...), asking the powers from the world's truth (Augury, Divination, Commune, Contact Other Plane, Commune with Nature, Legend Lore), talking (a language rule on the road, Tongues, Speak with Animals and Dead, Sending, Dream's nightmare, Detect Thoughts); merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics E.4: minds and the law (Friends, Enthrall, Zone of Truth, Geas, Modify Memory, Glibness, Antipathy/Sympathy, Awaken), disguise and illusion (Disguise Self, Seeming, the images, Mislead, Project Image, Illusory Script, Nystul's Magic Aura, Nondetection, Sequester, the camp's illusions), the small arts (Druidcraft, Elementalism, Prestidigitation, Thaumaturgy); E.4 split, E.5 next; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics E.5: locks and stone (Knock, Arcane Lock, Mending, Mage Hand, Fabricate, Creation, Stone Shape, Passwall, Move Earth, Leomund's Secret Chest), weather and land (Control Water, Control Weather, Plant Growth with a new four-feet-a-foot ground, Tsunami from the meeting screen); E.5 split, E.6 next; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics E.6: lasting protections (Glyph of Warding, Symbol, Magic Circle, Forbiddance, Guards and Wards, Private Sanctum, Hallow) and the caster's keeping (Demiplane, Tasha's Bubbling Cauldron); E.6 split, E.7 next; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics E.7: great magic (Contingency, Magic Jar, Clone, Imprisonment) and Wish's other uses (Instant Health, Object Creation, Resistance, Spell Immunity, Sudden Learning, Reshape Reality; Roll Redo in a fight); Part E complete, merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics F.1: allies on the field - Find Familiar (twelve forms of Appendix B, it Helps, keeps watch, follows on the map) and Find Steed (the Otherworldly Steed by its slot, its kind's gift, Life Bond, a mount on the road); Part F split in four; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics F.2: summoned spirits of levels 2-4 - Summon Beast, Fey, Undead, Aberration, Construct, Elemental and Giant Insect (numbers by the slot, held by concentration, the form picked for the fight, every trait and blow, the costly components); F.2 split, F.3 next; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics F.3: the spirits of levels 5-6 (Summon Celestial: Avenger or Defender, Healing Touch; Summon Dragon: the breath with the Rends, its resistance shared; Summon Fiend: Death Throes, Devil's Sight, the yugoloth's step, Magic Resistance) and Animate Objects (things by the caster's modifier, commanded with the Bonus Action); F.4 next; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Demigods & Magics F.7: the rest of Appendix B - 24 creatures of the 2025 MM with pictures, each a Polymorph shape and met in its biome (the water-breathers wait for Expansion 22), the cult's imp and quasit, the towers' tadpoles; Trample, holds that restrain, the Sting's sleep, Burst of Ingenuity, Running Leap; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-17 | Steel & Shadows Part B: the Eldritch Knight (wizard spells, War Bond, War Magic, Eldritch Strike, Arcane Charge) and the Arcane Trickster (the unseen hand in fights and towns, Magical Ambush, Versatile Trickster, Spell Thief); merged into `main` | `dlc/04-steel-shadows` |
| 2026-10-17 | Steel & Shadows begun (the branch, the design note, four parts); Part A: the Battle Master (superiority dice, the twenty maneuvers on the blow, as answers and as bonus actions, Student of War, Know Your Enemy, Relentless, the dice on checks; the Auto uses them); merged into `main` | `dlc/04-steel-shadows` |
| 2026-10-17 | Demigods & Magics F.8: Animal Shapes and Shapechange - the party as beasts for a day (on the road: the beast chosen, its pace, wings over water and mountains, no spells or gear; in a fight: the willing, a Bonus Action to leave, the druid's fresh shapes), a wizard keeping mind and spells in a dragon's body for an hour, shapes kept from fight to fight; Part F complete; merged into `main` | `dlc/03-demigods-magics` |
| 2026-10-18 | Schools & Domains Part C: the Mage Apprentice, Mage, Archmage, Priest and Archpriest (blocks, dress by people, the road, temples and great cities), wizards' towers lived in (wards, glyphs, guardians, the master, the library), apprenticeships, the casters' tactics; merged into `main` | `dlc/05-schools-domains` |
| 2026-10-18 | Schools & Domains Part D: the eleven wands, seven staffs and four rods of the DMG, one store of charges a thing | `dlc/05-schools-domains` |
| 2026-10-18 | Schools & Domains Part E: crystal balls, the Enduring Spellbook, Enspelled Armor and Weapon, the Hat of Many Spells and the Hat of Wizardry, the Pearl of Power, the Ring of Spell Storing, the five robes, the Ruby of the War Mage; the icon; **released as v1.5.0** | `dlc/05-schools-domains` |

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
