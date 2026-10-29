"""Static public-domain authoring and resolver-consumer examples."""

from uuid import UUID, uuid4

from rangekeeper.model import Entity, Model, System, Update
from rangekeeper.schema import Metadata
from rangekeeper.schema.index import RecordLocation
from rangekeeper.schema.runtime import Record
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.specification import Specification, SpecificationRecord

entity = Entity(id=uuid4(), code="A")
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
    system=System(entities=(entity,)),
)
identity: UUID = model.entity(id=entity.id).id
location: RecordLocation = model.record_at("/system/entities/0")
record: Record = model.record_by_id(entity.id).record
owner: UUID | None = location.owner_id
path: str = location.path
revision: Model = model.revise(Update(system=System()))
specification = Specification(
    record=SpecificationRecord(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"), model=model.id
    )
)


def investigation(resolver: DocumentResolver) -> tuple[UUID, ...]:
    """Consume a read-only dependency; no store implementation is assumed."""
    composition = specification.compose(resolver=resolver)
    composition.validate(resolver=resolver).raise_if_invalid()
    return composition.contributor_ids
