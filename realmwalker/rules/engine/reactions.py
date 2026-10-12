"""Reactions and the decisions that pause a fight (docs/EXPANSIONS.md §4.3.5).

Where the rules give someone a choice in the middle of something else - Shield as a blow lands, an opportunity attack
on a fleeing foe, Uncanny Dodge, Indomitable, Heroic Inspiration - the battle asks `ask(b, Decision(...))`. The enemy
and companions on Auto answer at once (the decision's `default`, the battle's own judgement). A party member the
player commands may be asked instead, by the Reactions setting:
    ask    (the default) only for what spends something limited - a spell slot, a use, Heroic Inspiration; free and
           obvious reactions (an opportunity attack on a fleeing enemy, rolling with a blow) happen by themselves
    all    every reaction asks
    auto   none asks: the game decides for you

Asking means pausing: the battle's resolution runs in a resolver (`Resolver`: a worker thread that hands over to the
caller and back, so only one of them ever runs) and stops at the decision; `Battle.pending_decision` shows it and
`Battle.answer(value)` takes the resolution up again. Nothing ever waits on the interface: when no resolution is
running in a resolver (tests, the balance tool, autoplay without a window), every decision takes its default.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field

SETTING_CHOICES = ("ask", "all", "auto")


@dataclass
class Decision:
    who: object  # the fighter who decides
    kind: str  # "shield", "opportunity", "uncanny_dodge", "protection", "projected_ward", "indomitable"...
    text: str  # what is happening, and the choice
    options: list = field(default_factory=lambda: [("yes", "Yes"), ("no", "No")])  # (value, label)
    default: str = "yes"  # what the battle would choose
    free: bool = False  # spends nothing limited (it may still use the reaction)


class Cancelled(Exception):
    """The battle was left while a decision waited."""


class Resolver:
    """Runs a piece of the battle so that it can stop at a decision and be taken up again."""

    def __init__(self) -> None:
        self.thread: threading.Thread | None = None
        self._to_worker: queue.Queue = queue.Queue()
        self._to_main: queue.Queue = queue.Queue()
        self.pending: Decision | None = None

    def in_worker(self) -> bool:
        return self.thread is not None and threading.current_thread() is self.thread

    def run(self, fn, *args, **kwargs):
        """Run `fn` to its end, or to the first decision (then `pending` is set and None is returned)."""
        if self.in_worker():
            return fn(*args, **kwargs)  # (already inside a resolution: just go on)
        if self.pending is not None:
            return None  # a decision is waiting: nothing else happens until it is answered
        self.thread = threading.Thread(target=self._work, args=(fn, args, kwargs), daemon=True, name="battle")
        self.thread.start()
        return self._wait()

    def _work(self, fn, args, kwargs) -> None:
        try:
            self._to_main.put(("done", fn(*args, **kwargs)))
        except Cancelled:
            self._to_main.put(("done", None))
        except BaseException as exc:  # handed to the caller, who raises it where the game catches errors
            self._to_main.put(("error", exc))

    def _wait(self):
        kind, value = self._to_main.get()
        if kind == "ask":
            self.pending = value
            return None
        self.thread = None
        if kind == "error":
            raise value
        return value

    def ask(self, decision: Decision) -> str:
        """In the worker: hand the decision over and wait for the answer."""
        self._to_main.put(("ask", decision))
        answer = self._to_worker.get()
        if answer is Cancelled:
            raise Cancelled()
        return answer

    def answer(self, value: str):
        """Give the waiting resolution its answer and run it on to its end or its next decision."""
        if self.pending is None:
            return None
        self.pending = None
        self._to_worker.put(value)
        return self._wait()

    def cancel(self) -> None:
        if self.pending is not None:
            self.pending = None
            self._to_worker.put(Cancelled)
            self._wait()


def needs_player(b, d: Decision) -> bool:
    who = d.who
    if not b.resolver.in_worker() or getattr(who, "auto", True) or who.side != "party" or not b.human:
        return False
    setting = getattr(b, "reactions", "ask")
    if setting == "auto":
        return False
    return setting == "all" or not d.free


def ask(b, d: Decision) -> str:
    """The answer to a decision (see the module's notes)."""
    if needs_player(b, d):
        return b.resolver.ask(d)
    return d.default


def yes(b, d: Decision) -> bool:
    return ask(b, d) == "yes"
