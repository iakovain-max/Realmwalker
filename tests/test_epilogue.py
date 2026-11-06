"""The epilogue in full, the tale's chapter of history and sequel threats (Expansion 6 G.4, docs/ADVENTURES.md §5.9,
§5.13): a tale's last screen tells of every place it touched as it now is, the patron, the cast, the realm, what is
left to come back and, last, you with your standing and name; the tale goes into the Legends book as a named chapter
linked from its villain, its places and the hero's life; a slain beast may leave its get, a broken band a gap that a
new gang fills, each asleep for weeks and then stirring, told to the hero who ended the first tale, and the tale
forged on it follows on from the first in the book."""

import copy

import pytest

from realmwalker.game import story
from realmwalker.game.state import new_game
from realmwalker.game.story import beats, endings, epilogue, sequels
from realmwalker.world import legends, news, threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.politics import Politics
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

pytestmark = pytest.mark.story


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Threatland", 61, "medium"), tables)


def _tale(made, tables, kind, tier=3, threat_id=None):
    w = copy.deepcopy(made)
    for t in [t for t in threats.records(w).values() if t["kind"] == kind and t["state"] != "ended"]:
        if threat_id is not None and t["id"] != threat_id:
            continue
        town = min((s for s in w.settlements if s.kind in ("town", "village")),
                   key=lambda s: threats.distance(w, t, s.x, s.y))
        game = new_game(w, tables, start_settlement=town.id)
        game.survival = False
        beats.director(game.world)["pending"] = None
        beats.director(game.world)["opening"] = None
        t = threats.records(game.world)[t["id"]]
        if t["state"] == "dormant":
            threats.stir(game.world, tables, t, game.world.rng, day=0)
        story.take_hook(game, t["id"])
        if story.active(game):
            adv = story.active(game)[0]
            adv["tier"] = tier
            beats.director(game.world)["card"] = None
            return game, adv, t
    pytest.fail(f"no tale of the {kind} could be forged here")


@pytest.fixture
def sure_sequels(monkeypatch):
    """Every sequel_threat op happens (the data gives each a chance)."""
    op = endings.OPS["sequel_threat"]
    monkeypatch.setitem(endings.OPS, "sequel_threat", lambda g, a, kind="heir", chance=1.0: op(g, a, kind, 1.0))


def _ordered(pages) -> bool:
    ranks = [epilogue._rank(p["about"]) for p in pages]
    return ranks == sorted(ranks)


def test_a_slain_beast_s_epilogue_tells_of_everything_it_touched(made, tables):
    game, adv, t = _tale(made, tables, "beast", tier=3)
    adv["boss_dead"] = True
    endings.finish(game, adv)
    pages = adv["epilogue"]
    abouts = [p["about"] for p in pages]
    assert 4 <= len(pages) <= epilogue.MOST, abouts
    assert abouts[-1] == "hero" and abouts[0] == "place" and _ordered(pages), abouts
    assert all(p["text"] and "{" not in p["text"] for p in pages), [p["text"] for p in pages if "{" in p["text"]]
    town = epilogue._town(game, adv)
    mark = epilogue.town_mark(town)
    assert mark in ("rebuilding", "memorial"), "the beast's town is rebuilding, with a statue in its square"
    assert any(p["about"].startswith("place:") for p in pages), "the lair as it now is (renamed, cleared)"
    if epilogue.realm_of(game, adv) is not None:
        realm = next(p for p in pages if p["about"] == "realm")
        assert epilogue.realm_of(game, adv).name in realm["text"]
        from realmwalker.game import reputation

        game.renown.standing[epilogue.realm_of(game, adv).id] = 30.0
        lines = epilogue.hero_lines(game, adv, {})
        assert any(epilogue.realm_of(game, adv).name in x for x in lines), "your standing with the realm, on your page"
        game.renown.standing[epilogue.realm_of(game, adv).id] = 2.0
        assert reputation.standing(game, epilogue.realm_of(game, adv).id) == 2
        assert not any(epilogue.realm_of(game, adv).name in x for x in epilogue.hero_lines(game, adv, {})),             "nothing to say of a realm that hardly knows you"
    from realmwalker.ui.gfx import vignette

    for p in pages:  # (every page has its picture)
        assert vignette.for_epilogue(game, adv, p["about"])["backdrop"] in vignette.BACKDROPS, p["about"]


def test_the_tale_is_a_named_chapter_in_the_legends_book(made, tables):
    game, adv, t = _tale(made, tables, "beast", tier=2)
    villain = threats.villain_figure(game.world, t)
    adv["boss_dead"] = True
    endings.finish(game, adv)
    w = game.world
    i = epilogue.tale_of(w, adv["id"])
    assert i is not None
    rec = w.politics["tales"][i]
    assert rec["won"] and rec["state"] == "won" and rec["title"] == adv["title"] and rec["villain"] == villain.id
    assert epilogue.chronicle(game, adv) is rec and len(w.politics["tales"]) == i + 1, "written once"
    refs = [r for r, _ in legends.entries(w, tables, "tales")]
    assert f"C{i}" in refs
    title, lines = legends.page(w, tables, f"C{i}")
    assert title.startswith(legends.cap(adv["title"])) and str(rec["year"]) in title
    text = "\n".join(lines)
    assert "What became of them" in text and legends.TALE_ENDS["won"] in text
    assert legends.plain(next(ln for ln in lines if "The tale of" in ln)).count(villain.name) == 1
    # the villain, its places link back to it; every link leads somewhere
    for ref in [f"H{villain.id}"] + rec["places"]:
        _, back = legends.page(w, tables, ref)
        assert any(f"[[C{i}|" in ln for ln in back), ref
    for ln in lines:
        for ref, _ in legends.LINK_RE.findall(ln):
            assert legends.page(w, tables, ref)[0] != "Nothing", ref


def test_a_tale_cut_short_by_death_is_written_as_far_as_it_went(made, tables):
    game, adv, t = _tale(made, tables, "risen", tier=2)
    from realmwalker.game import death

    game.over = {"cause": "of a fever"}
    rec = death.die(game)
    w = game.world
    i = epilogue.tale_of(w, adv["id"])
    tale = w.politics["tales"][i]
    assert tale["state"] == "orphaned" and tale["chapters"], "its chapters as far as it went"
    text = "\n".join(legends.page(w, tables, f"C{i}")[1])
    assert legends.TALE_ENDS["orphaned"] in text
    life = next(k for k, r in enumerate(w.politics["fallen"]) if r is rec)
    assert f"[[P{life}|" in text, "the hero's life is linked"
    assert any(f"[[C{i}|" in ln for ln in legends.page(w, tables, f"P{life}")[1]), "and the life links its tales"


def test_a_slain_beast_s_get_wakes_weeks_later_and_its_tale_follows_on(made, tables, sure_sequels, monkeypatch):
    game, adv, t = _tale(made, tables, "beast", tier=2)
    old = threats.villain_figure(game.world, t)
    adv["boss_dead"] = True
    endings.finish(game, adv)
    w = game.world
    assert adv.get("sequel", {}).get("kind") == "heir", "a lair was free near the old one"
    heir = threats.records(w)[adv["sequel"]["threat"]]
    fig = threats.villain_figure(w, heir)
    assert heir["state"] == "dormant" and heir["sequel"] == "heir" and heir["sequel_of"]["adv"] == adv["id"]
    assert fig.parent == old.id and fig.creature == old.creature and fig.alive and old.name in fig.name
    assert w.politics["lairs"][str(heir["home"]["site"])] == fig.id and threats.villain_lives(w, heir)
    assert any(p["about"] == "sequel" for p in adv["epilogue"]), "the epilogue says it is not over"
    tale = w.politics["tales"][epilogue.tale_of(w, adv["id"])]
    # it sleeps its weeks, then stirs for sure; the hero hears of it once
    monkeypatch.setattr(threats, "room_for", lambda *a, **k: True)
    pol = Politics(w, tables, w.rng.child("test"), day=news.now_days(w))
    threats.advance(pol, 7)
    assert heir["state"] == "dormant", "not before its time"
    w.time = int((heir["scheme"]["held_until"] + 1) * 24 * 60)
    pol = Politics(w, tables, w.rng.child("test2"), day=news.now_days(w))
    threats.advance(pol, 7)
    assert heir["state"] in threats.LIVE
    told = len(game.log.entries) if hasattr(game.log, "entries") else None
    sequels.daily(game)
    assert heir["sequel_of"].get("told") is not None
    if told is not None:
        assert len(game.log.entries) == told + 1
    sequels.daily(game)
    if told is not None:
        assert len(game.log.entries) == told + 1, "once"
    # the tale forged on it follows on from the first
    beats.director(w)["pending"] = None
    beats.director(w)["opening"] = None
    story.take_hook(game, heir["id"])
    adv2 = next((a for a in story.active(game) if a["threat"] == heir["id"]), None)
    assert adv2 is not None and adv2["sequel_of"] == adv["id"]
    adv2["boss_dead"] = True
    endings.finish(game, adv2)
    j = epilogue.tale_of(w, adv2["id"])
    i = w.politics["tales"].index(tale)
    assert any(f"[[C{i}|" in ln for ln in legends.page(w, tables, f"C{j}")[1]), "it came after"
    assert any(f"[[C{j}|" in ln for ln in legends.page(w, tables, f"C{i}")[1]), "what came of it"


def test_a_broken_band_leaves_a_gap_and_a_new_gang_fills_it(made, tables, sure_sequels):
    game, adv, t = _tale(made, tables, "outlaw", tier=2)
    gang = threats.gang_of(game.world, t)
    adv["boss_dead"] = True
    endings.finish(game, adv)
    w = game.world
    assert adv["ending"] in ("broken", "pardoned", "spared", "taken"), adv["ending"]
    assert adv.get("sequel", {}).get("kind") == "vacuum"
    new = threats.records(w)[adv["sequel"]["threat"]]
    band = threats.gang_of(w, new)
    assert band is not None and band.active and band.id != gang.id and new["source"]["gap_of"] == gang.id
    assert new["state"] == "dormant" and new["scheme"]["held_until"] > news.now_days(w)
    page = next(p for p in adv["epilogue"] if p["about"] == "sequel")
    assert band.name in page["text"]


def test_every_new_word_fills_for_every_kind_of_tale(made, tables):
    spec = tables.adventures["consequences"]["words"]
    keys = [k for k in spec if k.startswith(("vignette_", "epilogue_", "sequel_told_", "hero_"))]
    assert len(keys) >= 25
    for kind in ("beast", "outlaw", "risen"):
        game, adv, t = _tale(made, tables, kind, tier=2)
        for key in keys:
            for n in range(len(spec[key])):
                text = epilogue._words(game, adv, key, f"t/{n}", place="Here", old="There", realm="the Realm",
                                       ruler="the King", town="the Town", standing="friendly", title="Sir X",
                                       heir="the Get", gang="the Knives")
                assert text and "{" not in text, (kind, key, text)
        assert len(spec[key]) >= 3, key
