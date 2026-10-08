"""Exercise generated LinkML classes with the shared UUID-reference examples.

The temporary wrapper groups fixture records; it does not define a Model schema.
Run in the same pinned LinkML environment as validate.py.
"""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

import yaml
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.loaders import json_loader
from linkml_runtime.utils.schemaview import SchemaView

SCHEMA = Path(__file__).resolve().parents[1]

with TemporaryDirectory(prefix="rk-native-") as temp:
    directory = Path(temp)
    for schema_file in SCHEMA.glob("*.yaml"):
        shutil.copyfile(schema_file, directory / schema_file.name)
    wrapper = {
        "id": "https://example.org/rk-conformance",
        "name": "rk_conformance",
        "prefixes": {
            "linkml": "https://w3id.org/linkml/",
            "check": "https://example.org/",
        },
        "default_prefix": "check",
        "imports": ["definitions", "provenance"],
        "classes": {
            "Example": {
                "tree_root": True,
                "attributes": {
                    "definitions": {"range": "Definitions", "inlined": True},
                    "provenance": {"range": "Provenance", "inlined": True},
                    **{
                        key: {
                            "range": cls,
                            "multivalued": True,
                            "inlined": True,
                            "inlined_as_list": True,
                        }
                        for key, cls in (
                            ("entities", "Entity"),
                            ("relationships", "Relationship"),
                            ("assemblies", "Assembly"),
                        )
                    },
                },
            }
        },
    }
    source = directory / "example.yaml"
    source.write_text(yaml.safe_dump(wrapper, sort_keys=False))
    view = SchemaView(str(source))
    assert view.get_identifier_slot("Quantity") is None
    for name in (
        "Classification",
        "Taxonomy",
        "Measure",
        "Measurement",
        "Entity",
        "Relationship",
        "Assembly",
        "Label",
        "Value",
        "Claim",
        "Source",
    ):
        assert view.get_identifier_slot(name).name == "id", name
    for owner, slot, target in (
        ("Entity", "classification", "Classification"),
        ("Label", "classifications", "Classification"),
        ("Classification", "parent", "Classification"),
        ("Value", "measure", "Measure"),
        ("Measurement", "measure", "Measure"),
        ("Relationship", "source", "Entity"),
        ("Relationship", "target", "Entity"),
        ("Assembly", "entities", "Entity"),
        ("Assembly", "relationships", "Relationship"),
        ("Location", "source", "Source"),
        ("Fact", "claims", "Claim"),
        ("Reconciliation", "selected", "Claim"),
    ):
        field = view.induced_slot(slot, owner)
        assert field.range == target and field.inlined is False, (owner, slot)
    fact_targets = view.induced_slot("target", "Fact").any_of
    assert {field.range for field in fact_targets} == {
        "Entity",
        "Relationship",
        "Label",
        "Value",
        "Measurement",
    }
    assert all(field.inlined is False for field in fact_targets)
    upstream = view.induced_slot("sources", "Claim").any_of
    assert any(field.range == "Claim" and field.inlined is False for field in upstream)

    generated = directory / "records.py"
    generated.write_text(
        subprocess.check_output(
            [
                str(Path(sys.executable).with_name("gen-python")),
                str(source),
            ],
            text=True,
        )
    )
    spec = importlib.util.spec_from_file_location("rk_native_records", generated)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fixture = json.loads((SCHEMA.parent / "examples/schema/structural-graph.json").read_text())
    for content in (
        None,
        {"magnitude": 0, "units": "m^2"},
        {"magnitude": 855000, "units": "cm^2"},
    ):
        measurement = {
            "id": fixture["entities"][0]["characteristics"]["values"][0]["id"],
            "measure": fixture["definitions"]["measures"][0]["id"],
            "quantity": content,
        }
        record = json_loader.loads(
            json.dumps(measurement), target_class=module.Measurement
        )
        encoded = json.loads(json_dumper.dumps(record, inject_type=False))
        assert encoded.get("quantity") == content
        if content is not None:
            assert isinstance(record.quantity, module.Quantity)
    ownership = yaml.safe_load(
        (SCHEMA.parent / "examples/schema/ownership.yaml").read_text()
    )
    for example in (fixture, ownership):
        record = json_loader.loads(json.dumps(example), target_class=module.Example)
        apartment = record.entities[0]
        assert isinstance(apartment.classification, module.ClassificationId)
        assert isinstance(
            apartment.characteristics.labels[0].classifications[0],
            module.ClassificationId,
        )
        assert isinstance(apartment.characteristics.values[0].measure, module.MeasureId)
        encoded = json_dumper.dumps(record)
        restored = json_loader.loads(encoded, target_class=module.Example)
        assert json_dumper.dumps(restored) == encoded

        # Preserve supplied content; empty collections may be omitted by the dumper.
        def supplied_fields_preserved(before, after):
            if isinstance(before, dict):
                assert isinstance(after, dict)
                for key, value in before.items():
                    if key not in after and value in (None, [], {}):
                        continue
                    supplied_fields_preserved(value, after[key])
            elif isinstance(before, list):
                assert len(before) == len(after)
                for a, b in zip(before, after):
                    supplied_fields_preserved(a, b)
            else:
                assert before == after, (before, after)

        supplied_fields_preserved(example, json.loads(encoded))
    print(
        "Native identifiers, typed reference fields, and generated Python round trips passed for both examples."
    )
