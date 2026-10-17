"""The raised dead outside a fight (Expansion 3 F.4): Animate Dead and Create Undead on the road (through
game/spellwork's door: subjects, problem, cast), holding them again, the warning before the hold ends and what they
do when it does, where they go (never into a settlement's close-up map), their pictures behind the party, and the
mummy's rot carried after a fight. What they do in a fight is rules/servants.py and the battle's command."""
from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject
from realmwalker.rules import servants as rules

DAY = rules.DAY
FRESH_MINUTES = 60 * 6  # (a corpse of the last fight is fresh enough to raise for six hours, as for Speak with Dead)
CRYPT_BONES = 6  # (piles of old bones on a crypt's level underground)
# Create Undead (PHB 2024): what each slot raises, and how many.
UNDEAD_BY_SLOT = {6: {"ghoul": 3}, 7: {"ghoul": 4}, 8: {"ghoul": 5, "ghast": 2, "wight": 2},
                  9: {"ghoul": 6, "ghast": 3, "wight": 3, "mummy": 2}}
PLURAL = {"zombie": "zombies", "skeleton": "skeletons", "ghoul": "ghouls", "ghast": "ghasts", "wight": "wights",
          "mummy": "mummies"}


def _first(c) -> str:
    return esc(c.name.split()[0])


def _how(game, sid: str) -> str:
    spell = game.tables.spells[sid]
    return next((o.get("how", "") for o in spell.get("effects", ()) if o.get("op") == "road"), "")


# ---------------------------------------------------------------------------- the bodies here
def _fresh(game) -> dict | None:
    rec = getattr(game, "fresh_dead", None)
    if not rec:
        return None
    p = game.player
    here = game.local.key if game.local is not None else None
    if (rec["x"], rec["y"]) != (p.x, p.y) or rec["map"] != here or game.world.time - rec["time"] > FRESH_MINUTES:
        return None
    return rec


def corpses(game) -> list[dict]:
    """The Medium or Small humanoids of the last fight lying here, not yet raised."""
    rec = _fresh(game)
    out = []
    for d in (rec or {}).get("dead", []):
        if d["def_id"] not in game.tables.creatures:
            continue
        c = game.tables.creatures[d["def_id"]]
        if c.get("kind") == "humanoid" and c.get("size", "medium") in ("small", "medium") and not d.get("raised"):
            out.append(d)
    return out


def _crypt(game):
    lm = game.local
    if lm is None or lm.meta.get("style") != "crypt" or not lm.under_rock(game.player.lx, game.player.ly):
        return None
    return lm


def bones(game) -> int:
    """Piles of bones here: skeletons destroyed in the last fight, and a crypt's old dead."""
    rec = _fresh(game)
    n = sum(1 for d in (rec or {}).get("dead", []) if d["def_id"] == "skeleton" and not d.get("raised"))
    lm = _crypt(game)
    if lm is not None:
        n += int(lm.meta.get("bones", CRYPT_BONES))
    return n


def _use_corpses(game, n: int) -> None:
    for d in corpses(game)[:n]:
        d["raised"] = True
        d["asked"] = True  # (a body that walks has nothing left to tell Speak with Dead)


def _use_bones(game, n: int) -> None:
    rec = _fresh(game)
    for d in (rec or {}).get("dead", []):
        if n <= 0:
            return
        if d["def_id"] == "skeleton" and not d.get("raised"):
            d["raised"] = True
            n -= 1
    lm = _crypt(game)
    if lm is not None and n > 0:
        lm.meta["bones"] = max(0, int(lm.meta.get("bones", CRYPT_BONES)) - n)


# ---------------------------------------------------------------------------- the Spells page
def _bodies(n: int, what: str = "body") -> str:
    return f"{n} {what if n == 1 else ('bodies' if what == 'body' else what + 's')}"


def subjects(game, caster, sid: str) -> list[Subject]:
    how = _how(game, sid)
    out = []
    held = [r for r in rules.of_spell(caster, sid) if r.get("until") is not None]
    if how == "dead":
        n = len(corpses(game))
        if n:
            out.append(Subject(f"raise the dead here as zombies ({_bodies(n)})", "raise", "zombie",
                               data={"cid": "zombie", "group": "raise"}))
        m = bones(game)
        if m:
            out.append(Subject(f"raise the bones as skeletons ({_bodies(m, 'pile')})", "raise", "skeleton",
                               data={"cid": "skeleton", "group": "raise"}))
    elif how == "ghouls":
        n = len(corpses(game))
        if n:
            for cid, slot in (("ghoul", 6), ("ghast", 8), ("wight", 8), ("mummy", 9)):
                more = "" if slot == 6 else f"; a slot of {slot} or more"
                out.append(Subject(f"raise {PLURAL[cid]} from the dead here ({_bodies(n)}{more})", "raise", cid,
                                   data={"cid": cid, "slot": slot, "group": "raise"}))
    if held:
        out.append(Subject(f"hold your dead for another day ({len(held)} of them)", "raise", "hold",
                           data={"group": "hold"}))
    return out


def problem(game, caster, sid: str, target) -> str | None:
    how = _how(game, sid)
    if how == "ghouls" and game.light >= 0.5:
        return "only at night"
    if not isinstance(target, Subject):
        if not subjects(game, caster, sid):
            return "no corpse or bones lie here, and none of your dead wait to be held"
        return "choose (←→)"
    if target.ref == "hold":
        if not [r for r in rules.of_spell(caster, sid) if r.get("until") is not None]:
            return "none of your dead wait to be held"
        return None
    if rules.room(caster) <= 0:
        return f"no more will answer you: {rules.MAX} of the dead serve you already"
    if target.ref == "skeleton" and not bones(game):
        return "no bones lie here"
    if target.ref != "skeleton" and not corpses(game):
        return "no corpse of the last fight lies here"
    if how == "ghouls" and not any(it.def_id == "black_onyx" for it in caster.inventory):
        return "needs a black onyx stone (150 GP) for each corpse"
    return None


def count(game, caster, sid: str, cid: str, level: int) -> int:
    """How many the casting raises at this slot: the bodies here, the stones carried, the room left."""
    how = _how(game, sid)
    if how == "dead":
        allowed = 1 + 2 * max(0, int(level) - 3)
        there = bones(game) if cid == "skeleton" else len(corpses(game))
    else:
        allowed = UNDEAD_BY_SLOT.get(min(9, max(6, int(level))), {}).get(cid, 0)
        there = min(len(corpses(game)), sum(it.qty for it in caster.inventory if it.def_id == "black_onyx"))
    return max(0, min(allowed, there, rules.room(caster)))


def hold_count(sid: str, level: int) -> int:
    if sid == "animate_dead":
        return 4 + 2 * max(0, int(level) - 3)
    return max(UNDEAD_BY_SLOT.get(min(9, max(6, int(level))), {}).values(), default=3)


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    from realmwalker.game.companions import react

    if not isinstance(target, Subject):
        return []
    now = float(game.world.time)
    first = _first(caster)
    if target.ref == "hold":
        held = rules.hold(caster, sid, hold_count(sid, level), now + DAY)
        if not held:
            return ["None of your dead answer."]
        return [f"<magic>{first} speaks the words again over {'the dead' if len(held) > 1 else 'the ' + held[0]['name']}"
                f"</>: {'they are' if len(held) > 1 else 'it is'} {first}'s for another day ({len(held)} held)."]
    cid = target.data.get("cid", "zombie")
    note = []
    if int(target.data.get("slot", 0)) > int(level):
        note.append(f"<dim>At this slot only ghouls answer: {PLURAL[cid]} need a slot of {target.data['slot']}.</>")
        cid = "ghoul"
    n = count(game, caster, sid, cid, level)
    if n <= 0:
        return note + ["Nothing stirs."]
    if cid == "skeleton":
        _use_bones(game, n)
    else:
        _use_corpses(game, n)
    for _ in range(n):
        rules.add(caster, game.tables, cid, sid, until=now + DAY, now=now, word=True)
    name = game.tables.creatures[cid]["name"]
    what = f"a {name}" if n == 1 else f"{n} {PLURAL.get(cid, name + 's')}"
    words = {"skeleton": "Bones knit together with a dry clatter, and stand",
             "zombie": "The dead jerk, groan and get up off the ground",
             "ghoul": "The dead sit up, and their teeth grow long",
             "ghast": "The dead rise reeking, grey skin drawn tight over their grins",
             "wight": "The dead rise with a cold light in their eyes, and they remember how to hold a blade",
             "mummy": "The dead rise stiff and slow, and their skin turns to leather as you watch"}[cid]
    out = note + [f"<magic>{first} speaks over the dead.</> {words}: {what}, {first}'s for a day. "
                  f"<dim>In a fight they act only when commanded (a Bonus Action); cast it again before the day is "
                  f"out, or they will turn on you.</>"]
    if game.party[1:]:
        react(game, "desecration")
    return out


# ---------------------------------------------------------------------------- as time passes
def here(game) -> bool:
    """The dead follow the party in the wild and underground, never onto a settlement's close-up map."""
    lm = game.local
    return lm is None or lm.kind != "settlement"


def masters(game) -> list:
    return [c for c in game.party if c.alive and rules.records(c)]


def tick(game) -> None:
    """From pass_time: warn before a hold ends; free those it has ended for (they turn on the party out in the land,
    or wander off); the mummy's rot each day."""
    now = float(game.world.time)
    for c in game.party:
        if not c.spells.get("servants"):
            _rot_day(game, c, now)
            continue
        warn = rules.soon(c, now)
        if warn:
            for r in warn:
                r["warned"] = True
            game.say(f"<warn>The dead grow restless: {_first(c)}'s hold on "
                     f"{'them' if len(warn) > 1 else 'the ' + warn[0]['name']} ends within two hours.</> "
                     f"<dim>Cast {game.tables.spells[warn[0]['spell']]['name']} again to hold them.</>", "warn")
        freed = rules.due(c, now) if c.alive else list(rules.records(c))
        if freed:
            for r in freed:
                rules.drop(c, r)
            _go_free(game, c, freed)
        _rot_day(game, c, now)


def _go_free(game, master, freed: list[dict]) -> None:
    from realmwalker.game.encounters import PendingEncounter, threat_words

    first = _first(master)
    fight = here(game) and not game.busy and game.over is None and any(c.alive for c in game.party)
    if not fight:
        game.say(f"<warn>{first}'s hold on the dead is gone.</> "
                 f"{'They shamble' if len(freed) > 1 else 'It shambles'} off into the dark and {'are' if len(freed) > 1 else 'is'} "
                 "seen no more.", "warn")
        return
    rng = game.world.rng.child(f"raised_free/{game.world.time}")
    creatures = [rules.creature_of(r, 93000 + i) for i, r in enumerate(freed)]
    g = game.tables.creatures.encounters["raised_dead"]
    game.say(f"<danger>{first}'s hold on the dead is gone, and they remember what they hate.</>", "danger")
    game.encounter = PendingEncounter("raised_dead", creatures, rng.choice(g["intro"]), True,
                                      threat_words(game.tables, creatures, game.party), attitude="hostile")
    game.dirty = True


def died(game, char) -> None:
    """A master dies: the hold on their dead ends at once, and they go free (with the party still about them, they
    turn on it)."""
    freed = list(rules.records(char))
    if freed:
        char.spells["servants"] = []
        _go_free(game, char, freed)


def _rot_day(game, c, now: float) -> None:
    """A mummy's curse carried out of the fight: no healing (hit points kept no higher than they were), and each 24
    hours the maximum 3d6 lower; at nothing, the cursed one dies and turns to dust."""
    since = c.effects.get(rules.ROT)
    if not since or not c.alive:
        return
    from realmwalker.core import dice

    cap = c.effects.get(rules.ROT_HP)
    c.effects[rules.ROT_HP] = float(min(c.hp, cap if cap is not None else c.hp))
    if c.hp > c.effects[rules.ROT_HP]:
        c.hp = int(c.effects[rules.ROT_HP])
    days = int((now - float(since)) // DAY)
    done = int(c.effects.get(rules.ROT_DAYS, 0))
    rng = game.world.rng.child(f"mummy_rot/{c.name}/{days}")
    while done < days and c.alive:
        done += 1
        loss = dice.roll("3d6", rng).total
        c.effects[rules.ROT_LOST] = float(c.effects.get(rules.ROT_LOST, 0)) + loss
        c.max_hp = max(0, c.max_hp - loss)
        c.hp = min(c.hp, c.max_hp)
        c.effects[rules.ROT_HP] = float(min(c.effects[rules.ROT_HP], c.hp))
        game.say(f"<danger>The rot spreads in {_first(c)}'s flesh</>: the hit point maximum falls by {loss}. "
                 f"<dim>Remove Curse lifts it.</>", "danger")
        if c.max_hp <= 0:
            c.alive = False
            c.hp = 0
            c.effects[rules.DUST] = 1.0
            c.death_cause = "rotted away to dust under a mummy's curse"
            game.say(f"<danger>{_first(c)} crumbles to grey dust.</>", "danger")
    c.effects[rules.ROT_DAYS] = float(done)


def lift_rot(c) -> bool:
    """Remove Curse: the mummy's rot is gone, and the maximum it took comes back."""
    if not c.effects.get(rules.ROT):
        return False
    lost = int(c.effects.pop(rules.ROT_LOST, 0))
    c.max_hp += lost
    for k in (rules.ROT, rules.ROT_HP, rules.ROT_DAYS):
        c.effects.pop(k, None)
    return True


# ---------------------------------------------------------------------------- after a fight
def after_battle(game, battle) -> list[str]:
    from realmwalker.game.companions import react

    out = rules.after(battle, float(game.world.time))
    for line in out:
        game.say(line, "magic")
    if out and game.party[1:]:
        react(game, "desecration")
    return out


def following(game) -> list[dict]:
    """The dead that walk behind the party here (for the close-up map's pictures)."""
    if not here(game):
        return []
    return [r for c in game.party if c.alive for r in rules.records(c) if int(r.get("hp", 0)) > 0]
