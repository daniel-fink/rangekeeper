"""Notebook boundary tested with synthetic storage groups."""

import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
import yaml

from rangekeeper.graph import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Feature,
    Graph,
    Taxonomy,
)
from rangekeeper.graph.adapter import json as graph_json
from rangekeeper.graph.adapter.cytoscape.layout.profile import prepare
from rangekeeper.graph.workflow import layout_review


def fixture(tmp_path):
    kind = Classification(code="shelf", name="Shelf")
    one, two = Entity(code="one"), Entity(code="two")
    a = Assembly(
        code="a",
        classification=kind,
        entity_ids=frozenset({one.id}),
        characteristics=Characteristics(
            features={"rank": Feature(name="rank", value=2)}
        ),
    )
    b = Assembly(
        code="b",
        classification=kind,
        entity_ids=frozenset({two.id}),
        characteristics=Characteristics(
            features={"rank": Feature(name="rank", value=1)}
        ),
    )
    root = Assembly(code="root", entity_ids=frozenset({a.id, b.id}))
    graph = Graph(
        entities=(one, two, a, b, root),
        definitions=Definitions(
            taxonomies=(Taxonomy(code="kinds", name="Kinds", classifications=(kind,)),)
        ),
    )
    profile = {
        "schema": "rk-layout-profile-v1",
        "canvas": {"width": 1200, "height": 1200},
        "footprints": {"node_width": 100, "node_height": 44, "assembly_min_width": 140},
        "grid_classifications": ["shelf"],
        "stack_order": {
            "classification": "shelf",
            "feature": "rank",
            "descending": True,
        },
        "signals": [],
        "weights": {
            "grid": 4,
            "direction": 3,
            "order": 6,
            "similarity": 3,
            "compactness": 1,
        },
        "rationales": {"grid": "Storage grid", "stack": "Storage stack"},
        "notes": ["Synthetic schematic"],
    }
    spec = tmp_path / "layout.yaml"
    spec.write_text(yaml.safe_dump(profile))
    directory = tmp_path / "build"
    directory.mkdir()
    graph_json.write(graph, directory / "graph.json")
    (directory / "review.html").write_text("<html>Synthetic completed review</html>")
    (directory / "run.json").write_text(
        json.dumps({
            "complete": True,
            "signature": {},
            "artifacts": {
                n: sha256((directory / n).read_bytes()).hexdigest()
                for n in ("graph.json", "review.html")
            },
        })
    )
    attempt = SimpleNamespace(
        status="completed", directory=directory, result=SimpleNamespace(graph=graph)
    )
    return attempt, spec, tmp_path / "layouts", profile, (a, b, root)


def test_fresh_profile_and_repeated_graph_layout(tmp_path):
    attempt, spec, out, profile, (a, b, root) = fixture(tmp_path)
    before = graph_json.dumps(attempt.result.graph)
    p, report = prepare(attempt.result.graph, profile)
    preference = next(v for v in p.preferences if v.assembly == str(root.id))
    assert preference.orders == ((str(a.id), str(b.id), "y"),)
    assert report[str(root.id)]["missing_ranges"] == []
    first = layout_review.build(attempt, profile=spec, output_root=out)
    assert first.status == "completed", first.diagnostics
    assert first.directory is not None
    second = layout_review.build(attempt, profile=spec, output_root=out)
    assert second.status == "completed", second.diagnostics
    assert second.directory is not None
    assert first.directory != second.directory
    assert (first.directory / "geometry.json").read_bytes() == (
        second.directory / "geometry.json"
    ).read_bytes()
    assert (second.directory / "context.json").exists()
    assert graph_json.dumps(attempt.result.graph) == before
    profile["stack_order"]["feature"] = "missing"
    _, report = prepare(attempt.result.graph, profile)
    assert (
        report[str(root.id)]["orders"] == ()
        and len(report[str(root.id)]["missing_ranges"]) == 2
    )


@pytest.mark.parametrize(
    "failure",
    ["upstream", "profile", "export", "interrupt", "stale_graph", "changed_code"],
)
def test_layout_failure_retains_previous_success(tmp_path, monkeypatch, failure):
    attempt, spec, out, _profile, _ = fixture(tmp_path)
    first = layout_review.build(attempt, profile=spec, output_root=out)
    assert first.status == "completed", first.diagnostics
    assert first.directory is not None
    pointer = (out / "latest.json").read_bytes()
    geometry = (first.directory / "geometry.json").read_bytes()
    if failure == "upstream":
        attempt.status = "failed"
    elif failure == "profile":
        spec.write_text("schema: invalid")
    elif failure in ("export", "interrupt"):

        def fail(*args, **kwargs):
            if failure == "interrupt":
                raise KeyboardInterrupt()
            raise OSError("Simulated export failure")

        monkeypatch.setattr(layout_review, "export_layout_review", fail)
    elif failure == "stale_graph":
        attempt.result.graph = Graph(entities=(Entity(code="changed"),))
    else:
        real = layout_review._implementation
        calls = []

        def changed():
            calls.append(1)
            return {**real(), "test-change": len(calls)}

        monkeypatch.setattr(layout_review, "_implementation", changed)
    result = layout_review.build(attempt, profile=spec, output_root=out)
    assert (
        result.status in {"failed", "interrupted"}
        and result.directory is None
        and result.measurements is None
    )
    assert result.previous == first.directory
    assert "Previous successful layout" in result._repr_html_()
    assert (out / "latest.json").read_bytes() == pointer and (
        first.directory / "geometry.json"
    ).read_bytes() == geometry


def preset_profile(legacy):
    return {
        key: value
        for key, value in {
            **legacy,
            "schema": "rk-layout-profile-v2",
            "preset": "stacked-compact-v1",
        }.items()
        if key not in {"canvas", "footprints", "weights"}
    }


def test_preset_preserves_explicit_policy_and_captures_resolution(tmp_path):
    from rangekeeper.graph.adapter.cytoscape.layout.profile import resolve
    from rangekeeper.graph.adapter.cytoscape.layout.seed import grid_seed

    attempt, spec, out, legacy, _ = fixture(tmp_path)
    legacy["canvas"] = {"width": 16000, "height": 30000}
    legacy["footprints"] = {
        "node_width": 248,
        "node_height": 44,
        "assembly_min_width": 280,
    }
    authored = preset_profile(legacy)
    old_problem, old_report = prepare(attempt.result.graph, legacy)
    new_problem, new_report = prepare(attempt.result.graph, authored)
    assert old_problem.document() == new_problem.document()
    assert old_report == new_report
    old_result, new_result = grid_seed(old_problem), grid_seed(new_problem)
    assert old_result is not None and new_result is not None
    assert old_result.geometry_document() == new_result.geometry_document()
    spec.write_text(yaml.safe_dump(authored))
    result = layout_review.build(attempt, profile=spec, output_root=out)
    assert result.status == "completed", result.diagnostics
    assert result.directory is not None
    context = json.loads((result.directory / "context.json").read_text())
    assert context["profile"] == authored
    assert context["resolved_profile"] == resolve(authored)
    assert context["profile_sha256"] == sha256(spec.read_bytes()).hexdigest()
    assert resolve(legacy)["notes"] == legacy["notes"]
    snapshot = json.dumps(authored)
    resolved = resolve(authored)
    resolved["footprints"]["node_width"] = 1
    resolved["notes"].append("changed")
    assert resolve(authored)["footprints"]["node_width"] == 248
    assert json.dumps(authored) == snapshot
    assert "changed" not in resolve(authored)["notes"]


@pytest.mark.parametrize(
    "change",
    [
        {"preset": "unknown-v1"},
        {"canvas": {"width": 1, "height": 1}},
        {"notes": "not a list"},
    ],
)
def test_preset_rejects_unknown_policy_and_inline_overrides(tmp_path, change):
    from rangekeeper.graph.adapter.cytoscape.layout.profile import resolve

    _, _, _, legacy, _ = fixture(tmp_path)
    with pytest.raises(ValueError):
        resolve({**preset_profile(legacy), **change})
