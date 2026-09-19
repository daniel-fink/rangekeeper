"""Compose native RK graphs from declared business keys and Evidence bindings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from rangekeeper.graph import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Feature,
    Graph,
    Label,
    Measurement,
    Relationship,
    Taxonomy,
)
from rangekeeper.graph.operation import Operation, _Failure
from rangekeeper.graph.operation import fingerprint as operation_fingerprint
from rangekeeper.graph.provenance import (
    AssemblyState,
    Claim,
    EntityState,
    Fact,
    Provenance,
    RelationshipState,
)
from rangekeeper.measure import AggregationRule, Index, Measure, QuantityKind

from ._declarations import fields, sequence, text
from .bindings import binding, condition, template, validate_binding, validate_condition
from .references import references


@dataclass(frozen=True, slots=True)
class Finding:
    """Retains a construction limitation or provisional interpretation that may
    have no single input cell or numeric comparison to attach to.
    """

    topic: str
    subject: str
    explanation: str
    references: tuple[str, ...] = ()


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
                "measurements",
                {"measure", "binding"},
                {
                    "measure",
                    "binding",
                    "when",
                    "decisions",
                    "evidence",
                    "on_unavailable",
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
                if kind == "measurements" and attr["measure"] not in measures:
                    raise ValueError("Unknown measure")
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


def compose(
    model: Mapping[str, Any],
    outputs: Mapping[str, Any],
    settings: Claim[str],
    decisions: Mapping[str, Claim[str]],
    operation: Operation,
    *,
    namespace: str,
) -> tuple[Graph, tuple[Finding, ...], dict[tuple[str, str], Entity | Assembly]]:
    """Constructs actual RK objects and Facts rather than an intermediate project
    graph. Business-key identity survives changed measurements or source
    editions; membership follows explicitly selected relationships.
    Model declarations and named Evidence are usable without YAML or a runner.
    """
    identity_namespace = uuid5(NAMESPACE_URL, namespace)

    def identity(kind, key):
        return uuid5(identity_namespace, json.dumps([kind, key], ensure_ascii=False))

    classes = {}
    pending = list(model["classifications"])
    while pending:
        ready = [
            c for c in pending if c.get("parent") is None or c["parent"] in classes
        ]
        if not ready:
            raise ValueError("Classification hierarchy contains a cycle")
        for c in ready:
            classes[c["code"]] = Classification(
                id=identity("classification", c["code"]),
                code=c["code"],
                name=c["name"],
                definition=c.get("definition"),
                parent=classes.get(c.get("parent")),
            )
            pending.remove(c)
    taxonomy = Taxonomy(
        id=identity("taxonomy", model["taxonomy"]["code"]),
        classifications=tuple(classes.values()),
        **model["taxonomy"],
    )
    measures = {
        m["code"]: Measure(
            id=identity("measure", m["code"]),
            code=m["code"],
            name=m["name"],
            definition=m.get("definition"),
            units=Index.registry.Unit(m["units"]),
            quantity_kind=QuantityKind[m["quantity_kind"]],
            aggregation=AggregationRule[m["aggregation"]],
        )
        for m in model["measures"]
    }
    defs = Definitions(taxonomies=(taxonomy,), measures=tuple(measures.values()))
    objects = {}
    by_key = {}
    object_inputs = {}
    facts = []
    findings = []
    token = operation_fingerprint(operation)

    def parents(policy, row, table):
        sources = [
            c
            for b in policy.get("evidence", ())
            for c in binding(b, row, table, outputs)[1]
        ]
        sources += [decisions[d] for d in policy.get("decisions", ())]
        return tuple(sources)

    def attach(target, inputs):
        if isinstance(target, Assembly):
            value = AssemblyState.from_assembly(target)
        elif isinstance(target, Entity):
            value = EntityState.from_entity(target)
        elif isinstance(target, Relationship):
            value = RelationshipState.from_relationship(target)
        elif isinstance(target, Measurement):
            value = target.quantity
        elif isinstance(target, Label):
            value = target.classifications
        else:
            value = target.value
        sources = tuple({c.id: c for c in (*inputs, settings)}.values())
        claim = Claim.derived(
            value,
            from_claims=sources,
            method=operation.method,
            id=uuid5(identity_namespace, token + str(target.id)),
        )
        facts.append(Fact(target=target, claims=(claim,)))
        return claim

    def contexts(policy):
        table = outputs[policy["table"]] if "table" in policy else None
        return (
            [(r, table) for r in table.data.rows]
            if table is not None
            else [(None, None)]
        )

    for policy in (*model["templates"], *model["objects"]):
        for row, table in contexts(policy):
            if not condition(policy.get("when"), row, table, outputs):
                continue
            key, key_claims = binding(policy["key"], row, table, outputs)
            if type(key) is not str or not key:
                raise _Failure(
                    "unavailable_identity",
                    f"{policy['id']} requires a nonempty text business key",
                )
            address = (policy["identity_kind"], key)
            uid = identity(*address)
            if address in by_key or uid in objects:
                raise _Failure(
                    "duplicate_business_key", f"Duplicate business identity {address}"
                )
            ctx = {"key": key, "id": str(uid)}
            base = (*key_claims, *parents(policy, row, table))
            features = {}
            readings = {}
            labels = {}

            def feature(name, value, sources, features=features, uid=uid, base=base):
                if name in features:
                    raise _Failure(
                        "duplicate_characteristic", f"Duplicate feature {name}"
                    )
                item = Feature(
                    id=identity("feature", f"{uid}:{name}"), name=name, value=value
                )
                features[name] = item
                attach(item, (*sources, *base))

            for attr in policy.get("features", ()):
                if not condition(attr.get("when"), row, table, outputs):
                    continue
                value, sources = binding(attr["binding"], row, table, outputs)
                if value is None and attr.get("omit_unavailable", False):
                    continue
                feature(attr["name"], value, (*sources, *parents(attr, row, table)))
            for attr in policy.get("measurements", ()):
                if not condition(attr.get("when"), row, table, outputs):
                    continue
                value, sources = binding(attr["binding"], row, table, outputs)
                sources = (*sources, *parents(attr, row, table))
                code = attr["measure"]
                if value is None:
                    missing = attr.get("on_unavailable", {})
                    if missing:
                        findings.append(
                            Finding(
                                missing.get("topic", "Unavailable measurement"),
                                str(uid),
                                template(
                                    missing.get(
                                        "explanation",
                                        code + ": required evidence is unavailable",
                                    ),
                                    ctx,
                                ),
                                references(sources),
                            )
                        )
                        if "feature" in missing:
                            raw, rawclaims = binding(
                                missing.get("binding", attr["binding"]),
                                row,
                                table,
                                outputs,
                            )
                            feature(missing["feature"], raw, rawclaims)
                    continue
                if type(value) not in (int, float):
                    raise _Failure(
                        "invalid_measurement",
                        "Measurement bindings require interpreted numeric Evidence",
                    )
                if code in readings:
                    raise _Failure(
                        "duplicate_characteristic", f"Duplicate measurement {code}"
                    )
                measure = measures[code]
                if measure.quantity_kind is QuantityKind.COUNT and value != int(value):
                    raise _Failure(
                        "fractional_count", "Count measure requires an integer"
                    )
                item = Measurement(
                    id=identity("measurement", f"{uid}:{code}"),
                    measure=measure,
                    quantity=value * measure.units,
                )
                readings[code] = item
                attach(item, (*sources, *base))
            for attr in policy.get("labels", ()):
                if not condition(attr.get("when"), row, table, outputs):
                    continue
                codes = []
                sources = []
                for b in attr["bindings"]:
                    value, upstream = binding(b, row, table, outputs)
                    sources.extend(upstream)
                    if value is not None:
                        if value not in classes:
                            raise _Failure(
                                "unknown_classification",
                                f"Unknown label classification {value}",
                            )
                        codes.append(value)
                if codes:
                    name = attr["name"]
                    if name in labels:
                        raise _Failure(
                            "duplicate_characteristic", f"Duplicate label {name}"
                        )
                    item = Label(
                        id=identity("label", f"{uid}:{name}"),
                        key=name,
                        classifications=tuple(classes[c] for c in codes),
                    )
                    labels[name] = item
                    attach(item, (*sources, *parents(attr, row, table), *base))
            code, codeclaims = binding(
                policy.get("code", policy["key"]), row, table, outputs
            )
            obj = (Assembly if policy["kind"] == "assembly" else Entity)(
                id=uid,
                code=code,
                name=template(policy["name"], ctx),
                classification=classes[policy["classification"]],
                characteristics=Characteristics(
                    features=features, measurements=readings, labels=labels
                ),
            )
            objects[uid] = obj
            by_key[address] = obj
            object_inputs[uid] = (*base, *codeclaims)
            for f in policy.get("findings", ()):
                if condition(f.get("when"), row, table, outputs):
                    findings.append(
                        Finding(
                            f["topic"],
                            template(f.get("subject", "{id}"), ctx),
                            template(f["explanation"], ctx),
                            references(parents(f, row, table) or base),
                        )
                    )
    edges = []
    edge_claims = {}
    seen_edges = set()
    for policy in model["relationships"]:
        for row, table in contexts(policy):
            if not condition(policy.get("when"), row, table, outputs):
                continue
            source, sources = binding(policy["source"]["key"], row, table, outputs)
            target, targets = binding(policy["target"]["key"], row, table, outputs)
            left = by_key.get((policy["source"]["kind"], source))
            right = by_key.get((policy["target"]["kind"], target))
            if left is None or right is None:
                if policy.get("unmatched", "error") == "error":
                    raise _Failure(
                        "unmatched_relationship",
                        f"{policy['id']}: unresolved business key {source!r} -> {target!r}",
                    )
                findings.append(
                    Finding(
                        "Unmatched relationship",
                        str(target),
                        "No unambiguous target; object retained without this relationship.",
                        references((*sources, *targets)),
                    )
                )
                continue
            values = {
                "source_key": source,
                "target_key": target,
                "source_id": str(left.id),
                "target_id": str(right.id),
            }
            uid = identity(policy["identity_kind"], template(policy["key"], values))
            if uid in seen_edges:
                raise _Failure(
                    "duplicate_relationship", "Duplicate relationship identity"
                )
            seen_edges.add(uid)
            edge = Relationship(
                id=uid,
                source_id=left.id,
                target_id=right.id,
                classification=classes[policy["classification"]],
            )
            edges.append(edge)
            upstream = (
                *sources,
                *targets,
                *parents(policy, row, table),
                *object_inputs[left.id],
                *object_inputs[right.id],
            )
            edge_claims[uid] = attach(edge, upstream)
    if model.get("acyclic", True):
        import networkx as nx

        net = nx.DiGraph()
        net.add_edges_from(
            (e.source_id, e.target_id)
            for e in edges
            if e.classification.code in model["memberships"]
        )
        if not nx.is_directed_acyclic_graph(net):
            raise _Failure(
                "membership_cycle", "Selected membership relationships form a cycle"
            )
    for uid, obj in list(objects.items()):
        selected = [
            e
            for e in edges
            if e.source_id == uid and e.classification.code in model["memberships"]
        ]
        if selected and not isinstance(obj, Assembly):
            raise _Failure(
                "invalid_membership_owner",
                "Membership relationships must originate from an Assembly",
            )
        if isinstance(obj, Assembly):
            obj = replace(
                obj,
                entity_ids=frozenset(e.target_id for e in selected),
                relationship_ids=frozenset(e.id for e in selected),
            )
            objects[uid] = obj
        attach(obj, (*object_inputs[uid], *(edge_claims[e.id] for e in selected)))
    for f in model.get("findings", ()):
        findings.append(Finding(**f))
    graph = Graph(
        definitions=defs,
        entities=tuple(objects.values()),
        relationships=tuple(edges),
        provenance=Provenance(facts=tuple(facts)),
    )
    return graph, tuple(findings), {key: objects[obj.id] for key, obj in by_key.items()}
