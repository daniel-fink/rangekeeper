"""Explicit naming upgrade for the unreleased v1 scenario methods."""

from uuid import UUID
from .drafts import _revision
from ..model import Model

_METHODS = {
    "market.v1": "market.v2",
    "market.estimates.v1": "market.estimates.v2",
    "independent.v1": "independent.v2",
}
_OUTPUTS = {
    "pricing_factor": "space_market_price_factors",
    "true_value": "asset_true_value",
    "implied_cap_rate": "implied_reversion_cap_rates",
    "autoregression": "autoregressive_returns",
    "volatility": "cumulative_volatility",
}


def upgrade_scenario_names(data: dict, *, revision_id: UUID | None = None) -> Model:
    """Upgrade v1 labels into a new Model revision without recalculating quantities.

    Accept Model 0.5.0 with recognized v1 scenario records. Preserve canonical
    Value/Movement identities, plans' identities, quantities, claims, random
    stream identifiers and availability dates. Only the method/name vocabulary
    and owning Model revision change. Old Runs and external revision pins are
    untouched; callers must explicitly select the upgraded revision. No IO.

    This is a draft-format conversion, not a replay or a claim of a new execution.
    Unsupported methods, conflicting names and malformed content fail validation.
    """
    result = _revision(data, "Model", {"0.5.0"}, revision_id)
    records = (result.get("provenance") or {}).get("scenarios") or []
    if not records:
        raise ValueError("no scenario records to upgrade")
    renames: dict[str, str] = {}
    for record in records:
        plan = record["plan"]
        method = plan["method"]
        if method not in _METHODS:
            raise ValueError(f"expected a v1 scenario method, got {method}")
        market = method.startswith("market.")
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
                    if field == "outputs"
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
    # Rename only canonical declarations, never opaque evidence or UUID references.
    system = result.get("system") or {}
    for collection in ("entities", "relationships", "assemblies"):
        for owner in system.get(collection) or []:
            for value in (owner.get("characteristics") or {}).get("values") or []:
                if value["id"] in renames:
                    value["key"] = renames[value["id"]]

    def visit(formulations):
        for formulation in formulations or []:
            for value in formulation.get("values") or []:
                if value["id"] in renames:
                    value["key"] = renames[value["id"]]
            visit(formulation.get("formulations"))

    visit(system.get("formulations"))
    return Model.from_data(result)
