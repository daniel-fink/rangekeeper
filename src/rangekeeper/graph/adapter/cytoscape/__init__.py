"""Shared read-only graph projection and self-contained offline viewer."""

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from uuid import UUID

from rangekeeper.graph import Assembly, Classification, Graph, View
from rangekeeper.graph.provenance import Claim

from .document import validate_document

__all__ = ["ASSETS", "present", "project", "validate_document", "write_viewer"]

ASSETS = Path(__file__).with_name("assets")


def present(value: object, depth: int = 0) -> object:
    """Bound rich values for display; never pretend unsupported values are serialized."""
    if depth > 7:
        return {"display_truncated": True}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        import math

        return value if math.isfinite(value) else {"nonfinite": str(value)}
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Classification):
        return {"id": str(value.id), "code": value.code, "name": value.name}
    if hasattr(value, "magnitude") and hasattr(value, "units"):
        return {
            "value": present(value.magnitude, depth + 1),
            "units": f"{value.units:~P}",
        }
    if isinstance(value, Mapping):
        items = list(value.items())
        result = {str(k): present(v, depth + 1) for k, v in items[:60]}
        if len(items) > 60:
            result["display_truncated"] = True
        return result
    if isinstance(value, (tuple, list, set, frozenset)):
        items = sorted(value, key=str) if isinstance(value, (set, frozenset)) else value
        result = [present(v, depth + 1) for v in items[:60]]
        if len(items) > 60:
            result.append({"display_truncated": True})
        return result
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: present(getattr(value, f.name), depth + 1)
            for f in fields(value)
            if not f.name.startswith("_")
        }
    return {"unsupported_display_type": type(value).__name__}


def project(graph: Graph | View, name: str, config: dict | None = None) -> dict:
    """Project public RK objects into a viewer document without mutating the Graph."""
    config = dict(config or {})
    if set(config) - {
        "positions",
        "notes",
        "anchors",
        "initialFocus",
        "alignment",
        "containmentClassifications",
    }:
        raise ValueError("Unknown viewer configuration fields")
    config["positions"] = dict(config.get("positions", {}))
    config.setdefault("positions", {})
    config.setdefault("notes", [])
    config.setdefault("anchors", [])
    config.setdefault("initialFocus", None)
    view = graph if isinstance(graph, View) else graph.view()
    graph = view.graph
    claims: dict[str, dict] = {}

    def claim_row(c: Claim) -> str:
        key = str(c.id)
        if key not in claims:
            claims[key] = {
                "id": key,
                "kind": c.kind.value,
                "value": present(c.value),
                "method": present(c.method),
                "sources": [],
            }
            claims[key]["sources"] = [
                {"claim": claim_row(s)}
                if isinstance(s, Claim)
                else {
                    "name": s.source.name,
                    "checksum": s.source.checksum,
                    "reference": dict(s.reference),
                }
                for s in c.sources
            ]
        return key

    def fact_row(target) -> dict | None:
        fact = graph.provenance.fact_for(target)
        if fact is None:
            return None
        return {
            "status": fact.status.value,
            "claims": [claim_row(c) for c in fact.claims],
            "selected": str(fact.current_claim.id) if fact.current_claim else None,
            "reconciliation": fact.reconciliation.status.value
            if fact.reconciliation
            else None,
            "method": present(fact.reconciliation.method)
            if fact.reconciliation
            else None,
        }

    def detail(owner) -> dict:
        return {
            "id": str(owner.id),
            "classification": present(owner.classification),
            "fact": fact_row(owner),
            "measurements": [
                {
                    "id": str(m.id),
                    "measureId": str(m.measure.id),
                    "name": m.measure.name,
                    "code": m.measure.code,
                    "value": present(m.quantity),
                    "definition": m.measure.definition,
                    "fact": fact_row(m),
                }
                for m in owner.measurements.values()
            ],
            "labels": [
                {
                    "id": str(l.id),
                    "name": l.key,
                    "value": present(l.classifications),
                    "fact": fact_row(l),
                }
                for l in owner.labels.values()
            ],
            "features": [
                {
                    "id": str(f.id),
                    "name": f.name,
                    "value": present(f.value),
                    "fact": fact_row(f),
                }
                for f in owner.features.values()
            ],
        }

    details = {str(o.id): detail(o) for o in (*view.entities, *view.relationships)}
    assemblies = {
        str(e.id): {
            "name": e.name or e.code,
            "entities": sorted(
                str(i) for i in e.entity_ids if i in {n.id for n in view.entities}
            ),
            "relationships": sorted(
                str(i)
                for i in e.relationship_ids
                if i in {r.id for r in view.relationships}
            ),
        }
        for e in view.entities
        if isinstance(e, Assembly)
    }
    parents: dict[str, list[str]] = defaultdict(list)
    for e in view.relationships:
        if str(e.classification.id) in config.get("containmentClassifications", []):
            parents[str(e.target_id)].append(str(e.source_id))
    ambiguous = sorted(i for i, items in parents.items() if len(set(items)) > 1)
    # Diagnose cyclic candidate hierarchies without flattening the domain graph.
    adjacency: dict[str, list[str]] = defaultdict(list)
    for child, items in parents.items():
        for parent in items:
            adjacency[parent].append(child)
    active: set[str] = set()
    seen: set[str] = set()
    cycles: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in active:
            cycles.update(path[path.index(node) :])
            return
        if node in seen:
            return
        active.add(node)
        for child in adjacency[node]:
            visit(child, [*path, node])
        active.remove(node)
        seen.add(node)

    for node in list(adjacency):
        visit(node, [])
    for i, e in enumerate(view.entities):
        config["positions"].setdefault(
            str(e.id), {"x": (i % 10) * 180, "y": (i // 10) * 140}
        )
    return {
        "name": name,
        "elements": [
            *[
                {
                    "data": {
                        "id": str(e.id),
                        "label": e.name or e.code or str(e.id),
                        "code": e.code or "",
                        "kind": "assembly" if isinstance(e, Assembly) else "entity",
                        "type": str(e.classification.id) if e.classification else "",
                        "classificationCode": e.classification.code
                        if e.classification
                        else "",
                    },
                    "position": config["positions"].get(str(e.id), {"x": 0, "y": 0}),
                }
                for e in view.entities
            ],
            *[
                {
                    "data": {
                        "id": str(e.id),
                        "source": str(e.source_id),
                        "target": str(e.target_id),
                        "label": e.classification.name,
                        "type": str(e.classification.id),
                        "classificationCode": e.classification.code,
                        "kind": "relationship",
                    }
                }
                for e in view.relationships
            ],
        ],
        "assemblies": assemblies,
        "details": details,
        "claims": claims,
        "diagnostics": {
            "ambiguousParents": ambiguous,
            "containmentCycles": sorted(cycles),
        },
        **config,
    }


def write_viewer(datasets: list[dict], path: Path) -> Path:
    """Write one offline HTML file; data, code, styles, and dependency assets are inline."""
    if not datasets:
        raise ValueError("At least one display document is required")
    for dataset in datasets:
        validate_document(dataset)
    template = (ASSETS / "viewer.html").read_text()
    payload = (
        json
        .dumps(
            {"format": "cytoscape-spike-view-v1", "datasets": datasets},
            ensure_ascii=False,
            allow_nan=False,
        )
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    vendor = "\n".join(
        (ASSETS / "vendor" / f).read_text()
        for f in (
            "cytoscape.js",
            "layout-base.js",
            "cose-base.js",
            "cytoscape-fcose.js",
        )
    )
    html = (
        template
        .replace("/* VENDOR */", vendor)
        .replace("/* PROJECTION */", (ASSETS / "projection.js").read_text())
        .replace("/* ROUTING */", (ASSETS / "routing.js").read_text())
        .replace("/* APP */", (ASSETS / "viewer.js").read_text())
        .replace("/* STYLE */", (ASSETS / "viewer.css").read_text())
        .replace('"__DATA__"', payload)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path
