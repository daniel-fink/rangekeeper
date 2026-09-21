"""Sequential workflow execution. The API performs no artifact export."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from types import MappingProxyType
from uuid import NAMESPACE_URL, UUID, uuid5

from rangekeeper.graph import Graph, _structured
from rangekeeper.graph.adapter import excel
from rangekeeper.graph.adapter.excel.classification import classify_rows
from rangekeeper.graph.operation import Operation, Outcome, _Failure
from rangekeeper.graph.operation import fingerprint as operation_fingerprint
from rangekeeper.graph.provenance import Claim, Location, Method, Source, locations
from rangekeeper.graph.workflow.checking import CheckResult, evaluate
from rangekeeper.graph.workflow.composition import Finding, compose
from rangekeeper.graph.workflow.ingestion import Evidence, fingerprint, tabular
from rangekeeper.graph.workflow.ingestion.transform import transform
from rangekeeper.graph.workflow.source_checks import SourceCheck
from rangekeeper.graph.workflow.source_checks import evaluate as source_checks
from rangekeeper.graph.workflow.specification import (
    ClassifySpec,
    ConcatSpec,
    ExtractSpec,
    NumbersSpec,
    ReadSpec,
    SelectSpec,
    TransformsSpec,
    WorkflowSpec,
)

from ._declarations import plain
from .ingestion.predicates import Predicate, select_where


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowResult:
    """Keeps the built graph together with named Evidence, checks and execution
    records so reviewers can explain the result without reconstructing the
    build.
    """

    graph: Graph
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
    """Connects reviewed declarations to reusable RK operations and stops when a
    prerequisite is unavailable. Returning results without export lets CLI,
    notebook and direct callers choose their own persistence boundary.
    """
    if not isinstance(spec, WorkflowSpec):
        raise TypeError("run requires WorkflowSpec")
    root = Path(input_root).resolve()
    package = Path(__file__).resolve().parents[2]
    from .implementation import manifests

    implementation, semantic_implementation, implementation_fingerprint = manifests(
        package
    )
    operation = Operation(
        method=Method(code="rk.workflow.run", version="2"),
        specification=spec.to_mapping(),
        inputs={"implementation": implementation_fingerprint},
    )
    operations = []
    step_operations = {}
    outputs = {}
    namespace = uuid5(NAMESPACE_URL, spec.namespace)
    source = Source(
        id=uuid5(namespace, "configuration:" + operation_fingerprint(operation)),
        name="workflow specification",
        checksum=operation_fingerprint(operation),
    )
    settings = Claim.sourced(
        json.dumps(plain(spec.to_mapping()), ensure_ascii=False, sort_keys=True),
        at=Location(source=source, reference={"files": ",".join(spec.hashes)}),
        id=uuid5(source.id, "effective-settings"),
    )
    decisions = {
        d["id"]: Claim.derived(
            json.dumps(plain(d), sort_keys=True),
            from_claims=(settings,),
            method=Method(code="reviewed-decision", version=d["date"]),
            id=uuid5(source.id, d["id"]),
        )
        for d in spec.decisions["decisions"]
    }

    def accept(outcome):
        operations.append(outcome.operation)
        if outcome.output is None:
            raise _Unavailable(outcome.diagnostics)
        return outcome.output

    try:
        for step in spec.steps:
            first_operation = len(operations)
            r = step.request
            op = step.operation
            invocation = Operation(
                method=Method(code="rk.workflow." + op, version="1"),
                specification=step.to_mapping(),
                inputs={
                    k: outputs[k].fingerprint
                    if isinstance(outputs[k], excel.Workbook)
                    else fingerprint(outputs[k])
                    for k in step.inputs
                },
            )
            operations.append(invocation)
            if op == "read":
                assert isinstance(r, ReadSpec)
                candidates = [root / f for f in r.files if (root / f).is_file()]
                if not candidates:
                    raise _Failure(
                        "missing_source", f"No declared file found for {r.source_key}"
                    )
                if any(not p.resolve().is_relative_to(root) for p in candidates):
                    raise _Failure(
                        "source_outside_root", "Resolved source escapes input_root"
                    )
                hashes = {
                    hashlib.sha256(p.read_bytes()).hexdigest() for p in candidates
                }
                if len(hashes) != 1:
                    raise _Failure(
                        "ambiguous_source",
                        f"Declared filenames contain different editions for {r.source_key}",
                    )
                output = accept(
                    excel.read(
                        candidates[0],
                        namespace=namespace,
                        source_key=r.source_key,
                        name=r.source_key,
                        expected_checksum=r.checksum,
                    )
                )
            elif op == "extract":
                assert isinstance(r, ExtractSpec)
                book = outputs[r.input]
                output = accept(
                    excel.extract_table(
                        book, r.specification, unique_stop=r.unique_stop
                    )
                )
            elif op == "classify_rows":
                assert isinstance(r, ClassifySpec)
                output = accept(
                    classify_rows(
                        outputs[r.input],
                        outputs[r.workbook],
                        specification=r.specification,
                        settings=settings,
                        name=step.id,
                    )
                )
            elif op == "numbers":
                assert isinstance(r, NumbersSpec)
                output = accept(
                    tabular.numbers(
                        outputs[r.input],
                        specifications=r.specifications,
                        settings=settings,
                        name=step.id,
                    )
                )
            elif op == "transform":
                assert isinstance(r, TransformsSpec)
                output = accept(
                    transform(
                        outputs[r.input],
                        specifications=r.specifications,
                        settings=settings,
                        name=step.id,
                    )
                )
            elif op == "concat":
                assert isinstance(r, ConcatSpec)
                output = accept(
                    tabular.concat((outputs[k] for k in r.inputs), name=step.id)
                )
            elif op == "select":
                assert isinstance(r, SelectSpec)
                evidence = outputs[r.input]
                row_ids = (
                    None if r.row_ids is None else tuple(UUID(x) for x in r.row_ids)
                )
                if r.where is not None:
                    output = accept(
                        select_where(
                            evidence,
                            predicate=Predicate.from_mapping(r.where),
                            columns=r.columns,
                            name=step.id,
                        )
                    )
                else:
                    output = accept(
                        tabular.select(
                            evidence, row_ids=row_ids, columns=r.columns, name=step.id
                        )
                    )
            outputs[step.id] = output
            step_operations[step.id] = {
                "dispatch": operation_fingerprint(invocation),
                "native": tuple(
                    operation_fingerprint(o) for o in operations[first_operation + 1 :]
                ),
            }
        evidence_inputs = {
            key: fingerprint(value)
            for key, value in outputs.items()
            if isinstance(value, Evidence)
        }
        composition = Operation(
            method=Method(code="rk.workflow.compose", version="2"),
            specification={"model": spec.model, "decisions": spec.decisions},
            inputs={
                **evidence_inputs,
                "implementation": implementation_fingerprint,
                "configuration": str(settings.id),
            },
        )
        operations.append(composition)
        graph, findings, by_key = compose(
            spec.model,
            outputs,
            settings,
            decisions,
            composition,
            namespace=spec.namespace,
        )
        from rangekeeper.graph.adapter.json import dumps

        graph_hash = "sha256:" + hashlib.sha256(dumps(graph).encode()).hexdigest()
        checks_operation = Operation(
            method=Method(code="rk.workflow.checks", version="1"),
            specification=spec.checks,
            inputs={
                **evidence_inputs,
                "graph": graph_hash,
                "implementation": implementation_fingerprint,
            },
        )
        operations.append(checks_operation)
        checks = evaluate(spec.checks, graph, by_key, outputs)
        native_checks = source_checks(spec.checks.get("source_checks", ()), outputs)
        deferred_records = []
        for declaration in spec.model.get("deferred", ()):
            evidence = outputs[declaration["table"]]
            for row in evidence.data.rows:
                claim = tabular.claim(evidence, row.id, declaration["column"])
                cells = [x for x in locations(claim) if "cell" in x.reference]
                if len(cells) != 1:
                    raise _Failure(
                        "ambiguous_record",
                        "Supporting row requires one native source location",
                    )
                loc = cells[0]
                coordinate = loc.reference["cell"]
                physical_row = coordinate.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                deferred_records.append(
                    f"{loc.source.checksum}:{loc.reference['sheet']}:{physical_row}:{declaration['kind']}"
                )
        operations.append(operation)
        metadata = {
            "format": "rk.workflow/v1",
            "implementation": implementation,
            "semantic_implementation": semantic_implementation,
            "semantic_version": 2,
            "step_operations": step_operations,
            "python": sys.version.split()[0],
            "dependencies": {
                name: version(name)
                for name in ("rangekeeper", "openpyxl", "pyyaml", "pint")
            },
            "deferred_records": tuple(sorted(deferred_records)),
            "aggregation_policies": spec.model.get("aggregates", ()),
            "specification": dict(spec.hashes),
            "sources": {
                k: {
                    "id": str(v.source.id),
                    "name": v.source.name,
                    "checksum": v.source.checksum,
                    "fingerprint": v.fingerprint,
                }
                for k, v in outputs.items()
                if isinstance(v, excel.Workbook)
            },
            "operations": tuple(operation_fingerprint(o) for o in operations),
            "deferred": spec.checks.get("deferred", ()),
            "notes": spec.checks.get("notes", ()),
        }
        if spec.declarations:
            metadata["effective_specification"] = spec.to_mapping()
        return Outcome(
            operation=operation,
            output=WorkflowResult(
                graph=graph,
                evidence={k: v for k, v in outputs.items() if isinstance(v, Evidence)},
                checks=checks,
                source_checks=native_checks,
                findings=findings,
                operations=tuple(operations),
                metadata=metadata,
            ),
        )
    except _Failure as exc:
        return Outcome(operation=operation, output=None, diagnostics=(exc.diagnostic,))
    except _Unavailable as exc:
        return Outcome(operation=operation, output=None, diagnostics=exc.diagnostics)


class _Unavailable(Exception):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
