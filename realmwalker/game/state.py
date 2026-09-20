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


# "Text detail" in Settings: 0 brief (only what matters), 1 normal, 2 rich (more of the world's voice).
TRADES = ("inn", "store", "smithy", "healer", "stable", "market")
VERBOSITY = {"brief": 0, "normal": 1, "rich": 2}
WEATHER_NEWS = ("fog", "drizzle", "rain", "storm", "flurries", "snow", "blizzard", "heat")


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
        self.talk_to: int | None = None  # a townsperson the player has just walked up to (the screen opens a talk)
        self.battle_npcs: dict[int, int] = {}  # creature uid -> townsperson id, while fighting townsfolk
        self.narration: list[dict] = []  # finished travel days waiting to be written up (by the screen)
        from realmwalker.game.reputation import Renown

        self.renown = Renown()  # standing with factions, bounties, crimes, news heard (game.reputation)
        self.arrest: dict | None = None  # the watch has hold of the player (game.law)
        self.sentence: dict | None = None  # the law's punishment, being carried out (game.law)
        self.confined: dict | None = None  # in jail or at hard labour: fed and sheltered, going nowhere
        self.read_board = False  # walked into a notice board (the screen shows it)
        self.waiting: list[Character] = []  # companions told to wait somewhere (game.companions)
        self.lit: dict | None = None  # the torch or lantern burning underground (game.dungeon)
        self.quests: list[dict] = []  # work taken on: the journal (game.quests)
        self._last_moment = -10**6  # the step count when street life was last remarked on
        self._last_weather: str | None = None  # the sky as it was, to notice when it turns
        self.verbosity = "normal"  # set from the player's settings by the game screen
        self._weather_said = -10**6  # world minute of the last remark about the sky
        self._realm_here: int | None = None
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
    def flavour(self, need: int = 1) -> bool:
        """Is the player's 'Text detail' setting at least this high? (1 normal, 2 rich.)"""
        return VERBOSITY.get(self.verbosity, 1) >= need

    def bury_the_dead(self) -> None:
        """Nobody dead travels with you: whatever killed them, they leave the party and the waiting."""
        if self.over is not None or self.battle is not None:
            return
        gone = [c for c in list(self.party[1:]) + list(self.waiting) if not c.alive]
        if not gone:
            return
        from realmwalker.game.companions import died

        self.party = [c for c in self.party if c.alive or c is self.party[0]]
        self.waiting = [c for c in self.waiting if c.alive]
        for c in gone:
            if c.companion:
                died(self, c)

    def pass_time(self, minutes: float, activity: str = "rest") -> None:
        """Advance the world clock; the party lives through it (needs, weather, wounds) in chunks.
        activity: "walk", "rest", "sleep" or "fight"."""
        from realmwalker.game import survival

        whole = int(minutes)
        if whole <= 0:
            return
        if self.lit and self.local is not None and self.local.kind == "dungeon":
            from realmwalker.game import dungeon

            dungeon.burn(self, whole)
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
        self.bury_the_dead()
        self._weather_moment()
        after = self.moment
        if self.world.factions and after.total_days * 24 + after.hour != before.total_days * 24 + before.hour:
            from realmwalker.game import law

            law.tick(self)
        if after.total_days != before.total_days:
            if self.world.factions:
                from realmwalker.game import news, reputation
                from realmwalker.world import politics

                if getattr(self, "politics_live", True):
                    politics.tick(self.world, self.tables)
                reputation.tick(self)
                if self.party[1:] or self.waiting:
                    from realmwalker.game import companions

                    companions.daily(self)
            if self.quests:
                from realmwalker.game import quests

                quests.daily(self)
                here = self.world.settlement_at(self.player.x, self.player.y)
                if here is not None and here.status.get("plague") and self.survival:
                    from realmwalker.rules import health

                    rng = self.world.rng.child(f"plague-day/{self.world.time}")
                    for c in self.party:
                        if rng.chance(0.15):
                            health.expose(c, self.tables, "plague", rng)
                news.prune(self.world)
            if self.leader.animals:
                from realmwalker.game.services import feed_animals

                for text in feed_animals(self):
                    self.say(text, "warn")
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
                or self.over is not None or self.event is not None or self.arrest is not None
                or self.sentence is not None)

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
        if self.leader.animals:
            from realmwalker.game.services import riding_factor

            minutes = max(1, int(round(minutes * riding_factor(self))))
        self._wading = fording
        self.pass_time(minutes, "walk")
        if self.over is not None:
            return True
        self._log_step(nx, ny)
        if self.party[1:]:
            from realmwalker.game.companions import road_talk

            road_talk(self)
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
        seen_now = [site for site in self.world.sites
                    if x0 <= site.x < x1 and y0 <= site.y < y1 and not p.explored[site.x, site.y]
                    and circle[site.x - x0, site.y - y0]]
        p.explored[x0:x1, y0:y1] |= circle
        for site in seen_now[:1]:  # one landmark at a time: the rest are on the map
            self._landmark(site)
        # Settlements announce themselves from a little further (smoke, bells, roads).
        for s in self.world.settlements:
            if abs(s.x - p.x) <= radius + 2 and abs(s.y - p.y) <= radius + 2:
                p.known_settlements.add(s.id)

    def _landmark(self, site) -> None:
        """Something man-made or old, seen from a distance: it goes on the map, and you are told."""
        from realmwalker.game.events import compass

        p = self.player
        dx, dy = site.x - p.x, site.y - p.y
        if dx == 0 and dy == 0:
            return  # you are standing on it; arriving says its name
        miles = int(round(math.hypot(dx, dy) * MILES_PER_TILE))
        from realmwalker.core.textgen import a_or_an

        spec = self.tables.sites["site_types"].get(site.kind, {})
        what = a_or_an(spec.get("name", site.kind))
        far = "on the skyline" if miles >= 15 else "away"
        self.say(f"<place>{what[:1].upper() + what[1:]}</>, {far} to the {compass(dx, dy)}, about {miles} miles off.",
                 "place")

    def _arrive(self, prev_area) -> None:
        p = self.player
        area = self.world.area_at(p.x, p.y)
        if area is not None and area is not prev_area:
            first = area.id not in p.visited_areas
            p.visited_areas.add(area.id)
            if first:
                from realmwalker.game.describe import area_text

                written = area_text(self.world, area)
                if written:
                    self.say(f"You enter <place>{area.name}</>. <ai>{written}</>", "place")
                else:
                    biome = self.biome_def(p.x, p.y)
                    desc = self.world.rng.child(f"areadesc{area.id}").choice(biome["descriptions"])
                    self.say(f"You enter <place>{area.name}</>. {desc}", "place")
                if self.party[1:]:
                    from realmwalker.game.companions import react

                    react(self, "discovery", quiet=True)
            elif area.id not in self._recent_areas:
                self.say(f"You are back in <place>{area.name}</>.", "place")
            # Walking along a border should not repeat the same announcement every step.
            self._recent_areas = ([area.id] + [a for a in self._recent_areas if a != area.id])[:4]
        self._check_realm()
        if self.waiting:
            from realmwalker.game.companions import rejoin

            for text in rejoin(self):
                self.say(text, "good")
        s = self.world.settlement_at(p.x, p.y)
        if s is not None:
            from realmwalker.game.reputation import learn_place

            first = s.id not in p.visited_settlements
            p.visited_settlements.add(s.id)
            p.known_settlements.add(s.id)
            self.say(self.settlement_arrival_text(s, first), "place")
            learn_place(self, s, quiet=False)
        site = self.world.site_at(p.x, p.y)
        if site is not None:
            spec = self.tables.sites["site_types"].get(site.kind, {})
            self.say(f"You come upon <place>{_cap(site.name)}</>. {spec.get('desc', '')}", "place")
        if self.world.politics.get("dragons"):
            from realmwalker.game import dragons

            dragons.arrive(self)
        if self.quests:
            from realmwalker.game import quests

            quests.on_arrive(self)

    def _check_realm(self) -> None:
        """Crossing a border: say whose lands these are."""
        from realmwalker.world import factions as fx

        if not self.world.factions:
            return
        p = self.player
        lord = fx.lord_at(self.world, p.x, p.y)
        here = lord.id if lord is not None else -1
        if self._realm_here is None:
            self._realm_here = here
            return
        if here == self._realm_here:
            return
        before = self.world.factions.get(self._realm_here)
        self._realm_here = here
        if lord is None:
            if before is not None:
                self.say(f"You leave the lands of {before.name}. <dim>No lord's law runs here.</>", "place")
            return
        from realmwalker.game.reputation import know

        know(self, lord.id)
        top = fx.top_liege(self.world, lord)
        if top is not None and top is not lord:
            know(self, top.id)
            self.say(f"You cross into the lands of {lord.name}, <dim>sworn to {top.name}.</>", "place")
        else:
            self.say(f"You cross into the lands of {lord.name}.", "place")

    def settlement_troubles(self, s) -> list[str]:
        """Siege, sack, fire, plague and hunger, as you see them walking in. Plague may follow you out."""
        from realmwalker.world import factions as fx

        out = []
        st = s.status
        if st.get("siege"):
            by = self.world.factions.get(st["siege"].get("by", -1))
            out.append(f"<danger>{s.name} is under siege{' by ' + by.name if by else ''}.</> Soldiers' fires ring the "
                       f"walls, and food is dear inside them.")
        if st.get("sacked") is not None:
            out.append(f"<danger>{s.name} was sacked not long ago.</> Burned roofs, fresh graves, and people who look "
                       f"at strangers with hate.")
        if st.get("burned") is not None:
            out.append(f"<warn>Much of {s.name} has been burned.</> What is left huddles among the black beams.")
        if st.get("tribute"):
            out.append(f"<danger>{s.name} pays tribute to {st['tribute']}.</> Cattle are driven up the mountain "
                       f"roads, and nobody looks at the sky for long.")
        if st.get("raided"):
            out.append(f"<warn>{s.name} was raided days ago.</> The people are frightened and angry.")
        if st.get("famine"):
            out.append("<warn>There is hunger here.</> Bread costs what meat should, and the children are thin.")
        if st.get("plague"):
            out.append(f"<danger>Plague is in {s.name}.</> Doors are marked with chalk, and the dead-carts go by.")
            from realmwalker.rules import health

            rng = self.world.rng.child(f"plague/{s.id}/{self.world.time}")
            for c in self.party:
                if rng.chance(0.2):
                    health.expose(c, self.tables, "plague", rng)
        realm = fx.realm_of_settlement(self.world, s) if self.world.factions else None
        if realm is not None and not out:
            from realmwalker.world.politics import at_war

            if at_war(self.world, realm.id):
                out.append(f"<dim>{realm.name[:1].upper() + realm.name[1:]} is at war; there are more soldiers "
                           f"about than usual, and fewer young men.</>")
        return out

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
        site = self.world.site_at(p.x, p.y)
        if site is not None and lm.kind != "settlement":
            from realmwalker.world.dungeon import add_entrance

            add_entrance(self.tables, lm)
        where = self.world.settlement_at(p.x, p.y)
        if where is not None:
            from realmwalker.game.people import populate_town, update_positions

            self.say(f"You walk into <place>{where.name}</>.", "place")
            if lm.kind == "settlement" and self.world.factions:
                from realmwalker.game import law

                for text in law.gate_search(self, where):
                    self.say(text, "warn")
            if lm.kind == "settlement":
                town = populate_town(self, lm, where)
                update_positions(self, lm)
                if self.world.factions:
                    from realmwalker.game.people import refresh_figures

                    refresh_figures(self, lm, where)
                from realmwalker.game.people import refresh_travellers

                refresh_travellers(self, lm, where)
                for text in self.settlement_troubles(where):
                    self.say(text, "warn")
                if not town.seen and town.description:
                    from realmwalker.core.textgen import escape_markup

                    self.say(("<ai>" if town.description_source == "ai" else "") + escape_markup(town.description)
                             + ("</>" if town.description_source == "ai" else ""), "flavor")
                town.seen = True
        else:
            biome = self.biome_def(p.x, p.y)
            self.say(f"You leave the track and look about you: {biome['name']}.", "flavor")
        self.dirty = True
        return lm

    def leave_local(self) -> None:
        if not self.in_local:
            return
        if self.local is not None and self.local.kind == "dungeon":
            self.say("You are underground. Find the stairs up (<) first.", "system")
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
        from realmwalker.game.people import npc_at

        npc = npc_at(self, nx, ny)
        if npc is not None:
            self.talk_to = npc.id
            return True
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
        if self.tables.terrain.has_tag(t, "notice_board"):
            self.read_board = True
            return True
        if tid in ("door_locked", "chest", "sarcophagus"):
            from realmwalker.game import dungeon

            dungeon.bump(self, nx, ny)
            return True
        if tid == "door_closed":
            lm.terrain[nx, ny] = lm.terrain_ids.index("door_open") if "door_open" in lm.terrain_ids else lm.terrain[nx, ny]
            self.pass_seconds(LOCAL_STEP_SECONDS)
            self.say("You open the door.", "flavor")
            self._shut_for_the_night(lm, nx, ny)
            return True
        if not T.walk[t]:
            return False
        before_building = lm.building_at(p.lx, p.ly)
        p.lx, p.ly = nx, ny
        p.steps += 1
        now_building = lm.building_at(nx, ny)
        if now_building is not None and now_building is not before_building and self.world.factions:
            from realmwalker.game import law

            law.trespass_check(self, lm.buildings.index(now_building))
        self.pass_seconds(int(LOCAL_STEP_SECONDS * float(T.cost[t]) * (1.41 if dx and dy else 1.0) * pace), "walk")
        here = lm.items.get((nx, ny))
        if here:
            names = ", ".join(self.tables.items.name(i) for i in here[:4]) + (" and more" if len(here) > 4 else "")
            self.say(f"Here: <loot>{names}</>. <dim>(g to pick up)</>", "loot")
        if tid in ("stairs_down", "stairs_up") or lm.kind == "dungeon":
            from realmwalker.game import dungeon

            dungeon.on_step(self, nx, ny)
            if self.local is not lm:
                return True
        if self.over is None:
            self._creatures_act(lm)
            self._people_act(lm)
            if lm.kind == "settlement":
                self._street_life(lm)
            if self.world.factions and lm.kind == "settlement":
                from realmwalker.game import law

                law.watch(self)
        return True

    def _shut_for_the_night(self, lm, x: int, y: int) -> None:
        """Trades keep hours. Push a shop door open after dark and a voice answers through it."""
        from realmwalker.game.people import is_day

        if lm.kind != "settlement" or is_day(self):
            return
        b = lm.building_at(x, y)
        if b is None or b.kind not in TRADES:
            return
        rng = self.world.rng.child(f"shut/{self.player.steps}")
        self.say(rng.choice(self.tables.dialogue["closed"]), "flavor")

    def _weather_moment(self) -> None:
        """A line when the weather turns, said outdoors and not more than once a change."""
        if self.busy or self.over is not None or not self.flavour():
            return
        if self.local is not None and self.local.kind == "dungeon":
            return
        kind = self.weather.kind
        if kind == self._last_weather:
            return
        was = self._last_weather
        self._last_weather = kind
        if was is None:
            return  # the weather you started in is not news
        # Cloud thickening and thinning is not news; rain, snow, fog, storms and heat are, and so is their end.
        if kind not in WEATHER_NEWS and was not in WEATHER_NEWS:
            return
        if kind not in WEATHER_NEWS and was in WEATHER_NEWS:
            kind = "clear"
        if self.world.time - int(self._weather_said) < 90:
            return
        lines = self.tables.fallback.get("weather_change", {}).get(kind, [])
        if not lines:
            return
        self._weather_said = self.world.time
        rng = self.world.rng.child(f"weather-say/{self.world.time}")
        self.say(rng.choice(lines), "flavor")

    def _street_life(self, lm: LocalMap) -> None:
        """Now and then, something small happening in the street (game/people.town_moment)."""
        s = self.world.settlement_at(self.player.x, self.player.y)
        if s is None or self.busy or not self.flavour():
            return
        steps = self.player.steps
        if steps - int(self._last_moment) < (15 if self.flavour(2) else 25):  # counted in steps
            return
        rng = self.world.rng.child(f"street/{s.id}/{steps}")  # a new roll each step, not each minute
        if not rng.chance(0.2):
            return
        from realmwalker.game.people import town_moment

        text = town_moment(self, s)
        if text:
            self._last_moment = steps
            self.say(text, "flavor")

    def _people_act(self, lm: LocalMap) -> None:
        if lm.kind != "settlement":
            return
        from realmwalker.game.people import update_positions, wander

        update_positions(self, lm)
        wander(self, lm)

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
        if not pile and lm.kind == "dungeon":
            from realmwalker.game import dungeon

            got = dungeon.take_hoard(self)
            for text in got:
                self.say(text, "loot")
            if got:
                return 1
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
            self._people_act(self.local)
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
    # A real name: "The Wanderer" reads badly in the middle of a sentence ("The is cold", "Survival (The)").
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
    from realmwalker.game.reputation import starting_knowledge

    starting_knowledge(game)
    m = game.moment
    game.say(f"<title>{m.long_text()}.</> {SEASON_LINES.get(m.season, '')}", "system")
    game._arrive(None)
    game.say("Press <loot>F1</> for help. Arrow keys or the number pad walk; <loot>></> enters the land around you.", "system")
    game.say("Walk into a town, talk to the people in it, and ask <loot>\"Is there any work?\"</> — that is how you "
             "start. <loot>j</> is your journal.", "system")
    return game
