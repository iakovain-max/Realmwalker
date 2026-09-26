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


# Words starting with a vowel letter that still take "a" (a one-eyed man, a useful knife, a ewe), and the few
# with a silent h that take "an"; a lone "a" before a little word ("plan a is") is a letter, not an article.
_A_BEFORE = ("one", "once", "uni", "use", "usu", "ure", "uti", "eu", "ewe", "uku")
_AN_BEFORE = ("hour", "honest", "honour", "honor", "heir")
_NOT_ARTICLE = {"is", "in", "and", "or", "as", "at", "if", "it", "of", "on", "an", "am", "are", "a", "i", "up"}
_A_VOWEL_RE = re.compile(r"\b([Aa]) ([AEIOUaeiouHh][\w-]*)")


def _an(m: re.Match) -> str:
    word = m.group(2).lower()
    if word in _NOT_ARTICLE:
        return m.group(0)
    if word[0] == "h":
        return f"{m.group(1)}n {m.group(2)}" if word.startswith(_AN_BEFORE) else m.group(0)
    return m.group(0) if word.startswith(_A_BEFORE) else f"{m.group(1)}n {m.group(2)}"


def articles(text: str) -> str:
    """Fix "a" before a vowel: a template's "in a {season}" filled with "autumn" reads "in an autumn"."""
    return _A_VOWEL_RE.sub(_an, text)


def tidy(text: str) -> str:
    text = articles(re.sub(r"\s+", " ", text).strip())
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    # Capitalise the start of each sentence, and of speech that opens one ("the Grey Wolf. A wolf..." -> "The...").
    return re.sub(r"(^|[.!?]\s+)([\"“]?)([a-z])", lambda m: m.group(1) + m.group(2) + m.group(3).upper(), text)


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
