"""History: the chronicle that tells the world's past, and remember(), which writes into it while the game is played.

Worlds *live* their history year by year as they are made (world/ages, after Dwarf Fortress): world.history is the
list of what happened (dated events, oldest first), and today is what the ages left. The chronicle is told from it
age by age, in built-in words.
"""

from __future__ import annotations

from realmwalker.world import factions as fx


def remember(world, year: int, kind: str, text: str, *, importance: int = 2, factions=(), places=(), sites=(),
             figures=(), player: bool = False, data: dict | None = None) -> dict:
    """Write something into the world's history while the game is played (it keeps its order: today is last)."""
    e = {"id": int(world.politics.get("next_event", len(world.history))), "year": int(year), "kind": kind,
         "text": text, "importance": int(max(1, min(5, importance))), "factions": [int(f) for f in factions],
         "places": [int(p) for p in places], "figures": [int(h) for h in figures]}
    if sites:
        e["sites"] = [int(s) for s in sites]
    if player:
        e["player"] = True
    if data:
        e["data"] = data
    world.politics["next_event"] = e["id"] + 1
    world.history.append(e)
    return e


# ---------------------------------------------------------------------------- the chronicle
ERA_YEARS = 50
WAR_GROUP = "war"
WAR_KINDS_TOLD = ("war", "peace", "battle", "taken", "sacked", "siege", "relieved", "rebellion", "freedom", "crushed")


def present_lines(world, tables) -> list[str]:
    """Who rules the great realms today, and who is at war."""
    year = tables.calendar.at(world.time).year
    out = []
    for f in fx.active_factions(world, "kingdom", "free_city", "elven_realm", "clan"):
        if f.liege >= 0:
            continue
        leader = fx.leader_of(world, f)
        if leader is not None and leader.alive:
            out.append(f"{f.name[:1].upper() + f.name[1:]} is ruled by {leader.full_name()}, "
                       f"{leader.age(year)} years old.")
    for war in world.wars:
        if war.get("active"):
            a, d = world.factions.get(war["attacker"]), world.factions.get(war["defender"])
            if a is not None and d is not None:
                out.append(f"{a.name[:1].upper() + a.name[1:]} is at war with {d.name}.")
    return out


def pick_events(events: list[dict], most: int = 6) -> list[dict]:
    """The events a chronicler would choose from a stretch of years: the greatest first, few of one kind."""
    best, per_group = [], {}
    for e in sorted(events, key=lambda e: (-e.get("importance", 2), e["year"], e.get("id", 0))):
        group = WAR_GROUP if e["kind"] in WAR_KINDS_TOLD else e["kind"]
        if per_group.get(group, 0) >= (3 if group == WAR_GROUP else 1):
            continue
        per_group[group] = per_group.get(group, 0) + 1
        best.append(e)
        if len(best) >= most:
            break
    best.sort(key=lambda e: (e["year"], e.get("id", 0)))
    return best


def lower_first(text: str) -> str:
    """'The dragon...' -> 'the dragon...' after 'In 812,' (names and people keep their capitals)."""
    for article in ("The ", "A ", "An "):
        if text.startswith(article):
            return article.lower() + text[len(article):]
    return text


def chronicle_by_ages(world, tables) -> dict:
    """The chronicle of a world that lived its history (world/ages): told age by age."""
    eras = world.politics["eras"]
    now = tables.calendar.at(world.time).year
    events = [e for e in world.history if e.get("importance", 2) >= 3 and e.get("text")]
    paras = []
    myth = eras[0]
    old = pick_events([e for e in events if e["year"] < myth["end"]], 5)
    first = f"Of {myth['name']} little is certain. {myth.get('summary', '')}".strip()
    if old:
        first += " " + " ".join(e["text"] for e in old)
    paras.append(first)
    for era in eras[1:]:
        span = [e for e in events if era["start"] <= e["year"] < era["end"]]
        great = [e for e in span if e.get("importance", 2) >= 4] or span
        chosen = pick_events(great)
        name = era["name"][:1].upper() + era["name"][1:]
        text = f"{name}, from {era['start']} to {era['end'] - 1}. {era.get('summary', '')}".strip()
        if chosen:
            text += " " + " ".join(f"In {e['year']}, {lower_first(e['text'])}" for e in chosen)
        paras.append(text)
    today = present_lines(world, tables)
    if today:
        paras.append(f"And now, in the year {now}: " + " ".join(today))
    return {"title": f"A Chronicle of {world.meta.name}", "text": "\n\n".join(paras)}


def chronicle_fallback(world, tables) -> dict:
    """The chronicle in built-in words: the deep past, then the ages, then today."""
    return chronicle_by_ages(world, tables)
