"""One-call document files: ``load`` reads a document and ``save`` writes one (#295).

A document file is JSON. It holds one document (a Model, a Specification, a Run
or market paths) with its kind, and the documents that it depends on, so that a
loaded document can be read on its own:

```json
{
  "kind": "Specification",
  "document": {...},
  "documents": [{"kind": "Model", "document": {...}}]
}
```

``documents`` is absent when the document depends on none, as for a Model or
market paths; the file is then the envelope that ``DirectoryStore`` writes. A
loaded Specification keeps its Model and the other documents of the file as its
resolver, so ``rk.execution.solve`` resolves them.
"""

import json as _json
from collections.abc import Mapping, Sequence
from pathlib import Path

from rangekeeper.io._amounts import amounts, strict
from rangekeeper.io._atomic import write_new
from rangekeeper.io._document import KINDS, Document, trusted
from rangekeeper.io.json import _parse
from rangekeeper.run.documents import Documents, closure, require_same
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.shared.errors import DecodeError
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.specification.composition import collect_specifications
from rangekeeper.specification.specification import Specification

__all__ = ["load", "save"]

# The keys of one document in a file, and of the file itself.
_ENTRY = frozenset({"kind", "document"})
_FILE = _ENTRY | {"documents"}


def save(
    *,
    document: Document,
    path: Path | str,
    resolver: SpecificationResolver | None = None,
) -> Path:
    """Write a document, and each document that it depends on, to a new JSON file.

    A Specification brings the documents that it keeps: its Model, and the
    cases that ``cases`` made, with their Models; its own resolver, or
    ``resolver``, gives the others, such as its includes. Another document
    takes its dependencies from ``resolver``: a Run its Specification and its
    outputs. A missing dependency raises MissingReferenceError and writes
    nothing.

    Missing parent folders are made. The file is written atomically and never
    replaced: when ``path`` holds the same document already, ``save`` returns
    its path; another document there raises RevisionConflictError. Return the
    path.
    """
    root = trusted(document)
    found = closure([root], resolver=_kept(root, resolver=resolver))
    text = _encoded(
        root, others=[item for item in found.documents() if item is not root]
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        return write_new(destination, text)
    except FileExistsError:
        require_same(load(path=destination), root)
        return destination


def load(*, path: Path | str) -> Document:
    """Read a document file that ``save`` wrote, and return its document.

    The file gives the kind, so ``load`` takes none. Each document is
    validated as ``rk.io.json.read`` validates it. A Specification keeps its
    Model and the other documents of the file as its resolver, so that
    ``fix``, ``roles`` and ``rk.execution.solve`` find them. Text that is not
    a document file raises DecodeError. A document that the file's document
    needs and the file lacks raises MissingReferenceError, and one that it
    does not need raises DecodeError.
    """
    entry, others = _read(Path(path))
    held = Documents((_decoded(item) for item in others), where=str(path))
    root = _decoded(entry, held=held)
    found = closure([root], resolver=held, where=f"document file {path}")
    if len(found) != len(held) + 1:
        raise DecodeError(
            f"{path} holds documents that its {entry['kind']} does not depend on"
        )
    return root


def _read(path: Path) -> tuple[dict[str, object], list[object]]:
    """Return the document of a file, with its kind, and the other documents."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise DecodeError(str(error)) from error
    data = _parse(text)
    if not isinstance(data, dict) or not _ENTRY <= set(data) <= _FILE:
        raise DecodeError("a document file has a kind, a document and its documents")
    if "documents" not in data:
        return data, []
    others = data.pop("documents")
    if not isinstance(others, list) or not others:
        raise DecodeError("documents is a list of one document or more")
    return data, others


def _kept(root: Document, *, resolver: SpecificationResolver | None) -> Documents:
    """Return the documents that made ``root``, then ``resolver``."""
    where = "the documents that made it; pass resolver="
    if not isinstance(root, Specification):
        return Documents(fallback=resolver, where=where)
    fallback = root.resolver if resolver is None else resolver
    specifications, _ = collect_specifications(
        root, resolver=Documents(fallback=fallback, where=where)
    )
    models = [item.model for item in specifications.values() if item.model is not None]
    return Documents(
        (*specifications.values(), *models), fallback=fallback, where=where
    )


def _encoded(root: Document, *, others: Sequence[Document]) -> str:
    data: dict[str, object] = _entry(root)
    if others:
        data["documents"] = [_entry(item) for item in others]
    return _json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def _entry(document: Document) -> dict[str, object]:
    return {"kind": type(document).__name__, "document": document.to_data()}


def _decoded(entry: object, *, held: Documents | None = None) -> Document:
    """Return the document of one entry of a file; a Specification keeps ``held``."""
    if not isinstance(entry, Mapping) or set(entry) != _ENTRY:
        raise DecodeError("each document of a file has exactly kind and document")
    kind = KINDS.get(entry["kind"]) if isinstance(entry["kind"], str) else None
    if kind is None:
        raise DecodeError(f"unknown document kind {entry['kind']!r}")
    data = amounts(kind.__name__, entry["document"], strict)
    if not isinstance(data, Mapping):
        raise DecodeError("a document is a JSON object")
    if kind is not Specification or held is None:
        return kind.from_data(data=data)
    record = SpecificationRecord.from_data(data)
    model = None if record.model is None else held.load_model(record.model)
    return Specification(record=record, model=model, resolver=held)
