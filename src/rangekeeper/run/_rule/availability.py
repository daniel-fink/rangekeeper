"""Rule observation dates derived from coordinates and declared dates."""

from datetime import date, timedelta


def available_on(
    *,
    movement_date: date | None = None,
    period_end: date | None = None,
    declared: date | None = None,
) -> date | None:
    """Return the latest boundary; an explicit Movement date takes precedence."""
    coordinate = movement_date or (
        period_end - timedelta(days=1) if period_end else None
    )
    dates = [d for d in (coordinate, declared) if d is not None]
    return max(dates) if dates else None
