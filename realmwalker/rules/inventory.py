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
    """Take items out of the pack (unequipping first). Returns the removed items as a new stack."""
    it = char.item(uid)
    if it is None:
        return None
    take = it.qty if qty is None else max(1, min(qty, it.qty))
    if take >= it.qty:
        slot = char.slot_of(uid)
        if slot is not None and cursed(it):
            return None  # it will not come off
        if slot is not None:
            del char.equipped[slot]
        char.inventory.remove(it)
        return it
    it.qty -= take
    return Item(0, it.def_id, take, it.quality, it.condition, it.name, it.made_at, list(it.tags))


def cursed(item: Item | None) -> bool:
    return bool(item is not None and item.magic and item.magic.get("cursed"))


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
    d = items.get(it.def_id)
    slots = items.slots_for(it)
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
    """Everything in the pack that could go in this slot."""
    return [it for it in char.inventory if slot in items.slots_for(it)]


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
