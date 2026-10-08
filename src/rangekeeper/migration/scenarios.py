"""Explicit naming upgrade for the unreleased v1 scenario methods."""

from uuid import UUID
from rangekeeper.schema.index import walk_data
from rangekeeper.model import Model

_METHODS = {
    "market.v1": "market",
    "market.estimates.v1": "market.estimates",
    "independent.v1": "market.independent",
    "market.v2": "market",
    "market.estimates.v2": "market.estimates",
    "independent.v2": "market.independent",
}
_OUTPUTS = {
    "pricing_factor": "space_market_price_factors",
    "true_value": "asset_true_value",
    "implied_cap_rate": "implied_reversion_cap_rates",
    "autoregression": "autoregressive_returns",
    "volatility": "cumulative_volatility",
}


def convert_names(result: dict) -> None:
    """Convert recognized old scenario labels in an already copied, current-layout Model."""
    records = (result.get("provenance") or {}).get("scenarios") or []
    renames: dict[str, str] = {}
    for record in records:
        plan = record["plan"]
        method = plan["method"]
        if method not in _METHODS:
            from rangekeeper.model.scenario.contracts import method as contract_for

            contract_for(method)
            continue
        legacy = method.endswith(".v1")
        market = method.startswith("market.") and legacy
        plan["method"] = _METHODS[method]
        if market:
            for parameter in plan["parameters"]:
                if parameter["name"] == "volatility":
                    parameter["name"] = "volatility_per_period"
            for stream in record["streams"]:
                if stream["name"] == "volatility":
                    stream["name"] = "volatility_per_period"
        for field in ("inputs", "outputs"):
            for binding in record[field]:
                before = binding["name"]
                after = (
                    _OUTPUTS.get(before, before)
                    if field == "outputs" and legacy
                    else (
                        "volatility_per_period"
                        if market and before == "volatility"
                        else before
                    )
                )
                if after != before:
                    binding["name"] = after
                    key = "input_" + after if field == "inputs" else after
                    if binding["value"] in renames and renames[binding["value"]] != key:
                        raise ValueError(
                            "conflicting names for a shared scenario Value"
                        )
                    renames[binding["value"]] = key
    for record, _ in walk_data("Model", result):
        if record.get("id") in renames and "key" in record and "kind" in record:
            record["key"] = renames[record["id"]]


def upgrade_scenario_names(data: dict, *, revision_id: UUID | None = None) -> Model:
    """Create a current Model revision without recomputing historical scenario paths.

    Original documents, captured draws and stream IDs remain unchanged. Missing
    historical calculation fingerprints stay absent; exact replay is unavailable.
    """
    from rangekeeper.migration.drafts import upgrade_model

    records = (data.get("provenance") or {}).get("scenarios") or []
    if not records or not any(
        record["plan"]["method"] in _METHODS for record in records
    ):
        raise ValueError("expected recognized v1 or v2 scenario methods")
    return upgrade_model(data, revision_id=revision_id)
