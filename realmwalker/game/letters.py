"""Letters as pages (Expansion 6 B.2, docs/ADVENTURES.md §8.12): a letter, a note or an order that the story puts in
your hand is a page in its writer's hand, sealed in their colours, kept so it opens again from the pack.

A letter is a record in `world.politics["letters"]` {id: {"from", "hand", "seal", "lines", "key", "read", "day",
"ink" (a writer's own: a villain's, E.2), "sigil" (what is pressed into its wax: SIGILS, E.7)}}
(JSON-native, saved with the world) and an item carrying the tag `letter:<id>` (the `quest:<id>` pattern: items have
tags, not free data). `game.letter` (not saved) is the letter waiting to be shown: the game screen opens its page.

    write(game, sender=, lines=, hand=, seal=, key=, ink=, sigil=)   a new letter's record; its id
    give(game, lid, item_id="sealed_letter")          into the leader's pack
    of_item(game, item)                                the record an item carries, or None
    show(game, lid)                                    the page opens (and the letter is read)
    hand_for(kind)                                     the hand a kind of writer writes in
"""

from __future__ import annotations

HANDS = ("plain", "fine", "dark")  # a farmer's or a miller's wife's; a lord's or a priest's; a villain's
SEALS = {"plain": (150, 40, 32), "fine": (120, 30, 60), "dark": (62, 50, 66)}
SIGILS = ("mark", "sun", "key", "skull", "crown", "tear")  # (pressed into the wax: a villain's by its temper, E.7)


def records(world) -> dict:
    return world.politics.setdefault("letters", {})


def hand_for(kind: str) -> str:
    """The hand a writer writes in: villains and the dead in a dark hand, lords, priests and scribes a fine one,
    everyone else a plain one."""
    if kind in ("villain", "beast", "cult", "dead", "dark"):
        return "dark"
    if kind in ("lord", "priest", "scribe", "mage", "headman", "noble", "fine"):
        return "fine"
    return "plain"


def write(game, *, sender: str, lines: list[str], hand: str = "plain", seal=None, key: int | None = None,
          ink=None, sigil: str | None = None) -> str:
    recs = records(game.world)
    lid = f"L{len(recs) + 1}"
    while lid in recs:
        lid = f"L{int(lid[1:]) + 1}"
    hand = hand if hand in HANDS else "plain"
    recs[lid] = {"from": sender, "hand": hand, "seal": list(seal or SEALS[hand]), "lines": [str(x) for x in lines],
                 "key": key, "read": False, "day": int(game.moment.total_days)}
    if ink:  # (a writer's own ink: the villain's, Expansion 6 E.2)
        recs[lid]["ink"] = [int(v) for v in ink][:3]
    if sigil in SIGILS and sigil != "mark":
        recs[lid]["sigil"] = sigil
    return lid


def give(game, lid: str, item_id: str = "sealed_letter"):
    from realmwalker.rules.inventory import add_item

    return add_item(game.leader, game.tables.items, item_id, 1, made_at=game.world.time, tags=[f"letter:{lid}"])


def lid_of(item) -> str | None:
    return next((tag.split(":", 1)[1] for tag in getattr(item, "tags", []) if tag.startswith("letter:")), None)


def of_item(game, item) -> dict | None:
    lid = lid_of(item)
    return records(game.world).get(lid) if lid else None


def show(game, lid: str) -> None:
    """The letter's page opens (the game screen shows it as soon as nothing else waits)."""
    if lid in records(game.world):
        game.letter = lid


def mark_read(game, lid: str) -> bool:
    """The page has been seen: True the first time."""
    rec = records(game.world).get(lid)
    if rec is None or rec["read"]:
        return False
    rec["read"] = True
    game.cue("seal")  # (the seal broken, the page opened out: Expansion 6 D.5)
    return True
