"""Prompt templates live as plain text files in ai/prompts/ so they can be tuned without code.

File format:
    @max_tokens: 700        <- optional settings lines at the top
    @temperature: 0.9
    # comment lines are ignored
    The prompt text, with {slots} filled from variables.

Only {lower_case} slots that match a supplied variable are replaced, so literal braces are safe.
Files are re-read when they change on disk, so prompts can be edited while the game runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SLOT_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


@dataclass
class PromptTemplate:
    name: str
    text: str
    settings: dict[str, str] = field(default_factory=dict)

    def render(self, variables: dict[str, object]) -> str:
        def sub(m: re.Match) -> str:
            key = m.group(1)
            return str(variables[key]) if key in variables else m.group(0)

        return _SLOT_RE.sub(sub, self.text).strip()

    def slots(self) -> set[str]:
        return set(_SLOT_RE.findall(self.text))

    def setting_int(self, key: str, default: int) -> int:
        try:
            return int(self.settings.get(key, default))
        except ValueError:
            return default

    def setting_float(self, key: str, default: float) -> float:
        try:
            return float(self.settings.get(key, default))
        except ValueError:
            return default


def parse_template(name: str, raw: str) -> PromptTemplate:
    settings: dict[str, str] = {}
    body: list[str] = []
    header = True
    for line in raw.splitlines():
        stripped = line.strip()
        if header and stripped.startswith("@") and ":" in stripped:
            key, value = stripped[1:].split(":", 1)
            settings[key.strip()] = value.strip()
            continue
        if stripped.startswith("#"):
            continue
        header = False
        body.append(line)
    return PromptTemplate(name, "\n".join(body).strip(), settings)


class PromptLibrary:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._cache: dict[str, tuple[float, PromptTemplate]] = {}

    def get(self, name: str) -> PromptTemplate:
        path = self.folder / f"{name}.txt"
        mtime = path.stat().st_mtime  # raises FileNotFoundError for a missing prompt
        cached = self._cache.get(name)
        if cached and cached[0] == mtime:
            return cached[1]
        template = parse_template(name, path.read_text(encoding="utf-8"))
        self._cache[name] = (mtime, template)
        return template

    def exists(self, name: str) -> bool:
        return (self.folder / f"{name}.txt").exists()

    def names(self) -> list[str]:
        return sorted(p.stem for p in self.folder.glob("*.txt"))
