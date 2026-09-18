import pytest

from realmwalker.ai import parsing
from realmwalker.ai.service import Refused, validate_reply
from realmwalker.ai.tasks import SAMPLE_TAVERN
from realmwalker.core.schema import SchemaError

GOOD = {
    "name": "The Drowned Crow",
    "sign": "A crow, painted badly.",
    "description": "A leaky cellar. It smells of fish.",
    "keeper": "Aldric Fenwick",
    "manner": "He counts your coins twice.",
    "overheard": '"The river took another one."',
}


def test_plain_json():
    assert parsing.parse_json_reply('{"a": 1}') == {"a": 1}


def test_code_fences_are_stripped():
    assert parsing.parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}


def test_prose_around_json():
    assert parsing.parse_json_reply('Sure! Here you go:\n{"a": {"b": "x}y"}}\nEnjoy.') == {"a": {"b": "x}y"}}


def test_trailing_commas_repaired():
    assert parsing.parse_json_reply('{"a": [1, 2,], "b": 3,}') == {"a": [1, 2], "b": 3}


def test_list_of_objects_takes_first():
    assert parsing.parse_json_reply('[{"a": 1}, {"a": 2}]') == {"a": 1}


@pytest.mark.parametrize("text", ["", "   ", "no json here", "{broken", '"just a string"'])
def test_unusable_replies_raise(text):
    with pytest.raises(parsing.ParseError):
        parsing.parse_json_reply(text)


def test_refusals_detected():
    assert parsing.looks_like_refusal("I'm sorry, but I can't help with that.")
    assert parsing.looks_like_refusal("As an AI language model, I cannot write this.")
    assert not parsing.looks_like_refusal("The keeper is sorry for nothing.")


def test_validate_reply_accepts_good_json():
    import json

    data = validate_reply(SAMPLE_TAVERN, json.dumps(GOOD))
    assert data["name"] == "The Drowned Crow"


def test_validate_reply_unwraps_single_nested_object():
    import json

    assert validate_reply(SAMPLE_TAVERN, json.dumps({"tavern": GOOD}))["keeper"] == "Aldric Fenwick"


def test_validate_reply_rejects_missing_fields():
    import json

    with pytest.raises(SchemaError):
        validate_reply(SAMPLE_TAVERN, json.dumps({"name": "X"}))


def test_validate_reply_detects_refusal_text_and_fields():
    import json

    with pytest.raises(Refused):
        validate_reply(SAMPLE_TAVERN, "I cannot help with that request.")
    bad = dict(GOOD, description="I'm sorry, but I can't write violent content.")
    with pytest.raises(Refused):
        validate_reply(SAMPLE_TAVERN, json.dumps(bad))


def test_markup_characters_removed_from_ai_text():
    import json

    data = validate_reply(SAMPLE_TAVERN, json.dumps(dict(GOOD, name="The <danger>Crow</>")))
    assert "<" not in data["name"] and ">" not in data["name"]
