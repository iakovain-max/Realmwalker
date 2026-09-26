"""The party's one pack (after v1): everyone travelling together carries from the same pack, and the weight is
shared out over all of them, so nobody hands arrows to the archer or balances loads by hand.

The rules are in rules/inventory.py (the shared list, who wears what) and rules/character.py (Sheet.pack_load and
pack_capacity). This keeps the party in step: `sync(game)` is called whenever someone joins, leaves or dies, when a
game is made or loaded, and as time passes, and it only does anything when the party has changed.

- Someone who joins pours what they carry into the pack; what they wear stays on them.
- Someone who is told to wait, is sent away or deserts takes what they wear and wield, and nothing else.
- Someone who dies leaves everything to the rest (you take their gear from the body).
"""

from __future__ import annotations

from realmwalker.rules.inventory import merge_into, take_out


def sync(game) -> None:
    party = getattr(game, "party", None)
    if not party:
        return
    leader = party[0]
    shared = leader.inventory
    members = [c for c in party if c is leader or c.alive]
    before = getattr(game, "_pack_members", [])
    if len(before) == len(members) and all(a is b for a, b in zip(before, members)) and \
            all(c.inventory is shared for c in members):
        return
    # Those who are no longer with the party take their gear (the dead leave it).
    for c in before:
        if not any(c is m for m in members) and c.inventory is shared and c is not leader:
            take_out(c, keep_gear=c.alive)
    for c in party:
        if c is not leader and not c.alive and c.inventory is shared:
            take_out(c, keep_gear=False)
    for c in members[1:]:
        merge_into(shared, c, game.tables.items)
    for c in members:
        c._pack_mates = members
    game._pack_members = members
