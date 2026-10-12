"""The codex (docs/expansions/codex): the checklist of everything in the three books that the expansions bring in
(docs/EXPANSIONS.md §4.2). It must be well formed, and it must tell the truth: what it calls done is in the game, and
an expansion that is out has nothing left to do."""

from tools.codex import codex


def test_the_codex_is_well_formed_and_its_done_entries_exist(data):
    released = {p.order for p in data.packs if p.record["status"] == "released"}
    problems = codex.problems(data, released)
    assert not problems, "\n".join(problems[:30])


def test_the_codex_covers_the_three_books():
    kinds = {kind for kind, _ in codex.entries()}
    assert {"spells", "monsters", "magic_items", "classes"} <= kinds
    cov = codex.coverage()["files"]
    assert sum(cov["spells"].values()) > 350, "every PHB spell"
    assert sum(cov["monsters"].values()) > 450, "every Monster Manual stat block"
    assert sum(cov["magic_items"].values()) > 300, "every DMG magic item"
    assert sum(cov["classes"].values()) > 500, "every class, subclass and feature"


def test_every_entry_belongs_to_one_expansion_of_the_programme():
    by_dlc = codex.coverage()["dlc"]
    assert set(by_dlc) <= set(range(1, 27))
    assert 1 in by_dlc, "Dice & Destiny has entries of its own"


def test_problems_are_found(tmp_path):
    """The checks themselves work (on made-up entries, in a folder of their own)."""
    import json

    path = tmp_path / "spells.json"
    path.write_text(json.dumps({"entries": [
        {"id": "spell:x", "name": "X", "book": "phb", "page": 1, "dlc": 30, "status": "adapted", "game": [], "note": ""},
        {"id": "spell:x", "name": "X", "book": "nope", "page": 1, "dlc": 3, "status": "done", "game": ["nope"],
         "note": "", "upgrade_in": 2}]}), encoding="utf-8")
    found = "\n".join(codex.problems(folder=tmp_path))
    for bit in ("dlc must be", "must say why", "the id is also in", "book must be", "upgrade_in must be"):
        assert bit in found, bit
