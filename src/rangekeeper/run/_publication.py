"""Bounded finalized-Run conformance; not a scheduler, evaluator, or solver.

Structurally validate supplied documents first. Typed catalogues resolve immutable
references. Scalar output checks preserve input definitions, check supplied amounts
and required recorded quantities, but do not evaluate equations or prove feasibility.
Specification-local Value publication and structural interventions need adapters.
"""

from copy import deepcopy
import math

from rangekeeper.model._references import (
    reference_key,
    recorded_quantity,
    numerical_units,
)
from rangekeeper._validation import require
from rangekeeper.model._validation import validate_model
from rangekeeper.specification._validation import records


class Publication:
    """Check accepted outputs with one producer per revision in a Run tree.

    The resolver is supplied by the tree; this object never loads or stores data.
    It checks declared changes and evidence, while execution checks mathematics.
    """

    def __init__(self, resolve, model_version, quantities_equal=None):
        self.resolve = resolve
        self.model_version = model_version
        self.quantities_equal = quantities_equal
        self.input_ids = set()
        self.output_ids = set()
        self.producers = {}

    def check(self, run, model, effective, scope):
        """Check permitted changed Values, assignments, lineage and retained Claims."""
        input_id = model["metadata"]["id"]
        self.input_ids.add(input_id)
        assignments = list(effective.get("assignments") or [])
        decisions = run["report"].get("decisions") or []
        if effective.get("policy"):
            from rangekeeper.specification._policy_validation import validate_decisions

            assignments.extend(
                validate_decisions(
                    effective["policy"],
                    decisions,
                    scope=scope,
                    provenance=model.get("provenance") or {},
                )
            )
        else:
            require(not decisions, "decision evidence requires a policy")
        roles = list(effective.get("unknowns") or []) + [
            a["target"] for a in assignments
        ]
        needed = {reference_key(r): r for r in roles}
        model_values = {
            r["id"] for r in records(model.get("system") or {}) if "id" in r
        }
        require(
            all(r["target"] in model_values for r in roles),
            "Specification-local Value publication requires adapter",
        )

        def definition(snapshot):
            result = deepcopy(snapshot)
            result.pop("metadata", None)
            result.pop("provenance", None)
            for r in records(result):
                if r.get("kind") == "measurement" and "id" in r and r["id"] in needed:
                    r.pop("quantity", None)
                if r.get("kind") == "flow" and "id" in r:
                    for m in (r.get("flow") or {}).get("movements") or []:
                        if m["id"] in needed:
                            m.pop("magnitude", None)
                            m.pop("claims", None)
            return result

        for ref in run.get("outputs") or []:
            output = self.resolve(ref, "Model")
            require(ref != input_id, "output cannot be input revision")
            require(ref not in self.producers, "output has multiple producing Runs")
            self.producers[ref] = run["metadata"]["id"]
            self.output_ids.add(ref)
            require(
                output["metadata"].get("previous") == input_id,
                "output lineage must reference input",
            )
            output_scope = validate_model(output, self.model_version)
            require(
                definition(output) == definition(model),
                "output must preserve input definitions and unrelated recorded content",
            )
            for target in needed.values():
                quantity = recorded_quantity(
                    target, output_scope.targets, output_scope.measures
                )
                require(
                    quantity is not None, "accepted output has unresolved solve Value"
                )
                require(
                    quantity["units"]
                    == numerical_units(target, scope.targets, scope.measures),
                    "output unit conversion requires adapter",
                )
                require(
                    math.isfinite(quantity["magnitude"]), "non-finite output quantity"
                )
            for assignment in assignments:
                actual = recorded_quantity(
                    assignment["target"], output_scope.targets, output_scope.measures
                )
                expected = assignment["quantity"]
                require(
                    (
                        self.quantities_equal(actual, expected)
                        if self.quantities_equal is not None
                        else actual == expected
                    ),
                    "output violates assignment",
                )
            old_claims = {
                c["id"]: c for c in (model.get("provenance") or {}).get("claims") or []
            }
            new_claims = {
                c["id"]: c for c in (output.get("provenance") or {}).get("claims") or []
            }
            require(
                all(new_claims.get(k) == v for k, v in old_claims.items()),
                "historical Claims changed",
            )
