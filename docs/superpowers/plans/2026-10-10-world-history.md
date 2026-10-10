# Deep History Implementation Plan

> **For agentic workers:** implemented natively in one long unattended session (Anton's standing preference: no
> check-ins). Steps use checkbox (`- [ ]`) syntax for tracking. If the session is summarised, re-read this file and
> `docs/WORLD_HISTORY.md`, then continue from the first unticked task.

**Goal:** worlds whose present is the outcome of a lived, DF-style history (peoples, families, wars, beasts, faith,
artifacts, eras), readable in a Legends book and felt in play, without breaking any existing system.

**Architecture:** a new pure-logic package `realmwalker/world/ages/` simulates the years on the generated land, using
the existing `Settlement`, `Site`, `Faction` and `Figure` objects directly, steered by fated and doomed spots;
`present.py` turns the end state into today's world in the shapes the rest of the game already reads.

**Tech Stack:** Python 3.12, numpy, tcod (pathing), pytest; data in `data/*.json` validated by `data/schemas.py`.

**Spec:** `docs/WORLD_HISTORY.md`

## Global Constraints
- Logic never imports UI; one seeded RNG per world (`rng.child(...)`), no `random` module calls.
- Numbers and words live in `data/history.json` (schema in `realmwalker/data/schemas.py`).
- Arrays indexed `[x, y]`; LF line endings (check `tr -cd '\r' < file | wc -c` after scripted edits).
- `Settlement.id` == its index in `world.settlements`; `Site.id` == its index in `world.sites`.
- Older saves must still load (new dataclass fields have defaults); a crash is never acceptable.
- World generation: large world < 30 s (test), medium target < 8 s, small target < 3 s.
- Milestone done = all tests pass + smoke test + autoplay clean in both AI modes; commit; update `docs/PROGRESS.md`;
  push the branch `world-history` to origin.

## Review Focus
- A history in which a fated place is razed: it must be rebuilt (and named anew) before the present.
- A realm whose whole royal line dies out in a war or plague: succession must still give a living leader.
- Figures referenced by events after renumbering doomed places into ruins: every reference must still resolve.
- A beast whose lair site is also wanted by a tribe, cult or gang: one site, one master (`Site.faction` or a lair).
- The 100-year and 1000-year history lengths: same guarantees as the default 250.

---

### Task 1: Data and model foundations
**Files:** create `data/history.json`; modify `realmwalker/data/schemas.py`, `realmwalker/world/tables.py`,
`realmwalker/world/factions.py` (Figure fields), `data/names.json` (much larger pools), `data/place_names.json`.
**Produces:** `tables.history` (dict); `Figure` fields `kind, mother, father, home, lair, job, cls, level, kills,
slayer, buried, spheres, deity, creature, regnal` (defaults); name pools of 60+ first names per sex and 60+ family
names per culture.
- [ ] Tests: `tests/test_schema_data.py` still passes; new `tests/test_ages.py::test_history_data_is_valid` loads
  `tables.history` and checks required keys; old Figure dicts (without the new keys) still load.
- [ ] Commit.

### Task 2: Spots — fated and doomed places
**Files:** modify `realmwalker/world/generator.py` (place doomed spots after today's; keep today's placement
unchanged; reduce random ruins by the doomed count; pass `spots` to the history); create
`realmwalker/world/ages/land.py`.
**Produces:** `Spot(sid, x, y, destiny, fated, score, cap)`; `land.make_spots(world, gen) -> list[Spot]`;
`land.neighbours(spots, radius) -> dict[int, list[tuple[float, int]]]`; settlements for doomed spots are appended to
`world.settlements` during the history and removed at the end.
- [ ] Tests: doomed spots are on passable land, spaced like settlements, not on today's places.
- [ ] Commit.

### Task 3: The simulation core and the people
**Files:** create `realmwalker/world/ages/__init__.py`, `sim.py`, `folk.py`, `words.py`.
**Produces:** `AgeSim(world, tables, rng, years, progress=None, spots=...)` with `run()`, `record(kind, values, *,
importance, factions, places, sites, figures, war, data) -> dict` (event with id and text), `alive` figure set;
`folk.birth/marry/die/age_year`, regnal numbers, death causes; progress `(year, figures, events, headline)`.
- [ ] Tests: determinism (same seed, identical events and figures); genealogy sanity (parents 14+ years older,
  no death before birth, no one older than their people allow).
- [ ] Commit.

### Task 4: Realms — origins, growth, grants, succession, rebellion
**Files:** create `realmwalker/world/ages/realms.py`; extend `land.py` (founding, growth, abandonment).
**Produces:** realms founded at the start (old human kingdoms, dwarven clans, elven realms), expansion onto spots,
feudal grants raising noble houses, succession by custom with regency and crises, free cities, proclaimed kingdoms;
ownership events (`founded`, `granted`, `taken`, `freedom`, `escheat`...) carry `data.owner`.
- [ ] Tests: every fated spot is founded and owned before the present; ownership replay equals today's owners;
  every line of rulers ends with a living leader and the dead before.
- [ ] Commit.

### Task 5: War
**Files:** create `realmwalker/world/ages/war.py`.
**Produces:** named wars with causes and allies; battles with commanders, numbers, deaths and slayers; sieges,
sacks, razings (doomed spots; fated spots only early and then rebuilt); peace treaties moving borders; veterans and
deserters for Task 8.
- [ ] Tests: a war has battles, battles have commanders and the dead have slayers; razed fated places are rebuilt.
- [ ] Commit.

### Task 6: The wild — tribes, beasts, heroes, old sites
**Files:** create `realmwalker/world/ages/wild.py`.
**Produces:** tribes that raid, burn and abduct; beasts (dragons, trolls, ogres, spiders, dire wolves, bears) with
lairs and kills; heroes who hunt them; barrows with buried kings and grave goods; towers with builders; caves with
their occupants over time; `politics["lairs"]`, `politics["tombs"]`.
- [ ] Tests: every living beast has a lair site that exists and nobody else holds; at least one dragon sleeps.
- [ ] Commit.

### Task 7: Faith and lore
**Files:** create `realmwalker/world/ages/faith.py`, `lore.py`.
**Produces:** god figures, churches with founders, temples (`presence`), saints, heresies -> cults, persecutions;
artifacts with makers and movements (`politics["artifacts"]` keeps `name, kind, site, bearer, found, fate` and adds
`maker, made, material, history, holder, place`); works (`politics["works"]`).
- [ ] Tests: every artifact is in exactly one place (a living holder, a settlement, a site, or lost); retrieve quests
  still find artifacts in sites.
- [ ] Commit.

### Task 8: Orders, eras and the present
**Files:** create `realmwalker/world/ages/orders.py`, `eras.py`, `present.py`; modify `realmwalker/world/history.py`
(generate_history runs the ages for new worlds; old worlds keep the told history), `realmwalker/world/generator.py`.
**Produces:** today's world: doomed places -> ruin sites with `politics["ruins"]` pasts; references remapped; counts
and required faction kinds ensured; laws, strength, colours, goals, relations; roles for figures; `dragons`,
`artifacts`, `founded`, `places`, `eras`; recent news.
- [ ] Tests: the whole existing suite (test_factions, test_politics updated where history is now real, test_world,
  test_adventure...), plus present-structure tests at all three sizes and all four history lengths; performance.
- [ ] Smoke test, autoplay both modes; commit; update PROGRESS; push.

### Task 9: The Legends book
**Files:** create `realmwalker/world/legends.py`, `realmwalker/ui/screens/legends.py`; modify
`realmwalker/ui/screens/chronicle.py` (open the book), `realmwalker/ui/screens/new_world.py` (history length, live
year counter and headlines while the ages are lived), title-screen saved worlds (read a world's legends).
**Produces:** `legends.entry(world, tables, ref) -> list[str]` (marked-up lines with links `<link=F12>...</>`),
`legends.index(world, tables, category, query) -> list[(ref, label)]`; a screen with categories, search, links,
back/forward.
- [ ] Tests: every category lists and every entry renders headless; links resolve; screens fit at all sizes.
- [ ] Commit; push.

### Task 10: The past in play
**Files:** modify `game/describe.py` (ruins and towns say their past), `game/people.py` (living figures placed as
townsfolk; real backstories), `game/dialogue.py` (ask about the history of a place), `game/people_ai.py` (facts for
the AI), `game/dungeon.py` (named beasts and barrow kings as bosses), `game/books.py` (real works), quests (avenge a
death; reclaim an heirloom).
- [ ] Tests for each hook; autoplay; commit; push.

### Task 11: The world keeps living, and polish
**Files:** `world/politics.py` (live events get ids; living heroes and beasts age and die), docs (PROGRESS,
CLAUDE.md, README_FRIENDS.txt), memory.
- [ ] Full verification; final push.
