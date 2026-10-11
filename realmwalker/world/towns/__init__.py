"""Towns: the close-up map of a settlement, laid out the way its people build (data/towns.json).

A Norse village is long halls round a mead hall inside an earth bank; a Qasari city a bazaar street from the gate to
the great domed temple, winding alleys and houses round courtyards; a Khurgan camp rings of felt tents round the
khan's; a Volsk town a wooden fort with an onion-domed church above log houses; an Itzan city a stepped pyramid on a
great plaza; a dwarven hold halls cut in the rock and lit by braziers and lava; an elven hall homes in giant trees.

    size_of(tables, settlement) -> (width, height)   the close-up map's size (great cities are the biggest)
    build(builder, settlement)                       lay the town out on a world.local.LocalBuilder

Each building is a world.local.Building with its kind, shape (rect, long, round, court, tree, mound, carved), its
rooms (what each is for, and so how it is furnished) and its look (roof and walls, drawn by ui/gfx/roofs.py).
"""

from __future__ import annotations

from realmwalker.world.towns.plan import Plan, style_for


def size_of(tables, settlement) -> tuple[int, int]:
    sizes = tables.towns["sizes"]
    key = "great" if getattr(settlement, "great", False) else settlement.kind
    w, h = sizes.get(key) or sizes.get(settlement.kind) or (96, 64)
    return int(w), int(h)


def build(b, settlement) -> None:
    """Lay out the settlement on the builder's map (its ground, water, river and road are already there)."""
    from realmwalker.world.towns import layouts

    style = style_for(b.tables, settlement)
    plan = Plan(b, settlement, style)
    layout = style.get("layout", "organic")
    if settlement.kind in ("town", "city") and style.get("city_layout") and settlement.kind == "city":
        layout = style["city_layout"]
    if settlement.kind == "hold":
        layout = "hold"
    elif settlement.kind == "elfhall":
        layout = "grove"
    getattr(layouts, layout, layouts.organic)(plan)
    plan.connect()
    plan.notice_board()
    plan.finish()
