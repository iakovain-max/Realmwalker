"""Lasting protections and the caster's keeping (Expansion 3 part E.6, docs/expansions/03-demigods-magics.md).

Road ops `does` "protect" (`how`: glyph, symbol, guards, forbiddance, circle, sanctum), "hallow", "demiplane" and
"cauldron" (rules/spells.E6_KINDS), through game/spellwork's door (subjects, problem, cast).

A protection on a camp is a camp ward (`Camp.wards`, as E.1's: game/spellwork.wards_here): it stands where the party
rests, in the wild or underground, and is left behind when the party moves on. A hallowed place is the world's, for
good (`world.politics["hallowed"]`). What they do is read by the rest of the game:
    night(game, enc)        the night's visitors meet the wards first (from spellwork.night_visitors)
    keeps_out(game)         underground, may the party rest while hunters search the level (from spellwork.hidden)
    at_the_start(game, b)   a fight at the camp or on hallowed ground (from fight.start_battle)
    unseen_camp(game)       Private Sanctum: the camp is dark fog and silence from outside (fight.rest)
    room_thief(game, rng)   a glyph in your room at the inn meets the night's thief (services._night)
    scar["laid"]            a haunted field hallowed with Peaceful Rest (read by game/past.restless, encounters)
    brewed(item)            a potion from Tasha's cauldron: no merchant buys it (economy.sell_price)
"""
from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character
from realmwalker.rules.inventory import add_existing, add_item, distinct_packs, remove_item

DAY = 24 * 60
GLYPH_WAITS = 365 * DAY  # a glyph waits until it is set off: as long as you camp here (the camp is left behind)
RUNE_TYPES = ("fire", "cold", "lightning", "thunder", "acid")
SYMBOLS = {  # effect -> (the save, its words on the Spells page)
    "death": ("con", "Death: 10d10 necrotic, a Constitution save for half"),
    "discord": ("wis", "Discord: they quarrel among themselves (Disadvantage on attacks for a minute)"),
    "fear": ("wis", "Fear: Frightened, they run from it"),
    "pain": ("con", "Pain: Incapacitated for a minute"),
    "sleep": ("wis", "Sleep: Unconscious for ten minutes, until hurt"),
    "stunning": ("wis", "Stunning: Stunned for a minute"),
}
SYMBOL_ROUNDS = {"discord": 10, "pain": 10, "sleep": 100, "stunning": 10}
SYMBOL_STATE = {"discord": "discord", "pain": "incapacitated", "sleep": "unconscious", "stunning": "stunned"}
CIRCLE_KINDS = ("celestial", "elemental", "fey", "fiend", "undead")
FORBIDDEN_KINDS = ("aberration", "celestial", "elemental", "fey", "fiend", "undead")
HALLOW_KINDS = ("aberration", "elemental", "fey", "fiend", "undead")  # (holy ground: celestials are welcome)
HALLOW_SQUARES = 12  # 60 feet
HALLOW_EXTRAS = {
    "courage": "Courage: nobody of the party can be Frightened in a fight here",
    "fear": "Fear: every foe here that is not a humanoid is Frightened",
    "resistance": "Resistance: the party resists necrotic damage here",
    "vulnerability": "Vulnerability: aberrations, elementals, fey, fiends and undead here are vulnerable to radiant",
    "peaceful_rest": "Peaceful Rest: the dead buried here never rise",
}
GUARDS_LOST = 0.5  # the fog: at each choice of way, half the time they believe they go the other way
SANCTUM_CHANCE = 0.5  # the night is half as likely to bring anything as a cold camp's
GLYPH_SPELL_MAX = 5


def _road(spell: dict) -> dict:
    return next((o for o in spell.get("effects", ()) if o.get("op") == "road"), {})


def _first(c) -> str:
    return esc(c.name.split()[0])


def _now(game) -> int:
    return int(game.world.time)


def _flags(game) -> dict:
    return game.renown.flags


def _kind(game, cr) -> str:
    return str(game.tables.creatures[cr.def_id].get("kind", ""))


def _town_id(game) -> int | None:
    lm = game.local
    if lm is None or lm.kind != "settlement":
        return None
    s = game.world.settlement_at(game.player.x, game.player.y)
    return s.id if s is not None else None


def _underground(game) -> bool:
    lm = game.local
    return lm is not None and lm.kind == "dungeon"


def _band_name(game, enc) -> str:
    return esc(game.tables.creatures.encounters.get(enc.group, {}).get("name", "them"))


# ---------------------------------------------------------------------------- the dice against a creature
def _save(game, cr, ability: str, dc: int, rng) -> bool:
    cdef = game.tables.creatures[cr.def_id]
    bonus = int((cdef.get("saves") or {}).get(ability, (int((cdef.get("abilities") or {}).get(ability, 10)) - 10) // 2))
    return dice.d20(rng).natural + bonus >= dc


def _hurt(game, cr, amount: int, dtype: str) -> int:
    """Damage to a creature before a fight, after its immunity, resistance and vulnerability. Returns what it took."""
    cdef = game.tables.creatures[cr.def_id]
    if dtype in cdef.get("immune", []):
        return 0
    if dtype in cdef.get("resist", []):
        amount //= 2
    if dtype in cdef.get("vulnerable", []):
        amount *= 2
    cr.hp -= amount
    if cr.hp <= 0:
        cr.hp = 0
        cr.alive = False
    return amount


def _immune_to(game, cr, cid: str) -> bool:
    return cid in game.tables.creatures[cr.def_id].get("condition_immune", [])


# ---------------------------------------------------------------------------- read by the rest of the game
def ward(game, key: str) -> dict | None:
    """The record of a protection standing at the camp here, or None."""
    from realmwalker.game import spellwork

    return spellwork.wards_here(game).get(key)


def hallowed_at(game) -> dict | None:
    """The hallowed ground the party stands on: in the open the map tile (any close-up map of it but the underground),
    underground within 60 feet of where it was hallowed."""
    p = game.player
    for rec in game.world.politics.get("hallowed", ()):
        if (rec["x"], rec["y"]) != (p.x, p.y):
            continue
        if rec.get("local") is None and not _underground(game):
            return rec
        if rec.get("local") is not None and rec["local"] == p.local_key and _underground(game) \
                and max(abs(rec["lx"] - p.lx), abs(rec["ly"] - p.ly)) <= HALLOW_SQUARES:
            return rec
    return None


def _kept_out(game) -> set[str]:
    """The kinds of creature that cannot come to the party here (a Magic Circle at the camp, hallowed ground)."""
    out: set[str] = set()
    if ward(game, "circle") is not None:
        out |= set(CIRCLE_KINDS)
    if hallowed_at(game) is not None:
        out |= set(HALLOW_KINDS)
    return out


def keeps_out(game) -> bool:
    """Underground, the hunters cannot reach the party's rest: Guards and Wards' fog and locked ways, or only kinds
    of creature that a Magic Circle or hallowed ground keeps out are hunting."""
    if ward(game, "guards") is not None:
        return True
    kept = _kept_out(game)
    lm = game.local
    if not kept or lm is None:
        return False
    hunters = [cr for a in lm.actors if a.alert for cr in a.creatures if cr.hp > 0]
    return bool(hunters) and all(_kind(game, cr) in kept for cr in hunters)


def unseen_camp(game) -> bool:
    """Private Sanctum: nothing outside sees the camp's fire or hears its sleepers."""
    return ward(game, "sanctum") is not None


def guards_the_animals(game) -> str:
    """Words for a protection that keeps rustlers from the animals, or ""."""
    if ward(game, "sanctum") is not None:
        return "Whoever came for the animals in the night found nothing but dark fog, and went away."
    if ward(game, "guards") is not None:
        return "Someone was at the animals in the small hours, lost their way in the fog, and went off with nothing."
    return ""


def brewed(item) -> bool:
    """A potion from Tasha's Bubbling Cauldron: it is magic's own, and no merchant buys it."""
    return any(t.startswith("cauldron:") for t in (getattr(item, "tags", None) or []))


def demiplane_things(game) -> list[dict]:
    """What is kept in the party's demiplane: item records (nothing on this side weighs, wears, sells or steals them)."""
    return list((_flags(game).get("demiplane") or {}).get("items") or [])


def tick(game) -> None:
    """As time passes: a glyph in your room at the inn is no longer yours once you leave the town."""
    room = _flags(game).get("glyph_room")
    if room is not None:
        s = game.world.settlement_at(game.player.x, game.player.y)
        if s is None or s.id != room.get("settlement"):
            del _flags(game)["glyph_room"]


def room_thief(game, rng) -> str | None:
    """The night's thief at the inn sets off the glyph in your room (and it is spent). Words, or None."""
    room = _flags(game).get("glyph_room")
    s = game.world.settlement_at(game.player.x, game.player.y)
    if room is None or s is None or s.id != room.get("settlement"):
        return None
    del _flags(game)["glyph_room"]
    if room.get("how") == "symbol":
        what = {"death": "a cry, and then nothing", "discord": "two voices quarrelling in the passage, going away",
                "fear": "running feet in the passage", "pain": "a scream, and someone crawling away",
                "sleep": "a thud against the door, and later someone stumbling off", "stunning": "a thud, and later "
                "someone stumbling off"}.get(room.get("effect"), "a cry")
        return (f"<good>In the night the symbol on your door flares:</> you hear {what}. In the morning your things "
                "are all there.")
    return (f"<good>In the night the glyph on your door bursts with {esc(room.get('type', 'fire'))}:</> a yell, and "
            "running feet. In the morning your things are all there, and the door is scorched.")


# ---------------------------------------------------------------------------- the night
def night(game, enc) -> tuple[object, list[str]]:
    """What the camp's lasting protections do to the night's visitors, before the older wards (game/spellwork):
    hallowed ground and a Magic Circle keep their kinds out, Guards and Wards' fog leads them astray, a glyph or a
    symbol on the way in is set off, Forbiddance burns its kinds. Returns the encounter (None when nothing comes on)
    and what to say."""
    notes: list[str] = []
    acted = False
    rng = game.world.rng.child(f"warding/night/{game.world.time}")
    kept = _kept_out(game)
    if kept:
        out = [cr for cr in enc.creatures if cr.hp > 0 and _kind(game, cr) in kept]
        if out:
            enc.creatures = [cr for cr in enc.creatures if cr not in out]
            where = "the hallowed ground" if hallowed_at(game) is not None and ward(game, "circle") is None \
                else "the glowing ring of runes"
            if not [cr for cr in enc.creatures if cr.hp > 0]:
                return None, [f"<good>In the night something comes to the edge of {where}, and can come no further.</> "
                              "After a long while it goes away."]
            notes.append(f"<good>Some of them stop at the edge of {where} and can come no further;</> the rest come on.")
            acted = True
    if ward(game, "guards") is not None:
        if rng.chance(GUARDS_LOST):
            return None, notes + ["<good>In the night something blunders about in the fog round the camp, turns the "
                                  "wrong way at every turn, and goes off into the dark.</>"]
        notes.append("<warn>A mouth in the fog cries out: something has found its way through to the camp.</>")
        acted = True
    for key in ("glyph", "symbol"):
        rec = ward(game, key)
        if rec is not None and not rec.get("fired"):
            notes += _set_off(game, enc, key, rec, rng)
            acted = True
    rec = ward(game, "forbiddance")
    if rec is not None:
        burnt = [cr for cr in enc.creatures if cr.hp > 0 and _kind(game, cr) in FORBIDDEN_KINDS]
        if burnt:
            for cr in burnt:
                _hurt(game, cr, dice.roll(rec.get("dice", "5d10"), rng).total, rec.get("type", "radiant"))
            notes.append(f"<good>Light flares {'white' if rec.get('type') == 'radiant' else 'black'} at the edge of "
                         f"the camp:</> the forbidden ground burns what comes into it.")
            acted = True
    if acted:
        enc.asleep, enc.warned = False, True
    if not [cr for cr in enc.creatures if cr.hp > 0]:
        return None, notes + ["<good>Nothing of them comes on.</>"]
    return enc, notes


def _set_off(game, enc, key: str, rec: dict, rng) -> list[str]:
    """A glyph or a symbol on the way into the camp, set off by the night's band."""
    dc = int(rec.get("dc", 13))
    alive = [cr for cr in enc.creatures if cr.hp > 0]
    band = _band_name(game, enc)
    if key == "glyph" and rec.get("kind") == "spell":
        rec["fired"] = True  # (the stored spell strikes the first of them as the fight begins: at_the_start)
        name = game.tables.spells[rec["spell"]]["name"] if rec.get("spell") in game.tables.spells else "a spell"
        return [f"<warn>A glyph flares on the path into the camp:</> {band} have set it off, and you are awake. "
                f"<dim>({esc(name)} waits in it for the first of them.)</>"]
    del game.camp.wards[key]
    if key == "glyph":
        dtype = rec.get("type", "fire")
        hurt = 0
        for cr in alive:
            dmg = dice.roll(rec.get("dice", "5d8"), rng).total
            if _save(game, cr, "dex", dc, rng):
                dmg //= 2
            hurt += _hurt(game, cr, dmg, dtype)
        dead = len([cr for cr in alive if cr.hp <= 0])
        return [f"<warn>A glyph on the path into the camp erupts in {esc(dtype)}</> as {band} cross it: you are awake. "
                f"<dim>({rec.get('dice', '5d8')} {esc(dtype)}, Dexterity save DC {dc} for half)</>"
                + (f" <good>{dead} of them fall{'s' if dead == 1 else ''}.</>" if dead else "")]
    effect = rec.get("effect", "death")
    ability = SYMBOLS[effect][0]
    took, fled = 0, []
    for cr in alive:
        if effect == "death":
            dmg = dice.roll(rec.get("dice", "10d10"), rng).total
            if _save(game, cr, ability, dc, rng):
                dmg //= 2
            if _hurt(game, cr, dmg, "necrotic") > 0:
                took += 1
            continue
        state = "frightened" if effect == "fear" else SYMBOL_STATE[effect]
        if (state != "discord" and _immune_to(game, cr, state)) or _save(game, cr, ability, dc, rng):
            continue
        took += 1
        if effect == "fear":
            fled.append(cr)
        else:
            cr.conditions[state] = SYMBOL_ROUNDS[effect]
    if fled:
        enc.creatures = [cr for cr in enc.creatures if cr not in fled]
    words = {"death": "the air turns cold as a tomb", "discord": "they turn on one another, shouting",
             "fear": "they cry out and run", "pain": "they double up in agony", "sleep": "they drop where they stand, "
             "asleep", "stunning": "they stand reeling, senseless"}[effect]
    dead = len([cr for cr in alive if cr.hp <= 0])
    return [f"<warn>A symbol on the path into the camp blazes as {band} cross it:</> you are awake. "
            + (f"<good>{took} of them: {words}.</>" if took else "They shrug it off.")
            + (f" <good>{dead} fall dead.</>" if dead else "")
            + f" <dim>({esc(SYMBOLS[effect][1])}; DC {dc})</>"]


# ---------------------------------------------------------------------------- the fight
def at_the_start(game, battle) -> list[str]:
    """A fight at the camp or on hallowed ground begins: the stored spell of a glyph set off strikes the first of
    them; Forbiddance burns its kinds at the end of their turns; a Magic Circle wards the party against its kinds;
    hallowed ground's blessing holds. Returns what to say (the battle's own log says the rest)."""
    from realmwalker.rules.combat import FOE, PARTY
    from realmwalker.rules.engine import durations

    out: list[str] = []
    party = [f for f in battle.side(PARTY) if f.char is not None]
    foes = [f for f in battle.side(FOE) if f.state == "fighting"]
    rec = ward(game, "glyph")
    if rec is not None and rec.get("fired"):
        del game.camp.wards["glyph"]
        caster = next((f for f in party if f.char.name == rec.get("by")), None)
        sid = rec.get("spell")
        if caster is None and foes:
            out.append("<dim>The glyph flares and gutters out: the one who drew it is not here to give its spell "
                       "form.</>")
        if caster is not None and foes and sid in game.tables.spells:
            from realmwalker.rules.engine import effects

            spell = game.tables.spells[sid]
            first = foes[0]
            target = first if spell["target"] == "enemy" else None
            point = (first.x, first.y) if spell["target"] == "point" or spell.get("area") else None
            battle.say(f"The glyph's stored <magic>{spell['name']}</> bursts out at {first.the_name}.", "magic")
            effects.cast(battle, caster, sid, spell, target, point, up=max(0, int(rec.get("slot", spell["level"]))
                                                                            - int(spell["level"])),
                         mod=int(rec.get("mod", 0)), dc=int(rec.get("dc", 13)), bonus=int(rec.get("bonus", 0)), mult=1,
                         level=int(rec.get("slot", spell["level"])), slotted=True)
    rec = ward(game, "forbiddance")
    by = next((f for f in party if f.char.name == (rec or {}).get("by")), party[0] if party else None)
    if rec is not None and by is not None:
        for f in foes:
            if f.kind in FORBIDDEN_KINDS:
                f.buffs.append({"dot": rec.get("dice", "5d10"), "dot_type": rec.get("type", "radiant"),
                                "dot_at": "end", "by": by.id, "source": "forbiddance", "dot_name": "Forbiddance"})
    if ward(game, "circle") is not None:
        for f in party:
            durations.buff(f, {"warded_kinds": list(CIRCLE_KINDS), "source": "magic_circle"})
    holy = hallowed_at(game)
    if holy is not None:
        extra = holy.get("extra")
        if extra == "courage":
            for f in party:
                durations.buff(f, {"immune": ["frightened"], "source": "hallow"})
                durations.remove(f, "frightened")
        elif extra == "resistance":
            for f in party:
                durations.buff(f, {"resist": ["necrotic"], "source": "hallow"})
        elif extra == "vulnerability":
            for f in foes:
                if f.kind in HALLOW_KINDS:
                    durations.buff(f, {"vulnerable": ["radiant"], "source": "hallow"})
        elif extra == "fear":
            for f in foes:
                if f.kind != "humanoid":
                    durations.give(battle, f, "frightened")
        if extra in ("courage", "resistance", "vulnerability", "fear"):
            out.append(f"<magic>You fight on hallowed ground.</> <dim>({esc(HALLOW_EXTRAS[extra])})</>")
    return out


# ---------------------------------------------------------------------------- what can be aimed at
def _slots_after(c: Character, t, first: int, second: int) -> bool:
    """Whether two slots can be spent: one of `first` or higher, then one of `second` or higher."""
    left = list(spellrules.slots_left(c, t))
    for need in (first, second):
        i = next((i for i in range(need - 1, len(left)) if left[i] > 0), None)
        if i is None:
            return False
        left[i] -= 1
    return True


def glyph_spells(game, c: Character) -> list[str]:
    """The prepared spells a glyph can hold: level 5 or lower, cast with an action at a foe or a point, without
    concentration, and a slot left for them besides the glyph's own."""
    t = game.tables
    out = []
    for sid in spellrules.known_spells(c, t):
        sp = t.spells[sid]
        if not 1 <= int(sp.get("level", 0)) <= GLYPH_SPELL_MAX or sp.get("concentration") \
                or spellrules.out_of_battle(sp) or sp.get("cast", "action") != "action" \
                or sp.get("target") not in ("enemy", "point") or "item" in sp.get("classes", ()):
            continue
        if spellrules.component_problem(c, t, sid) or not _slots_after(c, t, 3, int(sp["level"])):
            continue
        out.append(sid)
    return sorted(out, key=lambda s: (-int(t.spells[s]["level"]), t.spells[s]["name"]))


def _demiplane_loads(game) -> list[Subject]:
    from realmwalker.game.stonework import _goes_in
    from realmwalker.rules.inventory import carried
    from realmwalker.game.economy import money_text

    worn = {uid for c in game.party for uid in c.equipped.values() if uid is not None}
    things = list(carried(game.party))
    treasure = [it for it in things if it.def_id != "leomunds_chest" and _goes_in(game, it, "treasure", worn)]
    arms = [it for it in things if it.def_id != "leomunds_chest" and _goes_in(game, it, "arms", worn)]
    money = sum(c.money for c in game.party)
    out = []
    if treasure or money:
        out.append(Subject(f"leave the coin and the treasure there ({money_text(money)}, {len(treasure)} things)",
                           "load", "treasure"))
    if arms:
        out.append(Subject(f"leave the spare arms and armour there ({len(arms)} things)", "load", "arms"))
    if arms and (treasure or money):
        out.append(Subject("leave all of it there", "load", "all"))
    kept = _flags(game).get("demiplane") or {}
    if kept.get("items") or kept.get("money"):
        out.append(Subject(f"take back everything kept there ({len(kept.get('items') or [])} things"
                           + (f", {money_text(int(kept.get('money', 0)))}" if kept.get("money") else "") + ")",
                           "load", "back"))
    out.append(Subject("only a room out of the world to rest in, for the hour", "load", "room"))
    return out


def potions(game) -> list[str]:
    """The potions Tasha's cauldron can brew: the common and uncommon ones the game has."""
    items = game.tables.items
    out = []
    for iid, d in items.defs.items():
        if isinstance(d, dict) and iid.startswith("potion") and d.get("rarity") in ("common", "uncommon") \
                and not d.get("rare"):
            out.append(iid)
    return sorted(out, key=lambda i: (int(items.get(i).get("value", 0)), i))


def subjects(game, caster, sid: str) -> list[Subject]:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does, how = o.get("does"), o.get("how")
    if does == "protect" and how == "glyph":
        out = [Subject(f"an explosive rune of {t} ({_glyph_dice(o, None)})", "rune", t) for t in RUNE_TYPES]
        t = game.tables
        for s in glyph_spells(game, caster):
            out.append(Subject(f"a spell glyph holding {t.spells[s]['name']} (level {t.spells[s]['level']})",
                               "spell", s))
        return out
    if does == "protect" and how == "symbol":
        return [Subject(words, "symbol", key) for key, (_, words) in SYMBOLS.items()]
    if does == "protect" and how == "forbiddance":
        return [Subject("radiant: white fire", "damage", "radiant"), Subject("necrotic: black frost", "damage",
                                                                             "necrotic")]
    if does == "hallow":
        return [Subject(words, "blessing", key) for key, words in HALLOW_EXTRAS.items()]
    if does == "demiplane":
        return _demiplane_loads(game)
    if does == "cauldron":
        items = game.tables.items
        return [Subject(items.get(i)["name"], "potion", i) for i in potions(game)]
    return []


def _glyph_dice(o: dict, level: int | None) -> str:
    base = str(o.get("dice", "5d8"))
    n, die = base.split("d")
    return f"{int(n) + max(0, (level or 3) - 3)}d{die}"


def problem(game, caster, sid: str, target) -> str | None:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does, how = o.get("does"), o.get("how")
    aimed = target is not None and not isinstance(target, Character)
    if does == "protect":
        town = _town_id(game) is not None
        if how in ("glyph", "symbol"):
            if town:
                if _flags(game).get("glyph_room", {}).get("settlement") == _town_id(game):
                    return "a glyph already guards your room here"
            elif game.local is not None:  # (the night comes to a camp on the wide map; nothing comes underground)
                return "only on the way into a camp in the open country (off the close-up map), or your room at an inn"
            elif ward(game, how) is not None and not ward(game, how).get("fired"):
                return f"a {how} already waits on the way into the camp"
            if how == "glyph" and aimed and target.kind == "spell" and target.ref not in glyph_spells(game, caster):
                return "no spell slot left for the spell it would hold"
        else:
            if town:
                return "not in the middle of a town"
            rec = ward(game, how if how != "circle" else "circle")
            if rec is not None and float(rec["until"]) - game.world.time > 60:
                return f"it is still working here ({max(1, round((float(rec['until']) - game.world.time) / 60))}h left)"
        if how in ("glyph", "symbol", "forbiddance") and not aimed:
            return "choose which (←→)"
    if does == "hallow":
        if hallowed_at(game) is not None:
            return "this ground is hallowed already"
        if not aimed:
            return "choose its blessing (←→)"
    if does == "demiplane" and not aimed:
        return "choose what to do there (←→)"
    if does == "cauldron":
        if not potions(game):
            return "there is no potion it knows how to brew"
        if not aimed:
            return "choose the potion (←→)"
    return None


# ---------------------------------------------------------------------------- the castings
def _camp_ward(game, caster, key: str, minutes: int, sdef: dict, /, **more) -> dict:
    """A protection on the camp here (made if there is none): its record, kept in `Camp.wards`."""
    from realmwalker.game.camp import make_camp

    camp = make_camp(game)
    dc = spellrules.save_dc(game.sheet(caster), game.tables)
    # (from the end of the casting: its minutes are still to pass)
    rec = {"until": game.world.time + minutes + int(sdef.get("minutes", 1)), "dc": int(dc), "by": caster.name,
           **more}
    camp.wards[key] = rec
    return rec


def _protect(game, caster, sid: str, spell: dict, o: dict, target, level: int) -> list[str]:
    how = o["how"]
    first = _first(caster)
    t = game.tables
    if how in ("glyph", "symbol") and _town_id(game) is not None:
        rec = {"settlement": _town_id(game), "how": how, "dc": spellrules.save_dc(game.sheet(caster), t)}
        if how == "glyph":
            rec["type"] = target.ref if target.kind == "rune" else "fire"
        else:
            rec["effect"] = target.ref
        _flags(game)["glyph_room"] = rec
        return [f"{first} draws a {'glyph' if how == 'glyph' else 'symbol'} on a door-sized slate and it fades from "
                "sight: hung on the door of whatever room you take at the inn here, it will meet whoever comes in the "
                "night. <dim>(It waits while you stay in this town.)</>"]
    if how == "glyph":
        if target.kind == "spell":
            stored = target.ref
            sp = t.spells[stored]
            slot = spellrules.lowest_free_slot(caster, t, int(sp["level"]))
            if slot is None:  # (a higher slot spent on the glyph took the one it would have used: nothing is lost)
                spellrules.unspend_slot(caster, level)
                for m in (spell.get("material") or {}).get("items", ())[:1]:
                    add_item(caster, t.items, m)
                return ["The glyph begins to take shape, but no spell slot is left for the spell it would hold: "
                        f"{first} stops, and keeps the dust and the slot."]
            spellrules.spend_slot(caster, slot)
            spellrules.spend_material(caster, t, stored)
            s = game.sheet(caster)
            _camp_ward(game, caster, "glyph", GLYPH_WAITS, spell, kind="spell", spell=stored, slot=slot,
                       mod=s.mod(spellrules.casting_ability(caster, t)),
                       bonus=spellrules.attack_bonus(s, t))
            return [f"{first} traces a glyph across the path into the camp for an hour, and speaks "
                    f"<magic>{esc(sp['name'])}</> into it; it fades from sight. It will strike the first thing that "
                    "comes in the night."]
        _camp_ward(game, caster, "glyph", GLYPH_WAITS, spell, kind="rune", type=target.ref, dice=_glyph_dice(o, level))
        return [f"{first} traces a glyph across the path into the camp for an hour, and it fades from sight. "
                f"Whatever comes in the night will meet a burst of {esc(target.ref)} "
                f"<dim>({_glyph_dice(o, level)}, a Dexterity save for half)</>, and you will be awake."]
    if how == "symbol":
        _camp_ward(game, caster, "symbol", GLYPH_WAITS, spell, effect=target.ref, dice=o.get("dice", "10d10"))
        return [f"{first} draws a symbol across the path into the camp in diamond dust, and it sinks out of sight. "
                f"Whatever comes in the night will meet it: <dim>{esc(SYMBOLS[target.ref][1])}.</>"]
    hours = int(o.get("hours", 24))
    if how == "circle":
        hours += int(o.get("per_up", 1)) * max(0, level - int(spell["level"]))
    lasts = f"{hours} hours" if hours > 1 else "an hour"
    if how == "guards":
        _camp_ward(game, caster, "guards", hours * 60, spell)
        return [f"{first} walks the camp's bounds for an hour with a silver rod: fog rises between the trees, the ways "
                f"in tangle, webs hang in the gaps, and a mouth opens in a stone to keep watch. It stands {lasts}."]
    if how == "forbiddance":
        _camp_ward(game, caster, "forbiddance", hours * 60, spell, type=target.ref, dice=o.get("dice", "5d10"))
        return [f"{first} scatters ruby dust round the camp and prays for ten minutes: for a day, aberrations, "
                f"celestials, elementals, fey, fiends and undead that come here will burn "
                f"<dim>({o.get('dice', '5d10')} {esc(target.ref)})</>."]
    if how == "circle":
        _camp_ward(game, caster, "circle", hours * 60, spell)
        return [f"{first} pours a ring of silvered salt round the camp, and runes glow where it falls: for {lasts}, "
                "celestials, elementals, fey, fiends and undead cannot come inside it."]
    if how == "sanctum":
        _camp_ward(game, caster, "sanctum", hours * 60, spell)
        return [f"{first} sets a sheet of lead on the ground and speaks for ten minutes: the camp's edge darkens into "
                f"fog that no eye or ear passes. It stands {lasts}."]
    return []


def _hallow(game, caster, target) -> list[str]:
    from realmwalker.game import past

    p = game.player
    under = _underground(game)
    rec = {"x": p.x, "y": p.y, "local": p.local_key if under else None, "lx": p.lx, "ly": p.ly,
           "kinds": list(HALLOW_KINDS), "extra": target.ref, "by": caster.name, "time": _now(game)}
    game.world.politics.setdefault("hallowed", []).append(rec)
    out = [f"<magic>{_first(caster)} burns the hallowing incense and prays through a day and a night,</> and the "
           "ground here grows holy: aberrations, elementals, fey, fiends and undead cannot come onto it, for good. "
           f"<dim>({esc(HALLOW_EXTRAS[target.ref])})</>"]
    if target.ref != "peaceful_rest":
        return out
    scar = past.scar_at(game.world, p.x, p.y) if not under else None
    s = game.world.settlement_at(p.x, p.y)
    if scar is not None and not scar.get("laid"):
        scar["laid"] = True
        out.append(f"<good>The dead of {esc(scar.get('name', 'the old battle'))} lie quiet now: they will not walk "
                   "again.</>")
        _deed(game, f"laid the dead of {scar.get('name', 'an old battle')} to rest", p.x, p.y,
              f"A priest prayed a day and a night over the field of {scar.get('name', 'an old battle')}; the folk say "
              "its dead walk no more.")
    elif s is not None and getattr(s, "owner", None) is not None:
        out.append(f"<good>The folk of {esc(s.name)} will bury their dead in peace, and remember who gave it.</>")
        _deed(game, f"hallowed the graves of {s.name}", p.x, p.y,
              f"A priest hallowed the graves of {s.name}: no dead of theirs will rise again.")
    return out


def _deed(game, text: str, x: int, y: int, news: str) -> None:
    from realmwalker.game import reputation
    from realmwalker.world import factions as fx

    w = game.world
    amounts = {}
    for s in w.settlements:
        if abs(s.x - x) + abs(s.y - y) <= 8:
            realm = fx.realm_of_settlement(w, s)
            if realm is not None:
                amounts[realm.id] = max(amounts.get(realm.id, 0.0), 3.0)
    if amounts:
        reputation.deed(game, text, amounts, x=x, y=y, fame=2, news_text=news)


def _demiplane(game, caster, spell: dict, o: dict, target) -> list[str]:
    from realmwalker.game.economy import money_text
    from realmwalker.game.stonework import _goes_in
    from realmwalker.rules.items import Item

    first = _first(caster)
    out = [f"{first} draws a door on the nearest stone with one finger, and it darkens into a real one: beyond it, "
           "a bare stone room thirty feet on a side, out of the world."]
    _camp_ward(game, caster, "demiplane", int(o.get("minutes_open", 60)), spell)
    kept = _flags(game).setdefault("demiplane", {"money": 0, "items": []})
    load = target.ref
    if load == "back":
        things = [add_existing(game.leader, game.tables.items, Item.from_dict(d)) for d in kept.get("items") or []]
        money = int(kept.get("money", 0))
        game.leader.money += money
        _flags(game)["demiplane"] = {"money": 0, "items": []}
        game.cue("chest")
        out.append(f"You carry out everything you left there: {len(things)} thing{'s' if len(things) != 1 else ''}"
                   + (f" and {money_text(money)}" if money else "") + ".")
    elif load in ("treasure", "arms", "all"):
        worn = {uid for c in game.party for uid in c.equipped.values() if uid is not None}
        n = 0
        for c in distinct_packs(game.party):
            for it in list(c.inventory):
                if it.def_id != "leomunds_chest" and _goes_in(game, it, load, worn):
                    gone = remove_item(c, it.uid)
                    if gone is not None:
                        kept["items"].append(gone.to_dict())
                        n += 1
        money = 0
        if load in ("treasure", "all"):
            for c in game.party:
                money += c.money
                c.money = 0
        kept["money"] = int(kept.get("money", 0)) + money
        out.append(f"You leave {n} thing{'s' if n != 1 else ''}" + (f" and {money_text(money)}" if money else "")
                   + " in the room. They will be there when the door is made again.")
    out.append("<dim>For the hour the door stands, the room is somewhere to rest that nothing outside can reach.</>")
    return out


def _cauldron(game, caster, target) -> list[str]:
    t = game.tables
    gone = 0
    for c in distinct_packs(game.party):
        for it in list(c.inventory):
            if brewed(it):
                gone += it.qty
                remove_item(c, it.uid)
    s = game.sheet(caster)
    n = max(1, s.mod(spellrules.casting_ability(caster, t)))
    add_item(game.leader, t.items, target.ref, n, made_at=_now(game), tags=[f"cauldron:{_now(game)}"])
    name = t.items.get(target.ref)["name"]
    out = [f"<magic>A claw-footed cauldron bubbles up out of nothing beside {_first(caster)},</> and {n} vial"
           f"{'s' if n != 1 else ''} of {esc(name)} are drawn from it before it sinks away."]
    if gone:
        out.append("<dim>The last cauldron's potions are gone from the pack.</>")
    return out


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    spell = game.tables.spells[sid]
    o = _road(spell)
    does = o.get("does")
    if isinstance(target, Character):
        target = None
    if does == "protect":
        return _protect(game, caster, sid, spell, o, target, level)
    if does == "hallow":
        return _hallow(game, caster, target)
    if does == "demiplane":
        return _demiplane(game, caster, spell, o, target)
    if does == "cauldron":
        return _cauldron(game, caster, target)
    return []
