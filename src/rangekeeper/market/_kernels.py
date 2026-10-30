"""Deterministic market kernels over supplied draws; they draw no random numbers.

Each kernel calculates one component of a market path, one value for each
Period, from its parameters per Period and from draws that the caller made.
``rk.market.Dynamics`` composes them. Invalid parameters raise ContractError,
and a result that is not finite raises NumericalError.
"""

import math
from collections.abc import Sequence

from rangekeeper.shared.errors import ContractError, NumericalError

__all__ = [
    "accumulate_volatility",
    "autoregression",
    "cycle",
    "shock",
    "trend",
]

# The bisection tolerance of an asymmetric cycle: the root is exact to within it.
_TOLERANCE = 1e-10
_STEPS = math.ceil(math.log2(2 / _TOLERANCE)) + 1


def trend(*, count: int, rate: float, initial: float = 1.0) -> tuple[float, ...]:
    """Return ``initial`` compounded at ``rate`` for each Period: ``initial * (1 + rate) ** i``."""
    _require_count(count)
    _require_finite(rate=rate, initial=initial)
    values = tuple(initial * (1 + rate) ** i for i in range(count))
    _require_result(values, "trend")
    return values


def cycle(
    *,
    count: int,
    period: float,
    phase: float,
    amplitude: float,
    asymmetry: float = 0,
) -> tuple[float, ...]:
    """Return a sine of ``amplitude`` with ``period`` and ``phase`` in Periods.

    ``amplitude`` is half the peak-to-trough height. A nonzero ``asymmetry``,
    in (-1, 1), shears the sine: ``y = sin(angle - asymmetry * y)``, found by
    bisection. Zero asymmetry is exactly the sine.
    """
    _require_count(count)
    _require_finite(
        period=period, phase=phase, amplitude=amplitude, asymmetry=asymmetry
    )
    if period <= 0 or not -1 < asymmetry < 1:
        raise ContractError(
            "a cycle needs a positive period and an asymmetry between -1 and 1",
            values={"period": period, "asymmetry": asymmetry},
        )
    return tuple(
        amplitude * _sheared((i - phase) * 2 * math.pi / period, asymmetry)
        for i in range(count)
    )


def _sheared(angle: float, asymmetry: float) -> float:
    """Return y with ``y = sin(angle - asymmetry * y)``; ``sin(angle)`` at zero asymmetry."""
    if asymmetry == 0:
        return math.sin(angle)
    low, high = -1.0, 1.0
    for _ in range(_STEPS):
        middle = (low + high) / 2
        if middle - math.sin(angle - asymmetry * middle) < 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def autoregression(
    *, innovations: Sequence[float], parameter: float
) -> tuple[float, ...]:
    """Add each innovation to ``parameter`` times the previous value (AR(1))."""
    _require_finite(parameter=parameter)
    if not all(math.isfinite(x) for x in innovations):
        raise ContractError("autoregression innovations must be finite")
    values: list[float] = []
    for innovation in innovations:
        values.append(innovation + (parameter * values[-1] if values else 0))
    return tuple(values)


def accumulate_volatility(
    *,
    trend: Sequence[float],
    returns: Sequence[float],
    growth: float,
    mean_reversion: float,
) -> tuple[float, ...]:
    """Return a level that starts at the trend and takes each later return.

    Each later level is the previous level times ``1 + growth + return``,
    plus ``mean_reversion`` times the distance of the previous level from the
    previous trend value.
    """
    if len(trend) != len(returns):
        raise ContractError(
            "the trend and the returns need one value for each Period",
            values={"trend": len(trend), "returns": len(returns)},
        )
    _require_finite(growth=growth, mean_reversion=mean_reversion)
    if not all(math.isfinite(x) for x in (*trend, *returns)):
        raise ContractError("the trend and the returns must be finite")
    result: list[float] = []
    for i, level in enumerate(trend):
        result.append(
            level
            if i == 0
            else result[-1] * (1 + growth + returns[i])
            + mean_reversion * (trend[i - 1] - result[-1])
        )
    _require_result(result, "volatility")
    return tuple(result)


def shock(
    *,
    events: Sequence[float],
    probability: float,
    dissipation: float,
    size: float,
) -> tuple[float, ...]:
    """Return a shock of ``size`` at the first event below ``probability``, then its decay.

    The shock happens once at most. Each later Period keeps ``1 - dissipation``
    of the shock of the Period before. The events are draws in [0, 1].
    """
    if (
        not 0 <= probability <= 1
        or not 0 <= dissipation <= 1
        or not math.isfinite(size)
    ):
        raise ContractError(
            "a shock needs a probability and a dissipation from 0 to 1 and a "
            "finite size",
            values={"probability": probability, "dissipation": dissipation},
        )
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in events):
        raise ContractError("shock events must be draws from 0 to 1")
    first = next((i for i, event in enumerate(events) if event < probability), None)
    return tuple(
        0.0 if first is None or i < first else size * (1 - dissipation) ** (i - first)
        for i in range(len(events))
    )


def _require_count(count: int) -> None:
    if type(count) is not int:
        raise TypeError("count must be an int")
    if count < 0:
        raise ContractError(
            f"count must not be negative, not {count}", values={"count": count}
        )


def _require_finite(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value):
            raise ContractError(
                f"{name} must be finite, not {value}", values={name: value}
            )


def _require_result(values: Sequence[float], name: str) -> None:
    if not all(math.isfinite(x) for x in values):
        raise NumericalError(f"the {name} overflowed")
