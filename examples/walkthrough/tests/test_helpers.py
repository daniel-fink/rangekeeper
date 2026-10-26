"""The walkthrough helpers write local HTML and return notebook iframes."""

from datetime import date
from urllib.request import urlopen

import plotly.graph_objects as go
import pytest
from helpers import plot, theme
from IPython.display import IFrame

from rangekeeper.model.flux import Flow


def read(frame):
    with urlopen(frame.src) as response:
        return response.read().decode()


def test_apply_theme_keeps_values_and_adds_redundant_encoding():
    figure = go.Figure(go.Scatter(x=[1, 2], y=[3, 4], name="Rent"))
    styled = theme.apply_theme(figure, mode="dark")
    assert styled.data[0].y == (3, 4)
    assert styled.data[0].line.dash == "solid"
    assert (
        styled.layout.template.layout.paper_bgcolor == theme.MODES["dark"]["background"]
    )


def test_show_plot_exports_a_themed_copy_with_a_local_bundle(workdir):
    figure = go.Figure(go.Bar(x=["A"], y=[1]), layout={"title": "Area by use"})
    before = figure.to_plotly_json()
    frame = plot.show_plot(figure)
    assert isinstance(frame, IFrame)
    assert frame.src.startswith("http://127.0.0.1:")
    assert figure.to_plotly_json() == before
    page = workdir / "output" / "area-by-use.html"
    assert (workdir / "output" / "plotly.min.js").is_file()
    assert read(frame) == page.read_text()
    assert "__RK_MODES__" not in page.read_text()


def test_show_plot_needs_a_title_or_a_path(workdir):
    with pytest.raises(ValueError, match="title or an explicit output path"):
        plot.show_plot(go.Figure())


def test_show_flows_labels_year_end_dates_by_year(workdir):
    dates = [date(year, 12, 31) for year in (2027, 2028, 2029)]
    flow = Flow.from_events(dates, [1.0, 2.0, 3.0], units="AUD")
    frame = plot.show_flows(flows={"Rent": flow}, title="Rent", path="rent.html")
    assert (workdir / "rent.html").is_file()
    assert "2027" in read(frame)


def test_show_timeline_draws_each_phase(workdir):
    phases = [
        {"name": "Building A", "start": "2028-01-01", "open": "2030-01-01"},
        {"name": "Building B", "start": "2030-01-01", "open": "2032-01-01"},
    ]
    plot.show_timeline(phases=phases, path="timeline.html")
    page = (workdir / "timeline.html").read_text()
    assert "Building A" in page and "Building B" in page


def test_show_sunburst_labels_entities_and_keeps_uuid_identities(workdir, tree):
    hierarchy, root, child = tree
    frame = plot.show_sunburst(
        hierarchy=hierarchy,
        amounts={child.id: 5.0},
        title="Area",
        units="m²",
        path="area.html",
    )
    page = read(frame)
    assert str(child.id) in page and "Building A" in page


def test_show_graph_writes_the_view(workdir, tree):
    hierarchy, root, _ = tree
    plot.show_graph(view=hierarchy.view, path="graph.html", hierarchical=True)
    assert "buildingA" in (workdir / "graph.html").read_text()


def test_show_geometry_writes_a_verified_viewer_for_the_data_package(workdir):
    frame = plot.show_geometry("floors", height=400)
    assert frame.src.endswith("walkthrough/output/geometry/viewer.html?view=floors")
    assert "Speckle" in read(frame)
    assert (plot.LESSONS / "output" / "geometry" / "geometry.json").is_file()
    with pytest.raises(ValueError, match="Unknown geometry view"):
        plot.show_geometry("roof")
