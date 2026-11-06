"""Traitors (Expansion 6 F.3, docs/ADVENTURES.md §5.3, §5.6): one of the cast who serves the villain, with a hidden
reason, at least two tells the attentive player can catch, and a moment.

Whether a tale hides one is decided once, the first day of its second chapter (when the cast is known and trust has
had a chance to grow): adventures.cast.json "traitors" `chance` by blueprint, then whom, weighted by `from`:
- the patron, at most once in a hero's life (the DMG's rule: `renown.flags["patron_betrayed"]` keeps the tale it
  happened in; story/patrons.py's motive becomes "traitor");
- the tale's ally (story/stakes.py; never the ally the Reading named, `adv["reading"]["named"]`, Part F.4);
- a hired companion (bond "hired") who is no tale's ally.
The record is `adv["traitor"]` (None: no traitor) {role, npc, name, first, sex, reason (kin, paid, belief), why,
used {near: [i], far: [i]}, seen, last, state, made, fate, key, in_fight}.

The tells come by night (`on_night`, at camp or at the inn, from `tell_after` days after it was decided, every
`every` days at `event_chance`, `tells` of them at most): the beat "traitor_tell" with a line of the reason's `near`
words (one at your side) or `far` (the patron, an ally riding with the patron). The patron's sealed letter in a
deliver step is a tell too (`read_letter`). From the second tell the beat lets you act (condition `traitor_tells`):
have it out (Insight: they yield, and feed the villain false word - it is surprised at the finale; or they flee to
it), send them away, or draw steel (`fight`: they and the men they bring). The patron may also be faced in their
own town (`talk_choices`: "story_accuse", sure from the second tell, an Insight check on the first).

Missed, the betrayal comes at the moment (`on_night` once the finale's chapter is open): one at your side goes in
the night before, with a key of the tale, and the villain's servants come after them (the beat "traitor_turns": op
`traitor turn`, then `strike`); one far away sells you (the beat "traitor_sells": a patron calls the militia off).
A patron who has not yet been kind to you twice (patrons.trust < betray_at) falters instead. Still hidden when the
finale's fight begins (`at_finale`): the twist - one in the fight turns on its second round (charmed into the
villain's service: it fights for the foe), a patron's men stand beside it and it is not surprised. One who turned or
fled stands beside the villain (`turned_as` by tier, role "traitor"); `on_battle` follows them. Their fate is a
page of the epilogue (`after_tale`; a patron's replaces the grateful patron's page).

    decide(game, adv)   daily(game)   on_night(game, where, morning)   at_finale(battle, game, adv, boss)
    on_battle(game, result)   read_letter(game, q, first)   talk_choices(conv)   talk_choose(conv, choice)
    after_tale(game, adv)   journal_line(game, adv)

The full forms (F.5): `from_by` gives a blueprint its own weights by role (the Risen's patron most of all), and a
reason may be a tale's or a role's own (`blueprints`, `roles`: the Risen's patron who paid the waker, "woke"; the
Outlaw's cut of the toll, "toll"). A reason with `waker` lines: once the tale's waker is beaten (its lieutenant's
fate, or its defeat step done) while the traitor is hidden, `rec["waker"]` is "due" (daily) and what was found on it
is told at the next fire or inn before any other tell ("told"), whatever the clock says.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story.beats import condition, op

STATES = ("hidden", "yielded", "sent", "fled", "fought", "slain", "turned", "faltered", "never")
GONE = ("fled", "turned")  # (they stand beside the villain at the finale)
BEATS = ("traitor_tell", "traitor_turns", "traitor_sells")
TURN_ROUND = 2  # the round of the finale one still hidden turns on
TALK_CHOICES = {"story_accuse"}


def spec(game) -> dict:
    return game.tables.adventures.get("traitors") or {}


def _story():
    from realmwalker.game import story

    return story


def _today(game) -> int:
    return int(game.moment.total_days)


def _adv(game, ctx) -> dict | None:
    return _story().adventures(game.world).get((ctx or {}).get("adv") or "")


def hidden(adv: dict) -> dict | None:
    rec = adv.get("traitor")
    return rec if rec and rec["state"] == "hidden" else None


# ---------------------------------------------------------------------------- who
def _candidates(game, adv: dict) -> list[tuple[str, object]]:
    from realmwalker.game.story import patrons, reading, stakes

    out: list[tuple[str, object]] = []
    named = reading.named(game, adv)  # (never the one the Reading's Hand named: F.4)
    p = patrons.npc(game, adv)
    rec = patrons.record(adv)
    if p is not None and rec is not None and rec["motive"] == "plain" and not _patron_spent(game, adv) and \
            (named is None or int(named) != int(p.id)):
        out.append(("patron", p))
    ally = adv.get("ally") or {}
    a = stakes.npc_of(game, adv)
    if ally.get("state") in ("joined", "riding") and a is not None and a.alive and \
            (named is None or int(named) != int(a.id)):
        out.append(("ally", a))
    for c in game.party[1:]:
        comp = c.companion or {}
        if comp.get("bond", "hired") == "hired" and not comp.get("adv") and c.alive:
            out.append(("companion", c))
            break
    return out


def _patron_spent(game, adv: dict) -> bool:
    """A patron has betrayed this hero already (or is the traitor of another of their tales): never a second."""
    from realmwalker.game.story.forge import life_of

    if game.renown.flags.get("patron_betrayed") not in (None, adv["id"]):
        return True
    life = life_of(game)
    return any(a is not adv and a["hero"]["life"] == life and (a.get("traitor") or {}).get("role") == "patron"
               and a["traitor"]["state"] not in ("faltered", "never")
               for a in _story().adventures(game.world).values())


def decide(game, adv: dict) -> None:
    """Whether this tale hides a traitor, and who (decided once, the first day of its second chapter; with nobody
    yet to be it - the ally not yet won, nobody hired - asked again each day until the finale's chapter)."""
    if "traitor" in adv or int(adv.get("chapter", 0)) < 1:
        return
    sp = spec(game)
    rng = game.world.rng.child(f"traitor/{adv['id']}")
    if not sp or not rng.chance(float(sp["chance"].get(adv["blueprint"], 0.0))):
        adv["traitor"] = None
        return
    weights = dict(sp["from"], **sp.get("from_by", {}).get(adv["blueprint"], {}))  # (F.5: a tale's own)
    cands = [(r, w) for r, w in _candidates(game, adv) if int(weights.get(r, 0)) > 0]
    if not cands:
        if _in_finale(adv):
            adv["traitor"] = None
        return
    role, who = rng.weighted(cands, [float(weights[r]) for r, _ in cands])
    reason = _reason(sp, adv, role, rng)
    if role == "companion":
        npc_id = (who.companion or {}).get("npc")
        name, sex = who.name, who.sex
    else:
        npc_id, name, sex = int(who.id), who.name, who.sex
    rec = {"role": role, "npc": npc_id, "name": name, "first": name.split()[0], "sex": sex, "reason": reason,
           "used": {"near": [], "far": []}, "seen": 0, "last": _today(game), "state": "hidden", "made": _today(game),
           "fate": None, "key": None, "in_fight": False}
    adv["traitor"] = rec
    if role == "patron":
        from realmwalker.game.story import patrons

        patrons.record(adv)["motive"] = "traitor"
        game.renown.flags["patron_betrayed"] = adv["id"]  # (a patron betrays at most once in a hero's life)
    rec["why"] = _say(game, adv, sp["reasons"][reason]["why"], rng.child("why"))


def _reason(sp: dict, adv: dict, role: str, rng) -> str:
    """Why they do it: a reason that fits this tale and this role (the full forms' own among them: F.5)."""
    bp = adv["blueprint"]
    fits = {k: v for k, v in sp["reasons"].items() if int(v["weight"]) > 0
            and bp in v.get("blueprints", [bp]) and role in v.get("roles", [role])}
    fits = fits or {k: v for k, v in sp["reasons"].items() if not v.get("blueprints") and not v.get("roles")} \
        or dict(sp["reasons"])  # (no reason written for this tale and role: any plain one)
    reasons = sorted(fits)
    if not any(int(fits[k]["weight"]) > 0 for k in reasons):
        return reasons[0]
    return rng.weighted(reasons, [float(fits[k]["weight"]) for k in reasons])


def daily(game) -> None:
    for adv in _story().active(game):
        decide(game, adv)
        _waker_falls(game, adv)


def _waker_falls(game, adv: dict) -> None:
    """The Risen's waker beaten while the one who paid it is still hidden: what is found on it is a tell, told at
    the next fire or inn (F.5, ADVENTURES.md §6.2: the waker's identity, sometimes the patron)."""
    rec = hidden(adv)
    if rec is None or rec.get("waker") or not spec(game)["reasons"][rec["reason"]].get("waker"):
        return
    from realmwalker.game.story import lieutenants

    lt = lieutenants.of(game, adv, "waker")
    beaten = lt is not None and lt["fate"] not in ("unmet", "met", "escaped")
    beaten = beaten or any(st["kind"] == "defeat" and st["target"].get("role") == "waker" and st["state"] == "done"
                           for ch in adv["chapters"] for st in ch["steps"])
    if beaten:
        rec["waker"] = "due"


def companion(game, adv: dict, *, waiting: bool = True):
    """The traitor as a companion of the party (or told to wait), or None."""
    rec = adv.get("traitor") or {}
    if not rec:
        return None
    pool = list(game.party[1:]) + (list(getattr(game, "waiting", [])) if waiting else [])
    for c in pool:
        comp = c.companion or {}
        if rec.get("npc") is not None and comp.get("npc") is not None and int(comp["npc"]) == int(rec["npc"]):
            return c
        if rec.get("npc") is None and c.name == rec["name"]:
            return c
    return None


def near(game, adv: dict) -> bool:
    """Whether the traitor travels with you (a companion in the party), or is someone you do not see every day."""
    return companion(game, adv, waiting=False) is not None


def npc(game, adv: dict):
    rec = adv.get("traitor") or {}
    return game.world.npcs.get(int(rec["npc"])) if rec.get("npc") is not None else None


def _words(game, adv: dict) -> dict:
    """The tale's words with the traitor's: {traitor}, {traitor_full}, {traitor_role}, {why}, and their pronouns."""
    from realmwalker.game.story import words as wordsmod

    out = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
    rec = adv.get("traitor") or {}
    if rec:
        p = textgen.pronoun_values(rec.get("sex", ""))
        p["es"] = "es" if p["s"] else ""
        p["theirs"] = {"he": "his", "she": "hers"}.get(p["they"], "theirs")
        out.update(p)
        out.update(traitor=rec["first"], traitor_full=rec["name"], why=rec.get("why", ""),
                   traitor_role={"patron": "the one who sent for you", "ally": "the one who came with you",
                                 "companion": "one of your own company"}[rec["role"]])
    return out


def _say(game, adv: dict, lines, rng) -> str:
    text = textgen.fill(rng.choice(list(lines)), rng, game.tables.adventures.get("words", {}), _words(game, adv))
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------- the tells, and the moment
def _in_finale(adv: dict) -> bool:
    ch = _story().chapter(adv)
    return ch is not None and any(st["kind"] == "finale" for st in ch["steps"])


def on_night(game, where: str, *, morning: bool = True) -> bool:
    """A night at camp or at the inn (story.on_night): a tell, or - in the finale's chapter - the betrayal.
    True when a beat waits. The betrayal of one at your side comes in the dark; the rest wait for the morning."""
    from realmwalker.game.story import beats, patrons

    sp = spec(game)
    if not sp or beats.pending(game) is not None or where not in ("inn", "camp"):
        return False
    today = _today(game)
    clock = sp["clock"]
    for adv in _story().active(game):
        rec = hidden(adv)
        if rec is None:
            continue
        close = near(game, adv)
        if _in_finale(adv):
            if rec["role"] == "patron" and patrons.trust(adv) < int(patrons.spec(game)["trust"]["betray_at"]):
                rec["state"] = rec["fate"] = "faltered"  # (they could not, after all the kindness between you)
                continue
            if close and where == "camp" and not morning:
                return _offer(game, adv, "traitor_turns", where, {})
            if not close and morning and (rec["role"] != "ally" or npc(game, adv) is not None):
                return _offer(game, adv, "traitor_sells", where, {})
            continue
        if rec.get("waker") == "due" and morning and not (close and where != "camp"):
            rec["waker"] = "told"  # (what was found on the waker: told first, whatever the clock says)
            tell = _say(game, adv, sp["reasons"][rec["reason"]]["waker"],
                        game.world.rng.child(f"traitor-waker/{adv['id']}"))
            rec["seen"] = int(rec["seen"]) + 1
            rec["last"] = today
            _note(game, adv, tell)
            return _offer(game, adv, "traitor_tell", where, {"tell": tell, "doubt": _doubt(rec)})
        if not morning or (close and where != "camp") or today - int(rec["made"]) < int(clock["tell_after"]) or \
                today - int(rec["last"]) < int(clock["every"]) or int(rec["seen"]) >= int(clock["tells"]):
            continue
        if not game.world.rng.child(f"traitor-night/{adv['id']}/{today}").chance(float(clock["event_chance"])):
            continue
        tell = _tell(game, adv, rec, "near" if close else "far")
        if tell is None:
            continue
        rec["seen"] = int(rec["seen"]) + 1
        rec["last"] = today
        _note(game, adv, tell)
        return _offer(game, adv, "traitor_tell", where, {"tell": tell, "doubt": _doubt(rec)})
    return False


def _tell(game, adv: dict, rec: dict, kind: str) -> str | None:
    lines = spec(game)["reasons"][rec["reason"]][kind]
    used = rec.setdefault("used", {}).setdefault(kind, [])
    free = [i for i in range(len(lines)) if i not in used]
    if not free:
        return None
    rng = game.world.rng.child(f"traitor-tell/{adv['id']}/{rec['seen']}")
    i = rng.choice(free)
    used.append(i)
    return _say(game, adv, [lines[i]], rng)


def _doubt(rec: dict) -> str:
    n = int(rec["seen"])
    if n <= 1:
        return "It may be nothing. You tell yourself it is nothing."
    if n == 2:
        return f"Twice now. Whatever it is, it is not nothing, and it is {rec['first']}."
    return f"There is no explaining it away any more. It is {rec['first']}."


def _note(game, adv: dict, tell: str) -> None:
    _story().journal(adv, f"Something is wrong about {adv['traitor']['first']}: {tell}", _today(game))


def _offer(game, adv: dict, beat: str, where: str, more: dict) -> bool:
    from realmwalker.game.story import beats

    if beat not in game.tables.beats:
        return False
    words = _words(game, adv)
    words.update(more)
    beats.offer(game, beat, adv=adv["id"], where=where, words=words)
    return True


def read_letter(game, q: dict, first: bool) -> list[str]:
    """The seal broken on a deliver step's letter (quests.read_letter): if the patron who gave it serves the villain,
    it is a tell. Returns what is read ([]: nothing of the tale's)."""
    adv = _story().adventures(game.world).get(q.get("adventure") or "")
    rec = hidden(adv) if adv else None
    if rec is None or rec["role"] != "patron":
        return []
    if not first:
        return [f"<warn>{esc(rec.get('letter', ''))}</>"] if rec.get("letter") else []
    text = (f"The letter is in {rec['first']}'s hand, and it is not what you were told. Half of it is a list: your "
            f"road, the days, the people who stand with you. It is meant to be read by someone else first.")
    rec["letter"] = text
    rec["seen"] = int(rec["seen"]) + 1
    rec["last"] = _today(game)
    _note(game, adv, text)
    return [f"<warn>{esc(text)}</>"]


@condition("traitor_near")
def _near_cond(game, ctx, value) -> bool:
    """The traitor of this beat's tale travels with you (or, with false, does not): steel and sending away are for
    one at your side; one far off is faced where they live."""
    adv = _adv(game, ctx)
    return adv is not None and near(game, adv) == bool(value)


@condition("traitor_tells")
def _tells_cond(game, ctx, value) -> bool:
    """The traitor of this beat's tale is still hidden, and you have seen at least this many of their tells."""
    adv = _adv(game, ctx)
    rec = hidden(adv) if adv else None
    return rec is not None and int(rec["seen"]) >= int(value)


# ---------------------------------------------------------------------------- what is done about it
@op("traitor")
def _traitor_op(game, ctx, what: str):
    """The traitor's story: yield (caught and confessed: the villain is fed false word), flee (caught, they run to
    it), send (sent away), fight (steel here and now: they and the men they bring), turn (the betrayal: one at your
    side goes with a key of the tale; a patron calls the militia off)."""
    adv = _adv(game, ctx)
    rec = (adv or {}).get("traitor")
    if not rec or rec["state"] != "hidden":
        return []
    out: list[str] = []
    if what == "yield":
        rec["state"] = rec["fate"] = "yielded"
        line = f"{rec['name']} has confessed. What goes back to {_villain(game, adv)} now is what you want it to hear."
        _story().journal(adv, line, _today(game))
        out.append(f"<good>{esc(line)}</>")
        if "traitor_caught" not in adv["flags"]:
            adv["flags"].append("traitor_caught")
        return out
    if what in ("flee", "send", "fight", "turn"):
        out += _leave(game, adv, rec, deserted=what != "send")
    if what == "flee":
        rec["state"] = "fled"
        out.append(f"<warn>{esc(rec['name'])} has gone to {esc(_villain(game, adv))}.</>")
    elif what == "send":
        rec["state"] = rec["fate"] = "sent"
    elif what == "fight":
        rec["state"] = "fought"
        _fight(game, adv, rec)
    elif what == "turn":
        rec["state"] = "turned"
        out += _betray(game, adv, rec)
    _story().journal(adv, _say(game, adv, ["{traitor_full} served {villain_short}. {why}"],
                               game.world.rng.child(f"traitor-why/{adv['id']}")), _today(game))
    game.dirty = True
    return out


def _villain(game, adv: dict) -> str:
    return _story()._villain_name(game, adv)


def _leave(game, adv: dict, rec: dict, *, deserted: bool) -> list[str]:
    """They are no longer with you: a companion leaves the party, an ally riding with the patron breaks with you, a
    patron leaves their town."""
    from realmwalker.game import companions

    out: list[str] = []
    c = companion(game, adv)
    if c is not None:
        out += [f"<warn>{esc(x)}</>" for x in companions.dismiss(game, c, deserted=deserted)]
    ally = adv.get("ally") or {}
    if rec["role"] == "ally" and ally.get("state") in ("joined", "riding"):
        ally["state"] = "broke"
        if "ally" in adv["keys"]:
            adv["keys"].remove("ally")
    p = npc(game, adv)
    if p is not None and rec["role"] != "companion" and c is None:
        p.present = False
        p.flags["gone"] = True  # (gone from their town, to the villain or anywhere but near you: people.py keeps them
        p.flags["story_gone"] = adv["id"]  # away)
    return out


def _betray(game, adv: dict, rec: dict) -> list[str]:
    from realmwalker.game.story import villain
    from realmwalker.game.story import words as wordsmod

    out: list[str] = []
    villain.notice(game, adv, 2)
    if "betrayed" not in adv["flags"]:
        adv["flags"].append("betrayed")
    lost = [k for k in ("militia", "ally") if k in adv["keys"]] if rec["role"] == "patron" else sorted(adv["keys"])
    if lost:
        k = lost[0] if rec["role"] == "patron" else game.world.rng.child(f"traitor-key/{adv['id']}").choice(lost)
        adv["keys"].remove(k)
        rec["key"] = k
        out.append(f"<danger>{esc(rec['first'])} took {esc(wordsmod.key_text(game, adv, k))} with them.</>")
    return out


def _men(game, adv: dict, rec: dict, rng, *, with_leader: bool) -> list:
    """The traitor (as a fighter of their tier) and the men they bring, tagged with the tale (role "traitor")."""
    from realmwalker.rules.creatures import spawn

    sp = spec(game)
    tier = max(1, min(4, int(adv.get("tier", 1))))
    t = game.tables
    ids = []
    if with_leader:
        ids.append(next((k for k in sp["turned_as"][tier - 1] if k in t.creatures), "bandit"))
    men = [k for k in sp["patron_men"][tier - 1] if k in t.creatures] or ["thug"]
    ids += [men[i % len(men)] for i in range(1 if with_leader else 2)]
    out = []
    for n, k in enumerate(ids):
        c = spawn(t, k, rng.child(f"m{n}"), 9500 + n, now=int(game.world.time))
        lead = with_leader and n == 0
        if lead:
            c.name, c.named = rec["name"], True
        c.story = {"adv": adv["id"], "role": "traitor", "leader": lead}
        out.append(c)
    return out


def _fight(game, adv: dict, rec: dict) -> None:
    from realmwalker.game.encounters import PendingEncounter, threat_words

    if game.over is not None:
        return
    creatures = _men(game, adv, rec, game.world.rng.child(f"traitor-fight/{adv['id']}"), with_leader=True)
    intro = _say(game, adv, ["{traitor_full} and the ones {they} brought, steel out."],
                 game.world.rng.child(f"traitor-intro/{adv['id']}"))
    game.encounter = PendingEncounter("thugs", creatures, intro, True,
                                      threat_words(game.tables, creatures, game.party), attitude="hostile")
    game.travel = None


# ---------------------------------------------------------------------------- facing the patron in their town
def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    game, person = conv.game, conv.npc
    out = []
    for adv in _story().active(game):
        rec = hidden(adv)
        if rec is None or rec["role"] != "patron" or int(rec["seen"]) < 1 or rec.get("npc") is None or \
                int(rec["npc"]) != int(person.id):
            continue
        out.append(Choice("story_accuse", f"I know what you have done, {person.first_name}.",
                          data={"adv": adv["id"]}))
    return out


def talk_choose(conv, choice) -> None:
    game = conv.game
    adv = _story().adventures(game.world).get(choice.data.get("adv"))
    rec = hidden(adv) if adv else None
    if rec is None:
        return
    sure = int(rec["seen"]) >= 2
    ok, roll = (True, "") if sure else conv.check("insight", 14)
    ctx = {"adv": adv["id"]}
    if ok:
        conv.npc_says(_say(game, adv, ["\"...How long have you known?\" {traitor} sits down, very slowly. \"{why}\""],
                           game.world.rng.child(f"accuse/{adv['id']}")) + (f" {roll}" if roll else ""))
        for line in _traitor_op(game, ctx, "yield"):
            conv.note(line)
    else:
        conv.npc_says(f"\"I don't know what you mean.\" But {esc(rec['first'])} will not look at you. {roll}")
        for line in _traitor_op(game, ctx, "flee"):
            conv.note(line)
        conv.ended = True
    game.dirty = True


# ---------------------------------------------------------------------------- the finale
def at_finale(battle, game, adv: dict, boss) -> list[str]:
    """The finale (finale.prepare, after its keys): false word fed to it; the twist of one still hidden; one who
    turned or fled standing beside it."""
    from realmwalker.rules.combat import FOE

    rec = adv.get("traitor")
    if not rec:
        return []
    out: list[str] = []
    if rec["state"] == "yielded":
        if battle.env.surprised is None:
            battle.env.surprised = FOE
        out.append(f"<good>{esc(_say(game, adv, ['It does not expect you yet. {traitor} told it what you wanted it to hear.'], battle.rng))}</>")
        return out
    if rec["state"] in GONE and rec["role"] != "patron":
        for c in _men(game, adv, rec, battle.rng.child(f"traitor-finale/{adv['id']}"), with_leader=True)[:1]:
            f = battle.add_ally(c, boss, "story_foe")
            f.bond = None  # (a foe in its own right: it keeps the fight going, and is not the villain's to dismiss)
            f.auto = True
        out.append(f"<danger>{esc(_say(game, adv, ['{traitor_full} stands beside it.'], battle.rng))}</>")
        return out
    if rec["state"] == "turned" and rec["role"] == "patron":
        if battle.env.surprised == FOE:
            battle.env.surprised = None
        out.append(f"<warn>{esc(_say(game, adv, ['It knew you were coming. {traitor} told it.'], battle.rng))}</>")
        return out
    if rec["state"] != "hidden":
        return out
    fighter = _fighter_of(battle, game, adv, rec)
    if fighter is None:  # (far from here: they sold your road all the same, and their men are here)
        from realmwalker.game.story import patrons

        if rec["role"] == "patron" and patrons.trust(adv) < int(patrons.spec(game)["trust"]["betray_at"]):
            rec["state"] = rec["fate"] = "faltered"
            return out
        rec["state"] = "turned"
        _betray(game, adv, rec)
        if battle.env.surprised == FOE:
            battle.env.surprised = None
        for c in _men(game, adv, rec, battle.rng.child(f"traitor-men/{adv['id']}"), with_leader=False):
            f = battle.add_ally(c, boss, "story_foe")
            f.bond = None
            f.auto = True
        out.append(f"<danger>{esc(_say(game, adv, ['It was waiting for you, and {traitor} sent men to stand with it.'], battle.rng))}</>")
        return out

    def turn(b, _done=[]):
        if _done or b.round < TURN_ROUND or b.outcome is not None or not fighter.active:
            return
        _done.append(True)
        from realmwalker.rules.engine import durations

        rec["in_fight"] = True
        rec["state"] = "turned"
        took = durations.give(b, fighter, "charmed", rounds=None, source=boss, control=FOE)
        if not took:  # (nothing can turn their mind: they run instead)
            fighter.state = "fled"
            b._event("leave", who=fighter.id)
        b.say(_say(game, adv, ["{traitor_full} steps back from you, and turns, and stands with it."], b.rng), "danger")
        b._event("condition", who=fighter.id, cond="charmed")

    battle.round_hooks.append(turn)
    return out


def _fighter_of(battle, game, adv: dict, rec: dict):
    """The traitor's fighter in this battle (a companion, or an ally brought by stakes.to_battle), or None."""
    c = companion(game, adv, waiting=False)
    for f in battle.fighters:
        if f.char is None:
            continue
        if c is not None and f.char is c:
            return f
        if rec["role"] == "ally" and f.char.name == rec["name"] and f.bond is not None:
            return f
    return None


def on_battle(game, result) -> None:
    """After a fight (story.on_battle): the traitor slain, or one who turned in the fight gone over for good."""
    advs = _story().adventures(game.world)
    for c in result.dead:
        tag = getattr(c, "story", None) or {}
        adv = advs.get(tag.get("adv")) if tag.get("role") == "traitor" and tag.get("leader") else None
        rec = (adv or {}).get("traitor")
        if rec and rec["state"] in GONE + ("fought",):
            rec["state"] = rec["fate"] = "slain"
    for adv in advs.values():
        rec = adv.get("traitor")
        if not rec or not rec.get("in_fight"):
            continue
        rec["in_fight"] = False
        c = companion(game, adv)
        if c is not None and not c.alive:
            rec["fate"] = "slain"
        elif c is not None:
            from realmwalker.game import companions

            for line in companions.dismiss(game, c, deserted=True):
                game.say(line, "warn")
        ally = adv.get("ally") or {}
        if rec["role"] == "ally" and ally.get("state") in ("joined", "riding"):
            ally["state"] = "broke"
    for adv in _story().active(game):
        rec = adv.get("traitor")
        if rec and rec["state"] == "fought" and result.outcome == "victory":
            rec["state"] = rec["fate"] = "sent"  # (beaten, and gone where they will not trouble you again)


# ---------------------------------------------------------------------------- the end
def after_tale(game, adv: dict) -> None:
    """The tale is over (endings.finish): their fate, and a page of the epilogue (a patron's replaces their page)."""
    rec = adv.get("traitor")
    sp = spec(game)
    if not rec or not sp:
        return
    if rec.get("fate") is None:
        rec["fate"] = {"hidden": "never", "fought": "sent"}.get(rec["state"], rec["state"])
    if rec["state"] == "hidden":
        rec["state"] = "never"
    if rec["role"] == "patron" and rec["fate"] in ("faltered", "never") and \
            game.renown.flags.get("patron_betrayed") == adv["id"]:
        game.renown.flags.pop("patron_betrayed")  # (it never came to a betrayal: the once in a life is not spent)
    if rec["fate"] == "never" and int(rec["seen"]) == 0:
        return  # (never so much as suspected: nothing to tell)
    text = _say(game, adv, sp["fates"].get(rec["fate"], sp["fates"]["never"]),
                game.world.rng.child(f"traitor-fate/{adv['id']}"))
    pages = adv.setdefault("epilogue", [])
    if rec["role"] == "patron":
        pages[:] = [p for p in pages if p.get("about") != "patron"]
    page = next((p for p in pages if p.get("about") == "traitor"), None)
    if page is not None:
        page["text"] = text
    else:
        pages.insert(max(0, len(pages) - 1), {"about": "traitor", "text": text})


WORDS = {"yielded": "confessed", "sent": "sent away", "fled": "fled to the enemy", "fought": "fought you",
         "slain": "slain", "turned": "betrayed you", "faltered": "could not do it", "never": "never known"}


def journal_line(game, adv: dict) -> str:
    """The doubts you have, and what came of them (the journal)."""
    rec = adv.get("traitor")
    if not rec or (rec["state"] == "hidden" and int(rec["seen"]) == 0):
        return ""
    if rec["state"] == "hidden":
        n = int(rec["seen"])
        return f"{esc(rec['name'])}: {n} thing{'s' if n != 1 else ''} that do not add up"
    return f"{esc(rec['name'])} served {esc(_villain(game, adv))} ({WORDS.get(rec['state'], rec['state'])})"
