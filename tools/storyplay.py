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
        fight.take_loot(g)
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
            while g.local is not None and g.local.kind == "dungeon":
                level = int(g.local.meta.get("level", 1))
                if level <= 1:
                    break
                dungeon.descend(g, level - 1, from_below=True)
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
    a = ap.parse_args()
    results = play(a.runs, a.verbose)
    done = [r for r in results if r.finished]
    gaps = [x for r in results for x in r.gaps()]
    print(f"\nfinished {len(done)} of {len(results)} ({100 * len(done) / max(1, len(results)):.0f}%); "
          f"days median {statistics.median([r.days for r in done]) if done else 0:.1f}; "
          f"gap between story moments median {statistics.median(gaps) if gaps else 0:.1f} h")
    return 0 if len(done) >= 0.9 * len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
