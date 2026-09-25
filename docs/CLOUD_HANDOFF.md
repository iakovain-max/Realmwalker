# Realmwalker — handover for a cloud session

Read this first if you are running in a **Claude Code cloud session** (a Linux container with this repo
checked out) rather than on Anton's Windows machine. `CLAUDE.md` still applies in full; this file only says
what is different up here and how work gets back to him.

## Who you are working for

Anton. **He is not a programmer.** Explain what you did in terms of what changed *in the game*, never in terms
of functions and files. If he has to do something, give Windows click-by-click steps. Never ask him to edit code.
He plays the game on Windows; you only ever see Linux. He leaves sessions running and prefers you to keep
working rather than stop to check in — but ask when a choice would change what the work *is*.

## The project in three lines

A grim, text-heavy open-world party RPG on D&D 5e rules: CP437 graphics via python-tcod, all content in
`data/*.json`, flavour text optionally written by the Player2 app's local AI with a built-in fallback for
everything. Nine milestones (M0–M9) are done and the design's v1 lists are complete; work since then is polish.

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
| All tests | ✅ | `.venv/bin/python -m pytest -q` (≈645 tests, a few minutes) |
| Autoplay bot, both AI modes | ✅ | `.venv/bin/python tools/autoplay.py --turns 3000` |
| Balance numbers | ✅ | `.venv/bin/python tools/balance.py --runs 60` |
| Mock Player2 server | ✅ | `.venv/bin/python tools/mock_player2.py --port 4316 --mode chaos` (tests start it themselves) |
| Window smoke test | ⚠️ | Needs a display. Try `SDL_VIDEODRIVER=dummy .venv/bin/python main.py --smoke-test out.png` **once**; if it fails, do not fight it — say in the PR that the window check is owed on Windows |
| Friend build (`.exe` + zip) | ❌ | PyInstaller would build a Linux binary. Only Anton's Windows machine makes `Realmwalker.zip` |
| The real Player2 app | ❌ | It lives at `127.0.0.1:4315` on Anton's PC and is not reachable here. **Never** try; a stray call costs him real energy (it happened once, ~15 joules). Tests and the smoke test must always use the mock or the AI off |

## Definition of done for a cloud change

1. `pytest` green.
2. Autoplay clean in both modes (`RESULT: OK` twice).
3. `tools/balance.py` still inside the bands (`tests/test_balance.py` covers this) if you touched combat, cold,
   bleeding or XP.
4. `docs/PROGRESS.md` updated — every session, in his language, under "After v1 — continuing work".
5. Commits are small and readable, message ending with:
   `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
6. One pull request per piece of work, with a description Anton can read: what is different when he plays, what
   you verified, and an explicit line saying **the window smoke test and the friend build still need running on
   Windows** (unless the dummy-display run above worked, in which case say so).

## Rules it is expensive to break

The full set is in `CLAUDE.md`. These are the ones that bite hardest, and the ones a fresh session gets wrong:

- **His saves are real now.** New fields in a save mean bumping `FORMAT_VERSION` in `realmwalker/game/save.py`
  and adding a `MIGRATIONS` entry. Never break an old save.
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

1. Ask him what felt rough when he played — he said on 2026-09-26 that the game is good enough but "quite rough
   around the edges", and that list is the best possible backlog. Write his answers into `docs/PROGRESS.md` as a
   plain list, then work through them in small PRs, one rough edge at a time.
2. Useful shape for that work, based on what has paid off so far: measure before writing. Scripts that walk the
   world, hold a hundred conversations, or fight forty fights and then count which lines repeat found more real
   problems than reading code did. Keep them in the session scratch directory, not in the repo.
3. The "Ideas parking lot" at the bottom of `docs/PROGRESS.md` (more races and classes, sailing, owning property,
   joining sieges, full smithing, AI voices, romance, a warband, a main story) is the long list. **Do not start
   any of it without asking him** — it is explicitly marked "do not build yet".

## Local quirks worth knowing

- `main.py` is crash-safe: errors land in `logs/errors.log` and a friendly screen, so a stack trace in the log is
  a real bug even when the game kept running.
- Tests that only care about travel can set `game.survival = False` and monkeypatch `encounters.encounter_chance`,
  `events.event_chance` and `GameState.lost_dc`.
- An overworld step is 45–180 minutes of game time; anything rate-limited "per half hour" effectively fires every
  step. Rate-limit on steps instead.
- `Play.bat` installs Python 3.12 on Windows if it is missing; it is his only way in, so do not change what it
  does without saying so in plain language.
