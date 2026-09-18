"""The expected shape of every file in data/. Add an entry here when adding a new data file."""

from __future__ import annotations

from realmwalker.core.schema import List, Map, Obj, Spec, Str


def word_list(min_items: int = 1, max_len: int = 80) -> List:
    return List(Str(max_len=max_len), min_items=min_items)


def table_set(*names: str, max_len: int = 600) -> Obj:
    """A group of fallback-text tables, each a non-empty list of strings."""
    return Obj({name: List(Str(max_len=max_len), min_items=1) for name in names})


CULTURE = Obj(
    {
        "label": Str(max_len=60),
        "male": word_list(5, 30),
        "female": word_list(5, 30),
        "family": word_list(5, 40),
    }
)

NAMES = Obj({"cultures": Map(CULTURE, min_items=1)})

TAVERN_TABLES = (
    "name_pattern", "adjective", "noun", "part", "house", "sign_state", "building", "light", "smell",
    "sound", "crowd", "detail", "description", "manner", "overheard", "region", "season",
)

FALLBACK_TEXT = Obj({"tavern": table_set(*TAVERN_TABLES)})

# Slots that code fills in itself (not from a table), per table set.
RUNTIME_SLOTS: dict[str, set[str]] = {
    "tavern": {"family", "keeper"},
}

DATA_FILES: dict[str, Spec] = {
    "names.json": NAMES,
    "fallback_text.json": FALLBACK_TEXT,
}
