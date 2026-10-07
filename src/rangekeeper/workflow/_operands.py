"""Evaluate declared comparison operands without losing either side's evidence."""

from dataclasses import dataclass
from typing import Any

from rangekeeper.model import Assembly, Classification
from rangekeeper.graph import View
from rangekeeper.graph.selection import _recorded_quantity, _local_value
from rangekeeper.graph.reduction import _collect_quantities
from rangekeeper.model.characteristics import value as local_value
from rangekeeper.units import default_units
from rangekeeper.operation import _Failure
from rangekeeper.evidence import Claim

from .bindings import binding, require_columns
from rangekeeper.evidence import tabular
from rangekeeper.evidence.predicates import equal


@dataclass(frozen=True, slots=True)
class OperandResult:
    """Named support and completeness information travels with each operand value."""

    value: object
    claims: tuple[Claim, ...] = ()
    targets: tuple[str, ...] = ()
    known_subtotal: int | float | None = None
    missing: tuple[str, ...] = ()

    def __post_init__(self):
        for field in ("claims", "targets", "missing"):
            object.__setattr__(self, field, tuple(getattr(self, field)))


def codes_of(entities):
    codes = [e.code for e in entities]
    if any(code is None for code in codes):
        raise _Failure(
            "missing_business_key", "Identity comparison requires object codes"
        )
    return tuple(sorted(code for code in codes if code is not None))


def table_operand(op, row, table, outputs) -> OperandResult:
    kind = op["kind"]
    claims: list[Claim] = []
    targets: list[str] = []
    missing: list[str] = []
    known: int | float | None = None
    value: Any
    selected = outputs[op["table"]]
    require_columns(selected, (op["column"], *op.get("evidence_columns", ())))
    rows = list(selected.data.rows)
    if "where" in op:
        w = op["where"]
        require_columns(selected, (w["column"],))
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
        value = known if rows and (not missing) else None
    return OperandResult(value, tuple(claims), tuple(targets), known, tuple(missing))


def model_operand(op, row, table, model, by_key, outputs, *, view) -> OperandResult:
    kind = op["kind"]
    claims: list[Claim] = []
    targets: list[str] = []
    missing: list[str] = []
    known: int | float | None = None
    value: Any
    entities = list(view.entities)
    if "classification" in op:
        entities = [
            x
            for x in entities
            if x.classification
            and model._index.get(x.classification, Classification).code
            == op["classification"]
        ]
    if "member_of" in op:
        m = op["member_of"]
        key, _ = binding(m["key"], row, table, outputs)
        parent = by_key.get((m["kind"], key))
        if parent is not None:
            parent = model.entity(parent.id)  # Resolve against this pinned revision.
        if parent is not None and (not isinstance(parent, Assembly)):
            raise _Failure(
                "invalid_membership_target", "Membership filter requires an Assembly"
            )
        entities = [
            x
            for x in entities
            if parent is not None and x.id in (parent.entities or ())
        ]
    if "value_key" in op and kind in {"model_keys", "model_count"}:
        expected = (
            binding(op["binding"], row, table, outputs)[0] if "binding" in op else None
        )
        entities = [
            x
            for x in entities
            if (item := local_value(x.characteristics, op["value_key"])) is not None
            and (
                expected is None
                or item.quantity is not None
                and item.quantity.magnitude == expected
            )
        ]
    if "codes" in op:
        codes = op["codes"]
        evidence = outputs[codes["table"]]
        require_columns(evidence, (codes["column"], *codes.get("evidence_columns", ())))
        wanted = {r.values[codes["column"]] for r in evidence.data.rows}
        entities = [e for e in entities if e.code in wanted]
        for r in evidence.data.rows:
            claims.extend(
                tabular.claim(evidence, r.id, c)
                for c in codes.get("evidence_columns", ())
            )
        missing.extend(str(k) for k in wanted - {e.code for e in entities})
    targets = [str(e.id) for e in entities]
    if kind == "model_count":
        value = len(entities)
    elif kind == "model_keys":
        value = codes_of(entities)
    else:
        population = _collect_quantities(
            ((e, _local_value(e, op["value_key"], None)) for e in entities),
            op["units"],
            default_units,
        )
        missing.extend(model.entity(uid).code for uid in population.coverage.missing)
        targets = [
            str(population.value_ids[uid]) for uid in population.coverage.measured
        ]
        known = (
            sum(q.magnitude for q in population.quantities)
            if population.quantities
            else None
        )
        value = (
            known
            if entities and (not missing or not op.get("require_complete", True))
            else None
        )
    return OperandResult(value, tuple(claims), tuple(targets), known, tuple(missing))


def operand(op, row, table, model, by_key, outputs, *, view=None) -> OperandResult:
    kind = op["kind"]
    claims: list[Claim] = []
    targets: list[str] = []
    missing: list[str] = []
    known = None
    if kind == "value":
        return OperandResult(op["value"])
    if kind in {"column", "evidence"}:
        value, parents = binding(op["binding"], row, table, outputs)
        return OperandResult(value, claims=tuple(parents))
    if kind.startswith("table_"):
        return table_operand(op, row, table, outputs)
    if kind == "model_value":
        key, _upstream = binding(op["key"], row, table, outputs)
        obj = by_key.get((op["identity_kind"], key))
        if obj is not None:
            obj = model.entity(
                obj.id
            )  # Business-key indexes carry identity, not state.
        item = (
            local_value(obj.characteristics, op["value_key"])
            if obj is not None
            else None
        )
        value = (
            _recorded_quantity(item, op["units"], default_units).magnitude
            if item is not None and item.quantity is not None
            else None
        )
        return OperandResult(
            value,
            tuple(claims),
            tuple(
                []
                if obj is None
                or (item is None and op.get("missing_target", "omit") == "omit")
                else [str(item.id if item else obj.id)]
            ),
            known,
            tuple(missing),
        )
    if kind == "membership_keys":
        key, _upstream = binding(op["key"], row, table, outputs)
        obj = by_key.get((op["identity_kind"], key))
        if obj is not None:
            obj = model.entity(
                obj.id
            )  # Business-key indexes carry identity, not state.
        if obj is None:
            return OperandResult(
                (), tuple(claims), tuple(targets), known, tuple(missing)
            )
        if not isinstance(obj, Assembly):
            raise _Failure(
                "invalid_membership_target",
                "Membership comparison requires an Assembly",
            )
        targets = [str(obj.id)]
        members = [model.entity(uid) for uid in (obj.entities or ())]
        if "classification" in op:
            members = [
                x
                for x in members
                if x.classification
                and model._index.get(x.classification, Classification).code
                == op["classification"]
            ]
        return OperandResult(
            codes_of(members), tuple(claims), tuple(targets), known, tuple(missing)
        )
    return model_operand(
        op,
        row,
        table,
        model,
        by_key,
        outputs,
        view=view if view is not None else View(model),
    )
