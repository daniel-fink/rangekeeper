"""Headless rendering probe for planar Speckle quads; not a production renderer."""

import hashlib
import json


def triangulate(mesh, diagonal):
    """Convert a planar quad in two ways without changing its stored definition."""
    if mesh.get("speckle_type") != "Objects.Geometry.Mesh" or mesh.get("faces") != [
        4,
        0,
        1,
        2,
        3,
    ]:
        raise ValueError("probe requires one explicit quad")
    if len(mesh.get("vertices", [])) != 12:
        raise ValueError("probe requires four vertices")
    if diagonal not in ("02", "13"):
        raise ValueError("unknown diagonal")
    triangles = [[0, 1, 2], [0, 2, 3]] if diagonal == "02" else [[0, 1, 3], [1, 2, 3]]
    result = {
        "vertices": list(mesh["vertices"]),
        "triangles": triangles,
        "units": mesh["units"],
    }
    result["cache_key"] = hashlib.sha256(
        json.dumps(
            {"source": mesh, "converter": "planar-quad-probe/1", "diagonal": diagonal},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return result


def area(rendering):
    vertices = [rendering["vertices"][i : i + 3] for i in range(0, 12, 3)]
    total = 0.0
    for triangle in rendering["triangles"]:
        a, b, c = [vertices[i] for i in triangle]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        cross = [
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        ]
        total += sum(x * x for x in cross) ** 0.5 / 2
    return total
