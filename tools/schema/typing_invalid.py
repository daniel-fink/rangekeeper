"""Expected static errors. This file is deliberately not executable."""

from rangekeeper.model.expression import ExpressionKind
from rangekeeper.model import ValueKind

from uuid import uuid4
from rangekeeper.schema.records import Entity, Expression, Location, Quantity

Entity()  # Missing required identity.
Entity(id="not a UUID")
Entity(id=uuid4(), unknown=True)
Quantity(magnitude="1", units="m")
Expression(id=uuid4(), kind="boolean")  # Valid wire text is not a typed Enum member.
Expression(id=uuid4(), kind=ValueKind.MEASUREMENT)  # Unrelated enums remain distinct.
Expression(id=uuid4(), kind=ExpressionKind.QUANTITY, quantity=Entity(id=uuid4()))
Location(source=uuid4(), address=("line",))
entity = Entity(id=uuid4())
entity.name = "mutable"
