"""The AI service: background workers, a priority queue, a health ping and the status indicator.

Game code never waits on the AI. It submits a request and gets a Ticket back; results are
handed back on the main thread by `poll()`, which the game loop calls every frame. When the
AI is off, offline, out of energy or too slow, callers use their built-in fallback text.
"""

from __future__ import annotations

import itertools
import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from realmwalker.ai import parsing
from realmwalker.ai.client import P2Error, Player2Client
from realmwalker.ai.prompts import PromptLibrary
from realmwalker.core.logs import AI_DEBUG_LOGGER
from realmwalker.core.schema import Obj, SchemaError

log = logging.getLogger("realmwalker.ai")
debug_log = logging.getLogger(AI_DEBUG_LOGGER)

SYSTEM_PROMPT = "system"
CONNECT_GRACE = 10.0  # seconds a request may wait while the first health ping is in progress
CORRECTION = (
    "That reply could not be used: {error}. Reply again with ONLY the JSON object described above, "
    "every field filled in, and no other text."
)


class Priority:
    URGENT = 0  # the player is waiting (conversation)
    HIGH = 2  # needed very soon (the party is arriving)
    NORMAL = 5
    BACKGROUND = 8  # buffers and world flavour


class AIStatus(str, Enum):
    DISABLED = "disabled"
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"
    NO_ENERGY = "no_energy"
    NOT_LOGGED_IN = "not_logged_in"
    SIMULATED_OFFLINE = "simulated_offline"


STATUS_TEXT = {
    AIStatus.DISABLED: ("AI off — using built-in text", "dim"),
    AIStatus.CONNECTING: ("AI connecting…", "warn"),
    AIStatus.ONLINE: ("AI online", "good"),
    AIStatus.OFFLINE: ("AI offline — using built-in text", "warn"),
    AIStatus.NO_ENERGY: ("AI out of energy — using built-in text", "warn"),
    AIStatus.NOT_LOGGED_IN: ("AI: log in to the Player2 app", "warn"),
    AIStatus.SIMULATED_OFFLINE: ("AI offline (test) — using built-in text", "warn"),
}


@dataclass(frozen=True)
class AITask:
    """One kind of text we ask the AI for: a prompt file plus the JSON shape we accept."""

    name: str
    schema: Obj
    max_tokens: int = 700
    temperature: float = 0.85


@dataclass
class AIResult:
    ok: bool
    data: dict | None = None
    error: str = ""
    elapsed: float = 0.0
    attempts: int = 0
    raw: str = ""
    tokens: int = 0


class Ticket:
    def __init__(self, task: AITask, messages: list[dict], max_tokens: int, temperature: float,
                 callback: Callable[[AIResult], None] | None, created: float) -> None:
        self.task = task
        self.messages = messages
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.callback = callback
        self.created = created
        self.done = False
        self.cancelled = False
        self.result: AIResult | None = None

    def cancel(self) -> None:
        """The caller no longer needs this (e.g. it timed out and used the fallback)."""
        self.cancelled = True


@dataclass(order=True)
class _Job:
    priority: int
    seq: int
    ticket: Ticket = field(compare=False)


class AIService:
    def __init__(
        self,
        *,
        prompts: PromptLibrary,
        client_factory: Callable[[], Player2Client],
        enabled: bool = True,
        workers: int = 2,
        ping_interval: float = 60.0,
        retry_interval: float = 15.0,
        energy_reserve: int = 6,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.prompts = prompts
        self.energy_reserve = energy_reserve  # background requests stop below this much energy
        self.client_factory = client_factory
        self.workers = workers
        self.ping_interval = ping_interval
        self.retry_interval = retry_interval
        self.clock = clock

        self._enabled = enabled
        self._simulated_offline = False
        self._status = AIStatus.CONNECTING if enabled else AIStatus.DISABLED
        self.client_version = ""
        self.joules: int | None = None
        self.patron_tier = ""
        self.last_ping_at: float | None = None
        self.last_ping_ok = False
        self.last_error = ""
        self._server_errors = 0

        self._lock = threading.Lock()
        self._jobs: queue.PriorityQueue[_Job] = queue.PriorityQueue()
        self._results: queue.SimpleQueue[Ticket] = queue.SimpleQueue()
        self._seq = itertools.count()
        self._stop = threading.Event()
        self._wake_ping = threading.Event()
        self._threads: list[threading.Thread] = []
        self._in_flight = 0
        self.stats = {"sent": 0, "ok": 0, "failed": 0, "retried": 0, "refused": 0}

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._threads:
            return
        self._stop.clear()
        pinger = threading.Thread(target=self._ping_loop, name="ai-ping", daemon=True)
        self._threads.append(pinger)
        for i in range(self.workers):
            self._threads.append(threading.Thread(target=self._worker_loop, name=f"ai-worker-{i}", daemon=True))
        for t in self._threads:
            t.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._wake_ping.set()
        for t in self._threads:
            t.join(timeout)
        self._threads.clear()

    # ------------------------------------------------------------------ status
    @property
    def status(self) -> AIStatus:
        if not self._enabled:
            return AIStatus.DISABLED
        if self._simulated_offline:
            return AIStatus.SIMULATED_OFFLINE
        return self._status

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def simulated_offline(self) -> bool:
        return self._simulated_offline

    def usable(self) -> bool:
        return self.status == AIStatus.ONLINE

    def status_text(self) -> tuple[str, str]:
        """(label, colour name) for the little status indicator."""
        return STATUS_TEXT[self.status]

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled
            if enabled:
                self._status = AIStatus.CONNECTING
        if enabled:
            self.ping_now()

    def set_simulated_offline(self, on: bool) -> None:
        self._simulated_offline = on
        if not on:
            self.ping_now()

    def ping_now(self) -> None:
        self._wake_ping.set()

    @property
    def pending(self) -> int:
        return self._jobs.qsize() + self._in_flight

    # ------------------------------------------------------------------ requests
    def build_messages(self, task: AITask, variables: dict, *, context: str = "") -> list[dict]:
        system = self.prompts.get(SYSTEM_PROMPT).render({})
        if context:
            system = f"{system}\n\nWorld context:\n{context.strip()}"
        user = self.prompts.get(task.name).render({**variables, "schema": task.schema.example_json()})
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def submit(
        self,
        task: AITask,
        variables: dict,
        *,
        priority: int = Priority.NORMAL,
        callback: Callable[[AIResult], None] | None = None,
        context: str = "",
    ) -> Ticket:
        """Queue a request. The callback runs later on the main thread, from poll()."""
        template = self.prompts.get(task.name)
        max_tokens = template.setting_int("max_tokens", task.max_tokens)
        temperature = template.setting_float("temperature", task.temperature)
        ticket = Ticket(task, self.build_messages(task, variables, context=context), max_tokens, temperature,
                        callback, self.clock())
        if priority >= Priority.BACKGROUND and self.joules is not None and self.joules < self.energy_reserve:
            # Low on energy: keep what is left for text the player is waiting for.
            self._finish(ticket, AIResult(False, error="saving AI energy for important text"))
        elif self.status in (AIStatus.ONLINE, AIStatus.CONNECTING):
            self._jobs.put(_Job(priority, next(self._seq), ticket))
        else:
            self._finish(ticket, AIResult(False, error=self.status_text()[0]))
        return ticket

    def poll(self, max_items: int = 50) -> int:
        """Deliver finished results to their callbacks. Call from the main thread every frame."""
        delivered = 0
        while delivered < max_items:
            try:
                ticket = self._results.get_nowait()
            except queue.Empty:
                break
            delivered += 1
            if ticket.cancelled or ticket.callback is None:
                continue
            try:
                ticket.callback(ticket.result)
            except Exception:  # a broken callback must never take the game down
                log.exception("AI result callback failed for task %s", ticket.task.name)
        return delivered

    def wait_idle(self, timeout: float = 10.0) -> bool:
        """Block until the queue is empty (tests and the autoplay bot only)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.pending == 0:
                return True
            time.sleep(0.01)
        return False

    # ------------------------------------------------------------------ threads
    def _finish(self, ticket: Ticket, result: AIResult) -> None:
        ticket.result = result
        ticket.done = True
        self._results.put(ticket)

    def _ping_loop(self) -> None:
        client: Player2Client | None = None
        try:
            while not self._stop.is_set():
                if self._enabled and not self._simulated_offline:
                    if client is None:
                        client = self.client_factory()
                    self._ping(client)
                interval = self.ping_interval if self._status == AIStatus.ONLINE else self.retry_interval
                if self._status == AIStatus.NO_ENERGY:
                    interval = max(interval, 60.0)
                self._wake_ping.wait(interval)
                self._wake_ping.clear()
        finally:
            if client is not None:
                client.close()

    def _ping(self, client: Player2Client) -> None:
        self.last_ping_at = self.clock()
        try:
            version = client.health()
            joules, tier = client.joules()
        except P2Error as exc:
            self.last_ping_ok = False
            self.last_error = str(exc)
            self._status = _status_for_error(exc, self._status)
            return
        except Exception as exc:  # never let the ping thread die
            log.exception("Unexpected error pinging Player2")
            self.last_ping_ok = False
            self.last_error = str(exc)
            self._status = AIStatus.OFFLINE
            return
        previous = self._status
        self.last_ping_ok = True
        self.last_error = ""
        self.client_version = version
        self.joules = joules
        self.patron_tier = tier
        self._status = AIStatus.NO_ENERGY if joules <= 0 else AIStatus.ONLINE
        if previous != self._status:
            log.info("Player2 status: %s (client %s, energy %s)", self._status.value, version, joules)

    def _worker_loop(self) -> None:
        client: Player2Client | None = None
        try:
            while not self._stop.is_set():
                try:
                    job = self._jobs.get(timeout=0.25)
                except queue.Empty:
                    continue
                ticket = job.ticket
                if ticket.cancelled:
                    self._finish(ticket, AIResult(False, error="cancelled"))
                    continue
                if self.status == AIStatus.CONNECTING and self.clock() - ticket.created < CONNECT_GRACE:
                    # Still finding out whether Player2 is there; hold the job briefly.
                    self._stop.wait(0.2)
                    self._jobs.put(job)
                    continue
                if not self.usable():
                    self._finish(ticket, AIResult(False, error=self.status_text()[0]))
                    continue
                with self._lock:
                    self._in_flight += 1
                try:
                    if client is None:
                        client = self.client_factory()
                    result = self._run(ticket, client)
                except Exception as exc:
                    log.exception("AI request %s crashed", ticket.task.name)
                    result = AIResult(False, error=f"internal error: {exc}")
                finally:
                    with self._lock:
                        self._in_flight -= 1
                with self._lock:
                    self.stats["ok" if result.ok else "failed"] += 1
                self._finish(ticket, result)
        finally:
            if client is not None:
                client.close()

    def _run(self, ticket: Ticket, client: Player2Client) -> AIResult:
        start = self.clock()
        messages = list(ticket.messages)
        raw = ""
        error = ""
        tokens = 0
        for attempt in (1, 2):
            if ticket.cancelled:
                return AIResult(False, error="cancelled", attempts=attempt - 1)
            with self._lock:
                self.stats["sent"] += 1
            debug_log.debug("REQUEST %s (attempt %d):\n%s", ticket.task.name, attempt, _format_messages(messages))
            try:
                reply = client.chat(messages, max_tokens=ticket.max_tokens, temperature=ticket.temperature)
            except P2Error as exc:
                debug_log.debug("FAILED %s: %s (%s)", ticket.task.name, exc, exc.kind)
                if exc.kind == "truncated":
                    log.warning("AI task %s ran out of tokens (max_tokens %d); raise @max_tokens in its prompt file",
                                ticket.task.name, ticket.max_tokens)
                self._note_error(exc, client)
                # Empty or cut-off replies are not retried: a retry costs the same energy again.
                self._refresh_energy(client)
                return AIResult(False, error=str(exc), elapsed=self.clock() - start, attempts=attempt, tokens=tokens)
            self._server_errors = 0
            tokens += reply.prompt_tokens + reply.completion_tokens
            raw = reply.content
            debug_log.debug("REPLY %s (%s, %d completion tokens):\n%s", ticket.task.name, reply.finish_reason,
                            reply.completion_tokens, raw)
            try:
                data = validate_reply(ticket.task, raw)
                self._refresh_energy(client)
                return AIResult(True, data=data, elapsed=self.clock() - start, attempts=attempt, raw=raw, tokens=tokens)
            except Refused:
                with self._lock:
                    self.stats["refused"] += 1
                self._refresh_energy(client)
                return AIResult(False, error="the model refused", elapsed=self.clock() - start, attempts=attempt,
                                raw=raw, tokens=tokens)
            except (parsing.ParseError, SchemaError) as exc:
                error = str(exc)
                if attempt == 1:
                    with self._lock:
                        self.stats["retried"] += 1
                    messages = messages + [
                        {"role": "assistant", "content": raw[:2000]},
                        {"role": "user", "content": CORRECTION.format(error=error)},
                    ]
        self._refresh_energy(client)
        return AIResult(False, error=f"unusable reply: {error}", elapsed=self.clock() - start, attempts=2, raw=raw,
                        tokens=tokens)

    def _refresh_energy(self, client: Player2Client) -> None:
        """Update the energy display after spending some (a cheap local call)."""
        try:
            self.joules, self.patron_tier = client.joules()
            if self.joules <= 0:
                self._status = AIStatus.NO_ENERGY
        except P2Error:
            pass
        except Exception:
            log.exception("Unexpected error reading Player2 energy")

    def _note_error(self, exc: P2Error, client: Player2Client) -> None:
        if exc.kind == "server":
            self._server_errors += 1
            # Running out of energy sometimes shows up as plain server errors: check the balance.
            if self._server_errors >= 3:
                self._server_errors = 0
                try:
                    joules, _ = client.joules()
                    self.joules = joules
                    if joules <= 0:
                        self._status = AIStatus.NO_ENERGY
                except P2Error:
                    pass
            return
        new_status = _status_for_error(exc, self._status)
        if new_status != self._status:
            self._status = new_status
            self.ping_now()


class Refused(Exception):
    pass


def validate_reply(task: AITask, raw: str) -> dict:
    """Parse and clean one reply against the task schema. Raises ParseError/SchemaError/Refused."""
    try:
        obj = parsing.parse_json_reply(raw)
    except parsing.ParseError as exc:
        if parsing.looks_like_refusal(raw):
            raise Refused() from exc
        raise
    try:
        data = task.schema.clean(obj)
    except SchemaError:
        # Some models wrap the answer: {"tavern": {...}}. Unwrap a single nested object.
        inner = [v for v in obj.values() if isinstance(v, dict)]
        if len(obj) == 1 and len(inner) == 1:
            data = task.schema.clean(inner[0])
        else:
            raise
    if parsing.find_refusal_in_values(data):
        raise Refused()
    return _clean_strings(data)


def _clean_strings(value):
    if isinstance(value, str):
        return parsing.clean_ai_text(value)
    if isinstance(value, dict):
        return {k: _clean_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_strings(v) for v in value]
    return value


def _status_for_error(exc: P2Error, current: AIStatus) -> AIStatus:
    if exc.kind in ("offline", "timeout"):
        return AIStatus.OFFLINE
    if exc.kind == "auth":
        return AIStatus.NOT_LOGGED_IN
    if exc.kind == "energy":
        return AIStatus.NO_ENERGY
    if exc.kind == "server":
        return AIStatus.OFFLINE if current == AIStatus.CONNECTING else current
    return current


def _format_messages(messages: list[dict]) -> str:
    return "\n".join(f"[{m['role']}] {m['content']}" for m in messages)
