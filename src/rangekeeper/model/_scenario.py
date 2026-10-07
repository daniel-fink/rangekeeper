"""Pure scenario-record conformance; no numerical or random implementation imports."""

from datetime import date, timedelta
from uuid import UUID
from .._validation import require, require_unique
from .distribution import Distribution
from ..scenarios.contracts import method, check_values, check_inputs
from .scope import resolve_reference, reference_key


def validate_plan(plan):
    contract = method(plan["method"])
    periods = plan["periods"]
    require(bool(periods), "scenario requires periods")
    require(
        all(p["start_inclusive"] < p["end_exclusive"] for p in periods),
        "invalid scenario period",
    )
    require(
        all(
            a["end_exclusive"] <= b["start_inclusive"]
            for a, b in zip(periods, periods[1:])
        ),
        "scenario periods overlap or are out of order",
    )
    params = plan["parameters"]
    require_unique(params, "name", "scenario parameter")
    expected = set(contract.parameters)
    require(
        {p["name"] for p in params} == expected, "scenario parameter inventory mismatch"
    )
    fixed = {}
    for p in params:
        q, d = p.get("quantity"), p.get("distribution")
        require(
            (q is None) != (d is None),
            "parameter requires exactly one quantity or distribution",
        )
        if q:
            fixed[p["name"]] = q["magnitude"]
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

    check_values(plan["method"], fixed)


def validate_realizations(provenance, scope):
    """Check captured input/output references and delayed observation declarations."""
    realizations = provenance.get("scenarios") or []
    require_unique(realizations, "id", "scenario realization")
    for item in realizations:
        validate_plan(item["plan"])
        for field in ("inputs", "outputs", "streams", "versions"):
            require_unique(item[field], "name", f"scenario {field}")
        if item.get("calculation") is not None:
            require_unique(
                item["calculation"]["versions"], "name", "calculation dependency"
            )
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

        if item["outputs"]:
            availability = {
                reference_key(a["target"]): a["available_at"]
                for a in item["availability"]
            }
            for binding in item["outputs"]:
                delay = method(item["plan"]["method"]).output_offsets[binding["name"]]
                if delay:
                    value = scope.values[UUID(binding["value"])]
                    for index, movement in enumerate(value["flow"]["movements"]):
                        required = (
                            date.fromisoformat(
                                item["plan"]["periods"][index + delay]["end_exclusive"]
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
    contract = method(plan["method"])
    arrays = set(contract.arrays)
    parameters = {p["name"]: p for p in plan["parameters"]}
    required = arrays | (set(parameters) if contract.scalar_parameters else set())
    require(
        {b["name"] for b in item["inputs"]} == required,
        "captured input inventory mismatch",
    )
    outputs = set(contract.output_offsets)
    require(
        not item["outputs"] or {b["name"] for b in item["outputs"]} == outputs,
        "captured output inventory mismatch",
    )
    availability = {
        reference_key(a["target"]): a["available_at"] for a in item["availability"]
    }
    expected_availability = set()
    captured, captured_arrays = {}, {}
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
                    contract.output_offsets[name] if field == "outputs" else 0
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
                        date.fromisoformat(plan["periods"][index]["end_exclusive"])
                        - timedelta(days=1)
                    ).isoformat()
                    require(
                        token in availability and availability[token] >= earliest,
                        "scenario observation precedes its period end",
                    )
                magnitudes = [m["magnitude"] for m in movements]
                if field == "inputs":
                    captured_arrays[name] = magnitudes
            else:
                quantity = value.get("quantity")
                require(
                    quantity is not None and quantity["units"] == "dimensionless",
                    "captured parameter must be a dimensionless Quantity",
                )
                magnitudes = [quantity["magnitude"]]
            if field == "inputs" and name in parameters:
                if contract.scalar_parameters:
                    captured[name] = magnitudes[0]
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
    check_inputs(plan["method"], captured, captured_arrays)
    require(
        set(availability) == expected_availability,
        "scenario availability inventory mismatch",
    )
