"""Specification.on moves a Specification to another Model revision."""

from uuid import UUID

import pytest

import rangekeeper as rk
from rangekeeper.model.expression.authoring import add, equal, reference
from rangekeeper.schema.records import Reference
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, UnitError
from rangekeeper.specification import Role
from tests.specification.lesson_02 import lesson_02_model
from tests.specification.test_roles import front_door

NAMESPACE = UUID("0b4c9a52-3f7e-4f0e-9d55-6a1f3c2b8e10")


def roles(specification):
    return {row.values["key"]: row.values["role"] for row in specification.roles.rows}


def with_fees(model):
    """Return a revision that adds fees to the total cost."""
    draft = model.edit()
    project = draft.entity(code="project")
    fees = project.value(key="fees", units="AUD")
    project.equations(
        equal(
            reference(Reference(target=fees.id)),
            add(
                reference(Reference(target=project.ref(key="land_cost").id)),
                reference(Reference(target=project.ref(key="works_cost").id)),
            ),
        )
    )
    return draft.commit()


def test_on_keeps_the_roles_and_frees_the_new_values():
    model = lesson_02_model()
    front = front_door(model)
    revised = with_fees(model)
    moved = front.on(model=revised)
    assert moved.model_id == revised.id
    assert moved.metadata.previous == front.id
    assert moved.metadata.name == front.metadata.name
    assert front.model_id == model.id
    assert moved.record.assignments == front.record.assignments
    assert roles(moved) == {**roles(front), "fees": Role.FREE}
    # Later calls use the new revision.
    assert roles(moved.fix(fees="1e6 AUD"))["fees"] is Role.FIXED
    assert moved.on(model=revised) is moved


def test_on_refuses_a_fixed_value_that_the_revision_lacks():
    model = lesson_02_model(namespace=NAMESPACE)
    front = front_door(model)
    lean = lesson_02_model(
        name="No operating cost", namespace=NAMESPACE, operating_cost=False
    )
    with pytest.raises(ContractError, match="free them first") as error:
        front.on(model=lean)
    assert error.value.code is Code.REFERENCE_MISSING
    assert error.value.values["keys"] == ("operating_cost",)
    operating = model.value(owner=model.entity(code="project").id, key="operating_cost")
    assert error.value.targets == (operating.id,)
    # Free the value first: a free value that the revision lacks is dropped.
    moved = front.free("operating_cost").on(model=lean)
    assert "operating_cost" not in roles(moved)
    assert roles(moved)["land_cost"] is Role.FIXED
    assert len(moved.record.unknowns) == 6


def test_on_checks_its_arguments_and_units():
    model = lesson_02_model(namespace=NAMESPACE)
    front = front_door(model)
    with pytest.raises(TypeError, match="Model"):
        front.on(model=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        front.on(lesson_02_model())  # type: ignore[misc]
    # A Model that gives land_cost other units.
    draft = rk.Model(name="Other units", namespace=NAMESPACE).edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="land_cost", units="sqm")
    for key in (
        "works_cost",
        "operating_cost",
        "reference_income",
        "mortgage_constant",
    ):
        project.value(key=key, units="AUD")
    project.value(key="leverage", units="ratio")
    project.value(key="coverage", units="ratio")
    with pytest.raises(UnitError):
        front.on(model=draft.commit())
