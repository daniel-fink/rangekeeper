# Lesson 05: When to commit (proposed cells)

Issue: [#207](https://github.com/daniel-fink/rangekeeper/issues/207). Plan:
[ADR-020 §05](../../../docs/decisions/020-walkthrough-plan-v2.md#05-when-to-commit).
Design: [#213](https://github.com/daniel-fink/rangekeeper/issues/213) (sequential
decisions), [#139](https://github.com/daniel-fink/rangekeeper/issues/139)
(availability). Implementation: [#215](https://github.com/daniel-fink/rangekeeper/issues/215).
API conventions and the gap list: [README](README.md).

Decision used here (D9 in the [README](README.md#decisions)): if a value can change,
it belongs in the Specification; if it is part of the modelling, it belongs in the
Model. The Model declares the date relations (lesson 03). A policy rule **decides**
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
Building B cannot start before the shared works finish. These relations are part of
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
plan = helpers.load_base_plan()
model.equations.involving("start_date", "b_start")
```

```python
# cell 3
assumptions = {
    "discount_rate": "7 %/year",
    "opex_growth": "3.5 %/year",
    "exit_cap_rate": "5 %",
    "rent_growth": "0 %/year",
}
yearly = rk.duration.Frequency.YEAR
debt = {"leverage": "65 %", "loan_rate": "6 %/year", "equity_rate": "12 %/year"}
fixed = model.specify(name="Fixed plan").fix(**plan.inputs, **assumptions, **debt)
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
assign = {"rent_index": "rent_index"}
fixed_stories = rk.execution.solve(
    specification=fixed.across(paths=stories, assign=assign)
)
fixed_stories.table("equity_npv", "peak_shortfall")
```

## 3. A rule: wait to start

Narrative: in place of a fixed start date, decide it. Each January from 2027 to
2030, read the latest rent index. Start when it reaches 1.05. If it never does, do
not buy the site. `decide` replaces the fixed start date with a rule.

```python
# cell 6
wait = fixed.decide(
    key="start_date",
    when="rent_index >= 1.05",
    review=yearly,
    window=(date(2027, 1, 1), date(2031, 1, 1)),
    otherwise="never",
)
waited = rk.execution.solve(specification=wait.across(paths=stories, assign=assign))
waited.table("start_date", "b_start", "equity_npv")
```

Narrative: the trace shows each review: the date, what was observed, when it became
known, and the result. Building B's start is still fixed at 2030. **Predict:** what
happens on a history where the project starts in 2030? Building B would start
before the shared works finish. The Model's constraint `b_start >= shared_start +
1 year` catches this: the case is infeasible, and the diagnostic names the
constraint. The rule for Building B must follow the rule for the start.

```python
# cell 7
waited.case(key="long downturn").trace()
waited.case(key="long downturn").status, waited.case(key="long downturn").diagnostics
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
        when="shift(flow=rent_index, periods=-1) >= 1.05",
        review=yearly,
        window=(date(2027, 1, 1), date(2031, 1, 1)),
        otherwise="never",
    )
except rk.errors.AvailabilityError as error:
    print(error.code, error.value, error.available_on, error.decision_date)
```

> **Finance note.** Hindsight bias: a rule that sees the future always looks
> valuable. Availability dates come from the market paths (lesson 04).

## 5. Start Building B when the market and funding allow

Narrative: decide Building B's start too. Start B when the index reaches 1.10 and
the funding headroom covers B's whole budget. Building B's earliest date follows
the start date, so the window starts there. The headroom comes from the funding
account of lesson 03, with the decisions made so far.

```python
# cell 9
start_b = wait.decide(
    key="b_start",
    when="rent_index >= 1.10 and funding.headroom >= b_cost",
    review=yearly,
    window=("shared_start + 1 year", date(2033, 1, 1)),
    otherwise="never",
)
helpers.show_decisions(
    specification=start_b
)  # the decided values, their rules and windows
```

## 6. Stop and sell Building B's site

Narrative: if Building B has not started by 2033, sell its share of the site. The
price rule is part of the modelling: the site sells at its share of the land cost,
scaled by the rent index on the sale date. Add it to the Model. The sale date is a
decided value.

```python
# cell 10
draft = model.edit()
site = draft.entity(code="property")
site.values(b_land_share="ratio", b_sale_date="date")
site.equations(
    "b_site_value = b_land_share * land_cost * at(flow=rent_index, on=b_sale_date)",
    "b_site_sale = event(amount=b_site_value, on=b_sale_date)",
)
site.extend(key="project_cash", terms="+ b_site_sale")
model = draft.commit()
```

```python
# cell 11
strategy = (
    start_b.on(model=model)
    .fix(b_land_share="40 %")
    .decide(
        key="b_sale_date",
        when="b_start == never",
        review=yearly,
        window=(date(2033, 1, 1), date(2034, 1, 1)),
        otherwise="never",
    )
)
traced = rk.execution.solve(specification=strategy.across(paths=stories, assign=assign))
traced.decisions()  # one row for each case and review
```

```python
# cell 12
helpers.plot_decisions(
    outcome=traced, name="rent_index"
)  # each history and its decisions
```

## 7. All paths: paired comparison

Narrative. **Predict:** does the strategy raise the mean equity NPV? Run the fixed
plan and the strategy on the same paths. Compare them path by path: each paired
difference holds the market fixed and shows the effect of the rules alone.

```python
# cell 13
fixed_plan = fixed.on(model=model).fix(b_land_share="40 %", b_sale_date="never")
fixed_out = rk.execution.solve(
    specification=fixed_plan.across(paths=paths, assign=assign)
)
flex_out = rk.execution.solve(specification=strategy.across(paths=paths, assign=assign))
```

```python
# cell 14
difference = flex_out.compare(other=fixed_out, keys=["equity_npv", "peak_shortfall"])
difference.summary()  # mean difference, share of paths better, worst loss
```

```python
# cell 15
helpers.plot_target_curve(
    distributions={
        "Strategy": flex_out.distribution(key="equity_npv"),
        "Fixed plan": fixed_out.distribution(key="equity_npv"),
    }
)
```

## 8. Rule parameters and realised decisions

Narrative: the threshold 1.05 is a parameter of the rule. It is the same on every
path. The start date is a realised decision: it differs from path to path. Read the
realised start years, and the paired difference for each.

```python
# cell 16
flex_out.distribution(key="start_date").counts()
difference.by(key="start_date").summary()  # where waiting gains, and where it costs
```

## 9. Optional: a threshold sweep

Narrative: a rule parameter can be a named Specification parameter. Cases can then
sweep it. Cases and paths multiply: each threshold runs on every path.

```python
# cell 17
swept = (
    strategy.parameters(start_threshold=1.05)
    .decide(
        key="start_date",
        when="rent_index >= start_threshold",
        review=yearly,
        window=(date(2027, 1, 1), date(2031, 1, 1)),
        otherwise="never",
    )
    .cases(cases={f"{t:.2f}": {"start_threshold": t} for t in (1.00, 1.02, 1.05, 1.08)})
)
sweep = rk.execution.solve(specification=swept.across(paths=paths, assign=assign))
sweep.compare(other=fixed_out, keys=["equity_npv"]).by_case().summary()
```

## Exercises

**Try it 1: a lower threshold.** Start when the index reaches 1.02. How many paths
start in 2027? Does the mean paired difference rise?

```python
# solution
early = strategy.decide(
    key="start_date",
    when="rent_index >= 1.02",
    review=yearly,
    window=(date(2027, 1, 1), date(2031, 1, 1)),
    otherwise="never",
)
early_out = rk.execution.solve(specification=early.across(paths=paths, assign=assign))
early_out.distribution(key="start_date").counts()
early_out.compare(other=fixed_out, keys=["equity_npv"]).summary()
```

**Try it 2: no funding check.** Remove the funding condition from Building B's rule.
On how many paths does the commitment gap become positive?

```python
# solution
reckless = strategy.decide(
    key="b_start",
    when="rent_index >= 1.10",
    review=yearly,
    window=("shared_start + 1 year", date(2033, 1, 1)),
    otherwise="never",
)
reckless_out = rk.execution.solve(
    specification=reckless.across(paths=paths, assign=assign)
)
gaps = reckless_out.distribution(key="commitment_gap")
gaps.probability(above="0 AUD")
```

**Try it 3: a worse site price.** Lower Building B's land share to 25 %. How does
the paired difference change on the paths where B never starts?

```python
# solution
cheap_site = strategy.fix(b_land_share="25 %")
cheap = rk.execution.solve(specification=cheap_site.across(paths=paths, assign=assign))
cheap.compare(other=fixed_out, keys=["equity_npv"]).where(b_start="never").summary()
```

## Checks and recap

```python
# cell 18 (checks)
assert flex_out.run.market_paths == fixed_out.run.market_paths == paths.id
assert all(
    row.available_on <= row.decision_date for row in flex_out.decisions().observations()
)
starts = flex_out.decisions().where(value="b_start", result="decided")
assert all(row.observed["funding.headroom"] >= row.observed["b_cost"] for row in starts)
assert flex_out.case(key=paths.keys[0]).run.policy_evidence.verified
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

16 core code cells, 1 optional cell and 1 check cell (budget 20–25), 3 exercise
solutions. The longest cell has 14 lines (cell 11). Cells follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2 | 1, 10 | G26; G47: `equations.involving(keys)` |
| 4 | 10 | G48: `MarketPaths` from explicit Flows (the three histories are data, made once) |
| 6 | 2, 6 | G49: `Specification.decide(key, when=, review=, window=, otherwise=)`, the "decided" role, rules as strings |
| 6, 10, 13 | 5 | G50: `never` for date values; functions treat a `never` date as "no flow" |
| 7, 12 | 8, 9 | G51: `Outcome.trace()` and `Outcome.decisions()` tables; infeasible decided values name the constraint (G52) |
| 8 | 9 | G53: `AvailabilityError` at Specification validation ([#139](https://github.com/daniel-fink/rangekeeper/issues/139)) |
| 9 | 6 | G54: sequential solve: a rule observes solved values (funding) under the decisions so far ([#213](https://github.com/daniel-fink/rangekeeper/issues/213)) |
| 9, 11 | 3 | G55: decision windows with expression bounds; rules that observe earlier decisions (`b_start == never`) |
| 10 | 2, 3 | G27 (`extend`); G17 (`at`, `event`) |
| 13–16 | 8 | G56: `Outcome.compare(other=, keys=)` paired by path, with `summary`, `by`, `by_case`, `where` |
| 15 | 10 | Helper draws only |
| 17 | 2 | G57: Specification parameters for rules, and cases × paths |
| 18 | 8 | G58: policy evidence in the Run (`policy_evidence.verified`), observations with `available_on` |

## Cells for #213

The design for sequential decisions must support:

- **Observations.** A rule names Model values (`rent_index`, `funding.headroom`,
  `b_cost`) and earlier decided values (`b_start == never`). The value read is the
  latest one available on the review date.
- **Availability.** Market path Flows carry availability dates (period end by
  default). Solved values, such as funding headroom, are available on the review date
  when they depend only on Movements up to that date. Validation rejects a rule that
  reads a later value (cell 8).
- **Decided values.** A date value, or "never". The decision fixes the value; the
  Model's relations and constraints move the dependent dates (cells 6, 9, 11).
- **Windows.** Review dates from a start to an end, with bounds that can be
  expressions of earlier decisions (cell 9).
- **Funding.** The rule observes the funding account under the decisions made so far,
  so evaluation alternates review and solve in date order (cell 9).
- **Traces.** For each case and review: date, decided value, observations with their
  availability dates, the rule's truth and the result (cells 7, 11).
- **Paired comparison.** Two Outcomes on the same pinned `MarketPaths`, matched by
  path key (cells 13–16).
