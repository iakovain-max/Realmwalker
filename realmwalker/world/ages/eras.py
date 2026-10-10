"""Naming the ages: the years are divided into eras by what filled them (war, dragons, plague, founding, heroes, a
long peace under one great realm), the way Dwarf Fortress names its Age of Myth and Age of Legends.

The years are looked at a few at a time. Each stretch is measured against data/history.json "eras.thresholds" (how
much war, fire, plague... in a year makes it *that* kind of year); the strongest theme over its threshold names
the stretch, or it was a time of peace. Neighbouring stretches of one kind run together, and short eras are folded
into their neighbours until there are a handful, as a chronicler would tell it.
"""

from __future__ import annotations

THEMES = ("founding", "war", "dragons", "beasts", "plague", "heroes")


def name_eras(sim) -> list[dict]:
    s = sim
    data = s.data["eras"]
    limits = data["thresholds"]
    step = max(5, s.years // 25)
    stretches: list[list] = []
    for start in range(s.year0, s.present, step):
        span = range(start, min(s.present, start + step))
        total = {t: 0.0 for t in THEMES}
        for y in span:
            st = s.stats.get(y, {})
            total["war"] += st.get("battles", 0) + 2 * st.get("sieges", 0) + 3 * st.get("ruined", 0)
            total["dragons"] += st.get("dragon_attacks", 0)
            total["beasts"] += st.get("beast_attacks", 0) + 0.3 * st.get("raids", 0)
            total["plague"] += st.get("plague", 0) + 0.5 * st.get("famine", 0)
            total["founding"] += st.get("founded", 0)
            total["heroes"] += st.get("heroes", 0)
        years = max(1, len(span))
        score = {t: total[t] / years / float(limits[t]) for t in THEMES}
        best = max(THEMES, key=lambda t: (score[t], t))
        theme = best if score[best] >= 1.0 else "peace"
        if stretches and stretches[-1][2] == theme:
            stretches[-1][1] = span.stop
        else:
            stretches.append([start, span.stop, theme])
    shortest = max(20, s.years // 8)
    most = 6 if s.years >= 300 else 5 if s.years >= 150 else 3
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
        keep = stretches[a] if stretches[a][1] - stretches[a][0] >= stretches[b][1] - stretches[b][0] else stretches[b]
        stretches[a] = [stretches[a][0], stretches[b][1], keep[2]]
        del stretches[b]
    for k in range(len(stretches) - 1, 0, -1):  # two neighbours of one kind after folding are one era
        if stretches[k][2] == stretches[k - 1][2]:
            stretches[k - 1][1] = stretches[k][1]
            del stretches[k]
    themes = data["themes"]
    eras = [{"name": s.r.choice(data["myth"]), "start": None, "end": s.year0, "theme": "myth",
             "summary": s.r.choice(themes["myth"]["summary"])}]
    for start, end, theme in stretches:
        realm = s.top_realm.get(start + (end - start) // 2) or s.top_realm.get(start) or "the realm"
        eras.append({"name": s.words.era_name(theme, realm=realm), "start": start, "end": end, "theme": theme,
                     "summary": s.r.choice(themes[theme]["summary"])})
    return eras
