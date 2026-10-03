# Realmwalker — project guide for Claude Code

A grim, text-heavy open-world party RPG on D&D 5e rules, with CP437 graphics (python-tcod) and
AI-written flavour text from the Player2 app. **The user is not a programmer**: explain progress in
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
                           magic_items (making, identifying, curses, AI names), quests (work from templates tied to
                           real things, the journal), dragons (lairs, tribute, killing one), books (maps, histories,
                           lore, letters), death (the obituary and what the world keeps), interlude (the weeks that
                           pass before a new life in an old world)
  rules/                   character (Character + Sheet: derived numbers), items, inventory (equip rules), creation,
                           combat (Battle: rank combat on 5e dice), creatures, spells, wounds, progression (XP, rests),
                           body (needs, body heat, wetness, exhaustion), health (blood, pain, infection, healing,
                           injuries, diseases, treatment, drink, poppy)
  world/weather.py         weather as a deterministic function of seed, place and time (moving fronts)
  world/dungeon.py         dungeon levels under a site: styles, rooms, caves, doors, secrets, traps, chests
  world/factions.py        factions and figures (model, generation, territory map, relations, laws)
  world/politics.py        the politics engine: succession, wars, sieges, plague, raids, cults, gangs (history + live)
  world/history.py         250 years of history at world creation; the built-in chronicle
  world/news.py            news items and how they travel along the roads
  ui/                      window loop, fonts (tileset built at runtime), input, markup, widgets, map_render, screens/
data/                      ALL game data as JSON (names, fallback text, ... later races, items, creatures)
ai/prompts/                prompt templates (plain text, @max_tokens header, {slots})
assets/fonts/              DejaVu Sans Mono + licence
tests/                     pytest suite (headless; AI tests use tools/mock_player2.py, never the real app)
tools/                     autoplay.py, mock_player2.py, build_friends.py, balance.py (the design's targets)
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
- Dragons: records in `world.politics["dragons"]` (made by `world/history.py`, which always leaves one asleep).
  `world/politics.dragon_wakes` burns or taxes a village while you play; `game/dragons.py` has the warning signs,
  the descent warning and `on_battle`, which marks one slain for good (news, history, fame, tribute lifted).
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
- Screens added after v1: `ui/screens/spells.py` (S), `ui/screens/journal.py` (j; Tab switches Work/People),
  `CraftScreen` in `ui/screens/camp.py` (m at camp), `ui/screens/interlude.py` (after a new character in an old
  world).
- Fair chances (2026-10, Anton: "too easy to randomly die"): outside a battle 0 hit points is down, not dead (traps
  call `fight.lie_senseless`; only a blow taking a whole life's worth below zero kills). `fight.finish_battle` passes
  the fight's minutes only after the downed have come round, been robbed or been left for dead (beasts that win roll
  `_left_for_dead`). Underground counts as sheltered and dark (`survival.sheltered`, `fight.battle_env`). Water from the
  sky is `survival.sky_water`; skins top up on the move via `survival.top_up`. Measure deadliness with a scripted
  "careful player" over many lives before and after changing combat, cold, encounters or wounds.
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
