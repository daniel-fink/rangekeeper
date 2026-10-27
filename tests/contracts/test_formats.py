"""Document format versions: the 1.0.0 reset and the reader rule (ADR-017)."""

import importlib
import json
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from rangekeeper import Model, Run, Specification
from rangekeeper.schema.records import Metadata
from rangekeeper.schema.records import Run as RunRecord
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.schema.validation import document_version, supports_version
from rangekeeper.shared.errors import UnsupportedVersionError

KINDS = ("Model", "Specification", "Run")
EXAMPLES = Path(__file__).resolve().parents[2] / "examples/schema"


def test_every_document_format_is_1_0_0():
    manifest = json.loads(
        files("rangekeeper.schema").joinpath("manifest.json").read_text()
    )
    assert manifest["document_versions"] == dict.fromkeys(KINDS, "1.0.0")
    assert all(document_version(kind) == "1.0.0" for kind in KINDS)


@pytest.mark.parametrize(
    ("version", "current", "expected"),
    [
        ("1.0.0", "1.0.0", True),
        ("1.0.0", "1.2.0", True),
        ("1.1.0", "1.2.0", True),
        ("1.2.1", "1.2.0", False),
        ("1.1.0", "1.0.0", False),
        ("0.8.0", "1.0.0", False),
        ("0.7.0", "1.0.0", False),
        ("2.0.0", "1.0.0", False),
        ("1.0", "1.0.0", False),
        ("v1.0.0", "1.0.0", False),
        (None, "1.0.0", False),
    ],
)
def test_reader_reads_its_major_version_up_to_its_own(version, current, expected):
    assert supports_version(version, current) is expected


@pytest.mark.parametrize("version", ["0.7.0", "0.8.0"])
def test_model_reader_rejects_0x_formats(version):
    with pytest.raises(UnsupportedVersionError):
        Model.create(metadata=Metadata(id=uuid4(), schema_version=version))


def test_specification_and_run_readers_reject_0x_formats():
    model = Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))
    with pytest.raises(UnsupportedVersionError):
        Specification(
            SpecificationRecord(
                metadata=Metadata(id=uuid4(), schema_version="0.7.0"), model=model.id
            )
        )
    data = yaml.safe_load((EXAMPLES / "run-failed.yaml").read_text())
    data["metadata"]["schema_version"] = "0.4.0"
    with pytest.raises(UnsupportedVersionError):
        Run(RunRecord.from_data(data))


def test_the_0_7_migration_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("rangekeeper.io.migration")
