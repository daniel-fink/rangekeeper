"""Convert transient source support into schema provenance at the Model boundary."""

import json
import sys
from importlib.metadata import version
from uuid import NAMESPACE_URL, uuid5
from typing import cast
from rangekeeper.workflow import evidence
from rangekeeper.schema.runtime import JSONValue
from rangekeeper.shared.encoding import encode
from rangekeeper.schema.records import (
    Claim,
    ClaimKind,
    Fact,
    Location,
    Method,
    Provenance,
    Source,
)
from rangekeeper.workflow.operation import _Failure, fingerprint
from rangekeeper.workflow._declarations import plain
from rangekeeper.workflow.bindings import require_columns


class ProvenanceBuilder:
    """Private build-local collector; canonical records contain UUID links only.

    Source observation content uses a labelled, type-sensitive encoding so dates,
    tuples, false, zero and missing readings retain their distinct meanings. This
    does not add domain Features: only declared schema fields become Model state.
    """

    def __init__(self):
        self.claims = {}
        self.sources = {}
        self.facts = []
        self._active = set()
        self._prepared = {}

    def add(self, claim: evidence.Claim):
        """Retain every ancestor once; reject conflicting identities and cycles."""
        if id(claim) in self._prepared:
            return self._prepared[id(claim)].id
        if claim.id in self._active:
            raise _Failure("cyclic_evidence", "Source Claim support contains a cycle")
        self._active.add(claim.id)
        supports = []
        for parent in claim.sources:
            if isinstance(parent, evidence.Claim):
                supports.append(self.add(parent))
            else:
                source = parent.source
                source_record = Source(
                    id=source.id,
                    name=source.name,
                    checksum=source.checksum,
                    issued_at=(
                        source.issued_at.isoformat() if source.issued_at else None
                    ),
                    received_at=(
                        source.received_at.isoformat() if source.received_at else None
                    ),
                    author=source.author,
                )
                self._retain(self.sources, source_record)
                supports.append(
                    Location(source=source.id, address=dict(parent.reference))
                )
        method = (
            Method(
                code=claim.method.code,
                version=claim.method.version,
                description=claim.method.description,
            )
            if claim.method
            else None
        )
        record = Claim(
            id=claim.id,
            kind=claim.kind,
            content={
                "encoding": "rk.source-value/v1",
                "value": cast(JSONValue, encode(claim.value)),
            },
            sources=tuple(supports),
            method=method,
        )
        self._retain(self.claims, record)
        self._active.remove(claim.id)
        self._prepared[id(claim)] = claim
        return claim.id

    @staticmethod
    def _retain(index, record):
        previous = index.get(record.id)
        if previous is not None and previous != record:
            raise _Failure(
                "conflicting_evidence", f"Conflicting evidence identity: {record.id}"
            )
        index[record.id] = record

    def attach(self, target, *, id, sources, method, upstream=()):
        """Record the composed declaration and its source support without mutation."""
        support = tuple(dict.fromkeys((*upstream, *(self.add(c) for c in sources))))
        claim = Claim(
            id=id,
            kind=ClaimKind.DERIVED,
            content=target.to_data(),
            sources=support,
            method=Method(
                code=method.code, version=method.version, description=method.description
            ),
        )
        self._retain(self.claims, claim)
        self.facts.append(Fact(target=target.id, claims=(id,)))
        return id

    def finish(self) -> Provenance:
        """Return immutable generated records; Model construction validates references."""
        return Provenance(
            sources=tuple(self.sources.values()),
            claims=tuple(self.claims.values()),
            facts=tuple(self.facts),
        )


def configuration(spec, operation):
    namespace = uuid5(NAMESPACE_URL, spec.namespace)
    token = fingerprint(operation)
    source = evidence.Source(
        id=uuid5(namespace, "configuration:" + token),
        name="workflow specification",
        checksum=token,
    )
    settings = evidence.Claim.sourced(
        json.dumps(plain(spec.to_mapping()), ensure_ascii=False, sort_keys=True),
        at=evidence.Location(
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
        d["id"]: evidence.Claim.derived(
            json.dumps(plain(d), sort_keys=True),
            from_claims=(settings,),
            method=evidence.Method(code="reviewed-decision", version=d["date"]),
            id=uuid5(source.id, d["id"]),
        )
        for d in spec.decisions["decisions"]
    }
    return namespace, settings, decisions


def deferred_records(declarations, outputs, source_ids):
    """Retain row identity and source locations; adapters may supply legacy native tokens."""
    from rangekeeper.workflow.catalog import RECORD_FORMATTERS

    records, evidence_records = [], []
    for declaration in declarations:
        table = outputs[declaration["table"]]
        require_columns(table, (declaration["column"],))
        for row in table.data.rows:
            claim = evidence.tabular.claim(table, row.id, declaration["column"])
            native = [
                loc for loc in evidence.locations(claim) if loc.source.id in source_ids
            ]
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
            evidence_records.append(
                {
                    "table": declaration["table"],
                    "row": str(row.id),
                    "kind": declaration["kind"],
                    "source": str(loc.source.id),
                    "reference": dict(loc.reference),
                }
            )
    return tuple(sorted(records)), tuple(evidence_records)


def metadata(
    spec,
    produced,
    step_records,
    operations,
    implementation,
    semantic,
    dependencies,
):
    outputs = {key: item.value for key, item in produced.items()}
    source_ids = {
        item.source.id for item in produced.values() if item.source is not None
    }
    deferred, deferred_evidence = deferred_records(
        spec.model.get("deferred", ()), outputs, source_ids
    )
    result = {
        "format": "rk.workflow/v2",
        "implementation": implementation,
        "semantic_implementation": semantic,
        "semantic_version": 5,
        "step_operations": step_records,
        "python": sys.version.split()[0],
        "dependencies": {name: version(name) for name in dependencies},
        "deferred_records": deferred,
        "deferred_evidence": deferred_evidence,
        "aggregation_policies": spec.model.get("aggregates", ()),
        "specification": dict(spec.hashes),
        "review_specification": spec.to_mapping(),
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
