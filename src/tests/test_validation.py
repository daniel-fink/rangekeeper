import rangekeeper as rk


def valid_model():
    source = rk.graph.Entity(entity_id="source")
    target = rk.graph.Entity(entity_id="target")
    classification = rk.graph.Classification(code="connects", name="Connects")
    relationship = rk.graph.Relationship(
        "source", "target", classification, relationship_id="relationship"
    )
    assembly = rk.graph.Assembly(
        entity_id="assembly",
        entities=(source, target),
        relationships=(relationship,),
    )
    model = rk.graph.Model()
    model.add_assembly(assembly)
    return model, assembly, source, target, relationship


def test_validation_result_is_typed_and_truthy_when_valid():
    model, *_ = valid_model()

    result = model.validate()

    assert isinstance(result, rk.graph.ValidationResult)
    assert result.issues == ()
    assert result.is_valid
    assert result


def test_validation_reports_multiple_registry_and_graph_violations():
    model, _, source, _, relationship = valid_model()
    model._graph.nodes["source"]["entity"] = rk.graph.Entity(entity_id="source")
    model._graph.add_node("orphan")
    model._graph.remove_edge("source", "target", key="relationship")
    model._graph.add_edge(
        "target", "source", key="wrong-key", relationship=relationship
    )

    result = model.validate()
    codes = {issue.code for issue in result.issues}

    assert not result.is_valid
    assert not result
    assert "entity.node_object" in codes
    assert "node.entity_missing" in codes
    assert "edge.key" in codes
    assert "edge.endpoints" in codes
    assert "relationship.edge_missing" in codes
    assert model.entity("source") is source


def test_validation_reports_noncanonical_assembly_contents():
    model, assembly, _, target, relationship = valid_model()
    noncanonical = rk.graph.Entity(entity_id="source")
    assembly._entities = {noncanonical, target}

    result = model.validate()
    codes = {issue.code for issue in result.issues}

    assert "assembly.canonical_entity" in codes
    assert model.relationship("relationship") is relationship


def test_validation_survives_malformed_private_assembly_state():
    model, assembly, *_ = valid_model()
    assembly._entities = {"not-an-entity"}
    assembly._relationships = {"not-a-relationship"}

    result = model.validate()
    codes = {issue.code for issue in result.issues}

    assert "assembly.contents" in codes
    assert "assembly.entity_type" in codes
    assert "assembly.relationship_type" in codes
