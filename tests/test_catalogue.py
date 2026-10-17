"""The spell catalogue (Expansion 3 part D): every spell it brings is cast in a real fight, does what its data says
without breaking the battle, is worth something to the Auto where it should be, and its follow-up (a Witch Bolt's
later bolts, moving a Moonbeam) can be cast while it is held."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY, Battle, Env, again_spell
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import estimates
from realmwalker.rules.inventory import add_item, equip
from realmwalker.rules.progression import award_xp
from realmwalker.world.tables import Tables

PACK = "demigods_magics"


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def _ids(data_dir="data"):
    from pathlib import Path

    from realmwalker.data.registry import DataRegistry

    d, _ = DataRegistry.load(Path(data_dir))
    spells = d.get("spells.json")["spells"]
    return sorted(sid for sid in spells if not sid.startswith("_") and d.origin("spells", sid, "spells") == PACK
                  and not spells[sid].get("minutes") and not spells[sid].get("road_only"))  # (Part E's are cast
    # outside a fight: tests/test_spells_outside.py)


try:
    SPELLS = _ids()
except Exception:  # (the data is checked by its own tests)
    SPELLS = []


def caster(tables, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("cleric")
    b.set_background("acolyte")
    c = b.build()
    award_xp(c, 14000, tables, RNG(seed), auto=True)  # level 6: slots to level 3
    c.hp = c.max_hp - 8  # (a little hurt: a healing spell on oneself is worth something)
    staff = add_item(c, tables.items, "quarterstaff")
    equip(c, tables.items, staff.uid, "main_hand")
    return c


def friend(tables, seed=2):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    c = b.build()
    c.hp = max(1, c.max_hp - 5)
    return c


def scene(tables, seed=1):
    rng = RNG(seed, "foes")
    foes = [spawn(tables, d, rng, i + 1) for i, d in enumerate(("bandit", "bandit", "wolf"))]
    b = Battle(tables, [caster(tables), friend(tables)], foes, Env(), RNG(seed, "battle"),
               spots={0: (3, 4), 1: (1, 6), 2: (4, 4), 3: (8, 4), 4: (6, 2)})  # (a foe beside the caster, the friend apart)
    b.start("Test fight.")
    return b


def my_turn(b, f):
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(f)


def aim(b, f, sid):
    """Where a spell would be aimed in this scene: at the nearest foe, at the hurt friend, at a foe's square."""
    sp = b.t.spells[sid]
    mode = sp["target"]
    foes = sorted(b.enemies_of(f), key=lambda e: b.gap(f, e))
    if mode in ("enemy", "bound"):
        ts = b.spell_targets(f, sid)
        return (min(ts, key=lambda e: b.gap(f, e)) if ts else None), None
    if mode in ("ally", "downed_ally", "dead_ally"):
        ts = b.spell_targets(f, sid)
        return (min(ts, key=lambda x: x.hp / max(1, x.max_hp)) if ts else None), None
    if mode in ("point", "direction"):
        pts = b.spell_points(f, sid)
        if not pts:
            return None, None
        e = foes[0]
        return None, min(pts, key=lambda p: (abs(p[0] - e.x) + abs(p[1] - e.y), p))
    return None, None


def problems(b) -> list[str]:
    out = []
    for x in b.fighters:
        if min(x.action, x.bonus, x.move_left) < 0:
            out.append(f"{x.name}: action {x.action}, bonus {x.bonus}, move {x.move_left}")
        if not 0 <= x.hp <= x.max_hp or x.temp_hp < 0:
            out.append(f"{x.name}: {x.hp} of {x.max_hp} hit points (+{x.temp_hp})")
    return out


def test_the_catalogue_is_in_the_game(tables):
    assert len(SPELLS) >= 130, "the first two waves (cantrips to level 5) bring the battle spells"
    for sid in SPELLS:
        sp = tables.spells[sid]
        assert sp.get("fx"), f"{sid} has no look"
        assert sp["text"] and len(sp["text"]) <= 300, sid


@pytest.mark.parametrize("sid", SPELLS)
def test_each_spell_is_cast_in_a_real_fight(tables, sid):
    b = scene(tables)
    f = b.side(PARTY)[0]
    my_turn(b, f)
    sp = tables.spells[sid]
    target, point = aim(b, f, sid)
    if sp["target"] in ("enemy", "ally", "downed_ally", "bound") and target is None:
        pytest.skip(f"{sid}: nobody to aim it at in this scene")
    level = max(1, sp["level"])
    b.cast(f, sid, sp, target, point, up=0, mod=3, dc=14, bonus=6, mult=2, level=level if sp["level"] else 0)
    assert not problems(b), problems(b)
    again = again_spell(f, tables)
    if again is not None and again.startswith(sid) and not (tables.spells[again]["target"] == "point"
                                                          and not b.spell_points(f, again)):
        # (a follow-up with nowhere to aim it here is not offered: Tree Stride on a field without trees)
        f.action = f.bonus = 1
        assert again in [s for s, ok, _ in b.spell_options(f) if ok], f"{sid}'s follow-up is not offered"
        t2, p2 = aim(b, f, again)
        if tables.spells[again]["target"] in ("enemy", "bound", "ally") and t2 is None:
            pass
        else:
            assert b.do_cast(f, again, t2, point=p2), f"{sid}'s follow-up could not be cast"
    # The fight goes on to its end with everything the spell left on the field.
    for x in b.fighters:
        if x.side == PARTY:
            x.auto = True
    for _ in range(3000):
        if b.outcome is not None:
            break
        b.step()
        assert not problems(b), problems(b)
    assert b.outcome is not None


# Spells the Auto has no use for in this scene (a reason each).
NO_USE: dict[str, str] = {
    "arms_of_hadar": "it catches everyone around the caster, and a friend stands within ten feet",
    "expeditious_retreat": "nobody here is hurt badly enough to want to run",
    "protection_from_evil_and_good": "no aberration, celestial, elemental, fey, fiend or undead here",
    "silence": "no foe here casts spells",
    "dimension_door": "the caster is barely hurt, and every square near a foe is beside another foe",
    "dispel_magic": "no spell is on anyone here",
    "dispel_evil_and_good": "no celestial, elemental, fey, fiend or undead here",
    "greater_restoration": "nobody here is charmed, petrified or cursed",
    "circle_of_death": "its 60-foot sphere takes in the caster and a friend wherever it falls on this small field",
    "otilukes_freezing_sphere": "its 60-foot sphere takes in the caster and a friend wherever it falls on this small field",
    "true_seeing": "no foe here is invisible, hidden or in magical darkness",
    "detect_thoughts": "no foe here is invisible or hidden (tests/test_spells_road3.py weighs it against an invisible one)",
    "reverse_gravity": "its 50-foot cylinder lifts the caster and a friend too wherever it falls on this small field",
    "antimagic_field": "no foe here casts spells, and the caster's own magic would be lost",
    "sunburst": "its 60-foot sphere takes in the caster and a friend wherever it falls on this small field",
    "meteor_swarm": "its 40-foot spheres take in the caster and a friend wherever they fall on this small field",
    # Part E.2: the body's spells, worth casting only where the field asks for them (tests/test_spells_outside.py
    # puts each one where it is: the dark, the invisible, water, a fall, trees)
    "light": "the field is lit",
    "dancing_lights": "the field is lit",
    "daylight": "the field is lit, and no foe has laid magical darkness",
    "darkvision": "the field is lit",
    "see_invisibility": "no foe here is invisible",
    "jump": "nothing here to leap over",
    "longstrider": "everyone is within a walk of the fight",
    "feather_fall": "cast by itself as someone falls",
    "spider_climb": "nothing here to climb",
    "water_walk": "no deep water here",
    "alter_self": "no deep water here (on the road it is a disguise)",
    "enhance_ability": "nobody here grapples or shoves",
    "pass_without_trace": "nobody here is hiding",
    "tree_stride": "no trees here",
    "gaseous_form": "nobody here is about to fall (as mist a fighter cannot strike)",
    "feign_death": "nobody here is about to fall (feigning, a fighter is out of the fight)",
}


@pytest.mark.parametrize("sid", SPELLS)
def test_the_auto_sees_the_worth_of_each_spell(tables, sid):
    if sid in NO_USE:
        pytest.skip(NO_USE[sid])
    b = scene(tables)
    f = b.side(PARTY)[0]
    my_turn(b, f)
    sp = tables.spells[sid]
    if sp["target"] == "bound":
        pytest.skip("a follow-up")
    best = 0.0
    if sp["target"] in ("enemy", "ally", "downed_ally", "dead_ally"):
        for t in b.spell_targets(f, sid):
            best = max(best, estimates.spell_value(b, f, sid, target=t).total(care=4.0))
    elif sp["target"] in ("point", "direction"):
        for e in b.enemies_of(f):
            for p in [(e.x, e.y)] + [(e.x + dx, e.y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]:
                if p in b.spell_points(f, sid):
                    best = max(best, estimates.spell_value(b, f, sid, point=p).total(care=4.0))
    else:
        best = estimates.spell_value(b, f, sid).total(care=4.0)
    assert best > 0.5, f"the Auto would never cast {sid} here"
