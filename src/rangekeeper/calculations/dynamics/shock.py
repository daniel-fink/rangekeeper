"""First-event shock with explicit amplitude and geometric dissipation."""

from collections.abc import Sequence
import math


def calculate_shock(
    events: Sequence[float], *, likelihood: float, dissipation: float, impact: float = 1
) -> tuple[float, ...]:
    """Trigger at the first draw below likelihood, then decay without retriggering.

    Passing impact=1 reproduces the old normalized event path. Apply the requested
    amplitude here exactly once, rather than retaining an unused impact parameter.
    """
    if (
        not 0 <= likelihood <= 1
        or not 0 <= dissipation <= 1
        or not math.isfinite(impact)
    ):
        raise ValueError("invalid shock parameters")
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in events):
        raise ValueError("event draws must lie in [0, 1]")
    first = next((i for i, event in enumerate(events) if event < likelihood), None)
    return tuple(
        0.0 if first is None or i < first else impact * (1 - dissipation) ** (i - first)
        for i in range(len(events))
    )
