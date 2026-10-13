"""Shared Plotly style for the walkthroughs; no global Plotly defaults change."""

import plotly.graph_objects as go
import plotly.io as pio

FONT = (
    "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
)

# Object identity colours stay the same in every chart and both colour modes.
USE_COLORS = {
    "hotel": "#4477AA",
    "residential": "#228833",
    "retail": "#CCBB44",
    "parking": "#999999",
    "cores": "#AA3377",
    "plant": "#EE6677",
}
SERIES_COLORS = ["#4477AA", "#CC6677", "#228833", "#AA3377", "#CCBB44", "#999999"]
PACKAGE_COLORS = {
    "Shared plinth": "#999999",
    "Building A": "#4477AA",
    "Building B": "#AA3377",
}
MODES = {
    "light": {"background": "#FFFFFF", "text": "#292524", "grid": "#E7E5E4"},
    "dark": {"background": "#1C1917", "text": "#D6D3D1", "grid": "#44403C"},
}
CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def template(mode="light"):
    """Return a fresh built-in template with the walkthrough's shared style."""
    colors = MODES[mode]
    result = go.layout.Template(
        pio.templates["plotly_dark" if mode == "dark" else "plotly_white"]
    )
    axis = dict(
        gridcolor=colors["grid"],
        linecolor=colors["grid"],
        zerolinecolor=colors["grid"],
        automargin=True,
        tickangle=0,
        title=dict(standoff=12),
    )
    result.layout.update(
        font=dict(family=FONT, size=14, color=colors["text"]),
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["background"],
        colorway=SERIES_COLORS,
        title=dict(
            x=0,
            xanchor="left",
            y=1,
            yanchor="top",
            yref="container",
            pad=dict(t=28),
            font=dict(size=18),
            automargin=False,
        ),
        margin=dict(l=65, r=24, t=95, b=65),
        legend=dict(orientation="h", x=0, y=1.04, yanchor="bottom"),
        hoverlabel=dict(
            bgcolor=colors["background"],
            bordercolor=colors["grid"],
            font=dict(family=FONT, size=14, color=colors["text"]),
            namelength=-1,
        ),
        xaxis=axis,
        yaxis=axis,
    )
    return result


def apply_theme(figure, *, mode="light"):
    """Style a Figure in place without changing its values or trace identities."""
    figure.update_layout(template=template(mode))
    # A redundant dash/marker encoding keeps lines distinct without colour.
    dashes = ("solid", "dash", "dot", "dashdot")
    symbols = ("circle", "diamond", "square", "triangle-up")
    for index, trace in enumerate(figure.data):
        if trace.type == "scatter":
            if trace.line.dash is None:
                trace.line.dash = dashes[index % len(dashes)]
            if trace.marker.symbol is None:
                trace.marker.symbol = symbols[index % len(symbols)]
    return figure
