"""Values that equations define without a declaration take their units from them (D44).

Declare every input and every result that you rely on; the draft works out the
kind and units of the other values that an equation defines, and ``commit()``
names a value that it cannot work out. A declaration is a check (#151).
"""

import importlib.util
from datetime import date
from uuid import UUID

import pytest

import rangekeeper as rk
from rangekeeper.model import ValueKind
from rangekeeper.quantity import default_units
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import EquationError, ValidationError

EXECUTION = all(importlib.util.find_spec(name) for name in ("pyomo", "highspy"))


def inputs(model: rk.Model | None = None) -> rk.model.ModelDraft:
    """Return a draft with a project and its declared inputs."""
    draft = (model or rk.Model(name="Inference")).edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="land_cost", units="AUD")
    project.value(key="area", units="sqm")
    project.value(key="rent", units="AUD per sqm pa")
    project.value(key="opex", units="AUD pa")
    project.value(key="cap_rate", units="ratio")
    project.date(key="start_date")
    return draft


def units_of(model: rk.Model, key: str) -> tuple[ValueKind, str | None]:
    value = model.value(key=key)
    measure = None if value.measure is None else model.record_by_id(value.measure)
    return value.kind, None if measure is None else measure.record.units


def test_values_that_equations_define_take_their_kind_and_units():
    draft = inputs()
    draft.entity(code="project").equations(
        "income = rent * area",
        "noi = income - opex",
        "value = noi * 1 year / cap_rate",
        "total_cost = land_cost + value",
        "yield_on_cost = noi * 1 year / total_cost",
        "open_date = start_date + 2 years",
    )
    model = draft.commit()
    assert units_of(model, "income") == (ValueKind.MEASUREMENT, "AUD pa")
    assert units_of(model, "noi") == (ValueKind.MEASUREMENT, "AUD pa")
    assert units_of(model, "value") == (ValueKind.MEASUREMENT, "AUD")
    assert units_of(model, "total_cost") == (ValueKind.MEASUREMENT, "AUD")
    assert units_of(model, "yield_on_cost") == (ValueKind.MEASUREMENT, "ratio")
    assert units_of(model, "open_date") == (ValueKind.DATE, None)
    # The inferred values follow the declared ones, in the order of their equations.
    keys = [
        value.key
        for value in model.entity(code="project").record.characteristics.values
    ]
    assert keys[6:] == [
        "income",
        "noi",
        "value",
        "total_cost",
        "yield_on_cost",
        "open_date",
    ]


def test_a_definition_can_come_later_in_the_same_call():
    # Lesson 03 cell 12: the first equation uses loan_interest, the last defines it.
    draft = inputs()
    draft.entity(code="project").equations(
        "need = land_cost + interest",
        "interest = land_cost * cap_rate",
    )
    model = draft.commit()
    assert units_of(model, "need") == (ValueKind.MEASUREMENT, "AUD")
    assert units_of(model, "interest") == (ValueKind.MEASUREMENT, "AUD")


def test_a_later_call_and_a_later_revision_use_a_defined_value():
    draft = inputs()
    project = draft.entity(code="project")
    project.equations("income = rent * area")
    project.add_formulation(name="Value").equations(
        "value = income * 1 year / cap_rate"
    )
    model = draft.commit()
    draft = model.edit()
    draft.entity(code="project").equations("price = value + land_cost")
    model = draft.commit()
    assert units_of(model, "price") == (ValueKind.MEASUREMENT, "AUD")


def test_a_name_that_no_equation_defines_is_checked_when_written():
    draft = inputs()
    project = draft.entity(code="project")
    with pytest.raises(EquationError) as error:
        project.equations("income = rent * area", "noi = incme - opex")
    assert error.value.code is Code.REFERENCE_MISSING
    assert error.value.text == "noi = incme - opex"
    assert (error.value.start, error.value.end) == (6, 11)
    assert error.value.suggestions == ("income",)
    assert "define it with an equation such as 'incme = ...'" in str(error.value)
    # The failed call reserved nothing: income is not defined yet.
    with pytest.raises(EquationError) as error:
        project.equations("noi = income - opex")
    assert error.value.text == "noi = income - opex"
    # A bound does not define a value.
    with pytest.raises(EquationError):
        project.equations("shortfall >= 0 AUD")


def test_a_declaration_keeps_the_value_that_equations_reference():
    draft = inputs()
    project = draft.entity(code="project")
    project.equations("total_cost = land_cost + land_cost")
    total = project.value(key="total_cost", units="AUD")
    model = draft.commit()
    value = model.value(key="total_cost")
    assert value.id == total.id
    (equation,) = model.system.formulations[0].expressions
    assert equation.operands[0].target.target == total.id


def test_a_declaration_is_a_check_of_its_equation():
    # D44: the declared result catches an equation that gives other units.
    draft = inputs()
    project = draft.entity(code="project")
    project.value(key="unlevered_npv", units="AUD")
    project.equations("income = rent * area", "unlevered_npv = income")
    with pytest.raises(ValidationError) as error:
        draft.commit()
    (issue,) = error.value.report.issues
    assert issue.code is Code.INCOMPATIBLE_UNITS
    assert issue.values["equation"] == "unlevered_npv = income"
    assert issue.values["units"] == ["AUD", "AUD pa"]


def test_commit_names_each_value_that_it_cannot_work_out():
    draft = inputs()
    project = draft.entity(code="project")
    project.equations("x = y", "y = x", "z = land_cost")
    with pytest.raises(ValidationError) as error:
        draft.commit()
    issues = error.value.report.issues
    assert [issue.values["key"] for issue in issues] == ["x", "y"]
    assert {issue.code for issue in issues} == {Code.UNITS}
    assert issues[0].values["where"] == "Entity project"
    assert "declare it with its units" in issues[0].message
    # The failed commit changed nothing: a declaration corrects it.
    project.value(key="x", units="AUD")
    model = draft.commit()
    assert units_of(model, "y") == (ValueKind.MEASUREMENT, "AUD")
    assert units_of(model, "z") == (ValueKind.MEASUREMENT, "AUD")


def test_other_entities_name_a_defined_value_by_code_and_key():
    draft = inputs()
    site = draft.add_entity(code="site")
    draft.entity(code="project").equations("income = rent * area")
    site.value(key="share", units="ratio")
    site.equations("site_income = share * project.income")
    model = draft.commit()
    site_income = model.value(key="site.site_income")
    assert site_income.kind is ValueKind.MEASUREMENT


def test_units_without_a_matching_measure_keep_their_canonical_text():
    draft = rk.Model(name="Canonical").edit()
    project = draft.add_entity(code="project")
    project.value(key="area", units="sqm")
    project.value(key="height", units="m")
    project.equations("volume = area * height")
    model = draft.commit()
    kind, units = units_of(model, "volume")
    assert kind is ValueKind.MEASUREMENT
    assert units == default_units.canonical(units="sqm * m")


def test_a_namespace_derives_the_identities_of_defined_values():
    namespace = UUID("0f8ad1f2-6a6e-4a3c-9d7e-35cfb3b8f4a1")

    def build() -> rk.Model:
        draft = inputs(rk.Model(name="Plan", namespace=namespace))
        draft.entity(code="project").equations("income = rent * area")
        return draft.commit()

    first, second = build(), build()
    assert first.value(key="income").id == second.value(key="income").id
    assert first.to_data()["definitions"] == second.to_data()["definitions"]


YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def works(model: rk.Model | None = None) -> rk.model.ModelDraft:
    """Return a draft with two Flows of works over YEARS, and a date."""
    draft = (model or rk.Model(name="Works")).edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="a_works", units="AUD", periods=YEARS)
    project.flow(key="b_works", units="AUD", periods=YEARS)
    project.value(key="share", units="ratio")
    project.date(key="sale_date")
    return draft


def test_a_definition_of_flows_gives_a_flow_over_their_periods():
    draft = works()
    draft.entity(code="project").equations(
        "works = a_works + b_works",
        "own_works = share * works",
        "until_sale = works.until(on=sale_date)",
        "running = works.cumulative()",
        "larger = rx.max(0 AUD, a_works - b_works)",
    )
    model = draft.commit()
    for key in ("works", "own_works", "until_sale", "running", "larger"):
        value = model.value(key=key)
        assert units_of(model, key) == (ValueKind.FLOW, "AUD"), key
        assert [item.period for item in value.flow.movements] == list(YEARS), key
        assert all(item.magnitude is None for item in value.flow.movements)


def test_a_scalar_method_of_a_flow_gives_a_value():
    # Lesson 03 cell 21: max() of a Flow is one amount, so rx.max of it too.
    draft = works()
    draft.entity(code="project").equations(
        "total = a_works.total()",
        "peak = (a_works - b_works).max()",
        "gap = rx.max(0 AUD, (a_works - b_works).max())",
    )
    model = draft.commit()
    for key in ("total", "peak", "gap"):
        assert units_of(model, key) == (ValueKind.MEASUREMENT, "AUD"), key
        assert model.value(key=key).flow is None


def test_a_value_beside_a_scalar_waits_for_the_shape_of_its_definition():
    # need is defined before later, a Flow: a scalar beside an unknown value
    # gives no shape, so need waits for later instead of being a scalar.
    draft = works()
    project = draft.entity(code="project")
    project.value(key="fee", units="AUD")
    project.equations(
        "need = later - fee",
        "later = a_works + b_works",
        "capped = rx.max(fee, need)",
    )
    model = draft.commit()
    for key in ("need", "later", "capped"):
        assert units_of(model, key) == (ValueKind.FLOW, "AUD"), key
        assert len(model.value(key=key).flow.movements) == len(YEARS), key


def test_a_flow_made_from_amounts_needs_declared_periods():
    # D44: a Flow made by a profile or an event is declared with its Periods.
    draft = works()
    project = draft.entity(code="project")
    project.value(key="cost", units="AUD")
    with pytest.raises((EquationError, rk.errors.ContractError)):
        project.equations("fees = rx.flow.event(amount=cost, on=sale_date)")


def test_a_namespace_derives_the_movements_of_an_inferred_flow():
    namespace = UUID("6b0f5d8e-6c43-4d5e-9a8b-1f2e3d4c5b6a")

    def build() -> rk.Model:
        draft = works(rk.Model(name="Works", namespace=namespace))
        draft.entity(code="project").equations("works = a_works + b_works")
        return draft.commit()

    first, second = build(), build()
    left = [item.id for item in first.value(key="works").flow.movements]
    right = [item.id for item in second.value(key="works").flow.movements]
    assert left == right


@pytest.mark.skipif(not EXECUTION, reason="requires the optional execution extra")
def test_a_solve_reads_values_in_their_inferred_units():
    draft = inputs()
    draft.entity(code="project").equations(
        "income = rent * area",
        "value = (income - opex) * 1 year / cap_rate",
    )
    model = draft.commit()
    outcome = rk.execution.solve(
        specification=model.specify(name="Value")
        .fix(area="1000 sqm", rent="500 AUD per sqm pa", opex="100000 AUD pa")
        .fix(cap_rate=0.05, land_cost="1 AUD")
    )
    assert outcome["income"] == rk.Quantity(text="500000 AUD pa")
    assert rk.quantity.isclose(
        actual=outcome["value"], expected=rk.Quantity(text="8e6 AUD")
    )


def test_a_call_gives_the_units_of_its_equation_function():
    # Lesson 03 cell 8: exit_value is the operating amount at the sale date over
    # the exit cap rate. The registry gives each call's units (#309).
    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    draft = rk.Model(name="Calls").edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="operating", units="AUD", periods=years)
    project.date(key="sale_date")
    project.value(key="exit_cap_rate", units="ratio")
    project.value(key="equity", units="AUD")
    project.equations(
        "exit_value = operating.at(on=sale_date) / exit_cap_rate",
        "total = operating.total()",
        "larger = rx.max(equity, total)",
    )
    model = draft.commit()
    for key in ("exit_value", "total", "larger"):
        assert units_of(model, key) == (ValueKind.MEASUREMENT, "AUD")
