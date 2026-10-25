"""Headless autoplay bot: plays the game with random but sensible input and checks invariants.

    python tools/autoplay.py
    python tools/autoplay.py --turns 10000 --seed 7

Every screen lists sensible keys for the bot (Screen.autoplay_keys); the bot mixes those with
random keys, mouse moves and clicks on real buttons. It fails if the game reports any error,
if an invariant breaks, or if anything is written to errors.log. As milestones add systems,
the invariant checks grow with them.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import string
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tcod.console  # noqa: E402

from realmwalker.app import App  # noqa: E402
from realmwalker.config import AUTOSAVE_CHOICES, FONT_SIZES, VERBOSITY_LEVELS, Settings  # noqa: E402
from realmwalker.core.logs import count_error_lines  # noqa: E402
from realmwalker.rules.character import Sheet  # noqa: E402
from realmwalker.ui.input import KeyEvent, MouseEvent  # noqa: E402

CONSOLE_SIZES = [(80, 30), (100, 34), (120, 45), (192, 54)]
SPECIAL_KEYS = ["up", "down", "left", "right", "enter", "escape", "tab", "backspace", "pageup", "pagedown",
                "home", "end", "f1", "upleft", "downright", "wait"]


@dataclass
class AutoplayReport:
    turns: int = 0
    restarts: int = 0
    errors: list[str] = field(default_factory=list)
    screens: Counter = field(default_factory=Counter)
    save_checks: int = 0
    game_turns: int = 0
    fights: int = 0
    events: int = 0
    talks: int = 0
    crimes: int = 0
    hires: int = 0
    dungeons: int = 0
    quests: int = 0
    quest_trips: int = 0
    battle_turns: int = 0
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = [
            f"Autoplay: {self.turns} turns, {self.restarts} restarts, {self.elapsed:.1f} s",
            f"  screens visited: {dict(self.screens.most_common())}",
            f"  turns inside a game: {self.game_turns}  save/load round trips checked: {self.save_checks}",
            f"  fights started by the bot: {self.fights}  travel events: {self.events}  talks: {self.talks}  "
            f"crimes: {self.crimes}  companions hired: {self.hires}  dungeons: {self.dungeons}  work taken on: "
            f"{self.quests} (visited: {self.quest_trips})  troubles acted on: {getattr(self, 'sits', 0)}  "
            f"turns spent in battle: {self.battle_turns}",
            "  RESULT: " + ("OK" if self.ok else f"FAILED ({len(self.errors)} problems)"),
        ]
        lines += [f"    - {e}" for e in self.errors[:20]]
        return "\n".join(lines)


def _pick_event(app: App, rng: random.Random, console: tcod.console.Console):
    roll = rng.random()
    top = app.top
    if roll < 0.60 and top is not None:
        keys = top.autoplay_keys() or [KeyEvent("escape")]
        return rng.choice(keys)
    if roll < 0.72:
        return KeyEvent(rng.choice(string.ascii_letters + string.digits + " ?.,<>`"))
    if roll < 0.82:
        return KeyEvent(rng.choice(SPECIAL_KEYS))
    if roll < 0.84:
        return KeyEvent(rng.choice(["=", "-"]), ctrl=True)
    if roll < 0.92 and app.regions:
        region = rng.choice(app.regions)
        x = region.x + rng.randrange(max(1, region.w))
        y = region.y + rng.randrange(max(1, region.h))
        kind = rng.choice(["click", "click", "move", "wheel"])
        return MouseEvent(kind, x, y, button=rng.choice(["left", "left", "right"]), dy=rng.choice([-1, 1]))
    return MouseEvent("move", rng.randrange(console.width), rng.randrange(console.height))


def _check_invariants(app: App, report: AutoplayReport, turn: int) -> None:
    def fail(msg: str) -> None:
        if len(report.errors) < 50:
            report.errors.append(f"turn {turn}: {msg}")

    if app.error_count:
        fail(f"the game reported {app.error_count} recovered error(s); see errors.log")
        app.error_count = 0
    if not app.screens:
        fail("screen stack is empty")
    audio = app.audio
    if audio.unknown:
        fail(f"sounds asked for that data/sounds.json does not have: {sorted(audio.unknown)}")
        audio.unknown.clear()
    if audio.bank.problems or audio.problems or audio.music.broken:
        fail(f"sound trouble: {audio.bank.problems[:2]} {audio.problems[:2]} {audio.music.broken}")
        audio.bank.problems.clear()
        audio.problems.clear()
        audio.music.broken = ""
    mood = app.music_mood()
    if mood is not None and mood.split("/")[0] not in audio.library.moods:
        fail(f"music asked for a mood data/music.json does not have: {mood}")
    s = app.settings
    if s.font_size not in FONT_SIZES or s.verbosity not in VERBOSITY_LEVELS or s.autosave_minutes not in AUTOSAVE_CHOICES:
        fail(f"settings out of range: {s}")
    game = app.game
    if game is not None:
        w, p = game.world, game.player
        if getattr(game, "sneaking", False) and not game.in_local:
            fail("creeping about on the overworld")
        if not w.in_bounds(p.x, p.y):
            fail(f"player off the world at {(p.x, p.y)}")
        elif not app.tables.biomes.passable[game._biome_remap[w.biome[p.x, p.y]]]:
            fail(f"player standing in impassable {game.biome_key(p.x, p.y)} at {(p.x, p.y)}")
        if game.in_local:
            lm = game.local
            if lm is None or not lm.in_bounds(p.lx, p.ly):
                fail("player outside the local map")
            else:
                t = int(game.remap_for(lm)[lm.terrain[p.lx, p.ly]])
                if not app.tables.terrain.walk[t]:
                    fail(f"player inside solid {app.tables.terrain.ids[t]} on a local map")
        if any(not d.startswith(("site:", "deeper:", "wonder:")) for d in p.discoveries):
            fail(f"an unknown kind of discovery: {sorted(p.discoveries)[:5]}")
        key = w.meta.id
        last = _LAST_TIME.get(key)
        if last is not None and w.time < last:
            fail(f"time ran backwards: {last} -> {w.time}")
        _LAST_TIME[key] = w.time
        if p.explored.shape != (w.width, w.height):
            fail("explored map has the wrong shape")
        walk = getattr(game, "walk_to", None)
        if walk is not None and (game.local is None or not game.local.in_bounds(*walk)):
            fail(f"walking to {walk}, which is not on this map")
        for member in game.party:
            if not 0 <= member.hp <= member.max_hp:
                fail(f"{member.name} has {member.hp}/{member.max_hp} hit points")
            if member.money < 0:
                fail(f"{member.name} has negative money")
            uids = [it.uid for it in member.inventory]
            if len(uids) != len(set(uids)):
                fail(f"{member.name} has two items with the same id")
            if any(it.qty <= 0 for it in member.inventory):
                fail(f"{member.name} carries an item stack of zero or fewer")
            if any(not 0 <= it.condition <= 100 for it in member.inventory):
                fail(f"{member.name} carries something worn past nothing or mended past new")
            for slot, uid in member.equipped.items():
                it = member.item(uid)
                if it is not None and slot not in app.tables.items.slots_for(it, member):
                    fail(f"{member.name} wears the {app.tables.items.name(it)} where it does not go ({slot})")
            if member.equipped.get("back") is not None and Sheet(member, app.tables).pack_carry() < 0:
                fail(f"{member.name}'s pack carries less than nothing")
            for need in ("hunger", "thirst", "fatigue", "dirt", "wet", "intoxication"):
                value = getattr(member, need)
                if not 0 <= value <= 100:
                    fail(f"{member.name} has {need} {value}")
            if not -100 <= member.body_heat <= 100 or not 0 <= member.blood <= 100:
                fail(f"{member.name} has body heat {member.body_heat} and blood {member.blood}")
            if not 0 <= member.exhaustion <= 6:
                fail(f"{member.name} has exhaustion {member.exhaustion}")
            for w in member.wounds:
                if not 1 <= w.severity <= 3 or not 0 <= w.bleed <= 3 or not 0 <= w.infection <= 100:
                    fail(f"{member.name} has an impossible wound {w}")
            for d in member.diseases:
                if d.get("phase") not in ("incubating", "sick", "dormant", "immune") or d.get("id") not in app.tables.diseases:
                    fail(f"{member.name} has an impossible disease {d}")
            for inj in member.injuries:
                if inj.startswith("lost_") and any(w.part == inj[5:] and w.note not in ("the stump", "cautery")
                                                   for w in member.wounds):
                    fail(f"{member.name} has a new wound on a {inj[5:].replace('_', ' ')} that is not there")
            if ("lost_left_arm" in member.injuries or "lost_right_arm" in member.injuries) and member.equipped.get("off_hand"):
                fail(f"{member.name} holds something in a hand that is gone")
            if any(v < -1e-6 for k, v in member.effects.items() if not k.endswith("_clean")):
                fail(f"{member.name} has an expired timed effect {member.effects}")
            from realmwalker.rules import spells as spellrules

            for sid, hours in spellrules.lasting(member).items():
                if sid not in app.tables.spells or not spellrules.lasts(app.tables, sid) or \
                        hours > int(app.tables.spells[sid]["rounds"]) / spellrules.ROUNDS_PER_HOUR + 1e-6:
                    fail(f"{member.name} has an impossible lasting spell {sid} ({hours} hours)")
            used = member.spells.get("slots_used", []) if member.spells else []
            if any(u > n for u, n in zip(used, spellrules.slots_total(member, app.tables))):
                fail(f"{member.name} has spent more spell slots than they have: {used}")
            if member.spells and spellrules.prepared_count(member, app.tables):
                ready = spellrules.prepared(member, app.tables)
                if len(ready) > spellrules.prepared_count(member, app.tables) \
                        or set(ready) - set(spellrules.preparable(member, app.tables)):
                    fail(f"{member.name} has an impossible list of prepared spells: {ready}")
            from realmwalker.rules.inventory import container_capacity

            for it in member.inventory:
                if it.fill < 0 or it.fill > container_capacity(app.tables.items, it) + 1e-6:
                    fail(f"{member.name}'s {it.def_id} holds {it.fill} pints")
            from realmwalker.rules import progression

            kinds = ("subclass", "asi", "boon", "feat", "style", "spells", "cantrips", "mastery", "option",
                     "expertise", "pick")
            stuck = [p for p in member.pending if p.get("kind") not in kinds
                     or (p.get("kind") not in ("spells", "cantrips", "pick", "expertise", "feat")
                         and not progression.options(member, app.tables, p))]
            if stuck:  # (a spell to copy or pick, a cantrip, a skill may have nothing left: dropped when looked at)
                fail(f"{member.name} has an impossible level-up choice waiting: {stuck}")
            if any(not 1 <= v <= 20 for v in member.abilities.values()):
                fail(f"{member.name} has an ability out of range: {member.abilities}")
            table = app.tables.rules["xp_for_level"]
            earned = min(app.tables.rules["max_level"], sum(1 for need in table if member.xp >= need))
            if member.level != earned:
                fail(f"{member.name} is level {member.level} with {member.xp} experience (should be {earned})")
            equipped = list(member.equipped.values())
            if len(equipped) != len(set(equipped)):
                fail(f"{member.name} wears one item in two places")
            if any(member.item(uid) is None for uid in equipped):
                fail(f"{member.name} has something equipped that is not in the pack")
        lm = game.local
        if lm is not None:
            for pile in lm.items.values():
                if any(it.qty <= 0 for it in pile):
                    fail("an item on the ground has zero quantity")
            walk = app.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
            # A band being fought right now holds its dead until the battle is settled.
            quiet = game.battle is None and game.aftermath is None
            for a in lm.actors:
                if not lm.in_bounds(a.x, a.y) or not walk[a.x, a.y]:
                    fail(f"creatures of {a.group} stand in a wall at {(a.x, a.y)}")
                if not a.creatures and quiet:
                    fail(f"an empty band of {a.group} is on the map")
                if quiet and any(not 0 < c.hp <= c.max_hp for c in a.creatures):
                    fail(f"a creature of {a.group} has impossible hit points")
            if lm.kind == "settlement":
                from realmwalker.game.people import npcs_in, settlement_here

                here = settlement_here(game)
                spots: dict = {}
                town = game.world.towns.get(here.id) if here is not None else None
                for shop in (town.shops.values() if town is not None else []):
                    if shop["coin"] < 0 or any(q < 0 for q in shop["stock"].values()):
                        fail(f"a shop in {here.name} has negative coin or stock")
                for npc in npcs_in(game.world, here.id) if here is not None else []:
                    if not -100 <= npc.disposition <= 100:
                        fail(f"{npc.name} has disposition {npc.disposition}")
                    if npc.alive and npc.present:
                        if not lm.in_bounds(npc.x, npc.y) or not walk[npc.x, npc.y]:
                            fail(f"{npc.name} the {npc.title} stands in a wall at {(npc.x, npc.y)}")
                        if (npc.x, npc.y) in spots:
                            other = spots[(npc.x, npc.y)]
                            fail(f"two townsfolk stand at {(npc.x, npc.y)}: {other.name} the {other.title} "
                                 f"({other.flags.get('stays', '')}) and {npc.name} the {npc.title}")
                        spots[(npc.x, npc.y)] = npc
            burning = (lm.meta or {}).get("fire")
            if burning:  # (nobody ever stands in a fire: game/fire.py)
                if f"{game.player.lx},{game.player.ly}" in burning and game.local is lm:
                    fail(f"you stand on a burning square at {(game.player.lx, game.player.ly)}")
                for (x, y), npc in (spots.items() if lm.kind == "settlement" else ()):
                    if f"{x},{y}" in burning:
                        fail(f"{npc.name} the {npc.title} stands on a burning square at {(x, y)}")
                for a in lm.actors:
                    if f"{a.x},{a.y}" in burning:
                        fail(f"a band of {a.group} stands on a burning square at {(a.x, a.y)}")
        b = game.battle
        if b is not None:
            if b.outcome is None and not b.order:
                fail("a battle is running without a turn order")
            taken = {}
            for f in b.fighters:
                if not 0 <= f.hp <= f.max_hp:
                    fail(f"{f.name} has {f.hp}/{f.max_hp} hit points in battle")
                if f.state not in ("fighting", "fleeing", "down", "dead", "fled", "surrendered"):
                    fail(f"{f.name} is in an unknown state {f.state!r}")
                if f.state in ("fighting", "fleeing", "down", "surrendered"):
                    # On the grid: everyone on the field, on ground that can be stood on (or climbed onto, or swum;
                    # a flier aloft over water and low things), nobody on anybody else unless the rules allow it
                    # (stopped on the way through: Prone; one above the other).
                    fld = b.field
                    for c in f.cells:
                        if not fld.in_bounds(*c) or not (fld.walk[c] or fld.climb[c] or fld.swim[c]
                                                         or (f.z > 0 and fld.fly[c])):
                            fail(f"{f.name} stands in a wall or off the field at {c} in battle")
                        other = taken.get(c)
                        if other is not None and not f.z and not other.z and "prone" not in f.conditions \
                                and "prone" not in other.conditions:
                            fail(f"{f.name} and {other.name} share the square {c} in battle")
                        taken.setdefault(c, f)
                if f.move_left < 0:
                    fail(f"{f.name} has walked further than they could ({f.move_left} feet left)")
                if f.bond is not None and f.bond.get("conc") and f.state in ("fighting", "fleeing"):
                    # (Expansion 3 F.2: a summoned spirit is there only while its caster holds the spell)
                    owner = b.fighter(f.bond["owner"])
                    if (owner.concentration or {}).get("spell") != f.bond.get("spell") or owner.side != f.side:
                        fail(f"{f.name} is on the field, but {owner.name} no longer holds {f.bond.get('spell')}")
                shared = any(str(bf.get("source", "")).startswith("shared_resistance:") for bf in f.buffs)
                if shared and (f.concentration or {}).get("spell") != "summon_dragon":
                    # (Expansion 3 F.3: a draconic spirit's resistance is shared only while its caster holds it)
                    fail(f"{f.name} still shares a draconic spirit's resistance without holding Summon Dragon")
        _check_factions(game, fail)
        _check_threats(game, fail)
        _check_adventures(game, fail)
        _check_law(game, fail)
        _check_quests(game, fail)
        _check_magic(game, fail)
        _check_companions(game, fail)
        _check_history(game, fail, full=turn % 50 == 0)
        if game.travel is not None and game.pace() is None:
            fail("a journey marches on though nobody can walk")
        if not isinstance(getattr(game, "heeded", set()), set):
            fail("what the journey has stopped for is not a set")
        if not game.leader.alive and game.over is None and b is None and game.aftermath is None:
            fail("the leader is dead but the game goes on")
        if game.over is None and any(not c.alive for c in game.party) and b is None and game.aftermath is None:
            fail("a dead companion is still in the party")


def _check_adventures(game, fail) -> None:
    """Expansion 6: every tale points at its threat and real places; a live tale's chapter is open, its live steps
    have targets that exist (or a repair), its cast's people exist or wait for their town; a waiting beat exists; the
    records are JSON-native."""
    import json

    from realmwalker.game import story
    from realmwalker.game.story import cast, places
    from realmwalker.world import threats

    w = game.world
    for aid, adv in w.politics.get("adventures", {}).items():
        if adv["id"] != aid or adv["threat"] not in threats.records(w):
            fail(f"tale {aid} has no threat")
            continue
        if adv["state"] == "active":
            ch = story.chapter(adv)
            if ch is None or ch["state"] != "open":
                fail(f"tale {aid} is under way with no open chapter")
            for name, pl in adv["places"].items():
                if not places.exists(w, pl):
                    fail(f"tale {aid}: its place {name} does not exist")
            for role, entry in adv["cast"].items():
                if "npc" in entry and entry["npc"] not in w.npcs:
                    fail(f"tale {aid}: its {role} is nobody")
                if cast.pending(entry) and not any(r["adv"] == aid and r["role"] == role for r in
                                                   w.politics.get("story_people", {}).get(f"S{entry['settlement']}", [])):
                    fail(f"tale {aid}: its {role} waits for a town that will never give them")
    d = w.politics.get("director") or {}
    if d.get("pending") and d["pending"]["beat"] not in game.tables.beats:
        fail(f"a beat waits that does not exist ({d['pending']['beat']})")
    for key in ("threats", "adventures", "director", "story_sites", "story_people"):
        rec = w.politics.get(key)
        if rec is not None and json.loads(json.dumps(rec)) != rec:
            fail(f"politics[{key!r}] is not JSON-native")


def _check_threats(game, fail) -> None:
    """Expansion 6: every threat points at real places and a real villain; a live one's villain still lives and its
    clock is on a real stage; a doom never takes a settlement to nobody."""
    from realmwalker.world import threats

    w = game.world
    kinds = game.tables.threats.get("kinds", {})
    for tid, t in threats.records(w).items():
        if t["id"] != tid or t["state"] not in threats.STATES or t["kind"] not in kinds:
            fail(f"threat {tid} is broken ({t.get('state')}, {t.get('kind')})")
            continue
        home = t["home"]
        if not (0 <= home.get("site", 0) < len(w.sites) and 0 <= home.get("settlement", 0) < len(w.settlements)):
            fail(f"threat {tid} has a home that does not exist")
        if any(not 0 <= s < len(w.settlements) for s in t["stakes"]):
            fail(f"threat {tid} threatens a settlement that does not exist")
        stage = t["scheme"]["stage"]
        if t["state"] in threats.LIVE:
            if not 0 <= stage < len(kinds[t["kind"]]["stages"]):
                fail(f"threat {tid} is on a stage its scheme does not have ({stage})")
            fig = threats.villain_figure(w, t)
            if fig is not None and not fig.alive:
                fail(f"threat {tid} goes on though its villain is dead")
        elif t["state"] == "ended" and not t.get("outcome"):
            fail(f"threat {tid} ended without an outcome")
    for s in w.settlements:
        if s.population <= 0:
            fail(f"{s.name} has nobody left in it")


def _check_factions(game, fail) -> None:
    """M6: holdings point at living realms, relations are symmetric, standings and bounties are in range."""
    w = game.world
    if not w.factions:
        fail("the world has no factions")
        return
    for s in w.settlements:
        if s.owner >= 0 and (s.owner not in w.factions or w.factions[s.owner].kind not in (
                "kingdom", "noble_house", "free_city", "clan", "highland_clan", "elven_realm")):
            fail(f"{s.name} is held by something that is not a realm ({s.owner})")
    for f in w.factions.values():
        if f.liege == f.id:
            fail(f"{f.name} is its own liege")
        for other, v in f.relations.items():
            if not -100 <= v <= 100 or w.factions.get(other) is None or w.factions[other].relations.get(f.id) != v:
                fail(f"relation between {f.name} and {other} is broken ({v})")
                break
        if f.active and f.leader not in w.figures:
            fail(f"{f.name} has no leader")
        elif f.active and f.kind in ("bandit_gang", "cult") and not w.figures[f.leader].alive:
            fail(f"{f.name} is led by the dead")
    for war in w.wars:
        if war.get("attacker") not in w.factions or war.get("defender") not in w.factions:
            fail(f"a war between factions that do not exist: {war}")
        if war.get("active") and war.get("attacker") == war.get("defender"):
            fail("a faction at war with itself")
    for s in w.settlements:
        if not isinstance(s.status, dict):
            fail(f"{s.name} has a broken status")
        elif s.status.get("siege") and not any(x.get("active") and x.get("siege") and
                                                x["siege"].get("settlement") == s.id for x in w.wars):
            fail(f"{s.name} is besieged by no war")
        if s.population <= 0:
            fail(f"{s.name} has no people left ({s.population})")
    ids = [n["id"] for n in w.news]
    if len(ids) != len(set(ids)):
        fail("two pieces of news share an id")
    if len(w.news) > 500:
        fail(f"news is piling up ({len(w.news)} items)")
    years = [e["year"] for e in w.history]
    if years != sorted(years):
        fail("the history is out of order")
    for f in w.factions.values():
        if f.active and f.leader in w.figures and not w.figures[f.leader].alive:
            fail(f"{f.name} is led by the dead")
    r = game.renown
    if any(not -100 <= v <= 100 for v in r.standing.values()):
        fail(f"a standing is out of range: {r.standing}")
    if any(v < 0 for v in r.bounties.values()):
        fail(f"a negative bounty: {r.bounties}")
    if any(fid not in w.factions for fid in r.known):
        fail("the player knows of a faction that does not exist")


def _check_history(game, fail, full: bool = False) -> None:
    """The lived history (world/ages): what it names exists, lairs hold living beasts, and (now and then, it is long)
    replaying its ledger of who held what gives today's map, however the world has moved on since."""
    w = game.world
    n_s, n_x = len(w.settlements), len(w.sites)
    for e in w.history[-60:]:
        if any(not 0 <= p < n_s for p in e.get("places", ())) or any(not 0 <= x < n_x for x in e.get("sites", ())):
            fail(f"an event names a place that does not exist: {e.get('text', '')[:70]!r}")
            break
        if any(f not in w.factions for f in e.get("factions", ())) or \
                any(h not in w.figures for h in e.get("figures", ())):
            fail(f"an event names someone who does not exist: {e.get('text', '')[:70]!r}")
            break
    for site_id, hid in w.politics.get("lairs", {}).items():
        fig = w.figures.get(hid)
        if fig is None or not fig.alive or not 0 <= int(site_id) < n_x:
            fail(f"a lair ({site_id}) is kept by someone dead or missing")
            break
    if not full:
        return
    holder: dict[int, int] = {}
    for e in w.history:
        for sid, fid in (e.get("data") or {}).get("owners", ()):
            holder[sid] = fid
    for s in w.settlements:
        if holder.get(s.id, -1) != s.owner:
            fail(f"the history's ledger says {s.name} is held by {holder.get(s.id, -1)}, the map by {s.owner}")
            break


def _check_companions(game, fail) -> None:
    """M7: a party of at most five, loyalty in range, companions tied to real townsfolk.
    (One killed in a fight stays in the party until the battle and its aftermath are over.)"""
    settled = game.battle is None and game.aftermath is None and game.over is None
    if settled and any(c.alive and c.inventory is not game.party[0].inventory for c in game.party):
        fail("someone in the party carries apart from the party's one pack")
    worn = [uid for c in game.party if c.alive for uid in c.equipped.values()]
    if len(worn) != len(set(worn)):
        fail("two people in the party wear the same thing")
    if any(c.inventory is game.party[0].inventory for c in getattr(game, "waiting", [])):
        fail("a companion left waiting still carries from the party's pack")
    on_water = not game.in_local and game.party and not game.biome_def(game.player.x, game.player.y)["passable"]
    if on_water and game.magic_crossing(game.player.x, game.player.y) is None:  # (Expansion 3 E.2: water walked on,
        fail("the party stands on open water with no spell to carry it")  # a lake walked under, the wind)
    for c in game.party:  # (E.2: a lasting spell's flags are kept only while it lasts)
        home = (c.spells or {}).get("sanctuary")
        if home is not None and not 0 <= int(home) < len(game.world.settlements):
            fail(f"{c.name}'s sanctuary is no town")
    names = None  # (Expansion 3 E.3: a nightmare waits only for a figure of this world; a bound sapphire's thing is
    for c in game.party:  # remembered by whoever bound it, as it was when taken)
        for uid, rec in ((c.spells or {}).get("summons") or {}).items():
            if not rec.get("name") or rec.get("taken") and not rec.get("item"):
                fail(f"{c.name}'s summons record for {uid} is broken: {rec}")
    for name in (game.renown.flags.get("nightmares") or {}) if getattr(game, "renown", None) else ():
        names = names or {f.name for f in game.world.figures.values()}
        if name not in names:
            fail(f"a nightmare waits for {name}, who is nobody in this world")
    for m in getattr(game, "sensed", []) or []:
        if game.local is not None and m["map"] == game.local.key and not game.local.in_bounds(m["x"], m["y"]):
            fail(f"something sensed is marked off the map: {m}")
    flags = game.renown.flags if getattr(game, "renown", None) else {}  # (Expansion 3 E.4: minds and illusions)
    for nid in flags.get("geased") or []:
        if nid not in game.world.npcs:
            fail(f"a geas binds person {nid}, who is nobody in this world")
    anti = flags.get("antipathy")
    if anti and anti.get("kind") not in game.tables.creatures:
        fail(f"Antipathy/Sympathy names a kind of creature that does not exist: {anti}")
    dis = flags.get("distraction")
    if dis and dis.get("settlement") is not None and not 0 <= int(dis["settlement"]) < len(game.world.settlements):
        fail(f"an illusion draws the eyes of no town: {dis}")
    if any(a.get("awake") and not a.get("name") for a in (game.leader.animals if game.party else [])):
        fail("an awakened animal has no name")
    held = flags.get("weather")  # (Expansion 3 E.5: locks and stone, weather and land)
    if held and (held.get("how") not in ("clear", "rain", "calm", "warm", "cold")
                 or not game.world.in_bounds(int(held["x"]), int(held["y"]))):
        fail(f"Control Weather holds a weather that cannot be: {held}")
    room = flags.get("arcane_room")
    if room is not None and not 0 <= int(room) < len(game.world.settlements):
        fail(f"an inn room is locked in no town: {room}")
    for d in (flags.get("secret_chest") or {}).get("items") or []:
        if d.get("def_id") not in game.tables.items.defs:
            fail(f"the secret chest holds a thing that does not exist: {d}")
    for c in game.party:
        for it in c.inventory:
            for tag in it.tags or []:
                if tag.startswith("conjured:") and int(tag.split(":")[1]) < game.world.time - 24 * 60:
                    fail(f"Creation's {it.def_id} outlived its time by more than a day")
    glyph = flags.get("glyph_room")  # (Expansion 3 E.6: lasting protections and the caster's keeping)
    if glyph is not None and not 0 <= int(glyph.get("settlement", -1)) < len(game.world.settlements):
        fail(f"a glyph guards an inn room in no town: {glyph}")
    for d in (flags.get("demiplane") or {}).get("items") or []:
        if d.get("def_id") not in game.tables.items.defs:
            fail(f"the demiplane holds a thing that does not exist: {d}")
    if int((flags.get("demiplane") or {}).get("money", 0)) < 0:
        fail("the demiplane holds less than no money")
    for rec in game.world.politics.get("hallowed", ()):
        if not game.world.in_bounds(int(rec["x"]), int(rec["y"])) or rec.get("extra") not in (
                "courage", "fear", "resistance", "vulnerability", "peaceful_rest"):
            fail(f"hallowed ground that cannot be: {rec}")
    stamps = {tag for c in game.party for it in c.inventory for tag in it.tags or [] if tag.startswith("cauldron:")}
    if len(stamps) > 1:
        fail(f"potions from more than one of Tasha's cauldrons are still about: {sorted(stamps)}")
    for c in list(game.party) + list(getattr(game, "waiting", []) or []):  # (Expansion 3 E.7: great magic)
        rec = (c.spells or {}).get("contingency")
        if rec and (rec.get("spell") not in game.tables.spells or rec.get("trigger") not in ("start", "bloodied", "down")
                    or int(game.tables.spells[rec["spell"]]["level"]) > 5):
            fail(f"a Contingency that cannot be on {c.name}: {rec}")
        for d in (c.spells or {}).get("wished_resist", ()):
            if d not in ("acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing",
                         "poison", "psychic", "radiant", "slashing", "thunder"):
                fail(f"{c.name} resists by a wish what is no damage type: {d}")
        for key in c.effects:
            if key.startswith("immune_spell:") and key.split(":", 1)[1] not in game.tables.spells:
                fail(f"{c.name} is immune by a wish to a spell that does not exist: {key}")
    for rec in flags.get("clones") or []:
        if not 0 <= int(rec.get("settlement", -1)) < len(game.world.settlements):
            fail(f"a clone grows in no town: {rec}")
    from realmwalker.rules import allies as ally_rules  # (Expansion 3 F.1: familiars and steeds)

    for c in game.party:
        fam = ally_rules.record(c, "familiar")
        if fam is not None and (fam.get("form") not in ally_rules.FAMILIAR_FORMS or fam.get("type") not in ally_rules.TYPES
                                or not 0 <= int(fam.get("hp", 0)) <= int(fam.get("max_hp", 0))
                                or fam.get("gone") and int(fam.get("hp", 0)) > 0):
            fail(f"{c.name}'s familiar cannot be: {fam}")
        steed = ally_rules.record(c, "steed")
        if steed is not None and (steed.get("look") not in ally_rules.STEED_LOOKS or steed.get("type") not in ally_rules.TYPES
                                  or int(steed.get("level", 0)) < 2
                                  or not 0 <= int(steed.get("hp", 0)) <= ally_rules.steed_max_hp(steed["level"])):
            fail(f"{c.name}'s steed cannot be: {steed}")
    from realmwalker.rules import servants as servant_rules  # (Expansion 3 F.4: the raised dead)

    for c in game.party:
        rows = c.spells.get("servants") or []
        if len(rows) > servant_rules.MAX:
            fail(f"{c.name} has {len(rows)} servants, more than {servant_rules.MAX}")
        for r in rows:
            if r.get("cid") not in game.tables.creatures or not 0 < int(r.get("hp", 0)) <= int(r.get("max_hp", 0)) \
                    or r.get("until") is not None and float(r["until"]) < game.world.time - 31 \
                    or len({x.get("id") for x in rows}) != len(rows):
                fail(f"{c.name}'s servant cannot be: {r}")
            elif r.get("form"):  # (F.5: a Planar Ally's spirit has its creature's form and the numbers of its slot)
                summon = game.tables.creatures[r["cid"]].get("summon") or {}
                if r["form"] not in summon.get("forms", {}) or int(r.get("level", 0)) < int(summon.get("level", 99)) \
                        or int(r["max_hp"]) != servant_rules.spirit_max_hp(game.tables, r["cid"], r["form"],
                                                                           int(r["level"])):
                    fail(f"{c.name}'s spirit cannot be: {r}")
        if c.effects.get(servant_rules.ROT) and c.alive and c.hp > c.effects.get(servant_rules.ROT_HP, c.hp) + 0.5:
            fail(f"{c.name} healed under a mummy's rot: {c.hp} above {c.effects.get(servant_rules.ROT_HP)}")
        shape = c.spells.get("shape")  # (Expansion 3 F.8: Animal Shapes, Shapechange worn outside a fight)
        if shape is not None and game.battle is None and (
                not isinstance(shape, dict) or shape.get("form") not in game.tables.creatures
                or shape.get("spell") not in game.tables.spells or int(shape.get("temp", 0)) <= 0
                or float(shape.get("until", 0)) < game.world.time - 31
                or float(shape["until"]) > game.world.time + 24 * 60 + 1):
            fail(f"{c.name}'s shape cannot be: {shape}")
    if game.party:
        riders = {c.name for c in game.party if c.alive and (ally_rules.record(c, "steed") or {}).get("gone") is False}
        herd = [a.get("summoned") for a in game.leader.animals if a.get("summoned")]
        if sorted(herd) != sorted(riders):
            fail(f"the steeds in the herd ({herd}) are not those of the living with a steed ({sorted(riders)})")
    camp_now = getattr(game, "camp", None)
    for key, rec in ((camp_now.wards or {}).items() if camp_now is not None else ()):
        if key == "glyph" and rec.get("kind") == "spell" and rec.get("spell") not in game.tables.spells:
            fail(f"a glyph holds a spell that does not exist: {rec}")
        if key == "symbol" and rec.get("effect") not in ("death", "discord", "fear", "pain", "sleep", "stunning"):
            fail(f"a symbol bears an effect that cannot be: {rec}")
    lm = game.local
    if lm is not None and lm.kind == "dungeon":
        for rec in lm.meta.get("passwall") or []:
            if any(not lm.in_bounds(int(x), int(y)) for x, y, _ in rec["cells"]):
                fail(f"a passage through the wall runs off the map: {rec}")
    for b in getattr(game, "fallen", []) or []:  # (Expansion 3 E.1: the bodies the party carries for raising)
        if b["char"].alive or any(b["char"] is c for c in game.party):
            fail(f"{b['char'].name} is carried as a body but is alive or walks with the party")
        if settled and b["char"].inventory is game.party[0].inventory:
            fail(f"{b['char'].name}'s body still carries from the party's pack")
    if len(game.party) > 1 + int(game.tables.companions["max_companions"]):
        fail(f"the party is too big ({len(game.party)})")
    if game.party and game.party[0].companion:
        fail("a companion is leading the party")
    kinds = game.tables.companions["archetypes"]
    if any(n.flags.get("grateful") and n.flags.get("recruit") not in kinds for n in game.world.npcs.values()):
        fail("someone freed from chains waits at an inn but cannot be taken on")
    for c in list(game.party[1:]) + list(getattr(game, "waiting", [])):
        k = c.companion
        if not k:
            fail(f"{c.name} travels with you but is no companion")
            continue
        if not 0 <= k.get("loyalty", -1) <= 100:
            fail(f"{c.name} has loyalty {k.get('loyalty')}")
        if k.get("npc") not in game.world.npcs:
            fail(f"{c.name} came from nowhere")
        if c in getattr(game, "waiting", []) and not k.get("wait_at"):
            fail(f"{c.name} is waiting nowhere")
        if not c.alive and settled:
            fail(f"dead {c.name} is still in the party")
        if c.money:
            fail(f"{c.name} carries coin of their own ({c.money}); only the leader's purse is spent")
        from realmwalker.data.schemas import BONDS

        bond = k.get("bond", "hired")
        if bond not in BONDS + ("unique",):
            fail(f"{c.name} follows you for no reason the game knows ({bond})")
        elif bond not in ("hired", "grateful") and k.get("wage"):
            fail(f"{c.name} is {bond} but takes a wage")
        elif bond == "sworn" and k.get("lender") not in game.world.factions:
            fail(f"{c.name} was lent by a realm that never was")
    # The seven unique companions: each is one person, in one place at a time.
    from realmwalker.game import uniques

    seen: dict[str, int] = {}
    for c in list(game.party[1:]) + list(getattr(game, "waiting", [])):
        uid = uniques.unique_of(c)
        if uid:
            seen[uid] = seen.get(uid, 0) + 1
            if uniques.records(game.world).get(uid, {}).get("state") != "with" and settled:
                fail(f"{c.name} travels with you, but the world thinks they are elsewhere")
    for uid, n in seen.items():
        if n > 1:
            fail(f"{uid} is in the party {n} times")
    for uid, r in uniques.records(game.world).items():
        if r.get("state") not in ("waiting", "with", "dead"):
            fail(f"{uid} is in no state the game knows ({r.get('state')})")
        if not 0 <= r.get("town", -1) < len(game.world.settlements):
            fail(f"{uid} lives nowhere")
    faces = [n.flags["unique"] for n in game.world.npcs.values() if n.flags.get("unique") and n.alive]
    if len(faces) != len(set(faces)):
        fail(f"two townsfolk share one unique face: {sorted(faces)}")


def _check_law(game, fail) -> None:
    """M6: the law's records make sense."""
    w = game.world
    r = game.renown
    for rec in r.crimes:
        if rec.get("crime") not in game.tables.law["crimes"] and rec.get("crime") != "old":
            fail(f"an unknown crime on the record: {rec.get('crime')}")
        if rec.get("realm") not in w.factions:
            fail("a crime recorded against a realm that does not exist")
    if game.arrest is not None and game.arrest.get("realm") not in w.factions:
        fail("arrested by a realm that does not exist")
    if game.sentence is not None:
        for step in game.sentence.get("steps", []):
            if step.split(":")[0] not in ("fine", "jail", "labour", "flogging", "branding", "death"):
                fail(f"an impossible sentence step {step}")
    if game.confined is not None and game.sentence is None:
        fail("confined without a sentence")
    for cap in r.flags.get("captives") or []:
        if not cap.get("name") or int(cap.get("reward", 0)) <= 0:
            fail(f"a prisoner nobody would pay for is being led along: {cap}")
    for fid, skills in r.flags.get("trained", {}).items():
        if any(sk not in game.leader.skills for sk in skills):  # what was taught stays, even if they cast you out
            fail(f"lessons from faction {fid} that did not take: {skills}")
    held = r.flags.get("confiscated")
    if held is not None and (held.get("money", 0) < 0 or not isinstance(held.get("items"), list)):
        fail("confiscated belongings are broken")
    for c in r.flags.get("captives", []):
        if c.get("def_id") not in game.tables.creatures:
            fail(f"a captive of unknown kind {c.get('def_id')}")
    # Spellcasting for pay (Expansion 3 G.2): who casts reaches no higher than the place allows, and a mage keeps a shop.
    if game.local is not None and game.local.kind == "settlement":
        from realmwalker.game import economy, spellhire
        from realmwalker.game.people import npcs_in

        s = w.settlement_at(game.player.x, game.player.y)
        for n in npcs_in(w, s.id) if s is not None else []:
            if n.job not in spellhire.TRADITION or not n.alive:
                continue
            cap = int(spellhire.spec(game)["reach"].get(spellhire._kind(game, n), 2))
            if not 0 <= spellhire.reach(game, n) <= cap:
                fail(f"a {n.job} who casts above what {s.name} allows: {spellhire.reach(game, n)} > {cap}")
            if n.job == "mage" and economy.shop_kind(game, n) != "mage":
                fail("a mage with no wares")


def _check_magic(game, fail) -> None:
    """Magic items, treasure and encounters (Expansion 1, part D): bonds within the rules, charges within their
    bounds, a known travel pace, a met band with a known attitude."""
    from realmwalker.rules import magic

    pack = {it.uid: it for c in game.party for it in c.inventory}
    for c in game.party:
        if len(c.attuned) > magic.ATTUNE_MAX:
            fail(f"{c.name} is bound to {len(c.attuned)} things")
        if len(set(c.attuned)) != len(c.attuned):
            fail(f"{c.name} is bound twice to one thing")
        for uid in c.attuned:
            it = pack.get(uid)
            if it is None or not it.magic.get("attune"):
                fail(f"{c.name} is bound to a thing that is gone or needs no bond ({uid})")
        from realmwalker.rules import spells as spellrules, war_bond

        if len(war_bond.bonds(c)) > war_bond.MAX_BONDS:  # (an Eldritch Knight's War Bond, Expansion 4 Part B)
            fail(f"{c.name} has {len(war_bond.bonds(c))} bonded weapons")
        if c.spells and len(spellrules.prepared(c, game.tables)) > spellrules.prepared_count(c, game.tables):
            fail(f"{c.name} has more spells prepared than the table allows")
    # Steel & Shadows Part C: a duel is a fight in progress, a masked potion is a potion of healing, a poison's DC
    # is a number (rules/poisons.py, game/shadows.py)
    if game.renown.flags.get("duel") is not None and game.battle is None and game.aftermath is None:
        fail("a duel of honour outlived its fight")
    from realmwalker.rules import poisons

    for it in pack.values():
        real = poisons.masked(it)
        if real is not None and (real not in game.tables.items or it.def_id != "potion_healing"):
            fail(f"a masked thing that is not a healing draught ({it.def_id} hiding {real})")
        if it.def_id in game.tables.items and game.tables.items.get(it.def_id).get("poison"):
            rec = poisons.of_item(game.tables, it)
            if rec is None or not isinstance(rec.get("dc"), int):
                fail(f"a poison without a proper save ({it.def_id})")
    # Steel & Shadows Part D: a shifting thing is in a shape it has; a once-a-day power is spent or ready, nothing else;
    # the Luck Blade's Wish never grows back (rules/engine/handlers/arms.py)
    from realmwalker.rules.engine.handlers import arms

    for it in pack.values():
        form = (it.magic or {}).get("form")
        if form and (form not in arms.FORMS or arms.FORMS[form] not in game.tables.items):
            fail(f"a magic thing in a shape it cannot take ({it.def_id}: {form})")
        for p in magic.props(it):
            if p.get("today") not in (None, 1):
                fail(f"a once-a-day power in an odd state on {it.def_id}: {p}")
            if p.get("no_regain") and int(p.get("left", 0)) > int(p.get("value", 0)):
                fail(f"charges that came back on {it.def_id}")
    # Schools & Domains Part A: a diviner's foretold rolls are d20s, three at most; the third eye is one of its gifts
    for c in game.party:
        dice_ = (c.spells or {}).get("portent") or []
        if len(dice_) > 3 or any(not isinstance(d, int) or not 1 <= d <= 20 for d in dice_):
            fail(f"odd foretold rolls on {c.name}: {dice_}")
        if (c.spells or {}).get("third_eye") not in (None, "dark", "unseen"):
            fail(f"a third eye open on something it cannot see: {c.spells['third_eye']}")
    # Schools & Domains Part B: the Trickster's blessing is on one at a time; the gods' chances stay small
    blessed = [c.name for c in game.party if (c.effects or {}).get("kept:trickster_blessing")]
    if len(blessed) > 1:
        fail(f"the Trickster's blessing on more than one: {blessed}")
    from realmwalker.game import gods

    for c in game.party:
        p = gods.chance(game, c)
        if not 0.0 <= p <= gods.MOST:
            fail(f"a god's answer out of bounds for {c.name}: {p}")
    battle = getattr(game, "battle", None)
    if battle is not None:
        ids = {f.id for f in battle.fighters}
        for tok in battle.tokens:
            if tok.kind == "duplicity" and tok.owner not in ids:
                fail("a double with no maker on the field")
    # Schools & Domains Part C: a tower lived in is kept by a living wizard (or a mages' circle) at its master's
    # numbers; nobody's people is one the world does not know; a creature fights with a block that exists
    from realmwalker.world import dungeon as gen

    for key, lm in game.world.local_maps.items():
        master = (lm.meta or {}).get("master") if lm.kind == "dungeon" else None
        if master is None:
            continue
        if master.get("rank") not in gen.MASTER_DC:
            fail(f"a tower master of no rank the game knows at {key}: {master}")
        fig = game.world.figures.get(master.get("figure"))
        if master.get("figure") is not None and fig is None:
            fail(f"a tower kept by a wizard the world never had at {key}")
        for f in lm.features.values():
            if f.get("trap") == "glyph" and int(f.get("dc", 0)) != gen.MASTER_DC[master["rank"]]:
                fail(f"a glyph at {key} not in its master's hand: DC {f.get('dc')}")
        for a in lm.actors:
            for cr in a.creatures:
                if cr.culture and cr.culture not in getattr(game.tables.cultures, "ids", ()) \
                        and cr.culture not in game.tables.sprites["figures"]["cultures"]:
                    fail(f"a creature of an unknown people at {key}: {cr.culture}")
    for npc in game.world.npcs.values():
        if npc.stats not in game.tables.creatures.defs:
            fail(f"{npc.name} fights with a block the game does not have: {npc.stats}")
    owners: dict[int, int] = {}
    for c in game.party:
        for uid in c.attuned:
            owners[uid] = owners.get(uid, 0) + 1
    if any(n > 1 for n in owners.values()):
        fail("one magic thing bound to two people")
    for it in pack.values():
        for p in magic.props(it):
            if p.get("kind") in ("charges", "pool") and not p.get("at_will") and not magic.pooled(p):
                if not 0 <= int(p.get("left", p.get("value", 1))) <= int(p.get("value", 1)):
                    fail(f"charges out of bounds on {it.def_id}: {p}")
            if magic.pooled(p) and (magic.pool(it) is None and int(p.get("cost", 1)) > 0
                                    or p.get("spell") not in game.tables.spells):
                fail(f"a wand's spell with no store of charges, or a spell the game lacks, on {it.def_id}: {p}")
        mind = it.magic.get("sentient") if it.magic else None
        if mind and mind.get("purpose") not in game.tables.magic["sentient"]["purposes"]:
            fail(f"a sentient thing with an unknown purpose: {mind.get('purpose')}")
        use = game.tables.items.get(it.def_id).get("use") or {}  # (Expansion 3 C.3: scrolls and potions)
        if use.get("scroll") and use["scroll"] not in game.tables.spells:
            fail(f"a scroll of a spell the game does not have: {it.def_id}")
        if use.get("heal"):
            from realmwalker.core import dice

            try:
                dice.parse(use["heal"])
            except dice.DiceError:
                fail(f"a potion whose healing cannot be rolled: {it.def_id} {use['heal']}")
    if game.player.pace not in ("slow", "normal", "fast"):
        fail(f"unknown travel pace {game.player.pace}")
    enc = game.encounter
    if enc is not None and getattr(enc, "attitude", "hostile") not in ("hostile", "indifferent", "friendly"):
        fail(f"a band with an unknown attitude: {enc.attitude}")


def _check_quests(game, fail) -> None:
    """M8: the journal holds real work, tied to things that exist. Expansion 6 C.2: nobody rolls weekly offers, and
    what waits to be taken (commissions, pleas) is not in the journal too, and is given by a living person."""
    from realmwalker.game.story import work

    w = game.world
    states = ("offered", "active", "return", "finished", "failed", "abandoned")
    seen = set()
    for sid, town in w.towns.items():
        if "offers" in town.flags or "offer_day" in town.flags:
            fail(f"settlement {sid} has weekly offers again")
    taken = {q["id"] for q in game.quests}
    for q in work.waiting(game):
        if q["id"] in taken:
            fail(f"quest {q['id']} ({q['template']}) waits to be taken and is in the journal")
        if q.get("giver", -1) not in w.npcs:
            fail(f"waiting quest {q['id']} ({q['template']}) has no giver")
        if q.get("state") != "offered":
            fail(f"waiting quest {q['id']} ({q['template']}) is {q.get('state')!r}")
    for sid, recs in w.politics.get("contracts", {}).items():  # (paid work, C.3)
        s = w.settlements[int(sid)]
        if len(recs) > work.slots(s):
            fail(f"{s.name} has {len(recs)} contracts at once")
        for rec in recs:
            q = rec["quest"]
            if q["template"] not in ("escort", "deliver", "defend") or q.get("contract") != rec["id"]:
                fail(f"contract {rec['id']} in {s.name} is not paid work of a known kind")
            if q["template"] != "defend" and (not q.get("danger") or
                                              q["danger"].get("group") not in game.tables.creatures.encounters):
                fail(f"contract {rec['id']} in {s.name} names no real danger on its road")
    from realmwalker.game.story import situations  # (situations, C.6)

    preds = situations.predicaments(game.tables)
    live_by_town: dict[int, int] = {}
    for sit in w.politics.get("situations", {}).values():
        if sit.get("predicament") not in preds:
            continue
        where = f"situation {sit['id']} ({sit['predicament']})"
        if sit["state"] not in situations.LIVE + situations.ENDED:
            fail(f"{where} is in state {sit['state']!r}")
        if not 0 <= int(sit["town"]) < len(w.settlements) or int(sit["town"]) not in w.towns:
            fail(f"{where} is in a town with no people")
        for role, rec in sit["roles"].items():
            if rec.get("npc") is not None and rec["npc"] not in w.npcs:
                fail(f"{where}: its {role} is nobody")
            n = w.npcs.get(rec.get("npc", -1))
            if n is not None and sit["state"] in situations.LIVE and n.alive and \
                    (n.flags.get("story") or {}).get("sit") not in (sit["id"], None):
                fail(f"{where}: its {role} {n.name} belongs to another story")
        if sit.get("adventure"):  # (an adventure's own step, C.10: outside the towns' rarity)
            from realmwalker.game import story

            if story.find_step(game, sit["adventure"], sit.get("step")) is None:
                fail(f"{where} is the step {sit.get('step')} of {sit['adventure']}, which has no such step")
        elif sit["state"] in situations.LIVE:
            live_by_town[int(sit["town"])] = live_by_town.get(int(sit["town"]), 0) + 1
            if sit["state"] == "taken" and sit.get("life") != situations._life(game) and sit.get("life"):
                fail(f"{where} is taken by a hero who is not this one")
        elif sit.get("ending") is None:
            fail(f"{where} ended with no ending")
        if "{" in " ".join(str(v) for v in sit["words"].values()) + " ".join(sit["journal"]):
            fail(f"{where}'s words are unfilled")
    for sid, n in live_by_town.items():
        if n > (2 if w.settlements[sid].great else 1):
            fail(f"{w.settlements[sid].name} has {n} live situations at once")
    from realmwalker.game.story import vignettes  # (hand-made vignettes, C.9)

    vigs = [s for s in w.politics.get("situations", {}).values() if vignettes.is_vignette(preds.get(s.get("predicament"), {}))]
    for sit in vigs:
        if sit["root"].get("vignette") != sit["predicament"]:
            fail(f"vignette {sit['id']} ({sit['predicament']}) was forged from a root that is not its own")
    if len({s["predicament"] for s in vigs}) != len(vigs):
        fail("a vignette was met twice in one world")
    from realmwalker.game.story import favours  # (favours and contacts, C.7)

    for f in game.renown.legend.get("favours", []):
        if f.get("from") not in w.npcs or f.get("kind") not in favours.KINDS or not 1 <= int(f.get("weight", 0)) <= 3:
            fail(f"a favour owed is not a favour: {f}")
        if f.get("used") and f.get("spent_on") is None:
            fail(f"a favour was spent on nothing: {f}")
    seen_contacts = set()
    for c in game.renown.legend.get("contacts", []):
        if c.get("npc") not in w.npcs or c.get("kind") not in favours.CONTACT_KINDS:
            fail(f"a contact is not a contact: {c}")
        if c.get("npc") in seen_contacts:
            fail(f"{w.npcs[c['npc']].name} is a contact twice")
        seen_contacts.add(c.get("npc"))
    events = game.tables.lives.get("events", {})  # (lives of townsfolk, C.4)
    for npc in w.npcs.values():
        lf = npc.flags.get("life")
        if lf is None:
            continue
        for t in lf["ties"]:
            if t.get("npc") is not None and t["npc"] not in w.npcs:
                fail(f"{npc.name}'s {t['kind']} {t['name']} is tied to nobody")
        for ev in lf["events"]:
            if ev["kind"] not in events:
                fail(f"{npc.name} lived an unknown event {ev['kind']!r}")
        if npc.flags.get("dress") == "mourning" and not npc.flags.get("mourning_until"):
            fail(f"{npc.name} wears black with no end to it")
        if "{" in npc.profile.get("want", "") + npc.profile.get("secret", "") + npc.profile.get("fear", ""):
            fail(f"{npc.name}'s words are unfilled")
    for q in game.quests:
        where = f"quest {q.get('id')} ({q.get('template')})"
        if q.get("template") not in game.tables.quests["templates"]:
            fail(f"{where} is of no known kind")
            continue
        if q.get("state") not in states:
            fail(f"{where} is in state {q.get('state')!r}")
        if q["id"] in seen:
            fail(f"{where} is in the journal twice")
        seen.add(q["id"])
        if q["state"] in ("active", "return") and q.get("deadline") is None:
            fail(f"{where} has no deadline")
        if q.get("giver", -1) >= 0 and q["giver"] not in w.npcs:
            fail(f"{where} was given by nobody")
        if not 0 <= q.get("town", -1) < len(w.settlements):
            fail(f"{where} belongs to no town")
        if q.get("reward", 0) < 0:
            fail(f"{where} pays {q.get('reward')}")
        t = q.get("target", {})
        if "site" in t and not 0 <= t["site"] < len(w.sites):
            fail(f"{where} points at no site")
        if "dest" in t and not 0 <= t["dest"] < len(w.settlements):
            fail(f"{where} points at no town")
        if "npc" in t and t["npc"] not in w.npcs:
            fail(f"{where} points at nobody")
        if q["state"] == "return" and not q.get("done"):
            fail(f"{where} is finished and not finished at once")


_LAST_TIME: dict[str, int] = {}


def _check_save_round_trip(app: App, report: AutoplayReport, turn: int) -> None:
    """Saving and loading must give back exactly the same game."""
    from realmwalker.game import save

    game = app.game
    if game is None:
        return
    folder = save.save_game(game, app.paths.saves)
    loaded = save.load_game(folder, app.tables)
    a, b = save.world_entries(game.world), save.world_entries(loaded.world)
    c, d = save.character_entries(game), save.character_entries(loaded)
    diffs = [k for k in a if k != "manifest.json" and a[k] != b.get(k)]
    diffs += [k for k in c if k != "manifest.json" and c[k] != d.get(k)]
    if diffs:
        report.errors.append(f"turn {turn}: save/load round trip differs in {diffs[:5]}")
    report.save_checks += 1


def _start_a_fight(app: App, rng: random.Random, report: AutoplayReport) -> None:
    """Random walking rarely meets trouble, so now and then trouble is sent to find the bot."""
    from realmwalker.game.encounters import make_encounter
    from realmwalker.ui.screens.game_screen import GameScreen

    game = app.game
    if game is None or game.busy or not isinstance(app.top, GameScreen):
        return
    roll = rng.random()
    if roll < 0.3:
        from realmwalker.game.people import npcs_in

        here = game.world.settlement_at(game.player.x, game.player.y)
        if here is None:
            towns = [t for t in game.world.settlements if t.kind in ("town", "city")]
            here = rng.choice(towns if towns and rng.random() < 0.6 else game.world.settlements)
            game.player.local_key = None
            game.sneaking = False
            game.player.x, game.player.y = here.x, here.y
        if not game.in_local:
            game.enter_local()
        people = [n for n in npcs_in(game.world, here.id) if n.alive and n.present]
        if people and rng.random() < 0.6:
            # Take on what waits here (M8; Expansion 6 C.2): a plea or a commission through its giver's own choice
            # in a conversation, else a bounty from the board.
            from realmwalker.game import quests
            from realmwalker.game.dialogue import Conversation
            from realmwalker.game.story import work

            for npc, q in work.offers_here(game, here):
                if npc is None:
                    quests.accept(game, q)
                else:
                    conv = Conversation(game, npc)
                    own = next((c for c in conv.menu() if c.id == "own_work" and c.data.get("q") == q["id"]), None)
                    if own is None:
                        continue
                    conv.choose(own)
                    yes = next((c for c in conv.menu() if c.id == "work_accept"), None)
                    if yes is None:
                        continue
                    conv.choose(yes)
                if q in game.quests:
                    report.quests += 1
                    return
            # A trouble of the town (C.6): ask the one who asks, take it on, and try an act or two of it.
            from realmwalker.game.story import situations

            for sit in situations.live_in(game, here.id):
                for role in sit["roles"]:
                    npc = situations._npc(game, sit, role)
                    if npc is None or not npc.alive or not npc.present:
                        continue
                    conv = Conversation(game, npc)
                    opts = [c for c in conv.menu() if c.id.startswith(("sit_", "fav_")) and c.enabled
                            and c.id != "sit_refuse"]  # (a favour called in: C.7)
                    if opts:
                        conv.choose(rng.choice(opts))
                        conv.close()
                        report.sits = getattr(report, "sits", 0) + 1
                        return
            from realmwalker.game.story import favours  # (an informant's news: C.7)

            for rec, npc in favours.contacts(game):
                if npc.settlement == here.id and npc.present and rec["kind"] == "informant":
                    conv = Conversation(game, npc)
                    ask = next((c for c in conv.menu() if c.id == "contact_ask" and c.enabled), None)
                    if ask is not None:
                        conv.choose(ask)
                        conv.close()
                        return
        if people and rng.random() < 0.1 and game.world.factions:
            # Now and then the bot joins a faction of someone here, so that commissions come (Expansion 6 C.2).
            from realmwalker.game import reputation
            from realmwalker.game.people import npc_factions

            for f in npc_factions(game, rng.choice(people)):
                if reputation.join_problem(game, f) is None:
                    reputation.join(game, f)
                    return
        hires = [n for n in people if n.flags.get("recruit") and not n.flags.get("companion")]
        if hires and rng.random() < 0.5 and len(game.party) < 3:
            from realmwalker.game import companions

            game.leader.money += 5000
            hires[0].met, hires[0].disposition = True, max(hires[0].disposition, 10)
            if companions.hire(game, hires[0]) and hires[0].flags.get("companion"):
                report.hires += 1
            return
        if people and rng.random() < 0.25 and game.world.factions:
            # Now and then the bot breaks the law in front of the watch (or not), to exercise arrests and sentences.
            from realmwalker.game import law

            crime = rng.choice(["theft", "assault", "trespass", "pickpocket", "murder"])
            guards = [n for n in people if n.job == "guard"]
            seen = [rng.choice(guards)] if guards and rng.random() < 0.6 else rng.sample(people, min(2, len(people)))
            if law.commit(game, crime, victim=rng.choice(people), value=rng.randint(0, 300), witnesses=seen):
                report.crimes += 1
            return
        if people:
            npc = rng.choice(people)
            lm = game.local
            spot = None
            if lm is not None and lm.kind == "settlement" and rng.random() < 0.5:
                # Stand beside them and press t, as a player would (walking into people only squeezes past).
                from realmwalker.game.people import npc_at

                walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
                spot = next(((npc.x + dx, npc.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                             if lm.in_bounds(npc.x + dx, npc.y + dy) and walk[npc.x + dx, npc.y + dy]
                             and npc_at(game, npc.x + dx, npc.y + dy) is None), None)
            if spot is not None:
                game.player.lx, game.player.ly = spot
                app.handle_event(KeyEvent("t"))
            else:
                game.talk_to = npc.id
            report.talks += 1
        return
    if roll < 0.38 and game.quests:
        # Go where the work is: arrivals, raids, escorts and beasts all happen on the spot.
        from realmwalker.game import quests

        live = [q for q in quests.active(game) if not q["done"]]
        if live:
            q = rng.choice(live)
            t = q["target"]
            where = None
            if "site" in t and 0 <= t["site"] < len(game.world.sites):
                site = game.world.sites[t["site"]]
                where = (site.x, site.y)
            elif "dest" in t and 0 <= t["dest"] < len(game.world.settlements):
                s = game.world.settlements[t["dest"]]
                where = (s.x, s.y)
            elif q["template"] == "hunt_beast":
                where = (int(t["x"]), int(t["y"]))
            elif q["template"] == "defend" and 0 <= t.get("settlement", -1) < len(game.world.settlements):
                s = game.world.settlements[t["settlement"]]
                where = (s.x, s.y)
            if where is not None:
                game.player.local_key = None
                game.sneaking = False
                game.player.x, game.player.y = where
                game._arrive(None)
                if rng.random() < 0.5 and not game.busy:
                    game.enter_local()
                report.quest_trips += 1
                return
    if roll < 0.4 and game.world.sites:
        from realmwalker.game import dungeon

        site = rng.choice(game.world.sites)
        game.player.local_key = None
        game.sneaking = False
        game.player.x, game.player.y = site.x, site.y
        game.enter_local()
        dungeon.descend(game, 1)
        report.dungeons += 1
        return
    if roll < 0.55:
        from realmwalker.game.events import make_event

        game.event = make_event(game, rng.choice(sorted(app.tables.travel_events)))
        report.events += 1
        return
    group = rng.choice(sorted(app.tables.creatures.encounters))
    game.encounter = make_encounter(game, group, game.world.rng.child(f"autoplay/{game.world.time}/{group}"))
    report.fights += 1


def run_autoplay(*, turns: int = 3000, seed: int = 1, home: Path | None = None) -> AutoplayReport:
    report = AutoplayReport()
    own_home = home is None
    home = Path(tempfile.mkdtemp(prefix="realmwalker_autoplay_")) if home is None else home
    config = {"debug_console": True}
    rng = random.Random(seed)
    start = time.monotonic()

    def new_app() -> App:
        # Headless, the app draws as a window would (maps, figures, the fight's stage), recording the pictures.
        return App(home=home, headless=True, config_overrides=config)

    app = new_app()
    console = tcod.console.Console(*CONSOLE_SIZES[0], order="F")
    try:
        for turn in range(turns):
            if turn % 200 == 0:
                console = tcod.console.Console(*rng.choice(CONSOLE_SIZES), order="F")
            ev = _pick_event(app, rng, console)
            app.handle_event(ev)
            app.update()
            app.render(console)
            app.window_requests.clear()
            if app.top is not None:
                report.screens[type(app.top).__name__] += 1
            _check_invariants(app, report, turn)
            if app.game is not None:
                report.game_turns += 1
                if report.game_turns % 400 == 0:
                    _check_save_round_trip(app, report, turn)
                if report.game_turns % 150 == 0:
                    _start_a_fight(app, rng, report)
                if app.game is not None and app.game.battle is not None:
                    report.battle_turns += 1
            report.turns = turn + 1
            if not app.running:
                app.shutdown()
                report.restarts += 1
                app = new_app()
        app.update()
        _check_invariants(app, report, report.turns)
    finally:
        app.shutdown()

    # Settings written to disk must load back identically.
    loaded = Settings.load(app.paths.settings_file)
    if loaded != app.settings:
        report.errors.append(f"settings did not round-trip: saved {app.settings}, loaded {loaded}")
    logged = count_error_lines(app.paths.logs)
    if logged:
        tail = (app.paths.logs / "errors.log").read_text(encoding="utf-8", errors="replace")[-1500:]
        report.errors.append(f"{logged} error line(s) in errors.log:\n{tail}")
    report.elapsed = time.monotonic() - start
    if own_home and report.ok:
        shutil.rmtree(home, ignore_errors=True)
    elif not report.ok:
        report.errors.append(f"logs kept in {home}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Realmwalker headless autoplay bot")
    parser.add_argument("--turns", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="print a machine-readable result line")
    args = parser.parse_args()
    report = run_autoplay(turns=args.turns, seed=args.seed)
    print(report.summary())
    if args.json:
        print(json.dumps({"ok": report.ok, "turns": report.turns, "errors": len(report.errors)}))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
