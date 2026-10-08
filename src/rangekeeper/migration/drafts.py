"""Explicit source-layout upgrades; canonical readers accept current versions only."""

from collections.abc import Mapping
from uuid import UUID, uuid4, uuid5

from rangekeeper.schema.runtime import _json_copy
from rangekeeper.schema.records import Metadata
from rangekeeper.schema.validation import document_version, _slot_map

# These explicit differences describe the supported draft layouts. They are not
# canonical aliases: conversion walks the source before changing any field name.
_SOURCE_TYPES = {"Decision": "DecisionPoint", "DecisionOutcome": "Decision"}
_TARGET_TYPES = {value: key for key, value in _SOURCE_TYPES.items()}
_SOURCE_FIELDS = {
    "Period": {"start_inclusive": "start", "end_exclusive": "end"},
    "Span": {"start_inclusive": "start", "end_exclusive": "end"},
    "Policy": {"decisions": "points"},
    "Decision": {"decision": "point"},
    "Report": {"outcomes": "decisions"},
}


def _movement_id(value, key):
    return str(uuid5(UUID(str(value)), "movement:" + key))


def _walk(node, kind):
    """Traverse supported source slots, excluding opaque evidence payloads."""
    if not isinstance(node, dict):
        return
    yield node, kind
    renames = _SOURCE_FIELDS.get(kind, {})
    for name, slot in _slot_map(_TARGET_TYPES.get(kind, kind)).items():
        source = renames.get(name, name)
        if source != name and name in node:
            raise ValueError(f"mixed source layout: {kind}.{name}")
        if slot["mapping"] or source not in node or node[source] is None:
            continue
        child = next(
            (o["kind"] for o in slot["options"] if o["category"] == "record"), None
        )
        if child is None:
            continue
        # CalculationProvenance did not exist in any supported source version.
        if child == "CalculationProvenance":
            raise ValueError("calculation provenance is not part of the source format")
        child = _SOURCE_TYPES.get(child, child)
        for value in node[source] if slot["many"] else [node[source]]:
            yield from _walk(value, child)


def _convert(result, kind):
    records = list(_walk(result, kind))
    for record, record_kind in records:
        if (
            record_kind == "Value"
            and record.get("kind") == "flow"
            and record.get("flow") is not None
        ):
            for movement in record["flow"]["movements"]:
                if "id" not in movement:
                    movement["id"] = _movement_id(record["id"], movement["key"])
        if (
            record_kind == "Expression"
            and record.get("kind") == "reference"
            and isinstance(record.get("target"), str)
        ):
            record["target"] = {"target": record["target"]}
        if record_kind == "Reference" and "value" in record:
            if "target" in record:
                raise ValueError("mixed direct and owner/key Reference layout")
            value, movement = record.pop("value"), record.pop("movement", None)
            record["target"] = (
                value if movement is None else _movement_id(value, movement)
            )
        for target, source in _SOURCE_FIELDS.get(record_kind, {}).items():
            if source in record:
                record[target] = record.pop(source)
    return result


def _revision(data, kind, versions, revision_id):
    result = _json_copy(data)
    metadata = result.get("metadata", {})
    if metadata.get("schema_version") not in versions:
        raise ValueError(f"expected {kind} version in {sorted(versions)}")
    source = Metadata.from_data(metadata)
    old = source.id
    if revision_id is not None and (
        not isinstance(revision_id, UUID) or revision_id in (old, source.previous)
    ):
        raise ValueError("upgrade requires a new revision UUID")
    metadata.update(
        id=str(revision_id or uuid4()),
        previous=str(old),
        schema_version=document_version(kind),
    )
    return result


def upgrade_model(data: dict, *, revision_id: UUID | None = None):
    """Convert Model 0.3–0.6 into a new revision without recalculating results.

    The returned metadata.previous and metadata.id form the explicit revision map.
    Original files, historical Runs, quantities and captured inputs stay unchanged.
    """
    from rangekeeper.model import Model
    from rangekeeper.migration.scenarios import convert_names

    result = _revision(data, "Model", {"0.3.0", "0.4.0", "0.5.0", "0.6.0"}, revision_id)
    _convert(result, "Model")
    convert_names(result)
    return Model.from_data(result)


def upgrade_specification(
    data: dict,
    *,
    model: UUID | None = None,
    revisions: Mapping[UUID, UUID] | None = None,
    revision_id: UUID | None = None,
):
    """Convert Specification 0.4–0.6 with explicit new Model/include/case pins.

    Conversion performs no IO. Validate the new dependency graph with its resolver
    before publication; absent/conflicting maps cannot select a latest revision.
    """
    from rangekeeper.specification import Specification

    result = _revision(data, "Specification", {"0.4.0", "0.5.0", "0.6.0"}, revision_id)
    revision_map = dict(revisions or {})
    if any(
        not isinstance(old, UUID) or not isinstance(new, UUID) or old == new
        for old, new in revision_map.items()
    ):
        raise ValueError("revision mappings require distinct old and new UUIDs")
    if result.get("model") is not None:
        old = UUID(result["model"])
        mapped = revision_map.get(old)
        if model is not None and (
            not isinstance(model, UUID)
            or model == old
            or mapped is not None
            and model != mapped
        ):
            raise ValueError("conflicting or unchanged Model revision")
        selected = model or mapped
        if selected is None:
            raise ValueError("upgraded Model revision must be supplied explicitly")
        revision_map[old] = selected
        result["model"] = str(revision_map[old])
    if len(set(revision_map.values())) != len(revision_map):
        raise ValueError("conflicting revision mappings")
    if revision_map.keys() & set(revision_map.values()):
        raise ValueError("revision mappings cannot reuse known source UUIDs")
    if UUID(result["metadata"]["id"]) in (
        revision_map.keys() | set(revision_map.values())
    ):
        raise ValueError("Specification revision UUID conflicts with a dependency")
    for field in ("includes", "cases"):
        if result.get(field):
            if any(UUID(ref) not in revision_map for ref in result[field]):
                raise ValueError(f"complete upgraded {field} mapping required")
            result[field] = [str(revision_map[UUID(ref)]) for ref in result[field]]
    for field in ("assignments", "estimates"):
        for assignment in result.get(field) or []:
            if "value" in assignment and "target" in assignment:
                raise ValueError("mixed source Assignment target layout")
            if "target" not in assignment:
                assignment["target"] = {"value": assignment.pop("value")}
    if result.get("unknowns") is not None:
        result["unknowns"] = [
            {"value": ref} if isinstance(ref, str) else ref
            for ref in result["unknowns"]
        ]
    _convert(result, "Specification")
    return Specification.from_data(result)
