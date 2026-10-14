"""Check portability of the generated schemas against the shared cases."""
from pathlib import Path
import json
import os
import subprocess
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

root = Path(__file__).resolve().parent
cases = json.loads((root / "cases.json").read_text())
bundle = json.loads((root / "typespec/tsp-output/@typespec/json-schema/probe.schema.json").read_text())
registry = Registry().with_resources((v["$id"], Resource.from_contents(v)) for v in bundle["$defs"].values())
ts_validator = Draft202012Validator(bundle["$defs"]["Model"], registry=registry)
ts_tree_validator = Draft202012Validator(bundle["$defs"]["Tree"], registry=registry)
checks = {
    "typespec_json_schema": ts_validator,
    "cue_json_schema": Draft202012Validator(json.loads((root / "cue.schema.json").read_text())),
    "cue_semantic_export": Draft202012Validator(json.loads((root / "cue-semantic.schema.json").read_text())),
}
rows, errors = {}, {}
for name, data in cases.items():
    rows[name] = {}
    for label, validator in checks.items():
        try:
            validator.validate(data)
            rows[name][label] = "accept"
        except Exception as error:
            rows[name][label] = "reject"
            errors[f"{name}:{label}"] = str(error)[:2500]
ts_tree_validator.validate(json.loads((root / "tree.json").read_text()))
inverse = subprocess.run([os.environ.get("CUE", "cue"), "export", str(root / "inverse.cue")], capture_output=True, text=True, timeout=10)
result = {"versions": {
    name: json.loads((root / "typespec/node_modules" / name / "package.json").read_text())["version"]
    for name in ("@typespec/compiler", "@typespec/json-schema")
}, "results": rows, "typespec_recursive_tree": "accept", "cue_inverse": {"exit_code": inverse.returncode, "stderr": inverse.stderr}}
(root / "export-results.json").write_text(json.dumps(result, indent=2) + "\n")
(root / "export-errors.json").write_text(json.dumps(errors, indent=2) + "\n")
print(json.dumps(result, indent=2))
