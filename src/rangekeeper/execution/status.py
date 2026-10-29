"""The Status of an Outcome: what a solve found, in one word.

This module imports nothing from ``execution``, so that the error classes and
the failure tables can both name ``Status``.
"""

from enum import StrEnum


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


__all__ = ["Status"]
