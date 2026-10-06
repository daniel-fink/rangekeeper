"""Model-backed graph behavior, independent of legacy Graph domain assumptions."""

from dataclasses import FrozenInstanceError
import subprocess
import sys
from uuid import uuid4

import pytest

from rangekeeper.model import (
    Model,
    Metadata,
    Definitions,
    Classification,
    Taxonomy,
    System,
    Entity,
    Assembly,
    Relationship,
    Characteristics,
    Value,
    Measure,
    Quantity,
    Formulation,
    Update,
)
from rangekeeper.graph import (
    View,
    Hierarchy,
    Reduction,
    SelectionError,
    HierarchyError,
    AggregationError,
)
from rangekeeper.graph.membership import (
    entities_in,
    relationships_in,
    containing_assemblies,
)
from rangekeeper.graph.selection import select_value
from rangekeeper.graph.reducers import (
    sum_quantities,
    mean_quantities,
    min_quantity,
    max_quantity,
)
from rangekeeper.errors import MissingReferenceError, ReferenceTypeError, UnitError
from rangekeeper.io import json as codec


def fixture(*, missing=False, overlap=False, amounts=(10, 20, 0)):
    measure = Measure(id=uuid4(), code="area", name="Area", units="meter ** 2")
    classification_root = Classification(id=uuid4(), code="kind", name="Kind")
    link = Classification(
        id=uuid4(), code="contains", name="Contains", parent=classification_root.id
    )
    node_class = Classification(
        id=uuid4(), code="room", name="Room", parent=classification_root.id
    )
    taxonomy = Taxonomy(
        id=uuid4(),
        code="project",
        name="Project",
        classifications=(classification_root, link, node_class),
    )
    nodes = []
    for code, magnitude in zip(("a", "b", "c"), amounts):
        quantity = (
            {}
            if (missing and code == "b")
            else {"quantity": Quantity(magnitude=magnitude, units="meter ** 2")}
        )
        values = (
            Value(
                id=uuid4(),
                key="net",
                kind="measurement",
                measure=measure.id,
                **quantity
            ),
            Value(
                id=uuid4(),
                key="gross",
                kind="measurement",
                measure=measure.id,
                quantity=Quantity(magnitude=100, units="meter ** 2"),
            ),
        )
        nodes.append(
            Entity(
                id=uuid4(),
                code=code,
                classification=node_class.id,
                characteristics=Characteristics(values=values),
            )
        )
    a, b, c = nodes
    root = Assembly(id=uuid4(), code="root", entities=tuple(item.id for item in nodes))
    edges = tuple(
        Relationship(id=uuid4(), source=root.id, target=node.id, classification=link.id)
        for node in nodes
    )
    root = Assembly.from_data(
        {**root.to_data(), "relationships": [str(e.id) for e in edges]}
    )
    assemblies = [root]
    if overlap:
        assemblies.append(Assembly(id=uuid4(), code="other", entities=(b.id,)))
    local = Value(
        id=uuid4(),
        key="net",
        kind="measurement",
        measure=measure.id,
        quantity=Quantity(magnitude=777, units="meter ** 2"),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
        definitions=Definitions(measures=(measure,), taxonomies=(taxonomy,)),
        system=System(
            entities=tuple(nodes),
            assemblies=tuple(assemblies),
            relationships=edges,
            formulations=(Formulation(id=uuid4(), values=(local,)),),
        ),
    )
    return model, root, a, b, c, edges, measure


def reduction(
    *,
    select=None,
    reducer=sum_quantities,
    require_complete=True,
    contributors=None,
    units="meter ** 2"
):
    return Reduction(
        select=select or select_value("net"),
        reducer=reducer,
        units=units,
        contributors=contributors or (lambda entity: not isinstance(entity, Assembly)),
        require_complete=require_complete,
    )


def revise(model, edit):
    data = model.system.to_data()
    edit(data)
    return model.revise(Update(system=System.from_data(data)))


def test_model_selection_modes_and_stable_order():
    model, root, a, b, c, edges, _ = fixture(overlap=True)
    view = View(model, assembly=root.id)
    assert tuple(item.id for item in view.entities) == (a.id, b.id, c.id, root.id)
    assert view.entity(root.id) is model.entity(root.id)
    assert root.id not in {item.id for item in model.system.entities}
    assert view.relationships == edges
    assert View(model, entities=(b.id, root.id, a.id)).relationships == edges[:2]
    assert View(model, relationships=(edges[1].id,)).entities == (
        model.entity(b.id),
        model.entity(root.id),
    )
    assert View(model, entities=()).entities == ()
    assert View(model, relationships=()).relationships == ()
    assert len(View(model).entities) == 5
    assert view.roots == (model.entity(root.id),)
    assert view.leaves == (model.entity(a.id), model.entity(b.id), model.entity(c.id))
    assert view.successors(root.id) == view.leaves
    assert view.predecessors(b.id) == view.roots
    assert view.is_arborescence
    with pytest.raises((FrozenInstanceError, AttributeError)):
        view.model = model


@pytest.mark.parametrize("kind", ["entity", "relationship"])
def test_lookup_scope_and_strict_uuid_errors(kind):
    model, root, a, b, c, edges, _ = fixture()
    view = View(model, entities=(a.id,))
    method = getattr(view, kind)
    id = b.id if kind == "entity" else edges[0].id
    wrong = edges[0].id if kind == "entity" else a.id
    with pytest.raises(SelectionError):
        method(id)
    with pytest.raises(MissingReferenceError):
        method(uuid4())
    with pytest.raises(ReferenceTypeError):
        method(wrong)
    with pytest.raises(TypeError):
        method(str(id))


def test_explicit_endpoint_and_assembly_validation():
    model, root, a, b, c, edges, _ = fixture()
    with pytest.raises(SelectionError, match="endpoint"):
        View(model, entities=(a.id,), relationships=(edges[0].id,))
    with pytest.raises(SelectionError, match="mutually exclusive"):
        View(model, entities=(), assembly=root.id)
    with pytest.raises(ReferenceTypeError):
        View(model, assembly=a.id)
    with pytest.raises(TypeError):
        View(model, entities=("a",))
    with pytest.raises(TypeError):
        View(object())
    with pytest.raises(TypeError):
        View(model).aggregate(object())


@pytest.mark.parametrize("argument", ["entities", "relationships"])
@pytest.mark.parametrize("invalid", ["", b"", False])
def test_empty_wrong_type_selectors_are_not_empty_selections(argument, invalid):
    model, *_ = fixture()
    with pytest.raises(TypeError):
        View(model, **{argument: invalid})


def test_filter_keeps_selection_and_removes_incident_edges():
    model, root, a, b, c, edges, _ = fixture()
    view = View(model, assembly=root.id).filter(
        predicate=lambda entity: entity.id != b.id
    )
    assert view.relationships == (edges[0], edges[2])
    assert view.successors(root.id) == (model.entity(a.id), model.entity(c.id))
    with pytest.raises(TypeError):
        view.filter(predicate=lambda entity: 1)
    with pytest.raises(MissingReferenceError):
        view.filter(entity_classification=uuid4())


def test_membership_and_relationship_direction_are_distinct():
    model, root, a, b, c, edges, _ = fixture(overlap=True)
    assert entities_in(model, root.id) == (
        model.entity(a.id),
        model.entity(b.id),
        model.entity(c.id),
    )
    assert relationships_in(model, root.id) == edges
    assert tuple(x.code for x in containing_assemblies(model, b.id)) == (
        "root",
        "other",
    )
    empty_edges = View(model, entities=(root.id, a.id, b.id, c.id), relationships=())
    assert empty_edges.successors(root.id) == ()
    hierarchy = Hierarchy.from_membership(empty_edges, root=root.id)
    assert hierarchy.children(root.id) == (a.id, b.id, c.id)
    assert hierarchy.kind == "membership"
    assert not empty_edges.is_arborescence
    for func in (entities_in, relationships_in):
        with pytest.raises(ReferenceTypeError):
            func(model, a.id)
    with pytest.raises(TypeError):
        entities_in(model, root.id, recursive=1)


def test_nested_membership_deduplicates_but_hierarchy_rejects_shared_child():
    model, root, a, b, c, edges, _ = fixture(overlap=True)
    other = model.system.assemblies[1]
    outer = Assembly(id=uuid4(), code="outer", entities=(root.id, other.id))
    model = revise(model, lambda data: data["assemblies"].append(outer.to_data()))
    members = entities_in(model, outer.id, recursive=True)
    assert tuple(x.id for x in members) == (a.id, b.id, c.id, root.id, other.id)
    assert tuple(
        x.code for x in containing_assemblies(model, b.id, recursive=True)
    ) == ("root", "other", "outer")
    view = View(model, entities=(outer.id, *(x.id for x in members)), relationships=())
    with pytest.raises(HierarchyError) as error:
        Hierarchy.from_membership(view, root=outer.id)
    assert error.value.code == "multiple_parents" and error.value.ids == (b.id,)
    selected = View(
        model, entities=(outer.id, root.id, a.id, b.id, c.id), relationships=()
    )
    tree = Hierarchy.from_membership(selected, root=outer.id)
    assert tree.preorder() == (outer.id, root.id, a.id, b.id, c.id)
    assert tree.postorder() == (a.id, b.id, c.id, root.id, outer.id)
    assert tree.parent(outer.id) is None and tree.parent(b.id) == root.id


@pytest.mark.parametrize(
    "case,code",
    [
        ("empty", "empty"),
        ("disconnected", "disconnected"),
        ("cycle", "cycle"),
        ("parallel", "parallel_edges"),
        ("multiple", "multiple_parents"),
    ],
)
def test_hierarchy_rejects_ambiguous_topology(case, code):
    model, root, a, b, c, edges, _ = fixture()
    if case == "empty":
        view = View(model, entities=())
    elif case == "disconnected":
        view = View(model, entities=(a.id, b.id), relationships=())
    else:
        extra = {
            "id": str(uuid4()),
            "source": str(root.id if case == "parallel" else b.id),
            "target": str(a.id if case != "cycle" else root.id),
            "classification": str(edges[0].classification),
        }
        model = revise(model, lambda data: data["relationships"].append(extra))
        view = View(model)
    with pytest.raises(HierarchyError) as error:
        Hierarchy.from_relationships(view)
    assert error.value.code == code
    assert not view.is_arborescence


def test_singleton_is_tree_and_hierarchy_is_immutable():
    model, root, a, b, c, edges, _ = fixture()
    tree = Hierarchy.from_relationships(View(model, entities=(a.id,)))
    assert tree.root == a.id and tree.children(a.id) == ()
    assert tree.preorder() == tree.postorder() == (a.id,)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        tree.root = b.id
    with pytest.raises(TypeError):
        tree._children[a.id] = (b.id,)
    with pytest.raises(SelectionError):
        tree.parent(b.id)


def test_reduction_selects_value_key_not_measure_and_preserves_model():
    model, root, a, b, c, edges, measure = fixture()
    before = model.to_data()
    view = View(model, assembly=root.id)
    result = view.aggregate(reduction(select=select_value("net", measure=measure.id)))
    assert result.root_value.magnitude == 30
    assert result[c.id].magnitude == 0
    assert result.coverage(root.id).complete
    assert result.coverage(root.id).selected == (a.id, b.id, c.id)
    assert result.value_ids[a.id] == a.characteristics.values[0].id
    gross = view.aggregate(reduction(select=select_value("gross", measure=measure.id)))
    assert gross.root_value.magnitude == 300
    assert model.to_data() == before
    with pytest.raises(TypeError):
        result.value_ids[a.id] = uuid4()
    with pytest.raises(AttributeError):
        result.root_value.magnitude = 999


def test_missing_values_and_known_subtotal_do_not_become_zero():
    model, root, a, b, c, edges, _ = fixture(missing=True)
    view = View(model, assembly=root.id)
    strict = view.aggregate(reduction())
    assert strict.root_value is None and strict.known_subtotal(root.id).magnitude == 10
    assert strict.coverage(root.id).missing == (b.id,)
    assert strict.value(b.id) is None and strict.value(c.id).magnitude == 0
    assert b.id in strict.value_ids  # unresolved content still has an identity
    assert view.aggregate(reduction(require_complete=False)).root_value.magnitude == 10
    absent = view.aggregate(reduction(select=select_value("absent")))
    assert absent.root_value is None and absent.known_subtotal(root.id) is None
    assert not absent.value_ids
    empty = view.aggregate(
        Reduction(
            select=select_value("net"),
            reducer=sum_quantities,
            units="meter ** 2",
            contributors=lambda e: False,
        )
    )
    assert empty.coverage(root.id).status == "empty" and empty.root_value is None


def test_mean_reduces_raw_contributors_not_subtree_means():
    model, root, a, b, c, edges, _ = fixture(amounts=(10, 20, 90))

    # Unequal subtrees: root -> a -> b, root -> c; eligible a, b, c.
    def edit(data):
        data["relationships"][1]["source"] = str(a.id)

    model = revise(model, edit)
    view = View(model)
    mean = view.aggregate(reduction(reducer=mean_quantities))
    assert mean.root_value.magnitude == 40 and mean.value(a.id).magnitude == 15
    assert view.aggregate(reduction(reducer=min_quantity)).root_value.magnitude == 10
    assert view.aggregate(reduction(reducer=max_quantity)).root_value.magnitude == 90
    with pytest.raises(AggregationError):
        mean.known_subtotal(root.id)


def test_unit_conversion_and_incompatible_results():
    model, root, a, b, c, edges, _ = fixture()
    result = View(model).aggregate(reduction(units="centimeter ** 2"))
    assert result.root_value.magnitude == pytest.approx(300000)
    with pytest.raises(UnitError):
        View(model).aggregate(reduction(units="second"))
    with pytest.raises(UnitError):
        View(model).aggregate(
            reduction(reducer=lambda values: Quantity(magnitude=1, units="AUD"))
        )


def test_revision_pinning_and_stale_selector_rejection():
    model, root, a, b, c, edges, _ = fixture()
    changed = revise(
        model,
        lambda data: data["entities"][0]["characteristics"]["values"][0][
            "quantity"
        ].update(magnitude=50),
    )
    assert View(model).aggregate(reduction()).root_value.magnitude == 30
    assert View(changed).aggregate(reduction()).root_value.magnitude == 70
    assert select_value("net")(changed, a).quantity.magnitude == 50
    with pytest.raises(SelectionError):
        View(changed).aggregate(
            reduction(select=lambda m, e: a.characteristics.values[0])
        )
    assert (
        View(codec.loads(codec.dumps(changed), kind=Model))
        .aggregate(reduction())
        .root_value.magnitude
        == 70
    )


@pytest.mark.parametrize("kind", ["other_owner", "formulation", "wrong_measure"])
def test_selector_cannot_escape_owner_or_measure(kind):
    model, root, a, b, c, edges, measure = fixture()
    if kind == "other_owner":
        selector = lambda m, e: b.characteristics.values[0]
    elif kind == "formulation":
        selector = lambda m, e: model.system.formulations[0].values[0]
    else:
        other = Measure(id=uuid4(), code="other", name="Other", units="meter ** 2")
        model = model.revise(
            Update(
                definitions=Definitions(
                    measures=(measure, other), taxonomies=model.definitions.taxonomies
                )
            )
        )
        selector = select_value("net", measure=other.id)
    with pytest.raises(SelectionError):
        View(model).aggregate(reduction(select=selector))


@pytest.mark.parametrize("failure", ["selector", "reducer", "contributors"])
def test_invalid_callback_results_are_not_silently_used(failure):
    model, *_ = fixture()
    kw = (
        {"select": lambda m, e: 1}
        if failure == "selector"
        else (
            {"reducer": lambda values: None}
            if failure == "reducer"
            else {"contributors": lambda e: 1}
        )
    )
    with pytest.raises(TypeError):
        View(model).aggregate(reduction(**kw))


def test_reducers_reject_empty_mixed_and_overflow_quantities():
    with pytest.raises(AggregationError):
        sum_quantities(())
    with pytest.raises(AggregationError):
        sum_quantities(
            (Quantity(magnitude=1, units="m"), Quantity(magnitude=1, units="cm"))
        )
    with pytest.raises(AggregationError):
        sum_quantities(
            (Quantity(magnitude=1e308, units="m"), Quantity(magnitude=1e308, units="m"))
        )


def test_imports_are_lightweight():
    script = """
import sys
import rangekeeper.graph as graph
for prefix in ('pint','numpy','networkx','pandas','pyomo','highspy','matplotlib','specklepy','rangekeeper.legacy','rangekeeper.graph.graph'):
    assert not any(name==prefix or name.startswith(prefix+'.') for name in sys.modules),prefix
from rangekeeper import Model
from rangekeeper.model import Metadata
from uuid import uuid4
model=Model.create(metadata=Metadata(id=uuid4(),schema_version='0.5.0'))
assert graph.View(model).entities==()
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_exact_classification_filters_do_not_expand_descendants():
    model, root, a, b, c, edges, _ = fixture()
    view = View(model)
    assert view.filter(entity_classification=a.classification).entities == (
        model.entity(a.id),
        model.entity(b.id),
        model.entity(c.id),
    )
    assert view.filter(entity_classification=a.classification).relationships == ()
    parent = model.definitions.taxonomies[0].classifications[0]
    assert view.filter(entity_classification=parent.id).entities == ()
    assert (
        view.filter(relationship_classification=edges[0].classification).relationships
        == edges
    )
    assert view.filter(relationship_classification=a.classification).relationships == ()
    with pytest.raises(ReferenceTypeError):
        view.filter(entity_classification=model.definitions.measures[0].id)


def test_membership_root_must_be_an_explicit_selected_uuid():
    model, root, a, b, c, edges, _ = fixture()
    view = View(model, assembly=root.id)
    with pytest.raises(TypeError):
        Hierarchy.from_membership(view, root=None)
    with pytest.raises(HierarchyError) as error:
        Hierarchy.from_membership(view, root=a.id)
    assert error.value.code == "root_mismatch"


def test_aggregation_requires_a_deliberate_parent_contributor_policy():
    model, root, a, b, c, edges, _ = fixture()
    # Default includes the unmeasured Assembly, so it must not silently report complete.
    result = View(model).aggregate(
        Reduction(
            select=select_value("net"), reducer=sum_quantities, units="meter ** 2"
        )
    )
    assert result.root_value is None and result.coverage(root.id).missing == (root.id,)
    assert result.known_subtotal(root.id).magnitude == 30


def test_custom_reducer_normalizes_returned_units_and_errors_remain_visible():
    model, root, a, b, c, edges, _ = fixture()
    result = View(model).aggregate(
        reduction(
            reducer=lambda values: Quantity(magnitude=10000, units="centimeter ** 2")
        )
    )
    assert result.root_value.magnitude == 1 and result.root_value.units == "meter ** 2"

    def broken(values):
        raise RuntimeError("caller reducer failed")

    with pytest.raises(RuntimeError, match="caller reducer failed"):
        View(model).aggregate(reduction(reducer=broken))


def test_selector_validates_measure_even_when_local_key_is_absent():
    model, root, a, b, c, edges, _ = fixture()
    with pytest.raises(MissingReferenceError):
        select_value("absent", measure=uuid4())(model, a)
    with pytest.raises(ReferenceTypeError):
        select_value("absent", measure=model.definitions.taxonomies[0].id)(model, a)
