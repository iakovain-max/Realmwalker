"""The kernel's start-up check: everything the data names must exist in the code (docs/EXPANSIONS.md §4.3.2).

`problems(tables)` returns friendly lines for the data-problems screen (the App runs it after building the tables, and
tests/test_engine.py runs it on the real data): every condition the rules need, every trait a creature, race or class
names, every modifier, `when` test, event and handler a trait definition names.
"""

from __future__ import annotations

from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import conditions as cond
from realmwalker.rules.engine import actions, effects, events
from realmwalker.rules.engine import traits as tr

MODIFIER_KEYS = {
    "attack", "attacked", "enemy_attacks", "save", "resist", "crit_range", "passive", "ignores_zone",
    "immune_condition", "attacks",
}
MODIFIER_EXTRAS = {"when", "why", "abilities"}


def problems(tables) -> list[str]:
    out: list[str] = []
    have = cond.table(tables)
    for cid in cond.IDS:
        if cid not in have:
            out.append(f"data/conditions.json: the rules need the condition '{cid}'.")
    events._ensure_handlers()
    defs = tr.table(tables)
    for tid, d in defs.items():
        if tid.startswith("_"):
            continue
        where = f"data/traits.json: {tid}"
        for i, m in enumerate(d.get("modifiers", [])):
            keys = set(m) - MODIFIER_EXTRAS
            unknown = keys - MODIFIER_KEYS
            if unknown:
                out.append(f"{where}: modifier {i} says {', '.join(sorted(unknown))}, which the rules do not know.")
            if not keys:
                out.append(f"{where}: modifier {i} changes nothing.")
            for w in m.get("when", []):
                if w not in tr.WHEN:
                    out.append(f"{where}: modifier {i} names the test '{w}', which the rules do not have.")
        acts = d.get("activate") or []
        for a in acts if isinstance(acts, list) else [acts]:
            for o in a.get("effects", []):
                if o.get("op") not in effects.OPS:
                    out.append(f"{where}: {a.get('id')} does '{o.get('op')}', which the rules cannot do.")
                if o.get("op") == "special" and o.get("handler") not in effects.SPECIAL:
                    out.append(f"{where}: {a.get('id')} calls '{o.get('handler')}', which the code does not have.")
            for r in a.get("requires", []):
                if r not in actions.REQUIRES:
                    out.append(f"{where}: {a.get('id')} requires '{r}', which the rules cannot test.")
        for i, h in enumerate(d.get("hooks", [])):
            if h["event"] not in events.EVENTS:
                out.append(f"{where}: hook {i} listens for '{h['event']}', which is not an event of a fight.")
            if h["handler"] not in events.HANDLERS:
                out.append(f"{where}: hook {i} names the handler '{h['handler']}', which the code does not have.")
    for sid, spell in tables.spells.defs.items():
        if not isinstance(spell, dict):
            continue
        for o in spellrules.ops(spell):
            if o.get("op") not in effects.OPS:
                out.append(f"data/spells.json: {sid} does '{o.get('op')}', which the rules cannot do.")
            if o.get("op") == "special" and o.get("handler") not in effects.SPECIAL:
                out.append(f"data/spells.json: {sid} calls '{o.get('handler')}', which the code does not have.")
            if o.get("op") == "condition" and o.get("condition") not in cond.table(tables):
                out.append(f"data/spells.json: {sid} gives the condition '{o.get('condition')}', which data/conditions.json "
                           "does not define.")
    for cid, c in tables.creatures.defs.items():
        for t in c.get("traits", []):
            if t not in defs:
                out.append(f"data/creatures.json: {cid} has the trait '{t}', which data/traits.json does not define.")
    for rid, r in tables.races.items():
        for t in r.get("traits", []):
            if t.get("rule") and t["rule"] not in defs:
                out.append(f"data/races.json: {rid} trait {t['id']} has the rule '{t['rule']}', "
                           "which data/traits.json does not define.")
    for cls_id, c in tables.classes.items():
        feats = list(c.get("features", []))
        for sub in c.get("subclasses", {}).values():
            feats += sub.get("features", [])
        for f in feats:
            if f.get("rule") and f["rule"] not in defs:
                out.append(f"data/classes.json: {cls_id} feature {f['id']} has the rule '{f['rule']}', "
                           "which data/traits.json does not define.")
    return out
