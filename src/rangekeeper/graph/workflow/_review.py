"""Read-only indexes connecting authored interpretation to supported graph Facts."""

import json
from collections import defaultdict
from collections.abc import Mapping
from html import escape
from urllib.parse import quote, urljoin

from rangekeeper.graph.provenance import Claim


def decision_records(claims):
    """Walk all supporting Claims; a derived assertion may use several decisions."""
    pending, seen = list(claims), set()
    while pending:
        claim = pending.pop()
        if claim.id in seen:
            continue
        seen.add(claim.id)
        if claim.method and claim.method.code == "reviewed-decision":
            try:
                record = (
                    json.loads(claim.value)
                    if isinstance(claim.value, str)
                    else claim.value
                )
            except (ValueError, TypeError):
                record = None
            if isinstance(record, Mapping) and isinstance(record.get("id"), str):
                yield record
        pending.extend(c for c in claim.sources if isinstance(c, Claim))


def object_index(result):
    """Resolve assertion targets to their inspectable graph owners."""
    owners = {}
    for owner in (*result.graph.entities, *result.graph.relationships):
        label = (
            getattr(owner, "code", None)
            or getattr(owner, "name", None)
            or str(owner.id)
        )
        owners[owner.id] = {
            "owner": str(owner.id),
            "label": label,
            "characteristic": "Object",
        }
        for kind in ("features", "measurements", "labels"):
            for key, characteristic in getattr(owner, kind).items():
                owners[characteristic.id] = {
                    "owner": str(owner.id),
                    "label": label,
                    "characteristic": f"{kind}: {key}",
                }
    return owners


def usage(result):
    """Separate declared use from actual Fact support; never infer targets from prose."""
    targets = defaultdict(dict)
    owners = object_index(result)
    for fact in result.graph.provenance.facts:
        if fact.target.id not in owners:
            continue
        for decision in decision_records(fact.claims):
            targets[decision["id"]][str(fact.target.id)] = owners[fact.target.id]
    declared = defaultdict(list)

    def visit(value, path):
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == "decisions" and isinstance(child, (tuple, list)):
                    for identifier in child:
                        if isinstance(identifier, str):
                            declared[identifier].append(path)
                else:
                    visit(child, f"{path}.{key}")
        elif isinstance(value, (tuple, list)):
            for index, child in enumerate(value):
                identity = (
                    child.get("id", index) if isinstance(child, Mapping) else index
                )
                visit(child, f"{path}[{identity}]")

    snapshot = result.metadata.get("review_specification", {})
    for section in ("steps", "model", "checks"):
        visit(snapshot.get(section, {}), section)
    return {key: tuple(value.values()) for key, value in targets.items()}, dict(
        declared
    )


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


def clarification_html(result, viewer_url):
    snapshot = result.metadata.get("review_specification")
    if not snapshot:
        return "<h2>Questions and decisions</h2><p>This older build did not capture authored review records.</p>"
    targets, declared = usage(result)
    return decisions_html(
        snapshot.get("decisions", {}),
        targets=targets,
        declared=declared,
        viewer_url=viewer_url,
    )
