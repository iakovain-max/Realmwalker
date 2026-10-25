"""The words a story is written with (docs/ADVENTURES.md §8.8): real names everywhere - the villain's name and kind,
its home, the towns, the cast, a victim of the history and the year they died, what it fears - for textgen's
templates and nested tables (adventures.json "words")."""

from __future__ import annotations


def for_adventure(game, adv: dict | None) -> dict:
    from realmwalker.game.story import cast, places
    from realmwalker.world import threats

    w = game.world
    out = {"hero": game.leader.name.split()[0]}
    if adv is None:
        return out
    t = threats.records(w).get(adv["threat"])
    if t is not None:
        name = threats.villain_name(w, t)
        fig = threats.villain_figure(w, t)
        out["villain"] = name
        out["villain_short"] = fig.name if fig is not None else name
        out["beast"] = _beast_word(game, fig) if fig is not None else "beast"
        out.update({"he": "it", "him": "it", "his": "its", "He": "It", "His": "Its"})  # (a beast's; a person's below)
        victim = _victim(w, fig)
        out["victim"] = victim[0]
        out["victim_year"] = victim[1]
        if fig is not None and fig.kind != "beast":  # (the dead king's death, the captain's gang: D.3)
            from realmwalker.game.past import year_text

            she = getattr(fig, "sex", "male") == "female"
            slayer = w.figures.get(fig.slayer) if getattr(fig, "slayer", -1) >= 0 else None
            out["slayer"] = slayer.full_name() if slayer is not None else \
                f"those who wanted {'her' if she else 'him'} dead"  # (the history named no one)
            # (a phrase that follows a verb: "died in 812", "died 340 years before the Reckoning", "died long ago")
            year = year_text(fig.died) if fig.died is not None else "long ago"
            out["died_year"] = f"in {year}" if year.lstrip("-").isdigit() else year
            out.update({"he": "she" if she else "he", "him": "her" if she else "him", "his": "her" if she else "his",
                        "He": "She" if she else "He", "His": "Her" if she else "His", "king": "queen" if she else
                        "king", "man": "woman" if she else "man"})
        gang = threats.gang_of(w, t) if t["kind"] == "outlaw" else None
        if gang is not None:
            out["gang"] = gang.name
        temper = game.tables.villains.get("tempers", {}).get(t["villain"].get("temper") or "", {})
        if temper.get("omens"):
            rng = w.rng.child(f"omen/{adv['id']}/{game.moment.total_days}")
            out["omen"] = rng.choice(temper["omens"])
    out["companion"] = game.party[1].name.split()[0] if len(game.party) > 1 else out["hero"]
    # (what its spy stole, and whose: a tailored move's words, E.1; only a stolen token makes one, the rest is for
    # the storybook's reading)
    token = adv.get("token") or {"what": "a glove", "of": out["companion"]}
    out["token"], out["token_of"] = token["what"], token["of"]
    out["helper"], out["helper_town"] = "one who helped you", "the town"
    helper = w.npcs.get(int(adv["reprisal"])) if adv.get("reprisal") is not None else None
    if helper is not None:  # (the one who pays for helping you: a reprisal's words)
        out["helper"] = helper.name
        sid = getattr(helper, "settlement", None)
        out["helper_town"] = w.settlements[int(sid)].name if sid is not None and 0 <= int(sid) < len(
            w.settlements) else "the town"
    wedge = adv.get("wedge") or {}  # (the companion its wedge is driven at, and what it offers them: E.2)
    out["tempted"] = str(wedge.get("name", out["companion"])).split()[0]
    out["offer"] = wedge.get("offer", "what they want most")
    frame = adv.get("frame") or {}  # (where it did its murder, and to whom: E.2)
    sid = frame.get("settlement")
    out["frame_town"] = w.settlements[int(sid)].name if sid is not None else "a town near here"
    out["frame_victim"] = frame.get("name", "a stranger")
    for name, p in adv["places"].items():
        if places.exists(w, p):
            out[name] = places.name(w, p)
    home = adv["places"].get("home")
    if home:
        x, y = places.xy(w, home)
        area = w.area_at(x, y)
        out["area"] = area.name if area is not None else "the hill country"
    for role in adv["cast"]:
        out[role] = cast.describe(game, adv, role)
    wk = weakness(game, adv)
    if wk is not None:
        out["weakness"] = wk["name"]
        rng = w.rng.child(f"lore/{adv['id']}")
        from realmwalker.core import textgen

        out["weakness_lore"] = textgen.fill(rng.choice(wk["lore"]), rng, {}, out)
    return out


def weakness(game, adv: dict) -> dict | None:
    wid = (adv.get("hidden") or {}).get("weakness", {}).get("weakness")
    for lst in game.tables.villains.get("weaknesses", {}).values():
        for x in lst:
            if x["id"] == wid:
                return x
    return None


def _beast_word(game, fig) -> str:
    from realmwalker.game import past

    try:
        return past.beast_word(game, fig)
    except (KeyError, AttributeError):
        return "beast"


def _victim(world, fig) -> tuple[str, str]:
    from realmwalker.game.past import year_text

    if fig is not None:
        for k in getattr(fig, "kills", []):
            v = world.figures.get(k)
            if v is not None:
                return v.full_name(), year_text(v.died) if v.died is not None else "the old days"
    return "more people than anyone has counted", "the old days"


KEY_WORDS = {"weakness": "what it fears", "means": "the means to use it", "bait": "the bait it could not pass by",
             "quiet": "it does not know you have come", "ally": "{ally} at your side",
             "anchor": "what binds {villain_short} to the world, in your hands", "name": "{his} true name",
             "militia": "the people of {town}, ready to stand", "ford": "the ford held against {his} dead",
             "backway": "the hideout's back way, that the gang does not watch",
             "inside": "the man in {town} who sold the caravans' days, turned",
             "rival": "a truce with your rivals: they will come when you face it"}


def key_text(game, adv: dict, k: str) -> str:
    from realmwalker.core import textgen

    words = for_adventure(game, adv)
    if k == "weakness" and "weakness" in words:
        return f"it fears {words['weakness']}"
    return textgen.fill(KEY_WORDS.get(k, k.replace("_", " ")), game.world.rng, {}, words)
