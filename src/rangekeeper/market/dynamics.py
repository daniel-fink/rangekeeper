"""Deterministic market kernels; scenario orchestration owns random streams."""

import math
from collections.abc import Sequence

from rangekeeper.profile import GrowthMethod, grow_values
from rangekeeper.shared.errors import ContractError, NumericalError


def calculate_trend(
    *,
    count: int,
    growth_rate: float,
    cap_rate: float,
    initial_value: float | None = None,
    initial_price_factor: float = 1,
) -> tuple[float, ...]:
    """Preserve the legacy initial-value convention when no explicit value is supplied."""
    initial = (
        initial_price_factor * cap_rate if initial_value is None else initial_value
    )
    return grow_values(
        initial, count=count, method=GrowthMethod.COMPOUND, rate=growth_rate
    )


def calculate_cycle(
    *,
    count: int,
    period: float,
    phase: float,
    amplitude: float,
    asymmetry: float = 0,
    tolerance: float = 1e-10,
) -> tuple[float, ...]:
    """Evaluate a sine or the legacy sheared sine; zero asymmetry is exactly sine.

    Restrict shear to (-1, 1) so the implicit equation has a unique root. The
    bisection interval follows the sine bound and iteration count is finite.
    """
    if type(count) is not int:
        raise TypeError("count must be an int")
    if not all(math.isfinite(x) for x in (period, phase, amplitude, asymmetry)):
        raise ContractError("cycle parameters must be finite")
    if count < 0 or period <= 0 or not -1 < asymmetry < 1 or not 0 < tolerance < 1:
        raise ContractError(
            "invalid cycle parameters",
            values={
                "count": count,
                "period": period,
                "asymmetry": asymmetry,
                "tolerance": tolerance,
            },
        )
    values = []
    for i in range(count):
        angle = (i - phase) * 2 * math.pi / period
        if asymmetry == 0:
            values.append(amplitude * math.sin(angle))
            continue
        low, high = -1.0, 1.0
        for _ in range(math.ceil(math.log2(2 / tolerance)) + 1):
            mid = (low + high) / 2
            # y = sin(angle - shear*y), equivalent to the old auxiliary-root form.
            if mid - math.sin(angle - asymmetry * mid) < 0:
                low = mid
            else:
                high = mid
        values.append(amplitude * (low + high) / 2)
    return tuple(values)


def calculate_autoregression(
    *,
    innovations: Sequence[float],
    parameter: float,
) -> tuple[float, ...]:
    """Add each innovation to the parameter times the previous value (AR(1))."""
    if not math.isfinite(parameter) or any(not math.isfinite(x) for x in innovations):
        raise ContractError("autoregression inputs must be finite")
    values: list[float] = []
    for innovation in innovations:
        values.append(innovation + (parameter * values[-1] if values else 0))
    return tuple(values)


def accumulate_volatility(
    *,
    trend: Sequence[float],
    returns: Sequence[float],
    growth_rate: float,
    mean_reversion: float,
) -> tuple[float, ...]:
    """First level is the first trend value; subsequent returns affect each new level."""
    if len(trend) != len(returns) or not all(
        math.isfinite(x) for x in (*trend, *returns, growth_rate, mean_reversion)
    ):
        raise ContractError(
            "volatility inputs must be finite and have matching lengths"
        )
    result: list[float] = []
    for i, level in enumerate(trend):
        result.append(
            level
            if i == 0
            else result[-1] * (1 + growth_rate + returns[i])
            + mean_reversion * (trend[i - 1] - result[-1])
        )
    if any(not math.isfinite(x) for x in result):
        raise NumericalError("volatility accumulation overflowed")
    return tuple(result)


def calculate_shock(
    *,
    events: Sequence[float],
    likelihood: float,
    dissipation: float,
    impact: float = 1,
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
        raise ContractError(
            "invalid shock parameters",
            values={"likelihood": likelihood, "dissipation": dissipation},
        )
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in events):
        raise ContractError("event draws must lie in [0, 1]")
    first = next((i for i, event in enumerate(events) if event < likelihood), None)
    return tuple(
        0.0 if first is None or i < first else impact * (1 - dissipation) ** (i - first)
        for i in range(len(events))
    )
