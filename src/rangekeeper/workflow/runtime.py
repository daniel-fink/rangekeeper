"""Compose the build phases; native formats are owned by catalog integrations."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from rangekeeper import Model, _structured
from rangekeeper.operation import Operation, Outcome, _Failure
from rangekeeper.evidence import Method
from rangekeeper.errors import ValidationError, IdentityConflictError, UnitError

from . import _audit
from ._execution import Unavailable, execute_steps
from .checking import CheckResult, evaluate
from .composition import Finding, compose
from .implementation import manifests
from .ingestion import Evidence
from .source_checks import SourceCheck
from .source_checks import evaluate as source_checks
from .specification import WorkflowSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowResult:
    """Keeps the built Model together with named Evidence, checks and execution
    records so reviewers can explain the result without reconstructing the
    build.
    """

    model: Model
    evidence: Mapping[str, Evidence]
    checks: tuple[CheckResult, ...]
    source_checks: tuple[SourceCheck, ...]
    findings: tuple[Finding, ...]
    operations: tuple[Operation, ...]
    metadata: Mapping[str, object]

    def __post_init__(self):
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))
        object.__setattr__(self, "metadata", _structured.freeze_mapping(self.metadata))


def run(spec: WorkflowSpec, *, input_root: Path) -> Outcome[WorkflowResult]:
    """Execute declared operations, compose, check and return without exporting files.

    Native values remain in execution storage; only table Evidence feeds the
    Model construction contract. Handlers own native fingerprints and sources.
    """
    if not isinstance(spec, WorkflowSpec):
        raise TypeError("run requires WorkflowSpec")
    modules, dependencies = _audit.capabilities(spec)
    audit, semantic, implementation_id = manifests(
        Path(__file__).resolve().parents[1], modules=modules
    )
    operation = Operation(
        method=Method(code="rk.workflow.run", version="4"),
        specification=spec.to_mapping(),
        inputs={"implementation": implementation_id},
    )
    namespace, settings, decisions = _audit.configuration(spec, operation)
    operations: list[Operation] = []
    try:
        produced, step_records = execute_steps(
            spec.steps,
            root=Path(input_root).resolve(),
            namespace=namespace,
            settings=settings,
            operations=operations,
        )
        outputs = {key: item.value for key, item in produced.items()}
        evidence = {
            key: value for key, value in outputs.items() if isinstance(value, Evidence)
        }
        evidence_inputs = {key: produced[key].fingerprint for key in evidence}
        composition = Operation(
            method=Method(code="rk.workflow.compose", version="3"),
            specification={"model": spec.model, "decisions": spec.decisions},
            inputs={
                **evidence_inputs,
                "implementation": implementation_id,
                "configuration": str(settings.id),
            },
        )
        operations.append(composition)
        model, findings, by_key = compose(
            spec.model,
            evidence,
            settings,
            decisions,
            composition,
            namespace=spec.namespace,
        )
        from rangekeeper.io.json import dumps

        model_hash = "sha256:" + hashlib.sha256(dumps(model).encode()).hexdigest()
        checks_operation = Operation(
            method=Method(code="rk.workflow.checks", version="3"),
            specification=spec.checks,
            inputs={
                **evidence_inputs,
                "model": model_hash,
                "implementation": implementation_id,
            },
        )
        operations.append(checks_operation)
        checks = evaluate(spec.checks, model, by_key, evidence)
        source_ids = {
            item.source.id for item in produced.values() if item.source is not None
        }
        native_checks = source_checks(
            spec.checks.get("source_checks", ()), outputs, source_ids=source_ids
        )
        operations.append(operation)
        metadata = _audit.metadata(
            spec, produced, step_records, operations, audit, semantic, dependencies
        )
        return Outcome(
            operation=operation,
            output=WorkflowResult(
                model=model,
                evidence=evidence,
                checks=checks,
                source_checks=native_checks,
                findings=findings,
                operations=tuple(operations),
                metadata=metadata,
            ),
        )
    except (ValidationError, IdentityConflictError, UnitError) as exc:
        failure = _Failure("invalid_model", str(exc))
        return Outcome(
            operation=operation, output=None, diagnostics=(failure.diagnostic,)
        )
    except _Failure as exc:
        return Outcome(operation=operation, output=None, diagnostics=(exc.diagnostic,))
    except Unavailable as exc:
        return Outcome(operation=operation, output=None, diagnostics=exc.diagnostics)
