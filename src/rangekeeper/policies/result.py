"""Immutable derived policy state; persistent fields remain generated records."""

from dataclasses import dataclass
from datetime import date
from .._schema.records import Assignment, Decision, ObservedQuantity


@dataclass(frozen=True)
class Observation:
    """Only the declared, available quantities at one date; no Model/store handle."""

    at: date
    quantities: tuple[ObservedQuantity, ...]


@dataclass(frozen=True)
class DecisionHistory:
    """Earlier decisions supplied explicitly to the next decision point."""

    decisions: tuple[Decision, ...] = ()


@dataclass(frozen=True)
class PolicyResult:
    """Derived trace and explicit controls; makes no claim of solve feasibility."""

    decisions: tuple[Decision, ...]
    assignments: tuple[Assignment, ...]
