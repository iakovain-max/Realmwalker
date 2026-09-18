"""The kinds of text we ask the AI for. Each task pairs a prompt file (ai/prompts/<name>.txt)
with the JSON shape we accept, and comes with a built-in fallback that needs no AI at all."""

from __future__ import annotations

from realmwalker.ai.service import AITask
from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.core.schema import Obj, Str
from realmwalker.data.registry import DataRegistry

# ---------------------------------------------------------------------------- sample tavern
# Used by the Player2 test screen: one call returns a whole tavern with its keeper.

SAMPLE_TAVERN = AITask(
    name="sample_tavern",
    schema=Obj(
        {
            "name": Str("the tavern's name, 2 to 5 words", max_len=48),
            "sign": Str("one sentence: what its hanging sign shows, and the state it is in", max_len=200),
            "description": Str("3 or 4 sentences: the building, the smell, the drinkers, one telling detail", max_len=900),
            "keeper": Str("the keeper's full name", max_len=40),
            "manner": Str("one sentence on how the keeper treats strangers", max_len=240),
            "overheard": Str("one line a drinker says about local trouble, in double quotes", max_len=240),
        }
    ),
    max_tokens=3000,
    temperature=0.9,
)

CULTURE_STYLE = {
    "heartland": "lowland English-sounding medieval",
    "northmarch": "Norse-sounding highland",
    "southron": "Iberian- and Italian-sounding coastal",
}


def sample_tavern_variables(rng: RNG, data: DataRegistry) -> dict:
    tables = data.fallback["tavern"]
    culture = rng.choice(sorted(CULTURE_STYLE))
    return {
        "region": rng.choice(tables["region"]),
        "season": rng.choice(tables["season"]),
        "culture": CULTURE_STYLE[culture],
        "culture_id": culture,
    }


def sample_tavern_fallback(rng: RNG, data: DataRegistry, variables: dict | None = None) -> dict:
    tables = data.fallback["tavern"]
    cultures = data.names["cultures"]
    culture_id = (variables or {}).get("culture_id", "heartland")
    culture = cultures.get(culture_id) or next(iter(cultures.values()))
    sex = rng.choice(["male", "female"])
    keeper = f"{rng.choice(culture[sex])} {rng.choice(culture['family'])}"
    name = textgen.fill(rng.choice(tables["name_pattern"]), rng, tables, {"family": rng.choice(culture["family"])})
    sign_subject = next((n for n in tables["noun"] if n in name.split() or f"{n}'s" in name), None)
    subject = textgen.a_or_an(sign_subject.lower()) if sign_subject else "a foaming tankard"
    sign = textgen.tidy(f"The sign shows {subject}, {rng.choice(tables['sign_state'])}.")
    description = textgen.fill(rng.choice(tables["description"]), rng, tables)
    manner = textgen.fill(rng.choice(tables["manner"]), rng, tables, {"keeper": keeper.split()[0]})
    return {
        "name": name,
        "sign": sign,
        "description": description,
        "keeper": keeper,
        "manner": manner,
        "overheard": rng.choice(tables["overheard"]),
    }


ALL_TASKS: list[AITask] = [SAMPLE_TAVERN]
