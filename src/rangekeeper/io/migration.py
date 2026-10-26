"""Explicit canonical format migration; never alter an old artifact in place."""

from uuid import UUID, uuid4

from rangekeeper import Model
from rangekeeper.schema.validation import document_version


def model_07_to_08(model: Model, *, id: UUID | None = None) -> Model:
    """Keep old content, assign a new Model identity and retain its predecessor."""
    if model.metadata.schema_version != "0.7.0":
        raise ValueError("Expected a Model with schema 0.7.0")
    data = model.to_data()
    identity = id or uuid4()
    if not isinstance(identity, UUID) or identity == model.id:
        raise ValueError("Migration requires a new UUID")
    data["metadata"] = {
        **model.metadata.to_data(),
        "id": str(identity),
        "previous": str(model.id),
        "schema_version": document_version("Model"),
    }
    return Model.from_data(data)
