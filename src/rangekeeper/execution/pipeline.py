"""Run the stages for each case: pure ``solve`` and publishing ``execute``."""

from dataclasses import replace
from uuid import UUID

from rangekeeper.execution import assembly
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.planning import Cases, resolve_cases
from rangekeeper.model import Model
from rangekeeper.run import Prerequisites, Run
from rangekeeper.run import validate as validate_run
from rangekeeper.run.validation import mark_validated
from rangekeeper.shared.errors import MissingReferenceError
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.shared.store import RecordStore
from rangekeeper.specification import Composition, Specification


def solve(
    specification: Specification,
    resolver: DocumentResolver | None = None,
    *,
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
    from the Specification's own resolver, when it has one. Any other identity
    raises MissingReferenceError.
    """

    def __init__(self, specification: Specification) -> None:
        if not isinstance(specification, Specification):
            raise TypeError("specification must be a Specification")
        self.specification = specification
        # The facade keeps these for chained calls; they are not saved.
        self.model = specification.model
        self.resolver = specification.resolver

    def load_model(self, id: UUID) -> Model:
        """Return the pinned Model, else load it from the Specification's resolver."""
        if self.model is not None and self.model.id == id:
            return self.model
        if self.resolver is not None:
            return self.resolver.load_model(id)
        raise self._missing(id, "Model")

    def load_specification(self, id: UUID) -> Specification:
        """Return the Specification itself, else load it from its resolver."""
        if id == self.specification.id:
            return self.specification
        if self.resolver is not None:
            return self.resolver.load_specification(id)
        raise self._missing(id, "Specification")

    def load_run(self, id: UUID) -> Run:
        """Load a Run from the Specification's resolver, when it can load Runs."""
        load_run = getattr(self.resolver, "load_run", None)
        if load_run is None:
            raise self._missing(id, "Run")
        return load_run(id)

    @staticmethod
    def _missing(id: UUID, kind: str) -> MissingReferenceError:
        return MissingReferenceError(
            id,
            kind=kind,
            where="the documents that made the Specification; pass resolver=",
        )


def execute(
    specification: Specification,
    store: RecordStore,
    *,
    config: ExecutionConfig | None = None,
) -> Outcome:
    """Solve ``specification`` with ``store`` as resolver, then publish the result.

    Publication puts each case Specification that ``store`` does not hold,
    then the Specification, then for each case its outputs and then its Run, cases
    before their batch. Each Run is validated once, against
    ``store``, before anything is put; ``store.put`` does not repeat that
    validation. Nothing is put when solving or validation raises. There is no
    multi-document transaction: a storage error can leave accepted outputs or
    completed case Runs. Caller-owned input records never change.
    """
    outcome, cases = _run(specification, store, config, store=store)
    for case in _case_documents(specification, cases):
        if not _stored(store, case.id):
            store.put(case)
    store.put(specification)
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
    cases = resolve_cases(specification, resolver=resolver)
    scopes: dict[UUID, object] = {}
    outcome = _case(specification, cases, config, backend, scopes)
    tree = tuple(outcome.walk())
    overlay = assembly.Overlay(
        cases,
        models=(model for item in tree for model in item.outputs),
        runs=(item.run for item in tree),
    )
    prerequisites = Prerequisites(
        compositions={
            id: view
            for id, view in cases.compositions.items()
            if isinstance(view, Composition)
        },
        scopes=scopes,
    )
    # A store validates with the unit system of the input Model; so does execute.
    validate_run(
        outcome.run,
        resolver=overlay,
        units=config.units if store is None else None,
        prerequisites=prerequisites,
    ).raise_if_invalid()
    if store is not None:
        for item in tree:
            mark_validated(item.run, store, _unstored(item, cases))
    return outcome, cases


def _case_documents(specification: Specification, cases: Cases) -> list[Specification]:
    """Return the case Specifications of a batch, each case before its batch."""
    found = []
    for identity in specification.record.cases or ():
        case = cases.documents[identity]
        found.extend(_case_documents(case, cases))
        found.append(case)
    return found


def _stored(store: RecordStore, id: UUID) -> bool:
    """Return whether ``store`` already holds the Specification ``id``."""
    try:
        store.load_specification(id)
    except MissingReferenceError:
        return False
    return True


def _unstored(outcome: Outcome, cases: Cases) -> set[UUID]:
    """Return the revisions that validating ``outcome.run`` read from no store."""
    documents = {cases.root.id}
    documents.update(case.id for case in _case_documents(cases.root, cases))
    for item in outcome.walk():
        documents.update(model.id for model in item.outputs)
        if item is not outcome:
            documents.add(item.run.id)
    return documents


def _case(
    specification: Specification,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
    scopes: dict[UUID, object],
) -> Outcome:
    # A case's key is the name of its Specification.
    key = specification.metadata.name
    outcome = _attempt(specification, cases, config, backend, scopes)
    return outcome if key is None else replace(outcome, key=key)


def _attempt(
    specification: Specification,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
    scopes: dict[UUID, object],
) -> Outcome:
    if specification.record.cases:
        return assembly.assemble_batch(
            specification,
            tuple(
                _case(cases.documents[id], cases, config, backend, scopes)
                for id in specification.record.cases
            ),
            resolver=cases,
            validate=False,
        )
    attempt = Attempt(
        config,
        backend,
        specification,
        cases.compositions[specification.id],
        resolver=cases,
        validate=False,
    )
    outcome = attempt.execute()
    validation = attempt.validation
    if validation is not None and validation.report.valid and validation.scope:
        scopes[specification.id] = validation.scope
    return outcome
