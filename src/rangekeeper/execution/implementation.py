"""Execution implementation identities; solver evidence remains adapter-owned."""

from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import platform

from .._implementation import semantic_digest, manifest_digest
from ..units import default_units


_COMMON = (
    "_implementation.py",
    "_records.py",
    "_record_index.py",
    "_revision.py",
    "_validation.py",
    "diagnostics.py",
    "errors.py",
    "references.py",
    "_schema/records.py",
    "_schema/enums.py",
    "_schema/validation.py",
    "_behaviors/flow.py",
    "_behaviors/period.py",
    "_behaviors/distribution.py",
    "_coordinates.py",
    "duration/calendar.py",
    "model/model.py",
    "model/update.py",
    "model/validation.py",
    "model/scope.py",
    "model/content.py",
    "model/definitions.py",
    "model/system.py",
    "model/provenance.py",
    "model/_scenario.py",
    "scenarios/contracts.py",
    "model/expression/domains.py",
    "model/expression/validation.py",
    "model/formulation/traversal.py",
    "model/formulation/preparation.py",
    "model/formulation/validation.py",
    "units.py",
)
_RESOURCES = ("_schema/schema.json", "_schema/slots.json")
_GROUPS = {
    "compiler": (
        "execution/compiler.py",
        "execution/preparation.py",
        "specification/specification.py",
        "specification/validation.py",
        "specification/composition.py",
        "policies/evaluation.py",
        "policies/observation.py",
        "policies/validation.py",
        "policies/predicate.py",
        "policies/_availability.py",
        "model/expression/evaluation.py",
    ),
    "evaluator": (
        "execution/acceptance.py",
        "execution/evaluator.py",
        "model/expression/evaluation.py",
    ),
}


def fingerprint(role: str, *, package: Path | None = None) -> str:
    """Hash a role's declared semantic sources, schema resources and dependencies."""
    package = Path(__file__).resolve().parents[1] if package is None else package
    paths = (*_COMMON, "execution/implementation.py", *_GROUPS[role])
    manifest = {
        "format": "execution-implementation/v1",
        "role": role,
        "currencies": default_units.currencies,
        "sources": {
            name: semantic_digest((package / name).read_text()) for name in paths
        },
        "resources": {
            name: sha256((package / name).read_bytes()).hexdigest()
            for name in _RESOURCES
        },
        "versions": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("pint", "py-moneyed", "jsonschema")},
        },
    }
    return "execution-implementation/v1:" + manifest_digest(manifest)
