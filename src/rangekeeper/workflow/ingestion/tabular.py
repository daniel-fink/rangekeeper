"""Construct, inspect and transform Evidence[Table] using stable row identities."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from rangekeeper.errors import IdentityConflictError
from rangekeeper.evidence import Claim, Method
from rangekeeper.table import Row, Table
from rangekeeper.workflow.ingestion._encoding import encode
from rangekeeper.workflow.ingestion.errors import EvidenceValidationError
from rangekeeper.workflow.ingestion.evidence import (
    Evidence,
    EvidenceKey,
    Issue,
    IssueSeverity,
    _applicable,
)

if TYPE_CHECKING:
    from rangekeeper.operation import Outcome


def from_claims(
    *,
    name: str,
    columns: Iterable[str],
    row_ids: Iterable[UUID],
    claims: Mapping[EvidenceKey, Claim[Any]],
    issues: Iterable[Issue] = (),
) -> Evidence[Table]:
    """Derive Table values from terminal Claims; reject missing/extra evidence.

    Uses Claims as the single source of cell values, avoiding two independently
    constructed representations that can disagree.
    """
    # Delegate column and row identity normalization to Table, including its
    # existing errors, rather than maintaining a separate tabular schema.
    if isinstance(columns, (str, bytes)):
        raise TypeError("columns must be an iterable of strings")
    columns = Table(columns=tuple(columns), rows=()).columns
    row_ids = tuple(row_ids)
    skeleton = Table(
        columns=columns,
        rows=tuple(Row(values={c: None for c in columns}, id=uid) for uid in row_ids),
    )
    if not isinstance(claims, Mapping):
        raise TypeError("claims must be a mapping")
    rows = []
    for uid in _row_ids(skeleton):
        values = {}
        for column in columns:
            key = ("rows", str(uid), column)
            if key not in claims:
                raise EvidenceValidationError(
                    "claim_coverage", "Missing terminal Claim", key=key
                )
            claim_value = claims[key]
            if not isinstance(claim_value, Claim):
                raise TypeError("claims must contain Claim objects")
            values[column] = claim_value.value
        rows.append(Row(values=values, id=uid))
    return Evidence(
        name=name,
        data=Table(columns=columns, rows=tuple(rows)),
        claims=claims,
        issues=tuple(issues),
    )


def row(evidence: Evidence[Table], row_id: UUID) -> Row:
    """Resolve a row by UUID, never by display offset.

    Keeps consumer access stable when a table is selected, concatenated or
    displayed in a different order.
    """
    if not isinstance(evidence, Evidence) or not isinstance(evidence.data, Table):
        raise TypeError("Expected Evidence[Table]")
    return evidence.data.row(row_id)


def claim(evidence: Evidence[Table], row_id: UUID, column: str) -> Claim[Any]:
    """Return the terminal Claim; traverse Claim.sources for its full lineage.

    Use this instead of reading a value alone when downstream work must preserve
    the observation that supports it.
    """
    selected = row(evidence, row_id)
    if not isinstance(column, str):
        raise TypeError("column must be str")
    if column not in selected.values:
        raise KeyError(column)
    return evidence.claims[("rows", str(row_id), column)]


def issues_for(
    evidence: Evidence[Table],
    row_id: UUID,
    column: str | None = None,
) -> tuple[Issue, ...]:
    """Include ancestor scopes; row inspection also includes its cell issues.

    Collects the explanations a consumer needs at the chosen scope without
    requiring it to interpret raw address prefixes.
    """
    row(evidence, row_id)
    if column is not None:
        claim(evidence, row_id, column)
    key = ("rows", str(row_id)) + (() if column is None else (column,))
    return tuple(
        issue
        for issue in evidence.issues
        if _applicable(issue, key)
        or (column is None and any(scope[:2] == key for scope in issue.at))
    )


def _row_ids(table: Table) -> tuple[UUID, ...]:
    ids = []
    for item in table.rows:
        if item.id is None:
            raise EvidenceValidationError(
                "missing_row_ids", "Evidence requires an ID on every row"
            )
        ids.append(item.id)
    return tuple(ids)


def _validate_table(table: Table) -> None:
    _row_ids(table)
    for item in table.rows:
        for value in item.values.values():
            encode(value)


def _addressed_row(table: Table, key: EvidenceKey) -> Row:
    try:
        identifier = UUID(key[1])
        if str(identifier) != key[1]:
            raise ValueError("Noncanonical UUID")
        return table.row(identifier)
    except (ValueError, IndexError, KeyError) as exc:
        raise EvidenceValidationError(
            "invalid_address", "Unknown/noncanonical row ID", key=key
        ) from exc


def _validate_scope(table: Table, key: EvidenceKey) -> None:
    if not key:
        return
    if len(key) not in (2, 3) or key[0] != "rows":
        raise EvidenceValidationError(
            "invalid_address", "Expected row or cell address", key=key
        )
    _addressed_row(table, key)
    if len(key) == 3 and key[2] not in table.columns:
        raise EvidenceValidationError("invalid_address", "Unknown column", key=key)


def _cell(table: Table, key: EvidenceKey) -> object:
    _validate_scope(table, key)
    if len(key) != 3:
        raise EvidenceValidationError(
            "invalid_address", "Claim must address a cell", key=key
        )
    return _addressed_row(table, key).values[key[2]]


def _cell_keys(table: Table) -> Iterable[EvidenceKey]:
    return (
        ("rows", str(uid), column)
        for uid in _row_ids(table)
        for column in table.columns
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class NumberSpec:
    """Interpret a source column numerically without coercing text or units.

    Makes admissibility explicit so labels, booleans and missing markers cannot
    silently become measurements. Integer and negative-value policies belong to
    the field being interpreted.
    """

    column: str
    integer: bool = False
    nonnegative: bool = False
    missing_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.column, "column")
        if type(self.integer) is not bool or type(self.nonnegative) is not bool:
            raise TypeError("integer and nonnegative must be bool")
        if not isinstance(self.missing_markers, (tuple, list)):
            raise TypeError("missing_markers must be a sequence of strings")
        for marker in self.missing_markers:
            _text(marker, "missing marker")
        markers = tuple(dict.fromkeys(m.strip() for m in self.missing_markers))
        object.__setattr__(self, "missing_markers", markers)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> NumberSpec:
        """Rejects misspelled or mistyped numeric policies at the declaration
        boundary rather than silently applying different defaults.
        """
        if not isinstance(value, Mapping):
            raise TypeError("NumberSpec must be a mapping")
        if set(value) - {"column", "integer", "nonnegative", "missing_markers"}:
            raise ValueError("Unknown NumberSpec fields")
        if "column" not in value:
            raise ValueError("NumberSpec requires column")
        fields: dict[str, Any] = dict(value)
        return cls(**fields)

    def to_mapping(self) -> dict[str, object]:
        """Records the effective numeric policy, including defaults, so its
        derivation can be reproduced independently of the caller.
        """
        return {
            "column": self.column,
            "integer": self.integer,
            "nonnegative": self.nonnegative,
            "missing_markers": list(self.missing_markers),
        }


def _text(value: object, field: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be nonempty text")


def _evidence(value: Evidence[Table]) -> None:
    from rangekeeper.workflow.ingestion.validation import validate

    if not isinstance(value, Evidence) or type(value.data) is not Table:
        raise TypeError("Expected Evidence[Table]")
    validate(value)


from ._derivation import unique_issues as _unique_issues


def _output(*, name, columns, row_ids, claims, issues) -> Evidence[Table]:
    from rangekeeper.operation import _Failure

    try:
        return from_claims(
            name=name,
            columns=columns,
            row_ids=row_ids,
            claims=claims,
            issues=_unique_issues(issues),
        )
    except (EvidenceValidationError, IdentityConflictError) as exc:
        raise _Failure("conflicting_evidence", str(exc)) from exc


def select(
    evidence: Evidence[Table],
    *,
    row_ids: Iterable[UUID] | None = None,
    columns: Iterable[str] | None = None,
    name: str | None = None,
) -> Outcome[Evidence[Table]]:
    """Select/order outputs, preserving Claims and projecting Issue scopes.

    Allows detail, notes or other row groups to be reviewed separately without
    manufacturing new observations or retaining explanations for discarded
    cells.
    """
    from rangekeeper.operation import _Failure, _invoke
    from rangekeeper.workflow.ingestion.fingerprint import fingerprint

    _evidence(evidence)
    selected_ids = _row_ids(evidence.data) if row_ids is None else tuple(row_ids)
    if any(not isinstance(uid, UUID) for uid in selected_ids):
        raise TypeError("row_ids must contain UUIDs")
    if isinstance(columns, (str, bytes)):
        raise TypeError("columns must be an iterable of column names")
    selected_columns = evidence.data.columns if columns is None else tuple(columns)
    for column in selected_columns:
        _text(column, "column")
    output_name = evidence.name if name is None else name
    _text(output_name, "name")

    def execute(operation):
        if len(set(selected_ids)) != len(selected_ids) or len(
            set(selected_columns)
        ) != len(selected_columns):
            raise _Failure(
                "duplicate_selector", "Selectors must not repeat rows or columns"
            )
        if set(selected_ids) - set(_row_ids(evidence.data)):
            raise _Failure("unknown_row", "Selected row does not exist")
        if set(selected_columns) - set(evidence.data.columns):
            raise _Failure("missing_column", "Selected column does not exist")
        ids = {str(uid) for uid in selected_ids}
        issues = []
        for issue in evidence.issues:
            scopes = tuple(
                s
                for s in issue.at
                if not s or (s[1] in ids and (len(s) == 2 or s[2] in selected_columns))
            )
            if scopes:
                issues.append(
                    issue if scopes == issue.at else replace(issue, at=scopes)
                )
        return _output(
            name=output_name,
            columns=selected_columns,
            row_ids=selected_ids,
            claims={
                k: v
                for k, v in evidence.claims.items()
                if k[1] in ids and k[2] in selected_columns
            },
            issues=issues,
        )

    return _invoke(
        Method(code="rk.tabular.select", version="1"),
        {
            "name": output_name,
            "row_ids": tuple(str(uid) for uid in selected_ids),
            "columns": selected_columns,
        },
        {"evidence": fingerprint(evidence)},
        execute,
    )


def concat(
    evidences: Iterable[Evidence[Table]], *, name: str
) -> Outcome[Evidence[Table]]:
    """Append compatible tables, confining global Issues to their input rows.

    Combines separate source ranges without losing their identities. Confining
    each input-wide Issue prevents an explanation from leaking onto unrelated
    appended rows.
    """
    from rangekeeper.operation import _Failure, _invoke
    from rangekeeper.workflow.ingestion.fingerprint import fingerprint

    parts = tuple(evidences)
    if not parts:
        raise ValueError("concat requires at least one input")
    _text(name, "name")
    for part in parts:
        _evidence(part)

    def execute(operation):
        columns = parts[0].data.columns
        ids, claims, issues = [], {}, []
        seen = set()
        for part in parts:
            if part.data.columns != columns:
                raise _Failure(
                    "incompatible_columns",
                    "Concatenated tables require identical ordered columns",
                )
            part_ids = _row_ids(part.data)
            if seen.intersection(part_ids):
                raise _Failure("duplicate_row", "Concatenated row IDs must be unique")
            seen.update(part_ids)
            ids.extend(part_ids)
            claims.update(part.claims)
            for issue in part.issues:
                scopes = tuple(
                    dict.fromkeys(
                        scope
                        for original in issue.at
                        for scope in (
                            (original,)
                            if original
                            else tuple(("rows", str(uid)) for uid in part_ids)
                        )
                    )
                )
                if scopes:
                    issues.append(
                        issue if scopes == issue.at else replace(issue, at=scopes)
                    )
        return _output(
            name=name, columns=columns, row_ids=ids, claims=claims, issues=issues
        )

    return _invoke(
        Method(code="rk.tabular.concat", version="1"),
        {"name": name, "input_order": tuple(str(i) for i in range(len(parts)))},
        {str(i): fingerprint(part) for i, part in enumerate(parts)},
        execute,
    )


def _number(value: object, spec: NumberSpec) -> tuple[int | float | None, str | None]:
    if type(value) is str:
        if not value.strip():
            return None, "blank_value"
        if value.strip() in spec.missing_markers:
            return None, "missing_marker"
    if type(value) is not int and type(value) is not float:
        return None, "non_numeric_value"
    if type(value) is float and not math.isfinite(value):
        return None, "non_finite_value"
    if spec.nonnegative and value < 0:
        return None, "negative_value"
    if spec.integer and value != int(value):
        return None, "fractional_count"
    return int(value) if spec.integer else value, None


_NUMBER_MESSAGES = {
    "blank_value": "blank",
    "missing_marker": "dash marker",
    "non_numeric_value": "non-numeric value",
    "non_finite_value": "non-finite value",
    "negative_value": "negative value",
    "fractional_count": "fractional count",
}


def numbers(
    evidence: Evidence[Table],
    *,
    specifications: Mapping[str, NumberSpec],
    settings: Claim[str] | None = None,
    name: str | None = None,
) -> Outcome[Evidence[Table]]:
    """Append numeric interpretations supported by existing source Claims.

    Keeps numeric interpretation separate from the original observation.
    Appended Claims retain source and optional configuration lineage;
    unavailable values remain explained instead of being coerced to zero.
    """
    from rangekeeper.operation import _Failure, _invoke
    from rangekeeper.operation import fingerprint as operation_fingerprint
    from rangekeeper.workflow.ingestion.fingerprint import fingerprint

    _evidence(evidence)
    if not isinstance(specifications, Mapping):
        raise TypeError("specifications must map output names to NumberSpec")
    specs = dict(specifications)
    for output, spec in specs.items():
        _text(output, "output column")
        if not isinstance(spec, NumberSpec):
            raise TypeError("specifications must contain NumberSpec objects")
    if settings is not None and (
        not isinstance(settings, Claim) or type(settings.value) is not str
    ):
        raise TypeError("settings must be Claim[str]")
    output_name = evidence.name if name is None else name
    _text(output_name, "name")
    inputs = {"evidence": fingerprint(evidence)}
    from ._derivation import settings_inputs

    inputs.update(settings_inputs(settings))
    method = Method(code="rk.tabular.numbers", version="2")

    def execute(operation):
        if set(specs).intersection(evidence.data.columns):
            raise _Failure(
                "output_collision",
                "Numeric outputs must not overwrite existing columns",
            )
        if any(spec.column not in evidence.data.columns for spec in specs.values()):
            raise _Failure("missing_column", "Numeric source column does not exist")
        operation_key = operation_fingerprint(operation)
        claims = dict(evidence.claims)
        issues = list(evidence.issues)
        for uid in _row_ids(evidence.data):
            for output, spec in specs.items():
                upstream = claim(evidence, uid, spec.column)
                key = ("rows", str(uid), output)
                value, code = (
                    (None, None)
                    if upstream.value is None
                    else _number(upstream.value, spec)
                )
                parents = (
                    (upstream,)
                    if settings is None or settings is upstream
                    else (upstream, settings)
                )
                claims[key] = Claim.derived(
                    value,
                    from_claims=parents,
                    method=method,
                    id=uuid5(uid, f"{operation_key}:{output}"),
                )
                if upstream.value is None:
                    for issue in issues_for(evidence, uid, spec.column):
                        issues.append(replace(issue, at=(key,)))
                elif code is not None:
                    issues.append(
                        Issue(
                            rule_id=operation_key,
                            code=code,
                            severity=IssueSeverity.WARNING,
                            message=_NUMBER_MESSAGES[code],
                            at=(key,),
                            related_claims=(upstream,),
                        )
                    )
        return _output(
            name=output_name,
            columns=(*evidence.data.columns, *specs),
            row_ids=_row_ids(evidence.data),
            claims=claims,
            issues=issues,
        )

    return _invoke(
        method,
        {
            "name": output_name,
            "specifications": tuple(
                (output, spec.to_mapping()) for output, spec in specs.items()
            ),
        },
        inputs,
        execute,
    )
