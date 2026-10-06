"""Explicit upgrades of draft documents; historical Runs are never rewritten."""

from collections.abc import Mapping
from uuid import UUID, uuid4, uuid5
from .._records import _json_copy
from ..model import Model
from ..specification import Specification
from .._schema.validation import document_version


def _movement_id(value, key):
    """Map the former owner/key address deterministically, across document revisions."""
    return str(uuid5(UUID(str(value)), "movement:" + key))


def _walk(node, kind):
    """Traverse declared record slots only; arbitrary evidence mappings are opaque."""
    from .._schema.validation import _slot_map

    if not isinstance(node, dict):
        return
    yield node, kind
    for name, slot in _slot_map(kind).items():
        if slot["mapping"] or name not in node:
            continue
        records = [
            option["kind"]
            for option in slot["options"]
            if option["category"] == "record"
        ]
        if not records:
            continue
        children = node[name] if slot["many"] else [node[name]]
        for child in children or []:
            yield from _walk(child, records[0])


def _movements(node, kind="Model"):
    """Add identities only to declared Flow Values; opaque evidence stays unchanged."""
    for record, record_kind in _walk(node, kind):
        if (
            record_kind == "Value"
            and record.get("kind") == "flow"
            and record.get("flow") is not None
        ):
            for movement in record["flow"]["movements"]:
                if "id" not in movement:
                    movement["id"] = _movement_id(record["id"], movement["key"])


def _references(node, kind="Model"):
    """Rewrite typed references, without treating arbitrary value fields as addresses."""
    for record, record_kind in _walk(node, kind):
        if (
            record_kind == "Expression"
            and record.get("kind") == "reference"
            and isinstance(record.get("target"), str)
        ):
            record["target"] = {"target": record["target"]}
        if record_kind == "Reference" and "value" in record:
            value, movement = record.pop("value"), record.pop("movement", None)
            record["target"] = (
                value if movement is None else _movement_id(value, movement)
            )


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
    """Upgrade Model 0.3.0/0.4.0/0.5.0 into a complete 0.6.0 revision.

    Value identities stay fixed; old owner/key addresses determine Movement UUIDs. Flow keys,
    dates, units, ordered mathematics and provenance remain unchanged. Invalid or
    unsupported old content fails validation; no input, store or file is changed.
    """
    result = _revision(data, "Model", {"0.3.0", "0.4.0", "0.5.0"}, revision_id)
    _movements(result)
    _references(result)
    return Model.from_data(result)


def upgrade_specification(
    data: dict,
    *,
    model: UUID | None = None,
    revisions: Mapping[UUID, UUID] | None = None,
    revision_id: UUID | None = None,
) -> Specification:
    """Upgrade 0.4.0/0.5.0 roles and expressions, requiring explicit new external pins.

    Pass the upgraded Model UUID and a complete mapping for includes/cases. A
    partial contribution needs neither when it has no such references. The caller
    then performs resolver-backed validation. Old Runs keep their original pins.
    """
    result = _revision(data, "Specification", {"0.4.0", "0.5.0"}, revision_id)
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
            if "target" not in assignment:
                assignment["target"] = dict(value=assignment.pop("value"))
    if result.get("unknowns") is not None:
        result["unknowns"] = [
            dict(value=ref) if isinstance(ref, str) else ref
            for ref in result["unknowns"]
        ]
    _movements(result, "Specification")
    _references(result, "Specification")
    return Specification.from_data(result)
