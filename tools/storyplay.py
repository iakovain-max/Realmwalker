"""Storyplay (docs/ADVENTURES.md §9): a careful party plays a tale through, on real roads and in real time.

A party of four at the tier's target level (the hero and three companions of the start town) sets out from the town
nearest a beast threat. The bot takes the hook, then does what the journal says, in order: it walks the world map step
by step (the journey stops for the night and the party rests; bands met on the way are fought on Auto), answers each
beat with a sensible choice, talks to the people of the tale where they live, buys what the weakness needs, takes the
choice when it is put, fights the named foe and the finale on the battle's Auto, and reads the epilogue. What it
reports: finished or not, the ending, days, levels, fights, beats seen, and the gaps between story moments (hours).

Part A's measure: the Beast finishes in at least 90% of 20 runs.

    .venv/Scripts/python.exe tools/storyplay.py --runs 20
    .venv/Scripts/python.exe tools/storyplay.py --runs 1 --verbose
"""

from __future__ import annotations

import argparse
import copy
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realmwalker.core.rng import RNG  # noqa: E402
from realmwalker.game import companions, dungeon, fight, story  # noqa: E402
from realmwalker.game.dialogue import Conversation  # noqa: E402
from realmwalker.game.people import npcs_in, prepare_town  # noqa: E402
from realmwalker.game.state import new_game  # noqa: E402
from realmwalker.game.story import beats, cast, forge, places  # noqa: E402
from realmwalker.rules import progression  # noqa: E402
from realmwalker.rules.combat import PARTY  # noqa: E402
from realmwalker.rules.inventory import add_item  # noqa: E402
from realmwalker.world import threats  # noqa: E402
from realmwalker.world.generator import WorldOptions  # noqa: E402

WORLDS = [("Forgeland", 77, "medium"), ("Threatland", 61, "medium"), ("Lawland", 12, "medium")]
PARTY_CLASSES = ("fighter", "cleric", "rogue", "wizard")
MAX_DAYS = 120
MAX_ACTIONS = 400


@dataclass
class Run:
    world: str = ""
    threat: str = ""
    finished: bool = False
    ending: str | None = None
    days: float = 0.0
    levels: int = 0
    fights: int = 0
    beats: list = field(default_factory=list)
    moments: list = field(default_factory=list)  # (the game hour of each story moment)
    why: str = ""
    log: list = field(default_factory=list)

    def gaps(self) -> list[float]:
        return [b - a for a, b in zip(self.moments, self.moments[1:])]


class Player:
    keeps_things = True  # (takes every thing a fight leaves; the earner takes the coin and leaves the weight)

    def __init__(self, game, run: Run, verbose: bool = False) -> None:
        self.game = game
        self.run = run
        self.verbose = verbose

    def note(self, text: str) -> None:
        self.run.log.append(f"day {self.game.world.time / 1440:6.2f}: {text}")
        if self.verbose:
            print(self.run.log[-1])

    def moment(self) -> None:
        self.run.moments.append(self.game.world.time / 60)

    # ------------------------------------------------------------------ what waits
    def settle(self) -> None:
        """Answer whatever waits (a beat, a card, a fight, the finale's card, the epilogue, level-up choices)."""
        g = self.game
        for _ in range(30):
            if g.over is not None:
                return
            if g.battle is not None:
                self.battle()
            elif g.encounter is not None:
                fight.encounter_fight(g, ambush=False)
                self.battle()
            elif g.event is not None:
                self.road_event()
            elif beats.pending(g) is not None:
                self.beat()
            elif beats.director(g.world).get("card"):
                beats.director(g.world)["card"] = None
            elif getattr(g, "finale", None):
                self.note("the finale: Fight")
                self.moment()
                story.fight_finale(g)
                if g.battle is None:
                    g.finale = None
            elif getattr(g, "epilogue", None):
                offered = g.renown.legend.get("offered") or []
                if offered:
                    g.renown.legend["epithet"] = offered[0]
                self.note(f"the epilogue ({len(story.adventures(g.world)[g.epilogue['adv']].get('epilogue', []))} "
                          f"pages)")
                g.epilogue = None
            else:
                break
        for c in g.party:
            if c.pending:
                progression.auto_resolve(c, g.tables)

    def road_event(self) -> None:
        """Something on the road (a flooded ford, a pedlar): the first thing it may do that costs no coin."""
        from realmwalker.game import events

        g = self.game
        ev = g.event
        opts = g.tables.travel_events[ev.event_id]["options"]
        can = [i for i, (_, ok, _) in enumerate(events.options(g, ev)) if ok and "shop" not in opts[i]]
        free = [i for i in can if not opts[i].get("requires", {}).get("money")
                and int((opts[i].get("outcome") or {}).get("money", 0)) >= 0]
        if free or can:
            events.choose(g, ev, (free or can)[0])
            self.note(f"on the road: {ev.event_id}")
        g.event = None

    def beat(self) -> None:
        g = self.game
        rec = beats.pending(g)
        opts = [o for o in beats.choices(g, rec) if o["ok"]]
        prefer = ("hunt it", "quietly", "stake out", "tooth", "look closer", "study it", "stand to the fire",
                  "think back")
        pick = next((o for w in prefer for o in opts if w in o["label"].lower()), None)
        pick = pick or next((o for o in opts if "not now" not in o["label"].lower()), opts[0] if opts else None)
        self.run.beats.append(rec["beat"])
        self.moment()
        self.note(f"beat {rec['beat']}: {pick['label'] if pick else '(none)'}")
        if pick is None or pick["i"] < 0:
            beats.director(g.world)["pending"] = None
            return
        beats.choose(g, rec, pick["i"])

    def battle(self) -> None:
        from tools.arena import run as play_out

        g = self.game
        b = g.battle
        for f in b.side(PARTY):
            f.auto = True
        play_out(b, max_steps=6000)
        self.run.fights += 1
        after = fight.finish_battle(g)
        self.note(f"a fight: {after.outcome}")
        fight.take_loot(g, None if self.keeps_things else [])
        fight.leave_loot(g)
        g.aftermath = None
        g.encounter = None
        if g.over is None:
            self.recover()

    def recover(self) -> None:
        """A careful party rests when it is hurt (a long rest outside a map, a short one in it)."""
        g = self.game
        hurt = any(c.alive and c.hp < c.max_hp * 0.6 for c in g.party)
        if not hurt or g.battle is not None or g.encounter is not None:
            return
        for line in fight.rest(g, "long" if g.local is None else "short"):
            if "can't rest" in line:
                return
        self.settle()

    # ------------------------------------------------------------------ getting about
    def go(self, xy: tuple[int, int]) -> bool:
        """Walk the world map to a tile, stopping for the night and for whatever happens; True when there."""
        g = self.game
        if g.local is not None:
            for _ in range(20):  # (up the stairs, level by level, and out)
                if g.local is None or g.local.kind != "dungeon":
                    break
                dungeon.ascend(g)
            g.leave_local()
        for _ in range(60):
            self.settle()
            if g.over is not None:
                return False
            if (g.player.x, g.player.y) == tuple(xy):
                return True
            plan = g.plan_travel(tuple(xy))
            if plan is None:
                self.run.why = f"no way to {xy}"
                return False
            g.set_out(plan)
            while g.travel is not None and g.travel_step():
                if g.busy:
                    break
            self.settle()
            if g.over is not None:
                return False
            if (g.player.x, g.player.y) != tuple(xy) and g.travel is None and not g.busy:
                for line in fight.rest(g, "night"):
                    pass
                self.settle()
        return (g.player.x, g.player.y) == tuple(xy)

    def town(self, sid: int):
        g = self.game
        s = g.world.settlements[sid]
        if not self.go((s.x, s.y)):
            return None
        prepare_town(g, s)
        return s

    def talk(self, entry: dict, choice_id: str, sid: str) -> bool:
        g = self.game
        if not entry or "settlement" not in entry:
            return False
        if self.town(int(entry["settlement"])) is None:
            return False
        adv = story.active(g)[0]
        who = cast.person(g.world, entry)
        if who is None:
            for st in story.open_steps(adv):
                if st["id"] == sid:
                    entry = st["target"].get("who") or adv["cast"].get(st["target"].get("role", ""), {})
            who = cast.person(g.world, entry)
        if who is None:
            jobs = entry.get("jobs") or [entry.get("job")]
            who = next((n for n in npcs_in(g.world, int(entry["settlement"])) if n.alive and n.job in jobs), None)
        if who is None:
            return False
        conv = Conversation(g, who)
        ch = next((c for c in conv.menu() if c.id == choice_id), None)
        if ch is None:
            return False
        conv.choose(ch)
        self.moment()
        self.note(f"talked with {who.name} ({choice_id})")
        return True

    # ------------------------------------------------------------------ the steps
    def act(self, adv: dict, st: dict) -> None:
        g = self.game
        t, kind = st["target"], st["kind"]
        if kind in ("go", "search"):
            if self.go(places.xy(g.world, t["place"])):
                story.on_arrive(g)
                self.settle()
                if st["state"] == "open" and kind == "search":
                    story.after_beat(g)
                    self.settle()
        elif kind == "witness":
            if not self.talk(t.get("who") or adv["cast"].get(t["role"], {}), "story_witness", st["id"]):
                self.run.why = "the witness could not be found"
        elif kind == "learn":
            for r in sorted(t["routes"], key=lambda r: (r.get("how") != "talk" or r.get("role") != "ally",
                                                           r.get("how") != "check")):
                if r.get("how") == "talk" and self.talk(r.get("who") or {}, "story_learn", st["id"]):
                    break
                if r.get("how") == "check" and self.go(places.xy(g.world, r["at"])):
                    story.on_arrive(g)
                    self.settle()
                    if st["state"] != "open":
                        break
        elif kind == "prepare":
            item = t["means"][0]
            add_item(g.leader, g.tables.items, item, 2)
            price = int(g.tables.items.get(item).get("value", 1)) * 2
            g.leader.money = max(0, g.leader.money - price)
            self.note(f"bought {item}")
            g.pass_time(60, "rest")
            beats.director(g.world)["day"] = -1
            story.daily(g)
        elif kind in ("choose", "slay"):
            for line in fight.rest(g, "long"):
                pass
            if beats.pending(g) is None and g.encounter is None:
                story.on_night(g, "camp")
            self.settle()
        elif kind == "finale":
            self.finale(adv, st)

    def finale(self, adv: dict, st: dict) -> None:
        g = self.game
        site = g.world.sites[adv["places"]["home"]["site"]]
        if not self.go((site.x, site.y)):
            return
        for c in g.party:  # (a careful party goes down rested)
            c.hp = c.max_hp
        g.enter_local()
        depth = dungeon.gen.depth_for(g.world, site)
        dungeon.descend(g, 1)
        while int(g.local.meta.get("level", 1)) < depth:
            dungeon.descend(g, int(g.local.meta["level"]) + 1)
        band = next((a for a in g.local.actors if a.creatures and getattr(a.creatures[0], "story", None)), None)
        if band is None:
            self.run.why = "no boss on the finale's level"
            return
        story.hold_for_finale(g, band)
        self.settle()


# ---------------------------------------------------------------------------- the income measure (§9)
INCOME_DAYS = 30
INCOME_LEVEL = 3
INCOME_REF = Path(__file__).resolve().parents[1] / "tests" / "data" / "income_ref.json"
HONEST = ("deliver", "escort", "clear_lair", "bounty", "hunt_beast", "retrieve", "rescue", "defend")
REACH = 20  # (tiles: the careful player takes work it can walk to and back)
CAREFUL_RATIO = 1.0  # (a beast or a raid worth more than the party's High budget is turned down)


@dataclass
class Earnings:
    world: str = ""
    days: float = 0.0
    total: int = 0  # (the party's purse at the end less at the start, in copper)
    work: int = 0  # (what was paid for work)
    jobs: int = 0
    failed: int = 0
    fights: int = 0
    died: bool = False
    log: list = field(default_factory=list)


class Earner(Player):
    """The careful player of the income measure: it looks at the work waiting in the town it is in (the board's
    bounties, the people's own pleas and commissions: Expansion 6 C.2; contracts and situations as they come), takes
    the honest kind it can walk to (the best pay for the walk), does it (the letter carried, the traveller seen there,
    the place cleared and its chests opened, the beast found, the village stood by), comes back for the money, and
    walks on to the next town when nobody here has any. It counts coin: it takes the money and what the work is
    after, and leaves the rest where it lies."""

    keeps_things = False

    def __init__(self, game, earn: Earnings, verbose: bool = False) -> None:
        super().__init__(game, Run(world=earn.world), verbose)
        self.earn = earn
        self.asked: dict[int, float] = {}  # (settlement -> the day its people were last asked)
        self.end = self.day() + INCOME_DAYS

    def purse(self) -> int:
        return sum(int(c.money) for c in self.game.party)

    def day(self) -> float:
        return self.game.world.time / 1440

    def battle(self) -> None:
        super().battle()
        self.earn.fights += 1

    def settle(self) -> None:
        """As the tale's party does, but a band that would very likely kill it is slipped past if it can be."""
        from realmwalker.game.encounters import DEADLY_RATIO, threat_ratio

        g = self.game
        enc = g.encounter
        if enc is not None and g.battle is None and \
                threat_ratio(g.tables, [c.def_id for c in enc.creatures], [c for c in g.party if c.alive]) \
                >= DEADLY_RATIO:
            self.note(f"slipping past {enc.group}")
            fight.encounter_evade(g)
        super().settle()

    def recover(self) -> None:
        """Hurt, it rests: a long rest anywhere but under the ground, where a short one must do."""
        g = self.game
        if g.battle is not None or g.encounter is not None or g.over is not None:
            return
        if not any(c.alive and c.hp < c.max_hp * 0.9 for c in g.party):
            return
        long = g.local is None or g.local.kind != "dungeon"
        for line in fight.rest(g, "long" if long else "short"):
            if "can't rest" in line:
                return
        self.settle()

    def ask_for_work(self, s) -> dict | None:
        """Look at what waits here (Expansion 6 C.2: the bounties on the board, the pleas and commissions of the
        people who have them, through their own choice); take the best honest piece within reach."""
        from realmwalker.game import quests
        from realmwalker.game.story import work

        g = self.game
        self.asked[s.id] = self.day()
        best, best_worth, best_npc = None, 0.0, None
        for npc, q in work.offers_here(g, s):
            tiles = self.trip_tiles(q, s)
            if q["template"] not in HONEST or tiles is None or tiles > 2 * REACH:
                continue
            group = q["target"].get("group")
            if group in g.tables.creatures.encounters and quests.beast_ratio(g, group) > CAREFUL_RATIO:
                continue  # (a careful party does not stand against what would likely kill it)
            worth = q["reward"] / (4 + tiles)
            if worth > best_worth:
                best, best_worth, best_npc = q, worth, npc
        if best is None:
            return None
        if best_npc is None:
            quests.accept(g, best)  # (a poster taken down from the board)
        else:
            conv = Conversation(g, best_npc)
            own = next((c for c in conv.menu() if c.id == "own_work" and c.data.get("q") == best["id"]), None)
            if own is None:
                return None
            conv.choose(own)
            accept = next((c for c in conv.menu() if c.id == "work_accept"), None)
            if accept is None:
                return None
            conv.choose(accept)
        if best not in g.quests:
            return None
        self.note(f"took {best['template']} from {best['giver_name']} for {best['reward']}")
        return best

    def where(self, q: dict) -> tuple[int, int] | None:
        w, t = self.game.world, q["target"]
        if "site" in t and 0 <= t["site"] < len(w.sites):
            return w.sites[t["site"]].x, w.sites[t["site"]].y
        if "dest" in t and 0 <= t["dest"] < len(w.settlements):
            return w.settlements[t["dest"]].x, w.settlements[t["dest"]].y
        if q["template"] == "defend" and 0 <= t.get("settlement", -1) < len(w.settlements):
            return w.settlements[t["settlement"]].x, w.settlements[t["settlement"]].y
        if "x" in t:
            return int(t["x"]), int(t["y"])
        return None

    def trip_tiles(self, q: dict, s) -> float | None:
        xy = self.where(q)
        if xy is None:
            return None
        one = abs(xy[0] - s.x) + abs(xy[1] - s.y)
        return one if q["template"] in ("deliver", "escort") else 2 * one

    def do(self, q: dict) -> None:
        g = self.game
        t, tpl = q["target"], q["template"]
        xy = self.where(q)
        self.recover()  # (it sets out rested)
        if xy is None or not self.go(xy):
            return
        if g.over is not None:
            return
        if "site" in t:
            self.clear(g.world.sites[t["site"]], q)
        elif tpl == "deliver":
            dest = self.town(int(t["dest"]))
            who = g.world.npcs.get(t.get("npc"))
            if dest is not None and who is not None and who.alive:
                conv = Conversation(g, who)
                ch = next((c for c in conv.menu() if c.id == "deliver_letter"), None)
                if ch is not None:
                    conv.choose(ch)
        elif tpl == "defend":
            s = g.world.settlements[int(t["settlement"])]
            prepare_town(g, s)
            while not q["done"] and q["state"] == "active" and g.over is None and self.day() < self.end and \
                    g.moment.total_days <= int(t.get("when", 0)) + 1:
                self.recover()
                g.pass_time(240, "rest")
                self.settle()
        self.settle()

    def clear(self, site, q: dict) -> None:
        """Down to the bottom, fighting every band met on the way, opening the chests, freeing the captive."""
        from realmwalker.game import quests
        from realmwalker.game.encounters import DEADLY_RATIO, threat_ratio

        g = self.game
        g.enter_local()
        depth = dungeon.gen.depth_for(g.world, site)
        for level in range(1, depth + 1):
            dungeon.descend(g, level)
            lm = g.local
            fought: set[int] = set()
            for _ in range(12):
                band = next((a for a in lm.actors if a.creatures and a.id not in fought), None)
                if band is None or g.over is not None:
                    break
                fought.add(band.id)
                if threat_ratio(g.tables, [c.def_id for c in band.creatures], [c for c in g.party if c.alive]) \
                        >= DEADLY_RATIO:
                    self.note(f"turned back from {band.group}")
                    quests.abandon(g, q)
                    return  # (what waits down here would very likely kill it: the careful party goes home)
                if story.hold_for_finale(g, band):
                    self.settle()
                else:
                    fight.start_battle(g, band.creatures, "You close with them.", actor=band)
                    self.settle()
                if g.over is not None or not any(c.alive and c.hp > 0 for c in g.party):
                    return
                self.recover()
            for pos, f in list(lm.features.items()):
                if f.get("kind") == "chest" and not f.get("opened"):
                    dungeon.open_chest(g, lm, *pos)
                    self.take_work_things(lm)
                elif f.get("kind") == "captive":
                    quests.free_captive(g, lm, *pos)
            if g.over is not None:
                return
        self.settle()

    def take_work_things(self, lm) -> None:
        """From what a chest gave up, only what the work is after (the coin is in the purse already)."""
        from realmwalker.rules.inventory import add_existing

        g = self.game
        pile = lm.items.get((g.player.lx, g.player.ly), [])
        for it in [it for it in pile if any(t.startswith("quest:") for t in it.tags)]:
            pile.remove(it)
            add_existing(g.leader, g.tables.items, it)

    def paid(self, q: dict, gained: int) -> None:
        """Every payment for work, however it comes (a giver's thanks, a traveller at the gate, a letter's reader)."""
        self.earn.work += gained
        self.earn.jobs += 1
        self.note(f"paid {gained} for {q['template']}")

    def turn_in(self, q: dict) -> None:
        g = self.game
        if self.town(int(q["town"])) is None:
            return
        who = g.world.npcs.get(q["giver"])
        if who is None or not who.alive:
            return
        conv = Conversation(g, who)
        ch = next((c for c in conv.menu() if c.id == "quest_turn_in" and c.enabled), None)
        if ch is None:
            return
        conv.choose(ch)

    def next_town(self):
        """The nearest peopled place not asked this week, within reach."""
        g, w = self.game, self.game.world
        here = (g.player.x, g.player.y)
        towns = [s for s in w.settlements if s.population > 0 and self.day() - self.asked.get(s.id, -99) >= 7
                 and abs(s.x - here[0]) + abs(s.y - here[1]) <= REACH and g.plan_travel((s.x, s.y)) is not None]
        return min(towns, key=lambda s: abs(s.x - here[0]) + abs(s.y - here[1]), default=None)


def earn_once(tables, made, label: str, i: int, verbose: bool = False) -> Earnings:
    """Thirty days of a careful party living by its work, from the i-th town of a world."""
    from realmwalker.game import quests

    w = copy.deepcopy(made)
    earn = Earnings(world=label)
    towns = sorted((s for s in w.settlements if s.kind in ("town", "village")), key=lambda s: s.id)
    town = towns[(i * 7) % len(towns)]
    game = new_game(w, tables, start_settlement=town.id)
    game.survival = False
    make_party(game, INCOME_LEVEL, 2000 + i)
    p = Earner(game, earn, verbose)
    start, start_purse = p.day(), p.purse()
    reward = quests.reward

    def counted(game_, q, **kw):  # (every payment for work goes through quests.reward)
        before = p.purse()
        lines = reward(game_, q, **kw)
        p.paid(q, max(0, p.purse() - before))
        return lines

    quests.reward = counted
    try:
        while p.day() < p.end and game.over is None:
            p.settle()
            live = [q for q in quests.active(game) if q["state"] in quests.LIVE and not q.get("adventure")]
            if live:
                q = live[0]
                before = game.world.time
                if q["done"]:
                    p.turn_in(q)
                    if q["state"] in quests.LIVE:  # (nobody to pay: let it go)
                        quests.abandon(game, q)
                else:
                    p.do(q)
                    if not q["done"] and q["state"] == "active" and game.world.time == before:
                        quests.abandon(game, q)  # (the careful player could not do it)
                if q["state"] in ("failed", "abandoned"):
                    earn.failed += 1
                continue
            s = game.world.settlement_at(game.player.x, game.player.y)
            if s is not None and p.day() - p.asked.get(s.id, -99) >= 7:
                prepare_town(game, s)
                if p.ask_for_work(s) is not None:
                    continue
            nxt = p.next_town()
            if nxt is None or not p.go((nxt.x, nxt.y)):
                game.pass_time(24 * 60, "rest")
        p.settle()
    finally:
        quests.reward = reward
    earn.days = p.day() - start
    # (the last job may run a little past the thirtieth day: what was earned is counted at thirty days' rate)
    earn.total = int((p.purse() - start_purse) * INCOME_DAYS / max(INCOME_DAYS, earn.days))
    earn.work = int(earn.work * INCOME_DAYS / max(INCOME_DAYS, earn.days))
    earn.died = game.over is not None
    earn.log = p.run.log
    return earn


def income(runs: int, verbose: bool = False, tables=None) -> list[Earnings]:
    from tests.worlds import cached_world
    from tools.balance import load_tables

    tables = tables or load_tables()
    made = {w: cached_world(WorldOptions(*w), tables) for w in WORLDS}
    out = []
    for i in range(runs):
        w = WORLDS[i % len(WORLDS)]
        e = earn_once(tables, made[w], w[0], i // len(WORLDS), verbose)
        out.append(e)
        print(f"run {i + 1:2d} {e.world:<10} days={e.days:.1f} total={e.total} work={e.work} jobs={e.jobs} "
              f"failed={e.failed} fights={e.fights}{' DIED' if e.died else ''}")
    return out


def income_summary(results: list[Earnings]) -> dict:
    lived = [e for e in results if not e.died]
    return {
        "runs": len(results), "days": INCOME_DAYS, "level": INCOME_LEVEL, "worlds": [w[0] for w in WORLDS],
        "mean_total": round(statistics.mean(e.total for e in results), 1) if results else 0,
        "median_total": statistics.median(e.total for e in results) if results else 0,
        "mean_work": round(statistics.mean(e.work for e in results), 1) if results else 0,
        "mean_jobs": round(statistics.mean(e.jobs for e in results), 2) if results else 0,
        "mean_fights": round(statistics.mean(e.fights for e in results), 2) if results else 0,
        "died": len(results) - len(lived),
        "per_run": [{"world": e.world, "total": e.total, "work": e.work, "jobs": e.jobs, "failed": e.failed,
                     "fights": e.fights, "died": e.died} for e in results],
    }


def income_report(results: list[Earnings], write: bool) -> int:
    import json

    summary = income_summary(results)
    print(f"\nmean income over {INCOME_DAYS} days: {summary['mean_total']} cp (work {summary['mean_work']} cp, "
          f"{summary['mean_jobs']} jobs, {summary['mean_fights']} fights; {summary['died']} died)")
    if INCOME_REF.exists() and not write:
        ref = json.loads(INCOME_REF.read_text(encoding="utf-8"))
        ratio = summary["mean_total"] / max(1, ref["mean_total"])
        print(f"against the reference ({ref['mean_total']} cp, {ref['build']}): {ratio:.2f} (band 0.7-1.3)")
    if write:
        import subprocess

        build = subprocess.run(["git", "log", "-1", "--format=%h %cs"], capture_output=True, text=True,
                               cwd=INCOME_REF.parents[2]).stdout.strip()
        summary = {"_comment": "The income of storyplay's careful player over thirty days on the build before Part C "
                               "of Adventures & Events (C.1; docs/ADVENTURES.md §9, the income measure). Written by "
                               "tools/storyplay.py --income --write; never rewritten after Part C begins.",
                   "build": build, **summary}
        INCOME_REF.parent.mkdir(parents=True, exist_ok=True)
        INCOME_REF.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"kept in {INCOME_REF}")
    return 0


def make_party(game, level: int, seed: int) -> None:
    from tools.balance import make_hero

    g = game
    hero = make_hero(g.tables, PARTY_CLASSES[0], level, seed)
    hero.money = 200
    g.party[0] = hero
    g.player.name = hero.name
    town = g.world.settlement_at(g.player.x, g.player.y)
    prepare_town(g, town)
    folk = [n for n in npcs_in(g.world, town.id) if n.alive and n.present and 16 <= n.age <= 50]
    bond = "sworn"  # (no wage: they came for the hunt)
    rng = RNG(seed, "storyplay/party")
    for i, cls in enumerate(PARTY_CLASSES[1:]):
        if i >= len(folk):
            break
        char = companions.build(g, folk[i], cls, "soldier", level, rng.child(str(i)))
        companions.enlist(g, folk[i], char, bond)


def play_once(tables, made, label: str, i: int, verbose: bool = False, hours: int = 0) -> Run:
    """One life on one world: the i-th beast threat, setting out `hours` into the first day (each run its own dice)."""
    w = copy.deepcopy(made)
    run = Run(world=label)
    found = [t for t in threats.records(w).values() if t["kind"] == "beast" and t["state"] != "ended"]
    if not found:
        run.why = "no beast threat"
        return run
    t = found[i % len(found)]
    run.threat = t["id"]
    town = min((s for s in w.settlements if s.kind in ("town", "village", "hamlet")),
               key=lambda s: threats.distance(w, t, s.x, s.y))
    game = new_game(w, tables, start_settlement=town.id)
    game.survival = False
    if hours:
        game.pass_time(60 * hours, "rest")
    level = int(tables.threats.get("target_level", {}).get(str(t["tier"]), 3))
    make_party(game, level, 1000 + i)
    if t["state"] == "dormant":
        threats.stir(w, tables, t, w.rng.child(f"storyplay/{i}"), day=0)
    p = Player(game, run, verbose)
    beats.director(w)["pending"] = None
    beats.director(w)["scheduled"] = []
    story.offer_hook(game, t, town)
    start_day = game.world.time / 1440
    start_levels = sum(c.level for c in game.party)
    p.settle()
    adv = story.active(game)[0] if story.active(game) else None
    if adv is None:
        run.why = "the hook was not taken (no tale forged)"
        return run
    for _ in range(MAX_ACTIONS):
        p.settle()
        if game.over is not None:
            run.why = "the party died"
            break
        if adv["state"] != "active":
            break
        if game.world.time / 1440 - start_day > MAX_DAYS:
            run.why = f"not done in {MAX_DAYS} days"
            break
        st = next((s for s in story.open_steps(adv) if not s["optional"]), None)
        if st is None:
            run.why = "no open step"
            break
        before = (st["id"], st["state"], game.world.time)
        p.act(adv, st)
        if (st["id"], st["state"]) == before[:2] and game.world.time == before[2] and adv["state"] == "active":
            run.why = run.why or f"stuck at {st['id']} ({st['kind']})"
            break
    p.settle()
    run.ending = adv.get("ending")
    run.finished = adv["state"] != "active" and adv.get("ending") not in (None, "abandoned")
    run.days = game.world.time / 1440 - start_day
    run.levels = sum(c.level for c in game.party if c.alive) - start_levels
    return run


def play(runs: int, verbose: bool = False, tables=None) -> list[Run]:
    from tests.worlds import cached_world
    from tools.balance import load_tables

    tables = tables or load_tables()
    made = {w: cached_world(WorldOptions(*w), tables) for w in WORLDS}
    out = []
    for i in range(runs):
        w = WORLDS[i % len(WORLDS)]
        r = play_once(tables, made[w], w[0], i // len(WORLDS), verbose, hours=i % 24)
        out.append(r)
        print(f"run {i + 1:2d} {r.world:<10} {r.threat:<4} {'FINISHED' if r.finished else 'not done':<9} "
              f"ending={r.ending} days={r.days:.1f} fights={r.fights} beats={len(r.beats)} "
              f"levels+{r.levels} {r.why}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--income", action="store_true", help="the income measure: thirty days of honest work")
    ap.add_argument("--write", action="store_true", help="with --income: keep the result as the reference")
    a = ap.parse_args()
    if a.income:
        return income_report(income(a.runs, a.verbose), a.write)
    results = play(a.runs, a.verbose)
    done = [r for r in results if r.finished]
    gaps = [x for r in results for x in r.gaps()]
    print(f"\nfinished {len(done)} of {len(results)} ({100 * len(done) / max(1, len(results)):.0f}%); "
          f"days median {statistics.median([r.days for r in done]) if done else 0:.1f}; "
          f"gap between story moments median {statistics.median(gaps) if gaps else 0:.1f} h")
    return 0 if len(done) >= 0.9 * len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
