"""Death and what is left behind (M9).

Death is permanent. Everything the character carried is gone: there is no body to find and no gear to recover.
What remains is what the world remembers — and the world keeps going.

- `die(game)` writes the fallen character into the world (`world.politics["fallen"]`), puts their death into the
  chronicle and the news if anyone had heard of them, and releases the surviving companions to go home, where
  another traveller may hire them one day.
- `fallback_obituary`: the words on the death screen, kept with the record so the next character can read about
  the one before.

Nothing here carries over to a new character: their standing, money and gear all die with them. Only the story
stays, in the world.
"""

from __future__ import annotations

from realmwalker.core.textgen import a_or_an, count_of
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.rules.items import money_text
from realmwalker.world import factions as fx


def fallen(world) -> list[dict]:
    return world.politics.setdefault("fallen", [])


def place_text(game) -> str:
    w = game.world
    p = game.player
    s = w.settlement_at(p.x, p.y)
    if s is not None:
        return s.name
    site = w.site_at(p.x, p.y)
    if site is not None:
        return site.name
    area = w.area_at(p.x, p.y)
    if area is not None:
        return area.name
    return game.biome_def(p.x, p.y)["name"]


def record_for(game) -> dict | None:
    """The record for this character, if death has already been written down."""
    return next((r for r in fallen(game.world) if r.get("id") == game.world.meta.id + "/" + game.leader.name
                 and r.get("day") == game.moment.total_days), None)


def die(game) -> dict:
    """Write a death into the world. Safe to call twice (it only happens once)."""
    from realmwalker.game import reputation
    from realmwalker.world.politics import year_of

    kept = record_for(game)
    if kept is not None:
        return kept
    from realmwalker.game import story

    story.on_death(game)  # (the hero's tales are orphaned; the threats go on: Expansion 6)
    w = game.world
    c = game.leader
    over = game.over or {}
    m = game.moment
    r = game.renown
    standings = {fid: int(v) for fid, v in r.standing.items() if fid in w.factions and abs(v) >= 15}
    record = {
        "id": w.meta.id + "/" + c.name, "name": c.name, "race": c.race, "cls": c.cls, "level": c.level,
        "age": c.age, "day": m.total_days, "year": year_of(w, game.tables), "date": m.date_text(),
        "cause": over.get("cause", "of misfortune"), "place": place_text(game), "x": int(game.player.x),
        "y": int(game.player.y), "deeds": list(c.deeds[-8:]), "kills": dict(c.kills),
        "fame": r.fame, "infamy": r.infamy, "money": c.money, "days_lived": m.total_days - int(r.flags.get("start_day", 0)),
        "titles": list(reputation.titles(game)), "standings": {str(k): v for k, v in standings.items()},
        "quests_done": sum(1 for q in game.quests if q["state"] == "finished"),
        "companions": [x.name for x in list(game.party[1:]) + list(game.waiting)],
        "obituary": "",
    }
    record["obituary"] = write_obituary(game, record)
    fallen(w).append(record)
    remember(game, record)
    from realmwalker.game import revival

    revival.bury_all(game)  # (the bodies the party carried are dead for good now)
    release_companions(game)
    game.dirty = True
    return record


def road_words(days: int) -> str:
    """How long a life was on the road, as an obituary says it."""
    if days < 3:
        return "only a few days"
    if days < 14:
        return "barely a fortnight"
    if days < 60:
        return f"some {max(2, round(days / 7))} weeks"
    if days < 330:
        return f"some {max(2, round(days / 30))} months"
    if days < 700:
        return "about a year"
    return f"some {round(days / 365)} years"


def write_obituary(game, record: dict) -> str:
    """A few sentences about the dead, from the built-in words (data/fallback_text.json obituary), kept with the
    record: who they were, what the world thought of them, what they did and killed, and where it ended."""
    from realmwalker.core import textgen

    tables = game.tables.fallback["obituary"]
    rng = game.world.rng.child(f"obituary/{record['id']}/{record['day']}")
    t = game.tables
    first = record["name"].split()[0]
    kills = sum(record.get("kills", {}).values())
    values = {
        "first": first, "age": str(record["age"]), "road": road_words(int(record.get("days_lived", 0))),
        "who": f"{a_or_an(t.races[record['race']]['name'].lower())} {t.classes[record['cls']]['name'].lower()}",
        "place": record["place"], "year": str(record["year"]), "kills": kill_list(game, record, 4),
        "deed": rng.choice(record["deeds"]) if record.get("deeds") else "",
    }
    known = record["fame"] - record["infamy"]
    standing = "fame" if record["fame"] >= 10 and known >= 0 else "infamy" if record["infamy"] >= 10 else "nobody"
    parts = ["opening", standing, "deeds" if record.get("deeds") else "no_deeds"]
    if kills >= 8:
        parts.append("killer")
    elif kills == 0 and rng.chance(0.6):
        parts.append("gentle")
    parts.append("closing")
    return " ".join(textgen.fill(rng.choice(tables[part]), rng, tables, values) for part in parts)


def how_they_died(cause: str) -> str:
    """A death as it reads after a name. Causes are kept as they happen ("froze to death", "died of thirst",
    "killed by the wolf", "of misfortune"); this makes each one follow a name: "... was killed by the wolf"."""
    cause = (cause or "").strip() or "died"
    words = cause.split()
    if words[0] == "of":
        return f"died {cause}"
    if len(words) > 1 and words[1] == "by":
        return f"was {cause}"
    return cause


def remember(game, record: dict) -> None:
    """The world hears of it: the chronicle for the famous, news for anyone people had heard of."""
    from realmwalker.world import news

    from realmwalker.world import history

    w = game.world
    known = record["fame"] + record["infamy"]
    text = f"{record['name']} {how_they_died(record['cause'])}, at {record['place']}"
    if known >= 8 or record["level"] >= 4:
        history.remember(w, record["year"], "legend", text, importance=3 if known >= 20 else 2, player=True)
    if known >= 4:
        news.add(w, text, record["x"], record["y"], kind="deed", importance=2 if known < 20 else 3, player=True)


def release_companions(game) -> None:
    """Those who lived go home, and can be hired again by whoever comes next."""
    from realmwalker.game.people import town_of

    w = game.world
    for c in list(game.party[1:]) + list(game.waiting):
        if not c.alive:
            continue
        npc = w.npcs.get(c.companion.get("npc", -1)) if c.companion else None
        if npc is None:
            continue
        npc.flags.pop("companion", None)
        from realmwalker.game.companions import released

        released(game, c, npc)  # sell-swords can be hired again; the rest go back to who they were
        npc.alive = True
        npc.present = True
        how = how_they_died(game.over.get("cause", "") if game.over else "") if game.over else "died badly"
        npc.remember(f"travelled with {game.leader.name}, who {how}")
        town = town_of(w, npc.settlement)
        if npc.id not in town.npcs:
            town.npcs.append(npc.id)
    game.party = game.party[:1]
    game.waiting = []


# ---------------------------------------------------------------------------- the words
def kill_list(game, record: dict, limit: int = 6) -> str:
    kills = sorted(record.get("kills", {}).items(), key=lambda kv: -kv[1])[:limit]
    return ", ".join(count_of(n, k) for k, n in kills)


def standing_words(game, record: dict) -> list[str]:
    """What the powers of the land thought of them, in their own words."""
    w = game.world
    out = []
    for fid, value in sorted(record.get("standings", {}).items(), key=lambda kv: -abs(kv[1]))[:4]:
        f = w.factions.get(int(fid))
        if f is None:
            continue
        word, color = fx.standing_name(game.tables, value)
        out.append(f"<{color}>{esc(f.name)}: {word}</>")
    return out


def fallback_obituary(game, record: dict) -> list[str]:
    """The built-in obituary: plain facts, plainly put."""
    t = game.tables
    race = t.races[record["race"]]["name"]
    cls = t.classes[record["cls"]]["name"]
    lines = [
        f"<title>{esc(record['name'])}</>",
        f"<dim>{race} {cls}, level {record['level']}, aged {record['age']}</>",
        "",
        f"{esc(record['name'].split()[0])} {esc(how_they_died(record['cause']))} on {esc(record['date'])}, "
        f"at {esc(record['place'])}.",
    ]
    if record.get("obituary"):
        lines += ["", *[esc(p) for p in record["obituary"].split("\n") if p.strip()]]
    kills = kill_list(game, record)
    if kills:
        lines += ["", f"Killed: {esc(kills)}."]
    if record.get("quests_done"):
        lines.append(f"Work finished for others: {record['quests_done']}.")
    if record.get("companions"):
        lines.append(f"Travelled with: {esc(', '.join(record['companions']))}.")
    if record.get("deeds"):
        lines += ["", "Remembered for:"] + [f"  · {esc(d)}" for d in record["deeds"][-6:]]
    words = standing_words(game, record)
    if words:
        lines += ["", "What they thought of them: " + " · ".join(words)]
    lines += ["", f"<dim>They died with {money_text(record.get('money', 0))} on them, and it is gone, with "
                  f"everything else they carried.</>",
              "<dim>The world goes on. You can begin a new life in it from the title screen (New Character).</>"]
    return lines


# ---------------------------------------------------------------------------- those who came before
def former_lives(game) -> list[dict]:
    """Characters of yours who died in this world, newest first."""
    return list(reversed(fallen(game.world)))
