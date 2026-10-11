"""Law and crime (M6 part 2): witnesses, reports, bounties, the watch, sentences, escapes, disguises, deeds and
their ripples, prisoners, guild membership, titles, theft and the conversation options."""

import copy

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import law, law_talk, reputation, save
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world import factions as fx
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Lawland", 12, "medium"), tables).generate()


def hero(tables, cls="rogue", background="criminal"):
    b = CharacterBuilder(tables, RNG(3, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background(background)
    return b.build()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables, hero(tables, background="folk_hero"))
    g.survival = False
    return g


def in_town(game, kind="town"):
    s = next(s for s in game.world.settlements if s.kind == kind and fx.owner_of(game.world, s) is not None)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    game.renown.bounties.clear()
    realm = fx.realm_of_settlement(game.world, s)
    return s, realm


def someone(game, s, job=None, exclude=()):
    return next(n for n in npcs_in(game.world, s.id) if (job is None or n.job == job) and n.alive
                and n.job not in exclude)


def fixed_d20(monkeypatch, value):
    class Roll:
        natural = value
        total = value

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Roll())


def test_a_guard_who_sees_a_crime_acts_at_once(game):
    s, realm = in_town(game)
    guard = someone(game, s, "guard")
    rec = law.commit(game, "assault", victim=someone(game, s, exclude=("guard",)), witnesses=[guard])
    assert rec["reported"]
    assert game.renown.bounties[realm.id] == game.tables.law["crimes"]["assault"]["fine"]
    assert reputation.standing(game, realm.id) < 0
    assert game.arrest is not None and game.arrest["realm"] == realm.id
    assert game.busy


def test_witnesses_report_unless_silenced(game):
    s, realm = in_town(game)
    a, b = [n for n in npcs_in(game.world, s.id) if n.job not in ("guard",)][:2]
    rec = law.commit(game, "theft", victim=a, value=100, witnesses=[b])
    assert not rec["reported"] and rec.get("report_at")
    game.pass_time(5 * 60)
    assert rec["reported"] and game.renown.bounties[realm.id] > 0
    # A silenced witness keeps quiet.
    game.renown.bounties.clear()
    rec2 = law.commit(game, "theft", victim=a, value=100, witnesses=[b])
    law.silence(b, [rec2])
    game.pass_time(5 * 60)
    assert not rec2["reported"] and not game.renown.bounties.get(realm.id)


def test_unseen_crimes_are_never_traced(game):
    s, realm = in_town(game)
    rec = law.commit(game, "trespass", witnesses=[])
    assert rec["unseen"] and not rec["reported"]
    game.pass_time(6 * 60)
    assert not game.renown.bounties.get(realm.id)


def test_no_law_in_the_wild(game):
    w = game.world
    owner, _ = fx.territory(w)
    x, y = next((x, y) for x in range(w.width) for y in range(w.height)
                if owner[x, y] < 0 and w.biome_ids[w.biome[x, y]] not in ("ocean", "lake"))
    game.player.local_key = None
    game.player.x, game.player.y = x, y
    assert law.commit(game, "murder", witnesses=[]) is None


def test_petty_crimes_can_be_paid_for(game):
    s, realm = in_town(game)
    law.commit(game, "theft", value=50, witnesses=[someone(game, s, "guard")])
    bounty = game.renown.bounties[realm.id]
    game.leader.money = bounty + 100
    options = {o[0]: o for o in law.arrest_options(game)}
    assert options["pay"][2]
    text = law.pay_bounty(game, realm.id)
    assert "clean" in text and game.renown.bounties[realm.id] == 0 and game.leader.money == 100
    assert all(r["settled"] for r in game.renown.crimes if r["realm"] == realm.id)


def test_murder_cannot_be_bought_off(game):
    s, realm = in_town(game)
    law.commit(game, "murder", victim=someone(game, s, exclude=("guard",)), witnesses=[someone(game, s, "guard")])
    game.leader.money = 10**7
    assert not law.can_buy_off(game, realm.id)
    assert "death" in law.sentence_for(game, realm.id) or "jail:60" in law.sentence_for(game, realm.id)


def serve_all(game):
    for _ in range(12):
        if game.sentence is None or game.sentence.get("finished") or game.sentence.get("gallows"):
            break
        law.carry_out(game)


def test_going_quietly_serves_the_sentence(game, monkeypatch):
    s, realm = in_town(game)
    realm.laws["harshness"] = "stern"
    law.commit(game, "assault", victim=someone(game, s, exclude=("guard",)), witnesses=[someone(game, s, "guard")])
    game.leader.money = 0
    sword = len(game.leader.inventory)
    t0 = game.world.time
    law.go_quietly(game)
    assert game.arrest is None and game.sentence["steps"] == ["fine", "jail:5"]
    serve_all(game)
    s_ = game.sentence
    assert s_["finished"] and not s_["escaped"]
    # The unpaid fine became extra jail days, and time passed.
    assert game.world.time - t0 >= 5 * 24 * 60
    assert game.renown.bounties[realm.id] == 0
    assert len(game.leader.inventory) == sword, "belongings come back"
    assert "confiscated" not in game.renown.flags


def test_the_lash_and_the_brand(game):
    s, realm = in_town(game)
    realm.laws["harshness"] = "harsh"
    law.commit(game, "forbidden_magic", witnesses=[someone(game, s, "guard")])
    law.go_quietly(game)
    assert game.sentence["steps"] == ["branding", "labour:30"]
    law.carry_out(game)
    assert "branded" in game.renown.marks and "brand" in game.leader.appearance
    before = len(game.leader.wounds)
    law.flog(game)
    assert len(game.leader.wounds) >= before + 2


def test_the_rope(game):
    s, realm = in_town(game)
    realm.laws["harshness"] = "harsh"
    law.commit(game, "murder", victim=someone(game, s, exclude=("guard",)), witnesses=[someone(game, s, "guard")])
    law.go_quietly(game)
    assert game.sentence["steps"] == ["death"]
    law.carry_out(game)
    assert game.sentence.get("gallows")
    law.gallows_choice(game, escape=False)
    assert game.over is not None and "hanged" in game.over["cause"]


def test_escaping_the_gallows(game, monkeypatch):
    s, realm = in_town(game)
    realm.laws["harshness"] = "harsh"
    law.commit(game, "murder", victim=someone(game, s, exclude=("guard",)), witnesses=[someone(game, s, "guard")])
    law.go_quietly(game)
    law.carry_out(game)
    fixed_d20(monkeypatch, 20)
    notes = law.gallows_choice(game, escape=True)
    assert game.over is None and game.sentence["escaped"] and not game.in_local
    assert any(r["crime"] == "jailbreak" for r in game.renown.crimes)
    assert notes


def test_bribing_and_running(game, monkeypatch):
    s, realm = in_town(game)
    guard = someone(game, s, "guard")
    law.commit(game, "theft", value=10, witnesses=[guard])
    game.leader.money = 10**6
    fixed_d20(monkeypatch, 20)
    ok, _ = law.bribe_guard(game)
    assert ok and game.arrest is None and guard.flags["bribed_until"] > game.world.time
    assert game.renown.bounties[realm.id] > 0, "still wanted"
    law.start_arrest(game, guard)
    fixed_d20(monkeypatch, 1)
    ok, _ = law.run_for_it(game)
    assert not ok and game.arrest is not None
    assert not {o[0]: o for o in law.arrest_options(game)}["run"][2]


def test_fighting_the_watch(game):
    s, realm = in_town(game)
    law.commit(game, "theft", value=10, witnesses=[someone(game, s, "guard")])
    law.fight_the_watch(game)
    assert game.arrest is None
    assert game.battle is not None or game.encounter is not None
    assert any(r["crime"] == "resisting_arrest" for r in game.renown.crimes)


def test_the_watch_knows_a_wanted_face(game, monkeypatch):
    s, realm = in_town(game)
    game.renown.bounties[realm.id] = 5000
    guard = someone(game, s, "guard")
    guard.x, guard.y = game.player.lx + 1, game.player.ly
    guard.present = True
    monkeypatch.setattr(RNG, "chance", lambda self, p: True)
    law.watch(game)
    assert game.arrest is not None


def test_a_disguise_hides_you(game, monkeypatch):
    s, realm = in_town(game)
    game.leader.tools.append("disguise_kit")
    fixed_d20(monkeypatch, 20)
    law.put_on_disguise(game, game.leader)
    assert law.disguised(game)
    law.commit(game, "theft", value=10, witnesses=[someone(game, s, "guard")])
    assert not game.renown.bounties.get(realm.id), "the stranger in disguise is wanted, not you"
    game.arrest = None
    game.renown.bounties[realm.id] = 5000
    guard = someone(game, s, "guard")
    guard.x, guard.y = game.player.lx + 1, game.player.ly
    fixed_d20(monkeypatch, 1)
    law.watch(game)
    assert game.arrest is None, "a good disguise fools the watch"


def test_deeds_ripple_as_news_travels(game):
    w = game.world
    kingdoms = fx.active_factions(w, "kingdom")
    others = [f for f in fx.active_factions(w) if f.id != kingdoms[0].id]

    def ties(realm):
        friends = [f for f in fx.active_factions(w) if fx.relation(w, realm.id, f.id) >= 40 and f.id != realm.id]
        enemies = [f for f in fx.active_factions(w) if fx.relation(w, realm.id, f.id) <= -40]
        return friends, enemies

    realm = next((k for k in kingdoms if all(ties(k))), kingdoms[0])
    friends, enemies = ties(realm)
    if not (friends and enemies):  # (a peaceful world: make a friend and an enemy for the test)
        fx.set_relation(w, realm.id, others[0].id, 60)
        fx.set_relation(w, realm.id, others[-1].id, -60)
        friends, enemies = ties(realm)
    assert friends and enemies
    reputation.deed(game, "saved the king's daughter", {realm.id: 30.0}, immediate=(realm.id,), fame=5,
                    news_text="someone saved the king's daughter")
    assert reputation.standing(game, realm.id) == 30
    assert game.renown.pending
    game.world.time += 200 * 24 * 60
    reputation.tick(game)
    assert not game.renown.pending
    assert all(reputation.standing(game, f.id) > 0 for f in friends)
    assert all(reputation.standing(game, f.id) < 0 for f in enemies)
    assert game.renown.fame == 5
    assert any(n["player"] for n in w.news)


def test_beating_bandits_angers_their_gang(game):
    from realmwalker.rules.combat import BattleResult
    from realmwalker.rules.creatures import spawn

    w = game.world
    gang = fx.active_factions(w, "bandit_gang")[0]
    site = w.sites[gang.site]
    game.player.local_key = None
    game.player.x, game.player.y = site.x, site.y
    rng = RNG(1, "x")
    dead = [spawn(game.tables, "bandit", rng, i) for i in range(3)]
    result = BattleResult("victory", dead=dead, captives=[], fled=[dead[0]], loot_items=[], loot_money=0, xp=0,
                          rounds=1, party_dead=[])
    reputation.battle_deeds(game, result)
    assert reputation.standing(game, gang.id) < 0
    assert gang.id in game.renown.known


def test_prisoners_for_the_law(game):
    s, realm = in_town(game)
    game.renown.flags["captives"] = [{"def_id": "bandit", "name": "the bandit", "reward": 800, "since": 0,
                                      "faction": -1}]
    guard = someone(game, s, "guard")
    conv = Conversation(game, guard)
    ids = [c.id for c in conv.menu()]
    assert "prisoners" in ids
    money = game.leader.money
    conv.choose(next(c for c in conv.menu() if c.id == "prisoners"))
    assert game.leader.money == money + 800 and not game.renown.flags.get("captives")
    assert game.leader.deeds[-1] == "handed a prisoner to the law"  # not "1 prisoner(s)"


def test_settling_debts_in_conversation(game):
    s, realm = in_town(game)
    law.commit(game, "theft", value=10, witnesses=[someone(game, s, exclude=("guard",))], reported=True)
    game.arrest = None
    game.leader.money = 10**6
    guard = someone(game, s, "guard")
    conv = Conversation(game, guard)
    choice = next(c for c in conv.menu() if c.id == "pay_fines")
    assert choice.enabled
    conv.choose(choice)
    assert game.renown.bounties[realm.id] == 0


def test_silencing_a_witness(game, monkeypatch):
    s, realm = in_town(game)
    a, b = [n for n in npcs_in(game.world, s.id) if n.job != "guard"][:2]
    rec = law.commit(game, "theft", victim=a, value=10, witnesses=[b])
    conv = Conversation(game, b)
    ids = [c.id for c in conv.menu()]
    assert "hush_pay" in ids and "hush_threat" in ids
    fixed_d20(monkeypatch, 20)
    conv.choose(next(c for c in conv.menu() if c.id == "hush_threat"))
    game.pass_time(6 * 60)
    assert not rec["reported"]


def test_joining_a_guild_and_its_ranks(game):
    s, realm = in_town(game, "city")
    smith = next((n for n in npcs_in(game.world, s.id) if n.job in ("smith", "shopkeeper", "healer", "priest")
                  and law_talk.joinable(game, n)), None)
    if smith is None:
        pytest.skip("no guild here")
    f = law_talk.joinable(game, smith)[0]
    spec = game.tables.law["join"][f.kind]
    assert reputation.join_problem(game, f) is not None or spec["standing"] <= 0
    reputation.set_standing(game, f.id, 20)
    game.leader.money = 10**6
    game.leader.skills += [spec.get("skill")] if spec.get("skill") else []
    game.leader.tools += [spec.get("tool")] if spec.get("tool") else []
    if spec.get("classes"):
        game.leader.cls = spec["classes"][0]
    if spec.get("faith"):
        game.leader.culture = next(c for c, laws in game.tables.factions["culture_laws"].items()
                                   if fx.faith_for_culture(game.tables, c) == f.faith)
    assert reputation.join_problem(game, f) is None
    text = reputation.join(game, f)
    assert "sworn" in text and f.id in game.renown.members
    assert reputation.rank_name(game, f.id) == spec["ranks"][0]  # everyone starts at the bottom
    reputation.set_standing(game, f.id, 80)
    assert reputation.needs_trial(game, f.id)  # standing opens the door; their work walks you through it
    assert reputation.rank_name(game, f.id) == spec["ranks"][0]
    reputation.tick(game)  # ...but they cannot go on calling you an apprentice for ever
    assert reputation.rank_name(game, f.id) == spec["ranks"][1]
    reputation.confirm_rank(game, f.id)
    assert reputation.rank_name(game, f.id) == spec["ranks"][2]
    assert reputation.member_discount(game, [f]) > 0


def test_a_ruler_grants_a_title(game):
    w = game.world
    k = fx.active_factions(w, "kingdom")[0]
    assert reputation.title_problem(game, k)
    reputation.set_standing(game, k.id, 60)
    game.renown.fame = 20
    assert reputation.title_problem(game, k) is None
    text = reputation.grant_title(game, k)
    assert reputation.titles(game) and reputation.titles(game)[0] in text


def test_stealing_from_a_shop(game, monkeypatch):
    from realmwalker.game import economy

    s, realm = in_town(game, "city")
    trader = next(n for n in npcs_in(game.world, s.id) if economy.shop_spec(game, n) is not None)
    shop = economy.shop_state(game, trader)
    item_id = next(iter(shop["stock"]))
    before = shop["stock"][item_id]
    monkeypatch.setattr(law, "witnesses_here", lambda *a, **k: [])
    fixed_d20(monkeypatch, 20)
    ok, _ = law.steal_from_shop(game, trader, item_id)
    assert ok and shop["stock"].get(item_id, 0) == before - 1
    got = next(it for it in game.leader.inventory if it.def_id == item_id and "stolen" in it.tags)
    assert economy.sell_price(game, trader, got)[0] is None
    fixed_d20(monkeypatch, 1)
    ok, _ = law.steal_from_shop(game, trader, item_id if shop["stock"].get(item_id) else next(iter(shop["stock"])))
    assert not ok and any(r["crime"] == "theft" for r in game.renown.crimes)


def test_pickpocketing(game, monkeypatch):
    s, realm = in_town(game)
    mark = someone(game, s, exclude=("guard",))
    mark.purse = 1000
    monkeypatch.setattr(law, "witnesses_here", lambda *a, **k: [])
    fixed_d20(monkeypatch, 20)
    money = game.leader.money
    conv = Conversation(game, mark)
    conv.choose(next(c for c in conv.menu() if c.id == "pickpocket"))
    assert game.leader.money > money and mark.purse < 1000


def test_contraband_at_the_gate(game, monkeypatch):
    from realmwalker.rules.inventory import add_item

    w = game.world
    s = next((s for s in w.settlements if s.walled and fx.realm_of_settlement(w, s) is not None), None)
    if s is None:
        pytest.skip("no walled town")
    monkeypatch.setattr(law, "contraband_for", lambda game, realm_id: ["poppy_milk"])
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    banned = law.contraband_for(game, fx.realm_of_settlement(w, s).id)[0]
    add_item(game.leader, game.tables.items, banned, 1)
    monkeypatch.setattr(RNG, "chance", lambda self, p: True)
    notes = law.gate_search(game, s)
    assert notes and not any(it.def_id == banned for it in game.leader.inventory)
    assert any(r["crime"] == "smuggling" for r in game.renown.crimes)


def test_law_survives_saving(game, tmp_path):
    s, realm = in_town(game)
    law.commit(game, "assault", victim=someone(game, s, exclude=("guard",)), witnesses=[someone(game, s, "guard")])
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / game.world.meta.id, game.tables)
    assert loaded.arrest == game.arrest
    assert loaded.renown.bounties == game.renown.bounties
    assert loaded.renown.crimes == game.renown.crimes


def test_fence_ransoms_prisoners_for_more_than_the_watch(game):
    """The guild sells prisoners back to their own people, quietly, at the data's ransom share."""
    from realmwalker.game import law_talk

    st, _ = in_town(game)
    w = game.world
    guild = next((f for f in w.factions.values() if f.kind == "thieves_guild"), None)
    assert guild is not None
    npc = someone(game, st)
    npc.flags["secret"] = guild.id
    game.renown.known.add(guild.id)
    game.renown.members[guild.id] = {"rank": 0, "since": w.time}
    assert law.is_fence(game, npc)
    game.renown.flags["captives"] = [
        {"def_id": "bandit", "name": "a bandit", "reward": 800, "since": w.time, "faction": -1}]
    before_money, before_news = game.leader.money, len(w.news)
    text = law_talk.ransom(game, npc)
    share = float(game.tables.law["ransom_share"])
    assert game.leader.money - before_money == int(800 * share)
    assert not game.renown.flags.get("captives")
    assert len(w.news) == before_news, "quiet work is not talked about"
    assert "gp" in text or "sp" in text


def test_ransom_needs_prisoners(game):
    from realmwalker.game import law_talk

    st, _ = in_town(game)
    game.renown.flags.pop("captives", None)
    assert "no prisoners" in law_talk.ransom(game, someone(game, st)).lower()
