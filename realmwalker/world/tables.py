"""Fast lookup tables built from data files: biomes (overworld) and terrain (local maps).

Maps store small integer indices; these tables turn them into glyphs, colours, costs and flags
with numpy indexing, so drawing and path costs never loop over cells in Python.
"""

from __future__ import annotations

import numpy as np

from realmwalker.data.registry import DataRegistry


def _glyph_table(defs: list[dict], key: str = "glyphs") -> tuple[np.ndarray, np.ndarray]:
    width = max(len(d[key]) for d in defs)
    table = np.zeros((len(defs), width), dtype=np.int32)
    counts = np.zeros(len(defs), dtype=np.int32)
    for i, d in enumerate(defs):
        glyphs = [ord(g) for g in d[key]]
        counts[i] = len(glyphs)
        for j in range(width):
            table[i, j] = glyphs[j % len(glyphs)]
    return table, counts


class BiomeTable:
    def __init__(self, data: dict) -> None:
        biomes = data["biomes"]
        self.ids: list[str] = [k for k in biomes if not k.startswith("_")]
        self.index = {bid: i for i, bid in enumerate(self.ids)}
        self.defs = [biomes[bid] for bid in self.ids]
        self.names = [d["name"] for d in self.defs]
        self.passable = np.array([d["passable"] for d in self.defs], dtype=bool)
        self.move_hours = np.array([d["move_hours"] for d in self.defs], dtype=np.float32)
        self.fg = np.array([d["fg"] for d in self.defs], dtype=np.uint8)
        self.bg = np.array([d["bg"] for d in self.defs], dtype=np.uint8)
        self.glyphs, self.glyph_counts = _glyph_table(self.defs)

    def id(self, name: str) -> int:
        return self.index[name]

    def __getitem__(self, i: int) -> dict:
        return self.defs[i]


class TerrainTable:
    def __init__(self, data: dict) -> None:
        terrain = data["terrain"]
        self.ids: list[str] = [k for k in terrain if not k.startswith("_")]
        self.index = {tid: i for i, tid in enumerate(self.ids)}
        self.defs = [terrain[tid] for tid in self.ids]
        self.walk = np.array([d["walk"] for d in self.defs], dtype=bool)
        self.see = np.array([d["see"] for d in self.defs], dtype=bool)
        self.cost = np.array([d["cost"] for d in self.defs], dtype=np.float32)
        self.fg = np.array([d["fg"] for d in self.defs], dtype=np.uint8)
        self.bg = np.array([d["bg"] for d in self.defs], dtype=np.uint8)
        self.glyphs, self.glyph_counts = _glyph_table(self.defs)
        self.tags = [set(d["tags"]) for d in self.defs]

    def id(self, name: str) -> int:
        return self.index[name]

    def has_tag(self, index: int, tag: str) -> bool:
        return tag in self.tags[index]

    def tag_mask(self, tag: str) -> np.ndarray:
        return np.array([tag in t for t in self.tags], dtype=bool)

    def __getitem__(self, i: int) -> dict:
        return self.defs[i]


class Tables:
    """All lookup tables for one game session."""

    def __init__(self, data: DataRegistry) -> None:
        self.biomes = BiomeTable(data["biomes.json"])
        self.terrain = TerrainTable(data["local_terrain.json"])
        self.calendar_data = data["calendar.json"]
        self.sites = data["sites.json"]
        self.place_names = data["place_names.json"]
        self.names = data["names.json"]
        from realmwalker.rules.items import ItemTable
        from realmwalker.world.calendar import Calendar

        self.calendar = Calendar(self.calendar_data)
        self.rules = data["rules.json"]
        self.races = {k: v for k, v in data["races.json"]["races"].items() if not k.startswith("_")}
        self.classes = {k: v for k, v in data["classes.json"]["classes"].items() if not k.startswith("_")}
        self.backgrounds_data = data["backgrounds.json"]
        self.backgrounds = {k: v for k, v in self.backgrounds_data["backgrounds"].items() if not k.startswith("_")}
        self.items = ItemTable(data["items.json"])
        self.appearance = data["appearance.json"]
        self.fallback = data["fallback_text.json"]
        from realmwalker.rules.creatures import CreatureTable
        from realmwalker.rules.spells import SpellTable

        self.creatures = CreatureTable(data["creatures.json"])
        self.spells = SpellTable(data["spells.json"])
        self.combat_text = data["combat_text.json"]
        from realmwalker.rules.health import DiseaseTable

        self.diseases = DiseaseTable(data["diseases.json"])
        self.health = data["health.json"]
        self.camping = data["camping.json"]
        self.people = data["people.json"]
        self.dialogue = data["dialogue.json"]
        self.travel_events = {k: v for k, v in data["travel_events.json"]["events"].items() if not k.startswith("_")}
