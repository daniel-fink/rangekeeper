"""Generate structural validators for the UUID-based schema examples.

Use LinkML 1.11.1 and jsonschema. Cross-record checks remain in the runtime
conformance fixture; generated JSON Schema alone cannot establish referential integrity.
"""

import copy
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schema"
GENERATE = Path(sys.executable).with_name("gen-json-schema")
validators = {}
for name, file in (
    ("Definitions", "definitions"),
    ("Taxonomy", "classification"),
    ("Entity", "entity"),
    ("Relationship", "relationship"),
    ("Assembly", "assembly"),
    ("Classification", "classification"),
    ("Measure", "measure"),
    ("Quantity", "measure"),
    ("Measurement", "measure"),
    ("Characteristics", "characteristics"),
    ("Label", "characteristics"),
    ("Value", "characteristics"),
    ("Provenance", "provenance"),
):
    schema = json.loads(
        subprocess.check_output(
            [
                str(GENERATE),
                "--closed",
                "--top-class",
                name,
                str(SCHEMA / f"{file}.yaml"),
            ],
            text=True,
        )
    )
    cls = validator_for(schema)
    cls.check_schema(schema)
    validators[name] = cls(schema, format_checker=FormatChecker())


def unique_keys(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError(f"duplicate dictionary key: {key}")
        record[key] = value
    return record


fixture = json.loads(
    (SCHEMA / "examples/structural-graph.json").read_text(),
    object_pairs_hook=unique_keys,
)


def validate_example(example):
    for key, name in (
        ("entities", "Entity"),
        ("relationships", "Relationship"),
        ("assemblies", "Assembly"),
    ):
        for record in example[key]:
            validators[name].validate(record)
    validators["Provenance"].validate(example["provenance"])
    validators["Definitions"].validate(example["definitions"])


validate_example(fixture)
# The README's first YAML block is instance data under the same record profile.
import yaml

readme = yaml.safe_load(
    (SCHEMA / "README.md").read_text().split("```yaml\n", 1)[1].split("```", 1)[0]
)
validate_example(readme)

cases = []
measurement = {
    "id": fixture["entities"][0]["characteristics"]["values"][0]["id"],
    "measure": fixture["definitions"]["measures"][0]["id"],
}
for quantity in (
    None,
    {"magnitude": 0, "units": "m^2"},
    {"magnitude": 855000, "units": "cm^2"},
):
    validators["Measurement"].validate(dict(measurement, quantity=quantity))
    if quantity is not None:
        validators["Quantity"].validate(quantity)
validators["Measurement"].validate(measurement)
for quantity in (
    {},
    {"magnitude": 1},
    {"units": "m^2"},
    {"magnitude": None, "units": "m^2"},
    {"magnitude": True, "units": "m^2"},
    {"magnitude": 1, "units": " "},
    {"magnitude": 1, "units": None},
    {"magnitude": 1, "units": "m^2", "id": measurement["id"]},
    {"magnitude": 1, "units": "m^2", "measure": measurement["measure"]},
):
    cases.append(("Quantity", quantity))
    cases.append(("Measurement", dict(measurement, quantity=quantity)))
    cases.append(
        ("Value", dict(measurement, key="area", kind="measurement", quantity=quantity))
    )
cases.append(("Measurement", dict(measurement, amount=85.5)))
cases.append(("Value", dict(measurement, key="area", kind="measurement", amount=85.5)))
legacy_value = copy.deepcopy(fixture["entities"][0]["characteristics"]["values"][0])
legacy_value["type"] = legacy_value.pop("kind")
cases.append(("Value", legacy_value))
for name, record, field in (
    ("Entity", fixture["entities"][0], "id"),
    ("Relationship", fixture["relationships"][0], "source"),
    ("Relationship", fixture["relationships"][0], "classification"),
    ("Assembly", fixture["assemblies"][0], "id"),
    (
        "Classification",
        fixture["definitions"]["taxonomies"][0]["classifications"][1],
        "id",
    ),
    ("Measure", fixture["definitions"]["measures"][0], "id"),
    ("Value", fixture["entities"][0]["characteristics"]["values"][0], "id"),
    ("Value", fixture["entities"][0]["characteristics"]["values"][0], "key"),
):
    invalid = copy.deepcopy(record)
    invalid.pop(field)
    cases.append((name, invalid))
for kind in ("asserted", "derived"):
    invalid = copy.deepcopy(fixture["provenance"])
    next(c for c in invalid["claims"] if c["kind"] == kind).pop("method")
    cases.append(("Provenance", invalid))
invalid = copy.deepcopy(fixture["provenance"])
invalid["facts"][0]["claims"] = []
cases.append(("Provenance", invalid))
for code in ("", " ", " A", "A ", "A\n", "\tA"):
    invalid = copy.deepcopy(fixture["entities"][0])
    invalid["code"] = code
    cases.append(("Entity", invalid))
for reference in (
    "apartment",
    "example.apartment",
    {"taxonomy": "example", "code": "apartment"},
    "",
    123,
):
    invalid = copy.deepcopy(fixture["entities"][0])
    invalid["classification"] = reference
    cases.append(("Entity", invalid))
    invalid = copy.deepcopy(fixture["entities"][0])
    invalid["characteristics"]["labels"][0]["classifications"] = [reference]
    cases.append(("Entity", invalid))
    invalid = copy.deepcopy(fixture["entities"][0])
    invalid["characteristics"]["values"][0]["measure"] = reference
    cases.append(("Entity", invalid))
    invalid = copy.deepcopy(fixture["definitions"])
    invalid["taxonomies"][0]["classifications"][1]["parent"] = reference
    cases.append(("Definitions", invalid))
    invalid = copy.deepcopy(fixture["provenance"])
    invalid["facts"][0]["target"] = reference
    cases.append(("Provenance", invalid))
# Code-keyed catalogues are no longer an accepted serialized collection shape.
invalid = copy.deepcopy(fixture["definitions"])
invalid["measures"] = {x["code"]: x for x in invalid["measures"]}
cases.append(("Definitions", invalid))
invalid = copy.deepcopy(fixture["entities"][0])
invalid["characteristics"]["values"] = {
    x["key"]: x for x in invalid["characteristics"]["values"]
}
cases.append(("Entity", invalid))
# Replaced instance names are rejected rather than ignored or treated as aliases.
for name, record, old, new in (
    ("Relationship", fixture["relationships"][0], "source_id", "source"),
    ("Relationship", fixture["relationships"][0], "target_id", "target"),
    ("Assembly", fixture["assemblies"][0], "entity_ids", "entities"),
    ("Assembly", fixture["assemblies"][0], "relationship_ids", "relationships"),
):
    invalid = copy.deepcopy(record)
    invalid[old] = invalid.pop(new)
    cases.append((name, invalid))
invalid = copy.deepcopy(fixture["provenance"])
claim = invalid["claims"][0]
claim["value"] = claim.pop("content")
cases.append(("Provenance", invalid))
invalid = copy.deepcopy(fixture["provenance"])
location = invalid["claims"][0]["sources"][0]
location["reference"] = location.pop("address")
cases.append(("Provenance", invalid))
for name, record in cases:
    if validators[name].is_valid(record):
        raise AssertionError(f"{name} unexpectedly accepted invalid record: {record}")

# Record shape is not evidence of reference resolution or conditional support counts.
invalid = copy.deepcopy(fixture["entities"][0])
invalid["classification"] = "00000000-0000-0000-0000-000000000000"
assert validators["Entity"].is_valid(invalid)
invalid = copy.deepcopy(fixture["provenance"])
invalid["claims"][0]["sources"] = []
assert validators["Provenance"].is_valid(invalid)
print(
    f"{len(validators)} schemas generated; both examples and {len(cases)} rejection cases passed."
)
print("Reference existence and empty Claim support still require semantic validation.")
