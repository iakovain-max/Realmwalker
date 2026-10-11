# A world of extremes, peoples and living towns — design

Anton asked (2026-10-11), in his words, for:

1. **Extremes**: "Huge cities, way bigger than the other ones. Extremely hot deserts. Inhospitable northern glacial
   plains. Epic mountain ranges ... deviations, make it interesting and varied", and **great wonders of the world**:
   "gigantic mountains, waterfalls, lava lakes, volcanoes, enchanted forests, unusual lakes, cliffs, oases, beautiful
   ravines".
2. **Cultures** "with drastically different styles, architecture, names, dress and armor, law", especially among
   humans, evolving naturally but "reminiscent of real world" (desert people with Arabic-style names, a northern people
   somewhat Scandinavian), "way more names and naming variations" (people, kingdoms, relics, clans, churches): today
   every world sounds the same.
3. **Towns far more varied**: dwarven cities are "human cities inside a mountain (lighted during the day and dark
   during the night)", elven cities "human cities made of wood with green woods". More variety of shapes, sizes and
   looks of towns and buildings; much more furniture and things (torches, flags, tables, books, boxes, chests,
   sculptures...).
4. **Towns bigger and more realistic**, more places, more happening, "way, way more citizens"; walking into someone
   no longer starts a conversation; people move on their own, and time moves independently of the player's moves.
5. **The world map** more vivid and varied, showing the new lands; **names for geographic features** (lakes, rivers,
   ranges, wonders) in the language of the people living nearby; **clearer realm and culture map modes**; a map that
   is comfortable to zoom and scroll, and not laggy.

Old saves need not load (he said so). This document is the design; the plan is
`docs/superpowers/plans/2026-10-11-world-variety.md`.

## What success looks like

- Two worlds made with different seeds feel like different places: different peoples, different-sounding names,
  different lands; within a world, a desert city, a northern fjord town, a steppe camp, a dwarven hold and an elven
  grove look nothing alike from the street and inside.
- Every world has a few things worth travelling to see, named, drawn on the map, with a place of their own to walk.
- A big town has hundreds of people who go about their day while you watch; you can walk through a crowd.
- The world map opens instantly and zooms and pans smoothly; its realm and culture views can be read at a glance.
- Nothing that works today stops working: every existing test, the smoke test and the autoplay bot stay green.

## 1. Peoples (cultures)

**One registry.** `data/cultures.json` defines every culture: who they are (race, label, "like" = the real-world
inspiration), where they like to live (biome weights, temperature and moisture ranges, coast or interior), how they
name people (patterns, gendered family names), realms (realm name patterns per faction kind) and titles, their faith,
law, succession custom, town style, dress, colour on the culture map, and a one-line "about". Name pools stay in
`data/names.json`, place-name parts in `data/place_names.json` (which gains per-culture *geography* patterns), laws in
`data/factions.json` `culture_laws`, peoples in `data/history.json` `peoples`. `realmwalker/world/cultures.py` reads
them all and answers questions ("the human cultures", "the title of a sultanate's ruler", "how a Volsk woman's family
name ends"); code stops listing cultures by hand (about 60 places today).

**Human cultures** (id, inspiration, home):

| id | like | home |
|---|---|---|
| heartland | English, Anglo-Norman | temperate plains and woods |
| northmarch | Norse | cold coasts, taiga, tundra |
| southron | Italian, Iberian | warm coasts and hills |
| highland | Gaelic (Scots, Irish, Welsh) | cool wet hills and moors |
| qasari | Arabic, Persian | deserts, dunes, oases |
| khurgan | Mongol, Turkic | steppe and dry grassland |
| volsk | Slavic, Rus | cold forests and great rivers inland |
| thalassian | Greek, Byzantine | warm coasts and islands |
| itzan | Maya, Aztec | jungle and hot lowlands |

Elves, dwarves, halflings and orcs stay as they are (and get their own geography names, town styles and dress).

**Where they live.** After the biomes are made, each human culture's suitability is scored over the map; a world gets
the cultures whose homes exist (small 4-5, medium 6-7, large 8-9), each from a hearth at its best spot, grown outwards
by a competing flood whose cost follows the land (seas and mountain ranges make borders). The result is a culture map
(`world.culture`, indices into `world.culture_ids`, saved like the biome map). Settlements take the culture of their
ground (holds dwarven, elf-halls elven, some villages halfling).

**Evolving.** In the lived history (world/ages) a realm that founds or takes a place far from home brings its people:
colonies and conquests spread a culture; a town ruled for generations by another people may come to speak as they do
(an event in the history). At the end the culture map is redrawn around the settlements, so frontiers are where the
history left them. Each world also gives every culture its own name for itself (from a list per culture: the
Northmen, the Hrafnings, the Vestfolk...), so the same people sound different from world to world.

**Names.** `realmwalker/world/names.py` (the name forge) gives every name in the game:
- much bigger pools per culture (150+ given names per sex and 150+ family names), and
- per world, new names grown from each culture's own sounds (a letter-chain model trained on its pool), mixed with
  a share of the real pool, so worlds do not share their people;
- culture-shaped full names: patronymics (Bjorn Haraldsson, Sigrid Haraldsdottir; Rashid ibn Tariq; Ivan
  Petrovich), gendered family names (Volkov / Volkova, Komnenos / Komnene), clan names (Fergus mac Aodh, Mairi nic
  Aodh), bynames; nobles keep a house name as their last word, which the history uses for dynasties;
- places, realms ("the Sultanate of Qadira", "the Jarldom of Hvitfjell", "the Grand Principality of Volodar", "the
  Khaganate of the Blue Sky"...), noble houses ("the Banu Qasim", "Clan MacAodh"), churches, guilds, gangs, relics
  ("Dhu'l-Nur, the Sword of the Morning", "Skull-Splitter") in each culture's style;
- new faiths for the new peoples (the Eternal Sky, the Thunder-Kin, the Twelve Thrones, the One Flame, the Feathered
  Serpent, the Ash-Tree Gods), with their gods for the history.

**Everything else a people changes**: titles of rulers (Sultan, Khan, Jarl, Knyaz, Basileus...), laws, succession,
town style (section 3), dress and arms (section 5), the AI's name style, the arrival line ("Qasari folk live here"),
and a new character can be born to any of them (races.json).

## 2. The land: extremes and wonders

**Per-world character.** New world options (with Random as the default): *Land* (continent, islands, twin lands,
inland sea) and *Climate* (frozen, cold, temperate, warm, scorched, varied). They shift the sea fraction, the
coastline shaping and the global temperature, so worlds differ in kind and not only in seed.

**Epic ranges and extremes.** One to four great ranges are drawn as wandering spines across the land and raised far
higher than the rest (peaks to 8,800 m; the highest is a named wonder); plateaus end in cliffs; rivers that cross a
cliff fall; rivers through dry high ground cut ravines. Temperature spreads further (polar ice in the far north, deep
heat in the dry south) and new biomes appear where the climate calls for them:

| new biome | where | behaves like (code families) |
|---|---|---|
| glacier | below about -10 °C | tundra (and colder) |
| steppe | cool and dry plains | plains |
| savanna | hot, half-dry | plains |
| jungle | hot and wet | forest (slower) |
| dunes | very hot and very dry | desert (hotter) |
| badlands | dry broken uplands | hills |
| salt_flat | dry basins | desert |
| volcanic | around volcanoes | hills (barren) |
| fey_forest | the enchanted woods (a wonder) | forest |

Every biome names a **family** (`biomes.json` "family"); code that asks "is this a desert?" asks the family, so all
the systems that know deserts, forests and tundra (camps, encounters, music, survival, water, vision, mounts) work for
the new lands without a list of cases each.

**Wonders** (`data/wonders.json`, `realmwalker/world/wonders.py`): placed after the land by their own rules, each named
in the language of the nearest people, drawn on the world map, described when you look, with a close-up map of its
own, a page in the Legends book, a place in the history (volcanoes erupt; pilgrims go to holy lakes), and something
for the player (discovery and fame; some a boon: hot springs heal, an oasis waters, the enchanted wood is strange).
Kinds: the great peak, volcanoes (one awake with a lava lake), great waterfalls, ravines, great cliffs, crater lakes,
salt lakes, glowing lakes, oases, hot springs, the enchanted forest, a giant tree, stone arches, sinkholes, a
petrified forest, a great glacier wall, and the drifting stones (rocks that float: the one plainly magical thing).

**Geography has names.** Areas (forests, ranges, hills, marshes, deserts, plains, lakes, rivers, seas, and now
islands and bays) are named by the culture of the land they lie in, with each culture's own words ("Svartvatn",
"Jabal al-Nar", "Wadi Rimal", "Belozero", "Loch Dubh", "Monti Neri", "Khar Nuur") and sometimes in translation
("the Weeping Fells"). Big areas show their names on the world map.

## 3. Towns

**Bigger.** The close-up map of a settlement is sized to it: hamlet 96x64 ... city 192x128, and a **great city**
(the one or two largest places in a world, many times the size of any other) 256x176. Populations follow a steep
curve so the largest cities dwarf the rest.

**A style per people** (`data/towns.json`, `realmwalker/world/towns/`): each culture or race picks a layout and the
stuff of its buildings.

| style | who | the town |
|---|---|---|
| organic | heartland, highland, northmarch villages | roads in from the country to a market square; streets branching; walls around the core with gates where roads cross; suburbs and fields outside |
| grid | southron, thalassian cities | planned blocks, a piazza or agora with colonnades, a harbour |
| medina | qasari | a bazaar street from the gate to the great domed temple; courtyard houses down winding alleys; a citadel; palms and a pool |
| camp | khurgan | rings of round felt tents around the khan's great tent; horse pens; carts |
| kremlin | volsk | a wooden fort with towers on a rise by the river, an onion-domed church inside; log houses along streets outside |
| terraces | thalassian towns | white houses stepping down to the sea; a temple of columns above |
| plaza | itzan | a stepped pyramid on a great plaza, a ball court, causeways to thatched compounds, a cenote well |
| longhouse | northmarch | long halls round a mead hall, a stave church, boat sheds on the shore, an earth rampart |
| hold | dwarves | cut into the rock: a gate in the mountain, a pillared great hall, forges over lava channels, mushroom farms, tombs, stairs and bridges over chasms; no sky: braziers and lava light it, day and night alike |
| grove | elves | giant trees with homes in and around them, glades, moonwells, glowing lanterns, stepping stones, no walls but thorn hedges |
| burrows | halflings | homes dug into green mounds with round doors, gardens and hedges |

**Buildings** come in shapes (rectangle, L, courtyard, round, cross, long hall), with rooms inside (hall, bedroom,
kitchen, workshop, shop floor, chapel, storeroom...) furnished by what the room is for, and their look follows the
style: roofs (thatch, slate, tile, shingle, turf, flat with parapet, dome, onion dome, felt, stepped stone, living
leaves) and walls (plaster and timber, brick, stone, logs, mud brick, whitewash, sandstone, marble, felt, living
wood). Many more kinds: bakeries, butchers, tailors, tanneries, mills, warehouses, barracks, guildhalls, libraries,
bathhouses, monasteries, shrines, palaces, mansions, docks, lighthouses, jails.

**Things** (local terrain, each with a picture): torches and lanterns on walls (they light the night), lamp posts,
braziers, banners and flags, statues, fountains, benches, flower beds, hedges, palms, market stalls with their goods,
tables and chairs and stools, beds, chests and trunks, wardrobes, shelves and bookcases, books, rugs, tapestries,
barrels, kegs, crates, sacks, weapon racks, armour stands, looms, spinning wheels, ovens, kilns, cauldrons, anvils,
altars, thrones, candles, and the rest. Chests and trunks in towns are furniture, not loot (no new theft rules).

## 4. People who live there

**Many more.** The number of townsfolk follows the population: a hamlet 8-14, a village 20-35, a town 50-110, a city
120-260, a great city 250-450, a hold 60-150, an elf-hall 40-90. Besides the people of note there are bakers,
butchers, tailors, scribes, monks, soldiers, sailors, porters, children, elders, minstrels, preachers, pilgrims...
(new occupations with their own words). Ordinary people get their full description only when you first look at them
or speak to them.

**A day.** Everyone has a home, a post and a day by their trade: up at dawn, to work, a meal at noon, the inn or the
square in the evening, home to bed; guards keep shifts and walk rounds; children play; merchants keep their stalls;
drunks stagger home late. They **walk** there along the streets (paths found once and kept), go in through doors
and come out again, and step round each other and you.

**Time flows in towns.** On a close-up map the clock runs by itself (Settings, *Time in towns*: "flows" or "waits for
you"): one step of time (6 seconds of the world) about every half second, and people move with it; you walk as before.
Time stops whenever another screen is open. In the wild and underground time still waits for you (monsters creeping
up while you read the map would not be fair).

**Walking into someone** no longer starts a conversation: you squeeze past (you swap places), unless they will not
budge (a guard at the gate). To talk: **t** (to whoever is beside you; a short list if several are), Enter, or click
them. A crowd can be walked through.

**More happening**: people say things as you pass (a few words over their heads: "Fresh bread!", "Mind the cart!"),
a minstrel plays in the square, a preacher preaches, criers cry the news, the watch goes round with lanterns at night,
market days fill the square, now and then a procession or a brawl.

## 5. Dress and arms by people

Townsfolk, guards, nobles and soldiers dress as their people do: Qasari robes, turbans and veils, lamellar and
turban helms with curved swords; Khurgan coats closed at the side, fur hats, lamellar, bows; Northmen in wool and fur
with mail, round shields and nasal helms; Volsk kaftans, tall hats, scale and pointed helms; Thalassians in draped
tunics, crested helms and round bronze shields; Itzan quilted cotton armour, feathers and obsidian-edged clubs;
Highlanders in plaids; Southrons in doublets and morions. New garments are drawn in `tools/figure_gear.py`; which
people wear what is data (`data/sprites.json` figures "cultures").

## 6. The world map

**Painted once.** The whole world is painted once, in a background thread, at a fixed 12 map pixels to a square, and
shown at any zoom by the GPU: whole-number enlargements stay sharp pixels, reductions are smoothed. Zooming and
panning never repaint. A small picture of the whole world stands in for the first moments.

**Vivid.** Richer colours with the climate in them (green wet plains, gold steppe, red badlands, white glaciers, dark
jungle), sea that shades from turquoise shallows to deep blue, snow on high peaks, stronger relief; new little
drawings (dunes, palms, acacias, jungle canopy, steppe grass, glacier cracks, volcanoes with fire and smoke, mesas,
salt pans, fey trees, cliffs); the wonders drawn large; towns drawn in the style of their people (domes, yurts,
longhouses, onion domes, white towns, pyramids, mountain gates, great trees); names written on the land (seas, ranges,
deserts, forests, lakes, rivers), as many as fit at that zoom.

**Comfortable.** The mouse wheel zooms where the pointer is, smoothly; dragging pans; arrows move the cursor (the view
follows) and Shift moves faster; a click selects a place and the side panel tells about it; Enter, a double click or
the side panel's button travels there (a single click no longer sets off). The view opens centred on you.

**Map views** (keys and buttons): Land, **Realms** (each realm filled in its colour with a strong border and its name
across it; vassals striped with their liege's colour; wars marked; a legend in the side panel with each realm, its
ruler and how it stands with you, and clicking one highlights it), **Peoples** (each culture filled in its colour with
its name across its lands; the legend tells how they live), and Weather.

## 7. Saves and safety

The save format version goes up; older worlds are refused with the friendly message (allowed). Logic never imports
UI; one seeded RNG per world (`rng.child`); data validated at startup; arrays are [x, y].

## 8. Testing

New tests for each part (cultures and names, placement, biomes and wonders, geography names, each town style:
connected, doors reachable, nobody walled in; people's days, paths, swaps, the town clock; bump does not talk; the
painter and the map views headless; the map screen's zoom and pan), the existing suite kept green, performance kept
in bounds (a large world with 1000 years under 30 s; a great city's close-up map under 2 s; a town tick with 300
people under 10 ms), and the autoplay bot learns the new things (it walks through crowds, talks with t, opens the
map views) and checks new invariants (townsfolk stand on walkable ground and never two on one square).
