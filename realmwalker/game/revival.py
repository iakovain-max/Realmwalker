"""Return from death (Expansion 3 E.1; PHB 2024 Revivify, Raise Dead, Reincarnate, Resurrection, True Resurrection,
Gentle Repose).

A companion who dies is carried by the party while someone in it could still bring them back: a caster who has a
spell of return ready, or could prepare one before its time runs out, or a scroll of one that someone can read. The
body is a record in `game.fallen` ({"char", "died", "counted", "since", "repose", "cause"}; saved with the
character). Otherwise, or once ten days of death have passed (Gentle Repose stops that count while it lasts), the
party buries them and the world hears of it as before (`companions.died`).

The leader's death is the end of the game, unless a companion who is still standing can bring them back at once:
they do, as they would in the moment (the cheapest spell that works, its slot and costly component spent). After a
fight, a companion with Revivify ready kneels by a friend who fell in its last minute; the player casts the rest
from the Spells page (S), at a body as the target.

Times are world minutes (`World.time`). A spell's reach in time is its revive op's `within_rounds` (ten to a minute)
or `within_days`.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup
from realmwalker.rules import health
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character

KEEP_DAYS = 10  # a body is buried after this long dead (counted without the days under Gentle Repose)
DAY = 24 * 60


# ---------------------------------------------------------------------------- the spells and their reach
def revive_spells(tables) -> list[str]:
    """Every spell of return, cheapest first (by level)."""
    out = [sid for sid, sp in tables.spells.defs.items() if isinstance(sp, dict) and not sid.startswith("_")
           and spellrules.has_op(sp, "revive") and "again" not in sp.get("classes", ())]
    return sorted(out, key=lambda s: (int(tables.spells[s]["level"]), s))


def reach(spell: dict) -> float:
    """How long dead someone may be for this spell to call them back, in minutes."""
    o = spellrules.op(spell, "revive") or {}
    if o.get("within_days"):
        return float(o["within_days"]) * DAY
    return float(o.get("within_rounds", 10)) / 10.0  # (ten rounds to a minute)


def dead_for(game, body: dict) -> float:
    """Minutes dead, not counting the time under Gentle Repose."""
    now = float(game.world.time)
    since = float(body.get("since", body["died"]))
    counted = float(body.get("counted", 0.0))
    repose = float(body.get("repose", 0.0))
    if repose > since:
        counted += max(0.0, now - min(now, repose))
    else:
        counted += max(0.0, now - since)
    return counted


def _settle(game, body: dict) -> None:
    """Bring the count up to now (before the repose changes)."""
    body["counted"] = dead_for(game, body)
    body["since"] = float(game.world.time)


# ---------------------------------------------------------------------------- who could do it
def _scrolls(game) -> list:
    """Scrolls of return in the party's packs: (item, spell id)."""
    out = []
    seen = set()
    for c in game.party:
        for it in c.inventory:
            if id(it) in seen:
                continue
            seen.add(id(it))
            sid = (game.tables.items.get(it.def_id).get("use") or {}).get("scroll")
            if sid in game.tables.spells and spellrules.has_op(game.tables.spells[sid], "revive"):
                out.append((it, sid))
    return out


def ready_now(game, caster: Character, sid: str) -> tuple[bool, str]:
    """Could this party member cast this spell of return right now (prepared, a slot, its component)?"""
    t = game.tables
    if not caster.alive or caster.hp <= 0:
        return False, "they are down"
    if sid not in spellrules.known_spells(caster, t):
        return False, "not prepared"
    ok, why = spellrules.can_cast(caster, t, sid)
    if not ok:
        return False, why
    level = int(t.spells[sid]["level"])
    if level and spellrules.lowest_free_slot(caster, t, level) is None and not spellrules.free_cast(caster, t, sid):
        return False, "no spell slot left"
    return True, ""


def could_raise(game, minutes_dead: float, *, leader_too: bool = True) -> bool:
    """Could anyone in the party bring back someone this long dead, now or before the time runs out: a spell ready
    (or one they could prepare after a night's rest, for the spells that reach a day or more), or a scroll someone
    can read."""
    t = game.tables
    for sid in revive_spells(t):
        window = reach(t.spells[sid])
        if window < minutes_dead:
            continue
        for c in game.party:
            if not c.alive or (c is game.party[0] and not leader_too):
                continue
            if sid in spellrules.known_spells(c, t):
                return True
            if window >= DAY and (sid in spellrules.preparable(c, t) or sid in spellrules.always_prepared(c, t)):
                return True
    for it, sid in _scrolls(game):
        if reach(t.spells[sid]) >= minutes_dead and any(c.alive and spellrules.scroll_reader(c, t, sid)
                                                        for c in game.party):
            return True
    return False


# ---------------------------------------------------------------------------- a companion falls
def fall(game, c: Character, *, died_at: float | None = None, left: bool = False) -> bool:
    """A companion is dead. If the party can carry them and someone could still raise them, the body is kept
    (returns True); otherwise they are dead for good (companions.died)."""
    from realmwalker.game import pack
    from realmwalker.game.companions import died

    pack.sync(game)  # (the dead leave what they carried to the rest)
    if left or not c.companion:
        if c.companion:
            died(game, c)
        return False
    now = float(game.world.time)
    when = now if died_at is None else min(now, float(died_at))
    if not could_raise(game, now - when):
        died(game, c)
        return False
    fallen = getattr(game, "fallen", None)
    if fallen is None:
        game.fallen = fallen = []
    if not any(b["char"] is c for b in fallen):
        fallen.append({"char": c, "died": when, "since": when, "counted": 0.0, "repose": 0.0,
                       "cause": getattr(c, "death_cause", None) or ""})
        game.say(f"The party carries {escape_markup(c.name.split()[0])}'s body. <dim>A spell of return can still "
                 f"bring them back (the Spells page, S); otherwise they are buried in ten days.</>", "info")
    return True


def bodies(game, sid: str | None = None) -> list[dict]:
    """The fallen the party carries (those a spell can still reach, when `sid` is given)."""
    out = list(getattr(game, "fallen", []) or [])
    if sid is not None:
        window = reach(game.tables.spells[sid]) if spellrules.has_op(game.tables.spells[sid], "revive") else None
        out = [b for b in out if window is None or dead_for(game, b) <= window]
    return out


def body_of(game, char: Character) -> dict | None:
    return next((b for b in getattr(game, "fallen", []) or [] if b["char"] is char), None)


def tick(game) -> None:
    """As time passes: a body nobody could raise any more, or ten days dead, is buried."""
    fallen = getattr(game, "fallen", None)
    if not fallen or game.over is not None or game.battle is not None:
        return
    from realmwalker.game.companions import died

    for b in list(fallen):
        dead = dead_for(game, b)
        if dead <= KEEP_DAYS * DAY and could_raise(game, dead):
            continue
        fallen.remove(b)
        c = b["char"]
        first = escape_markup(c.name.split()[0])
        where = "in the churchyard" if game.world.settlement_at(game.player.x, game.player.y) is not None \
            else "by the way, under a cairn of stones"
        game.say(f"<warn>You bury {first} {where}.</> There is no calling them back now.", "warn")
        died(game, c)
        game.dirty = True


def bury_all(game) -> None:
    """The leader is dead and nobody is left to raise anyone: the bodies carried are dead for good."""
    from realmwalker.game.companions import died

    for b in list(getattr(game, "fallen", []) or []):
        died(game, b["char"])
    game.fallen = []


def when_text(minutes: float) -> str:
    if minutes < 1.5:
        return "moments ago"
    if minutes < 90:
        return f"{round(minutes)} minutes dead"
    if minutes < 2 * DAY:
        return f"{round(minutes / 60)} hours dead"
    return f"{round(minutes / DAY)} days dead"


# ---------------------------------------------------------------------------- the casting
def problem(game, sid: str, body: dict | None) -> str | None:
    """Why this spell cannot reach this body (None if it can)."""
    spell = game.tables.spells[sid]
    if body is None:
        return "nobody of the party lies dead"
    dust = body["char"].effects.get("kept:dust")
    if spellrules.has_op(spell, "revive") and dust and not (spellrules.op(spell, "revive") or {}).get("cures"):
        return (f"nothing is left of {escape_markup(body['char'].name.split()[0])} but dust: only True Resurrection "
                "reaches them")
    if spellrules.has_op(spell, "revive"):
        dead = dead_for(game, body)
        if dead > reach(spell):
            return f"{escape_markup(body['char'].name.split()[0])} has been dead too long for it ({when_text(dead)})"
        if not _room(game):
            return "the party is full: someone must leave it first"
    elif spellrules.op(spell, "road") and float(body.get("repose", 0)) > game.world.time + DAY:
        return "the body is already kept from decay"
    return None


def _room(game) -> bool:
    """Is there room in the party for one more companion (the fallen do not count while they lie dead)?"""
    from realmwalker.game import companions

    return companions.room(game) if getattr(game.tables, "companions", None) else True


def raise_body(game, caster: Character, sid: str, body: dict, rng=None) -> list[str]:
    """The spell of return is cast (its slot and component already spent): the fallen comes back to the party."""
    from realmwalker.game import pack

    t = game.tables
    spell = t.spells[sid]
    o = spellrules.op(spell, "revive") or {}
    c = body["char"]
    first = escape_markup(c.name.split()[0])
    rng = rng or game.world.rng.child(f"revive/{sid}/{game.world.time}/{c.name}")
    if body in getattr(game, "fallen", []):
        game.fallen.remove(body)
    out = [f"<magic>{escape_markup(caster.name.split()[0])} casts {spell['name']} over {first}.</>"]
    out += return_to_life(game, c, spell, o, rng)
    game.cue("heal")
    if c not in game.party:
        game.party.append(c)
    pack.sync(game)
    game.pass_time(int(spell.get("minutes", 0)), "rest")  # (Revivify is an action: no minute passes)
    game.dirty = True
    return out


def return_to_life(game, c: Character, spell: dict, o: dict, rng) -> list[str]:
    """What a spell of return does to the body it calls the soul back into."""
    t = game.tables
    first = escape_markup(c.name.split()[0])
    out = []
    c.alive = True
    if hasattr(c, "death_cause"):
        c.death_cause = None
    if o.get("species") == "new":
        out.append(_new_body(game, c, rng))
    if o.get("hp") == "all" or o.get("species") == "new":
        c.hp = c.max_hp
    else:
        c.hp = max(1, int(o.get("hp", 1)))
    if o.get("closes") or o.get("species") == "new":
        c.wounds = [] if o.get("regrow") or o.get("species") == "new" else [w for w in c.wounds if w.severity < 2]
        for w in c.wounds:
            w.bleed = 0
            w.infection = 0
        c.effects.pop("poisoned", None)
    else:
        for w in c.wounds:  # (Revivify closes nothing: the one casting it binds what still bleeds as they work,
            if w.bleed or w.internal:  # and the life coming back stems the bleeding inside)
                w.bandaged = True
                w.internal = False
    if o.get("regrow") or o.get("species") == "new":
        c.injuries = [i for i in c.injuries if not i.startswith("lost_")]
    if o.get("cures"):
        c.diseases = []
        _lift_curses(game, c)
    # The magic holds the body together for a while: what killed them does not kill them again in the next breath.
    c.blood = max(c.blood, 50.0)
    c.exhaustion = min(c.exhaustion, 4)
    c.hunger = min(c.hunger, 60.0)
    c.thirst = min(c.thirst, 60.0)
    c.body_heat = max(-40.0, min(40.0, c.body_heat))
    toll = int(o.get("toll", 0))
    if toll:
        c.effects[health.DEATH_TOLL] = float(max(toll, c.effects.get(health.DEATH_TOLL, 0)))
    words = {1: "draws a ragged breath and opens their eyes",
             "all": "breathes, whole again, and sits up as if from sleep"}
    out.append(f"<good>{first} {words['all'] if c.hp >= c.max_hp else words[1]}.</>"
               + (f" <dim>Coming back from death is an ordeal: -{toll} to every d20 roll, one less after each long "
                  f"rest.</>" if toll else ""))
    return out


def _lift_curses(game, c: Character) -> None:
    from realmwalker.rules import magic

    for it in magic.attuned_items(c):
        if it.magic.get("cursed"):
            c.attuned = [u for u in c.attuned if u != it.uid]


def _new_body(game, c: Character, rng) -> str:
    """Reincarnate: a new body, of a people rolled on the book's table (those not in this world's lands are
    rolled again among those that are)."""
    from realmwalker.rules import looks

    t = game.tables
    table = ["aasimar", "dragonborn", "dwarf", "elf", "gnome", "goliath", "halfling", "human", "orc", "tiefling"]
    have = [s for s in table if s in t.races]
    roll = dice.roll("1d10", rng).total
    new = table[roll - 1]
    if new not in t.races:
        new = rng.choice(have or [c.species])
    old = c.species
    c.species = new
    lineages = (t.races.get(new) or {}).get("lineages") or {}
    c.lineage = rng.choice(sorted(lineages)) if lineages else None
    c.looks = looks.random_looks(t, c.species, c.sex, c.age, rng)
    c.appearance = looks.describe(t, c.looks, c.species, c.sex)
    name = (t.races.get(new) or {}).get("name", new)
    was = (t.races.get(old) or {}).get("name", old)
    return (f"The body that forms is not the one that fell: {escape_markup(c.name.split()[0])} wakes "
            f"{'an' if name[:1].lower() in 'aeiou' else 'a'} {name.lower()}" + (f", no longer {was.lower()}." if old != new else
                                                                                 ", as before, yet new."))


# ---------------------------------------------------------------------------- the moment of death
def _best_reviver(game, minutes_dead: float, exclude: Character):
    """The companion and the spell (or scroll) that can bring someone this long dead back now, cheapest first."""
    t = game.tables
    for sid in revive_spells(t):
        if reach(t.spells[sid]) < minutes_dead:
            continue
        for c in game.party:
            if c is exclude or not c.alive or c.hp <= 0:
                continue
            if ready_now(game, c, sid)[0]:
                return c, sid, None
    for it, sid in _scrolls(game):
        if reach(t.spells[sid]) < minutes_dead:
            continue
        for c in game.party:
            if c is not exclude and c.alive and c.hp > 0 and spellrules.scroll_reader(c, t, sid) == "sure":
                return c, sid, it
    return None, None, None


def _spend(game, caster: Character, sid: str, scroll) -> None:
    t = game.tables
    if scroll is not None:
        from realmwalker.rules.inventory import remove_item

        owner = next((m for m in game.party if any(i is scroll for i in m.inventory)), caster)
        remove_item(owner, scroll.uid, 1)
        return
    level = int(t.spells[sid]["level"])
    free = spellrules.free_cast(caster, t, sid)
    if free:
        spellrules.spend_free(caster, sid, free)
    elif level:
        spellrules.spend_slot(caster, spellrules.lowest_free_slot(caster, t, level))
    spellrules.spend_material(caster, t, sid)


def save_leader(game, minutes_dead: float = 0.0) -> list[str] | None:
    """The leader has just died: a companion still standing who can call them back does it at once. Returns what
    to say, or None when nobody can (the end)."""
    leader = game.party[0] if game.party else None
    if leader is None or leader.alive or not game.party[1:]:
        return None
    if "hanged" in str(getattr(leader, "death_cause", "") or ""):
        return None  # (the realm's justice: nobody may cut down the hanged)
    c, sid, scroll = _best_reviver(game, minutes_dead, leader)
    if c is None:
        return None
    _spend(game, c, sid, scroll)
    spell = game.tables.spells[sid]
    rng = game.world.rng.child(f"revive/leader/{game.world.time}")
    how = "reads a scroll of" if scroll is not None else "casts"
    out = [f"<magic>All is dark. Then a voice: {escape_markup(c.name.split()[0])} kneels over you and {how} "
           f"{spell['name']}.</>"]
    out += return_to_life(game, leader, spell, spellrules.op(spell, "revive") or {}, rng)
    game.cue("heal")
    if int(spell.get("minutes", 0)) > 1:
        out.append(f"<dim>It took {spell['minutes'] // 60 or spell['minutes']} "
                   f"{'hour' if spell['minutes'] >= 60 else 'minutes'}.</>")
    game.dirty = True
    return out


def auto_revive(game) -> list[str]:
    """After a fight: a companion with a spell of return ready brings back a friend whose time is running out
    (Revivify's minute) at once, as they would on Auto. The player decides the slower ones."""
    out = []
    for b in list(getattr(game, "fallen", []) or []):
        dead = dead_for(game, b)
        if not _room(game):
            break
        for sid in revive_spells(game.tables):
            window = reach(game.tables.spells[sid])
            if window < dead or window > 10:
                continue  # (only the spells whose time runs out in minutes)
            caster = next((c for c in game.party[1:] if ready_now(game, c, sid)[0]), None)
            if caster is None:
                continue
            _spend(game, caster, sid, None)
            out += raise_body(game, caster, sid, b)
            break
    return out


def leader_note(game) -> list[str]:
    """After a fight: tell the player when they alone could still bring a friend back in the minute left."""
    out = []
    leader = game.party[0]
    for b in getattr(game, "fallen", []) or []:
        dead = dead_for(game, b)
        for sid in revive_spells(game.tables):
            if dead <= reach(game.tables.spells[sid]) <= 10 and ready_now(game, leader, sid)[0]:
                out.append(f"<good>{escape_markup(b['char'].name.split()[0])} can still be brought back:</> "
                           f"{game.tables.spells[sid]['name']} from the Spells page (S), before the minute is out.")
                break
    return out


# ---------------------------------------------------------------------------- saving
def to_save(game) -> list[dict]:
    return [{**{k: v for k, v in b.items() if k != "char"}, "char": b["char"].to_dict()}
            for b in getattr(game, "fallen", []) or []]


def from_save(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows or []:
        c = Character.from_dict(r["char"])
        c.alive = False
        out.append({**{k: v for k, v in r.items() if k != "char"}, "char": c})
    return out


def repose(game, body: dict, days: int = 10) -> str:
    """Gentle Repose: the days under it do not count against a spell of return, and the body does not decay."""
    _settle(game, body)
    body["repose"] = float(game.world.time) + days * DAY
    return (f"{escape_markup(body['char'].name.split()[0])}'s body is kept from decay: the next {days} days will "
            f"not count against a spell of return.")
