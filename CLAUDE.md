# Realmwalker — project guide for Claude Code

A grim, text-heavy open-world party RPG on D&D 5e rules, with CP437 graphics (python-tcod) and
AI-written flavour text from the Player2 app. **The user is not a programmer**: explain progress in
gameplay terms, give Windows click-by-click steps when they must do something, never ask them to edit code.

- Source of truth for the design: `docs/DESIGN.md` (verbatim copy of the user's document).
- Status, decisions, known bugs, how to test: `docs/PROGRESS.md`. **Update it at the end of every session.**

## Running things (Windows, from the project folder)

| What | Command |
|---|---|
| Play (what the user does) | double-click `Play.bat` (sets up `.venv` on first run) |
| Run from a terminal | `.venv\Scripts\python.exe main.py` |
| Window smoke test (opens, tours screens, screenshots, exits) | `.venv\Scripts\python.exe main.py --smoke-test out.png` |
| All tests | `.venv\Scripts\python.exe -m pytest` |
| Autoplay bot (AI off + mocked AI) | `.venv\Scripts\python.exe tools\autoplay.py --turns 3000` |
| Mock Player2 server | `.venv\Scripts\python.exe tools\mock_player2.py --port 4316 --mode chaos` |
| Friend build (tests, exe, smoke check, zip) | double-click `Build_For_Friends.bat` (runs `tools\build_friends.py`) |

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
  game/                    state (player, actions, travel, time), save (versioned zips), log, describe (look text)
  ui/                      window loop, fonts (tileset built at runtime), input, markup, widgets, map_render, screens/
data/                      ALL game data as JSON (names, fallback text, ... later races, items, creatures)
ai/prompts/                prompt templates (plain text, @max_tokens header, {slots})
assets/fonts/              DejaVu Sans Mono + licence
tests/                     pytest suite (headless; AI tests use tools/mock_player2.py, never the real app)
tools/                     autoplay.py, mock_player2.py, build_friends.py
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
- New save fields: bump `game/save.py` FORMAT_VERSION and add a MIGRATIONS entry; never break old saves.
- The autoplay bot checks game invariants (`tools/autoplay.py`); add checks there as systems are added.

## Player2 facts (verified 2026-09-19 against the local docs at http://127.0.0.1:4315/docs, v0.10.79)

- Base URL `http://127.0.0.1:<port>/v1` (port from `%APPDATA%\game.player2.client\api.port`, default 4315).
  Use 127.0.0.1, not localhost. Endpoints: `GET /health`, `GET /joules`, `POST /chat/completions`.
- Game client id is optional locally (header `player2-game-key`); set it in config.json if ever needed.
- **Do not send `response_format`** — the current model then returns empty content.
- **The model thinks silently**: ~600 hidden tokens before a ~180-token answer. Too small a `max_tokens`
  gives an EMPTY reply that still costs energy. Keep `@max_tokens` generous (3000 for rich prompts).
- **Energy is scarce**: ~2 joules per rich call; the user's Patron Basic account had ~10 joules/day.
  Background requests stop below `AIService.energy_reserve`. Never burn real energy in tests — use the mock.

## Git

Commit after every working step with a clear message ending in the Co-Authored-By line.
Working copy uses LF (`core.autocrlf false`); `.bat` files are CRLF via `.gitattributes`.
