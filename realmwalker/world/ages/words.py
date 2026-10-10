"""Words for the ages: the text of events, and the names of wars, battles, beasts, artifacts, works and eras.

Every pattern lives in data/history.json ("text" for events, "names" for names, "words" for the parts they are
filled from); the events the live politics engine also tells (succession, war, plague...) fall back to
data/politics.json "text", so the two always speak with one voice.
"""

from __future__ import annotations

import re

from realmwalker.core import textgen

ORDINALS = ["", "", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth"]
_SLOT = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI",
         "XVII", "XVIII", "XIX", "XX"]


def roman(n: int) -> str:
    return ROMAN[n] if 0 < n < len(ROMAN) else str(n)


def cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


class Words:
    def __init__(self, sim) -> None:
        self.s = sim
        self.names = sim.data["names"]
        self.words = sim.data["words"]
        self.templates = {**sim.t.politics["text"], **sim.data["text"]}
        self.used: set[str] = set()
        self.battles_at: dict[str, int] = {}

    # ------------------------------------------------------------------ event text
    def text(self, kind: str, values: dict) -> str:
        options = self.templates.get(kind)
        if not options:
            return kind.replace("_", " ")
        words = {k: str(v) for k, v in values.items()}
        return textgen.fill(self.s.r.choice(options), self.s.r, self.words, words)

    def fill(self, pattern: str, **values) -> str:
        """A name from a pattern: slots from `values`, else a word from data/history.json "words". Names keep
        their case ("the Siege of Ashford" is written mid-sentence; the sentence capitalises it when it leads)."""
        r = self.s.r

        def sub(m: re.Match) -> str:
            key = m.group(1)
            if key in values:
                return str(values[key])
            options = self.words.get(key)
            return r.choice(options) if options else m.group(0)

        return _SLOT.sub(sub, pattern).strip()

    def unique(self, patterns: list[str], **values) -> str:
        """A name nobody has used yet; if every pattern is taken, the second (third...) of the first one."""
        first = ""
        for i in range(12):
            name = self.fill(self.s.r.choice(patterns), **values)
            first = first or name
            if name not in self.used:
                self.used.add(name)
                return name
        for n in range(2, len(ORDINALS)):
            name = ordinal_name(first, n)
            if name not in self.used:
                self.used.add(name)
                return name
        return first

    # ------------------------------------------------------------------ names
    def war_name(self, reason: str, attacker, defender, place: str) -> str:
        patterns = self.names["war"].get(reason) or self.names["war"]["default"]
        short_a = short_name(attacker.name)
        short_d = short_name(defender.name)
        return self.unique(patterns + self.names["war"]["default"][:2], attacker=short_a, defender=short_d, place=place,
                           house=short_a)

    def battle_name(self, place: str, kind: str = "battle") -> str:
        patterns = self.names["battle"].get(kind) or self.names["battle"]["battle"]
        name = self.fill(self.s.r.choice(patterns), place=place)
        n = self.battles_at.get(name, 0) + 1
        self.battles_at[name] = n
        return ordinal_name(name, n) if 1 < n < len(ORDINALS) else name

    def peace_name(self, place: str) -> str:
        return self.unique(self.names["peace"], place=place)

    def beast_name(self, btype: str) -> tuple[str, str]:
        spec = self.s.data["beasts"][btype]
        for _ in range(12):
            name = self.fill(self.s.r.choice(spec["names"]))
            if name not in self.used:
                break
        self.used.add(name)
        epithet = self.fill(self.s.r.choice(spec["epithets"])) if spec.get("epithets") else ""
        return name, epithet

    def artifact_name(self, kind: str, culture: str, maker_name: str = "") -> str:
        a = self.s.data["artifacts"]
        word = a["kinds"][kind]["word"]
        kennings = a["kennings"].get(kind) or a["kennings"]["_any"]
        patterns = [f"the {word} of {{of}}", "{kenning}", f"the {{adj}} {word}"]
        for _ in range(12):
            pattern = self.s.r.choice(patterns)
            name = self.fill(pattern, of=self.s.r.choice(a["of"]), kenning=self.s.r.choice(kennings),
                             adj=self.s.r.choice(a["adjectives"]))
            if name not in self.used:
                break
        self.used.add(name)
        return name

    def work_title(self, form: str, **values) -> str:
        return self.unique(self.s.data["works"]["forms"][form]["titles"], **values)

    def era_name(self, theme: str, **values) -> str:
        if "realm" in values:
            values["realm"] = short_name(values["realm"])
        return self.unique(self.s.data["eras"]["themes"][theme]["names"], **values)


def ordinal_name(name: str, n: int) -> str:
    """'the Battle of Ashford' -> 'the Second Battle of Ashford'."""
    word = ORDINALS[n] if n < len(ORDINALS) else f"{n}th"
    if name.lower().startswith("the "):
        return f"{name[:4]}{word} {name[4:]}"
    return f"the {word} {name}"


def short_name(faction_name: str) -> str:
    """'the Kingdom of Ashmere' -> 'Ashmere'; 'House Draycott' -> 'Draycott'; others as they are."""
    name = faction_name
    for prefix in ("the Kingdom of ", "the Crown of ", "the Free City of ", "the Realm of ", "the Elven Realm of ",
                   "House ", "Clan ", "the Clan of ", "the "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name
