"""Verify the relocation, preserved inputs and exact tested wheel without writes.

Only the evidence report is written. Original source workbooks, host files,
archives, Git indexes and external applications are never changed.
"""

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
baseline = json.loads((OUT / "baseline.json").read_text())
moves = json.loads((OUT / "moves.json").read_text())
wheel = Path("/private/tmp/rk-legacy-isolation-wheel/wheel/rangekeeper-0.8.71-py3-none-any.whl")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WithoutImports(ast.NodeTransformer):
    """Ignore import spelling when checking preserved predecessor behaviour."""

    def visit_Import(self, node):
        return None

    def visit_ImportFrom(self, node):
        return None


for name, expected in baseline["protected"].items():
    assert digest(Path(name)) == expected, name
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == baseline["head"]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).strip()

python_bodies, csharp_resources = [], []
for item in moves:
    assert not (ROOT / item["old"]).exists(), item["old"]
    path = ROOT / item["new"]
    assert path.is_file(), path
    if item["old"].startswith("grasshopper/"):
        assert digest(path) == item["before_sha256"], path
        csharp_resources.append(item["new"])
    elif item["old"].startswith("src/rangekeeper/"):
        original = subprocess.check_output(["git", "show", "HEAD:" + item["old"]], cwd=ROOT, text=True)
        assert hashlib.sha256(original.encode()).hexdigest() == item["before_sha256"], item["old"]
        assert ast.dump(WithoutImports().visit(ast.parse(original))) == ast.dump(WithoutImports().visit(ast.parse(path.read_text()))), path
        python_bodies.append(item["new"])

# The shared error file was split rather than moved. Preserve each predecessor
# class/function body and keep the three canonical errors in their original home.
old_errors = subprocess.check_output(["git", "show", "HEAD:src/rangekeeper/graph/errors.py"], cwd=ROOT, text=True)
canonical_names = {"SelectionError", "HierarchyError", "AggregationError"}
original_nodes = [n for n in ast.parse(old_errors).body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name not in canonical_names]
legacy_nodes = [n for n in ast.parse((ROOT / "src/rangekeeper/legacy/graph/errors.py").read_text()).body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
assert [ast.dump(n) for n in original_nodes] == [ast.dump(n) for n in legacy_nodes]

changed_canonical = {"src/rangekeeper/__init__.py", "src/rangekeeper/model/__init__.py", "src/rangekeeper/graph/__init__.py", "src/rangekeeper/graph/errors.py"}
old_paths = {item["old"] for item in moves} | {"src/rangekeeper/graph/legacy/__init__.py"}
updated_docs = {"grasshopper/README.md", "grasshopper/WINDOWS_DEVELOPMENT.md"}
preserved = []
for name, expected in baseline["inputs"].items():
    if name.startswith(("src/rangekeeper/", "grasshopper/")) and name not in old_paths | changed_canonical | updated_docs:
        assert digest(ROOT / name) == expected, name
        preserved.append(name)
with zipfile.ZipFile(wheel) as archive:
    packaged = [name for name in archive.namelist() if name.startswith("rangekeeper/") and not name.endswith("/")]
    for name in packaged:
        assert (ROOT / "src" / name).read_bytes() == archive.read(name), name
    assert "rangekeeper/legacy/graph/graph.py" in packaged
    assert "rangekeeper/api.py" not in packaged and "rangekeeper/measure.py" not in packaged
for name in ("README.md", "pyproject.toml"):
    assert (ROOT / "src" / name).read_bytes() == (wheel.parent.parent / "stage" / name).read_bytes()

suite = ET.parse(OUT / "full-suite.xml").find("testsuite")
counts = {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}
assert counts == {"tests": 1087, "failures": 0, "errors": 0, "skipped": 24}, counts
report = {
    "head": baseline["head"], "index_empty": True,
    "protected_files_unchanged": len(baseline["protected"]),
    "moves": len(moves), "predecessor_python_bodies_preserved": python_bodies,
    "predecessor_errors_preserved": len(legacy_nodes),
    "csharp_and_resources_byte_identical": csharp_resources,
    "other_runtime_and_csharp_inputs_unchanged": len(preserved),
    "wheel_sha256": digest(wheel), "wheel_files_equal_to_source": len(packaged),
    "suite": counts, "remaining_gate": "Official Windows connector acceptance",
    "commit_push_or_publication": False,
}
(OUT / "final-state.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, indent=2))
