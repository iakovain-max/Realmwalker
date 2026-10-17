"""The sounds of a fight, read from what the rules record (rules/combat.Battle.events).

Each event gives sounds for two moments: "start" (the blow is swung, the bow loosed, the spell spoken) and "impact"
(it lands, or someone falls). The battle board knows when those moments are drawn and plays them then; without
pictures they follow one another closely.
"""

from __future__ import annotations

HIT_BY_TYPE = {
    "slashing": "hit_slash", "piercing": "hit_pierce", "bludgeoning": "hit_blunt",
    "fire": "burn", "cold": "frost", "lightning": "thunder", "thunder": "thunder",
    "acid": "acid", "poison": "acid",
    "necrotic": "magic_hit", "radiant": "magic_hit", "force": "magic_hit", "psychic": "magic_hit",
}
ZONE_SOUNDS = {"web": "web", "fire": "burn", "ice": "frost", "fog": "spell", "darkness": "spell",
               "guardians": "buff", "guardian": "buff", "caltrops": "drop", "bearings": "drop",
               "blades": "spell", "thorns": "web", "celestial": "buff", "icewall": "frost",
               "antimagic": "spell", "quake": "thunder", "embers": "burn", "prismatic": "buff", "glare": "buff",
               "storm": "thunder"}
BOWS = ("bow", "crossbow")
THROWN = ("sling", "dart", "javelin", "dagger", "handaxe", "hand axe", "spear", "rock", "stone", "net", "flask")


def _start_of_attack(ev: dict) -> str | None:
    weapon = str(ev.get("weapon", "")).lower()
    how = ev.get("how", "")
    if how.startswith("spell"):
        return "spell_bolt"
    if ev.get("melee"):
        return "bite" if any(w in weapon for w in ("bite", "fang", "jaws", "beak")) else "swing"
    if any(w in weapon for w in BOWS):
        return "bow"
    if any(w in weapon for w in THROWN):
        return "throw"
    return "throw" if how == "ranged" else "swing"


def battle_sounds(ev: dict) -> list[tuple[str, str]]:
    """(moment, sound) pairs for one event of a battle."""
    k = ev.get("kind")
    if k == "attack":
        out = []
        start = _start_of_attack(ev)
        if start:
            out.append(("start", start))
        if not ev.get("hit") and ev.get("armoured"):
            out.append(("impact", "deflect"))  # the blow rings off armour; a clean miss is only the swing
        return out
    if k == "damage":
        hit = HIT_BY_TYPE.get(ev.get("dtype", ""), "hit_blunt")
        return [("impact", hit)] + ([("impact", "hit_crit")] if ev.get("crit") else [])
    if k == "dart":
        return [("start", "spell_bolt")]
    if k == "cast":
        out = [("start", "spell_bolt" if ev.get("look") in ("bolt", "ray", "line") else "spell")]
        if ev.get("area") and ev.get("effect") in ("save", "breath"):
            burst = HIT_BY_TYPE.get(ev.get("dtype", ""))
            if burst and burst not in ("hit_slash", "hit_pierce", "hit_blunt"):
                out.append(("impact", burst))
        return out
    if k == "heal":
        return [("start", "heal")]
    if k == "buff":
        return [("start", "buff")]
    if k in ("down", "dead"):
        return [("impact", "fall")]
    if k == "mastery":  # a weapon's trick: the thud of a fall, the shove of a push
        sid = {"topple": "fall", "push": "hit_blunt"}.get(ev.get("trick", ""))
        return [("impact", sid)] if sid else []
    if k == "maneuver":  # a Battle Master's: steel turned aside, a friend rallied, light feet
        sid = {"Parry": "deflect", "Rally": "buff", "Evasive Footwork": "buff"}.get(ev.get("what", ""))
        return [("start", sid)] if sid else []
    if k == "disarm":
        return [("impact", "drop")]
    if k == "rearm":  # (War Bond: the bonded weapon slaps into the knight's hand)
        return [("start", "equip")]
    if k == "zone":
        sid = ZONE_SOUNDS.get(ev.get("zone", ""))
        return [("start", sid)] if sid else []
    if k == "teleport":
        return [("start", "spell")]
    if k == "token_strike":
        return [("start", "swing")]
    return []


def foes_cry(kinds: list[str]) -> str | None:
    """What the enemy sounds like as a fight begins: beasts and monsters growl, the dead moan, people say nothing."""
    if not kinds:
        return None
    if any(k == "undead" for k in kinds):
        return "moan"
    if any(k in ("beast", "giant", "dragon", "monstrosity") for k in kinds):
        return "growl"
    return None


def combat_mood(foes: list, boss_band: bool) -> str:
    """The music for a fight against these foes (fighters of the enemy side)."""
    kinds = [getattr(f, "kind", "") for f in foes]
    if "dragon" in kinds:
        return "boss/dragon"
    if boss_band:
        return "boss"
    if not kinds:
        return "combat"
    top = max(sorted(set(kinds)), key=kinds.count)
    return "combat/" + {"humanoid": "people", "beast": "beasts", "undead": "undead"}.get(top, "monsters")


def timeline(events: list[dict], now: float) -> list[tuple[float, str]]:
    """When nothing is drawn moving (animations off): each blow's sounds a moment after the last."""
    out = []
    t = now
    for ev in events:
        for moment, sid in battle_sounds(ev):
            out.append((t + (0.14 if moment == "impact" else 0.0), sid))
        if ev.get("kind") in ("attack", "cast", "dart"):
            t += 0.3
    return out
