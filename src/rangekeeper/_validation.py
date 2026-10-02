"""Domain-independent semantic invariants and validation orchestration.

These checks raise ContractError; Python argument guards in ``validate`` raise
TypeError/ValueError instead. Callers own collection scope and validation order.
This module imports no Model, Specification, Run, solver, or storage behavior.
"""

from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import TypeVar, cast
from uuid import UUID

from ._records import Record
from ._schema.validation import validate as structure
from .diagnostics import Issue, ValidationReport
from .errors import ContractError

K = TypeVar("K", bound=Hashable)


def require(
    condition: object, message: str, *, code: str = "semantic.contract", path: str = ""
) -> None:
    """Raise ContractError with diagnostic context when a condition is false."""
    if not condition:
        raise ContractError(message, code=code, path=path)


def require_unique(
    records: Iterable[Mapping[str, object]], field: str, label: str, *, path: str = ""
) -> None:
    """Require distinct non-null field values within this one owning collection.

    Missing/None values are ignored; comparison remains exact and case-sensitive.
    Structural validation must establish hashable values first. Inputs are read
    once and never changed. ``path`` is the collection's JSON Pointer.
    """
    seen = set()
    token = field.replace("~", "~0").replace("/", "~1")
    for index, record in enumerate(records):
        value = record.get(field)
        if value is not None:
            require(
                value not in seen,
                f"duplicate {label}: {value}",
                code="semantic.unique",
                path=f"{path}/{index}/{token}",
            )
            seen.add(value)


def require_acyclic(
    edges: Mapping[K, Iterable[K]], label: str, *, path: str = ""
) -> None:
    """Reject cycles in directed edges without requiring every target to be a key.

    A shared descendant is allowed. Missing targets are terminal nodes; reference
    existence is a separate rule. No input collection is changed.
    """
    visiting: set[K] = set()
    complete: set[K] = set()

    def visit(node: K) -> None:
        require(
            node not in visiting, f"{label} cycle", code="semantic.cycle", path=path
        )
        if node in complete:
            return
        visiting.add(node)
        for target in edges.get(node, ()):
            visit(target)
        visiting.remove(node)
        complete.add(node)

    for node in edges:
        visit(node)


def require_ownership(document: object, *, path: str = "") -> None:
    """Reject repeated declarations and containment cycles in a prepared envelope.

    This low-level check treats every dict ``id`` as a declaration. Its caller
    MUST exclude opaque payloads first (for example Claim.content). Typed record
    traversal belongs to the domain index, not this generic dict/list check.
    """
    identities = set()
    active: set[int] = set()

    def visit(node, current: str) -> None:
        if not isinstance(node, (dict, list)):
            return
        require(
            id(node) not in active,
            "cyclic containment",
            code="semantic.containment",
            path=current,
        )
        active.add(id(node))
        children: Iterable[tuple[object, object]]
        if isinstance(node, dict):
            if "id" in node:
                identity = node["id"]
                require(
                    identity not in identities,
                    f"duplicate identity: {identity}",
                    code="semantic.identity",
                    path=current + "/id",
                )
                identities.add(identity)
            children = node.items()
        else:
            children = enumerate(node)
        for key, child in children:
            token = str(key).replace("~", "~0").replace("/", "~1")
            visit(child, current + "/" + token)
        active.remove(id(node))

    visit(document, path)


def _document_id(data) -> UUID | None:
    try:
        return UUID(data["metadata"]["id"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def checked(
    kind: str, value: Record | Mapping[str, object], label: str, issues: list[Issue]
) -> dict:
    """Collect structural issues and return detached schema-normalized data.

    Semantic operations must be gated on the resulting issue list being empty.
    Schema kinds come from generated records; no field schema is duplicated here.
    """
    from ._schema.records import _TYPES

    if isinstance(value, Record):
        if value._kind != kind:
            issues.append(
                Issue(
                    "structure.kind",
                    f"expected {kind}, received {value._kind}",
                    path=label,
                )
            )
        value = value.to_data()
    report = structure(kind, value)
    issues.extend(
        Issue(i.code, i.message, _document_id(value), label + i.path)
        for i in report.issues
    )
    record_type = cast(type[Record], _TYPES[kind])
    return {} if not report.valid else record_type.from_data(value).to_data()


def bounded(
    issues: list[Issue], operation: Callable[[], object], *, document=None
) -> ValidationReport:
    """Run one dependent stage only when prior checks passed; retain its first error.

    Only ContractError is caught. Programming errors remain visible, and checks
    that need missing prerequisites are never run after an earlier stage fails.
    """
    if not issues:
        try:
            operation()
        except ContractError as error:
            issues.append(
                Issue(error.code, str(error), _document_id(document), error.path)
            )
    return ValidationReport(tuple(issues))
