from __future__ import annotations

from collections.abc import Iterable

import pint

from ...measure import Index
from ..model import Model
from ..view import View
from .context import RestoreContext
from .errors import SnapshotError
from .record import Record, Snapshot
from .selection import required_classifications, select_source


SCHEMA_VERSION = 1
RECORD_TYPES = frozenset({"classification", "entity", "assembly", "relationship"})


def snapshot(source: Model | View) -> Snapshot:
    entities, relationships = select_source(source)
    classifications = required_classifications(entities, relationships)
    records = (
        *(
            Record.from_classification(item)
            for item in sorted(classifications, key=Record.classification_id)
        ),
        *(
            Record.from_entity(item)
            for item in sorted(entities, key=lambda item: item.entity_id)
        ),
        *(
            Record.from_relationship(item)
            for item in sorted(relationships, key=lambda item: item.relationship_id)
        ),
    )
    return Snapshot(schema_version=SCHEMA_VERSION, records=records)


def restore(
    materialized: Snapshot,
    *,
    registry: pint.UnitRegistry = Index.registry,
) -> Model:
    if not isinstance(materialized, Snapshot):
        raise TypeError("materialized must be a Snapshot")
    if materialized.schema_version != SCHEMA_VERSION:
        raise SnapshotError(
            f"unsupported Snapshot schema version {materialized.schema_version}"
        )

    records = _partition_records(materialized.records)
    context = RestoreContext(registry)
    context.load_classifications(records["classification"])
    for record in (*records["entity"], *records["assembly"]):
        context.add_entity(record)
    for record in records["relationship"]:
        context.add_relationship(record)
    context.populate_assemblies()
    return context.build_model()


def _partition_records(records: Iterable[Record]) -> dict[str, list[Record]]:
    by_type: dict[str, list[Record]] = {record_type: [] for record_type in RECORD_TYPES}
    for record in records:
        try:
            by_type[record.record_type].append(record)
        except KeyError as error:
            raise SnapshotError(
                f"unknown record type {record.record_type!r}"
            ) from error
    return by_type
