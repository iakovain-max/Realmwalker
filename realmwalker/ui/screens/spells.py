"""The Spells screen: what a caster knows, what they can still cast today, and what each one does."""

from __future__ import annotations

from realmwalker.rules import spells as sp
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText

SCHOOLS = {"evocation": "Evocation", "abjuration": "Abjuration", "conjuration": "Conjuration",
           "divination": "Divination", "enchantment": "Enchantment", "illusion": "Illusion",
           "necromancy": "Necromancy", "transmutation": "Transmutation"}


def spell_lines(game, char) -> list[str]:
    """One line per spell: what it is, and whether it can be cast now."""
    t = game.tables
    out = []
    known = sp.known_spells(char, t)
    by_level: dict[int, list[str]] = {}
    for sid in known:
        by_level.setdefault(t.spells[sid]["level"], []).append(sid)
    for level in sorted(by_level):
        label = "Cantrips <dim>(cast as often as you like)</>" if level == 0 else f"Level {level}"
        out.append(f"<title>{label}</>")
        for sid in sorted(by_level[level], key=lambda s: t.spells[s]["name"]):
            spell = t.spells[sid]
            ok, why = sp.can_cast(char, t, sid)
            name = markup.escape(spell["name"])
            bits = []
            if spell.get("damage"):
                bits.append(f"{spell['damage']} {spell.get('damage_type', '')}".strip())
            if spell.get("heal"):
                bits.append(f"heals {spell['heal']}")
            if spell.get("save"):
                bits.append(f"{spell['save'].upper()} save")
            if spell.get("attack"):
                bits.append(f"{spell['attack']} attack")
            tail = f" <dim>({', '.join(bits)})</>" if bits else ""
            head = f"<magic>{name}</>" if ok else f"<dim>{name}</>"
            out.append(f"  {head}{tail}")
            out.append(f"    <dim>{markup.escape(spell.get('text', ''))}</>"
                       + ("" if ok else f" <warn>{markup.escape(why)}</>"))
        out.append("")
    return out


def caster_summary(game, char) -> list[str]:
    t = game.tables
    sheet = game.sheet(char)
    total = sp.slots_total(char, t)
    left = sp.slots_left(char, t)
    lines = [f"<title>{markup.escape(char.name)}</>",
             f"<dim>{t.classes[char.cls]['name']} {char.level}</>", ""]
    if not sp.is_caster(char, t):
        lines.append("<dim>No magic. Some people are lucky like that.</>")
        return lines
    lines.append(f"<dim>Spell attack</> {sp.attack_bonus(sheet, t):+d}   <dim>Save DC</> {sp.save_dc(sheet, t)}")
    if total:
        slots = "  ".join(f"<info>L{i + 1}</> {left[i]}/{total[i]}" for i in range(len(total)) if total[i])
        lines.append(f"<dim>Slots left today:</> {slots}")
        lines.append("<dim>Slots come back with a long rest (camp, r).</>")
    else:
        lines.append("<dim>No spell slots yet: cantrips only.</>")
    if char.cls == "wizard":
        book = [s for s in char.spells.get("spellbook", []) if s in t.spells]
        lines.append(f"<dim>Spellbook:</> {len(book)} spells. Copy more from scrolls (Enter on a scroll in the pack).")
    lines.append("")
    return lines


class SpellsScreen(Screen):
    title = "Spells"

    def __init__(self, app, game, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.view = ScrollText("")
        self._shown = None

    @property
    def char(self):
        self.index = max(0, min(self.index, len(self.game.party) - 1))
        return self.game.party[self.index]

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "S"):
            self.close()
        elif ev.key == "tab":
            self.index = (self.index + 1) % max(1, len(self.game.party))
        elif ev.key in ("up", "down", "pageup", "pagedown", "home", "end"):
            self.view.handle_key(ev)
        return True

    def render(self, canvas: Canvas) -> None:
        game = self.game
        c = self.char
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"Spells: {markup.escape(c.name)}", double=True)
        key = (c.name, game.world.time, tuple(sp.slots_left(c, game.tables)))
        if self._shown != key:
            self.view.set_text("\n".join(caster_summary(game, c) + spell_lines(game, c)))
            self._shown = key
        self.view.render(canvas, 2, 2, w - 4, h - 5)
        bx = canvas.button(2, h - 2, "Close", self.close, hotkey="Esc")
        if len(game.party) > 1:
            bx = canvas.button(bx + 2, h - 2, "Next member", lambda: self.handle_key(KeyEvent("tab")), hotkey="Tab")
        canvas.text(bx + 2, h - 2, "↑↓ PgUp PgDn scroll", colors.FAINT, max_width=max(0, w - bx - 4))

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "tab", "pagedown", "escape")]
