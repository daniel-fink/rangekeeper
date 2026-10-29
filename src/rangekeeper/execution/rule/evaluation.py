"""Finite rule orchestration, separate from numerical feasibility and storage."""

from datetime import date
from uuid import UUID

from rangekeeper.execution.rule.observation import RuleCapabilityError, _observe
from rangekeeper.execution.rule.result import RuleResult
from rangekeeper.model import Model
from rangekeeper.model._scope import scope_for_model
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.run._rule.availability import evidence_dates
from rangekeeper.run._rule.evidence import validate_evidence
from rangekeeper.run._rule.predicate import evaluate as evaluate_expression
from rangekeeper.schema.records import (
    ActionKind,
    Assignment,
    RuleEvidence,
    RuleSet,
)
from rangekeeper.shared.errors import ContractError
from rangekeeper.specification.rule.validation import validate_rules


def _decide(decision, observation, *, units):
    quantities = {item.target.target: item.quantity for item in observation.quantities}
    selected = None
    for rule in decision.rules:
        try:
            result = evaluate_expression(rule.condition, quantities, units=units)
        except (ValueError, KeyError, ArithmeticError) as error:
            raise RuleCapabilityError(str(error)) from error
        if type(result) is not bool:
            raise RuleCapabilityError("rule must evaluate to Boolean")
        if result:
            selected = rule
            break
    actions = selected.actions if selected else decision.fallback
    assignments = []
    terminated = False
    for action in actions:
        if action.kind is ActionKind.ASSIGN:
            if action.target is None or action.quantity is None:
                raise RuleCapabilityError(
                    "assign action requires a target and quantity"
                )
            assignments.append(
                Assignment(target=action.target, quantity=action.quantity)
            )
        elif action.kind is ActionKind.TERMINATE:
            terminated = True
    return RuleEvidence(
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
    *,
    rules: RuleSet,
    model: Model,
    units: UnitSystem | None = None,
) -> RuleResult:
    """Evaluate a validated finite declaration against one pinned recorded path.

    Without ``units``, evaluation uses the unit system of ``model``.
    """
    if not isinstance(rules, RuleSet):
        raise TypeError("rules must be a RuleSet record")
    units = model.unit_system if units is None else units
    scope = scope_for_model(model)
    declaration = rules.to_data()
    validate_rules(declaration, scope=scope, units_compatible=units.compatible)
    provenance = model.provenance.to_data() if model.provenance else {}
    evidence = evidence_dates(provenance)
    controlled = {target.target for target in rules.targets}
    outcomes: list[RuleEvidence] = []
    prior: dict[UUID, tuple[Quantity, date]] = {}
    for decision in rules.decisions:
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
                raise RuleCapabilityError("rules cannot assign the same control twice")
            prior[assignment.target.target] = (assignment.quantity, outcome.at)
        outcomes.append(outcome)
        if outcome.terminated:
            break
    try:
        validate_evidence(
            declaration,
            [item.to_data() for item in outcomes],
            scope=scope,
            provenance=provenance,
            units=units,
        )
    except ContractError as error:
        raise RuleCapabilityError(str(error)) from error
    return RuleResult(evidence=tuple(outcomes))
