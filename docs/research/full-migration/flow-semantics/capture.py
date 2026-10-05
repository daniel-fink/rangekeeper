"""Retain final inputs, API signatures and inspected installed-notebook evidence."""

from pathlib import Path
import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

import nbformat

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--wheel-dir", type=Path, default=Path("/private/tmp/rk-flow-semantics-wheel"))
args = parser.parse_args()
site = args.wheel_dir / "site"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


notebook = nbformat.read(OUT / "basic_dcf.ipynb", as_version=4)
source = nbformat.read(ROOT / "walkthrough/basic_dcf.ipynb", as_version=4)
nbformat.validate(notebook)
assert [c.source for c in notebook.cells] == [c.source for c in source.cells]
code = [cell for cell in notebook.cells if cell.cell_type == "code"]
assert len(code) == 23 and [cell.execution_count for cell in code] == list(range(1, 24))
outputs = [output for cell in code for output in cell.outputs]
assert not any(output.output_type == "error" for output in outputs)
text = "\n".join(output.get("text", "") for output in outputs)
assert "Property PV: $1,000" in text and str(site) in text
assert "<table" in (OUT / "basic_dcf.html").read_text()
shutil.copy2(OUT / "basic_dcf.ipynb", ROOT / "walkthrough/basic_dcf.ipynb")
(OUT / "notebook-inspection.json").write_text(json.dumps(dict(
    code_cells=23, errors=0, pv=1000, independent_oracle_passed=True,
    source_cells_unchanged=True, table_markup_checked=True,
    visual_review_completed=False, wheel_site=str(site)), indent=2) + "\n")

before = json.loads((OUT / "before.json").read_text())
preserved = (".gitignore", "src/uv.lock", "src/uv.sync-conflict-20261005-170953-H3RQGJU.lock")
assert all(digest(ROOT / name) == before["sha256"][name] for name in preserved)
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True)
current = {name: digest(ROOT / name) for name in before["sha256"] if (ROOT / name).is_file()}
current["src/tests/test_flow_operations.py"] = digest(ROOT / "src/tests/test_flow_operations.py")
for path in (ROOT / "src/rangekeeper").rglob("*.py"):
    assert digest(site / path.relative_to(ROOT / "src")) == digest(path), path
suite = ET.parse(OUT / "pytest-local.xml").getroot().find("testsuite")
assert suite is not None and suite.attrib["failures"] == suite.attrib["errors"] == "0"
(OUT / "final-state.json").write_text(json.dumps(dict(
    head=before["head"], input_sha256=current,
    changed_inputs=[name for name, value in current.items() if value != before["sha256"].get(name)],
    preserved_unrelated_files=list(preserved), wheel_python_matches_source=True,
    index_empty=True, pytest=suite.attrib), indent=2) + "\n")

paths = [path for package in ("calculations", "temporal", "migration")
         for path in (ROOT / "src/rangekeeper" / package).rglob("*.py")]
paths.extend(ROOT / "src/rangekeeper" / name for name in (
    "model/flow.py", "model/content.py", "model/duration.py", "adapters/pandas.py", "adapters/polars.py"))
items = []
for path in sorted(paths):
    def visit(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                items.append(dict(module=str(path.relative_to(ROOT)), symbol=prefix + node.name,
                    arguments=ast.unparse(node.args), returns=ast.unparse(node.returns) if node.returns else None,
                    docstring=ast.get_docstring(node)))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, prefix + node.name + ".")
    visit(ast.parse(path.read_text()).body)
(OUT / "api.json").write_text(json.dumps(items, indent=2) + "\n")
print("Notebook and full regression verified; wheel Python matches source; unrelated files preserved; index empty.")
