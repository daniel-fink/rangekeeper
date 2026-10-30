"""The entities of a Model revision: ``model.entity()`` and ``Entity.values`` (D44).

``model.entity(code=)`` returns a read-only ``ModelEntity``. Its ``values`` show
the units of each value, and whether a call declared them or the draft inferred
them from the equations. The draft stores ``inferred=True`` on each Value that
it infers, and a later revision works those units out again.
"""

from datetime import date
from uuid import UUID

import pytest

import rangekeeper as rk
from rangekeeper.model import ModelEntity, ValueKind

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def project() -> rk.Model:
    """Return a revision with declared inputs, a declared result and inferred values."""
    draft = rk.Model(name="Entity values").edit()
    project = draft.add_entity(code="project", classification="project", name="Project")
    project.value(key="rent", units="AUD per sqm pa", description="Rent per area")
    project.value(key="area", units="sqm")
    project.value(key="value", units="AUD")
    project.value(key="cap_rate", units="ratio")
    project.date(key="start_date")
    project.flow(key="a_works", units="AUD", periods=YEARS)
    project.flow(key="b_works", units="AUD", periods=YEARS)
    project.equations(
        "income = rent * area",
        "value = income * 1 year / cap_rate",
        "open_date = start_date + 2 years",
        "works = a_works + b_works",
    )
    return draft.commit()


def test_entity_is_a_read_only_view_of_its_record():
    model = project()
    entity = model.entity(code="project")
    assert isinstance(entity, ModelEntity)
    record = entity.record
    assert isinstance(record, rk.model.Entity)
    assert (entity.id, entity.code, entity.name, entity.classification) == (
        record.id,
        "project",
        "Project",
        record.classification,
    )
    assert model.entity(id=entity.id) == entity
    assert model.entity(name="Project") == entity
    assert hash(model.entity(id=entity.id)) == hash(entity)
    assert repr(entity) == "<entity project 'Project'>"
    with pytest.raises(TypeError):
        ModelEntity()
    with pytest.raises(AttributeError):
        entity.code = "other"  # type: ignore[misc]


def test_values_show_each_values_units_as_declared_or_inferred():
    entity = project().entity(code="project")
    table = entity.values
    assert table.columns == ("key", "kind", "units", "inferred", "description")
    rows = {row.values["key"]: row for row in table.rows}
    shown = {
        key: (row.values["units"], row.values["inferred"]) for key, row in rows.items()
    }
    assert shown == {
        "rent": ("AUD per sqm pa", False),
        "area": ("sqm", False),
        "value": ("AUD", False),
        "cap_rate": ("ratio", False),
        "start_date": (None, False),
        "a_works": ("AUD", False),
        "b_works": ("AUD", False),
        # No Measure of the revision spells AUD per year, so the text is canonical.
        "income": (rk.quantity.default_units.canonical(units="AUD pa"), True),
        "open_date": (None, True),
        "works": ("AUD", True),
    }
    assert rows["works"].values["kind"] is ValueKind.FLOW
    assert rows["rent"].values["description"] == "Rent per area"
    assert rows["income"].id == entity.record.characteristics.values[7].id


def test_the_draft_stores_the_values_that_it_inferred():
    model = project()
    assert model.value(key="income").inferred is True
    assert model.value(key="value").inferred is None
    data = model.to_data()
    stored = {
        value["key"]: value.get("inferred")
        for value in data["system"]["entities"][0]["characteristics"]["values"]
    }
    assert stored["income"] is True and stored["works"] is True
    # A declared Value has no stored flag.
    assert stored["rent"] is None and stored["value"] is None
    again = rk.Model.from_data(data=data)
    assert again.value(key="income").inferred is True


def test_a_later_revision_works_inferred_units_out_again():
    # A Model from data whose inferred Flow lost its Periods: the next revision
    # works out the kind, units and Periods again from its equation.
    data = project().to_data()
    for value in data["system"]["entities"][0]["characteristics"]["values"]:
        if value["key"] == "works":
            del value["flow"]
    model = rk.Model.from_data(data=data)
    assert model.value(key="works").flow is None
    draft = model.edit()
    draft.entity(code="project").value(key="fee", units="AUD")
    revision = draft.commit()
    works = revision.value(key="works")
    assert (works.kind, works.inferred) == (ValueKind.FLOW, True)
    assert [movement.period for movement in works.flow.movements] == list(YEARS)
    assert works.id == model.value(key="works").id


def test_a_revision_keeps_inferred_values_that_do_not_change():
    model = project()
    draft = model.edit()
    draft.entity(code="project").value(key="fee", units="AUD")
    revision = draft.commit()
    for key in ("income", "open_date", "works"):
        assert revision.value(key=key) == model.value(key=key), key


def test_a_declared_value_stays_a_check():
    draft = project().edit()
    project_handle = draft.entity(code="project")
    project_handle.value(key="noi", units="AUD")
    project_handle.equations("noi = income")
    with pytest.raises(rk.errors.ValidationError) as error:
        draft.commit()
    assert error.value.code is rk.errors.Code.INCOMPATIBLE_UNITS


def test_a_namespace_keeps_the_identities_of_inferred_values():
    namespace = UUID("2f1d7e44-8b9a-4c3d-a1e2-5f6a7b8c9d0e")

    def build() -> rk.Model:
        draft = rk.Model(name="Plan", namespace=namespace).edit()
        project = draft.add_entity(code="project")
        project.flow(key="a_works", units="AUD", periods=YEARS)
        project.equations("works = a_works + a_works")
        return draft.commit()

    # The Expression UUIDs are not derived yet; the values are.
    first, second = build().to_data(), build().to_data()
    assert first["system"]["entities"] == second["system"]["entities"]
