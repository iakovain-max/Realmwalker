"""The past in play (2026-10): what the lived history (world/ages) says about the places and people you meet.

- A ruin says what it was and how it ended; a barrow whose it is; a lonely tower who raised it; a lair what lives in
  it, once you are close enough to see the bones.
- A town remembers when it was founded and by whom, and the great things that happened to it.
- Townsfolk who were there (or whose parents were) tell of it in their own words.

Only words: nothing here changes the world. Worlds made before the ages were lived have less to say, and say it.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc
from realmwalker.core.textgen import tidy

GREAT_KINDS = ("razed", "sacked", "taken", "dragon", "dragon_tribute", "great_plague", "plague", "beast_attack",
               "burned", "raid", "became_city", "became_town", "founded_town", "founded_lordship", "rebuilt", "charter",
               "granted", "battle_named", "relieved", "beast_destroyed", "artifact_stolen", "persecution", "heresy",
               "martyred", "temple_raised", "proclaimed", "succession", "crisis", "assassination", "assassination_unknown",
               "regent_usurps")


def cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def year_text(year) -> str:
    if year is None:
        return "long ago"
    return str(year) if year > 0 else f"{1 - year} years before the Reckoning"


# ---------------------------------------------------------------------------- sites
def site_past(game, site) -> str:
    """A line or two about what a site was (marked up), or "" when nothing is remembered."""
    w = game.world
    pol = w.politics
    out = []
    past = pol.get("ruins", {}).get(str(site.id))
    if past:
        if past.get("elder"):
            out.append(f"<dim>It was {esc(past.get('was', 'something'))} of {esc(past.get('people', 'an old people'))}"
                       f", before the records began; {esc(past.get('cause', 'it fell'))} ended it.</>")
        elif past.get("name"):
            was = past.get("was", "a town")
            founded = (past.get("names") or [[None, past.get("founded")]])[0][1]
            fell = past.get("fell", past.get("year"))
            out.append(f"<dim>Once {esc(was)}, founded in {year_text(founded)}; in {year_text(fell)} it ended: "
                       f"{esc(past.get('cause', 'abandoned'))}.</>")
    tomb = pol.get("tombs", {}).get(str(site.id))
    if tomb is not None and tomb in w.figures:
        fig = w.figures[tomb]
        out.append(f"<dim>The barrow of {esc(fig.full_name())}, who died {year_text(fig.died)}.</>"
                   if site.kind == "barrow" else f"<dim>{esc(fig.full_name())} lies here.</>")
    tower = pol.get("towers", {}).get(str(site.id))
    if tower is not None and tower in w.figures:
        fig = w.figures[tower]
        out.append(f"<dim>Raised by the wizard {esc(fig.name)}.</>")
    beast = lair_beast(game, site)
    if beast is not None and close_enough(game, site):
        spec = beast_word(game, beast)
        out.append(f"<danger>The lair of {esc(beast.name)} {esc(beast.epithet)}, a {esc(spec)}.</>".replace("  ", " "))
    return " ".join(out)


def close_enough(game, site, tiles: int = 2) -> bool:
    p = game.player
    return abs(site.x - p.x) <= tiles and abs(site.y - p.y) <= tiles


def lair_beast(game, site):
    hid = game.world.politics.get("lairs", {}).get(str(site.id))
    fig = game.world.figures.get(hid) if hid is not None else None
    return fig if fig is not None and fig.alive else None


def beast_word(game, fig) -> str:
    for spec in game.tables.history["beasts"].values():
        if spec["creature"] == fig.creature:
            return spec["word"]
    return game.tables.creatures[fig.creature].get("name", "beast") if fig.creature in game.tables.creatures \
        else "beast"


# ---------------------------------------------------------------------------- settlements
def events_at(world, sid: int) -> list[dict]:
    return [e for e in world.history if sid in e.get("places", ()) and e.get("text")]


def founding_line(game, s) -> str:
    """'Founded in 812.' (and by whom, if the founding is remembered)."""
    w = game.world
    place = w.politics.get("places", {}).get(str(s.id))
    if not place or place.get("founded") is None:
        founded = w.politics.get("founded", {}).get(str(s.id))
        return f"Founded in {year_text(founded)}." if founded is not None else ""
    names = place.get("names", [])
    line = f"Founded in {year_text(place['founded'])}"
    if len(names) > 1:
        old = [n for n, _ in names[:-1] if n != s.name]
        if old:
            line += f", where {esc(old[-1])} stood before"
    return line + "."


def great_events(game, s, most: int = 3) -> list[dict]:
    """The things a town remembers best: the worst and the greatest, newest first."""
    events = [e for e in events_at(game.world, s.id) if e["kind"] in GREAT_KINDS and e.get("importance", 1) >= 2]
    events.sort(key=lambda e: (-e.get("importance", 2), -e["year"]))
    return events[:most]


def place_past(game, s) -> str:
    """A short history of a settlement, marked up, for the Look panel and the town's description."""
    parts = []
    first = founding_line(game, s)
    if first:
        parts.append(first)
    for e in great_events(game, s, 2):
        parts.append(f"In {year_text(e['year'])}: {esc(lower_first(e['text']))}")
    return " ".join(parts)


def lower_first(text: str) -> str:
    for article in ("The ", "A ", "An "):
        if text.startswith(article):
            return article.lower() + text[len(article):]
    return text


# ---------------------------------------------------------------------------- what townsfolk say
def remembered(game, npc, rng) -> str | None:
    """Something a townsperson remembers of their town's past, in their own words (None if nothing)."""
    w = game.world
    s = w.settlements[npc.settlement]
    year = game.moment.year
    events = great_events(game, s, 6)
    if not events:
        return None
    lived = [e for e in events if year - e["year"] <= npc.age - 6]
    if lived and rng.chance(0.6):
        e = rng.choice(lived)
        ago = year - e["year"]
        frames = game.tables.history.get("speech", {}).get("lived") or ["\"I remember it: {text}\""]
        when = "last year" if ago <= 1 else f"{ago} years ago" if ago < 20 else "when I was young"
        return tidy(rng.choice(frames).format(text=esc(lower_first(e["text"])), when=when, place=esc(s.name)))
    e = rng.choice(events)
    frames = game.tables.history.get("speech", {}).get("heard") or ["\"They say that {text}\""]
    return tidy(rng.choice(frames).format(text=esc(lower_first(e["text"])), when=year_text(e["year"]),
                                          place=esc(s.name)))


def figure_story(game, fig, rng) -> str:
    """A historical person's story, in a sentence or two, for the backstory of the townsperson they are."""
    w = game.world
    lines = []
    year = game.moment.year
    mine = [e for e in w.history if fig.id in e.get("figures", ()) and e.get("text") and
            e["kind"] not in ("wedding", "settled", "came_under")]
    mine.sort(key=lambda e: (-e.get("importance", 2), -e["year"]))
    for e in mine[:2]:
        lines.append(f"In {year_text(e['year'])}, {lower_first(e['text'])}")
    if fig.kills:
        victim = w.figures.get(fig.kills[0])
        if victim is not None:
            lines.append(f"{'He' if fig.sex == 'male' else 'She'} killed {victim.full_name()}.")
    parent = w.figures.get(fig.father) or w.figures.get(fig.mother)
    if parent is not None and not parent.alive and parent.died is not None and year - parent.died < 60:
        relation = "father" if parent.id == fig.father else "mother"
        lines.append(f"{'His' if fig.sex == 'male' else 'Her'} {relation}, {parent.full_name()}, died {parent.cause}.")
    return " ".join(lines[:3])


# ---------------------------------------------------------------------------- the masters of the old places
def group_of(game, fig) -> str | None:
    """The encounter group a beast of the history fights as (data/history.json beasts)."""
    for spec in game.tables.history["beasts"].values():
        if spec["creature"] == fig.creature:
            return spec["group"]
    return None


def beast_title(fig) -> str:
    return f"{fig.name} {fig.epithet}".strip()


def boss_for(game, site, boss: str | None) -> tuple[str | None, str | None]:
    """Who waits at the bottom of a site, by the history: a named beast in its lair, or the king in the barrow.
    Returns (encounter group, name), the name None when the place's master has no story."""
    if site is None:
        return boss, None
    beast = lair_beast(game, site)
    if beast is not None and beast.kind == "beast":
        group = group_of(game, beast)
        if group is not None and group in game.tables.creatures.encounters:
            return group, beast_title(beast)
    if site.kind == "barrow" and boss == "barrow_wight":
        tomb = game.world.politics.get("tombs", {}).get(str(site.id))
        fig = game.world.figures.get(tomb) if tomb is not None else None
        if fig is not None:
            return boss, fig.full_name()
    return boss, None


def on_battle(game, result) -> None:
    """A named thing of the history lies dead at your feet: the world remembers who did it."""
    if result.outcome != "victory":
        return
    w = game.world
    names = {c.name for c in result.dead if getattr(c, "named", False)}
    if not names:
        return
    for site_id, hid in list(w.politics.get("lairs", {}).items()):
        fig = w.figures.get(hid)
        if fig is not None and fig.alive and fig.kind == "beast" and beast_title(fig) in names:
            beast_slain(game, fig, int(site_id))
    site = w.site_at(game.player.x, game.player.y)
    if site is not None and site.kind == "barrow":
        tomb = w.politics.get("tombs", {}).get(str(site.id))
        fig = w.figures.get(tomb) if tomb is not None else None
        if fig is not None and fig.full_name() in names and not w.politics.setdefault("laid", {}).get(str(site.id)):
            w.politics["laid"][str(site.id)] = game.moment.year
            from realmwalker.world.history import remember

            text = f"{game.leader.name} put down {fig.full_name()}, who had walked in {site.name} since they died"
            remember(w, game.moment.year, "laid_to_rest", text, importance=3, sites=[site.id], figures=[fig.id],
                     player=True)
            game.say(f"<good>{esc(fig.full_name())} is still at last.</> <dim>{esc(cap(site.name))} is only a grave "
                     f"now.</>", "good")


def figure_slain(game, hid, site_id: int | None = None) -> None:
    """The figure of a beast the player killed is dead, and its lair empty (dragons call this too)."""
    w = game.world
    fig = w.figures.get(hid) if hid is not None else None
    if fig is None or not fig.alive:
        return
    fig.died = game.moment.year
    fig.cause = f"slain by {game.leader.name}"
    if site_id is not None:
        fig.died_at = f"X{site_id}"
    lairs = w.politics.get("lairs", {})
    for key, holder in list(lairs.items()):
        if holder == fig.id:
            del lairs[key]


def beast_slain(game, fig, site_id: int) -> None:
    from realmwalker.game import reputation
    from realmwalker.world import factions as fx
    from realmwalker.world.history import remember

    w = game.world
    site = w.sites[site_id]
    word = beast_word(game, fig)
    title = beast_title(fig)
    figure_slain(game, fig.id, site_id)
    victims = len(fig.kills)
    text = f"{game.leader.name} slew {title}, the {word} of {site.name}" + \
        (f", that had killed {victims} people of note" if victims > 1 else "")
    remember(w, game.moment.year, "beast_slain", text, importance=4, sites=[site_id], figures=[fig.id], player=True)
    amounts = {}
    for s in w.settlements:
        if abs(s.x - site.x) + abs(s.y - site.y) <= 16:
            realm = fx.realm_of_settlement(w, s)
            if realm is not None:
                amounts[realm.id] = max(amounts.get(realm.id, 0.0), 6.0 + victims)
    reputation.deed(game, f"slew {title}", amounts, x=site.x, y=site.y, fame=8 + victims, importance=3,
                    news_text=text)
    game.say(f"<good>{esc(title)} is dead.</> <dim>The {esc(word)} of {esc(site.name)} will not come down to the "
             f"farms again.</>", "good")


# ---------------------------------------------------------------------------- the marks the history left on the land
def scar_at(world, x: int, y: int) -> dict | None:
    """A field of a great battle, or the ruin of a town put to the sword, here (or next to here)."""
    best = None
    for scar in world.politics.get("scars", ()):
        d = max(abs(scar["x"] - x), abs(scar["y"] - y))
        if d <= 1 and (best is None or d < best[0]):
            best = (d, scar)
    return best[1] if best is not None else None


def scar_words(game, scar: dict, key: str) -> str:
    rng = game.world.rng.child(f"scar/{key}/{scar['x']},{scar['y']}/{game.world.time // 1440}")
    lines = game.tables.history.get("scars", {}).get(f"{key}_{scar['kind']}") or \
        game.tables.history.get("scars", {}).get(key) or []
    if not lines:
        return ""
    dead = f"{scar['dead']:,}" if scar.get("dead") else "many"
    return tidy(rng.choice(lines).format(name=esc(scar["name"]), year=scar["year"], dead=dead))


def scar_look(game, x: int, y: int) -> str:
    """What the Look panel says of a battlefield (only where the field itself is)."""
    scar = scar_at(game.world, x, y)
    if scar is None or (scar["x"], scar["y"]) != (x, y) or scar["kind"] != "battle":
        return ""
    return f"<dim>{scar_words(game, scar, 'look')}</>"


def restless(game, rng) -> str | None:
    """At night on a field of the dead: the intro of the dead that come for you, or None (not here, not now)."""
    p = game.player
    scar = scar_at(game.world, p.x, p.y)
    if scar is None or game.light >= 0.5 or not rng.chance(0.6):
        return None
    return scar_words(game, scar, "intro") or None


# ---------------------------------------------------------------------------- blood feuds
def grudge_of(world, hid: int) -> dict | None:
    """The blood feud someone of the history carries (world/ages/present.grudges), if the one they hate still lives."""
    for g in world.politics.get("grudges", ()):
        if g["by"] == hid:
            target = world.figures.get(g["against"])
            if target is not None and target.alive:
                return g
    return None


def grudge_want(game, g: dict) -> str:
    w = game.world
    target = w.figures[g["against"]]
    kin = w.figures.get(g["kin"])
    lines = game.tables.history.get("grudges", {}).get("want") or ["to see {target} dead, for {relation} {kin}"]
    rng = w.rng.child(f"grudge/{g['by']}")
    return rng.choice(lines).format(target=target.full_name(), relation=f"their {g['relation']}",
                                    kin=kin.full_name() if kin is not None else "", year=g.get("year", ""))
