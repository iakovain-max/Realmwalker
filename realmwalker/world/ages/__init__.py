"""The ages: a world's history, lived year by year when the world is made (after Dwarf Fortress's world generation).

The land is made first (world/generator.py). Then the years are lived: peoples found towns, kingdoms rise, marry,
quarrel and go to war; monsters come out of the wild and heroes go after them; prophets and heretics, smiths and
bards leave their marks. Whatever is standing at the end is the world the player walks into. See
docs/WORLD_HISTORY.md for the design.

Pure logic: no UI. Everything random comes from the RNG it is given.
"""

from realmwalker.world.ages.sim import AgeSim, live_the_ages

__all__ = ["AgeSim", "live_the_ages"]
