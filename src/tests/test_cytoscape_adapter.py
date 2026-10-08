import json
from copy import deepcopy

import pytest

from uuid import uuid4
from rangekeeper.model.system import View
from rangekeeper.model import (
    Model,
    Metadata,
    System,
    Assembly,
    Classification,
    Definitions,
    Entity,
    Relationship,
    Taxonomy,
)
from rangekeeper.adapters.cytoscape import project, validate_document, write_viewer


def fixture():
    a, b = (
        Entity(id=uuid4(), code="a", name="</script><img src=x onerror=alert(1)>"),
        Entity(id=uuid4(), code="b"),
    )
    x, y = (
        Classification(id=uuid4(), code="links", name="First"),
        Classification(id=uuid4(), code="links", name="Second"),
    )
    defs = Definitions(
        taxonomies=(
            Taxonomy(
                id=uuid4(), code="one", name="First taxonomy", classifications=(x,)
            ),
            Taxonomy(
                id=uuid4(), code="two", name="Second taxonomy", classifications=(y,)
            ),
        )
    )
    edges = (
        Relationship(id=uuid4(), source=a.id, target=b.id, classification=x.id),
        Relationship(id=uuid4(), source=b.id, target=a.id, classification=y.id),
    )
    box = Assembly(
        id=uuid4(),
        code="box",
        entities=(a.id, b.id),
        relationships=tuple(e.id for e in edges),
    )
    return (
        Model.create(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
            definitions=defs,
            system=System(assemblies=(box,), entities=(a, b), relationships=edges),
        ),
        box,
        a,
        b,
    )


def test_projection_uses_uuids_preserves_membership_and_exports_view(tmp_path):
    graph, box, a, b = fixture()
    document = project(graph, "Example")
    validate_document(document)
    assert (
        len({e["data"]["type"] for e in document["elements"] if "source" in e["data"]})
        == 2
    )
    assert document["diagnostics"]["ambiguousParents"] == []
    assert document["assemblies"][str(box.id)]["entities"] == sorted(
        [
            str(a.id),
            str(b.id),
        ]
    )
    view = project(View(graph, entities=(box.id, a.id)), "View")
    assert view["assemblies"][str(box.id)]["entities"] == [str(a.id)]
    assert set(view["details"]) == {str(a.id), str(box.id)}
    text = write_viewer([document], tmp_path / "viewer.html").read_text()
    payload = text.split('<script id="graph-data" type="application/json">')[1].split(
        "</script>"
    )[0]
    assert "<img" not in payload and "\\u003cimg" in payload
    assert json.loads(payload)["datasets"][0]["elements"] == document["elements"]
    assert "<script src=" not in text and "connect-src 'none'" in text


def test_invalid_display_documents_fail_before_export(tmp_path):
    graph, box, _a, _b = fixture()
    doc = project(graph, "Example")
    broken = deepcopy(doc)
    broken["assemblies"][str(box.id)]["entities"].append(str(box.id))
    with pytest.raises(ValueError, match="cycle"):
        write_viewer([broken], tmp_path / "bad.html")
    broken = deepcopy(doc)
    broken["reviewItems"] = [{"targets": ["absent"]}]
    with pytest.raises(ValueError, match="Finding target"):
        write_viewer([broken], tmp_path / "bad.html")
    assert not (tmp_path / "bad.html").exists()
    with pytest.raises(ValueError, match="Unknown viewer configuration"):
        project(graph, "Example", {"elements": []})


def test_projection_materializes_each_selection_once(monkeypatch):
    model, box, a, _ = fixture()
    view = View(model, entities=(box.id, a.id))
    expected = project(view, "Selected")
    calls = {"entities": 0, "relationships": 0}
    for name in calls:
        original = getattr(View, name).fget

        def counted(self, name=name, original=original):
            calls[name] += 1
            return original(self)

        monkeypatch.setattr(View, name, property(counted))
    assert project(view, "Selected") == expected
    assert calls == {"entities": 1, "relationships": 1}
