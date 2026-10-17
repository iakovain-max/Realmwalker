"""Items: base definitions from data/items.json, and the item instances characters carry.

An instance records only what differs between copies of the same thing: how many, their quality,
their condition, a custom name for unique items, and when food was made (for spoilage).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

BODY_PARTS = ("head", "torso", "arms", "legs", "hands", "feet")
EQUIP_SLOTS = ("main_hand", "off_hand", "armor", "helmet", "outer", "main", "under", "head", "hands", "feet",
               "back", "neck", "ring")
SLOT_NAMES = {
    "main_hand": "Main hand", "off_hand": "Off hand", "armor": "Armour", "helmet": "Helmet",
    "outer": "Cloak / coat", "main": "Clothes", "under": "Underclothes", "head": "Hat / hood",
    "hands": "Gloves", "feet": "Footwear", "back": "Pack", "neck": "Neck", "ring": "Ring",
}
CATEGORY_NAMES = {
    "weapon": "Weapons", "ammo": "Ammunition", "armor": "Armour", "shield": "Shields", "helmet": "Helmets",
    "clothing": "Clothing", "gear": "Gear", "tool": "Tools", "focus": "Holy symbols & foci", "book": "Books & papers",
    "food": "Food", "drink": "Drink", "trade": "Trade goods", "jewellery": "Rings & amulets",
}
UNKNOWN = {"name": "strange object", "category": "gear", "weight": 1, "value": 0, "material": "stone"}


@dataclass
class Item:
    uid: int
    def_id: str
    qty: int = 1
    quality: str = "common"
    condition: int = 100  # 0 ruined .. 100 perfect
    name: str = ""  # custom name for unique items
    made_at: int = 0  # world minute it was made or caught (food spoilage)
    tags: list[str] = field(default_factory=list)  # e.g. "stolen"
    magic: dict = field(default_factory=dict)  # magic items: rarity, properties, curse, name (rules/magic.py)
    fill: float = 0.0  # containers: pints held
    fill_kind: str = ""  # containers: "clean", "boiled", "river", "marsh"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Item:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


class ItemTable:
    def __init__(self, data: dict) -> None:
        self.defs: dict[str, dict] = {k: v for k, v in data["items"].items() if not k.startswith("_")}
        self.qualities = data["qualities"]
        self.materials = data["materials"]
        self.starting_packs = data.get("starting_packs", {})
        self.upkeep = data.get("upkeep", {})  # wear, mending, honing... (game/gear.py)

    def add_scrolls(self, spells, numbers: dict | None = None) -> None:
        """A scroll for every spell, cantrips too (made from data/spells.json, not listed in items.json): DMG 2024's
        Spell Scroll, valued and graded by data/rules.json "spell_scrolls" (its save DC and attack bonus are read
        there by rules/spells.scroll_numbers)."""
        numbers = numbers or {}
        values, rarities = numbers.get("value") or [], numbers.get("rarity") or []
        for sid, spell in spells.defs.items():
            level = int(spell["level"])
            if spell.get("classes") in (["item"], ["again"]):
                continue  # (a flask's or a coating's pseudo-spell, a spell's follow-up: nothing to write down)
            what = "a cantrip" if level == 0 else f"level {level}"
            self.defs[f"scroll_{sid}"] = {
                "name": f"scroll of {spell['name']}", "category": "book", "weight": 0.1,
                "value": values[level] if level < len(values) else 2500 * max(1, level),
                "rarity": rarities[level] if level < len(rarities) else "common",
                "material": "paper", "use": {"scroll": sid},
                "description": f"{spell['name']} ({what}, {spell.get('school', 'arcane')}), written out in a mage's "
                               f"cipher. Whoever has the spell on their calling's list can read it aloud once, with "
                               f"no materials; a wizard can copy it into a spellbook instead.",
            }

    def get(self, def_id: str) -> dict:
        return self.defs.get(def_id, UNKNOWN)

    def __contains__(self, def_id: str) -> bool:
        return def_id in self.defs

    def proficiency_words(self, keys: list[str]) -> str:
        """Weapon or armour training as words: a group ("simple", "martial") stays, an item id becomes its name."""
        return ", ".join(self.defs[k]["name"] if k in self.defs else k.replace("_", " ") for k in keys)

    # ------------------------------------------------------------------ descriptions
    def base_name(self, item: Item) -> str:
        if item.magic:
            base = self.get(item.def_id)["name"]
            if item.magic.get("identified"):
                return item.magic.get("title") or item.name or f"magic {base}"
            return f"strange {base}"
        return item.name or self.get(item.def_id)["name"]

    def name(self, item: Item, with_qty: bool = True) -> str:
        name = self.base_name(item)
        if item.quality != "common" and not item.name and not item.magic:
            name = f"{self.qualities.get(item.quality, {}).get('name', item.quality)} {name}"
        if with_qty and item.qty > 1:
            name = f"{name} ×{item.qty}"
        return name

    def category(self, item: Item) -> str:
        return self.get(item.def_id)["category"]

    def weight(self, item: Item) -> float:
        return float(self.get(item.def_id)["weight"]) * item.qty + item.fill  # a pint of water weighs a pound

    def unit_value(self, item: Item) -> int:
        d = self.get(item.def_id)
        mult = self.qualities.get(item.quality, {}).get("value", 1.0)
        wear = 0.3 + 0.7 * max(0, min(100, item.condition)) / 100.0
        value = d["value"] * mult * wear
        if item.magic and item.magic.get("identified"):
            value += int(item.magic.get("value", 0))
        return int(round(value))

    def value(self, item: Item) -> int:
        return self.unit_value(item) * item.qty

    def stackable(self, item: Item) -> bool:
        return bool(self.get(item.def_id).get("stack")) and not item.magic

    def condition_word(self, item: Item) -> str:
        c = item.condition
        if c >= 90:
            return "good"
        if c >= 60:
            return "worn"
        if c >= 30:
            return "battered"
        if c > 0:
            return "falling apart"
        return "ruined"

    def slots_for(self, item: Item, char=None) -> list[str]:
        """Where it goes (`char`: the wielder, whose feats may free the off hand)."""
        d = self.get(item.def_id)
        cat = d["category"]
        if cat == "weapon":
            props = d.get("properties", [])
            if "light" in props:
                return ["main_hand", "off_hand"]
            if char is not None and any(f["id"] == "dual_wielder" for f in char.feats) \
                    and "two_handed" not in props and "ranged" not in props:
                return ["main_hand", "off_hand"]  # (Dual Wielder: any one-handed melee weapon in the off hand)
            return ["main_hand"]
        if cat == "shield":
            return ["off_hand"]
        if cat == "armor":
            return ["armor"]
        if cat == "helmet":
            return ["helmet"]
        if cat in ("clothing", "jewellery"):
            return [d["slot"]]
        if cat in ("focus",) or d.get("light"):
            # Foci, torches and lanterns are held; a holy symbol can also hang at the neck.
            return ([d["slot"]] if d.get("slot") else []) + ["off_hand"]
        if d.get("slot"):
            return [d["slot"]]  # a pack on the back, a trophy at the neck
        return []


def money_text(cp: int) -> str:
    """'3 gp 4 sp 2 cp' with the zero parts left out."""
    cp = max(0, int(cp))
    gp, rem = divmod(cp, 100)
    sp, cp = divmod(rem, 10)
    parts = [f"{gp} gp" if gp else "", f"{sp} sp" if sp else "", f"{cp} cp" if cp else ""]
    return " ".join(p for p in parts if p) or "0 cp"


def money_short(cp: int) -> str:
    """Money in at most nine letters, for a column: '2412 gp', '3 gp 4 sp', '4 sp 2 cp'."""
    cp = max(0, int(cp))
    gp, rem = divmod(cp, 100)
    if gp >= 10:
        return f"{gp} gp" if gp < 1000000 else f"{gp // 1000}k gp"
    sp, c = divmod(rem, 10)
    if gp:
        return f"{gp} gp {sp} sp" if sp else f"{gp} gp"
    return money_text(cp)


def coin_weight(cp: int) -> float:
    """Coins weigh 50 to the pound; money is carried in the fewest coins."""
    gp, rem = divmod(max(0, cp), 100)
    sp, cp = divmod(rem, 10)
    return (gp + sp + cp) / 50.0


# ---------------------------------------------------------------------------- trinkets (Expansion 2 part D)
def make_trinket(tables, rng, uid: int = 0, now: int = 0) -> Item:
    """One keepsake from data/trinkets.json: the "trinket" item, named and remembered by its tag."""
    t = rng.choice(sorted(tables.trinkets.values(), key=lambda x: x["id"]))
    return Item(uid, "trinket", 1, name=t["name"], made_at=now, tags=[f"trinket:{t['id']}"])


def trinket_words(tables, item: Item) -> str:
    """What a trinket is, in its own words ("" for anything else)."""
    tid = next((tag.split(":", 1)[1] for tag in item.tags if tag.startswith("trinket:")), "")
    return tables.trinkets.get(tid, {}).get("text", "")
