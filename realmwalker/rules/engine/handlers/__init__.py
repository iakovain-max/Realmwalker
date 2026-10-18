"""Python for what the data cannot say, registered by id (`@handler("...")` from rules/engine/events.py).

    features.py   race traits and class features
    monsters.py   creature traits
    mastery.py    the weapon masteries (PHB 2024)
    feats.py      the origin feats (PHB 2024 chapter 5)
    general_feats.py   the general and fighting style feats
    boons.py      the epic boons (level 19)
    fighter.py    the 2024 fighter, the Champion and the Knight
    battle_master.py   the Battle Master's superiority dice and maneuvers (Expansion 4)
    arcane.py     the Eldritch Knight and the Arcane Trickster (Expansion 4 Part B)
    arms.py       the fighter's and rogue's magic weapons and things (Expansion 4 Part D)
    rogue.py      the 2024 rogue (Sneak Attack, Cunning Strike), the Thief and the Assassin
    cleric.py     the 2024 cleric (Divine Spark, Blessed Strikes, Divine Intervention), the Life and War Domains
    domains.py    the Light Domain (Warding Flare, Radiance of the Dawn, Corona of Light) and the Trickery Domain
                  (Blessing of the Trickster, Invoke Duplicity's double, Trickster's Transposition; Expansion 5 Part B)
    wizard.py     the 2024 wizard (Overchannel, the ward's mending, Counterspell)
    schools.py    the Diviner (Portent, Expert Divination, The Third Eye) and the Illusionist (Expansion 5 Part A)
    staves.py     the wizard's and cleric's wands, staffs and rods (Expansion 5 Part D)
    summons.py    the summoned spirits' traits and the fey spirit's moods (Expansion 3 F.2)
    undead.py     the raised dead's traits: the ghast's Stench, the mummy's rot (Expansion 3 F.4)
"""

from realmwalker.rules.engine.handlers import (arcane, arms, battle_master, boons, cleric, domains, feats,  # noqa: F401
                                               features, fighter,  # noqa: F401
                                               general_feats,  # noqa: F401
                                               mastery, monsters, rogue, schools, staves, summons, undead,  # noqa: F401
                                               wizard)  # noqa: F401  (registering is importing)
