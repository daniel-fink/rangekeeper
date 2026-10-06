"""Shared date-only observation boundaries from canonical coordinates and provenance."""

from datetime import date, timedelta
from ._references import reference_key, resolve_reference


def available_on(target, values, provenance, *, declared=None):
    """Return the latest required date; explicit declarations can only delay access."""
    dates = [] if declared is None else [date.fromisoformat(declared)]
    _, movement = resolve_reference(target, values)
    if movement:
        if movement.get("date"):
            dates.append(date.fromisoformat(movement["date"]))
        elif movement.get("period"):
            dates.append(
                date.fromisoformat(movement["period"]["end"]) - timedelta(days=1)
            )
    token = reference_key(target)
    for scenario in provenance.get("scenarios") or []:
        for item in scenario["availability"]:
            if reference_key(item["target"]) == token:
                dates.append(date.fromisoformat(item["available_at"]))
    return max(dates).isoformat() if dates else None
