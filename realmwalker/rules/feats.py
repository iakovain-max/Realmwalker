"""Feats (Player's Handbook 2024, chapter 5; data/feats.json): taking one, its choices, and what it gives outside a
fight. What a feat does in a fight is its kernel trait (data/traits.json "feat_<id>", rules/engine/handlers/feats.py).

`Character.feats` is a list of {"id", "choices"}. Choices are made when the feat is taken: a background may fix some
(Magic Initiate (Cleric) fixes the list); the rest get sensible defaults (`default_choices`) that the player can
change on the creation screen. Spells a feat or a species lineage gives are "innate": cantrips at will, a level 1
spell once a long rest (`innate_spells`; cast in a fight as "innate:<source>:<spell id>").
"""

from __future__ import annotations

from realmwalker.rules.character import Character

# Kinds of tool a choice may name (Character.tools holds their ids).
TOOL_GROUPS = {
    "artisan": ["smiths_tools", "carpenters_tools", "leatherworkers_tools", "cooks_utensils", "calligraphers_supplies",
                "brewers_supplies", "masons_tools", "weavers_tools", "woodcarvers_tools", "potters_tools",
                "tinkers_tools", "jewelers_tools", "glassblowers_tools", "painters_supplies", "cobblers_tools",
                "alchemists_supplies", "cartographers_tools"],
    "instrument": ["lute", "flute", "drum", "bagpipes", "horn", "lyre", "viol", "shawm", "pan_flute", "dulcimer"],
    "gaming": ["dice_set", "playing_cards", "dragonchess_set", "three_dragon_ante_set"],
    "other": ["thieves_tools", "herbalism_kit", "disguise_kit", "forgery_kit", "navigators_tools", "poisoners_kit"],
}
# Good defaults, most generally useful first.
SKILL_ORDER = ["perception", "stealth", "athletics", "insight", "survival", "medicine", "persuasion", "investigation",
               "acrobatics", "arcana", "history", "religion", "nature", "intimidation", "deception", "sleight_of_hand",
               "animal_handling", "performance"]


def defs(tables) -> dict:
    return tables.feats["feats"]


def tool_name(tables, tid: str) -> str:
    return tables.rules["tools"].get(tid, tid.replace("_", " "))


def has(char: Character, fid: str) -> bool:
    return any(f["id"] == fid for f in char.feats)


def taken(char: Character, fid: str) -> list[dict]:
    return [f for f in char.feats if f["id"] == fid]


def origin_feats(tables) -> list[str]:
    return [fid for fid, d in defs(tables).items() if d["category"] == "origin"]


def name(tables, feat: dict | str) -> str:
    """'Magic Initiate (Cleric)', 'Alert'."""
    fid = feat if isinstance(feat, str) else feat["id"]
    d = defs(tables).get(fid, {})
    out = d.get("name", fid.replace("_", " ").title())
    lst = (feat.get("choices") or {}).get("list") if isinstance(feat, dict) else None
    return f"{out} ({lst.title()})" if lst else out


# ---------------------------------------------------------------------------- choices
def options(tables, char: Character, fid: str, key: str, choices: dict) -> list[str]:
    """What one of a feat's choices may be, given the others already made."""
    spec = defs(tables)[fid]["choices"][key]
    kind = spec["kind"]
    if kind == "skill":
        return [s for s in SKILL_ORDER if s in tables.rules["skills"] and s not in char.skills]
    if kind == "skill_or_tool":
        skills = [s for s in SKILL_ORDER if s in tables.rules["skills"] and s not in char.skills]
        tools = [t for group in ("artisan", "instrument", "other") for t in TOOL_GROUPS[group] if t not in char.tools]
        return skills + tools
    if kind == "tool":
        return [t for t in TOOL_GROUPS[spec["from"]] if t not in char.tools]
    if kind in ("spell_list", "ability"):
        return list(spec["from"])
    if kind in ("cantrip", "spell"):
        lst = choices.get("list", "wizard")
        level = 0 if kind == "cantrip" else int(spec.get("level", 1))
        return sorted(sid for sid, sp in tables.spells.defs.items()
                      if isinstance(sp, dict) and sp["level"] == level and lst in sp.get("classes", ()))
    return []


def default_choices(tables, char: Character, fid: str, fixed: dict | None = None) -> dict:
    """Every choice of a feat made sensibly (the fixed ones kept)."""
    out = dict(fixed or {})
    spec = defs(tables)[fid].get("choices", {})
    for key, c in spec.items():
        if key in out:
            continue
        opts = options(tables, char, fid, key, out)
        n = int(c.get("count", 1))
        if c["kind"] == "ability":
            sc = tables.classes[char.cls].get("spellcasting")
            best = max(opts, key=lambda a: (sc is not None and sc["ability"] == a, char.abilities.get(a, 10)))
            out[key] = best
        elif c["kind"] == "spell_list":
            out[key] = next((x for x in opts if x == char.cls), opts[0] if opts else "")
        elif n == 1 and c["kind"] not in ("cantrip", "spell", "skill_or_tool", "tool"):
            out[key] = opts[0] if opts else ""
        else:
            out[key] = _best(tables, c["kind"], opts)[:n]
    return out


def _best(tables, kind: str, opts: list[str]) -> list[str]:
    if kind in ("cantrip", "spell"):
        def worth(sid):  # harm first, then healing, then the rest (the Auto can use them all)
            sp = tables.spells[sid]
            from realmwalker.rules import spells as sr

            return (not sr.harms(sp), sr.heal_op(sp) is None, sp["name"])
        return sorted(opts, key=worth)
    return list(opts)


def grant(char: Character, tables, fid: str, choices: dict | None = None) -> dict:
    """Take a feat: its choices (defaults for what is not given), and what it gives at once."""
    picked = default_choices(tables, char, fid, choices)
    char.feats.append({"id": fid, "choices": picked})
    if fid == "skilled":
        for x in picked.get("skills", []):
            if x in tables.rules["skills"]:
                if x not in char.skills:
                    char.skills.append(x)
            elif x not in char.tools:
                char.tools.append(x)
    for key in ("tools",):
        for x in picked.get(key, []) if fid in ("crafter", "musician") else []:
            if x not in char.tools:
                char.tools.append(x)
    if fid == "tough":
        char.max_hp += 2 * char.level
        char.hp += 2 * char.level
    if fid == "lucky":
        char.uses["luck"] = luck_points(char)
    for src, sid, _ability in innate_spells(char, tables):
        if tables.spells[sid]["level"] > 0:
            char.uses.setdefault(innate_key(src, sid), 1)
    return picked


def luck_points(char: Character) -> int:
    return 2 + (char.level - 1) // 4


def hp_per_level(char: Character) -> int:
    """Hit points a feat adds at every level (Tough)."""
    return 2 if has(char, "tough") else 0


# ---------------------------------------------------------------------------- innate spells
def innate_key(source: str, sid: str) -> str:
    return f"innate:{source}:{sid}"


def innate_spells(char: Character, tables) -> list[tuple[str, str, str]]:
    """(source, spell id, casting ability) of every spell a feat or a lineage gives, that the game has and that the
    character's level allows (a lineage's level 3 and 5 spells)."""
    out = []
    for i, f in enumerate(char.feats):
        if f["id"] == "magic_initiate":
            ch = f.get("choices") or {}
            ability = ch.get("ability", "int")
            for sid in list(ch.get("cantrips", [])) + list(ch.get("spell", [])):
                if sid in tables.spells:
                    out.append((f"feat{i}", sid, ability))
    lineage = (tables.races.get(char.species, {}).get("lineages") or {}).get(char.lineage or "")
    if lineage:
        ability = (char.choices or {}).get("lineage_ability") or _best_ability(char)
        for lvl, sids in sorted((lineage.get("spells") or {}).items(), key=lambda p: int(p[0])):
            if char.level >= int(lvl):
                out += [("lineage", sid, ability) for sid in sids if sid in tables.spells]
    return out


def _best_ability(char: Character) -> str:
    return max(("int", "wis", "cha"), key=lambda a: char.abilities.get(a, 10))


def rest(char: Character, tables, kind: str) -> None:
    """A long rest brings back the luck and the once-a-day spells."""
    if kind != "long":
        return
    if has(char, "lucky"):
        char.uses["luck"] = luck_points(char)
    for src, sid, _ability in innate_spells(char, tables):
        if tables.spells[sid]["level"] > 0:
            char.uses[innate_key(src, sid)] = 1


def crafter_discount(char_list, tables) -> float:
    """Crafter: a fifth off plain goods, if anyone in the party has it."""
    return 0.2 if any(has(c, "crafter") for c in char_list) else 0.0


def sheet_lines(char: Character, tables) -> list[str]:
    """The feats in words, for the character sheet."""
    out = []
    for f in char.feats:
        d = defs(tables).get(f["id"])
        if not d:
            continue
        ch = f.get("choices") or {}
        extra = []
        for key, v in ch.items():
            if key in ("list", "ability"):
                continue
            vals = v if isinstance(v, list) else [v]
            words = [tables.spells[x]["name"] if x in tables.spells else
                     tables.rules["skills"][x]["name"] if x in tables.rules["skills"] else tool_name(tables, x) for x in vals]
            extra.append(", ".join(words))
        tail = f" <dim>({'; '.join(extra)})</>" if extra else ""
        out.append(f"<loot>{name(tables, f)}</> <dim>(feat)</>: {d['text']}{tail}")
    return out
