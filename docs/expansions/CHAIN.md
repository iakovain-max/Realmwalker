# The working day: how the builder sessions take turns

Anton presses **Realmwalker: START the day** in the morning (the Scheduled tasks list in the Claude app, Run now) and
**Realmwalker: STOP** whenever he wants it to stop. In between, the builder tasks `realmwalker-chain-a` and
`realmwalker-chain-b` take turns: one part of the expansion programme per session, one session at a time, until
20:00. This file is what every one of those sessions follows. (Anton set this up on 2026-10-13.)

Files, all in `D:\Project Dawn\build\` (git-ignored, on this PC only):
- `run_window.json` — `{"started": ISO time, "until": ISO time, "first_check": ISO time}`, written by START.
- `STOP` — written by STOP; any session that sees it stops at its next safe point.
- `chain.lock` — `{"task": id, "session_started": ISO time}`, held by the session that is building a part.

Use the PC's local time for all of these (`date -Iseconds` in Git Bash).

## A. The start button (task `realmwalker-start`)

1. Delete `build/STOP` if it is there.
2. Write `build/run_window.json`: started = now, until = today 20:00 local, first_check = now + 60 minutes.
3. Switch the builders on: scheduled-tasks `update_scheduled_task` with `enabled: true` for `realmwalker-chain-a` and
   `realmwalker-chain-b` (if the tool refuses, carry on: the window file alone governs them).
4. Then build a part yourself by section C, as task `realmwalker-start` (its partners are the two builders).

## B. The stop button (task `realmwalker-stop`)

1. Write `build/STOP` (one line: the time).
2. Switch the builders off: `update_scheduled_task` with `enabled: false` for both (if refused, the STOP file still
   stops them).
3. Delete `build/run_window.json`. Do not touch `build/chain.lock` or the git working copy: a session that is still
   building will see STOP, save its work on the working branch and release the lock itself.
4. Report what you did, and whether a session was still running (list_task_runs of the three tasks).

## C. A builder's turn (tasks `realmwalker-chain-a`, `realmwalker-chain-b`, and START's own part)

### C.1 Should I work at all? (cheap: a few tool calls, then stop if any answer is no)

Stop at once, changing nothing, if any of these holds:
1. `build/STOP` exists.
2. `build/run_window.json` is missing, or now is past its `until`. (If past `until`: delete the file and switch both
   builders off with `update_scheduled_task enabled: false`, then stop.)
3. Now is before `first_check` and you are not the START task (START has just begun a part).
4. Another session is at work: list_task_runs for `realmwalker-chain-a`, `realmwalker-chain-b` and `realmwalker-start`
   shows a run with status "running" other than your own (your own run is the newest one of your task with status
   running; if your task shows two running, the older one is at work: stop).
5. `build/chain.lock` exists and was written less than 10 minutes ago (two firings close together: the other one
   won). An older lock while no run of the three tasks is "running" (rule 4) was left by a session that was cut off:
   delete it and go on, continuing its work by C.2.
6. `docs/expansions/STATUS.md` has a line starting with "Blocked:".

Otherwise write `build/chain.lock` with your task id and the time, at once, before anything else.

### C.2 Pick up where the last session left off

- `git status`: if the working copy has uncommitted changes, a session was cut off (a usage limit, a crash, STOP).
  Read `git diff` and `git log -5`, and the part named in STATUS.md: finish that work rather than starting over; never
  discard it (no `git checkout --`, no `git reset --hard`, no `git clean`).
- Make sure you are on the working branch named in STATUS.md (`dlc/NN-name`), not main, before you change code.

### C.3 Build exactly the next part

Read `CLAUDE.md` (follow "How to work: fast, without losing quality"), `docs/expansions/STATUS.md`, the expansion's
design note it points to and `docs/EXPANSIONS.md` section 5. Do exactly the part named under "Next session starts
at", from start to merge:
- done means playable (a rule is usable in play: the action list, the enemy and Auto, the screen, one test in a real
  fight);
- commit after every working step (a cut-off session loses little);
- tests while building: the tests of what you touched, `pytest -n 10`; run the full suite (`pytest -n 10`) after each
  finished task of the part, not only at the end;
- bulk data (book tables, items, monsters, spells, codex marking) through two or three helper agents on the sonnet
  model, each with a precise brief; numbers from the books are checked on page images;
- before merging, one after another (never two heavy checks at once): the full suite, the autoplay bot, the window
  smoke test; then one fresh-review helper against `docs/EXPANSIONS.md` section 5.2, and fix what it finds;
- update `docs/PROGRESS.md` (in gameplay terms) and `STATUS.md` (with the new "Next session starts at"), commit,
  merge into main and push, as CLAUDE.md and the plan describe.

Anton is not a programmer and is away: never ask him questions; choose sensibly and write each choice into the commit
message and `docs/PROGRESS.md`. If something cannot be solved without him: write "Blocked: <what, in plain words>" at
the top of STATUS.md, commit and push the working branch (not main), release the lock and stop.

### C.4 Safe points: look for STOP

Before each heavy check (full suite, autoplay, smoke test), before merging into main, and between the tasks of a part,
look for `build/STOP`. If it is there: commit what works on the working branch (never merge half a part into main),
push the branch, add a line at the top of STATUS.md's notes: "Stopped by Anton at <time> during <task>; the next
session continues it", commit and push that, delete `build/chain.lock`, and stop.

### C.5 The end of a turn

- Delete `build/chain.lock`.
- If the part was the last of an expansion (it is released) or the programme is finished: switch both builders off
  (`update_scheduled_task enabled: false`), delete `build/run_window.json`, and stop, so Anton can play it.
- Otherwise just stop: the next firing of a builder (within twenty minutes) takes the next part.
- Finish with a short summary in plain gameplay terms: what is new, what was checked, what comes next.

## How it behaves at the limits

- A usage limit reached mid-part ends the session where it is. Everything committed is safe; uncommitted work stays in
  the working copy and the lock stays. Firings during the limit fail or stop at once. The first firing after the limit
  resets sees no run "running" and an old lock: it deletes the lock and continues the cut-off part (C.1.5, C.2).
- No firing starts a part after 20:00; a part begun before 20:00 finishes, merges and pushes.
