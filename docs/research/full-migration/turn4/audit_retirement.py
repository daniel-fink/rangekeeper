"""Audit current imports and overlay dispositions on the frozen 671-symbol ledger.

Static discovery covers Python sources and notebook code cells. Import-absence
tests and installed consumer execution provide the runtime evidence separately.
Historical research, generated book copies and archived projects are not callers.
"""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
RETIRED = {
    "flux", "_legacy_duration", "distribution", "extrapolation", "projection",
    "formula", "dynamics", "segmentation", "policy", "format", "space",
    "update_class", "rgba_from_cmap",
}
HELD_GRAPH = {
    "_catalog", "graph", "entity", "assembly", "relationship", "characteristics",
    "classification", "taxonomy", "definitions", "provenance", "revision",
    "update", "table", "adapter", "legacy", "Graph", "Entity", "Assembly",
    "Relationship", "Characteristics", "Feature", "Measurement", "Label",
    "Definitions", "Classification", "Taxonomy",
}


def category(reference):
    parts = reference.split(".")
    if len(parts) < 2 or parts[0] != "rangekeeper":
        return None
    if parts[1] in RETIRED:
        return "removed"
    if parts[1] in {"api", "measure"} or (
        len(parts) > 2 and parts[1] == "graph" and parts[2] in HELD_GRAPH
    ):
        return "held-windows"
    return None


def references(source, path):
    # This presentation magic changes no imports. Keep its line for numbering;
    # reject any other non-Python cell syntax instead of silently omitting it.
    source = "\n".join("" if line.strip() == "%matplotlib inline" else line for line in source.splitlines())
    tree = ast.parse(source, filename=str(path))
    aliases, result = {}, set()
    relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    package = None
    if str(relative).startswith("src/rangekeeper/"):
        module = ".".join(relative.with_suffix("").parts[1:])
        package = module.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
                result.add((node.lineno, item.name))
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                if package is None:
                    continue
                prefix = importlib.util.resolve_name("." * node.level + prefix, package)
            for item in node.names:
                reference = prefix + "." + item.name
                aliases[item.asname or item.name] = reference
                result.add((node.lineno, reference))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        parts, value = [], node
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name) and value.id in aliases:
            result.add((node.lineno, aliases[value.id] + "." + ".".join(reversed(parts))))
    return sorted((line, ref, category(ref)) for line, ref in result if category(ref))


paths = []
for folder in ("src/rangekeeper", "src/tests", "src/docs", "src/examples", "walkthrough", "tools"):
    paths.extend(p for p in (ROOT / folder).rglob("*") if p.suffix in {".py", ".ipynb"}
                 and not any(x in p.parts for x in ("_build", "node_modules", "__pycache__", ".venv", ".ipynb_checkpoints")))
rows = []
for path in sorted(paths):
    sources = [(None, path.read_text())] if path.suffix == ".py" else [
        (i, "".join(cell["source"])) for i, cell in enumerate(json.loads(path.read_text())["cells"])
        if cell["cell_type"] == "code"
    ]
    for cell, source in sources:
        for line, ref, disposition in references(source, path):
            rows.append({"path": str(path.relative_to(ROOT)), "cell": cell, "line": line,
                         "reference": ref, "disposition": disposition})
assert not [r for r in rows if r["disposition"] == "removed"], rows
for row in rows:
    if row["path"].startswith("src/rangekeeper/"):
        # Only the held predecessor group may import its own old domain.
        relative = row["path"].removeprefix("src/").replace("/", ".").removesuffix(".py")
        assert category(relative) == "held-windows", row
    else:
        assert row["path"].startswith("src/tests/"), row
        row["disposition"] = "held-windows-test"
(OUT / "imports.json").write_text(json.dumps({"scanned_files": len(paths), "occurrences": rows,
    "note": "AST discovery; negative string guards are covered by test_retirement and installed tests."}, indent=2) + "\n")

old = json.loads((OUT.parent / "turn3/ledger.json").read_text())
destinations = {
    "flux.py": "model.flow; calculations.series/financial; adapters.pandas/polars/plotting",
    "duration.py": "model.duration; duration.calendar/period; explicit half-open date intervals",
    "distribution.py": "model.distribution; calculations.distribution; explicit generator",
    "extrapolation.py": "calculations.projection.project_values/project",
    "projection.py": "calculations.projection.project/allocate/pad; explicit origin and periods",
    "financial.py": "calculations.account.calculate_account/AccountResult; formulations.account",
    "black_swan.py": "calculations.dynamics.shock.calculate_shock; scenarios.components.make_black_swan",
    "cyclicality.py": "calculations.dynamics.cyclicality.calculate_cycle; scenarios.components.make_cyclicality",
    "market.py": "scenarios.plan.make_plan; scenarios.market.generate/realize; scenarios.replay.replay",
    "noise.py": "calculations.dynamics.noise.sample_noise; scenarios.components.make_noise",
    "trend.py": "calculations.dynamics.trend.calculate_trend; scenarios.components.make_trend",
    "volatility.py": "calculations.dynamics.volatility; scenarios.components.make_volatility",
    "policy.py": "specification.policy records; policies.evaluate; finite declarative rules, no callbacks",
    "segmentation.py": "calculations.interval.Interval; Model Entities/Assemblies/property Values and Taxonomy",
    "format.py": "detached presentation using Python formatting and dataframe/plotting library APIs",
    "space.py": "comment-only stub removed; canonical Entity/Assembly content is model-owned",
}
for row in old["symbols"]:
    path, symbol = row["path"], row["symbol"]
    name = Path(path).name
    if "/graph/" in path or name in {"measure.py", "api.py"}:
        row.update(status="held-windows", destination="Canonical replacements accepted; predecessor dependency group retained", acceptance="../turn3/RETIREMENT.md")
    elif name == "__init__.py":
        if symbol.split(".")[0] in {"update_class", "rgba_from_cmap"}:
            row.update(status="removed", destination="Explicit authoring and detached plotting", acceptance="src/tests/test_retirement.py")
        else:
            row.update(status="retained" if path == "src/rangekeeper/__init__.py" else "removed", destination="Canonical lazy exports", acceptance="src/tests/test_retirement.py")
    else:
        assert name in destinations, row
        row.update(status="removed", destination=destinations[name], acceptance="BEHAVIOUR.md")
old["note"] = "Frozen inventory with explicit Turn 4 dispositions; held does not mean removed or fully accepted externally."
for module in old["modules"]:
    statuses = {row["status"] for row in old["symbols"] if row["path"] == module["path"]}
    if not statuses:
        statuses = {"held-windows" if "/graph/" in module["path"] else "removed"}
    module["turn4_status"] = sorted(statuses)

# Preserve the original evidence under an explicit historical key. Current
# dispositions use the current file bytes and acceptance, not the old imports.
projects = ROOT.parent / "Whirlwind/projects"
held_test_paths = {row["path"] for row in rows if row["disposition"] == "held-windows-test"}
for consumer in old["consumers"]:
    path = consumer["path"]
    consumer["historical_evidence"] = consumer.pop("evidence")
    actual = (ROOT if consumer["scope"] == "repository" else projects) / path
    consumer["current_sha256"] = hashlib.sha256(actual.read_bytes()).hexdigest() if actual.is_file() else None
    if consumer["scope"] == "external":
        consumer.update(status="canonical; rebuilt and compared from isolated installed wheel",
                        acceptance="project-builds.txt; project-comparisons.txt; project-tests.txt; mandarin-notebook.txt")
        if actual.suffix in {".py", ".ipynb"}:
            sources = [actual.read_text()] if actual.suffix == ".py" else [
                "".join(cell["source"]) for cell in json.loads(actual.read_text())["cells"]
                if cell["cell_type"] == "code"
            ]
            assert not [hit for source in sources for hit in references(source, actual)], path
    elif path == "src/tests/models/linear_graph.py":
        consumer.update(status="removed; commented-only file had no implemented behavior", acceptance="removed-files.json")
    elif path == "src/tests/test_api.py":
        consumer.update(status="held live predecessor tests; not executed", acceptance="RETIREMENT.md")
    elif path in held_test_paths:
        consumer.update(status="held predecessor regression; passed", acceptance="full-suite.xml; RETIREMENT.md")
    elif path.startswith("walkthrough/"):
        consumer.update(status="canonical; fresh-kernel installed-wheel execution passed", acceptance="notebooks.txt")
    elif path.startswith("src/docs/examples/"):
        consumer.update(status="canonical example; detached execution passed", acceptance="documentation-examples-final.txt")
    else:
        consumer.update(status="canonical; regression or generation/typing/tool acceptance passed",
                        acceptance="full-suite.xml; installed.txt; generation.txt; typing.txt")
old["parallel_branch_features_note"] = "Historical source inventory; canonical ports were accepted in Turn 3 and are unchanged in Turn 4."
(OUT / "ledger.json").write_text(json.dumps(old, indent=2) + "\n")
print(json.dumps({"scanned_files": len(paths), "held_references": len(rows),
                  "removed_imports": 0, "symbols_assigned": len(old["symbols"])}))
