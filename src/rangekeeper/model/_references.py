"""Shared reference keys and scalar eligibility without solver dependencies.

Keys are private lookup tokens, not new domain identities. A slash follows the
fixed-length UUID, so Movement keys can themselves contain slashes unambiguously.
"""

from .._validation import require


def reference_key(reference: dict) -> str:
    """Return a stable key for a structurally validated ValueReference."""
    value = reference["value"]
    movement = reference.get("movement")
    return value if movement is None else value + "/" + movement


def resolve_reference(reference: dict, values):
    """Return the owning Value and optional Movement; reject unresolved shapes."""
    identity = reference["value"]
    require(identity in values, "unknown or non-Value role target")
    value = values[identity]
    key = reference.get("movement")
    if key is None:
        return value, None
    require(value.get("kind") == "flow", "Movement reference requires a Flow Value")
    flow = value.get("flow")
    require(flow is not None, "Movement reference requires a declared Flow shape")
    matches = [m for m in flow["movements"] if m["key"] == key]
    require(len(matches) == 1, "unknown or duplicate Movement key")
    return value, matches[0]


def numerical_units(reference: dict, values, measures) -> str:
    """Resolve numerical role units without treating content as an assignment."""
    value, movement = resolve_reference(reference, values)
    if movement is not None:
        return value["flow"]["units"]
    require(
        value.get("kind") == "measurement",
        "unsupported role Value kind; Flow roles require a Movement key",
    )
    return measures[value["measure"]]["units"]


def recorded_quantity(reference: dict, values, measures):
    """Read a scalar amount explicitly; an absent or null amount stays unresolved."""
    value, movement = resolve_reference(reference, values)
    if movement is None:
        numerical_units(reference, values, measures)
        return value.get("quantity")
    magnitude = movement.get("magnitude")
    return (
        None
        if magnitude is None
        else dict(magnitude=magnitude, units=value["flow"]["units"])
    )
