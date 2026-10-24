"""The cast of an adventure (docs/ADVENTURES.md §5.3): roles bound to real people, found in the world first.

A role's record is one of {"npc": id} (a townsperson), {"figure": id} (a figure of the history), {"settlement": id}
(a whole village, as an innocent), or, while their town has never been filled with people, {"job", "settlement"}:
forging never builds a town map, so the person is chosen (or made) the first time the town is populated
(`place_people`, from people.populate_town) and kept in `politics["story_people"]` until then. A bound person carries
`flags["story"]` {adv, role}: they are not moved on as travellers, and their jobs are not failed for their absence.

The people selectors (headman_of, priest_of, hunter_of...) return such specs; they register in the selector
registry like the place selectors.
"""

from __future__ import annotations

from realmwalker.game.story.selectors import selector

# What each people selector looks for, in order (data/people.json occupations).
JOBS = {
    "headman_of": ("headman", "lord", "elder"),
    "lord_of": ("lord", "headman"),
    "priest_of": ("priest", "preacher", "monk"),
    "notable_of": ("headman", "elder", "lord", "innkeeper", "priest"),
    "hunter_of": ("woodcutter", "herder", "farmer"),
    "kin_of_victim": ("farmer", "herder", "washerwoman", "labourer"),
    "survivor_of": ("herder", "farmer", "carter", "woodcutter", "labourer"),
}


def _people_selector(name: str):
    jobs = JOBS[name]

    def pick(forge, town):
        if not town or "settlement" not in town:
            return []
        return [{"job": jobs[0], "jobs": list(jobs), "settlement": int(town["settlement"])}]
    pick.__doc__ = f"A person of the town: {', '.join(jobs)}."
    selector(name)(pick)


for _name in JOBS:
    _people_selector(_name)


@selector("settlement")
def _settlement(forge, town):
    """A whole village (the innocent who suffers if you fail)."""
    return [{"settlement": int(town["settlement"])}] if town and "settlement" in town else []


# ---------------------------------------------------------------------------- binding people
def person(world, entry: dict | None):
    """The townsperson or figure a role is bound to, or None (not yet placed, or a village, or gone)."""
    if not entry:
        return None
    if "npc" in entry:
        return world.npcs.get(int(entry["npc"]))
    if "figure" in entry:
        return world.figures.get(int(entry["figure"]))
    return None


def pending(entry: dict | None) -> bool:
    return bool(entry) and "job" in entry and "npc" not in entry


def bind_now(game, adv: dict, role: str, entry: dict) -> dict:
    """Bind a person role at once if their town has its people already, else keep it for when it does."""
    w = game.world
    sid = int(entry["settlement"])
    town = w.towns.get(sid)
    if town is not None and town.npcs:
        npc = _choose(game, sid, entry, adv)
        if npc is not None:
            return _take(npc, adv, role, entry)
    w.politics.setdefault("story_people", {}).setdefault(f"S{sid}", []).append(
        {"adv": adv["id"], "role": role, "jobs": list(entry.get("jobs", [entry["job"]]))})
    return dict(entry)


def _taken(world, npc) -> bool:
    return bool(npc.flags.get("story"))


def _choose(game, sid: int, entry: dict, adv: dict):
    from realmwalker.game.people import npcs_in

    folk = [n for n in npcs_in(game.world, sid) if n.alive and not _taken(game.world, n)]
    for job in entry.get("jobs", [entry["job"]]):
        found = sorted((n for n in folk if n.job == job), key=lambda n: n.id)
        if found:
            return found[0]
    adults = sorted((n for n in folk if n.job not in ("child", "guard")), key=lambda n: n.id)
    return adults[0] if adults else None


def _take(npc, adv: dict, role: str, entry: dict) -> dict:
    npc.flags["story"] = {"adv": adv["id"], "role": role}
    return {"npc": int(npc.id), "settlement": int(entry["settlement"]), "job": npc.job}


def place_people(game, town, settlement) -> None:
    """A town is filled with people for the first time: the roles waiting for it are bound to its folk."""
    w = game.world
    waiting = w.politics.get("story_people", {}).pop(f"S{settlement.id}", [])
    advs = w.politics.get("adventures", {})
    for rec in waiting:
        adv = advs.get(rec["adv"])
        if adv is None or adv.get("state") != "active":
            continue
        entry = adv["cast"].get(rec["role"]) or {"settlement": settlement.id, "job": rec["jobs"][0]}
        npc = _choose(game, settlement.id, dict(entry, jobs=rec["jobs"]), adv)
        if npc is not None:
            adv["cast"][rec["role"]] = _take(npc, adv, rec["role"], entry)
        _rebind_steps(adv, rec["role"], adv["cast"][rec["role"]])


def _rebind_steps(adv: dict, role: str, entry: dict) -> None:
    """Steps and routes that name a role see the person now bound to it."""
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            t = st["target"]
            if t.get("role") == role:
                t["who"] = dict(entry)
            for r in t.get("routes", []):
                if r.get("role") == role:
                    r["who"] = dict(entry)


def describe(game, adv: dict, role: str) -> str:
    """A role in words: their name if known, else what they are ("the headman of Coldwell")."""
    w = game.world
    entry = adv["cast"].get(role)
    who = person(w, entry)
    if who is not None:
        return who.name if hasattr(who, "job") else who.full_name()
    if entry and "settlement" in entry:
        s = w.settlements[int(entry["settlement"])]
        if "job" in entry:
            job = game.tables.people["occupations"].get(entry["job"], {}).get("name", entry["job"])
            return f"the {job} of {s.name}"
        return s.name
    return "someone"
