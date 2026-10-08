"""Shared escaped HTML review and explicit artifact writing for workflows."""

import json
from dataclasses import asdict
from html import escape
from pathlib import Path
from urllib.parse import quote, urljoin

from rangekeeper.io import json as model_json
from rangekeeper.adapters.cytoscape import project, write_viewer
from rangekeeper.workflow.operation import fingerprint
from rangekeeper.workflow.evidence import tabular

from rangekeeper.workflow._declarations import plain
from rangekeeper.workflow.reporting import prepare
from rangekeeper.workflow.references import references
from rangekeeper.workflow.checking import CheckStatus


def target_links(targets, viewer_url):
    """A characteristic is inspected through its actual owner in Cytoscape."""
    links = []
    for target in targets:
        url = viewer_url.split("#")[0] + "#select=" + quote(target["owner"], safe="")
        links.append(
            '<li><a target="_blank" rel="noopener" href="'
            + escape(url, quote=True)
            + '">'
            + escape(target["label"])
            + "</a> · "
            + escape(target["characteristic"])
            + "</li>"
        )
    if not links:
        return "<p>No supported graph target recorded.</p>"
    return (
        f"<details><summary>{len(links)} supported assertions</summary><ul>"
        + "".join(links)
        + "</ul></details>"
    )


def decisions_html(decisions, *, targets=None, declared=None, viewer_url="viewer.html"):
    """Render existing questions without equating mapping approval with resolution."""
    targets, declared = targets or {}, declared or {}
    review_url = (
        "" if viewer_url == "viewer.html" else urljoin(viewer_url, "review.html")
    )
    records = sorted(
        decisions.get("decisions", ()),
        key=lambda d: (d.get("status") == "accepted", d.get("id", "")),
    )
    parts = [
        '<section id="clarifications"><h2>Questions and decisions</h2><p>Mapping approval and evidence completeness are separate. Questions and limitations below remain visible even for accepted mappings.</p>'
    ]
    for d in records:
        identifier = d["id"]
        attribution = d.get("source") or "Attribution not recorded"
        date = d.get("date") or "Date not recorded"
        refs = d.get("references") or ("Supporting source references not recorded",)
        parts += [
            '<details id="decision-'
            + escape(identifier, quote=True)
            + ('" open><summary>' if d.get("status") != "accepted" else '"><summary>')
            + escape(
                f"{identifier} · {d.get('status', 'Status not recorded')} · {d.get('category', '')}"
            )
            + "</summary>",
            "<p>" + escape(d.get("text", "Decision text not recorded")) + "</p>",
            "<p>" + escape(f"{attribution} · {date}") + "</p>",
            "<p>Evidence: " + escape("; ".join(refs)) + "</p>",
        ]
        uses = declared.get(identifier, ())
        parts.append(
            "<p>Declared uses: " + escape("; ".join(uses) or "None recorded") + "</p>"
        )
        parts.append(target_links(targets.get(identifier, ()), viewer_url))
        parts.append("</details>")
    for m in decisions.get("mappings", ()):
        identifier = m["id"]
        parts.append(
            '<details id="mapping-'
            + escape(identifier, quote=True)
            + '"><summary>'
            + escape(
                f"{identifier} · {m.get('title', '')} · mapping status: {m.get('status', 'not recorded')}"
            )
            + "</summary>"
        )
        for title, field in [
            ("Question / limitation", "question"),
            ("Proposed interpretation", "proposal"),
            ("Graph effect", "graph_structure"),
        ]:
            parts.append(
                "<p><strong>"
                + title
                + ":</strong> "
                + escape(m.get(field) or "Not recorded")
                + "</p>"
            )
        parts.append(
            "<p>Evidence: "
            + escape(
                f"{m.get('source', 'Source not recorded')} · {m.get('sheet', 'Sheet not recorded')} · {', '.join(m.get('cells', ())) or 'Cells not recorded'}"
            )
            + "</p>"
        )
        parts.append(
            "<p>Decisions: "
            + ", ".join(
                '<a href="'
                + escape(review_url + "#decision-" + quote(d, safe=""), quote=True)
                + '">'
                + escape(d)
                + "</a>"
                for d in m.get("decisions", ())
            )
            + "</p>"
        )
        combined = {
            (t["owner"], t["characteristic"]): t
            for d in m.get("decisions", ())
            for t in targets.get(d, ())
        }
        parts.append(target_links(combined.values(), viewer_url))
        parts.append("</details>")
    return (
        "".join(parts)
        + "</section>"
        + """<script>
function revealReviewAnchor(){const id=decodeURIComponent(location.hash.slice(1));
const item=document.getElementById(id);if(item&&item.tagName==='DETAILS'){item.open=true;item.scrollIntoView();}}
window.addEventListener('hashchange',revealReviewAnchor);revealReviewAnchor();</script>"""
    )


def clarification_html(result, viewer_url, *, prepared=None):
    snapshot = result.metadata.get("review_specification")
    if not snapshot:
        return "<h2>Questions and decisions</h2><p>This older build did not capture authored review records.</p>"
    prepared = prepare(result) if prepared is None else prepared
    targets, declared = prepared.targets, prepared.declared
    return decisions_html(
        snapshot.get("decisions", {}),
        targets=targets,
        declared=declared,
        viewer_url=viewer_url,
    )


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
        missing = check[name]["missing"]
        known = check[name]["known_subtotal"]
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


def _display_value(check, side):
    value = check[side]["value"]
    return len(value) if check["report_counts"] and value is not None else value


def render(result, *, viewer_url: str = "viewer.html", compact: bool = False) -> str:
    """Gives notebook and CLI users the same inspection of Evidence, checks and
    limitations while retaining access to the underlying graph provenance.
    """
    return _render(result, prepare(result), viewer_url=viewer_url, compact=compact)


def _render(result, prepared, *, viewer_url="viewer.html", compact=False):
    summaries = []
    for category in dict.fromkeys(c["category"] for c in prepared.checks):
        counts = ", ".join(
            f"{sum(c['category'] == category and c['status'] == status for c in prepared.checks)} {status}"
            for status in ("agree", "unavailable", "difference")
        )
        summaries.append(f"<li>{escape(category)}: {counts}</li>")
    rows = []
    owners = {str(key): value for key, value in prepared.owners.items()}
    for c in sorted(
        prepared.checks,
        key=lambda c: (
            {"difference": 0, "unavailable": 1, "agree": 2}.get(c["status"], 1),
            c["group"],
            c["scope"],
        ),
    ):
        if compact and c["status"] == CheckStatus.AGREE.value:
            continue
        rows.append(
            "<tr>"
            + "".join(
                "<td>" + escape(str(v)) + "</td>"
                for v in (
                    c["group"],
                    c["scope"],
                    c["status"],
                    _display_value(c, "left"),
                    _display_value(c, "right"),
                    c["explanation"],
                )
            )
            + "<td>"
            + _references(c["references"])
            + _completeness(c)
            + target_links(
                (
                    owners[t]
                    for t in dict.fromkeys(
                        (*c["left"]["targets"], *c["right"]["targets"])
                    )
                    if t in owners
                ),
                viewer_url,
            )
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
    for name, table in () if compact else result.evidence.items():
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
                title = (
                    str(claim.id)
                    + " · "
                    + "; ".join(
                        prepared.cell_references[(name, ("rows", str(row.id), column))]
                    )
                )
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
    if effective and not compact:
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
        + "</ul>"
        + clarification_html(result, viewer_url, prepared=prepared)
        + "<details><summary>Named Evidence</summary><table><tr><th>Name</th><th>Rows</th><th>Columns</th><th>Issues</th></tr>"
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
    prepared = prepare(result)
    checks = {
        "schema": "rk.workflow-checks/v2",
        "checks": prepared.checks,
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
    write_viewer(
        [project(result.model, "Workflow Model", {"reviewUrl": "review.html"})],
        destination / "viewer.html",
    )
    (destination / "review.html").write_text(_render(result, prepared))
    return destination
