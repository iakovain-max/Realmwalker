"""Coloured text markup and word wrapping.

Write "<danger>The wound bleeds.</> You feel faint." Tags are palette names (see colors.NAMED)
or "#rrggbb"; "</>" returns to the previous colour. Unknown tags are printed literally.
Text from the AI or the player is passed through `escape()` first, so it can never inject tags.
"""

from __future__ import annotations

import re

from realmwalker.ui import colors
from realmwalker.ui.colors import Color

_TAG_RE = re.compile(r"<(/?)([a-z_]+|#[0-9a-fA-F]{6})?>")

Span = tuple[str, Color]


def escape(text: str) -> str:
    return text.replace("<", "(").replace(">", ")")


def _tag_color(name: str) -> Color | None:
    if name.startswith("#"):
        return (int(name[1:3], 16), int(name[3:5], 16), int(name[5:7], 16))
    return colors.NAMED.get(name)


def parse(text: str, default: Color = colors.FG) -> list[Span]:
    spans: list[Span] = []
    stack = [default]
    pos = 0
    for m in _TAG_RE.finditer(text):
        closing, name = m.group(1), m.group(2)
        if closing and not name:
            if m.start() > pos:
                spans.append((text[pos : m.start()], stack[-1]))
            if len(stack) > 1:
                stack.pop()
            pos = m.end()
            continue
        color = _tag_color(name) if name and not closing else None
        if color is None:
            continue  # not a tag we know; leave it in the text
        if m.start() > pos:
            spans.append((text[pos : m.start()], stack[-1]))
        stack.append(color)
        pos = m.end()
    if pos < len(text):
        spans.append((text[pos:], stack[-1]))
    return [s for s in spans if s[0]]


def plain(text: str) -> str:
    return "".join(s for s, _ in parse(text))


def length(text: str) -> int:
    return len(plain(text))


def wrap(text: str, width: int, default: Color = colors.FG) -> list[list[Span]]:
    """Word-wrap marked-up text into lines of coloured spans. Honors newlines."""
    width = max(1, width)
    lines: list[list[Span]] = []
    for paragraph in text.split("\n"):
        spans = parse(paragraph, default)
        # Break into words (keeping colour), then fill lines greedily.
        words: list[list[Span]] = [[]]
        for chunk, color in spans:
            parts = re.split(r"( )", chunk)
            for part in parts:
                if part == " ":
                    words.append([])
                elif part:
                    words[-1].append((part, color))
        line: list[Span] = []
        line_len = 0
        for word in words:
            wlen = sum(len(s) for s, _ in word)
            if wlen == 0:
                if line_len and line_len < width:
                    line.append((" ", default))
                    line_len += 1
                continue
            needed = wlen + (1 if line_len else 0)
            if line_len and line_len + needed > width:
                lines.append(_rstrip(line))
                line, line_len = [], 0
            if line_len:
                line.append((" ", default))
                line_len += 1
            # Hard-split words longer than a whole line.
            while wlen > width:
                head, word = _split_word(word, width - line_len)
                line.extend(head)
                lines.append(line)
                line, line_len = [], 0
                wlen = sum(len(s) for s, _ in word)
            line.extend(word)
            line_len += wlen
        lines.append(_rstrip(line))
    return lines


def _rstrip(line: list[Span]) -> list[Span]:
    while line and line[-1][0].strip() == "":
        line = line[:-1]
    return line


def _split_word(word: list[Span], n: int) -> tuple[list[Span], list[Span]]:
    head: list[Span] = []
    rest: list[Span] = []
    count = 0
    for text, color in word:
        if count >= n:
            rest.append((text, color))
        elif count + len(text) <= n:
            head.append((text, color))
            count += len(text)
        else:
            cut = n - count
            head.append((text[:cut], color))
            rest.append((text[cut:], color))
            count = n
    return head, rest
