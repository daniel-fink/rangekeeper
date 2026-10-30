"""Group equations in named Formulations of an entity: add_formulation and formulation.

The names and the order of the calls follow lesson 03 (cells 5–8, 12, 18 and 21).
Its equations need equation functions and Flow equations (#278, #279), so these
tests use equations that parse now, in the same Formulations.
"""

import importlib.util
from uuid import UUID

import pytest

import rangekeeper as rk
from rangekeeper.model import FormulationHandle
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    ContractError,
    EquationError,
    MissingReferenceError,
    RevisionConflictError,
)

EXECUTION = all(importlib.util.find_spec(name) for name in ("pyomo", "highspy"))


def plan(model: rk.Model | None = None) -> rk.model.ModelDraft:
    """Return a draft with the project, its dates and its costs."""
    draft = (model or rk.Model(name="Mixed-use base plan")).edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("start_date", "b_start", "shared_start", "a_start", "a_open"):
        project.date(key=key)
    for key in ("land_cost", "a_cost", "b_cost", "works", "total_cost"):
        project.value(key=key, units="AUD")
    return draft


def groups(model: rk.Model) -> dict[str | None, list[int]]:
    """Return the number of equations of each Formulation, by name or code."""
    found: dict[str | None, list[int]] = {}

    def visit(formulation: rk.model.Formulation) -> None:
        label = formulation.name or formulation.code
        found.setdefault(label, []).append(len(formulation.constraints or ()))
        for child in formulation.formulations or ():
            visit(child)

    for root in model.system.formulations or ():
        visit(root)
    return found


def test_a_named_formulation_groups_its_equations_under_the_default_formulation():
    draft = plan()
    project = draft.entity(code="project")
    dates = project.add_formulation(name="Dates")
    dates.equations(
        "shared_start = start_date",
        "a_start = shared_start + 1 year",
        "a_open = a_start + 2 years",
        "b_start >= shared_start + 1 year",
    )
    development = project.add_formulation(name="Development")
    development.equations("works = a_cost + b_cost")
    project.equations("total_cost = land_cost + works")
    model = draft.commit()
    (root,) = model.system.formulations
    assert (root.code, root.name) == ("project", None)
    assert [child.name for child in root.formulations] == ["Dates", "Development"]
    assert groups(model) == {"project": [1], "Dates": [4], "Development": [1]}
    # The named Formulations are records of the revision, found by their UUID.
    assert model.formulation(dates.id).name == "Dates"
    assert model.owner_of(dates.id) == root.id


def test_a_later_draft_finds_a_formulation_and_adds_to_it():
    # Cells 12, 18 and 21: "Funding" is made once, then found in later drafts.
    draft = plan()
    funding = draft.entity(code="project").add_formulation(name="Funding")
    funding.equations("works = a_cost + b_cost")
    model = draft.commit()
    draft = model.edit()
    project = draft.entity(code="project")
    found = project.formulation(name="Funding")
    assert found == funding
    assert (found.id, found.name, found.owner) == (funding.id, "Funding", project.id)
    found.equations("total_cost = land_cost + works", "land_cost >= 0 AUD")
    model = draft.commit()
    assert groups(model) == {"project": [0], "Funding": [3]}
    # The default Formulation exists, with the named one as its child.
    assert model.edit().entity(code="project").formulation(name="Funding") == found


def test_one_call_adds_to_one_formulation_and_a_formulation_takes_more_calls():
    # Cells 7 and 7b add to "Operations" with two calls.
    draft = plan()
    project = draft.entity(code="project")
    operations = project.add_formulation(name="Operations")
    operations.equations("works = a_cost + b_cost")
    operations.equations("total_cost = land_cost + works")
    model = draft.commit()
    assert groups(model) == {"project": [0], "Operations": [2]}


def test_a_name_is_declared_once_and_found_by_name():
    draft = plan()
    project = draft.entity(code="project")
    with pytest.raises(MissingReferenceError) as missing:
        project.formulation(name="Funding")
    assert (missing.value.kind, missing.value.by) == ("Formulation", "name")
    assert missing.value.candidates == ()
    project.add_formulation(name="Funding", description="Equity first, then the loan")
    with pytest.raises(ContractError) as duplicate:
        project.add_formulation(name="Funding")
    assert duplicate.value.code == Code.UNIQUE
    assert duplicate.value.values["name"] == "Funding"
    with pytest.raises(MissingReferenceError) as near:
        project.formulation(name="Fundng")
    assert near.value.candidates == ("Funding",)
    assert near.value.where == "Entity project"
    for name in ("", "  "):
        with pytest.raises(ContractError):
            project.add_formulation(name=name)
    with pytest.raises(TypeError):
        project.add_formulation(name=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        project.add_formulation("Funding")  # type: ignore[misc]
    model = draft.commit()
    (funding,) = model.system.formulations[0].formulations
    assert funding.description == "Equity first, then the loan"


def test_names_belong_to_their_entity():
    draft = plan()
    project = draft.entity(code="project")
    site = draft.add_entity(code="site")
    site.value(key="area", units="sqm")
    project.add_formulation(name="Funding")
    site_funding = site.add_formulation(name="Funding")
    site_funding.equations("area >= 0 sqm")
    # The equations of a Formulation name the keys of its entity.
    with pytest.raises(EquationError, match="not found in Entity site"):
        site_funding.equations("works = a_cost + b_cost")
    model = draft.commit()
    roots = {root.code: root for root in model.system.formulations}
    assert [child.name for child in roots["site"].formulations] == ["Funding"]
    assert repr(site_funding) == "<formulation 'Funding' on site>"


def test_a_failed_call_adds_no_equation():
    draft = plan()
    dates = draft.entity(code="project").add_formulation(name="Dates")
    with pytest.raises(EquationError):
        dates.equations("a_start = start_date + 1 year", "a_open = a_strat + 2 years")
    with pytest.raises(TypeError):
        dates.equations()
    model = draft.commit()
    assert groups(model) == {"project": [0], "Dates": [0]}


def test_a_committed_draft_takes_no_formulation():
    draft = plan()
    project = draft.entity(code="project")
    dates = project.add_formulation(name="Dates")
    draft.commit()
    with pytest.raises(RevisionConflictError):
        project.add_formulation(name="Funding")
    with pytest.raises(RevisionConflictError):
        dates.equations("a_start = start_date + 1 year")


def test_handles_are_made_by_a_draft_and_display_briefly():
    draft = plan()
    project = draft.entity(code="project")
    dates = project.add_formulation(name="Dates")
    assert repr(dates) == "<formulation 'Dates' on project>"
    assert isinstance(dates, FormulationHandle)
    with pytest.raises(TypeError):
        FormulationHandle()


def test_a_namespace_derives_the_identities_of_named_formulations():
    namespace = UUID("4d1a4f53-6c51-49a8-9a7e-0b5c7d4f6a10")

    def build() -> rk.Model:
        draft = plan(rk.Model(name="Plan", namespace=namespace))
        draft.entity(code="project").add_formulation(name="Dates")
        return draft.commit()

    first, second = build(), build()
    assert first.to_data()["system"] == second.to_data()["system"]


@pytest.mark.skipif(not EXECUTION, reason="requires the optional execution extra")
def test_equations_of_a_named_formulation_hold_in_a_solve_and_name_it():
    draft = plan()
    project = draft.entity(code="project")
    project.add_formulation(name="Development").equations("works = a_cost + b_cost")
    project.equations("total_cost = land_cost + works")
    model = draft.commit()
    specification = model.specify(name="Costs").fix(
        land_cost="20e6 AUD", a_cost="30e6 AUD", b_cost="10e6 AUD"
    )
    outcome = rk.execution.solve(specification=specification)
    assert outcome["total_cost"] == rk.Quantity(text="60e6 AUD")
    named = {
        diagnostic.values["equation"]: diagnostic.values.get("formulation")
        for diagnostic in outcome.diagnostics
        if "equation" in (diagnostic.values or {})
    }
    assert named == {
        "works = a_cost + b_cost": "Development",
        "total_cost = land_cost + works": "project",
    }
