"""The walkthrough helpers write local HTML and return notebook iframes."""

from datetime import date
from urllib.request import urlopen

import plotly.graph_objects as go
import pytest
from helpers import load_base_plan, load_property, plot, theme
from IPython.display import IFrame

import rangekeeper as rk
from rangekeeper.flow import Flow


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
    flow = Flow.from_events(dates=dates, magnitudes=[1.0, 2.0, 3.0], units="AUD")
    frame = plot.show_flows(flows={"Rent": flow}, title="Rent", path="rent.html")
    assert (workdir / "rent.html").is_file()
    assert "2027" in read(frame)


def test_show_timeline_draws_each_package_of_the_plan(workdir):
    plan = load_base_plan()
    plot.show_timeline(of=plan, path="timeline.html")
    page = (workdir / "timeline.html").read_text()
    for name in ("Shared plinth", "Building A", "Building B"):
        assert name in page


def test_plot_cash_flows_and_plot_flows_draw_flows_of_an_outcome(workdir):
    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    draft = rk.Model(name="Drawn").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="cost", units="AUD")
    project.date(key="start")
    project.flow(key="works", units="AUD", periods=years)
    project.equations(
        "works = -rx.profile.uniform(total=cost, start=start, length=2 years)",
        "paid = -works.cumulative()",
    )
    specification = (
        draft.commit()
        .specify(name="Drawn")
        .fix(cost="10e6 AUD", start=date(2027, 1, 1))
    )
    outcome = rk.execution.solve(specification=specification)
    bars = plot.plot_cash_flows(outcome=outcome, key="works", path="bars.html")
    assert isinstance(bars, IFrame)
    assert "works by year" in (workdir / "bars.html").read_text()
    lines = plot.plot_flows(outcome=outcome, keys=["works", "paid"], path="lines.html")
    assert isinstance(lines, IFrame)
    page = (workdir / "lines.html").read_text()
    assert "works" in page and "paid" in page


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


def test_show_geometry_draws_only_the_data_package_with_geometry(workdir):
    with pytest.raises(ValueError, match="No geometry"):
        plot.show_geometry(name="another_property")


def test_load_property_gives_each_total_with_units_and_origin():
    data = load_property(year=2032)
    assert list(data)[:2] == ["works_cost", "operating_cost"]
    assert "parking_rent" not in data
    # The project brief: hotel GFA 11,716.69 m², at an efficiency of 0.8.
    assert rk.quantity.isclose(
        actual=data["hotel_area"],
        expected=rk.Quantity(text="9373.35 sqm"),
        tolerance="0.01 sqm",
    )
    assert data["hotel_rent"].units == "AUD per sqm pa"
    assert data["operating_cost"].magnitude > 0
    assert "finance allowance" in data.origin("works_cost")
    assert "hotel_vacancy" in data._repr_html_()
    with pytest.raises(ValueError, match="No totals for 2031"):
        load_property(year=2031)


def test_load_base_plan_gives_dates_quantities_and_origins():
    plan = load_base_plan()
    assert plan["start_date"] == date(2027, 1, 1)
    assert plan["b_start"] == date(2030, 1, 1)
    assert plan["a_cost"].units == "AUD"
    assert plan["a_income"].units == "AUD pa"
    assert plan["shared_opex"].units == "AUD pa"
    assert plan["loan_limit"] == rk.Quantity(text="65e6 AUD")
    assert plan.origin("equity") == "development.json equity"
    assert plan.areas["building_a"]["hotel"].units == "sqm"
    assert plan.rates["hotel"] == rk.Quantity(text="3000 AUD per sqm")
    assert [phase.name for phase in plan.phases] == [
        "Shared plinth",
        "Building A",
        "Building B",
    ]
    assert plan.phases[1].open == date(2030, 1, 1)
    assert "2027-01-01" in repr(plan)
    assert "<table>" in plan._repr_html_() and "a_cost" in plan._repr_html_()


def test_show_equations_joins_each_equation_to_its_values(workdir):
    model = rk.Model(name="Costs")
    draft = model.edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("land_cost", "works_cost", "total_cost"):
        project.value(key=key, units="AUD")
    project.equations("total_cost = land_cost + works_cost")
    model = draft.commit()
    page = read(plot.show_equations(of=model))
    assert "total_cost = land_cost + works_cost" in page
    specification = model.specify(name="Costs").fix(land_cost="1 AUD")
    page = read(plot.show_equations(of=specification))
    assert '"Fixed"' in page and '"Free"' in page
    with pytest.raises(TypeError, match="Model or a Specification"):
        plot.show_equations(of=None)
