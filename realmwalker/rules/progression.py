"""Experience, levelling and resting.

A level-up adds hit points and class features at once. The choices (a subclass, ability increases or a feat, new
spells and cantrips, weapon masteries, a second fighting style) wait in `char.pending` until the player makes them on
the level-up screen, or asks for sensible choices to be made (`auto_resolve`; `suggest` is the one it would make).
A feat taken at an ability increase may leave picks of its own (which ability it raises, which element): they wait
as a "feat" choice, one pick at a time, and the feat is taken when the last is made. Rest recovers hit points, hit dice, spell slots and once-per-rest features.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules.character import Character, modifier
from realmwalker.rules.engine import resources
from realmwalker.rules.engine import traits as trs
from realmwalker.rules.spells import restore_slots


def award_xp(char: Character, xp: int, tables, rng: RNG, *, auto: bool = False) -> list[str]:
    """Give experience; returns messages (including any level-ups)."""
    if xp <= 0 or not char.alive:
        return []
    char.xp += xp
    messages = []
    table = tables.rules["xp_for_level"]
    while char.level < min(tables.rules["max_level"], len(table)) and char.xp >= table[char.level]:
        messages += level_up(char, tables, rng, auto=auto)
    return messages


def level_up(char: Character, tables, rng: RNG, *, auto: bool = False) -> list[str]:
    """Up a level: hit points and features now; choices wait in char.pending (made now if auto)."""
    notes = _level_up(char, tables, rng)
    if char.companion and rng.chance(0.5) and tables.companions:
        from realmwalker.core import textgen

        own = tables.uniques["uniques"].get(char.companion.get("unique"), {}).get("lines", {}).get("level_up")
        text = rng.choice(own or tables.companions["lines"]["level_up"])
        notes.append(textgen.fill(text, rng, {}, {"name": char.name.split()[0], "leader": "you",
                                                  **textgen.pronoun_values(char.sex)}))
    if char.pending:
        notes.append(f"<info>{char.name.split()[0]} has choices to make</> (the character sheet, c, then l).")
    if auto:
        notes += auto_resolve(char, tables)
    return notes


def feature_gives(char: Character, tables, feat: dict) -> None:
    """What a class feature gives at once (data "gives"): saving throws (Slippery Mind), tools and the kit for them
    (Assassin's Tools)."""
    gives = feat.get("gives") or {}
    for a in gives.get("saves", ()):
        if a not in char.saves:
            char.saves.append(a)
    for t in gives.get("tools", ()):
        if t not in char.tools:
            char.tools.append(t)
    for t in gives.get("armor", ()):
        if t not in char.armor_prof:
            char.armor_prof.append(t)
    for t in gives.get("weapons", ()):
        if t not in char.weapon_prof:
            char.weapon_prof.append(t)
    if feat.get("choose"):
        add_pending(char, {"kind": "option", "feature": feat["id"], "level": char.level})
    if feat.get("expertise"):  # (a wizard's Scholar, a rogue's second Expertise)
        ex = feat["expertise"]
        add_pending(char, {"kind": "expertise", "count": int(ex["count"]), "skills": list(ex.get("skills") or []),
                           "feature": feat["id"], "level": char.level})
    if feat.get("savant") and char.spells is not None:  # two of the school's spells, level 1 or 2, for nothing
        add_pending(char, {"kind": "spells", "count": 2, "school": feat["savant"], "top": 2, "feature": feat["id"],
                           "level": char.level})
    for pick in feat.get("picks", ()):  # (Spell Mastery, Signature Spells)
        if char.spells is not None:
            add_pending(char, {"kind": "pick", "feature": feat["id"], **pick, "level": char.level})
    from realmwalker.rules.inventory import add_item

    for i in gives.get("items", ()):
        if not any(x.def_id == i for x in char.inventory):
            add_item(char, tables.items, i)


def _level_up(char: Character, tables, rng: RNG) -> list[str]:
    cls = tables.classes[char.cls]
    before = trs.of_char(char, tables)
    top_before = spell_top_level(char, tables)
    savants = [f.get("savant") for f in cls["subclasses"].get(char.subclass or "", {}).get("features", [])
               if f.get("savant") and f["id"] in char.features]
    char.level += 1
    con = modifier(char.abilities["con"])
    from realmwalker.rules import feats

    gain = max(1, cls["hit_die"] // 2 + 1 + con + int(tables.races[char.race].get("hp_per_level", 0))) \
        + feats.hp_per_level(char)
    char.max_hp += gain
    char.hp += gain
    char.hit_dice += 1
    notes = [f"<good>{char.name.split()[0]} reaches level {char.level}</> (+{gain} hit points)."]
    for feat in cls["features"]:
        if feat["level"] != char.level:
            continue
        if feat["id"] == "subclass" and not char.subclass:
            add_pending(char, {"kind": "subclass", "level": char.level})
        elif feat["id"] == "asi":
            add_pending(char, {"kind": "asi", "level": char.level})
        elif feat["id"] == "epic_boon":  # level 19 (2024): an epic boon, or another feat
            add_pending(char, {"kind": "boon", "level": char.level})
        elif feat["id"] not in char.features:
            char.features.append(feat["id"])
            notes.append(f"New: {feat['name']}.")
            feature_gives(char, tables, feat)
    if char.subclass:
        for feat in cls["subclasses"][char.subclass]["features"]:
            if feat["level"] == char.level and feat["id"] not in char.features:
                char.features.append(feat["id"])
                notes.append(f"New: {feat['name']}.")
                feature_gives(char, tables, feat)
                _offer_style(char, feat)
    if char.cls == "wizard" and char.spells:
        add_pending(char, {"kind": "spells", "count": 2, "level": char.level})
        if spell_top_level(char, tables) > top_before:  # a new level of slots: one more of a Savant's school
            for school in savants:
                add_pending(char, {"kind": "spells", "count": 1, "school": school, "level": char.level})
    offer_masteries(char, tables)  # a fourth kind of weapon at level 4, a fifth at 10 (fighters)
    cantrips = cls.get("spellcasting", {}).get("cantrips")
    if cantrips and char.spells:
        missing = cantrips[char.level - 1] - len(char.spells.get("cantrips", []))
        if missing > 0:
            add_pending(char, {"kind": "cantrips", "count": missing, "level": char.level})
    resources.granted(char, tables, before)  # a new Action Surge or Channel Divinity starts ready
    from realmwalker.rules import feats

    feats.level_up(char, tables)  # more luck points; a lineage's spell of this level ready to cast
    return notes


# ---------------------------------------------------------------------------- level-up choices
# ---------------------------------------------------------------------------- weapon masteries (PHB 2024)
def mastery_count(char: Character, tables) -> int:
    """How many kinds of weapon the class lets them master at this level (0 without Weapon Mastery), and one more for
    each Weapon Master feat."""
    table = tables.classes[char.cls].get("mastery") or []
    from realmwalker.rules import feats

    return max([0] + [n for lvl, n in table if char.level >= lvl]) + len(feats.taken(char, "weapon_master"))


def mastery_options(char: Character, tables) -> list[str]:
    """The weapons they could master: those they are proficient with that have a mastery, the ones in the pack first,
    then by the weapon's worth to their class (finesse and ranged for a rogue)."""
    from realmwalker.rules.character import Sheet

    items = tables.items
    s = Sheet(char, tables)
    carried = {it.def_id for it in char.inventory}
    out = []
    for wid, d in items.defs.items():
        if d.get("category") != "weapon" or not d.get("mastery") or d.get("rare") or wid in char.masteries:
            continue
        from realmwalker.rules.items import Item

        if not s.proficient_with_weapon(Item(0, wid)):
            continue
        out.append(wid)
    best = max(("str", "dex"), key=lambda a: char.abilities.get(a, 10))

    def rank(wid):
        d = items.get(wid)
        props = d.get("properties", [])
        suits = ("finesse" in props or "ranged" in props) if best == "dex" else ("ranged" not in props)
        return (wid not in carried, not suits, -_avg_damage(d.get("damage", "1")), d["name"])

    return sorted(out, key=rank)


def _avg_damage(expr: str) -> float:
    from realmwalker.core import dice

    try:
        n, sides, flat = dice.parse(expr)
    except dice.DiceError:
        return 0.0
    return n * (sides + 1) / 2 + flat


def masteries_due(char: Character, tables) -> int:
    """How many more masteries they may choose now (already waiting in a choice counts)."""
    waiting = sum(c.get("count", 1) for c in char.pending if c["kind"] == "mastery")
    return max(0, mastery_count(char, tables) - len(char.masteries) - waiting)


def offer_masteries(char: Character, tables) -> None:
    """Add a waiting choice for the masteries they have room for (creation, a level, a long rest's change)."""
    n = masteries_due(char, tables)
    if n > 0 and mastery_options(char, tables):
        add_pending(char, {"kind": "mastery", "count": n, "level": char.level})


def relearn_masteries(char: Character, tables) -> bool:
    """After a long rest (2024): put the masteries aside to choose them again. False if they cannot now."""
    if not mastery_count(char, tables) or char.uses.get("mastery_change", 0) <= 0:
        return False
    char.uses["mastery_change"] = 0
    char.masteries = []
    char.pending = [c for c in char.pending if c["kind"] != "mastery"]
    offer_masteries(char, tables)
    return True


def _offer_style(char: Character, feature: dict) -> None:
    """A feature that teaches another fighting style (the Champion's at level 10) waits as a choice of style feat."""
    if feature.get("rule") == "fighting_style" and feature["id"] != "fighting_style":
        add_pending(char, {"kind": "style", "level": char.level})


def take_feat(char: Character, tables, fid: str, *, front: bool = True) -> list[str]:
    """Begin taking a feat at a level: at once if it leaves nothing to pick, or a "feat" choice that waits for its
    picks (put first, so the level-up screen asks them next)."""
    from realmwalker.rules import feats

    choice = {"kind": "feat", "feat": fid, "made": {}, "level": char.level, "new": True}
    if _feat_step(char, tables, choice) is None:
        return _finish_feat(char, tables, choice)
    if front:
        char.pending.insert(0, choice)
    else:
        char.pending.append(choice)
    return [f"{char.name.split()[0]} begins to learn {feats.name(tables, fid)}."]


def _feat_step(char: Character, tables, choice: dict):
    """(key, spec, options) of the next pick a feat being taken needs, or None when all are made. A pick with only one
    possible answer is made at once."""
    from realmwalker.rules import feats

    fid, made = choice["feat"], choice["made"]
    for key, spec in feats.defs(tables)[fid].get("choices", {}).items():
        n = int(spec.get("count", 1))
        have = made.get(key)
        if n == 1 and have is not None or n > 1 and len(have or []) >= n:
            continue
        opts = [o for o in feats.options(tables, char, fid, key, made) if o not in (have or [])]
        if n == 1 and len(opts) == 1:
            made[key] = opts[0]
            continue
        if not opts:
            made.setdefault(key, [] if n > 1 else "")
            continue
        return key, spec, opts
    return None


def _finish_feat(char: Character, tables, choice: dict) -> list[str]:
    from realmwalker.rules import feats

    from realmwalker.rules.engine import resources
    from realmwalker.rules.engine import traits as tr

    fid = choice["feat"]
    picked = {k: v for k, v in choice["made"].items() if v not in ("", [])}
    before = tr.of_char(char, tables)
    feats.grant(char, tables, fid, picked)
    resources.granted(char, tables, before)  # (its pools start full: Last Stand, the ten dice)
    if choice in char.pending:
        char.pending.remove(choice)
    return [f"{char.name.split()[0]} takes the feat {feats.name(tables, char.feats[-1])}."]


def _pick_label(tables, kind: str, value: str) -> tuple[str, str]:
    """Words for one pick of a feat: (label, details)."""
    from realmwalker.rules import feats

    rules = tables.rules
    if kind == "increase":
        return f"+1 {rules['abilities'][value]['name']}", ""
    if kind == "damage_type":
        return value.title(), f"Your spells of {value} ignore resistance to it; a 1 on their damage dice counts as 2."
    if kind in ("cantrip", "spell") and value in tables.spells:
        sp = tables.spells[value]
        return sp["name"], sp.get("text", sp.get("description", ""))
    if value in rules["skills"]:
        return rules["skills"][value]["name"], f"({rules['skills'][value]['ability'].upper()})"
    return feats.choice_word(tables, value), ""


def add_pending(char: Character, choice: dict) -> None:
    choice = dict(choice, new=True)
    char.pending.append(choice)


def spell_top_level(char: Character, tables) -> int:
    sc = tables.classes[char.cls].get("spellcasting")
    if not sc:
        return 0
    return len(sc["slots"][min(char.level, len(sc["slots"])) - 1])


def options(char: Character, tables, choice: dict) -> list[tuple[str, str, str]]:
    """(id, label, details) for one pending choice."""
    cls = tables.classes[char.cls]
    kind = choice["kind"]
    names = {a: tables.rules["abilities"][a]["name"] for a in tables.rules["abilities"]}
    if kind == "option":
        feat = next((f for f in cls["features"] if f["id"] == choice["feature"]), {})
        return [(o, cls["options"][o]["name"], cls["options"][o]["text"]) for o in feat.get("choose", ())
                if o not in char.features]
    if kind == "subclass":
        return [(sid, s["name"], s.get("text", "") + " " + "; ".join(
            f"level {f['level']}: {f['name']}" for f in s.get("features", [])))
            for sid, s in cls["subclasses"].items()]
    if kind == "feat":
        step = _feat_step(char, tables, choice)
        if step is None:
            return []
        key, spec, opts = step
        out = []
        for v in opts:
            label, details = _pick_label(tables, spec["kind"], v)
            out.append((v, label, details))
        return out
    if kind == "style":
        from realmwalker.rules import feats

        return [(fid, feats.name(tables, fid), feats.defs(tables)[fid]["text"]) for fid in feats.styles(tables)
                if not feats.has(char, fid)]
    if kind == "asi":
        out = []
        for a in tables.rules["abilities"]:
            if char.abilities[a] <= 18:
                out.append((f"{a}+2", f"+2 {names[a]}", f"{names[a]} {char.abilities[a]} → {char.abilities[a] + 2}"))
        abil = list(tables.rules["abilities"])
        for i, a in enumerate(abil):
            for b in abil[i + 1:]:
                if char.abilities[a] <= 19 and char.abilities[b] <= 19:
                    out.append((f"{a}+1,{b}+1", f"+1 {names[a]}, +1 {names[b]}",
                                f"{names[a]} {char.abilities[a]} → {char.abilities[a] + 1}, "
                                f"{names[b]} {char.abilities[b]} → {char.abilities[b] + 1}"))
        primary = cls["primary"]
        out.sort(key=lambda o: (not any(p in o[0] for p in primary), 0 if "+2" in o[0] else 1))
        from realmwalker.rules import feats

        for fid in feats.choosable(char, tables):  # or a feat (2024): general feats, and origin feats not yet had
            d = feats.defs(tables)[fid]
            pre = feats.prerequisite_words(tables, fid)
            out.append((f"feat:{fid}", f"Feat: {d['name']}", d["text"] + (f" (Needs {pre}.)" if pre else "")))
        return out
    if kind == "boon":
        from realmwalker.rules import feats

        out = []
        for fid in feats.choosable(char, tables, ("epic", "general", "origin")):
            d = feats.defs(tables)[fid]
            word = "Epic boon" if d["category"] == "epic" else "Feat"
            out.append((f"feat:{fid}", f"{word}: {d['name']}", d["text"]))
        out.sort(key=lambda o: not o[1].startswith("Epic"))
        return out + [o for o in options(char, tables, {"kind": "asi"}) if not o[0].startswith("feat:")]
    if kind == "spells":
        top = min(spell_top_level(char, tables), int(choice.get("top", 9)))
        book = char.spells.get("spellbook", [])
        spells = [s for s in tables.spells.for_class(char.cls, top) if tables.spells[s]["level"] > 0 and s not in book
                  and (not choice.get("school") or tables.spells[s].get("school") == choice["school"])]
        spells.sort(key=lambda s: (-tables.spells[s]["level"], tables.spells[s]["name"]))
        return [(s, f"{tables.spells[s]['name']} (level {tables.spells[s]['level']})",
                 tables.spells[s].get("text", tables.spells[s].get("description", ""))) for s in spells]
    if kind == "mastery":
        items = tables.items
        return [(w, f"{items.get(w)['name'].title()}: {items.get(w)['mastery'].title()}",
                 tables.traits["traits"].get(f"mastery_{items.get(w)['mastery']}", {}).get("text", ""))
                for w in mastery_options(char, tables)]
    if kind == "cantrips":
        known = char.spells.get("cantrips", [])
        return [(s, tables.spells[s]["name"], tables.spells[s].get("text", tables.spells[s].get("description", "")))
                for s in tables.spells.for_class(char.cls, 0) if tables.spells[s]["level"] == 0 and s not in known]
    if kind == "expertise":
        rules = tables.rules["skills"]
        return [(sk, rules[sk]["name"], f"Twice your proficiency bonus on {rules[sk]['name']} checks.")
                for sk in sorted(char.skills) if sk in rules and sk not in char.expertise
                and (not choice.get("skills") or sk in choice["skills"])]
    if kind == "pick":
        return [(s, tables.spells[s]["name"], tables.spells[s].get("text", "")) for s in pick_options(char, tables, choice)]
    return []


def pick_options(char: Character, tables, choice: dict) -> list[str]:
    """The spellbook's spells a Spell Mastery or Signature Spells pick can take: of its level (and cast with an action,
    for Spell Mastery), not picked already."""
    have = (char.spells or {}).get(choice["key"], [])
    out = []
    for sid in (char.spells or {}).get("spellbook", []):
        sp = tables.spells.defs.get(sid)
        if sp is None or sp["level"] != int(choice["spell_level"]) or sid in have:
            continue
        if choice.get("cast") == "action" and sp.get("cast", "action") != "action":
            continue
        out.append(sid)
    return out


def choice_title(char: Character, tables, choice: dict) -> str:
    kind = choice["kind"]
    if kind == "option":
        feat = next((f for f in tables.classes[char.cls]["features"] if f["id"] == choice["feature"]), {})
        return f"{feat.get('name', 'A choice')}: choose one"
    if kind == "subclass":
        return f"Choose a path for {char.name.split()[0]}"
    if kind == "asi":
        return "Improve your abilities (+2 to one, or +1 to two), or take a feat"
    if kind == "boon":
        return "Choose an epic boon (or another feat)"
    if kind == "feat":
        from realmwalker.rules import feats

        step = _feat_step(char, tables, choice)
        what = {"increase": "which ability does it raise?", "damage_type": "which element?",
                "spell": "which spell?", "cantrip": "which cantrip?", "expertise": "expertise in which skill?",
                "skill_or_expertise": "which skill?", "skill": "which skill?", "tool": "which tool?",
                "skill_or_tool": "which skill or tool?"}.get(step[1]["kind"], "choose") if step else "done"
        return f"{feats.name(tables, choice['feat'])}: {what}"
    if kind == "style":
        return "Learn another fighting style"
    if kind == "spells":
        n = choice.get("count", 1)
        if choice.get("school"):
            return f"{choice['school'].title()} Savant: copy {n} {choice['school']} spell{'s' if n > 1 else ''} for nothing"
        return f"Copy {n} new spell{'s' if n > 1 else ''} into your spellbook"
    if kind == "expertise":
        n = choice.get("count", 1)
        return f"Expertise: choose {n} skill{'s' if n > 1 else ''} you know"
    if kind == "pick":
        level = choice["spell_level"]
        if choice["key"] == "mastery":
            return f"Spell Mastery: a level {level} spell to cast at will"
        return f"Signature Spells: {choice.get('count', 1)} level {level} spell{'s' if choice.get('count', 1) > 1 else ''}"
    if kind == "cantrips":
        n = choice.get("count", 1)
        return f"Learn {n} new cantrip{'s' if n > 1 else ''}"
    if kind == "mastery":
        n = choice.get("count", 1)
        return f"Master {n} more kind{'s' if n > 1 else ''} of weapon (its trick in battle)"
    return "Choose"


def resolve(char: Character, tables, choice: dict, option_id: str) -> list[str]:
    """Make one pending choice. Returns what changed."""
    cls = tables.classes[char.cls]
    kind = choice["kind"]
    notes = []
    if kind == "option":
        opt = cls["options"][option_id]
        char.features.append(option_id)
        feature_gives(char, tables, opt)
        if opt.get("cantrips") and char.spells is not None:
            add_pending(char, {"kind": "cantrips", "count": int(opt["cantrips"]), "level": char.level})
        notes.append(f"{char.name.split()[0]}: {opt['name']}.")
        char.pending.remove(choice)
    if kind == "subclass":
        char.subclass = option_id
        sub = cls["subclasses"][option_id]
        notes.append(f"{char.name.split()[0]} follows the {sub['name']}.")
        for feat in sub.get("features", []):
            if feat["level"] <= char.level and feat["id"] not in char.features:
                char.features.append(feat["id"])
                notes.append(f"New: {feat['name']}.")
                feature_gives(char, tables, feat)
                _offer_style(char, feat)
        char.pending.remove(choice)
    elif kind in ("asi", "boon") and option_id.startswith("feat:"):
        char.pending.remove(choice)
        notes += take_feat(char, tables, option_id[5:])
    elif kind == "feat":
        step = _feat_step(char, tables, choice)
        if step is not None:
            key, spec, _opts = step
            if int(spec.get("count", 1)) > 1:
                choice["made"].setdefault(key, []).append(option_id)
            else:
                choice["made"][key] = option_id
        if _feat_step(char, tables, choice) is None:
            notes += _finish_feat(char, tables, choice)
    elif kind == "style":
        from realmwalker.rules import feats

        feats.grant(char, tables, option_id)
        notes.append(f"{char.name.split()[0]} learns the {feats.name(tables, option_id)} fighting style.")
        char.pending.remove(choice)
    elif kind in ("asi", "boon"):
        for part in option_id.split(","):
            ability, amount = part.split("+")
            before = modifier(char.abilities[ability])
            char.abilities[ability] = min(20, char.abilities[ability] + int(amount))
            notes.append(f"{tables.rules['abilities'][ability]['name']} rises to {char.abilities[ability]}.")
            if ability == "con":
                gain = (modifier(char.abilities[ability]) - before) * char.level  # hardier at every level
                char.max_hp += gain
                char.hp += gain
        char.pending.remove(choice)
    elif kind == "mastery":
        char.masteries.append(option_id)
        d = tables.items.get(option_id)
        notes.append(f"{char.name.split()[0]} masters the {d['name']}: {d['mastery'].title()}.")
        choice["count"] = choice.get("count", 1) - 1
        if choice["count"] <= 0 or not options(char, tables, choice):
            char.pending.remove(choice)
    elif kind == "expertise":
        char.expertise.append(option_id)
        notes.append(f"{char.name.split()[0]} becomes expert in {tables.rules['skills'][option_id]['name']}.")
        choice["count"] = choice.get("count", 1) - 1
        if choice["count"] <= 0 or not options(char, tables, choice):
            char.pending.remove(choice)
    elif kind == "pick":
        char.spells.setdefault(choice["key"], []).append(option_id)
        if choice["key"] == "signature":
            char.uses[f"signature:{option_id}"] = 1
        notes.append(f"{tables.spells[option_id]['name']}: "
                     f"{'at will' if choice['key'] == 'mastery' else 'a signature spell'}.")
        choice["count"] = choice.get("count", 1) - 1
        if choice["count"] <= 0 or not options(char, tables, choice):
            char.pending.remove(choice)
    elif kind in ("spells", "cantrips"):
        key = "spellbook" if kind == "spells" else "cantrips"
        char.spells.setdefault(key, []).append(option_id)
        notes.append(f"{'Copied' if kind == 'spells' else 'Learned'} {tables.spells[option_id]['name']}.")
        choice["count"] = choice.get("count", 1) - 1
        if choice["count"] <= 0 or not options(char, tables, choice):
            char.pending.remove(choice)
    return notes


def auto_resolve(char: Character, tables) -> list[str]:
    """Sensible choices for everything waiting: the first path, the main ability, the strongest spells."""
    notes = []
    cls = tables.classes[char.cls]
    for _ in range(400):  # (each pick is a step: a wizard of 20 made at once has a hundred)
        if not char.pending:
            break
        choice = char.pending[0]
        opts = options(char, tables, choice)
        if not opts:
            char.pending.remove(choice)
            continue
        notes += resolve(char, tables, choice, suggest(char, tables, choice, opts))
    return notes


def suggest(char: Character, tables, choice: dict, opts: list | None = None) -> str:
    """The choice the Auto makes and Suggest points at: at an ability increase, +2 to the main ability while it is
    even and below 18; otherwise the feat that suits how they fight (data/feats.json "suggest", rules/feats.archetype);
    a feat's own picks and a style as the feats would choose them; the first option for the rest."""
    from realmwalker.rules import feats

    opts = options(char, tables, choice) if opts is None else opts
    ids = [o[0] for o in opts]
    if not ids:
        return ""
    kind = choice["kind"]
    cls = tables.classes[char.cls]
    if kind == "option":  # (a fighting priest guards and smites; a priest of the book prays and blasts)
        fighting = feats.archetype(char, tables) not in ("caster", "healer")
        for pick in (("order_protector", "blessed_divine_strike") if fighting else
                     ("order_thaumaturge", "blessed_potent_spellcasting")):
            if pick in ids:
                return pick
        return ids[0]
    if kind == "expertise":  # (a wizard's own field first; a rogue's sneaking and noticing)
        for sk in ("arcana", "stealth", "perception", "investigation"):
            if sk in ids:
                return sk
        return ids[0]
    if kind == "pick":  # what harms the most foes (a fireball for a signature), then what harms at all
        from realmwalker.rules import spells as spellrules

        def worth(sid: str) -> tuple:
            sp = tables.spells[sid]
            return (spellrules.harms(sp), bool(sp.get("area")), not sp.get("concentration"), sp["name"])

        return max(ids, key=worth)
    if kind == "asi":
        best = max(cls["primary"], key=lambda a: (char.abilities[a] <= 18, -cls["primary"].index(a)))
        plus_two = f"{best}+2"
        score = char.abilities[best]
        if score <= 16 and score % 2 == 0 and plus_two in ids:
            return plus_two
        for fid in tables.feats.get("suggest", {}).get(feats.archetype(char, tables), []):
            if f"feat:{fid}" in ids:
                return f"feat:{fid}"
        return plus_two if plus_two in ids else ids[0]
    if kind == "boon":
        for fid in tables.feats.get("suggest_boon", {}).get(feats.archetype(char, tables), []):
            if f"feat:{fid}" in ids:
                return f"feat:{fid}"
        return ids[0]
    if kind == "feat":
        step = _feat_step(char, tables, choice)
        if step is not None:
            key, spec, step_opts = step
            if spec["kind"] == "increase":
                pick = feats.best_ability(char, tables, step_opts)
                return pick if pick in ids else ids[0]
            want = feats.default_choices(tables, char, choice["feat"], dict(choice["made"])).get(key)
            want = want[0] if isinstance(want, list) and want else want
            return want if want in ids else ids[0]
    if kind == "style":
        return feats.suited_style(char, tables, ids)
    return ids[0]


def has_new_choices(char: Character) -> bool:
    return any(c.get("new") for c in char.pending)


def seen_choices(char: Character) -> None:
    for c in char.pending:
        c["new"] = False


def short_rest(char: Character, tables, rng: RNG, *, meal: bool = False) -> list[str]:
    """An hour's rest: spend hit dice to heal, recover short-rest features. `meal`: a Chef cooked (2024: whoever
    spends Hit Dice regains 1d8 more)."""
    notes = []
    die = tables.classes[char.cls]["hit_die"]
    con = modifier(char.abilities["con"])
    healed = 0
    from realmwalker.rules import magic

    if magic.flag(char, "no_healing"):
        notes.append(f"{char.name.split()[0]} cannot heal: the artifact will not allow it.")
    while char.hp < char.max_hp and char.hit_dice > 0 and not magic.flag(char, "no_healing"):
        char.hit_dice -= 1
        amount = max(1, dice.roll(f"1d{die}", rng).total + con)
        char.hp = min(char.max_hp, char.hp + amount)
        healed += amount
    if healed and meal:
        extra = rng.randint(1, 8)
        char.hp = min(char.max_hp, char.hp + extra)
        healed += extra
    if healed:
        notes.append(f"{char.name.split()[0]} recovers {healed} hit points.")
    resources.recover(char, tables, "short")  # Second Wind, Action Surge, Channel Divinity... (data/traits.json)
    if "arcane_recovery" in char.features and char.uses.get("arcane_recovery", 1) and char.spells \
            and any(char.spells.get("slots_used", [])[:5]):
        # (2024: slot levels adding up to half the wizard's level, rounded up, none of level 6 or higher; the
        # highest first, as a wizard would choose)
        used = char.spells.setdefault("slots_used", [0] * 9)
        budget = max(1, (char.level + 1) // 2)
        back = []
        for i in reversed(range(min(5, len(used)))):
            while used[i] and budget >= i + 1:
                used[i] -= 1
                budget -= i + 1
                back.append(i + 1)
        if back:
            char.uses["arcane_recovery"] = 0
            notes.append(f"Arcane Recovery restores spell slots (level {', '.join(str(n) for n in back)}).")
    signature_back(char)
    return notes


def signature_back(char: Character) -> None:
    """A wizard's Signature Spells: each once again after a short or long rest."""
    for sid in (char.spells or {}).get("signature", []):
        char.uses[f"signature:{sid}"] = 1


def long_rest(char: Character, tables, rng: RNG) -> list[str]:
    """A full night: hit points, spell slots and features restored; half the hit dice back."""
    if not char.alive:
        return []
    from realmwalker.rules import magic

    if not magic.flag(char, "no_healing"):
        char.hp = char.max_hp
    char.hit_dice = min(char.level, char.hit_dice + max(1, char.level // 2))
    restore_slots(char)
    resources.recover(char, tables, "long")  # every pool (data/traits.json), an orc's toughness among them
    char.uses["arcane_recovery"] = 1
    signature_back(char)
    char.uses.pop("overchannel", None)  # (an evoker's Overchannel is safe once more)
    for key in ("ward_made", "arcane_ward"):  # an abjurer's ward is made anew each day
        char.uses.pop(key, None)
    from realmwalker.rules import feats

    feats.rest(char, tables, "long")  # luck points, the once-a-day spells of a feat or a lineage
    if mastery_count(char, tables):
        char.uses["mastery_change"] = 1  # the weapons mastered may be changed (the character sheet)
        offer_masteries(char, tables)
    return [f"{char.name.split()[0]} wakes rested."]
