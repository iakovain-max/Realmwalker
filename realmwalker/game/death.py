"""Death and what is left behind (M9).

Death is permanent. Everything the character carried is gone: there is no body to find and no gear to recover.
What remains is what the world remembers — and the world keeps going.

- `die(game)` writes the fallen character into the world (`world.politics["fallen"]`), puts their death into the
  chronicle and the news if anyone had heard of them, and releases the surviving companions to go home, where
  another traveller may hire them one day.
- `fallback_obituary` / `obituary_facts` / `apply_obituary`: the words on the death screen, built-in or written by
  the AI (task OBITUARY), and kept with the record so the next character can read about the one before.

Nothing here carries over to a new character: their standing, money and gear all die with them. Only the story
stays, in the world.
"""

from __future__ import annotations

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
        "obituary": "", "obituary_source": "",
    }
    fallen(w).append(record)
    remember(game, record)
    release_companions(game)
    game.dirty = True
    return record


def remember(game, record: dict) -> None:
    """The world hears of it: the chronicle for the famous, news for anyone people had heard of."""
    from realmwalker.world import news

    w = game.world
    known = record["fame"] + record["infamy"]
    text = f"{record['name']} died {record['cause']}, at {record['place']}"
    if known >= 8 or record["level"] >= 4:
        w.history.append({"year": record["year"], "kind": "legend", "text": text, "factions": [], "places": [],
                          "figures": [], "importance": 3 if known >= 20 else 2, "player": True})
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
        npc.remember(f"travelled with {game.leader.name}, who died {game.over.get('cause', 'badly') if game.over else 'badly'}")
        town = town_of(w, npc.settlement)
        if npc.id not in town.npcs:
            town.npcs.append(npc.id)
    game.party = game.party[:1]
    game.waiting = []


# ---------------------------------------------------------------------------- the words
def kill_list(game, record: dict, limit: int = 6) -> str:
    kills = sorted(record.get("kills", {}).items(), key=lambda kv: -kv[1])[:limit]
    return ", ".join(f"{n} {k}{'s' if n > 1 and not k.endswith('s') else ''}" for k, n in kills)


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
        f"Died {esc(record['date'])}, {esc(record['cause'])}, at {esc(record['place'])}.",
    ]
    if record.get("obituary"):
        lines += ["", *[f"<ai>{esc(p)}</>" if record.get("obituary_source") == "ai" else esc(p)
                        for p in record["obituary"].split("\n") if p.strip()]]
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


def obituary_facts(game, record: dict) -> dict:
    t = game.tables
    w = game.world
    standings = []
    for fid, value in record.get("standings", {}).items():
        f = w.factions.get(int(fid))
        if f is not None:
            word, _ = fx.standing_name(t, value)
            standings.append(f"{f.name}: {word}")
    return {
        "name": record["name"],
        "who": f"a {t.races[record['race']]['name'].lower()} {t.classes[record['cls']]['name'].lower()}, "
               f"level {record['level']}, aged {record['age']}",
        "death": f"{record['cause']}, at {record['place']}, in the year {record['year']}",
        "deeds": "; ".join(record.get("deeds", [])) or "nothing anyone wrote down",
        "kills": kill_list(game, record) or "nothing worth counting",
        "standing": "; ".join(standings) or "nobody of importance had an opinion",
        "fame": f"fame {record['fame']}, infamy {record['infamy']}",
    }


def apply_obituary(game, record: dict, data: dict) -> bool:
    if not data or not data.get("obituary") or record.get("obituary_source") == "ai":
        return False
    record["obituary"] = str(data["obituary"]).strip()
    record["obituary_source"] = "ai"
    game.dirty = True
    return True


# ---------------------------------------------------------------------------- those who came before
def former_lives(game) -> list[dict]:
    """Characters of yours who died in this world, newest first."""
    return list(reversed(fallen(game.world)))
