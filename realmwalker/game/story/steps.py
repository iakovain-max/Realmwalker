"""The step kinds of adventures (docs/ADVENTURES.md §5.2, §8.5): a registry of small handlers by id.

A step kind is a class registered with `@step("go")`. Its `fields` are the keys a blueprint's step may carry besides
the common ones (story/check.py reports any other). The forge calls `bind(forge, spec)` once to turn the blueprint's
words into a target (JSON-native); the game's listeners (story/__init__.py) say when a step is done; `repair` keeps
an adventure from ever being stuck (law 6): when a step's target is gone, it binds a new one, or is done another way.

A step record: {"id": "killings.2", "kind", "state" (open, done, failed), "target", "optional", "gives", "beat"}.
`gives` are what finishing it brings: "clue:<truth>", "key:<k>", "lead:<place>", "flag:<f>" (a choose step's beat
sets one of its "flag:a|flag:b" itself).

Part A's kinds: go, search, witness, read, learn, prepare, choose, slay, finale. Part D's: rescue, fetch, defeat,
capture, recruit, rally, hold, rite, escort, confront (their game side, setup and listeners, is story/deeds.py). A kind
may say `goal(st)`: a test of the goal language (story/goals.py) that finishes it however it was made true. A step's
`fails_to` is the codeword a failed step leaves (a failed step still moves its chapter on: law 6).
"""

from __future__ import annotations

STEPS: dict[str, type] = {}
COMMON = {"kind", "id", "optional", "gives", "fails_to", "tier_min", "words", "beat"}
LEARN_ROUTES = 3  # every truth has at least three ways to be learned (the three-clue rule)


def step(kind: str):
    def wrap(cls):
        cls.kind = kind
        STEPS[kind] = cls
        return cls
    return wrap


class Step:
    """The default behaviour of every kind: its place bound, nothing to repair."""
    kind = ""
    fields: frozenset = frozenset()
    fight = False  # (the content rule: every chapter has a step that is not a fight)
    beat_finishes = False  # whether playing its beat finishes it (else the beat's own "step_done" op does)

    @classmethod
    def allowed(cls) -> set:
        return COMMON | set(cls.fields)

    @classmethod
    def bind(cls, forge, spec: dict) -> dict:
        t = {}
        if "at" in spec:
            t["place"] = forge.place(spec["at"])
        return t

    @classmethod
    def repair(cls, game, adv: dict, st: dict) -> bool:
        """True when it changed the step (a new target, or done another way)."""
        return False

    @classmethod
    def goal(cls, st: dict):
        """A goal-language test that finishes the step when it holds (None: it has none)."""
        return None


@step("go")
class Go(Step):
    """Reach a place: a town, a site, a field. Its beat (if any) plays on arrival."""
    fields = frozenset({"at"})
    beat_finishes = True


@step("search")
class Search(Step):
    """Search a place (a kill, a body, a battlefield): its beat plays there, with a check that can only cost time."""
    fields = frozenset({"at", "skill", "dc"})
    beat_finishes = True

    @classmethod
    def bind(cls, forge, spec):
        t = super().bind(forge, spec)
        t["skill"] = spec.get("skill", "investigation")
        t["dc"] = int(spec.get("dc", 12))
        return t


@step("witness")
class Witness(Step):
    """Talk to someone who saw it (a role of the cast); they tell it in a conversation."""
    fields = frozenset({"who"})

    @classmethod
    def bind(cls, forge, spec):
        role = spec["who"]
        return {"role": role, "who": dict(forge.cast.get(role) or {})}

    @classmethod
    def repair(cls, game, adv, st):
        from realmwalker.game.story import cast

        who = cast.person(game.world, st["target"].get("who"))
        if who is None or getattr(who, "alive", True):
            return False
        entry = st["target"]["who"]
        sid = entry.get("settlement")
        if sid is not None:
            other = cast._choose(game, int(sid), {"job": entry.get("job", "farmer"), "jobs": [entry.get("job", "farmer")]},
                                 adv)
            if other is not None:
                adv["cast"][st["target"]["role"]] = cast._take(other, adv, st["target"]["role"], entry)
                st["target"]["who"] = dict(adv["cast"][st["target"]["role"]])
                return True
        st["state"] = "done"  # (no one left who saw it: the tale is told by the bodies themselves)
        return True


@step("read")
class Read(Step):
    """Read a document: a letter, a chronicle, an order (a book item with the step's tag)."""
    fields = frozenset({"what"})

    @classmethod
    def bind(cls, forge, spec):
        return {"item": spec["what"], "tag": f"story:{forge.aid}:{forge.step_id}"}


@step("learn")
class Learn(Step):
    """Learn a truth by any of several routes (a sage, someone who knows, a check at the place, divination)."""
    fields = frozenset({"about", "routes"})

    @classmethod
    def bind(cls, forge, spec):
        routes = []
        for r in spec["routes"]:
            for found in forge.resolve_all(r)[:1]:
                if "who" in found and isinstance(found["who"], dict) and "job" in found["who"] and \
                        "npc" not in found["who"]:
                    found = dict(found, who=dict(found["who"]))
                role = forge.role_named(r)
                if role:
                    found = dict(found, role=role)
                routes.append(found)
        if len(routes) < LEARN_ROUTES:
            forge.fail(f"the truth '{spec['about']}' has only {len(routes)} ways to be learned")
        return {"truth": spec["about"], "routes": routes}

    @classmethod
    def repair(cls, game, adv, st):
        from realmwalker.game.story import cast

        before = len(st["target"]["routes"])
        st["target"]["routes"] = [r for r in st["target"]["routes"] if r.get("how") != "talk" or
                                  cast.pending(r.get("who")) or getattr(cast.person(game.world, r.get("who")),
                                                                        "alive", True)]
        return len(st["target"]["routes"]) != before


@step("prepare")
class Prepare(Step):
    """Get the means: whatever the truth learned says will work (fire, silver, a bait), bought or made."""
    fields = frozenset({"what"})

    @classmethod
    def bind(cls, forge, spec):
        what = spec["what"]
        means = []
        if what in forge.hidden and "weakness" in forge.hidden[what]:
            w = forge.weakness(forge.hidden[what]["weakness"])
            means = list(w.get("means", [])) if w else []
        elif isinstance(what, list):
            means = list(what)
        if not means:
            forge.fail(f"nothing names the means for '{what}'")
        return {"means": means}


@step("choose")
class Choose(Step):
    """A decision that splits the story: its beat's choices set the codeword."""
    fields = frozenset()
    beat_finishes = True

    @classmethod
    def bind(cls, forge, spec):
        if "beat" not in spec:
            forge.fail("a choose step needs its beat")
        return {}


@step("slay")
class Slay(Step):
    """Defeat a named foe of the story (by the story tag on the creatures), met at a place."""
    fields = frozenset({"who", "at", "fled_ok"})
    fight = True

    @classmethod
    def bind(cls, forge, spec):
        t = super().bind(forge, spec)
        t["role"] = spec["who"]
        t["fled_ok"] = bool(spec.get("fled_ok", False))
        return t


@step("finale")
class Finale(Step):
    """The end of it: the boss's band, bound to its exact dungeon level (or a field), and the fight."""
    fields = frozenset({"at"})
    fight = True

    @classmethod
    def bind(cls, forge, spec):
        from realmwalker.game.story import places

        t = super().bind(forge, spec)
        key = places.dungeon_key(forge.world, t["place"])
        if key is not None:
            t["level"] = key
        return t


# ---------------------------------------------------------------------------- Part D's kinds (game side: story/deeds.py)
def _level(forge, place: dict, kind: str) -> tuple[str, int]:
    """The dungeon level a step's place names (`home.level(1)`, `home.deepest`): its key and number."""
    from realmwalker.game.story import places

    key, n = places.dungeon_key(forge.world, place), places.dungeon_level(forge.world, place)
    if key is None or n is None:
        forge.fail(f"a {kind} step needs a level under a site (site.level(n) or site.deepest)")
    return key, int(n)


def _who(forge, spec: dict, field: str = "who") -> dict:
    role = spec[field]
    if role not in forge.cast and role != "villain":
        forge.fail(f"the role '{role}' is not cast")
    return {"role": role, "who": dict(forge.cast.get(role) or {})}


def _check(spec: dict, skill: str, dc: int) -> dict:
    c = spec.get("check") or [skill, dc]
    return {"skill": str(c[0]), "dc": int(c[1])}


@step("rescue")
class Rescue(Step):
    """Free someone the story's foes hold, on a level of a site above its master's hall (a step quest of the rescue
    kind: the captive in chains, placed on that level when the party comes down to it)."""
    fields = frozenset({"who", "at"})

    @classmethod
    def bind(cls, forge, spec):
        t = super().bind(forge, spec)
        t.update(_who(forge, spec))
        t["level"], t["n"] = _level(forge, t["place"], "rescue")
        return t

    @classmethod
    def goal(cls, st: dict):
        return ["free", st["target"]["role"]] if "npc" in st["target"].get("who", {}) else None


@step("fetch")
class Fetch(Step):
    """Bring back a thing of the story (an anchor, a relic, a ledger) from where it lies: a chest on a level of a site
    holding an item tagged for this step; done once it is carried (the goal holds(you, tag))."""
    fields = frozenset({"what", "base", "at"})

    @classmethod
    def bind(cls, forge, spec):
        t = super().bind(forge, spec)
        t["level"], t["n"] = _level(forge, t["place"], "fetch")
        t["what"] = spec["what"]
        t["base"] = spec.get("base", "gold_ring")
        if t["base"] not in forge.tables.items:
            forge.fail(f"no item '{t['base']}' to be the thing fetched")
        t["tag"] = f"story:{forge.aid}:{forge.step_id}"
        return t

    @classmethod
    def goal(cls, st: dict):
        return ["holds", "you", st["target"]["tag"]]


@step("defeat")
class Defeat(Step):
    """Overcome a foe of the story's cast (a lieutenant, the waker, a raiding party): slain or taken alive, met at a
    place - their band on a level of a site, or waiting on a tile of the land. How it ended is a codeword
    (<role>_slain, <role>_taken)."""
    fields = frozenset({"who", "at", "group", "fled_ok"})
    fight = True
    slain_ok = True

    @classmethod
    def bind(cls, forge, spec):
        from realmwalker.game.story import places

        t = super().bind(forge, spec)
        t.update(_who(forge, spec))
        key = places.dungeon_key(forge.world, t["place"])
        if key is not None:
            t["level"] = key
        group = spec.get("group") or (forge.cast.get(spec["who"]) or {}).get("band")
        if not group or group not in forge.tables.creatures.encounters:
            forge.fail(f"no band for the {spec['who']} ({group})")
        t["group"] = group
        t["fled_ok"] = bool(spec.get("fled_ok", False))
        return t


@step("capture")
class Capture(Defeat):
    """Take a foe of the story alive (the aftermath's capture, or questioning them there: `story.on_fate` from
    `fight.decide_captive`); questioned, they give the step's lead. Killed instead, the step fails (its fails_to)."""
    slain_ok = False


@step("recruit")
class Recruit(Step):
    """Win someone of the cast to your side (a talk with a check, or a price): the key "<role>" (the ally fights at
    the finale); refused, they may be asked again the next day. May become a situation (§8.10)."""
    fields = frozenset({"who", "check", "price"})

    @classmethod
    def bind(cls, forge, spec):
        t = _who(forge, spec)
        t.update(_check(spec, "persuasion", 12))
        t["price"] = int(spec.get("price", 0))
        return t


@step("rally")
class Rally(Step):
    """Raise the people of a place to stand (the militia): a talk with its headman (or the role named) and a check;
    the key "militia". May become a situation."""
    fields = frozenset({"at", "who", "check"})

    @classmethod
    def bind(cls, forge, spec):
        t = super().bind(forge, spec)
        if "settlement" not in t.get("place", {}):
            forge.fail("a rally step needs a settlement")
        if "who" in spec:
            t.update(_who(forge, spec))
        t.update(_check(spec, "persuasion", 13))
        return t


@step("hold")
class Hold(Step):
    """Hold a place on a set night (said in the journal): waves of the foe as battles one after another with no rest
    between, at a settlement or on a road tile. Not there that night, or beaten, it fails (fails_to)."""
    fields = frozenset({"at", "days", "waves", "group"})
    fight = True

    @classmethod
    def bind(cls, forge, spec):
        t = super().bind(forge, spec)
        if "site" in t["place"]:
            forge.fail("a hold step is at a settlement or on the land, not under a site")
        group = spec.get("group")
        if not group or group not in forge.tables.creatures.encounters:
            forge.fail(f"no band for the waves ({group})")
        t["group"] = group
        t["days"] = [int(d) for d in spec.get("days", [6, 9])]
        t["waves"] = int(spec.get("waves", 2 + min(2, int(forge.threat["tier"]) - 1)))
        return t


@step("rite")
class Rite(Step):
    """A rite at a place (laying the dead to rest, sealing a door): there, with what it needs (keys or story things
    carried), and a check that can only cost time. Its beat, if any, plays it."""
    fields = frozenset({"at", "needs", "check"})
    beat_finishes = True

    @classmethod
    def bind(cls, forge, spec):
        t = super().bind(forge, spec)
        t["needs"] = list(spec.get("needs", []))
        t.update(_check(spec, "religion", 13))
        return t


@step("escort")
class Escort(Step):
    """Walk someone of the cast (or a caravan's carter) to a place (a step quest of the escort kind); an `ambush`
    band may fall on you on the way. Done when they get there alive (the goal at(who, to))."""
    fields = frozenset({"who", "to", "ambush"})

    @classmethod
    def bind(cls, forge, spec):
        t = _who(forge, spec)
        t["to"] = forge.place(spec["to"])
        if "settlement" not in t["to"]:
            forge.fail("an escort step ends at a settlement")
        amb = spec.get("ambush")
        if amb and amb not in forge.tables.creatures.encounters:
            forge.fail(f"no band '{amb}' for the ambush")
        t["ambush"] = amb
        return t

    @classmethod
    def goal(cls, st: dict):
        return ["at", st["target"]["role"], dict(st["target"]["to"])] if "npc" in st["target"].get("who", {}) \
            else None


@step("confront")
class Confront(Step):
    """Face someone of the cast with what you know (the inside man): a talk, with a check unless you hold the step's
    clue; they yield (a codeword) or fight (their band, `group`). May become a situation."""
    fields = frozenset({"who", "check", "clue", "group"})

    @classmethod
    def bind(cls, forge, spec):
        t = _who(forge, spec)
        t.update(_check(spec, "intimidation", 14))
        t["clue"] = spec.get("clue")
        group = spec.get("group", "thugs")
        if group not in forge.tables.creatures.encounters:
            forge.fail(f"no band '{group}' for the one confronted")
        t["group"] = group
        return t
