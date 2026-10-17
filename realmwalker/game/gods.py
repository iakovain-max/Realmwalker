"""The gods of the world's faiths and the devout (DMG 2024 chapter 3, "Gods and Other Powers" and "Divine
Intervention"; Expansion 5 Part B).

The world keeps its own faiths (data/factions.json faiths: a god, what it is god of, the peoples who follow it, and
the cleric domains its priests serve). A character's god is their people's. Someone devout - a cleric, or anyone the
faith's church counts as one of its own or thinks well of - who is about to die in a fight may be answered
(rules/miracles.py does the miracle). The chance is small and grows with deeds for the faith; once the god has
answered, it will not again for a year.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup

BASE = 0.02  # (anyone devout)
CLERIC = 0.03  # (the god's own priest)
PER_RANK = 0.01  # (each rank in the church)
MOST = 0.12
QUIET_DAYS = 365  # (once answered, a year before the god hears again)


def faith_of(game, c) -> tuple[str, dict]:
    from realmwalker.world.cultures import faith_for

    fid = faith_for(game.tables, c.culture)
    faiths = game.tables.factions["faiths"]
    return fid, faiths.get(fid) or {}


def chance(game, c) -> float:
    """How likely their god is to answer them as they die (0 if they are not devout, or the god answered lately)."""
    from realmwalker.game import reputation
    from realmwalker.world import factions as fx

    if not c.alive:
        return 0.0
    last = game.renown.flags.get("god_answered")
    if last is not None and game.world.time - int(last) < QUIET_DAYS * 1440:
        return 0.0
    fid, faith = faith_of(game, c)
    if not faith:
        return 0.0
    church = fx.church_of(game.world, fid) if game.world.factions else None
    rank = reputation.rank(game, church.id) if church is not None else None
    standing = reputation.standing(game, church.id) if church is not None else 0
    cleric = c.cls == "cleric"
    if not cleric and rank is None and standing < 20:
        return 0.0  # (not devout: the god does not know their name)
    p = BASE + (CLERIC if cleric else 0.0) + PER_RANK * (rank or 0) + max(0, min(40, standing)) / 1000.0
    return min(MOST, p)


def prayers(game, battle) -> dict:
    """The devout among the party as a fight begins, by fighter id."""
    out = {}
    for f in battle.side("party"):
        c = f.char
        if c is None or f.bond is not None:
            continue
        p = chance(game, c)
        if p <= 0:
            continue
        fid, faith = faith_of(game, c)
        domains = list(faith.get("domains") or ("life",))
        if c.cls == "cleric" and c.subclass in domains:
            domains = [c.subclass]  # (a priest is answered as their own domain is)
        out[f.id] = {"chance": p, "faith": fid, "god": faith.get("god", ""), "short": faith.get("short", ""),
                     "domains": domains}
    return out


def after_battle(game, battle) -> list[str]:
    """A god answered in this fight: the world remembers it, and the god is quiet for a while."""
    answered = [f for f in battle.fighters if f.id in (getattr(battle, "answered", None) or ())]
    if not answered:
        return []
    from realmwalker.world import history

    game.renown.flags["god_answered"] = int(game.world.time)
    out = []
    for f in answered:
        p = battle.prayers.get(f.id, {})
        name = escape_markup(f.char.name)
        god = p.get("god") or "the god"
        from realmwalker.world.politics import year_of

        year = year_of(game.world, game.tables)
        history.remember(game.world, year, "miracle", f"{f.char.name} called on {god} in the hour of death, and was "
                         "answered.", importance=2, player=True)
        out.append(f"<magic>{name} was dying, and {escape_markup(god)} answered.</> The god will not be so near again "
                   "for a long while.")
    return out
