"""One semantic expression traversal in an explicit mathematical scope."""

from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from uuid import UUID
from rangekeeper.shared.validation import require
from rangekeeper.shared.errors import ContractError
from rangekeeper.model.scope import Scope, resolve_reference
from rangekeeper.model.expression.domains import (
    compare_domains,
    DomainCompatibility,
    infer_operator_domain,
    infer_selection_domain,
)


def validate_function_signature(function, *, scope: Scope) -> None:
    """Check parameter ordering, domain references and empty-collection behavior."""
    names = set()
    optional_seen = False
    named_seen = False
    for parameter in function.get("parameters") or []:
        require(parameter["name"] not in names, "duplicate parameter name")
        names.add(parameter["name"])
        if parameter["kind"] == "named_only":
            named_seen = True
        else:
            require(not named_seen, "positional parameter follows named-only parameter")
            if parameter["required"]:
                require(
                    not optional_seen,
                    "required positional parameter follows optional",
                )
            else:
                optional_seen = True
        validate_domain_references(parameter["domain"], scope=scope)
        if parameter["domain"]["kind"] == "collection":
            require(
                "empty_collection" in function, "missing empty-collection behaviour"
            )
    validate_domain_references(function["result"], scope=scope)
    if function.get("empty_collection") == "zero":
        require(
            function["result"]["kind"] in ("number", "quantity", "measurement"),
            "zero empty result must be numerical",
        )


def validate_domain_references(domain, *, scope: Scope) -> None:
    """Require Measure references within this scope, including collection item domains."""
    if "measure" in domain:
        require(UUID(domain["measure"]) in scope.measures, "unknown signature Measure")
    if "item_domain" in domain:
        validate_domain_references(domain["item_domain"], scope=scope)


def validate_query_references(query, *, scope: Scope) -> None:
    """Check declared query references without traversing the graph."""
    require(
        UUID(query["starting_at"]) in scope.entities, "unknown Query starting Entity"
    )
    for step in query.get("steps") or []:
        if step["kind"] == "relationship":
            require(
                UUID(step["classification"]) in scope.classifications,
                "unknown Relationship Classification",
            )
    filter_ = query.get("filter", {})
    if "classification" in filter_:
        require(
            UUID(filter_["classification"]) in scope.classifications,
            "unknown Entity Classification",
        )
    for label in filter_.get("labels") or []:
        require(
            UUID(label["classification"]) in scope.classifications,
            "unknown Label Classification",
        )


def infer_query_domain(query, *, scope: Scope) -> dict:
    """Infer a conservative collection domain from declared candidates only."""
    validate_query_references(query, scope=scope)
    projection = query["projection"]
    if projection["kind"] == "entity":
        item_domain = dict(kind="entity")
    else:
        if "measure" in projection:
            require(
                UUID(projection["measure"]) in scope.measures,
                "unknown projection Measure",
            )
        candidates = [
            value
            for value in scope.values.values()
            if ("key" not in projection or value.get("key") == projection["key"])
            and (
                "measure" not in projection
                or value.get("measure") == projection["measure"]
            )
        ]
        domains = [scope.domains[UUID(value["id"])] for value in candidates]
        item_domain = (
            domains[0]
            if domains and all(domain == domains[0] for domain in domains)
            else dict(kind="unknown")
        )
    return dict(
        kind="collection",
        item_domain=item_domain,
        collection_kind="set" if query["duplicates"] == "distinct" else "bag",
    )


def _infer_expression_domain(node, seen, *, scope: Scope, analysis, path) -> dict:
    """Validate one expression tree and infer its coarse domain without evaluating it."""
    require(UUID(node["id"]) not in seen, "duplicate Expression identity")
    seen.add(UUID(node["id"]))
    kind = node["kind"]
    if kind == "quantity":
        import math

        require(math.isfinite(node["quantity"]["magnitude"]), "non-finite magnitude")
        return dict(kind="quantity", units=node["quantity"]["units"])
    if kind == "boolean":
        return dict(kind=kind)
    if kind == "reference":
        target = node["target"]
        value, movement = resolve_reference(target, scope.targets)
        if movement is not None:
            return dict(kind="quantity", units=value["flow"]["units"])
        return scope.domains[UUID(value["id"])]
    if kind in ("binary", "unary"):
        args = [node["operand"]] if kind == "unary" else node["operands"]
        domains = [
            _analyze_node(
                arg,
                seen,
                scope=scope,
                analysis=analysis,
                path=path + ("/operand" if kind == "unary" else f"/operands/{index}"),
            )
            for index, arg in enumerate(args)
        ]
        return infer_operator_domain(
            node["operator"], domains, unary=kind == "unary", scope=scope
        )
    if kind == "query":
        return infer_query_domain(node["query"], scope=scope)
    if kind == "selection":
        selection = node["selection"]
        base = _analyze_node(
            selection["base"],
            seen,
            scope=scope,
            analysis=analysis,
            path=path + "/selection/base",
        )
        if selection["kind"] == "member":
            return infer_selection_domain(base, member=selection["member"], scope=scope)
        index_domain = _analyze_node(
            selection["index"],
            seen,
            scope=scope,
            analysis=analysis,
            path=path + "/selection/index",
        )
        literal = selection["index"].get("quantity", {}).get("magnitude")
        return infer_selection_domain(
            base, index=index_domain, literal=literal, scope=scope
        )
    if kind == "call":
        call = node["call"]
        require(UUID(call["function"]) in scope.functions, "unknown Function")
        function = scope.functions[UUID(call["function"])]
        parameters = function.get("parameters") or []
        bound = bind_arguments(call, function)
        for parameter in parameters:
            name = parameter["name"]
            require(
                name in bound or not parameter["required"],
                "missing required argument",
            )
            if name in bound:
                actual = _analyze_node(
                    bound[name][0],
                    seen,
                    scope=scope,
                    analysis=analysis,
                    path=path + "/call" + bound[name][1],
                )
                comparison = compare_domains(actual, parameter["domain"], scope=scope)
                require(
                    comparison is DomainCompatibility.COMPATIBLE,
                    (
                        f"argument domain not established: {name}"
                        if comparison is DomainCompatibility.UNPROVEN
                        else f"argument domain mismatch: {name}"
                    ),
                    path=path + "/call" + bound[name][1],
                )
        return function["result"]
    raise ContractError(f"unsupported expression kind: {kind}")


def _require_constraint_identities(constraints, *, scope: Scope) -> set[UUID]:
    """Reserve Constraint declarations before walking the combined expression scope."""
    seen = set(scope.identities)
    for index, constraint in enumerate(constraints):
        identity = UUID(constraint["id"])
        require(
            identity not in seen,
            "duplicate Constraint identity",
            code="semantic.identity",
            path=f"/constraints/{index}/id",
        )
        seen.add(identity)
    return seen


def validate_constraint_predicates(
    constraints,
    expressions,
    *,
    scope: Scope,
    expression_paths=None,
    constraint_paths=None,
):
    """Validate mathematical identities, predicate references and Boolean domains.

    Names/codes must be checked separately in each owning collection. Constraint
    and expression UUIDs share this combined scope; multiple Constraints may refer
    to one expression node. Prerequisite identity/expression failures stop dependent
    predicate checks. No input is changed and satisfaction is never evaluated.
    """
    seen = _require_constraint_identities(constraints, scope=scope)
    analysis = analyze_expressions(
        expressions, scope=scope, reserved=seen, locations=expression_paths
    )
    for index, constraint in enumerate(constraints):
        predicate = UUID(constraint["predicate"])
        path = (
            constraint_paths[index]
            if constraint_paths is not None
            else f"/constraints/{index}"
        ) + "/predicate"
        require(
            predicate in analysis.nodes_by_id,
            "unknown or non-Expression Constraint predicate",
            code="reference.predicate",
            path=path,
        )
        require(
            analysis.domains_by_id[predicate]["kind"] == "boolean",
            "Constraint predicate must be Boolean",
            code="semantic.predicate",
            path=path,
        )
    return analysis


@dataclass(frozen=True)
class ExpressionAnalysis:
    nodes_by_id: Mapping
    domains_by_id: Mapping
    paths_by_id: Mapping


def _analyze_node(node, seen, *, scope, analysis, path):
    try:
        result = _infer_expression_domain(
            node, seen, scope=scope, analysis=analysis, path=path
        )
    except ContractError as error:
        if error.path:
            raise
        raise ContractError(str(error), code=error.code, path=path) from error
    identity = UUID(node["id"])
    analysis[0][identity] = node
    analysis[1][identity] = result
    analysis[2][identity] = path
    return result


def analyze_expressions(expressions, *, scope, reserved=(), locations=None):
    """Analyze each declaration once and retain its domain for all consumers."""
    seen = set(scope.identities) | set(reserved)
    nodes, domains, paths = {}, {}, {}
    for index, node in enumerate(expressions):
        path = locations[index] if locations is not None else f"/expressions/{index}"
        _analyze_node(
            node, seen, scope=scope, analysis=(nodes, domains, paths), path=path
        )
    return ExpressionAnalysis(
        *(MappingProxyType(value) for value in (nodes, domains, paths))
    )


def infer_expression_domain(node, seen=None, *, scope: Scope) -> dict:
    analysis = analyze_expressions((node,), scope=scope, reserved=seen or ())
    return analysis.domains_by_id[UUID(node["id"])]


def bind_arguments(call, function):
    """Bind arguments without analyzing or evaluating their expressions."""
    parameters = function.get("parameters") or []
    positional = [p for p in parameters if p["kind"] == "positional_or_named"]
    args = call.get("arguments") or []
    require(len(args) <= len(positional), "too many positional arguments")
    bound = {
        p["name"]: (argument, f"/arguments/{index}")
        for index, (p, argument) in enumerate(zip(positional, args))
    }
    by_name = {p["name"]: p for p in parameters}
    for index, argument in enumerate(call.get("named_arguments") or []):
        name = argument["name"]
        require(name in by_name, "unknown named argument")
        require(name not in bound, "parameter bound more than once")
        bound[name] = (argument["expression"], f"/named_arguments/{index}/expression")
    for parameter in parameters:
        require(
            parameter["name"] in bound or not parameter["required"],
            "missing required argument",
        )
    return bound
