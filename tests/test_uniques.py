"""The seven unique companions (after v1, asked for by Anton): hand-made, the same in every world, each found and won
in their own way, each with a gift of their own, and remembered by the world when they leave or die."""

import copy

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import companions as comp
from realmwalker.game import save, uniques
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables

SEVEN = ("osric", "durgin", "tobiah", "wendeline", "grusha", "aelith", "wren")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Sevenfold", 21, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    g.leader.money = 100000
    return g


@pytest.fixture
def lucky(monkeypatch):
    """Every check in conversation succeeds, and every die rolls high."""
    from realmwalker.game import camp

    monkeypatch.setattr(Conversation, "check", lambda self, skill, dc: (True, f"({skill} vs {dc})"))
    monkeypatch.setattr(camp, "check", lambda game, skill, dc, bonus=0, tag="": (True, f"({skill} vs {dc})"))
    monkeypatch.setattr(dice, "d20", lambda rng, **kw: type("R", (), {"natural": 20, "total": 20})())


def visit(game, uid):
    """Walk into the town where they are, and find them."""
    r = uniques.rec(game, uid)
    s = game.world.settlements[r["town"]]
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    npc = uniques.npc_of(game, uid)
    assert npc is not None and npc.flags["unique"] == uid
    return npc


def talk(game, npc):
    npc.met = True
    return Conversation(game, npc)


def choose(game, npc, step):
    conv = talk(game, npc)
    choice = next((c for c in conv.menu() if c.id == "recruit" and c.data.get("step") == step), None)
    assert choice is not None, [c.data for c in conv.menu() if c.id == "recruit"]
    assert choice.enabled, choice.why
    conv.choose(choice)
    return conv


def steps(game, npc):
    return {c.data.get("step"): c for c in talk(game, npc).menu() if c.id == "recruit"}


def joined(game, uid):
    c = uniques.with_party(game, uid)
    assert c is not None, f"{uid} did not join"
    assert comp.bond_of(c) == "unique" and c.companion["wage"] == 0 and c.money == 0
    return c


# ---------------------------------------------------------------------------- the same seven, everywhere
@pytest.mark.parametrize("seed,size", [(21, "medium"), (5, "small"), (99, "large")])
def test_the_seven_are_in_every_world(tables, seed, size):
    w = WorldGenerator(WorldOptions("Anywhere", seed, size), tables).generate()
    game = new_game(w, tables)
    recs = uniques.ensure(game)
    assert set(recs) == set(SEVEN)
    towns = [r["town"] for r in recs.values()]
    assert len(set(towns)) >= 5, "spread about, not all in one town"
    for uid in SEVEN:
        npc = visit(game, uid)
        u = tables.uniques["uniques"][uid]
        assert (npc.name, npc.sex, npc.age, npc.race) == (u["name"], u["sex"], u["age"], u["race"])
        assert npc.profile["appearance"] == uniques.fill(game, uid, u["profile"]["appearance"])
        assert any(n["kind"] == "unique" for n in w.news), "people talk about them"


def test_they_are_the_same_people_in_any_world(tables):
    made = []
    for seed in (3, 8):
        w = WorldGenerator(WorldOptions("Twin", seed, "small"), tables).generate()
        game = new_game(w, tables)
        made.append({uid: uniques.make_character(game, uid) for uid in SEVEN})
    for uid in SEVEN:
        a, b = made[0][uid], made[1][uid]
        assert (a.name, a.cls, a.subclass, a.level, a.abilities, a.skills, a.expertise) == \
               (b.name, b.cls, b.subclass, b.level, b.abilities, b.skills, b.expertise)
        mine = [it for it in a.inventory if it.magic.get("unique") == uid]
        assert len(mine) == 1 and a.slot_of(mine[0].uid) is not None, "their own thing, worn"


def test_they_come_a_level_above_you(game):
    game.leader.level = 5
    for uid in SEVEN:
        c = uniques.make_character(game, uid)
        assert c.level == 6 and c.hp == c.max_hp and not c.pending


# ---------------------------------------------------------------------------- Osric
def test_osric_is_yours_when_the_barrow_is_still(game, lucky):
    from realmwalker.game import quests

    npc = visit(game, "osric")
    assert set(steps(game, npc)) == {"ask"}
    choose(game, npc, "ask")
    choose(game, npc, "vow")
    q = uniques.unique_quest(game, "osric")
    assert q["template"] == "clear_lair" and q["target"]["site"] == uniques.rec(game, "osric")["site"]
    assert q["reward"] == 0 and "no money" in quests.terms(q)
    assert "advice" in steps(game, npc)
    quests.mark_done(game, q)
    choose(game, npc, "done")
    osric = joined(game, "osric")
    assert q["state"] == "finished" and "Grey Lantern" in comp.bond_text(game, osric)
    osric.companion["order"] = "follow"
    assert comp.watching(game), "Osric keeps watch whatever his orders"


def test_osric_knows_when_somebody_has_already_done_it(game, lucky):
    npc = visit(game, "osric")
    game.world.politics.setdefault("cleared", []).append(uniques.rec(game, "osric")["site"])
    choose(game, npc, "cleared")
    joined(game, "osric")


# ---------------------------------------------------------------------------- Durgin
def test_durgin_drinks_then_swears(game, lucky, monkeypatch):
    from realmwalker.game import dragons

    npc = visit(game, "durgin")
    r = uniques.rec(game, "durgin")
    if not r.get("dragon"):
        pytest.skip("no dragon sleeps in this world")
    monkeypatch.setattr(dice, "d20", lambda rng, **kw: type("R", (), {"natural": 1, "total": 1})())
    conv = choose(game, npc, "drink")
    assert conv.ended and game.leader.intoxication >= 50, "under the table"
    assert not steps(game, npc)["drink"].enabled, "once a day"
    game.world.time += 1440
    game.leader.intoxication = 0
    monkeypatch.setattr(dice, "d20", lambda rng, **kw: type("R", (), {"natural": 20, "total": 20})())
    choose(game, npc, "drink")
    oath = steps(game, npc)["oath"]
    assert not oath.enabled and "unblooded" in oath.why
    game.leader.level = 3
    choose(game, npc, "oath")
    durgin = joined(game, "durgin")
    q = uniques.unique_quest(game, "durgin")
    lair = game.world.sites[q["target"]["site"]]
    assert q["template"] == "slay_dragon" and game.player.explored[lair.x, lair.y]
    assert r["dragon"] in comp.bond_text(game, durgin)
    # The wyrm dies: Durgin's oath is kept.
    d = next(d for d in dragons.living(game.world) if d["name"] == r["dragon"])
    dragons.mark_slain(game, d)
    q["done"], q["state"] = True, "return"
    uniques.daily(game)
    assert durgin.companion["oath"] == "avenged" and "Avenged" in comp.bond_text(game, durgin)
    assert q["state"] == "finished"


def test_durgin_does_not_forgive_a_broken_oath(game, lucky):
    from realmwalker.game import quests

    npc = visit(game, "durgin")
    if not uniques.rec(game, "durgin").get("dragon"):
        pytest.skip("no dragon sleeps in this world")
    game.leader.level = 4
    choose(game, npc, "drink")
    choose(game, npc, "oath")
    joined(game, "durgin")
    quests.abandon(game, uniques.unique_quest(game, "durgin"))
    assert uniques.with_party(game, "durgin") is None
    again = steps(game, npc)["again"]
    assert not again.enabled and "oath" in again.why


# ---------------------------------------------------------------------------- Tobiah
def test_tobiah_can_be_bought_out(game):
    npc = visit(game, "tobiah")
    money = game.leader.money
    choose(game, npc, "hello")
    choose(game, npc, "pay")
    tobiah = joined(game, "tobiah")
    assert game.leader.money == money - uniques.FINE
    assert tobiah.uses.get("relentless_endurance") and "relentless_endurance" in tobiah.features


def test_tobiah_can_be_talked_out_or_let_out(game, lucky):
    npc = visit(game, "tobiah")
    choose(game, npc, "pick")
    joined(game, "tobiah")


def test_the_rope_does_not_take_tobiah(game):
    from realmwalker.rules import progression

    npc = visit(game, "tobiah")
    choose(game, npc, "pay")
    tobiah = joined(game, "tobiah")
    tobiah.uses["relentless_endurance"] = 0
    progression.long_rest(tobiah, game.tables, RNG(1))
    assert tobiah.uses["relentless_endurance"] == 1, "every morning, the luck comes back"


# ---------------------------------------------------------------------------- Wendeline
def test_wendeline_comes_after_a_day_among_the_sick(game, lucky):
    from realmwalker.rules import health

    npc = visit(game, "wendeline")
    start = game.world.time
    choose(game, npc, "work")
    assert game.world.time >= start + 8 * 60
    choose(game, npc, "come")
    wendeline = joined(game, "wendeline")
    assert not health.expose(wendeline, game.tables, "plague", RNG(2)), "she has never once been ill"
    assert any(p.get("spell") == "cure_wounds" for it in wendeline.inventory for p in (it.magic or {}).get("props", []))


def test_wendeline_knows_what_they_say_of_you(game):
    npc = visit(game, "wendeline")
    game.renown.infamy = 40
    come = steps(game, npc)["come"]
    assert not come.enabled


# ---------------------------------------------------------------------------- Grusha
def grusha_along(game):
    npc = visit(game, "grusha")
    choose(game, npc, "tell")
    choose(game, npc, "insight")
    choose(game, npc, "go")
    grusha = joined(game, "grusha")
    assert grusha.companion["penance"] == "pending"
    village = game.world.settlements[uniques.rec(game, "grusha")["village"]]
    assert village.name in comp.bond_text(game, grusha)
    game.player.local_key = None
    game.player.x, game.player.y = village.x, village.y
    game.enter_local()
    head = uniques.headman(game, village)
    assert head is not None
    return grusha, head


def test_grusha_is_forgiven(game, lucky):
    grusha, head = grusha_along(game)
    assert any("know Grusha" in m for m in [m.text for m in game.log.messages[-12:]]), "the village remembers her"
    conv = choose(game, head, "plead")
    assert grusha.companion["penance"] == "forgiven" and "Forgiven" in comp.bond_text(game, grusha)
    assert not [c for c in conv.menu() if c.data.get("step") == "plead"]


def test_grusha_can_be_handed_over(game, lucky):
    grusha, head = grusha_along(game)
    choose(game, head, "hang")
    assert not grusha.alive and grusha not in game.party
    assert uniques.rec(game, "grusha")["state"] == "dead"
    assert any("Grusha" in n["text"] and "dead" in n["text"] for n in game.world.news)


def test_grusha_can_be_paid_for(game, lucky):
    grusha, head = grusha_along(game)
    money = game.leader.money
    choose(game, head, "price")
    assert grusha.companion["penance"] == "paid" and game.leader.money == money - uniques.BLOOD_PRICE


def test_orcs_know_grushas_name(game, lucky):
    from realmwalker.game import fight
    from realmwalker.game.encounters import make_encounter

    game.encounter = make_encounter(game, "orc_raiders", RNG(3))
    before, _ = fight.encounter_talk_dc(game)
    grusha_along(game)
    game.encounter = make_encounter(game, "orc_raiders", RNG(3))
    after, _ = fight.encounter_talk_dc(game)
    assert after < before


# ---------------------------------------------------------------------------- Aelith
def test_aelith_reads_a_book_and_comes(game):
    from realmwalker.rules.inventory import add_item

    npc = visit(game, "aelith")
    assert not steps(game, npc)["book"].enabled
    add_item(game.leader, game.tables.items, "history_book")
    choose(game, npc, "book")
    aelith = joined(game, "aelith")
    assert any(it.def_id == "history_book" for it in game.leader.inventory), "she gives it back"
    assert "fireball" in aelith.spells["spellbook"], "her book holds more than she can cast yet"


def test_aelith_remembers_where_things_happened(game, lucky):
    npc = visit(game, "aelith")
    choose(game, npc, "history")
    joined(game, "aelith")
    seen = {p for e in game.world.history for p in e.get("places", []) if e.get("text")}
    s = next(s for s in game.world.settlements if s.id in seen and s.id != uniques.rec(game, "aelith")["town"])
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    assert any("Aelith" in m for m in [m.text for m in game.log.messages[-10:]]), "she was here before"


# ---------------------------------------------------------------------------- Wren
def test_wren_comes_when_her_crate_gets_past_the_gate(game, lucky, monkeypatch):
    from realmwalker.game import law, quests

    npc = visit(game, "wren")
    choose(game, npc, "cargo")
    q = uniques.unique_quest(game, "wren")
    if q is None:
        joined(game, "wren")  # no walled town near: she took you on trust
        return
    assert q["template"] == "smuggle" and q["state"] == "active"
    assert "waiting" in steps(game, npc)
    quests.mark_done(game, q)
    q["state"] = "finished"
    choose(game, npc, "done")
    joined(game, "wren")
    walled = next(s for s in game.world.settlements if s.walled)
    monkeypatch.setattr(RNG, "chance", lambda self, p: True)
    said = law.gate_search(game, walled)
    if said:
        assert "Wren" in said[0] or "wardens" in said[0]


# ---------------------------------------------------------------------------- leaving, dying, coming back
def test_they_come_back_as_they_left(game):
    npc = visit(game, "tobiah")
    choose(game, npc, "pay")
    tobiah = joined(game, "tobiah")
    tobiah.xp += 123
    level = tobiah.level
    comp.dismiss(game, tobiah)
    r = uniques.rec(game, "tobiah")
    assert r["state"] == "waiting" and "char" in r
    npc = visit(game, "tobiah")
    choose(game, npc, "again")
    back = joined(game, "tobiah")
    assert back.xp == tobiah.xp and back.level == level


def test_a_dead_unique_is_gone_for_good(game):
    npc = visit(game, "tobiah")
    choose(game, npc, "pay")
    tobiah = joined(game, "tobiah")
    tobiah.alive = False
    game.party.remove(tobiah)
    comp.died(game, tobiah)
    assert uniques.rec(game, "tobiah")["state"] == "dead"
    assert not uniques.talk_choices(talk(game, npc)) or not npc.alive


def test_a_leaders_death_sends_them_home(game):
    from realmwalker.game import death

    npc = visit(game, "tobiah")
    choose(game, npc, "pay")
    joined(game, "tobiah")
    death.release_companions(game)
    r = uniques.rec(game, "tobiah")
    assert r["state"] == "waiting" and "char" in r and "recruit" not in npc.flags


def test_their_voices_are_their_own(game):
    npc = visit(game, "aelith")
    game.leader.inventory.append(game.leader.inventory[0].__class__(uid=999, def_id="history_book"))
    choose(game, npc, "book")
    aelith = joined(game, "aelith")
    own = set(game.tables.uniques["uniques"]["aelith"]["lines"]["road"])
    said = comp.line(game, "road", aelith, RNG(4))
    assert said in own or any(said == line.replace("{name}", "Aelith") for line in own)
    npc = visit(game, "tobiah")
    choose(game, npc, "pay")
    rng = RNG(5)
    assert uniques.banter(game, rng), "two of the seven talk to each other"


def test_the_seven_survive_saving(game, tmp_path):
    npc = visit(game, "tobiah")
    choose(game, npc, "pay")
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    t = uniques.with_party(loaded, "tobiah")
    assert t is not None and uniques.rec(loaded, "tobiah")["state"] == "with"
    assert any(it.magic.get("unique") == "tobiah" for it in t.inventory)


def test_the_party_screen_shows_who_they_are(make_app, world):
    import tcod.console

    from realmwalker.ui.screens.party import PartyScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    game.leader.money = 100000
    app.start_game(game)
    npc = visit(game, "tobiah")
    choose(game, npc, "pay")
    screen = PartyScreen(app, game)
    screen.sel = 1
    app.push(screen)
    con = tcod.console.Console(120, 40, order="F")
    app.render(con)
    text = "\n".join("".join(chr(ch) for ch in con.rgb["ch"][:, y]) for y in range(con.height))
    assert "Twice-Hanged" in text and "Raise pay" not in text
    assert app.error_count == 0


def test_talk_of_them_puts_their_town_on_your_map(game):
    from realmwalker.game import news

    uniques.ensure(game)
    r = uniques.rec(game, "tobiah")
    s = game.world.settlements[r["town"]]
    game.player.known_settlements.discard(s.id)
    game.player.x, game.player.y = s.x, s.y
    heard = news.hear(game, count=40)
    assert any("Tobiah" in h or "hanged twice" in h for h in heard)
    assert s.id in game.player.known_settlements
