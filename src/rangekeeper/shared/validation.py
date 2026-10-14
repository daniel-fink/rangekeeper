"""Domain-independent semantic invariants and validation orchestration.

These checks raise ContractError; Python argument guards in ``validate`` raise
TypeError/ValueError instead. Callers own collection scope and validation order.
This module imports no Model, Specification, Run, solver, or storage behavior.
"""

from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import TypeVar, cast
from uuid import UUID

from rangekeeper.schema.runtime import Record
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import ContractError

K = TypeVar("K", bound=Hashable)


def require(
    condition: object,
    message: str,
    *,
    code: str = "semantic.contract",
    path: str = "",
) -> None:
    """Raise ContractError with diagnostic context when a condition is false."""
    if not condition:
        raise ContractError(message, code=code, path=path)


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
        if not isinstance(node, (Mapping, list, tuple)):
            return
        require(
            id(node) not in active,
            "cyclic containment",
            code="semantic.containment",
            path=current,
        )
        active.add(id(node))
        children: Iterable[tuple[object, object]]
        if isinstance(node, Mapping):
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


def require_declarations(documents):
    """Check declaration identities through schema slots, excluding opaque payloads."""
    from rangekeeper.schema.index import walk_data

    identities = set()
    for kind, data in documents:
        for record, path in walk_data(kind, data):
            if "id" in record:
                identity = record["id"]
                require(
                    identity not in identities,
                    f"duplicate identity: {identity}",
                    code="semantic.identity",
                    path=path + "/id",
                )
                identities.add(identity)
    return identities


def _document_id(data) -> UUID | None:
    try:
        return UUID(data["metadata"]["id"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def checked_record(kind, value, label, issues):
    """Retain one structurally validated record and contextualize boundary failures."""
    from rangekeeper.schema.records import _TYPES
    from rangekeeper.shared.errors import ValidationError

    if isinstance(value, Record):
        if value._kind == kind:
            return value
        issues.append(
            Issue(
                "structure.kind", f"expected {kind}, received {value._kind}", path=label
            )
        )
        return None
    try:
        return _TYPES[kind].from_data(value)
    except ValidationError as error:
        issues.extend(
            Issue(issue.code, issue.message, _document_id(value), label + issue.path)
            for issue in error.report.issues
        )
    except (ValueError, TypeError) as error:
        issues.append(Issue("structure.json", str(error), _document_id(value), label))
    return None


def checked(
    kind: str,
    value: Record | Mapping[str, object],
    label: str,
    issues: list[Issue],
) -> dict:
    """Expose one detached representation from the shared structural preparation."""
    record = checked_record(kind, value, label, issues)
    return record.to_data() if record is not None else {}


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
            issues.append(
                Issue(
                    error.code,
                    str(error),
                    error.document_id or _document_id(document),
                    error.path,
                )
            )
    return ValidationReport(tuple(issues))


def validate_known_reference_types(root: Record, *, index) -> None:
    """Check locally resolvable reference types without requiring external targets.

    Partial Specifications can point outside their declaration scope. A target
    already declared locally cannot masquerade as another record kind.
    Complete Model/composition validation owns reference existence checks.
    """
    from rangekeeper.schema.index import walk
    from rangekeeper.schema.runtime import Record
    from rangekeeper.schema.validation import _slot_map
    from uuid import UUID

    from rangekeeper.schema.records import _TYPES, Reference, Value, Movement

    for record, _, path in walk(root):
        for name, field in _slot_map(record._kind).items():
            types = tuple(
                _TYPES[option["kind"]]
                for option in field["options"]
                if option["category"] == "uuid" and option["kind"] in _TYPES
            )
            if isinstance(record, Reference) and name == "target":
                types = (Value, Movement)
            if not types:
                continue
            value = getattr(record, name)
            entries = enumerate(value) if isinstance(value, tuple) else ((None, value),)
            for position, identity in entries:
                if isinstance(identity, UUID) and identity in index.records:
                    actual = index.records[identity]
                    expected = ", ".join(kind.__name__ for kind in types)
                    require(
                        isinstance(actual, types),
                        f"{identity} targets {actual._kind}; expected {expected}",
                        code="reference.kind",
                        path=f"{path}/{name}"
                        + (f"/{position}" if position is not None else ""),
                    )
