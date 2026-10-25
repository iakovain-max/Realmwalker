"""Quests (M8): work that code makes from templates (data/quests.json) and ties to real things in the world: a
real gang's captain in a real hideout, a real site near the town, a named beast in real country, a letter for a
real innkeeper in a real town, an artifact from the world's history lying in a real barrow.

Nobody rolls a job each week (Expansion 6 C.2): work is a commission, a plea, a bounty, a contract, a situation or a
chapter of an adventure, built here by `make` for a target its source chooses (game/story/work.py keeps what waits
to be taken). Accepted work goes into the journal (`game.quests`, saved with the character). Progress is
noticed where it happens (a fight won, a chest opened, chains broken, a word with the right person); rewards and
consequences go through reputation, news and the companions. Some work has a hidden side: the outlaws are starving
deserters, the letter would hang its sender, the debtor has nothing.

Code owns targets, rewards and outcomes, and the terms are always shown.

A quest is a plain dict (so it saves as JSON):
  id, template, state ("offered", "active", "return", "finished", "failed", "abandoned"), giver (npc id, or -1 for
  the town's authorities), giver_name, town, faction, reward (copper), days, deadline, hidden, revealed, done,
  target (what and where: site, gang, x/y, dest, npc, item...), words (slot values for the text), journal (lines).
"""

from __future__ import annotations

import math

from realmwalker.core import dice, textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.core.rng import RNG
from realmwalker.game.encounters import DEADLY_RATIO, ratio_words, threat_ratio
from realmwalker.rules.creatures import typical_group
from realmwalker.rules.items import Item, money_text
from realmwalker.world import factions as fx

AUTHORITY_JOBS = ("guard", "headman", "lord")  # who pays a bounty posted on the board
DEBT_DC = 12
BLACKMAIL_DC = 13
LIVE = ("active", "return")
COVERT = ("assassinate", "steal", "smuggle")  # work nobody boasts about, and nobody hears of
TAGS = {"bounty": ("victory",), "clear_lair": ("victory",), "hunt_beast": ("victory",), "rescue": ("help_poor",),
        "investigate": ("cult_hunted",), "retrieve": ("discovery",), "slay_dragon": ("victory", "hard_fight"),
        "apprenticeship": ("discovery",)}
FETCHED = ("retrieve", "steal", "apprenticeship")  # work that ends with a thing carried back to whoever set it


class _Spot:
    def __init__(self, x: int, y: int) -> None:
        self.x, self.y = x, y


def _cha(game, skill: str, roll: int) -> int:
    """A Charisma check's die under Glibness (game/glamour.py)."""
    from realmwalker.game import glamour

    return glamour.cha_roll(game, game.leader, skill, roll)


def spec(game) -> dict:
    return game.tables.quests


def active(game) -> list[dict]:
    return [q for q in game.quests if q["state"] in LIVE]


def map_marks(game) -> list[tuple[int, int]]:
    """Where the work you have in hand wants you, lit on the maps: sites, towns and a patch of wild country; and
    the places your tales want you (Expansion 6)."""
    from realmwalker.game import story

    tales = story.map_marks(game)
    if not getattr(game, "quests", None):
        return tales
    w = game.world
    out = []
    for q in active(game):
        if q["done"]:
            continue
        t = q["target"]
        if "site" in t and 0 <= t["site"] < len(w.sites):
            out.append((w.sites[t["site"]].x, w.sites[t["site"]].y))
        if "dest" in t and 0 <= t["dest"] < len(w.settlements):
            out.append((w.settlements[t["dest"]].x, w.settlements[t["dest"]].y))
        if q["template"] == "hunt_beast":
            out.append((int(t["x"]), int(t["y"])))
    return out + tales


def by_id(game, qid) -> dict | None:
    return next((q for q in game.quests if q["id"] == qid), None)


def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def direction(frm, to) -> str:
    from realmwalker.game.events import compass

    miles = int(round(dist(frm, to) * 3))
    return f"about {miles} miles to the {compass(to.x - frm.x, to.y - frm.y)} of {frm.name}"


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def fill(game, q: dict, kind: str, which: str = "") -> str:
    """Built-in words for a quest ({slots} from its words, reward and days)."""
    rng = game.world.rng.child(f"quest-text/{q['id']}/{kind}/{which}")
    texts = spec(game)["text"]
    text = texts.get(q.get("text_key", ""), texts[q["template"]])  # a variant's own words, if it has them
    options = text["hidden"][which] if kind == "hidden" else text[kind]
    values = {k: str(v) for k, v in q.get("words", {}).items()}
    values.update(reward=money_text(q["reward"]), days=str(q["days"]))
    return cap(textgen.fill(rng.choice(options), rng, {}, values))


def title(game, q) -> str:
    return fill(game, q, "title")


def pitch(game, q) -> str:
    return fill(game, q, "pitch")


def terms(q) -> str:
    if q.get("unique") and not q["reward"]:
        return f"{q['words'].get('pay', 'no money')}, {q['days']} days"  # one of the seven asks it of you
    return f"{money_text(q['reward'])}, {q['days']} days"


def giver_jobs(game) -> set[str]:
    return {job for t in spec(game)["templates"].values() for job in t["givers"]}


def days_left(game, q) -> int | None:
    if q.get("deadline") is None or q["done"]:
        return None
    return q["deadline"] - game.moment.total_days


# ---------------------------------------------------------------------------- making work
# Nobody thinks of a job every week any more (Expansion 6 C.2, ADVENTURES.md 5.15): work is a commission from a
# faction you serve, a plea from someone with a real need, a bounty on the board, a contract, a situation or a
# chapter of an adventure (game/story/work.py holds who has which). `make_offer` is today's choice for a person.
def trial_note(game, q) -> str:
    f = game.world.factions.get(q.get("trial", -1))
    if f is None:
        return ""
    from realmwalker.game.reputation import rank_name

    return (f"<info>{f.name} is watching this one. Do it, and you will be more than "
            f"{rank_name(game, f.id)} to them.</>")


def make_offer(game, npc, rng: RNG, template: str | None = None, avoid=()) -> dict | None:
    """Work this person might set today: of the kind asked for, or of any kind their trade gives."""
    kinds = [template] if template else [t for t, s in spec(game)["templates"].items() if npc.job in s["givers"]]
    rng.shuffle(kinds)
    # A town where three people all want an heirloom fetched is a dull town: spread the kinds about.
    counts = {k: sum(1 for a in avoid if a == k) for k in kinds}
    kinds.sort(key=lambda k: counts.get(k, 0))
    for kind in kinds:
        q = build(game, npc, kind, rng)
        if q is not None:
            return q
    return None


WALKING_DAY_MINUTES = 8 * 60  # a day's walking, stopping for the nights
ONE_WAY = ("deliver", "escort", "smuggle")  # work that ends where it is taken, not back with the giver


def walking_minutes(game, frm, to) -> int | None:
    """How long the real walk takes between two places, by the roads and the lie of the land."""
    import tcod.path

    path = tcod.path.path2d(game.travel_costs(), start_points=[(frm.x, frm.y)], end_points=[(to.x, to.y)],
                            cardinal=100, diagonal=141)
    if len(path) < 2:
        return None
    total, x, y = 0, frm.x, frm.y
    for nx, ny in path.tolist()[1:]:
        step = game.step_minutes(x, y, int(nx), int(ny))
        if step is None:
            return None
        total, x, y = total + step, int(nx), int(ny)
    return total


def allow_the_walk(game, q: dict) -> None:
    """Enough days for the real walk there (and back), walking by day, with a few to spare: a straight line on
    the map is not the way through hills and forest, and a rescue could be offered that nobody could reach."""
    w = game.world
    t = q.get("target", {})
    if "site" in t:
        to = w.sites[t["site"]]
    elif "dest" in t:
        to = w.settlements[t["dest"]]
    elif "x" in t:
        to = _Spot(t["x"], t["y"])
    else:
        return
    minutes = walking_minutes(game, w.settlements[q["town"]], to)
    if minutes is None:
        return
    trips = 1 if q["template"] in ONE_WAY else 2
    q["days"] = max(int(q["days"]), math.ceil(minutes * trips / WALKING_DAY_MINUTES) + 3)


def base_quest(game, npc, template: str, rng: RNG, *, hard: float = 1.0, town=None) -> dict:
    from realmwalker.game.people import npc_factions

    s = spec(game)["templates"][template]
    lo, hi = s["reward"]
    w = game.world
    qid = int(w.politics.get("next_quest", 0))
    w.politics["next_quest"] = qid + 1
    town = town or w.settlements[npc.settlement]
    facs = npc_factions(game, npc) if npc is not None else []
    if not facs:
        owner = fx.owner_of(w, town)
        facs = [owner] if owner is not None else []
    level = max(c.level for c in game.party) if game.party else 1
    reward = int(rng.randint(lo, hi) * hard * (0.8 + 0.1 * level)) // 10 * 10
    lo_d, hi_d = s["days"]
    hidden = None
    for h, chance in s.get("hidden", {}).items():
        if hidden is None and rng.chance(float(chance)):
            hidden = h
    return {
        "id": qid, "template": template, "state": "offered", "giver": npc.id if npc is not None else -1,
        "giver_name": npc.name if npc is not None else f"the watch of {town.name}",
        "giver_job": npc.job if npc is not None else "guard", "town": town.id,
        "faction": facs[0].id if facs else -1, "reward": max(10, reward), "days": rng.randint(lo_d, hi_d),
        "offered_day": game.moment.total_days, "hidden": hidden, "revealed": False, "done": False,
        "target": {}, "words": {"giver": npc.first_name if npc is not None else "the watch", "town": town.name},
        "journal": [],
    }


def allow_for(q: dict, tiles: float) -> None:
    """Enough days to walk there (and back), at a hard pace of about seven tiles a day, with some to spare."""
    q["days"] = max(int(q["days"]), int(math.ceil(tiles / 7)) + 4)


def cleared(game) -> set[int]:
    return set(game.world.politics.get("cleared", []))


# ---------------------------------------------------------------------------- the builders: pick, then make
# Each kind of work has two halves (Expansion 6 C.2). A picker chooses today's target near the giver, as the weekly
# offers did; it is kept for whatever still wants a random target (a companion's own request, a commission, the debug
# console). A maker builds the quest dict for a target it is given, so that situations, contracts, commissions and an
# adventure's steps can say what the work is about. A target is a plain dict: "kind" (the template), "town" (the
# settlement the work is set from, when there is no giver to say it) and the ids its kind needs (each picker says).

def _bounty_pick(game, npc, rng, town):
    """{"gang"}: the nearest gang within reach."""
    w = game.world
    gangs = [f for f in fx.active_factions(w, "bandit_gang") if 0 <= f.site < len(w.sites)
             and f.site not in cleared(game) and dist(w.sites[f.site], town) <= 32]
    if not gangs:
        return None
    return {"gang": min(gangs, key=lambda f: dist(w.sites[f.site], town)).id}


def _bounty(game, npc, target, rng, town):
    w = game.world
    gang = w.factions[target["gang"]]
    site = w.sites[gang.site]
    leader = fx.leader_of(w, gang)
    q = base_quest(game, npc, "bounty", rng, hard=1 + dist(site, town) / 40, town=town)
    q["target"] = {"site": site.id, "gang": gang.id}
    q["words"].update(target=leader.full_name() if leader is not None and leader.alive else "their captain",
                      gang=gang.name, site=site.name, where=direction(town, site))
    allow_for(q, dist(site, town) * 2)
    return q


def _clear_lair_pick(game, npc, rng, town):
    """{"site"}: a place to clear near the town, a beast of the old songs first."""
    from realmwalker.game import past
    from realmwalker.world import dungeon as gen

    w = game.world
    done = cleared(game) | {q["target"].get("site") for q in _all_quests(game) if q["template"] == "clear_lair"}
    sites = [s for s in w.sites if s.id not in done and 3 <= dist(s, town) <= 16
             and gen.style_for(w, s) in ("cellars", "crypt", "cave", "warren", "tower")]
    if not sites:
        return None
    # A beast of the old songs, if one lairs near enough: the town has a name for it, and its dead.
    named = [s for s in sites if past.lair_beast(game, s) is not None and
             past.lair_beast(game, s).kind == "beast"]
    return {"site": (rng.choice(named) if named and rng.chance(0.7) else rng.choice(sites)).id}


def _clear_lair(game, npc, target, rng, town):
    from realmwalker.game import past

    w = game.world
    site = w.sites[target["site"]]
    q = base_quest(game, npc, "clear_lair", rng, hard=1 + site.danger / 6, town=town)
    q["target"] = {"site": site.id}
    q["words"].update(site=site.name, where=direction(town, site))
    beast = past.lair_beast(game, site)
    if beast is not None and beast.kind == "beast":
        victims = [w.figures[k] for k in beast.kills if k in w.figures]
        ours = [v for v in victims if v.home == f"S{town.id}"]
        victim = (ours or victims)[0].full_name() if (ours or victims) else "more of ours than anyone can count"
        q["text_key"] = "clear_lair_beast"
        q["words"].update(beast=past.beast_title(beast), beast_word=past.beast_word(game, beast), victim=victim)
        q["target"]["beast"] = beast.id
    return q


def _hunt_beast_pick(game, npc, rng, town):
    """{"beast", "site", "group"} (a beast of the history in its lair) or {"group", "x", "y"} (one of the list)."""
    w = game.world
    found = _lair_beasts(game, town)
    if found:
        site, fig, group = rng.choice(found)
        return {"beast": fig.id, "site": site.id, "group": group}
    beasts = [b for b in spec(game)["beasts"] if b[0] in game.tables.creatures.encounters]
    if not beasts:
        return None
    # Nobody sends a green traveller after a troll: the beast is one the party might live through (the boar and the
    # orchard bear at first, the trolls and ogres once they have made a name).
    fitting = [b for b in beasts if beast_ratio(game, b[0]) < DEADLY_RATIO]
    group = rng.choice(fitting or [min(beasts, key=lambda b: beast_ratio(game, b[0]))])[0]
    for _ in range(40):
        x = town.x + rng.randint(-12, 12)
        y = town.y + rng.randint(-12, 12)
        if not w.in_bounds(x, y) or abs(x - town.x) + abs(y - town.y) < 5:
            continue
        if not game.biome_def(x, y)["passable"] or w.settlement_at(x, y) or w.site_at(x, y):
            continue  # water, or somewhere people live
        return {"group": group, "x": x, "y": y}
    return None


def _lair_beasts(game, town) -> list:
    """Real beasts of the history, lairing within reach and ones the party might live through, before any beast of
    the fixed list: the town knows their names, and where they sleep."""
    from realmwalker.game import past

    w = game.world
    taken = {q["target"].get("beast") for q in _all_quests(game) if q["template"] == "hunt_beast"}
    found = []
    for key, hid in sorted(w.politics.get("lairs", {}).items()):
        fig = w.figures.get(hid)
        if fig is None or not fig.alive or fig.kind != "beast" or fig.id in taken or not 0 <= int(key) < len(w.sites):
            continue
        site = w.sites[int(key)]
        group = past.group_of(game, fig)
        if 3 <= dist(site, town) <= 16 and group in game.tables.creatures.encounters and \
                beast_ratio(game, group) < DEADLY_RATIO:
            found.append((site, fig, group))
    return found


def _hunt_beast(game, npc, target, rng, town):
    from realmwalker.game import past

    w = game.world
    q = base_quest(game, npc, "hunt_beast", rng, town=town)
    fig = w.figures.get(target.get("beast", -1))
    if fig is not None and target.get("site") is not None:
        site = w.sites[target["site"]]
        q["target"] = {"x": site.x, "y": site.y, "group": target["group"], "beast": fig.id, "site": site.id}
        q["words"].update(beast=past.beast_title(fig), beast_what=past.beast_word(game, fig),
                          where=f"in its lair at {site.name}, {direction(town, site)}")
        return q
    x, y, group = int(target["x"]), int(target["y"]), target["group"]
    _, name, what = next((b for b in spec(game)["beasts"] if b[0] == group), (group, "the beast", "a beast"))
    area = w.area_at(x, y)
    q["target"] = {"x": x, "y": y, "group": group}
    where = f"in {area.name}" if area is not None else "out in the wild"
    q["words"].update(beast=name, beast_what=what, where=f"{where}, {direction(town, _Spot(x, y))}")
    return q


def beast_ratio(game, group: str) -> float:
    """How a beast (and whatever runs with it), or a band of raiders, measures up against the party as it is now."""
    alive = [c for c in game.party if c.alive] or game.party
    return threat_ratio(game.tables, typical_group(game.tables, group, len(alive)), alive)


def danger_note(game, q: dict) -> str:
    """What a sensible person thinks on hearing what the work is: how the beast measures up (the same words the road
    uses for a band you meet), or "" when there is nothing to judge."""
    road = q.get("danger")  # (a contract's danger on the way: game/story/work.py)
    if road and not road.get("met") and road.get("group") in game.tables.creatures.encounters:
        return f"<dim>On the road, {textgen.escape_markup(road.get('name', 'trouble'))}:</> " \
               f"{ratio_words(beast_ratio(game, road['group']))}"
    group = q.get("target", {}).get("group")
    if q.get("template") not in ("hunt_beast", "defend") or group not in game.tables.creatures.encounters:
        return ""
    words = ratio_words(beast_ratio(game, group))
    if q["template"] == "defend":
        return f"<dim>Standing against {q['words'].get('raiders', 'the raiders')}:</> {words}"
    return f"<dim>Hunting {q['words'].get('beast', 'it')}:</> {words}"


def _someone_in(game, dest, rng: RNG, jobs=None):
    """A real person of standing in another place (the place is made ready if nobody has been there yet)."""
    from realmwalker.game.people import npcs_in, prepare_town

    if not npcs_in(game.world, dest.id):
        prepare_town(game, dest)
    folk = [n for n in npcs_in(game.world, dest.id) if n.alive and n.notable and n.job != "lord"
            and (jobs is None or n.job in jobs)]
    return rng.choice(folk) if folk else None


def _someone_far(game, town, rng, lo, hi, jobs=None, walled=False):
    """{"dest", "npc"}: a person of standing in another place between lo and hi tiles away."""
    dests = [s for s in game.world.settlements if s.id != town.id and lo <= dist(s, town) <= hi
             and (s.walled or not walled)]
    if not dests:
        return None
    dest = rng.choice(dests)
    who = _someone_in(game, dest, rng, jobs=jobs)
    return None if who is None else {"dest": dest.id, "npc": who.id}


def _deliver_pick(game, npc, rng, town):
    return _someone_far(game, town, rng, 8, 40)


def _deliver(game, npc, target, rng, town):
    w = game.world
    dest, who = w.settlements[target["dest"]], w.npcs[target["npc"]]
    q = base_quest(game, npc, "deliver", rng, hard=1 + dist(dest, town) / 30, town=town)
    q["target"] = {"dest": dest.id, "npc": who.id}
    q["words"].update(recipient=f"{who.name}, the {who.title}", recipient_name=who.name, dest=dest.name)
    allow_for(q, dist(dest, town))
    return q


def _retrieve_pick(game, npc, rng, town):
    """{"site", "artifact"} (a lost treasure of the old days, for a priest or a lord) or {"site"} (an heirloom)."""
    w = game.world
    taken = {q["target"].get("artifact") for q in _all_quests(game) if q["template"] == "retrieve"}
    artifacts = [(i, a) for i, a in enumerate(w.politics.get("artifacts", []))
                 if 0 <= a.get("site", -1) < len(w.sites) and not a.get("found") and i not in taken
                 and dist(w.sites[a["site"]], town) <= 40]
    if artifacts and npc is not None and npc.job in ("priest", "lord") and rng.chance(0.6):
        i, a = rng.choice(artifacts)
        return {"site": a["site"], "artifact": i}
    sites = [s for s in w.sites if 4 <= dist(s, town) <= 25]
    return {"site": rng.choice(sites).id} if sites else None


def _retrieve(game, npc, target, rng, town):
    from realmwalker.game.people import family_of

    w = game.world
    site = w.sites[target["site"]]
    if target.get("artifact") is not None:
        i = int(target["artifact"])
        a = w.politics["artifacts"][i]
        q = base_quest(game, npc, "retrieve", rng, hard=2.5, town=town)
        q["target"] = {"site": site.id, "artifact": i, "item": a["name"]}
        q["words"].update(item=a["name"], site=site.name, where=direction(town, site))
        allow_for(q, dist(site, town) * 2)
        return q
    family = family_of(npc) if npc is not None else town.name
    # Keyed on the family, so two houses in one town do not both want the same thing.
    thing, base = w.rng.child(f"heirloom/{family}/{npc.id if npc is not None else -1}").choice(
        spec(game)["heirlooms"])
    name = f"the {family} {thing}"
    q = base_quest(game, npc, "retrieve", rng, hard=1 + site.danger / 6, town=town)
    q["target"] = {"site": site.id, "item": name, "base": base}
    q["words"].update(item=name, site=site.name, where=direction(town, site))
    return q


def _apprenticeship_pick(game, npc, rng, town):
    """{"site", "wizard", "rival"}: a wizard's grimoire - from the tower of a wizard of the world's history who is dead
    (or, while they live, from their own shelves: a rival's), else from a place where one was lost."""
    from realmwalker.world import dungeon as gen

    w = game.world
    taken = {q["target"].get("site") for q in _all_quests(game) if q["template"] == "apprenticeship"}
    towers = []
    for sid, hid in w.politics.get("towers", {}).items():
        site = w.sites[int(sid)] if 0 <= int(sid) < len(w.sites) else None
        fig = w.figures.get(hid)
        if site is None or fig is None or site.id in taken or gen.style_for(w, site) != "tower":
            continue
        if 3 <= dist(site, town) <= 30:
            towers.append((site, fig))
    if towers:
        site, fig = rng.choice(towers)
        return {"site": site.id, "wizard": fig.name, "rival": fig.alive}
    sites = [x for x in w.sites if 4 <= dist(x, town) <= 25 and x.id not in taken]
    if not sites:
        return None
    return {"site": rng.choice(sites).id, "wizard": rng.choice(spec(game)["text"]["apprenticeship"]["nameless"]),
            "rival": False}


def _apprenticeship(game, npc, target, rng, town):
    """A mage's proof of worth (Expansion 5 C.3): bring back a wizard's grimoire, and the mage takes one of you as an
    apprentice: a spell taught (`lesson`)."""
    site = game.world.sites[target["site"]]
    wizard, rival = target["wizard"], bool(target.get("rival"))
    q = base_quest(game, npc, "apprenticeship", rng, hard=(1.5 if rival else 1.0) + site.danger / 8, town=town)
    item = f"the grimoire of {wizard}"
    q["target"] = {"site": site.id, "item": item, "base": "spellbook", "wizard": wizard, "rival": rival}
    q["words"].update(item=item, site=site.name, where=direction(town, site), wizard=wizard)
    return q


LESSON_TOP = 3  # (the highest spell level a town's mage teaches an apprentice)


def lesson(game, q, npc) -> list[str]:
    """The apprenticeship's real pay: the mage teaches a wizard of the party a spell for their book (of a level
    they could prepare, at most third, that they lack), or, with no wizard among you, writes out a scroll."""
    from realmwalker.game import treasure
    from realmwalker.rules.inventory import add_existing
    from realmwalker.rules.progression import spell_top_level

    t = game.tables
    rng = game.world.rng.child(f"lesson/{q['id']}")
    for c in (c for c in game.party if c.alive and c.cls == "wizard"):
        top = min(LESSON_TOP, spell_top_level(c, t))
        book = set(c.spells.get("spellbook", []))
        can = sorted(sid for sid, sp in t.spells.defs.items() if "wizard" in sp.get("classes", ())
                     and 1 <= int(sp["level"]) <= top and sid not in book and not sp.get("again_of"))
        if can:
            sid = rng.choice(can)
            c.spells.setdefault("spellbook", []).append(sid)
            return [f"<magic>{esc(npc.first_name)} keeps the bargain: a long night over the grimoire with "
                    f"{esc(c.name.split()[0])}, and {t.spells[sid]['name']} is written into their book.</> "
                    f"<dim>(an apprentice's lesson)</>"]
    scrolls = sorted(d for d, it in t.items.defs.items() if (it.get("use") or {}).get("scroll") in t.spells
                     and "wizard" in t.spells[it["use"]["scroll"]].get("classes", ())
                     and 1 <= int(t.spells[it["use"]["scroll"]]["level"]) <= 2)
    if not scrolls:
        return []
    it = add_existing(game.leader, t.items, treasure.new_item(game, rng.choice(scrolls), rng))
    return [f"<magic>No wizard among you to teach, so {esc(npc.first_name)} writes out a scroll instead: "
            f"{t.items.name(it)}.</>"]


def _rescue_pick(game, npc, rng, town):
    """{"holder", "kin"}: a gang, cult or tribe within reach holds someone of the giver's."""
    w = game.world
    holders = [f for f in fx.active_factions(w, "bandit_gang", "cult", "tribe") if 0 <= f.site < len(w.sites)
               and f.site not in cleared(game) and dist(w.sites[f.site], town) <= 22]
    if not holders:
        return None
    return {"holder": rng.choice(holders).id, "kin": rng.choice(spec(game)["kin"])}


def _rescue(game, npc, target, rng, town):
    from realmwalker.game.people import family_of
    from realmwalker.world.names import forge

    w = game.world
    holder = w.factions[target["holder"]]
    site = w.sites[holder.site]
    kin = target.get("kin") or rng.choice(spec(game)["kin"])
    sex = target.get("sex") or ("male" if kin in ("son", "brother", "husband") else
                                "female" if kin in ("daughter", "sister", "wife") else rng.choice(["male", "female"]))
    captive = target.get("captive")
    if captive is None:
        nf = forge(w, game.tables)
        captive = nf.person(town.culture, sex, rng, family=family_of(npc)) if kin != "apprentice" and \
            npc is not None else nf.person(town.culture, sex, rng)
    q = base_quest(game, npc, "rescue", rng, hard=1.5, town=town)
    q["target"] = {"site": site.id, "captive": captive, "sex": sex, "holder": holder.id}
    q["words"].update(captive=captive, kin=kin, site=site.name, where=direction(town, site))
    allow_for(q, dist(site, town) * 2)
    return q


def _collect_debt_pick(game, npc, rng, town):
    """{"dest", "npc", "debt"}."""
    t = _someone_far(game, town, rng, 6, 30, jobs=("innkeeper", "smith", "shopkeeper", "headman", "stablemaster"))
    return None if t is None else {**t, "debt": rng.randint(20, 100) * 100}


def _collect_debt(game, npc, target, rng, town):
    w = game.world
    dest, who = w.settlements[target["dest"]], w.npcs[target["npc"]]
    debt = int(target.get("debt") or rng.randint(20, 100) * 100)
    q = base_quest(game, npc, "collect_debt", rng, town=town)
    q["reward"] = debt // 4
    q["target"] = {"dest": dest.id, "npc": who.id, "debt": debt, "collected": 0}
    q["words"].update(debtor=f"{who.name}, the {who.title}", debtor_name=who.name, dest=dest.name,
                      debt=money_text(debt))
    allow_for(q, dist(dest, town) * 2)
    return q


def _investigate_pick(game, npc, rng, town):
    """{"cult"}: the missing are taken somewhere a cart can reach in a night or two, not to a ruin a fortnight's walk
    away: a cult with a foothold in the town is the likeliest, but only if its hiding place is near enough."""
    w = game.world
    cults = [f for f in fx.active_factions(w, "cult") if 0 <= f.site < len(w.sites)
             and dist(w.sites[f.site], town) <= 30]
    if not cults:
        return None
    rooted = [f for f in cults if town.id in f.presence]
    return {"cult": rng.choice(rooted or cults).id}


def _investigate(game, npc, target, rng, town):
    w = game.world
    cult = w.factions[target["cult"]]
    site = w.sites[cult.site]
    q = base_quest(game, npc, "investigate", rng, town=town)
    q["target"] = {"site": site.id, "cult": cult.id, "asked": []}
    q["words"].update(site=site.name, where=direction(town, site), cult=cult.name)
    allow_for(q, dist(site, town) * 2)
    return q


def _slay_dragon_pick(game, npc, rng, town):
    """{"dragon"}: the one job a lord will not give to just anyone: it is a way of dying, for most."""
    from realmwalker.game import dragons

    w = game.world
    level = max(c.level for c in game.party) if game.party else 1
    desperate = bool(town.status.get("tribute") or town.status.get("burned"))
    if level < 4 and not (desperate and level >= 3):
        return None
    near = [d for d in dragons.living(w) if dist(w.sites[d["lair"]], town) <= 20
            and not any(q["target"].get("dragon") == d["name"] for q in _all_quests(game))]
    if not near:
        return None
    return {"dragon": min(near, key=lambda d: dist(w.sites[d["lair"]], town))["name"]}


def _slay_dragon(game, npc, target, rng, town):
    w = game.world
    d = next(d for d in w.politics.get("dragons", []) if d["name"] == target["dragon"])
    site = w.sites[d["lair"]]
    q = base_quest(game, npc, "slay_dragon", rng, hard=1.0, town=town)
    q["target"] = {"site": site.id, "dragon": d["name"]}
    q["words"].update(dragon=d["name"], colour=d.get("color", "great"), site=site.name,
                      where=direction(town, site))
    allow_for(q, dist(site, town) * 2)
    return q


RAIDER_GROUPS = {"tribe": ("orc_raiders", "goblin_warband", "orc_warband"), "bandit_gang": ("bandit_gang",),
                 "cult": ("cultists",)}


def _smuggle_pick(game, npc, rng, town):
    """A crate that must not be seen. Walled towns search travellers at the gate (game/law.py)."""
    return _someone_far(game, town, rng, 8, 35, jobs=("innkeeper", "shopkeeper", "market_trader", "smith"),
                        walled=True)


def _smuggle(game, npc, target, rng, town):
    w = game.world
    dest, who = w.settlements[target["dest"]], w.npcs[target["npc"]]
    q = base_quest(game, npc, "smuggle", rng, hard=1 + dist(dest, town) / 25, town=town)
    q["target"] = {"dest": dest.id, "npc": who.id}
    q["words"].update(recipient=f"{who.name}, the {who.title}", recipient_name=who.name, dest=dest.name,
                      where=direction(town, dest))
    allow_for(q, dist(dest, town))
    return q


def _defend_pick(game, npc, rng, town):
    """{"faction", "group", "when"}: they came last year, and they are coming again."""
    w = game.world
    if town.kind in ("city",):
        return None  # a city has walls and a watch of its own
    threats = [f for f in fx.active_factions(w, "tribe", "bandit_gang", "cult")
               if news_place(w, f) is not None and dist(_Spot(*news_place(w, f)), town) <= 25]
    if not threats:
        return None
    foe = rng.choice(threats)
    groups = [g for g in RAIDER_GROUPS.get(foe.kind, ()) if g in game.tables.creatures.encounters]
    if not groups:
        return None
    return {"faction": foe.id, "group": rng.choice(groups), "when": game.moment.total_days + rng.randint(3, 8)}


def _defend(game, npc, target, rng, town):
    """Be there on the day ("when": the day they come, if the target says)."""
    w = game.world
    foe = w.factions[target["faction"]]
    group = target.get("group") or next(g for g in RAIDER_GROUPS[foe.kind] if g in game.tables.creatures.encounters)
    when = int(target.get("when") or game.moment.total_days + rng.randint(3, 8))
    q = base_quest(game, npc, "defend", rng, hard=1.4, town=town)
    q["target"] = {"settlement": town.id, "group": group, "when": when, "faction": foe.id}
    q["days"] = when - game.moment.total_days + 2
    spot = news_place(w, foe)
    q["words"].update(raiders=foe.name, where=direction(town, _Spot(*spot)).split(" of ")[0] if spot else "the wild",
                      when=when_text(game, when))
    return q


def news_place(world, faction):
    from realmwalker.world import news as world_news

    return world_news.faction_place(world, faction)


def when_text(game, day: int) -> str:
    left = day - game.moment.total_days
    if left <= 1:
        return "tomorrow"
    if left <= 3:
        return f"in {left} days"
    return f"in {left} days, at the turn of the moon"


def _escort_pick(game, npc, rng, town):
    """{"dest", "npc"}: somebody of the town who has to get somewhere, and knows what the roads are like."""
    from realmwalker.game.people import npcs_in

    w = game.world
    dests = [s for s in w.settlements if s.id != town.id and 6 <= dist(s, town) <= 30]
    folk = [n for n in npcs_in(w, town.id) if n.alive and not n.notable and not n.flags.get("companion")
            and not n.flags.get("escort") and n.job not in ("guard", "beggar")]
    if not dests or not folk:
        return None
    dest = rng.choice(dests)
    return {"dest": dest.id, "npc": rng.choice(folk).id}


def _escort(game, npc, target, rng, town):
    w = game.world
    dest, who = w.settlements[target["dest"]], w.npcs[target["npc"]]
    q = base_quest(game, npc, "escort", rng, hard=1 + dist(dest, town) / 30, town=town)
    q["target"] = {"dest": dest.id, "npc": who.id}
    q["words"].update(traveller=who.name, dest=dest.name, where=direction(town, dest))
    allow_for(q, dist(dest, town))
    return q


def _grudge(game, npc):
    """The blood feud the history left this person (world/ages), or None."""
    from realmwalker.game import past

    fig = game.world.figures.get(npc.flags.get("figure", -1)) if npc is not None else None
    return past.grudge_of(game.world, fig.id) if fig is not None else None


def _vendetta_pick(game, npc, rng, town):
    """{"npc", "vendetta"}: the one who killed their kin still lives, and sits somewhere."""
    from realmwalker.game.people import prepare_town

    w = game.world
    grudge = _grudge(game, npc)
    if grudge is None:
        return None
    target = w.figures[grudge["against"]]
    if target.npc < 0 or target.npc not in w.npcs:
        f = w.factions.get(target.faction)
        if f is None or not f.active or f.leader != target.id or not 0 <= f.seat < len(w.settlements):
            return None
        prepare_town(game, w.settlements[f.seat])  # lords sit in their halls: placing the town seats them
    mark = w.npcs.get(target.npc) if target.npc >= 0 else None
    if mark is None or not mark.alive or mark.settlement == npc.settlement:
        return None
    return {"npc": mark.id, "vendetta": True}


def _assassinate_pick(game, npc, rng, town):
    """A knife in the dark, for money (a blood feud's, most often, when there is one). The law does not care who
    paid."""
    vendetta = _vendetta_pick(game, npc, rng, town)
    if vendetta is not None and rng.chance(0.8):
        return vendetta
    return _someone_far(game, town, rng, 4, 30)


def _assassinate(game, npc, target, rng, town):
    w = game.world
    mark = w.npcs[target["npc"]]
    dest = w.settlements[mark.settlement]
    grudge = _grudge(game, npc) if target.get("vendetta") else None
    q = base_quest(game, npc, "assassinate", rng, hard=(1.5 if grudge else 1) + dist(dest, town) / 30, town=town)
    q["target"] = {"dest": dest.id, "npc": mark.id}
    if grudge is not None:
        kin = w.figures.get(grudge["kin"])
        q["hidden"] = None  # no doubt about this one: it is true
        q["text_key"] = "assassinate_vendetta"
        q["words"].update(target=w.figures[grudge["against"]].full_name(), dest=dest.name,
                          where=direction(town, dest), relation=grudge["relation"],
                          kin=kin.full_name() if kin is not None else "my kin", cause=grudge.get("cause", ""))
    else:
        q["words"].update(target=mark.name, dest=dest.name, where=direction(town, dest))
    allow_for(q, dist(dest, town) * 2)
    return q


def _cure_pick(game, npc, rng, town):
    """{"count"}: the sickness is here, and the herbs are not."""
    if not town.status.get("plague") and not town.status.get("famine"):
        return None
    if "healing_herbs" not in game.tables.items:
        return None
    return {"count": rng.randint(4, 7)}


def _cure(game, npc, target, rng, town):
    q = base_quest(game, npc, "cure", rng, hard=1.2, town=town)
    q["target"] = {"count": int(target.get("count") or rng.randint(4, 7)), "item": "healing_herbs",
                   "settlement": town.id}
    q["words"].update(count=str(q["target"]["count"]))
    return q


def _feud_pick(game, npc, rng, town):
    """{"a", "b"}: two people who will not speak, and a town taking sides."""
    from realmwalker.game.people import npcs_in

    folk = [n for n in npcs_in(game.world, town.id) if n.alive and n.notable and (npc is None or n.id != npc.id)]
    if len(folk) < 2:
        return None
    one, two = rng.sample(folk, 2)
    return {"a": one.id, "b": two.id}


def _feud(game, npc, target, rng, town):
    w = game.world
    one, two = w.npcs[target["a"]], w.npcs[target["b"]]
    q = base_quest(game, npc, "feud", rng, town=town)
    q["target"] = {"a": one.id, "b": two.id, "agreed": []}
    q["words"].update(one=one.name, two=two.name)
    return q


STEAL_THINGS = [("a ledger", "ledger"), ("a bundle of letters", "letters"), ("a signet", "signet"),
                ("a deed of land", "deed"), ("a key", "key")]


def _steal_pick(game, npc, rng, town):
    """{"dest", "npc", "thing"}: something small, in somebody else's pocket."""
    w = game.world
    places = [s for s in w.settlements if dist(s, town) <= 25]
    rng.shuffle(places)
    for dest in places:
        mark = _someone_in(game, dest, rng)
        if mark is None or (npc is not None and mark.id == npc.id):
            continue
        return {"dest": dest.id, "npc": mark.id, "thing": rng.choice(STEAL_THINGS)[1]}
    return None


def _steal(game, npc, target, rng, town):
    w = game.world
    mark = w.npcs[target["npc"]]
    dest = w.settlements[mark.settlement]
    what, kind = next((t for t in STEAL_THINGS if t[1] == target.get("thing")), None) or rng.choice(STEAL_THINGS)
    q = base_quest(game, npc, "steal", rng, hard=1 + dist(dest, town) / 25, town=town)
    q["target"] = {"dest": dest.id, "npc": mark.id, "kind": kind}
    q["words"].update(item=what, mark=mark.name, dest=dest.name, where=direction(town, dest))
    allow_for(q, dist(dest, town) * 2)
    return q


KINDS = ("bounty", "slay_dragon", "escort", "assassinate", "cure", "feud", "steal", "defend", "smuggle", "clear_lair",
         "hunt_beast", "deliver", "retrieve", "rescue", "collect_debt", "investigate", "apprenticeship")
PICKERS = {k: globals()[f"_{k}_pick"] for k in KINDS}
MAKERS = {k: globals()[f"_{k}"] for k in KINDS}


def pick(game, kind: str, giver, rng: RNG, town=None) -> dict | None:
    """Today's choice of a target for this kind of work, set by this giver (or from this town), or None."""
    town = town or game.world.settlements[giver.settlement]
    target = PICKERS[kind](game, giver, rng, town)
    return None if target is None else {"kind": kind, "town": town.id, **target}


def make(game, giver, target: dict, rng: RNG) -> dict:
    """The quest dict for work on a target someone has chosen: its terms, its words, and days enough for the real
    walk. `giver` is the person setting it (None: the town's watch, `target["town"]`)."""
    w = game.world
    town = w.settlements[int(target["town"])] if target.get("town") is not None else w.settlements[giver.settlement]
    q = MAKERS[target["kind"]](game, giver, target, rng, town)
    allow_the_walk(game, q)
    return q


def build(game, giver, kind: str, rng: RNG, town=None) -> dict | None:
    """Pick, then make: work of this kind with today's target, or None when nothing near fits."""
    target = pick(game, kind, giver, rng, town)
    return None if target is None else make(game, giver, target, rng)


def _all_quests(game) -> list[dict]:
    """Work taken on and work waiting to be taken (so two pieces of work do not chase one thing)."""
    from realmwalker.game.story import work

    return list(game.quests) + work.waiting(game)


def board_bounties(game, settlement) -> list[dict]:
    """Bounties posted on the notice board here, paid by the town's watch: one for each gang within reach, and for
    the two nearest beasts of the history that lair within it (a threat's villain among them: taking that bounty
    opens its tale, story.on_job_taken)."""
    from realmwalker.game import past
    from realmwalker.game.people import town_of

    w = game.world
    town = town_of(w, settlement.id)
    posted = town.flags.setdefault("board", {})
    taken = {q["target"].get("gang") for q in active(game) if q["template"] == "bounty"}
    hunted = {q["target"].get("beast") for q in _all_quests(game) if q["template"] in ("hunt_beast", "clear_lair")}
    beasts = []
    done = cleared(game)
    for key, hid in sorted(w.politics.get("lairs", {}).items()):
        fig = w.figures.get(hid)
        if fig is None or not fig.alive or fig.kind != "beast" or fig.id in hunted or not 0 <= int(key) < len(w.sites):
            continue
        site = w.sites[int(key)]
        group = past.group_of(game, fig)
        # (the watch posts only what it might hope a traveller could kill, as anyone setting work does)
        if site.id not in done and 3 <= dist(site, settlement) <= 30 and \
                group in game.tables.creatures.encounters and beast_ratio(game, group) < DEADLY_RATIO:
            beasts.append((dist(site, settlement), site.id, fig.id, group))
    wild = []  # (the gangs' posters first, then the beasts')
    for _, sid, fid, group in sorted(beasts)[:2]:
        q = posted.get(f"beast{fid}")
        if q is None or q.get("state") != "offered":
            q = make(game, None, {"kind": "hunt_beast", "beast": fid, "site": sid, "group": group,
                                  "town": settlement.id}, w.rng.child(f"board/{settlement.id}/beast{fid}"))
            posted[f"beast{fid}"] = q
        wild.append(q)
    out = []
    for gang in fx.active_factions(w, "bandit_gang"):
        if not 0 <= gang.site < len(w.sites) or gang.site in cleared(game) or gang.id in taken:
            continue
        if dist(w.sites[gang.site], settlement) > 30:
            continue
        q = posted.get(str(gang.id))
        if q is None or q.get("state") != "offered":
            q = make(game, None, {"kind": "bounty", "gang": gang.id, "town": settlement.id},
                     w.rng.child(f"board/{settlement.id}/{gang.id}"))
            posted[str(gang.id)] = q
        out.append(q)
    return out + wild


# ---------------------------------------------------------------------------- taking it on
def accept(game, q) -> list[str]:
    from realmwalker.game.people import town_of
    from realmwalker.rules.inventory import add_existing

    if q.get("state") != "offered" or by_id(game, q["id"]) is not None:
        return []
    from realmwalker.game.story import work

    town = town_of(game.world, q["town"])
    pool = town.flags.get("board", {})
    for k, v in list(pool.items()):
        if v is q or v.get("id") == q["id"]:
            del pool[k]
    work.taken(game, q)
    q["state"] = "active"
    q["taken"] = game.moment.total_days
    q["deadline"] = game.moment.total_days + int(q["days"])
    q["journal"].append(fill(game, q, "journal"))
    game.quests.append(q)
    game.cue("quest")
    t = q["target"]
    w = game.world
    notes = [f"<info>Journal: {title(game, q)}.</> <dim>({terms(q)}; j for the journal)</>"]
    if "site" in t:
        s = w.sites[t["site"]]
        if not game.player.explored[s.x, s.y]:
            game.player.explored[s.x, s.y] = True
            notes.append(f"<info>{cap(s.name)} is on your map now.</>")
    if "dest" in t:
        game.player.known_settlements.add(t["dest"])
    if q["template"] == "hunt_beast":
        game.player.explored[t["x"], t["y"]] = True
        notes.append("<info>Where it was last seen is marked on your map.</>")
    if t.get("beast") is not None:
        from realmwalker.game import story

        story.on_job_taken(game, q)  # (a beast with a tale of its own: Expansion 6)
    if q["template"] == "escort":
        who = w.npcs.get(t["npc"])
        if who is not None:
            who.flags["escort"] = q["id"]
            who.present = False
            notes.append(f"<info>{who.name} gathers their things and falls in behind you.</>")
    if q["template"] == "smuggle":
        crate = Item(uid=0, def_id="sealed_crate", qty=1, made_at=w.time,
                     name=f"sealed crate for {q['words']['recipient_name']}",
                     tags=[f"quest:{q['id']}", "contraband"])
        add_existing(game.leader, game.tables.items, crate)
        notes.append("<loot>You take the crate. It is heavy, and it must not be seen at a gate.</>")
    if q["template"] == "deliver":
        letter = Item(uid=0, def_id="sealed_letter", qty=1, made_at=w.time,
                      name=f"sealed letter for {q['words']['recipient'].split(',')[0]}", tags=[f"quest:{q['id']}"])
        add_existing(game.leader, game.tables.items, letter)
        notes.append("<loot>You take the sealed letter.</>")
    if q["template"] == "investigate" and t["cult"] in w.factions:
        pass  # the cult stays unknown until you find it
    game.dirty = True
    return notes


def abandon(game, q) -> None:
    fail(game, q, "You gave it up.")
    q["state"] = "abandoned"


# ---------------------------------------------------------------------------- noticing progress
def mark_done(game, q, text: str | None = None) -> None:
    if q["done"] or q["state"] not in LIVE:
        return
    q["done"] = True
    q["state"] = "return"
    line = text or fill(game, q, "done")
    q["journal"].append(line)
    game.say(f"<good>Journal: {line}</>", "good")
    game.dirty = True


def reveal(game, q) -> None:
    if q.get("hidden") and not q.get("revealed"):
        q["revealed"] = True
        text = fill(game, q, "hidden", q["hidden"])
        q["journal"].append(text)
        game.say(f"<warn>{text}</>", "warn")


def at_site(game, site_id) -> bool:
    if site_id is None or not 0 <= site_id < len(game.world.sites):
        return False
    s = game.world.sites[site_id]
    return (game.player.x, game.player.y) == (s.x, s.y)


def boss_for(game, site, boss: str | None) -> str | None:
    """Who waits at the bottom: the site's usual master, unless a job says otherwise (the 'outlaws' who are
    really starving deserters)."""
    for q in active(game):
        if q["template"] == "bounty" and q.get("hidden") == "deserters" and q["target"].get("site") == site.id:
            if "deserters" in game.tables.creatures.encounters:
                return "deserters"
    return boss


def deepest(lm) -> bool:
    return lm is not None and lm.kind == "dungeon" and int(lm.meta.get("level", 1)) == int(lm.meta.get("depth", 1))


def boss_of(lm) -> str | None:
    from realmwalker.game.dungeon import BOSSES

    return lm.meta.get("boss") or BOSSES.get(lm.meta.get("style"))


def site_cleared(game, site_id: int) -> None:
    """The worst of a place is dead or gone: jobs that wanted it so are done, and the world remembers."""
    w = game.world
    done = w.politics.setdefault("cleared", [])
    if site_id not in done:
        done.append(site_id)
    for q in active(game):
        if q["target"].get("site") != site_id or q["done"]:
            continue
        if q["template"] in ("clear_lair", "bounty", "slay_dragon"):
            mark_done(game, q)
        elif q["template"] == "investigate":
            q["ended"] = True
            if not q["target"].get("found"):
                found_cult(game, q)


def defended(game, result) -> None:
    for q in active(game):
        if q["template"] == "defend" and not q["done"] and q["target"].get("spawned") and \
                at_settlement(game, q["target"].get("settlement")) and result.outcome in ("victory", "parley"):
            mark_done(game, q)


def on_battle(game, result, actor=None) -> None:
    """After a fight: a lair's master beaten, a gang's captain dead or taken, a named beast brought down —
    or somebody you were supposed to be keeping alive, dead."""
    if result.outcome not in ("victory", "parley"):
        for q in escorting(game):
            lost_escort(game, q, f"{q['words']['traveller']} did not survive the fight.")
        return
    defended(game, result)
    lm = game.local
    site = game.world.site_at(game.player.x, game.player.y)
    beaten = list(result.dead) + list(result.captives)
    if site is not None and actor is not None and deepest(lm) and actor.group == boss_of(lm) and \
            actor not in lm.actors:
        for q in active(game):
            if q["template"] == "bounty" and q["target"].get("site") == site.id and result.outcome == "parley":
                q["mercy"] = True
        site_cleared(game, site.id)
    elif site is not None and any(c.def_id == "bandit_captain" for c in beaten):
        for q in active(game):
            if q["template"] == "bounty" and q["target"].get("site") == site.id:
                mark_done(game, q)
    for q in active(game):
        if q["template"] == "hunt_beast" and not q["done"] and result.outcome == "victory":
            name = q["words"].get("beast")
            if any(c.name == name for c in beaten):
                mark_done(game, q)


def raid_due(game, q) -> bool:
    t = q["target"]
    return not t.get("spawned") and game.moment.total_days >= int(t.get("when", 0))


def at_settlement(game, sid) -> bool:
    if sid is None or not 0 <= sid < len(game.world.settlements):
        return False
    s = game.world.settlements[sid]
    return (game.player.x, game.player.y) == (s.x, s.y)


def spring_raid(game, q) -> bool:
    """The day has come and you are here: they come out of the trees."""
    from realmwalker.game.encounters import make_encounter

    if game.encounter is not None or game.battle is not None or game.busy:
        return False
    t = q["target"]
    rng = game.world.rng.child(f"raid/{q['id']}")
    enc = make_encounter(game, t["group"], rng)
    enc.intro = f"They come at dusk, out of the fields: {q['words'].get('raiders', 'raiders')}. " + enc.intro
    enc.spotted_first = True
    t["spawned"] = True
    game.encounter = enc
    game.travel = None
    game.say(f"<danger>{q['words'].get('raiders', 'Raiders')} are here.</>", "danger")
    return True


def raid_missed(game, q) -> None:
    """They came, and you were somewhere else."""
    from realmwalker.world import news

    w = game.world
    s = w.settlements[q["target"]["settlement"]]
    from realmwalker.world import marks

    day = news.now_days(w)
    marks.add(w, s, "raided", day, game.tables, until=day + 20, by=q["words"].get("raiders", ""))
    if s.kind in ("hamlet", "village") and w.rng.child(f"raid-burn/{q['id']}").chance(0.4):
        marks.add(w, s, "burned", day, game.tables)
        s.population = max(10, int(s.population * 0.75))
    news.add(w, f"{q['words'].get('raiders', 'raiders')} fell on {s.name}", s.x, s.y, kind="raid", importance=3,
             places=[s.id])
    fail(game, q)


def escorting(game) -> list[dict]:
    """Jobs whose traveller is walking with you right now."""
    return [q for q in active(game) if q["template"] == "escort" and not q["done"]]


def deliver_escort(game, q) -> None:
    """The traveller is where they wanted to be, and pays on the spot."""
    from realmwalker.game.people import town_of

    w = game.world
    who = w.npcs.get(q["target"]["npc"])
    dest = w.settlements[q["target"]["dest"]]
    if who is not None:
        old = town_of(w, who.settlement)
        if who.id in old.npcs:
            old.npcs.remove(who.id)
        who.settlement = dest.id
        who.present = True
        who.flags.pop("escort", None)
        who.post = who.home = (0, 0)
        who.building = -1
        town_of(w, dest.id).npcs.append(who.id)
    mark_done(game, q)
    for line in reward(game, q, text=f"{q['words']['traveller']} counts out {money_text(q['reward'])} at the gate, "
                                     f"and does not look back."):
        game.say(line, "good")


def lost_escort(game, q, why: str) -> None:
    who = game.world.npcs.get(q["target"]["npc"])
    if who is not None:
        who.alive = False
        who.flags.pop("escort", None)
    fail(game, q, why)


def on_arrive(game) -> None:
    """Walking onto a tile of the wide world: a hunted beast may be waiting there, a journey may end, or a
    village you promised to stand with may be about to be attacked."""
    p = game.player
    for q in active(game):
        if q["template"] == "defend" and not q["done"] and raid_due(game, q) and \
                at_settlement(game, q["target"].get("settlement")):
            spring_raid(game, q)
    for q in escorting(game):
        dest = game.world.settlements[q["target"]["dest"]]
        if (p.x, p.y) == (dest.x, dest.y):
            deliver_escort(game, q)
    if game.encounter is not None or game.battle is not None:
        return
    for q in active(game):
        t = q["target"]
        if q["template"] != "hunt_beast" or q["done"] or (p.x, p.y) != (t["x"], t["y"]) or "beast" in t:
            continue  # (a beast of the history waits at the bottom of its lair)
        from realmwalker.game.encounters import make_encounter

        rng = game.world.rng.child(f"beast/{q['id']}/{game.world.time}")
        enc = make_encounter(game, t["group"], rng)
        if enc.creatures:
            enc.creatures[0].name = q["words"]["beast"]
            enc.creatures[0].named = True
            enc.intro = f"This is where {q['words']['beast']} was seen. It is still here. " + enc.intro
            game.encounter = enc
            game.travel = None
        return


def on_arrive_dungeon(game, lm) -> None:
    """Going down into a place a job concerns: the deserters' camp, the heirloom's chest, the captive in chains,
    the cult's hidden temple."""
    site = game.world.site_at(game.player.x, game.player.y)
    if site is None:
        return
    for q in active(game):
        t = q["target"]
        if t.get("site") != site.id or q["done"]:
            continue
        tpl = q["template"]
        if tpl == "bounty" and q.get("hidden") == "deserters":
            reveal(game, q)
        if tpl == "investigate" and not t.get("found"):
            found_cult(game, q)
        if not deepest(lm):
            continue
        if tpl in ("retrieve", "apprenticeship") and not t.get("placed"):
            t["placed"] = place_in_room(game, lm, {"kind": "chest", "locked": 0, "treasure": 2, "quest": q["id"]},
                                        "chest")
        elif tpl == "rescue" and not t.get("placed"):
            t["placed"] = place_in_room(game, lm, {"kind": "captive", "quest": q["id"], "name": t["captive"]},
                                        "captive")
    if deepest(lm) and lm.populated and not lm.actors and site.id not in cleared(game):
        site_cleared(game, site.id)  # nothing left alive down here


def found_cult(game, q) -> None:
    from realmwalker.game.reputation import know

    t = q["target"]
    t["found"] = True
    know(game, t["cult"])
    mark_done(game, q)


def place_in_room(game, lm, feature: dict, terrain: str) -> bool:
    """Put a quest's thing in the last open room of the deepest level (where the master of the place waits)."""
    from realmwalker.game.dungeon import set_terrain

    rooms = lm.meta.get("rooms", [])
    if not rooms:
        return False
    hidden = set(lm.meta.get("hidden", []))
    open_rooms = [i for i in range(len(rooms)) if i not in hidden] or list(range(len(rooms)))
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken = {(a.x, a.y) for a in lm.actors}
    for i in reversed(open_rooms):
        rx, ry, rw, rh = rooms[i]
        cells = [(x, y) for y in range(ry, ry + rh) for x in range(rx, rx + rw)
                 if lm.in_bounds(x, y) and walk[x, y] and (x, y) not in lm.features and (x, y) not in taken
                 and (x, y) != tuple(lm.entry)]
        # against a wall, so it never blocks the way through the room
        edge = [(x, y) for x, y in cells if x in (rx, rx + rw - 1) or y in (ry, ry + rh - 1)]
        pool = edge or cells
        if pool:
            x, y = pool[len(pool) // 2]
            lm.features[(x, y)] = feature
            set_terrain(lm, x, y, terrain)
            return True
    return False


def quest_item(game, q) -> Item:
    """The thing a retrieve job is after, made when its chest is opened."""
    t = q["target"]
    w = game.world
    if "artifact" in t:
        from realmwalker.game import past

        it = past.artifact_item(game, t["artifact"])
    else:
        it = Item(uid=0, def_id=t.get("base", "gold_ring"), qty=1, made_at=w.time, name=t["item"])
    it.tags = list(it.tags) + [f"quest:{q['id']}"]
    return it


def on_chest(game, feature: dict) -> list[Item]:
    """Opening a chest that holds what a job is after."""
    q = by_id(game, feature.get("quest"))
    if q is None:
        return []
    item = quest_item(game, q)
    mark_done(game, q)
    return [item]


def free_captive(game, lm, x: int, y: int) -> None:
    """Walking into the chained captive."""
    from realmwalker.game.dungeon import set_terrain

    f = lm.features.pop((x, y), {})
    held = game.world.npcs.get(int(f["npc"])) if f.get("npc") is not None else None  # (a situation's captive: C.5)
    held = held if held is not None and held.alive else None
    q = by_id(game, f.get("quest"))
    name = f.get("name", "The captive")
    live = q is not None and q["state"] in LIVE
    if live or held is not None:
        from realmwalker.game import magic_items

        magic_items.notice(game, "rescue")
    if not live and held is None:
        set_terrain(lm, x, y, "bones")
        game.say(f"<warn>{name} is dead, still in the chains. You were too late.</>", "warn")
        return
    set_terrain(lm, x, y, "chains")
    game.say(f"<good>You break the chains. {name} is thin and filthy, but alive, and will follow you home.</>", "good")
    if live:
        q["target"]["freed"] = True
        mark_done(game, q)
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "mercy", "help_poor")
    if held is not None:
        held.flags.pop("captive", None)
        held.flags["with_party"] = True
        from realmwalker.game.story import goals

        goals.notify(game, "captive", "force", npc=held)


def on_pickpocket(game, npc) -> list[str]:
    """A hand in the right pocket: a job may be after what is in it."""
    out = []
    for q in active(game):
        if q["template"] == "steal" and q["target"].get("npc") == npc.id and not q["done"]:
            it = Item(uid=0, def_id="sealed_letter", qty=1, made_at=game.world.time,
                      name=q["words"]["item"], tags=[f"quest:{q['id']}"])
            from realmwalker.rules.inventory import add_existing

            add_existing(game.leader, game.tables.items, it)
            mark_done(game, q)
            out.append(f"<loot>Among the coins: {q['words']['item']}.</>")
            if q.get("hidden") == "framed":
                reveal(game, q)
    return out


def on_goods_seized(game) -> None:
    """The wardens took what you were carrying: any job that depended on it is over."""
    for q in active(game):
        if q["template"] in ("smuggle", "deliver") + FETCHED and not holds_quest_item(game, q) \
                and not q["done"]:
            fail(game, q, "The watch has it now.")


def on_npc_death(game, npc) -> None:
    """Someone has died: a job may have wanted exactly that, or the opposite."""
    for q in active(game):
        t = q["target"]
        if q["done"]:
            continue
        if q["template"] == "assassinate" and t.get("npc") == npc.id:
            mark_done(game, q)
        elif q["template"] == "escort" and t.get("npc") == npc.id:
            fail(game, q, f"{q['words']['traveller']} is dead.")
        elif q["template"] == "feud" and npc.id in (t.get("a"), t.get("b")):
            fail(game, q, "One of them is past making peace.")
        elif q["template"] in ("deliver", "collect_debt", "steal") and t.get("npc") == npc.id:
            fail(game, q, f"{npc.name} is dead, and that is the end of that.")


def herbs_held(game, q) -> int:
    kind = q["target"].get("item", "healing_herbs")
    from realmwalker.rules.inventory import carried

    return sum(it.qty for it in carried(game.party) if it.def_id == kind)


def take_herbs(game, q) -> None:
    from realmwalker.rules.inventory import remove_item

    left = int(q["target"].get("count", 0))
    for c in game.party:
        for it in list(c.inventory):
            if left <= 0:
                return
            if it.def_id == q["target"].get("item", "healing_herbs"):
                take = min(left, it.qty)
                remove_item(c, it.uid, take)
                left -= take


def holds_quest_item(game, q) -> bool:
    tag = f"quest:{q['id']}"
    return any(tag in it.tags for c in game.party for it in c.inventory)


def take_quest_item(game, q) -> None:
    from realmwalker.rules.inventory import remove_item

    tag = f"quest:{q['id']}"
    for c in game.party:
        for it in list(c.inventory):
            if tag in it.tags:
                if c.slot_of(it.uid) is not None:
                    from realmwalker.rules.inventory import unequip

                    unequip(c, c.slot_of(it.uid))
                remove_item(c, it.uid)


# ---------------------------------------------------------------------------- a companion's own business
# What a devoted companion finally asks you for, by what they want out of all this.
PERSONAL = {"revenge": ("bounty", "clear_lair"), "knowledge": ("retrieve", "investigate"),
            "cause": ("investigate", "clear_lair"), "loot": ("steal", "retrieve"),
            "pay": ("collect_debt", "bounty")}
PERSONAL_PREFACE = {
    "revenge": "\"I've never asked you for anything. I'm asking now.\"",
    "knowledge": "\"There is something I have wanted to see since before I met you.\"",
    "cause": "\"You know what I believe. Here is what it asks of us.\"",
    "loot": "\"A word. Quietly. There's something I've had my eye on.\"",
    "pay": "\"Before you ask: this one is mine, not yours.\"",
}


def devoted(game, c) -> bool:
    spec = game.tables.companions["loyalty"]
    return bool(c.companion) and float(c.companion.get("loyalty", 0)) >= float(spec["devoted"])


def personal_offer(game, c) -> dict | None:
    """The job a devoted companion asks you for, made once and then kept with them."""
    comp = c.companion
    if not comp or comp.get("personal_done") or not devoted(game, c):
        return None
    taken = comp.get("personal")
    if taken is not None:
        return by_id(game, taken)
    kept = comp.get("personal_offer")
    if kept is not None:
        return kept
    npc = game.world.npcs.get(comp.get("npc", -1))
    if npc is None:
        return None
    rng = game.world.rng.child(f"personal/{comp.get('npc')}/{game.moment.total_days}")
    want = comp.get("want", "pay")
    q = None
    from realmwalker.game.uniques import personal

    for template in personal(c, game.tables) or PERSONAL.get(want, ("bounty",)):
        q = make_offer(game, npc, rng, template)
        if q is not None:
            break
    if q is None:
        return None
    q["personal"] = comp.get("npc", -1)
    q["reward"] = max(10, q["reward"] // 2)  # a favour, not a contract
    q["giver_name"] = c.name
    q["words"]["giver"] = c.name.split()[0]
    comp["personal_offer"] = q
    return q


def personal_pitch(game, c, q) -> str:
    want = c.companion.get("want", "pay")
    return f"{PERSONAL_PREFACE.get(want, '')} {pitch(game, q)}".strip()


def accept_personal(game, c, q) -> list[str]:
    comp = c.companion
    comp.pop("personal_offer", None)
    comp["personal"] = q["id"]
    notes = accept(game, q)
    from realmwalker.game.companions import change_loyalty

    change_loyalty(c, 5)
    return notes


def refuse_personal(game, c) -> str:
    from realmwalker.game.companions import change_loyalty, first

    comp = c.companion
    comp.pop("personal_offer", None)
    comp["personal_done"] = True
    change_loyalty(c, -12)
    return f"{first(c)} says nothing for a while, and then talks about the weather."


def finish_personal(game, c, q) -> list[str]:
    """Telling a companion their own business is settled."""
    from realmwalker.game.companions import change_loyalty, first

    c.companion["personal_done"] = True
    change_loyalty(c, 20)
    out = reward(game, q, text=f"{first(c)} pays you {money_text(q['reward'])} out of their own purse, and you know "
                               f"better than to refuse it.")
    out.append(f"<good>{first(c)} will follow you anywhere now.</>")
    return out


# ---------------------------------------------------------------------------- the end of it
GIFT_GIVERS = ("lord", "priest", "headman")  # those with a strongroom, a vestry or a chest under the bed


def strongroom_gift(game, q, giver, share: float) -> list[str]:
    """DMG 2024 Quest Rewards: a roll on the hoard table with the party's level for the CR. The coin a village or a
    lord can pay is the reward in the terms; on top of it, for the great works (300 experience and more), a lord, a
    priest or a headman adds what the hoard row says in magic items, from their own strongroom."""
    s = spec(game)["templates"][q["template"]]
    if share < 1.0 or int(s["xp"]) < 300 or giver is None or giver.job not in GIFT_GIVERS:
        return []
    from realmwalker.game import treasure
    from realmwalker.rules.inventory import add_existing

    rng = game.world.rng.child(f"quest-gift/{q['id']}")
    level = max((c.level for c in game.party if c.alive), default=1)
    _lo, _hi, _expr, _times, magic = next((r for r in game.tables.treasure["hoard"] if level <= r[1]),
                                          game.tables.treasure["hoard"][-1])
    out = []
    for _ in range(treasure.magic_count(game, magic, rng)):
        it = treasure.magic_item(game, rng, treasure.rarity_for(game, level, rng), None)
        if it is None:
            continue
        add_existing(game.leader, game.tables.items, it)
        out.append(f"<loot>{giver.first_name} brings out something more, wrapped in cloth: "
                   f"{game.tables.items.name(it)}.</>")
    return out


def reward(game, q, *, share: float = 1.0, text: str | None = None) -> list[str]:
    if q.get("adventure"):
        from realmwalker.game import story

        story.on_quest_end(game, q, True)  # (a step of a tale: Expansion 6)
    from realmwalker.game import followers, reputation
    from realmwalker.game.companions import react
    from realmwalker.game.people import change_disposition
    from realmwalker.rules.progression import award_xp

    w = game.world
    s = spec(game)["templates"][q["template"]]
    money = int(q["reward"] * share)
    kept, shared = followers.on_reward(game, q, money)  # those who came for a share of it take theirs first
    game.leader.money += kept
    q["state"] = "finished"
    q["finished"] = game.moment.total_days
    game.cue("quest_done")
    amounts: dict[int, float] = {}
    if q["faction"] in w.factions:
        amounts[q["faction"]] = float(s["standing"]) * min(1.0, share)
    town = w.settlements[q["town"]]
    realm = fx.realm_of_settlement(w, town)
    if realm is not None and realm.id not in amounts:
        amounts[realm.id] = float(s["standing"]) / 2
    target = q["target"]
    if q["template"] == "bounty" and target.get("gang") in w.factions:
        amounts[target["gang"]] = -15.0
    if q["template"] == "investigate" and target.get("cult") in w.factions:
        amounts[target["cult"]] = -20.0
    # Quiet work is quiet: nobody puts it about that you killed a man or lifted a ledger for pay.
    covert = q["template"] in COVERT
    if covert:
        amounts = {q["faction"]: float(s["standing"])} if q["faction"] in w.factions else {}
    deed_text = (f"did quiet work for {q['giver_name']} of {town.name}" if covert else
                 f"did the work of {q['giver_name']} of {town.name}: {title(game, q)}")
    reputation.deed(game, deed_text, amounts, immediate=tuple(amounts),
                    fame=0 if covert else (2 if s["xp"] >= 200 else 1), infamy=1 if covert else 0, importance=1,
                    news_text=None if covert else
                    f"{game.leader.name} did the work of {q['giver_name']} of {town.name}")
    rng = w.rng.child(f"quest-xp/{q['id']}")
    notes = []
    for c in game.party:
        notes += award_xp(c, int(s["xp"] * min(1.0, share)), game.tables, rng)
    tags = TAGS.get(q["template"], ())
    if q.get("mercy"):
        tags = ("mercy",)
    if game.party[1:] and tags:
        react(game, *tags, quiet=True)
    giver = w.npcs.get(q["giver"])
    if giver is not None and giver.alive:
        change_disposition(giver, 20)
        giver.remember(f"the traveller did the work they asked ({title(game, q)})")
    freed = q["template"] == "rescue" and target.get("freed") and share >= 1.0
    if text:
        line = text
    else:
        rng2 = w.rng.child(f"quest-pay/{q['id']}")
        pattern = rng2.choice(spec(game)["rewards_text"])
        line = cap(textgen.fill(pattern, rng2, {}, {"giver": q["words"].get("giver", "They"),
                                                    "reward": money_text(money)}))
    q["journal"].append(line)
    out = [f"<good>{line}</> <dim>(+{int(s['xp'] * min(1.0, share))} experience each)</>"] + notes
    out += strongroom_gift(game, q, giver, share)
    if freed:
        from realmwalker.game.companions import grateful

        out += grateful(game, q)
    if q.get("trial") is not None and share >= 1.0:
        from realmwalker.game.reputation import confirm_rank

        said = confirm_rank(game, q["trial"])
        if said:
            q["journal"].append(said)
            out.append(f"<good>{said}</>")
    out += shared
    game.dirty = True
    return out


def fail(game, q, why: str | None = None) -> None:
    from realmwalker.game import reputation
    from realmwalker.game.people import change_disposition

    if q.get("adventure"):
        from realmwalker.game import story

        story.on_quest_end(game, q, False)

    q["state"] = "failed"
    line = why or fill(game, q, "failed")
    q["journal"].append(line)
    game.say(f"<warn>Journal: {title(game, q)} has failed.</> {line}", "warn")
    if q["faction"] in game.world.factions:
        reputation.change_standing(game, q["faction"], -3)
    giver = game.world.npcs.get(q["giver"])
    if giver is not None:
        change_disposition(giver, -15)
        giver.remember(f"the traveller let them down ({title(game, q)})")
    if q["template"] == "deliver":
        take_quest_item(game, q)
    if q["template"] == "escort":
        who = game.world.npcs.get(q["target"].get("npc", -1))
        if who is not None and who.alive:
            who.flags.pop("escort", None)
            who.present = True
            who.remember("was left on the road by the traveller")
    if q.get("personal") is not None:
        from realmwalker.game.companions import change_loyalty, companions

        for c in companions(game):
            if c.companion.get("personal") == q["id"]:
                c.companion["personal_done"] = True
                change_loyalty(c, -15)
                game.say(f"<warn>{c.name.split()[0]} will not talk about it.</>", "warn")
    from realmwalker.game import followers

    followers.on_fail(game, q)  # those who came along for a share of it
    game.dirty = True


def daily(game) -> None:
    """Deadlines, raids that fall due, and givers who are no longer there to pay."""
    today = game.moment.total_days
    for q in active(game):
        if q["template"] == "defend" and not q["done"] and raid_due(game, q):
            if at_settlement(game, q["target"].get("settlement")):
                spring_raid(game, q)
            elif today > int(q["target"].get("when", 0)):
                raid_missed(game, q)
    for q in active(game):
        giver = game.world.npcs.get(q["giver"])
        if q.get("personal") is None and q["giver"] >= 0 and (giver is None or not giver.alive) and                 not q.get("adventure"):  # (a step of a story: the story decides what a dead giver means)
            q["state"] = "finished"
            q["journal"].append(f"{q['giver_name']} is dead. Nobody will pay for this now.")
            game.say(f"<warn>Journal: {title(game, q)}: {q['giver_name']} is dead.</>", "warn")
            continue
        if not q["done"] and today > q.get("deadline", 10**9):
            fail(game, q)


def payer(game, q, npc) -> bool:
    """Is this the person to report to?"""
    if q.get("personal") is not None or q.get("unique"):
        return False  # you tell them yourself: on the party screen, or in their own words
    if q["giver"] >= 0:
        return npc.id == q["giver"]
    return npc.settlement == q["town"] and npc.job in AUTHORITY_JOBS


# ---------------------------------------------------------------------------- conversation
QUEST_CHOICES = {"own_work", "work_accept", "work_decline", "quest_turn_in", "deliver_letter", "show_letter",
                 "blackmail", "collect_debt", "debt_take", "debt_forgive", "ask_missing", "make_peace",
                 "buy_peace", "warn_target", "hand_over_goods", "deliver_goods"}


def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    game = conv.game
    npc = conv.npc
    if conv.mode == "quest_offer":
        return [Choice("work_accept", f"I'll do it. ({terms(conv.pending_offer)})"),
                Choice("work_decline", "Not now.")] if conv.pending_offer else []
    out = []
    here = npc.settlement
    for q in active(game):
        t = q["target"]
        tpl = q["template"]
        name = title(game, q)
        if q["done"] and payer(game, q, npc):
            if tpl in FETCHED and not holds_quest_item(game, q):
                out.append(Choice("quest_turn_in", f"About {name}...", False, "you don't have it with you",
                                  {"q": q["id"]}))
            elif tpl == "collect_debt" and game.leader.money < t.get("collected", 0):
                out.append(Choice("quest_turn_in", f"About {name}...", False, "you don't have the money any more",
                                  {"q": q["id"]}))
            elif tpl != "deliver":
                out.append(Choice("quest_turn_in", f"About {name}: it's done.", data={"q": q["id"]}))
        if tpl == "smuggle" and not q["done"] and holds_quest_item(game, q) and npc.id == t.get("npc"):
            out.append(Choice("deliver_goods", "I have your crate.", data={"q": q["id"]}))
        if tpl == "deliver" and not q["done"] and holds_quest_item(game, q):
            if npc.id == t.get("npc"):
                out.append(Choice("deliver_letter", "I have a letter for you.", data={"q": q["id"]}))
            elif q.get("revealed") and npc.id == q["giver"]:
                out.append(Choice("blackmail", "[Intimidation] I read your letter. What is it worth to you?",
                                  data={"q": q["id"]}))
            elif q.get("revealed") and here == q["town"] and npc.job in ("lord", "headman") and npc.id != q["giver"]:
                out.append(Choice("show_letter", f"There is a letter you should see, from {q['giver_name']}.",
                                  data={"q": q["id"]}))
        if tpl == "collect_debt" and not q["done"] and npc.id == t.get("npc"):
            if q.get("revealed"):
                out.append(Choice("debt_take", "Take what little there is.", data={"q": q["id"]}))
                out.append(Choice("debt_forgive", "Keep it. I'll tell them you paid what you could.",
                                  data={"q": q["id"]}))
            else:
                tried = t.get("tried") == game.moment.total_days
                out.append(Choice("collect_debt", f"[Persuasion or Intimidation] You owe {q['giver_name']} money.",
                                  not tried, "they will not hear of it again today", {"q": q["id"]}))
        if tpl == "feud" and not q["done"] and npc.id in (t.get("a"), t.get("b")) and \
                npc.id not in t.get("agreed", []):
            out.append(Choice("make_peace", f"[Persuasion] About {other_name(game, q, npc)}...",
                              data={"q": q["id"]}))
            price = peace_price(q)
            out.append(Choice("buy_peace", f"Offer {money_text(price)} to let it go.",
                              game.leader.money >= price, "you don't have that much", {"q": q["id"]}))
        if tpl == "assassinate" and not q["done"] and npc.id == t.get("npc"):
            reveal(game, q)  # face to face, you see what they are (if there is anything to see)
            if q.get("revealed"):
                out.append(Choice("warn_target", "Someone is paying to have you killed.", data={"q": q["id"]}))
        if tpl == "cure" and not q["done"] and payer(game, q, npc) and herbs_held(game, q) >= t.get("count", 0):
            out.append(Choice("hand_over_goods", "I have the herbs.", data={"q": q["id"]}))
        if tpl == "investigate" and not q["done"] and here == q["town"] and not npc.notable and \
                npc.id not in t.get("asked", []) and not t.get("clue"):
            out.append(Choice("ask_missing", "What do you know about the people going missing?", data={"q": q["id"]}))
    from realmwalker.game.story import work

    return out + work.choices(conv)  # (what they have for you: a commission, a plea)


def talk_choose(conv, choice) -> None:
    """Carry out a work-related choice. One small handler per choice (CHOICE_HANDLERS below)."""
    game = conv.game
    cid = choice.id
    if cid == "own_work":
        from realmwalker.game.story import work

        return work.offer(conv, choice)
    if cid in ("work_accept", "work_decline"):
        return _answer_offer(conv, cid)
    q = by_id(game, choice.data.get("q", -1))
    handler = CHOICE_HANDLERS.get(cid)
    if q is None or handler is None:
        return
    handler(conv, q)


def _answer_offer(conv, cid: str) -> None:
    q = conv.pending_offer
    conv.mode = "main"
    conv.pending_offer = None
    if cid == "work_decline" or q is None:
        conv.you_say("Not now.")
        return
    conv.you_say("I'll do it.")
    conv.npc_says(conv.rng.choice(["\"Good.\"", "\"Don't make me sorry.\"", "\"Then go. Time's short.\"",
                                   "\"I'll believe it when it's done.\""]))
    for text in accept(conv.game, q):
        conv.note(text)


def _turn_in(conv, q) -> None:
    """Telling whoever set the work that it is done, and being paid for it."""
    game, npc, t = conv.game, conv.npc, q["target"]
    conv.you_say("It's done.")
    share, text = 1.0, None
    if q["template"] in FETCHED:
        take_quest_item(game, q)
    elif q["template"] == "collect_debt":
        game.leader.money -= t.get("collected", 0)
        q["reward"] = t.get("collected", 0) // 4
        text = (f"You hand over {money_text(t.get('collected', 0))}; {npc.first_name} counts it and gives you "
                f"your quarter: {money_text(q['reward'])}.")
    elif q["template"] == "rescue":
        text = (f"{t['captive']} is home. {npc.first_name} cannot speak for a while, then presses "
                f"{money_text(q['reward'])} on you.")
    elif q["template"] == "investigate" and q.get("ended"):
        share = 1.5
    if q.get("mercy"):
        share = 0.5
        conv.npc_says("\"Gone, you say. Not dead. ... Well. Gone will do. Half, then.\"")
    else:
        conv.npc_says(conv.rng.choice(["\"Good. That's good.\"", "\"I didn't think you'd come back.\"",
                                       "\"Then it's paid for.\""]))
    for line in reward(game, q, share=share, text=text):
        conv.note(line)
    if q["template"] == "apprenticeship":
        for line in lesson(game, q, npc):
            conv.note(line)


def _deliver_letter(conv, q) -> None:
    from realmwalker.game.people import change_disposition

    game, npc = conv.game, conv.npc
    conv.you_say("I have a letter for you.")
    take_quest_item(game, q)
    q["done"] = True
    if q.get("opened"):
        change_disposition(npc, -15)
        conv.npc_says("\"This seal has been broken.\" A long look. \"Half. And be glad of it.\"")
        lines = reward(game, q, share=0.5,
                       text=f"{npc.first_name} pays you {money_text(q['reward'] // 2)}, and not kindly.")
    else:
        lines = reward(game, q, text=f"{npc.first_name} breaks the seal, reads, and pays you "
                                     f"{money_text(q['reward'])}.")
    for line in lines:
        conv.note(line)


def _deliver_goods(conv, q) -> None:
    game, npc = conv.game, conv.npc
    conv.you_say("I have your crate.")
    take_quest_item(game, q)
    mark_done(game, q)
    conv.npc_says("They look at the seal, not at you. \"Good. Forget the way here.\"")
    for line in reward(game, q, text=f"{npc.first_name} pays you {money_text(q['reward'])} in small coin."):
        conv.note(line)


def _show_letter(conv, q) -> None:
    """Taking an incriminating letter to the lord instead of its addressee."""
    from realmwalker.world import news

    game, npc = conv.game, conv.npc
    conv.you_say(f"There is a letter you should see, from {q['giver_name']}.")
    take_quest_item(game, q)
    giver = game.world.npcs.get(q["giver"])
    if giver is not None:
        giver.flags["disgraced"] = True
        giver.disposition = -80
        giver.remember("was betrayed to the law by the traveller")
    q["done"] = True
    q["faction"] = -1  # the giver's people will not thank you for this
    conv.npc_says("They read it twice. \"Leave this with me. And say nothing.\"")
    for line in reward(game, q, share=1.5,
                       text=f"{npc.first_name} pays you {money_text(int(q['reward'] * 1.5))} for your honesty."):
        conv.note(line)
    town = game.world.settlements[q["town"]]
    news.add(game.world, f"{q['giver_name']} of {town.name} was disgraced, on the word of a traveller",
             town.x, town.y, kind="crime", importance=2, places=[town.id])


def _blackmail(conv, q) -> None:
    game, npc, rng = conv.game, conv.npc, conv.rng
    sheet = game.sheet()
    conv.you_say("I read your letter. What is it worth to you?")
    roll = _cha(game, "intimidation", dice.d20(rng).natural) + sheet.skill_bonus("intimidation")
    if roll < BLACKMAIL_DC:
        conv.npc_says("\"Get out. Do what you like with it.\"")
        conv.note(f"<dim>(Intimidation {roll} vs {BLACKMAIL_DC})</>")
        return
    from realmwalker.game.companions import react

    paid = max(q["reward"], min(max(0, npc.purse), q["reward"] * 3))
    npc.purse = max(0, npc.purse - paid)
    game.leader.money += paid
    npc.disposition = -90
    npc.remember("was blackmailed by the traveller")
    take_quest_item(game, q)
    q["state"] = "finished"
    q["journal"].append(f"{q['giver_name']} paid {money_text(paid)} to have the letter back, and will hate you "
                        f"for it.")
    conv.npc_says("A long silence. Then the money, counted out with shaking hands.")
    conv.note(f"<loot>You get {money_text(paid)}.</> <dim>(Intimidation {roll})</>")
    react(game, "cruelty", "theft")


def _press_debt(conv, q) -> None:
    game, npc, t, rng = conv.game, conv.npc, q["target"], conv.rng
    sheet = game.sheet()
    conv.you_say(f"You owe {q['giver_name']} money.")
    if q.get("hidden") == "destitute" and not q.get("revealed"):
        reveal(game, q)
        conv.npc_says("\"Look around you. Does it look like I have it?\"")
        return
    t["tried"] = game.moment.total_days
    skill = max(("persuasion", "intimidation"), key=lambda s: sheet.skill_bonus(s))
    roll = _cha(game, skill, dice.d20(rng).natural) + sheet.skill_bonus(skill)
    if roll >= DEBT_DC:
        t["collected"] = t["debt"]
        game.leader.money += t["debt"]
        conv.npc_says("\"Fine. Take it. Tell them we're square.\"")
        conv.note(f"<loot>You collect {money_text(t['debt'])} for {q['giver_name']}.</> "
                  f"<dim>({skill.capitalize()} {roll})</>")
        mark_done(game, q)
    else:
        conv.npc_says("\"I'll pay when I can. Now get out.\"")
        conv.note(f"<dim>({skill.capitalize()} {roll} vs {DEBT_DC}; you can try again another day)</>")


def _debt_take(conv, q) -> None:
    from realmwalker.game.companions import react

    game, t = conv.game, q["target"]
    little = max(100, t["debt"] // 5)
    t["collected"] = little
    game.leader.money += little
    conv.note(f"You take {money_text(little)}, which is everything they have. Nobody looks at you as you go.")
    react(game, "cruelty")
    mark_done(game, q)


def _debt_forgive(conv, q) -> None:
    from realmwalker.game.companions import react
    from realmwalker.game.people import change_disposition

    game, npc = conv.game, conv.npc
    conv.note("You leave them what they have. You will have to tell the lender something.")
    react(game, "mercy", "charity", "help_poor")
    q["state"] = "finished"
    q["journal"].append(f"You let {q['words']['debtor']} keep what little they had. There is no pay for that.")
    change_disposition(npc, 30)


def _make_peace(conv, q) -> None:
    game, npc, t, rng = conv.game, conv.npc, q["target"], conv.rng
    sheet = game.sheet()
    conv.you_say(f"About {other_name(game, npc=npc, q=q)}...")
    roll = _cha(game, "persuasion", dice.d20(rng).natural) + sheet.skill_bonus("persuasion")
    dc = 13 + (2 if "proud" in npc.traits or "suspicious" in npc.traits else 0)
    if roll >= dc:
        t.setdefault("agreed", []).append(npc.id)
        conv.npc_says("\"... Fine. For you, and for the sake of the place. Not for them.\"")
        conv.note(f"<dim>(Persuasion {roll} vs {dc})</>")
        check_feud(game, q, conv)
    else:
        conv.npc_says("\"You don't know what they did. Don't come to me about it again.\"")
        conv.note(f"<dim>(Persuasion {roll} vs {dc})</>")


def _buy_peace(conv, q) -> None:
    from realmwalker.game.people import change_disposition

    game, npc, t = conv.game, conv.npc, q["target"]
    price = peace_price(q)
    if game.leader.money < price:
        return
    game.leader.money -= price
    npc.purse += price
    t.setdefault("agreed", []).append(npc.id)
    change_disposition(npc, 15)
    conv.note(f"You pay {money_text(price)}. It is remarkable what that settles.")
    check_feud(game, q, conv)


def _warn_target(conv, q) -> None:
    """Telling the person you were paid to kill who paid for it."""
    from realmwalker.game.companions import react
    from realmwalker.game.people import change_disposition

    game, npc = conv.game, conv.npc
    conv.you_say("Someone is paying to have you killed.")
    conv.npc_says("A long silence. \"Who?\"")
    q["state"] = "finished"
    q["journal"].append(f"You warned {q['words']['target']} instead of killing them. {q['giver_name']} will learn "
                        f"of it sooner or later.")
    paid = min(max(npc.purse, 0), q["reward"])
    npc.purse -= paid
    game.leader.money += paid
    change_disposition(npc, 40)
    npc.remember(f"was warned by the traveller that {q['giver_name']} wanted them dead")
    giver = game.world.npcs.get(q["giver"])
    if giver is not None:
        giver.disposition = -70
        giver.remember("was betrayed by the traveller")
    conv.note(f"<loot>{npc.first_name} gives you {money_text(paid)} and tells you to go.</>")
    react(game, "mercy")


def _hand_over_goods(conv, q) -> None:
    game, npc, t = conv.game, conv.npc, q["target"]
    conv.you_say("I have the herbs.")
    take_herbs(game, q)
    mark_done(game, q)
    settlement = game.world.settlements[t.get("settlement", q["town"])]
    settlement.status.pop("plague", None)
    conv.npc_says("\"Thank God. Thank you. Now go and wash your hands.\"")
    for line in reward(game, q, text=f"{npc.first_name} pays you {money_text(q['reward'])}, which is everything "
                                     f"the parish had."):
        conv.note(line)


def _ask_missing(conv, q) -> None:
    game, npc, t, rng = conv.game, conv.npc, q["target"], conv.rng
    conv.you_say("What do you know about the people going missing?")
    t.setdefault("asked", []).append(npc.id)
    if len(t["asked"]) >= 2 or rng.chance(0.3):
        t["clue"] = True
        conv.npc_says(fill(game, q, "clue"))
        site = game.world.sites[t["site"]]
        game.player.explored[site.x, site.y] = True
        q["journal"].append(f"The trail leads to {site.name}.")
        conv.note("<info>(It is on your map now.)</>")
    else:
        conv.npc_says(rng.choice(["\"Nothing. I don't know anything. Ask someone else.\"",
                                  "\"Keep your voice down. ... No. I can't.\"",
                                  "\"People leave. It's a hard place.\""]))


CHOICE_HANDLERS = {
    "quest_turn_in": _turn_in, "deliver_letter": _deliver_letter, "deliver_goods": _deliver_goods,
    "show_letter": _show_letter, "blackmail": _blackmail, "collect_debt": _press_debt,
    "debt_take": _debt_take, "debt_forgive": _debt_forgive, "make_peace": _make_peace, "buy_peace": _buy_peace,
    "warn_target": _warn_target, "hand_over_goods": _hand_over_goods, "ask_missing": _ask_missing,
}


def other_name(game, q=None, npc=None) -> str:
    """In a feud, the other one."""
    t = q["target"]
    other = t["b"] if npc.id == t.get("a") else t["a"]
    who = game.world.npcs.get(other)
    return who.name if who is not None else "them"


def peace_price(q) -> int:
    return max(200, int(q["reward"] * 0.4))


def check_feud(game, q, conv=None) -> None:
    t = q["target"]
    if len(set(t.get("agreed", []))) >= 2:
        mark_done(game, q)
        if conv is not None:
            conv.note("<good>That is both of them. Tell whoever asked.</>")


def read_letter(game, it) -> list[str]:
    """Breaking the seal on a letter you carry for someone."""
    qid = next((int(tag.split(":")[1]) for tag in it.tags if tag.startswith("quest:")), None)
    q = by_id(game, qid)
    if q is None or q["template"] != "deliver":
        return ["There is nothing more to it."]
    first = not q.get("opened")
    q["opened"] = True
    if it.name.startswith("sealed "):
        it.name = "opened " + it.name.removeprefix("sealed ")
    if q.get("hidden") == "incriminating":
        if first:
            reveal(game, q)
        return [f"<warn>{fill(game, q, 'hidden', 'incriminating')}</>"] if not first else []
    return [f"You break the seal. It is dull business between {q['giver_name']} and {q['words']['recipient']}: "
            f"money, grain and a wedding. The broken seal will show."]


