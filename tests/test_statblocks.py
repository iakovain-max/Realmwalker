"""2025 stat blocks (rules/engine/statblocks.py): a block plus a creature's flavour makes the creature a fight uses;
and the 2025 machinery - Multiattack plans, Recharge, uses per day, at-will and per-day spellcasting, Legendary
Resistance and Legendary Actions - proven on test creatures (the first real legendary creature comes with a later
expansion)."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import statblocks
from realmwalker.rules import tactics
from realmwalker.world.tables import Tables

DRAKE = {
    "name": "Test Drake", "page": 1, "size": "large", "type": "dragon", "tags": [], "alignment": "unaligned",
    "ac": 15, "initiative": 4, "hp": "10d10+30", "hp_avg": 85, "speed": {"walk": 30, "fly": 60},
    "abilities": {"str": 18, "dex": 12, "con": 16, "int": 8, "wis": 12, "cha": 10},
    "saves": {"dex": 4, "wis": 4}, "skills": {"perception": 4}, "senses": {"darkvision": 60}, "passive": 14,
    "languages": ["Draconic"], "telepathy": 0, "cr": 5, "xp": 1800, "pb": 3,
    "resist": ["cold"], "vulnerable": [], "immune": ["fire"], "condition_immune": ["frightened"], "gear": [],
    "traits": [{"id": "legendary_resistance", "name": "Legendary Resistance", "uses": "2/day"}],
    "actions": [
        {"id": "bite", "name": "Bite", "kind": "melee", "bonus": 7, "reach": 10, "damage": "2d8+4", "type": "piercing",
         "extra": [{"damage": "1d6", "type": "fire"}]},
        {"id": "claw", "name": "Claw", "kind": "melee", "bonus": 7, "reach": 5, "damage": "1d6+4", "type": "slashing",
         "on_hit": [{"op": "condition", "condition": "prone", "max_size": "medium"}]},
        {"id": "fire_breath", "name": "Fire Breath", "kind": "save", "save": "dex", "dc": 14,
         "area": {"shape": "cone", "size": 30}, "damage": "6d6", "type": "fire", "half": True, "recharge": 5},
        {"id": "roar", "name": "Roar", "kind": "melee", "bonus": 7, "reach": 5, "damage": "1d4", "type": "thunder",
         "uses": "1/day"},
    ],
    "multiattack": {"attacks": [{"id": "bite", "count": 1}, {"id": "claw", "count": 2}]},
    "bonus_actions": [], "reactions": [],
    "spellcasting": {"ability": "cha", "dc": 13, "attack": 5, "at_will": ["fire_bolt"], "per_day": {"1": ["command"]}},
    "legendary_resistance": {"per_day": 2, "lair": 3},
    "legendary": {"uses": 2, "lair_uses": 3,
                  "actions": [{"id": "tail", "name": "Tail", "kind": "melee", "bonus": 7, "reach": 10, "damage": "1d8+4",
                               "type": "bludgeoning"}]},
}
FLAVOUR = {"statblock": "test_drake", "name": "drake", "plural": "drakes", "body": "quadruped", "morale": "warrior",
           "traits": ["takes_food"], "attack_extras": {"bite": {"wound": "bite"}}, "descriptions": ["A test drake."]}


@pytest.fixture(scope="module")
def tables(data):
    t = Tables(data)
    t.creatures.defs["test_drake"] = statblocks.resolve("test_drake", FLAVOUR, {"test_drake": DRAKE})
    return t


def hero(tables, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    return b.build()


def fight(tables, gap=1, seed=1):
    c = hero(tables, seed)
    cr = spawn(tables, "test_drake", RNG(seed, "foe"), 1)
    b = Battle(tables, [c], [cr], Env(), RNG(seed, "battle"), spots={0: (3, 4), 1: (3 + gap, 4)})
    b.start()
    return b, b.fighters[0], b.fighters[1]


def test_a_block_and_its_flavour_make_the_creature(tables):
    d = tables.creatures["test_drake"]
    assert (d["name"], d["ac"], d["cr"], d["xp"], d["initiative"], d["speed"]) == ("drake", 15, 5.0, 1800, 4, 30)
    assert d["speeds"]["fly"] == 60 and d["darkvision"] == 60 and d["resist"] == ["cold"]
    assert "takes_food" in d["traits"] and d["multiattack_plan"] == ["bite", "claw", "claw"]
    bite = next(a for a in d["attacks"] if a["id"] == "bite")
    assert bite["reach"] and bite["wound"] == "bite" and bite["extra"][0]["type"] == "fire"


def test_saves_and_initiative_come_from_the_block(tables):
    b, me, drake = fight(tables)
    assert drake.save_bonus("dex") == 4 and drake.save_bonus("str") == 4  # proficient Dex 4; Str 18 is +4 anyway
    assert drake.save_bonus("con") == 3


def test_multiattack_plays_out_the_plan(tables):
    b, me, drake = fight(tables, gap=1)
    me.char.hp = me.char.max_hp = 500
    names = []
    real = b._attack

    def spy(att, opt, target, **kw):
        names.append(opt.extra.get("id"))
        return real(att, opt, target, **kw)
    b._attack = spy
    b.order = [drake.id, me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(drake)
    drake.recharge["fire breath"] = False  # (so it does not breathe)
    opts = [o for o in b.attack_options(drake) if o.available and not o.extra.get("area")]
    tactics._fight(b, drake, opts, attacks=3)
    assert names[:3] == ["bite", "claw", "claw"]


def test_an_extra_damage_type_and_a_hit_that_knocks_down(tables):
    b, me, drake = fight(tables)
    me.char.hp = me.char.max_hp = 500
    bite = next(o for o in b.attack_options(drake) if o.extra.get("id") == "bite")
    claw = next(o for o in b.attack_options(drake) if o.extra.get("id") == "claw")
    bite.bonus = claw.bonus = 99
    b._attack(drake, bite, me)
    assert any(e["kind"] == "damage" and e["dtype"] == "fire" for e in b.events)
    b._attack(drake, claw, me)
    assert "prone" in me.conditions


def test_recharge_and_uses_per_day(tables):
    b, me, drake = fight(tables, gap=2)
    breath = next(o for o in b.attack_options(drake) if o.extra.get("id") == "fire_breath")
    assert breath.available
    b.area_attack(drake, breath, (me.x, me.y))
    assert not next(o for o in b.attack_options(drake) if o.extra.get("id") == "fire_breath").available
    roar = next(o for o in b.attack_options(drake) if o.extra.get("id") == "roar")
    b._attack(drake, roar, me)
    assert not next(o for o in b.attack_options(drake) if o.extra.get("id") == "roar").available


def test_legendary_resistance_turns_failed_saves_twice_a_day(tables):
    b, me, drake = fight(tables)
    results = [b._save(drake, "int", 40) for _ in range(3)]
    assert results == [True, True, False]


def test_legendary_actions_strike_after_another_creatures_turn(tables):
    b, me, drake = fight(tables, gap=2)
    me.char.hp = me.char.max_hp = 500
    b.order = [me.id, drake.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    b.end_turn()
    assert [e for e in b.events if e["kind"] == "attack" and e["by"] == drake.id]  # its tail, out of turn
    assert drake.creature.uses["legendary_actions"] == 1
    b._start_of_turn(drake)
    assert drake.creature.uses["legendary_actions"] == 2  # back at the start of its own turn


def test_spellcasting_at_will_and_per_day(tables):
    b, me, drake = fight(tables, gap=4)
    b.order = [drake.id, me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(drake)
    assert {"fire_bolt", "command"} <= set(b.creature_spells(drake))
    assert b.creature_cast(drake, "command", me)
    drake.action, drake.cast_action_spell = 1, False
    assert "command" not in b.creature_spells(drake) and "fire_bolt" in b.creature_spells(drake)
