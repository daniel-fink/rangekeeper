# Lesson 05: When to commit (proposed cells)

Issue: [#207](https://github.com/daniel-fink/rangekeeper/issues/207). Plan:
[ADR-020 §05](../../../docs/decisions/020-walkthrough-plan-v2.md#05-when-to-commit).
Design: [#213](https://github.com/daniel-fink/rangekeeper/issues/213) (sequential
decisions), [#139](https://github.com/daniel-fink/rangekeeper/issues/139)
(availability). Implementation: [#215](https://github.com/daniel-fink/rangekeeper/issues/215).
API conventions and the gap list: [README](README.md).

Decision used here (D9 in the [README](README.md#decisions)): if a value can change,
it belongs in the Specification; if it is part of the modelling, it belongs in the
Model. The Model declares the date equations (lesson 03). A policy rule **decides**
one value: it fixes the value on the first review date on which its condition holds.
"Decided" is a role beside fixed and free. There is no separate action concept.

The lesson is not authored until #215 is verified (ADR-020).

## Goals box

> **Question.** When should we buy the site, start Building B, or stop?
>
> **You will learn to:**
>
> 1. write a decision rule with a threshold on an observed value;
> 2. use only the information available at the decision date;
> 3. check funding before a commitment, and read a decision trace;
> 4. compare the fixed plan with a strategy on the same paths, as paired differences;
> 5. tell rule parameters from realised decisions.
>
> **Before you start.** Lessons 03 and 04.
>
> **Time.** 60 minutes core, 30 minutes optional (threshold sweep).
>
> **Not in this lesson.** Changes to the design (lesson 07).
>
> **Source.** Figure 9.1 in de Neufville and Geltner (2018), used with the
> publisher's permission and with attribution. Chapters 9 and 10 are cited for the
> method.

## 1. The plan, the paths and the dates that can move

Narrative: start from lesson 04's Model and paths. The plan's dates are related:
the shared works start on the start date, Building A follows a year later, and
Building B cannot start before the shared works finish. These equations are part of
the Model. Only two dates are inputs: the start date and Building B's start.

```python
# cell 1
from datetime import date

import rangekeeper as rk
import helpers
```

```python
# cell 2
model = rk.io.load(path=helpers.data_path(name="04_base_plan_on_paths.model.json"))
paths = rk.io.load(path=helpers.data_path(name="04_rent_index.paths.json"))
model.equations.where(formulation="Dates")  # the plan's date equations
```

```python
# cell 3
fixed = rk.io.load(path=helpers.data_path(name="04_base_case.specification.json"))
fixed.roles  # lesson 04's base case: start in 2027, Building B in 2030
```

## 2. Three readable histories

Narrative: before 500 paths, look at three: an early recovery, a long downturn,
and a short recovery then a decline. The fixed plan starts in 2027 on all three.

```python
# cell 4
stories = rk.io.load(path=helpers.data_path(name="05_histories.paths.json"))
helpers.plot_paths(paths=stories, names=["rent_index"])
```

```python
# cell 5
fixed_stories_outcome = rk.execution.solve(specification=fixed.across(paths=stories))
fixed_stories_outcome.table("equity_npv", "peak_shortfall")
```

## 3. A rule: wait to start

Narrative: in place of a fixed start date, decide it. Each January from 2027 to
2030, read the latest rent index. Start when it reaches 1.05. If it never does, do
not buy the site. `decide` replaces the fixed start date with a rule. The reviews are
a `Periods`: the rule looks on the first day of each Period. The threshold is a
value in the Specification, so you can change it later without rewriting the rule.
`rk.duration.NEVER` means the event does not happen.

```python
# cell 6
yearly = rk.duration.Frequency.YEAR
start_reviews = rk.duration.Span(start=date(2027, 1, 1), end=date(2031, 1, 1)).periods(
    frequency=yearly
)
wait = fixed.parameters(start_threshold=1.05).decide(
    key="start_date",
    when="rent_index >= start_threshold",
    periods=start_reviews,
    otherwise=rk.duration.NEVER,
)
wait_outcome = rk.execution.solve(specification=wait.across(paths=stories))
wait_outcome.table("start_date", "b_start", "equity_npv")
```

Narrative: the trace shows each review: the date, what was observed, when it became
known, and the result. Building B's start is still fixed at 2030. **Predict:** what
happens on a history where the project starts in 2030? Building B would start
before the shared works finish. The Model's constraint `b_start >= shared_start +
1 year` catches this: the case is infeasible, and the diagnostic names the
constraint. The rule for Building B must follow the rule for the start.

```python
# cell 7
downturn = wait_outcome.case(key="long downturn")
downturn.trace()  # each review: date, observed value, when it was known, result
```

```python
# cell 7b
downturn.status, downturn.diagnostics
```

> **Finance note.** A start date that follows the market is an option to wait. Its
> value comes from avoiding bad outcomes. Its cost is lost income and a shorter
> operating period before the common sale date.

## 4. Only what is known

Narrative: a rule cannot use the future. The 2028 rent index is known only at the
end of 2028. A rule that reads next year's index fails when the Specification is
made, before any solve.

```python
# cell 8
try:
    fixed.decide(
        key="start_date",
        when="rent_index.shift(by=-1) >= 1.05",
        periods=start_reviews,
        otherwise=rk.duration.NEVER,
    )
except rk.errors.AvailabilityError as error:
    print(error.code, error.key, error.available_on, error.decision_date)
```

> **Finance note.** Hindsight bias: a rule that sees the future always looks
> valuable. Availability dates come from the market paths (lesson 04).

## 5. Start Building B when the market and funding allow

Narrative: decide Building B's start too. Start B when the index reaches 1.10 and
the available equity and the available loan cover B's whole budget. Both come from
lesson 03's funding equations, with the decisions made so far. Building B cannot
start before the shared works finish, so `earliest=` skips the reviews before that
date on each path.

```python
# cell 9
b_reviews = rk.duration.Span(start=date(2028, 1, 1), end=date(2033, 1, 1)).periods(
    frequency=yearly
)
start_b = wait.decide(
    key="b_start",
    when="rent_index >= 1.10 and equity_available + loan_available >= b_cost",
    periods=b_reviews,
    earliest="shared_start + 1 year",
    otherwise=rk.duration.NEVER,
)
# the decided values, their rules and their review Periods
helpers.show_decisions(specification=start_b)
```

## 6. Stop and sell Building B's site

Narrative: if Building B has not started by 2033, sell its share of the site. The
price rule is part of the modelling: the site sells at its share of the land cost,
scaled by the rent index on the sale date. Add it to the Model. The sale date is a
decided value.

```python
# cell 10
years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=yearly
)
draft = model.edit()
site = draft.entity(code="property")
site.value(key="b_land_share", units="ratio")
site.date(key="b_sale_date")
site.flow(key="b_site_sale", units="AUD", periods=years)
site.equations(
    "b_site_value = b_land_share * land_cost * rent_index.at(on=b_sale_date)",
    "b_site_sale = rx.flow.event(amount=b_site_value, on=b_sale_date)",
)
site.add_to(key="project_cash", term="b_site_sale")
model = draft.commit()
```

```python
# cell 11
sale_reviews = rk.duration.Span(start=date(2033, 1, 1), end=date(2034, 1, 1)).periods(
    frequency=yearly
)
strategy = (
    start_b.on(model=model)
    .fix(b_land_share="40 %")
    .decide(
        key="b_sale_date",
        when="b_start == NEVER",
        periods=sale_reviews,
        otherwise=rk.duration.NEVER,
    )
)
```

```python
# cell 11b
stories_outcome = rk.execution.solve(specification=strategy.across(paths=stories))
stories_outcome.decisions()  # one row for each case and review
```

```python
# cell 12
# each history and its decisions
helpers.plot_decisions(outcome=stories_outcome, name="rent_index")
```

## 7. All paths: paired comparison

Narrative. **Predict:** does the strategy raise the mean equity NPV? Run the fixed
plan and the strategy on the same paths. Compare them path by path: each paired
difference holds the market fixed and shows the effect of the rules alone.

```python
# cell 13
fixed_plan = fixed.on(model=model).fix(
    b_land_share="40 %", b_sale_date=rk.duration.NEVER
)
fixed_outcome = rk.execution.solve(specification=fixed_plan.across(paths=paths))
strategy_outcome = rk.execution.solve(specification=strategy.across(paths=paths))
```

```python
# cell 14
difference = rk.execution.compare(
    outcomes={"Strategy": strategy_outcome, "Fixed plan": fixed_outcome},
    keys=["equity_npv", "peak_shortfall"],
    baseline="Fixed plan",
)
difference.summary()  # mean difference, share of paths better, worst loss
```

```python
# cell 15
helpers.plot_target_curve(
    outcomes={"Strategy": strategy_outcome, "Fixed plan": fixed_outcome},
    key="equity_npv",
)
```

## 8. Rule parameters and realised decisions

Narrative: the threshold 1.05 is a parameter of the rule. It is the same on every
path. The start date is a realised decision: it differs from path to path. Read the
realised start years, and the paired difference for each.

```python
# cell 16
strategy_outcome.distribution(key="start_date").counts()
difference.by(key="start_date").summary()  # where waiting gains, and where it costs
```

## 9. Optional: a threshold sweep

Narrative: the threshold is a value in the Specification (cell 6), so cases can sweep
it like any other value. Cases and paths multiply: each threshold runs on every
path.

```python
# cell 17
thresholds = {
    "1.00": {"start_threshold": 1.00},
    "1.02": {"start_threshold": 1.02},
    "1.05": {"start_threshold": 1.05},
    "1.08": {"start_threshold": 1.08},
}
```

```python
# cell 17b
swept = strategy.cases(cases=thresholds)
sweep_outcome = rk.execution.solve(specification=swept.across(paths=paths))
sweep_difference = rk.execution.compare(
    outcomes={"Sweep": sweep_outcome, "Fixed plan": fixed_outcome},
    keys=["equity_npv"],
    baseline="Fixed plan",
)
sweep_difference.by_case().summary()
```

## Exercises

**Try it 1: a lower threshold.** Start when the index reaches 1.02. How many paths
start in 2027? Does the mean paired difference rise?

```python
# solution
early = strategy.fix(start_threshold=1.02)
early_outcome = rk.execution.solve(specification=early.across(paths=paths))
early_outcome.distribution(key="start_date").counts()
rk.execution.compare(
    outcomes={"Early": early_outcome, "Fixed plan": fixed_outcome},
    keys=["equity_npv"],
    baseline="Fixed plan",
).summary()
```

**Try it 2: no funding check.** Remove the funding condition from Building B's rule.
On how many paths does the commitment gap become positive?

```python
# solution
reckless = strategy.decide(
    key="b_start",
    when="rent_index >= 1.10",
    periods=b_reviews,
    earliest="shared_start + 1 year",
    otherwise=rk.duration.NEVER,
)
reckless_outcome = rk.execution.solve(specification=reckless.across(paths=paths))
gaps = reckless_outcome.distribution(key="commitment_gap")
gaps.probability(above="0 AUD")
```

**Try it 3: a worse site price.** Lower Building B's land share to 25 %. How does
the paired difference change on the paths where B never starts?

```python
# solution
cheap_site = strategy.fix(b_land_share="25 %")
cheap_site_outcome = rk.execution.solve(specification=cheap_site.across(paths=paths))
cheap_difference = rk.execution.compare(
    outcomes={"Cheap site": cheap_site_outcome, "Fixed plan": fixed_outcome},
    keys=["equity_npv"],
    baseline="Fixed plan",
)
cheap_difference.where(b_start=rk.duration.NEVER).summary()
```

## Checks and recap

```python
# cell 18 (checks)
assert strategy_outcome.run.market_paths == fixed_outcome.run.market_paths == paths.id
for row in strategy_outcome.decisions().observations():
    assert row.available_on <= row.decision_date
decided = rk.execution.ReviewResult.DECIDED
for row in strategy_outcome.decisions().where(key="b_start", result=decided):
    available = row.observed["equity_available"] + row.observed["loan_available"]
    assert available >= row.observed["b_cost"]
assert strategy_outcome.case(key=paths.keys[0]).run.policy_evidence.verified
```

**Recap.**

1. A rule decides a value that the Model relates to the rest of the plan. The Model
   says how dates depend on each other; the Specification says when to commit.
2. A rule sees only what is known at its date. Funding is checked with the decisions
   made so far.
3. Compare strategies path by path on the same paths. A rule's parameters are fixed;
   its decisions vary by path.

**Next.** Lesson 06 opens the project's structure. Lesson 07 lets rules choose
between designs.

## Cell budget

18 core code cells, 2 optional cells and 1 check cell (budget 20–25), 3 exercise
solutions. The longest cell has 15 lines (cell 10). Cells follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2 | 1, 10 | G26; G47: `equations.where(keys=, formulation=)` |
| 4 | 10 | G48: `rk.market.Paths` from explicit Flows (the three histories are data, made once) |
| 6 | 2, 6 | D1–D2 of the review: `rk.duration.Periods` from `Span.periods`; G49: `Specification.decide(key=, when=, periods=, earliest=, latest=, otherwise=)`, the "decided" role, rules as strings; G57: `parameters` for a rule's threshold |
| 6, 11, 13 | 5 | G50: `rk.duration.NEVER` for date values, `NEVER` in rule text; functions treat a `NEVER` date as "no flow" |
| 7–7b, 11b, 12 | 8, 9 | G51: `Outcome.trace()` and `Outcome.decisions()` tables; infeasible decided values name the constraint (G52) |
| 8 | 9 | G53: `AvailabilityError` (with `key`) at Specification validation ([#139](https://github.com/daniel-fink/rangekeeper/issues/139)) |
| 9 | 6 | G54: sequential solve: a rule observes solved values (funding) under the decisions so far ([#213](https://github.com/daniel-fink/rangekeeper/issues/213)) |
| 9, 11 | 3 | G55: `earliest=` and `latest=` expression bounds on the reviews; rules that observe earlier decisions (`b_start == never`) |
| 10 | 2, 3 | G27 (`add_to(key=, term=)`); G17 (`at`, `rx.flow.event`) |
| 13–16 | 8 | G56, G66: `rk.execution.compare(outcomes=, keys=, baseline=)` paired by path, with `summary`, `by`, `by_case`, `where` |
| 15 | 10 | Helper draws only |
| 17–17b, Try it 1 | 2 | G57: a rule's threshold fixed and swept like any Specification value; cases × paths |
| 18 | 8 | G58: policy evidence in the Run (`policy_evidence.verified`), observations with `available_on`; `rk.execution.ReviewResult` |

## Cells for #213

The design for sequential decisions must support:

- **Observations.** A rule names Model values (`rent_index`, `equity_available`,
  `loan_available`,
  `b_cost`) and earlier decided values (`b_start == NEVER`). The value read is the
  latest one available on the review date.
- **Availability.** Market path Flows carry availability dates (period end by
  default). Solved values, such as the available loan, are available on the review date
  when they depend only on Movements up to that date. Validation rejects a rule that
  reads a later value (cell 8).
- **Decided values.** A date value, or `rk.duration.NEVER`. The decision fixes the
  value; the Model's equations, equalities and bounds, move the dependent dates
  (cells 6, 9, 11).
- **Reviews.** A `Periods`: the rule looks on the first day of each Period.
  `earliest=` and `latest=` skip reviews outside bounds that are expressions of
  earlier decisions (cell 9).
- **Funding.** The rule observes the funding values (`equity_available`,
  `loan_available`) under the decisions made so far, so evaluation alternates review
  and solve in date order (cell 9).
- **Traces.** For each case and review: date, decided value, observations with their
  availability dates, the rule's truth and the result (cells 7, 11).
- **Paired comparison.** Two Outcomes on the same pinned `rk.market.Paths`, matched by
 path key (cells 13–16).
