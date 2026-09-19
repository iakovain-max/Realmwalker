"""The expected shape of every file in data/. Add an entry here when adding a new data file."""

from __future__ import annotations

from realmwalker.core.schema import Any_, Bool, Float, Int, List, Map, Obj, Spec, Str


def word_list(min_items: int = 1, max_len: int = 80) -> List:
    return List(Str(max_len=max_len), min_items=min_items)


def table_set(*names: str, max_len: int = 600) -> Obj:
    """A group of fallback-text tables, each a non-empty list of strings."""
    return Obj({name: List(Str(max_len=max_len), min_items=1) for name in names})


COLOR = List(Int(min=0, max=255), min_items=3, max_items=3)
GLYPHS = List(Str(max_len=1), min_items=1)
WEIGHTED = List(List(Any_(), min_items=2, max_items=2), min_items=1)

# ---------------------------------------------------------------------------- names and text
CULTURE = Obj(
    {
        "label": Str(max_len=60),
        "male": word_list(5, 30),
        "female": word_list(5, 30),
        "family": word_list(5, 40),
    }
)

NAMES = Obj({"cultures": Map(CULTURE, min_items=1)})

TAVERN_TABLES = (
    "name_pattern", "adjective", "noun", "part", "house", "sign_state", "building", "light", "smell",
    "sound", "crowd", "detail", "description", "manner", "overheard", "region", "season",
)

FALLBACK_TEXT = Obj({"tavern": table_set(*TAVERN_TABLES)})

# Slots that code fills in itself (not from a table), per table set.
RUNTIME_SLOTS: dict[str, set[str]] = {
    "tavern": {"family", "keeper"},
}

PLACE_NAMES = Obj(
    {
        "settlements": Map(
            Obj({"patterns": word_list(1), "prefix": word_list(3), "suffix": word_list(3),
                 "epithet": List(Str(max_len=40), optional=True)}),
            min_items=1,
        ),
        "regions": Map(word_list(1)),
    }
)

# ---------------------------------------------------------------------------- world
BIOME = Obj(
    {
        "name": Str(max_len=40),
        "glyphs": GLYPHS,
        "fg": COLOR,
        "bg": COLOR,
        "move_hours": Float(min=0, max=24),
        "passable": Bool(),
        "local": Obj(
            {
                "ground": WEIGHTED,
                "trees": Float(min=0, max=1),
                "tree_types": List(Str(max_len=40)),
                "rocks": Float(min=0, max=1),
                "bushes": Float(min=0, max=1),
                "water": Float(min=0, max=1),
            }
        ),
        "descriptions": word_list(1, 300),
    }
)
BIOMES = Obj({"biomes": Map(BIOME, min_items=1)})
REQUIRED_BIOMES = ("ocean", "lake", "coast", "plains", "forest", "pine_forest", "hills", "mountains",
                   "high_mountains", "marsh", "tundra", "desert")

TERRAIN = Obj(
    {
        "name": Str(max_len=40),
        "glyphs": GLYPHS,
        "fg": COLOR,
        "bg": COLOR,
        "walk": Bool(),
        "see": Bool(),
        "cost": Float(min=0.1, max=10),
        "tags": List(Str(max_len=30)),
        "desc": Str(max_len=300),
    }
)
LOCAL_TERRAIN = Obj({"terrain": Map(TERRAIN, min_items=1)})

CALENDAR = Obj(
    {
        "era": Str(max_len=60),
        "start_year": Int(min=1, max=100000),
        "days_per_month": Int(min=1, max=60),
        "weekdays": word_list(1, 30),
        "months": List(
            Obj({"name": Str(max_len=30), "season": Str(choices=["spring", "summer", "autumn", "winter"]),
                 "daylight": Float(min=4, max=20), "temp_offset": Float(min=-30, max=30)}),
            min_items=4,
        ),
    }
)

SETTLEMENT_TYPE = Obj(
    {
        "name": Str(max_len=40),
        "glyph": Str(max_len=1),
        "fg": COLOR,
        "population": List(Int(min=1, max=10**6), min_items=2, max_items=2),
        "buildings": List(Int(min=1, max=200), min_items=2, max_items=2),
        "walls": Str(choices=["none", "palisade", "stone"]),
        "wall_chance": Float(min=0, max=1, optional=True),
        "rank": Int(min=1, max=5),
    }
)
SITE_TYPE = Obj({"name": Str(max_len=40), "glyph": Str(max_len=1), "fg": COLOR, "desc": Str(max_len=300)})
SITES = Obj({"settlement_types": Map(SETTLEMENT_TYPE, min_items=1), "site_types": Map(SITE_TYPE, min_items=1)})
REQUIRED_SETTLEMENT_TYPES = ("hamlet", "village", "town", "city", "hold", "elfhall")

DATA_FILES: dict[str, Spec] = {
    "names.json": NAMES,
    "fallback_text.json": FALLBACK_TEXT,
    "place_names.json": PLACE_NAMES,
    "biomes.json": BIOMES,
    "local_terrain.json": LOCAL_TERRAIN,
    "calendar.json": CALENDAR,
    "sites.json": SITES,
}

# ---------------------------------------------------------------------------- characters (M2)
ABILITY_IDS = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_MAP = Obj({a: Int(min=-5, max=5, optional=True) for a in ABILITY_IDS})

RULES = Obj(
    {
        "abilities": Map(Obj({"name": Str(max_len=20), "short": Str(max_len=4)}), min_items=6),
        "skills": Map(Obj({"name": Str(max_len=30), "ability": Str(choices=list(ABILITY_IDS))}), min_items=18),
        "point_buy": Obj({"budget": Int(min=0, max=100), "min": Int(min=1, max=20), "max": Int(min=1, max=20),
                          "costs": Map(Int(min=0, max=50))}),
        "proficiency_bonus": List(Int(min=1, max=10), min_items=10),
        "xp_for_level": List(Int(min=0, max=10**7), min_items=10),
        "max_level": Int(min=1, max=20),
        "asi_levels": List(Int(min=1, max=20)),
        "carry": Obj({"per_strength": Int(min=1, max=100), "encumbered_per_strength": Int(min=1, max=100),
                      "heavily_per_strength": Int(min=1, max=100)}),
        "languages": word_list(1, 40),
        "tools": Map(Str(max_len=40)),
    }
)

TRAIT = Obj({"id": Str(max_len=40), "name": Str(max_len=60), "text": Str(max_len=300), "rule": Str(max_len=40, optional=True)})
RACE = Obj(
    {
        "name": Str(max_len=30), "description": Str(max_len=600), "ability_bonus": ABILITY_MAP,
        "speed": Int(min=5, max=60), "size": Str(choices=["small", "medium"]), "darkvision": Int(min=0, max=120),
        "cultures": word_list(1, 30), "languages": word_list(1, 30), "extra_languages": Int(min=0, max=5),
        "skills": List(Str(max_len=30)), "tools_choice": List(Str(max_len=40), optional=True),
        "age": Obj({"adult": Int(min=1, max=1000), "old": Int(min=1, max=1000), "max": Int(min=1, max=2000)}),
        "hp_per_level": Int(min=0, max=5, optional=True),
        "traits": List(TRAIT), "standing": Map(Int(min=-100, max=100)),
    }
)
RACES = Obj({"races": Map(RACE, min_items=1)})

FEATURE = Obj({"level": Int(min=1, max=20), "id": Str(max_len=40), "name": Str(max_len=60), "text": Str(max_len=400),
               "rule": Str(max_len=40, optional=True)})
KIT = Obj({"name": Str(max_len=40), "items": WEIGHTED})
CLASS = Obj(
    {
        "name": Str(max_len=30), "description": Str(max_len=600), "hit_die": Int(min=4, max=12),
        "primary": List(Str(choices=list(ABILITY_IDS)), min_items=1), "saves": List(Str(choices=list(ABILITY_IDS)), min_items=2, max_items=2),
        "armor": List(Str(max_len=20)), "weapons": List(Str(max_len=30)), "tools": List(Str(max_len=40)),
        "skill_count": Int(min=0, max=6), "skill_choices": List(Str(max_len=30), min_items=1),
        "suggested": Obj({a: Int(min=8, max=15) for a in ABILITY_IDS}),
        "choices_at_1": List(Str(max_len=30)),
        "fighting_styles": Map(Obj({"name": Str(max_len=40), "text": Str(max_len=300)}), optional=True),
        "spellcasting": Obj({"ability": Str(choices=list(ABILITY_IDS)), "type": Str(choices=["prepared", "spellbook", "known"]),
                             "cantrips": List(Int(min=0, max=10), min_items=10),
                             "slots": List(List(Int(min=0, max=10)), min_items=10)}, optional=True),
        "features": List(FEATURE, min_items=1),
        "subclasses": Map(Obj({"name": Str(max_len=40), "text": Str(max_len=300), "features": List(FEATURE),
                               "armor": List(Str(max_len=20), optional=True), "weapons": List(Str(max_len=30), optional=True)}),
                          min_items=1),
        "kits": List(KIT, min_items=1),
    }
)
CLASSES = Obj({"classes": Map(CLASS, min_items=1)})

BACKGROUND = Obj(
    {
        "name": Str(max_len=30), "description": Str(max_len=600), "skills": List(Str(max_len=30), min_items=2, max_items=2),
        "tools": List(Str(max_len=40)), "languages": Int(min=0, max=3), "items": WEIGHTED, "money": Int(min=0, max=10**6),
        "feature": Obj({"name": Str(max_len=60), "text": Str(max_len=400)}),
        "tie": Obj({"kind": Str(max_len=30), "text": Str(max_len=400)}),
        "start": Obj({"kinds": List(Str(max_len=20), min_items=1), "biomes": List(Str(max_len=30), optional=True)}),
        "personality": word_list(1, 200), "ideal": word_list(1, 200), "bond": word_list(1, 200), "flaw": word_list(1, 200),
    }
)
BACKGROUNDS = Obj({"backgrounds": Map(BACKGROUND, min_items=1), "tie_words": Map(word_list(1, 120))})

ITEM = Obj(
    {
        "name": Str(max_len=60), "category": Str(choices=["weapon", "ammo", "armor", "shield", "helmet", "clothing", "gear",
                                                          "tool", "focus", "book", "food", "drink", "trade"]),
        "weight": Float(min=0, max=1000), "value": Int(min=0, max=10**8), "material": Str(max_len=20),
        "description": Str(max_len=400, optional=True), "stack": Bool(optional=True),
        "damage": Str(max_len=10, optional=True), "damage_type": Str(choices=["slashing", "piercing", "bludgeoning"], optional=True),
        "group": Str(choices=["simple", "martial"], optional=True), "properties": List(Str(max_len=20), optional=True),
        "versatile": Str(max_len=10, optional=True), "range": List(Int(min=0, max=2000), min_items=2, max_items=2, optional=True),
        "ammo": Str(max_len=30, optional=True),
        "armor_type": Str(choices=["light", "medium", "heavy"], optional=True), "ac": Int(min=0, max=30, optional=True),
        "str_req": Int(min=0, max=30, optional=True), "stealth_disadvantage": Bool(optional=True),
        "covers": List(Str(choices=["head", "torso", "arms", "legs", "hands", "feet"]), optional=True),
        "ac_bonus": Int(min=0, max=5, optional=True), "perception_penalty": Int(min=0, max=10, optional=True),
        "slot": Str(choices=["under", "main", "outer", "head", "hands", "feet"], optional=True),
        "warmth": Float(min=0, max=10, optional=True), "wind": Float(min=0, max=1, optional=True),
        "water": Float(min=0, max=1, optional=True), "social": Int(min=-3, max=3, optional=True), "hood": Bool(optional=True),
        "tool": Str(max_len=40, optional=True), "light": Any_(optional=True), "container": Any_(optional=True),
        "food": Any_(optional=True), "drink": Any_(optional=True), "use": Any_(optional=True),
    }
)
ITEMS = Obj(
    {
        "qualities": Map(Obj({"name": Str(max_len=20), "value": Float(min=0, max=100), "attack": Int(min=-5, max=5),
                              "armor": Int(min=-5, max=5), "durability": Float(min=0, max=10)}), min_items=1),
        "materials": Map(Obj({"name": Str(max_len=30)}), min_items=1),
        "items": Map(ITEM, min_items=1),
        "starting_packs": Map(WEIGHTED),
    }
)

APPEARANCE = Obj(
    {
        "hair": Map(word_list(1)), "eyes": word_list(1), "build": Map(word_list(1)), "mark": word_list(1, 120),
        "backstory": Map(word_list(1, 300)), "background_lines": Map(Str(max_len=400)),
    }
)

DATA_FILES.update({
    "rules.json": RULES,
    "races.json": RACES,
    "classes.json": CLASSES,
    "backgrounds.json": BACKGROUNDS,
    "items.json": ITEMS,
    "appearance.json": APPEARANCE,
})

# ---------------------------------------------------------------------------- combat (M3)
ATTACK = Obj(
    {
        "name": Str(max_len=40), "kind": Str(choices=["melee", "ranged", "spell_melee", "spell_ranged"]),
        "bonus": Int(min=-5, max=20), "damage": Str(max_len=12),
        "damage_type": Str(choices=["slashing", "piercing", "bludgeoning", "fire", "cold", "lightning", "necrotic",
                                    "radiant", "force", "thunder", "poison", "acid", "psychic"]),
        "item": Str(max_len=40, optional=True), "wound": Str(max_len=20, optional=True), "reach": Bool(optional=True),
        "trip_dc": Int(min=1, max=30, optional=True), "paralyze_dc": Int(min=1, max=30, optional=True),
        "poison": Any_(optional=True), "disease": Str(max_len=40, optional=True),
    }
)
CREATURE = Obj(
    {
        "name": Str(max_len=40), "plural": Str(max_len=40),
        "kind": Str(choices=["beast", "humanoid", "undead", "giant", "monstrosity", "dragon"]),
        "body": Str(choices=["humanoid", "quadruped", "spider"]), "size": Str(choices=["tiny", "small", "medium", "large", "huge"]),
        "cr": Float(min=0, max=30), "xp": Int(min=0, max=200000), "ac": Int(min=1, max=30), "hp": Str(max_len=12),
        "speed": Int(min=0, max=120), "abilities": Obj({a: Int(min=1, max=30) for a in ABILITY_IDS}),
        "skills": Map(Int(min=-5, max=20)), "darkvision": Int(min=0, max=120),
        "attacks": List(ATTACK, min_items=1), "multiattack": Int(min=1, max=6, optional=True),
        "traits": List(Str(max_len=40)), "morale": Str(choices=["beast", "bandit", "soldier", "coward", "warrior", "fanatic", "mindless"]),
        "rank": Str(choices=["front", "back"]), "names": Str(max_len=30, optional=True),
        "gear": List(List(Any_(), min_items=2, max_items=2)), "money": Any_(optional=True),
        "loot": List(List(Any_(), min_items=2, max_items=2), optional=True),
        "butcher": List(List(Any_(), min_items=2, max_items=2), optional=True),
        "vulnerable": List(Str(max_len=20), optional=True), "immune": List(Str(max_len=20), optional=True),
        "glyph": Str(max_len=1), "color": COLOR, "descriptions": word_list(1, 300),
    }
)
ENCOUNTER = Obj(
    {
        "name": Str(max_len=60), "members": List(List(Any_(), min_items=2, max_items=2), min_items=1),
        "biomes": List(Str(max_len=30), min_items=1), "danger": List(Int(min=0, max=10), min_items=2, max_items=2),
        "time": Str(choices=["any", "day", "night"]), "weight": Float(min=0, max=100), "road": Bool(optional=True),
        "intro": word_list(1, 300),
    }
)
CREATURES = Obj({"creatures": Map(CREATURE, min_items=1), "encounters": Map(ENCOUNTER, min_items=1),
                 "site_inhabitants": Map(List(Str(max_len=40)))})

SPELL = Obj(
    {
        "name": Str(max_len=40), "level": Int(min=0, max=9), "school": Str(max_len=20), "classes": List(Str(max_len=20), min_items=1),
        "kind": Str(choices=["attack", "auto", "save", "heal", "buff", "condition", "sleep", "stabilize", "cure", "summon",
                             "aura", "move", "revive"]),
        "target": Str(choices=["enemy", "ally", "self", "downed_ally", "dead_ally", "enemy_front", "enemy_back", "all_enemies",
                               "all_allies"]),
        "text": Str(max_len=300),
    },
    strict=False,
)
SPELLS = Obj({"spells": Map(SPELL, min_items=1), "starting": Map(Any_())})

COMBAT_TEXT = Obj(
    {
        "locations": Map(WEIGHTED), "part_names": Map(Map(word_list(1))), "hit": Map(word_list(1, 200)),
        "crit": word_list(1), "miss": word_list(1, 200), "armored_miss": word_list(1, 200),
        "wound": Map(Map(word_list(1, 200))), "down": word_list(1, 200), "dead": word_list(1, 200),
        "flee": word_list(1, 200), "surrender": word_list(1, 200), "beg": word_list(1, 200),
        "aftermath": Map(word_list(1, 400)),
    }
)

DATA_FILES.update({
    "creatures.json": CREATURES,
    "spells.json": SPELLS,
    "combat_text.json": COMBAT_TEXT,
})
