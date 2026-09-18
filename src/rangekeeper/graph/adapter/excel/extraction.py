"""Physical rows to Evidence[Table], with no semantic filtering or coercion."""

from typing import Any
from uuid import UUID, uuid5

from ...provenance import Claim, Method
from ...table import Table
from .. import _structured
from ..ingestion import Evidence, EvidenceKey, Issue, IssueSeverity, tabular
from ..ingestion._encoding import encode
from ..operation import Operation, Outcome, _Failure, _invoke, fingerprint
from .snapshot import Cell, Workbook, Worksheet
from .specification import ExtractionSpec

_METHOD = Method(code="rk.excel.extract_table", version="1")
_VALUE_METHOD = Method(code="rk.excel.stored_value", version="1")


def _matches(cell: Cell, expected: object, comparison: str) -> bool:
    if cell.data_type == "e" or cell.cached_type == "e":
        return False
    if cell.formula is not None and not cell.cache_present:
        return False
    actual = cell.value
    if comparison == "trim":
        actual = actual.strip() if type(actual) is str else actual
        expected = expected.strip() if type(expected) is str else expected
    return encode(actual) == encode(expected)


def _last_row(sheet: Worksheet, spec: ExtractionSpec) -> int:
    if spec.rows.end is not None:
        return spec.rows.end
    stop = spec.rows.stop_before
    assert stop is not None
    for row in range(spec.rows.start, sheet.declared_rows + 1):
        if _matches(sheet.cell(f"{stop.column}{row}"), stop.equals, stop.comparison):
            return row - 1
    raise _Failure(
        "missing_stop_marker",
        "Required stopping marker was not found",
        locations=(sheet.location,),
        details={
            "start": spec.rows.start,
            "stop_before": {
                "column": stop.column,
                "equals": stop.equals,
                "comparison": stop.comparison,
            },
        },
    )


def _cell_claim(
    cell: Cell,
    operation_key: str,
    canonical: dict[str, Claim[Any]],
) -> tuple[Claim[Any], str | None]:
    value, code = cell.value, None
    if cell.merged_anchor is not None and cell.merged_anchor != cell.coordinate:
        value, code = None, "merged_cell_covered"
    elif cell.data_type == "e" or cell.cached_type == "e":
        value, code = None, "excel_error"
    elif cell.formula is not None and not cell.cache_present:
        value, code = None, "missing_formula_cache"
    elif value is None:
        code = "blank_cell"
    if cell.coordinate in canonical:
        return canonical[cell.coordinate], code

    namespace = cell.location.source.id
    key = _structured.fingerprint((
        operation_key,
        cell.location.reference,
        cell.observation(),
    ))
    if cell.formula is not None or code in ("excel_error", "merged_cell_covered"):
        observation = Claim.sourced(
            cell.observation(),
            at=cell.location,
            id=uuid5(namespace, "observation:" + key),
            method=_METHOD,
        )
        claim = Claim.derived(
            value,
            from_claims=(observation,),
            method=_VALUE_METHOD,
            id=uuid5(namespace, "value:" + key),
        )
    else:
        claim = Claim.sourced(
            value,
            at=cell.location,
            method=_METHOD,
            id=uuid5(namespace, "value:" + key),
        )
    canonical[cell.coordinate] = claim
    return claim, code


_MESSAGES = {
    "blank_cell": "Source cell is blank",
    "excel_error": "Source cell stores an Excel error",
    "missing_formula_cache": "Formula has no stored cached result; it was not recalculated",
    "merged_cell_covered": "Cell is covered by a merged range; anchor values are not propagated",
}


def extract_table(
    workbook: Workbook, specification: ExtractionSpec
) -> Outcome[Evidence[Table]]:
    if not isinstance(workbook, Workbook):
        raise TypeError("workbook must be Workbook")
    if not isinstance(specification, ExtractionSpec):
        raise TypeError("specification must be ExtractionSpec")

    def execute(operation: Operation) -> Evidence[Table]:
        sheet = workbook._require_sheet(specification.sheet)
        for coordinate, expected in sorted(specification.expect.cells.items()):
            cell = sheet.cell(coordinate)
            if not _matches(cell, expected, specification.expect.comparison):
                raise _Failure(
                    "layout_mismatch",
                    "Source does not match an extraction layout guard",
                    locations=(cell.location,),
                    details={
                        "expected": expected,
                        "actual": cell.value,
                        "comparison": specification.expect.comparison,
                    },
                )
        end = _last_row(sheet, specification)
        operation_key = fingerprint(operation)
        claims: dict[EvidenceKey, Claim[Any]] = {}
        canonical: dict[str, Claim[Any]] = {}
        issues: list[Issue] = []
        row_ids: list[UUID] = []
        for row in range(specification.rows.start, end + 1):
            row_id = uuid5(
                workbook.source.id,
                _structured.fingerprint((
                    "rk.excel.row/v1",
                    specification.id,
                    specification.sheet,
                    row,
                )),
            )
            row_ids.append(row_id)
            for column in specification.columns:
                cell = sheet.cell(f"{column.column}{row}")
                claim, code = _cell_claim(cell, operation_key, canonical)
                key = ("rows", str(row_id), column.name)
                claims[key] = claim
                if code is not None:
                    issues.append(
                        Issue(
                            rule_id=specification.id,
                            code=code,
                            severity=IssueSeverity.WARNING,
                            message=_MESSAGES[code],
                            at=(key,),
                            related_claims=(claim,),
                            details={
                                "sheet": specification.sheet,
                                "cell": cell.coordinate,
                                "merged_anchor": cell.merged_anchor,
                            },
                        )
                    )
        return tabular.from_claims(
            name=specification.id,
            columns=(column.name for column in specification.columns),
            row_ids=row_ids,
            claims=claims,
            issues=issues,
        )

    return _invoke(
        _METHOD, specification.to_mapping(), {"workbook": workbook.fingerprint}, execute
    )
