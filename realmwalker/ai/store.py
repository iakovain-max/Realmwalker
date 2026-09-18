"""Generate once, keep forever.

Every piece of flavour text gets a stable key (e.g. "settlement:12:desc"). The store keeps it
with its source ("ai" or "fallback") and whether the player has seen it. Fallback text that the
player has not seen yet may be upgraded to AI text when that arrives; anything seen is final.
The whole store is saved with the game.
"""

from __future__ import annotations

from collections.abc import Callable

from realmwalker.ai.service import AIResult, AIService, AITask, Priority


class FlavorStore:
    def __init__(self) -> None:
        self._entries: dict[str, dict] = {}

    def __contains__(self, key: str) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: str) -> dict | None:
        entry = self._entries.get(key)
        return entry["data"] if entry else None

    def source(self, key: str) -> str | None:
        entry = self._entries.get(key)
        return entry["source"] if entry else None

    def is_seen(self, key: str) -> bool:
        entry = self._entries.get(key)
        return bool(entry and entry["seen"])

    def put(self, key: str, data: dict, source: str) -> None:
        self._entries[key] = {"data": data, "source": source, "seen": False}

    def mark_seen(self, key: str) -> None:
        if key in self._entries:
            self._entries[key]["seen"] = True

    def offer_ai(self, key: str, data: dict) -> bool:
        """Store AI text unless the player has already seen other text for this key."""
        entry = self._entries.get(key)
        if entry is None:
            self.put(key, data, "ai")
            return True
        if entry["source"] == "fallback" and not entry["seen"]:
            entry["data"] = data
            entry["source"] = "ai"
            return True
        return False

    def ensure(
        self,
        key: str,
        fallback: Callable[[], dict],
        ai: AIService | None = None,
        task: AITask | None = None,
        variables: dict | None = None,
        *,
        priority: int = Priority.HIGH,
        context: str = "",
    ) -> dict:
        """Text needed right now: return what we have, else the fallback at once (and ask the AI
        for a better version that replaces it if it arrives before the player looks)."""
        existing = self.get(key)
        if existing is not None:
            return existing
        data = fallback()
        self.put(key, data, "fallback")
        if ai is not None and task is not None and ai.usable():
            self.prefetch(key, ai, task, variables or {}, priority=priority, context=context)
        return data

    def prefetch(self, key: str, ai: AIService, task: AITask, variables: dict, *,
                 priority: int = Priority.BACKGROUND, context: str = "") -> None:
        """Text that will be needed soon: ask the AI now, keep the answer when it comes."""
        if key in self._entries and self._entries[key]["source"] == "ai":
            return

        def done(result: AIResult) -> None:
            if result.ok and result.data is not None:
                self.offer_ai(key, result.data)

        ai.submit(task, variables, priority=priority, callback=done, context=context)

    # ------------------------------------------------------------------ saving
    def to_dict(self) -> dict:
        return {"entries": self._entries}

    @classmethod
    def from_dict(cls, data: dict) -> FlavorStore:
        store = cls()
        for key, entry in (data or {}).get("entries", {}).items():
            if isinstance(entry, dict) and "data" in entry:
                store._entries[key] = {
                    "data": entry["data"],
                    "source": entry.get("source", "fallback"),
                    "seen": bool(entry.get("seen", False)),
                }
        return store
