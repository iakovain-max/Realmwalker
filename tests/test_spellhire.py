"""Spellcasting for pay, scrolls in temples and mages' shops, the law of magic (Expansion 3 G.2, PHB 2024 p. 232).

A temple's priest and a town's mage cast what would do the party some good for the book's price; everything they
offer is cast in a real town and does its work; the hired caster breaks no law; a mage where magic is forbidden casts
only unseen; the mages live where the circle keeps a house and sell scrolls by rarity."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import economy, law, magic, magic_items, revival, services, spellhire
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules import spells as sp
from realmwalker.rules import wounds
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.inventory import add_existing
from realmwalker.world import factions as fx
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Hireland", 43, "small"), tables)


def hero(tables, cls="fighter", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("soldier")
    return b.build()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables, hero(tables))
    friend = hero(tables, "fighter", seed=2)
    friend.is_player = False
    friend.companion = {"loyalty": 60, "wage": 0}
    g.party.append(friend)
    g.survival = False
    from realmwalker.game import pack

    pack.sync(g)
    return g


def into(game, kind="city"):
    s = next(s for s in game.world.settlements if s.kind == kind)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    game.renown.bounties.clear()
    return s


def one(game, s, job):
    return next(n for n in npcs_in(game.world, s.id) if n.job == job and n.alive)


def purse(game):
    return sum(c.money for c in game.party)


# ---------------------------------------------------------------------------- prices and reach
def test_the_price_is_the_books_table_and_the_component(game, tables):
    s = into(game)
    priest = one(game, s, "priest")
    priest.flags.pop("price_mod", None)
    table = tables.economy["services"]["spellcasting"]["price"]
    assert table == [3000, 5000, 20000, 30000, 200000, 200000, 2000000, 2000000, 2000000, 10000000]
    neutral = services.fee(game, priest, 10000) / 10000
    assert spellhire.price(game, priest, "cure_wounds") == round(5000 * neutral)
    # Raise Dead: level 5 and a diamond worth 500 GP, which the buyer pays for too.
    assert spellhire.component_value(tables, "raise_dead") >= 50000
    assert spellhire.price(game, priest, "raise_dead") == round((200000 + spellhire.component_value(tables, "raise_dead")) * neutral)


def test_how_high_a_spell_can_be_found_depends_on_the_place(game):
    seen = {}
    for kind in ("village", "town", "city"):
        s = into(game, kind)
        for n in npcs_in(game.world, s.id):
            if n.job in ("priest", "mage"):
                r = spellhire.reach(game, n)
                seen.setdefault(kind, []).append(r)
                cap = 2 if kind == "village" else 5 if kind == "town" else 9
                assert 0 <= r <= cap, (kind, n.job, r)
                if "figure" in n.flags:
                    assert r == cap
                assert r == spellhire.reach(game, n), "the same each time"
    assert seen.get("city") and min(seen["city"]) >= 5
    assert spellhire.caster_level(9) == 17 and spellhire.caster_level(1) == 1 and spellhire.caster_level(3) == 5


# ---------------------------------------------------------------------------- everything offered is cast
def _hurt(game):
    lead, friend = game.party[0], game.party[1] if len(game.party) > 1 else None
    lead.hp = max(1, lead.max_hp // 2)
    if not lead.wounds:
        w = wounds.make_wound("left_arm", "slashing", 2, RNG(1, "w"), now=game.world.time)
        if w is not None:
            lead.wounds.append(w)
    if not lead.diseases:
        lead.diseases.append({"id": "dysentery", "phase": "sick"})
    if friend is not None and friend.alive:  # (a body to raise, fresh for Revivify)
        friend.hp = 0
        friend.alive = False
        game.bury_the_dead()
    if not magic.strange_things(game, lead):
        for i in range(50):
            it = magic_items.make(game, RNG(i, "strange"), kind="jewellery", rarity="uncommon")
            if it is not None:
                it.magic["identified"] = False
                it.magic["cursed"] = False
                add_existing(lead, game.tables.items, it)
                break
    lead.effects["kept:mummy_rot"] = 1  # (Remove Curse lifts it)


@pytest.mark.slow
@pytest.mark.parametrize("job", ["priest", "mage"])
def test_everything_a_great_caster_offers_is_cast_for_pay(game, monkeypatch, job):
    s = into(game)
    npc = one(game, s, job)
    monkeypatch.setattr(spellhire, "reach", lambda g, n: 9 if n is npc else -1)
    spellhire._OFFERS.clear()
    for c in game.party:
        c.money = 0
    game.leader.money = 10 ** 9
    done = set()
    for _ in range(120):
        _hurt(game)
        offers = [o for o in spellhire.offers(game, npc) if o[3] not in done]
        if not offers:
            break
        arg, label, cost, sid, target = offers[0]
        before = purse(game)
        out = services.perform(game, npc, "spellcasting", arg)
        assert out and "can't" not in out[0], (label, out)
        assert purse(game) == before - cost, (label, before, cost, purse(game))
        assert not game.renown.bounties, (label, "the hired caster broke no law of the party's")
        done.add(sid)
    tables = game.tables
    if job == "priest":
        assert {"cure_wounds", "lesser_restoration", "revivify", "raise_dead", "resurrection", "true_resurrection",
                "aid", "regenerate", "remove_curse", "gentle_repose", "heroes_feast"} <= done, sorted(done)
        assert len(game.party) > 1 or revival.bodies(game)
    else:
        assert {"identify", "darkvision", "water_breathing", "legend_lore"} <= done, sorted(done)
    for sid in done:
        assert job.replace("priest", "cleric").replace("mage", "wizard") in tables.spells[sid]["classes"]
        assert sp.road_use(tables, sid) in spellhire.FOR_HIRE


def test_a_wound_healed_and_a_thing_named_for_coin(game):
    s = into(game)
    priest = one(game, s, "priest")
    mage = one(game, s, "mage")
    game.leader.money = 10 ** 7
    lead = game.leader
    lead.hp = 1
    arg = next(o[0] for o in spellhire.offers(game, priest) if o[3] == "cure_wounds")
    services.perform(game, priest, "spellcasting", arg)
    assert lead.hp > 1
    it = next(i for i in (magic_items.make(game, RNG(k, "x"), kind="jewellery", rarity="uncommon") for k in range(50))
              if i is not None)
    it.magic["identified"] = False
    it = add_existing(lead, game.tables.items, it)
    spellhire._OFFERS.clear()
    offer = next(o for o in spellhire.offers(game, mage) if o[3] == "identify")
    assert offer[4] is not None and getattr(offer[4], "uid", None) == it.uid
    out = services.perform(game, mage, "spellcasting", offer[0])
    assert it.magic["identified"], out
    assert any("Identify" in line for line in out)


def test_nothing_is_offered_that_would_do_nothing(game):
    s = into(game)
    priest = one(game, s, "priest")
    for c in game.party:
        c.hp = c.max_hp
        c.wounds.clear()
        c.diseases.clear()
    sids = {o[3] for o in spellhire.offers(game, priest)}
    assert not sids & {"cure_wounds", "healing_word", "lesser_restoration", "revivify", "raise_dead", "regenerate",
                       "remove_curse"}, sids


# ---------------------------------------------------------------------------- the law of magic
def test_a_mage_where_magic_is_forbidden_casts_only_unseen_and_dearer(game, monkeypatch):
    s = into(game)
    mage = one(game, s, "mage")
    plain = spellhire.price(game, mage, "darkvision")
    monkeypatch.setattr(magic, "magic_forbidden", lambda g, st: True)
    assert spellhire.secret(game, mage)
    assert spellhire.price(game, mage, "darkvision") == round(plain * 1.5) or \
        abs(spellhire.price(game, mage, "darkvision") - plain * 1.5) <= 2
    monkeypatch.setattr(law, "witnesses_here", lambda g, **k: [object()])
    assert "forbidden" in spellhire.refusal(game, mage)
    svc = next(v for v in services.services_for(game, mage) if v.id == "spellcasting")
    assert not svc.enabled and "forbidden" in svc.why
    monkeypatch.setattr(law, "witnesses_here", lambda g, **k: [])
    assert spellhire.refusal(game, mage) == ""
    # ...and no scrolls on open sale but the temple's prayers.
    assert magic.scroll_stock(game, s, RNG(1), tradition="wizard", top=3) == {}
    assert magic.scroll_stock(game, s, RNG(1), tradition="cleric", top=3, lo=3, hi=3)


def test_the_hired_caster_breaks_no_law_but_the_party_does(game, monkeypatch):
    s = into(game)
    monkeypatch.setattr(fx, "laws_of", lambda w, r: {"magic": "forbidden", "religion": "tolerant"})
    monkeypatch.setattr(law, "witnesses_here", lambda g, **k: [one(game, s, "guard")])
    priest = one(game, s, "priest")
    law.magic_check(game, spellhire.caster(game, priest))
    assert not game.renown.bounties
    wizard = hero(game.tables, "wizard", seed=5)
    game.party.append(wizard)
    law.magic_check(game, wizard)
    assert game.renown.bounties
    assert law.party_casts(game)


def test_a_licence_from_a_mage_for_any_caster_in_the_party(game, monkeypatch):
    from realmwalker.game import law_talk
    from realmwalker.game.dialogue import Conversation

    s = into(game)
    monkeypatch.setattr(fx, "laws_of", lambda w, r: {"magic": "licensed", "religion": "tolerant"})
    mage = one(game, s, "mage")
    conv = Conversation(game, mage)
    assert not any(c.id == "licence" for c in law_talk.choices(conv)), "a party of fighters needs none"
    game.party.append(hero(game.tables, "wizard", seed=6))
    assert any(c.id == "licence" for c in law_talk.choices(conv))


# ---------------------------------------------------------------------------- mages and scrolls
def test_mages_live_in_cities_and_sell_the_wizards_scrolls(game, tables):
    s = into(game)
    mages = [n for n in npcs_in(game.world, s.id) if n.job == "mage"]
    assert len(mages) == (3 if getattr(s, "great", False) else 2)
    shop = economy.shop_state(game, mages[0])
    assert shop is not None and shop["kind"] == "mage"
    scrolls = [d for d in shop["stock"] if (tables.items.get(d).get("use") or {}).get("scroll")]
    assert scrolls
    for d in scrolls:
        spell = tables.spells[tables.items.get(d)["use"]["scroll"]]
        assert "wizard" in spell["classes"] and spell["level"] <= 5
    total = {}
    for i in range(40):
        for d, q in magic.scroll_stock(game, s, RNG(i), tradition="wizard", top=5, lo=2, hi=5).items():
            total[d] = total.get(d, 0) + q
    levels = [tables.spells[tables.items.get(d)["use"]["scroll"]]["level"] for d in total for _ in range(total[d])]
    assert sum(1 for lv in levels if lv >= 4) < sum(1 for lv in levels if lv <= 3), "rare scrolls are seldom"
    temple = next(n for n in npcs_in(game.world, s.id) if n.job == "acolyte")
    for _ in range(3):
        stock = economy.restock(game, temple, {"kind": "temple", "stock": {}, "used": [], "coin": 0})["stock"]
        for d in stock:
            if (tables.items.get(d).get("use") or {}).get("scroll"):
                assert "cleric" in tables.spells[tables.items.get(d)["use"]["scroll"]]["classes"]


def test_the_services_list_scrolls_and_shows_a_spells_card(make_app):
    import tcod.console

    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.services import ServicesScreen

    app = make_app()
    world = cached_world(WorldOptions("Hireland", 43, "small"), app.tables)
    game = new_game(copy.deepcopy(world), app.tables, hero(app.tables))
    game.survival = False
    app.start_game(game)
    s = into(game)
    priest = one(game, s, "priest")
    game.leader.money = 10 ** 8
    game.leader.hp = 1
    scr = ServicesScreen(app, game, priest)
    app.push(scr)
    rows = scr.entries()
    scr.pick(next(k for k, r in enumerate(rows) if r[0] == "spellcasting"))
    assert scr.sub is not None and scr.sub.id == "spellcasting"
    app.render(tcod.console.Console(80, 30, order="F"))
    assert "Cure Wounds" in app.last_canvas.words()
    for _ in range(60):
        app.handle_event(KeyEvent("down"))
    assert scr.cur == len(scr.entries()) - 1
    app.render(tcod.console.Console(80, 30, order="F"))
    assert scr.top > 0 or len(scr.entries()) <= scr.shown
    assert scr.tip(scr.entries()[0][0]) is not None
    app.handle_event(KeyEvent("home"))
    assert scr.cur == 0 and scr.top == 0
    hp = game.leader.hp
    scr.cur = next(k for k, r in enumerate(scr.entries()) if r[0].startswith("cure_wounds|"))
    app.handle_event(KeyEvent("enter"))
    assert game.leader.hp > hp and scr.sub is None
    app.render(tcod.console.Console(120, 40, order="F"))
    assert app.error_count == 0
