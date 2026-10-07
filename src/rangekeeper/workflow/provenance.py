"""Convert transient source support into schema provenance at the Model boundary."""

from typing import cast
from rangekeeper import evidence
from rangekeeper._records import JSONValue
from rangekeeper._encoding import encode
from rangekeeper._schema.records import (
    Claim,
    ClaimKind,
    Fact,
    Location,
    Method,
    Provenance,
    Source,
)
from rangekeeper.operation import _Failure


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
