"""Content packs: each expansion's data, kept in its own folder and merged over the base files (docs/EXPANSIONS.md §4.1).

    data/packs/06_tieflings_warlocks/
        pack.json            the expansion's record (name, tagline, icon, accent, status, version, adds...)
        creatures.json       a fragment with the same shape as data/creatures.json
        creatures.devils.json   ...or several fragments of one file, merged the same way
        conditions.json      a kind of file only packs have (registered in schemas.DATA_FILES / PACK_ONLY)

How a fragment merges, file by file, in pack order:
- A file's top-level keys are its sections ("creatures", "encounters"...). A section that is a dict on both sides
  merges entry by entry: a new entry is added; an entry the base (or an earlier pack) already has is an error, unless
  the fragment's entry says "_replace": true (it takes the place of the old one) or "_merge": true (its own keys merge
  into the old one, by the same rules, one level down).
- A list grows only when asked: {"_append": [...]} in place of the list adds to it; anything else defined twice is an
  error.
- Keys starting with "_" are comments and flags, and are not copied.

Every entry remembers where it came from (provenance): "base", or the pack's id. The registry answers origin() and
added_by() from it, so the main menu can count what each expansion brought and the codex test can check it.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PACKS_DIR = "packs"
PACK_FILE = "pack.json"
BASE = "base"


@dataclass
class Pack:
    folder: Path
    record: dict
    fragments: dict[str, list[Path]] = field(default_factory=dict)  # base file name -> fragment paths

    @property
    def id(self) -> str:
        return self.record["id"]

    @property
    def order(self) -> int:
        return int(self.record["order"])


def find_packs(data_dir: Path, errors: list[str]) -> list[Pack]:
    """Every pack under data/packs, in their order (a pack whose record is broken is reported and left out)."""
    from realmwalker.data.schemas import PACK

    root = data_dir / PACKS_DIR
    if not root.is_dir():
        return []
    packs: list[Pack] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        where = f"data/{PACKS_DIR}/{folder.name}/{PACK_FILE}"
        path = folder / PACK_FILE
        if not path.exists():
            errors.append(f"{where} is missing (every pack needs its record).")
            continue
        record = _read(path, where, errors)
        if record is None:
            continue
        problems: list[str] = []
        PACK.check(record, "", problems)
        if problems:
            errors.extend(f"{where}: {p}" for p in problems)
            continue
        pack = Pack(folder, record)
        for frag in sorted(folder.glob("*.json")):
            if frag.name == PACK_FILE:
                continue
            base = frag.name.split(".", 1)[0] + ".json"  # creatures.devils.json -> creatures.json
            pack.fragments.setdefault(base, []).append(frag)
        packs.append(pack)
    ids = [p.id for p in packs]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"data/{PACKS_DIR}: two packs are called '{dup}'.")
    orders = [p.order for p in packs]
    for dup in sorted({o for o in orders if orders.count(o) > 1}):
        errors.append(f"data/{PACKS_DIR}: two packs have order {dup}.")
    packs.sort(key=lambda p: (p.order, p.id))
    return packs


def _read(path: Path, where: str, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{where}: line {exc.lineno}, column {exc.colno}: {exc.msg}.")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{where}: could not be read ({exc}).")
    return None


def _clean(value: Any) -> Any:
    """A deep copy without the "_" flags and comments of a fragment's dicts (the base's own comments stay in base)."""
    if isinstance(value, dict):
        if set(value) == {"_append"}:
            return copy.deepcopy(value["_append"])
        return {k: _clean(v) for k, v in value.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


class Provenance:
    """Where each entry of the merged data came from: (file, section, key) -> "base" or a pack id."""

    def __init__(self) -> None:
        self.of: dict[tuple[str, str, str], str] = {}

    def note_base(self, filename: str, data: Any) -> None:
        if not isinstance(data, dict):
            return
        for section, value in data.items():
            if isinstance(value, dict) and not section.startswith("_"):
                for key in value:
                    if not str(key).startswith("_"):
                        self.of[(filename, section, str(key))] = BASE

    def origin(self, filename: str, key: str, section: str | None = None) -> str | None:
        if section is not None:
            return self.of.get((filename, section, key))
        for (f, _, k), who in self.of.items():
            if f == filename and k == key:
                return who
        return None

    def added_by(self, pack_id: str) -> dict[tuple[str, str], int]:
        out: dict[tuple[str, str], int] = {}
        for (f, s, _), who in self.of.items():
            if who == pack_id:
                out[(f, s)] = out.get((f, s), 0) + 1
        return out


def merge_fragment(base: dict, frag: dict, *, filename: str, pack_id: str, where: str, prov: Provenance,
                   errors: list[str]) -> None:
    """Merge one fragment into the base data of a file (in place), by the rules in the module's notes."""
    if not isinstance(frag, dict):
        errors.append(f"{where}: a fragment must be an object, like the file it adds to.")
        return
    for section, value in frag.items():
        if str(section).startswith("_"):
            continue
        if section not in base:
            base[section] = _clean(value)
            if isinstance(value, dict):
                for key in value:
                    if not str(key).startswith("_"):
                        prov.of[(filename, section, str(key))] = pack_id
            continue
        old = base[section]
        if isinstance(value, dict) and set(value) == {"_append"} and isinstance(old, list):
            old.extend(_clean(value["_append"]))
        elif isinstance(old, dict) and isinstance(value, dict):
            if value.get("_replace"):
                base[section] = _clean(value)
                continue
            for key, entry in value.items():
                if str(key).startswith("_"):
                    continue
                _merge_entry(old, str(key), entry, filename=filename, section=section, pack_id=pack_id,
                             where=f"{where}: {section}.{key}", prov=prov, errors=errors)
        else:
            errors.append(f"{where}: '{section}' is already defined (to add to a list, give {{\"_append\": [...]}}).")


def _merge_entry(container: dict, key: str, entry: Any, *, filename: str, section: str, pack_id: str, where: str,
                 prov: Provenance, errors: list[str]) -> None:
    if key not in container:
        container[key] = _clean(entry)
        prov.of[(filename, section, key)] = pack_id
        return
    if isinstance(entry, dict) and entry.get("_replace"):
        container[key] = _clean(entry)
        prov.of[(filename, section, key)] = pack_id
        return
    old = container[key]
    if isinstance(entry, dict) and entry.get("_merge") and isinstance(old, dict):
        for k, v in entry.items():
            if str(k).startswith("_"):
                continue
            if isinstance(v, dict) and set(v) == {"_append"} and isinstance(old.get(k), list):
                old[k].extend(_clean(v["_append"]))
            elif k not in old or (isinstance(v, dict) and (v.get("_replace") or v.get("_merge"))):
                _merge_entry(old, str(k), v, filename=filename, section=section, pack_id=pack_id,
                             where=f"{where}.{k}", prov=prov, errors=errors)
            else:
                errors.append(f"{where}.{k} is already defined (say \"_replace\": true to take its place).")
        return
    errors.append(f"{where} is already defined by {prov.of.get((filename, section, key), BASE)} "
                  "(say \"_replace\": true to take its place, or \"_merge\": true to add to it).")


def merge_packs(files: dict[str, Any], packs: list[Pack], known: set[str], prov: Provenance,
                errors: list[str]) -> None:
    """Merge every pack's fragments into the loaded base files, in pack order."""
    for pack in packs:
        for filename, paths in sorted(pack.fragments.items()):
            if filename not in known:
                errors.append(f"data/{PACKS_DIR}/{pack.folder.name}/{paths[0].name}: there is no data file "
                              f"called {filename} for it to add to.")
                continue
            for path in paths:
                where = f"data/{PACKS_DIR}/{pack.folder.name}/{path.name}"
                frag = _read(path, where, errors)
                if frag is None or filename not in files:
                    continue
                merge_fragment(files[filename], frag, filename=filename, pack_id=pack.id, where=where, prov=prov,
                               errors=errors)
