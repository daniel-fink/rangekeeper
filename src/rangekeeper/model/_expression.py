"""Bounded expression analysis and predicate checks over an explicit scope.

The scope contains lookup data; functions own validation and coarse domain inference.
These operations do not evaluate equations, traverse graphs, infer full arithmetic
units, or choose a solver. Structural validation must establish record shape first.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from rangekeeper._validation import require
from rangekeeper.errors import ContractError


@dataclass(frozen=True)
class Scope:
    """Lookup tables shared by bounded mathematical checks.

    Top-level tables and the identity set are read-only. Record values are borrowed
    from the caller's prepared envelope, preserving identity; this is a short-lived
    analysis context, not an immutable published document. Checks never mutate it.
    """

    measures: Mapping[str, dict]
    entities: Mapping[str, dict]
    classifications: Mapping[str, dict]
    values: Mapping[str, dict]
    domains: Mapping[str, dict]
    functions: Mapping[str, dict]
    identities: frozenset[str]


def build_scope(document, local_values=()) -> Scope:
    """Index declarations, validate their Measure references and Function signatures.

    The prepared envelope can include fixture-only input domains. Function signature
    checking is composed explicitly after the lookup tables have been constructed.
    No external resolution or mutation of supplied records occurs.
    """
    measures: dict[str, dict] = {}
    entities: dict[str, dict] = {}
    classifications: dict[str, dict] = {}
    values: dict[str, dict] = {}
    domains: dict[str, dict] = {}
    functions: dict[str, dict] = {}
    identities: set[str] = set()

    def add(collection, record):
        identity = record["id"]
        require(identity not in identities, f"duplicate identity: {identity}")
        identities.add(identity)
        collection[identity] = record

    for measure in document.get("definitions", {}).get("measures", []):
        add(measures, measure)
    for taxonomy in document.get("definitions", {}).get("taxonomies", []):
        require(taxonomy["id"] not in identities, "duplicate taxonomy identity")
        identities.add(taxonomy["id"])
        for classification in taxonomy["classifications"]:
            add(classifications, classification)
    for entity in (document.get("entities") or []) + (document.get("assemblies") or []):
        add(entities, entity)
        for value in entity.get("characteristics", {}).get("values", []):
            add(values, value)
            require(value["measure"] in measures, "unknown Value Measure")
            domains[value["id"]] = dict(kind="measurement", measure=value["measure"])
    for value in local_values:
        add(values, value)
        require(value["measure"] in measures, "unknown Value Measure")
        domains[value["id"]] = dict(kind="measurement", measure=value["measure"])
    # Explicitly a fixture domain environment, not accepted domain Value records.
    for value in document.get("input_domains") or []:
        add(values, value)
        domains[value["id"]] = value["domain"]
    codes = set()
    for function in document.get("functions") or []:
        add(functions, function)
        require(function["code"] not in codes, "duplicate Function code")
        codes.add(function["code"])
    scope = Scope(
        measures=MappingProxyType(measures),
        entities=MappingProxyType(entities),
        classifications=MappingProxyType(classifications),
        values=MappingProxyType(values),
        domains=MappingProxyType(domains),
        functions=MappingProxyType(functions),
        identities=frozenset(identities),
    )
    for function in functions.values():
        validate_function_signature(function, scope=scope)
    return scope


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
        require(domain["measure"] in scope.measures, "unknown signature Measure")
    if "item_domain" in domain:
        validate_domain_references(domain["item_domain"], scope=scope)


def get_numerical_units(domain, *, scope: Scope) -> str | None:
    """Return the declared units of a coarse numerical domain, if known."""
    if domain["kind"] == "number":
        return "dimensionless"
    if domain["kind"] == "quantity":
        return domain.get("units")
    if domain["kind"] == "measurement":
        return scope.measures.get(domain.get("measure"), {}).get("units")
    return None


def matches_domain(actual, expected, *, scope: Scope) -> bool:
    """Compare coarse domains using exact declared unit spellings; perform no conversion."""
    # Bounded fixtures recognize identical unit spellings, not conversions.
    # Unknown compatibility fails conservatively at signature boundaries.
    if expected["kind"] == "number":
        return get_numerical_units(actual, scope=scope) == "dimensionless"
    if expected["kind"] == "quantity":
        return actual["kind"] in ("number", "quantity", "measurement") and (
            "units" not in expected
            or get_numerical_units(actual, scope=scope) == expected["units"]
        )
    if actual["kind"] != expected["kind"]:
        return False
    if "measure" in expected and actual.get("measure") != expected["measure"]:
        return False
    if expected["kind"] == "collection":
        if (
            "collection_kind" in expected
            and actual.get("collection_kind") != expected["collection_kind"]
        ):
            return False
        return matches_domain(
            actual["item_domain"], expected["item_domain"], scope=scope
        )
    return True


def infer_query_domain(query, *, scope: Scope) -> dict:
    """Validate query references and infer its collection domain without executing traversal."""
    require(query["starting_at"] in scope.entities, "unknown Query starting Entity")
    for step in query.get("steps") or []:
        if step["kind"] == "relationship":
            require(
                step["classification"] in scope.classifications,
                "unknown Relationship Classification",
            )
    filter_ = query.get("filter", {})
    if "classification" in filter_:
        require(
            filter_["classification"] in scope.classifications,
            "unknown Entity Classification",
        )
    for label in filter_.get("labels") or []:
        require(
            label["classification"] in scope.classifications,
            "unknown Label Classification",
        )
    projection = query["projection"]
    if projection["kind"] == "entity":
        item_domain = dict(kind="entity")
    elif "measure" in projection:
        require(projection["measure"] in scope.measures, "unknown projection Measure")
        item_domain = dict(kind="measurement", measure=projection["measure"])
    else:
        # The present domain Value schema only admits measurements. This is
        # not query execution and does not establish membership/cardinality.
        item_domain = dict(kind="measurement")
    return dict(
        kind="collection",
        item_domain=item_domain,
        collection_kind="set" if query["duplicates"] == "distinct" else "bag",
    )


def infer_expression_domain(node, seen=None, *, scope: Scope) -> dict:
    """Validate one expression tree and infer its coarse domain without evaluating it."""
    if seen is None:
        seen = set(scope.identities)
    require(node["id"] not in seen, "duplicate Expression identity")
    seen.add(node["id"])
    kind = node["kind"]
    if kind == "quantity":
        import math

        require(math.isfinite(node["quantity"]["magnitude"]), "non-finite magnitude")
        return dict(kind="quantity", units=node["quantity"]["units"])
    if kind == "boolean":
        return dict(kind=kind)
    if kind == "reference":
        require(node["target"] in scope.domains, "unknown Value reference")
        return scope.domains[node["target"]]
    if kind in ("binary", "unary"):
        args = [node["operand"]] if kind == "unary" else node["operands"]
        domains = [infer_expression_domain(arg, seen, scope=scope) for arg in args]
        operator = node["operator"]
        if operator in ("logical_not", "logical_and", "logical_or"):
            require(
                all(t["kind"] == "boolean" for t in domains),
                "Boolean operands required",
            )
            return dict(kind="boolean")
        if operator in ("equal", "not_equal") and all(
            t["kind"] == "boolean" for t in domains
        ):
            return dict(kind="boolean")
        require(
            all(t["kind"] in ("number", "quantity", "measurement") for t in domains),
            "numerical operands required",
        )
        if operator in (
            "equal",
            "not_equal",
            "less_than",
            "less_than_or_equal",
            "greater_than",
            "greater_than_or_equal",
        ):
            return dict(kind="boolean")
        if all(get_numerical_units(t, scope=scope) == "dimensionless" for t in domains):
            return dict(kind="number")
        if kind == "unary" and get_numerical_units(domains[0], scope=scope) is not None:
            return dict(
                kind="quantity", units=get_numerical_units(domains[0], scope=scope)
            )
        # Full unit inference is deferred. Arithmetic alone does not supply
        # a Measurement's domain meaning or a Measure identity.
        return dict(kind="quantity")
    if kind == "query":
        return infer_query_domain(node["query"], scope=scope)
    if kind == "selection":
        selection = node["selection"]
        base = infer_expression_domain(selection["base"], seen, scope=scope)
        if selection["kind"] == "member":
            # Illustrative member contracts; not a complete rich Value schema.
            members = {
                "span": {
                    "start_date": dict(kind="date"),
                    "end_date": dict(kind="date"),
                },
                "account": {"transactions": dict(kind="flow")},
            }
            result = members.get(base["kind"], {}).get(selection["member"])
            require(result is not None, "unknown or unsupported member")
            return cast(dict, result)
        require(
            base["kind"] == "collection" and base.get("collection_kind") == "sequence",
            "this index fixture requires an ordered sequence",
        )
        index_domain = infer_expression_domain(selection["index"], seen, scope=scope)
        require(
            matches_domain(index_domain, dict(kind="number"), scope=scope),
            "numerical index required",
        )
        if selection["index"]["kind"] == "quantity":
            value = selection["index"]["quantity"]["magnitude"]
            require(
                value >= 0 and int(value) == value,
                "nonnegative integer sequence index required",
            )
        return base["item_domain"]
    if kind == "call":
        call = node["call"]
        require(call["function"] in scope.functions, "unknown Function")
        function = scope.functions[call["function"]]
        parameters = function.get("parameters") or []
        positional = [p for p in parameters if p["kind"] == "positional_or_named"]
        args = call.get("arguments") or []
        require(len(args) <= len(positional), "too many positional arguments")
        bound = {p["name"]: argument for p, argument in zip(positional, args)}
        by_name = {p["name"]: p for p in parameters}
        for argument in call.get("named_arguments") or []:
            name = argument["name"]
            require(name in by_name, "unknown named argument")
            require(name not in bound, "parameter bound more than once")
            bound[name] = argument["expression"]
        for parameter in parameters:
            name = parameter["name"]
            require(
                name in bound or not parameter["required"],
                "missing required argument",
            )
            if name in bound:
                actual = infer_expression_domain(bound[name], seen, scope=scope)
                require(
                    matches_domain(actual, parameter["domain"], scope=scope),
                    f"argument domain mismatch: {name}",
                )
        return function["result"]
    raise ContractError(f"unsupported expression kind: {kind}")


def _require_constraint_identities(constraints, *, scope: Scope) -> set[str]:
    """Reserve Constraint declarations before walking the combined expression scope."""
    seen = set(scope.identities)
    for index, constraint in enumerate(constraints):
        identity = constraint["id"]
        require(
            identity not in seen,
            "duplicate Constraint identity",
            code="semantic.identity",
            path=f"/constraints/{index}/id",
        )
        seen.add(identity)
    return seen


def _expression_nodes(node):
    """Visit embedded expression nodes; referenced Values are not traversed."""
    yield node
    children = list(node.get("operands") or [])
    if "operand" in node:
        children.append(node["operand"])
    if "call" in node:
        children.extend(node["call"].get("arguments") or [])
        children.extend(
            arg["expression"] for arg in node["call"].get("named_arguments") or []
        )
    if "selection" in node:
        children.append(node["selection"]["base"])
        if "index" in node["selection"]:
            children.append(node["selection"]["index"])
    for child in children:
        yield from _expression_nodes(child)


def validate_constraint_predicates(constraints, expressions, *, scope: Scope) -> None:
    """Validate mathematical identities, predicate references and Boolean domains.

    Names/codes must be checked separately in each owning collection. Constraint
    and expression UUIDs share this combined scope; multiple Constraints may refer
    to one expression node. Prerequisite identity/expression failures stop dependent
    predicate checks. No input is changed and satisfaction is never evaluated.
    """
    seen = _require_constraint_identities(constraints, scope=scope)
    by_id: dict[str, dict] = {}
    for root in expressions:
        infer_expression_domain(root, seen, scope=scope)
        by_id.update((node["id"], node) for node in _expression_nodes(root))
    for index, constraint in enumerate(constraints):
        predicate = constraint["predicate"]
        path = f"/constraints/{index}/predicate"
        require(
            predicate in by_id,
            "unknown or non-Expression Constraint predicate",
            code="reference.predicate",
            path=path,
        )
        domain = infer_expression_domain(by_id[predicate], scope=scope)
        require(
            domain["kind"] == "boolean",
            "Constraint predicate must be Boolean",
            code="semantic.predicate",
            path=path,
        )
