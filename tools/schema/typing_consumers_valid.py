"""Statically checked Model projection and source workflow calls."""

from rangekeeper import Model
from rangekeeper.execution.rule import RuleResult
from rangekeeper.market import Market
from rangekeeper.model import Distribution, Value
from rangekeeper.model.system import Hierarchy, View
from rangekeeper.model.system.table import ValueColumn, to_table
from rangekeeper.shared.table import Table


def consume(model: Model) -> Table:
    view = View(model)
    table = to_table(view, columns=(ValueColumn("Area", "net", "meter**2"),))
    tree = to_table(Hierarchy.from_relationships(view))
    return table


def consume_market(market: "Market", distribution: "Distribution") -> "Value":
    """Named Market access and calculations share the generated public record types."""
    distribution.check()
    value: Value = market.space_market_price_factors
    rates: Value = market.implied_reversion_cap_rates
    result: RuleResult = RuleResult(())
    return value
