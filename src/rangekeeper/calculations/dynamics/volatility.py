"""Autoregressive innovations and mean-reverting level accumulation."""

import math
from collections.abc import Sequence


def calculate_autoregression(
    innovations: Sequence[float], *, parameter: float
) -> tuple[float, ...]:
    if not math.isfinite(parameter) or any(not math.isfinite(x) for x in innovations):
        raise ValueError("autoregression inputs must be finite")
    values: list[float] = []
    for innovation in innovations:
        values.append(innovation + (parameter * values[-1] if values else 0))
    return tuple(values)


def accumulate_volatility(
    trend: Sequence[float],
    returns: Sequence[float],
    *,
    growth_rate: float,
    mean_reversion: float
) -> tuple[float, ...]:
    """First level is the first trend value; subsequent returns affect each new level."""
    if len(trend) != len(returns) or not all(
        math.isfinite(x) for x in (*trend, *returns, growth_rate, mean_reversion)
    ):
        raise ValueError("volatility inputs must be finite and have matching lengths")
    result: list[float] = []
    for i, level in enumerate(trend):
        result.append(
            level
            if i == 0
            else result[-1] * (1 + growth_rate + returns[i])
            + mean_reversion * (trend[i - 1] - result[-1])
        )
    if any(not math.isfinite(x) for x in result):
        raise ValueError("volatility accumulation overflowed")
    return tuple(result)
