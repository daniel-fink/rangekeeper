"""Legacy projection keeps row identities alongside values."""

from uuid import uuid5, NAMESPACE_URL
from rangekeeper.legacy.graph import (
    Classification,
    Definitions,
    Entity,
    Graph,
    Relationship,
    Taxonomy,
)


def uid(key):
    return uuid5(NAMESPACE_URL, "rk-evidence-test:" + key)


def test_graph_projection_identity_and_arborescence_order():
    from rangekeeper.legacy.graph.table import Table

    kind = Classification(id=uid("contains"), code="contains", name="Contains")
    taxonomy = Taxonomy(
        id=uid("taxonomy"), code="test", name="Test", classifications=(kind,)
    )
    root, child = (
        Entity(id=uid("root"), name="Root"),
        Entity(id=uid("child"), name="Child"),
    )
    graph = Graph(
        definitions=Definitions(taxonomies=(taxonomy,)),
        entities=(child, root),
        relationships=(
            Relationship(source_id=root.id, target_id=child.id, classification=kind),
        ),
    )
    plain = Table.from_view(graph.view(), fields=("name",))
    assert tuple(row.id for row in plain.rows) == (child.id, root.id)
    assert plain.columns == ("name",)
    tree = Table.from_arborescence(graph.view())
    assert tuple(row.id for row in tree.rows) == (root.id, child.id)
    assert tree.column("entity_id") == tuple(row.id for row in tree.rows)
