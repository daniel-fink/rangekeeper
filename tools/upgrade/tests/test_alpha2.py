"""Convert the 1.0.0a2 samples, which the published 1.0.0a2 package wrote (#386)."""

import json
from pathlib import Path
from typing import Any

import pytest

from rangekeeper import Model
from rangekeeper.io.bundle import Reader
from rangekeeper.model import Filter
from rangekeeper.model.system import View
from rangekeeper.schema.runtime import exact_equal
from tools.upgrade.__main__ import main
from tools.upgrade.convert import ConversionError, convert

SAMPLES = Path(__file__).with_name("samples") / "1.0.0a2"


def load() -> dict[str, Any]:
    """Return the data of the 1.0.0a2 sample Model."""
    return json.loads((SAMPLES / "model.json").read_text())


def condition(model: Model) -> Filter:
    """Return the Filter of the sample's query Expression."""
    (formulation,) = model.system.formulations
    (expression,) = formulation.expressions
    return expression.query.filter


def passed(model: Model) -> set[str]:
    """Return the codes of the Entities that pass the sample's Filter."""
    match = View(model).match(condition=condition(model))
    return {model.entity(identity).code for identity in match.passed}


def test_the_sample_is_a_1_0_0_document_with_an_exact_filter() -> None:
    data = load()
    assert data["metadata"]["schema_version"] == "1.0.0"
    (formulation,) = data["system"]["formulations"]
    query = formulation["expressions"][0]["query"]
    assert set(query["filter"]) == {"classification", "labels"}
    # The current meaning also matches the sub-types podium and suite.
    assert passed(Model.from_data(data)) == {"site", "level_1", "level_2"}


def test_conversion_keeps_the_exact_match_of_1_0_0a2() -> None:
    data = load()
    model = Model.from_data(convert(data, release="1.0.0a2"))
    found = condition(model)
    assert found.exclusive is True
    assert found.labels[0].exclusive is True
    assert passed(model) == {"site", "level_1"}
    # Nothing else changes: not the identity, not the format version.
    assert model.to_data()["metadata"] == data["metadata"]
    assert "exclusive" not in json.dumps(data)


def test_a_document_with_exclusive_is_already_current() -> None:
    data = convert(load(), release="1.0.0a2")
    with pytest.raises(ConversionError, match="already current"):
        convert(data, release="1.0.0a2")


def test_other_formats_are_refused() -> None:
    data = load()
    older = {**data, "metadata": {**data["metadata"], "schema_version": "0.8.0"}}
    with pytest.raises(ConversionError, match="not a 1.0.0a2 format"):
        convert(older, release="1.0.0a2")
    with pytest.raises(ConversionError, match="not a 0.x format"):
        convert(data, release="0.x")


def test_the_command_converts_documents_from_1_0_0a2(tmp_path: Path) -> None:
    arguments = ["documents", "--from", "1.0.0a2", str(SAMPLES / "model.json")]
    assert main([*arguments, "--output", str(tmp_path)]) == 0
    written = json.loads((tmp_path / "model.json").read_text())
    assert passed(Model.from_data(written)) == {"site", "level_1"}
    assert main(["documents", str(SAMPLES / "model.json"), "--output", "x"]) == 1


def test_a_1_0_0a2_bundle_converts_to_a_bundle_the_reader_opens(tmp_path: Path) -> None:
    # The current Reader refuses the 1.0.0a2 schema pin.
    with pytest.raises(ValueError, match="schema pin"):
        Reader(root=SAMPLES / "bundle")
    destination = tmp_path / "new"
    arguments = ["bundle", "--from", "1.0.0a2", str(SAMPLES / "bundle")]
    assert main([*arguments, str(destination)]) == 0
    restored = Reader(root=destination).model()
    expected = Model.from_data(convert(load(), release="1.0.0a2"))
    assert exact_equal(restored.to_data(), expected.to_data())
    # The 0.x release refuses the 1.0.0a2 pin.
    assert main(["bundle", str(SAMPLES / "bundle"), str(tmp_path / "other")]) == 1
