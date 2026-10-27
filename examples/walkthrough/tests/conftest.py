from uuid import uuid4

import pytest
from helpers import plot


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Run in an empty folder and close the local display servers afterwards."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    for display in plot._displays.values():
        display.close()
    plot._displays.clear()


@pytest.fixture
def tree():
    """A two-entity View joined by one containment relationship."""
    from rangekeeper.model import (
        Classification,
        Definitions,
        Entity,
        Metadata,
        Model,
        Relationship,
        System,
        Taxonomy,
    )
    from rangekeeper.model.system import Hierarchy, View

    node = Classification(id=uuid4(), code="node", name="Node")
    contains = Classification(
        id=uuid4(), code="contains", name="Contains", parent=node.id
    )
    root = Entity(id=uuid4(), code="root", name="buildingA", classification=node.id)
    child = Entity(id=uuid4(), code="child", name="Child", classification=node.id)
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(
            taxonomies=(
                Taxonomy(
                    id=uuid4(),
                    code="entity",
                    name="Entity Types",
                    classifications=(node, contains),
                ),
            )
        ),
        system=System(
            entities=(root, child),
            relationships=(
                Relationship(
                    id=uuid4(),
                    source=root.id,
                    target=child.id,
                    classification=contains.id,
                ),
            ),
        ),
    )
    view = View(model)
    return Hierarchy(view), root, child
