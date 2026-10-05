"""Known growth paths, separate from scenario parameter sampling."""

from ..projection import project_values


def calculate_trend(
    *,
    count: int,
    growth_rate: float,
    cap_rate: float,
    initial_value: float | None = None,
    initial_price_factor: float = 1
) -> tuple[float, ...]:
    """Preserve the legacy initial-value convention when no explicit value is supplied."""
    initial = (
        initial_price_factor * cap_rate if initial_value is None else initial_value
    )
    return project_values(initial, count=count, method="compound", rate=growth_rate)
