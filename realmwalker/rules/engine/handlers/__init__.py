"""Python for what the data cannot say, registered by id (`@handler("...")` from rules/engine/events.py).

    features.py   race traits and class features
    monsters.py   creature traits
    mastery.py    the weapon masteries (PHB 2024)
    feats.py      feats (PHB 2024 chapter 5)
"""

from realmwalker.rules.engine.handlers import feats, features, mastery, monsters  # noqa: F401  (registering is importing)
