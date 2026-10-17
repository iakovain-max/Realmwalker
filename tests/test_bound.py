"""The bound (Expansion 3 F.5): Planar Ally (the god's spirit for a price by the term, half for its church; in a real
fight on its own, played by the Auto; healed at a long rest; gone home when its time ends or its master dies; waiting
outside a town), Planar Binding (a captive goblin: the save, the jewel, the term by the slot, fighting for the party,
running off at the end; a spirit: refused without a Magic Circle turned inward, bound longer with one) and the
circle's two directions."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import servants, warding
from realmwalker.rules import progression, tactics
from realmwalker.rules import servants as rules
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE
from realmwalker.rules.engine import check
from realmwalker.rules.inventory import add_item
from realmwalker.world import factions as fx
from tests.test_servants import battle, cast, game_with, hero, in_the_wild, subject
from tests.test_wave4 import my_turn, sturdy

F5 = ("planar_ally", "planar_binding", "magic_circle")


@pytest.fixture(scope="module")
def tables(data):
    from realmwalker.world.tables import Tables

    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + list(F5))) if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


def cleric(tables, gp=200000):
    c = hero(tables, "cleric")
    c.money = gp * 100
    return c


def spirit(game, c, slot=6, term="a day"):
    cast(game, c, "planar_ally", subject(game, c, "planar_ally", term), slot)
    return next(r for r in rules.records(c) if r["spell"] == "planar_ally")


def captive(game, cid="goblin", name="the goblin"):
    game.renown.flags.setdefault("captives", []).append(
        {"def_id": cid, "name": name, "reward": 400, "since": game.world.time, "faction": -1})


# ---------------------------------------------------------------------------- the data
def test_the_spells_and_every_gods_spirit_are_known(tables):
    for sid in ("planar_ally", "planar_binding"):
        assert sp.road_use(tables, sid) == "bind" and f"scroll_{sid}" in tables.items
    assert tables.spells["planar_ally"]["level"] == 6 and tables.spells["planar_ally"]["classes"] == ["cleric"]
    assert tables.spells["planar_binding"]["material"]["consumed"]
    assert not check.problems(tables)
    for fid, faith in tables.factions["faiths"].items():
        ally = faith["ally"]
        assert ally["form"] in tables.creatures[ally["creature"]]["summon"]["forms"], fid


# ---------------------------------------------------------------------------- Planar Ally
def test_planar_ally_sends_the_gods_spirit_for_the_price_of_its_term(world, tables):
    c = cleric(tables)
    game = game_with(world, tables, c)
    in_the_wild(game)
    cid, form = servants.ally_kind(game, c)
    assert (cid, form) == ("celestial_spirit", "defender")  # (a human of the heartland: Solun's)
    before = c.money
    rec = spirit(game, c, 7)
    assert before - c.money == (10000 * 100) // (2 if servants.church_member(game, c) else 1)
    assert (rec["cid"], rec["form"], rec["level"], rec["word"], rec["heals"]) == (cid, form, 7, False, True)
    assert rec["name"].endswith("of Solun") and rec["picture"] == "celestial_defender"
    assert rec["until"] == pytest.approx(game.world.time + rules.DAY, abs=1)
    assert rec["max_hp"] == 40 + 10 * 2  # (40 at level 5, 10 a level above)


def test_no_money_no_spirit_and_its_church_pays_half(world, tables):
    c = cleric(tables, gp=500)
    game = game_with(world, tables, c)
    in_the_wild(game)
    hour = subject(game, c, "planar_ally", "an hour")
    assert "the price is 1000 gp" in magic_problem(game, c, "planar_ally", hour)
    church = fx.church_of(game.world, servants.faith_of(game, c)[0])
    assert church is not None
    game.renown.members[church.id] = 0
    assert servants.ally_price(game, c, 1000) == 50000
    assert magic_problem(game, c, "planar_ally", subject(game, c, "planar_ally", "an hour")) is None
    spirit(game, c, 6, "an hour")
    assert c.money == 0


def magic_problem(game, c, sid, target):
    from realmwalker.game import magic

    return magic.road_problem(game, c, sid, target)


def test_the_spirit_fights_on_its_own_at_its_slot_and_the_auto_plays_it(tables):
    c = cleric(tables)
    top = rules.spirit_max_hp(tables, "celestial_spirit", "defender", 6)
    rules.add(c, tables, "celestial_spirit", "planar_ally", until=10 ** 6, now=0, word=False, name="spirit of Solun",
              max_hp=top, form="defender", level=6, picture="celestial_defender", heals=True)
    b = battle(tables, [c], ["bandit"], {0: (2, 4), 1: (5, 4)})
    me = b.fighters[0]
    sp_ = next(f for f in b.fighters if f.bond is not None and f.bond["kind"] == "servant")
    assert sp_.cdef["ac"] == 11 + 6 + 2 and sp_.hp == top == 50 and sp_.bond["picture"] == "celestial_defender"
    assert sp_.cdef["attacks"][0]["bonus"] == sp.attack_bonus(_sheet(tables, c), tables)
    sturdy(*b.side(FOE))
    b.order = [sp_.id] + [x for x in b.order if x != sp_.id]
    b.turn, b.turn_started = 0, False
    b.step()
    assert not sp_.dodging and sp_.action == 1  # (no word needed)
    sp_.x, sp_.y = 4, 4
    tactics.take_turn(b, sp_)
    assert [e for e in b.events if e.get("kind") == "attack" and e.get("by") == sp_.id]
    assert me.state != "dead"


def _sheet(tables, c):
    from realmwalker.rules.character import Sheet

    return Sheet(c, tables)


def test_a_spirit_heals_at_a_long_rest_and_the_dead_do_not(tables):
    c = cleric(tables)
    rec = rules.add(c, tables, "celestial_spirit", "planar_ally", until=10 ** 6, now=0, word=False, max_hp=50,
                    form="defender", level=6, heals=True, hp=5)
    dead = rules.add(c, tables, "zombie", "animate_dead", until=10 ** 6, now=0, hp=3)
    rec["uses"] = {"celestial_healing_touch": 1}
    progression.long_rest(c, tables, RNG(1))
    assert rec["hp"] == 50 and rec["uses"] == {} and dead["hp"] == 3


def test_its_time_up_the_spirit_goes_home_and_turns_on_nobody(world, tables):
    c = cleric(tables)
    game = game_with(world, tables, c)
    in_the_wild(game)
    rec = spirit(game, c, 6, "an hour")
    game.world.time = rec["until"] - 60
    servants.tick(game)
    assert any("service" in m.text and "two hours" in m.text for m in game.log.messages[-4:])
    game.world.time = rec["until"] + 1
    servants.tick(game)
    assert not rules.records(c) and game.encounter is None
    assert any("served its time" in m.text for m in game.log.messages[-3:])


def test_a_dead_masters_spirit_goes_home_and_none_wait_in_a_town(world, tables):
    from tests.test_spells_road6 import in_town

    c = cleric(tables)
    game = game_with(world, tables, c)
    in_the_wild(game)
    spirit(game, c)
    assert servants.following(game)
    in_town(game)
    assert not servants.following(game)
    servants.died(game, c)
    assert not rules.records(c) and game.encounter is None


def test_a_spirit_reads_with_the_right_article_and_goes_with_a_dismissed_companion(world, tables):
    from realmwalker.game import companions

    c = cleric(tables)
    friend = cleric(tables)
    friend.name = "Brannoc Hale"
    friend.culture = "northmarch"  # (the All-Father of the Ash sends an avenging celestial spirit)
    friend.companion = {"npc": -1}
    game = game_with(world, tables, c, friend)
    in_the_wild(game)
    assert servants.ally_kind(game, friend) == ("celestial_spirit", "avenger")
    words = subject(game, friend, "planar_ally", "a day").name
    assert words.startswith("an avenging celestial spirit")
    out = cast(game, friend, "planar_ally", subject(game, friend, "planar_ally", "a day"), 6)
    assert any("and an avenging" in m for m in out)
    companions.dismiss(game, friend)
    assert not rules.records(friend) and game.encounter is None


# ---------------------------------------------------------------------------- Planar Binding
def test_a_captive_goblin_bound_by_the_slot_fights_for_the_party_and_runs_off_at_the_end(world, tables, monkeypatch):
    c = cleric(tables)
    game = game_with(world, tables, c)
    in_the_wild(game)
    captive(game)
    captive(game, "bandit", "the bandit")  # (a humanoid: no binding reaches it)
    add_item(c, tables.items, "gem_1000")
    subs = servants.binding_subjects(game, c)
    assert [s.kind for s in subs] == ["captive"] and "goblin" in subs[0].name
    monkeypatch.setattr(servants, "_cha_save", lambda *a: False)
    cast(game, c, "planar_binding", subs[0], 7)
    rec = rules.records(c)[0]
    assert (rec["cid"], rec["name"], rec["bound"], rec["word"]) == ("goblin", "goblin", True, False)
    assert rec["until"] == pytest.approx(game.world.time + 30 * rules.DAY, abs=1)
    assert [cap["def_id"] for cap in game.renown.flags["captives"]] == ["bandit"]
    assert not any(it.def_id == "gem_1000" for it in c.inventory)
    b = battle(tables, [c], ["bandit"], {0: (2, 4), 1: (6, 4)})
    gob = next(f for f in b.fighters if f.bond is not None and f.bond["kind"] == "servant")
    assert gob.cdef["name"] == tables.creatures["goblin"]["name"] and gob.side == b.fighters[0].side
    game.world.time = rec["until"] + 1
    servants.tick(game)
    assert not rules.records(c) and game.encounter is None
    assert any("binding on the goblin is over" in m.text for m in game.log.messages[-3:])


def test_a_captive_who_saves_stays_a_captive_and_the_jewel_is_spent(world, tables, monkeypatch):
    c = cleric(tables)
    game = game_with(world, tables, c)
    in_the_wild(game)
    captive(game)
    add_item(c, tables.items, "sapphire")
    monkeypatch.setattr(servants, "_cha_save", lambda *a: True)
    out = cast(game, c, "planar_binding", servants.binding_subjects(game, c)[0], 5)
    assert any("nothing is bound" in m for m in out)
    assert not rules.records(c) and len(game.renown.flags["captives"]) == 1
    assert not any(it.def_id == "sapphire" for it in c.inventory)
    assert magic_problem(game, c, "planar_binding", servants.binding_subjects(game, c)[0]) is not None  # (no jewel)


def test_a_spirit_is_bound_only_in_an_inward_circle_and_then_serves_longer(world, tables, monkeypatch):
    c = cleric(tables)
    friend = cleric(tables)
    friend.name = "Brannoc Hale"
    game = game_with(world, tables, c, friend)
    in_the_wild(game)
    rec = spirit(game, friend, 6, "an hour")
    add_item(c, tables.items, "gem_1000")
    add_item(c, tables.items, "gem_1000")
    add_item(c, tables.items, "silvered_salt")
    target = next(s for s in servants.binding_subjects(game, c) if s.kind == "servant")
    assert "Brannoc" in target.name
    assert "Magic Circle turned inward" in magic_problem(game, c, "planar_binding", target)
    cast(game, c, "magic_circle", subject(game, c, "magic_circle", "inward"))
    assert warding.inward_circle(game) is not None and warding.ward(game, "circle") is None
    monkeypatch.setattr(servants, "_cha_save", lambda *a: False)
    target = next(s for s in servants.binding_subjects(game, c) if s.kind == "servant")
    cast(game, c, "planar_binding", target, 6)
    assert not rules.records(friend)
    mine = rules.records(c)[0]
    assert mine["bound"] and mine["form"] == rec["form"]
    assert mine["until"] == pytest.approx(game.world.time + 10 * rules.DAY, abs=1)
    again = next(s for s in servants.binding_subjects(game, c) if s.kind == "servant")
    assert "again" in again.name
    game.world.time += 120  # (the circle is gone: one already bound needs none)
    assert warding.inward_circle(game) is None
    assert magic_problem(game, c, "planar_binding", again) is None


def test_the_circle_turned_outward_still_wards_the_camp(world, tables):
    c = cleric(tables)
    game = game_with(world, tables, c)
    in_the_wild(game)
    add_item(c, tables.items, "silvered_salt")
    cast(game, c, "magic_circle", subject(game, c, "magic_circle", "outward"))
    assert warding.ward(game, "circle") is not None and warding.inward_circle(game) is None
