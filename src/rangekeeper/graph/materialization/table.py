from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

import pint

from ...measure import Measure
from ..assembly import Assembly
from ..entity import Entity
from ..view import View
from .errors import TableError


GroupFunction = Callable[[tuple[object, ...]], object]

ENTITY_FIELDS = frozenset(
    {
        "entity_id",
        "code",
        "name",
        "entity_type",
        "classification_code",
        "classification_name",
        "classification_taxonomy",
    }
)
DEFAULT_ENTITY_FIELDS = (
    "entity_id",
    "name",
    "entity_type",
    "classification_code",
)


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]

    def __post_init__(self) -> None:
        columns = tuple(self.columns)
        if not all(isinstance(column, str) and column.strip() for column in columns):
            raise ValueError("columns must contain only non-empty strings")
        if len(columns) != len(set(columns)):
            raise ValueError("columns must be unique")
        normalized_rows = []
        for row in tuple(self.rows):
            if not isinstance(row, Mapping):
                raise TypeError("rows must contain only mappings")
            missing = set(columns).difference(row)
            extra = set(row).difference(columns)
            if missing or extra:
                raise ValueError(
                    "row columns do not match Table columns: "
                    f"missing={sorted(missing)}, extra={sorted(extra)}"
                )
            normalized_rows.append(
                MappingProxyType({column: row[column] for column in columns})
            )
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "rows", tuple(normalized_rows))

    def column(self, name: str) -> tuple[object, ...]:
        if name not in self.columns:
            raise KeyError(name)
        return tuple(row[name] for row in self.rows)

    @classmethod
    def from_view(
        cls,
        view: View,
        *,
        fields: Iterable[str] = DEFAULT_ENTITY_FIELDS,
        labels: Iterable[str] = (),
        measurements: Mapping[Measure | str, pint.Unit | str | None] | None = None,
        features: Iterable[str] = (),
    ) -> Table:
        if not isinstance(view, View):
            raise TypeError("view must be a View")
        selected_fields = _validated_names(fields, "fields")
        unknown_fields = set(selected_fields).difference(ENTITY_FIELDS)
        if unknown_fields:
            raise TableError(f"unknown entity fields: {sorted(unknown_fields)}")
        label_keys = _validated_names(labels, "labels")
        feature_names = _validated_names(features, "features")
        measure_columns = _measurement_columns(view, measurements)

        columns = (
            *selected_fields,
            *(f"label.{key}" for key in label_keys),
            *(column for _, _, column in measure_columns),
            *(f"feature.{name}" for name in feature_names),
        )
        if len(columns) != len(set(columns)):
            raise TableError("selected Table columns collide")

        rows = []
        for entity in view.entities:
            row = {
                field: _entity_field(entity, field, view=view)
                for field in selected_fields
            }
            for key in label_keys:
                label = entity.labels.get(key)
                row[f"label.{key}"] = (
                    ()
                    if label is None
                    else tuple(
                        classification.code for classification in label.classifications
                    )
                )
            for measure, target_unit, column in measure_columns:
                measurement = entity.characteristics.measurement(measure)
                quantity = None if measurement is None else measurement.quantity
                row[column] = (
                    None if quantity is None else quantity.to(target_unit).magnitude
                )
            for name in feature_names:
                feature = entity.features.get(name)
                row[f"feature.{name}"] = None if feature is None else feature.value
            rows.append(row)
        return cls(columns=columns, rows=tuple(rows))

    @classmethod
    def from_arborescence(
        cls,
        view: View,
        *,
        fields: Iterable[str] = DEFAULT_ENTITY_FIELDS,
        labels: Iterable[str] = (),
        measurements: Mapping[Measure | str, pint.Unit | str | None] | None = None,
        features: Iterable[str] = (),
    ) -> Table:
        """Project a parent-to-child arborescence with explicit parent IDs."""
        if not isinstance(view, View):
            raise TypeError("view must be a View")
        selected_fields = _validated_names(fields, "fields")
        if "entity_id" not in selected_fields:
            raise TableError("arborescence Tables require the 'entity_id' field")
        if not view.is_arborescence:
            raise TableError("view must be a non-empty parent-to-child arborescence")

        projected = cls.from_view(
            view,
            fields=selected_fields,
            labels=labels,
            measurements=measurements,
            features=features,
        )
        parent_by_entity = {
            relationship.target_id: relationship.source_id
            for relationship in view.relationships
        }
        children_by_parent: dict[UUID, list[UUID]] = {}
        for child_id, parent_id in parent_by_entity.items():
            children_by_parent.setdefault(parent_id, []).append(child_id)

        root_id = view.roots[0].id
        entity_order = _arborescence_preorder(root_id, children_by_parent)
        projected_by_entity = {row["entity_id"]: row for row in projected.rows}
        entity_id_index = projected.columns.index("entity_id")
        columns = (
            *projected.columns[: entity_id_index + 1],
            "parent_id",
            *projected.columns[entity_id_index + 1 :],
        )
        rows = []
        for entity_id in entity_order:
            projected_row = projected_by_entity[entity_id]
            row = dict(projected_row)
            row["parent_id"] = parent_by_entity.get(entity_id)
            rows.append({column: row[column] for column in columns})
        return cls(columns=columns, rows=tuple(rows))

    def group_by(
        self,
        *,
        by: Iterable[str],
        aggregations: Mapping[str, GroupFunction],
    ) -> Table:
        keys = tuple(by)
        if not keys:
            raise TableError("group_by requires at least one key column")
        if len(keys) != len(set(keys)):
            raise TableError("group_by key columns must be unique")
        for column in keys:
            if column not in self.columns:
                raise TableError(f"unknown group_by column {column!r}")
        if not isinstance(aggregations, Mapping) or not aggregations:
            raise TableError("aggregations must be a non-empty mapping")
        for column, function in aggregations.items():
            if column not in self.columns:
                raise TableError(f"unknown aggregation column {column!r}")
            if column in keys:
                raise TableError(f"aggregation column {column!r} is also a group key")
            if not callable(function):
                raise TypeError(f"aggregation for {column!r} must be callable")

        grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = {}
        for row in self.rows:
            key = tuple(row[column] for column in keys)
            try:
                hash(key)
            except TypeError as error:
                raise TableError("group_by key values must be hashable") from error
            grouped.setdefault(key, []).append(row)

        columns = (*keys, *aggregations)
        rows = []
        for key, grouped_rows in grouped.items():
            row = dict(zip(keys, key))
            for column, function in aggregations.items():
                row[column] = function(
                    tuple(grouped_row[column] for grouped_row in grouped_rows)
                )
            rows.append(row)
        return Table(columns=columns, rows=tuple(rows))


def _validated_names(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field} must be an iterable of strings, not a string")
    materialized = tuple(values)
    if not all(isinstance(value, str) and value.strip() for value in materialized):
        raise ValueError(f"{field} must contain only non-empty strings")
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"{field} must not contain duplicates")
    return materialized


def _arborescence_preorder(
    root_id: UUID,
    children_by_parent: Mapping[UUID, Iterable[UUID]],
) -> tuple[UUID, ...]:
    ordered = []
    pending = [root_id]
    while pending:
        entity_id = pending.pop()
        ordered.append(entity_id)
        pending.extend(sorted(children_by_parent.get(entity_id, ()), reverse=True))
    return tuple(ordered)


def _measurement_columns(
    view: View,
    measurements: Mapping[Measure | str, pint.Unit | str | None] | None,
) -> tuple[tuple[Measure, pint.Unit, str], ...]:
    if measurements is None:
        return ()
    if not isinstance(measurements, Mapping):
        raise TypeError("measurements must be a mapping or None")
    columns = []
    for reference, target in measurements.items():
        measure = (
            view.graph.definitions.measure(reference)
            if isinstance(reference, str)
            else view.graph.definitions.canonical_measure(reference)
        )
        if target is None:
            target_unit = measure.units
        elif isinstance(target, pint.Unit):
            target_unit = measure.units._REGISTRY.parse_units(str(target))
        elif isinstance(target, str):
            target_unit = measure.units._REGISTRY.parse_units(target)
        else:
            raise TypeError("measure target units must be Pint Units, strings, or None")
        if target_unit.dimensionality != measure.units.dimensionality:
            raise pint.DimensionalityError(target_unit, measure.units)
        columns.append(
            (
                measure,
                target_unit,
                f"measurement.{measure.code}",
            )
        )
    return tuple(columns)


def _entity_field(entity: Entity, field: str, *, view: View) -> object:
    if field == "entity_id":
        return entity.id
    if field == "code":
        return entity.code
    if field == "name":
        return entity.name
    if field == "entity_type":
        return "assembly" if isinstance(entity, Assembly) else "entity"
    if field == "classification_code":
        return entity.classification.code if entity.classification else None
    if field == "classification_name":
        return entity.classification.name if entity.classification else None
    if field == "classification_taxonomy":
        if entity.classification is None:
            return None
        return view.graph.definitions.taxonomy_of(entity.classification).code
    raise TableError(f"unknown entity field {field!r}")
