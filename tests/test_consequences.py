"""What the world keeps of a tale (Expansion 6 G.3, docs/ADVENTURES.md §5.9, §5.19, §8.6): a beast slain leaves a
monument with words cut in it, a new name on its lair, a song sung at the inns weeks later, a keepsake, a title and a
holding whose rent waits in the town; a tale's doom ruins a town in full (a floor of survivors, the townsfolk's
fates, the map re-stamped and still walkable) and the ruin creeps back to life (rebuilding with scaffolds, the people
growing back, newcomers in the empty homes, perhaps a memorial); an outlaw lord's doom occupies a town, which is freed
when the band falls, and the ledger still replays; the lord of a place dies or steps down and the succession runs;
relations, laws, standing, rights (free board, a letter that opens doors) and the ally's fate."""

import copy

import pytest

from realmwalker.core.textgen import escape_markup as esc

from realmwalker.game import people, placemarks, services
from realmwalker.game import story
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.game.story import beats, consequences, endings
from realmwalker.world import factions as fx
from realmwalker.world import marks, news, threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

pytestmark = pytest.mark.story


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Threatland", 61, "medium"), tables)


def _tale(made, tables, kind, tier=3):
    w = copy.deepcopy(made)
    for t in [t for t in threats.records(w).values() if t["kind"] == kind and t["state"] != "ended"]:
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


def _town(game, adv):
    return game.world.settlements[int(adv["places"]["town"]["settlement"])]


def _replays(w) -> bool:
    holder = {}
    for e in w.history:
        for sid, fid in (e.get("data") or {}).get("owners", ()):
            holder[sid] = fid
    return all(holder.get(s.id, s.owner) == s.owner for s in w.settlements)


def _days(game, n):
    game.world.time += int(n) * consequences.DAY


def test_every_word_of_the_consequences_fills_for_its_own_tale(made, tables):
    own = {"beast": ("monument_beast", "rename_beast", "relic_beast", "cause_failed"),
           "outlaw": ("monument_gibbet", "law_harshness"),
           "risen": ("monument_risen", "relic_risen", "relic_risen_hero", "cause_risen")}
    common = ("ruin_news", "land_name", "letter_line")
    from realmwalker.core import textgen
    from realmwalker.game.story import words as wordsmod

    words = tables.adventures["consequences"]["words"]
    for kind, keys in own.items():
        game, adv, t = _tale(made, tables, kind)
        values = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
        values.update(home="H", town="T", place="P", realm="R", value="v")
        for key in keys + common:
            for line in words[key]:
                text = textgen.fill(line, game.world.rng, tables.adventures.get("words", {}), values)
                assert "{" not in text, (kind, key, line)
    for line in words["song_at_inn"]:
        assert "{" not in textgen.fill(line, made.rng, {}, {"singer": "s", "title": "t", "hero": "h"})


def test_a_beast_slain_is_remembered_in_stone_song_name_keepsake_title_and_land(made, tables):
    game, adv, t = _tale(made, tables, "beast", tier=3)
    s = _town(game, adv)
    w = game.world
    site = w.sites[int(t["home"]["site"])]
    old_name = site.name
    realm = fx.realm_of_settlement(w, s)
    works = len(w.politics.get("works") or [])
    adv["boss_dead"] = True
    lines = endings.finish(game, adv)
    assert adv["ending"] == "slain"
    mem = s.status.get("memorial")
    assert isinstance(mem, dict) and mem["what"] == "statue" and mem["words"] and "{" not in mem["words"]
    assert site.name != old_name and w.politics["renamed"][f"X{site.id}"]["old"] == old_name
    work = w.politics["works"][works]
    assert work["about"] == {"adventure": adv["id"]} and work["author"] in w.figures
    assert any(f"relic:{adv['id']}" in it.tags for it in game.leader.inventory), "the keepsake is in your pack"
    if realm is not None and realm.kind in tables.law["titles"]["names"]:
        assert any(x["realm"] == realm.id for x in game.renown.flags["titles"]), "the realm honours you"
        land = game.renown.flags["lands"][0]
        assert land["settlement"] == s.id and land["rent"] > 0
        _days(game, 65)
        money = game.leader.money
        consequences.on_visit(game, s)
        assert game.leader.money == money + 2 * land["rent"], "two months of rent"
    assert not any("{" in x for x in lines)
    # the song is sung at an inn of the town only once its weeks have passed
    keeper = None
    sung = work["sung"]
    for near in sorted(w.settlements, key=lambda o: (o.x - sung["x"]) ** 2 + (o.y - sung["y"]) ** 2)[:6]:
        prepare_town(game, near)
        keeper = next((n for n in npcs_in(w, near.id) if n.job == "innkeeper"), None)
        if keeper is not None:
            break
    assert keeper is not None, "an inn within the song's reach"
    w.time = int(work["sung"]["from"] - 1) * consequences.DAY
    assert consequences.song_at_inn(game, keeper) == [], "not before its weeks have passed"
    w.time = int(work["sung"]["from"] + 1) * consequences.DAY
    sung = consequences.song_at_inn(game, keeper)
    assert sung and esc(work["title"]) in sung[0]
    assert consequences.song_at_inn(game, keeper) == [], "once in each town"


def test_the_monument_stands_in_the_square_and_has_words_to_read(made, tables):
    from realmwalker.game.describe import describe_local
    game, adv, t = _tale(made, tables, "beast", tier=1)
    s = _town(game, adv)
    endings.OPS["monument"](game, adv, "town", "cairn", "monument_beast")
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    lm = game.local
    rec = lm.meta["marks"]["memorial"]
    assert rec["props"], "it stands somewhere"
    x, y = rec["props"][0]
    assert lm.terrain_ids[int(lm.terrain[x, y])] == "cairn"
    lm.seen[x, y] = True
    assert s.status["memorial"]["words"] in describe_local(game, x, y).replace("&#x27;", "'")


def test_a_doom_ruins_a_town_in_full_and_it_comes_back_to_life(made, tables):
    from tests.test_towns import check_works
    from realmwalker.world.local import get_local_map

    game, adv, t = _tale(made, tables, "beast", tier=3)
    s = _town(game, adv)
    w = game.world
    prepare_town(game, s)
    folk = [n for n in npcs_in(w, s.id) if n.alive and n.job not in consequences.FATE_JOBS]
    notables = [n for n in folk if n.notable]
    was = s.population
    t["outcome"] = "doom"
    endings.finish(game, adv)
    assert adv["ending"] == "doom"
    rec = s.status["ruined"]
    assert rec["was"] >= was and s.population == max(5, int(rec["was"] * 0.1)), "a floor of survivors"
    dead = [n for n in folk if not n.alive]
    fled = [n for n in folk if n.alive and n.flags.get("gone")]
    assert dead and fled and all(n.alive and not n.flags.get("gone") for n in notables)
    lm = get_local_map(w, game.tables, s.x, s.y)
    placemarks.stamp(game, lm, s)
    assert "ruined" in lm.meta["marks"] and len(lm.meta["marks"]["ruined"]["shut"]) > len(lm.buildings) // 2
    check_works(lm, game.tables, f"{s.name} in ruins")
    # a year and more on: people creep back, and the ruin is rebuilding, remembering the town it was
    pol = _politics(game)
    pol.day = news.now_days(w) + 600
    pol.expire_status()
    r = s.status.get("rebuilding")
    assert "ruined" not in s.status and isinstance(r, dict) and r["was"] == rec["was"]
    before = s.population
    pol.regrow(0.25)
    assert before < s.population <= r["was"], "the people grow back"
    placemarks.stamp(game, lm, s)
    assert "scaffold" in {lm.terrain_ids[int(lm.terrain[x, y])] for x, y in lm.meta["marks"]["rebuilding"]["props"]}
    check_works(lm, game.tables, f"{s.name} rebuilding")
    s.population = r["was"]
    came = consequences.newcomers(game, s)
    assert came > 0 and all(n.flags.get("newcomer") is not None for n in npcs_in(w, s.id)[-came:])


def _politics(game):
    from realmwalker.game import past

    return past._politics(game)


def test_an_outlaw_doom_occupies_the_town_until_the_band_falls(made, tables):
    game, adv, t = _tale(made, tables, "outlaw", tier=3)
    w = game.world
    s = _town(game, adv)
    old = s.owner
    gang = threats.gang_of(w, t)
    s.status.pop("siege", None)
    t["outcome"] = "doom"
    endings.finish(game, adv)
    assert adv["ending"] == "doom"
    assert s.owner == gang.id and s.status["occupied"]["was"] == old and _replays(w)
    assert "occupied" in marks.label(tables, s)[0] or any("occupied" in x for x in marks.label(tables, s))
    pol = _politics(game)
    pol.fall(gang)
    assert s.owner == old and "occupied" not in s.status and _replays(w), "freed, and the ledger still true"


def test_an_occupation_whose_time_is_out_gives_the_town_back(made, tables):
    game, adv, t = _tale(made, tables, "outlaw", tier=3)
    w = game.world
    s = _town(game, adv)
    old = s.owner
    s.status.pop("siege", None)
    endings.OPS["set_owner"](game, adv, "town", "villain", 1)
    if s.owner == old:
        pytest.skip("this town cannot be occupied (a city)")
    pol = _politics(game)
    pol.day = float(s.status["occupied"]["until"]) + 1
    pol.expire_status()
    assert s.owner == old and "occupied" not in s.status and _replays(w)


def test_the_lord_of_a_place_dies_or_steps_down_and_the_seat_passes(made, tables):
    game, adv, t = _tale(made, tables, "risen", tier=3)
    w = game.world
    s = _town(game, adv)
    f = w.factions[s.owner]
    lord = fx.leader_of(w, f)
    if f.kind in consequences.CROWNS:
        assert endings.OPS["figure_dies"](game, adv, "lord:town", "cause_risen", 3) == [] and lord.alive,             "a tale never kills a crown"
        house = next(x for x in w.factions.values() if x.active and x.kind not in consequences.CROWNS
                     and x.kind not in ("bandit_gang", "pirate_crew") and fx.leader_of(w, x) is not None)
        _politics(game).set_owner(s, house.id)
        f, lord = house, fx.leader_of(w, house)
    endings.OPS["figure_dies"](game, adv, "lord:town", "cause_risen", 3)
    assert not lord.alive and fx.leader_of(w, f) is not None and fx.leader_of(w, f) is not lord
    second = fx.leader_of(w, f)
    endings.OPS["succession"](game, adv, "town", 1, "")
    assert second.alive and fx.leader_of(w, f) is not second, "stepped down, and another rules"


def test_relations_laws_standing_and_the_rights_of_a_hero(made, tables):
    from realmwalker.game import reputation

    game, adv, t = _tale(made, tables, "outlaw", tier=2)
    w = game.world
    s = _town(game, adv)
    realm = fx.realm_of_settlement(w, s)
    gang = threats.gang_of(w, t)
    before = fx.relation(w, realm.id, gang.id)
    endings.OPS["relation"](game, adv, "town", "villain", 15)
    assert fx.relation(w, realm.id, gang.id) > before
    lines = endings.OPS["law"](game, adv, "town", "harshness", "cruel")
    assert fx.laws_at(w, s)["harshness"] == "cruel" and lines and "{" not in lines[0]
    st = reputation.standing(game, realm.id)
    endings.OPS["standing"](game, adv, "town", 5)
    assert reputation.standing(game, realm.id) > st
    prepare_town(game, s)
    keeper = next((n for n in npcs_in(w, s.id) if n.job == "innkeeper"), None)
    endings.OPS["right"](game, adv, "town", "board")
    if keeper is not None:
        assert services.stay_price(game, keeper, "stay", services.grades(game, keeper)[0]) == 0, "free board"
    guard = next(n for n in npcs_in(w, s.id) if n.job in ("guard", "lord", "headman") or n.social == "high")
    plain = people.papers_impression(game, guard)
    endings.OPS["right"](game, adv, "town", "letter")
    assert people.papers_impression(game, guard) > plain, "the letter opens doors"
    assert any(it.tags and any(x.startswith("letter:") for x in it.tags) for it in game.leader.inventory)


def test_a_dark_ending_feeds_the_threat_and_the_ally_walks_away(made, tables):
    game, adv, t = _tale(made, tables, "risen", tier=1)
    tier = t["tier"]
    endings.OPS["threat_grows"](game, adv)
    endings.OPS["threat_grows"](game, adv)
    top = tables.threats["kinds"]["risen"]["tiers"][1]
    assert t["tier"] == min(top, tier + 1), "once"
    prepare_town(game, _town(game, adv))
    npc = next(n for n in npcs_in(game.world, _town(game, adv).id) if n.alive)
    adv["ally"] = {"state": "riding", "npc": npc.id}
    assert endings.OPS["ally_fate"](game, adv, "broke")
    assert adv["ally"]["state"] == "broke"


def test_a_risen_laid_to_rest_lifts_the_haunting_and_rests(made, tables):
    game, adv, t = _tale(made, tables, "risen", tier=4)
    w = game.world
    s = _town(game, adv)
    marks.add(w, s, "haunted", news.now_days(w), tables, by="him")
    adv["flags"].append("laid")
    endings.finish(game, adv)
    assert adv["ending"] == "laid_to_rest"
    assert "haunted" not in s.status and s.status["memorial"]["what"] == "shrine"
    assert str(t["home"]["site"]) not in (w.politics.get("tombs") or {})
    assert any(r["adv"] == adv["id"] for r in w.politics.get("relics", [])), "the grave-gold to the temple"
    assert consequences.relic_line(game, s)


def test_every_new_mark_has_its_words_and_dressing(tables):
    spec = tables.marks
    for m in ("ruined", "cursed", "occupied"):
        assert spec[m]["dress"] and len(spec[m]["troubles"]) >= 3 and len(spec[m]["moments"]) >= 3
    assert spec["rebuilding"]["leaves"]["mark"] == "memorial"
