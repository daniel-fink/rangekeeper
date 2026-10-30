"""Run the stages for each case: pure ``solve`` and publishing ``execute``."""

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import cast
from uuid import UUID

from rangekeeper.execution import assembly
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.planning import Cases, resolve_cases
from rangekeeper.model import Model
from rangekeeper.run import Run
from rangekeeper.run.validation import (
    Prerequisites,
    mark_validated,
    validate_executed,
)
from rangekeeper.shared.errors import MissingReferenceError
from rangekeeper.shared.references import DocumentResolver, SpecificationResolver
from rangekeeper.shared.store import RecordStore
from rangekeeper.specification import Specification


def solve(
    *,
    specification: Specification,
    resolver: DocumentResolver | None = None,
    config: ExecutionConfig | None = None,
) -> Outcome:
    """Run every stage for each case of ``specification``; write nothing.

    Without ``resolver``, the solve resolves the documents that made the
    Specification: the Model that ``model.specify()`` pinned, the
    Specification itself, and what its own resolver supplies. A Specification
    read from data has none of them; pass ``resolver`` for it. ``resolver``
    supplies the exact revisions that the Specification names.

    Each leaf case gives a finalized Run, even when it fails; repeated cases
    are separate attempts. Each Run is validated once, in one validation of
    the whole tree with the unstored outputs and case Runs laid over the
    resolver. Without ``config``, the defaults of ExecutionConfig apply.

    Missing references, invalid batch graphs and programming errors raise.
    Expected formulation and numerical failures are evidence in the Run. A
    feasible Run certifies only the documented scalar slice and its independent
    verification, not uniqueness or optimality.
    """
    if resolver is None:
        resolver = Pinned(specification)
    return _run(specification, resolver, config, store=None)[0]


class Pinned:
    """Resolve the documents that made a Specification, without a store.

    It returns the Specification itself and the Model revision that the
    Specification keeps from ``model.specify()``. It reads other identities
    from the Specification's own resolver, when it has one, and then from
    ``fallback``, when it is given: ``execute`` gives its store. Any other
    identity raises MissingReferenceError.
    """

    def __init__(
        self,
        specification: Specification,
        *,
        fallback: DocumentResolver | None = None,
    ) -> None:
        if not isinstance(specification, Specification):
            raise TypeError("specification must be a Specification")
        self.specification = specification
        # The facade keeps these for chained calls; they are not saved.
        self.model = specification.model
        self.resolver = specification.resolver
        self.fallback = fallback

    def load_model(self, id: UUID) -> Model:
        """Return the pinned Model, else load it from the resolvers."""
        if self.model is not None and self.model.id == id:
            return self.model
        return _first(
            self._sources(),
            load=lambda source: source.load_model(id),
            missing=lambda: self._missing(id, "Model"),
        )

    def load_specification(self, id: UUID) -> Specification:
        """Return the Specification itself, else load it from the resolvers."""
        if id == self.specification.id:
            return self.specification
        return _first(
            self._sources(),
            load=lambda source: source.load_specification(id),
            missing=lambda: self._missing(id, "Specification"),
        )

    def load_run(self, id: UUID) -> Run:
        """Load a Run from the resolvers that can load Runs."""
        sources = [
            cast(DocumentResolver, source)
            for source in self._sources()
            if hasattr(source, "load_run")
        ]
        return _first(
            sources,
            load=lambda source: source.load_run(id),
            missing=lambda: self._missing(id, "Run"),
        )

    def _sources(self) -> list[SpecificationResolver]:
        """Return the Specification's own resolver, then the fallback, when given."""
        return [
            source for source in (self.resolver, self.fallback) if source is not None
        ]

    @staticmethod
    def _missing(id: UUID, kind: str) -> MissingReferenceError:
        return MissingReferenceError(
            id,
            kind=kind,
            where="the documents that made the Specification; pass resolver=",
        )


def _first[S, D](
    sources: Sequence[S],
    *,
    load: Callable[[S], D],
    missing: Callable[[], MissingReferenceError],
) -> D:
    """Return what the first source that holds a revision loads.

    A source that does not hold it raises MissingReferenceError; the error of
    the last source raises, or ``missing()`` when there is no source.
    """
    if not sources:
        raise missing()
    for source in sources[:-1]:
        try:
            return load(source)
        except MissingReferenceError:
            continue
    return load(sources[-1])


def execute(
    *,
    specification: Specification,
    store: RecordStore,
    config: ExecutionConfig | None = None,
) -> Outcome:
    """Solve ``specification``, then publish its documents and its result to ``store``.

    The solve resolves the documents that made the Specification, as ``solve``
    does without a resolver, and then reads ``store``. Publication puts each
    input Model, include and case Specification that ``store`` does not hold,
    then the Specification, then for each case its outputs and then its Run,
    cases before their batch. So ``store`` can start empty, and it then holds
    everything that its Runs reference.

    Each Run is validated once, against ``store``, before anything is put;
    ``store.put`` does not repeat that validation. Nothing is put when solving
    or validation raises. There is no multi-document transaction: a storage
    error can leave accepted outputs or completed case Runs. Caller-owned
    input records never change.
    """
    resolver = Pinned(specification, fallback=store)
    outcome, cases = _run(specification, resolver, config, store=store)
    _publish_inputs(store, cases)
    for item in outcome.walk():
        if not item.cases:
            for model in item.outputs:
                store.put(model)
        store.put(item.run)
    return outcome


def _run(
    specification: Specification,
    resolver: DocumentResolver,
    config: ExecutionConfig | None,
    *,
    store: RecordStore | None,
) -> tuple[Outcome, Cases]:
    if not isinstance(specification, Specification):
        raise TypeError("specification must be a Specification")
    config = ExecutionConfig() if config is None else config
    backend = (
        registry.get(config.backend)
        if isinstance(config.backend, str)
        else config.backend
    )
    cases = resolve_cases(specification=specification, resolver=resolver)
    scopes: dict[UUID, object] = {}
    outcome = _case(
        specification, cases=cases, config=config, backend=backend, scopes=scopes
    )
    tree = tuple(outcome.walk())
    overlay = assembly.Overlay(
        resolver=cases,
        models=(model for item in tree for model in item.outputs),
        runs=(item.run for item in tree),
    )
    prerequisites = Prerequisites(compositions=cases.compositions, scopes=scopes)
    # A store validates with the unit system of the input Model; so does execute.
    validate_executed(
        outcome.run,
        resolver=overlay,
        units=config.units if store is None else None,
        prerequisites=prerequisites,
    ).raise_if_invalid()
    if store is not None:
        for item in tree:
            mark_validated(item.run, store, _unstored(item, cases))
    return outcome, cases


def _publish_inputs(store: RecordStore, cases: Cases) -> None:
    """Put the inputs that ``store`` lacks: Models, then Specifications, then the root."""
    for model in cases.models.values():
        if not _holds(store.load_model, model.id):
            store.put(model)
    for document in _inputs(cases.root, cases):
        if not _holds(store.load_specification, document.id):
            store.put(document)
    store.put(cases.root)


def _inputs(specification: Specification, cases: Cases) -> list[Specification]:
    """Return the includes and cases of a Specification, each before its user."""
    found = []
    for identity in (
        *(specification.record.includes or ()),
        *(specification.record.cases or ()),
    ):
        document = cases.documents[identity]
        found.extend(_inputs(document, cases))
        found.append(document)
    return found


def _holds(load: Callable[[UUID], object], id: UUID) -> bool:
    """Return whether ``load`` finds the revision ``id`` in a store."""
    try:
        load(id)
    except MissingReferenceError:
        return False
    return True


def _unstored(outcome: Outcome, cases: Cases) -> set[UUID]:
    """Return the revisions that validating ``outcome.run`` can read from no store.

    They are the documents that made the Specification and the unstored
    outputs and case Runs; ``execute`` puts each of them before the Run.
    """
    documents = set(cases.models) | set(cases.documents)
    for item in outcome.walk():
        documents.update(model.id for model in item.outputs)
        if item is not outcome:
            documents.add(item.run.id)
    return documents


def _case(
    specification: Specification,
    *,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
    scopes: dict[UUID, object],
) -> Outcome:
    # A case's key is the name of its Specification.
    key = specification.metadata.name
    outcome = _attempt(
        specification, cases=cases, config=config, backend=backend, scopes=scopes
    )
    return outcome if key is None else replace(outcome, key=key)


def _attempt(
    specification: Specification,
    *,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
    scopes: dict[UUID, object],
) -> Outcome:
    if specification.record.cases:
        return assembly.assemble_batch(
            specification=specification,
            cases=tuple(
                _case(
                    cases.documents[id],
                    cases=cases,
                    config=config,
                    backend=backend,
                    scopes=scopes,
                )
                for id in specification.record.cases
            ),
        )
    attempt = Attempt(
        specification,
        cases.failures.get(specification.id) or cases.compositions[specification.id],
        config=config,
        backend=backend,
        resolver=cases,
    )
    outcome = attempt.execute()
    validation = attempt.validation
    if validation is not None and validation.report.valid and validation._scope:
        scopes[specification.id] = validation._scope
    return outcome
