"""Rumours, letters and notice boards that lead somewhere (Expansion 6 G.5, docs/ADVENTURES.md §5.14).

What people say and what paper says points at the world's real troubles:
- `nearest_hook(game, x, y, reach=)`: the nearest threat nobody has taken on that the hero could take (within a
  week's walk: threats.json start.tiles, the notice boards' reach);
- `tell_hook(game, settlement, rng)`: the dialogue outcome `reveal_hook`: someone tells of that threat; its den goes
  on the map, its latest sign is heard (the claw marks on the map), and its hook beat is offered (take it, or not now),
  unless another story moment is already waiting. None when there is no such threat (the old news, then);
- `tell_clue(game, npc, rng)`: the dialogue outcome `reveal_clue`: for one of the hero's tales, someone points at
  where its current chapter's work is: who knows the truth a learn step wants, who saw it, the place of a step. The
  person becomes known, the place goes on the map, the tale's journal keeps the line, and the same pointer is never
  told twice (`adv["hints"]`: "<step id>/<route index>"). None when there is nothing to point at;
- `rumour_line(game, x, y, rng)`: an ordinary rumour that is about a real threat near here (its den on the map, no
  offer: the boards and the notables give that);
- `letter_lines(game, rng)`: a dead stranger's letter found in a chest (game/books._letter, first reading) that is
  about a threat in reach (twice the boards' reach from where it is read): its den on the map, its hook offered.
Every line is adventures `words` (rumour_hook, rumour_clue_who, rumour_clue_place, rumour_clue_saw, rumour_near,
letter_hook, letter_den), three variants at least, filled with the threat's or the tale's names.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

LETTER_REACH = 2  # a found letter reaches twice as far as a notice board
LETTER_CHANCE = 0.7  # how often a dead stranger's letter is about a live threat in reach, when there is one
RUMOUR_CHANCE = 0.3  # how often an ordinary rumour is about one


def reach(game) -> int:
    return int(game.tables.threats.get("start", {}).get("tiles", 56))


def nearest_hook(game, x: int, y: int, within: float | None = None) -> dict | None:
    """The nearest live threat nobody has taken on that the hero could take now, within `within` tiles."""
    from realmwalker.game import story
    from realmwalker.world import threats

    w = game.world
    limit = reach(game) if within is None else within
    best = None
    for t in threats.live(w):
        if t.get("adventure") is not None:
            continue
        d = threats.distance(w, t, x, y)
        if d > limit or (best is not None and (d, int(t["id"][1:])) >= best[0]):
            continue
        if story._can_take(game, t):  # (the dear test last: only for one in reach and nearer)
            best = ((d, int(t["id"][1:])), t)
    return best[1] if best else None


def _words(game) -> dict:
    return game.tables.adventures.get("words", {})


def _fill(game, key: str, rng, values: dict) -> str:
    from realmwalker.core import textgen
    from realmwalker.game.story.beats import tidy

    tables = _words(game)
    lines = tables.get(key) or ["{hook}"]
    return tidy(textgen.fill(rng.choice(list(lines)), rng, tables, values))


def _den_known(game, t: dict) -> None:
    """Its den on the map, and its latest sign heard (so the map's claw marks show it)."""
    from realmwalker.world import threats

    x, y = threats.home_xy(game.world, t)
    game.player.explored[x, y] = True
    if t.get("signs"):
        game.renown.heard.add(int(t["signs"][-1]))
    game.dirty = True


def _waiting(game) -> bool:
    from realmwalker.game.story import beats

    return beats.director(game.world).get("pending") is not None


def _offer(game, t: dict, town) -> bool:
    """Its hook beat, unless another story moment waits (it is then on the boards and with the notables still)."""
    from realmwalker.game import story

    if _waiting(game):
        return False
    before = t.get("offer")
    story.offer_hook(game, t, town, staged=False)
    return t.get("offer") is not before


def tell_hook(game, settlement, rng) -> list[str] | None:
    """`reveal_hook`: the nearest threat's tale, told and offered. None when there is none to tell."""
    from realmwalker.game import story

    t = nearest_hook(game, settlement.x, settlement.y)
    if t is None:
        return None
    values = story.hook_words(game, t, settlement)
    values["hook"] = story.hook_line(game, t, settlement)
    out = [esc(_fill(game, "rumour_hook", rng, values))]
    _den_known(game, t)
    out.append(f"<dim>({esc(values['home'])} is on your map now.)</>")
    _offer(game, t, settlement)
    return out


# ---------------------------------------------------------------------------- clues for a tale already taken
def _person_words(game, entry: dict | None) -> tuple[str, object] | None:
    """Words for a person a step names, and the townsperson (or None while they wait for their town)."""
    from realmwalker.game.story import cast

    if not entry:
        return None
    w = game.world
    who = cast.person(w, entry)
    if who is not None and hasattr(who, "job"):
        if not getattr(who, "alive", True):
            return None
        town = w.settlements[who.settlement].name if 0 <= who.settlement < len(w.settlements) else "the villages"
        return f"{who.name}, the {who.title} at {town}", who
    if who is not None:  # (a figure of the history)
        return who.full_name(), None
    if "settlement" in entry and 0 <= int(entry["settlement"]) < len(w.settlements):
        s = w.settlements[int(entry["settlement"])]
        if "job" in entry:
            job = game.tables.people["occupations"].get(entry["job"], {}).get("name", entry["job"])
            return f"the {job} of {s.name}", None
    return None


def _pointers(game, adv: dict) -> list[tuple[str, str, dict]]:
    """(hint key, words table, values) for every pointer the tale's current chapter has: required steps first."""
    from realmwalker.game import story
    from realmwalker.game.story import places

    w = game.world
    out = []
    steps = sorted(story.open_steps(adv), key=lambda s: bool(s.get("optional")))
    for st in steps:
        tg = st["target"]
        if st["kind"] == "learn":
            for i, r in enumerate(tg.get("routes", [])):
                if r.get("how") == "talk":
                    pw = _person_words(game, r.get("who"))
                    if pw:
                        out.append((f"{st['id']}/{i}", "rumour_clue_who", {"who": pw[0], "_npc": pw[1]}))
                elif r.get("at") and places.exists(w, r["at"]):
                    out.append((f"{st['id']}/{i}", "rumour_clue_place", {"place": places.name(w, r["at"]),
                                                                        "_at": r["at"]}))
            continue
        if st["kind"] == "witness":
            entry = tg.get("who") or (adv["cast"].get(tg["role"]) if tg.get("role") else None)
            pw = _person_words(game, entry)
            if pw:
                out.append((f"{st['id']}/w", "rumour_clue_saw", {"who": pw[0], "_npc": pw[1]}))
            continue
        place = tg.get("place")
        if place and places.exists(w, place) and st["kind"] not in ("choose", "slay", "prepare", "endure"):
            out.append((f"{st['id']}/p", "rumour_clue_place", {"place": places.name(w, place), "_at": place}))
    return out


def tell_clue(game, npc, rng) -> list[str] | None:
    """`reveal_clue`: someone points at where one of the hero's tales goes on. None when nothing is left to point."""
    from realmwalker.game import story
    from realmwalker.game.story import places
    from realmwalker.game.story import words as wordsmod

    for adv in story.active(game):
        hinted = adv.setdefault("hints", [])
        fresh = [p for p in _pointers(game, adv) if p[0] not in hinted and
                 not (p[2].get("_npc") is not None and npc is not None and p[2]["_npc"] is npc)]
        if not fresh:
            continue
        key, table, values = fresh[0]
        hinted.append(key)
        words = wordsmod.for_adventure(game, adv)
        fill = {k: v for k, v in words.items() if isinstance(v, str)}
        fill.setdefault("villain", "the enemy")  # (its threat record gone: never a raw slot)
        fill.update({k: v for k, v in values.items() if not k.startswith("_")})
        line = _fill(game, table, rng, fill)
        out = [esc(line)]
        who = values.get("_npc")
        if who is not None:
            who.known = True
        at = values.get("_at")
        if at is not None:
            x, y = places.xy(game.world, at)
            game.player.explored[x, y] = True
            out.append(f"<dim>({esc(values['place'])} is on your map now.)</>")
        teller = f"{npc.first_name}: " if npc is not None else ""
        story.journal(adv, f"{teller}{line}", int(game.moment.total_days))
        out.append(f"<dim>(Written in your journal, under {esc(adv['title'])}.)</>")
        game.dirty = True
        return out
    return None


# ---------------------------------------------------------------------------- rumours and letters
def rumour_line(game, x: int, y: int, rng) -> str | None:
    """An ordinary rumour about the nearest real threat (its den on the map; no offer). None now and then, or when
    there is none near."""
    from realmwalker.game import story

    if not rng.chance(RUMOUR_CHANCE):
        return None
    t = nearest_hook(game, x, y)
    if t is None:
        return None
    town = game.world.settlement_at(x, y)
    values = story.hook_words(game, t, town)
    _den_known(game, t)
    return esc(_fill(game, "rumour_near", rng, values)) + f" <dim>({esc(values['home'])} is on your map now.)</>"


def letter_lines(game, rng) -> list[str] | None:
    """A dead stranger's letter about a threat in reach: its den on the map, its tale offered. None when there is
    none (or the letter is about something else this time)."""
    from realmwalker.game import story

    p = game.player
    t = nearest_hook(game, p.x, p.y, within=reach(game) * LETTER_REACH)
    if t is None or not rng.chance(LETTER_CHANCE):
        return None
    values = story.hook_words(game, t, None)
    _den_known(game, t)
    out = [f"<warn>{esc(_fill(game, 'letter_hook', rng, values))}</>",
           f"<dim>{esc(_fill(game, 'letter_den', rng, values))} ({esc(values['home'])} is on your map now.)</>"]
    _offer(game, t, None)
    return out
