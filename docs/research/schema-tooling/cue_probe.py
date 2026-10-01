"""Compare the CUE validator against the same concrete fixtures."""
from pathlib import Path
import json
import os
import subprocess

root = Path(__file__).resolve().parent
cases = json.loads((root / "cases.json").read_text())
rows, errors = {}, {}
for name, data in cases.items():
    case_file = root / "cue-case.json"
    case_file.write_text(json.dumps(data))
    rows[name] = {}
    for schema in ("#Model", "#SemanticModel"):
        p = subprocess.run([os.environ.get("CUE", "cue"), "vet", "-c", str(root / "probe.cue"), str(case_file), "-d", schema],
                           capture_output=True, text=True, timeout=15)
        rows[name][schema] = "accept" if p.returncode == 0 else "reject"
        if p.returncode:
            errors[f"{name}:{schema}"] = p.stderr[:2500]
tree = {"kind": "add", "left": {"kind": "literal", "value": 2}, "right": {"kind": "add", "left": {"kind": "literal", "value": 3}, "right": {"kind": "literal", "value": 4}}}
(root / "tree.json").write_text(json.dumps(tree))
p = subprocess.run([os.environ.get("CUE", "cue"), "vet", "-c", str(root / "probe.cue"), str(root / "tree.json"), "-d", "#Tree"], capture_output=True, text=True, timeout=15)
result = {"version": subprocess.check_output([os.environ.get("CUE", "cue"), "version"], text=True), "results": rows,
          "recursive_tree": {"accepted": p.returncode == 0, "stderr": p.stderr}}
(root / "cue-results.json").write_text(json.dumps(result, indent=2) + "\n")
(root / "cue-errors.json").write_text(json.dumps(errors, indent=2) + "\n")
print(json.dumps(result, indent=2))
