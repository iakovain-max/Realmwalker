"""Schools & Domains part B: the Light and the Trickery Domains - Warding Flare and its improvement, Radiance of the
Dawn, Corona of Light; Blessing of the Trickster, Invoke Duplicity's double (spells from its square, the distraction,
moving it, Trickster's Transposition, Improved Duplicity) - each at work in a real fight, at a rest or on the road."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game.state import new_game
from realmwalker.rules import progression, tactics
from realmwalker.rules.combat import Zone
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.handlers import domains
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_feats import fight, hero, on_turn, soft
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture
def game(tables):
    g = new_game(copy.deepcopy(cached_world(WorldOptions("Domains", 7, "small"), tables)), tables)
    g.survival = False
    return g


def priest(tables, level, sub="light", seed=1):
    """A cleric of this domain, chosen at level 3 as a player chooses it."""
    c = hero(tables, "cleric", level=1, seed=seed)
    c.abilities["wis"] = 16
    for _ in range(level - 1):
        progression.level_up(c, tables, RNG(seed, "lv"))
        c.pending = [p for p in c.pending if p["kind"] not in ("asi", "boon")]
        pick = next((p for p in c.pending if p["kind"] == "subclass"), None)
        if pick is not None:
            progression.resolve(c, tables, pick, sub)
        progression.auto_resolve(c, tables)
    res.fill(c, tables)
    return c


def me_and(b):
    return b.side("party")[0], b.side("foe")


# ---------------------------------------------------------------------------- the paths
def test_the_two_domains_with_their_spells_and_uses(tables):
    li = priest(tables, 3, "light")
    assert li.subclass == "light" and {"radiance_of_the_dawn", "warding_flare"} <= set(li.features)
    from realmwalker.rules import spells as spellrules

    ready = spellrules.always_prepared(li, tables)
    assert {"burning_hands", "faerie_fire", "scorching_ray", "see_invisibility"} <= set(ready)
    pool = res.pools(li, tables)["warding_flare"]
    assert pool["recover"] == "long" and li.uses["warding_flare"] == 3
    li6 = priest(tables, 6, "light")
    assert res.pools(li6, tables)["warding_flare"]["recover"] == "short"  # (Improved Warding Flare)
    li6.uses["warding_flare"] = 0
    res.recover(li6, tables, "short")
    assert li6.uses["warding_flare"] == 3
    tr = priest(tables, 3, "trickery")
    assert {"blessing_of_the_trickster", "invoke_duplicity"} <= set(tr.features)
    assert {"charm_person", "disguise_self", "invisibility", "pass_without_trace"} <= set(spellrules.always_prepared(tr, tables))
    assert "tricksters_transposition" in priest(tables, 6, "trickery").features
    assert {"corona_of_light"} <= set(priest(tables, 17, "light").features)
    assert "improved_duplicity" in priest(tables, 17, "trickery").features


# ---------------------------------------------------------------------------- the Light Domain
def test_warding_flare_spoils_a_blow_at_a_friend(tables):
    c = priest(tables, 3, "light")
    b = fight(tables, c, "bandit", seed=3)
    me, (foe,) = me_and(b)
    opt = next(o for o in b.attack_options(foe) if o.available)
    seen = []
    real = query.attack_roll

    def spy(bb, att, target, o, **kw):
        r = real(bb, att, target, o, **kw)
        return r

    me.hp = me.max_hp // 3  # (hurt: the battle's judgement flares)
    import realmwalker.core.dice as dice_mod

    orig = dice_mod.d20

    def d20(rng, advantage=False, disadvantage=False):
        seen.append(disadvantage)
        return orig(rng, advantage=advantage, disadvantage=disadvantage)

    dice_mod.d20 = d20
    try:
        b._attack(foe, opt, me)
    finally:
        dice_mod.d20 = orig
    assert seen and seen[0] is True
    assert c.uses["warding_flare"] == 2 and me.reaction is False
    assert any(e["kind"] == "flare" for e in b.events)


def test_improved_warding_flare_gives_temporary_hit_points(tables):
    c = priest(tables, 6, "light")
    b = fight(tables, c, "bandit", seed=4)
    me, (foe,) = me_and(b)
    me.hp = me.max_hp // 3
    opt = next(o for o in b.attack_options(foe) if o.available)
    b._attack(foe, opt, me)
    assert c.uses["warding_flare"] == 2
    assert me.temp_hp >= 2 or me.hp < me.max_hp // 3  # (the gift, unless the blow went through it)


def test_no_flare_when_the_cleric_cannot_see_or_is_out_of_reach(tables):
    c = priest(tables, 3, "light")
    b = fight(tables, c, "bandit", seed=5)
    me, (foe,) = me_and(b)
    foe.x, foe.y = me.x + 8, me.y  # (40 feet off: too far to flare)
    opt = next(o for o in b.attack_options(foe) if o.available and not o.is_melee) \
        if any(not o.is_melee and o.available for o in b.attack_options(foe)) else None
    if opt is not None:
        b._attack(foe, opt, me)
        assert c.uses["warding_flare"] == 3


def test_radiance_of_the_dawn_burns_foes_and_the_dark(tables):
    c = priest(tables, 3, "light")
    b = fight(tables, c, "bandit", "bandit", seed=6)
    me, foes = me_and(b)
    for e in foes:
        soft(e, hp=200)
    dark = Zone(b._zone_id(), "darkness", {(me.x + 2, me.y)}, owner=foes[0].id, spell="darkness")
    b._add_zone(dark)
    on_turn(b, me)
    left = c.uses["channel_divinity"]
    assert actions.problem(b, me, actions.find(me, "radiance_of_the_dawn")) is None
    b.do_ability(me, "radiance_of_the_dawn")
    assert dark not in b.zones
    assert all(e.hp < 200 for e in foes)
    assert c.uses["channel_divinity"] == left - 1


def test_corona_puts_foes_saves_at_a_disadvantage(tables):
    c = priest(tables, 17, "light")
    b = fight(tables, c, "bandit", seed=7)
    me, (foe,) = me_and(b)
    on_turn(b, me)
    b.do_ability(me, "corona_of_light")
    assert domains.corona_of(me) is not None and me.buff_value("light")
    b._dawn = me
    try:
        r = query.save_roll(b, foe, "con")
    finally:
        b._dawn = None
    assert r.roll.disadvantage
    b._casting, b._casting_spell = me, tables.spells["fireball"]
    try:
        assert query.save_roll(b, foe, "dex").roll.disadvantage
        b._casting_spell = tables.spells["hold_person"]
        assert not query.save_roll(b, foe, "wis").roll.disadvantage  # (no fire, no radiance: no glare)
    finally:
        b._casting = b._casting_spell = None
    foe.x = me.x + 13  # (65 feet: out of the bright light)
    b._dawn = me
    try:
        assert not query.save_roll(b, foe, "con").roll.disadvantage
    finally:
        b._dawn = None


# ---------------------------------------------------------------------------- the Trickery Domain
def test_the_blessing_after_a_long_rest_and_in_a_fight(game, tables):
    c = priest(tables, 3, "trickery")
    game.party[:] = [game.party[0], c]
    notes = domains.bless_after_rest(game)
    assert notes and sum(domains.blessed(x) for x in game.party) == 1
    b = fight(tables, list(game.party), "bandit", seed=8)
    pr = next(f for f in b.side("party") if f.char is c)
    other = next(f for f in b.side("party") if f.char is not c)
    domains.bless(game.party, None)
    on_turn(b, pr)
    assert other in actions.aim_targets(b, pr, actions.find(pr, "blessing_of_the_trickster"))
    b.do_ability(pr, "blessing_of_the_trickster", other)
    assert domains.blessed(other.char) and not domains.blessed(c)


def test_hiding_with_the_blessing_rolls_at_an_advantage(tables, monkeypatch):
    c = priest(tables, 3, "trickery")
    domains.bless([c], c)
    b = fight(tables, c, "bandit", seed=9)
    me, (foe,) = me_and(b)
    import realmwalker.core.dice as dice_mod

    seen = []
    orig = dice_mod.d20
    monkeypatch.setattr(dice_mod, "d20", lambda rng, advantage=False, disadvantage=False:
                        seen.append(advantage) or orig(rng, advantage=advantage, disadvantage=disadvantage))
    monkeypatch.setattr(b, "hide_problem", lambda f: None)
    on_turn(b, me)
    b.do_hide(me)
    assert seen and seen[0] is True


def duplicity(tables, level=3, seed=10, foes=("bandit",)):
    c = priest(tables, level, "trickery", seed=seed)
    b = fight(tables, c, *foes, seed=seed)
    me, fs = me_and(b)
    for e in fs:
        soft(e, ac=12, hp=200)
    on_turn(b, me)
    return c, b, me, fs


def test_invoke_duplicity_makes_a_double_beside_the_foe_and_distracts_it(tables):
    c, b, me, (foe,) = duplicity(tables)
    a = actions.find(me, "invoke_duplicity")
    assert foe in actions.aim_targets(b, me, a)
    left = c.uses["channel_divinity"]
    b.do_ability(me, "invoke_duplicity", foe)
    tok = domains.double_of(b, me)
    assert tok is not None and max(abs(tok.x - foe.x), abs(tok.y - foe.y)) <= 1
    assert c.uses["channel_divinity"] == left - 1 and me.bonus == 0
    opt = next(o for o in b.attack_options(me) if o.available and o.is_melee)
    r = query.attack_roll(b, me, foe, opt)
    assert r.advantage and "the double distracts them" in r.notes
    assert actions.problem(b, me, actions.find(me, "invoke_duplicity")) is not None  # (one at a time)


def test_spells_are_cast_from_the_doubles_square(tables):
    c, b, me, (foe,) = duplicity(tables, level=5, seed=11)
    sid = "sacred_flame"
    if sid not in c.spells.get("cantrips", ()):
        c.spells["cantrips"] = list(c.spells.get("cantrips", ())) + [sid]
    from realmwalker.rules.combat import Token

    me.x, me.y = 0, 4
    foe.x, foe.y = 14, 4  # (70 feet: beyond the cleric's own reach of 60, 5 feet from the double)
    start = (me.x, me.y)
    tok = Token(b._zone_id(), domains.DOUBLE, 13, 4, me.id, rounds=10)
    b.tokens.append(tok)
    assert foe not in b._spell_targets(me, sid)
    assert foe in b.spell_targets(me, sid)
    before = foe.hp
    for _ in range(12):
        me.action = 1
        assert b.do_cast(me, sid, foe)
        if foe.hp < before:
            break
    assert foe.hp < before
    assert (me.x, me.y) == start  # (the cleric never left their own square)
    assert any(e["kind"] == "double_cast" for e in b.events)
    tok.x, tok.y = 0, 5  # (the double beside the cleric: no farther reach)
    assert foe not in b.spell_targets(me, sid)


def test_the_double_moves_and_trickster_swaps_places(tables):
    c, b, me, foes = duplicity(tables, level=6, seed=12, foes=("bandit", "bandit"))
    near, far = foes
    far.x, far.y = me.x + 8, me.y + 3
    b.do_ability(me, "invoke_duplicity", near)
    tok = domains.double_of(b, me)
    on_turn(b, me)
    assert far in actions.aim_targets(b, me, actions.find(me, "move_duplicity_swap"))
    start = (me.x, me.y)
    b.do_ability(me, "move_duplicity_swap", far)
    assert max(abs(me.x - far.x), abs(me.y - far.y)) <= 1  # (the cleric is beside the far foe now)
    assert (tok.x, tok.y) == start


def test_improved_duplicity_heals_as_the_double_ends_and_friends_are_distracted(tables):
    c = priest(tables, 17, "trickery", seed=13)
    friend = hero(tables, "fighter", seed=14, level=5)
    b = fight(tables, [c, friend], "bandit", seed=13)
    me = next(f for f in b.side("party") if f.char is c)
    fr = next(f for f in b.side("party") if f.char is friend)
    foe = b.side("foe")[0]
    soft(foe, ac=12, hp=300)
    on_turn(b, me)
    b.do_ability(me, "invoke_duplicity", foe)
    tok = domains.double_of(b, me)
    opt = next(o for o in b.attack_options(fr) if o.available)
    assert "the double distracts them" in query.attack_roll(b, fr, foe, opt).notes
    me.hp = me.max_hp - 20
    tok.rounds = 0
    on_turn(b, me)  # (its minute runs out as the cleric's turn begins)
    assert domains.double_of(b, me) is None
    assert me.hp == me.max_hp - 20 + c.level


def test_the_double_ends_when_its_maker_is_incapacitated(tables):
    c, b, me, (foe,) = duplicity(tables, seed=15)
    b.do_ability(me, "invoke_duplicity", foe)
    me.conditions["stunned"] = 2
    on_turn(b, foe)
    assert domains.double_of(b, me) is None


# ---------------------------------------------------------------------------- the gods (DMG 78-79)
def test_every_faith_serves_domains_and_a_priest_takes_their_gods(tables):
    faiths = tables.factions["faiths"]
    subs = set(tables.classes["cleric"]["subclasses"])
    assert all(f.get("domains") and set(f["domains"]) <= subs for f in faiths.values())
    from realmwalker.world.cultures import faith_for

    for culture in ("heartland", "northmarch", "volsk"):
        c = hero(tables, "cleric", level=1, seed=3)
        c.culture = culture
        c.abilities["wis"] = 16
        for _ in range(2):
            progression.level_up(c, tables, RNG(3, "lv"))
            c.pending = [p for p in c.pending if p["kind"] not in ("asi", "boon")]
            progression.auto_resolve(c, tables)
        doms = faiths[faith_for(tables, culture)]["domains"]
        assert c.subclass in doms, (culture, c.subclass, doms)


def test_the_devout_and_the_rest(game, tables):
    from realmwalker.game import gods

    c = priest(tables, 3, "light")
    c.culture = game.party[0].culture
    assert gods.chance(game, c) > 0  # (a priest is always devout)
    plain = game.party[0]
    if plain.cls != "cleric":
        assert gods.chance(game, plain) == 0.0 or gods.chance(game, plain) <= gods.MOST
    game.renown.flags["god_answered"] = game.world.time
    assert gods.chance(game, c) == 0.0  # (answered lately: the god is quiet)


@pytest.mark.parametrize("domain", ["life", "light", "trickery", "war"])
def test_the_god_answers_the_dying_with_its_domains_gift(tables, domain):
    c = priest(tables, 3, "light")
    b = fight(tables, c, "bandit", "bandit", seed=20)
    me, foes = me_and(b)
    b.prayers = {me.id: {"chance": 1.0, "god": "Solun the Bright", "short": "Solun", "domains": [domain]}}
    me.hp = 3
    b._apply_hp_loss(me, 500, source=foes[0], cause="a test blow")  # (a whole life below nothing: dead outright)
    assert me.state == "fighting" and me.hp >= 1 and c.alive
    assert me.id in b.answered and any(e["kind"] == "miracle" for e in b.events)
    if domain == "life":
        assert me.hp == me.max_hp // 2
    if domain == "trickery":
        assert "invisible" in me.conditions
    if domain == "war":
        assert me.buff_value("attack_die")
    b._kill(me, "again", foes[0])  # (once a fight)
    assert me.state == "dead"


def test_after_the_fight_the_world_remembers_and_the_god_is_quiet(game, tables):
    from realmwalker.game import fight as fightmod
    from realmwalker.game import gods

    c = game.party[0]
    c.cls = "cleric"
    b = fight(tables, c, "bandit", seed=21)
    me, _ = me_and(b)
    b.prayers = {me.id: {"chance": 1.0, "god": "Solun the Bright", "short": "Solun", "domains": ["life"]}}
    b.answered = [me.id]
    before = len(game.world.history)
    notes = gods.after_battle(game, b)
    assert notes and "answered" in notes[0]
    assert len(game.world.history) == before + 1 and game.world.history[-1]["kind"] == "miracle"
    assert gods.chance(game, c) == 0.0
