"""Walkthrough presentation using Rangekeeper's existing plotting adapters.

These helpers write local HTML and return notebook iframes. Model selection,
quantities, financial assumptions and calculations belong in the notebook.
The labels and use colours below follow the continuing mixed-use example.
"""

from pathlib import Path
import json
import re

from IPython.display import IFrame

from rangekeeper.adapters.plotting import plot_flows, plot_partition
from rangekeeper.adapters.visualization import graph_html
from rangekeeper.model.characteristics import value
from rangekeeper.model.content import decode


from .theme import CONFIG, FONT, MODES, USE_COLORS, apply_theme

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
        path = Path("design-output") / f"{slug}.html"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _content(entity, key):
    recorded = value(entity.characteristics, key)
    return None if recorded is None else decode(recorded.content)


def show_plot(figure, *, path=None):
    """Style and export a Plotly Figure; the local iframe follows the host theme.

    The supplied Figure stays editable and unchanged. One local Plotly bundle
    is shared by figures in the same output directory; no CDN is required.
    """
    import plotly.graph_objects as go

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
    return IFrame(
        src=path.as_posix(), width="100%", height=(figure.layout.height or 440) + 20
    )


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
    return IFrame(src=path.as_posix(), width="100%", height=780)


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
        own_use = _content(entity, "use")
        uses[uid] = own_use or uses.get(hierarchy.parent(uid))
        colors.append(USE_COLORS.get(uses[uid], "#DDE3EB"))
        number = _content(entity, "number")
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
