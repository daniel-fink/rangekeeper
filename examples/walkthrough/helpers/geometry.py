"""Display retained geometry with a verified, locally packaged Viewer build."""

import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path

from rangekeeper.io import json as codec
from rangekeeper.model import Model

from .speckle import validate_associations


def write(source: str | Path, destination: str | Path) -> Path:
    """Write a viewer and return its HTML path. No network access is performed.

    Source contains model.json, associations.json, transport.json.gz and manifest.json.
    Serve source and destination under the same local HTTP root, for example Jupyter
    or the walkthrough book. The browser verifies the retained source before display.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    hashes = {}
    for name in ("model.json", "associations.json", "transport.json.gz"):
        hashes[name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if hashes[name] != manifest["files"][name]["sha256"]:
            raise ValueError(f"Geometry source checksum mismatch: {name}")
    model = codec.loads((source / "model.json").read_text(), kind=Model)
    validate_associations(model, json.loads((source / "associations.json").read_text()))
    assets = files(__package__).joinpath("assets/geometry")
    bundle = json.loads(assets.joinpath("manifest.json").read_text())
    content = {}
    for name, expected in bundle["files"].items():
        if Path(name).name != name:
            raise ValueError("Invalid asset path")
        content[name] = assets.joinpath(name).read_bytes()
        if hashlib.sha256(content[name]).hexdigest() != expected:
            raise ValueError(f"Geometry asset checksum mismatch: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in content.items():
        (destination / name).write_bytes(data)
    (destination / "geometry.json").write_text(
        json.dumps(
            {
                "modelId": str(model.id),
                "rootId": manifest["requested_object_id"],
                "data": Path(os.path.relpath(source, destination)).as_posix(),
                "files": hashes,
                "bundle": bundle["version"],
            },
            indent=2,
        )
        + "\n"
    )
    (destination / "manifest.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return destination / "viewer.html"
