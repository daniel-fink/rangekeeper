from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real
from os import PathLike
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go
from pyvis.network import Network

from ..table import Table
from ..view import View
from .errors import AdapterEncodingError

__all__ = ["graph_html", "icicle", "sunburst", "treemap"]


def graph_html(
    view: View,
    path: str | PathLike[str],
    *,
    height: str = "750px",
    width: str = "100%",
    options: Mapping[str, object] | None = None,
) -> Path:
    """Write an interactive PyVis rendering of a View and return its path."""
    if not isinstance(view, View):
        raise TypeError("view must be a View")
    for value, name in ((height, "height"), (width, "width")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if options is not None and not isinstance(options, Mapping):
        raise TypeError("options must be a mapping or None")

    network = Network(
        height=height,
        width=width,
        directed=True,
        notebook=False,
        cdn_resources="in_line",
    )
    for entity in view.entities:
        classification = entity.classification
        taxonomy_code = None
        if classification is not None:
            taxonomy_code = view.graph.definitions.taxonomy_for(classification).code
        network.add_node(
            str(entity.id),
            label=entity.name or entity.code or str(entity.id),
            title=(
                str(entity.id)
                if classification is None
                else f"{entity.id}<br>{taxonomy_code}:{classification.code}"
            ),
            group=(
                None
                if classification is None
                else f"{taxonomy_code}:{classification.code}"
            ),
        )
    for relationship in view.relationships:
        network.add_edge(
            str(relationship.source_id),
            str(relationship.target_id),
            label=relationship.classification.code,
            title=relationship.classification.name,
        )
    if options is not None:
        try:
            network.set_options(json.dumps(dict(options), allow_nan=False))
        except (TypeError, ValueError) as error:
            raise AdapterEncodingError(f"invalid PyVis options: {error}") from error

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    network.write_html(str(target), open_browser=False, notebook=False)
    return target


def sunburst(
    table: Table,
    *,
    label_column: str = "name",
    value_column: str | None = None,
) -> go.Sunburst:
    """Create a Plotly Sunburst trace from an arborescence Table."""
    return _tree_trace(
        go.Sunburst,
        table,
        label_column=label_column,
        value_column=value_column,
    )


def treemap(
    table: Table,
    *,
    label_column: str = "name",
    value_column: str | None = None,
) -> go.Treemap:
    """Create a Plotly Treemap trace from an arborescence Table."""
    return _tree_trace(
        go.Treemap,
        table,
        label_column=label_column,
        value_column=value_column,
    )


def icicle(
    table: Table,
    *,
    label_column: str = "name",
    value_column: str | None = None,
) -> go.Icicle:
    """Create a Plotly Icicle trace from an arborescence Table."""
    return _tree_trace(
        go.Icicle,
        table,
        label_column=label_column,
        value_column=value_column,
    )


@dataclass(frozen=True, slots=True)
class _TreeProjection:
    ids: tuple[str, ...]
    labels: tuple[str, ...]
    parents: tuple[str, ...]
    values: tuple[float, ...] | None


def _tree_trace(
    trace_type: type[go.Sunburst] | type[go.Treemap] | type[go.Icicle],
    table: Table,
    *,
    label_column: str,
    value_column: str | None,
) -> go.Sunburst | go.Treemap | go.Icicle:
    projection = _tree_projection(
        table,
        label_column=label_column,
        value_column=value_column,
    )
    arguments: dict[str, object] = {
        "ids": projection.ids,
        "labels": projection.labels,
        "parents": projection.parents,
    }
    if projection.values is not None:
        arguments.update(values=projection.values, branchvalues="total")
    return trace_type(**arguments)


def _tree_projection(
    table: Table,
    *,
    label_column: str,
    value_column: str | None,
) -> _TreeProjection:
    """Validate hierarchy semantics before handing values to Plotly."""

    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    if not isinstance(label_column, str) or not label_column.strip():
        raise ValueError("label_column must be a non-empty column name")
    if value_column is not None and (
        not isinstance(value_column, str) or not value_column.strip()
    ):
        raise ValueError("value_column must be a non-empty column name or None")
    required = {"entity_id", "parent_id", label_column}
    if value_column is not None:
        required.add(value_column)
    missing = required.difference(table.columns)
    if missing:
        raise AdapterEncodingError(
            f"arborescence Table is missing columns: {sorted(missing)}"
        )

    ids = tuple(str(row["entity_id"]) for row in table.rows)
    if len(ids) != len(set(ids)):
        raise AdapterEncodingError("entity_id values must be unique")
    id_set = set(ids)
    raw_parents = tuple(
        None if row["parent_id"] is None else str(row["parent_id"])
        for row in table.rows
    )
    if not all(
        parent is None or isinstance(parent, str) and parent in id_set
        for parent in raw_parents
    ):
        raise AdapterEncodingError("parent_id values must be None or reference a row")

    graph = nx.DiGraph()
    graph.add_nodes_from(ids)
    graph.add_edges_from(
        (parent, entity_id)
        for entity_id, parent in zip(ids, raw_parents)
        if parent is not None
    )
    if not graph or not nx.is_arborescence(graph):
        raise AdapterEncodingError("Table rows must form one arborescence")

    labels = []
    for entity_id, row in zip(ids, table.rows):
        label = row[label_column]
        if label is None or isinstance(label, str) and not label.strip():
            labels.append(entity_id)
        elif isinstance(label, str):
            labels.append(label)
        else:
            raise AdapterEncodingError(
                f"visualization label column {label_column!r} must contain "
                "strings or missing values"
            )
    values = None
    if value_column is not None:
        selected_values = tuple(row[value_column] for row in table.rows)
        if not all(
            isinstance(item, Real)
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            and item >= 0
            for item in selected_values
        ):
            raise AdapterEncodingError(
                f"visualization value column {value_column!r} must contain finite, "
                "non-negative numbers"
            )
        values = tuple(float(item) for item in selected_values)
        values_by_id = dict(zip(ids, values))
        for parent_id, parent_value in values_by_id.items():
            child_total = math.fsum(
                child_value
                for child_value, parent in zip(values, raw_parents)
                if parent == parent_id
            )
            if child_total > parent_value and not math.isclose(
                child_total,
                parent_value,
                rel_tol=1e-9,
                abs_tol=1e-12,
            ):
                raise AdapterEncodingError(
                    f"visualization value column {value_column!r} has parent "
                    f"{parent_id!r} total {parent_value} below child total "
                    f"{child_total}"
                )
    return _TreeProjection(
        ids=ids,
        labels=tuple(labels),
        parents=tuple("" if parent is None else parent for parent in raw_parents),
        values=values,
    )
