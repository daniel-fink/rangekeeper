"""Record the tested LinkML documentation/cardinality behaviour, without fixing it."""
from pathlib import Path
import copy
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("PYSTOW_HOME", str(ROOT / "pystow"))
import yaml
from jsonschema import validators

schema = yaml.safe_load((ROOT / "linkml.yaml").read_text())
empty = json.loads((ROOT / "cases.json").read_text())["empty_constraints"]
bin_dir = Path(sys.executable).parent
rows = {}
for minimum in (0, 1):
    variant = copy.deepcopy(schema)
    variant["classes"]["Model"]["attributes"]["constraints"]["minimum_cardinality"] = minimum
    source = ROOT / f"cardinality-{minimum}.yaml"
    source.write_text(yaml.safe_dump(variant, sort_keys=False))
    generated = subprocess.run(
        [str(bin_dir / "gen-json-schema"), "--closed", "--include-range-class-descendants",
         "--top-class", "Model", str(source)],
        capture_output=True, text=True, check=True, timeout=60,
    )
    shape = json.loads(generated.stdout)
    validator = validators.validator_for(shape)(shape)
    doc_dir = ROOT / f"cardinality-docs-{minimum}"
    subprocess.run(
        [str(bin_dir / "gen-doc"), "-d", str(doc_dir), "--diagram-type",
         "mermaid_class_diagram", str(source)],
        capture_output=True, text=True, check=True, timeout=60,
    )
    rows[str(minimum)] = {
        "empty_constraints_accepted": validator.is_valid(empty),
        "doc_rows": [line for line in (doc_dir / "Model.md").read_text().splitlines()
                     if line.startswith("| [constraints]")],
        "schema_constraints": shape["$defs"]["Model"]["properties"]["constraints"],
    }
(ROOT / "cardinality-results.json").write_text(json.dumps(rows, indent=2) + "\n")

doc_dir = ROOT / "generated-docs"
subprocess.run(
    [str(bin_dir / "gen-doc"), "-d", str(doc_dir), "--include-top-level-diagram",
     "--diagram-type", "mermaid_class_diagram", str(ROOT / "linkml.yaml")],
    capture_output=True, text=True, check=True, timeout=60,
)
docs = {
    "top_level_mermaid_contains_none": "```mermaid\nNone\n```" in (doc_dir / "index.md").read_text(),
    "model_class_diagram_present": "classDiagram" in (doc_dir / "Model.md").read_text(),
    "model_constraints_row": [line for line in (doc_dir / "Model.md").read_text().splitlines()
                              if line.startswith("| [constraints]")],
}
(ROOT / "documentation-results.json").write_text(json.dumps(docs, indent=2) + "\n")
print(json.dumps({"cardinality": rows, "documentation": docs}, indent=2))
