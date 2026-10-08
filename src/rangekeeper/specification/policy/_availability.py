"""Policy observation dates derived from coordinates and recorded evidence."""

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from uuid import UUID


def available_on(
    *,
    movement_date: date | None = None,
    period_end: date | None = None,
    scenario_dates: Iterable[date] = (),
    declared: date | None = None,
) -> date | None:
    """Return the latest boundary; an explicit Movement date takes precedence."""
    coordinate = movement_date or (
        period_end - timedelta(days=1) if period_end else None
    )
    dates = [d for d in (coordinate, declared, *scenario_dates) if d is not None]
    return max(dates) if dates else None


def evidence_dates(provenance: Mapping) -> dict[UUID, date]:
    """Index the latest scenario evidence once for an observation operation."""
    result: dict[UUID, date] = {}
    for scenario in provenance.get("scenarios") or ():
        for item in scenario["availability"]:
            target = UUID(item["target"]["target"])
            result[target] = max(
                result.get(target, date.min), date.fromisoformat(item["available_at"])
            )
    return result
