"""Small document-kind dispatch shared by codecs and stores; no field definitions."""

from collections.abc import Mapping
from typing import TypeAlias, TypeVar, cast

from rangekeeper.market.paths import Paths
from rangekeeper.model.model import Model
from rangekeeper.run.documents import require_same as require_same
from rangekeeper.run.run import Run
from rangekeeper.shared.errors import DecodeError
from rangekeeper.shared.references import require_revision as require_revision
from rangekeeper.specification.specification import Specification

Document: TypeAlias = Model | Specification | Run | Paths
D = TypeVar("D", bound=Document)

# Each document facade has the name of its generated record.
KINDS: dict[str, type[Document]] = {
    kind.__name__: kind for kind in (Model, Specification, Run, Paths)
}


def require_kind(kind: object) -> None:
    """Accept an explicit public root facade, excluding derived views and raw records."""
    if kind not in KINDS.values():
        raise TypeError("kind must be Model, Specification, Run or Paths")


def restore(data: object, kind: type[D]) -> D:
    """Construct through the facade, retaining structural/semantic/version errors."""
    require_kind(kind)
    return cast(D, kind.from_data(data=cast(Mapping[str, object], data)))


def trusted(document: Document) -> Document:
    """Return a document that IO writes without validating it again (ADR-011).

    An exact Model, Specification, Run or Paths instance was validated when it was
    built, and it is immutable, so stores and codecs trust it. Data and other
    types are not accepted here; decode data with ``restore``.
    """
    require_kind(type(document))
    return document


def envelope(document: Document) -> dict:
    """Return the store-only kind envelope; codecs never emit this wrapper."""
    return {"kind": type(document).__name__, "document": document.to_data()}


def from_envelope(data: object) -> Document:
    """Decode a closed storage envelope through its declared document factory."""
    if not isinstance(data, dict) or set(data) != {"kind", "document"}:
        raise DecodeError("storage requires exactly kind and document")
    kind = data["kind"]
    if not isinstance(kind, str) or kind not in KINDS:
        raise DecodeError("unknown stored document kind")
    return restore(data["document"], KINDS[kind])
