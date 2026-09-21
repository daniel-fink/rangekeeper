"""Evaluate declared comparison operands without losing either side's evidence."""

from dataclasses import dataclass

from rangekeeper.graph import Assembly
from rangekeeper.graph.operation import _Failure
from rangekeeper.graph.provenance import Claim

from .bindings import binding, require_columns
from .ingestion import tabular
from .ingestion.predicates import equal


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
    claims, targets, missing, known = ([], [], [], None)
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


def graph_operand(op, row, table, graph, by_key, outputs) -> OperandResult:
    kind = op["kind"]
    claims, targets, missing, known = ([], [], [], None)
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
        if parent is not None and (not isinstance(parent, Assembly)):
            raise _Failure(
                "invalid_membership_target", "Membership filter requires an Assembly"
            )
        entities = [
            x for x in entities if parent is not None and x.id in parent.entity_ids
        ]
    if "measure" in op and kind in {"graph_keys", "graph_count"}:
        expected = (
            binding(op["binding"], row, table, outputs)[0] if "binding" in op else None
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
    return OperandResult(value, tuple(claims), tuple(targets), known, tuple(missing))


def operand(op, row, table, graph, by_key, outputs) -> OperandResult:
    kind = op["kind"]
    claims = []
    targets = []
    missing = []
    known = None
    if kind == "value":
        return OperandResult(op["value"])
    if kind in {"column", "evidence"}:
        value, parents = binding(op["binding"], row, table, outputs)
        return OperandResult(value, claims=tuple(parents))
    if kind.startswith("table_"):
        return table_operand(op, row, table, outputs)
    if kind == "graph_measurement":
        key, _upstream = binding(op["key"], row, table, outputs)
        obj = by_key.get((op["identity_kind"], key))
        item = obj.measurements.get(op["measure"]) if obj is not None else None
        value = (
            item.quantity.to(op.get("units", str(item.quantity.units))).magnitude
            if item
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
        members = [graph.entity(uid) for uid in obj.entity_ids]
        if "classification" in op:
            members = [
                x
                for x in members
                if x.classification and x.classification.code == op["classification"]
            ]
        return OperandResult(
            codes_of(members), tuple(claims), tuple(targets), known, tuple(missing)
        )
    return graph_operand(op, row, table, graph, by_key, outputs)
