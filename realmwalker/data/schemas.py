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

NAMES = Obj({"cultures": Map(CULTURE, min_items=1),
             # Expansion 3 F.1: names for a familiar and a steed (game/allies.py)
             "familiars": Obj({"familiar": word_list(5, 20), "steed": word_list(5, 20)}, optional=True)})

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
        "skills": Map(Obj({"name": Str(max_len=30), "ability": Str(choices=list(ABILITY_IDS)),
                           "text": Str(max_len=200, optional=True)}), min_items=18),
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
                           "deadly": Float(min=1, max=10), "most_extra": Float(min=1, max=5),
                           "tiers": List(List(Float(min=1, max=20), min_items=2), optional=True),
                           "legend_hp": List(Float(min=1, max=10), min_items=4, optional=True),
                           "deeper_level": List(Int(min=1, max=20), min_items=1, optional=True)}, optional=True),
        "travel_pace": Obj({"paces": Map(Obj({"name": Str(max_len=20), "time": Float(min=0.1, max=5),
                                              "passive": Int(min=-10, max=10)}, strict=False), min_items=3),
                            "max": Map(Str(choices=["fast", "normal", "slow"]))}, optional=True),
        "attitudes": Obj({"influence": Map(Str(choices=["advantage", "none", "disadvantage"])),
                          "start": Map(Map(Int(min=0, max=100))), "moods": Map(Str(max_len=20)),
                          "default_dc": Int(min=1, max=30)}, optional=True),
        "study": Obj({"skills": Map(Str(max_len=30)),
                      "dc": Obj({"base": Int(min=1, max=30), "per_cr": Float(min=0, max=5), "max": Int(min=1, max=40)})},
                     optional=True),
        "spell_scrolls": Obj({"dc": List(Int(min=1, max=30), min_items=10, max_items=10),
                              "attack": List(Int(min=0, max=20), min_items=10, max_items=10),
                              "rarity": List(Str(choices=["common", "uncommon", "rare", "very_rare", "legendary"]),
                                             min_items=10, max_items=10),
                              "value": List(Int(min=0, max=10**9), min_items=10, max_items=10)}, optional=True),
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
               "rule": Str(max_len=40, optional=True),
               "gives": Obj({"saves": List(Str(choices=list(ABILITY_IDS)), optional=True),
                             "tools": List(Str(max_len=40), optional=True),
                             "items": List(Str(max_len=40), optional=True),
                             "armor": List(Str(max_len=20), optional=True),
                             "weapons": List(Str(max_len=30), optional=True),
                             # a feat taken with the feature, its choices asked as a feat's are (Student of War)
                             "feat": Str(max_len=40, optional=True)}, optional=True),
               "choose": List(Str(max_len=40), optional=True),
               # how many of `choose` are picked at once (a Battle Master's maneuvers: three, then two at a time)
               "choose_count": Int(min=1, max=5, optional=True),
               # Expertise to choose (a wizard's Scholar: one of these skills they know; no list: any skill they know).
               "expertise": Obj({"count": Int(min=1, max=4), "skills": List(Str(max_len=30), optional=True)},
                                optional=True),
               # A wizard school's Savant: two spells of the school (level 1-2) at once, one more with each new slot level.
               "savant": Str(max_len=20, optional=True),
               # Cantrips beyond the table's count (Improved Illusions), and the one it teaches when not yet known.
               "cantrips": Int(min=1, max=3, optional=True),
               "learns": Str(max_len=40, optional=True),
               # Spells picked from the spellbook for a feature (Spell Mastery, Signature Spells), kept in spells[key].
               "picks": List(Obj({"key": Str(choices=["mastery", "signature"]), "spell_level": Int(min=1, max=9),
                                  "count": Int(min=1, max=3), "cast": Str(choices=["action"], optional=True)}),
                             optional=True)})
KIT =Obj({"name": Str(max_len=40), "items": WEIGHTED,
           "style": Str(max_len=30, optional=True)})  # the fighting style that suits it (the default)
# A class's (or a casting subclass's) spellcasting, every list by class level. `list`: whose spell list it draws on
# (the class's own by default; the Eldritch Knight's and Arcane Trickster's is the wizard's); `focus`: arcane or
# divine (by the type when left out); `changes` "level": the prepared list changes one spell a level, not after a
# long rest (the third casters); `given`: cantrips that come with it and are never swapped (the trickster's Mage Hand).
SPELLCASTING = Obj({"ability": Str(choices=list(ABILITY_IDS)), "type": Str(choices=["prepared", "spellbook", "known"]),
                    "cantrips": List(Int(min=0, max=10), min_items=10),
                    "slots": List(List(Int(min=0, max=10)), min_items=10),
                    # level 1+ spells prepared at each level (2024: the Prepared Spells column)
                    "prepared": List(Int(min=0, max=30), min_items=10, optional=True),
                    "list": Str(max_len=20, optional=True), "focus": Str(choices=["arcane", "divine"], optional=True),
                    "changes": Str(choices=["rest", "level"], optional=True),
                    "given": List(Str(max_len=40), optional=True)}, optional=True)
CLASS = Obj(
    {
        "name": Str(max_len=30), "description": Str(max_len=600), "hit_die": Int(min=4, max=12),
        "primary": List(Str(choices=list(ABILITY_IDS)), min_items=1), "saves": List(Str(choices=list(ABILITY_IDS)), min_items=2, max_items=2),
        "armor": List(Str(max_len=20)), "weapons": List(Str(max_len=30)), "tools": List(Str(max_len=40)),
        "skill_count": Int(min=0, max=6), "skill_choices": List(Str(max_len=30), min_items=1),
        "suggested": Obj({a: Int(min=8, max=15) for a in ABILITY_IDS}),
        "choices_at_1": List(Str(max_len=30)),
        # Weapon Mastery (2024): [[from level, how many kinds of weapon], ...]
        "mastery": List(List(Int(min=0, max=20), min_items=2, max_items=2), optional=True),
        "spellcasting": SPELLCASTING,
        "features": List(FEATURE, min_items=1),
        # A feature's choice (data "choose"): the options, each a feature of its own kept in Character.features.
        "options": Map(Obj({"name": Str(max_len=40), "text": Str(max_len=300), "gives": Any_(optional=True),
                            "cantrips": Int(min=1, max=3, optional=True)}), optional=True),
        "subclasses": Map(Obj({"name": Str(max_len=40), "text": Str(max_len=300), "features": List(FEATURE),
                               # always-prepared spells by class level (a domain's spells); ids may wait for the
                               # catalogue (Expansion 3 part D): only those in data/spells.json are prepared
                               "spells": Map(List(Str(max_len=40)), optional=True),
                               # a subclass that casts (Expansion 4 Part B: the Eldritch Knight, the Arcane
                               # Trickster): its own table by class level, from the level it is chosen
                               "spellcasting": SPELLCASTING,
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

# A poison (DMG 2024, p. 90-91; rules/poisons.py): how it gets in, the Constitution save, what a failure brings.
POISON = Obj({
    "kind": Str(choices=["contact", "ingested", "inhaled", "injury"]),
    "dc": Int(min=0, max=30),  # 0: no save (basic poison); a brewed dose keeps its brewer's DC in a "dc:<n>" tag
    "damage": Str(max_len=12, optional=True), "half": Bool(optional=True),  # (half on a success)
    "sure": Bool(optional=True),  # the damage is taken whatever the save (the Potion of Poison)
    "hours": Float(min=0, max=200, optional=True), "hours_dice": Str(max_len=8, optional=True),  # Poisoned this long
    "ends": Str(choices=["caster_turn_end"], optional=True),  # (Poisoner's brew: until the end of the brewer's next turn)
    "with": Str(choices=["paralyzed", "unconscious", "blinded"], optional=True),  # (while Poisoned in this way)
    "wakes": Bool(optional=True),  # the Unconscious ends when it takes damage
    "fail_by": Int(min=1, max=10, optional=True),  # `with` only on a failure by this much (Lolth's Sting)
    "repeat": Bool(optional=True),  # saved again at the end of each of its turns (Carrion Crawler Mucus)
    "fumes": Obj({"damage": Str(max_len=8), "successes": Int(min=1, max=10)}, optional=True),  # (Burnt Othur Fumes)
    "slow": Bool(optional=True),  # Speed halved while Poisoned (Torpor)
    "midnight": Bool(optional=True),  # nothing until the stroke of midnight (Midnight Tears)
    "daily": Obj({"damage": Str(max_len=8), "successes": Int(min=1, max=10), "no_heal": Bool(optional=True)},
                 optional=True),  # (Pale Tincture: a save every day)
    "truth": Bool(optional=True),  # cannot knowingly lie (Truth Serum)
    "from": List(Str(max_len=40), optional=True),  # the creatures (stat block ids) it is harvested from
}, strict=True, optional=True)

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
        "focus": Obj({"kind": Str(choices=["arcane", "divine", "druidic"]), "carried": Bool(optional=True)}, optional=True),
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
        # Expansion 2 part D: a pack opens into its contents; gear that helps a check; a tool's 2024 Utilize uses
        "pack": List(List(Any_(), min_items=2, max_items=2), min_items=1, optional=True),
        "helps": Obj({"search": Bool(optional=True), "traps": Int(min=1, max=10, optional=True),
                      "force": Int(min=1, max=10, optional=True), "disguise": Bool(optional=True)}, optional=True),
        "utilize": Obj({"ability": Str(choices=["str", "dex", "con", "int", "wis", "cha"]),
                        "uses": List(Obj({"text": Str(max_len=120), "dc": Int(min=5, max=30)}), min_items=1),
                        "crafts": List(Str(max_len=40), optional=True)}, optional=True),
        "trinket": Bool(optional=True),  # its name and words come from data/trinkets.json
        "tack": Str(choices=["riding", "exotic"], optional=True),  # a saddle (game/mounts.saddled)
        # Expansion 3 C.3: a magic consumable's rarity (potions of healing; spell scrolls are made with one)
        "rarity": Str(choices=["common", "uncommon", "rare", "very_rare", "legendary"], optional=True),
        "poison": POISON,
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
        "summon": Map(Any_(), optional=True),  # (a summoned creature: its numbers by the slot, rules/allies.py)
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
        # a Material component with a cost (2024): any of these items will do; consumed ones are used up by the casting
        "material": Obj({"items": List(Str(max_len=40), min_items=1), "consumed": Bool(optional=True),
                         # (a second thing needed beside it, kept: Legend Lore's ivory strips)
                         "also": List(Str(max_len=40), optional=True),
                         "text": Str(max_len=120)}, optional=True),
        "rounds": Int(min=0, max=100000, optional=True), "targets_up": Int(min=0, max=5, optional=True),
        "spheres": Int(min=2, max=8, optional=True),  # (Meteor Swarm: that many spheres, Battle._more_spheres)
        "target": Str(choices=["enemy", "ally", "creature", "self", "downed_ally", "dead_ally", "all_allies", "point",
                               "direction", "item", "place"]),
        # (place: where a travel spell goes, outside a fight: game/waymagic.py; creature: friend or foe, Polymorph)
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
        "resource": Obj({"id": Str(max_len=40), "max": Any_(),
                         "recover": Str(choices=["short", "short_one", "long", "dawn", "turn"])}, optional=True),
        "resources": List(Obj({"id": Str(max_len=40), "max": Any_(),
                               "recover": Str(choices=["short", "short_one", "long", "dawn", "turn"])}), optional=True),
        "where": Str(max_len=30, optional=True),
        "activate": Any_(optional=True),  # abilities it gives (rules/engine/actions.py; checked by rules/engine/check.py)
    }
)
TRAITS = Obj({"traits": Map(TRAIT_DEF, min_items=1)})

FEAT_CHOICE = Obj({"kind": Str(choices=["skill", "skill_or_tool", "tool", "spell_list", "cantrip", "spell", "ability",
                                         "increase", "damage_type", "skill_or_expertise", "expertise"]),
                   "from": Any_(optional=True), "count": Int(min=1, max=6, optional=True),
                   "level": Int(min=0, max=9, optional=True), "schools": List(Str(max_len=20), optional=True),
                   "ritual": Bool(optional=True), "untrained_save": Bool(optional=True),
                   "max": Int(min=20, max=30, optional=True), "any": Bool(optional=True)})
FEATS = Obj({"feats": Map(Obj({"name": Str(max_len=40), "category": Str(choices=["origin", "general", "fighting_style",
                                                                                   "epic"]),
                               "text": Str(max_len=500), "trait": Str(max_len=40, optional=True),
                               "repeatable": Bool(optional=True), "prerequisite": Any_(optional=True), "offered": Bool(optional=True),
                               "upgrade_in": Int(min=2, max=27, optional=True),
                               "choices": Map(FEAT_CHOICE, optional=True),
                               "gives": Obj({"armor": List(Str(max_len=20), optional=True),
                                             "weapons": List(Str(max_len=20), optional=True),
                                             "tools": List(Str(max_len=40), optional=True),
                                             "save": Str(max_len=20, optional=True)}, optional=True),
                               "spells": List(Str(max_len=40), optional=True)}), min_items=1),
             "suggest": Map(List(Str(max_len=40)), optional=True),
             "suggest_boon": Map(List(Str(max_len=40)), optional=True)})

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
        "crafts": Map(Obj({"name": Str(max_len=40), "needs": List(List(Any_(), min_items=2, max_items=2), min_items=0),
                           "gives": List(List(Any_(), min_items=2, max_items=2), min_items=1),
                           "minutes": Int(min=1, max=600), "skill": Str(max_len=20), "dc": Int(min=0, max=30),
                           "text": Str(max_len=200), "fire": Bool(optional=True),
                           "tool": Str(max_len=30, optional=True),
                           # Expansion 4 C.1: only for one who has this feat (the Poisoner's brew), its materials
                           # bought with coin (copper), as many as the maker's proficiency bonus, no check (dc 0)
                           "feat": Str(max_len=30, optional=True), "coin": Int(min=0, max=10**6, optional=True),
                           "by_proficiency": Bool(optional=True)})),
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
        "picture": Str(max_len=60, optional=True),  # a vignette's backdrop (ui/gfx/vignette.BACKDROPS)
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
            # [item, fewest, most] or [item, fewest, most, the smallest settlement kind that stocks it]
            "stock": List(List(Any_(), min_items=3, max_items=4), min_items=1), "markup": Float(min=0.1, max=5)})
GRADES = ["wretched", "squalid", "poor", "modest", "comfortable", "wealthy", "aristocratic"]  # PHB 2024 lifestyles
INN = Obj({"stay": Map(Int(min=0)), "meal": Map(Int(min=0)), "lifestyle": Map(Int(min=0)),
           "grades": Map(List(Str(choices=GRADES), min_items=1)), "theft": Map(Float(min=0, max=1)),
           "rest": Map(Int(min=0, max=3)), "seen": Map(Int(min=0, max=10)),
           "fill": Map(List(Int(min=0, max=100), min_items=2, max_items=2)), "sick": Map(Float(min=0, max=1))})
PASSAGE = Obj({"per_mile": Int(min=0), "mph": Float(min=0.5, max=20), "hours_a_day": Int(min=1, max=24),
               "max_miles": Int(min=1, max=5000)})
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
                            "ride": Float(min=0.1, max=2), "days_without_food": Int(min=1, max=30),
                            # Expansion 2 part D: only Small riders (a mastiff); a land where it goes better or worse
                            # than ride_lands says (a camel in the dunes); the saddle it needs; what it eats
                            "small_only": Bool(optional=True), "lands": Map(Float(min=0, max=1), optional=True),
                            "saddle": Str(max_len=40, optional=True), "eats": Str(choices=["fodder", "meat"], optional=True),
                            # Expansion 3 F.1: a steed of another world (Find Steed), never sold
                            "summoned": Bool(optional=True)}),
                       min_items=1),
        "vehicles": Map(Obj({"name": Str(max_len=40), "price": Int(min=0, max=10**7), "weight": Int(min=0, max=5000),
                             "rough": Float(min=1, max=5), "ride": Float(min=0.1, max=2), "seats": Int(min=0, max=8),
                             "snow": List(Str(max_len=30), optional=True)}), optional=True),
        "grazing": List(Str(max_len=30)),
        "ride_lands": Map(Float(min=0, max=1), optional=True),
        "services": Obj({"bath": Int(min=0),
                         "size_factor": Map(Float(min=0.1, max=10)), "treat_per_wound": Map(Int(min=0)),
                         "surgery": Int(min=0), "herbal_cure": Int(min=0), "prayer_healing": Int(min=0),
                         "cure_disease": Int(min=0), "repair_share": Float(min=0, max=2),
                         "labour_pay": List(Int(min=0), min_items=2, max_items=2),
                         # Expansion 2 part D (PHB 2024 p. 234): lifestyles, tolls, coaches, ships, messengers
                         "inn": INN, "toll": Int(min=0), "coach": PASSAGE, "ship": PASSAGE,
                         "messenger": Obj({"per_mile": Int(min=0), "miles_a_day": Int(min=1, max=200)}),
                         "stabling": Int(min=0), "feed": Int(min=0),
                         # Expansion 3 G.2 (PHB 2024 p. 232): spellcasting for pay
                         "spellcasting": Obj({"price": List(Int(min=0), min_items=10, max_items=10),
                                              "reach": Map(Int(min=0, max=9)),
                                              "own": Map(List(Int(min=0, max=9), min_items=2, max_items=2)),
                                              "secret_markup": Float(min=1, max=5),
                                              "min_hours": Float(min=0, max=24)})}),
        "culture_stock": Map(List(List(Any_(), min_items=3, max_items=4)), optional=True),
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
        # (Planar Ally, Expansion 3 F.5: the spirit this god sends, a summoned creature and its form)
        "ally": Obj({"creature": Str(max_len=40), "form": Str(max_len=30)}, optional=True),
        # (Expansion 5 Part B: the cleric domains its priests serve, and so its miracles: game/gods.py)
        "domains": List(Str(choices=["life", "light", "trickery", "war"]), min_items=1, optional=True),
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
        # Expansion 4 Part C (game/shadows.py): where poison is sold openly, who duels, the black market's prices
        "shadows": Obj({"poison_allowed": List(Str(max_len=30)), "duels": List(Str(max_len=30))}, optional=True),
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
                               "attune": Bool(optional=True), "title": Str(max_len=60, optional=True),
                               "secretly": Str(max_len=40, optional=True),  # what it really is (rules/poisons.mask)
                               "form": Str(max_len=20, optional=True),  # its shape at first (the Veteran's Cane)
                               "curse": Map(Any_(), optional=True),  # the book's own curse (the Sword of Vengeance)
                               "bases": List(Str(max_len=40), optional=True),  # what it may be made on
                               "attune_by": Any_(optional=True),  # "spellcaster" or [classes] (Expansion 5 Part D)
                               "enspell": Any_(optional=True),  # a spell bound in by its level (the Enspelled Staff; a list of
                               # schools: Enspelled Armor and Weapon, Expansion 5 Part E)
                               "qty": List(Int(min=1, max=100), min_items=2, max_items=2, optional=True)}))),
        "reroll": Int(min=0, max=50),
        "enspell": Map(List(Int(min=0, max=30), min_items=2, max_items=2), optional=True),  # [DC, attack] by level
        "patches": Obj({"always": word_list(1, 20), "table": List(List(Any_(), min_items=3, max_items=3), min_items=1)},
                       optional=True),  # the Robe of Useful Items (game/wonders.py)
        "magic_scale": List(Float(min=0, max=5), min_items=3, max_items=3),
        "tables": Map(List(List(Any_(), min_items=4, max_items=4), min_items=1), min_items=20),
    }
)
DATA_FILES.update({"treasure.json": TREASURE})

# ---------------------------------------------------------------------------- quests (M8)
QUEST_TEMPLATES = ("bounty", "clear_lair", "hunt_beast", "deliver", "retrieve", "rescue", "collect_debt",
                   "investigate", "slay_dragon", "escort", "assassinate", "cure", "feud", "steal", "defend",
                   "smuggle", "apprenticeship")
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
                         "clue": List(Str(max_len=400), min_items=1, optional=True),
                         "nameless": List(Str(max_len=60), min_items=1, optional=True)})),  # (apprenticeship: a lost wizard)
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
        "animate_ground": Int(min=1, max=8, optional=True),  # the ground's frames (embers: Expansion 6 B.7)
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

# Trinkets (Expansion 2 part D): keepsakes found in pockets and chests and given to every new character (one item,
# "trinket" in items.json; its name and words come from here, kept on the item: rules/items.make_trinket).
TRINKETS = Obj({"chance": Obj({"pocket": Float(min=0, max=1), "chest": Float(min=0, max=1)}),
                "trinkets": List(Obj({"id": Str(max_len=40), "name": Str(max_len=40), "text": Str(max_len=160)}),
                                 min_items=20)})
DATA_FILES.update({"trinkets.json": TRINKETS})

# ---------------------------------------------------------------------------- Adventures & Events (Expansion 6)
# The story engine's data (docs/ADVENTURES.md §8.2), all in data/packs/06_adventures_events/. The schemas check the
# shapes; what the entries name (step kinds, selectors, conditions, ops, finale keys) is checked against the code by
# realmwalker/game/story/check.py at start-up, as rules/engine/check.py does for the kernel.
TIER_BAND = List(Int(min=1, max=4), min_items=2, max_items=2)
DAY_BAND = List(Int(min=0, max=3650), min_items=2, max_items=2)


def ops_list(optional: bool = False) -> List:
    """[["op", arg, ...], ...]: what a stage, a beat or an ending does (each op checked by story/check.py)."""
    return List(List(Any_(), min_items=1), optional=optional)


THREAT_SOURCES = ("lairs", "tombs", "gangs", "cults", "towers", "tribes", "dragons", "crowns", "grudges", "artifacts",
                  "plagues")
THREAT_STAGE = Obj({
    "id": Str(max_len=30),
    "days": DAY_BAND,  # how long the stage lasts at tier 1 (threats.json stage_days stretches it for the tiers above)
    "signs": word_list(1, 300),  # news when it begins ({villain}, {home}, {place}, {area})
    "flavour": List(Str(max_len=300), optional=True),  # words on the land, behind Text detail
    "effects": ops_list(optional=True),  # world/threats.STAGE_OPS
    "doom": Bool(optional=True),
})
THREAT_KIND = Obj({
    "name": Str(max_len=40),
    "from": Str(choices=list(THREAT_SOURCES)),
    "tiers": TIER_BAND,
    # (a kind may live in the world before its tales are written: its threats still move, and end without the hero)
    "tempers": List(Str(max_len=30)),
    "blueprints": List(Str(max_len=40)),
    "reach": Int(min=1, max=60),  # tiles round its home that its signs and effects touch
    "stages": List(THREAT_STAGE, min_items=3, max_items=7),
    "hooks": word_list(3, 300),  # a notice board's line or a patron's plea ({villain}, {home}, {town}, {where})
})
THREATS = Obj({
    "budget": Map(List(Int(min=0, max=40), min_items=2, max_items=2), optional=True),  # active threats by world size
    "near_hero": Obj({"tiles": Int(min=5, max=200), "untaken": Int(min=0, max=10)}, optional=True),
    "start": Obj({"tiles": Int(min=5, max=200), "tier_one": Int(min=0, max=10)}, optional=True),
    "stage_days": Map(DAY_BAND, optional=True),  # by tier
    "sign_lead_days": Int(min=0, max=60, optional=True),
    "target_level": Map(Int(min=1, max=20), optional=True),  # by tier: the level a finale is measured for
    "tier_by_danger": List(List(Int(min=0, max=10), min_items=2, max_items=2), optional=True),  # [least danger, tier]
    "wake": Float(min=0, max=1, optional=True),  # a dormant threat's weekly chance to stir by itself
    "emptied": Obj({"floor": Float(min=0.05, max=1), "rebuild_days": Int(min=7, max=3650)}, optional=True),
    "hunters": Obj({"chance": Float(min=0, max=1), "per_fame": Float(min=0, max=1)}, optional=True),
    "interlude_stages": Int(min=0, max=5, optional=True),
    "kinds": Map(THREAT_KIND),
})

CHOICE = Obj({
    "label": word_list(1, 160),
    "requires": Map(Any_(), optional=True),
    "check": Obj({"skill": Str(max_len=30), "dc": Int(min=1, max=30)}, optional=True),
    "ops": ops_list(optional=True),
    "success": ops_list(optional=True),
    "failure": ops_list(optional=True),
    "result": List(Str(max_len=600), optional=True),
    "fail_result": List(Str(max_len=600), optional=True),
})
BEAT = Obj({
    "family": Str(max_len=30),
    "where": List(Str(max_len=30), optional=True),
    "time": Any_(optional=True),  # dawn, day, dusk, night: one, or a list
    "when": Map(Any_(), optional=True),  # conditions (story/beats.CONDITIONS)
    "weight": Int(min=0, max=100, optional=True),
    "title": List(Str(max_len=80), optional=True),
    "picture": Str(max_len=60, optional=True),
    "leaves": Str(max_len=30, optional=True),  # what it leaves at your camp, in the camp's picture (story.LEFT)
    "text": List(word_list(1, 600), min_items=1),  # pages, each a list of variants
    "choices": List(CHOICE, optional=True),
    "ops": ops_list(optional=True),  # what it does when it has no choices
})
BEATS = Obj({"beats": Map(BEAT)})

STEP = Obj({"kind": Str(max_len=20)}, strict=False)  # its other keys are its kind's own (story/steps.py fields)
CHAPTER = Obj({
    "id": Str(max_len=30),
    "need": Any_(),  # "all", or how many of its steps
    "title": word_list(2, 80),
    "goal": word_list(1, 200),  # the journal's one line
    "opening": word_list(3, 600),
    "reveal": word_list(3, 600),
    "steps": List(STEP, min_items=1),
    "set_piece": Str(max_len=30, optional=True),
    "tier_min": Int(min=1, max=4, optional=True),
})
ENDING = Obj({
    "id": Str(max_len=30),
    "if": List(Str(max_len=60), optional=True),
    "ops": ops_list(),
    "pages": Map(word_list(1, 600), optional=True),  # the epilogue's pages of this ending, by whom they tell of
    "from_part": Str(max_len=2, optional=True),
})
CAST_ROLE = Obj({"pick": List(Str(max_len=200), min_items=1), "count": List(Int(min=0, max=4), optional=True),
                 "chance": Float(min=0, max=1, optional=True), "as": Str(max_len=30, optional=True),
                 "from_part": Str(max_len=2, optional=True)})
BLUEPRINT = Obj({
    "name": Str(max_len=60),
    "tiers": TIER_BAND,
    "from": List(Str(max_len=30), min_items=1),  # threat kinds
    "flavours": List(Str(max_len=30), optional=True),
    "needs": Map(Any_(), optional=True),
    "title": word_list(3, 80),
    "hook": word_list(3, 600),
    "premise": word_list(1, 600),
    "places": Map(Str(max_len=300), min_items=1),  # selectors (story/selectors.py)
    "cast": Map(CAST_ROLE),
    "hidden": Map(Str(max_len=300), optional=True),
    "chapters": List(CHAPTER, min_items=2, max_items=6),
    "finale": Obj({"boss": Str(max_len=60), "template": Str(max_len=40), "at": Str(max_len=80),
                   "with": List(Str(max_len=60), optional=True), "keys": Map(List(Str(max_len=60)), optional=True),
                   "words": Map(word_list(1, 600), optional=True)}),
    "endings": List(ENDING, min_items=2),
    "epithets": List(Str(max_len=40), optional=True),  # tags of the epithets its epilogue offers
})
ADVENTURES = Obj({
    "max_active": Int(min=1, max=10, optional=True),
    "words": Map(word_list(1, 400), optional=True),  # nested tables for the story's text (story/words.py)
    "epithets": Map(word_list(3, 40), optional=True),  # by tag
    "blueprints": Map(BLUEPRINT),
})

BOSS = Obj({
    "tiers": TIER_BAND,
    "roles": List(Str(max_len=30), min_items=1),  # what it makes a boss of (a beast, a dead king, a captain...)
    "hp": Float(min=1, max=10),  # times the creature's hit points
    "resistances": Int(min=0, max=5),  # Legendary Resistances a day
    "actions": Int(min=0, max=5),  # legendary actions a round
    "menu": List(Str(max_len=30), min_items=1),  # what those actions may be (story/finale.LEGENDARY)
    "phase": Obj({"at": Float(min=0.05, max=0.95), "kind": Str(max_len=30), "lines": word_list(3, 300)},
                 optional=True),
    # met before its finale it fights as itself, and does this when it falls to `at` of its hit points (breaks off)
    "before": Obj({"at": Float(min=0.05, max=0.95), "kind": Str(max_len=30), "lines": word_list(3, 300)},
                  optional=True),
})
TEMPER = Obj({
    "speaks": Bool(),
    "moves": Map(Int(min=0, max=100), min_items=1),  # move id: weight
    "first_words": word_list(6, 300),
    "omens": word_list(8, 300),
})
WEAKNESS = Obj({"id": Str(max_len=30), "name": Str(max_len=60), "keys": List(Str(max_len=60)),
                "for": List(Str(max_len=40), optional=True), "lore": word_list(3, 400),
                "means": List(Str(max_len=40), optional=True)})
VILLAINS = Obj({
    "attention": Obj({"step": Int(min=0, max=5), "lieutenant": Int(min=0, max=5), "fortnight": Int(min=-5, max=0),
                      "max": Int(min=1, max=20), "moves_apart_days": Int(min=0, max=30),
                      "per_chapter": Int(min=0, max=10)}, optional=True),
    "tempers": Map(TEMPER),
    "moves": Map(Obj({"beat": Str(max_len=60), "attention": List(Int(min=0, max=20), min_items=2, max_items=2)})),
    "bosses": Map(BOSS),
    "weaknesses": Map(List(WEAKNESS, min_items=1)),  # by what the villain is (a creature type, or a creature id)
})
CUE = Obj({"cue": Str(max_len=20)}, strict=False)  # its other keys are its cue's own (story/stage.py CUES)
SCENE = Obj({
    "about": Str(max_len=300, optional=True),
    "cues": List(CUE, min_items=1),
    "words": Map(word_list(1, 300), optional=True),  # lines for its cues' `key`
    "cast": List(Str(max_len=30), optional=True),  # roles cast by whoever starts it (a situation's people)
    "given": List(Str(max_len=30), optional=True),  # words given by whoever starts it (a situation's plea)
})
SCENES = Obj({"scenes": Map(SCENE)})
DAY_SPAN = List(Int(min=0, max=3650), min_items=2, max_items=2)
MARK = Obj({
    "form": Str(choices=["day", "name", "record"]),
    "label": Str(max_len=40),
    "colour": Str(max_len=20),
    "ages": Obj({"into": Any_(), "after": DAY_SPAN}, optional=True),  # into: the next mark, or null
    "lasts": List(Int(min=0, max=3650), min_items=2, max_items=2, optional=True),  # a record's days with no until
    "troubles": word_list(3, 300),  # walking in ({town}, {by}, {by_part})
    "moments": word_list(3, 300),  # a thing seen in its streets
    "description": word_list(1, 300),  # a line for a town's first description
    "dress": Obj({"share": Float(min=0, max=1, optional=True)}, strict=False, optional=True),  # (game/placemarks.py)
})
FIRE = Obj({  # live fire on a town's map (game/fire.py)
    "burns": Map(List(Float(min=0, max=100), min_items=2, max_items=2)),
    "into": Map(Str(max_len=40)),
    "beams": Float(min=0, max=1),
    "shell": Float(min=0, max=1),
    "kindle": List(Int(min=0, max=20), min_items=2, max_items=2),
    "cries": word_list(3, 120),
}, optional=True)
MARKS = Obj({"marks": Map(MARK), "fire": FIRE})
WORK = Obj({  # work that waits to be taken (game/story/work.py; the kinds are data/quests.json templates)
    "commissions": Obj({
        "renew": DAY_SPAN,
        "reach": Int(min=1, max=200),
        "goals": Map(Obj({"match": word_list(1, 80), "kinds": word_list(1, 30)})),
        "by_kind": Map(word_list(1, 30)),
        "choice": word_list(2, 120),  # ({faction})
        "word": word_list(2, 200),  # ({faction}, {giver}, {title}, {town})
    }, optional=True),
    "pleas": List(Obj({"kind": Str(max_len=30), "jobs": List(Str(max_len=30)),
                       "need": Str(choices=["always", "sickness", "dragon", "grudge"]),
                       "choice": word_list(2, 120)}), min_items=1, optional=True),
    "plea_gap": Int(min=1, max=365, optional=True),
    "contracts": Obj({  # paid work: one a town, two in a city (C.3)
        "renew": DAY_SPAN,
        "near": Int(min=1, max=40),  # how far from the road a danger may be
        "kinds": Map(Obj({"kind": Str(choices=["escort", "deliver", "defend"]),
                          "from": Str(choices=["trade", "faith", "raiders"]),
                          "to": Str(choices=["market", "holy"], optional=True),
                          "text": Str(max_len=40, optional=True),  # a quests.json text variant
                          "givers": word_list(1, 30),
                          "travellers": List(Str(max_len=30), min_items=1, optional=True),
                          "recipients": List(Str(max_len=30), min_items=1, optional=True),
                          "choice": word_list(2, 120)})),  # ({dest}, {raiders})
        "danger": Obj({k: word_list(2, 120) for k in ("threat", "lair", "gang", "wild")}),  # ({name}, {site}, {area})
        "met": Obj({k: word_list(2, 200) for k in ("threat", "lair", "gang", "wild")}),  # (+ {town}, {giver})
        "terms": Str(max_len=300),
    }, optional=True),
}, optional=True)
_LIFE_PICK = Obj({"words": word_list(1, 160), "jobs": List(Str(max_len=30), optional=True),
                  "traits": List(Str(max_len=30), optional=True), "needs": Str(max_len=20, optional=True),
                  "not": Str(max_len=20, optional=True), "social": List(Str(choices=["low", "middle", "high"]), optional=True),
                  "forced": Bool(optional=True), "short": Str(max_len=40, optional=True)})
LIVES = Obj({  # townsfolk's lives (game/story/lives.py, C.4)
    "others": Int(min=0, max=60), "reach": Int(min=1, max=200), "per_town": Int(min=0, max=20), "every": Int(min=1, max=60),
    "kin": Obj({"spouse": Float(min=0, max=1), "children": List(Int(min=0, max=9), min_items=2, max_items=2),
                "parent": Float(min=0, max=1), "sibling": Float(min=0, max=1)}),
    "ties": Map(Float(min=0, max=1)),
    "wants": Map(_LIFE_PICK), "fears": Map(_LIFE_PICK), "secrets": Map(_LIFE_PICK),
    "secret_chance": Float(min=0, max=1), "things": Map(_LIFE_PICK),
    "events": Map(Obj({"chance": Float(min=0, max=1), "seed": Float(min=0, max=1), "days": DAY_SPAN,
                       "note": word_list(2, 160), "bark": word_list(2, 90),
                       "sign": List(Str(max_len=90), min_items=2, optional=True),
                       "murmur": List(Str(max_len=90), min_items=3, optional=True)})),
}, optional=True)
DATA_FILES.update({"lives.json": LIVES})
PACK_ONLY.update({"lives.json": {}})
_SIT_ACT = Obj({"id": Str(max_len=40), "who": Str(max_len=30, optional=True), "label": word_list(1, 160),
                "check": List(Any_(), min_items=2, max_items=2, optional=True), "price": Int(min=0, max=100000, optional=True),
                "way": Str(max_len=20, optional=True), "needs": List(Str(max_len=60), optional=True),
                "unless": List(Str(max_len=60), optional=True), "then": List(List(Any_(), min_items=1), optional=True),
                "fail": List(List(Any_(), min_items=1), optional=True), "say": List(Str(max_len=300), optional=True), "fail_say": List(Str(max_len=300), optional=True),
                "note": List(Str(max_len=300), optional=True), "pass": Bool(optional=True), "retry": Bool(optional=True)})
_SIT_OBSTACLE = Obj({"id": Str(max_len=40), "kind": Str(max_len=30), "who": Str(max_len=30, optional=True),
                     "note": word_list(1, 300), "acts": List(_SIT_ACT, optional=True), "chance": Float(min=0, max=1, optional=True),
                     "spells": List(Str(max_len=40), optional=True), "by_magic": List(List(Any_(), min_items=1), optional=True),
                     "magic_note": List(Str(max_len=300), optional=True)})
_SIT_ENDING = Obj({"id": Str(max_len=40), "when": Str(max_len=40, optional=True), "if": List(Str(max_len=60), optional=True),
                   "tone": Str(choices=["good", "mixed", "bitter"]), "ops": List(List(Any_(), min_items=1)),
                   "line": word_list(1, 300)})
SITUATIONS = Obj({  # situations (game/story/situations.py, C.6)
    "rarity": Obj({"gap": DAY_SPAN, "first": DAY_SPAN, "per_town": Int(min=0, max=5), "per_great": Int(min=0, max=5),
                   "near": Int(min=0, max=12), "turn_chance": Float(min=0, max=1)}, optional=True),
    "roots": Map(List(Str(max_len=40), min_items=1), optional=True),
    "talk": Map(word_list(2, 160), optional=True),  # ask, take, refuse, thanks, refused (a predicament may have its own)
    "meetings": Map(Obj({"scene": Str(max_len=40), "cast": Map(Str(max_len=30), min_items=1), "letter": Bool(optional=True)}),
                    optional=True),
    "turns": Map(Obj({"when": Str(max_len=10), "for": List(Str(max_len=40), min_items=1),
                      "needs": List(Str(max_len=30), optional=True), "threat": Bool(optional=True),
                      "ops": List(List(Any_(), min_items=1), optional=True), "obstacle": Obj({"id": Str(max_len=40), "kind": Str(max_len=30)}, strict=False, optional=True), "line": word_list(1, 300)}), optional=True),
    "predicaments": Map(Obj({
        "name": Str(max_len=80), "asks": Str(max_len=30, optional=True),
        "roles": Map(Obj({"bind": Str(max_len=20)}, strict=False), min_items=1),
        "parts": Map(Str(max_len=30), optional=True), "base": Str(max_len=40, optional=True),
        "forge": List(List(Any_(), min_items=1), optional=True),
        "obstacles": List(_SIT_OBSTACLE, optional=True), "acts": List(_SIT_ACT, optional=True),
        "work": Obj({"kind": Str(max_len=30)}, strict=False, optional=True),
        "goals": List(Obj({"id": Str(max_len=40), "test": List(Any_(), min_items=1),
                           "then": List(List(Any_(), min_items=1), optional=True)}), min_items=1),
        "endings": List(_SIT_ENDING, min_items=1),
        "lapse": Obj({"tone": Str(choices=["good", "mixed", "bitter"]), "ops": List(List(Any_(), min_items=1)),
                      "line": word_list(1, 300)}),
        "clock": DAY_SPAN, "meetings": List(Str(max_len=30), min_items=1),
        "words": Obj({"title": word_list(1, 120), "stakes": word_list(1, 200), "plea": word_list(1, 400),
                      "first": word_list(1, 300)}, strict=False),
    })),
}, optional=True)
DATA_FILES.update({"situations.json": SITUATIONS})
PACK_ONLY.update({"situations.json": {}})
DATA_FILES.update({"threats.json": THREATS, "adventures.json": ADVENTURES, "villains.json": VILLAINS,
                   "beats.json": BEATS, "scenes.json": SCENES, "marks.json": MARKS, "work.json": WORK})
PACK_ONLY.update({"threats.json": {"kinds": {}}, "adventures.json": {"blueprints": {}},
                  "villains.json": {"tempers": {}, "moves": {}, "bosses": {}, "weaknesses": {}},
                  "beats.json": {"beats": {}}, "scenes.json": {"scenes": {}}, "marks.json": {"marks": {}}, "work.json": {}})
