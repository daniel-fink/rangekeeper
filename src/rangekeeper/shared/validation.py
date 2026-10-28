"""Domain-independent semantic invariants and validation orchestration.

Helpers that read schema records are in ``rangekeeper.schema.validation``.

These checks raise ContractError; Python argument guards in ``validate`` raise
TypeError/ValueError instead. Callers own collection scope and validation order.
This module imports no Model, Specification, Run, solver, or storage behavior.
"""

from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any, TypeVar
from uuid import UUID

from rangekeeper.shared import pointer
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import ContractError

K = TypeVar("K", bound=Hashable)


def require(
    condition: object,
    message: str,
    *,
    code: Code = Code.CONTRACT,
    path: str = "",
    targets: Iterable[UUID] = (),
    values: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> None:
    """Raise ContractError with diagnostic context when a condition is false."""
    if not condition:
        raise ContractError(
            message,
            code=code,
            path=path,
            targets=targets,
            values=values,
            evidence=evidence,
        )


def require_unique(
    records: Iterable[Mapping[str, object]],
    field: str,
    label: str,
    *,
    path: str = "",
) -> None:
    """Require distinct non-null field values within this one owning collection.

    Missing/None values are ignored; comparison remains exact and case-sensitive.
    Structural validation must establish hashable values first. Inputs are read
    once and never changed. ``path`` is the collection's JSON Pointer.
    """
    seen = set()
    for index, record in enumerate(records):
        value = record.get(field)
        if value is not None:
            require(
                value not in seen,
                f"duplicate {label}: {value}",
                code=Code.UNIQUE,
                path=pointer.child(path, index, field),
                values={"field": field, "value": value},
            )
            seen.add(value)


def require_new(
    identities: set,
    identity: Hashable,
    *,
    label: str = "identity",
    path: str = "",
) -> None:
    """Add one declared identity to ``identities``; reject an identity seen before.

    This is the one duplicate-identity check. Callers own the scope of
    ``identities``, for example one document or one composition.
    """
    require(
        identity not in identities,
        f"duplicate {label}: {identity}",
        code=Code.IDENTITY,
        path=path,
        values={"identity": identity},
    )
    identities.add(identity)


def require_acyclic(
    edges: Mapping[K, Iterable[K]],
    label: str,
    *,
    path: str = "",
) -> None:
    """Reject cycles in directed edges without requiring every target to be a key.

    A shared descendant is allowed. Missing targets are terminal nodes; reference
    existence is a separate rule. No input collection is changed.
    """
    visiting: set[K] = set()
    complete: set[K] = set()

    def visit(node: K) -> None:
        require(node not in visiting, f"{label} cycle", code=Code.CYCLE, path=path)
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
    identities: set[Hashable] = set()
    active: set[int] = set()

    def visit(node, current: str) -> None:
        if not isinstance(node, (Mapping, list, tuple)):
            return
        require(
            id(node) not in active,
            "cyclic containment",
            code=Code.CONTAINMENT,
            path=current,
        )
        active.add(id(node))
        children: Iterable[tuple[object, object]]
        if isinstance(node, Mapping):
            if "id" in node:
                require_new(identities, node["id"], path=current + "/id")
            children = node.items()
        else:
            children = enumerate(node)
        for key, value in children:
            visit(value, pointer.child(current, key))
        active.remove(id(node))

    visit(document, path)


def _document_id(data) -> UUID | None:
    try:
        return UUID(data["metadata"]["id"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def bounded(
    issues: list[Issue],
    operation: Callable[[], object],
    *,
    document=None,
) -> ValidationReport:
    """Run one dependent stage only when prior checks passed; retain its first error.

    Only ContractError is caught. Programming errors remain visible, and checks
    that need missing prerequisites are never run after an earlier stage fails.
    """
    if not issues:
        try:
            operation()
        except ContractError as error:
            issues.append(Issue.from_error(error, document_id=_document_id(document)))
    return ValidationReport(tuple(issues))
