"""Shared read-only graph projection and self-contained offline viewer."""

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from uuid import UUID

from rangekeeper.model import ValueKind, Model, Assembly, Classification
from rangekeeper.model.system import View
from rangekeeper.model.definitions import classification, measure
from rangekeeper.model.provenance import fact_for
from rangekeeper.model.content import decode

from rangekeeper.adapters.cytoscape.document import validate_document

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
        sequence = (
            sorted(value, key=str) if isinstance(value, (set, frozenset)) else value
        )
        cells = [present(v, depth + 1) for v in sequence[:60]]
        if len(sequence) > 60:
            cells.append({"display_truncated": True})
        return cells
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: present(getattr(value, f.name), depth + 1)
            for f in fields(value)
            if not f.name.startswith("_")
        }
    return {"unsupported_display_type": type(value).__name__}


def project(model: Model | View, name: str, config: dict | None = None) -> dict:
    """Project public RK objects into a viewer document without mutating the Model."""
    config = dict(config or {})
    if set(config) - {
        "positions",
        "notes",
        "anchors",
        "initialFocus",
        "alignment",
        "reviewUrl",
        "containmentClassifications",
    }:
        raise ValueError("Unknown viewer configuration fields")
    config["positions"] = dict(config.get("positions", {}))
    config.setdefault("positions", {})
    config.setdefault("notes", [])
    config.setdefault("anchors", [])
    config.setdefault("initialFocus", None)
    if not isinstance(model, (Model, View)):
        raise TypeError("project requires a Model or Model-backed View")
    view = model if isinstance(model, View) else View(model)
    model = view.model
    entities, relationships = view.entities, view.relationships
    entity_ids = {item.id for item in entities}
    relationship_ids = {item.id for item in relationships}
    evidence = model.provenance
    all_claims = {c.id: c for c in evidence.claims or ()} if evidence else {}
    sources = {s.id: s for s in evidence.sources or ()} if evidence else {}
    claims: dict[str, dict] = {}
    facts = {f.target: f for f in evidence.facts or ()} if evidence else {}

    def claim_row(identity) -> str:
        key = str(identity)
        if key not in claims:
            c = all_claims[identity]
            encoded = c.content.get("value") if isinstance(c.content, Mapping) else None
            claims[key] = {
                "id": key,
                "kind": c.kind.value,
                "value": (
                    present(encoded[1])
                    if isinstance(c.content, Mapping)
                    and c.content.get("encoding") == "rk.source-value/v1"
                    and isinstance(encoded, tuple)
                    and len(encoded) == 2
                    and encoded[0] == "str"
                    else present(c.content)
                ),
                "method": present(c.method.to_data()) if c.method else None,
                "sources": [],
            }
            claims[key]["sources"] = [
                (
                    {"claim": claim_row(s)}
                    if isinstance(s, UUID)
                    else {
                        "name": sources[s.source].name,
                        "checksum": sources[s.source].checksum,
                        "reference": dict(s.address or {}),
                    }
                )
                for s in c.sources or ()
            ]
        return key

    def fact_row(target) -> dict | None:
        fact = facts.get(target.id)
        if fact is None:
            return None
        reconciliation = fact.reconciliation
        selected = (
            reconciliation.selected
            if reconciliation
            else (fact.claims[0] if len(fact.claims) == 1 else None)
        )
        return {
            "status": "recorded" if selected else "unresolved",
            "claims": [claim_row(uid) for uid in fact.claims],
            "selected": str(selected) if selected else None,
            "reconciliation": reconciliation.status.value if reconciliation else None,
            "method": (
                present(reconciliation.method.to_data())
                if reconciliation and reconciliation.method
                else None
            ),
        }

    def class_row(uid):
        c = classification(model.definitions, uid) if uid else None
        return present(c) if c else None

    def detail(owner) -> dict:
        values = owner.characteristics.values or () if owner.characteristics else ()
        labels = owner.characteristics.labels or () if owner.characteristics else ()
        return {
            "id": str(owner.id),
            "classification": class_row(owner.classification),
            "fact": fact_row(owner),
            "measurements": [
                {
                    "id": str(v.id),
                    "measureId": str(v.measure),
                    "name": v.key,
                    "code": v.key,
                    "kind": v.kind.value,
                    "value": (
                        {"value": v.quantity.magnitude, "units": v.quantity.units}
                        if v.quantity
                        else None
                    ),
                    "definition": measure(model.definitions, v.measure).definition,
                    "fact": fact_row(v),
                }
                for v in values
                if v.kind is ValueKind.MEASUREMENT
            ],
            "labels": [
                {
                    "id": str(l.id),
                    "name": l.key,
                    "value": [class_row(uid) for uid in l.classifications or ()],
                    "fact": fact_row(l),
                }
                for l in labels
            ],
            "features": [
                {
                    "id": str(v.id),
                    "name": v.key,
                    "value": present(decode(v.content)) if v.content else None,
                    "fact": fact_row(v),
                }
                for v in values
                if v.kind is ValueKind.PROPERTY
            ],
            "flows": [
                {
                    "id": str(v.id),
                    "name": v.key,
                    "value": present(v.flow.to_data()) if v.flow else None,
                    "fact": fact_row(v),
                }
                for v in values
                if v.kind is ValueKind.FLOW
            ],
        }

    details = {
        str(o.id): detail(o) for owners in (entities, relationships) for o in owners
    }
    assemblies = {
        str(e.id): {
            "name": e.name or e.code,
            "entities": sorted(str(i) for i in (e.entities or ()) if i in entity_ids),
            "relationships": sorted(
                str(i) for i in (e.relationships or ()) if i in relationship_ids
            ),
        }
        for e in entities
        if isinstance(e, Assembly)
    }
    parents: dict[str, list[str]] = defaultdict(list)
    for e in relationships:
        if str(e.classification) in config.get("containmentClassifications", []):
            parents[str(e.target)].append(str(e.source))
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
    for i, entity in enumerate(entities):
        config["positions"].setdefault(
            str(entity.id), {"x": (i % 10) * 180, "y": (i // 10) * 140}
        )
    return {
        "name": name,
        "modelId": str(model.id),
        "elements": [
            *[
                {
                    "data": {
                        "id": str(e.id),
                        "label": e.name or e.code or str(e.id),
                        "code": e.code or "",
                        "kind": "assembly" if isinstance(e, Assembly) else "entity",
                        "type": str(e.classification) if e.classification else "",
                        "classificationCode": (
                            classification(model.definitions, e.classification).code
                            if e.classification
                            else ""
                        ),
                    },
                    "position": config["positions"].get(str(e.id), {"x": 0, "y": 0}),
                }
                for e in entities
            ],
            *[
                {
                    "data": {
                        "id": str(e.id),
                        "source": str(e.source),
                        "target": str(e.target),
                        "label": classification(
                            model.definitions, e.classification
                        ).name,
                        "type": str(e.classification),
                        "classificationCode": classification(
                            model.definitions, e.classification
                        ).code,
                        "kind": "relationship",
                    }
                }
                for e in relationships
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
        json.dumps(
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
        template.replace("/* VENDOR */", vendor)
        .replace("/* PROJECTION */", (ASSETS / "projection.js").read_text())
        .replace("/* ROUTING */", (ASSETS / "routing.js").read_text())
        .replace("/* APP */", (ASSETS / "viewer.js").read_text())
        .replace("/* STYLE */", (ASSETS / "viewer.css").read_text())
        .replace('"__DATA__"', payload)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path
