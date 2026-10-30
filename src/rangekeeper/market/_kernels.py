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


def trend(*, count: int, rate: float) -> tuple[float, ...]:
    """Return 1 compounded at ``rate`` for each Period: ``(1 + rate) ** i``."""
    _require_count(count)
    _require_finite(rate=rate)
    values = tuple((1 + rate) ** i for i in range(count))
    _require_result(values, "trend")
    return values


def cycle(
    *,
    count: int,
    period: float,
    phase: float,
    amplitude: float,
) -> tuple[float, ...]:
    """Return a sine of ``amplitude`` with ``period`` and ``phase`` in Periods.

    ``amplitude`` is half the peak-to-trough height.
    """
    _require_count(count)
    _require_finite(period=period, phase=phase, amplitude=amplitude)
    if period <= 0:
        raise ContractError(
            f"a cycle needs a positive period, not {period}",
            values={"period": period},
        )
    return tuple(
        amplitude * math.sin((i - phase) * 2 * math.pi / period) for i in range(count)
    )


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
