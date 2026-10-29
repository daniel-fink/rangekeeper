"""The result of an execution: its finalized Run, outputs and case Outcomes."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Self
from uuid import UUID

from rangekeeper.execution import statuses
from rangekeeper.execution.backends.base import Termination
from rangekeeper.execution.errors import OutcomeError
from rangekeeper.execution.status import Status
from rangekeeper.flow import Flow, Stream
from rangekeeper.model import Model
from rangekeeper.model.targets import recorded_scalar, target_value
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
    Value,
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
# The Termination words that Runs recorded before 1.0.0b1 (#379).
_OLDER_WORDS = {"limit": Termination.LIMITED, "error": Termination.FAILED}


def status_of(report: Report) -> Status:
    """Return the Status of one leaf Run report."""
    solution = report.status.solution
    codes = {item.code for item in report.diagnostics or ()}
    if solution == SolutionStatus.FEASIBLE:
        if Code.UNDERDETERMINED.value in codes:
            return Status.UNDERDETERMINED
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


@dataclass(frozen=True)
class Evidence:
    """The typed solver evidence of one leaf Outcome.

    - ``termination`` is the backend's ``Termination``, or None when no
      backend ran. The words ``limit`` and ``error`` of an older Run read as
      ``LIMITED`` and ``FAILED``.
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


@dataclass(frozen=True)
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
            raise ValueError("outputs must be the Run's outputs, in order")
        if tuple(case.run.id for case in self.cases) != tuple(
            self.run.record.spawns or ()
        ):
            raise ValueError("cases must be the Run's spawned cases, in order")

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
                termination = _termination(str(values.pop("termination")))
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
        of them as the equations lack makes the solve determined. A dotted
        path names a value whose key is not unique in the Model. The tuple is
        empty when the equations determine every unknown. When bounds exist,
        they can still restrict these values.
        """
        self._require_leaf("free_unknowns")
        if not self.outputs:
            return ()
        keys: list[str] = []
        for item in self.diagnostics:
            if item.code in _FREE:
                for reference in item.references or ():
                    key = _key(self.model, target_value(self.model, reference))
                    if key not in keys:
                        keys.append(key)
        return tuple(keys)

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

    def __getitem__(self, key: str) -> Quantity | Flow:
        """Return the solved value at a key or a dotted path.

        A scalar value gives its Quantity; a Flow value gives its Flow. An
        Outcome without an output raises the error of ``raise_for_status()``.
        In an underdetermined Outcome, a free unknown holds one candidate value.
        """
        model = self.model
        value = model._value_at(key)
        if value.flow is not None:
            return value.flow
        if value.quantity is None:
            raise ContractError(f"{key} has no quantity in the output Model")
        return value.quantity

    def case(self, *, key: str) -> "Outcome":
        """Return the Outcome of the direct case with the key ``key``.

        No case with the key raises MissingReferenceError with the keys that
        exist. A leaf Outcome has no cases (TypeError).
        """
        if not self.cases:
            raise TypeError("a leaf Outcome has no cases")
        for case in self.cases:
            if case.key == key:
                return case
        raise MissingReferenceError(
            key,
            kind="case",
            by="key",
            where=self.key,
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

    def stream(self, *keys: str) -> Stream:
        """Return a Stream of the solved Flows at these keys, named by key.

        A batch has no single Stream: read it from one case,
        ``outcome.case(key=...).stream(...)``.
        """
        self._require_leaf("stream")
        if not keys:
            raise TypeError("stream takes at least one key")
        flows = {}
        for key in keys:
            value = self[key]
            if not isinstance(value, Flow):
                raise TypeError(f"{key} is not a Flow value")
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

    def _require_leaf(self, name: str) -> None:
        if self.cases:
            raise TypeError(
                f"a batch Outcome has no single {name}; read it from one of its cases"
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
    decisive = None if status is Status.INFEASIBLE else _decisive(report)
    if decisive is not None:
        return decisive
    return next((item for item in codes if item.code == Code.SOLVER_TERMINATION), None)


def _key(model: Model, value: Value) -> str:
    """Return the key of a Value, or its dotted path when the key is not unique."""
    try:
        if model._value_at(value.key).id == value.id:
            return value.key
    except LookupError:
        pass
    owner = model.owner_of(value.id)
    assert owner is not None  # an output Value has an owner
    return f"{model._path(owner)}.{value.key}"


def _termination(word: str) -> Termination:
    """Return the Termination of a recorded word, also a word of an older Run."""
    return _OLDER_WORDS.get(word) or Termination(word)


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None
