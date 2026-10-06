"""Convert the approved pinned design read; keep its payload and Model private."""

from pathlib import Path
import json
from uuid import UUID
from rangekeeper.migration.speckle import MappingSpec, convert_speckle
from rangekeeper.io import json as codec
from rangekeeper.adapters.speckle.mapping import encode_model, decode_model

p = Path("/private/tmp/rk-turn3-private")
mapping = MappingSpec(
    classifications=("floor", "space", "utilities", "building", "property"),
    relationships=("spatiallyContains", "services", "contains"),
    measurements={
        "gfa": "meter ** 2",
        "volume": "meter ** 3",
        "ffl": "meter",
        "ftf": "meter",
        "perimeter": "meter",
    },
    properties=("use", "number"),
    source_name="Speckle c0f66c35e3/e7acaac21ae7e9369339900a4aaeb827",
)
result = convert_speckle(
    json.loads((p / "design.json").read_text()),
    mapping=mapping,
    revision_id=UUID("424cbb7c-43eb-469e-bd3c-dd9d0926f3ee"),
)
assert result.model is not None, result.issues
codec.write(result.model, p / "design-model.json")
envelope = encode_model(result.model, associations=result.associations)
assert decode_model(envelope).to_data() == result.model.to_data()
print(
    json.dumps(
        {
            "status": "converted",
            "entities": len(result.model.system.entities),
            "assemblies": len(result.model.system.assemblies),
            "relationships": len(result.model.system.relationships),
            "associations": len(result.associations),
            "sha256": result.source_sha256,
        }
    )
)
