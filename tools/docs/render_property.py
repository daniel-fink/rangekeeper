"""Render notebook 02 geometry aids from the pinned local display meshes.

This is presentation preparation, not a geometry measurement or financial model.
No credentials or live Speckle service are used. Re-run after changing the source
package. The original Breps and transport IDs remain in that package.
"""

import csv
import gzip
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from prepare_property import PACKAGE, ROOT, domain_records, expand

OUTPUT = ROOT / "examples/walkthrough/resources/mixed-use"
COLORS = {
    "hotel": "#4477AA",
    "residential": "#228833",
    "retail": "#CCBB44",
    "parking": "#999999",
    "cores": "#AA3377",
    "plant": "#EE6677",
    "context": "#C6CBD1",
}


def meshes(value):
    if isinstance(value, dict):
        if value.get("speckle_type") == "Objects.Geometry.Mesh":
            yield value
        else:
            for child in value.values():
                yield from meshes(child)
    elif isinstance(value, list):
        for child in value:
            yield from meshes(child)


def numbers(chunks):
    return (
        [x for chunk in chunks for x in chunk["data"]]
        if chunks and isinstance(chunks[0], dict)
        else chunks
    )


def triangulate(mesh):
    vertices = np.array(numbers(mesh["vertices"])).reshape(-1, 3)
    faces = numbers(mesh["faces"])
    triangles = []
    cursor = 0
    while cursor < len(faces):
        count = {0: 3, 1: 4}.get(faces[cursor], faces[cursor])
        polygon = faces[cursor + 1 : cursor + 1 + count]
        if count < 3 or len(polygon) != count:
            raise ValueError("Invalid display mesh face")
        triangles.extend(
            (polygon[0], polygon[i], polygon[i + 1]) for i in range(1, count - 1)
        )
        cursor += count + 1
    triangles = np.array(triangles)
    if triangles.size == 0 or triangles.min() < 0 or triangles.max() >= len(vertices):
        raise ValueError("Invalid display mesh indices")
    return vertices, triangles


def render(items, name, title):
    seen = {item[1] for item in items}
    # A separate static rendering keeps the physical form visible without JS.
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(projection="3d")
    all_vertices = []
    for label, use, uid, mesh in items:
        if use == "context":
            continue
        vertices, triangles = triangulate(mesh)
        all_vertices.append(vertices)
        ax.add_collection3d(
            Poly3DCollection(
                vertices[triangles],
                facecolors=COLORS[use],
                edgecolors="#ffffff",
                linewidths=0.15,
                alpha=0.85,
            )
        )
    points = np.concatenate(all_vertices)
    lower, upper = points.min(axis=0), points.max(axis=0)
    extent = np.maximum(upper - lower, 1)
    for setter, lo, hi in zip(
        (ax.set_xlim, ax.set_ylim, ax.set_zlim),
        lower - extent * 0.05,
        upper + extent * 0.05,
    ):
        setter(lo, hi)
    ax.set_box_aspect(extent)
    ax.view_init(elev=25, azim=-60)
    ax.set_axis_off()
    ax.set_title(title.replace(" and context", ""), loc="left", fontsize=16, pad=12)
    ax.legend(
        handles=[
            Patch(color=COLORS[use], label=use.title())
            for use in COLORS
            if use in seen and use != "context"
        ],
        loc="lower center",
        ncol=3,
        frameon=False,
    )
    if name == "property":
        for label, position in (
            ("Building A", (0.30, 0.85)),
            ("Building B", (0.77, 0.57)),
            ("Shared basement plinth", (0.40, 0.21)),
        ):
            ax.text2D(
                *position,
                label,
                transform=ax.transAxes,
                fontsize=11,
                color="#172A3A",
                bbox=dict(facecolor="white", alpha=0.9, edgecolor="none"),
            )
    fig.savefig(OUTPUT / f"{name}.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = expand(
        json.loads(gzip.decompress((PACKAGE / "transport.json.gz").read_bytes()))
    )
    records = domain_records(source)
    rows = list(csv.DictReader((PACKAGE / "inventory.csv").open()))
    property_items, utility_items = [], []
    used_meshes = set()
    for row in rows:
        use = row["effective_use"]
        if row["classification"] != "floor" and use not in {"cores", "plant"}:
            continue
        for mesh in meshes(records[row["id"]].get("@displayValue", [])):
            if mesh["id"] in used_meshes:
                continue
            used_meshes.add(mesh["id"])
            item = (row["name"], use, row["id"], mesh)
            property_items.append(item)
            if row["classification"] != "floor":
                utility_items.append(item)
    context_items = []
    for mesh in meshes(source["@context"]):
        if mesh["id"] not in used_meshes:
            used_meshes.add(mesh["id"])
            context_items.append(
                (
                    "Surrounding context (excluded from calculations)",
                    "context",
                    mesh["id"],
                    mesh,
                )
            )
    render(property_items, "property", "Two buildings and their shared basement")
    render(
        utility_items,
        "utilities",
        "Physical services: two core systems and shared plant",
    )
    print(
        json.dumps(
            {
                "physical_objects": len({i[2] for i in property_items}),
                "property_meshes": len(property_items),
                "context_meshes": len(context_items),
                "output": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()
