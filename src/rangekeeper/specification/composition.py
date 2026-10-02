"""Immutable additive views over pinned Specification contributions."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from .._schema.records import Specification as SpecificationRecord
from .._schema.validation import document_version
from .._validation import bounded
from ..errors import IdentityConflictError, ReferenceTypeError
from ..references import SpecificationResolver
from ._composition import compose_specification
from .specification import Specification


@dataclass(frozen=True, slots=True, init=False)
class Composition:
    """Derived immutable requirements, not a saved revision or an execution result.

    Construct with ``compose``. Sources map semantic requirement paths (field plus
    target UUID, or setting name) to contributor revision UUIDs. The whole ordered
    objectives list has one contributor. No new metadata or identity is minted.
    """

    root_id: UUID
    model_id: UUID | None
    contributors: tuple[UUID, ...]
    requirements: SpecificationRecord
    sources: Mapping[tuple[str, ...], UUID]
    contributions: tuple[Specification, ...]

    def __init__(self) -> None:
        raise TypeError("construct a Composition with compose(root, resolver=...)")

    def __repr__(self) -> str:
        return f"Composition(root_id={self.root_id!r}, model_id={self.model_id!r}, contributors={len(self.contributors)})"


def compose(root: Specification, *, resolver: SpecificationResolver) -> Composition:
    """Resolve includes once and accumulate requirements without overrides or writes.

    Partial compositions may lack a Model pin. Independent duplicate requirements,
    cycles, wrong kinds and conflicting Model pins fail. A batch cannot be composed
    into one investigation; its case boundaries are deliberately retained for Run work.
    """
    if not isinstance(root, Specification):
        raise TypeError("root must be a Specification")
    documents = {root.id: root}
    pending = [root]
    while pending:
        current = pending.pop()
        # Resolve both kinds of edges so the shared checker can diagnose illegal
        # batch inclusion/cycles using the same catalogue as conformance tests.
        for identity in (current.record.includes or ()) + (current.record.cases or ()):
            if identity in documents:
                continue
            found = resolver.load_specification(identity)
            if not isinstance(found, Specification):
                raise ReferenceTypeError(
                    f"{identity} did not resolve to a Specification"
                )
            if found.id != identity:
                raise IdentityConflictError(
                    f"resolver returned {found.id} for {identity}"
                )
            documents[identity] = found
            pending.append(found)
    result = None

    def check():
        nonlocal result
        result = compose_specification(
            root.to_data(),
            {str(key): value.to_data() for key, value in documents.items()},
            document_version("Specification"),
        )

    bounded([], check, document=root.to_data()).raise_if_invalid()
    assert result is not None  # The shared check either produced a result or raised.
    record = SpecificationRecord.from_data(result.effective)
    composition = object.__new__(Composition)
    object.__setattr__(composition, "root_id", root.id)
    object.__setattr__(composition, "model_id", record.model)
    object.__setattr__(
        composition,
        "contributors",
        tuple(UUID(doc["metadata"]["id"]) for doc in result.contributors),
    )
    object.__setattr__(composition, "requirements", record)
    object.__setattr__(
        composition,
        "sources",
        MappingProxyType(
            {path: UUID(identity) for path, identity in result.sources.items()}
        ),
    )
    object.__setattr__(
        composition,
        "contributions",
        tuple(documents[identity] for identity in composition.contributors),
    )
    return composition
