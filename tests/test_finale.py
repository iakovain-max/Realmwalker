"""The finale, first form (Expansion 6 A.8, docs/ADVENTURES.md §5.8): the boss's card holds the fight until the
player says Fight; the boss template (hit points, Legendary Resistance, legendary actions, the frenzy at half its
hit points) and the keys found (its weakness with the means, surprise, the ally) take hold in a real fight, played
out on Auto to its end."""

import copy

import pytest

from realmwalker.game import dungeon, story
from realmwalker.game.state import new_game
from realmwalker.game.story import forge
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.engine.handlers import bosses
from realmwalker.world import threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

pytestmark = pytest.mark.story


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Forgeland", 77, "medium"), tables)


def _at_the_den(made, tables, keys=()):
    w = copy.deepcopy(made)
    t = next((t for t in threats.records(w).values() if t["kind"] == "beast" and t["state"] != "ended"), None)
    if t is None:
        pytest.skip("no beast")
    game = new_game(w, tables)
    game.survival = False
    adv = forge.make(game, t)
    adv["chapter"] = len(adv["chapters"]) - 1
    adv["keys"] = list(keys)
    site = w.sites[adv["places"]["home"]["site"]]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    depth = dungeon.gen.depth_for(w, site)
    dungeon.descend(game, 1)
    while int(game.local.meta.get("level", 1)) < depth:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)
    band = next(a for a in game.local.actors if a.creatures and getattr(a.creatures[0], "story", None))
    from realmwalker.game.people import prepare_town

    prepare_town(game, w.settlements[adv["places"]["town"]["settlement"]])  # (the ally is someone of the town)
    for c in game.party:
        c.level = max(c.level, adv["target_level"])
    return game, adv, band


def test_walking_into_the_boss_shows_its_card_first(made, tables):
    game, adv, band = _at_the_den(made, tables)
    assert story.hold_for_finale(game, band)
    assert game.finale == {"adv": adv["id"], "actor": band.id} and game.busy
    card = story.finale_card(game)
    assert card["name"] == band.creatures[0].name and card["first"]
    assert all(not ok for _, ok in card["known"]), "nothing found yet: every key a question mark"
    game.finale = None
    assert not game.busy


def test_the_boss_template_and_the_keys_in_a_real_fight(made, tables):
    from tools.arena import run

    keys = ["weakness", "means", "quiet", "ally"]
    game, adv, band = _at_the_den(made, tables, keys)
    base_hp = band.creatures[0].max_hp
    game.finale = {"adv": adv["id"], "actor": band.id}
    story.fight_finale(game)
    b = game.battle
    assert b is not None and game.finale is None
    boss = next(f for f in b.side(FOE) if f.creature is not None and (f.creature.story or {}).get("role") == "villain")
    assert boss.max_hp > base_hp and boss.cdef.get("legendary_resistance") and boss.cdef.get("legendary")
    assert boss.cdef.get("boss_phase")
    weak = adv["hidden"]["weakness"]["weakness"]
    if weak.endswith("_fire") and "fire" in str(game.tables.villains["weaknesses"]):
        assert "fire" in boss.cdef.get("vulnerable", []) or "frightened" in boss.conditions
    assert b.env.surprised == FOE, "it did not know you had come"
    assert any(f.bond and f.bond.get("kind") == "story_ally" for f in b.side(PARTY)), "the ally fights beside you"
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    assert b.outcome is not None


def test_the_frenzy_comes_at_half_its_hit_points(made, tables):
    game, adv, band = _at_the_den(made, tables)
    game.finale = {"adv": adv["id"], "actor": band.id}
    story.fight_finale(game)
    b = game.battle
    boss = next(f for f in b.side(FOE) if f.creature is not None and (f.creature.story or {}).get("role") == "villain")
    boss.hp = boss.max_hp // 2 - 1
    bosses.after_damage(b, boss)
    assert boss.__dict__.get("phased") and boss.cdef["morale"] == "fanatic"
    assert any(bf.get("id") == "frenzy" for bf in boss.buffs)
    assert any(e.get("kind") == "phase" for e in b.events)


def test_met_before_its_den_it_breaks_off_when_hurt(made, tables):
    """Before its finale the beast fights as itself (no template) and bolts at half its hit points; at its den it
    never runs."""
    from realmwalker.game.story import finale as finmod
    from tools.arena import setup

    game, adv, band = _at_the_den(made, tables)
    adv["chapter"] = 1  # (the hunt's price: the bait or the trail)
    b = setup(tables, band.creatures[0].def_id, "close", 1)
    boss = b.side(FOE)[0]
    boss.creature.story = {"adv": adv["id"], "role": "villain"}
    base = boss.max_hp
    finmod.prepare(b, game)
    assert boss.max_hp == base and not boss.cdef.get("legendary"), "not the boss yet"
    assert boss.cdef["boss_phase"]["kind"] == "breaks_off"
    boss.hp = boss.max_hp // 2 - 1
    bosses.after_damage(b, boss)
    assert boss.state == "fled"
    result = b.result()
    assert boss.creature in result.fled
    adv["chapter"] = len(adv["chapters"]) - 1
    b2 = setup(tables, band.creatures[0].def_id, "close", 2)
    boss2 = b2.side(FOE)[0]
    boss2.creature.story = {"adv": adv["id"], "role": "villain"}
    finmod.prepare(b2, game)
    assert boss2.cdef["morale"] == "fanatic" and boss2.cdef.get("legendary"), "at its den it stands and fights"


def test_a_beast_left_helpless_at_the_end_is_killed_where_it_lies(made, tables):
    from types import SimpleNamespace

    game, adv, band = _at_the_den(made, tables)
    beast = band.creatures[0]
    result = SimpleNamespace(outcome="victory", dead=[], captives=[beast], fled=[])
    lines = story.finish_off(game, result)
    assert lines and beast in result.dead and not result.captives and not beast.alive
    story.on_battle(game, result)
    assert adv["ending"] == "slain"
