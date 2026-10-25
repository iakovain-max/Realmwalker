"""The finale in full, second half (Expansion 6 E.5, docs/ADVENTURES.md §5.8 and §8.6): every finale key of the one
list, the new ones in real fights (a rival band coming on its round, the party blessed, a lieutenant kept away, the
rite finished over the body), the retreat and what it costs, and defeat as content (taken alive, the cells, the gear
in a locked chest, the escape step)."""

import pytest

from realmwalker.game import fight, story
from realmwalker.game.story import defeat, finale
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.world import threats
from tests.test_finale_arenas import _den, _fight, made, tables  # noqa: F401

pytestmark = pytest.mark.story

KEYS_OF_THE_DESIGN = ("no_legendary_resistance", "legendary_resistance", "vulnerable", "frightened", "ally_fights",
                      "rival_arrives", "minions", "surprise", "party_buff", "no_escape", "no_phase_two",
                      "rite_allowed", "lieutenant_absent")


def _kill(b, f):
    b._hit(None, f, f.hp + 50, "force", crit=False, weapon="force")


def _fell_party(b):
    for f in b.side(PARTY):
        if f.active:
            b._hit(None, f, f.hp + 3, "force", crit=False, weapon="force")
    b._check_end()


def test_every_key_of_the_design_is_known():
    for k in KEYS_OF_THE_DESIGN:
        assert k in finale.KEYS, k


def test_the_rival_band_comes_on_its_round(made, tables):
    from tools.arena import run

    game, adv, band = _den(made, tables, "beast", arena="")
    b, boss = _fight(game, adv, band)
    line = finale.KEYS["rival_arrives"](b, game, adv, boss, "2")
    assert line
    before = len([f for f in b.side(PARTY) if f.bond and f.bond.get("kind") == "story_ally"])
    hooks = list(b.round_hooks)
    for hook in hooks:  # (round 1: not yet)
        hook(b)
    assert len([f for f in b.side(PARTY) if f.bond and f.bond.get("kind") == "story_ally"]) == before
    b.round = 2
    for hook in hooks:  # (the battle runs these as each round begins)
        hook(b)
        hook(b)  # (once only)
    after = [f for f in b.side(PARTY) if f.bond and f.bond.get("kind") == "story_ally"]
    assert len(after) == before + 2 and all(f.auto for f in after), "two of them, fighting on their own"
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    assert b.outcome is not None


def test_the_party_blessed_by_its_key(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="")
    b, boss = _fight(game, adv, band)
    assert finale.KEYS["party_buff"](b, game, adv, boss, "bless")
    for f in b.side(PARTY):
        assert any(bf.get("attack_die") == "1d4" for bf in f.buffs)


def test_a_lieutenant_kept_away_is_not_in_the_fight(made, tables):
    game, adv, band = _den(made, tables, "outlaw", arena="", keys=["inside"])
    if len(band.creatures) < 2:
        pytest.skip("the captain alone")
    right_hand = band.creatures[1]
    right_hand.story = {"adv": adv["id"], "role": "raiders"}
    b, boss = _fight(game, adv, band)
    assert all(f.creature is not right_hand for f in b.fighters), "the Right Hand is off on an errand"
    assert right_hand not in band.creatures


def test_the_rite_finished_over_its_body(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="", keys=["anchor", "name"])
    ch = story.chapter(adv)
    rite = next((st for st in ch["steps"] if st["kind"] == "rite"), None)
    if rite is None:
        pytest.skip("no rite in this tale's last chapter")
    b, boss = _fight(game, adv, band)
    assert b.__dict__.get("rite_allowed") == adv["id"]
    assert boss.cdef.get("legendary_resistance") is None, "the anchor held"
    assert any("immune" in bf for f in b.side(PARTY) for bf in f.buffs), "its name spoken: no fear"
    for f in list(b.side(FOE)):
        if f.active:
            _kill(b, f)
    b._check_end()
    assert b.outcome == "victory"
    fight.finish_battle(game)
    assert rite["state"] == "done" and "laid" in adv["flags"]
    assert adv["state"] == "won" and adv["ending"] == next(e["id"] for e in tables.adventures["blueprints"]["risen"]
                                                           ["endings"] if e.get("if") == ["flag:laid"])


def test_the_retreat_costs_and_the_tale_goes_on(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="", keys=["ally"])
    t = threats.records(game.world)[adv["threat"]]
    t["scheme"]["next"] = 10 ** 6
    b, boss = _fight(game, adv, band)
    b._hit(None, boss, boss.hp // 2, "force", crit=False, weapon="force")
    assert boss.creature.hp < boss.creature.max_hp
    attention = int(adv.get("attention", 0))
    for f in b.side(PARTY):
        if f.active:
            f.state = "fled"
    b._check_end()
    assert b.outcome == "fled"
    fight.finish_battle(game)
    assert adv["state"] == "active" and adv["retreats"] == 1
    assert boss.creature.hp == boss.creature.max_hp, "whole again when you come back"
    assert t["scheme"]["next"] < 10 ** 6, "its scheme comes on"
    assert int(adv.get("attention", 0)) >= attention
    assert any(st["kind"] == "finale" and st["state"] == "open" for st in story.open_steps(adv))


def test_taken_alive_at_the_end_you_wake_in_its_cells(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="")
    t = story.threat_of(game, adv)
    t["villain"]["temper"] = "proud"
    if not defeat.keeps_prisoners(game, adv):
        pytest.skip("the villain is no person here")
    leader = game.party[0]
    weapons = [it for it in leader.inventory if tables.items.category(it) in defeat.TAKE]
    leader.money = 37
    b, boss = _fight(game, adv, band)
    _fell_party(b)
    assert b.outcome == "defeat"
    after = fight.finish_battle(game)
    assert after.outcome == "taken" and game.over is None
    assert all(c.alive and c.hp >= 1 for c in game.party)
    assert not any(tables.items.category(it) in defeat.TAKE for it in leader.inventory) and leader.money == 0
    lm = game.local
    chests = [(xy, f) for xy, f in lm.features.items() if f.get("story") == adv["id"]]
    if weapons:
        assert chests and chests[0][1]["locked"] > 0
        assert len(chests[0][1]["contents"]["items"]) >= len(weapons) and chests[0][1]["contents"]["money"] == 37
    assert (game.player.lx, game.player.ly) != (band.x, band.y)
    esc = next(st for st in story.open_steps(adv) if st["kind"] == "escape")
    assert esc["optional"] and adv["taken_alive"]
    assert any(st["kind"] == "finale" and st["state"] == "open" for st in story.open_steps(adv)), "the end still waits"
    game.player.local_key = None
    defeat.on_leave(game)
    assert esc["state"] == "done", "out of its hands"


def test_a_beast_never_takes_you_alive(made, tables):
    game, adv, band = _den(made, tables, "beast", arena="")
    assert not defeat.keeps_prisoners(game, adv)
