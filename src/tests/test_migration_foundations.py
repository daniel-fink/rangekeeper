"""Explicit format conversion and source-workflow property acceptance."""

from copy import deepcopy
from pathlib import Path
import importlib.util
import json
from uuid import uuid4

import pytest
from rangekeeper import Model
from rangekeeper.model.content import decode
from rangekeeper.migration import convert_graph, upgrade_model
from rangekeeper.workflow import load, run
from tests.test_graph_json import example
from rangekeeper.graph.adapter.json import dumps

ROOT = Path(__file__).resolve().parents[2]


def test_graph_upgrade_preserves_identity_properties_and_provenance():
    old = example()
    text = dumps(old)
    result = convert_graph(text)
    assert not result.issues and result.model is not None
    model = result.model
    assert len(model.system.assemblies) == 1 and len(model.system.entities) == 1
    parent, child = old.entities
    assert model.entity(parent.id).entities == (child.id,)
    reading = child.measurements["length"]
    feature = child.features["payload"]
    assert model.value(reading.id).quantity.magnitude == 0
    restored = decode(model.value(feature.id).content)
    assert restored == feature.value and type(restored["tuple"]) is tuple
    assert model.provenance.facts[0].target == reading.id
    assert (
        model.provenance.facts[0].reconciliation.selected
        == old.provenance.facts[0].reconciliation.selected.id
    )
    assert all(a == b for a, b in result.identity_map)
    assert dumps(old) == text


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(version=2),
        lambda x: x["objects"].append(x["objects"][0]),
        lambda x: x["root"]["fields"].update(unknown=True),
        lambda x: x["objects"].pop(),
    ],
)
def test_graph_upgrade_never_publishes_partial_output(change):
    raw = json.loads(dumps(example()))
    change(raw)
    result = convert_graph(json.dumps(raw))
    assert result.model is None and result.issues and result.source_sha256


def test_model_upgrade_requires_explicit_new_revision():
    old = {"metadata": {"id": str(uuid4()), "schema_version": "0.3.0"}}
    original = deepcopy(old)
    model = upgrade_model(old)
    assert old == original and str(model.id) != old["metadata"]["id"]
    assert str(model.metadata.previous) == old["metadata"]["id"]
    with pytest.raises(ValueError):
        Model.from_data(old)
    with pytest.raises(ValueError):
        upgrade_model(model.to_data())


@pytest.mark.parametrize("domain", ["accommodation", "equipment"])
def test_repository_workflow_examples_retain_property_evidence(tmp_path, domain):
    spec = importlib.util.spec_from_file_location(
        "example_inputs", ROOT / "src/examples/workflow/create_inputs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.create(tmp_path, domain)
    outcome = run(
        load(ROOT / "src/examples/workflow" / domain / "spec"), input_root=tmp_path
    )
    assert outcome.output is not None, outcome.diagnostics
    model = outcome.output.model
    props = [
        v
        for e in model.system.entities
        for v in e.characteristics.values
        if v.kind == "property"
    ]
    assert len(props) == 3
    assert {decode(p.content) for p in props} == (
        {"2B", "unknown"} if domain == "accommodation" else {"2C", "unknown"}
    )
    assert all(any(f.target == p.id for f in model.provenance.facts) for p in props)


def test_converter_cli_retains_report_and_refuses_overwrite(tmp_path):
    import subprocess
    import sys

    source = tmp_path / "old.json"
    source.write_text(dumps(example()))
    out = tmp_path / "converted"
    command = [sys.executable, "-m", "rangekeeper.migration", str(source), str(out)]
    subprocess.run(command, check=True, capture_output=True)
    report = json.loads((out / "report.json").read_text())
    assert (
        report["model"] == "model.json"
        and report["identity_map"]
        and not report["issues"]
    )
    before = (out / "model.json").read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert (out / "model.json").read_bytes() == before


def test_quantity_feature_is_reported_not_silently_changed_to_a_mapping():
    raw = json.loads(dumps(example()))
    feature = next(item for item in raw["objects"] if item["type"] == "Feature")
    feature["fields"]["value"] = {"quantity": [{"float": (1.0).hex()}, "meter"]}
    result = convert_graph(json.dumps(raw))
    assert result.model is None and "unsupported property type" in result.issues[0]
