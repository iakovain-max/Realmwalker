"""Hostile encounters: on the road (overworld) and creatures living on local maps.

Encounters depend on the region's danger, the land, whether it is night, and roads (bandits like
roads). Local maps of ruins, caves, barrows and towers are inhabited; wild country sometimes is.
Travel events that are not fights (merchants, pilgrims, refugees...) arrive with M4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import tcod.path

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules.creatures import Creature, choose_encounter, spawn_group

ALERT_RADIUS = 12


@dataclass
class PendingEncounter:
    """Something hostile met on the road, before anyone has drawn steel."""

    group: str
    creatures: list[Creature]
    intro: str
    spotted_first: bool  # the party saw them before being seen
    threat: str  # plain words on how dangerous this looks
    asleep: bool = False  # it came in the night, while the party slept
    attitude: str = "hostile"  # DMG 2024 starting attitude: hostile, indifferent or friendly


@dataclass
class LocalActor:
    """A band of creatures on a local map."""

    id: int
    group: str
    x: int
    y: int
    creatures: list[Creature] = field(default_factory=list)
    alert: bool = False
    seen: bool = False  # the player can see them right now

    def to_dict(self) -> dict:
        return {"id": self.id, "group": self.group, "x": self.x, "y": self.y, "alert": self.alert,
                "creatures": [c.to_dict() for c in self.creatures]}

    @classmethod
    def from_dict(cls, d: dict) -> LocalActor:
        return cls(d["id"], d["group"], d["x"], d["y"], [Creature.from_dict(c) for c in d["creatures"]], d.get("alert", False))


DEADLY_RATIO = 2.0  # a band worth twice the party's High budget "will very likely kill you" (threat_words)


def threat_ratio(tables, def_ids: list[str], party) -> float:
    """How a band measures up against the party (DMG 2024): its XP over the party's High budget."""
    from realmwalker.rules import encounter

    return encounter.ratio(tables, def_ids, [c.level for c in party if c.alive] or [1])


def threat_words(tables, creatures: list[Creature], party) -> str:
    """How dangerous a group looks next to the party (the DMG's encounter difficulty, in words)."""
    from realmwalker.rules import encounter

    levels = [c.level for c in party if c.alive] or [1]
    return DIFFICULTY_WORDS[encounter.difficulty(tables, [c.def_id for c in creatures], levels)]


DIFFICULTY_WORDS = {
    "trivial": "<good>You could take them.</>",
    "low": "<good>You could take them</>, though it would cost something.",
    "moderate": "<fg>A fair fight: it could go either way.</>",
    "high": "<warn>They look dangerous. Think twice.</>",
    "beyond": "<warn>They look dangerous. Think twice.</>",
    "deadly": "<danger>This will very likely kill you.</>",
}


def ratio_words(ratio: float) -> str:
    """Words for a band's XP over a party's High budget (the Moderate budget is about two thirds of High)."""
    if ratio < 0.5:
        return DIFFICULTY_WORDS["trivial"]
    if ratio <= 0.75:
        return DIFFICULTY_WORDS["moderate"]
    if ratio < DEADLY_RATIO:
        return DIFFICULTY_WORDS["high"]
    return DIFFICULTY_WORDS["deadly"]


def encounter_chance(danger: int, minutes: float, night: bool, on_road: bool) -> float:
    # A third rarer than it was until 2026-10 (0.004 + 0.009 a step of danger): a lone traveller met trouble every
    # two or three days, lost a third of those fights at level one, and rarely lived a month.
    per_hour = 0.003 + 0.006 * danger
    if night:
        per_hour *= 1.6
    if on_road:
        per_hour *= 0.7
    return min(0.9, per_hour * minutes / 60.0)


def roll_encounter(game, minutes: float) -> PendingEncounter | None:
    """Maybe something finds the party while it travels or camps."""
    w = game.world
    p = game.player
    if w.settlement_at(p.x, p.y) is not None or game.over is not None or not any(c.alive for c in game.party):
        return None
    danger = int(w.danger[p.x, p.y])
    night = game.light < 0.5
    on_road = bool(w.road[p.x, p.y])
    rng = w.rng.child(f"enc/{w.time}/{p.x},{p.y}")
    from realmwalker.game import past

    haunted = night and past.scar_at(w, p.x, p.y) is not None  # a field where the history left its dead
    if not rng.chance(encounter_chance(danger, minutes, night, on_road) * (1.6 if haunted else 1.0)):
        return None
    if haunted:
        intro = past.restless(game, rng)
        if intro and "restless_dead" in game.tables.creatures.encounters:
            enc = make_encounter(game, "restless_dead", rng)
            enc.intro = intro
            return enc
    group = choose_encounter(game.tables, game.land_key(p.x, p.y), danger, night, on_road, rng)
    if group is None:
        return None
    return make_encounter(game, group, rng)


def land_budget(game, rng: RNG, *, difficulty: str | None = None, deeper: int = 0) -> int:
    """What a band met here may be worth (DMG 2024 XP budget): the land's danger stands for a party level, the
    difficulty is rolled, per character of the party (bands are built for the land, not for the party's level)."""
    from realmwalker.rules import encounter

    p = game.player
    base = int(game.world.danger[p.x, p.y])
    difficulty = difficulty or encounter.roll_difficulty(game.tables, rng)
    size = len([c for c in game.party if c.alive]) or 1
    return encounter.budget(game.tables, [encounter.land_level(game.tables, base, deeper)] * size, difficulty)


def make_encounter(game, group: str, rng: RNG) -> PendingEncounter:
    tables = game.tables
    from realmwalker.rules import encounter

    special = float(tables.creatures.encounters[group].get("weight", 1)) == 0  # the watch, a mob: set pieces
    creatures = spawn_group(tables, group, rng, now=game.world.time, party_size=len(game.party),
                            budget=None if special else land_budget(game, rng.child("budget")))
    g = tables.creatures.encounters[group]
    stealth = max(int(tables.creatures[c.def_id].get("skills", {}).get("stealth", 0)) for c in creatures)
    their_roll = dice.d20(rng).natural + stealth
    our_best = max(game.sheet(c).passive_perception for c in game.party if c.alive)
    if game.light < 0.5 and not any(game.sheet(c).darkvision for c in game.party):
        our_best -= 5
    elif game.light >= 0.5:
        from realmwalker.rules.inventory import carried

        # A spyglass: the dust on the road ahead is seen before the riders are.
        our_best += 2 * max((int(tables.items.get(it.def_id).get("sight", 0)) for it in carried(game.party)), default=0)
    if game.travel_pace() != "normal":
        our_best += int(encounter.pace(tables, game.travel_pace()).get("passive", 0))  # fast -5, slow +5
    attitude = "hostile" if special else encounter.start_attitude(tables, [c.def_id for c in creatures], rng.child("mood"))
    if attitude != "hostile" and _hated(game, creatures):
        attitude = "hostile"  # an artifact's flaw: they know its bearer on sight
    return PendingEncounter(group, creatures, rng.choice(g["intro"]), our_best >= their_roll,
                            threat_words(tables, creatures, game.party), attitude=attitude)


def _hated(game, creatures) -> bool:
    from realmwalker.rules import magic

    for c in game.party:
        if not c.attuned:
            continue
        kind = magic.flag_value(c, "hated_by")
        if kind and any(game.tables.creatures[x.def_id].get("kind") == kind for x in creatures):
            return True
        if magic.flag(c, "beasts_hate") and any(game.tables.creatures[x.def_id].get("kind") == "beast"
                                                and float(game.tables.creatures[x.def_id].get("cr", 0)) <= 6
                                                for x in creatures):
            return True
    return False


# ---------------------------------------------------------------------------- local maps
def populate_local(game, lm) -> None:
    """Give a local map its inhabitants the first time anyone sets foot there."""
    if getattr(lm, "populated", False):
        return
    lm.populated = True
    w = game.world
    p = game.player
    rng = w.rng.child(f"populate/{lm.key}")
    site = w.site_at(p.x, p.y)
    danger = int(w.danger[p.x, p.y])
    groups: list[str] = []
    if site is not None:
        options = game.tables.creatures.site_inhabitants.get(site.kind, [])
        valid = [g for g in options if g in game.tables.creatures.encounters]
        if valid:
            groups.append(rng.choice(valid))
    elif w.settlement_at(p.x, p.y) is None and rng.chance(min(0.6, 0.05 * danger)):
        night = game.light < 0.5
        g = choose_encounter(game.tables, game.land_key(p.x, p.y), danger, night, False, rng)
        if g:
            groups.append(g)
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    ex, ey = lm.entry
    for i, group in enumerate(groups):
        spot = _far_spot(walk, (ex, ey), rng, min_dist=18)
        if spot is None:
            continue
        creatures = spawn_group(game.tables, group, rng.child(str(i)), now=w.time, party_size=len(game.party),
                                budget=land_budget(game, rng.child(f"budget{i}")))
        lm.actors.append(LocalActor(len(lm.actors) + 1, group, spot[0], spot[1], creatures))


def _far_spot(walk: np.ndarray, frm: tuple[int, int], rng: RNG, min_dist: int) -> tuple[int, int] | None:
    cells = np.argwhere(walk)
    if len(cells) == 0:
        return None
    d = np.maximum(np.abs(cells[:, 0] - frm[0]), np.abs(cells[:, 1] - frm[1]))
    far = cells[d >= min_dist]
    if len(far) == 0:
        far = cells
    x, y = far[rng.randint(0, len(far) - 1)]
    return int(x), int(y)


def actor_at(lm, x: int, y: int) -> LocalActor | None:
    for a in lm.actors:
        if a.x == x and a.y == y:
            return a
    return None


def passive_perception(game, a: LocalActor) -> int:
    """The sharpest of a band: 10 + their Perception."""
    best = 0
    for c in a.creatures:
        d = game.tables.creatures[c.def_id]
        best = max(best, int(d.get("skills", {}).get("perception", (int(d["abilities"]["wis"]) - 10) // 2)))
    return 10 + best


def notice_chance(game, a: LocalActor, dist: int) -> float:
    """How likely a band that could see you is to notice you this step. Walking openly it is a matter of luck
    and light; creeping (z), it is their Perception against your Stealth, which the dark helps and nearness
    hurts."""
    if not getattr(game, "sneaking", False):
        return (0.9 if dist <= 6 else 0.5) * (0.6 if game.light < 0.5 else 1.0)
    sharp = passive_perception(game, a)
    sharp += 5 if dist <= 2 else 2 if dist <= 5 else -2 if dist > 8 else 0
    sees_dark = any(int(game.tables.creatures[c.def_id].get("darkvision", 0)) for c in a.creatures)
    if game.light < 0.5 and not sees_dark:
        sharp -= 5
    return 1.0 if sharp >= game.sneak_roll else 0.0


def move_actors(game, lm) -> LocalActor | None:
    """Creatures react to the player's step. Returns an actor that has reached the player (a fight)."""
    from realmwalker.game.vision import can_see, player_fov

    p = game.player
    if not lm.actors:
        return None
    fov = player_fov(game, lm, remember=False)
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    for a in lm.actors:
        a.seen = bool(fov[a.x, a.y])
        dist = max(abs(a.x - p.lx), abs(a.y - p.ly))
        if not a.alert and dist <= ALERT_RADIUS:
            rng = game.world.rng.child(f"notice/{lm.key}/{a.id}/{game.world.time}")
            chance = notice_chance(game, a, dist)
            if can_see(game, lm, (a.x, a.y), (p.lx, p.ly), ALERT_RADIUS) and rng.chance(chance):
                a.alert = True
                if a.seen:
                    name = _group_name(game, a)
                    game.say(f"<danger>{name} {'has' if _one(name) else 'have'} seen you!</>", "danger")
        if a.alert and dist > 1:
            cost = np.where(walk, 1, 0).astype(np.int32)
            for other in lm.actors:
                if other is not a:
                    cost[other.x, other.y] = 0
            cost[p.lx, p.ly] = 1
            path = tcod.path.path2d(cost, start_points=[(a.x, a.y)], end_points=[(p.lx, p.ly)], cardinal=2, diagonal=3)
            if len(path) >= 2:
                nx, ny = (int(v) for v in path[1])
                if (nx, ny) != (p.lx, p.ly):
                    a.x, a.y = nx, ny
                    dist = max(abs(a.x - p.lx), abs(a.y - p.ly))
        if a.alert and dist <= 1:
            return a
    return None


def _one(name: str) -> bool:
    """Does a band's name take "has"? A bear, a gnoll pack, the barrow's lord: yes. Footpads, hired thugs: no."""
    words = name.lower().split()
    return words[0] in ("a", "an") or words[-1] in ("lord", "circle", "dragon", "captain", "watch")


def _group_name(game, a: LocalActor) -> str:
    name = game.tables.creatures.encounters.get(a.group, {}).get("name", "something")
    return name[:1].upper() + name[1:]
