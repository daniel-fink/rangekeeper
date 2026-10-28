"""The trace check: stored rule evidence against its declarations and inputs.

It runs on a stored Run without a solve, so it is part of evidence validation.
The rule evaluator in ``execution.rule`` makes the evidence; this check does not
trust it.
"""

from datetime import date
from uuid import UUID

from rangekeeper.model._scope import recorded_quantity, reference_key, resolve_reference
from rangekeeper.quantity import default_units
from rangekeeper.run._rule.availability import available_on, evidence_dates
from rangekeeper.run._rule.predicate import evaluate
from rangekeeper.schema.records import Expression, Quantity
from rangekeeper.shared.validation import require


def validate_evidence(rules, outcomes, *, scope, provenance=None, units=default_units):
    """Independently check ordered outcome evidence against declarations and inputs."""
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
