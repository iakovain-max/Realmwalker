"""Character creation: the choices a player makes, checked against the rules, turned into a Character.

Every choice has a sensible default, so a character can be made by accepting everything
(the autoplay bot relies on this). Social ties are tied to real places in the world.
"""

from __future__ import annotations

import math

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.rules import looks
from realmwalker.rules.character import ABILITIES, Character, modifier
from realmwalker.rules.inventory import add_item, equip_everything_sensible, fill_containers

SEXES = ("male", "female")
# Default skill picks, most generally useful first.
SKILL_PREFERENCE = ["perception", "stealth", "survival", "medicine", "arcana", "insight", "athletics", "investigation",
                    "sleight_of_hand", "persuasion", "acrobatics", "history", "religion", "intimidation", "deception"]
PRONOUNS = {"male": ("he", "him", "his"), "female": ("she", "her", "her")}


class CharacterBuilder:
    def __init__(self, tables, rng: RNG, world=None) -> None:
        self.t = tables
        self.rng = rng
        self.world = world  # names come from this world's forge when there is one
        self.race = "human"
        self.culture = "heartland"
        self.cls = "fighter"
        self.background = "soldier"
        self.scores: dict[str, int] = dict(tables.classes[self.cls]["suggested"])
        self.class_skills: list[str] = []
        self.expertise: list[str] = []
        self.fighting_style: str | None = None
        self.style_chosen = False  # the player picked the fighting style by hand
        self.subclass: str | None = None
        self.kit = 0
        self.sex = "male"
        self.name = ""
        self.age = 25
        self.appearance = ""
        self.looks: dict = {}  # rules/looks.py; the appearance words are written from these
        self.backstory = ""
        self.personality = self.ideal = self.bond = self.flaw = ""
        self.start_settlement: int | None = None
        self.lineage: str | None = None  # an elf's drow, high or wood
        self.choices: dict = {}  # species choices: Skillful's skill, Keen Senses' skill
        self.versatile: str = "skilled"  # a human's origin feat
        self.feat_choices: dict[str, dict] = {}  # by source ("background", "versatile"): the feat's own picks
        self.bonus_mode = "2/1"  # the background's increases: "2/1" (+2 and +1) or "1/1/1"
        self.bonus_pick: list[str] = []  # for "2/1": [the +2, the +1]
        self.take_gold = False  # the background's option B (50 gp) instead of its equipment
        self.score_method = "point_buy"  # point_buy, array (15, 14, 13, 12, 10, 8) or roll (4d6, lowest dropped)
        self.languages: list[str] = []  # the two standard languages chosen (Common is everyone's)
        self.open_pools: set[str] = set()  # skill picks the player emptied by hand: left empty, not filled again
        self.set_class("fighter")
        self.set_race("human")
        self.randomize_identity()

    # ------------------------------------------------------------------ choices
    def set_race(self, race: str) -> None:
        self.race = race
        cultures = self.t.races[race]["cultures"]
        if self.culture not in cultures:
            self.culture = cultures[0]
        lineages = list(self.t.races[race].get("lineages") or {})
        self.lineage = lineages[0] if lineages else None
        self.choices = {}
        self.open_pools.clear()
        self._fix_species_choices()
        self.languages = []
        self._fix_languages()
        self.randomize_identity(keep_sex=True)
        self._fix_skills()

    # ------------------------------------------------------------------ species choices (2024)
    def species_choices(self) -> dict:
        return dict(self.t.races[self.race].get("choices") or {})

    def choice_options(self, key: str) -> list[str]:
        """What one species choice may be: a skill (not already had), an origin feat, a lineage."""
        spec = self.species_choices().get(key, {})
        kind = spec.get("kind")
        if kind == "skill":
            have = set(self.t.backgrounds[self.background]["skills"]) | set(self.class_skills) | set(self._feat_picks())
            pool = spec.get("from") or list(self.t.rules["skills"])
            return [s for s in pool if s not in have or s == self.choices.get(key)]
        if kind == "origin_feat":
            from realmwalker.rules import feats

            bg = self.t.backgrounds[self.background]["feat"]["id"]
            return [f for f in feats.origin_feats(self.t) if f != bg or feats.defs(self.t)[f].get("repeatable")]
        if kind == "lineage":
            return list(self.t.races[self.race].get("lineages") or {})
        return []

    def set_choice(self, key: str, value: str) -> None:
        if key == "lineage":
            self.lineage = value
        elif key == "versatile":
            self.versatile = value
            self.open_pools = {p for p in self.open_pools if not p.startswith("feat:versatile:")}
        else:
            self.choices[key] = value
        self._fix_skills()

    def _fix_species_choices(self) -> None:
        for key, spec in self.species_choices().items():
            opts = self.choice_options(key)
            if spec["kind"] == "skill" and self.choices.get(key) not in opts:
                if f"species:{key}" in self.open_pools:
                    self.choices[key] = ""  # (emptied by hand: the player picks it on the Skills step)
                else:
                    self.choices[key] = next((s for s in SKILL_PREFERENCE if s in opts), opts[0] if opts else "")
        for key in [k for k in self.choices if k not in self.species_choices()]:
            del self.choices[key]

    # ------------------------------------------------------------------ the background's increases (2024)
    def bg_abilities(self) -> list[str]:
        return list(self.t.backgrounds[self.background]["abilities"])

    def _fix_bonus(self) -> None:
        abil = self.bg_abilities()
        primary = self.t.classes[self.cls]["primary"]
        ranked = sorted(abil, key=lambda a: (primary.index(a) if a in primary else 9, -self.scores.get(a, 10)))
        if len(self.bonus_pick) != 2 or any(a not in abil for a in self.bonus_pick) or self.bonus_pick[0] == self.bonus_pick[1]:
            self.bonus_pick = ranked[:2]

    def bonus(self) -> dict[str, int]:
        """What the background adds to each ability."""
        if self.bonus_mode == "1/1/1":
            return {a: 1 for a in self.bg_abilities()}
        self._fix_bonus()
        return {self.bonus_pick[0]: 2, self.bonus_pick[1]: 1}

    def set_bonus(self, mode: str, pick: list[str] | None = None) -> None:
        self.bonus_mode = mode if mode in ("2/1", "1/1/1") else "2/1"
        if pick is not None:
            self.bonus_pick = list(pick)
        self._fix_bonus()

    # ------------------------------------------------------------------ languages (2024: Common and two more)
    def language_options(self) -> list[str]:
        return list(self.t.rules["language_lists"]["standard"])

    def _fix_languages(self) -> None:
        lists = self.t.rules["language_lists"]
        opts = self.language_options()
        keep = [x for x in self.languages if x in opts][:2]
        liked = lists["by_species"].get(self.race, []) + lists["by_culture"].get(self.culture, []) + opts
        for x in liked:
            if len(keep) >= 2:
                break
            if x not in keep and x in opts:
                keep.append(x)
        self.languages = keep

    def set_language(self, slot: int, value: str) -> None:
        if value in self.language_options() and value not in self.languages:
            self._fix_languages()
            self.languages[slot] = value

    # ------------------------------------------------------------------ feats from the origin
    def _proto(self):
        """What a feat's choices look at, before the character is made: their skills, tools, class, scores."""
        from types import SimpleNamespace

        bg = self.t.backgrounds[self.background]
        return SimpleNamespace(skills=self.all_skills(), tools=list(self.t.classes[self.cls]["tools"]) + list(bg["tools"]),
                               cls=self.cls, abilities=self.final_scores(), species=self.race, lineage=self.lineage,
                               choices=self.choices, feats=[], level=1)

    def _fix_feats(self) -> None:
        """Every origin feat's choices made (the defaults for what is missing or no longer possible)."""
        from realmwalker.rules import feats

        if "versatile" in self.species_choices() and self.versatile not in self.choice_options("versatile"):
            self.versatile = next(iter(self.choice_options("versatile")), "skilled")
        proto = self._proto()
        fixed_now = {}
        lists_used: list[str] = []
        for source, fid, fixed in self.origin_feats():
            fixed = dict(fixed)
            if fid == "magic_initiate" and lists_used and "list" not in fixed:
                # (taken again: another list; the first copy's spells are not offered twice)
                have_list = (self.feat_choices.get(source) or {}).get("list")
                if have_list in lists_used or have_list is None:
                    fixed["list"] = next(x for x in ("cleric", "druid", "wizard") if x not in lists_used)
            have = dict(self.feat_choices.get(source) or {})
            if have.get("_feat") != fid:
                have = {}
            spec = feats.defs(self.t)[fid].get("choices", {})
            clean = dict(fixed)
            partial: dict[str, list] = {}  # picks still good, topped up with defaults below
            for key, c in spec.items():
                if key in fixed or key not in have:
                    continue
                opts = feats.options(self.t, proto, fid, key, {**clean, **have})
                v = have[key]
                n = int(c.get("count", 1))
                if isinstance(v, list):
                    v = [x for x in v if x in opts][:n]
                    if len(v) == n or f"feat:{source}:{key}" in self.open_pools:
                        clean[key] = v  # (one the player emptied by hand stays short until they pick again)
                    elif v:
                        partial[key] = v
                elif v in opts:
                    clean[key] = v
            fixed_now[source] = {**feats.default_choices(self.t, proto, fid, clean), "_feat": fid}
            picked = fixed_now[source]
            for key, kept in partial.items():
                n = int(spec[key].get("count", 1))
                picked[key] = (kept + [x for x in picked.get(key) or [] if x not in kept])[:n]
            if picked.get("list"):
                lists_used.append(picked["list"])
            for x in picked.get("skills", []) + picked.get("tools", []):  # (a second Skilled picks others)
                (proto.skills if x in self.t.rules["skills"] else proto.tools).append(x)
        self.feat_choices = fixed_now

    def feat_slots(self) -> list[tuple[str, str, str, int, list[str]]]:
        """(source, feat id, choice key, index, options) for each pick an origin feat leaves to the player."""
        from realmwalker.rules import feats

        self._fix_feats()
        proto = self._proto()
        out = []
        for source, fid, fixed in self.origin_feats():
            ch = self.feat_choices[source]
            if fid == "magic_initiate" and source != "background":
                fixed = {**fixed, "list": ch.get("list")}  # (its list differs from the background's: fixed here)
            for key, c in feats.defs(self.t)[fid].get("choices", {}).items():
                if key in fixed:
                    continue
                opts = feats.options(self.t, proto, fid, key, ch)
                n = int(c.get("count", 1))
                if c["kind"] in ("cantrip", "spell", "skill_or_tool", "tool"):
                    for i in range(n):
                        out.append((source, fid, key, i, opts))
                else:
                    out.append((source, fid, key, -1, opts))
        return out

    def set_feat_slot(self, source: str, key: str, index: int, value: str) -> None:
        self._fix_feats()
        ch = self.feat_choices[source]
        if index < 0:
            ch[key] = value
            for k in [k for k in list(ch) if k not in (key, "_feat") and isinstance(ch[k], list)]:
                if key == "list":
                    del ch[k]  # (another list: other spells)
        else:
            picks = list(ch.get(key) or [])
            if value in picks:
                picks[picks.index(value)] = picks[index]  # swapped with the slot that had it
            while len(picks) <= index:
                picks.append(value)
            picks[index] = value
            ch[key] = picks
        self._fix_feats()

    def origin_feats(self) -> list[tuple[str, str, dict]]:
        """(source, feat id, fixed choices) of the feats this origin gives: the background's, a human's Versatile."""
        bg = self.t.backgrounds[self.background]["feat"]
        out = [("background", bg["id"], dict(bg.get("choices") or {}))]
        if "versatile" in self.species_choices():
            out.append(("versatile", self.versatile, {}))
        return out

    def set_culture(self, culture: str) -> None:
        if culture in self.t.races[self.race]["cultures"]:
            self.culture = culture
            self.randomize_identity(keep_sex=True)

    def set_kit(self, kit: int) -> None:
        """Choose the equipment; until a fighting style has been picked by hand, the one that suits it goes with it
        (Defence with mail and a shield, Archery with a longbow)."""
        c = self.t.classes[self.cls]
        self.kit = max(0, min(kit, len(c["kits"]) - 1))
        style = c["kits"][self.kit].get("style")
        if self.fighting_style is not None and not self.style_chosen and style in self.styles():
            self.fighting_style = style

    def styles(self) -> list[str]:
        """The Fighting Style feats a fighter may start with."""
        from realmwalker.rules import feats

        return feats.styles(self.t)

    def set_class(self, cls: str) -> None:
        self.cls = cls
        c = self.t.classes[cls]
        kept = list(self.scores.values()) if getattr(self, "score_method", "point_buy") != "point_buy" else None
        self.scores = dict(c["suggested"])
        if kept:
            self._place(kept)  # (the array or the rolled scores, moved to what the new calling needs)
        self.kit = 0
        self.fighting_style = self.styles()[0] if "fighting_style" in c["choices_at_1"] else None
        self.style_chosen = False
        self.set_kit(0)
        subs = list(c.get("subclasses", {}))
        self.subclass = subs[0] if "subclass" in c["choices_at_1"] and subs else None
        self.class_skills = []
        self.expertise = []
        self.open_pools.clear()
        self._fix_skills()

    def set_background(self, bg: str) -> None:
        self.background = bg
        self.start_settlement = None
        self.feat_choices.pop("background", None)
        self.open_pools.clear()
        self._fix_bonus()
        self._fix_skills()

    def fixed_skills(self) -> list[str]:
        """Skills granted by species and background (not chosen as class skills)."""
        species = [v for k, v in self.choices.items() if v in self.t.rules["skills"]]
        return list(dict.fromkeys(self.t.races[self.race]["skills"] + self.t.backgrounds[self.background]["skills"]
                                  + species))

    def skill_options(self) -> list[str]:
        fixed = set(self.fixed_skills()) | set(self._feat_picks())
        return [s for s in self.t.classes[self.cls]["skill_choices"] if s not in fixed]

    # ------------------------------------------------------------------ every skill and tool pick in one place
    SKILL_KINDS = ("skill", "skill_or_tool", "tool")

    def _feat_picks(self) -> list[str]:
        """The skills and tools the origin feats' picks hold now (Skilled, Crafter, Musician), as they stand."""
        from realmwalker.rules import feats

        out = []
        for source, ch in self.feat_choices.items():
            spec = feats.defs(self.t).get(ch.get("_feat", ""), {}).get("choices", {})
            for key, c in spec.items():
                if c["kind"] in self.SKILL_KINDS:
                    v = ch.get(key) or []
                    out += v if isinstance(v, list) else [v]
        return [x for x in out if x]

    def known_skills(self) -> list[str]:
        """Every skill they will have: people, background, calling and the origin feats' picks."""
        return list(dict.fromkeys(self.all_skills() + [x for x in self._feat_picks() if x in self.t.rules["skills"]]))

    def known_tools(self) -> list[str]:
        bg = self.t.backgrounds[self.background]
        return list(dict.fromkeys(list(self.t.classes[self.cls]["tools"]) + list(bg["tools"])
                                  + [x for x in self._feat_picks() if x not in self.t.rules["skills"]]))

    def skill_pools(self) -> list[dict]:
        """Every pick of a skill or tool at first level, in one list: {id, name, count, picked, allowed, kind}. The
        calling's skills, the people's (Skillful, Keen Senses) and the origin feats' (Skilled, Crafter, Musician)."""
        from realmwalker.rules import feats

        self._fix_feats()
        t = self.t
        skills = list(t.rules["skills"])
        pools = [{"id": "class", "name": f"{t.classes[self.cls]['name']} skills", "count": self.skill_count(),
                  "picked": list(self.class_skills), "allowed": list(t.classes[self.cls]["skill_choices"]),
                  "kind": "skill", "from": "your calling"}]
        for key, spec in self.species_choices().items():
            if spec.get("kind") != "skill":
                continue
            trait = next((x for x in t.races[self.race]["traits"] if x["id"] == key), {})
            v = self.choices.get(key)
            pools.append({"id": f"species:{key}", "name": trait.get("name", key), "count": 1,
                          "picked": [v] if v else [], "allowed": list(spec.get("from") or skills), "kind": "skill",
                          "from": f"your people ({t.races[self.race]['name']})"})
        named = [fid for _, fid, _ in self.origin_feats()]
        for source, fid, fixed in self.origin_feats():
            d = feats.defs(t)[fid]
            for key, c in d.get("choices", {}).items():
                if key in fixed or c["kind"] not in self.SKILL_KINDS:
                    continue
                if c["kind"] == "tool":
                    allowed = list(feats.TOOL_GROUPS[c["from"]])
                elif c["kind"] == "skill":
                    allowed = skills
                else:
                    allowed = skills + [x for g in ("artisan", "instrument", "other") for x in feats.TOOL_GROUPS[g]]
                v = self.feat_choices.get(source, {}).get(key) or []
                where = "your background" if source == "background" else "Versatile, a human's"
                pools.append({"id": f"feat:{source}:{key}",
                              "name": d["name"] + (f" ({'background' if source == 'background' else 'Versatile'})"
                                                   if named.count(fid) > 1 else ""),
                              "count": int(c.get("count", 1)), "picked": list(v if isinstance(v, list) else [v]),
                              "allowed": allowed, "kind": c["kind"], "from": f"the {d['name']} feat ({where})"})
        return pools

    def granted(self) -> dict[str, str]:
        """Skills and tools that come with the origin and calling and are not picked: {id: where from}."""
        t = self.t
        out = {s: f"your people ({t.races[self.race]['name']})" for s in t.races[self.race]["skills"]}
        bg = t.backgrounds[self.background]
        for s in list(bg["skills"]) + list(bg["tools"]):
            out[s] = f"your background ({bg['name']})"
        for s in t.classes[self.cls]["tools"]:
            out.setdefault(s, f"your calling ({t.classes[self.cls]['name']})")
        return out

    def _put(self, pool: dict, x: str) -> None:
        pid = pool["id"]
        if pid == "class":
            self.class_skills.append(x)
        elif pid.startswith("species:"):
            self.choices[pid[8:]] = x
        else:
            _, source, key = pid.split(":")
            ch = self.feat_choices[source]
            ch[key] = [v for v in (ch.get(key) or []) if v] + [x]
        pool["picked"].append(x)
        if len(pool["picked"]) >= pool["count"]:
            self.open_pools.discard(pid)

    def _take(self, pool: dict, x: str) -> None:
        pid = pool["id"]
        if pid == "class":
            self.class_skills.remove(x)
        elif pid.startswith("species:"):
            self.choices[pid[8:]] = ""
        else:
            _, source, key = pid.split(":")
            ch = self.feat_choices[source]
            ch[key] = [v for v in (ch.get(key) or []) if v != x]
        pool["picked"].remove(x)
        self.open_pools.add(pid)
        if x in self.expertise:
            self.expertise.remove(x)
            self.open_pools.add("expertise")

    def pick(self, x: str) -> str:
        """Tick a skill or tool: it goes to the first pick with room that may take it (the narrowest first), moving
        one already chosen to another pick when that makes room. Returns '' or why it could not be done."""
        name = self.t.rules["skills"][x]["name"] if x in self.t.rules["skills"] else self.t.rules["tools"].get(x, x)
        if x in self.known_skills() or x in self.known_tools():
            return f"You already have {name}."
        pools = self.skill_pools()
        takes = sorted((p for p in pools if x in p["allowed"]), key=lambda p: len(p["allowed"]))
        if not takes:
            return f"None of your picks can be {name}."
        for p in takes:
            if len(p["picked"]) < p["count"]:
                self._put(p, x)
                return ""
        for p in takes:  # make room: something already chosen moves to a pick that still has room
            for y in list(p["picked"]):
                q = next((q for q in pools if q is not p and len(q["picked"]) < q["count"] and y in q["allowed"]), None)
                if q is not None:
                    self._take(p, y)
                    self._put(q, y)
                    self._put(p, x)
                    return ""
        return (f"{name} could be one of: {', '.join(p['name'] for p in takes)}, and they are all chosen. "
                "Untick one first.")

    def unpick(self, x: str) -> str:
        """Untick a skill or tool. Returns '' or why it cannot be (it comes with the origin)."""
        for p in self.skill_pools():
            if x in p["picked"]:
                self._take(p, x)
                return ""
        where = self.granted().get(x)
        return f"That comes from {where}; it cannot be unticked." if where else ""

    def picks_left(self) -> int:
        return sum(max(0, p["count"] - len(p["picked"])) for p in self.skill_pools())

    def skill_count(self) -> int:
        return self.t.classes[self.cls]["skill_count"]

    def toggle_skill(self, skill: str) -> bool:
        if skill in self.class_skills:
            self.class_skills.remove(skill)
            self.open_pools.add("class")
            if skill in self.expertise:
                self.expertise.remove(skill)
                self.open_pools.add("expertise")
            return True
        if skill in self.skill_options() and len(self.class_skills) < self.skill_count():
            self.class_skills.append(skill)
            return True
        return False

    def all_skills(self) -> list[str]:
        return list(dict.fromkeys(self.fixed_skills() + self.class_skills))

    def needs_expertise(self) -> int:
        return 2 if "expertise" in self.t.classes[self.cls]["choices_at_1"] else 0

    def toggle_expertise(self, skill: str) -> bool:
        if skill in self.expertise:
            self.expertise.remove(skill)
            self.open_pools.add("expertise")
            return True
        if skill in self.known_skills() and len(self.expertise) < self.needs_expertise():
            self.expertise.append(skill)
            if len(self.expertise) >= self.needs_expertise():
                self.open_pools.discard("expertise")
            return True
        return False

    def _fix_skills(self) -> None:
        """Keep chosen skills valid and fill any missing picks with sensible defaults."""
        if hasattr(self, "choices"):
            self._fix_species_choices()
        options = self.skill_options()
        self.class_skills = [s for s in self.class_skills if s in options][: self.skill_count()]
        for s in [p for p in SKILL_PREFERENCE if p in options] + options:
            if len(self.class_skills) >= self.skill_count() or "class" in self.open_pools:
                break
            if s not in self.class_skills:
                self.class_skills.append(s)
        for key, spec in self.species_choices().items():  # (Keen Senses had all its skills taken by the calling:
            allowed = spec.get("from") or []               # it takes one, and the calling picks another)
            if spec.get("kind") == "skill" and not self.choices.get(key) and f"species:{key}" not in self.open_pools \
                    and "class" not in self.open_pools:
                s = next((s for s in self.class_skills if s in allowed), None)
                if s is not None:
                    self.class_skills.remove(s)
                    self.choices[key] = s
                    options = self.skill_options()
                    more = dict.fromkeys([p for p in SKILL_PREFERENCE if p in options] + options)
                    self.class_skills += [x for x in more if x not in self.class_skills][
                        : self.skill_count() - len(self.class_skills)]
        known = self.known_skills()
        self.expertise =[s for s in self.expertise if s in known][: self.needs_expertise()]
        preferred = ["stealth", "perception", "sleight_of_hand", "deception", "acrobatics", "investigation"]
        for s in preferred + known:
            if len(self.expertise) >= self.needs_expertise() or "expertise" in self.open_pools:
                break
            if s in known and s not in self.expertise:
                self.expertise.append(s)

    # ------------------------------------------------------------------ ability scores
    @property
    def point_buy(self) -> dict:
        return self.t.rules["point_buy"]

    def points_spent(self) -> int:
        costs = self.point_buy["costs"]
        return sum(costs[str(v)] for v in self.scores.values())

    def points_left(self) -> int:
        return self.point_buy["budget"] - self.points_spent()

    def can_change(self, ability: str, delta: int) -> bool:
        pb = self.point_buy
        if getattr(self, "score_method", "point_buy") != "point_buy":
            return False  # (an array or rolled scores are swapped, not bought: a right-click there does nothing)
        new = self.scores[ability] + delta
        if new < pb["min"] or new > pb["max"]:
            return False
        costs = pb["costs"]
        extra = costs[str(new)] - costs[str(self.scores[ability])]
        return self.points_left() - extra >= 0

    def change(self, ability: str, delta: int) -> bool:
        if self.can_change(ability, delta):
            self.scores[ability] += delta
            return True
        return False

    def final_scores(self) -> dict[str, int]:
        bonus = self.bonus()
        return {a: min(20, self.scores[a] + int(bonus.get(a, 0))) for a in ABILITIES}

    def max_hp(self) -> int:
        con = modifier(self.final_scores()["con"])
        tough = 2 if any(fid == "tough" for _, fid, _ in self.origin_feats()) else 0
        return max(1, self.t.classes[self.cls]["hit_die"] + con + int(self.t.races[self.race].get("hp_per_level", 0))) \
            + tough

    # ------------------------------------------------------------------ the ways of making ability scores (2024)
    STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)

    def set_method(self, method: str) -> None:
        """Point buy (27 points), the standard array (15, 14, 13, 12, 10, 8, placed by the class's needs), or rolling
        4d6 and keeping the three highest, six times (placed the same way)."""
        self.score_method = method if method in ("point_buy", "array", "roll") else "point_buy"
        if self.score_method == "point_buy":
            self.scores = dict(self.t.classes[self.cls]["suggested"])
        elif self.score_method == "array":
            self._place(list(self.STANDARD_ARRAY))
        else:
            self.reroll()
        self._fix_bonus()

    def reroll(self) -> list[int]:
        """Roll 4d6 six times, keep the three highest of each."""
        rolls = []
        for _ in range(6):
            dice4 = sorted(self.rng.randint(1, 6) for _ in range(4))
            rolls.append(sum(dice4[1:]))
        self.score_method = "roll"
        self._place(sorted(rolls, reverse=True))
        return rolls

    def _place(self, values: list[int]) -> None:
        """Highest first into what the class needs most (its suggested scores' order)."""
        sug = self.t.classes[self.cls]["suggested"]
        order = sorted(ABILITIES, key=lambda a: -sug[a])
        values = sorted(values, reverse=True)
        self.scores = {a: values[i] for i, a in enumerate(order)}

    def swap_scores(self, a: str, b: str) -> None:
        """Array and rolled scores are moved by swapping two of them."""
        self.scores[a], self.scores[b] = self.scores[b], self.scores[a]

    # ------------------------------------------------------------------ identity
    def random_name(self) -> str:
        if self.world is not None:
            from realmwalker.world.names import forge

            return forge(self.world, self.t).person(self.culture, self.sex, self.rng)
        culture = self.t.names["cultures"].get(self.culture) or next(iter(self.t.names["cultures"].values()))
        return f"{self.rng.choice(culture[self.sex])} {self.rng.choice(culture['family'])}"

    def culture_label(self) -> str:
        return self.t.cultures.adjective(self.world, self.culture)

    def random_age(self) -> int:
        age = self.t.races[self.race]["age"]
        lo = age["adult"]
        hi = max(lo + 1, int(lo + (age["old"] - lo) * 0.5))
        return self.rng.randint(lo, hi)

    def random_appearance(self) -> str:
        """New looks, at random for this people, sex and age; returns the words for them."""
        self.randomize_looks()
        return self.appearance

    def randomize_looks(self) -> None:
        self.looks = looks.random_looks(self.t, self.race, self.sex, self.age, self.rng)
        self.appearance = looks.describe(self.t, self.looks, self.race, self.sex)

    def set_look(self, slot: str, value: str) -> None:
        """One look chosen (slot: build, skin, eyes, hair, hair_colour, beard, beard_colour, mark, paint, paint_colour,
        dye, cloak, or feature:<name>); the words that describe the character are written again."""
        new = dict(self.looks)
        if slot.startswith("feature:"):
            new["features"] = {**(new.get("features") or {}), slot[8:]: value}
        else:
            if slot == "hair_colour" and new.get("beard_colour") == new.get("hair_colour"):
                new["beard_colour"] = value  # a beard follows the hair unless chosen apart
            new[slot] = value
        self.looks = looks.normalise(self.t, new, self.race, self.sex, self.name)
        self.appearance = looks.describe(self.t, self.looks, self.race, self.sex)

    def fit_looks(self) -> None:
        """Keep the looks that still suit after a change of sex (a beard may go), and say them again."""
        self.looks = looks.normalise(self.t, self.looks, self.race, self.sex, self.name)
        self.appearance = looks.describe(self.t, self.looks, self.race, self.sex)

    def randomize_identity(self, keep_sex: bool = False) -> None:
        if not keep_sex:
            self.sex = self.rng.choice(list(SEXES))
        self.name = self.random_name()
        self.age = self.random_age()
        self.randomize_looks()
        self.backstory = ""

    def fallback_backstory(self, home_name: str) -> dict:
        """A backstory from the built-in words (data/appearance.json backstory)."""
        a = self.t.appearance
        bg = self.t.backgrounds[self.background]
        he, him, his = PRONOUNS[self.sex]
        culture = self.culture_label()
        values = {
            "name": self.name.split()[0], "home": home_name, "years": str(self.age), "culture": culture,
            "season": self.rng.choice(["winter", "spring", "summer", "autumn"]),
            "nth": self.rng.choice(["second", "third", "fourth", "youngest", "eldest"]),
            "pronoun": he, "pronoun_cap": he.capitalize(), "object": him, "possessive": his,
            "coin": "a few coins",
        }
        lines = a["background_lines"].get(self.background) or ["{name} learned a trade, and then left it."]
        values["background_line"] = textgen.fill(self.rng.choice(lines), self.rng, {}, values)
        tables = a["backstory"]
        parts = [textgen.fill(self.rng.choice(tables[k]), self.rng, tables, values) for k in ("opening", "middle", "closing")]
        return {
            "backstory": " ".join(parts),
            "personality": self.rng.choice(bg["personality"]),
            "ideal": self.rng.choice(bg["ideal"]),
            "bond": self.rng.choice(bg["bond"]),
            "flaw": self.rng.choice(bg["flaw"]),
        }

    def apply_backstory(self, data: dict) -> None:
        self.backstory = data.get("backstory", "")
        self.personality = data.get("personality", "")
        self.ideal = data.get("ideal", "")
        self.bond = data.get("bond", "")
        self.flaw = data.get("flaw", "")

    # ------------------------------------------------------------------ checks and build
    def problems(self) -> list[str]:
        out = []
        if self.score_method == "point_buy" and self.points_left() < 0:
            out.append("You have spent more ability points than you have.")
        for p in self.skill_pools():
            if len(p["picked"]) < p["count"]:
                n = p["count"] - len(p["picked"])
                what = {"skill": "skill", "tool": "tool", "skill_or_tool": "skill or tool"}[p["kind"]]
                out.append(f"Choose {n} more {what}{'s' if n > 1 else ''} for {p['name']} (step 6, Skills & tools).")
        if len(self.expertise) != self.needs_expertise():
            out.append(f"Choose {self.needs_expertise()} skills for Expertise (step 6, Skills & tools).")
        if not self.name.strip():
            out.append("Your character needs a name.")
        return out

    def build(self, world_time: int = 0) -> Character:
        t = self.t
        race, cls, bg = t.races[self.race], t.classes[self.cls], t.backgrounds[self.background]
        abilities = self.final_scores()
        armor = list(cls["armor"])
        weapons = list(cls["weapons"])
        if self.subclass:
            sub = cls["subclasses"][self.subclass]
            armor += sub.get("armor", [])
            weapons += sub.get("weapons", [])
        tools = list(dict.fromkeys(cls["tools"] + bg["tools"]))
        self._fix_languages()
        languages = ["Common"] + list(self.languages)
        if self.cls == "rogue":
            languages.append("Thieves' Cant")
        hp = self.max_hp()
        features = [f["id"] for f in cls["features"] if f["level"] <= 1]
        choose_at_1 = [f for f in cls["features"] if f["level"] <= 1 and f.get("choose")]  # (Divine Order)
        uses: dict = {}
        char = Character(
            name=self.name.strip(), sex=self.sex, age=self.age, species=self.race, culture=self.culture,
            cls=self.cls, background=self.background, base_scores=dict(self.scores), abilities=abilities,
            level=1, xp=0, subclass=self.subclass, max_hp=hp, hp=hp, hit_dice=1,
            skills=self.all_skills(), expertise=list(self.expertise), saves=list(cls["saves"]),
            armor_prof=list(dict.fromkeys(armor)), weapon_prof=list(dict.fromkeys(weapons)), tools=tools,
            languages=languages, features=features, uses=uses,
            money=int(bg["gold"] if self.take_gold else bg["money"]), appearance=self.appearance, looks=dict(self.looks),
            backstory=self.backstory, personality=self.personality, ideal=self.ideal, bond=self.bond, flaw=self.flaw,
            lineage=self.lineage, choices={k: v for k, v in self.choices.items()},
        )
        char.max_hp = char.hp = hp - (2 if any(fid == "tough" for _, fid, _ in self.origin_feats()) else 0)
        from realmwalker.rules import feats

        self._fix_feats()
        for source, fid, fixed in self.origin_feats():  # the background's feat, a human's Versatile
            picked = {k: v for k, v in self.feat_choices.get(source, {}).items() if k != "_feat"}
            feats.grant(char, t, fid, {**fixed, **picked})
        if self.fighting_style:
            feats.grant(char, t, self.fighting_style)  # the fighter's trained way of fighting (a feat, 2024)
        items = t.items
        kit = cls["kits"][max(0, min(self.kit, len(cls["kits"]) - 1))]
        for def_id, qty in t.items.starting_packs.get("everyone", []) + kit["items"] + ([] if self.take_gold else bg["items"]):
            add_item(char, items, def_id, int(qty), made_at=world_time)
        if "trinket" in items:  # everyone sets out with one keepsake (PHB 2024 Trinkets)
            from realmwalker.rules.items import make_trinket

            keep = make_trinket(t, self.rng.child("trinket"), now=world_time)
            add_item(char, items, "trinket", name=keep.name, tags=keep.tags, made_at=world_time)
        equip_everything_sensible(char, items)
        fill_containers(char, items, "clean")
        from realmwalker.rules.spells import init_spells

        init_spells(char, t)
        from realmwalker.rules.engine import resources

        resources.fill(char, t)  # Second Wind, an orc's Relentless Endurance, War Priest... start ready
        from realmwalker.rules import progression

        if progression.mastery_count(char, t):  # the kit's weapons first; changed on the character sheet before long
            char.masteries = progression.mastery_options(char, t)[:progression.mastery_count(char, t)]
            char.uses["mastery_change"] = 1
        for f in choose_at_1:  # (a cleric's Divine Order waits on the sheet: c, then l)
            progression.add_pending(char, {"kind": "option", "feature": f["id"], "level": 1})
        return char


# ---------------------------------------------------------------------------- places and ties
def starting_places(world, tables, background: str, race: str, rng: RNG, count: int = 4,
                    culture: str | None = None) -> list[int]:
    """A few settlements suited to a background, spread over the map (among the character's own people, where
    there are any)."""
    bg = tables.backgrounds[background]
    kinds = bg["start"]["kinds"]
    biomes = set(bg["start"].get("biomes", []))
    preferred_culture = {"elf": "elven", "dwarf": "dwarven", "halfling": "halfling"}.get(race)
    scored = []
    for s in world.settlements:
        score = 0.0
        if s.kind in kinds:
            score += 3
        elif s.kind in ("town", "village") or (race == "dwarf" and s.kind == "hold") or (race == "elf" and s.kind == "elfhall"):
            score += 1
        else:
            continue
        if biomes and world.biome_id(s.x, s.y) in biomes:
            score += 2
        if preferred_culture and s.culture == preferred_culture:
            score += 2
        if culture and s.culture == culture:
            score += 4
        if race == "dwarf" and s.kind == "hold" or race == "elf" and s.kind == "elfhall":
            score += 3
        score += rng.random()
        scored.append((score, s))
    scored.sort(key=lambda p: -p[0])
    chosen: list = []
    for _, s in scored:
        if all(math.hypot(s.x - o.x, s.y - o.y) > 12 for o in chosen):
            chosen.append(s)
        if len(chosen) >= count:
            break
    return [s.id for s in chosen]


def make_ties(world, tables, character: Character, start_id: int, rng: RNG) -> list[dict]:
    """Starting social ties: people and places that exist in this world."""
    bg = tables.backgrounds[character.background]
    words = tables.backgrounds_data["tie_words"]
    start = world.settlements[start_id]
    culture = tables.names["cultures"].get(start.culture) or tables.names["cultures"]["heartland"]
    from realmwalker.world.names import forge

    nf = forge(world, tables)

    def person(title_m: str = "", title_f: str = "") -> str:
        sex = rng.choice(["male", "female"])
        title = (title_m if sex == "male" else title_f)
        name = nf.person(start.culture, sex, rng)
        return f"{title} {name}" if title else name

    def nearby(kinds: tuple[str, ...], exclude: int | None = None) -> object:
        options = [s for s in world.settlements if s.kind in kinds and s.id != exclude]
        options.sort(key=lambda s: math.hypot(s.x - start.x, s.y - start.y))
        return rng.choice(options[:4]) if options else start

    from realmwalker.world import factions as fx

    tie = bg["tie"]
    values: dict[str, str] = {k: rng.choice(v) for k, v in words.items()}
    refs: dict = {}
    kind = tie["kind"]
    have_factions = bool(getattr(world, "factions", None))
    if kind == "lord_served":
        seat = nearby(("town", "city"))
        lord_faction = fx.owner_of(world, seat) if have_factions else None
        leader = fx.leader_of(world, lord_faction)
        if lord_faction is not None and leader is not None:
            house = lord_faction.name if lord_faction.kind == "noble_house" else                 f"House {lord_faction.flags.get('dynasty') or leader.name.split()[-1]}"
            values.update(lord=leader.full_name(), house=house, place=seat.name)
            deserted = "desert" in values.get("how", "")
            refs.update(faction=lord_faction.id, standing=-30 if deserted else 15)
        else:
            values.update(lord=person("Lord", "Lady"), house=f"House {rng.choice(culture['family'])}", place=seat.name)
        refs["place"] = seat.id
    elif kind == "temple":
        values.update(place=start.name, priest=person("Father", "Mother"))
        refs["place"] = start.id
        church = fx.church_of(world, fx.faith_for_culture(tables, start.culture)) if have_factions else None
        if church is not None:
            refs.update(faction=church.id, standing=25)
    elif kind == "criminal":
        other = nearby(("town", "city", "village"), exclude=start.id)
        bounty = rng.choice([15, 20, 25, 40, 50])
        values.update(contact=person(), place=start.name, bounty_place=other.name, bounty=f"{bounty} gold crowns")
        refs.update(place=start.id, bounty_place=other.id, bounty=bounty * 100, crime=values.get("crime", ""))
        if have_factions:
            realm = fx.realm_of_settlement(world, other)
            if realm is not None:
                refs["bounty_faction"] = realm.id
            thieves = [f for f in fx.active_factions(world, "thieves_guild") if start.id in f.presence]
            if thieves:
                refs.update(faction=thieves[0].id, standing=20)
    elif kind == "home_village":
        values.update(place=start.name, headman=person())
        refs["place"] = start.id
        lord_faction = fx.owner_of(world, start) if have_factions else None
        if lord_faction is not None:
            refs.update(faction=lord_faction.id, standing=10)
    elif kind == "noble_house":
        family = character.name.split()[-1]
        seat = nearby(("town", "city"))
        values.update(house=f"House {family}", place=seat.name, head=person().split()[0] + f" {family}")
        refs["place"] = seat.id
    elif kind == "scholar":
        city = nearby(("city", "town"))
        values.update(master=person("Master", "Mistress"), place=city.name)
        refs["place"] = city.id
        circles = fx.active_factions(world, "mages_circle") if have_factions else []
        if circles:
            refs.update(faction=circles[0].id, standing=15)
    elif kind == "clan":
        values.update(place=start.name, chief=person())
        refs["place"] = start.id
        clans = sorted(fx.active_factions(world, "highland_clan", "clan") if have_factions else [],
                       key=lambda f: math.hypot(world.settlements[f.seat].x - start.x, world.settlements[f.seat].y - start.y))
        if clans and math.hypot(world.settlements[clans[0].seat].x - start.x, world.settlements[clans[0].seat].y - start.y) < 40:
            clan = clans[0]
            leader = fx.leader_of(world, clan)
            name = clan.name[4:] if clan.name.lower().startswith("the ") else clan.name  # "born to the {clan}"
            values.update(clan=name, place=world.settlements[clan.seat].name,
                          chief=leader.full_name() if leader else person())
            refs.update(faction=clan.id, standing=30, place=clan.seat)
    elif kind == "guild":
        values.update(place=start.name, master=person())
        refs["place"] = start.id
        want = "smiths_guild" if "Smith" in values.get("guild", "") else "merchant_guild"
        guilds = fx.active_factions(world, want) if have_factions else []
        if guilds:
            refs.update(faction=guilds[0].id, standing=5)
    from realmwalker.world.ages.ties import enrich

    extra = enrich(world, tables, kind, character, start, values, refs, rng)  # the real past behind it, if any
    text = textgen.fill(tie["text"], rng, {}, values)
    if extra:
        text = f"{text} {extra}"
    return [{"kind": kind, "text": text, "names": {k: v for k, v in values.items() if k not in words}, "refs": refs}]
