"""Expected static errors. This file is deliberately not executable."""

from uuid import uuid4
from rangekeeper._schema.records import Entity, Expression, Location, Quantity

Entity()  # Missing required identity.
Entity(id="not a UUID")
Entity(id=uuid4(), unknown=True)
Quantity(magnitude="1", units="m")
Expression(id=uuid4(), kind="unknown")
Expression(id=uuid4(), kind="quantity", quantity=Entity(id=uuid4()))
Location(source=uuid4(), address=("line",))
entity = Entity(id=uuid4())
entity.name = "mutable"
