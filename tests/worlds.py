"""Worlds for tests, made once and kept (in memory, and on disk under build/test_worlds) while the code and data that
make them stay the same.

Making a world lives its whole history and takes one to six seconds; the suite needs about eighty of them, most of them
the same ones run after run. `cached_world(options, tables)` returns a fresh copy of the world those options make,
from the cache when the world-making code and the data are unchanged, else made now (and kept). Tests that test the
making itself (determinism, speed) call WorldGenerator directly instead.

What counts as "the code that makes worlds": every realmwalker module a world's making imports (measured: the world,
core, data and rules packages and paths.py). If the making ever imports a module outside them, the cache notices,
says so once, and stops being used, so it can never hand back a world made by older code.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path

from realmwalker.world.generator import WorldGenerator, WorldOptions

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "build" / "test_worlds"
COVERED = ("realmwalker/world/", "realmwalker/core/", "realmwalker/data/", "realmwalker/rules/", "realmwalker/paths.py",
           "realmwalker/__init__.py")

_memory: dict[str, bytes] = {}
_code_hash: str | None = None
_enabled = True


def _code_fingerprint() -> str:
    global _code_hash
    if _code_hash is None:
        h = hashlib.sha256()
        for path in sorted((ROOT / "realmwalker").rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(COVERED):
                h.update(rel.encode())
                h.update(path.read_bytes())
        _code_hash = h.hexdigest()
    return _code_hash


def _data_fingerprint(tables) -> str:
    files = getattr(tables.data, "_files", None)
    blob = json.dumps(files, sort_keys=True, default=str).encode() if files is not None else repr(id(tables)).encode()
    return hashlib.sha256(blob).hexdigest()


def _covered_modules_only(before: set[str]) -> bool:
    """True if a world's making imported nothing outside the code the fingerprint covers."""
    for name in set(sys.modules) - before:
        if not name.startswith("realmwalker"):
            continue
        file = getattr(sys.modules[name], "__file__", None)
        if file is None:
            continue
        rel = Path(file).resolve().relative_to(ROOT).as_posix()
        if not rel.startswith(COVERED):
            print(f"tests/worlds.py: making a world imported {rel}, which the cache does not watch; "
                  f"the world cache is off for this run (add it to COVERED)", file=sys.stderr)
            return False
    return True


def cached_world(options: WorldOptions, tables):
    """A fresh copy of the world these options make (see the module's notes)."""
    global _enabled
    if not _enabled:
        return WorldGenerator(options, tables).generate()
    key = hashlib.sha256(f"{options!r}|{_code_fingerprint()}|{_data_fingerprint(tables)}".encode()).hexdigest()[:32]
    blob = _memory.get(key)
    path = CACHE_DIR / f"{key}.pickle"
    if blob is None and path.exists():
        try:
            blob = path.read_bytes()
        except OSError:
            blob = None
    if blob is not None:
        try:
            # Only ever files this module wrote itself, in the git-ignored build folder of this checkout.
            world = pickle.loads(blob)
            _memory[key] = blob
            return world
        except Exception:
            blob = None
    before = set(sys.modules)
    world = WorldGenerator(options, tables).generate()
    if not _covered_modules_only(before):
        _enabled = False
        return world
    blob = pickle.dumps(world, protocol=pickle.HIGHEST_PROTOCOL)
    _memory[key] = blob
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{id(blob)}.tmp")
        tmp.write_bytes(blob)
        tmp.replace(path)  # atomic: parallel workers making the same world do not trip over each other
    except OSError:
        pass
    return world
