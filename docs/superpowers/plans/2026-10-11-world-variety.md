# World Variety Implementation Plan

> **For agentic workers:** implemented natively in one long unattended session (Anton's standing preference: no
> check-ins). Steps use checkbox (`- [ ]`) syntax for tracking. If the session is summarised, re-read this file and
> `docs/WORLD_VARIETY.md`, then continue from the first unticked step. Branch: `world-variety` (from `world-history`).

**Goal:** worlds of extremes and wonders, peopled by distinct real-world-inspired cultures with far more names, with
big, varied towns full of people who live their day in real time, shown on a vivid, fast, readable world map.

**Architecture:** a culture registry (`world/cultures.py`) and name forge (`world/names.py`) that every namer uses; a
culture map made after the biomes and moved by the history; new biomes with code "families"; wonders as their own
module; a town package (`world/towns/`) with a style per people; a town clock and walking townsfolk
(`game/townlife.py`); a world map painted once and shown at any zoom, with realm and people views.

**Tech Stack:** Python 3.12, numpy, tcod (paths, SDL), Pillow; data in `data/*.json` validated by
`realmwalker/data/schemas.py`; tiles built by `tools/build_tiles.py` (+ `tile_art.py`, `figure_gear.py`).

**Spec:** `docs/WORLD_VARIETY.md`

## Global Constraints
- Logic never imports UI; one seeded RNG per world (`rng.child(...)`), no `random` module in game logic.
- Numbers and words in `data/*.json` with schemas; new data files are registered in `schemas.FILES` and validated.
- Arrays indexed `[x, y]`; LF line endings (`tr -cd '\r' < file | wc -c` is 0); use the Edit tool for backslashes.
- Never let a test or the smoke test reach the real Player2 app.
- Old saves may be refused (bump `game/save.py` FORMAT_VERSION once), never crash, never delete files.
- Budgets: large world with 1000 years < 30 s; a great city's close-up map < 2 s; a town tick with 300 people < 10 ms.
- Phase done = targeted tests pass; milestone done = all tests + smoke test + autoplay both AI modes; commit; push.

## Review Focus
- A world whose climate has no desert (or no steppe...): the cultures that need it are simply absent, nobody breaks.
- A culture with patronymic or gendered family names founding a dynasty: the dynasty name stays stable for its heirs.
- A settlement whose culture changed in the history: its close-up map, names and dress follow the new culture.
- A crowd of townsfolk in a narrow street or a doorway: the player can always get through, nobody is stuck forever.
- A huge city's close-up map at the map edge, on a river and a coast at once: still connected, still enterable.

---

### Phase 1: Peoples and names

#### Task 1.1: The culture registry
**Files:** create `data/cultures.json`, `realmwalker/world/cultures.py`; modify `realmwalker/data/schemas.py`
(CULTURES, cross-checks in `registry.py`), `realmwalker/world/tables.py` (`tables.cultures`).
**Produces:** `Cultures(tables_data)` with `ids`, `human`, `get(cid)`, `label(world, cid)`, `race(cid)`,
`realm_patterns(kind, cid)`, `title(kind, sex, cid)`, `faith(cid)`, `town_style(cid)`, `dress(cid)`, `home(cid)`.
- [ ] Tests: data valid; every culture has names, place names, laws, peoples, faith; labels; titles fall back.
- [ ] Commit.

#### Task 1.2: Names for nine human peoples (data)
**Files:** `data/names.json` (heartland, northmarch, southron grown; highland, qasari, khurgan, volsk, thalassian,
itzan new: 150+ per sex and family each; bynames), `data/place_names.json` (settlement parts per culture, `geo`
patterns and words per culture), `data/factions.json` (culture_laws, land suffixes, new faiths), `data/history.json`
(peoples, pantheon for the new faiths, artifact words per culture).
- [ ] Tests: pool sizes; every culture has every geography kind; no duplicate names inside a pool.
- [ ] Commit.

#### Task 1.3: The name forge
**Files:** create `realmwalker/world/names.py`; tests `tests/test_names.py`.
**Produces:** `forge(world, tables) -> NameForge` (cached per world seed) with `given(cid, sex, rng)`,
`family(cid, sex, rng)`, `person(cid, sex, rng, *, father=None, noble=False, family=None)`, `family_for(cid, base,
sex)`, `base_family(cid, family)`, `place(cid, rng)`, `geo(cid, kind, rng)`, `realm(kind, cid, rng, **values)`,
`label(cid)`; Markov name growth (order 2-3) with a share of real names; a blocklist.
- [ ] Tests: deterministic per seed; worlds differ; gendered family names; patronymics; uniqueness helpers.
- [ ] Commit.

#### Task 1.4: Everyone names through the forge
**Files:** `world/factions.py` (make_figure, land_name, seat_family, titles), `world/ages/folk.py` (first_name,
family_name, person, child), `world/ages/realms.py`, `present.py`, `lore.py`, `orders.py`, `wild.py`, `war.py`,
`world/naming.py` (Namer uses the forge), `game/people.py` (make_npc, race_for), `rules/creation.py` (ties, start
places by culture), `ai/tasks.py` (culture styles from data), `game/state.py` (arrival line), `game/uniques.py`.
- [ ] Tests: whole suite green; a world's figures use each culture's patterns; dynasties stable.
- [ ] Commit.

#### Task 1.5: The culture map and its history
**Files:** `world/generator.py` (`_cultures` after `_biomes`; settlements take their ground's culture), `world/model.py`
(`culture` array + `culture_ids`), `world/ages/land.py`/`realms.py` (colonies and conquests carry culture;
assimilation events; `present` redraws the map), `data/races.json` (human cultures), `game/save.py` (FORMAT_VERSION).
- [ ] Tests: cultures contiguous and suited; settlements match; history changes recorded; old-save refusal friendly.
- [ ] Phase verification (full suite), commit, push.

### Phase 2: The land

#### Task 2.1: Biome families and new biomes
**Files:** `data/biomes.json` (family + glacier, steppe, savanna, jungle, dunes, badlands, salt_flat, volcanic,
fey_forest), `world/tables.py` (`family` table), code that names biomes (camp, care, encounters, mounts, survival,
vision, arena, state, music mood, ages wild/factions tribe homes, localview cold biomes, history), `data/local_terrain.json`
+ `data/sprites.json` + tiles for new ground and plants (palm, acacia, jungle tree, cactus, ash, lava, salt crust,
red rock, glacier ice, fey trees).
- [ ] Tests: every biome has a family and a local recipe; systems answer for new biomes.
- [ ] Commit.

#### Task 2.2: World options and extremes
**Files:** `world/generator.py` (Land and Climate options; great ranges; plateaus and cliffs; ravines; polar ice;
hot deserts; biome rules), `ui/screens/new_world.py` (two new rows).
- [ ] Tests: each option makes worlds with the expected traits; highest peaks above 6000 m; glaciers in frozen worlds.
- [ ] Commit.

#### Task 2.3: Wonders
**Files:** create `data/wonders.json`, `realmwalker/world/wonders.py`; modify generator (placement), model (sites of
kind "wonder" or `world.wonders`), `world/local.py` (close-up maps of wonders), `game/describe.py`, `world/legends.py`,
history (eruptions), discovery and boons (`game/state.py` discover, camp).
- [ ] Tests: every wonder kind can be placed and has a map; names; boons; Legends pages.
- [ ] Commit.

#### Task 2.4: Geography named by its people
**Files:** generator `_areas` (islands, bays, ranges, peaks), `world/names.py` geo, `game/describe.py`.
- [ ] Tests: areas named in the culture of their ground; every kind has a pattern.
- [ ] Phase verification, commit, push.

### Phase 3: The world map

#### Task 3.1: Painted once, shown at any zoom
**Files:** `ui/gfx/paint.py` (canonical k=12 tiles of the whole world, painted in the background, faster stamping),
`ui/gfx/worldview.py` (draw any ppc from the canonical tiles), `config.py` (WORLD_ZOOMS).
- [ ] Tests: painter tiles cover the world; any zoom draws without painting; headless timings.
- [ ] Commit.

#### Task 3.2: Vivid colours, new marks, wonders, towns by people, names on the land
**Files:** `paint.py`, `data/sprites.json` world section, `tools/tile_art.py` (town marks by style), tiles rebuild.
- [ ] Tests: every biome has colour and marks; every town style has a mark; labels placed without overlap.
- [ ] Commit.

#### Task 3.3: The map screen: zoom, pan, drag, select; Realms and Peoples views with legends
**Files:** `ui/screens/world_map.py`, `ui/input.py` (drag), `ui/gfx/worldview.py` (overlays, labels).
- [ ] Tests: wheel zoom keeps the point under the mouse; drag pans; click selects, Enter travels; views and legends.
- [ ] Phase verification, commit, push.

### Phase 4: Towns

#### Task 4.1: Sizes and the town package
**Files:** create `realmwalker/world/towns/{__init__,style,layout,buildings,props}.py`, `data/towns.json`; modify
`world/local.py` (variable sizes; settlement maps from the package), `game/people.py` (no fixed map size), every user
of the map's size; settlement population curve and great cities (generator, sites.json).
- [ ] Tests: every kind and size builds; connected; doors reachable; entry walkable.
- [ ] Commit.

#### Task 4.2: Things in towns (terrain, pictures)
**Files:** `data/local_terrain.json`, `data/sprites.json` terrain, `tools/tile_art.py` (furniture and props),
`tools/build_tiles.py` (picks from the pack: statues, fountains, torches, banners, walls, floors), rebuilt
`assets/tiles`, `ui/gfx/localview.py` (lights from torches, lamp posts, braziers).
- [ ] Tests: every terrain has a picture; lights glow at night.
- [ ] Commit.

#### Task 4.3: Styles: organic, grid, medina, camp, kremlin, terraces, plaza, longhouse, burrows
**Files:** `world/towns/layout.py`, `buildings.py` (shapes, rooms, furniture), `ui/gfx/roofs.py` (roofs and walls
per style: flat, dome, onion, felt, stepped, longhouse, round, courtyard).
- [ ] Tests: each style builds for every size; buildings have rooms and furniture; looks per style.
- [ ] Commit.

#### Task 4.4: Dwarven holds and elven groves
**Files:** `world/towns/layout.py` (hold, grove), `ui/gfx/localview.py` (underground light for holds),
`game/state.py` / `ui/map_render.py` (no daylight inside holds).
- [ ] Tests: a hold is lit the same at noon and midnight; a grove has giant trees and moonwells.
- [ ] Phase verification, commit, push.

### Phase 5: People

#### Task 5.1: Many more townsfolk, new trades
**Files:** `data/people.json` (occupations, settlement_people by size), `data/dialogue.json` (greetings per trade),
`game/people.py` (populate by population, lazy descriptions), `game/people_ai.py`.
- [ ] Tests: counts by size; every trade has words; lazy descriptions appear when looked at.
- [ ] Commit.

#### Task 5.2: Days, paths and walking
**Files:** create `realmwalker/game/townlife.py` (schedules, goals, paths, steps, swaps); modify `game/people.py`
(update_positions/wander replaced), `game/state.py` (`tick_town`, bump = squeeze past, `t` talks).
- [ ] Tests: people reach their posts; nobody overlaps; doors; crowds pass; bump does not talk; t talks.
- [ ] Commit.

#### Task 5.3: The town clock
**Files:** `ui/screens/game_screen.py` (real-time ticks while on a settlement map), `config.py` + settings screen
(Time in towns), `app.frame_timeout`, help text, action bar (Talk).
- [ ] Tests: ticks advance time and move people; paused under other screens; setting respected.
- [ ] Commit.

#### Task 5.4: More happening; dress and arms by people
**Files:** `data/people.json` (barks, street happenings), `ui/gfx/localview.py` (words over heads),
`tools/figure_gear.py` (new garments), `data/sprites.json` figures "cultures", rebuilt tiles, `ui/gfx/dolls.py`.
- [ ] Tests: every culture's outfit resolves to drawn garments; barks shown and paced.
- [ ] Phase verification, commit, push.

### Phase 6: Finish
- [ ] Autoplay learns the new things and checks new invariants; full suite; smoke test (new shots: a desert city,
  a hold, a grove, the map views); autoplay both modes; PROGRESS.md, CLAUDE.md, README_FRIENDS.txt, memory; push.
