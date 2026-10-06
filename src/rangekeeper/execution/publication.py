"""Construct detached candidate revisions; persist only after independent acceptance."""

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID, uuid4

from ..model import Model
from ..model.update import Update
from .._schema.records import Quantity, System, Provenance
from ..io import json
from ..references import DocumentResolver
from .preparation import Prepared
from .errors import NumericalError


def candidate(
    prepared: Prepared, unknowns: Mapping[str, float], *, run_id: UUID
) -> Model:
    """Construct and round-trip one candidate, preserving shape and unrelated content.

    Private symbol tokens never become domain identities. Each changed Movement
    receives new evidence; old Claims remain available as revision history.
    """
    from .evaluator import quantity as finite_quantity

    if set(unknowns) != set(prepared.unknowns):
        raise NumericalError(
            "backend candidate does not contain exactly the unknown symbols"
        )
    quantities = dict(prepared.assignments)
    for token, magnitude in unknowns.items():
        quantities[token] = finite_quantity(magnitude, prepared.value_units[token])
    data = cast(dict[str, Any], prepared.model.to_data())
    provenance = data.setdefault("provenance", {})
    claims = provenance.setdefault("claims", [])
    changed = {str(prepared.references[token].value) for token in quantities}
    facts = [f for f in provenance.get("facts", []) if f["target"] not in changed]

    def claim(content, method):
        identity = str(uuid4())
        claims.append(
            dict(
                id=identity,
                kind="asserted",
                content=content,
                method=dict(
                    code=method,
                    version="2",
                    description=f"Run {run_id}; Specification {prepared.composition.root_id}; independently checked publication.",
                ),
            )
        )
        return identity

    def replace(node):
        if isinstance(node, dict):
            identity = node.get("id")
            if identity in changed and node.get("kind") in ("measurement", "flow"):
                if node["kind"] == "measurement":
                    node["quantity"] = quantities[identity].to_data()
                else:
                    for movement in node["flow"]["movements"]:
                        token = identity + "/" + movement["key"]
                        if token in quantities:
                            amount = quantities[token].to_data()
                            movement["magnitude"] = amount["magnitude"]
                            movement["claims"] = [
                                claim(
                                    dict(
                                        target=prepared.references[token].to_data(),
                                        quantity=amount,
                                    ),
                                    (
                                        "rangekeeper.movement.assignment"
                                        if token in prepared.assignments
                                        else "rangekeeper.movement.solution"
                                    ),
                                )
                            ]
                content = {
                    name: node[name]
                    for name in ("measure", "quantity", "flow")
                    if name in node
                }
                evidence = claim(content, "rangekeeper.value.publication")
                facts.append(dict(target=identity, claims=[evidence]))
            for child in node.values():
                replace(child)
        elif isinstance(node, list):
            for child in node:
                replace(child)

    replace(data.get("system", {}))
    if not quantities:
        claim(dict(model=str(prepared.model.id)), "rangekeeper.feasibility")
    provenance["facts"] = facts
    result = prepared.model.revise(
        Update(
            system=System.from_data(data.get("system", {})),
            provenance=Provenance.from_data(provenance),
        )
    )
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
