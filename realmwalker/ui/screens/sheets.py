"""Character sheet, inventory and equipment screens."""

from __future__ import annotations

from realmwalker.game import gear
from realmwalker.game.magic import lasting_text
from realmwalker.game.state import GameState
from realmwalker.rules import describe, progression
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import ABILITIES, Sheet, signed
from realmwalker.rules.inventory import best_slot_items, equip, pack_mates, unequip, worn_by
from realmwalker.rules.items import CATEGORY_NAMES, EQUIP_SLOTS, SLOT_NAMES, Item, money_short, money_text
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


def spoilage_text(game: GameState, item: Item, in_list: bool = False) -> str:
    """How long food keeps: "60 days" (in a list, "keeps 60 days", or it reads like 60 days of food)."""
    food = game.tables.items.get(item.def_id).get("food")
    if not food or not food.get("spoil_days"):
        return ""
    age_days = (game.world.time - item.made_at) / (60 * 24)
    left = food["spoil_days"] - age_days
    if left <= 0:
        return "<danger>spoiled</>"
    if left < 2:
        return "<warn>going off</>"
    if in_list:
        return "<dim>keeps months</>" if left >= 100 else f"<dim>keeps {int(left)} days</>"
    return f"<dim>{int(left)} days</>"


def item_details(game: GameState, item: Item) -> str:
    t = game.tables.items
    d = t.get(item.def_id)
    sheet = game.sheet()
    lines = [f"<loot>{markup.escape(t.name(item))}</>"]
    if d.get("description"):
        lines.append(d["description"])
    if item.magic:
        from realmwalker.game.magic_items import describe

        lines += describe(game, item)
    cat = d["category"]
    if cat == "weapon":
        props = ", ".join(p.replace("_", "-") for p in d.get("properties", [])) or "none"
        extra = f" (two hands {d['versatile']})" if d.get("versatile") else ""
        rng = f" · range {d['range'][0]}/{d['range'][1]} ft" if d.get("range") else ""
        lines.append(f"Damage {d['damage']}{extra} {d['damage_type']}{rng}")
        lines.append(f"<dim>{d.get('group', '').capitalize()} weapon · {props}</>")
        if d.get("mastery"):
            trick = game.tables.traits["traits"].get(f"mastery_{d['mastery']}", {})
            known = item.def_id in getattr(sheet.c, "masteries", ())
            lines.append(f"{'<good>' if known else '<dim>'}Mastery: {d['mastery'].title()}</> "
                         f"<dim>{trick.get('text', '')}{'' if known else ' (not mastered)'}</>")
        if not sheet.proficient_with_weapon(item):
            lines.append("<warn>You are not trained with this weapon.</>")
    elif cat == "armor":
        dex = {"light": "+ Dex", "medium": "+ Dex (max 2)", "heavy": ""}[d["armor_type"]]
        lines.append(f"{d['armor_type'].capitalize()} armour · AC {d['ac']} {dex}")
        lines.append(f"<dim>Covers: {', '.join(d.get('covers', []))}</>")
        from realmwalker.rules import magic as magicrules

        light = magicrules.item_flag(item, "mithral")
        if d.get("str_req") and not light:
            lines.append(f"<dim>Needs Strength {d['str_req']} to move freely.</>")
        if d.get("stealth_disadvantage") and not light:
            lines.append("<dim>Noisy: disadvantage on Stealth.</>")
        if not sheet.proficient_with_armor(item):
            lines.append("<warn>You are not trained to fight in this.</>")
    elif cat == "shield":
        lines.append(f"+{d.get('ac_bonus', 2)} AC · held in the off hand")
        if not sheet.proficient_with_armor(item):
            lines.append("<warn>Untrained with shields: it gives you no protection.</>")
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
    lines += gear_lines(game, item, d)
    if d.get("light"):
        hours = d["light"]["hours"]
        lines.append(f"Gives light for about {hours:g} hour{'' if hours == 1 else 's'}.")
    weight = t.weight(item)
    lines.append(f"<dim>Weight {weight:g} lb · worth about {money_text(t.value(item))} · condition: {t.condition_word(item)}</>")
    if "stolen" in item.tags:
        lines.append("<danger>Stolen.</>")
    return "\n".join(lines)


IMPRESS_WORDS = {"high": "Lords, ladies and their people", "priests": "Priests", "soldiers": "Guards and soldiers",
                 "traders": "Shopkeepers, smiths and traders"}


def gear_lines(game: GameState, item: Item, d: dict) -> list[str]:
    """What a thing does for you, in a line or two each (game/gear.py and the rules that read the item's data)."""
    t = game.tables.items
    out = []
    cat = d["category"]
    if d.get("carry"):
        out.append(f"<good>Worn on the back: you can carry {d['carry']:g} lb more</> before you count as laden.")
    if d.get("focus"):
        f = d["focus"]
        who = "a wizard" if f["kind"] == "arcane" else "a priest"
        how = "carried" if f.get("carried") else ("worn or held" if d.get("slot") else "held in the hand")
        out.append(f"<magic>Spell focus</> for {who}: +1 to spell attacks and the DC of their spells, {how}.")
    if d.get("impress"):
        imp = d["impress"]
        how = "wears" if imp.get("worn") else "carries"
        out.append(f"{IMPRESS_WORDS.get(imp['people'], 'Some people')} think better of whoever {how} it.")
    for skill, n in (d.get("bonus") or {}).get("skills", {}).items():
        name = game.tables.rules["skills"].get(skill, {}).get("name", skill)
        out.append(f"{n:+d} to {name} while worn.")
    if cat == "jewellery" and d.get("social") and not item.magic:
        out.append("Worn, it makes you look better off.")
    if d.get("mends"):
        mats = ", ".join(t.materials.get(m, {}).get("name", m) for m in d["mends"]["materials"])
        out.append(f"Mends things of {mats}: an hour's work (better if you are trained with it).")
    use = d.get("use") or {}
    if use.get("throw") and use["throw"] in game.tables.spells:
        out.append(f"<danger>Thrown in a fight</> (Item): {game.tables.spells[use['throw']]['text']}")
    if cat in ("weapon", "armor", "shield", "helmet") and not item.magic and \
            item.condition < int(t.upkeep.get("battered", 30)):
        out.append("<warn>Battered: " + ("-1 to hit with it" if cat == "weapon" else "-1 to armour class" if cat == "armor"
                                         else "it will not last") + ". A smith, or the right tools, can mend it.</>")
    if d.get("how") and not d.get("description", "").startswith(d["how"][:20]):
        out.append(f"<dim>{d['how']}</>")
    return out


def load_line(sheet: Sheet) -> str:
    """The load against what can be carried: the whole party's, when it shares one pack."""
    light, heavy, limit = sheet.pack_capacity()
    enc = sheet.encumbrance()
    word, color = ENCUMBRANCE_WORDS[enc]
    who = "Party load" if len(pack_mates(sheet.c)) > 1 else "Load"
    return f"{who} {sheet.pack_load():g} / {light:g} lb · <{color}>{word}</>"


# ---------------------------------------------------------------------------- character sheet
class CharacterScreen(Screen):
    title = "Character"

    def __init__(self, app, game: GameState, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.notes = ScrollText("")
        self.show_skills = True  # in a narrow window the notes take the skills' place (s switches)

    @property
    def char(self):
        return self.game.party[self.index]

    def narrow(self, width: int) -> bool:
        return width - (2 + 38 + 34) - 2 < 24

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
        culture = t.cultures.adjective(self.game.world, c.culture)
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
        ]
        on = spellrules.lasting(c, t)
        if on:
            lines.append("<dim>Spells on you:</> " + ", ".join(
                f"<magic>{t.spells[sid]['name']}</> <dim>({lasting_text(hours)})</>" for sid, hours in on.items()))
        lines += [
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
                  f"<dim>Weapons:</> {t.items.proficiency_words(c.weapon_prof) or 'none'}"]
        y = 2
        for line in lines:
            y += canvas.wrapped(col1, y, line, 36, max_lines=2)
            if y > h - 4:
                break
        narrow = self.narrow(w)
        if narrow and not self.show_skills:
            col3 = col2  # the notes, where the skills were
        else:
            canvas.text(col2, 2, "Skills", colors.TITLE)
            for i, (sid, sk) in enumerate(t.rules["skills"].items()):
                mark = "♦" if sid in c.expertise else ("●" if sid in c.skills else "·")
                fg = colors.FG if sid in c.skills else colors.DIM
                canvas.text(col2, 3 + i, f"{mark} {sk['name']:<16} {signed(s.skill_bonus(sid)):>3} {sk['ability'].upper()}",
                            fg, max_width=w - col2 - 1)
            canvas.text(col2, 4 + len(t.rules["skills"]), "● trained  ♦ expert", colors.FAINT, max_width=w - col2 - 1)
            top = 6 + len(t.rules["skills"])
            room = h - 5 - top
            if room >= 7:  # the person, as they stand, in what they wear
                from realmwalker.ui.gfx import scenes

                fw = min(col3 - col2 - 3, max(14, room * canvas.cell_h // canvas.cell_w))
                canvas.clear_cells(col2, top, fw, room)
                scenes.figure(canvas, c, t, tuple(int(v) for v in canvas.cell_rect(col2, top, fw, room)))

        notes = []
        for trait in s.race["traits"]:
            notes.append(f"<loot>{trait['name']}</> <dim>({race})</>: {trait['text']}")
        for f in s.features():
            if f["id"] in ("subclass", "asi") or (f["id"] == "fighting_style" and c.fighting_style):
                continue
            if f["id"] == "weapon_mastery" and c.masteries:
                names = ", ".join(f"{t.items.get(w)['name']} ({t.items.get(w)['mastery'].title()})"
                                  for w in c.masteries if w in t.items)
                change = " <dim>(m: choose again)</>" if c.uses.get("mastery_change", 0) > 0 else ""
                notes.append(f"<loot>{f['name']}</>: {names}.{change}")
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
        if c is g.leader and (c.deeds or g.renown.fame or g.renown.infamy):
            r = g.renown
            notes.append(f"<title>Known for</> <dim>(fame {r.fame}, infamy {r.infamy})</>")
            for deed in c.deeds[-6:][::-1]:
                notes.append(f"  · {markup.escape(deed)}")
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
        if not narrow or not self.show_skills:
            self.notes.render(canvas, col3, 2, w - col3 - 2, h - 6)
        bx = canvas.button(2, h - 3, "Inventory", lambda: self._switch(InventoryScreen), hotkey="i")
        if narrow:
            bx = canvas.button(bx + 3, h - 3, "Notes" if self.show_skills else "Skills", self.toggle_skills, hotkey="s")
        bx = canvas.button(bx + 3, h - 3, "Equipment", lambda: self._switch(EquipmentScreen), hotkey="e")
        if c.pending:
            bx = canvas.button(bx + 3, h - 3, f"Level-up choices ({len(c.pending)})", self.level_up, hotkey="l")
        if c.masteries and c.uses.get("mastery_change", 0) > 0 and not narrow:  # (narrow: the m key, as the notes say)
            bx = canvas.button(bx + 3, h - 3, "Masteries", self.change_masteries, hotkey="m")
        if len(g.party) > 1:
            bx = canvas.button(bx + 3, h - 3, "Next member", self.next_member, hotkey="Tab")
        canvas.button(bx + 3, h - 3, "Back", self.close, hotkey="Esc")

    def toggle_skills(self) -> None:
        self.show_skills = not self.show_skills

    def change_masteries(self) -> None:
        """Choose the weapons mastered again (once after each long rest, and before the first)."""
        if progression.relearn_masteries(self.char, self.game.tables):
            self.game.dirty = True
            self.level_up()

    def level_up(self) -> None:
        from realmwalker.ui.screens.levelup import LevelUpScreen

        self.app.push(LevelUpScreen(self.app, self.game, self.index))

    def next_member(self) -> None:
        self.index = (self.index + 1) % len(self.game.party)
        self.notes.set_text("")

    def _switch(self, cls) -> None:
        self.app.replace(cls(self.app, self.game, self.index))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "c"):
            self.close()
        elif ev.key == "i":
            self._switch(InventoryScreen)
        elif ev.key == "e":
            self._switch(EquipmentScreen)
        elif ev.key == "l" and self.char.pending:
            self.level_up()
        elif ev.key == "m" and self.char.masteries and self.char.uses.get("mastery_change", 0) > 0:
            self.change_masteries()
        elif ev.key == "tab" and len(self.game.party) > 1:
            self.next_member()
        elif ev.key == "s" and self.narrow(self.app.last_console_size[0]):
            self.toggle_skills()
        else:
            return self.notes.handle_key(ev)
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "pagedown", "tab", "l", "i", "e", "s", "escape")]


# ---------------------------------------------------------------------------- inventory
FILTERS = [
    ("All", None),
    ("Weapons", {"weapon", "ammo"}),
    ("Armour", {"armor", "shield", "helmet"}),
    ("Clothing", {"clothing"}),
    ("Gear", {"gear", "tool", "focus", "book", "jewellery"}),
    ("Food", {"food", "drink"}),
    ("Trade", {"trade"}),
]
SORTS = ["category", "name", "weight", "value"]
FILTER_ICONS = {"All": "icon/inventory", "Weapons": "item/longsword", "Armour": "item/chain_mail",
                "Clothing": "item/wool_cloak", "Gear": "item/rope", "Food": "item/bread", "Trade": "item/_coins_1"}


def item_icon(canvas, game, it) -> str:
    """The picture for a thing (its own, or one for its kind)."""
    from realmwalker.ui.gfx.localview import item_sprite

    return item_sprite(canvas.gfx.atlas, game.tables, it) or ""


def item_picture(canvas, game, it, x: float, y: float, size: float) -> None:
    """A thing, large: a weapon or shield in its own colours (a rare one as it was made, glowing if it glows), else
    its picture; magic things with a faint light behind them."""
    from realmwalker.ui.gfx import dolls
    from realmwalker.ui.gfx.scene import Image

    atlas = canvas.gfx.atlas
    magic = it.magic or {}
    glow = (magic.get("look") or {}).get("glow") if magic else None
    if magic and (glow or magic.get("identified")):
        rgb = dolls.colour(game.tables, glow, {"uncommon": (120, 200, 120), "rare": (110, 150, 255),
                                               "very_rare": (190, 120, 255)}.get(magic.get("rarity"), (200, 200, 200)))
        from realmwalker.ui.gfx.battlefx import _glow_image

        canvas.under(Image("item_glow", _glow_image, (x - size * 0.15, y - size * 0.15, size * 1.3, size * 1.3),
                           rgba=(*rgb, 150)))
    parts = dolls.item_parts(it, game.tables, atlas) if (magic.get("look") if magic else None) else None
    if parts:
        crop = dolls.bounds(atlas, parts)
        k = max(1, int(size // crop[2]))  # a whole number of screen pixels to each of its own
        side = k * crop[2]
        cmd = dolls.draw(atlas, parts, int(x + (size - side) / 2), int(y + (size - side) / 2), side, crop=crop)
        if cmd is not None:
            canvas.under(cmd)
            return
    canvas.sprite(item_icon(canvas, game, it), x, y, size, size)


GEAR_VERBS = ("Sharpen blades", "Mend gear", "Set it for the night", "Pass the evening", "Pray", "Write a scroll",
              "Throw (in a fight)")  # game/gear.use_name


class InventoryScreen(Screen):
    title = "Inventory"
    sound_open = "ui_pack"

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
        if d.get("use", {}).get("disguise"):
            return "Disguise yourself"
        if d.get("use", {}).get("scroll"):
            return "Copy into spellbook" if self.char.cls == "wizard" else "Read"
        if it.magic and not it.magic.get("identified") and not self.game.tables.items.slots_for(it):
            return "Study it"
        if d.get("use", {}).get("read"):
            return "Read it"
        if it.def_id == "sealed_letter" and any(tag.startswith("quest:") for tag in it.tags):
            return "Break the seal" if it.name.startswith("sealed") else "Read the letter"
        from realmwalker.game import gear

        verb = gear.use_name(self.game, it)
        if verb:
            return verb
        wearer, _ = worn_by(self.char, it.uid)
        if wearer is not None:
            return "Remove" if wearer is self.char else f"Take it off {wearer.name.split()[0]}"
        if self.game.tables.items.slots_for(it):
            return "Wear / wield"
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
        elif name == "Disguise yourself":
            from realmwalker.game import law

            self.game.say(law.put_on_disguise(self.game, self.char), "info")
        elif name == "Study it":
            from realmwalker.game import magic_items

            for line in magic_items.study(self.game, self.char, it):
                self.game.say(line, "magic")
        elif name == "Read it":
            from realmwalker.game import books

            for line in books.read(self.game, self.char, it):
                self.game.say(line, "info")
        elif name in ("Break the seal", "Read the letter"):
            from realmwalker.game import quests

            def read(it=it) -> None:
                for line in quests.read_letter(self.game, it):
                    self.game.say(line, "info")

            if name == "Break the seal":
                self.app.push(ConfirmBox(self.app, "Break the seal and read it? Whoever it is for will see that "
                                                   "it has been opened.", read, title="Break the seal?"))
            else:
                read()
        elif name == "Copy into spellbook":
            from realmwalker.game import magic

            for line in magic.copy_scroll(self.game, self.char, it):
                self.game.say(line, "magic")
        elif name == "Read":
            sid = self.game.tables.items.get(it.def_id)["use"]["scroll"]
            spell = self.game.tables.spells[sid]
            self.game.say(f"The scroll holds {spell['name']}: {spell['text']} It can be read aloud once in a fight "
                          f"(Cast a spell).", "magic")
        elif name == "Use":
            from realmwalker.game import gear

            self.game.say(gear.how_text(self.game, it), "system")
        elif name in GEAR_VERBS:
            from realmwalker.game import gear

            for line in gear.use_item(self.game, self.char, it):
                self.game.say(line, "info")
            self.game.dirty = True
        else:
            self.toggle_equip()

    def give(self) -> None:
        """Hand the chosen thing to the next member of the party."""
        it = self.current()
        if it is None or len(self.game.party) < 2:
            return
        from realmwalker.rules.inventory import add_existing, remove_item

        c = self.char
        other = self.game.party[(self.index + 1) % len(self.game.party)]
        if other.inventory is c.inventory:
            # One pack for the whole party: handing it over means they take it up or put it on.
            t = self.game.tables.items
            if not t.slots_for(it):
                self.game.say("You all carry from the one pack already; there is nothing to hand over.", "system")
                return
            wearer, slot = worn_by(c, it.uid)
            if wearer is not None and wearer is not other:
                unequip(wearer, slot)
            ok, msg = equip(other, t, it.uid)
            self.game.say(f"{other.name.split()[0]} takes the {t.name(it, False)}." if ok else msg,
                          "info" if ok else "warn")
            self.game.dirty = True
            return
        if c.slot_of(it.uid) is not None:
            self.game.say("Take it off first.", "system")
            return
        taken = remove_item(c, it.uid, it.qty)
        if taken is not None:
            add_existing(other, self.game.tables.items, taken)
            self.game.say(f"{c.name.split()[0]} gives {self.game.tables.items.name(taken)} to "
                          f"{other.name.split()[0]}.", "info")
            self.game.dirty = True

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
        wearer, slot = worn_by(c, it.uid)
        if slot is not None:
            if unequip(wearer, slot) is None:
                self.game.say(f"The {t.name(it, False)} will not come off.", "warn")
            else:
                who = "You take" if wearer is self.game.leader else f"{wearer.name.split()[0]} takes"
                self.game.say(f"{who} off the {t.name(it, False)}.", "info")
                gear.dressed(self.game, it, False)
        else:
            ok, msg = equip(c, t, it.uid)
            self.game.say(msg, "info" if ok else "warn")
            if ok:
                gear.dressed(self.game, it, True)
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
        s = Sheet(c, g.tables)
        w, h = canvas.width, canvas.height
        shared = len(pack_mates(c)) > 1
        title = f"The party's pack · {markup.escape(c.name.split()[0])} (Tab)" if shared else markup.escape(c.name)
        canvas.frame(0, 0, w, h - 1, f"Inventory — {title}", double=True)
        wide = w >= 116
        doll_w = 34 if wide else 0
        card_w = max(30, min(48, (w - doll_w) * 2 // 5))
        list_x = 2 + doll_w
        list_w = w - list_x - card_w - 3
        if wide:
            self._render_worn(canvas, 2, 2, doll_w - 2, h - 8)
        self._render_tabs(canvas, list_x, 2, list_w + card_w)
        self._render_list(canvas, list_x, 4, list_w, h - 10)
        self._render_card(canvas, list_x + list_w + 1, 4, card_w + 1, h - 10)
        self._render_load(canvas, 2, h - 5, w - 4, s)
        row = [("Equipment", lambda: self.app.replace(EquipmentScreen(self.app, g, self.index)), "e")] if not wide else []
        if len(g.party) > 1:
            row += [("Next member", lambda: self.handle_key(KeyEvent("tab")), "Tab")]
        canvas.button_row(2, h - 3, w - 2, row + [("Sort: " + SORTS[self.sort], self._cycle_sort, "s"),
                                                  ("Back", self.close, "Esc")])

    # ---- the left column: who wears what
    def _render_worn(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        from realmwalker.rules.items import EQUIP_SLOTS, SLOT_NAMES

        g = self.game
        c = self.char
        t = g.tables.items
        canvas.frame(x, y, w, h, markup.escape(c.name.split()[0]), fg=colors.FAINT, bg=None, style="inset")
        top = y + 1
        from realmwalker.ui.gfx import dolls

        cw, ch = canvas.cell_w, canvas.cell_h
        size = min((w - 4) * cw, 7 * ch)
        px = x * cw + (w * cw - size) / 2
        canvas.clear_cells(x + 1, top, w - 2, 7)
        from realmwalker.ui.gfx import theme

        canvas.under(*theme.panel(px - 6, top * ch + 2, size + 12, size + 4, "glass", ornaments=False))
        size = max(32, int(size) // 32 * 32)
        px = x * cw + (w * cw - size) / 2
        cmd = dolls.draw(canvas.gfx.atlas, dolls.character(c, g.tables, atlas=canvas.gfx.atlas), px,
                         top * ch + 4 + (7 * ch - 8 - size), size)
        if cmd is not None:
            canvas.over(cmd)
        top += 8
        canvas.text(x + 2, top, "Worn and held", colors.TITLE, max_width=w - 4)
        top += 1
        for i, slot in enumerate(EQUIP_SLOTS):
            ry = top + i
            if ry >= y + h - 1:
                break
            it = c.equipped_item(slot)
            over = canvas.hit(x + 1, ry, w - 2, 1, action=lambda slot=slot: self.pick_slot(slot),
                              right_action=lambda slot=slot: self.take_off(slot),
                              tooltip=(f"{SLOT_NAMES[slot]}: click to choose what goes here; right-click to take it off."))
            cur = self.current()
            if it is not None and cur is not None and it.uid == cur.uid:
                canvas.fill(x + 1, ry, w - 2, 1, colors.HILITE_BG)
            elif over:
                canvas.fill(x + 1, ry, w - 2, 1, colors.HOVER_BG)
            cx = x + 2
            if it is not None:
                canvas.icon(cx, ry, item_icon(canvas, g, it))
            cx += 3
            label_w = 13 if w - (cx - x) >= 26 else 9
            canvas.text(cx, ry, SLOT_NAMES[slot][: label_w - 1], colors.DIM, max_width=x + w - 1 - cx)
            name = markup.escape(t.name(it)) if it else "—"
            canvas.text(cx + label_w, ry, name, colors.named("loot") if it else colors.FAINT,
                        max_width=x + w - 2 - cx - label_w)

    def pick_slot(self, slot: str) -> None:
        from realmwalker.rules.items import SLOT_NAMES

        options = best_slot_items(self.char, self.game.tables.items, slot)
        if not options:
            self.app.notify(f"You have nothing to wear or hold there ({SLOT_NAMES[slot].lower()}).", "warn")
            return
        self.app.push(ItemPicker(self.app, self.game, self.char, slot, options))

    def take_off(self, slot: str) -> None:
        it = unequip(self.char, slot)
        if it is not None:
            self.game.say(f"You take off the {self.game.tables.items.name(it, False)}.", "info")
            self.game.dirty = True

    # ---- the tabs along the top
    def _render_tabs(self, canvas: Canvas, x: int, y: int, w: int) -> None:
        cx = x
        for i, (name, _) in enumerate(FILTERS):
            label = f" {name} "
            icon = FILTER_ICONS.get(name, "")
            width = len(label) + (3 if icon else 0)
            if cx + width > x + w:
                break
            over = canvas.hit(cx, y, width, 1, action=lambda i=i: self._set_filter(i), tooltip=f"Show {name.lower()} "
                              "(left and right arrows)")
            from realmwalker.ui.gfx import theme

            state = "active" if i == self.filter else ("hover" if over else "normal")
            canvas.clear_cells(cx, y, width, 1)
            canvas.under(theme.button(cx * canvas.cell_w, y * canvas.cell_h, width * canvas.cell_w,
                                      canvas.cell_h, state))
            tx = cx
            if icon:
                canvas.icon(cx + 1, y, icon)
                tx = cx + 2
            canvas.text(tx, y, label, colors.SELECT_FG if i == self.filter else colors.FG)
            cx += width + 1

    # ---- the list of things
    def _rows(self) -> list[tuple[str, object]]:
        """What the list shows: headings between kinds of thing (when sorted by kind), then the things."""
        t = self.game.tables.items
        items = self.visible_items()
        if SORTS[self.sort] != "category":
            return [("item", it) for it in items]
        out: list[tuple[str, object]] = []
        last = None
        for it in items:
            cat = t.category(it)
            if cat != last:
                out.append(("head", CATEGORY_NAMES.get(cat, cat.capitalize())))
                last = cat
            out.append(("item", it))
        return out

    def _render_list(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        g = self.game
        c = self.char
        t = g.tables.items
        canvas.frame(x - 1, y - 1, w + 2, h + 2, "", fg=colors.FAINT, bg=None, style="inset")
        name_x = x + 3
        cols_w = 18
        name_w = max(8, w - (name_x - x) - cols_w)
        canvas.text(name_x, y, "Thing", colors.DIM)
        canvas.text(x + w - cols_w, y, f"{'Wt':>5}{'Value':>9}", colors.DIM)
        rows = self._rows()
        items = [r[1] for r in rows if r[0] == "item"]
        cur = self.current()
        sel_row = next((i for i, r in enumerate(rows) if r[0] == "item" and cur is not None and r[1] is cur), 0)
        room = max(1, h - 2)
        if sel_row < self.offset:
            self.offset = max(0, sel_row - 1 if sel_row > 0 and rows[sel_row - 1][0] == "head" else sel_row)
        if sel_row >= self.offset + room:
            self.offset = sel_row - room + 1
        self.offset = max(0, min(self.offset, max(0, len(rows) - room)))

        def wheel(dy: int) -> None:
            self.offset = max(0, min(max(0, len(rows) - room), self.offset - dy * 3))

        canvas.hit(x, y + 1, w, room, wheel=wheel)
        for i, (kind, value) in enumerate(rows[self.offset:self.offset + room]):
            ry = y + 1 + i
            if kind == "head":
                canvas.section(x, ry, w, value)
                continue
            it = value
            idx = items.index(it)
            selected = cur is not None and it is cur
            over = canvas.hit(x, ry, w, 1, action=lambda idx=idx: self._click(idx),
                              right_action=lambda idx=idx: self._menu(idx),
                              tooltip=None)
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, ry, w, 1, bg)
            wearer, _ = worn_by(c, it.uid)
            canvas.icon(x, ry, item_icon(canvas, g, it))
            if wearer is not None:
                from realmwalker.ui.gfx.scene import Rect

                canvas.over(Rect(x * canvas.cell_w + 1, ry * canvas.cell_h + 1, 4, 4, (120, 210, 100, 255)))
            name = markup.escape(t.name(it))
            if wearer is not None and wearer is not c:
                who = wearer.name.split()[0]
                name = f"{name[:name_w - len(who) - 3]} ({who})"
            elif wearer is c:
                name = name[:name_w - 7] + " <dim>(worn)</>" if len(name) < name_w - 7 else name[:name_w]
            color = colors.SELECT_FG if selected else (colors.named("magic") if it.magic else colors.FG)
            marks = describe.item_marks(g, it) if it.magic else []
            canvas.markup(name_x, ry, name, fg=color, bg=bg, max_width=name_w - 2 * len(marks))
            for k, mark in enumerate(marks):  # bound to someone; a sentient thing wanting something
                mx = name_x + name_w - 2 * (len(marks) - k)
                canvas.icon(mx, ry, f"status/{mark}")
                canvas.hit(mx, ry, 2, 1, tooltip=lambda it=it, mark=mark: describe.item_mark_card(g, it, mark))
            canvas.text(x + w - cols_w, ry, f"{t.weight(it):>5g}", colors.DIM, bg)
            canvas.text(x + w - cols_w + 5, ry, f"{money_short(t.value(it)):>9}"[-9:], colors.named("loot"), bg)
        if not items:
            canvas.text(name_x, y + 2, "Nothing here.", colors.DIM)
        if len(rows) > room:
            canvas.text(x + w - 12, y + h - 1, f"{self.offset + 1}-{min(len(rows), self.offset + room)}/{len(rows)}",
                        colors.FAINT)

    # ---- the card: everything about the chosen thing, and what to do with it
    def _render_card(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        g = self.game
        c = self.char
        t = g.tables.items
        canvas.frame(x, y - 1, w, h + 2, "", fg=colors.FAINT, bg=None, style="inset")
        cur = self.current()
        ix, iw = x + 2, w - 4
        if cur is None:
            canvas.text(ix, y + 1, "Choose something on the left.", colors.DIM, max_width=iw)
            return
        top = y + 1
        from realmwalker.ui.gfx import theme
        from realmwalker.ui.gfx.scene import Text

        cw, ch = canvas.cell_w, canvas.cell_h
        size = 3 * ch
        canvas.clear_cells(ix, top, 7, 3)
        canvas.under(*theme.panel(ix * cw - 2, top * ch - 2, size + 4, size + 4, "glass", ornaments=False))
        item_picture(canvas, g, cur, ix * cw, top * ch, size)
        canvas.clear_cells(ix + 7, top, iw - 7, 1)
        canvas.over(Text((ix + 7) * cw, top * ch + ch / 2, t.name(cur), "heading", 17,
                         (214, 176, 108, 255) if not cur.magic else (200, 160, 250, 255), anchor="lm"))
        canvas.markup(ix + 7, top + 1, f"<dim>{CATEGORY_NAMES.get(t.category(cur), t.category(cur))}</>",
                      max_width=iw - 7)
        wearer, _ = worn_by(c, cur.uid)
        mx = ix + 7
        for mark in describe.item_marks(g, cur) if cur.magic else []:
            canvas.icon(mx, top + 2, f"status/{mark}")
            canvas.hit(mx, top + 2, 2, 1, tooltip=lambda mark=mark: describe.item_mark_card(g, cur, mark))
            mx += 3
        if wearer is not None:
            canvas.markup(mx, top + 2, f"<good>Worn by {markup.escape(wearer.name.split()[0])}</>",
                          max_width=ix + iw - mx)
        top += 4
        details = item_details(g, cur)
        details = details.split(chr(10), 1)[1] if chr(10) in details else ""  # the name is the heading already
        compare = self.comparison(cur)
        if compare:
            details += "\n" + compare
        buttons = self.card_actions(cur)
        room = max(2, (y + h) - top - len(buttons) - 1)
        used = canvas.wrapped(ix, top, details, iw, max_lines=room)
        by = max(top + used + 1, y + h - len(buttons))
        bw = min(iw, max(len(label) + len(key) + 3 for label, _, key in buttons))
        for i, (label, fn, key) in enumerate(buttons):
            if by + i >= y + h + 1:
                break
            pad = bw - (len(label) + len(key) + 3)
            canvas.button(ix, by + i, label + " " * max(0, pad), fn, hotkey=key, max_width=iw)

    def card_actions(self, it: Item) -> list[tuple[str, object, str]]:
        g = self.game
        out = [(self.action_name(it), self.use, "Enter")]
        wearer, slot = worn_by(self.char, it.uid)
        if wearer is not None and self.action_name(it) not in ("Remove",) and not self.action_name(it).startswith("Take it"):
            out.append(("Take it off", lambda: self.take_off_item(it), "u"))
        if it.qty > 1:
            out.append((f"Drop all {it.qty}", lambda: self.drop(True), "d"))
            out.append(("Drop one", lambda: self.drop(False), "D"))
        else:
            out.append(("Drop", lambda: self.drop(True), "d"))
        if len(g.party) > 1:
            other = g.party[(self.index + 1) % len(g.party)].name.split()[0]
            out.append((f"Give to {other}", self.give, "g"))
        if it.magic and not it.magic.get("identified") and self.action_name(it) != "Study it":
            out.append(("Study it (an hour)", lambda: self.study(it), "k"))
        if it.magic and it.magic.get("attune"):
            from realmwalker.rules import magic as magicrules

            if magicrules.is_attuned(self.char, it):
                out.append(("End the bond (an hour)", lambda: self.attune(it), "a"))
            else:
                out.append(("Attune (an hour)", lambda: self.attune(it), "a"))
        return out

    def study(self, it: Item) -> None:
        from realmwalker.game import magic_items

        for line in magic_items.study(self.game, self.char, it):
            self.game.say(line, "magic")

    def attune(self, it: Item) -> None:
        """Bind this member to the thing through a short rest, or unpick the bond (PHB 2024 attunement)."""
        from realmwalker.game import magic_items
        from realmwalker.rules import magic as magicrules

        if magicrules.is_attuned(self.char, it):
            lines = magic_items.end_attunement(self.game, self.char, it)
        else:
            lines = magic_items.attune(self.game, self.char, it)
        for line in lines:
            self.game.say(line, "magic")

    def take_off_item(self, it: Item) -> None:
        wearer, slot = worn_by(self.char, it.uid)
        if wearer is None or slot is None:
            return
        if unequip(wearer, slot) is None:
            self.game.say(f"The {self.game.tables.items.name(it, False)} will not come off.", "warn")
        else:
            self.game.say(f"{'You take' if wearer is self.game.leader else wearer.name.split()[0] + ' takes'} off the "
                          f"{self.game.tables.items.name(it, False)}.", "info")
        self.game.dirty = True

    def comparison(self, it: Item) -> str:
        """How it measures up against what is worn in its place."""
        t = self.game.tables.items
        c = self.char
        slots = t.slots_for(it)
        if not slots or worn_by(c, it.uid)[0] is not None:
            return ""
        d = t.get(it.def_id)
        now = next((c.equipped_item(sl) for sl in slots if c.equipped_item(sl) is not None), None)
        if now is None:
            return f"<good>Nothing is worn there now.</>" if d["category"] in ("armor", "helmet", "shield", "clothing") else ""
        n = t.get(now.def_id)
        if d["category"] == "weapon" and n.get("category") == "weapon":
            return f"<dim>Instead of your</> {markup.escape(t.name(now, False))}: <dim>{n['damage']} {n['damage_type']}</>"
        if d["category"] == "armor" and n.get("category") == "armor":
            sign = "<good>" if d.get("ac", 0) > n.get("ac", 0) else ("<warn>" if d.get("ac", 0) < n.get("ac", 0) else "<dim>")
            return (f"<dim>Instead of your</> {markup.escape(t.name(now, False))}: base AC {sign}{d.get('ac')}</> "
                    f"<dim>against</> {n.get('ac')}")
        if d["category"] == "clothing" and n.get("category") == "clothing":
            return (f"<dim>Instead of your</> {markup.escape(t.name(now, False))}: warmth {d.get('warmth', 0)} "
                    f"<dim>against</> {n.get('warmth', 0)}")
        return f"<dim>Instead of your</> {markup.escape(t.name(now, False))}."

    def _render_load(self, canvas: Canvas, x: int, y: int, w: int, s: Sheet) -> None:
        light, heavy, limit = s.pack_capacity()
        load = s.pack_load()
        text = f"{load_line(s)} · <dim>Money:</> <loot>{money_text(self.char.money)}</>"
        from realmwalker.ui.gfx import theme

        enc = s.encumbrance()
        color = colors.named(ENCUMBRANCE_WORDS[enc][1])
        bw = min(40, w // 3)
        canvas.clear_cells(x, y, bw, 1)
        canvas.under(*theme.bar(x * canvas.cell_w, y * canvas.cell_h + 4, bw * canvas.cell_w, canvas.cell_h - 8,
                                load / max(1.0, limit), color))
        # Marks where burdened and heavily burdened begin.
        from realmwalker.ui.gfx.scene import Rect

        for mark in (light, heavy):
            mx = x * canvas.cell_w + bw * canvas.cell_w * min(1.0, mark / max(1.0, limit))
            canvas.over(Rect(mx, y * canvas.cell_h + 2, 2, canvas.cell_h - 4, (240, 220, 170, 200)))
        canvas.markup(x + bw + 2, y, text, max_width=w - bw - 2)

    def _cycle_sort(self) -> None:
        self.sort = (self.sort + 1) % len(SORTS)
        self.offset = 0

    def _menu(self, idx: int) -> None:
        from realmwalker.ui.screens.popup import ContextMenu

        self.selected = idx
        it = self.current()
        if it is None:
            return
        entries = [(label, fn, "") for label, fn, _ in self.card_actions(it)]
        self.app.push(ContextMenu(self.app, self.app.mouse, entries, markup.escape(self.game.tables.items.name(it))))

    def _set_filter(self, i: int) -> None:
        self.filter = i
        self.selected = 0
        self.offset = 0

    def _click(self, idx: int) -> None:
        now = self.app.clock()
        if idx == self.selected and now - getattr(self, "_last_click", -9.0) < 0.5:
            self.use()  # a double click uses it (wears it, eats it, reads it...)
            self._last_click = -9.0
            return
        self._last_click = now
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
            self._cycle_sort()
        elif ev.key == "enter":
            self.use()
        elif ev.key == "d":
            self.drop(True)
        elif ev.key == "D":
            self.drop(False)
        elif ev.key == "u":
            it = self.current()
            if it is not None:
                self.take_off_item(it)
        elif ev.key == "e":
            self.app.replace(EquipmentScreen(self.app, self.game, self.index))
        elif ev.key == "c":
            self.app.replace(CharacterScreen(self.app, self.game, self.index))
        elif ev.key in ("g", "G"):
            self.give()
        elif ev.key in ("a", "k"):
            it = self.current()
            if it is not None and it.magic:
                if ev.key == "a" and it.magic.get("attune"):
                    self.attune(it)
                elif ev.key == "k" and not it.magic.get("identified"):
                    self.study(it)
                else:
                    return False
            else:
                return False
        elif ev.key == "tab" and len(self.game.party) > 1:
            self.index = (self.index + 1) % len(self.game.party)
            self.selected = 0
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("up", "down", "down", "left", "right", "s", "enter", "enter", "k", "a", "D", "u",
                                      "escape")]


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
    sound_open = "ui_pack"

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
        tx = bx + 13
        from realmwalker.ui.gfx import dolls, theme

        cw, ch = canvas.cell_w, canvas.cell_h
        size = 32 * max(2, min(20 * cw // 32, 12 * ch // 32, max(0, w - bx - 36) * cw // 32))
        canvas.under(*theme.panel(bx * cw, by * ch, size + 16, size + 12, "glass", ornaments=False))
        cmd = dolls.draw(canvas.gfx.atlas, dolls.character(c, g.tables, atlas=canvas.gfx.atlas), bx * cw + 8,
                         by * ch + 4, size)
        if cmd is not None:
            canvas.under(cmd)
        tx = bx + (size + 16) // cw + 2
        ly = by
        for part in ("head", "torso", "arms", "legs", "hands", "feet"):
            items = ", ".join(cover[part]) or "<dim>unprotected</>"
            canvas.markup(tx, ly, f"<dim>{part.capitalize():<6}</> {items}", max_width=w - tx - 2)
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
        if ok:
            gear.dressed(self.game, it, True)
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
