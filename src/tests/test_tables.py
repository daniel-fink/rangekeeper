from dataclasses import FrozenInstanceError

import pint
import pytest

import rangekeeper as rk


materialization = rk.graph.materialization
units = rk.measure.Index.registry


def table_model():
    entity_types = rk.graph.Classification(
        code="entity", name="Entity", scheme="project.entity"
    )
    building_kind = entity_types.define(code="building", name="Building")
    space_kind = entity_types.define(code="space", name="Space")
    uses = rk.graph.Classification(code="use", name="Use", scheme="ABS FCB")
    office_use = uses.define(code="231", name="Offices")
    retail_use = uses.define(code="233", name="Shops")
    contains = rk.graph.Classification(
        code="contains", name="Contains", scheme="project.relationship"
    )
    area = rk.measure.Measure(
        code="project.area",
        name="Area",
        units=units.sqm,
        definition="Floor area",
    )
    building = rk.graph.Assembly(
        entity_id="building",
        name="Building",
        classification=building_kind,
        characteristics=rk.graph.Characteristics(
            measures={area: 100 * units.sqm},
            features={"rating": "A"},
        ),
    )
    office = rk.graph.Entity(
        entity_id="office",
        name="Office",
        classification=space_kind,
        characteristics=rk.graph.Characteristics(
            occupancy={"use": (office_use,)},
            measures={area: 10_000 * units.sqft},
            features={"rating": "B"},
        ),
    )
    mixed = rk.graph.Entity(
        entity_id="mixed",
        name="Mixed Use",
        classification=space_kind,
        characteristics=rk.graph.Characteristics(
            occupancy={"use": (office_use, retail_use)},
            features={"rating": "C"},
        ),
    )
    relationships = (
        rk.graph.Relationship(
            "building", "office", contains, relationship_id="building-office"
        ),
        rk.graph.Relationship(
            "building", "mixed", contains, relationship_id="building-mixed"
        ),
    )
    building._replace_contents(entities=(office, mixed), relationships=relationships)
    model = rk.graph.Model()
    model.add_assembly(building)
    return model, building, office, mixed, contains, area


def test_table_is_rectangular_read_only_and_column_addressable():
    table = materialization.Table(
        columns=("name", "value"),
        rows=({"name": "A", "value": 1}, {"name": "B", "value": 2}),
    )

    assert table.column("value") == (1, 2)
    with pytest.raises(TypeError):
        table.rows[0]["value"] = 3
    with pytest.raises(FrozenInstanceError):
        table.columns = ()
    with pytest.raises(ValueError, match="do not match"):
        materialization.Table(columns=("name",), rows=({"other": "A"},))


def test_entity_table_owns_column_order_and_selected_fields():
    model, *_ = table_model()

    table = materialization.entity_table(
        model,
        fields=(
            "entity_id",
            "name",
            "entity_type",
            "classification_code",
            "classification_scheme",
        ),
        features=("rating",),
    )

    assert table.columns == (
        "entity_id",
        "name",
        "entity_type",
        "classification_code",
        "classification_scheme",
        "feature.rating",
    )
    assert table.column("entity_id") == ("building", "mixed", "office")
    assert table.rows[0]["entity_type"] == "assembly"
    assert table.rows[0]["classification_code"] == "building"
    assert table.rows[0]["classification_scheme"] == "project.entity"
    assert table.column("feature.rating") == ("A", "C", "B")


def test_occupancy_projection_is_scheme_aware_and_has_explicit_multi_policy():
    model, _, office, mixed, *_ = table_model()

    table = materialization.entity_table(model, occupancy_facets=("use",))
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[office.entity_id]["occupancy.use"] == (("ABS FCB", "231"),)
    assert rows[mixed.entity_id]["occupancy.use"] == (
        ("ABS FCB", "231"),
        ("ABS FCB", "233"),
    )

    first = materialization.entity_table(
        model,
        occupancy_facets=("use",),
        multiple_classifications="first",
    )
    first_rows = {row["entity_id"]: row for row in first.rows}
    assert first_rows[mixed.entity_id]["occupancy.use"] == ("ABS FCB", "231")

    with pytest.raises(materialization.TableError, match="multiple classifications"):
        materialization.entity_table(
            model,
            occupancy_facets=("use",),
            multiple_classifications="error",
        )


def test_measure_projection_converts_to_target_units_and_uses_numeric_cells():
    model, building, office, _, _, area = table_model()

    table = materialization.entity_table(model, measures={area: units.sqft})
    column = "measure.project.area [squarefoot]"
    rows = {row["entity_id"]: row for row in table.rows}

    assert table.columns[-1] == column
    assert rows[office.entity_id][column] == pytest.approx(10_000)
    assert rows[building.entity_id][column] == pytest.approx(1_076.391)
    assert rows["mixed"][column] is None
    assert not isinstance(rows[office.entity_id][column], pint.Quantity)


def test_default_measure_target_uses_the_measure_definition_units():
    model, _, office, _, _, area = table_model()

    table = materialization.entity_table(model, measures={area: None})
    column = "measure.project.area [squaremeter]"
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[office.entity_id][column] == pytest.approx(929.0304)


def test_parent_and_children_columns_come_from_the_selected_relationship_overlay():
    model, building, office, mixed, contains, _ = table_model()

    table = materialization.entity_table(model, parent_relationship=contains)
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[building.entity_id]["parent_id"] is None
    assert rows[building.entity_id]["children_ids"] == ("mixed", "office")
    assert rows[office.entity_id]["parent_id"] == "building"
    assert rows[mixed.entity_id]["parent_id"] == "building"
    assert rows[office.entity_id]["children_ids"] == ()


def test_reverse_relationship_direction_can_supply_parent_columns():
    contains = rk.graph.Classification(code="contains", name="Contains")
    parent = rk.graph.Entity(entity_id="parent")
    child = rk.graph.Entity(entity_id="child")
    model = rk.graph.Model()
    model.add_entities((parent, child))
    model.add_relationship(
        rk.graph.Relationship(
            "child", "parent", contains, relationship_id="child-parent"
        )
    )

    table = materialization.entity_table(
        model, parent_relationship=contains, outgoing=False
    )
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows["child"]["parent_id"] == "parent"
    assert rows["parent"]["children_ids"] == ("child",)


def test_multiple_parents_are_rejected_for_a_singular_parent_column():
    model, _, office, _, contains, _ = table_model()
    other = rk.graph.Entity(entity_id="other")
    model.add_entity(other)
    model.add_relationship(
        rk.graph.Relationship(
            "other", office.entity_id, contains, relationship_id="other-office"
        )
    )

    with pytest.raises(materialization.TableError, match="multiple parents"):
        materialization.entity_table(model, parent_relationship=contains)


def test_view_projection_remains_scoped_to_the_view():
    model, building, office, _, contains, _ = table_model()
    view = model.view(
        predicate=lambda entity: entity.entity_id in {"building", "office"}
    )

    table = materialization.entity_table(
        view, parent_relationship=contains, features=("rating",)
    )

    assert table.column("entity_id") == (building.entity_id, office.entity_id)
    assert table.column("parent_id") == (None, "building")


def test_feature_projection_preserves_rich_runtime_values():
    model, _, office, *_ = table_model()
    runtime_value = object()
    office.features["runtime"] = runtime_value

    table = materialization.entity_table(model, features=("runtime",))
    rows = {row["entity_id"]: row for row in table.rows}

    assert rows[office.entity_id]["feature.runtime"] is runtime_value


def test_group_by_uses_explicit_functions_and_preserves_first_seen_order():
    table = materialization.Table(
        columns=("use", "area", "count"),
        rows=(
            {"use": "office", "area": 10, "count": 1},
            {"use": "retail", "area": 5, "count": 1},
            {"use": "office", "area": None, "count": 1},
            {"use": "office", "area": 20, "count": 1},
        ),
    )

    grouped = table.group_by(
        by=("use",),
        aggregations={
            "area": lambda values: sum(value for value in values if value is not None),
            "count": sum,
        },
    )

    assert grouped.columns == ("use", "area", "count")
    assert tuple(dict(row) for row in grouped.rows) == (
        {"use": "office", "area": 30, "count": 3},
        {"use": "retail", "area": 5, "count": 1},
    )


def test_table_selection_validation_is_precise():
    model, *_, area = table_model()

    with pytest.raises(materialization.TableError, match="unknown entity fields"):
        materialization.entity_table(model, fields=("unknown",))
    with pytest.raises(TypeError, match="not a string"):
        materialization.entity_table(model, features="rating")
    with pytest.raises(TypeError, match="Measure keys"):
        materialization.entity_table(model, measures={"project.area": None})
    with pytest.raises(pint.DimensionalityError):
        materialization.entity_table(model, measures={area: units.meter})
