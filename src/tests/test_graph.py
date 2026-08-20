import rangekeeper as rk


def test_graph_package_exports_phase_one_domain_classes():
    assert rk.graph.Entity.__module__ == "rangekeeper.graph.entity"
    assert rk.graph.Assembly.__module__ == "rangekeeper.graph.assembly"
    assert rk.graph.Relationship.__module__ == "rangekeeper.graph.relationship"
    assert rk.graph.Classification.__module__ == ("rangekeeper.graph.classification")
    assert rk.graph.Characteristics.__module__ == ("rangekeeper.graph.characteristics")
    assert rk.graph.Provenance.__module__ == "rangekeeper.graph.provenance"


def test_graph_package_exports_phase_two_model_types():
    assert rk.graph.Model.__module__ == "rangekeeper.graph.model"
    assert rk.graph.View.__module__ == "rangekeeper.graph.view"
    assert rk.graph.EntityRegistry.__module__ == "rangekeeper.graph.registry"
    assert rk.graph.RelationshipRegistry.__module__ == "rangekeeper.graph.registry"
    assert rk.graph.AssemblyRegistry.__module__ == "rangekeeper.graph.registry"
    assert rk.graph.TaxonomyRegistry.__module__ == "rangekeeper.graph.registry"
    assert rk.graph.ValidationResult.__module__ == ("rangekeeper.graph.validation")


def test_phase_one_domain_classes_do_not_inherit_from_speckle_base():
    from specklepy.objects import Base

    domain_classes = (
        rk.graph.Entity,
        rk.graph.Assembly,
        rk.graph.Relationship,
        rk.graph.Classification,
        rk.graph.Characteristics,
        rk.graph.Provenance,
    )

    assert all(not issubclass(domain_class, Base) for domain_class in domain_classes)
