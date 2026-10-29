"""Convert the 0.x samples, which the published 1.0.0a1 package wrote."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from rangekeeper import Model, Run, Specification
from rangekeeper.execution import Outcome
from rangekeeper.execution.backends import Termination
from rangekeeper.io import MemoryStore
from rangekeeper.io._amounts import amounts
from rangekeeper.run import validate
from rangekeeper.schema.runtime import exact_equal
from tools.upgrade.__main__ import main
from tools.upgrade.convert import ConversionError, _amount, convert, kind_of

SAMPLES = Path(__file__).with_name("samples")


def load(name):
    text = (SAMPLES / name).read_text()
    return yaml.safe_load(text) if name.endswith(".yaml") else json.loads(text)


def converted():
    """Return the converted sample documents in a store, by file name."""
    store, result = MemoryStore(), {}
    for name, kind in (
        ("model.json", Model),
        ("output.json", Model),
        ("specification.yaml", Specification),
        ("run.json", Run),
    ):
        result[name] = kind.from_data(data=convert(load(name), release="0.x"))
        store.put(result[name])
    return store, result


def keys(value):
    """Return the field names at every depth, outside opaque Claim content."""
    if isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != "content"}
        return set(value) | {k for child in value.values() for k in keys(child)}
    if isinstance(value, list):
        return {k for child in value for k in keys(child)}
    return set()


def test_samples_are_the_formats_that_need_conversion():
    assert load("model.json")["metadata"]["schema_version"] == "0.7.0"
    assert load("specification.yaml")["metadata"]["schema_version"] == "0.7.0"
    assert load("run.json")["metadata"]["schema_version"] == "0.4.0"
    assert "policy" in load("specification.yaml")
    assert "outcomes" in load("run.json")["report"]
    assert "start_inclusive" in keys(load("model.json"))


def test_documents_convert_to_valid_1_0_documents():
    store, documents = converted()
    for document in documents.values():
        assert document.metadata.schema_version == "1.0.0"
        data = document.to_data()
        assert not keys(data) & {"start_inclusive", "end_exclusive", "policy"}
    specification = documents["specification.yaml"].to_data()
    assert specification["rules"] == load("specification.yaml")["policy"]
    run = documents["run.json"]
    assert run.report.rule_evidence
    assert validate(run=run, resolver=store).valid


def test_the_solver_evidence_of_a_converted_run_reads_as_unknown():
    _, documents = converted()
    outcome = Outcome(run=documents["run.json"], outputs=(documents["output.json"],))
    evidence = outcome.evidence
    # A 0.x Run keeps its solver evidence in the message, as recorded.
    assert evidence.termination is Termination.UNKNOWN
    assert evidence.backend == {}


def test_identities_and_lineage_do_not_change():
    _, documents = converted()
    for name, document in documents.items():
        before = load(name)["metadata"]
        after = document.to_data()["metadata"]
        assert {k: v for k, v in after.items() if k != "schema_version"} == {
            k: v for k, v in before.items() if k != "schema_version"
        }


def test_currency_magnitudes_become_canonical_amounts():
    _, documents = converted()
    model = documents["output.json"]
    flows = [
        value.flow
        for formulation in model.system.formulations
        for value in formulation.values
        if value.flow is not None and value.flow.units == "AUD"
    ]
    assert flows
    for flow in flows:
        for movement in flow.movements:
            if movement.magnitude is not None:
                assert type(movement.magnitude) is Decimal
                assert type(movement.to_data()["magnitude"]) is str
    before = json.dumps(load("output.json"))
    assert '"magnitude": 100.0' in before
    assert '"magnitude": "100"' in json.dumps(model.to_data())


def test_a_float_with_binary_noise_becomes_its_fifteen_digit_amount():
    quantity = {"magnitude": 0.1 + 0.2, "units": "AUD"}
    rate = {"magnitude": 0.1 + 0.2, "units": "AUD/year"}
    assert amounts("Quantity", quantity, _amount)["magnitude"] == "0.3"
    assert amounts("Quantity", rate, _amount) == rate


def test_other_versions_and_kinds_are_refused():
    data = load("model.json")
    for version in ("1.0.0", "0.6.0", None):
        changed = {**data, "metadata": {**data["metadata"], "schema_version": version}}
        with pytest.raises(ConversionError, match="not a 0.x format"):
            convert(changed, release="0.x")
    with pytest.raises(ConversionError, match="unknown document kind"):
        convert(data, "Paths", release="0.x")
    with pytest.raises(ConversionError, match="unknown release"):
        convert(data, release="1.0.0a1")
    assert kind_of(load("run.json")) == "Run"
    assert kind_of(load("specification.yaml")) == "Specification"


def test_the_input_does_not_change():
    data = load("specification.yaml")
    copy = json.loads(json.dumps(data))
    convert(data, release="0.x")
    assert data == copy


def test_bundle_conversion_writes_a_new_bundle_with_the_same_documents(tmp_path):
    pytest.importorskip("pyarrow")
    from rangekeeper.io.bundle import Reader
    from tools.upgrade.bundle import read

    _, documents = converted()
    assert main(["bundle", str(SAMPLES / "bundle"), str(tmp_path / "new")]) == 0
    reader = Reader(root=tmp_path / "new")
    restored = {document.id: document for document in reader.documents()}
    for document in documents.values():
        assert exact_equal(restored[document.id].to_data(), document.to_data())
    (run,) = [d for d in restored.values() if isinstance(d, Run)]
    assert validate(run=run, resolver=reader).valid
    assert {kind for kind, _ in read(SAMPLES / "bundle", release="0.x")} == {
        "Model",
        "Specification",
        "Run",
    }
    assert main(["bundle", str(SAMPLES / "bundle"), str(tmp_path / "new")]) != 0


def test_the_command_writes_new_files_and_never_replaces_one(tmp_path, capsys):
    names = ["model.json", "specification.yaml", "run.json", "output.json"]
    arguments = ["documents", *(str(SAMPLES / n) for n in names)]
    assert main([*arguments, "--output", str(tmp_path)]) == 0
    assert Specification.from_data(yaml.safe_load((tmp_path / names[1]).read_text()))
    assert main([*arguments, "--output", str(tmp_path)]) == 1
    assert "error" in capsys.readouterr().err


def test_filters_keep_their_exact_match():
    from tools.upgrade.convert import RELEASES, _fields

    query = {
        "starting_at": "00000000-0000-4000-8000-000000000001",
        "filter": {
            "classification": "00000000-0000-4000-8000-000000000002",
            "labels": [
                {"key": "use", "classification": "00000000-0000-4000-8000-000000000003"}
            ],
        },
        "projection": {"kind": "entity"},
        "duplicates": "distinct",
    }
    result = _fields("Query", query, RELEASES["0.x"])
    assert result["filter"]["exclusive"] is True
    assert result["filter"]["labels"][0]["exclusive"] is True
    assert "exclusive" not in query["filter"]
    # A Filter without a classification gets no exclusive field.
    assert _fields("Filter", {"labels": []}, RELEASES["0.x"]) == {"labels": []}


def test_a_property_date_stays_a_property_value():
    from tools.upgrade.convert import RELEASES, _fields

    # The 0.x formats have no date kind (#280): a date in property content stays
    # property content, and the converted Value has no date or never field.
    value = {
        "id": "00000000-0000-4000-8000-000000000004",
        "key": "start_date",
        "kind": "property",
        "content": {"kind": "date", "text": "2027-01-01"},
    }
    result = _fields("Value", value, RELEASES["0.x"])
    assert result == value
    assert not {"date", "never"} & set(result)
    assert all("never" not in keys(load(name)) for name in ("model.json", "run.json"))
