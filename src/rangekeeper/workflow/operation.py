"""Immutable invocation records and explicit outcomes for document operations."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from rangekeeper.shared import arguments as validate
from rangekeeper.shared import structured as _structured
from rangekeeper.workflow.evidence import Location, Method

__all__ = ["Diagnostic", "Severity", "Operation", "Outcome", "fingerprint"]
T = TypeVar("T")


from rangekeeper.schema.enums import Severity


@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """Effective invocation description, not an executable algorithm or run ID.

    Separates reproducible computation identity from execution timing, allowing
    a caller to explain exactly which parameters and input versions produced an
    output.
    """

    method: Method
    specification: Mapping[str, object]
    inputs: Mapping[str, str | None]

    def __post_init__(self) -> None:
        if not isinstance(self.method, Method):
            raise TypeError("method must be Method")
        if self.method.version is None:
            raise ValueError("Recorded operations require a method version")
        validate.require_text(self.method.version, "method.version")
        if not isinstance(self.inputs, Mapping):
            raise TypeError("inputs must be a mapping")
        for key, value in self.inputs.items():
            validate.require_text(key, "input name")
            if value is not None:
                validate.require_text(value, "input fingerprint")
        object.__setattr__(
            self, "specification", _structured.freeze_mapping(self.specification)
        )
        object.__setattr__(self, "inputs", _structured.freeze_mapping(self.inputs))


@dataclass(frozen=True, slots=True, kw_only=True)
class Diagnostic:
    """Invocation-level explanation; Evidence issues belong to output addresses.

    Explains why a request could not be carried out when there may be no output
    cell on which to place an Issue.
    """

    code: str
    severity: Severity
    message: str
    locations: tuple[Location, ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("code", "message"):
            validate.require_text(getattr(self, name), name)
        if not isinstance(self.severity, Severity):
            raise TypeError("severity must be Severity")
        locations = tuple(self.locations)
        if any(not isinstance(item, Location) for item in locations):
            raise TypeError("locations must contain Location objects")
        object.__setattr__(self, "locations", locations)
        object.__setattr__(self, "details", _structured.freeze_mapping(self.details))


@dataclass(frozen=True, slots=True, kw_only=True)
class Outcome(Generic[T]):
    """An invocation and its optional output; severity never decides availability.

    Distinguishes an unavailable operation from a successful Evidence table
    containing unavailable cells. Expected input incompatibilities remain
    reviewable without pretending a result exists.
    """

    operation: Operation
    output: T | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.operation, Operation):
            raise TypeError("operation must be Operation")
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain Diagnostic objects")
        if self.output is None and not diagnostics:
            raise ValueError("Unavailable output requires a diagnostic")
        object.__setattr__(self, "diagnostics", diagnostics)


def fingerprint(operation: Operation) -> str:
    """Identifies the effective computation for replay and derived-Claim identity.
    Equal invocations share a digest rather than receiving a new job identity.
    """
    if not isinstance(operation, Operation):
        raise TypeError("Expected Operation")
    return _structured.fingerprint(
        {
            "format": "rk.operation/v1",
            "method": (operation.method.code, operation.method.version),
            "specification": operation.specification,
            "inputs": operation.inputs,
        }
    )


class _Failure(Exception):
    """Private control flow for an anticipated input/capability mismatch.

    Lets an operation report an expected source mismatch without converting
    programmer errors into apparently normal Outcomes.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        locations: tuple[Location, ...] = (),
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic = Diagnostic(
            code=code,
            severity=Severity.ERROR,
            message=message,
            locations=locations,
            details={} if details is None else details,
        )


def _invoke(
    method: Method,
    specification: Mapping[str, object],
    inputs: Mapping[str, str | None],
    run: Callable[[Operation], T],
) -> Outcome[T]:
    """Keeps anticipated failure-to-Outcome conversion consistent across operations
    while leaving invalid arguments and unexpected exceptions visible to the
    caller.
    """
    operation = Operation(method=method, specification=specification, inputs=inputs)
    try:
        output = run(operation)
    except _Failure as exc:
        return Outcome(operation=operation, output=None, diagnostics=(exc.diagnostic,))
    return Outcome(operation=operation, output=output)
