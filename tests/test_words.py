"""Words that sound right (after v1): people tell their own stories, nobody gives away the cutpurse at the inn,
rumours and work stay within reach, capitals sit where they belong, and the day's walk remembers its weather."""

import copy
import re

import pytest

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.game import events, quests
from realmwalker.game.dialogue import Choice, Conversation, plural
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Wordland", 1, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def town_with_people(game, want=lambda npcs: True):
    for s in game.world.settlements:
        prepare_town(game, s)
        folk = [n for n in npcs_in(game.world, s.id) if n.alive]
        if folk and want(folk):
            game.player.x, game.player.y = s.x, s.y
            game.player.local_key = None
            return s, folk
    pytest.skip("no town with the people this test needs")


def ask(conv, cid):
    choice = next(c for c in conv.menu() if c.id == cid)
    before = len(conv.lines)
    conv.choose(choice)
    return conv.lines[before:]


# ---------------------------------------------------------------------------- conversations
def test_a_life_story_is_told_not_quoted_in_the_third_person(game):
    s, folk = town_with_people(game)
    told = 0
    for npc in folk[:30]:
        npc.known = True
        conv = Conversation(game, npc)
        npc.disposition = 40  # (after meeting them: a first meeting sets how they take you)
        lines = ask(conv, "who")
        story = npc.profile.get("backstory")
        if not story:
            continue
        spoken = [t for who, t in lines if who == "npc"]
        noted = [t for who, t in lines if who == "note"]
        assert not any(story in t for t in spoken), f"{npc.name} speaks their own story in the third person"
        assert any(t.startswith(f"{npc.first_name}'s story") for t in noted), noted
        told += 1
    assert told


def test_a_ruler_gives_their_style(game):
    def ruled(npcs):
        return any(game.world.figures.get(n.flags.get("figure", -1)) is not None
                   and game.world.figures[n.flags["figure"]].role == "ruler" for n in npcs)

    s, folk = town_with_people(game, ruled)
    npc = next(n for n in folk if game.world.figures.get(n.flags.get("figure", -1)) is not None
               and game.world.figures[n.flags["figure"]].role == "ruler")
    npc.known = False
    fig = game.world.figures[npc.flags["figure"]]
    said = " ".join(t for who, t in ask(Conversation(game, npc), "who") if who == "npc")
    assert f"{fig.title} {npc.name}" in said
    assert "I'm the" not in said


def test_nobody_names_the_cutpurse_at_the_inn(game):
    s, folk = town_with_people(game)
    speaker = next(n for n in folk if n.notable)
    thief = next(n for n in folk if n is not speaker and n.notable)
    thief.flags["recruit"] = "cutpurse"
    thief.title = "cutpurse"
    conv = Conversation(game, speaker)
    speaker.disposition = 30
    text = " ".join(t for who, t in ask(conv, "place"))
    assert "cutpurse" not in text
    assert "at the inn" in text


def test_the_town_is_described_once_a_day_not_by_everyone(game):
    s, folk = town_with_people(game)
    from realmwalker.game.people import town_of

    town = town_of(game.world, s.id)
    town.description = "A place of mud and bells."
    notable = [n for n in folk if n.alive][:3]
    seen = []
    for npc in notable:
        conv = Conversation(game, npc)
        npc.disposition = 30
        seen.append(any(t == town.description for who, t in ask(conv, "place")))
    assert seen[0] and not any(seen[1:])


def test_titles_have_proper_plurals():
    assert plural("lady") == "ladies" and plural("headman") == "headmen"
    assert plural("guildmistress") == "guildmistresses" and plural("smith") == "smiths"
    assert plural("traveller at the inn") == "travellers at the inn"


def test_the_game_says_more_than_one_thing_to_a_stranger(data):
    d = data["dialogue.json"]
    assert len(set(d["who_are_you"])) >= 8 and len(set(d["tell_about_self"])) >= 8
    t = data["people.json"]["text"]
    for job in ("farmer", "carter", "beggar", "fisher", "miner", "weaver"):
        assert len(t[f"backstory_{job}"]) >= 3, f"a {job} has a life of their own"


# ---------------------------------------------------------------------------- rumours and work within reach
def test_rumoured_places_are_within_reach(game):
    p = game.player
    for _ in range(80):
        text = events.hear_place(game, RNG(len(p.known_settlements), "hear"))
        if text is None:
            break
        miles = int(re.search(r"about (\d+) miles", text).group(1))
        assert miles <= events.HEARSAY_REACH * 3 * 1.42, text
    assert events.hear_place(game, RNG(1)) is None or len(p.known_settlements) < len(game.world.settlements)


def test_the_missing_are_never_taken_a_fortnight_away(game):
    for s in game.world.settlements[:30]:
        prepare_town(game, s)
        for npc in npcs_in(game.world, s.id):
            if npc.job not in game.tables.quests["templates"]["investigate"]["givers"]:
                continue
            q = quests.make_offer(game, npc, RNG(npc.id, "inv"), template="investigate")
            if q is not None:
                site = game.world.sites[q["target"]["site"]]
                assert quests.dist(site, s) <= 30, f"{site.name} is {quests.dist(site, s) * 3:.0f} miles away"


def test_work_is_worded_with_capitals_where_they_belong(game):
    checked = 0
    for s in game.world.settlements[:30]:
        prepare_town(game, s)
        for npc in npcs_in(game.world, s.id):
            for t in ("retrieve", "hunt_beast", "clear_lair"):
                if npc.job not in game.tables.quests["templates"][t]["givers"]:
                    continue
                q = quests.make_offer(game, npc, RNG(npc.id, f"w/{t}"), template=t)
                if q is None:
                    continue
                for kind in ("pitch", "journal", "done"):
                    text = quests.fill(game, q, kind)
                    assert not re.search(r'(^|[.!?]\s+)"?[a-z]', text), text
                    assert not re.search(r"[a-z,] The [A-Z][a-z]+ [a-z]", text), text
                    checked += 1
    assert checked


def test_speech_that_opens_a_sentence_is_capitalised():
    assert textgen.tidy('"the Grey Wolf. it took a dog." he said.') == '"The Grey Wolf. It took a dog." he said.'


# ---------------------------------------------------------------------------- grammar
def test_a_town_on_the_coast_does_not_sit_in_the_coast(game):
    from realmwalker.game.town_words import town_description

    coast = [s for s in game.world.settlements if game.biome_key(s.x, s.y) == "coast"]
    if not coast:
        pytest.skip("no coastal town")
    for i in range(40):
        text = town_description(game, coast[0], RNG(i, "coast"))
        assert "in the coast" not in text


def test_a_hard_season_takes_the_right_article(tables):
    from realmwalker.rules.creation import CharacterBuilder

    for seed in range(40):
        b = CharacterBuilder(tables, RNG(seed, "article"))
        b.set_race("human")
        b.set_class("fighter")
        b.set_background("soldier")
        text = b.fallback_backstory("Holt").get("backstory", "")
        assert "a autumn" not in text and "a winter that" not in text


def test_personalities_read_as_english(game):
    s, folk = town_with_people(game)
    for npc in folk:
        text = npc.profile.get("personality", "")
        assert not re.search(r"\bis a [a-z ]+ and [a-z]+;", text) or " and a " in text, text
        assert "say she is" not in npc.profile.get("secret", "") and "say he is" not in npc.profile.get("secret", "")


# ---------------------------------------------------------------------------- fights and the road
def test_a_knowledge_roll_comes_before_what_it_told_you(tables):
    from realmwalker.rules.combat import Battle, Env
    from realmwalker.rules.creation import CharacterBuilder
    from realmwalker.rules.creatures import spawn_group

    b = CharacterBuilder(tables, RNG(2, "sage"))
    b.set_race("human")
    b.set_class("wizard")
    b.set_background("sage")
    hero = b.build()
    for seed in range(20):
        battle = Battle(tables, [hero], spawn_group(tables, "bandits", RNG(seed, "f")), Env(), RNG(seed, "b"))
        battle.start("A test.")
        texts = [m[0] if isinstance(m, tuple) else getattr(m, "text", str(m)) for m in battle.log]
        for i, t in enumerate(texts):
            if " knows " in t:
                assert i > 0 and "vs DC" in texts[i - 1], texts[max(0, i - 2): i + 1]
                return
    pytest.skip("nobody knew anything in twenty fights")


def test_the_days_walk_remembers_the_weather_that_held_it(tables, data):
    from realmwalker.game.events import travel_day_passage

    t = data.fallback["travel_day"]
    for sky in ("rain", "fog", "clear", "snow"):
        for seed in range(6):
            text = travel_day_passage(RNG(seed, sky), data, {"name": "Wat", "miles": 24, "lands": "grassland and forest",
                                                            "weather": sky, "mood": "tired", "season": "spring",
                                                            "events": "nothing much", "road": "mostly on the road",
                                                            "sky": sky})
            assert any(line in text for line in t[f"sky_{sky}"]), text
