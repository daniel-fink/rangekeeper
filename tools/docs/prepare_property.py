"""Capture, rebuild and verify the pinned notebook 02 property source package.

Only capture uses Speckle or credentials. Build and verify work offline and use
the existing explicit legacy converter. They do not author financial equations.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
from uuid import NAMESPACE_URL, UUID, uuid5


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "examples/walkthrough/data/mixed_use_property"
PROJECT = "c0f66c35e3"
OBJECT = "e7acaac21ae7e9369339900a4aaeb827"
LEGACY = "6732e83d277c8de81f3dec2906e06d0e75d3b6fa"
MAPPING = {
    "classifications": ["property", "building", "space", "floor", "utilities"],
    "relationships": ["spatiallyContains", "services", "contains"],
    "measurements": {
        "gfa": "meter ** 2",
        "volume": "meter ** 3",
        "ffl": "meter",
        "ftf": "meter",
        "perimeter": "meter",
    },
    "properties": ["use", "number"],
    "source_name": f"Speckle {PROJECT}/{OBJECT}",
}


def encode(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def capture(destination: Path) -> None:
    """Receive the exact object into memory; retain original transport JSON strings."""
    import os
    from dotenv import dotenv_values
    from specklepy.api.client import SpeckleClient
    from specklepy.api import operations
    from specklepy.transports.memory import MemoryTransport
    from specklepy.transports.server import ServerTransport

    require(not destination.exists(), "Capture destination already exists")
    token = os.environ.get("SPECKLE_TOKEN") or dotenv_values(ROOT / "src/.env").get(
        "SPECKLE_TOKEN"
    )
    require(bool(token), "Configure SPECKLE_TOKEN before capture")
    client = SpeckleClient(host="app.speckle.systems")
    client.authenticate_with_token(token)
    memory = MemoryTransport()
    operations.receive(
        obj_id=OBJECT,
        remote_transport=ServerTransport(stream_id=PROJECT, client=client),
        local_transport=memory,
    )
    expand(memory.objects)  # Validate closure before retaining the capture.
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encode(memory.objects))
    print(f"Captured {len(memory.objects)} original transport records")


def expand(transport: dict[str, str]) -> dict:
    """Resolve all transport references, keeping original IDs and geometry.

    Remove only __closure indexes from the derived expanded form. Original JSON
    strings, including those indexes, remain unchanged in the source archive.
    """
    objects = {key: json.loads(value) for key, value in transport.items()}
    require(OBJECT in objects, "Pinned root is missing")
    require(
        set(objects) == {OBJECT, *objects[OBJECT]["__closure"]},
        "Capture must contain the root and its complete declared closure",
    )
    require(all(key == value["id"] for key, value in objects.items()), "ID mismatch")
    reached = {OBJECT}

    def visit(value, active):
        if isinstance(value, dict):
            if value.get("speckle_type") == "reference":
                key = value["referencedId"]
                require(key in objects, f"Missing detached object {key}")
                require(key not in active, f"Cyclic transport reference {key}")
                reached.add(key)
                return visit(objects[key], (*active, key))
            return {
                key: visit(child, active)
                for key, child in value.items()
                if key != "__closure"
            }
        if isinstance(value, list):
            return [visit(child, active) for child in value]
        return value

    result = visit(objects[OBJECT], (OBJECT,))
    require(reached == set(objects), "Capture contains unreachable transport objects")
    return result


def domain_records(payload: dict) -> dict[str, dict]:
    records = {}

    def visit(value):
        if isinstance(value, dict):
            if "entityId" in value:
                records.setdefault(value["entityId"], {}).update(value)
            for key, child in value.items():
                if key not in {"@displayValue", "displayValue", "renderMaterial"}:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return records


def table_bytes(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def legacy_assumptions() -> dict:
    """Read constant teaching inputs without executing the legacy notebook."""
    notebook = json.loads(
        subprocess.check_output(
            ["git", "show", f"{LEGACY}:walkthrough/drive_model_from_design.ipynb"],
            cwd=ROOT,
        )
    )
    values = {}
    for index in (26, 58):
        for statement in ast.parse("".join(notebook["cells"][index]["source"])).body:
            if isinstance(statement, ast.Assign):
                value = statement.value
                if isinstance(value, ast.Call):
                    require(
                        isinstance(value.func, ast.Name) and value.func.id == "dict",
                        "Unexpected legacy input expression",
                    )
                    value = {
                        item.arg: ast.literal_eval(item.value)
                        for item in value.keywords
                    }
                else:
                    value = ast.literal_eval(value)
                values[statement.targets[0].id] = value
    fields = {
        "efficiency": "efficiency_ratios",
        "initial_rent_AUD_per_m2_per_year": "initial_income_per_area_pa",
        "annual_income_growth": "pgi_growth_rates",
        "vacancy": "vacancy_rates",
        "floor_opex_AUD_per_m2_per_year": "floor_opex_per_area_pa",
        "facade_opex_AUD_per_m2_per_year": "facade_opex_per_area_pa",
        "floor_capex_AUD_per_m2_per_payment": "floor_capex_per_area_pa",
    }
    return {
        "status": "Legacy teaching assumptions retained for notebook 02; not market estimates or measured geometry",
        "source": {
            "commit": LEGACY,
            "notebook": "walkthrough/drive_model_from_design.ipynb",
            "zero_based_cells": {
                "income": 26,
                "dates": 28,
                "costs": 58,
                "capital_projection": [61, 63],
                "capitalization": 94,
                "discount": 99,
            },
        },
        "currency": "AUD",
        "use_assumptions": {
            use: {field: values[key][use] for field, key in fields.items()}
            for use in ("hotel", "residential", "retail", "parking")
        },
        "annual_opex_growth": values["opex_growth_rate"],
        "utility_capex_AUD_per_m3_per_payment": {
            "cores": values["cores_capex_per_vol_pa"],
            "plant": values["plant_capex_per_vol_pa"],
        },
        "capex_growth_per_payment_interval": values["capex_growth_rate"],
        "capital_payments": [
            {"date": "2005-12-31", "growth_exponent": 0},
            {"date": "2010-12-31", "growth_exponent": 1},
        ],
        "holding_span": {
            "start_inclusive": "2001-01-01",
            "end_exclusive": "2011-01-01",
        },
        "forecast_span": {
            "start_inclusive": "2001-01-01",
            "end_exclusive": "2012-01-01",
        },
        "timing": {
            "operating_payments": "year_end",
            "first_income_growth_exponent": 0,
            "sale_date": "2010-12-31",
            "sale_basis": "2011 NACF after all intended capital expenditure",
            "exit_capitalization_rate": 0.05,
            "annual_discount_rate": 0.07,
            "discount_exponents": list(range(1, 11)),
        },
        "reporting": {
            "root_contributors": "Unique floor and physical utility identities in the spatial hierarchy",
            "shared_costs": "Show plinth and shared plant separately; no implied allocation to buildings",
            "utilities_group": "Inspection grouping of the same physical utilities; not additional costs",
        },
        "worked_floor_id": "22851887-f9ee-4aa8-8755-bc021c3a3b30",
        "legacy_correction": "Include utility-only capital expenditure in NACF even where an object has no income or OPEX",
    }


def derive(transport: dict[str, str]) -> dict[str, bytes]:
    """Convert and independently reconcile identities, values, edges and geometry."""
    from rangekeeper.adapters.speckle import decode_model, encode_model
    from rangekeeper.io import json as codec
    from rangekeeper.migration import speckle
    from rangekeeper.model import Model
    from rangekeeper.model.content import decode
    from rangekeeper.model.system import View, Hierarchy

    payload = expand(transport)
    converter_hash = digest(Path(speckle.__file__).read_bytes())
    revision_key = digest(encode([payload, MAPPING, converter_hash]))
    result = speckle.convert_speckle(
        payload,
        mapping=speckle.MappingSpec(**MAPPING),
        revision_id=uuid5(
            NAMESPACE_URL, "urn:rk:walkthrough:property:v1:" + revision_key
        ),
    )
    require(result.model is not None, f"Conversion issues: {result.issues}")
    model = result.model
    source = domain_records(payload["@property"])
    require(
        set(source) == set(domain_records(payload)), "Domain records outside property"
    )
    entities = {str(item.id): item for item in model.find_entities()}
    require(set(entities) == set(source), "Source and Model identities differ")
    require(all(a == b for a, b in result.identity_map), "Domain identity changed")
    classes = {
        item.id: item.code
        for taxonomy in model.definitions.taxonomies
        for item in taxonomy.classifications
    }
    measurements = 0
    properties = 0
    for key, raw in source.items():
        obj = entities[key]
        require(obj.name == raw["name"], "Name differs from source")
        require(classes[obj.classification] == raw["type"], "Classification differs")
        actual = {value.key: value for value in obj.characteristics.values or ()}
        expected = set(raw) & (
            set(MAPPING["measurements"]) | set(MAPPING["properties"])
        )
        require(set(actual) == expected, "Source field coverage differs")
        for field in expected:
            if field in MAPPING["measurements"]:
                value = actual[field].quantity
                require(
                    value is not None and value.magnitude == raw[field],
                    "Quantity differs",
                )
                require(
                    value.units == MAPPING["measurements"][field],
                    "Unit mapping differs",
                )
                measurements += 1
            else:
                require(decode(actual[field].content) == raw[field], "Property differs")
                properties += 1

    edges = {
        (str(edge.source), str(edge.target), classes[edge.classification])
        for edge in model.system.relationships
    }
    expected_edges = set()
    for owner, raw in source.items():
        for edge in raw.get("relationships", []):

            def endpoint(value):
                return (
                    owner
                    if value is None
                    else value["entityId"] if isinstance(value, dict) else value
                )

            expected_edges.add(
                (endpoint(edge["source"]), endpoint(edge["target"]), edge["type"])
            )
    require(edges == expected_edges, "Source and Model relationship sets differ")

    legacy_html = subprocess.check_output(
        ["git", "show", f"{LEGACY}:walkthrough/_static/property.html"], cwd=ROOT
    ).decode()
    legacy_graph = {}
    for name in ("nodes", "edges"):
        match = re.search(
            rf"{name}\s*=\s*new vis\.DataSet\((\[.*?\])\);", legacy_html, re.S
        )
        require(match is not None, f"Legacy {name} data missing")
        legacy_graph[name] = json.loads(match[1])
    require(
        set(source) == {node["id"] for node in legacy_graph["nodes"]},
        "Legacy node set differs",
    )
    require(
        edges == {(e["from"], e["to"], e["label"]) for e in legacy_graph["edges"]},
        "Legacy edge set differs",
    )

    spatial = View(
        model,
        relationships=[
            e.id
            for e in model.system.relationships
            if classes[e.classification] == "spatiallyContains"
        ],
    )
    hierarchy = Hierarchy.from_relationships(spatial)
    require(
        set(map(str, hierarchy.preorder())) == set(source),
        "Spatial scope is incomplete",
    )
    grouped = defaultdict(list)
    rows = []
    geometry_checks = []
    for uid in hierarchy.preorder():
        raw = source[str(uid)]
        parent = hierarchy.parent(uid)
        branch = uid
        while hierarchy.parent(branch) not in (None, hierarchy.root):
            branch = hierarchy.parent(branch)
        effective_use = raw.get("use")
        if raw["type"] == "floor":
            effective_use = source[str(parent)]["use"]
            require(
                effective_use in {"hotel", "residential", "retail", "parking"},
                "Unknown use",
            )
            require(
                all(
                    type(raw.get(k)) in (int, float)
                    for k in ("gfa", "perimeter", "ftf", "ffl", "number")
                ),
                "Incomplete floor measurements",
            )
            grouped[(source[str(branch)]["name"], effective_use)].append(raw["gfa"])
        if raw["type"] == "floor" or (raw["type"] == "utilities" and "volume" in raw):
            breps = [
                g
                for g in raw.get("@displayValue", [])
                if g.get("speckle_type") == "Objects.Geometry.Brep"
            ]
            require(
                len(breps) == 1 and breps[0]["units"] == "m",
                "Expected one metre-based Brep",
            )
            field, geometric = (
                ("gfa", "area") if raw["type"] == "floor" else ("volume", "volume")
            )
            require(
                math.isclose(
                    raw[field], breps[0][geometric], rel_tol=1e-10, abs_tol=1e-7
                ),
                "Geometry summary differs",
            )
            geometry_checks.append(
                {
                    "id": str(uid),
                    "field": field,
                    "source": raw[field],
                    "geometry_summary": breps[0][geometric],
                }
            )
        rows.append(
            {
                "id": str(uid),
                "name": raw["name"],
                "classification": raw["type"],
                "parent_id": str(parent) if parent else "",
                "branch": source[str(branch)]["name"],
                "source_use": raw.get("use", ""),
                "effective_use": effective_use or "",
                "gfa_m2": raw.get("gfa", ""),
                "perimeter_m": raw.get("perimeter", ""),
                "ftf_m": raw.get("ftf", ""),
                "ffl_m": raw.get("ffl", ""),
                "volume_m3": raw.get("volume", ""),
                "number": raw.get("number", ""),
            }
        )

    associations = [dict(item) for item in result.associations]
    transport_ids = set(transport)
    require(
        {a["domain_id"] for a in associations} == set(source),
        "Association coverage differs",
    )
    require(
        all(a["content_id"] in transport_ids for a in associations),
        "Association source ID missing",
    )
    envelope = encode_model(model, associations=associations)
    require(
        decode_model(envelope).to_data() == model.to_data(),
        "Envelope round trip differs",
    )
    serialized = codec.dumps(model)
    require(
        codec.loads(serialized, kind=Model).to_data() == model.to_data(),
        "Model round trip differs",
    )
    summary = {
        "status": "passed",
        "model_revision": str(model.id),
        "transport_objects": len(transport),
        "project_objects": len(source),
        "entities": len(model.system.entities),
        "assemblies": len(model.system.assemblies),
        "classifications": dict(Counter(v["type"] for v in source.values())),
        "relationships": dict(Counter(e[2] for e in edges)),
        "associations": len(associations),
        "measurements_checked": measurements,
        "properties_checked": properties,
        "root_id": str(hierarchy.root),
        "source_sha256": result.source_sha256,
        "converter_sha256": converter_hash,
        "legacy_commit": LEGACY,
        "legacy_graph_exact_identity_and_edge_match": True,
        "gfa_m2": math.fsum(v["gfa"] for v in source.values() if v["type"] == "floor"),
        "areas": [
            {
                "building": b,
                "use": u,
                "floor_objects": len(values),
                "gfa_m2": math.fsum(values),
            }
            for (b, u), values in sorted(grouped.items())
        ],
        "geometry_summary_checks": geometry_checks,
        "geometry_check_scope": "Compare supplied Brep area/volume summaries; no independent BRep recomputation or viewer acceptance.",
    }
    relationship_rows = [
        {
            "source_id": a,
            "source_name": source[a]["name"],
            "type": c,
            "target_id": b,
            "target_name": source[b]["name"],
        }
        for a, b, c in sorted(edges)
    ]
    return {
        "model.json": serialized.encode(),
        "mapping.json": encode(MAPPING),
        "associations.json": encode(associations),
        "inventory.csv": table_bytes(rows),
        "relationships.csv": table_bytes(relationship_rows),
        "audit.json": encode(summary),
        "assumptions.json": encode(legacy_assumptions()),
    }


def build(
    transport_path: Path,
    destination: Path,
    *,
    captured_on: str,
    sdk_version: str,
) -> None:
    require(not destination.exists(), "Build destination already exists")
    transport = json.loads(transport_path.read_bytes())
    files = derive(transport)
    files["transport.json.gz"] = gzip.compress(encode(transport), mtime=0)
    manifest = {
        "host": "app.speckle.systems",
        "project_id": PROJECT,
        "model_id": "119ad04487",
        "requested_object_id": OBJECT,
        "historical_version_id": "9a9670946f",
        "pin_basis": "Explicit object in the legacy notebooks; historical version resolution is not asserted.",
        "captured_on": captured_on,
        "sdk": "specklepy",
        "sdk_version": sdk_version,
        "geometry_storage": "Complete original transport JSON, including context and property, in transport.json.gz",
        "normalisation": "Resolve all references; remove only __closure indexes for conversion; preserve original content IDs.",
        "files": {
            name: {"sha256": digest(data), "bytes": len(data)}
            for name, data in files.items()
        },
    }
    destination.mkdir(parents=True)
    for name, data in files.items():
        (destination / name).write_bytes(data)
    (destination / "manifest.json").write_bytes(encode(manifest))
    print(
        json.dumps(
            {
                "status": "built",
                "path": str(destination),
                "bytes": sum(map(len, files.values())),
            }
        )
    )


def verify(destination: Path) -> None:
    manifest = json.loads((destination / "manifest.json").read_bytes())
    for name, item in manifest["files"].items():
        data = (destination / name).read_bytes()
        require(
            digest(data) == item["sha256"] and len(data) == item["bytes"],
            f"Artifact changed: {name}",
        )
    transport = json.loads(
        gzip.decompress((destination / "transport.json.gz").read_bytes())
    )
    for name, data in derive(transport).items():
        require(
            (destination / name).read_bytes() == data,
            f"Offline rebuild differs: {name}",
        )
    print(
        "Verified hashes, complete transport closure, exact offline rebuild, legacy graph, values, geometry summaries and codec round trips"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    acquisition = commands.add_parser("capture")
    acquisition.add_argument("--output", type=Path, required=True)
    creation = commands.add_parser("build")
    creation.add_argument("--transport", type=Path, required=True)
    creation.add_argument("--output", type=Path, default=PACKAGE)
    creation.add_argument(
        "--captured-on", required=True, help="Actual capture date, YYYY-MM-DD"
    )
    creation.add_argument(
        "--sdk-version", required=True, help="SDK version used for capture"
    )
    verification = commands.add_parser("verify")
    verification.add_argument("--package", type=Path, default=PACKAGE)
    args = parser.parse_args()
    if args.command == "capture":
        capture(args.output)
    elif args.command == "build":
        build(
            args.transport,
            args.output,
            captured_on=args.captured_on,
            sdk_version=args.sdk_version,
        )
    else:
        verify(args.package)
