# The relay: how the builder sessions hand the work to each other

Anton presses **Realmwalker: START** (the Scheduled list in the Claude app, Run now; or he types "start" in the relay
session) and the expansion programme builds itself, part after part, until he presses **Realmwalker: STOP** (or types
"stop" in the relay session, or double-clicks `Stop.bat` in the project folder). One builder session works at a time.
When its part is done it sends one message to the **relay session**, which starts the other builder task within
seconds; the new session reads this file, `CLAUDE.md` and `STATUS.md`, and carries on. Nothing fires on a clock while
the work goes well; the clock is only a safety net. (Anton and Claude set this up on 2026-10-17, replacing the
twenty-minute chain of 2026-10-13, which fired too often and still left gaps.)

Why this shape: a scheduled run (a session the app starts by itself, with nobody looking at it) may not start a task or
a session, nor change a task's schedule; all of that is refused unattended, permission rules or not. It may read, edit,
run commands, commit, push, and **send a message to an ordinary session**. An ordinary session in Auto mode may start a
task (`run_scheduled_task`) and set the new session's model. So the builders are scheduled tasks, and one ordinary
session, kept open, is the switchboard.

## A. The pieces

- **The relay session**: an ordinary session on this project (Auto mode, Opus 5.5), kept open in the app, whose only
  job is section R. It keeps a tiny memory: every turn is a few tool calls. Its id is in `build/relay.json`
  (`relay.py status` shows it; `relay.py set-relay --session <id>` sets it). Any session can become the relay session:
  open the project in a new session (Auto mode) and say "Be the Realmwalker relay session: do section R of
  docs/expansions/RELAY.md".
- **Scheduled tasks** (the Claude app's Scheduled list; their prompts are short and point here):
  - `realmwalker-a` and `realmwalker-b`: the two builders, with no schedule of their own. The relay session starts them
    by turns (a task may not be started while its last run is still finishing, so two tasks alternate), and sets each
    new run to Opus 5.5 at high effort right after starting it.
  - `realmwalker-net`: the safety net, every two hours while the work is on: it sends the relay session one message
    ("check") and stops. The relay session then restarts the work only if the baton lies dropped.
  - `realmwalker-start`, `realmwalker-stop`: Anton's buttons; each clears or writes STOP and messages the relay session.
- **Files** in `D:\Project Dawn\build\` (git-ignored, on this PC only), handled by `tools/relay.py`:
  `relay.json` (the baton: who holds it, its session id, the last heartbeat, the part, a note; and the relay session's
  id), `STOP` (the stop button), `REHEARSAL` (while it exists the builders only rehearse the hand-over, section E).
- **The script**: `.venv\Scripts\python.exe tools\relay.py ...` from the project folder (Git Bash: `cd "/d/Project
  Dawn"`): `status` · `set-relay` · `take` · `beat` · `handoff` · `release` · `stop` · `clear-stop`. Each prints a few
  plain lines and says what to do next.
- **Messages** go with `mcp__ccd_session_mgmt__send_message` (load it with ToolSearch `select:` first) to the relay
  session's id. They begin with `RELAY DONE` (a part finished), `RELAY LIMIT` (a usage window nearly used up),
  `RELAY START`, `RELAY STOP`, `RELAY CHECK` (the net), `RELAY BLOCKED`.

## R. The relay session (an ordinary session, kept open)

You are the switchboard. Every turn, whatever woke you (a message from a builder, from the net or from a button, a
wake-up you scheduled, or Anton typing "start", "stop" or "status"), do this in as few tool calls as possible and answer
in one or two lines. Never do any game work, never read the code, never ask Anton anything.

1. Run `relay.py status` (Bash: `cd "/d/Project Dawn" && .venv/Scripts/python.exe tools/relay.py status`). If it says
   the relay session is UNKNOWN or names another session, run `relay.py set-relay --session <your id>` (`get_session`
   with `"self"` gives it).
2. Anton typed "stop", or the message is `RELAY STOP`, or `stop: YES`: `relay.py stop` if the file is not there yet;
   switch the net off (`update_scheduled_task` `realmwalker-net`, `enabled: false`); say that the work stops at the
   builder's next safe point. Nothing else.
3. `blocked: YES`, or the message is `RELAY BLOCKED`: switch the net off, say what is blocked, and stop. The same if
   `next:` says the whole programme is finished, or a rehearsal says DONE.
4. Anton typed "start", or the message is `RELAY START`: `relay.py clear-stop`, switch the net on
   (`update_scheduled_task` `realmwalker-net`, `enabled: true`), then go on with step 5.
5. Is a builder at work? `baton: HELD` → `get_session` on its session id. Running and `age_min` under 60: all is well,
   say so, and stop. Not running, or silent for 60 minutes or more: it was cut off (a usage limit, a crash); dispatch
   the task that `dispatch next:` names. `baton: free`: dispatch the task that `dispatch next:` names (if the baton was
   released less than two minutes ago by a `RELAY DONE`, that is the normal hand-over).
6. **Dispatch** = `mcp__scheduled-tasks__run_scheduled_task` with that task id, then at once
   `mcp__ccd_session_mgmt__set_session_model` on the new session id with `"claude-opus-5-5"` and
   `mcp__ccd_session_mgmt__set_session_effort` with `"high"`. If the run is refused because that task still has a run
   in progress, try the other builder; if both are refused, `ScheduleWakeup` 300 seconds and try again then. Say in one
   line which builder you started and what `next:` says it will do.
7. A `RELAY LIMIT` message names the moment a usage window resets: schedule a wake-up for three minutes after it
   (`ScheduleWakeup`; it allows at most 3600 seconds, so wake hourly until then, each wake doing steps 1 and 5 again).
   A wake-up that finds the builder alive does nothing. If a wake-up itself fails under the limit, the net's next
   message catches up.
8. `RELAY CHECK` (the net) and "status": steps 1 and 5 only; answer in one line.

## B. START (task `realmwalker-start`, or "start" typed in the relay session)

The task: `relay.py clear-stop`; `relay.py status` for the relay session's id; `send_message` to it: `RELAY START`;
report in one sentence. If the relay session is UNKNOWN, say so: Anton opens the project in a new session (Auto mode)
and says "Be the Realmwalker relay session: do section R of docs/expansions/RELAY.md, then start".

## C. STOP (task `realmwalker-stop`, "stop" typed in the relay session, or `Stop.bat`)

The task: `relay.py stop`; `relay.py status`; `send_message` to the relay session: `RELAY STOP`; report in two plain
sentences: the work is stopped; whether a builder still holds the baton (it saves its work and stops at its next safe
point; to stop it this instant, open that session in the sidebar and press Stop). Do not touch the git working copy.
`Stop.bat` only writes the file; the builder stops at its next safe point and the net's next message makes the relay
session switch the net off.

## D. A builder's turn (tasks `realmwalker-a` and `realmwalker-b`)

Anton is away: never ask him anything; choose sensibly and write each choice into the commit message and
`docs/PROGRESS.md`. Never call `run_scheduled_task`, `start_session` or `update_scheduled_task` (refused unattended),
never `git reset --hard`, `git checkout --` or `git clean` (a cut-off session's work is never thrown away).

### D.1 Should I work? (one script call, at most one tool call more)

Run `relay.py status`.
- `stop: YES` → stop at once, changing nothing. (If an earlier run of yours still holds the baton, `relay.py release`
  first.)
- `blocked: YES`, or `next:` says the whole programme is finished → stop at once.
- `baton: HELD` by the **other** task → `get_session` on its session id. Running and `age_min` under 60: it is alive
  (you were started by mistake): stop at once. Not running, or silent for 60 minutes or more: it was cut off. Take over.
- `baton: HELD` by **your own** task (an earlier run of yours died) → take over.
- `baton: free` → take it.

Take: `get_session` with `"self"` for your session id, then `relay.py take --task <your task> --session <id> --part
"<the next: line, shortened>"`. If `rehearsal: YES`, go to section E.

### D.2 Pick up where the last session left off

`status` shows the branch and the number of uncommitted files. Uncommitted work means a session was cut off: read `git
diff` and `git log -5`, the baton's `part` and `note`, and STATUS.md's notes; finish that work rather than starting over.
Make sure you are on the working branch named in STATUS.md (`dlc/NN-name`), not `main`, before changing code.

### D.3 Build exactly the next part

Read `CLAUDE.md` ("How to work: fast, without losing quality"), `docs/expansions/STATUS.md`, the expansion's design
note it points to, and `docs/EXPANSIONS.md` section 5. Do exactly the part named under "Next session starts at", from
start to merge:
- done means playable (a rule is usable in play: the action list, the enemy and Auto, the screen, one test in a real
  fight);
- commit after every working step, and **beat after every commit** (D.4);
- tests while building: the tests of what you touched (`pytest -n 10 tests/test_x.py`);
- bulk data (book tables, items, monsters, spells, codex marking) through two or three helper agents on the sonnet
  model, each with a precise brief; numbers from the books are checked on page images;
- before merging, the three big checks side by side, started together in the background and waited for together
  (beat before starting them and after they finish): the full suite (`pytest -n 10`), the autoplay bot
  (`tools/autoplay.py --turns 3000`, its own temporary home) and the window smoke test (`main.py --smoke-test
  build/smoke.png --home build/smoke_home`, never the player's own home). While they run, write the PROGRESS and
  STATUS notes. If one fails, fix it and run that one again (and the full suite again after any code change). Then one
  fresh-review helper on the sonnet model against `docs/EXPANSIONS.md` section 5.2; fix what it finds and run the full
  suite once more;
- update `docs/PROGRESS.md` (in gameplay terms) and `STATUS.md` (with the new "Next session starts at"), commit, merge
  into `main` and push, as CLAUDE.md and the plan describe;
- if the part was the last of an expansion, do its release as `docs/EXPANSIONS.md` §5.1 step 12 says, and set
  STATUS.md's "Next session starts at" to the next expansion's step 1 (its branch and design note). A release does not
  stop the work;
- if something cannot be solved without Anton: write "Blocked: <what, in plain words>" at the top of STATUS.md, commit
  and push the working branch (not main), `relay.py release`, send the relay session `RELAY BLOCKED: <what>`, and stop.

### D.4 The beat (after every commit; before and after each long check; at least every 20 minutes of work)

1. `get_usage` with `"self"`: the 5-hour window's `percentUsed` and `resetsAt`, the weekly `percentUsed` and
   `resetsAt`, and the context `percentUsed`.
2. `relay.py beat --part "<where you are, a few words>" --five <N> --five-reset <resetsAt> --weekly <N>
   --weekly-reset <resetsAt>` (add `--note "<what a stranger must know to resume>"` whenever that changed).
3. If it prints a `RELAY LIMIT` line, send that message to the relay session (once; the script says when). Then, if
   the limit cuts you off, the relay session restarts the work three minutes after the window resets.
4. If it says STOP is there → D.6.
5. If the context is 70% used or more → hand off at the next commit (D.5), mid-part, with a `--note` that says exactly
   where the work stands and what comes next. (Memory is cheap to re-read; a session compacted at 97% loses detail.)

### D.5 The hand-over (the end of the part)

A fresh session at the start of a part is cheaper than this one going on: it re-reads only STATUS.md, the design note
and CLAUDE.md, while every further step here re-reads everything this session has seen. So when the part is merged and
pushed and STATUS.md names the next one: `relay.py handoff --note "<one or two lines for the next session>"`, send the
relay session the `RELAY DONE` message it prints, reply with a short summary in plain gameplay terms (what is new, what
was checked, what comes next) and **end your turn**. One exception: if the baton was taken under 30 minutes ago and the
context is under 40% (a design note, a small part, a quick fix), go straight on with the next part instead.

### D.6 STOP

At a safe point (a beat said STOP, or `status` shows it): commit what works on the working branch (never merge half a
part into main), push the branch, add a line at the top of STATUS.md's notes ("Stopped by Anton at <time> during <task>;
the next session continues it"), commit and push that, `relay.py release`, and stop. Send nothing.

## E. Rehearsal (while `build/REHEARSAL` exists)

(To rehearse: `relay.py reset-hops`, create `build/REHEARSAL`, press START; three hand-overs later it stops by itself;
then delete `build/REHEARSAL` and `build/STOP`.) No game work. Take the baton as in D.1. Then: beat once with real `get_usage` numbers; append one line to
`build/rehearsal.log`: `hop <hops> <task> <session id> <model from get_session self> <time>`; wait one minute
(`sleep 60`); if `status` shows the rehearsal DONE (`hops` of 3 or more), `relay.py release` and send the relay session
`RELAY DONE by <task>: rehearsal finished`; otherwise `relay.py handoff --note "rehearsal hop <n>"` and send the
`RELAY DONE` message it prints. Then stop.

## F. The net (task `realmwalker-net`, every two hours while the work is on)

`relay.py status` for the relay session's id; `send_message` to it: `RELAY CHECK`; stop. (If the relay session is
UNKNOWN: stop; say so in one line.) Never do game work.

## G. How it behaves at the limits

- **A usage limit** (Pro: a 5-hour window, a weekly one) cuts the running builder off where it is. Everything committed
  is safe; uncommitted work stays in the working copy with the baton's note. The builder warned the relay session when
  the window passed 60%, so the relay session wakes three minutes after the reset and starts the other builder, which
  resumes (D.1, D.2). If the cut came without warning, the net's next message (within two hours) does the same.
- **A crash or a frozen session**: the net's next message; the relay session sees a holder that is not running (or
  silent for an hour) and restarts the work.
- **The PC asleep or the app closed**: nothing runs. Anton sets Windows to never sleep when plugged in and leaves the
  Claude app open.
- **Two builders at once** cannot happen for long: a builder that finds a live holder stops at once (D.1), the relay
  session dispatches only when the baton is free or its holder is dead, and a run may not start another.
- **A release** does not stop the work; the next builder begins the next expansion.
- **The relay session's memory** grows a little with every hand-over (two or three tool calls each); after a few
  hundred, start a fresh one (section A) and the builders follow it from the next hand-over on.
