"""Validate Specification structure, composition, roles, and native LinkML round trips.

Use the pinned schema environment. These examples specify expected arithmetic;
they do not execute a solver or produce Run/output Model artifacts.
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

from expression_contract import ContractError
from specification_contract import records, validate_specification

SCHEMA = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
VERSION = yaml.safe_load((SCHEMA / "specification.yaml").read_text())["version"]
MODEL_VERSION = yaml.safe_load((SCHEMA / "model.yaml").read_text())["version"]


def uid(name):
    return str(uuid5(NAMESPACE_URL, "rk-specification-check/" + name))


validators = {}
for cls in (
    "Specification",
    "Metadata",
    "Assignment",
    "Objective",
    "Settings",
    "Model",
):
    schema = "model" if cls == "Model" else "specification"
    generated = json.loads(
        subprocess.check_output(
            [
                str(BIN / "gen-json-schema"),
                "--closed",
                "--top-class",
                cls,
                str(SCHEMA / f"{schema}.yaml"),
            ],
            text=True,
        )
    )
    validator = validator_for(generated)
    validator.check_schema(generated)
    validators[cls] = validator(generated, format_checker=FormatChecker())

view = SchemaView(str(SCHEMA / "specification.yaml"))
assert view.get_identifier_slot("Specification") is None
assert view.get_identifier_slot("Metadata").name == "id"
assert view.get_class("Metadata").from_schema.endswith("/common")
assert view.get_class("Specification").tree_root
for owner, field, target in (
    ("Specification", "model", "Metadata"),
    ("Specification", "includes", "Metadata"),
    ("Specification", "cases", "Metadata"),
    ("Specification", "unknowns", "Value"),
    ("Assignment", "value", "Value"),
    ("Objective", "expression", "Expression"),
):
    slot = view.induced_slot(field, owner)
    assert slot.range == target and slot.inlined is False
for field, target in (
    ("assignments", "Assignment"),
    ("estimates", "Assignment"),
    ("formulations", "Formulation"),
):
    slot = view.induced_slot(field, "Specification")
    assert slot.range == target and slot.multivalued and slot.inlined_as_list
    assert not slot.list_elements_ordered
objectives_slot = view.induced_slot("objectives", "Specification")
assert objectives_slot.range == "Objective" and objectives_slot.multivalued
assert objectives_slot.inlined and objectives_slot.inlined_as_list
assert objectives_slot.list_elements_ordered

model = yaml.safe_load((SCHEMA / "examples/model.yaml").read_text())
forward, inverse, optimization, multiple = [
    yaml.safe_load((SCHEMA / f"examples/specification-{name}.yaml").read_text())
    for name in ("forward", "inverse", "optimization", "objectives")
]
model_before = copy.deepcopy(model)
value_records = {
    r["key"]: r for r in records(model["system"]) if r.get("kind") == "measurement"
}
values = {key: record["id"] for key, record in value_records.items()}
valid = [(p, model) for p in (forward, inverse, optimization, multiple)]

# Preference order is document content, preserved even when it is reversed.
# Neither direction declares a particular search or selection workflow.
reversed_preferences = copy.deepcopy(multiple)
reversed_preferences["objectives"].reverse()
reversed_preferences["metadata"].update(
    id=uid("reversed-preferences"), previous=multiple["metadata"]["id"]
)
valid.append((reversed_preferences, model))

# Both omission and an empty collection mean that no objectives are specified.
empty_objectives = copy.deepcopy(forward)
empty_objectives["objectives"] = []
valid.append((empty_objectives, model))

# The second criterion alone can introduce a required Value dependency.
secondary_dependency = copy.deepcopy(optimization)
secondary_dependency["formulations"][0]["expressions"].append(
    dict(id=uid("secondary-area"), kind="reference", target=values["floor_area"])
)
secondary_dependency["objectives"].append(
    dict(expression=uid("secondary-area"), sense="minimize")
)
secondary_dependency["unknowns"].append(values["floor_area"])
valid.append((secondary_dependency, model))

# An empty system admits an empty investigation; no artificial objective or role.
minimal_model = dict(metadata=dict(id=uid("empty-model"), schema_version=MODEL_VERSION))
minimal = dict(
    metadata=dict(id=uid("empty-specification"), schema_version=VERSION),
    model=minimal_model["metadata"]["id"],
)
valid.append((minimal, minimal_model))

# Recorded amounts do not supply assignments, fix unknowns, or initialize a solve.
# This is a hand-authored snapshot, not a claimed solver output.
recorded = copy.deepcopy(model)
recorded["metadata"].update(id=uid("recorded-model"), previous=model["metadata"]["id"])
stored = {
    r["id"]: r for r in records(recorded["system"]) if r.get("kind") == "measurement"
}
for key, amount, units in (
    ("annual_rent_per_home", 30000, "AUD/dwelling/year"),
    ("NOI", 550000, "AUD/year"),
    ("capital_value", 11000000, "AUD"),
):
    stored[values[key]]["quantity"] = dict(magnitude=amount, units=units)
reused = copy.deepcopy(inverse)
reused["metadata"].update(
    id=uid("inverse-recorded"), previous=inverse["metadata"]["id"]
)
reused["model"] = recorded["metadata"]["id"]
reused.pop("estimates")
valid.append((reused, recorded))

# A local Value can be assigned; additional equations share Model Values.
local = copy.deepcopy(optimization)
formulation = local["formulations"][0]
limit = dict(
    id=uid("limit-value"),
    key="rent_limit",
    kind="measurement",
    measure=value_records["annual_rent_per_home"]["measure"],
)
formulation["values"] = [limit]
formulation["expressions"][0]["operands"][1] = dict(
    id=uid("limit-ref"), kind="reference", target=limit["id"]
)
local["assignments"].append(
    dict(value=limit["id"], quantity=dict(magnitude=32000, units="AUD/dwelling/year"))
)
valid.append((local, model))

local_unknown = copy.deepcopy(local)
local_unknown["assignments"].pop()
local_unknown["unknowns"].append(limit["id"])
local_unknown["estimates"].append(
    dict(value=limit["id"], quantity=dict(magnitude=32000, units="AUD/dwelling/year"))
)
valid.append((local_unknown, model))

# Root codes belong to separate Model/Specification collections; identity is still global.
same_code = copy.deepcopy(local)
same_code["formulations"][0]["code"] = model["system"]["formulations"][0]["code"]
valid.append((same_code, model))

# Specification constraints can assert a Model predicate without copying its Expression.
shared = copy.deepcopy(forward)
model_constraint = next(r for r in records(model["system"]) if "predicate" in r)
shared["formulations"] = [
    dict(
        id=uid("shared-formulation"),
        constraints=[
            dict(id=uid("shared-constraint"), predicate=model_constraint["predicate"])
        ],
    )
]
valid.append((shared, model))

# An objective may reference a nested numerical node owned by the input Model.
model_objective = copy.deepcopy(forward)
model_objective["objectives"] = [
    dict(
        expression=next(
            r["id"] for r in records(model["system"]) if r.get("kind") == "reference"
        ),
        sense="minimize",
    )
]
valid.append((model_objective, model))

# Zero and negative estimates are finite content; feasibility is a later concern.
zero = copy.deepcopy(inverse)
zero["assignments"][1]["quantity"]["magnitude"] = 0
zero["estimates"][0]["quantity"]["magnitude"] = -100
valid.append((zero, model))

# Equation/unknown counting is not a schema validity rule: underdetermined is valid.
underdetermined = copy.deepcopy(forward)
rent = underdetermined["assignments"].pop(1)
underdetermined["unknowns"].append(rent["value"])
valid.append((underdetermined, model))

# Literal false is a valid but unsatisfiable additional constraint.
infeasible = copy.deepcopy(forward)
infeasible["formulations"] = [
    dict(
        id=uid("false-formulation"),
        expressions=[dict(id=uid("false-predicate"), kind="boolean", boolean=False)],
        constraints=[
            dict(id=uid("false-constraint"), predicate=uid("false-predicate"))
        ],
    )
]
valid.append((infeasible, model))

for document, snapshot in valid:
    before = copy.deepcopy((document, snapshot))
    validators["Specification"].validate(document)
    validators["Model"].validate(snapshot)
    scope = validate_specification(document, snapshot, VERSION, MODEL_VERSION)
    assert (document, snapshot) == before
assert model == model_before
assert (
    validate_specification(reused, recorded, VERSION, MODEL_VERSION).values[
        values["annual_rent_per_home"]
    ]["quantity"]["magnitude"]
    == 30000
)
validate_specification(
    reused, recorded, VERSION, MODEL_VERSION, history=[inverse["metadata"]]
)

invalid = []


def shape_case(change):
    document = copy.deepcopy(optimization)
    change(document)
    invalid.append(document)


shape_case(lambda p: p.pop("metadata"))
shape_case(lambda p: p["metadata"].pop("id"))
shape_case(lambda p: p["metadata"].pop("schema_version"))
for field in (
    "fixed",
    "initial_guesses",
    "requested_results",
    "constraints",
    "expressions",
    "inputs",
    "policies",
    "solver_options",
    "handling",
    "comparison",
):
    shape_case(lambda p, field=field: p.update({field: []}))
for ref in ("model.name", dict(id=uid("embedded-model")), 42):
    shape_case(lambda p, ref=ref: p.update(model=ref))
for field in ("includes", "cases"):
    for ref in ("specification.name", dict(id=uid("embedded-specification")), 42):
        shape_case(lambda p, field=field, ref=ref: p.update({field: [ref]}))
shape_case(lambda p: p["assignments"][0].pop("value"))
shape_case(lambda p: p["assignments"][0].pop("quantity"))
shape_case(lambda p: p["assignments"][0].update(quantity=None))
shape_case(lambda p: p["assignments"][0].update(value=dict(id=values["homes"])))
shape_case(lambda p: p["assignments"][0]["quantity"].update(magnitude=True))
shape_case(lambda p: p["assignments"][0]["quantity"].pop("units"))
shape_case(lambda p: p["estimates"][0].pop("quantity"))
shape_case(lambda p: p.update(unknowns=[dict(id=values["NOI"])]))
shape_case(lambda p: p.update(unknowns=["NOI"]))
shape_case(lambda p: p["objectives"][0].pop("expression"))
shape_case(lambda p: p["objectives"][0].pop("sense"))
shape_case(lambda p: p["objectives"][0].update(sense="solve"))
shape_case(
    lambda p: p["objectives"][0].update(
        expression=p["formulations"][0]["expressions"][1]
    )
)
shape_case(lambda p: p.update(objectives=p["objectives"][0]))
shape_case(lambda p: p.update(objective=p.pop("objectives")[0]))
shape_case(lambda p: p["objectives"].append(dict(sense="minimize")))
shape_case(lambda p: p["objectives"].append(dict(expression=uid("missing-sense"))))
shape_case(lambda p: p["objectives"][0].update(priority=1))
shape_case(lambda p: p.update(formulations=[uid("formulation-reference")]))
shape_case(lambda p: p.update(settings=dict(iteration_limit=0)))
shape_case(lambda p: p.update(settings=dict(iteration_limit=1.5)))
shape_case(lambda p: p.update(settings=dict(time_limit=-1)))
shape_case(lambda p: p.update(settings=dict(relative_tolerance=2)))
shape_case(lambda p: p.update(settings=dict(solver="arbitrary")))
for document in invalid:
    assert not validators["Specification"].is_valid(document), document

semantic = []


def semantic_case(message, change, *, snapshot=model, base=optimization, **kwargs):
    document = copy.deepcopy(base)
    change(document)
    semantic.append((document, snapshot, message, kwargs))


semantic_case(
    "unsupported Specification schema version",
    lambda p: p["metadata"].update(schema_version="99"),
)
semantic_case(
    "input Model revision mismatch", lambda p: p.update(model=uid("other-model"))
)
semantic_case("requires an input Model", lambda p: p.pop("model"))
semantic_case(
    "duplicate identity", lambda p: p["metadata"].update(id=model["metadata"]["id"])
)
semantic_case(
    "self predecessor", lambda p: p["metadata"].update(previous=p["metadata"]["id"])
)
semantic_case(
    "predecessor targets current scope",
    lambda p: p["metadata"].update(previous=model["metadata"]["id"]),
)
semantic_case(
    "revision history cycle",
    lambda p: p["metadata"].update(previous=uid("ancestor")),
    history=[
        dict(
            id=uid("ancestor"),
            schema_version=VERSION,
            previous=optimization["metadata"]["id"],
        )
    ],
)
semantic_case(
    "non-Value role target",
    lambda p: p["assignments"][0].update(value=model["system"]["entities"][0]["id"]),
)
semantic_case(
    "non-Value role target", lambda p: p["unknowns"].append(uid("missing-value"))
)
semantic_case(
    "non-Value role target",
    lambda p: p["estimates"][0].update(value=uid("missing-estimate")),
)
semantic_case(
    "duplicate assignments target",
    lambda p: p["assignments"].append(copy.deepcopy(p["assignments"][0])),
)
semantic_case(
    "duplicate estimates target",
    lambda p: p["estimates"].append(copy.deepcopy(p["estimates"][0])),
)
semantic_case("duplicate unknown", lambda p: p["unknowns"].append(p["unknowns"][0]))
semantic_case(
    "roles overlap", lambda p: p["unknowns"].append(p["assignments"][0]["value"])
)
semantic_case(
    "not an unknown",
    lambda p: p["estimates"].append(copy.deepcopy(p["assignments"][0])),
)
semantic_case("missing solve role", lambda p: p["assignments"].pop())
semantic_case("missing solve role", lambda p: p["unknowns"].remove(values["NOI"]))
semantic_case(
    "missing solve role",
    lambda p: p["assignments"].pop(1),
    snapshot=recorded,
    base=reused,
)
semantic_case(
    "non-finite supplied magnitude",
    lambda p: p["assignments"][0]["quantity"].update(magnitude=float("inf")),
)
semantic_case(
    "non-finite supplied magnitude",
    lambda p: p["estimates"][0]["quantity"].update(magnitude=float("nan")),
)
semantic_case(
    "unit compatibility requires",
    lambda p: p["assignments"][0]["quantity"].update(units="m^2"),
)
semantic_case(
    "unit compatibility requires",
    lambda p: p["estimates"][0]["quantity"].update(units="USD/dwelling/year"),
)
semantic_case(
    "unknown or non-Expression objective",
    lambda p: p["objectives"][0].update(expression=values["NOI"]),
)
semantic_case(
    "scalar numerical",
    lambda p: p["objectives"][0].update(expression=model_constraint["predicate"]),
)
query = next(r for r in records(model["system"]) if r.get("kind") == "query")
semantic_case(
    "scalar numerical", lambda p: p["objectives"][0].update(expression=query["id"])
)
semantic_case(
    "unknown or non-Expression objective",
    lambda p: p["objectives"][1].update(expression=values["NOI"]),
    base=multiple,
)
semantic_case(
    "scalar numerical",
    lambda p: p["objectives"][1].update(expression=model_constraint["predicate"]),
    base=multiple,
)
semantic_case(
    "scalar numerical",
    lambda p: p["objectives"][1].update(expression=query["id"]),
    base=multiple,
)
semantic_case(
    "missing solve role",
    lambda p: p["unknowns"].remove(values["floor_area"]),
    base=secondary_dependency,
)
semantic_case(
    "duplicate identity",
    lambda p: p["formulations"][0].update(id=model["system"]["formulations"][0]["id"]),
)
semantic_case(
    "duplicate identity",
    lambda p: p["formulations"][0].update(values=[copy.deepcopy(value_records["NOI"])]),
)
semantic_case(
    "unknown Value reference",
    lambda p: p["formulations"][0]["expressions"][1].update(
        target=uid("missing-symbol")
    ),
)
semantic_case("positive and finite", lambda p: p.update(settings=dict(time_limit=0)))
semantic_case(
    "positive and finite", lambda p: p.update(settings=dict(relative_tolerance=0))
)
semantic_case(
    "positive and finite", lambda p: p.update(settings=dict(time_limit=float("inf")))
)
semantic_case("less than one", lambda p: p.update(settings=dict(relative_tolerance=1)))

# A previously unused query cannot be promoted to imposed mathematics and then
# silently bypass dependency/role discovery by this bounded checker.
aggregate = next(r for r in records(model["system"]) if r.get("kind") == "call")
semantic_case(
    "graph adapter", lambda p: p["objectives"][0].update(expression=aggregate["id"])
)

for document, snapshot, message, kwargs in semantic:
    validators["Specification"].validate(document)
    validators["Model"].validate(snapshot)
    try:
        validate_specification(document, snapshot, VERSION, MODEL_VERSION, **kwargs)
    except ContractError as error:
        assert message in str(error), (message, str(error))
    else:
        raise AssertionError(f"Missing Specification rejection: {message}")


def nonempty(content):
    if isinstance(content, dict):
        return {
            k: v
            for k, raw in content.items()
            if (v := nonempty(raw)) not in (None, [], {})
        }
    if isinstance(content, list):
        return [nonempty(x) for x in content]
    return content


with TemporaryDirectory(prefix="rk-specification-") as temp:
    path = Path(temp) / "records.py"
    path.write_text(
        subprocess.check_output(
            [str(BIN / "gen-python"), str(SCHEMA / "specification.yaml")], text=True
        )
    )
    spec = importlib.util.spec_from_file_location("rk_specification_records", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for document, snapshot in valid:
        record = json_loader.loads(
            json.dumps(document), target_class=module.Specification
        )
        assert isinstance(record.metadata, module.Metadata)
        assert isinstance(record.metadata.id, module.MetadataId)
        assert isinstance(record.model, module.MetadataId)
        assert all(isinstance(ref, module.ValueId) for ref in record.unknowns)
        for assignment in record.assignments + record.estimates:
            assert isinstance(assignment, module.Assignment)
            assert isinstance(assignment.value, module.ValueId)
            assert isinstance(assignment.quantity, module.Quantity)
        for objective in record.objectives:
            assert isinstance(objective.expression, module.ExpressionId)
        after = json.loads(json_dumper.dumps(record, inject_type=False))
        assert after.get("objectives", []) == document.get("objectives", [])
        assert nonempty(document) == nonempty(after), (document, after)
        validators["Specification"].validate(after)
        validate_specification(after, snapshot, VERSION, MODEL_VERSION)
        restored = json_loader.loads(
            json.dumps(after), target_class=module.Specification
        )
        assert json.loads(json_dumper.dumps(restored, inject_type=False)) == after

    from specification_composition_cases import check_composition

    check_composition(SCHEMA, validators, module, model, VERSION, MODEL_VERSION)

print(
    f"Passed {len(validators)} generated schemas, {len(valid)} valid Specifications, {len(invalid)} structural rejections,"
)
print(
    f"{len(semantic)} bounded semantic rejections, and {len(valid)} native Specification round trips."
)
print(
    "No solver executed. Unit conversion, imposed query dependency resolution, and Run publication require adapters."
)
