"""Validate Formulation ownership/references and generated LinkML Python round trips.

Run in the pinned LinkML environment used by validate.py. The enclosing fixture
is not a Model schema. These checks do not evaluate constraints or run a solver.
"""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import UUID, NAMESPACE_URL, uuid5

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.loaders import json_loader
from linkml_runtime.utils.schemaview import SchemaView
import yaml

import _library

from rangekeeper.model.formulation.preparation import prepare_formulations
from rangekeeper.errors import ContractError

SCHEMA = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent


def uid(name):
    return str(uuid5(NAMESPACE_URL, "rk-formulation-check/" + name))


validators = {}
for name, file in (
    ("Formulation", "formulation"),
    ("Binding", "formulation"),
    ("Definitions", "definitions"),
    ("Entity", "entity"),
    ("Relationship", "relationship"),
    ("Assembly", "assembly"),
):
    generated = json.loads(_library.schema_json(name))
    cls = validator_for(generated)
    cls.check_schema(generated)
    validators[name] = cls(generated, format_checker=FormatChecker())

view = SchemaView(str(SCHEMA / "formulation.yaml"))
assert view.get_identifier_slot("Formulation").name == "id"
assert view.get_identifier_slot("Binding") is None
field = view.induced_slot("value", "Binding")
assert field.range == "Value" and field.inlined is False
for name, target in (
    ("bindings", "Binding"),
    ("values", "Value"),
    ("expressions", "Expression"),
    ("constraints", "Constraint"),
    ("formulations", "Formulation"),
):
    field = view.induced_slot(name, "Formulation")
    assert field.range == target and field.inlined and field.inlined_as_list
    assert field.multivalued and not field.list_elements_ordered


def structural(document):
    validators["Definitions"].validate(document.get("definitions", {}))
    for collection, cls in (
        ("entities", "Entity"),
        ("relationships", "Relationship"),
        ("assemblies", "Assembly"),
        ("formulations", "Formulation"),
    ):
        for record in document.get(collection) or []:
            validators[cls].validate(record)


fixture = yaml.safe_load((SCHEMA / "examples/valuation-formulations.yaml").read_text())
scalar = yaml.safe_load((SCHEMA / "examples/valuation-expressions.yaml").read_text())
root = fixture["formulations"][0]
income, capital = root["formulations"]
noi = root["values"][0]
symbol = noi["id"]
valid = [fixture, dict(formulations=[dict(id=uid("empty"))])]

# The Formulation arrangement preserves the original mathematics and Value identities.
assert [b["expressions"][0] for b in root["formulations"]] == scalar["expressions"]
assert [b["constraints"][0]["predicate"] for b in root["formulations"]] == [
    c["predicate"] for c in scalar["constraints"]
]
assert [b["constraints"][0]["id"] for b in root["formulations"]] == [
    c["id"] for c in scalar["constraints"]
]
assert noi == next(
    v for v in scalar["entities"][0]["characteristics"]["values"] if v["id"] == symbol
)

renamed = copy.deepcopy(fixture)
renamed["formulations"][0]["code"] = "renamed"
renamed["formulations"][0]["bindings"][0]["name"] = "dwellings"
renamed["formulations"][0]["values"][0]["key"] = "net_income"
valid.append(renamed)

reordered = copy.deepcopy(fixture)
reordered["formulations"][0]["formulations"].reverse()
valid.append(reordered)

# Siblings share a Value owned by one sibling; containment does not hide it.
sibling = copy.deepcopy(fixture)
sibling["formulations"][0]["formulations"][0]["values"] = sibling["formulations"][
    0
].pop("values")
valid.append(sibling)

# Distinct constraints can assert one predicate without copying its Expression.
shared = copy.deepcopy(fixture)
shared["formulations"][0]["constraints"] = [
    dict(id=uid("shared-predicate"), predicate=income["expressions"][0]["id"])
]
valid.append(shared)

# Several names can alias a Value. A binding can also expose a locally owned Value.
aliases = copy.deepcopy(fixture)
aliases["formulations"][0]["bindings"].extend(
    [
        dict(name="net_income", value=symbol),
        dict(name="NOI", value=symbol),
    ]
)
valid.append(aliases)

# Zero and an unresolved amount remain distinct and neither changes symbol identity.
resolved = copy.deepcopy(fixture)
resolved["formulations"][0]["values"][0]["quantity"] = dict(
    magnitude=0, units="AUD/year"
)
valid.append(resolved)

# Relationship-owned Values are also eligible shared symbols.
relationship_case = copy.deepcopy(fixture)
graph = json.loads((SCHEMA / "examples/structural-graph.json").read_text())
relationship = copy.deepcopy(graph["relationships"][0])
relationship_case["definitions"]["taxonomies"] = copy.deepcopy(
    graph["definitions"]["taxonomies"]
)
relationship.update(
    id=uid("relationship"),
    source=fixture["entities"][0]["id"],
    target=fixture["entities"][0]["id"],
)
relationship["characteristics"] = dict(
    values=[relationship_case["formulations"][0].pop("values")[0]]
)
relationship_case["relationships"] = [relationship]
valid.append(relationship_case)

# False predicates are valid declarations even though imposing one is infeasible.
false_case = dict(
    formulations=[
        dict(
            id=uid("false-formulation"),
            expressions=[dict(id=uid("false"), kind="boolean", boolean=False)],
            constraints=[dict(id=uid("false-assertion"), predicate=uid("false"))],
        )
    ]
)
valid.append(false_case)

for document in valid:
    structural(document)
    prepare_formulations(document)
assert prepare_formulations(fixture)[0].values[UUID(symbol)] is noi
assert (
    prepare_formulations(resolved)[0].domains[UUID(symbol)]
    == prepare_formulations(fixture)[0].domains[UUID(symbol)]
)

invalid = []
for field in ("id",):
    bad = copy.deepcopy(root)
    bad.pop(field)
    invalid.append(("Formulation", bad))
for field in ("name", "value"):
    bad = copy.deepcopy(root["bindings"][0])
    bad.pop(field)
    invalid.append(("Binding", bad))
for reference in ("NOI", "valuation.NOI", dict(id=symbol), 42, None):
    invalid.append(("Binding", dict(name="income", value=reference)))
for name in ("", " ", " leading", "trailing "):
    invalid.append(("Binding", dict(name=name, value=symbol)))
    invalid.append(("Formulation", dict(id=uid("code"), code=name)))
for field in ("bindings", "values", "expressions", "constraints", "formulations"):
    bad = copy.deepcopy(root)
    bad[field] = {"named": (root.get(field) or [income])[0]}
    invalid.append(("Formulation", bad))
for field, value in (
    ("template", uid("future-template")),
    ("active", False),
    ("fixed", {symbol: 0}),
    ("objective", symbol),
    ("solver_options", {}),
):
    invalid.append(("Formulation", dict(id=uid("extra"), **{field: value})))
# A legacy child collection is rejected rather than silently ignored.
bad = copy.deepcopy(root)
bad["blocks"] = bad.pop("formulations")
invalid.append(("Formulation", bad))
invalid.append(("Formulation", dict(id=uid("child-ref"), formulations=[income["id"]])))
invalid.append(("Formulation", dict(id=uid("local-ref"), values=[UUID(symbol)])))
bad = copy.deepcopy(root)
bad["formulations"][0]["expressions"][0]["kind"] = "unknown"
invalid.append(("Formulation", bad))
bad = copy.deepcopy(root)
bad["values"][0].pop("measure")
invalid.append(("Formulation", bad))
bad = copy.deepcopy(root)
bad["constraints"] = [dict(id=uid("malformed-constraint"), predicate="income")]
invalid.append(("Formulation", bad))
for cls, record in invalid:
    assert not validators[cls].is_valid(record), (cls, record)

semantic = []


def case(message, change):
    document = copy.deepcopy(fixture)
    change(document, document["formulations"][0])
    semantic.append((document, message))


case("unknown or non-Value", lambda d, b: b["bindings"][0].update(value=uid("missing")))
case(
    "unknown or non-Value",
    lambda d, b: b["bindings"][0].update(value=d["entities"][0]["id"]),
)
case(
    "unknown or non-Value",
    lambda d, b: b["bindings"][0].update(
        value=b["formulations"][0]["expressions"][0]["id"]
    ),
)
case(
    "duplicate Binding name",
    lambda d, b: b["bindings"].append(dict(b["bindings"][0], value=symbol)),
)
case(
    "duplicate local Value key",
    lambda d, b: b["values"].append(dict(b["values"][0], id=uid("same-key"))),
)
case(
    "duplicate sibling Formulation code",
    lambda d, b: b["formulations"][1].update(code=b["formulations"][0]["code"]),
)
case(
    "duplicate sibling Formulation code",
    lambda d, b: d["formulations"].append(dict(id=uid("root-code"), code=b["code"])),
)
case(
    "duplicate Constraint code",
    lambda d, b: b["formulations"][0]["constraints"].append(
        dict(b["formulations"][0]["constraints"][0], id=uid("constraint-code"))
    ),
)
case(
    "duplicate identity",
    lambda d, b: b["values"].append(
        copy.deepcopy(d["entities"][0]["characteristics"]["values"][0])
    ),
)
case(
    "duplicate identity",
    lambda d, b: d["formulations"].append(copy.deepcopy(b["formulations"][0])),
)
case(
    "duplicate identity",
    lambda d, b: b["formulations"][1].update(
        formulations=[copy.deepcopy(b["formulations"][0])]
    ),
)
case(
    "duplicate identity",
    lambda d, b: b["formulations"][1]["expressions"].append(
        copy.deepcopy(b["formulations"][0]["expressions"][0])
    ),
)
case(
    "duplicate identity",
    lambda d, b: b["formulations"][0]["constraints"][0].update(id=b["id"]),
)
case(
    "unknown Value Measure",
    lambda d, b: b["values"][0].update(measure=uid("missing-measure")),
)
case(
    "unknown Value or Movement reference",
    lambda d, b: b["formulations"][0]["expressions"][0]["operands"][0].update(
        target=dict(target=b["id"])
    ),
)
case(
    "unknown or non-Expression",
    lambda d, b: b["formulations"][0]["constraints"][0].update(predicate=symbol),
)
case(
    "must be Boolean",
    lambda d, b: b["formulations"][0]["constraints"][0].update(
        predicate=b["formulations"][0]["expressions"][0]["operands"][0]["id"]
    ),
)
case(
    "root Expressions or Constraints",
    lambda d, b: d.update(
        expressions=[dict(id=uid("root-expression"), kind="boolean", boolean=True)]
    ),
)
case(
    "non-finite Value",
    lambda d, b: b["values"][0].update(
        quantity=dict(magnitude=float("inf"), units="AUD/year")
    ),
)
for document, message in semantic:
    structural(document)
    try:
        prepare_formulations(document)
    except ContractError as error:
        assert message in str(error), (message, str(error))
    else:
        raise AssertionError(f"Missing Formulation semantic rejection: {message}")

# A YAML anchor can create a cycle before JSON/schema validation is possible.
cycle = dict(id=uid("cycle"))
cycle["formulations"] = [cycle]
try:
    prepare_formulations(dict(formulations=[cycle]))
except ContractError as error:
    assert "cyclic containment" in str(error)
else:
    raise AssertionError("Missing cyclic containment rejection")

roundtrips = 0
with TemporaryDirectory(prefix="rk-formulation-") as temp:
    path = Path(temp) / "records.py"
    path.write_text(
        subprocess.check_output(
            [str(BIN / "gen-python"), str(SCHEMA / "formulation.yaml")],
            text=True,
        )
    )
    spec = importlib.util.spec_from_file_location("rk_formulation_records", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for document in valid:
        restored_document = copy.deepcopy(document)
        restored_document["formulations"] = []
        for before in document["formulations"]:
            record = json_loader.loads(
                json.dumps(before), target_class=module.Formulation
            )
            after = json.loads(json_dumper.dumps(record, inject_type=False))
            assert before == after, (before, after)
            assert isinstance(record.id, module.FormulationId)
            if record.bindings:
                assert isinstance(record.bindings[0].value, module.ValueId)
            if record.formulations:
                assert isinstance(record.formulations[0], module.Formulation)
            validators["Formulation"].validate(after)
            restored_document["formulations"].append(after)
            roundtrips += 1
        prepare_formulations(restored_document)

print(
    f"Passed {len(validators)} generated schemas, {len(valid)} valid fixture scopes, {len(invalid)} structural rejections,"
)
print(
    f"{len(semantic)+1} bounded semantic rejections, and {roundtrips} native Formulation round trips."
)
print(
    "Formulation compilation, constraint satisfaction, unit inference, and solving remain unimplemented."
)
