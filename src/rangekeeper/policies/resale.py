"""Period-end threshold resale declarations; the scenario history stays intact."""

from uuid import UUID
from collections.abc import Mapping
from ..model import Model

from .._schema.records import (
    Policy,
    DecisionPoint,
    Rule,
    Action,
    ObservationBinding,
    Quantity,
    ValueReference,
)
from ..formulations._alignment import aligned, target, shape
from ..formulations._identity import identify, identify_tree
from ..formulations.expression import reference, literal, binary


def build_stop_gain_resale_policy(
    model: Model,
    *,
    id: UUID,
    pricing_factor: UUID,
    holding: UUID,
    sale: UUID,
    threshold: float,
    minimum_holding_periods: int = 1,
    mapping: Mapping[str, str] | None = None
) -> Policy:
    """Declare one sale at first factor > threshold, otherwise at the final horizon.

    Decisions occur on each period's last included date. The sale period has
    holding=1 and sale=1, so its operating cashflow is included. Later controls
    are zero. Minimum holding is a positive count including the sale period.
    An explicit mapping selects observed keys when the market extends beyond the
    investment horizon. Availability still prevents future observations.
    Threshold is dimensionless. No path, cashflow or Model is changed.
    """
    if mapping is None:
        rows = aligned(model, (pricing_factor, sale), holding)
    else:
        factors = {m.key: m for m in shape(model, pricing_factor).movements}
        controls = aligned(model, (sale,), holding)
        if set(mapping) != {h.key for h, _ in controls} or not set(
            mapping.values()
        ) <= set(factors):
            raise ValueError("policy mapping must cover every control coordinate")
        rows = [(h, (factors[mapping[h.key]], matches[0])) for h, matches in controls]
    if (
        not rows
        or type(minimum_holding_periods) is not int
        or not 1 <= minimum_holding_periods <= len(rows)
    ):
        raise ValueError("minimum holding must lie within the declared horizon")
    targets = tuple(
        ref for h, (_, s) in rows for ref in (target(holding, h), target(sale, s))
    )

    def assign(ref, magnitude):
        return Action(
            kind="assign",
            target=ref,
            quantity=Quantity(magnitude=magnitude, units="dimensionless"),
        )

    def sell(index):
        actions = []
        for offset, (h, (_, s)) in enumerate(rows[index:]):
            actions.extend(
                (
                    assign(target(holding, h), int(offset == 0)),
                    assign(target(sale, s), int(offset == 0)),
                )
            )
        return (*actions, Action(kind="terminate"))

    points = []
    for index, (h, (factor, s)) in enumerate(rows):
        at = h.resolve(timing="last_day")
        observation = ObservationBinding(
            name="pricing_factor", target=target(pricing_factor, factor)
        )
        condition = identify_tree(
            id,
            "resale",
            h.key,
            binary("greater_than", reference(observation.target), literal(threshold)),
        )
        rules = (
            (
                Rule(
                    id=identify(id, h.key, "rule"),
                    condition=condition,
                    actions=sell(index),
                ),
            )
            if index + 1 >= minimum_holding_periods
            else ()
        )
        fallback = (
            sell(index)
            if index == len(rows) - 1
            else (assign(target(holding, h), 1), assign(target(sale, s), 0))
        )
        points.append(
            DecisionPoint(
                id=identify(id, h.key, "point"),
                at=at,
                observations=(observation,),
                rules=rules,
                fallback=fallback,
            )
        )
    return Policy(id=id, targets=targets, points=tuple(points))
