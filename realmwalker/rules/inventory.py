"""Adding, removing, equipping and unequipping items, following the rules of hands and layers."""

from __future__ import annotations

from realmwalker.rules.character import Character
from realmwalker.rules.items import Item, ItemTable


def add_item(char: Character, items: ItemTable, def_id: str, qty: int = 1, *, quality: str = "common",
             condition: int = 100, made_at: int = 0, name: str = "", tags: list[str] | None = None) -> Item:
    """Put items in a character's pack, merging with an identical stack if there is one."""
    probe = Item(0, def_id, qty, quality, condition, name, made_at, list(tags or []))
    if items.stackable(probe):
        for it in char.inventory:
            if (it.def_id == def_id and it.quality == quality and it.condition == condition and it.name == name
                    and sorted(it.tags) == sorted(probe.tags) and abs(it.made_at - made_at) < 60 * 24):
                it.qty += qty
                return it
    probe.uid = char.new_uid()
    char.inventory.append(probe)
    return probe


def add_existing(char: Character, items: ItemTable, item: Item) -> Item:
    """Take an item that came from somewhere else (the ground, another character)."""
    it = add_item(char, items, item.def_id, item.qty, quality=item.quality, condition=item.condition,
                  made_at=item.made_at, name=item.name, tags=item.tags)
    if item.magic:
        it.magic = item.magic
    if item.fill and it.qty == 1:
        it.fill, it.fill_kind = item.fill, item.fill_kind
    return it


def fill_containers(char: Character, items: ItemTable, kind: str = "clean") -> float:
    """Top up every waterskin (and other liquid containers). Returns pints added."""
    added = 0.0
    for it in char.inventory:
        cap = container_capacity(items, it)
        if cap and it.fill < cap:
            if it.fill > 0 and it.fill_kind != kind:
                kind_now = worse_water(it.fill_kind, kind)
            else:
                kind_now = kind
            added += cap - it.fill
            it.fill = float(cap)
            it.fill_kind = kind_now
    return added


def container_capacity(items: ItemTable, item: Item) -> float:
    return float(items.get(item.def_id).get("container", {}).get("liquid", 0)) * item.qty


WATER_RISK = {"clean": 0, "boiled": 0, "stream": 1, "river": 2, "lake": 2, "marsh": 3}


def worse_water(a: str, b: str) -> str:
    """Mixing water: the result is as risky as the worst of the two."""
    return a if WATER_RISK.get(a, 2) >= WATER_RISK.get(b, 2) else b


def remove_item(char: Character, uid: int, qty: int | None = None) -> Item | None:
    """Take items out of the pack (unequipping first, whoever in the party has it on). Returns the removed items as
    a new stack."""
    it = char.item(uid)
    if it is None:
        return None
    take = it.qty if qty is None else max(1, min(qty, it.qty))
    if take >= it.qty:
        wearer, slot = worn_by(char, uid)
        if slot is not None and cursed(it):
            return None  # it will not come off
        if slot is not None:
            del wearer.equipped[slot]
        char.inventory.remove(it)
        return it
    it.qty -= take
    return Item(0, it.def_id, take, it.quality, it.condition, it.name, it.made_at, list(it.tags))


def cursed(item: Item | None) -> bool:
    """A cursed thing clings to whoever has it on; Remove Curse loosens it (`magic["loosed"]`: the curse remains,
    but it can be taken off and thrown away) until it is put on again."""
    return bool(item is not None and item.magic and item.magic.get("cursed") and not item.magic.get("loosed"))


def unequip(char: Character, slot: str) -> Item | None:
    if cursed(char.equipped_item(slot)):
        return None  # cursed things cling
    uid = char.equipped.pop(slot, None)
    return char.item(uid) if uid is not None else None


def equip(char: Character, items: ItemTable, uid: int, slot: str | None = None) -> tuple[bool, str]:
    """Equip an item. Returns (success, message for the log)."""
    it = char.item(uid)
    if it is None:
        return False, "You don't have that."
    wearer, _ = worn_by(char, uid)  # the party shares one pack: it may be on someone else
    if wearer is not None and wearer is not char:
        return False, f"{wearer.name.split()[0]} has the {items.name(it, False)}. Take it off them first."
    d = items.get(it.def_id)
    slots = items.slots_for(it, char)
    if not slots:
        return False, f"You can't wear or wield the {items.name(it, False)}."
    if slot is None:
        slot = slots[0]
        if slot == "main_hand" and "off_hand" in slots and char.equipped.get("main_hand") is not None \
                and char.equipped.get("off_hand") is None:
            slot = "off_hand"  # a second light weapon goes in the other hand
    if slot not in slots:
        return False, f"The {items.name(it, False)} doesn't go there."
    if "lost_left_arm" in char.injuries or "lost_right_arm" in char.injuries:
        if slot == "off_hand":
            return False, "With one hand left, there is nothing to hold it in."
        if "two_handed" in d.get("properties", []):
            return False, f"The {items.name(it, False)} needs two hands."
    there = char.equipped_item(slot)
    if cursed(there) and there.uid != uid:
        there.magic["curse_known"] = True
        return False, (f"The {items.name(there, False)} will not come off. It is cursed; a priest may be able to "
                       f"lift it.")
    current = char.slot_of(uid)
    if current is not None:
        del char.equipped[current]
    if it.magic and it.magic.get("loosed") and current is None:
        it.magic.pop("loosed", None)  # (put on again, the curse takes hold again)
    props = d.get("properties", [])
    messages = []
    if slot == "main_hand" and "two_handed" in props:
        other = unequip(char, "off_hand")
        if other is not None:
            messages.append(f"You put away the {items.name(other, False)} to take it in both hands.")
    if slot == "off_hand":
        main = char.equipped_item("main_hand")
        if main is not None and "two_handed" in items.get(main.def_id).get("properties", []):
            unequip(char, "main_hand")
            messages.append(f"You shoulder the {items.name(main, False)} to free a hand.")
    old = unequip(char, slot)
    if old is not None and old.uid != uid:
        messages.append(f"You take off the {items.name(old, False)}.")
    char.equipped[slot] = uid
    verb = "wield" if d["category"] == "weapon" else ("hold" if slot == "off_hand" else "put on")
    messages.append(f"You {verb} the {items.name(it, False)}.")
    if cursed(it) and not it.magic.get("curse_known"):
        it.magic["curse_known"] = True
        messages.append("A chill runs through you, and something tightens. It will not come off.")
    return True, " ".join(messages)


def best_slot_items(char: Character, items: ItemTable, slot: str) -> list[Item]:
    """Everything in the pack that could go in this slot (and nobody else in the party has on)."""
    return [it for it in char.inventory if slot in items.slots_for(it, char) and worn_by(char, it.uid)[0] in (None, char)]


def equip_everything_sensible(char: Character, items: ItemTable) -> None:
    """After character creation: wear the clothes and armour, take up the best weapon and a shield."""
    for it in list(char.inventory):
        slots = items.slots_for(it)
        cat = items.category(it)
        if cat in ("armor", "helmet", "clothing") and slots and char.equipped.get(slots[0]) is None:
            equip(char, items, it.uid, slots[0])
    weapons = [it for it in char.inventory if items.category(it) == "weapon"]
    melee = [w for w in weapons if "ranged" not in items.get(w.def_id).get("properties", [])]

    def dice_avg(expr: str) -> float:
        n, _, s = expr.partition("d")
        return int(n or 1) * (int(s) + 1) / 2

    if melee:
        best = max(melee, key=lambda w: dice_avg(items.get(w.def_id)["damage"]))
        equip(char, items, best.uid, "main_hand")
    elif weapons:
        equip(char, items, weapons[0].uid, "main_hand")
    main = char.equipped_item("main_hand")
    two_handed = main is not None and "two_handed" in items.get(main.def_id).get("properties", [])
    if not two_handed:
        for it in char.inventory:
            if items.category(it) == "shield":
                equip(char, items, it.uid, "off_hand")
                break
    # A pack on the back (the one that carries most), a priest's holy symbol at the neck, a ring, a trophy; and a
    # wizard with a free hand holds a crystal focus.
    free = [it for it in char.inventory if worn_by(char, it.uid)[0] is None]
    packs = [it for it in free if "back" in items.slots_for(it)]
    if packs and char.equipped.get("back") is None:
        equip(char, items, max(packs, key=lambda it: float(items.get(it.def_id).get("carry", 0))).uid, "back")
    for it in sorted(free, key=lambda it: not items.get(it.def_id).get("focus")):
        slots = items.slots_for(it)
        if items.get(it.def_id).get("focus") and slots[0] == "off_hand":
            continue  # a crystal is held, below
        for slot in ("neck", "ring"):
            if slots and slots[0] == slot and char.equipped.get(slot) is None and not it.magic:
                equip(char, items, it.uid, slot)
    if char.cls == "wizard" and not two_handed and char.equipped.get("off_hand") is None:
        crystal = next((it for it in free if (items.get(it.def_id).get("focus") or {}).get("kind") == "arcane"
                        and not items.get(it.def_id)["focus"].get("carried") and worn_by(char, it.uid)[0] is None),
                       None)
        if crystal is not None:
            equip(char, items, crystal.uid, "off_hand")


# ---------------------------------------------------------------------------- the party's one pack
# Everyone travelling together shares one pack: every member's `inventory` is the same list (the leader's), so
# whoever needs the arrows, the bandages or the bread finds them, and nobody hands things about. What each wears
# and wields stays theirs (`equipped`, by item number in the shared list). The weight is carried together:
# Sheet.pack_load / pack_capacity. game/pack.py keeps the party in step as people join, leave and die.
def pack_mates(char: Character) -> list[Character]:
    """Everyone sharing this character's pack, themselves included."""
    mates = getattr(char, "_pack_mates", None)
    if mates and any(m is char for m in mates) and all(m.inventory is char.inventory for m in mates):
        return mates
    return [char]


def worn_by(char: Character, uid: int) -> tuple[Character | None, str | None]:
    """(who has it on, and where) among those sharing this pack, or (None, None)."""
    for m in pack_mates(char):
        slot = m.slot_of(uid)
        if slot is not None:
            return m, slot
    return None, None


def distinct_packs(chars) -> list[Character]:
    """One character for each separate pack among these: the party shares one, so usually just the leader. Loop over
    these, not over the party, to count or list what is carried without counting it twice."""
    seen: set[int] = set()
    out = []
    for c in chars:
        if id(c.inventory) not in seen:
            seen.add(id(c.inventory))
            out.append(c)
    return out


def carried(chars) -> list[Item]:
    """Everything these characters carry, each thing once."""
    return [it for c in distinct_packs(chars) for it in c.inventory]


def merge_into(shared: list[Item], char: Character, items: ItemTable | None = None) -> None:
    """Pour a character's things into the shared pack. What they do not wear joins a like stack if there is one (a
    quiver of bolts on a quiver of bolts); anything else keeps its number unless that is taken there, and then gets
    a free one (what they wear follows it)."""
    if char.inventory is shared:
        return
    taken = {it.uid for it in shared}
    top = max(taken, default=0)
    renumber: dict[int, int] = {}
    worn = set(char.equipped.values())
    for it in char.inventory:
        if items is not None and it.uid not in worn and items.stackable(it) and not it.magic:
            like = next((x for x in shared if x.def_id == it.def_id and x.quality == it.quality
                         and x.condition == it.condition and x.name == it.name and sorted(x.tags) == sorted(it.tags)
                         and abs(x.made_at - it.made_at) < 60 * 24 and not x.magic and x.fill == it.fill), None)
            if like is not None:
                like.qty += it.qty
                continue
        if it.uid in taken:
            top += 1
            renumber[it.uid] = top
            it.uid = top
        taken.add(it.uid)
        top = max(top, it.uid)
        shared.append(it)
    char.equipped = {slot: renumber.get(uid, uid) for slot, uid in char.equipped.items()}
    char.inventory = shared


def take_out(char: Character, *, keep_gear: bool = True) -> None:
    """Leave the shared pack: with what they wear and wield (keep_gear), or with nothing, leaving it all to the
    rest (the dead)."""
    shared = char.inventory
    if keep_gear:
        worn = set(char.equipped.values())
        own = [it for it in shared if it.uid in worn]
        for it in own:
            shared.remove(it)
        char.inventory = own
    else:
        char.equipped = {}
        char.inventory = []
    char._pack_mates = None
