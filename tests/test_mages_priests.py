"""Expansion 5 Part C: mages and priests of the world (docs/expansions/05-schools-domains.md).

C.1: the Monster Manual's Mage Apprentice, Mage, Archmage, Priest and Archpriest - their blocks, the casting their
blocks describe (spells at a higher level, Divine Aid and Misty Step with the bonus action, Protective Magic's
Counterspell or Shield three times a day, Holy Word on enemies only), their dress among each people, and the road.
"""
from __future__ import annotations

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.creatures import Creature, spawn
from realmwalker.world.tables import Tables
from tests.test_feats import fight, hero, on_turn, soft


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def foe(b, def_id):
    return next(f for f in b.fighters if f.side == FOE and f.creature.def_id == def_id)


# ---------------------------------------------------------------------------- C.1 the blocks
@pytest.mark.parametrize("cid, ac, hp, cr, multi", [
    ("mage_apprentice", 15, "9d8+9", 2, None), ("mage", 15, "18d8", 6, 3), ("archmage", 17, "31d8+31", 12, 4),
    ("priest", 13, "7d8+7", 2, 2), ("archpriest", 16, "32d8+96", 12, 3)])
def test_the_book_numbers(tables, cid, ac, hp, cr, multi):
    d = tables.creatures[cid]
    assert (d["ac"], d["hp"], d["cr"], d.get("multiattack")) == (ac, hp, cr, multi)
    assert d["kind"] == "humanoid" and d["descriptions"]


def test_what_the_block_says_it_casts(tables):
    mage, arch, priest = tables.creatures["mage"], tables.creatures["archmage"], tables.creatures["priest"]
    assert mage["spellcasting"]["dc"] == 14 and mage["spellcasting"]["levels"] == {"fireball": 4}
    assert mage["spellcasting"]["shared"]["protective_magic"] == {"uses": 3, "spells": ["counterspell", "shield"]}
    assert "misty_step" in mage["spellcasting"]["bonus"] and "misty_step" in mage["spellcasting"]["per_day"]["3"]
    assert "mage_armor" not in mage["spells"]  # (included in its AC)
    assert "mind_blank" not in arch["spells"] and "magic_resistance" in arch["traits"]
    assert arch["immune"] == ["psychic"] and arch["condition_immune"] == ["charmed"]
    # A priest's DC and attack are not printed: Wisdom and proficiency (8 + 2 + 3; 2 + 3).
    assert (priest["spellcasting"]["dc"], priest["spellcasting"]["attack"]) == (13, 5)
    assert set(priest["spellcasting"]["bonus"]) == {"bless", "dispel_magic", "healing_word", "lesser_restoration"}


def test_divine_aid_is_a_bonus_action_whatever_the_spell(tables):
    c = hero(tables, "fighter", level=3)
    b = fight(tables, c, "priest")
    pr = foe(b, "priest")
    on_turn(b, pr)
    assert "bless" in b.creature_spells(pr)
    assert b.creature_cast(pr, "bless", target=pr)
    assert pr.bonus == 0 and pr.action == 1  # (Bless, an action's spell, went with the bonus action)
    assert pr.creature.uses["pool:divine_aid"] == 2


def test_a_mage_casts_fireball_at_level_four(tables, monkeypatch):
    c = hero(tables, "fighter", level=5)
    b = fight(tables, c, "mage", spots={0: (3, 4), 1: (9, 4)})
    m = foe(b, "mage")
    on_turn(b, m)
    seen = {}
    real = b.cast

    def cast(f, sid, spell, target, point, **kw):
        seen[sid] = kw
        return real(f, sid, spell, target, point, **kw)

    monkeypatch.setattr(b, "cast", cast)
    pc = next(f for f in b.fighters if f.side == PARTY)
    point = (pc.x, pc.y)
    assert point in b.spell_points(m, "fireball")
    assert b.creature_cast(m, "fireball", point=point)
    assert seen["fireball"]["up"] == 1 and seen["fireball"]["level"] == 4
    assert m.creature.uses["spell:fireball"] == 1


def test_protective_magic_shield_turns_a_blow_and_shares_the_three_with_counterspell(tables):
    c = hero(tables, "fighter", level=5)
    b = fight(tables, c, "mage")
    m = foe(b, "mage")
    pc = next(f for f in b.fighters if f.side == PARTY)
    on_turn(b, pc)
    m.reaction = True
    opt = next(o for o in b.attack_options(pc) if o.key == "main")
    assert b._shield(m, pc, opt, 16, 15)
    assert m.creature.uses["pool:protective_magic"] == 2 and not m.reaction
    assert any(x.get("source") == "shield" and x.get("ac") == 5 for x in m.buffs)
    from realmwalker.rules.engine.handlers import wizard

    m.creature.uses["pool:protective_magic"] = 0
    assert wizard.counter_slot(b, m) is None  # (the three are spent: no Counterspell either)
    m.reaction = True
    m.buffs = [x for x in m.buffs if x.get("source") != "shield"]
    assert not b._shield(m, pc, opt, 16, 15)


def test_a_mage_counterspells_a_party_caster(tables):
    c = hero(tables, "wizard", level=5)
    b = fight(tables, c, "mage", spots={0: (3, 4), 1: (6, 4)})
    m = foe(b, "mage")
    pc = next(f for f in b.fighters if f.side == PARTY)
    on_turn(b, pc)
    m.reaction = True
    assert b._countered(pc, "magic_missile", tables.spells["magic_missile"]) in (True, False)
    assert m.creature.uses["pool:protective_magic"] == 2 and not m.reaction


def test_holy_word_strikes_enemies_only_and_recharges_on_a_four(tables):
    c = hero(tables, "fighter", level=5)
    b = fight(tables, c, "archpriest", "priest", spots={0: (3, 4), 1: (4, 4), 2: (4, 5)})
    ap, pr = foe(b, "archpriest"), foe(b, "priest")
    pc = next(f for f in b.fighters if f.side == PARTY)
    on_turn(b, ap)
    word = next(o for o in b.attack_options(ap) if o.extra.get("area") and o.available)
    hp_pr = pr.hp
    b.area_attack(ap, word, (pc.x, pc.y))
    assert pr.hp == hp_pr  # (each enemy in it: the priest beside it is spared)
    assert b._recharge_on(ap, word.extra["name"]) == 4 and not ap.recharge[word.extra["name"]]


def test_a_mage_and_a_priest_fight_to_the_end(tables):
    from tools import arena

    party = [hero(tables, "fighter", seed=s, level=6) for s in (1, 2, 3)]
    for cid in ("mage", "priest", "mage_apprentice", "archpriest"):
        b = fight(tables, party, cid, seed=4, spots={0: (2, 4), 1: (2, 5), 2: (2, 6), 3: (9, 5)})
        for f in b.fighters:
            f.auto = True
        r = arena.run(b)
        assert b.outcome is not None, cid
        assert any(k.startswith("cast:") for k in r["used"]), (cid, r["used"])


# ---------------------------------------------------------------------------- C.1 dress and the road
def test_a_creature_keeps_its_people_in_the_save(tables):
    c = spawn(tables, "mage", RNG(1, "m"), 1)
    c.culture = "qasari"
    assert Creature.from_dict(c.to_dict()).culture == "qasari"
    c.culture = ""
    assert "culture" not in c.to_dict() and Creature.from_dict(c.to_dict()).culture == ""


def test_mages_dress_as_their_people(tables):
    from realmwalker.ui.gfx import dolls

    plain = [p[0] for p in dolls.creature("mage", tables, "m1")]
    qasari = [p[0] for p in dolls.creature("mage", tables, "m1", culture="qasari")]
    assert any("wizard" in t for t in plain) and any("turban" in t for t in qasari)
    assert not dolls.check(tables) if hasattr(dolls, "check") else True


def test_folk_met_on_the_road_are_of_the_land(tables, monkeypatch):
    import copy

    from realmwalker.game.encounters import make_encounter
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    g = new_game(copy.deepcopy(cached_world(WorldOptions("Mages", 7, "small"), tables)), tables)
    w, p = g.world, g.player
    folk = w.culture_at(p.x, p.y) if w.culture is not None else None
    e = make_encounter(g, "travelling_mage", RNG(3, "enc"))
    assert {c.def_id for c in e.creatures} <= {"mage", "mage_apprentice"}
    assert all(c.culture == (folk or "") for c in e.creatures)


# ---------------------------------------------------------------------------- C.2 towers lived in, temples staffed
@pytest.fixture
def game(tables):
    import copy

    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    g = new_game(copy.deepcopy(cached_world(WorldOptions("Mages", 7, "small"), tables)), tables)
    g.survival = False
    return g


def lived_tower(game, rank="mage"):
    """A tower of this world whose wizard lives (one made so if the history left none alive)."""
    from realmwalker.world import dungeon as gen

    w = game.world
    towers = [s for s in w.sites if s.kind == "tower" and str(s.id) in w.politics.get("towers", {})
              and gen.style_for(w, s) == "tower"]
    assert towers, "the test world has no tower with a history"
    site = towers[0]
    fig = w.figures[w.politics["towers"][str(site.id)]]
    fig.died = None
    fig.level, fig.fame = (15, 9) if rank == "archmage" else (8, 4)
    game.player.x, game.player.y = site.x, site.y
    return site, fig


def test_a_tower_whose_wizard_lives_is_kept(game):
    from realmwalker.world import dungeon as gen

    site, fig = lived_tower(game)
    m = gen.tower_master(game.world, site)
    assert m == {"figure": fig.id, "name": fig.name, "rank": "mage"}
    depth = gen.depth_for(game.world, site)
    top = gen.get_dungeon(game.world, game.tables, site, depth)
    assert top.meta["master"]["rank"] == "mage" and top.meta["desc"] in game.tables.sites["dungeon_styles"]["tower_lived"]
    kinds = [f.get("kind") for f in top.features.values()]
    assert "library" in kinds
    assert all(f["trap"] == "glyph" and f["dc"] == 14 for f in top.features.values() if f.get("kind") == "trap")
    assert all(f.get("warded") for f in top.features.values() if f.get("kind") == "lock")
    names = set(top.terrain_ids[int(i)] for i in set(top.terrain.flatten().tolist()))
    assert "bookcase" in names and "rubble" not in names


def test_an_empty_towers_floors_are_as_they_were(game):
    from realmwalker.world import dungeon as gen

    site, fig = lived_tower(game)
    fig.died = 1
    assert gen.tower_master(game.world, site) is None
    lm = gen.get_dungeon(game.world, game.tables, site, 1)
    assert "master" not in lm.meta
    assert all(f.get("trap") != "glyph" for f in lm.features.values())


def test_the_master_waits_at_the_top_with_the_household(game):
    from realmwalker.game import dungeon
    from realmwalker.world import dungeon as gen

    site, fig = lived_tower(game, "archmage")
    depth = gen.depth_for(game.world, site)
    top = gen.get_dungeon(game.world, game.tables, site, depth)
    dungeon.populate(game, top)
    assert top.meta["boss"] == "tower_archmage"
    master = next(c for a in top.actors for c in a.creatures if c.def_id == "archmage")
    assert master.name == fig.name and master.named and master.culture == fig.culture
    others = {a.group for a in top.actors} - {"tower_archmage"}
    assert others <= {"tower_apprentices", "tower_familiars"}


def test_a_glyph_on_the_stair_goes_off(game, monkeypatch):
    from realmwalker.game import dungeon
    from realmwalker.world import dungeon as gen

    site, fig = lived_tower(game)
    lm = gen.get_dungeon(game.world, game.tables, site, 1)
    game.player.local_key = lm.key
    pos, f = next((p, f) for p, f in lm.features.items() if f.get("trap") == "glyph")
    monkeypatch.setattr(dungeon, "passive", lambda g, s: (0, g.leader))
    before = game.leader.hp = game.leader.max_hp = 200
    dungeon.spring(game, lm, *pos, f)
    assert f["spent"] and game.leader.hp < before
    assert any("glyph of warding" in m.text for m in game.log.recent(3))


def test_the_library_gives_scrolls_and_lore_once(game):
    from realmwalker.game import dungeon
    from realmwalker.world import dungeon as gen

    site, fig = lived_tower(game)
    depth = gen.depth_for(game.world, site)
    lm = gen.get_dungeon(game.world, game.tables, site, depth)
    game.player.local_key = lm.key
    (x, y), _ = next((p, f) for p, f in lm.features.items() if f.get("kind") == "library")
    game.player.lx, game.player.ly = lm.entry
    assert dungeon.bump(game, x, y)
    found = lm.items[(game.player.lx, game.player.ly)]
    ids = [i.def_id for i in found]
    assert "lore_book" in ids and any(i.startswith("scroll_") for i in ids)
    scrolls = [game.tables.items.get(i)["use"]["scroll"] for i in ids if i.startswith("scroll_")]
    assert all("wizard" in game.tables.spells[s]["classes"] and 1 <= game.tables.spells[s]["level"] <= 3 for s in scrolls)
    dungeon.bump(game, x, y)
    assert len(lm.items[(game.player.lx, game.player.ly)]) == len(found)  # (once)


def test_the_world_remembers_the_wizard_slain_in_their_tower(game):
    from types import SimpleNamespace

    from realmwalker.game import past

    site, fig = lived_tower(game)
    body = spawn(game.tables, "mage", RNG(1, "m"), 1)
    body.name, body.named = fig.name, True
    past.on_battle(game, SimpleNamespace(outcome="victory", dead=[body]))
    assert not fig.alive and fig.died_at == f"X{site.id}"
    assert any(e.get("player") and fig.id in e.get("figures", ()) for e in game.world.history)
    from realmwalker.world import dungeon as gen

    held = game.world.factions.get(site.faction) if getattr(site, "faction", -1) >= 0 else None
    if held is None or held.kind != "mages_circle":
        assert gen.tower_master(game.world, site) is None  # (empty now)


def test_temples_and_mages_on_the_books_blocks(game, tables):
    from realmwalker.game import spellhire

    occ = tables.people["occupations"]
    assert occ["priest"]["stats"] == "priest" and occ["mage"]["stats"] == "mage"

    great = [s for s in game.world.settlements if getattr(s, "great", False)]
    if not great:
        pytest.skip("no great city in the small test world")
    from realmwalker.game.people import npcs_in, populate_town
    from realmwalker.world.local import get_local_map

    s = great[0]
    game.player.x, game.player.y = s.x, s.y
    lm = get_local_map(game.world, tables, s.x, s.y)
    populate_town(game, lm, s)
    folk = npcs_in(game.world, s.id)
    high = [n for n in folk if n.stats == "archpriest"]
    assert len(high) == 1 and high[0].title.startswith("high priest")
    assert spellhire.reach(game, high[0]) == int(spellhire.spec(game)["reach"]["city"])


# ---------------------------------------------------------------------------- C.3 apprenticeships, the history's casters
def test_the_historys_temple_heads_and_circle_mages_fight_on_the_books_blocks():
    from types import SimpleNamespace

    from realmwalker.game.people import figure_stats

    assert figure_stats("priest", SimpleNamespace(level=3, fame=1)) == "archpriest"
    assert figure_stats("mage", SimpleNamespace(level=14, fame=2)) == "archmage"
    assert figure_stats("mage", SimpleNamespace(level=8, fame=8)) == "archmage"
    assert figure_stats("mage", SimpleNamespace(level=8, fame=3)) == "mage"
    assert figure_stats("lord", SimpleNamespace(level=8, fame=3)) is None


def town_mage(game):
    from realmwalker.game.people import add, make_npc, town_of

    s = game.world.settlements[0]
    npc = make_npc(game, s, "mage", RNG(5, "mage"))
    add(game.world, town_of(game.world, s.id), npc)
    game.player.x, game.player.y = s.x, s.y
    return npc


def test_a_mage_offers_an_apprenticeship_for_a_grimoire(game):
    from realmwalker.game import quests

    site, fig = lived_tower(game)
    npc = town_mage(game)
    q = quests.make_offer(game, npc, RNG(2, "offer"), template="apprenticeship")
    assert q is not None and q["giver_job"] == "mage"
    t = q["target"]
    assert t["item"].startswith("the grimoire of ") and t["base"] == "spellbook"
    if t["wizard"] == fig.name:
        assert t["rival"] is True  # (the wizard lives: their own shelves)
    words = quests.pitch(game, q)
    assert t["wizard"] in words or t["item"] in words


def test_the_grimoire_waits_at_the_bottom_and_counts_as_carried_back(game):
    from realmwalker.game import quests
    from realmwalker.world import dungeon as gen

    site, fig = lived_tower(game)
    fig.died = 1  # (a dead wizard's tower)
    npc = town_mage(game)
    q = quests.make_offer(game, npc, RNG(2, "offer"), template="apprenticeship")
    q["target"].update(site=site.id)
    quests.accept(game, q)
    game.player.x, game.player.y = site.x, site.y
    lm = gen.get_dungeon(game.world, game.tables, site, gen.depth_for(game.world, site))
    lm.populated = True
    quests.on_arrive_dungeon(game, lm)
    feat = next(f for f in lm.features.values() if f.get("quest") == q["id"])
    items = quests.on_chest(game, feat)
    assert items and items[0].def_id == "spellbook" and q["done"]
    assert "apprenticeship" in quests.FETCHED and not quests.holds_quest_item(game, q)


def test_the_lesson_writes_a_spell_into_a_wizards_book(game, tables):
    from realmwalker.game import quests

    npc = town_mage(game)
    wiz = hero(tables, "wizard", level=5)
    game.party.append(wiz)
    before = set(wiz.spells.get("spellbook", []))
    q = {"id": 991}
    lines = quests.lesson(game, q, npc)
    new = set(wiz.spells["spellbook"]) - before
    assert len(new) == 1 and lines
    sid = new.pop()
    assert "wizard" in tables.spells[sid]["classes"] and 1 <= tables.spells[sid]["level"] <= 3


def test_with_no_wizard_the_lesson_is_a_scroll(game):
    from realmwalker.game import quests

    npc = town_mage(game)
    game.party[:] = [c for c in game.party if c.cls != "wizard"] or game.party[:1]
    game.leader.cls = "fighter" if game.leader.cls == "wizard" else game.leader.cls
    n = len(game.leader.inventory)
    lines = quests.lesson(game, {"id": 992}, npc)
    assert lines and len(game.leader.inventory) == n + 1
    assert game.leader.inventory[-1].def_id.startswith("scroll_")


# ---------------------------------------------------------------------------- C.4 the tactics in their scenes
def cast_events(b, f):
    return [e.get("spell") for e in b.events if e["kind"] == "cast" and e.get("by") == f.id]


def test_a_hurt_mage_ringed_by_blades_vanishes(tables):
    from realmwalker.rules import tactics
    from tools import arena

    for seed in range(1, 6):
        b = arena.setup(tables, "mage", "close", seed)
        m = next(f for f in b.fighters if f.side == FOE and f.creature.uid == 1)
        m.creature.hp = m.max_hp // 3
        for sid in ("misty_step", "cone_of_cold", "fireball"):  # (the end of its day: no step away, no blast)
            m.creature.uses[f"spell:{sid}"] = 0
        for o in b.fighters:
            if o.side == FOE and o is not m:
                o.creature.hp = 0
                o.state = "dead"
        on_turn(b, m)
        if sum(1 for e in b.enemies_of(m) if b.gap(m, e) <= 2) < 3:
            continue
        tactics.take_turn(b, m)
        if "invisibility" in cast_events(b, m):
            assert "invisible" in m.conditions or m.concentration is not None
            return
    pytest.fail("a hurt mage among blades never vanished")


def swordsmen(tables, n=4, level=8):
    """Fighters with blades and nothing to shoot or throw."""
    out = []
    for s in range(n):
        c = hero(tables, "fighter", seed=10 + s, level=level)
        c.inventory = [it for it in c.inventory if "range" not in tables.items.get(it.def_id)
                       and "thrown" not in tables.items.get(it.def_id).get("properties", ())]
        out.append(c)
    return out


def test_a_mage_rises_above_swordsmen(tables):
    from realmwalker.rules import tactics

    b = fight(tables, swordsmen(tables), "mage", spots={0: (3, 4), 1: (3, 6), 2: (2, 5), 3: (4, 7), 4: (5, 5)})
    m = foe(b, "mage")
    from realmwalker.rules.engine import estimates

    assert all(estimates._strikes_only_close(b, e) for e in b.enemies_of(m))
    on_turn(b, m)
    tactics.take_turn(b, m)
    assert "fly" in cast_events(b, m)
    assert m.fly_speed >= 60


def test_an_archmage_reads_the_minds_it_cannot_see(tables):
    from realmwalker.rules import tactics

    c = hero(tables, "rogue", level=10)
    b = fight(tables, c, "archmage", spots={0: (3, 4), 1: (8, 4)})
    a = foe(b, "archmage")
    pc = next(f for f in b.fighters if f.side == PARTY)
    pc.conditions["invisible"] = -1
    pc.hidden = 20
    on_turn(b, a)
    tactics.take_turn(b, a)
    assert "detect_thoughts" in cast_events(b, a)


@pytest.mark.parametrize("healer, spell, held", [("priest", "lesser_restoration", "paralyzed"),
                                                  ("archpriest", "lesser_restoration", "paralyzed"),
                                                  ("archpriest", "greater_restoration", "petrified")])
def test_a_priest_frees_a_friend_held_by_what_the_prayer_ends(tables, healer, spell, held):
    from realmwalker.rules import tactics

    c = hero(tables, "fighter", level=8)
    b = fight(tables, c, healer, "mage", spots={0: (2, 4), 1: (8, 4), 2: (9, 4)})
    h, friend = foe(b, healer), foe(b, "mage")
    friend.conditions[held] = -1
    if spell == "greater_restoration":
        h.creature.uses["pool:divine_aid"] = 0  # (Lesser Restoration cannot end petrification anyway)
    on_turn(b, h)
    tactics.take_turn(b, h)
    assert spell in cast_events(b, h)
    assert held not in friend.conditions
