"""Named market-component constructors, returning shared ScenarioParameter records.

These functions declare normalized, dimensionless inputs. They do not generate
paths, consume randomness, mutate Models or write files. Bounds/distributions are
validated when the complete ScenarioPlan is built. Cycle amplitudes are half the
peak-to-trough height; phase and period are measured in the plan's period steps.
"""

from typing import cast

from .contracts import DIRECT
from ..model import Quantity
from ..model.scenario import Distribution, ScenarioParameter

ParameterInput = float | Quantity | Distribution


def _parameters(**values: ParameterInput) -> tuple[ScenarioParameter, ...]:
    return tuple(
        (
            ScenarioParameter(name=name, distribution=value)
            if isinstance(value, Distribution)
            else ScenarioParameter(
                name=name,
                quantity=(
                    value
                    if isinstance(value, Quantity)
                    else Quantity(magnitude=value, units="dimensionless")
                ),
            )
        )
        for name, value in values.items()
    )


def make_trend(
    *,
    initial_value: ParameterInput = cast(float, DIRECT["initial_value"].default),
    growth_rate: ParameterInput = cast(float, DIRECT["growth_rate"].default),
    cap_rate: ParameterInput = cast(float, DIRECT["cap_rate"].default),
) -> tuple[ScenarioParameter, ...]:
    """Declare the initial rental level, per-period growth and long-run cap rate."""
    return _parameters(
        initial_value=initial_value, growth_rate=growth_rate, cap_rate=cap_rate
    )


def make_volatility(
    *,
    volatility_per_period: ParameterInput = cast(
        float, DIRECT["volatility_per_period"].default
    ),
    autoregression: ParameterInput = cast(float, DIRECT["autoregression"].default),
    mean_reversion: ParameterInput = cast(float, DIRECT["mean_reversion"].default),
) -> tuple[ScenarioParameter, ...]:
    """Declare innovation scale and the return/level dependence parameters."""
    return _parameters(
        volatility_per_period=volatility_per_period,
        autoregression=autoregression,
        mean_reversion=mean_reversion,
    )


def make_cyclicality(
    *,
    space_period: ParameterInput = cast(float, DIRECT["space_period"].default),
    space_phase: ParameterInput = cast(float, DIRECT["space_phase"].default),
    space_amplitude: ParameterInput = cast(float, DIRECT["space_amplitude"].default),
    space_asymmetry: ParameterInput = cast(float, DIRECT["space_asymmetry"].default),
    asset_period: ParameterInput = cast(float, DIRECT["asset_period"].default),
    asset_phase: ParameterInput = cast(float, DIRECT["asset_phase"].default),
    asset_amplitude: ParameterInput = cast(float, DIRECT["asset_amplitude"].default),
    asset_asymmetry: ParameterInput = cast(float, DIRECT["asset_asymmetry"].default),
) -> tuple[ScenarioParameter, ...]:
    """Declare two cycles from direct parameters; amplitudes are not full heights."""
    return _parameters(
        space_period=space_period,
        space_phase=space_phase,
        space_amplitude=space_amplitude,
        space_asymmetry=space_asymmetry,
        asset_period=asset_period,
        asset_phase=asset_phase,
        asset_amplitude=asset_amplitude,
        asset_asymmetry=asset_asymmetry,
    )


def make_noise(
    *,
    lower: ParameterInput = cast(float, DIRECT["noise_lower"].default),
    upper: ParameterInput = cast(float, DIRECT["noise_upper"].default),
) -> tuple[ScenarioParameter, ...]:
    """Declare the uniform deal-noise bounds used by the current market method."""
    return _parameters(noise_lower=lower, noise_upper=upper)


def make_black_swan(
    *,
    likelihood: ParameterInput = cast(float, DIRECT["shock_likelihood"].default),
    impact: ParameterInput = cast(float, DIRECT["shock_impact"].default),
    dissipation: ParameterInput = cast(float, DIRECT["shock_dissipation"].default),
) -> tuple[ScenarioParameter, ...]:
    """Declare the once-per-scenario shock recipe; its impact is applied once."""
    return _parameters(
        shock_likelihood=likelihood, shock_impact=impact, shock_dissipation=dissipation
    )
