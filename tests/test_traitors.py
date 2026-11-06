"""The cast's secrets (Expansion 6 F.3, docs/ADVENTURES.md §5.3, §5.6): a patron's hidden motive, told once they
have been kind to you; a traitor among the cast (the patron at most once in a hero's life, the ally, a hired
companion) with at least two tells, caught (they confess and feed the villain false word; flee; are sent away;
fight) or missed (the betrayal the night before, the twist in the finale's fight, one who turned standing beside the
villain); the innocent's fate; the step kinds deliver and infiltrate."""

import pytest

from realmwalker.game import companions, quests, story
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.story import beats, check, deeds, endings, patrons, traitors
from realmwalker.rules.combat import FOE, PARTY
from tests.test_finale_arenas import _den, _fight  # noqa: F401
from tests.test_risen_outlaw import _open_chapter, _play, _step, _tale, made, tables  # noqa: F401
from tests.test_situations import talk

pytestmark = pytest.mark.story


def _whole(text: str) -> bool:
    return "{" not in text and "}" not in text


def _patron(game, adv):
    prepare_town(game, game.world.settlements[adv["places"]["town"]["settlement"]])
    p = patrons.npc(game, adv)
    if p is None:
        pytest.skip("this tale's patron is not a townsperson")
    return p


def _hire(game, adv):
    """A hired companion from the tale's town (no tale's ally)."""
    sid = adv["places"]["town"]["settlement"]
    prepare_town(game, game.world.settlements[sid])
    folk = [n for n in sorted(npcs_in(game.world, sid), key=lambda n: n.id)
            if n.alive and not n.flags.get("story") and n.job not in ("child", "guard")]
    npc = next((n for n in folk if n.flags.get("recruit")), folk[0])
    npc.flags.setdefault("recruit", sorted(companions.data(game)["archetypes"])[0])
    c = companions.make_character(game, npc, companions.terms(game, npc))
    game.party.append(c)
    return c


def _with_traitor(game, adv, monkeypatch, role, reason="kin"):
    tr = game.tables.adventures["traitors"]
    monkeypatch.setitem(tr["chance"], adv["blueprint"], 1.0)
    monkeypatch.setitem(tr, "from", {role: 1})
    monkeypatch.setitem(tr, "reasons", {reason: tr["reasons"][reason]})
    adv.pop("traitor", None)
    patrons.decide(game, adv)
    adv["patron"]["motive"] = "plain"
    if int(adv["chapter"]) < 1:
        adv["chapter"] = 1
    traitors.decide(game, adv)
    rec = adv["traitor"]
    assert rec is not None and rec["role"] == role
    return rec


def _tell(game, adv, where="camp"):
    rec = adv["traitor"]
    rec["made"] = rec["last"] = int(game.moment.total_days) - 10
    old = game.tables.adventures["traitors"]["clock"]["event_chance"]
    game.tables.adventures["traitors"]["clock"]["event_chance"] = 1.0
    try:
        assert traitors.on_night(game, where, morning=True)
    finally:
        game.tables.adventures["traitors"]["clock"]["event_chance"] = old
    pending = beats.pending(game)
    assert pending["beat"] == "traitor_tell"
    return pending


def test_the_cast_data_passes_the_start_up_check(tables):
    assert [p for p in check.problems(tables) if "cast" in p or "traitor" in p or "patron" in p] == []
    for b in patrons.BEATS + traitors.BEATS + ("story_infiltrate",):
        assert b in tables.beats


def test_the_patron_is_kind_first_and_tells_their_motive_later(made, tables):
    game, adv, t = _tale(made, tables, "risen")
    p = _patron(game, adv)
    patrons.decide(game, adv)
    adv["patron"]["motive"] = "guilt"
    adv["patron"]["made"] = int(game.moment.total_days) - 5
    game.player.x, game.player.y = game.world.settlements[p.settlement].x, game.world.settlements[p.settlement].y
    money = game.leader.money
    assert patrons.on_night(game, "inn")
    rec = beats.pending(game)
    assert rec["beat"] == "patron_gift"
    assert all(_whole(x) for x in beats.pages(game, rec))
    _play(game, 0)
    assert game.leader.money > money and adv["patron"]["trust"] == 1
    assert not patrons.on_night(game, "inn"), "a kindness once a chapter, and the motive waits for the second"
    adv["chapter"] = 1
    adv["chapters"][1]["state"] = "open"
    assert patrons.on_night(game, "inn")
    rec = beats.pending(game)
    if rec["beat"] == "patron_gift":
        _play(game, 1)
        assert patrons.on_night(game, "inn")
        rec = beats.pending(game)
    assert rec["beat"] == "patron_motive"
    pages = beats.pages(game, rec)
    assert all(_whole(x) for x in pages) and len(pages[1]) > 40
    _play(game, 0)
    assert adv["patron"]["answer"] == "forgave"
    assert "began with them" in patrons.journal_line(game, adv)
    adv["state"] = "won"
    patrons.after_tale(game, adv)
    page = next(x for x in adv["epilogue"] if x["about"] == "patron")
    assert _whole(page["text"]) and p.first_name in page["text"] or p.name.split()[0] in page["text"]


def test_a_patron_betrays_at_most_once_in_a_heros_life(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    _patron(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "patron")
    assert adv["patron"]["motive"] == "traitor"
    assert game.renown.flags["patron_betrayed"] == adv["id"]
    other = dict(adv, id="A99", patron={"motive": "plain", "trust": 0, "gifts": 0, "gift_ch": -1, "told": None,
                                        "answer": None, "made": 0})
    other.pop("traitor")
    assert not [r for r, _ in traitors._candidates(game, other) if r == "patron"], "never twice in one life"
    assert rec["why"] and _whole(rec["why"])


def test_two_tells_then_a_confession_feeds_it_false_word(made, tables, monkeypatch):
    monkeypatch.setattr("realmwalker.game.camp.check", lambda game, skill, dc, **kw: (True, f"{skill}: success"))
    game, adv, band = _den(made, tables, "beast", arena="")
    adv["chapter"] = 1
    c = _hire(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "companion", "paid")
    first = _tell(game, adv)
    texts = beats.pages(game, first)
    assert all(_whole(x) for x in texts) and rec["first"] in " ".join(texts)
    opts = beats.choices(game, first)
    assert opts[0]["ok"] and not any(o["ok"] for o in opts[1:]), "one tell is not enough to act on"
    _play(game, 0)
    second = _tell(game, adv)
    opts = beats.choices(game, second)
    assert all(o["ok"] for o in opts), "the second tell lets you act"
    _play(game, 1)
    assert rec["state"] == "yielded" and "traitor_caught" in adv["flags"]
    assert c in game.party, "one who confessed stays with you"
    assert "confessed" in traitors.journal_line(game, adv)
    adv["chapter"] = len(adv["chapters"]) - 1
    b, boss = _fight(game, adv, band)
    assert b.env.surprised == FOE, "it was told what you wanted it to hear"


def test_missed_one_at_your_side_goes_the_night_before(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    c = _hire(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "companion", "belief")
    adv["keys"] = ["name"]
    _open_chapter(game, adv, len(adv["chapters"]) - 1)
    assert not traitors.on_night(game, "camp", morning=True), "the betrayal comes in the dark"
    assert traitors.on_night(game, "camp", morning=False)
    pending = beats.pending(game)
    assert pending["beat"] == "traitor_turns"
    assert all(_whole(x) for x in beats.pages(game, pending))
    _play(game, -1)
    assert rec["state"] == "turned" and c not in game.party
    assert rec["key"] == "name" and "name" not in adv["keys"]
    assert game.encounter is not None, "and its servants come after them"


def test_one_who_turned_stands_beside_the_villain(made, tables, monkeypatch):
    game, adv, band = _den(made, tables, "beast", arena="")
    c = _hire(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "companion")
    beats.OPS["traitor"](game, {"adv": adv["id"]}, "flee")
    assert rec["state"] == "fled" and c not in game.party
    adv["chapter"] = len(adv["chapters"]) - 1
    b, boss = _fight(game, adv, band)
    beside = [f for f in b.side(FOE) if f.creature is not None and f.name == rec["name"]]
    assert beside and beside[0].bond is None and (beside[0].creature.story or {}).get("role") == "traitor"
    beside[0].hp = 0
    beside[0].state = "dead"


def test_still_hidden_they_turn_in_the_finales_fight(made, tables, monkeypatch):
    game, adv, band = _den(made, tables, "beast", arena="")
    c = _hire(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "companion")
    adv["chapter"] = len(adv["chapters"]) - 1
    b, boss = _fight(game, adv, band)
    f = next(x for x in b.fighters if x.char is c)
    assert f.team == PARTY
    b.round = traitors.TURN_ROUND
    for hook in list(b.round_hooks):
        hook(b)
    assert rec["state"] == "turned" and (f.team == FOE or f.state == "fled"), "the twist: they fight for it now"


def test_a_patron_who_was_never_kind_falters(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    _patron(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "patron")
    _open_chapter(game, adv, len(adv["chapters"]) - 1)
    assert not traitors.on_night(game, "inn", morning=True)
    assert rec["state"] == "faltered"
    adv["patron"]["trust"] = 2
    rec["state"], rec["fate"] = "hidden", None
    assert traitors.on_night(game, "inn", morning=True)
    assert beats.pending(game)["beat"] == "traitor_sells"
    adv["keys"] = ["militia", "name"]
    _play(game, -1)
    assert rec["state"] == "turned" and "militia" not in adv["keys"] and "name" in adv["keys"]


def test_the_patron_is_faced_in_their_own_town(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    p = _patron(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "patron")
    rec["seen"] = 2
    s = game.world.settlements[p.settlement]
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    talk(game, p, "story_accuse")
    assert rec["state"] == "yielded"


def test_a_deliver_step_carries_the_patrons_letter_and_a_traitor_s_letter_is_a_tell(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    _patron(game, adv)
    st = _step(adv, "deliver")
    _open_chapter(game, adv, 1)
    assert st.get("quest"), "its chapter opened: the letter is in your pack"
    q = quests.by_id(game, st["quest"])
    letter = next(it for c in game.party for it in c.inventory if f"quest:{q['id']}" in it.tags)
    assert _whole(letter.name) and q["template"] == "deliver"
    rec = _with_traitor(game, adv, monkeypatch, "patron")
    seen = rec["seen"]
    told = quests.read_letter(game, letter)
    assert rec["seen"] == seen + 1 and told
    who = game.world.npcs[st["target"]["npc"]]
    s = game.world.settlements[who.settlement]
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    talk(game, who, "deliver_letter")
    assert st["state"] == "done"
    assert any(it.def_id == "holy_water" for it in game.leader.inventory), "the temple gives back holy water"


def test_infiltrate_gets_you_in_unseen_or_brings_the_watch(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    _open_chapter(game, adv, 2)
    st = _step(adv, "infiltrate")
    site = game.world.sites[adv["places"]["home"]["site"]]
    game.player.x, game.player.y = site.x, site.y
    monkeypatch.setattr("realmwalker.game.camp.check", lambda game, skill, dc, **kw: (True, f"{skill}: success"))
    assert story.on_arrive(game)
    rec = beats.pending(game)
    assert rec["beat"] == "story_infiltrate" and all(_whole(x) for x in beats.pages(game, rec))
    opts = beats.choices(game, rec)
    assert not opts[0]["ok"], "a disguise needs a disguise on"
    _play(game, 1)
    assert st["state"] == "done" and "backway" in adv["keys"]
    assert beats.pending(game) is not None and beats.pending(game)["beat"] == "outlaw_the_hideout", \
        "then the arrival's own beat"
    game2, adv2, _ = _tale(made, tables, "outlaw")
    _open_chapter(game2, adv2, 2)
    st2 = _step(adv2, "infiltrate")
    game2.player.x, game2.player.y = site.x, site.y
    monkeypatch.setattr("realmwalker.game.camp.check", lambda game, skill, dc, **kw: (False, f"{skill}: failure"))
    assert story.on_arrive(game2)
    _play(game2, 1)
    assert st2["state"] == "failed" and game2.encounter is not None
    assert all((c.story or {}).get("role") == "infiltrate" for c in game2.encounter.creatures)


def test_the_epilogue_tells_of_the_traitor_and_the_innocent(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    _hire(game, adv)
    rec = _with_traitor(game, adv, monkeypatch, "companion")
    beats.OPS["traitor"](game, {"adv": adv["id"]}, "send")
    adv["boss_dead"] = True
    for line in endings.finish(game, adv):
        assert _whole(line)
    pages = {p["about"]: p["text"] for p in adv["epilogue"]}
    assert "traitor" in pages and rec["name"].split()[0] in pages["traitor"]
    assert "innocent" in pages and all(_whole(x) for x in pages.values())
    assert adv["innocent"]["fate"] == ("spared" if adv["state"] == "won" else "lost")
    assert rec["fate"] == "sent"
