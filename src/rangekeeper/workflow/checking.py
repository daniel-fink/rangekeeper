"""Structured comparisons distinguish unavailable results, fidelity and reconciliation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rangekeeper.model import Assembly, Entity, Model
from rangekeeper.graph import View
from rangekeeper.operation import _Failure

from ._declarations import fields, sequence, text
from ._operands import operand
from .bindings import (
    binding,
    condition,
    require_columns,
    template,
    validate_binding,
    validate_condition,
)
from .references import references


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Retains comparison operands, scope, missing contributors and model targets
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
    # Legacy fields above retain their left-side meaning for existing consumers.
    left_missing: tuple[str, ...] = ()
    right_missing: tuple[str, ...] = ()
    left_known_subtotal: int | float | None = None
    right_known_subtotal: int | float | None = None


_MODEL_FILTERS = {"classification", "member_of", "codes"}
_OPERANDS = {
    "value": ({"value"}, set()),
    "column": ({"binding"}, set()),
    "evidence": ({"binding"}, set()),
    "table_keys": ({"table", "column"}, {"where", "evidence_columns"}),
    "table_count": ({"table", "column"}, {"where", "evidence_columns"}),
    "table_total": ({"table", "column"}, {"where", "evidence_columns"}),
    "model_keys": (set(), _MODEL_FILTERS | {"value_key", "binding"}),
    "model_count": (set(), _MODEL_FILTERS | {"value_key", "binding"}),
    "model_total": (
        {"value_key", "units"},
        _MODEL_FILTERS | {"units", "require_complete"},
    ),
    "model_value": (
        {"identity_kind", "key", "value_key", "units"},
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
                "value_key",
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
        raise ValueError("Unknown model invariant")


def evaluate(
    spec: Mapping[str, Any],
    model: Model,
    by_key: Mapping[tuple[str, str], Entity | Assembly],
    outputs: Mapping[str, Any],
) -> tuple[CheckResult, ...]:
    """Keeps source fidelity, independent reconciliation and unavailable totals
    distinguishable. Exact member comparisons prevent equal counts from
    concealing different populations.
    """

    results = []
    for c in spec["comparisons"]:
        table = outputs[c["each"]] if "each" in c else None
        if table is not None and "scope_column" in c:
            require_columns(table, (c["scope_column"],))
        for row in table.data.rows if table is not None else (None,):
            if not condition(c.get("when"), row, table, outputs):
                continue
            context = {
                "key": (
                    str(row.values[c["scope_column"]])
                    if row is not None and "scope_column" in c
                    else ""
                )
            }
            left_result = operand(c["left"], row, table, model, by_key, outputs)
            right_result = operand(c["right"], row, table, model, by_key, outputs)
            left, right = left_result.value, right_result.value
            if left is None or right is None:
                status = "unavailable"
            elif (
                isinstance(left, (int, float))
                and not isinstance(left, bool)
                and isinstance(right, (int, float))
                and not isinstance(right, bool)
            ):
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
            if c.get("report") == "counts" and any(
                value is not None and not isinstance(value, tuple)
                for value in (left, right)
            ):
                raise _Failure(
                    "invalid_count_report", "Count reports require key collections"
                )
            members_left = (
                left if c.get("report") == "counts" and isinstance(left, tuple) else ()
            )
            members_right = (
                right
                if c.get("report") == "counts" and isinstance(right, tuple)
                else ()
            )
            if c.get("report") == "counts":
                left = None if left is None else len(members_left)
                right = None if right is None else len(members_right)
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
                    references=references(
                        (
                            *left_result.claims,
                            *right_result.claims,
                            *extra,
                        )
                    ),
                    targets=tuple(
                        dict.fromkeys((*left_result.targets, *right_result.targets))
                    ),
                    known_subtotal=left_result.known_subtotal,
                    missing=left_result.missing,
                    left_missing=left_result.missing,
                    right_missing=right_result.missing,
                    left_known_subtotal=left_result.known_subtotal,
                    right_known_subtotal=right_result.known_subtotal,
                    purpose=c.get("purpose", "comparison"),
                    category=c.get("category", "comparison"),
                    source=c.get("source", ""),
                    left_members=members_left,
                    right_members=members_right,
                )
            )
    results.extend(_invariants(spec, model))
    return tuple(results)


def _invariants(spec, model):
    results = []
    targets = (
        {f.target for f in model.provenance.facts or ()} if model.provenance else set()
    )
    view = View(model)
    for rule in spec.get("invariants", ()):
        if rule == "fact_coverage":
            expected = {x.id for x in (*view.entities, *view.relationships)}
            expected.update(
                x.id
                for e in (*view.entities, *view.relationships)
                if e.characteristics
                for col in (
                    e.characteristics.labels or (),
                    e.characteristics.values or (),
                )
                for x in col
            )
            ok = expected == targets
        elif rule == "membership":
            ok = all(
                set(e.entities or ())
                == set(
                    r.target
                    for r in view.relationships
                    if r.id in (e.relationships or ())
                )
                for e in view.entities
                if isinstance(e, Assembly)
            )
        else:
            ok = all(
                x.classification is not None
                for x in (*view.entities, *view.relationships)
            )
        results.append(
            CheckResult(
                rule,
                "Invariants",
                rule,
                ok,
                True,
                "agree" if ok else "difference",
                "Model structural invariant",
                purpose="invariant",
                category="invariant",
            )
        )
    return tuple(results)
