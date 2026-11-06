"""Hidden debug console (the ` key). Switched off by config.json (debug_console).

Commands grow with each milestone; type "help" for the list.
"""

from __future__ import annotations

from collections.abc import Callable

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

MAX_HISTORY = 200


class DebugConsole(Screen):
    modal = True
    captures_text = True
    title = "Debug console"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.line = ""
        self.output: list[str] = ["<dim>Debug console. Type</> help <dim>for commands. Esc or ` closes.</>"]
        self.history: list[str] = []
        self.history_pos = 0
        self.commands: dict[str, tuple[Callable[[list[str]], None], str]] = {}
        self._register_builtin()

    def command(self, name: str, help_text: str):
        def deco(fn: Callable[[list[str]], None]):
            self.commands[name] = (fn, help_text)
            return fn

        return deco

    def say(self, text: str) -> None:
        self.output.append(text)
        self.output = self.output[-MAX_HISTORY:]

    def _register_builtin(self) -> None:
        app = self.app

        @self.command("help", "list commands")
        def _help(args):
            for name in sorted(self.commands):
                self.say(f"  <loot>{name}</> <dim>— {self.commands[name][1]}</>")

        @self.command("font", "font <size> — set text size")
        def _font(args):
            if args and args[0].isdigit():
                app.set_font_size(int(args[0]))
            self.say(f"Text size: {app.settings.font_size}")

        @self.command("notify", "notify <text> — show a message")
        def _notify(args):
            app.notify(" ".join(args) or "Hello.", "info")

        @self.command("test-error", "raise an error on purpose, to check the game recovers")
        def _error(args):
            raise RuntimeError("Deliberate test error from the debug console")

        @self.command("clear", "clear this console")
        def _clear(args):
            self.output.clear()

        def need_game():
            if app.game is None:
                self.say("<warn>Start or continue a game first.</>")
            return app.game

        @self.command("fight", "fight <group> — meet an encounter group (fight list: show groups)")
        def _fight(args):
            game = need_game()
            if game is None:
                return
            groups = sorted(app.tables.creatures.encounters)
            if not args or args[0] == "list" or args[0] not in groups:
                self.say("Groups: " + ", ".join(groups))
                return
            from realmwalker.game.encounters import make_encounter

            if game.busy:
                self.say("<warn>Finish what is happening first.</>")
                return
            game.encounter = make_encounter(game, args[0], game.world.rng.child(f"debug/{game.world.time}/{args[0]}"))
            self.close()

        @self.command("land", "land <kind> [size] — change the land near you (rift, blight, dead_forest, scorch, "
                              "drown, crater; land undo: the last change)")
        def _land(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.world import reshape

            w = game.world
            if args and args[0] == "undo":
                led = reshape.ledger(w)
                ok = bool(led) and reshape.undo(w, led[-1]["id"])
                game.land_check()
                self.say("The last change to the land is undone." if ok else "<warn>Nothing to undo.</>")
                return
            if not args or args[0] not in reshape.KINDS:
                self.say("Kinds: " + ", ".join(reshape.KINDS))
                return
            kind = args[0]
            size = float(args[1]) if len(args) > 1 and args[1].replace(".", "", 1).isdigit() else None
            x, y = game.player.x, game.player.y
            off = 1 if kind == "rift" else 4
            shape = {"x": min(w.width - 1, x + off), "y": y}
            if kind == "rift":
                shape.update({"dir": 1.5708, "len": int(size or 24)})
                shape["y"] = max(0, y - int(size or 24) // 2)
            elif kind == "drown":
                shape["n"] = int(size or 24)
            else:
                shape["r"] = size or 2.5
            rec = reshape.make(w, kind, shape, seed=f"debug/{w.time}/{kind}", day=w.time / 1440.0,
                               keep=[(x, y)])
            game.land_check()
            game.dirty = True
            self.say(f"Changed {len(rec['cells'])} cells ({kind})." if rec else "<warn>Nothing there to change.</>")

        @self.command("camp", "camp — refugees pitch a camp outside the town nearest you; camp grow: the nearest "
                              "founded camp grows a stage (a palisade, then a village)")
        def _camp(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.core.rng import RNG
            from realmwalker.world import factions as fx, founding, news
            from realmwalker.world.politics import Politics

            w = game.world
            x, y = game.player.x, game.player.y
            w.politics["party_at"] = [x, y]
            pol = Politics(w, game.tables, RNG(int(w.time), "debug camp"), day=news.now_days(w))

            def far(s):
                return abs(s.x - x) + abs(s.y - y)

            if args and args[0] == "grow":
                recs = [r for r in founding.records(w) if r["stage"] < len(founding.STAGES) - 1]
                if not recs:
                    self.say("<warn>No camp to grow.</>")
                    return
                rec = min(recs, key=lambda r: far(w.settlements[int(r["settlement"])]))
                s = w.settlements[int(rec["settlement"])]
                founding.set_stage(pol, rec, s, int(rec["stage"]) + 1)
                now = ("a camp", "a fortified camp", "a village")[min(2, int(rec["stage"]))]
                self.say(f"{markup.escape(s.name)} is now {now} (its map changes at your next visit).")
                return
            sp = founding.spec(game.tables).get("refugee_camp") or {}
            old = sp.get("chance")
            sp["chance"] = 1.0
            try:
                for s in sorted((s for s in w.settlements if s.kind in ("town", "city")), key=far)[:5]:
                    realm = fx.top_liege(w, w.factions.get(s.owner))
                    enemy = next((f for f in fx.active_factions(w, *fx.REALM_KINDS)
                                  if realm is None or f.id != realm.id), None)
                    camp = founding.refugee_camp(pol, s, enemy)
                    if camp is not None:
                        fx.touch(w)
                        game.land_check()
                        game.player.known_settlements.add(camp.id)
                        game.dirty = True
                        self.say(f"Refugees of {s.name} have pitched {camp.name} at {camp.x},{camp.y}.")
                        return
            finally:
                sp["chance"] = old
            self.say("<warn>No room for a camp outside the towns near you.</>")

        @self.command("host", "host <kind> — a host sets out from the town nearest you for the next one (army, horde, "
                              "the_dead, crusade, warband, refugees)")
        def _host(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.world import hosts

            if not args or args[0] not in hosts.KINDS:
                self.say("Kinds: " + ", ".join(hosts.KINDS))
                return
            w, p = game.world, game.player
            near = sorted(w.settlements, key=lambda s: (abs(s.x - p.x) + abs(s.y - p.y), s.id))
            if len(near) < 2:
                self.say("<warn>Nowhere to march to.</>")
                return
            fid = next((f.id for f in w.factions.values() if f.active), -1) if args[0] != "refugees" else -1
            h = hosts.raise_host(w, game.tables, args[0], (near[0].x, near[0].y), near[1].id, day=w.time / 1440.0,
                                 faction=fid if args[0] not in ("horde", "the_dead") else -1, strength=150,
                                 who="the debug console", people=60)
            game.dirty = True
            self.say(f"{h['id']}: {args[0]} from {near[0].name} to {near[1].name}, {len(h['path'])} squares."
                     if h else "<warn>No road goes there.</>")

        @self.command("quest", "quest <kind> — take on work of that kind (quest list: show kinds)")
        def _quest(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.game import quests
            from realmwalker.game.people import npcs_in

            kinds = sorted(quests.spec(game)["templates"])
            if not args or args[0] == "list" or args[0] not in kinds:
                self.say("Kinds: " + ", ".join(kinds))
                return
            kind = args[0]
            here = game.world.settlement_at(game.player.x, game.player.y)
            folk = [n for n in npcs_in(game.world, here.id) if n.alive] if here is not None else []
            folk = [n for n in folk if n.job in quests.spec(game)["templates"][kind]["givers"]] or folk
            if not folk:
                self.say("<warn>Stand in a town with people in it first (> to enter it).</>")
                return
            rng = game.world.rng.child(f"debug-quest/{game.world.time}/{kind}")
            q = quests.make_offer(game, folk[0], rng, kind)
            if q is None:
                self.say(f"<warn>Nothing in this world fits '{kind}' from here.</>")
                return
            for text in quests.accept(game, q):
                self.say(text)
            self.say(f"<good>{quests.title(game, q)}</> — {quests.pitch(game, q)}")

        @self.command("heal", "heal the party fully (and close wounds)")
        def _heal(args):
            game = need_game()
            if game is None:
                return
            for c in game.party:
                c.hp = c.max_hp
                c.wounds.clear()
            self.say("Healed.")

        @self.command("gold", "gold <n> — give the leader n gold pieces")
        def _gold(args):
            game = need_game()
            if game is not None and args and args[0].lstrip("-").isdigit():
                game.leader.money = max(0, game.leader.money + int(args[0]) * 100)
                self.say(f"Money: {game.leader.money // 100} gp")

        @self.command("book", "book <item> [variant] — give the leader a magic item of the DMG (book list: show them)")
        def _book(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.core.rng import RNG
            from realmwalker.game import treasure

            makers = treasure.spec(game)["makers"]
            if not args or args[0] == "list" or args[0] not in makers:
                self.say("Items: " + ", ".join(sorted(makers)))
                return
            slug = args[0]
            variants = makers[slug]
            variant = " ".join(args[1:]) if len(args) > 1 else ("" if "" in variants else next(iter(variants)))
            if variant not in variants and "*" not in variants:
                self.say("Variants: " + "; ".join(sorted(variants)))
                return
            it = treasure.make_listed(game, slug, variant, "rare", RNG(game.world.time, f"debug-book/{slug}"))
            if it is None:
                self.say(f"<warn>The game cannot make '{slug}' yet.</>")
                return
            it.magic["identified"] = True
            from realmwalker.rules.inventory import add_existing

            add_existing(game.leader, app.tables.items, it)
            self.say(f"<good>{markup.escape(it.magic.get('title') or slug)}</> is in {game.leader.name}'s pack.")

        def town_here(game):
            here = game.world.settlement_at(game.player.x, game.player.y)
            if here is None:
                self.say("<warn>Stand on a town first.</>")
            return here

        @self.command("mark", "mark <mark> | mark clear — put a mark on the town you stand on (mark list: show them)")
        def _mark(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.world import marks

            known = sorted(marks.table(app.tables))
            if not args or args[0] == "list" or args[0] not in known + ["clear"]:
                self.say("Marks: " + ", ".join(known))
                return
            here = town_here(game)
            if here is None:
                return
            day = game.moment.total_days
            if args[0] == "clear":
                here.status.clear()
            else:
                marks.add(game.world, here, args[0], day, app.tables, **({"by": 0} if args[0] == "siege" else {}))
            if game.in_local and game.local is not None and game.local.kind == "settlement":
                from realmwalker.game import fire, placemarks

                placemarks.stamp(game, game.local, here)
                fire.kindle(game, game.local, here)
            self.say(f"{markup.escape(here.name)}: {', '.join(marks.marks_of(here)) or 'no marks'}.")

        @self.command("scene", "scene <id> — play a scene on the town map you stand in (scene list: show them)")
        def _scene(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.game.story import stage

            ids = sorted(app.tables.scenes)
            if not args or args[0] == "list" or args[0] not in ids:
                self.say("Scenes: " + ", ".join(ids))
                return
            if stage.current(game) is not None:
                self.say("<warn>A scene is already playing.</>")
                return
            words = {"town": "this town", "hook": "Something has been killing our people.", "villain": "the beast",
                     "home": "the hills", "hero": game.leader.name.split()[0], "sender": "a hunter",
                     "ally": "the hunter"}
            if stage.start(game, args[0], words=words, force=True) is None:
                self.say("<warn>Scenes play on a town's map (> to go in).</>")
                return
            self.close()

        @self.command("showcase", "showcase — mark the towns about you, one of each sign, to see on the world map; "
                                  "showcase world: the land changed about you, hosts on the roads, a refugee camp, "
                                  "a threat's reach known")
        def _showcase(args):
            game = need_game()
            if game is None:
                return
            if args and args[0] == "world":
                for line in showcase_world(self, game):
                    self.say(line)
                return
            from realmwalker.world import marks

            p = game.player
            day = game.moment.total_days
            near = sorted(game.world.settlements, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))
            here = game.world.settlement_at(p.x, p.y)
            shown = ("burning", "siege", "plague", "tribute", "festival", "memorial", "sacked", "beset", "burned")
            for s, mark in zip([s for s in near if s is not here], shown):
                p.known_settlements.add(s.id)
                marks.add(game.world, s, mark, day, app.tables, **({"by": 0} if mark == "siege" else
                                                                   {"name": "a dragon"} if mark == "tribute" else {}))
                self.say(f"{markup.escape(s.name)}: {mark}")
            self.say("Open the world map (m) to see their signs. 'mark <mark>' marks the town you stand on.")

        @self.command("xp", "xp <n> — give the leader experience")
        def _xp(args):
            game = need_game()
            if game is not None and args and args[0].isdigit():
                from realmwalker.rules.progression import award_xp

                for note in award_xp(game.leader, int(args[0]), app.tables, game.world.rng.child("debug-xp")):
                    self.say(note)
                self.say(f"Level {game.leader.level}, {game.leader.xp} XP")

    def run(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.history.append(text)
        self.history_pos = len(self.history)
        self.say(f"<title>></> {markup.escape(text)}")
        name, *args = text.split()
        entry = self.commands.get(name.lower())
        if entry is None:
            self.say(f"<warn>Unknown command:</> {markup.escape(name)} <dim>(try help)</>")
            return
        entry[0](args)

    # ------------------------------------------------------------------
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        height = max(8, h // 2)
        y0 = h - height
        canvas.frame(0, y0, w, height, self.title, fg=colors.named("magic"), bg=(12, 10, 18))
        rows = height - 4
        lines: list = []
        for text in self.output:
            lines.extend(markup.wrap(text, w - 4))
        for i, line in enumerate(lines[-rows:]):
            canvas.spans(2, y0 + 1 + i, line, max_width=w - 4)
        canvas.text(2, h - 2, "> " + self.line[-(w - 8):] + "_", colors.SELECT_FG)
        canvas.hit(0, 0, w, h)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "`", "~"):
            self.close()
        elif ev.key == "enter":
            line, self.line = self.line, ""
            try:
                self.run(line)
            except Exception as exc:
                self.app.report_error(f"running the debug command '{line}'")
                self.say(f"<danger>Error:</> {markup.escape(str(exc))}")
        elif ev.key == "backspace":
            self.line = self.line[:-1]
        elif ev.key == "up" and self.history:
            self.history_pos = max(0, self.history_pos - 1)
            self.line = self.history[self.history_pos]
        elif ev.key == "down" and self.history:
            self.history_pos = min(len(self.history), self.history_pos + 1)
            self.line = self.history[self.history_pos] if self.history_pos < len(self.history) else ""
        elif ev.is_text:
            self.line += ev.key
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(c) for c in "status"] + [KeyEvent("enter"), KeyEvent("escape")]


# ---------------------------------------------------------------------------- showcase world (Expansion 6 G.10)
LAND_SHOWN = (("rift", (9, -12)), ("blight", (-8, -6)), ("dead_forest", (-9, 5)), ("scorch", (8, 6)),
              ("drown", (2, 11)), ("crater", (-2, -11)))


def showcase_world(console, game) -> list[str]:
    """Everything Part G does to the world, staged about the party for the world map (the console's `showcase
    world`, tools/showcase.py's world sheet): one of each land change at a few days' walk, a host of each kind set out
    on the roads between the nearest towns (a third of the way along), refugees of the nearest town in a camp outside
    it, and the nearest live threat's reach known (its signs heard, its den seen)."""
    from realmwalker.world import hosts, reshape, threats

    w, p = game.world, game.player
    x, y = p.x, p.y
    day = w.time / 1440.0
    said = []
    for kind, (dx, dy) in LAND_SHOWN:
        cx, cy = max(0, min(w.width - 1, x + dx)), max(0, min(w.height - 1, y + dy))
        if kind == "dead_forest":  # (it takes only forest: the nearest wood to its spot, within a week's walk)
            import numpy as np

            woods = np.argwhere(np.isin(w.biome, [i for i, b in enumerate(w.biome_ids) if b in reshape.FORESTS]))
            woods = [(int(a), int(b)) for a, b in woods if max(abs(a - x), abs(b - y)) in range(3, 16)]
            if woods:
                cx, cy = min(woods, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
        shape = {"x": cx, "y": cy}
        if kind == "rift":
            shape.update({"dir": 1.5708, "len": 18, "y": max(0, cy - 9)})
        elif kind == "drown":
            shape["n"] = 20
        else:
            shape["r"] = 2.5
        rec = reshape.make(w, kind, shape, seed=f"showcase/{w.time}/{kind}", day=day, keep=[(x, y)])
        said.append(f"{kind}: {len(rec['cells'])} cells at {cx},{cy}" if rec else f"<warn>{kind}: nothing to change</>")
    game.land_check()
    near = sorted(w.settlements, key=lambda s: (abs(s.x - x) + abs(s.y - y), s.id))
    fid = next((f.id for f in w.factions.values() if f.active), -1)
    for i, kind in enumerate(hosts.KINDS):
        if len(near) < 2:
            break
        a, b = near[i % len(near)], near[(i + 1) % len(near)]
        h = hosts.raise_host(w, game.tables, kind, (a.x, a.y), b.id, day=day,
                             faction=fid if kind not in ("horde", "the_dead", "refugees") else -1,
                             strength=60 + 40 * i, who="the showcase", people=60, most=999)
        if h is None:
            said.append(f"<warn>{kind}: no road from {a.name} to {b.name}</>")
            continue
        h["at"] = float(len(h["path"]) // 3)
        h["x"], h["y"] = h["path"][int(h["at"])]
        for s in (a, b):
            p.known_settlements.add(s.id)
        said.append(f"{kind}: {a.name} to {b.name}")
    console.run("camp")
    said += console.output[-1:]
    t = min(threats.live(w), key=lambda t: threats.distance(w, t, x, y), default=None)
    if t is not None:
        game.renown.heard.update(t.get("signs", []))
        hx, hy = threats.home_xy(w, t)
        p.explored[hx, hy] = True
        said.append(f"the reach of {t['id']} ({t['kind']}) at {t['reach']['x']},{t['reach']['y']} is known")
    for dx in range(-16, 17):  # (the country it was all staged in, seen)
        for dy in range(-16, 17):
            if w.in_bounds(x + dx, y + dy) and dx * dx + dy * dy <= 256:
                p.explored[x + dx, y + dy] = True
    game.dirty = True
    said.append("Open the world map (m) to see it all.")
    return said
