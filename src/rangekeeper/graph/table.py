from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

import pint

from ..measure import Measure
from .assembly import Assembly
from .entity import Entity
from .view import View


__all__ = ["Table", "TableError"]


_ENTITY_FIELD_NAMES = frozenset(
    {
        "entity_id",
        "code",
        "name",
        "entity_kind",
        "classification_code",
        "classification_name",
        "taxonomy_code",
    }
)
_DEFAULT_ENTITY_FIELD_NAMES = (
    "entity_id",
    "name",
    "entity_kind",
    "classification_code",
)


class TableError(ValueError):
    """Raised when Table data or projection arguments are invalid."""


@dataclass(frozen=True, slots=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]

    def __post_init__(self) -> None:
        columns = _validate_names(self.columns, "columns")
        normalized_rows = []
        for row in tuple(self.rows):
            if not isinstance(row, Mapping):
                raise TypeError("rows must contain only mappings")
            missing = tuple(column for column in columns if column not in row)
            extra = tuple(column for column in row if column not in columns)
            if missing or extra:
                raise TableError(
                    "row columns do not match Table columns: "
                    f"missing={list(missing)!r}, extra={list(extra)!r}"
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
        entity_fields: Iterable[str] = _DEFAULT_ENTITY_FIELD_NAMES,
        labels: Iterable[str] = (),
        measurements: Mapping[Measure | str, pint.Unit | str | None] | None = None,
        features: Iterable[str] = (),
    ) -> Table:
        if not isinstance(view, View):
            raise TypeError("view must be a View")
        entity_field_names = _validate_names(entity_fields, "entity_fields")
        unknown_entity_fields = set(entity_field_names).difference(_ENTITY_FIELD_NAMES)
        if unknown_entity_fields:
            raise TableError(f"unknown entity fields: {sorted(unknown_entity_fields)}")
        label_keys = _validate_names(labels, "labels")
        feature_names = _validate_names(features, "features")
        measurement_projections = _measurement_projections(view, measurements)

        columns = (
            *entity_field_names,
            *(f"label.{key}" for key in label_keys),
            *(column_name for _, _, column_name in measurement_projections),
            *(f"feature.{name}" for name in feature_names),
        )
        if len(columns) != len(set(columns)):
            raise TableError("selected Table columns collide")

        rows = []
        for entity in view.entities:
            row = {
                field_name: _entity_value(entity, field_name, view=view)
                for field_name in entity_field_names
            }
            for key in label_keys:
                label = entity.labels.get(key)
                row[f"label.{key}"] = (
                    ()
                    if label is None
                    else tuple(
                        (
                            view.graph.definitions.taxonomy_for(classification).code,
                            classification.code,
                        )
                        for classification in label.classifications
                    )
                )
            for measure, target_units, column_name in measurement_projections:
                measurement = entity.characteristics.measurement(measure)
                quantity = None if measurement is None else measurement.quantity
                row[column_name] = (
                    None if quantity is None else quantity.to(target_units).magnitude
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
        entity_fields: Iterable[str] = _DEFAULT_ENTITY_FIELD_NAMES,
        labels: Iterable[str] = (),
        measurements: Mapping[Measure | str, pint.Unit | str | None] | None = None,
        features: Iterable[str] = (),
    ) -> Table:
        """Project a parent-to-child arborescence with explicit parent IDs."""
        projected = cls.from_view(
            view,
            entity_fields=entity_fields,
            labels=labels,
            measurements=measurements,
            features=features,
        )
        if "entity_id" not in projected.columns:
            raise TableError("arborescence Tables require the 'entity_id' field")
        if not view.is_arborescence:
            raise TableError("view must be a non-empty parent-to-child arborescence")

        parent_by_entity = {
            relationship.target_id: relationship.source_id
            for relationship in view.relationships
        }
        children_by_parent: dict[UUID, list[UUID]] = {}
        for child_id, parent_id in parent_by_entity.items():
            children_by_parent.setdefault(parent_id, []).append(child_id)

        root_id = view.roots[0].id
        entity_order = _preorder(root_id, children_by_parent)
        projected_by_entity = {row["entity_id"]: row for row in projected.rows}
        entity_id_index = projected.columns.index("entity_id")
        columns = (
            *projected.columns[: entity_id_index + 1],
            "parent_id",
            *projected.columns[entity_id_index + 1 :],
        )
        rows = []
        for entity_id in entity_order:
            row = dict(projected_by_entity[entity_id])
            row["parent_id"] = parent_by_entity.get(entity_id)
            rows.append({column: row[column] for column in columns})
        return cls(columns=columns, rows=tuple(rows))


def _validate_names(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field} must be an iterable of strings, not a string")
    materialized = tuple(values)
    if not all(isinstance(value, str) and value.strip() for value in materialized):
        raise TableError(f"{field} must contain only non-empty strings")
    if len(materialized) != len(set(materialized)):
        raise TableError(f"{field} must not contain duplicates")
    return materialized


def _preorder(
    root_id: UUID,
    children_by_parent: Mapping[UUID, Iterable[UUID]],
) -> tuple[UUID, ...]:
    ordered = []
    pending = [root_id]
    while pending:
        entity_id = pending.pop()
        ordered.append(entity_id)
        pending.extend(reversed(tuple(children_by_parent.get(entity_id, ()))))
    return tuple(ordered)


def _measurement_projections(
    view: View,
    measurements: Mapping[Measure | str, pint.Unit | str | None] | None,
) -> tuple[tuple[Measure, pint.Unit, str], ...]:
    if measurements is None:
        return ()
    if not isinstance(measurements, Mapping):
        raise TypeError("measurements must be a mapping or None")
    projections = []
    for measure_reference, requested_units in measurements.items():
        measure = (
            view.graph.definitions.measures[measure_reference]
            if isinstance(measure_reference, str)
            else view.graph.definitions.measures._require_catalog_instance(
                measure_reference
            )
        )
        if requested_units is None:
            target_units = measure.units
        elif isinstance(requested_units, pint.Unit):
            target_units = measure.units._REGISTRY.parse_units(str(requested_units))
        elif isinstance(requested_units, str):
            target_units = measure.units._REGISTRY.parse_units(requested_units)
        else:
            raise TypeError("measure target units must be Pint Units, strings, or None")
        if target_units.dimensionality != measure.units.dimensionality:
            raise pint.DimensionalityError(target_units, measure.units)
        column_name = f"measurement.{measure.code}"
        projections.append(
            (
                measure,
                target_units,
                column_name,
            )
        )
    return tuple(projections)


def _entity_value(entity: Entity, field_name: str, *, view: View) -> object:
    if field_name == "entity_id":
        return entity.id
    if field_name == "code":
        return entity.code
    if field_name == "name":
        return entity.name
    if field_name == "entity_kind":
        return "assembly" if isinstance(entity, Assembly) else "entity"
    if field_name == "classification_code":
        return entity.classification.code if entity.classification else None
    if field_name == "classification_name":
        return entity.classification.name if entity.classification else None
    if field_name == "taxonomy_code":
        if entity.classification is None:
            return None
        return view.graph.definitions.taxonomy_for(entity.classification).code
    raise TableError(f"unknown entity field {field_name!r}")
