"""The raised dead outside a fight (Expansion 3 F.4): Animate Dead and Create Undead on the road (through
game/spellwork's door: subjects, problem, cast), holding them again, the warning before the hold ends and what they
do when it does, where they go (never into a settlement's close-up map), their pictures behind the party, and the
mummy's rot carried after a fight. The bound (F.5): Planar Ally (a spirit of the caster's god for a price) and
Planar Binding (a captive celestial, elemental, fey or fiend, or a Planar Ally's spirit held in a Magic Circle turned
inward); they serve on their own and go away, not against the party, when their time ends. What they do in a fight
is rules/servants.py and the battle's command."""
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
# Planar Ally (PHB 2024): the terms (words, minutes, gold pieces); 100 GP a minute is never cheaper than an hour.
TERMS = (("an hour", 60, 1000), ("a day", DAY, 10000), ("three days", 3 * DAY, 30000), ("ten days", 10 * DAY, 100000))
# Planar Binding: days bound by the slot; the kinds it reaches; the casting (the creature stays in range for all of it).
BINDING_DAYS = {5: 1, 6: 10, 7: 30, 8: 180, 9: 366}
BINDABLE = ("celestial", "elemental", "fey", "fiend")
BINDING_MINUTES = 60
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
    if how == "ally":
        return ally_subjects(game, caster)
    if how == "binding":
        return binding_subjects(game, caster)
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
    if how == "ally":
        return ally_problem(game, caster, target)
    if how == "binding":
        return binding_problem(game, caster, target)
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
    how = _how(game, sid)
    if how == "ally":
        return cast_ally(game, caster, target, level)
    if how == "binding":
        return cast_binding(game, caster, target, level)
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


# ---------------------------------------------------------------------------- the bound (F.5)
def faith_of(game, caster) -> tuple[str, dict]:
    """The caster's god: the faith of their people (data/factions.json faiths)."""
    from realmwalker.world import factions as fx

    fid = fx.faith_for_culture(game.tables, caster.culture)
    faiths = game.tables.factions["faiths"]
    return fid, faiths.get(fid) or faiths["radiant"]


def ally_kind(game, caster) -> tuple[str, str]:
    """The spirit the caster's god sends: (creature, form)."""
    ally = faith_of(game, caster)[1].get("ally") or {"creature": "celestial_spirit", "form": "defender"}
    return ally["creature"], ally["form"]


def church_member(game, caster) -> bool:
    """The party's leader belongs to the church of the caster's god (Planar Ally's price is halved)."""
    from realmwalker.game import reputation
    from realmwalker.world import factions as fx

    church = fx.church_of(game.world, faith_of(game, caster)[0])
    return church is not None and reputation.rank(game, church.id) is not None


def ally_price(game, caster, gp: int) -> int:
    """A term's price in copper."""
    cp = int(gp) * 100
    return cp // 2 if church_member(game, caster) else cp


def _spirit_name(game, caster) -> str:
    cid, form = ally_kind(game, caster)
    return f"{game.tables.creatures[cid]['summon']['forms'][form]['name']} of {faith_of(game, caster)[1]['short']}"


def ally_subjects(game, caster) -> list[Subject]:
    from realmwalker.rules.items import money_text

    half = " (half: you are of its church)" if church_member(game, caster) else ""
    what = esc(_spirit_name(game, caster))
    return [Subject(f"a {what}, for {words}: {money_text(ally_price(game, caster, gp))}{half}", "term", words,
                    data={"minutes": minutes, "gp": gp}) for words, minutes, gp in TERMS]


def ally_problem(game, caster, target) -> str | None:
    from realmwalker.game import law
    from realmwalker.rules.items import money_text

    if rules.room(caster) <= 0:
        return f"no more will answer you: {rules.MAX} serve you already"
    if not isinstance(target, Subject):
        return "choose how long it will serve (←→)"
    price = ally_price(game, caster, int(target.data.get("gp", 0)))
    if law.party_money(game) < price:
        return f"the price is {money_text(price)}, and the party has {money_text(law.party_money(game))}"
    return None


def cast_ally(game, caster, target, level: int) -> list[str]:
    from realmwalker.game import law
    from realmwalker.rules.items import money_text

    now = float(game.world.time)
    cid, form = ally_kind(game, caster)
    _, faith = faith_of(game, caster)
    fm = game.tables.creatures[cid]["summon"]["forms"][form]
    price = ally_price(game, caster, int(target.data.get("gp", 0)))
    if law.party_money(game) < price:
        return ["The spirit names its price, and you cannot pay it: it is gone as it came."]
    level = max(int(game.tables.creatures[cid]["summon"]["level"]), int(level))
    # (its service starts as the ten minutes' prayer ends: they are still to pass)
    until = now + int(game.tables.spells["planar_ally"].get("minutes", 10)) + int(target.data.get("minutes", 60))
    rec = rules.add(caster, game.tables, cid, "planar_ally", until=until, now=now, word=False,
                    name=_spirit_name(game, caster), max_hp=rules.spirit_max_hp(game.tables, cid, form, level),
                    form=form, level=level, picture=fm.get("picture", ""), heals=True)
    if rec is None:
        return ["No spirit answers."]
    law.take_money(game, price)
    first = _first(caster)
    return [f"<magic>{first} prays to {esc(faith['god'])} for ten minutes</>, and a {esc(rec['name'])} stands where "
            f"the air was. {first} gives {money_text(price)} to {esc(faith['short'])}'s cause, and it agrees to serve "
            f"for {target.ref}. <dim>It fights beside you on its own, and goes home when its time is up.</>"]


def bound_rows(game) -> list[tuple]:
    """Every spirit or bound creature serving one of the party: (master, record)."""
    return [(c, r) for c in game.party if c.alive for r in rules.records(c)
            if r.get("spell") in ("planar_ally", "planar_binding")]


def bindable_captives(game) -> list[tuple[int, dict]]:
    """The party's captives that Planar Binding reaches (celestials, elementals, fey, fiends): (index, record)."""
    t = game.tables
    return [(i, cap) for i, cap in enumerate(game.renown.flags.get("captives") or [])
            if cap.get("def_id") in t.creatures and t.creatures[cap["def_id"]].get("kind") in BINDABLE]


def _left(game, rec: dict) -> str:
    m = max(0.0, float(rec.get("until") or 0) - game.world.time)
    if m >= 2 * DAY:
        return f"{int(m // DAY)} days"
    if m >= 120:
        return f"{int(m // 60)} hours"
    return f"{max(1, int(m))} minutes"


def binding_subjects(game, caster) -> list[Subject]:
    out = []
    for i, cap in bindable_captives(game):
        kind = game.tables.creatures[cap["def_id"]]["kind"]
        out.append(Subject(f"bind {esc(cap['name'])}, your captive ({kind})", "captive", str(i),
                           data={"def_id": cap["def_id"], "group": "captive"}))
    for c, r in bound_rows(game):
        whose = "" if c is caster else f" ({_first(c)}'s)"
        if r.get("bound"):
            words = f"bind the {esc(r['name'])}{whose} again (bound {_left(game, r)} more)"
        else:
            words = f"bind the {esc(r['name'])}{whose} (its service ends in {_left(game, r)})"
        out.append(Subject(words, "servant", f"{c.name}|{r['id']}", data={"group": "servant"}))
    return out


def servant_of(game, ref: str):
    """(master, record) for a binding Subject's ref, or (None, None)."""
    name, _, rid = ref.rpartition("|")
    for c in game.party:
        if c.name == name and c.alive:
            rec = next((r for r in rules.records(c) if str(r.get("id")) == rid), None)
            if rec is not None:
                return c, rec
    return None, None


def binding_problem(game, caster, target) -> str | None:
    from realmwalker.game import warding

    if not isinstance(target, Subject):
        if not binding_subjects(game, caster):
            return "no celestial, elemental, fey or fiend is held here: a captive, or a Planar Ally's spirit"
        return "choose (←→)"
    if target.kind == "captive":
        caps = game.renown.flags.get("captives") or []
        i = int(target.ref)
        if i >= len(caps) or caps[i].get("def_id") != target.data.get("def_id"):
            return "that captive is gone"
        if rules.room(caster) <= 0:
            return f"no more will answer you: {rules.MAX} serve you already"
        return None
    master, rec = servant_of(game, target.ref)
    if rec is None:
        return "it is gone"
    if master is not caster and rules.room(caster) <= 0:
        return f"no more will answer you: {rules.MAX} serve you already"
    if not rec.get("bound"):
        held = warding.inward_circle(game)
        if held is None or float(held["until"]) < game.world.time + BINDING_MINUTES:
            return "it will not stay an hour to be bound: hold it first in a Magic Circle turned inward"
    return None


def _cha_save(game, cid: str, form: str, dc: int, rng) -> bool:
    """A Charisma save against the binding (Magic Resistance: Advantage)."""
    from realmwalker.core import dice

    cdef = game.tables.creatures[cid]
    bonus = int((cdef.get("saves") or {}).get("cha", (int((cdef.get("abilities") or {}).get("cha", 10)) - 10) // 2))
    traits = list(cdef.get("traits", []))
    if form and "summon" in cdef:
        traits += list(cdef["summon"].get("forms", {}).get(form, {}).get("traits", []))
    roll = dice.d20(rng).natural
    if "magic_resistance" in traits:
        roll = max(roll, dice.d20(rng).natural)
    return roll + bonus >= dc


def cast_binding(game, caster, target, level: int) -> list[str]:
    from realmwalker.rules import spells as spellrules

    now = float(game.world.time)
    first = _first(caster)
    days = BINDING_DAYS.get(min(9, max(5, int(level))), 1)
    until = now + BINDING_MINUTES + days * DAY  # (from the end of the hour's casting)
    lasts = "a day" if days == 1 else f"{days} days"
    dc = spellrules.save_dc(game.sheet(caster), game.tables)
    rng = game.world.rng.child(f"planar_binding/{caster.name}/{game.world.time}")
    if target.kind == "captive":
        caps = game.renown.flags.get("captives") or []
        cap = caps[int(target.ref)]
        if _cha_save(game, cap["def_id"], "", dc, rng):
            return [f"<magic>{first} speaks the binding for an hour</> over {esc(cap['name'])}, who spits and will not "
                    "bend: the jewel cracks and goes dark, and nothing is bound."]
        name = cap["name"][4:] if cap["name"].startswith("the ") else cap["name"]
        rec = rules.add(caster, game.tables, cap["def_id"], "planar_binding", until=until, now=now, word=False,
                        name=name, heals=True, bound=True)
        if rec is None:
            return ["Nothing answers."]
        caps.remove(cap)
        if not caps:
            game.renown.flags.pop("captives", None)
        return [f"<magic>{first} speaks the binding for an hour</> over {esc(cap['name'])}, and the jewel burns to "
                f"nothing: the eyes go dull, then fix on {first}. It is {first}'s to command for {lasts}. "
                "<dim>Its bonds come off and it fights beside you on its own. No watch will pay for it now.</>"]
    master, rec = servant_of(game, target.ref)
    if _cha_save(game, rec["cid"], rec.get("form", ""), dc, rng):
        return [f"<magic>{first} speaks the binding for an hour</> over the {esc(rec['name'])}, which only smiles: the "
                "jewel cracks and goes dark, and nothing is bound. <dim>Its own bargain still holds.</>"]
    rec["until"] = max(float(rec.get("until") or now), until)
    rec["bound"] = True
    rec["warned"] = False
    if master is not caster:
        rules.drop(master, rec)
        rows = rules.records(caster, make=True)
        rec["id"] = max([0] + [int(r.get("id", 0)) for r in rows]) + 1
        rows.append(rec)
    return [f"<magic>{first} speaks the binding for an hour</> over the {esc(rec['name'])}, and the jewel burns to "
            f"nothing: it is bound to {first} for {lasts}."]


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
            dead = [r for r in warn if rules.is_undead(r)]
            if dead:
                game.say(f"<warn>The dead grow restless: {_first(c)}'s hold on "
                         f"{'them' if len(dead) > 1 else 'the ' + dead[0]['name']} ends within two hours.</> "
                         f"<dim>Cast {game.tables.spells[dead[0]['spell']]['name']} again to hold them.</>", "warn")
            for r in warn:
                if not rules.is_undead(r):
                    keep = "" if r.get("bound") else \
                        " <dim>Planar Binding, cast in a Magic Circle turned inward, would keep it.</>"
                    game.say(f"<warn>The {esc(r['name'])}'s {'binding' if r.get('bound') else 'service'} to "
                             f"{_first(c)} ends within two hours.</>{keep}", "warn")
        freed = rules.due(c, now) if c.alive else list(rules.records(c))
        if freed:
            for r in freed:
                rules.drop(c, r)
            _leave(game, c, freed)
        _rot_day(game, c, now)


def _leave(game, master, freed: list[dict]) -> None:
    """Those whose time is up: the dead go free (and may turn on the party); the bound go away."""
    for r in freed:
        if not rules.is_undead(r):
            _go_home(game, master, r)
    dead = [r for r in freed if rules.is_undead(r)]
    if dead:
        _go_free(game, master, dead)


def _go_home(game, master, rec: dict) -> None:
    """A spirit's service or a binding is over: a spirit reports and returns to its own plane; a bound creature of
    this world slips off into the wild."""
    name = esc(rec["name"])
    if rec.get("form"):
        game.say(f"<magic>The {name} has served its time.</> It bows its head to {_first(master)}, says that what was "
                 "asked is done, and is gone like a candle blown out.", "magic")
    else:
        game.say(f"<warn>The binding on the {name} is over.</> It backs away from {_first(master)}, then turns and "
                 "runs, and is soon lost to sight.", "warn")


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
        char.spells.pop("servants", None)
        _leave(game, char, freed)


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
        loss = min(dice.roll("3d6", rng).total, c.max_hp)  # (what is taken: no more than there is)
        c.effects[rules.ROT_LOST] = float(c.effects.get(rules.ROT_LOST, 0)) + loss
        c.max_hp = max(0, c.max_hp - loss)
        c.hp = min(c.hp, c.max_hp)
        c.effects[rules.ROT_HP] = float(min(c.effects[rules.ROT_HP], c.hp))
        game.say(f"<danger>The rot spreads in {_first(c)}'s flesh</>: the hit point maximum falls by {loss}. "
                 f"<dim>Remove Curse lifts it.</>", "danger")
        if c.max_hp <= 0:
            c.hp = 0
            c.effects[rules.DUST] = 1.0
            c.death_cause = "rotted away to dust under a mummy's curse"
            game.say(f"<danger>{_first(c)} crumbles to grey dust.</>", "danger")
            c.effects[rules.ROT_DAYS] = float(done)
            from realmwalker.game import survival

            survival.check_death(game, c)
            return
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
