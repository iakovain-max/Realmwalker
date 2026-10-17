"""Python for what the data cannot say, registered by id (`@handler("...")` from rules/engine/events.py).

    features.py   race traits and class features
    monsters.py   creature traits
    mastery.py    the weapon masteries (PHB 2024)
    feats.py      the origin feats (PHB 2024 chapter 5)
    general_feats.py   the general and fighting style feats
    boons.py      the epic boons (level 19)
    fighter.py    the 2024 fighter, the Champion and the Knight
    rogue.py      the 2024 rogue (Sneak Attack, Cunning Strike), the Thief and the Assassin
    cleric.py     the 2024 cleric (Divine Spark, Blessed Strikes, Divine Intervention), the Life and War Domains
    wizard.py     the 2024 wizard (Overchannel, the ward's mending, Counterspell)
    summons.py    the summoned spirits' traits and the fey spirit's moods (Expansion 3 F.2)
    undead.py     the raised dead's traits: the ghast's Stench, the mummy's rot (Expansion 3 F.4)
"""

from realmwalker.rules.engine.handlers import (boons, cleric, feats, features, fighter, general_feats,  # noqa: F401
                                               mastery, monsters, rogue, summons, undead, wizard)  # noqa: F401  (registering is importing)
