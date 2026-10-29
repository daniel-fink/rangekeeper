"""The backend contract: an AffineProblem in, a BackendResult out (ADR-013)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from rangekeeper.execution.compiler import AffineProblem
from rangekeeper.execution.settings import Limits
from rangekeeper.schema.records import Diagnostic, Implementation


class Termination(StrEnum):
    """How a backend finished, in words that generic code reads.

    Only independent verification decides whether a candidate is accepted.
    ``LIMIT`` and ``UNKNOWN`` never prove infeasibility.
    """

    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    LIMIT = "limit"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BackendResult:
    """A backend's claim, its candidate and its raw evidence.

    - ``termination``: ``FEASIBLE`` (a feasible candidate), ``INFEASIBLE``
      (proven infeasible), ``LIMIT`` (a time, iteration or other limit),
      ``ERROR`` (failed or interrupted) or ``UNKNOWN``.
    - ``candidate`` maps each variable to a value, or is None.
    - ``limits`` are the limits that the solver applied: the request, or the
      request after the backend adjusted it. None when no solver invocation
      applied them, for example when a deadline stopped the backend first.
    - ``diagnostics`` are the backend's own findings, such as row scaling or an
      adjusted limit. ``evidence`` is its raw JSON evidence, such as its own
      status words.

    Generic code reads only ``termination``, ``candidate`` and ``limits``.
    """

    termination: Termination
    candidate: Mapping[UUID, float] | None = None
    implementations: tuple[Implementation, ...] = ()
    evidence: Mapping[str, object] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
    limits: Limits | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.termination, Termination):
            raise TypeError("termination must be a Termination")


@runtime_checkable
class Backend(Protocol):
    """Backends must enforce the remaining wall deadline and return finite evidence."""

    def solve(
        self,
        problem: AffineProblem,
        *,
        limits: Limits,
        remaining: float,
        options: Mapping[str, object],
    ) -> BackendResult:
        """Solve a problem within the remaining seconds; return a BackendResult.

        ``options`` are the ``backend_options`` of the ExecutionConfig. Raise
        UnsupportedError for an option or a row that the backend refuses.
        """
        ...
