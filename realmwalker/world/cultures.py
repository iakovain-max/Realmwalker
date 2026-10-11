"""The peoples of the world, in one place (data/cultures.json; their name pools are in names.json, place-name parts in
place_names.json, laws in factions.json culture_laws, growth and succession in history.json peoples).

Code asks here instead of listing peoples by hand: which peoples are human, a people's race, how their realms are
named and what their rulers are called, their faith, their town style and dress, where they like to live. A world
calls each people by a name of its own (world.politics["peoples"], chosen when the world is made), so the same
people may be "Northmen" in one world and "Hrafnings" in the next: people() and adjective() give the name in a world.
"""

from __future__ import annotations

DEFAULT = "heartland"


class Cultures:
    def __init__(self, data: dict, names: dict, factions: dict) -> None:
        self.defs: dict[str, dict] = {k: v for k, v in data["cultures"].items() if not k.startswith("_")}
        self.ids: list[str] = list(self.defs)
        self.pools: dict = names["cultures"]
        self.kinds: dict = factions["kinds"]
        self.human: list[str] = [c for c, d in self.defs.items() if d["kind"] == "human"]
        self.elder: list[str] = [c for c, d in self.defs.items() if d["kind"] == "elder"]

    # ------------------------------------------------------------------ what a people is
    def known(self, cid: str) -> bool:
        return cid in self.defs

    def get(self, cid: str) -> dict:
        return self.defs.get(cid) or self.defs[DEFAULT]

    def race(self, cid: str) -> str:
        return self.get(cid)["race"]

    def kind(self, cid: str) -> str:
        return self.get(cid)["kind"]

    def is_human(self, cid: str) -> bool:
        return self.known(cid) and self.defs[cid]["kind"] == "human"

    def faith(self, cid: str) -> str:
        return self.get(cid)["faith"]

    def town_style(self, cid: str) -> str:
        return self.get(cid).get("town", DEFAULT)

    def dress(self, cid: str) -> str:
        return self.get(cid).get("dress", DEFAULT)

    def color(self, cid: str) -> tuple[int, int, int]:
        return tuple(self.get(cid)["color"])

    def home(self, cid: str) -> dict:
        return self.get(cid)["home"]

    def human_or_default(self, cid: str) -> str:
        """A human people to stand in for one that is not (an elf-hall's lord is still named by elves, but a human
        realm founded among elves takes the land's human people, or the default)."""
        return cid if self.is_human(cid) else DEFAULT

    # ------------------------------------------------------------------ realms and titles
    def realm_patterns(self, kind: str, cid: str) -> list[str]:
        """How this people names a realm of this kind (or the general patterns of data/factions.json)."""
        own = self.get(cid).get("realms", {}).get(kind)
        return list(own) if own else list(self.kinds[kind]["names"])

    def title(self, kind: str, sex: str, cid: str | None = None) -> str:
        """What this people calls the head of a realm of this kind ('Sultana', 'Jarl', 'Khagan'...)."""
        pair = self.get(cid).get("titles", {}).get(kind) if cid else None
        pair = pair or self.kinds.get(kind, {}).get("leader") or ["", ""]
        return pair[1] if sex == "female" else pair[0]

    def titles_of(self, kind: str) -> set[str]:
        """Every title any people gives the head of this kind of realm (to recognise a crowned head by title)."""
        out = set(self.kinds.get(kind, {}).get("leader") or ())
        for d in self.defs.values():
            out.update(d.get("titles", {}).get(kind, ()))
        return out

    def land_suffixes(self, cid: str) -> list[str]:
        return list(self.get(cid).get("land_suffix") or self.defs[DEFAULT]["land_suffix"])

    # ------------------------------------------------------------------ names a world gives a people
    def folk_options(self, cid: str) -> list[list[str]]:
        return self.get(cid)["folk"]

    def choose_folk(self, world, rng) -> None:
        """Give each people this world's name for them (kept in world.politics["peoples"])."""
        chosen = {}
        for cid in self.ids:
            options = self.folk_options(cid)
            chosen[cid] = list(options[rng.randint(0, len(options) - 1)])
        world.politics["peoples"] = chosen

    def _folk(self, world, cid: str) -> list[str]:
        peoples = (getattr(world, "politics", None) or {}).get("peoples", {}) if world is not None else {}
        pair = peoples.get(cid)
        if pair:
            return pair
        if cid in self.defs:
            return self.defs[cid]["folk"][0]
        label = self.pools.get(cid, {}).get("label", cid.replace("_", " ").title())
        return [label, label]

    def people(self, world, cid: str) -> str:
        """The people, plural: 'Heartlanders', 'the Fair Folk'."""
        return self._folk(world, cid)[0]

    def adjective(self, world, cid: str) -> str:
        """Of the people: 'Heartland folk live here', 'a Qasari caravan'."""
        return self._folk(world, cid)[1]

    def about(self, cid: str) -> str:
        return self.get(cid).get("about", "")


def faith_for(tables, cid: str) -> str:
    """The faith of a people, by the registry (or, for a people it does not know, data/factions.json faiths)."""
    cultures = getattr(tables, "cultures", None)
    if cultures is not None and cultures.known(cid):
        return cultures.faith(cid)
    for fid, faith in tables.factions["faiths"].items():
        if cid in faith.get("cultures", []):
            return fid
    return "radiant"
