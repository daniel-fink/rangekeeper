"""Six deliberately invalid public-domain operations; do not execute."""

from uuid import uuid4
from rangekeeper.model import Model, Metadata, Update
from rangekeeper.references import DocumentResolver
from rangekeeper.specification import Specification

model = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.7.0"))
model.entity("entity-code")
model.find_entities(classification="class-code")
model.metadata = Metadata(id=uuid4(), schema_version="0.7.0")
Update(system=None)
Specification(model)


def invalid_compose(resolver: DocumentResolver) -> None:
    model.compose(resolver=resolver)
