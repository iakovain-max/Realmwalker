"""The main game view's furniture: the side panel (who you are, how you are, when and where), the message log,
the action bar along the bottom (everything the keys do, for the mouse), and what a right click on the map offers.

Everything is laid out in text cells, so it works headless and in the old letters look; with pictures the panel
shows portraits, bars and icons as well.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from realmwalker.ui import colors, markup
from realmwalker.ui.widgets import Canvas

PANEL_W = 40
LOG_H = 7
BAR_H = 3
SLOT_W = 6


# ---------------------------------------------------------------------------- the action bar
@dataclass
class Action:
    id: str
    label: str
    key: str  # the key that does it ("" for none), as shown
    icon: str
    run: Callable[[], None]
    tip: str
    enabled: bool = True
    context: bool = False  # a thing you can do here and now (drawn first, lit)


def actions(gs) -> list[Action]:
    """Everything the main view can do, in the order the bar shows them."""
    game = gs.game
    press = gs.press
    local = game.in_local
    lm = game.local
    underground = lm is not None and lm.kind == "dungeon"
    out: list[Action] = []
    # Things to do right here.
    if not local:
        here = game.world.settlement_at(game.player.x, game.player.y)
        site = game.world.site_at(game.player.x, game.player.y) if hasattr(game.world, "site_at") else None
        what = here.name if here is not None else (site.name if site is not None else "the land here")
        out.append(Action("enter", "Enter", "↵", "enter", gs.enter, f"Go into {markup.escape(what)} on foot (Enter).",
                          context=here is not None or site is not None))
    else:
        if not underground:
            out.append(Action("leave", "Leave", "x", "leave", gs.leave, "Back to the open road and the wider land (x)."))
        if lm is not None and lm.items.get((game.player.lx, game.player.ly)):
            out.append(Action("pickup", "Take", "g", "pickup", lambda: press("g"), "Pick up what lies here (g).",
                              context=True))
        npc = gs.npc_beside()
        if npc is not None:
            out.append(Action("talk", "Talk", "↵", "talk", lambda npc=npc: gs.talk(npc),
                              f"Talk to {markup.escape(npc.name if npc.known else npc.title or 'them')} (Enter).",
                              context=True))
    # Looking and moving.
    out.append(Action("look", "Look", "l", "look", lambda: press("l"), "Look around: move a cursor over the map (l). "
                       "Right-click anything on the map for what you can do with it."))
    if local:
        out.append(Action("search", "Search", "s", "search", lambda: press("s"), "Search here for traps, doors and "
                           "hidden things (s)."))
        out.append(Action("sneak", "Creep" if not game.sneaking else "Walk", "z", "sneak", lambda: press("z"),
                          "Creep: slower, but harder to see and hear (z)."))
    out.append(Action("wait", "Wait", ".", "wait", lambda: press("."), "Wait a while (. or 5)."))
    out.append(Action("map", "Map", "m", "map", lambda: press("m"), "The world map (m). The mouse wheel zooms this map."))
    if not local:
        out.append(Action("travel", "Travel", "t", "travel", lambda: press("t"), "Choose where to travel (t), or click "
                          "a place on the map."))
    out.append(Action("camp", "Camp", "r", "camp", lambda: press("r"), "Make camp: rest, sleep, a fire, food (r)."))
    out.append(Action("water", "Water", "w", "water", lambda: press("w"), "Fill the waterskins here (w)."))
    out.append(Action("wash", "Wash", "b", "wash", lambda: press("b"), "Wash yourself and your clothes (b)."))
    # You and yours.
    out.append(Action("character", "Hero", "c", "character", lambda: press("c"), "Your character sheet (c)."))
    out.append(Action("inventory", "Pack", "i", "inventory", lambda: press("i"), "Your pack and what you wear (i)."))
    out.append(Action("health", "Health", "h", "health", lambda: press("h"), "Wounds, needs and care (h)."))
    if any(c.spells for c in game.party):
        out.append(Action("spells", "Spells", "a", "spells", lambda: press("a"), "Spells and prayers (a)."))
    out.append(Action("party", "Party", "p", "party", lambda: press("p"), "Your companions and orders (p)."))
    # The world.
    out.append(Action("journal", "Journal", "j", "journal", lambda: press("j"), "Work in hand and people you know (j)."))
    out.append(Action("news", "News", "n", "news", lambda: press("n"), "News and the chronicle of the realm (n)."))
    out.append(Action("factions", "Realms", "f", "factions", lambda: press("f"), "Realms, factions and your standing (f)."))
    out.append(Action("log", "Log", "o", "log", lambda: press("o"), "Every message so far (o)."))
    out.append(Action("menu", "Menu", "Esc", "menu", lambda: press("escape"), "Save, settings, help, quit (Esc)."))
    return out


def render_actionbar(gs, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    acts = actions(gs)
    acts.sort(key=lambda a: not a.context)
    slots = max(1, w // SLOT_W)
    shown = acts
    more: list[Action] = []
    if len(acts) > slots:
        shown = acts[: slots - 1]
        more = acts[slots - 1:]
    gs.bar_actions = {a.id: a for a in acts}
    if canvas.gfx is not None:
        from realmwalker.ui.gfx import theme

        canvas.clear_cells(x, y, w, h)
        canvas.under(*theme.panel(*canvas.cell_rect(x, y, w, h), "log", ornaments=False))
    else:
        canvas.fill(x, y, w, h, colors.PANEL_BG)
    for i, a in enumerate(shown):
        _slot(canvas, x + i * SLOT_W, y, h, a)
    if more:
        def open_more(more=more) -> None:
            from realmwalker.ui.screens.popup import ContextMenu

            gs.app.push(ContextMenu(gs.app, (x + (len(shown)) * SLOT_W, y - len(more) - 2),
                                    [(f"{a.label} <dim>({a.key})</>", a.run, a.icon) for a in more], "More"))

        _slot(canvas, x + len(shown) * SLOT_W, y, h, Action("more", "More", "", "more", open_more,
                                                           "Everything that did not fit on the bar."))


def _slot(canvas: Canvas, x: int, y: int, h: int, a: Action) -> None:
    w = SLOT_W
    over = canvas.hit(x, y, w, h, action=a.run if a.enabled else None, tooltip=a.tip)
    if canvas.gfx is not None:
        from realmwalker.ui.gfx import theme
        from realmwalker.ui.gfx.scene import Text

        cw, ch = canvas.cell_w, canvas.cell_h
        px, py, pw, ph = x * cw + 2, y * ch + 3, w * cw - 4, h * ch - 6
        state = "off" if not a.enabled else ("hover" if over else ("active" if a.context else "normal"))
        canvas.under(theme.button(px, py, pw, ph, state))
        label_h = 13
        size = max(12, min(pw - 16, ph - label_h - 8))
        canvas.sprite(f"icon/{a.icon}", px + (pw - size) / 2, py + 4, size, size,
                      (255, 255, 255, 255 if a.enabled else 110), over=False)
        canvas.over(Text(px + pw / 2, py + ph - 4, a.label, "prose_bold", 13,
                         (240, 226, 190, 255) if a.enabled else (120, 116, 110, 255), anchor="ms", shadow=True))
        if a.key and len(a.key) <= 5:
            canvas.over(Text(px + 4, py + 3, a.key, "mono", 10, (226, 190, 116, 220), anchor="lt", shadow=True))
        return
    bg = colors.HOVER_BG if over else None
    key_fg = colors.TITLE if a.enabled else colors.FAINT
    canvas.text(x, y, f"[{a.key}]"[: w - 1] if a.key else "", key_fg, bg)
    canvas.text(x, y + 1, a.label[: w - 1], colors.SELECT_FG if (over or a.context) else colors.FG, bg)


# ---------------------------------------------------------------------------- statuses
STATUS_ICONS = (
    ("exhaustion", "tired"), ("bleeding", "bleed"), ("festering", "festering"), ("sick", "sick"), ("thirst", "thirst"),
    ("parched", "thirst"), ("dry", "thirst"), ("hungry", "hunger"), ("starving", "hunger"), ("famished", "hunger"),
    ("peckish", "hunger"), ("tired", "tired"), ("exhausted", "tired"), ("weary", "tired"), ("sleepy", "tired"),
    ("cold", "cold"), ("chill", "cold"), ("freez", "cold"), ("hypotherm", "cold"), ("shiver", "cold"),
    ("hot", "hot"), ("heat", "hot"), ("overheat", "hot"), ("wet", "wet"), ("soak", "wet"), ("damp", "wet"),
    ("dirt", "dirty"), ("filth", "dirty"), ("grubby", "dirty"), ("pain", "pain"), ("agony", "pain"), ("wound", "pain"),
    ("drunk", "drunk"), ("tipsy", "drunk"), ("merry", "drunk"), ("blood", "bleed"), ("pale", "bleed"), ("faint", "bleed"),
)


def status_icon(word: str) -> str:
    w = markup.plain(word).lower()
    for key, icon in STATUS_ICONS:
        if key in w:
            return icon
    return "danger"


def render_statuses(canvas: Canvas, x: int, y: int, w: int, words: list[str], max_lines: int = 2) -> int:
    """The things that are not fine, as icons and words, flowing over as many lines as allowed."""
    if not words:
        return 0
    line, cx = 0, x
    for word in words:
        n = markup.length(word) + (4 if canvas.gfx is not None else 0)
        if cx > x and cx + n > x + w:
            line += 1
            cx = x
            if line >= max_lines:
                break
        if canvas.gfx is not None:
            canvas.icon(cx, y + line, f"icon/{status_icon(word)}")
            cx += 3
        cx = canvas.markup(cx, y + line, word, max_width=x + w - cx) + (1 if canvas.gfx is not None else 0)
        if canvas.gfx is None:
            cx = canvas.text(cx, y + line, " · " if word is not words[-1] else "", colors.DIM)
    return line + 1


# ---------------------------------------------------------------------------- the panel
def sky_icon(game) -> str:
    m = game.moment
    part = m.part_of_day(game.latitude)
    kind = game.weather.kind
    if kind in ("drizzle", "rain"):
        return "rain"
    if kind == "storm":
        return "storm"
    if kind in ("flurries", "snow", "blizzard"):
        return "snow"
    if kind == "fog":
        return "fog"
    if kind in ("overcast", "cloudy"):
        return "cloud"
    if part in ("night", "before dawn"):
        return "moon"
    if part in ("dawn", "dusk"):
        return "dusk"
    return "sun"


def render_party(gs, canvas: Canvas, x: int, y: int, w: int) -> int:
    from realmwalker.rules.character import Sheet
    from realmwalker.rules.items import money_text
    from realmwalker.ui.screens.health import status_words
    from realmwalker.ui.screens.sheets import ENCUMBRANCE_WORDS

    game = gs.game
    gfx = canvas.gfx is not None
    for index, member in enumerate(game.party):
        s = Sheet(member, game.tables)
        ratio = member.hp / max(1, member.max_hp)
        color = "good" if ratio > 0.6 else ("warn" if ratio > 0.3 else "danger")
        cls = game.tables.classes[member.cls]["name"]
        tx = x
        if gfx:
            from realmwalker.ui.gfx import dolls, theme

            cw, ch = canvas.cell_w, canvas.cell_h
            canvas.under(*theme.panel(x * cw, y * ch + 2, 5 * cw, 3 * ch - 4, "inset", ornaments=False))
            size = min(5 * cw - 6, 3 * ch - 8)
            cmd = dolls.draw(canvas.gfx.atlas, dolls.character(member, game.tables, atlas=canvas.gfx.atlas),
                             x * cw + (5 * cw - size) / 2, y * ch + (3 * ch - size) / 2, size)
            if cmd is not None:
                canvas.over(cmd)
            canvas.clear_cells(x, y, 5, 3)
            tx = x + 6
        tw = w - (tx - x)
        mood = ""
        if member.companion:
            from realmwalker.game.companions import loyalty_word

            word, wcolor = loyalty_word(member.companion.get("loyalty", 50))
            mood = f" <{wcolor}>{word}</>"
        canvas.markup(tx, y, f"<name>{markup.escape(member.name.split()[0])}</> <dim>{cls} {member.level}</>{mood}",
                      max_width=tw)
        numbers = f"{member.hp}/{member.max_hp}"
        bar_w = max(4, tw - len(numbers) - 7)
        if gfx:
            from realmwalker.ui.gfx import theme

            cw, ch = canvas.cell_w, canvas.cell_h
            lag = gs.hp_lag(index, ratio)
            canvas.clear_cells(tx, y + 1, bar_w, 1)
            canvas.under(*theme.bar(tx * cw, (y + 1) * ch + 4, bar_w * cw, ch - 8, ratio,
                                    colors.named(color), lag=lag))
        else:
            filled = int(round(bar_w * ratio))
            canvas.text(tx, y + 1, "█" * filled, colors.named(color))
            canvas.text(tx + filled, y + 1, "░" * (bar_w - filled), colors.FAINT)
        canvas.markup(tx + bar_w + 1, y + 1, f"<{color}>{numbers}</> <dim>AC</> {s.armor_class()}",
                      max_width=tw - bar_w - 1)
        canvas.hit(x, y, w, 2, action=lambda index=index: gs.open_sheet("c", index),
                   tooltip=f"{markup.escape(member.name)}: click for the character sheet (c); right-click for more.",
                   right_action=lambda index=index: gs.member_menu(index))
        enc = s.encumbrance()
        word, ecolor = ENCUMBRANCE_WORDS[enc]
        load = "" if enc == 0 else f" · <{ecolor}>{word}</>"
        if member.companion:
            from realmwalker.game.companions import pay_word

            purse = f"<dim>{pay_word(game, member)}</>"
        else:
            purse = f"<loot>{money_text(member.money)}</>"
        if gfx:
            canvas.icon(tx, y + 2, "icon/coin" if not member.companion else "icon/party")
            canvas.markup(tx + 3, y + 2, f"{purse}{load}", max_width=tw - 3)
        else:
            canvas.markup(tx, y + 2, f"{purse}{load}", max_width=tw)
        y += 3
        if member.animals:
            from realmwalker.game import mounts

            riding = " · ".join(mounts.who_rides_what(game))
            walks = "" if mounts.all_mounted(game) else " <warn>(at a walk)</>"
            y += canvas.wrapped(x, y, f"<dim>Riding:</> {markup.escape(riding)}{walks}", w, max_lines=3)
        words = status_words(member, game.tables)
        if words:
            used = render_statuses(canvas, x, y, w, words, max_lines=2)
            canvas.hit(x, y, w, used, action=lambda index=index: gs.open_sheet("h", index),
                       tooltip="Click (or press h) for the Health screen.")
            y += used
        y += 1 if gfx else 0
    return y


def render_panel(gs, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    from realmwalker.game.describe import cap, danger_text, temperature_word, typical_temperature
    from realmwalker.world.weather import describe as describe_weather

    game = gs.game
    p = game.player
    gfx = canvas.gfx is not None
    canvas.frame(x, y, w, h, markup.escape(game.leader.name), fg=colors.BORDER, bg=colors.PANEL_BG)
    ix, iw = x + 2, w - 4
    row = y + 2
    row = render_party(gs, canvas, ix, row, iw) + 1
    m = game.moment
    part = m.part_of_day(game.latitude)
    tx = ix + 3 if gfx else ix
    if gfx:
        canvas.icon(ix, row, f"icon/{sky_icon(game)}")
    canvas.markup(tx, row, f"<title>{m.time_text()}</> <dim>·</> {part} <dim>· {m.season}</>", max_width=iw - (tx - ix))
    row += 1
    canvas.text(tx, row, m.date_text(), colors.FG, max_width=iw - (tx - ix))
    row += 1
    canvas.text(tx, row, f"{m.year} {m.cal.era}", colors.DIM, max_width=iw - (tx - ix))
    row += 1
    row += canvas.wrapped(tx, row, f"<info>{describe_weather(game.weather)}</>", iw - (tx - ix), max_lines=2)
    temp = typical_temperature(game, p.x, p.y)
    canvas.markup(tx, row, f"<dim>Usually</> {temperature_word(temp)} <dim>this month</>", max_width=iw - (tx - ix))
    row += 2

    canvas.section(ix, row, iw, "Where")
    row += 1
    world = game.world
    underground = game.local is not None and game.local.kind == "dungeon"

    def line(icon: str, text: str, lines: int = 1) -> None:
        nonlocal row
        if gfx:
            if icon:
                canvas.icon(ix, row, f"icon/{icon}")
            row += canvas.wrapped(ix + 3, row, text, iw - 3, max_lines=lines)
        else:
            row += canvas.wrapped(ix, row, text, iw, max_lines=lines)

    area = None
    if underground:
        from realmwalker.game.dungeon import site_here

        meta = game.local.meta
        site = site_here(game)
        if site is not None:
            line("place", f"<place>{markup.escape(cap(site.name))}</>")
        depth = int(meta.get("depth", 1))
        where = f"the {meta.get('name', 'dark')}" + (f", level {meta.get('level', 1)} of {depth}" if depth > 1 else "")
        line("stairs_down", f"Underground: {where}")
        lit = game.lit
        if lit and lit.get("hours", 0) > 0:
            name = game.tables.items.get(lit["def_id"])["name"]
            mins = int(lit["hours"] * 60)
            line("hot", f"<loot>Light:</> {name} <dim>({mins} min left)</>")
        else:
            line("danger", "<warn>No light: you see only what you touch.</>", 2)
    else:
        area = world.area_at(p.x, p.y)
        settlement = world.settlement_at(p.x, p.y)
        if settlement is not None:
            kind = game.tables.sites["settlement_types"][settlement.kind]["name"]
            line("place", f"<place>{settlement.name}</> <dim>({kind})</>")
        if area is not None:
            line("" if settlement is not None else "place", f"<place>{cap(area.name)}</>")
        if world.factions:
            from realmwalker.world.factions import lord_at, top_liege

            lord = lord_at(world, p.x, p.y)
            if lord is not None:
                top = top_liege(world, lord)
                realm = cap(top.name) if top is not None else cap(lord.name)
                line("realm", f"<info>{markup.escape(realm)}</>")
                if game.renown.bounties.get(top.id if top else lord.id):
                    line("danger", "<danger>You are wanted here.</>")
        line("", cap(game.biome_def(p.x, p.y)["name"]) + (" · on the road" if world.road[p.x, p.y] else ""))
        line("danger", f"Wilds: {danger_text(int(world.danger[p.x, p.y]))}")
    if game.in_local and not underground:
        lm = game.local
        b = lm.building_at(p.lx, p.ly) if lm else None
        line("", "<dim>On foot, looking closely" + (f"; inside a {b.kind}" if b else "") + ".</>")
    if game.sneaking:
        line("sneak", f"<info>Creeping</> <dim>(Stealth {game.sneak_roll}; z to stop)</>")
    if game.lost:
        line("danger", "<warn>Lost: you don't know which way you're going.</>", 2)
    if game.travel is not None:
        line("travel", f"<good>Travelling</> <dim>— {len(game.travel.path) * 3} miles to go</>")
    if gfx and game.quests:
        canvas.icon(ix, row + 1, "icon/work")
        row += gs._work_line(canvas, ix + 3, row, iw - 3)
    else:
        row += gs._work_line(canvas, ix, row, iw)
    row += 1

    target = gs.look or gs.hover
    if target is not None and row < h - 3:
        canvas.section(ix, row, iw, "Looking at" if gs.look else "Under the mouse")
        row += 1
        text = gs.describe(*target)
        used = canvas.wrapped(ix, row, text, iw, max_lines=max(1, h - row - 4))
        row += used + 1
        if gs.look is not None and row < h - 2:
            hint = ("arrows move · Enter: travel there · Esc: stop" if not game.in_local else
                    "arrows move · Tab: next place · Enter: walk there · Esc: stop")
            canvas.wrapped(ix, row, f"<faint>{hint}</>", iw, max_lines=2)


def render_log(gs, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    canvas.frame(x, y, w, h, "Messages", fg=colors.FAINT, bg=colors.PANEL_BG, title_fg=colors.DIM,
                 style="log" if canvas.gfx is not None else None)
    inner = w - 4
    lines: list = []
    for msg in gs.game.log.recent(h * 2):
        color = colors.named(msg.color)
        text = msg.text + (f" <dim>(×{msg.count})</>" if msg.count > 1 else "")
        lines.extend(markup.wrap(text, inner, color))
    visible = lines[-(h - 2):]
    for i, line in enumerate(visible):
        canvas.spans(x + 2, y + 1 + i, line, max_width=inner)
    canvas.hit(x, y, w, h, action=gs.open_log, tooltip="Click (or press o) for the full message log.")


# ---------------------------------------------------------------------------- right click on the map
def map_menu(gs, cell: tuple[int, int]) -> list[tuple[str, Callable[[], None] | None, str]]:
    """What a right click on a square of the map offers."""
    from realmwalker.game import wayfinding

    game = gs.game
    here = gs.player_pos()
    entries: list = []
    if game.in_local:
        from realmwalker.game.people import npc_at

        npc = npc_at(game, *cell)
        if npc is not None:
            who = npc.name if npc.known else (npc.title or "this person")
            entries.append((f"Talk to {markup.escape(who)}", lambda: gs.walk_to_talk(cell), "talk"))
        if cell != here:
            entries.append(("Walk here", lambda: wayfinding.begin(game, cell, talk=False), "travel"))
        if game.local is not None and game.local.items.get(cell):
            if cell == here:
                entries.append(("Pick up what lies here", lambda: gs.press("g"), "pickup"))
            else:
                entries.append(("Walk there and look at what lies there", lambda: wayfinding.begin(game, cell), "pickup"))
        if cell == here:
            entries.append(("Search here", lambda: gs.press("s"), "search"))
            entries.append(("Wait a while", lambda: gs.press("."), "wait"))
    else:
        if cell == here:
            entries.append(("Enter the land here", gs.enter, "enter"))
            entries.append(("Make camp", lambda: gs.press("r"), "camp"))
            entries.append(("Wait an hour", lambda: gs.press("."), "wait"))
        else:
            entries.append(("Travel here", lambda: gs.plan_travel_to(cell), "travel"))
    entries.append(("Look at this", lambda: gs.set_look(cell), "look"))
    return entries
