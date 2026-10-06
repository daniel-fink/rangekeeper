"""Resolve observation availability before data reaches a decision rule."""

from collections.abc import Sequence
from datetime import date
from ..model import Model
from ..model._references import reference_key
from ..model.flow import resolve_date
from .._schema.records import ObservationBinding, ObservedQuantity, Quantity
from ..duration.calendar import require_date
from .result import Observation


class PolicyCapabilityError(ValueError):
    """Missing/unavailable/endogenous observations cannot drive this finite policy."""


def observe(
    model: Model, *, at: date, bindings: Sequence[ObservationBinding]
) -> Observation:
    """Copy declared quantities available by at; never infer missing data as zero.

    Availability cannot precede a Movement's recorded date or its realization
    evidence. Undated period data requires explicit availability. Scalar inputs
    also need an explicit availability date. Reading does not change the Model.
    """
    require_date(at)
    evidence: dict[str, date] = {}
    for realization in (
        model.provenance.scenarios
        if model.provenance and model.provenance.scenarios
        else ()
    ):
        for availability in realization.availability:
            token = reference_key(availability.target.to_data())
            evidence[token] = max(
                evidence.get(token, date.min), availability.available_at
            )
    result = []
    for binding in bindings:
        target = binding.target
        value = model.value(target.value)
        available = [
            d
            for d in (
                binding.available_at,
                evidence.get(reference_key(target.to_data())),
            )
            if d is not None
        ]
        if target.movement is None:
            quantity = value.quantity if value.kind == "measurement" else None
        else:
            if value.kind != "flow" or value.flow is None:
                raise PolicyCapabilityError(
                    "observation requires a declared Flow shape"
                )
            matches = [m for m in value.flow.movements if m.key == target.movement]
            if len(matches) != 1:
                raise PolicyCapabilityError("observation Movement does not exist")
            item = matches[0]
            if item.date is not None:
                available.append(item.date)
            elif item.period is not None:
                # Period totals cannot be observed before their coverage is complete.
                available.append(resolve_date(item, timing="last_day"))
            quantity = (
                None
                if item.magnitude is None
                else Quantity(magnitude=item.magnitude, units=value.flow.units)
            )
        if not available or max(available) > at:
            raise PolicyCapabilityError(
                f"observation {binding.name} is unavailable at {at}"
            )
        if quantity is None:
            raise PolicyCapabilityError(
                f"observation {binding.name} is unresolved; endogenous sequential policies are unsupported"
            )
        result.append(
            ObservedQuantity(
                name=binding.name,
                target=target,
                quantity=quantity,
                available_at=max(available),
            )
        )
    return Observation(at, tuple(result))
