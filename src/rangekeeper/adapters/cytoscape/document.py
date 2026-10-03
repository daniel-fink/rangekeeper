"""Validate the JSON display contract before producing an offline document."""

import math
from collections.abc import Mapping


def validate_document(document: dict) -> None:
    """Reject duplicate IDs, dangling links and cyclic Assembly membership.

    This is a read-only display projection, not a graph persistence format.
    Classification identities are UUIDs supplied by the graph exporter.
    """
    required = {
        "name",
        "elements",
        "assemblies",
        "details",
        "claims",
        "positions",
        "notes",
        "anchors",
        "diagnostics",
    }
    if not isinstance(document, dict) or required - document.keys():
        raise ValueError("Incomplete Cytoscape display document")
    elements = document["elements"]
    ids = [e["data"]["id"] for e in elements]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate display object identity")
    nodes = {e["data"]["id"] for e in elements if "source" not in e["data"]}
    edges = {e["data"]["id"] for e in elements if "source" in e["data"]}
    for element in elements:
        row = element["data"]
        if "source" in row and not {row["source"], row["target"]} <= nodes:
            raise ValueError("Relationship endpoint outside display scope")
    if set(document["details"]) != set(ids):
        raise ValueError("Object details must match the display scope")
    if not set(document["assemblies"]) <= nodes:
        raise ValueError("Assembly outside display scope")
    for identifier in nodes:
        position = document["positions"].get(identifier)
        if not isinstance(position, Mapping) or any(
            not isinstance(position.get(axis), (float, int))
            or not math.isfinite(position[axis])
            for axis in ("x", "y")
        ):
            raise ValueError(f"Invalid position for {identifier}")
    active, visited = set(), set()

    def visit(identifier):
        if identifier in active:
            raise ValueError("Assembly membership cycle")
        if identifier in visited:
            return
        active.add(identifier)
        assembly = document["assemblies"][identifier]
        if (
            not set(assembly["entities"]) <= nodes
            or not set(assembly["relationships"]) <= edges
        ):
            raise ValueError("Assembly member outside display scope")
        for child in assembly["entities"]:
            if child in document["assemblies"]:
                visit(child)
        active.remove(identifier)
        visited.add(identifier)

    for identifier in document["assemblies"]:
        visit(identifier)
    for finding in document.get("reviewItems", []):
        if not set(finding["targets"]) <= set(ids):
            raise ValueError("Finding target outside display scope")
    if (
        document.get("initialFocus") is not None
        and document["initialFocus"] not in document["assemblies"]
    ):
        raise ValueError("Initial focus must reference a projected Assembly")
    if not set(document["anchors"]) <= nodes:
        raise ValueError("Layout anchor outside display scope")
