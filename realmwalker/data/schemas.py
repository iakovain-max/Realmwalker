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

TRAVEL_DAY_TABLES = ("passage", "opening", "walking", "closing")

SETTLEMENT_TABLES = ("passage", "approach", "sight", "smell", "detail")

FALLBACK_TEXT = Obj({"tavern": table_set(*TAVERN_TABLES), "travel_day": table_set(*TRAVEL_DAY_TABLES),
                     "settlement": table_set(*SETTLEMENT_TABLES),
                     "weather_change": Map(word_list(1, 200), min_items=1)})

# Slots that code fills in itself (not from a table), per table set.
RUNTIME_SLOTS: dict[str, set[str]] = {
    "tavern": {"family", "keeper"},
    "travel_day": {"name", "miles", "lands", "weather", "mood", "season", "events", "road"},
    "settlement": {"name", "kind", "land", "season"},
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
SITES = Obj({"settlement_types": Map(SETTLEMENT_TYPE, min_items=1), "site_types": Map(SITE_TYPE, min_items=1),
             "dungeon_styles": Map(word_list(1, 300), min_items=1)})
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
                                                          "tool", "focus", "book", "food", "drink", "trade", "jewellery"]),
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
        "slot": Str(choices=["under", "main", "outer", "head", "hands", "feet", "ring", "neck"], optional=True),
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
        "poison": Any_(optional=True), "disease": Str(max_len=40, optional=True), "disease_chance": Float(min=0, max=1, optional=True),
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
        "forage": Map(Obj({"dc": Int(min=0, max=30), "winter_dc": Int(min=0, max=20),
                           "find": List(List(Any_(), min_items=2, max_items=2), min_items=1),
                           "extra": List(List(Any_(), min_items=3, max_items=3))})),
        "hunt": Map(Obj({"dc": Int(min=0, max=30), "game": List(List(Any_(), min_items=4, max_items=4), min_items=1)})),
        "fish": Obj({"dc": Int(min=0, max=30), "tackle_bonus": Int(min=0, max=10), "catch": List(Any_(), min_items=2, max_items=2)}),
        "cooking": Map(Obj({"becomes": Str(max_len=40), "needs_pot": Bool(optional=True)})),
        "night": NIGHT_SOUNDS,
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
        "place": Str(choices=["inn", "temple", "smithy", "store", "healer", "stable", "hall", "keep", "stall", "street"]),
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
                                      "guards": List(Int(min=0, max=20), min_items=2, max_items=2)})),
        "commoner_jobs": List(Str(max_len=40), min_items=1),
        "personality": Map(Obj({"disposition": Int(min=-50, max=50), "bribe": Int(min=-50, max=50),
                                "threat": Int(min=-10, max=10), "words": Str(max_len=60)}), min_items=2),
        "speech": word_list(1),
        "text": Map(word_list(1, 300)),
    }
)
DIALOGUE = Obj(
    {
        "greeting": Map(word_list(1, 300)), "remember_threat": word_list(1, 300), "remember_help": word_list(1, 300),
        "who_are_you": word_list(1, 300), "about_place": word_list(1, 300), "size_line": Map(Str(max_len=300)),
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
            "faith": Bool(optional=True)})
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
        "lines": Map(word_list(1, 300)),
    }
)
COMPANION_LINES = ("hired", "approve", "disapprove", "complain", "unpaid", "desert", "leave", "devoted", "battle",
                   "camp", "level_up", "mood_good", "mood_fair", "mood_bad", "road", "road_tired", "road_wet",
                   "road_night")

DATA_FILES.update({"companions.json": COMPANIONS})

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
    }
)

DATA_FILES.update({"magic.json": MAGIC})

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
        "letters": word_list(1, 200),
        "rewards_text": word_list(1, 200),
    }
)

DATA_FILES.update({"quests.json": QUESTS})
