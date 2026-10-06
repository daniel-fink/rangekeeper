"""Pure scenario-record conformance; no numerical or random implementation imports."""

import math
from datetime import date, timedelta
from .._validation import require, require_unique
from .distribution import Distribution
from ._references import resolve_reference, reference_key

_MARKET = set(
    "initial_value growth_rate cap_rate volatility_per_period autoregression mean_reversion space_period space_phase space_amplitude space_asymmetry asset_period asset_phase asset_amplitude asset_asymmetry noise_lower noise_upper shock_likelihood shock_dissipation shock_impact".split()
)


def validate_plan(plan):
    require(
        plan["method"] in ("market.v2", "market.estimates.v2", "independent.v2"),
        "unsupported scenario method/version",
    )
    periods = plan["periods"]
    require(bool(periods), "scenario requires periods")
    require(all(p["start"] < p["end"] for p in periods), "invalid scenario period")
    require(
        all(a["end"] <= b["start"] for a, b in zip(periods, periods[1:])),
        "scenario periods overlap or are out of order",
    )
    params = plan["parameters"]
    require_unique(params, "name", "scenario parameter")
    expected = (
        (
            _MARKET - {"space_phase", "asset_phase", "asset_period"}
            | {
                "space_phase_proportion",
                "asset_phase_difference",
                "asset_period_difference",
            }
        )
        if plan["method"] == "market.estimates.v2"
        else _MARKET if plan["method"] == "market.v2" else {"space_factor", "asset_cap"}
    )
    require(
        {p["name"] for p in params} == expected, "scenario parameter inventory mismatch"
    )
    for p in params:
        q, d = p.get("quantity"), p.get("distribution")
        require(
            (q is None) != (d is None),
            "parameter requires exactly one quantity or distribution",
        )
        if q:
            require(math.isfinite(q["magnitude"]), "non-finite scenario parameter")
            require(
                q["units"] == "dimensionless",
                "normalized market parameters require dimensionless units",
            )
        if d:
            Distribution.from_data(d).check()
            require(
                d["units"] == "dimensionless",
                "normalized distribution requires dimensionless units",
            )


def validate_realizations(provenance, scope):
    """Check captured input/output references and delayed observation declarations."""
    realizations = provenance.get("scenarios") or []
    require_unique(realizations, "id", "scenario realization")
    for item in realizations:
        validate_plan(item["plan"])
        for field in ("inputs", "outputs", "streams", "versions"):
            require_unique(item[field], "name", f"scenario {field}")
        _validate_contents(item, scope)
        tokens = [reference_key(a["target"]) for a in item["availability"]]
        require(len(tokens) == len(set(tokens)), "duplicate observation availability")
        for availability in item["availability"]:
            _, movement = resolve_reference(availability["target"], scope.targets)
            require(movement is not None, "scenario availability requires a Movement")
            if movement.get("date") is not None:
                require(
                    availability["available_at"] >= movement["date"],
                    "observation available before recorded date",
                )

        if item["plan"]["method"].startswith("market."):
            availability = {
                reference_key(a["target"]): a["available_at"]
                for a in item["availability"]
            }
            for binding in item["outputs"]:
                if binding["name"] in ("implied_reversion_cap_rates", "returns"):
                    value = scope.values[binding["value"]]
                    for index, movement in enumerate(value["flow"]["movements"]):
                        required = (
                            date.fromisoformat(
                                item["plan"]["periods"][index + 1]["end"]
                            )
                            - timedelta(days=1)
                        ).isoformat()
                        actual = availability.get(
                            reference_key(dict(target=movement["id"]))
                        )
                        require(
                            actual is not None and actual >= required,
                            "forward-derived observation precedes its inputs",
                        )


def _validate_contents(item, scope):
    """Enforce complete captured shapes without importing generation algorithms."""
    plan = item["plan"]
    market = plan["method"].startswith("market.")
    arrays = (
        {"innovations", "noise", "events"} if market else {"space_factor", "asset_cap"}
    )
    parameters = {p["name"]: p for p in plan["parameters"]}
    required = arrays | (set(parameters) if market else set())
    require(
        {b["name"] for b in item["inputs"]} == required,
        "captured input inventory mismatch",
    )
    outputs = (
        {
            "trend",
            "autoregressive_returns",
            "cumulative_volatility",
            "space_cycle",
            "asset_cycle",
            "space_market",
            "asset_market",
            "asset_true_value",
            "space_market_price_factors",
            "noise_effect",
            "shock_effect",
            "noisy_value",
            "historical_value",
            "implied_reversion_cap_rates",
            "returns",
        }
        if market
        else {"space_market_price_factors", "asset_market", "historical_value"}
    )
    require(
        not item["outputs"] or {b["name"] for b in item["outputs"]} == outputs,
        "captured output inventory mismatch",
    )
    availability = {
        reference_key(a["target"]): a["available_at"] for a in item["availability"]
    }
    expected_availability = set()
    for field in ("inputs", "outputs"):
        for binding in item[field]:
            value, _ = resolve_reference(dict(target=binding["value"]), scope.targets)
            name = binding["name"]
            is_flow = field == "outputs" or name in arrays
            if is_flow:
                flow = value.get("flow")
                require(
                    flow is not None and flow["units"] == "dimensionless",
                    "scenario path must be a dimensionless Flow",
                )
                count = len(plan["periods"]) - (
                    1
                    if field == "outputs"
                    and market
                    and name in ("implied_reversion_cap_rates", "returns")
                    else 0
                )
                movements = flow["movements"]
                require(len(movements) == count, "scenario path length mismatch")
                for index, movement in enumerate(movements):
                    require(
                        movement.get("period") == plan["periods"][index]
                        and movement["key"] == f"p{index+1}",
                        "scenario path coordinate mismatch",
                    )
                    require(
                        movement.get("magnitude") is not None,
                        "captured scenario path cannot be unresolved",
                    )
                    token = reference_key(dict(target=movement["id"]))
                    expected_availability.add(token)
                    earliest = (
                        date.fromisoformat(plan["periods"][index]["end"])
                        - timedelta(days=1)
                    ).isoformat()
                    require(
                        token in availability and availability[token] >= earliest,
                        "scenario observation precedes its period end",
                    )
                magnitudes = [m["magnitude"] for m in movements]
            else:
                quantity = value.get("quantity")
                require(
                    quantity is not None and quantity["units"] == "dimensionless",
                    "captured parameter must be a dimensionless Quantity",
                )
                magnitudes = [quantity["magnitude"]]
            if field == "inputs" and name in parameters:
                parameter = parameters[name]
                if parameter.get("quantity") is not None:
                    require(
                        all(
                            x == parameter["quantity"]["magnitude"] for x in magnitudes
                        ),
                        "captured parameter differs from fixed plan input",
                    )
                else:
                    distribution = parameter["distribution"]
                    require(
                        all(
                            distribution["lower"] <= x <= distribution["upper"]
                            for x in magnitudes
                        ),
                        "captured parameter outside distribution support",
                    )
            if field == "inputs" and name == "events":
                require(
                    all(0 <= x <= 1 for x in magnitudes),
                    "shock event draws must be in [0, 1]",
                )
    require(
        set(availability) == expected_availability,
        "scenario availability inventory mismatch",
    )
