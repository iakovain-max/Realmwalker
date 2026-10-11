"""The battle screen: the battlefield as a grid of squares, everyone on it, the order of battle, the log, and the
action bar for whoever's turn it is.

The fight itself is rules/combat.Battle. This screen paces the enemy's turns so they can be watched, and lets the
player spend each party member's turn: walk (click a square, or the arrow keys), attack (click an enemy, or a), cast
(c, then a creature or a square), dash, disengage, dodge, hide, help, shove, use an item, a class ability, parley,
surrender, leave the field from its edge, let the game play the turn (z), or end it (e or Space).
"""

from __future__ import annotations

from realmwalker.audio import cues
from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY, Battle, Fighter, spell_id
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent, MouseEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas

ENEMY_STEP_SECONDS = 0.35
ACTIONS = [
    ("a", "Attack", "attack"), ("c", "Spells", "cast"), ("u", "Item", "item"), ("b", "Abilities", "ability"),
    ("r", "Dash", "dash"), ("w", "Disengage", "disengage"), ("d", "Dodge", "dodge"), ("n", "Hide", "hide"),
    ("h", "Help", "help"), ("s", "Shove/Grab", "shove"), ("p", "Parley", "parley"), ("y", "Surrender", "surrender"),
    ("f", "Flee", "flee"), ("z", "Auto", "auto"), ("e", "End turn", "end"),
]
ACTION_HELP = {
    "attack": "Strike with a weapon: anyone within reach, or anyone in range you can see. Click an enemy to walk up "
              "and strike. With Extra Attack you get more than one, and may move between them.",
    "cast": "Cast a spell you know. Levelled spells use a slot; cantrips are free. Areas catch friend and foe alike.",
    "item": "Drink a potion, give one to someone beside you, bind a bleeding wound, or throw a flask of oil, holy water "
            "or alchemist's fire at a square (an action).",
    "ability": "Your class's tricks: Second Wind, Action Surge, Cunning Action, an off-hand strike, Turn Undead...",
    "dash": "Use your action to run: twice your speed this turn.",
    "disengage": "Use your action to back away carefully: no opportunity attacks this turn.",
    "dodge": "Use your action to defend: attacks against you have disadvantage until your next turn.",
    "hide": "Slip out of sight (behind cover, in brush or darkness): your next attack has advantage.",
    "help": "Give a friend advantage against an enemy beside you, or stop a fallen friend beside you bleeding out.",
    "shove": "Knock someone beside you down, push them back five feet, or grab and hold them.",
    "parley": "Talk them down, threaten them, or calm wild animals.",
    "surrender": "Give up. Robbers and soldiers may let you live; beasts and the dead will not.",
    "flee": "Leave the field from its edge (the marked squares). Whoever is left on it, fights on.",
    "auto": "Let the game play this turn for this character, the way it plays the enemy's.",
    "end": "End this character's turn.",
}
ACTION_ICONS = {"attack": "attack", "cast": "cast", "item": "item", "ability": "ability", "dash": "travel",
                "disengage": "leave", "dodge": "defend", "hide": "sneak", "help": "health", "shove": "shove",
                "parley": "parley", "surrender": "surrender", "flee": "flee", "auto": "wait", "end": "rest"}
HEALTH_WORDS = [(0.99, "unhurt", "good"), (0.75, "scratched", "good"), (0.5, "wounded", "warn"),
                (0.25, "badly hurt", "danger"), (0.0, "near death", "danger")]
LOG_COLORS = {"danger": "danger", "good": "good", "dice": "info", "flavor": "dim", "system": "dim",
              "magic": "magic", "speech": "name", "warn": "warn", "info": "fg"}
OUTCOME_TEXT = {"victory": "<good>Victory.</> The fight is over.", "defeat": "<danger>You have fallen.</>",
                "fled": "<warn>You got away.</>", "parley": "<good>They let you go.</>",
                "surrendered": "<warn>You have surrendered.</>"}
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "upleft": (-1, -1), "upright": (1, -1),
        "downleft": (-1, 1), "downright": (1, 1)}
ZOOMS = (16, 24, 32, 40, 48, 64, 80, 96)


def health_word(f: Fighter) -> tuple[str, str]:
    ratio = f.hp / max(1, f.max_hp)
    for limit, word, color in HEALTH_WORDS:
        if ratio >= limit:
            return word, color
    return "near death", "danger"


class BattleScreen(Screen):
    title = "Battle"
    animating = True
    sound_open = None  # blades drawn, and the enemy's cry (on_enter)

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.battle: Battle = game.battle
        self.mode = "idle"  # idle, choose, target, aim, over
        self.choice_kind = ""
        self.choices: list[tuple] = []  # (label, value, enabled, why)
        self.choice_index = 0
        self.targets: list[Fighter] = []
        self.target_index = 0
        self.pending: dict = {}
        self.aim: tuple[int, int] | None = None
        self.hover: tuple[int, int] | None = None
        self.slots_line = ""
        self.last_step = app.clock()
        self.log_scroll = 0
        from realmwalker.ui.gfx.battlefx import BattleBoard

        self.board = BattleBoard()
        self.stage = self.board  # (the old name, for tests and tools)
        self.staged = False
        self.zoom: int | None = None
        self.letters = None  # (x0, y0, cells a square) of the field drawn in letters
        self.auto_once: int | None = None
        self._reach_key = None
        self._reach: dict = {}
        self._tree: dict = {}
        if getattr(app.settings, "battle_companions", "command") == "auto":
            for f in self.battle.side(PARTY)[1:]:
                f.auto = True  # (Settings: companions fight by themselves)
        self.heard = len(self.battle.events)  # the events whose sounds have been played (without the board)

    @property
    def key_sounds(self) -> bool:
        return self.mode != "idle"  # choosing from a list ticks; walking the field does not

    def on_enter(self) -> None:
        self.app.audio.play("battle_start")
        cry = cues.foes_cry([f.kind for f in self.battle.side(FOE)])
        if cry:
            self.app.audio.play(cry, delay=0.35)

    def music(self) -> str | None:
        b = self.battle
        if b.outcome == "victory":
            return "victory"
        if b.outcome == "defeat":
            return "defeat"
        if b.outcome is not None:
            return None  # got away, or let go: the music of the place comes back
        actor = self.game.battle_actor
        lm = self.game.local
        boss = actor is not None and lm is not None and lm.kind == "dungeon" and lm.meta.get("boss") == actor.group
        return cues.combat_mood(b.side(FOE), boss)

    def _play_sounds(self) -> None:
        """The fight's sounds: on the board's timeline when it is drawn, else one after another as they happen."""
        now = self.app.clock()
        if self.staged:
            pending, self.board.sounds = self.board.sounds, []
            self.heard = len(self.battle.events)
        else:
            new = self.battle.events[self.heard:]
            self.heard = len(self.battle.events)
            pending = cues.timeline(new, now)
        for when, sid in pending:
            self.app.audio.play(sid, delay=max(0.0, when - now))

    # ------------------------------------------------------------------ flow
    def update(self) -> None:
        self._play_sounds()
        b = self.battle
        if b.outcome is not None:
            self.mode = "over"
            return
        now = self.app.clock()
        board_busy = self.staged and self.board.busy(now) and not self.app.headless
        f = b.pending_party()
        if f is not None:
            if self.auto_once is not None and self.auto_once != f.id:
                self._clear_auto()
            if not board_busy and self.mode == "idle" and b.turn_spent(f):
                b.end_turn()  # nothing left to do: on to the next
                self.last_step = now
            return
        if not self.app.headless and now - self.last_step < ENEMY_STEP_SECONDS:
            return
        if board_busy:
            return  # let it play out before the next
        self.last_step = now
        cur = b.current if b.order else None
        if self.auto_once is not None and (cur is None or cur.id != self.auto_once):
            self._clear_auto()  # the turn it was asked for is over
        # Run automatic steps until something worth watching happens or the player must choose.
        seen = len(b.events), len(b.log)
        for _ in range(200):
            if b.outcome is not None or b.pending_party() is not None:
                break
            b.step()
            if (len(b.events), len(b.log)) != seen:
                break
        if b.outcome is not None:
            self.mode = "over"
        elif b.pending_party() is not None:
            self.mode = "idle"

    def _clear_auto(self) -> None:
        companions_alone = getattr(self.app.settings, "battle_companions", "command") == "auto"
        for f in self.battle.side(PARTY):
            if f.id == self.auto_once and not (companions_alone and f is not self.battle.side(PARTY)[0]):
                f.auto = False
        self.auto_once = None

    def finish(self) -> None:
        from realmwalker.game.fight import finish_battle
        from realmwalker.ui.screens.aftermath import AftermathScreen

        after = finish_battle(self.game)
        self.app.replace(AftermathScreen(self.app, self.game, after))

    def _acted(self) -> None:
        """After the player's choice: back to the field."""
        self.mode = "idle" if self.battle.outcome is None else "over"
        self.pending = {}
        self.aim = None
        self.log_scroll = 0
        self._reach_key = None

    # ------------------------------------------------------------------ what the one acting can do
    def actor(self) -> Fighter | None:
        return self.battle.pending_party()

    def reach(self, f: Fighter) -> dict:
        """Where `f` can end a move this turn (worked out once until something changes, not every frame)."""
        key = (f.id, f.x, f.y, f.move_left, len(self.battle.events), self.battle.round)
        if key != self._reach_key:
            self._reach_key = key
            self._tree = self.battle.move_tree(f) if f.move_left >= 5 else {}
            occ = self.battle.occupied_by_others(f)
            self._reach = {sq: st for sq, st in self._tree.items()
                           if sq != (f.x, f.y) and grid.can_stop(sq, f.sq, occ)}
        return self._reach

    def available(self, f: Fighter, action: str) -> tuple[bool, str]:
        b = self.battle
        if action == "attack":
            return (b.has_action(f), "no action left this turn")
        if action == "cast":
            return (bool(b.spell_options(f)), f"{f.name} knows no spells")
        if action == "item":
            hands = f.action > 0 or b.fast_hands(f)
            return (hands and bool(b.usable_items(f)), "nothing to use" if hands else "no action left")
        if action == "ability":
            return (any(ok for _, _, ok, _ in b.class_abilities(f)), "nothing to call on now")
        if action in ("dash", "disengage", "dodge", "help", "shove", "parley"):
            return (f.action > 0, "no action left this turn")
        if action == "hide":
            if f.action <= 0 and not ("cunning_action" in (f.char.features if f.char else []) and f.bonus > 0):
                return False, "no action left this turn"
            why = b.hide_problem(f)
            return (why is None, why or "")
        if action == "flee":
            return (b.can_leave(f), "reach the edge of the field first")
        return True, ""

    def pick_action(self, action: str) -> None:
        f = self.actor()
        if f is None or self.mode == "over":
            return
        b = self.battle
        tables = self.game.tables
        if action == "end":
            b.end_turn()
            self._acted()
            return
        if action == "auto":
            f.auto = True
            self.auto_once = f.id
            self._acted()
            return
        ok, why = self.available(f, action)
        if action == "flee" and not ok:
            self.app.notify("Get to the edge of the field (the marked squares) to leave it.", "warn")
            self.pending = {"show_exits": True}
            return
        if not ok and action not in ("cast", "ability"):
            self.app.notify(markup.plain(why)[:1].upper() + markup.plain(why)[1:] + ".", "warn")
            return
        if action == "attack":
            rows = [(self._attack_label(f, o), o, *self._attack_ok(f, o)) for o in b.attack_options(f)]
            if not any(r[2] for r in rows):
                self.app.notify("No one in reach. Click an enemy to walk up and strike, or walk closer.", "warn")
                return
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
                if sp.get("cast") == "bonus":
                    lvl += ", bonus action"
                if ok and sp["target"] in ("enemy", "ally", "downed_ally", "dead_ally") and not b.spell_targets(f, sid):
                    ok, why = False, "no one in reach"
                rows.append((f"{sp['name']} <dim>({lvl}) {sp['text']}</>", sid, ok, why))
            self._open_choices("cast", rows)
        elif action == "item":
            rows = []
            for i in b.usable_items(f):
                throw = b.throw_value(i)
                hint = f" <dim>(throw it: {tables.spells[spell_id(throw)]['text']})</>" if throw else ""
                ok = not throw or f.action > 0 or f.attacks_left > 0
                rows.append((markup.escape(tables.items.name(i)) + hint, i.uid, ok, "no action left this turn"))
            self._open_choices("item", rows)
        elif action == "ability":
            abilities = b.class_abilities(f)
            if not abilities:
                self.app.notify(f"{f.name} has no special abilities to call on.", "warn")
                return
            self._open_choices("ability", [(name, aid, ok, why) for aid, name, ok, why in abilities])
        elif action == "dash":
            self._do(b.do_dash, f)
        elif action == "disengage":
            self._do(b.do_disengage, f)
        elif action == "dodge":
            self._do(b.do_dodge, f)
        elif action == "hide":
            cunning = f.char is not None and "cunning_action" in f.char.features and f.bonus > 0
            self._do(lambda x: b.do_hide(x, bonus=cunning and f.action <= 0), f)
        elif action == "help":
            allies = b.help_targets(f)
            if not allies:
                self.app.notify("Nobody to help: stand beside a fallen friend, or beside an enemy a friend is fighting.", "warn")
                return
            self.pending["value"] = None
            self._open_targets("help", allies)
        elif action == "shove":
            rows = [("Knock them down", "prone", True, ""), ("Push them back five feet", "push", True, ""),
                    ("Grab and hold them", "grapple", True, "")]
            if "grappled" in f.conditions or "restrained" in f.conditions:
                rows.append(("Break free", "escape", True, ""))
            self._open_choices("shove", rows)
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
            left = [x.name for x in b.side(PARTY) if x.state == "down"]
            warn = f" <danger>{', '.join(left)} will be left behind if nobody carries on the fight.</>" if left else ""
            self.app.push(ConfirmBox(self.app, f"Leave the field? {f.name} gets clear of the fight.{warn}",
                                     lambda: self._do(b.do_leave, f), title="Flee", danger=bool(left)))

    def _do(self, fn, *args) -> None:
        if self.actor() is None:
            return
        fn(*args)
        self._acted()

    def _attack_label(self, f: Fighter, o) -> str:
        kind = {"melee": "melee", "ranged": "ranged", "spell_melee": "touch", "spell_ranged": "spell"}[o.kind]
        reach = f", reach {o.reach_sq * 5} ft" if o.is_melee else (f", {o.range[0]}/{o.range[1]} ft" if o.range[0] else "")
        return f"{o.name} <dim>({kind}{reach}: {o.bonus:+d} to hit, {o.damage} {o.damage_type})</>"

    def _attack_ok(self, f: Fighter, o) -> tuple[bool, str]:
        if not o.available:
            return False, o.reason
        if not self.battle.targets_for(f, o):
            return False, "no one in reach"
        return True, ""

    def _open_choices(self, kind: str, rows: list[tuple]) -> None:
        if not rows:
            self.app.notify("Nothing to choose.", "warn")
            return
        self.mode = "choose"
        self.choice_kind = kind
        self.choices = rows
        self.choice_index = next((i for i, r in enumerate(rows) if r[2]), 0)

    def _open_targets(self, kind: str, targets: list[Fighter]) -> None:
        if not targets:
            self.app.notify("There is no one to target.", "warn")
            self.mode = "idle"
            return
        self.mode = "target"
        self.pending["target_kind"] = kind
        self.targets = targets
        f = self.actor()
        self.target_index = min(range(len(targets)), key=lambda i: (targets[i].hp, self.battle.gap(f, targets[i]))) if f else 0

    def _open_aim(self, kind: str) -> None:
        f = self.actor()
        if f is None:
            return
        self.mode = "aim"
        self.pending["aim_kind"] = kind
        sid = self.pending.get("value")
        points = self.battle.spell_points(f, sid) if kind == "cast" else set()
        self.pending["points"] = points
        enemies = [e for e in self.battle.enemies_of(f) if (e.x, e.y) in points]
        if enemies:
            e = min(enemies, key=lambda e: self.battle.gap(f, e))
            self.aim = (e.x, e.y)
        else:
            self.aim = (f.x + 1, f.y) if (f.x + 1, f.y) in points else next(iter(sorted(points)), (f.x, f.y))

    def confirm_choice(self) -> None:
        if not self.choices:
            self.mode = "idle"
            return
        label, value, enabled, why = self.choices[self.choice_index]
        f = self.actor()
        if f is None:
            self.mode = "idle"
            return
        if not enabled:
            self.app.notify(markup.plain(why) or "Not possible.", "warn")
            return
        b = self.battle
        kind = self.choice_kind
        self.pending["value"] = value
        if kind == "attack":
            self._open_targets("attack", b.targets_for(f, value))
        elif kind == "cast":
            sp = self.game.tables.spells[spell_id(value)]
            if sp["target"] in ("enemy", "ally", "downed_ally", "dead_ally"):
                self._open_targets("cast", b.spell_targets(f, value))
            elif sp["target"] in ("point", "direction"):
                self._open_aim("cast")
            else:
                self._do(b.do_cast, f, value, None)
        elif kind == "item":
            it = f.char.item(value) if f.char is not None else None
            throw = b.throw_value(it) if it is not None else None
            if throw:
                self.pending["value"] = throw  # a flask is aimed at a square, like a spell
                self._open_aim("cast")
            else:
                self._open_targets("item", b.item_targets(f))
        elif kind == "ability":
            if value == "offhand":
                opt = b.offhand_option(f)
                self._open_targets("offhand", [t for t in b.enemies_of(f) if opt is not None and b.in_reach(f, opt, t)[0]])
            elif value == "spirit_strike":
                self._open_targets("spirit", b.spirit_targets(f))
            elif value == "war_priest":
                opts = [o for o in b.attack_options(f) if o.available and o.item_uid is not None]
                self._open_targets("war_priest", b.targets_for(f, opts[0]) if opts else [])
            else:
                self._do(b.do_ability, f, value)
        elif kind == "shove":
            if value == "escape":
                self._do(b.do_escape, f)
                return
            targets = [t for t in b.enemies_of(f) if b.can_grapple(f, t)[0]]
            if not targets:
                reasons = {b.can_grapple(f, t)[1] for t in b.enemies_of(f)}
                self.app.notify(f"No one you can lay hands on ({', '.join(sorted(reasons)) or 'nobody there'}).", "warn")
                self.mode = "idle"
                return
            self._open_targets("shove", targets)
        elif kind == "parley":
            self._do(b.do_parley, f, value)

    def confirm_target(self) -> None:
        f = self.actor()
        if f is None or not self.targets:
            self.mode = "idle"
            return
        target = self.targets[self.target_index]
        kind = self.pending.get("target_kind")
        value = self.pending.get("value")
        b = self.battle
        if kind == "attack":
            self._do(b.do_attack, f, value, target)
        elif kind == "cast":
            self._do(lambda x: b.do_cast(x, value, target), f)
        elif kind == "item":
            self._do(b.do_item, f, value, target)
        elif kind == "help":
            self._do(b.do_help, f, target)
        elif kind == "shove":
            if value == "grapple":
                self._do(b.do_grapple, f, target)
            else:
                self._do(b.do_shove, f, target, value)
        elif kind == "offhand":
            self._do(lambda x: b.do_ability(x, "offhand", target), f)
        elif kind == "spirit":
            self._do(lambda x: b.do_ability(x, "spirit_strike", target), f)
        elif kind == "war_priest":
            self._do(lambda x: b.do_ability(x, "war_priest", target), f)
        else:
            self.mode = "idle"

    def confirm_aim(self) -> None:
        f = self.actor()
        if f is None or self.aim is None:
            self.mode = "idle"
            return
        if self.aim not in self.pending.get("points", ()):
            self.app.notify("You cannot aim it there.", "warn")
            return
        value = self.pending.get("value")
        point = self.aim
        sp = self.game.tables.spells[spell_id(value)]
        caught = []
        if sp.get("area") and sp["kind"] in ("save", "sleep", "condition"):
            area = self.battle.spell_area(f, value, point)
            victims = self.battle.in_area(area, sp.get("affects", "all"), f)
            spared = self.battle.sculpted(f, value, victims)
            caught = [x.name for x in victims if x.side == f.side and x.id not in spared]
        if caught:
            names = ", ".join(caught[:-1]) + (" and " if len(caught) > 1 else "") + caught[-1]
            self.app.push(ConfirmBox(self.app, f"{sp['name']} will catch <danger>{markup.escape(names)}</> too. Cast it "
                                               f"there anyway?", lambda: self._do(lambda x: self.battle.do_cast(
                                                   x, value, None, point=point), f), title=sp["name"], danger=True))
            return
        self._do(lambda x: self.battle.do_cast(x, value, None, point=point), f)

    # ------------------------------------------------------------------ moving and quick attacks
    def step_toward(self, dx: int, dy: int) -> None:
        f = self.actor()
        if f is None:
            return
        dest = (f.x + dx, f.y + dy)
        other = self.battle.at(*dest)
        if other is not None and other.side != f.side and other.active:
            self.quick_attack(other)
            return
        if dest in self.reach(f):
            self.battle.do_move(f, dest)
            self._reach_key = None
        elif f.move_left < 5:
            self.app.notify(f"{f.name} has no movement left. (e ends the turn.)", "warn")

    def walk_to(self, sq: tuple[int, int]) -> None:
        f = self.actor()
        if f is None:
            return
        if sq in self.reach(f):
            self.battle.do_move(f, sq)
            self._reach_key = None
        else:
            self.app.notify("Too far to walk this turn." if f.move_left >= 5 else f"{f.name} has no movement left.", "warn")

    def best_attack(self, f: Fighter, target: Fighter):
        """The attack that reaches the target from here, best first: melee if they are beside you."""
        options = [o for o in self.battle.attack_options(f) if o.available]
        reach = [o for o in options if self.battle.in_reach(f, o, target)[0]]
        if not reach:
            return None
        return max(reach, key=lambda o: (o.is_melee, o.bonus + len(o.damage)))

    def quick_attack(self, target: Fighter) -> None:
        """Clicking an enemy attacks it with the best weapon that reaches; out of reach, walk up to it first."""
        f = self.actor()
        b = self.battle
        if f is None:
            return
        if not b.has_action(f):
            self.app.notify(f"{f.name} has no action left. (e ends the turn.)", "warn")
            return
        opt = self.best_attack(f, target)
        if opt is None:
            melee = [o for o in b.attack_options(f) if o.available and o.is_melee]
            spots = []
            for o in melee:
                for sq, st in self.reach(f).items():
                    if grid.gap((sq[0], sq[1], f.sq), target.space) <= o.reach_sq:
                        spots.append((st.cost + st.risk, sq))
            if not spots:
                self.app.notify(f"{f.name} cannot reach {target.name} this turn.", "warn")
                return
            b.do_move(f, min(spots)[1])
            self._reach_key = None
            if not f.active or b.pending_party() is not f:
                self._acted()
                return
            opt = self.best_attack(f, target)
            if opt is None:
                self._acted()
                return
        self._do(b.do_attack, f, opt, target)

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("pageup", "pagedown"):
            self.log_scroll = max(0, self.log_scroll + (5 if ev.key == "pageup" else -5))
            return True
        if ev.key in ("+", "=", "-"):
            self._zoom(1 if ev.key != "-" else -1)
            return True
        if self.mode == "over":
            if ev.key in ("enter", " ", "escape"):
                self.finish()
            return True
        if self.actor() is None:
            self.last_step = 0.0  # any key hurries the enemy along
            self.board.busy_until = 0.0
            return True
        if self.mode == "idle":
            if ev.key in DIRS:
                self.step_toward(*DIRS[ev.key])
                return True
            if ev.key in (" ",):
                self.pick_action("end")
                return True
            for key, _, action in ACTIONS:
                if ev.key == key:
                    self.pick_action(action)
                    return True
            if ev.key == "tab":
                f = self.actor()
                enemies = self.battle.enemies_of(f)
                if enemies:
                    self.pending["value"] = None
                    self.mode = "target"
                    self.pending["target_kind"] = "look"
                    self.targets = sorted(enemies, key=lambda e: self.battle.gap(f, e))
                    self.target_index = 0
                return True
            if ev.key == "?":
                from realmwalker.ui.screens.help import HelpScreen

                self.app.push(HelpScreen(self.app))
                return True
            return False
        if self.mode == "choose":
            if ev.key == "escape":
                self.mode = "idle"
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
                self.mode = "idle"
            elif ev.key in ("left", "up") or (ev.key == "tab" and ev.shift):
                self.target_index = (self.target_index - 1) % len(self.targets)
            elif ev.key in ("right", "down", "tab"):
                self.target_index = (self.target_index + 1) % len(self.targets)
            elif ev.key == "enter":
                if self.pending.get("target_kind") == "look":
                    self.quick_attack(self.targets[self.target_index])
                else:
                    self.confirm_target()
            elif ev.is_text and ev.key.isdigit() and 0 < int(ev.key) <= len(self.targets):
                self.target_index = int(ev.key) - 1
                if self.pending.get("target_kind") != "look":
                    self.confirm_target()
            return True
        if self.mode == "aim":
            if ev.key == "escape":
                self.mode = "idle"
            elif ev.key in DIRS and self.aim is not None:
                dx, dy = DIRS[ev.key]
                nx, ny = self.aim[0] + dx, self.aim[1] + dy
                if self.battle.field.in_bounds(nx, ny):
                    self.aim = (nx, ny)
            elif ev.key == "enter":
                self.confirm_aim()
            return True
        return False

    def handle_mouse(self, ev: MouseEvent) -> bool:
        sq = self.square_at(ev)
        if ev.kind == "move":
            self.hover = sq
            if self.mode == "aim" and sq is not None:
                self.aim = sq
            return False
        if ev.kind == "wheel" and sq is not None:
            self._zoom(1 if ev.dy > 0 else -1)
            return True
        if ev.kind != "click" or sq is None or self.mode == "over":
            return False
        f = self.actor()
        if f is None:
            return False
        who = self.battle.at(*sq)
        if ev.button == "right":
            self.mode = "idle"
            return True
        if self.mode == "aim":
            self.aim = sq
            self.confirm_aim()
            return True
        if self.mode == "target":
            if who is not None and who in self.targets:
                self.target_index = self.targets.index(who)
                if self.pending.get("target_kind") == "look":
                    self.quick_attack(who)
                else:
                    self.confirm_target()
            return True
        if self.mode == "idle":
            if who is not None and who.side != f.side and who.active:
                self.quick_attack(who)
            elif who is None or who is f:
                if who is None:
                    self.walk_to(sq)
            return True
        return False

    def square_at(self, ev: MouseEvent) -> tuple[int, int] | None:
        fld = self.battle.field
        if self.staged and ev.px >= 0:
            return self.board.to_square(ev.px, ev.py, fld)
        if self.staged:
            gfx = self.app.gfx
            if gfx is None:
                return None
            return self.board.to_square((ev.x + 0.5) * gfx.cell_w, (ev.y + 0.5) * gfx.cell_h, fld)
        if self.letters is None:
            return None
        x0, y0, cw = self.letters
        sx, sy = (ev.x - x0) // cw, ev.y - y0
        return (sx, sy) if fld.in_bounds(sx, sy) and ev.x >= x0 else None

    def _zoom(self, step: int) -> None:
        cur = self.zoom or self.board.T
        i = min(range(len(ZOOMS)), key=lambda k: abs(ZOOMS[k] - cur))
        self.zoom = ZOOMS[max(0, min(len(ZOOMS) - 1, i + step))]

    # ------------------------------------------------------------------ what to show on the field
    def overlay(self) -> dict:
        b = self.battle
        f = self.actor()
        ov: dict = {"current": b.current.id if b.order and b.outcome is None else None}
        if f is None:
            return ov
        ov["seen"] = {e.id for e in b.enemies_of(f) if any(b.can_see(p, e) for p in b.side(PARTY) if p.standing)}
        if self.mode == "idle":
            reach = self.reach(f)
            ov["reach"] = set(reach)
            hov = self.hover
            if hov is not None:
                who = b.at(*hov)
                if hov in reach:
                    path = [(f.x, f.y)] + grid.route(self._tree, hov)
                    ov["path"] = path
                    ov["cost"] = reach[hov].cost
                    ov["warn"] = self._provoking(f, path)
                elif who is not None and who.side != f.side:
                    ov["threat"] = self._threat(who)
                    ov["targets"] = {who.id}
                    ov["target"] = who.id
                    ov["flank"] = self._flank_squares(f, who, reach)
                    ov["named"] = {who.id}
                ov["hover"] = hov
            if self.pending.get("show_exits"):
                ov["exits"] = {(x, y) for x in range(b.field.width) for y in range(b.field.height) if b.field.exits[x, y]}
        elif self.mode == "target":
            ov["targets"] = {t.id for t in self.targets}
            ov["target"] = self.targets[self.target_index].id if self.targets else None
        elif self.mode == "aim" and self.aim is not None:
            sid = self.pending.get("value")
            sp = self.game.tables.spells[spell_id(sid)]
            area = b.spell_area(f, sid, self.aim) if sp.get("area") else [self.aim]
            ov["area"] = set(area)
            from realmwalker.ui.gfx.battlefx import colour_for

            ov["area_color"] = colour_for(sp.get("damage_type", ""), spell_id(sid)) if self.aim in self.pending.get("points", ()) \
                else (120, 120, 120)
            ov["aim"] = self.aim
        return ov

    def _provoking(self, f: Fighter, path: list[tuple[int, int]]) -> set:
        """The squares on a path where leaving an enemy's reach gives them a free blow."""
        b = self.battle
        out = set()
        if f.disengaged:
            return out
        threats = b.threats(f)
        for a, c in zip(path, path[1:]):
            for _, sp, r in threats:
                if grid.gap((a[0], a[1], f.sq), sp) <= r < grid.gap((c[0], c[1], f.sq), sp):
                    out.add(c)
        return out

    def _flank_squares(self, f: Fighter, e: Fighter, reach: dict) -> set:
        """Squares `f` could reach this turn (or stands on) from which a friend on the far side would flank `e`."""
        b = self.battle
        friends = [a for a in b.allies_of(f) if a is not f and a.standing and not a.incapacitated and b.gap(a, e) <= 1]
        if not friends:
            return set()
        out = set()
        for sq in list(reach) + [(f.x, f.y)]:
            space = (sq[0], sq[1], f.sq)
            if grid.gap(space, e.space) == 1 and any(grid.flanks(space, a.space, e.space) for a in friends):
                out.add(sq)
        return out

    def _threat(self, e: Fighter) -> set:
        r = self.battle.reach_of(e)
        out = set()
        for x in range(e.x - r, e.x + e.sq + r):
            for y in range(e.y - r, e.y + e.sq + r):
                if self.battle.field.in_bounds(x, y) and (x, y) not in e.cells:
                    out.add((x, y))
        return out

    # ------------------------------------------------------------------ drawing
    @property
    def moving(self) -> bool:
        return self.staged and (self.board.busy(self.app.clock()) or bool(self.board.fx))

    @property
    def ambient(self) -> bool:
        return self.staged

    def render(self, canvas: Canvas) -> None:
        b = self.battle
        w, h = canvas.width, canvas.height
        title = f"Battle: {b.title}" if b.title else "Battle"
        canvas.frame(0, 0, w, h, markup.escape(title), double=True, fg=colors.named("danger"))
        side_w = max(30, min(46, w // 4))
        bar_h = 3
        fx0, fy0 = 1, 3
        fw, fh = w - side_w - 2, h - fy0 - bar_h - 1
        if canvas.tiles:
            self._render_order_pictures(canvas, 2, 1, w - 4)
        else:
            self._render_order(canvas, 2, 1, w - 4)
        if canvas.tiles:
            self._render_field_pictures(canvas, fx0, fy0, fw, fh)
        else:
            self.staged = False
            self._render_field_letters(canvas, fx0, fy0, fw, fh)
        sx = w - side_w - 1
        for yy in range(1, h - 1):
            canvas.text(sx - 1, yy, "│", colors.FAINT)
        self._render_side(canvas, sx, 1, side_w, h - 2)
        self._render_bar(canvas, 2, h - bar_h - 1, fw - 2, bar_h)

    def _render_field_pictures(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        b = self.battle
        canvas.clear_cells(x, y, w, h)
        rect = tuple(int(v) for v in canvas.cell_rect(x, y, w, h))
        now = canvas.now
        self.staged = True
        self.board.feed(b, now, canvas.gfx.animate)
        from realmwalker.ui.gfx.scene import Clip, Text

        canvas.under(Clip(rect))
        self.board.draw(canvas, self.game, b, rect, now, overlay=self.overlay(), zoom=self.zoom)
        canvas.under(Clip(None))
        canvas.over(Clip(None))
        for fid, (cx, cy, cw, ch) in self.board.cells.items():
            f = b.fighter(fid)
            if f.state in ("fled",):
                continue
            canvas.hit(cx, cy, cw, ch, tooltip=self._tooltip(f))
        if b.outcome is not None:
            words = {"victory": ("Victory", (236, 200, 120)), "defeat": ("Fallen", (220, 70, 56)),
                     "fled": ("Escaped", (220, 180, 110)), "parley": ("They let you go", (180, 220, 160)),
                     "surrendered": ("Surrendered", (200, 170, 140))}.get(b.outcome, (str(b.outcome), (220, 220, 220)))
            canvas.over(Text(rect[0] + rect[2] / 2, rect[1] + rect[3] * 0.2, words[0], "heading", 44, (*words[1], 255),
                             anchor="mm", outline=True, shadow=True))

    def _render_field_letters(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        """The field in letters: each square a letter (two cells wide when there is room), people as their letters,
        whose turn it is lit, where they can walk shaded."""
        b = self.battle
        fld = b.field
        T = self.game.tables.terrain
        cw = 2 if fld.width * 2 <= w else 1
        vis_w = min(fld.width, w // cw)
        vis_h = min(fld.height, h)
        f = self.actor()
        cur = b.current if b.order and b.outcome is None else None
        x0 = x + max(0, (w - vis_w * cw) // 2)
        y0 = y + max(0, (h - vis_h) // 2)
        # Follow the one whose turn it is when the field is bigger than the room for it.
        ox = 0 if fld.width <= vis_w else max(0, min(fld.width - vis_w, (cur.x if cur else 0) - vis_w // 2))
        oy = 0 if fld.height <= vis_h else max(0, min(fld.height - vis_h, (cur.y if cur else 0) - vis_h // 2))
        self.letters = (x0 - ox * cw, y0 - oy, cw)
        ov = self.overlay()
        reach = ov.get("reach", set())
        path = set(ov.get("path", []) or [])
        area = ov.get("area", set())
        targets = ov.get("targets", set())
        for sy in range(oy, oy + vis_h):
            for sx in range(ox, ox + vis_w):
                t = int(fld.terrain[sx, sy])
                glyph = chr(int(T.glyphs[t][(sx * 7 + sy * 13) % max(1, int(T.glyph_counts[t]))]))
                fg = tuple(int(v) for v in T.fg[t])
                bg = tuple(int(v) for v in T.bg[t])
                if (sx, sy) in area:
                    bg = (90, 50, 20)
                elif (sx, sy) in path:
                    bg = (70, 66, 30)
                elif (sx, sy) in reach:
                    bg = (22, 34, 60)
                if any((sx, sy) in z.cells for z in b.zones):
                    z = next(z for z in b.zones if (sx, sy) in z.cells)
                    glyph = {"web": "#", "fire": "^", "fog": "░", "ice": "*", "guardians": "·", "guardian": "·"}.get(z.kind, glyph)
                    fg = {"web": (220, 220, 210), "fire": (255, 140, 40), "fog": (180, 180, 190), "ice": (200, 230, 255)}.get(z.kind, (255, 220, 130))
                px = x0 + (sx - ox) * cw
                canvas.text(px, y0 + sy - oy, glyph + (" " if cw == 2 else ""), fg, bg)
        for fi in b.fighters:
            if fi.state in ("fled",):
                continue
            for (cx_, cy_) in fi.cells:
                if not (ox <= cx_ < ox + vis_w and oy <= cy_ < oy + vis_h):
                    continue
                px = x0 + (cx_ - ox) * cw
                if fi.char:
                    glyph = str(b.side(PARTY).index(fi) + 1)
                    fg = colors.named("good")
                else:
                    glyph = fi.cdef["glyph"]
                    fg = tuple(fi.cdef["color"])
                if fi.state == "dead":
                    glyph, fg = "%", (120, 40, 36)
                elif fi.state == "down":
                    glyph, fg = "_", (220, 80, 60)
                bg = None
                if cur is fi:
                    bg = colors.HILITE_BG
                elif fi.id in targets:
                    bg = (90, 30, 24) if fi.id != ov.get("target") else (150, 50, 30)
                canvas.text(px, y0 + cy_ - oy, glyph + (" " if cw == 2 else ""), fg, bg)
                canvas.hit(px, y0 + cy_ - oy, cw, 1, tooltip=self._tooltip(fi))
        if self.mode == "aim" and self.aim is not None:
            ax, ay = self.aim
            if ox <= ax < ox + vis_w and oy <= ay < oy + vis_h:
                canvas.text(x0 + (ax - ox) * cw, y0 + ay - oy, "X", colors.TITLE, (90, 50, 20))
        if b.outcome is not None:
            canvas.markup(x + 2, y, OUTCOME_TEXT.get(b.outcome, markup.escape(str(b.outcome))), max_width=w - 4)

    def _render_order_pictures(self, canvas: Canvas, x: int, y: int, w: int) -> None:
        """The order of battle as a row of small figures, whoever acts now first and lit."""
        from realmwalker.ui.gfx import dolls
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
            cw, ch = canvas.cell_w, canvas.cell_h
            parts = self.board.figures.get(f.id) or _figure(f, self.game, canvas.gfx.atlas)
            self.board.figures[f.id] = parts
            cmd = dolls.draw(canvas.gfx.atlas, parts, cx * cw, y * ch - 2, ch + 2, alpha=1.0 if f.standing else 0.5)
            if cmd is not None:
                canvas.over(cmd)
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
            mark = str(b.side(PARTY).index(f) + 1) if f.char else f.cdef["glyph"]
            label = f"►{mark}:{f.name}" if current else f"{mark}:{f.name}"
            if cx + len(label) > x + w - 2:
                canvas.text(cx, y, "…", colors.DIM)
                break
            cx = canvas.text(cx, y, label, colors.SELECT_FG if current else color, colors.HILITE_BG if current else None)
            cx = canvas.text(cx, y, "  ", colors.DIM)

    def _render_side(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> int:
        """The right-hand column: who acts and what they have left; the list to choose from; the log."""
        b = self.battle
        f = self.actor()
        cy = y
        if self.mode == "over":
            canvas.markup(x, cy, OUTCOME_TEXT.get(b.outcome, markup.escape(str(b.outcome))), max_width=w)
            canvas.button(x, cy + 2, "Continue", self.finish, hotkey="Enter")
            cy += 4
        elif f is None:
            cur = b.current if b.order else None
            name = markup.escape(cur.name) if cur else "The enemy"
            canvas.markup(x, cy, f"<dim>{name} acts…</>", max_width=w)
            canvas.text(x, cy + 1, "(any key hurries them)", colors.FAINT, max_width=w)
            cy += 3
        else:
            cy = self._render_card(canvas, f, x, cy, w)
            if self.mode == "choose":
                cy = self._render_choices(canvas, x, cy + 1, w, max(4, min(len(self.choices) + 2, h // 2)))
            elif self.mode == "target":
                t = self.targets[self.target_index] if self.targets else None
                canvas.text(x, cy + 1, "Choose: click, Tab or arrows, Enter. Esc back", colors.DIM, max_width=w)
                if t is not None:
                    canvas.markup(x, cy + 2, f"<title>► {markup.escape(t.name)}</>", max_width=w)
                    cy = self._render_odds(canvas, f, t, x, cy + 3, w)
                cy += 1
            elif self.mode == "aim":
                sid = self.pending.get("value")
                sp = self.game.tables.spells[spell_id(sid)]
                canvas.markup(x, cy + 1, f"<magic>{markup.escape(sp['name'])}</>: aim with the mouse or arrows, Enter "
                                         f"to cast, Esc back", max_width=w)
                area = b.spell_area(f, sid, self.aim) if sp.get("area") and self.aim is not None else []
                caught = b.in_area(area, sp.get("affects", "all"), f) if area else []
                friends = [x_.name for x_ in caught if x_.side == f.side]
                foes = [x_.name for x_ in caught if x_.side != f.side]
                line = (f"Catches: {', '.join(foes) or 'no enemy'}" + (f"; <danger>and {', '.join(friends)}</>" if friends else ""))
                canvas.wrapped(x, cy + 3, line, w, max_lines=3)
                cy += 6
            else:
                cy = self._render_hover(canvas, f, x, cy + 1, w)
        log_y = cy + 1
        canvas.hline(x, log_y - 1, w, "─", colors.FAINT)
        self._render_log(canvas, x, log_y, w, y + h - log_y)
        return cy

    def _render_card(self, canvas: Canvas, f: Fighter, x: int, y: int, w: int) -> int:
        b = self.battle
        name = markup.escape(f.name)
        canvas.markup(x, y, f"<title>{name}</>: your move", max_width=w)
        word, color = health_word(f)
        bw = max(6, w - 12)
        canvas.bar(x, y + 1, bw, f.hp / max(1, f.max_hp), colors.named(color))
        canvas.text(x + bw + 1, y + 1, f"{f.hp}/{f.max_hp}", colors.named(color))
        pips = []
        pips.append(f"<{'good' if b.has_action(f) else 'dim'}>Action{'×' + str(f.action) if f.action > 1 else ''}</>")
        if f.attacks_left > 0:
            pips[-1] = f"<good>{f.attacks_left} attack{'s' if f.attacks_left > 1 else ''} left</>"
        pips.append(f"<{'good' if f.bonus > 0 else 'dim'}>Bonus</>")
        pips.append(f"<{'good' if f.reaction else 'dim'}>Reaction</>")
        canvas.markup(x, y + 2, " · ".join(pips), max_width=w)
        move = f"Move {f.move_left} ft" + (f" of {f.speed}" if not f.dashed else " (running)")
        canvas.markup(x, y + 3, f"<info>{move}</> <dim>AC {f.ac()}</>", max_width=w)
        bits = []
        if f.concentration:
            sp = self.game.tables.spells.defs.get(f.concentration["spell"], {})
            bits.append(f"<magic>holding {markup.escape(sp.get('name', 'a spell'))}</>")
        bits += [c for c in f.conditions if c not in ("unconscious",)]
        if f.hidden:
            bits.append("<good>hidden</>")
        if f.disengaged:
            bits.append("disengaging")
        if f.dodging:
            bits.append("dodging")
        if f.buff_value("attack_die"):
            bits.append("blessed")
        if bits:
            canvas.markup(x, y + 4, " · ".join(bits), fg=colors.DIM, max_width=w)
            return y + 5
        return y + 4

    def _render_hover(self, canvas: Canvas, f: Fighter, x: int, y: int, w: int) -> int:
        """What is under the mouse: a square (what it is, how far) or someone (how hurt, the odds of hitting them)."""
        b = self.battle
        hov = self.hover
        if hov is None:
            canvas.wrapped(x, y, "<dim>Click a square to walk there, an enemy to attack it. Hover to see the odds.</>",
                           w, max_lines=3)
            return y + 3
        who = b.at(*hov)
        if who is not None and who is not f:
            canvas.markup(x, y, f"<{'good' if who.side == PARTY else 'danger'}>{markup.escape(who.name)}</> "
                                f"<dim>{b.feet(f, who)} ft away</>", max_width=w)
            if who.side != f.side:
                y2 = self._render_odds(canvas, f, who, x, y + 1, w)
                flank = self._flank_squares(f, who, self.reach(f)) if self.mode == "idle" else set()
                if flank and (f.x, f.y) not in flank:
                    canvas.markup(x, y2, "<good>Gold diamonds:</> <dim>stand there to flank it (advantage).</>", max_width=w)
                    return y2 + 1
                return y2
            word, color = health_word(who)
            canvas.markup(x, y + 1, f"<{color}>{word}</> <dim>{who.hp}/{who.max_hp}</>", max_width=w)
            return y + 2
        what = b.field.describe(*hov)
        dist = grid.gap(f.space, (hov[0], hov[1], 1)) * 5
        notes = []
        if b.field.difficult(*hov):
            notes.append("hard going")
        if b.field.low[hov]:
            notes.append("cover")
        if b.field.solid[hov]:
            notes.append("blocks sight")
        if b.field.exits[hov]:
            notes.append("the edge: you can leave from here")
        z = next((z for z in b.zones if hov in z.cells), None)
        if z is not None:
            notes.append({"web": "webbed", "fire": "burning", "fog": "fog", "ice": "ice", "guardians": "spirits",
                          "guardian": "the guardian's reach"}.get(z.kind, z.kind))
        canvas.markup(x, y, f"{markup.escape(what[:1].upper() + what[1:])} <dim>{dist} ft</>", max_width=w)
        if notes:
            canvas.markup(x, y + 1, f"<dim>{', '.join(notes)}</>", max_width=w)
        return y + 2

    def _render_odds(self, canvas: Canvas, f: Fighter, t: Fighter, x: int, y: int, w: int) -> int:
        b = self.battle
        known = t.side == PARTY or (t.creature is not None and t.creature.def_id in b.known)
        word, color = health_word(t)
        canvas.markup(x, y, f"<{color}>{word}</>" + (f" <dim>{t.hp}/{t.max_hp}, AC {t.ac()}</>" if known else ""),
                      max_width=w)
        opt = None
        if self.mode == "target" and self.pending.get("target_kind") == "attack":
            opt = self.pending.get("value")
        if opt is None and t.side != f.side:
            opt = self.best_attack(f, t)
        if opt is None or t.side == f.side:
            if t.side != f.side:
                canvas.text(x, y + 1, "Out of reach from here.", colors.DIM, max_width=w)
                return y + 2
            return y + 1
        chance = b.hit_chance(f, opt, t)
        adv, dis, why = b._adv_dis(f, t, opt)
        _, cover = b.target_ac(f, t, opt)
        notes = list(why) + ([grid.COVER_WORDS[cover]] if cover else [])
        mode = " with advantage" if adv and not dis else (" with disadvantage" if dis and not adv else "")
        canvas.markup(x, y + 1, f"{markup.escape(opt.name)}: <title>{int(round(chance * 100))}%</> to hit{mode}", max_width=w)
        if notes:
            canvas.markup(x, y + 2, f"<dim>{markup.escape(', '.join(notes))}</>", max_width=w)
            return y + 3
        return y + 2

    def _render_choices(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> int:
        canvas.text(x, y, "↑↓ or 1-9, Enter; Esc back", colors.DIM, max_width=w)
        if self.choice_kind == "cast" and self.slots_line and len(self.slots_line) < w:
            canvas.text(x, y + 1, self.slots_line, colors.named("magic"))
            y += 1
        room = max(1, h - 2)
        first = max(0, min(self.choice_index - room + 1, len(self.choices) - room))
        for row, (label, value, enabled, why) in enumerate(self.choices[first:first + room]):
            i = first + row
            ry = y + 1 + row
            selected = i == self.choice_index
            over = canvas.hit(x, ry, w, 1, action=lambda i=i: self._click_choice(i),
                              tooltip=(markup.escape(why) if not enabled else label))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, ry, w, 1, bg)
            if enabled:
                fg = colors.SELECT_FG if selected else colors.FG
                canvas.markup(x, ry, f"{i + 1}. {label}", fg=fg, bg=bg, max_width=w)
            else:
                canvas.text(x, ry, f"{i + 1}. {markup.plain(label)}: {why}", colors.FAINT, bg, max_width=w)
        return y + 1 + min(room, len(self.choices))

    def _click_choice(self, i: int) -> None:
        self.choice_index = i
        self.confirm_choice()

    def _render_bar(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        """The actions as buttons along the bottom, those not possible now greyed."""
        f = self.actor()
        if f is None or self.mode == "over":
            if self.mode != "over":
                canvas.text(x, y + 1, "Mouse wheel or + and - to zoom. PgUp/PgDn scroll the log.", colors.FAINT, max_width=w)
            return
        icons = canvas.gfx is not None
        need = max(len(label) for _, label, _ in ACTIONS) + 5 + (2 if icons else 0)
        rows = max(1, min(h, -(-len(ACTIONS) // max(1, w // need))))
        per = -(-len(ACTIONS) // rows)
        col_w = max(need if per * need <= w else 8, w // per)
        for i, (key, label, action) in enumerate(ACTIONS):
            row, col = divmod(i, per)
            if row >= h:
                break
            bx = x + col * col_w
            by = y + row
            ok, why = self.available(f, action)
            if icons:
                canvas.icon(bx, by, f"icon/{ACTION_ICONS.get(action, 'more')}", rgba=(255, 255, 255, 255 if ok else 110))
                bx += 2
            tip = ACTION_HELP[action] + ("" if ok else f" ({why})")
            canvas.button(bx, by, label, lambda a=action: self.pick_action(a), hotkey=key, tooltip=tip, enabled=ok,
                          max_width=col_w - (3 if icons else 1))

    def _tooltip(self, f: Fighter) -> str:
        b = self.battle
        if f.char:
            wounds = "; ".join(w.label for w in f.char.wounds) or "no wounds"
            return f"<name>{markup.escape(f.char.name)}</> {f.hp}/{f.max_hp}: {wounds}."
        desc = markup.escape(f.cdef["descriptions"][0]) if f.cdef.get("descriptions") else markup.escape(f.cdef["name"])
        wounds = "; ".join(w.label for w in f.creature.wounds)
        known = f.creature.def_id in b.known
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

    def autoplay_keys(self) -> list[KeyEvent]:
        if self.mode == "over":
            return [KeyEvent("enter")]
        if self.actor() is None:
            return [KeyEvent(" ")]
        if self.mode == "idle":
            return [KeyEvent(k) for k in ("z", "z", "z", "z", "a", "right", "up", "left", "down", "r", "d", "c", "b",
                                          "h", "s", "n", "w", "u", "tab", "e", "e", "p")]
        if self.mode == "aim":
            return [KeyEvent(k) for k in ("enter", "enter", "right", "left", "escape")]
        return [KeyEvent(k) for k in ("enter", "enter", "1", "down", "right", "escape")]
