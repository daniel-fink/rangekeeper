"""Configuration lineage and result metadata, separate from step execution."""

import json
import sys
from importlib.metadata import version
from uuid import NAMESPACE_URL, uuid5

from rangekeeper.graph.operation import _Failure, fingerprint
from rangekeeper.graph.provenance import Claim, Location, Method, Source, locations

from ._contracts import OperationDeclaration, SourceCheckDeclaration
from ._declarations import plain
from .bindings import require_columns
from .ingestion import tabular


def configuration(spec, operation):
    namespace = uuid5(NAMESPACE_URL, spec.namespace)
    token = fingerprint(operation)
    source = Source(
        id=uuid5(namespace, "configuration:" + token),
        name="workflow specification",
        checksum=token,
    )
    settings = Claim.sourced(
        json.dumps(plain(spec.to_mapping()), ensure_ascii=False, sort_keys=True),
        at=Location(
            source=source,
            reference=(
                {"files": ",".join(spec.hashes)}
                if spec.hashes
                else {"configuration": "direct API"}
            ),
        ),
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
    return namespace, settings, decisions


def capabilities(spec):
    """Conservative explicit code groups; no runtime dependency introspection."""
    from .catalog import OPERATIONS, SOURCE_CHECKS

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
        sorted(
            {"rangekeeper", "pint", "pyyaml"}
            | {d for h in handlers for d in h.dependencies_used}
        )
    )
    return modules, dependencies


def deferred_records(declarations, outputs, source_ids):
    """Retain row identity and source locations; adapters may supply legacy native tokens."""
    from .catalog import RECORD_FORMATTERS

    records, evidence_records = [], []
    for declaration in declarations:
        evidence = outputs[declaration["table"]]
        require_columns(evidence, (declaration["column"],))
        for row in evidence.data.rows:
            claim = tabular.claim(evidence, row.id, declaration["column"])
            native = [loc for loc in locations(claim) if loc.source.id in source_ids]
            if len(native) != 1:
                raise _Failure(
                    "ambiguous_record",
                    "Supporting row requires one native source location",
                )
            loc = native[0]
            reference = next(
                (value for f in RECORD_FORMATTERS if (value := f(loc)) is not None),
                None,
            )
            if reference is None:
                reference = f"{loc.source.checksum}:row:{row.id}"
            records.append(reference + ":" + declaration["kind"])
            evidence_records.append({
                "table": declaration["table"],
                "row": str(row.id),
                "kind": declaration["kind"],
                "source": str(loc.source.id),
                "reference": dict(loc.reference),
            })
    return tuple(sorted(records)), tuple(evidence_records)


def metadata(
    spec, produced, step_records, operations, implementation, semantic, dependencies
):
    outputs = {key: item.value for key, item in produced.items()}
    source_ids = {
        item.source.id for item in produced.values() if item.source is not None
    }
    deferred, deferred_evidence = deferred_records(
        spec.model.get("deferred", ()), outputs, source_ids
    )
    result = {
        "format": "rk.workflow/v1",
        "review_specification": spec.to_mapping(),
        "implementation": implementation,
        "semantic_implementation": semantic,
        "semantic_version": 3,
        "step_operations": step_records,
        "python": sys.version.split()[0],
        "dependencies": {name: version(name) for name in dependencies},
        "deferred_records": deferred,
        "deferred_evidence": deferred_evidence,
        "aggregation_policies": spec.model.get("aggregates", ()),
        "specification": dict(spec.hashes),
        "sources": {
            key: {
                "id": str(item.source.id),
                "name": item.source.name,
                "checksum": item.source.checksum,
                "fingerprint": item.fingerprint,
            }
            for key, item in produced.items()
            if item.source is not None
        },
        "operations": tuple(fingerprint(o) for o in operations),
        "deferred": spec.checks.get("deferred", ()),
        "notes": spec.checks.get("notes", ()),
    }
    if spec.declarations:
        result["effective_specification"] = spec.to_mapping()
    return result
