"""Walkthrough presentation helpers for charts, graphs and geometry.

These helpers write local HTML and return notebook iframes. Model selection,
quantities, financial assumptions and calculations belong in the notebook.
The labels and use colours below follow the continuing mixed-use example.
"""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import plotly.graph_objects as go
from IPython.display import IFrame

from rangekeeper.errors import MissingReferenceError
from rangekeeper.model.content import decode

from .chart import plot_flows, plot_partition
from .graph import graph_html
from .local import LocalDisplay
from .theme import CONFIG, FONT, MODES, PACKAGE_COLORS, USE_COLORS, apply_theme

LESSONS = Path(__file__).resolve().parents[1]
DATA = LESSONS.parent / "data" / "mixed_use_property"

_displays = {}


def _iframe(path, height, *, root=None):
    parts = urlsplit(str(path))
    target = Path(parts.path).resolve()
    if root is None:
        root = Path.cwd() if target.is_relative_to(Path.cwd()) else target.parent
    root = Path(root).resolve()
    if root not in _displays:
        _displays[root] = LocalDisplay(root)
    local_path = str(target) + ("?" + parts.query if parts.query else "")
    return IFrame(src=_displays[root].url(local_path), width="100%", height=height)


def show_geometry(view="context", height=650):
    """Write the local geometry viewer for the property and display one view."""
    from . import geometry

    if view not in {"context", "property", "floors", "utilities"}:
        raise ValueError("Unknown geometry view")
    page = geometry.write(DATA, LESSONS / "output" / "geometry")
    # The viewer reads the data package by a relative path, so serve both.
    return _iframe(f"{page}?view={view}", height, root=DATA.parents[1])


LABELS = {
    "buildingA": "Building A",
    "buildingB": "Building B",
    "plinth": "Shared plinth",
}


def _path(path, title):
    if path is None:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            raise ValueError("Supply a title or an explicit output path")
        path = Path("output") / f"{slug}.html"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _content(model, entity, key):
    try:
        recorded = model.value(owner=entity.id, key=key)
    except MissingReferenceError:
        return None
    return decode(recorded.content)


def show_plot(figure, *, path=None):
    """Style and export a Plotly Figure; the local iframe follows the host theme.

    The supplied Figure stays editable and unchanged. One local Plotly bundle
    is shared by figures in the same output directory; no CDN is required.
    """
    figure = apply_theme(go.Figure(figure))
    path = _path(path, figure.layout.title.text or "")
    script = (
        Path(__file__)
        .with_name("theme.js")
        .read_text()
        .replace("__RK_MODES__", json.dumps(MODES))
        .replace("__RK_FONT__", json.dumps(FONT))
    )
    figure.write_html(
        path, include_plotlyjs="directory", config=CONFIG, post_script=script
    )
    return _iframe(path, (figure.layout.height or 440) + 20)


def show_flows(*, flows, title="", timing=None, path=None):
    """Plot named Flows with explicit timing; presentation stays outside the lesson."""
    figure = plot_flows(flows=flows, title=title, timing=timing)
    dates = sorted({day for trace in figure.data for day in trace.x})
    if dates and len({(day.month, day.day) for day in dates}) == 1:
        # Put annual labels on the actual observation dates. Automatic January
        # ticks can make a 31 December receipt appear to belong to the next year.
        count = min(5, len(dates))
        ticks = [
            dates[round(i * (len(dates) - 1) / max(1, count - 1))] for i in range(count)
        ]
        figure.update_xaxes(
            tickmode="array",
            tickvals=ticks,
            ticktext=[str(day.year) for day in ticks],
            title_text=f"Year ({dates[0]:%d %b})",
        )
    return show_plot(figure, path=path)


def show_graph(*, view, path, hierarchical=False):
    """Display the selected View; layout never changes its relationships."""
    options = {
        "layout": {"randomSeed": 7},
        "interaction": {"hover": True, "navigationButtons": True},
        "nodes": {"shape": "dot", "size": 12, "font": {"size": 15}},
        "edges": {"font": {"size": 11}, "smooth": {"type": "dynamic"}},
        "physics": {"stabilization": {"iterations": 250}},
    }
    if hierarchical:
        options.update(
            layout={
                "hierarchical": {
                    "enabled": True,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "nodeSpacing": 180,
                    "levelSeparation": 160,
                }
            },
            physics={"enabled": False},
            edges={"smooth": False, "font": {"size": 11}},
        )
    path = graph_html(view, _path(path, ""), options=options)
    return _iframe(path, 780)


def show_sunburst(
    *, hierarchy, amounts, title, units, expense_magnitudes=False, path=None
):
    """Display explicit contributions using the library's additive sunburst.

    UUIDs remain the chart identities. Labels and inherited use colours are
    presentation only. Expense magnitudes affect the chart, not supplied flows.
    An optional path supports stable filenames; otherwise the title supplies it.
    """
    figure = plot_partition(
        hierarchy,
        amounts,
        units=units,
        title=title,
        expense_magnitudes=expense_magnitudes,
    )
    colors, labels, names = [], [], []
    uses = {}
    for uid in hierarchy.preorder():
        entity = hierarchy.view.entity(uid)
        own_use = _content(hierarchy.view.model, entity, "use")
        uses[uid] = own_use or uses.get(hierarchy.parent(uid))
        colors.append(USE_COLORS.get(uses[uid], "#DDE3EB"))
        number = _content(hierarchy.view.model, entity, "number")
        label = (
            f"Floor {number}"
            if number is not None
            else LABELS.get(entity.name, (own_use or entity.name or str(uid)).title())
        )
        labels.append(label)
        names.append(entity.name or str(uid))
    figure.update_traces(
        marker=dict(colors=colors),
        labels=labels,
        customdata=names,
        hovertemplate="%{customdata}<br>%{value:,.2f} " + units + "<extra></extra>",
    )
    figure.update_layout(height=570)
    return show_plot(figure, path=path)


def show_timeline(*, phases, path):
    """Display supplied construction/opening dates without selecting a plan."""
    figure = go.Figure()
    for phase in phases:
        start, end = (date.fromisoformat(phase[k]) for k in ("start", "open"))
        figure.add_trace(
            go.Scatter(
                x=[start, end],
                y=[phase["name"]] * 2,
                mode="lines+markers",
                name=phase["name"],
                line=dict(width=12, color=PACKAGE_COLORS.get(phase["name"], "#999999")),
                marker=dict(size=12, symbol=["square", "diamond"]),
                hovertemplate="%{y}<br>%{x|%d %b %Y}<extra></extra>",
            )
        )
    figure.update_layout(
        title="Base plan · construction to opening",
        height=370,
        showlegend=False,
        margin=dict(l=130),
    )
    figure.update_yaxes(autorange="reversed", title_text="Package")
    dates = sorted(
        {date.fromisoformat(p[key]) for p in phases for key in ("start", "open")}
    )
    figure.update_xaxes(
        type="date",
        title_text="Start (square) → opening (diamond)",
        tickmode="array",
        tickvals=dates,
        ticktext=[str(d.year) for d in dates],
    )
    return show_plot(figure, path=path)


def show_relations(*, formulation, names, specifications, path):
    """Inspect equation participation and Specification roles, without solve arrows.

    Edges come from the actual expression references. The dropdown changes only
    role styling; the Model's equations and variable identities stay fixed.
    """

    def references(expression):
        if expression.target is not None:
            yield expression.target.target
        for operand in expression.operands or ():
            yield from references(operand)

    variables = list(names)
    equations = list(formulation.expressions)
    variable_y = {uid: 1 - i / (len(variables) - 1) for i, uid in enumerate(variables)}
    equation_y = [1 - i / (len(equations) - 1) for i in range(len(equations))]
    edge_x, edge_y = [], []
    for expression, y in zip(equations, equation_y, strict=True):
        for uid in set(references(expression)):
            edge_x.extend([0, 1, None])
            edge_y.extend([variable_y[uid], y, None])
    figure = go.Figure(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(color="#999999", width=1),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    role_styles = []
    for title, specification in specifications.items():
        fixed = {item.target.target for item in specification.record.assignments}
        unknown = {item.target for item in specification.record.unknowns}
        if set(variables) != fixed | unknown or fixed & unknown:
            raise ValueError("Every displayed variable needs exactly one solve role")
        roles = ["Fixed" if uid in fixed else "Unknown" for uid in variables]
        role_styles.append(
            (
                title,
                roles,
                ["#4477AA" if r == "Fixed" else "#CC6677" for r in roles],
                ["square" if r == "Fixed" else "circle" for r in roles],
            )
        )
    title, roles, colors, symbols = role_styles[0]
    figure.add_trace(
        go.Scatter(
            x=[0] * len(variables),
            y=list(variable_y.values()),
            mode="markers+text",
            text=list(names.values()),
            textposition="middle left",
            cliponaxis=False,
            marker=dict(color=colors, symbol=symbols, size=13),
            customdata=roles,
            hovertemplate="%{text}<br>%{customdata}<extra></extra>",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[1] * len(equations),
            y=equation_y,
            mode="markers+text",
            text=[f"Eq. {i + 1}" for i in range(len(equations))],
            textposition="middle right",
            cliponaxis=False,
            marker=dict(symbol="diamond-open", size=13, color="#999999"),
            hoverinfo="text",
            showlegend=False,
        )
    )
    buttons = [
        dict(
            label=label,
            method="restyle",
            args=[
                {
                    "marker.color": [colors],
                    "marker.symbol": [symbols],
                    "customdata": [roles],
                },
                [1],
            ],
        )
        for label, roles, colors, symbols in role_styles
    ]
    figure.update_layout(
        title="Same relations · different knowns and unknowns",
        height=620,
        margin=dict(l=140, r=75, t=145, b=35),
        updatemenus=[dict(buttons=buttons, x=0, y=1.13, xanchor="left", yanchor="top")],
    )
    figure.update_xaxes(visible=False, range=[-0.05, 1.1], fixedrange=True)
    figure.update_yaxes(visible=False, range=[-0.04, 1.04], fixedrange=True)
    return show_plot(figure, path=path)
