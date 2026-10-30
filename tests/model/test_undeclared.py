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
from rangekeeper.model._dimensions import Kind
from rangekeeper.model._undeclared import Undeclared, definitions_in, known_values
from rangekeeper.model.expression.authoring import add, equal, reference
from rangekeeper.quantity import default_units
from rangekeeper.schema.records import Reference, Value
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
    keys = [value.key for value in model.entity(code="project").characteristics.values]
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


def test_a_definition_that_references_a_whole_flow_gives_a_flow():
    """Read the inference itself: Flow equations do not commit before #279.

    Model validation does not take arithmetic on whole Flows yet, so a draft
    with ``works = a_works + b_works`` cannot commit. The inference gives
    ``works`` the kind and units that its commit will use.
    """
    measure = rk.model.Measure(id=UUID(int=1), code="AUD", name="AUD", units="AUD")
    flows = [
        Value(
            id=UUID(int=index),
            key=key,
            kind=ValueKind.FLOW,
            measure=measure.id,
        )
        for index, key in ((2, "a_works"), (3, "b_works"))
    ]
    works = UUID(int=4)
    equation = equal(
        reference(Reference(target=works)),
        add(*(reference(Reference(target=flow.id)) for flow in flows)),
    )
    assert [target for target, _ in definitions_in(equation)] == [works]
    undeclared = Undeclared()
    undeclared.add(
        owner=UUID(int=9),
        where="Entity project",
        new={"works": works},
        equations=[equation],
        texts=[],
        candidates=[],
    )
    found = undeclared.infer(
        equations=[equation],
        units=default_units,
        lookup=known_values(flows, measures=[measure]),
    )
    assert (found[works].kind, found[works].units, found[works].flow) == (
        Kind.QUANTITY,
        "AUD",
        True,
    )


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
