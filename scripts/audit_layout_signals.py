"""Inventory a completed graph for layout research; never infer graph facts.

This spike tool records classifications, membership, characteristics and their
actual Fact/Claim lineage. Presentation recommendations remain a separate review.
It reads only the saved graph and its frozen review manifest, not current YAML.
"""

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from rangekeeper.graph import Assembly, Graph
from rangekeeper.graph.adapter import json as graph_json
from rangekeeper.graph.provenance import Claim


def inventory(graph: Graph) -> dict:
    entities = {entity.id: entity for entity in graph.entities}
    groups = [entity for entity in graph.entities if isinstance(entity, Assembly)]
    parents = {identifier: [] for identifier in entities}
    for group in groups:
        for identifier in group.entity_ids:
            parents[identifier].append(str(group.id))

    def classification(entity):
        item = entity.classification
        return (
            {"id": str(item.id), "code": item.code, "definition": item.definition}
            if item
            else None
        )

    def evidence(target):
        fact = graph.provenance.fact_for(target)
        if fact is None:
            return {"status": "missing", "claims": [], "locations": []}
        claims, locations = {}, {}

        def visit(claim):
            key = str(claim.id)
            if key in claims:
                return
            claims[key] = {"id": key, "kind": claim.kind.value}
            for source in claim.sources:
                if isinstance(source, Claim):
                    visit(source)
                else:
                    location = {
                        "source_id": str(source.source.id),
                        "source": source.source.name,
                        "checksum": source.source.checksum,
                        "reference": dict(source.reference),
                    }
                    locations[json.dumps(location, sort_keys=True)] = location

        for claim in fact.claims:
            visit(claim)
        return {
            "status": fact.status.value,
            "selected_claim": str(fact.current_claim.id)
            if fact.current_claim
            else None,
            "claims": [claims[key] for key in sorted(claims)],
            "locations": [locations[key] for key in sorted(locations)],
        }

    def value_record(value):
        # Preserve JSON primitives without guessing units, date semantics or axes.
        if value is None or type(value) in (str, int, float, bool):
            return {"value": value, "python_type": type(value).__name__}
        return {
            "display": str(value),
            "python_type": f"{type(value).__module__}.{type(value).__qualname__}",
            "note": "Display only; consult the typed graph for this payload.",
        }

    objects = []
    for entity in sorted(graph.entities, key=lambda item: str(item.id)):
        objects.append(
            {
                "id": str(entity.id),
                "code": entity.code,
                "name": entity.name,
                "kind": type(entity).__name__,
                "classification": classification(entity),
                "parents": sorted(parents[entity.id]),
                "members": sorted(str(i) for i in entity.entity_ids)
                if isinstance(entity, Assembly)
                else [],
                "evidence": evidence(entity),
                "features": {
                    key: {
                        "id": str(item.id),
                        **value_record(item.value),
                        "evidence": evidence(item),
                    }
                    for key, item in sorted(entity.characteristics.features.items())
                },
                "measurements": {
                    key: {
                        "id": str(item.id),
                        "display": str(item.quantity),
                        "definition": item.measure.definition,
                    }
                    for key, item in sorted(entity.characteristics.measurements.items())
                },
                "labels": {
                    key: [c.code for c in item.classifications]
                    for key, item in sorted(entity.characteristics.labels.items())
                },
            }
        )

    def counts(values):
        return dict(sorted(Counter(values).items()))

    return {
        "schema": "rk-layout-signal-inventory-v1",
        "counts": {
            "objects": len(graph.entities),
            "ordinary_nodes": len(graph.entities) - len(groups),
            "assemblies": len(groups),
            "relationships": len(graph.relationships),
            "facts": len(graph.provenance.facts),
            "shared_direct_members": sum(len(p) > 1 for p in parents.values()),
        },
        "entity_classifications": counts(
            e.classification.code if e.classification else "<unclassified>"
            for e in graph.entities
        ),
        "relationship_classifications": counts(
            r.classification.code if r.classification else "<unclassified>"
            for r in graph.relationships
        ),
        "feature_keys": counts(k for e in graph.entities for k in e.features),
        "measurement_keys": counts(k for e in graph.entities for k in e.measurements),
        "objects": objects,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.bundle / name for name in ("graph.json", "manifest.json", "run.json")]
    payloads = {path.name: path.read_bytes() for path in paths}
    run = json.loads(payloads["run.json"])
    if run.get("complete") is not True:
        raise ValueError("The selected workflow bundle is not marked complete")
    manifest = json.loads(payloads["manifest.json"])
    graph = graph_json.loads(payloads["graph.json"].decode())
    canonical_before = graph_json.dumps(graph)
    report = inventory(graph)
    assert graph_json.dumps(graph) == canonical_before, "Graph changed during audit"
    report["snapshot"] = {
        "bundle": str(args.bundle.resolve()),
        "finished_at": run.get("finished_at"),
        "sha256": {name: sha256(data).hexdigest() for name, data in payloads.items()},
        "inventory_script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Selected completed snapshot; no claim of current input freshness.",
    }
    report["frozen_review"] = manifest.get("review_specification", {}).get("decisions")
    for path in paths:
        if path.read_bytes() != payloads[path.name]:
            raise ValueError(f"Snapshot changed during audit: {path}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Never replace an earlier audit report.
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
