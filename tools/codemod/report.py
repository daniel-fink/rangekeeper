"""Record what a codemod run changes and what it leaves for review."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field

from .renamemap import Entry

# Kinds of change that need a person to act. The other kinds are applied.
REVIEW_KINDS = frozenset({"review", "removed"})


@dataclass(frozen=True)
class Change:
    """One change, or one use that needs review, at a source location."""

    path: str
    line: int
    kind: str
    detail: str


@dataclass
class Report:
    """The result of one run."""

    changes: list[Change] = field(default_factory=list)
    moves: list[tuple[str, str]] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    skipped: tuple[Entry, ...] = ()
    errors: list[str] = field(default_factory=list)

    @property
    def applied(self) -> list[Change]:
        """Return the changes that the run makes."""
        return [c for c in self.changes if c.kind not in REVIEW_KINDS]

    @property
    def review(self) -> list[Change]:
        """Return the uses that need a person to act."""
        return [c for c in self.changes if c.kind in REVIEW_KINDS]

    @property
    def changed(self) -> bool:
        """Return true when the run changes any file."""
        return bool(self.applied or self.moves or self.created)

    def summary(self, *, verbose: bool = False) -> str:
        """Return a readable summary."""
        lines = []
        files = {c.path for c in self.applied}
        lines.append(
            f"{len(self.moves)} files moved, {len(self.created)} files created, "
            f"{len(self.applied)} changes in {len(files)} files, "
            f"{len(self.review)} uses to review."
        )
        counts = Counter(c.kind for c in self.changes)
        if counts:
            lines.append(
                "By kind: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items()))
            )
        if self.moves:
            lines.append("")
            lines.append("Moved:")
            lines.extend(f"  {old} -> {new}" for old, new in self.moves)
        if self.created:
            lines.append("")
            lines.append("Created:")
            lines.extend(f"  {path}" for path in self.created)
        if verbose and self.applied:
            lines.append("")
            lines.append("Changes:")
            lines.extend(
                f"  {c.path}:{c.line}: {c.kind}: {c.detail}" for c in self.applied
            )
        if self.review:
            lines.append("")
            lines.append("Review:")
            lines.extend(
                f"  {c.path}:{c.line}: {c.kind}: {c.detail}" for c in self.review
            )
        if self.skipped:
            lines.append("")
            lines.append("Not applied:")
            for entry in self.skipped:
                lines.append(f"  [{entry.status}{_requires(entry)}] {_describe(entry)}")
        if self.errors:
            lines.append("")
            lines.append("Errors:")
            lines.extend(f"  {e}" for e in self.errors)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Return the report as JSON."""
        return json.dumps(
            {
                "moves": self.moves,
                "created": self.created,
                "changes": [asdict(c) for c in self.applied],
                "review": [asdict(c) for c in self.review],
                "skipped": [
                    {"kind": type(e).__name__, **asdict(e)} for e in self.skipped
                ],
                "errors": self.errors,
            },
            indent=2,
        )


def _requires(entry: Entry) -> str:
    return f", requires {'+'.join(entry.requires)}" if entry.requires else ""


def _describe(entry: Entry) -> str:
    data = asdict(entry)
    old = data.get("old") or ".".join(
        x
        for x in (
            data.get("module") or data.get("owner") or data.get("callable"),
            data.get("name"),
        )
        if x
    )
    new = data.get("new") or data.get("new_module") or data.get("new_name") or "?"
    reason = entry.pending or entry.note
    return f"{old or data.get('topic')} -> {new}" + (f" ({reason})" if reason else "")
