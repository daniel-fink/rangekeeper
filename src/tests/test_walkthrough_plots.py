"""Presentation helpers preserve figures and keep meaning stable across themes."""

import json
from pathlib import Path
import re
from datetime import date

import plotly.graph_objects as go
import plotly.io as pio


def test_walkthrough_export_preserves_figure_and_packages_theme(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "examples/walkthrough")
    )
    from helpers.plot import show_plot
    from helpers.theme import apply_theme

    figure = go.Figure(
        go.Scatter(x=[1, 2], y=[-10, 20], name="Cash", line=dict(color="#AA3377"))
    )
    figure.update_layout(title="Cash", xaxis_title="Year", yaxis_title="AUD")
    source = figure.to_json()
    default = pio.templates.default
    for mode in ("light", "dark"):
        styled = apply_theme(go.Figure(figure), mode=mode)
        assert tuple(styled.data[0].y) == (-10, 20)
        assert styled.data[0].line.color == "#AA3377"
        assert styled.layout.xaxis.title.text == "Year"
    frame = show_plot(figure, path=tmp_path / "cash.html")
    assert frame.src == (tmp_path / "cash.html").as_posix()
    assert figure.to_json() == source
    assert pio.templates.default == default
    html = (tmp_path / "cash.html").read_text()
    start = re.search(r'Plotly\.newPlot\(\s*"[^"]+",\s*', html).end()
    data = json.JSONDecoder().raw_decode(html[start:])[0]
    assert data[0]["y"] == [-10, 20]
    assert data[0]["line"]["color"] == "#AA3377"
    assert "__RK_" not in html and "{plot_id}" not in html
    assert "MutationObserver" in html and "Plotly.relayout" in html
    assert 'src="plotly.min.js"' in html
    assert (tmp_path / "plotly.min.js").exists()


def test_annual_labels_use_receipt_year_and_retain_endpoints(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "examples/walkthrough")
    )
    from helpers import plot
    from rangekeeper.model.flux import Flow

    monkeypatch.setattr(plot, "show_plot", lambda figure, **kwargs: figure)
    dates = [date(year, 12, 31) for year in range(2001, 2012)]
    figure = plot.show_flows(
        flows={"Income": Flow.from_events(dates, range(11), units="AUD")}
    )
    assert figure.layout.xaxis.tickvals[0] == dates[0]
    assert figure.layout.xaxis.tickvals[-1] == dates[-1]
    assert figure.layout.xaxis.ticktext[0] == "2001"
    assert figure.layout.xaxis.ticktext[-1] == "2011"
    assert figure.layout.xaxis.title.text == "Year (31 Dec)"
    assert tuple(figure.data[0].x) == tuple(dates)
