"""Shared escaped HTML review and explicit artifact writing for workflows."""

import json
from dataclasses import asdict
from html import escape
from pathlib import Path

from rangekeeper.io import json as model_json
from rangekeeper.adapters.cytoscape import project, write_viewer
from rangekeeper.operation import fingerprint
from rangekeeper.workflow.ingestion import tabular

from ._declarations import plain
from .references import references


def _references(items) -> str:
    if not items:
        return ""
    return (
        f"<details><summary>{len(items)} source references</summary><ul>"
        + "".join("<li>" + escape(item) + "</li>" for item in items)
        + "</ul></details>"
    )


def _completeness(check) -> str:
    """Show each operand's missing contributors without suggesting a complete total."""
    sides = []
    for name in ("left", "right"):
        missing = getattr(check, name + "_missing")
        known = getattr(check, name + "_known_subtotal")
        if missing:
            sides.append(
                "<li>"
                + escape(
                    f"{name.title()}: known subtotal {known}; missing contributors: "
                    + ", ".join(missing)
                )
                + "</li>"
            )
    return (
        (
            "<details><summary>Incomplete operands</summary><ul>"
            + "".join(sides)
            + "</ul></details>"
        )
        if sides
        else ""
    )


def render(result, *, viewer_url: str = "viewer.html") -> str:
    """Gives notebook and CLI users the same inspection of Evidence, checks and
    limitations while retaining access to the underlying graph provenance.
    """
    summaries = []
    for category in dict.fromkeys(c.category for c in result.checks):
        counts = ", ".join(
            f"{sum(c.category == category and c.status == status for c in result.checks)} {status}"
            for status in ("agree", "unavailable", "difference")
        )
        summaries.append(f"<li>{escape(category)}: {counts}</li>")
    rows = []
    for c in result.checks:
        rows.append(
            "<tr>"
            + "".join(
                "<td>" + escape(str(v)) + "</td>"
                for v in (
                    c.group,
                    c.scope,
                    c.status,
                    c.left,
                    c.right,
                    c.explanation,
                )
            )
            + "<td>"
            + _references(c.references)
            + _completeness(c)
            + "</td></tr>"
        )
    findings = "".join(
        "<li>" + escape(f"{f.topic}: {f.subject} — {f.explanation}") + "</li>"
        for f in result.findings
    )
    evidence = "".join(
        "<tr>"
        + "".join(
            "<td>" + escape(str(v)) + "</td>"
            for v in (name, len(e.data.rows), len(e.data.columns), len(e.issues))
        )
        + "</tr>"
        for name, e in result.evidence.items()
    )
    detail = []
    for name, table in result.evidence.items():
        header = (
            "<tr><th>Row ID</th>"
            + "".join("<th>" + escape(c) + "</th>" for c in table.data.columns)
            + "</tr>"
        )
        body = []
        for row in table.data.rows:
            cells = []
            for column in table.data.columns:
                claim = tabular.claim(table, row.id, column)
                title = str(claim.id) + " · " + "; ".join(references((claim,)))
                cells.append(
                    '<td title="'
                    + escape(title, quote=True)
                    + '">'
                    + escape("Unavailable" if claim.value is None else str(claim.value))
                    + "</td>"
                )
            body.append("<tr><td>" + str(row.id) + "</td>" + "".join(cells) + "</tr>")
        explanations = "".join(
            "<li>" + escape(i.message + " · " + str(i.at)) + "</li>"
            for i in table.issues
        )
        detail.append(
            "<details><summary>"
            + escape(name)
            + "</summary><table>"
            + header
            + "".join(body)
            + "</table><details><summary>Issues</summary><ul>"
            + explanations
            + "</ul></details></details>"
        )
    sources = "".join(
        "<tr>"
        + "".join(
            "<td>" + escape(str(v)) + "</td>"
            for v in (c.name, c.status, c.count, c.explanation)
        )
        + "<td>"
        + _references(c.references)
        + "</td></tr>"
        for c in result.source_checks
    )
    effective = result.metadata.get("effective_specification")
    declarations = ""
    if effective:
        declarations = (
            "<details><summary>Shared declarations and effective specification</summary>"
            "<p>Definitions and consumer paths retain the authored reference origins.</p>"
            '<pre style="white-space:pre-wrap">'
            + escape(json.dumps(plain(effective), ensure_ascii=False, indent=2))
            + "</pre></details>"
        )
    return (
        '<!doctype html><meta charset="utf-8"><title>Workflow review</title><style>body{font:15px system-ui;margin:2rem}table{border-collapse:collapse;width:100%}th{background:#f4f6f8}td{vertical-align:top;overflow-wrap:anywhere}summary{cursor:pointer}td details{margin:0}td ul{max-height:18rem;overflow:auto;padding-left:1.2rem}td,th{border:1px solid #ddd;padding:.4rem;text-align:left}details{margin:1rem 0}</style><h1>Workflow review</h1><ul>'
        + "".join(summaries)
        + '</ul><p><a href="'
        + escape(viewer_url, quote=True)
        + '">Open graph and provenance</a></p><h2>Findings</h2><ul>'
        + findings
        + "</ul><details><summary>Named Evidence</summary><table><tr><th>Name</th><th>Rows</th><th>Columns</th><th>Issues</th></tr>"
        + evidence
        + "</table></details><h2>Checks</h2><table><tr><th>Group</th><th>Scope</th><th>Status</th><th>Left</th><th>Right</th><th>Explanation</th><th>Sources</th></tr>"
        + "".join(rows)
        + "</table><h2>Source checks</h2><table><tr><th>Name</th><th>Status</th><th>Count</th><th>Explanation</th><th>Sources</th></tr>"
        + sources
        + "</table>"
        + declarations
        + "<h2>Evidence and lineage</h2>"
        + "".join(detail)
    )


def export(result, destination: Path):
    """Explicit export; run() itself never calls this function.

    Makes artifact creation an explicit caller decision after a build. The
    graph, checks and manifest travel together so a viewer alone cannot be
    mistaken for a reloadable reference.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    model_json.write(result.model, destination / "model.json")
    checks = {
        "checks": [asdict(c) for c in result.checks],
        "source_checks": [asdict(c) for c in result.source_checks],
        "deferred_records": plain(result.metadata.get("deferred_records", ())),
        "findings": [asdict(f) for f in result.findings],
        "deferred": plain(result.metadata.get("deferred", ())),
        "notes": plain(result.metadata.get("notes", ())),
    }
    (destination / "checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n"
    )
    metadata = plain(result.metadata)
    metadata["operation_records"] = [
        {
            "fingerprint": fingerprint(o),
            "method": {"code": o.method.code, "version": o.method.version},
            "specification": plain(o.specification),
            "inputs": plain(o.inputs),
        }
        for o in result.operations
    ]
    (destination / "manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    write_viewer([project(result.model, "Workflow Model")], destination / "viewer.html")
    (destination / "review.html").write_text(render(result))
    return destination
