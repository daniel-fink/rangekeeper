"""Rewrite Markdown, notebooks and configuration text."""

from __future__ import annotations

import json
import re

import libcst as cst

from .python import Context, Locations, PythonRewriter, rewrite_text
from .report import Change

FENCE = re.compile(
    r"^(?P<indent>[ \t]{0,3})(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)\n", re.MULTILINE
)
PYTHON_INFO = frozenset({"python", "py", "python3", "pycon", "ipython", "{code-cell}"})
SHORT = "rk"


class TextRewriter:
    """Rewrite files that are not Python modules."""

    def __init__(self, python: PythonRewriter, locations: Locations) -> None:
        self.python = python
        self.resolver = python.resolver
        self.locations = locations

    def _plain(
        self, text: str, path: str, line: int, *, short: str = ""
    ) -> tuple[str, list[Change]]:
        new = rewrite_text(text, self.resolver, self.locations, short=short)
        if new == text:
            return text, []
        return new, _line_changes(path, line, text, new)

    def _code(
        self, code: str, path: str, line: int, uses: bool
    ) -> tuple[str, list[Change]]:
        try:
            new, changes = self.python.rewrite(
                code, Context(path=path, uses_package=uses)
            )
        except cst.ParserSyntaxError:
            return self._plain(code, path, line, short=SHORT)
        return new, [
            Change(c.path, c.line + line - 1 if c.line else line, c.kind, c.detail)
            for c in changes
        ]

    def markdown(
        self, text: str, path: str, *, line: int = 1
    ) -> tuple[str, list[Change]]:
        """Rewrite prose and Python code blocks in Markdown."""
        uses = self.resolver.package in text or f"{SHORT}." in text
        out: list[str] = []
        changes: list[Change] = []
        position = 0
        while True:
            match = FENCE.search(text, position)
            if match is None:
                break
            closing = re.compile(
                rf"^[ \t]{{0,3}}{re.escape(match['fence'][0])}{{{len(match['fence'])},}}[ \t]*$",
                re.MULTILINE,
            )
            close = closing.search(text, match.end())
            if close is None:
                break
            prose = text[position : match.start()]
            start_line = line + text.count("\n", 0, position)
            new, found = self._plain(prose, path, start_line, short=SHORT)
            out.append(new)
            changes += found
            out.append(match.group(0))
            body = text[match.end() : close.start()]
            body_line = line + text.count("\n", 0, match.end())
            info = match["info"].strip().split()
            if info and info[0].lower() in PYTHON_INFO:
                new, found = self._code(body, path, body_line, uses)
            else:
                new, found = self._plain(body, path, body_line, short=SHORT)
            out.append(new)
            changes += found
            out.append(text[close.start() : close.end()])
            position = close.end()
        new, found = self._plain(
            text[position:], path, line + text.count("\n", 0, position), short=SHORT
        )
        out.append(new)
        changes += found
        return "".join(out), changes

    def notebook(self, text: str, path: str) -> tuple[str, list[Change]]:
        """Rewrite the code and Markdown cells of a notebook."""
        data = json.loads(text)
        uses = self.resolver.package in text
        changes: list[Change] = []
        for number, cell in enumerate(data.get("cells", []), start=1):
            source = cell.get("source", "")
            joined = "".join(source) if isinstance(source, list) else source
            where = f"{path}#cell{number}"
            if cell.get("cell_type") == "code":
                new, found = self._code(joined, where, 1, uses)
            elif cell.get("cell_type") == "markdown":
                new, found = self.markdown(joined, where)
            else:
                continue
            if new != joined:
                cell["source"] = (
                    new.splitlines(keepends=True) if isinstance(source, list) else new
                )
                changes += found
        if not changes:
            return text, []
        indent = 1
        match = re.match(r'\{\n( +)"', text)
        if match:
            indent = len(match[1])
        return json.dumps(data, indent=indent, ensure_ascii=False) + (
            "\n" if text.endswith("\n") else ""
        ), changes

    def config(self, text: str, path: str) -> tuple[str, list[Change]]:
        """Rewrite dotted names and paths in configuration text."""
        return self._plain(text, path, 1)


def _line_changes(path: str, first: int, old: str, new: str) -> list[Change]:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    changes = []
    for i, (a, b) in enumerate(zip(old_lines, new_lines, strict=False)):
        if a != b:
            changes.append(
                Change(path, first + i, "text", f"{a.strip()} -> {b.strip()}")
            )
    return changes
