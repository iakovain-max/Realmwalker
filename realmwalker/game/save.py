"""Saving and loading. Versioned, compressed, and written safely (to a temp file, then swapped in).

Layout on disk (%APPDATA%\\Realmwalker\\saves\\<world id>\\):
  world.zip      the world: arrays (.npy), settlements, sites, areas, local maps, clock, flavour text
  character.zip  the living character: position, knowledge, message log
The world outlives characters: when a character dies only character.zip is removed (M9).

Each zip holds manifest.json with a format number. Older formats are upgraded by MIGRATIONS
when loaded, so game updates do not break existing saves. Arrays are stored as plain numeric
.npy data (numpy's loader refuses anything executable by default); everything else is JSON.
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import os
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from realmwalker import __version__
from realmwalker.ai.store import FlavorStore
from realmwalker.core.rng import RNG
from realmwalker.game.encounters import LocalActor
from realmwalker.game.people import NPC, Town
from realmwalker.game.log import MessageLog
from realmwalker.game.state import GameState, PlayerState
from realmwalker.rules.character import Character
from realmwalker.rules.items import Item
from realmwalker.world.factions import Faction, Figure
from realmwalker.world.local import Building, LocalMap
from realmwalker.world.model import ARRAY_NAMES, Area, Settlement, Site, World, WorldMeta
from realmwalker.world.tables import Tables

log = logging.getLogger("realmwalker.save")

FORMAT_VERSION = 6
WORLD_FILE = "world.zip"
CHARACTER_FILE = "character.zip"

def _v1_to_v2(kind: str, body: dict) -> dict:
    """Format 2 added characters (M2). Older saves get the default wanderer when loaded."""
    if kind == "character":
        body = dict(body)
        body.setdefault("party", None)
    return body


def _v2_to_v3(kind: str, body: dict) -> dict:
    """Format 3 added the body over time (needs, body heat, exhaustion, blood, diseases, injuries) and
    waterskin contents (M4). Missing fields take their defaults when characters and items load."""
    return body


def _v3_to_v4(kind: str, body: dict) -> dict:
    """Format 4 added townsfolk and towns to the world (M5). Older worlds start with nobody known; settlement
    maps made before M5 have no shops or stables, but their people are made on the next visit."""
    if kind == "world":
        body = dict(body)
        body.setdefault("npcs", [])
        body.setdefault("towns", [])
        body.setdefault("next_npc_id", 0)
    return body


def _v4_to_v5(kind: str, body: dict) -> dict:
    """Format 5 added animals (mules and horses) to characters and shop stock to towns (M5). Missing fields take
    their defaults."""
    return body


def _v5_to_v6(kind: str, body: dict) -> dict:
    """Format 6 added factions, history, wars and news to the world, and reputation to the character (M6).
    Older worlds get their factions made when they are loaded (world.factions.ensure_factions)."""
    if kind == "world":
        body = dict(body)
        for key in ("factions", "figures", "wars", "history", "news"):
            body.setdefault(key, [])
        body.setdefault("politics", {})
        body.setdefault("next_figure_id", 0)
    return body


# format number -> function upgrading a loaded JSON body (of a given kind) to the next format.
MIGRATIONS: dict[int, Callable[[str, dict], dict]] = {1: _v1_to_v2, 2: _v2_to_v3, 3: _v3_to_v4, 4: _v4_to_v5,
                                                      5: _v5_to_v6}


class SaveError(Exception):
    pass


# ---------------------------------------------------------------------------- helpers
def _npy(arr: np.ndarray) -> bytes:
    if arr.dtype == object:
        raise SaveError("refusing to save a non-numeric array")
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(arr))
    return buf.getvalue()


def _load_npy(data: bytes) -> np.ndarray:
    return np.load(io.BytesIO(data))


def _write_zip(path: Path, entries: dict[str, bytes | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    os.replace(tmp, path)


def _manifest(kind: str) -> str:
    return json.dumps({
        "format": FORMAT_VERSION,
        "kind": kind,
        "game_version": __version__,
        "saved": datetime.datetime.now().isoformat(timespec="seconds"),
    })


def _migrate(manifest: dict, body: dict) -> dict:
    fmt = int(manifest.get("format", 1))
    if fmt > FORMAT_VERSION:
        raise SaveError("This save was made by a newer version of the game.")
    while fmt < FORMAT_VERSION:
        body = MIGRATIONS[fmt](manifest.get("kind", ""), body)
        fmt += 1
    return body


# ---------------------------------------------------------------------------- world
def world_entries(world: World) -> dict[str, bytes | str]:
    body = {
        "meta": asdict(world.meta),
        "width": world.width,
        "height": world.height,
        "biome_ids": world.biome_ids,
        "time": world.time,
        "rng": world.rng.get_state(),
        "flavor": world.flavor.to_dict(),
        **world.objects_dict(),
        "local_maps": sorted(world.local_maps),
        "npcs": [n.to_dict() for _, n in sorted(world.npcs.items())],
        "towns": [t.to_dict() for _, t in sorted(world.towns.items())],
        "next_npc_id": world.next_npc_id,
        "factions": [f.to_dict() for _, f in sorted(world.factions.items())],
        "figures": [f.to_dict() for _, f in sorted(world.figures.items())],
        "next_figure_id": world.next_figure_id,
        "wars": world.wars,
        "history": world.history,
        "news": world.news,
        "politics": world.politics,
    }
    entries: dict[str, bytes | str] = {"manifest.json": _manifest("world"), "world.json": json.dumps(body)}
    for name, arr in world.arrays().items():
        entries[f"arrays/{name}.npy"] = _npy(arr)
    for key, lm in world.local_maps.items():
        safe = key.replace(",", "_")
        entries[f"local/{safe}.json"] = json.dumps({
            "key": lm.key, "kind": lm.kind, "width": lm.width, "height": lm.height,
            "terrain_ids": lm.terrain_ids, "entry": list(lm.entry),
            "buildings": [asdict(b) for b in lm.buildings],
            "items": [[x, y, [i.to_dict() for i in pile]] for (x, y), pile in sorted(lm.items.items()) if pile],
            "actors": [a.to_dict() for a in lm.actors],
            "populated": lm.populated,
        })
        entries[f"local/{safe}.terrain.npy"] = _npy(lm.terrain)
        entries[f"local/{safe}.variant.npy"] = _npy(lm.variant)
        entries[f"local/{safe}.seen.npy"] = _npy(lm.seen)
    return entries


def save_world(world: World, folder: Path) -> None:
    _write_zip(folder / WORLD_FILE, world_entries(world))


def load_world(folder: Path) -> World:
    path = folder / WORLD_FILE
    try:
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("manifest.json"))
            body = _migrate(manifest, json.loads(z.read("world.json")))
            arrays = {name: _load_npy(z.read(f"arrays/{name}.npy")) for name in ARRAY_NAMES}
            local_maps = {}
            for key in body.get("local_maps", []):
                safe = key.replace(",", "_")
                info = json.loads(z.read(f"local/{safe}.json"))
                local_maps[key] = LocalMap(
                    key=info["key"], kind=info["kind"], width=info["width"], height=info["height"],
                    terrain_ids=info["terrain_ids"],
                    terrain=_load_npy(z.read(f"local/{safe}.terrain.npy")),
                    variant=_load_npy(z.read(f"local/{safe}.variant.npy")),
                    buildings=[Building(**{**b, "door": tuple(b.get("door", (0, 0)))}) for b in info["buildings"]],
                    entry=tuple(info["entry"]),
                    seen=_load_npy(z.read(f"local/{safe}.seen.npy")),
                    items={(x, y): [Item.from_dict(i) for i in pile] for x, y, pile in info.get("items", [])},
                    actors=[LocalActor.from_dict(a) for a in info.get("actors", [])],
                    populated=bool(info.get("populated", False)),
                )
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise SaveError(f"The world save could not be read ({exc}).") from exc
    return World(
        meta=WorldMeta(**body["meta"]),
        width=body["width"],
        height=body["height"],
        biome_ids=body["biome_ids"],
        settlements=[Settlement(**s) for s in body["settlements"]],
        sites=[Site(**s) for s in body["sites"]],
        areas=[Area(**a) for a in body["areas"]],
        time=int(body["time"]),
        local_maps=local_maps,
        flavor=FlavorStore.from_dict(body.get("flavor", {})),
        rng=RNG.from_state(body["rng"]),
        npcs={n["id"]: NPC.from_dict(n) for n in body.get("npcs", [])},
        towns={t["settlement"]: Town.from_dict(t) for t in body.get("towns", [])},
        next_npc_id=int(body.get("next_npc_id", 0)),
        factions={f["id"]: Faction.from_dict(f) for f in body.get("factions", [])},
        figures={f["id"]: Figure.from_dict(f) for f in body.get("figures", [])},
        next_figure_id=int(body.get("next_figure_id", 0)),
        wars=body.get("wars", []),
        history=body.get("history", []),
        news=body.get("news", []),
        politics=body.get("politics", {}),
        **arrays,
    )


# ---------------------------------------------------------------------------- character
def character_entries(game: GameState) -> dict[str, bytes | str]:
    p = game.player
    body = {
        "name": p.name, "x": p.x, "y": p.y, "local_key": p.local_key, "lx": p.lx, "ly": p.ly,
        "alive": p.alive, "home": p.home, "seconds": p.seconds, "steps": p.steps,
        "known_settlements": sorted(p.known_settlements),
        "visited_settlements": sorted(p.visited_settlements),
        "visited_areas": sorted(p.visited_areas),
        "log": game.log.to_dict(),
        "party": [c.to_dict() for c in game.party],
        "renown": game.renown.to_dict(),
        "arrest": game.arrest,
        "sentence": game.sentence,
    }
    return {"manifest.json": _manifest("character"), "character.json": json.dumps(body),
            "explored.npy": _npy(p.explored)}


def load_player(folder: Path) -> tuple[PlayerState, MessageLog, list[Character] | None, dict]:
    path = folder / CHARACTER_FILE
    try:
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("manifest.json"))
            body = _migrate(manifest, json.loads(z.read("character.json")))
            explored = _load_npy(z.read("explored.npy"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise SaveError(f"The character save could not be read ({exc}).") from exc
    player = PlayerState(
        name=body["name"], x=body["x"], y=body["y"], explored=explored, local_key=body.get("local_key"),
        lx=body.get("lx", 0), ly=body.get("ly", 0), alive=body.get("alive", True), home=body.get("home", -1),
        known_settlements=set(body.get("known_settlements", [])),
        visited_settlements=set(body.get("visited_settlements", [])),
        visited_areas=set(body.get("visited_areas", [])),
        seconds=body.get("seconds", 0), steps=body.get("steps", 0),
    )
    party = body.get("party")
    party_chars = [Character.from_dict(c) for c in party] if party else None
    extra = {"renown": body.get("renown", {}), "arrest": body.get("arrest"), "sentence": body.get("sentence")}
    return player, MessageLog.from_dict(body.get("log", {})), party_chars, extra


# ---------------------------------------------------------------------------- whole game
def world_folder(saves_dir: Path, world: World) -> Path:
    return saves_dir / world.meta.id


def save_game(game: GameState, saves_dir: Path) -> Path:
    folder = world_folder(saves_dir, game.world)
    save_world(game.world, folder)
    _write_zip(folder / CHARACTER_FILE, character_entries(game))
    game.dirty = False
    return folder


def load_game(folder: Path, tables: Tables) -> GameState:
    from realmwalker.game.reputation import Renown, starting_knowledge
    from realmwalker.world.factions import ensure_factions

    from realmwalker.world.history import ensure_history

    world = load_world(folder)
    ensure_factions(world, tables)
    ensure_history(world, tables)
    player, messages, party, extra = load_player(folder)
    if player.local_key is not None and player.local_key not in world.local_maps:
        player.local_key = None
    try:
        game = GameState(world, player, tables, messages, party=party)
    except (KeyError, TypeError, ValueError) as exc:
        raise SaveError(f"The character in this save could not be understood ({exc}).") from exc
    if party is None:
        player.name = game.leader.name
    game.renown = Renown.from_dict(extra["renown"])
    game.arrest = extra.get("arrest")
    game.sentence = extra.get("sentence")
    if not game.renown.flags.get("started"):
        starting_knowledge(game)  # a character from before M6
    return game


@dataclass
class SaveSummary:
    folder: Path
    world_name: str
    world_id: str
    seed: int
    size: str
    created: str
    character: str | None
    saved: str


def list_saves(saves_dir: Path) -> list[SaveSummary]:
    """All worlds on disk, most recently saved first. Unreadable folders are skipped."""
    out: list[SaveSummary] = []
    if not saves_dir.exists():
        return out
    for folder in saves_dir.iterdir():
        wpath = folder / WORLD_FILE
        if not wpath.exists():
            continue
        try:
            with zipfile.ZipFile(wpath) as z:
                manifest = json.loads(z.read("manifest.json"))
                body = json.loads(z.read("world.json"))
            meta = body["meta"]
            character = None
            saved = manifest.get("saved", "")
            cpath = folder / CHARACTER_FILE
            if cpath.exists():
                with zipfile.ZipFile(cpath) as z:
                    cm = json.loads(z.read("manifest.json"))
                    cb = json.loads(z.read("character.json"))
                if cb.get("alive", True):
                    character = cb.get("name")
                    saved = max(saved, cm.get("saved", ""))
            out.append(SaveSummary(folder, meta["name"], meta["id"], meta["seed"], meta["size"],
                                   meta.get("created", ""), character, saved))
        except Exception:
            log.warning("Skipping unreadable save folder %s", folder, exc_info=True)
    out.sort(key=lambda s: s.saved, reverse=True)
    return out
