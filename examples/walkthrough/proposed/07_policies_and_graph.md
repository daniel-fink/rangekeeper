# Lesson 07: Policies and the model graph (proposed cells)

Issue: [#244](https://github.com/daniel-fink/rangekeeper/issues/244). Plan:
[ADR-020 §07](../../../docs/decisions/020-walkthrough-plan-v2.md#07-policies-and-the-model-graph).
Design: [#214](https://github.com/daniel-fink/rangekeeper/issues/214) (design
variants). Implementation: [#216](https://github.com/daniel-fink/rangekeeper/issues/216)
and [#215](https://github.com/daniel-fink/rangekeeper/issues/215).
API conventions and the gap list: [README](README.md).

Decisions used here (D9 and D10 in the [README](README.md#decisions)): each design
option is its own Model revision. A Specification lists the alternatives, and the
choice between them is a decided value, like lesson 05's dates. A provision cost is a
Specification value, so a sweep can change it.

The lesson is not authored until #216 is verified (ADR-020).

## Goals box

> **Question.** Which design provisions are worth paying for now?
>
> **You will learn to:**
>
> 1. make a design alternative as a new Model revision, and roll up its structure;
> 2. let a rule choose between alternatives, together with lesson 05's timing rules;
> 3. compare the fixed design, timing flexibility, a provision and the combination on
>    the same paths, with the provision paid on every path;
> 4. find the largest provision cost that a criterion justifies, and check that the
>    rules do not change with it;
> 5. choose a threshold on one path set and test it on another.
>
> **Before you start.** Lessons 05 and 06.
>
> **Time.** 60 minutes core, 30 minutes optional (vertical expansion).
>
> **Not in this lesson.** A search for the best possible strategy. The best strategy
> tested here is not a global optimum.
>
> **Source.** de Neufville and Geltner (2018), chapters on flexibility in and on
> projects, cited by section.

## 1. The property, its plan and its markets

Narrative: start from the property graph of lesson 06 with the dated plan of lessons
03–05. The building incomes, operating costs and budgets are now rollups of the
floors. Each use's index is lesson 04's market index times a factor of its own (lesson
04's optional section). The Model writes that as an equation.

```python
# cell 1
from datetime import date

import rangekeeper as rk
import helpers
```

```python
# cell 2
residential = rk.io.load(path=helpers.data_path(name="07_property_plan.model.json"))
use_paths = rk.io.load(path=helpers.data_path(name="04_use_factors.paths.json"))
plan = helpers.load_base_plan()
residential.rollups()  # key, value rolled up, relationship, root and contributors
```

Narrative: start from lesson 04's Specification. It fixed each building's income,
operating cost and budget as totals. Here the floors give those totals, so free them
and fix the rates by use in their place. As in lesson 04, the market indices carry
all rent growth.

```python
# cell 3
yearly = rk.duration.Frequency.YEAR
base = rk.io.load(path=helpers.data_path(name="04_base_case.specification.json"))
fixed = (
    base.on(model=residential)
    .free("a_income", "b_income", "a_opex", "b_opex", "a_cost", "b_cost")
    .fix(efficiency=plan["efficiency"], rent=plan["rent"], vacancy=plan["vacancy"])
    .fix(b_land_share="40 %", provision="0 AUD")
)
```

Narrative: the paths hold `market_index` and one factor for each use. The Model
declares `market_index`, a keyed `use_factor` with one member for each use, and the
equation `use_index = market_index * use_factor`. `market_index` matches by name. The
factors' names differ from the Model's, so `across` needs `series=`: the path series
for each member.

```python
# cell 3b
use_series = {
    "use_factor": {
        "hotel": "hotel_factor",
        "residential": "residential_factor",
        "retail": "retail_factor",
    }
}
residential.equations.where(keys=["use_index"])  # use_index = market_index * use_factor
```

## 2. A design alternative

Narrative: a paid provision lets Building B open as a hotel in place of residential.
It is not a new rent label. A hotel needs more cores and plant, so the alternative
changes the structure: the floors take the hotel use, and new cores and services
join Building B. Make it as a new revision of the same Model.

```python
# cell 4
draft = residential.edit(name="Building B as hotel")
draft.relabel(
    filter=rk.model.Filter(classification="floor", within="building_b"), use="hotel"
)
# cores and plant, with their costs
draft.include(fragment=helpers.load_fragment(name="building_b_hotel_services"))
hotel = draft.commit()
```

```python
# cell 5
# relabelled floors, added entities and relationships
rk.model.diff(before=residential, after=hotel)
```

Narrative. **Predict:** which of Building B's totals change? Roll up the same values
over both structures.

```python
# cell 6
# one row for each of Building B's totals, one column for each design
rk.model.compare(
    models={"Residential": residential, "Hotel": hotel},
    rollups=["b_income", "b_opex", "b_cost"],
)
```

> **Finance note.** Flexibility *in* a project is a design change that keeps a choice
> open, such as structure for a hotel use. Flexibility *on* a project is a choice
> about the project as built, such as when to start. A provision has a cost now, on
> every path, whether or not the choice is ever used.

## 3. A rule chooses the design

Narrative: the alternatives are part of the question, so they belong in the
Specification. The choice of design is a decided value. Before Building B starts,
choose the hotel if the hotel market has outgrown the residential market by 10 %.
Otherwise build residential. The provision is paid when the site is bought.

```python
# cell 7
timing = rk.io.load(path=helpers.data_path(name="05_strategy.specification.json")).rules
design_reviews = rk.duration.Span(start=date(2028, 1, 1), end=date(2033, 1, 1)).periods(
    frequency=yearly
)
timing  # lesson 05's three rules, as written there
```

Narrative: the rule reads the Model's keyed index, one member for each use. The
threshold is a value in the Specification, so section 7 can sweep it. Building B's
design is reviewed each January from 2028, from a year after the shared works start
until the year before Building B starts.

```python
# cell 7b
switch = (
    fixed.alternatives(b_design={"residential": residential, "hotel": hotel})
    .fix(provision="2.5e6 AUD")
    .parameters(switch_threshold=1.10)
    .decide(
        key="b_design",
        when='use_index["hotel"] >= switch_threshold * use_index["residential"]',
        periods=design_reviews,
        earliest="shared_start + 1 year",
        latest="b_start - 1 year",
        then="hotel",
        otherwise="residential",
    )
)
```

```python
# cell 8
strategies = {
    "fixed": fixed,
    "timing": fixed.with_rules(rules=timing),
    "switch": switch,
    "both": switch.with_rules(rules=timing),
}
strategy_outcomes = {}
for name, strategy in strategies.items():
    on_paths = strategy.across(paths=use_paths, series=use_series)
    strategy_outcomes[name] = rk.execution.solve(specification=on_paths)
```

## 4. Paired comparison of four strategies

Narrative: every strategy ran on the same paths. Compare each with the fixed
design, path by path. The provision is in every path of `switch` and `both`, also
where Building B stays residential.

```python
# cell 9
comparison = rk.execution.compare(
    outcomes=strategy_outcomes, keys=["equity_npv", "peak_shortfall"], baseline="fixed"
)
comparison.summary()  # mean difference, share better, 5 % quantile
```

```python
# cell 10
helpers.plot_target_curve(outcomes=strategy_outcomes, key="equity_npv")
```

## 5. What gets built

Narrative: report the delivered projects as well as their value. How often does
Building B open as a hotel? What is the use mix of the realised design?

```python
# cell 11
both_outcome = strategy_outcomes["both"]
both_outcome.distribution(key="b_design").counts()
```

```python
# cell 12
floors = rk.model.Filter(classification="floor")
both_outcome.rollup(
    of="nla",
    over="contains",
    root="property",
    contributors=floors,
).pivot(columns="use").describe()
```

## 6. The largest justified premium

Narrative: the provision is paid at the start, from equity. If the rules do not
depend on its cost, every dollar of provision lowers the equity NPV by its present
value on every path. Then the largest justified premium under the mean criterion is
the mean paired gain without the provision. **Check the "if" first**: run the
strategy at several provision costs and confirm that the decisions are the same.

```python
# cell 13
premiums = {
    "0 AUD": {"provision": "0 AUD"},
    "2.5e6 AUD": {"provision": "2.5e6 AUD"},
    "5e6 AUD": {"provision": "5e6 AUD"},
    "7.5e6 AUD": {"provision": "7.5e6 AUD"},
}
premium_sweep = (
    strategies["both"].cases(cases=premiums).across(paths=use_paths, series=use_series)
)
premium_outcome = rk.execution.solve(specification=premium_sweep)
premium_outcome.decisions().same_across_cases()  # are the decisions the same at every premium?
```

```python
# cell 14
gain = rk.execution.compare(
    outcomes={"Premiums": premium_outcome, "Timing": strategy_outcomes["timing"]},
    keys=["equity_npv"],
    baseline="Timing",
).by_case()
gain.summary()
gain.breakeven(key="provision", criterion=rk.execution.Criterion.MEAN)
```

> **Finance note.** The provision uses equity and loan capacity that Building B's
> rule needs. If the decisions change with the premium, read the largest justified
> premium from the sweep, not from one run. State the criterion: a mean criterion
> and a 5 % quantile criterion give different premiums.

## 7. Choose on one path set, test on another

Narrative: a threshold chosen on the same paths that test it looks better than it is.
Choose the switch threshold on lesson 04's paths, then test it on new paths from the
same generator with a new seed.

```python
# cell 15
thresholds = {
    "1.00": {"switch_threshold": 1.00},
    "1.05": {"switch_threshold": 1.05},
    "1.10": {"switch_threshold": 1.10},
    "1.20": {"switch_threshold": 1.20},
}
```

```python
# cell 15b
threshold_sweep = strategies["both"].cases(cases=thresholds)
```

```python
# cell 15c
train_outcome = rk.execution.solve(
    specification=threshold_sweep.across(paths=use_paths, series=use_series)
)
by_threshold = rk.execution.compare(
    outcomes={"Thresholds": train_outcome, "Timing": strategy_outcomes["timing"]},
    keys=["equity_npv"],
    baseline="Timing",
).by_case()
best = by_threshold.best(criterion=rk.execution.Criterion.MEAN)
```

```python
# cell 16
fresh = use_paths.regenerate(seed=2)  # the same generator, periods and count
chosen = threshold_sweep.case(key=best)
test_outcome = rk.execution.solve(
    specification=chosen.across(paths=fresh, series=use_series)
)
timing_only = strategies["timing"].across(paths=fresh, series=use_series)
baseline_outcome = rk.execution.solve(specification=timing_only)
# usually less than in training
rk.execution.compare(
    outcomes={"Chosen": test_outcome, "Timing": baseline_outcome},
    keys=["equity_npv"],
    baseline="Timing",
).summary()
```

## Optional: vertical expansion

Narrative: stronger structure in Building A, paid now, lets it add three floors
later. The expanded design adds the floors, labelled `phase="expansion"`. Building
A's own rollups count only `phase="base"` floors, so the new floors need their own
rollups and their own dates. The floor equations of lesson 06 apply to the new floors
too, because they match the same filter. A rule decides the expansion date.

```python
# cell 17
draft = residential.edit(name="Building A expanded")
site = draft.entity(code="property")
draft.include(fragment=helpers.load_fragment(name="building_a_extra_floors"))
extra = rk.model.Filter(classification="floor", labels={"phase": "expansion"})
```

Narrative: the new floors have their own income and cost, rolled up under Building A.

```python
# cell 17b
site.rollup(
    key="x_income",
    of="income",
    over="contains",
    root="building_a",
    contributors=extra,
)
site.rollup(
    key="x_cost",
    of="build_cost",
    over="contains",
    root="building_a",
    contributors=extra,
)
```

Narrative: the expansion is built in one year from its date, and earns from the year
after. Add both to the existing works and income.

```python
# cell 17c
site.date(key="expansion_date")
site.equations("x_open = expansion_date + 1 year")
site.add_to(
    key="works",
    term="-rx.profile.uniform(total=x_cost, start=expansion_date, years=1)",
)
site.add_to(key="income", term="rx.profile.constant(initial=x_income, start=x_open)")
expanded = draft.commit()
```

```python
# cell 18
expansion_reviews = rk.duration.Span(
    start=date(2030, 1, 1), end=date(2035, 1, 1)
).periods(frequency=yearly)
expand = (
    strategies["both"]
    .alternatives(a_design={"base": residential, "expanded": expanded})
    .fix(a_provision="1.5e6 AUD")
    .decide(
        key="expansion_date",
        when='use_index["residential"] >= 1.25',
        periods=expansion_reviews,
        earliest="a_open + 3 years",
        otherwise=rk.duration.NEVER,
    )
)
```

```python
# cell 18b
expand_outcome = rk.execution.solve(
    specification=expand.across(paths=use_paths, series=use_series)
)
rk.execution.compare(
    outcomes={"Expand": expand_outcome, "Both": strategy_outcomes["both"]},
    keys=["equity_npv"],
    baseline="Both",
).summary()
```

## Exercises

**Try it 1: the cost of a provision never used.** On how many paths does Building B
stay residential? What does the switch strategy lose on those paths?

```python
# solution
switch_vs_fixed = rk.execution.compare(
    outcomes=strategy_outcomes, keys=["equity_npv"], baseline="fixed"
).select("switch")
switch_vs_fixed.where(b_design="residential").summary()
```

**Try it 2: a cautious criterion.** Find the largest justified premium under the 5 %
quantile criterion.

```python
# solution
gain.breakeven(key="provision", criterion=rk.execution.Criterion.QUANTILE, level=0.05)
```

**Try it 3: the switch without timing flexibility.** Is the switch worth more with or
without lesson 05's rules?

```python
# solution
comparison.select("switch", "both").summary()
```

## Checks and recap

```python
# cell 19 (checks)
for outcome in strategy_outcomes.values():
    assert outcome.run.market_paths == use_paths.id  # the same paths
provision_paid = both_outcome.table("provision_cost")["provision_cost"]
assert (provision_paid < 0).all()  # paid on every path
first = use_paths.keys[0]
assert both_outcome.case(key=first).model.id in (residential.id, hotel.id)
assert rk.model.diff(
    before=residential, after=hotel
).added_entities  # a structural change
```

**Recap.**

1. A design alternative is a new revision of the Model. Rollups over each revision
   show what each design delivers.
2. A rule chooses between alternatives in the same way that it chooses dates. The
   provision is paid on every path.
3. A justified premium needs a stated criterion, a check that the rules do not
   change with it, and a test on paths that did not choose the thresholds.

**Next.** The book ends here. The "Start here" page lists further reading and the
how-to guides.

## Cell budget

20 core code cells, 5 optional cells and 1 check cell (budget 20–25), 3 exercise
solutions. The longest cell has 16 lines (optional cell 18). Cells follow
`ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2 | 1, 10 | G26; G59: `Model.rollups()` table |
| 3–3b | 2, 4 | G43 (keyed values, and a keyed equation `use_index = market_index * use_factor`); G60, G73: `series=` maps a keyed Flow value to several path series (D31) |
| 4 | 2, 7 | G61: `edit(name=)`, `relabel(filter, **labels)`, `include(fragment)`; `Filter(within=)` ([#121](https://github.com/daniel-fink/rangekeeper/issues/121)) |
| 5 | 7 | G62: `rk.model.diff(a, b)` with typed parts |
| 6 | 7, 8 | G74: `rk.model.compare(models=, rollups=)` gives one table of declared rollups by design |
| 7b | 2, 6 | G63: `Specification.alternatives(key={name: Model})` and a decided Model choice with `then=` (ADR-022); G49 (`periods=`), G55 (`earliest=`, `latest=`), G57 (`parameters`); keyed members in rule text (`use_index["hotel"]`) |
| 7 | 1, 10 | G64: `Specification.rules` reads the rules of a saved Specification, so lesson 05's rules are loaded as a document, not from a helper |
| 8 | 2 | G65: `Specification.with_rules(rules)` |
| 9–10 | 8 | G66: `rk.execution.compare(outcomes=, keys=, baseline=)` for several strategies |
| 11 | 8 | G31: `distribution(key=).counts()` for a decided choice |
| 12 | 7, 8 | G46 for batches: `Outcome.rollup(...)` over each case's realised Model |
| 13 | 8 | G67: `decisions().same_across_cases()` |
| 14 | 8 | G68: `by_case().breakeven(key=, criterion=, level=)` and `best(criterion=)` with `rk.execution.Criterion` |
| 15–15c | 2 | G57: the threshold swept as cases; G75: `Specification.case(key=)` (cell 16) |
| 16 | 4, 6 | G69: `Paths.regenerate(seed=)` rebuilds the generator from the capture record |
| 17–17c | 2, 3 | G61, G17; G27 (`add_to(key=, term=)` adds a term to one side of an equation) |
| 18 | 6 | G63 with two alternative keys at once; G50 (`rk.duration.NEVER`) |
| 19 | 8 | G62, G33 |

## Cells for #214

The design for structural variants must support:

- **Alternatives as Model revisions.** `edit()`, `relabel`, `include` and `commit`
  make each option (cell 4). The options share the property entity and the equations; they
  differ in structure.
- **A bounded choice in the Specification.** `alternatives(key={name: Model})` pins
  each option's revision. The choice is a decided value with review Periods, bounds and a
  default (cell 7b). Several choices can be open at once (cell 18).
- **Realised structure per path.** Each case's Outcome carries the realised Model, so
  rollups and pivots work per path and across the batch (cells 11–12).
- **Geometry of each option.** The hotel fragment carries geometry, so that
  `helpers.show_geometry(model=both_outcome.case(key=...).model, color_by="use")` can show
  Building B as built on one path. The proposed cells do not show it yet; add it
  when the fragment data exists.
- **Provision on every path.** The provision is an ordinary fixed value in the
  Specification, and its cash flow is in every option's equations (cells 7, 13, 19).
- **Paired evaluation.** All strategies on one pinned `rk.market.Paths`, compared by path
  against a named baseline (cells 9, 14, 16).
- **Kept apart from optimisation.** Threshold and premium sweeps are cases. Nothing
  searches the rule space (cells 13, 15).
