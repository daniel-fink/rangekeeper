"""Resolve recorded or previously decided quantities at explicit observation dates."""

from collections.abc import Sequence
from datetime import date

from rangekeeper.execution.rule.result import Observation
from rangekeeper.model import Model
from rangekeeper.model._scope import (
    recorded_quantity,
    resolve_reference,
    scope_for_model,
)
from rangekeeper.quantity import Quantity
from rangekeeper.run._rule.availability import available_on
from rangekeeper.schema.records import ObservationBinding, ObservedQuantity
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import RangekeeperError


class RuleCapabilityError(RangekeeperError, ValueError):
    """Missing, unavailable or endogenous quantities cannot drive a finite rule set."""

    code = Code.RULE_CAPABILITY


def _observe(scope, *, at, bindings, prior, controlled):
    result = []
    for binding in bindings:
        token = binding.target.target
        if token in prior:
            quantity, when = prior[token]
            available = max(when, binding.available_at or when)
        else:
            if token in controlled:
                raise RuleCapabilityError(
                    "rule observation requires an earlier decision; recorded controls are not current decisions"
                )
            target = binding.target.to_data()
            _, movement = resolve_reference(target, scope.targets)
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
                declared=binding.available_at,
            )
            data = recorded_quantity(target, scope.targets, scope.measures)
            quantity = Quantity.from_data(data) if data is not None else None
        if available is None or available > at:
            raise RuleCapabilityError(
                f"observation {binding.name} is unavailable at {at}"
            )
        if quantity is None:
            raise RuleCapabilityError(
                f"observation {binding.name} is unresolved; endogenous sequential rules are unsupported"
            )
        result.append(
            ObservedQuantity(
                name=binding.name,
                target=binding.target,
                quantity=quantity,
                available_at=available,
            )
        )
    return Observation(at=at, quantities=tuple(result))


def observe(
    *,
    model: Model,
    at: date,
    bindings: Sequence[ObservationBinding],
) -> Observation:
    """Read available quantities without mutation or inferred zero values.

    Undated period Movements become available on their last included date. Scalar
    observations require provenance or a declared date; explicit dates can delay
    access but cannot advance a coordinate or provenance boundary.
    """
    if type(at) is not date:
        raise TypeError("at must be a date")
    bindings = tuple(bindings)
    if any(not isinstance(binding, ObservationBinding) for binding in bindings):
        raise TypeError("bindings must be ObservationBinding records")
    scope = scope_for_model(model)
    return _observe(
        scope,
        at=at,
        bindings=bindings,
        prior={},
        controlled=frozenset(),
    )
