"""Known-input path construction using the characterized numerical kernels."""

import math
from ..calculations.dynamics.trend import calculate_trend
from ..calculations.dynamics.volatility import (
    calculate_autoregression,
    accumulate_volatility,
)
from ..calculations.dynamics.cyclicality import calculate_cycle
from ..calculations.dynamics.shock import calculate_shock


def construct_paths(method, parameters, draws):
    """Return named arrays and forward-dependency offsets, with no randomness."""
    if method == "independent.v2":
        factors, caps = draws["space_factor"], draws["asset_cap"]
        if any(c <= 0 for c in caps):
            raise ValueError("capitalization rates must be positive")
        return {
            "space_market_price_factors": factors,
            "asset_market": caps,
            "historical_value": tuple(f / c for f, c in zip(factors, caps)),
        }, {}
    p = dict(parameters)
    if method == "market.estimates.v2":
        # Preserve the old linked cycle estimates: phase differences are fractions
        # of the space cycle, and period differences are measured in periods.
        p["space_phase"] = p["space_period"] * p["space_phase_proportion"]
        p["asset_phase"] = (
            p["space_phase"] + p["asset_phase_difference"] * p["space_period"]
        )
        p["asset_period"] = p["space_period"] + p["asset_period_difference"]
    count = len(draws["innovations"])
    if p["initial_value"] <= 0 or p["cap_rate"] <= 0 or p["volatility_per_period"] < 0:
        raise ValueError(
            "initial value/capitalization must be positive; volatility nonnegative"
        )
    trend = calculate_trend(
        count=count,
        growth_rate=p["growth_rate"],
        cap_rate=p["cap_rate"],
        initial_value=p["initial_value"],
    )
    ar = calculate_autoregression(draws["innovations"], parameter=p["autoregression"])
    volatility = accumulate_volatility(
        trend, ar, growth_rate=p["growth_rate"], mean_reversion=p["mean_reversion"]
    )
    space_cycle = calculate_cycle(
        count=count,
        period=p["space_period"],
        phase=p["space_phase"],
        amplitude=p["space_amplitude"],
        asymmetry=p["space_asymmetry"],
    )
    asset_cycle = calculate_cycle(
        count=count,
        period=p["asset_period"],
        phase=p["asset_phase"],
        amplitude=p["asset_amplitude"],
        asymmetry=p["asset_asymmetry"],
    )
    space = tuple((1 + c) * level for c, level in zip(space_cycle, volatility))
    asset = tuple(p["cap_rate"] - c for c in asset_cycle)
    if any(x <= 0 for x in asset):
        raise ValueError("market path has nonpositive capitalization")
    true = tuple(s / a for s, a in zip(space, asset))
    noise = draws["noise"]
    shock = calculate_shock(
        draws["events"],
        likelihood=p["shock_likelihood"],
        dissipation=p["shock_dissipation"],
        impact=p["shock_impact"],
    )
    noisy = tuple((1 + n) * v for n, v in zip(noise, true))
    # The shock kernel has already applied amplitude. Apply the resulting factor once.
    historical = tuple(v * (1 + s) for v, s in zip(noisy, shock))
    if any(v == 0 for v in historical):
        raise ValueError("zero historical value cannot define forward ratios")
    paths = dict(
        trend=trend,
        autoregressive_returns=ar,
        cumulative_volatility=volatility,
        space_cycle=space_cycle,
        asset_cycle=asset_cycle,
        space_market=space,
        asset_market=asset,
        asset_true_value=true,
        space_market_price_factors=tuple(v / p["initial_value"] for v in space),
        noise_effect=noise,
        shock_effect=shock,
        noisy_value=noisy,
        historical_value=historical,
        implied_reversion_cap_rates=tuple(
            space[i + 1] / historical[i] for i in range(count - 1)
        ),
        returns=tuple(historical[i + 1] / historical[i] - 1 for i in range(count - 1)),
    )
    if any(not math.isfinite(v) for values in paths.values() for v in values):
        raise ValueError("non-finite realized market path")
    return paths, {"implied_reversion_cap_rates": 1, "returns": 1}
