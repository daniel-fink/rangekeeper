"""Stage 6: make a detached candidate revision; nothing is stored here."""

import json
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID, uuid4

from rangekeeper.execution.errors import NumericalError
from rangekeeper.execution.preparation import Binding
from rangekeeper.model import Model
from rangekeeper.model.targets import target_value
from rangekeeper.schema.index import walk_data
from rangekeeper.schema.revision import check_revision
from rangekeeper.schema.runtime import copy_json


def make_candidate(
    *,
    binding: Binding,
    unknowns: Mapping[UUID, float],
    run_id: UUID,
) -> Model:
    """Write solved values into a new candidate Model revision and round-trip it.

    The candidate keeps the shape and the unrelated content of the input Model.
    Only independent verification decides whether it is published.

    Private symbol tokens never become domain identities. Each changed Movement
    receives new evidence; old Claims remain available as revision history.
    """
    from rangekeeper.model.expression.evaluation import finite_quantity

    if set(unknowns) != set(binding.unknowns):
        raise NumericalError(
            "backend candidate does not contain exactly the unknown symbols"
        )
    quantities = dict(binding.assignments)
    for token, magnitude in unknowns.items():
        try:
            quantities[token] = finite_quantity(magnitude, binding.value_units[token])
        except (ArithmeticError, TypeError, ValueError) as error:
            raise NumericalError(str(error)) from error
    data = cast(dict[str, Any], binding.model.to_data())
    provenance = data.setdefault("provenance", {})
    claims = provenance.setdefault("claims", [])
    changed = {
        str(target_value(binding.model, binding.references[token]).id)
        for token in quantities
    }
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
                    description=f"Run {run_id}; Specification {binding.composition.root_id}; independently checked publication.",
                ),
            )
        )
        return identity

    for node, _ in walk_data("System", data.get("system", {})):
        identity = node.get("id")
        if identity in changed and node.get("kind") in ("measurement", "flow"):
            if node["kind"] == "measurement":
                node["quantity"] = quantities[UUID(identity)].to_data()
            else:
                for movement in node["flow"]["movements"]:
                    token = UUID(movement["id"])
                    if token in quantities:
                        amount = quantities[token].to_data()
                        movement["magnitude"] = amount["magnitude"]
                        movement["claims"] = [
                            claim(
                                dict(
                                    target=binding.references[token].to_data(),
                                    quantity=amount,
                                ),
                                (
                                    "rangekeeper.movement.assignment"
                                    if token in binding.assignments
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
    if not quantities:
        claim(dict(model=str(binding.model.id)), "rangekeeper.feasibility")
    provenance["facts"] = facts
    data["metadata"] = dict(
        data["metadata"], id=str(uuid4()), previous=str(binding.model.id)
    )
    # Round-trip through strict JSON, as the codecs do, so the candidate holds
    # only what a stored revision can hold. Then build and check it once.
    text = json.dumps(data, ensure_ascii=False, allow_nan=False)
    candidate = Model.from_data(
        copy_json(json.loads(text)), units=binding.model.unit_system
    )
    check_revision(binding.model._record, candidate._record)
    return candidate
