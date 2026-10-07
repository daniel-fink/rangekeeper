"""Static examples for the generated boundary; also valid executable authoring."""

from rangekeeper.model import ClaimKind
from rangekeeper.model.expression import ExpressionKind
from rangekeeper.model import ValueKind

from uuid import UUID, uuid4
from datetime import date

from rangekeeper._schema.records import (
    Assembly,
    Characteristics,
    Claim,
    Entity,
    Expression,
    Flow,
    Location,
    Metadata,
    Method,
    Model,
    Quantity,
    Period,
    Movement,
    Value,
)

entity: Entity = Assembly(id=uuid4())
value = Value(
    id=uuid4(),
    key="rent",
    kind=ValueKind.MEASUREMENT,
    measure=uuid4(),
    quantity=Quantity(magnitude=0, units="AUD/year"),
)
traits = Characteristics(values=(value,))
model = Model(metadata=Metadata(id=uuid4(), schema_version="0.7.0"))
identity: UUID = model.metadata.id
claim = Claim(
    id=uuid4(),
    kind=ClaimKind.ASSERTED,
    method=Method(code="manual"),
    content={"ordered": [0, False, None]},
    sources=(Location(source=uuid4(), address={"line": "1"}), uuid4()),
)
expression = Expression(id=uuid4(), kind=ExpressionKind.BOOLEAN, boolean=False)
restored: Model = Model.from_data(model.to_data())

period = Period(start_inclusive=date(2026, 1, 1), end_exclusive=date(2026, 2, 1))
start: date = period.start_inclusive
movement = Movement(id=uuid4(), key="january", period=period)
payment_date: date | None = movement.date
flow = Flow(units="AUD", movements=(movement,))
movements: tuple[Movement, ...] = flow.movements
