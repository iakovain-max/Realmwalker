"""The years between (M9): what happens in a world while nobody is looking.

When a new character is made in a world that has already been played — after the last one died, or was left
behind — the world does not politely wait. A few weeks to a few months pass: rulers die, wars are declared and
lost, towns are taken, plague comes, gangs rise and hang, a dragon wakes. Then the new character walks into
whatever is left, and is told what changed.

`pass_the_years(world, tables)` moves the clock and runs the politics engine over the gap, and returns a summary
in plain words (`lines`) with the news that came out of it.
"""

from __future__ import annotations

from realmwalker.core.rng import RNG
from realmwalker.world import factions as fx
from realmwalker.world import news, politics

SPAN_DAYS = (21, 150)  # a few weeks to a few months
MAX_LINES = 14


def should_pass(world) -> bool:
    """Only for a world that somebody has already lived (and died) in."""
    return bool(world.politics.get("fallen")) or world.politics.get("last_tick") is not None


def snapshot(world) -> dict:
    return {
        "owners": {s.id: s.owner for s in world.settlements},
        "rulers": {f.id: f.leader for f in fx.active_factions(world)},
        "alive": {f.id for f in fx.active_factions(world)},
        "wars": {w["id"] for w in world.wars if w.get("ended") is None},
        "status": {s.id: tuple(sorted(s.status)) for s in world.settlements},
        "dragons": {d["name"]: bool(d.get("alive")) for d in world.politics.get("dragons", [])},
    }


def pass_the_years(world, tables, rng: RNG | None = None, days: int | None = None) -> dict:
    rng = rng or world.rng.child(f"interlude/{world.time}")
    days = int(days if days is not None else rng.randint(*SPAN_DAYS))
    before = snapshot(world)
    from_day = news.now_days(world)
    world.time += days * 1440
    politics.tick(world, tables)
    after = snapshot(world)
    items = [n for n in world.news if n["day"] >= from_day and n.get("importance", 2) >= 2 and not n.get("player")]
    items.sort(key=lambda n: (-n.get("importance", 2), -n["day"]))
    return {"days": days, "lines": changes(world, tables, before, after), "news": items[:MAX_LINES]}


def changes(world, tables, before: dict, after: dict) -> list[str]:
    """What is different now, in the words the player would use."""
    from realmwalker.core.textgen import escape_markup as esc

    lines: list[str] = []
    for sid, owner in after["owners"].items():
        was = before["owners"].get(sid)
        if was == owner:
            continue
        s = world.settlements[sid]
        now = world.factions.get(owner)
        old = world.factions.get(was)
        if now is not None and old is not None:
            lines.append(f"<warn>{esc(s.name)} is held by {esc(now.name)} now, taken from {esc(old.name)}.</>")
        elif now is not None:
            lines.append(f"<warn>{esc(s.name)} answers to {esc(now.name)} now.</>")
    for fid, leader in after["rulers"].items():
        if before["rulers"].get(fid, leader) == leader:
            continue
        f = world.factions.get(fid)
        fig = world.figures.get(leader)
        if f is not None and fig is not None:
            lines.append(f"<info>{esc(f.name)} has a new ruler: {esc(fig.full_name())}.</>")
    gone = before["alive"] - after["alive"]
    for fid in gone:
        f = world.factions.get(fid)
        if f is not None:
            lines.append(f"<danger>{esc(f.name)} is no more.</>")
    risen = after["alive"] - before["alive"]
    for fid in risen:
        f = world.factions.get(fid)
        if f is not None:
            lines.append(f"<warn>{esc(f.name)} has risen.</>")
    for war in world.wars:
        if war["id"] in after["wars"] - before["wars"]:
            a, d = world.factions.get(war["attacker"]), world.factions.get(war["defender"])
            if a is not None and d is not None:
                lines.append(f"<danger>{esc(a.name)} is at war with {esc(d.name)}.</>")
        elif war["id"] in before["wars"] - after["wars"]:
            a, d = world.factions.get(war["attacker"]), world.factions.get(war["defender"])
            if a is not None and d is not None:
                lines.append(f"<good>The war between {esc(a.name)} and {esc(d.name)} is over.</>")
    for sid, status in after["status"].items():
        new_states = set(status) - set(before["status"].get(sid, ()))
        s = world.settlements[sid]
        words = {"plague": "<danger>Plague is in {}.</>", "famine": "<warn>There is famine in {}.</>",
                 "siege": "<danger>{} is under siege.</>", "sacked": "<danger>{} was sacked.</>",
                 "burned": "<danger>{} was burned.</>", "raided": "<warn>{} was raided.</>",
                 "tribute": "<danger>{} pays tribute to a dragon now.</>"}
        for state in new_states:
            if state in words:
                lines.append(words[state].format(esc(s.name)))
    for name, alive in after["dragons"].items():
        if alive and not before["dragons"].get(name, True):
            lines.append(f"<danger>{esc(name)} is awake.</>")
    return lines[:MAX_LINES]


def summary_text(world, tables, summary: dict) -> list[str]:
    """The whole 'while you were away' page, marked up."""
    from realmwalker.core.textgen import escape_markup as esc
    from realmwalker.game import death

    days = summary["days"]
    span = f"{days} days" if days < 60 else f"{days // 30} months"
    out = [f"<title>{span} pass.</>", ""]
    if summary["lines"]:
        out += summary["lines"]
    else:
        out.append("<dim>Nothing that reached the roads. The great ones kept their quarrels indoors.</>")
    if summary["news"]:
        out += ["", "<title>What people are saying</>"]
        out += [f"<dim>·</> {esc(n['text'][:1].upper() + n['text'][1:])}" for n in summary["news"][:8]]
    fallen = world.politics.get("fallen", [])
    if fallen:
        last = fallen[-1]
        out += ["", f"<dim>The last traveller to walk this land was {esc(last['name'])}, who "
                    f"{esc(death.how_they_died(last['cause']))} at {esc(last['place'])} in {last['year']}.</>"]
    return out
