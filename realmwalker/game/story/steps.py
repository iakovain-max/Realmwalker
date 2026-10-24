"""The step kinds of adventures (docs/ADVENTURES.md §5.2, §8.5): a registry of small handlers by id.

A step kind is a class registered with `@step("go")`. Its `fields` are the keys a blueprint's step may carry besides
the common ones (story/check.py reports any other). The forge calls `bind(forge, spec)` once to turn the blueprint's
words into a target (JSON-native); the game's listeners (story/__init__.py) say when a step is done; `repair` keeps
an adventure from ever being stuck (law 6): when a step's target is gone, it binds a new one, or is done another way.

A step record: {"id": "killings.2", "kind", "state" (open, done, failed), "target", "optional", "gives", "beat"}.
`gives` are what finishing it brings: "clue:<truth>", "key:<k>", "lead:<place>", "flag:<f>" (a choose step's beat
sets one of its "flag:a|flag:b" itself).

Part A's kinds: go, search, witness, read, learn, prepare, choose, slay, finale.
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
