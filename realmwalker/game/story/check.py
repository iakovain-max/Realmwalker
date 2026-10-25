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

BUILT_PARTS = {"A"}  # the parts of Expansion 6 whose content may be used (from_part)


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
    for kid, kind in tables.threats.get("kinds", {}).items():
        if kid.startswith("_"):
            continue
        for stage in kind["stages"]:
            _ops(f"threats.json: {kid}, stage {stage['id']}", stage.get("effects"), threats.STAGE_OPS, out,
                 "stage effect")
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
                for field in ("at", "who", "about", "what"):
                    if isinstance(st.get(field), str):
                        _selector(f"{sw}, {field}", st[field], bound, out)
                for route in st.get("routes", []):
                    _selector(f"{sw}, routes", route, bound | {"lore", "town"}, out)
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
        for i, ch in enumerate(beat.get("choices", [])):
            cw = f"{where}, choice {i + 1}"
            for part in ("ops", "success", "failure"):
                _ops(cw, ch.get(part), beatlang.OPS, out, "op")
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
    for mid, move in tables.villains.get("moves", {}).items():
        if move["beat"] not in beats:
            out.append(f"villains.json: move {mid}: there is no beat called '{move['beat']}'.")
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
    from realmwalker.game.story import favours

    out.extend(favours.problems(tables))
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
