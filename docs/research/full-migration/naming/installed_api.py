"""Check the installed public vocabulary and lightweight record imports."""
import importlib.util
import json
import sys
import rangekeeper
from rangekeeper.model.distribution import Distribution
from rangekeeper._schema.records import Distribution as Generated, Binding, RandomStream
from rangekeeper.scenarios import Market, market
from rangekeeper.policies import DecisionHistory, build_stop_gain_resale_policy

assert Distribution is Generated
assert importlib.util.find_spec('rangekeeper.scenarios.result') is None
for name in ('DistributionParameters', 'NamedValue', 'ComponentStream', 'ScenarioResult', 'PolicyState'):
    from rangekeeper._schema import records
    assert not hasattr(records, name)
assert all(hasattr(Market, name) for name in (
    'space_market_price_factors', 'asset_true_value', 'implied_reversion_cap_rates',
    'cumulative_volatility', 'autoregressive_returns', 'noise', 'black_swan'))
assert not {'scipy', 'numpy', 'pyomo', 'pandas', 'polars', 'linkml', 'rangekeeper.flux',
            'rangekeeper.dynamics', 'rangekeeper.policy'} & set(sys.modules)
print(json.dumps({'rk':rangekeeper.__file__, 'record':Distribution.__module__,
                  'market':Market.__module__, 'lightweight': True}))
