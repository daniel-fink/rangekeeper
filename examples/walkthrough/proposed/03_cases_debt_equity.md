# Lesson 03: Cases, debt and equity (proposed cells)

Issue: [#205](https://github.com/daniel-fink/rangekeeper/issues/205). Plan:
[ADR-020 §03](../../../docs/decisions/020-walkthrough-plan-v2.md#03-cases-debt-and-equity).
API conventions and the gap list: [README](README.md).

Decisions used here (recorded in the [README](README.md#decisions)): the cases
reach the cash flows through the solve (D1); `irr`, `min` and `max` are evaluated
after the affine stage, and a fixed IRR becomes an affine row (D4); funding is an
equity-first cascade composed from `cumulative()`, `diff()` and `max`, with no
account object (D2).

## Goals box

> **Question.** How does the base plan perform in weak, reference and strong markets,
> with and without debt? Can we pay the bills when they fall due?
>
> **You will learn to:**
>
> 1. build dated cash flows from a base plan, and tell the base plan from the base case;
> 2. declare named market cases and solve them in one batch;
> 3. fund the plan with equity first, then a loan, and report unlevered NPV, equity
>    NPV and equity IRR for each case and equity level;
> 4. find the land price that gives a target equity IRR;
> 5. test construction funding: the loan principal, what is left to spend and the
>    shortfall.
>
> **Before you start.** Lessons 01 and 02.
>
> **Time.** 60 minutes core, 25 minutes optional (more equity levels, the Run as
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
helpers.show_timeline(of=plan)
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
hard_costs = rk.Quantity(text="0 AUD")
for use in areas:
    hard_costs = hard_costs + areas[use] * plan.rates[use]
soft_costs = 0.10 * hard_costs
contingency = 0.10 * hard_costs
budget = hard_costs + soft_costs + contingency
assert rk.quantity.isclose(actual=budget, expected=plan["a_cost"])
```

## 3. The dated Model

Narrative: as in lesson 02, start an empty Model and edit it. Declare the inputs
with their units. Dates are values too, so a later lesson can change them. The
plan's sequence relates them: the shared works start on the start date, Building A
follows a year later, each building takes two years to build, and Building B cannot
start before the shared works finish. Group equations in named formulations, like
the sections of a pro forma: `add_formulation(name=)` makes one, and its
`equations(...)` adds to it. A formulation changes nothing in the solve; it organises
the display and the trace. The date equations form "Dates".

```python
# cell 5
model = rk.Model(name="Mixed-use base plan")
draft = model.edit()
project = draft.add_entity(code="project", classification="project")
project.date(key="base_date")
project.date(key="sale_date")
project.date(key="start_date")
project.date(key="b_start")
dates = project.add_formulation(name="Dates")
dates.equations(
    "shared_start = start_date",
    "a_start = shared_start + 1 year",
    "a_open = a_start + 2 years",
    "b_open = b_start + 2 years",
    "b_start >= shared_start + 1 year",
)
```

Narrative: the amounts and rates. Incomes and operating costs are annual amounts
at 2027 prices; budgets and renewals are totals. The cases in section 5 change two of
the rates.

```python
# cell 5b
project.value(key="land_cost", units="AUD")
project.value(key="shared_cost", units="AUD")
project.value(key="a_cost", units="AUD")
project.value(key="b_cost", units="AUD")
project.value(key="a_income", units="AUD pa")
project.value(key="b_income", units="AUD pa")
project.value(key="a_opex", units="AUD pa")
project.value(key="b_opex", units="AUD pa")
project.value(key="a_renewal", units="AUD")
project.value(key="b_renewal", units="AUD")
project.value(key="rent_growth", units="% pa")
project.value(key="opex_growth", units="% pa")
project.value(key="exit_cap_rate", units="ratio")
project.value(key="discount_rate", units="% pa")
```

Narrative: some Flows are made from amounts, by a profile or an event. Nothing in
their equations says which Periods they cover, so declare them here, each with its
Periods. Every other value takes its units and Periods from its equation: a sum of
yearly Flows is yearly, and `commit()` names any value that it cannot work out.

```python
# cell 5c
project.flow(key="land", units="AUD", periods=years)
project.flow(key="shared_works", units="AUD", periods=years)
project.flow(key="a_works", units="AUD", periods=years)
project.flow(key="b_works", units="AUD", periods=years)
project.flow(key="a_rent", units="AUD", periods=years)
project.flow(key="b_rent", units="AUD", periods=years)
project.flow(key="a_costs", units="AUD", periods=years)
project.flow(key="b_costs", units="AUD", periods=years)
project.flow(key="a_renewals", units="AUD", periods=years)
project.flow(key="b_renewals", units="AUD", periods=years)
project.flow(key="sale", units="AUD", periods=years)
```

Narrative: development, the next group. The site is bought on the start date.
Development payments are negative; `rx.profile.uniform` divides an amount evenly
over the years from a start date. In lesson 01, `rk.` functions calculated a result
at once. In an equation, functions start with `rx.`: they write a relation that the
solve uses.

```python
# cell 6
development = project.add_formulation(name="Development")
development.equations(
    "land = -rx.flow.event(amount=land_cost, on=start_date)",
    "shared_works = -rx.profile.uniform(total=shared_cost, start=shared_start, length=1 year)",
    "a_works = -rx.profile.uniform(total=a_cost, start=a_start, length=2 years)",
    "b_works = -rx.profile.uniform(total=b_cost, start=b_start, length=2 years)",
    "works = shared_works + a_works + b_works",
)
```

Narrative: operations. Rents grow on one calendar from 2027, but each building
earns nothing until it opens. Renewals come every five years after opening.

```python
# cell 7
operations = project.add_formulation(name="Operations")
operations.equations(
    "a_rent = rx.profile.compounding(initial=a_income, rate=rent_growth, start=a_open)",
    "b_rent = rx.profile.compounding(initial=b_income, rate=rent_growth, start=b_open)",
    "a_costs = rx.profile.compounding(initial=a_opex, rate=opex_growth, start=a_open)",
    "b_costs = rx.profile.compounding(initial=b_opex, rate=opex_growth, start=b_open)",
    "income = a_rent + b_rent",
    "opex = -(a_costs + b_costs)",
)
```

Narrative: renewals come every five years after each building opens, at costs that
grow from 2027.

```python
# cell 7b
operations.equations(
    (
        "a_renewals = rx.profile.compounding(initial=a_renewal, rate=opex_growth,"
        " start=a_open + 5 years, every=5 years)"
    ),
    (
        "b_renewals = rx.profile.compounding(initial=b_renewal, rate=opex_growth,"
        " start=b_open + 5 years, every=5 years)"
    ),
    "renewals = -(a_renewals + b_renewals)",
    "operating = income + opex + renewals",
)
```

Narrative: the sale and the value. These are lesson 01's ideas, now as equations.

```python
# cell 8
sale_and_value = project.add_formulation(name="Sale and value")
sale_and_value.equations(
    "exit_value = operating.at(on=sale_date + 1 year) / exit_cap_rate",
    "sale = rx.flow.event(amount=exit_value, on=sale_date)",
    "project_cash = land + works + operating + sale",
    "net_cash_flow = project_cash.until(on=sale_date)",
    "unlevered_npv = rx.finance.npv(flow=net_cash_flow, rate=discount_rate, on=base_date)",
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
base = base.fix(rent_growth="3 % pa", exit_cap_rate="5 %")
base = base.fix(discount_rate="7 % pa", opex_growth="3.5 % pa")
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
    "reference": {"rent_growth": "3 % pa", "exit_cap_rate": "5 %"},
    "strong": {"rent_growth": "5 % pa", "exit_cap_rate": "4.5 %"},
}
cases_outcome = rk.execution.solve(specification=base.cases(cases=cases))
cases_outcome.table("unlevered_npv")
```


> **Under the hood.** `base.cases(...)` makes one batch Specification. Each case
> overrides the base's fixed values by key. The solve builds the shared linear
> structure once and solves each case.

## 6. Debt and equity: equity first, then the loan

Narrative: the owner commits 50 million AUD of equity and pays it in as costs fall
due. Lenders usually require the equity to be spent first. When the equity is used
up, a construction loan pays the rest, up to its limit. Income and the sale repay the
loan first; the rest goes to equity. The funding need is the running total that the
project has not paid from its own cash; the loan principal is the part of it that the
equity cannot cover. `diff()` gives each period's change in a running total: the
reverse of `cumulative()`. Add the equations to a new revision of the Model.

```python
# cell 12
draft = model.edit()
project = draft.entity(code="project")
project.value(key="equity", units="AUD")
project.value(key="loan_limit", units="AUD")
project.value(key="loan_rate", units="% pa")
project.value(key="equity_rate", units="% pa")
funding = project.add_formulation(name="Funding")
funding.equations(
    "funding_need = -(net_cash_flow + loan_interest).cumulative()",
    "loan_principal = rx.max(0 AUD, funding_need - equity)",
    "loan_draws = loan_principal.diff()",
    "loan_interest = -rx.finance.interest(balance=loan_principal, rate=loan_rate)",
)
```

Narrative: equity receives whatever the project pays that does not go to or come from
the loan. Its cash flow is negative while it pays costs, zero while the loan pays,
and positive once the loan is repaid.

```python
# cell 12b
funding.equations(
    "equity_cash_flow = net_cash_flow + loan_interest + loan_draws",
    "equity_npv = rx.finance.npv(flow=equity_cash_flow, rate=equity_rate, on=base_date)",
    "equity_irr = rx.finance.irr(flow=equity_cash_flow)",
)
model = draft.commit()
```

```python
# cell 13
levered = base.on(model=model).fix(
    equity=plan["equity"],
    loan_limit=plan["loan_limit"],
    loan_rate="6 % pa",
    equity_rate="12 % pa",
)
levered_outcome = rk.execution.solve(specification=levered.cases(cases=cases))
levered_outcome.table("unlevered_npv", "equity_npv", "equity_irr")
```

> **Finance note.** Debt makes the equity's results larger in both directions. When
> the property earns more than the loan rate, debt raises the equity IRR. IRR has
> failure cases: a cash flow with more than one change of sign can have more than one
> IRR, and the solve then reports `irr_not_unique`.

## 7. Equity levels

Narrative. **Predict:** in the reference case, does the equity NPV rise when the
owner commits less equity and borrows more? Compare three levels in one batch.

```python
# cell 14
levels = {
    "80 m equity": {"equity": "80e6 AUD"},
    "50 m equity": {"equity": "50e6 AUD"},
    "30 m equity": {"equity": "30e6 AUD"},
}
rk.execution.solve(specification=levered.cases(cases=levels)).table(
    "equity_npv", "equity_irr", "loan_principal"
)
```

## 8. A target equity IRR

Narrative: the back door again, now on dated cash flows. The investor needs a 15 %
equity IRR. What land price gives it? Fix the IRR and free the land cost. With the
IRR fixed, the IRR equation becomes "NPV at 15 % is zero", which is linear.
The cascade's `max` has two sides; the solve finds which side applies in each period
and checks it after the solve.

```python
# cell 15
target = levered.fix(equity_irr="15 % pa").free("land_cost")
target_outcome = rk.execution.solve(specification=target)
target_outcome["land_cost"]
```

## 9. Can we pay the bills? By hand once

Narrative: a positive NPV does not pay a construction invoice. Payments come at the
end of each year. Split the first year's payments by hand: equity pays first, and the
loan pays what the equity cannot.

```python
# cell 16
paid_2027 = -(
    outcome["land"].at(on=date(2027, 1, 1)) + outcome["works"].at(on=date(2027, 1, 1))
)
from_equity = min(paid_2027, plan["equity"])
from_loan = paid_2027 - from_equity
from_equity, from_loan
```

Narrative: the Model makes the same split every year. Read the reference case from
the batch. This is the spreadsheet corkscrew: the running total of the need, and the
loan's part of it.

```python
# cell 17
reference_outcome = levered_outcome.case(key="reference")
assert reference_outcome["loan_principal"].at(on=date(2027, 1, 1)) == from_loan
reference_outcome.stream(
    "net_cash_flow", "funding_need", "loan_draws", "loan_principal", "equity_cash_flow"
)
```

## 10. What is left to spend

Narrative: what can still be spent is the available equity and the available loan.
`project.formulation(name="Funding")` finds the formulation that cell 12 made.
`loan_available` is what can still be drawn under the limit; `loan_principal` is what
is owed. A shortfall is loan principal above the limit. Building A's income helps to
pay for Building B, so the need includes the operating cash flow.

```python
# cell 18
draft = model.edit()
project = draft.entity(code="project")
funding = project.formulation(name="Funding")
funding.equations(
    "equity_available = rx.max(0 AUD, equity - funding_need)",
    "loan_available = loan_limit - loan_principal",
    "shortfall = rx.max(0 AUD, -loan_available)",
    "peak_shortfall = shortfall.max()",
)
model = draft.commit()
```

```python
# cell 19
funded = levered.on(model=model)
funded_outcome = rk.execution.solve(specification=funded.cases(cases=cases))
funded_outcome.table("unlevered_npv", "equity_npv", "equity_irr", "peak_shortfall")
```

```python
# cell 20
helpers.plot_flows(
    outcome=funded_outcome.case(key="weak"), keys=["equity_available", "loan_available"]
)
```

> **Finance note.** The shortfall uses only the equity and the loan that exist at each
> date. It assumes no future sale or refinance.

## 11. Optional: commitments

Narrative: a package's remaining payments become committed when it starts. What is
still to be paid is the running total less the whole total; `since` makes it zero
before the start date. The commitment gap is the largest amount by which committed
but unpaid payments exceed the available equity and the available loan. Lesson 05
uses it to check whether a start can be funded.

```python
# cell 21
draft = model.edit()
project = draft.entity(code="project")
funding = project.formulation(name="Funding")
funding.equations(
    "shared_unpaid = shared_works.cumulative() - shared_works.total()",
    "a_unpaid = a_works.cumulative() - a_works.total()",
    "b_unpaid = b_works.cumulative() - b_works.total()",
    "committed = shared_unpaid.since(on=shared_start) + a_unpaid.since(on=a_start)"
    " + b_unpaid.since(on=b_start)",
    "commitment_gap = rx.max(0 AUD, (committed - equity_available - loan_available).max())",
)
model = draft.commit()
committed_outcome = rk.execution.solve(
    specification=funded.on(model=model).cases(cases=cases)
)
committed_outcome.table("peak_shortfall", "commitment_gap")
```

> **Finance note.** When Building B starts, its whole budget is committed, even though
> the payments come over two years.

## 12. Optional, under the hood: the Run as evidence

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

**Try it 1: a stress case.** Solve the funded plan with no rent growth and a 7 % exit
cap rate. Compare it with the reference case. Does the peak shortfall change? Which
cash flow causes the change?

```python
# solution
stress_outcome = rk.execution.solve(
    specification=funded.fix(rent_growth="0 % pa", exit_cap_rate="7 %")
)
rk.execution.compare(
    outcomes={
        "Reference": funded_outcome.case(key="reference"),
        "Stress": stress_outcome,
    },
    keys=["peak_shortfall", "equity_npv"],
    baseline="Reference",
)
```

The shortfall increases. Building A's income is lower, so it pays less of Building
B's works. The exit cap rate changes the equity NPV but not the shortfall, because the
sale occurs after all works are paid.

**Try it 2: the target IRR in the weak case.** What land price gives a 15 % equity
IRR in the weak market?

```python
# solution
weak_target_outcome = rk.execution.solve(
    specification=target.fix(rent_growth="1 % pa", exit_cap_rate="6 %")
)
assert weak_target_outcome["land_cost"] < target_outcome["land_cost"]
```

**Try it 3: start Building B a year later.** In which year is the available loan
smallest now?

```python
# solution
later_outcome = rk.execution.solve(specification=funded.fix(b_start=date(2031, 1, 1)))
later_outcome["loan_available"].argmin()
```

## Checks and recap

```python
# cell 24 (checks)
npvs = cases_outcome.table("unlevered_npv")["unlevered_npv"]
assert npvs.is_sorted()  # weak < reference < strong
cash = target_outcome["equity_cash_flow"]
target_npv = rk.finance.npv(flow=cash, rate="15 % pa", on=date(2027, 1, 1))
assert rk.quantity.isclose(actual=target_npv, expected="0 AUD", tolerance="1 AUD")
reference_outcome = funded_outcome.case(key="reference")
assert reference_outcome["loan_principal"].at(on=date(2027, 1, 1)) == from_loan
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

24 core code cells, 3 optional cells (sections 11 and 12, one in a new kernel) and 1 check cell
(budget 20–25), 3 exercise solutions. The longest cell has 17 lines (optional cell 21). Cells
follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2–3 | 10 | G07: `load_base_plan`, `show_timeline` load and draw only |
| 4 | 6 | By hand once; the budget then lives in the plan's inputs |
| 5–5c | 2, 5 | G08 (entity handles); G72: the "Dates" formulation; G15: date-valued Values; G16: Flows made from amounts declare their Periods, other values take units and shape from their equations |
| 6–8 | 3, 6 | G72: formulation handles, `add_formulation(name=)` and `formulation(name=)`, with `equations(...)` (D43); G17: functions in equations (`rx.flow.event`, `rx.profile.uniform`, `rx.profile.compounding`, `rk.finance.npv`, and the methods `at` and `trim`); G18: Flow-valued string equations; date arithmetic in G15 |
| 7 | 6 | `compounding` with `base`, `start` and `every`: the Compounding profile in an equation (G70, [#168](https://github.com/daniel-fink/rangekeeper/issues/168)) |
| 9 | 2, 8 | G11, G12 |
| 10 | 8 | G19: `Outcome.stream` and Flow values in `Outcome` |
| 11, 13 | 8 | Cases ([#144](https://github.com/daniel-fink/rangekeeper/issues/144)). G20: `cases(mapping)` overrides by key; `Outcome.case`, `Outcome.table` with a case column |
| 12–12b | 3, 6 | The equity-first cascade as equations (D2): G05 (`cumulative()`, `diff()`), G17 (`rx.finance.interest`, `rx.finance.irr`, period-by-period `max`); G09: `max` and `irr` are evaluated in period order after the affine stage |
| 13 | 2 | G21: `Specification.on(model)` pins a new revision and keeps roles by key |
| 15 | 6, 8 | G22: a fixed `irr` becomes a linear NPV row; G77: with a free value, the solve picks the active side of each `max` and checks it after the solve |
| 16 | 6 | By hand once |
| 17 | 6, 8 | G19, G20: the corkscrew read from a case of the batch; composition, with no account class (D2) |
| 18, 21 | 2, 3, 6 | G05: `total()`, `cumulative()`, `since(on=)`, `max()`; G09 evaluates `max` after the affine stage |
| 20 | 10 | Helper draws named Flows only (`plot_flows`) |
| 22–23 | 1, 4 | `execute` ([#126](https://github.com/daniel-fink/rangekeeper/issues/126)); G25: `rk.execution.replay` and `store.find_runs(specification=name)` |
| 24 | 5, 8 | G06 |

## Open choices for review

- **Unit inference (G16).** Lesson 02 declares every value. From lesson 03, only
  inputs are declared. The alternative is to declare every Flow, which adds about
  15 lines to cells 6–8.
