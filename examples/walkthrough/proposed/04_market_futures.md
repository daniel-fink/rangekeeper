# Lesson 04: Many market futures (proposed cells)

Issue: [#206](https://github.com/daniel-fink/rangekeeper/issues/206). Plan:
[ADR-020 §04](../../../docs/decisions/020-walkthrough-plan-v2.md#04-many-market-futures)
and [ADR-014](../../../docs/decisions/014-market-paths.md).
API conventions and the gap list: [README](README.md).

## Goals box

> **Question.** How does the same plan perform across many possible market
> histories?
>
> **You will learn to:**
>
> 1. tell named cases from generated market paths;
> 2. build one path from trend, cycle, volatility, noise and shock components;
> 3. generate and capture market paths with a seed, and replay them;
> 4. run the plan across the paths, and read the distribution of NPV and funding
>    shortfall;
> 5. explain why the plan valued on average inputs differs from the average of its
>    results.
>
> **Before you start.** Lesson 03.
>
> **Time.** 60 minutes core, 30 minutes optional (correlated use markets).
>
> **Not in this lesson.** Decisions that react to the market (lesson 05).
>
> **Source.** Figure 7.2 in de Neufville and Geltner (2018), used with the
> publisher's permission and with attribution. Chapter 7 is cited for the market
> model.

## 1. The plan from lesson 03

Narrative: this lesson starts from lesson 03's Model, saved as a document in the
data package. Show its equations so that nothing is hidden.

```python
# cell 1
from datetime import date

import rangekeeper as rk
import helpers
```

```python
# cell 2
model = rk.io.load(path=helpers.data_path(name="03_base_plan.model.json"))
model.equations  # the equations from lesson 03
```

## 2. One market driver

Narrative: lesson 03 grew rents at a fixed rate in each case. Here, one property-wide
rent index carries the market, trend included. Add the index as a driver Flow and use
it in the income equation.

```python
# cell 3
yearly = rk.duration.Frequency.YEAR
years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=yearly
)
draft = model.edit()
site = draft.entity(code="property")
site.flow(key="rent_index", units="ratio", periods=years)
site.replace(key="income", equation="income = rent_index * (a_rent + b_rent)")
```

Narrative: lesson 03's rents compound at `rent_growth`. Now the index carries all
growth, so each rent is flat at today's income, and the Model has no rent growth to
apply. The Model cannot count growth twice, so no Specification has to remember to
set a rate to zero.

```python
# cell 3b
site.replace(
    key="a_rent",
    equation="a_rent = rk.profile.constant(initial=a_income, start=a_open)",
)
site.replace(
    key="b_rent",
    equation="b_rent = rk.profile.constant(initial=b_income, start=b_open)",
)
site.remove(key="rent_growth")
model = draft.commit()
```

Narrative: lesson 03's Specification fixed a rent growth rate. This Model has no
rent growth, so free that value before you move the Specification to the new
revision. `on` refuses a fixed value that the new revision does not declare.

```python
# cell 4
base = rk.io.load(path=helpers.data_path(name="03_base_case.specification.json"))
base = base.free("rent_growth").on(model=model)
base.roles  # lesson 03's plan, assumptions, debt and funding, by name
```

> **Finance note.** Market growth applied twice is a common error. If the index
> already grows 2 % a year, a 2 % rent growth on top of it gives 4 %. Put the growth
> in one place: here, the index.

## 3. A path, one component at a time

Narrative: a path generator makes market paths from parameters. Start with a trend
only. Then add a cycle, then volatility and noise, then a rare shock. After each
step, **predict** the shape and then draw it.

```python
# cell 5
trend = rk.market.Dynamics(trend="2 % pa")
helpers.plot_paths(paths=trend.generate(periods=years, count=1), names=["rent_index"])
```

```python
# cell 6
cycle = trend.replace(cycle_period="10 years", cycle_amplitude="10 %")
helpers.plot_paths(paths=cycle.generate(periods=years, count=1), names=["rent_index"])
```

Narrative: a trend and a cycle are fixed shapes. Volatility, noise and shocks are
random, so from here each path is random. A **seed** makes random paths repeatable:
the same seed and parameters give the same paths. The seed is a label for one set of
random numbers; it is not a date. `generate` refuses random dynamics without a seed.

```python
# cell 7
dynamics = cycle.replace(
    volatility="5 % pa", noise="2 %", shock_probability="2 % pa", shock_size="-25 %"
)
helpers.plot_paths(
    paths=dynamics.generate(periods=years, seed=1, count=5), names=["rent_index"]
)
```

> **Finance note.** Real-estate markets cycle, revert to a trend and suffer rare
> shocks. Figure 7.2 shows these components for one path.

## 4. Generate and capture

Narrative: generate many paths with one seed. The result is an `rk.market.Paths`
document. Its capture record keeps the generator, its parameters, the seed and the
library versions. Replay uses the captured values and draws no new random numbers.

```python
# cell 8
count = helpers.path_count(default=500)  # RK_PATH_COUNT: 4 in CI, full locally
paths = dynamics.generate(periods=years, seed=1, count=count)
paths.capture  # generator, parameters, seed, versions
```

```python
# cell 9
rk.io.save(document=paths, path="paths/04_rent_index.json")
assert rk.io.load(path="paths/04_rent_index.json") == paths
assert dynamics.generate(periods=years, seed=1, count=count) == paths
```

## 5. The plan on average inputs

Narrative. **Predict:** is the NPV on the average path the same as the average NPV
across paths? First, value the plan on the average rent index.

```python
# cell 10
average_outcome = rk.execution.solve(
    specification=base.fix(rent_index=paths.mean(name="rent_index"))
)
average_outcome["unlevered_npv"], average_outcome["equity_npv"]
```

## 6. The plan across all paths

Narrative: `across` makes one case for each path. A path is a set of named series.
In each case, `across` fixes each Model value from the series with the same name:
here, `rent_index`. One solve gives one result for each path.

```python
# cell 11
paths_outcome = rk.execution.solve(specification=base.across(paths=paths))
paths_outcome.table("unlevered_npv", "equity_npv", "peak_shortfall").head()
```

```python
# cell 12
npv = paths_outcome.distribution(key="unlevered_npv")
npv.summary()  # mean, standard deviation, 5 % and 95 % quantiles
```

```python
# cell 13
helpers.plot_target_curve(
    outcomes=paths_outcome,
    key="unlevered_npv",
    markers={"Average path": average_outcome["unlevered_npv"]},
)
```

## 7. The flaw of averages

Narrative: the average of the results differs from the result on the average path.
Leverage and the funding limit are not linear in the market, so the difference is
larger for equity and for funding.

```python
# cell 14
rk.execution.table(
    outcomes={"Average path": average_outcome, "Mean of paths": paths_outcome.mean()},
    keys=["unlevered_npv", "equity_npv", "peak_shortfall"],
)
```

> **Finance note.** A plan that looks good on the average path can fail on many paths.
> Read the downside: the 5 % quantile (value at risk) and the share of paths with a
> funding shortfall.

## 8. Downside and funding

Narrative: read the probability of a loss and of a funding shortfall.

```python
# cell 15
shortfall = paths_outcome.distribution(key="peak_shortfall")
npv.probability(below="0 AUD"), shortfall.probability(above="0 AUD")
```

```python
# cell 16
worst = npv.case(quantile=0.05)  # the path at the 5 % quantile of the NPV
helpers.plot_flows(
    outcome=worst, keys=["equity_available", "loan_available", "committed"]
)
```

## 9. Optional: correlated use markets

Narrative: hotel, residential and retail markets move together, but not exactly.
A correlated generator gives one index for each use. The Model uses each index in
the income of its use.

```python
# cell 17
uses = rk.market.Dynamics.correlated(
    generators={
        "hotel_index": dynamics.replace(volatility="8 % pa"),
        "residential_index": dynamics,
        "retail_index": dynamics.replace(trend="1 % pa"),
    },
    correlation={
        "hotel_index": {"residential_index": 0.5, "retail_index": 0.3},
        "residential_index": {"retail_index": 0.4},
    },
)
use_paths = uses.generate(periods=years, seed=1, count=count)
```

```python
# cell 18
helpers.plot_paths(
    paths=use_paths, names=["hotel_index", "residential_index", "retail_index"], count=3
)
use_paths.correlation()  # sample correlation of the period changes
```

## Exercises

**Try it 1: more volatility.** Double the volatility. How does the 5 % quantile of
the NPV change? How does the mean change?

```python
# solution
volatile = dynamics.replace(volatility="10 % pa").generate(
    periods=years, seed=1, count=count
)
volatile_outcome = rk.execution.solve(specification=base.across(paths=volatile))
volatile_npv = volatile_outcome.distribution(key="unlevered_npv")
assert volatile_npv.quantile(level=0.05) < npv.quantile(level=0.05)
```

**Try it 2: growth applied twice.** In a draft, make Building A's rent compound at
2 % pa again, as in lesson 03, on top of the index. How much does the mean NPV rise?
Why is this wrong?

```python
# solution
draft = model.edit()
site = draft.entity(code="property")
site.replace(
    key="a_rent",
    equation="a_rent = rk.profile.compounding(initial=a_income, rate=2 % pa, start=a_open)",
)
twice_model = draft.commit()
twice_outcome = rk.execution.solve(
    specification=base.on(model=twice_model).across(paths=paths)
)
twice_outcome.distribution(key="unlevered_npv").mean - npv.mean
```

The mean NPV rises, but the market did not change. The index already contains the
trend, so Building A's rent now grows twice.

**Try it 3: another seed.** Regenerate the paths with seed 2. How much does
the mean NPV move? What does this say about the path count?

```python
# solution
other = paths.regenerate(seed=2)  # the same generator, periods and count
reseeded_outcome = rk.execution.solve(specification=base.across(paths=other))
reseeded_outcome.distribution(key="unlevered_npv").mean - npv.mean
```

## Checks and recap

```python
# cell 19 (checks)
assert len(paths_outcome.cases) == count
assert paths_outcome.run.market_paths == paths.id  # the Run pins the paths
assert npv.mean != average_outcome["unlevered_npv"]  # the flaw of averages
first = paths.keys[0]
assert paths_outcome.case(key=first)["rent_index"] == paths[first]["rent_index"]
```

**Recap.**

1. A case is a named set of assumptions. A market path is one generated history.
   Both enter a batch Specification the same way: as fixed values.
2. Market paths are captured inputs: a seed and parameters give the same paths, and
   the Run pins them.
3. The result on the average path is not the average result. Read the distribution,
   and above all its downside.

**Next.** Lesson 05 lets decisions react to the market path, using only what is
known at each date.

## Cell budget

17 core code cells, 2 optional cells and 1 check cell (budget 20–25), 3 exercise
solutions. The longest cell has 13 lines (cell 17). Cells follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2 | 1, 10 | G26: `rk.io.load` and `rk.io.save` for any document kind; `model.equations` display ([G10](README.md#gap-list)) |
| 3–3b | 2, 3 | G27: equation keys, entity `replace(key=, equation=)` and `remove(key=)`; G28: entity `flow(key=, units=, periods=)` |
| 4 | 2, 5 | G21: `free` then `on(model=)`; `on` refuses a fixed value that the new revision does not declare |
| 5–7 | 6, 11 | `rk.market.Dynamics` ([#135](https://github.com/daniel-fink/rangekeeper/issues/135), [#136](https://github.com/daniel-fink/rangekeeper/issues/136)). G29: generator parameters as Quantity strings, `replace(...)`; `generate` needs `seed=` only when the dynamics are random |
| 5–7, 13, 16, 18 | 10 | Helpers draw only |
| 8–9 | 4, 6 | `rk.market.Paths` and its capture ([#137](https://github.com/daniel-fink/rangekeeper/issues/137)); G26; value equality of documents (G06) |
| 10 | 6 | G30: `Paths.mean(name)` gives one Flow |
| 11 | 8 | `across` ([#138](https://github.com/daniel-fink/rangekeeper/issues/138)). G73: path series match Model values by key |
| 12–15 | 8 | G31: `Outcome.distribution(key)` with `summary`, `mean`, `quantile(level=)`, `probability`, `case(quantile=)` |
| 14 | 8 | G13; G31: `Outcome.mean()` gives the mean of a batch as one row for `rk.execution.table` |
| 16 | 8 | G31: `Distribution.case(quantile=)` returns the case at a quantile |
| 17–18 | 6 | G32: correlated generators with correlations by name, and `Paths.correlation()` |
| 19 | 8 | G33: `Outcome.run.market_paths` pin; `Paths[key][name]`; G69: `Paths.regenerate(seed=)` (Try it 3) |
| — | — | Run time across 500 paths needs the reusable worker ([#130](https://github.com/daniel-fink/rangekeeper/issues/130)) and one structure for all cases (G20) |
