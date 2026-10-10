"""Settings: text size, fullscreen, pictures and animation, dice display, AI on/off, verbosity, autosave, sound."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from realmwalker.config import ANIMATION_CHOICES, AUTOSAVE_CHOICES, COMPANION_CHOICES, GRAPHICS_CHOICES, MAP_ZOOMS, \
    VERBOSITY_LEVELS, VOLUME_STEPS, WORLD_ZOOMS, Settings
from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas


@dataclass
class Option:
    label: str
    value: Callable[[], str]
    change: Callable[[int], None]  # called with -1 or +1
    help: str
    level: Callable[[], int] | None = None  # a volume (0-10): drawn as a bar before the value


class SettingsScreen(Screen):
    title = "Settings"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.selected = 0
        s = app.settings
        self.options = [
            Option("Text size", lambda: str(s.font_size), self._font,
                   "Size of the letters and map tiles. Shortcut anywhere: Ctrl + and Ctrl -. Ctrl 0 resets."),
            Option("Fullscreen", lambda: _onoff(s.fullscreen), lambda d: app.toggle_fullscreen(),
                   "Fill the whole screen. Shortcut anywhere: F11."),
            Option("Show dice rolls", lambda: _onoff(s.show_dice), lambda d: self._toggle("show_dice"),
                   "Show every roll in the message log, e.g. 'Persuasion: 14 + 3 = 17 vs DC 15 — success.'"),
            Option("AI text (Player2)", lambda: _onoff(s.ai_enabled), lambda d: app.set_ai_enabled(not s.ai_enabled),
                   "Use the Player2 AI for names, descriptions and dialogue. When off, built-in text is used."),
            Option("AI extras", lambda: _onoff(s.ai_extras), lambda d: self._toggle("ai_extras"),
                   "Let the AI also write regions, dungeons, magic items, work and obituaries. Off: the AI is "
                   "kept for people, places and conversation, which saves Player2 energy."),
            Option("Text detail", lambda: s.verbosity.capitalize(), self._verbosity,
                   "How much of the world's voice you hear: street life in towns, companions talking on the "
                   "road, the weather turning, sounds in the night. Brief keeps only what matters."),
            Option("Autosave every", lambda: f"{s.autosave_minutes} min", self._autosave,
                   "The game also saves on important events and when you quit. There is no manual reload."),
            Option("AI debug log", lambda: _onoff(s.ai_debug_log), lambda d: app.set_ai_debug_log(not s.ai_debug_log),
                   "Write every AI request and reply to logs/ai_debug.log. Useful when tuning prompts."),
            Option("Eat and drink by yourself", lambda: _onoff(s.auto_supplies), lambda d: self._toggle("auto_supplies"),
                   "Take meals and drinks from the pack when hungry or thirsty. Off: you must eat and drink "
                   "from the inventory yourself (Enter on food or a waterskin)."),
            Option("Graphics", lambda: {"tiles": "Pictures", "letters": "Letters"}[s.graphics],
                   lambda d: self._cycle("graphics", GRAPHICS_CHOICES, d),
                   "Pictures: the maps painted and drawn with tiles, people as figures. Letters: the old look, the "
                   "land drawn in letters and symbols."),
            Option("Animations", lambda: {"full": "Full", "calm": "Calm", "off": "Off"}[s.animations],
                   lambda d: self._cycle("animations", ANIMATION_CHOICES, d),
                   "Full: people walk smoothly, blows land in fights, and water, fire, mist and stars move. Calm: the "
                   "same, but nothing moves on its own. Off: no movement at all."),
            Option("Close-up map scale", lambda: f"{s.map_zoom} px", lambda d: self._cycle("map_zoom", MAP_ZOOMS, d),
                   "How big a square of a town, the wild or a dungeon is drawn. The mouse wheel over the map, or + "
                   "and -, change it while you play."),
            Option("Overworld scale", lambda: f"{s.world_zoom} px", lambda d: self._cycle("world_zoom", WORLD_ZOOMS, d),
                   "How big a square of country is drawn on the overworld. The mouse wheel over the map, or + and -, "
                   "change it while you play."),
            Option("Companions in a fight", lambda: {"command": "You command them", "auto": "They fight by themselves"}[
                       s.battle_companions], lambda d: self._cycle("battle_companions", COMPANION_CHOICES, d),
                   "You command them: you play every turn of the party. They fight by themselves: you play your own "
                   "character's turns and your companions choose their own (as z does for one turn)."),
            Option("Volume", lambda: f"{s.volume * 10}%", lambda d: self._volume("volume", d, "ui_click"),
                   "How loud the whole game is. Ctrl M, anywhere, turns all sound off and on again.",
                   level=lambda: s.volume),
            Option("Music", lambda: f"{s.music_volume * 10}%", lambda d: self._volume("music_volume", d, None),
                   "How loud the music is.", level=lambda: s.music_volume),
            Option("Sound effects", lambda: f"{s.effects_volume * 10}%",
                   lambda d: self._volume("effects_volume", d, "hit_blunt"),
                   "Fights, coins, doors, traps, chests, the harp when you go up a level.",
                   level=lambda: s.effects_volume),
            Option("Interface sounds", lambda: f"{s.interface_volume * 10}%",
                   lambda d: self._volume("interface_volume", d, "ui_click"),
                   "Clicks, pages turning, screens opening and closing, the tick as you move down a list.",
                   level=lambda: s.interface_volume),
            Option("Sound in the background", lambda: _onoff(s.sound_in_background),
                   lambda d: self._toggle_sound("sound_in_background"),
                   "Keep the music and sounds playing while another window is in front of the game."),
            Option("Your music", lambda: "open ►", lambda d: self._music_page(),
                   "Add your own music: which folder plays when (combat, travel, towns, dungeons...), how many tunes "
                   "each has, a button to open the folder, and a way to listen to each."),
        ]

    def _cycle(self, name: str, choices, d: int) -> None:
        s = self.app.settings
        cur = getattr(s, name)
        i = choices.index(cur) if cur in choices else 0
        setattr(s, name, choices[(i + d) % len(choices)])
        self.app.save_settings()

    def _toggle(self, name: str) -> None:
        setattr(self.app.settings, name, not getattr(self.app.settings, name))
        self.app.save_settings()

    def _volume(self, name: str, d: int, sample: str | None) -> None:
        s = self.app.settings
        setattr(s, name, max(0, min(VOLUME_STEPS, getattr(s, name) + d)))
        if name == "volume" and s.muted and s.volume > 0:
            s.muted = False  # turning the volume up is meant to be heard
        self.app.sound_settings_changed()
        if sample:
            self.app.audio.ui(sample)  # hear the new level

    def _toggle_sound(self, name: str) -> None:
        self._toggle(name)
        self.app.sound_settings_changed()

    def _music_page(self) -> None:
        from realmwalker.ui.screens.music import MusicScreen

        self.app.push(MusicScreen(self.app))

    def _font(self, d: int) -> None:
        self.app.change_font_size(d)

    def _verbosity(self, d: int) -> None:
        s = self.app.settings
        s.verbosity = VERBOSITY_LEVELS[(VERBOSITY_LEVELS.index(s.verbosity) + d) % len(VERBOSITY_LEVELS)]
        self.app.save_settings()

    def _autosave(self, d: int) -> None:
        s = self.app.settings
        s.autosave_minutes = AUTOSAVE_CHOICES[(AUTOSAVE_CHOICES.index(s.autosave_minutes) + d) % len(AUTOSAVE_CHOICES)]
        self.app.save_settings()

    def _reset(self) -> None:
        def do_reset() -> None:
            old = self.app.settings
            fresh = Settings()
            if fresh.font_size != old.font_size:
                self.app.window_requests.add("font")
            if fresh.fullscreen != old.fullscreen:
                self.app.window_requests.add("fullscreen")
            for name, value in fresh.to_dict().items():
                setattr(old, name, value)
            self.app.set_ai_enabled(old.ai_enabled)
            self.app.set_ai_debug_log(old.ai_debug_log)
            self.app.sound_settings_changed()
            self.app.notify("Settings reset to defaults", "info")

        self.app.push(ConfirmBox(self.app, "Reset every setting to its default value?", do_reset))

    # ------------------------------------------------------------------
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(84, w - 2)
        height = min(len(self.options) + 12, h - 1)
        x0 = (w - width) // 2
        y0 = max(0, (h - height) // 2)
        canvas.frame(x0, y0, width, height, self.title, double=True)
        x = x0 + 3
        y = y0 + 2
        for i, opt in enumerate(self.options):
            row = y + i
            selected = i == self.selected
            over = canvas.hit(x, row, width - 6, 1, action=lambda i=i: self._click(i), tooltip=opt.help,
                              right_action=lambda i=i: self._click(i, -1))
            if over and canvas.mouse != getattr(self, "_last_mouse", None):
                self.selected = i
            bg = colors.HILITE_BG if selected else None
            if bg:
                canvas.fill(x, row, width - 6, 1, bg)
            canvas.text(x, row, "► " if selected else "  ", colors.TITLE, bg)
            canvas.text(x + 2, row, opt.label, colors.SELECT_FG if selected else colors.FG, bg)
            fg = colors.TITLE if selected else colors.DIM
            if opt.level is not None:
                canvas.text(x + 30, row, "◄ " if selected else "  ", fg, bg)
                canvas.bar(x + 32, row, VOLUME_STEPS, opt.level() / VOLUME_STEPS, fg)
                canvas.text(x + 33 + VOLUME_STEPS, row, f"{opt.value()} ►" if selected else opt.value(), fg, bg)
            else:
                value = f"◄ {opt.value()} ►" if selected else f"  {opt.value()}  "
                canvas.text(x + 30, row, value, fg, bg)
        self._last_mouse = canvas.mouse
        y += len(self.options) + 1
        canvas.hline(x, y, width - 6, "─", colors.FAINT)
        canvas.wrapped(x, y + 1, f"<dim>{self.options[self.selected].help}</>", width - 6, max_lines=3)
        by = y0 + height - 2
        bx = canvas.button(x, by, "Reset to defaults", self._reset, hotkey="R")
        canvas.button(bx + 3, by, "Back", self.close, hotkey="Esc")
        canvas.text(x0 + width - 32, by, "↑↓ choose  ←→ change", colors.FAINT)

    def _click(self, i: int, d: int = 1) -> None:
        self.selected = i
        self._change(d)

    def _change(self, d: int) -> None:
        self.app.audio.ui("ui_toggle")
        self.options[self.selected].change(d)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "up":
            self.selected = (self.selected - 1) % len(self.options)
        elif ev.key == "down":
            self.selected = (self.selected + 1) % len(self.options)
        elif ev.key in ("left", "-"):
            self._change(-1)
        elif ev.key in ("right", "enter", " ", "+"):
            self._change(+1)
        elif ev.key in ("r", "R"):
            self._reset()
        elif ev.key == "escape":
            self.close()
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("up"), KeyEvent("down"), KeyEvent("left"), KeyEvent("right"), KeyEvent("escape")]


def _onoff(value: bool) -> str:
    return "On" if value else "Off"

