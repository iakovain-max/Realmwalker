"""The story engine's start-up check (docs/ADVENTURES.md §8.2): everything the story data names must exist in the code.

`problems(tables)` returns friendly lines for the data-problems screen (the App runs it after building the tables, and
tests/test_story_data.py runs it on the real data): every threat stage's effects, every blueprint's selectors, step
kinds and their fields, finale keys, ending conditions and ops; every beat's conditions, ops and checks; every boss
template's legendary actions and phase; every villain move's beat. Entries marked `from_part` are skipped until that
part is built.
"""

from __future__ import annotations

from realmwalker.game.story import LEFT
from realmwalker.game.story import beats as beatlang
from realmwalker.game.story import endings, finale, selectors, steps
from realmwalker.world import threats

BUILT_PARTS = {"A", "D"}  # the parts of Expansion 6 whose content may be used (from_part)


def _ensure_loaded() -> None:
    """Import the modules that fill the registries (each kind, selector, op and key registers itself)."""
    from realmwalker.game.story import load_all

    load_all()


def _built(entry) -> bool:
    return not isinstance(entry, dict) or entry.get("from_part", "A") in BUILT_PARTS


def _ops(where: str, ops, known: dict, out: list[str], what: str) -> None:
    for op in ops or []:
        if not op or not isinstance(op[0], str) or op[0] not in known:
            out.append(f"{where}: the {what} '{op[0] if op else op}' is not one the game knows.")


def _selector(where: str, text: str, bound: set[str], out: list[str]) -> None:
    try:
        tree = selectors.parse(text)
    except selectors.SelectorError as e:
        out.append(f"{where}: '{text}' cannot be read ({e}).")
        return
    for call in selectors.calls(tree):
        if call.name != "hidden" and call.name not in selectors.SELECTORS:
            out.append(f"{where}: the selector '{call.name}' is not one the game knows.")
    words = {id(a) for c in selectors.calls(tree) for a in c.args
             if isinstance(a, selectors.Path) and len(a.parts) == 1 and isinstance(a.parts[0], str)}
    for path in selectors.paths(tree):
        root = path.parts[0]
        if id(path) in words and root not in bound:
            continue  # (a word given to a selector: settlement_with(temple, 0, 40))
        if isinstance(root, str) and root not in bound and root not in selectors.ROOTS:
            out.append(f"{where}: '{root}' is not bound yet (a place or a role of this blueprint).")
        for part in path.parts[1:]:
            name = part.name if isinstance(part, selectors.Call) else part
            if isinstance(part, selectors.Call) and name not in selectors.PLACE_PARTS:
                out.append(f"{where}: '{name}(...)' is not a part of a place the game knows.")


def _key(where: str, text: str, out: list[str]) -> None:
    name, _ = finale.split_key(text)
    if name not in finale.KEYS:
        out.append(f"{where}: the finale key '{name}' is not one the game knows.")


def problems(tables) -> list[str]:
    _ensure_loaded()
    out: list[str] = []
    skills = set(tables.rules.get("skills", {}))
    beats = tables.beats
    bosses = tables.villains.get("bosses", {})
    creatures = getattr(tables, "creatures", None)
    news_words = (getattr(tables, "politics", None) or {}).get("text")  # (None: tables without them, in tests)
    for kid, kind in tables.threats.get("kinds", {}).items():
        if kid.startswith("_"):
            continue
        for stage in kind["stages"]:
            _ops(f"threats.json: {kid}, stage {stage['id']}", stage.get("effects"), threats.STAGE_OPS, out,
                 "stage effect")
            group = (stage.get("roads") or {}).get("group")
            if group and creatures is not None and group not in creatures.encounters:
                out.append(f"threats.json: {kid}, stage {stage['id']}: the road band '{group}' is not an encounter.")
        if kind.get("creature") and creatures is not None and kind["creature"] not in creatures:
            out.append(f"threats.json: {kid}: the creature '{kind['creature']}' is not one the game has.")
        if kind.get("band") and creatures is not None and kind["band"] not in creatures.encounters:
            out.append(f"threats.json: {kid}: its villain's band '{kind['band']}' is not an encounter.")
        ends = kind.get("ends")
        if ends and (kid not in threats.ENDINGS or (news_words is not None and ends["text"] not in news_words)):
            out.append(f"threats.json: {kid}: its own ending needs a handler in world/threats.ENDINGS and news "
                       f"'{ends['text']}' in politics.json.")
    for bid, bp in tables.adventures.get("blueprints", {}).items():
        if bid.startswith("_"):
            continue
        where = f"adventures.json: {bid}"
        bound = set(bp["cast"]) | {"patron", "ally", "allies", "rival", "innocent", "lieutenant", "traitor", "sage"}
        for name, text in bp["places"].items():
            _selector(f"{where}, places.{name}", text, bound, out)
            bound.add(name)
        for role, spec in bp["cast"].items():
            if _built(spec):
                for pick in spec["pick"]:
                    _selector(f"{where}, cast.{role}", pick, bound, out)
        for name, text in bp.get("hidden", {}).items():
            _selector(f"{where}, hidden.{name}", text, bound, out)
            bound.add(name)
        for ch in bp["chapters"]:
            for i, st in enumerate(ch["steps"]):
                sw = f"{where}, chapter {ch['id']}, step {i + 1}"
                if not _built(st):
                    continue
                cls = steps.STEPS.get(st["kind"])
                if cls is None:
                    out.append(f"{sw}: the step kind '{st['kind']}' is not one the game knows.")
                    continue
                extra = set(st) - cls.allowed() - {"from_part"}
                if extra:
                    out.append(f"{sw}: a {st['kind']} step does not take {', '.join(sorted(extra))}.")
                if "beat" in st and st["beat"] not in beats:
                    out.append(f"{sw}: there is no beat called '{st['beat']}'.")
                for wk in ("answer", "words"):
                    if st.get(wk) and st[wk] not in tables.adventures.get("words", {}):
                        out.append(f"{sw}: there are no words called '{st[wk]}' in adventures.json.")
                for field in ("at", "who", "about", "what", "to"):
                    if field == "what" and st["kind"] == "fetch":
                        continue  # (a thing's name in words: "the crown of {villain_short}")
                    if isinstance(st.get(field), str):
                        _selector(f"{sw}, {field}", st[field], bound, out)
                for route in st.get("routes", []):
                    _selector(f"{sw}, routes", route, bound | {"lore", "town"}, out)
        for lt in bp.get("lieutenants", []):  # (E.3: a band's named head)
            lw = f"{where}, lieutenant {lt['as']}"
            picks = (bp["cast"].get(lt["as"]) or {}).get("pick", [])
            if not picks or not all(p.startswith("band(") for p in picks):
                out.append(f"{lw}: a lieutenant leads a cast role that is a band (band(...)).")
            for cid in lt.get("creature", []):
                if creatures is not None and cid not in creatures:
                    out.append(f"{lw}: there is no creature '{cid}'.")
            for g in lt.get("turns", []):
                if g.partition(":")[0] not in ("clue", "key"):
                    out.append(f"{lw}: one who turns gives a clue or a key, not '{g}'.")
        fin = bp["finale"]
        if fin["template"] not in bosses:
            out.append(f"{where}: the finale's boss template '{fin['template']}' is not in villains.json.")
        _selector(f"{where}, finale.at", fin["at"], bound, out)
        for k, keys in fin.get("keys", {}).items():
            for key in keys:
                _key(f"{where}, finale.keys.{k}", key, out)
        for e in bp["endings"]:
            if not _built(e):
                continue
            ew = f"{where}, ending {e['id']}"
            for cond in e.get("if", []):
                if not endings.known_condition(cond):
                    out.append(f"{ew}: the ending condition '{cond}' is not one the game knows.")
            _ops(ew, e["ops"], endings.OPS, out, "consequence")
        if not bp["endings"] or bp["endings"][-1].get("if"):
            out.append(f"{where}: its last ending must have no 'if' (the default).")
    for bid, beat in beats.items():
        where = f"beats.json: {bid}"
        for cond in beat.get("when", {}):
            if cond not in beatlang.CONDITIONS:
                out.append(f"{where}: the condition '{cond}' is not one the game knows.")
        _ops(where, beat.get("ops"), beatlang.OPS, out, "op")
        if beat.get("leaves") and beat["leaves"] not in LEFT:
            out.append(f"{where}: it leaves '{beat['leaves']}', which the camp's picture cannot draw.")
        if beat.get("stage") and getattr(tables, "scenes", None) and beat["stage"] not in tables.scenes:
            out.append(f"{where}: it is staged as the scene '{beat['stage']}', which there is not.")
        words = tables.adventures.get("words") or None  # (tables with no words at all: a test's, nothing to check)
        for op in (beat.get("ops") or []) if words is not None else []:
            if op and op[0] == "letter" and (len(op) < 2 or op[1] not in words):
                out.append(f"{where}: its letter has no words in adventures.json ('{op[1:2]}').")
        for i, ch in enumerate(beat.get("choices", [])):
            cw = f"{where}, choice {i + 1}"
            for part in ("ops", "success", "failure"):
                _ops(cw, ch.get(part), beatlang.OPS, out, "op")
                for op in ch.get(part) or []:
                    if words is not None and op and op[0] == "letter" and (len(op) < 2 or op[1] not in words):
                        out.append(f"{cw}: its letter has no words in adventures.json ('{op[1:2]}').")
            for cond in ch.get("requires", {}):
                if cond not in beatlang.CONDITIONS:
                    out.append(f"{cw}: the requirement '{cond}' is not one the game knows.")
            if "check" in ch and ch["check"]["skill"] not in skills:
                out.append(f"{cw}: '{ch['check']['skill']}' is not a skill.")
            if "check" in ch and not ("success" in ch and "failure" in ch):
                out.append(f"{cw}: a choice with a check says what success and failure do.")
    for tid, boss in bosses.items():
        if tid.startswith("_"):
            continue
        for m in boss["menu"]:
            if m not in finale.LEGENDARY:
                out.append(f"villains.json: boss {tid}: the legendary action '{m}' is not one the game knows.")
        if "before" in boss and boss["before"]["kind"] not in finale.PHASES:
            out.append(f"villains.json: boss {tid}: what it does before its finale, '{boss['before']['kind']}', is "
                       f"not one the game knows.")
        if "phase" in boss and boss["phase"]["kind"] not in finale.PHASES:
            out.append(f"villains.json: boss {tid}: the second phase '{boss['phase']['kind']}' is not one the game "
                       f"knows.")
        if boss.get("phase", {}).get("creature") and boss["phase"]["creature"] not in tables.creatures:
            out.append(f"villains.json: boss {tid}: there is no creature '{boss['phase']['creature']}' to come at its "
                       f"second phase.")
    from realmwalker.rules.combat import MORALE_HP, FEARLESS

    for trait, tr in (tables.villains.get("lieutenants") or {}).get("traits", {}).items():
        if tr["morale"] not in set(MORALE_HP) | FEARLESS:
            out.append(f"villains.json: lieutenants' trait {trait}: the morale '{tr['morale']}' is not one the game "
                       f"knows.")
    for kind, group in (tables.villains.get("lieutenants") or {}).get("nemesis", {}).get("band", {}).items():
        if creatures is not None and group not in creatures.encounters:
            out.append(f"villains.json: lieutenants' nemesis band for {kind}, '{group}', is not an encounter.")
    from realmwalker.game.story import villain

    for mid, move in tables.villains.get("moves", {}).items():
        for b in (move["beat"], move.get("disloyal")):
            if b and b not in beats:
                out.append(f"villains.json: move {mid}: there is no beat called '{b}'.")
        for need in move.get("needs", []):
            if need not in villain.NEEDS:
                out.append(f"villains.json: move {mid}: it needs '{need}', which is not one the game knows.")
    for how, (mark, scene) in villain.SEEN.items():
        if getattr(tables, "scenes", None) and scene not in tables.scenes:
            out.append(f"story/villain.py: a reprisal by '{how}' is shown as the scene '{scene}', which there is not.")
    moves = tables.villains.get("moves", {})
    for tid, tem in tables.villains.get("tempers", {}).items():  # (E.1: a temper's weights name real moves)
        for mid in tem.get("moves", {}):
            if mid not in moves:
                out.append(f"villains.json: temper {tid}: there is no move called '{mid}'.")
    for mid in (tables.villains.get("wrath") or {}).get("moves", []):
        if mid not in moves:
            out.append(f"villains.json: wrath: there is no move called '{mid}'.")
    for kind, lst in tables.villains.get("weaknesses", {}).items():
        for w in lst:
            for key in w["keys"]:
                _key(f"villains.json: weakness {kind}/{w['id']}", key, out)
    out.extend(scene_problems(tables))
    from realmwalker.game.story import lives

    out.extend(lives.problems(tables))
    from realmwalker.game.story import goals

    out.extend(goals.self_problems())
    out.extend(goals.data_problems(tables))
    from realmwalker.game.story import situations

    out.extend(situations.problems(tables))
    from realmwalker.game.story import vignettes

    out.extend(vignettes.problems(tables))
    from realmwalker.game.story import favours

    out.extend(favours.problems(tables))
    from realmwalker.game.story import experience

    out.extend(experience.problems(tables))
    return out


def scene_problems(tables) -> list[str]:
    """Every scene's cues are ones the stage knows, every `key` has its words, every beat it opens exists."""
    from realmwalker.game.story import stage

    out = []
    for sid, scene in getattr(tables, "scenes", {}).items():
        roles = {"you"} | set(scene.get("cast", []))
        given = set(scene.get("given", []))
        for i, c in enumerate(scene["cues"]):
            where = f"scenes.json: {sid}, cue {i + 1}"
            if c["cue"] not in stage.CUES:
                out.append(f"{where}: the cue '{c['cue']}' is not one the stage knows.")
            for k in ("key", "letter"):
                if c.get(k) and c[k] not in scene.get("words", {}) and c[k] not in given:
                    out.append(f"{where}: there are no words called '{c[k]}'.")
            if c["cue"] == "beat" and c.get("id") and c["id"] not in tables.beats:
                out.append(f"{where}: there is no beat called '{c['id']}'.")
            if c.get("role"):
                roles.add(c["role"])
            for k in ("who", "to", "at", "near"):
                v = c.get(k)
                if isinstance(v, str) and v not in roles and v not in ("home", "gate", "away", "square"):
                    out.append(f"{where}: '{v}' is not cast before this cue.")
    return out
