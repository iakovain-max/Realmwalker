"""Built-in names for places: settlements by culture, regions by the people of their land, old sites. The AI may
later add descriptions, but names come from here so they are stable and cost no energy.

With a world's name forge (world/names.py) settlements use the people's parts with this world's grown stems, and
regions are named in the people's own words ('Svartvatn', 'Jabal al-Nar'); without one (or for a land no people
claims) the old English region patterns of data/place_names.json 'regions' are used.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.rng import RNG


class Namer:
    def __init__(self, place_names: dict, rng: RNG, forge=None) -> None:
        self.data = place_names
        self.rng = rng
        self.forge = forge
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
        if self.forge is not None:
            tables = self.forge.settlement_tables(culture)
        else:
            tables = self.data["settlements"].get(culture) or self.data["settlements"]["heartland"]

        def make() -> str:
            pattern = self.rng.choice(tables["patterns"])
            name = textgen.fill(pattern, self.rng, tables)
            return name[0].upper() + name[1:]

        return self._unique(make)

    def region(self, kind: str, culture: str | None = None) -> str:
        if self.forge is not None and culture:
            return self._unique(lambda: self.forge.geo(culture, kind, self.rng))
        regions = self.data["regions"]
        patterns = regions.get(kind) or regions["plains"]
        # Nobody lives here to name it after a place or a person: their names are made of the old words.
        plain = [p for p in patterns if "{root}" not in p and "{person}" not in p] or patterns

        def make() -> str:
            values = {"root": self.rng.choice(regions["stem"]), "person": self.rng.choice(regions["noun"])}
            name = textgen.fill(self.rng.choice(plain), self.rng, regions, values)
            # Stored as used mid-sentence ("you enter the Black Fen"); capitalised when it starts one.
            return "the " + name[4:] if name.startswith("The ") else name

        return self._unique(make)

    def site(self, kind: str, culture: str | None = None) -> str:
        regions = self.data["regions"]

        def make() -> str:
            adjective = self.rng.choice(regions["adjective"])
            noun = self.rng.choice(regions["noun"])
            stem = self.forge.stem(culture, self.rng) if self.forge is not None and culture else \
                self.rng.choice(regions["stem"])
            options = {
                "ruin": [f"the ruins of {stem}hall", f"the {adjective} Ruins", f"old {stem}keep"],
                "cave": [f"the {adjective} Cave", f"the {noun}'s Hole", f"{stem}hole"],
                "barrow": [f"the {adjective} Barrow", f"the {noun}'s Barrow", f"{stem} Howe"],
                "tower": [f"the {adjective} Tower", f"{stem} Tower", f"the {noun}'s Tower"],
            }.get(kind, [f"the {adjective} Place"])
            return self.rng.choice(options)

        return self._unique(make)
