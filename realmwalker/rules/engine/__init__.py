"""The rules kernel (docs/EXPANSIONS.md §4.3): what the rules of a fight are made of, so that new content is data.

    conditions.py   the 2024 conditions and exhaustion, read from data/conditions.json
    query.py        every derived number in one place: advantage and disadvantage, saving throws, AC, speed,
                    resistances, critical hits. The battle, its screen and the tactics all ask here.
    events.py       hook points ("attack_hit", "damage_incoming", "hp_zero"...) and the dispatcher that runs the
                    hooks of whatever traits, features and spells the fighters have
    traits.py       the definitions of traits and features (data/traits.json): modifiers and hooks
    effects.py      effect operations ("ops"): what spells and abilities do, as data
    durations.py    how long things last, and their ending
    resources.py    pools of uses (Second Wind, Channel Divinity...) and when they come back
    handlers/       Python for what data cannot say, registered by id
    check.py        the start-up check: every op, handler and trait the data names must exist

Pure logic, like the rest of rules/: it never imports the interface.
"""
