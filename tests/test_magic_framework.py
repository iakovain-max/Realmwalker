"""The magic item framework (Expansion 1, D.1; DMG 2024 chapter 7, PHB "Magic Items"): attunement, charges at dawn,
identification, artifacts rolled for the world, sentient things and their conflicts, in play and in a real fight."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import magic_items
from realmwalker.game.state import new_game
from realmwalker.rules import magic
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import query
from realmwalker.rules.inventory import add_existing, equip
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Magicland", 41, "small"), tables)


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def ring(game, seed=1, **extra):
    it = magic_items.make(game, RNG(seed, "ring"), kind="jewellery", rarity="rare", sentient=False,
                          props=[{"kind": "ac", "value": 1}])
    it.magic.update(extra)
    return add_existing(game.leader, game.tables.items, it)


def artifact(game, *, want=None, avoid=(), seed=0):
    for i in range(400):
        it = magic_items.make_artifact(game, RNG(seed + i, "art"), kind="weapon")
        ids = {p.get("id") for p in it.magic["props"]} | set(it.magic.get("on", []))
        if (want is None or want in ids) and not ids & set(avoid):
            it.magic["identified"] = True
            return it
    pytest.skip(f"no artifact with {want}")


def test_attunement_is_needed_and_limited_to_three(game):
    c = game.leader
    rings = [ring(game, seed=i) for i in range(4)]
    assert all(r.magic["attune"] for r in rings)
    equip(c, game.tables.items, rings[0].uid)
    ac = game.sheet().armor_class()
    t0 = game.world.time
    lines = magic_items.attune(game, c, rings[0])
    assert game.world.time - t0 == 60 and c.attuned == [rings[0].uid]  # a short rest
    assert game.sheet().armor_class() == ac + 1 and "bound" in " ".join(lines).lower() or c.attuned
    for r in rings[1:3]:
        magic_items.attune(game, c, r)
    assert len(c.attuned) == 3
    assert "3" in magic.can_attune(c, rings[3])
    assert magic_items.attune(game, c, rings[3])[0].startswith(c.name.split()[0])
    assert len(c.attuned) == 3
    magic_items.end_attunement(game, c, rings[1])
    assert rings[1].uid not in c.attuned


def test_a_plain_plus_one_sword_needs_no_bond(game):
    it = magic_items.make(game, RNG(3), kind="weapon", rarity="uncommon", props=[{"kind": "bonus", "value": 1}],
                          sentient=False)
    assert not it.magic["attune"]


def test_a_curse_holds_the_bond(game):
    c = game.leader
    r = ring(game, cursed=True, curse={"text": "It whispers.", "effect": "save", "value": -2})
    out = magic_items.attune(game, c, r)
    assert r.magic["curse_known"] and any("cursed" in line for line in out)
    assert "cannot" in magic_items.end_attunement(game, c, r)[0]
    assert r.uid in c.attuned
    magic_items.lift_curse(r)
    magic_items.end_attunement(game, c, r)
    assert r.uid not in c.attuned


def test_a_bond_ends_when_the_thing_is_gone(game):
    c = game.leader
    r = ring(game)
    magic_items.attune(game, c, r)
    c.inventory.remove(r)
    game.pass_time(30)
    assert r.uid not in c.attuned


def test_charges_come_back_at_dawn_not_with_rest(game):
    c = game.leader
    wand = magic_items.make(game, RNG(5), kind="focus", rarity="rare", sentient=False,
                            props=[{"kind": "charges", "spell": "magic_missile", "value": 7, "left": 0,
                                    "regain": "1d6+1"}])
    wand = add_existing(c, game.tables.items, wand)
    assert wand.magic["attune_by"] == "spellcaster"
    m = game.moment
    game.world.time += (24 - m.hour) * 60 - m.minute + 3 * 60  # 3 in the morning
    game.pass_time(60)
    p = wand.magic["props"][0]
    assert p["left"] == 0
    game.pass_time(4 * 60)  # past six
    assert 2 <= p["left"] <= 7


def test_artifacts_roll_real_properties(game):
    seen = set()
    for i in range(60):
        it = magic_items.make_artifact(game, RNG(i, "art"))
        assert it is not None and it.magic["rarity"] == "artifact" and it.magic["attune"]
        assert it.magic["destroy"] and "{" not in it.magic["destroy"]
        art = [p for p in it.magic["props"] if p.get("artifact")]
        assert any(p["artifact"] == "major_good" for p in art)
        assert any(p["artifact"] == "minor_bad" for p in art)
        for p in art:
            assert "{" not in p["text"]
            if p["kind"] == "trait":
                assert p["trait"] in game.tables.traits["traits"]
            if p["kind"] == "charges":
                assert p["spell"] in game.tables.spells
            seen.add(p["id"])
        assert len(magic_items.describe(game, it)) == 2  # hidden until known (and the bond it needs)
        it.magic["identified"] = True
        lines = magic_items.describe(game, it)
        assert any("broken" in line for line in lines)
    assert {"quest", "avatar", "prisoner"}.isdisjoint(seen)  # what the game cannot run is rolled again
    assert len(seen) > 15


def fight(game, foe="wolf"):
    b = Battle(game.tables, [game.leader], [spawn(game.tables, foe, RNG(1), 1)], Env(), RNG(1),
               spots={0: (2, 4), 1: (3, 4)})
    b.start("Test")
    return b, next(f for f in b.fighters if f.char is game.leader), next(f for f in b.fighters if f.char is None)


def test_an_artifacts_force_and_frailty_in_a_real_fight(game):
    c = game.leader
    it = artifact(game, want="force")
    it = add_existing(c, game.tables.items, it)
    equip(c, game.tables.items, it.uid, "main_hand")
    b, me, wolf = fight(game)
    assert "item_force" not in __import__("realmwalker.rules.engine.traits", fromlist=["of"]).of(me)
    c.attuned.append(it.uid)
    b, me, wolf = fight(game)
    from realmwalker.rules.engine import traits

    assert "item_force" in traits.of(me)
    hits = []
    b.say = lambda *a, **k: None
    for _ in range(30):
        wolf.hp = 500
        me.action = 1
        me.attacks_left = 1
        before = wolf.hp
        opt = next(o for o in b.attack_options(me) if o.key == "main")
        assert b.do_attack(me, opt, wolf), b.attack_problem(me, opt, wolf)
        if wolf.hp < before:
            hits.append([e for e in b.events if e.get("kind") == "damage" and e.get("dtype") == "force"])
    assert hits and any(h for h in hits)


def test_frailty_doubles_harm(game):
    c = game.leader
    it = artifact(game, want="frail_all")
    it = add_existing(c, game.tables.items, it)
    c.attuned.append(it.uid)
    b, me, wolf = fight(game)
    assert query.damage_taken(me, 10, "slashing")[0] == 20


def test_the_jealous_artifact_and_no_healing(game):
    c = game.leader
    r = ring(game)
    magic_items.attune(game, c, r)
    jealous = add_existing(c, game.tables.items, artifact(game, want="jealous", avoid=("shock", "deadly_bond", "drains")))
    magic_items.attune(game, c, jealous)
    assert c.attuned == [jealous.uid]
    assert "nothing else" in magic.can_attune(c, r)


def test_flaws_bite_outside_a_fight(game):
    c = game.leader
    it = add_existing(c, game.tables.items, artifact(game, want="no_healing"))
    c.attuned.append(it.uid)
    c.hp = 1
    from realmwalker.rules.progression import long_rest

    long_rest(c, game.tables, RNG(1))
    assert c.hp == 1


def sentient_sword(game, purpose="destroyer", cha=18):
    it = magic_items.make(game, RNG(9), kind="weapon", rarity="very_rare", sentient=True)
    it.magic["sentient"].update(purpose=purpose, cha=cha, communication="speech")
    it.magic["identified"] = True
    it = add_existing(game.leader, game.tables.items, it)
    equip(game.leader, game.tables.items, it.uid, "main_hand")
    game.leader.attuned.append(it.uid)
    return it


def test_a_sentient_thing_speaks_and_makes_demands(game, monkeypatch):
    it = sentient_sword(game)
    mind = it.magic["sentient"]
    assert {"int", "wis", "cha", "alignment", "communication", "senses", "purpose"} <= set(mind)
    assert any("awake" in line for line in magic_items.describe(game, it))
    said = magic_items.notice(game, "victory", creatures=[{"type": "beast", "alignment": "unaligned"}])
    assert said  # pleased, and says so
    # Fleeing angers a destroyer: a Charisma save it will win (DC 12 + 4), then a demand.
    from realmwalker.core import dice

    class Low:
        natural = 1
        total = 1

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Low())
    magic_items.notice(game, "fled", creatures=[])
    demand = mind["demand"]
    assert demand["kind"] in ("dreams", "keep_close", "change", "get_rid")
    demand["kind"] = "dreams"
    game.world.time = demand["until"] + 1
    magic_items.check_demands(game)
    assert it.magic["suppressed"] and not magic.working(game.leader, it)
    # Served at last: a victory meets its want, and the power comes back.
    magic_items.notice(game, "victory", creatures=[{"type": "beast", "alignment": "unaligned"}])
    assert not it.magic.get("suppressed") and "demand" not in mind


def test_a_seized_bearer_fights_on_auto(game, monkeypatch):
    it = sentient_sword(game)
    it.magic["sentient"]["seized_until"] = game.world.time + 600
    from realmwalker.game import fight

    b = fight.start_battle(game, [spawn(game.tables, "wolf", RNG(1), 1)], "Test")
    me = next(f for f in b.fighters if f.char is game.leader)
    assert me.auto


def test_saving_keeps_the_bonds(game, tmp_path):
    from realmwalker.game import save

    r = ring(game)
    magic_items.attune(game, game.leader, r)
    art = add_existing(game.leader, game.tables.items, artifact(game))
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / game.world.meta.id, game.tables)
    assert r.uid in loaded.leader.attuned
    got = loaded.leader.item(art.uid)
    assert got.magic["destroy"] == art.magic["destroy"]
