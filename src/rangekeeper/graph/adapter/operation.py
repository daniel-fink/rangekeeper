"""Immutable invocation records and explicit outcomes for document operations."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from ... import validate
from ..provenance import Location, Method
from . import _structured
from .ingestion import IssueSeverity

__all__ = ["Diagnostic", "Operation", "Outcome", "fingerprint"]
T = TypeVar("T")


@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """Effective invocation description, not an executable algorithm or run ID."""

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
    """Invocation-level explanation; Evidence issues belong to output addresses."""

    code: str
    severity: IssueSeverity
    message: str
    locations: tuple[Location, ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("code", "message"):
            validate.require_text(getattr(self, name), name)
        if not isinstance(self.severity, IssueSeverity):
            raise TypeError("severity must be IssueSeverity")
        locations = tuple(self.locations)
        if any(not isinstance(item, Location) for item in locations):
            raise TypeError("locations must contain Location objects")
        object.__setattr__(self, "locations", locations)
        object.__setattr__(self, "details", _structured.freeze_mapping(self.details))


@dataclass(frozen=True, slots=True, kw_only=True)
class Outcome(Generic[T]):
    """An invocation and its optional output; severity never decides availability."""

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
    if not isinstance(operation, Operation):
        raise TypeError("Expected Operation")
    return _structured.fingerprint({
        "format": "rk.operation/v1",
        "method": (operation.method.code, operation.method.version),
        "specification": operation.specification,
        "inputs": operation.inputs,
    })


class _Failure(Exception):
    """Private control flow for an anticipated input/capability mismatch."""

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
            severity=IssueSeverity.ERROR,
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
    operation = Operation(method=method, specification=specification, inputs=inputs)
    try:
        output = run(operation)
    except _Failure as exc:
        return Outcome(operation=operation, output=None, diagnostics=(exc.diagnostic,))
    return Outcome(operation=operation, output=output)
