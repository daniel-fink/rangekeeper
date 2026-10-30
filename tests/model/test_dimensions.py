"""Dimensional analysis of equations at Model and Specification validation (#151).

A Model whose equation has units that disagree fails to commit, and loading it
fails, with ``incompatible_units``: the issue names the equation, the part that
fails and both units (ADR-016). A quantity that fixes a value checks its units
too, and execution never reports units as an unsupported capability.
"""

import importlib.util
from uuid import UUID, uuid4

import pytest

import rangekeeper as rk
from rangekeeper.errors import Code, UnitError, ValidationError

EXECUTION = all(importlib.util.find_spec(name) for name in ("pyomo", "highspy"))


def project(model: rk.Model | None = None) -> rk.model.ModelDraft:
    """Return a draft with a project and values in several units."""
    draft = (model or rk.Model(name="Units")).edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("land_cost", "works_cost", "total_cost"):
        project.value(key=key, units="AUD")
    project.value(key="area", units="sqm")
    project.value(key="rent", units="AUD per sqm pa")
    project.value(key="income", units="AUD pa")
    project.value(key="leverage", units="ratio")
    project.value(key="height", units="m")
    project.value(key="height_ft", units="ft")
    project.date(key="start_date")
    project.date(key="open_date")
    return draft


def failure(*equations: str) -> ValidationError:
    """Return the error of a commit of the project with these equations."""
    draft = project()
    draft.entity(code="project").equations(*equations)
    with pytest.raises(ValidationError) as error:
        draft.commit()
    return error.value


def test_a_sum_of_values_in_other_units_does_not_commit():
    error = failure("total_cost = land_cost + area")
    assert error.code == Code.INCOMPATIBLE_UNITS
    (issue,) = error.report.issues
    assert issue.code == Code.INCOMPATIBLE_UNITS
    assert dict(issue.values) == {
        "equation": "total_cost = land_cost + area",
        "term": "land_cost + area",
        "units": ["AUD", "sqm"],
    }
    assert '"land_cost + area" has AUD and sqm' in issue.message
    assert issue.path.startswith("/system/formulations/0/expressions/0/")
    # The target is the Constraint of the equation.
    (constraint,) = issue.targets
    assert isinstance(constraint, UUID)


def test_a_declaration_checks_the_units_that_its_equation_gives():
    # D44: a declared value is a check. Rent times area is AUD pa, not AUD.
    error = failure("total_cost = rent * area")
    (issue,) = error.report.issues
    assert issue.values["equation"] == "total_cost = rent * area"
    assert issue.values["term"] == "total_cost = rent * area"
    assert issue.values["units"][0] == "AUD"
    assert rk.quantity.default_units.compatible(issue.values["units"][1], "AUD pa")


def test_bounds_and_each_failing_part_are_checked():
    error = failure(
        "land_cost >= 0 sqm",
        "total_cost - leverage = works_cost",
        "income = rent * area",
    )
    terms = [issue.values["term"] for issue in error.report.issues]
    assert terms == ["land_cost >= 0 sqm", "total_cost - leverage"]
    assert {issue.code for issue in error.report.issues} == {Code.INCOMPATIBLE_UNITS}


def test_compatible_units_of_another_scale_commit():
    draft = project()
    draft.entity(code="project").equations(
        "income = rent * area",
        "height = height_ft",
        "total_cost = land_cost + works_cost",
        "leverage = 65 %",
        "land_cost = leverage * total_cost",
        "open_date = start_date + 2 years",
        "open_date >= start_date",
    )
    model = draft.commit()
    assert len(model.system.formulations[0].constraints) == 7


def test_loading_a_model_checks_its_equations():
    draft = project()
    draft.entity(code="project").equations("total_cost = land_cost + works_cost")
    data = draft.commit().to_data()
    (expression,) = data["system"]["formulations"][0]["expressions"]
    area = next(
        value["id"]
        for value in data["system"]["entities"][0]["characteristics"]["values"]
        if value["key"] == "area"
    )
    expression["operands"][1]["operands"][1]["target"]["target"] = area
    with pytest.raises(ValidationError) as error:
        rk.Model.from_data(data=data)
    assert error.value.code == Code.INCOMPATIBLE_UNITS
    assert error.value.report.issues[0].values["units"] == ["AUD", "sqm"]


def test_a_quantity_that_fixes_a_value_checks_its_units():
    draft = project()
    draft.entity(code="project").equations("total_cost = land_cost + works_cost")
    model = draft.commit()
    with pytest.raises(UnitError) as error:
        model.specify(name="Wrong").fix(land_cost="5 sqm")
    assert error.value.code == Code.INCOMPATIBLE_UNITS
    assert "land_cost" in str(error.value)
    with pytest.raises(UnitError) as error:
        model.specify(name="Bare").fix(land_cost=5)
    assert error.value.code == Code.INCOMPATIBLE_UNITS
    land = model.value(key="land_cost")
    record = model.specify(name="Data").fix(land_cost="1 AUD").record.to_data()
    record["assignments"][0]["quantity"] = {"magnitude": 1, "units": "sqm"}
    record["assignments"][0]["target"]["target"] = str(land.id)
    report = rk.Specification.from_data(data=record).validate(
        resolver=model_store(model)
    )
    (issue,) = report.issues
    assert issue.code == Code.INCOMPATIBLE_UNITS
    assert dict(issue.values) == {
        "key": "land_cost",
        "units": "sqm",
        "expected": "AUD",
    }


def model_store(model: rk.Model) -> "rk.io.MemoryStore":
    store = rk.io.MemoryStore()
    store.put(model)
    return store


@pytest.mark.skipif(not EXECUTION, reason="requires the optional execution extra")
def test_execution_reports_units_that_disagree_as_invalid():
    # A Specification equation is not checked before the solve; its units fail
    # there as incompatible_units, never as an unsupported capability.
    draft = project()
    draft.entity(code="project").equations("total_cost = land_cost + works_cost")
    model = draft.commit()
    total = model.value(key="total_cost")
    bound = {
        "id": str(uuid4()),
        "kind": "binary",
        "operator": "less_than_or_equal",
        "operands": [
            {
                "id": str(uuid4()),
                "kind": "reference",
                "target": {"target": str(total.id)},
            },
            {
                "id": str(uuid4()),
                "kind": "quantity",
                "quantity": {"magnitude": 5, "units": "sqm"},
            },
        ],
    }
    data = (
        model.specify(name="Bound")
        .fix(land_cost="20e6 AUD", works_cost="30e6 AUD")
        .record.to_data()
    )
    data["formulations"] = [
        {
            "id": str(uuid4()),
            "expressions": [bound],
            "constraints": [{"id": str(uuid4()), "predicate": bound["id"]}],
        }
    ]
    specification = rk.Specification.from_data(data=data)
    outcome = rk.execution.solve(
        specification=specification, resolver=model_store(model)
    )
    assert outcome.status is rk.execution.Status.INVALID
    codes = {diagnostic.code for diagnostic in outcome.diagnostics}
    assert Code.INCOMPATIBLE_UNITS.value in codes
    assert Code.UNSUPPORTED_CAPABILITY.value not in codes
    with pytest.raises(UnitError) as error:
        outcome.raise_for_status()
    assert error.value.code == Code.INCOMPATIBLE_UNITS
