"""The equations of a Model revision: keys, the keys they use, text and ``where``.

``model.equations`` gives one ``Equation`` for each Constraint (G10, G47, D40).
A draft gives each equation the key of the first value of its text.
"""

import pickle
from datetime import date
from uuid import UUID

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.model import Equation, Equations

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def feasibility() -> rk.Model:
    """Return lesson 02's Model: one project, its values and six equations."""
    draft = rk.Model(name="Feasibility").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("land_cost", "works_cost", "total_cost", "mortgage"):
        project.value(key=key, units="AUD")
    project.value(key="leverage", units="ratio")
    project.value(key="mortgage_constant", units="% pa")
    for key in ("debt_service", "noi", "operating_cost", "effective_income"):
        project.value(key=key, units="AUD pa")
    project.value(key="reference_income", units="AUD pa")
    project.value(key="coverage", units="ratio")
    project.value(key="rent_factor", units="ratio")
    project.equations(
        "total_cost = land_cost + works_cost",
        "mortgage = leverage * total_cost",
        "debt_service = mortgage_constant * mortgage",
        "noi = coverage * debt_service",
        "effective_income = noi + operating_cost",
        "effective_income = rent_factor * reference_income",
    )
    return draft.commit()


def dated() -> rk.Model:
    """Return a Model with lesson 03's date equations in a "Dates" Formulation."""
    draft = rk.Model(name="Plan").edit()
    project = draft.add_entity(code="project", classification="project")
    project.date(key="start_date")
    project.date(key="b_start")
    project.value(key="land_cost", units="AUD")
    dates = project.add_formulation(name="Dates")
    dates.equations(
        "shared_start = start_date",
        "a_start = shared_start + 1 year",
        "b_start >= shared_start + 1 year",
    )
    project.equations("total = land_cost")
    return draft.commit()


def test_each_equation_has_the_key_of_its_first_value():
    equations = feasibility().equations
    assert isinstance(equations, Equations)
    assert [item.key for item in equations] == [
        "total_cost",
        "mortgage",
        "debt_service",
        "noi",
        "effective_income",
        "effective_income_2",
    ]


def test_a_key_is_the_code_of_the_constraint():
    model = feasibility()
    (root,) = model.system.formulations
    assert [item.code for item in root.constraints] == [
        item.key for item in model.equations
    ]


def test_an_equation_gives_its_text_and_the_keys_it_uses():
    (noi,) = feasibility().equations.where(key="noi")
    assert isinstance(noi, Equation)
    assert noi.text == "noi = coverage * debt_service"
    assert str(noi) == noi.text
    assert noi.keys == ("noi", "coverage", "debt_service")
    assert (noi.formulation, noi.entity) == (None, "project")
    assert repr(noi) == "<equation noi = coverage * debt_service>"
    assert isinstance(noi.id, UUID)


def test_the_text_of_an_equation_is_the_text_of_rx():
    """The 02 aside: Term.text and Equation.text are the same canonical text."""
    model = feasibility()
    project = model.edit().entity(code="project")
    noi = project.ref(key="noi")
    coverage = project.ref(key="coverage")
    debt_service = project.ref(key="debt_service")
    (equation,) = model.equations.where(key="noi")
    assert (noi == coverage * debt_service).text == equation.text


def test_where_matches_columns_with_text_or_a_list():
    model = dated()
    assert [item.key for item in model.equations.where(formulation="Dates")] == [
        "shared_start",
        "a_start",
        "b_start",
    ]
    assert [item.key for item in model.equations.where(keys="shared_start")] == [
        "shared_start",
        "a_start",
        "b_start",
    ]
    picked = model.equations.where(key=["total", "a_start"])
    assert [item.key for item in picked] == ["total", "a_start"]
    both = model.equations.where(keys="start_date", formulation="Dates")
    assert [item.key for item in both] == ["shared_start"]
    assert len(model.equations.where(entity="project")) == 4
    assert not model.equations.where(key="missing")


def test_where_takes_at_least_one_column_of_text():
    equations = dated().equations
    with pytest.raises(TypeError, match="at least one"):
        equations.where()
    with pytest.raises(TypeError, match="text"):
        equations.where(key=1)  # type: ignore[arg-type]


def test_the_default_formulation_comes_first_and_has_no_name():
    (total, *dates) = dated().equations
    assert (total.key, total.formulation) == ("total", None)
    assert {item.formulation for item in dates} == {"Dates"}


def test_equations_are_a_sequence_with_a_table():
    equations = dated().equations
    assert len(equations) == 4
    assert equations[0].key == "total"
    assert isinstance(equations[1:], Equations)
    assert list(equations[1:]) == list(equations)[1:]
    table = equations.table
    assert table.columns == ("key", "text", "formulation", "entity")
    assert table.column("text")[0] == "total = land_cost"
    assert table.rows[0].id == equations[0].id
    assert "<table>" in equations._repr_html_()
    assert repr(equations).splitlines()[1] == "  total = land_cost"
    assert repr(Equations()) == "Equations(0 equations)"
    assert Equations(list(equations)) == equations
    assert hash(Equations(list(equations))) == hash(equations)
    with pytest.raises(TypeError, match="Equation"):
        Equations(["total = land_cost"])  # type: ignore[list-item]


def test_a_value_of_another_entity_is_written_with_its_code():
    draft = rk.Model(name="Floors").edit()
    project = draft.add_entity(code="project", classification="project")
    floor = draft.add_entity(code="floor_1", classification="floor")
    floor.value(key="income", units="AUD pa")
    project.value(key="reference_income", units="AUD pa")
    project.equations("reference_income = floor_1.income")
    (equation,) = draft.commit().equations
    assert equation.text == "reference_income = floor_1.income"
    assert equation.keys == ("reference_income", "floor_1.income")


def test_an_equation_with_no_value_on_its_left_takes_the_first_of_its_text():
    draft = rk.Model(name="Bounds").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="noi", units="AUD pa")
    project.value(key="debt_service", units="AUD pa")
    project.equations(
        "0 AUD pa <= debt_service",
        rx.max(project.ref(key="noi"), "0 AUD pa") >= "0 AUD pa",
    )
    assert [item.key for item in draft.commit().equations] == ["debt_service", "noi"]


def test_a_model_from_records_names_its_equations_by_their_first_value():
    """A Constraint with no code takes the key of the first value of its text."""
    model = feasibility()
    data = model.to_data()
    for constraint in data["system"]["formulations"][0]["constraints"]:
        del constraint["code"]
    keys = [item.key for item in rk.Model.from_data(data=data).equations]
    assert keys[-2:] == ["effective_income", "effective_income"]


def test_an_empty_model_has_no_equations():
    assert len(rk.Model(name="Empty").equations) == 0


def test_a_namespace_derives_the_identity_of_each_equation_from_its_key():
    namespace = UUID("c7a1b9e0-3f0d-4a55-9e27-5d2f7f0b4c11")

    def build() -> rk.Model:
        draft = rk.Model(name="Plan", namespace=namespace).edit()
        project = draft.add_entity(code="project", classification="project")
        project.value(key="a", units="AUD")
        project.value(key="b", units="AUD")
        project.equations("a = b", "a >= 0 AUD")
        return draft.commit()

    first, second = build(), build()
    assert [item.id for item in first.equations] == [
        item.id for item in second.equations
    ]
    assert [item.key for item in first.equations] == ["a", "a_2"]


def test_a_flow_equation_lists_its_keys():
    draft = rk.Model(name="Works").edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="a_works", units="AUD", periods=YEARS)
    project.flow(key="b_works", units="AUD", periods=YEARS)
    project.equations("works = a_works + b_works")
    (works,) = draft.commit().equations
    assert works.keys == ("works", "a_works", "b_works")


def test_a_missing_reference_error_names_what_references_it():
    error = rk.errors.MissingReferenceError(
        "income", kind="Value", by="key", where="Entity project", referenced_by=["op"]
    )
    assert error.referenced_by == ("op",)
    assert str(error).endswith("; referenced by: op")
    again = pickle.loads(pickle.dumps(error))
    assert (again.requested, again.referenced_by) == ("income", ("op",))
