"""Validate complete Model documents and native LinkML serialization.

Uses the same pinned LinkML environment as the other schema checks. This is a
bounded conformance suite, not a Model persistence implementation or solver.
"""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.loaders import json_loader
from linkml_runtime.utils.schemaview import SchemaView
import yaml

import _library

from rangekeeper.errors import ContractError
from rangekeeper.model._validation import validate_model

SCHEMA = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
VERSION = yaml.safe_load((SCHEMA / "model.yaml").read_text())["version"]


def uid(name):
    return str(uuid5(NAMESPACE_URL, "rk-model-check/" + name))


validators = {}
for cls in ("Model", "Metadata", "System"):
    generated = json.loads(
        _library.schema_json(cls)
    )
    validator = validator_for(generated)
    validator.check_schema(generated)
    validators[cls] = validator(generated, format_checker=FormatChecker())
view = SchemaView(str(SCHEMA / "model.yaml"))
assert view.get_identifier_slot("Model") is None
assert view.get_identifier_slot("System") is None
assert view.get_identifier_slot("Metadata").name == "id"
assert view.get_class("Model").tree_root
previous = view.induced_slot("previous", "Metadata")
assert previous.range == "Metadata" and previous.inlined is False
formulations = view.induced_slot("formulations", "System")
assert formulations.range == "Formulation" and formulations.inlined_as_list
functions = view.induced_slot("functions", "Definitions")
assert functions.range == "Function" and functions.inlined_as_list

fixture = yaml.safe_load((SCHEMA / "examples/model.yaml").read_text())
initial = dict(metadata=dict(id=uid("minimal"), schema_version=VERSION))
valid = [fixture, initial]
with_previous = copy.deepcopy(fixture)
with_previous["metadata"].update(
    id=uid("successor"), previous=fixture["metadata"]["id"]
)
valid.append(with_previous)
with_empty = dict(
    initial, system=dict(entities=[], formulations=[]), definitions={}, provenance={}
)
valid.append(with_empty)
renamed = copy.deepcopy(fixture)
renamed["metadata"]["id"] = uid("renamed")
renamed["system"]["entities"][0]["code"] = "renamed-apartment"
renamed["definitions"]["functions"][0]["code"] = "renamed.sum"
valid.append(renamed)
# Generic evidence content is opaque, not another identified declaration.
opaque = copy.deepcopy(fixture)
opaque["provenance"]["claims"][0]["content"] = {"id": fixture["metadata"]["id"]}
valid.append(opaque)
for document in valid:
    validators["Model"].validate(document)
    validate_model(document, VERSION)
validate_model(with_previous, VERSION, history=[fixture["metadata"]])

invalid = []


def shape_case(change):
    document = copy.deepcopy(fixture)
    change(document)
    invalid.append(document)


shape_case(lambda d: d.pop("metadata"))
shape_case(lambda d: d["metadata"].pop("id"))
shape_case(lambda d: d["metadata"].pop("schema_version"))
shape_case(lambda d: d.update(metadata=uid("inline-metadata")))
shape_case(lambda d: d["metadata"].update(id="not-a-uuid"))
shape_case(lambda d: d["metadata"].update(schema_version=" "))
shape_case(lambda d: d["metadata"].update(previous={"id": uid("prior")}))
shape_case(lambda d: d["metadata"].update(previous="previous.name"))
for field in (
    "id",
    "entities",
    "blocks",
    "functions",
    "expressions",
    "constraints",
    "fixed",
    "objective",
):
    shape_case(lambda d, field=field: d.update({field: []}))
for field in ("mathematics", "calculations", "blocks", "expressions", "constraints"):
    shape_case(lambda d, field=field: d["system"].update({field: []}))
shape_case(lambda d: d["system"].update(formulations=[uid("formulation-reference")]))
shape_case(
    lambda d: d["definitions"].update(
        functions={"sum": d["definitions"]["functions"][0]}
    )
)
shape_case(lambda d: d["definitions"]["functions"][0].pop("result"))
shape_case(lambda d: d["provenance"]["facts"][0].update(claims=[]))
shape_case(lambda d: d["system"]["formulations"][0]["values"][0].pop("measure"))
for document in invalid:
    assert not validators["Model"].is_valid(document), document

semantic = []


def semantic_case(message, change, history=()):
    document = copy.deepcopy(fixture)
    change(document)
    semantic.append((document, message, history))


semantic_case(
    "unsupported schema version",
    lambda d: d["metadata"].update(schema_version="99.0.0"),
)
semantic_case(
    "self predecessor", lambda d: d["metadata"].update(previous=d["metadata"]["id"])
)
semantic_case(
    "previous targets current",
    lambda d: d["metadata"].update(previous=d["system"]["entities"][0]["id"]),
)
semantic_case(
    "revision history cycle",
    lambda d: d["metadata"].update(previous=uid("ancestor")),
    [
        dict(
            id=uid("ancestor"),
            schema_version=VERSION,
            previous=fixture["metadata"]["id"],
        )
    ],
)
semantic_case(
    "duplicate identity",
    lambda d: d["metadata"].update(id=d["system"]["entities"][0]["id"]),
)
semantic_case(
    "duplicate identity",
    lambda d: d["provenance"]["sources"][0].update(
        id=d["system"]["formulations"][0]["id"]
    ),
)
semantic_case(
    "duplicate identity",
    lambda d: d["system"]["entities"].append(
        dict(id=d["system"]["assemblies"][0]["id"])
    ),
)
semantic_case(
    "Entity/Assembly code",
    lambda d: d["system"]["assemblies"][0].update(
        code=d["system"]["entities"][0]["code"]
    ),
)
semantic_case(
    "measures code",
    lambda d: d["definitions"]["measures"][1].update(
        code=d["definitions"]["measures"][0]["code"]
    ),
)
semantic_case(
    "Function code",
    lambda d: d["definitions"]["functions"].append(
        dict(d["definitions"]["functions"][0], id=uid("function-copy"))
    ),
)
semantic_case(
    "Classification parent outside",
    lambda d: d["definitions"]["taxonomies"][0]["classifications"][1].update(
        parent=uid("missing-classification")
    ),
)
semantic_case(
    "one root",
    lambda d: d["definitions"]["taxonomies"][0]["classifications"][1].pop("parent"),
)
semantic_case(
    "Classification parent cycle",
    lambda d: d["definitions"]["taxonomies"][0]["classifications"][0].update(
        parent=d["definitions"]["taxonomies"][0]["classifications"][1]["id"]
    ),
)
semantic_case(
    "unknown Classification",
    lambda d: d["system"]["entities"][0].update(
        classification=uid("missing-classification")
    ),
)
semantic_case(
    "unknown Label Classification",
    lambda d: d["system"]["entities"][0]["characteristics"]["labels"][0].update(
        classifications=[uid("missing-label-classification")]
    ),
)
semantic_case(
    "Relationship endpoint",
    lambda d: d["system"]["relationships"][0].update(
        source=d["definitions"]["measures"][0]["id"]
    ),
)
semantic_case(
    "unknown Assembly Entity",
    lambda d: d["system"]["assemblies"][0]["entities"].append(uid("missing-member")),
)
semantic_case(
    "Assembly membership cycle",
    lambda d: d["system"]["assemblies"][0]["entities"].append(
        d["system"]["assemblies"][0]["id"]
    ),
)
semantic_case(
    "unknown or non-Value",
    lambda d: d["system"]["formulations"][0]["bindings"][0].update(
        value=uid("outside-snapshot")
    ),
)
semantic_case("unknown Function", lambda d: d["definitions"].pop("functions"))
semantic_case("unknown Source", lambda d: d["provenance"]["sources"].clear())
semantic_case(
    "unknown supporting Claim",
    lambda d: d["provenance"]["facts"][0].update(claims=[uid("missing-claim")]),
)
semantic_case(
    "ineligible Fact target",
    lambda d: d["provenance"]["facts"][0].update(target=d["metadata"]["id"]),
)
semantic_case(
    "duplicate Fact target",
    lambda d: d["provenance"]["facts"].append(
        copy.deepcopy(d["provenance"]["facts"][0])
    ),
)

for document, message, history in semantic:
    validators["Model"].validate(document)
    try:
        validate_model(document, VERSION, history=history)
    except ContractError as error:
        assert message in str(error), (message, str(error))
    else:
        raise AssertionError(f"Missing Model rejection: {message}")


def nonempty(content):
    """Generated dumpers may omit optional empty containers, but not zero/false."""
    if isinstance(content, dict):
        return {
            k: v
            for k, raw in content.items()
            if (v := nonempty(raw)) not in (None, [], {})
        }
    if isinstance(content, list):
        return [nonempty(x) for x in content]
    return content


with TemporaryDirectory(prefix="rk-model-") as temp:
    path = Path(temp) / "records.py"
    path.write_text(
        subprocess.check_output(
            [str(BIN / "gen-python"), str(SCHEMA / "model.yaml")], text=True
        )
    )
    spec = importlib.util.spec_from_file_location("rk_model_records", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for document in valid:
        record = json_loader.loads(json.dumps(document), target_class=module.Model)
        assert isinstance(record.metadata, module.Metadata)
        assert isinstance(record.metadata.id, module.MetadataId)
        if record.metadata.previous:
            assert isinstance(record.metadata.previous, module.MetadataId)
        if record.system and record.system.formulations:
            assert isinstance(record.system.formulations[0], module.Formulation)
        if record.definitions and record.definitions.functions:
            assert isinstance(record.definitions.functions[0], module.Function)
        after = json.loads(json_dumper.dumps(record, inject_type=False))
        assert nonempty(document) == nonempty(after), (document, after)
        validators["Model"].validate(after)
        validate_model(after, VERSION)
        restored = json_loader.loads(json.dumps(after), target_class=module.Model)
        assert json.loads(json_dumper.dumps(restored, inject_type=False)) == after

print(
    f"Passed {len(validators)} generated schemas, {len(valid)} valid Models, {len(invalid)} structural rejections,"
)
print(
    f"{len(semantic)} bounded semantic rejections, and {len(valid)} native Model round trips."
)
print(
    "Storage immutability, generic Fact/content agreement, unit inference, and execution remain outside this check."
)
