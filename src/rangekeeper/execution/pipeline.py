"""Run the stages for each case: pure ``solve`` and publishing ``execute``."""

from rangekeeper.execution import assembly
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.planning import Cases, resolve_cases
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.shared.store import RecordStore
from rangekeeper.specification import Specification


def solve(
    specification: Specification,
    resolver: DocumentResolver,
    *,
    config: ExecutionConfig | None = None,
) -> Outcome:
    """Run every stage for each case of ``specification``; write nothing.

    ``resolver`` supplies the exact revisions that the Specification names.
    Each leaf case gives a finalized Run, even when it fails; repeated cases
    are separate attempts. Each Run is validated once, with the unstored
    outputs and case Runs laid over ``resolver``. Without ``config``, the
    defaults of ExecutionConfig apply.

    Missing references, invalid batch graphs and programming errors raise.
    Expected formulation and numerical failures are evidence in the Run. A
    feasible Run certifies only the documented scalar slice and its independent
    verification, not uniqueness or optimality.
    """
    return _run(specification, resolver, config, validate=True)


def execute(
    specification: Specification,
    store: RecordStore,
    *,
    config: ExecutionConfig | None = None,
) -> Outcome:
    """Solve ``specification`` with ``store`` as resolver, then publish the result.

    Publication puts the Specification, then for each case its outputs and then
    its Run, cases before their batch. ``store.put`` is the one validation of
    each Run. Nothing is put when solving raises. There is no multi-document
    transaction: a storage error can leave accepted outputs or completed case
    Runs. Caller-owned input records never change.
    """
    outcome = _run(specification, store, config, validate=False)
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
    validate: bool,
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
    return _case(specification, cases, config, backend, validate)


def _case(
    specification: Specification,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
    validate: bool,
) -> Outcome:
    if specification.record.cases:
        return assembly.assemble_batch(
            specification,
            tuple(
                _case(cases.documents[id], cases, config, backend, validate)
                for id in specification.record.cases
            ),
            resolver=cases,
            validate=validate,
        )
    return Attempt(
        config,
        backend,
        specification,
        cases.compositions[specification.id],
        resolver=cases,
        validate=validate,
    ).execute()
