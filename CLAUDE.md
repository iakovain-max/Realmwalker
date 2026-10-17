# Realmwalker — project guide for Claude Code

A grim, text-heavy open-world party RPG on D&D 5e rules, drawn with pixel-art tiles and figures over a text grid
(python-tcod + its SDL renderer; pictures are the only look); every word the player reads is written into the game.
**Version 1.0** (2026-10-03): pictures and the new interface are in (`docs/PROGRESS.md`, first entry). **The user is not a programmer**: explain progress in
gameplay terms, give Windows click-by-click steps when they must do something, never ask them to edit code.

- Source of truth for the design: `docs/DESIGN.md` (verbatim copy of the user's document).
- Status, decisions, known bugs, how to test: `docs/PROGRESS.md`. **Update it at the end of every session.**
- **Running in a cloud session** (Linux, no window)? Read `docs/CLOUD_HANDOFF.md` first: it says
  what can and cannot be verified there, what "done" means without a window, and how work reaches the user.

## Running things (Windows, from the project folder)

| What | Command |
|---|---|
| Play (what the user does) | double-click `Play.bat` (sets up `.venv` on first run) |
| Get the newest version and play | double-click `Update_And_Play.bat` (git pull, then `Play.bat`) |
| Run from a terminal | `.venv\Scripts\python.exe main.py` |
| Window smoke test (opens, tours screens, screenshots, exits) | `.venv\Scripts\python.exe main.py --smoke-test out.png` |
| Developer tools (once) | `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` (pytest-xdist, pypdf, pypdfium2) |
| All tests, in parallel | `.venv\Scripts\python.exe -m pytest -n 10` (about a minute; 10 workers, not all 16: never 100% CPU) |
| Quick tests while working | `.venv\Scripts\python.exe -m pytest -n 10 -m "not slow"` (mark long tests `@pytest.mark.slow`). Tests take worlds from `tests/worlds.cached_world` (kept in build/test_worlds while the world-making code and data are unchanged) |
| Autoplay bot | `.venv\Scripts\python.exe tools\autoplay.py --turns 3000` |
| Balance numbers (fights, cold, wounds) | `.venv\Scripts\python.exe tools\balance.py --runs 60` |
| What the enemy uses, and how fast it thinks | `.venv\Scripts\python.exe tools\arena.py` (`--creature wolf --runs 10`) |
| Rebuild the tile sheets (after changing tools/*_art.py, figure_*.py) | `.venv\Scripts\python.exe tools\build_tiles.py --pack <Dungeon Crawl Stone Soup Full folder>` (no `--pack`: downloads it) |
| Rebuild the sounds and the shipped music (after changing tools/build_sounds.py) | `.venv\Scripts\python.exe tools\build_sounds.py` (downloads the CC0 packs into build/sound_packs; `--no-music`: effects only) |

Milestone "done" = all tests pass + the game launches (smoke test) + autoplay ran clean.
Then commit, update PROGRESS.md, and stop for user feedback (unless the user said to keep going).

## How to work: fast, without losing quality (Anton, 2026-10-12)

- **Done = playable.** A rule is done when it is usable in play: the rule, its entry in `actions.options`, the
  enemy's and Auto's use of it, the battle screen, and one test in a real fight. Never tick a rule that nothing calls.
- **Heavy checks once per part, side by side** (Anton, 2026-10-13: more load is fine, never 100% CPU). While
  building: the tests for what you touched (`pytest -n 10 tests/test_x.py`). Before a merge, all three together in
  the background: the full suite (`-n 10`, it runs the arena coverage test), autoplay (its own temporary home) and the
  smoke test (`--home build/smoke_home`). Run `tools/arena.py` by hand only when tuning tactics.
- **The relay** (docs/expansions/RELAY.md, 2026-10-17): START and STOP buttons; one builder session at a time holds
  the baton (`tools/relay.py`, build/relay.json), beats after every commit, and at the end of its part arms the other
  builder task to fire a minute later; a part cut off by a usage limit resumes right after the reset; releases do not
  stop the work; a safety net fires every three hours only to re-arm a dropped baton.
- **Helpers for bulk data** (book tables, items, monsters, spells, codex marking): two or three subagents at once on
  a cheaper model (`model: "sonnet"`), each with a precise brief (its entries, the schema, one finished example, the
  book pages, numbers checked on page images); the main session owns the kernel, joins the pieces and reviews.
- **Edit with the Edit/Write tools.** Scripts only for mechanical changes across many files, written to a file with
  Write first (shell heredocs here mangle quotes and backslashes).
- **Read narrowly**: `grep -n` and small line ranges, guided by the code map below; do not page through big files.
- **One part per session.** When a part is merged, update `docs/expansions/STATUS.md` and hand over: a fresh session
  re-reads only the notes, while a long one re-reads everything it has seen at every step, and a summarised one loses
  detail. A part that took under 30 minutes goes straight on with the next (docs/expansions/RELAY.md D.5).
- **The fresh review stays** before each merge, as a short checklist pass against `docs/EXPANSIONS.md` §5.2.

Code map of the two biggest files (by section; search for the `# ---` headers):
`rules/combat.py`: AttackOption, Env, Zone, Token, Fighter (identity, where, numbers, state), Battle: decisions,
helpers (gap, feet, team), placing, start (Study), Search and Ready, turn engine (start/end of turn, crowding),
light and sight, moving (move_tree, walk, leaps, objects, flying, falling, grapples), the action economy, attack
options, resolving attacks, morale, party actions (Help, shove, grapple, Influence, items), items and abilities,
spells, concentration, zones, bookkeeping.
`rules/tactics.py`: caution and roles, wits and targets (smarts, importance, focus, target_weight), take_turn,
monsters (_monster_turn, flying up and down, _fight, best_plan, _value, _instead_of_a_blow, approach, breaking
through, flee, creature magic, spell choice, keeping distance), party members on Auto (_party_turn, abilities by
what they do, healing the fallen, casting).

## Folder map

```
main.py                    entry point (crash-safe; --smoke-test, --home)
config.json                game-level config: the debug console switch
realmwalker/
  app.py                   App: config, data, sound, screen stack, error recovery (no window)
  paths.py                 where files live (game files in its folder; player files in %APPDATA%\Realmwalker)
  config.py                GameConfig (config.json) and Settings (player prefs, settings.json)
  core/                    rng (the one seeded RNG), dice, schema (validation), textgen (text templates), logs
  data/                    registry.py loads + validates data/*.json; schemas.py describes each file
  world/                   generator (terrain, rivers, climate, biomes, towns, roads), local maps, calendar,
                           tables (numpy lookups from data), model (World + save-friendly dataclasses)
  world/towns/             a settlement's close-up map, laid out the way its people build (data/towns.json): plan
                           (streets, plots, buildings with rooms and furniture, every door reached), layouts (one per
                           people: organic, grid, medina, camp, kremlin, terraces, plaza, longhouse, hold, grove,
                           burrows, stockade)
  game/                    state (player, party, actions, travel, time; street life, the weather turning,
                           landmarks), save (versioned zips), log, describe,
                           encounters (road trouble, local-map inhabitants), fight (start/finish battles, loot,
                           prisoners, rest), vision (field of view), survival (the body as time passes: weather,
                           eating, drinking, water sources, death), care (treatment, healing magic), camp (fire,
                           cooking, foraging, hunting, fishing), events (travel events, news, pedlars),
                           people (townsfolk: making, placing, impressions, memory), townlife (their day: schedules,
                           walking, squeezing past, words in passing, the town clock), dialogue
                           (conversations, whitelisted outcomes), town_words (a town's description, inn names),
                           economy (shops, prices, trade, haggling), services (inns, healers, temples, smiths,
                           stables, animals, labour), reputation (standing, deeds and their ripples, joining,
                           titles), law (crimes, witnesses, the watch, sentences, jail, disguise), law_talk (law and
                           faction choices in conversations), news (what the player hears), notices (town boards),
                           companions (hiring, wages, loyalty, orders, desertion), magic (copying spell scrolls),
                           dungeon (going under, light, traps, locks, chests, hoards), treasure (what is in them),
                           gear (what items are for: wear, mending, honing, snares, evenings, prayer, prisoners),
                           magic_items (making, identifying, curses, names), quests (work from templates tied to
                           real things, the journal), dragons (lairs, tribute, killing one), books (maps, histories,
                           lore, letters), death (the obituary and what the world keeps), interlude (the weeks that
                           pass before a new life in an old world)
  rules/                   character (Character + Sheet: derived numbers), items, inventory (equip rules), creation,
                           looks (how people look: options per people, random, read from words, written as words),
                           combat (Battle: D&D 5e combat on a grid), grid (the battlefield: distances, sight, cover,
                           areas, paths), tactics (how the enemy and Auto fight), creatures, spells, wounds, progression,
                           body (needs, body heat, wetness, exhaustion), health (blood, pain, infection, healing,
                           injuries, diseases, treatment, drink, poppy), describe (cards: statuses, creatures, options,
                           items, the log's rolls)
  rules/engine/            the rules kernel (Expansion 1): conditions (2024, data/conditions.json), query (every
                           derived number), traits (data/traits.json definitions), events (hooks + dispatcher),
                           handlers/ (Python by id), effects (spell ops), durations (endings by turns), check (start-up)
  world/weather.py         weather as a deterministic function of seed, place and time (moving fronts)
  world/dungeon.py         dungeon levels under a site: styles, rooms, caves, doors, secrets, traps, chests
  world/factions.py        factions and figures (model, generation, territory map, relations, laws)
  world/politics.py        the politics engine: succession, wars, sieges, plague, raids, cults, gangs (history + live)
  world/ages/              the lived history (2026-10, after Dwarf Fortress): sim (the year loop, events), land
                           (fated/doomed places), folk (families), realms (rulers, grants, succession), war, wild
                           (tribes, beasts, heroes, barrows, towers), faith, lore (artifacts, works), orders, eras,
                           present (what is left becomes today), words (names, event text); design docs/WORLD_HISTORY.md
  world/history.py         the chronicle (told by named ages) and remember() (history written while you play)
  world/legends.py         the Legends book's pages and lists (logic): every person, realm, place, war, beast...
  world/news.py            news items and how they travel along the roads
  ui/                      window loop, fonts (tileset built at runtime), input, markup, widgets (Canvas), hud (side
                           panel, log, action bar), tooltips (cards drawn beside what is pointed at), colors, screens/
  ui/gfx/                  the pictures: scene (picture commands, layers), gpu (draws them with SDL), atlas (the tile
                           sheets), theme (panels, buttons, bars), typefaces, localview (close-up maps: tiles, light,
                           people, followers), roofs (buildings: roofs, front walls, doors, lit windows), worldview +
                           paint (the overworld as a pixel map on parchment, painted in chunks on a thread), dolls
                           (people as stacked pixel-art layers), battlefx (the battle mat: field, figures, highlights,
                           spell areas and animation), scenes
                           (camp, figures, busts, wound marks), weatherfx (rain, snow, fog), titleart
  audio/                   sound (presentation, like ui/; logic never imports it): engine (Audio: effects by name,
                           one interface sound per frame, music by mood, volumes), bank (effects from assets/sounds),
                           music (the mood folders, the player on its own thread, crossfades, loudness remembered),
                           backend (SDL through tcod, or silent), cues (a fight's events -> sounds, music by foe),
                           watch (game.cue, a level gained, money, gear), levels (BS.1770 loudness, numpy only)
data/                      ALL game data as JSON (names, fallback text, ... later races, items, creatures)
assets/fonts/              DejaVu Sans Mono, Cinzel, EB Garamond, Grenze Gotisch + licences
assets/tiles/              sheet_*.png + tiles.json, BUILT by tools/build_tiles.py (commit them; the game never builds)
assets/sounds/, music/     effects (16-bit mono WAV) and the shipped tunes (OGG, by mood folder), BUILT by
                           tools/build_sounds.py from CC0 packs (Kenney, OpenGameArt, RandomMind) + CREDITS.txt; commit
music/ (project root)      the PLAYER's own music, by mood folder; made by the game, ignored by git
tests/                     pytest suite (headless)
tools/                     autoplay.py, balance.py (the design's targets), arena.py (every creature against a party),
                           build_tiles.py (+ tile_art.py: things drawn in code; figure_art.py: bodies; figure_gear.py:
                           clothes, armour, hair, hats, weapons, shields), build_sounds.py (effects and music)
```

## Rules of the codebase

- **Logic never imports UI.** Simulation code (world, rules, combat...) must be testable without a window.
  Screens call into logic; logic never calls screens.
- **One seeded RNG per world** (`core/rng.py`). Use `rng.child("purpose")` for independent streams.
  No `random` module calls in game logic. UI-only randomness uses `app.ui_rng`.
- **Data-driven.** Numbers and content live in `data/*.json`. Every data file has a schema in
  `realmwalker/data/schemas.py` and is validated at startup; problems show on a friendly screen.
- **Every word is written into the game.** Text comes from built-in words (data/*.json, `core/textgen` templates);
  "AI" in this codebase means only the game's own tactics. Text a player meets once (a town's description, an
  obituary, a chronicle) is written the first time it is needed and kept in the save. Where a player reads the same
  kind of text often, keep enough variants (`tests/test_text_variety.py` floors are the minimum).
- **Never make the player wait.** Long work runs in the background (the world map is painted on a thread).
- **Never crash.** App wraps every screen call; errors go to `logs/errors.log` and a friendly message.
  Don't swallow errors silently in logic — let the App boundary catch and report them.
- **Text colours** via markup: `"<danger>bleeding</>"`; palette names in `ui/colors.py`.
  Always `markup.escape()` text the player typed or the world made (names, deeds).
- Screens: subclass `ui/screens/base.Screen`; implement `render(canvas)`, `handle_key(ev)`,
  `autoplay_keys()` (sensible keys for the bot). Register clickable areas with `canvas.hit()` / `canvas.button()`.
- **Arrays are indexed [x, y]** (shape (width, height)) everywhere, matching tcod consoles (order="F").
- Saves store id lists (biome_ids, terrain_ids) next to index arrays so data files can change without
  breaking saves; always go through `GameState.remap_for()` / `_biome_remap` when reading them.
- Saves may break (Anton, 2026-09-26 and the expansion plan): there are no migrations and no code for old saves or
  old worlds. When what a save holds changes, bump `game/save.py` FORMAT_VERSION: a save of any other format is
  refused by `_check_format` with a friendly "Could not load ... The files are still there, untouched." box. Say so in
  the commit and the release notes, so he knows to start a new world. Never a crash, never a deleted file. Keep the id
  lists beside index arrays (`remap_for`, `_biome_remap`): they let an ordinary data change leave a save readable.
- The autoplay bot checks game invariants (`tools/autoplay.py`); add checks there as systems are added.
- Time: `GameState.pass_time(minutes, activity)` ("walk", "rest", "sleep", "fight") runs `game/survival.tick` in
  30-minute chunks (body, health, eating/drinking, death). Tests about travel alone can set `game.survival = False`
  and monkeypatch `encounters.encounter_chance`, `events.event_chance` and `GameState.lost_dc`.
- Townsfolk live in `world.npcs` / `world.towns` (saved with the world). A town is filled by
  `people.populate_town` on first entry (or `prepare_town` ahead of arrival): as many as data/people.json
  settlement_people "folk" says, a trade for each kind of building ("workers"), homes in beds. Walking into someone
  squeezes past them (`townlife.squeeze`; a warden at a gate, `flags["stays"]`, will not budge); talking is t, Enter
  or a click (`GameScreen.talk` sets `game.talk_to`; the game screen opens the conversation). Conversation
  outcomes stay in `dialogue.OUTCOMES`.
- Towns (2026-10-11, Anton: "way more varied ... bigger ... way, way more citizens ... make the NPC move on their
  own"): `world/towns` lays out each people's towns (data/towns.json styles: layout, street stuff, looks of roofs,
  walls and shapes, things in the streets, their own words for arriving); `Plan.connect` lays a path to any door that
  cannot be reached (or takes the building down); tests/test_towns.py checks every style and size (doors reached,
  nobody shut in by furniture, the way in walkable). The biggest cities are `Settlement.great` (generator
  `_great_cities`, data/towns.json "great"). A dwarven hold's map has `meta["underground"]` and `meta["open_below"]`:
  `LocalMap.under_rock(x, y)` is true in its halls (no sun, no weather, the same light at every hour) as in dungeons.
  Buildings of other peoples are drawn by `ui/gfx/houses.py` (flat, dome, onion, round, tree, mound, court, long
  turf), the rest by `roofs.py`.
- Townsfolk live their day (`game/townlife.py`, data/people.json "days" by trade): every STEP_SECONDS of the world
  they take a step towards where their day has them (paths found once and kept, not saved), swap in narrow ways, and
  call out now and then (data/people.json "barks", shown over their heads, behind Text detail). `catch_up` runs after
  anything that passes time in a town; after a long while `settle` puts everyone where they should be. On a town's
  map the game screen's town clock passes STEP_SECONDS every half second (`GameState.town_tick`; Settings, Time in
  towns: flows or waits); it stops under any other screen. Processions (townlife.HOLY_DAY) and evening brawls (the watch breaks them up) are townlife too. You swap only with someone coming the other way or standing still. Dress by people: data/sprites.json figures "cultures". The generator gives each people a share of the towns (`_people_shares`); a realm founding in another people's country mostly settles that people (history.json peoples_change colonists).
- Factions live in `world.factions` / `world.figures` (saved with the world); a settlement's `owner` is the
  faction holding it, its realm is `factions.top_liege(owner)`. After changing holdings call `factions.touch(world)`
  (territory cache). Player standing, crimes, bounties and heard news are in `game.renown` (saved with the character).
- Deeds go through `reputation.deed()` (standing, ripples by relation, news); crimes through `law.commit()`
  (witnesses, reports, bounties, arrests). Arrests and sentences are pending states (`game.arrest`,
  `game.sentence`) opened by `GameScreen._open_event_screen()`.
- `world/politics.Politics` moves the world while you play (`politics.tick` from `pass_time`, a week per step, with
  consequences); the years before play are lived by `world/ages`. Every event becomes news via `world/news.add`; the
  player hears it through `game/news.hear`.
- Level-ups add hit points and features at once; choices wait in `Character.pending` (`rules/progression`:
  `options`, `resolve`, `auto_resolve`). Pass `auto=True` to `award_xp` where nobody can choose.
- Companions are ordinary `Character`s in `game.party[1:]` with a `companion` dict (loyalty, wage, values, order,
  npc id); `game.waiting` holds those told to wait. When the player does something a companion might care about,
  call `companions.react(game, "<tag>")`; tags are matched against data/companions.json values and wants.
- Dungeons live in `world.local_maps` under the key `"x,y/level"` (`world/dungeon.get_dungeon`), with `features`
  {(x, y): trap/lock/chest/secret/captive} and `meta` {site, level, depth, style, rooms, hidden, boss, name}.
  `game/dungeon.py` drives them (descend/ascend, light from `game.lit`, search, unlock, bump, chests, the hoard).
  A level is built and populated once and then kept in the save.
- Magic items: `Item.magic` {rarity, kind, props, attune, identified, cursed, curse, title, story, source, value,
  artifact props, sentient, suppressed}; which properties work is `rules/magic.active(char)` (attunement:
  `Character.attuned`, three at most); effects are read through `rules/magic.total(char, kind, **match)`, `traits`
  (kernel trait ids) and `flag`. Code picks the properties within a budget (`game/magic_items.make`, `make_artifact`,
  `make_sentient`); built-in words name it and tell its history from the world's past. Charges come back at dawn
  (`magic_items.tick` from `pass_time`); a sentient thing hears `magic_items.notice(game, tag)`.
- Treasure (DMG 2024, data/treasure.json): `game/treasure` (hoards by CR and theme, the 20 random tables, stashes);
  pocket money from the MM treasure on stat blocks (`rules/creatures.individual_treasure`). Encounters:
  `rules/encounter` (XP budgets, `counts_for`, attitudes, travel pace; `spawn_group(budget=)`); `PlayerState.pace`.
- Quests (`game/quests.py`) are plain dicts in `game.quests` (saved with the character) made from
  `data/quests.json` templates and tied to real things: a faction, a site, a settlement, an npc, an artifact.
  Offers live in `Town.flags["offers"]` (one per person, a new one about once a week). Progress is noticed where
  it happens: `quests.on_battle` (from `fight.finish_battle`), `on_arrive` (overworld), `on_arrive_dungeon` and
  `on_chest`/`free_captive` (from `game/dungeon.py`), and the conversation choices in `quests.QUEST_CHOICES`.
  Rewards go through `reputation.deed`; failure through `quests.daily` (from `pass_time`). The game always shows
  the terms.
- Dragons: records in `world.politics["dragons"]` (made by `world/ages`, wild and present; one always sleeps).
  `world/politics.dragon_wakes` burns or taxes a village while you play; `game/dragons.py` has the warning signs,
  the descent warning and `on_battle`, which marks one slain for good (news, history, fame, tribute lifted).
- Lived history (2026-10, Anton: "the same kind of living world with long history and unique characters as Dwarf
  Fortress"): `world/ages` lives the years at world creation (`WorldOptions.history`, 100/250/500/1000; numbers and
  words in data/history.json). Today's settlements are *fated* spots (placed as before); the generator also leaves
  *doomed* spots that the ages turn into ruins (`politics["ruins"]` keeps each one's past). Every change of a
  settlement's owner is in the history's ledger (`event["data"]["owners"]`, via `ages/land.set_owner` and, while you
  play, `Politics.set_owner`): replaying it gives today's map (tests and autoplay check this). Figures carry family and
  place refs ("S12" settlement, "X5" site in `home`, `died_at`, `buried`), `kills`/`slayer`, `kind` (person, beast,
  dragon, god). `politics` also keeps `places`, `lairs` (site -> living beast), `tombs`, `towers`, `works`, `eras`,
  `next_event`; events have ids (`history.remember` writes one in play). `game/past.py` brings it into
  play (Look, conversations, heroes at inns, named beasts and barrow kings as bosses, the clear_lair_beast work,
  haunted battlefields from `politics["scars"]`, blood feuds from `politics["grudges"]` and the vendetta work, a lost
  artifact as a locked chest on its site's deepest level via `on_arrive_dungeon`/`on_chest`); `world/ages/ties.py`
  roots a new character's background in it; live beasts come down via `Politics.beast_comes`.
  `ui/screens/legends.py` is the Legends book (b in the News screen; Legends for a saved world). Ages are
  named against the world's own usual (`ages/eras.Judge`). After changing war or era numbers, measure wars per century
  at all four lengths: long histories once went silent after year 700.
- Death: `game/death.die(game)` writes the character into `world.politics["fallen"]` (chronicle, news, companions
  released) and the death screen shows `fallback_obituary` with the built-in obituary (`write_obituary`, data/
  fallback_text.json obituary) kept on the record. Nothing carries over to the next character except what the world remembers.
- A new character in a world that has been played runs `game/interlude.pass_the_years` first (real politics for
  three weeks to five months) and is shown what changed.
- Balance: `tools/balance.py` measures the design's targets (fights at level 1 and 3, a winter night, an
  untreated wound); `tests/test_balance.py` keeps them inside bands. Change combat, cold or bleeding numbers and
  run it before and after.
- The world's voice (street life in towns, companions talking on the road, the weather turning, night sounds,
  region and dungeon descriptions) is gated by `GameState.flavour(level)`, which reads the player's "Text detail"
  setting. Keep new flavour behind it.
- Faction rank: `reputation.rank` is `min(standing_rank, confirmed_rank)`. A promotion is confirmed by doing that
  faction's work (`quests.mark_trial` flags the offer, `reward` calls `reputation.confirm_rank`), or automatically
  when standing runs two ranks ahead (`reputation.tick`).
- Crafting at camp is data-driven (`data/camping.json` "crafts"); `camp.crafts(game)` lists what is possible here
  and `camp.make(game, id)` does it on a skill check.
- Items (2026-10-09, Anton: "make the items do something"): every gear, tool, focus and book item has a use, and its
  card says it. Data fields in data/items.json: `slot` "back" + `carry` (packs), `focus` (+1 spell attack/DC,
  `rules/spells.focus_bonus`), `impress` (`people.papers_impression`), `bonus.skills` (worn), `mends`, `pry`, `dig`,
  `washes`, `alarm`, `bind`, `bearings`, `sight`, `how` (where it is used), `use` keys hone/mend/snare/music/game/pray/
  scribe/throw (`game/gear.use_name`). Numbers in items.json "upkeep". Gear wears in fights (`gear.wear_from_battle`);
  thrown flasks are pseudo-spells in spells.json (`classes: ["item"]`, `thrown`) cast as "throw:<uid>:<spell>".
  A new item needs either a use or a `how` (tests/test_gear.py checks), and a picture (tools/build_tiles.py ITEMS).
- Screens added after v1: `ui/screens/legends.py` (the Legends book), `ui/screens/spells.py` (S),
  `ui/screens/journal.py` (j; Tab switches Work/People),
  `CraftScreen` in `ui/screens/camp.py` (m at camp), `ui/screens/interlude.py` (after a new character in an old
  world).
- Fair chances (2026-10, Anton: "too easy to randomly die"): outside a battle 0 hit points is down, not dead (traps
  call `fight.lie_senseless`; only a blow taking a whole life's worth below zero kills). `fight.finish_battle` passes
  the fight's minutes only after the downed have come round, been robbed or been left for dead (beasts that win roll
  `_left_for_dead`). Underground counts as sheltered and dark (`survival.sheltered`, `fight.battle_env`). Water from the
  sky is `survival.sky_water`; skins top up on the move via `survival.top_up`. Measure deadliness with a scripted
  "careful player" over many lives before and after changing combat, cold, encounters or wounds.
- Pictures (1.0): screens draw text cells as before and add picture commands with `canvas.under(...)` /
  `canvas.over(...)` (`ui/gfx/scene.py`: Batch, Sprite, Image, Rect, Lines, Text, Clip). Pictures are the only look
  (letters mode went in October 2026): `canvas.gfx` is always a GfxContext; headless (tests, autoplay) it is
  `ui/gfx.headless()`, which records every picture over the real tile sheets, so every screen's pictures run in every
  test. Box titles and headings are pictures: read what a screen says with `canvas.words()` (cells of every layer plus
  picture text), not only the console's cells. A PC that cannot start the renderer gets a clear message
  (`window.PicturesUnavailable`). Logic still never imports UI. Pictures live in `data/sprites.json` (validated):
  terrain, town walls, traps, map marks, and "figures" (colours, skins, hair, what each item looks like worn, outfits
  by trade, dressed creatures). New tiles: draw them in `tools/tile_art.py` (or a figure layer in `figure_gear.py`),
  rebuild with build_tiles.py, commit `assets/tiles`. Figures are 32x32; draw them at whole multiples or let
  `dolls.draw` scale them (it keeps pixels even). A rare item's look is `item.magic["look"]` {metal, cloth, emblem,
  glow}: `magic_items.look_for` picks it from the words of its name and story and from its powers.
- Looks (2026-10-10): `Character.looks` {build, skin, eyes, hair, hair_colour, beard, beard_colour, mark, paint,
  paint_colour, features {ears/tusks/horns/tail: option}, dye, cloak}, chosen on the creation Looks step; `appearance`
  is written from it by `rules/looks.describe`. Townsfolk and creatures have none stored: `looks.from_text` reads them
  from their words with a stable hash for the rest (`looks.of_npc`), and `dolls` draws from either. Options per people
  are data/appearance.json looks/races (`_default` for anything not written); body proportions, builds and colours are
  data/sprites.json figures (skins are real colours, drawn over grey). A new people needs nothing to work (human
  looks on a human body via `dolls.resolve_body`); its own body needs a `bodies` entry and a tile rebuild. Keep
  `tests/test_looks.py` green: every option must have a picture and a colour.
- Cards (Expansion 1 part E, docs/EXPANSIONS.md §4.15): `rules/describe.py` builds a `Card` (title, subtitle, icon,
  lines, footer) for anything pointed at; `canvas.hit(tooltip=)` takes words, a Card or a function making one (built
  only when shown, after 0.3 s); `ui/tooltips.py` draws it beside the thing. Every state a fight can produce is a
  `describe.Status` with an icon `status/<id>` (10x10, `tools/status_art.py`; `tests/test_cards.py` checks each has a
  picture and card words); a new status needs both. Rolls reach the log's tooltips through `Battle.dice_say` /
  `note_roll` (kept in `Battle.rolls` by line). Borrowed creature tiles pass `tools/adapt_art.py` in build_tiles.py
  (`--adapt-sheet` shows before and after); a spell's `fx` is its look (bolt, ray, cone, burst... the schema lists them),
  the cast event's `effect` what it does. Expansion icons: `tile_art.dlc_icons`.
- Animations go through `canvas.gfx.animate` (movement) and `canvas.gfx.ambient` (idle: water, smoke, weather), from
  the Animations setting; the game's state never waits for an animation.
- The rules kernel (Expansion 1, docs/EXPANSIONS.md §4.3; `rules/engine/`). Numbers go through one door:
  `query.attack_roll` (advantage/disadvantage with reasons; `Battle._adv_dis` wraps it), `query.save_roll`, `ac`,
  `speed`, `damage_taken` (immune/vulnerable/resist), `crit_range`, `crit_within`, `condition_immune`. The 2024
  conditions are data (data/conditions.json: includes, inactive, speed_zero, attacks/attacked, fails_saves, source
  rules...); a fighter keeps `conditions` {name: rounds or -1}, `sources` {name: fighter id} and `cond_ends`
  {name: ending} (`durations.give/remove/until/tick`: endings at the start or end of someone's turn, ended by damage,
  by concentration, or followed by another save). Traits and features are definitions in data/traits.json, keyed by
  creature trait id, race/class `rule` tag or feature id (`traits.of(f)`, `traits.of_char(char, tables)`): `modifiers`
  (attack/attacked/enemy_attacks/save/resist/crit_range/passive/ignores_zone/immune_condition, each with named `when`
  tests in `traits.WHEN`) and `hooks` (`events.emit(b, "attack_hit", actor=, target=, ...)`; handlers registered with
  `@handler("id")` in `engine/handlers/`; roles self/attacker/target/ally/any; the event's target and actor are asked
  first, then the order of battle). Spells are definitions: `spell["effects"]`, a list of ops run by
  `engine/effects.cast` (the op list is in its docstring); `rules/spells.py` reads them elsewhere (`ops`, `op`,
  `has_op`, `buff_of`, `heal_op`, `main_type`, `road_use`, `summary`). A new op, trait, `when` test, event or handler
  must be added to the code too: `engine/check.problems` reports unknown ones on the data-problems screen at start-up
  (and tests/test_engine.py runs it). Keep `battle.events` and their meaning (battlefx and audio/cues read them);
  a spell's `fx` names its look.
- Battles (grid, 2026-10-06, Anton's request; replaces the design's two ranks): a grid of 5-ft squares
  (`rules/grid.Field`, terrain indices from data/local_terrain.json; PHB distances, DMG corner cover, areas laid from
  a point of origin, Dijkstra paths that know opportunity attacks). `game/arena.build` makes the field: cut from
  `game.local` around the player and the band (dungeon, town, building, wild) or laid out from the biome on the road
  (road, stream, campfire); it places the party in its battle order (`Character.formation`, 5x5, row 0 = front,
  `arena.formation` / `set_cell`; FormationScreen from the party screen, f) and the foes by situation ("facing",
  "unaware", "ambushed", "camp"; line, arc for packs, block for road robbers, cluster, surround). A turn has movement
  (`move_left` feet), `action`, `bonus`, `reaction`; `do_move/do_attack/do_cast(point=)/do_dash/...` then `end_turn()`.
  Spells say `range`, `target` (enemy, ally, point, direction, self, all_allies...), `area` {shape, size}, `cast`
  (action/bonus/reaction), `concentration`; zones (web, fire, fog, ice, guardians) and tokens (spiritual weapon,
  guardian) live on the battle. Party members at 0 make death saves. `rules/tactics.take_turn` plays monsters and any
  fighter with `f.auto` (the screen's z, the balance tool and the tests use it). Every rule writes `battle.events`
  (move, attack, cast with its area, damage...), which `ui/gfx/battlefx.BattleBoard` turns into animation.
  Moving (2024): `grid.step_feet` is the one cost of a step (difficult terrain, crawling, climbing onto terrain
  tagged "climb", swimming terrain tagged "swim"; a Climb or Swim Speed pays no extra); `grid.paths` also leaps
  (`Fighter.jump`: half the Strength score standing, all of it after 10 feet of run) over water, chasms, fire and
  low things, and a leap in a path is two squares that are not side by side; `Battle.walk` makes the checks
  (`_may_go`: clearing a low thing, a river's current; landing on rough ground) with `Battle.check`.
- Tactics 2.0 (`rules/tactics.py`, Expansion 1 Part C): enemies and the companions' Auto choose from
  `rules/engine/actions.options` (pass `only=` kinds for speed) by `rules/engine/estimates` worth; a creature's
  `ai` {role, range, opens_with} in data/creatures.json says how it fights. The Auto's class abilities are read by
  what they do (`tactics._does`), never by name. `tests/test_tactics_coverage.py` (slow) fights every creature in
  `tools/arena.py`'s scenarios: every option chosen, nothing refused, no broken state, an enemy turn under 150 ms
  at the 95th percentile and never 400 ms (thread time). A new creature or spell must keep it green.
- Origins (Expansion 2 part B): `Character.species` (readable as `.race`; data/races.json keeps its name), `lineage`,
  `feats` [{id, choices}], `choices`; ability increases come from the background (`CharacterBuilder.bonus`), feats
  from the background and a human's Versatile (`origin_feats`, `feat_slots`). Feats are data/feats.json with a kernel
  trait each ("feat_<id>", handlers/feats.py); `rules/feats.py` grants them, picks defaults, and lists innate spells
  (a feat's or a lineage's, cast as "innate:<source>:<spell>" with no slot). Saves against a condition pass
  `against=` (Brave, Fey Ancestry). Creation runs calling, background, people, Origin, abilities (point buy, array,
  4d6)...; the smoke tour presses Enter through all ten steps.
- Feats (Expansion 2 part C): data/feats.json (categories origin, general, fighting_style; `prerequisite`, `choices`,
  `gives`, `offered: false` keeps one out of `feats.choosable` until its expansion). A level's "asi" choice lists
  feats too; a feat's picks wait as a "feat" choice (`progression.options/resolve`, Suggest by `feats.archetype`
  and feats.json "suggest"). Combat feats are kernel traits with handlers in `engine/handlers/general_feats.py`
  (once a turn: `mastery.once_a_turn`; check `used_this_turn` before asking); numbers where they are made
  (`Battle._weapon_option`, `spell_range`, `Sheet.armor_class`). `items.slots_for(item, char)` knows Dual Wielder.
  The fighter's style is a Fighting Style feat (no style field). A creature has a feat by its "feat_<id>" trait
  (data/creatures.json traits: the berserker, the guard, the orc warchief).
- The 2024 classes (Expansion 3 part B): class handlers in `engine/handlers/` (fighter, rogue, cleric, wizard); a
  feature's data may carry `choose` (an option kept as a feature: Divine Order), `expertise`, `savant` (a school's
  free spells) and `picks` (spells kept in `char.spells["mastery"|"signature"]`, cast without a slot through
  `spells.free_cast`); every cast goes through `Battle.cast`, which returns False when a foe's Counterspell stopped it
  (`Battle._countered`; the caller gives the slot back); `effects.cast(slotted=)` says whether a slot was spent.
- Spellcasting 2024 (Expansion 3 part C): prepared lists (`spells.prepared`, `fill_prepared`), higher slots
  (`spells.slot_choices`, `up_gain`), components (`spells.component_problem`, `spend_material`). Spell scrolls are made
  for every spell by `ItemTable.add_scrolls` (`scroll_<spell id>`, numbers in data/rules.json "spell_scrolls"); who
  reads one and how is `spells.scroll_reader` ("sure", "check", "device", "device_check" or None), the check before a
  scroll above you `spells.scroll_check`; in a fight "scroll:<uid>:<spell>" through `Battle.do_cast`, outside one
  `magic.read_scroll` (via `cast_on_road(scroll=)`). Potions of healing (items with `use.heal`) take the bonus action
  in a fight (`Battle.item_cost`), are drunk on the road by `care.drink_potion`, and the Auto uses them (`tactics._drink`).
- The spell catalogue (Expansion 3 part D): spells in data/packs/03_demigods_magics/spells.*.json, battle spells only
  (outside-a-fight ones come with Part E's systems, summons with F). What a spell leaves on a creature is a buff "mark"
  read in `rules/engine/marks.py` (its docstring lists every key; `engine/check` reports unknown ones and zone kinds):
  smites ready a `smite` mark that runs the spell's top-level `on_hit` on the next fitting hit; a spell's `again`
  becomes "<id>_again" (`spells.again_def`, class "again", no scroll), cast without a slot while the caster
  concentrates (`combat.again_spell`, target "bound" = the creature it was cast at); `minutes` keeps a spell out of
  fights; buffs take "$caster", "$dc", "$mod", "$spell", "$up", "$level", "$mult", "$foe_type" and `per_up`/`by_level`
  (lasting spells remember their slot: `spells.cast_at`). `tests/test_catalogue.py` casts every catalogue spell in a
  real fight and checks the Auto sees its worth (`estimates.spell_value`; NO_USE for reasoned exceptions).
  The second wave (D.2) added: fighters sent off the field (`Battle.send_away`/`bring_back`, state "away":
  Banishment, Blink, Resilient Sphere), the `dispel` op (`effects.held_spells`), auras shared with friends
  (`marks.share_auras`, run by `_follow_auras`), ground with a save and what a failure brings (`Battle._ground`,
  Zone `fail`/`rough`/`dark`/`held`), walls laid as terrain and restored when they end (Zone `was`), the Wind
  Wall (`Battle.wind_between`), `cast_kind` (Spell Breaker's bonus-action Dispel Magic); tests/test_wave2.py.
  The third wave (D.3, levels 6-7; the effects docstring's "third wave" part): `leap` (extra targets near the first,
  `effects.many`), dust and a lowered maximum (`Fighter.max_cut`), the three saves of stone (`Battle._stone_save`),
  the spell ward (`effects.warded`), shared temporary hit points (`effects.shares`), ground that heals friends (Zone
  `heal`), walls of ice, the forcecage (`send_away` "cage") and banishing for good (`Battle.send_off`), `by_hp`,
  `slay`, `lift` (Reverse Gravity: `Env.place` "underground"/"indoors" gives a ceiling), `one_of` (a die per
  creature), a summon's `on_hit`, `no_dispel`; marks dancing, aloft, spell_ward, truesight; tests/test_wave3.py.
  The fourth wave (D.4, levels 8-9; the effects docstring's "fourth wave"): Meteor Swarm's `spheres`
  (`Battle._more_spheres`), heal `full`/`pool`/`restore`, zones that `follow` their caster (Antimagic Field), `breaks`
  concentration (Earthquake), a prismatic wall with its `near` glare, a storm's `stages` (`Battle._storm_turn`), banish
  `escape` (Maze: `_maze_turn`), `time_stop` (`Battle._more_time`; `combat.TOUCHES` events end it); marks befuddled,
  foresight, holy, immune_damage. Wish: picking it opens a list (`BattleScreen._open_wish`): copies are cast ids
  "wish:copy:<spell>" (`Battle.wish_options`, `_cast_wished`: its level 9 slot, no components, no stress); the
  "wish" spell itself is Instant Health with `stress` (`spells.wish_stress`: effects wish_stress until a long rest,
  wish_strength hours of Strength 3, spells["wish_lost"]; `spells.strain` hurts every later casting, in a fight and
  on the road); tests/test_wave4.py.
- Spells outside battle (Expansion 3 part E): a spell used only outside a fight has `road_only` (or `minutes`:
  `spells.out_of_battle`, never offered in one) and an op {"op": "road", "does": one of `spells.ROAD_USES`} done by
  `game/spellwork.py` (food, water, purifying, the feast, curses, Regenerate, Gentle Repose; wards on the camp:
  `Camp.wards`, read by `fight.rest` and `survival.environment`); `magic.cast_on_road` spends the slot and passes the
  casting time. Return from death is `game/revival.py`: `game.fallen` (bodies carried, saved), `fall` (kept or buried),
  `raise_body`, `save_leader` (a companion calls the leader back), `auto_revive`; the revive op's `within_days`, `toll`
  (`health.DEATH_TOLL`, down one a long rest), `closes`, `regrow`, `cures`, `species: "new"`. A raised maximum is the
  `max_up` op (`spells.raise_max`/`lower_max`, `effects["spell_hp:<id>"]`, lowered when the spell ends). Companions
  act on their own through `spellwork.before_rest` and `conjure`. Tests: tests/test_spells_outside.py.
- The body on the move and travel by magic (Expansion 3 E.2): a lasting spell's buff is read outside a fight too:
  `rules/spells.SHEET_KEYS` are the sheet's (darkvision, speed, skills {skill: n}, check_adv: +5 on the best ability,
  carry) and the world's (steed, servant, water_walk, water_breathing, wind, ethereal, pathfinding: `game/waymagic.
  everyone`/`anyone`, `spells.lasting_flag`/`lasting_number`); light, see_invisible, climb/swim (true = the Speed),
  leap, mist and feigning are the battle's (rules/engine/marks.py lists them). `GameState.magic_crossing` carries the
  party over water and wind (`step_minutes`; `waymagic.ashore` when it ends out there); `GameState.pace` is never below
  a walker's unless everyone is borne by magic. Travel spells have target "place" (`waymagic.places`, Place objects on
  the Spells page) and op road `does: "travel"` with `how` in `spells.TRAVELS` (Teleport's 2024 table by familiarity,
  circles, Word of Recall's sanctuary `effects["recall_sanctuary"]`, plants, the planar three until Expansion 26, Arcane
  Gate to a dungeon's stairs); a lasting spell's `outside` (`spells.OUTSIDE`: disguise, path) runs
  `waymagic.after_lasting` as it is cast. Feather Fall is cast by itself (`Battle._feather_fall`, `dungeon.
  feather_fall`); `lift` has `gentle` (Levitate); `undark` ends low darkness (Daylight); zone "lights" (Dancing Lights);
  a teleport op's `near: "tree"` (Tree Stride); `camp.chore` is a chore's time. Tests: tests/test_spells_road2.py.
- Finding and seeing, asking the powers, talking (Expansion 3 E.3): road ops `does` sense/locate/scout/summons/ask
  (`game/divining.py`) and speak/send/read (`game/speech.py`), each with its `what`/`how`/`with` in
  `spells.E3_KINDS` (checked at start-up); `spellwork.DIVINING`/`SPEECH` send them there. A spell aimed at something
  chosen lists `divining.Subject`s on the Spells page (`spellwork.subjects` via `magic.road_targets`). A battle spell
  with a use outside a fight says `road_too` (Detect Thoughts: "read"). What is sensed on a close-up map is
  `game.sensed` (`divining.mark`/`marks_here`, not saved; drawn by localview as `mark/sensed_<kind>`); a chest's
  contents are settled by `dungeon.fix_contents` (kept in its feature until opened). The answers come from the world
  as it is (`divining.omen`, `questions`, `_work_truth`: a work's hidden side through `quests.reveal`). Repeats before a
  long rest: `char.uses["omen:<spell>"]`; Contact Other Plane's failure `char.uses["addled"]` (no casting,
  incapacitated in a fight; cleared by `progression.long_rest`). The language rule on the road is
  `speech.talk_problem` (from `fight.encounter_talk_dc`: stat block languages against Common and the party's; buffs
  tongues, comprehend, beast_speech). Drawmij's bound sapphire has the tag "summons:<uid>" (`gear.use_item` crushes it;
  `divining.taken` from robbery and confiscation). `speech.remember_the_dead` (finish_battle) keeps `game.fresh_dead`
  for Speak with Dead; Dream's nightmares wait in `renown.flags["nightmares"]` (`speech.nightmares_at_the_start` in
  start_battle). Buffs: linked (no surprise while two are linked), sense_thoughts (feet: `Battle.thinks`, `can_see`);
  `effects` forewarned (a band is seen first), forage_tip, hunting_tip. Tests: tests/test_spells_road3.py.
- Minds, illusions and the small arts (Expansion 3 E.4): road ops `does` mind/illusion/art (`how` in
  `spells.E4_KINDS`) are `game/glamour.py` (through spellwork's door, Subjects as in E.3: a person near, a kind of
  creature, a party animal, a far town, a thing carried or a body). A talk takes no time, so a minute's spell is a
  time window: `npc.flags` charmed_until / enthralled_until / geas_until (+ `renown.flags["geased"]`, soured by
  `glamour.tick` from spellwork.tick), `renown.flags` distraction {settlement, until, minus}, booming, antipathy {how,
  kind, until, dc}, script_until, warm_meal. Read by the rest: `glamour.charmed` (dialogue attitude), `cha_roll`
  (Glibness: dialogue, bribes, disguise kit), `watcher_minus`/`enthralled`/`unseen` (law: witnesses, thefts, creeping,
  the watch), `scripted` (gate search, papers), `hidden_thing` (robbers, confiscation; item tags "masked:<until>",
  "sequestered"), `on_meeting` (encounters: Antipathy/Sympathy), `awake_animal` (night visitors, rustlers). Lasting
  buff keys glib, unnoticed (Mislead, Invisibility), disguise, nondetection (Battle.thinks); disguise spells say
  `"disguise": "dc"` (waymagic.after_lasting); camp wards decoy, mouth, veil (`spellwork.ward_minutes`: rounds or
  `days`). Tests: tests/test_spells_road4.py.
- Locks and stone, weather and land (Expansion 3 E.5): road ops `does` lock/mend/hand/make/stone/chest/weather/plants/
  wave are `game/stonework.py` (kinds in `spells.E5_KINDS`). Arcane Lock's doors are `door_locked` with feature
  `arcane` (the party steps through: `stonework.through_own_lock` from `dungeon.bump`); inn rooms in
  `renown.flags["arcane_rooms"]` (services._night). Knock in the cells: `law.attempt_escape` (+10, a slot). Mage Hand:
  `flags["mage_hand"]` read by `law.steal_from_shop`. Creation's things carry the tag "conjured:<minute>" (vanish in
  `stonework.tick`; `economy.sell_price` refuses them). Passwall's cells and their old ground are in
  `lm.meta["passwall"]` (closed by `stonework.on_step` from `dungeon.on_step`). Leomund's Secret Chest: items tagged
  "ethereal" weigh nothing (`ItemTable.weight`), cannot be worn (`inventory.equip`) or sold, are `glamour.hidden_thing`;
  coin in `flags["secret_chest"]`; the replica's `use.recall` calls it back. Control Weather is `flags["weather"]`
  applied in `survival.weather` (`stonework.held_weather`); Control Water the lasting key `part_water`
  (`GameState.magic_crossing` "parted"); Move Earth the camp ward "earthworks". Plant Growth is a battle spell with
  `road_too: "plants"` and `road_minutes` (Enrichment: `flags["enriched"]`, camp foraging doubled); its Overgrowth is
  zone "overgrowth": `Field.zone_thick` (20 feet a square in `grid.step_feet`/`paths`), and a zone op's `spare`
  leaves out the squares near the caster's friends. Tsunami (`does: "wave"`) is cast from the encounter screen (w)
  when a band was seen first (`stonework.wave_casters`/`wave`); a Fighter made from a dead creature starts "dead" and
  `Battle.start` ends a fight with no foe standing. Tests: tests/test_spells_road5.py.
- Gear and tools 2024 (Expansion 2 part D): items.json `pack` (opens into its contents, gear.open_pack), `helps`
  {search, traps, force, disguise} (dungeon.helps, law.put_on_disguise), `utilize` (a tool's 2024 uses, on its card),
  `carry` also on carried containers (each kind once, Sheet.pack_carry), `trinket` (data/trinkets.json; the name and
  a `trinket:<id>` tag on the Item, rules/items.make_trinket); thrown or coated things are item spells (acid, net,
  caltrops and ball bearings as zones "caltrops"/"bearings" with a fixed `dc`, `coat_poison` and the `poisoned_blade`
  buff); antitoxin is `effects["antitoxin"]` (query.save_roll). The tool rule: `camp.check(..., tool=)` and
  `camp.tool_bonus` (proficiency; with the skill too, advantage). Shop stock lines may name a smallest settlement
  kind; economy.json `culture_stock` adds a people's wares to its general stores.
- Inns and passage (part D): economy.json services `inn` (stay, meal and lifestyle prices by grade, the grades by
  settlement kind, theft/rest/seen/fill/sick), `toll`, `coach`, `ship`, `messenger`, `stabling`; services `room`,
  `meal`, `stay` (by grade), `coach`/`ship` (game/passage.py: routes over roads or sea by Dijkstra, the fare per
  head per mile, `travel` moves the party and passes the days), `messenger` (a waiting companion's `coming` time:
  companions.rejoin waits for it; pass_time calls rejoin while anyone is coming).
- Mounts and vehicles (part D): economy.json animals may say `small_only`, `lands`, `saddle`, `eats`; saddles are
  items with `tack` (mounts.saddled: bareback riders tire as walkers); `Character.vehicles` [{kind}] from economy.json
  `vehicles` (mounts.drawn/pullers: the animals nobody rides pull it, services.animal_carry five times their carry;
  step_factor slows it off the roads; seated walkers ride in a carriage). A mastiff in the herd guards it at night.
- Arms and masteries (Expansion 2 part A): weapons carry their 2024 `mastery` (data/items.json); a character uses it
  with the `weapon_mastery` feature and the weapon kind in `Character.masteries` (`progression.mastery_count`,
  `offer_masteries`, `relearn_masteries` after a long rest; the sheet's m), a creature when its stat block attack
  names one (creatures.json attack_extras "mastery", trait `weapon_mastery`). The tricks are `rules/engine/handlers/
  mastery.py` on the `attack_done` event (Nick in `Battle.offhand_option`); free choices go through
  `tactics.mastery_choice`. Armour training (`query.untrained_armour`, `spells.armour_problem`), Heavy/Loading,
  ammunition found after a fight (`Battle.shot`), improvised bow blows, magic ammunition as its own attack option;
  materials are item flags (`magic.item_flag`: adamantine_armor/_weapon, mithral, silvered). Items marked `rare`
  (firearms) stay out of shops, kits and plain loot.
- Sound (2026-10-10, Anton's request: "basic and satisfying sounds... a simple way for me to add music"): `app.audio`
  (realmwalker/audio). Logic never imports it: game code asks for a sound with `game.cue("chest")` (a name from
  data/sounds.json; drained each frame by audio/watch.py, never saved), and the watcher also notices a level gained
  (harp), money changing (coins) and gear changing (equip). Screens: `sound_open` / `sound_close` (class attributes,
  None for silence), `key_sounds` (a quiet tick when a key visibly changes the screen: App._key_to_screen compares
  `ui_state`; False where keys walk or fight), `music()` (a mood like "travel/forest", or None to keep the music of
  the screen below), and `app.audio.play(id, delay=)` / `app.audio.ui(id)` (one interface sound per frame, the highest
  `priority` wins). A fight's sounds come from `battle.events` through audio/cues.py, timed by the battle board. Music
  moods and how they behave (pauses, fades, once, resume, fallbacks, the folders made for the player) are
  data/music.json; the player's tunes in `paths.music` (music/ next to the game) replace the shipped ones for that mood
  and are evened to -18 LUFS on first play (music_levels.json). Volumes 0-10 in Settings (+ Ctrl M mute); the "Your
  music" page (ui/screens/music.py) lists the moods, previews them and opens the folder. Headless (tests, autoplay)
  the same calls go to a SilentBackend: never open a sound device in a test. The smoke test plays to SDL's dummy
  driver and FAILS if the device, an effect or the title music did not work (main.sound_trouble). To check a mix
  without ears, record it: `SDL_AUDIO_DRIVER=disk SDL_AUDIO_DISK_OUTPUT_FILE=build/session.raw` before the smoke test
  writes what would be heard (float32 stereo 48 kHz raw) for `audio/levels` to measure. A new sound: add it
  to tools/build_sounds.py EFFECTS (or make it there), run it, add the entry to data/sounds.json, commit
  assets/sounds; tests/test_audio.py checks every name the code asks for exists and every file is at one loudness.
- Battles: `rules/combat.Battle` is pure logic driven by `step()` / `pending_party()` / `do_*()`; the screen
  (`ui/screens/battle.py`) only paces and asks. `GameState.busy` (encounter, battle, aftermath or death pending)
  blocks moving; `GameScreen._open_event_screen()` opens the right screen. Debug console: `fight <group>`.

## Git

Commit after every working step with a clear message ending in the Co-Authored-By line.
Working copy uses LF (`core.autocrlf false`); `.bat` files are CRLF via `.gitattributes`.
