"""Provider-neutral Geometry checks. Native decoding belongs to the provider."""

import json
from hashlib import sha256
from pathlib import PurePosixPath

from rangekeeper.shared.validation import require


def inventory_digest(files):
    """Hash the sorted exact native file inventory, independent of its storage root."""
    value = sorted(files, key=lambda item: item["path"])
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def safe_path(path):
    """Return True for a nonempty relative POSIX path with no empty, dot or parent segment."""
    return (
        isinstance(path, str)
        and bool(path)
        and "\\" not in path
        and not PurePosixPath(path).is_absolute()
        and all(p not in ("", ".", "..") for p in path.split("/"))
    )


def check_geometry(model):
    """Check the Geometry pin inventory and the uniqueness and targets of its mappings."""
    geometry = model.get("geometry")
    if geometry is None:
        return
    pin = geometry["pin"]
    paths = [item["path"] for item in pin["files"]]
    require(
        bool(paths)
        and len(set(paths)) == len(paths)
        and all(safe_path(p) for p in paths),
        "Geometry file paths must be unique safe relative paths",
    )
    require(
        pin["content_digest"] == inventory_digest(pin["files"]),
        "Geometry inventory digest does not match",
    )
    entities = {
        e["id"]
        for name in ("entities", "assemblies")
        for e in (model.get("system") or {}).get(name, [])
    }
    seen = set()
    for mapping in geometry.get("mappings", []):
        require(
            mapping["entity"] in entities,
            "Geometry mapping must target a Model Entity or Assembly",
        )
        element = mapping["element"]
        require(
            element["kind"] in ("object", "group"),
            "Geometry mapping must target a source object or structural group",
        )
        require(bool(element["key"]), "Geometry selector key is empty")
        pair = (mapping["entity"], json.dumps(element, sort_keys=True))
        require(pair not in seen, "Duplicate Geometry mapping pair")
        seen.add(pair)
