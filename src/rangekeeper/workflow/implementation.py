"""Separate exact installed-code audit from semantic computation identity."""

import hashlib
from importlib.metadata import version
from pathlib import Path

from rangekeeper.shared import structured as _structured
from rangekeeper.shared.fingerprints import semantic_digest
from rangekeeper.shared.units import default_units

from rangekeeper.workflow._contracts import OperationDeclaration, SourceCheckDeclaration


_CORE_DEPENDENCIES = frozenset(
    {"rangekeeper", "jsonschema", "pint", "py-moneyed", "pyyaml"}
)


def manifests(
    package: Path,
    *,
    modules: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
):
    """Audit every Python file; bind semantic identity to declared computation code.

    This conservative dependency set includes graph construction, provenance,
    measures, record behaviour and ingestion, plus selected handlers' native modules.
    Presentation and CLI export do not compute assertions and therefore cannot
    change their identities.
    """
    paths = sorted(package.rglob("*.py"))
    audit = {
        str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }
    semantic = {}
    for p in paths:
        name = str(p.relative_to(package))
        included = name.startswith(
            ("schema/", "shared/", "model/", "workflow/", "adapters/", "io/")
        )
        excluded = name.startswith("adapters/") and not (
            any(name.startswith(prefix) for prefix in modules)
            or name == "adapters/document.py"
        )
        excluded |= name in {
            "workflow/review.py",
            "workflow/reporting.py",
            "workflow/progress.py",
            "workflow/workbench.py",
            "workflow/references.py",
            "workflow/__main__.py",
        }
        if included and not excluded:
            semantic[name] = semantic_digest(p.read_text())
    resources = [
        *sorted((package / "schema").glob("*.json")),
    ]
    for resource in resources:
        if resource.is_file():
            name = str(resource.relative_to(package))
            digest = hashlib.sha256(resource.read_bytes()).hexdigest()
            audit[name] = digest
            semantic[name] = digest
    return (
        audit,
        semantic,
        _structured.fingerprint(
            {
                "version": 5,
                "modules": semantic,
                "currencies": default_units.currencies,
                "dependencies": {
                    name: version(name)
                    for name in sorted(_CORE_DEPENDENCIES | set(dependencies))
                },
            }
        ),
    )


def capabilities(spec):
    """Conservative explicit code groups; no runtime dependency introspection."""
    from rangekeeper.workflow.catalog import OPERATIONS, SOURCE_CHECKS

    handlers: list[OperationDeclaration | SourceCheckDeclaration] = [
        OPERATIONS[step.operation] for step in spec.steps
    ]
    handlers += [
        SOURCE_CHECKS[s["operation"]]
        for s in spec.checks.get("source_checks", ())
        if s["operation"] in SOURCE_CHECKS
    ]
    modules = tuple(sorted({m for h in handlers for m in h.modules}))
    dependencies = tuple(
        sorted(_CORE_DEPENDENCIES | {d for h in handlers for d in h.dependencies_used})
    )
    return modules, dependencies
