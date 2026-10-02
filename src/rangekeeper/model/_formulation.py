"""Bounded Formulation conformance checks, not a Model schema or solver adapter.

The example envelope supplies Definitions, domain objects, and root Formulations. These
checks establish canonical ownership, scoped names, and symbolic references for
that envelope. Structural validation must run first for ordinary serialized input.
"""

import math

from rangekeeper._validation import require, require_unique, require_ownership
from rangekeeper.model._expression import build_scope, validate_constraint_predicates
from rangekeeper.errors import ContractError


def validate_formulation_names(formulations, *, path="/formulations") -> None:
    """Check names within each owner without resolving mathematical references.

    Root and nested sibling codes, Binding names, Value keys and Constraint codes
    have separate owning collections. This same rule serves complete Models and
    partial Specifications; distinct owners may reuse the same names.
    """
    require_unique(formulations, "code", "sibling Formulation code", path=path)
    for index, formulation in enumerate(formulations):
        current = f"{path}/{index}"
        for collection, field, label in (
            ("bindings", "name", "Binding name"),
            ("values", "key", "local Value key"),
            ("constraints", "code", "Constraint code"),
        ):
            require_unique(
                formulation.get(collection) or [],
                field,
                label,
                path=f"{current}/{collection}",
            )
        validate_formulation_names(
            formulation.get("formulations") or [], path=f"{current}/formulations"
        )


def _walk_formulations(formulations, path):
    """Yield root and nested Formulations in document order."""
    for index, formulation in enumerate(formulations):
        current = f"{path}/{index}"
        yield formulation, current
        yield from _walk_formulations(
            formulation.get("formulations") or [], current + "/formulations"
        )


def validate_formulations(document, additional_formulations=(), *, path=""):
    """Validate the fixture scope without executing its mathematics.

    Returns the Expression scope so checks can inspect symbol identity. Separate
    Formulations may use the same local codes or alias the same shared Value. Expression
    references resolve by UUID across the scope, independent of collection order.
    """
    # Specification additions share mathematical identity scope, but their root codes
    # belong to a separate owning collection from the Model's root codes.
    require_ownership(
        dict(document, additional_formulations=list(additional_formulations))
    )
    require(
        not document.get("expressions") and not document.get("constraints"),
        "Formulation scope cannot also own root Expressions or Constraints",
    )
    roots = document.get("formulations") or []
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
        for index, record in enumerate(document.get(collection) or []):
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
    for relationship in document.get("relationships") or []:
        relationship_values.extend(
            (relationship.get("characteristics") or {}).get("values") or []
        )
    scope = build_scope(document, local_values=local_values + relationship_values)
    for value in scope.values.values():
        quantity = value.get("quantity")
        if quantity is not None:
            require(math.isfinite(quantity["magnitude"]), "non-finite Value magnitude")
    for formulation in formulations:
        for binding in formulation.get("bindings") or []:
            require(
                binding["value"] in scope.values, "unknown or non-Value Binding target"
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
    # Codes are checked within each owning Formulation above, rather than across Formulations.
    try:
        validate_constraint_predicates(constraints, expressions, scope=scope)
    except ContractError as error:
        # The mathematical scope combines owners. Translate a flattened Constraint
        # position back to the owning Formulation for user-facing diagnostics.
        if error.path.startswith("/constraints/"):
            locations = [
                f"{owner}/constraints/{index}"
                for formulation, owner in located
                for index, _ in enumerate(formulation.get("constraints") or [])
            ]
            _, _, position, *tail = error.path.split("/")
            location = locations[int(position)] + ("/" + "/".join(tail) if tail else "")
            raise ContractError(str(error), code=error.code, path=location) from error
        raise
    return scope
