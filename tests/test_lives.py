"""Lives of townsfolk (Expansion 6 C.4): the notables and a dozen others of the towns near the hero carry ties, a
want, a fear, secrets and things of note; their words come from the life; each week a few life events happen in the
towns within reach, and they show by themselves (black dress, a shut shop with a sign, a new grave, a crowd)."""

import pytest

from realmwalker.game import townlife
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.story import check, lives
from realmwalker.world.tables import Tables
from tests.test_first_hour import SEEDS, a_life


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def test_the_data_names_only_what_the_game_knows(tables):
    assert lives.problems(tables) == []
    assert not [p for p in check.problems(tables) if "lives.json" in p]


@pytest.mark.parametrize("seed", SEEDS)
def test_the_notables_and_a_dozen_others_have_lives(tables, seed):
    game, town = a_life(tables, seed)
    folk = [n for n in npcs_in(game.world, town.id) if n.alive]
    with_life = [n for n in folk if "life" in n.flags]
    assert all("life" in n.flags for n in folk if n.notable and not n.flags.get("visitor")
               and n.job not in ("wayfarer", "adventurer", "pilgrim"))
    assert len([n for n in with_life if not n.notable]) <= tables.lives["others"]
    assert len(with_life) >= min(len(folk), 6)
    kinds = set(lives.KIN_OF) | set(tables.lives["ties"])
    for n in with_life:
        lf = n.flags["life"]
        assert set(lf) >= {"ties", "want", "fear", "secrets", "things", "events"}
        for t in lf["ties"]:
            assert t["kind"] in kinds and t["name"] and t["state"] in ("alive", "dead", "levied")
            if t["npc"] is not None:
                assert t["npc"] in game.world.npcs
        if lf["want"] and not n.flags.get("grudge"):
            vals = lives.values(game, n)
            options = [lives.fill(w, vals) for w in tables.lives["wants"][lf["want"]]["words"]]
            assert n.profile["want"] in options, "the words townsfolk carry are written from the life"
        assert "{" not in n.profile.get("want", "") + n.profile.get("fear", "") + n.profile.get("secret", "")
    assert lives.ensure(game, town.id) == 0, "made once"
    # Those under one roof are tied by who they are.
    tied = [t for n in with_life for t in n.flags["life"]["ties"] if t["npc"] is not None and t["kind"] in lives.KIN_OF]
    houses = {}
    for n in folk:
        houses.setdefault(tuple(n.home), []).append(n)
    if any(len(h) > 1 and any("life" in m.flags for m in h) for h in houses.values()):
        assert tied, "a household's people are kin by name and by id"


def test_hidden_members_keep_their_faith_secret(tables):
    game, town = a_life(tables, SEEDS[0])
    w = game.world
    cult = next((f for f in w.factions.values() if f.kind in ("cult", "thieves_guild")), None)
    if cult is None:
        pytest.skip("no cult or thieves in this world")
    npc = next(n for n in npcs_in(w, town.id) if "life" in n.flags and not n.notable)
    npc.flags["secret"] = cult.id
    del npc.flags["life"]
    lives.ensure(game, town.id)
    secrets = npc.flags["life"]["secrets"]
    assert secrets[0]["kind"] == ("faith" if cult.kind == "cult" else "guild") and secrets[0]["faction"] == cult.id
    vals = lives.values(game, npc)
    assert npc.profile["secret"] in [lives.fill(x, vals) for x in tables.lives["secrets"][secrets[0]["kind"]]["words"]]


def _old_one(game, town):
    w = game.world
    folk = [n for n in npcs_in(w, town.id) if n.alive and "life" in n.flags and not n.flags.get("figure")]
    npc = max(folk, key=lambda n: sum(t["npc"] is not None for t in n.flags["life"]["ties"]))
    kin = next((t for t in npc.flags["life"]["ties"] if t["npc"] is not None and t["kind"] in lives.KIN_OF), None)
    if kin is None:  # (make one: a son living with them)
        other = next(n for n in folk if n is not npc)
        npc.flags["life"]["ties"].append(lives._tie("son", other.first_name, npc=other.id))
        other.flags["life"]["ties"].append(lives._tie("father", npc.first_name, npc=npc.id))
        kin = npc.flags["life"]["ties"][-1]
    npc.age = 90
    return npc, w.npcs[kin["npc"]]


@pytest.mark.parametrize("seed", SEEDS)
def test_a_death_shows_by_itself(tables, seed):
    game, town = a_life(tables, seed)
    w = game.world
    npc, mourner = _old_one(game, town)
    graves = len(game.local.meta.get("graves") or [])
    ev = None
    for i in range(40):  # (an old one's own death, not a parent's: by chance)
        ev = lives.happen(game, town, npc, "death_of_age", w.rng.child(f"t/{i}"))
        if not npc.alive:
            break
    assert not npc.alive and ev.get("self"), "the old one died, through the people code"
    assert len(game.local.meta["graves"]) == graves + 1, "a fresh grave in the graveyard"
    assert mourner.flags["dress"] == "mourning", "the family wear black"
    assert townlife.activity(game, mourner) == "home", "and keep to the house the first days"
    mev = mourner.flags["life"]["events"][-1]
    assert mev["kind"] == "death_of_age" and mev["name"] == npc.first_name
    told = lives.note(game, mourner)
    assert told and npc.first_name in told and "{" not in told
    conv = Conversation(game, mourner)
    mourner.known = True
    conv.choose(next(c for c in conv.menu() if c.id == "who"))
    if mourner.mood() not in ("hostile", "unfriendly"):
        assert any(npc.first_name in text for _, text in conv.lines), "they tell you of it"
    said = [townlife._words_for(game, mourner, r) for r in range(0, 200, 7)]
    assert any(s and s in [lives.fill(b, lives._event_vals(game, mourner, mev))
                           for b in tables.lives["events"]["death_of_age"]["bark"]] for s in said)
    g = town_flags(game, town)["life_gathering"]
    assert mourner.id in g["ids"] and len(g["ids"]) > 1, "a crowd stands round the grave"
    # The next morning the crowd forms through townlife; when its hours are over it goes.
    game.world.time = int(g["from"]) + 30
    townlife.tick(game, game.local, town)
    assert town_flags(game, town)["gathering"]["life"] == "death_of_age"
    game.world.time = int(g["until"]) + 1
    townlife.tick(game, game.local, town)
    assert "gathering" not in town_flags(game, town) and "life_gathering" not in town_flags(game, town)
    # Weeks later the black is put away.
    game.world.time += 40 * 1440
    lives.daily(game)
    assert "dress" not in mourner.flags and "life_show" not in mourner.flags


def town_flags(game, town):
    return game.world.towns[town.id].flags


def test_a_shut_shop_has_a_sign(tables):
    game, town = a_life(tables, SEEDS[0])
    from realmwalker.game import economy

    w = game.world
    keeper = next(n for n in npcs_in(w, town.id) if n.alive and economy.shop_spec(game, n) is not None
                  and n.building >= 0)
    if "life" not in keeper.flags:
        keeper.flags["life"] = lives.make(game, keeper, [], [keeper], w.rng.child("x"))
    lives.happen(game, town, keeper, "sickness", w.rng.child("sick"))
    assert lives.sign(game, keeper) in tables.lives["events"]["sickness"]["sign"]
    conv = Conversation(game, keeper)
    trade = next((c for c in conv.menu() if c.id == "trade"), None)
    assert trade is not None and not trade.enabled, "the shop is shut"
    shop = game.local.buildings[keeper.building]
    assert "shut" in lives.walk_in(game, game.local, shop)
    game.world.time += 12 * 1440
    lives.daily(game)
    assert lives.sign(game, keeper) is None
    assert next(c for c in Conversation(game, keeper).menu() if c.id == "trade").enabled


def test_weddings_births_and_the_rest(tables):
    game, town = a_life(tables, SEEDS[1])
    w = game.world
    folk = [n for n in npcs_in(w, town.id) if n.alive and "life" in n.flags]
    npc = folk[0]
    lf = npc.flags["life"]
    lf["ties"] = [t for t in lf["ties"] if lives.KIN_OF.get(t["kind"]) != "spouse"]
    npc.age = 25
    ev = lives.happen(game, town, npc, "marriage", w.rng.child("wed"))
    assert ev and lives._has(lf, "spouse")
    npc.flags.pop("life_show")
    if npc.sex == "male":
        lives._tie_of(lf, "spouse")["age"] = 24
    ev = lives.happen(game, town, npc, "birth", w.rng.child("born"))
    assert ev and any(t.get("age") == 0 and t["name"] == ev["name"] for t in lf["ties"])
    temple = lives._temple_door(game, town)
    if temple is not None:
        assert town_flags(game, town)["life_gathering"]["kind"] == "birth"
    lf["things"].append({"kind": "heirloom", "words": "a ring", "state": "kept"})
    ev = lives.happen(game, town, npc, "theft", w.rng.child("theft"))
    assert ev["thing"] == tables.lives["things"]["heirloom"]["short"] or lf["things"]
    lf["secrets"].append({"kind": "lover", "to": "Odo", "known": False})
    assert lives.happen(game, town, npc, "love_found_out", w.rng.child("found"))
    assert lf["secrets"][-1]["known"]
    for e in lf["events"]:
        line = lives.fill(tables.lives["events"][e["kind"]]["note"][0], lives._event_vals(game, npc, e))
        assert "{" not in line, line


@pytest.mark.parametrize("seed", SEEDS)
def test_weeks_of_lives_near_the_hero(tables, seed):
    game, town = a_life(tables, seed)
    w = game.world
    from realmwalker.game.people import prepare_town

    far = max(w.settlements, key=lambda s: max(abs(s.x - town.x), abs(s.y - town.y)))
    prepare_town(game, far)
    far_lives = {n.id: len(n.flags["life"]["events"]) for n in npcs_in(w, far.id) if "life" in n.flags}
    seen = []
    for _ in range(30):
        game.world.time += 7 * 1440
        happened = lives.week(game)
        per = {}
        for sid, _, kind in happened:
            per[sid] = per.get(sid, 0) + 1
            assert kind in tables.lives["events"]
        assert all(v <= tables.lives["per_town"] for v in per.values()), "at most three a town"
        assert far.id not in per or max(abs(far.x - town.x), abs(far.y - town.y)) <= tables.lives["reach"]
        seen += happened
        lives.daily(game)
    assert len(seen) >= 3, "the weeks bring life events"
    assert len({k for _, _, k in seen}) >= 2
    if max(abs(far.x - town.x), abs(far.y - town.y)) > tables.lives["reach"]:
        assert {n.id: len(n.flags["life"]["events"]) for n in npcs_in(w, far.id) if "life" in n.flags} == far_lives
    assert all(isinstance(ev, dict) for _, ev in lives.seeds(game, town.id))
