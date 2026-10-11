"""The expansions (docs/EXPANSIONS.md §4.1, §4.13): what the main menu's shelf shows, read from each pack's record.

Logic only, no UI. A pack under construction ("status": "planned") is loaded like any other but not shown: the shelf
and the Expansions screen show released expansions only, in their order.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


@dataclass
class Expansion:
    id: str
    order: int
    name: str
    tagline: str
    icon: str
    accent: tuple[int, int, int]
    status: str
    version: str
    released_on: str
    adds: list[str] = field(default_factory=list)
    counts: list[str] = field(default_factory=list)  # "49 fiends", from what the pack really added

    @property
    def released(self) -> bool:
        return self.status == "released"

    def when(self) -> str:
        """'Version 1.6 · 2 November 2026' (the date only once it is out)."""
        version = ".".join(self.version.split(".")[:2]) if self.version else ""
        parts = [f"Version {version}"] if version else []
        try:
            d = datetime.date.fromisoformat(self.released_on)
            parts.append(f"{d.day} {MONTHS[d.month - 1]} {d.year}")
        except ValueError:
            pass
        return " · ".join(parts)


def count_lines(data, pack) -> list[str]:
    """What the pack's record asks to count ([file, section, label]), from what it really added."""
    added = data.added_by(pack.id)
    out = []
    for filename, section, label in pack.record.get("counts", []):
        n = added.get((filename, section), 0)
        if n:
            out.append(f"{n} {label}")
    return out


def all_expansions(data) -> list[Expansion]:
    """Every pack, released or not, in order."""
    out = []
    for pack in data.packs:
        r = pack.record
        out.append(Expansion(id=r["id"], order=int(r["order"]), name=r["name"], tagline=r["tagline"], icon=r["icon"],
                             accent=tuple(int(c) for c in r["accent"]), status=r["status"], version=r["version"],
                             released_on=r["released_on"], adds=list(r["adds"]), counts=count_lines(data, pack)))
    return out


def released(data) -> list[Expansion]:
    """The expansions on the shelf: released ones, in order."""
    return [e for e in all_expansions(data) if e.released]
