"""The familiar and the steed outside a fight (Expansion 3 F.1): Find Familiar and Find Steed on the road (through
game/spellwork's door: subjects, problem, cast), sending a familiar away and calling it back, the steed in the herd,
the familiar's watch at night, and their records after a rest. What they do in a fight is rules/allies.py."""
from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject
from realmwalker.rules import allies as rules

FORM_WORDS = {"bat": "a bat", "cat": "a cat", "crab": "a crab", "frog": "a frog", "hawk": "a hawk", "lizard": "a lizard",
              "owl": "an owl", "rat": "a rat", "raven": "a raven", "scorpion": "a scorpion", "spider": "a spider",
              "weasel": "a weasel"}
TYPE_WORDS = {"celestial": "a celestial spirit", "fey": "a fey spirit", "fiend": "a fiendish spirit"}
LOOK_WORDS = {"horse": "a horse", "camel": "a camel", "dire_wolf": "a dire wolf"}
STEED_ANIMAL = "otherworldly_steed"  # (its entry in the herd: data/economy.json animals)


def _first(c) -> str:
    return esc(c.name.split()[0])


def _name(game, caster, kind: str, form: str) -> str:
    """A name from the game's words: the familiars' and steeds' list (data/names.json "familiars")."""
    words = game.tables.names.get("familiars") or {}
    pool = list(words.get(kind) or words.get("any") or ["Ash", "Pip", "Wren", "Soot", "Bramble"])
    taken = {(c.spells.get(k) or {}).get("name") for c in game.party for k in ("familiar", "steed")
             if isinstance(c.spells.get(k), dict)}
    rng = game.world.rng.child(f"familiar_name/{caster.name}/{kind}/{form}/{game.world.time}")
    free = [n for n in pool if n not in taken] or pool
    return rng.choice(free)


# ---------------------------------------------------------------------------- the Spells page
def subjects(game, caster, sid: str) -> list[Subject]:
    does = _does(game, sid)
    if does == "familiar":
        rec = rules.record(caster, "familiar")
        out = []
        if rec is not None and not rec.get("gone"):
            if rec.get("away"):
                out.append(Subject(f"call {esc(rec['name'])} back (no slot)", "familiar", "recall", data={"free": True}))
            else:
                out.append(Subject(f"send {esc(rec['name'])} away (no slot)", "familiar", "dismiss", data={"free": True}))
        keep = rec.get("type") if rec is not None and not rec.get("gone") else None
        for form in rules.FAMILIAR_FORMS:
            for type_ in ((keep,) if keep else rules.TYPES):
                out.append(Subject(f"{FORM_WORDS[form]}, {TYPE_WORDS[type_]}", "familiar", form,
                                   data={"form": form, "type": type_, "group": form}))
        return out
    if does == "steed":
        return [Subject(f"{LOOK_WORDS[look]}, {TYPE_WORDS[type_].replace(' spirit', '')}", "steed", look,
                        data={"look": look, "type": type_, "group": look})
                for look in rules.STEED_LOOKS for type_ in rules.TYPES]
    return []


def _does(game, sid: str) -> str | None:
    from realmwalker.game.spellwork import _does as does

    return does(game.tables.spells[sid])


def problem(game, caster, sid: str, target) -> str | None:
    if not isinstance(target, Subject):
        return "choose (←→)"
    rec = rules.record(caster, "familiar")
    if target.ref == "recall" and (rec is None or not rec.get("away")):
        return "no familiar waits in its pocket of the world"
    if target.ref == "dismiss" and (rec is None or rec.get("gone") or rec.get("away")):
        return "no familiar is with you"
    return None


def free_use(game, caster, target) -> list[str] | None:
    """Sending a familiar away or calling it back: a Magic action, no slot (None: not one of those)."""
    if not isinstance(target, Subject) or not target.data.get("free"):
        return None
    rec = rules.record(caster, "familiar")
    if rec is None or rec.get("gone"):
        return ["No familiar answers."]
    if target.ref == "dismiss":
        rec["away"] = True
        game.dirty = True
        return [f"{esc(rec['name'])} winks out of the world, into the pocket where it waits for {_first(caster)}."]
    rec["away"] = False
    game.dirty = True
    return [f"{esc(rec['name'])} is there again at {_first(caster)}'s side, as if it had never gone."]


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    does = _does(game, sid)
    if not isinstance(target, Subject):
        return []
    if does == "familiar":
        return _familiar(game, caster, target)
    if does == "steed":
        return _steed(game, caster, target, level)
    return []


def _familiar(game, caster, target: Subject) -> list[str]:
    form, type_ = target.data["form"], target.data["type"]
    rec = rules.record(caster, "familiar")
    max_hp = rules.familiar_max_hp(game.tables, form)
    if rec is not None and not rec.get("gone"):  # (one familiar only: it takes the new shape)
        rec.update({"form": form, "max_hp": max_hp, "hp": max_hp, "away": False})
        game.dirty = True
        return [f"The incense burns down, and {esc(rec['name'])} shivers and becomes {FORM_WORDS[form]}."]
    name = rec["name"] if rec is not None and rec.get("name") else _name(game, caster, "familiar", form)
    caster.spells["familiar"] = {"form": form, "type": type_, "name": name, "hp": max_hp, "max_hp": max_hp,
                                 "gone": False, "away": False}
    game.dirty = True
    return [f"The incense burns down through the hour, and something answers: {FORM_WORDS[form]} that is "
            f"{TYPE_WORDS[type_]} at heart. {_first(caster)} names it <name>{esc(name)}</>. It will go where "
            f"{_first(caster)} goes, keep watch at night and help in a fight, though it will not strike."]


def _steed(game, caster, target: Subject, level: int) -> list[str]:
    look, type_ = target.data["look"], target.data["type"]
    old = rules.record(caster, "steed")
    name = old["name"] if old is not None and old.get("name") else _name(game, caster, "steed", look)
    rules.new_steed(caster, level, look=look, type_=type_, name=name)
    put_in_herd(game)
    game.dirty = True
    return [f"{LOOK_WORDS[look][0].upper() + LOOK_WORDS[look][1:]} steps out of the air beside {_first(caster)}: "
            f"<name>{esc(name)}</>, {TYPE_WORDS[type_].replace(' spirit', '')} under its hide. It carries "
            f"{_first(caster)} on the road and fights at their side."]


# ---------------------------------------------------------------------------- the steed in the herd
def put_in_herd(game) -> None:
    """Each living steed is a mount in the herd (leader.animals: {kind, name, summoned: owner's name}); one that is
    gone, or whose owner is dead or not with the party, is taken out."""
    if not game.party:
        return
    herd = game.leader.animals
    herd[:] = [a for a in herd if not a.get("summoned")]
    for c in game.party:
        rec = rules.record(c, "steed")
        if c.alive and rec is not None and not rec.get("gone"):
            herd.append({"kind": STEED_ANIMAL, "name": rec.get("name") or "steed", "unfed": 0,
                         "bought": game.world.time, "summoned": c.name})


def summoned(animal: dict) -> bool:
    """A steed of another world: it eats nothing, is never sold, stabled, stolen or awakened."""
    return bool(animal.get("summoned"))


# ---------------------------------------------------------------------------- after a fight, a rest, a death
def after_battle(game, battle) -> None:
    rules.after(battle)
    put_in_herd(game)


def long_rest(game) -> None:
    for c in game.party:
        if c.alive:
            rules.rest(c, True)


def died(game, char) -> None:
    """A steed vanishes when its owner dies; a familiar goes with its master."""
    for kind in ("familiar", "steed"):
        rec = rules.record(char, kind)
        if rec is not None:
            rec["gone"] = True
    put_in_herd(game)


def watcher(game, char=None) -> dict | None:
    """A familiar with the party that keeps watch at night: the first one present."""
    for c in game.party if char is None else [char]:
        rec = rules.present(c, "familiar")
        if c.alive and rec is not None:
            return rec
    return None
