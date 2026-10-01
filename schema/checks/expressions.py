"""Validate expression/function/query/constraint records and Python round trips.

Use the pinned LinkML environment used by validate.py. Semantic checks are bounded
conformance fixtures, not a query executor, unit checker, evaluator, or solver.
"""

import copy
import importlib.util
import json
from pathlib import Path
import re
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

from expression_contract import Scope, ContractError

SCHEMA = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
validators = {}
for name, file in [
    ("Expression", "expression"),
    ("Constraint", "constraint"),
    ("Function", "function"),
    ("Domain", "function"),
    ("Query", "query"),
    ("Definitions", "definitions"),
    ("Entity", "entity"),
    ("Relationship", "relationship"),
    ("Assembly", "assembly"),
]:
    document = json.loads(
        subprocess.check_output(
            [
                str(BIN / "gen-json-schema"),
                "--closed",
                "--top-class",
                name,
                str(SCHEMA / f"{file}.yaml"),
            ],
            text=True,
        )
    )
    cls = validator_for(document)
    cls.check_schema(document)
    validators[name] = cls(document, format_checker=FormatChecker())
view = SchemaView(str(SCHEMA / "constraint.yaml"))
assert view.get_identifier_slot("Constraint").name == "id"
assert view.induced_slot("operands", "Expression").list_elements_ordered
assert view.induced_slot("arguments", "Call").list_elements_ordered
assert view.induced_slot("steps", "Query").list_elements_ordered
for owner, slot, target in [
    ("Expression", "target", "Value"),
    ("Constraint", "predicate", "Expression"),
    ("Call", "function", "Function"),
    ("Query", "starting_at", "Entity"),
    ("Traversal", "classification", "Classification"),
]:
    field = view.induced_slot(slot, owner)
    assert field.range == target and field.inlined is False

valid = []
fixtures = []
for name in ("valuation-expressions", "query-aggregation", "function-expressions"):
    fixture = yaml.safe_load((SCHEMA / f"examples/{name}.yaml").read_text())
    fixtures.append(fixture)
    validators["Definitions"].validate(fixture["definitions"])
    for collection, cls in [
        ("entities", "Entity"),
        ("relationships", "Relationship"),
        ("assemblies", "Assembly"),
        ("functions", "Function"),
        ("expressions", "Expression"),
        ("constraints", "Constraint"),
    ]:
        for record in fixture.get(collection, []):
            validators[cls].validate(record)
            if cls in ("Function", "Expression", "Constraint"):
                valid.append((cls, record))
    for record in fixture.get("input_domains", []):
        validators["Domain"].validate(record["domain"])
        valid.append(("Domain", record["domain"]))
    scope = Scope(fixture)
    scope.validate_constraints(fixture.get("constraints", []), fixture["expressions"])

scalar, graph, rich = fixtures
# A date result remains valid without a date literal node.
assert Scope(rich).expression(rich["expressions"][2]) == dict(kind="date")
readme = [
    yaml.safe_load(block)
    for block in re.findall(
        r"```yaml\n(.*?)```", (SCHEMA / "README.md").read_text(), re.DOTALL
    )
    if "kind: binary" in block
]
assert len(readme) == 1
Scope(scalar).expression(readme[0])
valid.extend(("Expression", item) for item in readme)
readme_constraints = [
    yaml.safe_load(block)
    for block in re.findall(
        r"```yaml\n(.*?)```", (SCHEMA / "README.md").read_text(), re.DOTALL
    )
    if "\npredicate: " in block
]
assert len(readme_constraints) == 1
Scope(scalar).validate_constraints(readme_constraints, scalar["expressions"])
valid.extend(("Constraint", item) for item in readme_constraints)
valid.extend(
    ("Domain", record)
    for record in (
        dict(kind="quantity"),
        dict(kind="quantity", units="m^2"),
        dict(
            kind="collection",
            collection_kind="sequence",
            item_domain=dict(
                kind="collection",
                collection_kind="set",
                item_domain=dict(kind="quantity", units="AUD"),
            ),
        ),
    )
)


def expression(name, kind, **content):
    return dict(
        id=str(uuid5(NAMESPACE_URL, "rk-expression-check/" + name)),
        kind=kind,
        **content,
    )


def quantity(name, magnitude, units="dimensionless"):
    return expression(name, "quantity", quantity=dict(magnitude=magnitude, units=units))


left = quantity("left", 10)
right = quantity("right", 2)
false = expression("false", "boolean", boolean=False)
true = expression("true", "boolean", boolean=True)
reference = expression(
    "reference",
    "reference",
    target=scalar["entities"][0]["characteristics"]["values"][0]["id"],
)
for node in [
    left,
    right,
    false,
    true,
    reference,
    quantity("zero", 0),
    quantity("negative", -0.125),
    quantity("unitful", 20, "m^2"),
]:
    valid.append(("Expression", node))
for operator in view.get_enum("Operator").permissible_values:
    if operator in ("negate", "logical_not"):
        node = expression(
            operator,
            "unary",
            operator=operator,
            operand=false if operator == "logical_not" else left,
        )
    else:
        operands = (
            [true, false]
            if operator in ("logical_and", "logical_or")
            else [left, right]
        )
        node = expression(operator, "binary", operator=operator, operands=operands)
    Scope(scalar).expression(node)
    valid.append(("Expression", node))
repeated = copy.deepcopy(reference)
repeated["id"] = expression("repeated", "reference")["id"]
valid.append(
    (
        "Expression",
        expression(
            "repeated-reference",
            "binary",
            operator="add",
            operands=[reference, repeated],
        ),
    )
)

# Query shape variants: reverse traversal, explicit multiplicity, Measure projection,
# root projection, label filtering, and explicit missing-characteristic omission.
query = graph["expressions"][0]["call"]["arguments"][0]["query"]
for duplicate in ("distinct", "preserve"):
    q = copy.deepcopy(query)
    q["duplicates"] = duplicate
    valid.append(("Query", q))
q = copy.deepcopy(query)
q["steps"][0]["direction"] = "incoming"
valid.append(("Query", q))
q = copy.deepcopy(query)
q["projection"].pop("key")
q["projection"]["measure"] = graph["definitions"]["measures"][0]["id"]
q["projection"]["cardinality"] = "many"
q["projection"]["missing"] = "omit"
valid.append(("Query", q))
q = dict(
    starting_at=graph["entities"][0]["id"],
    projection=dict(kind="entity"),
    duplicates="distinct",
)
valid.append(("Query", q))
q = copy.deepcopy(query)
q["filter"]["labels"] = [dict(key="use", classification=q["filter"]["classification"])]
valid.append(("Query", q))
valid.extend(
    ("Query", node["query"])
    for node in [graph["expressions"][1]["call"]["named_arguments"][0]["expression"]]
)


def constraint(name, predicate, **metadata):
    return dict(
        id=str(uuid5(NAMESPACE_URL, "rk-constraint-check/" + name)),
        predicate=predicate,
        **metadata,
    )


minimal = constraint("minimal", scalar["expressions"][0]["id"])
Scope(scalar).validate_constraints([minimal], scalar["expressions"])
valid.append(("Constraint", minimal))

# Predicate validity is independent of current truth and expression syntax form.
inequality = expression(
    "budget-predicate",
    "binary",
    operator="less_than_or_equal",
    operands=[quantity("cost", 500, "AUD"), quantity("budget", 1000, "AUD")],
)
logical = expression(
    "logical-predicate",
    "binary",
    operator="logical_and",
    operands=[
        inequality,
        expression("not-false", "unary", operator="logical_not", operand=false),
    ],
)
boolean_function = dict(
    id=str(uuid5(NAMESPACE_URL, "rk-constraint-check/boolean-function")),
    code="constant_true",
    name="Constant true",
    version="1",
    result=dict(kind="boolean"),
    semantics="Return the Boolean literal true.",
    unit_rule="Boolean results have no units.",
)
boolean_call = expression(
    "boolean-call", "call", call=dict(function=boolean_function["id"])
)
valid.append(("Function", boolean_function))
for label, root, targets in [
    ("false", false, [false["id"]]),
    ("inequality", inequality, [inequality["id"]]),
    # Nested predicates and reuse of the same predicate are valid UUID references.
    ("logical", logical, [logical["id"], inequality["id"], false["id"], logical["id"]]),
    ("call", boolean_call, [boolean_call["id"]]),
]:
    fixture = copy.deepcopy(scalar)
    fixture["functions"] = [boolean_function]
    records = [constraint(f"{label}-{i}", target) for i, target in enumerate(targets)]
    Scope(fixture).validate_constraints(records, [root])
    valid.append(("Expression", root))
    valid.extend(("Constraint", record) for record in records)

invalid = []


def reject(cls, record):
    invalid.append((cls, record))


for field in ("id", "predicate"):
    bad = dict(minimal)
    bad.pop(field)
    reject("Constraint", bad)
    for content in (None, "not-a-uuid", False):
        reject("Constraint", dict(minimal, **{field: content}))
for predicate in (scalar["expressions"][0], [minimal["predicate"]]):
    reject("Constraint", dict(minimal, predicate=predicate))
for metadata in (
    dict(code=" "),
    dict(code=" trailing "),
    dict(name=" "),
    dict(tolerance=0.001),
    dict(satisfied=True),
):
    reject("Constraint", dict(minimal, **metadata))

# Reject mixed content and null payloads across every expression kind.
representatives = {
    record["kind"]: record for cls, record in valid if cls == "Expression"
}
representatives["query"] = graph["expressions"][0]["call"]["arguments"][0]
for record in representatives.values():
    for field in ("id", "kind"):
        bad = copy.deepcopy(record)
        bad.pop(field)
        reject("Expression", bad)
    for field in set(record) - {"id", "kind"}:
        bad = copy.deepcopy(record)
        bad[field] = None
        reject("Expression", bad)
    foreign = "boolean" if record["kind"] != "boolean" else "quantity"
    bad = copy.deepcopy(record)
    bad[foreign] = (
        False if foreign == "boolean" else dict(magnitude=1, units="dimensionless")
    )
    reject("Expression", bad)
for operands in ([], [left], [left, right, left], {left["id"]: left}):
    reject(
        "Expression",
        expression("bad-arity", "binary", operator="divide", operands=operands),
    )
for node in [
    expression("bad-unary", "unary", operator="add", operand=left),
    expression("bad-binary", "binary", operator="negate", operands=[left, right]),
    expression("bad-operator", "binary", operator="eval", operands=[left, right]),
    quantity("bad-magnitude", True),
    expression("legacy-number", "number", number=10),
    expression("legacy-operation", "operation", operator="add", operands=[left, right]),
    expression("missing-units", "quantity", quantity=dict(magnitude=10)),
    expression("missing-magnitude", "quantity", quantity=dict(units="m^2")),
    expression(
        "null-magnitude", "quantity", quantity=dict(magnitude=None, units="m^2")
    ),
    dict(
        quantity("literal-measure", 10),
        measure=scalar["definitions"]["measures"][0]["id"],
    ),
    expression("bad-bool", "boolean", boolean=0),
    expression("deferred-date", "date", date="2026-09-30"),
    expression("deferred-string", "string", text=""),
    expression("bad-reference", "reference", target="annual_rent"),
    dict(left, source_code="print(1)"),
]:
    reject("Expression", node)
for field in ("function",):
    bad = copy.deepcopy(rich["expressions"][0])
    bad["call"][field] = None
    reject("Expression", bad)
for selection in [
    dict(kind="member", base=reference),
    dict(kind="member", base=reference, member="end_date", index=left),
    dict(kind="index", base=reference),
    dict(kind="index", base=reference, index=left, member="x"),
]:
    reject("Expression", expression("bad-selection", "selection", selection=selection))
for field in ("starting_at", "projection", "duplicates"):
    bad = copy.deepcopy(query)
    bad.pop(field)
    reject("Query", bad)
for projection in [
    dict(kind="value", cardinality="one", missing="error"),
    dict(
        kind="value",
        key="rent",
        measure=graph["definitions"]["measures"][0]["id"],
        cardinality="one",
        missing="error",
    ),
    dict(kind="entity", key="rent"),
    dict(kind="value", key="rent", cardinality="one"),
    dict(kind="value", key="rent", missing="error"),
]:
    bad = copy.deepcopy(query)
    bad["projection"] = projection
    reject("Query", bad)
for step in [
    dict(kind="relationship", depth="direct", direction="outgoing"),
    dict(kind="membership", depth="direct", direction="outgoing"),
    dict(
        kind="relationship",
        depth="transitive",
        classification=query["steps"][0]["classification"],
    ),
    dict(kind="membership", depth="unbounded"),
]:
    bad = copy.deepcopy(query)
    bad["steps"] = [step]
    reject("Query", bad)
bad = copy.deepcopy(query)
bad["filter"]["expression"] = left
reject("Query", bad)
bad = copy.deepcopy(query)
bad["duplicates"] = "implicit"
reject("Query", bad)
bad = copy.deepcopy(query)
bad["steps"][0]["relationship"] = bad["steps"][0].pop("classification")
reject("Query", bad)
for domain in [
    dict(kind="collection"),
    dict(kind="collection", items=dict(kind="number")),
    dict(kind="collection", item_type=dict(kind="number")),
    dict(kind="number", item_domain=dict(kind="number")),
    dict(kind="boolean", measure=graph["definitions"]["measures"][0]["id"]),
    dict(kind="number", collection_kind="sequence"),
    dict(kind="number", units="m^2"),
    dict(kind="quantity", measure=graph["definitions"]["measures"][0]["id"]),
]:
    reject("Domain", domain)
# Earlier field names are not aliases, including inside nested records.
for old, current in (("type", "domain"), ("binding", "kind")):
    bad = copy.deepcopy(graph["functions"][0])
    parameter = bad["parameters"][0]
    parameter[old] = parameter.pop(current)
    reject("Function", bad)
for field in ("id", "version", "semantics", "unit_rule", "result"):
    bad = copy.deepcopy(graph["functions"][0])
    bad.pop(field)
    reject("Function", bad)
for cls, record in valid:
    validators[cls].validate(record)
for cls, record in invalid:
    assert not validators[cls].is_valid(
        record
    ), f"Unexpectedly accepted {cls}: {record}"

# Cross-record and domain errors are deliberately distinct from structural checks.
semantic = []


def semantic_case(fixture, node, message):
    semantic.append((fixture, node, message))


scope = Scope(scalar)
area_domain = scope.expression(quantity("area", 20, "m^2"))
assert area_domain == dict(kind="quantity", units="m^2")
assert not scope.matches(area_domain, dict(kind="number"))
assert not scope.matches(area_domain, dict(kind="measurement"))
assert scope.matches(area_domain, dict(kind="quantity", units="m^2"))
assert scope.matches(scope.expression(left), dict(kind="number"))
product = expression(
    "product", "binary", operator="multiply", operands=[reference, right]
)
assert Scope(scalar).expression(product) == dict(kind="quantity")
for magnitude in (float("nan"), float("inf")):
    semantic_case(scalar, quantity("nonfinite", magnitude), "non-finite magnitude")

base = rich["expressions"][0]
bad = copy.deepcopy(base)
bad["call"]["function"] = left["id"]
semantic_case(rich, bad, "unknown Function")
bad = copy.deepcopy(base)
bad["call"].pop("arguments")
semantic_case(rich, bad, "missing required")
bad = copy.deepcopy(base)
bad["call"]["arguments"] = [left]
semantic_case(rich, bad, "domain mismatch")
bad = copy.deepcopy(base)
bad["call"]["arguments"].append(right)
semantic_case(rich, bad, "too many positional")
bad = copy.deepcopy(base)
bad["call"]["named_arguments"] = [dict(name="flow", expression=right)]
semantic_case(rich, bad, "more than once")
bad = copy.deepcopy(base)
bad["call"]["named_arguments"] = [dict(name="unknown", expression=right)]
semantic_case(rich, bad, "unknown named")
bad = copy.deepcopy(rich["expressions"][1])
bad["call"]["named_arguments"].append(copy.deepcopy(bad["call"]["named_arguments"][0]))
semantic_case(rich, bad, "more than once")
bad = copy.deepcopy(rich["expressions"][2])
bad["selection"]["member"] = "not_a_member"
semantic_case(rich, bad, "unknown or unsupported member")
bad = copy.deepcopy(rich["expressions"][4])
bad["selection"]["index"]["quantity"]["magnitude"] = 0.5
semantic_case(rich, bad, "integer sequence index")
bad = copy.deepcopy(rich["expressions"][4])
bad["selection"]["index"]["quantity"]["units"] = "m^2"
semantic_case(rich, bad, "numerical index required")
bad = copy.deepcopy(rich["expressions"][4])
bad["selection"]["base"] = copy.deepcopy(
    graph["expressions"][0]["call"]["arguments"][0]
)
semantic_case(graph, bad, "ordered sequence")
semantic_case(
    scalar, expression("unknown", "reference", target=left["id"]), "unknown Value"
)
semantic_case(
    scalar,
    expression("bad-types", "binary", operator="add", operands=[true, right]),
    "numerical operands",
)
semantic_case(
    scalar,
    expression("bad-logic", "binary", operator="logical_and", operands=[true, right]),
    "Boolean operands",
)
semantic_case(
    scalar,
    expression("repeated-id", "binary", operator="add", operands=[left, left]),
    "duplicate Expression",
)
bad = copy.deepcopy(graph["expressions"][0])
bad["call"]["arguments"][0]["query"]["starting_at"] = left["id"]
semantic_case(graph, bad, "starting Entity")
for fixture, node, message in semantic:
    validators["Expression"].validate(node)
    try:
        Scope(fixture).expression(node)
    except ContractError as error:
        assert message in str(error), (message, str(error))
    else:
        raise AssertionError(f"Missing semantic rejection: {message}")
for mutate in (
    "duplicate_parameter",
    "required_order",
    "named_order",
    "empty_collection",
):
    bad = copy.deepcopy(rich if mutate != "empty_collection" else graph)
    function = (
        bad["functions"][1] if mutate != "empty_collection" else bad["functions"][0]
    )
    if mutate == "duplicate_parameter":
        function["parameters"].append(copy.deepcopy(function["parameters"][0]))
    elif mutate == "required_order":
        function["parameters"][0]["required"] = False
        function["parameters"][1].update(required=True, kind="positional_or_named")
    elif mutate == "named_order":
        function["parameters"][0]["kind"] = "named_only"
        function["parameters"][1]["kind"] = "positional_or_named"
    else:
        function.pop("empty_collection")
    validators["Function"].validate(function)
    try:
        Scope(bad)
    except ContractError:
        pass
    else:
        raise AssertionError(f"Missing signature rejection: {mutate}")

# Structurally valid constraints can still have bad references or result domains.
constraint_semantic = [
    (
        scalar,
        scalar["expressions"],
        [constraint("missing", left["id"])],
        "unknown or non-Expression",
    ),
    (
        scalar,
        scalar["expressions"],
        [constraint("wrong-target", reference["target"])],
        "unknown or non-Expression",
    ),
    (scalar, [left], [constraint("number", left["id"])], "must be Boolean"),
    (
        scalar,
        [reference],
        [constraint("measurement", reference["id"])],
        "must be Boolean",
    ),
    (
        graph,
        [graph["expressions"][0]["call"]["arguments"][0]],
        [
            constraint(
                "collection", graph["expressions"][0]["call"]["arguments"][0]["id"]
            )
        ],
        "must be Boolean",
    ),
    (
        scalar,
        scalar["expressions"],
        [minimal, minimal],
        "duplicate Constraint identity",
    ),
    (
        scalar,
        scalar["expressions"],
        [
            dict(minimal, code="same"),
            constraint("same-code", minimal["predicate"], code="same"),
        ],
        "duplicate Constraint code",
    ),
    (
        scalar,
        scalar["expressions"],
        [dict(minimal, id=reference["target"])],
        "duplicate Constraint identity",
    ),
    (
        scalar,
        scalar["expressions"],
        [dict(minimal, id=minimal["predicate"])],
        "duplicate Expression identity",
    ),
]
for fixture, roots, records, message in constraint_semantic:
    for root in roots:
        validators["Expression"].validate(root)
    for record in records:
        validators["Constraint"].validate(record)
    try:
        Scope(fixture).validate_constraints(records, roots)
    except ContractError as error:
        assert message in str(error), (message, str(error))
    else:
        raise AssertionError(f"Missing Constraint rejection: {message}")

# Preserve the original equations, independent of display labels or source text.
assert [c["predicate"] for c in scalar["constraints"]] == [
    e["id"] for e in scalar["expressions"]
]
values = {
    v["id"]: v["key"]
    for e in scalar["entities"]
    for v in e["characteristics"]["values"]
}


def symbolic(node):
    if node["kind"] == "reference":
        return values[node["target"]]
    return (node["operator"], *(symbolic(child) for child in node["operands"]))


assert symbolic(scalar["expressions"][0]) == (
    "equal",
    "NOI",
    (
        "subtract",
        ("multiply", "homes", "annual_rent_per_home"),
        "annual_operating_cost",
    ),
)
assert symbolic(scalar["expressions"][1]) == (
    "equal",
    ("multiply", "capital_value", "capitalization_rate"),
    "NOI",
)

with TemporaryDirectory(prefix="rk-expression-") as temp:
    path = Path(temp) / "records.py"
    path.write_text(
        subprocess.check_output(
            [str(BIN / "gen-python"), str(SCHEMA / "constraint.yaml")], text=True
        )
    )
    spec = importlib.util.spec_from_file_location("rk_expression_records", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for cls, before in valid:
        record = json_loader.loads(
            json.dumps(before), target_class=getattr(module, cls)
        )
        after = json.loads(json_dumper.dumps(record, inject_type=False))
        assert after == before, (before, after)
        validators[cls].validate(after)
        restored = json_loader.loads(
            json.dumps(after), target_class=getattr(module, cls)
        )
        assert json.loads(json_dumper.dumps(restored, inject_type=False)) == before
        if cls == "Expression" and before["kind"] == "call":
            assert isinstance(record.call.function, module.FunctionId)
        if cls == "Query":
            assert isinstance(record.starting_at, module.EntityId)
        if cls == "Constraint":
            assert isinstance(record.predicate, module.ExpressionId)

print(
    f"Passed {len(validators)} generated schemas, {len(valid)} valid records, {len(invalid)} structural rejections,"
)
print(
    f"{len(semantic)+4+len(constraint_semantic)} bounded semantic rejections, and native Python round trips."
)
print(
    "Constraint satisfaction, query execution, rich Value payloads, dimensional checking, and solving remain unimplemented."
)
