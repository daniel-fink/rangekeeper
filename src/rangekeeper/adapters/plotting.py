"""Detached plotting adapters. Figures are returned; callers choose display or storage."""

from enum import Enum, unique


@unique
class PartitionKind(Enum):
    SUNBURST = "sunburst"
    TREEMAP = "treemap"


from collections.abc import Mapping, Sequence
from ..model.flow import Flow
from ..duration.period import PeriodTiming


def plot_flows(
    flows: Mapping[str, Flow], *, title: str = "", timing: PeriodTiming | None = None
):
    """Plot named resolved Flows by date, with explicit unit labels.

    Missing magnitudes fail. Period-only data requires an explicit date convention.
    Mixed units use distinct axes; no implicit conversion or time stripping occurs.
    """
    import matplotlib.pyplot as plt

    units = list(dict.fromkeys(flow.units for flow in flows.values()))
    if not units:
        raise ValueError("plot requires Flows")
    figure, axes = plt.subplots(
        len(units), 1, squeeze=False, figsize=(10, 3.5 * len(units))
    )
    for label, flow in flows.items():
        if any(m.magnitude is None for m in flow.movements):
            raise ValueError("plot requires resolved magnitudes")
        axis = axes[units.index(flow.units), 0]
        axis.plot(
            [m.resolve(timing=timing) for m in flow.movements],
            [m.magnitude for m in flow.movements],
            label=label,
        )
        axis.set_ylabel(flow.units)
        axis.set_xlabel("Date")
        axis.legend()
        axis.grid(alpha=0.2)
    figure.suptitle(title)
    figure.tight_layout()
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
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(9, 4))
    for name, values in samples.items():
        values = tuple(values)
        if not values or any(not math.isfinite(x) for x in values):
            raise ValueError("distribution requires nonempty finite samples")
        if cumulative:
            axis.step(
                sorted(values),
                [(i + 1) / len(values) for i in range(len(values))],
                where="post",
                label=name,
            )
        else:
            axis.hist(
                values, bins=min(30, max(3, len(values) // 3)), alpha=0.5, label=name
            )
    axis.set_xlabel(units)
    axis.set_ylabel("Cumulative probability" if cumulative else "Scenario count")
    axis.set_title(title)
    axis.legend()
    figure.tight_layout()
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
    import matplotlib.pyplot as plt

    if len(x) != len(y) or not x or any(not math.isfinite(v) for v in (*x, *y)):
        raise ValueError("paired plot requires matching finite samples")
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.scatter(x, y, color="#285f8f", marker="o")
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.set_title(title)
    axis.grid(alpha=0.2)
    figure.tight_layout()
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
