"""Execution implementation identities; solver evidence remains adapter-owned."""

from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import platform

from rangekeeper.shared.fingerprints import semantic_digest, manifest_digest
from rangekeeper.shared.units import default_units


_COMMON = (
    "shared/fingerprints.py",
    "schema/runtime.py",
    "schema/index.py",
    "schema/revision.py",
    "shared/validation.py",
    "shared/diagnostics.py",
    "shared/errors.py",
    "shared/references.py",
    "schema/records.py",
    "schema/enums.py",
    "schema/validation.py",
    "schema/behaviors/flow.py",
    "schema/behaviors/period.py",
    "schema/behaviors/distribution.py",
    "model/duration/calendar.py",
    "model/model.py",
    "model/update.py",
    "model/validation.py",
    "model/scope.py",
    "model/content.py",
    "model/definitions.py",
    "model/system/validation.py",
    "model/provenance.py",
    "model/scenario/contracts.py",
    "model/expression/domains.py",
    "model/expression/validation.py",
    "model/formulation/preparation.py",
    "model/formulation/validation.py",
    "shared/units.py",
)
_RESOURCES = ("schema/schema.json", "schema/slots.json")
_GROUPS = {
    "compiler": (
        "run/execution/compiler.py",
        "run/execution/preparation.py",
        "specification/specification.py",
        "specification/validation.py",
        "specification/composition.py",
        "specification/policy/evaluation.py",
        "specification/policy/observation.py",
        "specification/policy/validation.py",
        "specification/policy/predicate.py",
        "specification/policy/_availability.py",
        "model/expression/evaluation.py",
    ),
    "evaluator": (
        "run/execution/acceptance.py",
        "model/expression/evaluation.py",
    ),
}


def fingerprint(role: str, *, package: Path | None = None) -> str:
    """Hash a role's declared semantic sources, schema resources and dependencies."""
    package = Path(__file__).resolve().parents[2] if package is None else package
    paths = (*_COMMON, "run/execution/implementation.py", *_GROUPS[role])
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
