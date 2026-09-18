"""Turning an AI reply into a usable JSON object, defensively.

Models wrap JSON in code fences, add a sentence before or after it, leave trailing commas,
or refuse outright. We strip what we can, extract the first JSON object, and detect refusals.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n?(.*?)```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")

REFUSAL_PATTERNS = [
    r"\bI(?: am|'m) (?:sorry|unable|not able)\b",
    r"\bI can(?:not|'t|’t) (?:help|assist|create|write|provide|comply|do that|generate|produce)\b",
    r"\bI won(?:'t|’t) (?:help|assist|create|write|provide|generate)\b",
    r"\bas an AI\b",
    r"\bAI language model\b",
    r"\bcontent (?:policy|guidelines)\b",
    r"\bI must (?:decline|refuse)\b",
    r"\bnot (?:comfortable|appropriate) (?:to|for me)\b",
]
_REFUSAL_RE = re.compile("|".join(REFUSAL_PATTERNS), re.IGNORECASE)


class ParseError(ValueError):
    pass


def strip_code_fences(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def extract_first_json_object(text: str) -> str | None:
    """Return the first balanced {...} block, respecting strings and escapes."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        # Unbalanced from this start; try the next opening brace.
        start = text.find("{", start + 1)
    return None


def _try_load(candidate: str) -> Any:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    repaired = _TRAILING_COMMA_RE.sub(r"\1", candidate)
    repaired = repaired.replace("“", '"').replace("”", '"')
    return json.loads(repaired)


def parse_json_reply(text: str | None) -> dict:
    """Extract a JSON object from a model reply or raise ParseError explaining why not."""
    if not text or not text.strip():
        raise ParseError("the reply was empty")
    body = strip_code_fences(text)
    candidates = [body]
    extracted = extract_first_json_object(body)
    if extracted and extracted != body:
        candidates.append(extracted)
    if body != text:
        extracted_raw = extract_first_json_object(text)
        if extracted_raw:
            candidates.append(extracted_raw)
    last_error = "no JSON object found"
    for candidate in candidates:
        try:
            value = _try_load(candidate)
        except json.JSONDecodeError as exc:
            last_error = f"invalid JSON ({exc.msg} at line {exc.lineno})"
            continue
        if isinstance(value, dict):
            return value
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
        last_error = "the reply was JSON but not an object"
    if looks_like_refusal(text):
        raise ParseError("the model refused")
    raise ParseError(last_error)


def looks_like_refusal(text: str | None) -> bool:
    return bool(text) and bool(_REFUSAL_RE.search(text))


def find_refusal_in_values(value: Any) -> bool:
    """True if any string inside a parsed reply reads like a refusal."""
    if isinstance(value, str):
        return looks_like_refusal(value)
    if isinstance(value, dict):
        return any(find_refusal_in_values(v) for v in value.values())
    if isinstance(value, list):
        return any(find_refusal_in_values(v) for v in value)
    return False


def clean_ai_text(text: str) -> str:
    """Remove characters our colour markup uses, and stray markdown emphasis."""
    text = text.replace("<", "(").replace(">", ")")
    text = re.sub(r"\*\*?([^*]+)\*\*?", r"\1", text)
    return text
