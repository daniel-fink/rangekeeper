"""Bounded Formulation conformance checks, not a Model schema or solver adapter.

The example envelope supplies Definitions, domain objects, and root Formulations. These
checks establish canonical ownership, scoped names, and symbolic references for
that envelope. Structural validation must run first for ordinary serialized input.
"""

import math

from expression_contract import Scope, require


def unique_names(records, field, label):
    seen = set()
    for record in records:
        name = record.get(field)
        if name is not None:
            require(name not in seen, f"duplicate {label}: {name}")
            seen.add(name)


def check_ownership(document):
    """Reject repeated identities and cyclic in-memory/YAML containment."""
    identities = set()
    active = set()

    def visit(node):
        if not isinstance(node, (dict, list)):
            return
        require(id(node) not in active, "cyclic containment")
        active.add(id(node))
        if isinstance(node, dict):
            if "id" in node:
                identity = node["id"]
                require(identity not in identities, f"duplicate identity: {identity}")
                identities.add(identity)
            children = node.values()
        else:
            children = node
        for child in children:
            visit(child)
        active.remove(id(node))

    visit(document)


def validate_formulations(document, additional_formulations=()):
    """Validate the fixture scope without executing its mathematics.

    Returns the Expression scope so checks can inspect symbol identity. Separate
    Formulations may use the same local codes or alias the same shared Value. Expression
    references resolve by UUID across the scope, independent of collection order.
    """
    # Specification additions share mathematical identity scope, but their root codes
    # belong to a separate owning collection from the Model's root codes.
    check_ownership(
        dict(document, additional_formulations=list(additional_formulations))
    )
    require(
        not document.get("expressions") and not document.get("constraints"),
        "Formulation scope cannot also own root Expressions or Constraints",
    )
    formulations = []

    def collect(siblings):
        unique_names(siblings, "code", "sibling Formulation code")
        for formulation in siblings:
            formulations.append(formulation)
            unique_names(formulation.get("bindings") or [], "name", "Binding name")
            unique_names(formulation.get("values") or [], "key", "local Value key")
            unique_names(
                formulation.get("constraints") or [], "code", "Constraint code"
            )
            collect(formulation.get("formulations") or [])

    collect(document.get("formulations") or [])
    collect(additional_formulations)
    local_values = [
        value
        for formulation in formulations
        for value in formulation.get("values") or []
    ]
    # Relationship Values share the same reference scope as Entity/Assembly Values.
    relationship_values = []
    domain_objects = []
    for collection in ("entities", "assemblies", "relationships"):
        domain_objects.extend(document.get(collection) or [])
    for record in domain_objects:
        characteristics = record.get("characteristics") or {}
        unique_names(characteristics.get("values") or [], "key", "domain Value key")
        unique_names(characteristics.get("labels") or [], "key", "Label key")
    for relationship in document.get("relationships") or []:
        relationship_values.extend(
            (relationship.get("characteristics") or {}).get("values") or []
        )
    scope = Scope(document, local_values=local_values + relationship_values)
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
    scope.validate_constraints(constraints, expressions, check_codes=False)
    return scope
