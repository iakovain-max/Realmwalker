"""Fast lookup tables built from data files: biomes (overworld) and terrain (local maps).

Maps store small integer indices; these tables turn them into names, costs and flags with numpy indexing, so
path costs and the like never loop over cells in Python.
"""

from __future__ import annotations

import numpy as np

from realmwalker.data.registry import DataRegistry


class BiomeTable:
    def __init__(self, data: dict) -> None:
        biomes = data["biomes"]
        self.ids: list[str] = [k for k in biomes if not k.startswith("_")]
        self.index = {bid: i for i, bid in enumerate(self.ids)}
        self.defs = [biomes[bid] for bid in self.ids]
        self.names = [d["name"] for d in self.defs]
        self.passable = np.array([d["passable"] for d in self.defs], dtype=bool)
        self.move_hours = np.array([d["move_hours"] for d in self.defs], dtype=np.float32)
        # Each land's family: the older land it behaves like ("dunes" -> "desert"), itself for the old ones.
        self.families: list[str] = [d.get("family", bid) for bid, d in zip(self.ids, self.defs)]
        self.family_index = np.array([self.index[f] for f in self.families], dtype=np.int32)

    def id(self, name: str) -> int:
        return self.index[name]

    def family(self, bid: str) -> str:
        """The land this one behaves like: 'jungle' -> 'forest'; an unknown id is its own family."""
        i = self.index.get(bid)
        return self.families[i] if i is not None else bid

    def of_family(self, *families: str) -> list[int]:
        """The indices of every land in these families (for masks: np.isin(biome, B.of_family("forest")))."""
        return [i for i, f in enumerate(self.families) if f in families]

    def lookup(self, table: dict, bid: str, default=None):
        """A value kept per land, for this land or else for its family."""
        if bid in table:
            return table[bid]
        return table.get(self.family(bid), default)

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
        self.data = data  # the registry these tables were built from (its packs, provenance)
        self.biomes = BiomeTable(data["biomes.json"])
        self.terrain = TerrainTable(data["local_terrain.json"])
        self.calendar_data = data["calendar.json"]
        self.sites = data["sites.json"]
        self.place_names = data["place_names.json"]
        self.names = data["names.json"]
        from realmwalker.world.cultures import Cultures

        self.cultures = Cultures(data["cultures.json"], data["names.json"], data["factions.json"])
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

        self.creatures = CreatureTable(data["creatures.json"], data["statblocks.json"])
        self.sprites = data["sprites.json"]  # which picture shows what (ui/gfx)
        self.spells = SpellTable(data["spells.json"])
        self.items.add_scrolls(self.spells)
        self.combat_text = data["combat_text.json"]
        self.conditions = data["conditions.json"]  # the 2024 conditions (rules/engine/conditions.py)
        self.traits = data["traits.json"]  # traits and features as definitions (rules/engine/traits.py)
        self.feats = data["feats.json"]  # feats (rules/feats.py); what they do in a fight is their trait
        from realmwalker.rules.health import DiseaseTable

        self.diseases = DiseaseTable(data["diseases.json"])
        self.health = data["health.json"]
        self.camping = data["camping.json"]
        self.people = data["people.json"]
        self.dialogue = data["dialogue.json"]
        self.economy = data["economy.json"]
        self.factions = data["factions.json"]
        self.law = data["law.json"]
        self.politics = data["politics.json"]
        self.history = data["history.json"]
        self.companions = data["companions.json"]
        self.uniques = data["uniques.json"]
        self.magic = data["magic.json"]
        self.treasure = data["treasure.json"]
        self.wonders = data["wonders.json"]
        self.towns = data["towns.json"]
        self.trinkets = {t["id"]: t for t in data["trinkets.json"]["trinkets"]}  # keepsakes (rules/items.make_trinket)
        self.trinket_chance = data["trinkets.json"]["chance"]  # in a pocket, in a chest
        self.quests = data["quests.json"]
        self.travel_events = {k: v for k, v in data["travel_events.json"]["events"].items() if not k.startswith("_")}
