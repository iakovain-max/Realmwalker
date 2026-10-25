"""The finale (docs/ADVENTURES.md §5.8): a fair, epic fight.

A boss is a creature the game has, made a boss by a template (villains.json bosses): more hit points by tier,
Legendary Resistances, legendary actions from a menu (LEGENDARY), and a second phase at a share of its hit points
(PHASES). Keys found on the way change the fight (KEYS, applied by `prepare` from fight.start_battle before the
dice roll, the pattern of warding.at_the_start). One list for data and code: story/check.py reports names that are
not here.

The finale's band carries the story tag {"adv", "role"} on its creatures (saved with the actor); `prepare` finds
the adventure from it, so any fight with the boss is its finale, wherever it is met.
"""

from __future__ import annotations

from realmwalker.rules.engine.handlers.bosses import PHASES  # noqa: F401  (the second phases are the kernel's)

KEYS: dict[str, object] = {}
LEGENDARY: dict[str, object] = {}


def key(name: str):
    """fn(battle, game, adv, boss, *args) -> a line to say, or ''"""
    def wrap(fn):
        KEYS[name] = fn
        return fn
    return wrap


def legendary(name: str):
    """fn(fighter) -> the legendary actions it gives the boss (a stat block's `legendary.actions` entries)"""
    def wrap(fn):
        LEGENDARY[name] = fn
        return fn
    return wrap


def split_key(text: str) -> tuple[str, list[str]]:
    """'vulnerable(fire)' -> ('vulnerable', ['fire']); 'surprise' -> ('surprise', [])."""
    text = text.strip()
    if text.endswith(")") and "(" in text:
        name, rest = text.split("(", 1)
        args = [a.strip() for a in rest[:-1].split(",") if a.strip()]
        return name.strip(), args
    return text, []


# ---------------------------------------------------------------------------- the boss
def story_of(creature) -> dict | None:
    return getattr(creature, "story", None) or None


def template_for(tables, adv: dict) -> dict:
    return tables.villains["bosses"][adv["finale"]["template"]]


def make_boss(battle, f, template: dict, tier: int) -> None:
    """The template on the creature: hit points, Legendary Resistances, legendary actions, the phase armed."""
    d = dict(f.cdef)
    mult = float(template["hp"]) * (1.0 + 0.15 * (int(tier) - int(template["tiers"][0])))
    hp = max(f.max_hp, int(round(f.max_hp * mult)))
    if f.creature is not None and not f.creature.uses.get("boss_hp"):
        f.creature.max_hp = hp  # (once: a boss met again keeps the hit points it has left)
        f.creature.hp = hp
        f.creature.uses["boss_hp"] = 1
    if int(template["resistances"]) > 0:
        d["legendary_resistance"] = {"per_day": int(template["resistances"])}
    actions = []
    for m in template["menu"]:
        actions += LEGENDARY[m](f)
    if int(template["actions"]) > 0 and actions:
        d["legendary"] = {"uses": int(template["actions"]), "actions": actions}
    if template.get("phase"):
        d["boss_phase"] = dict(template["phase"])
    d["morale"] = "fanatic"  # (at its end it stands and fights: law 5, and the tale's own words)
    f.cdef = d
    if f.creature is not None:
        f.creature.uses.pop("legendary_resistance", None)
        f.creature.uses.pop("legendary_actions", None)


def prepare(battle, game) -> list[str]:
    """A fight with a story's boss begins: the template and every key found on the way take hold. Returns what to
    say (the battle's own log says the rest)."""
    from realmwalker.rules.combat import FOE

    out: list[str] = []
    advs = game.world.politics.get("adventures", {})
    out += _militia(battle, game, advs)
    from realmwalker.game.story import lieutenants

    for f in battle.side(FOE):
        lieutenants.arm(battle, f, game)  # (a lieutenant's morale, its try at escape, its grudges: E.3)
        tag = story_of(f.creature) if f.creature is not None else None
        if not tag or tag.get("role") != "villain":
            continue
        adv = advs.get(tag.get("adv"))
        if adv is None or adv.get("state") != "active" or adv.get("boss_dead"):
            continue  # (what was left of its band in its den, after it fell elsewhere, is no boss: E.4)
        battle.__dict__.setdefault("story_bosses", {})[f.id] = adv["id"]
        template = template_for(game.tables, adv)
        from realmwalker.game import story

        if not _is_finale(adv) and not story.at_its_den(adv, game.local.key if game.local is not None else None):
            # Met before its den it fights as itself, and breaks off when it is hurt (its template's "before"):
            # the template and the keys are for the end (law 5: the finale is where it stands and fights).
            # It gets away once in a tale, and never with what binds it in your hands (E.4).
            from realmwalker.game.story import early

            if template.get("before") and early.may_escape(game, adv):
                f.cdef = dict(f.cdef, boss_phase=dict(template["before"]))
            elif template.get("before"):
                line = early.no_flight(battle, game, adv, f)
                if line:
                    out.append(line)
            continue
        make_boss(battle, f, template, int(adv["tier"]))
        from realmwalker.game.story import early

        line = early.on_boss(battle, game, adv, f)  # (come back from the dead, and harder to put down: E.4)
        if line:
            out.append(line)
        battle.events.append({"kind": "boss", "who": f.id, "name": f.name, "line": adv["title"]})  # (its entrance)
        for found, keys in adv["finale"]["keys"].items():
            if found not in adv["keys"]:
                continue
            for text in keys:
                name, args = split_key(text)
                line = KEYS[name](battle, game, adv, f, *args)
                if line:
                    out.append(line)
    return out


MILITIA = 2  # the townsfolk who stand with you at a held place when you raised them (the key "militia")


def _militia(battle, game, advs: dict) -> list[str]:
    """A hold's wave (D.3): the people you raised stand with you (spears and pitchforks: the game's guards)."""
    from realmwalker.rules.combat import FOE, PARTY
    from realmwalker.rules.creatures import spawn

    tags = [story_of(f.creature) for f in battle.side(FOE) if f.creature is not None]
    adv = next((advs.get(t["adv"]) for t in tags if t and t.get("role") == "wave" and advs.get(t.get("adv"))), None)
    leader = next((f for f in battle.side(PARTY) if f.char is not None), None)
    if adv is None or "militia" not in adv["keys"] or leader is None or "guard" not in game.tables.creatures:
        return []
    for i in range(MILITIA):
        c = spawn(game.tables, "guard", battle.rng.child(f"militia/{i}"), 9100 + i, now=int(battle.now or 0))
        if not c.named:
            c.name = "militiaman" if i % 2 == 0 else "militiawoman"
        f = battle.add_ally(c, leader, "story_ally")
        f.auto = True  # (townsfolk fight as they can: you need not give them orders)
    return ["<good>The people you raised are here with you, spears and pitchforks and torches.</>"]


def _is_finale(adv: dict) -> bool:
    ch = adv["chapters"][adv["chapter"]] if adv["chapter"] < len(adv["chapters"]) else None
    return ch is not None and any(st["kind"] == "finale" and st["state"] == "open" for st in ch["steps"])


# ---------------------------------------------------------------------------- legendary actions and phases
@legendary("strike")
def _strike(f) -> list[dict]:
    """A blow out of turn with its best attack."""
    attacks = [a for a in f.cdef.get("attacks", ()) if a.get("kind") in ("melee", "ranged")]
    best = max(attacks, key=lambda a: (a.get("bonus", 0), str(a.get("damage", ""))), default=None)
    return [{"use": best["id"]}] if best is not None and best.get("id") else []


@legendary("move")
def _move(f) -> list[dict]:
    """It moves out of turn (half its speed, without drawing blows): Battle._legendary_window."""
    return [{"move": True}]


# ---------------------------------------------------------------------------- keys
@key("weakness")
def _weakness(battle, game, adv, boss, *args) -> str:
    """What it fears, learned on the way: the weakness's own keys, if the means are carried too."""
    wid = adv["hidden"].get("weakness", {}).get("weakness")
    w = None
    for lst in game.tables.villains.get("weaknesses", {}).values():
        for x in lst:
            if x["id"] == wid:
                w = x
    if w is None or "means" not in adv["keys"]:
        return ""
    lines = []
    for text in w["keys"]:
        name, a = split_key(text)
        if name != "weakness":
            line = KEYS[name](battle, game, adv, boss, *a)
            if line:
                lines.append(line)
    return " ".join(lines)


@key("vulnerable")
def _vulnerable(battle, game, adv, boss, dtype: str = "fire") -> str:
    d = dict(boss.cdef)
    d["vulnerable"] = sorted(set(d.get("vulnerable", [])) | {dtype})
    boss.cdef = d
    return f"<good>You know what it fears: {dtype} will hurt it twice over.</>"


@key("frightened")
def _frightened(battle, game, adv, boss, rounds: str = "1") -> str:
    from realmwalker.rules.engine import durations

    if durations.give(battle, boss, "frightened", rounds=int(rounds)):
        return "<good>It shies from what you carry, for a moment.</>"
    return ""


@key("surprise")
def _surprise(battle, game, adv, boss, *args) -> str:
    from realmwalker.rules.combat import FOE

    battle.env.surprised = FOE
    return "<good>It does not know you are here.</>"


@key("no_legendary_resistance")
def _no_lr(battle, game, adv, boss, *args) -> str:
    d = dict(boss.cdef)
    d["legendary_resistance"] = None
    boss.cdef = d
    return "<good>Whatever held it up so long holds it no more.</>"


@key("legendary_resistance")
def _less_lr(battle, game, adv, boss, n: str = "-1") -> str:
    d = dict(boss.cdef)
    lr = d.get("legendary_resistance") or {}
    if lr:
        d["legendary_resistance"] = {"per_day": max(0, int(lr.get("per_day", 0)) + int(n))}
    boss.cdef = d
    return ""


@key("minions")
def _minions(battle, game, adv, boss, percent: str = "-50") -> str:
    from realmwalker.rules.combat import FOE

    others = [f for f in battle.side(FOE) if f is not boss and f.state == "fighting"]
    gone = others[: int(len(others) * abs(int(percent)) / 100)]
    for f in gone:
        f.state = "fled"
    return f"<good>Fewer of them than there would have been: {len(gone)} not here.</>" if gone else ""


@key("no_phase_two")
def _no_phase(battle, game, adv, boss, *args) -> str:
    d = dict(boss.cdef)
    d.pop("boss_phase", None)
    boss.cdef = d
    return ""


@key("no_escape")
def _no_escape(battle, game, adv, boss, *args) -> str:
    """It cannot get away (what binds it is in your hands): a phase that would take it off the field never comes,
    and it does not run (E.4; before its finale, early.may_escape reads the same key)."""
    d = dict(boss.cdef)
    if (d.get("boss_phase") or {}).get("kind") in ("escape", "breaks_off"):
        d.pop("boss_phase", None)
    d["morale"] = "fanatic"
    boss.cdef = d
    return ""


@key("ally_fights")
def _ally_fights(battle, game, adv, boss, *args) -> str:
    """The ally who came with you fights beside you (as a hunter with a bow: the game's scout)."""
    from realmwalker.game.story import cast
    from realmwalker.rules.combat import PARTY
    from realmwalker.rules.creatures import spawn

    who = cast.person(game.world, adv["cast"].get("ally"))
    leader = next((f for f in battle.side(PARTY) if f.char is not None), None)
    if who is None or not getattr(who, "alive", True) or leader is None:
        return ""
    kind = "scout" if "scout" in game.tables.creatures else "guard"
    c = spawn(game.tables, kind, battle.rng.child("story-ally"), 1)
    c.name, c.named = who.name, True
    battle.add_ally(c, leader, "story_ally")
    return f"<good>{who.name} is with you, bow strung.</>"
