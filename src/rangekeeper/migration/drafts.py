"""Explicit upgrades of draft documents; historical Runs are never rewritten."""

from collections.abc import Mapping
from uuid import UUID, uuid4
from .._records import _json_copy
from ..model import Model
from ..specification import Specification
from .._schema.validation import document_version


def _references(node):
    """Change owned Expression wire fields while preserving opaque Claim content."""
    if isinstance(node, dict):
        if node.get("kind") == "reference" and isinstance(node.get("target"), str):
            node["target"] = {"value": node["target"]}
        for key, value in node.items():
            if key != "content":
                _references(value)
    elif isinstance(node, list):
        for value in node:
            _references(value)


def _revision(data, kind, versions, revision_id):
    result = _json_copy(data)
    metadata = result.get("metadata", {})
    if metadata.get("schema_version") not in versions:
        raise ValueError(f"expected {kind} version in {sorted(versions)}")
    old = metadata["id"]
    if revision_id is not None and str(revision_id) == old:
        raise ValueError("upgrade requires a new revision UUID")
    metadata.update(
        id=str(revision_id or uuid4()),
        previous=old,
        schema_version=document_version(kind),
    )
    return result


def upgrade_model(data: dict, *, revision_id: UUID | None = None) -> Model:
    """Upgrade Model 0.3.0/0.4.0 to a new 0.5.0 revision with stable Value identities.

    Scalar references gain their explicit ValueReference wrapper. Flow keys,
    dates, units, ordered mathematics and provenance remain unchanged. Invalid or
    unsupported old content fails validation; no input, store or file is changed.
    """
    result = _revision(data, "Model", {"0.3.0", "0.4.0"}, revision_id)
    _references(result.get("system"))
    return Model.from_data(result)


def upgrade_specification(
    data: dict,
    *,
    model: UUID | None = None,
    revisions: Mapping[UUID, UUID] | None = None,
    revision_id: UUID | None = None,
) -> Specification:
    """Upgrade 0.4.0 roles and expressions, requiring explicit new external pins.

    Pass the upgraded Model UUID and a complete mapping for includes/cases. A
    partial contribution needs neither when it has no such references. The caller
    then performs resolver-backed validation. Old Runs keep their original pins.
    """
    result = _revision(data, "Specification", {"0.4.0"}, revision_id)
    if result.get("model") is not None:
        if model is None:
            raise ValueError("upgraded Model revision must be supplied explicitly")
        result["model"] = str(model)
    for field in ("includes", "cases"):
        if result.get(field):
            if revisions is None or any(
                UUID(ref) not in revisions for ref in result[field]
            ):
                raise ValueError(f"complete upgraded {field} mapping required")
            result[field] = [str(revisions[UUID(ref)]) for ref in result[field]]
    for field in ("assignments", "estimates"):
        for assignment in result.get(field) or []:
            assignment["target"] = dict(value=assignment.pop("value"))
    if result.get("unknowns") is not None:
        result["unknowns"] = [dict(value=ref) for ref in result["unknowns"]]
    _references(result.get("formulations"))
    return Specification.from_data(result)
