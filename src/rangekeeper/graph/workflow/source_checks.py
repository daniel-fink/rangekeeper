"""Native workbook health and Evidence quality checks, with declared scopes."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from rangekeeper.graph.operation import _Failure
from rangekeeper.graph.provenance import locations
from rangekeeper.graph.workflow.ingestion import tabular

from ._declarations import fields, sequence
from .references import references


@dataclass(frozen=True, slots=True)
class SourceCheck:
    """Carries source-quality findings even for observations excluded from the
    graph, since successful graph construction does not establish source
    completeness.
    """

    id: str
    name: str
    status: str
    count: int
    explanation: str
    references: tuple[str, ...] = ()


def validate(specs, seen):
    """Reject incomplete declarations before any workbook is opened."""
    from ._declarations import text

    common = {"id", "operation"}
    contracts = {
        "workbook_health": ({"workbook"}, set()),
        "identities": ({"table", "column", "name", "explanation"}, set()),
        "occupied_rows": ({"table", "name", "explanation"}, {"columns"}),
        "numeric_issues": ({"tables"}, set()),
        "deferred": ({"name", "explanation"}, {"status"}),
    }
    ids = set()
    for index, s in enumerate(sequence(specs)):
        try:
            fields(s, set(s), common)
            op = text(s["operation"])
            if op not in contracts:
                raise ValueError("Unknown source check")
            required, optional = contracts[op]
            fields(s, common | required | optional, common | required)
            identifier = text(s["id"])
            if identifier in ids:
                raise ValueError("Duplicate source check ID")
            ids.add(identifier)
            for key in set(s) - {"columns", "tables"}:
                text(s[key])
            if "workbook" in s and seen.get(s["workbook"]) != "workbook":
                raise ValueError("Source check references unknown workbook")
            if "table" in s and seen.get(s["table"]) != "table":
                raise ValueError("Source check references unknown Evidence")
            for c in sequence(s.get("columns", ())):
                text(c)
            for t in sequence(s.get("tables", ())):
                fields(t, {"table", "columns"}, {"table", "columns"})
                if seen.get(t["table"]) != "table":
                    raise ValueError("Source check references unknown Evidence")
                for c in sequence(t["columns"]):
                    text(c)
        except (TypeError, ValueError) as exc:
            raise type(exc)(f"source_checks[{index}]: {exc}") from exc


def evaluate(specs, outputs):
    """Reviews native workbook health and declared Evidence scopes without
    inventing canonical graph objects for unsupported source material.
    """
    result = []
    for s in specs:
        op = s["operation"]
        if op == "workbook_health":
            book = outputs[s["workbook"]]
            cells = [c for sheet in book.worksheets for c in sheet.cells.values()]
            formulas = [c for c in cells if c.formula is not None]
            missing = [c for c in formulas if not c.cache_present]
            errors = [c for c in cells if c.data_type == "e" or c.cached_type == "e"]
            for suffix, name, selected, explanation in [
                (
                    "cache",
                    "Formula caches",
                    missing,
                    f"{len(formulas)} formulas inspected; caches are read, never calculated.",
                ),
                (
                    "errors",
                    "Excel errors",
                    errors,
                    "Includes stored formula results and literal error cells.",
                ),
            ]:
                refs = tuple(
                    f"{c.location.source.name} · {c.location.reference['sheet']}!{c.coordinate}"
                    for c in selected
                )
                result.append(
                    SourceCheck(
                        s["id"] + "-" + suffix,
                        book.source.name + ": " + name,
                        "finding" if selected else "passed",
                        len(selected),
                        explanation,
                        refs,
                    )
                )
        elif op == "deferred":
            result.append(
                SourceCheck(
                    s["id"],
                    s["name"],
                    s.get("status", "unable to assess"),
                    0,
                    s["explanation"],
                )
            )
        elif op in {"identities", "occupied_rows"}:
            table = outputs[s["table"]]
            parents = []
            if op == "identities":
                col = s["column"]
                if col not in table.data.columns:
                    raise _Failure(
                        "missing_column", "Identity check references an absent column"
                    )
                counts = Counter(
                    (type(r.values[col]), r.values[col]) for r in table.data.rows
                )
                rows = [
                    r
                    for r in table.data.rows
                    if r.values[col] is None
                    or counts[(type(r.values[col]), r.values[col])] > 1
                ]
                parents = [tabular.claim(table, r.id, col) for r in rows]
            else:
                rows = list(table.data.rows)
                parents = [
                    tabular.claim(table, r.id, c)
                    for r in rows
                    for c in s.get("columns", table.data.columns)
                    if r.values[c] is not None
                ]
            result.append(
                SourceCheck(
                    s["id"],
                    s["name"],
                    "finding"
                    if rows
                    else (
                        "unable to assess"
                        if not table.data.rows and op == "identities"
                        else "passed"
                    ),
                    len(rows),
                    s["explanation"],
                    references(parents),
                )
            )
        else:
            grouped = defaultdict(set)
            messages = {
                "blank_cell": "blank",
                "blank_value": "blank",
                "missing_marker": "dash marker",
                "missing_formula_cache": "missing formula cache",
                "excel_error": "Excel error",
                "non_numeric_value": "non-numeric value",
                "non_finite_value": "non-finite value",
                "negative_value": "negative value",
                "fractional_count": "fractional count",
            }
            for selection in s["tables"]:
                table = outputs[selection["table"]]
                for row in table.data.rows:
                    for col in selection["columns"]:
                        if col not in table.data.columns:
                            raise _Failure(
                                "missing_column",
                                "Numeric check references an absent column",
                            )
                        claim = tabular.claim(table, row.id, col)
                        if claim.value is not None:
                            continue
                        codes = [i.code for i in tabular.issues_for(table, row.id, col)]
                        labels = [messages[c] for c in codes if c in messages]
                        label = labels[0] if labels else "unavailable"
                        for loc in locations(claim):
                            if "cell" in loc.reference:
                                ref = f"{loc.source.name} · {loc.reference['sheet']}!{loc.reference['cell']}"
                                grouped[(loc.source.name, label)].add(ref)
            for (name, label), refs in sorted(grouped.items()):
                result.append(
                    SourceCheck(
                        s["id"] + "-" + name + "-" + label.lower().replace(" ", "-"),
                        name + ": " + label,
                        "review" if label in {"blank", "dash marker"} else "finding",
                        len(refs),
                        "Preserved as unavailable, never zero; applicability requires field review.",
                        tuple(sorted(refs)),
                    )
                )
    return tuple(result)
