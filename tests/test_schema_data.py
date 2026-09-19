import json

import pytest

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.core.schema import Int, List, Obj, SchemaError, Str, truncate_text
from realmwalker.data.registry import DataRegistry, check_template_slots
from realmwalker.paths import Paths


def test_real_data_files_are_valid():
    _, errors = DataRegistry.load(Paths().data)
    assert errors == []


def test_missing_and_broken_files_give_clear_errors(tmp_path):
    (tmp_path / "names.json").write_text('{"cultures": {', encoding="utf-8")
    _, errors = DataRegistry.load(tmp_path)
    assert any("names.json: line 1" in e for e in errors)
    assert any("fallback_text.json is missing" in e for e in errors)


def test_schema_reports_paths_and_typos():
    spec = Obj({"name": Str(), "age": Int(min=0, max=900)})
    errors = []
    spec.check({"name": 5, "age": 1000, "nmae": "x"}, "", errors)
    assert "name: expected text, got a whole number" in errors
    assert "age: 1000 is outside 0..900" in errors
    assert "nmae: unknown field (typo?)" in errors


def test_comment_keys_are_allowed():
    errors = []
    Obj({"a": Str()}).check({"a": "x", "_comment": "hello"}, "", errors)
    assert errors == []


def test_clean_is_forgiving_but_firm():
    spec = Obj({"name": Str(max_len=10), "level": Int(min=1, max=10), "tags": List(Str(), min_items=1, max_items=2)})
    out = spec.clean({"Name": "  Aldric   the  Bold  ", "level": "15", "tags": ["a", 5, {"x": 1}, "d"], "extra": 1})
    assert out["name"] == "Aldric…" or len(out["name"]) <= 10
    assert out["level"] == 10  # clamped
    assert out["tags"] == ["a", "5"]  # bad entries dropped, trimmed to max
    with pytest.raises(SchemaError):
        spec.clean({"level": 3, "tags": ["a"]})  # name missing


def test_choices_match_case_insensitively():
    spec = Str(choices=["easy", "medium", "hard"])
    assert spec.clean(" Hard. ") == "hard"
    with pytest.raises(SchemaError):
        spec.clean("impossible")


def test_example_json_describes_the_shape():
    spec = Obj({"skill": Str(choices=["Insight", "Persuasion"]), "dc": Int(min=5, max=25), "line": Str("what they say")})
    example = json.loads(spec.example_json())
    assert example == {"skill": "<one of: Insight | Persuasion>", "dc": "<whole number 5-25>", "line": "<what they say>"}


def test_truncate_prefers_sentence_end():
    text = "The door sticks. Inside it is dark and it smells of wet wool and tallow."
    assert truncate_text(text, 30) == "The door sticks."


def test_template_fill_uses_tables_and_values():
    tables = {"animal": ["crow"], "thing": ["the {animal}"]}
    out = textgen.fill("{name} saw {thing}. it flew.", RNG(1), tables, {"name": "Mira"})
    assert out == "Mira saw the crow. It flew."


def test_unknown_template_slots_are_reported():
    errors = check_template_slots({"tavern": {"description": ["a {nonsense} here"], "name_pattern": ["x"]}})
    assert errors and "{nonsense}" in errors[0]


def test_broken_creature_references_are_reported(tmp_path):
    import shutil

    src = Paths().data
    for f in src.glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    data = json.loads((tmp_path / "creatures.json").read_text(encoding="utf-8"))
    data["creatures"]["wolf"]["gear"] = [["golden_spoon", 1]]
    first_group = next(k for k in data["encounters"] if not k.startswith("_"))
    data["encounters"][first_group]["members"].append(["dragon_that_is_not_there", "1"])
    (tmp_path / "creatures.json").write_text(json.dumps(data), encoding="utf-8")
    _, errors = DataRegistry.load(tmp_path)
    assert any("golden_spoon" in e for e in errors)
    assert any("dragon_that_is_not_there" in e for e in errors)
