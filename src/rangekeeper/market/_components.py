"""The components of market dynamics, each with its own parameters per Period.

A component holds numbers per Period: ``rk.market.Dynamics`` converts its
parameters, such as ``"5 % pa"``, for the Periods of the paths. Each random
component draws from its own stream, so adding a component does not change
the draws of another. ``path`` composes the components over supplied draws
and draws no random numbers itself.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from rangekeeper.market._kernels import (
    accumulate_volatility,
    autoregression,
    cycle,
    shock,
    trend,
)

__all__ = [
    "Components",
    "Cycle",
    "Draws",
    "Noise",
    "Shock",
    "Trend",
    "Volatility",
    "path",
]

# The fixed conventions of the market method (ADR-014): the autoregression and
# mean reversion of the volatility, and the share of a shock that ends in each
# Period, as in rk 0.8 and the earlier scenario plan.
AUTOREGRESSION = 0.2
MEAN_REVERSION = 0.1
DISSIPATION = 0.5


class Generator(Protocol):
    """The part of a NumPy random Generator that the components use."""

    def normal(self, loc: float, scale: float, size: int) -> Sequence[float]:
        """Draw normal values."""
        ...

    def uniform(self, low: float, high: float, size: int) -> Sequence[float]:
        """Draw uniform values."""
        ...


@dataclass(frozen=True, kw_only=True)
class Trend:
    """Compound growth from 1: ``growth`` is the growth in each Period."""

    growth: float

    def level(self, *, count: int) -> tuple[float, ...]:
        """Return the trend of each Period, starting at 1."""
        return trend(count=count, rate=self.growth)


@dataclass(frozen=True, kw_only=True)
class Cycle:
    """A sine around the trend: ``period`` and ``phase`` in Periods, ``amplitude`` a ratio.

    The amplitude is half the peak-to-trough height.
    """

    period: float
    amplitude: float
    phase: float = 0.0

    def factors(self, *, count: int) -> tuple[float, ...]:
        """Return the factor ``1 + cycle`` of each Period."""
        values = cycle(
            count=count, period=self.period, phase=self.phase, amplitude=self.amplitude
        )
        return tuple(1 + value for value in values)


@dataclass(frozen=True, kw_only=True)
class Volatility:
    """Random returns around the trend, with autoregression and mean reversion.

    ``scale`` is the standard deviation of the innovation of each Period.
    """

    scale: float
    autoregression: float = AUTOREGRESSION
    mean_reversion: float = MEAN_REVERSION

    def draw(self, *, count: int, generator: Generator) -> tuple[float, ...]:
        """Draw the innovation of each Period from its stream."""
        return tuple(float(x) for x in generator.normal(0, self.scale, count))

    def level(
        self,
        *,
        trend: Sequence[float],
        growth: float,
        innovations: Sequence[float],
    ) -> tuple[float, ...]:
        """Return the level after the returns of each Period."""
        returns = autoregression(innovations=innovations, parameter=self.autoregression)
        return accumulate_volatility(
            trend=trend,
            returns=returns,
            growth=growth,
            mean_reversion=self.mean_reversion,
        )


@dataclass(frozen=True, kw_only=True)
class Noise:
    """Independent noise in each Period, uniform from ``-width`` to ``width``."""

    width: float

    def draw(self, *, count: int, generator: Generator) -> tuple[float, ...]:
        """Draw the noise of each Period from its stream."""
        return tuple(
            float(x) for x in generator.uniform(-self.width, self.width, count)
        )

    @staticmethod
    def factors(*, draws: Sequence[float]) -> tuple[float, ...]:
        """Return the factor ``1 + noise`` of each Period."""
        return tuple(1 + value for value in draws)


@dataclass(frozen=True, kw_only=True)
class Shock:
    """One rare shock at most: its probability in each Period, its size and its decay."""

    probability: float
    size: float
    dissipation: float = DISSIPATION

    @staticmethod
    def draw(*, count: int, generator: Generator) -> tuple[float, ...]:
        """Draw the event of each Period, from 0 to 1, from its stream."""
        return tuple(float(x) for x in generator.uniform(0, 1, count))

    def factors(self, *, events: Sequence[float]) -> tuple[float, ...]:
        """Return the factor ``1 + shock`` of each Period."""
        values = shock(
            events=events,
            probability=self.probability,
            dissipation=self.dissipation,
            size=self.size,
        )
        return tuple(1 + value for value in values)


@dataclass(frozen=True, kw_only=True)
class Components:
    """The components of one series, in Periods."""

    trend: Trend
    cycle: Cycle | None = None
    volatility: Volatility | None = None
    noise: Noise | None = None
    shock: Shock | None = None


@dataclass(frozen=True, kw_only=True)
class Draws:
    """The draws of one path of one series; None for a component that it lacks."""

    innovations: tuple[float, ...] | None = None
    noise: tuple[float, ...] | None = None
    events: tuple[float, ...] | None = None


def path(*, components: Components, count: int, draws: Draws) -> tuple[float, ...]:
    """Return one path of a series from its components and its draws.

    The level is the trend, after the volatility returns when there is
    volatility. The cycle, the noise and the shock each multiply it by one
    plus their value.
    """
    trend = components.trend.level(count=count)
    values = trend
    if components.volatility is not None:
        assert draws.innovations is not None
        values = components.volatility.level(
            trend=trend, growth=components.trend.growth, innovations=draws.innovations
        )
    factors: list[tuple[float, ...]] = []
    if components.cycle is not None:
        factors.append(components.cycle.factors(count=count))
    if components.noise is not None:
        assert draws.noise is not None
        factors.append(Noise.factors(draws=draws.noise))
    if components.shock is not None:
        assert draws.events is not None
        factors.append(components.shock.factors(events=draws.events))
    for factor in factors:
        values = tuple(v * f for v, f in zip(values, factor, strict=True))
    return values
