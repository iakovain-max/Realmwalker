"""The Spells screen (S): what a caster knows, what they can still cast today, and what each one does. A spell that
works outside a fight (one that lasts, like Mage Armour, or one that heals) can be cast from here: pick it, pick
who it is for, Enter."""

from __future__ import annotations

from realmwalker.game import magic
from realmwalker.rules import spells as sp
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

SCHOOLS = {"evocation": "Evocation", "abjuration": "Abjuration", "conjuration": "Conjuration",
           "divination": "Divination", "enchantment": "Enchantment", "illusion": "Illusion",
           "necromancy": "Necromancy", "transmutation": "Transmutation"}


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


def working_now(game) -> list[str]:
    """The lasting spells on anyone in the party, and how long each has left."""
    out = []
    for c in game.party:
        for sid, hours in sp.lasting(c, game.tables).items():
            out.append(f"<magic>{markup.escape(game.tables.spells[sid]['name'])}</> on {markup.escape(c.name.split()[0])}"
                       f" <dim>({magic.lasting_text(hours)} left)</>")
    return out


def spell_detail(game, char, sid: str, target) -> list[str]:
    """What the chosen spell is, and whether it can be cast here and now."""
    t = game.tables
    spell = t.spells[sid]
    school = SCHOOLS.get(spell.get("school", ""), "").lower()
    level = "Cantrip" if spell["level"] == 0 else f"Level {spell['level']}"
    bits = []
    if spell.get("damage"):
        bits.append(f"{spell['damage']} {spell.get('damage_type', '')}".strip())
    if spell.get("heal"):
        bits.append(f"heals {spell['heal']}")
    if spell.get("save"):
        bits.append(f"{spell['save'].upper()} save")
    if spell.get("attack"):
        bits.append(f"{spell['attack']} attack")
    lines = [f"<magic>{markup.escape(spell['name'])}</> <dim>{level}{', ' + school if school else ''}"
             + (f" · {', '.join(bits)}" if bits else "") + "</>",
             markup.escape(spell.get("text", ""))]
    ok, why = sp.can_cast(char, t, sid)
    if not ok:
        lines.append(f"<warn>{markup.escape(why[:1].upper() + why[1:])}.</>")
    problem = magic.road_problem(game, char, sid, target)
    if problem is None:
        whom = ""
        if magic.road_targets(game, char, sid):
            whom = " on yourself" if target is char else f" on {markup.escape(target.name.split()[0])}"
        if spell["kind"] == "identify":
            thing = game.tables.items.name(magic.strange_things(game, char)[0], False)
            lines.append(f"<good>Enter casts it over the {markup.escape(thing)} now.</> <dim>It takes ten minutes.</>")
        elif spell["kind"] in ("heal", "cure"):
            lines.append(f"<good>Enter casts it{whom} now.</> <dim>It takes a minute.</>")
        else:
            hours = int(spell.get("rounds", 0)) / sp.ROUNDS_PER_HOUR
            lines.append(f"<good>Enter casts it{whom} now.</> <dim>It takes a minute and lasts "
                         f"{magic.lasting_text(hours)}, into any fight on the way.</>")
    elif problem != why:
        lines.append(f"<dim>{markup.escape(problem[:1].upper() + problem[1:])}.</>")
    return lines


class SpellsScreen(Screen):
    title = "Spells"

    def __init__(self, app, game, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.sel = 0
        self.offset = 0
        self.target = 0
        self.message = ""

    @property
    def char(self):
        self.index = max(0, min(self.index, len(self.game.party) - 1))
        return self.game.party[self.index]

    def spells(self) -> list[str]:
        t = self.game.tables
        known = sp.known_spells(self.char, t)
        return sorted(known, key=lambda s: (t.spells[s]["level"], t.spells[s]["name"]))

    def current(self) -> str | None:
        spells = self.spells()
        if not spells:
            return None
        self.sel = max(0, min(self.sel, len(spells) - 1))
        return spells[self.sel]

    def targets(self) -> list:
        sid = self.current()
        return magic.road_targets(self.game, self.char, sid) if sid else []

    def chosen_target(self):
        targets = self.targets()
        if not targets:
            return self.char
        if self.char in targets and self.target == 0:
            self.target = targets.index(self.char)  # yourself first
        self.target %= len(targets)
        return targets[self.target]

    # ------------------------------------------------------------------ actions
    def cast(self) -> None:
        sid = self.current()
        if sid is None:
            return
        lines = magic.cast_on_road(self.game, self.char, sid, self.chosen_target())
        for text in lines:
            self.game.say(text, "magic")
        self.message = " ".join(lines)

    def next_member(self) -> None:
        self.index = (self.index + 1) % max(1, len(self.game.party))
        self.sel = self.offset = self.target = 0
        self.message = ""

    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.spells())
        if ev.key in ("escape", "S"):
            self.close()
        elif ev.key == "tab":
            self.next_member()
        elif ev.key == "up":
            self.sel = max(0, self.sel - 1)
        elif ev.key == "down":
            self.sel = min(max(0, n - 1), self.sel + 1)
        elif ev.key == "pageup":
            self.sel = max(0, self.sel - 10)
        elif ev.key == "pagedown":
            self.sel = min(max(0, n - 1), self.sel + 10)
        elif ev.key == "home":
            self.sel = 0
        elif ev.key == "end":
            self.sel = max(0, n - 1)
        elif ev.key in ("left", "right"):
            targets = self.targets()
            if targets:
                self.chosen_target()
                self.target = (self.target + (1 if ev.key == "right" else -1)) % len(targets)
        elif ev.key in ("enter", "kpenter"):
            self.cast()
        return True

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        game = self.game
        t = game.tables
        c = self.char
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"Spells: {markup.escape(c.name)}", double=True)
        spells = self.spells()
        sid = self.current()
        lw = min(30, max(22, w // 4))
        rx, rw = lw + 5, w - lw - 7
        bottom = h - 4
        # The list, with a heading for each level.
        rows: list[tuple[str, str | None]] = []
        last = None
        for i, s in enumerate(spells):
            level = t.spells[s]["level"]
            if level != last:
                rows.append(("Cantrips" if level == 0 else f"Level {level}", None))
                last = level
            rows.append((s, str(i)))
        visible = max(1, bottom - 2)
        at = next((r for r, (_, i) in enumerate(rows) if i == str(self.sel)), 0)
        if at < self.offset:
            self.offset = max(0, at - 1)
        elif at >= self.offset + visible:
            self.offset = at - visible + 1
        target = self.chosen_target() if sid else c
        y = 2
        for label, i in rows[self.offset:self.offset + visible]:
            if i is None:
                canvas.text(2, y, label, colors.TITLE, max_width=lw)
            else:
                idx = int(i)
                chosen = idx == self.sel
                if chosen:
                    canvas.fill(2, y, lw, 1, colors.HILITE_BG)
                canvas.hit(2, y, lw, 1, lambda idx=idx: setattr(self, "sel", idx))
                ok, _ = sp.can_cast(c, t, label)
                road = magic.road_problem(game, c, label, target if chosen else None) is None
                canvas.text(2, y, "►" if chosen else " ", colors.TITLE, colors.HILITE_BG if chosen else None)
                canvas.text(3, y, "●" if road else " ", colors.named("good"), colors.HILITE_BG if chosen else None)
                canvas.text(5, y, t.spells[label]["name"], colors.SELECT_FG if chosen else
                            (colors.named("magic") if ok else colors.DIM),
                            colors.HILITE_BG if chosen else None, max_width=lw - 3)
            y += 1
        if len(rows) > visible:
            canvas.text(2, bottom, f"{self.offset + 1}-{min(len(rows), self.offset + visible)} of {len(rows)}",
                        colors.FAINT, max_width=lw)
        if spells:
            canvas.markup(2, bottom - 1 if len(rows) > visible else min(bottom, y + 1),
                          "<good>●</> <dim>castable here</>", max_width=lw)
        # The caster, what is working now, and the chosen spell.
        lines = caster_summary(game, c)
        now = working_now(game)
        if now:
            lines += ["<title>Working now</>"] + now + [""]
        if sid:
            lines += spell_detail(game, c, sid, target)
        y = 2
        for line in lines:
            if y >= bottom - 2:
                break
            y += canvas.wrapped(rx, y, line, rw, max_lines=max(1, bottom - 2 - y)) if line else 1
        if self.message:
            canvas.wrapped(rx, bottom - 1, self.message, rw, max_lines=2)
        # Buttons along the bottom.
        bx = canvas.button(2, h - 2, "Close", self.close, hotkey="Esc")
        if sid:
            bx = canvas.button(bx + 2, h - 2, "Cast", self.cast, hotkey="Enter",
                               enabled=magic.road_problem(game, c, sid, target) is None)
        if len(game.party) > 1:
            bx = canvas.button(bx + 2, h - 2, "Next member", self.next_member, hotkey="Tab")
        hint = "↑↓ choose" + (" · ←→ on whom" if self.targets() else "")
        canvas.text(bx + 2, h - 2, hint, colors.FAINT, max_width=max(0, w - bx - 4))

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "enter", "right", "down", "tab", "pagedown", "escape")]
