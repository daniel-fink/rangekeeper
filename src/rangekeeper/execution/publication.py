"""Construct detached candidate revisions; persist only after independent acceptance."""

from collections.abc import Mapping
from uuid import UUID, uuid4

from ..model import Model
from ..model.update import Update
from .._schema.records import Quantity, System, Provenance
from ..io import json
from ..references import DocumentResolver
from .preparation import Prepared
from .errors import NumericalError


def candidate(
    prepared: Prepared, unknowns: Mapping[UUID, float], *, run_id: UUID
) -> Model:
    """Build and codec-round-trip a new Model with canonical scalar quantities.

    Preserve definitions, mathematical declarations, unrelated content and all old
    Claims. Replace Facts for the written Values with fresh method-labelled Claims;
    do not leave changed quantities attached to their previous accepted evidence.
    Method descriptions identify the Run/Specification without inventing a new
    schema-level cross-document provenance reference.
    """
    if set(unknowns) != set(prepared.unknowns):
        raise NumericalError(
            "backend candidate does not contain exactly the unknown UUIDs"
        )
    quantities = dict(prepared.assignments)
    for id, magnitude in unknowns.items():
        from .evaluator import quantity as finite_quantity

        quantities[id] = finite_quantity(magnitude, prepared.value_units[id])
    system = prepared.model.system.to_data() if prepared.model.system else {}
    serialized_quantities = {
        str(id): quantity.to_data() for id, quantity in quantities.items()
    }

    def replace(node):
        if isinstance(node, dict):
            id = node.get("id")
            if id in serialized_quantities and node.get("kind") == "measurement":
                node["quantity"] = serialized_quantities[id]
            for value in node.values():
                replace(value)
        elif isinstance(node, list):
            for value in node:
                replace(value)

    replace(system)
    provenance = (
        prepared.model.provenance.to_data() if prepared.model.provenance else {}
    )
    original = prepared.model.provenance
    claims = [claim.to_data() for claim in (original.claims or ())] if original else []
    facts = (
        [
            fact.to_data()
            for fact in (original.facts or ())
            if fact.target not in quantities
        ]
        if original
        else []
    )
    for id, quantity in quantities.items():
        claim_id = uuid4()
        claims.append(
            {
                "id": str(claim_id),
                "kind": "asserted",
                "content": {
                    "measure": str(prepared.values[id].measure),
                    "quantity": quantity.to_data(),
                },
                "method": {
                    "code": (
                        "rangekeeper.scalar.assignment"
                        if id in prepared.assignments
                        else "rangekeeper.scalar.solution"
                    ),
                    "version": "1",
                    "description": f"Run {run_id}; Specification {prepared.composition.root_id}; independently checked scalar publication.",
                },
            }
        )
        facts.append({"target": str(id), "claims": [str(claim_id)]})
    if not quantities:
        claims.append(
            {
                "id": str(uuid4()),
                "kind": "asserted",
                "content": {"model": str(prepared.model.id)},
                "method": {
                    "code": "rangekeeper.scalar.feasibility",
                    "version": "1",
                    "description": f"Run {run_id}; Specification {prepared.composition.root_id}; accepted constant-only mathematics.",
                },
            }
        )
    provenance.update(claims=claims, facts=facts)
    result = prepared.model.revise(
        Update(
            system=System.from_data(system),
            provenance=Provenance.from_data(provenance),
        )
    )
    # Numerical acceptance inspects exactly what interchange will deliver.
    return json.loads(json.dumps(result), kind=Model)


class CandidateResolver:
    """Overlay one not-yet-published Model for final Run validation before any put."""

    def __init__(self, candidate: Model, resolver: DocumentResolver) -> None:
        self.candidate = candidate
        self.resolver = resolver

    def load_model(self, id: UUID) -> Model:
        return (
            self.candidate if id == self.candidate.id else self.resolver.load_model(id)
        )

    def load_specification(self, id: UUID):
        return self.resolver.load_specification(id)

    def load_run(self, id: UUID):
        return self.resolver.load_run(id)
