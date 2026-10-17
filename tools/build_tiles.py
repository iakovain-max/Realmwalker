"""Builds the game's tile sheets (assets/tiles) from the Dungeon Crawl Stone Soup tile pack and tools/tile_art.py.

The Dungeon Crawl 32x32 tiles are public domain (CC0): https://opengameart.org/content/dungeon-crawl-32x32-tiles
Only the tiles listed here are taken; each gets a plain name ("creature/wolf", "item/longsword", "doll/body/chainmail")
and is toned to the game's grim palette. The result is a few sheet images and tiles.json, which the game loads.

    python tools/build_tiles.py                 (downloads the pack into build/tiles_src the first time)
    python tools/build_tiles.py --pack DIR      (use an unpacked copy: the folder holding dungeon/, monster/, ...)
    python tools/build_tiles.py --preview out.png  (also writes a contact sheet of everything)

Not run by the game: the finished sheets are kept in the repository.
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import adapt_art  # noqa: E402
import map_art  # noqa: E402
import nature_art  # noqa: E402
import tile_art  # noqa: E402
import gear_art  # noqa: E402
import beast_art  # noqa: E402
import town_art  # noqa: E402

PACK_URL = "https://opengameart.org/sites/default/files/Dungeon%20Crawl%20Stone%20Soup%20Full.zip"
OUT = ROOT / "assets" / "tiles"
SHEET = 2048

# How each family is toned: (saturation, brightness, warmth). The pack is bright and cheerful; the game is not.
GRADES = {
    "ground": (0.70, 0.86, 0.04),
    "water": (0.62, 0.80, -0.02),
    "wall": (0.66, 0.86, 0.03),
    "feature": (0.75, 0.88, 0.03),
    "tree": (0.70, 0.80, 0.02),
    "creature": (0.82, 0.94, 0.02),
    "doll": (0.80, 0.95, 0.02),
    "item": (0.88, 1.00, 0.0),
    "fx": (1.0, 1.0, 0.0),
    "none": (1.0, 1.0, 0.0),
}

# ---------------------------------------------------------------------------- what is taken from the pack
# name -> (path in the pack, grade, optional recolour {"hue": 0-255 target, "sat": x, "val": x})
PICKS: dict[str, tuple] = {}


def pick(name: str, path: str, grade: str, **recolor) -> None:
    PICKS[name] = (path, grade, recolor)


def pick_many(prefix: str, pattern: str, grade: str, limit: int | None = None) -> None:
    """Every file matching `pattern` (sorted), as prefix_0, prefix_1..."""
    PICKS[f"{prefix}*"] = (pattern, grade, {"limit": limit})


# Ground
pick_many("floor/grass", "dungeon/floor/grass/grass_[0-2]_new.png", "ground")
pick_many("floor/grass_old", "dungeon/floor/grass/grass_[0-2]_old.png", "ground")
pick_many("floor/grass_flowers", "dungeon/floor/grass/grass_flowers_*_new.png", "ground")
pick_many("floor/dirt", "dungeon/floor/dirt_[0-2]_new.png", "ground")
pick_many("floor/dirt_old", "dungeon/floor/dirt_[0-2]_old.png", "ground")
pick_many("floor/mud", "dungeon/floor/mud_[0-3].png", "ground")
pick_many("floor/sand", "dungeon/floor/sand_[1-8].png", "ground")
pick_many("floor/pebble", "dungeon/floor/pebble_brown_[0-8]_new.png", "ground")
pick_many("floor/greydirt", "dungeon/floor/grey_dirt_[0-7]_new.png", "ground")
pick_many("floor/flagstone", "dungeon/floor/rect_gray_[0-3]_new.png", "ground")
pick_many("floor/limestone", "dungeon/floor/limestone_[0-9].png", "ground")
pick_many("floor/crypt", "dungeon/floor/tomb_[0-3]_new.png", "ground")
pick_many("floor/ice", "dungeon/floor/ice_[0-3]_new.png", "ground")
pick_many("floor/lair", "dungeon/floor/lair_[0-3]_new.png", "ground")
pick_many("floor/swamp", "dungeon/floor/swamp_[0-3]_new.png", "ground")
pick_many("floor/moss", "dungeon/floor/moss_[0-3].png", "ground")
pick_many("floor/marble", "dungeon/floor/marble_floor_[1-6].png", "ground")
pick_many("floor/sandstone", "dungeon/floor/sandstone_floor_[0-9].png", "ground")
pick_many("floor/cobble", "dungeon/floor/floor_sand_stone_[0-7].png", "ground")
pick_many("floor/rough", "dungeon/floor/floor_sand_rock_[0-3].png", "ground")
pick_many("floor/redrock", "dungeon/floor/rough_red_[0-3].png", "ground")
pick_many("floor/volcanic", "dungeon/floor/volcanic_floor_[0-6].png", "ground")
pick_many("floor/lava", "dungeon/floor/lava_[0-3].png", "fx")
pick_many("floor/frozen", "dungeon/floor/frozen_[0-9].png", "ground")
pick_many("floor/crystal", "dungeon/floor/crystal_floor_[0-5].png", "ground")
# Water
pick_many("water/shallow", "dungeon/water/shallow_water*.png", "water", 2)
pick_many("water/shoals", "dungeon/water/shoals_shallow_water_[0-9].png", "water")
pick_many("water/deep", "dungeon/water/deep_water.png", "water")
pick("water/deep_1", "dungeon/water/deep_water_2.png", "water")
pick_many("water/deep_shoals", "dungeon/water/shoals_deep_water_[5-9].png", "water")
pick("water/murky_0", "dungeon/water/shallow_water_murky.png", "water")
pick("water/murky_1", "dungeon/water/shallow_water_murky_2.png", "water")
# Walls
pick_many("wall/stone", "dungeon/wall/stone_brick_*.png", "wall")
pick_many("wall/brick_gray", "dungeon/wall/brick_gray_[0-3].png", "wall")
pick_many("wall/brick_brown", "dungeon/wall/brick_brown_[0-7].png", "wall")
pick_many("wall/brick_dark", "dungeon/wall/brick_dark_[0-6].png", "wall")
pick_many("wall/catacombs", "dungeon/wall/catacombs_[0-9].png", "wall")
pick_many("wall/rock", "dungeon/wall/stone_dark_[0-3].png", "wall")
pick_many("wall/cave", "dungeon/wall/lab-rock_[0-3].png", "wall")
pick_many("wall/stone_gray", "dungeon/wall/stone_gray_[0-3].png", "wall")
pick_many("wall/vines", "dungeon/wall/brick_brown-vines_[1-4].png", "wall")
pick_many("wall/relief", "dungeon/wall/relief_[0-3].png", "wall")
pick_many("wall/sandstone", "dungeon/wall/sandstone_wall_[0-9].png", "wall")
pick_many("wall/marble", "dungeon/wall/marble_wall_[0-9]*.png", "wall", 6)
pick_many("wall/torch", "dungeon/wall/torches/torch_[0-4].png", "feature")
pick("wall/banner", "dungeon/wall/banners/banner_1.png", "feature")
# Features
pick("feature/door_closed", "dungeon/doors/closed_door.png", "feature")
pick("feature/door_open", "dungeon/doors/open_door.png", "feature")
pick("feature/door_locked", "dungeon/doors/runed_door.png", "feature")
pick("feature/door_secret", "dungeon/doors/detected_secret_door.png", "feature")
pick("feature/gate_open", "dungeon/doors/gate_open_middle.png", "feature")
pick("feature/gate_closed", "dungeon/doors/gate_closed_middle.png", "feature")
pick("feature/stairs_down", "dungeon/gateways/stone_stairs_down.png", "feature")
pick("feature/stairs_up", "dungeon/gateways/stone_stairs_up.png", "feature")
pick("feature/cave_down", "dungeon/gateways/rock_stairs_down.png", "feature")
pick("feature/cave_up", "dungeon/gateways/rock_stairs_up.png", "feature")
pick("feature/altar", "dungeon/altars/altar_base.png", "feature")
pick("feature/altar_holy", "dungeon/altars/altar_shining_one.png", "feature")
pick("feature/altar_dark", "dungeon/altars/altar_yredelemnul.png", "feature")
pick("feature/chest", "dungeon/chest_2_closed.png", "feature")
pick("feature/chest_open", "dungeon/chest_2_open.png", "feature")
pick("feature/box", "dungeon/large_box.png", "feature")
pick("feature/sarcophagus", "dungeon/vaults/sarcophagus_sealed.png", "feature")
pick("feature/sarcophagus_open", "dungeon/sarcophagus_open.png", "feature")
pick("feature/boulder", "dungeon/boulder.png", "feature")
pick("feature/fountain_0", "dungeon/blue_fountain.png", "feature")
pick("feature/fountain_1", "dungeon/blue_fountain_2.png", "feature")
pick("feature/fountain_dry", "dungeon/dry_fountain.png", "feature")
pick_many("feature/column", "dungeon/statues/crumbled_column*.png", "feature")
pick("feature/statue", "dungeon/statues/granite_statue.png", "feature")
pick("feature/statue_hero", "dungeon/statues/statue_ancient_hero.png", "feature")
pick("feature/pedestal", "dungeon/statues/pedestal.png", "feature")
pick("feature/hoard", "item/gold/gold_pile_25.png", "item")
pick("trap/pit", "dungeon/traps/trap_shaft.png", "feature")
pick("trap/darts", "dungeon/traps/trap_dart.png", "feature")
pick("trap/blade", "dungeon/traps/trap_blade.png", "feature")
pick("trap/fire", "dungeon/traps/trap_magical.png", "feature")
pick("trap/plate", "dungeon/traps/pressure_plate.png", "feature")
# Trees and plants
pick_many("tree/autumn", "dungeon/trees/tree_*.png", "tree")
pick_many("tree/mangrove", "dungeon/trees/mangrove_*.png", "tree")
pick_many("plant/bush", "monster/fungi_plants/bush_[2-4].png", "tree")
pick("plant/shrub", "monster/fungi_plants/plant.png", "tree")
pick("plant/briar", "monster/fungi_plants/briar_patch.png", "tree")
pick("plant/mushroom", "monster/fungi_plants/deathcap.png", "tree")

# Creatures (those drawn from the pack; people are dressed dolls, see data/sprites.json)
CREATURES = {
    "elephant": "monster/animals/elephant_new.png",
    "mastiff": "monster/animals/war_dog.png",
    "wolf": "monster/animals/wolf.png",
    "dire_wolf": "monster/animals/warg.png",
    "wild_dog": "monster/animals/jackal_new.png",
    "black_bear": "monster/animals/black_bear_new.png",
    "brown_bear": "monster/animals/grizzly_bear.png",
    "giant_rat": "monster/animals/rat.png",
    "giant_spider": "monster/animals/wolf_spider_new.png",
    "skeleton": "monster/undead/skeletons/skeleton_humanoid_small_new.png",
    "zombie": "monster/undead/zombies/zombie_small.png",
    "ghoul": "monster/undead/ghoul.png",
    "gnoll": "monster/gnoll_new.png",
    "hobgoblin": "monster/hobgoblin_new.png",
    "stirge": "monster/animals/giant_mosquito.png",
    "goblin": "monster/goblin_new.png",
    "goblin_boss": "monster/goblin_old.png",
    "orc": "monster/orc_new.png",
    "orc_warchief": "monster/orc_warlord.png",
    "ogre": "monster/ogre_new.png",
    "troll": "monster/troll.png",
    "wight": "monster/undead/wight_new.png",
    "young_dragon": "monster/dragons/dragon.png",
    # spare beasts and horrors, for creatures added later
    "bat": "monster/animals/bat.png",
    "giant_bat": "monster/animals/giant_bat.png",
    "snake": "monster/animals/snake.png",
    "adder": "monster/animals/adder.png",
    "crocodile": "monster/animals/crocodile.png",
    "giant_frog": "monster/animals/giant_frog.png",
    "giant_beetle": "monster/animals/giant_beetle.png",
    "scorpion": "monster/animals/scorpion_new.png",
    # the familiar's forms (Expansion 3 F.1; the cat, owl and weasel are drawn in tools/beast_art.py)
    "rat": "monster/animals/grey_rat.png",
    "spider": "monster/animals/spider.png",
    "frog": "monster/animals/giant_frog.png",
    "lizard": "monster/animals/iguana.png",
    "crab": "monster/animals/fire_crab.png",
    "giant_centipede": "monster/animals/giant_centipede.png",
    "polar_bear": "monster/animals/polar_bear.png",
    "hound": "monster/animals/hound.png",
    "war_dog": "monster/animals/war_dog.png",
    "sheep": "monster/animals/sheep.png",
    "yak": "monster/animals/yak_new.png",
    "raven": "monster/raven.png",
    "ghost": "monster/undead/ghost_new.png",
    "wraith": "monster/undead/wraith.png",
    "mummy": "monster/undead/mummy.png",
    "ghast": "monster/undead/necrophage_new.png",  # (Create Undead's ghast: Expansion 3 F.4)
    "lich": "monster/undead/lich.png",
    "vampire": "monster/undead/vampire_new.png",
    "skeleton_large": "monster/undead/skeletons/skeleton_humanoid_large_new.png",
    "skeleton_beast": "monster/undead/skeletons/skeleton_quadruped_small.png",
    "zombie_large": "monster/undead/zombies/zombie_ogre.png",
    "kobold": "monster/kobold_new.png",
    "gnoll_shaman": "monster/gnoll_shaman.png",
    "gnoll_sergeant": "monster/gnoll_sergeant.png",
    "orc_priest": "monster/orc_priest_new.png",
    "orc_warrior": "monster/orc_warrior_new.png",
    "orc_wizard": "monster/orc_wizard_new.png",
    "hill_giant": "monster/hill_giant_new.png",
    "ettin": "monster/ettin_new.png",
    "cyclops": "monster/cyclops_new.png",
    "minotaur": "monster/minotaur.png",
    "centaur": "monster/centaur.png",
    "harpy": "monster/harpy.png",
    "griffon": "monster/griffon.png",
    "manticore": "monster/manticore.png",
    "wyvern": "monster/dragons/wyvern_new.png",
    "swamp_dragon": "monster/dragons/swamp_dragon_new.png",
    "ice_dragon": "monster/dragons/ice_dragon_new.png",
    "golden_dragon": "monster/dragons/golden_dragon.png",
    "shadow_dragon": "monster/dragons/shadow_dragon.png",
    "hydra": "monster/dragons/hydra_3_new.png",
    "treant": "monster/fungi_plants/treant.png",
    "dryad": "monster/dryad.png",
    "earth_elemental": "monster/nonliving/earth_elemental.png",
    "fire_elemental": "monster/nonliving/fire_elemental_new.png",
    "gargoyle": "monster/nonliving/gargoyle.png",
    "stone_golem": "monster/nonliving/stone_golem.png",
    "deep_troll": "monster/deep_troll.png",
    "rock_troll": "monster/rock_troll.png",
    "naga": "monster/naga.png",
    "merfolk": "monster/merfolk.png",
    "necromancer": "monster/necromancer_new.png",
    "wizard": "monster/wizard.png",
    "death_knight": "monster/death_knight.png",
    # the summoned spirits' forms (Expansion 3 F.2; the wolf, hawk, ghost, ghoul, skeleton, golem, elementals,
    # centipede and spider are above)
    "shark": "monster/aquatic/shark_new.png",
    "fey_spirit": "monster/faun.png",
    "beholderkin_spirit": "monster/eyes/giant_eyeball.png",
    "mind_flayer_spirit": "monster/aberration/unseen_horror_new.png",
    "air_elemental": "monster/nonliving/air_elemental_new.png",
    "water_elemental": "monster/nonliving/water_elemental_new.png",
    "clay_golem": "monster/nonliving/clay_golem.png",
    "iron_golem": "monster/nonliving/iron_golem.png",
    "giant_wasp": "monster/animals/yellow_wasp.png",
    # each summoned creature by its own id (its card and anything that has no form), as its first form
    "bestial_spirit": "monster/animals/wolf.png",
    "undead_spirit": "monster/undead/ghoul.png",
    "aberrant_spirit": "monster/eyes/giant_eyeball.png",
    "construct_spirit": "monster/nonliving/iron_golem.png",
    "elemental_spirit": "monster/nonliving/earth_elemental.png",
    "giant_insect": "monster/animals/giant_centipede.png",
    # the spirits of levels 5-6 (Expansion 3 F.3; the animated objects are drawn in tools/beast_art.py)
    "celestial_spirit": "monster/holy/angel_new.png",
    "celestial_avenger": "monster/holy/angel_new.png",
    "celestial_defender": "monster/holy/angel_mace.png",
    "draconic_spirit": "monster/dragons/dragon.png",
    "draconic_acid": "monster/dragons/dragon.png",
    "draconic_cold": "monster/dragons/ice_dragon_new.png",
    "draconic_lightning": "monster/dragons/storm_dragon_new.png",
    "draconic_poison": "monster/dragons/swamp_dragon_new.png",
    "fiendish_spirit": "monster/demons/red_devil_new.png",
    "fiend_demon": "monster/demons/balrug_new.png",
    "fiend_devil": "monster/demons/red_devil_new.png",
    "fiend_yugoloth": "monster/demons/neqoxec_new.png",
}
for cid, path in CREATURES.items():
    pick(f"creature/{cid}", path, "creature")
# A wild boar: the pack's hog, darkened to a bristly brown-black.
pick("creature/boar", "monster/animals/hog_new.png", "creature", hue=14, sat=0.55, val=0.48)
# A bugbear: a hobgoblin made bigger and furrier in tone.
pick("creature/bugbear", "monster/boggart_new.png", "creature", hue=18, sat=0.6, val=0.7)
# A slaad spirit (Summon Aberration): the pack's giant frog in a red slaad's colours.
pick("creature/slaad_spirit", "monster/animals/giant_frog.png", "creature", hue=2, sat=0.75, val=0.8)
# A draconic spirit of flame (Summon Dragon): the pack's green dragon in a red dragon's colours.
pick("creature/draconic_fire", "monster/dragons/dragon.png", "creature", hue=0, sat=0.8, val=0.85)
# A hawk: the pack's shrike in a hawk's browns.
pick("creature/hawk", "monster/animals/caustic_shrike.png", "creature", hue=28, sat=0.5, val=0.8)

# Items. Every item in data/items.json gets item/<id>; several share a picture.
ITEMS = {
    # weapons
    "club": "item/weapon/club_new.png", "dagger": "item/weapon/dagger_new.png", "knife": "item/weapon/knife.png",
    "greatclub": "item/weapon/giant_club_new.png", "handaxe": "item/weapon/hand_axe_1_new.png",
    "javelin": "item/weapon/spear_1.png", "light_hammer": "item/weapon/hammer_1_new.png", "mace": "item/weapon/mace_1_new.png",
    "quarterstaff": "item/weapon/quarterstaff_new.png", "sickle": "item/weapon/scythe_1_new.png", "spear": "item/weapon/spear_2_new.png",
    "light_crossbow": "item/weapon/ranged/crossbow_1.png", "dart": "item/weapon/ranged/tomahawk_1.png",
    "shortbow": "item/weapon/ranged/shortbow_1.png", "sling": "item/weapon/ranged/sling_1.png",
    "battleaxe": "item/weapon/battle_axe_1.png", "flail": "item/weapon/flail_1_new.png", "glaive": "item/weapon/glaive_1.png",
    "greataxe": "item/weapon/executioner_axe_1.png", "greatsword": "item/weapon/greatsword_1_new.png",
    "halberd": "item/weapon/halberd_1.png", "longsword": "item/weapon/long_sword_1_new.png", "maul": "item/weapon/mace_large_1_new.png",
    "morningstar": "item/weapon/morningstar_1_new.png", "pike": "item/weapon/spear_3.png", "rapier": "item/weapon/rapier_1.png",
    "scimitar": "item/weapon/scimitar_1_new.png", "shortsword": "item/weapon/short_sword_1_new.png",
    "warhammer": "item/weapon/hammer_2_new.png", "war_pick": "item/weapon/morningstar_3.png",
    "hand_crossbow": "item/weapon/ranged/hand_crossbow.png", "heavy_crossbow": "item/weapon/ranged/arbalest_1.png",
    "longbow": "item/weapon/ranged/longbow_1.png",
    "lance": "item/weapon/spear_6.png", "trident": "item/weapon/trident_1.png", "whip": "item/weapon/bullwhip_new.png",
    # ammunition
    "arrows": "item/weapon/ranged/elven_arrow.png", "bolts": "item/weapon/ranged/orcish_arrow.png",
    "sling_bullets": "item/weapon/ranged/sling_bullet_1_new.png",
    "needles": "item/weapon/ranged/needle-c.png", "firearm_bullets": "item/weapon/ranged/sling_bullet_2_new.png",
    # armour
    "padded_armor": "item/armor/torso/animal_skin_1_new.png", "leather_armor": "item/armor/torso/leather_armor_1.png",
    "studded_leather": "item/armor/torso/studded_leather_armor.png", "hide_armor": "item/armor/torso/troll_hide.png",
    "chain_shirt": "item/armor/torso/ring_mail_1_new.png", "scale_mail": "item/armor/torso/scale_mail_1_new.png",
    "breastplate": "item/armor/torso/orcish_platemail.png", "half_plate": "item/armor/torso/plate_mail_2.png",
    "ring_mail": "item/armor/torso/ring_mail_2_new.png", "chain_mail": "item/armor/torso/chain_mail_1.png",
    "splint_armor": "item/armor/torso/splint_mail_1.png", "plate_armor": "item/armor/torso/plate_mail_1.png",
    "shield": "item/armor/shields/shield_2_new.png",
    "leather_cap": "item/armor/headgear/cap_1.png", "iron_helm": "item/armor/headgear/helmet_1.png",
    "great_helm": "item/armor/headgear/helmet_2_etched.png",
    # clothing
    "underclothes": "item/armor/torso/robe_1_new.png", "wool_underclothes": "item/armor/torso/robe_2_new.png",
    "rags": "item/armor/torso/animal_skin_2_new.png", "common_clothes": "item/armor/torso/robe_1_old.png",
    "dark_clothes": "item/armor/torso/robe_ego_2.png", "travelers_clothes": "item/armor/torso/leather_armor_2.png",
    "fine_clothes": "item/armor/torso/robe_art_1.png", "vestments": "item/armor/torso/robe_3.png",
    "wool_cloak": "item/armor/back/cloak_2.png", "hooded_cloak": "item/armor/back/cloak_3.png",
    "fur_cloak": "item/armor/back/cloak_1_leather.png", "oilskin_coat": "item/armor/back/cloak_4.png",
    "hood": "item/armor/headgear/hat_2.png", "fur_hat": "item/armor/headgear/hat_3.png",
    "wool_gloves": "item/armor/hands/glove_1_new.png", "leather_gloves": "item/armor/hands/glove_3_new.png",
    "boots": "item/armor/feet/boots_1_brown_new.png", "fine_boots": "item/armor/feet/boots_2_jackboots.png",
    "sandals": "item/armor/feet/low_boots.png",
    # gear
    "backpack": "item/misc/misc_box.png", "bedroll": "item/armor/back/cloak_1_leather.png",
    "blanket": "item/armor/back/cloak_2.png", "candle": "item/misc/misc_lamp_inert.png",
    "torch": "item/misc/misc_lantern.png", "lantern": "item/misc/misc_lamp_new.png",
    "oil_flask": "item/potion/brown_new.png", "tinderbox": "item/misc/misc_box.png",
    "crowbar": "item/weapon/spear_7.png", "rope": "item/misc/misc_disc_new.png",
    "grappling_hook": "item/weapon/trident_1.png", "iron_pot": "item/misc/misc_orb.png",
    "mess_kit": "item/misc/misc_quad.png", "waterskin": "item/potion/murky.png", "sack": "item/misc/misc_box.png",
    "shovel": "item/weapon/spear_6.png", "hunting_trap": "item/weapon/ranged/throwing_net.png",
    "fishing_tackle": "item/weapon/ranged/sling_2.png", "tent": "item/armor/back/cloak_4.png",
    "whetstone": "item/misc/misc_stone_new.png", "soap": "item/misc/misc_stone_inert.png",
    "bandages": "item/scroll/blank_paper.png", "splint": "item/weapon/club_old.png",
    "needle_thread": "item/weapon/ranged/needle-c.png", "incense": "item/misc/misc_phial.png",
    "ink_and_quill": "item/potion/black_new.png", "parchment": "item/scroll/blank_paper.png",
    "signet_ring": "item/ring/gold.png", "rank_insignia": "item/amulet/face_2.png",
    "trophy": "item/misc/misc_horn.png", "manacles": "item/misc/key.png",
    "potion_healing": "item/potion/ruby_new.png", "potion_healing_greater": "item/potion/purple_red.png",
    "potion_healing_superior": "item/potion/potion_purple_red.png", "potion_healing_supreme": "item/potion/ruby_old.png", "fodder": "item/food/fruit.png",
    "firewood": "item/weapon/club_2.png", "poppy_milk": "item/potion/white_new.png",
    "healing_herbs": "item/food/choko.png", "snares": "item/weapon/ranged/throwing_net.png",
    "bell_line": "item/misc/misc_disc_new.png", "spyglass": "item/wand/gem_brass_new.png",
    "holy_water": "item/potion/cloudy.png", "alchemists_fire": "item/potion/golden.png",
    # tools
    "healers_kit": "item/misc/misc_box.png", "thieves_tools": "item/misc/key.png",
    "disguise_kit": "item/misc/mirror.png", "herbalism_kit": "item/food/choko.png",
    "smiths_tools": "item/weapon/hammer_1_old.png", "carpenters_tools": "item/weapon/hand_axe_2_new.png",
    "cooks_utensils": "item/misc/misc_quad.png", "dice_set": "item/misc/misc_stone_old.png",
    "playing_cards": "item/misc/misc_deck_new.png", "lute": "item/misc/misc_fan_new.png", "flute": "item/misc/misc_horn.png",
    "navigators_tools": "item/misc/misc_orb.png", "leatherworkers_tools": "item/weapon/ranged/needle-c.png",
    # foci
    "holy_symbol": "item/amulet/celtic_yellow.png", "component_pouch": "item/misc/misc_bottle.png",
    "arcane_focus": "item/misc/misc_crystal_new.png",
    # books and papers
    "prayer_book": "item/book/white_new.png", "old_map": "item/scroll/scroll-brown.png",
    "history_book": "item/book/leather_new.png", "lore_book": "item/book/dark_blue_new.png",
    "found_letter": "item/scroll/scroll_old.png", "sealed_letter": "item/scroll/scroll-red.png",
    "spellbook": "item/book/book_of_the_dead_new.png", "pedigree_scroll": "item/scroll/scroll-yellow.png",
    "colleague_letter": "item/scroll/scroll-green.png", "guild_letter": "item/scroll/scroll-blue.png",
    # trade goods
    "sealed_crate": "dungeon/large_box.png", "diamond": "item/misc/misc_crystal_old.png",
    "diamond_dust": "item/potion/white_new.png",
    "black_pearl": "item/misc/misc_stone_new.png", "mushroom_powder": "item/potion/brown_new.png",
    "ruby_dust": "item/potion/ruby_new.png", "miniature_sword": "item/weapon/blessed_blade.png",
    "forked_rod": "item/misc/misc_fan_inert.png",
    # the costly components and the food of Part E's spells (Expansion 3 E.1)
    "fine_diamond": "item/amulet/crystal_white.png", "flawless_diamond": "item/misc/misc_crystal_new.png",
    "diamond_hoard": "item/misc/misc_box.png", "rare_oils": "item/potion/golden.png",
    "feast_bowl": "item/misc/misc_disc_new.png", "miniature_door": "dungeon/doors/closed_door.png",
    "goodberry": "item/food/strawberry_new.png", "conjured_food": "item/food/piece_of_ambrosia_new.png",
    # the costly components of Part E.2's spells, and the everburning torch of Continual Flame (Expansion 3 E.2)
    "ruby_dust_pinch": "item/potion/ruby_new.png", "rare_inks": "item/potion/magenta_new.png",
    "divination_tools": "item/misc/misc_deck_new.png", "jacinth": "item/amulet/crystal_red.png",
    "great_diamond": "item/misc/misc_crystal_old.png", "everburning_torch": "item/misc/misc_lantern.png",
    # the costly components of Part E.3's spells (Expansion 3 E.3)
    "seers_incense": "item/misc/misc_phial_inert.png", "burning_incense": "item/misc/misc_phial.png", "rare_incense": "item/misc/misc_lamp_old.png",
    "ivory_strips": "item/amulet/bone_gray.png", "glass_eye": "item/amulet/eye_cyan.png",
    "scrying_mirror": "item/misc/misc_phantom_mirror.png", "sapphire": "item/amulet/stone_2_blue.png",
    # the costly components of Part E.4's spells (Expansion 3 E.4)
    "jade_dust": "item/potion/emerald.png", "lead_ink": "item/potion/black_new.png",
    "diamond_dust_pinch": "item/potion/white_new.png",
    # the costly components of Part E.5's spells (Expansion 3 E.5)
    "gold_dust": "item/potion/yellow_new.png", "leomunds_chest": "dungeon/chest_2_closed.png",
    "chest_replica": "item/misc/misc_box.png",
    "glyph_diamond_dust": "item/misc/misc_crystal_new.png", "symbol_diamond_dust": "item/potion/silver.png",
    "silver_rod": "item/rod/rod_1_new.png", "hallowing_incense": "item/misc/misc_phial.png",
    "silvered_salt": "item/misc/misc_stone_new.png", "gilded_ladle": "item/rod/rod_7_new.png",
    # the costly components of Part E.7's spells (Expansion 3 E.7)
    "contingency_statuette": "dungeon/statues/statue_ancient_hero.png", "clone_vessel": "dungeon/sarcophagus_open.png",
    "imprisonment_statuette": "dungeon/statues/statue_iron.png",
    "wheat": "item/food/bread_ration_old.png", "salt": "item/misc/misc_stone_inert.png",
    "iron_bar": "item/misc/misc_rune.png", "wool_bolt": "item/armor/back/cloak_2.png",
    "linen_bolt": "item/armor/torso/robe_1_new.png", "furs": "item/armor/torso/animal_skin_3.png",
    "hides": "item/armor/torso/animal_skin_1_old.png", "pepper": "item/food/grape.png",
    "copper_ingot": "item/ring/copper.png", "silver_ingot": "item/ring/silver.png", "gold_ring": "item/ring/gold.png",
    "silver_chalice": "item/misc/misc_phial.png", "gemstone": "item/amulet/stone_2_red.png",
    "jewelled_brooch": "item/amulet/cameo_blue.png",
    "gem_10": "item/amulet/stone_1_cyan.png", "gem_50": "item/amulet/stone_1_green.png",
    "gem_100": "item/amulet/stone_2_blue.png", "gem_500": "item/amulet/stone_3_green.png",
    "gem_1000": "item/amulet/crystal_red.png", "gem_5000": "item/amulet/crystal_white.png",
    "art_25": "item/amulet/cameo_orange.png", "art_250": "item/amulet/face_2.png", "art_750": "item/misc/misc_lamp_new.png",
    "art_2500": "item/amulet/celtic_yellow.png", "art_7500": "item/amulet/face_1_gold.png",
    "silver_bar": "item/misc/misc_stone_new.png", "gold_bar": "item/gold/gold_pile_4.png",
    # food and drink
    "rations": "item/food/bread_ration_new.png", "bread": "item/food/bread_ration_old.png", "cheese": "item/food/cheese.png",
    "salt_pork": "item/food/meat_ration_old.png", "dried_fish": "item/food/beef_jerky_new.png", "apples": "item/food/apple.png",
    "oats": "item/food/sultana.png", "cooked_meat": "item/food/meat_ration_new.png", "raw_fish": "item/food/chunk.png",
    "cooked_fish": "item/food/sausage.png", "porridge": "item/food/honeycomb_old.png", "wild_food": "item/food/pear.png",
    "raw_meat": "item/food/chunk.png",
    "ale": "item/potion/brown_old.png", "spirits": "item/potion/golden.png", "wine": "item/potion/purple_red.png", "fine_wine": "item/potion/ruby_new.png",
    # jewellery
    "plain_ring": "item/ring/iron.png", "amulet": "item/amulet/stone_1_green.png",
    # stand-ins for kinds of thing, when an item has no picture of its own
    "_weapon": "item/weapon/long_sword_1_old.png", "_armor": "item/armor/torso/leather_armor_3.png",
    # Blades & Backgrounds part D gear (the rest is drawn in tools/gear_art.py)
    "acid": "item/potion/bubbly.png", "antitoxin": "item/potion/cyan_new.png", "basic_poison": "item/potion/murky.png",
    "glass_bottle": "item/potion/clear.png", "flask": "item/potion/cloudy.png", "vial": "item/potion/sky_blue.png",
    "perfume": "item/potion/pink.png", "horn": "item/misc/misc_horn.png", "mirror": "item/misc/mirror.png",
    "lamp": "item/misc/misc_lamp_old.png", "bullseye_lantern": "item/misc/misc_lamp_new.png",
    "map": "item/scroll/scroll_old.png", "robe": "item/armor/torso/robe_1_new.png",
    "costume": "item/armor/torso/robe_3.png", "druid_staff": "item/staff/staff_2.png",
    "arcane_staff": "item/staff/staff_1.png", "yew_wand": "item/wand/gem_wood_new.png",
    "arcane_wand": "item/wand/gem_ivory_new.png", "arcane_rod": "item/rod/rod_5_new.png",
    "arcane_orb": "item/misc/misc_orb.png", "holy_emblem": "item/amulet/celtic_yellow.png",
    "trinket": "item/amulet/bone_gray.png",
    "chest": "dungeon/chest_2_closed.png",
    "_food": "item/food/bread_ration_new.png", "_drink": "item/potion/brown_new.png",
    "_book": "item/book/tan_new.png", "_trade": "item/misc/misc_box.png", "_gear": "item/misc/misc_box.png",
    "_jewellery": "item/ring/gold_blue.png", "_magic": "item/misc/misc_orb_2.png", "_gold": "item/gold/gold_pile_7.png",
    "_scroll": "item/scroll/scroll_new.png", "_wand": "item/wand/gem_brass_new.png", "_potion": "item/potion/cloudy.png",
}
for iid, path in ITEMS.items():
    pick(f"item/{iid}", path, "item")
# The Summon spells' costly components (Expansion 3 F.2), some gilded.
pick("item/gilded_acorn", "item/food/apricot_new.png", "item")
pick("item/gilded_flower", "item/misc/misc_fan_new.png", "item", hue=45, sat=0.75, val=1.0)
pick("item/gilded_skull", "gui/spells/components/skull.png", "item", hue=45, sat=0.7, val=1.0)
pick("item/platinum_vial", "item/misc/misc_phial.png", "item")
pick("item/lockbox", "item/misc/misc_box.png", "item")
pick("item/elemental_vial", "item/potion/golden.png", "item")
# Summon Celestial, Dragon and Fiend's components (Expansion 3 F.3): a saint's face in silver, a disc cut with a
# coiled sign, a vial of dark blood.
pick("item/silver_reliquary", "item/amulet/face_1_gold.png", "item", hue=40, sat=0.08, val=1.0)
pick("item/dragon_token", "item/misc/misc_quad.png", "item")
pick("item/bloody_vial", "item/potion/ruby_new.png", "item", hue=0, sat=0.9, val=0.6)
# Create Undead's black onyx (Expansion 3 F.4): a stone gone dark.
pick("item/black_onyx", "item/misc/misc_stone_new.png", "item", hue=260, sat=0.15, val=0.35)
for i, path in enumerate(["item/gold/gold_pile_1.png", "item/gold/gold_pile_3.png", "item/gold/gold_pile_7.png",
                          "item/gold/gold_pile_16.png"]):
    pick(f"item/_coins_{i}", path, "item")

# Paper dolls: the pack's player parts, renamed. layer -> {our name: file name in player/<layer>/}
DOLL_RENAME = {
    "aragorn": "ranger", "aragorn_2": "ranger_2", "arwen": "gown", "boromir": "captain", "frodo": "vest_brown",
    "gandalf_g": "robe_grey", "gandalf": "wizard_grey", "gimli": "dwarf_mail", "isildur": "royal", "legolas": "tunic_green",
    "merry": "jerkin", "pipin": "coat_blue", "sam": "tunic_brown", "saruman": "robe_pale", "lears_chain_mail": "chain_long",
    "pj": "plain", "zhor": "furs", "karate_2": "tunic_red", "helm_gimli": "dwarf_helm",
}
DOLL_SKIP = ("draconian", "demonspawn", "centaur", "naga", "merfolk", "octopode", "felid", "kenku", "tengu", "gargoyle",
             "ghoul", "mummy", "vampire", "demigod", "formicid", "spriggan", "minotaur", "troll_", "ogre_", "kobold",
             "deep_dwarf", "deep_elf", "shadow", "gnome", "lorc", "bikini", "chunli", "garter", "jessica", "chinа",
             "china", "dragon", "faerie", "crystal", "armor_mummy", "armor_blue", "orange_crystal", "maxwell", "vanhel",
             "robe_rainbow", "robe_jester", "robe_clouds", "robe_misfortune", "robe_of_night", "shirt_hawaii", "clown",
             "art_", "eternal", "etheric", "dyrovepreva", "taiso", "yellow_wing", "horn_evil", "bear", "mummy", "ninja",
             "hooves", "spider", "claws", "bladehands", "fork", "trishula", "trident_demon", "demon", "black_whip",
             "holy_scourge", "katana", "nunchaku", "sword_seven", "triple_sword", "double_sword", "orb", "deck", "fan",
             "disc", "skull", "head.png", "spark", "light_", "fire_", "bone_lantern", "crystal", "gong", "of_ignorance",
             "of_resistance", "donald", "dd_scion", "louise", "glowing", "bloody")
DOLL_LAYERS = ("base", "cloak", "boots", "legs", "body", "gloves", "hair", "beard", "head", "hand_right", "hand_left")


def collect_doll(pack: Path) -> None:
    for layer in DOLL_LAYERS:
        files = sorted(glob.glob(str(pack / "player" / layer / "*.png")) + glob.glob(str(pack / "player" / layer / "misc" / "*.png")))
        for f in files:
            base = os.path.basename(f)[:-4]
            if any(s in os.path.basename(f) for s in DOLL_SKIP):
                if not (layer == "hand_left" and base in ("torch", "torch_2", "lantern")):
                    continue
            if layer == "base" and not any(base.startswith(r) for r in ("human", "elf", "dwarf", "halfling", "orc")):
                continue
            name = DOLL_RENAME.get(base, base).replace("-", "_")
            if "/misc/" in f.replace("\\", "/"):
                name = f"held_{name}"
            PICKS[f"doll/{layer}/{name}"] = (os.path.relpath(f, pack).replace("\\", "/"), "doll", {})


# Effects for fights and spells
FX = {
    "arrow": "effect/arrow_{i}.png", "bolt": "effect/crossbow_bolt_{i}.png", "dart": "effect/dart_{i}.png",
    "javelin": "effect/javelin_{i}_new.png", "icicle": "effect/icicle_{i}.png", "shot": "effect/iron_shot_{i}.png",
}
for name, pattern in FX.items():
    for i in range(8):
        PICKS[f"fx/{name}_{i}"] = (pattern.format(i=i), "fx", {"optional": True})
for name, path in {
    "flame_0": "effect/flame_0.png", "flame_1": "effect/flame_1.png", "flame_2": "effect/flame_2.png",
    "frost_0": "effect/frost_0.png", "frost_1": "effect/frost_1.png",
    "fire_0": "effect/cloud_fire_0.png", "fire_1": "effect/cloud_fire_1.png", "fire_2": "effect/cloud_fire_2.png",
    "cold_0": "effect/cloud_cold_0.png", "cold_1": "effect/cloud_cold_1.png", "cold_2": "effect/cloud_cold_2.png",
    "poison_0": "effect/cloud_poison_0.png", "poison_1": "effect/cloud_poison_1.png", "poison_2": "effect/cloud_poison_2.png",
    "smoke": "effect/cloud_grey_smoke.png", "dark": "effect/cloud_black_smoke.png",
    "sparkle_0": "effect/gold_sparkles_1.png", "sparkle_1": "effect/gold_sparkles_2.png", "sparkle_2": "effect/gold_sparkles_3.png",
    "magic_0": "effect/magic_bolt_1.png", "magic_1": "effect/magic_bolt_2.png", "magic_2": "effect/magic_bolt_3.png",
    "magic_dart_0": "effect/magic_dart_0.png", "magic_dart_1": "effect/magic_dart_1.png",
    "trail_0": "effect/cloud_magic_trail_0.png", "trail_1": "effect/cloud_magic_trail_1.png",
    "drain_0": "effect/drain_0_new.png", "drain_1": "effect/drain_1_new.png", "drain_2": "effect/drain_2_new.png",
    "glow_0": "effect/goldaura_0.png", "glow_1": "effect/goldaura_1.png", "glow_2": "effect/goldaura_2.png",
    "rain_0": "effect/cloud_rain_1.png", "rain_1": "effect/cloud_rain_2.png",
    "storm_0": "effect/cloud_storm_1.png", "storm_1": "effect/cloud_storm_2.png",
    "blood_0": "misc/blood/blood_puddle_red.png", "blood_1": "misc/blood/blood_puddle_red_1.png", "blood_2": "misc/blood/blood_puddle_red_2.png",
    "cursor": "misc/cursor.png", "cursor_red": "misc/cursor_red.png", "cursor_green": "misc/cursor_green.png",
    "halo": "misc/halo.png",
}.items():
    PICKS[f"fx/{name}"] = (path, "fx", {"optional": True})


# ---------------------------------------------------------------------------- toning
def grade(im: Image.Image, which: str) -> Image.Image:
    sat, bright, warm = GRADES[which]
    a = np.asarray(im.convert("RGBA"), np.float32).copy()
    rgb = a[..., :3]
    lum = (rgb * np.array([0.299, 0.587, 0.114], np.float32)).sum(axis=2, keepdims=True)
    rgb = lum + (rgb - lum) * sat
    rgb *= bright
    rgb[..., 0] *= 1 + warm
    rgb[..., 2] *= 1 - warm
    a[..., :3] = np.clip(rgb, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def recolor(im: Image.Image, hue: float, sat: float = 1.0, val: float = 1.0) -> Image.Image:
    alpha = im.getchannel("A")
    hsv = np.asarray(im.convert("RGB").convert("HSV"), np.float32).copy()
    hsv[..., 0] = hue
    hsv[..., 1] = np.clip(hsv[..., 1] * sat, 0, 255)
    hsv[..., 2] = np.clip(hsv[..., 2] * val, 0, 255)
    out = Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGBA")
    out.putalpha(alpha)
    return out


# ---------------------------------------------------------------------------- building
def fetch_pack() -> Path:
    dest = ROOT / "build" / "tiles_src"
    found = list(dest.glob("*/dungeon"))
    if found:
        return found[0].parent
    dest.mkdir(parents=True, exist_ok=True)
    print("Downloading the Dungeon Crawl tile pack (CC0, about 6 MB)...")
    with urllib.request.urlopen(PACK_URL, timeout=120) as r:
        data = r.read()
    zipfile.ZipFile(io.BytesIO(data)).extractall(dest)
    return next(dest.glob("*/dungeon")).parent


def body_parts(b) -> dict[str, list[float]]:
    """Where each part of a body is (the middle of it, in the figure's pixels), for marking wounds. The figure
    faces you, so its right arm and leg are on your left."""
    import figure_art as fa
    import numpy as np

    g = b.grid
    c = b.c
    out = {}
    for name, codes, side in (("head", (fa.HEAD,), 0), ("torso", (fa.TORSO, fa.PELVIS), 0),
                              ("right_arm", (fa.UARM, fa.LARM), -1), ("left_arm", (fa.UARM, fa.LARM), 1),
                              ("right_leg", (fa.ULEG, fa.LLEG), -1), ("left_leg", (fa.ULEG, fa.LLEG), 1)):
        m = np.isin(g, codes)
        if side < 0:
            m[:, c:] = False
        elif side > 0:
            m[:, :c] = False
        ys, xs = np.nonzero(m)
        if len(xs):
            out[name] = [round(float(xs.mean()), 1), round(float(ys.mean()), 1)]
    return out


def figure_tiles() -> tuple[dict[str, Image.Image], dict]:
    """People in pixel art (tools/figure_art.py, tools/figure_gear.py): bodies, what they wear, what they hold.
    Returns the tiles and the facts the game needs to stack them (each body's hands)."""
    import figure_art as fa
    import figure_gear as fg
    from PIL import ImageFilter

    out: dict[str, Image.Image] = {}
    bodies = fa.bodies()
    ref = bodies["human_male"]

    def keep(name: str, im: Image.Image) -> None:
        if np.asarray(im)[..., 3].any():
            out[name] = im

    for key, b in bodies.items():
        keep(f"fig/body/{key}", fa.base(b))
        for g in fg.GARMENTS:
            keep(f"fig/wear/{key}/{g}", fg.garment(b, g))
        for h in fg.HAIR:
            keep(f"fig/hair/{key}/{h}", fg.hair(b, h))
        for bd in fg.BEARDS:
            keep(f"fig/beard/{key}/{bd}", fg.beard(b, bd))
        for hg in fg.HEADGEAR:
            keep(f"fig/head/{key}/{hg}", fg.headgear(b, hg))
        keep(f"fig/cloak/{key}/back", fg.cloak(b, "back"))
        keep(f"fig/cloak/{key}/front", fg.cloak(b, "front"))
        keep(f"fig/eyes/{key}", fg.eyes(b))
        for mk in fg.MARKS:
            keep(f"fig/mark/{key}/{mk}", fg.mark(b, mk))
        for pt in fg.PAINTS:
            keep(f"fig/paint/{key}/{pt}", fg.face_paint(b, pt))
        for feat, options in fg.FEATURES.items():
            for opt in options:
                keep(f"fig/feature/{key}/{feat}_{opt}", fg.feature(b, feat, opt))
    right, left = ref.hands
    for w in fg.WEAPONS:
        metal = fg.held(w, right, "metal")
        keep(f"fig/held/{w}/metal", metal)
        keep(f"fig/held/{w}/rest", fg.held(w, right, "rest"))
        shape = np.asarray(fg.held(w, right, "all"))[..., 3] > 0
        glow = np.zeros((32, 32, 4), np.uint8)
        glow[..., :3] = 255
        glow[..., 3] = np.where(shape, 255, 0)
        g = Image.fromarray(glow, "RGBA").filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
        keep(f"fig/held/{w}/glow", g)
        keep(f"fig/held/{w}/left_metal", fg.held(w, left, "metal"))
        keep(f"fig/held/{w}/left_rest", fg.held(w, left, "rest"))
    for kind in fg.SHIELDS:
        keep(f"fig/shield/{kind}/field", fg.shield(kind, left, "field"))
        keep(f"fig/shield/{kind}/rim", fg.shield(kind, left, "rim"))
        for em in fg.EMBLEMS[1:]:
            keep(f"fig/shield/{kind}/{em}", fg.shield(kind, left, em))
    meta = {"ref": "human_male", "hands": {k: [list(b.hands[0]), list(b.hands[1])] for k, b in bodies.items()},
            "heads": {k: list(b.head) for k, b in bodies.items()},
            "parts": {k: body_parts(b) for k, b in bodies.items()}}
    return out, meta


ADAPTED: list[tuple[str, Image.Image, Image.Image]] = []  # (creature, as borrowed, as adapted), for the sheet


def gather(pack: Path) -> dict[str, Image.Image]:
    tiles: dict[str, Image.Image] = {}
    missing = []
    for name, (path, which, extra) in PICKS.items():
        if name.endswith("*"):
            files = sorted(glob.glob(str(pack / path)))
            if extra.get("limit"):
                files = files[: extra["limit"]]
            if not files:
                missing.append(path)
            for i, f in enumerate(files):
                tiles[f"{name[:-1]}_{i}"] = grade(Image.open(f), which)
            continue
        f = pack / path
        if not f.exists():
            if not extra.get("optional"):
                missing.append(path)
            continue
        im = Image.open(f).convert("RGBA")
        if "hue" in extra:
            im = recolor(im, extra["hue"], extra.get("sat", 1.0), extra.get("val", 1.0))
        tiles[name] = grade(im, which)
    if missing:
        raise SystemExit("Missing from the pack:\n  " + "\n  ".join(missing))
    # Borrowed creatures pass through the adaptation step, so they look like the game's own figures.
    ADAPTED.clear()
    for name in sorted(k for k in tiles if k.startswith("creature/")):
        before = tiles[name]
        tiles[name] = adapt_art.adapt(before, name.split("/", 1)[1])
        ADAPTED.append((name.split("/", 1)[1], before, tiles[name]))
    # Autumn trees, turned green for most of the year.
    autumn = sorted(k for k in tiles if k.startswith("tree/autumn_"))
    for i, k in enumerate(autumn):
        tiles[f"tree/oak_{i}"] = grade(tile_art.recolor_tree(tiles[k], 62 + (i % 3) * 6), "tree")
    # Grass that is not quite so green: dry grass for steppe and heath, frosted for the cold.
    grass = sorted(k for k in tiles if k.startswith("floor/grass_") and k[len("floor/grass_"):].isdigit())
    for i, k in enumerate(grass):
        tiles[f"floor/drygrass_{i}"] = tile_art.tinted(tiles[k], (150, 136, 80), 0.45)
        tiles[f"floor/heath_{i}"] = tile_art.tinted(tiles[k], (122, 112, 92), 0.55)
        tiles[f"floor/frost_{i}"] = tile_art.tinted(tiles[k], (176, 188, 196), 0.35)
    # Bare rock in the open is lighter than a cave's floor.
    for i, k in enumerate(sorted(k for k in tiles if k.startswith("floor/greydirt_"))):
        a = np.asarray(tiles[k], np.float32).copy()
        a[..., :3] = np.clip(a[..., :3] * 1.9 + 14, 0, 255)
        tiles[f"floor/rock_{i}"] = Image.fromarray(a.astype(np.uint8), "RGBA")
    figs, _ = figure_tiles()
    tiles.update(figs)
    for name, im in {**tile_art.all_drawn(), **nature_art.all_drawn(), **map_art.all_drawn(), **gear_art.all_drawn(), **beast_art.all_drawn(),
                     **town_art.all_drawn()}.items():
        which = "none" if name.startswith(("icon/", "map/", "status/", "dlc/")) else ("ground" if name.startswith(("floor/", "wall/")) else "feature")
        if any(k in name for k in ("glow", "/fey", "water/hot", "moonstone")):
            which = "fx"  # things that shine keep their light
        tiles[name] = grade(im, which) if which != "none" else im
    return tiles


def pack_sheets(tiles: dict[str, Image.Image]) -> tuple[list[Image.Image], dict]:
    """Shelf-pack the tiles into SHEET-sized images. Returns the sheets and name -> [sheet, x, y, w, h]."""
    sheets: list[Image.Image] = []
    index: dict[str, list[int]] = {}
    order = sorted(tiles, key=lambda n: (-tiles[n].height, n))
    sheet = None
    x = y = shelf = 0
    for name in order:
        im = tiles[name]
        w, h = im.size
        if sheet is None or x + w > SHEET:
            x = 0
            y += shelf
            shelf = 0
        if sheet is None or y + h > SHEET:
            sheet = Image.new("RGBA", (SHEET, SHEET), (0, 0, 0, 0))
            sheets.append(sheet)
            x = y = shelf = 0
        sheet.paste(im, (x, y))
        index[name] = [len(sheets) - 1, x, y, w, h]
        x += w
        shelf = max(shelf, h)
    return sheets, index


def preview(tiles: dict[str, Image.Image], path: Path) -> None:
    names = sorted(tiles)
    cols = 24
    cell = 40
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 10)), (40, 40, 44))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        im = tiles[n]
        x, y = (i % cols) * cell, (i // cols) * (cell + 10)
        sheet.paste(im.resize((32, 32)), (x + 4, y), im.resize((32, 32)))
        d.text((x, y + 32), n.split("/")[-1][:7], fill=(200, 200, 200))
    sheet.save(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=None)
    ap.add_argument("--preview", default=None)
    ap.add_argument("--adapt-sheet", default=None, help="write the borrowed creatures before and after, side by side")
    args = ap.parse_args(argv)
    pack = Path(args.pack) if args.pack else fetch_pack()
    tiles = gather(pack)
    sheets, index = pack_sheets(tiles)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("sheet_*.png"):
        old.unlink()
    files = []
    for i, s in enumerate(sheets):
        fn = f"sheet_{i}.png"
        s.save(OUT / fn, optimize=True)
        files.append(fn)
    meta = {"_comment": "Built by tools/build_tiles.py from the Dungeon Crawl Stone Soup tiles (CC0) and tools/tile_art.py. "
                        "name: [sheet, x, y, w, h].",
            "tile": 32, "sheets": files, "figures": figure_tiles()[1], "tiles": {k: index[k] for k in sorted(index)}}
    (OUT / "tiles.json").write_text(json.dumps(meta, indent=0, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"{len(tiles)} tiles in {len(sheets)} sheets -> {OUT}")
    if args.preview:
        preview(tiles, Path(args.preview))
    if args.adapt_sheet:
        adapt_art.before_after(ADAPTED, Path(args.adapt_sheet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
