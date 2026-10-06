"""Resolve observation availability before data reaches a decision rule."""

from collections.abc import Sequence
from datetime import date
from ..model import Model
from ..model._references import reference_key

from .._schema.records import ObservationBinding, ObservedQuantity, Quantity, Movement
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
        record = model.resolve(target)
        owner = model.owner_of(record.id) if isinstance(record, Movement) else record.id
        assert owner is not None
        value = model.value(owner)
        available = [
            d
            for d in (
                binding.available_at,
                evidence.get(reference_key(target.to_data())),
            )
            if d is not None
        ]
        if not isinstance(record, Movement):
            quantity = value.quantity if value.kind == "measurement" else None
        else:
            if value.kind != "flow" or value.flow is None:
                raise PolicyCapabilityError(
                    "observation requires a declared Flow shape"
                )
            item = record
            if item.date is not None:
                available.append(item.date)
            elif item.period is not None:
                # Period totals cannot be observed before their coverage is complete.
                available.append(item.resolve(timing="last_day"))
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
