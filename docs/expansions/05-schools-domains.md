# Expansion 5 — Schools & Domains (M, five parts)

*Icon*: an open grimoire under a radiant sun-disc. *Tagline*: "Every school of the arcane. Every domain of the
divine." Branch `dlc/05-schools-domains`; each part goes to `main` when it meets §5.2 of `docs/EXPANSIONS.md`; the
icon and version 1.5.0 come with Part E. Books: PHB 77–79 (Light, Trickery), 176–178 (Diviner, Illusionist), 372
(Illusions); DMG 78–79 (gods, divine intervention) and the Appendix B items; MM 201–202 (Mage Apprentice, Mage,
Archmage), 251 (Priest, Archpriest). Codex: 73 entries (`tools/codex/coverage.py --dlc`).

## What Anton will see

At level 3 a wizard may now become a **Diviner**, who wakes each morning with two (later three) dice already rolled
and lays them in place of anyone's roll – a foe's save against a spell, a friend's death save, a lock that must open –
and who opens a third eye that sees in the dark and sees the invisible; or an **Illusionist**, whose phantoms stand
on the battle mat as crates, walls and pillars that block a bowman's line until someone sees through them, whose
duplicate takes the blow meant for him, and who at the top makes an illusion real for a minute. A cleric may serve a
god of the **Light**, flaring to spoil a foe's blow and burning the dark away with the dawn, or of **Trickery**, with a
double that flanks foes, casts spells from where it stands and changes places with its maker. The gods of the world's
faiths now answer the desperate prayers of the devout (rarely). **Real mages and priests** walk the world: apprentices
and mages at the towers, an archmage at the greatest of them, priests and archpriests in the temples, all fighting
with the spells of their stat blocks (Counterspell, Shield, healing their side). **Wizards' towers** are lived in again:
the history's tower mage at the top, wards on the stairs, guardians, a library; apprenticeships are work. The
**wizard's and cleric's magic items** of the DMG come last: wands, staffs, rods, robes, hats, pearls and the crystal
ball.

## Decisions

- **Portent** is `char.spells["portent"]` (a list of d20s, rolled at `progression.long_rest`; three from level 14). A
  roll is replaced before it is made, once a turn, on any D20 Test of the diviner or a creature they can see: in a
  fight through the kernel's d20 door (`query.attack_roll`, `save_roll`, `Battle.check`, death saves) with the
  battle's judgement (asked under the Reactions setting "all"): a low die on a foe's save against the party's best
  spell or a foe's blow that would land on a hurt friend, a high die on a friend's save or death save that matters;
  outside one on the party's own checks (`camp.check`, `dialogue.check`, the dungeon's) when a high die makes a check
  that would otherwise likely fail. No save format change (char dicts are saved as they are).
- **Expert Divination** gives back a lower slot (up to 5) after a divination cast with a slot of 2+, in a fight and on
  the road. **The Third Eye** is a bonus action until the next rest: darkvision 120 (a sheet key), reading every
  script (`speech`), or See Invisibility without a slot; the Auto takes See Invisibility when an invisible foe is near.
- **Illusions on the battle mat** (PHB 372, §4.3.2): a new zone kind "illusion" – an image that blocks sight (not
  movement) for everyone except those who have seen through it (`Zone.seen` ids). Seeing through: the Study action
  (Intelligence (Investigation) against the caster's spell DC) or walking into it. Minor Illusion (a 5-foot image),
  Silent Image (a 15-foot cube) and Major Image (20 feet) become battle spells with `road_too` (their town uses stay).
- **The Illusionist**: Illusion Savant (`savant`); Improved Illusions (no Verbal component for illusion spells, +60
  feet of range, Minor Illusion known and cast as a bonus action); Phantasmal Creatures (Summon Beast and Summon Fey
  always prepared, each once a long rest without a slot at half hit points, drawn spectral); Illusory Self (a reaction
  when hit: the blow misses; once a short rest, or a 2+ slot restores it); Illusory Reality (a bonus action: one
  illusion of a slotted spell becomes real for a minute – it then blocks movement too, or bridges water and chasms
  as terrain restored when it ends).
- **The Light Domain**: Warding Flare (a reaction: disadvantage on a blow within 30 feet; Wisdom uses a long rest,
  short from 6, with 2d6 + Wisdom temporary hit points from 6); Radiance of the Dawn (Channel Divinity: ends magical
  darkness within 30 feet, 2d10 + level radiant, Constitution half); Corona of Light (a minute of sunlight, foes in it
  at disadvantage on saves against fire, radiant and the Dawn). Domain spells as the book.
- **The Trickery Domain**: Blessing of the Trickster (advantage on Stealth for one until a long rest; outside fights
  through the law's sneaking and the dungeon's); Invoke Duplicity (Channel Divinity, bonus action: a double for a
  minute – a Token on the field that casts the cleric's spells from its square and gives advantage when the cleric and
  the double are both beside a foe; moved 50 feet with a bonus action); Trickster's Transposition (swap places as it
  is made or moved); Improved Duplicity (friends' advantage beside it; heals the cleric's level when it ends).
- **Gods and divine intervention (DMG 78–79)**: the world's faiths (data/factions.json) keep their names; each gains
  `domains` (which of Life, Light, Trickery, War... its priests serve) and a god's temperament for omens. A devout
  character (a cleric, or anyone in good standing with their faith) who is about to die may be answered: a small
  chance that grows with deeds for the faith, once in a long while (the DMG's guidance), with a miracle chosen by the
  domain (healing, light, an escape). Clerics' level 10 Divine Intervention is unchanged.
- **Mages and priests** are the 2025 stat blocks with their spell lists cast through Expansion 3's enemy casters
  (`cdef["spells"]`, `tactics._pick_cast`); Counterspell and Shield as reactions. Dolls by culture (robes, vestments).
- **No new class and no new people.** No save format change unless a part needs one (then bumped and noted).

## Parts and tasks

### Part A — The Diviner and the Illusionist
- [x] A.1 Data: both subclasses in classes.json with savants; traits; Portent's dice at a long rest; the card.
- [x] A.2 Portent in a fight (attacks, saves, checks, death saves; once a turn; asked or judged) and outside one;
  Expert Divination; The Third Eye's three gifts; Greater Portent.
- [x] A.3 Illusions on the field: zone kind "illusion" (sight blocked, seen through by Study or touch); Minor
  Illusion, Silent Image, Major Image in battle; Improved Illusions; Illusory Self; Illusory Reality; Phantasmal
  Creatures (spectral summons at half hit points).
- [x] A.4 Tactics (Portent on the deciding roll; images cutting a shooter's line; the Auto's choices), the battle
  screen, pictures (portent dice, illusion shimmer), cards, icons, sounds; 17 codex entries + the Illusions rule; a
  test in a real fight each; Part A to `main`.

### Part B — The Light and the Trickery Domains; the gods
- [ ] B.1 Data: both domains, their spells, traits and Channel Divinity uses.
- [ ] B.2 Warding Flare and its improvement, Radiance of the Dawn, Corona of Light.
- [ ] B.3 Blessing of the Trickster, Invoke Duplicity (the double as a Token), Transposition, Improved Duplicity.
- [ ] B.4 The faiths' domains and divine intervention for the devout (DMG 78–79).
- [ ] B.5 Tactics, pictures (the flare, the dawn, the corona, the double), cards, icons; 13 codex entries + 2 DMG
  rules; Part B to `main`.

### Part C — Mages and priests of the world
- [ ] C.1 Mage Apprentice, Mage, Archmage, Priest, Archpriest stat blocks, creatures, dolls by culture, encounters.
- [ ] C.2 Wizards' towers lived in: the history's tower mage as its master (Mage or Archmage by fame), apprentices,
  wards and guardians, the library; temples staffed by priests (spells for pay from Expansion 3 G.2 by them).
- [ ] C.3 Apprenticeships as work (quests), the history's tower mages and high priests on these stat blocks.
- [ ] C.4 Tactics (Counterspell, Shield, healing their side), arena green; cards, words; 5 codex entries; to `main`.

### Part D — Wands, staffs and rods
- [ ] D.1 The eleven wands (binding, enemy detection, fear, fireballs, lightning bolts, magic detection, magic
  missiles, paralysis, polymorph, pyrotechnics, the war mage).
- [ ] D.2 The seven staffs (adornment, charming, healing, power, striking, the magi, the enspelled staff) and the four
  rods (absorption, alertness, resurrection, rulership); treasure placement, pictures, the Auto's use; to `main`.

### Part E — Robes, hats and the rest; release
- [ ] E.1 Crystal Ball, Enduring Spellbook, Enspelled Armor and Weapon, Hat of Many Spells, Hat of Wizardry, Pearl of
  Power, Ring of Spell Storing, the five robes, Ruby of the War Mage.
- [ ] E.2 Every Expansion 5 codex entry settled; balance; the icon; release v1.5.0.
