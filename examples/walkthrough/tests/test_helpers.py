"""The walkthrough helpers write local HTML and return notebook iframes."""

from datetime import date
from urllib.request import urlopen

import plotly.graph_objects as go
import pytest
from helpers import data_path, load_base_plan, load_paths, load_property, plot, theme
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


YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def market_paths(*names):
    """Return two generated market paths with these series."""
    dynamics = rk.market.Dynamics(trend="2 % pa", volatility="5 % pa")
    return rk.market.generate(
        dynamics=dict.fromkeys(names, dynamics), periods=YEARS, seed=1, count=2
    )


def test_data_path_gives_a_file_of_the_data_package():
    assert data_path(name="base_plan.json").is_file()
    with pytest.raises(ValueError, match="no file 'missing.json'"):
        data_path(name="missing.json")


def test_plot_flows_draws_labelled_flows_and_needs_one_source(workdir):
    flow = Flow.from_events(
        dates=[date(2027, 12, 31), date(2028, 12, 31)],
        magnitudes=[1.0, 2.0],
        units="AUD",
    )
    frame = plot.plot_flows(flows={"Hotel": flow}, path="labelled.html")
    assert isinstance(frame, IFrame)
    assert "Hotel" in (workdir / "labelled.html").read_text()
    both = {"flows": {"Hotel": flow}, "outcome": object(), "keys": ["works"]}
    for arguments in ({}, {"keys": ["works"]}, both):
        with pytest.raises(ValueError, match="outcome and keys, or flows"):
            plot.plot_flows(**arguments)


def test_plot_paths_draws_each_series_of_each_path_in_its_own_file(workdir):
    one = market_paths("rent_index")
    frame = plot.plot_paths(paths=one)
    assert isinstance(frame, IFrame)
    page = (workdir / "output" / f"paths-{one.id}.html").read_text()
    assert all(key in page for key in one.keys)
    two = market_paths("market_index", "hotel_factor")
    plot.plot_paths(paths=two)
    page = (workdir / "output" / f"paths-{two.id}.html").read_text()
    assert f"{two.keys[0]}: hotel_factor" in page


def test_plot_paths_draws_the_series_that_it_names(workdir):
    both = market_paths("market_index", "hotel_factor")
    plot.plot_paths(paths=both, names=["hotel_factor"], path="named.html")
    page = (workdir / "named.html").read_text()
    assert "hotel_factor" in page and "market_index" not in page
    assert f"{both.keys[0]}: " not in page


def test_load_paths_keeps_the_first_paths_of_a_smaller_count(monkeypatch):
    monkeypatch.delenv("RK_PATH_COUNT", raising=False)
    stored = load_paths(name="05_histories.paths.json")
    assert stored == rk.io.load(path=data_path(name="05_histories.paths.json"))
    monkeypatch.setenv("RK_PATH_COUNT", "9")
    assert load_paths(name="05_histories.paths.json") == stored
    monkeypatch.setenv("RK_PATH_COUNT", "2")
    fewer = load_paths(name="05_histories.paths.json")
    assert fewer.keys == stored.keys[:2]
    assert fewer[fewer.keys[1]]["rent_index"] == stored[fewer.keys[1]]["rent_index"]


def strategy_on_paths():
    """Return a strategy with two rules, and its Outcome on two paths."""
    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2033, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    draft = rk.Model(name="Decided").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="cost", units="AUD")
    project.date(key="start")
    project.date(key="sale")
    project.flow(key="rent_index", units="ratio", periods=years)
    project.flow(key="works", units="AUD", periods=years)
    project.equations("works = -rx.flow.event(amount=cost, on=start)")
    window = rk.specification.Window(earliest=date(2027, 1, 1), latest=date(2029, 1, 1))
    specification = (
        draft.commit()
        .specify(name="Decided")
        .fix(cost="10e6 AUD")
        .parameters(trigger=1.05)
        .fix(
            start=window.where(condition="rent_index >= trigger").first(
                otherwise=rk.duration.NEVER
            )
        )
        .fix(
            sale=window.where(condition="start == NEVER").first(
                otherwise=rk.duration.NEVER
            )
        )
    )
    rising = [1.0, 1.1, 1.1, 1.1, 1.1, 1.1]
    flat = [1.0] * 6
    paths = rk.market.Paths.from_flows(
        flows={
            key: {
                "rent_index": Flow.from_periods(
                    periods=years, magnitudes=index, units="ratio"
                )
            }
            for key, index in {"rising": rising, "flat": flat}.items()
        }
    )
    return specification, rk.execution.solve(
        specification=specification.across(paths=paths)
    )


def test_show_decisions_gives_each_rule_and_window():
    specification, _ = strategy_on_paths()
    table = plot.show_decisions(of=specification)
    assert table.column("key") == ("start", "sale")
    assert table.column("condition")[0] == "rent_index >= trigger"
    assert table.column("earliest")[0] == date(2027, 1, 1)
    assert table.column("otherwise")[0] is rk.duration.NEVER
    assert table.column("triggers") == ("trigger = 1.05", "")


def test_plot_decisions_marks_each_decided_date_on_its_path(workdir):
    _, outcome = strategy_on_paths()
    frame = plot.plot_decisions(outcome=outcome, key="rent_index", path="decided.html")
    assert isinstance(frame, IFrame)
    page = (workdir / "decided.html").read_text()
    assert "rising: start" in page
    assert "flat: start" not in page


def test_plot_target_curve_draws_a_curve_for_each_outcome(workdir):
    _, outcome = strategy_on_paths()
    plot.plot_target_curve(
        outcomes={"One": outcome, "Two": outcome}, key="cost", path="curves.html"
    )
    page = (workdir / "curves.html").read_text()
    assert '"name":"One"' in page and '"name":"Two"' in page


def test_plot_target_curve_draws_a_batch_and_checks_the_marker_units(workdir):
    draft = rk.Model(name="Drawn").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="rent", units="AUD")
    project.flow(key="rent_index", units="ratio", periods=YEARS)
    project.equations("income = rent_index * rent", "total_income = income.total()")
    specification = draft.commit().specify(name="Drawn").fix(rent="10 AUD")
    outcomes = rk.execution.solve(
        specification=specification.across(paths=market_paths("rent_index"))
    )
    frame = plot.plot_target_curve(
        outcomes=outcomes,
        key="total_income",
        markers={"Middle": rk.Quantity(text="20 AUD")},
        path="curve.html",
    )
    assert isinstance(frame, IFrame)
    page = (workdir / "curve.html").read_text()
    assert "Target curve of total_income, 2 market paths" in page
    assert "Middle" in page
    with pytest.raises(ValueError, match="must have the units"):
        plot.plot_target_curve(
            outcomes=outcomes,
            key="total_income",
            markers={"Ratio": rk.Quantity(text="1 ratio")},
            path="wrong.html",
        )


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
