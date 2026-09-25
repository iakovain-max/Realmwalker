"""Built-in text templates: the fallback writer used whenever the AI is unavailable.

Templates use {key} slots. Each slot is filled from `values` if given, otherwise with a
random entry from `tables[key]`; entries may contain further slots (up to a few levels deep).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from realmwalker.core.rng import RNG

_SLOT_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
MAX_DEPTH = 6


def fill(template: str, rng: RNG, tables: Mapping[str, Sequence[str]], values: Mapping[str, str] | None = None) -> str:
    values = values or {}

    def expand(text: str, depth: int) -> str:
        if depth > MAX_DEPTH:
            return text

        def sub(m: re.Match) -> str:
            key = m.group(1)
            if key in values:
                return str(values[key])
            options = tables.get(key)
            if not options:
                return m.group(0)
            return expand(rng.choice(list(options)), depth + 1)

        return _SLOT_RE.sub(sub, text)

    return tidy(expand(template, 0))


def tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    # Capitalise the start of each sentence.
    return re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def pronoun_values(sex: str) -> dict[str, str]:
    """Slots for writing about someone: {they} {them} {their} {themselves} {They} {Their}, and {s} {are} {have}
    for the verb that follows ("{they} walk{s}")."""
    if sex == "female":
        p = {"they": "she", "them": "her", "their": "her", "themselves": "herself", "s": "s", "are": "is", "have": "has"}
    elif sex == "male":
        p = {"they": "he", "them": "him", "their": "his", "themselves": "himself", "s": "s", "are": "is", "have": "has"}
    else:
        p = {"they": "they", "them": "them", "their": "their", "themselves": "themselves", "s": "", "are": "are",
             "have": "have"}
    p["They"], p["Their"] = p["they"].capitalize(), p["their"].capitalize()
    return p


def a_or_an(word: str) -> str:
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def slots(template: str) -> list[str]:
    return _SLOT_RE.findall(template)


def escape_markup(text: str) -> str:
    """Make outside text (AI or player) safe to show inside colour markup (same as ui.markup.escape)."""
    return text.replace("<", "(").replace(">", ")")
