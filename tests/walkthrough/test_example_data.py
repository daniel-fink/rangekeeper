"""The mixed-use property data package records its licence and provenance."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[2] / "examples/data/mixed_use_property"
UNLISTED = {"LICENSE", "README.md", "manifest.json"}
ORIGINS = {"legacy-notebook", "book-method", "author", "derived"}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def leaves(value, pointer=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, f"{pointer}/{key}")
    else:
        yield pointer


def covers(pattern, pointer):
    parts, target = pattern.split("/")[1:], pointer.split("/")[1:]
    return len(parts) <= len(target) and all(
        part in ("*", key) for part, key in zip(parts, target, strict=False)
    )


def test_manifest_lists_every_file_with_hash_origin_and_licence():
    manifest = load("manifest.json")
    assert manifest["licence"]["spdx"] == "CC-BY-4.0"
    assert "Attribution 4.0 International" in (DATA / "LICENSE").read_text(
        encoding="utf-8"
    )
    present = {path.name for path in DATA.iterdir()} - UNLISTED
    assert set(manifest["files"]) == present
    for name, entry in manifest["files"].items():
        data = (DATA / name).read_bytes()
        assert entry["bytes"] == len(data), name
        assert entry["sha256"] == hashlib.sha256(data).hexdigest(), name
        assert entry["origin"] in manifest["origin_vocabulary"], name
        assert entry["licence"] == "CC-BY-4.0", name
        assert entry["description"], name


@pytest.mark.parametrize("name", ["assumptions.json", "development.json"])
def test_each_teaching_assumption_names_its_origin(name):
    origins = load("origins.json")
    assert set(origins["origins_vocabulary"]) == ORIGINS
    patterns = origins[name]
    metadata = origins["metadata"][name]
    for pointer in leaves(load(name)):
        if any(covers(prefix, pointer) for prefix in metadata):
            continue
        matches = [pattern for pattern in patterns if covers(pattern, pointer)]
        assert len(matches) == 1, (pointer, matches)
    for pattern, origin in patterns.items():
        assert origin["origin"] in ORIGINS, pattern
        assert any(covers(pattern, pointer) for pointer in leaves(load(name))), pattern
        if origin["origin"] == "legacy-notebook":
            assert origin["cells"], pattern
        elif origin["origin"] == "book-method":
            assert origin["reference"], pattern
        elif origin["origin"] == "derived":
            assert origin["from"], pattern
        else:
            assert origin["note"], pattern


def derivation(name):
    """Return the derivation script of the data package with this name."""
    path = DATA.parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_base_plan_file_is_the_derivation_of_the_package():
    # examples/data/derive_base_plan.py writes the file; it must not be edited by hand.
    derive_base_plan = derivation("derive_base_plan")
    text = (DATA / "base_plan.json").read_text(encoding="utf-8")
    assert text == derive_base_plan.text()
    plan = load("base_plan.json")
    amounts = plan["values"]
    # The budgets of the three packages and the allowance are the works cost.
    works = load("totals_2032.json")["totals"]["works_cost"]["magnitude"]
    allowance = load("development.json")["construction_finance_allowance_AUD"]
    budgets = sum(
        amounts[key]["magnitude"] for key in ("shared_cost", "a_cost", "b_cost")
    )
    assert budgets + allowance == pytest.approx(works)
    # The operating costs of the three packages grow to the total of 2032.
    opex = sum(amounts[key]["magnitude"] for key in ("shared_opex", "a_opex", "b_opex"))
    total = load("totals_2032.json")["totals"]["operating_cost"]["magnitude"]
    assert opex * 1.035**5 == pytest.approx(total)
    assert (
        amounts["loan_limit"]["magnitude"]
        == (load("development.json")["funding"]["bridge_limit_AUD"])
    )
    assert set(plan["areas"]) == {"shared", "building_a", "building_b"}


def test_the_totals_file_is_the_derivation_of_the_package():
    # examples/data/derive_totals.py writes the file; it must not be edited by hand.
    derive_totals = derivation("derive_totals")
    text = (DATA / "totals_2032.json").read_text(encoding="utf-8")
    assert text == derive_totals.text()
    items = ("area", "rent", "vacancy")
    keys = {f"{use}_{item}" for use in derive_totals.RENTED for item in items}
    totals = load("totals_2032.json")["totals"]
    assert set(totals) == {"works_cost", "operating_cost", *keys}


def test_the_documents_of_lessons_04_and_05_are_the_derivation_of_the_lessons():
    # examples/data/derive_lesson_documents.py writes the files; --check compares them.
    derive = derivation("derive_lesson_documents")
    assert derive.main(["--check"]) == 0
    assert derive.main(["--unknown"]) == 2


def test_the_lesson_document_check_ignores_ids_and_finds_other_changes(tmp_path):
    derive = derivation("derive_lesson_documents")
    first = "11111111-1111-4111-8111-111111111111"
    second = "22222222-2222-4222-8222-222222222222"
    # The same IDs in the same order of first use give the same text.
    assert derive.without_ids(f"{first} {second} {first}") == derive.without_ids(
        f"{second} {first} {second}"
    )
    # Two IDs cannot become one.
    assert derive.without_ids(f"{first} {first}") != derive.without_ids(
        f"{first} {second}"
    )
    for name in derive.FILES:
        text = (DATA / name).read_text(encoding="utf-8")
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert derive.differing(tmp_path) == []
    (name, *_) = derive.FILES
    (tmp_path / name).write_text("{}", encoding="utf-8")
    assert derive.differing(tmp_path) == [name]


def test_the_lesson_document_check_ignores_versions_and_small_rounding_of_paths(
    tmp_path,
):
    derive = derivation("derive_lesson_documents")
    name = "05_histories.paths.json"
    content = json.loads((DATA / name).read_text(encoding="utf-8"))
    content["document"]["capture"]["versions"] = [{"name": "numpy", "version": "9"}]
    content["document"]["metadata"]["id"] = "other"
    amounts = content["document"]["members"][0]["amounts"][0]["magnitudes"]
    amounts[0] += 1e-13
    (tmp_path / name).write_text(json.dumps(content), encoding="utf-8")
    assert derive.differing(tmp_path, names=(name,)) == []
    amounts[0] += 1e-3
    (tmp_path / name).write_text(json.dumps(content), encoding="utf-8")
    assert derive.differing(tmp_path, names=(name,)) == [name]
