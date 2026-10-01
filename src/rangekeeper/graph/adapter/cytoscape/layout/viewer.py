"""Validated saved-layout display binding and atomic review export.

No ingestion, graph mutation or solver invocation. A caller supplies an already
completed display document, frozen problem, and result.
"""

import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4

from .check import check, metrics
from .model import Problem, Rect, from_document
from .result import Result


def fingerprint(value: dict) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def display_fingerprint(document: dict) -> str:
    return fingerprint({
        "elements": [e["data"] for e in document["elements"]],
        "assemblies": document["assemblies"],
        "details": document["details"],
        "claims": document["claims"],
        "reviewItems": document.get("reviewItems", []),
    })


def validate_saved_layout(document: dict) -> None:
    artifact = document["savedLayout"]
    if artifact["schema"] != "rk-saved-layout-v1":
        raise ValueError("Unsupported saved layout schema")
    if display_fingerprint(document) != artifact["displayFingerprint"]:
        raise ValueError("Saved layout belongs to a different graph display snapshot")
    problem = from_document(artifact["problem"])
    geometry = artifact["geometry"]
    if geometry["problem_fingerprint"] != problem.fingerprint:
        raise ValueError("Saved layout problem fingerprint mismatch")
    if fingerprint(geometry) != artifact["geometryFingerprint"]:
        raise ValueError("Saved layout geometry fingerprint mismatch")
    if geometry["mode"] != "strict" or geometry["findings"]:
        raise ValueError(
            "Only checked strict geometry can be displayed as saved layout"
        )
    rectangles = {i: Rect(**r) for i, r in geometry["rectangles"].items()}
    nodes = {e["data"]["id"] for e in document["elements"] if "source" not in e["data"]}
    if set(rectangles) != nodes or {
        a.id: set(a.members) for a in problem.assemblies
    } != {i: set(a["entities"]) for i, a in document["assemblies"].items()}:
        raise ValueError("Saved layout identities or memberships do not match")
    if (
        check(problem, rectangles)
        or metrics(problem, rectangles, geometry["grids"]) != geometry["metrics"]
    ):
        raise ValueError("Saved layout failed independent geometry/score validation")
    if problem.header < 28 or any(
        r.width < 32 or r.height < 28 for r in rectangles.values()
    ):
        raise ValueError("Saved footprints are too small for the viewer label contract")
    for element in document["elements"]:
        i = element["data"]["id"]
        if i in rectangles:
            r = rectangles[i]
            expected = {"x": r.x + r.width / 2, "y": r.y + r.height / 2}
            if (
                document["positions"][i] != expected
                or element.get("position") != expected
            ):
                raise ValueError("Saved positions do not match rectangle centres")


def with_saved_layout(document: dict, problem: Problem, result: Result) -> dict:
    """Return a new display snapshot; reject stale, partial or diagnostic geometry."""
    if (
        result.status not in {"feasible", "optimal"}
        or result.problem_fingerprint != problem.fingerprint
    ):
        raise ValueError("A matching successful layout result is required")
    output = deepcopy(document)
    geometry = result.geometry_document()
    output["savedLayout"] = {
        "schema": "rk-saved-layout-v1",
        "problem": problem.document(),
        "geometry": geometry,
        "geometryFingerprint": fingerprint(geometry),
        "displayFingerprint": display_fingerprint(output),
    }
    output["positions"] = {
        i: {"x": r.x + r.width / 2, "y": r.y + r.height / 2}
        for i, r in result.rectangles.items()
    }
    for element in output["elements"]:
        if "source" not in element["data"]:
            element["position"] = dict(output["positions"][element["data"]["id"]])
    output["initialFocus"] = None
    validate_saved_layout(output)
    return output


def export_layout_review(
    document: dict,
    problem: Problem,
    result: Result,
    root: Path,
    *,
    review_html: Path | None = None,
    context: dict | None = None,
) -> Path:
    """Publish a complete unique run, then atomically update latest.json.

    A failed validation/export leaves the previous successful pointer untouched.
    An interruption may leave an unreferenced temporary/run directory; it cannot
    make the pointer refer to a partial bundle. Runtime metadata is separate.
    """
    from .. import write_viewer
    from .render import svg

    output = with_saved_layout(document, problem, result)
    if output.get("reviewUrl") and review_html is None:
        raise ValueError(
            "Provide the completed review snapshot for provenance return links"
        )
    root = Path(root)
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    temporary = Path(mkdtemp(prefix=".building-", dir=runs))
    identifier = str(uuid4())
    destination = runs / identifier
    pointer = root / f".latest-{identifier}.json"
    try:
        for name, value in (
            ("problem.json", problem.document()),
            ("geometry.json", result.geometry_document()),
            ("document.json", output),
            (
                "run.json",
                {
                    "completedAt": datetime.now(timezone.utc).isoformat(),
                    "result": asdict(result),
                },
            ),
        ):
            (temporary / name).write_text(
                json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
            )
        if context is not None:
            (temporary / "context.json").write_text(
                json.dumps(context, sort_keys=True, indent=2, allow_nan=False) + "\n"
            )
        if review_html is not None:
            shutil.copyfile(review_html, temporary / "review.html")
        write_viewer([output], temporary / "viewer.html")
        (temporary / "layout.svg").write_text(svg(problem, result))
        manifest = {
            f.name: sha256(f.read_bytes()).hexdigest() for f in temporary.iterdir()
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        )
        temporary.rename(destination)
        pointer.write_text(
            json.dumps({
                "run": f"runs/{identifier}",
                "viewer": f"runs/{identifier}/viewer.html",
            })
            + "\n"
        )
        pointer.replace(root / "latest.json")
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        pointer.unlink(missing_ok=True)
    return destination
