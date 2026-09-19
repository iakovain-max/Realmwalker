"""Character sheet, inventory and equipment screens."""

from __future__ import annotations

from realmwalker.game.state import GameState
from realmwalker.rules.character import ABILITIES, Sheet, signed
from realmwalker.rules.inventory import best_slot_items, equip, unequip
from realmwalker.rules.items import CATEGORY_NAMES, EQUIP_SLOTS, SLOT_NAMES, Item, money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen, modal_box
from realmwalker.ui.widgets import Canvas, ScrollText

ENCUMBRANCE_WORDS = [("unburdened", "good"), ("encumbered", "warn"), ("heavily laden", "danger"), ("overloaded", "danger")]
SOCIAL_WORDS = {-3: "half-naked", -2: "ragged", -1: "shabby", 0: "plain", 1: "respectable", 2: "well-dressed", 3: "courtly"}


def item_glyph(category: str) -> tuple[str, str]:
    """(glyph, colour name) for an item lying on the ground."""
    return {
        "weapon": ("/", "loot"), "ammo": ("|", "loot"), "armor": ("[", "loot"), "shield": ("]", "loot"),
        "helmet": ("^", "loot"), "clothing": ("(", "loot"), "food": ("%", "good"), "drink": ("!", "info"),
        "book": ("?", "loot"), "trade": ("*", "loot"), "tool": ("&", "loot"), "focus": ("♀", "magic"),
    }.get(category, ("=", "loot"))


def spoilage_text(game: GameState, item: Item) -> str:
    food = game.tables.items.get(item.def_id).get("food")
    if not food or not food.get("spoil_days"):
        return ""
    age_days = (game.world.time - item.made_at) / (60 * 24)
    left = food["spoil_days"] - age_days
    if left <= 0:
        return "<danger>spoiled</>"
    if left < 2:
        return "<warn>going off</>"
    return f"<dim>{int(left)} days</>"


def item_details(game: GameState, item: Item) -> str:
    t = game.tables.items
    d = t.get(item.def_id)
    sheet = game.sheet()
    lines = [f"<loot>{markup.escape(t.name(item))}</>"]
    if d.get("description"):
        lines.append(d["description"])
    cat = d["category"]
    if cat == "weapon":
        props = ", ".join(p.replace("_", "-") for p in d.get("properties", [])) or "none"
        extra = f" (two hands {d['versatile']})" if d.get("versatile") else ""
        rng = f" · range {d['range'][0]}/{d['range'][1]} ft" if d.get("range") else ""
        lines.append(f"Damage {d['damage']}{extra} {d['damage_type']}{rng}")
        lines.append(f"<dim>{d.get('group', '').capitalize()} weapon · {props}</>")
        if not sheet.proficient_with_weapon(item):
            lines.append("<warn>You are not trained with this weapon.</>")
    elif cat == "armor":
        dex = {"light": "+ Dex", "medium": "+ Dex (max 2)", "heavy": ""}[d["armor_type"]]
        lines.append(f"{d['armor_type'].capitalize()} armour · AC {d['ac']} {dex}")
        lines.append(f"<dim>Covers: {', '.join(d.get('covers', []))}</>")
        if d.get("str_req"):
            lines.append(f"<dim>Needs Strength {d['str_req']} to move freely.</>")
        if d.get("stealth_disadvantage"):
            lines.append("<dim>Noisy: disadvantage on Stealth.</>")
        if not sheet.proficient_with_armor(item):
            lines.append("<warn>You are not trained to fight in this.</>")
    elif cat == "shield":
        lines.append(f"+{d.get('ac_bonus', 2)} AC · held in the off hand")
    elif cat == "helmet":
        lines.append("Protects the head from wounds.")
    elif cat == "clothing":
        lines.append(f"{SLOT_NAMES.get(d['slot'], d['slot'])} · warmth {d.get('warmth', 0)} · wind {int(d.get('wind', 0) * 100)}% "
                     f"· rain {int(d.get('water', 0) * 100)}%")
    elif cat == "food":
        food = d["food"]
        lines.append(f"About {food['nutrition']:g} day's food · {food.get('state', 'fresh')}"
                     + (" · must be cooked" if food.get("needs_cooking") else "") + (" · raw" if food.get("raw") else ""))
        spoil = spoilage_text(game, item)
        if spoil:
            lines.append(f"Keeps: {spoil}")
    elif cat == "drink":
        drink = d["drink"]
        lines.append("Strong drink." if drink.get("alcohol", 0) >= 3 else "Quenches thirst" +
                     (", and goes to the head." if drink.get("alcohol") else "."))
    if d.get("container"):
        from realmwalker.game.survival import WATER_NAMES

        cap = d["container"].get("liquid", 0) * item.qty
        if item.fill:
            risky = item.fill_kind not in ("clean", "boiled")
            warn = " <warn>(not safe unboiled)</>" if risky else ""
            lines.append(f"Holds {cap:g} pints: {item.fill:g} of {WATER_NAMES.get(item.fill_kind, 'water')}{warn}.")
        else:
            lines.append(f"Holds {cap:g} pints. Empty. Fill it at a well, river or lake (w).")
    if d.get("bedding"):
        lines.append(f"Bedding: {d['bedding']} warmth while you sleep.")
    if d.get("light"):
        lines.append(f"Gives light for about {d['light']['hours']} hour(s).")
    weight = t.weight(item)
    lines.append(f"<dim>Weight {weight:g} lb · worth about {money_text(t.value(item))} · condition: {t.condition_word(item)}</>")
    if "stolen" in item.tags:
        lines.append("<danger>Stolen.</>")
    return "\n".join(lines)


def load_line(sheet: Sheet) -> str:
    light, heavy, limit = sheet.capacity()
    enc = sheet.encumbrance()
    word, color = ENCUMBRANCE_WORDS[enc]
    return f"Load {sheet.load():g} / {light:g} lb · <{color}>{word}</>"


# ---------------------------------------------------------------------------- character sheet
class CharacterScreen(Screen):
    title = "Character"

    def __init__(self, app, game: GameState, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.notes = ScrollText("")

    @property
    def char(self):
        return self.game.party[self.index]

    def render(self, canvas: Canvas) -> None:
        g = self.game
        c = self.char
        t = g.tables
        s = Sheet(c, t)
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"{markup.escape(c.name)}", double=True)
        col1, col2 = 2, 2 + 38
        col3 = col2 + 34
        race = t.races[c.race]["name"]
        culture = t.names["cultures"].get(c.culture, {}).get("label", c.culture)
        cls = t.classes[c.cls]
        sub = f" ({cls['subclasses'][c.subclass]['name']})" if c.subclass else ""
        nxt = s.xp_for_next()
        lines = [
            f"<name>{markup.escape(c.name)}</>",
            f"{c.sex.capitalize()}, {c.age} · {race} ({culture})",
            f"{cls['name']} {c.level}{sub}",
            f"<dim>Background:</> {t.backgrounds[c.background]['name']}",
            f"<dim>Experience:</> {c.xp}" + (f" / {nxt}" if nxt else ""),
            "",
            f"<dim>Hit points</>   <good>{c.hp}</> / {c.max_hp}",
            f"<dim>Armour class</> {s.armor_class()}",
            f"<dim>Speed</>        {s.speed()} ft",
            f"<dim>Initiative</>   {signed(s.initiative)}",
            f"<dim>Proficiency</>  +{s.proficiency}",
            f"<dim>Passive Perception</> {s.passive_perception}",
            "",
            "<title>Ability      Score  Mod  Save</>",
        ]
        for a in ABILITIES:
            name = t.rules["abilities"][a]["name"]
            prof = "●" if a in c.saves else " "
            lines.append(f"{name:<12} {c.abilities[a]:>4}  {signed(s.mod(a)):>3}  {prof}{signed(s.save_bonus(a))}")
        lines += ["", f"<dim>Languages:</> {', '.join(c.languages)}",
                  f"<dim>Tools:</> {', '.join(t.rules['tools'].get(x, x) for x in c.tools) or 'none'}",
                  f"<dim>Armour:</> {', '.join(c.armor_prof) or 'none'}",
                  f"<dim>Weapons:</> {', '.join(c.weapon_prof)}"]
        y = 2
        for line in lines:
            y += canvas.wrapped(col1, y, line, 36, max_lines=2)
            if y > h - 4:
                break
        canvas.text(col2, 2, "Skills", colors.TITLE)
        for i, (sid, sk) in enumerate(t.rules["skills"].items()):
            mark = "♦" if sid in c.expertise else ("●" if sid in c.skills else "·")
            fg = colors.FG if sid in c.skills else colors.DIM
            canvas.text(col2, 3 + i, f"{mark} {sk['name']:<16} {signed(s.skill_bonus(sid)):>3} {sk['ability'].upper()}", fg)
        canvas.text(col2, 4 + len(t.rules["skills"]), "● trained  ♦ expert", colors.FAINT)

        notes = []
        for trait in s.race["traits"]:
            notes.append(f"<loot>{trait['name']}</> <dim>({race})</>: {trait['text']}")
        for f in s.features():
            if f["id"] in ("subclass", "asi") or (f["id"] == "fighting_style" and c.fighting_style):
                continue
            notes.append(f"<loot>{f['name']}</>: {f['text']}")
        if c.fighting_style:
            st = cls["fighting_styles"][c.fighting_style]
            notes.append(f"<loot>Fighting Style: {st['name']}</>: {st['text']}")
        feature = t.backgrounds[c.background]["feature"]
        notes.append(f"<loot>{feature['name']}</> <dim>(background)</>: {feature['text']}")
        notes.append("")
        for tie in c.ties:
            notes.append(f"<title>Tie:</> {markup.escape(tie['text'])}")
        notes.append("")
        notes.append(f"<title>Looks:</> {markup.escape(c.appearance)}")
        for label, value in (("Personality", c.personality), ("Ideal", c.ideal), ("Bond", c.bond), ("Flaw", c.flaw)):
            if value:
                notes.append(f"<title>{label}:</> {markup.escape(value)}")
        if c.backstory:
            notes += ["", markup.escape(c.backstory)]
        text = "\n".join(notes)
        if self.notes.text != text:
            self.notes.set_text(text)
        self.notes.render(canvas, col3, 2, max(20, w - col3 - 2), h - 6)
        bx = canvas.button(2, h - 3, "Inventory", lambda: self._switch(InventoryScreen), hotkey="i")
        bx = canvas.button(bx + 3, h - 3, "Equipment", lambda: self._switch(EquipmentScreen), hotkey="e")
        canvas.button(bx + 3, h - 3, "Back", self.close, hotkey="Esc")

    def _switch(self, cls) -> None:
        self.app.replace(cls(self.app, self.game, self.index))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "c"):
            self.close()
        elif ev.key == "i":
            self._switch(InventoryScreen)
        elif ev.key == "e":
            self._switch(EquipmentScreen)
        else:
            return self.notes.handle_key(ev)
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "pagedown", "i", "e", "escape")]


# ---------------------------------------------------------------------------- inventory
FILTERS = [
    ("All", None),
    ("Weapons", {"weapon", "ammo"}),
    ("Armour", {"armor", "shield", "helmet"}),
    ("Clothing", {"clothing"}),
    ("Gear", {"gear", "tool", "focus", "book"}),
    ("Food", {"food", "drink"}),
    ("Trade", {"trade"}),
]
SORTS = ["category", "name", "weight", "value"]


class InventoryScreen(Screen):
    title = "Inventory"

    def __init__(self, app, game: GameState, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.filter = 0
        self.sort = 0
        self.selected = 0
        self.offset = 0

    @property
    def char(self):
        return self.game.party[self.index]

    def visible_items(self) -> list[Item]:
        t = self.game.tables.items
        cats = FILTERS[self.filter][1]
        items = [i for i in self.char.inventory if cats is None or t.category(i) in cats]
        key = SORTS[self.sort]
        order = list(CATEGORY_NAMES)
        if key == "category":
            items.sort(key=lambda i: (order.index(t.category(i)) if t.category(i) in order else 99, t.name(i)))
        elif key == "name":
            items.sort(key=lambda i: t.name(i))
        elif key == "weight":
            items.sort(key=lambda i: -t.weight(i))
        else:
            items.sort(key=lambda i: -t.value(i))
        return items

    def current(self) -> Item | None:
        items = self.visible_items()
        if not items:
            return None
        self.selected = max(0, min(self.selected, len(items) - 1))
        return items[self.selected]

    # ------------------------------------------------------------------ actions
    def action_name(self, it: Item | None) -> str:
        if it is None:
            return "Use"
        d = self.game.tables.items.get(it.def_id)
        if d.get("food"):
            return "Eat"
        if d.get("drink") or (d.get("container") and it.fill > 0):
            return "Drink"
        if d.get("use", {}).get("painkiller"):
            return "Take"
        if self.game.tables.items.slots_for(it) or self.char.slot_of(it.uid):
            return "Remove" if self.char.slot_of(it.uid) else "Wear / wield"
        return "Use"

    def use(self) -> None:
        """Enter: wear or take off, eat, or drink, depending on the item."""
        it = self.current()
        if it is None:
            return
        name = self.action_name(it)
        if name == "Eat":
            self.eat(it)
        elif name == "Drink":
            self.drink(it)
        elif name == "Take":
            from realmwalker.game import care

            for msg in care.painkiller(self.game, self.char):
                self.game.say(msg, "info")
        elif name == "Use":
            self.game.say("You can't use that here. (Bandages, herbs and kits are used on the Health screen, h.)",
                          "system")
        else:
            self.toggle_equip()

    def eat(self, it: Item) -> None:
        from realmwalker.game.survival import eat_item

        c = self.char
        if c.hunger < 5:
            self.game.say(f"{c.name.split()[0]} is not hungry.", "system")
            return
        food = self.game.tables.items.get(it.def_id)["food"]
        if food.get("needs_cooking") and not (self.game.camp and self.game.camp.fire):
            self.game.say("That needs cooking over a fire first (make camp with a fire: r).", "warn")
            return
        self.game.say(eat_item(self.game, c, it), "info")
        self.game.pass_time(10)
        self.game.dirty = True

    def drink(self, it: Item) -> None:
        from realmwalker.game import survival
        from realmwalker.rules import body

        c = self.char
        d = self.game.tables.items.get(it.def_id)
        if d.get("drink"):
            from realmwalker.rules.inventory import remove_item

            drink = d["drink"]
            remove_item(c, it.uid, 1)
            body.drink(c, float(drink.get("water", 0.5)) * 2, float(drink.get("alcohol", 0)))
            self.game.say(f"{c.name.split()[0]} drinks the {d['name']}.", "info")
        else:
            if c.thirst < 3:
                self.game.say(f"{c.name.split()[0]} is not thirsty.", "system")
                return
            pints = min(it.fill, max(1.0, round(c.thirst / body.PINT_POINTS)))
            kind = it.fill_kind
            it.fill = round(it.fill - pints, 2)
            if it.fill <= 0:
                it.fill, it.fill_kind = 0.0, ""
            survival.drink_from(self.game, c, kind, pints, "the waterskin")
            self.game.say(f"{c.name.split()[0]} drinks {pints:g} pint{'s' if pints != 1 else ''} of "
                          f"{survival.WATER_NAMES.get(kind, 'water')}.", "info")
        self.game.pass_time(2)
        self.game.dirty = True

    def toggle_equip(self) -> None:
        it = self.current()
        if it is None:
            return
        c = self.char
        t = self.game.tables.items
        slot = c.slot_of(it.uid)
        if slot is not None:
            unequip(c, slot)
            self.game.say(f"You take off the {t.name(it, False)}.", "info")
        else:
            ok, msg = equip(c, t, it.uid)
            self.game.say(msg, "info" if ok else "warn")
        self.game.dirty = True

    def drop(self, all_of_it: bool = True) -> None:
        it = self.current()
        if it is None:
            return
        qty = None if all_of_it else 1
        name = self.game.tables.items.name(it)
        if self.game.local is None:
            self.game.say("Enter the land around you (>) to put things down; by the roadside they would be lost.", "system")
            return
        if all_of_it and it.qty > 1:
            self.app.push(ConfirmBox(self.app, f"Put down all of the {markup.escape(name)}?",
                                     lambda: self.game.drop(it.uid, None), title="Drop"))
        else:
            self.game.drop(it.uid, qty)

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        g = self.game
        c = self.char
        t = g.tables.items
        s = Sheet(c, g.tables)
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"Inventory — {markup.escape(c.name)}", double=True)
        x = 2
        for i, (name, _) in enumerate(FILTERS):
            label = f"[{name}]" if i == self.filter else f" {name} "
            over = canvas.hit(x, 2, len(label), 1, action=lambda i=i: self._set_filter(i))
            x = canvas.text(x, 2, label, colors.SELECT_FG if i == self.filter else (colors.FG if over else colors.DIM)) + 1
        canvas.text(x + 2, 2, f"sort: {SORTS[self.sort]} (s)", colors.FAINT)
        list_w = min(64, w - 40)
        canvas.text(2, 4, f"{'':2}{'Item':<32}{'Wt':>6}{'Value':>10}  Note", colors.DIM)
        items = self.visible_items()
        rows = h - 10
        if self.selected < self.offset:
            self.offset = self.selected
        if self.selected >= self.offset + rows:
            self.offset = self.selected - rows + 1
        for i, it in enumerate(items[self.offset:self.offset + rows]):
            idx = i + self.offset
            y = 5 + i
            selected = idx == self.selected
            over = canvas.hit(2, y, list_w, 1, action=lambda idx=idx: self._click(idx),
                              right_action=lambda idx=idx: self._select_and(idx, self.toggle_equip))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(2, y, list_w, 1, bg)
            worn = "▪" if c.slot_of(it.uid) else " "
            name = markup.escape(t.name(it))[:31]
            canvas.text(2, y, f"{worn} ", colors.named("good"), bg)
            canvas.text(4, y, name, colors.SELECT_FG if selected else colors.FG, bg)
            canvas.text(36, y, f"{t.weight(it):>6g}", colors.DIM, bg)
            canvas.text(42, y, f"{money_text(t.value(it)):>10}"[-10:], colors.named("loot"), bg)
            note = spoilage_text(g, it) or ("" if it.condition >= 90 else f"<dim>{t.condition_word(it)}</>")
            canvas.markup(54, y, note, bg=bg, max_width=list_w - 52)
        if not items:
            canvas.text(4, 5, "Nothing here.", colors.DIM)
        dx = 2 + list_w + 2
        canvas.frame(dx - 1, 4, w - dx, h - 9, "", fg=colors.FAINT, bg=None)
        cur = self.current()
        if cur is not None:
            canvas.wrapped(dx + 1, 5, item_details(g, cur), w - dx - 3, max_lines=h - 12)
        canvas.markup(2, h - 4, f"{load_line(s)} · <dim>Money:</> <loot>{money_text(c.money)}</>", max_width=w - 4)
        bx = canvas.button(2, h - 3, self.action_name(cur), self.use, hotkey="Enter")
        bx = canvas.button(bx + 3, h - 3, "Drop", self.drop, hotkey="d")
        bx = canvas.button(bx + 3, h - 3, "Drop one", lambda: self.drop(False), hotkey="D")
        bx = canvas.button(bx + 3, h - 3, "Equipment", lambda: self.app.replace(EquipmentScreen(self.app, g, self.index)), hotkey="e")
        canvas.button(bx + 3, h - 3, "Back", self.close, hotkey="Esc")

    def _set_filter(self, i: int) -> None:
        self.filter = i
        self.selected = 0
        self.offset = 0

    def _click(self, idx: int) -> None:
        if idx == self.selected:
            self.use()
        self.selected = idx

    def _select_and(self, idx: int, fn) -> None:
        self.selected = idx
        fn()

    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.visible_items())
        if ev.key in ("escape", "i"):
            self.close()
        elif ev.key == "up":
            self.selected = max(0, self.selected - 1)
        elif ev.key == "down":
            self.selected = min(max(0, n - 1), self.selected + 1)
        elif ev.key == "pageup":
            self.selected = max(0, self.selected - 10)
        elif ev.key == "pagedown":
            self.selected = min(max(0, n - 1), self.selected + 10)
        elif ev.key in ("left", "right"):
            self._set_filter((self.filter + (1 if ev.key == "right" else -1)) % len(FILTERS))
        elif ev.key == "s":
            self.sort = (self.sort + 1) % len(SORTS)
        elif ev.key == "enter":
            self.use()
        elif ev.key == "d":
            self.drop(True)
        elif ev.key == "D":
            self.drop(False)
        elif ev.key == "e":
            self.app.replace(EquipmentScreen(self.app, self.game, self.index))
        elif ev.key == "c":
            self.app.replace(CharacterScreen(self.app, self.game, self.index))
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("up", "down", "down", "left", "right", "s", "enter", "enter", "D", "escape")]


# ---------------------------------------------------------------------------- equipment
BODY = [
    # (text, part) drawn top to bottom; parts light up when covered.
    ("   .---.   ", "head"),
    ("   | o |   ", "head"),
    ("   '---'   ", "head"),
    (" ___|||___ ", "torso"),
    ("/|  ###  |\\", "arms"),
    ("||  ###  ||", "arms"),
    ("||  ###  ||", "torso"),
    ("m|__###__|m", "hands"),
    ("   |   |   ", "legs"),
    ("   |   |   ", "legs"),
    ("   |   |   ", "legs"),
    ("  _|   |_  ", "feet"),
]


class EquipmentScreen(Screen):
    title = "Equipment"

    def __init__(self, app, game: GameState, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.selected = 0

    @property
    def char(self):
        return self.game.party[self.index]

    def slot(self) -> str:
        return EQUIP_SLOTS[self.selected]

    def pick(self) -> None:
        slot = self.slot()
        options = best_slot_items(self.char, self.game.tables.items, slot)
        if not options:
            self.app.notify(f"You have nothing to wear or hold there ({SLOT_NAMES[slot].lower()}).", "warn")
            return
        self.app.push(ItemPicker(self.app, self.game, self.char, slot, options))

    def remove(self) -> None:
        it = unequip(self.char, self.slot())
        if it is not None:
            self.game.say(f"You take off the {self.game.tables.items.name(it, False)}.", "info")
            self.game.dirty = True

    def render(self, canvas: Canvas) -> None:
        g = self.game
        c = self.char
        t = g.tables.items
        s = Sheet(c, g.tables)
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"Equipment — {markup.escape(c.name)}", double=True)
        canvas.text(2, 2, "Slot            Item", colors.DIM)
        for i, slot in enumerate(EQUIP_SLOTS):
            y = 3 + i
            selected = i == self.selected
            it = c.equipped_item(slot)
            over = canvas.hit(2, y, 60, 1, action=lambda i=i: self._click(i), right_action=lambda i=i: self._remove_at(i))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(2, y, 60, 1, bg)
            canvas.text(2, y, ("► " if selected else "  ") + f"{SLOT_NAMES[slot]:<14}", colors.SELECT_FG if selected else colors.FG, bg)
            name = markup.escape(t.name(it)) if it else "—"
            canvas.text(18, y, name, colors.named("loot") if it else colors.FAINT, bg, max_width=44)
        cover = s.coverage()
        bx, by = 66, 3
        canvas.text(bx, by - 1, "Protection", colors.TITLE)
        for i, (text, part) in enumerate(BODY):
            fg = colors.named("good") if cover[part] else colors.FAINT
            canvas.text(bx, by + i, text, fg)
        ly = by
        for part in ("head", "torso", "arms", "legs", "hands", "feet"):
            items = ", ".join(cover[part]) or "<dim>unprotected</>"
            canvas.markup(bx + 13, ly, f"<dim>{part.capitalize():<6}</> {items}", max_width=w - bx - 15)
            ly += 2
        y = 3 + len(EQUIP_SLOTS) + 2
        social = SOCIAL_WORDS.get(s.social(), "plain")
        info = [
            f"<dim>Armour class</> {s.armor_class()}",
            f"<dim>Warmth of clothes</> {s.warmth():g} <dim>· keeps out wind</> {int(s.wind_protection() * 100)}% "
            f"<dim>· keeps out rain</> {int(s.water_protection() * 100)}%",
            f"<dim>People will see you as</> {social}.",
            load_line(s),
        ]
        armor = c.equipped_item("armor")
        if armor is not None and not s.proficient_with_armor(armor):
            info.append("<warn>You are not trained in this armour: clumsy and exhausting.</>")
        if s.armor_too_heavy():
            info.append("<warn>Your armour is too heavy for your strength: you move slower.</>")
        for line in info:
            y += canvas.wrapped(2, y, line, min(62, w - 4))
        cur = c.equipped_item(self.slot())
        if cur is not None and h - 4 - y > 3:
            canvas.wrapped(2, y + 1, item_details(g, cur), min(62, w - 4), max_lines=h - 6 - y)
        bx2 = canvas.button(2, h - 3, "Choose item", self.pick, hotkey="Enter")
        bx2 = canvas.button(bx2 + 3, h - 3, "Take off", self.remove, hotkey="u")
        bx2 = canvas.button(bx2 + 3, h - 3, "Inventory", lambda: self.app.replace(InventoryScreen(self.app, g, self.index)), hotkey="i")
        canvas.button(bx2 + 3, h - 3, "Back", self.close, hotkey="Esc")

    def _click(self, i: int) -> None:
        if i == self.selected:
            self.pick()
        self.selected = i

    def _remove_at(self, i: int) -> None:
        self.selected = i
        self.remove()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "e"):
            self.close()
        elif ev.key == "up":
            self.selected = (self.selected - 1) % len(EQUIP_SLOTS)
        elif ev.key == "down":
            self.selected = (self.selected + 1) % len(EQUIP_SLOTS)
        elif ev.key == "enter":
            self.pick()
        elif ev.key == "u":
            self.remove()
        elif ev.key == "i":
            self.app.replace(InventoryScreen(self.app, self.game, self.index))
        elif ev.key == "c":
            self.app.replace(CharacterScreen(self.app, self.game, self.index))
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("up", "down", "down", "enter", "u", "escape")]


class ItemPicker(Screen):
    """Choose which item goes in an equipment slot."""

    modal = True

    def __init__(self, app, game: GameState, char, slot: str, options: list[Item]) -> None:
        super().__init__(app)
        self.game = game
        self.char = char
        self.slot = slot
        self.options = options
        self.selected = 0

    def choose(self, i: int) -> None:
        it = self.options[i]
        ok, msg = equip(self.char, self.game.tables.items, it.uid, self.slot)
        self.game.say(msg, "info" if ok else "warn")
        self.game.dirty = True
        self.close()

    def render(self, canvas: Canvas) -> None:
        t = self.game.tables.items
        x, y, w, h = modal_box(canvas, 60, len(self.options) + 5, f"{SLOT_NAMES[self.slot]}: choose")
        for i, it in enumerate(self.options):
            selected = i == self.selected
            over = canvas.hit(x + 2, y + 2 + i, w - 4, 1, action=lambda i=i: self.choose(i))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x + 2, y + 2 + i, w - 4, 1, bg)
            worn = " (worn)" if self.char.slot_of(it.uid) else ""
            canvas.text(x + 2, y + 2 + i, ("► " if selected else "  ") + t.name(it) + worn,
                        colors.SELECT_FG if selected else colors.FG, bg, max_width=w - 4)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            self.close()
        elif ev.key == "up":
            self.selected = (self.selected - 1) % len(self.options)
        elif ev.key == "down":
            self.selected = (self.selected + 1) % len(self.options)
        elif ev.key == "enter":
            self.choose(self.selected)
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("enter"), KeyEvent("escape")]
