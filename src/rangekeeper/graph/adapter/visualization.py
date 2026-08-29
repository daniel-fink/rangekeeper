from __future__ import annotations

import json
import math
from collections.abc import Mapping
from numbers import Real
from os import PathLike
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go
from pyvis.network import Network

from ..materialization import Table
from ..view import View
from .errors import AdapterEncodingError


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
            taxonomy_code = view.graph.definitions.taxonomy_of(classification).code
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
            network.set_options(json.dumps(dict(options)))
        except (TypeError, ValueError) as error:
            raise AdapterEncodingError(f"invalid PyVis options: {error}") from error

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    network.write_html(str(target), open_browser=False, notebook=False)
    return target


def sunburst(
    table: Table,
    *,
    label: str = "name",
    value: str | None = None,
) -> go.Sunburst:
    """Create a Plotly Sunburst trace from an arborescence Table."""
    projection = _tree_projection(table, label=label, value=value)
    arguments = {
        "ids": projection.ids,
        "labels": projection.labels,
        "parents": projection.parents,
    }
    if projection.values is not None:
        arguments.update(values=projection.values, branchvalues="total")
    return go.Sunburst(**arguments)


def treemap(
    table: Table,
    *,
    label: str = "name",
    value: str | None = None,
) -> go.Treemap:
    """Create a Plotly Treemap trace from an arborescence Table."""
    projection = _tree_projection(table, label=label, value=value)
    arguments = {
        "ids": projection.ids,
        "labels": projection.labels,
        "parents": projection.parents,
    }
    if projection.values is not None:
        arguments.update(values=projection.values, branchvalues="total")
    return go.Treemap(**arguments)


def icicle(
    table: Table,
    *,
    label: str = "name",
    value: str | None = None,
) -> go.Icicle:
    """Create a Plotly Icicle trace from an arborescence Table."""
    projection = _tree_projection(table, label=label, value=value)
    arguments = {
        "ids": projection.ids,
        "labels": projection.labels,
        "parents": projection.parents,
    }
    if projection.values is not None:
        arguments.update(values=projection.values, branchvalues="total")
    return go.Icicle(**arguments)


class _TreeProjection:
    def __init__(
        self,
        *,
        ids: tuple[str, ...],
        labels: tuple[str, ...],
        parents: tuple[str, ...],
        values: tuple[float, ...] | None,
    ) -> None:
        self.ids = ids
        self.labels = labels
        self.parents = parents
        self.values = values


def _tree_projection(
    table: Table,
    *,
    label: str,
    value: str | None,
) -> _TreeProjection:
    if not isinstance(table, Table):
        raise TypeError("table must be a Table")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label must be a non-empty column name")
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError("value must be a non-empty column name or None")
    required = {"entity_id", "parent_id", label}
    if value is not None:
        required.add(value)
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

    labels = tuple(
        row[label] if isinstance(row[label], str) and row[label] else entity_id
        for entity_id, row in zip(ids, table.rows)
    )
    values = None
    if value is not None:
        selected_values = tuple(row[value] for row in table.rows)
        if not all(
            isinstance(item, Real)
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            and item >= 0
            for item in selected_values
        ):
            raise AdapterEncodingError(
                f"visualization value column {value!r} must contain finite, "
                "non-negative numbers"
            )
        values = tuple(float(item) for item in selected_values)
    return _TreeProjection(
        ids=ids,
        labels=labels,
        parents=tuple("" if parent is None else parent for parent in raw_parents),
        values=values,
    )
