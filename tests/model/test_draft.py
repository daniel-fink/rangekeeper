"""Make a Model with rk.Model(name=), change it in a ModelDraft and commit it."""

import importlib.util
from datetime import date
from uuid import UUID, uuid4

import pytest

import rangekeeper as rk
from rangekeeper.model import EntityHandle, ModelDraft, ValueHandle, ValueKind
from rangekeeper.model.expression.authoring import (
    add,
    binary,
    date_literal,
    divide,
    equal,
    literal,
    reference,
)
from rangekeeper.quantity import default_units
from rangekeeper.schema.enums import Operator
from rangekeeper.schema.records import Reference
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    EquationError,
    MissingReferenceError,
    RevisionConflictError,
    UnitError,
)

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def ref(handle: ValueHandle):
    return reference(Reference(target=handle.id))


def costs(model=None):
    """Return a draft with a project, three cost values and one equation."""
    draft = (model or rk.Model(name="Costs")).edit()
    project = draft.add_entity(code="project", classification="project")
    land = project.value(key="land_cost", units="AUD")
    works = project.value(key="works_cost", units="AUD")
    total = project.value(key="total_cost", units="AUD")
    project.equations(equal(ref(total), add(ref(land), ref(works))))
    return draft, project


def test_a_new_model_is_empty_and_named():
    model = rk.Model(name="Feasibility", description="Front door")
    assert model.metadata.name == "Feasibility"
    assert model.metadata.description == "Front door"
    assert model.metadata.schema_version == "1.0.0"
    assert (model.definitions, model.system, model.provenance) == (None, None, None)
    assert model.unit_system is default_units
    assert rk.Model is rk.model.Model
    assert rk.Model(name="Feasibility").id != model.id


def test_a_model_takes_keyword_arguments_and_a_name():
    with pytest.raises(TypeError):
        rk.Model("Feasibility")  # type: ignore[misc]
    with pytest.raises(ValueError):
        rk.Model(name=" ")
    with pytest.raises(TypeError, match="namespace"):
        rk.Model(name="Feasibility", namespace="example")  # type: ignore[arg-type]


def test_commit_returns_a_new_revision_and_leaves_the_model_unchanged():
    model = rk.Model(name="Costs")
    draft, project = costs(model)
    assert isinstance(draft, ModelDraft) and draft.model is model
    revision = draft.commit()
    assert revision.id != model.id
    assert revision.metadata.previous == model.id
    assert revision.metadata.name == "Costs"
    assert model.system is None
    entity = revision.entity(code="project")
    assert entity.id == project.id
    value = revision.value(owner=entity.id, key="total_cost")
    assert value.kind == ValueKind.MEASUREMENT and value.quantity is None
    measure = revision.definitions.measures[0]
    assert (measure.code, measure.units) == ("AUD", "AUD")
    assert value.measure == measure.id
    (formulation,) = revision.system.formulations
    assert formulation.code == "project"
    assert len(formulation.constraints) == 1
    assert formulation.constraints[0].predicate == formulation.expressions[0].id


def test_edit_names_the_revision():
    revision = costs()[0].commit()
    draft = revision.edit(name="Second", description="More costs")
    draft.entity(code="project").value(key="fees", units="AUD")
    second = draft.commit()
    assert (second.metadata.name, second.metadata.description) == (
        "Second",
        "More costs",
    )


def test_a_later_draft_finds_entities_and_values_and_adds_equations():
    revision = costs()[0].commit()
    draft = revision.edit()
    project = draft.entity(code="project")
    assert draft.entity(code="project") is project
    assert draft.entity(id=project.id) is project
    total = project.ref(key="total_cost")
    assert isinstance(total, ValueHandle)
    assert (total.id, total.key, total.kind, total.owner, total.units) == (
        revision.value(owner=project.id, key="total_cost").id,
        "total_cost",
        ValueKind.MEASUREMENT,
        project.id,
        "AUD",
    )
    budget = project.value(key="budget", units="AUD")
    project.equations(equal(ref(budget), ref(total)))
    second = draft.commit()
    (formulation,) = second.system.formulations
    assert len(formulation.constraints) == 2
    with pytest.raises(MissingReferenceError) as error:
        project.ref(key="total_cots")
    assert error.value.candidates == ("total_cost",)


def test_a_committed_draft_takes_no_change():
    draft, project = costs()
    draft.commit()
    with pytest.raises(RevisionConflictError):
        project.value(key="fees", units="AUD")
    with pytest.raises(RevisionConflictError):
        draft.add_entity(code="other")
    with pytest.raises(RevisionConflictError):
        draft.commit()


def test_a_draft_with_no_change_does_not_commit_and_stays_open():
    revision = costs()[0].commit()
    draft = revision.edit()
    with pytest.raises(RevisionConflictError):
        draft.commit()
    draft.entity(code="project").value(key="fees", units="AUD")
    assert draft.commit().metadata.previous == revision.id


def test_classification_codes_are_found_or_declared():
    draft = rk.Model(name="Site").edit()
    project = draft.add_entity(code="project", classification="project")
    floor = draft.add_entity(code="floor_1", classification="floor")
    draft.add_entity(code="floor_2", classification="floor")
    use = draft.add_classification(code="hotel", taxonomy="use")
    model = draft.commit()
    entity, uses = model.definitions.taxonomies
    assert entity.code == "entity" and uses.code == "use"
    root, *children = entity.classifications
    assert root.code == "entity" and root.parent is None
    assert [(item.code, item.parent) for item in children] == [
        ("project", root.id),
        ("floor", root.id),
    ]
    assert model.entity(id=project.id).classification == children[0].id
    assert model.entity(id=floor.id).classification == children[1].id
    assert use.parent == uses.classifications[0].id

    draft = model.edit()
    draft.add_classification(code="floor", taxonomy="use")
    with pytest.raises(AmbiguousReferenceError):
        draft.add_entity(code="floor_3", classification="floor")
    with pytest.raises(ContractError) as error:
        draft.add_classification(code="hotel", taxonomy="use")
    assert error.value.code == Code.UNIQUE
    with pytest.raises(MissingReferenceError):
        draft.add_entity(code="floor_3", classification=uuid4())


def test_codes_and_keys_are_unique_and_checked_when_declared():
    draft, project = costs()
    with pytest.raises(ContractError) as error:
        draft.add_entity(code="project")
    assert error.value.code == Code.UNIQUE
    with pytest.raises(ContractError) as error:
        project.value(key="land_cost", units="AUD")
    assert error.value.values["key"] == "land_cost"
    for key in ("land cost", "class", "rx", "NEVER", "2nd"):
        with pytest.raises(ContractError, match="identifier") as error:
            project.value(key=key, units="AUD")
        assert error.value.values == {"key": key}
    with pytest.raises(UnitError) as unit:
        project.value(key="area", units="sqmm")
    assert unit.value.code == Code.UNITS
    with pytest.raises(ContractError):
        draft.add_measure(code="AUD", name="Dollars", units="AUD")


def test_values_share_a_measure_for_their_units():
    draft = rk.Model(name="Units").edit()
    area = draft.add_measure(code="area", name="Area", units="sqm")
    project = draft.add_entity(code="project")
    gfa = project.value(key="gfa", units="sqm")
    nla = project.value(key="nla", units="sqm")
    rent = project.value(key="rent", units="AUD per sqm pa")
    model = draft.commit()
    assert model.value(id=gfa.id).measure == model.value(id=nla.id).measure == area.id
    assert [item.code for item in model.definitions.measures] == [
        "area",
        "AUD per sqm pa",
    ]
    assert rent.units == "AUD per sqm pa"


def test_flows_have_movements_only_when_declared_with_periods():
    draft = rk.Model(name="Flows").edit()
    project = draft.add_entity(code="project")
    index = project.flow(key="rent_index", units="ratio", periods=YEARS)
    rent = project.flow(key="rent", units="AUD")
    with pytest.raises(TypeError, match="Periods"):
        project.flow(key="other", units="AUD", periods=[date(2027, 1, 1)])
    model = draft.commit()
    declared = model.value(id=index.id)
    assert declared.kind == ValueKind.FLOW
    assert declared.flow.units == "ratio"
    assert [m.period for m in declared.flow.movements] == list(YEARS)
    assert all(m.magnitude is None for m in declared.flow.movements)
    assert model.value(id=rent.id).flow is None


def test_equations_are_checked_when_added():
    draft, project = costs()
    land = project.ref(key="land_cost")
    with pytest.raises(TypeError, match="text, a Term or an Expression"):
        project.equations(42)  # type: ignore[arg-type]
    with pytest.raises(ContractError, match="Boolean") as error:
        project.equations(add(ref(land), literal(1, "AUD")))
    assert error.value.code is Code.PREDICATE
    other = rk.Model(name="Other").edit().add_entity(code="other")
    stranger = other.value(key="other", units="AUD")
    with pytest.raises(MissingReferenceError) as missing:
        project.equations(equal(ref(land), ref(stranger)))
    assert missing.value.where == "Entity project"
    with pytest.raises(TypeError):
        project.equations()


def records(expression):
    """Return exported Expression records without the UUIDs of their nodes."""

    def strip(data):
        if isinstance(data, dict):
            return {key: strip(value) for key, value in data.items() if key != "id"}
        if isinstance(data, list):
            return [strip(item) for item in data]
        return data

    return strip(expression.to_data())


def test_equation_text_makes_the_records_of_the_record_constructors():
    draft = rk.Model(name="Value").edit()
    project = draft.add_entity(code="project", classification="project")
    value = project.value(key="value", units="AUD")
    noi = project.value(key="noi", units="AUD pa")
    cap_rate = project.value(key="cap_rate", units="% pa")
    project.equations("value = noi / cap_rate")
    project.equations(equal(ref(value), divide(ref(noi), ref(cap_rate))))
    model = draft.commit()
    (formulation,) = model.system.formulations
    text, record = formulation.expressions
    assert records(text) == records(record)
    assert [c.predicate for c in formulation.constraints] == [text.id, record.id]


def test_equation_text_is_checked_when_added_and_adds_nothing_on_failure():
    draft, project = costs()
    with pytest.raises(EquationError) as error:
        project.equations(
            "total_cost = land_cost + works_cost",
            "total_cost = land_cost + work_cost",
        )
    assert (error.value.code, error.value.start, error.value.end) == (
        Code.REFERENCE_MISSING,
        25,
        34,
    )
    assert error.value.suggestions == ("works_cost", "total_cost")
    with pytest.raises(EquationError) as error:
        project.equations("total_cost + 1 AUD")
    assert error.value.code is Code.PREDICATE
    with pytest.raises(EquationError) as error:
        project.equations("total_cost == land_cost")
    assert error.value.code is Code.EQUATION_SYNTAX
    # A failed call adds no equation; the draft keeps the one of ``costs``.
    (formulation,) = draft.commit().system.formulations
    assert len(formulation.constraints) == 1


def test_equation_text_names_a_value_of_another_entity_by_code_and_key():
    draft = rk.Model(name="Two buildings").edit()
    building = draft.add_entity(code="building_a", classification="building")
    income = building.value(key="income", units="AUD pa")
    project = draft.add_entity(code="project", classification="project")
    total = project.value(key="income", units="AUD pa")
    project.equations("income = building_a.income")
    model = draft.commit()
    (expression,) = model.system.formulations[0].expressions
    assert [operand.target.target for operand in expression.operands] == [
        total.id,
        income.id,
    ]
    project = model.edit().entity(code="project")
    with pytest.raises(EquationError) as error:
        project.equations("income = building_b.income")
    assert error.value.suggestions == ("building_a",)
    with pytest.raises(EquationError) as error:
        project.equations("income = income.total")
    assert error.value.code is Code.REFERENCE_MISSING


def test_assemblies_and_relationships_refer_to_entities_by_handle_or_code():
    draft = rk.Model(name="Graph").edit()
    building = draft.add_entity(code="building", classification="building")
    floor = draft.add_entity(code="floor_1", classification="floor")
    contains = draft.add_relationship(
        source=building, target="floor_1", classification="contains"
    )
    group = draft.add_assembly(code="phase_1", entities=["building", floor.id])
    assert isinstance(group, EntityHandle)
    group.value(key="budget", units="AUD")
    model = draft.commit()
    assert model.relationship(contains.id).source == building.id
    assembly = model.assembly(group.id)
    assert assembly.entities == (building.id, floor.id)
    assert model.value(owner=group.id, key="budget").key == "budget"
    taxonomies = {t.code: t for t in model.definitions.taxonomies}
    assert [c.code for c in taxonomies["relationship"].classifications] == [
        "relationship",
        "contains",
    ]
    with pytest.raises(MissingReferenceError) as error:
        draft.entity(code="buildng")
    assert error.value.candidates == ("building",)


def test_a_handle_belongs_to_its_draft():
    first = rk.Model(name="A").edit()
    handle = first.add_entity(code="a")
    second = rk.Model(name="B").edit()
    second.add_entity(code="a")
    with pytest.raises(ContractError, match="another draft") as error:
        second.add_assembly(code="group", entities=[handle])
    assert error.value.targets == (handle.id,)


def test_a_draft_is_made_by_edit():
    with pytest.raises(TypeError, match="edit"):
        ModelDraft()


def test_a_namespace_derives_the_identities_that_a_draft_makes():
    namespace = UUID("a5ef6c9f-6e0a-4b52-8fbb-2f4b8f43a1b1")

    def build():
        model = rk.Model(name="Costs", namespace=namespace)
        draft = model.edit()
        project = draft.add_entity(code="project", classification="project")
        project.value(key="land_cost", units="AUD")
        project.flow(key="rent_index", units="ratio", periods=YEARS)
        return model, draft.commit()

    (first, first_revision), (second, second_revision) = build(), build()
    assert first.id == second.id
    left, right = first_revision.to_data(), second_revision.to_data()
    assert left["definitions"] == right["definitions"]
    assert left["system"] == right["system"]
    # A revision made from a namespaced Model keeps the namespace.
    third = first_revision.edit()
    third.entity(code="project").value(key="fees", units="AUD")
    fees = third.commit().value(
        owner=first_revision.entity(code="project").id, key="fees"
    )
    again = second_revision.edit()
    again.entity(code="project").value(key="fees", units="AUD")
    assert again.commit().value(id=fees.id).key == "fees"


def test_lesson_02_cell_4_runs_as_written():
    model = rk.Model(name="Mixed-use feasibility")
    draft = model.edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="land_cost", units="AUD")
    project.value(key="works_cost", units="AUD")
    project.value(key="total_cost", units="AUD")
    project.value(key="leverage", units="ratio")
    project.value(key="mortgage", units="AUD")
    project.value(key="mortgage_constant", units="% pa")
    project.value(key="debt_service", units="AUD pa")
    project.value(key="coverage", units="ratio")
    project.value(key="noi", units="AUD pa")
    project.value(key="operating_cost", units="AUD pa")
    project.value(key="effective_income", units="AUD pa")
    project.value(key="rent_factor", units="ratio")
    project.value(key="reference_income", units="AUD pa")
    model = draft.commit()
    assert len(model.system.entities[0].characteristics.values) == 13


@pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")),
    reason="requires the optional execution extra",
)
def test_a_committed_model_solves():
    from rangekeeper.execution import execute
    from rangekeeper.io import MemoryStore
    from rangekeeper.run import SolutionStatus

    model = costs()[0].commit()
    entity = model.entity(code="project")
    land, works, total = (
        model.value(owner=entity.id, key=key).id
        for key in ("land_cost", "works_cost", "total_cost")
    )
    specification = rk.Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(model.id),
            "assignments": [
                {
                    "target": {"target": str(land)},
                    "quantity": {"magnitude": "20000000", "units": "AUD"},
                },
                {
                    "target": {"target": str(works)},
                    "quantity": {"magnitude": "30000000", "units": "AUD"},
                },
            ],
            "unknowns": [{"target": str(total)}],
        }
    )
    store = MemoryStore()
    store.put(model)
    run = execute(specification=specification, store=store).run
    assert run.report.status.solution == SolutionStatus.FEASIBLE
    solved = store.load_model(run.record.outputs[0])
    assert solved.value(id=total).quantity == rk.Quantity(text="50e6 AUD")


def test_dates_have_no_units_and_no_recorded_content():
    draft = rk.Model(name="Dates").edit()
    project = draft.add_entity(code="project", classification="project")
    start = project.date(key="start_date", description="The site is bought")
    assert (start.key, start.owner, start.units) == ("start_date", project.id, None)
    assert project.ref(key="start_date").id == start.id
    model = draft.commit()
    value = model.value(id=start.id)
    assert (value.kind, value.measure, value.date, value.never) == (
        ValueKind.DATE,
        None,
        None,
        None,
    )
    assert value.description == "The site is bought"
    assert model.definitions is None or not model.definitions.measures
    assert model.edit().entity(code="project").ref(key="start_date").units is None


def test_date_keys_follow_the_value_rules():
    draft = rk.Model(name="Dates").edit()
    project = draft.add_entity(code="project")
    project.date(key="start_date")
    with pytest.raises(ContractError) as error:
        project.date(key="start_date")
    assert error.value.code == Code.UNIQUE
    with pytest.raises(ContractError):
        project.value(key="start_date", units="AUD")
    for key in ("start date", "NEVER", "rk", "class"):
        with pytest.raises(ValueError, match="identifier"):
            project.date(key=key)
    with pytest.raises(TypeError):
        project.date(key="sale_date", units="day")  # type: ignore[call-arg]


def test_lesson_03_cell_5_dates_and_their_equations():
    # Cell 03·5 declares the plan's dates and relates them, in equation text,
    # in the "Dates" Formulation. The dates that equations define (#282) come
    # later: here every date is declared.
    model = rk.Model(name="Mixed-use base plan")
    draft = model.edit()
    project = draft.add_entity(code="project", classification="project")
    project.date(key="base_date")
    project.date(key="sale_date")
    start = project.date(key="start_date")
    b_start = project.date(key="b_start")
    shared_start = project.date(key="shared_start")
    project.date(key="a_start")
    project.date(key="a_open")
    project.date(key="b_open")
    dates = project.add_formulation(name="Dates")
    dates.equations(
        "shared_start = start_date",
        "a_start = shared_start + 1 year",
        "a_open = a_start + 2 years",
        "b_open = b_start + 2 years",
        "b_start >= shared_start + 1 year",
    )
    dates.equations("start_date != NEVER")
    model = draft.commit()
    values = model.entity(code="project").record.characteristics.values
    assert [value.key for value in values][:4] == [
        "base_date",
        "sale_date",
        "start_date",
        "b_start",
    ]
    assert {value.kind for value in values} == {ValueKind.DATE}
    formulation = model.formulation(dates.id)
    assert formulation.name == "Dates"
    assert len(formulation.constraints) == 6
    bound, never = formulation.expressions[4:]
    assert records(bound) == records(
        binary(
            Operator.GREATER_THAN_OR_EQUAL,
            ref(b_start),
            add(ref(shared_start), literal(1, "year")),
        )
    )
    assert records(never) == records(
        binary(Operator.NOT_EQUAL, ref(start), date_literal(rk.duration.NEVER))
    )


def test_a_date_equation_needs_dates_and_calendar_lengths():
    draft = rk.Model(name="Dates").edit()
    project = draft.add_entity(code="project")
    start = project.date(key="start_date")
    land = project.value(key="land_cost", units="AUD")
    project.equations(equal(ref(land), add(ref(start), literal(1, "AUD"))))
    with pytest.raises(rk.errors.ValidationError, match="date length"):
        draft.commit()


def test_handles_are_made_by_a_draft_and_display_briefly():
    draft = rk.Model(name="Display").edit()
    project = draft.add_entity(code="project", name="Project")
    site = draft.add_entity(code="site")
    assert repr(project) == "<entity project 'Project'>"
    assert repr(site) == "<entity site>"
    assert repr(project.value(key="land_cost", units="AUD")) == (
        "<value land_cost [AUD] on Project>"
    )
    assert repr(site.flow(key="rent", units="AUD")) == "<flow rent [AUD] on site>"
    assert repr(site.date(key="start")) == "<date start on site>"
    assert "-" not in repr(project.ref(key="land_cost"))
    group = draft.add_assembly(code="group", entities=[project, site])
    assert repr(group) == "<assembly group>"
    with pytest.raises(TypeError):
        ValueHandle()
    with pytest.raises(TypeError):
        EntityHandle()
