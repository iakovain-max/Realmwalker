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

from realmwalker.core import dice, textgen
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
    discoveries: set[str] = field(default_factory=set)  # "site:<id>", "deeper:<site id>/<level>" (experience given)
    seconds: int = 0  # sub-minute time carried from local-map steps
    steps: int = 0
    pace: str = "normal"  # the travel pace chosen (fast, normal, slow; PHB 2024): the land may hold it back


@dataclass
class TravelPlan:
    path: list[tuple[int, int]]  # overworld tiles, not including the start
    minutes: int
    miles: int
    destination: tuple[int, int]
    riding: bool = False  # everyone rides, and the minutes count it (game/mounts.py)


# "Text detail" in Settings: 0 brief (only what matters), 1 normal, 2 rich (more of the world's voice).
TRADES = ("inn", "store", "smithy", "healer", "stable", "market")
COMING_BACK = (
    "You reach {place} again.",
    "{place} comes up out of the country ahead, and you know the shape of it.",
    "The road brings you back to {place}.",
    "Here is {place} again, no better and no worse.",
    "You come back into {place} by the same road you left by.",
    "{place}, again: the smell of it before the sight of it.",
)
BORDER_SIGNS = (
    "A boundary stone, chipped and grown over, with arms on it that were cut deep and are not deep now.",
    "A gibbet at the roadside, old enough that the cage is empty and the chain has rusted through.",
    "Somebody has painted a device on the end wall of a barn, and repainted it recently.",
    "The field walls change: different stone, laid a different way.",
    "A shrine at the crossroads, swept, with fresh flowers in it.",
    "Two riders sit their horses on the rise and watch you the whole length of the valley.",
    "A toll post, unmanned, with the bar up and nobody minding it.",
    "The road is suddenly better kept, and then it is not.",
    "A cairn with a pole in it, and rags tied to the pole.",
    "The milestone here is new, and the one behind you was not.",
)
NO_LAW = (
    "No lord's law runs here.",
    "Nobody's writ reaches this country.",
    "From here on, whatever happens to you is nobody's business but yours.",
    "There is no lord over this, and no watch in it.",
)
FORDING = ("You wade {river}, waist-deep and numbingly cold, holding your pack over your head.",
           "You find a shallow place and cross {river}, feeling for the bottom with each foot.",
           "{river} comes up to your waist and pulls at you the whole way over.",
           "You cross {river}. The stones underfoot are round and green and want you off them.")
FORDING_COLD = ("You wade {river}. The cold of it goes through you like a nail.",
                "There is ice at the edges of {river}. You cross anyway, and cannot feel your legs at the far side.",
                "{river} is snowmelt to the waist, and it takes your breath away.")
FOUND_LIGHT = ("Dawn comes up grey behind you, and the country makes sense again. You know where you are.",
               "With the light, a hill you know stands up out of the murk. You have your bearings.",
               "Morning finds you, and the land with it: you know which way you are walking now.")
FOUND_CLEAR = ("The weather lifts and the way is plain again.",
               "The murk thins, goes ragged, and blows off. You know where you are.",
               "It clears enough to see a long way, and nothing about it puzzles you any more.")
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
        self.walk_to: tuple[int, int] | None = None  # a spot on this close-up map being walked to (game.wayfinding)
        self.walk_talk: int | None = None  # ...and the townsperson there, when it is them you are walking up to
        self.battle_npcs: dict[int, int] = {}  # creature uid -> townsperson id, while fighting townsfolk
        self.narration: list[dict] = []  # finished travel days waiting to be written up (by the screen)
        from realmwalker.game.reputation import Renown

        self.renown = Renown()  # standing with factions, bounties, crimes, news heard (game.reputation)
        self.arrest: dict | None = None  # the watch has hold of the player (game.law)
        self.sentence: dict | None = None  # the law's punishment, being carried out (game.law)
        self.confined: dict | None = None  # in jail or at hard labour: fed and sheltered, going nowhere
        self.read_board = False  # walked into a notice board (the screen shows it)
        self.sneaking = False  # creeping on a close-up map (z): slower, and seen only by those who beat sneak_roll
        self.sneak_roll = 0  # the party's Stealth roll when they began to creep (the worst of them)
        # Part E.3 (not saved, like a campfire): what divination magic shows on a close-up map (game/divining.mark),
        # the foes slain in the last fight (game/speech: Speak with Dead), and the band being fought.
        self.sensed: list[dict] = []
        self.fresh_dead: dict | None = None
        self.battle_group: str | None = None
        self.let_in: tuple[int, int] | None = None  # (settlement id, day): let through a shut gate tonight
        self.waiting: list[Character] = []  # companions told to wait somewhere (game.companions)
        self.fallen: list[dict] = []  # the bodies of companions the party carries, while a spell could still raise
        # them (game/revival.py)
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
        self.heeded: set[str] = set()  # what a journey has already stopped for (game.journey)
        self.journey_to: tuple[int, int] | None = None  # where an unfinished journey was going
        self.cues: list[str] = []  # sounds asked for by what just happened (see cue(); never saved)

    def cue(self, sound: str) -> None:
        """Something happened that has a sound (a chest opens, a trap goes off): the name of a sound in
        data/sounds.json. The screens play it; the game neither knows nor cares whether anyone heard."""
        self.cues.append(sound)
        del self.cues[:-8]

    # ------------------------------------------------------------------ queries
    @property
    def leader(self) -> Character:
        return self.party[0]

    def sheet(self, char: Character | None = None) -> Sheet:
        return Sheet(char or self.leader, self.tables)

    def travel_pace(self) -> str:
        """The pace the party travels at on the big map: the one chosen, as far as the land allows (DMG 2024 Travel
        Terrain, one step faster on a good road). On a close-up map, always Normal."""
        if self.in_local:
            return "normal"
        from realmwalker.rules import encounter

        p = self.player
        land = self.land_key(p.x, p.y)
        top = encounter.max_pace(self.tables, land, self.tables.biomes.family(land) or land, bool(self.world.road[p.x, p.y]))
        # Mountains and marsh are slow going already (their steps cost more): there the land only forbids Fast.
        return encounter.allowed(p.pace, "normal" if top == "slow" else top)

    def cycle_pace(self) -> str:
        """Slow, Normal, Fast (v): what each does, and whether the land allows it here."""
        from realmwalker.rules import encounter

        order = ["normal", "fast", "slow"]
        p = self.player
        p.pace = order[(order.index(p.pace) + 1) % 3 if p.pace in order else 0]
        now = self.travel_pace()
        what = {"fast": "covering ground quickly, a quarter less time, but noticing less (-5), and easy to lose "
                        "your way and to see",
                "normal": "a steady pace; you notice what you would, but you are no quieter than a walker",
                "slow": "a careful pace: half as long again, but you notice more (+5), keep your bearings better "
                        "and can slip away quietly"}[p.pace]
        held = "" if now == p.pace else (f" <warn>The land here allows no more than "
                                         f"{encounter.pace(self.tables, now)['name']}.</>")
        return f"Travel pace: <good>{encounter.pace(self.tables, p.pace)['name']}</>, {what}.{held}"

    def pace(self) -> float | None:
        """How much slower than an unburdened walker the party moves (None = someone cannot move)."""
        from realmwalker.rules import body, health

        from realmwalker.game import mounts

        from realmwalker.rules import spells as spellrules

        from realmwalker.game import shapeshift
        from realmwalker.rules import shapes

        ridden = mounts.assign(self)[0] if not self.in_local and self.leader.animals else {}
        worst = 0.0
        borne = not self.in_local  # (everyone carried by magic on the big map: quicker than a walker)
        for member in self.party:
            b = body.travel_multiplier(member)
            form = shapeshift.form_of(self, member) if member.alive else None
            if form is not None and b is not None:  # (Animal Shapes, Shapechange: the form's own legs or wings, F.8)
                worst = max(worst, 30.0 / max(5, shapes.speed(self.tables, form)) * b)
                continue
            m = Sheet(member, self.tables).travel_multiplier()
            if m is None or b is None:
                return None
            if borne and not (spellrules.lasting_flag(member, self.tables, "wind")
                              or spellrules.lasting_flag(member, self.tables, "steed")):
                borne = False
            # A rider's lame leg does not slow the party (on the big map, with a mount under them).
            worst = max(worst, m * b * health.travel_multiplier(member, self.tables, riding=id(member) in ridden))
        # A walker's pace at best: the 2024 travel pace does not grow with speed. Only a party borne by magic (Phantom
        # Steeds for everyone, Wind Walk) goes quicker.
        return worst if borne and 0 < worst < 1.0 else max(1.0, worst)

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
        """The kind of land here as the systems know it: its family ('jungle' is 'forest', 'dunes' is 'desert').
        For the land itself (descriptions, pictures, music) ask land_key."""
        B = self.tables.biomes
        return B.families[int(self._biome_remap[self.world.biome[x, y]])]

    def land_key(self, x: int, y: int) -> str:
        """The land itself: 'jungle', 'dunes', 'glacier'..."""
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
        from realmwalker.game import revival
        from realmwalker.game.companions import died

        in_party = [c for c in self.party[1:] if not c.alive]
        self.party = [c for c in self.party if c.alive or c is self.party[0]]
        self.waiting = [c for c in self.waiting if c.alive]
        for c in gone:
            if any(c is x for x in in_party):
                revival.fall(self, c)  # (the body is carried while someone could still raise them)
            elif c.companion:
                died(self, c)

    def pass_time(self, minutes: float, activity: str = "rest") -> None:
        """Advance the world clock; the party lives through it (needs, weather, wounds) in chunks.
        activity: "walk", "rest", "sleep" or "fight"."""
        from realmwalker.game import pack, survival

        pack.sync(self)  # whoever is with the party now shares its pack
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
            if any(c.spells.get("servants") or c.effects.get("kept:mummy_rot") for c in self.party):
                from realmwalker.game import servants

                servants.tick(self)  # (the raised dead: their hold, going free; a mummy's rot)
            if self.over is not None:
                self.world.time += remaining
                break
        self.bury_the_dead()
        if self.fallen:
            from realmwalker.game import revival

            revival.tick(self)
        from realmwalker.game import spellwork

        spellwork.tick(self)  # (magic berries are gone when their day is out)
        from realmwalker.game import allies

        allies.put_in_herd(self)  # (a steed goes and comes with its rider)
        p = self.player
        if not self.in_local and self.party and self.over is None and not self.biome_def(p.x, p.y)["passable"]:
            from realmwalker.game import waymagic

            said = waymagic.ashore(self)  # (a spell that held the party over the water ran out while time passed)
            if said:
                self.say(said, "warn")
        self._weather_moment()
        after = self.moment
        from realmwalker.game import magic_items

        magic_items.tick(self, before, after)  # dawn: charges back; what sentient things want; bonds to lost things
        if any((c.companion or {}).get("coming") for c in self.waiting):  # sent for by messenger (game/passage.py)
            from realmwalker.game.companions import rejoin

            for text in rejoin(self):
                self.say(text, "good")
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
            if self.renown.flags.get("captives"):
                from realmwalker.game.gear import captives_slip

                captives_slip(self)  # prisoners not chained may slip away in the night
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
        over = self.magic_crossing(x1, y1)  # (Wind Walk, Water Walk, Water Breathing: game/waymagic.py)
        if not target["passable"] and over is None:
            return None
        diagonal = x0 != x1 and y0 != y1
        if over in ("wind", "fly"):
            hours = 1.0  # (a cloud on the wind, or wings: every land alike; the pace makes it quicker)
        elif not target["passable"] or not self.biome_def(x0, y0)["passable"]:
            hours = 2.0 if over in ("under", "swim") else 1.0  # (the bottom of a lake, or swimming, is slow going;
            # the water's face is not)
        elif w.road[x0, y0] and w.road[x1, y1]:
            hours = ROAD_HOURS.get(self.biome_key(x1, y1), DEFAULT_ROAD_HOURS)
        else:
            here = self.biome_def(x0, y0)
            hours = (float(here["move_hours"]) + float(target["move_hours"])) / 2.0
            if w.river[x1, y1] and not w.road[x1, y1] and over is None:
                hours += FORD_MINUTES / 60.0
        if diagonal:
            hours *= 1.41
        return max(1, int(round(hours * MINUTES_PER_HOUR)))

    def magic_crossing(self, x: int, y: int) -> str | None:
        """How the party's lasting spells carry it over this tile, if they do: "wind" (Wind Walk: anything), "over"
        (Water Walk: rivers, lakes and the sea), "under" (Water Breathing: a lake's bottom). None: on foot."""
        if not self.party:
            return None
        from realmwalker.game import waymagic

        if waymagic.everyone(self, "wind"):
            return "wind"
        from realmwalker.game import shapeshift
        from realmwalker.rules import shapes

        if shapeshift.all_shaped(self, shapes.flies):
            return "fly"  # (Animal Shapes or Shapechange: everyone on wings, over water and mountains: F.8)
        watery = self.biome_key(x, y) in ("ocean", "lake") or bool(self.world.river[x, y])
        if not watery:
            return None
        if waymagic.everyone(self, "water_walk"):
            return "over"
        if self.biome_key(x, y) != "ocean" and shapeshift.all_shaped(self, shapes.swims):
            return "swim"  # (everyone in a swimmer's shape: rivers and lakes, not the open sea)
        if waymagic.everyone(self, "water_breathing") and self.biome_key(x, y) != "ocean":
            return "under"
        if self.world.river[x, y] and self.biome_key(x, y) not in ("ocean", "lake") and waymagic.anyone(self, "part_water"):
            return "parted"  # (Control Water: the river stands aside, and its bed is crossed dry)
        return None

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
        self.sneaking = False  # creeping is for the close view: on the road nobody creeps
        dx, dy = self._maybe_stray(dx, dy)
        nx, ny = p.x + dx, p.y + dy
        pace = self.pace()
        if pace is None:
            from realmwalker.game.journey import why_cannot_walk

            self.say(why_cannot_walk(self), "warn")
            return False
        minutes = self.step_minutes(p.x, p.y, nx, ny)
        if minutes is not None:
            minutes = int(round(minutes * pace))
        if minutes is None:
            if self.world.in_bounds(nx, ny):
                self.say(f"The {self.biome_def(nx, ny)['name']} bars the way. There is no crossing without a boat.", "warn")
            return False
        crossing = self.magic_crossing(nx, ny)
        fording = (bool(self.world.river[nx, ny]) and not self.world.road[nx, ny] and crossing in (None, "under")
                   or crossing in ("under", "swim"))  # (under a lake's water, or swimming, everyone is soaked; over
        # it, nobody)
        prev_area = self.world.area_at(p.x, p.y)
        x0, y0 = p.x, p.y
        p.x, p.y = nx, ny
        p.steps += 1
        minutes = int(round(minutes * self.weather.travel_factor()))
        if self.travel_pace() != "normal":
            from realmwalker.rules import encounter

            minutes = max(1, int(round(minutes * float(encounter.pace(self.tables, self.travel_pace())["time"]))))
        if self.leader.animals:
            from realmwalker.game import mounts

            minutes = max(1, int(round(minutes * mounts.step_factor(self, x0, y0, nx, ny))))
        self._wading = fording
        self.pass_time(minutes, "walk")
        if self.over is not None:
            return True
        self._log_step(nx, ny)
        if self.party[1:]:
            from realmwalker.game.companions import road_talk

            road_talk(self)
        self._check_bearings()
        if crossing == "under" and not self.world.river[nx, ny]:
            self.say("You walk down into the cold water and along the lake's bottom, breathing it like air, and come "
                     "up again soaked to the skin.", "warn")
        elif crossing == "over":
            self.say("You walk on the water as on a road, dry-shod.", "info")
        elif crossing == "swim" and not self.world.river[nx, ny]:
            self.say("You swim on through the cold water in your borrowed shapes, and climb out soaked.", "warn")
        elif crossing == "swim":
            self.say("You swim the river in your borrowed shapes, and shake yourselves dry on the far bank.", "info")
        elif crossing == "fly" and not self.biome_def(nx, ny)["passable"]:
            self.say(f"You fly over the {self.biome_def(nx, ny)['name']} on borrowed wings.", "info")
        elif crossing == "parted":
            self.say("The river draws back on either side like two walls of glass, and you cross on its wet stones, "
                     "dry-shod.", "info")
        elif fording:
            river = self.world.river_at(nx, ny)
            name = f"the {river.name.removeprefix('the ')}" if river else "a river"
            rng = self.world.rng.child(f"ford/{self.player.steps}")
            cold = self.weather.temp < 4
            line = rng.choice(FORDING_COLD if cold else FORDING).format(river=name)
            self.say(line[:1].upper() + line[1:], "warn")
        self.reveal()
        self._arrive(prev_area)
        if not self.busy and self.survival:
            from realmwalker.game.survival import top_up

            filled = top_up(self)
            if filled:
                self.say(filled, "info")
        if self.over is None:
            from realmwalker.game import waymagic

            ashore = waymagic.ashore(self)
            if ashore:
                self.say(ashore, "warn")
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

        # The day is remembered by the weather that held most of it, not by the last hour's.
        skies = log.setdefault("skies", {})
        skies[self.weather.kind] = skies.get(self.weather.kind, 0) + 1
        sky = max(skies, key=skies.get)
        log["sky"], log["weather"] = sky, KIND_WORDS.get(sky, sky)

    def lost_dc(self) -> int | None:
        """How hard it is to keep your bearings here, or None if there is no danger of getting lost."""
        p = self.player
        w = self.world
        if w.road[p.x, p.y] or w.settlement_at(p.x, p.y) is not None:
            return None
        if self.party:
            from realmwalker.game import waymagic

            if waymagic.anyone(self, "pathfinding") or waymagic.everyone(self, "wind"):
                return None  # (Find the Path knows the way; clouds on the wind see the land laid out below)
        vis = self.weather.visibility
        dark = self.light < 0.3
        from realmwalker.world import wonders

        if "bewilder" in wonders.boons(self.tables, w, p.x, p.y):
            return 14 + (3 if dark else 0)  # the paths of the enchanted wood are never where you left them
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
            if self.lost_dc() is None:  # the light is back, or the weather has cleared
                self.lost = False
                rng = self.world.rng.child(f"found/{self.player.steps}")
                if self.light >= 0.3 and self.weather.visibility >= 0.6:
                    lines = FOUND_LIGHT if self.moment.hour < 9 else FOUND_CLEAR
                else:
                    lines = FOUND_CLEAR
                self.say(rng.choice(lines), "good")
            return
        dc = self.lost_dc()
        if dc is None:
            return
        if self.travel is not None:
            from realmwalker.game.journey import night_unheeded

            if night_unheeded(self):
                return  # a traveller stops at dusk, before the dark (or the storm with it) can lose them (game.journey)
        from realmwalker.rules import encounter

        mode = encounter.pace(self.tables, self.travel_pace()).get("survival", "")  # fast: worse; slow: better
        ok, roll = check(self, "survival", dc, self.bearings_bonus(), tag="lost", mode=mode)
        if not ok:
            self.lost = True
            self.travel = None
            what = "fog" if self.weather.kind == "fog" else ("storm" if self.weather.visibility < 0.6 else "dark")
            self.say(f"{roll} <warn>In the {what} you lose your way.</> You are no longer sure which way you are "
                     f"walking. Find a road, or wait for better light.", "warn")

    def bearings_bonus(self) -> int:
        """Navigator's tools in the pack: a needle that points north in the fog (more for someone taught to use them)."""
        from realmwalker.rules.inventory import carried

        best = 0
        for it in carried(self.party):
            d = self.tables.items.get(it.def_id)
            if d.get("bearings"):
                trained = any(d.get("tool") in c.tools for c in self.party if c.alive)
                best = max(best, int(d["bearings"]) + (self.sheet().proficiency if trained else 0))
            for p in (it.magic or {}).get("props", ()):  # (the Rod of Lordly Might's needle)
                if p.get("kind") == "bearings":
                    best = max(best, int(p.get("value", 0)))
        return best

    def reveal(self) -> None:
        """Mark overworld tiles around the player as explored."""
        p = self.player
        biome = self.biome_key(p.x, p.y)
        radius = {"hills": 5, "mountains": 6, "high_mountains": 8, "forest": 2, "pine_forest": 2}.get(biome, 3)
        if self.light < 0.5:
            radius = max(1, radius - 1)
        elif biome not in ("forest", "pine_forest") and self.party:
            from realmwalker.rules.inventory import carried

            # A spyglass by day, where the trees do not close in: further across the land.
            radius += max((int(self.tables.items.get(it.def_id).get("sight", 0)) for it in carried(self.party)),
                          default=0)
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
                gained, notes = self.discover("region") if p.steps else ("", [])  # not where you were born
                biome = self.biome_def(p.x, p.y)
                desc = self.world.rng.child(f"areadesc{area.id}").choice(biome["descriptions"])
                self.say(f"You enter <place>{area.name}</>. {desc}{gained}", "place")
                for note in notes:
                    self.say(note, "good")
                from realmwalker.game import magic_items

                magic_items.notice(self, "discovery")
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
        if self.world.wonders:
            from realmwalker.world import wonders

            wonders.arrive(self)
        site = self.world.site_at(p.x, p.y)
        if site is not None:
            spec = self.tables.sites["site_types"].get(site.kind, {})
            gained, notes = self.discover("site", f"site:{site.id}") if p.steps else ("", [])
            self.say(f"You come upon <place>{_cap(site.name)}</>. {spec.get('desc', '')}{gained}", "place")
            for note in notes:
                self.say(note, "good")
        if self.world.politics.get("dragons"):
            from realmwalker.game import dragons

            dragons.arrive(self)
        if self.quests:
            from realmwalker.game import quests

            quests.on_arrive(self)

    def discover(self, kind: str, key: str | None = None) -> tuple[str, list[str]]:
        """Experience for finding somewhere new (the design's discovery): a region, a site, a level deeper under the
        ground, each once per character, for everyone in the party (data/rules.json "discovery_xp", times each one's
        level). Returns the note for the line that tells of it (" (+10 experience)") and any level-up messages."""
        if key is not None:
            if key in self.player.discoveries:
                return "", []
            self.player.discoveries.add(key)
        per_level = int(self.tables.rules.get("discovery_xp", {}).get(kind, 0))
        if per_level <= 0:
            return "", []
        from realmwalker.rules.progression import award_xp

        rng = self.world.rng.child(f"discovery/{kind}/{self.player.steps}")
        notes: list[str] = []
        for c in self.party:
            if c.alive:
                notes += award_xp(c, per_level * c.level, self.tables, rng)
        return f" <dim>(+{per_level * self.leader.level} experience)</>", notes

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
                rng = self.world.rng.child(f"nolaw/{p.steps}")
                self.say(f"You leave the lands of {before.name}. <dim>{rng.choice(NO_LAW)}</>", "place")
            return
        from realmwalker.game.reputation import know

        know(self, lord.id)
        top = fx.top_liege(self.world, lord)
        sign = ""
        if self.flavour(1):
            rng = self.world.rng.child(f"border/{lord.id}/{p.steps}")
            sign = rng.choice(BORDER_SIGNS) + " "
        if top is not None and top is not lord:
            know(self, top.id)
            self.say(f"{sign}You cross into the lands of {lord.name}, <dim>sworn to {top.name}.</>", "place")
        else:
            self.say(f"{sign}You cross into the lands of {lord.name}.", "place")

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
            if not self.flavour(1):
                return f"You reach <place>{s.name}</> again."
            rng = self.world.rng.child(f"return/{s.id}/{self.player.steps}")
            return rng.choice(COMING_BACK).format(place=f"<place>{s.name}</>")
        culture = self.tables.cultures.adjective(self.world, s.culture)
        souls = f"about {round(s.population, -1 if s.population < 1000 else -2):,} souls"
        walls = " behind its walls" if s.walled else ""
        return f"You reach <place>{s.name}</>, {textgen.a_or_an(kind)} of {souls}{walls}. <dim>{culture} folk live here.</>"

    # ------------------------------------------------------------------ local maps
    # ------------------------------------------------------------------ after dark
    def toggle_sneak(self) -> str:
        """Begin or stop creeping on a close-up map. Beginning rolls the party's Stealth once: the worst of them,
        at a disadvantage in armour that clanks. Anyone who might see you must beat it with their Perception."""
        if self.sneaking:
            self.sneaking = False
            return "You stop creeping and walk upright."
        if not self.in_local:
            return "You can only creep about on foot, in the close view (> first)."
        rng = self.world.rng.child(f"sneak/{self.player.steps}")
        worst = None
        for c in self.party:
            if not c.alive:
                continue
            armor = c.equipped_item("armor")
            from realmwalker.rules import magic

            clanks = armor is not None and bool(self.tables.items.get(armor.def_id).get("stealth_disadvantage")) \
                and not magic.item_flag(armor, "mithral") or self.sheet(c).armour_disadvantage("dex")
            if c.attuned:
                from realmwalker.rules import magic

                clanks = clanks or magic.flag(c, "stench")  # an artifact's sour stink
            from realmwalker.rules.engine.handlers import domains

            soft = domains.blessed(c)  # (the Trickster's blessing: soft feet)
            roll = dice.d20(rng, advantage=soft, disadvantage=clanks).natural + self.sheet(c).skill_bonus("stealth")
            if worst is None or roll < worst[0]:
                worst = (roll, c, clanks)
        roll, c, clanks = worst
        self.sneaking, self.sneak_roll = True, roll
        who = "" if len(self.party) == 1 else f" {c.name.split()[0]}'s is the worst."
        armour = " Armour that clanks makes it harder." if clanks else ""
        return (f"You keep low and move quietly. <dice>(Stealth {roll}.{who}{armour})</> "
                f"<dim>Slower going; z to stop.</>")

    def gate_shut(self) -> bool:
        """A walled town or city shuts its gates from nightfall until dawn, unless you have been let in tonight."""
        s = self.world.settlement_at(self.player.x, self.player.y)
        if s is None or not s.walled or s.kind not in ("town", "city") or self.in_local:
            return False
        if self.moment.part_of_day(self.latitude) not in ("night", "before dawn"):
            return False
        return self.let_in != (s.id, self._night_of())

    def _night_of(self) -> int:
        """Which night it is: the day it began (the hours after midnight belong to the evening before)."""
        return (self.world.time - 12 * 60) // (24 * 60)

    def minutes_to_dawn(self) -> int:
        m = self.moment
        sunrise, _ = m.sun_times(self.latitude)
        return int(round(((sunrise - 0.5 - m.fractional_hour) % 24) * 60))

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
            if lm.kind == "settlement" and where.walled and where.kind in ("town", "city"):
                toll = int(self.tables.economy["services"].get("toll", 0)) * len([c for c in self.party if c.alive])
                if toll and self.leader.money >= toll:  # (PHB 2024: a road or gate toll, 1 cp a head)
                    self.leader.money -= toll
                    from realmwalker.rules.items import money_text

                    self.say(f"The gate warden takes the toll: {money_text(toll)}.", "dim")
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
                from realmwalker.game.followers import arrive_town

                arrive_town(self, lm, where)  # the homeless of places nearby, and those who have heard of you
                for text in self.settlement_troubles(where):
                    self.say(text, "warn")
                if not town.seen and town.description:
                    from realmwalker.core.textgen import escape_markup

                    self.say(escape_markup(town.description), "flavor")
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
            self.say("You are underground. Find the stairs up first.", "system")
            return
        here = self.world.settlement_at(self.player.x, self.player.y)
        if here is not None:
            self.let_in = (here.id, self._night_of())  # the wardens have seen you go out: they will let you back in
        self.player.local_key = None
        self.sneaking = False
        self.say("You return to the road and the wider land.", "flavor")
        self.dirty = True

    def _move_local(self, dx: int, dy: int) -> bool:
        lm = self.local
        p = self.player
        if lm is None:
            p.local_key = None
            return False
        if lm.kind == "dungeon" and self.party:
            from realmwalker.game import waymagic

            out = waymagic.shunted(self)  # (Etherealness ended while you stood inside the stone)
            if out:
                self.say(out, "danger")
                return True
        nx, ny = p.lx + dx, p.ly + dy
        if not lm.in_bounds(nx, ny):
            if any(a.alert for a in lm.actors):
                self.say("You break away and leave them behind.", "warn")
            self.leave_local()
            return True
        from realmwalker.game.encounters import actor_at
        from realmwalker.game.people import npc_at

        npc = npc_at(self, nx, ny)
        if npc is not None:  # you squeeze past (talking is t, Enter or a click: game/townlife.py)
            from realmwalker.game import townlife

            if not townlife.squeeze(self, npc):
                who = npc.label()
                why = "is asleep" if townlife.asleep(self, npc) else "does not stand aside"
                self.say(f"{who[:1].upper() + who[1:]} {why}.", "system")
                return False
        target = actor_at(lm, nx, ny)
        if target is not None and lm.kind == "dungeon":
            from realmwalker.game import waymagic

            if waymagic.ethereal_here(self):
                self.say("They cannot see you, and your hands pass through them like smoke (Etherealness).", "system")
                return False
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
            from realmwalker.game.journey import why_cannot_walk

            self.say(why_cannot_walk(self), "warn")
            return False
        T = self.tables.terrain
        t = int(self.remap_for(lm)[lm.terrain[nx, ny]])
        tid = T.ids[t]
        if self.tables.terrain.has_tag(t, "notice_board"):
            self.read_board = True
            return True
        if lm.kind == "dungeon" and (tid in ("chest", "sarcophagus") or not T.walk[t]):
            from realmwalker.game import waymagic

            if waymagic.ethereal_here(self):
                if tid in ("chest", "sarcophagus"):
                    self.say("Your hand passes through it like smoke: nothing on this side can be touched while you "
                             "walk the grey (Etherealness).", "system")
                    return False
                p.lx, p.ly = nx, ny  # (walls and doors do not stop the ethereal)
                p.steps += 1
                self.pass_seconds(int(LOCAL_STEP_SECONDS * 2 * pace), "walk")
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
        if now_building is not None and now_building is not before_building:
            if self.world.factions:
                from realmwalker.game import law

                law.trespass_check(self, lm.buildings.index(now_building))
            self._walk_in(lm, now_building)
        creep = 2.0 if self.sneaking else 1.0
        self.pass_seconds(int(LOCAL_STEP_SECONDS * float(T.cost[t]) * (1.41 if dx and dy else 1.0) * pace * creep), "walk")
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
            elif lm.kind == "dungeon":
                self._underground(lm)
            if self.world.factions and lm.kind == "settlement":
                from realmwalker.game import law

                law.watch(self)
        return True

    def _walk_in(self, lm, building) -> None:
        """Stepping into the common room of an inn: what the place is like, once per inn."""
        if lm.kind != "settlement" or building.kind != "inn" or self.busy or not self.flavour():
            return
        s = self.world.settlement_at(self.player.x, self.player.y)
        town = self.world.towns.get(s.id) if s is not None else None
        if town is None:
            return
        from realmwalker.game.town_words import taproom

        bi = lm.buildings.index(building)
        seen = town.flags.setdefault("taprooms_seen", [])
        if bi in seen:
            return
        seen.append(bi)
        name = town.names.get(bi, "")
        text = taproom(self, town, bi)
        self.say((f"<place>{name}</>: " if name else "") + text, "flavor")

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

    def _underground(self, lm: LocalMap) -> None:
        """Now and then, something the dark does while you are walking through it."""
        seeing = bool(self.lit) or (self.party and self.sheet().darkvision)
        if self.busy or not self.flavour() or not seeing:
            return
        steps = self.player.steps
        if steps - int(self._last_moment) < (12 if self.flavour(2) else 20):
            return
        rng = self.world.rng.child(f"under/{lm.key}/{steps}")
        if not rng.chance(0.2):
            return
        moments = self.tables.sites.get("dungeon_moments", {})
        lines = list(moments.get("any", [])) + list(moments.get(lm.meta.get("style", ""), []))
        if not lines:
            return
        self._last_moment = steps
        self.say(rng.choice(lines), "flavor")

    def _people_act(self, lm: LocalMap) -> None:
        if lm.kind != "settlement":
            return
        from realmwalker.game.people import update_positions

        update_positions(self, lm)

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
        self.cue("pickup")
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

    # ------------------------------------------------------------------ the town's clock
    def town_tick(self) -> bool:
        """One step of a town's own time (the game screen's town clock, while you stand and watch): the world moves
        on a few seconds, and its people with it. False (and nothing happens) anywhere but a town's close-up map, or
        while something is going on."""
        lm = self.local
        if lm is None or lm.kind != "settlement" or self.busy or self.over is not None:
            return False
        from realmwalker.game import townlife

        self.pass_seconds(townlife.STEP_SECONDS, "rest")
        if self.over is None and self.local is lm:
            self._creatures_act(lm)
            self._people_act(lm)
        return True

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
        from realmwalker.game import mounts

        riding = bool(self.leader.animals) and mounts.all_mounted(self)
        minutes = 0.0
        x, y = p.x, p.y
        for nx, ny in points:
            step = self.step_minutes(x, y, nx, ny)
            if step is None:
                return None
            minutes += step * (mounts.step_factor(self, x, y, nx, ny) if riding else 1.0)
            x, y = nx, ny
        return TravelPlan(points, int(round(minutes)), len(points) * MILES_PER_TILE, dest, riding=riding)

    def travel_step(self) -> bool:
        """Take one step of a planned journey. Returns False when the journey is over."""
        plan = self.travel
        if plan is None or not plan.path:
            self.travel = None
            return False
        from realmwalker.game import journey

        self.journey_to = plan.destination
        nx, ny = plan.path[0]
        ok = self._move_overworld(nx - self.player.x, ny - self.player.y)
        if not ok:
            if self.pace() is not None:  # (otherwise the reason has been given already)
                self.say("Your way is blocked; you stop to find another route.", "warn")
            self.travel = None
            return False
        plan.path.pop(0)
        if self.travel is None:  # interrupted on the way
            return False
        if not plan.path:
            self.say("You have reached your destination.", "good")
            self.travel = None
            self.journey_to = None
            return False
        why = journey.reason_to_stop(self, nearly_there=len(plan.path) <= 1)
        if why is not None:
            self.travel = None
            self.say(f"<warn>You stop.</> {why} <dim>(r: make camp · t, Enter: go on)</>", "warn")
            return False
        return True

    def set_out(self, plan: TravelPlan) -> None:
        """Begin a journey. What is already wrong (the dark, a limp) was seen before setting out."""
        from realmwalker.game import journey

        journey.begin(self)
        self.travel = plan
        self.journey_to = plan.destination

    def describe_plan(self, plan: TravelPlan) -> str:
        walking = duration_text(plan.minutes)
        if plan.minutes <= WALKING_HOURS_PER_DAY * MINUTES_PER_HOUR:
            return f"{plan.miles} miles, about {walking} {'in the saddle' if plan.riding else 'on foot'}"
        days = plan.minutes / (WALKING_HOURS_PER_DAY * MINUTES_PER_HOUR)
        days = "a day" if days < 1.25 else "a day and a half" if days < 1.75 else f"{round(days)} days"
        return f"{plan.miles} miles: {walking} of {'riding' if plan.riding else 'walking'}, about {days} at a steady pace"

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
    """A ready-made character, for quick starts and tests."""
    from realmwalker.rules.creation import CharacterBuilder

    builder = CharacterBuilder(tables, RNG(world.meta.seed, "wanderer"))
    # A real name: "The Wanderer" reads badly in the middle of a sentence ("The is cold", "Survival (The)").
    builder.apply_backstory(builder.fallback_backstory("the lowlands"))
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
    game.say("Press <loot>F1</> for help. Arrow keys, the number pad or a click walk; <loot>Enter</> goes into the land "
             "around you. Every action is also a button along the bottom, and a right click on the map says what "
             "you can do there.", "system")
    game.say("Walk into a town, talk to the people in it, and ask <loot>\"Is there any work?\"</> — that is how you "
             "start. <loot>j</> is your journal.", "system")
    return game
