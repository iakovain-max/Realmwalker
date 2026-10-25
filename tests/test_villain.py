"""The villain who acts (Expansion 6 E.1, docs/ADVENTURES.md §5.4): attention rises with every harm done to it and has
a name for each level; its temper weighs the moves its attention allows; one move in two days, and beasts never write;
a spy unseen steals a token and the next move is made with it, a spy seen can be chased; a setback brings its wrath at
once; a reprisal falls on one who helped you; a strike comes in force, and its dead are counted in a real fight."""

import pytest

from realmwalker.game import fight
from realmwalker.game.people import prepare_town
from realmwalker.game.story import beats, villain
from realmwalker.rules.combat import PARTY
from tests.test_risen_outlaw import _tale, made, tables  # noqa: F401
from tests.test_story_hooks import _start_near_a_beast

pytestmark = pytest.mark.story


def _temper_moves(monkeypatch, game, adv, moves):
    monkeypatch.setitem(villain.temper(game, adv), "moves", moves)
    monkeypatch.setitem(game.tables.villains["attention"], "chance", [1.0])  # (a move at every chance)


def _days(game, n):
    game.world.time += 1440 * n


def test_attention_rises_with_harm_and_has_a_name(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    adv["attention"] = 0
    assert villain.level(game, adv) == "unaware"
    villain.on_step(game, adv, {"kind": "witness"})
    assert adv["attention"] == 1 and villain.level(game, adv) == "has heard of you"
    villain.on_fight(game, adv, servants=1)
    assert adv["attention"] == 2, "its servants killed"
    game.player.x, game.player.y = t["reach"]["x"], t["reach"]["y"]
    villain.on_magic(game, 3)
    assert adv["attention"] == 2, "small magic goes unnoticed"
    villain.on_magic(game, 7)
    assert adv["attention"] == 3 and villain.level(game, adv) == "testing", "great magic in its reach"
    villain.on_fight(game, adv, lieutenants=1)
    assert adv["attention"] == 5 and adv.get("wrath"), "a lieutenant slain: more, and its wrath"
    villain.on_step(game, adv, {"kind": "witness"})
    assert adv["attention"] == 5 and villain.level(game, adv) == "obsessed", "never above the most"
    _days(game, 15)
    villain.quiet(game, adv)
    assert adv["attention"] == 4, "a quiet fortnight"


def test_the_temper_weighs_the_moves_its_attention_allows(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    tem = villain.temper(game, adv)
    table = tables.villains["moves"]
    for att in (1, 2, 4, 5):
        adv["attention"] = att
        chosen = set()
        for day in range(40):
            adv["moves"] = []
            for where in ("road", "camp", "inn", "town"):
                villain.due_move(game, adv, where)
                if adv["moves"]:
                    chosen.add(adv["moves"][-1]["move"])
                    break
            _days(game, 1)
        assert chosen, f"some move at attention {att}"
        for mid in chosen:
            assert mid in tem["moves"], f"{mid} is its temper's"
            lo, hi = table[mid]["attention"]
            assert lo <= att <= hi, f"{mid} fits attention {att}"
        if att >= 4:
            assert any(table[m]["attention"][0] >= 3 for m in chosen), f"high moves at {att}: {chosen}"


def test_one_move_in_two_days_and_a_beast_never_writes(made, tables):
    game, t = _start_near_a_beast(made, tables)
    from realmwalker.game.story import forge

    adv = forge.make(game, t)
    adv["attention"] = 5
    assert not villain.speaks(game, adv)
    for _ in range(30):
        for where in ("road", "camp", "wild"):
            villain.due_move(game, adv, where)
        adv["chapter"] = (adv["chapter"] + 1) % len(adv["chapters"])  # (no chapter's count holds it back)
        _days(game, 1)
    days = [m["day"] for m in adv["moves"]]
    assert len(days) >= 5
    assert all(b - a >= 2 for a, b in zip(days, days[1:])), "one move in two days"
    assert not any(tables.villains["moves"][m["move"]].get("speaks") for m in adv["moves"]), "beasts never write"


def test_a_spy_unseen_steals_a_token_and_the_next_move_is_made_with_it(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    adv["attention"] = 2
    monkeypatch.setitem(tables.villains["spy"], "dc", 40)
    _temper_moves(monkeypatch, game, adv, {"token_letter": 1})
    assert villain.due_move(game, adv, "camp") is None, "nothing to make it with yet"
    _temper_moves(monkeypatch, game, adv, {"spy": 1})
    said = len(game.log.messages)
    assert villain.due_move(game, adv, "road") is None, "unseen: no beat"
    tok = adv["token"]
    assert tok["what"] in tables.villains["spy"]["tokens"] and not tok.get("used")
    assert tok["of"] in [c.name.split()[0] for c in game.party]
    assert len(game.log.messages) > said and tok["what"] in game.log.messages[-1].text, "the loss is noticed"
    _days(game, 2)
    game.world.time += (24 - game.moment.hour + 7) % 24 * 60  # (morning)
    _temper_moves(monkeypatch, game, adv, {"token_letter": 1, "villain_omen": 0})
    adv["chapter"] = (adv["chapter"] + 1) % len(adv["chapters"])
    assert villain.due_move(game, adv, "camp") == "villain_token_letter"
    assert "used" in tok
    beats.offer(game, "villain_token_letter", adv=adv["id"], where="camp")
    rec = beats.pending(game)
    assert tok["of"] in " ".join(beats.pages(game, rec)), "it names whose it was"
    lines = beats.choose(game, rec, 0)
    assert any("letter" in x for x in lines)
    letter = list(game.world.politics["letters"].values())[-1]
    assert tok["of"] in " ".join(letter["lines"]) or tok["what"] in " ".join(letter["lines"]), "made with the token"
    _days(game, 3)
    adv["chapter"] = (adv["chapter"] + 1) % len(adv["chapters"])
    assert villain.due_move(game, adv, "camp") is None, "a token makes one such move"


def test_a_spy_seen_can_be_chased(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    adv["attention"] = 1
    monkeypatch.setitem(tables.villains["spy"], "dc", 0)
    _temper_moves(monkeypatch, game, adv, {"spy": 1})
    assert villain.due_move(game, adv, "road") == "villain_spy_seen"
    assert "token" not in adv
    beats.offer(game, "villain_spy_seen", adv=adv["id"], where="road")
    beats.choose(game, beats.pending(game), 1)
    assert "knows_its_spy" in adv["flags"]


def test_wrath_lashes_out_at_once_whatever_the_chapter(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    adv["attention"] = 2
    adv["moves"] = [{"day": int(game.moment.total_days), "move": "outlaw_omen", "chapter": adv["chapter"]}] * 2
    _days(game, 3)
    assert villain.due_move(game, adv, "road") is None, "the chapter's moves are made"
    villain.on_fight(game, adv, lieutenants=1)
    assert adv["attention"] >= 4 and adv["wrath"]["why"] == "lieutenant"
    beat = None
    for where in ("road", "wild", "camp", "inn"):
        beat = villain.due_move(game, adv, where)
        if beat:
            break
    assert beat is not None, "it lashes out"
    made_move = adv["moves"][-1]
    assert made_move.get("wrath") and (tables.villains["moves"][made_move["move"]]["attention"][0] >= 3
                                       or made_move["move"] in tables.villains["wrath"]["moves"]), "an angry move"
    assert "wrath" not in adv


def test_a_reprisal_falls_on_one_who_helped_you(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    entry = adv["cast"]["witness"]
    prepare_town(game, game.world.settlements[int(entry["settlement"])])
    entry = adv["cast"]["witness"]
    assert "npc" in entry, "the witness is bound to a townsperson"
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            if "witness" in [st["target"].get("role")] + [r.get("role") for r in st["target"].get("routes", [])]:
                st["state"] = "done"  # (the witness has told what they know: no step needs them now)
    game.player.x, game.player.y = t["reach"]["x"], t["reach"]["y"]  # (away from the witness's town)
    adv["attention"] = 4
    _temper_moves(monkeypatch, game, adv, {"reprisal": 1})
    beat = next((b for w in ("road", "wild", "camp") if (b := villain.due_move(game, adv, w))), None)
    assert beat == "villain_reprisal"
    npc = game.world.npcs[int(entry["npc"])]
    beats.offer(game, beat, adv=adv["id"], where="road")
    rec = beats.pending(game)
    assert npc.name in " ".join(beats.pages(game, rec))
    beats.choose(game, rec, 0)
    assert not npc.alive and npc.flags["reprisal"]["adv"] == adv["id"]
    assert any(npc.name in n["text"] for n in game.world.news), "the news tells it"
    assert adv["reprisals"] == [npc.id]


def test_a_strike_comes_in_force_and_its_dead_are_counted_in_a_real_fight(made, tables):
    from tools.arena import run

    game, adv, t = _tale(made, tables, "outlaw")
    adv["attention"] = 4
    beats.offer(game, "villain_strike", adv=adv["id"], where="road")
    beats.choose(game, beats.pending(game), 0)
    enc = game.encounter
    assert enc is not None and len(enc.creatures) >= 2, "a band and more of its servants"
    assert all(c.story == {"adv": adv["id"], "role": "minion"} for c in enc.creatures)
    for c in game.party:
        c.level = max(c.level, 12)
        c.hp = c.max_hp = 200
    b = fight.start_battle(game, enc.creatures, enc.intro)
    game.encounter = None
    for f in b.side(PARTY):
        f.auto = True
    before = adv["attention"]
    run(b, max_steps=4000)
    assert b.outcome is not None
    fight.finish_battle(game)
    assert b.outcome == "victory", "a strong party wins"
    assert adv["attention"] == min(5, before + 1), "its servants killed: it hears of it once"


def test_a_beast_hunts_in_person_and_a_beast_in_wrath_tests_you(made, tables, monkeypatch):
    from realmwalker.game.story import forge

    game, t = _start_near_a_beast(made, tables)
    adv = forge.make(game, t)
    adv["attention"] = 5
    _temper_moves(monkeypatch, game, adv, {"hunt": 1})
    assert villain.due_move(game, adv, "road") == "villain_hunt", "the beast breaks off when hurt: it may hunt"
    beats.offer(game, "villain_hunt", adv=adv["id"], where="road")
    beats.choose(game, beats.pending(game), 0)
    enc = game.encounter
    assert enc is not None and enc.creatures[0].story["role"] == "villain", "it comes itself"
    game.encounter = None
    _days(game, 3)
    adv["attention"] = 2
    _temper_moves(monkeypatch, game, adv, {"omen": 3, "test": 1})
    villain.on_fight(game, adv, lieutenants=1)
    assert adv["attention"] == 5 and adv.get("wrath")
    adv["attention"] = 3  # (its wrath: a test by night, never an omen)
    assert villain.due_move(game, adv, "road") is None, "in its wrath it spends nothing on an omen"
    game.world.time += (24 - game.moment.hour + 1) * 60
    assert villain.due_move(game, adv, "camp") == "beast_test_night"


def test_the_villain_visits_by_night_and_talks(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    adv["attention"] = 3
    _temper_moves(monkeypatch, game, adv, {"visit": 1})
    game.world.time += (24 - game.moment.hour + 1) * 60
    assert villain.due_move(game, adv, "camp") == "villain_visit"
    beats.offer(game, "villain_visit", adv=adv["id"], where="camp")
    rec = beats.pending(game)
    assert "{" not in " ".join(beats.pages(game, rec))
    clues = int(adv["clues"].get("villain", 0))
    beats.choose(game, rec, 0)
    assert int(adv["clues"].get("villain", 0)) > clues, "listening teaches you something of it"


def test_the_journal_shows_its_eye(made, tables):
    from realmwalker.ui.screens.journal import tale_lines

    game, adv, t = _tale(made, tables, "risen")
    adv["attention"] = 3
    text = tale_lines(game, adv)
    assert "Its eye" in text and "testing" in text
