"""Thin wrapper around the local Player2 app API (checked against its docs, client v0.10.79).

Facts from the Player2 docs that shape this module:
* The API runs at http://127.0.0.1:<port>/v1 while the Player2 app is open. Use 127.0.0.1, not
  "localhost" (IPv6 trouble). The port is written to %APPDATA%/game.player2.client/api.port and
  defaults to 4315; the file disappears when the app closes cleanly.
* GET  /v1/health  -> {"client_version": "..."}; ping every 60 s while the game runs.
* GET  /v1/joules  -> {"joules": int, "patron_tier": str, "user_id": str}; remaining energy.
* POST /v1/chat/completions, OpenAI style; reply text is choices[0].message.content.
* Errors: 401 = not logged in to the app, 402 = out of energy, 429 = too many requests, 5xx.
* An optional game client id goes in the "player2-game-key" header. Not required locally.

Found by testing (Player2 v0.10.79, model deepseek-v4-pro, 2026-09-19):
* response_format={"type": "json_object"} makes the model return an empty message, so we never
  send response_format and parse JSON ourselves instead.
* The model thinks silently before answering: a tavern description used 784 completion tokens
  of which only ~180 were the answer. A max_tokens that is too small yields an EMPTY reply that
  still costs energy, so allowances must be generous (see ai/prompts/*.txt @max_tokens).
* Cost observed: about 2 energy ("joules") for ~1300 tokens. A Patron Basic account had ~10 a day.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx

DEFAULT_PORT = 4315


def port_file() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "game.player2.client" / "api.port"


def app_detected() -> bool:
    """The port file exists only while the Player2 app is running."""
    pf = port_file()
    return bool(pf and pf.exists())


def discover_base_url() -> str:
    port = DEFAULT_PORT
    pf = port_file()
    if pf and pf.exists():
        try:
            port = int(pf.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            port = DEFAULT_PORT
    return f"http://127.0.0.1:{port}/v1"


class P2Error(Exception):
    """A failed Player2 call. `kind` is one of:
    offline, auth, energy, rate, server, timeout, bad_response, empty."""

    def __init__(self, kind: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


@dataclass
class ChatReply:
    content: str
    finish_reason: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class Player2Client:
    def __init__(self, base_url: str | None = None, game_key: str = "", *, chat_timeout: float = 60.0) -> None:
        self.base_url = (base_url or discover_base_url()).rstrip("/")
        headers = {"Content-Type": "application/json"}
        if game_key:
            headers["player2-game-key"] = game_key
        self._http = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(chat_timeout, connect=3.0),
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Player2Client:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, *, json_body: dict | None = None, timeout: float | None = None) -> dict:
        try:
            kwargs = {"json": json_body} if json_body is not None else {}
            if timeout is not None:
                kwargs["timeout"] = timeout
            resp = self._http.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise P2Error("offline", "Player2 app is not running or not reachable") from exc
        except httpx.TimeoutException as exc:
            raise P2Error("timeout", "Player2 did not answer in time") from exc
        except httpx.HTTPError as exc:
            raise P2Error("offline", f"connection problem: {exc}") from exc

        code = resp.status_code
        if code == 401:
            raise P2Error("auth", "not logged in to the Player2 app", code)
        if code == 402:
            raise P2Error("energy", "out of Player2 energy for today", code)
        if code == 429:
            raise P2Error("rate", "too many requests; slowing down", code)
        if code >= 500:
            raise P2Error("server", f"Player2 server error ({code})", code)
        if code >= 400:
            raise P2Error("bad_response", f"request rejected ({code}): {resp.text[:200]}", code)
        try:
            data = resp.json()
        except ValueError as exc:
            raise P2Error("bad_response", "reply was not JSON", code) from exc
        if not isinstance(data, dict):
            raise P2Error("bad_response", "reply was not a JSON object", code)
        return data

    def health(self) -> str:
        """Return the Player2 client version, or raise P2Error."""
        data = self._request("GET", "/health", timeout=5.0)
        return str(data.get("client_version", "unknown"))

    def joules(self) -> tuple[int, str]:
        """Return (remaining energy, patron tier)."""
        data = self._request("GET", "/joules", timeout=5.0)
        try:
            return int(data.get("joules", 0)), str(data.get("patron_tier", ""))
        except (TypeError, ValueError) as exc:
            raise P2Error("bad_response", "joules reply malformed") from exc

    def chat(self, messages: list[dict], *, max_tokens: int = 600, temperature: float | None = None) -> ChatReply:
        body: dict = {"messages": messages, "max_tokens": max_tokens, "stream": False}
        if temperature is not None:
            body["temperature"] = temperature
        data = self._request("POST", "/chat/completions", json_body=body)
        try:
            choice = data["choices"][0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            finish = str(choice.get("finish_reason") or "")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise P2Error("bad_response", "chat reply had no choices") from exc
        usage = data.get("usage") or {}
        used = int(usage.get("completion_tokens", 0) or 0)
        if not isinstance(content, str) or not content.strip():
            # The current model "thinks" silently before answering. If it spends the whole token
            # allowance thinking, the reply is empty but the energy is still spent.
            if used >= max_tokens * 0.95:
                raise P2Error("truncated", f"the model used all {used} tokens thinking and wrote nothing")
            raise P2Error("empty", f"the model returned no text (finish: {finish or '?'})")
        return ChatReply(
            content=content,
            finish_reason=finish,
            model=str(data.get("model", "")),
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=used,
        )
