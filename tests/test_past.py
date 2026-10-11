"""The past in play (2026-10): what the lived history (world/ages) gives the game.

Ruins say what they were; barrows whose they are; towns when they were founded and what befell them; townsfolk tell
of it; heroes of the history sit in the inns; named beasts wait in their lairs and are remembered when they die; the
dead king in a barrow has his own name; towns pay to be rid of the beast that killed their people; history books
quote the world's own chronicles; the AI is told the truth.
"""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import dungeon, past, quests
from realmwalker.game.describe import describe_overworld
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.rules.creatures import spawn
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Pastland", 33, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def result(dead=()):
    return SimpleNamespace(outcome="victory", dead=list(dead), captives=[], fled=[], xp=0)


def stand_on(game, thing):
    game.player.x, game.player.y = thing.x, thing.y
    game.player.explored[thing.x, thing.y] = True


# ---------------------------------------------------------------------------- places say what they were
def test_ruins_and_barrows_tell_their_past(game):
    w = game.world
    ruins = [s for s in w.sites if s.kind == "ruin" and not w.politics["ruins"][str(s.id)].get("elder")]
    assert ruins
    site = ruins[0]
    stand_on(game, site)
    text = describe_overworld(game, site.x, site.y)
    past_of = w.politics["ruins"][str(site.id)]
    assert "Once" in text and str(past_of["fell"]) in text
    barrows = [s for s in w.sites if str(s.id) in w.politics.get("tombs", {})]
    if barrows:
        stand_on(game, barrows[0])
        fig = w.figures[w.politics["tombs"][str(barrows[0].id)]]
        assert fig.full_name() in describe_overworld(game, barrows[0].x, barrows[0].y)


def test_towns_remember_their_founding_and_their_troubles(game):
    w = game.world
    town = max(w.settlements, key=lambda s: len(past.great_events(game, s, 6)))
    stand_on(game, town)
    text = describe_overworld(game, town.x, town.y)
    assert "Founded in" in text
    assert past.great_events(game, town)
    game.enter_local()
    folk = [n for n in npcs_in(w, town.id) if n.alive and n.job not in ("guard",)]
    said = []
    for npc in folk[:6]:
        npc.disposition = 40
        conv = Conversation(game, npc)
        conv.choose(next(c for c in conv.menu() if c.id == "place"))
        said += [text for _, text in conv.lines]
    assert any(e["text"][:12].lower() in line.lower() for line in said for e in past.great_events(game, town, 6)), \
        said


# ---------------------------------------------------------------------------- the masters of the old places
def a_lair(game):
    for site_id, hid in game.world.politics.get("lairs", {}).items():
        fig = game.world.figures[hid]
        if fig.kind == "beast":
            return game.world.sites[int(site_id)], fig
    pytest.skip("no named beast in this world")


def test_a_named_beast_waits_in_its_lair_and_its_death_is_remembered(game):
    site, beast = a_lair(game)
    stand_on(game, site)
    assert beast.name in past.site_past(game, site)
    game.enter_local()
    dungeon.descend(game, 1)
    deepest = int(game.local.meta.get("depth", 1))
    while int(game.local.meta.get("level", 1)) < deepest:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)
    named = [c for a in game.local.actors for c in a.creatures if getattr(c, "named", False)]
    assert named and named[0].name == past.beast_title(beast), [a.group for a in game.local.actors]
    fame = game.renown.fame
    past.on_battle(game, result(dead=named[:1]))
    assert not beast.alive and str(site.id) not in game.world.politics["lairs"]
    assert game.renown.fame > fame
    assert any(e.get("player") and e["kind"] == "beast_slain" and beast.name in e["text"]
               for e in game.world.history)


def test_the_dead_king_in_the_barrow_has_a_name(game):
    w = game.world
    barrows = [s for s in w.sites if s.kind == "barrow" and str(s.id) in w.politics.get("tombs", {})
               and dungeon.gen.style_for(w, s) == "crypt"]
    if not barrows:
        pytest.skip("no tomb in this world")
    site = barrows[0]
    fig = w.figures[w.politics["tombs"][str(site.id)]]
    group, name = past.boss_for(game, site, "barrow_wight")
    assert group == "barrow_wight" and name == fig.full_name()
    stand_on(game, site)
    wight = spawn(game.tables, "wight", RNG(2), 1)
    wight.name, wight.named = name, True
    past.on_battle(game, result(dead=[wight]))
    assert any(e.get("player") and e["kind"] == "laid_to_rest" for e in w.history)


def test_a_town_pays_to_be_rid_of_the_beast_that_killed_its_people(game):
    w = game.world
    lairs = [(w.sites[int(k)], w.figures[h]) for k, h in w.politics.get("lairs", {}).items()
             if w.figures[h].kind == "beast"]
    near = [s for s in w.settlements if any(3 <= quests.dist(s, site) <= 16 for site, _ in lairs)]
    if not near:
        pytest.skip("nobody lives near a lair")
    for s in near[:6]:
        prepare_town(game, s)
        for npc in npcs_in(w, s.id)[:8]:
            for i in range(8):
                q = quests._clear_lair(game, npc, RNG(i, "lair"))
                if q and q.get("text_key") == "clear_lair_beast":
                    beast = w.figures[q["target"]["beast"]]
                    assert q["words"]["beast"] == past.beast_title(beast)
                    text = quests.pitch(game, q)
                    assert q["words"]["beast"] in text and "{" not in text
                    return
    pytest.skip("no offer came up")


# ---------------------------------------------------------------------------- people of the history
def test_heroes_of_the_history_drink_in_their_home_inns(game):
    w = game.world
    heroes = [f for f in w.figures.values() if f.alive and f.kind == "person" and f.job in ("adventurer", "hero")
              and f.home.startswith("S")]
    if not heroes:
        pytest.skip("no living hero in this world")
    for hero in heroes:
        town = w.settlements[int(hero.home[1:])]
        stand_on(game, town)
        game.enter_local()
        met = [n for n in npcs_in(w, town.id) if n.flags.get("figure") is not None
               and w.figures[n.flags["figure"]].job in ("adventurer", "hero")]
        if met:
            npc = met[0]
            assert npc.flags.get("recruit") and npc.title and npc.profile["backstory"]
            return
        game.leave_local() if hasattr(game, "leave_local") else None
    pytest.skip("no hero lives where there is an inn")


def test_a_town_knows_its_true_past(game):
    w = game.world
    town = max(w.settlements, key=lambda s: len(past.great_events(game, s, 6)))
    assert "Founded in" in past.place_past(game, town)


def test_history_books_quote_the_world_s_own_chronicles(game):
    from realmwalker.game import books

    w = game.world
    assert w.politics.get("works")
    said = []
    for i in range(12):
        said += books._history(game, RNG(i, "book"), True)
    assert any("It is a copy of" in line for line in said)
    assert not any(".." in line for line in said)


# ---------------------------------------------------------------------------- a new character's ties to the past
def hero_of(tables, background: str, seed: int = 1):
    from realmwalker.rules.creation import CharacterBuilder

    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background(background)
    return b.build()


def test_a_soldier_marched_in_a_real_war(game, tables):
    from realmwalker.rules.creation import make_ties

    w = game.world
    for s in w.settlements:
        tie = make_ties(w, tables, hero_of(tables, "soldier"), s.id, RNG(s.id, "ties"))[0]
        if "war" in tie["refs"]:
            war = next(x for x in w.wars if x["id"] == tie["refs"]["war"])
            assert war["name"] in tie["text"] and "{" not in tie["text"]
            return
    pytest.skip("no lord here fought a war in living memory")


def test_a_folk_hero_drove_off_a_real_beast_or_raiders(game, tables):
    from realmwalker.rules.creation import make_ties

    w = game.world
    year = game.moment.year
    struck = {p for e in w.history if e["kind"] in ("beast_attack", "dragon", "raid", "burned") and
              year - e["year"] <= 25 for p in e.get("places", ())}
    if not struck:
        pytest.skip("nothing troubled any village in living memory")
    sid = sorted(struck)[0]
    tie = make_ties(w, tables, hero_of(tables, "folk_hero"), sid, RNG(3, "ties"))[0]
    assert "foe" in tie["refs"] or "foe_faction" in tie["refs"]
    foe = w.figures[tie["refs"]["foe"]].name if "foe" in tie["refs"] else w.factions[tie["refs"]["foe_faction"]].name
    assert foe in tie["text"]


def test_a_noble_knows_whom_their_house_is_sworn_to(game, tables):
    from realmwalker.rules.creation import make_ties
    from realmwalker.world import factions as fx

    w = game.world
    house = fx.active_factions(w, "noble_house")[0]
    tie = make_ties(w, tables, hero_of(tables, "noble"), house.seat, RNG(4, "ties"))[0]
    lord = w.factions[tie["refs"]["sworn_to"]]
    assert lord.name in tie["text"] and fx.leader_of(w, lord).full_name() in tie["text"]
    assert "faction" not in tie["refs"]  # their own small house is made for them (game/reputation)


# ---------------------------------------------------------------------------- the beasts go on, and the dead walk
def test_beasts_of_the_history_come_down_while_you_play(game, tables):
    from realmwalker.world.politics import BEAST_REACH, Politics, year_of

    w = game.world
    lairs =[(int(k), w.figures[h]) for k, h in w.politics.get("lairs", {}).items() if w.figures[h].kind == "beast"]
    lairs = [(k, f) for k, f in lairs if any(abs(s.x - w.sites[k].x) + abs(s.y - w.sites[k].y) <= BEAST_REACH
                                             and s.kind in ("hamlet", "village", "town") for s in w.settlements)]
    if not lairs:
        pytest.skip("no named beast with anyone to trouble in this world")
    engine = Politics(w, tables, RNG(5, "beasts"), year=year_of(w, tables))
    before = len(w.news)
    for site_id, fig in lairs:
        engine.beast_comes(fig, site_id)
    assert len(w.news) > before
    assert any(s.status.get("beast") for s in w.settlements)
    assert tables.politics["rates"]["beast_attack"] > 0


def test_heroes_of_the_history_grow_old_while_you_play(game, tables):
    from realmwalker.world.politics import Politics, year_of

    w = game.world
    heroes = [f for f in w.figures.values() if f.alive and f.kind == "person" and f.role == "hero"]
    if len(heroes) < 2:
        pytest.skip("fewer than two living heroes in this world")
    old, friend = heroes[:2]
    year = year_of(w, tables)
    old.born = friend.born = year - 120  # older than anyone lives
    old.fame, old.home = max(old.fame, 5), "S0"
    prepare_town(game, w.settlements[0])
    walker = next(n for n in npcs_in(w, 0) if n.alive)
    walker.flags["companion"] = True  # this one was hired and walks with the player
    friend.npc = walker.id
    before = len(w.news)
    Politics(w, tables, RNG(6, "years"), year=year).mortality(50.0)
    assert not old.alive and old.cause
    assert any(old.full_name() in n["text"] for n in w.news[before:])  # people had heard of this one
    assert friend.alive


def test_the_dead_of_the_great_battles_walk_at_night(game, monkeypatch):
    from realmwalker.game import encounters

    w = game.world
    scars = [s for s in w.politics.get("scars", []) if s["kind"] == "battle"]
    if not scars:
        pytest.skip("no great battle left its dead")
    scar = scars[0]
    game.player.x, game.player.y = scar["x"], scar["y"]
    game.player.explored[scar["x"], scar["y"]] = True
    assert scar["name"].lower() in describe_overworld(game, scar["x"], scar["y"]).lower()
    monkeypatch.setattr(game.__class__, "light", property(lambda self: 0.1))
    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 1.0)
    met = [encounters.roll_encounter(game, 60) for _ in range(12)]
    dead = [m for m in met if m is not None and m.group == "restless_dead"]
    assert dead and any(scar["name"].lower() in m.intro.lower() for m in dead)


def test_blood_feuds_the_history_left(game):
    w = game.world
    grudges = w.politics.get("grudges", [])
    for g in grudges:
        by, against, kin = w.figures[g["by"]], w.figures[g["against"]], w.figures[g["kin"]]
        assert by.alive and against.alive and not kin.alive and kin.slayer == against.id
    living = [g for g in grudges if past.grudge_of(w, g["by"]) is not None]
    if not living:
        pytest.skip("nobody alive has a blood feud in this world")
    g = living[0]
    want = past.grudge_want(game, g)
    assert w.figures[g["against"]].full_name() in want and "{" not in want


def test_a_treasure_of_the_history_lies_where_the_history_left_it(game):
    w = game.world
    arts = [(i, a) for i, a in enumerate(w.politics["artifacts"]) if a["site"] >= 0 and not a.get("found")]
    if not arts:
        pytest.skip("no treasure lies anywhere in this world")
    i, a = arts[0]
    site = w.sites[a["site"]]
    stand_on(game, site)
    game.enter_local()
    dungeon.descend(game, 1)
    while int(game.local.meta.get("level", 1)) < int(game.local.meta.get("depth", 1)):
        dungeon.descend(game, int(game.local.meta["level"]) + 1)
    spots = [(xy, f) for xy, f in game.local.features.items() if f.get("artifact") == i]
    assert spots, "the treasure is not down there"
    (x, y), feature = spots[0]
    feature["locked"] = 0
    game.player.lx, game.player.ly = x, y
    dungeon.open_chest(game, game.local, x, y)
    found = [it for pile in game.local.items.values() for it in pile if it.magic and it.magic.get("source") == "history"]
    assert found and found[0].magic["title"].lower() == a["name"].lower()
    assert a["found"] and any(e.get("player") and e["kind"] == "artifact_found" for e in w.history)
