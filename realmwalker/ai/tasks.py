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


# ---------------------------------------------------------------------------- character backstory
BACKSTORY = AITask(
    name="backstory",
    schema=Obj(
        {
            "backstory": Str("3 to 5 sentences of backstory, third person", max_len=900),
            "personality": Str("one sentence: a personality trait, first person", max_len=200),
            "ideal": Str("one sentence: an ideal they hold, first person", max_len=200),
            "bond": Str("one sentence: a bond to a person or place, first person", max_len=200),
            "flaw": Str("one sentence: a flaw, first person", max_len=200),
        }
    ),
    max_tokens=3000,
    temperature=0.9,
)


def backstory_variables(builder, tables, home_name: str, tie_text: str) -> dict:
    race = tables.races[builder.race]
    bg = tables.backgrounds[builder.background]
    culture = tables.names["cultures"].get(builder.culture, {}).get("label", builder.culture)
    return {
        "name": builder.name, "sex": builder.sex.capitalize(), "age": builder.age, "race": race["name"],
        "culture": culture, "class_name": tables.classes[builder.cls]["name"], "background": bg["name"],
        "background_text": bg["description"], "home": home_name, "tie": tie_text or "none worth mentioning",
        "appearance": builder.appearance,
    }


# ---------------------------------------------------------------------------- a day on the road
TRAVEL_DAY = AITask(
    name="travel_day",
    schema=Obj({"passage": Str("2 or 3 sentences, second person, past tense", max_len=600)}),
    max_tokens=3000,
    temperature=0.9,
)


def travel_day_fallback(rng: RNG, data: DataRegistry, variables: dict) -> dict:
    tables = data.fallback["travel_day"]
    text = textgen.fill(rng.choice(tables["passage"]), rng, tables, {k: str(v) for k, v in variables.items()})
    return {"passage": textgen.tidy(text)}


# ---------------------------------------------------------------------------- the chronicle of the world (M6)
CHRONICLE = AITask(
    name="chronicle",
    schema=Obj({"title": Str("the chronicle's title, 3 to 8 words", max_len=80),
                "chronicle": Str("five to eight short paragraphs separated by blank lines", max_len=6000)}),
    max_tokens=3000,
    temperature=0.85,
)


# ---------------------------------------------------------------------------- magic items (M8)
MAGIC_ITEM = AITask(
    name="magic_item",
    schema=Obj({"name": Str("the item's name, 2 to 6 words", max_len=60),
                "history": Str("two or three sentences of its history", max_len=500)}),
    max_tokens=3000,
    temperature=0.9,
)


# ---------------------------------------------------------------------------- death (M9)
OBITUARY = AITask(
    name="obituary",
    schema=Obj({"obituary": Str("three or four sentences about the dead traveller", max_len=900)}),
    max_tokens=3000,
    temperature=0.9,
)


# ---------------------------------------------------------------------------- quests (M8)
QUEST = AITask(
    name="quest",
    schema=Obj({"title": Str("a short name for the job, 2 to 6 words", max_len=60),
                "pitch": Str("what the giver says, in double quotes, 2 to 4 sentences", max_len=600)}),
    max_tokens=3000,
    temperature=0.9,
)


# ---------------------------------------------------------------------------- settlements and people
def _settlement_task() -> AITask:
    from realmwalker.core.schema import Int, List

    return AITask(
        name="settlement",
        schema=Obj(
            {
                "description": Str("3 or 4 sentences: arriving there", max_len=900),
                "inn_names": List(Str("an inn's name, 2 to 5 words", max_len=48), max_items=4, optional=True),
                "people": List(
                    Obj(
                        {
                            "id": Int("the person's id", min=0, max=10**9),
                            "appearance": Str("one sentence", max_len=300),
                            "personality": Str("one sentence", max_len=300),
                            "speech": Str("a few words", max_len=80, optional=True),
                            "backstory": Str("two sentences", max_len=500),
                            "secret": Str("one short clause", max_len=200),
                            "want": Str("one short clause", max_len=200),
                        }
                    ),
                    max_items=14,
                    optional=True,
                ),
            }
        ),
        max_tokens=3000,
        temperature=0.9,
    )


def _dialogue_task() -> AITask:
    from realmwalker.core.schema import List
    from realmwalker.game.dialogue import OUTCOMES, SKILLS_ALLOWED

    result = {"outcome": Str(choices=OUTCOMES), "line": Str("a short reaction", max_len=260)}
    return AITask(
        name="dialogue",
        schema=Obj(
            {
                "line": Str("their opening words, in double quotes", max_len=300),
                "options": List(
                    Obj(
                        {
                            "text": Str("the traveller's intent, 3 to 12 words", max_len=100),
                            "skill": Str(choices=sorted(SKILLS_ALLOWED)),
                            "difficulty": Str(choices=["easy", "medium", "hard", "very hard"]),
                            "success": Obj({**result, "topic": Str("a subject, 1 to 4 words", max_len=40, optional=True)}),
                            "failure": Obj(result),
                        }
                    ),
                    max_items=3,
                    optional=True,
                ),
            }
        ),
        max_tokens=3000,
        temperature=0.9,
    )


SETTLEMENT = _settlement_task()
DIALOGUE = _dialogue_task()

ALL_TASKS: list[AITask] = [SAMPLE_TAVERN, BACKSTORY, TRAVEL_DAY, SETTLEMENT, DIALOGUE, CHRONICLE, MAGIC_ITEM,
                           QUEST, OBITUARY]
