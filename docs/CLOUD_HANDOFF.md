# Realmwalker — handover for a cloud session

Read this first if you are running in a **Claude Code cloud session** (a Linux container with this repo
checked out) rather than on Anton's Windows machine. `CLAUDE.md` still applies in full; this file only says
what is different up here and how work gets back to him.

## Who you are working for

Anton. **He is not a programmer.** Explain what you did in terms of what changed *in the game*, never in terms
of functions and files. If he has to do something, give Windows click-by-click steps. Never ask him to edit code.
He plays the game on Windows; you only ever see Linux.

**He is usually at work while you run, and cannot try each small tweak.** So do not work in small steps and wait
for him. Take a whole theme, do all of it, and have it finished and pushed by the time he looks. Do not stop to
ask a question you can answer from the design, the code, or a sensible default: make the call, write down what you
assumed in the PR, and carry on. The only things worth stopping for are decisions that would waste the work if
guessed wrong — and even then, do everything that does not depend on the answer first.

## The project in three lines

A grim, text-heavy open-world party RPG on D&D 5e rules: pixel-art tiles and figures drawn over a text grid
(python-tcod and its SDL renderer, with an all-letters fallback), all content in `data/*.json`, flavour text
optionally written by the Player2 app's local AI with a built-in fallback for everything. Nine milestones (M0–M9)
are done, the design's v1 lists are complete, and **version 1.0** (2026-10-03) added the pictures and the new
interface (mouse play, action bar, rebuilt pack, animated fights). Work since then is polish.

Read in this order: `CLAUDE.md` (how the codebase works and its rules), `docs/DESIGN.md` (the design, which is
the source of truth), `docs/PROGRESS.md` (status, decisions, and the "After v1 — continuing work" section).

## What runs up here, and what does not

First, set the environment up (Python 3.12):

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` includes `pyinstaller`, which is only used by the Windows packaging step; it installs fine
and is otherwise ignored.

| Check | Cloud | How |
|---|---|---|
| All tests | ✅ | `.venv/bin/python -m pytest -q` (≈950 tests, several minutes) |
| Autoplay bot, both AI modes | ✅ | `.venv/bin/python tools/autoplay.py --turns 3000` |
| Balance numbers | ✅ | `.venv/bin/python tools/balance.py --runs 60` |
| Mock Player2 server | ✅ | `.venv/bin/python tools/mock_player2.py --port 4316 --mode chaos` (tests start it themselves) |
| Rebuild the tile sheets | ✅ | `.venv/bin/python tools/build_tiles.py` (downloads the CC0 Dungeon Crawl pack into `build/`; pure Pillow and numpy). Commit `assets/tiles` afterwards |
| Window smoke test | ⚠️ | Needs a display. Try `SDL_VIDEODRIVER=dummy .venv/bin/python main.py --smoke-test out.png` **once**; if it fails, do not fight it — say in the PR that the window check is owed on Windows |
| Friend build (`.exe` + zip) | ❌ | PyInstaller would build a Linux binary. Only Anton's Windows machine makes `Realmwalker.zip` |
| The real Player2 app | ❌ | It lives at `127.0.0.1:4315` on Anton's PC and is not reachable here. **Never** try; a stray call costs him real energy (it happened once, ~15 joules). Tests and the smoke test must always use the mock or the AI off |

## How to work through a long unattended stretch

Big sweeping batches are what he wants, and they are safe here because nothing reaches him until he merges.

- **One branch, many commits, one pull request per theme.** Name it for the work: `cloud/town-life`,
  `cloud/combat-feel`. Put everything belonging to that theme on it, however much that is. Do not open a second
  branch off `main` for work that builds on the first — it would not contain it until he merges. If two themes are
  genuinely independent, separate branches are better, because he can take one and drop the other.
- **Commit after every working step, with the tests green at that commit.** That way a step that turns out bad can
  be dropped without losing the rest, and he can read the branch as a story.
- **Never leave `main` broken**; it is what he plays.
- **Keep going after a finished batch.** Don't wait to be told: pick the next item from the list in
  `docs/PROGRESS.md`, start a new branch, and keep working until the list is done or you run out of session.
- **If the session stops in the middle** (a usage limit, a crash, being closed), everything committed is safe and
  pushed, so the next session picks up from the branch. Push as you go rather than only at the end.
- A batch of forty commits is fine. A batch that cannot be verified is not.

**Done for each batch means:**

1. `pytest` green.
2. Autoplay clean in both modes (`RESULT: OK` twice).
3. `tools/balance.py` inside its bands if you touched combat, cold, bleeding or XP.
4. `docs/PROGRESS.md` updated in his language, under "After v1 — continuing work".
5. Commit messages readable, each ending with the Co-Authored-By line your session's instructions give.
6. A pull request whose description he can read without knowing any code, in this shape:
   - **What is different when you play** — grouped by theme, in game terms.
   - **How to see it** — for each visible thing, where to look: which screen, which key, whether it needs a fresh
     world or a new character.
   - **What I could not check here** — the window itself, how it looks, anything needing the real Player2 AI, and
     the friend build. Say plainly that these are owed on Windows.
   - **Anything you assumed** because you did not stop to ask.

## Because you cannot see the game

This is the real limit of working up here, so work with it rather than against it:

- Prefer changes a test or a small measuring script can prove. Scripts that walk the world for four thousand
  steps, hold a hundred conversations, or fight forty fights and then count which lines repeat have found more
  real problems in this project than reading code did. Keep them in the session's scratch directory, not the repo.
- For anything about **layout, colour or how a screen reads**, write the change, then say exactly where he (or a
  Claude Code session on his PC) should look. He will run one locally to check how it looks and to debug — leave
  it what it needs: notes in `docs/PROGRESS.md`, a short "how to see this" line per item, and no half-finished
  work on the branch.
- Rendering code can still be exercised headlessly: screens can be pushed and rendered into a `tcod.console.Console`
  in a test (see `tests/test_app_ui.py`), which catches crashes and wrong text even without a window.
- **The pictures** (since 1.0) are recorded as commands even without a window: `tests/test_graphics_ui.py` gives the
  app a GfxContext over the real tile atlas and checks what each screen asks to draw (that a portrait, a figure, a
  map chunk, a fight stage is there). Pixel output needs a real GPU window; if `SDL_VIDEODRIVER=dummy` cannot make a
  renderer, say in the PR that how it *looks* is owed on Windows. Every picture path must keep a letters path
  (`canvas.gfx is None`), because Settings → Graphics → Letters and the tests use it.
- New art is drawn in code (`tools/tile_art.py`, `tools/figure_art.py`, `tools/figure_gear.py`) and baked into
  `assets/tiles` by `tools/build_tiles.py`; look at it by saving the tiles to a PNG and enlarging them, and check
  `data/sprites.json` names only tiles that exist (`dolls.problems()`, used by the tests).

## Rules it is expensive to break

The full set is in `CLAUDE.md`. These are the ones that bite hardest, and the ones a fresh session gets wrong:

- **Old saves do not matter yet** (he said so on 2026-09-26). Bump `FORMAT_VERSION` in
  `realmwalker/game/save.py` when a save's shape changes, but a `MIGRATIONS` entry is optional: without one an old
  save is refused with a friendly "Could not load ... The files are still there, untouched." box, which is fine.
  Put a line in the PR saying old characters will not load, so he knows to start a new one. A crash, or deleting
  his files, is never fine.
- **One seeded RNG per world** (`core/rng.py`), `rng.child("purpose")` for streams, no `random` module in game
  logic. Key streams on **stable counters** (`player.steps`, a per-battle counter) and never on the world clock
  or the length of the log: two bugs came from exactly that.
- **Logic never imports UI.** Simulation code must be testable without a window.
- **`data/*.json` is hand-formatted.** Append with targeted string edits; never re-dump a whole JSON file, or the
  diff becomes a thousand lines and the formatting is lost.
- **AI writes words, code owns numbers.** Every AI task = prompt file + schema + fallback that needs no AI.
  All new flavour goes behind `GameState.flavour(level)` ("Text detail") and AI extras behind `App.ai_extras()`.
- **The writing has floors.** `tests/test_text_variety.py` asserts minimum line counts for the text a player
  reads hundreds of times (misses, wounds, greetings, encounters, weather, news). Add to the lists; do not thin
  them out to make a test pass.
- **Escape anything from the AI or the player** with `markup.escape()`, and use palette names from
  `ui/colors.py` for `<tags>` (`flavor` is a log colour, not a markup tag).
- **Line endings.** The working copy is LF; `.bat` files and `README_FRIENDS.txt` are CRLF via `.gitattributes`.
  Do not "fix" them.
- Add new invariants to `tools/autoplay.py` when you add a system, and remember the bot's checks only hold when
  `game.battle is None and game.aftermath is None`.

## How your work reaches Anton

You open a pull request; he merges it on GitHub; then on his PC he double-clicks **`Update_And_Play.bat`**,
which pulls the new version and starts the game. He does not use a terminal. If a change needs a fresh world or
a new character to be visible, say so in the PR in one line.

## Where to start

1. **Get his list of rough edges** — he said on 2026-09-26 that the game is good enough but "quite rough around
   the edges", and his own list beats anything you would invent. Ask once, early, in one message; write the
   answers into `docs/PROGRESS.md` as a plain list. If he is at work and does not answer, **do not idle**: start
   on the rough edges you can find yourself with the measuring scripts above, and take his list when it comes.
2. Work through that list in themed batches, biggest nuisance first.
3. The "Ideas parking lot" at the bottom of `docs/PROGRESS.md` (more races and classes, sailing, owning property,
   joining sieges, full smithing, AI voices, romance, a warband, a main story) is the long list. **Do not start
   any of it without asking him** — it is explicitly marked "do not build yet". Polish, fixes and more content of
   kinds that already exist need no permission.

## Local quirks worth knowing

- `main.py` is crash-safe: errors land in `logs/errors.log` and a friendly screen, so a stack trace in the log is
  a real bug even when the game kept running.
- Tests that only care about travel can set `game.survival = False` and monkeypatch `encounters.encounter_chance`,
  `events.event_chance` and `GameState.lost_dc`.
- An overworld step is 45–180 minutes of game time; anything rate-limited "per half hour" effectively fires every
  step. Rate-limit on steps instead.
- `Play.bat` installs Python 3.12 on Windows if it is missing; it is his only way in, so do not change what it
  does without saying so in plain language.
