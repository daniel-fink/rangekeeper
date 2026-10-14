"""Bounded schema experiment; not an RK implementation or solver."""
from __future__ import annotations

import copy
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("PYSTOW_HOME", str(ROOT / "pystow"))
import yaml
from jsonschema import Draft202012Validator, validators
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from typing import Annotated, Literal, Union

schema = {
    "id": "https://example.org/rk-schema-probe", "name": "rk_schema_probe",
    "prefixes": {"linkml": "https://w3id.org/linkml/", "probe": "https://example.org/rk-schema-probe/"},
    "default_prefix": "probe", "imports": ["linkml:types"], "default_range": "string",
    "classes": {
        "Declaration": {"abstract": True, "attributes": {
            "id": {"identifier": True}, "kind": {"required": True, "designates_type": True},
        }},
        "ValueDeclaration": {"is_a": "Declaration", "slot_usage": {"kind": {"equals_string": "ValueDeclaration"}},
            "attributes": {"unit": {"required": True}}},
        "EntityDeclaration": {"is_a": "Declaration", "slot_usage": {"kind": {"equals_string": "EntityDeclaration"}}},
        "Expression": {"abstract": True, "attributes": {
            "id": {"identifier": True}, "kind": {"required": True, "designates_type": True},
        }},
        "NumericLiteral": {"is_a": "Expression", "slot_usage": {"kind": {"equals_string": "NumericLiteral"}},
            "attributes": {"value": {"range": "float", "required": True}, "unit": {"required": True}}},
        "BooleanLiteral": {"is_a": "Expression", "slot_usage": {"kind": {"equals_string": "BooleanLiteral"}},
            "attributes": {"value": {"range": "boolean", "required": True}}},
        "Reference": {"is_a": "Expression", "slot_usage": {"kind": {"equals_string": "Reference"}},
            "attributes": {"target": {"range": "ValueDeclaration", "required": True, "inlined": False}}},
        "LessEqual": {"is_a": "Expression", "slot_usage": {"kind": {"equals_string": "LessEqual"}},
            "attributes": {k: {"range": "Expression", "required": True, "inlined": False} for k in ("left", "right")}},
        "Constraint": {"attributes": {"predicate": {"range": "Expression", "required": True, "inlined": False}}},
        "Model": {"tree_root": True, "attributes": {
            k: {"range": v, "required": True, "multivalued": True, "inlined": True, "inlined_as_list": True}
            for k, v in (("declarations", "Declaration"), ("expressions", "Expression"), ("constraints", "Constraint"))
        }},
    },
}
(ROOT / "linkml.yaml").write_text(yaml.safe_dump(schema, sort_keys=False))
env = dict(os.environ)
def generate(exe, args, output):
    result = subprocess.run([str(Path(sys.executable).parent / exe), *args, str(ROOT / "linkml.yaml")],
                            capture_output=True, text=True, env=env, timeout=60)
    (ROOT / (output + ".stderr")).write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"{exe}: {result.stderr}")
    (ROOT / output).write_text(result.stdout)
generate("gen-json-schema", ["--closed", "--include-range-class-descendants", "--top-class", "Model"], "linkml.schema.json")
generate("gen-pydantic", ["--extra-fields", "forbid"], "linkml_models.py")
generated_schema = json.loads((ROOT / "linkml.schema.json").read_text())
GeneratedValidator = validators.validator_for(generated_schema)
GeneratedValidator.check_schema(generated_schema)
generated_validator = GeneratedValidator(generated_schema)
spec = importlib.util.spec_from_file_location("linkml_probe_models", ROOT / "linkml_models.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
class ValueDeclaration(StrictRecord):
    id: str
    kind: Literal["ValueDeclaration"]
    unit: str
class EntityDeclaration(StrictRecord):
    id: str
    kind: Literal["EntityDeclaration"]
class NumericLiteral(StrictRecord):
    id: str
    kind: Literal["NumericLiteral"]
    value: float
    unit: str
class BooleanLiteral(StrictRecord):
    id: str
    kind: Literal["BooleanLiteral"]
    value: bool
class Reference(StrictRecord):
    id: str
    kind: Literal["Reference"]
    target: str
class LessEqual(StrictRecord):
    id: str
    kind: Literal["LessEqual"]
    left: str
    right: str
class Constraint(StrictRecord):
    predicate: str
Declaration = Annotated[Union[ValueDeclaration, EntityDeclaration], Field(discriminator="kind")]
Expression = Annotated[Union[NumericLiteral, BooleanLiteral, Reference, LessEqual], Field(discriminator="kind")]
class Model(StrictRecord):
    declarations: list[Declaration]
    expressions: list[Expression]
    constraints: list[Constraint]

class SemanticModel(Model):
    @model_validator(mode="after")
    def check_reference_targets(self):
        decl = {d.id: d for d in self.declarations}
        expr = {e.id: e for e in self.expressions}
        if len(decl) != len(self.declarations) or len(expr) != len(self.expressions):
            raise ValueError("duplicate identity")
        for e in self.expressions:
            if isinstance(e, Reference) and not isinstance(decl.get(e.target), ValueDeclaration):
                raise ValueError("reference must identify a value declaration")
        # This probe only accepts numeric references/literals as comparison operands.
        for e in self.expressions:
            if isinstance(e, LessEqual):
                operands = [expr.get(e.left), expr.get(e.right)]
                units = []
                for operand in operands:
                    if isinstance(operand, Reference):
                        units.append(decl[operand.target].unit)
                    elif isinstance(operand, NumericLiteral):
                        units.append(operand.unit)
                    else:
                        raise ValueError("comparison needs numeric operands")
                if units[0] != units[1]:
                    raise ValueError("unit mismatch in probe")
        for c in self.constraints:
            if not isinstance(expr.get(c.predicate), (LessEqual, BooleanLiteral)):
                raise ValueError("constraint requires a Boolean expression")
        return self

direct_schema = Model.model_json_schema()
(ROOT / "pydantic.schema.json").write_text(json.dumps(direct_schema, indent=2) + "\n")
semantic_schema = SemanticModel.model_json_schema()
(ROOT / "pydantic-semantic.schema.json").write_text(json.dumps(semantic_schema, indent=2) + "\n")
base = {
    "declarations": [{"id": "cost", "kind": "ValueDeclaration", "unit": "AUD"}, {"id": "site", "kind": "EntityDeclaration"}],
    "expressions": [
        {"id": "cost_ref", "kind": "Reference", "target": "cost"},
        {"id": "limit", "kind": "NumericLiteral", "value": 100.0, "unit": "AUD"},
        {"id": "within_budget", "kind": "LessEqual", "left": "cost_ref", "right": "limit"},
    ],
    "constraints": [{"predicate": "within_budget"}],
}
cases = {"valid": copy.deepcopy(base)}
def change(name, callback):
    data = copy.deepcopy(base)
    callback(data)
    cases[name] = data
change("missing_literal_value", lambda d: d["expressions"][1].pop("value"))
change("string_as_number", lambda d: d["expressions"][1].update(value="100"))
change("bool_as_number", lambda d: d["expressions"][1].update(value=True))
change("null_as_number", lambda d: d["expressions"][1].update(value=None))
change("unknown_expression_kind", lambda d: d["expressions"][1].update(kind="Unknown"))
change("missing_expression_kind", lambda d: d["expressions"][1].pop("kind"))
change("missing_declaration_kind", lambda d: d["declarations"][0].pop("kind"))
change("abstract_expression", lambda d: d["expressions"].append({"id": "abstract", "kind": "Expression"}))
change("extra_literal_field", lambda d: d["expressions"][1].update(target="cost"))
change("missing_operand", lambda d: d["expressions"][2].pop("right"))
change("dangling_reference", lambda d: d["expressions"][0].update(target="absent"))
change("wrong_reference_kind", lambda d: d["expressions"][0].update(target="site"))
change("numeric_constraint", lambda d: d["constraints"][0].update(predicate="limit"))
change("wrong_units", lambda d: d["expressions"][1].update(unit="m2"))
change("duplicate_identity", lambda d: d["declarations"].append(copy.deepcopy(d["declarations"][0])))
change("empty_constraints", lambda d: d.update(constraints=[]))
change("omitted_constraints", lambda d: d.pop("constraints"))
change("null_constraints", lambda d: d.update(constraints=None))
change("extra_model_field", lambda d: d.update(surprise=1))
(ROOT / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
checks = {
    "linkml_json_schema": lambda d: generated_validator.validate(d),
    "linkml_pydantic_default": lambda d: module.Model.model_validate(d),
    "linkml_pydantic_strict": lambda d: module.Model.model_validate(d, strict=True),
    "pydantic_strict": lambda d: Model.model_validate(d),
    "pydantic_json_schema": lambda d: Draft202012Validator(direct_schema).validate(d),
    "pydantic_with_semantics": lambda d: SemanticModel.model_validate(d),
    "pydantic_semantic_export": lambda d: Draft202012Validator(semantic_schema).validate(d),
}
rows = {}
errors = {}
for name, data in cases.items():
    rows[name] = {}
    for checker, fn in checks.items():
        try:
            fn(copy.deepcopy(data))
            rows[name][checker] = "accept"
        except Exception as error:
            rows[name][checker] = "reject"
            errors[f"{name}:{checker}"] = str(error)[:1800]
result = {
    "versions": {n: importlib.metadata.version(n) for n in ("linkml", "linkml-runtime", "jsonschema", "pydantic")},
    "python": sys.version, "results": rows,
    "scope": "Generated schema/object validation and one explicit semantic checker; not execution, inversion, migration or broad framework conformance.",
}
(ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
(ROOT / "errors.json").write_text(json.dumps(errors, indent=2) + "\n")
print(json.dumps(result, indent=2))
