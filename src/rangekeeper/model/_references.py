"""Resolve direct declaration identities in an explicitly supplied scope.

The target index owns the Value/Movement distinction and Movement ownership.
No reference carries a document address or interprets an event matching key.
"""

from .._validation import require


def reference_key(reference: dict) -> str:
    """Return the declaration UUID used as the private numerical symbol token."""
    return reference["target"]


def resolve_reference(reference: dict, targets):
    """Return the owning Value and optional Movement from the scope's target index."""
    identity = reference["target"]
    require(identity in targets, "unknown Value or Movement reference")
    return targets[identity]


def numerical_units(reference: dict, targets, measures) -> str:
    """Resolve numerical role units without treating recorded content as an assignment."""
    value, movement = resolve_reference(reference, targets)
    if movement is not None:
        return value["flow"]["units"]
    require(
        value.get("kind") == "measurement",
        "numerical roles require a scalar measurement or Movement",
    )
    return measures[value["measure"]]["units"]


def recorded_quantity(reference: dict, targets, measures):
    """Read a scalar amount explicitly; an absent or null amount stays unresolved."""
    value, movement = resolve_reference(reference, targets)
    if movement is None:
        numerical_units(reference, targets, measures)
        return value.get("quantity")
    magnitude = movement.get("magnitude")
    return (
        None
        if magnitude is None
        else dict(magnitude=magnitude, units=value["flow"]["units"])
    )
