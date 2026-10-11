"""The name forge: every name of a person, place, realm or stretch of country, in the manner of its people.

Each people's pools (data/names.json) are the seed. A world takes most of them and grows new names from the same
sounds (a chain of letters learned from the pool), so no two worlds share their people. A full name is put together
the way that people does it (data/cultures.json "naming"): Bjorn Haraldsson and Sigrid Haraldsdottir, Rashid ibn
Tariq or Rashid al-Qasimi, Ivan Petrovich, Anna Volkova, Fergus mac Aodh. Places come from the people's own
place-name parts (data/place_names.json), with stems grown the same way; geography ("geo") from each people's
words for mountains, lakes and rivers.

forge(world, tables) gives the world's forge (made once, from the world's seed). Logic only: no UI.
"""

from __future__ import annotations

import re
from collections import defaultdict

from realmwalker.core import textgen
from realmwalker.core.rng import RNG

BLOCKED = ("nigg", "fagg", "cunt", "shit", "fuck", "rape", "slut", "whore", "nazi", "piss", "dick", "cock", "twat",
           "wank", "bitch", "kike", "spic", "chink", "anus", "poop", "turd", "allah", "christ", "jesus", "satan",
           "lucifer", "hitler")
BLOCKED_WORDS = {"alah", "allah", "ilah", "illah", "bolg", "azog", "thorin", "frodo", "bilbo", "gandalf", "sauron"}
COMPOUND_FAMILIES = {"dwarven", "halfling", "orcish"}  # English compounds: grown letter by letter they break
SLAVIC_FORMS = (("tskiy", "tskaya"), ("skiy", "skaya"), ("sky", "skaya"), ("skoy", "skaya"), ("ky", "kaya"),
                ("oy", "aya"), ("ov", "ova"), ("ev", "eva"), ("in", "ina"), ("yn", "yna"))
GREEK_FORMS = (("os", "ou"), ("is", "i"), ("as", "a"), ("es", "e"))
KEEP_REAL = 0.72  # of a pool a world keeps
GROWN = 0.4  # new names grown, as a share of the pool
GEO_FAMILY = {"steppe": ("plains",), "savanna": ("plains",), "jungle": ("forest",), "fey_forest": ("forest",),
              "dunes": ("desert",), "salt_flat": ("salt", "desert"), "badlands": ("hills",),
              "volcanic": ("mountains",), "glacier": ("tundra",), "oasis": ("lake",), "salt": ("lake",)}


# ---------------------------------------------------------------------------- growing names
class Chain:
    """Letters following letters: an order-n chain learned from a list of names."""

    def __init__(self, words: list[str], order: int = 3) -> None:
        self.order = order
        self.next: dict[str, list[str]] = defaultdict(list)
        self.words = {w.lower() for w in words}
        self.long = sorted((w for w in self.words if len(w) >= 5), key=len, reverse=True)
        self.lengths = sorted(len(w) for w in words) or [6]
        for w in words:
            padded = "^" * order + w.lower() + "$"
            for i in range(len(w) + 1):
                self.next[padded[i:i + order]].append(padded[i + order])

    def make(self, rng: RNG, *, tries: int = 40) -> str | None:
        lo = max(4, self.lengths[len(self.lengths) // 10])
        hi = min(14, self.lengths[len(self.lengths) // 2] + 2)
        for _ in range(tries):
            key = "^" * self.order
            out = ""
            while True:
                options = self.next.get(key)
                if not options:
                    break
                ch = rng.choice(options)
                if ch == "$":
                    break
                out += ch
                key = (key + ch)[-self.order:]
                if len(out) > hi:
                    break
            if not (lo <= len(out) <= hi) or out in self.words or not good(out):
                continue
            if any(w in out for w in self.long):
                continue  # a real name with more stuck on: two names run together ("Godricholas")
            return out[:1].upper() + out[1:]
        return None


def good(word: str) -> bool:
    w = word.lower()
    if w in BLOCKED_WORDS or any(b in w for b in BLOCKED):
        return False
    if re.search(r"(.)\1\1", w) or re.search(r"[^aeiouy]{5}", w) or re.search(r"[aeiou]{4}", w):
        return False
    return not w.endswith(("-", "'"))


# ---------------------------------------------------------------------------- the forge
class NameForge:
    def __init__(self, seed: int, tables) -> None:
        self.t = tables
        self.cultures = tables.cultures
        self.rng = RNG(seed, "names")
        self.pools: dict[tuple[str, str], list[str]] = {}
        self.stems: dict[str, list[str]] = {}
        self.chains: dict[tuple[str, str], Chain] = {}
        self.regions = tables.place_names["regions"]
        self.geo_data = tables.place_names.get("geo", {})
        for cid in self.cultures.ids:
            pool = self.cultures.pools.get(cid) or self.cultures.pools["heartland"]
            for key in ("male", "female", "family"):
                grow = 0.0 if key == "family" and cid in COMPOUND_FAMILIES else GROWN
                self.pools[(cid, key)] = self._world_pool(cid, key, pool[key], grow=grow)
            parts = tables.place_names["settlements"].get(cid) or tables.place_names["settlements"]["heartland"]
            self.stems[cid] = self._world_pool(cid, "stem", parts["prefix"], grow=0.6)

    def _world_pool(self, cid: str, key: str, real: list[str], grow: float = GROWN) -> list[str]:
        rng = self.rng.child(f"{cid}/{key}")
        keep = [n for n in real if rng.random() < KEEP_REAL] or list(real)
        chain = self.chains[(cid, key)] = Chain(real, order=3 if len(real) >= 40 else 2)
        grown = []
        for _ in range(int(len(real) * grow)):
            n = chain.make(rng)
            if n and n not in grown and n not in keep:
                grown.append(n)
        return keep + grown

    # ------------------------------------------------------------------ parts of names
    def given(self, cid: str, sex: str, rng: RNG, avoid=()) -> str:
        pool = self.pools.get((cid, "female" if sex == "female" else "male")) or self.pools[("heartland", "male")]
        name = rng.choice(pool)
        for _ in range(6):
            if name not in avoid:
                break
            name = rng.choice(pool)
        return name

    def family_base(self, cid: str, rng: RNG, avoid=()) -> str:
        """A family's own name, as its men bear it (world/ages keeps it on the figure)."""
        pool = self.pools.get((cid, "family")) or self.pools[("heartland", "family")]
        options = [n for n in pool if n not in avoid] or pool
        return rng.choice(options)

    def family_for(self, cid: str, base: str, sex: str) -> str:
        """The family name as a man or a woman of this people bears it (Volkov / Volkova, Komnenos / Komnenou)."""
        if sex != "female" or not base:
            return base
        forms = self.cultures.get(cid)["naming"].get("family_forms")
        rules = SLAVIC_FORMS if forms == "slavic" else GREEK_FORMS if forms == "greek" else ()
        for male, female in rules:
            if base.endswith(male):
                return base[: len(base) - len(male)] + female
        return base

    def patronymic(self, cid: str, father: str, sex: str) -> str:
        style = self.cultures.get(cid)["naming"].get("patronymic")
        female = sex == "female"
        if style == "norse":
            joint = "" if father.endswith("s") else "s"
            return f"{father}{joint}{'dottir' if female else 'son'}"
        if style == "gaelic":
            return f"{'nic' if female else 'mac'} {father}"
        if style == "arabic":
            return f"{'bint' if female else 'ibn'} {father}"
        if style == "slavic":
            if father.endswith("ei"):
                stem, male_end, female_end = father[:-1], "evich", "evna"
            elif father.endswith(("i", "y")):
                stem, male_end, female_end = father[:-1], "ievich", "ievna"
            elif father.endswith(("a", "o")):
                stem, male_end, female_end = father[:-1], "ich", "ichna"
            else:
                stem, male_end, female_end = father, "ovich", "ovna"
            return stem + (female_end if female else male_end)
        return father

    def byname(self, cid: str, rng: RNG) -> str:
        own = (self.cultures.pools.get(cid) or {}).get("byname")
        return rng.choice(own or self.t.factions["words"]["epithet"])

    # ------------------------------------------------------------------ whole names
    def person(self, cid: str, sex: str, rng: RNG, *, noble: bool = False, first: str | None = None,
               family: str | None = None, father: str | None = None) -> str:
        """A full name, put together as this people does ('Rashid ibn Tariq', 'Anna Volkova')."""
        naming = self.cultures.get(cid)["naming"]
        patterns = naming["noble" if noble else "person"]
        pattern = rng.weighted([p[0] for p in patterns], [float(p[1]) for p in patterns])
        if family is None and "{family}" in pattern:
            family = self.family_base(cid, rng)
        values = {"given": first or self.given(cid, sex, rng)}
        if "{family}" in pattern:
            values["family"] = self.family_for(cid, family or "", sex)
        if "{father}" in pattern or "{patronymic}" in pattern:
            values["father"] = father or self.given(cid, "male", rng)
            values["patronymic"] = self.patronymic(cid, values["father"], sex)
        if "{byname}" in pattern:
            values["byname"] = self.byname(cid, rng)
        return " ".join(textgen.fill(pattern, rng, {}, values).split())

    # ------------------------------------------------------------------ places
    def stem(self, cid: str, rng: RNG) -> str:
        return rng.choice(self.stems.get(cid) or self.stems["heartland"])

    def place_root(self, cid: str, rng: RNG) -> str:
        """A word like the people's own place names (for 'Lake {root}', 'the River {root}')."""
        parts = self.t.place_names["settlements"].get(cid) or self.t.place_names["settlements"]["heartland"]
        stem = self.stem(cid, rng)
        suffix = rng.choice([x for x in parts["suffix"] if x.lower() != stem.lower()] or parts["suffix"])
        word = stem + suffix
        return word[:1].upper() + word[1:].lower()

    def settlement_tables(self, cid: str) -> dict:
        """The people's place-name parts, with this world's grown stems among the prefixes."""
        parts = dict(self.t.place_names["settlements"].get(cid) or self.t.place_names["settlements"]["heartland"])
        parts["prefix"] = self.stems.get(cid) or parts["prefix"]
        return parts

    def land(self, cid: str, rng: RNG) -> str:
        """A country's name: a stem and one of the people's land endings ('Ashmark', 'Qadiristan', 'Zaryania')."""
        suffix = rng.choice(self.cultures.land_suffixes(cid))
        stem = self.stem(cid, rng)
        if stem[-1:].lower() == suffix[:1].lower():
            suffix = suffix[1:]
        word = stem + suffix
        return word[:1].upper() + word[1:].lower()

    def geo(self, cid: str, kind: str, rng: RNG) -> str:
        """A name for a stretch of land or water in this people's words ('Svartvatn', 'Jabal al-Nar', 'Loch Dubh')."""
        geo = self.geo_data.get(cid) or self.geo_data.get("heartland") or {}
        patterns = geo.get(kind) or self.regions.get(kind)
        for other in GEO_FAMILY.get(kind, ()):  # the people's word for the nearest kind of place, else anyone's
            patterns = patterns or geo.get(other) or self.regions.get(other)
        return self.fill_place(cid, rng.choice(patterns or ["the {adjective} Land"]), rng)

    def fill_place(self, cid: str, pattern: str, rng: RNG) -> str:
        """A place name from a pattern, its slots filled in this people's words ({root}, {person}, {adj}...)."""
        geo = self.geo_data.get(cid) or self.geo_data.get("heartland") or {}
        values = {}
        if "{root}" in pattern:
            glued = re.search(r"\{root\}[a-z]", pattern) is not None
            values["root"] = self.stem(cid, rng) if glued else self.place_root(cid, rng)
        if "{person}" in pattern:
            values["person"] = self.given(cid, rng.choice(["male", "female"]), rng)
        tables = dict(geo)
        tables.setdefault("adjective", self.regions["adjective"])
        tables.setdefault("noun", self.regions["noun"])
        tables.setdefault("stem", self.regions["stem"])
        name = textgen.fill(pattern, rng, tables, values)
        name = " ".join(name.split())
        return "the " + name[4:] if name.startswith("The ") else name


_FORGES: dict[tuple[int, int], NameForge] = {}


def forge(world, tables) -> NameForge:
    """The world's name forge (one per world seed and set of tables)."""
    seed = int(world.meta.seed) if hasattr(world, "meta") else int(world)
    key = (seed, id(tables))
    f = _FORGES.get(key)
    if f is None:
        if len(_FORGES) > 8:
            _FORGES.clear()
        f = _FORGES[key] = NameForge(seed, tables)
    return f
