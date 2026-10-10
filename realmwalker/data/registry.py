"""Loads every data file, checks it against its schema and reports problems in plain words."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from realmwalker.core import textgen
from realmwalker.data.schemas import DATA_FILES, RUNTIME_SLOTS

log = logging.getLogger("realmwalker.data")


class DataRegistry:
    def __init__(self, files: dict[str, Any]) -> None:
        self._files = files

    def __getitem__(self, name: str) -> Any:
        return self._files[name]

    def get(self, name: str, default: Any = None) -> Any:
        return self._files.get(name, default)

    @property
    def names(self) -> dict:
        return self._files.get("names.json", {"cultures": {}})

    @property
    def fallback(self) -> dict:
        return self._files.get("fallback_text.json", {})

    @classmethod
    def load(cls, data_dir: Path) -> tuple[DataRegistry, list[str]]:
        files: dict[str, Any] = {}
        errors: list[str] = []
        for filename, spec in DATA_FILES.items():
            path = data_dir / filename
            if not path.exists():
                errors.append(f"data/{filename} is missing.")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"data/{filename}: line {exc.lineno}, column {exc.colno}: {exc.msg}.")
                continue
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"data/{filename}: could not be read ({exc}).")
                continue
            file_errors: list[str] = []
            spec.check(data, "", file_errors)
            errors.extend(f"data/{filename}: {e}" for e in file_errors)
            if not file_errors:
                files[filename] = data
        if "fallback_text.json" in files:
            errors.extend(check_template_slots(files["fallback_text.json"]))
        errors.extend(check_cross_references(files))
        for e in errors:
            log.error("Data problem: %s", e)
        return cls(files), errors


def check_cross_references(files: dict[str, Any]) -> list[str]:
    """Things one file refers to in another must exist (e.g. a biome's ground types)."""
    from realmwalker.data.schemas import REQUIRED_BIOMES, REQUIRED_SETTLEMENT_TYPES

    errors: list[str] = []
    terrain = set(files.get("local_terrain.json", {}).get("terrain", {}))
    biomes = files.get("biomes.json", {}).get("biomes", {})
    if biomes:
        for bid in REQUIRED_BIOMES:
            if bid not in biomes:
                errors.append(f"data/biomes.json: the game needs a biome called '{bid}'.")
    if biomes and terrain:
        for bid, b in biomes.items():
            if bid.startswith("_"):
                continue
            for i, pair in enumerate(b["local"]["ground"]):
                if not isinstance(pair[0], str) or pair[0] not in terrain:
                    errors.append(f"data/biomes.json: {bid}.local.ground[{i}] names unknown terrain {pair[0]!r}.")
                if not isinstance(pair[1], (int, float)) or pair[1] <= 0:
                    errors.append(f"data/biomes.json: {bid}.local.ground[{i}] needs a positive weight.")
            for t in b["local"]["tree_types"]:
                if t not in terrain:
                    errors.append(f"data/biomes.json: {bid}.local.tree_types names unknown terrain {t!r}.")
    sites = files.get("sites.json", {})
    if sites:
        for kind in REQUIRED_SETTLEMENT_TYPES:
            if kind not in sites.get("settlement_types", {}):
                errors.append(f"data/sites.json: the game needs a settlement type called '{kind}'.")
    names = files.get("place_names.json", {})
    for culture, tables in names.get("settlements", {}).items():
        for pattern in tables.get("patterns", []):
            for slot in textgen.slots(pattern):
                if slot not in tables:
                    errors.append(f"data/place_names.json: settlements.{culture} pattern {pattern!r} uses "
                                  f"{{{slot}}} but there is no '{slot}' list.")
    errors.extend(_check_character_refs(files))
    errors.extend(_check_combat_refs(files))
    errors.extend(_check_faction_refs(files))
    regions = names.get("regions", {})
    for kind, patterns in regions.items():
        for pattern in patterns:
            for slot in textgen.slots(pattern):
                if slot not in regions:
                    errors.append(f"data/place_names.json: regions.{kind} pattern {pattern!r} uses {{{slot}}}, "
                                  f"which is not a list in 'regions'.")
    return errors


def _check_faction_refs(files: dict[str, Any]) -> list[str]:
    from realmwalker.data.schemas import REQUIRED_FACTION_KINDS, VALUE_IDS

    data = files.get("factions.json")
    if not data:
        return []
    errors: list[str] = []
    runtime = {"land", "seat", "family", "faith", "god", "leader"}
    for kind in REQUIRED_FACTION_KINDS:
        if kind not in data["kinds"]:
            errors.append(f"data/factions.json: the game needs a faction kind called '{kind}'.")
    for kid, k in data["kinds"].items():
        for pattern in k["names"]:
            for slot in textgen.slots(pattern):
                if slot not in data["words"] and slot not in runtime:
                    errors.append(f"data/factions.json: kinds.{kid} name {pattern!r} uses {{{slot}}}, which is not a "
                                  f"list in 'words'.")
        for i, pair in enumerate(k["values"]):
            if pair[0] not in VALUE_IDS or not isinstance(pair[1], (int, float)):
                errors.append(f"data/factions.json: kinds.{kid}.values[{i}] should be [value, weight].")
    for vid in VALUE_IDS:
        if vid not in data["values"]:
            errors.append(f"data/factions.json: values needs an entry for '{vid}'.")
    cultures = set(files.get("names.json", {}).get("cultures", {}))
    for culture in cultures:
        if culture not in data["culture_laws"]:
            errors.append(f"data/factions.json: culture_laws needs laws for the '{culture}' people.")
    errors.extend(_check_law_refs(files, cultures))
    errors.extend(_check_politics_refs(files))
    errors.extend(_check_companion_refs(files))
    errors.extend(_check_unique_refs(files))
    errors.extend(_check_magic_refs(files))
    errors.extend(_check_quest_refs(files))
    return errors


def _check_quest_refs(files: dict[str, Any]) -> list[str]:
    from realmwalker.data.schemas import QUEST_TEMPLATES

    data = files.get("quests.json")
    if not data:
        return []
    errors: list[str] = []
    jobs = set(files.get("people.json", {}).get("occupations", {}))
    groups = set(files.get("creatures.json", {}).get("encounters", {}))
    items = files.get("items.json", {}).get("items", {})
    for tid in QUEST_TEMPLATES:
        if tid not in data["templates"]:
            errors.append(f"data/quests.json: templates needs '{tid}'.")
        if tid not in data["text"]:
            errors.append(f"data/quests.json: text needs '{tid}'.")
    for tid, t in data["templates"].items():
        if tid not in QUEST_TEMPLATES:
            errors.append(f"data/quests.json: templates.{tid} is not a kind of work the game knows.")
        for job in t["givers"]:
            if jobs and job not in jobs:
                errors.append(f"data/quests.json: templates.{tid} names unknown occupation {job!r}.")
        if t["reward"][0] > t["reward"][1] or t["days"][0] > t["days"][1]:
            errors.append(f"data/quests.json: templates.{tid} has a range the wrong way round.")
        for h in t["hidden"]:
            if h not in data["text"].get(tid, {}).get("hidden", {}):
                errors.append(f"data/quests.json: templates.{tid} has hidden side {h!r} but no text.hidden.{h}.")
    for b in data["beasts"]:
        if groups and b[0] not in groups:
            errors.append(f"data/quests.json: beasts names unknown encounter group {b[0]!r}.")
    for name, base in data["heirlooms"]:
        if items and base not in items:
            errors.append(f"data/quests.json: heirlooms names unknown item {base!r}.")
    return errors


def _check_magic_refs(files: dict[str, Any]) -> list[str]:
    data = files.get("magic.json")
    if not data:
        return []
    errors: list[str] = []
    items = files.get("items.json", {}).get("items", {})
    spells = files.get("spells.json", {}).get("spells", {})
    for kind, bases in data["bases"].items():
        for b in bases:
            if items and b not in items:
                errors.append(f"data/magic.json: bases.{kind} names unknown item {b!r}.")
    for sid in data["charge_spells"]:
        if spells and sid not in spells:
            errors.append(f"data/magic.json: charge_spells names unknown spell {sid!r}.")
    return errors


def _check_companion_refs(files: dict[str, Any]) -> list[str]:
    from realmwalker.data.schemas import COMPANION_LINES

    data = files.get("companions.json")
    if not data:
        return []
    errors: list[str] = []
    classes = set(files.get("classes.json", {}).get("classes", {}))
    backgrounds = set(files.get("backgrounds.json", {}).get("backgrounds", {}))
    for aid, a in data["archetypes"].items():
        for cls in a["classes"]:
            if classes and cls not in classes:
                errors.append(f"data/companions.json: archetypes.{aid} names unknown class {cls!r}.")
        if backgrounds and a["background"] not in backgrounds:
            errors.append(f"data/companions.json: archetypes.{aid} names unknown background {a['background']!r}.")
        for v in a["values"]:
            if v not in data["values"]:
                errors.append(f"data/companions.json: archetypes.{aid} has value {v!r}, which is not in 'values'.")
    for kind in COMPANION_LINES:
        if kind not in data["lines"]:
            errors.append(f"data/companions.json: lines needs '{kind}'.")
    for key in data["lines"]:
        # "road_devout": what somebody who cares about that says, in place of an ordinary "road" line.
        if key not in COMPANION_LINES and not any(key == f"{kind}_{v}" for kind in COMPANION_LINES for v in data["values"]):
            errors.append(f"data/companions.json: lines has '{key}', which is no kind of line (or no value) the game knows.")
    from realmwalker.data.schemas import BONDS

    jobs = set(files.get("people.json", {}).get("occupations", {}))
    bonds = {k: v for k, v in data["bonds"].items() if not k.startswith("_")}
    for bond in BONDS:
        if bond not in bonds:
            errors.append(f"data/companions.json: bonds needs '{bond}'.")
    for bid, b in bonds.items():
        for cls in b.get("classes", []):
            if classes and cls not in classes:
                errors.append(f"data/companions.json: bonds.{bid} names unknown class {cls!r}.")
        if backgrounds and b.get("background", "soldier") not in backgrounds:
            errors.append(f"data/companions.json: bonds.{bid} names unknown background {b['background']!r}.")
        for v in b.get("values", []):
            if v not in data["values"]:
                errors.append(f"data/companions.json: bonds.{bid} has value {v!r}, which is not in 'values'.")
        for job in b.get("jobs", []):
            if jobs and job not in jobs:
                errors.append(f"data/companions.json: bonds.{bid} names unknown job {job!r}.")
    return errors


def _check_unique_refs(files: dict[str, Any]) -> list[str]:
    """The seven unique companions may only be made of things the game has."""
    from realmwalker.data.schemas import COMPANION_LINES

    data = files.get("uniques.json")
    if not data:
        return []
    errors: list[str] = []
    races = files.get("races.json", {}).get("races", {})
    classes = files.get("classes.json", {}).get("classes", {})
    backgrounds = files.get("backgrounds.json", {}).get("backgrounds", {})
    items = files.get("items.json", {}).get("items", {})
    spells = files.get("spells.json", {}).get("spells", {})
    skills = files.get("rules.json", {}).get("skills", {})
    props = files.get("magic.json", {}).get("properties", {})
    creatures = files.get("creatures.json", {}).get("creatures", {})
    traits = files.get("people.json", {}).get("personality", {})
    values = files.get("companions.json", {}).get("values", {})
    uniques = {k: v for k, v in data["uniques"].items() if not k.startswith("_")}

    def bad(uid: str, what: str) -> None:
        errors.append(f"data/uniques.json: {uid} {what}.")

    for uid, u in uniques.items():
        race = races.get(u["race"])
        if races and race is None:
            bad(uid, f"is of unknown race {u['race']!r}")
        elif race is not None and u["culture"] not in race["cultures"]:
            bad(uid, f"has culture {u['culture']!r}, which {u['race']} do not have")
        cls = classes.get(u["class"])
        if classes and cls is None:
            bad(uid, f"is of unknown class {u['class']!r}")
        elif cls is not None:
            if u.get("subclass") and u["subclass"] not in cls.get("subclasses", {}):
                bad(uid, f"names unknown subclass {u['subclass']!r}")
            if u.get("style") and u["style"] not in cls.get("fighting_styles", {}):
                bad(uid, f"names unknown fighting style {u['style']!r}")
        if backgrounds and u["background"] not in backgrounds:
            bad(uid, f"names unknown background {u['background']!r}")
        for s in u["skills"] + u["expertise"]:
            if skills and s not in skills:
                bad(uid, f"names unknown skill {s!r}")
        for s in u.get("cantrips", []) + u.get("spells", []):
            if spells and s not in spells:
                bad(uid, f"names unknown spell {s!r}")
        for pair in u["kit"]:
            if items and (not isinstance(pair[0], str) or pair[0] not in items):
                bad(uid, f"carries unknown item {pair[0]!r}")
        if items and u["item"]["base"] not in items:
            bad(uid, f"has a signature item made of unknown item {u['item']['base']!r}")
        for p in u["item"]["props"]:
            if props and p["kind"] not in props:
                bad(uid, f"has a signature item with unknown property {p['kind']!r}")
            if p.get("spell") and spells and p["spell"] not in spells:
                bad(uid, f"has a signature item that casts unknown spell {p['spell']!r}")
        for v in u["values"]:
            if values and v not in values:
                bad(uid, f"has value {v!r}, which is not in data/companions.json")
        if creatures and u["stats"] not in creatures:
            bad(uid, f"fights as unknown creature {u['stats']!r}")
        for t in u["traits"]:
            if traits and t not in traits:
                bad(uid, f"has unknown personality trait {t!r}")
        for kind in u["lines"]:
            if kind not in COMPANION_LINES:
                bad(uid, f"has lines of unknown kind {kind!r}")
        if "default" not in u["bond_text"]:
            bad(uid, "needs a 'default' bond_text")
    for pair in data["banter"]:
        if not pair.startswith("_") and any(p not in uniques for p in pair.split("+")):
            errors.append(f"data/uniques.json: banter {pair!r} names someone who is not one of the uniques.")
    return errors


def _check_politics_refs(files: dict[str, Any]) -> list[str]:
    from realmwalker.data.schemas import POLITICS_RATES, POLITICS_TEXT

    data = files.get("politics.json")
    if not data:
        return []
    errors: list[str] = []
    for kind in POLITICS_TEXT:
        if kind not in data["text"]:
            errors.append(f"data/politics.json: text needs words for '{kind}'.")
    for rate in POLITICS_RATES:
        if rate not in data["rates"]:
            errors.append(f"data/politics.json: rates needs '{rate}'.")
    races = set(files.get("races.json", {}).get("races", {}))
    for key in ("lifespan", "reign"):
        for race in races:
            if race not in data[key]:
                errors.append(f"data/politics.json: {key} needs an entry for {race!r}.")
    for cause in ("old", "illness", "battle", "murder", "accident", "plague"):
        if cause not in data["causes"]:
            errors.append(f"data/politics.json: causes needs '{cause}'.")
    errors.extend(_check_history_refs(files))
    return errors


def _check_history_refs(files: dict[str, Any]) -> list[str]:
    """data/history.json: words for every event the ages tell, beasts that exist, peoples for every culture."""
    from realmwalker.data.schemas import HISTORY_TEXT

    data = files.get("history.json")
    if not data:
        return []
    errors: list[str] = []
    for kind in HISTORY_TEXT:
        if kind not in data["text"]:
            errors.append(f"data/history.json: text needs words for '{kind}'.")
    creatures = files.get("creatures.json", {})
    for name, beast in data["beasts"].items():
        if creatures and beast["creature"] not in creatures.get("creatures", {}):
            errors.append(f"data/history.json: beast {name!r} is a {beast['creature']!r}, which is not a creature.")
        if creatures and beast["group"] not in creatures.get("encounters", {}):
            errors.append(f"data/history.json: beast {name!r} fights as {beast['group']!r}, which is not an "
                          f"encounter group.")
    if "dragon" not in data["beasts"]:
        errors.append("data/history.json: beasts needs 'dragon'.")
    cultures = set(files.get("names.json", {}).get("cultures", {}))
    for culture in cultures:
        if culture not in data["peoples"]:
            errors.append(f"data/history.json: peoples needs an entry for the {culture!r} people.")
    for kind in ("city", "town", "village", "hamlet", "doomed"):
        if kind not in data["spots"]["plans"]:
            errors.append(f"data/history.json: spots.plans needs '{kind}'.")
    faiths = files.get("factions.json", {}).get("faiths", {})
    for faith in faiths:
        if faith not in data["pantheon"]:
            errors.append(f"data/history.json: pantheon needs the gods of {faith!r}.")
    for form in data["works"]["forms"].values():
        for title in form["titles"]:
            if "{subject}" not in title:
                errors.append(f"data/history.json: the title {title!r} must name its {{subject}}.")
    return errors


def _check_law_refs(files: dict[str, Any], cultures: set) -> list[str]:
    from realmwalker.data.schemas import PUNISHMENT_STEPS

    law = files.get("law.json")
    if not law:
        return []
    errors: list[str] = []
    items = set(files.get("items.json", {}).get("items", {}))
    creatures = set(files.get("creatures.json", {}).get("creatures", {}))
    classes = set(files.get("classes.json", {}).get("classes", {}))
    kinds = set(files.get("factions.json", {}).get("kinds", {}))
    for level in ("lenient", "stern", "harsh", "cruel"):
        if level not in law["punishments"]:
            errors.append(f"data/law.json: punishments needs a '{level}' list.")
    for level, table in law["punishments"].items():
        for steps in table:
            for step in steps:
                if step.split(":")[0] not in PUNISHMENT_STEPS:
                    errors.append(f"data/law.json: punishments.{level} has an unknown step {step!r}.")
    for culture in cultures:
        for key in ("contraband", "hunting"):
            if culture not in law[key]:
                errors.append(f"data/law.json: {key} needs an entry for the '{culture}' people.")
    for culture, banned in law["contraband"].items():
        for item in banned:
            if items and item not in items:
                errors.append(f"data/law.json: contraband.{culture} names unknown item {item!r}.")
    for cid in law["rewards"]:
        if creatures and cid not in creatures:
            errors.append(f"data/law.json: rewards names unknown creature {cid!r}.")
    for kind, spec in law["join"].items():
        if kinds and kind not in kinds:
            errors.append(f"data/law.json: join names unknown faction kind {kind!r}.")
        for cls in spec.get("classes", []):
            if classes and cls not in classes:
                errors.append(f"data/law.json: join.{kind} names unknown class {cls!r}.")
        if spec.get("tool") and items and spec["tool"] not in items:
            errors.append(f"data/law.json: join.{kind} needs unknown tool {spec['tool']!r}.")
    for crime in ("theft", "assault", "murder", "trespass", "resisting_arrest", "jailbreak", "fleeing_arrest"):
        if crime not in law["crimes"]:
            errors.append(f"data/law.json: the game needs a crime called '{crime}'.")
    return errors


def _check_character_refs(files: dict[str, Any]) -> list[str]:
    """Races, classes and backgrounds must only mention skills, tools, items and cultures that exist."""
    errors: list[str] = []
    rules = files.get("rules.json")
    items = files.get("items.json", {}).get("items")
    if not rules or items is None:
        return errors
    skills = set(rules["skills"])
    tools = set(rules["tools"])
    cultures = set(files.get("names.json", {}).get("cultures", {}))

    def need(kind: str, value: str, pool: set, where: str) -> None:
        if value not in pool:
            errors.append(f"{where} mentions unknown {kind} '{value}'.")

    for rid, race in files.get("races.json", {}).get("races", {}).items():
        for s in race["skills"]:
            need("skill", s, skills, f"data/races.json: {rid}")
        for t in race.get("tools_choice", []):
            need("tool", t, tools, f"data/races.json: {rid}")
        for c in race["cultures"]:
            if cultures:
                need("culture", c, cultures, f"data/races.json: {rid}")
    for cid, cls in files.get("classes.json", {}).get("classes", {}).items():
        for s in cls["skill_choices"]:
            need("skill", s, skills, f"data/classes.json: {cid}")
        for t in cls["tools"]:
            need("tool", t, tools, f"data/classes.json: {cid}")
        for kit in cls["kits"]:
            for item_id, qty in kit["items"]:
                need("item", item_id, set(items), f"data/classes.json: {cid} kit '{kit['name']}'")
    for bid, bg in files.get("backgrounds.json", {}).get("backgrounds", {}).items():
        for s in bg["skills"]:
            need("skill", s, skills, f"data/backgrounds.json: {bid}")
        for t in bg["tools"]:
            need("tool", t, tools, f"data/backgrounds.json: {bid}")
        for item_id, qty in bg["items"]:
            need("item", item_id, set(items), f"data/backgrounds.json: {bid}")
    for pack, entries in files.get("items.json", {}).get("starting_packs", {}).items():
        for item_id, qty in entries:
            need("item", item_id, set(items), f"data/items.json: starting pack '{pack}'")
    for iid, item in items.items():
        if "ammo" in item:
            need("item", item["ammo"], set(items), f"data/items.json: {iid} ammo")
        if "tool" in item:
            need("tool", item["tool"], tools, f"data/items.json: {iid}")
        for s in item.get("bonus", {}).get("skills", {}):
            need("skill", s, skills, f"data/items.json: {iid} bonus")
        materials = set(files.get("items.json", {}).get("materials", {}))
        for m in item.get("mends", {}).get("materials", []):
            need("material", m, materials, f"data/items.json: {iid} mends")
        thrown = (item.get("use") or {}).get("throw") if isinstance(item.get("use"), dict) else None
        spells = files.get("spells.json", {}).get("spells", {})
        if thrown and spells and thrown not in spells:
            errors.append(f"data/items.json: {iid} is thrown as unknown spell '{thrown}'.")
    return errors


def _check_combat_refs(files: dict[str, Any]) -> list[str]:
    """Creatures carry real items, encounter groups name real creatures, sites name real groups,
    and class spell lists name real spells."""
    errors: list[str] = []
    data = files.get("creatures.json")
    items = set(files.get("items.json", {}).get("items", {}))
    if data:
        creatures = {k for k in data["creatures"] if not k.startswith("_")}
        groups = {k for k in data["encounters"] if not k.startswith("_")}
        for cid in creatures:
            d = data["creatures"][cid]
            for item_id, _ in d.get("gear", []) + d.get("loot", []):
                if items and item_id not in items:
                    errors.append(f"data/creatures.json: {cid} carries unknown item '{item_id}'.")
            if not d.get("attacks"):
                errors.append(f"data/creatures.json: {cid} has no attacks.")
        for gid in groups:
            g = data["encounters"][gid]
            for member in g["members"]:
                if member[0] not in creatures:
                    errors.append(f"data/creatures.json: encounter group {gid} names unknown creature '{member[0]}'.")
            if not g.get("intro"):
                errors.append(f"data/creatures.json: encounter group {gid} needs at least one intro line.")
        for kind, listed in data.get("site_inhabitants", {}).items():
            if kind.startswith("_"):
                continue
            for gid in listed:
                if gid not in groups:
                    errors.append(f"data/creatures.json: site_inhabitants.{kind} names unknown group '{gid}'.")
    diseases = files.get("diseases.json", {}).get("diseases", {})
    injuries = files.get("health.json", {}).get("injuries", {})
    if data and diseases:
        for cid, d in data["creatures"].items():
            if cid.startswith("_"):
                continue
            for a in d.get("attacks", []):
                if a.get("disease") and a["disease"] not in diseases:
                    errors.append(f"data/creatures.json: {cid} spreads unknown disease '{a['disease']}'.")
    for did, d in diseases.items():
        lasting = d.get("lasting") if isinstance(d, dict) else None
        if lasting and injuries and lasting.get("injury") not in injuries:
            errors.append(f"data/diseases.json: {did} leaves unknown injury '{lasting.get('injury')}'.")
    items = set(files.get("items.json", {}).get("items", {}))
    groups = set((data or {}).get("encounters", {}))
    skills = set(files.get("rules.json", {}).get("skills", {}))
    camping = files.get("camping.json")
    if camping and items:
        for biome, spec in camping.get("forage", {}).items():
            for entry in spec.get("find", []) + spec.get("extra", []):
                if entry[0] not in items:
                    errors.append(f"data/camping.json: forage.{biome} finds unknown item '{entry[0]}'.")
        for biome, spec in camping.get("hunt", {}).items():
            for g in spec.get("game", []):
                if g[3] and g[3] not in items:
                    errors.append(f"data/camping.json: hunt.{biome} gives unknown item '{g[3]}'.")
        for raw, recipe in camping.get("cooking", {}).items():
            for i in (raw, recipe.get("becomes")):
                if i not in items:
                    errors.append(f"data/camping.json: cooking mentions unknown item '{i}'.")
    for eid, ev in files.get("travel_events.json", {}).get("events", {}).items():
        if eid.startswith("_") or not isinstance(ev, dict):
            continue
        for opt in ev.get("options", []):
            outs = [opt.get("outcome") or {}]
            if opt.get("check"):
                outs += [opt["check"].get("success", {}), opt["check"].get("failure", {})]
                if skills and opt["check"].get("skill") not in skills:
                    errors.append(f"data/travel_events.json: {eid} checks unknown skill '{opt['check'].get('skill')}'.")
            listed = [e[0] for e in opt.get("shop", {}).get("stock", [])]
            listed += [e[0] for e in opt.get("requires", {}).get("items", [])]
            for out in outs:
                listed += [e[0] for e in out.get("items", []) + out.get("loot", [])]
                for g in [out.get("fight")] + ([out["ambush"][0]] if out.get("ambush") else []):
                    if g and groups and g not in groups:
                        errors.append(f"data/travel_events.json: {eid} starts a fight with unknown group '{g}'.")
            for i in listed:
                if items and i not in items:
                    errors.append(f"data/travel_events.json: {eid} mentions unknown item '{i}'.")
    econ = files.get("economy.json", {})
    for kind, shop in econ.get("shops", {}).items():
        for entry in shop.get("stock", []):
            if items and entry[0] not in items:
                errors.append(f"data/economy.json: shop '{kind}' stocks unknown item '{entry[0]}'.")
    for trade in {o.get("trade") for o in files.get("people.json", {}).get("occupations", {}).values() if o.get("trade")}:
        if econ.get("shops") and trade not in econ["shops"]:
            errors.append(f"data/people.json: an occupation trades as unknown shop kind '{trade}'.")
    spells = files.get("spells.json")
    if spells:
        known = {k for k in spells["spells"] if not k.startswith("_")}
        for cls, start in spells.get("starting", {}).items():
            for key in ("cantrips", "spellbook"):
                for sid in start.get(key, []):
                    if sid not in known:
                        errors.append(f"data/spells.json: starting.{cls}.{key} names unknown spell '{sid}'.")
    return errors


def check_template_slots(fallback: dict) -> list[str]:
    """Every {slot} in a fallback table must name another table in the same set, or a runtime value."""
    errors = []
    for set_name, tables in fallback.items():
        if set_name.startswith("_") or not isinstance(tables, dict):
            continue
        allowed = set(tables) | RUNTIME_SLOTS.get(set_name, set())
        for table_name, entries in tables.items():
            for i, entry in enumerate(entries):
                for slot in textgen.slots(entry):
                    if slot not in allowed:
                        errors.append(
                            f"data/fallback_text.json: {set_name}.{table_name}[{i}] uses {{{slot}}}, "
                            f"but there is no '{slot}' list in '{set_name}'."
                        )
    return errors
