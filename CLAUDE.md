# Realmwalker — project guide for Claude Code

A grim, text-heavy open-world party RPG on D&D 5e rules, drawn with pixel-art tiles and figures over a text grid
(python-tcod + its SDL renderer; letters only as a fallback) and AI-written flavour text from the Player2 app.
**Version 1.0** (2026-10-03): pictures and the new interface are in (`docs/PROGRESS.md`, first entry). **The user is not a programmer**: explain progress in
gameplay terms, give Windows click-by-click steps when they must do something, never ask them to edit code.

- Source of truth for the design: `docs/DESIGN.md` (verbatim copy of the user's document).
- Status, decisions, known bugs, how to test: `docs/PROGRESS.md`. **Update it at the end of every session.**
- **Running in a cloud session** (Linux, no window, no Player2 app)? Read `docs/CLOUD_HANDOFF.md` first: it says
  what can and cannot be verified there, what "done" means without a window, and how work reaches the user.

## Running things (Windows, from the project folder)

| What | Command |
|---|---|
| Play (what the user does) | double-click `Play.bat` (sets up `.venv` on first run) |
| Get the newest version and play | double-click `Update_And_Play.bat` (git pull, then `Play.bat`) |
| Run from a terminal | `.venv\Scripts\python.exe main.py` |
| Window smoke test (opens, tours screens, screenshots, exits) | `.venv\Scripts\python.exe main.py --smoke-test out.png` |
| All tests | `.venv\Scripts\python.exe -m pytest` |
| Autoplay bot (AI off + mocked AI) | `.venv\Scripts\python.exe tools\autoplay.py --turns 3000` |
| Mock Player2 server | `.venv\Scripts\python.exe tools\mock_player2.py --port 4316 --mode chaos` |
| Friend build (tests, exe, smoke check, zip) | double-click `Build_For_Friends.bat` (runs `tools\build_friends.py`) |
| Balance numbers (fights, cold, wounds) | `.venv\Scripts\python.exe tools\balance.py --runs 60` |
| Rebuild the tile sheets (after changing tools/*_art.py, figure_*.py) | `.venv\Scripts\python.exe tools\build_tiles.py --pack <Dungeon Crawl Stone Soup Full folder>` (no `--pack`: downloads it) |
| Rebuild the sounds and the shipped music (after changing tools/build_sounds.py) | `.venv\Scripts\python.exe tools\build_sounds.py` (downloads the CC0 packs into build/sound_packs; `--no-music`: effects only) |

Milestone "done" = all tests pass + the game launches (smoke test) + autoplay ran clean in both AI modes.
Then commit, update PROGRESS.md, and stop for user feedback (unless the user said to keep going).

## Folder map

```
main.py                    entry point (crash-safe; --smoke-test, --home)
config.json                game-level config: Player2 client id (optional), debug console switch
realmwalker/
  app.py                   App: config, data, AI service, screen stack, error recovery (no window)
  paths.py                 where files live (dev vs packaged; player files in %APPDATA%\Realmwalker)
  config.py                GameConfig (config.json) and Settings (player prefs, settings.json)
  core/                    rng (the one seeded RNG), dice, schema (validation), textgen (fallback templates), logs
  data/                    registry.py loads + validates data/*.json; schemas.py describes each file
  ai/                      client (Player2 HTTP), service (workers/queue/ping), parsing, prompts, tasks, store
  world/                   generator (terrain, rivers, climate, biomes, towns, roads), local maps, calendar,
                           tables (numpy lookups from data), model (World + save-friendly dataclasses)
  game/                    state (player, party, actions, travel, time; street life, the weather turning,
                           landmarks), save (versioned zips), log, describe,
                           encounters (road trouble, local-map inhabitants), fight (start/finish battles, loot,
                           prisoners, rest), vision (field of view), survival (the body as time passes: weather,
                           eating, drinking, water sources, death), care (treatment, healing magic), camp (fire,
                           cooking, foraging, hunting, fishing), events (travel events, news, pedlars),
                           people (townsfolk: making, placing, day/night, impressions, memory), dialogue
                           (conversations, whitelisted outcomes), people_ai (AI facts in, validated words out),
                           economy (shops, prices, trade, haggling), services (inns, healers, temples, smiths,
                           stables, animals, labour), reputation (standing, deeds and their ripples, joining,
                           titles), law (crimes, witnesses, the watch, sentences, jail, disguise), law_talk (law and
                           faction choices in conversations), news (what the player hears), notices (town boards),
                           companions (hiring, wages, loyalty, orders, desertion), magic (copying spell scrolls),
                           dungeon (going under, light, traps, locks, chests, hoards), treasure (what is in them),
                           gear (what items are for: wear, mending, honing, snares, evenings, prayer, prisoners),
                           magic_items (making, identifying, curses, AI names), quests (work from templates tied to
                           real things, the journal), dragons (lairs, tribute, killing one), books (maps, histories,
                           lore, letters), death (the obituary and what the world keeps), interlude (the weeks that
                           pass before a new life in an old world)
  rules/                   character (Character + Sheet: derived numbers), items, inventory (equip rules), creation,
                           looks (how people look: options per people, random, read from words, written as words),
                           combat (Battle: D&D 5e combat on a grid), grid (the battlefield: distances, sight, cover,
                           areas, paths), tactics (how the enemy and Auto fight), creatures, spells, wounds, progression,
                           body (needs, body heat, wetness, exhaustion), health (blood, pain, infection, healing,
                           injuries, diseases, treatment, drink, poppy)
  world/weather.py         weather as a deterministic function of seed, place and time (moving fronts)
  world/dungeon.py         dungeon levels under a site: styles, rooms, caves, doors, secrets, traps, chests
  world/factions.py        factions and figures (model, generation, territory map, relations, laws)
  world/politics.py        the politics engine: succession, wars, sieges, plague, raids, cults, gangs (history + live)
  world/ages/              the lived history (2026-10, after Dwarf Fortress): sim (the year loop, events), land
                           (fated/doomed places), folk (families), realms (rulers, grants, succession), war, wild
                           (tribes, beasts, heroes, barrows, towers), faith, lore (artifacts, works), orders, eras,
                           present (what is left becomes today), words (names, event text); design docs/WORLD_HISTORY.md
  world/history.py         the chronicle (told by named ages); the old "told" history for worlds made before the ages
  world/legends.py         the Legends book's pages and lists (logic): every person, realm, place, war, beast...
  world/news.py            news items and how they travel along the roads
  ui/                      window loop, fonts (tileset built at runtime), input, markup, widgets (Canvas), map_render
                           (the letters view), hud (side panel, log, action bar), colors, screens/
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
ai/prompts/                prompt templates (plain text, @max_tokens header, {slots})
assets/fonts/              DejaVu Sans Mono, Cinzel, EB Garamond, Grenze Gotisch + licences
assets/tiles/              sheet_*.png + tiles.json, BUILT by tools/build_tiles.py (commit them; the game never builds)
assets/sounds/, music/     effects (16-bit mono WAV) and the shipped tunes (OGG, by mood folder), BUILT by
                           tools/build_sounds.py from CC0 packs (Kenney, OpenGameArt, RandomMind) + CREDITS.txt; commit
music/ (project root)      the PLAYER's own music, by mood folder; made by the game, ignored by git
tests/                     pytest suite (headless; AI tests use tools/mock_player2.py, never the real app)
tools/                     autoplay.py, mock_player2.py, build_friends.py, balance.py (the design's targets),
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
- **AI writes words, code owns numbers.** Every AI task (`ai/tasks.py`) = prompt file + schema + fallback.
  Schemas clamp/trim AI output; AI may only choose from whitelists. Always have a fallback that needs no AI.
- **Never make the player wait.** Submit AI work to `app.ai` (returns a Ticket; callback runs on the main
  thread via `poll()`). Use `FlavorStore.ensure()` for text needed now, `prefetch()` for text needed soon.
  Everything generated is stored in the save and never regenerated.
- **Never crash.** App wraps every screen call; errors go to `logs/errors.log` and a friendly message.
  Don't swallow errors silently in logic — let the App boundary catch and report them.
- **Text colours** via markup: `"<danger>bleeding</>"`; palette names in `ui/colors.py`.
  Always `markup.escape()` text from the AI or the player.
- Screens: subclass `ui/screens/base.Screen`; implement `render(canvas)`, `handle_key(ev)`,
  `autoplay_keys()` (sensible keys for the bot). Register clickable areas with `canvas.hit()` / `canvas.button()`.
- **Arrays are indexed [x, y]** (shape (width, height)) everywhere, matching tcod consoles (order="F").
- Saves store id lists (biome_ids, terrain_ids) next to index arrays so data files can change without
  breaking saves; always go through `GameState.remap_for()` / `_biome_remap` when reading them.
- New save fields: bump `game/save.py` FORMAT_VERSION. A MIGRATIONS entry is **optional** while the game is
  young — the user said on 2026-09-26 that old saves do not matter yet. Without one, an older save is refused
  with a friendly "Could not load ... The files are still there, untouched." box (a KeyError inside `_migrate`
  becomes a `SaveError`), which is acceptable: say so in the commit or PR so he knows to start a new character.
  What is never acceptable is a crash, or deleting his files.
- The autoplay bot checks game invariants (`tools/autoplay.py`); add checks there as systems are added.
- Time: `GameState.pass_time(minutes, activity)` ("walk", "rest", "sleep", "fight") runs `game/survival.tick` in
  30-minute chunks (body, health, eating/drinking, death). Tests about travel alone can set `game.survival = False`
  and monkeypatch `encounters.encounter_chance`, `events.event_chance` and `GameState.lost_dc`.
- Townsfolk live in `world.npcs` / `world.towns` (saved with the world). A town is filled by
  `people.populate_town` on first entry (or `prepare_town` ahead of arrival). Walking into someone sets
  `game.talk_to`; the game screen opens the conversation. AI conversation outcomes must stay in
  `dialogue.OUTCOMES`, narrowed per person by `people_ai.allowed_outcomes`.
- The smoke test always runs with the AI off; tests use the mock. Never let a test reach the real Player2 app.
- Factions live in `world.factions` / `world.figures` (saved with the world); a settlement's `owner` is the
  faction holding it, its realm is `factions.top_liege(owner)`. After changing holdings call `factions.touch(world)`
  (territory cache). Player standing, crimes, bounties and heard news are in `game.renown` (saved with the character).
- Deeds go through `reputation.deed()` (standing, ripples by relation, news); crimes through `law.commit()`
  (witnesses, reports, bounties, arrests). Arrests and sentences are pending states (`game.arrest`,
  `game.sentence`) opened by `GameScreen._open_event_screen()`.
- `world/politics.Politics` runs in history mode (narrative only; never destroys today's factions or changes
  today's holdings) and live mode (`politics.tick` from `pass_time`, a week per step, with consequences). Every
  event becomes news via `world/news.add`; the player hears it through `game/news.hear`.
- Level-ups add hit points and features at once; choices wait in `Character.pending` (`rules/progression`:
  `options`, `resolve`, `auto_resolve`). Pass `auto=True` to `award_xp` where nobody can choose.
- Companions are ordinary `Character`s in `game.party[1:]` with a `companion` dict (loyalty, wage, values, order,
  npc id); `game.waiting` holds those told to wait. When the player does something a companion might care about,
  call `companions.react(game, "<tag>")`; tags are matched against data/companions.json values and wants.
- Dungeons live in `world.local_maps` under the key `"x,y/level"` (`world/dungeon.get_dungeon`), with `features`
  {(x, y): trap/lock/chest/secret/captive} and `meta` {site, level, depth, style, rooms, hidden, boss, name}.
  `game/dungeon.py` drives them (descend/ascend, light from `game.lit`, search, unlock, bump, chests, the hoard).
  A level is built and populated once and then kept in the save.
- Magic items: `Item.magic` {rarity, props, identified, cursed, curse, title, story, source, value}; effects are
  read through `rules/magic.total(char, kind, **match)`. Code picks the properties within a budget
  (`game/magic_items.make`); the AI may only name and tell its history (task MAGIC_ITEM).
- Quests (`game/quests.py`) are plain dicts in `game.quests` (saved with the character) made from
  `data/quests.json` templates and tied to real things: a faction, a site, a settlement, an npc, an artifact.
  Offers live in `Town.flags["offers"]` (one per person, a new one about once a week). Progress is noticed where
  it happens: `quests.on_battle` (from `fight.finish_battle`), `on_arrive` (overworld), `on_arrive_dungeon` and
  `on_chest`/`free_captive` (from `game/dungeon.py`), and the conversation choices in `quests.QUEST_CHOICES`.
  Rewards go through `reputation.deed`; failure through `quests.daily` (from `pass_time`). The AI (task QUEST)
  may write the giver's words only; the game always shows the terms.
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
  `deep_history`, `next_event`; events have ids (`history.remember` writes one in play). `game/past.py` brings it into
  play (Look, conversations, heroes at inns, named beasts and barrow kings as bosses, the clear_lair_beast work);
  `ui/screens/legends.py` is the Legends book (b in the News screen; Legends for a saved world). Worlds made before keep
  their old history; every reader must cope with events without ids and figures without the new fields.
- Death: `game/death.die(game)` writes the character into `world.politics["fallen"]` (chronicle, news, companions
  released) and the death screen shows `fallback_obituary`, replaced by the AI's words (task OBITUARY) when they
  arrive. Nothing carries over to the next character except what the world remembers.
- A new character in a world that has been played runs `game/interlude.pass_the_years` first (real politics for
  three weeks to five months) and is shown what changed.
- Balance: `tools/balance.py` measures the design's targets (fights at level 1 and 3, a winter night, an
  untreated wound); `tests/test_balance.py` keeps them inside bands. Change combat, cold or bleeding numbers and
  run it before and after.
- The world's voice (street life in towns, companions talking on the road, the weather turning, night sounds,
  region and dungeon descriptions) is gated by `GameState.flavour(level)`, which reads the player's "Text detail"
  setting; AI flourishes are gated by `App.ai_extras()` ("AI extras" in Settings). Keep new flavour behind both.
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
  `canvas.over(...)` (`ui/gfx/scene.py`: Batch, Sprite, Image, Rect, Lines, Text, Clip). `canvas.gfx` is None headless
  and in letters mode, so every picture path must have a letters path (tests run headless; `tests/test_graphics_ui.py`
  renders with a fake GfxContext). Logic still never imports UI. Pictures live in `data/sprites.json` (validated):
  terrain, town walls, traps, map marks, and "figures" (colours, skins, hair, what each item looks like worn, outfits
  by trade, dressed creatures). New tiles: draw them in `tools/tile_art.py` (or a figure layer in `figure_gear.py`),
  rebuild with build_tiles.py, commit `assets/tiles`. Figures are 32x32; draw them at whole multiples or let
  `dolls.draw` scale them (it keeps pixels even). A rare item's look is `item.magic["look"]` {metal, cloth, emblem,
  glow}: `magic_items.look_for` picks it, the AI may only choose from `ai/tasks.py` LOOK_* lists.
- Looks (2026-10-10): `Character.looks` {build, skin, eyes, hair, hair_colour, beard, beard_colour, mark, paint,
  paint_colour, features {ears/tusks/horns/tail: option}, dye, cloak}, chosen on the creation Looks step; `appearance`
  is written from it by `rules/looks.describe`. Townsfolk and creatures have none stored: `looks.from_text` reads them
  from their words with a stable hash for the rest (`looks.of_npc`), and `dolls` draws from either. Options per people
  are data/appearance.json looks/races (`_default` for anything not written); body proportions, builds and colours are
  data/sprites.json figures (skins are real colours, drawn over grey). A new people needs nothing to work (human
  looks on a human body via `dolls.resolve_body`); its own body needs a `bodies` entry and a tile rebuild. Keep
  `tests/test_looks.py` green: every option must have a picture and a colour.
- Animations go through `canvas.gfx.animate` (movement) and `canvas.gfx.ambient` (idle: water, smoke, weather), from
  the Animations setting; the game's state never waits for an animation.
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

## Player2 facts (verified 2026-09-19 against the local docs at http://127.0.0.1:4315/docs, v0.10.79)

- Base URL `http://127.0.0.1:<port>/v1` (port from `%APPDATA%\game.player2.client\api.port`, default 4315).
  Use 127.0.0.1, not localhost. Endpoints: `GET /health`, `GET /joules`, `POST /chat/completions`.
- Game client id is optional locally (header `player2-game-key`); set it in config.json if ever needed.
- **Do not send `response_format`** — the current model then returns empty content.
- **The model thinks silently**: ~600 hidden tokens before a ~180-token answer. Too small a `max_tokens`
  gives an EMPTY reply that still costs energy. Keep `@max_tokens` generous (3000 for rich prompts).
- **Energy**: ~2 joules per rich call. The user's account showed 10 before its daily refill and 91 after.
  Background requests stop below `AIService.energy_reserve`. Never burn real energy in tests — use the mock.

## Git

Commit after every working step with a clear message ending in the Co-Authored-By line.
Working copy uses LF (`core.autocrlf false`); `.bat` files are CRLF via `.gitattributes`.
