"""Great magic (Expansion 3 part E.7, docs/expansions/03-demigods-magics.md): Contingency, Magic Jar, Clone,
Imprisonment, and Wish's other uses outside a fight.

Road ops `does` "contingency", "jar", "clone", "imprison" and Wish's `road_too` "wish" (rules/spells.ROAD_USES),
through game/spellwork's door (subjects, problem, cast). What they leave behind is read by the rest of the game:
    char.spells["contingency"]   {spell, slot, trigger, until}: rules/combat.Battle._contingency casts it in a fight
    char.spells["jar"]           {since, dc}: the soul in its gem (rules/combat: the body still, Possess and Return)
    renown.flags["clones"]       [{who, settlement, x, y, ready}]: `cheat_death` (the leader, from the screens that
                                 would open the death screen) and `clone_wakes` (a companion, from companions.died)
    char.spells["wished_resist"] damage types resisted for good (rules/engine/query.resists)
    char.effects["immune_spell:<id>"]  hours left of a wished immunity to one spell (rules/engine/effects.warded)
    char.spells["simulacrum"]    {of, char, made}: a Simulacrum's copy of a person (rules/simulacrum.py); a copy of a
                                 creature is a servant record with spell "simulacrum" (rules/servants.py) (G.3)
Imprisonment is cast from the meeting screen (`prison_casters`, `imprison`), as Tsunami is.
"""
from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character
from realmwalker.rules.inventory import add_item, carried, distinct_packs, remove_item

DAY = 24 * 60
TRIGGERS = {"start": "as a fight begins", "bloodied": "when brought below half the hit points",
            "down": "when they fall"}
CONTINGENT_MAX = 5
JAR_FEET = 100
CLONE_MILES_A_DAY = 24  # (the companions bring what the dead carried, as when sent for)
WISH_OBJECT_MAX = 2500000  # 25,000 GP, in copper
WISH_OBJECT_MIN = 10000  # (the list shows the things worth a wish: 100 GP and more)
IMMUNITY_HOURS = 8.0
RESHAPE_BEAST = 0.5  # that a beast of the songs were dead: half the time
RESHAPE_DRAGON = 0.25  # a dragon: a quarter
DAMAGE_TYPES = ("acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison",
                "psychic", "radiant", "slashing", "thunder")
PRISONS = {  # a creature's kind -> the form of its prison (the game's choice), and its words
    "dragon": ("burial", "is entombed far beneath the earth, in a hollow globe of force just large enough to hold it"),
    "undead": ("chaining", "is held fast by chains that rise out of the ground and root it where it stands, for ever"),
    "fiend": ("hedged", "is gone into a prison of its own, a labyrinth warded against every road out"),
    "celestial": ("hedged", "is gone into a prison of its own, a tower warded against every road out"),
    "fey": ("hedged", "is gone into a prison of its own, a cage of thorns warded against every road out"),
    "humanoid": ("minimus", "shrinks to an inch and is gone into a gem that lies on the grass, looking out"),
}
PRISON_ELSE = ("slumber", "sinks down into a sleep that nothing will ever wake it from")


def _road(spell: dict) -> dict:
    return next((o for o in spell.get("effects", ()) if o.get("op") == "road"), {})


def _first(c) -> str:
    return esc(c.name.split()[0])


def _now(game) -> int:
    return int(game.world.time)


def _flags(game) -> dict:
    return game.renown.flags


def _does(game, sid: str) -> str | None:
    spell = game.tables.spells[sid]
    return _road(spell).get("does") or spell.get("road_too")


# ---------------------------------------------------------------------------- Contingency
def contingent_spells(game, c: Character) -> list[str]:
    """The spells a Contingency can hold for this caster now: level 5 or lower, cast with an action, aimed at the
    caster (self or a friend), used in a fight, and a slot left for them besides Contingency's own."""
    from realmwalker.game.warding import _slots_after

    t = game.tables
    out = []
    for sid in spellrules.known_spells(c, t):
        sp = t.spells[sid]
        if not 1 <= int(sp.get("level", 0)) <= CONTINGENT_MAX or spellrules.out_of_battle(sp) \
                or sp.get("cast", "action") != "action" or sp.get("target") not in ("self", "ally") \
                or "item" in sp.get("classes", ()) or sp.get("again_of"):
            continue
        if spellrules.component_problem(c, t, sid) or not _slots_after(c, t, 6, int(sp["level"])):
            continue
        out.append(sid)
    return sorted(out, key=lambda s: (-int(t.spells[s]["level"]), t.spells[s]["name"]))


def contingency_words(game, c: Character) -> str | None:
    """What waits on someone (for the Spells page and the sheet), or None."""
    rec = (c.spells or {}).get("contingency")
    if not rec or rec.get("spell") not in game.tables.spells:
        return None
    left = max(0.0, float(rec["until"]) - game.world.time) / DAY
    return (f"{game.tables.spells[rec['spell']]['name']} waits on {_first(c)}, {TRIGGERS.get(rec['trigger'], '')} "
            f"({max(1, round(left))} day{'s' if round(left) != 1 else ''} left).")


def _contingency(game, caster: Character, sid: str, target, level: int) -> list[str]:
    t = game.tables
    o = _road(t.spells[sid])
    held = target.ref
    sp = t.spells[held]
    slot = spellrules.lowest_free_slot(caster, t, int(sp["level"]))
    out = []
    old = (caster.spells or {}).pop("contingency", None)
    if old:
        out.append(f"<dim>The {t.spells[old['spell']]['name']} that waited before is gone.</>")
    if slot is not None:
        spellrules.spend_slot(caster, slot)
    used = spellrules.spend_material(caster, t, held)
    caster.spells["contingency"] = {"spell": held, "slot": int(slot or sp["level"]), "trigger": target.data["trigger"],
                                    "until": _now(game) + int(o.get("days", 10)) * DAY}
    out.insert(0, f"<magic>{_first(caster)} speaks {sp['name']} into the jewelled statuette, and it waits there,</> "
                  f"{TRIGGERS[target.data['trigger']]}.")
    if used:
        out.append(f"<dim>The {used} is used up.</>")
    out.append(f"<dim>Both slots are spent. For ten days it will take effect on {_first(caster)} alone, without an "
               "action, the moment it comes; casting Contingency again ends this one.</>")
    return out


# ---------------------------------------------------------------------------- Magic Jar
def in_jar(c: Character | None) -> bool:
    return c is not None and bool((c.spells or {}).get("jar"))


def return_to_body(game, c: Character) -> list[str]:
    """Outside a fight: the soul goes back into its body, and the gem shatters."""
    if not in_jar(c):
        return []
    c.spells.pop("jar", None)
    game.dirty = True
    return [f"<magic>{_first(c)} draws a breath and opens their eyes:</> the soul is home, and the gem that held it "
            "cracks and falls to glittering pieces."]


def _jar(game, caster: Character, spell: dict) -> list[str]:
    s = game.sheet(caster)
    caster.spells["jar"] = {"since": _now(game), "dc": int(spellrules.save_dc(s, game.tables))}
    return [f"<magic>{_first(caster)}'s body goes slack,</> and a light moves in the gem in their hand: the soul is "
            "in it now.",
            f"<dim>The others carry the body along. In a fight it lies still where it is set down, and the soul may "
            f"leap {JAR_FEET} feet into a humanoid foe (a Charisma save) to fight with its body, or go home; outside a "
            "fight, cast Magic Jar again to go back (no slot). No other spell can be cast from the gem.</>"]


# ---------------------------------------------------------------------------- Clone
def clones(game) -> list[dict]:
    return _flags(game).setdefault("clones", [])


def clone_of(game, c: Character, *, ready: bool = False) -> dict | None:
    for rec in clones(game):
        if rec.get("who") == c.name and (not ready or game.world.time >= float(rec["ready"])):
            return rec
    return None


def _town(game):
    lm = game.local
    if lm is None or lm.kind != "settlement":
        return None
    s = game.world.settlement_at(game.player.x, game.player.y)
    return s if s is not None and s.kind in ("town", "city") else None


def _clone(game, caster: Character, spell: dict, target) -> list[str]:
    who = next((c for c in game.party if c.name == target.ref), caster)
    s = _town(game)
    for m in distinct_packs(game.party):
        it = next((it for it in m.inventory if it.def_id == "clone_vessel"), None)
        if it is not None:
            remove_item(m, it.uid, 1)
            break
    days = int(_road(spell).get("days", 120))
    clones(game).append({"who": who.name, "settlement": s.id if s is not None else -1,
                         "x": game.player.x, "y": game.player.y, "ready": _now(game) + days * DAY,
                         "made": _now(game)})
    place = esc(s.name) if s is not None else "this place"
    return [f"<magic>{_first(caster)} lays the flawless diamond on {_first(who)}'s skin for an hour of words,</> and "
            f"it is gone; in the sealed vessel something begins to grow. The priests of {place} carry it down into "
            "their crypt.",
            f"<dim>In {days} days it will be grown. If {_first(who)} dies after that, their soul will wake in it "
            f"here in {place}, whole, with nothing of what they carried.</>"]


def _restore(game, c: Character) -> None:
    from realmwalker.game import revival

    revival.return_to_life(game, c, {}, {"hp": "all", "closes": True, "regrow": True, "cures": True},
                           game.world.rng.child(f"clone/{c.name}/{game.world.time}"))
    c.blood = 100.0
    c.exhaustion = 0
    c.hunger = 0.0
    c.thirst = 0.0
    c.fatigue = 0.0
    c.body_heat = 0.0
    c.wounds = []
    from realmwalker.rules import health

    c.effects.pop(health.DEATH_TOLL, None)  # (a new body: the soul came straight to it)


def _strip(game, c: Character, to: Character | None) -> None:
    """The clone has none of the original's things: the companions take them up (else they are lost)."""
    from realmwalker.rules.inventory import add_existing

    c.equipped.clear()
    others = [m for m in list(game.party) + list(getattr(game, "waiting", []) or []) if m is not c]
    if any(m.inventory is c.inventory for m in others):  # (the party's one pack: it stays with them)
        c.inventory = []
        if to is not None:
            to.money += c.money
        c.money = 0
        return
    for it in list(c.inventory):
        gone = remove_item(c, it.uid, it.qty)
        if gone is not None and to is not None:
            add_existing(to, game.tables.items, gone)
    if to is not None:
        to.money += c.money
    c.money = 0


def cheat_death(game) -> list[str] | None:
    """The leader is dead (game.over is set): a grown clone takes their soul. Returns what to say, or None (the
    end)."""
    if game.over is None or not game.party:
        return None
    leader = game.party[0]
    rec = clone_of(game, leader, ready=True)
    if rec is None:
        return None
    clones(game).remove(rec)
    w = game.world
    s = w.settlements[rec["settlement"]] if 0 <= int(rec.get("settlement", -1)) < len(w.settlements) else None
    x, y = (s.x, s.y) if s is not None else (int(rec["x"]), int(rec["y"]))
    friends = [c for c in game.party[1:] if c.alive]
    from realmwalker.rules.inventory import take_out

    for c in friends[1:]:
        if c.inventory is leader.inventory:
            take_out(c, keep_gear=True)  # (each walks with what they wear; the first carries the pack)
    _strip(game, leader, friends[0] if friends else None)
    _restore(game, leader)
    if game.local is not None:
        game.leave_local()
    miles = (abs(game.player.x - x) + abs(game.player.y - y)) * 3
    days = miles / CLONE_MILES_A_DAY
    for c in friends:
        c.companion["order"] = "wait"
        c.companion["wait_at"] = [x, y]
        c.companion["coming"] = int(w.time + days * DAY)
        game.waiting.append(c)
    game.party = [leader]
    game.player.x, game.player.y = x, y
    game.over = None
    game.travel = None
    game.aftermath = None
    game.dirty = True
    place = esc(s.name) if s is not None else "the crypt"
    out = [f"<magic>Darkness, and then cold stone under your hands.</> You wake in the sealed vessel in the crypt "
           f"of {place}, naked and whole, the lid lifted by frightened priests. Your old body lies far away, and "
           "everything it carried with it."]
    if friends:
        out.append(f"<dim>{', '.join(_first(c) for c in friends)} gather what you left and set out for {place}: "
                   f"about {max(1, round(days))} day{'s' if round(days) != 1 else ''} on the road.</>")
    game.cue("heal")
    return out


def clone_wakes(game, c: Character) -> bool:
    """A companion is dead for good: a grown clone of theirs takes the soul, and they wait in its town."""
    rec = clone_of(game, c, ready=True) if c.companion else None
    if rec is None:
        return False
    clones(game).remove(rec)
    w = game.world
    s = w.settlements[rec["settlement"]] if 0 <= int(rec.get("settlement", -1)) < len(w.settlements) else None
    _strip(game, c, game.leader if game.party else None)  # (what they carried stayed with the party: pack.sync)
    _restore(game, c)
    c.companion["order"] = "wait"
    c.companion["wait_at"] = [s.x, s.y] if s is not None else [int(rec["x"]), int(rec["y"])]
    c.companion.pop("coming", None)
    game.party = [m for m in game.party if m is not c]
    if c not in game.waiting:
        game.waiting.append(c)
    game.say(f"<magic>But {_first(c)}'s soul does not go far:</> it wakes in the clone in the crypt of "
             f"{esc(s.name) if s is not None else 'its vessel'}, and {_first(c)} waits there for you.", "good")
    game.dirty = True
    return True


# ---------------------------------------------------------------------------- Imprisonment
def prison_casters(game) -> list[tuple[Character, str]]:
    """Who could bind a creature before a fight (Imprisonment ready, a slot and the statuette), with the spell."""
    t = game.tables
    out = []
    for c in game.party:
        if not c.alive or c.hp <= 0 or not c.spells:
            continue
        for sid in spellrules.known_spells(c, t):
            if _road(t.spells[sid]).get("does") != "imprison":
                continue
            ok, _ = spellrules.can_cast(c, t, sid)
            if ok and spellrules.lowest_free_slot(c, t, int(t.spells[sid]["level"])) is not None:
                out.append((c, sid))
    return out


def prisoner(game, enc):
    """The strongest of a band, the one Imprisonment would bind."""
    t = game.tables
    left = [cr for cr in enc.creatures if cr.alive and cr.hp > 0]
    return max(left, key=lambda cr: (float(t.creatures[cr.def_id].get("cr", 0)), cr.max_hp), default=None)


def _bound_in_the_world(game, cr) -> list[str]:
    """A named beast or a dragon of the world bound for good: the land counts it as rid of it."""
    from realmwalker.game import dragons, past

    w = game.world
    if not cr.named:
        return []
    d = next((d for d in dragons.living(w) if d.get("name") == cr.name), None)
    if d is not None:
        _wished_gone(game, d=d, how="bound")
        return [f"<good>The dragon {esc(d['name'])} is bound for good.</> <dim>The towns it taxed will hear it.</>"]
    for key, hid in list(w.politics.get("lairs", {}).items()):
        fig = w.figures.get(hid)
        if fig is not None and fig.alive and fig.name == cr.name:
            _wished_gone(game, fig=fig, site_id=int(key), how="bound")
            return [f"<good>{esc(past.beast_title(fig))} is bound for good.</> <dim>It will not come down to the "
                    "farms again.</>"]
    return []


def imprison(game) -> list[str]:
    """Imprisonment before a fight: the strongest of a band seen first makes a Wisdom save, and a failure binds it
    for good. The minute of casting passes; whoever is left fights, knowing you. Returns what to say."""
    from realmwalker.rules import progression

    enc = game.encounter
    casters = prison_casters(game)
    if enc is None or not casters:
        return []
    c, sid = casters[0]
    t = game.tables
    spell = t.spells[sid]
    target = prisoner(game, enc)
    if target is None:
        return []
    slot = spellrules.lowest_free_slot(c, t, int(spell["level"]))
    spellrules.spend_slot(c, slot)
    spellrules.spend_material(c, t, sid)
    dc = spellrules.save_dc(game.sheet(c), t)
    rng = game.world.rng.child(f"imprison/{game.world.time}")
    cdef = t.creatures[target.def_id]
    bonus = int((cdef.get("saves") or {}).get("wis", (int((cdef.get("abilities") or {}).get("wis", 10)) - 10) // 2))
    roll = dice.d20(rng).natural
    name = esc(target.name if target.named else f"the {target.name}")
    out = [f"<magic>{_first(c)} holds up the jade statuette for a long minute and names {name}.</> "
           f"<dim>(Wisdom save: {roll} {bonus:+d} = {roll + bonus} vs DC {dc})</>"]
    kept = roll + bonus >= dc
    lr = int(cdef.get("legendary_resistance", 0) or 0)
    if not kept and lr > int(target.uses.get("legendary_resistance", 0)):
        target.uses["legendary_resistance"] = int(target.uses.get("legendary_resistance", 0)) + 1
        kept = True
        out.append(f"{name.capitalize()} will not be held: it throws the binding off by sheer will (Legendary "
                   "Resistance).")
    game.pass_time(int(spell.get("minutes", 1)), "rest")
    enc.spotted_first = False
    game.cue("spell")
    if kept:
        out.append(f"The statuette cracks across its blank face; {name} is unharmed, and knows you now.")
        return out
    form, words = PRISONS.get(str(cdef.get("kind", "")), PRISON_ELSE)
    enc.creatures.remove(target)
    out.append(f"<good>{name.capitalize()} {words}.</> <dim>The statuette takes its likeness and is gone with it.</>")
    out += _bound_in_the_world(game, target)
    xp = int(cdef.get("xp", 0))
    living = [m for m in game.party if m.alive]
    if xp and living:
        share = xp // len(living)
        for m in living:
            for line in progression.award_xp(m, share, t, rng):
                out.append(line)
        out.append(f"<good>+{share} experience</> each." if len(living) > 1 else f"<good>+{share} experience.</>")
    left = [cr for cr in enc.creatures if cr.alive and cr.hp > 0]
    if not left:
        game.encounter = None
        out.append("Nothing of them is left to fight.")
    else:
        out.append(f"{len(left)} of them come on.")
    return out


# ---------------------------------------------------------------------------- Wish outside a fight
def wish_objects(game) -> list[str]:
    """The things a wish can make: anything that is not magic, worth 100 to 25,000 GP."""
    items = game.tables.items
    out = []
    for iid, d in items.defs.items():
        if not isinstance(d, dict) or iid.startswith(("_", "scroll", "potion")) or d.get("rare") or d.get("magic"):
            continue
        if d.get("category") in ("food", "drink") or d.get("trinket") or d.get("pack"):
            continue
        if WISH_OBJECT_MIN <= int(d.get("value", 0)) <= WISH_OBJECT_MAX:
            out.append(iid)
    return sorted(out, key=lambda i: (-int(items.get(i)["value"]), items.get(i)["name"]))


def foe_spells(game) -> list[str]:
    """The spells the creatures of this world cast in a fight (Spell Immunity's choices)."""
    t = game.tables
    cached = getattr(t, "_foe_spells", None)
    if cached is not None:
        return cached
    seen = set()
    for cdef in t.creatures.defs.values():
        for sid in (cdef.get("spells") or {}) if isinstance(cdef, dict) else ():
            sp = t.spells.defs.get(sid)
            if sp is not None and int(sp.get("level", 0)) >= 1 and not spellrules.out_of_battle(sp) \
                    and spellrules.harms(sp):  # (only what is cast at you: not their own blessings)
                seen.add(sid)
    out = sorted(seen, key=lambda s: (-int(t.spells[s]["level"]), t.spells[s]["name"]))
    t._foe_spells = out
    return out


def swappable_feats(game, c: Character) -> list[str]:
    """The feats Sudden Learning could replace: any not needed by another feat or a feature of theirs."""
    from realmwalker.rules import feats

    t = game.tables
    defs = feats.defs(t)
    out = []
    for f in c.feats:
        fid = f["id"]
        if fid not in defs:
            continue
        needed = any(fid in str((defs.get(o["id"]) or {}).get("prerequisite", "")) for o in c.feats if o["id"] != fid)
        if not needed and fid not in out:
            out.append(fid)
    return out


def _reshape_wishes(game) -> list[Subject]:
    from realmwalker.game import dragons, past
    from realmwalker.world import factions as fx

    w = game.world
    out = []
    lost = [(i, a) for i, a in enumerate(w.politics.get("artifacts", [])) if not a.get("found")
            and a.get("site") is not None and 0 <= int(a["site"]) < len(w.sites)]
    if lost:
        p = game.player
        i, a = min(lost, key=lambda ia: abs(w.sites[ia[1]["site"]].x - p.x) + abs(w.sites[ia[1]["site"]].y - p.y))
        out.append(Subject(f"Reshape Reality: to hold {past.cap(a['name'])} (it carries you to where it lies)",
                           "reshape", "artifact", data={"group": "reshape", "index": i}))
    for key, hid in sorted(w.politics.get("lairs", {}).items()):
        fig = w.figures.get(hid)
        if fig is not None and fig.alive:
            out.append(Subject(f"Reshape Reality: that {past.beast_title(fig)} were dead (half the time; else it "
                               "comes for you)", "reshape", "beast", data={"group": "reshape", "fig": hid,
                                                                             "site": int(key)}))
    for d in dragons.living(w):
        out.append(Subject(f"Reshape Reality: that the dragon {d['name']} were dead (a quarter of the time; else "
                           "it comes for you)", "reshape", "dragon", data={"group": "reshape", "dragon": d["name"]}))
    realm = fx.realm_at(w, game.player.x, game.player.y)
    if realm is not None and (game.renown.bounties.get(realm.id, 0) > 0
                              or any(r.get("realm") == realm.id and not r.get("settled") for r in game.renown.crimes)):
        out.append(Subject(f"Reshape Reality: that {realm.name} forgot your crimes", "reshape", "law",
                           data={"group": "reshape", "realm": realm.id}))
    from realmwalker.game import revival

    for b in (getattr(game, "fallen", []) or []) if revival._room(game) else ():
        out.append(Subject(f"Reshape Reality: that {b['char'].name.split()[0]} were alive again", "reshape", "friend",
                           data={"group": "reshape", "name": b["char"].name}))
    return out


def wish_subjects(game, caster: Character) -> list[Subject]:
    """Every use of Wish outside a fight, in groups (Shift and an arrow jump to the next group)."""
    from realmwalker.rules import feats

    t = game.tables
    out = [Subject("Instant Health: you and every friend here whole, the effects Greater Restoration ends ended",
                   "health", "all", data={"group": "health"})]
    out += [Subject(f"Object Creation: {t.items.get(i)['name']} ({t.items.get(i)['value'] // 100:,} GP)",
                    "object", i, data={"group": "object"}) for i in wish_objects(game)]
    out += [Subject(f"Resistance: the whole party resists {d} damage, for good", "resist", d,
                    data={"group": "resist"}) for d in DAMAGE_TYPES
            if not all(d in (c.spells or {}).get("wished_resist", ()) for c in game.party if c.alive)]
    out += [Subject(f"Spell Immunity: the whole party for 8 hours against {t.spells[s]['name']}", "immune", s,
                    data={"group": "immune"}) for s in foe_spells(game)]
    out += [Subject(f"Sudden Learning: give up {feats.name(t, fid)} for another feat", "learn", fid,
                    data={"group": "learn"}) for fid in swappable_feats(game, caster)]
    out += _reshape_wishes(game)
    return out


def _wished_gone(game, *, d: dict | None = None, fig=None, site_id: int | None = None, how: str = "wished") -> None:
    """A dragon or a beast of the songs gone from the world by magic (dead by a wish, or bound): its lair empty,
    its tribute lifted, the history told, the land grateful."""
    from realmwalker.game import past, reputation
    from realmwalker.world import factions as fx
    from realmwalker.world.history import remember

    w = game.world
    if d is not None:
        from realmwalker.game.dragons import tribute_towns

        d["alive"] = False
        d["slain_by"] = game.leader.name
        d["how"] = how
        past.figure_slain(game, d.get("figure"), d.get("lair"))
        lair = w.sites[d["lair"]] if d.get("lair") is not None and 0 <= int(d["lair"]) < len(w.sites) else None
        towns = tribute_towns(w, d, 20.0)
        for s in towns:
            s.status.pop("tribute", None)
        title, x, y, fame = f"the dragon {d['name']}", (lair.x if lair else game.player.x), \
            (lair.y if lair else game.player.y), 15
    else:
        site = w.sites[site_id]
        past.figure_slain(game, fig.id, site_id)
        towns = [s for s in w.settlements if abs(s.x - site.x) + abs(s.y - site.y) <= 16]
        title, x, y, fame = past.beast_title(fig), site.x, site.y, 5
    text = (f"{game.leader.name} bound {title} for ever" if how == "bound" else
            f"{title[:1].upper() + title[1:]} died, and it is said that {game.leader.name} wished it so")
    remember(w, game.moment.year, "beast_bound" if how == "bound" else "beast_wished", text, importance=4,
             player=True)
    amounts = {}
    for s in towns:
        realm = fx.realm_of_settlement(w, s)
        if realm is not None:
            amounts[realm.id] = max(amounts.get(realm.id, 0.0), 6.0)
    reputation.deed(game, f"{'bound' if how == 'bound' else 'was rid of'} {title}", amounts, x=x, y=y, fame=fame,
                    importance=3, news_text=text)


def _wish(game, caster: Character, sid: str, target, level: int) -> list[str]:
    """One of Wish's other uses outside a fight; every one brings the stress."""
    t = game.tables
    kind, ref = target.kind, target.ref
    first = _first(caster)
    out = [f"<magic>{first} speaks a Wish,</> and the world gives way."]
    living = [c for c in game.party if c.alive]
    if kind == "health":
        for c in living:
            c.hp = c.max_hp
            c.exhaustion = 0
            c.effects.pop("poisoned", None)
            for w in c.wounds:
                w.bleed = 0
                w.infection = 0
        out.append("<good>Everyone of the party stands whole, as if no blow had ever landed.</>")
    elif kind == "object":
        add_item(game.leader, t.items, ref, 1, made_at=_now(game))
        out.append(f"<good>{esc(t.items.get(ref)['name']).capitalize()} lies on the ground before {first}.</> "
                   "<dim>It is real, and it is yours.</>")
    elif kind == "resist":
        for c in living:
            got = c.spells.setdefault("wished_resist", [])
            if ref not in got:
                got.append(ref)
        out.append(f"<good>The party will resist {ref} damage for the rest of their lives.</>")
    elif kind == "immune":
        for c in living:
            c.effects[f"immune_spell:{ref}"] = IMMUNITY_HOURS
        out.append(f"<good>For eight hours, {t.spells[ref]['name']} will not touch anyone of the party.</>")
    elif kind == "learn":
        out += _sudden_learning(game, caster, ref)
    elif kind == "reshape":
        out += _reshape(game, caster, target)
    for line in spellrules.wish_stress(caster, game.world.rng.child(f"wish/{game.world.time}")):
        out.append(line)
    return out


def _sudden_learning(game, caster: Character, fid: str) -> list[str]:
    from realmwalker.rules import feats, progression

    t = game.tables
    feats.revoke(caster, t, fid)
    progression.add_pending(caster, {"kind": "relearn", "level": caster.level, "old": fid})
    return [f"Everything {_first(caster)} knew of {feats.name(t, fid)} is gone, as if never learned.",
            "<good>A new feat waits to be chosen</> <dim>(the character sheet, c).</>"]


def _politics(game, rng):
    """The world's politics, to make something happen now (a beast comes down, a dragon wakes)."""
    from realmwalker.world import news
    from realmwalker.world.politics import Politics

    w = game.world
    return Politics(w, game.tables, rng, day=news.now_days(w), year=game.tables.calendar.at(int(w.time)).year)


def _reshape(game, caster: Character, target) -> list[str]:
    from realmwalker.game import dragons, law, past, revival

    w = game.world
    rng = w.rng.child(f"reshape/{w.time}")
    what = target.ref
    if what == "artifact":
        a = w.politics["artifacts"][int(target.data["index"])]
        site = w.sites[int(a["site"])]
        if game.local is not None:
            game.leave_local()
        game.player.x, game.player.y = site.x, site.y
        game.travel = None
        return [f"<magic>The world folds.</> You stand before {esc(site.name)}: somewhere in its deepest places lies "
                f"{esc(past.cap(a['name']))}. <dim>The wish brought you to it; taking it is yours to do.</>"]
    if what == "beast":
        fig = w.figures.get(target.data["fig"])
        if fig is None or not fig.alive:
            return ["Nothing happens: it is already gone."]
        if rng.chance(RESHAPE_BEAST):
            _wished_gone(game, fig=fig, site_id=int(target.data["site"]))
            return [f"<good>Far away, {esc(past.beast_title(fig))} lies down in its lair and does not rise again.</>"]
        _politics(game, rng).beast_comes(fig, int(target.data["site"]))
        return [f"<danger>The wish twists.</> {esc(past.beast_title(fig))} lifts its head in its lair: it knows your "
                "name now, and it comes down from the heights."]
    if what == "dragon":
        d = next((d for d in dragons.living(w) if d.get("name") == target.data["dragon"]), None)
        if d is None:
            return ["Nothing happens: it is already gone."]
        if rng.chance(RESHAPE_DRAGON):
            _wished_gone(game, d=d)
            return [f"<good>Far away, the dragon {esc(d['name'])} sighs out its last breath on its hoard.</>"]
        _politics(game, rng).dragon_wakes(d)
        return [f"<danger>The wish twists.</> On its hoard the dragon {esc(d['name'])} opens one eye: it has heard "
                "its name in a mortal mouth, and it is awake now, and angry."]
    if what == "law":
        rid = int(target.data["realm"])
        law.settle(game, rid)
        for r in game.renown.crimes:
            if r.get("realm") == rid:
                r["settled"] = True
                r["reported"] = True
        realm = w.factions.get(rid)
        return [f"<good>In {esc(realm.name) if realm else 'this realm'} the records go blank and the watch forgets "
                "your face:</> no crime of yours is remembered there."]
    if what == "friend":
        b = next((b for b in getattr(game, "fallen", []) or [] if b["char"].name == target.data["name"]), None)
        if b is None:
            return ["Nothing happens."]
        c = b["char"]
        game.fallen.remove(b)
        out = revival.return_to_life(game, c, {}, {"hp": "all", "closes": True, "regrow": True, "cures": True,
                                                    "toll": 4}, rng)
        if c not in game.party:
            game.party.append(c)
        from realmwalker.game import pack

        pack.sync(game)
        return out
    return []


# ---------------------------------------------------------------------------- Simulacrum (G.3)
SIMULACRUM_KINDS = ("beast", "humanoid")


def simulacrum_subjects(game, caster: Character) -> list[Subject]:
    """Those within ten feet for the twelve hours: anyone of the party (the caster too), a beast of the herd with a
    stat block, a prisoner who is a beast or a humanoid."""
    t = game.tables
    out = [Subject(c.name, "simulacrum", c.name, data={"what": "person"}) for c in game.party if c.alive]
    for i, a in enumerate(game.leader.animals):
        kind = a.get("kind")
        if a.get("summoned") or kind not in t.creatures or t.creatures[kind]["kind"] not in SIMULACRUM_KINDS:
            continue
        out.append(Subject(f"{a.get('name') or t.creatures[kind]['name']}, the {t.creatures[kind]['name']}",
                           "simulacrum", kind, data={"what": "creature", "name": a.get("name") or "", "herd": i}))
    for i, cap in enumerate(_flags(game).get("captives") or []):
        cid = cap.get("def_id")
        if cid not in t.creatures or t.creatures[cid]["kind"] not in SIMULACRUM_KINDS:
            continue
        out.append(Subject(f"{cap.get('name') or t.creatures[cid]['name']}, your prisoner", "simulacrum", cid,
                           data={"what": "creature", "name": "", "captive": i}))
    return out


def _simulacrum(game, caster: Character, target) -> list[str]:
    from realmwalker.rules import servants as servant_rules, simulacrum as sim

    t = game.tables
    gone = sim.destroy(caster)
    out = []
    if gone:
        out.append(f"<dim>Somewhere behind them {esc(gone)} slumps into wet snow: a second likeness unmakes the "
                   "first.</>")
    first = _first(caster)
    if target.data.get("what") == "person":
        who = next((c for c in game.party if c.name == target.ref), caster)
        copy = sim.make(who, t)
        sim.keep(caster, copy, who.name, _now(game))
        self_ = who is caster
        out.insert(0, f"<magic>For twelve hours {first} works the ruby dust into a heap of snow at "
                      f"{'their own' if self_ else _first(who) + chr(39) + 's'} feet,</> and at the last touch it stands "
                      f"up as {'them' if self_ else _first(who)}: the same face, the same voice, {sim.FROST}.")
        out.append(f"<dim>{esc(copy.name)} ({copy.max_hp} hit points, half the original's) fights beside {first}, "
                   "acting right after them. Nothing heals it; at a long rest beside it, 100 GP of powders mend each "
                   "hit point. It never rests, learns or grows, its spells do not come back, and at 0 hit points it "
                   "melts.</>")
        return out
    cid = str(target.ref)
    block = t.creatures[cid]
    top = max(1, servant_rules.avg_hp(t, cid) // 2)
    name = sim.name_for(target.data.get("name") or block["name"]) if target.data.get("name") else         f"snow {block['name']}"
    rec = servant_rules.add(caster, t, cid, sim.SPELL, until=None, now=_now(game), word=False, name=name,
                            max_hp=top, type="construct")
    if rec is None:
        return out + [f"{first} has twelve creatures at their word already: the snow will not rise."]
    out.insert(0, f"<magic>For twelve hours {first} works the ruby dust into a heap of snow beside "
                  f"{esc(target.name.split(',')[0])},</> and at the last touch it rises as its likeness, {sim.FROST}.")
    out.append(f"<dim>The {esc(name)} ({top} hit points) follows {first} and fights at their side, acting right after "
               "them. Nothing heals it but the repair at a long rest (100 GP a hit point); at 0 it melts.</>")
    return out


# ---------------------------------------------------------------------------- the door
def subjects(game, caster, sid: str) -> list[Subject]:
    does = _does(game, sid)
    if does == "simulacrum":
        return simulacrum_subjects(game, caster)
    if does == "contingency":
        t = game.tables
        return [Subject(f"{t.spells[s]['name']} (level {t.spells[s]['level']}), {words}", "contingency", s,
                        data={"trigger": trig, "group": s})
                for s in contingent_spells(game, caster) for trig, words in TRIGGERS.items()]
    if does == "jar" and in_jar(caster):
        return [Subject("go back into your body (no slot)", "jar", "return")]
    if does == "clone":
        return [Subject(c.name, "clone", c.name) for c in game.party if c.alive and clone_of(game, c) is None]
    if does == "wish":
        return wish_subjects(game, caster)
    return []


def problem(game, caster, sid: str, target) -> str | None:
    does = _does(game, sid)
    aimed = isinstance(target, Subject)
    if does == "contingency":
        if not contingent_spells(game, caster):
            return ("no spell to hold: one of level 5 or lower, cast with an action on yourself, with a slot left "
                    "for it besides Contingency's")
        if not aimed:
            return "choose the spell and its moment (←→)"
    if does == "jar" and in_jar(caster) and not aimed:
        return "choose (←→)"
    if does == "clone":
        if _town(game) is None:
            return "only in a town or city, whose temple keeps the vessel in its crypt"
        if not aimed:
            return "a clone already grows for everyone of the party" if not subjects(game, caster, sid) else \
                "choose whose (←→)"
    if does == "imprison":
        return "cast from the meeting screen, when a band is seen first (i)"
    if does == "simulacrum" and not aimed:
        return "choose whose likeness (←→)"
    if does == "simulacrum" and target.data.get("what") == "creature":
        from realmwalker.rules import servants as servant_rules, simulacrum as sim

        if not servant_rules.room(caster) and not servant_rules.of_spell(caster, sim.SPELL):
            return "twelve creatures are at your word already: the snow would not rise"
    if does == "wish":
        if caster.spells.get("wish_lost"):
            return "the strain of an old wish: Wish will never come again"
        if not aimed:
            return "choose the wish (←→; Shift ←→: the next kind)"
    return None


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    spell = game.tables.spells[sid]
    does = _does(game, sid)
    if isinstance(target, Character):
        target = None
    if does == "contingency" and target is not None:
        return _contingency(game, caster, sid, target, level)
    if does == "jar":
        return _jar(game, caster, spell)
    if does == "clone" and target is not None:
        return _clone(game, caster, spell, target)
    if does == "simulacrum" and target is not None:
        return _simulacrum(game, caster, target)
    if does == "wish" and target is not None:
        return _wish(game, caster, sid, target, level)
    return []


def tick(game) -> None:
    """As time passes: a Contingency's ten days run out; a wished immunity to a spell is counted down with the other
    effects (survival)."""
    now = game.world.time
    for c in list(game.party) + list(getattr(game, "waiting", []) or []):
        rec = (c.spells or {}).get("contingency")
        if rec and now >= float(rec.get("until", 0)):
            c.spells.pop("contingency", None)
