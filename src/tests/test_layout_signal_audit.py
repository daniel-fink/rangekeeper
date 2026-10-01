"""The spike inventory preserves evidence without promoting it to layout intent."""

import json
import runpy
import sys
from pathlib import Path

import pytest

from rangekeeper.graph import Assembly, Characteristics, Entity, Feature, Graph
from rangekeeper.graph.adapter import json as graph_json
from rangekeeper.graph.provenance import (
    Claim,
    ClaimKind,
    Fact,
    Location,
    Method,
    Provenance,
    Source,
)

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/audit_layout_signals.py"
inventory = runpy.run_path(str(SCRIPT))["inventory"]


def test_inventory_keeps_shared_identity_and_missing_evidence():
    node = Entity(
        code="shared",
        characteristics=Characteristics(
            features={
                "zero": Feature(name="zero", value=0),
                "unknown": Feature(name="unknown", value=None),
            }
        ),
    )
    left = Assembly.of(entities=(node,), code="left")
    right = Assembly.of(entities=(node,), code="right")
    graph = Graph(entities=(left, right, node))
    before = graph_json.dumps(graph)
    report = inventory(graph)
    record = next(e for e in report["objects"] if e["id"] == str(node.id))
    assert report["counts"]["shared_direct_members"] == 1
    assert set(record["parents"]) == {str(left.id), str(right.id)}
    assert record["features"]["zero"]["value"] == 0
    assert record["features"]["unknown"]["value"] is None
    assert record["features"]["zero"]["evidence"]["status"] == "missing"
    assert "direction" not in record
    assert graph_json.dumps(graph) == before


def test_inventory_retains_all_claim_support_and_deduplicates_locations():
    location = Location(
        source=Source(name="Synthetic", checksum="example"), reference={"cell": "A1"}
    )
    original = Claim(value=0, kind=ClaimKind.SOURCED, sources=(location,))
    derived = Claim(
        value=0,
        kind=ClaimKind.DERIVED,
        sources=(original, location),
        method=Method(code="synthetic-copy"),
    )
    feature = Feature(name="height", value=0)
    node = Entity(characteristics=Characteristics(features={"height": feature}))
    graph = Graph(
        entities=(node,),
        provenance=Provenance(
            facts=(Fact(target=feature, claims=(original, derived)),)
        ),
    )
    support = inventory(graph)["objects"][0]["features"]["height"]["evidence"]
    assert support["status"] == "determinate"
    assert {c["id"] for c in support["claims"]} == {str(original.id), str(derived.id)}
    assert len(support["locations"]) == 1
    assert support["locations"][0]["reference"] == {"cell": "A1"}


def test_cli_requires_completed_snapshot_and_never_replaces_report(
    tmp_path, monkeypatch
):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    graph_path = bundle / "graph.json"
    graph_path.write_text(graph_json.dumps(Graph(entities=(Entity(code="example"),))))
    frozen_review = {"decisions": [{"id": "original", "text": "Frozen evidence"}]}
    (bundle / "manifest.json").write_text(
        json.dumps({"review_specification": {"decisions": frozen_review}})
    )
    run_path = bundle / "run.json"
    run_path.write_text('{"complete": false}')
    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        sys, "argv", [str(SCRIPT), "--bundle", str(bundle), "--output", str(output)]
    )
    with pytest.raises(ValueError, match="not marked complete"):
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert not output.exists()
    run_path.write_text('{"complete": true}')
    before = graph_path.read_bytes()
    runpy.run_path(str(SCRIPT), run_name="__main__")
    report = output.read_bytes()
    assert json.loads(report)["frozen_review"] == frozen_review
    assert graph_path.read_bytes() == before
    with pytest.raises(FileExistsError):
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert output.read_bytes() == report
