"""The result of an execution: its finalized Run, outputs and case Outcomes."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Self
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.execution import statuses
from rangekeeper.execution.backends.base import Termination
from rangekeeper.execution.decisions import DecisionTable, decision_rows
from rangekeeper.execution.distribution import (
    DateDistribution,
    Distribution,
    Mean,
    _distribution_of,
)
from rangekeeper.execution.errors import OutcomeError
from rangekeeper.execution.status import Status
from rangekeeper.flow import Flow, Stream
from rangekeeper.model import Model
from rangekeeper.model.targets import recorded_scalar
from rangekeeper.quantity import Quantity
from rangekeeper.run import Run
from rangekeeper.schema.records import (
    CompletionStatus,
    Diagnostic,
    Implementation,
    Reference,
    Report,
    Severity,
    SolutionStatus,
    ValueKind,
)
from rangekeeper.schema.runtime import FrozenJSONValue
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    ContractError,
    MissingReferenceError,
    RangekeeperError,
)
from rangekeeper.shared.table import Table

_FREE = (Code.UNDERDETERMINED.value, Code.UNIQUENESS_NOT_ASSESSED.value)
# The Termination of each recorded word, with the words of Runs before
# 1.0.0b1 (#379).
_WORDS = {
    **{item.value: item for item in Termination},
    "limit": Termination.LIMITED,
    "error": Termination.FAILED,
}


def status_of(report: Report) -> Status:
    """Return the Status of one leaf Run report."""
    solution = report.status.solution
    codes = {item.code for item in report.diagnostics or ()}
    # A Run before #152 records an underdetermined solve as feasible, with the
    # diagnostic: bounds or not, the equations leave these unknowns free.
    if solution == SolutionStatus.UNDERDETERMINED or (
        solution == SolutionStatus.FEASIBLE and codes.intersection(_FREE)
    ):
        return Status.UNDERDETERMINED
    if solution == SolutionStatus.FEASIBLE:
        return Status.FEASIBLE
    if solution == SolutionStatus.INFEASIBLE:
        return Status.INFEASIBLE
    if report.status.completion == CompletionStatus.LIMITED:
        return Status.LIMITED
    decisive = _decisive(report)
    if decisive is None:
        return Status.FAILED
    return statuses.failed(decisive.code)


def _decisive(report: Report) -> Diagnostic | None:
    """Return the diagnostic that ended a failed attempt, or None.

    It is the last diagnostic of an expected failure, whatever its severity
    (the attempt deadline is a warning), or else the last error.
    """
    ending = [
        item
        for item in report.diagnostics or ()
        if item.code in statuses.BY_CODE or item.severity == Severity.ERROR
    ]
    return ending[-1] if ending else None


@dataclass(frozen=True, kw_only=True)
class Evidence:
    """The typed solver evidence of one leaf Outcome.

    - ``termination`` is the backend's ``Termination``, or None when no
      backend ran. The words ``limit`` and ``error`` of an older Run read as
      ``LIMITED`` and ``FAILED``. A Run that recorded no Termination word, or
      a word of its backend (1.0.0a1, or a Run that ``tools/upgrade``
      converted), reads as ``UNKNOWN``; ``backend`` keeps that word.
    - ``backend`` is the backend's own evidence, such as its status words and
      iteration count. Generic code does not read it.
    - ``equality_rank`` and ``unknown_count`` come from the rank analysis of
      an underdetermined solve; otherwise they are None.
    - ``implementations`` are the compiler, solver, convention and evaluator
      implementations that the Run records.
    """

    termination: Termination | None = None
    backend: Mapping[str, FrozenJSONValue] = field(
        default_factory=lambda: MappingProxyType({})
    )
    equality_rank: int | None = None
    unknown_count: int | None = None
    implementations: tuple[Implementation, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Outcome:
    """The finalized Run of one Specification, with its outputs and cases.

    ``outputs`` are the accepted output Models, in the order of
    ``run.record.outputs``. A batch has one Outcome in ``cases`` for each of
    its direct cases, in Specification order; a leaf has none. ``key`` is the
    name of the Specification that the Outcome solved: for a case of a batch
    that ``Specification.cases`` made, its case key. An Outcome is immutable
    and holds no store.

    Read a solved value by its key, ``outcome["land_cost"]``: a Quantity for a
    scalar value, a Flow for a Flow value. ``status`` says what the solve
    found, and ``raise_for_status()`` raises when it found no determined
    result.
    """

    run: Run
    outputs: tuple[Model, ...] = ()
    cases: tuple["Outcome", ...] = ()
    key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run, Run):
            raise TypeError("run must be a Run")
        if tuple(model.id for model in self.outputs) != tuple(
            self.run.record.outputs or ()
        ):
            raise ContractError(
                "outputs must be the Run's outputs, in order",
                document_id=self.run.id,
                targets=tuple(model.id for model in self.outputs),
            )
        if tuple(case.run.id for case in self.cases) != tuple(
            self.run.record.spawns or ()
        ):
            raise ContractError(
                "cases must be the Run's spawned cases, in order",
                document_id=self.run.id,
                targets=tuple(case.run.id for case in self.cases),
            )

    def walk(self) -> Iterator["Outcome"]:
        """Yield each case Outcome before its parent, ending with this one."""
        for case in self.cases:
            yield from case.walk()
        yield self

    @property
    def status(self) -> Status:
        """Return what the solve found.

        A batch takes the status of its first leaf case, in ``walk()`` order,
        that is not ``FEASIBLE``; it is ``FEASIBLE`` when every case is.
        """
        if not self.cases:
            return status_of(self.run.report)
        for case in self._leaves():
            found = case.status
            if found is not Status.FEASIBLE:
                return found
        return Status.FEASIBLE

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return the diagnostics of this Outcome's Run, in report order."""
        return tuple(self.run.report.diagnostics or ())

    @property
    def evidence(self) -> Evidence:
        """Return the typed solver evidence of a leaf Outcome.

        A batch has no solver evidence of its own: read it from its cases.
        """
        self._require_leaf("evidence")
        termination: Termination | None = None
        backend: dict[str, FrozenJSONValue] = {}
        rank: int | None = None
        count: int | None = None
        for item in self.diagnostics:
            values: dict[str, FrozenJSONValue] = (
                dict(item.values) if isinstance(item.values, Mapping) else {}
            )
            if item.code == Code.SOLVER_TERMINATION.value:
                termination = _termination(values)
                backend = values
            elif item.code in _FREE:
                rank = _integer(values.get("equality_rank"))
                count = _integer(values.get("unknown_count"))
        runtime = self.run.report.runtime
        return Evidence(
            termination=termination,
            backend=MappingProxyType(backend),
            equality_rank=rank,
            unknown_count=count,
            implementations=tuple(
                () if runtime is None else runtime.implementations or ()
            ),
        )

    @property
    def free_unknowns(self) -> tuple[str, ...]:
        """Return the keys of the free values that the equations do not determine.

        These are every undetermined unknown, in unknown order: each value
        that can change while every equality still holds (D7). Fixing as many
        of them as the equations lack makes the solve determined. Each key is
        the one that ``Model.key_of`` gives, so ``fix`` and ``outcome[key]``
        take it: a dotted key names a value whose key is not unique in the
        Model. The tuple is empty exactly when the equations determine every
        unknown. A bound can still restrict these values: the diagnostic is
        then ``uniqueness_not_assessed``. The keys need no output: the
        diagnostic records them. A Run before #152 records only references,
        which its output Model names.
        """
        self._require_leaf("free_unknowns")
        keys: list[str] = []
        for item in self.diagnostics:
            if item.code in _FREE:
                for key in self._free_keys(item):
                    if key not in keys:
                        keys.append(key)
        return tuple(keys)

    def _free_keys(self, diagnostic: Diagnostic) -> tuple[str, ...]:
        """Return the keys of the free unknowns that one diagnostic names."""
        values = diagnostic.values if isinstance(diagnostic.values, Mapping) else {}
        recorded = values.get("unknowns")
        if isinstance(recorded, (list, tuple)):
            return tuple(str(key) for key in recorded)
        if not self.outputs:
            return ()
        return tuple(
            self.model.key_of(reference.target)
            for reference in diagnostic.references or ()
        )

    @property
    def model(self) -> Model:
        """Return the accepted output Model of a leaf Outcome.

        Without an output, raise the error of ``raise_for_status()``.
        """
        self._require_leaf("model")
        if not self.outputs:
            self.raise_for_status()
            raise OutcomeError("this Outcome has no output Model", status=self.status)
        return self.outputs[0]

    def __getitem__(self, key: str) -> Quantity | Flow | DateValue:
        """Return the solved value at a key, as ``Model.value(key=)`` takes it.

        The key is a bare key, a dotted key such as ``building_a.income``, or
        the text of a Value UUID.

        A scalar value gives its Quantity; a Flow value gives its Flow; a date
        Value gives its date, or ``rk.duration.NEVER``. An Outcome without an
        output raises the error of ``raise_for_status()``. An underdetermined
        Outcome has an output only with
        ``ExecutionConfig(allow_underdetermined=True)``; a free unknown then
        holds one candidate value.
        """
        value = self.model.value(key=key)
        if value.flow is not None:
            return value.flow
        if value.kind is ValueKind.DATE:
            if value.never is not None:
                return NEVER
            if value.date is None:
                raise ContractError(f"{key} has no date in the output Model")
            return value.date
        if value.quantity is None:
            raise ContractError(f"{key} has no quantity in the output Model")
        return value.quantity

    def case(self, *, key: str) -> "Outcome":
        """Return the Outcome of the direct case with the key ``key``.

        No case with the key raises MissingReferenceError with the keys that
        exist. A leaf Outcome has no cases: ContractError with the code
        ``BATCH_REQUIRED``.
        """
        self._require_batch("case")
        for case in self.cases:
            if case.key == key:
                return case
        raise MissingReferenceError(
            key,
            kind="Outcome",
            by="key",
            where=f"Outcome {self.key or self.run.id}",
            document_id=self.run.id,
            candidates=[case.key for case in self.cases if case.key is not None],
        )

    def table(self, *keys: str) -> Table:
        """Return a Table of solved values: one row for each leaf case.

        The columns are ``case``, ``status`` and one column for each key: the
        Quantity of a scalar value, or the Flow of a Flow value. ``case`` is the
        case key, with the keys of nested batches joined by ``/``; a leaf
        Outcome gives one row with its own key. A case without an output has
        None for each value; ``status`` says why.
        """
        if not keys:
            raise TypeError("table takes at least one key")
        rows = []
        for path, leaf in self._keyed_leaves(()):
            row: dict[str, object] = {
                "case": "/".join(path) if path else self.key,
                "status": leaf.status,
            }
            for key in keys:
                row[key] = leaf[key] if leaf.outputs else None
            rows.append(row)
        return Table(("case", "status", *keys), rows)

    def distribution(self, *, key: str) -> "Distribution[Outcome] | DateDistribution":
        """Return the distribution of the solved value at ``key`` across the leaf cases.

        Each leaf case, in ``walk()`` order, has the same weight. A scalar
        value gives a ``Distribution``: its ``summary()``, ``mean()``,
        ``quantile(level=)``, ``probability(below=, above=)``, ``counts()``
        and ``case(quantile=)``, which returns the leaf Outcome at that
        quantile. A date value gives a ``DateDistribution`` with
        ``counts()``. A Flow value raises ContractError with the code
        ``DISTRIBUTION_VALUE``. A case without an output raises the error of
        its ``raise_for_status()``. A leaf Outcome has no cases:
        ContractError with the code ``BATCH_REQUIRED``.
        """
        self._require_batch("distribution")
        return _distribution_of(
            key=key, values=[(leaf, leaf[key]) for leaf in self._leaves()]
        )

    def mean(self) -> Mean:
        """Return the mean of this batch's scalar values, each leaf case with the same weight.

        Read the mean of a value by key, ``outcome.mean()["equity_npv"]``.
        ``rk.execution.compare`` takes the ``Mean`` as one leaf Outcome. A leaf
        Outcome has no cases: ContractError with the code ``BATCH_REQUIRED``.
        """
        self._require_batch("mean")
        return Mean._of(outcome=self)

    @property
    def decisions(self) -> DecisionTable:
        """Return the decision trace of each leaf case, one row for each window date.

        Read them with ``where(key=, result=)`` and ``observations``. A case without
        rules has no rows, and a case that failed during its rules holds the records
        up to its failure.
        """
        return DecisionTable(
            rows=(
                row
                for path, leaf in self._keyed_leaves(())
                for row in decision_rows(
                    "/".join(path) if path else self.key, leaf.run.rule_evidence
                )
            )
        )

    @property
    def trace(self) -> DecisionTable:
        """Return the decision trace of a leaf Outcome, one row for each window date.

        A batch has no single trace: read ``decisions``, or the trace of one case.
        """
        self._require_leaf("trace")
        return self.decisions

    def stream(self, *keys: str) -> Stream:
        """Return a Stream of the solved Flows at these keys, named by key.

        A batch has no single Stream: read it from one case,
        ``outcome.case(key=...).stream(...)``. A key of a scalar value raises
        ContractError.
        """
        self._require_leaf("stream")
        if not keys:
            raise TypeError("stream takes at least one key")
        flows = {}
        for key in keys:
            value = self[key]
            if not isinstance(value, Flow):
                raise ContractError(
                    f"{key} is not a Flow value",
                    document_id=self.run.id,
                    values={"key": key},
                )
            flows[key] = value
        return Stream(flows=flows)

    def _keyed_leaves(
        self, path: tuple[str, ...]
    ) -> Iterator[tuple[tuple[str, ...], "Outcome"]]:
        if not self.cases:
            yield path, self
            return
        for position, case in enumerate(self.cases):
            yield from case._keyed_leaves(path + (case.key or str(position),))

    def quantity(self, reference: Reference | UUID) -> Quantity:
        """Return the solved Quantity of a scalar Value or a Movement."""
        if isinstance(reference, UUID):
            reference = Reference(target=reference)
        found = recorded_scalar(self.model, reference)
        if found is None:
            raise ContractError(
                f"{reference.target} has no quantity in the output Model"
            )
        return found

    def raise_for_status(self) -> Self:
        """Return this Outcome when its status is ``FEASIBLE``; otherwise raise.

        The error says why, with the code of the decisive diagnostic:

        | Status | Error |
        | --- | --- |
        | ``UNSUPPORTED`` | ``UnsupportedError`` |
        | ``INVALID`` | ``ValidationError`` |
        | ``LIMITED`` | ``AttemptDeadlineError`` for the attempt deadline, else ``OutcomeError`` |
        | ``FAILED`` | ``NumericalError`` or ``BackendUnavailableError``, else ``OutcomeError`` |
        | ``UNDERDETERMINED``, ``INFEASIBLE`` | ``OutcomeError`` |

        When the decisions of rules break a date constraint, ``OutcomeError``
        has the code ``constraint_residual`` and that constraint in ``equation``.

        A batch raises for its first leaf case, in ``walk()`` order, that is
        not ``FEASIBLE``.
        """
        for case in self._leaves():
            error = _error(case)
            if error is not None:
                raise error
        return self

    def _leaves(self) -> Iterator["Outcome"]:
        return (item for item in self.walk() if not item.cases)

    def _require_batch(self, name: str) -> None:
        """Raise ContractError with the code ``BATCH_REQUIRED`` for a leaf."""
        if not self.cases:
            raise ContractError(
                f"{name} reads the cases of a batch, and a leaf Outcome has none",
                code=Code.BATCH_REQUIRED,
                document_id=self.run.id,
            )

    def _require_leaf(self, name: str) -> None:
        """Raise ContractError with the code ``BATCH_UNSUPPORTED`` for a batch."""
        if self.cases:
            raise ContractError(
                f"a batch Outcome has no single {name}; read it from one of its cases",
                code=Code.BATCH_UNSUPPORTED,
                document_id=self.run.id,
            )


def _error(outcome: Outcome) -> RangekeeperError | None:
    """Return the error for a leaf Outcome's status, or None when it is feasible."""
    status = outcome.status
    if status is Status.FEASIBLE:
        return None
    reason = _reason(outcome.run.report, status)
    message = f"the solve is {status.value}"
    if reason is None:
        return OutcomeError(message, status=status)
    return statuses.rebuilt(
        reason, message=f"{message}: {reason.message}", status=status
    )


def _reason(report: Report, status: Status) -> Diagnostic | None:
    """Return the diagnostic that says why an Outcome has its status."""
    codes = report.diagnostics or ()
    if status is Status.UNDERDETERMINED:
        return next(item for item in codes if item.code in _FREE)
    decisive = _broken(report) if status is Status.INFEASIBLE else _decisive(report)
    if decisive is not None:
        return decisive
    return next((item for item in codes if item.code == Code.SOLVER_TERMINATION), None)


def _broken(report: Report) -> Diagnostic | None:
    """Return the first constraint that the decisions of rules break, or None."""
    return next(
        (
            item
            for item in report.diagnostics or ()
            if item.code == Code.CONSTRAINT_RESIDUAL and item.severity == Severity.ERROR
        ),
        None,
    )


def _termination(values: dict[str, FrozenJSONValue]) -> Termination:
    """Remove the Termination word from solver evidence and return its Termination.

    A missing word, or a word that is not a Termination word, is ``UNKNOWN``,
    and the word stays in ``values``.
    """
    found = _WORDS.get(str(values.get("termination")))
    if found is None:
        return Termination.UNKNOWN
    del values["termination"]
    return found


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None
