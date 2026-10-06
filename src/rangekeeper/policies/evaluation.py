"""Explicit finite policy orchestration, separate from numerical feasibility."""

from ..model import Model
from ..model._predicate import evaluate as evaluate_expression
from ..model._references import reference_key
from .._schema.records import (
    DecisionPoint,
    Decision,
    Policy,
    Assignment,
    ObservedQuantity,
)
from ..specification._policy_validation import validate_policy, validate_decisions
from ..model._validation import validate_model
from .._schema.validation import document_version
from ..units import default_units
from .observation import observe, PolicyCapabilityError
from .result import Observation, DecisionHistory, PolicyResult


def decide(
    point: DecisionPoint, observation: Observation, state: DecisionHistory
) -> Decision:
    """Apply the first true rule atomically, or its explicit fallback.

    The rule sees only the observation object. Prior decisions establish state;
    they cannot grant access to future data or an unrestricted Model.
    """
    if observation.at != point.at or any(
        o.available_at > point.at for o in observation.quantities
    ):
        raise PolicyCapabilityError("observation date exceeds decision boundary")
    if state.decisions and (
        state.decisions[-1].terminated or state.decisions[-1].at >= point.at
    ):
        raise PolicyCapabilityError("decision sequence is terminated or out of order")
    if [(o.name, o.target) for o in observation.quantities] != [
        (o.name, o.target) for o in point.observations
    ]:
        raise PolicyCapabilityError("observation does not match declared bindings")
    quantities = {
        reference_key(o.target.to_data()): o.quantity for o in observation.quantities
    }
    selected = None
    for rule in point.rules:
        try:
            result = evaluate_expression(rule.condition, quantities)
        except (ValueError, KeyError, ArithmeticError) as error:
            raise PolicyCapabilityError(str(error)) from error
        if type(result) is not bool:
            raise PolicyCapabilityError("rule must evaluate to Boolean")
        if result:
            selected = rule
            break
    actions = selected.actions if selected else point.fallback
    supplied = []
    for action in actions:
        if action.kind == "assign":
            assert action.target is not None and action.quantity is not None
            supplied.append(Assignment(target=action.target, quantity=action.quantity))
    assignments = tuple(supplied)
    prior = {
        reference_key(a.target.to_data())
        for d in state.decisions
        for a in d.assignments
    }
    if any(reference_key(a.target.to_data()) in prior for a in assignments):
        raise PolicyCapabilityError("policy cannot assign the same control twice")
    return Decision(
        point=point.id,
        at=point.at,
        rule=selected.id if selected else None,
        observations=observation.quantities,
        assignments=assignments,
        terminated=any(a.kind == "terminate" for a in actions),
        termination_reason=(
            ("rule_matched" if selected else "fallback")
            if any(a.kind == "terminate" for a in actions)
            else None
        ),
    )


def evaluate(policy: Policy, *, model: Model) -> PolicyResult:
    """Evaluate a finite policy against a pinned known path without mutation or IO.

    Only exogenous recorded quantities and earlier decisions are available. An
    unresolved endogenous observation fails explicitly; no staged solve occurs.
    """
    scope = validate_model(model.to_data(), document_version("Model"))
    validate_policy(
        policy.to_data(), scope=scope, units_compatible=default_units.compatible
    )
    decisions: list[Decision] = []
    controlled = {reference_key(t.to_data()) for t in policy.targets}
    for point in policy.points:
        prior = {
            reference_key(a.target.to_data()): (a.quantity, d.at)
            for d in decisions
            for a in d.assignments
        }
        items = []
        for binding in point.observations:
            token = reference_key(binding.target.to_data())
            if token in prior:
                quantity, available = prior[token]
                available = max(available, binding.available_at or available)
                if available > point.at:
                    raise PolicyCapabilityError("earlier decision is not yet available")
                items.append(
                    ObservedQuantity(
                        name=binding.name,
                        target=binding.target,
                        quantity=quantity,
                        available_at=available,
                    )
                )
            else:
                if token in controlled:
                    raise PolicyCapabilityError(
                        "policy observation requires an earlier decision; recorded controls are not current decisions"
                    )
                items.extend(
                    observe(model, at=point.at, bindings=(binding,)).quantities
                )
        decision = decide(
            point, Observation(point.at, tuple(items)), DecisionHistory(tuple(decisions))
        )
        decisions.append(decision)
        if decision.terminated:
            break
    validate_decisions(
        policy.to_data(),
        [d.to_data() for d in decisions],
        scope=scope,
        provenance=model.provenance.to_data() if model.provenance else {},
    )
    return PolicyResult(
        tuple(decisions), tuple(a for d in decisions for a in d.assignments)
    )
