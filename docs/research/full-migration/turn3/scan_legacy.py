"""Inventory active Python/notebook references and assign explicit retirement gates.

This lexical inventory includes import guards and test strings. It is supporting
source evidence, not a claim that unexecuted service consumers are compatible.
"""

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_name("legacy-dependencies.json")
OLD = r"(?:_legacy_duration|flux|distribution|extrapolation|projection|formula|dynamics|segmentation|policy|measure|api|format|space)"
patterns = [
    re.compile(r"\b(?:rk|rangekeeper)\." + OLD + r"\b"),
    re.compile(r"from\s+rangekeeper\s+import\s+[^#\n]*\b" + OLD + r"\b"),
    re.compile(r"from\s+\.+\s+import\s+[^#\n]*\b" + OLD + r"\b"),
    re.compile(r"\b(?:rk|rangekeeper)\.(?:Graph|update_class)\b"),
    re.compile(
        r"(?:rangekeeper\.)?graph\.(?:legacy|graph|entity|assembly|characteristics|definitions|workflow|revision)\b"
    ),
]
rows = []
for folder in ("src/rangekeeper", "src/tests", "src/examples", "walkthrough", "tools"):
    for path in sorted((ROOT / folder).rglob("*")):
        if path.suffix not in (".py", ".ipynb") or any(
            part.startswith(".")
            or part in ("__pycache__", "node_modules", "_schema", "_build")
            for part in path.relative_to(ROOT).parts
        ):
            continue
        if path.suffix == ".ipynb":
            sources = [
                (f"cell {i + 1}", "".join(c["source"]))
                for i, c in enumerate(json.loads(path.read_text())["cells"])
                if c["cell_type"] == "code"
            ]
        else:
            sources = [("", path.read_text())]
        for cell, source in sources:
            for number, line in enumerate(source.splitlines(), 1):
                if any(pattern.search(line) for pattern in patterns):
                    relative = str(path.relative_to(ROOT))
                    gate = (
                        "Turn 4: retain characterization checks until equivalent canonical behavior and remaining caller ports pass"
                        if relative.startswith("src/tests")
                        else (
                            "Turn 4: negative import guard or historical caller; inspect before deletion"
                            if relative.startswith(
                                ("walkthrough", "src/examples", "tools")
                            )
                            or "/adapters/" in relative
                            else "Turn 4: remove implementation/export after Turn 3 consumers and characterization gates pass"
                        )
                    )
                    rows.append(
                        dict(
                            path=relative,
                            cell=cell or None,
                            line=number,
                            # Inventory dependencies without copying credential literals.
                            source=re.sub(
                                r"(?i)(token\s*=\s*['\"])[^'\"]+(['\"])",
                                r"\1<redacted>\2",
                                line.strip(),
                            ),
                            retirement=gate,
                        )
                    )
# Root lazy exports are string mappings, not imports; retain them explicitly.
init = ROOT / "src/rangekeeper/__init__.py"
for number, line in enumerate(init.read_text().splitlines(), 1):
    if re.search(r'[\'"]' + OLD + r'[\'"]\s*:', line):
        rows.append(
            dict(
                path=str(init.relative_to(ROOT)),
                line=number,
                source=line.strip(),
                retirement="Turn 4: remove lazy legacy export after remaining caller proof",
            )
        )
new_consumers = {
    "walkthrough/" + n + ".ipynb"
    for n in (
        "basic_dcf",
        "deterministic_scenarios",
        "market_dynamics",
        "flexibility_intro",
        "flexibility_under_uncertainty",
        "load_design",
        "drive_model_from_design",
    )
}
new_consumers |= {
    "src/tests/models/" + n + ".py"
    for n in ("deterministic", "probabilistic", "flexible")
}
active = [
    r
    for r in rows
    if r["path"] in new_consumers
    and not (
        r["source"].startswith("assert not") or " & set(sys.modules)" in r["source"]
    )
]
assert not active, active
OUT.write_text(
    json.dumps(
        dict(
            note="Lexical references include test/import-guard strings; each retained hit has a removal gate.",
            migrated_consumers=sorted(new_consumers),
            migrated_runtime_references=active,
            occurrences=rows,
        ),
        indent=2,
    )
    + "\n"
)
print(
    json.dumps(
        dict(
            occurrences=len(rows),
            files=len({r["path"] for r in rows}),
            migrated_runtime_references=len(active),
        )
    )
)
