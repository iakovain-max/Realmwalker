"""Mage Hand Legerdemain on the road (Expansion 4 Part B): an Arcane Trickster's unseen hand does the thieving.

A trickster in the party who knows Mage Hand needs no casting first: the hand is cast with a bonus action and nobody
sees it. Through it they make the Sleight of Hand check (their own bonus, with Advantage as Mage Hand gives a stall
theft) from 30 feet away, so:
- a stall's wares (`law.steal_from_shop`): whoever sees the thing go sees no thief; a failure only drops the thing;
- a purse (`law_talk.pickpocket`): the victim feels a tug and sees nobody; no witness can name the thief.
"""

from __future__ import annotations


def trickster(game):
    """The party member whose unseen hand would do it (the best at Sleight of Hand), or None."""
    who = [c for c in game.party if c.alive and "mage_hand_legerdemain" in c.features
           and "mage_hand" in (c.spells or {}).get("cantrips", ())]
    if not who:
        return None
    return max(who, key=lambda c: (game.sheet(c).skill_bonus("sleight_of_hand"), -game.party.index(c)))


def first(c) -> str:
    return c.name.split()[0]
