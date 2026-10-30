"""The dynamics of a market series, and the paths that they generate (ADR-014).

``Dynamics`` declares how one series moves: a trend, with an optional cycle,
volatility, noise and shock. ``generate`` makes market paths of one named
series or several, each independent. The built-in path generator
``dynamics`` makes them, so ``Paths.regenerate`` makes them again.
"""

import hashlib
import json
import math
import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from rangekeeper.duration import Period
from rangekeeper.market._components import (
    Components,
    Cycle,
    Draws,
    Noise,
    Shock,
    Trend,
    Volatility,
    path,
)
from rangekeeper.market.generator import generators
from rangekeeper.market.paths import Paths
from rangekeeper.profile import Distribution, period_scales
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema.records import (
    LibraryVersion,
    MarketPath,
    PathAmounts,
    PathCapture,
    PathParameter,
    PathSeries,
    RandomStream,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, UnitError
from rangekeeper.shared.optional import requires

__all__ = ["Dynamics", "DynamicsGenerator", "generate"]

Parameter = Quantity | str | float | Distribution
Value = Quantity | Distribution
NAME: Final = "dynamics"
ALGORITHM: Final = "numpy.SeedSequence/PCG64"
_ZERO_LAG: Final = "0 days"
# The share of the remaining shock that ends in each year, as before #299.
_DISSIPATION: Final = 0.5


@dataclass(frozen=True)
class _Rule:
    """The units of one parameter and the range of its values in those units."""

    units: str
    lower: float | None = None
    upper: float | None = None
    # The value must be greater than ``lower``, not equal to it.
    above: bool = False

    def check(self, value: float, *, name: str) -> None:
        """Raise ContractError for a value outside the range."""
        low = self.lower is not None and (
            value < self.lower or (self.above and value == self.lower)
        )
        high = self.upper is not None and value > self.upper
        if not math.isfinite(value) or low or high:
            raise ContractError(
                f"{name} {value} {self.units} is outside its range",
                values={"name": name, "value": value, "units": self.units},
            )


# Each parameter, in order, with its units and range. Rates are per year;
# the generator converts them for the Periods of the paths.
_RULES: Final = {
    "trend": _Rule("pa", -1, above=True),
    "cycle_period": _Rule("year", 0, above=True),
    "cycle_amplitude": _Rule("ratio"),
    "volatility": _Rule("pa", 0),
    "noise": _Rule("ratio", 0),
    "shock_probability": _Rule("pa", 0, 1),
    "shock_size": _Rule("ratio", -1),
}
# The parameters that are given together: each pair makes one component.
_PAIRS: Final = (
    ("cycle_period", "cycle_amplitude"),
    ("shock_probability", "shock_size"),
)
# The parameter that makes each random component.
_RANDOM: Final = {
    "volatility": "volatility",
    "noise": "noise",
    "shock": "shock_probability",
}


class Dynamics:
    """How one market series moves: a trend, with an optional cycle, volatility, noise and shock.

    Each parameter is a Quantity, its text or a ``rk.model.Distribution`` that
    each path draws from once. A ratio can also be a number.

    - ``trend``: the growth per year, such as ``"2 % pa"``;
    - ``cycle_period`` and ``cycle_amplitude``: the length of a cycle, such as
      ``"10 years"``, and half its peak-to-trough height, such as ``"10 %"``;
    - ``volatility``: the standard deviation of the yearly returns, such as
      ``"5 % pa"``. The returns follow an AR(1) process with coefficient 0.2,
      and in each Period the level reverts by 10 % of its distance from the
      trend;
    - ``noise``: the half-width of independent uniform noise in each Period,
      such as ``"2 %"``;
    - ``shock_probability`` and ``shock_size``: the chance per year of one rare
      shock, such as ``"2 % pa"``, and its size, such as ``"-25 %"``. Half of
      the remaining shock ends in each later year.

    A cycle needs its period and its amplitude, and a shock its probability
    and its size. The series starts at 1. Volatility, noise and shocks are
    random, and so is a parameter that is a Distribution: ``generate`` needs a
    seed for them. ``replace`` returns new Dynamics with some parameters
    changed.
    """

    __slots__ = ("_values",)
    _values: Mapping[str, Value]

    def __init__(  # noqa: PLR0913 - the parameters of the proposed cells (G29)
        self,
        *,
        trend: Parameter = "0 % pa",
        cycle_period: Parameter | None = None,
        cycle_amplitude: Parameter | None = None,
        volatility: Parameter | None = None,
        noise: Parameter | None = None,
        shock_probability: Parameter | None = None,
        shock_size: Parameter | None = None,
    ) -> None:
        given = {
            "trend": trend,
            "cycle_period": cycle_period,
            "cycle_amplitude": cycle_amplitude,
            "volatility": volatility,
            "noise": noise,
            "shock_probability": shock_probability,
            "shock_size": shock_size,
        }
        values = {
            name: _value(value, name=name)
            for name, value in given.items()
            if value is not None
        }
        _require_pairs(values)
        object.__setattr__(self, "_values", values)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Dynamics is immutable; use replace")

    def replace(  # noqa: PLR0913 - the parameters of __init__
        self,
        *,
        trend: Parameter | None = None,
        cycle_period: Parameter | None = None,
        cycle_amplitude: Parameter | None = None,
        volatility: Parameter | None = None,
        noise: Parameter | None = None,
        shock_probability: Parameter | None = None,
        shock_size: Parameter | None = None,
    ) -> "Dynamics":
        """Return new Dynamics with the parameters given here changed; the others stay."""
        changes = {
            "trend": trend,
            "cycle_period": cycle_period,
            "cycle_amplitude": cycle_amplitude,
            "volatility": volatility,
            "noise": noise,
            "shock_probability": shock_probability,
            "shock_size": shock_size,
        }
        merged: dict[str, Any] = dict(self._values)
        merged.update({k: v for k, v in changes.items() if v is not None})
        return Dynamics(**merged)

    @property
    def parameters(self) -> Mapping[str, Value]:
        """The parameters that are given, by name, each a Quantity or a Distribution."""
        return dict(self._values)

    @property
    def random(self) -> tuple[str, ...]:
        """The random components, then each parameter that is a Distribution."""
        found = [
            component
            for component, parameter in _RANDOM.items()
            if parameter in self._values
        ]
        found.extend(
            name
            for name, value in self._values.items()
            if isinstance(value, Distribution)
        )
        return tuple(found)

    def records(self, *, series: str) -> tuple[PathParameter, ...]:
        """Return the parameters as the capture record keeps them, for one series."""
        return tuple(
            PathParameter(series=series, name=name, distribution=value)
            if isinstance(value, Distribution)
            else PathParameter(series=series, name=name, quantity=value)
            for name, value in self._values.items()
        )

    @classmethod
    def from_records(cls, records: Sequence[PathParameter]) -> "Dynamics":
        """Return the Dynamics of the parameter records of one series."""
        values: dict[str, Any] = {}
        for record in records:
            if record.name not in _RULES:
                raise ContractError(
                    f"{record.name} is not a parameter of Dynamics",
                    values={"name": record.name, "parameters": list(_RULES)},
                )
            values[record.name] = (
                record.quantity if record.distribution is None else record.distribution
            )
        return cls(**values)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dynamics):
            return NotImplemented
        return self.records(series="x") == other.records(series="x")

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        parts = ", ".join(
            f"{name}={_text(value)!r}" for name, value in self._values.items()
        )
        return f"Dynamics({parts})"


def generate(
    *,
    dynamics: Mapping[str, Dynamics],
    periods: Sequence[Period],
    seed: int | None = None,
    count: int,
) -> Paths:
    """Make ``count`` paths of each named series over ``periods``.

    ``dynamics`` maps each series name to its Dynamics; the series are
    independent. Random dynamics need ``seed``, a whole number of zero or
    more, and the same seed gives the same paths. Without a seed, random
    dynamics raise ContractError, which names the random components; fixed
    dynamics take no seed. The Periods must have one length. The capture
    record keeps the parameters and the seed, so ``Paths.regenerate`` makes
    the paths again.
    """
    if not isinstance(dynamics, Mapping) or not dynamics:
        raise TypeError("dynamics takes a mapping from each series name to Dynamics")
    for name, item in dynamics.items():
        if not isinstance(name, str) or not isinstance(item, Dynamics):
            raise TypeError(
                "dynamics takes a mapping from each series name to Dynamics"
            )
    records = tuple(
        record
        for name, item in dynamics.items()
        for record in item.records(series=name)
    )
    return GENERATOR.generate(
        parameters=records, periods=periods, seed=seed, count=count
    )


class DynamicsGenerator:
    """The built-in path generator of ``Dynamics``, registered as ``dynamics``.

    Each path of each series draws from its own streams: one for each random
    component and each distributed parameter, seeded by the seed, the index
    of the path and the stream's identifier. So the first paths are the same
    whatever the count, and adding a series changes no other series.
    """

    def generate(
        self,
        *,
        parameters: Sequence[PathParameter],
        periods: Sequence[Period],
        seed: int | None,
        count: int,
    ) -> Paths:
        """Return ``count`` paths of each series of ``parameters`` over ``periods``."""
        dynamics = _by_series(parameters)
        _require_count(count)
        sequence = tuple(periods)
        step = _step(sequence)
        _require_seed(dynamics, seed=seed)
        width = len(str(count))
        members = [
            MarketPath(
                key=f"path_{index + 1:0{width}d}",
                amounts=tuple(
                    PathAmounts(
                        series=name,
                        magnitudes=_series(
                            item,
                            streams=_Streams(seed=seed, series=name, index=index),
                            step=step,
                            count=len(sequence),
                        ),
                    )
                    for name, item in dynamics.items()
                ),
            )
            for index in range(count)
        ]
        return Paths.create(
            periods=sequence,
            series=tuple(
                PathSeries(name=name, units="ratio", lag=Quantity(text=_ZERO_LAG))
                for name in dynamics
            ),
            members=members,
            capture=_capture(dynamics, parameters=parameters, seed=seed, count=count),
        )


GENERATOR: Final = DynamicsGenerator()
generators.register(name=NAME, implementation=GENERATOR)


def _value(value: Parameter, *, name: str) -> Value:
    """Return a parameter as a Quantity or a Distribution, after its units and range."""
    rule = _RULES[name]
    if isinstance(value, Distribution):
        _require_units(value.units, rule=rule, name=name)
        for bound in (value.lower, value.upper):
            quantity = Quantity(magnitude=bound, units=value.units)
            rule.check(_number(quantity, rule), name=name)
        return value
    if isinstance(value, str):
        quantity = Quantity(text=value)
    elif isinstance(value, Quantity):
        quantity = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        quantity = Quantity(magnitude=value, units="ratio")
    else:
        raise TypeError(f"{name} must be a Quantity, its text or a Distribution")
    _require_units(quantity.units, rule=rule, name=name)
    rule.check(_number(quantity, rule), name=name)
    return quantity


def _require_units(units: str, *, rule: _Rule, name: str) -> None:
    """Raise UnitError for units that do not convert to the units of the parameter."""
    if not default_units.compatible(units, rule.units):
        raise UnitError(
            f"{name} takes units like {rule.units!r}, not {units!r}",
            code=Code.INCOMPATIBLE_UNITS,
        )


def _number(quantity: Quantity, rule: _Rule) -> float:
    """Return a Quantity as a number in the units of the parameter."""
    return default_units.convert(quantity=quantity, to=rule.units).number


def _require_pairs(values: Mapping[str, Value]) -> None:
    """Require both parameters of a cycle and of a shock, or neither."""
    for first, second in _PAIRS:
        if (first in values) != (second in values):
            missing = second if first in values else first
            raise ContractError(
                f"{first} and {second} are given together; give {missing}",
                values={"missing": missing},
            )


def _text(value: Value) -> str:
    """Return a parameter as text."""
    if isinstance(value, Distribution):
        return f"{value.kind} {value.lower} to {value.upper} {value.units}"
    return str(value)


def _by_series(parameters: Sequence[PathParameter]) -> dict[str, Dynamics]:
    """Return the Dynamics of each series of the parameter records, in order."""
    grouped: dict[str, list[PathParameter]] = {}
    for record in parameters:
        if not isinstance(record, PathParameter):
            raise TypeError("parameters must be PathParameter records")
        grouped.setdefault(record.series, []).append(record)
    if not grouped:
        raise ContractError("the dynamics generator needs the parameters of a series")
    return {name: Dynamics.from_records(items) for name, items in grouped.items()}


def _require_count(count: int) -> None:
    """Require a count of one path or more."""
    if type(count) is not int:
        raise TypeError("count must be an int")
    if count < 1:
        raise ContractError(
            f"count must be at least 1, not {count}", values={"count": count}
        )


def _step(periods: tuple[Period, ...]) -> float:
    """Return the length of each Period in years; the Periods must have one length."""
    if not periods:
        raise ContractError("generate needs at least one Period")
    lengths = period_scales(units="pa", periods=periods)
    if any(not math.isclose(x, lengths[0], rel_tol=1e-12) for x in lengths):
        raise ContractError(
            "generate needs Periods of one length",
            values={"lengths": sorted(set(lengths))},
        )
    return lengths[0]


def _require_seed(dynamics: Mapping[str, Dynamics], *, seed: int | None) -> None:
    """Require a seed for random dynamics, and no seed for fixed dynamics."""
    random = {name: list(item.random) for name, item in dynamics.items() if item.random}
    if seed is None:
        if random:
            listed = "; ".join(
                f"{name}: {', '.join(parts)}" for name, parts in random.items()
            )
            raise ContractError(
                f"these dynamics are random, so generate needs a seed: {listed}",
                values={"random": random},
            )
        return
    if type(seed) is not int:
        raise TypeError("seed must be an int")
    if not random:
        raise ContractError(
            "these dynamics are fixed, so they take no seed", values={"seed": seed}
        )
    if seed < 0:
        raise ContractError(
            f"seed must not be negative, not {seed}", values={"seed": seed}
        )


def identifier(*, series: str, component: str) -> str:
    """Return the SHA-256 hexadecimal digest that names one random stream."""
    text = json.dumps([series, component], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, kw_only=True)
class _Streams:
    """The random streams of one series in one path."""

    seed: int | None
    series: str
    index: int

    def generator(self, component: str) -> Any:
        """Return a fresh NumPy Generator for one component of this path."""
        assert self.seed is not None
        with requires("calculations"):
            import numpy as np  # noqa: PLC0415 - optional dependency

        digest = bytes.fromhex(identifier(series=self.series, component=component))
        words = [int.from_bytes(digest[i : i + 4], "big") for i in range(0, 32, 4)]
        return np.random.Generator(
            np.random.PCG64(np.random.SeedSequence([self.seed, self.index, *words]))
        )


def _parameter_stream(name: str) -> str:
    """Return the name of the stream that a distributed parameter draws from."""
    return f"parameter.{name}"


def _stream_names(item: Dynamics) -> tuple[str, ...]:
    """Return the names of the random streams of one series, in order."""
    return tuple(
        component if component in _RANDOM else _parameter_stream(component)
        for component in item.random
    )


def _numbers(item: Dynamics, *, streams: _Streams) -> dict[str, float]:
    """Return each parameter in its units; a Distribution draws once from its stream."""
    numbers = {}
    for name, value in item.parameters.items():
        quantity = value
        if isinstance(value, Distribution):
            stream = streams.generator(_parameter_stream(name))
            (drawn,) = value.sample(size=1, generator=stream)
            quantity = Quantity(magnitude=drawn, units=value.units)
        assert isinstance(quantity, Quantity)
        numbers[name] = _number(quantity, _RULES[name])
    return numbers


def components(numbers: Mapping[str, float], *, step: float) -> Components:
    """Return the components of a series in Periods of ``step`` years.

    ``numbers`` are the parameters of Dynamics in their units: rates per
    year, lengths in years and ratios.
    """
    cycle = volatility = noise = shock = None
    if "cycle_period" in numbers:
        cycle = Cycle(
            period=numbers["cycle_period"] / step,
            amplitude=numbers["cycle_amplitude"],
        )
    if "volatility" in numbers:
        volatility = Volatility(scale=numbers["volatility"] * math.sqrt(step))
    if "noise" in numbers:
        noise = Noise(width=numbers["noise"])
    if "shock_probability" in numbers:
        shock = Shock(
            probability=1 - (1 - numbers["shock_probability"]) ** step,
            size=numbers["shock_size"],
            dissipation=1 - (1 - _DISSIPATION) ** step,
        )
    return Components(
        trend=Trend(growth=(1 + numbers["trend"]) ** step - 1),
        cycle=cycle,
        volatility=volatility,
        noise=noise,
        shock=shock,
    )


def _series(
    item: Dynamics, *, streams: _Streams, step: float, count: int
) -> tuple[float, ...]:
    """Return one path of one series: its draws, then its components over them."""
    parts = components(_numbers(item, streams=streams), step=step)
    innovations = noise = events = None
    if parts.volatility is not None:
        innovations = parts.volatility.draw(
            count=count, generator=streams.generator("volatility")
        )
    if parts.noise is not None:
        noise = parts.noise.draw(count=count, generator=streams.generator("noise"))
    if parts.shock is not None:
        events = Shock.draw(count=count, generator=streams.generator("shock"))
    draws = Draws(innovations=innovations, noise=noise, events=events)
    return path(components=parts, count=count, draws=draws)


def _capture(
    dynamics: Mapping[str, Dynamics],
    *,
    parameters: Sequence[PathParameter],
    seed: int | None,
    count: int,
) -> PathCapture:
    """Return the capture record: generator, fingerprint, parameters, seed and versions."""
    registration = generators.describe(GENERATOR)
    python = LibraryVersion(name="python", version=platform.python_version())
    if seed is None:
        return PathCapture(
            generator=registration.name,
            fingerprint=registration.fingerprint,
            count=count,
            parameters=tuple(parameters),
            streams=(),
            versions=(python,),
        )
    with requires("calculations"):
        import numpy as np  # noqa: PLC0415 - optional dependency
    streams = tuple(
        RandomStream(
            name=f"{name}.{stream}",
            identifier=identifier(series=name, component=stream),
        )
        for name, item in dynamics.items()
        for stream in _stream_names(item)
    )
    return PathCapture(
        generator=registration.name,
        fingerprint=registration.fingerprint,
        seed=seed,
        count=count,
        parameters=tuple(parameters),
        algorithm=ALGORITHM,
        streams=streams,
        versions=(python, LibraryVersion(name="numpy", version=np.__version__)),
    )
