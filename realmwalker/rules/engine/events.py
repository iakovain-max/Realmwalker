"""Hook points of a fight, and the dispatcher that runs the hooks of whatever is on the fighters (docs/EXPANSIONS.md
§4.3.3).

The battle calls `emit(b, "attack_hit", actor=att, target=t, ...)` where something may step in. Every fighter's traits
and features (data/traits.json "hooks") and the spells on them (buffs, BUFF_HOOKS) are asked in a fixed order: the
creatures the event is about (its target, then its actor), then the order of battle (initiative, then fighter id); a
fighter's spells before its own traits, its traits by name. A hook
says whose event it listens to ("as"):
    self      the fighter the event is about (`actor`: whose turn starts, who rolls, who casts)
    attacker  the one attacking (`actor` of an attack event)
    target    the one attacked, hurt or felled (`target`)
    ally      a friend of the target, not the target itself
    any       every event of that kind
A hook marked "reaction" is skipped when its owner has no reaction left; the handler spends it.

Handlers are Python, registered by id (`@handler("sneak_attack")`, rules/engine/handlers/). They read and change the
event (its fields are the numbers in play: `amount`, `crit`, `hit`, `natural`...) and set `ev.stop` to end the round
of asking (a blow already turned aside needs nobody else to turn it).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable

from realmwalker.rules.engine import traits as tr

EVENTS = (
    "battle_start", "round_start", "turn_start", "turn_end", "round_end", "initiative",
    "d20_before", "d20_after",
    "attack_declared", "attack_hit", "attack_damage", "attack_missed", "critical",
    "damage_incoming", "damage_taken", "save_damage", "hp_zero", "killed",
    "spell_declared", "spell_cast", "heal_spell", "saving_throw", "ability_used",
    "condition_applied", "condition_ended",
    "move_step", "leave_reach", "enter_reach", "ally_attacked", "healed", "legendary_window",
    "short_rest", "long_rest", "dawn",
)
ROLES = ("self", "attacker", "target", "ally", "any")

HANDLERS: dict[str, Callable] = {}

# Spells on a fighter whose part in a fight is a hook (the buff's key -> its hook).
BUFF_HOOKS = {
    "death_ward": {"event": "hp_zero", "as": "target", "handler": "death_ward"},
}


def handler(name: str):
    """Register a handler by the id the data names it with."""
    def register(fn: Callable) -> Callable:
        HANDLERS[name] = fn
        return fn
    return register


def hooks_of(f, kind: str) -> list[tuple[dict, dict | None]]:
    """(hook, buff it came from or None) for one event, in the order they are asked."""
    out: list[tuple[dict, dict | None]] = []
    for buff in f.buffs:
        for key, hook in BUFF_HOOKS.items():
            if buff.get(key) and hook["event"] == kind:
                out.append((hook, buff))
    have = tr.of(f)
    cached = f.__dict__.get("_hooks")
    if cached is None or cached[0] is not have:
        defs = tr.table(f.t)
        by_kind: dict[str, list[dict]] = {}
        for t in sorted(have):
            for hook in (defs.get(t) or {}).get("hooks", ()):
                by_kind.setdefault(hook["event"], []).append(hook)
        cached = f.__dict__["_hooks"] = (have, by_kind)
    out.extend((hook, None) for hook in cached[1].get(kind, ()))
    return out


def _order(b, ev) -> list:
    """The creatures the event is about first (its target, then its actor), then everyone in the order of battle."""
    rank = {fid: i for i, fid in enumerate(b.order)}
    first = [x for x in (ev.target, ev.actor) if x is not None]
    rest = sorted((f for f in b.fighters if all(f is not x for x in first)),
                  key=lambda f: (rank.get(f.id, len(rank)), f.id))
    return list(dict.fromkeys(first)) + rest


def _listens(role: str, owner, ev) -> bool:
    if role in ("self", "attacker"):
        return owner is ev.actor
    if role == "target":
        return owner is ev.target
    if role == "ally":
        t = ev.target
        return t is not None and owner is not t and owner.team == t.team and owner.active
    return True


def emit(b, kind: str, *, actor=None, target=None, **data) -> SimpleNamespace:
    """Ask every hook listening to this event; returns the event with whatever the handlers changed."""
    ev = SimpleNamespace(kind=kind, actor=actor, target=target, stop=False, **data)
    _ensure_handlers()
    for owner in _order(b, ev):
        for hook, buff in hooks_of(owner, kind):
            if not _listens(hook["as"], owner, ev):
                continue
            if hook.get("reaction") and not owner.reaction:
                continue
            HANDLERS[hook["handler"]](b, owner, ev, hook, buff)
            if ev.stop:
                return ev
    return ev


_loaded = False


def _ensure_handlers() -> None:
    global _loaded
    if not _loaded:
        _loaded = True
        from realmwalker.rules.engine import handlers  # noqa: F401  (registers them)
