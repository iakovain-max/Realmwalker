"""Allies with stakes (Expansion 6 F.1, docs/ADVENTURES.md §5.6): an adventure's ally is a story, not a sword for hire.

Winning a tale's ally is gaining its key "ally" (a recruit step's talk, the hunter's situation, the one who knows):
`join` (from the key op) gives them a stake (adventures.allies.json `stakes`, by the tale's blueprint and the ally's
trade) and either brings them into the party as a companion under the bond "oath" (companions.json: no wage, their
stake's values) or, when the company is full, has them ride with the patron: they stay in their town and come to the
tale's fights as a character beside you (`to_battle`, from finale.prepare: any fight with a foe of the tale;
`Battle.add_ally(char=)`, bond kind "story_ally", on Auto), without taking a place in the party.

The record is `adv["ally"]` {npc, stake (its id), words {stake, confidence}, state, joined, told, crisis, held,
at_finale, fate, fate_due}. States: joined (a companion), riding (with the patron), taken (carried off by the
villain: a rescue step), broke (went off alone), home, fell, sworn (stayed with you for good).

The arc, three beats played on a night at camp or at the inn (`on_night`, beats.allies.json): the confidence (their
stake, a day or more after joining; for one who rides, at the inn of their own town), a crisis once the second chapter
has begun (by the stake: revenge - they want to go now - or doubt - they want to go home; one who rides with the
patron is taken instead), and, when the tale is won and they live, their fate: the oath (the bond "pledged") or home.
A death in the finale is dying well (the epilogue says so). The op "ally" moves the arc; a companion who leaves
(`dismissed`) or dies (`died`) is followed here too; the key "ally" goes with one who leaves.

    join(game, adv)   on_night(game, where)   to_battle(battle, game, advs)   on_battle(game, result)
    after_tale(game, adv)   dismissed(game, c, deserted)   died(game, c)   journal_line(game, adv)
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story.beats import condition, op

LIVE = ("joined", "riding", "taken")
CRISES = {"revenge": "ally_crisis_revenge", "doubt": "ally_crisis_doubt", "taken": "ally_crisis_taken"}


def spec(game) -> dict:
    return game.tables.adventures.get("allies") or {}


def _story():
    from realmwalker.game import story

    return story


def _today(game) -> int:
    return int(game.moment.total_days)


def npc_of(game, adv: dict):
    rec = adv.get("ally") or {}
    return game.world.npcs.get(int(rec["npc"])) if rec.get("npc") is not None else None


def companion_of(game, adv: dict, *, waiting: bool = True):
    """The ally as a companion of the party (or told to wait, with `waiting`), or None."""
    pool = list(game.party[1:]) + (list(getattr(game, "waiting", [])) if waiting else [])
    return next((c for c in pool if c.companion and c.companion.get("adv") == adv["id"]), None)


# ---------------------------------------------------------------------------- joining
def join(game, adv: dict) -> list[str]:
    """The tale's ally is won: their stake, and a place in the party (or a seat by the patron). Once a tale."""
    from realmwalker.game import companions
    from realmwalker.game.story import cast

    sp = spec(game)
    who = cast.person(game.world, adv["cast"].get("ally"))
    if not sp or adv.get("ally") or who is None or not hasattr(who, "job") or not who.alive:
        return []
    rng = game.world.rng.child(f"ally/{adv['id']}")
    sid = _pick_stake(game, adv, who, rng)
    stake = sp["stakes"][sid]
    rec = {"npc": int(who.id), "stake": sid, "state": "riding", "joined": _today(game), "told": None,
           "crisis": None, "held": None, "fate": None}
    adv["ally"] = rec
    words = _words(game, adv)
    tables = game.tables.adventures.get("words", {})
    rec["words"] = {"stake": textgen.fill(rng.choice(stake["stake"]), rng, tables, words)}
    rec["words"]["confidence"] = textgen.fill(rng.choice(stake["confidence"]), rng, tables, _words(game, adv))
    if companions.room(game) and not who.flags.get("companion"):
        char = _character(game, who, rng.child("build"))
        lines = companions.enlist(game, who, char, "oath", values=list(stake["values"]), want=stake["want"],
                                  adv=adv["id"], stake=rec["words"]["stake"])
        rec["state"] = "joined"
        _story().journal(adv, esc(f"{who.name} came with you, for {rec['words']['stake']}."), _today(game))
        return lines
    line = _say(game, adv, sp["riding"], rng.child("riding"))
    _story().journal(adv, esc(f"{who.name} rides with {words.get('patron', 'the patron')}, for "
                              f"{rec['words']['stake']}."), _today(game))
    return [f"<good>{esc(line)}</>"]


def _pick_stake(game, adv: dict, npc, rng) -> str:
    """A stake written for this tale comes first, then one for any tale; the ally's trade may narrow it."""
    stakes = spec(game)["stakes"]
    fits = [k for k, s in sorted(stakes.items()) if adv["blueprint"] in s.get("blueprints", [adv["blueprint"]])
            and npc.job in s.get("jobs", [npc.job])]
    own = [k for k in fits if adv["blueprint"] in stakes[k].get("blueprints", ())]
    return rng.choice(own or fits or sorted(stakes))


def _character(game, npc, rng):
    """The ally as a full character: the class of their trade, at the hero's level."""
    from realmwalker.game import companions

    sp = spec(game)
    cls, background = sp["classes"].get(npc.job, sp["default_class"])
    return companions.build(game, npc, cls, background, max(1, int(game.leader.level)), rng)


def _words(game, adv: dict) -> dict:
    """The tale's words with the ally's own: {ally}, {ally_full}, {stake}, {confidence}, their pronouns."""
    from realmwalker.game.story import words as wordsmod

    out = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
    npc = npc_of(game, adv)
    rec = adv.get("ally") or {}
    if npc is not None:
        out.update(ally=npc.first_name, ally_full=npc.name, **textgen.pronoun_values(npc.sex))
    out.update(rec.get("words") or {})
    return out


def _say(game, adv: dict, lines: list[str], rng) -> str:
    text = textgen.fill(rng.choice(list(lines)), rng, game.tables.adventures.get("words", {}), _words(game, adv))
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------- the arc
def _refresh(game, adv: dict, rec: dict) -> None:
    """What the world did to them since: dead, or freed from the villain's hall."""
    npc = npc_of(game, adv)
    if rec["state"] in LIVE and (npc is None or not npc.alive):
        rec["state"] = "fell"
    elif rec["state"] == "taken" and not npc.flags.get("kidnapped"):
        rec["state"] = "riding"  # (brought back alive from its hall)


def on_night(game, where: str) -> bool:
    """A night at camp or at the inn (story.on_night): an ally's next beat, if one is due. True when one waits."""
    from realmwalker.game.story import beats, villain

    sp = spec(game)
    if not sp or beats.pending(game) is not None:
        return False
    arc = sp["arc"]
    today = _today(game)
    story = _story()
    for adv in story.active(game):
        rec = adv.get("ally")
        if not rec:
            continue
        _refresh(game, adv, rec)
        npc = npc_of(game, adv)
        with_you = rec["state"] == "joined" and companion_of(game, adv, waiting=False) is not None
        at_home = rec["state"] == "riding" and where == "inn" and npc is not None and \
            _town_here(game) == npc.settlement
        if rec.get("told") is None and (with_you or at_home) and today - int(rec["joined"]) >= int(
                arc["confidence_after"]):
            return _offer(game, adv, "ally_confidence", where)
        if rec.get("told") is None or rec.get("crisis") is not None or today - int(rec["told"]) < int(
                arc["crisis_after"]) or int(adv["chapter"]) < 1 or _in_finale(adv):
            continue
        if not game.world.rng.child(f"ally-crisis/{adv['id']}/{today}").chance(float(arc["crisis_chance"])):
            continue
        if with_you:
            rec["crisis"] = sp["stakes"].get(rec["stake"], {}).get("crisis", "doubt")
        elif rec["state"] == "riding" and villain.lair(game, adv) is not None:
            rec["crisis"] = "taken"
        else:
            continue
        return _offer(game, adv, CRISES[rec["crisis"]], where)
    for adv in sorted(story.adventures(game.world).values(), key=lambda a: a["id"]):
        rec = adv.get("ally")
        if rec and rec.get("fate_due") and adv["hero"]["life"] == _life(game):
            rec["fate_due"] = False
            return _offer(game, adv, "ally_fate", where)
    return False


def _life(game) -> int:
    from realmwalker.game.story.forge import life_of

    return life_of(game)


def _town_here(game) -> int | None:
    s = game.world.settlement_at(game.player.x, game.player.y)
    return s.id if s is not None else None


def _in_finale(adv: dict) -> bool:
    ch = _story().chapter(adv)
    return ch is not None and any(st["kind"] == "finale" for st in ch["steps"])


def _offer(game, adv: dict, beat: str, where: str) -> bool:
    from realmwalker.game.story import beats

    if beat not in game.tables.beats:
        return False
    beats.offer(game, beat, adv=adv["id"], where=where, words=_words(game, adv))
    return True


@condition("party_room")
def _party_room(game, rec, value) -> bool:
    """A place in your company (an ally who rode with the patron, offering their oath, needs one; one already in the
    party has theirs)."""
    from realmwalker.game import companions

    adv = _story().adventures(game.world).get((rec or {}).get("adv") or "")
    have = adv is not None and companion_of(game, adv) is not None
    return (have or companions.room(game)) == bool(value)


@op("ally")
def _ally_op(game, rec, what: str, n: int = 0):
    """The ally's arc moves: told (the confidence; loyalty n), held / held_hard (the crisis weathered; loyalty n),
    breaks (they go off alone), home (they go home), taken (carried off to the villain's hall), sworn (their oath),
    farewell (sent home at the end)."""
    from realmwalker.game import companions

    adv = _story().adventures(game.world).get((rec or {}).get("adv") or "")
    ally = (adv or {}).get("ally")
    if not ally:
        return []
    c = companion_of(game, adv)
    npc = npc_of(game, adv)
    out: list[str] = []
    if what in ("told", "held", "held_hard"):
        ally["told" if what == "told" else "held"] = _today(game) if what == "told" else what
        if c is not None:
            companions.change_loyalty(c, float(n))
        elif npc is not None:
            from realmwalker.game.people import change_disposition

            change_disposition(npc, int(n))
    elif what in ("breaks", "home"):
        ally["state"] = "broke" if what == "breaks" else "home"
        if c is not None:
            out += [esc(x) for x in companions.dismiss(game, c)]
        if "ally" in adv["keys"]:
            adv["keys"].remove("ally")
        verb = "went off alone, after it" if what == "breaks" else "went home"
        _story().journal(adv, esc(f"{npc.name if npc else 'Your ally'} {verb}."), _today(game))
        out.append(f"<warn>{esc(npc.first_name if npc else 'Your ally')} will not be with you at the end.</>")
    elif what == "taken":
        from realmwalker.game.story import villain

        adv["reprisal"] = int(ally["npc"])
        name = villain.kidnap(game, adv)
        if name:
            ally["state"] = "taken"
            out.append(f"<warn>{esc(name)} is held in {esc(_words(game, adv).get('home', 'its hall'))}.</>")
    elif what == "sworn":
        ally["state"] = ally["fate"] = "sworn"
        if c is None and npc is not None and npc.alive and companions.room(game):
            c = _character(game, npc, game.world.rng.child(f"ally/{adv['id']}/sworn"))
            out += companions.enlist(game, npc, c, "pledged", values=list(
                spec(game)["stakes"].get(ally["stake"], {}).get("values", ["brave"])), stake=ally["words"]["stake"])
        elif c is not None:
            c.companion["bond"] = "pledged"
            c.companion.pop("adv", None)
            companions.change_loyalty(c, 10.0)
        if npc is not None:
            npc.flags.pop("story", None)
        _story().journal(adv, esc(f"{npc.name if npc else 'Your ally'} swore to you when it was over."),
                         _today(game))
    elif what == "farewell":
        ally["state"] = ally["fate"] = "home"
        if c is not None:
            out += [esc(x) for x in companions.dismiss(game, c)]
        if npc is not None:
            npc.flags.pop("story", None)
    game.dirty = True
    return out


# ---------------------------------------------------------------------------- in a fight
def to_battle(battle, game, advs: dict) -> list[str]:
    """A fight with a tale's foes (finale.prepare): its ally who rides with the patron is there, beside you, as a
    character of their own on Auto (not of the party). Returns what to say."""
    from realmwalker.game.story.finale import story_of
    from realmwalker.rules.combat import FOE, PARTY

    leader = next((f for f in battle.side(PARTY) if f.char is not None and f.bond is None), None)
    if leader is None:
        return []
    ids = sorted({t["adv"] for t in (story_of(f.creature) for f in battle.side(FOE) if f.creature is not None)
                  if t and t.get("adv")})
    out = []
    for aid in ids:
        adv = advs.get(aid)
        rec = (adv or {}).get("ally")
        if adv is None or adv.get("state") != "active" or not rec or "ally" not in adv["keys"]:
            continue
        _refresh(game, adv, rec)
        npc = npc_of(game, adv)
        if rec["state"] != "riding" or npc is None:
            continue
        char = _character(game, npc, game.world.rng.child(f"ally/{aid}/build"))
        f = battle.add_ally(None, leader, "story_ally", char=char)
        f.auto = True
        battle.__dict__.setdefault("story_allies", {})[f.id] = aid
        out.append(f"<good>{esc(npc.first_name)} is here, as {_pronoun(npc)} promised, armed and beside you.</>")
    return out


def _pronoun(npc) -> str:
    return textgen.pronoun_values(npc.sex)["they"]


def fighting(battle, adv: dict) -> bool:
    """The tale's ally is on this field (the finale's key "ally_fights" then adds no one)."""
    return adv["id"] in (battle.__dict__.get("story_allies") or {}).values()


def on_battle(game, result) -> None:
    """After a fight (story.on_battle): an ally who rode with the patron and fell there is dead; one who fought in
    the finale is remembered for it."""
    battle = getattr(game, "battle", None)
    if battle is None:
        return
    advs = _story().adventures(game.world)
    finale = battle.__dict__.get("finale_of")
    for fid, aid in (battle.__dict__.get("story_allies") or {}).items():
        adv = advs.get(aid)
        f = battle.fighter(fid)
        if adv is None or not adv.get("ally") or f is None:
            continue
        rec = adv["ally"]
        rec["at_finale"] = rec.get("at_finale") or finale == aid
        if f.state == "dead":
            npc = npc_of(game, adv)
            if npc is not None:
                npc.alive = False
                npc.present = False
            rec["state"] = "fell"
    if finale in advs and advs[finale].get("ally") and companion_of(game, advs[finale], waiting=False) is not None:
        advs[finale]["ally"]["at_finale"] = True


# ---------------------------------------------------------------------------- the party
def dismissed(game, c, deserted: bool) -> None:
    """A companion leaves the party (companions.dismiss): an ally sent away rides with the patron again; one who
    deserts has broken with you, and the key goes with them."""
    adv = _story().adventures(game.world).get(c.companion.get("adv") or "")
    rec = (adv or {}).get("ally")
    if not rec or rec["state"] != "joined":
        return
    if deserted:
        rec["state"] = "broke"
        if "ally" in adv["keys"]:
            adv["keys"].remove("ally")
    else:
        rec["state"] = "riding"


def died(game, c) -> None:
    """A companion is dead (companions.died): if they were a tale's ally, they fell."""
    adv = _story().adventures(game.world).get(c.companion.get("adv") or "")
    if adv is not None and adv.get("ally") and adv["ally"]["state"] in LIVE:
        adv["ally"]["state"] = "fell"


# ---------------------------------------------------------------------------- the end
def after_tale(game, adv: dict) -> None:
    """The tale is over (endings.finish): the ally's fate, and their page in the epilogue. One who lives through a
    won tale is asked at the next night's fire (the beat "ally_fate"); otherwise they go home."""
    from realmwalker.game import companions

    rec = adv.get("ally")
    sp = spec(game)
    if not rec or not sp:
        return
    _refresh(game, adv, rec)
    npc = npc_of(game, adv)
    if rec["state"] == "taken" and npc is not None:
        npc.flags.pop("kidnapped", None)  # (its hall is broken, or it has gone: they find their own way home)
        npc.present = True
        rec["state"] = "home"
    if rec["state"] == "fell":
        rec["fate"] = "fell_well" if rec.get("at_finale") else "fell"
    elif rec["state"] == "broke":
        rec["fate"] = "broke"
        if npc is not None and npc.alive:
            npc.present = True
    elif rec["state"] in ("joined", "riding") and adv["state"] == "won" and npc is not None and npc.alive:
        rec["fate_due"] = True  # (their oath or home: asked at the fire)
        return
    else:
        c = companion_of(game, adv)
        if c is not None:
            companions.dismiss(game, c)
        rec["state"] = "home"
        rec["fate"] = "home"
    rng = game.world.rng.child(f"ally-fate/{adv['id']}")
    text = _say(game, adv, sp["fates"].get(rec["fate"], sp["fates"]["home"]), rng)
    pages = adv.setdefault("epilogue", [])
    page = next((p for p in pages if p.get("about") == "ally"), None)
    if page is not None:
        page["text"] = text
    else:
        pages.insert(max(0, len(pages) - 1), {"about": "ally", "text": text})


def journal_line(game, adv: dict) -> str:
    """Who stands with you in the tale, and for what (the journal)."""
    rec = adv.get("ally")
    npc = npc_of(game, adv)
    if not rec or npc is None:
        return ""
    where = {"joined": "with you", "riding": "rides with the patron", "taken": "taken by it", "broke": "went alone",
             "home": "gone home", "fell": "dead", "sworn": "sworn to you"}.get(rec["state"], "")
    return f"{esc(npc.name)} ({where}), for {esc(rec['words']['stake'])}"
