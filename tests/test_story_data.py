"""The story engine's data (Expansion 6 A.2): four new kinds of data file in the pack, their schemas, their
cross-references, and the start-up check that what they name exists in the code (game/story/check.py)."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.data.registry import check_cross_references
from realmwalker.game.story import beats, check, endings, finale, selectors, steps
from realmwalker.world import threats
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def test_the_story_files_load_from_the_pack_and_the_check_is_clean(data, tables):
    for name in ("threats.json", "adventures.json", "villains.json", "beats.json"):
        assert data.get(name) is not None
    assert tables.threats["target_level"]["1"] == 3
    assert tables.adventures["max_active"] == 3
    assert check.problems(tables) == []


def test_selectors_are_read_by_the_grammar_of_blueprints():
    tree = selectors.parse("hidden(2, site_of_figure(villain.slayer), scar_of(villain), site_style(crypt|temple, 6, 30))")
    assert isinstance(tree, selectors.Call) and tree.name == "hidden" and tree.args[0] == 2
    names = [c.name for c in selectors.calls(tree)]
    assert names == ["hidden", "site_of_figure", "scar_of", "site_style"]
    assert isinstance(tree.args[3].args[0], selectors.Words) and tree.args[3].args[0].words == ["crypt", "temple"]
    alt = selectors.parse("settlement_with(temple, 12, 40) | settlement_great(10, 60)")
    assert isinstance(alt, selectors.Alt) and len(alt.options) == 2
    path = selectors.parse("home.level(1)")
    assert isinstance(path, selectors.Path) and path.parts[0] == "home" and path.parts[1].name == "level"
    for bad in ("settlement_near(home, 2", "a)b", ""):
        with pytest.raises(selectors.SelectorError):
            selectors.parse(bad)


def _fake(tables, **over):
    t = SimpleNamespace(threats=copy.deepcopy(tables.threats), adventures=copy.deepcopy(tables.adventures),
                        villains=copy.deepcopy(tables.villains), beats=copy.deepcopy(tables.beats), rules=tables.rules)
    for k, v in over.items():
        setattr(t, k, v)
    return t


def _blueprint():
    step = {"kind": "go", "at": "home"}
    chapter = {"id": "one", "need": "all", "title": ["A", "B"], "goal": ["Go."], "opening": ["a", "b", "c"],
               "reveal": ["a", "b", "c"], "steps": [step]}
    return {"name": "Test", "tiers": [1, 2], "from": ["beast"], "title": ["a", "b", "c"], "hook": ["a", "b", "c"],
            "premise": ["a"], "places": {"home": "threat.home", "town": "settlement_near(home, 2, 10)"},
            "cast": {"patron": {"pick": ["headman_of(town)"]}},
            "chapters": [chapter, dict(chapter, id="two")],
            "finale": {"boss": "villain", "template": "t", "at": "home.deepest", "keys": {"weakness": ["surprise"]}},
            "endings": [{"id": "slain", "if": ["boss_dead"], "ops": [["fame", 3]]}, {"id": "gone", "ops": []}]}


def test_the_check_reports_what_the_code_does_not_know(tables, monkeypatch):
    bp = _blueprint()
    bp["chapters"][0]["steps"] += [{"kind": "dance"}, {"kind": "go", "at": "nowhere_yet"}]
    bp["chapters"][1]["steps"][0]["colour"] = "red"
    bp["places"]["odd"] = "settlement_somewhere(home)"
    bp["endings"][0]["if"].append("moon:full")
    bp["endings"][-1]["if"] = ["boss_dead"]
    adv = {"blueprints": {"test": bp}}
    beat = {"family": "villain", "when": {"phase_of_moon": 1}, "text": [["x"]],
            "choices": [{"label": ["Run."], "ops": [["teleport"]], "check": {"skill": "juggling", "dc": 12}}]}
    vil = {"tempers": {}, "moves": {"m": {"beat": "no_such_beat", "attention": [0, 9]}},
           "bosses": {"t": {"tiers": [1, 2], "roles": ["beast"], "hp": 1.5, "resistances": 1, "actions": 2,
                            "menu": ["juggle"]}},
           "weaknesses": {"beast": [{"id": "x", "name": "X", "keys": ["polka"], "lore": ["a", "b", "c"]}]}}
    monkeypatch.setitem(steps.STEPS, "go", type("Go", (steps.Step,), {"fields": frozenset({"at"})}))
    monkeypatch.setitem(selectors.SELECTORS, "settlement_near", lambda *a: [])
    monkeypatch.setitem(selectors.SELECTORS, "headman_of", lambda *a: [])
    monkeypatch.setitem(endings.CONDITIONS, "boss_dead", lambda *a: True)
    monkeypatch.setitem(endings.OPS, "fame", lambda *a: [])
    monkeypatch.setitem(finale.KEYS, "surprise", lambda *a: None)
    out = "\n".join(check.problems(_fake(tables, adventures=adv, beats={"b": beat}, villains=vil)))
    for words in ("step kind 'dance'", "'nowhere_yet' is not bound", "does not take colour",
                  "selector 'settlement_somewhere'", "ending condition 'moon:full'", "last ending must have no 'if'",
                  "condition 'phase_of_moon'", "op 'teleport'", "'juggling' is not a skill",
                  "says what success and failure do", "legendary action 'juggle'", "no beat called 'no_such_beat'",
                  "finale key 'polka'"):
        assert words in out, words
    good = _blueprint()
    assert check.problems(_fake(tables, adventures={"blueprints": {"test": good}},
                                villains=dict(vil, moves={}, bosses={"t": dict(vil["bosses"]["t"], menu=[])},
                                              weaknesses={}))) == []


def test_the_story_files_name_each_other(tables):
    files = {"threats.json": {"kinds": {"beast": {"blueprints": ["no_blueprint"], "tempers": ["no_temper"]}}},
             "adventures.json": {"blueprints": {"b": {"from": ["no_kind"]}}},
             "villains.json": {"tempers": {"bestial": {"moves": {"no_move": 1}}}, "moves": {}}}
    out = "\n".join(e for e in check_cross_references(files) if "threats.json" in e or "adventures.json" in e
                    or "villains.json" in e)
    for words in ("blueprint 'no_blueprint'", "temper 'no_temper'", "made from 'no_kind'", "move 'no_move'"):
        assert words in out, words


def test_every_registry_is_a_whitelist_filled_by_the_code():
    for reg in (steps.STEPS, selectors.SELECTORS, beats.CONDITIONS, beats.OPS, endings.CONDITIONS, endings.OPS,
                finale.KEYS, finale.LEGENDARY, finale.PHASES, threats.STAGE_OPS):
        assert isinstance(reg, dict)
    assert finale.split_key("vulnerable(fire)") == ("vulnerable", ["fire"])
    assert finale.split_key("surprise") == ("surprise", [])
