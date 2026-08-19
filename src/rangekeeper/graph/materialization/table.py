from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

import pint

from ...measure import Measure
from ..assembly import Assembly
from ..classification import Classification
from ..entity import Entity
from ..model import Model
from ..view import View
from .errors import TableError


MultipleClassificationPolicy = Literal["tuple", "first", "error"]
GroupFunction = Callable[[tuple[object, ...]], object]

ENTITY_FIELDS = frozenset(
    {
        "entity_id",
        "name",
        "entity_type",
        "classification_code",
        "classification_name",
        "classification_scheme",
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


def entity_table(
    source: Model | View,
    *,
    fields: Iterable[str] = DEFAULT_ENTITY_FIELDS,
    occupancy_facets: Iterable[str] = (),
    measures: Mapping[Measure, pint.Unit | str | None] | None = None,
    features: Iterable[str] = (),
    parent_relationship: Classification | str | None = None,
    outgoing: bool = True,
    multiple_classifications: MultipleClassificationPolicy = "tuple",
) -> Table:
    view = _view(source)
    selected_fields = _validated_names(fields, "fields")
    unknown_fields = set(selected_fields).difference(ENTITY_FIELDS)
    if unknown_fields:
        raise TableError(f"unknown entity fields: {sorted(unknown_fields)}")
    facets = _validated_names(occupancy_facets, "occupancy_facets")
    feature_names = _validated_names(features, "features")
    if multiple_classifications not in ("tuple", "first", "error"):
        raise TableError(
            "multiple_classifications must be 'tuple', 'first', or 'error'"
        )
    if not isinstance(outgoing, bool):
        raise TypeError("outgoing must be a bool")
    if parent_relationship is not None and not isinstance(
        parent_relationship, (Classification, str)
    ):
        raise TypeError("parent_relationship must be a Classification, string, or None")
    measure_columns = _measure_columns(measures)

    columns = (
        *selected_fields,
        *(f"occupancy.{facet}" for facet in facets),
        *(column for _, _, column in measure_columns),
        *(f"feature.{name}" for name in feature_names),
        *(("parent_id", "children_ids") if parent_relationship is not None else ()),
    )
    if len(columns) != len(set(columns)):
        raise TableError("selected Table columns collide")

    rows = []
    for entity in view.entities():
        row = {field: _entity_field(entity, field) for field in selected_fields}
        for facet in facets:
            row[f"occupancy.{facet}"] = _occupancy_value(
                entity.occupancy.get(facet, ()),
                policy=multiple_classifications,
                entity=entity,
                facet=facet,
            )
        for measure, target_unit, column in measure_columns:
            quantity = entity.characteristics.get_measure(measure)
            row[column] = (
                None if quantity is None else quantity.to(target_unit).magnitude
            )
        for name in feature_names:
            row[f"feature.{name}"] = entity.features.get(name)
        if parent_relationship is not None:
            if outgoing:
                parents = view.predecessors(entity, parent_relationship)
                children = view.successors(entity, parent_relationship)
            else:
                parents = view.successors(entity, parent_relationship)
                children = view.predecessors(entity, parent_relationship)
            if len(parents) > 1:
                raise TableError(
                    f"entity {entity.entity_id!r} has multiple parents in the "
                    "selected relationship overlay"
                )
            row["parent_id"] = parents[0].entity_id if parents else None
            row["children_ids"] = tuple(child.entity_id for child in children)
        rows.append(row)
    return Table(columns=columns, rows=tuple(rows))


def _view(source: Model | View) -> View:
    if isinstance(source, Model):
        return source.view()
    if isinstance(source, View):
        return source
    raise TypeError("source must be a Model or View")


def _validated_names(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field} must be an iterable of strings, not a string")
    materialized = tuple(values)
    if not all(isinstance(value, str) and value.strip() for value in materialized):
        raise ValueError(f"{field} must contain only non-empty strings")
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"{field} must not contain duplicates")
    return materialized


def _measure_columns(
    measures: Mapping[Measure, pint.Unit | str | None] | None,
) -> tuple[tuple[Measure, pint.Unit, str], ...]:
    if measures is None:
        return ()
    if not isinstance(measures, Mapping):
        raise TypeError("measures must be a mapping or None")
    columns = []
    for measure, target in measures.items():
        if not isinstance(measure, Measure):
            raise TypeError("measure selections must use Measure keys")
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
                f"measure.{measure.code} [{target_unit}]",
            )
        )
    return tuple(columns)


def _entity_field(entity: Entity, field: str) -> object:
    if field == "entity_id":
        return entity.entity_id
    if field == "name":
        return entity.name
    if field == "entity_type":
        return "assembly" if isinstance(entity, Assembly) else "entity"
    if field == "classification_code":
        return entity.classification.code if entity.classification else None
    if field == "classification_name":
        return entity.classification.name if entity.classification else None
    if field == "classification_scheme":
        return entity.classification.scheme if entity.classification else None
    raise TableError(f"unknown entity field {field!r}")


def _occupancy_value(
    classifications: tuple[Classification, ...],
    *,
    policy: MultipleClassificationPolicy,
    entity: Entity,
    facet: str,
) -> object:
    values = tuple(classification.key for classification in classifications)
    if policy == "tuple":
        return values
    if len(values) > 1 and policy == "error":
        raise TableError(
            f"entity {entity.entity_id!r} has multiple classifications for "
            f"occupancy facet {facet!r}"
        )
    return values[0] if values else None
