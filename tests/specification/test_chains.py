"""Chained Specification calls: each returns a new Specification with new Metadata."""

import importlib.util
from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.model.expression.authoring import add, equal, reference
from rangekeeper.schema.records import Reference
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
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
    assert front.metadata.name == "Front door"
    assert front.metadata.description == "Rent from cost"
    assert front.metadata.schema_version == "1.0.0"
    assert front.metadata.previous is None
    assert not front.record.assignments
    assert model.specify().id != front.id


def test_each_call_returns_a_new_specification_and_leaves_the_last_one():
    model = costs()
    land = model.value(owner=model.entity(code="project").id, key="land_cost")
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
    assert targets(freed, "unknowns") == [Reference(target=land.id)]
    assert len(freed.record.assignments) == 1
    assert not freed.fix(land_cost=aud("1")).record.unknowns


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
    assert targets(freed, "unknowns") == [Reference(target=movements[-1])]
    assert len(freed.record.assignments) == 2


def test_fix_and_free_check_their_arguments():
    model = costs()
    spec = model.specify()
    with pytest.raises(TypeError, match="at least one"):
        spec.fix()
    with pytest.raises(TypeError, match="at least one"):
        spec.free()
    with pytest.raises(TypeError, match="Quantity"):
        spec.fix(land_cost=20e6)
    with pytest.raises(UnitError):
        spec.fix(land_cost=rk.Quantity(text="20 sqm"))
    with pytest.raises(ValueError, match="more than once"):
        spec.free("land_cost", "project.land_cost")


def test_a_specification_needs_its_model_for_keys():
    model = costs()
    record = SpecificationRecord(
        metadata=rk.model.Metadata(id=uuid4(), schema_version="1.0.0"),
        model=model.id,
    )
    with pytest.raises(ValueError, match="no Model"):
        Specification(record).fix(land_cost=aud("1"))
    attached = Specification(record, model=model).fix(land_cost=aud("1"))
    assert attached.metadata.previous == record.metadata.id
    with pytest.raises(ValueError, match="pins"):
        Specification(record, model=rk.Model(name="Other"))
    with pytest.raises(TypeError, match="Model"):
        Specification(record, model=object())  # type: ignore[arg-type]


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
    front = (
        model.specify(name="Front door")
        .fix(land_cost=aud("20e6"), works_cost=aud("30e6"))
        .free("project.total_cost")
    )
    back = front.fix({"project.total_cost": aud("60e6")}).free("land_cost")
    results = {}
    for name, specification in (("front", front), ("back", back)):
        run = execute(specification, store).run
        assert run.report.status.solution == SolutionStatus.FEASIBLE
        results[name] = store.load_model(run.record.outputs[0])
    project = model.entity(code="project").id
    assert results["front"].value(owner=project, key="total_cost").quantity == aud(
        "50e6"
    )
    assert results["back"].value(owner=project, key="land_cost").quantity == aud("30e6")
