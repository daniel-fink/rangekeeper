"""Pinned read acceptance of the new transport; no publication or payload retention."""

from pathlib import Path
import json, os
from dotenv import load_dotenv
from specklepy.api.client import SpeckleClient
from rangekeeper.adapters.speckle.transport import receive
from rangekeeper.migration.speckle import convert_speckle, MappingSpec

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / "walkthrough/.env")
load_dotenv(ROOT / "src/.env")
client = SpeckleClient(host="app.speckle.systems")
client.authenticate_with_token(os.environ["SPECKLE_TOKEN"])
result = receive(
    client, project_id="c0f66c35e3", object_id="e7acaac21ae7e9369339900a4aaeb827"
)
assert result.source["object_id"] == "e7acaac21ae7e9369339900a4aaeb827"
converted = convert_speckle(
    result.payload,
    mapping=MappingSpec(
        classifications=("property", "building", "space", "floor", "utilities"),
        relationships=("spatiallyContains", "services", "contains"),
        measurements={
            "gfa": "meter ** 2",
            "volume": "meter ** 3",
            "ffl": "meter",
            "ftf": "meter",
            "perimeter": "meter",
        },
        properties=("use", "number"),
    ),
)
assert converted.model, converted.issues
print(
    json.dumps(
        {
            "status": "passed",
            "source": dict(result.source),
            "entities": len(converted.model.system.entities),
            "assemblies": len(converted.model.system.assemblies),
            "relationships": len(converted.model.system.relationships),
        }
    )
)
