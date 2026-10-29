"""Six deliberately invalid public-domain operations; do not execute."""

from uuid import uuid4

from rangekeeper.model import Metadata, Model, Update
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Specification

model = Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))
model.entity(id="entity-code")
model.find_entities(classification="class-code")
model.metadata = Metadata(id=uuid4(), schema_version="1.0.0")
Update(system=None)
Specification(record=model)


def invalid_compose(resolver: DocumentResolver) -> None:
    model.compose(resolver=resolver)
