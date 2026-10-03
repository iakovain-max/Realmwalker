"""Health over time: bleeding and blood, pain, infection, wounds healing (or healing badly), lasting
injuries, diseases, drink, painkillers and addiction, and the treatment of all of it.

Pure rules on a Character; game/survival.py calls tick() as time passes and the Health screen
calls the treatment functions. Hit points are stamina and luck; wounds, blood and sickness are
the body. Numbers here are tuned so that:
- a minor cut heals in about three days, a serious wound in about ten, a critical one in three
  weeks, and a broken bone in about a month (and only straight if splinted);
- most cuts clot by themselves after costing some blood; a gushing wound left alone kills in hours;
- an open wound left dirty often festers; a festering wound can kill in about a week.
"""

from __future__ import annotations

from dataclasses import dataclass

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules import body
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.inventory import WATER_RISK, container_capacity, remove_item
from realmwalker.rules.wounds import PART_LABEL, SEVERITY, Wound

WOUND_PAIN = {1: 1, 2: 3, 3: 6}
BLEED_PER_HOUR = {1: 3.0, 2: 6.0, 3: 15.0}  # blood lost per hour by an unbandaged wound
INTERNAL_PER_HOUR = 3.0
CLOT_CHANCE_PER_HOUR = {1: 0.35, 2: 0.25, 3: 0.10}  # a bleed easing by one step on its own (resting)
HEAL_HOURS = {1: 72.0, 2: 240.0, 3: 360.0}  # hours to heal one step of severity
FRACTURE_HEAL_HOURS = {1: 300.0, 2: 600.0, 3: 720.0}
OPEN_KINDS = {"cut", "puncture", "bite", "burn", "frostbite"}
INFECTION_PER_DAY = {1: 0.06, 2: 0.14, 3: 0.25}  # chance a fresh open wound festers, per day
# Each day a festering wound is fought: a good day takes this much off, a bad day adds this (until 2026-10, 12 off and
# 20 on: even a cleaned, bound wound on a resting body drifted towards the grave once it had turned).
INFECTION_EASES = 14.0
INFECTION_SPREADS = 16.0
BLOOD_REGEN_PER_HOUR = 1.0
PAIN_STAGES = [(15, "in shock", "danger"), (10, "in agony", "danger"), (6, "in pain", "warn"), (3, "hurting", "dim")]
BLOOD_STAGES = [(25, "bleeding to death", "danger"), (40, "collapsing", "danger"), (60, "faint", "warn"), (80, "pale", "dim")]
INTOX_STAGES = [(70, "very drunk", "warn"), (45, "drunk", "warn"), (20, "tipsy", "dim")]


@dataclass
class HealthContext:
    activity: str = "rest"
    marsh: bool = False  # in marsh country
    warm_season: bool = False
    now: int = 0


class DiseaseTable:
    def __init__(self, data: dict) -> None:
        self.defs: dict[str, dict] = {k: v for k, v in data["diseases"].items() if not k.startswith("_")}

    def __getitem__(self, did: str) -> dict:
        return self.defs[did]

    def __contains__(self, did: str) -> bool:
        return did in self.defs

    def spread_by(self, source: str) -> list[str]:
        return [k for k, d in self.defs.items() if source in d["spread"]]


# ---------------------------------------------------------------------------- reading the body
def pain(char: Character, tables=None) -> int:
    total = 0.0
    for w in char.wounds:
        p = WOUND_PAIN.get(w.severity, 1)
        if w.kind == "fracture" and not w.splinted:
            p += 2
        if w.infection >= 30:
            p += 2
        eased = int(w.bandaged) + int(w.splinted) + int(w.stitched)
        total += max(p / 2, p - eased)
    if tables is not None:
        total += sum(float(e.get("pain", 0)) for e in disease_effects(char, tables))
    if char.effects.get("withdrawal", 0) > 0:
        total += 3
    if char.effects.get("hangover", 0) > 0:
        total += 1
    if char.effects.get("poppy", 0) > 0:
        total -= 8
    total -= char.intoxication / 12.0
    return max(0, int(round(total)))


def _stage(value: float, stages: list, below: bool = False) -> tuple[str, str] | None:
    for limit, word, color in stages:
        if (value < limit) if below else (value >= limit):
            return word, color
    return None


def pain_stage(char: Character, tables=None) -> tuple[str, str] | None:
    return _stage(pain(char, tables), PAIN_STAGES)


def blood_stage(char: Character) -> tuple[str, str] | None:
    return _stage(char.blood, BLOOD_STAGES, below=True)


def intox_stage(char: Character) -> tuple[str, str] | None:
    return _stage(char.intoxication, INTOX_STAGES)


def disease_effects(char: Character, tables) -> list[dict]:
    out = []
    for d in char.diseases:
        if d.get("phase") != "sick" or d["id"] not in tables.diseases:
            continue
        stages = tables.diseases[d["id"]]["stages"]
        out.append(stages[min(d.get("stage", 0), len(stages) - 1)]["effects"])
    return out


def injury_effects(char: Character, tables) -> dict:
    merged: dict = {"skills": {}, "attack": 0, "ranged_attack": 0, "travel": 1.0, "speed": 0}
    for inj in char.injuries:
        e = tables.health["injuries"].get(inj, {}).get("effects", {})
        for sk, v in e.get("skills", {}).items():
            merged["skills"][sk] = merged["skills"].get(sk, 0) + int(v)
        merged["attack"] += int(e.get("attack", 0))
        merged["ranged_attack"] += int(e.get("ranged_attack", 0))
        merged["travel"] *= float(e.get("travel", 1.0))
        merged["speed"] += int(e.get("speed", 0))
    return merged


def penalty(char: Character, tables) -> int:
    """Everything that makes rolls worse right now, as one number (0 .. -10). Exhaustion is separate."""
    p = -body.condition_penalty(char)
    p += {"hurting": 1, "in pain": 2, "in agony": 4, "in shock": 6}.get((pain_stage(char, tables) or ("", ""))[0], 0)
    p += {"pale": 1, "faint": 2, "collapsing": 3, "bleeding to death": 4}.get((blood_stage(char) or ("", ""))[0], 0)
    p += {"drunk": 2, "very drunk": 4}.get((intox_stage(char) or ("", ""))[0], 0)
    p += sum(int(e.get("penalty", 0)) for e in disease_effects(char, tables))
    if char.effects.get("poisoned", 0) > 0:
        p += 2
    if char.effects.get("withdrawal", 0) > 0:
        p += 2
    if char.effects.get("hangover", 0) > 0:
        p += 1
    return -min(10, p)


def concussed(char: Character) -> bool:
    return any(w.part == "head" and w.severity >= 2 and w.kind in ("blunt", "fracture") for w in char.wounds)


LIMBS = ("left_arm", "right_arm", "left_leg", "right_leg")


def one_armed(char: Character) -> bool:
    """An arm taken off: one hand holds everything, and nothing needs two."""
    return "lost_left_arm" in char.injuries or "lost_right_arm" in char.injuries


def lost(char: Character, part: str) -> bool:
    return f"lost_{part}" in char.injuries


def beyond_saving(w: Wound) -> bool:
    """A limb that will kill its owner or never mend: festering towards the blood, or smashed, burnt or frozen
    past repair. Only then is taking it off offered."""
    return w.part in LIMBS and (w.infection >= 40 or w.severity >= 3 and w.kind in ("fracture", "blunt", "burn",
                                                                                     "frostbite"))


def broken_arm(char: Character, side: str) -> bool:
    """A broken bone (or a critical wound) in this arm: the hand can't hold a weapon."""
    part = f"{side}_arm"
    return any(w.part == part and (w.kind == "fracture" and w.severity >= 2 or w.severity >= 3) for w in char.wounds)


def travel_multiplier(char: Character, tables) -> float:
    m = injury_effects(char, tables)["travel"]
    for w in char.wounds:
        if w.part in ("left_leg", "right_leg"):
            m *= {1: 1.0, 2: 1.3, 3: 1.7}[w.severity] * (1.15 if w.kind == "fracture" and not w.splinted else 1.0)
    for e in disease_effects(char, tables):
        m *= float(e.get("travel", 1.0))
    m *= {"faint": 1.2, "collapsing": 1.5, "bleeding to death": 2.0}.get((blood_stage(char) or ("", ""))[0], 1.0)
    m *= {"in agony": 1.3, "in shock": 2.0}.get((pain_stage(char, tables) or ("", ""))[0], 1.0)
    return m


# ---------------------------------------------------------------------------- catching things
def expose(char: Character, tables, disease_id: str, rng: RNG) -> bool:
    """Something that could give a disease happened. Returns True if it starts to incubate."""
    if disease_id not in tables.diseases or any(d["id"] == disease_id for d in char.diseases):
        return False
    if "plague_proof" in char.features:  # Sister Wendeline has never once been ill
        return False
    d = tables.diseases[disease_id]
    lo, hi = d["incubation_hours"]
    char.diseases.append({"id": disease_id, "phase": "incubating", "stage": 0, "hours": 0.0,
                          "until": float(rng.randint(int(lo), int(hi))) if hi > lo else float(lo),
                          "day": 0.0, "wins": 0, "rested": 0.0})
    return True


def _take_exposures(char: Character, tables, rng: RNG) -> None:
    keep = []
    for cond in char.conditions:
        if cond.startswith("exposed:"):
            expose(char, tables, cond.split(":", 1)[1], rng)
        else:
            keep.append(cond)
    char.conditions = keep


# ---------------------------------------------------------------------------- time passing
def tick(char: Character, tables, ctx: HealthContext, minutes: float, rng: RNG) -> list[tuple[str, str]]:
    """Advance wounds, blood, infection, diseases, drink and drugs by some minutes. Returns messages.
    Never kills outright: it lowers hit points, blood or raises strain; sets char.death_cause when the
    body gives out, for the caller to act on."""
    if not char.alive or minutes <= 0:
        return []
    hours = minutes / 60.0
    events: list[tuple[str, str]] = []
    n = body.first(char)
    resting = ctx.activity in ("rest", "sleep")
    _take_exposures(char, tables, rng)
    events += _timed_effects(char, hours, tables)
    events += _environment_exposures(char, tables, ctx, hours, rng)
    events += _bleeding(char, hours, resting, rng)
    events += _infection(char, tables, ctx, hours, resting, rng)
    events += _healing(char, tables, ctx, hours, rng)
    events += _diseases(char, tables, ctx, hours, rng)
    # Blood comes back slowly on a full belly, once the bleeding has stopped.
    still_bleeding = any((w.bleed and not w.bandaged) or w.internal for w in char.wounds)
    if char.blood < 100 and char.hunger < 55 and char.thirst < 60 and not still_bleeding:
        char.blood = min(100.0, char.blood + BLOOD_REGEN_PER_HOUR * (1.5 if resting else 1.0) * hours)
    if char.blood < 25:
        _hurt(char, hours / 1.0)  # a hit point an hour
        events.append((f"<danger>{n} is grey and cold from blood loss.</>", "danger"))
    if char.blood <= 0:
        char.blood = 0.0
        char.death_cause = "bled to death"
    worst_infection = max((w.infection for w in char.wounds), default=0.0)
    if worst_infection >= 100:
        char.death_cause = "died of a festering wound"
    return _dedupe(events)


def _dedupe(events):
    seen = set()
    out = []
    for e in events:
        if e[0] not in seen:
            seen.add(e[0])
            out.append(e)
    return out


def _hurt(char: Character, amount: float) -> None:
    char.hurt_carry += amount
    whole = int(char.hurt_carry)
    if whole:
        char.hurt_carry -= whole
        char.hp = max(0, char.hp - whole)


def _timed_effects(char: Character, hours: float, tables=None) -> list[tuple[str, str]]:
    events = []
    n = body.first(char)
    for key in list(char.effects):
        if key.endswith("_clean"):
            char.effects[key] += hours  # counters since the last dose
            continue
        char.effects[key] -= hours
        if char.effects[key] <= 0:
            del char.effects[key]
            if key == "poppy":
                events.append((f"{n}'s poppy dream fades, and the pain comes back.", "warn"))
            elif key == "hangover":
                events.append((f"{n}'s head clears at last.", "dim"))
            elif key == "disguised":
                events.append((f"{n}'s disguise has worn off.", "dim"))
            elif key.startswith("spell:") and tables is not None and key[6:] in tables.spells:
                events.append((f"The {tables.spells[key[6:]]['name']} on {n} fades.", "dim"))
    # Drink wears off, and real drunkenness leaves a hangover.
    if char.intoxication > 0:
        if char.intoxication >= 45:
            char.effects["drunk"] = 48.0
        char.intoxication = max(0.0, char.intoxication - 10.0 * hours)
    if char.intoxication < 20 and char.effects.get("drunk", 0) > 0:
        del char.effects["drunk"]
        char.effects["hangover"] = 8.0
        events.append((f"{n} is sobering up into a pounding headache.", "dim"))
    # Poppy: craving grows with use and fades with time.
    level = char.addictions.get("poppy", 0.0)
    if level > 0:
        since = char.effects.get("poppy_clean", 0.0)
        if char.effects.get("poppy", 0) <= 0 and since > 18 and level >= 40:
            if char.effects.get("withdrawal", 0) <= 0:
                events.append((f"<warn>{n} craves the poppy: sweating, shaking, aching.</>", "warn"))
            char.effects["withdrawal"] = 2.0
        if char.effects.get("poppy", 0) <= 0:
            char.addictions["poppy"] = max(0.0, level - 2.0 / 24.0 * hours)
            if char.addictions["poppy"] <= 0:
                del char.addictions["poppy"]
                char.effects.pop("poppy_clean", None)
    return events


def _environment_exposures(char: Character, tables, ctx: HealthContext, hours: float, rng: RNG) -> list:
    """Cold and wet, marsh air and filth can bring sickness."""
    if char.body_heat <= -40 and (char.wet >= 40 or char.exhaustion >= 2):
        if rng.chance(0.006 * hours):
            expose(char, tables, "lung_fever", rng)
    if ctx.marsh and ctx.warm_season and rng.chance(0.0025 * hours):
        expose(char, tables, "marsh_fever", rng)
    if char.dirt >= 85 and rng.chance(0.002 * hours):
        expose(char, tables, "camp_fever", rng)
    return []


def _bleeding(char: Character, hours: float, resting: bool, rng: RNG) -> list:
    events = []
    n = body.first(char)
    lost = 0.0
    for w in char.wounds:
        if w.bleed and not w.bandaged:
            lost += BLEED_PER_HOUR[w.bleed] * hours
            chance = CLOT_CHANCE_PER_HOUR[w.bleed] * hours * (1.0 if resting else 0.6)
            if rng.chance(min(0.95, chance)):
                w.bleed -= 1
                if w.bleed == 0:
                    events.append((f"The {PART_LABEL.get(w.part, w.part)} wound on {n} has stopped bleeding.", "good"))
        if w.internal:
            lost += INTERNAL_PER_HOUR * hours
            if rng.chance(min(0.9, (0.06 if resting else 0.02) * hours)):
                w.internal = False
                events.append((f"The bleeding inside {n} seems to have stopped.", "good"))
    if lost:
        before = char.blood
        char.blood = max(0.0, char.blood - lost)
        for limit, word, color in BLOOD_STAGES:
            if char.blood < limit <= before:
                events.append((f"<{color}>{n} has lost a lot of blood and is {word}.</>", color))
                break
    return events


def _infection(char: Character, tables, ctx: HealthContext, hours: float, resting: bool, rng: RNG) -> list:
    events = []
    n = body.first(char)
    sheet = Sheet(char, tables)
    for w in char.wounds:
        where = PART_LABEL.get(w.part, w.part)
        if w.infection <= 0:
            if w.kind not in OPEN_KINDS or (w.kind == "frostbite" and w.severity < 2):
                continue
            age_days = (ctx.now - w.created) / (60 * 24)
            chance = INFECTION_PER_DAY.get(w.severity, 0.1) / 24.0 * hours
            chance *= 0.25 if w.cleaned else 1.0
            chance *= 0.7 if w.bandaged else 1.0
            chance *= 0.8 if w.stitched else 1.0
            chance *= 2.0 if w.kind == "bite" else (1.3 if w.kind == "burn" else 1.0)
            chance *= 1.5 if char.dirt >= 60 else 1.0
            chance *= 1.5 if ctx.marsh else 1.0
            chance *= 1.0 if age_days < 5 else 0.3
            if rng.chance(chance):
                w.infection = 8.0
                w.infected = True
                events.append((f"<warn>The {where} wound on {n} is hot, red and swollen: it is festering.</>", "warn"))
            continue
        # A festering wound: each day the body fights it, or it spreads.
        w.clock += hours
        while w.clock >= 24:
            w.clock -= 24
            bonus = 2 if char.effects.get("herbal", 0) > 0 else 0
            bonus += 1 if w.cleaned else 0
            bonus += 1 if resting else 0
            roll = dice.d20(rng).natural + sheet.save_bonus("con") + bonus
            if roll >= 10 + w.severity:
                w.infection = max(0.0, w.infection - INFECTION_EASES)
                if w.infection <= 0:
                    w.infected = False
                    events.append((f"The {where} wound on {n} is clean at last.", "good"))
            else:
                before = w.infection
                w.infection = min(100.0, w.infection + INFECTION_SPREADS)
                if before < 70 <= w.infection:
                    events.append((f"<danger>Red streaks run from the {where} wound on {n}: the poison is in the blood.</>",
                                   "danger"))
        if w.infection >= 70:
            _hurt(char, hours / 6.0)
            char.strain += 1.0 * hours
    # Wound fever comes and goes with the worst infection.
    worst = max((w.infection for w in char.wounds), default=0.0)
    fever = next((d for d in char.diseases if d["id"] == "wound_fever"), None)
    if worst >= 40 and fever is None and "wound_fever" in tables.diseases:
        char.diseases.append({"id": "wound_fever", "phase": "sick", "stage": 0, "hours": 0.0, "until": 0.0,
                              "day": 0.0, "wins": 0, "rested": 0.0})
        events.append((f"<danger>{n} has wound fever.</>", "danger"))
    elif fever is not None and worst < 20:
        char.diseases.remove(fever)
        events.append((f"{n}'s wound fever breaks.", "good"))
    return events


def _heal_hours(w: Wound) -> float:
    table = FRACTURE_HEAL_HOURS if w.kind == "fracture" else HEAL_HOURS
    return table.get(w.severity, 72.0)


def _healing(char: Character, tables, ctx: HealthContext, hours: float, rng: RNG) -> list:
    events = []
    n = body.first(char)
    rate = {"sleep": 2.0, "rest": 1.5, "walk": 1.0, "fight": 0.5}.get(ctx.activity, 1.0)
    if char.blood < 60:
        rate *= 0.6
    if char.hunger >= 80 or char.thirst >= 85:
        rate *= 0.3
    for w in list(char.wounds):
        if w.infection >= 30:
            continue  # nothing heals while it festers
        r = rate
        if w.stitched:
            r *= 1.4
        if w.bandaged:
            r *= 1.1
        if w.kind == "fracture" and not w.splinted:
            r *= 0.8
        w.healing += hours * r
        if w.healing < _heal_hours(w):
            continue
        w.healing = 0.0
        w.severity -= 1
        w.bleed = min(w.bleed, max(0, w.severity - 1))
        where = PART_LABEL.get(w.part, w.part)
        if w.severity <= 0:
            char.wounds.remove(w)
            injury = _lasting_injury(char, tables, w, rng)
            if injury:
                name = tables.health["injuries"][injury]["name"]
                events.append((f"The {where} wound on {n} has healed, but left {name}.", "warn"))
            else:
                events.append((f"The {where} wound on {n} has healed.", "good"))
        else:
            events.append((f"The {where} wound on {n} is mending: now {SEVERITY[w.severity]}.", "good"))
    return events


def _lasting_injury(char: Character, tables, w: Wound, rng: RNG) -> str | None:
    """A critical wound, or a bone left unset, may heal badly."""
    crooked = w.kind == "fracture" and not w.splinted
    if w.peak < 3 and not crooked:
        return None
    treated = w.stitched or w.splinted or w.cleaned
    if not rng.chance(0.2 if treated and not crooked else 0.55):
        return None
    options = []
    if w.part == "head":
        options = ["lost_eye"] if w.kind == "puncture" and rng.chance(0.3) else ["facial_scar"]
    elif w.part in ("left_arm", "right_arm"):
        options = ["weak_arm"] if w.kind in ("fracture", "blunt") else (["lost_fingers"] if rng.chance(0.3) else ["scar"])
    elif w.part in ("left_leg", "right_leg"):
        options = ["limp"] if w.kind in ("fracture", "blunt") or w.peak >= 3 else ["scar"]
    else:
        options = ["scar"]
    injury = options[0]
    if injury not in tables.health["injuries"]:
        return None
    if injury != "scar" and injury in char.injuries:
        injury = "scar"
    if injury not in char.injuries:
        char.injuries.append(injury)
    return injury


def _diseases(char: Character, tables, ctx: HealthContext, hours: float, rng: RNG) -> list:
    events = []
    n = body.first(char)
    sheet = Sheet(char, tables)
    for d in list(char.diseases):
        did = d["id"]
        if did not in tables.diseases:
            char.diseases.remove(d)
            continue
        dd = tables.diseases[did]
        phase = d["phase"]
        d["hours"] = d.get("hours", 0.0) + hours
        if phase == "incubating":
            if d["hours"] < d.get("until", 0):
                continue
            dc = int(dd.get("save_dc", 10))
            roll = dice.d20(rng).natural + sheet.save_bonus("con")
            if dc and roll >= dc:
                char.diseases.remove(d)
                events.append((f"{n} feels feverish for an hour or two, then it passes.", "dim"))
            else:
                d.update(phase="sick", stage=0, hours=0.0, day=0.0, wins=0, rested=0.0)
                events.append((f"<danger>{n} has fallen sick: {dd['name']}.</> {dd['text']}", "danger"))
            continue
        if phase == "dormant":
            d["day"] = d.get("day", 0.0) + hours
            while d["day"] >= 24:
                d["day"] -= 24
                if rng.chance(float(dd.get("recurring", 0)) / 30.0):
                    d.update(phase="sick", stage=0, hours=0.0, wins=0, rested=0.0)
                    events.append((f"<danger>{dd['name'].capitalize()} has come back to {n}.</>", "danger"))
                    break
            continue
        if phase != "sick" or did == "wound_fever":
            _apply_sickness(char, dd, d, hours)
            continue
        _apply_sickness(char, dd, d, hours)
        if ctx.activity in ("rest", "sleep"):
            d["rested"] = d.get("rested", 0.0) + hours
        d["day"] = d.get("day", 0.0) + hours
        stages = dd["stages"]
        # One recovery roll a day.
        while d["day"] >= 24 and d in char.diseases:
            d["day"] -= 24
            bonus = _treatment_bonus(char, dd, d)
            d["rested"] = 0.0
            roll = dice.d20(rng).natural + sheet.save_bonus("con") + bonus
            if roll >= int(dd.get("recovery_dc", 12)):
                d["wins"] = d.get("wins", 0) + 1
                if d["wins"] >= int(dd.get("recoveries", 2)):
                    events += _recover(char, tables, dd, d, rng)
                    break
                if d["stage"] > 0:
                    d["stage"] -= 1
                    d["hours"] = 0.0
                    events.append((f"{n} is over the worst of {dd['name']}.", "good"))
                else:
                    events.append((f"{n} feels a little better.", "good"))
        if d not in char.diseases:
            continue
        stage = stages[min(d["stage"], len(stages) - 1)]
        if d["hours"] >= float(stage["hours"]):
            d["hours"] = 0.0
            if d["stage"] < len(stages) - 1:
                d["stage"] += 1
                events.append((f"<danger>{n} is getting worse: {stages[d['stage']]['name']}.</>", "danger"))
            elif dd.get("fatal"):
                roll = dice.d20(rng).natural + sheet.save_bonus("con")
                if roll < int(dd.get("death_dc", 12)):
                    char.death_cause = f"died of {dd['name']}"
                    char.hp = 0
    return events


def _apply_sickness(char: Character, dd: dict, d: dict, hours: float) -> None:
    stages = dd["stages"]
    e = stages[min(d.get("stage", 0), len(stages) - 1)]["effects"]
    char.thirst = min(100.0, char.thirst + body.THIRST_PER_HOUR * (float(e.get("thirst", 1.0)) - 1.0) * hours)
    char.hunger = min(100.0, char.hunger + body.HUNGER_PER_HOUR * (float(e.get("hunger", 1.0)) - 1.0) * hours)
    char.fatigue = min(100.0, char.fatigue + body.FATIGUE_PER_HOUR * (float(e.get("fatigue", 1.0)) - 1.0) * hours)
    char.strain += float(e.get("strain", 0.0)) * hours
    if e.get("hp_per_day"):
        _hurt(char, float(e["hp_per_day"]) * hours / 24.0)


def _treatment_bonus(char: Character, dd: dict, d: dict) -> int:
    t = dd.get("treatments", {})
    bonus = 0
    if d.get("rested", 0) >= 14:
        bonus += int(t.get("rest", 0))
    if char.effects.get("herbal", 0) > 0:
        bonus += int(t.get("herbs", 0))
    if char.thirst < 40:
        bonus += int(t.get("clean_water", 0))
    if char.body_heat > -20 and char.wet < 35:
        bonus += int(t.get("warmth", 0))
    if char.dirt < 30:
        bonus += int(t.get("clean", 0))
    return bonus


def _recover(char: Character, tables, dd: dict, d: dict, rng: RNG) -> list:
    n = body.first(char)
    events = [(f"<good>{n} has recovered from {dd['name']}.</>", "good")]
    if dd.get("recurring"):
        d.update(phase="dormant", stage=0, hours=0.0, day=0.0, wins=0)
    elif dd.get("immunity"):
        d.update(phase="immune", stage=0, hours=0.0)
    else:
        char.diseases.remove(d)
    lasting = dd.get("lasting")
    if lasting and rng.chance(float(lasting.get("chance", 0))):
        inj = lasting["injury"]
        if inj in tables.health["injuries"] and inj not in char.injuries:
            char.injuries.append(inj)
            events.append((f"It has left {n} with {tables.health['injuries'][inj]['name']}.", "warn"))
    return events


# ---------------------------------------------------------------------------- treatment
TREATMENTS = {
    "bandage": ("Bandage", 5, "Stops a wound bleeding. Needs bandages or a healer's kit. Medicine DC 10, harder "
                              "the worse it bleeds."),
    "clean": ("Clean", 10, "Wash the wound with strong drink or clean water. Much less likely to fester; helps one "
                           "that already has. Medicine DC 10."),
    "stitch": ("Stitch", 20, "Sew a gaping cut closed: heals faster, bleeds less, scars less. Needle and thread or a "
                             "healer's kit. Medicine DC 12."),
    "splint": ("Splint", 20, "Set and bind a broken bone so it heals straight. A splint (or a stout stick in "
                             "wooded country). Medicine DC 11."),
    "cauterize": ("Cauterize", 5, "Burn the wound shut: the bleeding stops at once, but it leaves a burn. Needs a "
                                  "fire or a torch."),
    "poultice": ("Poultice", 15, "Herbs against festering. Healing herbs or a herbalism kit. Medicine (or Nature) "
                                 "DC 12."),
    "amputate": ("Amputate", 60, "Take off a limb that cannot be saved, to save a life. Needs a blade; fire or a torch "
                                 "seals the stump. Medicine DC 13, much harder on yourself. It cannot be undone."),
}


def _blade(char: Character, tables):
    """Something sharp enough to take a limb: a cutting weapon or a knife."""
    for it in char.inventory:
        d = tables.items.get(it.def_id)
        if d.get("category") == "weapon" and d.get("damage_type") == "slashing":
            return it
    return None


def _find(char: Character, tables, def_ids: tuple[str, ...]):
    for did in def_ids:
        for it in char.inventory:
            if it.def_id == did:
                return it
    return None


def _kit(char: Character):
    return next((it for it in char.inventory if it.def_id == "healers_kit" and it.condition > 0), None)


def _use_kit(char: Character, kit) -> None:
    """A healer's kit has ten uses; its condition counts them down."""
    kit.condition -= 10
    if kit.condition <= 0:
        remove_item(char, kit.uid)


def treatment_options(healer: Character, patient: Character, wound: Wound, tables, *, fire: bool,
                      wooded: bool) -> list[tuple[str, str, bool, str]]:
    """(action, label, possible, why not) for a wound."""
    out = []
    has_kit = _kit(healer) is not None
    # Bandage
    if not wound.bleed:
        out.append(("bandage", "Bandage", False, "it is not bleeding"))
    elif wound.bandaged:
        out.append(("bandage", "Bandage", False, "already bandaged"))
    else:
        ok = has_kit or _find(healer, tables, ("bandages",)) is not None
        out.append(("bandage", "Bandage", ok, "no bandages or healer's kit"))
    # Clean
    if wound.kind not in OPEN_KINDS:
        out.append(("clean", "Clean", False, "the skin is not broken"))
    elif wound.cleaned and wound.infection <= 0:
        out.append(("clean", "Clean", False, "already clean"))
    else:
        ok = _cleaning_supply(healer, tables) is not None
        out.append(("clean", "Clean", ok, "no strong drink or clean water"))
    # Stitch
    if wound.kind not in ("cut", "bite", "puncture") or wound.severity < 2:
        out.append(("stitch", "Stitch", False, "nothing to sew"))
    elif wound.stitched:
        out.append(("stitch", "Stitch", False, "already stitched"))
    else:
        ok = has_kit or _find(healer, tables, ("needle_thread",)) is not None
        out.append(("stitch", "Stitch", ok, "no needle and thread or healer's kit"))
    # Splint
    if wound.kind != "fracture":
        out.append(("splint", "Splint", False, "no broken bone"))
    elif wound.splinted:
        out.append(("splint", "Splint", False, "already splinted"))
    else:
        ok = _find(healer, tables, ("splint", "quarterstaff")) is not None or wooded
        out.append(("splint", "Splint", ok, "no splint or straight wood"))
    # Cauterize
    if not wound.bleed:
        out.append(("cauterize", "Cauterize", False, "it is not bleeding"))
    else:
        ok = fire or _find(healer, tables, ("torch",)) is not None
        out.append(("cauterize", "Cauterize", ok, "no fire or torch"))
    # Poultice
    if wound.infection <= 0:
        out.append(("poultice", "Poultice", False, "it is not festering"))
    else:
        ok = _find(healer, tables, ("healing_herbs",)) is not None or \
            _find(healer, tables, ("herbalism_kit",)) is not None
        out.append(("poultice", "Poultice", ok, "no healing herbs or herbalism kit"))
    # Amputate: only for a limb that cannot be saved
    if beyond_saving(wound):
        out.append(("amputate", "Amputate the limb", _blade(healer, tables) is not None,
                    "no blade to do it with (a knife, an axe, a sword)"))
    return out


def _cleaning_supply(healer: Character, tables):
    """Strong drink first, then boiled or clean water from a waterskin."""
    spirit = _find(healer, tables, ("spirits", "wine", "ale"))
    if spirit is not None:
        return spirit
    for it in healer.inventory:
        if container_capacity(tables.items, it) and it.fill >= 1 and WATER_RISK.get(it.fill_kind, 2) == 0:
            return it
    return None


def _medicine(healer: Character, tables, rng: RNG, dc: int, bonus: int = 0, nature: bool = False) -> tuple[bool, str]:
    s = Sheet(healer, tables)
    skill = "medicine"
    if nature and s.skill_bonus("nature") > s.skill_bonus("medicine"):
        skill = "nature"
    b = s.skill_bonus(skill) + bonus
    roll = dice.d20(rng).natural
    name = tables.rules["skills"][skill]["name"]
    sign = "+" if b >= 0 else "-"
    return roll + b >= dc, f"<dice>{name}: {roll} {sign} {abs(b)} = {roll + b} vs DC {dc}</>"


def treat(healer: Character, patient: Character, wound: Wound, action: str, tables, rng: RNG, *,
          fire: bool = False, wooded: bool = False, now: int = 0) -> tuple[bool, list[str], int]:
    """Try a treatment. Returns (success, messages, minutes it took)."""
    opts = {a: (ok, why) for a, _, ok, why in treatment_options(healer, patient, wound, tables, fire=fire, wooded=wooded)}
    ok, why = opts.get(action, (False, "unknown treatment"))
    name, minutes, _ = TREATMENTS[action]
    if not ok:
        return False, [f"{name}: {why}."], 0
    who = body.first(patient)
    where = PART_LABEL.get(wound.part, wound.part)
    msgs: list[str] = []
    success = False
    if action == "bandage":
        kit = _kit(healer)
        dc = 8 + 2 * wound.bleed
        success, dice_text = _medicine(healer, tables, rng, dc, 3 if kit else 0)
        msgs.append(dice_text)
        if kit is not None:
            _use_kit(healer, kit)
        else:
            remove_item(healer, _find(healer, tables, ("bandages",)).uid, 1)
        if success:
            wound.bandaged = True
            msgs.append(f"The {where} wound on {who} is bound tight. The bleeding stops.")
        else:
            msgs.append("The bandage soaks through; the knot slips. It will need doing again.")
    elif action == "clean":
        supply = _cleaning_supply(healer, tables)
        strong = tables.items.get(supply.def_id).get("drink") is not None
        success, dice_text = _medicine(healer, tables, rng, 10, 2 if strong else 0)
        msgs.append(dice_text)
        if strong:
            remove_item(healer, supply.uid, 1)
        else:
            supply.fill = round(supply.fill - 1, 2)
            if supply.fill <= 0:
                supply.fill, supply.fill_kind = 0.0, ""
        if success:
            wound.cleaned = True
            wound.infection = max(0.0, wound.infection - 25.0)
            if wound.infection <= 0:
                wound.infected = False
            msgs.append(f"{who} grits their teeth while the {where} wound is washed out.")
        else:
            msgs.append("The wound is washed, but not well; dirt stays in it.")
    elif action == "stitch":
        kit = _kit(healer)
        dc = 12 + (2 if wound.severity >= 3 else 0)
        success, dice_text = _medicine(healer, tables, rng, dc, 2 if kit else 0)
        msgs.append(dice_text)
        if kit is not None:
            _use_kit(healer, kit)
        if success:
            wound.stitched = True
            wound.bleed = max(0, wound.bleed - 2)
            msgs.append(f"Neat stitches close the {where} wound on {who}.")
        else:
            wound.infection = max(wound.infection, 0.0) + (5.0 if wound.infection > 0 else 0.0)
            msgs.append("Clumsy stitches that will have to come out. It hurts, and bleeds more.")
    elif action == "splint":
        splint = _find(healer, tables, ("splint",))
        success, dice_text = _medicine(healer, tables, rng, 11)
        msgs.append(dice_text)
        if success:
            wound.splinted = True
            if splint is not None:
                remove_item(healer, splint.uid, 1)
            msgs.append(f"The bone in {who}'s {where} is set and bound. {who} nearly passes out from the pain.")
        else:
            msgs.append("The bone will not go back. Try again, or find someone who knows how.")
    elif action == "cauterize":
        success = True
        if not fire:
            torch = _find(healer, tables, ("torch",))
            remove_item(healer, torch.uid, 1)
        wound.bleed = 0
        wound.internal = False
        patient.wounds.append(Wound(wound.part, "burn", 2 if wound.severity >= 3 else 1, 0, now, note="cautery"))
        msgs.append(f"Hot iron on the {where}. The smell is terrible. The bleeding stops.")
        s = Sheet(patient, tables)
        if dice.d20(rng).natural + s.save_bonus("con") < 12:
            msgs.append(f"{who} faints.")
            minutes += 30
    elif action == "poultice":
        herbs = _find(healer, tables, ("healing_herbs",))
        kit = _find(healer, tables, ("herbalism_kit",))
        bonus = Sheet(healer, tables).proficiency if kit is not None and "herbalism_kit" in healer.tools else 0
        success, dice_text = _medicine(healer, tables, rng, 12, bonus, nature=True)
        msgs.append(dice_text)
        if herbs is not None:
            remove_item(healer, herbs.uid, 1)
        if success:
            wound.infection = max(0.0, wound.infection - 35.0)
            if wound.infection <= 0:
                wound.infected = False
            patient.effects["herbal"] = 24.0
            msgs.append(f"A green, bitter-smelling poultice goes on the {where} wound.")
        else:
            msgs.append("The herbs are the wrong ones, or wrongly prepared.")
    elif action == "amputate":
        msgs += _amputate(healer, patient, wound, tables, rng, fire=fire, now=now)
        success = not any("botched" in m for m in msgs)
        if any("faints" in m for m in msgs):
            minutes += 60
    return success, msgs, minutes


def _amputate(healer: Character, patient: Character, wound: Wound, tables, rng: RNG, *, fire: bool,
              now: int) -> list[str]:
    """The limb comes off either way; skill decides whether the stump is clean or a second danger."""
    from realmwalker.rules.inventory import unequip

    who = body.first(patient)
    where = PART_LABEL.get(wound.part, wound.part)
    dc = 13 + (5 if healer is patient else 0)
    success, dice_text = _medicine(healer, tables, rng, dc, 2 if _kit(healer) else 0)
    msgs = [dice_text]
    torch = None if fire else _find(healer, tables, ("torch",))
    sealed = fire or torch is not None
    if torch is not None:
        remove_item(healer, torch.uid, 1)
    patient.wounds = [w for w in patient.wounds if w.part != wound.part]
    patient.wounds.append(Wound(wound.part, "cut", 2 if success else 3, 0 if sealed else (1 if success else 3), now,
                                note="the stump", cleaned=success, infection=0.0 if success else 15.0))
    if sealed:
        patient.wounds.append(Wound(wound.part, "burn", 1, 0, now, note="cautery"))
    patient.blood = max(5.0, patient.blood - (10.0 if success else 25.0))
    injury = f"lost_{wound.part}"
    if injury in tables.health["injuries"] and injury not in patient.injuries:
        patient.injuries.append(injury)
    if wound.part in ("left_arm", "right_arm"):
        unequip(patient, "off_hand")  # one hand left, and it holds the main weapon
        main = patient.equipped_item("main_hand")
        if main is not None and "two_handed" in tables.items.get(main.def_id).get("properties", []):
            unequip(patient, "main_hand")
    if success:
        msgs.append(f"It is done quickly, the way a surgeon does it. {who}'s {where} is gone, and the stump is "
                    f"closed{' and seared' if sealed else ''} clean.")
    else:
        msgs.append(f"It is botched: a long, sawing business. {who}'s {where} is gone, and the stump is ragged and "
                    f"{'seared badly' if sealed else 'pouring blood'}.")
    if dice.d20(rng).natural + Sheet(patient, tables).save_bonus("con") < 15:
        msgs.append(f"{who} faints.")
    return msgs


def take_poppy(char: Character) -> str:
    char.effects["poppy"] = 8.0
    char.effects["poppy_clean"] = 0.0
    char.effects.pop("withdrawal", None)
    char.addictions["poppy"] = min(100.0, char.addictions.get("poppy", 0.0) + 12.0)
    warn = " The craving for it is getting stronger." if char.addictions["poppy"] >= 40 else ""
    return f"{body.first(char)} drinks the poppy milk. The pain goes soft and far away.{warn}"


def magic_heal(char: Character, wound: Wound | None, amount: int) -> list[str]:
    """Cure Wounds and its like: hit points, and the worst of one wound mended by a step."""
    msgs = []
    char.hp = min(body.hp_cap(char), char.hp + amount)
    msgs.append(f"{body.first(char)} recovers {amount} hit points.")
    if wound is not None and wound in char.wounds:
        wound.severity -= 1
        wound.bleed = max(0, wound.bleed - 1)
        wound.internal = False
        wound.infection = max(0.0, wound.infection - 30.0)
        if wound.infection <= 0:
            wound.infected = False
        where = PART_LABEL.get(wound.part, wound.part)
        if wound.severity <= 0:
            char.wounds.remove(wound)
            msgs.append(f"The {where} wound closes under the light.")
        else:
            msgs.append(f"The {where} wound knits a little: now {SEVERITY[wound.severity]}.")
    return msgs


def magic_restore(char: Character, tables) -> list[str]:
    """Lesser Restoration: ends one sickness (or every festering wound)."""
    sick = [d for d in char.diseases if d.get("phase") in ("sick", "incubating") and d["id"] != "wound_fever"
            and (d["phase"] == "incubating" or not tables.diseases[d["id"]].get("cure_before_symptoms"))]
    if sick:
        d = sick[0]
        char.diseases.remove(d)
        return [f"The sickness leaves {body.first(char)}: {tables.diseases[d['id']]['name']} is gone."]
    festering = [w for w in char.wounds if w.infection > 0]
    if festering:
        for w in festering:
            w.infection = 0.0
            w.infected = False
        return [f"The heat goes out of {body.first(char)}'s wounds."]
    return ["There is nothing for the spell to mend."]


def describe_wound(w: Wound) -> str:
    bits = []
    if w.bleed and not w.bandaged:
        bits.append("<danger>" + {1: "bleeding", 2: "bleeding badly", 3: "pouring blood"}[w.bleed] + "</>")
    if w.internal:
        bits.append("<danger>bleeding inside</>")
    if w.bandaged:
        bits.append("<good>bandaged</>")
    if w.stitched:
        bits.append("<good>stitched</>")
    if w.splinted:
        bits.append("<good>splinted</>")
    elif w.kind == "fracture":
        bits.append("<warn>not set</>")
    if w.cleaned:
        bits.append("<dim>cleaned</>")
    if w.infection >= 70:
        bits.append("<danger>blood poisoning</>")
    elif w.infection > 0:
        bits.append("<danger>festering</>")
    need = _heal_hours(w)
    if w.infection < 30:
        bits.append(f"<dim>{int(100 * w.healing / need)}% to {SEVERITY.get(w.severity - 1, 'healed')}</>")
    return ", ".join(bits)


def carry_battle_state(char: Character, conditions: dict) -> None:
    """After a fight: poison lingers for a while."""
    if "poisoned" in conditions:
        char.effects["poisoned"] = max(char.effects.get("poisoned", 0.0), 1.0)

