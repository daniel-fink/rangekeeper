from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real
from os import PathLike
from pathlib import Path
from typing import cast

from rangekeeper.shared.optional import requires

with requires("visualisation"):
    import networkx as nx
    import plotly.graph_objects as go

from rangekeeper.model.definitions import classification as find_classification
from rangekeeper.model.system import View
from rangekeeper.shared.errors import EncodingError
from rangekeeper.shared.table import Table

__all__ = [
    "icicle",
    "sunburst",
    "treemap",
    "plot_flows",
    "plot_distribution",
    "plot_pairs",
    "plot_partition",
    "PartitionKind",
]


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
    trace_type: type[go.Sunburst | go.Treemap | go.Icicle],
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
        raise EncodingError(f"arborescence Table is missing columns: {sorted(missing)}")

    ids = tuple(str(row.values["entity_id"]) for row in table.rows)
    if len(ids) != len(set(ids)):
        raise EncodingError("entity_id values must be unique")
    id_set = set(ids)
    raw_parents = tuple(
        None if row.values["parent_id"] is None else str(row.values["parent_id"])
        for row in table.rows
    )
    if not all(
        parent is None or isinstance(parent, str) and parent in id_set
        for parent in raw_parents
    ):
        raise EncodingError("parent_id values must be None or reference a row")

    graph = nx.DiGraph()
    graph.add_nodes_from(ids)
    graph.add_edges_from(
        (parent, entity_id)
        for entity_id, parent in zip(ids, raw_parents)
        if parent is not None
    )
    if not graph or not nx.is_arborescence(graph):
        raise EncodingError("Table rows must form one arborescence")

    labels = []
    for entity_id, row in zip(ids, table.rows):
        label = row.values[label_column]
        if label is None or isinstance(label, str) and not label.strip():
            labels.append(entity_id)
        elif isinstance(label, str):
            labels.append(label)
        else:
            raise EncodingError(
                f"visualization label column {label_column!r} must contain "
                "strings or missing values"
            )
    values = None
    if value_column is not None:
        selected_values = tuple(row.values[value_column] for row in table.rows)
        if not all(
            isinstance(item, Real)
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            and float(item) >= 0
            for item in selected_values
        ):
            raise EncodingError(
                f"visualization value column {value_column!r} must contain finite, "
                "non-negative numbers"
            )
        values = tuple(float(cast(Real, item)) for item in selected_values)
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
                raise EncodingError(
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


"""Detached Plotly adapters. Callers choose styling, display and storage."""

from enum import Enum, unique


@unique
class PartitionKind(Enum):
    SUNBURST = "sunburst"
    TREEMAP = "treemap"


from collections.abc import Mapping, Sequence

from rangekeeper.model.duration.period import PeriodTiming
from rangekeeper.model.flux import Flow


def plot_flows(
    flows: Mapping[str, Flow], *, title: str = "", timing: PeriodTiming | None = None
):
    """Plot named resolved Flows by date, with explicit unit labels.

    Missing magnitudes fail. Period-only data requires an explicit date convention.
    Mixed units use separate panels; no implicit conversion or time stripping occurs.
    Returns a Plotly Figure without changing the session's default template.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    units = list(dict.fromkeys(flow.units for flow in flows.values()))
    if not units:
        raise ValueError("plot requires Flows")
    figure = make_subplots(rows=len(units), cols=1, shared_xaxes=True)
    for label, flow in flows.items():
        if any(m.magnitude is None for m in flow.movements):
            raise ValueError("plot requires resolved magnitudes")
        row = units.index(flow.units) + 1
        figure.add_trace(
            go.Scatter(
                x=[m.resolve(timing=timing) for m in flow.movements],
                y=[m.magnitude for m in flow.movements],
                name=label,
                mode="lines+markers",
                hovertemplate="%{x|%d %b %Y}<br>%{y:,.2f} "
                + flow.units
                + "<extra>%{fullData.name}</extra>",
            ),
            row=row,
            col=1,
        )
        figure.update_yaxes(title_text=flow.units, row=row, col=1)
    figure.update_xaxes(type="date", title_text="Date", row=len(units), col=1)
    figure.update_layout(title=title, height=280 * len(units) + 160)
    return figure


def plot_distribution(
    samples: Mapping[str, Sequence[float]],
    *,
    units: str,
    title: str = "",
    cumulative: bool = False,
):
    """Plot detached finite samples as histograms or empirical cumulative curves."""
    import math

    import plotly.graph_objects as go

    figure = go.Figure()
    for name, values in samples.items():
        values = tuple(values)
        if not values or any(not math.isfinite(x) for x in values):
            raise ValueError("distribution requires nonempty finite samples")
        if cumulative:
            figure.add_trace(
                go.Scatter(
                    x=sorted(values),
                    y=[(i + 1) / len(values) for i in range(len(values))],
                    name=name,
                    mode="lines",
                    line_shape="hv",
                )
            )
        else:
            figure.add_trace(
                go.Histogram(
                    x=values,
                    nbinsx=min(30, max(3, len(values) // 3)),
                    opacity=0.55,
                    name=name,
                    bingroup="samples",
                )
            )
    figure.update_layout(
        title=title,
        xaxis_title=units,
        yaxis_title="Cumulative probability" if cumulative else "Scenario count",
        barmode="overlay",
        height=440,
    )
    if cumulative:
        figure.update_yaxes(range=[0, 1], tickformat=".0%")
    return figure


def plot_pairs(
    x: Sequence[float],
    y: Sequence[float],
    *,
    x_label: str,
    y_label: str,
    title: str = "",
):
    """Plot paired scenario outcomes, retaining one point per shared realization."""
    import math

    import plotly.graph_objects as go

    if len(x) != len(y) or not x or any(not math.isfinite(v) for v in (*x, *y)):
        raise ValueError("paired plot requires matching finite samples")
    figure = go.Figure(go.Scatter(x=list(x), y=list(y), mode="markers"))
    figure.update_layout(
        title=title, xaxis_title=x_label, yaxis_title=y_label, height=440
    )
    return figure


def plot_partition(
    hierarchy,
    amounts,
    *,
    units: str,
    title: str,
    kind: PartitionKind = PartitionKind.SUNBURST,
    expense_magnitudes: bool = False,
):
    """Plot additive detached contributor amounts on a validated tree.

    Each supplied UUID contributes once. Ancestor values are calculated from
    children plus their own direct contribution. Missing contributors must be
    handled by the caller, not filled by this adapter. Signed negative expenses
    require the explicit expense_magnitudes projection; the Model is unchanged.
    Shared membership requires an occurrence design and is rejected by Hierarchy.
    """
    import math

    import plotly.graph_objects as go

    if not isinstance(kind, PartitionKind):
        raise TypeError("kind must be PartitionKind")
    ids = hierarchy.preorder()
    selected = set(ids)
    if not set(amounts) <= selected or any(
        not math.isfinite(x) for x in amounts.values()
    ):
        raise ValueError("amounts require selected UUIDs and finite numbers")
    if expense_magnitudes:
        if any(x > 0 for x in amounts.values()):
            raise ValueError("expense magnitude requires nonpositive expenses")
        direct = {uid: -x for uid, x in amounts.items()}
        title += " — expense magnitudes"
    else:
        if any(x < 0 for x in amounts.values()):
            raise ValueError("negative amounts require an explicit expense projection")
        direct = dict(amounts)
    totals = {uid: direct.get(uid, 0) for uid in ids}
    for uid in reversed(ids):
        parent = hierarchy.parent(uid)
        if parent is not None:
            totals[parent] += totals[uid]
    trace_type = go.Sunburst if kind is PartitionKind.SUNBURST else go.Treemap
    figure = go.Figure(
        trace_type(
            ids=[str(uid) for uid in ids],
            labels=[hierarchy.view.entity(uid).name or str(uid) for uid in ids],
            parents=[
                str(hierarchy.parent(uid)) if hierarchy.parent(uid) is not None else ""
                for uid in ids
            ],
            values=[totals[uid] for uid in ids],
            branchvalues="total",
            marker=dict(colors=["#285f8f"] * len(ids)),
            hovertemplate="%{label}<br>%{value:,.2f} " + units + "<extra></extra>",
        )
    )
    figure.update_layout(title=title, margin=dict(t=70, l=15, r=15, b=15), height=500)
    return figure
