"""Favours and contacts (Expansion 6 C.7, docs/ADVENTURES.md §8.10): a favour owed is called in as a way through
someone else's obstacle, or for a hiding place; a contact sends word, warns you of the watch, opens the door at night
and deals as their kind does; both are in the journal's People tab."""

import pytest

from realmwalker.game import economy, law, services, townlife
from realmwalker.game.dialogue import Conversation
from realmwalker.game.law_talk import realm_of_npc
from realmwalker.game.people import is_day, npc_factions, npcs_in, prepare_town
from realmwalker.game.story import check, favours, goals, situations
from realmwalker.rules.inventory import add_item
from realmwalker.world.tables import Tables
from tests.test_first_hour import SEEDS, a_life
from tests.test_situations import forced, talk


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture
def life(tables):
    townlife.forget()
    return a_life(tables, SEEDS[0])


def owe(game, npc, kind="word", weight=1) -> dict:
    fav = {"from": npc.id, "weight": weight, "kind": kind, "day": int(game.moment.total_days), "used": False,
           "situation": None}
    game.renown.legend.setdefault("favours", []).append(fav)
    return fav


def befriend(game, npc, kind) -> dict:
    rec = {"npc": npc.id, "kind": kind, "since": int(game.moment.total_days)}
    game.renown.legend.setdefault("contacts", []).append(rec)
    return rec


def someone(game, town, but=()):
    return next(n for n in npcs_in(game.world, town.id) if n.alive and n.id not in but and not n.flags.get("story"))


def said(game) -> str:
    return " ".join(m.text for m in game.log.messages)


def test_the_data_reads_right(tables):
    assert check.problems(tables) == []
    blocks = [ob for p in situations.predicaments(tables).values() for ob in p.get("obstacles", []) if ob.get("favour")]
    assert len(blocks) >= 12, "most obstacles can be opened by a favour"


def test_a_favour_pays_a_debt(life):
    game, town = life
    sit = forced(game, town, "promise_unkept")
    situations.met(game, sit)
    asker, creditor = situations.asker(game, sit), situations._npc(game, sit, "creditor")
    talk(game, asker, "sit_take")
    fav = owe(game, asker, "goods", 2)
    money = game.leader.money
    talk(game, creditor, "fav_call")
    assert fav["used"] and fav["used_day"] == int(game.moment.total_days) and fav["spent_on"] == sit["id"]
    assert sit["state"] == "done" and sit["ending"] == "kept_favour", "the ending knows a name opened the way"
    assert goals.way_used(sit, "favour")
    assert game.leader.money == money, "a favour costs no coin"
    assert not favours.owed(game), "and it is spent"


def test_a_favour_too_light_or_out_of_reach_is_not_offered(life):
    game, town = life
    sit = forced(game, town, "promise_unkept")
    situations.met(game, sit)
    asker, creditor = situations.asker(game, sit), situations._npc(game, sit, "creditor")
    talk(game, asker, "sit_take")
    owe(game, asker, "goods", 1)  # (the debt needs a heavier one)
    owe(game, asker, "shelter", 3)  # (and shelter does not pay debts)
    assert not [c for c in Conversation(game, creditor).menu() if c.id == "fav_call"]
    far = next((s for s in game.world.settlements if s.id != town.id and s.kind in ("village", "town")), None)
    prepare_town(game, far)
    stranger = next(n for n in npcs_in(game.world, far.id) if n.job != creditor.job and n.alive)
    if {f.id for f in npc_factions(game, stranger)} & {f.id for f in npc_factions(game, creditor)}:
        pytest.skip("the stranger shares a guild with the creditor")
    owe(game, stranger, "goods", 3)
    assert not [c for c in Conversation(game, creditor).menu() if c.id == "fav_call"], "out of reach"
    same_trade = next((n for n in game.world.npcs.values() if n.job == creditor.job and n.settlement != town.id), None)
    if same_trade is not None:
        owe(game, same_trade, "goods", 2)
        assert [c for c in Conversation(game, creditor).menu() if c.id == "fav_call"], "their own trade reaches"


def test_a_shelter_favour_hides_the_wanted(life):
    game, town = life
    npc = someone(game, town)
    realm = realm_of_npc(game, npc)
    if realm is None:
        pytest.skip("a town under no realm")
    owe(game, npc, "shelter", 1)
    assert not [c for c in Conversation(game, npc).menu() if c.id == "fav_hide"], "nobody hides one nobody wants"
    game.renown.bounties[realm.id] = 1000
    day = game.moment.total_days
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "fav_hide"))
    assert game.renown.bounties[realm.id] == 500
    assert game.moment.total_days >= day + 2 and not favours.owed(game)


def test_a_contact_warns_you_of_the_watch(life):
    game, town = life
    npc = someone(game, town)
    realm = realm_of_npc(game, npc)
    if realm is None:
        pytest.skip("a town under no realm")
    befriend(game, npc, "informant")
    game.renown.bounties[realm.id] = 500
    favours.on_enter_town(game, town)
    assert favours.warned(game, realm.id)
    assert npc.first_name in said(game), "a runner brings the word"
    game.world.time += 25 * 60
    assert not favours.warned(game, realm.id), "a warning holds for a day"


def test_a_report_brings_a_letter(life):
    game, town = life
    npc = someone(game, town)
    realm = realm_of_npc(game, npc)
    if realm is None:
        pytest.skip("a town under no realm")
    rec = befriend(game, npc, "fence")
    game.leave_local()
    far = max(game.world.settlements, key=lambda s: abs(s.x - town.x) + abs(s.y - town.y))
    game.player.x, game.player.y = far.x, far.y
    game.renown.bounties[realm.id] = 500
    favours.on_report(game, realm.id)
    assert rec["warn"] == [realm.id]
    favours.daily(game)
    assert "warn" not in rec and favours.warned(game, realm.id)
    assert npc.first_name in said(game)


def test_letters_come_while_you_are_away(life):
    game, town = life
    npc = someone(game, town)
    rec = befriend(game, npc, "informant")
    game.leave_local()
    favours.daily(game)
    first = rec["next_letter"]
    assert 10 <= first - game.moment.total_days <= 20
    before = len(game.log.messages)
    game.world.time += (first - game.moment.total_days) * 24 * 60
    favours.daily(game)
    assert len(game.log.messages) > before and npc.first_name in said(game)
    assert rec["next_letter"] > first


def test_an_informant_points_at_a_trouble(life):
    game, town = life
    sit = forced(game, town, "promise_unkept")
    asker = situations.asker(game, sit)
    npc = someone(game, town, but={asker.id})
    befriend(game, npc, "informant")
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "contact_ask"))
    assert any(asker.first_name in text for who, text in conv.lines if who == "npc")
    again = next(c for c in Conversation(game, npc).menu() if c.id == "contact_ask")
    assert not again.enabled, "once a day"


def test_a_contact_lets_you_in_at_night(life):
    game, town = life
    lm = game.local
    home = None
    for n in npcs_in(game.world, town.id):
        for bi, b in enumerate(lm.buildings):
            if b.kind in law.CONFINED_BUILDINGS and b.x <= n.home[0] < b.x + b.w and b.y <= n.home[1] < b.y + b.h:
                home = (n, bi)
                break
        if home:
            break
    if home is None:
        pytest.skip("nobody lives in a house here")
    n, bi = home
    while is_day(game):
        game.world.time += 60
    n.x, n.y = n.home
    crimes = len(game.renown.crimes)
    befriend(game, n, "healer")
    assert favours.opens_at_night(game, n)
    law.trespass_check(game, bi)
    assert len(game.renown.crimes) == crimes, "a friend's house is no trespass"


def test_contacts_deal_as_their_kind_does(life):
    game, town = life
    smith = next((n for n in npcs_in(game.world, town.id) if economy.shop_spec(game, n)
                  and "weapon" in economy.shop_spec(game, n)["buys"]), None)
    if smith is not None:
        stolen = add_item(game.leader, game.tables.items, "dagger", tags=["stolen"])
        assert economy.sell_price(game, smith, stolen)[0] is None
        befriend(game, smith, "fence")
        assert economy.sell_price(game, smith, stolen)[0] is not None, "a fence you know buys it"
    other = someone(game, town, but={smith.id} if smith else ())
    before = {s.id for s in services.services_for(game, other)}
    befriend(game, other, "healer")
    after = {s.id for s in services.services_for(game, other)}
    assert {"treat_wounds", "surgery", "herbal_cure"} <= after
    assert before <= after
    assert favours.discount(game, other) < 1.0


def test_the_people_tab_lists_them(life, make_app):
    from realmwalker.ui.screens.journal import PEOPLE, JournalScreen, person_lines

    game, town = life
    npc = someone(game, town)
    owe(game, npc, "door", 2)
    befriend(game, npc, "scholar")
    screen = JournalScreen(make_app(), game, tab=PEOPLE)
    rows = screen.rows()
    assert rows[0] == ("group", "Favours and contacts") and rows[1] == ("quest", npc)
    assert rows.count(("quest", npc)) == 1
    text = person_lines(game, npc)
    assert "favour" in text and "contact" in text
