"""Static examples for the generated boundary; also valid executable authoring."""

from uuid import UUID, uuid4

from rangekeeper._schema.records import (
    Assembly,
    Characteristics,
    Claim,
    Entity,
    Expression,
    Location,
    Metadata,
    Method,
    Model,
    Quantity,
    Value,
)

entity: Entity = Assembly(id=uuid4())
value = Value(
    id=uuid4(),
    key="rent",
    kind="measurement",
    measure=uuid4(),
    quantity=Quantity(magnitude=0, units="AUD/year"),
)
traits = Characteristics(values=(value,))
model = Model(metadata=Metadata(id=uuid4(), schema_version="0.3.0"))
identity: UUID = model.metadata.id
claim = Claim(
    id=uuid4(),
    kind="asserted",
    method=Method(code="manual"),
    content={"ordered": [0, False, None]},
    sources=(Location(source=uuid4(), address={"line": "1"}), uuid4()),
)
expression = Expression(id=uuid4(), kind="boolean", boolean=False)
restored: Model = Model.from_data(model.to_data())
