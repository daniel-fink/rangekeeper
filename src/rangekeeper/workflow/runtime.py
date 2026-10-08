"""Compose the build phases; native formats are owned by catalog integrations."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper import Model
from rangekeeper.shared import structured as _structured
from rangekeeper.shared.errors import IdentityConflictError, UnitError, ValidationError
from rangekeeper.workflow.evidence import Claim, Evidence, Method
from rangekeeper.workflow.operation import Operation, Outcome, _Failure, fingerprint

from rangekeeper.workflow import implementation, provenance
from rangekeeper.workflow._contracts import ExecutionContext, Produced
from rangekeeper.workflow.catalog import OPERATIONS
from rangekeeper.workflow.checking import CheckResult, evaluate
from rangekeeper.workflow.composition import Finding, _compose
from rangekeeper.workflow.implementation import manifests
from rangekeeper.workflow.progress import (
    Observer,
    ProgressPhase,
    ProgressStatus,
    Reporter,
    emit,
)
from rangekeeper.workflow.source_checks import SourceCheck
from rangekeeper.workflow.source_checks import evaluate as source_checks
from rangekeeper.workflow.specification import WorkflowSpec

if TYPE_CHECKING:
    from rangekeeper.workflow.specification import StepSpec


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


def run(
    spec: WorkflowSpec,
    *,
    input_root: Path,
    on_progress: Observer | None = None,
) -> Outcome[WorkflowResult]:
    """Build without export; observer failures are warnings, not semantic failures.

    Inputs are read through their declared adapters. The returned Model is
    immutable. No store or output file is written. Invalid declarations fail
    before execution; unavailable operations return diagnostics with no output.
    """
    reporter = Reporter(on_progress)
    emit(reporter, ProgressPhase.WORKFLOW, ProgressStatus.RUNNING)
    outcome = _run(spec, input_root=input_root, on_progress=reporter)
    emit(
        reporter,
        ProgressPhase.WORKFLOW,
        ProgressStatus.COMPLETED if outcome.output else ProgressStatus.FAILED,
    )
    return replace(outcome, diagnostics=(*outcome.diagnostics, *reporter.diagnostics))


def _run(
    spec: WorkflowSpec,
    *,
    input_root: Path,
    on_progress: Observer,
) -> Outcome[WorkflowResult]:
    """Execute declared operations, compose, check and return without exporting files.

    Native values remain in execution storage; only table Evidence feeds the
    Model construction contract. Handlers own native fingerprints and sources.
    """
    if not isinstance(spec, WorkflowSpec):
        raise TypeError("run requires WorkflowSpec")
    modules, dependencies = implementation.capabilities(spec)
    audit, semantic, implementation_id = manifests(
        Path(__file__).resolve().parents[1], modules=modules, dependencies=dependencies
    )
    operation = Operation(
        method=Method(code="rk.workflow.run", version="5"),
        specification=spec.to_mapping(),
        inputs={"implementation": implementation_id},
    )
    namespace, settings, decisions = provenance.configuration(spec, operation)
    operations: list[Operation] = []
    try:
        produced, step_records = execute_steps(
            spec.steps,
            root=Path(input_root).resolve(),
            namespace=namespace,
            settings=settings,
            operations=operations,
            on_progress=on_progress,
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
        emit(on_progress, ProgressPhase.COMPOSITION, ProgressStatus.RUNNING)
        model, findings, by_key = _compose(
            spec.model,
            evidence,
            settings,
            decisions,
            composition,
            namespace=spec.namespace,
        )
        emit(on_progress, ProgressPhase.COMPOSITION, ProgressStatus.COMPLETED)
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
        emit(on_progress, ProgressPhase.CHECKS, ProgressStatus.RUNNING)
        checks = evaluate(spec.checks, model, by_key, evidence)
        source_ids = {
            item.source.id for item in produced.values() if item.source is not None
        }
        native_checks = source_checks(
            spec.checks.get("source_checks", ()), outputs, source_ids=source_ids
        )
        emit(on_progress, ProgressPhase.CHECKS, ProgressStatus.COMPLETED)
        operations.append(operation)
        metadata = provenance.metadata(
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


class Unavailable(Exception):
    """Propagate native diagnostics without discarding them or catching programmer errors."""

    def __init__(self, diagnostics):
        self.diagnostics = diagnostics


def execute_steps(
    steps: Sequence[StepSpec],
    *,
    root: Path,
    namespace: UUID,
    settings: Claim[str],
    operations: list[Operation],
    on_progress: Observer | None = None,
) -> tuple[dict[str, Produced], dict[str, object]]:
    """Only declared prerequisites are visible to a handler; outputs remain native."""
    produced: dict[str, Produced] = {}
    records: dict[str, object] = {}
    for index, step in enumerate(steps):
        emit(
            on_progress,
            ProgressPhase.STEP,
            ProgressStatus.RUNNING,
            step=step.id,
            completed=index,
            total=len(steps),
        )
        handler = OPERATIONS[step.operation]
        inputs = MappingProxyType({name: produced[name].value for name in step.inputs})
        invocation = Operation(
            method=Method(code="rk.workflow." + step.operation, version="1"),
            specification=step.to_mapping(),
            inputs={name: produced[name].fingerprint for name in step.inputs},
        )
        operations.append(invocation)
        result = handler.execute(
            step.request, inputs, ExecutionContext(root, namespace, settings, step.id)
        )
        operations.append(result.operation)
        if result.output is None:
            raise Unavailable(result.diagnostics)
        emit(
            on_progress,
            ProgressPhase.STEP,
            ProgressStatus.COMPLETED,
            step=step.id,
            completed=index + 1,
            total=len(steps),
        )
        produced[step.id] = handler.describe(result.output)
        records[step.id] = {
            "dispatch": fingerprint(invocation),
            "native": (fingerprint(result.operation),),
        }
    return produced, records
