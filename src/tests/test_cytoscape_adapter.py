import json
from copy import deepcopy

import pytest

from rangekeeper.graph import (
    Assembly,
    Classification,
    Definitions,
    Entity,
    Graph,
    Relationship,
    Taxonomy,
)
from rangekeeper.graph.adapter.cytoscape import project, validate_document, write_viewer


def fixture():
    a, b = (
        Entity(code="a", name="</script><img src=x onerror=alert(1)>"),
        Entity(code="b"),
    )
    x, y = (
        Classification(code="links", name="First"),
        Classification(code="links", name="Second"),
    )
    defs = Definitions(
        taxonomies=(
            Taxonomy(code="one", name="First taxonomy", classifications=(x,)),
            Taxonomy(code="two", name="Second taxonomy", classifications=(y,)),
        )
    )
    edges = (
        Relationship.between(a, b, classification=x),
        Relationship.between(b, a, classification=y),
    )
    box = Assembly(
        code="box", entity_ids={a.id, b.id}, relationship_ids={e.id for e in edges}
    )
    return Graph(definitions=defs, entities=(box, a, b), relationships=edges), box, a, b


def test_projection_uses_uuids_preserves_membership_and_exports_view(tmp_path):
    graph, box, a, b = fixture()
    document = project(graph, "Example")
    validate_document(document)
    assert (
        len({e["data"]["type"] for e in document["elements"] if "source" in e["data"]})
        == 2
    )
    assert document["diagnostics"]["ambiguousParents"] == []
    assert document["assemblies"][str(box.id)]["entities"] == sorted([
        str(a.id),
        str(b.id),
    ])
    view = project(graph.view(entities=(box, a)), "View")
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
