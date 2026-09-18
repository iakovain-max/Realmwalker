"""Loads every data file, checks it against its schema and reports problems in plain words."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from realmwalker.core import textgen
from realmwalker.data.schemas import DATA_FILES, RUNTIME_SLOTS

log = logging.getLogger("realmwalker.data")


class DataRegistry:
    def __init__(self, files: dict[str, Any]) -> None:
        self._files = files

    def __getitem__(self, name: str) -> Any:
        return self._files[name]

    def get(self, name: str, default: Any = None) -> Any:
        return self._files.get(name, default)

    @property
    def names(self) -> dict:
        return self._files.get("names.json", {"cultures": {}})

    @property
    def fallback(self) -> dict:
        return self._files.get("fallback_text.json", {})

    @classmethod
    def load(cls, data_dir: Path) -> tuple[DataRegistry, list[str]]:
        files: dict[str, Any] = {}
        errors: list[str] = []
        for filename, spec in DATA_FILES.items():
            path = data_dir / filename
            if not path.exists():
                errors.append(f"data/{filename} is missing.")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"data/{filename}: line {exc.lineno}, column {exc.colno}: {exc.msg}.")
                continue
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"data/{filename}: could not be read ({exc}).")
                continue
            file_errors: list[str] = []
            spec.check(data, "", file_errors)
            errors.extend(f"data/{filename}: {e}" for e in file_errors)
            if not file_errors:
                files[filename] = data
        if "fallback_text.json" in files:
            errors.extend(check_template_slots(files["fallback_text.json"]))
        for e in errors:
            log.error("Data problem: %s", e)
        return cls(files), errors


def check_template_slots(fallback: dict) -> list[str]:
    """Every {slot} in a fallback table must name another table in the same set, or a runtime value."""
    errors = []
    for set_name, tables in fallback.items():
        if set_name.startswith("_") or not isinstance(tables, dict):
            continue
        allowed = set(tables) | RUNTIME_SLOTS.get(set_name, set())
        for table_name, entries in tables.items():
            for i, entry in enumerate(entries):
                for slot in textgen.slots(entry):
                    if slot not in allowed:
                        errors.append(
                            f"data/fallback_text.json: {set_name}.{table_name}[{i}] uses {{{slot}}}, "
                            f"but there is no '{slot}' list in '{set_name}'."
                        )
    return errors
