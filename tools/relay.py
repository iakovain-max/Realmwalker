"""The relay: one builder session at a time, handing the baton on through the relay session (docs/expansions/RELAY.md).

A builder session calls this script instead of reading and writing the relay files by hand, so that every step is one
tool call with a short answer. Everything lives in build/ (git-ignored, on this PC only):

  build/relay.json   the baton: who holds it, its session, when it last beat, the part it is on, notes; and the id of
                     the relay session (the ordinary session that starts the builders)
  build/STOP         Anton's stop button: a builder that sees it saves its work and stops
  build/REHEARSAL    while this exists the builders only rehearse the hand-over (no game work)

Commands (all print short plain text; "now" is the PC's local time):
  status                      everything a builder or the relay session needs to decide what to do (one call)
  set-relay --session S       remember the relay session's id (the session that starts the builders)
  take --task T --session S --part P        take the baton
  beat [--part P] [--note N] [--five N --five-reset ISO] [--weekly N --weekly-reset ISO]
                              refresh the heartbeat; says when to warn the relay session of a usage limit
  handoff [--note N]          release the baton and print the message to send to the relay session
  release [--note N]          release the baton without handing on (Blocked, STOP, the programme finished)
  stop / clear-stop           write or remove build/STOP
  other --task T              the other builder task's id
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
BATON = BUILD / "relay.json"
STOP = BUILD / "STOP"
REHEARSAL = BUILD / "REHEARSAL"
STATUS_MD = ROOT / "docs" / "expansions" / "STATUS.md"

TASKS = ("realmwalker-a", "realmwalker-b")
NET_TASK = "realmwalker-net"

STALE_MINUTES = 60           # a holder silent this long (and not running) is dead: the relay session restarts the work
FIVE_HOUR_WARN_AT = 60       # warn the relay session once the 5-hour window is this full (percent)
WEEKLY_WARN_AT = 95          # the same for the weekly window
REHEARSAL_HOPS = 3           # a rehearsal stops after this many hand-overs


def now() -> datetime:
    return datetime.now().astimezone()


def iso(t: datetime) -> str:
    return t.replace(microsecond=0).isoformat()


def parse(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    t = datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone()


def read_baton() -> dict:
    if not BATON.exists():
        return {}
    try:
        return json.loads(BATON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_baton(d: dict) -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    BATON.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def other(task: str) -> str:
    if task not in TASKS:
        return TASKS[0]
    return TASKS[1] if task == TASKS[0] else TASKS[0]


def git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def status_lines() -> list[str]:
    t = now()
    b = read_baton()
    lines = [f"now: {iso(t)}"]
    lines.append(f"relay session: {b.get('relay') or 'UNKNOWN (relay.py set-relay --session <id>)'}")
    lines.append(f"stop: {'YES - ' + STOP.read_text(encoding='utf-8', errors='replace').strip() if STOP.exists() else 'no'}")
    hops = int(b.get("hops", 0))
    if REHEARSAL.exists():
        done = " - DONE, dispatch nothing more" if hops >= REHEARSAL_HOPS else ""
        lines.append(f"rehearsal: YES, hops={hops} of {REHEARSAL_HOPS} (no game work: rehearse the hand-over only){done}")
    else:
        lines.append("rehearsal: no")
    blocked = "no"
    nxt = "(STATUS.md has no 'Next session starts at' line)"
    if STATUS_MD.exists():
        for line in STATUS_MD.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Blocked:"):
                blocked = "YES - " + line
            if line.startswith("Next session starts at"):
                nxt = line
    lines.append(f"blocked: {blocked}")
    if b.get("task"):
        age = ""
        if b.get("heartbeat"):
            try:
                age = f" age_min={int((t - parse(b['heartbeat'])).total_seconds() // 60)}"
            except ValueError:
                age = " age_min=?"
        lines.append(f"baton: HELD by task={b.get('task')} session={b.get('session')} taken={b.get('taken')} "
                     f"heartbeat={b.get('heartbeat')}{age} hops={hops}")
        lines.append(f"part: {b.get('part', '')}")
        lines.append(f"dispatch next: {other(b['task'])} (only if the holder is dead: not running, or silent "
                     f"{STALE_MINUTES} minutes)")
    else:
        free_min = ""
        if b.get("released"):
            try:
                free_min = f", free for {int((t - parse(b['released'])).total_seconds() // 60)} min"
            except ValueError:
                pass
        lines.append(f"baton: free (last holder: {b.get('last_task', 'none')}, released {b.get('released', '-')}"
                     f"{free_min}, hops={hops})")
        lines.append(f"dispatch next: {other(b.get('last_task', ''))}")
    if b.get("note"):
        lines.append(f"note: {b['note']}")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = git("status", "--porcelain")
    n = len([x for x in dirty.splitlines() if x.strip()])
    last = git("log", "-1", "--format=%h %ci %s")
    lines.append(f"git: branch={branch} uncommitted_files={n} last_commit=\"{last[:140]}\"")
    lines.append(f"next: {nxt}")
    return lines


def cmd_status(_: argparse.Namespace) -> None:
    print("\n".join(status_lines()))


def cmd_set_relay(a: argparse.Namespace) -> None:
    b = read_baton()
    b["relay"] = a.session
    write_baton(b)
    print(f"relay session: {a.session}")


def cmd_take(a: argparse.Namespace) -> None:
    b = read_baton()
    t = iso(now())
    hops = int(b.get("hops", 0)) + 1
    b.update({"task": a.task, "session": a.session, "taken": t, "heartbeat": t, "part": a.part, "hops": hops,
              "warned": ""})
    for k in ("last_task", "released"):
        b.pop(k, None)
    write_baton(b)
    print(f"took the baton as {a.task} (session {a.session}) at {t}; hop {hops}")


def cmd_beat(a: argparse.Namespace) -> None:
    b = read_baton()
    if not b.get("task"):
        print("no baton held: take it first (relay.py take)")
        sys.exit(1)
    b["heartbeat"] = iso(now())
    if a.part:
        b["part"] = a.part
    if a.note:
        b["note"] = a.note
    warn = key = ""
    if a.five is not None and a.five_reset and a.five >= FIVE_HOUR_WARN_AT:
        key = "5h " + iso(parse(a.five_reset))
        warn = f"the 5-hour window is {a.five}% used and resets at {iso(parse(a.five_reset))}"
    if a.weekly is not None and a.weekly_reset and a.weekly >= WEEKLY_WARN_AT:
        key = "week " + iso(parse(a.weekly_reset))
        warn = f"the weekly window is {a.weekly}% used and resets at {iso(parse(a.weekly_reset))}"
    print(f"heartbeat {b['heartbeat']} (task {b['task']}, part: {b.get('part', '')})")
    if warn and b.get("warned") != key:   # once per window
        b["warned"] = key
        print(f"tell the relay session {b.get('relay', '?')} once, with send_message: \"RELAY LIMIT: {warn}\"")
    write_baton(b)
    if STOP.exists():
        print("STOP is there: finish the step, save on the branch, release the baton, stop.")


def cmd_handoff(a: argparse.Namespace) -> None:
    b = read_baton()
    task = b.get("task") or TASKS[0]
    t = now()
    note = a.note or b.get("note", "")
    nb = {"relay": b.get("relay", ""), "last_task": task, "released": iso(t), "note": note,
          "hops": int(b.get("hops", 0))}
    write_baton(nb)
    print(f"baton released by {task} at {iso(t)}")
    print(f"send_message to the relay session {nb['relay'] or '?'}: \"RELAY DONE by {task}: {note or 'part done'}\" "
          f"- then a short summary for Anton, and end your turn")


def cmd_release(a: argparse.Namespace) -> None:
    b = read_baton()
    task = b.get("task") or "none"
    nb = {"relay": b.get("relay", ""), "last_task": task, "released": iso(now()),
          "note": a.note or b.get("note", ""), "hops": int(b.get("hops", 0))}
    write_baton(nb)
    print(f"baton released by {task}; nothing handed on")


def cmd_stop(_: argparse.Namespace) -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    STOP.write_text(iso(now()) + "\n", encoding="utf-8")
    print(f"STOP written at {iso(now())}")


def cmd_clear_stop(_: argparse.Namespace) -> None:
    if STOP.exists():
        STOP.unlink()
        print("STOP removed")
    else:
        print("no STOP file")


def cmd_other(a: argparse.Namespace) -> None:
    print(other(a.task))


def cmd_reset_hops(_: argparse.Namespace) -> None:
    b = read_baton()
    b["hops"] = 0
    write_baton(b)
    print("hops reset to 0 (a rehearsal counts three hand-overs from here)")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    s = sub.add_parser("set-relay")
    s.add_argument("--session", required=True)
    s.set_defaults(fn=cmd_set_relay)
    s = sub.add_parser("take")
    s.add_argument("--task", required=True, choices=TASKS)
    s.add_argument("--session", required=True)
    s.add_argument("--part", default="")
    s.set_defaults(fn=cmd_take)
    s = sub.add_parser("beat")
    s.add_argument("--part")
    s.add_argument("--note")
    s.add_argument("--five", type=int, help="the 5-hour window's percent used (get_usage)")
    s.add_argument("--five-reset", help="when it resets (ISO, from get_usage)")
    s.add_argument("--weekly", type=int)
    s.add_argument("--weekly-reset")
    s.set_defaults(fn=cmd_beat)
    s = sub.add_parser("handoff")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_handoff)
    s = sub.add_parser("release")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_release)
    sub.add_parser("stop").set_defaults(fn=cmd_stop)
    sub.add_parser("clear-stop").set_defaults(fn=cmd_clear_stop)
    s = sub.add_parser("other")
    s.add_argument("--task", required=True)
    s.set_defaults(fn=cmd_other)
    sub.add_parser("reset-hops").set_defaults(fn=cmd_reset_hops)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
