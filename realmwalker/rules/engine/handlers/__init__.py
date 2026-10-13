"""Python for what the data cannot say, registered by id (`@handler("...")` from rules/engine/events.py).

    features.py   race traits and class features
    monsters.py   creature traits
    mastery.py    the weapon masteries (PHB 2024)
    feats.py      the origin feats (PHB 2024 chapter 5)
    general_feats.py   the general and fighting style feats
    boons.py      the epic boons (level 19)
"""

from realmwalker.rules.engine.handlers import boons, feats, features, general_feats, mastery, monsters  # noqa: F401  (registering is importing)
