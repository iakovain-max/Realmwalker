"""Playing: moving, time, local maps, travel, saving and loading."""

import json
import zipfile

import numpy as np
import pytest

from realmwalker.game import save
from realmwalker.game.describe import describe_local, describe_overworld
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture
def game(tables):
    world = WorldGenerator(WorldOptions("Playland", 202, "small"), tables).generate()
    return new_game(world, tables)


def neighbours(game):
    p = game.player
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx or dy) and game.world.in_bounds(p.x + dx, p.y + dy):
                yield dx, dy


def test_new_game_starts_in_a_settlement(game):
    p = game.player
    assert game.world.settlement_at(p.x, p.y) is not None
    assert p.explored[p.x, p.y] and p.explored.sum() > 100
    assert game.log.messages


def test_moving_takes_time_and_roads_are_faster(game):
    p = game.player
    t0 = game.world.time
    road_steps = [(dx, dy) for dx, dy in neighbours(game) if game.world.road[p.x + dx, p.y + dy] and not (dx and dy)]
    assert road_steps, "towns sit on roads"
    minutes = game.step_minutes(p.x, p.y, p.x + road_steps[0][0], p.y + road_steps[0][1])
    assert game.move(*road_steps[0])
    assert game.world.time - t0 == minutes
    on_road = game.step_minutes(p.x, p.y, p.x, p.y)  # a road tile to itself is still a road step
    assert on_road is not None and on_road <= 60


def test_cannot_walk_into_the_sea(game, tables):
    ocean = tables.biomes.index["ocean"]
    world = game.world
    x, y = map(int, np.argwhere(world.biome == ocean)[0])
    assert game.step_minutes(x, y, x, y) is None


def test_local_map_enter_walk_and_leave(game):
    lm = game.enter_local()
    p = game.player
    assert game.in_local and (p.lx, p.ly) == lm.entry
    moved = sum(game.move(dx, dy) for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)] * 3)
    assert moved > 0
    assert "You are here" in describe_local(game, p.lx, p.ly) or describe_local(game, p.lx, p.ly)
    # Walking off the edge returns to the overworld.
    p.lx = 0
    game.move(-1, 0)
    assert not game.in_local


def test_doors_open_when_walked_into(game, tables):
    lm = game.enter_local()
    b = lm.buildings[0]
    dx_, dy_ = b.door
    p = game.player
    # Stand outside the door and walk into it.
    for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        x, y = dx_ + ox, dy_ + oy
        if lm.in_bounds(x, y) and tables.terrain.walk[game.remap_for(lm)[lm.terrain[x, y]]] and not b.contains(x, y):
            p.lx, p.ly = x, y
            game.move(-ox, -oy)
            break
    assert tables.terrain.ids[game.remap_for(lm)[lm.terrain[dx_, dy_]]] == "door_open"


def test_travel_plan_and_journey(game, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.state.GameState.lost_dc", lambda self: None)
    game.survival = False  # a journey of many days; hunger and thirst are tested elsewhere
    world = game.world
    p = game.player
    target = max((s for s in world.settlements if s.kind != "hamlet"), key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))
    plan = game.plan_travel((target.x, target.y))
    assert plan is not None and plan.minutes > 0 and plan.miles > 0
    game.set_out(plan)
    t0 = world.time
    steps = stops = 0
    while (p.x, p.y) != (target.x, target.y):
        if game.travel is None:  # stopped for the night: t, Enter, and on again
            stops += 1
            game.set_out(game.plan_travel((target.x, target.y)))
        game.travel_step()
        steps += 1
        assert steps < 5000
    assert (p.x, p.y) == (target.x, target.y)
    assert stops >= 1, "a journey of days stops for the night"
    # Rain, snow and storms slow the walk; the plan is the estimate for fair weather.
    assert plan.minutes <= world.time - t0 <= plan.minutes * 2
    assert "day" in game.describe_plan(plan) or "hour" in game.describe_plan(plan)


def test_describe_tiles(game):
    p = game.player
    text = describe_overworld(game, p.x, p.y)
    assert "You are here" in text
    far = describe_overworld(game, 0, 0)
    assert far


def test_save_and_load_round_trip(game, tables, tmp_path):
    for _ in range(10):
        for dx, dy in neighbours(game):
            if game.move(dx, dy):
                break
    game.enter_local()
    for _ in range(5):
        game.move(1, 0)
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, tables)
    a, b = save.world_entries(game.world), save.world_entries(loaded.world)
    assert [k for k in a if k != "manifest.json" and a[k] != b[k]] == []
    c1, c2 = save.character_entries(game), save.character_entries(loaded)
    assert [k for k in c1 if k != "manifest.json" and c1[k] != c2[k]] == []
    summaries = save.list_saves(tmp_path)
    assert summaries and summaries[0].character == game.player.name


def test_broken_and_future_saves_are_refused(game, tables, tmp_path):
    folder = save.save_game(game, tmp_path)
    (folder / save.CHARACTER_FILE).write_bytes(b"not a zip")
    with pytest.raises(save.SaveError):
        save.load_game(folder, tables)
    folder = save.save_game(game, tmp_path)
    path = folder / save.WORLD_FILE
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(entries["manifest.json"])
    manifest["format"] = save.FORMAT_VERSION + 1
    entries["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w") as z:
        for n, d in entries.items():
            z.writestr(n, d)
    with pytest.raises(save.SaveError, match="newer version"):
        save.load_game(folder, tables)


def test_days_are_announced(game):
    before = len(game.log.messages)
    game.wait(60 * 24)
    assert len(game.log.messages) > before


def test_drop_and_pick_up_items(game):
    game.enter_local()
    leader = game.leader
    torch = next(i for i in leader.inventory if i.def_id == "torch")
    count = torch.qty
    assert game.drop(torch.uid, 1)
    assert sum(i.qty for i in leader.inventory if i.def_id == "torch") == count - 1
    assert game.pick_up() == 1
    assert sum(i.qty for i in leader.inventory if i.def_id == "torch") == count


def test_items_on_the_ground_survive_saving(game, tables, tmp_path):
    game.enter_local()
    blanket = next((i for i in game.leader.inventory if i.def_id == "blanket"), None)
    assert blanket is not None
    game.drop(blanket.uid)
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, tables)
    lm = loaded.local
    assert any(i.def_id == "blanket" for pile in lm.items.values() for i in pile)


def test_saves_from_before_the_peoples_are_refused_kindly(game, tables, tmp_path):
    """Format 11 (2026-10-11: peoples on the map, bigger towns) has no way back to older saves (Anton: old saves do
    not matter yet). An older one is refused with a plain message, and its files are left as they were."""
    folder = save.save_game(game, tmp_path)
    path = folder / save.CHARACTER_FILE
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    body = json.loads(entries["character.json"])
    del body["party"]
    manifest = json.loads(entries["manifest.json"])
    manifest["format"] = 1
    entries["character.json"] = json.dumps(body).encode()
    entries["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w") as z:
        for n, d in entries.items():
            z.writestr(n, d)
    before = path.read_bytes()
    with pytest.raises(save.SaveError):
        save.load_game(folder, tables)
    assert path.read_bytes() == before


def test_heavy_loads_slow_travel(game, tables, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.state.GameState.lost_dc", lambda self: None)
    from realmwalker.rules.inventory import add_item

    p = game.player
    dx, dy = next((dx, dy) for dx, dy in neighbours(game) if game.step_minutes(p.x, p.y, p.x + dx, p.y + dy))
    base = game.step_minutes(p.x, p.y, p.x + dx, p.y + dy)
    add_item(game.leader, tables.items, "iron_bar", 12)
    t0 = game.world.time
    assert game.move(dx, dy)
    assert game.world.time - t0 > base
    add_item(game.leader, tables.items, "iron_bar", 30)
    assert not game.move(-dx, -dy)


def test_a_region_describes_itself(game):
    """The country you walk into says what it is like, the first time you come into it."""
    area = next(a for a in game.world.areas if a.kind != "river")
    game.player.x, game.player.y = area.x, area.y
    game.player.visited_areas.discard(area.id)
    game._arrive(None)
    said = [m.text for m in game.log.messages[-3:] if area.name in m.text]
    assert said and "{" not in said[-1] and len(said[-1]) > len(area.name) + 20


def test_landmarks_are_seen_from_a_distance(game):
    """A ruin or a cave coming into view is remarked on, and goes on the map."""
    site = min(game.world.sites, key=lambda s: abs(s.x - game.player.x) + abs(s.y - game.player.y))
    game.player.explored[:] = False
    game.player.x, game.player.y = site.x + 2, site.y
    said = len(game.log.messages)
    game.reveal()
    text = " ".join(m.text for m in game.log.messages[said:])
    assert "miles off" in text and game.player.explored[site.x, site.y]
    said = len(game.log.messages)
    game.reveal()  # a place already seen is not announced twice
    assert len(game.log.messages) == said


def test_text_detail_is_honoured(game):
    """'Text detail' in Settings decides how much of the world's voice you hear."""
    s = next(x for x in game.world.settlements if x.kind in ("town", "city"))
    game.player.x, game.player.y = s.x, s.y
    lm = game.enter_local()
    game.verbosity = "brief"
    said = []
    game.say = lambda text, color="fg": said.append(text)
    for _ in range(80):
        game.player.steps += 1
        game._street_life(lm)
    assert not said, said
    game.verbosity = "normal"
    for _ in range(80):
        game.player.steps += 1
        game._street_life(lm)
    assert said
    assert game.flavour() and not game.flavour(2)
    game.verbosity = "rich"
    assert game.flavour(2)
