"""The result of an execution: its finalized Run, outputs and case Outcomes."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Self
from uuid import UUID

from rangekeeper.execution.backends.base import Termination
from rangekeeper.execution.errors import OutcomeError
from rangekeeper.flow import Flow
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
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    ContractError,
    NumericalError,
    RangekeeperError,
    UnsupportedError,
    ValidationError,
)


class Status(StrEnum):
    """What an Outcome found, in one word.

    The status follows from the Run report: its completion, its solution and
    the code of its decisive diagnostic.
    """

    FEASIBLE = "feasible"
    """An accepted candidate, and the equations determine each unknown."""
    UNDERDETERMINED = "underdetermined"
    """An accepted candidate, but the equations leave some unknowns free."""
    INFEASIBLE = "infeasible"
    """The backend proved that no candidate satisfies the equations."""
    UNSUPPORTED = "unsupported"
    """The problem is outside the supported mathematics or limits."""
    INVALID = "invalid"
    """The Specification is not valid against its Model."""
    LIMITED = "limited"
    """A time or iteration limit stopped the attempt before a candidate."""
    FAILED = "failed"
    """A numerical, backend or verification failure."""


# The status of a failed attempt, by the code of its decisive diagnostic. Any
# other code of an error diagnostic is an UnsupportedError's own code.
_FAILURES: Mapping[str, Status] = MappingProxyType(
    {
        Code.SPECIFICATION_INVALID.value: Status.INVALID,
        Code.NUMERICAL_FAILURE.value: Status.FAILED,
        Code.NUMERICAL_REJECTION.value: Status.FAILED,
        Code.BACKEND_UNAVAILABLE.value: Status.FAILED,
    }
)

_FREE = (Code.UNDERDETERMINED.value, Code.UNIQUENESS_NOT_ASSESSED.value)


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
    return _FAILURES.get(decisive.code, Status.UNSUPPORTED)


def _decisive(report: Report) -> Diagnostic | None:
    """Return the last error diagnostic: the one that ended the attempt."""
    errors = [
        item for item in report.diagnostics or () if item.severity == Severity.ERROR
    ]
    return errors[-1] if errors else None


@dataclass(frozen=True)
class Evidence:
    """The typed solver evidence of one leaf Outcome.

    - ``termination`` is the backend's ``Termination``, or None when no
      backend ran.
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
    its direct cases, in Specification order; a leaf has none. An Outcome is
    immutable and holds no store.

    Read a solved value by its key, ``outcome["land_cost"]``: a Quantity for a
    scalar value, a Flow for a Flow value. ``status`` says what the solve
    found, and ``raise_for_status()`` raises when it found no determined
    result.
    """

    run: Run
    outputs: tuple[Model, ...] = ()
    cases: tuple["Outcome", ...] = ()

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
                termination = Termination(str(values.pop("termination")))
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
    report = outcome.run.report
    decisive = _decisive(report)
    if status is Status.UNDERDETERMINED:
        decisive = next(
            item
            for item in report.diagnostics or ()
            if item.code == Code.UNDERDETERMINED
        )
    elif status is Status.INFEASIBLE or decisive is None:
        decisive = next(
            (
                item
                for item in report.diagnostics or ()
                if item.code == Code.SOLVER_TERMINATION
            ),
            None,
        )
    message = f"the solve is {status.value}"
    if decisive is not None:
        message += f": {decisive.message}"
    code = None if decisive is None else Code(decisive.code)
    document = None if decisive is None else decisive.document
    target = None if decisive is None else decisive.target
    if status is Status.UNSUPPORTED:
        assert code is not None
        values = {} if decisive is None else decisive.values
        if not isinstance(values, Mapping):
            values = {}
        equation = values.get("equation")
        unknowns = values.get("unknowns")
        return UnsupportedError(
            message,
            code=code,
            document=document,
            target=target,
            equation=equation if isinstance(equation, str) else None,
            unknowns=(
                tuple(str(key) for key in unknowns)
                if isinstance(unknowns, (list, tuple))
                else ()
            ),
        )
    if status is Status.INVALID:
        assert code is not None
        return ValidationError(
            ValidationReport(
                (
                    Issue(
                        code,
                        message,
                        document,
                        targets=() if target is None else (target,),
                    ),
                )
            )
        )
    if code is Code.ATTEMPT_DEADLINE:
        return AttemptDeadlineError(message)
    if code in (Code.NUMERICAL_FAILURE, Code.NUMERICAL_REJECTION):
        error = NumericalError(message)
        error.code = code
        return error
    if code is Code.BACKEND_UNAVAILABLE:
        return BackendUnavailableError(message)
    return OutcomeError(
        message,
        status=status,
        code=code,
        document=document,
        target=target,
    )


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


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None
