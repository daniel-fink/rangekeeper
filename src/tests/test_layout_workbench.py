"""Notebook boundary tested with synthetic storage groups."""

import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
import yaml

from uuid import uuid4
from rangekeeper.model import (
    Model,
    Metadata,
    System,
    Assembly,
    Entity,
    Characteristics,
    Classification,
    Definitions,
    Taxonomy,
    Value,
)
from rangekeeper.model.content import encode
from rangekeeper.io import json as graph_json
from rangekeeper.migration.layout import upgrade_profile
from rangekeeper.adapters.cytoscape.layout.profile import prepare
from rangekeeper.workflow import layout_review


def fixture(tmp_path):
    kind = Classification(id=uuid4(), code="shelf", name="Shelf")
    one, two = Entity(id=uuid4(), code="one"), Entity(id=uuid4(), code="two")
    a = Assembly(
        id=uuid4(),
        code="a",
        classification=kind.id,
        entities=tuple({one.id}),
        characteristics=Characteristics(
            values=(Value(id=uuid4(), key="rank", kind="property", content=encode(2)),)
        ),
    )
    b = Assembly(
        id=uuid4(),
        code="b",
        classification=kind.id,
        entities=tuple({two.id}),
        characteristics=Characteristics(
            values=(Value(id=uuid4(), key="rank", kind="property", content=encode(1)),)
        ),
    )
    root = Assembly(id=uuid4(), code="root", entities=tuple({a.id, b.id}))
    graph = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
        system=System(entities=(one, two), assemblies=(a, b, root)),
        definitions=Definitions(
            taxonomies=(
                Taxonomy(
                    id=uuid4(), code="kinds", name="Kinds", classifications=(kind,)
                ),
            )
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
    profile = upgrade_profile(profile, model=graph)
    spec = tmp_path / "layout.yaml"
    spec.write_text(yaml.safe_dump(profile))
    directory = tmp_path / "build"
    directory.mkdir()
    graph_json.write(graph, directory / "model.json")
    (directory / "review.html").write_text("<html>Synthetic completed review</html>")
    (directory / "run.json").write_text(
        json.dumps(
            {
                "complete": True,
                "signature": {},
                "artifacts": {
                    n: sha256((directory / n).read_bytes()).hexdigest()
                    for n in ("model.json", "review.html")
                },
            }
        )
    )
    attempt = SimpleNamespace(
        status="completed", directory=directory, result=SimpleNamespace(model=graph)
    )
    return attempt, spec, tmp_path / "layouts", profile, (a, b, root)


def test_fresh_profile_and_repeated_graph_layout(tmp_path):
    attempt, spec, out, profile, (a, b, root) = fixture(tmp_path)
    before = graph_json.dumps(attempt.result.model)
    p, report = prepare(attempt.result.model, profile)
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
    assert graph_json.dumps(attempt.result.model) == before
    profile["stack_order"]["key"] = "missing"
    _, report = prepare(attempt.result.model, profile)
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
        attempt.result.model = Model.create(
            metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
            system=System(entities=(Entity(id=uuid4(), code="changed"),)),
        )
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


def test_profile_old_formats_require_explicit_upgrade(tmp_path):
    from rangekeeper.adapters.cytoscape.layout.profile import resolve
    from copy import deepcopy

    attempt, _, _, profile, _ = fixture(tmp_path)
    canonical = deepcopy(profile)
    with pytest.raises(ValueError, match="upgrade_profile"):
        resolve({**profile, "schema": "rk-layout-profile-v2"})
    resolved = resolve(profile)
    resolved["notes"].append("mutation")
    assert profile == canonical and "mutation" not in resolve(profile)["notes"]
    with pytest.raises(ValueError):
        resolve({**profile, "unexpected": 1})


def test_saved_layout_binds_model_revision(tmp_path):
    from copy import deepcopy
    from rangekeeper.adapters.cytoscape import validate_document

    attempt, spec, out, _, _ = fixture(tmp_path)
    first = layout_review.build(attempt, profile=spec, output_root=out)
    assert first.status == "completed", first.diagnostics
    doc = json.loads((first.directory / "document.json").read_text())
    doc["modelId"] = str(uuid4())
    with pytest.raises(ValueError, match="different"):
        validate_document(doc)
