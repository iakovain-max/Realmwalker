"""Python for what the data cannot say, registered by id (`@handler("...")` from rules/engine/events.py).

    features.py   race traits and class features
    monsters.py   creature traits
    mastery.py    the weapon masteries (PHB 2024)
    feats.py      the origin feats (PHB 2024 chapter 5)
    general_feats.py   the general and fighting style feats
    boons.py      the epic boons (level 19)
    fighter.py    the 2024 fighter, the Champion and the Knight
    rogue.py      the 2024 rogue (Sneak Attack, Cunning Strike), the Thief and the Assassin
"""

from realmwalker.rules.engine.handlers import boons, feats, features, fighter, general_feats, mastery, monsters, rogue  # noqa: F401  (registering is importing)
