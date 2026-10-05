"""Capture static migration evidence without importing or executing consumer code.

Run from any directory with Python 3.10+. Outputs contain source locations,
signatures, hashes and lexical references, never notebook outputs or input data.
This is discovery evidence, not call-graph completeness or runtime acceptance.
"""

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PROJECTS = ROOT.parent / "Whirlwind/projects"
LAYOUT = ROOT.parent / "Whirlwind/.worktrees/rk-assembly-layout"

# Each group has a disposition in FULL_MIGRATION_REVIEW.md. New support modules
# are captured separately so that age/root placement does not imply retirement.
GROUPS = {
    "graph-domain": [
        "graph/graph.py", "graph/_catalog.py", "graph/entity.py",
        "graph/relationship.py", "graph/assembly.py", "graph/characteristics.py",
        "graph/classification.py", "graph/taxonomy.py", "graph/definitions.py",
        "graph/provenance.py", "graph/revision.py", "graph/update.py",
        "graph/adapter/__init__.py", "graph/adapter/json.py", "graph/table.py",
        "graph/legacy/__init__.py", "graph/legacy/view.py", "graph/legacy/reduction.py",
        "graph/__init__.py", "graph/errors.py",
    ],
    "units": ["measure.py"],
    "temporal": ["flux.py", "duration.py"],
    "numerical": ["distribution.py", "extrapolation.py", "projection.py",
                  "formula/__init__.py", "formula/financial.py"],
    "scenarios": [str(p.relative_to(ROOT / "src/rangekeeper"))
                  for p in sorted((ROOT / "src/rangekeeper/dynamics").glob("*.py"))],
    "policy": ["policy.py"],
    "segmentation": ["segmentation.py"],
    "integration": ["api.py"],
    "presentation": ["format.py"],
    "root-cleanup": ["__init__.py", "space.py"],
}


def git(root, *args):
    """Read Git metadata; unavailable external repositories are explicit."""
    if not root.is_dir():
        return None
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_api(path):
    """Include private methods too: important algorithms can live behind them."""
    tree = ast.parse(path.read_text())
    symbols = []

    def visit(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                symbols.append({"name": prefix + node.name, "line": node.lineno,
                                "kind": "class", "bases": [ast.unparse(b) for b in node.bases]})
                visit(node.body, prefix + node.name + ".")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append({"name": prefix + node.name, "line": node.lineno,
                                "kind": "callable", "arguments": ast.unparse(node.args),
                                "returns": ast.unparse(node.returns) if node.returns else None})
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                symbols.append({"name": prefix + node.target.id, "line": node.lineno,
                                "kind": "field", "annotation": ast.unparse(node.annotation)})
            elif prefix and isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        symbols.append({"name": prefix + target.id, "line": node.lineno,
                                        "kind": "class-attribute"})
    visit(tree.body)
    return {"sha256": fingerprint(path), "symbols": symbols}


def refs(path):
    """Read code cells only; matches are candidates, not resolved Python calls."""
    if path.suffix == ".ipynb":
        doc = json.loads(path.read_text())
        chunks = [(i, "".join(c.get("source", []))) for i, c in enumerate(doc["cells"])
                  if c.get("cell_type") == "code"]
    else:
        chunks = [(None, path.read_text())]
    hits = []
    for cell, code in chunks:
        for match in re.finditer(r"\b(?:rangekeeper|rk)(?:\.[A-Za-z_]\w*)*", code):
            hits.append({"cell": cell, "line": code[:match.start()].count("\n") + 1,
                         "reference": match.group()})
    return {"sha256": fingerprint(path), "references": hits}


def state(root):
    return {"path": str(root), "head": git(root, "rev-parse", "HEAD"),
            "branch": git(root, "branch", "--show-current"),
            "status": git(root, "status", "--short")}


def main():
    modules = {}
    for group, paths in GROUPS.items():
        for rel in paths:
            path = ROOT / "src/rangekeeper" / rel
            modules[str(path.relative_to(ROOT))] = {"group": group, **source_api(path)}
    tracked = git(ROOT, "ls-files").splitlines()
    local = {}
    for rel in tracked:
        path = ROOT / rel
        eligible = (rel.startswith(("src/tests/", "src/docs/examples/", "src/examples/", "tools/"))
                    and path.suffix in {".py", ".yaml", ".toml"})
        eligible |= path.parent == ROOT / "walkthrough" and path.suffix == ".ipynb"
        if eligible:
            item = refs(path)
            if item["references"] or path.suffix == ".yaml":
                local[rel] = item
    external = {}
    for rel in (git(PROJECTS, "ls-files") or "").splitlines():
        parts = Path(rel).parts
        if not parts or parts[0] not in {"mandarin", "east-whisman"}:
            continue
        if any(p in {"archive", "artifacts", "inputs"} for p in parts):
            continue
        path = PROJECTS / rel
        if path.suffix in {".py", ".ipynb", ".toml", ".yaml"}:
            external[rel] = refs(path)
    extensions = {}
    for rel in (git(LAYOUT, "ls-files", "src/rangekeeper/**/*.py") or "").splitlines():
        path = LAYOUT / rel
        if "/cytoscape/layout/" in rel or path.name in {"workbench.py", "layout_review.py", "_progress.py", "_review.py"}:
            extensions[rel] = source_api(path)
    doc = {
        "status": "static discovery only; no consumer executed",
        "capture": {"python": sys.version, "executable": sys.executable,
                    "script": str(Path(__file__).resolve()), "cwd": str(Path.cwd())},
        "repositories": {"rk": state(ROOT), "projects": state(PROJECTS), "layout": state(LAYOUT)},
        "review_modules": modules,
        "other_library_sources": {
            str(p.relative_to(ROOT)): fingerprint(p)
            for p in sorted((ROOT / "src/rangekeeper").rglob("*.py"))
            if str(p.relative_to(ROOT)) not in modules and "__pycache__" not in p.parts
        },
        "local_consumer_candidates": local, "external_consumer_candidates": external,
        "parallel_branch_features": extensions,
        "other_tracked_surfaces": {
            prefix: [p for p in tracked if p.startswith(prefix)]
            for prefix in ("grasshopper/", "hypar/", "walkthrough/_build/")
        },
        "limits": [
            "Lexical matches do not resolve aliases, dynamic imports, or instance-method calls.",
            "Function bodies were not executed. Listed symbols are not certified behavior.",
            "External inventory covers the two named local projects and the known RK layout worktree only.",
            "Generated notebook copies are listed separately, not counted as independent source notebooks.",
            "No source workbooks, credentials, archived code or notebook outputs were read by this script.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "inventory.json").write_text(json.dumps(doc, indent=2) + "\n")
    lines = ["# Remaining-code symbol inventory", "",
             "Static capture only. The [review proposal](../../FULL_MIGRATION_REVIEW.md) owns dispositions.",
             "Each symbol must receive a behavior-contract row before its implementation is retired.",
             "Private methods and fields are included to expose algorithms and mutation contracts.", ""]
    for path, item in modules.items():
        lines += [f"## `{path}`", "", f"Review group: `{item['group']}`.", ""]
        for symbol in item["symbols"]:
            label = symbol["name"]
            if symbol["kind"] == "callable":
                label += "(" + symbol["arguments"] + ")"
            lines.append(f"- `{label}` — {symbol['kind']}, line {symbol['line']}.")
        if not item["symbols"]:
            lines.append("No classes or functions; inspect imports, re-exports or commented residue.")
        lines.append("")
    (OUT / "SYMBOLS.md").write_text("\n".join(lines))
    print(json.dumps({"modules": len(modules), "symbols": sum(len(x["symbols"]) for x in modules.values()),
                      "local_candidates": len(local), "external_candidates": len(external),
                      "branch_feature_modules": len(extensions)}, indent=2))


if __name__ == "__main__":
    main()
