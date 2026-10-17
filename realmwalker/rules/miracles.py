"""Divine intervention for the devout (DMG 2024 chapter 3, "Gods and Other Powers": Divine Intervention; Expansion 5
Part B). The game's side is game/gods.py: who is devout and how likely their god is to hear them, worked out as a
fight begins (`Battle.prayers`: fighter id -> {chance, faith, god, short, domains}), and what the world remembers
after. This is the fight's side: `answer` is asked by `Battle._kill` when a devout character is about to die. A small
chance; once a fight (for one of the party), and the game keeps it to once in a long while. The god does not win
the fight (the DMG: never eliminate risk and danger): the dying one comes back to their feet hurt, with one gift
chosen by the god's domain -

    life      healing: half their hit points
    light     a blinding light: a quarter of their hit points, foes within 30 feet blinded (a Constitution save)
    trickery  an escape: a quarter of their hit points, unseen (Invisible) for a round or two
    war       the god's own fire: a quarter of their hit points, and blessed (a d4 on blows and saves) for a minute
"""

from __future__ import annotations

from realmwalker.rules.engine import durations

GOD_DC = 15  # (a god's light, against a foe's Constitution)


def answer(b, f) -> bool:
    """`f` is about to die: their god may answer. True if the god did (they live)."""
    p = (getattr(b, "prayers", None) or {}).get(f.id)
    if p is None or p.get("answered") or b.answered or f.char is None or f.bond is not None or f.state == "dead":
        return False
    p["tried"] = True
    if b.rng.random() >= float(p.get("chance", 0.0)):
        return False
    p["answered"] = True
    domains = list(p.get("domains") or ("life",))
    domain = domains[0] if len(domains) == 1 else b.rng.choice(domains)
    p["domain"] = domain
    b.answered.append(f.id)
    _rise(b, f, f.max_hp // 2 if domain == "life" else max(1, f.max_hp // 4))
    god = p.get("short") or p.get("god") or "the god"
    b._event("miracle", who=f.id, domain=domain)
    b.say(f"<magic>{f.the_name} cries out to {god} - and {god} answers.</>", "magic")
    if domain == "life":
        b.say(f"Light runs into {f.the_name}'s wounds; {f.possessive} breath comes back.", "magic")
    elif domain == "light":
        b.say(f"A light like a second sun breaks over {f.the_name}.", "magic")
        for e in b.enemies_of(f):
            if e.active and b.feet(f, e) <= 30 and not b._save(e, "con", GOD_DC, against=("blinded",)):
                if durations.give(b, e, "blinded", ends=durations.until(b, e, "turn_end")):
                    b.say(f"{e.the_name} reels, blinded.", "good" if f.side == "party" else "danger")
    elif domain == "trickery":
        durations.give(b, f, "invisible", rounds=2)
        b.say(f"{f.the_name} is gone - no, there, a shadow among shadows, unseen.", "magic")
    else:
        durations.buff(f, {"attack_die": "1d4", "save_die": "1d4", "rounds": 10, "source": "god_war"})
        b.say(f"{f.the_name} rises with the god's own fire in {f.possessive} eyes.", "magic")
    return True


def _rise(b, f, hp: int) -> None:
    f.hp = max(f.hp, 1, min(f.max_hp, hp))  # (never less than they had: a word of power can strike the hale)
    f.state = "fighting"
    f.stable = False
    f.death_saves = [0, 0]
    f.conditions.pop("unconscious", None)
    b._event("heal", to=f.id, amount=f.hp)
