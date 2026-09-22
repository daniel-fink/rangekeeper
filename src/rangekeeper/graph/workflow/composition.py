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

from ._model_validation import validate_measurements, validate_model
from .bindings import binding, condition, template
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


def compose(
    model: Mapping[str, Any],
    outputs: Mapping[str, Any],
    settings: Claim[str],
    decisions: Mapping[str, Claim[str]],
    operation: Operation,
    *,
    namespace: str,
) -> tuple[Graph, tuple[Finding, ...], dict[tuple[str, str], Entity | Assembly]]:
    """Build native RK objects in dependency order with stable business identities.

    Explicit phases retain canonical references without an intermediate graph
    model. This API can be used independently of YAML and workflow execution.
    """
    build = _Composition(model, outputs, settings, decisions, operation, namespace)
    build.add_objects()
    build.add_relationships()
    build.finalize_memberships()
    return build.finish()


def _definitions(model, identity):
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
    return defs, classes, measures


class _Composition:
    """Own the transient indexes needed to construct canonical graph instances.

    The phases share only this build's state. Facts for assemblies are attached
    after membership finalization, so every Fact targets the registered instance.
    """

    def __init__(self, model, outputs, settings, decisions, operation, namespace):
        self.model = model
        self.outputs = outputs
        self.settings = settings
        self.decisions = decisions
        self.operation = operation
        self.identity_namespace = uuid5(NAMESPACE_URL, namespace)
        self.definitions, self.classes, self.measures = _definitions(
            model, self.identity
        )
        self.objects = {}
        self.by_key = {}
        self.object_inputs = {}
        self.facts = []
        self.findings = []
        self.edges = []
        self.edge_claims = {}
        self.token = operation_fingerprint(operation)

    def identity(self, kind, key):
        return uuid5(
            self.identity_namespace, json.dumps([kind, key], ensure_ascii=False)
        )

    def parents(self, policy, row, table):
        sources = [
            c
            for b in policy.get("evidence", ())
            for c in binding(b, row, table, self.outputs)[1]
        ]
        sources += [self.decisions[d] for d in policy.get("decisions", ())]
        return tuple(sources)

    def attach(self, target, inputs):
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
        sources = tuple({c.id: c for c in (*inputs, self.settings)}.values())
        claim = Claim.derived(
            value,
            from_claims=sources,
            method=self.operation.method,
            id=uuid5(self.identity_namespace, self.token + str(target.id)),
        )
        self.facts.append(Fact(target=target, claims=(claim,)))
        return claim

    def contexts(self, policy):
        table = self.outputs[policy["table"]] if "table" in policy else None
        return (
            [(r, table) for r in table.data.rows]
            if table is not None
            else [(None, None)]
        )

    def add_objects(self):
        for policy in (*self.model["templates"], *self.model["objects"]):
            for row, table in self.contexts(policy):
                if condition(policy.get("when"), row, table, self.outputs):
                    self.add_object(policy, row, table)

    def add_object(self, policy, row, table):
        key, key_claims = binding(policy["key"], row, table, self.outputs)
        if type(key) is not str or not key:
            raise _Failure(
                "unavailable_identity",
                f"{policy['id']} requires a nonempty text business key",
            )
        address = (policy["identity_kind"], key)
        uid = self.identity(*address)
        if address in self.by_key or uid in self.objects:
            raise _Failure(
                "duplicate_business_key", f"Duplicate business identity {address}"
            )
        ctx = {"key": key, "id": str(uid)}
        base = (*key_claims, *self.parents(policy, row, table))
        characteristics = self.characteristics(policy, row, table, uid, base, ctx)
        code, codeclaims = binding(
            policy.get("code", policy["key"]), row, table, self.outputs
        )
        obj = (Assembly if policy["kind"] == "assembly" else Entity)(
            id=uid,
            code=code,
            name=template(policy["name"], ctx),
            classification=self.classes[policy["classification"]],
            characteristics=characteristics,
        )
        self.objects[uid] = obj
        self.by_key[address] = obj
        self.object_inputs[uid] = (*base, *codeclaims)
        for f in policy.get("findings", ()):
            if condition(f.get("when"), row, table, self.outputs):
                self.findings.append(
                    Finding(
                        f["topic"],
                        template(f.get("subject", "{id}"), ctx),
                        template(f["explanation"], ctx),
                        references(self.parents(f, row, table) or base),
                    )
                )

    def characteristics(self, policy, row, table, uid, base, ctx):
        features = {}
        readings = {}
        labels = {}

        def feature(name, value, sources):
            if name in features:
                raise _Failure("duplicate_characteristic", f"Duplicate feature {name}")
            item = Feature(
                id=self.identity("feature", f"{uid}:{name}"), name=name, value=value
            )
            features[name] = item
            self.attach(item, (*sources, *base))

        for attr in policy.get("features", ()):
            if not condition(attr.get("when"), row, table, self.outputs):
                continue
            value, sources = binding(attr["binding"], row, table, self.outputs)
            if value is None and attr.get("omit_unavailable", False):
                continue
            feature(attr["name"], value, (*sources, *self.parents(attr, row, table)))
        for attr in policy.get("measurements", ()):
            if not condition(attr.get("when"), row, table, self.outputs):
                continue
            value, sources = binding(attr["binding"], row, table, self.outputs)
            sources = (*sources, *self.parents(attr, row, table))
            code = attr["measure"]
            if value is None:
                missing = attr.get("on_unavailable", {})
                if missing:
                    self.findings.append(
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
                            self.outputs,
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
            measure = self.measures[code]
            if measure.quantity_kind is QuantityKind.COUNT and value != int(value):
                raise _Failure("fractional_count", "Count measure requires an integer")
            item = Measurement(
                id=self.identity("measurement", f"{uid}:{code}"),
                measure=measure,
                quantity=value * measure.units,
            )
            readings[code] = item
            self.attach(item, (*sources, *base))
        for attr in policy.get("labels", ()):
            if not condition(attr.get("when"), row, table, self.outputs):
                continue
            codes = []
            sources = []
            for b in attr["bindings"]:
                value, upstream = binding(b, row, table, self.outputs)
                sources.extend(upstream)
                if value is not None:
                    if value not in self.classes:
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
                    id=self.identity("label", f"{uid}:{name}"),
                    key=name,
                    classifications=tuple(self.classes[c] for c in codes),
                )
                labels[name] = item
                self.attach(item, (*sources, *self.parents(attr, row, table), *base))
        return Characteristics(features=features, measurements=readings, labels=labels)

    def add_relationships(self):
        seen_edges = set()
        for policy in self.model["relationships"]:
            for row, table in self.contexts(policy):
                if not condition(policy.get("when"), row, table, self.outputs):
                    continue
                source, sources = binding(
                    policy["source"]["key"], row, table, self.outputs
                )
                target, targets = binding(
                    policy["target"]["key"], row, table, self.outputs
                )
                left = self.by_key.get((policy["source"]["kind"], source))
                right = self.by_key.get((policy["target"]["kind"], target))
                if left is None or right is None:
                    if policy.get("unmatched", "error") == "error":
                        raise _Failure(
                            "unmatched_relationship",
                            f"{policy['id']}: unresolved business key {source!r} -> {target!r}",
                        )
                    self.findings.append(
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
                uid = self.identity(
                    policy["identity_kind"], template(policy["key"], values)
                )
                if uid in seen_edges:
                    raise _Failure(
                        "duplicate_relationship", "Duplicate relationship identity"
                    )
                seen_edges.add(uid)
                edge = Relationship(
                    id=uid,
                    source_id=left.id,
                    target_id=right.id,
                    classification=self.classes[policy["classification"]],
                )
                self.edges.append(edge)
                upstream = (
                    *sources,
                    *targets,
                    *self.parents(policy, row, table),
                    *self.object_inputs[left.id],
                    *self.object_inputs[right.id],
                )
                self.edge_claims[uid] = self.attach(edge, upstream)

    def finalize_memberships(self):
        if self.model.get("acyclic", True):
            import networkx as nx

            net = nx.DiGraph()
            net.add_edges_from(
                (e.source_id, e.target_id)
                for e in self.edges
                if e.classification.code in self.model["memberships"]
            )
            if not nx.is_directed_acyclic_graph(net):
                raise _Failure(
                    "membership_cycle", "Selected membership relationships form a cycle"
                )
        for uid, obj in list(self.objects.items()):
            selected = [
                e
                for e in self.edges
                if e.source_id == uid
                and e.classification.code in self.model["memberships"]
            ]
            if selected and (not isinstance(obj, Assembly)):
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
                self.objects[uid] = obj
            self.attach(
                obj,
                (*self.object_inputs[uid], *(self.edge_claims[e.id] for e in selected)),
            )

    def finish(self):
        for f in self.model.get("findings", ()):
            self.findings.append(Finding(**f))
        graph = Graph(
            definitions=self.definitions,
            entities=tuple(self.objects.values()),
            relationships=tuple(self.edges),
            provenance=Provenance(facts=tuple(self.facts)),
        )
        return (
            graph,
            tuple(self.findings),
            {key: self.objects[obj.id] for key, obj in self.by_key.items()},
        )


__all__ = ["validate_measurements", "validate_model"]
