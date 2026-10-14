"""Retain final input hashes and inspect the executed notebook without rendering."""

from pathlib import Path
import ast
import hashlib
import importlib.metadata as metadata
import json
import platform
import shutil
import subprocess
import sys

import nbformat

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
WHEEL_SITE = Path("/private/tmp/rk-date-only-final/site")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


notebook = nbformat.read(OUT / "basic_dcf_final.ipynb", as_version=4)
nbformat.validate(notebook)
code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
assert len(code_cells) == 23
assert [c.execution_count for c in code_cells] == list(range(1, 24))
outputs = [output for cell in code_cells for output in cell.outputs]
assert not any(output.output_type == "error" for output in outputs)
texts = "\n".join(output.get("text", "") for output in outputs)
assert "Property PV: $1,000" in texts
assert str(WHEEL_SITE) in texts
html = (OUT / "basic_dcf_final.html").read_text()
assert "<table" in html and "Net Cashflow with Reversion" in html
shutil.copy2(OUT / "basic_dcf_final.ipynb", ROOT / "walkthrough/basic_dcf.ipynb")

# Formatting/docstrings can differ from the built wheel without changing logic.
# Record every difference; semantic drift must fail inspection.
def code_tree(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    return ast.dump(tree, include_attributes=False)


differences = []
for path in (ROOT / "src/rangekeeper").rglob("*.py"):
    installed = WHEEL_SITE / path.relative_to(ROOT / "src")
    assert installed.is_file(), installed
    if digest(path) != digest(installed):
        assert code_tree(path) == code_tree(installed), path
        differences.append(str(path.relative_to(ROOT)))
inspection = dict(code_cells=23, errors=0, property_pv=1000,
                  independent_oracle_passed=True, wheel_site=str(WHEEL_SITE),
                  nonsemantic_source_differences=differences,
                  html_table_checked=True, visual_review_completed=False)
(OUT / "notebook-inspection.json").write_text(json.dumps(inspection, indent=2) + "\n")

initial = json.loads((OUT / "before.json").read_text())
assert digest(ROOT / ".gitignore") == initial["sha256"][".gitignore"]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True)
files = {str(p.relative_to(ROOT)): digest(p)
         for directory in ("src/rangekeeper", "schema", "src/tests", "tools/schema")
         for p in sorted((ROOT / directory).rglob("*"))
         if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".yaml", ".json", ".toml"}}
files["walkthrough/basic_dcf.ipynb"] = digest(ROOT / "walkthrough/basic_dcf.ipynb")
sys.path.insert(0, str(ROOT / "src"))
import rangekeeper

versions = {name: metadata.version(name) for name in (
    "jsonschema", "pandas", "polars", "numpy", "scipy", "pint", "pyomo", "highspy",
    "nbformat", "nbclient", "ipykernel")}
state = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
             import_path=rangekeeper.__file__, sys_path=sys.path, packages=versions,
             input_sha256=files, unrelated_gitignore_preserved=True, index_empty=True,
             head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip())
(OUT / "final-state.json").write_text(json.dumps(state, indent=2) + "\n")

paths = [path for package in ("calculations", "temporal", "migration")
         for path in (ROOT / "src/rangekeeper" / package).rglob("*.py")]
paths.extend(ROOT / "src/rangekeeper" / path for path in (
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
print(json.dumps({"files": len(files), "callables": len(items), **inspection,
                  "unrelated_gitignore_preserved": True, "index_empty": True}))
