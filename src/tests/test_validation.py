import rangekeeper as rk


def valid_graph():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    classification = rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="connects", name="Connects")
    relationship = rk.graph.Relationship(
        "source", "target", classification, relationship_id="relationship"
    )
    assembly = rk.graph.Assembly(
        entity_id="assembly",
        entities=(source, target),
        relationships=(relationship,),
    )
    graph = rk.graph.Graph()
    graph.assemblies.add(assembly)
    return graph, assembly, source, target, relationship


def test_validation_result_is_typed_and_truthy_when_valid():
    graph, *_ = valid_graph()

    result = graph.validate()

    assert isinstance(result, rk.graph.ValidationResult)
    assert result.issues == ()
    assert result.is_valid
    assert result


def test_validation_reports_multiple_registry_and_graph_violations():
    graph, _, source, _, relationship = valid_graph()
    graph._graph.nodes["source"]["entity"] = rk.graph.Entity(entity_id="source")
    graph._graph.add_node("orphan")
    graph._graph.remove_edge("source", "target", key="relationship")
    graph._graph.add_edge(
        "target", "source", key="wrong-key", relationship=relationship
    )

    result = graph.validate()
    codes = {issue.code for issue in result.issues}

    assert not result.is_valid
    assert not result
    assert "entity.node_object" in codes
    assert "node.entity_missing" in codes
    assert "edge.key" in codes
    assert "edge.endpoints" in codes
    assert "relationship.edge_missing" in codes
    assert graph.entities["source"] is source


def test_validation_reports_noncanonical_assembly_contents():
    graph, assembly, _, target, relationship = valid_graph()
    noncanonical = rk.graph.Entity(entity_id="source")
    assembly._entities = {noncanonical, target}

    result = graph.validate()
    codes = {issue.code for issue in result.issues}

    assert "assembly.canonical_entity" in codes
    assert graph.relationships["relationship"] is relationship


def test_validation_survives_malformed_private_assembly_state():
    graph, assembly, *_ = valid_graph()
    assembly._entities = {"not-an-entity"}
    assembly._relationships = {"not-a-relationship"}

    result = graph.validate()
    codes = {issue.code for issue in result.issues}

    assert "assembly.contents" in codes
    assert "assembly.entity_type" in codes
    assert "assembly.relationship_type" in codes
