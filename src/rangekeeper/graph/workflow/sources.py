"""Resolve declared source editions without depending on a file format."""

import hashlib
from pathlib import Path

from rangekeeper.graph.operation import _Failure


def resolve_file(root: Path, filenames: tuple[str, ...], source_key: str) -> Path:
    """Allow equivalent filename candidates, but never choose between editions."""
    candidates = [root / name for name in filenames if (root / name).is_file()]
    if not candidates:
        raise _Failure("missing_source", f"No declared file found for {source_key}")
    if any(not p.resolve().is_relative_to(root) for p in candidates):
        raise _Failure("source_outside_root", "Resolved source escapes input_root")
    if len({hashlib.sha256(p.read_bytes()).hexdigest() for p in candidates}) != 1:
        raise _Failure(
            "ambiguous_source",
            f"Declared filenames contain different editions for {source_key}",
        )
    return candidates[0]
