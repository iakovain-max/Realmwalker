"""Help: every key binding and a short guide. Grows with each milestone."""

from __future__ import annotations

from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText

HELP_TEXT = """<title>Realmwalker</title>
A grim, open-world party role-playing game built on the rules of Dungeons & Dragons 5th Edition. Travel, trade, fight, scheme, survive, and eventually die. The world goes on without you.

<title>Keys that work everywhere</title>
  <loot>F1</>              This help
  <loot>Esc</>             Back / close
  <loot>Ctrl +</> / <loot>Ctrl -</>   Bigger / smaller text
  <loot>Ctrl 0</>          Default text size
  <loot>F11</>             Fullscreen on/off (also Alt+Enter)
  <loot>F12</>             Save a screenshot (in %APPDATA%\\Realmwalker\\screenshots)
  <loot>Mouse</>           Hover for tooltips, click to choose, wheel to scroll

<title>Menus</title>
  <loot>↑ ↓</>             Choose
  <loot>Enter</>           Select
  <loot>Letter keys</>     The highlighted letter next to each option
  <loot>← →</>             Change a setting

<title>Getting started</title>
Choose <loot>New World</> on the title screen, pick a size and seed, and the land is made in a few seconds. You start as a nameless wanderer in a town or village (character creation arrives in the next milestone). The game saves itself as you go; <loot>Continue</> picks up where you left off.

<title>Walking and looking</title>
  <loot>Arrow keys</>      Walk north, south, east, west
  <loot>Number pad</>      Walk in all eight directions (7 9 1 3 are diagonals)
  <loot>Home PgUp</>       Walk north-west / north-east
  <loot>End PgDn</>        Walk south-west / south-east
  <loot>.</> or <loot>5</>          Wait (an hour on the overworld, a minute on foot)
  <loot>></>               Enter the land around you: see it up close (towns, forests, rivers)
  <loot><</>               Leave the close view and return to the overworld (or walk off its edge)
  <loot>l</>               Look around: move a cursor to examine anything. Enter travels there.
  <loot>Mouse</>           Hover over the map to examine; click next to you to step; click further to travel
  <loot>Right-click</>     Look at a spot

<title>Journeys</title>
  <loot>m</>               World map (<loot>z</> zooms out to the whole world)
  <loot>t</>               Travel: pick a destination on the world map and see how long it takes
Roads are much faster than open country. Forests, hills and marshes are slow; mountains very slow. Rivers without a bridge must be waded. Any key stops a journey.

<title>Other screens</title>
  <loot>L</>               The full message log
  <loot>/</>               Map legend: what every symbol means
  <loot>Esc</>             Game menu: help, settings, save and leave

<title>Player2 AI</title>
The game uses the free Player2 app to write names, descriptions and dialogue. Keep Player2 running for AI text. Without it the game still works, using its own built-in text. The indicator in the bottom-right corner shows which is in use. The AI never decides what happens: dice and rules do.

<title>More to come</title>
Characters, combat, survival, towns and their people, factions, companions, quests and death arrive milestone by milestone. This page lists every key as they are added.
"""


class HelpScreen(Screen):
    title = "Help"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.view = ScrollText(HELP_TEXT)

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(96, w - 2)
        x0 = (w - width) // 2
        canvas.frame(x0, 0, width, h - 1, "Help", double=True)
        self.view.render(canvas, x0 + 2, 2, width - 4, h - 5)
        canvas.button(x0 + 2, h - 3, "Back", self.close, hotkey="Esc")
        canvas.text(x0 + 12, h - 3, "↑↓ PgUp PgDn scroll", (80, 76, 70))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "f1", "?"):
            self.close()
            return True
        return self.view.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("pagedown"), KeyEvent("up"), KeyEvent("escape")]
