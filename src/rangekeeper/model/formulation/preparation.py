"""Prepare canonical Model or conformance declarations for bounded mathematics.

Canonical callers supply structurally checked records and checked declaration
ownership. Conformance envelopes supply only mathematical/domain declarations.
Neither path evaluates quantities, executes graph queries or invokes a solver.
"""

import math
from uuid import UUID

from rangekeeper.shared.validation import require, require_unique, require_ownership
from rangekeeper.model.scope import build_scope, validate_values
from rangekeeper.model.expression.validation import (
    validate_constraint_predicates,
    validate_function_signature,
)
from rangekeeper.model.formulation.validation import validate_formulation_names


def _walk_formulations(formulations, path):
    """Yield root and nested Formulations with their original document locations."""
    for index, formulation in enumerate(formulations):
        current = f"{path}/{index}"
        yield formulation, current
        yield from _walk_formulations(
            formulation.get("formulations") or [], current + "/formulations"
        )


def prepare_formulations(document, additional_formulations=(), *, path=""):
    """Return one Scope, ExpressionAnalysis and original Formulation locations.

    Different owners may reuse local codes or bind the same shared Value. References
    resolve by UUID across the combined scope, independent of collection order.
    """
    additional_formulations = tuple(additional_formulations)
    # Specification additions share mathematical identity scope, but their root codes
    # belong to a separate owning collection from the Model's root codes.
    canonical = "metadata" in document
    system = (document.get("system") or {}) if canonical else document
    if not canonical:
        require_ownership(
            dict(document, additional_formulations=list(additional_formulations))
        )
    require(
        not system.get("expressions") and not system.get("constraints"),
        "Formulation scope cannot also own root Expressions or Constraints",
    )
    roots = system.get("formulations") or []
    validate_formulation_names(roots, path=path + "/formulations")
    validate_formulation_names(additional_formulations, path="/additional_formulations")
    located = [
        *_walk_formulations(roots, path + "/formulations"),
        *_walk_formulations(additional_formulations, "/additional_formulations"),
    ]
    formulations = [formulation for formulation, _ in located]
    local_values = [
        value
        for formulation in formulations
        for value in formulation.get("values") or []
    ]
    # Relationship Values share the same reference scope as Entity/Assembly Values.
    relationship_values = []
    for collection in ("entities", "assemblies", "relationships"):
        for index, record in enumerate(system.get(collection) or []):
            characteristics = record.get("characteristics") or {}
            current = f"{path}/{collection}/{index}/characteristics"
            require_unique(
                characteristics.get("values") or [],
                "key",
                "domain Value key",
                path=current + "/values",
            )
            require_unique(
                characteristics.get("labels") or [],
                "key",
                "Label key",
                path=current + "/labels",
            )
    for relationship in system.get("relationships") or []:
        relationship_values.extend(
            (relationship.get("characteristics") or {}).get("values") or []
        )
    scope = build_scope(document, local_values=local_values + relationship_values)
    validate_values(scope)
    for function in scope.functions.values():
        validate_function_signature(function, scope=scope)
    for value in scope.values.values():
        quantity = value.get("quantity")
        if quantity is not None:
            require(math.isfinite(quantity["magnitude"]), "non-finite Value magnitude")
    for formulation, owner in located:
        for index, binding in enumerate(formulation.get("bindings") or []):
            require(
                UUID(binding["value"]) in scope.values,
                "unknown or non-Value Binding target",
                path=f"{owner}/bindings/{index}/value",
            )
    expressions = [
        node
        for formulation in formulations
        for node in formulation.get("expressions") or []
    ]
    constraints = [
        record
        for formulation in formulations
        for record in formulation.get("constraints") or []
    ]
    analysis = validate_constraint_predicates(
        constraints,
        expressions,
        scope=scope,
        expression_paths=[
            f"{owner}/expressions/{index}"
            for formulation, owner in located
            for index, _ in enumerate(formulation.get("expressions") or ())
        ],
        constraint_paths=[
            f"{owner}/constraints/{index}"
            for formulation, owner in located
            for index, _ in enumerate(formulation.get("constraints") or ())
        ],
    )
    return scope, analysis, tuple(located)
