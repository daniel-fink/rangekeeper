"""Chained Specification calls: each returns a new Specification with new Metadata."""

import importlib.util
from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.model.expression.authoring import add, equal, reference
from rangekeeper.schema.records import Assignment, Reference
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    MissingReferenceError,
    UnitError,
)
from rangekeeper.specification import Specification, SpecificationRecord

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def aud(text):
    return rk.Quantity(text=f"{text} AUD")


def costs():
    """Return a committed Model: total_cost = land_cost + works_cost."""
    draft = rk.Model(name="Costs").edit()
    project = draft.add_entity(code="project", classification="project")
    land = project.value(key="land_cost", units="AUD")
    works = project.value(key="works_cost", units="AUD")
    total = project.value(key="total_cost", units="AUD")
    project.flow(key="rent_index", units="ratio", periods=YEARS)

    def ref(handle):
        return reference(Reference(target=handle.id))

    project.equations(equal(ref(total), add(ref(land), ref(works))))
    building = draft.add_entity(code="building_a")
    building.value(key="total_cost", units="AUD")
    return draft.commit()


def targets(specification, field):
    items = getattr(specification.record, field) or ()
    return [item.target if field == "assignments" else item for item in items]


def test_specify_fills_in_the_metadata_and_pins_the_model():
    model = costs()
    front = model.specify(name="Front door", description="Rent from cost")
    assert isinstance(front, Specification)
    assert front.record.model == model.id
    assert front.model_id == model.id
    assert front.metadata.name == "Front door"
    assert front.metadata.description == "Rent from cost"
    assert front.metadata.schema_version == "1.0.0"
    assert front.metadata.previous is None
    assert not front.record.assignments
    assert model.specify().id != front.id


def test_each_call_returns_a_new_specification_and_leaves_the_last_one():
    model = costs()
    project = model.entity(code="project").id
    land = model.value(owner=project, key="land_cost")
    total = model.value(owner=project, key="total_cost")
    front = model.specify(name="Front door")
    fixed = front.fix(land_cost=aud("20e6"), works_cost=aud("30e6"))
    assert fixed.id != front.id
    assert fixed.metadata.previous == front.id
    assert fixed.metadata.name == "Front door"
    assert not front.record.assignments
    assert targets(fixed, "assignments")[0] == Reference(target=land.id)
    assert fixed.record.assignments[0].quantity == aud("20e6")

    refixed = fixed.fix(land_cost=aud("25e6"))
    assert [a.quantity for a in refixed.record.assignments] == [
        aud("30e6"),
        aud("25e6"),
    ]
    freed = refixed.free("land_cost")
    assert targets(freed, "unknowns") == [
        Reference(target=land.id),
        Reference(target=total.id),
    ]
    assert len(freed.record.assignments) == 1
    assert targets(freed.fix(land_cost=aud("1")), "unknowns") == [
        Reference(target=total.id)
    ]


def test_dotted_paths_uuids_and_ambiguous_keys():
    model = costs()
    building = model.value(owner=model.entity(code="building_a").id, key="total_cost")
    spec = model.specify()
    with pytest.raises(AmbiguousReferenceError) as error:
        spec.fix(total_cost=aud("1"))
    assert error.value.candidates == ("project.total_cost", "building_a.total_cost")
    fixed = spec.fix({"building_a.total_cost": aud("1")})
    assert targets(fixed, "assignments") == [Reference(target=building.id)]
    assert spec.fix({building.id: aud("1")}).record.assignments == (
        fixed.record.assignments
    )
    with pytest.raises(MissingReferenceError) as error:
        spec.fix(land_cots=aud("1"))
    assert "land_cost" in error.value.candidates
    for path in ("zz.total_cost", "project.total_cots"):
        with pytest.raises(MissingReferenceError) as error:
            spec.fix({path: aud("1")})
        assert (error.value.kind, error.value.by) == ("Value", "path")
        assert error.value.requested == path
    assert "project.total_cost" in error.value.candidates
    with pytest.raises(TypeError, match="twice"):
        spec.fix({"land_cost": aud("1")}, land_cost=aud("2"))


def test_a_flow_fixes_each_movement_or_the_selected_ones():
    model = costs()
    index = model.value(owner=model.entity(code="project").id, key="rent_index")
    movements = [m.id for m in index.flow.movements]
    ratio = rk.Quantity(text="1 ratio")
    every = model.specify().fix(rent_index=ratio)
    assert targets(every, "assignments") == [Reference(target=m) for m in movements]
    first = model.specify().fix(rent_index={movements[0]: ratio})
    assert targets(first, "assignments") == [Reference(target=movements[0])]
    freed = every.free(movements[-1])
    assert Reference(target=movements[-1]) in targets(freed, "unknowns")
    assert len(freed.record.assignments) == 2


def test_fix_and_free_check_their_arguments():
    model = costs()
    spec = model.specify()
    with pytest.raises(TypeError, match="at least one"):
        spec.fix()
    with pytest.raises(TypeError, match="at least one"):
        spec.free()
    with pytest.raises(UnitError, match="bare number fixes a ratio"):
        spec.fix(land_cost=20e6)
    with pytest.raises(TypeError, match="Quantity"):
        spec.fix(land_cost=True)
    with pytest.raises(TypeError, match="Quantity"):
        spec.fix(land_cost=None)
    with pytest.raises(UnitError):
        spec.fix(land_cost=rk.Quantity(text="20 sqm"))
    with pytest.raises(ContractError, match="more than once") as error:
        spec.free("land_cost", "project.land_cost")
    assert error.value.code is Code.UNIQUE


def test_a_specification_needs_its_model_for_keys():
    model = costs()
    record = SpecificationRecord(
        metadata=rk.model.Metadata(id=uuid4(), schema_version="1.0.0"),
        model=model.id,
    )
    with pytest.raises(ContractError, match="no Model"):
        Specification(record=record).fix(land_cost=aud("1"))
    attached = Specification(record=record, model=model).fix(land_cost=aud("1"))
    assert attached.metadata.previous == record.metadata.id
    with pytest.raises(ContractError, match="pins") as error:
        Specification(record=record, model=rk.Model(name="Other"))
    assert error.value.code is Code.IDENTITY
    with pytest.raises(TypeError, match="Model"):
        Specification(record=record, model=object())  # type: ignore[arg-type]


@pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")),
    reason="requires the optional execution extra",
)
def test_a_chained_specification_solves():
    from rangekeeper.execution import execute
    from rangekeeper.io import MemoryStore
    from rangekeeper.run import SolutionStatus

    model = costs()
    store = MemoryStore()
    store.put(model)
    front = model.specify(name="Front door").fix(
        land_cost=aud("20e6"), works_cost=aud("30e6")
    )
    back = front.fix({"project.total_cost": aud("60e6")}).free("land_cost")
    results = {}
    for name, specification in (("front", front), ("back", back)):
        run = execute(specification=specification, store=store).run
        assert run.report.status.solution == SolutionStatus.FEASIBLE
        results[name] = store.load_model(run.record.outputs[0])
    project = model.entity(code="project").id
    assert results["front"].value(owner=project, key="total_cost").quantity == aud(
        "50e6"
    )
    assert results["back"].value(owner=project, key="land_cost").quantity == aud("30e6")


def with_estimate(specification, key, quantity):
    """Return a revision of ``specification`` with an estimate for ``key``."""
    model = specification.model
    value = model.value(owner=model.entity(code="project").id, key=key)
    estimate = Assignment(target=Reference(target=value.id), quantity=quantity)
    metadata = specification.metadata.replace(id=uuid4(), previous=specification.id)
    return specification.revise(
        specification.record.replace(metadata=metadata, estimates=(estimate,))
    )


def test_free_keeps_an_estimate_and_fix_replaces_it():
    model = costs()
    spec = with_estimate(model.specify(), "land_cost", aud("20e6"))
    assert spec.record.estimates
    # A free of a free value changes no role: the same Specification.
    assert spec.free("land_cost") is spec
    other = spec.fix(works_cost=aud("30e6"))
    assert other.record.estimates == spec.record.estimates
    assert other.free("works_cost").record.estimates == spec.record.estimates
    fixed = spec.fix(land_cost=aud("25e6"))
    assert not fixed.record.estimates
    assert not fixed.free("land_cost").record.estimates


def three_costs():
    """Return a committed Model with three independent values."""
    draft = rk.Model(name="Three costs").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("first", "middle", "last"):
        project.value(key=key, units="AUD")
    return draft.commit()


def fixed_three():
    return three_costs().specify().fix(first="1 AUD", middle="2 AUD", last="3 AUD")


def fixed_values(specification):
    """Return (key, quantity) of each assignment, in stored order."""
    model = specification.model
    project = model.entity(code="project").id
    keys = {
        model.value(owner=project, key=key).id: key
        for key in ("first", "middle", "last")
    }
    return [
        (keys[item.target.target], item.quantity)
        for item in specification.record.assignments
    ]


@pytest.mark.parametrize(
    ("key", "amount"),
    [("first", "1"), ("middle", "2"), ("last", "3")],
)
def test_fix_with_the_same_value_returns_the_same_specification(key, amount):
    spec = fixed_three()
    assert spec.fix(**{key: f"{amount} AUD"}) is spec
    assert spec.fix(**{key: aud(amount)}) is spec


def test_fix_of_the_same_values_in_another_order_returns_the_same_specification():
    spec = fixed_three()
    assert spec.fix(last="3 AUD", first="1 AUD") is spec
    assert spec.fix(middle="2 AUD", last="3 AUD", first="1 AUD") is spec


def test_fix_of_each_movement_with_the_same_value_returns_the_same_specification():
    spec = costs().specify().fix(rent_index=1.0).fix(land_cost="20e6 AUD")
    assert spec.fix(rent_index=1.0) is spec


@pytest.mark.parametrize("key", ["first", "middle", "last"])
def test_fix_with_another_value_moves_the_assignment_to_the_end(key):
    spec = fixed_three()
    changed = spec.fix(**{key: "9 AUD"})
    assert changed is not spec
    assert changed.metadata.previous == spec.id
    assert fixed_values(changed) == [
        *(item for item in fixed_values(spec) if item[0] != key),
        (key, aud("9")),
    ]


def test_fix_of_the_same_value_beside_another_value_moves_both_to_the_end():
    changed = fixed_three().fix(first="1 AUD", middle="9 AUD")
    assert fixed_values(changed) == [
        ("last", aud("3")),
        ("first", aud("1")),
        ("middle", aud("9")),
    ]
