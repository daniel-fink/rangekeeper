"""Statically checked Model projection and source workflow calls."""

from rangekeeper import Model
from rangekeeper.flow import Flow
from rangekeeper.market import Paths
from rangekeeper.model import Distribution
from rangekeeper.model.system import Hierarchy, View
from rangekeeper.model.system.table import ValueColumn, to_table
from rangekeeper.shared.table import Table


def consume(model: Model) -> Table:
    view = View(model=model)
    table = to_table(
        source=view, columns=(ValueColumn(name="Area", key="net", units="meter**2"),)
    )
    tree = to_table(source=Hierarchy.from_relationships(view))
    return table


def consume_market(paths: "Paths", distribution: "Distribution") -> "Flow":
    """Market paths give Flows; calculations share the generated public record types."""
    distribution.check()
    index: Flow = paths[paths.keys[0]]["rent_index"]
    mean: Flow = paths.mean(name="rent_index")
    return index
