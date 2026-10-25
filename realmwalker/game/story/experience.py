"""Experience from stories (Expansion 6 C.8, docs/ADVENTURES.md §8.10 "Story experience"; data situations.json
"experience").

Every story's experience goes through `award`: a share of the encounter budget the game already uses for the party's
levels (rules/encounter.budget), by size: a situation's end is small, fair or great (a share of a moderate budget, x1.25
when its way through shed no blood), a tale's chapter a high budget, a tale won a share of one on top of its finale
fight's own. The living share it as they share a fight's.

The *Experience* setting (Settings screen; `Settings.experience`, copied onto `game.experience` every frame by the game
screen as `verbosity` is): "both" (the default) or "stories" - the DMG's milestones: fights give none
(`fights_count`, read by fight.finish_battle) and a story's experience is doubled (`stories_only`).

    spec(game)  fights_count(game)  amount(game, size, no_fight=False)  award(game, size, key, no_fight=False)
    problems(tables)
"""

from __future__ import annotations

DEFAULT = {"sizes": {"small": ["moderate", 0.25], "fair": ["moderate", 0.5], "great": ["moderate", 1.0],
                     "chapter": ["high", 1.0], "finale": ["high", 0.5]}, "no_fight": 1.25, "stories_only": 2.0}


def spec(game) -> dict:
    return (getattr(game.tables, "situations", None) or {}).get("experience") or DEFAULT


def fights_count(game) -> bool:
    """Whether beating foes is worth experience (not under "Stories only")."""
    return getattr(game, "experience", "both") != "stories"


def amount(game, size: str, no_fight: bool = False) -> int:
    """The experience each living member of the party gets for a story's end of this size."""
    from realmwalker.rules import encounter

    living = [c for c in game.party if c.alive]
    if not living:
        return 0
    sp = spec(game)
    difficulty, share = sp["sizes"].get(size, sp["sizes"].get("fair", ["moderate", 0.5]))
    xp = encounter.budget(game.tables, [c.level for c in living], difficulty) * float(share) / len(living)
    if no_fight:
        xp *= float(sp.get("no_fight", 1.0))
    if not fights_count(game):
        xp *= float(sp.get("stories_only", 1.0))
    return int(xp)


def award(game, size: str, key: str, no_fight: bool = False) -> list[str]:
    """Give a story's experience to the living; the lines to show (the amount first, then any levels gained)."""
    from realmwalker.rules.progression import award_xp

    xp = amount(game, size, no_fight)
    if xp <= 0:
        return []
    rng = game.world.rng.child(f"story_xp/{key}")
    out = []
    for c in game.party:
        if c.alive:
            out += award_xp(c, xp, game.tables, rng)
    living = sum(1 for c in game.party if c.alive)
    return [f"<good>+{xp} experience</>{' each' if living > 1 else ''}."] + out


def problems(tables) -> list[str]:
    from realmwalker.rules.encounter import DIFFICULTIES

    sp = (getattr(tables, "situations", None) or {}).get("experience")
    if not sp:
        return []
    out = []
    for size in ("small", "fair", "great", "chapter", "finale"):
        if size not in sp["sizes"]:
            out.append(f"situations.json: experience.sizes has no '{size}'.")
    for size, (difficulty, share) in sp["sizes"].items():
        if difficulty not in DIFFICULTIES or not isinstance(share, (int, float)) or not 0 < share <= 5:
            out.append(f"situations.json: experience.sizes.{size} must be [one of {DIFFICULTIES}, a share].")
    return out
