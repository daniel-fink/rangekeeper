"""Named market-component constructors, returning shared ScenarioParameter records.

These functions declare normalized, dimensionless inputs. They do not generate
paths, consume randomness, mutate Models or write files. Bounds/distributions are
validated when the complete ScenarioPlan is built. Cycle amplitudes are half the
peak-to-trough height; phase and period are measured in the plan's period steps.
"""

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
    initial_value: ParameterInput = 0.05,
    growth_rate: ParameterInput = 0.02,
    cap_rate: ParameterInput = 0.05,
) -> tuple[ScenarioParameter, ...]:
    """Declare the initial rental level, per-period growth and long-run cap rate."""
    return _parameters(
        initial_value=initial_value, growth_rate=growth_rate, cap_rate=cap_rate
    )


def make_volatility(
    *,
    volatility_per_period: ParameterInput = 0.03,
    autoregression: ParameterInput = 0.2,
    mean_reversion: ParameterInput = 0.1,
) -> tuple[ScenarioParameter, ...]:
    """Declare innovation scale and the return/level dependence parameters."""
    return _parameters(
        volatility_per_period=volatility_per_period,
        autoregression=autoregression,
        mean_reversion=mean_reversion,
    )


def make_cyclicality(
    *,
    space_period: ParameterInput = 10.0,
    space_phase: ParameterInput = 0.0,
    space_amplitude: ParameterInput = 0.1,
    space_asymmetry: ParameterInput = 0.0,
    asset_period: ParameterInput = 10.0,
    asset_phase: ParameterInput = 2.0,
    asset_amplitude: ParameterInput = 0.005,
    asset_asymmetry: ParameterInput = 0.0,
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
    *, lower: ParameterInput = -0.02, upper: ParameterInput = 0.02
) -> tuple[ScenarioParameter, ...]:
    """Declare the uniform deal-noise bounds used by the current market method."""
    return _parameters(noise_lower=lower, noise_upper=upper)


def make_black_swan(
    *,
    likelihood: ParameterInput = 0.02,
    impact: ParameterInput = -0.2,
    dissipation: ParameterInput = 0.5,
) -> tuple[ScenarioParameter, ...]:
    """Declare the once-per-scenario shock recipe; its impact is applied once."""
    return _parameters(
        shock_likelihood=likelihood, shock_impact=impact, shock_dissipation=dissipation
    )
