"""Known-input path construction using the characterized numerical kernels."""

import math

from rangekeeper.market._kernels import (
    accumulate_volatility,
    autoregression,
    cycle,
)
from rangekeeper.market._kernels import shock as shock_values
from rangekeeper.market._kernels import trend as trend_values
from rangekeeper.market.contracts import check_inputs
from rangekeeper.market.contracts import method as contract_for


def construct_paths(method, parameters, draws):
    """Return named arrays and forward-dependency offsets, with no randomness."""
    contract = contract_for(method)
    check_inputs(method, parameters, draws)
    if not contract.scalar_parameters:
        factors, caps = draws["space_factor"], draws["asset_cap"]
        return {
            "space_market_price_factors": factors,
            "asset_market": caps,
            "historical_value": tuple(
                f / c for f, c in zip(factors, caps, strict=True)
            ),
        }, {}
    p = dict(parameters)
    if method == "market.estimates":
        # Preserve the old linked cycle estimates: phase differences are fractions
        # of the space cycle, and period differences are measured in periods.
        p["space_phase"] = p["space_period"] * p["space_phase_proportion"]
        p["asset_phase"] = (
            p["space_phase"] + p["asset_phase_difference"] * p["space_period"]
        )
        p["asset_period"] = p["space_period"] + p["asset_period_difference"]
    count = len(draws["innovations"])
    trend = trend_values(count=count, rate=p["growth_rate"], initial=p["initial_value"])
    ar = autoregression(innovations=draws["innovations"], parameter=p["autoregression"])
    volatility = accumulate_volatility(
        trend=trend,
        returns=ar,
        growth=p["growth_rate"],
        mean_reversion=p["mean_reversion"],
    )
    space_cycle = cycle(
        count=count,
        period=p["space_period"],
        phase=p["space_phase"],
        amplitude=p["space_amplitude"],
        asymmetry=p["space_asymmetry"],
    )
    asset_cycle = cycle(
        count=count,
        period=p["asset_period"],
        phase=p["asset_phase"],
        amplitude=p["asset_amplitude"],
        asymmetry=p["asset_asymmetry"],
    )
    space = tuple(
        (1 + c) * level for c, level in zip(space_cycle, volatility, strict=True)
    )
    asset = tuple(p["cap_rate"] - c for c in asset_cycle)
    if any(x <= 0 for x in asset):
        raise ValueError("market path has nonpositive capitalization")
    true = tuple(s / a for s, a in zip(space, asset, strict=True))
    noise = draws["noise"]
    shock = shock_values(
        events=draws["events"],
        probability=p["shock_likelihood"],
        dissipation=p["shock_dissipation"],
        size=p["shock_impact"],
    )
    noisy = tuple((1 + n) * v for n, v in zip(noise, true, strict=True))
    # The shock kernel has already applied amplitude. Apply the resulting factor once.
    historical = tuple(v * (1 + s) for v, s in zip(noisy, shock, strict=True))
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
    return paths, contract.output_offsets
