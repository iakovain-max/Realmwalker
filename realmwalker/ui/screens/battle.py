"""The battle screen: both sides in their ranks, the turn order, the action menu and the battle log.

The fight itself is rules/combat.Battle. This screen paces the enemy's turns so they can be read,
asks the player what each party member does, and hands over to the aftermath when it is over.
"""

from __future__ import annotations

from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import BACK, FOE, FRONT, PARTY, Battle, Fighter, spell_id
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas

ENEMY_STEP_SECONDS = 0.6
MAX_PER_RANK = 3
ACTIONS = [
    ("a", "Attack", "attack"), ("c", "Cast a spell", "cast"), ("u", "Use an item", "item"),
    ("b", "Class ability", "ability"), ("d", "Dodge", "dodge"), ("h", "Help / first aid", "help"),
    ("s", "Shove or grapple", "shove"), ("r", "Change rank", "rank"), ("p", "Parley", "parley"),
    ("y", "Surrender", "surrender"), ("f", "Flee", "flee"),
]
ACTION_HELP = {
    "attack": "Strike with a weapon. From the back rank you need a reach or ranged weapon.",
    "cast": "Cast a spell you know. Levelled spells use a slot; cantrips are free.",
    "item": "Drink or give a potion, or bandage a bleeding wound.",
    "ability": "Your class's special tricks: Second Wind, Action Surge, Turn Undead...",
    "dodge": "Do nothing but defend: attacks against you have disadvantage until your next turn.",
    "help": "Give an ally advantage on their next attack, or stop a fallen friend bleeding out.",
    "shove": "Knock an enemy down, drive them out of their front rank, or grab and hold them.",
    "rank": "Step forward into the front rank, or back out of reach of blades.",
    "parley": "Talk them down, threaten them, or calm wild animals.",
    "surrender": "Give up. Robbers and soldiers may let you live; beasts and the dead will not.",
    "flee": "Run for it. Everyone standing must get away; anyone down is left behind.",
}
ACTION_ICONS = {"attack": "attack", "cast": "cast", "item": "item", "ability": "ability", "dodge": "defend",
                "help": "health", "shove": "shove", "rank": "rank", "parley": "parley", "surrender": "surrender",
                "flee": "flee"}
HEALTH_WORDS = [(0.99, "unhurt", "good"), (0.75, "scratched", "good"), (0.5, "wounded", "warn"),
                (0.25, "badly hurt", "danger"), (0.0, "near death", "danger")]
LOG_COLORS = {"danger": "danger", "good": "good", "dice": "info", "flavor": "dim", "system": "dim",
              "magic": "magic", "speech": "name", "warn": "warn", "info": "fg"}
OUTCOME_TEXT = {"victory": "<good>Victory.</> The fight is over.", "defeat": "<danger>You have fallen.</>",
                "fled": "<warn>You got away.</>", "parley": "<good>They let you go.</>",
                "surrendered": "<warn>You have surrendered.</>"}


def health_word(f: Fighter) -> tuple[str, str]:
    ratio = f.hp / max(1, f.max_hp)
    for limit, word, color in HEALTH_WORDS:
        if ratio >= limit:
            return word, color
    return "near death", "danger"


def rank_members(battle: Battle, side: str, rank: str) -> list[Fighter]:
    """Who stands (or lies) in a rank: the living first, the dead last; those who fled are gone."""
    members = [f for f in battle.side(side) if f.rank == rank and f.state != "fled"]
    return sorted(members, key=lambda f: (f.state == "dead", f.state == "down"))


class BattleScreen(Screen):
    title = "Battle"
    show_status = False
    animating = True

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.battle: Battle = game.battle
        self.mode = "menu"  # menu, choose, target, over
        self.choice_kind = ""
        self.choices: list[tuple] = []  # (label, value, enabled, why)
        self.choice_index = 0
        self.targets: list[Fighter] = []
        self.target_index = 0
        self.pending: dict = {}
        self.slots_line = ""
        self.last_step = app.clock()
        self.log_scroll = 0
        from realmwalker.ui.gfx.battlefx import BattleStage

        self.stage = BattleStage()
        self.staged = False  # the last frame drew the stage with pictures
        self.hover_fighter = None

    # ------------------------------------------------------------------ flow
    def update(self) -> None:
        b = self.battle
        if b.outcome is not None:
            self.mode = "over"
            return
        if b.pending_party() is not None:
            return
        now = self.app.clock()
        if not self.app.headless and now - self.last_step < ENEMY_STEP_SECONDS:
            return
        if self.staged and self.stage.busy(now) and not self.app.headless:
            return  # let the blow land before the next one
        self.last_step = now
        # Run automatic steps until something worth reading happens or the player must choose.
        seen = len(b.log)
        for _ in range(200):
            if b.outcome is not None or b.pending_party() is not None:
                break
            b.step()
            if len(b.log) > seen:
                break
        if b.outcome is not None:
            self.mode = "over"

    def finish(self) -> None:
        from realmwalker.game.fight import finish_battle
        from realmwalker.ui.screens.aftermath import AftermathScreen

        after = finish_battle(self.game)
        self.app.replace(AftermathScreen(self.app, self.game, after))

    def _acted(self) -> None:
        """After the player's choice: back to the menu, and a pause before the enemy answers."""
        self.mode = "menu" if self.battle.outcome is None else "over"
        self.last_step = self.app.clock()
        self.log_scroll = 0

    # ------------------------------------------------------------------ choosing actions
    def actor(self) -> Fighter | None:
        return self.battle.pending_party()

    def pick_action(self, action: str) -> None:
        f = self.actor()
        if f is None or self.mode == "over":
            return
        b = self.battle
        tables = self.game.tables
        if action == "attack":
            rows = [(self._attack_label(o), o, *self._attack_ok(f, o)) for o in b.attack_options(f)]
            self._open_choices("attack", rows)
        elif action == "cast":
            spells = b.spell_options(f)
            if not spells:
                self.app.notify(f"{f.name} knows no spells.", "warn")
                return
            slots = spellrules.slots_left(f.char, tables)
            self.slots_line = "slots " + " ".join(f"L{i + 1}:{n}" for i, n in enumerate(slots) if n or i == 0) if slots else ""
            rows = []
            for sid, ok, why in spells:
                sp = tables.spells[spell_id(sid)]
                lvl = "cantrip" if sp["level"] == 0 else f"level {sp['level']}"
                if sid.startswith("scroll:"):
                    lvl = "from a scroll"
                elif sid.startswith("charge:"):
                    lvl = "from a magic item"
                if ok and sp["target"] in ("enemy", "ally", "downed_ally", "dead_ally") and not b.spell_targets(f, sid):
                    ok, why = False, "no one to cast it on"
                rows.append((f"{sp['name']} <dim>({lvl}) {sp['text']}</>", sid, ok, why))
            self._open_choices("cast", rows)
        elif action == "item":
            items = b.usable_items(f)
            if not items:
                self.app.notify("Nothing to use: no potions, bandages or healer's kit.", "warn")
                return
            self._open_choices("item", [(tables.items.name(i), i.uid, True, "") for i in items])
        elif action == "ability":
            abilities = b.class_abilities(f)
            if not abilities:
                self.app.notify(f"{f.name} has no special abilities to call on.", "warn")
                return
            self._open_choices("ability", [(name, aid, ok, why) for aid, name, ok, why in abilities])
        elif action == "dodge":
            self._do(b.do_dodge, f)
        elif action == "help":
            allies = [x for x in b.side(PARTY) if x is not f and (x.active or x.state == "down")]
            if not allies:
                self.app.notify("There is nobody beside you to help.", "warn")
                return
            self.pending["value"] = None
            self._open_targets("help", allies)
        elif action == "shove":
            rows = [("Knock them down", "prone", True, ""), ("Drive them back a rank", "push", True, ""),
                    ("Grab and hold them", "grapple", True, "")]
            if "grappled" in f.conditions:
                rows.append(("Break free of a hold", "escape", True, ""))
            self._open_choices("shove", rows)
        elif action == "rank":
            self._do(b.do_change_rank, f)
        elif action == "parley":
            rows = []
            for key, label in (("persuade", "Talk them down (Persuasion)"), ("intimidate", "Threaten them (Intimidation)"),
                               ("calm", "Calm the animals (Animal Handling)")):
                dc = b.parley_dc(key)
                rows.append((label + (f" <dim>DC {dc}</>" if dc else ""), key, dc is not None, "they will not listen"))
            self._open_choices("parley", rows)
        elif action == "surrender":
            ok, why = b.surrender_possible()
            if not ok:
                self.app.notify(f"Surrender? {why[:1].upper() + why[1:]}.", "danger")
                return
            self.app.push(ConfirmBox(self.app, "Throw down your weapons and beg for your life? They will take what "
                                               "they want, and you will have to live with it.",
                                     lambda: self._do(b.do_surrender, f), title="Surrender", danger=True))
        elif action == "flee":
            dc = b.flee_dc()
            left = [x.name for x in b.side(PARTY) if x.state == "down"]
            warn = f" <danger>{', '.join(left)} will be left behind.</>" if left else ""
            self.app.push(ConfirmBox(self.app, f"Run for it? Everyone standing rolls Athletics or Acrobatics against "
                                               f"DC {dc}.{warn}", lambda: self._do(b.do_flee, f), title="Flee",
                                     danger=bool(left)))

    def _do(self, fn, *args) -> None:
        if self.actor() is None:
            return
        fn(*args)
        self._acted()

    def _attack_label(self, o) -> str:
        kind = {"melee": "melee", "ranged": "ranged", "spell_melee": "touch", "spell_ranged": "spell"}[o.kind]
        reach = ", reach" if o.reach else ""
        return f"{o.name} <dim>({kind}{reach}: {o.bonus:+d} to hit, {o.damage} {o.damage_type})</>"

    def _attack_ok(self, f: Fighter, o) -> tuple[bool, str]:
        if not o.available:
            return False, o.reason
        if o.is_melee:
            ok, why = self.battle.can_melee(f, o)
            if not ok:
                return False, why
        if not self.battle.targets_for(f, o.kind, o.reach):
            return False, "no one in reach"
        return True, ""

    def _open_choices(self, kind: str, rows: list[tuple]) -> None:
        self.mode = "choose"
        self.choice_kind = kind
        self.choices = rows
        self.choice_index = next((i for i, r in enumerate(rows) if r[2]), 0)

    def _open_targets(self, kind: str, targets: list[Fighter]) -> None:
        if not targets:
            self.app.notify("There is no one to target.", "warn")
            self.mode = "menu"
            return
        self.mode = "target"
        self.pending["target_kind"] = kind
        self.targets = targets
        self.target_index = 0

    def confirm_choice(self) -> None:
        if not self.choices:
            self.mode = "menu"
            return
        label, value, enabled, why = self.choices[self.choice_index]
        f = self.actor()
        if f is None:
            self.mode = "menu"
            return
        if not enabled:
            self.app.notify(markup.plain(why) or "Not possible.", "warn")
            return
        b = self.battle
        kind = self.choice_kind
        self.pending["value"] = value
        if kind == "attack":
            self._open_targets("attack", b.targets_for(f, value.kind, value.reach))
        elif kind == "cast":
            sp = self.game.tables.spells[spell_id(value)]
            if sp["target"] in ("enemy", "ally", "downed_ally", "dead_ally"):
                self._open_targets("cast", b.spell_targets(f, value))
            else:
                self._do(b.do_cast, f, value, None)
        elif kind == "item":
            self._open_targets("item", [x for x in b.side(PARTY) if x.active or x.state == "down"])
        elif kind == "ability":
            self._do(b.do_ability, f, value)
        elif kind == "shove":
            if value == "escape":
                self._do(b.do_escape, f)
                return
            targets = [t for t in b.enemies_of(f) if b.can_grapple(f, t)[0]]
            if not targets:
                reasons = {b.can_grapple(f, t)[1] for t in b.enemies_of(f)}
                self.app.notify(f"No one you can wrestle ({', '.join(sorted(reasons)) or 'nobody there'}).", "warn")
                self.mode = "menu"
                return
            self._open_targets("shove", targets)
        elif kind == "parley":
            self._do(b.do_parley, f, value)

    def confirm_target(self) -> None:
        f = self.actor()
        if f is None or not self.targets:
            self.mode = "menu"
            return
        target = self.targets[self.target_index]
        kind = self.pending.get("target_kind")
        value = self.pending.get("value")
        b = self.battle
        if kind == "attack":
            self._do(b.do_attack, f, value, target)
        elif kind == "cast":
            self._do(b.do_cast, f, value, target)
        elif kind == "item":
            self._do(b.do_item, f, value, target)
        elif kind == "help":
            self._do(b.do_help, f, target)
        elif kind == "shove":
            if value == "grapple":
                self._do(b.do_grapple, f, target)
            else:
                self._do(b.do_shove, f, target, value)
        else:
            self.mode = "menu"

    def quick_attack(self, target: Fighter) -> None:
        """Clicking an enemy attacks it with the first weapon that can reach."""
        f = self.actor()
        if f is None:
            return
        for o in self.battle.attack_options(f):
            if self._attack_ok(f, o)[0] and target in self.battle.targets_for(f, o.kind, o.reach):
                self._do(self.battle.do_attack, f, o, target)
                return
        self.app.notify(f"{f.name} cannot reach {target.name} from here.", "warn")

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("pageup", "pagedown"):
            self.log_scroll = max(0, self.log_scroll + (5 if ev.key == "pageup" else -5))
            return True
        if self.mode == "over":
            if ev.key in ("enter", " ", "escape"):
                self.finish()
            return True
        if self.actor() is None:
            self.last_step = 0.0  # any key hurries the enemy along
            self.stage.busy_until = 0.0
            return True
        if self.mode == "menu":
            for key, _, action in ACTIONS:
                if ev.key == key:
                    self.pick_action(action)
                    return True
            if ev.key == "?":
                from realmwalker.ui.screens.help import HelpScreen

                self.app.push(HelpScreen(self.app))
                return True
            return False
        if self.mode == "choose":
            if ev.key == "escape":
                self.mode = "menu"
            elif ev.key == "up":
                self.choice_index = (self.choice_index - 1) % len(self.choices)
            elif ev.key == "down":
                self.choice_index = (self.choice_index + 1) % len(self.choices)
            elif ev.key == "enter":
                self.confirm_choice()
            elif ev.is_text and ev.key.isdigit() and 0 < int(ev.key) <= len(self.choices):
                self.choice_index = int(ev.key) - 1
                self.confirm_choice()
            return True
        if self.mode == "target":
            if ev.key == "escape":
                self.mode = "menu"
            elif ev.key in ("left", "up") or (ev.key == "tab" and ev.shift):
                self.target_index = (self.target_index - 1) % len(self.targets)
            elif ev.key in ("right", "down", "tab"):
                self.target_index = (self.target_index + 1) % len(self.targets)
            elif ev.key == "enter":
                self.confirm_target()
            elif ev.is_text and ev.key.isdigit() and 0 < int(ev.key) <= len(self.targets):
                self.target_index = int(ev.key) - 1
                self.confirm_target()
            return True
        return False

    def _click_fighter(self, f: Fighter) -> None:
        if self.mode == "target" and f in self.targets:
            self.target_index = self.targets.index(f)
            self.confirm_target()
        elif self.mode == "menu" and f.side == FOE and f.active:
            self.quick_attack(f)

    def _click_choice(self, i: int) -> None:
        self.choice_index = i
        self.confirm_choice()

    # ------------------------------------------------------------------ drawing
    @property
    def moving(self) -> bool:
        return self.staged and (self.stage.busy(self.app.clock()) or bool(self.stage.fx))

    @property
    def ambient(self) -> bool:
        return self.staged

    def render(self, canvas: Canvas) -> None:
        if canvas.tiles:
            self._render_stage(canvas)
            return
        self.staged = False
        b = self.battle
        w, h = canvas.width, canvas.height
        title = f"Battle: {b.title}" if b.title else "Battle"
        canvas.frame(0, 0, w, h, markup.escape(title), double=True, fg=colors.named("danger"))
        self._render_order(canvas, 2, 1, w - 4)
        half = (w - 2) // 2
        box_w = max(14, min(28, (half - 5) // 2))
        box_h = 5
        bottom_min = 10
        slots = max(1, min(MAX_PER_RANK, (h - 5 - bottom_min) // box_h))
        # A big fight gets a bigger board when the window has room for it (the log and the orders keep 13 rows),
        # so that nobody on either side is hidden behind "+2 more".
        crowd = max(len(rank_members(b, side, rank)) for side in (PARTY, FOE) for rank in (FRONT, BACK))
        slots = max(slots, min(crowd, (h - 5 - 13) // box_h))
        field_h = slots * box_h
        mid = 1 + half
        canvas.text(2, 3, "YOUR SIDE", colors.named("good"))
        canvas.text(mid + 2, 3, "THE ENEMY", colors.named("danger"))
        canvas.text(2, 4, "back", colors.DIM)
        canvas.text(2 + box_w + 1, 4, "front", colors.DIM)
        canvas.text(mid + 2, 4, "front", colors.DIM)
        canvas.text(mid + 2 + box_w + 1, 4, "back", colors.DIM)
        for yy in range(3, 5 + field_h):
            canvas.text(mid, yy, "│", colors.FAINT)
        self._render_rank(canvas, rank_members(b, PARTY, BACK), 2, 5, box_w, box_h, slots)
        self._render_rank(canvas, rank_members(b, PARTY, FRONT), 2 + box_w + 1, 5, box_w, box_h, slots)
        self._render_rank(canvas, rank_members(b, FOE, FRONT), mid + 2, 5, box_w, box_h, slots)
        self._render_rank(canvas, rank_members(b, FOE, BACK), mid + 2 + box_w + 1, 5, box_w, box_h, slots)
        y0 = 5 + field_h
        canvas.hline(1, y0, w - 2, "─", colors.FAINT)
        menu_w = max(30, min(58, w * 2 // 5))
        log_w = w - menu_w - 5
        self._render_log(canvas, 2, y0 + 1, log_w, h - y0 - 2)
        for yy in range(y0 + 1, h - 1):
            canvas.text(2 + log_w + 1, yy, "│", colors.FAINT)
        self._render_menu(canvas, 4 + log_w, y0 + 1, menu_w - 1, h - y0 - 2)

    def _render_stage(self, canvas: Canvas) -> None:
        """The fight as a picture: everyone standing on the ground where it happens, the blows shown as they land."""
        b = self.battle
        w, h = canvas.width, canvas.height
        title = f"Battle: {b.title}" if b.title else "Battle"
        canvas.frame(0, 0, w, h, markup.escape(title), double=True, fg=colors.named("danger"))
        self._render_order_pictures(canvas, 2, 2, w - 4)
        bottom = max(11, min(16, h * 3 // 10))
        stage_rows = h - 4 - bottom
        canvas.clear_cells(1, 3, w - 2, stage_rows)
        rect = tuple(int(v) for v in canvas.cell_rect(1, 3, w - 2, stage_rows))
        now = canvas.now
        self.staged = True
        self.stage.feed(b, now, canvas.gfx.animate)
        current = b.current if (b.order and b.outcome is None) else None
        targets = {t.id for t in self.targets} if self.mode == "target" else set()
        target = self.targets[self.target_index] if self.mode == "target" and self.targets else None
        from realmwalker.ui.gfx.scene import Clip

        canvas.under(Clip(rect))
        self.stage.draw(canvas, self.game, b, rect, now, current=current, targets=targets, target=target,
                        hover=self.hover_fighter)
        canvas.under(Clip(None))
        self.hover_fighter = None
        for fid, (cx, cy, cw, ch) in self.stage.cells.items():
            f = b.fighter(fid)
            if f.state == "fled":
                continue
            if canvas.hit(cx, cy, cw, ch, action=lambda f=f: self._click_fighter(f), tooltip=self._tooltip(f)):
                self.hover_fighter = fid
        if b.outcome is not None:
            from realmwalker.ui.gfx.scene import Text

            words = {"victory": ("Victory", (236, 200, 120)), "defeat": ("Fallen", (220, 70, 56)),
                     "fled": ("Escaped", (220, 180, 110)), "parley": ("They let you go", (180, 220, 160)),
                     "surrendered": ("Surrendered", (200, 170, 140))}.get(b.outcome, (str(b.outcome), (220, 220, 220)))
            canvas.over(Text(rect[0] + rect[2] / 2, rect[1] + rect[3] * 0.22, words[0], "heading", 44, (*words[1], 255),
                             anchor="mm", outline=True, shadow=True))
        y0 = 3 + stage_rows
        canvas.hline(1, y0, w - 2, "─", colors.FAINT)
        menu_w = max(30, min(58, w * 2 // 5))
        log_w = w - menu_w - 5
        self._render_log(canvas, 2, y0 + 1, log_w, h - y0 - 2)
        for yy in range(y0 + 1, h - 1):
            canvas.text(2 + log_w + 1, yy, "│", colors.FAINT)
        self._render_menu(canvas, 4 + log_w, y0 + 1, menu_w - 1, h - y0 - 2)

    def _render_order_pictures(self, canvas: Canvas, x: int, y: int, w: int) -> None:
        """The order of battle as a row of small figures, whoever acts now first and lit."""
        from realmwalker.ui.gfx.battlefx import _figure

        b = self.battle
        cx = canvas.text(x, y, f"Round {b.round}", colors.DIM) + 2
        n = len(b.order)
        if not n:
            return
        start = b.turn if b.outcome is None else 0
        for k in range(n):
            f = b.fighter(b.order[(start + k) % n])
            if not f.active and f.state != "down":
                continue
            label = f.name
            width = len(label) + 4
            if cx + width > x + w:
                canvas.text(cx, y, "…", colors.DIM)
                break
            current = k == 0 and b.outcome is None
            if current:
                canvas.fill(cx, y, width - 1, 1, colors.HILITE_BG)
            names = _figure(f, self.game)
            cw, ch = canvas.cell_w, canvas.cell_h
            for name in names:
                canvas.sprite(name, cx * cw, y * ch - 2, ch + 2, ch + 2, (255, 255, 255, 255 if f.standing else 120))
            color = colors.named("good") if f.side == PARTY else colors.named("danger")
            if not f.standing:
                color = colors.FAINT
            canvas.text(cx + 3, y, label, colors.SELECT_FG if current else color)
            canvas.hit(cx, y, width, 1, tooltip=self._tooltip(f))
            cx += width + 1

    def _render_order(self, canvas: Canvas, x: int, y: int, w: int) -> None:
        b = self.battle
        cx = canvas.text(x, y, f"Round {b.round}: ", colors.DIM)
        for i, fid in enumerate(b.order):
            f = b.fighter(fid)
            if not f.active and f.state != "down":
                continue
            current = i == b.turn and b.outcome is None
            color = colors.named("good") if f.side == PARTY else colors.named("danger")
            if not f.standing:
                color = colors.FAINT
            label = f"►{f.name}" if current else f.name
            if cx + len(label) > x + w - 2:
                canvas.text(cx, y, "…", colors.DIM)
                break
            cx = canvas.text(cx, y, label, colors.SELECT_FG if current else color, colors.HILITE_BG if current else None)
            cx = canvas.text(cx, y, "  ", colors.DIM)

    def _render_rank(self, canvas: Canvas, fighters: list[Fighter], x: int, y: int, bw: int, bh: int, slots: int) -> None:
        shown = fighters[:slots]
        if len(fighters) > slots:
            shown = fighters[: slots - 1] if slots > 1 else fighters[:1]
        for i, f in enumerate(shown):
            self._render_box(canvas, f, x, y + i * bh, bw, bh)
        rest = fighters[len(shown):]
        if rest:
            ry = y + len(shown) * bh
            standing = sum(1 for f in rest if f.active)
            canvas.markup(x + 1, ry + 1, f"<dim>+{len(rest)} more</>", max_width=bw - 2)
            if standing:
                canvas.markup(x + 1, ry + 2, f"<dim>({standing} still fighting)</>", max_width=bw - 2)
            canvas.hit(x, ry, bw, bh, tooltip=", ".join(markup.escape(f.name) for f in rest))

    def _render_box(self, canvas: Canvas, f: Fighter, x: int, y: int, bw: int, bh: int) -> None:
        b = self.battle
        current = bool(b.order) and b.current is f and b.outcome is None
        targeted = self.mode == "target" and bool(self.targets) and self.targets[self.target_index] is f
        choosable = self.mode == "target" and f in self.targets
        border = colors.TITLE if current else (colors.named("warn") if targeted else (colors.BORDER if choosable else colors.FAINT))
        bg = (48, 24, 18) if targeted else colors.PANEL_BG
        canvas.frame(x, y, bw, bh, "", fg=border, bg=bg, double=current or targeted)
        canvas.hit(x, y, bw, bh, action=lambda f=f: self._click_fighter(f), tooltip=self._tooltip(f))
        inner = bw - 4
        if f.char:
            glyph, gcolor = "@", (255, 244, 200)
        else:
            glyph, gcolor = f.cdef["glyph"], tuple(f.cdef["color"])
        if not f.active and f.state != "down":
            gcolor = colors.FAINT
        canvas.text(x + 2, y + 1, glyph, gcolor, bg)
        name_fg = colors.named("good") if f.side == PARTY else colors.named("danger")
        if not f.active:
            name_fg = colors.DIM
        number = ""
        if choosable:
            number = f"{self.targets.index(f) + 1}."
            canvas.text(x + bw - 1 - len(number), y + 1, number, colors.TITLE, bg)
        canvas.text(x + 4, y + 1, f.name, name_fg, bg, max_width=inner - 2 - len(number))
        known = f.side == PARTY or (f.creature is not None and f.creature.def_id in b.known)
        word, color = health_word(f)
        numbers = f" {f.hp}/{f.max_hp}" if known else ""
        bar_w = max(3, inner - len(numbers))
        filled = int(round(bar_w * f.hp / max(1, f.max_hp)))
        canvas.text(x + 2, y + 2, "█" * filled, colors.named(color), bg)
        canvas.text(x + 2 + filled, y + 2, "░" * (bar_w - filled), colors.FAINT, bg)
        if numbers:
            canvas.text(x + 2 + bar_w, y + 2, numbers, colors.named(color), bg)
        canvas.markup(x + 2, y + 3, self._status(f, known, word, color), fg=colors.DIM, bg=bg, max_width=inner)

    def _status(self, f: Fighter, known: bool, word: str, color: str) -> str:
        states = {"down": f"<danger>DOWN</> <dim>{'stable' if f.stable else f'bleeding out: {f.dying}'}</>",
                  "dead": "<dim>dead</>", "fled": "<dim>fled</>", "fleeing": "<warn>fleeing</>",
                  "surrendered": "<good>yields</>"}
        if f.state in states:
            return states[f.state]
        bits = [f"AC {f.ac()}"] if known else [f"<{color}>{word}</>"]
        bits += [c for c in f.conditions if c != "unconscious"]
        if "unconscious" in f.conditions:
            bits.append("<good>asleep</>")
        if f.dodging:
            bits.append("dodging")
        if f.buff_value("attack_die"):
            bits.append("blessed")
        if any(w.bleed and not w.bandaged for w in f.wounds):
            bits.append("<danger>bleeding</>")
        return " · ".join(bits)

    def _tooltip(self, f: Fighter) -> str:
        if f.char:
            wounds = "; ".join(w.label for w in f.char.wounds) or "no wounds"
            return f"<name>{markup.escape(f.char.name)}</> ({f.rank} rank): {wounds}."
        desc = markup.escape(f.cdef["descriptions"][0]) if f.cdef.get("descriptions") else markup.escape(f.cdef["name"])
        wounds = "; ".join(w.label for w in f.creature.wounds)
        known = f.creature.def_id in self.battle.known
        stats = f" <dim>AC {f.ac()}, {f.hp}/{f.max_hp} hp.</>" if known else ""
        return desc + stats + (f" <danger>{wounds[:1].upper() + wounds[1:]}.</>" if wounds else "")

    def _render_log(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        if h <= 0 or w <= 4:
            return
        lines: list = []
        for text, cat in self.battle.log[-80:]:
            lines.extend(markup.wrap(text, w, colors.named(LOG_COLORS.get(cat, "fg"))))
        self.log_scroll = min(self.log_scroll, max(0, len(lines) - h))
        end = len(lines) - self.log_scroll
        start = max(0, end - h)
        for i, line in enumerate(lines[start:end]):
            canvas.spans(x, y + i, line, max_width=w)
        if self.log_scroll:
            canvas.text(x + w - 14, y + h - 1, "(PgDn: newer)", colors.FAINT)

        def wheel(dy: int) -> None:
            self.log_scroll = max(0, self.log_scroll + dy * 2)

        canvas.hit(x, y, w, h, wheel=wheel)

    def _render_menu(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        b = self.battle
        if self.mode == "over":
            canvas.markup(x, y, OUTCOME_TEXT.get(b.outcome, markup.escape(str(b.outcome))), max_width=w)
            canvas.button(x, y + 2, "Continue", self.finish, hotkey="Enter")
            return
        f = self.actor()
        if f is None:
            cur = b.current if b.order else None
            name = markup.escape(cur.name) if cur else "The enemy"
            canvas.markup(x, y, f"<dim>{name} acts…</>", max_width=w)
            canvas.text(x, y + 1, "(any key hurries them)", colors.FAINT, max_width=w)
            return
        canvas.markup(x, y, f"<title>{markup.escape(f.name)}</> <dim>({f.rank} rank)</>: your move", max_width=w)
        if self.mode == "menu":
            col_w = w // 2
            icons = canvas.gfx is not None
            for i, (key, label, action) in enumerate(ACTIONS):
                bx = x + (i % 2) * col_w
                by = y + 2 + i // 2
                if by >= y + h:
                    break
                if icons:
                    canvas.icon(bx, by, f"icon/{ACTION_ICONS.get(action, 'more')}")
                    bx += 2
                canvas.button(bx, by, label[: max(4, col_w - 5 - (2 if icons else 0))], lambda a=action: self.pick_action(a),
                              hotkey=key, tooltip=ACTION_HELP[action])
            hint_y = y + 2 + (len(ACTIONS) + 1) // 2 + 1
            if hint_y < y + h:
                canvas.text(x, hint_y, "Click an enemy to attack it.", colors.FAINT, max_width=w)
        elif self.mode == "choose":
            canvas.text(x, y + 1, "↑↓ or 1-9, Enter; Esc back", colors.DIM, max_width=w)
            if self.choice_kind == "cast" and self.slots_line and len(self.slots_line) < w - 28:
                canvas.text(x + w - len(self.slots_line), y + 1, self.slots_line, colors.named("magic"))
            room = max(1, h - 2)
            first = max(0, min(self.choice_index - room + 1, len(self.choices) - room))
            for row, (label, value, enabled, why) in enumerate(self.choices[first:first + room]):
                i = first + row
                ry = y + 2 + row
                selected = i == self.choice_index
                over = canvas.hit(x, ry, w, 1, action=lambda i=i: self._click_choice(i),
                                  tooltip=markup.escape(why) if not enabled else None)
                bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
                if bg:
                    canvas.fill(x, ry, w, 1, bg)
                if enabled:
                    fg = colors.SELECT_FG if selected else colors.FG
                    canvas.markup(x, ry, f"{i + 1}. {label}", fg=fg, bg=bg, max_width=w)
                else:
                    canvas.text(x, ry, f"{i + 1}. {markup.plain(label)}: {why}", colors.FAINT, bg, max_width=w)
        elif self.mode == "target":
            canvas.text(x, y + 1, "Pick a target: number, arrows or click. Esc back", colors.DIM, max_width=w)
            t = self.targets[self.target_index]
            canvas.markup(x, y + 3, f"<title>► {markup.escape(t.name)}</>", max_width=w)
            canvas.wrapped(x, y + 4, self._tooltip(t), w, max_lines=max(1, h - 5))

    def autoplay_keys(self) -> list[KeyEvent]:
        if self.mode == "over":
            return [KeyEvent("enter")]
        if self.actor() is None:
            return [KeyEvent(" ")]
        if self.mode == "menu":
            return [KeyEvent(k) for k in ("a", "a", "a", "a", "d", "c", "b", "r", "h", "s", "p", "u", "f")]
        return [KeyEvent(k) for k in ("enter", "enter", "1", "down", "right", "escape")]
