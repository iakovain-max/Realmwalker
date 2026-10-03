"""Tiny schema language used in two places:

* `check()`  - strict validation of our JSON data files, with readable error messages.
* `clean()`  - lenient clean-up of AI replies: trims text, clamps numbers, drops extras,
               and raises SchemaError only when something essential is missing or unusable.
* `example()` - the JSON shape shown to the AI in prompts, generated from the same schema,
               so what we ask for and what we accept can never drift apart.
"""

from __future__ import annotations

import json
import re
from typing import Any

_WS_RE = re.compile(r"\s+")


class SchemaError(ValueError):
    pass


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, int):
        return "a whole number"
    if isinstance(value, float):
        return "a number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    if value is None:
        return "null"
    return type(value).__name__


def join_path(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else key


class Spec:
    optional: bool = False
    hint: str = ""

    def check(self, value: Any, path: str, errors: list[str]) -> None:
        raise NotImplementedError

    def clean(self, value: Any, path: str = "") -> Any:
        raise NotImplementedError

    def example(self) -> Any:
        raise NotImplementedError

    def example_json(self) -> str:
        return json.dumps(self.example(), indent=2, ensure_ascii=False)


class Str(Spec):
    def __init__(
        self,
        hint: str = "text",
        *,
        max_len: int = 400,
        min_len: int = 1,
        choices: list[str] | tuple[str, ...] | None = None,
        optional: bool = False,
        lenient: bool = False,
    ) -> None:
        self.hint = hint
        self.max_len = max_len
        self.min_len = min_len
        self.choices = list(choices) if choices else None
        self.optional = optional
        self.lenient = lenient  # a word not among the choices is dropped (None), not an error

    def check(self, value, path, errors):
        if not isinstance(value, str):
            errors.append(f"{path}: expected text, got {_type_name(value)}")
            return
        if len(value.strip()) < self.min_len:
            errors.append(f"{path}: text is empty")
        elif len(value) > self.max_len:
            errors.append(f"{path}: text is longer than {self.max_len} characters")
        if self.choices and value not in self.choices:
            errors.append(f"{path}: {value!r} is not one of {', '.join(self.choices)}")

    def clean(self, value, path=""):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            raise SchemaError(f"{path or 'value'}: expected text, got {_type_name(value)}")
        text = _WS_RE.sub(" ", value).strip()
        if self.choices:
            lowered = {c.lower(): c for c in self.choices}
            key = text.lower().strip(" .!\"'")
            if key in lowered:
                return lowered[key]
            if self.lenient:
                return None
            raise SchemaError(f"{path or 'value'}: {text!r} is not one of {', '.join(self.choices)}")
        if len(text) < self.min_len:
            raise SchemaError(f"{path or 'value'}: text is empty")
        if len(text) > self.max_len:
            text = truncate_text(text, self.max_len)
        return text

    def example(self):
        if self.choices:
            return "<one of: " + " | ".join(self.choices) + ">"
        return f"<{self.hint}>"


class Int(Spec):
    def __init__(self, hint: str = "", *, min: int = -(10**9), max: int = 10**9, optional: bool = False) -> None:
        self.hint = hint
        self.min = min
        self.max = max
        self.optional = optional

    def check(self, value, path, errors):
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: expected a whole number, got {_type_name(value)}")
            return
        if not self.min <= value <= self.max:
            errors.append(f"{path}: {value} is outside {self.min}..{self.max}")

    def clean(self, value, path=""):
        if isinstance(value, bool):
            raise SchemaError(f"{path or 'value'}: expected a whole number")
        if isinstance(value, str):
            m = re.search(r"-?\d+", value)
            if not m:
                raise SchemaError(f"{path or 'value'}: expected a whole number, got {value!r}")
            value = int(m.group())
        if isinstance(value, float):
            value = round(value)
        if not isinstance(value, int):
            raise SchemaError(f"{path or 'value'}: expected a whole number, got {_type_name(value)}")
        return max(self.min, min(self.max, value))

    def example(self):
        return f"<whole number {self.min}-{self.max}>"


class Float(Spec):
    def __init__(self, hint: str = "", *, min: float = -1e18, max: float = 1e18, optional: bool = False) -> None:
        self.hint = hint
        self.min = min
        self.max = max
        self.optional = optional

    def check(self, value, path, errors):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{path}: expected a number, got {_type_name(value)}")
            return
        if value != value or not self.min <= value <= self.max:
            errors.append(f"{path}: {value} is outside {self.min}..{self.max}")

    def clean(self, value, path=""):
        if isinstance(value, bool):
            raise SchemaError(f"{path or 'value'}: expected a number")
        if isinstance(value, str):
            try:
                value = float(value.strip())
            except ValueError as exc:
                raise SchemaError(f"{path or 'value'}: expected a number, got {value!r}") from exc
        if not isinstance(value, (int, float)) or value != value:
            raise SchemaError(f"{path or 'value'}: expected a number")
        return max(self.min, min(self.max, float(value)))

    def example(self):
        return f"<number {self.min}-{self.max}>"


class Bool(Spec):
    def __init__(self, hint: str = "", *, optional: bool = False) -> None:
        self.hint = hint
        self.optional = optional

    def check(self, value, path, errors):
        if not isinstance(value, bool):
            errors.append(f"{path}: expected true or false, got {_type_name(value)}")

    def clean(self, value, path=""):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "yes", "false", "no"):
            return value.strip().lower() in ("true", "yes")
        raise SchemaError(f"{path or 'value'}: expected true or false")

    def example(self):
        return "<true or false>"


class Any_(Spec):
    def __init__(self, *, optional: bool = False) -> None:
        self.optional = optional

    def check(self, value, path, errors):
        return None

    def clean(self, value, path=""):
        return value

    def example(self):
        return "<anything>"


class List(Spec):
    def __init__(self, item: Spec, *, min_items: int = 0, max_items: int | None = None, optional: bool = False, hint: str = "") -> None:
        self.item = item
        self.min_items = min_items
        self.max_items = max_items
        self.optional = optional
        self.hint = hint

    def check(self, value, path, errors):
        if not isinstance(value, list):
            errors.append(f"{path}: expected a list, got {_type_name(value)}")
            return
        if len(value) < self.min_items:
            errors.append(f"{path}: needs at least {self.min_items} entries, has {len(value)}")
        if self.max_items is not None and len(value) > self.max_items:
            errors.append(f"{path}: has more than {self.max_items} entries")
        for i, item in enumerate(value):
            self.item.check(item, join_path(path, i), errors)

    def clean(self, value, path=""):
        if isinstance(value, (str, dict)) and not isinstance(self.item, List):
            value = [value]
        if not isinstance(value, list):
            raise SchemaError(f"{path or 'value'}: expected a list")
        out = []
        for i, item in enumerate(value):
            if self.max_items is not None and len(out) >= self.max_items:
                break
            try:
                out.append(self.item.clean(item, join_path(path, i)))
            except SchemaError:
                continue  # drop unusable entries, keep the good ones
        if len(out) < self.min_items:
            raise SchemaError(f"{path or 'value'}: needs at least {self.min_items} usable entries")
        return out

    def example(self):
        return [self.item.example() for _ in range(max(1, self.min_items))]


class Obj(Spec):
    """An object with known fields. Keys starting with '_' (comments) are always allowed."""

    def __init__(self, fields: dict[str, Spec], *, optional: bool = False, strict: bool = True, hint: str = "") -> None:
        self.fields = fields
        self.optional = optional
        self.strict = strict
        self.hint = hint

    def check(self, value, path, errors):
        if not isinstance(value, dict):
            errors.append(f"{path or 'file'}: expected an object, got {_type_name(value)}")
            return
        for key, spec in self.fields.items():
            if key not in value:
                if not spec.optional:
                    errors.append(f"{join_path(path, key)}: missing")
                continue
            spec.check(value[key], join_path(path, key), errors)
        if self.strict:
            for key in value:
                if key not in self.fields and not str(key).startswith("_"):
                    errors.append(f"{join_path(path, key)}: unknown field (typo?)")

    def clean(self, value, path=""):
        if not isinstance(value, dict):
            raise SchemaError(f"{path or 'reply'}: expected a JSON object")
        # Be forgiving about key case and spacing: "Keeper Name" -> "keeper_name".
        normalised = {_norm_key(k): v for k, v in value.items()}
        out = {}
        for key, spec in self.fields.items():
            raw = value.get(key, normalised.get(_norm_key(key)))
            if raw is None or raw == "":
                if spec.optional:
                    continue
                raise SchemaError(f"{join_path(path, key)}: missing")
            cleaned = spec.clean(raw, join_path(path, key))
            if cleaned is None and spec.optional:
                continue
            out[key] = cleaned
        return out

    def example(self):
        return {key: spec.example() for key, spec in self.fields.items()}


class Map(Spec):
    """An object whose keys are free-form ids and whose values share one spec."""

    def __init__(self, value: Spec, *, min_items: int = 0, optional: bool = False, hint: str = "") -> None:
        self.value = value
        self.min_items = min_items
        self.optional = optional
        self.hint = hint

    def check(self, value, path, errors):
        if not isinstance(value, dict):
            errors.append(f"{path}: expected an object, got {_type_name(value)}")
            return
        entries = {k: v for k, v in value.items() if not str(k).startswith("_")}
        if len(entries) < self.min_items:
            errors.append(f"{path}: needs at least {self.min_items} entries")
        for key, item in entries.items():
            self.value.check(item, join_path(path, key), errors)

    def clean(self, value, path=""):
        if not isinstance(value, dict):
            raise SchemaError(f"{path or 'value'}: expected an object")
        return {k: self.value.clean(v, join_path(path, k)) for k, v in value.items()}

    def example(self):
        return {"<id>": self.value.example()}


def _norm_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")


def truncate_text(text: str, max_len: int) -> str:
    """Shorten text, preferring to cut at the end of a sentence, then a word."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    for mark in (". ", "! ", "? "):
        idx = cut.rfind(mark)
        if idx >= max_len * 0.5:
            return cut[: idx + 1]
    idx = cut.rfind(" ")
    if idx >= max_len * 0.5:
        return cut[:idx].rstrip(",;:") + "…"
    return cut[: max_len - 1] + "…"
