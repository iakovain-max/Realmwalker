# The working day: how the builder sessions take turns

Anton presses **Realmwalker: START the day** in the morning (the Scheduled tasks list in the Claude app, Run now) and
**Realmwalker: STOP** whenever he wants it to stop. In between, the builder tasks `realmwalker-chain-a` and
`realmwalker-chain-b` take turns: one part of the expansion programme per session, one session at a time. No new
part starts after 20:00; a part already begun is finished, even if a usage limit interrupts it. Finished expansions
are released and the work goes straight on with the next one. This file is what every one of those sessions follows.
(Anton set this up on 2026-10-13.)

Files, all in `D:\Project Dawn\build\` (git-ignored, on this PC only):
- `run_window.json` — `{"started": ISO time, "until": ISO time, "first_check": ISO time}`, written by START.
- `STOP` — written by STOP; any session that sees it stops at its next safe point.
- `chain.lock` — `{"task": id, "session": session id, "taken": ISO time, "heartbeat": ISO time, "part": text}`, held
  by the session that is building a part. The holder rewrites `heartbeat` at least every 20 minutes of work (after
  each commit, before and after each long check).

Use the PC's local time for all of these (`date -Iseconds` in Git Bash). A session's own id is the `session_id` of the
newest run of its own task with status "running" (`list_task_runs`).

## A. The start button (task `realmwalker-start`)

1. Delete `build/STOP` if it is there.
2. Write `build/run_window.json`: started = now, until = today 20:00 local, first_check = now + 60 minutes.
3. Switch the builders on: scheduled-tasks `update_scheduled_task` with `enabled: true` for `realmwalker-chain-a` and
   `realmwalker-chain-b` (if the tool refuses, carry on: the files alone govern them).
4. Then take a turn yourself by section C, as task `realmwalker-start`.

## B. The stop button (task `realmwalker-stop`)

1. Write `build/STOP` (one line: the time).
2. Switch the builders off: `update_scheduled_task` with `enabled: false` for both (if refused, STOP still stops them).
3. Delete `build/run_window.json`. Do not touch `build/chain.lock` or the git working copy: a session that is still
   building will see STOP, save its work on the working branch and release the lock itself; a part cut off by a
   usage limit stays where it is until the next START.
4. Report what you did, and whether a session was still running (`list_task_runs` of the three tasks).

## C. A builder's turn (tasks `realmwalker-chain-a`, `realmwalker-chain-b`, and START's own turn)

### C.1 Should I work at all? (cheap: a few tool calls; if not, stop at once, changing nothing)

1. `build/STOP` exists: stop.
2. `docs/expansions/STATUS.md` has a line starting with "Blocked:": stop.
3. Is someone else at work? Look at `list_task_runs` for the three tasks and at `build/chain.lock`:
   - another run (not your own) has status "running" and either the lock's `heartbeat` or that run's
     `last_activity_at` is less than 45 minutes old: it is at work; stop;
   - the lock was written less than 10 minutes ago by another session: two firings close together, the other won;
     stop.
   - Otherwise any lock left behind belongs to a session that was cut off (a usage limit, a crash) or has stalled for
     45 minutes: you take its work over (C.2). Note this in your summary.
4. Is the day open?
   - A lock was left behind by a cut-off session (rule 3): resume that part even if the window is closed or missing.
     Finishing what was started comes first, so work cut off by a usage limit carries on by itself when the limit
     resets (the builders keep firing until it is finished).
   - Otherwise `build/run_window.json` must exist and now must be before its `until` (and, unless you are START,
     after its `first_check`). If the window has ended, delete it and switch both builders off
     (`update_scheduled_task enabled: false`), then stop. If it is missing, just stop.

Then write `build/chain.lock` with your task, your session id, taken = heartbeat = now and the part's name, at once.

### C.2 Pick up where the last session left off

- `git status`: if the working copy has uncommitted changes, a session was cut off (a usage limit, a crash, STOP).
  Read `git diff` and `git log -5`, the lock's `part`, and STATUS.md's notes: finish that work rather than starting
  over; never discard it (no `git checkout --`, no `git reset --hard`, no `git clean`).
- Make sure you are on the working branch named in STATUS.md (`dlc/NN-name`), not main, before you change code.

### C.3 Build exactly the next part

Read `CLAUDE.md` (follow "How to work: fast, without losing quality"), `docs/expansions/STATUS.md`, the expansion's
design note it points to and `docs/EXPANSIONS.md` section 5. Do exactly the part named under "Next session starts
at", from start to merge:
- done means playable (a rule is usable in play: the action list, the enemy and Auto, the screen, one test in a real
  fight);
- commit after every working step (a cut-off session loses little), and rewrite the lock's heartbeat each time;
- tests while building: the tests of what you touched (`pytest -n 10 tests/test_x.py`);
- bulk data (book tables, items, monsters, spells, codex marking) through two or three helper agents on the sonnet
  model, each with a precise brief; numbers from the books are checked on page images;
- before merging, the three big checks side by side, started together in the background and waited for together:
  the full suite (`pytest -n 10`), the autoplay bot (`tools/autoplay.py --turns 3000`, its own temporary home) and the
  window smoke test (`main.py --smoke-test build/smoke.png --home build/smoke_home`, never the player's own home). If
  one fails, fix it and run that one again (and the full suite again after any code change). Then one fresh-review
  helper against `docs/EXPANSIONS.md` section 5.2; fix what it finds and run the full suite once more;
- update `docs/PROGRESS.md` (in gameplay terms) and `STATUS.md` (with the new "Next session starts at"), commit,
  merge into main and push, as CLAUDE.md and the plan describe.

Anton is not a programmer and is away: never ask him questions; choose sensibly and write each choice into the commit
message and `docs/PROGRESS.md`. If something cannot be solved without him: write "Blocked: <what, in plain words>" at
the top of STATUS.md, commit and push the working branch (not main), release the lock and stop.

### C.4 Safe points: STOP, and whose lock it is

At each safe point (before the big checks, before merging into main, after each commit, between the tasks of a part):
- Read `build/chain.lock`. If it no longer names your session (you stalled and another session took over), stop at
  once: change nothing more, commit nothing; the new holder carries on.
- Look for `build/STOP`. If it is there: commit what works on the working branch (never merge half a part into main),
  push the branch, add a line at the top of STATUS.md's notes: "Stopped by Anton at <time> during <task>; the next
  session continues it", commit and push that, delete `build/chain.lock`, and stop.

### C.5 The end of a turn

- If the part was the last of an expansion, do its release as `docs/EXPANSIONS.md` §5.1 step 12 says (pack status,
  version, icon, notes, tag, GitHub release), and set STATUS.md's "Next session starts at" to the next expansion's
  step 1 (its branch and design note). The day does not stop for a release: the next turn begins the next expansion.
  Only when the whole programme is finished: switch both builders off and delete `build/run_window.json`.
- Delete `build/chain.lock`.
- Stop: the next firing of a builder (within twenty minutes) takes the next part.
- Finish with a short summary in plain gameplay terms: what is new, what was checked, what comes next.

## How it behaves at the limits

- **A usage limit** reached mid-part ends (or freezes) the session where it is. Everything committed is safe;
  uncommitted work stays in the working copy and the lock stays. The builders go on firing every 20 minutes; firings
  while the limit lasts fail or stop at once. The first firing after the limit resets finds the lock's heartbeat old
  (45 minutes or more) and takes the part over (C.1.3, C.2), even after 20:00 (C.1.4). If the frozen session wakes up
  later, its next safe point shows the lock is no longer its own and it stops without touching anything (C.4).
- **20:00**: no new part starts after it; a part begun before it, or cut off by a limit, is finished.
- **A release** does not stop the day.
