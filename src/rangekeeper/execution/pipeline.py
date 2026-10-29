"""Run the stages for each case: pure ``solve`` and publishing ``execute``."""

from uuid import UUID

from rangekeeper.execution import assembly
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.planning import Cases, resolve_cases
from rangekeeper.run import Prerequisites
from rangekeeper.run import validate as validate_run
from rangekeeper.run.validation import mark_validated
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.shared.store import RecordStore
from rangekeeper.specification import Composition, Specification


def solve(
    specification: Specification,
    resolver: DocumentResolver,
    *,
    config: ExecutionConfig | None = None,
) -> Outcome:
    """Run every stage for each case of ``specification``; write nothing.

    ``resolver`` supplies the exact revisions that the Specification names.
    Each leaf case gives a finalized Run, even when it fails; repeated cases
    are separate attempts. Each Run is validated once, in one validation of
    the whole tree with the unstored outputs and case Runs laid over
    ``resolver``. Without ``config``, the defaults of ExecutionConfig apply.

    Missing references, invalid batch graphs and programming errors raise.
    Expected formulation and numerical failures are evidence in the Run. A
    feasible Run certifies only the documented scalar slice and its independent
    verification, not uniqueness or optimality.
    """
    return _run(specification, resolver, config, store=None)


def execute(
    specification: Specification,
    store: RecordStore,
    *,
    config: ExecutionConfig | None = None,
) -> Outcome:
    """Solve ``specification`` with ``store`` as resolver, then publish the result.

    Publication puts the Specification, then for each case its outputs and then
    its Run, cases before their batch. Each Run is validated once, against
    ``store``, before anything is put; ``store.put`` does not repeat that
    validation. Nothing is put when solving or validation raises. There is no
    multi-document transaction: a storage error can leave accepted outputs or
    completed case Runs. Caller-owned input records never change.
    """
    outcome = _run(specification, store, config, store=store)
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
) -> Outcome:
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
            mark_validated(item.run, store, _unstored(item, specification))
    return outcome


def _unstored(outcome: Outcome, root: Specification) -> set[UUID]:
    """Return the revisions that validating ``outcome.run`` read from no store."""
    documents = {root.id}
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
