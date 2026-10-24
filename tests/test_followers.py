"""Why people follow you (after v1, asked for by Anton): only your purse is spent, and not everyone who walks with
you does it for a wage. Knights lent by a realm that honours you, farm lads and drunkards told about your work,
people talked into leaving home, the homeless, and those who have heard your name."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import companions as comp
from realmwalker.game import save
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Fellowland", 21, "medium"), tables)


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    g.leader.money = 100000
    return g


def to_town(game, kind="town"):
    s = next(s for s in game.world.settlements if s.kind == kind)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return s


def hire_one(game, kind="city"):
    s = to_town(game, kind)
    t = [n for n in npcs_in(game.world, s.id) if n.flags.get("recruit") and n.alive and not n.flags.get("companion")]
    if not t:
        pytest.skip("no traveller at this inn")
    npc = t[0]
    npc.disposition, npc.met = 20, True
    assert "joins you" in comp.hire(game, npc)[0]
    return game.party[-1], npc, s


# ---------------------------------------------------------------------------- one purse
def test_companions_carry_no_purse(game):
    c, npc, s = hire_one(game)
    assert c.money == 0, "a new companion brings no coin of their own for you to spend"
    before = game.leader.money
    comp.daily(game)
    assert c.money == 0 and game.leader.money == before - c.companion["wage"]
    assert comp.pay_word(game, c).endswith("a day")


def test_the_party_screen_shows_no_companion_purse(make_app, world):
    import tcod.console

    from realmwalker.ui.screens.party import PartyScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    game.leader.money = 100000
    app.start_game(game)
    c, npc, s = hire_one(game)
    screen = PartyScreen(app, game)
    screen.sel = 1
    app.push(screen)
    con = tcod.console.Console(120, 40, order="F")
    app.render(con)
    text = "\n".join("".join(chr(ch) for ch in con.rgb["ch"][:, y]) for y in range(con.height))
    assert "Money" not in text.split(c.name.split()[0], 1)[1], "a companion has no money line"
    assert app.error_count == 0


def member(tables, cls, seed):
    b = CharacterBuilder(tables, RNG(seed, "member"))
    b.set_class(cls)
    return b.build()


# ---------------------------------------------------------------------------- bonds
def talk(game, npc):
    from realmwalker.game.dialogue import Conversation

    npc.met = True
    return Conversation(game, npc)


def recruit_choices(conv, how=None):
    return [c for c in conv.menu() if c.id == "recruit" and (how is None or c.data.get("how") == how)]


@pytest.fixture
def lucky(monkeypatch):
    """Every skill check in conversation succeeds."""
    from realmwalker.game.dialogue import Conversation

    monkeypatch.setattr(Conversation, "check", lambda self, skill, dc: (True, f"({skill} vs {dc})"))


@pytest.fixture
def unlucky(monkeypatch):
    from realmwalker.game.dialogue import Conversation

    monkeypatch.setattr(Conversation, "check", lambda self, skill, dc: (False, f"({skill} vs {dc})"))


def test_the_hired_are_hired_and_say_so(game, tmp_path):
    c, npc, s = hire_one(game)
    assert comp.bond_of(c) == "hired" and comp.bond_text(game, c).startswith("Hired, for")
    c.companion.pop("bond")  # a companion from before bonds
    assert comp.bond_of(c) == "hired"


def ruler_of_a_realm(game):
    """Walk into the seat of a kingdom (or another realm that lends swords) and find its ruler."""
    from realmwalker.game import followers
    from realmwalker.world import factions as fx

    w = game.world
    for f in fx.active_factions(w, *followers.LENDING_KINDS):
        if not 0 <= f.seat < len(w.settlements):
            continue
        s = w.settlements[f.seat]
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        for npc in npcs_in(w, s.id):
            if followers.lender_of(game, npc) is f:
                return npc, f
    pytest.skip("no realm with a ruler at home in this world")


def test_a_realm_that_honours_you_lends_you_a_sword(game):
    from realmwalker.game import followers, reputation

    ruler, f = ruler_of_a_realm(game)
    conv = talk(game, ruler)
    choice = recruit_choices(conv, "sworn")[0]
    assert not choice.enabled and "honour you" in choice.why
    reputation.set_standing(game, f.id, 60)
    conv = talk(game, ruler)
    choice = recruit_choices(conv, "sworn")[0]
    assert choice.enabled, choice.why
    conv.choose(choice)
    knight = game.party[-1]
    assert comp.bond_of(knight) == "sworn" and knight.companion["lender"] == f.id
    assert knight.companion["wage"] == 0 and knight.money == 0 and knight.cls == "fighter"
    assert f.name in comp.bond_text(game, knight)
    assert not recruit_choices(talk(game, ruler), "sworn")[0].enabled, "one at a time"
    # They think less of you now: the sword is called home.
    reputation.set_standing(game, f.id, 5)
    followers.daily(game)
    assert knight not in game.party and comp.bond_of(knight) == "sworn"


def test_a_lent_sword_who_dies_is_remembered(game):
    from realmwalker.game import reputation

    ruler, f = ruler_of_a_realm(game)
    reputation.set_standing(game, f.id, 70)
    conv = talk(game, ruler)
    conv.choose(recruit_choices(conv, "sworn")[0])
    knight = game.party[-1]
    knight.alive = False
    comp.died(game, knight)
    assert reputation.standing(game, f.id) == 65
    game.party.remove(knight)
    choice = recruit_choices(talk(game, ruler), "sworn")[0]
    assert not choice.enabled and "dead" in choice.why


def a_quest(game):
    """Some paying work in hand."""
    from realmwalker.game import quests

    for s in game.world.settlements:
        if s.kind not in ("town", "city"):
            continue
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        for npc in npcs_in(game.world, s.id):
            q = quests.make_offer(game, npc, game.world.rng.child(f"a_quest/{npc.id}")) if npc.notable else None
            if q is not None and q["reward"] >= 50:
                quests.accept(game, q)
                return q
    pytest.skip("nobody offers work in this world")


def a_dreamer(game):
    from realmwalker.game import followers

    for s in game.world.settlements:
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        for npc in npcs_in(game.world, s.id):
            if followers.dreamer(game, npc) and npc.present:
                npc.disposition = 10
                return npc
    pytest.skip("no farm lads in this world")


def test_a_farm_lad_told_about_your_work(game, lucky):
    from realmwalker.game import quests

    npc = a_dreamer(game)
    choice = recruit_choices(talk(game, npc), "dream")[0]
    assert not choice.enabled and "no paying work" in choice.why
    q = a_quest(game)
    npc = a_dreamer(game)
    conv = talk(game, npc)
    honest = next(c for c in recruit_choices(conv, "dream") if not c.data.get("lie"))
    assert honest.enabled
    conv.choose(honest)
    lad = game.party[-1]
    assert comp.bond_of(lad) == "dreamer" and lad.level == 1 and lad.companion["wage"] == 0
    assert not any(it.def_id in ("chain_mail", "scale_mail", "longsword") for it in lad.inventory), "no soldier's kit"
    # The work pays: the lad takes a fifth, and is pleased.
    before, loyalty = game.leader.money, lad.companion["loyalty"]
    q["done"], q["state"] = True, "return"
    said = quests.reward(game, q)
    cut = int(q["reward"] * 0.2)
    assert game.leader.money == before + q["reward"] - cut and lad.companion["paid"] == cut
    assert lad.companion["loyalty"] > loyalty and any("share" in t for t in said)


def test_a_lie_about_riches_is_remembered(game, lucky):
    from realmwalker.game import followers, quests

    q = a_quest(game)
    q["reward"] = min(q["reward"], followers.RICH - 10)
    npc = a_dreamer(game)
    conv = talk(game, npc)
    lie = next(c for c in recruit_choices(conv, "dream") if c.data.get("lie"))
    conv.choose(lie)
    fool = game.party[-1]
    assert fool.companion["lied"]
    loyalty = fool.companion["loyalty"]
    q["done"], q["state"] = True, "return"
    said = quests.reward(game, q)
    assert fool.companion["loyalty"] < loyalty - 15, "rich, you said"  # (whatever else the work made them feel)
    assert any("<warn>" in t and fool.name.split()[0] in t for t in said)


def test_dreamers_lose_heart_without_work(game, lucky):
    from realmwalker.game import followers, quests

    q = a_quest(game)
    npc = a_dreamer(game)
    conv = talk(game, npc)
    conv.choose(recruit_choices(conv, "dream")[0])
    lad = game.party[-1]
    quests.abandon(game, q)
    assert lad.companion["loyalty"] < 50, "the work they came for was given up"
    loyalty = lad.companion["loyalty"]
    for _ in range(followers.IDLE_DAYS + 3):
        followers.daily(game)
    assert lad.companion["loyalty"] < loyalty


def a_restless_soul(game):
    from realmwalker.game import followers

    for s in game.world.settlements:
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        for npc in npcs_in(game.world, s.id):
            if followers.restless(game, npc) and npc.present:
                npc.disposition = 10
                return npc
    pytest.skip("nobody restless in this world")


def test_the_restless_can_be_talked_into_leaving(game, unlucky, monkeypatch):
    from realmwalker.game.dialogue import Conversation

    npc = a_restless_soul(game)
    conv = talk(game, npc)
    conv.choose(recruit_choices(conv, "restless")[0])
    assert len(game.party) == 1
    again = recruit_choices(talk(game, npc), "restless")[0]
    assert not again.enabled and "think" in again.why, "one try a week"
    npc.flags["restless_day"] -= 7
    monkeypatch.setattr(Conversation, "check", lambda self, skill, dc: (True, ""))
    conv = talk(game, npc)
    conv.choose(recruit_choices(conv, "restless")[0])
    c = game.party[-1]
    assert comp.bond_of(c) == "restless" and c.companion["want"] == "knowledge" and c.companion["wage"] == 0


def test_the_homeless_wait_at_inns_near_a_ruin(game):
    from realmwalker.game import followers

    w = game.world
    town = next(s for s in w.settlements if s.kind in ("town", "city")
                and any(o.id != s.id and abs(o.x - s.x) + abs(o.y - s.y) <= followers.RUIN_REACH for o in w.settlements))
    place = next(o for o in w.settlements if o.id != town.id and abs(o.x - town.x) + abs(o.y - town.y)
                 <= followers.RUIN_REACH)
    place.status["burned"] = game.moment.total_days - 3
    game.player.local_key = None
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    homeless = [n for n in npcs_in(w, town.id) if n.flags.get("follower") == "refugee" and n.flags.get("from") == place.id]
    if not homeless:
        pytest.skip("no room at the inn")
    npc = homeless[0]
    assert place.name in npc.title and npc.alive
    conv = talk(game, npc)
    choice = recruit_choices(conv, "refugee")[0]
    assert choice.enabled and "keep" in choice.label
    conv.choose(choice)
    c = game.party[-1]
    assert comp.bond_of(c) == "refugee" and place.name in comp.bond_text(game, c)


def test_admirers_seek_out_the_famous(game, monkeypatch):
    from realmwalker.game import followers

    game.renown.fame = 40
    monkeypatch.setattr(RNG, "chance", lambda self, p: True)
    s = to_town(game, "town")
    admirers = [n for n in npcs_in(game.world, s.id) if n.flags.get("follower") == "admirer"]
    if not admirers:
        pytest.skip("no room at the inn")
    monkeypatch.undo()
    conv = talk(game, admirers[0])
    conv.choose(recruit_choices(conv, "admirer")[0])
    c = game.party[-1]
    assert comp.bond_of(c) == "admirer" and c.companion["loyalty"] >= 70
    game.renown.infamy = 80
    loyalty = c.companion["loyalty"]
    followers.daily(game)
    assert c.companion["loyalty"] < loyalty, "the songs said otherwise"


def test_followers_survive_saving(game, tmp_path, lucky):
    q = a_quest(game)
    npc = a_dreamer(game)
    conv = talk(game, npc)
    conv.choose(recruit_choices(conv, "dream")[0])
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    c = loaded.party[-1]
    assert comp.bond_of(c) == "dreamer" and c.companion["work"] == q["id"]
    assert comp.pay_word(loaded, c) == "for a share"


def test_a_companion_is_not_also_standing_in_town(game):
    """They were: a hired traveller's townsperson came back to the inn by day while travelling with you."""
    from realmwalker.game.people import update_positions

    c, npc, s = hire_one(game)
    for _ in range(8):
        game.world.time += 6 * 60
        update_positions(game, game.local)
        assert not npc.present
    comp.dismiss(game, c)
    game.world.time += 24 * 60 - game.moment.hour * 60 + 12 * 60  # noon, some day
    update_positions(game, game.local)
    assert npc.present, "home again once they leave you"
