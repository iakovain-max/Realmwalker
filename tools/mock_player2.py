"""A fake Player2 app for tests and the autoplay bot, so AI code paths run without the real app
(and without spending real Player2 energy).

It answers /v1/health, /v1/joules and /v1/chat/completions. In "ok" mode it reads the JSON shape
our prompt asks for (the object full of <descriptions>) and fills it with plausible values, so
any task works without the mock knowing about it. Other modes simulate every failure we handle.

Run standalone:  python tools/mock_player2.py --port 4316 --mode chaos
then set "player2_base_url": "http://127.0.0.1:4316/v1" in config.json.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODES = ("ok", "fenced", "prose", "wrapped", "garbage_then_ok", "garbage", "refusal", "empty", "truncated",
         "http401", "http402", "http429", "http500", "slow")
CHAOS_WEIGHTS = {"ok": 10, "fenced": 3, "prose": 3, "wrapped": 2, "garbage_then_ok": 2, "garbage": 1,
                 "refusal": 1, "empty": 1, "truncated": 1, "http500": 1, "http429": 1}

_WORDS = ["ash", "barley", "cinder", "damp", "ember", "flint", "gorse", "hollow", "iron", "juniper", "kestrel",
          "lantern", "moss", "nettle", "oak", "peat", "quarry", "rust", "salt", "tallow", "umber", "vetch",
          "willow", "yarrow"]


def _find_shape(messages: list[dict]) -> object | None:
    """The first JSON object in a user message whose strings look like <placeholders>."""
    from realmwalker.ai.parsing import extract_first_json_object

    for m in messages:
        if m.get("role") != "user":
            continue
        text = m.get("content") or ""
        block = extract_first_json_object(text)
        if block and "<" in block:
            try:
                return json.loads(block)
            except ValueError:
                continue
    return None


def fill_shape(shape: object, rng: random.Random) -> object:
    if isinstance(shape, dict):
        return {k: fill_shape(v, rng) for k, v in shape.items()}
    if isinstance(shape, list):
        return [fill_shape(v, rng) for v in shape]
    if isinstance(shape, str):
        m = re.fullmatch(r"<one of: (.+)>", shape)
        if m:
            return rng.choice([c.strip() for c in m.group(1).split("|")])
        m = re.fullmatch(r"<whole number (-?\d+)-(-?\d+)>", shape)
        if m:
            return rng.randint(int(m.group(1)), int(m.group(2)))
        m = re.fullmatch(r"<number (-?[\d.e+]+)-(-?[\d.e+]+)>", shape)
        if m:
            return round(rng.uniform(float(m.group(1)), float(m.group(2))), 2)
        if shape == "<true or false>":
            return rng.random() < 0.5
        words = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(2, 5)))
        return f"Mock {words}."
    return shape


class MockPlayer2:
    def __init__(self, mode: str = "ok", *, joules: int = 500, latency: float = 0.0, seed: int = 0,
                 port: int = 0, version: str = "mock-1.0") -> None:
        self.mode = mode
        self.joules = joules
        self.latency = latency
        self.version = version
        self.rng = random.Random(seed)
        self.requests: list[dict] = []
        self.chat_calls = 0
        self._lock = threading.Lock()
        self._garbage_sent: set[int] = set()
        self.server = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.server.daemon_threads = True
        self.thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def start(self) -> MockPlayer2:
        self.thread = threading.Thread(target=self.server.serve_forever, name="mock-player2", daemon=True)
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self) -> MockPlayer2:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # ------------------------------------------------------------------
    def _pick_mode(self) -> str:
        if self.mode != "chaos":
            return self.mode
        names = list(CHAOS_WEIGHTS)
        return self.rng.choices(names, weights=[CHAOS_WEIGHTS[n] for n in names])[0]

    def _chat_reply(self, body: dict) -> tuple[int, dict | str]:
        with self._lock:
            self.chat_calls += 1
            self.requests.append(body)
            mode = self._pick_mode()
            rng = random.Random(self.rng.random())
        if self.latency:
            time.sleep(self.latency)
        if mode == "slow":
            time.sleep(3.0)
            mode = "ok"
        if mode.startswith("http"):
            code = int(mode[4:])
            if code == 402:
                self.joules = 0
            return code, "mock error"
        messages = body.get("messages", [])
        shape = _find_shape(messages)
        filled = fill_shape(shape, rng) if shape is not None else {"text": "Mock reply."}
        good = json.dumps(filled)
        is_retry = any(m.get("role") == "assistant" for m in messages)
        if mode == "garbage_then_ok":
            content = good if is_retry else "Here is your tavern! It is lovely."
        elif mode == "garbage":
            content = "{not json at all"
        elif mode == "fenced":
            content = f"```json\n{good}\n```"
        elif mode == "prose":
            content = f"Certainly. Here it is:\n{good}\nI hope this fits your world."
        elif mode == "wrapped":
            content = json.dumps({"result": filled})
        elif mode == "refusal":
            content = "I'm sorry, but I can't help with that request."
        elif mode in ("empty", "truncated"):
            content = ""
        else:
            content = good
        completion = int(body.get("max_tokens") or 4000) if mode == "truncated" else 50
        message = {"role": "assistant"}
        if content:
            message["content"] = content
        return 200, {
            "id": f"mock-{self.chat_calls}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "mock-model",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": completion, "total_tokens": 100 + completion},
        }

    def _handler(self):
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # keep test output quiet
                pass

            def _send(self, code: int, payload: dict | str) -> None:
                raw = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/plain" if isinstance(payload, str) else "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                if self.path == "/v1/health":
                    if mock.mode == "http401":
                        self._send(401, "not logged in")
                    else:
                        self._send(200, {"client_version": mock.version})
                elif self.path == "/v1/joules":
                    self._send(200, {"joules": mock.joules, "patron_tier": "", "user_id": "mock-user"})
                else:
                    self._send(404, "not found")

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    self._send(400, "bad json")
                    return
                if self.path == "/v1/chat/completions":
                    code, payload = mock._chat_reply(body)
                    self._send(code, payload)
                else:
                    self._send(404, "not found")

        return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Fake Player2 API for testing Realmwalker")
    parser.add_argument("--port", type=int, default=4316)
    parser.add_argument("--mode", default="ok", choices=MODES + ("chaos",))
    args = parser.parse_args()
    mock = MockPlayer2(args.mode, port=args.port).start()
    print(f"Mock Player2 running at {mock.base_url} (mode: {args.mode}). Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        mock.stop()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    main()
