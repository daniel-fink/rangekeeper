"""Static public-domain authoring and resolver-consumer examples."""

from uuid import UUID, uuid4

from rangekeeper.metadata import Metadata
from rangekeeper.model import Model, Entity, System, Update
from rangekeeper.references import DocumentResolver
from rangekeeper.specification import (
    Specification,
    SpecificationRecord,
    compose,
    validate,
)

entity = Entity(id=uuid4(), code="A")
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
    system=System(entities=(entity,)),
)
identity: UUID = model.entity(entity.id).id
revision: Model = model.revise(Update(system=System()))
specification = Specification(
    SpecificationRecord(
        metadata=Metadata(id=uuid4(), schema_version="0.4.0"), model=model.id
    )
)


def investigation(resolver: DocumentResolver) -> tuple[UUID, ...]:
    """Consume a read-only dependency; no store implementation is assumed."""
    composition = compose(specification, resolver=resolver)
    validate(composition, resolver=resolver).raise_if_invalid()
    return composition.contributors
