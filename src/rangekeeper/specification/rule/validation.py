"""Pure rule contract and trace checks over structurally validated records."""

import math
from datetime import date
from uuid import UUID

from rangekeeper.model.expression.validation import analyze_expressions
from rangekeeper.model.scope import (
    numerical_units,
    recorded_quantity,
    reference_key,
    resolve_reference,
)
from rangekeeper.quantity import default_units
from rangekeeper.shared.amounts import number
from rangekeeper.shared.validation import require
from rangekeeper.specification.rule._availability import available_on, evidence_dates


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
                    math.isfinite(number(actual["magnitude"])),
                    "non-finite rule assignment",
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


def validate_evidence(rules, outcomes, *, scope, provenance=None, units=default_units):
    """Independently check ordered outcome evidence against declarations and inputs."""
    from rangekeeper.quantity import Quantity
    from rangekeeper.schema.records import Expression
    from rangekeeper.specification.rule.predicate import evaluate

    require(bool(outcomes), "rules require decision evidence")
    require(len(outcomes) <= len(rules["decisions"]), "too much rule evidence")
    controlled = {reference_key(target) for target in rules["targets"]}
    evidence = evidence_dates(provenance or {})
    assignments, prior = [], {}
    terminated = False
    for decision, outcome in zip(rules["decisions"], outcomes, strict=False):
        require(not terminated, "outcome after termination")
        require(
            outcome["decision"] == decision["id"] and outcome["at"] == decision["at"],
            "outcome decision mismatch",
        )
        observations = outcome["observations"]
        require(
            [item["name"] for item in observations]
            == [item["name"] for item in decision["observations"]],
            "outcome observations mismatch",
        )
        for binding, observed in zip(
            decision["observations"], observations, strict=True
        ):
            require(
                binding["target"] == observed["target"], "observed reference mismatch"
            )
            token = reference_key(binding["target"])
            declared = (
                date.fromisoformat(binding["available_at"])
                if binding.get("available_at")
                else None
            )
            if token in prior:
                actual, earlier = prior[token]
                require(
                    earlier < date.fromisoformat(outcome["at"]),
                    "observation requires an earlier decision",
                )
                available = max(earlier, declared or earlier)
            else:
                require(
                    token not in controlled,
                    "rule observation requires an earlier decision; recorded controls are not current decisions",
                )
                _, movement = resolve_reference(binding["target"], scope.targets)
                available = available_on(
                    movement_date=(
                        date.fromisoformat(movement["date"])
                        if movement and movement.get("date")
                        else None
                    ),
                    period_end=(
                        date.fromisoformat(movement["period"]["end"])
                        if movement and movement.get("period")
                        else None
                    ),
                    scenario_dates=((evidence[token],) if token in evidence else ()),
                    declared=declared,
                )
                actual = recorded_quantity(
                    binding["target"], scope.targets, scope.measures
                )
            require(
                available is not None
                and observed["available_at"] == available.isoformat(),
                "observation availability differs from input evidence",
            )
            require(
                available <= date.fromisoformat(outcome["at"]),
                "observation from the future",
            )
            require(
                actual is not None and observed["quantity"] == actual,
                "observed quantity differs from input",
            )
        quantities = {
            UUID(item["target"]["target"]): Quantity.from_data(item["quantity"])
            for item in observations
        }
        selected = None
        for rule in decision["rules"]:
            result = evaluate(
                Expression.from_data(rule["condition"]), quantities, units=units
            )
            require(type(result) is bool, "rule requires Boolean result")
            if result:
                selected = rule
                break
        require(
            outcome.get("rule") == (selected["id"] if selected else None),
            "outcome did not use first matching rule",
        )
        actions = selected["actions"] if selected else decision["fallback"]
        expected = [
            {"target": action["target"], "quantity": action["quantity"]}
            for action in actions
            if action["kind"] == "assign"
        ]
        require(
            outcome["assignments"] == expected, "outcome differs from declared actions"
        )
        terminated = any(action["kind"] == "terminate" for action in actions)
        require(outcome["terminated"] == terminated, "termination evidence mismatch")
        require(
            outcome.get("termination_reason")
            == (("rule_matched" if selected else "fallback") if terminated else None),
            "termination reason mismatch",
        )
        for assignment in expected:
            token = reference_key(assignment["target"])
            require(token not in prior, "control assigned more than once")
            prior[token] = (assignment["quantity"], date.fromisoformat(outcome["at"]))
        assignments.extend(expected)
    require(
        terminated or len(outcomes) == len(rules["decisions"]),
        "truncated outcome sequence",
    )
    require(
        set(prior) == controlled,
        "outcome trace must supply each controlled target exactly once",
    )
    return assignments
