"""The forge (docs/ADVENTURES.md §8.5): a blueprint and a threat become an adventure, once, when its hook is taken.

`make(game, threat)` tries each blueprint made from the threat's kind and fitting its tier, seeded by the new
adventure's id (`rng.child(f"adventure/{aid}")`), so the same world and the same choices forge the same tale:
1. places, by selectors; 2. the cast, from the world first (people of towns never filled yet are chosen when they
are: story/cast.py); 3. the hidden truths; 4. chapters and steps (each kind binds its target; every truth with at
least three routes; the content rule: every chapter has a step that is not a fight and a choice that leaves a
codeword); 5. the tier's target level; 6. `story_sites` for the finale's exact dungeon level; 7. the words, written
once and kept; 8. the record in `politics["adventures"]`, the threat engaged and its offer cleared.
A blueprint that cannot be forged here (a selector finds nothing) gives way to the next; none: None.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.game.story import cast as castmod
from realmwalker.game.story import places as pl
from realmwalker.game.story import selectors as sel
from realmwalker.game.story.steps import STEPS


class ForgeFailed(Exception):
    pass


def records(world) -> dict:
    return world.politics.setdefault("adventures", {})


def _built(entry) -> bool:
    from realmwalker.game.story.check import BUILT_PARTS

    return not isinstance(entry, dict) or entry.get("from_part", "A") in BUILT_PARTS


class Forge:
    def __init__(self, game, threat: dict, bid: str, bp: dict, aid: str, rng) -> None:
        self.game = game
        self.world = game.world
        self.tables = game.tables
        self.threat = threat
        self.bid = bid
        self.bp = bp
        self.aid = aid
        self.rng = rng
        self.home = dict(threat["home"])
        self.places: dict[str, dict] = {}
        self.cast: dict[str, dict] = {}
        self.hidden: dict[str, dict] = {}
        self.candidates: dict[str, list] = {}
        self.step_id = ""

    def fail(self, why: str):
        raise ForgeFailed(why)

    # ------------------------------------------------------------------ selectors
    def resolve_all(self, text: str) -> list:
        return self.evaluate(sel.parse(text))

    def place(self, text: str) -> dict:
        found = self.resolve_all(text)
        if not found:
            self.fail(f"no place for '{text}'")
        return found[0]

    def role_named(self, text: str) -> str | None:
        """The cast role a route names ("ask(ally)" -> "ally"), so the route follows whoever is bound to it."""
        try:
            node = sel.parse(text)
        except sel.SelectorError:
            return None
        if isinstance(node, sel.Call):
            for a in node.args:
                if isinstance(a, sel.Path) and len(a.parts) == 1 and a.parts[0] in self.cast:
                    return a.parts[0]
        return None

    def weakness(self, wid: str) -> dict | None:
        for lst in self.tables.villains.get("weaknesses", {}).values():
            for w in lst:
                if w["id"] == wid:
                    return w
        return None

    def evaluate(self, node) -> list:
        if isinstance(node, int):
            return [node]
        if isinstance(node, sel.Words):
            return [list(node.words)]
        if isinstance(node, sel.Alt):
            for o in node.options:
                found = self.evaluate(o)
                if found:
                    return found
            return []
        if isinstance(node, sel.Path):
            return self._path(node)
        if node.name == "hidden":
            n = int(node.args[0]) if node.args and isinstance(node.args[0], int) else 1
            options = []
            for a in node.args[1:]:
                found = self.evaluate(a)
                if found and found[0] not in options:
                    options.append(found[0])
            options = options[:max(1, n)]
            if not options:
                return []
            pick = self.rng.choice(options)
            return [pick] + [o for o in options if o != pick]
        fn = sel.SELECTORS.get(node.name)
        if fn is None:
            self.fail(f"unknown selector {node.name}")
        args = []
        for a in node.args:
            if isinstance(a, int):
                args.append(a)
            elif isinstance(a, sel.Words):
                args.append(list(a.words))
            else:
                found = self.evaluate(a)
                if not found and isinstance(a, sel.Path) and len(a.parts) == 1 and isinstance(a.parts[0], str)                         and a.parts[0] not in self.places and a.parts[0] not in self.cast:
                    found = [a.parts[0]]  # (a word given to a selector: settlement_with(temple, 0, 40))
                if not found:
                    return []
                args.append(found[0])
        return list(fn(self, *args))

    def _path(self, node: sel.Path) -> list:
        root, rest = node.parts[0], node.parts[1:]
        if root == "threat" and rest[:1] == ["home"]:
            base, rest = dict(self.home), rest[1:]
        elif root == "villain" and not rest:
            return [{"figure": self.threat["villain"].get("figure")}]
        elif root == "tier" and not rest:
            return [int(self.threat["tier"])]
        elif root in self.places:
            base = dict(self.places[root])
        elif root in self.cast and not rest:
            return [dict(self.cast[root])]
        elif root in self.hidden and not rest:
            return [dict(self.hidden[root])]
        else:
            return []
        for part in rest:
            if isinstance(part, sel.Call) and part.name == "level":
                base = dict(base, part="level", level=int(part.args[0]) if part.args else 1)
            elif part in ("deepest", "outskirts", "inn"):
                base = dict(base, part=part)
            else:
                return []
        return [base]

    def pick(self, found: list):
        """A little variety among the best few (the nearest town, or the next nearest)."""
        return self.rng.choice(found[:2]) if len(found) > 1 else found[0]

    # ------------------------------------------------------------------ the forging
    def build(self) -> dict:
        bp, w, rng = self.bp, self.world, self.rng
        for name, text in bp["places"].items():
            found = self.resolve_all(text)
            if not found:
                self.fail(f"no place for {name} ({text})")
            asked = (self.threat.get("offer") or {}).get("by")
            if name == "town" and asked is not None and {"settlement": int(asked)} in found:
                self.places[name] = {"settlement": int(asked)}  # (the town whose people asked is the tale's town)
            else:
                self.places[name] = dict(found[0]) if text.startswith("threat.") else dict(self.pick(found))
        for role, spec in bp["cast"].items():
            if not _built(spec) or ("chance" in spec and not rng.chance(float(spec["chance"]))):
                continue
            for text in spec["pick"]:
                found = self.resolve_all(text)
                if found:
                    self.cast[role] = dict(found[0])
                    break
            else:
                self.fail(f"nobody to be the {role}")
        for name, text in bp.get("hidden", {}).items():
            found = self.resolve_all(text)
            if not found:
                self.fail(f"nothing for the hidden {name}")
            self.hidden[name] = dict(found[0])
            self.candidates[name] = [dict(f) for f in found]
        tier = int(self.threat["tier"])
        chapters = []
        for ci, ch in enumerate(c for c in bp["chapters"] if int(c.get("tier_min", 1)) <= tier):
            steps = []
            for si, spec in enumerate(s for s in ch["steps"] if _built(s) and int(s.get("tier_min", 1)) <= tier):
                self.step_id = f"{ch['id']}.{si + 1}"
                cls = STEPS[spec["kind"]]
                st = {"id": self.step_id, "kind": spec["kind"], "state": "open", "target": cls.bind(self, spec),
                      "optional": bool(spec.get("optional", False)), "gives": list(spec.get("gives", []))}
                if "beat" in spec:
                    st["beat"] = spec["beat"]
                if "fails_to" in spec:
                    st["fails_to"] = spec["fails_to"]
                steps.append(st)
            self._content_rule(ch["id"], steps)
            chapters.append({"id": ch["id"], "state": "open" if ci == 0 else "locked", "need": ch["need"],
                             "title": rng.choice(ch["title"]), "goal": rng.choice(ch["goal"]), "steps": steps,
                             "opening": rng.choice(ch["opening"]), "reveal": rng.choice(ch["reveal"])})
        return self._record(chapters)

    def _content_rule(self, cid: str, steps: list[dict]) -> None:
        if all(STEPS[s["kind"]].fight for s in steps):
            self.fail(f"chapter {cid} is nothing but fights")
        if not any(self._leaves_codeword(s) for s in steps):
            self.fail(f"chapter {cid} has no choice that leaves a codeword")

    def _leaves_codeword(self, st: dict) -> bool:
        if any(g.startswith("flag:") for g in st["gives"]):
            return True
        beat = self.tables.beats.get(st.get("beat", ""))
        if not beat:
            return False
        for ch in beat.get("choices", []):
            for part in ("ops", "success", "failure"):
                if any(op and op[0] == "flag" for op in ch.get(part, [])):
                    return True
        return False

    def _record(self, chapters: list[dict]) -> dict:
        game, w, bp, rng = self.game, self.world, self.bp, self.rng
        from realmwalker.world import news

        t = self.threat
        title = rng.choice(bp["title"])
        lead = game.leader
        adv = {"id": self.aid, "threat": t["id"], "blueprint": self.bid, "tier": int(t["tier"]), "title": title,
               "state": "active", "hero": {"name": lead.name, "life": life_of(game)},
               "began": float(news.now_days(w)), "chapter": 0, "cast": {}, "places": self.places,
               "hidden": self.hidden, "candidates": self.candidates, "reading": None, "chapters": chapters,
               "clues": {}, "keys": [], "flags": [], "attention": 0, "moves": [], "journal": [],
               "ending": None, "epilogue": [],
               "target_level": int(self.tables.threats.get("target_level", {}).get(str(t["tier"]), 3)),
               "finale": {"template": bp["finale"]["template"], "keys": dict(bp["finale"].get("keys", {})),
                          "boss": bp["finale"]["boss"]},
               "words": {"hook": rng.choice(bp["hook"]), "premise": rng.choice(bp["premise"])}}
        for role, entry in self.cast.items():
            adv["cast"][role] = castmod.bind_now(game, adv, role, entry) if castmod.pending(entry) else dict(entry)
        # (the words are written once the cast is bound: the patron, the villain's kind, its victim, the area)
        from realmwalker.game.story import words as wordsmod

        words = wordsmod.for_adventure(game, adv)
        words.setdefault("place", words.get("town", pl.name(w, self.home)))
        tables = self.tables.adventures.get("words", {})
        adv["title"] = textgen.fill(adv["title"], rng, tables, words)
        for k in ("hook", "premise"):
            adv["words"][k] = textgen.fill(adv["words"][k], rng, tables, words)
        for ch in chapters:
            for k in ("title", "goal", "opening", "reveal"):
                ch[k] = textgen.fill(ch[k], rng, tables, words)
        for ch in chapters:  # (steps that name a role see whoever was bound to it)
            for st in ch["steps"]:
                if "role" in st["target"]:
                    st["target"]["who"] = dict(adv["cast"].get(st["target"]["role"], {}))
                for r in st["target"].get("routes", []):
                    if "role" in r:
                        r["who"] = dict(adv["cast"].get(r["role"], {}))
        for ch in chapters:
            for st in ch["steps"]:
                key = st["target"].get("level")
                if st["kind"] == "finale" and key:
                    w.politics.setdefault("story_sites", {}).setdefault(key, []).append(
                        {"adv": self.aid, "what": "band", "roles": [bp["finale"]["boss"]] +
                         list(bp["finale"].get("with", []))})
        return adv


def life_of(game) -> str:
    """Which life this is (the world, the character's name and the day they set out): two heroes of one name differ."""
    return f"{game.world.meta.id}:{game.leader.name}:{int(game.renown.flags.get('start_day', 0))}"


def fitting(game, threat: dict) -> list[str]:
    bps = game.tables.adventures.get("blueprints", {})
    kind = game.tables.threats["kinds"].get(threat["kind"], {})
    return [b for b in kind.get("blueprints", []) if b in bps and threat["kind"] in bps[b]["from"]
            and bps[b]["tiers"][0] <= int(threat["tier"]) <= bps[b]["tiers"][1]]


def make(game, threat: dict) -> dict | None:
    """Forge an adventure on a threat (its hook taken). The record is stored; None when no blueprint fits here."""
    w = game.world
    for bid in fitting(game, threat):
        n = int(w.politics.get("next_adventure", 0))
        aid = f"A{n}"
        forge = Forge(game, threat, bid, game.tables.adventures["blueprints"][bid], aid, w.rng.child(f"adventure/{aid}"))
        try:
            sites_before = {k: list(v) for k, v in w.politics.get("story_sites", {}).items()}
            people_before = {k: list(v) for k, v in w.politics.get("story_people", {}).items()}
            adv = forge.build()
        except ForgeFailed as why:
            import logging

            logging.getLogger(__name__).info("Could not forge %s on %s: %s", bid, threat["id"], why)
            w.politics["story_sites"] = sites_before  # (nothing of a failed forging stays behind)
            w.politics["story_people"] = people_before
            continue
        w.politics["next_adventure"] = n + 1
        records(w)[aid] = adv
        threat["adventure"] = aid
        threat["offer"] = None
        return adv
    return None
