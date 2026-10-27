"""Retired 0.x system names stay absent from canonical imports."""

import ast
import importlib.util
from pathlib import Path

import pytest

import rangekeeper
from rangekeeper.model import system as graph
from rangekeeper.model.system import errors as graph_errors


@pytest.mark.parametrize("name", ("api", "measure"))
def test_old_root_module_paths_are_absent(name):
    assert name not in rangekeeper.__all__
    assert not hasattr(rangekeeper, name)
    assert importlib.util.find_spec(f"rangekeeper.{name}") is None


def test_system_surface_exposes_canonical_records_and_model_operations():
    import rangekeeper.model
    from rangekeeper.schema import records

    # One canonical path: rangekeeper.model exports the System records.
    for name in ("System", "Entity", "Assembly", "Relationship"):
        assert getattr(rangekeeper.model, name) is getattr(records, name)
        assert name not in graph.__all__
    for name in (
        "Graph",
        "Characteristics",
        "Definitions",
        "Measurement",
        "Feature",
        "Label",
        "Classification",
        "Taxonomy",
        "GraphError",
        "IdentityConflictError",
        "InvalidAggregationError",
    ):
        assert name not in graph.__all__
        assert not hasattr(graph, name), name
        assert not hasattr(graph_errors, name), name
    for name in (
        "_catalog",
        "graph",
        "entity",
        "assembly",
        "relationship",
        "characteristics",
        "classification",
        "taxonomy",
        "definitions",
        "provenance",
        "revision",
        "update",
        "adapter",
        "legacy",
    ):
        assert importlib.util.find_spec(f"rangekeeper.model.system.{name}") is None, (
            name
        )


def test_canonical_sources_do_not_import_the_predecessor():
    """Guard declared imports as well as the separate fresh-process checks."""
    root = Path(rangekeeper.__file__).parent
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if ".sync-conflict-" in path.name:
            continue
        module = "rangekeeper." + ".".join(relative.with_suffix("").parts)
        package = module.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [entry.name for entry in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    prefix = importlib.util.resolve_name(
                        "." * node.level + prefix, package
                    )
                names = [prefix, *(prefix + "." + entry.name for entry in node.names)]
            else:
                continue
            assert not any(
                name == "rangekeeper.legacy" or name.startswith("rangekeeper.legacy.")
                for name in names
            ), path
