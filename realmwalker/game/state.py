"""The running game: the player's position and knowledge, and every action that moves time on.

Pure logic. Screens call these methods and draw the results; nothing here draws anything.
The player is a placeholder wanderer until character creation arrives (M2).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
import tcod.path

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.game.log import MessageLog
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.inventory import add_existing, remove_item
from realmwalker.world.calendar import MINUTES_PER_HOUR, Moment, duration_text
from realmwalker.world.local import LocalMap, get_local_map, terrain_remap
from realmwalker.world.model import DIRS, World
from realmwalker.world.tables import Tables

log = logging.getLogger("realmwalker.game")

LOCAL_STEP_SECONDS = 6  # one local-map step: about one 5e round
MILES_PER_TILE = 3
FORD_MINUTES = 45
ROAD_HOURS = {"mountains": 1.6, "high_mountains": 3.0, "marsh": 1.2, "hills": 0.9}
DEFAULT_ROAD_HOURS = 0.75
WALKING_HOURS_PER_DAY = 8
HOME_RADIUS = 12  # tiles of home district the wanderer already knows


@dataclass
class PlayerState:
    name: str
    x: int
    y: int
    explored: np.ndarray  # bool [x, y] overworld tiles seen
    local_key: str | None = None
    lx: int = 0
    ly: int = 0
    alive: bool = True
    home: int = -1  # settlement id
    known_settlements: set[int] = field(default_factory=set)
    visited_settlements: set[int] = field(default_factory=set)
    visited_areas: set[int] = field(default_factory=set)
    seconds: int = 0  # sub-minute time carried from local-map steps
    steps: int = 0


@dataclass
class TravelPlan:
    path: list[tuple[int, int]]  # overworld tiles, not including the start
    minutes: int
    miles: int
    destination: tuple[int, int]


class GameState:
    def __init__(self, world: World, player: PlayerState, tables: Tables, messages: MessageLog | None = None,
                 party: list[Character] | None = None) -> None:
        self.world = world
        self.player = player
        self.tables = tables
        self.log = messages or MessageLog()
        self.party: list[Character] = party if party is not None else [default_wanderer(tables, world)]
        self.travel: TravelPlan | None = None
        self._cost_cache: np.ndarray | None = None
        B = tables.biomes
        self._biome_remap = np.array([B.index.get(b, B.index["plains"]) for b in world.biome_ids], dtype=np.int32)
        self.dirty = False  # something changed since the last save
        self.encounter = None  # a hostile group met on the road, before the fight (game.encounters)
        self.battle = None  # the fight in progress (rules.combat.Battle)
        self.battle_actor = None  # the local-map band being fought, if any
        self.aftermath = None  # what the last fight left behind (game.fight.Aftermath)
        self.over: dict | None = None  # set when the character has died
        self.show_dice = True
        self.auto_supplies = True  # eat and drink from the packs when needed (a setting)
        self.survival = True  # needs, weather and wounds over time (tests may switch it off)
        self.camp = None  # the camp while resting outdoors (game.camp.Camp)
        self.event = None  # a travel event waiting for the player's choice (game.events.PendingEvent)
        self.lost = False  # off the road in fog or darkness, with no idea where
        self.day_log: dict = {}  # today's journey, for the evening's narrated passage
        self.narration: list[dict] = []  # finished travel days waiting to be written up (by the screen)
        self._wading = False
        self._remaps: dict[str, np.ndarray] = {}
        self._recent_areas: list[int] = []

    # ------------------------------------------------------------------ queries
    @property
    def leader(self) -> Character:
        return self.party[0]

    def sheet(self, char: Character | None = None) -> Sheet:
        return Sheet(char or self.leader, self.tables)

    def pace(self) -> float | None:
        """How much slower than an unburdened walker the party moves (None = someone cannot move)."""
        from realmwalker.rules import body, health

        worst = 1.0
        for member in self.party:
            m = Sheet(member, self.tables).travel_multiplier()
            b = body.travel_multiplier(member)
            if m is None or b is None:
                return None
            worst = max(worst, m * b * health.travel_multiplier(member, self.tables))
        return worst

    @property
    def moment(self) -> Moment:
        return self.tables.calendar.at(self.world.time)

    @property
    def latitude(self) -> float:
        return self.world.latitude(self.player.y)

    @property
    def light(self) -> float:
        return self.moment.light(self.latitude)

    @property
    def in_local(self) -> bool:
        return self.player.local_key is not None

    @property
    def local(self) -> LocalMap | None:
        if self.player.local_key is None:
            return None
        return self.world.local_maps.get(self.player.local_key)

    def biome_def(self, x: int, y: int) -> dict:
        return self.tables.biomes.defs[int(self._biome_remap[self.world.biome[x, y]])]

    def biome_key(self, x: int, y: int) -> str:
        return self.tables.biomes.ids[int(self._biome_remap[self.world.biome[x, y]])]

    def say(self, text: str, category: str = "info") -> None:
        self.log.add(text, category, self.world.time)

    # ------------------------------------------------------------------ time
    def pass_time(self, minutes: float, activity: str = "rest") -> None:
        """Advance the world clock; the party lives through it (needs, weather, wounds) in chunks.
        activity: "walk", "rest", "sleep" or "fight"."""
        from realmwalker.game import survival

        whole = int(minutes)
        if whole <= 0:
            return
        before = self.moment
        remaining = whole
        while remaining > 0:
            step = min(30, remaining)
            self.world.time += step
            remaining -= step
            survival.tick(self, step, activity)
            if self.over is not None:
                self.world.time += remaining
                break
        after = self.moment
        if after.total_days != before.total_days:
            if self.day_log.get("miles"):
                self.narration.append(self.day_log)
                self.narration = self.narration[-3:]
            self.day_log = {}
            self.say(f"<title>{after.date_text()}.</>", "system")
        self.dirty = True

    def pass_seconds(self, seconds: int, activity: str = "rest") -> None:
        self.player.seconds += seconds
        minutes, self.player.seconds = divmod(self.player.seconds, 60)
        self.pass_time(minutes, activity)

    @property
    def weather(self):
        from realmwalker.game.survival import weather

        return weather(self)

    # ------------------------------------------------------------------ overworld movement
    def step_minutes(self, x0: int, y0: int, x1: int, y1: int) -> int | None:
        """Minutes to walk from one overworld tile to a neighbour, or None if impossible."""
        w = self.world
        if not w.in_bounds(x1, y1):
            return None
        target = self.biome_def(x1, y1)
        if not target["passable"]:
            return None
        diagonal = x0 != x1 and y0 != y1
        if w.road[x0, y0] and w.road[x1, y1]:
            hours = ROAD_HOURS.get(self.biome_key(x1, y1), DEFAULT_ROAD_HOURS)
        else:
            here = self.biome_def(x0, y0)
            hours = (float(here["move_hours"]) + float(target["move_hours"])) / 2.0
            if w.river[x1, y1] and not w.road[x1, y1]:
                hours += FORD_MINUTES / 60.0
        if diagonal:
            hours *= 1.41
        return max(1, int(round(hours * MINUTES_PER_HOUR)))

    @property
    def busy(self) -> bool:
        """Something must be dealt with first: trouble on the road, a fight or its aftermath, or death."""
        return (self.encounter is not None or self.battle is not None or self.aftermath is not None
                or self.over is not None or self.event is not None)

    def move(self, dx: int, dy: int) -> bool:
        if self.busy:
            return False
        self.camp = None  # moving on breaks camp
        if self.in_local:
            return self._move_local(dx, dy)
        return self._move_overworld(dx, dy)

    def _move_overworld(self, dx: int, dy: int) -> bool:
        p = self.player
        dx, dy = self._maybe_stray(dx, dy)
        nx, ny = p.x + dx, p.y + dy
        pace = self.pace()
        if pace is None:
            self.say("You are carrying too much to walk. Drop something first (i: inventory).", "warn")
            return False
        minutes = self.step_minutes(p.x, p.y, nx, ny)
        if minutes is not None:
            minutes = int(round(minutes * pace))
        if minutes is None:
            if self.world.in_bounds(nx, ny):
                self.say(f"The {self.biome_def(nx, ny)['name']} bars the way. There is no crossing without a boat.", "warn")
            return False
        fording = bool(self.world.river[nx, ny]) and not self.world.road[nx, ny]
        prev_area = self.world.area_at(p.x, p.y)
        p.x, p.y = nx, ny
        p.steps += 1
        minutes = int(round(minutes * self.weather.travel_factor()))
        self._wading = fording
        self.pass_time(minutes, "walk")
        if self.over is not None:
            return True
        self._log_step(nx, ny)
        self._check_bearings()
        if fording:
            river = self.world.river_at(nx, ny)
            name = f"the {river.name.removeprefix('the ')}" if river else "a river"
            self.say(f"You wade across {name}, waist-deep and numbingly cold.", "warn")
        self.reveal()
        self._arrive(prev_area)
        if self.encounter is None and self.battle is None:
            from realmwalker.game.encounters import roll_encounter

            enc = roll_encounter(self, minutes)
            if enc is not None:
                self.encounter = enc
                self.travel = None
            else:
                from realmwalker.game.events import roll_event

                ev = roll_event(self, minutes)
                if ev is not None:
                    self.event = ev
                    self.travel = None
                    self.day_log.setdefault("events", []).append(self.tables.travel_events[ev.event_id]["name"])
        return True

    # ------------------------------------------------------------------ the day's journey and getting lost
    def _log_step(self, x: int, y: int) -> None:
        log = self.day_log
        log["miles"] = log.get("miles", 0) + MILES_PER_TILE
        land = self.biome_def(x, y)["name"]
        lands = log.setdefault("lands", [])
        if land not in lands:
            lands.append(land)
        key = "road" if self.world.road[x, y] else "off_road"
        log[key] = log.get(key, 0) + 1
        from realmwalker.world.weather import KIND_WORDS

        log["weather"] = KIND_WORDS.get(self.weather.kind, self.weather.kind)

    def lost_dc(self) -> int | None:
        """How hard it is to keep your bearings here, or None if there is no danger of getting lost."""
        p = self.player
        w = self.world
        if w.road[p.x, p.y] or w.settlement_at(p.x, p.y) is not None:
            return None
        vis = self.weather.visibility
        dark = self.light < 0.3
        if vis >= 0.6 and not dark:
            return None
        return 10 + (6 if vis < 0.3 else (3 if vis < 0.6 else 0)) + (3 if dark else 0)

    def _maybe_stray(self, dx: int, dy: int) -> tuple[int, int]:
        """Lost, you may walk the wrong way without knowing it."""
        if not self.lost:
            return dx, dy
        rng = self.world.rng.child(f"stray/{self.world.time}")
        if rng.chance(0.5):
            options = [(ddx, ddy) for ddx in (-1, 0, 1) for ddy in (-1, 0, 1) if (ddx or ddy)]
            return rng.choice(options)
        return dx, dy

    def _check_bearings(self) -> None:
        from realmwalker.game.camp import check

        p = self.player
        if self.lost:
            if self.world.road[p.x, p.y] or self.world.settlement_at(p.x, p.y) is not None:
                self.lost = False
                self.say("You strike a road you know. Your bearings come back.", "good")
                return
            dc = self.lost_dc()
            ok, roll = check(self, "survival", dc or 8, tag="bearings")
            if ok:
                self.lost = False
                self.say(f"{roll} You find your bearings again.", "good")
            return
        dc = self.lost_dc()
        if dc is None:
            return
        ok, roll = check(self, "survival", dc, tag="lost")
        if not ok:
            self.lost = True
            self.travel = None
            what = "fog" if self.weather.kind == "fog" else ("storm" if self.weather.visibility < 0.6 else "dark")
            self.say(f"{roll} <warn>In the {what} you lose your way.</> You are no longer sure which way you are "
                     f"walking. Find a road, or wait for better light.", "warn")

    def reveal(self) -> None:
        """Mark overworld tiles around the player as explored."""
        p = self.player
        biome = self.biome_key(p.x, p.y)
        radius = {"hills": 5, "mountains": 6, "high_mountains": 8, "forest": 2, "pine_forest": 2}.get(biome, 3)
        if self.light < 0.5:
            radius = max(1, radius - 1)
        radius = max(1, int(round(radius * self.weather.visibility)))
        x0, x1 = max(0, p.x - radius), min(self.world.width, p.x + radius + 1)
        y0, y1 = max(0, p.y - radius), min(self.world.height, p.y + radius + 1)
        xs = np.arange(x0, x1)[:, None]
        ys = np.arange(y0, y1)[None, :]
        circle = (xs - p.x) ** 2 + (ys - p.y) ** 2 <= radius * radius + 1
        p.explored[x0:x1, y0:y1] |= circle
        # Settlements announce themselves from a little further (smoke, bells, roads).
        for s in self.world.settlements:
            if abs(s.x - p.x) <= radius + 2 and abs(s.y - p.y) <= radius + 2:
                p.known_settlements.add(s.id)

    def _arrive(self, prev_area) -> None:
        p = self.player
        area = self.world.area_at(p.x, p.y)
        if area is not None and area is not prev_area:
            first = area.id not in p.visited_areas
            p.visited_areas.add(area.id)
            if first:
                biome = self.biome_def(p.x, p.y)
                desc = self.world.rng.child(f"areadesc{area.id}").choice(biome["descriptions"])
                self.say(f"You enter <place>{area.name}</>. {desc}", "place")
            elif area.id not in self._recent_areas:
                self.say(f"You are back in <place>{area.name}</>.", "place")
            # Walking along a border should not repeat the same announcement every step.
            self._recent_areas = ([area.id] + [a for a in self._recent_areas if a != area.id])[:4]
        s = self.world.settlement_at(p.x, p.y)
        if s is not None:
            first = s.id not in p.visited_settlements
            p.visited_settlements.add(s.id)
            p.known_settlements.add(s.id)
            self.say(self.settlement_arrival_text(s, first), "place")
        site = self.world.site_at(p.x, p.y)
        if site is not None:
            spec = self.tables.sites["site_types"].get(site.kind, {})
            self.say(f"You come upon <place>{_cap(site.name)}</>. {spec.get('desc', '')}", "place")

    def settlement_arrival_text(self, s, first: bool) -> str:
        spec = self.tables.sites["settlement_types"][s.kind]
        kind = spec["name"]
        if not first:
            return f"You reach <place>{s.name}</> again."
        culture = self.tables.names["cultures"].get(s.culture, {}).get("label", s.culture)
        souls = f"about {round(s.population, -1 if s.population < 1000 else -2):,} souls"
        walls = " behind its walls" if s.walled else ""
        return f"You reach <place>{s.name}</>, {textgen.a_or_an(kind)} of {souls}{walls}. <dim>{culture} folk live here.</>"

    # ------------------------------------------------------------------ local maps
    def enter_local(self) -> LocalMap:
        p = self.player
        lm = get_local_map(self.world, self.tables, p.x, p.y)
        p.local_key = lm.key
        p.lx, p.ly = lm.entry
        from realmwalker.game.encounters import populate_local

        populate_local(self, lm)
        where = self.world.settlement_at(p.x, p.y)
        if where is not None:
            self.say(f"You walk into <place>{where.name}</>.", "place")
        else:
            biome = self.biome_def(p.x, p.y)
            self.say(f"You leave the track and look about you: {biome['name']}.", "flavor")
        self.dirty = True
        return lm

    def leave_local(self) -> None:
        if not self.in_local:
            return
        self.player.local_key = None
        self.say("You return to the road and the wider land.", "flavor")
        self.dirty = True

    def _move_local(self, dx: int, dy: int) -> bool:
        lm = self.local
        p = self.player
        if lm is None:
            p.local_key = None
            return False
        nx, ny = p.lx + dx, p.ly + dy
        if not lm.in_bounds(nx, ny):
            if any(a.alert for a in lm.actors):
                self.say("You break away and leave them behind.", "warn")
            self.leave_local()
            return True
        from realmwalker.game.encounters import actor_at

        target = actor_at(lm, nx, ny)
        if target is not None:
            from realmwalker.game.fight import start_battle
            from realmwalker.rules.combat import FOE

            name = self.tables.creatures.encounters.get(target.group, {}).get("name", "them")
            intro = f"You fall on {name}!" if not target.alert else f"You close with {name}."
            start_battle(self, target.creatures, intro, surprised=None if target.alert else FOE, actor=target,
                         title=name[:1].upper() + name[1:])
            return True
        pace = self.pace()
        if pace is None:
            self.say("You are carrying too much to move. Drop something first (i: inventory).", "warn")
            return False
        T = self.tables.terrain
        t = int(self.remap_for(lm)[lm.terrain[nx, ny]])
        tid = T.ids[t]
        if tid == "door_closed":
            lm.terrain[nx, ny] = lm.terrain_ids.index("door_open") if "door_open" in lm.terrain_ids else lm.terrain[nx, ny]
            self.pass_seconds(LOCAL_STEP_SECONDS)
            self.say("You open the door.", "flavor")
            return True
        if not T.walk[t]:
            return False
        p.lx, p.ly = nx, ny
        p.steps += 1
        self.pass_seconds(int(LOCAL_STEP_SECONDS * float(T.cost[t]) * (1.41 if dx and dy else 1.0) * pace), "walk")
        here = lm.items.get((nx, ny))
        if here:
            names = ", ".join(self.tables.items.name(i) for i in here[:4]) + (" and more" if len(here) > 4 else "")
            self.say(f"Here: <loot>{names}</>. <dim>(g to pick up)</>", "loot")
        if self.over is None:
            self._creatures_act(lm)
        return True

    def _creatures_act(self, lm: LocalMap) -> None:
        """Creatures on this map react to the player; one that reaches the player starts a fight."""
        from realmwalker.game.encounters import move_actors

        was_seen = {a.id: a.seen for a in lm.actors}
        hunter = move_actors(self, lm)
        if hunter is not None and self.battle is None:
            from realmwalker.game.fight import start_battle
            from realmwalker.rules.combat import PARTY

            name = self.tables.creatures.encounters.get(hunter.group, {}).get("name", "something")
            intro = self.world.rng.child(f"intro/{self.world.time}").choice(self.tables.creatures.encounters[hunter.group]["intro"])
            surprised = None if was_seen.get(hunter.id) else PARTY
            start_battle(self, hunter.creatures, intro, surprised=surprised, actor=hunter,
                         title=name[:1].upper() + name[1:])

    # ------------------------------------------------------------------ items on the ground
    def pick_up(self) -> int:
        lm = self.local
        p = self.player
        if lm is None:
            self.say("There is nothing here to pick up.", "system")
            return 0
        pile = lm.items.pop((p.lx, p.ly), [])
        if not pile:
            self.say("There is nothing here to pick up.", "system")
            return 0
        for item in pile:
            add_existing(self.leader, self.tables.items, item)
            self.say(f"You pick up the <loot>{self.tables.items.name(item)}</>.", "loot")
        self.pass_seconds(LOCAL_STEP_SECONDS)
        self.dirty = True
        return len(pile)

    def drop(self, uid: int, qty: int | None = None) -> bool:
        lm = self.local
        if lm is None:
            self.say("Enter the land around you (>) to put things down; by the roadside they would be lost.", "system")
            return False
        item = remove_item(self.leader, uid, qty)
        if item is None:
            return False
        p = self.player
        lm.items.setdefault((p.lx, p.ly), []).append(item)
        self.say(f"You put down the {self.tables.items.name(item)}.", "info")
        self.dirty = True
        return True

    def remap_for(self, lm: LocalMap) -> np.ndarray:
        """Stored terrain index -> current data terrain index, cached per map."""
        cached = self._remaps.get(lm.key)
        if cached is None or len(cached) != len(lm.terrain_ids):
            cached = terrain_remap(lm, self.tables)
            self._remaps[lm.key] = cached
        return cached

    # ------------------------------------------------------------------ waiting
    def wait(self, minutes: int) -> None:
        if self.busy:
            return
        self.pass_time(minutes)
        if self.over is not None:
            return
        if self.in_local and self.local is not None:
            self._creatures_act(self.local)
        elif not self.in_local:
            self.reveal()
            from realmwalker.game.encounters import roll_encounter

            self.encounter = roll_encounter(self, minutes * 0.5)  # sitting still draws less notice

    # ------------------------------------------------------------------ travel
    def travel_costs(self) -> np.ndarray:
        """Integer cost grid (minutes per tile, 0 = impassable) for path-finding."""
        if self._cost_cache is None:
            B = self.tables.biomes
            hours = B.move_hours[self._biome_remap[self.world.biome]]
            cost = hours * 60.0
            cost = np.where(self.world.river > 0, cost + FORD_MINUTES, cost)
            cost = np.where(self.world.road, DEFAULT_ROAD_HOURS * 60.0, cost)
            passable = B.passable[self._biome_remap[self.world.biome]]
            self._cost_cache = np.where(passable, np.maximum(1, cost), 0).astype(np.int32)
        return self._cost_cache

    def plan_travel(self, dest: tuple[int, int]) -> TravelPlan | None:
        p = self.player
        if dest == (p.x, p.y) or not self.world.in_bounds(*dest):
            return None
        path = tcod.path.path2d(self.travel_costs(), start_points=[(p.x, p.y)], end_points=[dest], cardinal=100, diagonal=141)
        if len(path) < 2:
            return None
        points = [tuple(int(v) for v in pt) for pt in path.tolist()][1:]
        minutes = 0
        x, y = p.x, p.y
        for nx, ny in points:
            step = self.step_minutes(x, y, nx, ny)
            if step is None:
                return None
            minutes += step
            x, y = nx, ny
        return TravelPlan(points, minutes, len(points) * MILES_PER_TILE, dest)

    def travel_step(self) -> bool:
        """Take one step of a planned journey. Returns False when the journey is over."""
        plan = self.travel
        if plan is None or not plan.path:
            self.travel = None
            return False
        nx, ny = plan.path[0]
        ok = self._move_overworld(nx - self.player.x, ny - self.player.y)
        if not ok:
            self.say("Your way is blocked; you stop to find another route.", "warn")
            self.travel = None
            return False
        plan.path.pop(0)
        if self.travel is None:  # interrupted on the way
            return False
        if not plan.path:
            self.say("You have reached your destination.", "good")
            self.travel = None
            return False
        return True

    def describe_plan(self, plan: TravelPlan) -> str:
        walking = duration_text(plan.minutes)
        if plan.minutes <= WALKING_HOURS_PER_DAY * MINUTES_PER_HOUR:
            return f"{plan.miles} miles, about {walking} on foot"
        days = plan.minutes / (WALKING_HOURS_PER_DAY * MINUTES_PER_HOUR)
        return f"{plan.miles} miles: {walking} of walking, about {days:.0f} days at a steady pace"

    # ------------------------------------------------------------------ bookkeeping
    def distance_to(self, x: int, y: int) -> float:
        return math.hypot(x - self.player.x, y - self.player.y)


SEASON_LINES = {
    "spring": "Early spring: the roads are mud and the nights still freeze.",
    "summer": "Summer: long days, short tempers, and fever in the low places.",
    "autumn": "Autumn: harvest, slaughter, and the first frosts.",
    "winter": "Winter: the killing season. Nobody travels who does not have to.",
}


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def default_wanderer(tables: Tables, world: World) -> Character:
    """A ready-made character, for quick starts, tests and saves from before character creation."""
    from realmwalker.rules.creation import CharacterBuilder

    builder = CharacterBuilder(tables, RNG(world.meta.seed, "wanderer"))
    builder.name = "The Wanderer"
    builder.apply_backstory(builder.fallback_backstory("the lowlands"), "built-in")
    return builder.build(world.time)


def new_game(world: World, tables: Tables, character: Character | None = None,
             start_settlement: int | None = None) -> GameState:
    """Start playing: a character (or the default wanderer) at a settlement."""
    rng = world.rng.child("start")
    towns = [s for s in world.settlements if s.kind in ("town", "village")] or world.settlements
    if start_settlement is not None:
        start = world.settlements[start_settlement]
    else:
        start = rng.choice(towns)
    character = character or default_wanderer(tables, world)
    player = PlayerState(name=character.name, x=start.x, y=start.y,
                         explored=np.zeros((world.width, world.height), dtype=bool), home=start.id)
    game = GameState(world, player, tables, party=[character])
    # You know your own district, and have heard of the big towns within a few days' walk.
    for s in world.settlements:
        if s.kind in ("city", "town") and math.hypot(s.x - start.x, s.y - start.y) < 45:
            player.known_settlements.add(s.id)
    xs = np.arange(world.width)[:, None]
    ys = np.arange(world.height)[None, :]
    player.explored |= (xs - start.x) ** 2 + (ys - start.y) ** 2 <= HOME_RADIUS ** 2
    # ...and the roads out of it, as far as the next towns.
    near_roads = world.road & ((xs - start.x) ** 2 + (ys - start.y) ** 2 <= (HOME_RADIUS * 2) ** 2)
    player.explored |= near_roads
    game.reveal()
    m = game.moment
    game.say(f"<title>{m.long_text()}.</> {SEASON_LINES.get(m.season, '')}", "system")
    game._arrive(None)
    game.say("Press <loot>F1</> for help. Arrow keys or the number pad walk; <loot>></> enters the land around you.", "system")
    return game
