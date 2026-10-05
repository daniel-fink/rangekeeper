"""Shared Flow result construction and resolved numerical input checks."""

from collections.abc import Sequence
from ..model.flow import Flow, Movement, validate_flow


def replace_movements(
    flow: Flow, movements: Sequence[Movement], *, units=None
) -> Flow:
    result = Flow(
        units=units or flow.units, movements=tuple(movements)
    )
    validate_flow(result)
    return result


def replace_movement(movement: Movement, magnitude, *, claims=None) -> Movement:
    data = movement.to_data()
    data["magnitude"] = magnitude
    if claims is not None:
        data["claims"] = [str(identity) for identity in claims]
    return Movement.from_data(data)


def require_resolved(flow: Flow) -> None:
    """Require valid coordinates, units and finite, known numerical entries.

    The consuming operation defines how it interprets these entries. This check
    does not infer or restrict the meaning of a Flow.
    """
    validate_flow(flow)
    for movement in flow.movements:
        magnitude(movement)


def magnitude(movement: Movement) -> float:
    """Read a resolved movement for arithmetic; reject a missing or nonfinite value."""
    from math import isfinite

    value = movement.magnitude
    if value is None or not isfinite(value):
        raise ValueError(f"unresolved/nonfinite movement: {movement.key}")
    return float(value)
