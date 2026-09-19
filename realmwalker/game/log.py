"""The message log: everything that happens, colour-coded by category."""

from __future__ import annotations

from dataclasses import asdict, dataclass

CATEGORY_COLOR = {
    "info": "fg",
    "flavor": "dim",
    "place": "place",
    "danger": "danger",
    "warn": "warn",
    "good": "good",
    "loot": "loot",
    "dice": "info",
    "system": "dim",
    "magic": "magic",
    "speech": "name",
}
MAX_MESSAGES = 600


@dataclass
class Message:
    text: str  # marked-up text
    category: str = "info"
    time: int = 0  # world minutes when it happened
    count: int = 1

    @property
    def color(self) -> str:
        return CATEGORY_COLOR.get(self.category, "fg")


class MessageLog:
    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.unread_from = 0

    def add(self, text: str, category: str = "info", time: int = 0) -> None:
        last = self.messages[-1] if self.messages else None
        if last and last.text == text and last.category == category:
            last.count += 1
            last.time = time
            return
        self.messages.append(Message(text, category, time))
        if len(self.messages) > MAX_MESSAGES:
            drop = len(self.messages) - MAX_MESSAGES
            self.messages = self.messages[drop:]
            self.unread_from = max(0, self.unread_from - drop)

    def recent(self, n: int) -> list[Message]:
        return self.messages[-n:]

    def to_dict(self) -> dict:
        return {"messages": [asdict(m) for m in self.messages[-MAX_MESSAGES:]]}

    @classmethod
    def from_dict(cls, data: dict) -> MessageLog:
        log = cls()
        for m in (data or {}).get("messages", []):
            log.messages.append(Message(m.get("text", ""), m.get("category", "info"), int(m.get("time", 0)), int(m.get("count", 1))))
        log.unread_from = len(log.messages)
        return log
