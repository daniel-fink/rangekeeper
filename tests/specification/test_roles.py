"""Specification roles: unfixed values are free; fix takes text, numbers and Quantities."""

import importlib.util
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.schema.records import Reference, RuleSet
from rangekeeper.shared.errors import UnitError
from rangekeeper.specification import Role, Specification
from tests.specification.lesson_02 import DATA, lesson_02_model

requires_execution = pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")),
    reason="requires the optional execution extra",
)

CONSTANT = rk.Quantity(text="8.6 % pa")


def front_door(model):
    """Return the Specification of lesson 02, cells 10 and 10b."""
    data = DATA
    front = (
        model.specify(name="Front door")
        .fix(land_cost="20e6 AUD", works_cost=data["works_cost"])
        .fix(operating_cost=data["operating_cost"])
        .fix(leverage="65 %", coverage=1.25, mortgage_constant=CONSTANT)
    )
    return front.fix(reference_income=data["reference_income"])


def roles(specification):
    return {row.values["key"]: row.values["role"] for row in specification.roles.rows}


def test_a_value_that_is_not_fixed_is_free():
    model = lesson_02_model()
    empty = model.specify()
    assert set(roles(empty).values()) == {Role.FREE}
    assert len(empty.record.unknowns) == 13
    front = front_door(model)
    assert roles(front) == {
        "land_cost": Role.FIXED,
        "works_cost": Role.FIXED,
        "total_cost": Role.FREE,
        "leverage": Role.FIXED,
        "mortgage": Role.FREE,
        "mortgage_constant": Role.FIXED,
        "debt_service": Role.FREE,
        "coverage": Role.FIXED,
        "noi": Role.FREE,
        "operating_cost": Role.FIXED,
        "effective_income": Role.FREE,
        "rent_factor": Role.FREE,
        "reference_income": Role.FIXED,
    }


def test_the_roles_table():
    model = lesson_02_model()
    front = front_door(model)
    table = front.roles
    assert table.columns == ("key", "movement", "role", "quantity")
    land = model.value(owner=model.entity(code="project").id, key="land_cost")
    row = table.row(land.id)
    assert row.values["quantity"] == rk.Quantity(text="20e6 AUD")
    assert row.values["role"] is Role.FIXED
    assert row.values["movement"] is None
    noi = table.rows[table.column("key").index("noi")]
    assert noi.values["role"] is Role.FREE
    assert noi.values["quantity"] is None


def test_fix_takes_text_numbers_and_quantities():
    model = lesson_02_model()
    front = front_door(model)
    quantities = {
        row.values["key"]: row.values["quantity"]
        for row in front.roles.rows
        if row.values["role"] is Role.FIXED
    }
    assert quantities["land_cost"] == rk.Quantity(text="20e6 AUD")
    assert quantities["leverage"] == rk.Quantity(text="65 %")
    assert quantities["coverage"] == rk.Quantity(magnitude=1.25, units="ratio")
    assert quantities["mortgage_constant"] == CONSTANT
    # A bare number is a ratio: a percentage target takes it too.
    assert front.fix(leverage=0.5).roles.row(
        model.value(owner=model.entity(code="project").id, key="leverage").id
    ).values["quantity"] == rk.Quantity(magnitude=0.5, units="ratio")
    with pytest.raises(UnitError, match="bare number fixes a ratio"):
        front.fix(land_cost=20e6)
    with pytest.raises(UnitError):
        front.fix(land_cost="20 sqm")
    with pytest.raises(UnitError, match="state the units"):
        front.fix(land_cost="20e6")
    with pytest.raises(TypeError, match="Quantity"):
        front.fix(coverage=True)


def test_a_later_fix_replaces_the_earlier_one_and_free_releases_it():
    model = lesson_02_model()
    front = front_door(model)
    refixed = front.fix(land_cost="25e6 AUD")
    land = model.value(owner=model.entity(code="project").id, key="land_cost")
    assert refixed.roles.row(land.id).values["quantity"] == rk.Quantity(text="25e6 AUD")
    assert len(refixed.record.assignments) == len(front.record.assignments)
    # Lesson 02, cell 13: change two roles.
    back = front.fix(rent_factor=1).free("land_cost")
    assert roles(back)["rent_factor"] is Role.FIXED
    assert roles(back)["land_cost"] is Role.FREE
    assert back.model_id == front.model_id == model.id
    # Nothing changes: the same Specification.
    assert back.free("land_cost") is back
    assert back.free("noi") is back
    assert back.fix(rent_factor=1) is back


def test_roles_need_the_model_and_a_concrete_specification():
    model = lesson_02_model()
    record = rk.specification.SpecificationRecord(
        metadata=rk.model.Metadata(id=uuid4(), schema_version="1.0.0"),
        model=model.id,
    )
    with pytest.raises(ValueError, match="no Model"):
        Specification(record).roles  # noqa: B018
    case = model.specify()
    batch = Specification(
        rk.specification.SpecificationRecord(
            metadata=rk.model.Metadata(id=uuid4(), schema_version="1.0.0"),
            model=model.id,
            cases=(case.id,),
        ),
        model=model,
    )
    with pytest.raises(ValueError, match="batch"):
        batch.roles  # noqa: B018


def test_a_rule_decides_its_target():
    model = lesson_02_model()
    land = model.value(owner=model.entity(code="project").id, key="land_cost")
    record = model.specify().record
    controlled = Specification(
        record.replace(
            unknowns=tuple(r for r in record.unknowns if r.target != land.id),
            rules=RuleSet(
                id=uuid4(), targets=(Reference(target=land.id),), decisions=()
            ),
        ),
        model=model,
    )
    assert controlled.roles.row(land.id).values["role"] is Role.DECIDED
    # A chained call does not free a decided value.
    fixed = controlled.fix(leverage="65 %")
    assert Reference(target=land.id) not in fixed.record.unknowns
    assert fixed.roles.row(land.id).values["role"] is Role.DECIDED


@requires_execution
def test_lesson_02_front_and_back_doors_solve():
    model = lesson_02_model()
    front = front_door(model)
    # Cells 11 and 13.
    front_outcome = rk.execution.solve(specification=front)
    front_outcome.raise_for_status()
    factor = front_outcome["rent_factor"]
    back = front.fix(rent_factor=1).free("land_cost")
    back_outcome = rk.execution.solve(specification=back)
    assert back_outcome.status is rk.execution.Status.FEASIBLE
    # Cell 16: the round trip gives back the land cost.
    round_trip = back.fix(rent_factor=front_outcome["rent_factor"])
    assert rk.quantity.isclose(
        actual=rk.execution.solve(specification=round_trip)["land_cost"],
        expected=rk.Quantity(text="20e6 AUD"),
    )
    # Cell 22.
    assert rk.quantity.isclose(
        actual=front_outcome["effective_income"],
        expected=factor * front_outcome["reference_income"],
    )
    assert back.model_id == front.model_id == model.id
