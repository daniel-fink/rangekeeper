"""Structured comparisons distinguish unavailable results, fidelity and reconciliation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any

from rangekeeper.model import Assembly, Entity, Model
from rangekeeper.graph import View
from rangekeeper.operation import _Failure
from rangekeeper._encoding import encode

from ._declarations import fields, sequence, text
from ._operands import OperandResult, operand
from .bindings import (
    binding,
    condition,
    require_columns,
    template,
    validate_binding,
    validate_condition,
)
from .references import references


@unique
class CheckStatus(Enum):
    AGREE = "agree"
    DIFFERENCE = "difference"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Two complete operand sides and one comparison decision."""

    id: str
    group: str
    scope: str
    left: OperandResult
    right: OperandResult
    status: CheckStatus
    explanation: str
    references: tuple[str, ...] = ()
    purpose: str = "comparison"
    category: str = "comparison"
    source: str = ""
    report_counts: bool = False

    def __post_init__(self):
        if not isinstance(self.left, OperandResult) or not isinstance(
            self.right, OperandResult
        ):
            raise TypeError("comparison sides must be OperandResult")
        if not isinstance(self.status, CheckStatus):
            raise TypeError("status must be CheckStatus")
        if type(self.report_counts) is not bool:
            raise TypeError("report_counts must be bool")

    @property
    def targets(self):
        return tuple(dict.fromkeys((*self.left.targets, *self.right.targets)))

    def display_value(self, side):
        value = getattr(self, side).value
        return len(value) if self.report_counts and value is not None else value

    def to_mapping(self):
        def side(item):
            return {
                "value": item.value,
                "claims": tuple(str(c.id) for c in item.claims),
                "references": references(item.claims),
                "targets": item.targets,
                "known_subtotal": item.known_subtotal,
                "missing": item.missing,
            }

        return {
            "id": self.id,
            "group": self.group,
            "scope": self.scope,
            "left": side(self.left),
            "right": side(self.right),
            "status": self.status.value,
            "explanation": self.explanation,
            "references": self.references,
            "purpose": self.purpose,
            "category": self.category,
            "source": self.source,
            "report_counts": self.report_counts,
        }


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
    view = View(model)
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
            left_result = operand(
                c["left"], row, table, model, by_key, outputs, view=view
            )
            right_result = operand(
                c["right"], row, table, model, by_key, outputs, view=view
            )
            left, right = left_result.value, right_result.value
            if left is None or right is None:
                status = CheckStatus.UNAVAILABLE
            elif (
                isinstance(left, (int, float))
                and not isinstance(left, bool)
                and isinstance(right, (int, float))
                and not isinstance(right, bool)
            ):
                status = (
                    CheckStatus.AGREE
                    if math.isclose(
                        left, right, rel_tol=0, abs_tol=c.get("tolerance", 0)
                    )
                    else CheckStatus.DIFFERENCE
                )
            else:
                status = (
                    CheckStatus.AGREE
                    if encode(left) == encode(right)
                    else CheckStatus.DIFFERENCE
                )
            if (
                c.get("report_when") == "difference"
                and status is not CheckStatus.DIFFERENCE
            ):
                continue
            if c.get("report") == "counts" and any(
                value is not None and not isinstance(value, tuple)
                for value in (left, right)
            ):
                raise _Failure(
                    "invalid_count_report", "Count reports require key collections"
                )
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
                    left=left_result,
                    right=right_result,
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
                    purpose=c.get("purpose", "comparison"),
                    category=c.get("category", "comparison"),
                    source=c.get("source", ""),
                    report_counts=c.get("report") == "counts",
                )
            )
    results.extend(_invariants(spec, model, view))
    return tuple(results)


def _invariants(spec, model, view):
    results = []
    targets = (
        {f.target for f in model.provenance.facts or ()} if model.provenance else set()
    )
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
                OperandResult(ok),
                OperandResult(True),
                CheckStatus.AGREE if ok else CheckStatus.DIFFERENCE,
                "Model structural invariant",
                purpose="invariant",
                category="invariant",
            )
        )
    return tuple(results)
