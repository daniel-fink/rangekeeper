"""Model-backed projections and source-building migration acceptance."""

from dataclasses import replace
from pathlib import Path
import runpy
import subprocess
import sys
from uuid import uuid4

import pytest

from rangekeeper import Model
from rangekeeper.model import (
    Metadata,
    Definitions,
    Measure,
    System,
    Entity,
    Assembly,
    Characteristics,
    Value,
    Quantity,
    Label,
    Classification,
    Taxonomy,
)
from rangekeeper.model.characteristics import value
from rangekeeper.graph import View, Hierarchy
from rangekeeper.graph.errors import SelectionError
from rangekeeper.graph.projection import (
    FieldColumn,
    ValueColumn,
    LabelColumn,
    to_table,
    to_tree_table,
)
from rangekeeper.errors import UnitError
from rangekeeper.io import json, yaml, MemoryStore, DirectoryStore
from rangekeeper.adapters.cytoscape import project, validate_document
from rangekeeper.workflow import load, run
from .test_workflow import example, rewrite


@pytest.fixture
def model():
    measure = Measure(id=uuid4(), code="area", name="Area", units="meter**2")
    kind = Classification(id=uuid4(), code="asset", name="Asset")
    taxonomy = Taxonomy(id=uuid4(), code="type", name="Type", classifications=(kind,))
    net = Value(
        id=uuid4(),
        key="net",
        kind="measurement",
        measure=measure.id,
        quantity=Quantity(magnitude=0, units="meter**2"),
    )
    gross = Value(
        id=uuid4(),
        key="gross",
        kind="measurement",
        measure=measure.id,
        quantity=Quantity(magnitude=2, units="meter**2"),
    )
    unresolved = Value(
        id=uuid4(), key="unknown", kind="measurement", measure=measure.id
    )
    entity = Entity(
        id=uuid4(),
        name="A",
        classification=kind.id,
        characteristics=Characteristics(
            values=(net, gross, unresolved),
            labels=(Label(id=uuid4(), key="use", classifications=(kind.id,)),),
        ),
    )
    first = Assembly(id=uuid4(), name="First", entities=(entity.id,))
    second = Assembly(id=uuid4(), name="Second", entities=(entity.id,))
    return Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.6.0"),
        definitions=Definitions(measures=(measure,), taxonomies=(taxonomy,)),
        system=System(entities=(entity,), assemblies=(first, second)),
    )


def test_value_projection_selects_local_keys_and_retains_zero(model):
    entity = model.system.entities[0]
    columns = [
        ValueColumn("net", "net", "centimeter**2"),
        ValueColumn("gross", "gross", "centimeter**2"),
        ValueColumn("unknown", "unknown", "meter**2"),
        ValueColumn("absent", "absent", "meter**2"),
        LabelColumn("use", "use"),
    ]
    before = model.to_data()
    table = to_table(View(model, entities=(entity.id,)), columns=columns)
    assert table.rows[0].id == entity.id
    assert table.column("net") == (0,)
    assert table.column("gross") == (20000,)
    assert table.column("unknown") == table.column("absent") == (None,)
    assert table.column("use") == ((entity.classification,),)
    assert value(entity.characteristics, "unknown") is not None
    assert value(entity.characteristics, "absent") is None
    assert model.to_data() == before


def test_projection_units_and_measure_assertions_are_checked(model):
    with pytest.raises(UnitError):
        to_table(View(model), columns=(ValueColumn("x", "net", "second"),))
    other = Measure(id=uuid4(), code="other", name="Other", units="meter**2")
    data = model.to_data()
    data["definitions"]["measures"].append(other.to_data())
    changed = Model.from_data(data)
    with pytest.raises(SelectionError):
        to_table(
            View(changed),
            columns=(ValueColumn("x", "net", "meter**2", measure=other.id),),
        )
    with pytest.raises(ValueError, match="duplicates"):
        to_table(
            View(model), columns=(FieldColumn("x", "name"), FieldColumn("x", "code"))
        )


def test_tree_projection_uses_selected_membership_and_revision(model):
    assembly = model.system.assemblies[0]
    hierarchy = Hierarchy.from_membership(
        View(model, assembly=assembly.id), root=assembly.id
    )
    table = to_tree_table(hierarchy)
    assert table.column("model_id") == (model.id, model.id)
    assert table.column("entity_id") == (assembly.id, model.system.entities[0].id)
    assert table.column("parent_id") == (None, assembly.id)


def test_shared_membership_does_not_duplicate_canonical_viewer_objects(model):
    document = project(model, "Overlapping assemblies")
    validate_document(document)
    entity = model.system.entities[0]
    assert document["modelId"] == str(model.id)
    assert (
        sum(item["data"]["id"] == str(entity.id) for item in document["elements"]) == 1
    )
    assert all(
        str(entity.id) in document["assemblies"][str(a.id)]["entities"]
        for a in model.system.assemblies
    )
    assert [m["code"] for m in document["details"][str(entity.id)]["measurements"]] == [
        "net",
        "gross",
        "unknown",
    ]


@pytest.mark.parametrize(
    "unsupported", ["feature", "missing_feature", "quantity_kind", "aggregation"]
)
def test_workflows_reject_unsupported_legacy_content_before_reading(
    tmp_path, unsupported
):
    root, docs = example(tmp_path)
    if unsupported == "feature":
        docs["model"]["templates"][0]["features"] = [
            {"name": "rich", "binding": {"value": "native content"}}
        ]
    elif unsupported == "missing_feature":
        docs["model"]["templates"][0]["measurements"][0]["on_unavailable"] = {
            "feature": "missing"
        }
    else:
        docs["model"]["measures"][0][unsupported] = "AREA"
    rewrite(root, docs)
    with pytest.raises(ValueError):
        load(root / "spec")


def test_version_one_workflow_requires_explicit_migration(tmp_path):
    root, docs = example(tmp_path)
    docs["model"]["version"] = 1
    rewrite(root, docs)
    with pytest.raises(ValueError, match="version 2"):
        load(root / "spec")


def test_workflow_multiple_values_per_measure_and_snapshot_storage(tmp_path):
    root, docs = example(tmp_path)
    docs["model"]["templates"][0]["measurements"].append(
        {"key": "gross", "measure": "size", "binding": {"value": 24}}
    )
    rewrite(root, docs)
    spec = load(root / "spec")
    outcome = run(spec, input_root=root / "inputs")
    assert outcome.output is not None, outcome.diagnostics
    model = outcome.output.model
    assert not hasattr(outcome.output, "graph")
    entity = next(e for e in model.system.entities if e.code == "A1")
    assert (
        value(entity.characteristics, "gross").measure
        == value(entity.characteristics, "size").measure
    )
    assert len(model.system.entities) == 3 and len(model.system.assemblies) == 2
    assert all(
        c.status == "agree" for c in outcome.output.checks if c.purpose == "invariant"
    )
    for codec in (json, yaml):
        restored = codec.loads(codec.dumps(model), kind=Model)
        assert restored.to_data() == model.to_data()
        for store in (
            MemoryStore(),
            DirectoryStore(tmp_path / (codec.__name__ + "-revisions")),
        ):
            store.put(restored)
            assert store.load_model(model.id).to_data() == model.to_data()
    with pytest.raises((AttributeError, TypeError)):
        entity.characteristics.values[0].key = "changed"


def test_new_consumer_imports_do_not_load_legacy_domain_or_solver():
    code = """
import sys
from rangekeeper import workflow, adapters, table, evidence, operation
from rangekeeper.workflow import run
from rangekeeper.adapters import document, excel, cytoscape
assert not any(n.startswith(('rangekeeper.legacy', 'rangekeeper.graph.graph', 'rangekeeper.graph.entity', 'rangekeeper.measure', 'pyomo', 'highspy', 'networkx', 'pandas')) for n in sys.modules)
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_workflow_to_real_scalar_executor(tmp_path):
    import importlib.util

    if any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")):
        pytest.skip("requires the optional execution extra")
    script = Path(__file__).resolve().parents[2] / "tools/workflow/scalar.py"
    summary = runpy.run_path(str(script))["run_example"](tmp_path / "example")
    assert summary["forward_gross"]["magnitude"] == 20
    assert summary["inverse_net"]["magnitude"] == 25
    assert (tmp_path / "example/workflow/model.json").is_file()
    assert (tmp_path / "example/workflow/viewer.html").is_file()


def test_source_dates_and_locations_survive_canonical_provenance():
    from datetime import date
    from rangekeeper import evidence
    from rangekeeper.workflow.provenance import ProvenanceBuilder
    from rangekeeper.model.provenance import locations

    source = evidence.Source(
        name="Schedule", checksum="abc", issued_at=date(2026, 10, 3)
    )
    observation = evidence.Claim.sourced(
        date(2026, 10, 2), at=evidence.Location(source=source, reference={"cell": "A1"})
    )
    entity = Entity(id=uuid4())
    builder = ProvenanceBuilder()
    support = builder.attach(
        entity,
        id=uuid4(),
        sources=(observation,),
        method=evidence.Method(code="test", version="1"),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.6.0"),
        system=System(entities=(entity,)),
        provenance=builder.finish(),
    )
    restored = json.loads(json.dumps(model), kind=Model)
    observed = next(c for c in restored.provenance.claims if c.id == observation.id)
    assert observed.content["value"] == ("date", "2026-10-02")
    assert restored.provenance.sources[0].issued_at == date(2026, 10, 3)
    assert restored.provenance.sources[0].to_data()["issued_at"] == "2026-10-03"
    assert locations(restored, support)[0].address["cell"] == "A1"


def test_direct_composition_rejects_features(tmp_path):
    from rangekeeper.workflow.composition import compose
    from rangekeeper.evidence import Claim, Method
    from rangekeeper.operation import Operation

    root, _ = example(tmp_path)
    spec = load(root / "spec")
    data = dict(spec.model)
    data["templates"] = ()
    data["objects"] = (
        {
            "id": "A",
            "kind": "entity",
            "classification": "item",
            "identity_kind": "item",
            "key": {"value": "A"},
            "name": "A",
            "features": [],
        },
    )
    method = Method(code="direct", version="1")
    with pytest.raises(ValueError, match="Unsupported Feature"):
        compose(
            data,
            {},
            Claim.asserted("settings", method=method),
            {},
            Operation(method=method, specification=data, inputs={}),
            namespace="urn:direct",
        )
