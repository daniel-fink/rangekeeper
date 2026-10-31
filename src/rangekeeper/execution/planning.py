"""Stage 1: resolve the immutable case graph before any stage runs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from rangekeeper.model import Model
from rangekeeper.run import Run
from rangekeeper.run.documents import Documents
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    IdentityConflictError,
    ReferenceTypeError,
    ValidationError,
)
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Composition, Specification
from rangekeeper.specification.composition import collect_specifications, compose


@dataclass(frozen=True, kw_only=True)
class Cases:
    """The resolved case graph of one root Specification.

    ``documents`` holds the root and each reachable include and case.
    ``models`` holds each Model revision that a document pins. ``compositions``
    holds the composition of each leaf case that composes, and ``failures``
    the ValidationError of each leaf case that does not, so that the leaf can
    record its own Run evidence. Each leaf case is in one of the two.

    A Cases is also a resolver: it returns its own revisions and reads other
    identities from ``resolver``. It holds no cache that changes after
    construction.
    """

    root: Specification
    documents: Mapping[UUID, Specification]
    models: Mapping[UUID, Model]
    compositions: Mapping[UUID, Composition]
    failures: Mapping[UUID, ValidationError]
    resolver: DocumentResolver
    _lookup: Documents = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Its own revisions first, else the resolver: one lookup, made once.
        lookup = Documents(
            (*self.models.values(), *self.documents.values()), fallback=self.resolver
        )
        object.__setattr__(self, "_lookup", lookup)

    def load_model(self, id: UUID) -> Model:
        """Return a resolved Model revision, else load it from the resolver."""
        return self._lookup.load_model(id)

    def load_specification(self, id: UUID) -> Specification:
        """Return a resolved Specification, else load it from the resolver."""
        return self._lookup.load_specification(id)

    def load_run(self, id: UUID) -> Run:
        """Load a Run from the resolver."""
        return self._lookup.load_run(id)


def resolve_cases(*, specification: Specification, resolver: DocumentResolver) -> Cases:
    """Resolve the case graph of ``specification`` and compose each leaf once.

    Missing or wrong-kind revisions, cycles and a batch Model pin that a leaf
    contradicts raise. A leaf whose composition fails keeps its
    ValidationError in ``failures``. Nothing is written.
    """
    if not isinstance(specification, Specification):
        raise TypeError("specification must be a Specification")
    documents, catalogue = collect_specifications(specification, resolver=resolver)
    models: dict[UUID, Model] = {}
    for current in documents.values():
        identity = current.record.model
        if identity is None or identity in models:
            continue
        model = resolver.load_model(identity)
        if not isinstance(model, Model):
            raise ReferenceTypeError("input reference did not resolve to a Model")
        if model.id != identity:
            raise IdentityConflictError("input resolver returned a different revision")
        models[identity] = model
    graph = Cases(
        root=specification,
        documents=MappingProxyType(documents),
        models=MappingProxyType(models),
        compositions=MappingProxyType({}),
        failures=MappingProxyType({}),
        resolver=resolver,
    )
    compositions: dict[UUID, Composition] = {}
    failures: dict[UUID, ValidationError] = {}

    def check_pins(current: Specification, pins: tuple[UUID, ...] = ()) -> None:
        if current.record.cases:
            pins += (current.record.model,) if current.record.model is not None else ()
            for id in current.record.cases:
                check_pins(documents[id], pins)
            return
        if current.id not in compositions and current.id not in failures:
            try:
                compositions[current.id] = compose(
                    current,
                    resolver=graph,
                    documents=documents,
                    catalogue=catalogue,
                )
            except ValidationError as error:
                failures[current.id] = error
        view = compositions.get(current.id)
        if view is None:
            return  # the leaf records its conflicting composition
        if view.model_id is not None and any(pin != view.model_id for pin in pins):
            raise ValidationError(
                ValidationReport(
                    (
                        Issue(
                            Code.BATCH_MODEL,
                            "batch input Model assertion mismatch",
                            current.id,
                        ),
                    )
                )
            )

    check_pins(specification)
    return Cases(
        root=specification,
        documents=MappingProxyType(documents),
        models=MappingProxyType(models),
        compositions=MappingProxyType(compositions),
        failures=MappingProxyType(failures),
        resolver=resolver,
    )
