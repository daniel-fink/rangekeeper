"""Bounded finalized-Run conformance; not a scheduler, evaluator, or solver.

Structurally validate supplied documents first. Typed catalogues resolve immutable
references. Scalar output checks preserve input definitions, check supplied amounts
and required recorded quantities, but do not evaluate equations or prove feasibility.
Specification-local Value publication and structural interventions need adapters.
"""

from copy import deepcopy
from .._records import exact_equal
import math
from uuid import UUID

from rangekeeper.model.scope import (
    reference_key,
    recorded_quantity,
    numerical_units,
)
from rangekeeper._validation import require
from .._record_index import walk_data


def validate_outputs(
    run,
    model,
    effective,
    scope,
    outputs,
    *,
    units,
    quantities_equal=None,
):
    """Check prepared outputs without owning tree traversal or producer state."""
    input_id = model["metadata"]["id"]
    assignments = list(effective.get("assignments") or [])
    decisions = run["report"].get("outcomes") or []
    if effective.get("policy"):
        from rangekeeper.policies.validation import validate_outcomes

        assignments.extend(
            validate_outcomes(
                effective["policy"],
                decisions,
                scope=scope,
                provenance=model.get("provenance") or {},
                units=units,
            )
        )
    else:
        require(not decisions, "decision evidence requires a policy")
    roles = list(effective.get("unknowns") or []) + [a["target"] for a in assignments]
    needed = {reference_key(r): r for r in roles}
    model_values = {r["id"] for r, _ in walk_data("Model", model) if "id" in r}
    require(
        all(r["target"] in model_values for r in roles),
        "Specification-local Value publication requires adapter",
    )

    def definition(snapshot):
        result = deepcopy(snapshot)
        result.pop("metadata", None)
        result.pop("provenance", None)
        for r, _ in walk_data("Model", result):
            if r.get("kind") == "measurement" and "id" in r and UUID(r["id"]) in needed:
                r.pop("quantity", None)
            if r.get("kind") == "flow" and "id" in r:
                for m in (r.get("flow") or {}).get("movements") or []:
                    if UUID(m["id"]) in needed:
                        m.pop("magnitude", None)
                        m.pop("claims", None)
        return result

    invariant = definition(model)
    old_claims = {
        c["id"]: c for c in (model.get("provenance") or {}).get("claims") or []
    }
    for output, output_scope in outputs:
        ref = output["metadata"]["id"]
        require(ref != input_id, "output cannot be input revision")
        require(
            output["metadata"].get("previous") == input_id,
            "output lineage must reference input",
        )
        require(
            exact_equal(definition(output), invariant),
            "output must preserve input definitions and unrelated recorded content",
        )
        for target in needed.values():
            quantity = recorded_quantity(
                target, output_scope.targets, output_scope.measures
            )
            require(quantity is not None, "accepted output has unresolved solve Value")
            require(
                quantity["units"]
                == numerical_units(target, scope.targets, scope.measures),
                "output unit conversion requires adapter",
            )
            require(math.isfinite(quantity["magnitude"]), "non-finite output quantity")
        for assignment in assignments:
            actual = recorded_quantity(
                assignment["target"], output_scope.targets, output_scope.measures
            )
            expected = assignment["quantity"]
            require(
                (
                    quantities_equal(actual, expected)
                    if quantities_equal is not None
                    else actual == expected
                ),
                "output violates assignment",
            )
        new_claims = {
            c["id"]: c for c in (output.get("provenance") or {}).get("claims") or []
        }
        require(
            all(exact_equal(new_claims.get(k), v) for k, v in old_claims.items()),
            "historical Claims changed",
        )
