"""The canonical Speckle envelope binds associations to one Model revision."""

from uuid import uuid4

import pytest
from helpers.speckle import CONTRACT, MappingError, decode_model, encode_model

from rangekeeper.model import Entity, Metadata, Model, System, Update


def test_current_envelope_and_associations_bind_revision():
    entity = Entity(id=uuid4(), name="Current")
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        system=System(entities=(entity,)),
    )
    associations = [
        {
            "model_revision": str(model.id),
            "domain_id": str(entity.id),
            "content_id": "retained",
        }
    ]
    encoded = encode_model(model, associations=associations)
    assert decode_model(encoded).to_data() == model.to_data()
    revised = model.revise(
        Update(system=System(entities=(Entity(id=entity.id, name="Changed"),)))
    )
    with pytest.raises(MappingError, match="revision"):
        encode_model(revised, associations=associations)


def test_envelope_rejects_source_payloads_and_foreign_associations():
    with pytest.raises(MappingError, match="canonical envelope"):
        decode_model({"speckle_type": "Base"})
    entity = Entity(id=uuid4(), name="Current")
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        system=System(entities=(entity,)),
    )
    with pytest.raises(MappingError, match="invalid association fields"):
        encode_model(model, associations=[{"domain_id": str(entity.id)}])
    assert CONTRACT["format"] == "rk.speckle-model/v1"
