"""The expected shape of every file in data/. Add an entry here when adding a new data file."""

from __future__ import annotations

from realmwalker.core.schema import Any_, Bool, Float, Int, List, Map, Obj, Spec, Str


def word_list(min_items: int = 1, max_len: int = 80) -> List:
    return List(Str(max_len=max_len), min_items=min_items)


def table_set(*names: str, max_len: int = 600) -> Obj:
    """A group of fallback-text tables, each a non-empty list of strings."""
    return Obj({name: List(Str(max_len=max_len), min_items=1) for name in names})


COLOR = List(Int(min=0, max=255), min_items=3, max_items=3)
WEIGHTED = List(List(Any_(), min_items=2, max_items=2), min_items=1)

# ---------------------------------------------------------------------------- names and text
CULTURE = Obj(
    {
        "label": Str(max_len=60),
        "male": word_list(5, 30),
        "female": word_list(5, 30),
        "family": word_list(5, 40),
        "byname": List(Str(max_len=40), optional=True),
    }
)

NAMES = Obj({"cultures": Map(CULTURE, min_items=1)})

PATRONYMICS = ["norse", "gaelic", "arabic", "slavic"]
FAMILY_FORMS = ["slavic", "greek"]
PEOPLE = Obj(
    {
        "folk": List(List(Str(max_len=40), min_items=2, max_items=2), min_items=1),
        "race": Str(max_len=20),
        "kind": Str(choices=["human", "elder", "small", "tribal"]),
        "like": Str(max_len=120),
        "color": COLOR,
        "about": Str(max_len=600),
        "home": Obj({"biomes": Map(Float(min=0, max=10)),
                     "temperature": List(Float(min=-80, max=80), min_items=2, max_items=2),
                     "moisture": List(Float(min=0, max=1), min_items=2, max_items=2),
                     "coast": Float(min=-1, max=1)}),
        "naming": Obj({"person": WEIGHTED, "noble": WEIGHTED, "patronymic": Str(choices=PATRONYMICS, optional=True),
                       "family_forms": Str(choices=FAMILY_FORMS, optional=True),
                       "family_prefix": Str(max_len=8, optional=True)}),
        "realms": Map(word_list(1, 80)),
        "titles": Map(List(Str(max_len=30), min_items=2, max_items=2)),
        "land_suffix": word_list(1, 20),
        "faith": Str(max_len=30),
        "town": Str(max_len=30),
        "dress": Str(max_len=30),
    }
)
CULTURES = Obj({"cultures": Map(PEOPLE, min_items=1)})
NAME_SLOTS = ("given", "family", "father", "patronymic", "byname")

TAVERN_TABLES = (
    "name_pattern", "adjective", "noun", "part", "house", "sign_state", "building", "light", "smell",
    "sound", "crowd", "detail", "description", "manner", "overheard", "region", "season",
)

SKIES = ("clear", "cloudy", "overcast", "fog", "drizzle", "rain", "storm", "flurries", "snow", "blizzard", "heat")
TRAVEL_DAY_TABLES = ("passage", "opening", "walking", "closing") + tuple(f"sky_{k}" for k in SKIES)

SETTLEMENT_TABLES = ("passage", "approach", "sight", "smell", "detail")
OBITUARY_TABLES = ("opening", "fame", "infamy", "nobody", "deeds", "no_deeds", "killer", "gentle", "closing")

FALLBACK_TEXT = Obj({"tavern": table_set(*TAVERN_TABLES), "travel_day": table_set(*TRAVEL_DAY_TABLES),
                     "settlement": table_set(*SETTLEMENT_TABLES), "obituary": table_set(*OBITUARY_TABLES),
                     "weather_change": Map(word_list(1, 200), min_items=1)})

# Slots that code fills in itself (not from a table), per table set.
RUNTIME_SLOTS: dict[str, set[str]] = {
    "tavern": {"family", "keeper"},
    "travel_day": {"name", "miles", "lands", "weather", "mood", "season", "events", "road", "sky"},
    "settlement": {"name", "kind", "land", "land_in", "season"},
    "obituary": {"first", "who", "age", "road", "place", "deed", "kills", "year"},
}

PLACE_NAMES = Obj(
    {
        "settlements": Map(
            Obj({"patterns": word_list(1), "prefix": word_list(3), "suffix": word_list(3),
                 "epithet": List(Str(max_len=40), optional=True)}),
            min_items=1,
        ),
        "regions": Map(word_list(1)),
        "geo": Map(Map(word_list(1, 80)), optional=True),
    }
)
GEO_SLOTS = ("root", "person", "adjective", "noun", "stem")  # filled by world/names.py, not from the 'geo' lists
GEO_KINDS = ("mountains", "hills", "forest", "pine_forest", "marsh", "plains", "desert", "tundra", "coast", "lake",
             "river", "ocean", "island", "bay", "peak")

# ---------------------------------------------------------------------------- world
BIOME = Obj(
    {
        "name": Str(max_len=40),
        "move_hours": Float(min=0, max=24),
        "passable": Bool(),
        # The older land this one behaves like in every system that asks "is this a desert?" (camping, encounters,
        # survival, riding...): a new land works everywhere at once. Absent: it is its own family.
        "family": Str(max_len=40, optional=True),
        "local": Obj(
            {
                "ground": WEIGHTED,
                "trees": Float(min=0, max=1),
                "tree_types": List(Str(max_len=40)),
                "rocks": Float(min=0, max=1),
                "bushes": Float(min=0, max=1),
                "water": Float(min=0, max=1),
                # Things strewn about: [terrain, chance per square] (cacti, termite hills, steam vents...).
                "scatter": List(List(Any_(), min_items=2, max_items=2), optional=True),
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
        "population": List(Int(min=1, max=10**6), min_items=2, max_items=2),
        "buildings": List(Int(min=1, max=200), min_items=2, max_items=2),
        "walls": Str(choices=["none", "palisade", "stone"]),
        "wall_chance": Float(min=0, max=1, optional=True),
        "rank": Int(min=1, max=5),
    }
)
SITE_TYPE = Obj({"name": Str(max_len=40), "desc": Str(max_len=300)})
SITES = Obj({"settlement_types": Map(SETTLEMENT_TYPE, min_items=1), "site_types": Map(SITE_TYPE, min_items=1),
             "dungeon_styles": Map(word_list(1, 300), min_items=1),
             "dungeon_moments": Map(word_list(1, 300), min_items=1)})
REQUIRED_SETTLEMENT_TYPES = ("hamlet", "village", "town", "city", "hold", "elfhall")

DATA_FILES: dict[str, Spec] = {
    "names.json": NAMES,
    "cultures.json": CULTURES,
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
        "discovery_xp": Obj({"region": Int(min=0, max=1000), "site": Int(min=0, max=1000),
                             "deeper": Int(min=0, max=1000), "wonder": Int(min=0, max=1000, optional=True)},
                            optional=True),
        "carry": Obj({"per_strength": Int(min=1, max=100), "encumbered_per_strength": Int(min=1, max=100),
                      "heavily_per_strength": Int(min=1, max=100)}),
        "languages": word_list(1, 40),
        "language_lists": Obj({"standard": word_list(1, 40), "rare": word_list(1, 40), "by_species": Map(word_list(1, 40)),
                               "by_culture": Map(word_list(1, 40))}),
        "tools": Map(Str(max_len=40)),
        "hazards": Obj({"falling": Obj({"feet_per_die": Int(min=1, max=100), "die": Int(min=2, max=20), "max_dice": Int(min=1, max=100)}),
                        "burning": Obj({"damage": Str(max_len=12), "type": Str(max_len=20)}),
                        "breath": Obj({"minutes": Int(min=0, max=60), "least_seconds": Int(min=0, max=600)})}, optional=True),
        "encounters": Obj({"budget": List(List(Int(min=0, max=100000), min_items=3, max_items=3), min_items=20),
                           "danger_level": List(Int(min=1, max=20), min_items=11), "odds": Map(Int(min=0, max=100)),
                           "deadly": Float(min=1, max=10), "most_extra": Float(min=1, max=5)}, optional=True),
        "travel_pace": Obj({"paces": Map(Obj({"name": Str(max_len=20), "time": Float(min=0.1, max=5),
                                              "passive": Int(min=-10, max=10)}, strict=False), min_items=3),
                            "max": Map(Str(choices=["fast", "normal", "slow"]))}, optional=True),
        "attitudes": Obj({"influence": Map(Str(choices=["advantage", "none", "disadvantage"])),
                          "start": Map(Map(Int(min=0, max=100))), "moods": Map(Str(max_len=20)),
                          "default_dc": Int(min=1, max=30)}, optional=True),
        "study": Obj({"skills": Map(Str(max_len=30)),
                      "dc": Obj({"base": Int(min=1, max=30), "per_cr": Float(min=0, max=5), "max": Int(min=1, max=40)})},
                     optional=True),
        "objects": Obj({"ac": Map(Int(min=1, max=30)), "hp": Map(List(Str(max_len=12), min_items=2, max_items=2)),
                        "immune": List(Str(max_len=20)), "terrain": Map(List(Any_(), min_items=4, max_items=4), optional=True)},
                       optional=True),
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
        # choices made at creation (2024): {id: {"kind": "skill" | "origin_feat" | "lineage", "from": [...]}}
        "choices": Map(Obj({"kind": Str(choices=["skill", "origin_feat", "lineage"]),
                            "from": List(Str(max_len=30), optional=True)}), optional=True),
        "lineages": Map(Obj({"name": Str(max_len=40), "text": Str(max_len=300), "speed": Int(min=5, max=60, optional=True),
                             "darkvision": Int(min=0, max=300, optional=True),
                             "spells": Map(List(Str(max_len=40)), optional=True)}), optional=True),
    }
)
RACES = Obj({"races": Map(RACE, min_items=1)})

FEATURE = Obj({"level": Int(min=1, max=20), "id": Str(max_len=40), "name": Str(max_len=60), "text": Str(max_len=400),
               "rule": Str(max_len=40, optional=True)})
KIT = Obj({"name": Str(max_len=40), "items": WEIGHTED,
           "style": Str(max_len=30, optional=True)})  # the fighting style that suits it (the default)
CLASS = Obj(
    {
        "name": Str(max_len=30), "description": Str(max_len=600), "hit_die": Int(min=4, max=12),
        "primary": List(Str(choices=list(ABILITY_IDS)), min_items=1), "saves": List(Str(choices=list(ABILITY_IDS)), min_items=2, max_items=2),
        "armor": List(Str(max_len=20)), "weapons": List(Str(max_len=30)), "tools": List(Str(max_len=40)),
        "skill_count": Int(min=0, max=6), "skill_choices": List(Str(max_len=30), min_items=1),
        "suggested": Obj({a: Int(min=8, max=15) for a in ABILITY_IDS}),
        "choices_at_1": List(Str(max_len=30)),
        "fighting_styles": Map(Obj({"name": Str(max_len=40), "text": Str(max_len=300)}), optional=True),
        # Weapon Mastery (2024): [[from level, how many kinds of weapon], ...]
        "mastery": List(List(Int(min=0, max=20), min_items=2, max_items=2), optional=True),
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
        "abilities": List(Str(choices=list(ABILITY_IDS)), min_items=3, max_items=3),  # raised +2/+1 or +1/+1/+1
        "feat": Obj({"id": Str(max_len=40), "choices": Map(Any_(), optional=True)}),  # its origin feat
        "gold": Int(min=0, max=10**6),  # equipment option B: coin instead
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
                                                          "tool", "focus", "book", "food", "drink", "trade", "jewellery"]),
        "weight": Float(min=0, max=1000), "value": Int(min=0, max=10**8), "material": Str(max_len=20),
        "description": Str(max_len=400, optional=True), "stack": Bool(optional=True),
        "damage": Str(max_len=10, optional=True), "damage_type": Str(choices=["slashing", "piercing", "bludgeoning"], optional=True),
        "group": Str(choices=["simple", "martial"], optional=True), "properties": List(Str(max_len=20), optional=True),
        "versatile": Str(max_len=10, optional=True), "range": List(Int(min=0, max=2000), min_items=2, max_items=2, optional=True),
        "ammo": Str(max_len=30, optional=True),
        "mastery": Str(choices=["cleave", "graze", "nick", "push", "sap", "slow", "topple", "vex"], optional=True),
        "rare": Bool(optional=True),  # gnomish work (firearms): never in ordinary shops, kits or common loot
        "armor_type": Str(choices=["light", "medium", "heavy"], optional=True), "ac": Int(min=0, max=30, optional=True),
        "str_req": Int(min=0, max=30, optional=True), "stealth_disadvantage": Bool(optional=True),
        "covers": List(Str(choices=["head", "torso", "arms", "legs", "hands", "feet"]), optional=True),
        "ac_bonus": Int(min=0, max=5, optional=True), "perception_penalty": Int(min=0, max=10, optional=True),
        "slot": Str(choices=["under", "main", "outer", "head", "hands", "feet", "ring", "neck", "back"], optional=True),
        "carry": Float(min=0, max=100, optional=True),  # worn on the back: pounds more before you count as laden
        "focus": Obj({"kind": Str(choices=["arcane", "divine"]), "carried": Bool(optional=True)}, optional=True),
        "impress": Obj({"people": Str(choices=["high", "priests", "soldiers", "traders"]), "bonus": Int(min=0, max=20),
                        "worn": Bool(optional=True)}, optional=True),
        "bonus": Obj({"skills": Map(Int(min=-5, max=5))}, optional=True),  # while worn
        "mends": Obj({"materials": List(Str(max_len=20), min_items=1), "cap": Int(min=1, max=100, optional=True)},
                     optional=True),
        "pry": Bool(optional=True), "dig": Bool(optional=True), "washes": Bool(optional=True),
        "alarm": Bool(optional=True), "bind": Str(choices=["rope", "manacles"], optional=True),
        "bearings": Int(min=0, max=10, optional=True), "sight": Int(min=0, max=5, optional=True),
        "how": Str(max_len=300, optional=True),  # where it is used, when it is not used from the pack
        "warmth": Float(min=0, max=10, optional=True), "wind": Float(min=0, max=1, optional=True),
        "water": Float(min=0, max=1, optional=True), "social": Int(min=-3, max=3, optional=True), "hood": Bool(optional=True),
        "tool": Str(max_len=40, optional=True), "light": Any_(optional=True), "container": Any_(optional=True),
        "food": Any_(optional=True), "drink": Any_(optional=True), "use": Any_(optional=True),
        "bedding": Float(min=0, max=15, optional=True),
    }
)
ITEMS = Obj(
    {
        "qualities": Map(Obj({"name": Str(max_len=20), "value": Float(min=0, max=100), "attack": Int(min=-5, max=5),
                              "armor": Int(min=-5, max=5), "durability": Float(min=0, max=10)}), min_items=1),
        "materials": Map(Obj({"name": Str(max_len=30)}), min_items=1),
        "upkeep": Obj({
            "wear": Obj({k: Float(min=0, max=1) for k in ("weapon", "armor", "shield", "helmet")}),
            "battered": Int(min=0, max=100),
            "mend": Obj({"minutes": Int(min=1, max=600), "items": Int(min=1, max=20), "step": Int(min=1, max=100),
                         "step_trained": Int(min=1, max=100), "cap": Int(min=1, max=100),
                         "cap_trained": Int(min=1, max=100)}),
            "hone": Obj({"minutes": Int(min=1, max=240), "damage": Int(min=0, max=5), "restore": Int(min=0, max=100)}),
            "snare": Int(min=-10, max=20),
            "escape": Obj({k: Float(min=0, max=1) for k in ("none", "rope", "manacles")}),
            "evening": Obj({"dc": Int(min=1, max=30), "music": Float(min=0, max=20), "game": Float(min=0, max=20),
                            "cap": Float(min=0, max=100), "minutes": Int(min=1, max=600)}),
            "prayer": Float(min=1, max=72),
            # minutes to put armour on and to take it off, by its kind (PHB 2024 Armor table)
            "don": Map(List(Int(min=0, max=60), min_items=2, max_items=2), optional=True),
        }, optional=True),
        "items": Map(ITEM, min_items=1),
        "starting_packs": Map(WEIGHTED),
    }
)

LOOK_OPTION = Obj({"name": Str(max_len=40), "words": List(Str(max_len=40)),
                   "say": Any_()})  # say: a phrase, or (builds) a list to pick from
LOOK_RACE = Obj({
    "builds": word_list(1, 20), "skins": word_list(1, 20), "eyes": word_list(1, 20), "hair_colours": word_list(1, 20),
    "old_colours": word_list(1, 20),
    "hair_styles": word_list(1, 20), "likely_hair": Map(word_list(1, 20)), "beards": Map(word_list(1, 20)),
    "likely_beards": Map(word_list(1, 20)), "beard_chance": Map(Float(min=0, max=1)), "marks": word_list(1, 20),
    "mark_chance": Float(min=0, max=1), "paints": word_list(1, 20), "paint_colours": word_list(1, 20),
    "paint_chance": Float(min=0, max=1), "features": Map(word_list(1, 20)),
}, strict=True)
for _spec in LOOK_RACE.fields.values():
    _spec.optional = True
LOOKS = Obj({
    "builds": Map(LOOK_OPTION, min_items=1), "skins": Map(LOOK_OPTION, min_items=1), "eyes": Map(LOOK_OPTION, min_items=1),
    "hair_colours": Map(LOOK_OPTION, min_items=1), "hair_styles": Map(LOOK_OPTION, min_items=1),
    "beards": Map(LOOK_OPTION, min_items=1), "marks": Map(LOOK_OPTION, min_items=1), "paints": Map(LOOK_OPTION, min_items=1),
    "paint_colours": Map(LOOK_OPTION, min_items=1),
    "features": Map(Obj({"name": Str(max_len=40), "options": Map(LOOK_OPTION, min_items=1)})),
    "dyes": word_list(1, 30), "races": Map(LOOK_RACE, min_items=1),
})
APPEARANCE = Obj(
    {
        "hair": Map(word_list(1)), "eyes": word_list(1), "build": Map(word_list(1)), "mark": word_list(1, 120),
        "backstory": Map(word_list(1, 300)), "background_lines": Map(word_list(1, 400)), "looks": LOOKS,
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
        "poison": Any_(optional=True), "disease": Str(max_len=40, optional=True), "disease_chance": Float(min=0, max=1, optional=True),
        # On the battle grid: how far a ranged attack carries (feet, normal and long), and breath weapons and the
        # like: an area (shape and size in feet), a saving throw against it, and how it recharges (on a d6 roll).
        "range": List(Int(min=5, max=1000), min_items=2, max_items=2, optional=True),
        "area": Obj({"shape": Str(choices=["cone", "line", "sphere", "cube", "cylinder"]), "size": Int(min=5, max=300)}, optional=True),
        "save": Str(choices=list(ABILITY_IDS), optional=True), "dc": Int(min=1, max=30, optional=True),
        "recharge": Int(min=2, max=6, optional=True),
    }
)
# A creature is its 2025 stat block ("statblock", data/statblocks.json) and its flavour; the numbers below are only for
# a creature written the old way, without a block (rules/engine/statblocks.py; registry checks one or the other).
CREATURE = Obj(
    {
        "statblock": Str(max_len=40, optional=True), "attack_extras": Map(Any_(), optional=True),
        "action_swap": Map(Any_(), optional=True), "override": Map(Any_(), optional=True),
        "name": Str(max_len=40), "plural": Str(max_len=40),
        "kind": Str(max_len=20, optional=True),
        "body": Str(choices=["humanoid", "quadruped", "spider"]),
        "size": Str(choices=["tiny", "small", "medium", "large", "huge", "gargantuan"], optional=True),
        "cr": Float(min=0, max=30, optional=True), "xp": Int(min=0, max=200000, optional=True),
        "ac": Int(min=1, max=30, optional=True), "hp": Str(max_len=12, optional=True),
        "speed": Int(min=0, max=120, optional=True), "abilities": Obj({a: Int(min=1, max=30) for a in ABILITY_IDS}, optional=True),
        "skills": Map(Int(min=-5, max=20), optional=True), "darkvision": Int(min=0, max=120, optional=True),
        "attacks": List(ATTACK, min_items=1, optional=True), "multiattack": Int(min=1, max=6, optional=True),
        "traits": List(Str(max_len=40), optional=True),
        "morale": Str(choices=["beast", "bandit", "soldier", "coward", "warrior", "fanatic", "mindless"]),
        # How it fights (rules/tactics.py): its role and the distance it likes to keep (feet; 0: in their faces).
        "ai": Obj({"role": Str(choices=["brute", "skirmisher", "artillery", "controller", "leader", "support", "lurker",
                                        "solo"]), "range": Int(min=0, max=600, optional=True),
                   "opens_with": Str(max_len=40, optional=True)}, optional=True),
        "names": Str(max_len=30, optional=True),
        "gear": List(List(Any_(), min_items=2, max_items=2)),
        "loot": List(List(Any_(), min_items=2, max_items=2), optional=True),
        "butcher": List(List(Any_(), min_items=2, max_items=2), optional=True),
        "vulnerable": List(Str(max_len=20), optional=True), "immune": List(Str(max_len=20), optional=True),
        # Creatures that cast: spell ids from spells.json, and their casting: ability, save DC, spell attack bonus,
        # and slots per spell level (index 0 = level 1).
        "spells": List(Str(max_len=40), optional=True),
        "spellcasting": Obj({"ability": Str(choices=list(ABILITY_IDS)), "dc": Int(min=1, max=30),
                             "attack": Int(min=-5, max=20), "slots": List(Int(min=0, max=9))}, optional=True),
        "descriptions": word_list(1, 300),
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
        # What it does: effect operations (rules/engine/effects.py; the kernel's start-up check knows every op).
        "effects": List(Obj({"op": Str(max_len=30)}, strict=False), min_items=1),
        "fx": Str(choices=["bolt", "ray", "darts", "touch", "cone", "burst", "shock", "line", "rain", "strike", "zone",
                           "aura", "summon", "teleport", "heal", "buff", "curse", "sleep", "thrown"], optional=True), "components": List(Str(choices=["V", "S", "M"]), optional=True),
        "rounds": Int(min=0, max=100000, optional=True), "targets_up": Int(min=0, max=5, optional=True),
        "target": Str(choices=["enemy", "ally", "self", "downed_ally", "dead_ally", "all_allies", "point", "direction", "item"]),
        "range": Any_(optional=True),
        "area": Obj({"shape": Str(choices=["cone", "line", "sphere", "cube", "cylinder", "emanation"]), "size": Int(min=5, max=300)},
                    optional=True),
        "cast": Str(choices=["action", "bonus", "reaction"], optional=True),
        "affects": Str(choices=["all", "enemies", "allies"], optional=True),
        "concentration": Bool(optional=True),
        "text": Str(max_len=300),
    },
    strict=False,
)
SPELLS = Obj({"spells": Map(SPELL, min_items=1), "starting": Map(Any_())})

COMBAT_TEXT = Obj(
    {
        "locations": Map(WEIGHTED), "part_names": Map(Map(word_list(1))), "hit": Map(word_list(1, 200)),
        "crit": word_list(1), "miss": word_list(1, 200), "armored_miss": word_list(1, 200),
        "ranged_miss": word_list(1, 200), "spell_miss": word_list(1, 200),
        "wound": Map(Map(word_list(1, 200))), "down": word_list(1, 200), "dead": word_list(1, 200),
        "flee": word_list(1, 200), "surrender": word_list(1, 200), "beg": word_list(1, 200),
        "aftermath": Map(word_list(1, 400)),
        "mastery": Map(word_list(1, 200), optional=True),  # a weapon's trick as it lands (rules/engine/handlers/mastery)
    }
)

DATA_FILES.update({
    "creatures.json": CREATURES,
    "spells.json": SPELLS,
    "combat_text.json": COMBAT_TEXT,
})

# ---------------------------------------------------------------------------- the rules kernel (Expansion 1)
SIZES_2025 = ("tiny", "small", "medium", "large", "huge", "gargantuan")
ADV = Str(choices=["advantage", "disadvantage"], optional=True)
CONDITION_IDS = ("blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated", "invisible", "paralyzed",
                 "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious")
CONDITION = Obj(
    {
        "name": Str(max_len=30), "text": Str(max_len=300),
        "includes": List(Str(choices=list(CONDITION_IDS)), optional=True),
        "inactive": Bool(optional=True), "speed_zero": Bool(optional=True), "crawl": Bool(optional=True),
        "stand_cost": Float(min=0, max=1, optional=True),
        "attacks": ADV, "attacked": ADV, "attacked_near": ADV, "attacked_far": ADV, "checks": ADV, "initiative": ADV,
        "crit_within": Int(min=5, max=30, optional=True),
        "fails_saves": List(Str(choices=list(ABILITY_IDS)), optional=True),
        "saves": Map(Str(choices=["advantage", "disadvantage"]), optional=True),
        "blind": Bool(optional=True), "deaf": Bool(optional=True), "unseen": Bool(optional=True),
        "unless_seen": Bool(optional=True), "drops": Bool(optional=True), "unaware": Bool(optional=True),
        "breaks_concentration": Bool(optional=True), "speechless": Bool(optional=True),
        "resist_all": Bool(optional=True), "immune": List(Str(choices=list(CONDITION_IDS)), optional=True),
        "while_source_seen": Bool(optional=True), "not_against_source": Bool(optional=True),
        "no_harm_source": Bool(optional=True), "no_approach_source": Bool(optional=True),
        "source_social": ADV,
    }
)
CONDITIONS = Obj(
    {
        "conditions": Map(CONDITION, min_items=len(CONDITION_IDS)),
        "exhaustion": Obj({"name": Str(max_len=30), "text": Str(max_len=300), "levels": Int(min=1, max=10),
                           "d20_per_level": Int(min=-5, max=0), "speed_per_level": Int(min=-10, max=0),
                           "long_rest": Int(min=0, max=6)}),
        "bloodied": Obj({"name": Str(max_len=30), "text": Str(max_len=300), "at_most": Float(min=0, max=1)}),
    }
)

# Traits and features as definitions (rules/engine/traits.py). The kernel's start-up check (rules/engine/check.py)
# makes sure every modifier, test, event and handler named here exists.
TRAIT_DEF = Obj(
    {
        "name": Str(max_len=60), "text": Str(max_len=300),
        "modifiers": List(Obj({"when": List(Str(max_len=40), optional=True), "why": Str(max_len=60, optional=True),
                               "abilities": List(Str(choices=list(ABILITY_IDS)), optional=True)}, strict=False),
                          optional=True),
        "hooks": List(Obj({"event": Str(max_len=30), "as": Str(choices=["self", "attacker", "target", "ally", "any"]),
                           "handler": Str(max_len=40), "reaction": Bool(optional=True)}, strict=False), optional=True),
        "resource": Obj({"id": Str(max_len=40), "max": Any_(), "recover": Str(choices=["short", "long", "dawn", "turn"])},
                        optional=True),
        "where": Str(max_len=30, optional=True),
        "activate": Any_(optional=True),  # abilities it gives (rules/engine/actions.py; checked by rules/engine/check.py)
    }
)
TRAITS = Obj({"traits": Map(TRAIT_DEF, min_items=1)})

FEAT_CHOICE = Obj({"kind": Str(choices=["skill", "skill_or_tool", "tool", "spell_list", "cantrip", "spell", "ability"]),
                   "from": Any_(optional=True), "count": Int(min=1, max=6, optional=True),
                   "level": Int(min=0, max=9, optional=True)})
FEATS = Obj({"feats": Map(Obj({"name": Str(max_len=40), "category": Str(choices=["origin", "general", "fighting_style",
                                                                                   "epic"]),
                               "text": Str(max_len=500), "trait": Str(max_len=40, optional=True),
                               "repeatable": Bool(optional=True), "prerequisite": Any_(optional=True),
                               "upgrade_in": Int(min=2, max=26, optional=True),
                               "choices": Map(FEAT_CHOICE, optional=True)}), min_items=1)})

STATBLOCK = Obj(
    {
        "name": Str(max_len=60), "page": Int(min=1, max=500), "size": Str(choices=list(SIZES_2025)),
        "type": Str(max_len=20), "ac": Int(min=1, max=30), "initiative": Int(min=-10, max=30), "hp": Str(max_len=16),
        "speed": Map(Any_()), "abilities": Obj({a: Int(min=1, max=30) for a in ABILITY_IDS}),
        "cr": Float(min=0, max=30), "xp": Int(min=0, max=200000), "pb": Int(min=2, max=9),
        "treasure": List(Str(choices=["any", "individual", "arcana", "armaments", "implements", "relics", "none"]),
                         optional=True),
        "actions": List(Obj({"id": Str(max_len=40), "name": Str(max_len=60), "kind": Str(max_len=20)}, strict=False)),
    },
    strict=False,
)
STATBLOCKS = Obj({"statblocks": Map(STATBLOCK)})

DATA_FILES.update({
    "conditions.json": CONDITIONS,
    "traits.json": TRAITS,
    "feats.json": FEATS,
    "statblocks.json": STATBLOCKS,
})

STAGE_EFFECTS = Obj(
    {"penalty": Int(min=0, max=10, optional=True), "thirst": Float(min=0, max=5, optional=True),
     "hunger": Float(min=0, max=5, optional=True), "fatigue": Float(min=0, max=5, optional=True),
     "strain": Float(min=0, max=10, optional=True), "hp_per_day": Int(min=0, max=50, optional=True),
     "travel": Float(min=1, max=5, optional=True), "pain": Int(min=0, max=10, optional=True)}
)
DISEASE = Obj(
    {
        "name": Str(max_len=40), "text": Str(max_len=400),
        "spread": List(Str(choices=["bad_water", "bad_food", "filth", "infection", "cold_wet", "marsh", "town",
                                    "rat_bite", "animal_bite", "undead"]), min_items=1),
        "incubation_hours": List(Int(min=0, max=5000), min_items=2, max_items=2), "save_dc": Int(min=0, max=30),
        "stages": List(Obj({"name": Str(max_len=60), "hours": Int(min=1, max=10000), "effects": STAGE_EFFECTS}),
                       min_items=1),
        "recovery_dc": Int(min=0, max=99), "recoveries": Int(min=0, max=99),
        "treatments": Map(Int(min=0, max=10)), "cure": List(Str(max_len=40)),
        "cure_before_symptoms": Bool(optional=True), "fatal": Bool(), "death_dc": Int(min=0, max=99, optional=True),
        "immunity": Bool(), "recurring": Float(min=0, max=1, optional=True),
        "lasting": Obj({"chance": Float(min=0, max=1), "injury": Str(max_len=40)}, optional=True),
    }
)
DISEASES = Obj({"diseases": Map(DISEASE, min_items=1)})
INJURY = Obj(
    {"name": Str(max_len=40), "text": Str(max_len=300), "parts": List(Str(max_len=20)),
     "effects": Obj({"skills": Map(Int(min=-10, max=10), optional=True), "attack": Int(min=-5, max=5, optional=True),
                     "ranged_attack": Int(min=-5, max=5, optional=True), "travel": Float(min=1, max=3, optional=True),
                     "speed": Int(min=-30, max=0, optional=True)})}
)
HEALTH = Obj({"injuries": Map(INJURY, min_items=1)})

DATA_FILES.update({
    "diseases.json": DISEASES,
    "health.json": HEALTH,
})

NIGHT_SOUNDS = Map(word_list(1, 200), min_items=1)
CAMPING = Obj(
    {
        "firewood": Map(Str(choices=["plenty", "some", "little", "none"])),
        "shelter": Map(Int(min=0, max=30), optional=True),
        "forage": Map(Obj({"dc": Int(min=0, max=30), "winter_dc": Int(min=0, max=20),
                           "find": List(List(Any_(), min_items=2, max_items=2), min_items=1),
                           "extra": List(List(Any_(), min_items=3, max_items=3))})),
        "hunt": Map(Obj({"dc": Int(min=0, max=30), "game": List(List(Any_(), min_items=4, max_items=4), min_items=1)})),
        "fish": Obj({"dc": Int(min=0, max=30), "tackle_bonus": Int(min=0, max=10), "catch": List(Any_(), min_items=2, max_items=2)}),
        "cooking": Map(Obj({"becomes": Str(max_len=40), "needs_pot": Bool(optional=True)})),
        "night": NIGHT_SOUNDS,
        "crafts": Map(Obj({"name": Str(max_len=40), "needs": List(List(Any_(), min_items=2, max_items=2), min_items=1),
                           "gives": List(List(Any_(), min_items=2, max_items=2), min_items=1),
                           "minutes": Int(min=1, max=600), "skill": Str(max_len=20), "dc": Int(min=0, max=30),
                           "text": Str(max_len=200), "fire": Bool(optional=True),
                           "tool": Str(max_len=30, optional=True)})),
    }
)


def outcome_spec(optional: bool = False) -> Obj:
    """What happens after a travel-event choice (see data/travel_events.json)."""
    return Obj(
        {
            "text": word_list(1, 400), "items": List(List(Any_(), min_items=2, max_items=2), optional=True),
            "loot": List(List(Any_(), min_items=3, max_items=3), optional=True),
            "money": Int(min=-100000, max=100000, optional=True), "xp": Int(min=0, max=10000, optional=True),
            "deed": Str(max_len=120, optional=True), "news": Bool(optional=True),
            "fatigue": Float(min=-100, max=100, optional=True),
            "effect": List(Any_(), min_items=2, max_items=2, optional=True), "fight": Str(max_len=40, optional=True),
            "ambush": List(Any_(), min_items=2, max_items=2, optional=True), "time": Int(min=0, max=10000, optional=True),
            "let_in": Bool(optional=True), "until_dawn": Bool(optional=True), "hurt": Str(max_len=20, optional=True),
        },
        optional=optional,
    )


OUTCOME = outcome_spec()
EVENT_OPTION = Obj(
    {
        "label": Str(max_len=80), "requires": Obj({"items": List(List(Any_(), min_items=2, max_items=2), optional=True),
                                                  "money": Int(min=0, max=10**7, optional=True)}, optional=True),
        "outcome": outcome_spec(optional=True),
        "check": Obj({"skill": Str(max_len=30), "dc": Int(min=0, max=40), "success": OUTCOME, "failure": OUTCOME},
                     optional=True),
        "shop": Obj({"stock": List(List(Any_(), min_items=2, max_items=2), min_items=1), "markup": Float(min=0.1, max=10)},
                    optional=True),
    }
)
TRAVEL_EVENT = Obj(
    {
        "name": Str(max_len=60),
        "where": Obj({"road": Bool(optional=True), "biomes": List(Str(max_len=30), min_items=1),
                      "danger": List(Int(min=0, max=10), min_items=2, max_items=2), "time": Str(choices=["any", "day", "night"]),
                      "season": Any_()}),
        "weight": Float(min=0, max=100), "intro": word_list(1, 400), "options": List(EVENT_OPTION, min_items=1),
    }
)
TRAVEL_EVENTS = Obj({"events": Map(TRAVEL_EVENT, min_items=1)})

DATA_FILES.update({
    "camping.json": CAMPING,
    "travel_events.json": TRAVEL_EVENTS,
})

OCCUPATION = Obj(
    {
        "name": Str(max_len=40), "titles": Map(Str(max_len=40), optional=True),
        "place": Str(choices=["inn", "temple", "smithy", "store", "healer", "stable", "hall", "keep", "stall", "street",
                              "home", "bakery", "brewery", "library", "barracks", "warehouse", "bathhouse", "bank"]),
        "notable": Bool(optional=True), "social": Str(choices=["low", "middle", "high"]),
        "purse": List(Int(min=0, max=10**7), min_items=2, max_items=2), "stats": Str(max_len=40),
        "trade": Str(max_len=40, optional=True), "services": List(Str(max_len=40), optional=True),
        "sex": Str(choices=["male", "female"], optional=True), "near": Str(max_len=20, optional=True),
    }
)
PEOPLE = Obj(
    {
        "occupations": Map(OCCUPATION, min_items=1),
        "settlement_people": Map(Obj({"notables": List(Str(max_len=40)), "commoners": List(Int(min=0, max=50), min_items=2, max_items=2),
                                      "guards": List(Int(min=0, max=20), min_items=2, max_items=2),
                                      "folk": List(Int(min=1, max=1000), min_items=2, max_items=2, optional=True)})),
        "commoner_jobs": List(Str(max_len=40), min_items=1),
        "town_jobs": List(Str(max_len=40), optional=True),
        "workers": Map(List(Str(max_len=40), min_items=1), optional=True),
        "days": Map(List(List(Any_(), min_items=2, max_items=2), min_items=1), optional=True),
        "barks": Map(word_list(1, 80), optional=True),
        "personality": Map(Obj({"disposition": Int(min=-50, max=50), "bribe": Int(min=-50, max=50),
                                "threat": Int(min=-10, max=10), "words": Str(max_len=60)}), min_items=2),
        "speech": word_list(1),
        "text": Map(word_list(1, 300)),
    }
)
DIALOGUE = Obj(
    {
        "greeting": Map(word_list(1, 300)), "greeting_job": Map(word_list(1, 300)),
        "remember_threat": word_list(1, 300), "remember_help": word_list(1, 300),
        "who_are_you": word_list(1, 300), "who_are_you_ruler": word_list(1, 300), "tell_about_self": word_list(1, 300),
        "about_place": word_list(1, 300), "size_line": Map(Str(max_len=300)),
        "no_rumours": word_list(1, 300), "rumour_intro": word_list(1, 300), "flavour_rumours": word_list(1, 300),
        "danger_rumour": word_list(1, 300), "threat_words": Map(Str(max_len=100)), "about_person": word_list(1, 300),
        "person_lines": word_list(1, 300), "threaten_success": word_list(1, 300), "threaten_failure": word_list(1, 300),
        "bribe_accept": word_list(1, 300), "bribe_refuse": word_list(1, 300), "refuse_talk": word_list(1, 300),
        "closed": word_list(1, 300), "goodbye": word_list(1, 300), "special": Map(List(Any_())),
    }
)

DATA_FILES.update({
    "people.json": PEOPLE,
    "dialogue.json": DIALOGUE,
})

SHOP = Obj({"name": Str(max_len=40), "buys": List(Str(max_len=20), min_items=1),
            "stock": List(List(Any_(), min_items=3, max_items=3), min_items=1), "markup": Float(min=0.1, max=5)})
ECONOMY = Obj(
    {
        "shops": Map(SHOP, min_items=1),
        "size": Map(Obj({"stock": Float(min=0, max=10), "coin": Int(min=0, max=10**7)}), min_items=1),
        "production": Map(Map(Float(min=0.05, max=5))),
        "trade_goods_scarcity": Float(min=0.5, max=5),
        "kind_prices": Map(Map(Float(min=0.1, max=5))),
        "season_prices": Map(Map(Float(min=0.1, max=5))),
        "sell_ratio": Float(min=0, max=1), "sell_ratio_trade": Float(min=0, max=1),
        "restock_days": Int(min=1, max=365),
        "haggle": Obj({"dc": Int(min=0, max=40), "per_point": Float(min=0, max=1), "max": Float(min=0, max=1)}),
        "animals": Map(Obj({"name": Str(max_len=40), "price": Int(min=0, max=10**7), "carry": Int(min=0, max=2000),
                            "ride": Float(min=0.1, max=2), "days_without_food": Int(min=1, max=30)}), min_items=1),
        "grazing": List(Str(max_len=30)),
        "ride_lands": Map(Float(min=0, max=1), optional=True),
        "services": Obj({"room_common": Int(min=0), "room_private": Int(min=0), "meal": Int(min=0), "bath": Int(min=0),
                         "size_factor": Map(Float(min=0.1, max=10)), "treat_per_wound": Map(Int(min=0)),
                         "surgery": Int(min=0), "herbal_cure": Int(min=0), "prayer_healing": Int(min=0),
                         "cure_disease": Int(min=0), "repair_share": Float(min=0, max=2),
                         "labour_pay": List(Int(min=0), min_items=2, max_items=2)}),
    }
)

DATA_FILES.update({"economy.json": ECONOMY})

# ---------------------------------------------------------------------------- factions (M6)
VALUE_IDS = ("pious", "mercantile", "xenophobic", "honor-bound", "expansionist", "secretive", "warlike", "tolerant",
             "cruel", "learned")
FAITH = Obj(
    {
        "name": Str(max_len=60), "god": Str(max_len=60), "short": Str(max_len=40), "about": Str(max_len=120),
        "cultures": List(Str(max_len=30)), "church": Bool(optional=True), "cult": Bool(optional=True),
        "values": List(Str(choices=VALUE_IDS)),
    }
)
FACTION_KIND = Obj(
    {
        "label": Str(max_len=40), "group": Str(choices=["realms", "wild", "guilds", "faiths", "outlaws"]),
        "secret": Bool(optional=True), "leader": List(Str(max_len=30), min_items=2, max_items=2),
        "names": word_list(1, 80), "values": List(List(Any_(), min_items=2, max_items=2), min_items=1),
        "wealth": List(Int(min=0, max=10**6), min_items=2, max_items=2),
        "military": List(Int(min=0, max=10**6), min_items=2, max_items=2),
    }
)
LAW_SET = Obj({"magic": Str(choices=["legal", "licensed", "forbidden"]),
               "weapons": Str(choices=["open", "peace_bond", "forbidden"]),
               "religion": Str(choices=["tolerant", "state_only"]), "serfdom": Bool(), "slavery": Bool(),
               "harshness": Str(choices=["lenient", "stern", "harsh", "cruel"])})
FACTIONS = Obj(
    {
        "faiths": Map(FAITH, min_items=1),
        "kinds": Map(FACTION_KIND, min_items=1),
        "groups": Map(Str(max_len=60)),
        "words": Map(word_list(1, 40)),
        "values": Map(Obj({"label": Str(max_len=30), "text": Str(max_len=120), "clashes": List(Str(choices=VALUE_IDS))})),
        "laws": Map(Map(Str(max_len=200))),
        "culture_laws": Map(LAW_SET, min_items=1),
        "value_laws": Map(Map(Str(max_len=30))),
        "standings": List(List(Any_(), min_items=3, max_items=3), min_items=2),
        "relation_states": List(List(Any_(), min_items=3, max_items=3), min_items=2),
        "counts": Map(List(Int(min=0, max=20), min_items=3, max_items=3)),
        "realm_colors": List(COLOR, min_items=4),
    }
)
REQUIRED_FACTION_KINDS = ("kingdom", "noble_house", "free_city", "clan", "highland_clan", "elven_realm", "tribe",
                          "merchant_guild", "thieves_guild", "mages_circle", "mercenary_company", "healers_guild",
                          "smiths_guild", "temple", "knightly_order", "cult", "bandit_gang", "pirate_crew")

DATA_FILES.update({"factions.json": FACTIONS})

# ---------------------------------------------------------------------------- law and crime (M6)
CRIME = Obj({"name": Str(max_len=60), "severity": Int(min=1, max=4), "fine": Int(min=0, max=10**7),
             "value_mult": Float(min=0, max=20, optional=True), "standing": Int(min=-100, max=0),
             "infamy": Int(min=0, max=100), "news": Str(max_len=120)})
JOIN = Obj({"standing": Int(min=-100, max=100), "fee": Int(min=0, max=10**7), "ranks": word_list(4, 40),
            "discount": Float(min=0, max=0.5), "skill": Str(max_len=30, optional=True),
            "tool": Str(max_len=30, optional=True), "classes": List(Str(max_len=30), optional=True),
            "faith": Bool(optional=True), "trains": List(Str(choices=[
                "acrobatics", "animal_handling", "arcana", "athletics", "deception", "history", "insight",
                "intimidation", "investigation", "medicine", "nature", "perception", "performance", "persuasion",
                "religion", "sleight_of_hand", "stealth", "survival"]), optional=True)})
LAW = Obj(
    {
        "crimes": Map(CRIME, min_items=1),
        "punishments": Map(List(List(Str(max_len=20), min_items=1), min_items=4, max_items=4), min_items=4),
        "fine_per_jail_day": Int(min=1, max=10**6),
        "report_minutes": List(Int(min=0, max=10000), min_items=2, max_items=2),
        "bribe": Obj({"share": Float(min=0, max=5), "minimum": Int(min=0), "dc": Int(min=0, max=40)}),
        "run_dc": Int(min=0, max=40), "escape_dc": Int(min=0, max=40), "gallows_escape_dc": Int(min=0, max=40),
        "recognise_chance": Float(min=0, max=1), "guard_sight": Int(min=1, max=40),
        "gate_search_chance": Float(min=0, max=1),
        "contraband": Map(List(Str(max_len=40))), "hunting": Map(Str(choices=["free", "lords_only"])),
        "licence_fee": Int(min=0, max=10**7),
        "rewards": Map(Int(min=0, max=10**7)), "ransom_share": Float(min=0, max=100),
        "join": Map(JOIN), "rank_standing": List(Int(min=-100, max=100), min_items=4, max_items=4),
        "training": Obj({"fee": Int(min=0, max=10**7), "more_per_lesson": Int(min=0, max=10**7),
                         "hours": Int(min=1, max=100)}, optional=True),
        "safehouse": Obj({"fee": Int(min=0, max=10**7), "days": Int(min=1, max=30), "bounty_left": Float(min=0, max=1),
                          "every_days": Int(min=1, max=100)}, optional=True),
        "titles": Obj({"standing": Int(min=0, max=100), "fame": Int(min=0, max=10**4),
                       "names": Map(List(Str(max_len=30), min_items=2, max_items=2))}),
    }
)
PUNISHMENT_STEPS = ("fine", "jail", "labour", "flogging", "branding", "death")

DATA_FILES.update({"law.json": LAW})

# ---------------------------------------------------------------------------- politics and history (M6)
RACE_NUMBERS = Map(Float(min=0.1, max=20))
POLITICS = Obj(
    {
        "history_years": Int(min=0, max=2000),
        "lifespan": RACE_NUMBERS,
        "mortality": Obj({"base": Float(min=0, max=1), "from_age": Int(min=0, max=200),
                          "doubling_years": Float(min=1, max=100)}),
        "reign": Map(List(Int(min=1, max=2000), min_items=2, max_items=2)),
        "birth_rate": Float(min=0, max=1),
        "rates": Map(Float(min=0, max=100)),
        "war_reasons": Map(Str(max_len=80)),
        "causes": Map(word_list(1, 80)),
        "dragons": Obj({"names": word_list(1, 40), "colors": word_list(1, 20), "epithets": word_list(1, 40),
                        "signs": word_list(1, 200)}),
        "artifacts": Obj({"kinds": List(List(Str(max_len=30), min_items=2, max_items=2), min_items=1),
                          "of": word_list(1, 40), "fates": word_list(1, 120)}),
        "legends": Obj({"deeds": word_list(1, 120), "epithets": word_list(1, 40)}),
        "text": Map(word_list(1, 200)),
        "ruin_causes": word_list(1, 60),
        "notices": word_list(1, 200),
    }
)
POLITICS_TEXT = ("succession", "crisis", "elected", "gang_ended", "war", "battle", "siege", "taken", "sacked", "relieved",
                 "peace", "rebellion", "freedom", "crushed", "plague", "famine", "raid", "burned", "cult", "cult_purged",
                 "cult_incident", "gang_new", "gang_destroyed", "dragon", "dragon_tribute", "dragon_slain",
                 "dragon_sleeps", "founded",
                 "ruin", "legend", "artifact", "marriage", "assassination", "treaty", "chapter")
POLITICS_RATES = ("war_base", "war_hostility", "war_battles_per_month", "peace_after_years", "rebellion", "plague",
                  "famine", "tribe_raid", "cult_spread", "cult_purge", "cult_incident", "gang_destroyed", "gang_new",
                  "dragon", "assassination", "marriage", "relation_drift", "military_regrowth", "treaty")

DATA_FILES.update({"politics.json": POLITICS})

# ---------------------------------------------------------------------------- the lived history (world/ages, 2026-10)
BY_SIZE = List(Int(min=0, max=100), min_items=3, max_items=3)
WEIGHTED_WORDS = List(List(Any_(), min_items=2, max_items=2), min_items=1)
BEAST = Obj({"creature": Str(max_len=40), "group": Str(max_len=40), "word": Str(max_len=40),
             "weight": Float(min=0, max=100), "lairs": word_list(1, 20), "biomes": word_list(1, 30),
             "power": Float(min=0, max=50), "life": List(Int(min=1, max=10000), min_items=2, max_items=2),
             "attack": Float(min=0, max=1), "range": Float(min=1, max=100), "names": word_list(3, 40),
             "epithets": word_list(1, 60), "slayer": word_list(1, 40)})
HISTORY = Obj(
    {
        "lengths": List(Int(min=10, max=2000), min_items=1),
        "start": Map(BY_SIZE),
        "rates": Map(Float(min=0, max=1)),
        "peoples_change": Obj({"after": Int(min=1, max=1000),
                               # how many towns a realm founds in another people's country are its own colonists
                               "colonists": Float(min=0, max=1, optional=True)}, optional=True),
        "spots": Obj({"reach": Float(min=5, max=200),
                      "thresholds": Obj({"village": Int(min=1), "town": Int(min=1), "city": Int(min=1)}),
                      "plans": Map(List(Float(min=-5000, max=5000), min_items=2, max_items=2)),
                      "doom_after": Int(min=1, max=500), "doomed": Map(BY_SIZE)}),
        "peoples": Map(Obj({"race": Str(max_len=20), "growth": Float(min=0, max=1),
                            "succession": Str(choices=["male_primogeniture", "primogeniture", "tanistry",
                                                       "seniority", "elective"])})),
        "folk": Obj({"adult": Int(min=1, max=100), "fertile": List(Int(min=1, max=100), min_items=2, max_items=2),
                     "child_death": Float(min=0, max=1), "marry": Float(min=0, max=1),
                     "alliance_marriage": Float(min=0, max=1), "marriage_bond": Float(min=0, max=100),
                     "birth": Float(min=0, max=1), "birth_decay": Float(min=0, max=1),
                     "max_children": Int(min=0, max=30), "named_after": Float(min=0, max=1),
                     "callings": Map(WEIGHTED_WORDS)}),
        "realms": Obj({"elder": Map(List(Int(min=0, max=10000), min_items=2, max_items=2)),
                       "spread": Float(min=0, max=1), "old_realm_age": List(Int(min=0), min_items=2, max_items=2),
                       "lordship_age": List(Int(min=0), min_items=2, max_items=2),
                       "church_age": List(Int(min=0), min_items=2, max_items=2), "drift": Float(min=0, max=50),
                       "border_friction": Float(min=0, max=50)}),
        "war": Obj({"reach": Float(min=1, max=500), "border_reach": Float(min=0, max=500, optional=True),
                    "base": Float(min=0, max=1), "hostility": Float(min=0, max=1),
                    "defender_edge": Float(min=0.1, max=5), "tribe_factor": Float(min=0, max=1),
                    "battles": List(Float(min=0, max=1), min_items=1, max_items=4)}),
        "heroes": Obj({"infamy": Int(min=0, max=100), "classes": WEIGHTED_WORDS}),
        "causes": Map(word_list(1, 80)),
        "epithets": Map(word_list(1, 40)),
        "beasts": Map(BEAST),
        "barrows": Obj({"titles": List(List(Str(max_len=30), min_items=2, max_items=2), min_items=1),
                        "epithets": word_list(1, 40)}),
        "elder_ruins": Obj({"was": word_list(1, 60), "peoples": word_list(1, 80), "causes": word_list(1, 120)}),
        "abandoned": Map(word_list(1, 120)),
        "ruin_names": Map(word_list(1, 60)),
        "pantheon": Map(Obj({"spheres": word_list(1, 30), "sex": Str(choices=["male", "female"], optional=True),
                             "lesser": List(List(Any_(), min_items=2, max_items=2))})),
        "artifacts": Obj({"kinds": Map(Obj({"word": Str(max_len=30), "weight": Float(min=0, max=100),
                                            "materials": word_list(1, 40)})),
                          "kennings": Map(word_list(1, 40)), "of": word_list(1, 40),
                          "adjectives": word_list(1, 30), "why": word_list(1, 80), "old_fates": word_list(1, 120),
                          "cultures": Map(Obj({"kennings": Map(word_list(1, 40)), "of": word_list(1, 40),
                                               "adjectives": word_list(1, 30)}), optional=True)}),
        "works": Obj({"forms": Map(Obj({"word": Str(max_len=30), "author": Str(max_len=30),
                                        "titles": word_list(1, 80)}))}),
        "eras": Obj({"myth": word_list(1, 60), "thresholds": Map(Float(min=0, max=10**6)),
                     "themes": Map(Obj({"names": word_list(1, 60), "summary": word_list(1, 200)})),
                     "stand_out": Float(min=1, max=100, optional=True), "quiet": Float(min=0, max=1, optional=True),
                     "least": Float(min=0, max=10, optional=True)}),
        "names": Obj({"war": Map(word_list(1, 80)), "battle": Map(word_list(1, 80)), "peace": word_list(1, 80),
                      "plague": word_list(1, 80)}),
        "words": Map(word_list(1, 80)),
        "text": Map(word_list(1, 300)),
        "speech": Map(word_list(1, 200), optional=True),
        "ties": Obj({"war": word_list(1, 200), "deed_beast": word_list(1, 200), "deed_raid": word_list(1, 200),
                     "noble": word_list(1, 200)}, optional=True),
        "scars": Map(word_list(1, 300), optional=True),
        "grudges": Map(word_list(1, 200), optional=True),
    }
)
HISTORY_TEXT = ("came_under", "became_town", "became_city", "settled", "founded_seat", "founded_town",
                "founded_lordship", "rebuilt", "wedding", "succession", "succession_minor", "came_of_age",
                "regent_usurps", "crisis", "house_ended", "granted", "fealty", "charter", "proclaimed",
                "assassination", "elected", "gang_ended", "war_named", "rebellion", "joined_war", "battle_named",
                "fell", "captured", "executed_captive", "ransomed", "relieved", "razed", "sacked", "taken",
                "peace_named", "ceded", "freedom", "crushed", "plague", "great_plague", "famine", "tribe_rose", "raid",
                "burned", "abducted", "beast_came", "dragon_came", "dragon", "dragon_tribute", "dragon_sleeps",
                "dragon_wakes", "beast_attack", "beast_slain", "dragon_slain", "hero_fell", "beast_died",
                "beast_destroyed", "burned_down", "abandoned", "elder_fall", "barrow_raised", "laid_to_rest",
                "tower_raised", "chapter", "church_founded", "temple_raised", "heresy", "persecution", "martyred",
                "sainted", "cult_destroyed", "faction_fell", "company_disbanded", "pirates_ended", "artifact_made",
                "artifact_stolen", "thief_caught", "artifact_found", "hero_lost", "artifact_lost_old", "work_written",
                "guild_founded", "guild_secret", "circle_founded", "healers_founded", "order_founded",
                "company_founded", "gang_new", "gang_destroyed", "pirates_new", "knighted", "died", "slain",
                "peace_small", "assassination_unknown", "outlaws_hunted", "hero_fell_outlaws")

DATA_FILES.update({"history.json": HISTORY})

# ---------------------------------------------------------------------------- companions (M7)
ARCHETYPE = Obj({"name": Str(max_len=40), "classes": word_list(1, 30), "background": Str(max_len=30),
                 "values": word_list(1, 30), "want": Str(choices=["pay", "loot", "cause", "knowledge", "revenge"]),
                 "where": List(Str(choices=["inn", "company"]), min_items=1), "weight": Float(min=0, max=100),
                 "story": word_list(1, 300)})
COMPANIONS = Obj(
    {
        "max_companions": Int(min=0, max=8),
        "archetypes": Map(ARCHETYPE, min_items=1),
        "values": Map(Obj({"label": Str(max_len=40), "likes": word_list(0, 40), "hates": word_list(0, 40)})),
        "reactions": Obj({"likes": Float(min=0, max=50), "hates": Float(min=-50, max=0)}),
        "wage": Obj({"base": Int(min=0), "per_level": Int(min=0), "upfront_days": Int(min=0, max=60)}),
        "share": Float(min=0, max=1),
        "loyalty": Obj({"start": Int(min=0, max=100), "complain": Int(min=0, max=100), "desert": Int(min=0, max=100),
                        "devoted": Int(min=0, max=100)}),
        "bonds": Map(Obj({"label": Str(max_len=30), "text": Str(max_len=300), "loyalty": Int(min=0, max=100, optional=True),
                          "classes": List(Str(max_len=30), min_items=1, optional=True),
                          "background": Str(max_len=30, optional=True), "values": List(Str(max_len=30), optional=True),
                          "want": Str(choices=["pay", "loot", "cause", "knowledge", "revenge"], optional=True),
                          "share": Float(min=0, max=1, optional=True), "jobs": List(Str(max_len=30), optional=True),
                          "story": List(Str(max_len=300), min_items=1, optional=True),
                          "titles": Map(Str(max_len=60), optional=True),
                          "kit": Map(List(List(Any_(), min_items=2, max_items=2)), optional=True),
                          "lines": Map(word_list(1, 300), optional=True)}), min_items=1),
        "lines": Map(word_list(1, 300)),
    }
)
COMPANION_LINES = ("hired", "approve", "disapprove", "complain", "unpaid", "desert", "leave", "devoted", "battle",
                   "camp", "level_up", "mood_good", "mood_fair", "mood_bad", "road", "road_tired", "road_wet",
                   "road_night", "road_cold", "road_hot")
BONDS = ("hired", "grateful", "sworn", "dreamer", "restless", "refugee", "admirer")  # why they follow you

DATA_FILES.update({"companions.json": COMPANIONS})

# ---------------------------------------------------------------------------- unique companions (after v1)
UNIQUE_PERKS = ("vigil", "dragonlore", "unhangable", "plaguebell", "tribes", "remembrance", "backroads")
UNIQUE_PLACES = ("barrow", "dragon", "gaol", "sickness", "penance", "memory", "road")
UNIQUE_ITEM = Obj({"base": Str(max_len=30), "title": Str(max_len=60), "rarity": Str(choices=["uncommon", "rare", "very_rare"]),
                   "props": List(Obj({"kind": Str(max_len=20), "value": Int(min=0, max=20),
                                      "skill": Str(max_len=30, optional=True), "type": Str(max_len=20, optional=True),
                                      "ability": Str(max_len=5, optional=True), "spell": Str(max_len=30, optional=True)}),
                                 min_items=1),
                   "story": Str(max_len=400),
                   "look": Obj({"metal": Str(max_len=20, optional=True), "cloth": Str(max_len=20, optional=True),
                                "emblem": Str(max_len=20, optional=True), "glow": Str(max_len=20, optional=True)},
                               optional=True)})
UNIQUE = Obj(
    {
        "name": Str(max_len=40), "known_as": Str(max_len=60), "epithet": Str(max_len=80), "title": Str(max_len=40),
        "role": Str(max_len=40),
        "sex": Str(choices=["male", "female"]), "age": Int(min=14, max=2000), "race": Str(max_len=30),
        "culture": Str(max_len=30), "class": Str(max_len=30), "subclass": Str(max_len=30, optional=True),
        "background": Str(max_len=30), "style": Str(max_len=30, optional=True), "level": Int(min=1, max=10),
        "scores": Obj({a: Int(min=3, max=18) for a in ("str", "dex", "con", "int", "wis", "cha")}),
        "skills": word_list(1, 30), "expertise": List(Str(max_len=30)),
        "cantrips": List(Str(max_len=30), optional=True), "spells": List(Str(max_len=30), optional=True),
        "kit": List(List(Any_(), min_items=2, max_items=2)), "item": UNIQUE_ITEM,
        "values": word_list(1, 30), "likes": List(Str(max_len=30)), "hates": List(Str(max_len=30)),
        "want": Str(choices=["pay", "loot", "cause", "knowledge", "revenge"]),
        "perk": Str(choices=UNIQUE_PERKS), "perk_text": Str(max_len=200), "personal": word_list(1, 30),
        "where": Str(choices=UNIQUE_PLACES), "building": word_list(1, 20), "stats": Str(max_len=30),
        "traits": word_list(1, 30), "speech": Str(max_len=200),
        "profile": Obj({k: Str(max_len=700) for k in ("appearance", "personality", "backstory", "secret", "want")}),
        "bond": Str(max_len=30), "bond_text": Map(Str(max_len=300), min_items=1),
        "rumours": word_list(1, 300), "talk": Map(word_list(1, 900), min_items=1),
        "lines": Map(word_list(1, 300), min_items=1),
    }
)
UNIQUES = Obj({"uniques": Map(UNIQUE, min_items=1), "banter": Map(word_list(1, 400)),
               "remembrance": word_list(1, 300)})

DATA_FILES.update({"uniques.json": UNIQUES})

# ---------------------------------------------------------------------------- magic items (M8)
MAGIC = Obj(
    {
        "rarities": Map(Obj({"budget": Float(min=0, max=10), "value_mult": Float(min=0, max=1000),
                             "value_add": Int(min=0, max=10**8), "tier": Int(min=0, max=10)}), min_items=1),
        "properties": Map(Obj({"label": Str(max_len=60), "cost": Float(min=0, max=10), "max": Int(min=1, max=10),
                               "step": Int(min=1, max=20, optional=True), "for": word_list(1, 20)}), min_items=1),
        "skills": word_list(1, 30), "resist_types": word_list(1, 20), "abilities": word_list(1, 5),
        "charge_spells": word_list(1, 40), "cursed_chance": Float(min=0, max=1),
        "curses": List(Obj({"text": Str(max_len=200), "effect": Str(max_len=20), "value": Int(min=-20, max=0),
                            "skill": Str(max_len=30, optional=True)}), min_items=1),
        "bases": Map(word_list(1, 40)),
        "names": Obj({"patterns": word_list(1, 80), "epithets": word_list(1, 30)}),
        "stories": word_list(1, 300),
        "looks": Obj({
            "metal": List(List(Any_(), min_items=2, max_items=2)), "cloth": List(List(Any_(), min_items=2, max_items=2)),
            "emblem": List(List(Any_(), min_items=2, max_items=2)), "glow_props": Map(Str(max_len=20)),
            "glow_chance": Map(Float(min=0, max=1)), "glows": word_list(1, 20), "metals": word_list(1, 20),
            "cloths": word_list(1, 20), "emblems": word_list(1, 20)}),
        "attune_props": word_list(0, 20), "attune_from": Str(max_len=20),
        "artifact": Obj({"count": Map(List(Int(min=0, max=4), min_items=2, max_items=2)),
                         "minor_good": List(List(Any_(), min_items=3, max_items=3), min_items=1),
                         "major_good": List(List(Any_(), min_items=3, max_items=3), min_items=1),
                         "minor_bad": List(List(Any_(), min_items=3, max_items=3), min_items=1),
                         "major_bad": List(List(Any_(), min_items=3, max_items=3), min_items=1),
                         "properties": Map(Obj({"text": Str(max_len=200)}, strict=False), min_items=1),
                         "hated_types": word_list(1, 20), "destroy": word_list(1, 300)}),
        "sentient": Obj({"chance": Map(Float(min=0, max=1)), "alignment": List(List(Any_(), min_items=3, max_items=3)),
                         "communication": List(List(Any_(), min_items=3, max_items=3)),
                         "senses": List(List(Any_(), min_items=3, max_items=3)),
                         "purposes": Map(Obj({"name": Str(max_len=30), "text": Str(max_len=200),
                                              "pleased": word_list(1, 30), "angered": word_list(1, 30)})),
                         "protects": word_list(1, 80), "demands": Map(Str(max_len=200)),
                         "voices": Map(Map(word_list(1, 200))), "withheld": Str(max_len=200),
                         "seized": Str(max_len=200), "freed": Str(max_len=200), "satisfied": Str(max_len=200)}),
    }
)

DATA_FILES.update({"magic.json": MAGIC})

# ---------------------------------------------------------------------------- treasure (Expansion 1, DMG 2024)
_BAND = List(Any_(), min_items=5, max_items=5)
TREASURE = Obj(
    {
        "coins": Map(Int(min=1, max=10000)),
        "individual": List(_BAND, min_items=1), "hoard": List(_BAND, min_items=1),
        "rarity": List(List(Any_(), min_items=3, max_items=3), min_items=1),
        "themes": Map(Obj({"money": word_list(1, 20), "kinds": word_list(1, 20)}), min_items=4),
        "gems": Map(Obj({"item": Str(max_len=40), "names": word_list(1, 60)}), min_items=1),
        "art": Map(Obj({"item": Str(max_len=40), "names": word_list(1, 80)}), min_items=1),
        "bars": List(List(Any_(), min_items=2, max_items=2), min_items=1),
        "goods": List(List(Any_(), min_items=2, max_items=2), min_items=1),
        "makers": Map(Map(Obj({"item": Str(max_len=40, optional=True), "scroll": Bool(optional=True),
                               "kind": Str(max_len=20, optional=True), "props": List(Map(Any_()), optional=True),
                               "attune": Bool(optional=True),
                               "bases": List(Str(max_len=40), optional=True),  # what it may be made on
                               "qty": List(Int(min=1, max=100), min_items=2, max_items=2, optional=True)}))),
        "reroll": Int(min=0, max=50),
        "magic_scale": List(Float(min=0, max=5), min_items=3, max_items=3),
        "tables": Map(List(List(Any_(), min_items=4, max_items=4), min_items=1), min_items=20),
    }
)
DATA_FILES.update({"treasure.json": TREASURE})

# ---------------------------------------------------------------------------- quests (M8)
QUEST_TEMPLATES = ("bounty", "clear_lair", "hunt_beast", "deliver", "retrieve", "rescue", "collect_debt",
                   "investigate", "slay_dragon", "escort", "assassinate", "cure", "feud", "steal", "defend",
                   "smuggle")
QUESTS = Obj(
    {
        "templates": Map(Obj({"givers": word_list(1, 30), "reward": List(Int(min=0, max=10**7), min_items=2, max_items=2),
                              "days": List(Int(min=1, max=365), min_items=2, max_items=2),
                              "standing": Float(min=0, max=50), "xp": Int(min=0, max=100000),
                              "hidden": Map(Float(min=0, max=1))}), min_items=1),
        "beasts": List(List(Str(max_len=120), min_items=3, max_items=3), min_items=1),
        "kin": word_list(1, 30),
        "heirlooms": List(List(Str(max_len=60), min_items=2, max_items=2), min_items=1),
        "text": Map(Obj({"title": word_list(1, 80), "pitch": word_list(1, 600), "journal": word_list(1, 600),
                         "done": word_list(1, 300), "failed": word_list(1, 300),
                         "hidden": Map(word_list(1, 600), optional=True),
                         "clue": List(Str(max_len=400), min_items=1, optional=True)})),
        "rewards_text": word_list(1, 200),
    }
)

DATA_FILES.update({"quests.json": QUESTS})

# ---------------------------------------------------------------------------- pictures (graphics update)
SPRITE_NAME = Str(max_len=60)
SPRITE_TERRAIN = Obj(
    {
        "ground": Str(max_len=60, optional=True),
        "over": Any_(optional=True),
        "over_chance": Float(min=0, max=1, optional=True),
        "object": Str(max_len=60, optional=True),
        "object_vertical": Str(max_len=60, optional=True),
        "wall": Str(max_len=60, optional=True),
        "water": Bool(optional=True),
        "autotile": Bool(optional=True),
        "animate": Int(min=1, max=8, optional=True),
        "light": List(Any_(), min_items=2, max_items=2, optional=True),
        "cold": Str(max_len=60, optional=True),
    }
)
SPRITES = Obj(
    {
        "terrain": Map(SPRITE_TERRAIN, min_items=1),
        "dungeon_styles": Map(Map(Str(max_len=60))),
        "town_walls": Map(Str(max_len=60)),
        "traps": Map(Str(max_len=60)),
        "figures": Obj({
            "colours": Map(COLOR, min_items=1), "metals": Map(COLOR, min_items=1), "glows": Map(COLOR, min_items=1),
            "skins": Map(Map(COLOR, min_items=1), min_items=1), "hair_colours": Map(COLOR, min_items=1),
            "eye_colours": Map(COLOR, min_items=1), "paint_colours": Map(COLOR, min_items=1),
            "bodies": Map(Map(Map(Int(min=0, max=24)), min_items=2), min_items=1),
            "builds": Map(Map(Int(min=-6, max=6)), min_items=1), "feature_tints": Map(Str(max_len=20, min_len=0)),
            "worn": Map(Any_()), "classes": Map(Map(List(Str(max_len=60, min_len=0), min_items=1))),
            "outfits": Map(Map(List(Str(max_len=60, min_len=0), min_items=1)), min_items=1), "creatures": Map(Map(List(Str(max_len=60, min_len=0), min_items=1))),
            # Dress by people: their everyday wear ("_", "_male", "_female") and by trade, over the trade's outfit.
            "cultures": Map(Map(Map(List(Str(max_len=60, min_len=0), min_items=1))), optional=True),
        }),
        "world": Obj({"biomes": Map(Obj({"color": COLOR, "deep": List(Int(min=0, max=255), min_items=3, max_items=3, optional=True),
                                          "marks": Str(max_len=30, optional=True),
                                          "density": Float(min=0, max=1, optional=True)})),
                      "road": COLOR, "river": COLOR, "ink": COLOR, "shore": COLOR, "paper": COLOR, "sea": COLOR,
                      "settlements": Map(Str(max_len=60)), "sites": Map(Str(max_len=60))}),
    }
)

DATA_FILES.update({"sprites.json": SPRITES})

# ---------------------------------------------------------------------------- sound and music
SOUND = Obj(
    {
        "files": List(Str(max_len=80), min_items=1),
        "group": Str(choices=["interface", "effects"]),
        "volume": Float(min=0, max=2),
        "pitch": Float(min=0, max=0.3, optional=True),
        "cooldown": Float(min=0, max=10, optional=True),
        "max": Int(min=1, max=8, optional=True),
        "priority": Int(min=0, max=9, optional=True),
        "about": Str(max_len=120, optional=True),
    }
)
SOUNDS = Obj({"sounds": Map(SOUND, min_items=1)})
SECONDS_RANGE = List(Float(min=0, max=3600), min_items=2, max_items=2, optional=True)
MOOD = Obj(
    {
        "about": Str(max_len=200),
        "kinds": List(Str(max_len=30), optional=True),
        "fallback": Str(max_len=30, optional=True),
        "gap": SECONDS_RANGE,
        "first": SECONDS_RANGE,
        "fade_in": Float(min=0, max=30, optional=True),
        "fade_out": Float(min=0, max=30, optional=True),
        "resume": Bool(optional=True),
        "once": Bool(optional=True),
        "volume": Float(min=0, max=2, optional=True),
    }
)
MUSIC = Obj({"moods": Map(MOOD, min_items=1)})

DATA_FILES.update({"sounds.json": SOUNDS, "music.json": MUSIC})

# ---------------------------------------------------------------------------- wonders of the world (world/wonders.py)
WONDER_BOONS = ("water", "warm", "heal", "bewilder", "shelter")
WONDER = Obj(
    {
        "what": Str(max_len=60),
        "count": List(Int(min=0, max=12), min_items=3, max_items=3),
        "chance": Float(min=0, max=1),
        "fame": Int(min=0, max=10),
        "mark": Str(max_len=30),
        "names": word_list(1, 60),
        "geo": List(Str(max_len=30)),
        "look": word_list(1, 400),
        "look_awake": List(Str(max_len=400), optional=True),
        "found": word_list(1, 400),
        "boon": List(Str(choices=list(WONDER_BOONS)), optional=True),
    }
)
WONDERS = Obj({"kinds": Map(WONDER, min_items=1)})
DATA_FILES.update({"wonders.json": WONDERS})

# ---------------------------------------------------------------------------- how each people builds (world/towns)
TOWN_LAYOUTS = ("organic", "grid", "medina", "camp", "kremlin", "terraces", "plaza", "longhouse", "hold", "grove",
                "burrows", "stockade")
TOWN_STYLE = Obj(
    {
        "layout": Str(choices=list(TOWN_LAYOUTS)),
        "city_layout": Str(choices=list(TOWN_LAYOUTS), optional=True),
        "street": Str(max_len=40), "lane": Str(max_len=40), "plaza": Str(max_len=40),
        "wall": Str(max_len=40), "palisade": Str(max_len=40),
        "look": Map(List(List(Str(max_len=30), min_items=1), min_items=3, max_items=3)),
        "floor": Str(max_len=40),
        "square": List(Str(max_len=40)), "street_things": List(Str(max_len=40), optional=True),
        "trees": List(Str(max_len=40)), "light": Str(max_len=40),
        "extra": List(Str(max_len=40)),
        # Coming into one of their places: the parts of the description (fallback_text "settlement"), their own.
        "words": Obj({k: word_list(1, 200) for k in ("approach", "sight", "smell", "detail")}, optional=True),
    }
)
TOWNS = Obj({
    "sizes": Map(List(Int(min=32, max=400), min_items=2, max_items=2)),
    "great": Obj({"count": List(Int(min=0, max=5), min_items=3, max_items=3),
                  "times": List(Float(min=1, max=20), min_items=2, max_items=2)}),
    "styles": Map(TOWN_STYLE, min_items=1),
})
DATA_FILES.update({"towns.json": TOWNS})

# ---------------------------------------------------------------------------- expansion packs (data/packs.py)
# A pack's record (data/packs/NN_id/pack.json): who it is on the main menu's shelf, and whether it is out yet.
PACK = Obj({
    "id": Str(max_len=40),
    "order": Int(min=1, max=99),
    "name": Str(max_len=60),
    "tagline": Str(max_len=120),
    "icon": Str(max_len=60),
    "accent": COLOR,
    "status": Str(choices=["planned", "released"]),
    "version": Str(max_len=12),
    "released_on": Str(max_len=10, min_len=0),  # "2026-11-02" once released, "" before
    "adds": word_list(0, 300),
    # What to count on the shelf: [data file, section, label]; "{n} {label}" for what this pack added there.
    "counts": List(List(Str(max_len=40), min_items=3, max_items=3), optional=True),
})
# Kinds of data file that only packs bring: their empty shape, used when data/ has no base file of that name.
PACK_ONLY: dict[str, dict] = {}
