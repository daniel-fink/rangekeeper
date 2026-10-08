"""Finite policy orchestration, separate from numerical feasibility and storage."""

from datetime import date
from uuid import UUID

from rangekeeper.schema.records import (
    ActionKind,
    Assignment,
    DecisionOutcome,
    Policy,
    Quantity,
)
from rangekeeper.model import Model
from rangekeeper.shared.errors import ContractError
from rangekeeper.model.scope import scope_for_model
from rangekeeper.shared.units import UnitSystem, default_units
from rangekeeper.specification.policy._availability import evidence_dates
from rangekeeper.specification.policy.observation import PolicyCapabilityError, _observe
from rangekeeper.specification.policy.predicate import evaluate as evaluate_expression
from rangekeeper.specification.policy.result import PolicyResult
from rangekeeper.specification.policy.validation import (
    validate_policy,
    validate_outcomes,
)


def _decide(decision, observation, *, units):
    quantities = {item.target.target: item.quantity for item in observation.quantities}
    selected = None
    for rule in decision.rules:
        try:
            result = evaluate_expression(rule.condition, quantities, units=units)
        except (ValueError, KeyError, ArithmeticError) as error:
            raise PolicyCapabilityError(str(error)) from error
        if type(result) is not bool:
            raise PolicyCapabilityError("rule must evaluate to Boolean")
        if result:
            selected = rule
            break
    actions = selected.actions if selected else decision.fallback
    assignments = []
    terminated = False
    for action in actions:
        if action.kind is ActionKind.ASSIGN:
            if action.target is None or action.quantity is None:
                raise PolicyCapabilityError(
                    "assign action requires a target and quantity"
                )
            assignments.append(
                Assignment(target=action.target, quantity=action.quantity)
            )
        elif action.kind is ActionKind.TERMINATE:
            terminated = True
    return DecisionOutcome(
        decision=decision.id,
        at=decision.at,
        rule=selected.id if selected else None,
        observations=observation.quantities,
        assignments=tuple(assignments),
        terminated=terminated,
        termination_reason=(
            ("rule_matched" if selected else "fallback") if terminated else None
        ),
    )


def evaluate(
    policy: Policy,
    *,
    model: Model,
    units: UnitSystem = default_units,
) -> PolicyResult:
    """Evaluate a validated finite declaration against one pinned recorded path."""
    if not isinstance(policy, Policy):
        raise TypeError("policy must be a Policy record")
    scope = scope_for_model(model)
    declaration = policy.to_data()
    validate_policy(declaration, scope=scope, units_compatible=units.compatible)
    provenance = model.provenance.to_data() if model.provenance else {}
    evidence = evidence_dates(provenance)
    controlled = {target.target for target in policy.targets}
    outcomes: list[DecisionOutcome] = []
    prior: dict[UUID, tuple[Quantity, date]] = {}
    for decision in policy.decisions:
        observation = _observe(
            scope,
            at=decision.at,
            bindings=decision.observations,
            evidence=evidence,
            prior=prior,
            controlled=controlled,
        )
        outcome = _decide(decision, observation, units=units)
        for assignment in outcome.assignments:
            if assignment.target.target in prior:
                raise PolicyCapabilityError(
                    "policy cannot assign the same control twice"
                )
            prior[assignment.target.target] = (assignment.quantity, outcome.at)
        outcomes.append(outcome)
        if outcome.terminated:
            break
    try:
        validate_outcomes(
            declaration,
            [item.to_data() for item in outcomes],
            scope=scope,
            provenance=provenance,
            units=units,
        )
    except ContractError as error:
        raise PolicyCapabilityError(str(error)) from error
    return PolicyResult(tuple(outcomes))
