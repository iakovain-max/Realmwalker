"""Built-in names for places: settlements by culture, regions by biome. The AI may later add
descriptions, but names come from here so they are stable and cost no energy."""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.rng import RNG


class Namer:
    def __init__(self, place_names: dict, rng: RNG) -> None:
        self.data = place_names
        self.rng = rng
        self.used: set[str] = set()

    def _unique(self, make) -> str:
        name = make()
        for _ in range(30):
            if name not in self.used:
                break
            name = make()
        else:
            name = f"{name} {self.rng.choice(['Minor', 'Nether', 'Upper', 'Lower', 'Old', 'New'])}"
        self.used.add(name)
        return name

    def settlement(self, culture: str) -> str:
        tables = self.data["settlements"].get(culture) or self.data["settlements"]["heartland"]

        def make() -> str:
            pattern = self.rng.choice(tables["patterns"])
            name = textgen.fill(pattern, self.rng, tables)
            # Avoid doubled letters at the join like "Ashhholt" and ugly triple consonants.
            return name[0].upper() + name[1:]

        return self._unique(make)

    def region(self, kind: str) -> str:
        regions = self.data["regions"]
        patterns = regions.get(kind) or regions["plains"]

        def make() -> str:
            name = textgen.fill(self.rng.choice(patterns), self.rng, regions)
            # Stored as used mid-sentence ("you enter the Black Fen"); capitalised when it starts one.
            return "the " + name[4:] if name.startswith("The ") else name

        return self._unique(make)

    def site(self, kind: str) -> str:
        regions = self.data["regions"]

        def make() -> str:
            adjective = self.rng.choice(regions["adjective"])
            noun = self.rng.choice(regions["noun"])
            stem = self.rng.choice(regions["stem"])
            options = {
                "ruin": [f"the ruins of {stem}hall", f"the {adjective} Ruins", f"old {stem}keep"],
                "cave": [f"the {adjective} Cave", f"the {noun}'s Hole", f"{stem}hole"],
                "barrow": [f"the {adjective} Barrow", f"the {noun}'s Barrow", f"{stem} Howe"],
                "tower": [f"the {adjective} Tower", f"{stem} Tower", f"the {noun}'s Tower"],
            }.get(kind, [f"the {adjective} Place"])
            return self.rng.choice(options)

        return self._unique(make)
