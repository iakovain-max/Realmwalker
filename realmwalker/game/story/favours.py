"""Favours and contacts (Expansion 6 C.7, docs/ADVENTURES.md §8.10; data favours.json): what a story's end leaves the
hero besides money, kept with the character and used later.

The records are written by the situations' `favour` and `contact` ops and live in `renown.legend`:

    favours  [{"from": npc id, "weight": 1-3, "kind": word|door|goods|shelter|sword, "day", "used": bool, "used_day"?,
               "situation", "spent_on"?}]
    contacts [{"npc", "kind": informant|fence|smuggler|healer|scholar, "since", "word_day"?, "asked"?, "next_letter"?,
               "warn"?: [realm ids]}]

**A favour** is spent as a way through an obstacle of a situation the hero has taken on: the obstacle must have a
`favour` block (situations.predicaments.json: the `then` ops that passing it does, and maybe its own `kinds`, `weight`,
`say`, `note`), the favour's kind must open that kind of obstacle and be heavy enough (favours.json `kinds`, `weights`),
and its giver must reach the one who stands in the way: they live in the situation's town or the other's, share a
faction with them (a guild, a temple; never only the realm), or follow the same trade in the same realm - or they are
the very one who owes it. The conversation with the one in the way offers "fav_call" (`call_choices`); calling it in (`call_in`) passes
the obstacle with the way "favour" (goals.notify), runs its ops and marks the favour used. A shelter favour can also be
called in with its giver where the hero is wanted ("fav_hide": days in their house, the price on your head halved).

**A contact** sends word: a runner when the hero comes to their town (`on_enter_town`, once a day: what their kind has
for you, and the watch's warning first), a letter carried by the roads when the hero is away but within reach
(`daily`, every 10-20 days), and at once when a crime of yours is reported in their realm (`on_report` from
law.report). A warning means the watch has your description: for a day you know which streets they walk
(`warned`: law.watch's chance to know you is halved). A contact opens their door at night (`opens_at_night`: the game
screen's talk; law.trespass_check lets you in) and deals as their kind does: a fence buys stolen goods (law.is_fence),
a smuggler sells what the shops do not (shadows.black_market_choice), a healer sees to wounds, a scholar names strange
things (services.services_for), their services a little cheaper (`discount`: services.fee; shop prices are the
shop's); an informant tells what they have
heard ("contact_ask": the news where they live, and a trouble near that wants you). Both are listed in the journal's
People tab (`people_rows`, `person_lines`).

    owed(game)  owed_by(game, npc)  contact_of(game, npc)  fitting(game, sit, ob, npc)  call_choices(conv)
    choose(conv, choice)  on_enter_town(game, s)  daily(game)  on_report(game, realm_id)  warned(game, realm_id)
    opens_at_night(game, npc)  knock_line(game, npc)  discount(game, npc)  people_rows(game)  person_lines(game, npc)
    problems(tables)
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc

CHOICES = {"fav_call", "fav_hide", "contact_ask"}
KINDS = ("word", "door", "goods", "shelter", "sword")
CONTACT_KINDS = ("informant", "fence", "smuggler", "healer", "scholar")


def data(game) -> dict:
    return getattr(game.tables, "favours", None) or {}


def _legend(game, key: str) -> list:
    return game.renown.legend.setdefault(key, [])


def _today(game) -> int:
    return int(game.moment.total_days)


def _npc(game, nid):
    return game.world.npcs.get(int(nid)) if nid is not None else None


def _values(game, npc) -> dict:
    from realmwalker.game.people import pronouns

    p = pronouns(npc)
    w = game.world
    town = w.settlements[npc.settlement].name if 0 <= npc.settlement < len(w.settlements) else "somewhere"
    return {"giver": npc.first_name, "giver_full": npc.name, "giver_they": p["they"], "giver_them": p["them"],
            "giver_their": p["their"], "giver_they_cap": p["they"][:1].upper() + p["they"][1:], "giver_town": town}


def _say(game, lines, npc, key: str, **extra) -> str:
    """A line of favours.json's words, the same each time for the same person and moment (escaped by the caller)."""
    if not lines:
        return ""
    rng = game.world.rng.child(f"favours/{key}/{npc.id}/{_today(game)}")
    values = dict(_values(game, npc), **{k: str(v) for k, v in extra.items()})
    return textgen.tidy(textgen.fill(rng.choice(list(lines)), rng, {}, values))


# ---------------------------------------------------------------------------- the records
def owed(game) -> list[dict]:
    """The favours still owed to the hero by people alive."""
    return [f for f in _legend(game, "favours") if not f.get("used") and _alive(game, f.get("from"))]


def owed_by(game, npc) -> list[dict]:
    return [f for f in owed(game) if int(f["from"]) == npc.id]


def _alive(game, nid) -> bool:
    n = _npc(game, nid)
    return n is not None and n.alive and not n.flags.get("gone")


def contacts(game) -> list[tuple[dict, object]]:
    """(record, person) for every contact alive and still in their town."""
    out = []
    for rec in _legend(game, "contacts"):
        n = _npc(game, rec.get("npc"))
        if n is not None and n.alive and not n.flags.get("gone"):
            out.append((rec, n))
    return out


def contact_of(game, npc) -> dict | None:
    return next((rec for rec, n in contacts(game) if n.id == npc.id), None)


def _kind_name(game, kind: str) -> str:
    return (data(game).get("kinds", {}).get(kind) or {}).get("name", kind)


# ---------------------------------------------------------------------------- favours as ways through
def need(game, ob: dict) -> tuple[tuple, int]:
    """The kinds of favour that open this obstacle and the weight it needs ((), 0 when no favour opens it)."""
    blk = ob.get("favour")
    if not blk:
        return (), 0
    d = data(game)
    kinds = tuple(blk.get("kinds") or [k for k, v in d.get("kinds", {}).items() if ob.get("kind") in v["opens"]])
    weights = d.get("weights", {})
    return kinds, int(blk.get("weight") or weights.get(ob.get("kind"), weights.get("_default", 1)))


def reaches(game, fav: dict, sit: dict, npc) -> bool:
    """Whether the one who owes the favour reaches this person: the same person, the situation's town or theirs, a
    faction they share (not only the realm), or the same trade in the same realm."""
    giver = _npc(game, fav.get("from"))
    if giver is None or not giver.alive:
        return False
    if giver.id == npc.id or giver.settlement in (sit.get("town"), npc.settlement):
        return True
    if giver.job == npc.job:
        a, b = _realm_of(game, giver), _realm_of(game, npc)
        if a is not None and b is not None and a.id == b.id:
            return True
    from realmwalker.game.people import npc_factions
    from realmwalker.world import factions as fx

    mine = {f.id for f in npc_factions(game, giver) if f.kind not in fx.REALM_KINDS}
    return bool(mine & {f.id for f in npc_factions(game, npc) if f.kind not in fx.REALM_KINDS})


def fitting(game, sit: dict, ob: dict, npc) -> list[dict]:
    """The favours that would open this obstacle with this person, the lightest first."""
    kinds, weight = need(game, ob)
    if not kinds:
        return []
    out = [f for f in owed(game) if f["kind"] in kinds and int(f["weight"]) >= weight and reaches(game, f, sit, npc)]
    return sorted(out, key=lambda f: (int(f["weight"]), int(f.get("day", 0))))


def _index(game, fav: dict) -> int:
    return next(i for i, f in enumerate(_legend(game, "favours")) if f is fav)


def call_choices(conv) -> list:
    """What calling in a favour offers in this conversation: a way through an obstacle this person stands in, hiding
    with the one who owes you shelter, and an informant's news."""
    from realmwalker.game.dialogue import Choice
    from realmwalker.game.story import situations

    game, npc = conv.game, conv.npc
    out = []
    for sit in situations.live_in(game, npc.settlement):
        if sit["state"] != "taken":
            continue
        role = situations._role_of(sit, npc)
        if role is None:
            continue
        for ob in sit["obstacles"]:
            if ob["state"] != "standing" or ob.get("who") != role:
                continue
            favs = fitting(game, sit, ob, npc)
            if not favs:
                continue
            fav = favs[0]
            giver = _npc(game, fav["from"])
            if giver.id == npc.id:
                label = _say(game, data(game).get("own") or ["You said you owed me. I am asking now."], giver, "own")
            else:
                label = _say(game, data(game).get("call"), giver, f"call/{ob['id']}")
            label = f"{label} (call in {giver.first_name}'s favour: {_kind_name(game, fav['kind'])})"
            out.append(Choice("fav_call", label, data={"sit": sit["id"], "ob": ob["id"], "fav": _index(game, fav)}))
    hide = _hide_offer(game, npc)
    if hide is not None:
        fav, realm = hide
        label = _say(game, data(game)["hide"]["label"], npc, "hide")
        out.append(Choice("fav_hide", f"{label} (call in the favour)", data={"fav": _index(game, fav)}))
    rec = contact_of(game, npc)
    if rec is not None and rec["kind"] == "informant":
        spec = data(game)["contacts"]["informant"]
        out.append(Choice("contact_ask", _say(game, spec.get("ask"), npc, "ask"), rec.get("asked") != _today(game),
                          "they have told you all they know today"))
    return out


def choose(conv, choice) -> None:
    game = conv.game
    if choice.id == "fav_call":
        from realmwalker.game.story import situations

        sit = situations.records(game.world).get(choice.data.get("sit"))
        favs = _legend(game, "favours")
        i = int(choice.data.get("fav", -1))
        if sit is None or sit["state"] != "taken" or not 0 <= i < len(favs):
            return
        ob = next((o for o in sit["obstacles"] if o["id"] == choice.data.get("ob")), None)
        if ob is not None and ob["state"] == "standing" and not favs[i].get("used") and _alive(game, favs[i]["from"]):
            conv.you_say(esc(choice.label.rsplit(" (call in", 1)[0]))
            call_in(conv, sit, ob, favs[i])
    elif choice.id == "fav_hide":
        favs = _legend(game, "favours")
        i = int(choice.data.get("fav", -1))
        if 0 <= i < len(favs):
            hide(conv, favs[i])
    elif choice.id == "contact_ask":
        rec = contact_of(game, conv.npc)
        if rec is not None:
            ask(conv, rec)


def call_in(conv, sit: dict, ob: dict, fav: dict) -> None:
    """A favour spent: the obstacle passed by the way "favour", its ops run, the favour marked used."""
    from realmwalker.game.story import goals, situations

    game = conv.game
    giver = _npc(game, fav["from"])
    if not _alive(game, fav["from"]) or fav.get("used"):
        return
    blk = ob.get("favour") or {}
    said = situations._fill(game, sit, blk["say"], f"favour/{ob['id']}") if blk.get("say") else \
        _say(game, data(game).get("answer"), giver, f"answer/{ob['id']}")
    conv.npc_says(esc(said))
    fav["used"], fav["used_day"] = True, _today(game)
    fav["spent_on"] = sit["id"]
    ob["state"] = "passed"
    ob["way"] = "favour"
    sit["used"].append(f"{ob['id']}/favour")
    for o in blk.get("then", []):
        for line in situations._op(game, sit, o):
            conv.note(line)
    note = situations._fill(game, sit, blk["note"], f"favour_note/{ob['id']}") if blk.get("note") else \
        f"{giver.first_name}'s name opened the way with {conv.npc.first_name}."
    sit["journal"].append(note)
    conv.note(f"<info>{esc(_say(game, data(game).get('spent'), giver, 'spent'))}</>")
    if giver.id != conv.npc.id:
        giver.memory.append(f"you called in the favour {giver.first_name} owed you, with {conv.npc.first_name}")
    game.dirty = True
    goals.notify(game, "talk", "favour", npc=conv.npc)


def _realm_of(game, npc):
    from realmwalker.game.law_talk import realm_of_npc

    return realm_of_npc(game, npc)


def _hide_offer(game, npc):
    """(favour, realm) when this person owes the hero shelter and the hero is wanted where they live."""
    favs = [f for f in owed_by(game, npc) if f["kind"] == "shelter"]
    if not favs:
        return None
    realm = _realm_of(game, npc)
    if realm is None or game.renown.bounties.get(realm.id, 0) <= 0:
        return None
    return favs[0], realm


def hide(conv, fav: dict) -> None:
    """Days hidden in the giver's house: fed, out of sight, and the watch lose half their interest."""
    game, npc = conv.game, conv.npc
    offer = _hide_offer(game, npc)
    if offer is None or offer[0] is not fav:
        return
    realm = offer[1]
    spec = data(game)["hide"]
    conv.you_say(esc(_say(game, spec["label"], npc, "hide")))
    conv.npc_says(esc(_say(game, spec["say"], npc, "hide_say")))
    fav["used"], fav["used_day"] = True, _today(game)
    fav["spent_on"] = "hide"
    days = int(spec["days"])
    game.confined = {"kind": "safehouse"}  # fed and under a roof, going nowhere
    try:
        for _ in range(days):
            game.pass_time(16 * 60, "rest")
            game.pass_time(8 * 60, "sleep")
            if game.over is not None:
                break
    finally:
        game.confined = None
    game.renown.bounties[realm.id] = int(game.renown.bounties.get(realm.id, 0) * float(spec["bounty_left"]))
    game.renown.flags["lay_low_day"] = game.moment.total_days
    game.dirty = True
    conv.note(f"<good>{esc(_say(game, spec['after'], npc, 'hide_after', days=days, realm=realm.name))}</>")
    conv.ended = True


def ask(conv, rec: dict) -> None:
    """An informant's news: what has reached their town, and a trouble near that wants the hero."""
    from realmwalker.game import news

    game, npc = conv.game, conv.npc
    spec = data(game)["contacts"]["informant"]
    rec["asked"] = _today(game)
    conv.you_say(esc(conv_label(game, npc, spec)))
    conv.npc_says(esc(_say(game, spec.get("says"), npc, "says")))
    s = game.world.settlements[npc.settlement]
    heard = news.hear(game, count=2, rng=game.world.rng.child(f"favours/news/{npc.id}/{_today(game)}"), x=s.x, y=s.y)
    for line in heard:
        conv.note(line)
    trouble = _trouble_line(game, npc, spec)
    if trouble:
        conv.npc_says(esc(trouble))
    elif not heard:
        conv.npc_says(esc(_say(game, spec.get("nothing"), npc, "nothing")))


def conv_label(game, npc, spec) -> str:
    return _say(game, spec.get("ask"), npc, "ask")


def _trouble_line(game, npc, spec) -> str:
    """A trouble near that the hero has not met: its asker and town, in the informant's words."""
    from realmwalker.game.story import goals, situations

    near = [s for s in goals.live(game) if s["state"] == "latent" and goals.within_reach(game, s)
            and s.get("town") is not None]
    if not near or not spec.get("trouble"):
        return ""
    w = game.world
    me = w.settlements[npc.settlement]
    sit = min(near, key=lambda s: (max(abs(w.settlements[s["town"]].x - me.x), abs(w.settlements[s["town"]].y - me.y)),
                                   s["id"]))
    asker = situations.asker(game, sit)
    if asker is None or not asker.alive:
        return ""
    vals = situations._values(game, sit)
    role = situations.spec_of(game, sit).get("asks", "asker")
    return _say(game, spec["trouble"], npc, f"trouble/{sit['id']}", asker=vals.get(role, asker.first_name),
                asker_them=vals.get(f"{role}_them", "them"), town=vals["town"])


# ---------------------------------------------------------------------------- contacts send word
def warned(game, realm_id: int) -> bool:
    """A contact's warning holds: the hero knows which streets the watch of this realm walk."""
    until = (game.renown.flags.get("warned") or {}).get(str(realm_id))
    return until is not None and game.world.time < int(until)


def _warn(game, realm_id: int) -> None:
    hours = int(data(game).get("warned_hours", 24))
    game.renown.flags.setdefault("warned", {})[str(realm_id)] = int(game.world.time + hours * 60)


def _wanted_in(game, realm) -> bool:
    return realm is not None and (game.renown.bounties.get(realm.id, 0) > 0 or any(
        r.get("disguised") and r.get("reported") and not r.get("settled") and r["realm"] == realm.id
        for r in game.renown.crimes))


def _kind_has_word(game, kind: str) -> bool:
    """Whether a contact of this kind has something for the hero now (an informant always does)."""
    from realmwalker.rules.inventory import distinct_packs

    packs = distinct_packs(game.party)
    if kind == "fence":
        return any("stolen" in it.tags for m in packs for it in m.inventory)
    if kind == "healer":
        return any(c.alive and (c.wounds or c.hp < c.max_hp) for c in game.party)
    if kind == "scholar":
        return any(it.magic and not it.magic.get("identified") for m in packs for it in m.inventory)
    return True


def on_enter_town(game, s) -> None:
    """Into a contact's town: a runner with their word (once a day), the watch's warning first."""
    d = data(game)
    if not d:
        return
    today = _today(game)
    for rec, n in contacts(game):
        if n.settlement != s.id or rec.get("word_day") == today:
            continue
        realm = _realm_of(game, n)
        if _wanted_in(game, realm):
            rec["word_day"] = today
            rec.pop("warn", None)
            _warn(game, realm.id)
            game.say(f"<warn>{esc(_say(game, d['warn']['runner'], n, 'warn_runner', realm=realm.name))}</>", "warn")
            continue
        spec = d["contacts"].get(rec["kind"]) or {}
        if not _kind_has_word(game, rec["kind"]):
            continue
        rec["word_day"] = today
        game.say(f"<info>{esc(_say(game, spec.get('runner'), n, 'runner'))}</>", "info")
        if rec["kind"] == "informant":
            trouble = _trouble_line(game, n, spec)
            if trouble:
                game.say(esc(trouble), "info")


def on_report(game, realm_id: int) -> None:
    """A crime of the hero's has reached the watch of this realm: contacts there will warn them (a runner now if the
    hero is in their town, else a letter the next day)."""
    from realmwalker.game import law

    here = law.settlement_here(game) if game.in_local else None
    for rec, n in contacts(game):
        realm = _realm_of(game, n)
        if realm is None or realm.id != realm_id:
            continue
        if here is not None and here.id == n.settlement:
            rec["word_day"] = _today(game)
            _warn(game, realm_id)
            game.say(f"<warn>{esc(_say(game, data(game)['warn']['runner'], n, 'warn_runner', realm=realm.name))}</>",
                     "warn")
        elif realm_id not in rec.setdefault("warn", []):
            rec["warn"].append(realm_id)


def daily(game) -> None:
    """Letters: a warning owed is written first; else, every 10-20 days, word from a contact within reach whose town
    the hero is not in."""
    d = data(game)
    if not d:
        return
    today = _today(game)
    p = game.player
    w = game.world
    gap = d["letters"]["gap"]
    reach = int(d["letters"]["reach"])
    from realmwalker.game import law

    here = law.settlement_here(game) if game.in_local else None
    for rec, n in contacts(game):
        s = w.settlements[n.settlement]
        if here is not None and here.id == s.id:
            continue
        if rec.get("warn"):
            from realmwalker.world import factions as fx

            realm = fx.realm_of_settlement(w, s)
            rec.pop("warn")
            if realm is not None and _wanted_in(game, realm):
                _warn(game, realm.id)  # (the warning holds for the hours after it is read)
                game.say(f"<warn>{esc(_say(game, d['warn']['letter'], n, 'warn_letter', realm=realm.name))}</>",
                         "warn")
                rec["next_letter"] = today + int(gap[0])
                continue
        if max(abs(s.x - p.x), abs(s.y - p.y)) > reach:
            continue
        nxt = rec.get("next_letter")
        if nxt is None:
            rng = w.rng.child(f"favours/letter/{n.id}/{today}")
            rec["next_letter"] = today + rng.randint(int(gap[0]), int(gap[1]))
            continue
        if today < int(nxt) or not _kind_has_word(game, rec["kind"]):
            continue
        rng = w.rng.child(f"favours/letter/{n.id}/{today}")
        rec["next_letter"] = today + rng.randint(int(gap[0]), int(gap[1]))
        spec = d["contacts"].get(rec["kind"]) or {}
        game.say(f"<info>{esc(_say(game, spec.get('letter'), n, 'letter'))}</>", "info")
        if rec["kind"] == "informant":
            from realmwalker.game import news

            for line in news.hear(game, count=1, rng=rng, x=s.x, y=s.y):
                game.say(line, "info")
            trouble = _trouble_line(game, n, spec)
            if trouble:
                game.say(esc(trouble), "info")


# ---------------------------------------------------------------------------- dealing at night
def opens_at_night(game, npc) -> bool:
    """A contact lets the hero in at any hour."""
    return contact_of(game, npc) is not None


def knock_line(game, npc) -> str:
    return esc(_say(game, data(game).get("knock"), npc, "knock"))


def vouch_line(game, npc) -> str:
    return esc(_say(game, data(game).get("vouch"), npc, "vouch"))


def is_kind(game, npc, kind: str) -> bool:
    rec = contact_of(game, npc)
    return rec is not None and rec["kind"] == kind


def discount(game, npc) -> float:
    """A contact's prices for the hero (services.fee): a friend's, a little under the rest."""
    return float(data(game).get("discount", 1.0)) if contact_of(game, npc) is not None else 1.0


# ---------------------------------------------------------------------------- the journal
def people_rows(game) -> list:
    """The people who owe the hero a favour or are their contacts, for the People tab's first group."""
    seen, out = set(), []
    for f in owed(game):
        n = _npc(game, f["from"])
        if n.id not in seen:
            seen.add(n.id)
            out.append(n)
    for _, n in contacts(game):
        if n.id not in seen:
            seen.add(n.id)
            out.append(n)
    return out


def person_lines(game, npc) -> list[str]:
    """What the People tab says of a favour owed or a contact."""
    out = []
    for f in owed_by(game, npc):
        weight = ("a small", "a fair", "a great")[max(1, min(3, int(f["weight"]))) - 1]
        out.append(f"<good>Owes you {weight} favour:</> {esc(_kind_name(game, f['kind']))} "
                   f"<dim>(since day {int(f.get('day', 0)) + 1})</>")
    rec = contact_of(game, npc)
    if rec is not None:
        spec = data(game).get("contacts", {}).get(rec["kind"]) or {}
        out.append(f"<good>Your contact:</> {esc(rec['kind'])}, {esc(spec.get('name', ''))}. "
                   f"<dim>They send word, open their door at night and warn you of the watch.</>")
    return out


# ---------------------------------------------------------------------------- the start-up check
def problems(tables) -> list[str]:
    d = getattr(tables, "favours", None) or {}
    if not d:
        return []
    out = []
    for k in KINDS:
        if k not in d.get("kinds", {}):
            out.append(f"favours.json: kinds has no '{k}'.")
    for k in CONTACT_KINDS:
        if k not in d.get("contacts", {}):
            out.append(f"favours.json: contacts has no '{k}'.")
    inf = d.get("contacts", {}).get("informant") or {}
    for key in ("ask", "says", "trouble", "nothing"):
        if not inf.get(key):
            out.append(f"favours.json: contacts.informant needs '{key}'.")
    from realmwalker.game.story import situations

    preds = situations.predicaments(tables)
    for pid, p in preds.items():
        roles = set(p.get("roles", {}))
        for ob in p.get("obstacles", []):
            blk = ob.get("favour")
            if not blk:
                continue
            where = f"situations: {pid}.{ob.get('id')}.favour"
            for k in blk.get("kinds", []):
                if k not in KINDS:
                    out.append(f"{where}: '{k}' is not a kind of favour.")
            if not blk.get("kinds") and not any(ob.get("kind") in v["opens"] for v in d.get("kinds", {}).values()):
                out.append(f"{where}: no kind of favour opens a '{ob.get('kind')}'.")
            for o in blk.get("then", []):
                out += situations._op_problem(o, roles, where)
    for pid, p in preds.items():
        for e in p.get("endings", []) + [p.get("lapse") or {}]:
            for o in e.get("ops", []):
                if o and o[0] == "favour" and (len(o) < 3 or o[2] not in KINDS):
                    out.append(f"situations: {pid}.{e.get('id', 'lapse')}: favour of an unknown kind {o[2:3]}.")
                if o and o[0] == "contact" and (len(o) < 3 or o[2] not in CONTACT_KINDS):
                    out.append(f"situations: {pid}.{e.get('id', 'lapse')}: contact of an unknown kind {o[2:3]}.")
    return out
