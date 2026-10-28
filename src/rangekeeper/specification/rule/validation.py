"""Pure rule declaration checks over structurally validated records."""

import math
from uuid import UUID

from rangekeeper.model._scope import numerical_units, reference_key
from rangekeeper.model.expression.validation import analyze_expressions
from rangekeeper.shared.validation import require


def validate_rules(rules, *, scope, units_compatible=None):
    """Check finite control ownership, dated observations and explicit actions.

    This validates declarations only. It does not execute rules or a solver.
    """
    targets = {reference_key(r): r for r in rules["targets"]}
    require(
        len(targets) == len(rules["targets"]) and bool(targets),
        "duplicate or empty rule targets",
    )
    for target in targets.values():
        numerical_units(target, scope.targets, scope.measures)
    require(bool(rules["decisions"]), "rules need decision points")
    dates = [p["at"] for p in rules["decisions"]]
    require(dates == sorted(set(dates)), "decision dates must be strictly increasing")
    covered = set()
    for point in rules["decisions"]:
        observations = point["observations"]
        require(
            len({o["name"] for o in observations}) == len(observations),
            "duplicate observation name",
        )
        observed = {reference_key(o["target"]) for o in observations}
        for observation in observations:
            numerical_units(observation["target"], scope.targets, scope.measures)
        for rule in point["rules"]:
            analysis = analyze_expressions((rule["condition"],), scope=scope)
            require(
                analysis.domains_by_id[UUID(rule["condition"]["id"])]["kind"]
                == "boolean",
                "rule requires Boolean condition",
            )
            refs = {
                reference_key(n["target"])
                for n in analysis.nodes_by_id.values()
                if n.get("kind") == "reference"
            }
            require(
                refs <= observed, "rule condition references undeclared observations"
            )
        for actions in [r["actions"] for r in point["rules"]] + [point["fallback"]]:
            require(bool(actions), "rules require explicit actions and fallback")
            local = set()
            terminated = False
            for action in actions:
                require(not terminated, "terminate must be the last action")
                if action["kind"] == "terminate":
                    require(
                        action.get("target") is None and action.get("quantity") is None,
                        "terminate cannot assign",
                    )
                    terminated = True
                    continue
                require(
                    action.get("target") is not None
                    and action.get("quantity") is not None,
                    "assign action needs target and quantity",
                )
                token = reference_key(action["target"])
                require(
                    token in targets and token not in local,
                    "undeclared or duplicate action target",
                )
                local.add(token)
                covered.add(token)
                expected = numerical_units(
                    action["target"], scope.targets, scope.measures
                )
                actual = action["quantity"]
                require(
                    math.isfinite(actual["magnitude"]), "non-finite rule assignment"
                )
                require(
                    (
                        units_compatible(actual["units"], expected)
                        if units_compatible
                        else actual["units"] == expected
                    ),
                    "incompatible rule assignment units",
                )
    require(covered == set(targets), "rules do not declare actions for all targets")
    return set(targets)
