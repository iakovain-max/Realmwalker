"""The opening of the game, done on purpose rather than at random: a new character in a new world can find
people, food, work, and the way to it. If any of this breaks, a new player is stuck on their first evening."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import economy, quests
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

SEEDS = (3, 42)


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def waiting(game, town):
    """What waits to be taken in the first town (Expansion 6: the bounties on its board, its people's pleas, and the
    contract every peopled town has, C.3)."""
    from realmwalker.game.story import work

    offers = work.offers_here(game, town)
    assert any(q.get("contract") for _, q in offers), "every peopled town has paid work"
    return offers


def a_life(tables, seed):
    world = cached_world(WorldOptions("Firstland", seed, "small"), tables)
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    game = new_game(world, tables, b.build())
    game.survival = False
    from realmwalker.game.story import beats

    beats.director(world)["pending"] = beats.director(world)["opening"] = None  # (the opening: tests below)
    town = min(world.settlements, key=lambda s: abs(s.x - game.player.x) + abs(s.y - game.player.y))
    game.player.x, game.player.y = town.x, town.y
    game.player.local_key = None
    game.enter_local()
    return game, town


@pytest.mark.parametrize("seed", SEEDS)
def test_the_first_town_has_people_money_and_a_shop(tables, seed):
    game, town = a_life(tables, seed)
    folk = [n for n in npcs_in(game.world, town.id) if n.alive]
    assert folk, "the first town you walk into is not empty"
    assert game.leader.money > 0, "you start with something in your purse"
    assert any(economy.shop_spec(game, n) is not None for n in folk), "and somebody will sell you food"


@pytest.mark.parametrize("seed", SEEDS)
def test_there_is_work_in_the_first_town_and_the_map_shows_where(tables, seed):
    game, town = a_life(tables, seed)
    offers = waiting(game, town)
    assert offers, "somebody in the first town wants something doing"
    npc, q = offers[0]
    if npc is not None:
        own = [c for c in Conversation(game, npc).menu() if c.id == "own_work"]
        assert own, "and they ask you for it themselves"
    quests.accept(game, q)
    assert any(x["id"] == q["id"] for x in game.quests), "taking it puts it in the journal"
    assert quests.title(game, q), "and it has a name"
    assert quests.map_marks(game), "and the map is lit where it wants you"


@pytest.mark.parametrize("seed", SEEDS)
def test_you_can_walk_from_the_town_towards_the_work(tables, seed, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    game, town = a_life(tables, seed)
    offers = waiting(game, town)
    assert offers
    quests.accept(game, offers[0][1])
    game.leave_local()
    spot = quests.map_marks(game)[0]
    was = abs(spot[0] - game.player.x) + abs(spot[1] - game.player.y)
    for _ in range(60):
        if game.busy:
            break
        dx = (spot[0] > game.player.x) - (spot[0] < game.player.x)
        dy = (spot[1] > game.player.y) - (spot[1] < game.player.y)
        if (dx, dy) == (0, 0) or not game.move(dx, dy):
            break
    now = abs(spot[0] - game.player.x) + abs(spot[1] - game.player.y)
    assert now < was, f"walking gets you closer to the work ({was} -> {now})"



@pytest.mark.story
@pytest.mark.parametrize("seed", SEEDS)
def test_a_new_life_is_offered_a_tale_on_its_first_day(tables, seed):
    """Expansion 6 (docs/ADVENTURES.md §9, the first hour): within its first game day a new life is offered a hook -
    its opening (a crisis at the gate, a summons, waking as the gang's captive), a beat that asks the hero to take a
    threat on, shown by the game screen as soon as nothing else waits."""
    from realmwalker.game.story import beats, opening

    world = cached_world(WorldOptions("Firstland", seed, "small"), tables)
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    game = new_game(world, tables, b.build())
    game.survival = False
    first = beats.director(game.world).get("opening")
    assert first is not None and first["kind"] in opening.KINDS, "every new life begins with an opening"
    began = game.world.time
    offered = None
    for _ in range(25):
        rec = beats.pending(game)
        if rec is not None and game.tables.beats[rec["beat"]]["family"] == "hook":
            offered = rec
            break
        if rec is not None:
            beats.director(game.world)["pending"] = None  # (another beat: let it pass)
        game.pass_time(60, "rest")
    assert offered is not None, "no tale was offered on the first day"
    assert offered["words"]["threat"] == first["threat"]
    assert offered["beat"] == opening.BEATS[first["kind"]]
    assert game.world.time - began <= 25 * 60


# ---------------------------------------------------------------------------- the three openings (Expansion 6 D.4)
NAMES = ("Ada", "Brann", "Cole", "Dara", "Edda", "Finn", "Gwen", "Hale", "Ivo", "Jory", "Kell", "Lune")


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Forgeland", 77, "medium"), tables)


def _life_near(made, tables, kind: str, background: str = "soldier", far: bool = False):
    """A new life in a copy of the world, beside a threat of `kind` (the others ended), at its nearest town (or one
    well out of its reach)."""
    import copy

    from realmwalker.world import threats

    w = copy.deepcopy(made)
    found = [t for t in threats.records(w).values() if t["kind"] == kind and t["state"] != "ended"]
    if not found:
        pytest.skip(f"no {kind} threat")
    t = found[0]
    for other in threats.records(w).values():
        if other is not t:
            other["state"] = "ended"
    towns = sorted((s for s in w.settlements if s.kind in ("town", "village")),
                   key=lambda s: threats.distance(w, t, s.x, s.y))
    reach = int(tables.threats["kinds"][kind]["reach"])
    if far:
        towns = [s for s in towns if s.id not in t["stakes"][:6] and threats.distance(w, t, s.x, s.y) > reach][:1]
        if not towns:
            pytest.skip("no town out of its reach")
    b = CharacterBuilder(tables, RNG(77, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background(background)
    game = new_game(w, tables, b.build(), start_settlement=towns[0].id)
    game.survival = False
    return game, threats.records(game.world)[t["id"]], towns[0]


def _begin(game, monkeypatch, kind: str):
    from realmwalker.game import story
    from realmwalker.game.story import beats, opening

    monkeypatch.setattr(opening, "choose", lambda *a: kind)
    beats.director(game.world)["pending"] = None
    story.begin(game)
    return beats.director(game.world)["opening"]


def _into_town(game, town):
    from realmwalker.game import townlife
    from tests.test_townlife import at_hour

    townlife.forget()
    at_hour(game, 11)
    game.player.local_key = None
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()


def _until_beat(game):
    from realmwalker.game import townlife
    from realmwalker.game.story import beats

    town = game.world.settlement_at(game.player.x, game.player.y)
    for _ in range(300):
        if beats.pending(game) is not None:
            break
        townlife.tick(game, game.local, town)
    return beats.pending(game)


@pytest.mark.story
def test_the_opening_fits_the_threat_the_hero_and_the_town(made, tables):
    from realmwalker.game.story import opening

    game, t, town = _life_near(made, tables, "beast")
    seen = set()
    for name in NAMES:
        game.leader.name = name
        seen.add(opening.choose(game, t, town))
    assert seen and seen <= {"crisis", "summons"}, f"nobody wakes as a beast's captive: {seen}"
    game, t, town = _life_near(made, tables, "outlaw", background="criminal")
    kinds = set()
    for name in NAMES:
        game.leader.name = name
        kinds.add(opening.choose(game, t, town))
    assert "terror" in kinds, "an outlaw's tale may begin in its ropes"
    game, t, far = _life_near(made, tables, "beast", far=True)
    for name in NAMES[:6]:
        game.leader.name = name
        assert opening.choose(game, t, far) == "summons", "a town out of its reach is sent for, not shut in"
    assert opening.choose(game, t, far) == opening.choose(game, t, far), "the same life, the same opening"


@pytest.mark.story
def test_arriving_into_a_crisis(made, tables, monkeypatch):
    """The gate barred behind you as the bell goes, a crowd in the street round the one who speaks for it; then the
    beat, and the tale taken is the life's opening."""
    from realmwalker.game import story
    from realmwalker.game.story import beats, stage

    game, t, town = _life_near(made, tables, "beast")
    rec = _begin(game, monkeypatch, "crisis")
    assert rec["kind"] == "crisis" and rec["state"] == "waiting" and beats.pending(game) is None
    _into_town(game, town)
    sc = stage.current(game)
    assert sc is not None and sc["id"] == "opening_gate", "the town's people show it"
    pend = _until_beat(game)
    assert pend is not None and pend["beat"] == "opening_crisis" and pend["words"]["threat"] == t["id"]
    assert pend["words"]["start"] == town.name
    text = " ".join(beats.pages(game, pend))
    assert "{" not in text and town.name in text
    out = beats.choose(game, pend, 0)
    adv = next(a for a in story.active(game) if a["threat"] == t["id"])
    assert adv["opening"] == "crisis" and out
    assert rec["state"] == "played"
    game.leave_local()
    beats.director(game.world)["pending"] = None
    _into_town(game, town)
    sc = stage.current(game)
    assert sc is None or sc["id"] != "opening_gate", "it happens once"


@pytest.mark.story
def test_a_summons_with_a_seal(made, tables, monkeypatch):
    from realmwalker.game import letters, story
    from realmwalker.game.story import beats, stage

    game, t, town = _life_near(made, tables, "risen")
    _begin(game, monkeypatch, "summons")
    _into_town(game, town)
    sc = stage.current(game)
    assert sc is not None and sc["id"] == "opening_summons", "a runner comes with a letter"
    pend = _until_beat(game)
    assert pend is not None and pend["beat"] == "opening_summons"
    held = [it for it in game.leader.inventory if letters.lid_of(it)]
    assert held, "the letter is yours to keep"
    asking = game.world.settlements[t["stakes"][0]].name if t["stakes"] else town.name
    assert pend["words"]["town"] == asking, "it comes from the threat's own town"
    page = " ".join(letters.records(game.world)[letters.lid_of(held[-1])]["lines"])
    assert "{" not in page and asking in page
    beats.choose(game, pend, 0)
    adv = next(a for a in story.active(game) if a["threat"] == t["id"])
    assert adv["opening"] == "summons"


@pytest.mark.story
def test_leaving_without_going_in_the_opening_finds_you_on_the_road(made, tables, monkeypatch):
    from realmwalker.game import story
    from realmwalker.game.story import beats

    game, t, town = _life_near(made, tables, "beast")
    _begin(game, monkeypatch, "crisis")
    assert not story.on_travel(game, 10), "at the gate it waits for you to go in"
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        if game.world.settlement_at(town.x + dx, town.y + dy) is None and \
                game.step_minutes(town.x, town.y, town.x + dx, town.y + dy) is not None:
            game.player.x, game.player.y = town.x + dx, town.y + dy
            break
    assert story.on_travel(game, 10)
    pend = beats.pending(game)
    assert pend is not None and pend["beat"] == "opening_crisis"


@pytest.mark.story
@pytest.mark.parametrize("free", (True, False))
def test_waking_as_the_gang_s_captive(made, tables, monkeypatch, free):
    """Present terror: the beat opens before anything else; however you get out of the ropes the tale is begun, and
    the guards are at their fire (unaware, if you were quiet), a short way out of the start town."""
    from realmwalker.game import camp, fight
    from realmwalker.game import story
    from realmwalker.game.story import beats

    game, t, town = _life_near(made, tables, "outlaw", background="criminal")
    _begin(game, monkeypatch, "terror")
    pend = beats.pending(game)
    assert pend is not None and pend["beat"] == "opening_captive", "you wake bound"
    assert game.busy
    text = " ".join(beats.pages(game, pend))
    assert "{" not in text
    monkeypatch.setattr(camp, "check", lambda *a, **k: (free, "(a roll)"))
    out = beats.choose(game, pend, 0)
    assert out
    adv = next(a for a in story.active(game) if a["threat"] == t["id"])
    assert adv["opening"] == "terror"
    enc = game.encounter
    assert enc is not None and enc.creatures and enc.spotted_first == free
    assert all(c.story and c.story["role"] == "minion" for c in enc.creatures)
    assert (game.player.x, game.player.y) != (town.x, town.y), "their camp is out of town"
    assert game.world.settlement_at(game.player.x, game.player.y) is None
    battle = fight.encounter_fight(game, ambush=free)
    T = game.tables.terrain.index
    assert (battle.field.terrain == T["campfire"]).any(), "their fire is on the field"
