"""The finale (docs/ADVENTURES.md §5.8): a fair, epic fight.

A boss is a creature the game has, made a boss by a template (villains.json bosses): more hit points by tier,
Legendary Resistances, legendary actions from a menu (LEGENDARY), and a second phase at a share of its hit points
(PHASES). Keys found on the way change the fight (KEYS, applied by `prepare` from fight.start_battle before the
dice roll, the pattern of warding.at_the_start). One list for data and code: story/check.py reports names that are
not here.

The finale's band carries the story tag {"adv", "role"} on its creatures (saved with the actor); `prepare` finds
the adventure from it, so any fight with the boss is its finale, wherever it is met.

E.5: a template's `by_tier` {"3": {...}} overrides its numbers at the tiers above (more Legendary Resistances and
actions, "command" in the menu, a harder great attack); `great` is its telegraphed great attack (dc and damage a
list by tier: rules/engine/handlers/bosses.py); `entrance` its words as it enters (the battle's "boss" event, a banner
across the mat). The arena (game/story/arenas.py) is laid when the field is built, and armed here to change with the
second phase.
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


def at_tier(template: dict, tier: int) -> dict:
    """The template's numbers at this tier: its `by_tier` entries up to it laid over the base, in order."""
    out = dict(template)
    for t in sorted((int(k) for k in (template.get("by_tier") or {})), key=int):
        if t <= int(tier):
            out.update(template["by_tier"][str(t)])
    return out


def great_at(spec: dict, tier: int) -> dict:
    """A great attack's numbers at this tier (dc and damage are lists by tier, the last kept for the tiers above)."""
    d = dict(spec)
    for k in ("dc", "damage"):
        v = spec[k]
        d[k] = v[max(0, min(len(v) - 1, int(tier) - 1))] if isinstance(v, list) else v
    return d


def make_boss(battle, f, template: dict, tier: int) -> None:
    """The template on the creature: hit points, Legendary Resistances, legendary actions, the phase armed, its great
    attack (E.5)."""
    template = at_tier(template, tier)
    d = dict(f.cdef)
    mult = float(template["hp"]) * (1.0 + 0.15 * (int(tier) - int(template["tiers"][0])))
    hp = max(f.max_hp, int(round(f.max_hp * mult)), int((template.get("might") or {}).get("min_hp", 0)))
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
    if template.get("great"):
        d["boss_great"] = great_at(template["great"], tier)
    d["morale"] = "fanatic"  # (at its end it stands and fights: law 5, and the tale's own words)
    if (d.get("boss_phase") or {}).get("kind") not in ("escape", "breaks_off"):
        d["holds_ground"] = True  # (never off the field by running, turned or frightened: only its escape phase, E.6)
    _might(d, template.get("might") or {})
    f.cdef = d
    if f.creature is not None:
        f.creature.uses.pop("legendary_resistance", None)
        f.creature.uses.pop("legendary_actions", None)


def _might(d: dict, might: dict) -> None:
    """The template's might at its tier (E.6): harder to hit (`ac`), surer with its attacks and harder to resist
    (`hit`: their bonus and save DCs), each blow heavier (`damage`: a die more of the blow's own type), more blows
    (`multiattack`); and the least a boss of the tier has (`min_hp` in make_boss, `min_ac`, `min_hit`,
    `min_attacks`): a giant spider and a troll alike stand for the tier's foe, not for what they were in the book."""
    if not might:
        return
    d["ac"] = max(int(d["ac"]) + int(might.get("ac", 0)), int(might.get("min_ac", 0)))
    hit, more, least = int(might.get("hit", 0)), might.get("damage"), int(might.get("min_hit", 0))
    attacks = []
    for a in d.get("attacks", ()):
        a = dict(a)
        if a.get("kind") in ("melee", "ranged") and not a.get("single_save"):
            a["bonus"] = max(int(a.get("bonus", 0)) + hit, least)
            if more and a.get("damage"):
                a["extra"] = list(a.get("extra") or ()) + [{"damage": more, "type": a.get("damage_type", "bludgeoning")}]
        if a.get("dc"):
            a["dc"] = int(a["dc"]) + hit
        attacks.append(a)
    d["attacks"] = attacks
    if might.get("multiattack") or might.get("min_attacks"):
        d["multiattack"] = max(max(1, int(d.get("multiattack", 1) or 1)) + int(might.get("multiattack", 0)),
                               int(might.get("min_attacks", 0)))


def strength(tables) -> dict:
    return tables.adventures.get("strength") or {}


def strengthen(game, adv: dict, creatures: list, rng) -> None:
    """Fairness rule 1 (§5.8): the finale's band is set by its threat's tier, never by the hero's level or the land.
    Its guards for the tier (adventures.finale.json strength: by threat kind) join the boss's own band until the band
    is worth `share` of the High budget of a party of four (or more, if the party is bigger) at the tier's target
    level, `most` of them at the most (then a guard takes the place of the weakest of the rank and file). With no keys it is beyond High (the boss's template is not counted); its
    keys thin it (minions), surprise it, bring allies."""
    from realmwalker.rules import encounter
    from realmwalker.rules.creatures import spawn

    t = _story().threat_of(game, adv)
    kind = t["kind"] if t else ""
    spec = dict(strength(game.tables))
    spec.update((spec.get("by_kind") or {}).get(kind) or {})  # (a kind's own share and size)
    guards = [g for g in ((spec.get("guards") or {}).get(kind, {}).get(str(adv["tier"])) or ())
              if g in game.tables.creatures]
    if not spec or not guards or not creatures:
        return
    size = max(4, len([c for c in game.party if c.alive]))
    goal = float(spec.get("share", 1.0)) * encounter.budget(game.tables, [int(adv["target_level"])] * size,
                                                            str(spec.get("difficulty", "high")))
    worth = encounter.xp_of(game.tables, [c.def_id for c in creatures])
    uid = max(int(c.uid) for c in creatures) + 1
    xp = {g: int(game.tables.creatures[g]["xp"]) for g in guards}
    most = int(spec.get("most", 8))
    while worth < goal:
        weak = None
        if len(creatures) >= most:  # (full: a guard takes the place of the weakest of its rank and file)
            plain = [c for c in creatures[1:] if (c.story or {}).get("role", "minion") == "minion"]
            weak = min(plain, key=lambda c: int(game.tables.creatures[c.def_id]["xp"]), default=None)
            if weak is None or int(game.tables.creatures[weak.def_id]["xp"]) >= min(xp.values()):
                break
        room = goal - worth + (int(game.tables.creatures[weak.def_id]["xp"]) if weak is not None else 0)
        fits = [g for g in guards if xp[g] <= room]  # (as often as the list names it)
        g = rng.choice(fits or [min(guards, key=xp.get)])
        c = spawn(game.tables, g, rng.child(f"guard{uid}"), uid, now=game.world.time)
        c.story = {"adv": adv["id"], "role": "minion"}
        if weak is not None:
            worth -= int(game.tables.creatures[weak.def_id]["xp"])
            creatures.remove(weak)
        creatures.append(c)
        worth += xp[g]
        uid += 1


def _story():
    from realmwalker.game import story

    return story


def prepare(battle, game) -> list[str]:
    """A fight with a story's boss begins: the template and every key found on the way take hold. Returns what to
    say (the battle's own log says the rest)."""
    from realmwalker.rules.combat import FOE

    out: list[str] = []
    advs = game.world.politics.get("adventures", {})
    out += _militia(battle, game, advs)
    from realmwalker.game.story import stakes

    out += stakes.to_battle(battle, game, advs)  # (an ally who rides with the patron comes to the tale's fights: F.1)
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
        battle.__dict__["finale_of"] = adv["id"]  # (its retreat and its defeat: story/defeat.py)
        from realmwalker.game.story import early

        line = early.on_boss(battle, game, adv, f)  # (come back from the dead, and harder to put down: E.4)
        if line:
            out.append(line)
        entrance = at_tier(template, int(adv["tier"])).get("entrance")
        if entrance:  # (its entrance: the words, and its name across the mat)
            from realmwalker.core.textgen import escape_markup as esc

            words = battle.rng.choice(entrance).replace("{name}", esc(f.the_name))
            out.append(f"<danger>{words[:1].upper() + words[1:]}</>")
        battle.events.append({"kind": "boss", "who": f.id, "name": f.name, "line": adv["title"]})
        from realmwalker.game.story import arenas

        out += arenas.on_finale(battle, game, adv, f)  # (the arena armed to change with its second phase)
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


@legendary("command")
def _command(f) -> list[dict]:
    """One of its own side strikes at its word (rules/engine/handlers/bosses.command)."""
    return [{"command": True}]


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

    others = [f for f in battle.side(FOE) if f is not boss and f.state == "fighting"
              and (story_of(f.creature) or {}).get("role", "minion") == "minion"]  # (a lieutenant has its own key)
    n = int(len(others) * abs(int(percent)) / 100)
    others.sort(key=lambda f: (-int(f.cdef.get("xp", 0)), f.id))
    gone = (others[0::2] + others[1::2])[:n]  # (every other one, strongest first: half of each kind, E.6)
    for f in gone:
        f.state = "fled"
    return f"<good>{_say(game, adv, 'minions_gone', n=len(gone))}</>" if gone else ""


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
    d["holds_ground"] = True
    boss.cdef = d
    return ""


@key("ally_fights")
def _ally_fights(battle, game, adv, boss, *args) -> str:
    """The ally who came with you fights beside you (as the creature of its tale's tier: adventures.finale.json
    strength "ally"; a hunter with a bow at the first)."""
    from realmwalker.game.story import cast
    from realmwalker.rules.combat import PARTY
    from realmwalker.rules.creatures import spawn

    who = cast.person(game.world, adv["cast"].get("ally"))
    leader = next((f for f in battle.side(PARTY) if f.char is not None), None)
    if who is None or not getattr(who, "alive", True) or leader is None:
        return ""
    from realmwalker.game.story import stakes

    if adv.get("ally"):  # (an ally with a stake is in the party, or came from the patron's side: F.1)
        here = stakes.fighting(battle, adv) or stakes.companion_of(game, adv, waiting=False) is not None
        return f"<good>{_say(game, adv, 'ally_with', who=who.name)}</>" if here else ""
    kinds = strength(game.tables).get("ally") or ["scout"]  # (by its tale's tier: E.6)
    kind = kinds[max(0, min(len(kinds) - 1, int(adv["tier"]) - 1))]
    kind = kind if kind in game.tables.creatures else "guard"
    c = spawn(game.tables, kind, battle.rng.child("story-ally"), 1)
    c.name, c.named = who.name, True
    battle.add_ally(c, leader, "story_ally")
    return f"<good>{_say(game, adv, 'ally_with', who=who.name)}</>"


RIVAL_KIND = "scout"  # who comes when no rival band is cast: hunters of the land with bows
PARTY_BUFFS = {  # party_buff(<name>): what the beacon lit or the ground hallowed gives the party for the fight
    "bless": {"attack_die": "1d4", "save_die": "1d4"},
    "courage": {"immune": ["frightened"]},
    "warded": {"resist": ["necrotic"]},
}


@key("rival_arrives")
def _rival_arrives(battle, game, adv, boss, rnd: str = "3") -> str:
    """The rival you befriended comes on the round named, with its band, from your side of the field."""
    from realmwalker.game.story import cast
    from realmwalker.rules.combat import PARTY
    from realmwalker.rules.creatures import spawn

    when = int(rnd)
    who = cast.person(game.world, (adv["cast"].get("rival") or {}).get("npc")) if adv["cast"].get("rival") else None
    name = who.name if who is not None else ""

    def arrive(b, _done=[]):
        if _done or b.round < when or b.outcome is not None:
            return
        _done.append(True)
        leader = next((f for f in b.side(PARTY) if f.char is not None and f.active), None)
        if leader is None:
            return
        kind = RIVAL_KIND if RIVAL_KIND in game.tables.creatures else "guard"
        edge = (0, leader.y) if leader.x < b.field.width // 2 else (b.field.width - 1, leader.y)
        for i in range(2):
            c = spawn(game.tables, kind, b.rng.child(f"rival/{i}"), 9200 + i, now=int(b.now or 0))
            if i == 0 and name:
                c.name, c.named = name, True
            f = b.add_ally(c, leader, "story_ally", point=edge)
            f.auto = True
        b.say(_say(game, adv, "rival_comes", who=f"{name} and their band" if name else "your rivals"), "good")
        b._event("arrive", who=leader.id)

    battle.round_hooks.append(arrive)
    return f"<good>{_say(game, adv, 'rival_promised', who=f"{name} and their band" if name else "your rivals")}</>"


@key("party_buff")
def _party_buff(battle, game, adv, boss, name: str = "bless") -> str:
    from realmwalker.rules.combat import PARTY
    from realmwalker.rules.engine import durations

    buff = PARTY_BUFFS.get(name)
    if buff is None:
        return ""
    for f in battle.side(PARTY):
        if f.active:
            durations.buff(f, dict(buff, source=f"story:{name}"))
    return f"<good>{_say(game, adv, 'blessed_' + name)}</>"


@key("rite_allowed")
def _rite_allowed(battle, game, adv, boss, *args) -> str:
    """The rite can be finished over its body: if it falls in this fight with what the rite needs in your hands, the
    rite is done (story.on_battle)."""
    battle.__dict__["rite_allowed"] = adv["id"]
    return f"<good>{_say(game, adv, 'rite_allowed')}</>"


@key("lieutenant_absent")
def _lieutenant_absent(battle, game, adv, boss, role: str = "") -> str:
    """That lieutenant is not in the fight (sent away, kept busy): taken off the field before it begins."""
    from realmwalker.rules.combat import FOE

    gone = [f for f in battle.side(FOE) if f.creature is not None and (story_of(f.creature) or {}).get("role") == role]
    bands = list(game.local.actors) if game.local is not None else []
    for f in gone:
        battle.fighters.remove(f)
        if f.id in battle.order:
            battle.order.remove(f.id)
        for a in bands:  # (it is off on the errand it was given: free, and still the villain's)
            a.creatures = [c for c in a.creatures if c is not f.creature]
    return f"<good>{_say(game, adv, 'lieutenant_absent', who=gone[0].name)}</>" if gone else ""


def _say(game, adv, key: str, **more) -> str:
    """A line of the finale's words (adventures.finale.json), filled and escaped for the battle's log."""
    from realmwalker.core.textgen import escape_markup as esc
    from realmwalker.game.story import deeds

    return esc(deeds.say(game, adv, key, **more))
