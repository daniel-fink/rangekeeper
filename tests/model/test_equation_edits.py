"""Edit the equations of a Model by key: replace, remove and add_to (G27, D40).

An entity handle finds an equation by its key in any of the entity's
Formulations. ``draft.remove(entity=)`` removes an entity; an equation that
still uses one of its values fails at ``commit()`` with a named error.
"""

from datetime import date

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    EquationError,
    MissingReferenceError,
    RevisionConflictError,
)

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2031, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def plan() -> rk.Model:
    """Return a project with rents that grow, cash and a funding bound."""
    draft = rk.Model(name="Plan").edit()
    project = draft.add_entity(code="project", classification="project")
    project.date(key="a_open")
    project.value(key="a_income", units="AUD pa")
    project.value(key="rent_growth", units="% pa")
    project.value(key="loan", units="AUD")
    project.value(key="loan_limit", units="AUD")
    project.flow(key="a_rent", units="AUD", periods=YEARS)
    project.flow(key="land", units="AUD", periods=YEARS)
    project.flow(key="sale", units="AUD", periods=YEARS)
    operations = project.add_formulation(name="Operations")
    operations.equations(
        "a_rent = rx.profile.compounding(initial=a_income, rate=rent_growth, "
        "start=a_open)",
        "income = a_rent",
    )
    project.equations("project_cash = land + income + sale", "loan <= loan_limit")
    return draft.commit()


def texts(model: rk.Model, *keys: str) -> list[str]:
    return [item.text for item in model.equations.where(key=list(keys))]


def test_replace_keeps_the_key_the_formulation_and_the_identity():
    model = plan()
    (before,) = model.equations.where(key="a_rent")
    draft = model.edit()
    project = draft.entity(code="project")
    project.replace(
        key="a_rent",
        equation="a_rent = rx.profile.constant(initial=a_income, start=a_open)",
    )
    revised = draft.commit()
    (after,) = revised.equations.where(key="a_rent")
    assert after.text == "a_rent = rx.profile.constant(initial=a_income, start=a_open)"
    assert (after.id, after.formulation) == (before.id, "Operations")
    assert [item.key for item in revised.equations] == [
        item.key for item in model.equations
    ]


def test_replace_drops_the_expression_that_it_replaces():
    draft = plan().edit()
    draft.entity(code="project").replace(key="income", equation="income = 2 * a_rent")
    revised = draft.commit()
    (_, operations) = (
        revised.system.formulations[0],
        revised.system.formulations[0].formulations[0],
    )
    assert len(operations.expressions) == len(operations.constraints) == 2


def test_replace_takes_rx_and_a_value_that_it_defines():
    model = plan()
    draft = model.edit()
    project = draft.entity(code="project")
    rent = project.ref(key="a_rent")
    income = project.ref(key="income")
    project.replace(key="income", equation=income == rx.max(rent, "0 AUD"))
    project.equations("gross = a_rent")
    project.replace(key="project_cash", equation="project_cash = land + gross + sale")
    revised = draft.commit()
    assert texts(revised, "income", "project_cash") == [
        "project_cash = land + gross + sale",
        "income = rx.max(a_rent, 0 AUD)",
    ]


def test_replace_checks_the_new_equation_and_changes_nothing_on_failure():
    model = plan()
    draft = model.edit()
    project = draft.entity(code="project")
    with pytest.raises(EquationError) as error:
        project.replace(key="income", equation="income = 2 * a_rnt")
    assert error.value.code is Code.REFERENCE_MISSING
    with pytest.raises(MissingReferenceError) as missing:
        project.replace(key="incme", equation="income = a_rent")
    assert (missing.value.kind, missing.value.by) == ("Equation", "key")
    assert "income" in missing.value.candidates
    with pytest.raises(RevisionConflictError):
        draft.commit()


def test_remove_takes_a_value_and_the_equations_that_name_it_by_key():
    """Lesson 04 cell 3b: remove the rent growth once no equation uses it."""
    model = plan()
    draft = model.edit()
    project = draft.entity(code="project")
    project.replace(
        key="a_rent",
        equation="a_rent = rx.profile.constant(initial=a_income, start=a_open)",
    )
    project.remove(key="rent_growth")
    revised = draft.commit()
    keys = [
        value.key
        for value in revised.entity(code="project").record.characteristics.values
    ]
    assert "rent_growth" not in keys
    with pytest.raises(MissingReferenceError):
        revised.value(key="rent_growth")


def test_an_equation_that_uses_a_removed_value_fails_at_commit():
    draft = plan().edit()
    project = draft.entity(code="project")
    project.remove(key="rent_growth")
    with pytest.raises(MissingReferenceError) as error:
        draft.commit()
    assert (error.value.requested, error.value.by) == ("rent_growth", "key")
    assert error.value.referenced_by == ("a_rent",)
    assert error.value.where == "Entity project"
    # The draft stays open to correct.
    project.remove(key="a_rent")
    with pytest.raises(MissingReferenceError) as again:
        draft.commit()
    assert (again.value.requested, again.value.referenced_by) == ("a_rent", ("income",))


def test_remove_of_a_defined_value_removes_its_equation():
    model = plan()
    draft = model.edit()
    project = draft.entity(code="project")
    project.remove(key="loan")
    project.remove(key="project_cash")
    revised = draft.commit()
    assert [item.key for item in revised.equations] == ["a_rent", "income"]
    with pytest.raises(MissingReferenceError):
        revised.value(key="project_cash")


def test_remove_of_a_key_that_names_nothing_raises_with_the_nearest_keys():
    draft = plan().edit()
    with pytest.raises(MissingReferenceError) as error:
        draft.entity(code="project").remove(key="rent_grwth")
    assert error.value.kind == "Value or equation"
    assert "rent_growth" in error.value.candidates


def test_remove_of_a_value_that_an_equation_of_the_draft_defines():
    draft = plan().edit()
    project = draft.entity(code="project")
    project.equations("net = project_cash - land")
    project.remove(key="net")
    with pytest.raises(RevisionConflictError):
        draft.commit()  # the draft added the value and removed it again
    project.value(key="fees", units="AUD")
    revised = draft.commit()
    assert "net" not in [item.key for item in revised.equations]
    with pytest.raises(MissingReferenceError):
        revised.value(key="net")


def test_add_to_adds_a_term_to_the_right_side():
    """Lesson 05 cell 10: add a site sale to the project's cash."""
    draft = plan().edit()
    project = draft.entity(code="project")
    project.flow(key="b_site_sale", units="AUD", periods=YEARS)
    project.add_to(key="project_cash", term="b_site_sale")
    project.add_to(key="loan", term="1e6 AUD")
    revised = draft.commit()
    assert texts(revised, "project_cash", "loan") == [
        "project_cash = land + income + sale + b_site_sale",
        "loan <= loan_limit + 1000000 AUD",
    ]


def test_add_to_subtracts_a_negated_term_and_takes_rx():
    """Lesson 07 cell 17c: add the cost of an expansion to the works."""
    draft = plan().edit()
    project = draft.entity(code="project")
    project.date(key="expansion_date")
    project.value(key="x_cost", units="AUD")
    project.add_to(
        key="project_cash",
        term="-rx.profile.uniform(total=x_cost, start=expansion_date, length=1 year)",
    )
    sale = project.ref(key="sale")
    project.add_to(key="income", term=-sale)
    project.add_to(key="income", term=sale.cumulative())
    revised = draft.commit()
    assert texts(revised, "project_cash", "income") == [
        "project_cash = land + income + sale"
        " - rx.profile.uniform(total=x_cost, start=expansion_date, length=1 year)",
        "income = a_rent - sale + sale.cumulative()",
    ]


def test_add_to_checks_the_new_equation():
    draft = plan().edit()
    project = draft.entity(code="project")
    with pytest.raises(EquationError) as error:
        project.add_to(key="project_cash", term="b_sale")
    assert error.value.code is Code.REFERENCE_MISSING
    with pytest.raises(EquationError):
        project.add_to(key="project_cash", term="(b_sale")
    with pytest.raises(TypeError, match="term"):
        project.add_to(key="project_cash", term=1)  # type: ignore[arg-type]
    with pytest.raises(RevisionConflictError):
        draft.commit()


def test_add_to_takes_an_equality_or_a_bound():
    draft = rk.Model(name="Logic").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="a", units="AUD")
    project.value(key="b", units="AUD")
    project.equations("a >= 0 AUD and b >= 0 AUD")
    with pytest.raises(ContractError) as error:
        project.add_to(key="a", term="b")
    assert error.value.code is Code.PREDICATE


def test_a_lookup_by_key_raises_for_several_equations_with_the_key():
    """Records can give two Formulations of an entity equations with one key."""
    data = plan().to_data()
    (root,) = data["system"]["formulations"]
    (operations,) = root["formulations"]
    for constraint in operations["constraints"]:
        if constraint["code"] == "income":
            constraint["code"] = "loan"
    draft = rk.Model.from_data(data=data).edit()
    with pytest.raises(AmbiguousReferenceError) as error:
        draft.entity(code="project").replace(key="loan", equation="loan <= 0 AUD")
    assert error.value.candidates == ("loan <= loan_limit", "income = a_rent")


def test_a_committed_draft_takes_no_edit():
    draft = plan().edit()
    project = draft.entity(code="project")
    project.value(key="fees", units="AUD")
    draft.commit()
    for call in (
        lambda: project.replace(key="income", equation="income = a_rent"),
        lambda: project.remove(key="fees"),
        lambda: project.add_to(key="income", term="a_rent"),
        lambda: draft.remove(entity="project"),
    ):
        with pytest.raises(RevisionConflictError):
            call()


def floors() -> rk.Model:
    """Return a project whose income is the sum of two floors, named by code."""
    draft = rk.Model(name="Floors").edit()
    project = draft.add_entity(code="project", classification="project")
    for code in ("a_hotel_floor_1", "a_hotel_floor_2"):
        floor = draft.add_entity(code=code, classification="floor")
        floor.value(key="nla", units="sqm")
        floor.value(key="rent", units="AUD per sqm pa")
        floor.equations("income = nla * rent")
        draft.add_relationship(source="project", target=code, classification="contains")
    draft.add_assembly(code="floors", entities=["a_hotel_floor_1", "a_hotel_floor_2"])
    project.value(key="reference_income", units="AUD pa")
    project.equations(
        "reference_income = a_hotel_floor_1.income + a_hotel_floor_2.income"
    )
    return draft.commit()


def test_remove_of_an_entity_names_the_equations_that_use_it():
    """Lesson 06 cell 24: remove a floor that an equation names by code."""
    draft = floors().edit()
    draft.remove(entity="a_hotel_floor_1")
    with pytest.raises(MissingReferenceError) as error:
        draft.commit()
    assert (error.value.requested, error.value.by) == ("a_hotel_floor_1.income", "path")
    assert error.value.referenced_by == ("reference_income",)
    assert "referenced by: reference_income" in str(error.value)


def test_remove_of_an_entity_takes_its_relationships_and_memberships():
    model = floors()
    draft = model.edit()
    draft.remove(entity=draft.entity(code="a_hotel_floor_1"))
    draft.entity(code="project").replace(
        key="reference_income", equation="reference_income = a_hotel_floor_2.income"
    )
    revised = draft.commit()
    with pytest.raises(MissingReferenceError):
        revised.entity(code="a_hotel_floor_1")
    assert len(revised.system.relationships) == 1
    members = revised.entity(code="floors").record.entities
    assert members == (revised.entity(code="a_hotel_floor_2").id,)
    assert [item.entity for item in revised.equations] == ["a_hotel_floor_2", "project"]


def test_a_handle_of_a_removed_entity_stops_working():
    draft = floors().edit()
    floor = draft.entity(code="a_hotel_floor_2")
    draft.remove(entity=floor.id)
    assert repr(floor) == f"<removed entity {floor.id}>"
    with pytest.raises(MissingReferenceError):
        floor.value(key="fees", units="AUD")
    with pytest.raises(MissingReferenceError):
        draft.entity(code="a_hotel_floor_2")


def test_a_removed_value_cannot_be_used_again_in_the_draft():
    draft = plan().edit()
    project = draft.entity(code="project")
    growth = project.ref(key="rent_growth")
    project.remove(key="rent_growth")
    with pytest.raises(MissingReferenceError):
        project.equations(growth >= "0 % pa")
    with pytest.raises(EquationError):
        project.equations("rent_growth >= 0 % pa")


def test_a_removed_inferred_value_is_not_worked_out_again():
    model = plan()
    assert model.value(key="income").inferred
    draft = model.edit()
    project = draft.entity(code="project")
    project.remove(key="income")
    with pytest.raises(MissingReferenceError) as error:
        draft.commit()
    assert error.value.referenced_by == ("project_cash",)
    project.remove(key="project_cash")
    revised = draft.commit()
    with pytest.raises(MissingReferenceError):
        revised.value(key="income")
