"""Validate reviewed model declarations before source execution."""

from rangekeeper.measure import AggregationRule, Index, QuantityKind

from ._declarations import fields, sequence, text
from .bindings import template, validate_binding, validate_condition


def validate_measurements(values, seen, decision_ids, measures):
    """Validate bindings equally at their definition and their point of use.

    Sharing must not let an unused malformed policy escape review, or let a
    repeated measure silently overwrite an earlier declaration.
    """
    codes = set()
    for attr in sequence(values):
        fields(
            attr,
            {"measure", "binding", "when", "decisions", "evidence", "on_unavailable"},
            {"measure", "binding"},
        )
        code = text(attr["measure"])
        if code not in measures:
            raise ValueError(f"Unknown measure: {code}")
        if code in codes:
            raise ValueError(f"Duplicate measurement declaration: {code}")
        codes.add(code)
        if set(sequence(attr.get("decisions", ()))) - set(decision_ids):
            raise ValueError("Unknown reviewed decision")
        for b in sequence(attr.get("evidence", ())):
            validate_binding(b, seen)
        validate_binding(attr["binding"], seen)
        validate_condition(attr.get("when"), seen)
        if "on_unavailable" in attr:
            missing = fields(
                attr["on_unavailable"], {"feature", "binding", "topic", "explanation"}
            )
            if "binding" in missing:
                validate_binding(missing["binding"], seen)
            for key in ("feature", "topic", "explanation"):
                if key in missing:
                    text(missing[key])


def validate_model(model, seen, decisions):
    fields(
        model,
        {
            "taxonomy",
            "classifications",
            "measures",
            "templates",
            "objects",
            "relationships",
            "memberships",
            "acyclic",
            "findings",
            "deferred",
            "aggregates",
        },
        {
            "taxonomy",
            "classifications",
            "measures",
            "templates",
            "objects",
            "relationships",
            "memberships",
        },
    )
    fields(decisions, {"decisions", "mappings"}, {"decisions"})
    decision_ids = []
    for d in sequence(decisions["decisions"]):
        fields(
            d,
            {
                "id",
                "status",
                "category",
                "text",
                "source",
                "date",
                "mappings",
                "references",
            },
            {"id", "status", "text", "source", "date"},
        )
        text(d["id"])
        decision_ids.append(d["id"])
    if len(set(decision_ids)) != len(decision_ids):
        raise ValueError("Duplicate decision identity")
    fields(model["taxonomy"], {"code", "name", "definition"}, {"code", "name"})
    classes = []
    for c in sequence(model["classifications"]):
        fields(c, {"code", "name", "definition", "parent"}, {"code", "name"})
        text(c["code"])
        classes.append(c["code"])
    if len(set(classes)) != len(classes):
        raise ValueError("Duplicate classification")
    for c in model["classifications"]:
        if c.get("parent") is not None and c["parent"] not in classes:
            raise ValueError("Unknown classification parent")
    measures = []
    for m in sequence(model["measures"]):
        fields(
            m,
            {"code", "name", "definition", "units", "quantity_kind", "aggregation"},
            {"code", "name", "units", "quantity_kind", "aggregation"},
        )
        QuantityKind[m["quantity_kind"]]
        AggregationRule[m["aggregation"]]
        Index.registry.Unit(m["units"])
        measures.append(m["code"])
    if len(set(measures)) != len(measures):
        raise ValueError("Duplicate measure")

    def finding(f):
        fields(
            f,
            {"topic", "subject", "explanation", "references", "when", "evidence"},
            {"topic", "explanation"},
        )
        validate_condition(f.get("when"), seen)
        for b in f.get("evidence", ()):
            validate_binding(b, seen)

    for f in model.get("findings", ()):
        finding(f)
        if "subject" not in f:
            raise ValueError("A global finding requires subject")
    for d in model.get("deferred", ()):
        fields(d, {"table", "column", "kind"}, {"table", "column", "kind"})
        if seen.get(d["table"]) != "table":
            raise ValueError("Unknown supporting Evidence")
    for a in model.get("aggregates", ()):
        fields(
            a,
            {
                "id",
                "root",
                "relationship",
                "contributor_classification",
                "measure",
                "require_measurement",
                "status",
                "rationale",
                "decisions",
            },
            {"id", "status", "rationale"},
        )
        if a["status"] != "deferred":
            raise ValueError(
                "Enabled aggregates must be explicit check operands; model aggregate policies are deferred scope"
            )
        if set(a.get("decisions", ())) - set(decision_ids):
            raise ValueError("Unknown aggregate decision")

    def policy(p):
        if set(p.get("decisions", ())) - set(decision_ids):
            raise ValueError("Unknown reviewed decision")
        for b in p.get("evidence", ()):
            validate_binding(b, seen)

    def attributes(p):
        validate_measurements(p.get("measurements", ()), seen, decision_ids, measures)
        for kind, required, allowed in [
            (
                "features",
                {"name", "binding"},
                {
                    "name",
                    "binding",
                    "when",
                    "decisions",
                    "evidence",
                    "omit_unavailable",
                },
            ),
            (
                "labels",
                {"name", "bindings"},
                {"name", "bindings", "when", "decisions", "evidence"},
            ),
        ]:
            for attr in p.get(kind, ()):
                fields(attr, allowed, required)
                policy(attr)
                validate_condition(attr.get("when"), seen)
                if kind == "labels":
                    for b in sequence(attr["bindings"]):
                        validate_binding(b, seen)
                else:
                    validate_binding(attr["binding"], seen)
                if "on_unavailable" in attr:
                    fields(
                        attr["on_unavailable"],
                        {"feature", "binding", "topic", "explanation"},
                    )
                    if "binding" in attr["on_unavailable"]:
                        validate_binding(attr["on_unavailable"]["binding"], seen)

    for p in (*sequence(model["templates"]), *sequence(model["objects"])):
        allowed = {
            "id",
            "kind",
            "classification",
            "name",
            "code",
            "identity_kind",
            "key",
            "table",
            "features",
            "measurements",
            "labels",
            "evidence",
            "decisions",
            "when",
            "findings",
        }
        fields(
            p, allowed, {"id", "kind", "classification", "name", "identity_kind", "key"}
        )
        if p["kind"] not in {"entity", "assembly"}:
            raise ValueError("Unsupported object kind")
        if p["classification"] not in classes:
            raise ValueError("Unknown classification")
        if "table" in p and seen.get(p["table"]) != "table":
            raise ValueError("Unknown template Evidence")
        validate_binding(p["key"], seen)
        if "code" in p:
            validate_binding(p["code"], seen)
        if "table" not in p and "value" not in p["key"]:
            raise ValueError("Explicit objects require a declared literal business key")
        policy(p)
        for f in p.get("findings", ()):
            finding(f)
        template(p["name"], {"key": "key", "id": "id"})
        attributes(p)
        validate_condition(p.get("when"), seen)
    for rel in sequence(model["relationships"]):
        fields(
            rel,
            {
                "id",
                "table",
                "source",
                "target",
                "identity_kind",
                "key",
                "classification",
                "decisions",
                "evidence",
                "when",
                "unmatched",
            },
            {"id", "source", "target", "identity_kind", "key", "classification"},
        )
        if rel["classification"] not in classes:
            raise ValueError("Unknown relationship classification")
        if "table" in rel and seen.get(rel["table"]) != "table":
            raise ValueError("Unknown relationship Evidence")
        for end in ("source", "target"):
            fields(rel[end], {"kind", "key"}, {"kind", "key"})
            validate_binding(rel[end]["key"], seen)
        template(
            rel["key"],
            {
                "source_key": "key",
                "target_key": "key",
                "source_id": "id",
                "target_id": "id",
            },
        )
        policy(rel)
        validate_condition(rel.get("when"), seen)
        if rel.get("unmatched", "error") not in {"error", "finding"}:
            raise ValueError("unmatched must be error or finding")
    if set(model["memberships"]) - set(classes):
        raise ValueError("Unknown membership classification")
    if type(model.get("acyclic", True)) is not bool:
        raise TypeError("acyclic must be boolean")
