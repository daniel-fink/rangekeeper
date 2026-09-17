from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

import networkx as nx
import pint

from ..measure import Measure
from .assembly import Assembly
from .entity import Entity
from .view import View

__all__ = ["Row", "Table", "TableError"]


_ENTITY_FIELDS = frozenset({
    "entity_id",
    "code",
    "name",
    "entity_kind",
    "classification_code",
    "classification_name",
    "taxonomy_code",
})
_DEFAULT_FIELDS = (
    "entity_id",
    "name",
    "entity_kind",
    "classification_code",
)


class TableError(ValueError):
    """Raised when Table data or projection arguments are invalid."""


@dataclass(frozen=True, slots=True)
class Row:
    """Cell values bundled with optional identity; values are shallowly frozen."""

    values: Mapping[str, object]
    id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.values, Mapping):
            raise TypeError("Row values must be a mapping")
        _validate_names(self.values, "Row columns")
        if self.id is not None and not isinstance(self.id, UUID):
            raise TypeError("Row id must be a UUID or None")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True, init=False)
class Table:
    """Ordered Rows with optional identity and unconstrained cell values.

    Construction accepts plain mappings as unidentified rows. Cell access is
    through row.values; identity is metadata and never an implicit column.
    """

    columns: tuple[str, ...]
    rows: tuple[Row, ...]

    def __init__(
        self,
        columns: Iterable[str],
        rows: Iterable[Row | Mapping[str, object]],
    ) -> None:
        columns = _validate_names(columns, "columns")
        normalized_rows = []
        identities = set()
        for item in rows:
            row = item if isinstance(item, Row) else Row(values=item)
            missing = tuple(column for column in columns if column not in row.values)
            extra = tuple(column for column in row.values if column not in columns)
            if missing or extra:
                raise TableError(
                    "row columns do not match Table columns: "
                    f"missing={list(missing)!r}, extra={list(extra)!r}"
                )
            if row.id is not None:
                if row.id in identities:
                    raise TableError("Row IDs must be unique")
                identities.add(row.id)
            normalized_rows.append(
                Row(
                    values={column: row.values[column] for column in columns}, id=row.id
                )
            )
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "rows", tuple(normalized_rows))

    def row(self, row_id: UUID) -> Row:
        """Return an identified Row; unidentified rows do not match any key."""
        if not isinstance(row_id, UUID):
            raise TypeError("row_id must be UUID")
        for row in self.rows:
            if row.id == row_id:
                return row
        raise KeyError(row_id)

    def column(self, name: str) -> tuple[object, ...]:
        """Return one column in row order."""

        if name not in self.columns:
            raise KeyError(name)
        return tuple(row.values[name] for row in self.rows)

    @classmethod
    def from_view(
        cls,
        view: View,
        *,
        fields: Iterable[str] = _DEFAULT_FIELDS,
        labels: Iterable[str] = (),
        measures: Mapping[Measure | str, pint.Unit | str | None] | None = None,
        features: Iterable[str] = (),
    ) -> Table:
        """Project fields and characteristics; measure values select output units."""

        if not isinstance(view, View):
            raise TypeError("view must be a View")
        fields = _validate_names(fields, "fields")
        unknown_fields = set(fields).difference(_ENTITY_FIELDS)
        if unknown_fields:
            raise TableError(f"unknown fields: {sorted(unknown_fields)}")
        labels = _validate_names(labels, "labels")
        features = _validate_names(features, "features")
        measurement_projections = _measurement_projections(view, measures)

        columns = (
            *fields,
            *(f"label.{key}" for key in labels),
            *(column_name for _, _, column_name in measurement_projections),
            *(f"feature.{name}" for name in features),
        )
        if len(columns) != len(set(columns)):
            raise TableError("selected Table columns collide")

        rows = []
        for entity in view.entities:
            row = {
                field_name: _entity_value(entity, field_name, view=view)
                for field_name in fields
            }
            for key in labels:
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
            for name in features:
                feature = entity.features.get(name)
                row[f"feature.{name}"] = None if feature is None else feature.value
            rows.append(Row(values=row, id=entity.id))
        return cls(columns=columns, rows=rows)

    @classmethod
    def from_arborescence(
        cls,
        view: View,
        *,
        fields: Iterable[str] = _DEFAULT_FIELDS,
        labels: Iterable[str] = (),
        measures: Mapping[Measure | str, pint.Unit | str | None] | None = None,
        features: Iterable[str] = (),
    ) -> Table:
        """Project a parent-to-child arborescence with explicit parent IDs."""
        if not isinstance(view, View):
            raise TypeError("view must be a View")
        if not view.is_arborescence:
            raise TableError("view must be a non-empty parent-to-child arborescence")
        projected = cls.from_view(
            view,
            fields=fields,
            labels=labels,
            measures=measures,
            features=features,
        )
        if "entity_id" not in projected.columns:
            raise TableError("arborescence Tables require the 'entity_id' field")

        parent_by_entity = {
            relationship.target_id: relationship.source_id
            for relationship in view.relationships
        }
        root_id = view.roots[0].id
        entity_order = tuple(nx.dfs_preorder_nodes(view._topology(), source=root_id))
        projected_by_entity = {row.id: row for row in projected.rows}
        entity_id_index = projected.columns.index("entity_id")
        columns = (
            *projected.columns[: entity_id_index + 1],
            "parent_id",
            *projected.columns[entity_id_index + 1 :],
        )
        rows = []
        for entity_id in entity_order:
            row = dict(projected_by_entity[entity_id].values)
            row["parent_id"] = parent_by_entity.get(entity_id)
            rows.append(
                Row(values={column: row[column] for column in columns}, id=entity_id)
            )
        return cls(columns=columns, rows=rows)


def _validate_names(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field} must be an iterable of strings, not a string")
    materialized = tuple(values)
    if not all(isinstance(value, str) and value.strip() for value in materialized):
        raise TableError(f"{field} must contain only non-empty strings")
    if len(materialized) != len(set(materialized)):
        raise TableError(f"{field} must not contain duplicates")
    return materialized


def _measurement_projections(
    view: View,
    measures: Mapping[Measure | str, pint.Unit | str | None] | None,
) -> tuple[tuple[Measure, pint.Unit, str], ...]:
    """Resolve measures once and normalize requested units before row projection."""

    if measures is None:
        return ()
    if not isinstance(measures, Mapping):
        raise TypeError("measures must be a mapping or None")
    projections = []
    for measure_reference, requested_units in measures.items():
        measure = view.graph.definitions._resolve_measure(measure_reference)
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
        projections.append((
            measure,
            target_units,
            column_name,
        ))
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
