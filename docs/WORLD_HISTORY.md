# Deep history: a world that has really lived (design, 2026-10-10)

Anton's request (2026-10-10): look through the code of Realmwalker and of Dwarf Fortress, work out how DF makes its
worlds, and give Realmwalker the same kind of living world, "with long history and unique characters", as detailed
and expansive as DF's, better suited to the game if possible, without breaking anything.

## What Dwarf Fortress does (what was learned)

DF's program code is closed, so this comes from what its folder does show: the world-gen settings and Lua generators
(`data/init/*.lua`, `data/vanilla/vanilla_procedural`), the civilisation definitions (`vanilla_entities`), and above
all two Legends exports, which are complete histories of real generated worlds. One of them (region 7, 252 years) was
read through by a script: 54,301 historical figures, 5,669 entities, 1,899 sites, 10,704 artifacts, 59,749 written
works and 532,414 events of 108 kinds, grouped into 29,420 "collections" (wars, battles, site conquests, beast
attacks, abductions, thefts, persecutions, journeys, festivals).

The heart of it:
1. **History is simulated, then the present is whatever is left.** Civilisations start at a few sites and spread by
   founding new ones; wars, beasts and plagues destroy some; what survives at the last year is the world you play.
   Every ruin was a real place, destroyed by someone, in a year, for a reason.
2. **Historical figures are real people with families.** Mothers, fathers, spouses, children, apprentices, friends,
   grudges; they hold positions, fight in battles (and are named in them), slay or are slain (DF's commonest causes of
   death: struck down in a fight 23k, murdered 6k, old age 5.5k), write books, make artifacts, worship gods, plot.
3. **Entities nest**: a civilisation, each site's government, its religions, military orders, merchant companies,
   bandit gangs, performance troupes. Positions have succession rules.
4. **Events are grouped into named collections**: "the Steamy Conflict" (a war) holds 28 battles; a battle holds
   duels and deaths; a conquest holds the attack, the plunder and the new leader.
5. **Artifacts have provenance**: made by a named person, carried, stolen, lost, claimed, stored, found again.
6. **Monsters have biographies**: megabeasts and titans with lairs attack sites (5,071 beast attacks), kill named
   people and are hunted by named heroes. The busiest figures in the export are demons, cyclopes, titans and rocs.
7. **Gods** have spheres; everyone worships; curses, secrets of immortality, necromancers.
8. **Eras** are named after the state of the world ("Age of Myth", "Age of Legends").
9. **Defenders usually win** (1,620 of 1,918 battles): wars grind, conquests are rare and mean something.

What DF does badly for a game like this: the history is enormous and mostly noise (100k "settled at a site" events,
24k scuffles), it does not care whether the present is playable, and almost none of it reaches the player outside
Legends mode.

## What Realmwalker had (before this work)

`world/generator.py` makes today's map first (terrain, settlements placed by how good the land is, roads, random
ruins); `world/factions.py` hands today's settlements to today's factions; `world/history.py` then *tells* a history
that agrees with them: a list of past rulers per faction, founding years, a cause for each ruin, a few legendary
heroes, dragons and artifacts, and the politics engine run in "history mode", which may only tell conquests that agree
with today's borders. A medium world had about 360 figures and 700 lines of history. History was decoration: nothing
in the present happened because of it.

## The new design: the ages are lived, and today is what is left

### In one paragraph (for Anton)
When a world is made, the land forms as before; then the years are lived one by one, as in Dwarf Fortress. Peoples
found towns and villages, kingdoms rise, marry, quarrel and go to war; battles are fought by named commanders and
knights, some die and are remembered; towns are besieged, sacked, burned, abandoned, rebuilt; dragons and other
monsters come out of the wild, burn villages and are hunted by heroes; prophets found churches and heretics found
cults; smiths make famous weapons that pass from hand to hand and are lost in battles, buried with kings or carried
off by dragons. Whatever is standing at the end is the world you play: every ruin was once a real town, every lord
has real ancestors, the troll in the cave has killed real people, and the sword in the barrow belonged to a real king.
A new Legends book lets you read all of it, like Legends mode, with every name a link.

### Better than DF, for this game
- **A playable present is guaranteed.** The simulation is steered without cheating: the places that will be today's
  towns are known in advance ("fated"), so the world always ends with the same number of cities, towns, villages,
  holds and halls as before (balance, quests and tests keep working); places that are "doomed" become ruins through
  real causes. Every event that is told really happened in the simulation.
- **Less noise, more story.** Only what a chronicler, a bard or a grandmother would remember is recorded; small things
  are counted, not listed.
- **The past reaches the player**: ruins say what they were; townsfolk who are historical figures tell their own
  history; named monsters wait in their lairs; barrow kings lie in their barrows with their grave goods; artifacts lie
  where the history left them; bards sing real songs about real events; books quote real chronicles.
- **History leaves marks on the land**: the dead of great battles do not rest easily, and the dragon's country is
  burned (later step).

## Architecture

```
world/generator.py      terrain as before; places today's settlements ("fated" spots) and the doomed ones; roads,
                        danger, the other sites; then runs the ages
world/ages/             the history simulation (pure logic, no UI)
  sim.py                AgeSim: state, the yearly loop, recording events, progress
  land.py               spots: fated and doomed places, neighbours, founding, growth, ruin
  folk.py               figures: birth, marriage, children, death, names and regnal numbers, careers
  realms.py             realms and lords: origins, feudal grants, succession, regency, crowns, rebellions, free cities
  war.py                wars: causes, allies, campaigns, named battles with commanders and casualties, sieges, peace
  wild.py               tribes, raids and abductions; beasts and dragons with lairs; heroes who hunt them; old sites
  faith.py              gods, churches, temples, saints, heresies, cults, persecutions
  lore.py               artifacts (made, carried, lost, buried, hoarded) and works (chronicles, songs, poems)
  orders.py             guilds, knightly orders, mages, mercenaries, gangs, pirates
  eras.py               naming the ages
  present.py            the end: doomed places become ruins, today's factions are checked and dressed, records for
                        the rest of the game (dragons, artifacts, ruins, lairs, eras)
  words.py              names of wars, battles, beasts, artifacts, works, eras; event text
world/history.py        public API (unchanged names): generate_history(), ensure_history(), the chronicle; old worlds
                        keep the old "told" history
world/legends.py        reading the history back: biographies, place histories, indexes, links (logic, no UI)
ui/screens/legends.py   the Legends book
data/history.json       every number and word the simulation uses (validated by data/schemas.py)
```

### Data model (all additions optional, so older saves still load)
- `Figure` gains `kind` (person, dragon, beast, god), `mother`, `father`, `home` (settlement), `lair` (site), `job`,
  `cls` and `level` (for heroes), `kills`, `slayer`, `buried` (site), `spheres` (gods), `deity`, `creature`
  (bestiary id), `regnal` (II, III...). `parent` keeps its meaning (the parent the house descends through).
- `world.history` events gain `id`, `sites` (site ids, for ruins and lairs), `war` (war id) and `data` (who fought,
  who died, numbers). `places` still means settlement ids.
- `world.wars` keeps every war ever fought (inactive ones are history), now with a `name` and `dead`.
- `world.factions` keeps fallen factions (`fallen` = year) so they can be read about; everything else already uses
  `active_factions`.
- `world.politics` gains `places` (each settlement's founding, founders and former names), `ruins` (now with the real
  past), `lairs` (site id -> beast figure id), `tombs` (site id -> figure id), `works`, `eras`, and richer
  `artifacts` (maker, year, every hand it passed through, where it is now) and `dragons` (same keys as before).

### The simulation, year by year
1. **Places.** Spots are fated (today's settlements, placed exactly as before) or doomed (extra places on good land,
   spaced like settlements). A spot is founded by the people who reach it first, takes their culture and a name in
   their tongue, grows toward what the land can feed, and may be raided, sacked, burned, struck by plague, abandoned
   or rebuilt. Fated places are founded in time to grow into what they are today; doomed places meet their end by a
   real cause (war, a horde, a dragon, plague and abandonment).
2. **Peoples.** Humans (Heartland, Northmarch, Southron) start from a few old realms in their homelands; halflings
   settle among them; dwarves and elves are elder peoples whose holds and halls are older than the records; orcs,
   goblins and nomads live in tribes in the wild.
3. **Folk.** Ruling families are real families: marriages between houses (alliances), children, heirs, siblings who
   might claim a throne, regents for child rulers, regnal numbers ("Aldric III"). Knights, generals, priests,
   mages, smiths, bards and heroes are made when the story needs them and then live their lives.
4. **Realms.** Kingdoms grant towns to noble houses (new houses are raised from war heroes and knights); successions
   follow each people's custom (primogeniture, tanistry, seniority, election); a throne without an heir means a
   crisis or a war of succession; vassals rebel; cities buy their freedom; lordships proclaim themselves kingdoms.
5. **War.** Neighbouring powers that hate each other go to war for a reason (land, a claim through marriage, faith,
   revenge, raids); allies join; every war has a name; each year brings battles at real places with named
   commanders, numbers and the dead (who killed whom), sieges, sacks and peace treaties that move borders.
6. **The wild.** Tribes raid, burn hamlets and carry people off; named beasts (dragons, trolls, ogres, giant spiders,
   dire wolves, great bears) take lairs in caves and ruins, attack settlements and kill people; heroes and knights go
   to slay them and win fame and epithets, or die and leave their gear in the lair.
7. **Faith.** Each faith has a pantheon (its god and lesser gods and saints with spheres); temples are raised as towns
   grow; martyrs become saints; heretics found cults that are persecuted.
8. **Lore.** Master smiths make named artifacts for rulers, heroes and churches; artifacts are inherited, lost in
   battle, taken by the victor, stolen, buried with their owner, carried off by dragons. Bards and chroniclers write
   songs and chronicles about the great events.
9. **Orders.** Guilds, orders, mercenary companies (veterans after a war), gangs (deserters), pirates, a mages'
   circle (founded by a real archmage) and a healers' guild (founded after a real plague) appear when the history
   gives them a reason.
10. **Eras.** The years are divided into ages and named after what dominated them (dragons, wars, plague, a golden
   age of one realm, the founding years).

### The present
At the last year, doomed places that still stand meet their fate, then become ruins (sites) that keep their whole
past. Today's factions are the simulation's survivors, with laws, strength, colours, goals ("to retake X") and
relations from their history. The records the rest of the game already reads (`dragons`, `artifacts`, `ruins`,
`founded`, rulers, heirs, wars) keep their old shape, so quests, dungeons, books, uniques, the death screen and the
interlude keep working.

### Guarantees (tested)
Same seed, same history. Every reference in every event resolves. Genealogy is sane (parents older than children,
nobody dies before birth or lives past their people's span, rulers in order). Replaying the ownership events of a
place gives today's holder. Every ruin has a past; every living beast has a lair; at least one dragon sleeps. Today's
world has the same structure as before (at least two kingdoms, noble houses, every town held by a realm, the counts of
guilds, cults and gangs). A medium world's history is lived in a few seconds; a large one in well under 30.

## Choices made (and why)
- **Fated places** rather than an unsteered simulation: Anton's balance, quests and the tests rely on the present
  having a known shape; DF itself rejects worlds that come out wrong, which this game cannot afford to do.
- **Only remembered things are recorded** (about 40 events a year in a medium world, not DF's 2,000).
- **Figures are the notable** (families of rulers, knights, priests, heroes, villains, beasts), a few thousand per
  world, not every peasant; common folk are numbers, as in DF's "entity populations".
- **No new monsters with no picture**: beasts use creatures that already have stat blocks and figures.
- **Old worlds keep their old history**; a new world gets the new one. Nothing is lost.
- **History length** is a choice when making a world (100, 250, 500 or 1000 years), as in DF; 250 by default.
