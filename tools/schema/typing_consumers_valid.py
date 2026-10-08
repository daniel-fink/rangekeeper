"""Statically checked Model projection and source workflow calls."""

from pathlib import Path
from rangekeeper import Model
from rangekeeper.model.system import View, Hierarchy
from rangekeeper.model.system.projection import ValueColumn, to_table
from rangekeeper.shared.table import Table
from rangekeeper.workflow.specification import WorkflowSpec
from rangekeeper.workflow.runtime import run

from rangekeeper.model import Value
from rangekeeper.model.distribution import Distribution
from rangekeeper.model.scenario import Market
from rangekeeper.specification.policy import PolicyResult


def consume(model: Model, spec: WorkflowSpec, root: Path) -> Table:
    view = View(model)
    table = to_table(view, columns=(ValueColumn("Area", "net", "meter**2"),))
    tree = to_table(Hierarchy.from_relationships(view))
    outcome = run(spec, input_root=root)
    if outcome.output is not None:
        built: Model = outcome.output.model
    return table


def consume_market(market: "Market", distribution: "Distribution") -> "Value":
    """Named Market access and calculations share the generated public record types."""
    distribution.check()
    value: Value = market.space_market_price_factors
    rates: Value = market.implied_reversion_cap_rates
    result: PolicyResult = PolicyResult(())
    return value
