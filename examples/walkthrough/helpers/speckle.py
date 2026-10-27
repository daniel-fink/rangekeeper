"""Decode canonical envelopes without authentication, network, storage or solving."""

import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from uuid import UUID

from rangekeeper.io import json as codec
from rangekeeper.model import Model
from rangekeeper.schema.runtime import copy_json


class MappingError(ValueError):
    """Invalid content with its source path and optional domain identity."""

    def __init__(self, message: str, *, path: str = "/", identity: str | None = None):
        self.path, self.identity = path, identity
        super().__init__(f"{path}: {message}" + (f" [{identity}]" if identity else ""))


# The same contract file drives C# constants and cross-language fixtures.
CONTRACT = json.loads(files(__package__).joinpath("speckle_contract.json").read_text())
FORMAT = CONTRACT["format"]
FIELDS = CONTRACT["fields"]


def validate_associations(model: Model, associations: object) -> list[dict]:
    """Copy external geometry associations, checking identity and revision scope.

    Geometry stays in the transport. Content and application IDs are opaque
    strings; they are never used as canonical identity or membership.
    """
    if not isinstance(associations, (list, tuple)):
        raise MappingError("associations must be an array", path="/rk_associations")
    result = []
    for index, raw in enumerate(associations):
        path = f"/rk_associations/{index}"
        if (
            not isinstance(raw, Mapping)
            or set(raw) - set(CONTRACT["association_fields"])
            or not set(CONTRACT["required_association_fields"]) <= set(raw)
        ):
            raise MappingError("invalid association fields", path=path)
        item = copy_json(raw)
        try:
            if UUID(item["model_revision"]) != model.id:
                raise ValueError("association refers to another Model revision")
            model.entity(UUID(item["domain_id"]))
            if "rhino_id" in item:
                UUID(item["rhino_id"])
            for key in ("application_id", "content_id"):
                if key in item and (not isinstance(item[key], str) or not item[key]):
                    raise ValueError(f"{key} must be nonempty text")
        except (ValueError, TypeError, LookupError) as error:
            raise MappingError(
                str(error), path=path, identity=item.get("domain_id")
            ) from error
        if item not in result:
            result.append(item)
    return result


def decode_model(payload: Mapping[str, object]) -> Model:
    """Validate a versioned envelope and return an immutable canonical Model.

    The canonical JSON property is a string, not a Speckle object hierarchy.
    Invalid envelopes raise MappingError. Source payloads need an explicit source
    reader; this operation does not infer Model membership from collection nesting.
    """
    if not isinstance(payload, Mapping) or payload.get(FIELDS["format"]) != FORMAT:
        raise MappingError(
            "expected canonical envelope; source data requires an explicit source reader"
        )
    raw = payload.get(FIELDS["model"])
    if not isinstance(raw, str):
        raise MappingError("canonical Model JSON must be a string", path="/rk_model")
    try:
        model = codec.loads(raw, kind=Model)
    except (ValueError, TypeError, LookupError) as error:
        raise MappingError(str(error), path="/rk_model") from error
    validate_associations(model, payload.get(FIELDS["associations"], []))
    return model


def encode_model(
    model: Model, *, associations: Sequence[Mapping[str, object]] = ()
) -> dict:
    """Return detached envelope data; no SDK object or publication is created."""
    if not isinstance(model, Model):
        raise TypeError("model must be Model")
    return {
        FIELDS["format"]: FORMAT,
        FIELDS["model"]: codec.dumps(model),
        FIELDS["associations"]: validate_associations(model, associations),
    }
