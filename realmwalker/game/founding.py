"""Founded places in play (Expansion 6 G.9): the game's side of world/founding.py.

A founded camp's close-up map is laid out for the stage it had when it was built (`lm.meta["founded_stage"]`, set by
`world/local.get_local_map`). When the camp has grown since (a palisade, timber halls; a village at last), the map is
laid out again the next time the party comes (`before_entry`, from `GameState.enter_local` and
`people.prepare_town`): the old map goes, and with it the camp's folk of the old stage, who move on (as travellers
do: `flags["moved_on"]`) so that the place fills again for what it now is. That waits while anyone there is tied to
the player - a companion, someone a story or a work is about, someone grateful - so nobody the player knows
vanishes; until then the old map stands.

    before_entry(game, x, y) -> bool    lay out a grown camp's map again (True if it was)
    free(game, s) -> bool               may this place's folk move on?
"""

from __future__ import annotations

TIES = ("companion", "story", "grateful")


def free(game, s) -> bool:
    from realmwalker.game.people import npcs_in

    folk = npcs_in(game.world, s.id)
    if any(n.flags.get(t) for n in folk for t in TIES):
        return False
    ids = {n.id for n in folk}
    for q in getattr(game, "quests", ()) or ():
        if q.get("state") not in ("offered", "active"):
            continue
        target = q.get("target") or {}
        if q.get("giver") in ids or target.get("npc") in ids:
            return False
    return True


def before_entry(game, x: int, y: int) -> bool:
    from realmwalker.game.people import npcs_in
    from realmwalker.world import founding
    from realmwalker.world.local import local_key

    w = game.world
    s = w.settlement_at(x, y)
    if s is None:
        return False
    rec = founding.record_of(w, s.id)
    key = local_key(x, y)
    lm = w.local_maps.get(key)
    if rec is None or lm is None or int(lm.meta.get("founded_stage", 0)) == int(rec["stage"]):
        return False
    if game.local is lm or not free(game, s):
        return False
    w.local_maps.pop(key, None)
    game._remaps.pop(key, None)
    for n in npcs_in(w, s.id):  # (they move on: the place fills again for what it has become)
        n.alive = False
        n.present = False
        n.flags["moved_on"] = True
    w.towns.pop(s.id, None)
    from realmwalker.game import townlife

    townlife.forget()
    return True
