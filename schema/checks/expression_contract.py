"""Bounded expression/constraint checks, not a production compiler or executor.

These checks exercise references, signatures and coarse domains for the accompanying
fixtures. They deliberately do not traverse a graph, evaluate expressions, prove
unit compatibility, construct rich Value payloads, or select a solver.
"""


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


class Scope:
    def __init__(self, document, local_values=()):
        self.measures = {}
        self.entities = {}
        self.classifications = {}
        self.values = {}
        self.domains = {}
        self.functions = {}
        identities = set()

        def add(collection, record):
            identity = record["id"]
            require(identity not in identities, f"duplicate identity: {identity}")
            identities.add(identity)
            collection[identity] = record

        for measure in document.get("definitions", {}).get("measures", []):
            add(self.measures, measure)
        for taxonomy in document.get("definitions", {}).get("taxonomies", []):
            require(taxonomy["id"] not in identities, "duplicate taxonomy identity")
            identities.add(taxonomy["id"])
            for classification in taxonomy["classifications"]:
                add(self.classifications, classification)
        for entity in (document.get("entities") or []) + (
            document.get("assemblies") or []
        ):
            add(self.entities, entity)
            for value in entity.get("characteristics", {}).get("values", []):
                add(self.values, value)
                require(value["measure"] in self.measures, "unknown Value Measure")
                self.domains[value["id"]] = dict(
                    kind="measurement", measure=value["measure"]
                )
        for value in local_values:
            add(self.values, value)
            require(value["measure"] in self.measures, "unknown Value Measure")
            self.domains[value["id"]] = dict(
                kind="measurement", measure=value["measure"]
            )
        # Explicitly a fixture domain environment, not accepted domain Value records.
        for value in document.get("input_domains") or []:
            add(self.values, value)
            self.domains[value["id"]] = value["domain"]
        codes = set()
        for function in document.get("functions") or []:
            add(self.functions, function)
            require(function["code"] not in codes, "duplicate Function code")
            codes.add(function["code"])
            self.signature(function)
        self.identities = identities

    def validate_constraints(self, constraints, expressions, check_codes=True):
        """Check predicate references and domains without evaluating satisfaction.

        The supplied collections are a fixture scope, not a Model schema. Check
        each expression tree once for unique identities, then permit repeated
        references to any of its nodes from separate Constraints. Formulation fixtures
        check codes per owning Formulation before checking the combined UUID scope.
        """
        seen = set(self.identities)
        codes = set()
        for constraint in constraints:
            identity = constraint["id"]
            require(identity not in seen, "duplicate Constraint identity")
            seen.add(identity)
            code = constraint.get("code")
            if code is not None and check_codes:
                require(code not in codes, "duplicate Constraint code")
                codes.add(code)

        def nodes(node):
            yield node
            children = list(node.get("operands") or [])
            if "operand" in node:
                children.append(node["operand"])
            if "call" in node:
                children.extend(node["call"].get("arguments") or [])
                children.extend(
                    argument["expression"]
                    for argument in node["call"].get("named_arguments") or []
                )
            if "selection" in node:
                children.append(node["selection"]["base"])
                if "index" in node["selection"]:
                    children.append(node["selection"]["index"])
            for child in children:
                yield from nodes(child)

        by_id = {}
        for root in expressions:
            self.expression(root, seen)
            by_id.update((node["id"], node) for node in nodes(root))
        for constraint in constraints:
            predicate = constraint["predicate"]
            require(
                predicate in by_id,
                "unknown or non-Expression Constraint predicate",
            )
            domain = self.expression(by_id[predicate])
            require(domain["kind"] == "boolean", "Constraint predicate must be Boolean")

    def signature(self, function):
        names = set()
        optional_seen = False
        named_seen = False
        for parameter in function.get("parameters") or []:
            require(parameter["name"] not in names, "duplicate parameter name")
            names.add(parameter["name"])
            if parameter["kind"] == "named_only":
                named_seen = True
            else:
                require(
                    not named_seen, "positional parameter follows named-only parameter"
                )
                if parameter["required"]:
                    require(
                        not optional_seen,
                        "required positional parameter follows optional",
                    )
                else:
                    optional_seen = True
            self.domain_references(parameter["domain"])
            if parameter["domain"]["kind"] == "collection":
                require(
                    "empty_collection" in function, "missing empty-collection behaviour"
                )
        self.domain_references(function["result"])
        if function.get("empty_collection") == "zero":
            require(
                function["result"]["kind"] in ("number", "quantity", "measurement"),
                "zero empty result must be numerical",
            )

    def domain_references(self, domain):
        if "measure" in domain:
            require(domain["measure"] in self.measures, "unknown signature Measure")
        if "item_domain" in domain:
            self.domain_references(domain["item_domain"])

    def numerical_units(self, domain):
        if domain["kind"] == "number":
            return "dimensionless"
        if domain["kind"] == "quantity":
            return domain.get("units")
        if domain["kind"] == "measurement":
            return self.measures.get(domain.get("measure"), {}).get("units")

    def matches(self, actual, expected):
        # Bounded fixtures recognize identical unit spellings, not conversions.
        # Unknown compatibility fails conservatively at signature boundaries.
        if expected["kind"] == "number":
            return self.numerical_units(actual) == "dimensionless"
        if expected["kind"] == "quantity":
            return actual["kind"] in ("number", "quantity", "measurement") and (
                "units" not in expected
                or self.numerical_units(actual) == expected["units"]
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
            return self.matches(actual["item_domain"], expected["item_domain"])
        return True

    def query_domain(self, query):
        require(query["starting_at"] in self.entities, "unknown Query starting Entity")
        for step in query.get("steps") or []:
            if step["kind"] == "relationship":
                require(
                    step["classification"] in self.classifications,
                    "unknown Relationship Classification",
                )
        filter_ = query.get("filter", {})
        if "classification" in filter_:
            require(
                filter_["classification"] in self.classifications,
                "unknown Entity Classification",
            )
        for label in filter_.get("labels") or []:
            require(
                label["classification"] in self.classifications,
                "unknown Label Classification",
            )
        projection = query["projection"]
        if projection["kind"] == "entity":
            item_domain = dict(kind="entity")
        elif "measure" in projection:
            require(
                projection["measure"] in self.measures, "unknown projection Measure"
            )
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

    def expression(self, node, seen=None):
        if seen is None:
            seen = set(self.identities)
        require(node["id"] not in seen, "duplicate Expression identity")
        seen.add(node["id"])
        kind = node["kind"]
        if kind == "quantity":
            import math

            require(
                math.isfinite(node["quantity"]["magnitude"]), "non-finite magnitude"
            )
            return dict(kind="quantity", units=node["quantity"]["units"])
        if kind == "boolean":
            return dict(kind=kind)
        if kind == "reference":
            require(node["target"] in self.domains, "unknown Value reference")
            return self.domains[node["target"]]
        if kind in ("binary", "unary"):
            args = [node["operand"]] if kind == "unary" else node["operands"]
            domains = [self.expression(arg, seen) for arg in args]
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
                all(
                    t["kind"] in ("number", "quantity", "measurement") for t in domains
                ),
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
            if all(self.numerical_units(t) == "dimensionless" for t in domains):
                return dict(kind="number")
            if kind == "unary" and self.numerical_units(domains[0]) is not None:
                return dict(kind="quantity", units=self.numerical_units(domains[0]))
            # Full unit inference is deferred. Arithmetic alone does not supply
            # a Measurement's domain meaning or a Measure identity.
            return dict(kind="quantity")
        if kind == "query":
            return self.query_domain(node["query"])
        if kind == "selection":
            selection = node["selection"]
            base = self.expression(selection["base"], seen)
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
                return result
            require(
                base["kind"] == "collection"
                and base.get("collection_kind") == "sequence",
                "this index fixture requires an ordered sequence",
            )
            index_domain = self.expression(selection["index"], seen)
            require(
                self.matches(index_domain, dict(kind="number")),
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
            require(call["function"] in self.functions, "unknown Function")
            function = self.functions[call["function"]]
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
                    actual = self.expression(bound[name], seen)
                    require(
                        self.matches(actual, parameter["domain"]),
                        f"argument domain mismatch: {name}",
                    )
            return function["result"]
        raise ContractError(f"unsupported expression kind: {kind}")
