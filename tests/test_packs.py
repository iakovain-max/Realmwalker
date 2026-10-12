"""Content packs and the expansion registry (docs/EXPANSIONS.md §4.1): each expansion's data in its own folder, merged
over the base files by key, with provenance; and the expansions the main menu's shelf shows."""

import json
import shutil

import pytest

from realmwalker.data.packs import BASE, Provenance, find_packs, merge_fragment
from realmwalker.data.registry import DataRegistry
from realmwalker.paths import Paths


def merge(base, frag, errors=None, prov=None):
    errors = [] if errors is None else errors
    prov = prov or Provenance()
    prov.note_base("x.json", base)
    merge_fragment(base, frag, filename="x.json", pack_id="p", where="pack/x.json", prov=prov, errors=errors)
    return errors, prov


def test_new_entries_are_added_and_remember_their_pack():
    base = {"creatures": {"wolf": {"hp": 11}}}
    errors, prov = merge(base, {"_comment": "hi", "creatures": {"imp": {"hp": 21, "_note": "x"}}, "lairs": {"a": {}}})
    assert not errors
    assert base["creatures"]["imp"] == {"hp": 21}, "flags and comments are not copied"
    assert "_comment" not in base and base["lairs"] == {"a": {}}
    assert prov.origin("x.json", "imp") == "p" and prov.origin("x.json", "wolf") == BASE
    assert prov.added_by("p") == {("x.json", "creatures"): 1, ("x.json", "lairs"): 1}


def test_an_entry_defined_twice_is_an_error_unless_it_replaces_or_merges():
    base = {"creatures": {"wolf": {"hp": 11, "tags": ["beast"]}}}
    errors, _ = merge(base, {"creatures": {"wolf": {"hp": 99}}})
    assert errors and "already defined" in errors[0] and base["creatures"]["wolf"]["hp"] == 11
    errors, prov = merge(base, {"creatures": {"wolf": {"_replace": True, "hp": 12}}})
    assert not errors and base["creatures"]["wolf"] == {"hp": 12} and prov.origin("x.json", "wolf") == "p"
    base = {"creatures": {"wolf": {"hp": 11, "tags": ["beast"]}}}
    errors, _ = merge(base, {"creatures": {"wolf": {"_merge": True, "cr": "1/4", "tags": {"_append": ["pack"]}}}})
    assert not errors and base["creatures"]["wolf"] == {"hp": 11, "tags": ["beast", "pack"], "cr": "1/4"}
    errors, _ = merge(base, {"creatures": {"wolf": {"_merge": True, "hp": 5}}})
    assert errors, "merging into an entry still may not redefine its fields"


def test_lists_grow_only_when_asked():
    base = {"names": ["a"], "more": ["x"]}
    errors, _ = merge(base, {"names": {"_append": ["b", "c"]}})
    assert not errors and base["names"] == ["a", "b", "c"]
    errors, _ = merge(base, {"more": ["y"]})
    assert errors and base["more"] == ["x"]


def make_pack(root, folder, record, files=None):
    d = root / "packs" / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "pack.json").write_text(json.dumps(record), encoding="utf-8")
    for name, data in (files or {}).items():
        (d / name).write_text(json.dumps(data), encoding="utf-8")
    return d


def record(pid, order, **kw):
    r = {"id": pid, "order": order, "name": pid.title(), "tagline": "A line.", "icon": f"dlc/{pid}",
         "accent": [10, 20, 30], "status": "planned", "version": f"1.{order}.0", "released_on": "", "adds": []}
    r.update(kw)
    return r


def test_pack_records_are_checked_and_must_not_clash(tmp_path):
    make_pack(tmp_path, "01_a", record("a", 1))
    make_pack(tmp_path, "02_b", record("a", 1))
    make_pack(tmp_path, "03_bad", {"id": "bad"})
    errors = []
    packs = find_packs(tmp_path, errors)
    assert any("two packs are called 'a'" in e for e in errors)
    assert any("two packs have order 1" in e for e in errors)
    assert any("03_bad" in e for e in errors) and all(p.id != "bad" for p in packs)


@pytest.fixture(scope="module")
def data_copy(tmp_path_factory):
    """The game's data with a test pack beside Expansion 1's (on a copy: the real folder is never written)."""
    root = tmp_path_factory.mktemp("data") / "data"
    shutil.copytree(Paths().data, root)
    wolf = json.loads((Paths().data / "creatures.json").read_text(encoding="utf-8"))["creatures"]["wolf"]
    make_pack(root, "90_test", record("test_pack", 90, status="released", released_on="2026-11-02",
                                      adds=["A test of packs"], counts=[["creatures.json", "creatures", "beasts"]]),
              {"creatures.json": {"creatures": {"test_wolf": dict(wolf, name="test wolf")}},
               "creatures.more.json": {"creatures": {"wolf": dict(wolf, _replace=True, name="grey wolf")}}})
    return root


def test_a_pack_merges_into_the_game_data_with_provenance(data_copy):
    data, errors = DataRegistry.load(data_copy)
    assert not errors, errors
    assert data["creatures.json"]["creatures"]["test_wolf"]["name"] == "test wolf"
    assert data["creatures.json"]["creatures"]["wolf"]["name"] == "grey wolf", "a pack may re-make a base entry"
    assert data.origin("creatures", "test_wolf") == "test_pack" and data.origin("creatures", "wolf") == "test_pack"
    assert data.origin("creatures", "boar") == "base" and data.origin("creatures", "nothing") is None
    assert data.added_by("test_pack") == {("creatures.json", "creatures"): 2}


def test_a_broken_pack_is_reported_not_fatal(tmp_path_factory, data_copy):
    root = tmp_path_factory.mktemp("broken") / "data"
    shutil.copytree(data_copy, root)
    make_pack(root, "91_broken", record("broken", 91), {"creatures.json": {"creatures": {"boar": {"hp": 1}}},
                                                       "nonsense.json": {"x": {}}})
    data, errors = DataRegistry.load(root)
    assert any("creatures.boar is already defined" in e for e in errors)
    assert any("no data file called nonsense.json" in e for e in errors)


def test_the_shelf_shows_released_expansions_in_order(data_copy):
    from realmwalker import expansions

    data, _ = DataRegistry.load(data_copy)
    everything = expansions.all_expansions(data)
    assert [e.order for e in everything] == sorted(e.order for e in everything)
    shown = expansions.released(data)
    assert all(e.released for e in shown) and "test_pack" in [e.id for e in shown]
    test = next(e for e in shown if e.id == "test_pack")
    assert test.counts == ["2 beasts"] and test.when() == "Version 1.90 · 2 November 2026"
    assert "dice_destiny" not in [e.id for e in shown] or next(e for e in everything if e.id == "dice_destiny").released


def test_every_real_pack_is_valid_and_released_ones_have_their_icon(data):
    from realmwalker import expansions
    from realmwalker.ui.gfx.atlas import load

    assert data.packs, "the expansion packs are in data/packs"
    ids = [p.id for p in data.packs]
    assert len(ids) == len(set(ids)) and [p.order for p in data.packs] == sorted(p.order for p in data.packs)
    atlas = load(str(Paths().tiles))
    for e in expansions.released(data):
        assert atlas.resolve(e.icon), f"{e.name} is released but has no icon {e.icon} in the tile sheets"
        assert e.adds and e.released_on, f"{e.name} is released without its 'adds' lines or its date"
