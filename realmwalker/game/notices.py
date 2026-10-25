"""The notice board in a town square (M6): wanted posters (perhaps your own face), the lord's proclamations,
the laws of the realm, and the small business of the town. Reading it is a quick way to hear the news that has
reached this place."""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game import law, news
from realmwalker.rules.items import money_text
from realmwalker.world import factions as fx

PROCLAIMED = ("war", "peace", "succession", "crisis", "elected", "taken", "sacked", "siege", "plague", "famine",
              "rebellion", "freedom", "crushed", "gang_new", "gang_destroyed", "treaty", "marriage", "cult_purged",
              "dragon", "dragon_tribute", "dragon_slain")


def notices(game, settlement) -> list[dict]:
    """[{"kind", "title", "text"}] pinned to the board here, most urgent first."""
    w = game.world
    t = game.tables
    rng = w.rng.child(f"notices/{settlement.id}/{game.moment.total_days // 7}")
    realm = fx.realm_of_settlement(w, settlement)
    out: list[dict] = []
    if realm is not None:
        bounty = game.renown.bounties.get(realm.id, 0)
        crimes = law.open_crimes(game, realm.id)
        if bounty > 0 and not law.disguised(game):
            what = sorted({law.crime_def(game, r["crime"])["name"] for r in crimes if r["crime"] in t.law["crimes"]})
            out.append({"kind": "wanted", "title": "WANTED",
                        "text": f"{esc(game.leader.name)}, for {', '.join(what) or 'crimes against the realm'}. "
                                f"{money_text(max(100, bounty // 2))} for their capture, alive. By order of "
                                f"{esc(realm.name)}. <dim>(The likeness is crude, but it is you.)</>"})
    from realmwalker.game import quests

    for q in quests.board_bounties(game, settlement):
        words = q["words"]
        if q["template"] == "hunt_beast":  # (a beast of the history, in its lair)
            out.append({"kind": "wanted", "title": "WANTED", "bounty": q,
                        "text": f"{esc(words['beast'])}, {esc(words['beast_what'])}, {esc(words['where'])}. "
                                f"{money_text(q['reward'])} from the watch of {esc(settlement.name)} for its head, "
                                f"within {q['days']} days."})
            continue
        if q["template"] == "clear_lair":  # (a den near the town: C.10)
            out.append({"kind": "wanted", "title": "WANTED", "bounty": q,
                        "text": f"Whatever has made its den at {esc(words['site'])}, {esc(words['where'])}, has "
                                f"taken stock and travellers. {money_text(q['reward'])} from the watch of "
                                f"{esc(settlement.name)} to whoever clears it out, within {q['days']} days."})
            continue
        out.append({"kind": "wanted", "title": "WANTED", "bounty": q,
                    "text": f"{esc(words['target'])} and the outlaws called {esc(words['gang'])}, for robbery and "
                            f"murder on the roads. They hide at {esc(words['site'])}. {money_text(q['reward'])} from "
                            f"the watch of {esc(settlement.name)} for the end of them, within {q['days']} days."})
    from realmwalker.game.story import work

    out += work.notices(game, settlement)  # (the town's paid work: who is hiring, and the terms)
    from realmwalker.game import story
    from realmwalker.world import threats

    for t_ in threats.live(w):  # (every stirring threat within a week's walk that nobody has taken on: Expansion 6)
        if t_.get("adventure") is None and threats.distance(w, t_, settlement.x, settlement.y) <=                 int(t.threats.get("start", {}).get("tiles", 56)) and story._can_take(game, t_):
            out.append({"kind": "hook", "title": "A PLEA", "text": esc(story.hook_line(game, t_, settlement)),
                        "hook": t_["id"]})
    heard = []
    for item in news.known_at(w, settlement.x, settlement.y):
        if item.get("kind") in PROCLAIMED and not item.get("player") and item["importance"] >= 2:
            heard.append(item)
        if len(heard) >= 4:
            break
    for item in heard:
        when = news.age_text(news.now_days(w) - item["day"])
        text = item["text"][:1].upper() + item["text"][1:]
        out.append({"kind": "proclamation", "title": "NEWS", "text": f"{esc(text)} <dim>({when})</>", "id": item["id"]})
    if realm is not None:
        laws = fx.laws_of(w, realm)
        words = t.factions["laws"]
        picks = [k for k in ("magic", "weapons", "religion") if laws.get(k) not in (None, "legal", "open", "tolerant")]
        for key in picks[:2]:
            out.append({"kind": "law", "title": "BY ORDER",
                        "text": f"{esc(realm.name[:1].upper() + realm.name[1:])}: {words[key][str(laws[key])]}"})
        banned = law.contraband_for(game, realm.id)
        if banned:
            names = ", ".join([t.items.get(i)["name"] for i in banned if i in t.items.defs
                               and not t.items.get(i).get("poison")]
                              + (["poisons of every kind"] if any(t.items.get(i).get("poison") for i in banned)
                                 else []))
            out.append({"kind": "law", "title": "BY ORDER", "text": f"Forbidden within the walls: {names}."})
    local = t.politics.get("notices", [])
    for line in rng.sample(local, min(2, len(local))):
        out.append({"kind": "local", "title": "NOTICE",
                    "text": esc(textgen.fill(line, rng, {}, {"place": settlement.name}))})
    return out


def read(game, settlement) -> list[dict]:
    """Read the board: its news counts as heard."""
    items = notices(game, settlement)
    for n in items:
        if "id" in n:
            game.renown.heard.add(n["id"])
    return items
