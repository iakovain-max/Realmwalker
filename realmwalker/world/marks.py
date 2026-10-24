"""Marks on places (Expansion 6 B.3, docs/ADVENTURES.md §5.19, §8.13): what a settlement is going through - besieged,
sacked, burning, burned, rebuilding, emptied, plague, famine, raided, tribute, a beast at its door, a festival, a
memorial. Not to be confused with rules/engine/marks.py (the marks spells leave on creatures).

Marks live in `Settlement.status` (saved with the world), in the forms politics has always written: `sacked` and
`burned` a day number, `tribute` a name, the rest records ({since, until, by...}); `since` reads either. Every place
that marks a settlement goes through `add`, so there is one door in; `age` (from Politics.expire_status) passes each
into its next mark instead of letting it vanish: burning -> burned -> rebuilding -> gone. Their words are data
(marks.json): the world map's label, what you see walking in, a thing seen in the streets.

    add(world, s, mark, day, **data)   lift(world, s, mark)   marks_of(s)   since(s, mark)
    age(world, tables, day)            words(tables, s, which, rng)        label(tables, s)

The world layer (no game): politics, threats and the ages use it, and the game reads it.
"""

from __future__ import annotations

DAY_FORM = ("sacked", "burned")  # a day number (what politics has always written)
NAME_FORM = ("tribute",)  # the name of whoever takes it
OWNED = ("siege", "emptied", "rebuilding")  # ended elsewhere: a siege by its war, the rest by world/threats.py


def table(tables) -> dict:
    return getattr(tables, "marks", None) or {}


def marks_of(s) -> list[str]:
    """The marks a settlement carries now (in the order they were made)."""
    return [k for k, v in s.status.items() if v is not None and v is not False]


def since(s, mark: str) -> float | None:
    """The day a mark began, whichever form it is kept in (None: not marked)."""
    v = s.status.get(mark)
    if v is None:
        return None
    if isinstance(v, dict):
        return float(v.get("since", v.get("until", 0)))
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return 0.0


def _pick(span, s, day: float, mark: str) -> float:
    lo, hi = float(span[0]), float(span[1])
    if hi <= lo:
        return lo
    h = (int(s.id) * 7919 + int(day) * 31 + sum(map(ord, mark))) % 1000
    return lo + (hi - lo) * h / 999.0


def add(world, s, mark: str, day: float, tables=None, **data) -> None:
    """Mark a settlement (the one door in). Day-form and name-form marks keep their old values; a record takes
    `since` and the data given, and a `lasts` span from marks.json when it is given no `until`."""
    if mark in DAY_FORM:
        s.status[mark] = day
        return
    if mark in NAME_FORM:
        s.status[mark] = data.get("name", data.get("by", ""))
        return
    rec = {"since": day}
    rec.update(data)
    spec = table(tables).get(mark, {}) if tables is not None else {}
    if "until" not in rec and spec.get("lasts"):
        rec["until"] = day + _pick(spec["lasts"], s, day, mark)
    s.status[mark] = rec


def lift(world, s, mark: str) -> None:
    s.status.pop(mark, None)


def age(world, tables, day: float) -> list[tuple]:
    """Every mark a day older: records past their `until` end, marks past their `ages` span pass into the next one
    (burning -> burned -> rebuilding). Returns what changed, as (settlement, old mark, new mark or None)."""
    spec = table(tables)
    out = []
    for s in world.settlements:
        for mark in list(s.status):
            if mark in OWNED:
                continue
            v = s.status.get(mark)
            d = spec.get(mark, {})
            ages = d.get("ages")
            ended = False
            if isinstance(v, dict) and "until" in v:
                ended = float(v["until"]) < day
            elif ages:
                start = since(s, mark)
                ended = start is not None and day > start + _pick(ages["after"], s, start, mark)
            if not ended:
                continue
            into = ages.get("into") if ages else None
            lift(world, s, mark)
            if into:
                extra = {"was": int(s.population)} if into == "rebuilding" else {}
                add(world, s, into, day, tables, **extra)
            out.append((s, mark, into))
    return out


# ---------------------------------------------------------------------------- words
def _by(world, s, mark: str) -> str:
    v = s.status.get(mark)
    if isinstance(v, str):
        return v
    if not isinstance(v, dict):
        return ""
    by = v.get("by")
    if isinstance(by, int) and getattr(world, "factions", None):
        f = world.factions.get(by)
        return f.name if f is not None else ""
    return str(by) if by else ""


def label(tables, s) -> list[str]:
    """The marks as the world map's words, coloured: ["<danger>under siege</>", ...]."""
    spec = table(tables)
    out = []
    for mark in marks_of(s):
        d = spec.get(mark)
        if d is not None and d.get("label"):
            out.append(f"<{d.get('colour', 'warn')}>{d['label']}</>")
    return out


def words(world, tables, s, which: str, rng) -> list[str]:
    """A line of each mark's words of a kind ("troubles", "moments", "description"), filled with the town and who did
    it: one line per mark."""
    from realmwalker.core.textgen import escape_markup

    spec = table(tables)
    out = []
    for mark in marks_of(s):
        lines = spec.get(mark, {}).get(which)
        if not lines:
            continue
        by = _by(world, s, mark)
        values = {"town": escape_markup(s.name), "by": escape_markup(by) or "something",
                  "by_part": f" by {escape_markup(by)}" if by else ""}
        text = rng.choice(list(lines))
        for k, v in values.items():
            text = text.replace("{" + k + "}", v)
        out.append(text)
    return out
