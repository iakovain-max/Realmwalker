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


def choice_word(tables, value: str) -> str:
    """A feat choice in words: 'Dexterity', 'Fire Bolt', 'Stealth', 'Cleric', "smith's tools"."""
    rules = tables.rules
    if value in rules["abilities"]:
        return rules["abilities"][value]["name"]
    if value in tables.spells:
        return tables.spells[value]["name"]
    if value in rules["skills"]:
        return rules["skills"][value]["name"]
    if value in rules["tools"]:
        return rules["tools"][value]
    return value.replace("_", " ").title()  # a spell list, a damage type


def has(char: Character, fid: str) -> bool:
    return any(f["id"] == fid for f in char.feats)


def taken(char: Character, fid: str) -> list[dict]:
    return [f for f in char.feats if f["id"] == fid]


def origin_feats(tables) -> list[str]:
    return [fid for fid, d in defs(tables).items() if d["category"] == "origin"]


def styles(tables) -> list[str]:
    """The Fighting Style feats, in the book's order."""
    return [fid for fid, d in defs(tables).items() if d["category"] == "fighting_style"]


def style_of(char: Character, tables) -> str | None:
    """The first Fighting Style feat they have (None without one)."""
    return next((f["id"] for f in char.feats if defs(tables).get(f["id"], {}).get("category") == "fighting_style"), None)


# ---------------------------------------------------------------------------- who may take a feat
ABILITY_WORDS = {"str": "Strength", "dex": "Dexterity", "con": "Constitution", "int": "Intelligence",
                 "wis": "Wisdom", "cha": "Charisma"}
TRAINING_WORDS = {"light": "light armour", "medium": "medium armour", "heavy": "heavy armour", "shield": "shields"}


def problem(char: Character, tables, fid: str) -> str | None:
    """Why they cannot take this feat now (None when they can): its prerequisite, or having it already."""
    d = defs(tables).get(fid)
    if d is None:
        return "no such feat"
    if has(char, fid) and not d.get("repeatable"):
        return "already taken"
    pre = d.get("prerequisite") or {}
    if char.level < int(pre.get("level", 1)):
        return f"level {pre['level']} or higher"
    need = pre.get("abilities") or {}
    if need and not any(char.abilities.get(a, 10) >= int(v) for a, v in need.items()):
        return " or ".join(f"{ABILITY_WORDS[a]} {v}" for a, v in need.items()) + " or more"
    if pre.get("training") and pre["training"] not in char.armor_prof:
        return f"training with {TRAINING_WORDS.get(pre['training'], pre['training'])}"
    if pre.get("spellcasting"):
        from realmwalker.rules import spells as sr

        if not sr.is_caster(char, tables):
            return "the power to cast spells"
    if pre.get("style") and not any(f.get("rule") == "fighting_style" for f in _class_features(char, tables)):
        return "the Fighting Style feature"
    for key, spec in d.get("choices", {}).items():
        if spec["kind"] in ("damage_type", "increase") and not options(tables, char, fid, key, {}):
            return "nothing left to choose" if spec["kind"] == "damage_type" else "no ability it raises is below 20"
    return None


def _class_features(char: Character, tables) -> list[dict]:
    cls = tables.classes[char.cls]
    out = [f for f in cls["features"] if f["level"] <= char.level]
    if char.subclass:
        out += [f for f in cls["subclasses"][char.subclass]["features"] if f["level"] <= char.level]
    return out


def prerequisite_words(tables, fid: str) -> str:
    """'level 4+, Strength 13+' for a card ('' when it has none)."""
    pre = defs(tables)[fid].get("prerequisite") or {}
    out = []
    if pre.get("level"):
        out.append(f"level {pre['level']}+")
    if pre.get("abilities"):
        out.append(" or ".join(f"{ABILITY_WORDS[a]} {v}+" for a, v in pre["abilities"].items()))
    if pre.get("training"):
        out.append(f"training with {TRAINING_WORDS.get(pre['training'], pre['training'])}")
    if pre.get("spellcasting"):
        out.append("spellcasting")
    if pre.get("style"):
        out.append("the Fighting Style feature")
    return ", ".join(out)


POLEARMS = ("quarterstaff", "spear", "glaive", "halberd", "pike")  # Polearm Master's weapons


def archetype(char: Character, tables) -> str:
    """How they fight, read from their calling and what they hold: the key of data/feats.json "suggest"."""
    items = tables.items
    main, off = char.equipped_item("main_hand"), char.equipped_item("off_hand")
    md = items.get(main.def_id) if main is not None and items.category(main) == "weapon" else None
    props = md.get("properties", []) if md else []
    if char.cls == "wizard":
        return "caster"
    if char.cls == "cleric" and (md is None or "heavy" not in props):
        return "healer"
    if md is None:
        return "brawler"
    if "ranged" in props:
        return "skulker" if char.cls == "rogue" else "archer"
    if main.def_id in POLEARMS and (off is None or "heavy" in props):
        return "polearm"
    if "two_handed" in props or "heavy" in props:
        return "great_weapon"
    if off is not None and items.category(off) == "shield":
        return "shield"
    if off is not None and items.category(off) == "weapon":
        return "two_weapon"
    return "duelist"


STYLE_FOR = {"great_weapon": ["great_weapon_fighting", "interception", "defense"],
             "polearm": ["great_weapon_fighting", "interception", "defense"],
             "archer": ["archery", "defense", "blind_fighting"], "skulker": ["archery", "blind_fighting"],
             "shield": ["defense", "protection", "interception", "dueling"],
             "two_weapon": ["two_weapon_fighting", "defense"], "duelist": ["dueling", "defense"],
             "brawler": ["unarmed_fighting", "defense"]}


def suited_style(char: Character, tables, ids: list[str]) -> str:
    """Of these fighting styles, the one that suits how they fight."""
    for fid in STYLE_FOR.get(archetype(char, tables), ["defense"]):
        if fid in ids:
            return fid
    return ids[0] if ids else ""


def choosable(char: Character, tables, categories=("general", "origin")) -> list[str]:
    """The feats they could take now, of these categories (a level's ability increase: general and origin feats)."""
    return [fid for fid, d in defs(tables).items() if d["category"] in categories and d.get("offered", True)
            and problem(char, tables, fid) is None]


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
    if kind == "increase":
        out = [a for a in spec["from"] if char.abilities.get(a, 10) < int(spec.get("max", 20))]
        if spec.get("untrained_save"):
            out = [a for a in out if a not in char.saves]
        return out
    if kind == "damage_type":
        done = {(f.get("choices") or {}).get(key) for f in taken(char, fid)}
        return [x for x in spec["from"] if x not in done]
    if kind == "skill_or_expertise":
        return [x for x in spec["from"] if x not in char.expertise]
    if kind == "expertise":
        mine = list(char.skills) + [x for x in choices.get("skill", []) if x not in char.skills]
        if spec.get("any"):
            mine = list(SKILL_ORDER)  # (Boon of Skill: every skill is theirs as the boon is taken)
        return [x for x in SKILL_ORDER if x in mine and x not in char.expertise]
    if kind in ("cantrip", "spell"):
        level = 0 if kind == "cantrip" else int(spec.get("level", 1))

        def fits(sp) -> bool:
            if not isinstance(sp, dict) or sp["level"] != level or "item" in sp.get("classes", ()):
                return False
            if spec.get("schools"):
                return sp.get("school") in spec["schools"]
            if spec.get("ritual"):
                return bool(sp.get("ritual"))
            return choices.get("list", "wizard") in sp.get("classes", ())
        return sorted(sid for sid, sp in tables.spells.defs.items() if fits(sp))
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
        if c["kind"] in ("ability", "increase"):
            out[key] = best_ability(char, tables, opts) if opts else ""
        elif c["kind"] in ("damage_type", "skill_or_expertise"):
            out[key] = (opts[:n] if n > 1 else opts[0]) if opts else ""
        elif c["kind"] == "spell_list":
            out[key] = next((x for x in opts if x == char.cls), opts[0] if opts else "")
        elif n == 1 and c["kind"] not in ("cantrip", "spell", "skill_or_tool", "tool"):
            out[key] = opts[0] if opts else ""
        else:
            out[key] = _best(tables, c["kind"], opts)[:n]
    return out


def best_ability(char: Character, tables, opts: list[str]) -> str:
    """Of these abilities, the one that serves them best: their casting ability, then their class's main ones, an odd
    score first (+1 rounds it up), then the highest."""
    cls = tables.classes[char.cls]
    sc = cls.get("spellcasting")
    primary = list(cls.get("primary", []))

    def worth(a):
        score = char.abilities.get(a, 10)
        return (sc is not None and sc["ability"] == a, a in primary, score % 2 == 1 and score < 20, score)
    return max(opts, key=worth)


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
    d = defs(tables)[fid]
    picked = default_choices(tables, char, fid, choices)
    char.feats.append({"id": fid, "choices": picked})
    for key, spec in d.get("choices", {}).items():
        vals = picked.get(key)
        vals = vals if isinstance(vals, list) else [vals] if vals else []
        kind = spec["kind"]
        for x in vals:
            if kind == "increase":
                raise_ability(char, x, top=int(spec.get("max", 20)))
            elif kind in ("skill", "skill_or_tool", "tool", "skill_or_expertise", "expertise"):
                if x in tables.rules["skills"]:
                    if kind == "expertise" or kind == "skill_or_expertise" and x in char.skills:
                        if x not in char.expertise:
                            char.expertise.append(x)
                    elif x not in char.skills:
                        char.skills.append(x)
                elif x not in char.tools:
                    char.tools.append(x)
    gives = d.get("gives") or {}
    for x in gives.get("armor", []):
        if x not in char.armor_prof:
            char.armor_prof.append(x)
    for x in gives.get("weapons", []):
        if x not in char.weapon_prof:
            char.weapon_prof.append(x)
    for x in gives.get("tools", []):
        if x not in char.tools:
            char.tools.append(x)
    if gives.get("save") and picked.get(gives["save"]) and picked[gives["save"]] not in char.saves:
        char.saves.append(picked[gives["save"]])
    if fid == "weapon_master":
        from realmwalker.rules import progression

        progression.offer_masteries(char, tables)
    if fid == "tough":
        char.max_hp += 2 * char.level
        char.hp += 2 * char.level
    if fid == "boon_of_fortitude":
        char.max_hp += 40
        char.hp += 40
    if fid == "boon_of_skill":
        for x in tables.rules["skills"]:
            if x not in char.skills:
                char.skills.append(x)
    if fid == "boon_of_recovery":
        char.uses["vitality_dice"] = 10
        char.uses["last_stand"] = 1
    if fid == "lucky":
        char.uses["luck"] = luck_points(char)
    for src, sid, _ability in innate_spells(char, tables):
        if tables.spells[sid]["level"] > 0:
            char.uses.setdefault(innate_key(src, sid), 1)
    return picked


def raise_ability(char: Character, ability: str, amount: int = 1, top: int = 20) -> None:
    """An ability raised by a feat (at most 20, or 30 by an epic boon); a hardier body has more hit points at every
    level."""
    from realmwalker.rules.character import modifier

    before = modifier(char.abilities[ability])
    char.abilities[ability] = min(max(top, char.abilities[ability]), char.abilities[ability] + amount)
    if ability == "con":
        gain = (modifier(char.abilities[ability]) - before) * char.level
        char.max_hp += gain
        char.hp += gain


def level_up(char: Character, tables) -> None:
    if has(char, "lucky"):
        char.uses["luck"] = max(char.uses.get("luck", 0), luck_points(char))
    for src, sid, _ability in innate_spells(char, tables):
        if tables.spells[sid]["level"] > 0:
            char.uses.setdefault(innate_key(src, sid), 1)


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
        ch = f.get("choices") or {}
        if f["id"] == "magic_initiate":
            ability = ch.get("ability", "int")
            for sid in list(ch.get("cantrips", [])) + list(ch.get("spell", [])):
                if sid in tables.spells:
                    out.append((f"feat{i}", sid, ability))
        elif defs(tables).get(f["id"], {}).get("spells"):  # Fey Touched, Shadow Touched, Telepathic
            ability = ch.get("increase") or _best_ability(char)
            for sid in list(defs(tables)[f["id"]]["spells"]) + list(ch.get("spell", [])):
                if sid in tables.spells:
                    out.append((f"feat{i}", sid, ability))
    lineage = (tables.races.get(char.species, {}).get("lineages") or {}).get(char.lineage or "")
    if lineage:
        ability = (char.choices or {}).get("lineage_ability") or _best_ability(char)
        for lvl, sids in sorted((lineage.get("spells") or {}).items(), key=lambda p: int(p[0])):
            if char.level >= int(lvl):
                out += [("lineage", sid, ability) for sid in sids if sid in tables.spells]
    return out


def ritual_spells(char: Character, tables) -> list[str]:
    """The rituals Ritual Caster taught them (cast outside a fight, without a slot)."""
    out = []
    for f in taken(char, "ritual_caster"):
        out += [sid for sid in (f.get("choices") or {}).get("rituals", []) if sid in tables.spells]
    return list(dict.fromkeys(out))


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


def boon_resists(char: Character) -> set[str]:
    """The two kinds of harm the Boon of Energy Resistance turns."""
    out: set[str] = set()
    for f in taken(char, "boon_of_energy_resistance"):
        got = (f.get("choices") or {}).get("resist") or []
        out |= set(got if isinstance(got, list) else [got])
    return out - {""}


def adept_types(char: Character) -> set[str]:
    """The elements Elemental Adept has mastered."""
    return {(f.get("choices") or {}).get("element") for f in taken(char, "elemental_adept")} - {None, ""}


def adept_ones(char: Character, dtype: str, rolls) -> int:
    """How much Elemental Adept adds to a roll of its element: one for every die that came up 1."""
    return sum(1 for r in rolls if r == 1) if dtype in adept_types(char) else 0


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
            words = [choice_word(tables, x) for x in vals]
            extra.append(("+1 " if key == "increase" else "") + ", ".join(words))
        tail = f" <dim>({'; '.join(extra)})</>" if extra else ""
        out.append(f"<loot>{name(tables, f)}</> <dim>(feat)</>: {d['text']}{tail}")
    return out
