"""Typed fluent operations on canonical and nested records."""

from datetime import date
from uuid import uuid4
from rangekeeper.model.flow import Flow, Movement
from rangekeeper.model.distribution import Distribution
from rangekeeper._schema.records import Assembly, Span, Value
from rangekeeper.calculations.account import Account
from rangekeeper.calculations.series import Aggregation, align

flow: Flow = Flow.from_events([date(2026, 1, 1)], [1], units="m").check()
movement: Movement = flow.movements[0].replace(magnitude=2, claims=())
number: float = movement.number
day: date = movement.resolve()
value: Value = Value(id=uuid4(), key="area", kind="flow", measure=uuid4(), flow=flow)
if value.flow is not None:
    copied: Flow = value.flow.replace(movements=(movement,)).check(resolved=True)
result: Aggregation = align([flow, flow]).reduce(reducer="max")
probabilities: tuple[float, ...] = Distribution.pert().cdf([0.0, 1.0])
assembly: Assembly = Assembly(id=uuid4()).replace(name="Group")
span: Span = Span(start=date(2026, 1, 1), end=date(2027, 1, 1)).replace(name="Year")
