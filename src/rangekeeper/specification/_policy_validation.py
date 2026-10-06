"""Pure policy contract and trace checks over structurally validated records."""

import math

from .._validation import require
from ..model._expression import infer_expression_domain
from ..model._references import reference_key, numerical_units, recorded_quantity


def validate_policy(policy, *, scope, units_compatible=None):
    """Check finite control ownership, dated observations and explicit actions.

    This validates declarations only. It does not execute a policy or a solver.
    """
    targets = {reference_key(r): r for r in policy["targets"]}
    require(
        len(targets) == len(policy["targets"]) and bool(targets),
        "duplicate or empty policy targets",
    )
    for target in targets.values():
        numerical_units(target, scope.values, scope.measures)
    require(bool(policy["points"]), "policy needs decision points")
    dates = [p["at"] for p in policy["points"]]
    require(dates == sorted(set(dates)), "decision dates must be strictly increasing")
    covered = set()
    for point in policy["points"]:
        observations = point["observations"]
        require(
            len({o["name"] for o in observations}) == len(observations),
            "duplicate observation name",
        )
        observed = {reference_key(o["target"]) for o in observations}
        for observation in observations:
            numerical_units(observation["target"], scope.values, scope.measures)
        for rule in point["rules"]:
            require(
                infer_expression_domain(rule["condition"], scope=scope)["kind"]
                == "boolean",
                "policy rule requires Boolean condition",
            )
            from ._validation import records

            refs = {
                reference_key(n["target"])
                for n in records(rule["condition"])
                if n.get("kind") == "reference"
            }
            require(
                refs <= observed, "policy condition references undeclared observations"
            )
        for actions in [r["actions"] for r in point["rules"]] + [point["fallback"]]:
            require(bool(actions), "policy requires explicit actions and fallback")
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
                    action["target"], scope.values, scope.measures
                )
                actual = action["quantity"]
                require(
                    math.isfinite(actual["magnitude"]), "non-finite policy assignment"
                )
                require(
                    (
                        units_compatible(actual["units"], expected)
                        if units_compatible
                        else actual["units"] == expected
                    ),
                    "incompatible policy assignment units",
                )
    require(covered == set(targets), "policy does not declare actions for all targets")
    return set(targets)


def validate_decisions(policy, decisions, *, scope, provenance=None):
    """Require an ordered trace whose actions supply each controlled target once.

    Observations must match the pinned input. Numerical feasibility remains a
    separate executor check; trace evidence never substitutes for that check.
    """
    assignments = []
    terminated = False
    require(bool(decisions), "policy requires decision evidence")
    require(len(decisions) <= len(policy["points"]), "too many policy decisions")
    for index, (point, decision) in enumerate(zip(policy["points"], decisions)):
        require(not terminated, "decision after termination")
        require(
            decision["point"] == point["id"] and decision["at"] == point["at"],
            "decision point mismatch",
        )
        observations = decision["observations"]
        require(
            [o["name"] for o in observations]
            == [o["name"] for o in point["observations"]],
            "decision observations mismatch",
        )
        for binding, observed in zip(point["observations"], observations):
            require(
                binding["target"] == observed["target"], "observed reference mismatch"
            )
            require(
                observed["available_at"] <= decision["at"],
                "observation from the future",
            )
            from ..model._availability import available_on

            prior_date = next(
                (
                    d["at"]
                    for d in decisions[:index]
                    if d["at"] < decision["at"]
                    and any(a["target"] == binding["target"] for a in d["assignments"])
                ),
                None,
            )
            canonical_date = (
                max(prior_date, binding.get("available_at") or prior_date)
                if prior_date
                else available_on(
                    binding["target"],
                    scope.values,
                    provenance or {},
                    declared=binding.get("available_at"),
                )
            )
            require(
                canonical_date is not None
                and observed["available_at"] == canonical_date,
                "observation availability differs from input evidence",
            )
            actual = recorded_quantity(binding["target"], scope.values, scope.measures)
            prior = next(
                (
                    a["quantity"]
                    for a in assignments
                    if a["target"] == binding["target"]
                ),
                None,
            )
            require(
                observed["quantity"] == (prior if prior is not None else actual),
                "observed quantity differs from input",
            )
        from ..model._predicate import evaluate
        from .._schema.records import Expression, Quantity

        quantities = {
            reference_key(o["target"]): Quantity.from_data(o["quantity"])
            for o in observations
        }
        first = next(
            (
                r
                for r in point["rules"]
                if evaluate(Expression.from_data(r["condition"]), quantities) is True
            ),
            None,
        )
        require(
            decision.get("rule") == (first["id"] if first else None),
            "decision did not use first matching rule",
        )
        selected = next(
            (r for r in point["rules"] if r["id"] == decision.get("rule")), None
        )
        require(
            decision.get("rule") is None or selected is not None,
            "unknown decision rule",
        )
        actions = selected["actions"] if selected else point["fallback"]
        expected = [
            {"target": a["target"], "quantity": a["quantity"]}
            for a in actions
            if a["kind"] == "assign"
        ]
        require(
            decision["assignments"] == expected,
            "decision differs from declared actions",
        )
        terminated = any(a["kind"] == "terminate" for a in actions)
        require(decision["terminated"] == terminated, "termination evidence mismatch")
        require(
            decision.get("termination_reason")
            == (("rule_matched" if selected else "fallback") if terminated else None),
            "termination reason mismatch",
        )
        assignments.extend(expected)
    require(
        terminated or len(decisions) == len(policy["points"]),
        "truncated decision sequence",
    )
    tokens = [reference_key(a["target"]) for a in assignments]
    require(
        len(tokens) == len(set(tokens))
        and set(tokens) == {reference_key(t) for t in policy["targets"]},
        "decision trace must supply each controlled target exactly once",
    )
    return assignments
