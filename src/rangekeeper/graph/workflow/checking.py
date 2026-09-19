"""Structured comparisons distinguish unavailable results, fidelity and reconciliation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rangekeeper.graph import Assembly, Entity, Graph
from rangekeeper.graph.operation import _Failure
from rangekeeper.graph.workflow.ingestion import tabular

from ._declarations import fields, sequence, text
from .bindings import binding, condition, template, validate_binding, validate_condition
from .ingestion.predicates import equal
from .references import references


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Retains comparison operands, scope, missing contributors and graph targets
    so an agreement can be assessed beyond a summary count.
    """

    id: str
    group: str
    scope: str
    left: object
    right: object
    status: str
    explanation: str
    references: tuple[str, ...] = ()
    targets: tuple[str, ...] = ()
    known_subtotal: int | float | None = None
    missing: tuple[str, ...] = ()
    purpose: str = "comparison"
    category: str = "comparison"
    source: str = ""
    left_members: tuple[str, ...] = ()
    right_members: tuple[str, ...] = ()


_GRAPH_FILTERS = {"classification", "member_of", "codes"}
_OPERANDS = {
    "value": ({"value"}, set()),
    "column": ({"binding"}, set()),
    "evidence": ({"binding"}, set()),
    "table_keys": ({"table", "column"}, {"where", "evidence_columns"}),
    "table_count": ({"table", "column"}, {"where", "evidence_columns"}),
    "table_total": ({"table", "column"}, {"where", "evidence_columns"}),
    "graph_keys": (set(), _GRAPH_FILTERS | {"measure", "binding"}),
    "graph_count": (set(), _GRAPH_FILTERS | {"measure", "binding"}),
    "graph_total": ({"measure"}, _GRAPH_FILTERS | {"units", "require_complete"}),
    "graph_measurement": (
        {"identity_kind", "key", "measure"},
        {"units", "missing_target"},
    ),
    "membership_keys": ({"identity_kind", "key"}, {"classification"}),
}


def validate_checks(spec, seen):
    fields(
        spec,
        {"comparisons", "invariants", "deferred", "notes", "source_checks"},
        {"comparisons"},
    )
    ids = []
    for c in sequence(spec["comparisons"]):
        fields(
            c,
            {
                "id",
                "group",
                "scope",
                "each",
                "scope_column",
                "left",
                "right",
                "tolerance",
                "explanation",
                "purpose",
                "category",
                "evidence",
                "when",
                "source",
                "report",
                "report_when",
            },
            {"id", "group", "scope", "left", "right"},
        )
        ids.append(c["id"])
        if c.get("report", "values") not in {"values", "counts"}:
            raise ValueError("Unknown report mode")
        if c.get("report_when", "always") not in {"always", "difference"}:
            raise ValueError("Unknown check emission policy")
        if "each" in c and seen.get(c["each"]) != "table":
            raise ValueError("Unknown check iteration Evidence")
        validate_condition(c.get("when"), seen)
        for b in c.get("evidence", ()):
            validate_binding(b, seen)
        if (
            type(c.get("tolerance", 0)) not in (int, float)
            or not math.isfinite(c.get("tolerance", 0))
            or c.get("tolerance", 0) < 0
        ):
            raise ValueError("Invalid comparison tolerance")
        for op in (c["left"], c["right"]):
            fields(op, set(op), {"kind"})
            kind = op["kind"]
            if type(kind) is not str or kind not in _OPERANDS:
                raise ValueError("Unknown check operand")
            required, optional = _OPERANDS[kind]
            fields(op, {"kind"} | required | optional, {"kind"} | required)
            for key in {
                "table",
                "column",
                "identity_kind",
                "classification",
                "measure",
                "units",
            } & set(op):
                text(op[key])
            if "require_complete" in op and type(op["require_complete"]) is not bool:
                raise TypeError("require_complete must be boolean")
            if op.get("missing_target", "omit") not in {"omit", "owner"}:
                raise ValueError("Unknown missing_target policy")
            for col in sequence(op.get("evidence_columns", ())):
                text(col)
            if "table" in op and seen.get(op["table"]) != "table":
                raise ValueError("Unknown operand Evidence")
            if "binding" in op:
                validate_binding(op["binding"], seen)
            if "key" in op:
                validate_binding(op["key"], seen)
            if "where" in op:
                fields(op["where"], {"column", "equals", "binding"}, {"column"})
                if ("equals" in op["where"]) == ("binding" in op["where"]):
                    raise ValueError("where requires equals or binding")
                if "binding" in op["where"]:
                    validate_binding(op["where"]["binding"], seen)
            if "codes" in op:
                fields(
                    op["codes"],
                    {"table", "column", "evidence_columns"},
                    {"table", "column"},
                )
                if seen.get(op["codes"]["table"]) != "table":
                    raise ValueError("Unknown eligibility Evidence")
            if "member_of" in op:
                fields(op["member_of"], {"kind", "key"}, {"kind", "key"})
                validate_binding(op["member_of"]["key"], seen)
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate check IDs")
    if set(spec.get("invariants", ())) - {
        "fact_coverage",
        "membership",
        "defined_kinds",
    }:
        raise ValueError("Unknown graph invariant")


def evaluate(
    spec: Mapping[str, Any],
    graph: Graph,
    by_key: Mapping[tuple[str, str], Entity | Assembly],
    outputs: Mapping[str, Any],
) -> tuple[CheckResult, ...]:
    """Keeps source fidelity, independent reconciliation and unavailable totals
    distinguishable. Exact member comparisons prevent equal counts from
    concealing different populations.
    """

    def codes_of(entities):
        codes = [e.code for e in entities]
        if any(code is None for code in codes):
            raise _Failure(
                "missing_business_key", "Identity comparison requires object codes"
            )
        return tuple(sorted(code for code in codes if code is not None))

    results = []

    def operand(op, row, table):
        kind = op["kind"]
        claims = []
        targets = []
        missing = []
        known = None
        if kind == "value":
            return op["value"], claims, targets, known, missing
        if kind in {"column", "evidence"}:
            value, parents = binding(op["binding"], row, table, outputs)
            return value, parents, targets, known, missing
        if kind.startswith("table_"):
            selected = outputs[op["table"]]
            rows = list(selected.data.rows)
            if "where" in op:
                w = op["where"]
                expected = (
                    binding(w["binding"], row, table, outputs)[0]
                    if "binding" in w
                    else w["equals"]
                )
                rows = [r for r in rows if equal(r.values[w["column"]], expected)]
            values = []
            for r in rows:
                c = tabular.claim(selected, r.id, op["column"])
                claims.extend(
                    tabular.claim(selected, r.id, col)
                    for col in op.get("evidence_columns", (op["column"],))
                )
                values.append(c.value)
                if c.value is None:
                    missing.append(str(r.id))
            if kind == "table_count":
                value = len(rows)
            elif kind == "table_keys":
                value = tuple(sorted(values, key=repr)) if not missing else None
            else:
                available = [v for v in values if v is not None]
                known = sum(available) if available else None
                value = known if rows and not missing else None
            return value, claims, targets, known, missing
        if kind == "graph_measurement":
            key, _upstream = binding(op["key"], row, table, outputs)
            obj = by_key.get((op["identity_kind"], key))
            item = obj.measurements.get(op["measure"]) if obj is not None else None
            value = (
                item.quantity.to(op.get("units", str(item.quantity.units))).magnitude
                if item
                else None
            )
            return (
                value,
                claims,
                (
                    []
                    if obj is None
                    or (item is None and op.get("missing_target", "omit") == "omit")
                    else [str(item.id if item else obj.id)]
                ),
                known,
                missing,
            )
        if kind == "membership_keys":
            key, _upstream = binding(op["key"], row, table, outputs)
            obj = by_key.get((op["identity_kind"], key))
            if obj is None:
                return (), claims, targets, known, missing
            if not isinstance(obj, Assembly):
                raise _Failure(
                    "invalid_membership_target",
                    "Membership comparison requires an Assembly",
                )
            targets = [str(obj.id)]
            members = [graph.entity(uid) for uid in obj.entity_ids]
            if "classification" in op:
                members = [
                    x
                    for x in members
                    if x.classification
                    and x.classification.code == op["classification"]
                ]
            return (
                codes_of(members),
                claims,
                targets,
                known,
                missing,
            )
        entities = list(graph.entities)
        if "classification" in op:
            entities = [
                x
                for x in entities
                if x.classification and x.classification.code == op["classification"]
            ]
        if "member_of" in op:
            m = op["member_of"]
            key, _ = binding(m["key"], row, table, outputs)
            parent = by_key.get((m["kind"], key))
            if parent is not None and not isinstance(parent, Assembly):
                raise _Failure(
                    "invalid_membership_target",
                    "Membership filter requires an Assembly",
                )
            entities = [
                x for x in entities if parent is not None and x.id in parent.entity_ids
            ]
        if "measure" in op and kind in {"graph_keys", "graph_count"}:
            expected = (
                binding(op["binding"], row, table, outputs)[0]
                if "binding" in op
                else None
            )
            entities = [
                x
                for x in entities
                if op["measure"] in x.measurements
                and (
                    expected is None
                    or x.measurements[op["measure"]].quantity.magnitude == expected
                )
            ]
        if "codes" in op:
            codes = op["codes"]
            evidence = outputs[codes["table"]]
            wanted = {r.values[codes["column"]] for r in evidence.data.rows}
            entities = [e for e in entities if e.code in wanted]
            for r in evidence.data.rows:
                claims.extend(
                    tabular.claim(evidence, r.id, c)
                    for c in codes.get("evidence_columns", ())
                )
            missing.extend(str(k) for k in wanted - {e.code for e in entities})
        targets = [str(e.id) for e in entities]
        if kind == "graph_count":
            value = len(entities)
        elif kind == "graph_keys":
            value = codes_of(entities)
        else:
            values = []
            targets = []
            for e in entities:
                m = e.measurements.get(op["measure"])
                if m is None:
                    missing.append(e.code)
                else:
                    values.append(
                        m.quantity.to(op.get("units", str(m.quantity.units))).magnitude
                    )
                    targets.append(str(m.id))
            known = sum(values) if values else None
            value = (
                known
                if entities and (not missing or not op.get("require_complete", True))
                else None
            )
        return value, claims, targets, known, missing

    for c in spec["comparisons"]:
        table = outputs[c["each"]] if "each" in c else None
        for row in table.data.rows if table is not None else (None,):
            if not condition(c.get("when"), row, table, outputs):
                continue
            context = {
                "key": str(row.values[c["scope_column"]])
                if row is not None and "scope_column" in c
                else ""
            }
            left, lc, lt, known, missing = operand(c["left"], row, table)
            right, rc, rt, _, _ = operand(c["right"], row, table)
            if left is None or right is None:
                status = "unavailable"
            elif type(left) in (int, float) and type(right) in (int, float):
                status = (
                    "agree"
                    if math.isclose(
                        left, right, rel_tol=0, abs_tol=c.get("tolerance", 0)
                    )
                    else "difference"
                )
            else:
                status = "agree" if left == right else "difference"
            if c.get("report_when") == "difference" and status != "difference":
                continue
            members_left = (
                tuple(left) if c.get("report") == "counts" and left is not None else ()
            )
            members_right = (
                tuple(right)
                if c.get("report") == "counts" and right is not None
                else ()
            )
            if c.get("report") == "counts":
                left = None if left is None else len(left)
                right = None if right is None else len(right)
            extra = [
                claim
                for b in c.get("evidence", ())
                for claim in binding(b, row, table, outputs)[1]
            ]
            results.append(
                CheckResult(
                    id=c["id"] + (":" + str(row.id) if row else ""),
                    group=c["group"],
                    scope=template(c["scope"], context),
                    left=left,
                    right=right,
                    status=status,
                    explanation=c.get(
                        "explanation",
                        "Compared the declared scopes; missing evidence remains unavailable.",
                    ),
                    references=references((*lc, *rc, *extra)),
                    targets=tuple(dict.fromkeys((*lt, *rt))),
                    known_subtotal=known,
                    missing=tuple(missing),
                    purpose=c.get("purpose", "comparison"),
                    category=c.get("category", "comparison"),
                    source=c.get("source", ""),
                    left_members=members_left,
                    right_members=members_right,
                )
            )
    targets = {f.target.id for f in graph.provenance.facts}
    for rule in spec.get("invariants", ()):
        if rule == "fact_coverage":
            expected = {x.id for x in (*graph.entities, *graph.relationships)}
            expected.update(
                x.id
                for e in graph.entities
                for col in (e.features, e.labels, e.measurements)
                for x in col.values()
            )
            ok = expected == targets
        elif rule == "membership":
            ok = all(
                e.entity_ids
                == frozenset(
                    r.target_id
                    for r in graph.relationships
                    if r.id in e.relationship_ids
                )
                for e in graph.entities
                if isinstance(e, Assembly)
            )
        else:
            ok = all(
                x.classification is not None
                for x in (*graph.entities, *graph.relationships)
            )
        results.append(
            CheckResult(
                rule,
                "Invariants",
                rule,
                ok,
                True,
                "agree" if ok else "difference",
                "Graph structural invariant",
                purpose="invariant",
                category="invariant",
            )
        )
    return tuple(results)
