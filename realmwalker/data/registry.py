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
        errors.extend(check_cross_references(files))
        for e in errors:
            log.error("Data problem: %s", e)
        return cls(files), errors


def check_cross_references(files: dict[str, Any]) -> list[str]:
    """Things one file refers to in another must exist (e.g. a biome's ground types)."""
    from realmwalker.data.schemas import REQUIRED_BIOMES, REQUIRED_SETTLEMENT_TYPES

    errors: list[str] = []
    terrain = set(files.get("local_terrain.json", {}).get("terrain", {}))
    biomes = files.get("biomes.json", {}).get("biomes", {})
    if biomes:
        for bid in REQUIRED_BIOMES:
            if bid not in biomes:
                errors.append(f"data/biomes.json: the game needs a biome called '{bid}'.")
    if biomes and terrain:
        for bid, b in biomes.items():
            if bid.startswith("_"):
                continue
            for i, pair in enumerate(b["local"]["ground"]):
                if not isinstance(pair[0], str) or pair[0] not in terrain:
                    errors.append(f"data/biomes.json: {bid}.local.ground[{i}] names unknown terrain {pair[0]!r}.")
                if not isinstance(pair[1], (int, float)) or pair[1] <= 0:
                    errors.append(f"data/biomes.json: {bid}.local.ground[{i}] needs a positive weight.")
            for t in b["local"]["tree_types"]:
                if t not in terrain:
                    errors.append(f"data/biomes.json: {bid}.local.tree_types names unknown terrain {t!r}.")
    sites = files.get("sites.json", {})
    if sites:
        for kind in REQUIRED_SETTLEMENT_TYPES:
            if kind not in sites.get("settlement_types", {}):
                errors.append(f"data/sites.json: the game needs a settlement type called '{kind}'.")
    names = files.get("place_names.json", {})
    for culture, tables in names.get("settlements", {}).items():
        for pattern in tables.get("patterns", []):
            for slot in textgen.slots(pattern):
                if slot not in tables:
                    errors.append(f"data/place_names.json: settlements.{culture} pattern {pattern!r} uses "
                                  f"{{{slot}}} but there is no '{slot}' list.")
    errors.extend(_check_character_refs(files))
    regions = names.get("regions", {})
    for kind, patterns in regions.items():
        for pattern in patterns:
            for slot in textgen.slots(pattern):
                if slot not in regions:
                    errors.append(f"data/place_names.json: regions.{kind} pattern {pattern!r} uses {{{slot}}}, "
                                  f"which is not a list in 'regions'.")
    return errors


def _check_character_refs(files: dict[str, Any]) -> list[str]:
    """Races, classes and backgrounds must only mention skills, tools, items and cultures that exist."""
    errors: list[str] = []
    rules = files.get("rules.json")
    items = files.get("items.json", {}).get("items")
    if not rules or items is None:
        return errors
    skills = set(rules["skills"])
    tools = set(rules["tools"])
    cultures = set(files.get("names.json", {}).get("cultures", {}))

    def need(kind: str, value: str, pool: set, where: str) -> None:
        if value not in pool:
            errors.append(f"{where} mentions unknown {kind} '{value}'.")

    for rid, race in files.get("races.json", {}).get("races", {}).items():
        for s in race["skills"]:
            need("skill", s, skills, f"data/races.json: {rid}")
        for t in race.get("tools_choice", []):
            need("tool", t, tools, f"data/races.json: {rid}")
        for c in race["cultures"]:
            if cultures:
                need("culture", c, cultures, f"data/races.json: {rid}")
    for cid, cls in files.get("classes.json", {}).get("classes", {}).items():
        for s in cls["skill_choices"]:
            need("skill", s, skills, f"data/classes.json: {cid}")
        for t in cls["tools"]:
            need("tool", t, tools, f"data/classes.json: {cid}")
        for kit in cls["kits"]:
            for item_id, qty in kit["items"]:
                need("item", item_id, set(items), f"data/classes.json: {cid} kit '{kit['name']}'")
    for bid, bg in files.get("backgrounds.json", {}).get("backgrounds", {}).items():
        for s in bg["skills"]:
            need("skill", s, skills, f"data/backgrounds.json: {bid}")
        for t in bg["tools"]:
            need("tool", t, tools, f"data/backgrounds.json: {bid}")
        for item_id, qty in bg["items"]:
            need("item", item_id, set(items), f"data/backgrounds.json: {bid}")
    for pack, entries in files.get("items.json", {}).get("starting_packs", {}).items():
        for item_id, qty in entries:
            need("item", item_id, set(items), f"data/items.json: starting pack '{pack}'")
    for iid, item in items.items():
        if "ammo" in item:
            need("item", item["ammo"], set(items), f"data/items.json: {iid} ammo")
        if "tool" in item:
            need("tool", item["tool"], tools, f"data/items.json: {iid}")
    return errors


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
