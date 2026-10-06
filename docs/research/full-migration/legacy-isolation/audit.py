"""Retain an import audit and updated locations without rewriting old evidence."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
rows = []
scanned = 0


def examine(path, source, cell):
    global scanned
    relative = path.relative_to(ROOT)
    source = "\n".join("" if line.strip() == "%matplotlib inline" else line for line in source.splitlines())
    tree = ast.parse(source)
    aliases = {}
    references = set()
    package = None
    if str(relative).startswith("src/rangekeeper/"):
        package = ".".join(relative.with_suffix("").parts[1:]).rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for entry in node.names:
                aliases[entry.asname or entry.name.split(".")[0]] = entry.name if entry.asname else entry.name.split(".")[0]
                references.add((node.lineno, entry.name))
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                if package is None:
                    continue
                prefix = importlib.util.resolve_name("." * node.level + prefix, package)
            for entry in node.names:
                name = prefix + "." + entry.name
                aliases[entry.asname or entry.name] = name
                references.add((node.lineno, name))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts, value = [], node
            while isinstance(value, ast.Attribute):
                parts.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name) and value.id in aliases:
                references.add((node.lineno, aliases[value.id] + "." + ".".join(reversed(parts))))
    for line, name in sorted(references):
        if name == "rangekeeper.legacy" or name.startswith("rangekeeper.legacy."):
            assert str(relative).startswith(("src/rangekeeper/legacy/", "src/tests/legacy/")), (relative, line, name)
            rows.append({"path": str(relative), "cell": cell, "line": line, "reference": name})
        for old in ("rangekeeper.api", "rangekeeper.measure", *OLD_GRAPH):
            assert name != old and not name.startswith(old + "."), (relative, line, name)


OLD_GRAPH = tuple("rangekeeper.graph." + name for name in (
    "_catalog", "graph", "entity", "assembly", "relationship", "characteristics",
    "classification", "taxonomy", "definitions", "provenance", "revision",
    "update", "table", "adapter", "legacy", "Graph", "Entity", "Assembly",
    "Characteristics", "Definitions", "Feature", "Measurement", "Taxonomy",
))
for folder in ("src/rangekeeper", "src/tests", "src/docs", "src/examples", "tools", "walkthrough"):
    for path in sorted((ROOT / folder).rglob("*")):
        if path.suffix not in {".py", ".ipynb"} or set(path.parts) & {"_build", "node_modules", "__pycache__", ".venv", ".ipynb_checkpoints"}:
            continue
        scanned += 1
        if path.suffix == ".py":
            examine(path, path.read_text(), None)
        else:
            for cell, data in enumerate(json.loads(path.read_text())["cells"]):
                if data["cell_type"] == "code":
                    examine(path, "".join(data["source"]), cell)

previous = json.loads((OUT.parent / "turn4/ledger.json").read_text())
moves = {row["old"]: row["new"] for row in json.loads((OUT / "moves.json").read_text())}
for symbol in previous["symbols"]:
    if symbol["status"] == "held-windows":
        old = symbol["path"]
        if old == "src/rangekeeper/graph/errors.py":
            current = "src/rangekeeper/legacy/graph/errors.py"
        elif old == "src/rangekeeper/graph/__init__.py":
            current = "src/rangekeeper/legacy/graph/__init__.py"
        elif old == "src/rangekeeper/graph/legacy/__init__.py":
            current = "src/rangekeeper/legacy/graph/__init__.py"
        else:
            current = moves.get(old)
        assert current is not None and (ROOT / current).exists(), old
        symbol.update(current_path=current, acceptance="README.md", destination="Explicit predecessor package; still held for Windows acceptance")
previous["note"] = "Turn 4 dispositions with explicit held-code locations after relocation. Previous paths and source evidence are historical."
held_tests = {row["path"] for row in rows if row["path"].startswith("src/tests/legacy/")}
for consumer in previous["consumers"]:
    path = consumer["path"]
    consumer["current_path"] = moves.get(path, path)
    if consumer["scope"] != "repository":
        consumer["acceptance"] = "../turn4/project-builds.txt; ../turn4/project-comparisons.txt; ../turn4/project-tests.txt"
        continue
    current = ROOT / consumer["current_path"]
    consumer["current_sha256"] = hashlib.sha256(current.read_bytes()).hexdigest() if current.is_file() else None
    if consumer["current_path"] in held_tests:
        consumer.update(status="explicit legacy regression; held for Windows", acceptance="full-suite.xml")
        if current.name == "test_api.py":
            consumer.update(status="held live predecessor tests; not executed", acceptance="README.md")
    elif path in {"src/tests/test_ingestion_evidence.py", "src/tests/test_migration_foundations.py", "src/tests/test_unresolved_measurements.py"}:
        consumer.update(status="canonical; no predecessor implementation import", acceptance="full-suite.xml; imports.json")
    else:
        consumer["acceptance"] = "README.md; ../turn4/BASELINE.md"
for module in previous["modules"]:
    module["current_path"] = moves.get(module["path"], module["path"])
    if module["path"] == "src/rangekeeper/graph/errors.py":
        module["split_path"] = "src/rangekeeper/legacy/graph/errors.py"
(OUT / "ledger.json").write_text(json.dumps(previous, indent=2) + "\n")
(OUT / "imports.json").write_text(json.dumps({"scanned_files": scanned, "references": rows, "canonical_to_legacy_imports": 0, "old_path_imports": 0}, indent=2) + "\n")
print(json.dumps({"scanned_files": scanned, "explicit_legacy_references": len(rows), "canonical_to_legacy_imports": 0, "old_path_imports": 0, "symbols": len(previous["symbols"])}))
