"""Patrons' hidden motives and the innocents' fates (Expansion 6 F.3, docs/ADVENTURES.md §5.3).

The patron (the one who asks you and pays) may have a reason they did not give: a debt the villain's death cancels,
a guilt (it began with them), a gain (they bought what the trouble emptied). It is decided once, the first day the
tale is active (adventures.cast.json "patrons" motives, by weight; most have none), and kept in `adv["patron"]`
{motive, trust, gifts, gift_ch, told, answer}; a patron who serves the villain has the motive "traitor" (set by
story/traitors.py, the once-in-a-life betrayal).

Trust comes before it is broken (Ravenloft): back in the patron's town, at its inn, the patron comes down with a
kindness once a chapter (`gifts` at most, from `gift_after` days into the tale: the beat "patron_gift"); each one,
taken or refused, is a mark of `trust`, and a traitor patron does not betray you before `betray_at` of them (they
falter). Once the second chapter has begun and they have been kind to you, a patron with a hidden motive tells it
at their town's inn (the beat "patron_motive"): you let it lie, are paid to keep it quiet, or tell the town. The
epilogue's patron page then says it (`after_tale`).

The innocent (the one who suffers if you fail: a village, a child, an heir) has a fate when the tale ends:
spared (won, and nothing more done to them), scarred (won, but reprisals, a taking, a betrayal on the way), lost (the
tale failed, or the person is dead). It is `adv["innocent"]` {fate} and a page of the epilogue, and the companions
hear it (`companions.react`: innocent_saved, innocent_lost).

    decide(game, adv)   daily(game)   on_night(game, where)   after_tale(game, adv)   journal_line(game, adv)
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story.beats import op

MOTIVES_TOLD = ("debt", "guilt", "gain")
BEATS = ("patron_gift", "patron_motive")


def spec(game) -> dict:
    return game.tables.adventures.get("patrons") or {}


def _story():
    from realmwalker.game import story

    return story


def _today(game) -> int:
    return int(game.moment.total_days)


def npc(game, adv: dict):
    """The patron as a living townsperson, or None."""
    from realmwalker.game.story import cast

    p = cast.person(game.world, adv["cast"].get("patron"))
    return p if p is not None and hasattr(p, "settlement") and getattr(p, "alive", False) else None


def record(adv: dict) -> dict | None:
    return adv.get("patron") or None


def trust(adv: dict) -> int:
    return int((adv.get("patron") or {}).get("trust", 0))


# ---------------------------------------------------------------------------- the motive
def decide(game, adv: dict) -> None:
    """The patron's hidden motive, decided once (the first day the tale is active)."""
    if "patron" in adv:
        return
    sp = spec(game)
    if not sp or not adv["cast"].get("patron"):
        adv["patron"] = None
        return
    rng = game.world.rng.child(f"patron/{adv['id']}")
    motives = sorted(m for m, v in sp["motives"].items() if int(v["weight"]) > 0)
    motive = rng.weighted(motives, [float(sp["motives"][m]["weight"]) for m in motives]) if motives else "plain"
    adv["patron"] = {"motive": motive, "trust": 0, "gifts": 0, "gift_ch": -1, "told": None, "answer": None,
                     "made": _today(game)}


def daily(game) -> None:
    for adv in _story().active(game):
        decide(game, adv)


def _words(game, adv: dict) -> dict:
    """The tale's words with the patron's: {patron}, {gift}, {motive_told}, {person} and the patron's pronouns."""
    from realmwalker.game.story import words as wordsmod

    out = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
    p = npc(game, adv)
    sex = getattr(p, "sex", "") if p is not None else ""
    pro = textgen.pronoun_values(sex)
    pro["es"] = "es" if pro["s"] else ""
    pro["theirs"] = {"he": "his", "she": "hers"}.get(pro["they"], "theirs")
    out.update(pro)
    out["person"] = {"male": "man", "female": "woman"}.get(sex, "person")
    if p is not None:
        out["patron"] = p.name
    rec = adv.get("patron") or {}
    sp = spec(game)
    rng = game.world.rng.child(f"patron-words/{adv['id']}")
    tables = game.tables.adventures.get("words", {})
    if sp.get("gifts"):
        out["gift"] = textgen.fill(rng.choice(sp["gifts"]), rng, tables, out)
    told = sp.get("motives", {}).get(rec.get("motive", ""), {}).get("told")
    if told:
        out["motive_told"] = textgen.fill(rng.child("told").choice(told), rng, tables, out)
    return out


def _say(game, adv: dict, lines, rng) -> str:
    text = textgen.fill(rng.choice(list(lines)), rng, game.tables.adventures.get("words", {}), _words(game, adv))
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------- at their inn
def on_night(game, where: str) -> bool:
    """A night at the inn of the patron's own town (story.on_night): their kindness, once a chapter; once the second
    chapter has begun and they have been kind, the motive they did not tell. True when a beat waits."""
    from realmwalker.game.story import beats

    sp = spec(game)
    if not sp or where != "inn" or beats.pending(game) is not None:
        return False
    here = game.world.settlement_at(game.player.x, game.player.y)
    if here is None:
        return False
    today = _today(game)
    for adv in _story().active(game):
        rec = record(adv)
        p = npc(game, adv)
        if rec is None or p is None or p.settlement != here.id or p.flags.get("gone") or \
                (adv.get("traitor") or {}).get("state", "hidden") not in ("hidden", "yielded", "faltered", "never"):
            continue  # (one who sold you, fled or was sent away comes down to nobody's table)
        ch = int(adv["chapter"])
        t = sp["trust"]
        if int(rec["gifts"]) < int(t["gifts"]) and ch > int(rec["gift_ch"]) and \
                today - int(rec["made"]) >= int(t["gift_after"]) and not _in_finale(adv):
            rec["gift_ch"] = ch
            return _offer(game, adv, "patron_gift", where)
        if rec["motive"] in MOTIVES_TOLD and rec.get("told") is None and ch >= 1 and int(rec["trust"]) >= 1:
            rec["told"] = today
            return _offer(game, adv, "patron_motive", where)
    return False


def _in_finale(adv: dict) -> bool:
    ch = _story().chapter(adv)
    return ch is not None and any(st["kind"] == "finale" for st in ch["steps"])


def _offer(game, adv: dict, beat: str, where: str) -> bool:
    from realmwalker.game.story import beats

    if beat not in game.tables.beats:
        return False
    beats.offer(game, beat, adv=adv["id"], where=where, words=_words(game, adv))
    return True


def _coin(game, adv: dict) -> int:
    tier = max(1, min(4, int(adv.get("tier", 1))))
    return int(spec(game)["gift_coin"][tier - 1])


@op("patron")
def _patron_op(game, ctx, what: str):
    """The patron's story: gift (their kindness taken: coin, and trust), refuse (refused: trust all the same),
    forgive / paid / expose (what you did with the motive they told)."""
    from realmwalker.game.people import change_disposition
    from realmwalker.rules.items import money_text

    adv = _story().adventures(game.world).get((ctx or {}).get("adv") or "")
    rec = record(adv) if adv else None
    if rec is None:
        return []
    p = npc(game, adv)
    out: list[str] = []
    if what in ("gift", "refuse"):
        rec["trust"] = int(rec["trust"]) + 1
        rec["gifts"] = int(rec["gifts"]) + 1
        if what == "gift":
            coin = _coin(game, adv)
            game.leader.money += coin
            out.append(f"<loot>{money_text(coin)}.</>")
        elif p is not None:
            change_disposition(p, 5)
        return out
    if what in ("forgive", "paid", "expose"):
        rec["answer"] = {"forgive": "forgave", "paid": "paid", "expose": "exposed"}[what]
        if p is not None:
            change_disposition(p, {"forgive": 10, "paid": -10, "expose": -40}[what])
            p.remember({"forgive": "the traveller kept my secret", "paid": "paid the traveller to keep quiet",
                        "expose": "the traveller told the town what I did"}[what])
        if what == "paid":
            coin = _coin(game, adv) * 2
            game.leader.money += coin
            out.append(f"<loot>{money_text(coin)}.</>")
        if what == "expose" and p is not None:
            from realmwalker.game.people import npcs_in

            for n in npcs_in(game.world, p.settlement):
                if n.alive and n.id != p.id:
                    n.remember(f"heard from the traveller what {p.first_name} did")
        line = _say(game, adv, spec(game)["answers"][rec["answer"]], game.world.rng.child(f"patron-ans/{adv['id']}"))
        _story().journal(adv, line, _today(game))
        out.append(f"<dim>{esc(line)}</>")
        return out
    return out


# ---------------------------------------------------------------------------- the end
def after_tale(game, adv: dict) -> None:
    """The tale is over (endings.finish): the patron's page says what they did not tell, once it came out; the
    innocent's fate and page."""
    rec = record(adv)
    sp = spec(game)
    pages = adv.setdefault("epilogue", [])
    if rec and sp and rec.get("told") is not None and rec["motive"] in MOTIVES_TOLD:
        lines = sp["motives"][rec["motive"]].get("page")
        if lines:
            text = _say(game, adv, lines, game.world.rng.child(f"patron-page/{adv['id']}"))
            _put_page(pages, "patron", text)
    _innocent(game, adv, pages)


def _put_page(pages: list, about: str, text: str) -> None:
    page = next((p for p in pages if p.get("about") == about), None)
    if page is not None:
        page["text"] = text
    else:
        pages.insert(max(0, len(pages) - 1), {"about": about, "text": text})


def innocent_fate(game, adv: dict) -> str | None:
    """How it ended for the one who suffers if you fail: spared, scarred or lost (None: the tale has no innocent)."""
    from realmwalker.game.story import cast

    entry = adv["cast"].get("innocent")
    if not entry:
        return None
    who = cast.person(game.world, entry)
    if adv["state"] != "won" or (who is not None and not getattr(who, "alive", True)):
        return "lost"
    if "settlement" in entry and "npc" not in entry and "job" not in entry:
        s = game.world.settlements[int(entry["settlement"])] if int(entry["settlement"]) < len(
            game.world.settlements) else None
        if s is None or getattr(s, "population", 1) <= 0:
            return "lost"
    hurt = adv.get("reprisal") or "betrayed" in adv["flags"] or (adv.get("traitor") or {}).get("state") == "turned" \
        or any(st.get("kidnap") and st["state"] == "failed" for ch in adv["chapters"] for st in ch["steps"])
    return "scarred" if hurt else "spared"


def _innocent(game, adv: dict, pages: list) -> None:
    sp = (game.tables.adventures.get("innocents") or {}).get("fates") or {}
    fate = innocent_fate(game, adv)
    if fate is None or fate not in sp:
        return
    from realmwalker.game.story import cast

    entry = adv["cast"]["innocent"]
    kind = "person" if cast.person(game.world, entry) is not None else "place"
    adv["innocent"] = {"fate": fate}
    words = _words(game, adv)
    words["innocent"] = cast.describe(game, adv, "innocent")
    rng = game.world.rng.child(f"innocent/{adv['id']}")
    text = textgen.fill(rng.choice(sp[fate][kind]), rng, game.tables.adventures.get("words", {}), words)
    _put_page(pages, "innocent", text[:1].upper() + text[1:])
    from realmwalker.game.companions import react

    react(game, "innocent_lost" if fate == "lost" else "innocent_saved")


def journal_line(game, adv: dict) -> str:
    """What the patron did not tell you, once they have (the journal)."""
    rec = record(adv)
    if not rec or rec.get("told") is None or rec["motive"] not in MOTIVES_TOLD:
        return ""
    words = {"debt": "a debt the villain's death cancels", "guilt": "it began with them",
             "gain": "they gain by it"}[rec["motive"]]
    p = npc(game, adv)
    name = p.name if p is not None else "the patron"
    answer = {"forgave": ", and you let it lie", "paid": ", and paid you to keep quiet",
              "exposed": ", and you told the town"}.get(rec.get("answer") or "", "")
    return f"{esc(name)}: {words}{answer}"
