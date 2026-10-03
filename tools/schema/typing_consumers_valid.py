"""Statically checked Model projection and source workflow calls."""

from pathlib import Path
from rangekeeper import Model
from rangekeeper.graph import View, Hierarchy
from rangekeeper.graph.projection import ValueColumn, to_table, to_tree_table
from rangekeeper.table import Table
from rangekeeper.workflow.specification import WorkflowSpec
from rangekeeper.workflow.runtime import run


def consume(model: Model, spec: WorkflowSpec, root: Path) -> Table:
    view = View(model)
    table = to_table(view, columns=(ValueColumn("Area", "net", "meter**2"),))
    tree = to_tree_table(Hierarchy.from_relationships(view))
    outcome = run(spec, input_root=root)
    if outcome.output is not None:
        built: Model = outcome.output.model
    return table
