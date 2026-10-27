# Lesson 03: Cases, debt and equity (proposed cells)

Issue: [#205](https://github.com/daniel-fink/rangekeeper/issues/205). Plan:
[ADR-020 §03](../../../docs/decisions/020-walkthrough-plan-v2.md#03-cases-debt-and-equity).
API conventions and the gap list: [README](README.md).

Decisions used here (recorded in the [README](README.md#decisions)): the cases
reach the cash flows through the solve (D1); `irr`, `min` and `max` are evaluated
after the affine stage, and a fixed IRR becomes an affine row (D4); funding is
composed from `cumulative()`, with no account object (D2).

## Goals box

> **Question.** How does the base plan perform in weak, reference and strong markets,
> with and without debt? Can we pay the bills when they fall due?
>
> **You will learn to:**
>
> 1. build dated cash flows from a base plan, and tell the base plan from the base case;
> 2. declare named market cases and solve them in one batch;
> 3. report unlevered NPV, equity NPV and equity IRR for each case, and compare
>    leverage levels;
> 4. find the land price that gives a target equity IRR;
> 5. test construction funding: cash balance, headroom and the commitment gap.
>
> **Before you start.** Lessons 01 and 02.
>
> **Time.** 60 minutes core, 25 minutes optional (more leverage levels, the Run as
> evidence).
>
> **Not in this lesson.** Many market futures (lesson 04). Changing the plan's dates
> by rule (lesson 05).
>
> **Source.** Table 4.1 in de Neufville and Geltner (2018), used with the
> publisher's permission and with attribution. The numbers are the property's own.

## 1. The base plan

Narrative: the base plan says what is built and when. Shared works in 2027, Building
A in 2028–2029 and Building B in 2030–2031. Each building opens the next January.
The base case is the financial result of that plan under stated reference
assumptions. The plan does not change in this lesson; the assumptions do.

```python
# cell 1
from datetime import date

import rangekeeper as rk
import helpers
```

```python
# cell 2
plan = helpers.load_base_plan()
plan  # dates, budgets, incomes and funding, with origins
```

```python
# cell 3
helpers.show_timeline(plan=plan)
yearly = rk.duration.Frequency.YEAR
years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=yearly
)
```

> **Finance note.** A development budget has hard costs (construction), soft costs
> (fees and approvals) and a contingency. Land is a separate line.

## 2. The budget, by hand once

Narrative: Building A's budget is its area by use times the construction rate, plus
10 % soft costs and 10 % contingency. Calculate it once by hand and compare it with
the plan's total. The other packages follow the same rule.

```python
# cell 4
areas = plan.areas["building_a"]
hard_costs = sum(areas[use] * plan.rates[use] for use in areas)
soft_costs = 0.10 * hard_costs
contingency = 0.10 * hard_costs
budget = hard_costs + soft_costs + contingency
assert rk.quantity.isclose(actual=budget, expected=plan["a_cost"])
```

## 3. The dated Model

Narrative: as in lesson 02, start an empty Model and edit it. Declare the inputs
with their units. Dates are values too, so a later lesson can change them.

```python
# cell 5
model = rk.Model(name="Mixed-use base plan")
draft = model.edit()
site = draft.add_entity(code="property", classification="property")
site.date(key="base_date")
site.date(key="sale_date")
site.date(key="start_date")
site.date(key="b_start")
```

Narrative: the amounts and rates. Incomes and operating costs are annual amounts
at 2027 prices; budgets and renewals are totals. The cases in section 5 change two of
the rates.

```python
# cell 5b
site.value(key="land_cost", units="AUD")
site.value(key="shared_cost", units="AUD")
site.value(key="a_cost", units="AUD")
site.value(key="b_cost", units="AUD")
site.value(key="a_income", units="AUD pa")
site.value(key="b_income", units="AUD pa")
site.value(key="a_opex", units="AUD pa")
site.value(key="b_opex", units="AUD pa")
site.value(key="a_renewal", units="AUD")
site.value(key="b_renewal", units="AUD")
site.value(key="rent_growth", units="% pa")
site.value(key="opex_growth", units="% pa")
site.value(key="exit_cap_rate", units="ratio")
site.value(key="discount_rate", units="% pa")
```

Narrative: some Flows are made from amounts, by a profile or an event. Nothing in
their equations says which Periods they cover, so declare them here, each with its
Periods. Every other value takes its units and Periods from its equation: a sum of
yearly Flows is yearly, and `commit()` names any value that it cannot work out.

```python
# cell 5c
site.flow(key="land", units="AUD", periods=years)
site.flow(key="shared_works", units="AUD", periods=years)
site.flow(key="a_works", units="AUD", periods=years)
site.flow(key="b_works", units="AUD", periods=years)
site.flow(key="a_rent", units="AUD", periods=years)
site.flow(key="b_rent", units="AUD", periods=years)
site.flow(key="a_costs", units="AUD", periods=years)
site.flow(key="b_costs", units="AUD", periods=years)
site.flow(key="a_renewals", units="AUD", periods=years)
site.flow(key="b_renewals", units="AUD", periods=years)
site.flow(key="sale", units="AUD", periods=years)
```

Narrative: equations can be grouped in named formulations, like the sections of a
pro forma: development, operations, sale and debt. A group changes nothing in the
solve; it organises the display and the trace.

The plan's sequence is a relation too. The site is bought and the shared works start
on the start date. Building A follows a year later, and each building
takes two years to build. Building B cannot start before the shared works finish.
Development payments are negative; `rk.profile.uniform` divides an amount evenly
over the years from a start date.

```python
# cell 6
site.equations(
    "shared_start = start_date",
    "a_start = shared_start + 1 year",
    "a_open = a_start + 2 years",
    "b_open = b_start + 2 years",
    "b_start >= shared_start + 1 year",
    "land = -rk.flow.event(amount=land_cost, on=start_date)",
    "shared_works = -rk.profile.uniform(total=shared_cost, start=shared_start, years=1)",
    "a_works = -rk.profile.uniform(total=a_cost, start=a_start, years=2)",
    "b_works = -rk.profile.uniform(total=b_cost, start=b_start, years=2)",
    "works = shared_works + a_works + b_works",
    formulation="Development",
)
```

Narrative: operations. Rents grow on one calendar from 2027, but each building
earns nothing until it opens. Renewals come every five years after opening.

```python
# cell 7
site.equations(
    "a_rent = rk.profile.compounding(initial=a_income, rate=rent_growth, start=a_open)",
    "b_rent = rk.profile.compounding(initial=b_income, rate=rent_growth, start=b_open)",
    "a_costs = rk.profile.compounding(initial=a_opex, rate=opex_growth, start=a_open)",
    "b_costs = rk.profile.compounding(initial=b_opex, rate=opex_growth, start=b_open)",
    "income = a_rent + b_rent",
    "opex = -(a_costs + b_costs)",
    formulation="Operations",
)
```

Narrative: renewals come every five years after each building opens, at costs that
grow from 2027.

```python
# cell 7b
site.equations(
    (
        "a_renewals = rk.profile.compounding(initial=a_renewal, rate=opex_growth,"
        " start=a_open + 5 years, every=5 years)"
    ),
    (
        "b_renewals = rk.profile.compounding(initial=b_renewal, rate=opex_growth,"
        " start=b_open + 5 years, every=5 years)"
    ),
    "renewals = -(a_renewals + b_renewals)",
    "operating = income + opex + renewals",
    formulation="Operations",
)
```

Narrative: the sale and the value. These are lesson 01's ideas, now as relations.

```python
# cell 8
site.equations(
    "exit_value = operating.at(on=sale_date + 1 year) / exit_cap_rate",
    "sale = rk.flow.event(amount=exit_value, on=sale_date)",
    "project_cash = land + works + operating + sale",
    "net_cash_flow = project_cash.trim(end=sale_date)",
    "unlevered_npv = rk.finance.npv(flow=net_cash_flow, rate=discount_rate, on=base_date)",
    formulation="Sale and value",
)
model = draft.commit()
```

## 4. The base case

Narrative. **Predict:** is the unlevered NPV positive at the reference assumptions?
Fix the plan's inputs and the reference assumptions. Everything else is free.

```python
# cell 9
base = (
    model.specify(name="Base case")
    .fix(base_date=plan["base_date"], sale_date=plan["sale_date"])
    .fix(start_date=plan["start_date"], b_start=plan["b_start"])
    .fix(land_cost=plan["land_cost"], shared_cost=plan["shared_cost"])
    .fix(a_cost=plan["a_cost"], b_cost=plan["b_cost"])
    .fix(a_income=plan["a_income"], b_income=plan["b_income"])
    .fix(a_opex=plan["a_opex"], b_opex=plan["b_opex"])
    .fix(a_renewal=plan["a_renewal"], b_renewal=plan["b_renewal"])
)
reference = {"rent_growth": "3 % pa", "exit_cap_rate": "5 %"}
base = base.fix(**reference).fix(discount_rate="7 % pa", opex_growth="3.5 % pa")
outcome = rk.execution.solve(specification=base)
outcome["unlevered_npv"]
```

```python
# cell 10
outcome.stream("land", "works", "income", "opex", "renewals", "sale").display()
helpers.plot_cash_flows(outcome=outcome, key="net_cash_flow")
```

## 5. Named cases

Narrative: a case is one named set of assumptions. A batch Specification holds the
cases; one solve gives one comparable table. Every case uses the same plan and the
same valuation conventions.

```python
# cell 11
cases = {
    "weak": {"rent_growth": "1 % pa", "exit_cap_rate": "6 %"},
    "reference": reference,
    "strong": {"rent_growth": "5 % pa", "exit_cap_rate": "4.5 %"},
}
outcomes = rk.execution.solve(specification=base.cases(cases=cases))
outcomes.table("unlevered_npv")
```


> **Under the hood.** `base.cases(...)` makes one batch Specification. Each case
> overrides the base's fixed values by key. The solve builds the shared affine
> structure once and solves each case.

## 6. Debt and equity

Narrative: a loan funds a fixed share of each development payment. The owner pays
interest each year and repays the balance from the sale. The equity investor's cash
flow is what remains. Add the relations to a new revision of the Model, then pin the
Specification to that revision.

```python
# cell 13
draft = model.edit()
site = draft.entity(code="property")
site.value(key="leverage", units="ratio")
site.value(key="loan_rate", units="% pa")
site.value(key="equity_rate", units="% pa")
site.equations(
    "loan_draws = -leverage * (land + works)",
    "loan_balance = loan_draws.cumulative()",
    "loan_interest = -rk.finance.interest(balance=loan_balance, rate=loan_rate)",
    "repayment = -rk.finance.settle(balance=loan_balance, on=sale_date)",
    formulation="Debt",
)
```

Narrative: the equity investor's cash flow is what remains after the loan.

```python
# cell 13b
site.equations(
    "equity_cash_flow = net_cash_flow + loan_draws + loan_interest + repayment",
    "equity_npv = rk.finance.npv(flow=equity_cash_flow, rate=equity_rate, on=base_date)",
    "equity_irr = rk.finance.irr(flow=equity_cash_flow)",
    formulation="Debt",
)
model = draft.commit()
```

```python
# cell 14
levered = base.on(model=model).fix(
    leverage="65 %", loan_rate="6 % pa", equity_rate="12 % pa"
)
levered_outcomes = rk.execution.solve(specification=levered.cases(cases=cases))
levered_outcomes.table("unlevered_npv", "equity_npv", "equity_irr")
```

> **Finance note.** Debt makes the equity's results larger in both directions. When
> the property earns more than the loan rate, leverage raises the equity IRR. IRR has
> failure cases: a cash flow with more than one change of sign can have more than one
> IRR, and the solve then reports `irr_not_unique`.

## 7. Leverage levels

Narrative. **Predict:** in the reference case, does the equity NPV rise with
leverage? Compare three levels in one batch.

```python
# cell 15
levels = {
    "no debt": {"leverage": 0},
    "50 %": {"leverage": "50 %"},
    "65 %": {"leverage": "65 %"},
}
rk.execution.solve(specification=levered.cases(cases=levels)).table(
    "equity_npv", "equity_irr"
)
```

## 8. A target equity IRR

Narrative: the back door again, now on dated cash flows. The investor needs a 15 %
equity IRR. What land price gives it? Fix the IRR and free the land cost. With the
IRR fixed, the IRR relation becomes "NPV at 15 % is zero", which is an affine row.

```python
# cell 16
target = levered.fix(equity_irr="15 % pa").free("land_cost")
target_outcome = rk.execution.solve(specification=target)
target_outcome["land_cost"]
```

## 9. Can we pay the bills? By hand once

Narrative: a positive NPV does not pay a construction invoice. The owner has 50
million AUD of equity and a bridge facility of 65 million AUD. Payments come at the
end of each year. Calculate the first year's closing balance and headroom by hand.

```python
# cell 17
paid_2027 = outcome["land"].at(on=date(2027, 1, 1)) + outcome["works"].at(
    on=date(2027, 1, 1)
)
closing_2027 = plan["equity"] + paid_2027
headroom_2027 = closing_2027 + plan["bridge_limit"]
closing_2027, headroom_2027
```

Narrative: now every year at once. The closing balance is the equity plus the
running total of the payments; the opening balance is the closing balance less that
year's payments. This is the spreadsheet corkscrew, built from one Flow method,
`cumulative()`, which the loan already used.

```python
# cell 18
payments = outcome["land"] + outcome["works"]
closing = plan["equity"] + payments.cumulative()
opening = closing - payments
headroom = closing + plan["bridge_limit"]
assert closing.at(on=date(2027, 1, 1)) == closing_2027
rk.flow.Stream(
    flows={
        "Opening": opening,
        "Payments": payments,
        "Closing": closing,
        "Headroom": headroom,
    }
).display()
```

## 10. Funding in the Model

Narrative: the same relations in the Model, so that every case and every later
lesson reports them. Building A's income helps to pay for Building B, so the cash
includes the operating cash flow. They form one named group, "Funding". There is no
account object: an account is equations.

```python
# cell 19
draft = model.edit()
site = draft.entity(code="property")
site.value(key="equity", units="AUD")
site.value(key="bridge_limit", units="AUD")
site.equations(
    "cash = equity + (land + works + operating).cumulative()",
    "opening_cash = cash - (land + works + operating)",
    "headroom = cash + bridge_limit",
    "peak_shortfall = max(0 AUD, -headroom.min())",
    formulation="Funding",
)
```

Narrative: a package's remaining payments become committed when it starts. What is
still to be paid is the running total less the whole total; `since` makes it zero
before the start date. The commitment gap is the largest amount by which committed
but unpaid payments exceed the headroom.

```python
# cell 19b
site.equations(
    "shared_unpaid = shared_works.cumulative() - shared_works.total()",
    "a_unpaid = a_works.cumulative() - a_works.total()",
    "b_unpaid = b_works.cumulative() - b_works.total()",
    "committed = shared_unpaid.since(on=shared_start) + a_unpaid.since(on=a_start)"
    " + b_unpaid.since(on=b_start)",
    "commitment_gap = max(0 AUD, (committed - headroom).max())",
    formulation="Funding",
)
model = draft.commit()
```

```python
# cell 20
funded = levered.on(model=model).fix(
    equity=plan["equity"], bridge_limit=plan["bridge_limit"]
)
summary = rk.execution.solve(specification=funded.cases(cases=cases))
summary.table(
    "unlevered_npv", "equity_npv", "equity_irr", "peak_shortfall", "commitment_gap"
)
```

```python
# cell 21
helpers.plot_flows(
    outcome=summary.case(key="weak"), keys=["cash", "headroom", "committed"]
)
```

> **Finance note.** The commitment gap uses only cash and facilities that exist at
> each date. It assumes no future sale or refinance. When Building B starts, its
> whole budget is committed, even though the payments come over two years.

## 11. Optional, under the hood: the Run as evidence

Narrative: `solve` keeps everything in memory. `execute` also publishes the outputs
and a Run to a store. A Run records the Specification, the Model revision, the
solver, the status and every case. Replay reads it in a fresh kernel and checks
that the result is the same. A namespace gives the same IDs on every build.

```python
# cell 22
store = rk.io.DirectoryStore(path="runs/03")
executed = rk.execution.execute(specification=funded.cases(cases=cases), store=store)
executed.run.id
```

```python
# cell 23 (new kernel)
store = rk.io.DirectoryStore(path="runs/03")
run = store.find_runs(specification="Base case")[-1]
rk.execution.replay(run=run, store=store).raise_for_status()
```

> **Under the hood: the same IDs on every build.** Pass a namespace to `rk.Model`.
> The same inputs then give the same Model ID and record IDs in every kernel
> ([#147](https://github.com/daniel-fink/rangekeeper/issues/147)):
>
> ```python
> ns = rk.model.namespace(name="rangekeeper-walkthrough/03")
> model = rk.Model(name="Mixed-use base plan", namespace=ns)
> ```

## Exercises

**Try it 1: a stress case.** Add a case with no rent growth and a 7 % exit cap rate.
Does the commitment gap change? Which cash flow causes the change?

```python
# solution
with_stress = {**cases, "stress": {"rent_growth": "0 % pa", "exit_cap_rate": "7 %"}}
stress = rk.execution.solve(specification=funded.cases(cases=with_stress))
gap = {key: stress.case(key=key)["commitment_gap"] for key in ("stress", "reference")}
assert gap["stress"] >= gap["reference"]
# Building A's lower income pays less of Building B's works.
# The exit cap rate has no effect.
```

**Try it 2: the target IRR in the weak case.** What land price gives a 15 % equity
IRR in the weak market?

```python
# solution
weak_target = target.fix(**cases["weak"])
assert (
    rk.execution.solve(specification=weak_target)["land_cost"]
    < target_outcome["land_cost"]
)
```

**Try it 3: start Building B a year later.** Which year has the least headroom now?

```python
# solution
later = rk.execution.solve(specification=funded.fix(b_start=date(2031, 1, 1)))
later["headroom"].argmin()
```

## Checks and recap

```python
# cell 24 (checks)
npvs = outcomes.table("unlevered_npv")["unlevered_npv"]
assert npvs.is_sorted()  # weak < reference < strong
cash = target_outcome["equity_cash_flow"]
target_npv = rk.finance.npv(flow=cash, rate="15 % pa", on=date(2027, 1, 1))
assert rk.quantity.isclose(actual=target_npv, expected="0 AUD", abs="1 AUD")
reference = summary.case(key="reference")
assert reference["headroom"].at(on=date(2027, 1, 1)) == headroom_2027
```

**Recap.**

1. The base plan is the dates; the base case is its result under reference
   assumptions. Cases change assumptions, not the plan.
2. One batch Specification gives one comparable table: unlevered and levered results,
   and the funding test, for every case.
3. A fixed equity IRR is a question like any other: the back door works on dated cash
   flows too.

**Next.** Lesson 04 replaces three named cases with many generated market paths.

## Cell budget

25 core code cells, 2 optional cells (section 11, one in a new kernel) and 1 check cell
(budget 20–25), 3 exercise solutions. The longest cell has 15 lines (cells 5b and 9). Cells
follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2–3 | 10 | G07: `load_base_plan`, `show_timeline` load and draw only |
| 4 | 6 | By hand once; the budget then lives in the plan's inputs |
| 5–5c | 2, 5 | G08 (entity handles); G15: date-valued Values; G16: Flows made from amounts declare their Periods, other values take units and shape from their equations |
| 6–8 | 3, 6 | G72: `formulation=` groups; G17: functions in equations (`rk.flow.event`, `rk.profile.uniform`, `rk.profile.compounding`, `rk.finance.npv`, and the methods `at` and `trim`); G18: Flow-valued string equations; date arithmetic in G15 |
| 7 | 6 | `compounding` with `base`, `start` and `every`: the Compounding profile in an equation (G70, [#168](https://github.com/daniel-fink/rangekeeper/issues/168)) |
| 9 | 2, 8 | G11, G12 |
| 10 | 8 | G19: `Outcome.stream` and Flow values in `Outcome` |
| 11, 14 | 8 | Cases ([#144](https://github.com/daniel-fink/rangekeeper/issues/144)). G20: `cases(mapping)` overrides by key; `Outcome.case`, `Outcome.table` with a case column |
| 13 | 3, 6 | G17 (`cumulative()`, `rk.finance.interest`, `rk.finance.settle`, `rk.finance.irr`); G09: `irr` is evaluated after the affine stage |
| 14 | 2 | G21: `Specification.on(model)` pins a new revision and keeps roles by key |
| 16 | 6, 8 | G22: a fixed `irr` becomes an affine NPV row |
| 17 | 6 | By hand once |
| 18 | 6 | `cumulative()` (G05); the corkscrew is composition, with no account class (D2) |
| 19–19b | 2, 3, 6 | G05: `total()`, `cumulative()`, `since(on=)`, `min()`, `max()`; G09 evaluates `min` and `max` after the affine stage |
| 21 | 10 | Helper draws named Flows only (`plot_flows`) |
| 22–23 | 1, 4 | `execute` ([#126](https://github.com/daniel-fink/rangekeeper/issues/126)); G25: `rk.execution.replay` and `store.find_runs(specification=name)` |
| 24 | 5, 8 | G06 |

## Open choices for review

- **Unit inference (G16).** Lesson 02 declares every value. From lesson 03, only
  inputs are declared. The alternative is to declare every Flow, which adds about
  15 lines to cells 6–8.
- **Funding structure.** The cells use equity plus an overdraft-style bridge limit.
  `development.json` also has a fixed draw schedule. Authoring picks one; the API is
  the same.
