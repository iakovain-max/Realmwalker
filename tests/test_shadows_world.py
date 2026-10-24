"""Steel & Shadows Part C.3: the people of the shadows in the world - poison and the law, the black market, the
guilds' work, a poisoned cup, duels of honour, and spies caught at court."""

from realmwalker.core.rng import RNG
from realmwalker.game import economy, law, quests, shadows
from realmwalker.game.dialogue import Conversation
from realmwalker.rules.inventory import add_item
from realmwalker.world import factions as fx
from realmwalker.world.politics import Politics
from tests.test_law import fixed_d20, game, in_town, someone, tables, world  # noqa: F401 (fixtures)


def member_of_guild(game, npc):
    w = game.world
    guild = next(f for f in w.factions.values() if f.kind == "thieves_guild")
    npc.flags["secret"] = guild.id
    game.renown.known.add(guild.id)
    game.renown.members[guild.id] = {"rank": 0, "since": w.time}
    return guild


def test_poison_is_contraband_where_the_realm_forbids_it(game, monkeypatch):
    s, realm = in_town(game)
    monkeypatch.setitem(game.tables.law["shadows"], "poison_allowed", [])
    banned = law.contraband_for(game, realm.id)
    assert "serpent_venom" in banned and "basic_poison" in banned
    assert not shadows.shop_sells(game, s, "serpent_venom")
    assert shadows.shop_sells(game, s, "bandages")
    monkeypatch.setitem(game.tables.law["shadows"], "poison_allowed", [realm.culture])
    assert "serpent_venom" not in law.contraband_for(game, realm.id)
    assert shadows.shop_sells(game, s, "serpent_venom")


def test_the_black_market_sells_under_the_counter_to_the_guild(game, monkeypatch):
    s, realm = in_town(game, "city")
    monkeypatch.setitem(game.tables.law["shadows"], "poison_allowed", [])
    npc = someone(game, s, exclude=("guard", "lord"))
    npc.job = "beggar" if "beggar" in game.tables.people["occupations"] else npc.job
    if game.tables.people["occupations"].get(npc.job, {}).get("trade"):
        npc.job = next(j for j, o in game.tables.people["occupations"].items() if not o.get("trade"))
    conv = Conversation(game, npc)
    assert not any(c.id == "black_market" for c in conv.menu())  # (a stranger is told nothing)
    member_of_guild(game, npc)
    conv = Conversation(game, npc)
    choice = next(c for c in conv.menu() if c.id == "black_market")
    assert conv.choose(choice) == "trade"
    assert economy.shop_kind(game, npc) == "black_market"
    rows = economy.listing(game, npc)
    poisons = [r for r in rows if game.tables.items.get(r["item_id"]).get("poison")]
    assert poisons
    r = poisons[0]
    assert r["price"] > game.tables.items.get(r["item_id"])["value"]  # (dearer than the honest price)


def test_the_guild_gives_its_own_the_killing_work(game):
    """A thieves' guild's commissions (Expansion 6 C.2) are its knives and its light fingers, given by its fences."""
    from realmwalker.game.story import work

    s, realm = in_town(game)
    npc = someone(game, s, exclude=("guard", "lord"))
    guild = next(f for f in game.world.factions.values() if f.kind == "thieves_guild")
    assert not work.member(game, npc, guild)
    member_of_guild(game, npc)
    assert work.member(game, npc, guild)
    assert {"assassinate", "steal"} <= set(work.kinds_for(game, guild))
    offer = quests.make_offer(game, npc, RNG(9, "q"), template="assassinate")
    assert offer is None or offer["template"] == "assassinate"


def test_truth_serum_in_a_cup_brings_out_their_secret(game, monkeypatch):
    s, realm = in_town(game)
    npc = someone(game, s, exclude=("guard", "lord"))
    guild = next(f for f in game.world.factions.values() if f.kind == "thieves_guild")
    npc.flags["secret"] = guild.id
    game.renown.known.discard(guild.id)
    add_item(game.leader, game.tables.items, "truth_serum")
    conv = Conversation(game, npc)
    choice = next(c for c in conv.menu() if c.id == "slip_poison")
    monkeypatch.setattr(shadows, "npc_save", lambda *a, **k: (False, 3))
    fixed_d20(monkeypatch, 20)
    conv.choose(choice)
    assert guild.id in game.renown.known
    assert not any(it.def_id == "truth_serum" for it in game.leader.inventory)


def test_a_lethal_cup_kills_and_a_clumsy_hand_is_an_assault(game, monkeypatch):
    s, realm = in_town(game)
    npc = someone(game, s, exclude=("guard", "lord"))
    add_item(game.leader, game.tables.items, "midnight_tears")
    conv = Conversation(game, npc)
    choice = next(c for c in conv.menu() if c.id == "slip_poison")
    monkeypatch.setattr(shadows, "npc_save", lambda *a, **k: (False, 3))
    fixed_d20(monkeypatch, 20)
    conv.choose(choice)
    assert not npc.alive
    other = someone(game, s, exclude=("guard", "lord"))
    add_item(game.leader, game.tables.items, "assassins_blood")
    conv = Conversation(game, other)
    choice = next(c for c in conv.menu() if c.id == "slip_poison")
    fixed_d20(monkeypatch, 1)
    before = len(game.renown.crimes)
    conv.choose(choice)
    assert other.alive and len(game.renown.crimes) == before + 1 and game.renown.crimes[-1]["crime"] == "assault"


def test_a_gentleman_of_a_duelling_people_answers_with_steel(game, monkeypatch):
    s, realm = in_town(game)
    npc = someone(game, s, exclude=("guard",))
    npc.social = "high"
    npc.job = "lord" if npc.job != "lord" else npc.job
    monkeypatch.setitem(game.tables.law["shadows"], "duels", [s.culture])
    conv = Conversation(game, npc)
    monkeypatch.setattr(conv, "check", lambda skill, dc: (False, "(a failed threat)"))
    conv.threaten()
    assert npc.flags.get("challenge") is not None
    accept = next(c for c in conv.menu() if c.id == "duel_accept")
    conv.choose(accept)
    assert game.battle is not None and game.renown.flags.get("duel") == npc.id

    class F:
        state = "down"

    assert shadows.duel_settled(game, npc, F(), "victory")
    assert npc.alive and not game.renown.flags.get("duel")
    assert not any(c["crime"] in ("assault", "murder") for c in game.renown.crimes)


def test_spies_are_caught_at_court(game):
    w = game.world
    p = Politics(w, game.tables, RNG(4, "p"))
    powers = p.powers()
    a, b = powers[0], powers[1]
    before = fx.relation(w, a.id, b.id)
    news = len(w.news)
    p.spy_caught(a, b)
    assert fx.relation(w, a.id, b.id) < before
    assert len(w.news) == news + 1 and ("spy" in w.news[-1]["text"].lower() or "agent" in w.news[-1]["text"].lower()
                                         or "letters" in w.news[-1]["text"].lower())
