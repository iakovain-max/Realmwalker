"""Listening to the game between frames, so its logic never has to know about sound: the sounds it asked for
(GameState.cue), a level gained, money changing hands, gear put on or taken off."""

from __future__ import annotations


class GameWatch:
    def __init__(self) -> None:
        self.game = None
        self.levels: dict[int, int] = {}
        self.money: int | None = None
        self.gear: dict[int, tuple] = {}

    def hear(self, game, audio) -> None:
        if game is None:
            self.game = None
            return
        party = [c for c in game.party if c is not None]
        levels = {id(c): int(c.level) for c in party}
        money = sum(int(c.money) for c in party)
        gear = {id(c): tuple(sorted((str(k), str(v)) for k, v in c.equipped.items())) for c in party}
        if game is not self.game:  # a game begun or loaded: what it is like now is where we start from
            self.game = game
            game.cues.clear()
        else:
            for sid in game.cues:
                audio.play(sid)
            game.cues.clear()
            if any(levels[k] > self.levels.get(k, levels[k]) for k in levels):
                audio.play("levelup")
            if money != self.money:
                audio.ui("coins")
            if any(gear[k] != self.gear.get(k, gear[k]) for k in gear):
                audio.ui("equip")
        self.levels, self.money, self.gear = levels, money, gear
