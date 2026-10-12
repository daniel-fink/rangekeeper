"""Detached Plotly adapters. Callers choose styling, display and storage."""

from enum import Enum, unique


@unique
class PartitionKind(Enum):
    SUNBURST = "sunburst"
    TREEMAP = "treemap"


from collections.abc import Mapping, Sequence
from rangekeeper.model.flux import Flow
from rangekeeper.model.duration.period import PeriodTiming


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
