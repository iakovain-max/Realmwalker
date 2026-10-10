"""Naming the ages: the years are divided into eras by what filled them (war, dragons, plague, founding, heroes, a
long peace under one great realm), the way Dwarf Fortress names its Age of Myth and Age of Legends.

A chronicler names a time by what set it apart from the others, so the years are measured against the world's own
usual. A few years at a time, each theme (war, dragons, beasts, plague, founding, heroes) is compared with how much of
it the whole history held: a theme names the stretch when it stands out (data/history.json "eras.stand_out" times
the usual) and is more than a trifle (at least "eras.least" of its "eras.thresholds" a year); a stretch whose troubles
all stayed under the usual ("eras.quiet") was a peace; anything else was the ordinary business of crowns, an age of
kings. Ordinary times and peaces are told apart by the realm that led them ("the Age of Ashmere", then "the Peace of
Redmarch"). Neighbouring stretches of one kind run together (up to a length a chronicler would still call one age),
and short eras are folded into their neighbours until there are a handful. A folded era is named again from
everything it holds, so a peace never hides a war.
"""

from __future__ import annotations

from collections import Counter

TROUBLES = ("war", "dragons", "beasts", "plague")
THEMES = TROUBLES + ("founding", "heroes")


def totals(sim, start: int, end: int) -> dict[str, float]:
    """How much of each theme the years from `start` up to `end` held."""
    total = dict.fromkeys(THEMES, 0.0)
    for y in range(start, end):
        st = sim.stats.get(y, {})
        total["war"] += st.get("battles", 0) + 2 * st.get("sieges", 0) + 3 * st.get("ruined", 0)
        total["dragons"] += st.get("dragon_attacks", 0)
        total["beasts"] += st.get("beast_attacks", 0) + 0.3 * st.get("raids", 0)
        total["plague"] += st.get("plague", 0) + 0.5 * st.get("famine", 0)
        total["founding"] += st.get("founded", 0)
        total["heroes"] += st.get("heroes", 0)
    return total


class Judge:
    """Says what kind of time a stretch of years was, against the usual of the whole history."""

    def __init__(self, sim) -> None:
        data = sim.data["eras"]
        self.sim = sim
        self.limits = {t: float(data["thresholds"][t]) for t in THEMES}
        self.stand_out = float(data.get("stand_out", 1.5))
        self.quiet = float(data.get("quiet", 0.8))
        self.least = float(data.get("least", 0.3))
        self.kings = "kings" in data["themes"]
        years = max(1, sim.present - sim.year0)
        whole = totals(sim, sim.year0, sim.present)
        # a theme the whole history hardly knew is measured against a trifle, not against nothing
        self.usual = {t: max(whole[t] / years, self.least * self.limits[t], 1e-9) for t in THEMES}

    def theme(self, start: int, end: int) -> str:
        years = max(1, end - start)
        total = totals(self.sim, start, end)
        rate = {t: total[t] / years for t in THEMES}
        ratio = {t: rate[t] / self.usual[t] for t in THEMES}
        named = [t for t in THEMES if ratio[t] >= self.stand_out and rate[t] >= self.least * self.limits[t]]
        if named:
            return max(named, key=lambda t: (ratio[t], t))
        if not self.kings or max(ratio[t] for t in TROUBLES) <= self.quiet:
            return "peace"
        return "kings"


def leading(sim, start: int, end: int) -> str:
    """The realm that was the greatest for most of those years ("" if none was)."""
    count = Counter(sim.top_realm[y] for y in range(start, end) if y in sim.top_realm)
    return max(count, key=lambda name: (count[name], name)) if count else ""


def name_eras(sim) -> list[dict]:
    s = sim
    data = s.data["eras"]
    judge = Judge(s)
    step = max(5, s.years // 25)
    stretches: list[list] = []
    for start in range(s.year0, s.present, step):
        end = min(s.present, start + step)
        stretches.append([start, end, judge.theme(start, end)])
    longest = max(100, s.years // 4)
    settle(stretches, judge, longest)
    shortest = max(20, s.years // 10)
    most = min(8, 3 + s.years // 120)
    while len(stretches) > 1 and (len(stretches) > most or min(e - b for b, e, _ in stretches) < shortest):
        i = min(range(len(stretches)), key=lambda k: (stretches[k][1] - stretches[k][0], k))
        if i == 0:
            j = 1
        elif i == len(stretches) - 1:
            j = i - 1
        else:
            before = stretches[i - 1][1] - stretches[i - 1][0]
            after = stretches[i + 1][1] - stretches[i + 1][0]
            j = i - 1 if before <= after else i + 1
        a, b = sorted((i, j))
        start, end = stretches[a][0], stretches[b][1]
        stretches[a:b + 1] = [[start, end, judge.theme(start, end)]]
        settle(stretches, judge, longest)
    themes = data["themes"]
    eras = [{"name": s.r.choice(data["myth"]), "start": None, "end": s.year0, "theme": "myth",
             "summary": s.r.choice(themes["myth"]["summary"])}]
    for start, end, theme in stretches:
        realm = leading(s, start, end) or "the realm"
        eras.append({"name": s.words.era_name(theme, realm=realm), "start": start, "end": end, "theme": theme,
                     "summary": s.r.choice(themes[theme]["summary"])})
    return eras


def settle(stretches: list[list], judge: Judge, longest: int) -> None:
    """Two neighbours of one kind are one era (named again from all its years, which may make it another kind), unless
    that would be longer than a chronicler would call one age."""

    def kind(st: list) -> tuple[str, str]:
        quiet = st[2] in ("kings", "peace")  # ordinary times and peaces are told apart by who led them
        return st[2], leading(judge.sim, st[0], st[1]) if quiet else ""

    k = 1
    while k < len(stretches):
        start, end = stretches[k - 1][0], stretches[k][1]
        if end - start > longest or kind(stretches[k]) != kind(stretches[k - 1]):
            k += 1
            continue
        stretches[k - 1:k + 1] = [[start, end, judge.theme(start, end)]]
        k = max(1, k - 1)
