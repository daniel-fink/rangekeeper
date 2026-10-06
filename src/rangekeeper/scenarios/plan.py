"""Construct complete market plans with explicit, recorded defaults."""

from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4
from typing import cast
from ..model.scenario import ScenarioPlan, ScenarioParameter, Distribution
from ..model.duration import Period
from ..model import Quantity
from ..model._scenario import validate_plan

# Defaults are authoring conveniences. Every chosen value is stored in the plan.
MARKET_DEFAULTS = dict(
    initial_value=0.05,
    growth_rate=0.02,
    cap_rate=0.05,
    volatility_per_period=0.03,
    autoregression=0.2,
    mean_reversion=0.1,
    space_period=10.0,
    space_phase=0.0,
    space_amplitude=0.1,
    space_asymmetry=0.0,
    asset_period=10.0,
    asset_phase=2.0,
    asset_amplitude=0.005,
    asset_asymmetry=0.0,
    noise_lower=-0.02,
    noise_upper=0.02,
    shock_likelihood=0.02,
    shock_dissipation=0.5,
    shock_impact=-0.2,
)


def make_plan(
    *,
    periods: Sequence[Period],
    seed: int,
    parameters: Mapping[str, float | Quantity | Distribution] | None = None,
    components: Sequence[Sequence[ScenarioParameter]] = (),
    id: UUID | None = None,
    method: str = "market.v2",
) -> ScenarioPlan:
    """Build a recorded plan; reject unknown names and incomplete independent plans.

    Components supply named parameter groups; duplicate explicit declarations fail.
    Market paths are normalized, dimensionless valuation factors. Use their
    factors with unit-bearing investment Flows. Independent plans sample paired
    space_factor and asset_cap distributions once per period.
    """
    values: dict[str, float | Quantity | Distribution] = (
        dict(MARKET_DEFAULTS) if method.startswith("market.") else {}
    )
    if method == "market.estimates.v2":
        for key in ("space_phase", "asset_phase", "asset_period"):
            values.pop(key)
        values.update(
            space_phase_proportion=0.0,
            asset_phase_difference=0.1,
            asset_period_difference=0.0,
        )
    declared = dict(parameters or {})
    for component in components:
        for parameter in component:
            if parameter.name in declared:
                raise ValueError(f"duplicate component parameter: {parameter.name}")
            if (parameter.quantity is None) == (parameter.distribution is None):
                raise ValueError(
                    "component requires exactly one quantity or distribution"
                )
            declared[parameter.name] = (
                parameter.quantity
                if parameter.quantity is not None
                else cast(Distribution, parameter.distribution)
            )
    parameters = declared
    if parameters:
        if method.startswith("market.") and set(parameters) - set(values):
            raise ValueError("unknown market parameter")
        values.update(parameters)
    records = []
    for name, value in sorted(values.items()):
        if isinstance(value, Distribution):
            records.append(ScenarioParameter(name=name, distribution=value))
        else:
            records.append(
                ScenarioParameter(
                    name=name,
                    quantity=(
                        value
                        if isinstance(value, Quantity)
                        else Quantity(magnitude=value, units="dimensionless")
                    ),
                )
            )
    plan = ScenarioPlan(
        id=id or uuid4(),
        method=method,
        seed=seed,
        periods=tuple(periods),
        parameters=tuple(records),
    )
    validate_plan(plan.to_data())
    return plan


def validate(plan: ScenarioPlan) -> None:
    """Validate a complete generation plan without drawing randomness or writing IO."""
    validate_plan(plan.to_data())
