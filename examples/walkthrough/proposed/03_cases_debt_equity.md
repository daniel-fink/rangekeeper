# Lesson 03: Cases, debt and equity (proposed cells)

Issue: [#205](https://github.com/daniel-fink/rangekeeper/issues/205). Plan:
[ADR-020 §03](../../../docs/decisions/020-walkthrough-plan-v2.md#03-cases-debt-and-equity).
API conventions and the gap list: [README](README.md).

Decisions used here (recorded in the [README](README.md#decisions)): the cases
reach the cash flows through the solve (D1); `irr`, `min` and `max` are evaluated
after the affine stage, and a fixed IRR becomes an affine row (D4); the funding
account is a Model relation and a `finance` class (D2).

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
plan.inputs                            # dates, budgets, incomes and funding, with origins
```

```python
# cell 3
helpers.show_timeline(plan)
years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods("year")
```

> **Finance note.** A development budget has hard costs (construction), soft costs
> (fees and approvals) and a contingency. Land is a separate line.

## 2. The budget, by hand once

Narrative: Building A's budget is its area by use times the construction rate, plus
10 % soft costs and 10 % contingency. Calculate it once by hand and compare it with
the plan's total. The other packages follow the same rule.

```python
# cell 4
hard = sum(plan.areas["building_a"][use] * plan.rates[use] for use in plan.areas["building_a"])
assert rk.units.isclose(hard * 1.2, plan.inputs["a_cost"])
```

## 3. The dated Model

Narrative: declare the inputs with their units. From this lesson on, declare only the
inputs: the builder infers the units and shape of every other value from the
equations, and `commit()` names any value that it cannot infer. Dates are values
too, so a later lesson can change them.

```python
# cell 5
b = rk.Model.build(name="Mixed-use base plan", subject="property", timeline=years)
b.values(
    base_date="date", sale_date="date", start_date="date", b_start="date",
    land_cost="AUD", shared_cost="AUD", a_cost="AUD", b_cost="AUD",
    a_income="AUD pa", b_income="AUD pa", a_opex="AUD pa", b_opex="AUD pa",
    a_renewal="AUD", b_renewal="AUD",
    rent_growth="1/year", opex_growth="1/year", exit_cap_rate="ratio", discount_rate="1/year",
)
```

Narrative: the plan's sequence is a relation too. The site is bought and the shared
works start on the start date. Building A follows a year later, and each building
takes two years to build. Building B cannot start before the shared works finish.
Development payments are negative; `uniform` divides an amount evenly over the years
from a start date.

```python
# cell 6
b.equations(
    "shared_start = start_date",
    "a_start = shared_start + 1 year",
    "a_open = a_start + 2 years",
    "b_open = b_start + 2 years",
    "b_start >= shared_start + 1 year",
    "land = -event(land_cost, on=start_date)",
    "shared_works = -uniform(shared_cost, start=shared_start, years=1)",
    "a_works = -uniform(a_cost, start=a_start, years=2)",
    "b_works = -uniform(b_cost, start=b_start, years=2)",
    "works = shared_works + a_works + b_works",
)
```

Narrative: operations. Rents grow on one calendar from 2027, but each building
earns nothing until it opens. Renewals come every five years after opening.

```python
# cell 7
b.equations(
    "income = compounding(a_income, rate=rent_growth, base=base_date, start=a_open)"
    " + compounding(b_income, rate=rent_growth, base=base_date, start=b_open)",
    "opex = -compounding(a_opex, rate=opex_growth, base=base_date, start=a_open)"
    " - compounding(b_opex, rate=opex_growth, base=base_date, start=b_open)",
    "renewals = -compounding(a_renewal, rate=opex_growth, base=base_date, start=a_open + 5 years, every=5 years)"
    " - compounding(b_renewal, rate=opex_growth, base=base_date, start=b_open + 5 years, every=5 years)",
    "operating = income + opex + renewals",
)
```

Narrative: the sale and the value. These are lesson 01's ideas, now as relations.

```python
# cell 8
b.equations(
    "sale = event(at(operating, sale_date + 1 year) / exit_cap_rate, on=sale_date)",
    "net_cash_flow = trim(land + works + operating + sale, end=sale_date)",
    "unlevered_npv = npv(net_cash_flow, rate=discount_rate, on=base_date)",
)
model = b.commit()
```

## 4. The base case

Narrative. **Predict:** is the unlevered NPV positive at the reference assumptions?
Fix the plan's inputs and the reference assumptions. Everything else is free.

```python
# cell 9
reference = {"rent_growth": "3 %/year", "exit_cap_rate": "5 %"}
valuation = {"discount_rate": "7 %/year", "opex_growth": "3.5 %/year"}
base = model.specify("Base case").fix(**plan.inputs, **valuation, **reference)
outcome = rk.execution.solve(base)
outcome["unlevered_npv"]
```

```python
# cell 10
outcome.stream("land", "works", "income", "opex", "renewals", "sale").display()
helpers.plot_cash_flows(outcome, "net_cash_flow")
```

## 5. Named cases

Narrative: a case is one named set of assumptions. A batch Specification holds the
cases; one solve gives one comparable table. Every case uses the same plan and the
same valuation conventions.

```python
# cell 11
cases = {
    "weak": {"rent_growth": "1 %/year", "exit_cap_rate": "6 %"},
    "reference": reference,
    "strong": {"rent_growth": "5 %/year", "exit_cap_rate": "4.5 %"},
}
outcomes = rk.execution.solve(base.cases(cases))
outcomes.table("unlevered_npv")
```

```python
# cell 12
outcomes.case("weak").stream("income", "sale").display()
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
e = model.edit()
e.values(leverage="ratio", loan_rate="1/year", equity_rate="1/year")
e.equations(
    "loan_draws = -leverage * (land + works)",
    "loan_balance = cumulative(loan_draws)",
    "loan_interest = -interest(loan_balance, rate=loan_rate)",
    "repayment = -settle(loan_balance, on=sale_date)",
    "equity_cash_flow = net_cash_flow + loan_draws + loan_interest + repayment",
    "equity_npv = npv(equity_cash_flow, rate=equity_rate, on=base_date)",
    "equity_irr = irr(equity_cash_flow)",
)
model = e.commit()
```

```python
# cell 14
debt = {"leverage": "65 %", "loan_rate": "6 %/year", "equity_rate": "12 %/year"}
levered = base.on(model).fix(**debt)
rk.execution.solve(levered.cases(cases)).table("unlevered_npv", "equity_npv", "equity_irr")
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
levels = {"no debt": {"leverage": 0}, "50 %": {"leverage": "50 %"}, "65 %": {"leverage": "65 %"}}
rk.execution.solve(levered.cases(levels)).table("equity_npv", "equity_irr")
```

## 8. A target equity IRR

Narrative: the back door again, now on dated cash flows. The investor needs a 15 %
equity IRR. What land price gives it? Fix the IRR and free the land cost. With the
IRR fixed, the IRR relation becomes "NPV at 15 % is zero", which is an affine row.

```python
# cell 16
target = levered.fix(equity_irr="15 %/year").free("land_cost")
target_outcome = rk.execution.solve(target)
target_outcome["land_cost"]
```

## 9. Can we pay the bills? By hand once

Narrative: a positive NPV does not pay a construction invoice. The owner has 50
million AUD of equity and a bridge facility of 65 million AUD. Payments come at the
end of each year. Calculate the first year's closing balance and headroom by hand.

```python
# cell 17
paid_2027 = outcome["land"].at(date(2027, 1, 1)) + outcome["works"].at(date(2027, 1, 1))
closing_2027 = plan.inputs["equity"] + paid_2027
headroom_2027 = closing_2027 + plan.inputs["bridge_limit"]
closing_2027, headroom_2027
```

```python
# cell 18
account = rk.finance.Account(opening=plan.inputs["equity"], limit=plan.inputs["bridge_limit"])
history = account.post(outcome["land"] + outcome["works"])
assert history.closing.at(date(2027, 1, 1)) == closing_2027
history.display()                      # opening, transactions, closing and headroom by year
```

## 10. Funding in the Model

Narrative: the same account as a relation, so that every case and every later
lesson reports it. Building A's income helps to pay for Building B, so the account
includes operating cash flow. A package's remaining payments become committed when
it starts.
The commitment gap is the largest amount by which committed but unpaid payments
exceed the headroom.

```python
# cell 19
e = model.edit()
e.values(equity="AUD", bridge_limit="AUD")
e.account("funding", opening="equity", limit="bridge_limit", transactions="land + works + operating",
          commitments={"shared_works": "shared_start", "a_works": "a_start", "b_works": "b_start"})
e.equations(
    "peak_shortfall = max(0 AUD, -min(funding.headroom))",
    "commitment_gap = max(0 AUD, max(funding.committed - funding.headroom))",
)
model = e.commit()
```

```python
# cell 20
funded = levered.on(model)
summary = rk.execution.solve(funded.cases(cases))
summary.table("unlevered_npv", "equity_npv", "equity_irr", "peak_shortfall", "commitment_gap")
```

```python
# cell 21
helpers.plot_funding(summary.case("weak"), "funding")      # balance, limit and committed payments
```

> **Finance note.** The commitment gap uses only cash and facilities that exist at
> each date. It assumes no future sale or refinance. When Building B starts, its
> whole budget is committed, even though the payments come over two years.

## 11. Under the hood: the Run as evidence

Narrative: `solve` keeps everything in memory. `execute` also publishes the outputs
and a Run to a store. A Run records the Specification, the Model revision, the
solver, the status and every case. Replay reads it in a fresh kernel and checks
that the result is the same. A namespace gives the same IDs on every build.

```python
# cell 22
store = rk.io.DirectoryStore("runs/03")
executed = rk.execution.execute(funded.cases(cases), store)
executed.run.id
```

```python
# cell 23 (new kernel)
store = rk.io.DirectoryStore("runs/03")
run = store.find_runs(specification="Base case")[-1]
rk.execution.replay(run, store).raise_for_status()
```

> **Under the hood: the same IDs on every build.** Pass a namespace to the builder.
> The same inputs then give the same Model ID and record IDs in every kernel
> ([#147](https://github.com/daniel-fink/rangekeeper/issues/147)):
>
> ```python
> ns = rk.model.namespace("rangekeeper-walkthrough/03")
> b = rk.Model.build(name="Mixed-use base plan", subject="property", timeline=years, namespace=ns)
> ```

## Exercises

**Try it 1: a stress case.** Add a case with no rent growth and a 7 % exit cap rate.
Does the commitment gap change? Which cash flow causes the change?

```python
# solution
stress = rk.execution.solve(funded.cases({**cases, "stress": {"rent_growth": "0 %/year",
                                                              "exit_cap_rate": "7 %"}}))
assert stress.case("stress")["commitment_gap"] >= stress.case("reference")["commitment_gap"]
# Building A's lower income pays less of Building B's works. The exit cap rate has no effect.
```

**Try it 2: the target IRR in the weak case.** What land price gives a 15 % equity
IRR in the weak market?

```python
# solution
weak_target = target.fix(**cases["weak"])
assert rk.execution.solve(weak_target)["land_cost"] < target_outcome["land_cost"]
```

**Try it 3: start Building B a year later.** Which year has the least headroom now?

```python
# solution
later = rk.execution.solve(funded.fix(b_start=date(2031, 1, 1)))
later["funding.headroom"].argmin()
```

## Checks and recap

```python
# cell 24 (checks)
weak, ref, strong = (outcomes.case(k)["unlevered_npv"] for k in ("weak", "reference", "strong"))
assert weak < ref < strong
assert rk.units.isclose(
    rk.finance.npv(target_outcome["equity_cash_flow"], rate="15 %/year", on=date(2027, 1, 1)),
    rk.units.q("0 AUD"), abs="1 AUD")
assert summary.case("reference")["funding.headroom"].at(date(2027, 1, 1)) == headroom_2027
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

22 core code cells and 1 cell in a new kernel (budget 20–25), 3 exercise solutions.
Cell 7 has 9 lines and cell 13 has 13; no cell has more than 15.

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2–3 | 10 | G07: `load_base_plan`, `show_timeline` load and draw only |
| 4 | 6 | By hand once; the budget then lives in the plan's inputs |
| 5 | 2, 5 | G08 (`subject`, `timeline`); G15: date-valued Values; G16: infer units and shapes of other values |
| 6–8 | 3, 6 | G17: Function catalogue for equations (`event`, `at`, `uniform`, `compounding`, `trim`, `npv`); G18: Flow-valued string equations; date arithmetic in G15 |
| 7 | 6 | `compounding` with `base`, `start` and `every`: the Compounding profile in an equation (G70, [#168](https://github.com/daniel-fink/rangekeeper/issues/168)) |
| 9 | 2, 8 | G11, G12 |
| 10, 12 | 8 | G19: `Outcome.stream` and Flow values in `Outcome` |
| 11, 14 | 8 | Cases ([#144](https://github.com/daniel-fink/rangekeeper/issues/144)). G20: `cases(mapping)` overrides by key; `Outcome.case`, `Outcome.table` with a case column |
| 13 | 3, 6 | G17 (`cumulative`, `interest`, `settle`, `irr`); G09: `irr` is evaluated after the affine stage |
| 14 | 2 | G21: `Specification.on(model)` pins a new revision and keeps roles by key |
| 16 | 6, 8 | G22: a fixed `irr` becomes an affine NPV row |
| 17 | 6 | By hand once |
| 18 | 6 | G23: `rk.finance.Account` with `limit`, `post`, `headroom` |
| 19 | 2, 6 | G24: `ModelBuilder.account` with `commitments`; `min` and `max` in G09 |
| 21 | 10 | Helper draws only |
| 22–23 | 1, 4 | `execute` ([#126](https://github.com/daniel-fink/rangekeeper/issues/126)); G25: `rk.execution.replay` and `store.find_runs(specification=name)` |
| 24 | 5, 8 | G06 |

## Open choices for review

- **Unit inference (G16).** Lesson 02 declares every value. From lesson 03, only
  inputs are declared. The alternative is to declare every Flow, which adds about
  15 lines to cells 6–8.
- **Funding structure.** The cells use equity plus an overdraft-style bridge limit.
  `development.json` also has a fixed draw schedule. Authoring picks one; the API is
  the same.
