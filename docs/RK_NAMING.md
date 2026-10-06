# RK naming

Prefer one clear noun for a type and one clear verb for an operation. Use a
qualified name when one word would lose domain meaning. Put an invariant on its
owner; keep cross-record and IO operations at their explicit boundary.

## Records and views

| Name | Responsibility |
|---|---|
| Model | Canonical immutable content and provenance |
| Market | Read-only, typed access to a recorded market within one Model revision |
| ScenarioPlan | Complete generation inputs, method, periods and seed |
| ScenarioParameter | Named fixed quantity or distribution input |
| ScenarioRealization | Captured inputs and outputs, random identities and availability |
| Distribution | One LinkML-generated probability-distribution record |
| Binding | A local name referring to a canonical Value; the container defines scope |
| RandomStream | Recorded identity of a random sequence, separate from a Flow Stream |
| DecisionHistory | Earlier decisions supplied to the next policy decision |

`schema/distribution.yaml` and `schema/binding.yaml` contain reusable contracts.
`schema/scenario.yaml` imports them. A Formulation and a realization use the same
Binding record; each container validates local uniqueness and target resolution.
No generated field schema is repeated in a handwritten distribution class.

Generated records inherit field-free behaviour from the explicit generator bridge.
`Distribution.uniform`, `triangular`, `pert` and `symmetric` construct parameters;
`check` validates their meaning. Instance methods `sample`, `cdf` and `mass` own
probability calculations. CDF means cumulative distribution function. Samples use
the record's units; probabilities are dimensionless. Sampling advances only the
supplied NumPy generator. Nested decoding returns the same class and methods.
See [record ownership and contracts](RECORD_BOUNDARY.md).

## Composable authoring

`scenarios.market` exposes `make_plan`, `make_trend`, `make_volatility`,
`make_cyclicality`, `make_noise`, `make_black_swan`, `sample`, `capture`, `realize`
and `generate`. Component constructors return tuples of generated
ScenarioParameter records. They do not sample or create output Flows. Duplicate
explicit parameters across components or the parameter mapping fail.

```python
from rangekeeper.scenarios import market

plan = market.make_plan(periods=periods, seed=23, components=(
    market.make_trend(growth_rate=.02),
    market.make_volatility(volatility_per_period=.03),
    market.make_cyclicality(space_amplitude=.25),
    market.make_noise(lower=-.02, upper=.02),
    market.make_black_swan(likelihood=.02, impact=-.25),
))
markets = market.generate(model, plan, scenario_keys=("base",))
pricing_value = markets[0].space_market_price_factors
pricing_flow = pricing_value.flow
```

`Market` stores only its Model and selected realization. Named properties resolve
canonical Values; they do not own copied Flow content or calculate on access.
Missing components raise KeyError, including components not provided by an
independent-path method. Captured inputs without realized outputs cannot be
presented as a Market. Selecting evidence from a different revision fails.

## Quantities retain their meaning

| Earlier public name | Current name |
|---|---|
| pricing_factor | space_market_price_factors |
| true_value | asset_true_value |
| implied_cap_rate | implied_reversion_cap_rates |
| input volatility | volatility_per_period |
| output volatility | cumulative_volatility |
| output autoregression | autoregressive_returns |

The autoregression coefficient is still an input named `autoregression`.
Cumulative volatility is a rental level after accumulation and mean reversion,
not a return increment. Space-cycle variation is centred on zero; its multiplier
is `1 + space_cycle`. The legacy `space_waveform` already included that one, so it
is not a synonym. Amplitude remains half the peak-to-trough height. No formula,
Flow semantic kind, or implicit assignment is introduced by these names.

Black Swan is the walkthrough name for the once-per-scenario shock recipe. The
general numerical function remains `calculate_shock`. `make_noise` declares the
current method's uniform bounds; it does not claim support for arbitrary deal-noise
distributions. Linked cycle estimates remain available through
`market.estimates.v2` and explicit plan parameters.

`Policy`, `Rule`, `condition`, `Action`, and `Decision` retain their meanings.
`build_stop_gain_resale_policy` names the supported resale rule. Observation
records remain separate from DecisionHistory. Policy evaluation has no authority
to infer missing observations or claim numerical feasibility.


## Runtime services

`Executor` traverses batches; `Plan` resolves their graph; `Attempt` owns one scalar
execution. Run `Tree` and `Publication` validators have separate scopes. Layout
`Formulation` owns symbolic geometry. The viewer uses `Viewer` for mutable display
state; C# `Validator.Check` overloads distinguish structural and Model checks.
Prefer composition between these services to inheritance with hidden state.
