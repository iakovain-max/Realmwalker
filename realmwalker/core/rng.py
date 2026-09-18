"""The one seeded random generator. All game randomness goes through an RNG owned by the world.

Independent sub-streams (`rng.child("local_map/12,40")`) are derived from the seed and a name,
so generating one thing never shifts the dice for another, and any bug can be reproduced
from the seed alone.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from typing import Any, TypeVar

import numpy as np

T = TypeVar("T")


def derive_seed(seed: int, stream: str) -> int:
    digest = hashlib.blake2b(f"{seed}:{stream}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little")


class RNG:
    def __init__(self, seed: int, stream: str = "root") -> None:
        self.seed = int(seed)
        self.stream = stream
        self._r = random.Random(derive_seed(self.seed, stream))

    def child(self, name: str) -> RNG:
        """An independent, reproducible generator for one purpose."""
        return RNG(self.seed, f"{self.stream}/{name}")

    def numpy(self, name: str = "np") -> np.random.Generator:
        """A numpy generator for map arrays, derived from this stream."""
        return np.random.default_rng(derive_seed(self.seed, f"{self.stream}/{name}"))

    # --- draws -------------------------------------------------------------
    def random(self) -> float:
        return self._r.random()

    def randint(self, low: int, high: int) -> int:
        """Inclusive on both ends, like a die."""
        return self._r.randint(low, high)

    def uniform(self, low: float, high: float) -> float:
        return self._r.uniform(low, high)

    def gauss(self, mu: float, sigma: float) -> float:
        return self._r.gauss(mu, sigma)

    def chance(self, probability: float) -> bool:
        return self._r.random() < probability

    def choice(self, items: Sequence[T]) -> T:
        if not items:
            raise IndexError("choice from an empty list")
        return items[self._r.randrange(len(items))]

    def weighted(self, items: Sequence[T], weights: Sequence[float]) -> T:
        return self._r.choices(items, weights=weights, k=1)[0]

    def sample(self, items: Sequence[T], k: int) -> list[T]:
        return self._r.sample(list(items), min(k, len(items)))

    def shuffle(self, items: list[Any]) -> None:
        self._r.shuffle(items)

    # --- saving ----------------------------------------------------------------
    def get_state(self) -> dict:
        version, internal, gauss_next = self._r.getstate()
        return {"seed": self.seed, "stream": self.stream, "state": [version, list(internal), gauss_next]}

    @classmethod
    def from_state(cls, data: dict) -> RNG:
        rng = cls(data["seed"], data["stream"])
        version, internal, gauss_next = data["state"]
        rng._r.setstate((version, tuple(internal), gauss_next))
        return rng
